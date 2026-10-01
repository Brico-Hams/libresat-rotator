from lsr.rotator import SimRotator
from lsr.rotctld import RotctldServer


def test_rotctld_protocol():
    rot = SimRotator()
    s = RotctldServer(rot, None, 0, 360, 0, 180)
    assert s.execute('P 123.4 45.6') == 'RPRT 0\n'
    az, el = map(float, s.execute('p').split())
    assert 0 <= az < 360 and 0 <= el <= 180
    assert s.execute('\\set_pos 10 20') == 'RPRT 0\n'
    ext = s.execute('+\\get_pos')
    assert ext.startswith('get_pos:') and ext.endswith('RPRT 0\n')
    ds = s.execute('\\dump_state').splitlines()
    assert ds[0] == '1' and ds[-1] == 'done' and 'max_el=180.000000' in ds
    assert s.execute('S') == 'RPRT 0\n'
    assert s.execute('P abc') == 'RPRT -1\n'
    assert s.execute('Z') == 'RPRT -11\n'
    assert s.execute('q') is None
    assert s.execute('P -10 5') == 'RPRT 0\n' and rot.tgt[0] == 350
