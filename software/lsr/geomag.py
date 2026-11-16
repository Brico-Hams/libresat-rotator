"""Magnetic declination from the NOAA/BGS World Magnetic Model (WMM2025, public domain).

Own implementation of the published WMM algorithm (spherical-harmonic synthesis of the main field with Schmidt
semi-normalised Legendre functions, geodetic -> geocentric conversion, linear secular variation). The coefficient table is
read from data/WMM2025.COF (official NOAA file format). Without the file `declination()` returns None and the caller falls
back to a manual declination (see data/WMM2025.COF.PLACEHOLDER).
"""
from __future__ import annotations

import math
from datetime import datetime, timezone
from pathlib import Path

DATA = Path(__file__).resolve().parent / 'data'
COF_FILE = DATA / 'WMM2025.COF'
A_REF = 6371.2                  # geomagnetic reference radius, km
WGS84_A = 6378.137
WGS84_F = 1 / 298.257223563


class WMM:
    def __init__(self, epoch: float, coeffs: dict[tuple[int, int], tuple[float, float, float, float]]):
        self.epoch, self.coeffs = epoch, coeffs
        self.nmax = max(n for n, _ in coeffs)

    @classmethod
    def parse(cls, text: str) -> 'WMM':
        """Parse an official .COF file: header 'epoch model date', then 'n m g h gdot hdot' lines, ended by 99999 lines."""
        epoch, coeffs = None, {}
        for line in text.splitlines():
            t = line.split()
            if not t or t[0].startswith('9999'):
                continue
            if epoch is None:
                epoch = float(t[0])
            elif len(t) >= 6:
                coeffs[(int(t[0]), int(t[1]))] = tuple(float(v) for v in t[2:6])
        if epoch is None or not coeffs:
            raise ValueError('not a WMM .COF file')
        return cls(epoch, coeffs)

    @classmethod
    def load(cls, path=None) -> 'WMM':
        return cls.parse(Path(path or COF_FILE).read_text())

    def field(self, lat: float, lon: float, alt_m: float = 0.0, year: float | None = None) -> dict:
        """Geodetic north/east/down components (nT) and D, I (deg) at the place and decimal year."""
        year = self.epoch if year is None else year
        dt = year - self.epoch
        lat = max(-89.999, min(89.999, lat))
        phi, lam = math.radians(lat), math.radians(lon)
        e2 = WGS84_F * (2 - WGS84_F)
        rn = WGS84_A / math.sqrt(1 - e2 * math.sin(phi) ** 2)
        h = alt_m / 1000.0
        p, z = (rn + h) * math.cos(phi), (rn * (1 - e2) + h) * math.sin(phi)
        r = math.hypot(p, z)
        lat_gc = math.asin(z / r)
        th = math.pi / 2 - lat_gc                       # geocentric colatitude
        st, ct = math.sin(th), math.cos(th)
        n_max = self.nmax
        P = [[0.0] * (n_max + 1) for _ in range(n_max + 1)]
        dP = [[0.0] * (n_max + 1) for _ in range(n_max + 1)]
        P[0][0] = 1.0
        for n in range(1, n_max + 1):
            for m in range(n + 1):
                if m == n:
                    k = 1.0 if n == 1 else math.sqrt(1.0 - 1.0 / (2 * n))
                    P[n][n] = k * st * P[n - 1][n - 1]
                    dP[n][n] = k * (st * dP[n - 1][n - 1] + ct * P[n - 1][n - 1])
                else:
                    d = math.sqrt(n * n - m * m)
                    q = math.sqrt((n - 1) ** 2 - m * m) if m <= n - 2 else 0.0
                    p2 = P[n - 2][m] if m <= n - 2 else 0.0
                    dp2 = dP[n - 2][m] if m <= n - 2 else 0.0
                    P[n][m] = ((2 * n - 1) * ct * P[n - 1][m] - q * p2) / d
                    dP[n][m] = ((2 * n - 1) * (ct * dP[n - 1][m] - st * P[n - 1][m]) - q * dp2) / d
        br = bt = bp = 0.0
        for (n, m), (g, hh, gd, hd) in self.coeffs.items():
            g, hh = g + gd * dt, hh + hd * dt
            ar = (A_REF / r) ** (n + 2)
            c, s = math.cos(m * lam), math.sin(m * lam)
            br += (n + 1) * ar * (g * c + hh * s) * P[n][m]
            bt -= ar * (g * c + hh * s) * dP[n][m]
            bp += ar * m * (g * s - hh * c) * P[n][m] / st
        x_gc, y, z_gc = -bt, bp, -br                    # north, east, down (geocentric)
        psi = phi - lat_gc
        x = x_gc * math.cos(psi) + z_gc * math.sin(psi)
        zd = -x_gc * math.sin(psi) + z_gc * math.cos(psi)
        hz = math.hypot(x, y)
        return dict(x=x, y=y, z=zd, h=hz, f=math.hypot(hz, zd),
                    decl=math.degrees(math.atan2(y, x)), incl=math.degrees(math.atan2(zd, hz)))


def decimal_year(t: datetime) -> float:
    t = t.astimezone(timezone.utc)
    y0 = datetime(t.year, 1, 1, tzinfo=timezone.utc)
    y1 = datetime(t.year + 1, 1, 1, tzinfo=timezone.utc)
    return t.year + (t - y0) / (y1 - y0)


def available() -> bool:
    return COF_FILE.exists()


_cache: dict = {}


def declination(lat: float, lon: float, alt_m: float = 0.0, when: datetime | None = None, model: WMM | None = None):
    """Magnetic declination in degrees (east positive) or None if no coefficient file is installed."""
    if model is None:
        if 'm' not in _cache:
            try:
                _cache['m'] = WMM.load()
            except (OSError, ValueError):
                _cache['m'] = None
        model = _cache['m']
        if model is None:
            return None
    when = when or datetime.now(timezone.utc)
    return model.field(lat, lon, alt_m, decimal_year(when))['decl']
