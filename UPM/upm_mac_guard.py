# upm_mac_guard.py - shared helpers for the UPM auto-configuration scripts
# (ap_detect.py, phone_detect.py).
#
# Why a MAC guard: on the LLDP device-undetect event, $EVENT.DEVICE is not a
# reliable way to know whether the device is really gone (it often arrives as
# "OTHER"), and LLDP neighbours can flap or change identity. Before reverting
# a port's configuration, the scripts check whether the device's MAC still
# appears anywhere in "show lldp port <port> neighbors detailed". If it does,
# the undetect is ignored. This check is vendor-agnostic: it does not depend
# on any vendor-specific text in the LLDP description.
#
# Deployment: copy this file to /usr/local/cfg on the switch, next to the
# scripts that import it ("from upm_mac_guard import ...").

import re

import exsh


def log(message):
    exsh.clicmd("create log message %s" % message, True)


def lldp_neighbors_detailed(port):
    return exsh.clicmd("show lldp port %s neighbors detailed" % port, True)


def mac_regex(device_mac):
    """Pattern that matches device_mac whatever separator the LLDP text uses
    (":", "-", "." or none), including the Cisco dotted format (every 4
    digits): an OPTIONAL separator between each pair of hex digits covers all
    of them at once. Case-insensitive."""
    hex_digits = re.sub(r"[^0-9A-Fa-f]", "", device_mac)
    if len(hex_digits) != 12:
        # $EVENT.DEVICE_MAC without 12 recognisable hex digits should not
        # happen; fall back to the simple "optional colon" pattern.
        return re.compile(re.sub(r":", ":?", device_mac), re.IGNORECASE)
    octets = [hex_digits[i:i + 2] for i in range(0, 12, 2)]
    pattern = r"[:\-.]?".join(octets)
    return re.compile(pattern, re.IGNORECASE)


def mac_still_present(port, device_mac):
    """True if device_mac still appears anywhere in the output of
    "show lldp port <port> neighbors detailed", whatever LLDP entry it is
    under now. Use this, not $EVENT.DEVICE, as the guard in the disconnect
    branch of any auto-configuration UPM profile."""
    output = lldp_neighbors_detailed(port)
    return mac_regex(device_mac).search(output) is not None
