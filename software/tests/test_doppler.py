import pytest

from lsr.astro import C_KMS
from lsr.doppler import DopplerEngine
from lsr.rigs import DummyRig
from lsr.satdb import Transponder, SatDB

CFG = {'fm_step_hz': 100, 'ssb_step_hz': 10, 'knob_follow': True, 'knob_threshold_hz': 30}


def test_fm_doppler():
    tp = Transponder('FM', 'fm', up=145.850, down=436.795, ctcss=67.0)
    rig = DummyRig()
    e = DopplerEngine(tp, rig, CFG)
    st = e.tick(-6.5)                                  # approaching: received higher
    assert st.rx == pytest.approx(436.795e6 * (1 + 6.5 / C_KMS))
    assert st.tx == pytest.approx(145.850e6 / (1 + 6.5 / C_KMS))
    assert rig.rx % 100 == 0 and abs(rig.rx - st.rx) <= 50
    assert rig.tone == 67.0 and rig.modes == ('FM', 'FM')
    n = len(rig.log); e.tick(-6.5 + 0.001)             # change < step: no CAT traffic
    assert len(rig.log) == n


def test_linear_inverting_knob_follow():
    tp = Transponder('RS-44', 'linear', up_low=145.935, up_high=145.995, down_low=435.610, down_high=435.670,
                     invert=True, up_mode='LSB', down_mode='USB')
    rig = DummyRig()
    e = DopplerEngine(tp, rig, CFG)
    st = e.tick(0.0)
    assert st.down_sat == pytest.approx(435.640e6) and st.tx == pytest.approx(145.965e6)
    rig.knob = rig.rx + 5000                           # operator tunes the downlink 5 kHz up
    st = e.tick(0.0)
    assert st.down_sat == pytest.approx(435.645e6, abs=1)
    assert st.tx == pytest.approx(145.960e6, abs=1)    # inverting: uplink goes 5 kHz down
    st = e.tick(-5.0)                                  # Doppler moves, satellite-frame stays
    assert st.down_sat == pytest.approx(435.645e6, abs=1)
    assert st.rx == pytest.approx(435.645e6 * (1 + 5 / C_KMS), abs=5)


def test_linear_non_inverting_mapping():
    tp = Transponder('A', 'linear', up_low=145.850, up_high=145.950, down_low=29.400, down_high=29.500, invert=False)
    assert tp.up_for_down(29.450e6) == pytest.approx(145.900e6)
    assert tp.clamp_down(30e6) == pytest.approx(29.5e6)


def test_satdb_loads():
    db = SatDB()
    assert db.get(25544).name == 'ISS'
    rs44 = db.get(44909).transponders[0]
    assert rs44.type == 'linear' and rs44.invert
