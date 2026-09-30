# ExtremeNetworks

## What you'll find here

Community material for building and running **Extreme Networks labs on GNS3**, driven by
[Claude Code](https://claude.com/claude-code). It is not an official Extreme Networks project.

| Path | What it is |
|---|---|
| [`extreme-gns3-skills/`](extreme-gns3-skills/) | A pack of 8 Claude Code skills for Switch Engine (EXOS VM), Fabric Engine (VOSS VM) and ExtremeCloud IQ Site Engine (XIQ-SE) on a GNS3 server. Start with its [README](extreme-gns3-skills/README.md). |
| [`extreme-gns3-skills/skills/`](extreme-gns3-skills/skills/) | The skills themselves, one folder each (`SKILL.md` + helper scripts). |
| [`extreme-gns3-skills/dist/`](extreme-gns3-skills/dist/) | Ready to use: the skills as a `.zip`, and a guide as PDF and HTML. |
| [`extreme-gns3-skills/VALIDATION.md`](extreme-gns3-skills/VALIDATION.md) | What was tested, on which versions, and the results. |
| [`extreme-gns3-skills/src/`](extreme-gns3-skills/src/) | Script and intro text used to build the guide in `dist/`. |
| [`UPM/`](UPM/) | EXOS Universal Port Manager scripts that auto-configure access ports for IP phones (ToIP) and WiFi APs detected by LLDP, discovering VLANs by name. Python and CLI (`.xsf`) versions. |

### The skills

| Skill | What it covers |
|---|---|
| `gns3-server-api` | Driving a remote GNS3 server by its REST API: projects, templates, nodes, links, consoles, NAT, known pitfalls. |
| `extreme-switch-templates` | Adding Switch Engine and Fabric Engine models/versions from github.com/extremenetworks and tuning templates. |
| `switch-engine-in-gns3` | Running EXOS VM nodes: first boot, wizard, save/backup, management, SNMP, `.xos` installs, Python/UPM. |
| `fabric-engine-in-gns3` | Running VOSS VM nodes: first login, Auto-Sense fabric, port/adapter mapping, saving. |
| `simulated-devices-in-gns3` | Alpine containers as LLDP endpoints, 802.1X supplicant + FreeRADIUS, FRR routers, VLAN hosts. |
| `site-engine-in-gns3` | Site Engine as a VM in the lab: sizing, network, discovery, firmware repository, ZTP+, MIB Tools. |
| `site-engine-flexview-builder` | Writing Site Engine FlexViews (`.tpl`) from a MIB and a plain-language description. |
| `extreme-product-docs` | Giving Claude the official User Guides / Command References as searchable text. |

## Quick start

The only prerequisite is a GNS3 server whose API and console ports you can reach.
Download [`extreme-gns3-skills.zip`](extreme-gns3-skills/dist/extreme-gns3-skills.zip) (or
clone this repo) and copy the folders under `extreme-gns3-skills/skills/` to
`~/.claude/skills/` (all projects) or `.claude/skills/` inside a project, keeping them side by
side. Details in the [pack README](extreme-gns3-skills/README.md#install).

## License

Text: CC BY 4.0. Scripts: MIT. See [`LICENSE`](extreme-gns3-skills/LICENSE). Extreme
Networks product names and images belong to Extreme Networks; virtual switch images are not
included.

Contributed by Salva Ferrer (AVTN, aquivatunombre.es).
