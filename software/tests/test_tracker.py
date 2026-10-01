from datetime import timedelta

import lsr.tracker as trk
from lsr.passes import find_passes
from lsr.rigs import DummyRig
from lsr.rotator import SimRotator
from lsr.satdb import SatDB
from lsr.tle import TleStore
from conftest import EPOCH


class Clock:
    def __init__(self, t): self.t = t
    def __call__(self): return self.t


def test_full_pass_simulation(cfg, monkeypatch):
    tles = TleStore(cfg); db = SatDB(); rig = DummyRig()
    rot = SimRotator(20, 15, 25, 0, 450, 0, 180)
    tr = trk.Tracker(cfg, rot, tles, db, rig)
    sat = tles.get('SO-50')
    p = find_passes(sat, tr.obs, EPOCH, 48, 0.0, 30.0)[0]
    clk = Clock(p.aos - timedelta(seconds=90))
    monkeypatch.setattr(trk, 'utcnow', clk)
    # SimRotator integrates in real time: drive its internal clock with the simulated one
    import lsr.rotator as rmod
    base = {'t0': clk.t}
    monkeypatch.setattr(rmod.time, 'monotonic', lambda: (clk.t - base['t0']).total_seconds())
    rot.t = 0.0
    tr.set_target('SO-50')
    modes, worst = set(), 0.0
    while clk.t < p.los + timedelta(seconds=10):
        tr.step()
        modes.add(tr.mode)
        if tr.mode == 'tracking' and tr.look.el > 1:
            az, el = rot.pos
            if el > 90:
                az, el = az + 180, 180 - el
            # pointing error on the sky (deg), small-angle
            import math
            d = math.degrees(math.acos(min(1, math.sin(math.radians(el)) * math.sin(math.radians(tr.look.el)) +
                     math.cos(math.radians(el)) * math.cos(math.radians(tr.look.el)) * math.cos(math.radians(az - tr.look.az)))))
            worst = max(worst, d)
        clk.t += timedelta(seconds=0.5)
    assert {'preposition', 'tracking'} <= modes
    assert tr.mode == 'idle'                         # auto_next off: stops after LOS
    assert worst < 3.0                               # well inside a 2-element beam
    assert any(e[0] == 'rx' for e in rig.log) and any(e[0] == 'tx' for e in rig.log)
    assert rig.tone == 67.0
