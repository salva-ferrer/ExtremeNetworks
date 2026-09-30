# Validation log

Evidence behind the "validated" claims in this pack. Figures are functional observations,
not performance measurements.

## Environment
- GNS3 server 2.2.45 (API v2) on a Linux x86_64 host with KVM, one `local` compute.
- Client: Linux, Python 3 (standard library), `curl`.

## Live test: Fabric Engine from GitHub (2026-09-30)

Throwaway project, deleted afterwards. Steps, all through the API from the client:

| Step | Result |
|---|---|
| Download `FEGNS3.9.4.0.0.qcow2` from the URL in `VOSSGNS3-V9.X.gns3a` | md5 `341aef71e2dbb976e6fa6369b363789e` matches the appliance file |
| `gns3a_to_template.py VOSSGNS3-V9.X.gns3a --version 9.4.0.0 --upload-image … --post <GNS3_HOST>` | image uploaded via `POST /v2/compute/qemu/images/…`, template "FabricEngine VM 9.4.0.0" created |
| 2 × Fabric Engine + 1 × Switch Engine (EXOS VM 32.6.3.126) from templates | nodes created with 33 (VOSS) and 13 (EXOS) ports, names from the template |
| Links FE1 1/1↔FE2 1/1, FE2 1/24↔EXOS Port1 | Fabric Engine boots to `Login:` in about 2-3 min; 1/1 goes Auto-Sense `NNI-ISIS-UP` (SPBM adjacency) with no configuration; EXOS sees FE2 `1/24` by LLDP; FE2 detects EXOS as a Fabric Attach proxy |
| First Fabric Engine login `rwa/rwa` | forced password change ("initial attempt using the default password") |
| `save config` | `Save config to file /intflash/config.cfg successful` |
| Adapters 25 / 29 / 32 (named `1/25/1`, `1/26/1`, `1/26/4` by the appliance) | 25 → VOSS port 1/25 (40G, up, LLDP), 29 → 1/26 (up, LLDP), 32 → no link. Without channelization only adapters 25 and 29 are usable |
| Node options without `-cpu host` | Fabric Engine 9.4.0.0 boots normally. Switch Engine 32.6.3.126 **stops in its bootloader menu** (`~>` prompt, "c) continue with boot process") |
| Real QEMU command lines (`command_line` in the node API) | GNS3 adds `-enable-kvm` to every QEMU node by itself; the appliance's own `-enable-kvm` is rewritten to `-machine accel=kvm` (redundant, no extra effect) |
| EXOS `save` then `answer y` with `gns3_console.py` | `Configuration saved to primary.cfg successfully` |
| Fresh EXOS VM: login during `(pending-AAA)` | `Failed to connect to authentication service ... Login incorrect`; works once "AAA ... is now available" is printed |
| EXOS first-boot security wizard | quit with `answer q --wizard`; defaults kept |
| `backup_configs.py <GNS3_HOST> <dir> SW1=<port> --save` (separate throwaway EXOS project) | switch saved (prompt loses `*`), 249-line `show configuration` written, with the changes made just before |
| Console line endings | `\r\n` counts as two lines on both EXOS and VOSS consoles (an empty password was sent); `\r` works |

## Live test: simulated devices around Switch Engine (2026-09-30)

Throwaway project, deleted afterwards: EXOS VM 32.6.3.126, a GNS3 `nat` node behind an
`ethernet_switch` for package installs, `alpine:latest` containers with 2-3 interfaces.

| Test | Result |
|---|---|
| FreeRADIUS 3 (`freeradius`, `freeradius-eap`) | fails to start until `certs/bootstrap` creates the TLS certificates (`rlm_eap_tls: Failed initializing SSL context`) |
| EXOS `enable netlogin dot1x` | `Error: No NetLogin VLAN is configured.` until `configure netlogin vlan <vlan>` |
| `wpa_supplicant -D wired`, EAP-MD5, on EXOS port 2 | `EAP state=SUCCESS`, `suppPortStatus=Authorized`; EXOS `show netlogin port 2`: `Yes, Radius 802.1x testuser`; RADIUS `Access-Accept` |
| Same with a wrong password | `EAP state=FAILURE`, `Access-Reject`, EXOS shows `No` |
| FRR (`frr`) OSPF on EXOS port 3 | EXOS `show ospf neighbor`: 2.2.2.2 `FULL`; each side learns the other's /32 loopback; ping between loopbacks OK |
| VLAN subinterface `eth1.20` ↔ EXOS tagged VLAN 20 | ping OK |
| Bond `802.3ad` (2 links) ↔ EXOS `enable sharing ... lacp` | container sees the switch as partner; EXOS stays `Selected`/`Waiting`, aggregator count 0, no traffic |
| Bond `balance-xor` ↔ EXOS static sharing | no traffic; EXOS ports 4-5 link state flapping (`A`/`R`) after container interface changes |
| `wpa_supplicant -f <file>` on Alpine | option not available in that build (prints usage) |

## Validated in earlier lab work (2026)
- Switch Engine 32.6.3.126: 13-port official template and a 25-adapter (24 data ports)
  extension; multi-switch labs with saved configs, `default.xsf`, TFTP, SNMP; `.xos` image
  install on the secondary partition and switching boot image (32.7.2.19 ↔ 32.6.3.126); UPM/Python scripts with Alpine + lldpd endpoints.
- Site Engine (XIQ-SE) 24.2.15.5 as a QEMU VM in GNS3: switch discovery by SNMP, firmware
  repository, FlexViews, MIB Tools, clone/resize/compaction of its disks, 8 GB/2 vCPU and
  16 GB/4 vCPU instances.

## Not validated
- Simulated devices other than those in the table above (BGP, DHCP/DNS, syslog, traffic
  tools, PEAP, MAC-auth, LLDP-MED); any of them against Fabric Engine.
- ExtremeControl and ExtremeAnalytics (no OVA available at the time).
- Fabric Engine beyond the steps above (services, SPBM L2/L3 VSNs, DvR, upgrades).
- GNS3 3.x (API v3).
