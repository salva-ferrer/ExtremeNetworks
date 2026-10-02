# Offline tests for edge_guard.py with a fake exsh module (run on a PC: python3 -m pytest tests/).
# They check the script's logic, not the EXOS CLI: the switch syntax is verified in the lab (RESULTS.md).
import os, runpy, sys, types
import pytest

SCRIPT = os.path.join(os.path.dirname(__file__), '..', 'edge_guard.py')


class FakeSwitch:
    """Records commands; ports in self.bound have the policy; commands in self.fail raise."""

    def __init__(self, bound=(), fail=()):
        self.bound, self.fail, self.cmds = set(bound), set(fail), []

    def clicmd(self, cmd, capture=False, **kw):
        self.cmds.append(cmd)
        if cmd in self.fail:
            raise RuntimeError('Error: %s' % cmd)
        w = cmd.split()
        if cmd.startswith('show access-list port'):
            return 'edge_stp\nedge_slpp\nedge_snap\n' if w[3] in self.bound else ''
        if w[0] == 'configure' and w[1] == 'access-list':
            self.bound.add(w[4])
        if w[0] == 'unconfigure' and w[1] == 'access-list':
            self.bound.discard(w[4])
        return ''


def run(argv, sw, monkeypatch):
    monkeypatch.setitem(sys.modules, 'exsh', types.SimpleNamespace(clicmd=sw.clicmd))
    monkeypatch.setattr(sys, 'argv', ['edge_guard.py'] + argv)
    return runpy.run_path(SCRIPT)


@pytest.fixture
def mod(monkeypatch):
    return run([], FakeSwitch(), monkeypatch)


@pytest.mark.parametrize('spec,expected', [
    ('1', ['1']),
    ('1,3-5,8', ['1', '3', '4', '5', '8']),
    ('3-5,4,1', ['3', '4', '5', '1']),
    (' 1 , 2 ', ['1', '2']),
    ('2:3', ['2:3']),
    ('2:1-3', ['2:1', '2:2', '2:3']),
    ('2:1-2:3,1:7', ['2:1', '2:2', '2:3', '1:7']),
])
def test_parse_ok(mod, spec, expected):
    assert mod['parse_ports'](spec) == expected


@pytest.mark.parametrize('spec', ['', '1,,2', '5-3', 'a', '1-', '-3', '1:2:3', '1:1-2:4', '0', '1-a', '2:0'])
def test_parse_bad(mod, spec):
    with pytest.raises(ValueError):
        mod['parse_ports'](spec)


def test_enable_idempotent(monkeypatch, capsys):
    sw = FakeSwitch(bound={'3'})
    run(['enable', 'port', '1,3-4'], sw, monkeypatch)
    assert 'configure access-list edge_guard ports 1 ingress' in sw.cmds
    assert 'configure access-list edge_guard ports 4 ingress' in sw.cmds
    assert 'configure access-list edge_guard ports 3 ingress' not in sw.cmds
    assert sw.bound == {'1', '3', '4'}
    out = capsys.readouterr().out
    assert 'already applied' in out and 'save' in out
    assert any(c.startswith('create log message') and '1,4' in c for c in sw.cmds)
    assert not any(c.startswith('save') for c in sw.cmds)


def test_disable_only_bound(monkeypatch, capsys):
    sw = FakeSwitch(bound={'1', '3', '4'})
    run(['disable', 'port', '3-5'], sw, monkeypatch)
    assert sw.bound == {'1'}
    assert 'unconfigure access-list edge_guard ports 5 ingress' not in sw.cmds
    assert 'not applied' in capsys.readouterr().out
    assert not any(c.startswith(('enable port', 'disable port')) for c in sw.cmds)


def test_error_on_one_port_continues(monkeypatch, capsys):
    sw = FakeSwitch(fail={'configure access-list edge_guard ports 2 ingress'})
    run(['enable', 'port', '1-3'], sw, monkeypatch)
    assert sw.bound == {'1', '3'}
    assert 'errors on ports: 2' in capsys.readouterr().out


def test_enable_without_policy_file(monkeypatch, capsys):
    sw = FakeSwitch(fail={'check policy edge_guard'})
    run(['enable', 'port', '1'], sw, monkeypatch)
    assert sw.cmds == ['check policy edge_guard']
    assert 'missing or invalid' in capsys.readouterr().out


@pytest.mark.parametrize('argv', [['enable'], ['enable', 'ports', '1'], ['enable', 'port', '5-3'],
                                  ['disable', 'port', '1', 'extra']])
def test_bad_usage_changes_nothing(monkeypatch, capsys, argv):
    sw = FakeSwitch()
    run(argv, sw, monkeypatch)
    assert sw.cmds == []
    assert 'usage' in capsys.readouterr().out


def test_upm_standalone_fallback(monkeypatch):
    sw = FakeSwitch(fail={'disable port 1:4'})
    run(['1', '4', 'edge_stp'], sw, monkeypatch)
    assert sw.cmds[:2] == ['disable port 1:4', 'disable port 4']
    assert 'edge_stp on port 4, port disabled' in sw.cmds[2]


def test_upm_stack(monkeypatch):
    sw = FakeSwitch()
    run(['2', '17', 'edge_snap'], sw, monkeypatch)
    assert sw.cmds[0] == 'disable port 2:17' and len(sw.cmds) == 2


def test_upm_slot2_no_fallback(monkeypatch):
    sw = FakeSwitch(fail={'disable port 2:17'})
    run(['2', '17', 'edge_snap'], sw, monkeypatch)
    assert 'disable port 17' not in sw.cmds
    assert 'error while disabling port 2:17' in sw.cmds[-1]


def test_upm_regsub_failed_disables_nothing(monkeypatch):
    # regsub did not match: the whole log line arrives split into words
    sw = FakeSwitch()
    run('IP Packet from 1:4 (vlanId=1) matches rule edge_stp: x'.split(), sw, monkeypatch)
    assert not any(c.startswith('disable port') for c in sw.cmds)
    assert 'unexpected arguments' in sw.cmds[-1]


def test_log_failure_is_swallowed(monkeypatch):
    sw = FakeSwitch()
    sw.fail = {'create log message "edge_guard.py: edge_stp on port 1:4, port disabled"'}
    run(['1', '4', 'edge_stp'], sw, monkeypatch)  # must not raise
    assert sw.cmds[0] == 'disable port 1:4'
