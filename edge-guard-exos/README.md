# edge-guard — shut an access port down when a switch shows up behind it (EXOS / Switch Engine)

Self-contained package: it can be copied or moved anywhere. Contents:

| File | What it is |
|---|---|
| `edge_guard.pol` | **Reference** ACL policy: one entry per protocol, using only conditions verified with real traffic. It also contains an optional, commented-out exit valve for Cisco CDP (§4.1). |
| `edge_guard-hw.pol` | **Experimental** ACL policy: specific SNAP-type signatures instead of the generic SNAP rule. Do not use it until `snap-type` has been verified on the target hardware. |
| `edge_guard.py` | Python script run by the UPM profile: disables the port and writes a log message. |
| `install.txt` | Configuration snippet: UPM profile, EMS filter, log target and policy binding. |
| `uninstall.txt` | How to remove it. |
| `RESULTS.md` | Test evidence (EXOS-VM 32.6.3.126 and Fabric Engine 9.4, 2026-10-01). |

## 0. Summary

**Goal:** draw a **hard boundary** between two kinds of port:
- **infrastructure** ports, loop-free by design, where redundancy comes from LAG/MLAG, stacking or
  clustering;
- **access (edge)** ports, where nothing that could come from a switch is accepted. If it shows up,
  the port is disabled, because of the risk of forming a loop.

It needs neither STP nor `link-type edge`.

**Verification status** (EXOS-VM 32.6.3.126, 2026-10-01):

| Verified with real traffic | Not verified |
|---|---|
| `edge_stp` (SAP 0x42) with STP, RSTP and MSTP | `snap-type`: accepted without error but never matches on EXOS-VM; no proof on any platform. This affects `edge_guard-hw.pol` and the CDP exit valve (§4.1) |
| `edge_snap` (SAP 0xAA) with real ELRP/EDP and injected PVST+/VTP | `mirror-cpu` on hardware (no effect on EXOS-VM) |
| `edge_slpp` (ethertype 0x8102) against a real Fabric Engine 9.4 | IGMP snooping with MAC ACLs on hardware |
| Full chain `.pol` → EMS → UPM → `.py` → `disable port` (Pass, ~0.2 s) | |
| LLDP and LACP are **not** affected by the SAP rules | |
| `deny` + `count` on ingress; `unconfigure access-list <pol> ingress` to remove the policy | |
| IGMP snooping unaffected on EXOS-VM by MAC and SAP ACLs | |

**What to use:** `edge_guard.pol`, the reference variant, in which every active entry is verified.
`edge_guard-hw.pol` is experimental.

**Side effect to accept:** `edge_snap` blocks every LLC/SNAP frame. That covers every proprietary
switch protocol (Cisco, Extreme, Foundry, Nortel), but also the **CDP sent by Cisco IP phones and
APs** (and by ESXi hosts with CDP enabled). See §3.1 and the exit valve in §4.1.

## 1. What it does and why

On an access port there should only be end devices. If a frame that **only a switch sends** arrives
on it (BPDU, PVST+, VTP, DTP, PAgP, UDLD, EDP/ELRP, SLPP), a switch is connected or a loop is forming,
and the port is disabled.

Compared with the native **BPDU guard** (`link-type edge` + `edge-safeguard` + `bpdu-restrict`), it
needs neither **STP** running nor the ports configured as **edge**, with everything that implies and
the risk of interfering elsewhere. It is an independent, per-port switch that also covers protocols
from several vendors and logs which protocol triggered it.

## 2. Concept

```
switch frame ──► ACL edge_guard (entry edge_<protocol>: deny ; count ; log ; mirror-cpu)
arrives on port         │   (the frame goes to the CPU and is not forwarded)
                        ▼
      EMS  <Info:Kern.Info> "... packet from 1:<port> (vlanId=N) matches rule edge_<protocol>: ..."
                        │   EMS filter edge_f: kern.info match string "matches rule edge_"
                        ▼
      UPM log target edge_guard ──► UPM profile edge_guard
                        │   regsub → p = <port>, r = edge_<protocol>
                        ▼
      load script edge_guard.py $p $r ──► disable port <p>
                                       └► create log message "edge_guard.py: <rule> on port <p>, port disabled"
```

- **One entry per protocol:** EXOS always evaluates ACLs as «match all». `if match any` with
  different fields passes `check policy` but matches nothing. Several entries act as an OR, and the
  entry name in the log tells which protocol was detected.
- **No MAC conditions:** the policy uses LLC SAP, SNAP type and ethertype. The signature does not
  depend on device MACs, and it sidesteps the User Guide warning about MAC ACLs and IGMP snooping
  (§8).
- **`deny`:** the frame is not propagated while the profile disables the port (~0.2 s).

## 3. Signatures (no MAC) and verification status

| Entry | Condition | Protocol | Verified with traffic? | Source |
|---|---|---|---|---|
| `edge_stp` | `destination-sap 0x42 ; source-sap 0x42` | IEEE STP, RSTP and MSTP. LLC `42 42 03`, Protocol ID `0000`; the version (00/02/03) and type (00 config, 80 TCN, 02 RST/MST) are inside the BPDU | **Yes** (EXOS-VM, all three modes) | IEEE 802.1D / 802.1Q |
| `edge_slpp` | `ethernet-type 0x8102` | VOSS/Fabric Engine SLPP (destination `0d:<sender MAC>`, 64 bytes, every 500 ms) | **Yes** (EXOS-VM against Fabric Engine 9.4) | real capture |
| `edge_snap` | `destination-sap 0xaa ; source-sap 0xaa` | Any LLC/SNAP frame: Extreme EDP/ELRP and Cisco PVST+/VTP/DTP/PAgP/UDLD/CDP | **Yes** (EXOS-VM: real ELRP/EDP and injected PVST+/VTP) | real capture |
| `edge_pvst` | `snap-type 0x010b` | Cisco PVST+/RPVST+ (destination 01:00:0C:CC:CC:CD) | **No** | Cisco (below) |
| `edge_vtp` | `snap-type 0x2003` | Cisco VTP (destination 01:00:0C:CC:CC:CC) | **No** | same |
| `edge_dtp` | `snap-type 0x2004` | Cisco DTP | **No** | same |
| `edge_pagp` | `snap-type 0x0104` | Cisco PAgP | **No** | same |
| `edge_udld` | `snap-type 0x0111` | Cisco UDLD | **No** | same |
| `edge_edp` | `snap-type 0x00bb` | Extreme **EDP / ELRP / EAPS / ESRP**: ELRP, EAPS and ESRP travel as TLVs inside EDP (LLC/SNAP `aa aa 03 00 e0 2b 00 bb`) | **No** | Wireshark (below) and `log-raw` capture |
| `allow_cdp` (commented out) | `snap-type 0x2000` → `permit` | Cisco CDP exit valve (§4.1) | **No** | Cisco; `lldpd` |

**Why the `snap-type` entries are not verified:** on EXOS-VM the condition is accepted without error
but never matches. It gave 0 matches with real ELRP/EDP and with injected PVST+ and VTP frames, while
the SAP 0xAA rule counted those same frames. There is no proof that it works on any other platform.
The User Guide documents it as a valid ingress condition, but that does not guarantee it works.

Sources:
- Cisco control-plane protocol table: <https://www.cisco.com/c/en/us/support/docs/switches/catalyst-6500-series-switches/24330-185.html>
- EDP in Wireshark (OUI 0x00E02B, type 0x00BB, carries EAPS and ESRP): <https://wiki.wireshark.org/EDP>
- Field `edp.elrp` (ELRP as an EDP TLV): <https://www.wireshark.org/docs/dfref/e/edp.html>

`destination-sap`, `source-sap` and `snap-type` are **ingress-only** conditions (Switch Engine 33.1.1
User Guide, table «ACL Match Conditions»).

### 3.1 Protocols affected by the SAP rules (`edge_stp` and `edge_snap`)

`destination-sap`/`source-sap` are only evaluated on **802.3 frames with an LLC header** (type/length
field below 0x0600). **Ethernet II** frames (which carry an ethertype) are never affected.

**Caught by `edge_stp`** (SAP 0x42, «Bridge Spanning Tree Protocol» in the IEEE LLC registry):
- IEEE 802.1D STP, 802.1w RSTP and 802.1s/Q MSTP (verified), destination 01:80:C2:00:00:00.
- The IEEE-format copy that Cisco PVST+ sends on the native VLAN uses the same format.

**Caught by `edge_snap`** (SAP 0xAA, i.e. every LLC/SNAP frame):

| Protocol | OUI / SNAP type | Destination MAC | Who sends it |
|---|---|---|---|
| Extreme EDP, and inside it ELRP, EAPS and ESRP | 00:E0:2B / 0x00BB | 00:E0:2B:00:00:00 (EDP), `0d:<MAC>` (ELRP) | Extreme switches. EDP is enabled by default on EXOS (verified) |
| Cisco CDP | 00:00:0C / 0x2000 | 01:00:0C:CC:CC:CC | Cisco switches and routers, **but also Cisco IP phones and APs**, and ESXi hosts with CDP in «both» mode |
| Cisco VTP / DTP / PAgP / UDLD | 00:00:0C / 0x2003 / 0x2004 / 0x0104 / 0x0111 | 01:00:0C:CC:CC:CC | Cisco switches |
| Cisco PVST+ / Rapid-PVST+ | 00:00:0C / 0x010B | 01:00:0C:CC:CC:CD | Cisco switches (verified with injected frames) |
| Foundry/Brocade/Ruckus FDP | 00:E0:52 / 0x2000 | 01:E0:52:CC:CC:CC | Foundry/Brocade switches |
| Nortel/Avaya SONMP (NDP) | 00:00:81 / 0x01A2 (hello), 0x01A1 (flatnet) | 01:00:81:00:01:00 | Nortel/Avaya switches (ERS/BOSS) and some Avaya devices |
| Legacy protocols over SNAP on Ethernet | e.g. AppleTalk phase 2 (08:00:07 / 0x809B), AARP (00:00:00 / 0x80F3), IPX «Ethernet_SNAP» (0x8137) | — | Very old hosts; practically extinct today |
| `lldpd` on Linux with CDP/FDP/EDP/SONMP enabled | as above | as above | Linux servers whose `lldpd` is configured to send those protocols (not the default) |

**Not affected** (verified on EXOS-VM, with the SAP rule evaluated before the protocol's own rule):
- **LLDP** (Ethernet II, ethertype 0x88CC, destination 01:80:C2:00:00:0E): 0 SAP matches.
- **LACP** (Ethernet II, ethertype 0x8809, destination 01:80:C2:00:00:02): 0 SAP matches with 24
  LACPDUs. Server LAGs are not affected.
- **SLPP** (Ethernet II, ethertype 0x8102): only `edge_slpp` catches it.

Also unaffected by design, since they are Ethernet II: IPv4/IPv6, ARP, 802.1X/EAPOL (0x888E),
MVRP/MMRP, PTP and LLDP-MED. Neither are LLC frames with other SAPs, such as NetBIOS (0xF0),
IS-IS (0xFE) or SNA (0x04).

**Design reading:** with the hard-boundary goal, blocking all LLC/SNAP is consistent: it covers every
proprietary switch protocol from Cisco, Extreme, Foundry and Nortel. A Cisco Catalyst behind an access
port may well advertise itself in LLDP only as a bridge, but sooner or later it betrays itself with
BPDU, PVST+, VTP, DTP or CDP. The only relevant side effect is the **CDP of Cisco phones and APs**
(and of ESXi if enabled): see §4.1.

Sources:
- IEEE LLC registry: <https://standards.ieee.org/products-programs/regauth/llc/public/>
- CDP/FDP/EDP/SONMP constants in the `lldpd` source: <https://github.com/lldpd/lldpd/tree/master/src/daemon/protocols>
- Cisco Best Practices (link in §3).

## 4. Which variant to use

- **`edge_guard.pol`, the reference variant.** Its active entries use only conditions verified with
  traffic: `edge_stp`, `edge_slpp` and `edge_snap`.
- **`edge_guard-hw.pol`, experimental.** It replaces `edge_snap` with the specific `snap-type` entries,
  which only switches send and which do not catch CDP. **Do not use it without first running the §6
  check on the real switch.** If `snap-type` does not match on that platform, this variant silently
  lets PVST+, VTP, DTP, PAgP, UDLD and EDP/ELRP through.

### 4.1 Exit valve for Cisco IP phones and APs (CDP) — not verified

`edge_guard.pol` contains a **commented-out** entry, `allow_cdp` (`snap-type 0x2000` → `permit`),
placed before `edge_snap`:
- **When to enable it:** only if blocking CDP causes problems with Cisco IP telephony or Cisco access
  points on those ports. Without it, a Cisco phone or AP sending CDP disables the port.
- **What it does:** it lets CDP through, while VTP, DTP, PAgP, UDLD and PVST+ keep being caught by
  `edge_snap`. Caveat: `snap-type` does not check the OUI, so Foundry FDP (also type 0x2000) would pass
  too.
- **It must be verified on the target hardware first.** We could not verify it: on EXOS-VM `snap-type`
  never matches. If it does not match on the hardware either, the valve does nothing and the phone or
  AP will still shut the port down.
- **Why not a MAC-based permit:** `ethernet-destination-address 01:00:0c:cc:cc:cc` would also let VTP,
  DTP, PAgP and UDLD through (same destination MAC), breaking the hard boundary.
- **Alternative considered and discarded: checking LLDP in the script.** The idea was to skip the
  shutdown when LLDP shows a neighbour advertising `Telephone` or `WLAN Access Point` on that port. It
  works in the lab (RESULTS §10), but it depends on protocol timing: at link-up, CDP can arrive before
  the LLDP neighbour is learned (~7 s in the lab), so the result depends on retry windows and EMS→UPM
  latency. It is also spoofable by any device advertising itself as a phone. It is documented as a
  possibility but **not included in the script**.

## 5. Installation

Requirements: EXOS/Switch Engine with Python scripting (≥ 32.2) and UPM, which depends on the
platform licence (see the Licensing Guide). Tested on EXOS-VM 32.6.3.126.

1. **Copy the files to the switch flash**, either:
   - via TFTP/SCP: `tftp get <server> edge_guard.pol` (add `vr VR-Mgmt` or another VR if needed; or
     `scp2 …`), and the same for `edge_guard.py`. If you use `edge_guard-hw.pol`, save it on the switch
     as `edge_guard.pol`;
   - or on the switch itself: `edit policy edge_guard.pol` and `edit script edge_guard.py` (vi editor:
     `i`, paste, `Esc`, `:wq`).
2. `check policy edge_guard` → it must answer `Policy file check successful.`
3. Paste `install.txt`, replacing `<access-ports>`.
4. Verify (§6) and `save`.

**If the policy is edited later,** run `refresh policy edge_guard`; otherwise the previous version
stays applied.

## 6. Verification

- `show access-list port <p> ingress`: the `edge_*` entries are listed.
- `show access-list counter`: one counter per entry.
- `show upm history`: `Log-Message(edge_f)  edge_guard  Pass`. `show upm history exec-id <n>` shows
  the executed script with its variables filled in; it is the best debugging tool.
- `show log match edge_guard`: `System.userComment … edge_guard.py: edge_stp on port 4, port disabled`.
- `show ports <p> no-refresh`: the port shows `D`.
- **`snap-type` check** (mandatory before using `edge_guard-hw.pol` or enabling `allow_cdp`): on a test
  port, apply the policy with counters only (UPM target not enabled) and connect an Extreme switch (EDP
  is on by default) or a Cisco device, or inject a PVST+/VTP/CDP frame. The counter of
  `edge_edp`/`edge_pvst`/`edge_vtp` (or the `allow_cdp` permit) must increase. If it stays at 0,
  `snap-type` does not work on that platform: use `edge_guard.pol` without the exit valve.

## 7. Recovering a port

By hand: `enable port <p>`. If the switch is still connected, the port goes down again immediately.
Automatic re-enabling could be built with a UPM timer; it is not included or tested.

## 8. Limitations and known pitfalls

- **`snap-type` on EXOS-VM:** never matches (§3).
- **`if match any` with different fields** does not work in ACLs; use one entry per protocol.
- **`elrp-dst-mac` is useless:** the switch resolves it to `01:<own MAC>`, while ELRP is sent to
  `0d:<sender MAC>`. `elrpsrc-mac` is rejected by the switch. ELRP is therefore detected by its Extreme
  SNAP encapsulation.
- **ACL `log` and the CPU:** `log` only records packets that reach the CPU. That is why `mirror-cpu` is
  added: the User Guide says it is needed on hardware for fast-path traffic. On EXOS-VM it makes no
  difference: every frame was logged with and without it, including SLPP, which EXOS does not trap
  natively. Not verified on hardware.
- **`deny` with `count`:** they work together on ingress (verified). The User Guide restriction is for
  egress only, and only on some platforms. `packet-count <name>` is an equivalent modifier.
- **Removing the policy:** `unconfigure access-list edge_guard ingress`. `configure access-list
  delete …` only works for dynamic ACLs.
- **IGMP snooping:** the User Guide 33.1.1 (p. 800-801) warns that an ACL with a MAC condition breaks
  IGMP snooping. On EXOS-VM **it does not reproduce**, but it is not verified on hardware. This policy
  uses no MAC conditions.
- **Only the port and the rule are passed to the script.** Passing the whole `${EVENT.LOG_PARAM_0}`
  breaks the CLI (`%% Invalid input`) because of the parentheses in the text.
- **Log messages from a profile:** the command is `create log message`; `create log entry` does not
  exist. A variable inside quotes is not expanded; without quotes, it is.
- **Dependencies:** it relies on the CPU, EMS and the script. If something fails, there is no
  protection and `show upm history` shows `Fail`. It is worth monitoring, for example with a log trap.

**Native alternative for SLPP:** if only SLPP matters, the native SLPP Guard is simpler:
`enable slpp guard ports <p>`. Verified: it logs `<Warn:SLPP.DsblPortRxPDU> Disabled Port 1 by SLPP
Guard due to the Reception of an SLPP PDU`, `show slpp guard ports <p>` shows the state, and the port
is re-enabled automatically when the timeout expires.

## 9. Comparison

| | This edge guard | Native BPDU guard | Native SLPP Guard | Meter with `disable-port` |
|---|---|---|---|---|
| Needs STP / edge | No | Yes / Yes | No | No |
| Protocols | All of §3 | IEEE BPDU only | SLPP only (configurable ethertype) | Any, but by **rate** |
| Reacts to | First frame (~0.2 s) | First frame | First frame | Exceeding N pps (not a single BPDU) |
| Recovery | Manual (or a custom UPM timer) | `recovery-timeout` 60-600 s | `configure slpp guard ports <p> recovery-timeout <10-65535 \| none>` (default 60 s; verified) | `clear access-list meter … out-of-profile` + `enable port` |
| Dependencies | CPU + EMS + UPM + script | STP | None (verified without STP against VOSS 9.4) | Hardware with meters (not on EXOS-VM) |
