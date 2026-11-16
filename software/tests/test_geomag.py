"""Geomagnetic declination: algorithm checks with a synthetic dipole, NOAA reference values when WMM2025.COF is installed."""
from datetime import datetime, timezone

import pytest

from lsr import geomag

DIPOLE = """2025.0 WMM-2025 11/13/2024
 1 0 -30000.0 0.0 -10.0 0.0
 1 1 0.0 0.0 0.0 0.0
999999999999999999999999999999999999999999999999
999999999999999999999999999999999999999999999999
"""


def test_parse_and_axial_dipole():
    m = geomag.WMM.parse(DIPOLE)
    assert m.epoch == 2025.0 and m.nmax == 1
    for lat, lon in ((0, 0), (45, -3.7), (60, 120), (-35, 151)):
        f = m.field(lat, lon, 0.0, 2025.0)
        assert abs(f['decl']) < 1e-6                  # a pure g10 field points to the geographic pole
    assert abs(m.field(60, 10, 0.0, 2025.0)['incl'] - 74.0) < 0.5    # tan I = 2 tan(lat)
    assert m.field(60, 10, 0.0, 2030.0)['f'] > m.field(60, 10, 0.0, 2025.0)['f']    # secular variation g10dot < 0 adds


def test_parse_rejects_garbage():
    with pytest.raises(ValueError):
        geomag.WMM.parse('nothing here')


def test_decimal_year():
    assert abs(geomag.decimal_year(datetime(2026, 1, 1, tzinfo=timezone.utc)) - 2026.0) < 1e-9
    assert abs(geomag.decimal_year(datetime(2026, 7, 2, 12, tzinfo=timezone.utc)) - 2026.5) < 0.01


def test_declination_without_file_is_none(monkeypatch, tmp_path):
    monkeypatch.setattr(geomag, 'COF_FILE', tmp_path / 'missing.COF')
    monkeypatch.setattr(geomag, '_cache', {})
    assert geomag.declination(40.0, -3.7) is None


@pytest.mark.skipif(not geomag.available(), reason='software/lsr/data/WMM2025.COF (official NOAA file) not installed yet')
def test_noaa_reference_declinations():
    t = datetime(2026, 1, 1, tzinfo=timezone.utc)
    for lat, lon, lo, hi in ((47.6, -122.3, 14.0, 16.5), (-33.9, 151.2, 11.5, 13.5), (40.4, -3.7, -2.0, 1.0)):
        d = geomag.declination(lat, lon, 0.0, t)
        assert lo <= d <= hi, (lat, lon, d)
