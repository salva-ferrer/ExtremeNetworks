# edge_guard.py - called by the UPM profile edge_guard:  load script edge_guard.py $s $p $r
# argv[1] = slot, argv[2] = port (from "packet from <slot>:<port>" in the ACL log line),
# argv[3] = name of the policy entry (rule) that matched the frame.
# Disables the port and writes a message to the switch log.
# Stack: the port is <slot>:<port>. Standalone: the log still says 1:<port>, but the CLI only
# accepts <port>, so with slot 1 it falls back to the bare port number.
import sys, exsh
slot, port, rule = sys.argv[1], sys.argv[2], sys.argv[3]
for target in ['%s:%s' % (slot, port)] + ([port] if slot == '1' else []):
    try:
        exsh.clicmd('disable port %s' % target)
    except RuntimeError:
        continue
    exsh.clicmd('create log message "edge_guard.py: %s on port %s, port disabled"' % (rule, target))
    break
else:
    exsh.clicmd('create log message "edge_guard.py: error while disabling port %s:%s"' % (slot, port))
