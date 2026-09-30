# Claude Code skills for Extreme Networks labs on GNS3

A pack of [Claude Code](https://claude.com/claude-code) *skills* to build and run labs with
Extreme Networks virtual products on a GNS3 server: **Switch Engine (EXOS VM)**, **Fabric
Engine (VOSS VM)** and **ExtremeCloud IQ Site Engine (XIQ-SE)**. They come from real work:
training labs with many pods, a customer proof of concept, and scripted tests, all driven
by Claude Code through the GNS3 API.

**The only assumption: you have the IP address of a working GNS3 server** (`<GNS3_HOST>`)
whose API and console ports you can reach. No GNS3 GUI, and no shell on the server, is
required.

## Contents

| Skill | What it covers |
|---|---|
| `gns3-server-api/` | Driving a remote GNS3 server by its REST API (v2): projects, templates, nodes, links, consoles, NAT, known pitfalls. Script `gns3_console.py` to talk to node consoles. |
| `extreme-switch-templates/` | Adding Switch Engine and Fabric Engine models/versions from github.com/extremenetworks and modifying templates (ports, RAM, QEMU options such as `-cpu host`). Script `gns3a_to_template.py`: `.gns3a` appliance → template, with image upload through the API. |
| `switch-engine-in-gns3/` | Running EXOS VM nodes: first boot, wizard, save/backup (`backup_configs.py`), `default.xsf`, out-of-band or in-band management, SNMP, `.xos` installs, Python/UPM. |
| `fabric-engine-in-gns3/` | Running VOSS VM nodes: first login and forced password change, Auto-Sense fabric, port/adapter mapping, saving. |
| `simulated-devices-in-gns3/` | Devices around the switches from Alpine containers: LLDP endpoints, 802.1X supplicant + FreeRADIUS, FRR routers (OSPF), tagged-VLAN hosts, servers and traffic tools; what did not work (LAG from a container). |
| `site-engine-in-gns3/` | Site Engine as a VM in the lab: image, sizing, disks, network, discovery, firmware repository, ZTP+ DNS, MIB Tools; ExtremeControl/ExtremeAnalytics (not validated). |
| `site-engine-flexview-builder/` | Writing Site Engine FlexViews (`.tpl`) from a MIB and a plain-language description. |
| `extreme-product-docs/` | Giving Claude the official User Guides / Command References as searchable text (`prepare_docs.py`) and the rules to use them. |

Every `SKILL.md` has the same structure: **validated environment**, procedure, gotchas, and
**environment dependencies** (what to look for if your setup differs).

## What has been validated

| Product | Version | Status |
|---|---|---|
| GNS3 server | 2.2.45 (API v2) | Validated. GNS3 3.x (API v3) not tested. |
| Switch Engine (EXOS VM) | 32.6.3.126 | Validated in multi-switch labs over several months. |
| Fabric Engine (VOSS VM) | 9.4.0.0 | Validated in a live test from GitHub to a two-node fabric (see `VALIDATION.md`). Fabric services not tested. |
| Site Engine (XIQ-SE) | 24.2.15.5 | Validated as a GNS3 VM with EXOS VM switches. |
| Simulated devices (Alpine) | alpine:latest | LLDP, 802.1X (EAP-MD5) + FreeRADIUS, FRR OSPF, 802.1Q hosts validated against EXOS VM; LAG from a container did not work; others not validated. |
| ExtremeControl, ExtremeAnalytics | — | **Not validated** (virtual appliances were not available). Guidance only. |

Everything ran on Linux clients (bash/fish, Python 3, curl). Windows and macOS were not
tested; the environment-dependency tables say what to adapt.

## Install

A skill is a folder with a `SKILL.md`. Copy the folders under `skills/` to
`~/.claude/skills/` (all your projects) or to `.claude/skills/` inside a project. Claude Code
lists them at start-up and uses one when the task matches its description; you can also
name it explicitly ("use the fabric-engine-in-gns3 skill"). Scripts need Python 3 (standard
library only); `prepare_docs.py` also uses `pdftotext`.

The scripts are referenced with paths relative to each skill folder
(e.g. `../gns3-server-api/scripts/gns3_console.py`): keep the folders side by side.

## Good practice

- Work in **your own GNS3 project**; never touch other people's projects on a shared server.
- Test on throwaway nodes, never on a switch someone is using: consoles are shared.
- Keep credentials out of files and chats: the scripts read `CONSOLE_USER`/`CONSOLE_PASS`
  from the environment.
- The Extreme virtual images are not supported by GTAC and have their own license
  (see each GitHub repo): this pack links to them and never redistributes them.

## License

Text: CC BY 4.0. Scripts: MIT. See `LICENSE`. Extreme Networks product names and images
belong to Extreme Networks; this is a community contribution, not an official Extreme
Networks product.

Contributed by Salva Ferrer (AVTN, aquivatunombre.es).
