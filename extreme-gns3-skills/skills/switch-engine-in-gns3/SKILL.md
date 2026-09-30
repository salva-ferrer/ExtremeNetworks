---
name: switch-engine-in-gns3
description: Use when operating Extreme Switch Engine (ExtremeXOS/EXOS VM) nodes in a GNS3 lab from Claude Code — first boot and login, the security wizard, saving and backing up configs, default.xsf bootstrap behaviour, TFTP/SNMP for Site Engine, installing .xos images, and Python/UPM requirements. For devices around the switch (LLDP endpoints, 802.1X clients, RADIUS, routers) see simulated-devices-in-gns3.
---

# Switch Engine (EXOS VM) in a GNS3 lab

Assumes a running EXOS VM node on `<GNS3_HOST>` (templates: `extreme-switch-templates`;
API and consoles: `gns3-server-api`). Commands go through the node's telnet console with
`gns3_console.py` (path: `../gns3-server-api/scripts/`).

## Validated environment

- EXOS VM **32.6.3.126** (official template, 13 and 25 adapters), GNS3 2.2.45, Linux client.
- Several multi-switch labs (up to 12 switches per project), saved/versioned configs,
  `default.xsf` bootstrap from TFTP, SNMP towards Site Engine, `.xos` installation.
- UPM and Python scripts tested with Alpine + lldpd endpoints (see `simulated-devices-in-gns3`).

## First boot

1. Boot takes about 1 minute. If the node never reaches `login:` and its console shows a
   bootloader settings menu (`~>` prompt, "c) continue with boot process"), the template
   lacks the QEMU option `-cpu host` (see `extreme-switch-templates`). Fix the template or
   node options (node stopped); `c` at that prompt continues the boot once.
2. The first prompt is `(pending-AAA) login:`. **Logins fail until the switch prints
   "Authentication Service (AAA) ... is now available"** (`Failed to connect to
   authentication service ... Login incorrect`). Wait, don't retry in a loop.
3. Login `admin`, empty password. A security wizard follows (MSTP, telnet, SNMP...). Each
   question ends with a BEL (`\x07`) and `\r\n` counts as two answers: answer one question at
   a time, or quit it keeping defaults:
   `python3 gns3_console.py <GNS3_HOST> <port> --wizard answer q`.
4. `disable clipaging` (the script does not do it for you) before long `show` commands.

## Saving and backing up

- `save` asks `Do you want to save configuration to primary.cfg? (y/N)`. With the script:
  `cmd "save"` then `answer y`. A `*` in front of the prompt (`* SW1.5 #`) means unsaved
  changes: check it before any `reboot` or `use image`.
- **Never send a command right after one that may prompt** (`save`, `enable ssh` key
  generation, `reboot`, `unconfigure switch`) without checking the prompt came back; the
  next command is swallowed as the answer.
- Back up several switches at once (saves first, then exports `show configuration`):
  ```bash
  python3 scripts/backup_configs.py <GNS3_HOST> configs/<session>/v<N> SW1=<port1> SW2=<port2> --save
  ```
  Keep `configs/` in git, one folder per lab session and version, to restore or diff later.
- `show switch | include "ver:|Image|Config"`: images in each partition, booted image,
  selected/booted config. `Config Booted: Factory Default` just means no saved config at the
  last boot.

## `default.xsf`: what really happens at boot

If the switch has **no saved configuration** (never saved, or config deleted /
`unconfigure switch`), it runs `default.xsf` from its filesystem on **every** boot. After
the first `save` it boots from the saved config and `default.xsf` no longer runs. Useful
to build repeatable lab switches:
- Put the per-switch settings in `default.xsf` (sysName, management IP and route,
  accounts, SNTP, SNMP, `tftp get` of lab scripts) and leave the switch unsaved: every
  reboot returns it to the lab baseline.
- Chicken-and-egg: to `tftp get` the file the switch needs a management IP first, so type
  it by hand the first time (example with the out-of-band port:
  `configure vlan Mgmt ipaddress <ip>/<len>` and
  `configure iproute add default <gw> vr VR-Mgmt`), then
  `tftp get <tftp_server> vr VR-Mgmt <path>/default.xsf default.xsf`. With in-band
  management use the VLAN and `vr VR-Default` instead (see next section).
- Anything done by hand (e.g. `enable ssh`) is lost at the next reboot unless you `save`.

## EXOS CLI gotchas seen in the lab (32.6.3)

- DHCP on a VLAN: `enable dhcp ipv4 vlan <name>` (`configure vlan <x> ipaddress dhcp` does
  not exist in this build).
- `enable ipforwarding` globally does not enable it per VLAN: also
  `enable ipforwarding vlan <name>`.
- Loopback for a test "remote host": `create vlan loop` / `configure loop ipaddress
  <ip>/32` / `enable loopback-mode vlan loop`.
- Routes must show the `f` flag (in FIB) in `show iproute` to be really active.
- The console session times out and asks for login again after inactivity.
- Verify syntax with `?` on the switch and against the documentation of **your** version
  (see `extreme-product-docs`): documentation and firmware sometimes disagree.

## Management plane for Site Engine and tools

**Any IP interface of the switch can be used for management** (SSH, SNMP, TFTP/SCP, Site
Engine discovery), not only the `Mgmt` port:
- **Out-of-band**: the `Mgmt` port (GNS3 adapter 0), VLAN `Mgmt`, virtual router `VR-Mgmt`.
  Our labs used this as a design choice: a separate `ethernet_switch` segment linking all
  Mgmt ports with Site Engine, so students can break the data plane without losing
  management.
- **In-band**: an IP on any data VLAN (e.g. `configure vlan Default ipaddress <ip>/<len>`),
  in `VR-Default`, reached through the data ports like any other host. Closer to many real
  networks, and the only option when the Mgmt port is not wired.
- The virtual router matters on the switch side: commands that open connections take a
  `vr` argument (`tftp ... vr VR-Mgmt`, `scp2 vr VR-Default ...`, `ping vr VR-Mgmt ...`,
  SNTP/SNMP trap/syslog targets). Use the VR of the interface you chose. Examples below use
  `VR-Mgmt`; replace it for in-band management.
- SNMP for discovery: `configure snmpv3 add community "public" name "public" user
  "v1v2c_ro"` (and `private`/`v1v2c_rw` for write), `enable snmp access`,
  `enable snmp access snmp-v1v2c` (and/or `snmpv3` with a user of your choice).
- SNTP: `configure sntp-client primary <ip> vr VR-Mgmt`, `enable sntp-client`.
- SSH: `enable ssh2` (generates a key, prompts; then `save`).

## Installing another image (.xos) on a deployed switch

**Only the `.xos` files published for the EXOS VM in github.com/extremenetworks/Virtual_EXOS
can be installed this way.** `.xos` images for physical switch families (Summit, ONIE/5xxx
bundles...) are built for other hardware and are not valid for the EXOS VM; to move a node
to a version that is not published for the VM there is no in-place path.

1. Put the `.xos` somewhere the switch reaches over its management VR (TFTP server, or SCP
   from a Linux host such as Site Engine, whose firmware repository is
   `/tftpboot/firmware/images/`).
2. `download image <tftp_ip> <file>.xos vr VR-Mgmt secondary` or
   `scp2 vr VR-Mgmt <user>@<host>:<path>/<file>.xos <file>.xos` + `install image <file>.xos secondary`.
3. `install` leaves the new partition selected: choose explicitly with `use image
   primary|secondary`, check that the prompt has no `*`, `reboot`, then
   `show switch | include "ver:|Image"`. The configuration is kept.
4. The `.xos` files and md5s are in the `Virtual_EXOS` README (32.6.3.126, 32.7.2.19,
   33.1.1.31, 33.6.1.14 at the time of writing).

## Python and UPM in the lab

- Requirements: `show security python` → `Python (current): On`; `show security fips-mode`
  → `Off`. Python 3 is available on EXOS since 32.2.
- No IP reachability to the switch? Upload a script through the console: `edit script
  <name>.py` (opens vi) then `gns3_console.py <GNS3_HOST> <port> vi-upload <local file>`
  (presses `i`, pastes, `ESC`, `:wq`); check with `ls` and `run script <name>.py`. With IP
  reachability (out-of-band or in-band), `scp2` is simpler.
- To trigger device-detect/UPM events, simulate endpoints with Alpine + lldpd:
  `simulated-devices-in-gns3` (includes a known classification difference: the endpoint
  is seen as `ROUTER`, not `BRIDGE`).

## Environment dependencies — what to look for in yours

| Need | What we used | What to identify in yours |
|---|---|---|
| Console access from scripts | `gns3_console.py` (Python sockets) | Network access to the console port range |
| TFTP/SCP source for `.xos` and `default.xsf` | a Linux node in the lab (Site Engine or a small VM) | Any host reachable from the switch's management VR |
| Config versioning | git | Any VCS |
