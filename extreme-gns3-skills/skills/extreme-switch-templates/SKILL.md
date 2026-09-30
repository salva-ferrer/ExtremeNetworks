---
name: extreme-switch-templates
description: Use when adding an Extreme Networks switch model or firmware version to a remote GNS3 server (Switch Engine/EXOS from github.com/extremenetworks/Virtual_EXOS, Fabric Engine/VOSS from Virtual_VOSS), creating a GNS3 template from a .gns3a appliance file without the GUI, or modifying an existing switch template (more ports, RAM, console, QEMU options such as -cpu host). Needs only the GNS3 server IP.
---

# Adding and modifying Extreme switch templates on a remote GNS3 server

Only `<GNS3_HOST>` is assumed (see `gns3-server-api` for the API basics). Everything here
works through the API: no GUI and no SSH to the server are needed.

## Validated environment

- GNS3 server 2.2.45, API v2. Linux client, Python 3 standard library.
- **Fabric Engine 9.4.0.0**: full path from GitHub to a running two-switch fabric, done
  with `scripts/gns3a_to_template.py` (see `VALIDATION.md` of the pack).
- **Switch Engine 32.6.3.126**: official 13-port template and a 24-data-port extension, used
  in multi-switch labs. Newer EXOS versions (32.7.2.19, 33.x) use the same procedure but were
  not all turned into templates in our lab.

## 1. Official sources (github.com/extremenetworks)

| Product | Repo | Appliance file | Images (qcow2) |
|---|---|---|---|
| Switch Engine (EXOS) | `Virtual_EXOS` | `exosvm.gns3a` | `EXOS-VM_<ver>.qcow2` (32.6.3.126 has a `v` prefix: `EXOS-VM_v32.6.3.126.qcow2`); also `.iso` (install) and `.xos` (in-place upgrade) |
| Fabric Engine (VOSS) | `Virtual_VOSS` | `VOSSGNS3-V9.X.gns3a` (also `.8.X`, `.7.X`) | `FEGNS3.<ver>.qcow2` (9.x), `VOSSGNS3.<ver>.qcow2` (8.x) |

Images are served from `https://akamai-ep.extremenetworks.com/Extreme_P/github-en/<repo>/<file>`.
The `.gns3a` lists every version with its file name, **md5** and download URL:
```bash
curl -sO https://raw.githubusercontent.com/extremenetworks/Virtual_VOSS/master/VOSSGNS3-V9.X.gns3a
python3 scripts/gns3a_to_template.py VOSSGNS3-V9.X.gns3a --list
```
Key appliance parameters (both use `-cpu host`, telnet console, `ide` disk, x86_64):

| | Switch Engine (`exosvm.gns3a`) | Fabric Engine 9.x (`VOSSGNS3-V9.X.gns3a`) |
|---|---|---|
| Adapters | 13 × `rtl8139`: `Mgmt` + `Port1`…`Port12` | 33 × `e1000`: `Mgmt` + `1/1`…`1/24` + 8 named `1/25/1`…`1/26/4` |
| RAM | 1024 MB (512 MB also boots) | 2048 MB (required since 8.1, 64-bit image) |
| Default login | `admin`, no password | `rwa`/`rwa`, **password change forced at first login** |
| Notes | no GTAC support; VXLAN VTEP and VPLS/VPWS configure but have no data plane; may sit 1-2 min in `(pending-AAA) login:` | no GTAC support; emulates a 5520-24T with limited data plane (XA1400 equivalent) since 8.10.1 |

Other useful repos: `EXOS_Apps`, `exoslib` (Python on EXOS), Ansible collections
`extreme.exos`, `extreme.voss`, `extreme.fe`. There is **no Site Engine / XIQ-SE image on
GitHub**: it comes from the Extreme portal with a license (see `site-engine-in-gns3`).
Read the license in each repo: redistribution of the binaries is restricted and publishing
test or benchmark results is not allowed.

## 2. Add a model or version (no GUI, no SSH)

1. Download the qcow2 on the client and check the md5 against the `.gns3a`:
   ```bash
   curl -O https://akamai-ep.extremenetworks.com/Extreme_P/github-en/Virtual_VOSS/FEGNS3.9.4.0.0.qcow2
   md5sum FEGNS3.9.4.0.0.qcow2
   ```
2. Upload it and create the template in one go (the script re-checks the md5, refuses to
   overwrite an existing template name, and prints the new `template_id`):
   ```bash
   python3 scripts/gns3a_to_template.py VOSSGNS3-V9.X.gns3a --version 9.4.0.0 \
       --upload-image FEGNS3.9.4.0.0.qcow2 --post <GNS3_HOST>
   ```
   Without `--post` it prints the JSON only (dry run). Under the hood:
   `POST /v2/compute/qemu/images/<file>` (raw body) then `POST /v2/templates`. If you have
   SSH to the server you can instead copy the file to its QEMU images directory
   (`/opt/gns3/images/QEMU/` on a typical install) and run without `--upload-image`.
3. **Name templates with the version** (`EXOS VM 33.6.1.14`, `FabricEngine VM 9.4.0.0`).
   Never overwrite or edit a template that running labs use; create a new one.
4. Validate in a throwaway project (never on someone's lab): two nodes linked through the
   **highest** port you intend to use, boot, `show lldp neighbor(s)` on both sides, save the
   config, and only then use the template for real work.

If you build the template JSON by hand instead of with the script, include
`"platform": "x86_64"` (or `qemu_path`); without it the node fails with
`qemu-system-None is not found`.

## 3. Modify a template

`PUT /v2/templates/<template_id>` with the fields to change; nodes created **afterwards**
get the new values, existing nodes keep theirs (change a node with `PUT
/v2/projects/<p>/nodes/<n>` + `properties`, node stopped). The script's `--adapters`,
`--ram`, `--cpus`, `--console` and `--name` options cover the common cases when creating.

- **QEMU options: keep `-cpu host` on Switch Engine.** It is a QEMU option that passes the
  host CPU model through to the guest instead of QEMU's generic default model. Without it,
  the EXOS VM does not recognise the CPU it runs on and **stops in its bootloader menu**
  (`~>` prompt, "c) continue with boot process") waiting for someone to continue the boot
  by hand. Fabric Engine 9.4.0.0 booted fine without it (tested), but keep it too, as the
  appliance file does.
- `-enable-kvm` / `-machine accel=kvm` in `options` are **redundant** on a Linux server with
  hardware acceleration enabled: GNS3 already adds `-enable-kvm` to every QEMU node (check a
  node's real `command_line` in the API). The server rewrites the appliance's `-enable-kvm`
  to `-machine accel=kvm`. Adding it to other templates changes nothing.
- `-nographic`: the switches use the serial console (telnet); harmless either way.
- **More ports on Switch Engine**: `adapters` 13 → 25 gives `Mgmt` + `Port1`…`Port24`
  (`PORT_TO_ADAPTER(n) = n`). Keep one `adapter_type` for the whole template (the official
  file uses `rtl8139`). Do it in the template, before creating nodes (see the "never
  resize" rule in `gns3-server-api`). Validate through `Port24`.
- **Fabric Engine ports**: adapters 1-24 = `1/1`…`1/24`. The appliance names adapters 25-32
  as breakout ports `1/25/1`…`1/26/4`, but an unchannelized switch only has `1/25` and
  `1/26` (40G): **adapter 25 = `1/25`, adapter 29 = `1/26`**, the other six carry nothing.
  Rename them in `custom_adapters` if that confuses users.
- `console_type`: keep `telnet` for switches.
- RAM/CPU: do not go below the appliance values without testing boot and your features.

## 4. Upgrading switches already deployed (without changing template)

- Switch Engine: copy the `.xos` from `Virtual_EXOS` to the switch (only those `.xos` files
  are valid for the EXOS VM; physical-switch images are not) via TFTP/SCP from a
  reachable server, e.g. Site Engine's firmware repository), then
  `install image <file>.xos secondary` → `use image secondary` (or primary) → `reboot`, and
  check with `show switch | include "ver:|Image"`. The config is kept.
- Fabric Engine: in-place upgrade with the release `.tgz` from the CLI (8.1+ requires the
  64-bit, 2048 MB settings already in the 9.x appliance). Not validated in our lab.

## Environment dependencies — what to look for in yours

| Need | What we used | What to identify in yours |
|---|---|---|
| Download from GitHub/akamai | `curl` on the client | Any HTTP client; proxy settings if needed |
| Upload images | API upload (`--upload-image`) | Same, or SCP if you have a shell on the server |
| Disk space on the server | checked before uploading | Space in the server's images directory (qcow2: 0.25-0.5 GB each) |
| KVM on the server host | enabled | Without KVM (nested virtualization off) the VMs are very slow or do not boot |
