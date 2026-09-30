---
name: simulated-devices-in-gns3
description: Use when a GNS3 lab with Extreme switches (Switch Engine/EXOS, Fabric Engine/VOSS) needs other devices connected to the network — LLDP endpoints (APs, phones), 802.1X supplicants and a RADIUS server, routers for OSPF/BGP tests, hosts on tagged VLANs, DHCP/DNS/syslog/TFTP servers, traffic sources — built from lightweight Alpine Linux docker containers. Includes what was tested and what did not work (LAG/LACP from a container).
---

# Simulating devices around the switches with Alpine containers

Real endpoints, servers and routers are rarely available as GNS3 appliances, but a small
**Alpine Linux docker container** with the right package covers most needs, costs a few MB
of RAM, and boots in a second. Assumes `<GNS3_HOST>` (API: `gns3-server-api`).

## Validated environment

Tested with EXOS VM 32.6.3.126 on GNS3 2.2.45 (see `VALIDATION.md`), `alpine:latest`
containers, packages from the Alpine repositories:

| Device simulated | Package | Status |
|---|---|---|
| LLDP endpoint (AP, generic device) | `lldpd` | **Validated** (UPM device-detect tests), with a classification caveat, see `reference/lldpd_endpoints.md` |
| 802.1X supplicant (wired, EAP-MD5) | `wpa_supplicant` | **Validated**: authenticated by EXOS netlogin through RADIUS; wrong password → reject, port unauthorized |
| RADIUS server | `freeradius` + `freeradius-eap` | **Validated** (Access-Accept / Access-Reject to EXOS) |
| OSPF router | `frr` | **Validated**: adjacency `FULL` with EXOS, loopbacks exchanged and reachable |
| Host on a tagged VLAN (802.1Q) | busybox `ip` | **Validated**: VLAN subinterface ↔ EXOS tagged port |
| LAG (LACP or static) to the switch | `iproute2` bonding | **Did not work** (see below) |
| BGP router, DHCP/DNS server, syslog/SNMP trap receiver, TFTP server, traffic generator, LLDP-MED phone, MAC-auth client, PEAP/TLS 802.1X | `frr`, `dnsmasq`, `rsyslog`/`net-snmp`, `tftp-hpa`, `iperf3`, `lldpd` | **Not validated**, recipes below are starting points |

Fabric Engine: same containers apply (LLDP was seen between VOSS and EXOS; the rest was not
tested against VOSS).

## Building blocks

**Container node** (no template needed; `compute_id` required):
```
POST /v2/projects/<p>/nodes
{"name": "RAD", "node_type": "docker", "compute_id": "local",
 "properties": {"image": "alpine:latest", "adapters": 2, "start_command": "/bin/sh",
                "console_type": "telnet"}}
```
The server pulls `alpine:latest` the first time (it needs Internet access). Or create a
reusable template with the same properties (`POST /v2/templates`, `template_type: docker`).

**Pattern: two interfaces per container.** `eth0` → an `ethernet_switch` linked to a GNS3
`nat` node, only for installing packages (`udhcpc -i eth0 -q; apk add -q <pkg>`); `eth1`
→ the switch port under test. This keeps the lab port clean and the switch out of the
Internet path. If you prefer no Internet at all, build your own image with the packages
preinstalled and push it to a registry the server can reach.

**Consoles**: the container console (telnet) is a root shell (`/ # `); drive it with
`gns3_console.py cmd "..."` like a switch. Addresses: `ip addr add <ip>/<len> dev eth1;
ip link set eth1 up`. Do not count on persistence: GNS3 keeps only the directories declared
persistent for docker nodes (`extra_volumes`; `/etc/network` by default) when containers
are recreated, so keep the setup commands in a script you can replay (we did not test which
changes survive a project close/reopen).

## 802.1X: supplicant + RADIUS + switch

Topology: RADIUS container `eth1` → switch port 1 (VLAN `radnet`), supplicant `eth1` → port 2.

RADIUS (FreeRADIUS 3 on Alpine):
```sh
apk add -q freeradius freeradius-eap openssl make
ip addr add 10.0.1.2/24 dev eth1; ip link set eth1 up
printf 'client sw1 {\n ipaddr = 10.0.1.1\n secret = testing123\n}\n' >> /etc/raddb/clients.conf
sed -i '1i testuser Cleartext-Password := "testpass"' /etc/raddb/mods-config/files/authorize
cd /etc/raddb/certs && ./bootstrap && chown -R radius:radius /etc/raddb/certs; cd /
(radiusd -X > /tmp/rad.log 2>&1 &)          # debug mode, log in /tmp/rad.log
```
The EAP module **does not start without certificates** (`rlm_eap_tls: Failed initializing
SSL context`) even if you only use EAP-MD5: run `certs/bootstrap` (self-signed, fine for a
lab; also needed for PEAP). Add VSAs (VLAN, Filter-Id) after the password in the
`authorize` file to test dynamic VLAN / policy assignment.

Switch Engine (netlogin 802.1X on port 2, RADIUS reached in-band from VR-Default):
```
configure vlan Default delete ports 1
create vlan radnet
configure vlan radnet add ports 1
configure vlan radnet ipaddress 10.0.1.1/24
configure radius netlogin primary server 10.0.1.2 1812 client-ip 10.0.1.1 vr VR-Default shared-secret testing123
enable radius netlogin
create vlan nlvlan
configure netlogin vlan nlvlan          # required first: "Error: No NetLogin VLAN is configured."
enable netlogin dot1x
enable netlogin ports 2 dot1x
```
Supplicant:
```sh
apk add -q wpa_supplicant
ip link set eth1 up
printf 'ctrl_interface=/var/run/wpa_supplicant\nap_scan=0\nnetwork={\n key_mgmt=IEEE8021X\n eap=MD5\n identity="testuser"\n password="testpass"\n eapol_flags=0\n}\n' > /etc/wpa.conf
wpa_supplicant -B -D wired -i eth1 -c /etc/wpa.conf     # Alpine's build has no -f option
wpa_cli -i eth1 status        # EAP state=SUCCESS, suppPortStatus=Authorized
```
Check: `show netlogin port 2` → `Yes, Radius  802.1x  testuser`; `/tmp/rad.log` →
`Access-Accept`. Negative test: `wpa_cli -i eth1 set_network 0 password '"wrong"'`,
`wpa_cli -i eth1 logoff; wpa_cli -i eth1 logon` → `EAP state=FAILURE`, `Access-Reject`,
switch shows `No`. EAPOL frames cross GNS3 container links without any special setting.
Next steps (not validated): PEAP (`eap=PEAP`, `phase2="auth=MSCHAPV2"`), MAC-based auth
(`enable netlogin mac`, RADIUS user = MAC address), several supplicants behind a hub.

## Routers for routing tests (FRRouting)

```sh
apk add -q frr
ip addr add 10.0.3.2/24 dev eth1; ip link set eth1 up; ip addr add 10.99.99.2/32 dev lo
sed -i 's/^ospfd=no/ospfd=yes/' /etc/frr/daemons        # bgpd=yes for BGP
/usr/lib/frr/frrinit.sh start
vtysh -c 'conf t' -c 'router ospf' -c 'ospf router-id 2.2.2.2' \
      -c 'network 10.0.3.0/24 area 0' -c 'network 10.99.99.2/32 area 0' -c 'end'
vtysh -c 'show ip ospf neighbor' -c 'show ip route ospf'
```
Switch Engine side:
```
configure vlan Default delete ports 3
create vlan ospfnet
configure vlan ospfnet add ports 3
configure vlan ospfnet ipaddress 10.0.3.1/24
enable ipforwarding vlan ospfnet
configure ospf routerid 1.1.1.1
configure ospf add vlan ospfnet area 0.0.0.0
enable ospf
show ospf neighbor                 # 2.2.2.2 FULL
```
Advertise more prefixes from the container (loopbacks, `ip route add blackhole ...` +
`redistribute static`) to load the switch's routing table. BGP (`bgpd=yes`, `router bgp
<asn>`, `neighbor ...`) follows the same pattern: not validated.
Useful for: route redistribution, filtering/policies, ECMP (two routers), failover tests,
VRRP neighbours (`keepalived` package, not validated).

## Hosts on tagged VLANs

```sh
ip link add link eth1 name eth1.20 type vlan id 20
ip addr add 10.0.20.2/24 dev eth1.20; ip link set eth1.20 up
```
Switch: `create vlan v20 tag 20`, `configure vlan v20 add ports 3 tagged`, IP on the VLAN.
One container can be a host in many VLANs (one subinterface each), handy for inter-VLAN
routing, ACL and QoS classification tests.

## Other servers and tools (not validated)

- **DHCP/DNS**: `dnsmasq` (`dhcp-range=...`, `address=/name/ip`); with the switch as relay
  (EXOS `configure bootprelay add <server>`), dnsmasq answers relayed requests with only a
  `dhcp-range` for that subnet. Do not use dnsmasq's own `dhcp-relay=` for this.
- **Syslog / SNMP traps**: `rsyslog` or `busybox syslogd -n -O /dev/stdout`; `net-snmp`
  (`snmptrapd -f -Lo`).
- **TFTP/SCP server** for configs, scripts and `.xos` images: `tftp-hpa` (`in.tftpd -L -s
  /srv/tftp`), `openssh`.
- **Traffic**: `iperf3`, `hping3`, `tcpreplay` to exercise ACLs, QoS, flow export. Mind the
  limited data plane of the virtual switches: use it for function, not for performance.
- **LLDP-MED phone**: `lldpd` supports MED classes and network policies; check which device
  type the switch assigns before relying on it.

## LAG / LACP from a container: did not work

Tried with a container with two links to EXOS ports 4-5 (`ip link add bond0 type bond mode
802.3ad`, iproute2) and `enable sharing 4 grouping 4-5 lacp`: the container received the
switch's LACPDUs (partner MAC set, both members in one aggregator), but EXOS stayed
`Selected`/`Waiting` with aggregator count 0 and no traffic. Static sharing with a
`balance-xor` bond failed too, and the link state of ports 4-5 on the EXOS VM flapped
between up and down after the container's interfaces were reconfigured. To test LAGs, use
two virtual switches back to back (not validated in this pack either).

## Why not 802.3x?

802.3x is Ethernet flow control (PAUSE frames). GNS3 links are software tunnels without
real congestion or PHY behaviour, so flow control cannot be tested meaningfully; test it on
hardware.

## Environment dependencies — what to look for in yours

| Need | What we used | What to identify in yours |
|---|---|---|
| Docker on the GNS3 server | GNS3's docker support, `alpine:latest` pulled from Docker Hub | Docker installed on the server and a reachable registry |
| Package installs | NAT node + `apk` | Internet via NAT, or prebuilt images |
