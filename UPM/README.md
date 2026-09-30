# UPM scripts: automatic port configuration for IP phones and WiFi APs

EXOS / Switch Engine **Universal Port Manager (UPM)** scripts that configure an access port
when LLDP detects an IP phone (ToIP) or a WiFi access point, and revert it when the device
leaves. The VLANs are **not hardcoded**: each script discovers them from `show vlan` by
name, so the same scripts work on every switch and building as long as VLAN names follow a
convention.

> **Note:** these are cleaned-up versions of scripts used in a real deployment. Site-specific
> names were removed, VLAN names became configurable patterns and the comments were
> rewritten. The cleaned-up versions have **not** been tested on a switch, so the cleanup
> itself may have introduced bugs. Test them in a lab before production use (see
> [Validation status](#validation-status) for what the original versions were tested on).

| File | What it does |
|---|---|
| `phone_detect.py` | IP phone (`GEN_TEL_PHONE`): voice VLAN tagged, LLDP-MED voice policy (DSCP 46), power-via-MDI, PoE operator limit, DiffServ examination. Reverted on undetect. |
| `phone_detect.xsf` | Same as `phone_detect.py` in EXOS CLI scripting (no Python needed). |
| `ap_detect.py` | WiFi AP: AP management VLAN untagged, every WiFi VLAN tagged, optionally removes FDB mac-tracking from the port. Reverted to `DEFAULT_VLAN` on undetect. |
| `upm_mac_guard.py` | Shared module used by both Python scripts: the MAC-based disconnect guard and logging. |

## How it works

- **Connect** (UPM `device-detect`): the script checks `$EVENT.DEVICE`. `GEN_TEL_PHONE` is a
  phone. `WLAN_ACCESS_PT` is an AP. `BRIDGE` (APs without LLDP-MED, e.g. Cisco) is ambiguous,
  so the script looks for a marker such as `Cisco AP Software` in the LLDP free text.
- **Disconnect** (UPM `device-undetect`): `$EVENT.DEVICE` is **not reliable** here (it often
  arrives as `OTHER`), and LLDP neighbours can flap. Before reverting anything, the script
  checks whether the device's MAC still appears in `show lldp port <port> neighbors detailed`.
  If it does, the undetect is ignored. The MAC is matched with any separator (`:`, `-`, `.`
  or none), because the format in LLDP fields varies by field and vendor.

## Adapt to your network

Edit the settings at the top of each script:

| Setting | Default | Meaning |
|---|---|---|
| `VOICE_VLAN_PATTERN` (`phone_detect.py`, and the `regexp` line in `phone_detect.xsf`) | name contains `toip` or `voice` | Voice VLAN. One per switch; the first match is used. |
| `AP_MGMT_VLAN_PATTERN` (`ap_detect.py`) | name contains `ap_mgmt` | Untagged AP management VLAN. One per switch. |
| `WIFI_VLAN_PATTERN` (`ap_detect.py`) | name contains `wifi` or `eduroam` | All the tagged WiFi VLANs. |
| `AP_TEXT_MARKERS` (`ap_detect.py`) | `Cisco AP Software` | LLDP text that identifies an AP reported as `BRIDGE`. Add your vendors' strings. |
| `NAC_USES_FDB_MAC_TRACKING` (`ap_detect.py`) | `True` | Removes FDB mac-tracking from AP ports while the AP is connected, and restores it when the AP leaves. See the note below. |

**Why the FDB mac-tracking step exists.** In the original deployment, the customer used the
EXOS FDB mac-tracking trap to trigger **FortiNAC** authorization: every new MAC on an access
port sent a trap, and FortiNAC then authorized that device. That model assumes one device
per access port. Behind an AP, though, the MACs of all its WiFi clients appear on the same
port, and each one would send a trap and an authorization request. For that reason the
script removes mac-tracking from the port while an AP is connected. If your NAC isn't
triggered by FDB mac-tracking (you use 802.1X, another trigger, or no NAC at all), set
`NAC_USES_FDB_MAC_TRACKING = False`.

All matching is case-insensitive. Check your patterns against `show vlan` before
deploying. A pattern that is too broad will add unwanted VLANs to the port.

## Requirements

- EXOS / Switch Engine **32.2 or later** for the Python scripts (native Python 3.8), with
  `configure security python on`. The `.xsf` needs no Python.
- The `.py` files together in `/usr/local/cfg` on the switch. The scripts import
  `upm_mac_guard`, so it must sit next to them.
- For phones, once per switch:
  ```
  configure diffserv examination code-point 46 qosprofile qp8
  configure diffserv examination code-point 32 qosprofile qp8
  ```

## Deploy

Python scripts are called from a one-line UPM profile. In Python the `$EVENT.*` values must
be passed as arguments on the `load script` line:

```
create upm profile AP_DETECT_PY
load script ap_detect.py connect $EVENT.DEVICE $EVENT.USER_PORT $EVENT.DEVICE_MAC
.
create upm profile AP_DETECT_PY_REMOVE
load script ap_detect.py disconnect $EVENT.DEVICE $EVENT.USER_PORT $EVENT.DEVICE_MAC
.
configure upm event device-detect profile "AP_DETECT_PY" ports <ap_ports>
configure upm event device-undetect profile "AP_DETECT_PY_REMOVE" ports <ap_ports>

create upm profile PHONE_DETECT_PY
load script phone_detect.py connect $EVENT.DEVICE $EVENT.USER_PORT $EVENT.DEVICE_MAC $EVENT.DEVICE_POWER
.
create upm profile PHONE_DETECT_PY_REMOVE
load script phone_detect.py disconnect $EVENT.DEVICE $EVENT.USER_PORT $EVENT.DEVICE_MAC $EVENT.DEVICE_POWER
.
configure upm event device-detect profile "PHONE_DETECT_PY" ports <access_ports>
configure upm event device-undetect profile "PHONE_DETECT_PY_REMOVE" ports <access_ports>
```

With the `.xsf` version, the profiles call `load script phone_detect.xsf connect` and
`load script phone_detect.xsf disconnect`. The `.xsf` reads `$(EVENT.*)` directly.

Test the logic by hand before binding it to UPM events:

```
run script ap_detect.py connect WLAN_ACCESS_PT 1:1 00:11:22:33:44:55
run script ap_detect.py disconnect WLAN_ACCESS_PT 1:1 00:11:22:33:44:55
show port 1:1 vlan
show log | include AP_
```

Every script writes `create log message` entries (`AP_Detected_on_…`,
`Voice_Undetect_Ignored_on_…`, errors such as `…no_voice_vlan_found…`) so you can follow
what it did.

## Validation status

This table describes the **original** (pre-cleanup) versions. The published files were only
syntax-checked and exercised locally against a stub of the `exsh` module.

| Script | Status of the original |
|---|---|
| `ap_detect.py` + `upm_mac_guard.py` | Validated end to end in GNS3 (EXOS VM 32.6.3, AP simulated with lldpd): UPM-triggered by `restart port`, VLANs applied and reverted, mac-tracking removed and restored, MAC guard ignoring an undetect while the AP was still present. |
| `phone_detect.xsf` | In production on a physical EXOS 33.7 switch with real IP phones, with a site-specific voice VLAN pattern. The generic pattern published here has not been run. |
| `phone_detect.py` | Not run on its own. It uses the same mechanism and guard module as the validated `ap_detect.py`, and the same command sequence as the production `.xsf`. |

The generic default VLAN patterns (`toip|voice`, `ap_mgmt`, `wifi|eduroam`) are new. Check
them against your own VLAN names.

Known quirks:
- Some phones report `$EVENT.DEVICE_POWER` as `0`. That single `inline-power` command then
  fails, and the rest of the script still runs (EXOS scripts ignore errors by default).
- An AP simulated with lldpd in GNS3 is classified as `ROUTER`, not `BRIDGE`, even when it
  advertises the Bridge capability. For that reason `ap_detect.py` treats `ROUTER` like
  `BRIDGE` (text marker still required). Real APs showed up as `BRIDGE`.

## License

MIT (scripts) and CC BY 4.0 (this README), as in [`../extreme-gns3-skills/LICENSE`](../extreme-gns3-skills/LICENSE).
Community contribution, not an official Extreme Networks product.
