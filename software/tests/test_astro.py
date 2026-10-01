from datetime import datetime, timedelta, timezone

import pytest

from lsr.astro import Observer, load_tle_text, sun_position, sun_declination, maidenhead, C_KMS

MAD = Observer(40.4168, -3.7038, 650)


def test_tle_parsing(tle_text):
    s = load_tle_text(tle_text)
    assert s['ISS (ZARYA)'].norad == 25544 and s['25544'] is s['ISS (ZARYA)']
    assert s['SO-50'].epoch.date().isoformat() == '2026-10-01'


def test_look_angles_against_skyfield(tle_text):
    sk = pytest.importorskip('skyfield.api')
    sat = load_tle_text(tle_text)['ISS (ZARYA)']
    ts = sk.load.timescale()
    es = sk.EarthSatellite(sat.line1, sat.line2, 'ISS', ts)
    top = sk.wgs84.latlon(MAD.lat, MAD.lon, MAD.alt)
    for k in range(0, 86400, 900):
        t = datetime(2026, 10, 1, tzinfo=timezone.utc) + timedelta(seconds=k)
        a = sat.look(MAD, t)
        d = (es - top).at(ts.from_datetime(t))
        alt, az, _ = d.altaz()
        rr = d.frame_latlon_and_rates(top)[5].km_per_s
        assert abs(a.el - alt.degrees) < 0.01
        if alt.degrees > -20:
            assert abs((a.az - az.degrees + 180) % 360 - 180) < 0.01
        assert abs(a.range_rate - rr) < 0.002            # < 3 Hz error at 435 MHz


def test_doppler_signs(tle_text):
    sat = load_tle_text(tle_text)['ISS (ZARYA)']
    lk = sat.look(MAD, datetime(2026, 10, 1, tzinfo=timezone.utc))
    f = 435e6
    assert lk.doppler(f) == pytest.approx(f * (1 - lk.range_rate / C_KMS))
    assert (lk.uplink(f) - f) * (f - lk.doppler(f)) > 0          # uplink and downlink corrections opposite
    assert abs(lk.range_rate) < 8.0


def test_sun_declination_seasons():
    assert abs(sun_declination(datetime(2026, 3, 20, 14, 46, tzinfo=timezone.utc))) < 0.05   # March equinox 2026
    assert sun_declination(datetime(2026, 6, 21, 8, 24, tzinfo=timezone.utc)) == pytest.approx(23.44, abs=0.02)


def test_sun_noon_elevation():
    # at local solar noon on the equinox the Sun is at 90 - latitude, due south
    o = Observer(40.0, 0.0, 0)
    pos = [sun_position(o, datetime(2026, 3, 20, 11, 0, tzinfo=timezone.utc) + timedelta(minutes=m), refraction=False)
           for m in range(0, 120)]
    az, el = max(pos, key=lambda p: p[1])
    assert el == pytest.approx(50.0, abs=0.1) and az == pytest.approx(180.0, abs=1.0)


def test_maidenhead():
    assert maidenhead(40.4168, -3.7038) == 'IN80dk'      # Madrid
    assert maidenhead(-34.6037, -58.3816)[:4] == 'GF05'  # Buenos Aires
