from datetime import datetime, timedelta, timezone

from lsr.astro import Observer, load_tle_text
import math

from lsr.passes import find_passes, plan_pass, Limits


def sky_sep(az, el, saz, sel):
    """Angle between the antenna (joint az/el, el may exceed 90) and the satellite."""
    def vec(a, e):
        a, e = math.radians(a), math.radians(e)
        return (math.cos(e) * math.sin(a), math.cos(e) * math.cos(a), math.sin(e))
    u, v = vec(az, el), vec(saz, sel)
    return math.degrees(math.acos(max(-1.0, min(1.0, sum(x * y for x, y in zip(u, v))))))

MAD = Observer(40.4168, -3.7038, 650)
T0 = datetime(2026, 10, 1, tzinfo=timezone.utc)


def _passes(tle_text, name='ISS (ZARYA)', hours=48):
    return find_passes(load_tle_text(tle_text)[name], MAD, T0, hours, 0.0, 0.0)


def test_find_passes(tle_text):
    ps = _passes(tle_text)
    assert len(ps) >= 4
    for p in ps:
        assert p.aos < p.tca < p.los
        assert 0 <= p.max_el <= 90
        assert 60 < p.duration < 900
        assert abs(p.track[0][2]) < 0.6 and abs(p.track[-1][2]) < 0.6     # starts/ends on the horizon


def test_plans_respect_limits(tle_text):
    lim = Limits(0, 450, 0, 180, 20, 15)
    for name in ('ISS (ZARYA)', 'SO-50', 'RS-44', 'AO-91'):
        for p in _passes(tle_text, name):
            pl = plan_pass(p, lim, current_az=0.0)
            assert pl is not None and pl.feasible
            azs = [a for _, a, _ in pl.points]; els = [e for _, _, e in pl.points]
            assert min(azs) >= 0 and max(azs) <= 450 and min(els) >= 0 and max(els) <= 180
            # the commanded direction is the satellite direction (flip: same line of sight, <= 5 deg)
            for (t, az, el), (_, saz, sel) in zip(pl.points, p.track):
                assert sky_sep(az, el, saz, max(0.0, sel)) <= (5.0 if pl.mode != 'normal' else 1e-6) + 1e-6


def test_high_pass_uses_flip(tle_text):
    ps = [p for n in ('ISS (ZARYA)', 'SO-50', 'AO-91', 'RS-44') for p in _passes(tle_text, n, 96)]
    high = max(ps, key=lambda p: p.max_el)
    assert high.max_el > 70
    lim = Limits(0, 450, 0, 180, 20, 15)
    normal = plan_pass(high, lim, 0.0, allow_flip=False)
    best = plan_pass(high, lim, 0.0, allow_flip=True)
    assert best.feasible and best.peak_az_rate <= 0.8 * lim.vmax_az + 1e-6 and best.max_error < 1.0
    if not normal.feasible or normal.peak_az_rate > 0.8 * lim.vmax_az:
        assert best.mode in ('flip', 'flip-rev')


def test_plan_interpolation(tle_text):
    p = _passes(tle_text)[0]
    pl = plan_pass(p, Limits(), 0.0)
    t_mid = p.aos + (p.los - p.aos) / 2
    az, el = pl.at(t_mid)
    assert pl.at(p.aos - timedelta(minutes=5)) == (pl.points[0][1], pl.points[0][2])
    assert 0 <= el <= 180


def test_anti_windup_unwinds_cable():
    from lsr.passes import Pass
    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    track = [(t0 + timedelta(seconds=10 * i), 10.0 + i, 30.0) for i in range(51)]       # az 10 -> 60 deg
    p = Pass('X', track[0][0], track[25][0], track[-1][0], 30.0, 10.0, 60.0, track)
    kw = dict(az_min=-360.0, az_max=360.0, el_min=-30.0, el_max=150.0, vmax_az=12.0, vmax_el=12.0)
    plain = plan_pass(p, Limits(**kw), current_az=-250.0)
    unwound = plan_pass(p, Limits(**kw, anti_windup=True), current_az=-250.0)
    assert plain.wrap == -360.0 and unwound.wrap == 0.0         # shortest slew vs ends near mid-range
    assert unwound.feasible and abs(unwound.points[-1][1]) < abs(plain.points[-1][1])


def test_no_flip_when_el_limited(tle_text):
    p = max(_passes(tle_text, 'SO-50', 96), key=lambda p: p.max_el)
    pl = plan_pass(p, Limits(0, 450, 0, 90, 20, 15), 0.0)
    assert pl.mode == 'normal' and max(e for _, _, e in pl.points) <= 90
