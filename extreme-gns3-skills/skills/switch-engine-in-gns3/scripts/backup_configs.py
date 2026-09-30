#!/usr/bin/env python3
"""Save and back up the running configuration of several Switch Engine (EXOS) or Fabric
Engine (VOSS) nodes through their GNS3 telnet consoles.

Usage:
  backup_configs.py <GNS3_HOST> <out_dir> <name>=<console_port> [<name>=<port> ...] [--os exos|voss] [--save]

  --save   run "save" (EXOS, answering y) / "save config" (VOSS) before exporting
Each switch's "show configuration" (EXOS) / "show running-config" (VOSS) is written to
<out_dir>/<name>.cfg. Consoles must be at the CLI prompt (already logged in, or EXOS
"admin" with no password). Version the out_dir with git, one folder per lab session/version.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "..", "gns3-server-api", "scripts"))
import gns3_console as gc   # noqa: E402
import socket               # noqa: E402

CMDS = {"exos": ("disable clipaging", "show configuration", "save"),
        "voss": ("terminal more disable", "show running-config", "save config")}


def run(sock, cmd, wait=30):
    sock.sendall(cmd.encode() + b"\r")
    return gc.clean(gc.read_until(sock, gc.at_prompt, wait))


def main():
    args = sys.argv[1:]
    osname = "exos"
    if "--os" in args:
        i = args.index("--os"); osname = args[i + 1]; del args[i:i + 2]
    save = "--save" in args
    if save:
        args.remove("--save")
    if len(args) < 3:
        sys.exit(__doc__)
    host, out = args[0], args[1]
    os.makedirs(out, exist_ok=True)
    nopage, show, savecmd = CMDS[osname]
    for pair in args[2:]:
        name, port = pair.split("=")
        s = socket.create_connection((host, int(port)), timeout=15)
        gc.login_if_needed(s, b"\r", os.environ.get("CONSOLE_USER", "admin"),
                           os.environ.get("CONSOLE_PASS", ""), 10)
        run(s, nopage, 5)
        if save:
            o = run(s, savecmd, 15)
            if "(y/N)" in o:
                run(s, "y", 30)
        text = run(s, show, 60)
        lines = text.replace("\r", "").split("\n")[1:]          # drop the command echo
        while lines and (not lines[-1].strip() or gc.PROMPT.match(lines[-1])):
            lines.pop()                                          # drop the final prompt
        with open(os.path.join(out, f"{name}.cfg"), "w") as f:
            f.write("\n".join(lines) + "\n")
        s.close()
        print(f"{name}: {len(lines)} lines -> {out}/{name}.cfg")


if __name__ == "__main__":
    main()
