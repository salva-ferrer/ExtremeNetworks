## About this guide

This document goes with the `extreme-gns3-skills` pack. It explains how to use the pack with
Claude Code and reproduces the full text of every skill so a person can review it before
installing. The scripts are only in the zip.

**Who it is for:** engineers, trainers and partners who build labs with Extreme Networks
virtual products on GNS3 and want Claude Code to do the repetitive work: creating
templates from the official GitHub images, building topologies through the API, booting and
configuring switches through their consoles, backing up configurations, and bringing Site
Engine into the lab.

**The only assumption:** the IP address of a working GNS3 server (`<GNS3_HOST>`) whose API
port (3080) and console ports (5000-9999) you can reach. Everything else (templates,
images, projects) can be created from there.

## How to work with Claude Code on a lab

- **Plan first, then execute.** For anything beyond a quick check, let Claude investigate
  and propose a plan (Claude Code's *plan mode*), approve it, then let it run. Say whether it
  may run the whole plan unattended or must stop at checkpoints.
- **Shared server, explicit consent.** On a GNS3 server used by others, ask Claude to
  confirm before anything that changes shared state: starting or stopping the server,
  opening or closing other projects, modifying templates or images in use. Inside its own
  throwaway project it can follow an approved plan.
- **Evidence over assumptions.** Ask Claude to check every claim against the device:
  command output, `show` commands, the API's own view (`GET .../nodes`, `command_line`),
  and the official documentation of the exact version (`extreme-product-docs`).
- **Consoles are shared.** Whatever Claude types on a switch console is visible to anyone
  attached to it, and vice versa. Never experiment on a switch someone else is using.
- **Credentials** go in environment variables or are typed by the human, never in files
  or chat.
- **Save what you learn.** Findings from each session (a gotcha, a working command) should go
  into project notes or into these skills, so the next session starts from there.

## Quick start: from an IP address to a small lab

1. *"Check the GNS3 server at `<GNS3_HOST>` and list its templates."* (`gns3-server-api`)
2. *"Add Fabric Engine 9.4.0.0 and Switch Engine 33.6.1.14 from Extreme's GitHub as
   templates."* (`extreme-switch-templates`: download, md5 check, upload through the API,
   template from the `.gns3a`)
3. *"Create a project `my-lab` with two Fabric Engine switches linked on 1/1 and one Switch
   Engine on 1/24 of the second, start them."* (`gns3-server-api`)
4. *"Do the first login on each switch and show me LLDP neighbors and IS-IS adjacencies."*
   (`fabric-engine-in-gns3`, `switch-engine-in-gns3`)
5. *"Save and back up all configs to `configs/v1`."* (`backup_configs.py`)
6. *"Add a FreeRADIUS container and an 802.1X client on port 2, and an FRR router peering
   OSPF on port 3."* (`simulated-devices-in-gns3`)
7. Optional: *"Add Site Engine to the management network and discover the switches."*
   (`site-engine-in-gns3`)

## What has been validated

| Product | Version | Status |
|---|---|---|
| GNS3 server | 2.2.45 (API v2) | Validated. GNS3 3.x (API v3) not tested. |
| Switch Engine (EXOS VM) | 32.6.3.126 | Validated in multi-switch labs over several months. |
| Fabric Engine (VOSS VM) | 9.4.0.0 | Validated in a live test from GitHub to a two-node fabric. Fabric services not tested. |
| Site Engine (XIQ-SE) | 24.2.15.5 | Validated as a GNS3 VM with EXOS VM switches. |
| Simulated devices (Alpine) | alpine:latest | LLDP, 802.1X (EAP-MD5) + FreeRADIUS, FRR OSPF, 802.1Q hosts validated against EXOS VM; LAG from a container did not work; others not validated. |
| ExtremeControl, ExtremeAnalytics | — | **Not validated** (virtual appliances were not available). Guidance only. |

Clients were Linux only. Each skill ends with an **environment dependencies** table that
says what to look for if your setup differs. The detailed evidence is in the appendix
"Validation log".

## Giving Claude the product documentation

Claude's general knowledge of Extreme CLIs is not version-exact. Download the User Guide,
Command Reference, EMS Message Catalog (and for Site Engine, its documentation collection)
**for the versions in your lab**, put them in a `docs/` folder, run
`scripts/prepare_docs.py docs/` (PDF and HTML to searchable text, plus an index), and tell
Claude the folder exists. The skill `extreme-product-docs` makes Claude search it before
stating a command, prefer the live CLI when they disagree, and cite the page it used.
