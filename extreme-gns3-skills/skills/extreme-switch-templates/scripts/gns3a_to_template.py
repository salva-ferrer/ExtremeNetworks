#!/usr/bin/env python3
"""Turn a GNS3 appliance file (.gns3a) into a template for a remote GNS3 server (API v2).

The GNS3 GUI "Import appliance" wizard does this interactively. On a remote server with
no GUI, this script builds the same QEMU template JSON and (optionally) posts it.

Usage:
  gns3a_to_template.py <file.gns3a> --list                      # show versions in the file
  gns3a_to_template.py <file.gns3a> --version <v> [--name N]    # print template JSON (dry run)
  gns3a_to_template.py <file.gns3a> --version <v> --post <GNS3_HOST>[:port]
  gns3a_to_template.py <file.gns3a> --version <v> --upload-image <local.qcow2> --post <GNS3_HOST>

Options:
  --name N             template name (default: "<appliance name> <version>")
  --adapters N         override the adapter count (extend ports; same adapter_type is kept)
  --ram MB / --cpus N  override RAM / vCPUs
  --console TYPE       override console_type (telnet, vnc, spice, none...)
  --upload-image FILE  upload the disk image through the API before creating the template
                       (POST /v2/compute/qemu/images/<filename>; no SSH to the host needed)

Only the Python 3 standard library is used. Tested against GNS3 server 2.2 (API v2).
"""
import argparse
import hashlib
import json
import os
import sys
import urllib.request

# Fields copied as-is from the appliance "qemu" section into the template.
QEMU_FIELDS = ["adapter_type", "adapters", "ram", "cpus", "hda_disk_interface",
               "hdb_disk_interface", "console_type", "boot_priority", "options",
               "kernel_command_line", "cpu_throttling", "process_priority", "on_close"]


def load(path):
    with open(path) as f:
        return json.load(f)


def find_version(app, version):
    for v in app.get("versions", []):
        if v["name"].lstrip("v") == version.lstrip("v"):
            return v
    names = ", ".join(v["name"] for v in app.get("versions", []))
    sys.exit(f"version {version!r} not in appliance (available: {names})")


def image_info(app, filename):
    for img in app.get("images", []):
        if img["filename"] == filename:
            return img
    return {}


def build_template(app, ver, args):
    q = app["qemu"]
    t = {"template_type": "qemu", "compute_id": "local",
         "name": args.name or f"{app['name']} {ver['name'].lstrip('v')}",
         "category": {"multilayer_switch": "switch", "router": "router",
                      "guest": "guest", "firewall": "firewall"}.get(app.get("category"), "switch"),
         "symbol": app.get("symbol", ":/symbols/multilayer_switch.svg"),
         # platform is mandatory when building the JSON by hand: without it the node fails
         # to start with "qemu-system-None is not found".
         "platform": q.get("arch", "x86_64")}
    for k in QEMU_FIELDS:
        if k in q:
            t[k] = q[k]
    for k in ("first_port_name", "port_name_format", "port_segment_size", "linked_clone"):
        if k in app:
            t[k] = app[k]
    if "custom_adapters" in app:
        t["custom_adapters"] = app["custom_adapters"]
    for disk, fname in ver["images"].items():   # hda_disk_image, cdrom_image, ...
        t[disk] = fname
    if args.adapters:
        t["adapters"] = args.adapters
    if args.ram:
        t["ram"] = args.ram
    if args.cpus:
        t["cpus"] = args.cpus
    if args.console:
        t["console_type"] = args.console
    return t


def api(host, method, path, body=None, stream=None):
    if ":" not in host:
        host += ":3080"
    data = stream if stream is not None else (json.dumps(body).encode() if body is not None else None)
    req = urllib.request.Request(f"http://{host}/v2{path}", data=data, method=method)
    if body is not None:
        req.add_header("Content-Type", "application/json")
    if stream is not None:   # stream the file instead of loading it into memory
        req.add_header("Content-Length", str(os.fstat(stream.fileno()).st_size))
        req.add_header("Content-Type", "application/octet-stream")
    with urllib.request.urlopen(req, timeout=600) as r:
        txt = r.read().decode()
        return json.loads(txt) if txt else {}


def md5(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("gns3a")
    p.add_argument("--list", action="store_true")
    p.add_argument("--version")
    p.add_argument("--name")
    p.add_argument("--adapters", type=int)
    p.add_argument("--ram", type=int)
    p.add_argument("--cpus", type=int)
    p.add_argument("--console")
    p.add_argument("--upload-image")
    p.add_argument("--post", metavar="GNS3_HOST")
    a = p.parse_args()

    app = load(a.gns3a)
    if a.list or not a.version:
        for v in app.get("versions", []):
            for fname in v["images"].values():
                i = image_info(app, fname)
                print(f"{v['name']:12} {fname:32} md5={i.get('md5sum', '?')} "
                      f"url={i.get('direct_download_url', '-')}")
        return

    ver = find_version(app, a.version)
    tpl = build_template(app, ver, a)
    if not a.post:
        print(json.dumps(tpl, indent=2))
        return

    if a.upload_image:
        fname = os.path.basename(a.upload_image)
        if fname != tpl.get("hda_disk_image"):
            sys.exit(f"image file name {fname} != appliance image {tpl.get('hda_disk_image')}")
        expected = image_info(app, fname).get("md5sum")
        got = md5(a.upload_image)
        if expected and got != expected:
            sys.exit(f"md5 mismatch for {fname}: {got} != {expected}")
        print(f"uploading {fname} ({os.path.getsize(a.upload_image)} bytes)...", file=sys.stderr)
        with open(a.upload_image, "rb") as f:
            api(a.post, "POST", f"/compute/qemu/images/{fname}", stream=f)

    present = {i["filename"] for i in api(a.post, "GET", "/compute/qemu/images")}
    missing = [f for f in ver["images"].values() if f not in present]
    if missing:
        sys.exit(f"image(s) not on the server: {missing} (use --upload-image)")
    if any(t["name"] == tpl["name"] for t in api(a.post, "GET", "/templates")):
        sys.exit(f"a template named {tpl['name']!r} already exists; pick another --name")
    res = api(a.post, "POST", "/templates", tpl)
    print(json.dumps({"template_id": res["template_id"], "name": res["name"]}))


if __name__ == "__main__":
    main()
