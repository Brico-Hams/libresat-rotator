import pytest

from lsr import config
from lsr.rotator import Rotator, make_rotator
from lsr.rotctld import RotctldServer


def load(tmp_path, text=None):
    p = tmp_path / 'c.yaml'
    if text is not None:
        p.write_text(text)
    return config.load(str(p))


def test_lsr1_defaults_unchanged(tmp_path):
    c = load(tmp_path)
    assert c['model'] == 'lsr1'
    assert c['station']['name'] == 'LSR-1'
    assert c['limits'] == {'az_min': 0.0, 'az_max': 450.0, 'el_min': 0.0, 'el_max': 180.0,
                           'vmax_az': 20.0, 'vmax_el': 15.0, 'allow_flip': True}
    assert load(tmp_path, 'model: lsr1\n')['limits'] == c['limits']


def test_lsr2_profile(tmp_path):
    c = load(tmp_path, 'model: lsr2\n')
    assert c['model'] == 'lsr2' and c['station']['name'] == 'LSR-2'
    l = c['limits']
    assert (l['az_min'], l['az_max'], l['el_min'], l['el_max']) == (-360.0, 360.0, -30.0, 150.0)
    assert l['vmax_az'] == l['vmax_el'] == 12.0 and l['allow_flip'] is False
    assert c['rotator']['baud'] == 9600 and l['anti_windup'] is False      # EasyComm II default of SARCTrac Mk5


def test_yaml_overrides_profile_and_rejects_unknown(tmp_path):
    c = load(tmp_path, 'model: lsr2\nstation: {name: Roof}\nlimits: {vmax_az: 8}\n')
    assert c['station']['name'] == 'Roof' and c['limits']['vmax_az'] == 8 and c['limits']['el_min'] == -30.0
    with pytest.raises(ValueError):
        load(tmp_path, 'model: lsr9\n')


@pytest.mark.parametrize('model,name', [('lsr1', 'LSR-1'), ('lsr2', 'LSR-2')])
def test_rotctld_model_name(tmp_path, model, name):
    c = load(tmp_path, f'model: {model}\nrotator: {{simulate: true}}\n')
    srv = RotctldServer(make_rotator(c))
    assert f'Model name: {name}' in srv.execute('\\dump_caps')
    assert f'LibreSat Rotator {name} ' in srv.execute('_')


def test_sim_respects_lsr2_el_range(tmp_path):
    rot = make_rotator(load(tmp_path, 'model: lsr2\nrotator: {simulate: true}\n'))
    rot.set_pos(10, -45)
    assert rot.tgt[1] == -30.0
    rot.set_pos(10, 170)
    assert rot.tgt[1] == 150.0
    rot.set_abs(-400, 10)
    assert rot.tgt[0] == -360.0


def test_lsr2_wire_azimuth_mapping(fake_serial):
    port = fake_serial(lambda b: b'AZ300.0 EL10.0\r\n' if b.startswith(b'AZ EL') else b'')
    r = Rotator(serial_factory=lambda: port, model='lsr2')
    r.set_abs(-100, 10)
    assert b'XP 260.00 10.00' in port.written
    assert r.get_pos() == (-60.0, 10.0)
    p1 = fake_serial()
    Rotator(serial_factory=lambda: p1, model='lsr1').set_abs(400, 10)
    assert b'XP 400.00 10.00' in p1.written
