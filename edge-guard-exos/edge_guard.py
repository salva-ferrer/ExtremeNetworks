# edge_guard.py - edge guard for EXOS / Switch Engine. Two modes:
#
# 1) By hand: apply/remove the edge_guard policy on access ports.
#      run script edge_guard.py enable port <list>
#      run script edge_guard.py disable port <list>
#    <list>: commas, ranges or both, e.g. 1,3-5,8   (stack: 2:3, 2:1-4, 2:1-2:4)
#    enable  = configure access-list edge_guard ports <p> ingress    (skips ports that already have it)
#    disable = unconfigure access-list edge_guard ports <p> ingress  (only removes the policy; it does
#              not touch the port's admin state: "enable port <p>" recovers a guarded port)
#    Nothing is saved: run "save" afterwards.
#
# 2) UPM, called by the profile edge_guard:  load script edge_guard.py $s $p $r
#    argv[1] = slot, argv[2] = port (from "packet from <slot>:<port>" in the ACL log line),
#    argv[3] = name of the policy entry (rule) that matched the frame.
#    Disables the port and writes a message to the switch log.
#    Stack: the port is <slot>:<port>. Standalone: the log still says 1:<port>, but the CLI only
#    accepts <port>, so with slot 1 it falls back to the bare port number.
import sys, exsh

POLICY = 'edge_guard'
USAGE = ('usage: run script edge_guard.py enable|disable port <list>\n'
         '       <list>: commas, ranges or both, e.g. 1,3-5,8 (stack: 2:3, 2:1-4, 2:1-2:4)')


def log(msg):
    try:
        exsh.clicmd('create log message "%s"' % msg.replace('"', "'"))
    except RuntimeError:
        pass


def _port(tok):
    # '4' -> (None, 4) ; '2:4' -> (2, 4)
    parts = tok.split(':')
    if len(parts) > 2 or not all(x.isdigit() for x in parts) or 0 in [int(x) for x in parts]:
        raise ValueError('invalid port "%s"' % tok)
    return (None, int(parts[0])) if len(parts) == 1 else (int(parts[0]), int(parts[1]))


def _fmt(slot, port):
    return str(port) if slot is None else '%d:%d' % (slot, port)


def parse_ports(spec):
    """'1,3-5,8' / '2:1-4' / '2:1-2:4' -> ordered list of port strings, no duplicates."""
    result = []
    for tok in spec.split(','):
        tok = tok.strip()
        if not tok:
            raise ValueError('empty element in port list "%s"' % spec)
        if '-' in tok:
            a, b = tok.split('-', 1)
            slot_a, first = _port(a)
            slot_b, last = _port(b)
            if slot_b is None:
                slot_b = slot_a  # 2:1-4 means 2:1-2:4
            if slot_a != slot_b:
                raise ValueError('range "%s" crosses slots' % tok)
            if first > last:
                raise ValueError('reversed range "%s"' % tok)
            ports = [_fmt(slot_a, n) for n in range(first, last + 1)]
        else:
            ports = [_fmt(*_port(tok))]
        for p in ports:
            if p not in result:
                result.append(p)
    return result


def has_policy(port):
    # The output lists the policy's entries (edge_stp, edge_slpp, edge_snap), one port at a time.
    out = exsh.clicmd('show access-list port %s ingress' % port, capture=True) or ''
    return 'edge_' in out


def manage(action, ports):
    apply_ = action == 'enable'
    done, errors = [], []
    for p in ports:
        try:
            if has_policy(p) == apply_:
                print('%-8s %s' % (p, 'already applied' if apply_ else 'not applied'))
                continue
            exsh.clicmd('%s access-list %s ports %s ingress'
                        % ('configure' if apply_ else 'unconfigure', POLICY, p))
        except RuntimeError as e:
            errors.append(p)
            print('%-8s ERROR: %s' % (p, str(e).strip()))
            continue
        done.append(p)
        print('%-8s %s' % (p, 'applied' if apply_ else 'removed'))
    if done:
        log('edge_guard.py: policy %s ports %s'
            % ('applied to' if apply_ else 'removed from', ','.join(done)))
    if errors:
        print('errors on ports: %s' % ','.join(errors))
    if done:
        print('not saved: run "save" to keep the change after a reboot')


def upm(slot, port, rule):
    for target in ['%s:%s' % (slot, port)] + ([port] if slot == '1' else []):
        try:
            exsh.clicmd('disable port %s' % target)
        except RuntimeError:
            continue
        log('edge_guard.py: %s on port %s, port disabled' % (rule, target))
        return
    log('edge_guard.py: error while disabling port %s:%s' % (slot, port))


def main(argv):
    if len(argv) > 1 and argv[1] in ('enable', 'disable'):
        if len(argv) != 4 or argv[2] != 'port':
            print(USAGE)
            return
        try:
            ports = parse_ports(argv[3])
        except ValueError as e:
            print('error: %s\n%s' % (e, USAGE))
            return
        if argv[1] == 'enable':
            try:
                exsh.clicmd('check policy %s' % POLICY)
            except RuntimeError:
                print('error: %s.pol missing or invalid on the flash (check policy %s)' % (POLICY, POLICY))
                return
        manage(argv[1], ports)
    elif len(argv) == 4 and argv[1].isdigit() and argv[2].isdigit() and argv[3].startswith('edge_'):
        upm(argv[1], argv[2], argv[3])
    else:
        # Also the UPM case when a regsub in the profile did not match (the whole log text arrives
        # split into words): never guess a port, just leave a trace in the log.
        if len(argv) > 1:
            log('edge_guard.py: unexpected arguments, no port disabled')
        print(USAGE)


main(sys.argv)
