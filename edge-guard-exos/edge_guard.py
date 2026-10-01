# edge_guard.py - called by the UPM profile edge_guard:  load script edge_guard.py $p $r
# argv[1] = port, argv[2] = name of the policy entry (rule) that matched the frame.
# Disables the port and writes a message to the switch log.
import sys, exsh
port, rule = sys.argv[1], sys.argv[2]
try:
    exsh.clicmd('disable port %s' % port)
    exsh.clicmd('create log message "edge_guard.py: %s on port %s, port disabled"' % (rule, port))
except RuntimeError:
    exsh.clicmd('create log message "edge_guard.py: error while disabling port %s"' % port)
