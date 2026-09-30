# phone_detect.py - UPM auto-configuration for IP phones (ToIP), Python version.
#
# On LLDP device-detect of an IP phone (GEN_TEL_PHONE) the port gets the voice
# VLAN tagged, LLDP-MED voice policy (DSCP 46), power-via-MDI, a PoE
# operator limit and DiffServ examination. On device-undetect it all gets
# reverted, unless the phone's MAC is still seen by LLDP on the port (see
# upm_mac_guard.py).
#
# The voice VLAN is not hardcoded: it is discovered from "show vlan" by
# name, with VOICE_VLAN_PATTERN below. One voice VLAN per switch is expected
# (the first match is used). Adapt the pattern to your naming convention.
#
# Same logic as phone_detect.xsf (the CLI-scripting version); only the
# language and the MAC guard (any separator, shared module) change.
#
# Requirements:
#   - EXOS 32.2 or later (native Python 3.8), "configure security python on".
#   - upm_mac_guard.py in the same directory (/usr/local/cfg).
#   - Once per switch:
#       configure diffserv examination code-point 46 qosprofile qp8
#       configure diffserv examination code-point 32 qosprofile qp8
#
# UPM profiles (a one-line .xsf wrapper that calls this script):
#
#   create upm profile PHONE_DETECT_PY
#   load script phone_detect.py connect $EVENT.DEVICE $EVENT.USER_PORT $EVENT.DEVICE_MAC $EVENT.DEVICE_POWER
#   .
#   create upm profile PHONE_DETECT_PY_REMOVE
#   load script phone_detect.py disconnect $EVENT.DEVICE $EVENT.USER_PORT $EVENT.DEVICE_MAC $EVENT.DEVICE_POWER
#   .
#   configure upm event device-detect profile "PHONE_DETECT_PY" ports <access_ports>
#   configure upm event device-undetect profile "PHONE_DETECT_PY_REMOVE" ports <access_ports>
#
# Arguments:
#   sys.argv[1] = "connect" | "disconnect"
#   sys.argv[2] = $EVENT.DEVICE        (LLDP device type)
#   sys.argv[3] = $EVENT.USER_PORT     (port)
#   sys.argv[4] = $EVENT.DEVICE_MAC    (device MAC, used by the disconnect guard)
#   sys.argv[5] = $EVENT.DEVICE_POWER  (PoE limit reported by the phone, connect
#                                       only; some phones report "0" and that
#                                       single command fails without stopping
#                                       the rest of the script)
#
# Manual test (without UPM):
#   run script phone_detect.py connect GEN_TEL_PHONE 1:2 00:11:22:33:44:55 6300
#   run script phone_detect.py disconnect GEN_TEL_PHONE 1:2 00:11:22:33:44:55 6300

import re
import sys

import exsh

from upm_mac_guard import log, mac_still_present

# Voice VLAN name pattern - adapt to your naming convention.
VOICE_VLAN_PATTERN = re.compile(r"\S*(?:toip|voice)\S*", re.IGNORECASE)


def discover_voice_vlan():
    """Voice VLAN name found in "show vlan", or None."""
    output = exsh.clicmd("show vlan", True)
    match = VOICE_VLAN_PATTERN.search(output)
    return match.group(0) if match else None


def apply_voice_config(port, device_power):
    voicevlan = discover_voice_vlan()
    if voicevlan is None:
        log("Voice_script_error_no_voice_vlan_found_on_%s" % port)
        return

    log("Voice_Device_Detected_on_%s" % port)
    exsh.clicmd("configure vlan %s add port %s tagged" % (voicevlan, port), True)
    exsh.clicmd("configure lldp ports %s advertise vendor-specific med capabilities" % port, True)
    exsh.clicmd(
        "configure lldp ports %s advertise vendor-specific dot1 vlan-name vlan %s" % (port, voicevlan), True
    )
    exsh.clicmd(
        "configure lldp ports %s advertise vendor-specific med policy application voice vlan %s dscp 46"
        % (port, voicevlan),
        True,
    )
    exsh.clicmd("configure lldp ports %s advertise vendor-specific med power-via-mdi" % port, True)
    exsh.clicmd("configure inline-power operator-limit %s ports %s" % (device_power, port), True)
    exsh.clicmd("enable diffserv examination ports %s" % port, True)


def revert_voice_config(port):
    voicevlan = discover_voice_vlan()
    if voicevlan is None:
        log("Voice_script_error_no_voice_vlan_found_on_%s" % port)
        return

    log("Voice_Device_Removed_from_%s" % port)
    exsh.clicmd("disable diffserv examination ports %s" % port, True)
    exsh.clicmd(
        "configure lldp ports %s no-advertise vendor-specific med policy application voice vlan %s dscp 46"
        % (port, voicevlan),
        True,
    )
    exsh.clicmd(
        "configure lldp ports %s no-advertise vendor-specific dot1 vlan-name vlan %s" % (port, voicevlan), True
    )
    exsh.clicmd("configure lldp ports %s no-advertise vendor-specific med power-via-mdi" % port, True)
    exsh.clicmd("configure lldp ports %s no-advertise vendor-specific med capabilities" % port, True)
    exsh.clicmd("unconfigure inline-power operator-limit ports %s" % port, True)
    exsh.clicmd("configure vlan %s delete port %s" % (voicevlan, port), True)


def handle_connect(event_device, port, device_power):
    if event_device == "GEN_TEL_PHONE":
        apply_voice_config(port, device_power)


def handle_disconnect(port, device_mac):
    # No filtering on $EVENT.DEVICE here: it is not reliable on
    # device-undetect. The MAC guard decides instead.
    if mac_still_present(port, device_mac):
        log("Voice_Undetect_Ignored_on_%s" % port)
    else:
        revert_voice_config(port)


def main():
    if len(sys.argv) < 6:
        log("Voice_script_error_missing_arguments")
        return

    action = sys.argv[1]
    event_device = sys.argv[2]
    port = sys.argv[3]
    device_mac = sys.argv[4]
    device_power = sys.argv[5]

    if action == "connect":
        handle_connect(event_device, port, device_power)
    else:
        handle_disconnect(port, device_mac)


if __name__ == "__main__":
    main()
