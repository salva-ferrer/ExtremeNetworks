---
name: site-engine-in-gns3
description: Use when running ExtremeCloud IQ Site Engine (XIQ-SE, formerly Extreme Management Center/NetSight) as a VM inside a GNS3 lab together with virtual Switch Engine/Fabric Engine switches — getting the image in, sizing, disks, console, network placement, discovering switches by SNMP, firmware repository, ZTP+ DNS, MIB Tools, cloning/compacting its disks — and for the (not validated) place of ExtremeControl and ExtremeAnalytics engines.
---

# Site Engine (XIQ-SE) inside a GNS3 lab

Assumes `<GNS3_HOST>` (API basics: `gns3-server-api`). Site Engine is **not** on GitHub: it
comes from the Extreme support portal and needs a license (an evaluation license works for
labs).

## Validated environment

- XIQ-SE **24.2.15.5** as a GNS3 QEMU VM on GNS3 2.2.45: web UI, SNMP discovery of EXOS VM
  switches, firmware repository used to push `.xos` images, FlexViews, MIB Tools.
- Instances at 16 GB RAM / 4 vCPU (as installed) and 8 GB / 2 vCPU (clone used for a single
  small lab of a few switches). Not validated with Fabric Engine devices.
- Our base VM was an Ubuntu VM with Site Engine installed on it; we did **not** import the
  vendor virtual appliance ourselves (see "Getting the image in").

## Getting the image in

Two routes; pick what your download gives you:
1. **Vendor virtual appliance (OVA/VMDK)** — not validated by us. An `.ova` is a tar archive:
   `tar xf <file>.ova`, then convert each disk:
   `qemu-img convert -p -O qcow2 <disk>.vmdk siteengine-hda.qcow2` (and `-hdb` for a second
   disk). Upload with `POST /v2/compute/qemu/images/<file>` (as `gns3a_to_template.py
   --upload-image` does) or copy to the server's QEMU images directory, then create a QEMU
   template with the RAM/CPU/disks from the OVA's `.ovf` descriptor.
2. **Install on a Linux VM** (how our instance was built): a supported Linux QEMU VM in
   GNS3, then the Site Engine installer inside it following the Installation Guide.

Template settings that worked: `platform: x86_64`, `adapter_type: virtio-net-pci`, 1-2
adapters (see network), disks as `hda`/`hdb`, `console_type: vnc` (or `spice`), RAM/vCPU as
below. Clear `options` at template level; if you add a QEMU guest-agent socket, set it per
node with a unique path (a socket defined in the template makes two instances collide).

## Sizing

- Start with what the Installation Guide asks for your version (our install: 16 GB / 4 vCPU).
- 8 GB / 2 vCPU was enough for one small lab (a few switches, one or two users). We did not
  go lower. Several instances on one server add up quickly: plan RAM before cloning a pool.

## Network placement

- Site Engine only needs IP reachability to **some** IP of each switch: the out-of-band
  `Mgmt` port or any in-band VLAN interface (see `switch-engine-in-gns3`, "Management
  plane"). In our labs, by design, Site Engine's NIC sat on the same `ethernet_switch`
  segment as the switches' `Mgmt` ports, with a static IP. With in-band management, connect
  it to a data VLAN (or route to one). On the switch, traffic it originates (traps, syslog,
  TFTP/SCP) leaves from the VR of the chosen interface.
- For Internet access (licensing, cloud onboarding, updates) add a second NIC to a GNS3
  `nat` node (DHCP from `192.168.122.0/24`; that address can change between boots, and it is
  only reachable from the GNS3 host itself) or route through a Linux router node.
- Web UI: `https://<site_engine_ip>:8443` from any machine with a route to it (e.g. a Linux
  desktop VM in the lab, reached through its VNC console).
- The console port (VNC/SPICE) can change on every start: read it from the API.

## Using it with the virtual switches

- **Discovery**: enable SNMP on the switches (see `switch-engine-in-gns3`), create the
  matching SNMP credential/profile in Site Engine and discover the management subnet(s) or add devices
  by IP. Check SNMP from the switch side with `show snmpv3 ...` and from Site Engine with its
  MIB Tools.
- **Firmware repository**: images uploaded through the web UI (Firmware / image
  management) land in `/tftpboot/firmware/images/` on the Site Engine server. Switches can pull
  them by TFTP, or with `scp2 vr <VR-Mgmt|VR-Default> <user>@<site_engine_ip>:/tftpboot/firmware/images/<file>.xos <file>.xos`.
  For EXOS VM upload only the `.xos` files published in `Virtual_EXOS` (not `.iso`, not
  images for physical switches).
- **ZTP+**: a switch doing ZTP+ gets an IP and DNS domain by DHCP (on the Mgmt port or an
  in-band VLAN; check which interfaces your version uses in its User Guide) and resolves
  `extremecontrol.<domain>` to find Site Engine. In a lab, make that name resolve to your
  instance: e.g. with dnsmasq, `address=/extremecontrol.<domain>/<site_engine_ip>`. If several
  labs share one flat subnet, tag by client MAC:
  `dhcp-host=<switch MAC on that interface>,set:lab1`, `dhcp-option=tag:lab1,15,"lab1.example"`. The MAC of
  each node port is in the GNS3 API (`ports[].mac_address`). Designed and
  pre-provisioned in our lab; the full ZTP+ flow was not exercised end to end.
- **MIB Tools** (legacy Java Web Start client): `https://<site_engine_ip>:8443/MIB_Tools.jnlp`
  (no link in the web UI of 24.2). On a Linux desktop, `icedtea-netx` (`javaws`) with OpenJDK
  11 runs it (accept the self-signed certificate and the signed app; `sun/misc/Launcher not
  found` traces are harmless). It queries SNMP **from the desktop**, so that desktop needs a
  route to the switches' management IPs.
- **FlexViews** (custom SNMP table views): skill `site-engine-flexview-builder`.

## Cloning and compacting Site Engine disks

To make a reusable template from an instance (or shrink it):
- Compact Site Engine's own database first (from its UI/admin tools), then zero-fill free
  space inside the guest and `qemu-img convert -O qcow2 -c`. **Zero-filling a thin disk
  without discard can first grow it massively** (e.g. from 17 GB to 200+ GB) before
  compaction: check free space first.
- `qemu-img convert` of an image with a backing file **does not always flatten it**: check
  `qemu-img info <file> | grep backing`. If a backing file remains, `qemu-img rebase -b ''
  <file>` (safe mode) merges it; the real size can then be much larger than the first
  result. Run `qemu-img check` before deleting any intermediate copy.
- Do this work in a large scratch directory on the images filesystem, never in `/tmp` on a
  small root partition (it filled `/` once).
- After cloning: new hostname/IP inside the guest, one unique guest-agent socket per node.

## ExtremeControl and ExtremeAnalytics — NOT validated

Not deployed in our lab (their virtual appliances were not available). How they would fit,
to be confirmed with the product documentation of your version:
- Both are separate engine VMs (Access Control engine for ExtremeControl/NAC, Analytics
  engine for ExtremeAnalytics) managed from Site Engine. In GNS3 they would be QEMU VMs built
  from the vendor appliance disks, like route 1 above, each with its own RAM/CPU needs.
- ExtremeControl needs the switches to send RADIUS (802.1X/MAC auth) to the engine: the
  engine's IP must be reachable from the switches' authentication VR, and test endpoints
  (Linux VMs with a supplicant, or Alpine containers) must sit behind switch ports.
- ExtremeAnalytics needs flow data (e.g. IPFIX/sFlow) or mirrored traffic from the switches;
  check which data plane features the virtual switches support (EXOS VM and VOSS VM have
  a limited data plane).
- If you validate them, add a section here with the same structure (image, sizing,
  network, gotchas).

## Environment dependencies — what to look for in yours

| Need | What we used | What to identify in yours |
|---|---|---|
| Site Engine image and license | installed on a Linux VM, evaluation-type lab use | Portal access; OVA or installer for your version |
| Disk conversion | `qemu-img` | `qemu-img` on the client or on the server |
| A browser/desktop inside the lab | Linux desktop VM with Firefox | Any VM with a route to Site Engine, or routing from your own PC |
