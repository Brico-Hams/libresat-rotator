"""Closed-loop control on SimRotator: step loss, stall, deadband, soft limits, feed-forward, backlash trim, faults."""
import copy

from lsr.control import Supervisor
from lsr.rotator import CorrectedRotator, SimRotator


class Clock:
    def __init__(self): self.t = 1000.0
    def __call__(self): return self.t


def make(cfg, clk, control=None, pointing=None, backlash=(0.0, 0.0)):
    c = copy.deepcopy(cfg)
    c['control'].update(enabled=True, **(control or {}))
    if pointing:
        c['pointing'].update(enabled=True, **pointing)
    base = SimRotator(clock=clk, backlash=backlash)
    return CorrectedRotator(base, c, clk), base


def run(rot, clk, seconds, dt=0.25):
    for _ in range(int(seconds / dt)):
        clk.t += dt
        rot.status()


def kinds(rot):
    return [e['kind'] for e in rot.sup.events]


def test_step_loss_detected_and_resynced(cfg):
    clk = Clock()
    rot, base = make(cfg, clk)
    rot.set_pos(50.0, 45.0)
    run(rot, clk, 12)
    assert abs(base.pos[0] - 50.0) < 0.1 and not rot.sup.faults
    base.inject_step_loss(0, 2.0)                         # output now 2 deg behind the step count
    run(rot, clk, 3)
    assert 'step_loss' in kinds(rot) and not rot.sup.faults
    assert abs(base.pos[0] - 48.0) < 0.1                   # step count re-synced to the encoder
    assert abs(base.raw()['enc'][0] - base.pos[0]) < 0.05


def test_small_disagreement_is_ignored(cfg):
    clk = Clock()
    rot, base = make(cfg, clk)
    rot.set_pos(50.0, 45.0)
    run(rot, clk, 12)
    base.inject_step_loss(0, 0.3)
    run(rot, clk, 4)
    assert 'step_loss' not in kinds(rot)


def test_stall_stops_and_latches_fault(cfg):
    clk = Clock()
    rot, base = make(cfg, clk)
    base.stall(0, True)
    rot.set_pos(200.0, 90.0)
    run(rot, clk, 4)
    assert 'stall_az' in rot.sup.faults
    assert base.tgt[0] == base.pos[0] or abs(base.tgt[0] - base.pos[0]) < 1.0    # stopped
    tgt = list(base.tgt)
    rot.set_pos(10.0, 20.0)                               # ignored while faulted
    assert base.tgt == tgt
    assert rot.control_status()['state'] == 'fault'
    base.stall(0, False)
    rot.clear_faults()
    rot.set_pos(10.0, 20.0)
    assert base.tgt[1] == 20.0


def test_normal_motion_does_not_stall(cfg):
    clk = Clock()
    rot, base = make(cfg, clk)
    rot.set_pos(300.0, 30.0)
    run(rot, clk, 25)
    assert not rot.sup.faults and abs(base.pos[0] - 300.0) < 0.1


def test_deadband_suppresses_tiny_commands(cfg):
    clk = Clock()
    rot, base = make(cfg, clk, control=dict(deadband=0.1))
    rot.set_pos(100.0, 45.0)
    rot.set_pos(100.03, 45.02)
    assert base.tgt[0] == 100.0 and base.tgt[1] == 45.0
    rot.set_pos(100.2, 45.0)
    assert abs(base.tgt[0] - 100.2) < 1e-9


def test_soft_limits(cfg):
    clk = Clock()
    cfg = copy.deepcopy(cfg)
    cfg['limits']['el_max'] = 80.0
    rot, base = make(cfg, clk)
    rot.set_pos(10.0, 85.0)
    assert base.tgt[1] == 80.0 and rot.limit_hit
    assert rot.control_status()['limit_hit']


def test_feedforward_leads_the_target(cfg):
    clk = Clock()
    cfg = copy.deepcopy(cfg)
    cfg['tracking']['lead_s'] = 2.0
    rot, base = make(cfg, clk, control=dict(feedforward=True))
    for az in (10.0, 10.5, 11.0):
        rot.set_pos(az, 45.0)
        clk.t += 1.0
        base.status()
    assert abs(base.tgt[0] - (11.0 + 0.5 * 2.0)) < 0.05


def test_pointing_applied_transparently(cfg):
    clk = Clock()
    rot, base = make(cfg, clk, pointing=dict(params=dict(az_off=2.0)))
    rot.set_pos(100.0, 30.0)
    run(rot, clk, 15)
    assert abs(base.get_pos()[0] - 98.0) < 0.1 and abs(rot.get_pos()[0] - 100.0) < 0.1
    assert rot.status()['raw_az'] < rot.status()['az']


def test_backlash_compensation_with_encoder_trim(cfg):
    clk = Clock()
    rot, base = make(cfg, clk, pointing=dict(backlash_az=0.4), backlash=(0.4, 0.0))
    rot.set_pos(50.0, 45.0)
    run(rot, clk, 15)
    rot.set_pos(80.0, 45.0)
    run(rot, clk, 15)
    assert abs(base.raw()['enc'][0] - 80.0) < 0.06         # the output, not the motor, reaches the target


def test_supervisor_sensor_faults():
    s = Supervisor(dict(require_gps=True, require_encoders=True))
    acts = s.update(0.0, dict(gps=[0, 0, 0, 0, 0], err=0), None)
    assert ('stop',) in acts and 'gps' in s.faults and 'encoder' in s.faults
    assert s.snapshot()['state'] == 'fault'
    s.clear()
    assert s.snapshot()['state'] == 'ok'


def test_supervisor_ignores_missing_sensors_by_default():
    s = Supervisor()
    assert s.update(0.0, dict(err=0), None) == [] and not s.faults
