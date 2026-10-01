# Test results — edge guard (EXOS-VM 32.6.3.126, 2026-10-01)

**Test bed** (GNS3 lab with EXOS-VM):
- **Switch A**, the protected one, with **STP disabled**.
- **Switch B**, on port 4 of A, generating the frames: STP in 802.1D/802.1W/MSTP modes, ELRP and EDP.
- **IGMP and LLDP tests:** a second pod with two Linux hosts (multicast sender and receiver of 239.0.0.1, and a frame generator) in a VLAN with IGMP snooping.
- **SLPP test:** a temporary GNS3 project with EXOS-VM ↔ Fabric Engine 9.4 (VOSS).

## 1. BPDU detection with STP disabled on the protected switch

| ACL on port 4 | Is the BPDU logged (`Kern.Info`)? |
|---|---|
| `permit ; count ; log` | Yes |
| `permit ; count ; log ; mirror-cpu` | Yes |
| `deny ; count ; log ; mirror-cpu` | Yes (the one used) |
| `deny ; count ; log` | Yes |

## 2. Signatures captured with `log-raw`

| Frame | Header after the length field (hex) | Meaning |
|---|---|---|
| 802.1D BPDU | `42420300 00000000` | LLC 42/42/03 · Protocol ID 0000 · version 00 · type 00 (config) |
| 802.1W BPDU | `42420300 0002023e` | version 02 · type 02 (RST) |
| MSTP BPDU | `42420300 0003023e` | version 03 · type 02 |
| ELRP | `aaaa0300 e02b00bb 01000028 …` | LLC/SNAP · OUI 00:e0:2b (Extreme) · SNAP type 0x00BB (same as EDP) · source `0e:<MAC>` · destination `0d:<MAC>` |

`destination-sap 0x42 ; source-sap 0x42` matched in all three STP modes: 6 matches every 8 s in each mode.

## 3. ACL conditions tested

| Condition | Result on EXOS-VM |
|---|---|
| `ethernet-destination-address 01:80:c2:00:00:00` (BPDU) | Matches |
| `destination-sap 0x42 ; source-sap 0x42` | Matches (STP/RSTP/MSTP) |
| `ethernet-destination-address elrp-dst-mac` | **Does not match**. The switch resolves it to `01:<own MAC>` (rebuilt bit by bit with masks); real ELRP goes to `0d:<sender MAC>` |
| `ethernet-source-address elrpsrc-mac` | Error: «not a valid mac address» |
| `destination-sap 0xaa ; source-sap 0xaa` | Matches ELRP/EDP and injected PVST+ and VTP frames (10 out of 10) |
| `snap-type 0x00bb` / `0x010b` / `0x2003` (also in decimal) | **0 matches** with the same frames. Accepted without error |
| `if match any { destination-sap 0x42 ; }` | Matches |
| `if match any { destination-sap 0x42 ; ethernet-type 0x8102 ; }` | **0 matches** (passes `check policy`) |
| `if match any { destination-sap 0x42 ; snap-type 0x010b ; }` | **0 matches** (passes `check policy`) |

## 4. Full chain `.pol` → EMS → UPM → `.py`

| Signal | Entry triggered | `show upm history` | Log |
|---|---|---|---|
| BPDU (B in MSTP) | `edge_stp` | Pass | `edge_guard.py: edge_stp on port 4, port disabled` |
| ELRP (B without STP) | `edge_snap` (on the VM, because `snap-type` does not work) | Pass | `edge_guard.py: edge_snap on port 4, port disabled` |

- **Reaction time:** about 0.15-0.3 s between the port's `link up` and `link down`.
- **Earlier versions tested, also with Pass:**
  - dynamic ACL (`create access-list`) instead of `.pol`;
  - profile with an inline `disable port` instead of the `.py`.

(The log messages in this file are shown in English, as the script now writes them. During the tests
the script wrote the same messages in Spanish.)

## 5. IGMP snooping with MAC ACLs (User Guide 33.1.1 warning, p. 800-801)

**Method:** the receiver (port 11 of switch A) joins a new group for 4 s while the sender captures IGMP with `tcpdump`. With snooping working, that join must not reach the sender, which is not a router port.

| Case | Join flooded to the sender? | `show igmp group` table | Stream to the receiver |
|---|---|---|---|
| No ACL (baseline) | No | 239.0.0.1 only on the receiver's port | Yes |
| MAC ACL on an unused port | No | Same | Yes |
| MAC ACL on the receiver's port | No | Same | Yes |
| MAC-free ACL (SAP 0x42) on the receiver's port | No | Same | Yes |
| MAC ACL on the sender's port (other switch) | No | Sender cache entry present | Yes |

**Conclusion:** on EXOS-VM the warning does not reproduce. It still has to be checked on hardware; the package's policy uses no MAC conditions.

## 6. SLPP against a real Fabric Engine 9.4 (temporary GNS3 project: EXOS-VM Port1 ↔ VOSS 1/1)

- **VOSS:**
  - `slpp enable`, `slpp vid 1`, `vlan members add 1 1/1`. The last one is needed: on 9.4 ports are not in any VLAN by default.
  - It transmits every 500 ms.
- **Captured frame:** source `0c:97:9d:87:00:00`, destination `0d:97:9d:87:00:00` (`0d:` + sender MAC, the same scheme as ELRP), ethertype `0x8102`, 64 bytes, VLAN 1. Exact 0.50 s spacing. No other traffic with that ethertype.
- **`edge_slpp`** (`ethernet-type 0x8102`): matches.
- **UPM chain with `.pol` + `.py`:** `Pass`, with the message `edge_guard.py: edge_slpp on port 1, port disabled`.
- **`mirror-cpu`** (counter vs `Kern.Info` lines in about 10 s):

| Actions | Counter | `Kern.Info` lines |
|---|---|---|
| `permit ; count ; log` | 29 | 31 |
| `permit ; count ; log ; mirror-cpu` | 29 | 29 |
| `deny ; count ; log` | 29 | 30 |
| `deny ; count ; log ; mirror-cpu` | 29 | 30 |

  On EXOS-VM `mirror-cpu` makes no difference (everything goes through the CPU), and `deny` + `count` works on ingress.
- **Native SLPP Guard** (`enable slpp guard ports 1`):
  - disables the port on receiving SLPP, logging `<Warn:SLPP.DsblPortRxPDU>`;
  - `show slpp guard ports 1` → state `Disabled`, timeout 60;
  - it re-enables the port automatically when the timeout expires, and disables it again 63 s later while SLPP keeps arriving;
  - timeout syntax: `configure slpp guard ports <p> recovery-timeout <10-65535 | none>`.
- **Removing a `.pol` policy from a port:** `unconfigure access-list <policy> ingress`. `configure access-list delete …` does not remove it.

## 7. LLDP and LACP are not affected by the SAP rules

Switch B as sender (EDP and STP disabled to isolate the test) and, on switch A, the SAP rules
evaluated **before** the protocol's own rule.

| Traffic (about 20-70 s) | `destination-sap 0x42 ; source-sap 0x42` | `destination-sap 0xaa ; source-sap 0xaa` | Protocol's own rule |
|---|---|---|---|
| LLDP (`-> 01:80:c2:00:00:0e`, ethertype 0x88CC, every 30 s) | 0 | 0 | `ethernet-type 0x88cc` = 2 |
| LACP with short timeout (`-> 01:80:c2:00:00:02`, ethertype 0x8809, 1/s) | 0 | 0 | `ethernet-type 0x8809` = 24 |

## 8. Protocols affected by the SAP rules (public sources)

SAP conditions are only evaluated on 802.3 frames with LLC. Ethernet II frames are never affected;
checked with LLDP and LACP (§7).

| Rule | Protocol | Identification | Checked in the lab | Source |
|---|---|---|---|---|
| SAP 0x42 | IEEE STP / RSTP / MSTP | LLC `42 42 03` | Yes (all three modes) | IEEE LLC registry (SAP 0x42 = Bridge Spanning Tree Protocol) |
| SAP 0xAA | Extreme EDP (+ ELRP, EAPS, ESRP as TLVs) | SNAP 00:E0:2B / 0x00BB, destination 00:E0:2B:00:00:00 (ELRP: `0d:<MAC>`) | Yes (real ELRP and EDP) | Wireshark EDP; `lldpd` source (`edp.h`) |
| SAP 0xAA | Cisco PVST+/RPVST+ | SNAP 00:00:0C / 0x010B, destination 01:00:0C:CC:CC:CD | Yes (injected frames) | Cisco Best Practices Catalyst 6500/4500 |
| SAP 0xAA | Cisco VTP | SNAP 00:00:0C / 0x2003 | Yes (injected frames) | same |
| SAP 0xAA | Cisco CDP | SNAP 00:00:0C / 0x2000 | Yes (injected frames, §10) | same; `lldpd` (`cdp.h`) |
| SAP 0xAA | Cisco DTP / PAgP / UDLD | SNAP 00:00:0C / 0x2004 / 0x0104 / 0x0111 | No (by design: it is SNAP) | same |
| SAP 0xAA | Foundry/Brocade FDP | SNAP 00:E0:52 / 0x2000, destination 01:E0:52:CC:CC:CC | No (by design) | `lldpd` (`cdp.h`) |
| SAP 0xAA | Nortel/Avaya SONMP (NDP) | SNAP 00:00:81 / 0x01A2 (hello), 0x01A1, destination 01:00:81:00:01:00 | No (by design) | `lldpd` (`sonmp.h`) |
| SAP 0xAA | AppleTalk phase 2, AARP, IPX Ethernet_SNAP (legacy) | SNAP (08:00:07 / 0x809B, 00:00:00 / 0x80F3, 0x8137) | No | Historical use of SNAP |
| — | LLDP (0x88CC), LACP (0x8809), SLPP (0x8102), IP, ARP, 802.1X (0x888E) | Ethernet II | LLDP/LACP/SLPP: yes, **not affected** by SAP | — |

Sources:
- IEEE LLC registry: <https://standards.ieee.org/products-programs/regauth/llc/public/>
- `lldpd`: <https://github.com/lldpd/lldpd/tree/master/src/daemon/protocols>
- Cisco: <https://www.cisco.com/c/en/us/support/docs/switches/catalyst-6500-series-switches/24330-185.html>
- Wireshark EDP: <https://wiki.wireshark.org/EDP>

The TLV marker `0x99` defined in `lldpd/edp.h` matches the ELRP capture in §2 (`… 99 0d 00 14 …`):
ELRP is the TLV of type `0x0D` inside EDP.

## 9. Pending on real hardware

1. **`snap-type`:** not verified on any platform (accepted but never matches on the VM). Until it is
   checked, `edge_guard-hw.pol` and the CDP exit valve (`allow_cdp`) are experimental.
2. **`mirror-cpu`:** check that without it fast-path traffic is not logged, as the guide states.
3. **Repeat the IGMP snooping test** with MAC ACLs.

## 10. Discarded alternative: LLDP check in the script (phones/APs and CDP)

Purpose: avoid shutting down ports with Cisco phones or APs because of their CDP. A script version
skipped the shutdown when the trigger was `edge_snap` towards `01:00:0c:cc:cc:cc` **and** LLDP showed
on that port a neighbour with `Telephone` or `WLAN Access Point` capability (retrying for ~8 s).
**It is not included in the package** because it depends on protocol timing (see below) and is
spoofable.

Test: the Linux host generated LLDP «telephone» frames (capabilities `Bridge, Telephone`), CDP
(SNAP 0x2000) and BPDUs with raw sockets. EXOS shows the capabilities as
`Enabled Capabilities: "Bridge, Telephone"`.

| Case | Expected | Result |
|---|---|---|
| A. Phone LLDP + CDP | Port stays up, exemption logged | OK: «edge_snap on port 11 ignored, LLDP sees phone/AP SEP-PRUEBA [Bridge, Telephone]» |
| B. Phone LLDP + BPDU | Port disabled (`edge_stp` has no exemption) | OK |
| C. No LLDP + CDP | Port disabled after the retry window | OK |
| D. CDP, then LLDP 3 s later | Exemption after retry | OK in a clean rerun. The first attempt failed because the LLDP sender started late (test harness latency), and the profile run did not show the retry loop being exercised |

**Why it was discarded:** after link-up the LLDP neighbour took **~7 s** to be learned (phone sending
every 5 s). The outcome therefore depends on the relative timing of CDP and LLDP, on the retry window
and on the EMS→UPM latency, i.e. on race conditions. Real phones may behave differently (LLDP-MED fast
start), but that would have to be checked device by device. The recommended alternative is the
`allow_cdp` exit valve in the ACL (README §4.1), pending hardware verification of `snap-type`.
