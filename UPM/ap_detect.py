# ap_detect.py - UPM auto-configuration for WiFi access points, Python version.
#
# On LLDP device-detect of an AP the port gets the AP management VLAN
# untagged and every WiFi VLAN tagged (and, optionally, FDB mac-tracking is
# removed from the port). On device-undetect it all gets reverted to
# DEFAULT_VLAN untagged, unless the AP's MAC is still seen by LLDP on the
# port (see upm_mac_guard.py).
#
# VLANs are not hardcoded: they are discovered from a single "show vlan" by
# name, with the patterns below. Adapt them to your naming convention.
#
# How an AP is recognised on connect:
#   - $EVENT.DEVICE == "WLAN_ACCESS_PT" (APs that send LLDP-MED): an AP.
#   - $EVENT.DEVICE == "BRIDGE" (APs without LLDP-MED, e.g. Cisco): ambiguous,
#     so the LLDP free text ("show lldp port <port> neighbors detailed") is
#     searched for one of AP_TEXT_MARKERS. Add your vendors' strings there.
#   - $EVENT.DEVICE == "ROUTER": treated like BRIDGE. Lab aid: an AP simulated
#     with lldpd in GNS3 is classified as ROUTER by EXOS even when it
#     advertises the Bridge capability. Real APs showed up as BRIDGE.
#   - Anything else: ignored without querying LLDP.
#
# Requirements:
#   - EXOS 32.2 or later (native Python 3.8), "configure security python on".
#   - upm_mac_guard.py in the same directory (/usr/local/cfg).
#
# UPM profiles (a one-line .xsf wrapper that calls this script):
#
#   create upm profile AP_DETECT_PY
#   load script ap_detect.py connect $EVENT.DEVICE $EVENT.USER_PORT $EVENT.DEVICE_MAC
#   .
#   create upm profile AP_DETECT_PY_REMOVE
#   load script ap_detect.py disconnect $EVENT.DEVICE $EVENT.USER_PORT $EVENT.DEVICE_MAC
#   .
#   configure upm event device-detect profile "AP_DETECT_PY" ports <ap_ports>
#   configure upm event device-undetect profile "AP_DETECT_PY_REMOVE" ports <ap_ports>
#
# Arguments (in Python the $EVENT.* values must be passed explicitly on the
# "load script" line; there is no $(EVENT.*) substitution inside a .py):
#   sys.argv[1] = "connect" | "disconnect"
#   sys.argv[2] = $EVENT.DEVICE        (LLDP device type)
#   sys.argv[3] = $EVENT.USER_PORT     (port)
#   sys.argv[4] = $EVENT.DEVICE_MAC    (device MAC, used by the disconnect guard)
#
# Manual test (without UPM):
#   run script ap_detect.py connect WLAN_ACCESS_PT 1:1 00:11:22:33:44:55
#   run script ap_detect.py disconnect WLAN_ACCESS_PT 1:1 00:11:22:33:44:55

import re
import sys

import exsh

from upm_mac_guard import log, lldp_neighbors_detailed, mac_still_present

# --- Settings: adapt to your network ------------------------------------------

# Untagged AP management VLAN: one per switch expected (first match is used).
AP_MGMT_VLAN_PATTERN = re.compile(r"\S*ap_mgmt\S*", re.IGNORECASE)

# Tagged WiFi VLANs: every VLAN whose name contains "wifi" or "eduroam".
WIFI_VLAN_PATTERN = re.compile(r"\S*(?:wifi|eduroam)\S*", re.IGNORECASE)

# LLDP free-text markers that identify an AP reported as BRIDGE/ROUTER.
AP_TEXT_MARKERS = [
    re.compile(r"Cisco AP Software", re.IGNORECASE),
]

# Behind an AP there are the MACs of all its WiFi clients. If your NAC is
# triggered by FDB mac-tracking (one device per access port), remove
# mac-tracking from AP ports while the AP is connected and restore it after.
# (Originally written for a FortiNAC deployment triggered by the mac-tracking
# trap; see README.md.) Set to False if your NAC does not rely on it.
NAC_USES_FDB_MAC_TRACKING = True

# ------------------------------------------------------------------------------


def discover_ap_vlans():
    """One "show vlan" to find both the untagged AP management VLAN and the
    tagged WiFi VLANs. Returns (untagged_or_None, tagged_list_no_duplicates)."""
    output = exsh.clicmd("show vlan", True)

    untagged_match = AP_MGMT_VLAN_PATTERN.search(output)
    untagged = untagged_match.group(0) if untagged_match else None

    tagged = []
    for name in WIFI_VLAN_PATTERN.findall(output):
        if name not in tagged and name != untagged:
            tagged.append(name)

    return untagged, tagged


def lldp_text_looks_like_ap(port):
    """Search the LLDP free text of the port for any AP_TEXT_MARKERS. Only
    used to classify the device on connect, never as the disconnect guard
    (a vendor string would wrongly revert other vendors' APs)."""
    output = lldp_neighbors_detailed(port)
    return any(marker.search(output) for marker in AP_TEXT_MARKERS)


def is_ap(event_device, port):
    if event_device == "WLAN_ACCESS_PT":
        return True
    if event_device in ("BRIDGE", "ROUTER"):
        return lldp_text_looks_like_ap(port)
    return False


def apply_ap_config(port):
    untagged, tagged = discover_ap_vlans()
    if untagged is None:
        log("AP_script_error_no_untagged_vlan_found_on_%s" % port)
        return
    if not tagged:
        log("AP_script_warning_no_wifi_vlans_found_on_%s" % port)

    log("AP_Detected_on_%s" % port)
    exsh.clicmd("configure vlan %s add port %s untagged" % (untagged, port), True)
    for vlan in tagged:
        exsh.clicmd("configure vlan %s add port %s tagged" % (vlan, port), True)
    if NAC_USES_FDB_MAC_TRACKING:
        exsh.clicmd("configure fdb mac-tracking delete ports %s" % port, True)


def revert_ap_config(port):
    untagged, tagged = discover_ap_vlans()
    if untagged is None:
        log("AP_script_error_no_untagged_vlan_found_on_%s" % port)
        return

    log("AP_Removed_from_%s" % port)
    for vlan in tagged:
        exsh.clicmd("configure vlan %s delete port %s" % (vlan, port), True)
    exsh.clicmd("configure vlan %s delete port %s" % (untagged, port), True)
    exsh.clicmd("configure vlan DEFAULT_VLAN add port %s untagged" % port, True)
    if NAC_USES_FDB_MAC_TRACKING:
        exsh.clicmd("configure fdb mac-tracking add ports %s" % port, True)


def handle_connect(event_device, port):
    if is_ap(event_device, port):
        apply_ap_config(port)


def handle_disconnect(port, device_mac):
    # No filtering on $EVENT.DEVICE here: it is not reliable on
    # device-undetect. The MAC guard decides instead.
    if mac_still_present(port, device_mac):
        log("AP_Undetect_Ignored_on_%s" % port)
    else:
        revert_ap_config(port)


def main():
    if len(sys.argv) < 5:
        log("AP_script_error_missing_arguments")
        return

    action = sys.argv[1]
    event_device = sys.argv[2]
    port = sys.argv[3]
    device_mac = sys.argv[4]

    log("AP_script_devtype_%s_is_%s" % (port, event_device))

    if action == "connect":
        handle_connect(event_device, port)
    else:
        handle_disconnect(port, device_mac)


if __name__ == "__main__":
    main()
