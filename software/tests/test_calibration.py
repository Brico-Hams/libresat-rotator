"""Auto-calibration with synthetic data: level, compass maths, magnetometer fit, sun scan/mark, backlash, persistence."""
import math
from datetime import datetime, timedelta, timezone

from lsr import calibration as cal
from lsr.astro import Observer
from lsr.pointing import PointingModel
from lsr.rotator import SimRotator

OBS = Observer(40.4168, -3.7038, 650.0)
NOON = datetime(2026, 6, 21, 11, 0, tzinfo=timezone.utc)
NOSLEEP = lambda s: None


def accel(tn, te):
    tn, te = math.radians(tn), math.radians(te)
    return (-math.sin(tn), -math.cos(tn) * math.sin(te), math.cos(tn) * math.cos(te))


def test_level_recovers_tilt_and_flags():
    r = cal.calibrate_level(lambda: accel(0.3, -0.2), n=5, delay=0, sleep=NOSLEEP)
    assert r['valid'] and r['ok']
    assert abs(r['tilt_n'] - 0.3) < 0.01 and abs(r['tilt_e'] + 0.2) < 0.01
    r = cal.calibrate_level(lambda: accel(1.2, 0.0), n=5, delay=0, sleep=NOSLEEP)
    assert r['valid'] and not r['ok'] and r['total'] > 1.0
    r = cal.calibrate_level(lambda: accel(1.2, 0.0), n=5, delay=0, sleep=NOSLEEP, threshold=2.0)
    assert r['ok']
    assert not cal.calibrate_level(lambda: (0.0, 0.0, 0.0), n=3, delay=0, sleep=NOSLEEP)['valid']


def test_tilt_compensated_heading():
    h = 75.0
    xh0, yh0, zw = math.cos(math.radians(h)), -math.sin(math.radians(h)), 0.8
    assert abs(cal.tilt_compensated_heading((xh0, yh0, zw), 0, 0) - h) < 1e-6
    p = math.radians(10)
    body = (xh0 * math.cos(p) - zw * math.sin(p), yh0, xh0 * math.sin(p) + zw * math.cos(p))
    assert abs(cal.tilt_compensated_heading(body, 0, 10) - h) < 1e-6
    r = math.radians(-8)
    body = (xh0, yh0 * math.cos(r) + zw * math.sin(r), -yh0 * math.sin(r) + zw * math.cos(r))
    assert abs(cal.tilt_compensated_heading(body, -8, 0) - h) < 1e-6


def test_compass_without_magnetometer_is_skipped():
    r = cal.calibrate_compass(None, None, 0.0)
    assert r['skipped'] and not r['valid'] and 'no magnetometer' in r['status']


def test_compass_true_north_offset_includes_declination():
    h, decl = 30.0, 2.0
    m = (math.cos(math.radians(h)), -math.sin(math.radians(h)), 0.5)
    r = cal.calibrate_compass(lambda: m, lambda: (0.0, 0.0, 1.0), decl, n=20, delay=0, sleep=NOSLEEP)
    assert r['valid'] and abs(r['az_off'] - 32.0) < 0.01


def sphere(c, radii, n=200):
    pts = []
    for i in range(n):
        z = 1 - 2 * (i + 0.5) / n
        r = math.sqrt(1 - z * z)
        th = i * math.pi * (3 - math.sqrt(5))
        pts.append((c[0] + radii[0] * r * math.cos(th), c[1] + radii[1] * r * math.sin(th), c[2] + radii[2] * z))
    return pts


def test_magcal_hard_and_soft_iron():
    c = (10.0, -5.0, 20.0)
    mc = cal.MagCal()
    for s in sphere(c, (40, 40, 40)):
        mc.add(s)
    mc.fit_minmax()
    assert all(abs(a - b) < 1.0 for a, b in zip(mc.offset, c))
    mc = cal.MagCal()
    for s in sphere(c, (40, 30, 50)):
        mc.add(s)
    mc.fit_ellipsoid()
    assert all(abs(a - b) < 0.1 for a, b in zip(mc.offset, c))
    norms = [math.sqrt(sum(v * v for v in mc.apply(s))) for s in sphere(c, (40, 30, 50), 20)]
    assert max(norms) - min(norms) < 0.5


def test_lowpass_alpha():
    lp = cal.LowPass(0.02)
    lp([0.0])
    assert abs(lp([100.0])[0] - 2.0) < 1e-9


def test_sun_scan_finds_injected_offsets():
    truth = PointingModel(dict(az_off=1.7, el_off=-0.9))
    now = lambda: NOON
    world = cal.SimSunWorld(OBS, truth, now)
    r = cal.sun_scan(world.move, world.read, OBS, now, PointingModel())
    assert r['valid'] and abs(r['az_off'] - 1.7) < 0.05 and abs(r['el_off'] + 0.9) < 0.05


def test_sun_scan_with_noise_and_sun_drift():
    truth = PointingModel(dict(az_off=-2.2, el_off=1.1))
    clk = [NOON]
    now = lambda: clk[0]
    world = cal.SimSunWorld(OBS, truth, now, noise=0.005)

    def move(a, e):
        clk[0] += timedelta(seconds=2)               # the Sun drifts 0.25 deg/min while the raster runs
        world.move(a, e)
    r = cal.sun_scan(move, world.read, OBS, now, PointingModel())
    assert r['valid'] and abs(r['az_off'] + 2.2) < 0.05 and abs(r['el_off'] - 1.1) < 0.05


def test_sun_scan_without_sun_reports_failure():
    r = cal.sun_scan(lambda a, e: None, lambda: 0.1, OBS, lambda: NOON)
    assert not r['valid']


def test_sun_mark_manual():
    sa, se = cal.sun_sky(OBS, NOON)
    r = cal.sun_mark(OBS, NOON, sa - 1.7, se + 0.9)
    assert r['valid'] and abs(r['az_off'] - 1.7) < 0.01 and abs(r['el_off'] + 0.9) < 0.01
    night = cal.sun_mark(OBS, datetime(2026, 6, 21, 1, 0, tzinfo=timezone.utc), 0.0, 0.0)
    assert not night['valid']


def test_backlash_measure_from_both_directions():
    st = dict(p=0.0, d=1, out=0.0)
    b = 0.6

    def move(p):
        st['d'] = 1 if p > st['p'] else (-1 if p < st['p'] else st['d'])
        st['p'] = p
        st['out'] = p - st['d'] * b / 2
    assert abs(cal.measure_backlash(move, lambda: st['out'], 50.0) - b) < 1e-9


class Clock:
    def __init__(self): self.t = 0.0
    def __call__(self): return self.t
    def sleep(self, s): self.t += s


def test_calibrate_index_encoder_method_on_sim():
    clk = Clock()
    rot = SimRotator(clock=clk, backlash=(0.4, 0.3))
    r = cal.calibrate_index(rot, clock=clk, sleep=clk.sleep)
    assert r['valid'], r
    assert abs(r['backlash_az'] - 0.4) < 0.05 and abs(r['backlash_el'] - 0.3) < 0.05


def test_validity_and_apply(cfg):
    cal.save_result(cfg, 'level', cal.calibrate_level(lambda: accel(0.3, -0.2), n=3, delay=0, sleep=NOSLEEP))
    cal.save_result(cfg, 'compass', dict(valid=True, az_off=5.0))
    p = cal.apply_to_pointing(cfg)['params']
    assert abs(p['tilt_n'] - 0.3) < 0.01 and p['az_off'] == 5.0
    cal.save_result(cfg, 'sun', dict(valid=True, az_off=1.0, el_off=-0.5))
    p = cal.apply_to_pointing(cfg)['params']
    assert p['az_off'] == 1.0 and p['el_off'] == -0.5          # the Sun beats the compass
    cal.save_result(cfg, 'sun', dict(valid=True, az_off=float('nan'), el_off=0.0))
    assert not cal.is_valid(cfg, 'sun')
    cal.save_result(cfg, 'index', dict(valid=False, backlash_az=0.3, backlash_el=0.3))
    assert not cal.is_valid(cfg, 'index') and cal.is_valid(cfg, 'compass')
    assert [r['step'] for r in cal.summary(cfg)] == list(cal.STEPS)


def test_station_and_time_falls_back_to_config(cfg):
    obs, when, src = cal.station_and_time(None, cfg)
    assert src == 'config' and abs(obs.lat - 40.4168) < 1e-9
