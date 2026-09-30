#!/usr/bin/env python3
"""Talk to the telnet console of a GNS3 node (Switch Engine/EXOS, Fabric Engine/VOSS,
docker containers...) from a script, without a telnet client.

Usage:
  gns3_console.py <GNS3_HOST> <port> cmd "show version" ["other command" ...]
  gns3_console.py <GNS3_HOST> <port> answer "y"          # reply to a y/N or wizard prompt
  gns3_console.py <GNS3_HOST> <port> answer "rwa" --until "Password: ?$"
                                                         # send, then wait for a given
                                                         # prompt (one step at a time)
  gns3_console.py <GNS3_HOST> <port> esc                 # ESC (leave live monitors)
  gns3_console.py <GNS3_HOST> <port> ctrl-c              # Ctrl-C
  gns3_console.py <GNS3_HOST> <port> vi-upload <file>    # paste a file into an already
                                                         # open vi (e.g. after
                                                         # "edit script x.py"), then :wq
Options:
  --wait S       max seconds to wait for the prompt after each command (default 15)
  --user U       login user if the console asks for one (default: $CONSOLE_USER or none)
  --password P   login password (default: $CONSOLE_PASS, empty if unset)
  --until REGEX  with "answer": wait until the last line matches REGEX instead of a
                 CLI prompt (login, password, "Re-enter the New password :" ...)
  --wizard       end lines with "\\r\\0" instead of the default "\\r" (EXOS wizard)

The console port of each node is in the API: GET /v2/projects/<p>/nodes/<n> -> "console".

Notes learned the hard way:
- telnetlib is gone from Python 3.13+, so plain sockets are used. GNS3 consoles accept a
  client that does not negotiate telnet options.
- Output is read until a prompt ("...# " or "...> ") shows up on its own line, or until
  --wait expires. Nothing is discarded, so long outputs ("show ports") are complete.
- EXOS first-boot wizard questions end with BEL (\\x07) and a "\\r\\n" counts as TWO
  answers. The default "\\r" is fine; --wizard ("\\r\\0") was also validated.
- Never send a command right after one that may raise an interactive prompt ("save",
  "enable ssh", "reboot") without checking the prompt came back: the next command
  would be swallowed as the answer. Use "answer" for the prompt.
- The console is shared: anyone attached to it (another user, the GNS3 GUI) sees
  everything typed here.
"""
import os
import re
import socket
import sys
import time

ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
CTRL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")
PROMPT = re.compile(r"^\*?\s*\S.{0,60}?[#>]\s*$")      # EXOS "X.3 #", VOSS "VSP:1#", "sw>"
LOGIN = re.compile(r"(login|username)\s*:\s*$", re.I)
PASSWD = re.compile(r"password\s*:\s*$", re.I)


def clean(text):
    return CTRL.sub("", ANSI.sub("", text))


def read_until(sock, pred, timeout):
    buf, deadline = "", time.time() + timeout
    sock.settimeout(0.3)
    while time.time() < deadline:
        try:
            chunk = sock.recv(4096)
            if not chunk:
                break
            buf += chunk.decode(errors="replace")
        except socket.timeout:
            pass
        if pred(clean(buf)):
            break
    return buf


def last_line(text):
    lines = [l for l in clean(text).replace("\r", "\n").split("\n") if l.strip()]
    return lines[-1] if lines else ""


def at_prompt(text):
    return bool(PROMPT.match(last_line(text)))


def login_if_needed(sock, eol, user, password, timeout):
    sock.sendall(eol)
    out = read_until(sock, lambda t: at_prompt(t) or LOGIN.search(last_line(t))
                     or PASSWD.search(last_line(t)), timeout)
    if LOGIN.search(last_line(out)) and user is not None:
        sock.sendall(user.encode() + eol)
        out += read_until(sock, lambda t: PASSWD.search(last_line(t)) or at_prompt(t), timeout)
    if PASSWD.search(last_line(out)):
        sock.sendall((password or "").encode() + eol)
        out += read_until(sock, at_prompt, timeout)
    return out


def main():
    args = sys.argv[1:]
    opts = {"--wait": "15", "--until": None, "--user": os.environ.get("CONSOLE_USER"),
            "--password": os.environ.get("CONSOLE_PASS", "")}
    wizard = "--wizard" in args
    if wizard:
        args.remove("--wizard")
    for k in list(opts):
        if k in args:
            i = args.index(k)
            opts[k] = args[i + 1]
            del args[i:i + 2]
    if len(args) < 3:
        print(__doc__)
        sys.exit(1)
    host, port, action, rest = args[0], int(args[1]), args[2], args[3:]
    wait = float(opts["--wait"])
    eol = b"\r\0" if wizard else b"\r"   # "\r\n" counts as TWO lines on EXOS and VOSS

    s = socket.create_connection((host, port), timeout=15)
    time.sleep(0.5)
    if action == "cmd":
        print(clean(login_if_needed(s, eol, opts["--user"], opts["--password"], wait)), end="")
        for c in rest:
            s.sendall(c.encode() + eol)
            print(clean(read_until(s, at_prompt, wait)), end="")
    elif action == "answer":
        s.sendall((rest[0] if rest else "").encode() + eol)
        until = re.compile(opts["--until"]) if opts["--until"] else None
        pred = (lambda t: until.search(last_line(t))) if until else at_prompt
        print(clean(read_until(s, pred, wait)), end="")
    elif action in ("esc", "ctrl-c"):
        s.sendall(b"\x1b" if action == "esc" else b"\x03")
        print(clean(read_until(s, at_prompt, 3)), end="")
    elif action == "vi-upload":
        for data, w in ((b"i", 1), (open(rest[0], "rb").read(), 3), (b"\x1b", 1), (b":wq\r\n", 2)):
            s.sendall(data)
            time.sleep(w)
        print(clean(read_until(s, at_prompt, wait)), end="")
    else:
        sys.exit(f"unknown action: {action}")
    print()
    s.close()


if __name__ == "__main__":
    main()
