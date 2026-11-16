"""Pointing model: identity default, tilt sign, inverse, least-squares fit, backlash compensation, CSV."""
import math

from lsr.pointing import BacklashComp, Pointing, PointingModel, Point, load_points, save_points, wrap180
from lsr.rotator import SimRotator, make_rotator

TRUTH = dict(az_off=2.5, el_off=-0.8, tilt_n=0.4, tilt_e=-0.3, nonperp=0.15, collim=0.1, ecc_sin=0.05, ecc_cos=-0.04)


def test_default_is_identity():
    m = PointingModel()
    assert m.to_sky(123.4, 56.7) == (123.4, 56.7)
    assert m.to_mount(123.4, 56.7) == (123.4, 56.7)


def test_disabled_config_does_not_wrap(cfg):
    assert isinstance(make_rotator(cfg), SimRotator)


def test_offsets_and_roundtrip():
    m = PointingModel(TRUTH)
    sa, se = m.to_sky(100.0, 30.0)
    assert abs(sa - 102.5) < 1.0 and abs(se - 29.2) < 0.5
    for az, el in ((10, 5), (200, 45), (359, 80), (90, 20)):
        a, e = m.to_mount(*m.to_sky(az, el))
        assert abs(wrap180(a - az)) < 1e-6 and abs(e - el) < 1e-6


def test_tilt_towards_north_lowers_elevation_in_the_north():
    m = PointingModel(dict(tilt_n=1.0))
    assert abs(m.to_sky(0.0, 30.0)[1] - 29.0) < 0.01
    assert abs(m.to_sky(180.0, 30.0)[1] - 31.0) < 0.01
    assert abs(m.to_sky(90.0, 30.0)[1] - 30.0) < 0.01


def test_refraction_roundtrip_raises_low_targets():
    m = PointingModel(refraction=True)
    assert m.to_mount(0.0, 2.0)[1] > 2.0              # the apparent position is higher: point above the geometric target
    a, e = m.to_mount(*m.to_sky(0.0, 5.0))
    assert abs(e - 5.0) < 1e-6


def test_fit_recovers_injected_parameters():
    truth = PointingModel(TRUTH)
    pts = []
    for az in range(0, 360, 30):
        for el in (15, 45, 75):
            sa, se = truth.to_sky(az, el)
            pts.append(Point(sa, se, az, el))
    m = PointingModel()
    res = m.fit(pts)
    assert res.rms < 0.02 and res.n == len(pts)
    for k, v in TRUTH.items():
        assert abs(res.params[k] - v) < 0.03, (k, res.params[k], v)


def test_fit_with_few_terms_and_noise_reports_rms():
    truth = PointingModel(dict(az_off=3.0, el_off=0.7))
    pts = [Point(*truth.to_sky(az, el), az, el) for az, el in ((10, 20), (100, 40), (200, 60), (300, 30), (50, 70))]
    res = PointingModel().fit(pts, ['az_off', 'el_off'])
    assert abs(res.params['az_off'] - 3.0) < 1e-3 and abs(res.params['el_off'] - 0.7) < 1e-3
    assert res.rms < 1e-3


def test_backlash_compensation():
    b = BacklashComp(0.4, 0.0)
    assert b.command(0, 10.0) == 10.0
    assert abs(b.command(0, 20.0) - 20.2) < 1e-9 and abs(b.report(0, 20.2) - 20.0) < 1e-9
    assert abs(b.command(0, 15.0) - 14.8) < 1e-9 and abs(b.report(0, 14.8) - 15.0) < 1e-9
    assert b.command(1, 5.0) == 5.0 and b.command(1, 9.0) == 9.0      # zero backlash = identity


def test_pointing_runtime_inverse_and_invalid_params_fall_back():
    p = Pointing({'pointing': {'params': TRUTH}})
    ma, me = p.command(150.0, 40.0)
    ra, re_ = p.report(ma, me)
    assert abs(ra - 150.0) < 1e-6 and abs(re_ - 40.0) < 1e-6
    bad = Pointing({'pointing': {'params': {'az_off': 500.0}}})
    assert bad.command(10.0, 20.0) == (10.0, 20.0)


def test_csv_roundtrip(tmp_path):
    f = tmp_path / 'p.csv'
    pts = [Point(10.5, 20.25, 8.0, 20.0, 1.0, 'sun'), Point(200.0, 45.0, 198.0, 45.5, 2.0, 'landmark')]
    save_points(str(f), pts)
    back = load_points(str(f))
    assert len(back) == 2 and back[1].note == 'landmark' and abs(back[0].sky_az - 10.5) < 1e-6 and back[1].weight == 2.0
