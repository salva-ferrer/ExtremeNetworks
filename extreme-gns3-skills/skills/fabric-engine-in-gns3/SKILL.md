---
name: fabric-engine-in-gns3
description: Use when running Extreme Fabric Engine (VOSS VM, 5520-24T emulation) nodes in a GNS3 lab from Claude Code — first boot, forced password change, console quirks, Auto-Sense fabric formation, port-to-adapter mapping (including the 40G ports), saving config, and what has and has not been validated.
---

# Fabric Engine (VOSS VM) in a GNS3 lab

Assumes a Fabric Engine template on `<GNS3_HOST>` (create it from
`VOSSGNS3-V9.X.gns3a` with `extreme-switch-templates`). Consoles: `gns3-server-api`.

## Validation status — read first

**Validated (Fabric Engine 9.4.0.0, GNS3 2.2.45):** template from GitHub via the API, boot,
first login and password change, Auto-Sense forming an SPBM adjacency between two nodes,
LLDP towards Switch Engine, the 40G ports, `save config`, booting without `-cpu host`.
**Not validated:** services on top of the fabric (L2/L3 VSNs, I-SIDs, DvR, multicast),
management IP configuration (out-of-band `Mgmt` port or in-band), upgrades, Site Engine onboarding of VOSS, anything with more than two
nodes. Treat those parts as your own tests, and check the syntax against the Fabric Engine
documentation of your release (`extreme-product-docs`).

## First boot

1. Boot to `Login:` takes about 2-3 minutes. The console is noisy: log lines (ZTP+
   discovery, cloud agent trying to reach ExtremeCloud IQ, Auto-Sense) keep scrolling and
   can land after the `Login:` prompt.
2. On the console, a first-boot questionnaire may appear (disable MSTP? enhanced security
   mode? disable telnet? enable SNMPv1/v2c? SNMPv3?). Answer one question at a time; empty
   answers keep the defaults.
3. Login `rwa` / `rwa`. **The first login forces a password change** ("This is an initial
   attempt using the default password. Please change the password to continue."): enter a
   new password twice. Drive this one prompt at a time: wait for `Password:`, `Enter the New
   password :`, `Re-enter the New password :`, then the prompt `5520-24T-FabricEngine:1>`:
   ```bash
   C="python3 ../gns3-server-api/scripts/gns3_console.py <GNS3_HOST> <port>"
   $C answer ""    --until "Login: ?$"
   $C answer rwa   --until "Password: ?$"
   $C answer rwa   --until "New password ?: ?$"
   $C answer '<new password>' --until "Re-enter.*: ?$"
   $C answer '<new password>' --until "[>#] ?$"
   ```
4. **Send `\r`, not `\r\n`**: with `\r\n` the switch sees an extra empty line, takes an
   empty password, and after 3 failures locks the console for 60 seconds ("Maximum number
   of login attempts reached for console").
5. Then `enable` (prompt `...:1#`) and `terminal more disable` before long outputs. The
   session survives disconnecting from the console port:
   ```bash
   python3 ../gns3-server-api/scripts/gns3_console.py <GNS3_HOST> <port> \
       cmd "enable" "terminal more disable" "show sys-info" "show isis adjacencies"
   ```

## What you get with no configuration

- Every data port has **Auto-Sense** enabled. Linking two Fabric Engine nodes port-to-port
  forms the fabric on its own: the port goes `NNI-ISIS-UP`, `show isis adjacencies` shows the
  neighbor, an SPBM nickname is auto-generated. Two parallel links go `NNI-MLT`.
- A Switch Engine neighbor is detected as a Fabric Attach proxy
  (`Auto-Sense port ... entered FA-PROXY-NOAUTH state`), and both see each other by LLDP.
- Useful checks: `show lldp neighbor`, `show lldp neighbor summary`, `show isis
  adjacencies`, `show interfaces gigabitEthernet auto-sense <ports>`,
  `show interfaces gigabitEthernet interface <ports>`.
- If you don't want this in a lab (e.g. a port towards a plain host), disable Auto-Sense on
  that port per the documentation of your release.

## Ports and GNS3 adapters

| GNS3 adapter | Appliance port name | Switch port |
|---|---|---|
| 0 | `Mgmt` | management port |
| 1-24 | `1/1`…`1/24` | `1/1`…`1/24` (1000BaseTX) |
| 25 | `1/25/1` | **`1/25`** (40G) |
| 29 | `1/26/1` | **`1/26`** (40G) |
| 26-28, 30-32 | `1/25/2-4`, `1/26/2-4` | no link while the ports are not channelized |

The node reports a chassis `5520-24T-FabricEngine` and a dummy serial number.

## Saving

`save config` → `Save config to file /intflash/config.cfg successful`. Back up with
`backup_configs.py ... --os voss` from the `switch-engine-in-gns3` skill (exports
`show running-config`; set `CONSOLE_USER`/`CONSOLE_PASS` if the console asks for login).

## Resources and options

- 2048 MB RAM, 1 vCPU per node (appliance defaults). Several nodes need several GB of RAM on
  the server: check capacity before building larger fabrics.
- 9.4.0.0 booted fine with and without the QEMU option `-cpu host`; keep it as in the
  appliance file. `-enable-kvm` from the appliance is redundant (GNS3 adds it).

## Environment dependencies — what to look for in yours

| Need | What we used | What to identify in yours |
|---|---|---|
| Image and template | `FEGNS3.9.4.0.0.qcow2` + `VOSSGNS3-V9.X.gns3a` from GitHub | Same, or the version your lab needs |
| Interactive console steps | one-prompt-at-a-time Python over sockets | Any expect-like tool, or a human at the console for first login |
