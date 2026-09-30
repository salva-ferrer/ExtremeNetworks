---
name: gns3-server-api
description: Use when driving a remote GNS3 server (API v2) to build or operate a lab with Extreme Networks virtual devices (Switch Engine/EXOS, Fabric Engine/VOSS, Site Engine) given only its IP address — checking the server, projects, templates, nodes, links, consoles, NAT, and the known API pitfalls (phantom ports, adapter resize breaking links, auto_close, console port range). For adding switch models see extreme-switch-templates.
---

# Driving a remote GNS3 server through its REST API

The only assumption is **`<GNS3_HOST>`**: the IP (or name) of a working GNS3 server whose API
port (default `3080`) and console port range are reachable from where Claude Code runs. No GUI
is needed; everything here is plain HTTP + JSON. Replace placeholders in `<ANGLE_BRACKETS>`.

## Validated environment

- GNS3 server **2.2.45**, API **v2**, no API authentication, one compute (`local`), KVM
  available on the host. Clients: Linux, `curl` 8.x, Python 3 standard library.
- Devices: Switch Engine (EXOS VM) 32.6.3, Fabric Engine (VOSS VM) 9.4.0, Site Engine
  (XIQ-SE) 24.2 as a QEMU VM, Linux QEMU VMs, docker (Alpine), NAT and `ethernet_switch` nodes.
- **GNS3 3.x uses API v3** (different paths, token authentication). The concepts below still
  hold, but check the v3 documentation before reusing any call.

## Ground rules

1. **Check before anything else**: `curl -s -m 5 http://<GNS3_HOST>:3080/v2/version`. No
   answer means no lab: fix reachability (VPN, firewall, server powered off) first. A server
   that has just booted needs a minute or two before the API answers.
2. **Work in your own project.** A GNS3 server is often shared (courses, other engineers).
   Never open, close, modify or delete a project you did not create: closing a project stops
   all of its nodes. Ask the human before touching anything shared (templates in use, images).
3. **Test in a throwaway project first**, never on nodes someone is using. A telnet console
   is shared: whoever is attached sees everything you type, including `show` commands.
4. Before creating big things (templates, many VMs) check free disk on the server if you
   have a shell there (images live under `/opt/gns3/images/` in a typical install).

## Core API calls (v2)

```
GET  /v2/version                                   # server version
GET  /v2/computes                                  # usually just "local"
GET  /v2/projects                                  # name, project_id, status (opened/closed)
POST /v2/projects                 {"name": "MY_LAB", "auto_close": false}
POST /v2/projects/<p>/open        | /close
PUT  /v2/projects/<p>             {"auto_close": false}
GET  /v2/templates                                 # name, template_id, template_type
POST /v2/projects/<p>/templates/<t>  {"x": 0, "y": 0, "compute_id": "local", "name": "SW1"}
GET  /v2/projects/<p>/nodes                        # status, console, console_type, ports[]
POST /v2/projects/<p>/nodes/<n>/start | /stop | /reload
PUT  /v2/projects/<p>/nodes/<n>   {"name": ..., "properties": {...}}   # node STOPPED
DELETE /v2/projects/<p>/nodes/<n>
GET  /v2/projects/<p>/links
POST /v2/projects/<p>/links       {"nodes": [{"node_id": A, "adapter_number": 1, "port_number": 0},
                                             {"node_id": B, "adapter_number": 1, "port_number": 0}]}
DELETE /v2/projects/<p>/links/<l>
GET  /v2/compute/qemu/images                       # QEMU images on the server
POST /v2/compute/qemu/images/<filename>            # upload an image (raw body)
POST /v2/templates                                 # create a template (extreme-switch-templates)
```
Example session:
```bash
H=http://<GNS3_HOST>:3080/v2
P=$(curl -s -X POST $H/projects -H 'Content-Type: application/json' \
      -d '{"name":"my-lab","auto_close":false}' | python3 -c 'import json,sys;print(json.load(sys.stdin)["project_id"])')
curl -s $H/templates | python3 -c 'import json,sys;[print(t["template_id"],t["name"]) for t in json.load(sys.stdin)]'
curl -s -X POST $H/projects/$P/templates/<TEMPLATE_ID> -H 'Content-Type: application/json' \
     -d '{"x":0,"y":0,"compute_id":"local","name":"SW1"}'
curl -s $H/projects/$P/nodes | python3 -c '
import json,sys
for n in json.load(sys.stdin): print(n["name"], n["status"], n["console_type"], n["console"])'
```

- **Always pass `"compute_id": "local"`** when creating nodes and templates: some creations
  (NAT node, docker template) fail without it.
- **Ports: never guess the mapping.** Read `ports[]` of the node (`adapter_number`,
  `port_number`, `name`). For Extreme appliances adapter 0 is `Mgmt`, and adapter *n* is data
  port *n* (EXOS `Port<n>`, VOSS `1/<n>`); VOSS adapters 25-32 are the breakout ports
  `1/25/1`…`1/26/4`.
- **Set `auto_close: false`** on your project. Otherwise the server closes the project, and
  stops every node in it, when it sees no GUI client connected, which is always the case for
  API-only work. Misleading symptom: consoles or remote desktops "unreachable" in a loop,
  while in fact the whole project is closed (`GET /v2/projects/<p>` → `status`).
- **NAT to the outside world**: there is no invokable "NAT" template; create the node directly:
  `POST /v2/projects/<p>/nodes` with `{"name": "NAT1", "node_type": "nat", "compute_id": "local",
  "properties": {"ports_mapping": [{"interface": "virbr0", "name": "nat0", "port_number": 0, "type": "ethernet"}]}}`.
  It gives DHCP in `192.168.122.0/24` and masquerades **only that subnet**: traffic routed
  from other subnets behind it is lost. Put a Linux router (with its own NAT) in between if
  several lab subnets need Internet access.
- `ethernet_switch` nodes are cheap, have no CLI and are ideal as fan-in segments (management
  network, services network). Create them large (e.g. 48 ports) from day one.

## Consoles

- `console_type` `telnet` (switches) → `telnet <GNS3_HOST> <console>` or, from a script,
  `scripts/gns3_console.py` (below). `vnc`/`spice` (VMs) → a VNC/SPICE viewer on the same
  port. **The console port of VMs may change between restarts**: always read it from the API.
- The GNS3 console port range is **5000-9999** by default. A manual `console` value outside
  it is silently ignored and replaced. If you design a port numbering scheme, keep it within
  4 digits. Changing `console` needs node stopped → `PUT` → start (does not affect links).
- If a remote-desktop gateway (e.g. Apache Guacamole) will front the VMs, use `vnc`, not
  `spice`: the official `guacd` image has no SPICE support. Test with a banner check
  (`cat < /dev/tcp/<GNS3_HOST>/<port>` prints `RFB 003.008` for VNC), not only `nc -z`.

`scripts/gns3_console.py`:
```bash
python3 scripts/gns3_console.py <GNS3_HOST> <port> cmd "show version"                # EXOS
CONSOLE_USER=rwa CONSOLE_PASS='<new password>' python3 scripts/gns3_console.py <GNS3_HOST> <port> \
    cmd "enable" "terminal more disable" "show isis adjacencies"                     # VOSS
python3 scripts/gns3_console.py <GNS3_HOST> <port> cmd "save"      # then:
python3 scripts/gns3_console.py <GNS3_HOST> <port> answer y        # reply to the y/N prompt
```
It logs in if asked, waits for the prompt after every command (so long outputs are
complete), and supports `--wizard`, `esc`, `ctrl-c` and `vi-upload` (see its header).

Console gotchas seen on both Switch Engine and Fabric Engine:
- **Send `\r`, not `\r\n`**: `\r\n` counts as two lines, so a password gets an extra
  empty answer and the login fails (three failures lock the VOSS console for 60 s).
- Interactive steps (first-boot wizards, forced password change, `y/N` confirmations) are
  safest driven one prompt at a time: send, wait for the exact prompt text, send the next.
  Log messages printed on the console (VOSS prints many while it boots: ZTP+, cloud agent,
  Auto-Sense) can hide the prompt from a naive "last line" check.
- A telnet console session survives disconnects: once logged in, the next connection lands
  at the same prompt (and so does anyone else's).

## Known API pitfalls (and how to avoid them)

- **`PUT` changes to `adapters`, `adapter_type`, `ports_mapping`, `console_type` or
  `options` are not applied to a running node.** Always stop → `PUT` → start.
- **Resizing `adapters` on a node that already has links can break them.** Observed: all
  UDP tunnels of the node were reassigned, links stayed listed in `/links` but came back
  with `NO-CARRIER`; restarting the peers did not help; the only fix was deleting and
  recreating the links (and, for a single-port NAT node, the whole node). Changing
  `console_type` or adding QEMU devices can also reorder the VM's PCI bus, so a Linux guest
  renames its NICs (`ens4`→`ens3`).
  **Design rule: never resize, over-provision.** Create each template/node with the adapter
  count it will ever need (plus a spare or two) in the creating `POST`; later "add an
  interface" becomes "link an adapter that already exists", which never triggers the bug.
  For Linux guests, pin NetworkManager profiles by MAC, not by interface name:
  `nmcli connection modify '<profile>' 802-3-ethernet.mac-address <MAC> connection.interface-name ''`.
- **Phantom ports**: after deleting a link, the port may stay reserved (`"Port X isn't free"`
  although `/links` doesn't list it). Restarting the node does not free it. Use another free
  port; for a single-port node (`nat`), delete and recreate the node (it has no state).
- After any resize or console change, re-check `GET .../links` before assuming the cabling
  is unchanged.

## Optional: if you also have a shell on the GNS3 host

Not required by the rest of the pack, but useful:
- **QEMU guest agent** (run commands inside a Linux VM without network): add to the node's
  `properties.options` `-device virtio-serial-pci -chardev socket,path=/tmp/qga-<node>.sock,server,nowait,id=qga0 -device virtserialport,chardev=qga0,name=org.qemu.guest_agent.0`
  (stop → PUT → start; one **unique** socket per node, never at template level or two nodes
  collide), install `qemu-guest-agent` in the guest, then on the host:
  `echo '{"execute":"guest-exec","arguments":{"path":"/bin/hostname","capture-output":true}}' | sudo nc -U /tmp/qga-<node>.sock`
  and read the result with `guest-exec-status` + `{"pid": N}` (`out-data` is base64). Feed
  the JSON through stdin, never interpolated into a quoted shell string.
- Disk: `df -h` of the images/projects filesystem before creating templates. Do large
  `qemu-img` work in a scratch directory on that big filesystem, not in `/tmp` (often on a
  small root partition).

## Environment dependencies — what to look for in yours

| Need | What we used | What to identify in your environment |
|---|---|---|
| Reach the API and console ports | Routed/VPN access to `<GNS3_HOST>` | How you reach 3080 and 5000-9999 without re-routing all your traffic |
| HTTP + JSON client | `curl`, Python 3 stdlib | Any; Python stdlib is enough for the scripts |
| Console client for scripts | `gns3_console.py` (sockets) | Only Python 3 and network access to the console port |
| API version | v2 (GNS3 2.2) | GNS3 3.x → API v3, adapt paths and auth |
