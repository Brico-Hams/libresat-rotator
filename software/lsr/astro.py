"""Orbit and sky geometry with no heavy dependencies (only `sgp4`).

- Satellite look angles: SGP4 (TEME) -> pseudo-Earth-fixed (GMST rotation) -> local ENU.
  Polar motion and nutation are ignored: the error is a few arc-seconds, far below any
  amateur antenna beamwidth. tests/test_astro.py checks against Skyfield when available.
- Sun: NOAA / Meeus low-precision algorithm (~0.01 deg), with Bennett refraction, used
  for the "sun alignment" calibration (true north without a compass).
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone

from sgp4.api import Satrec, WGS72, jday
from sgp4.propagation import gstime

C_KMS = 299792.458
OMEGA_E = 7.292115146706979e-5          # rad/s
WGS84_A = 6378.137
WGS84_F = 1 / 298.257223563


@dataclass(frozen=True)
class Observer:
    lat: float          # deg, north positive
    lon: float          # deg, east positive
    alt: float = 0.0    # m above the ellipsoid

    def ecef(self):
        lat, lon = math.radians(self.lat), math.radians(self.lon)
        e2 = WGS84_F * (2 - WGS84_F)
        n = WGS84_A / math.sqrt(1 - e2 * math.sin(lat) ** 2)
        h = self.alt / 1000.0
        return ((n + h) * math.cos(lat) * math.cos(lon),
                (n + h) * math.cos(lat) * math.sin(lon),
                (n * (1 - e2) + h) * math.sin(lat))


@dataclass
class Look:
    t: datetime
    az: float           # deg 0..360 from true north, clockwise
    el: float           # deg
    range_km: float
    range_rate: float   # km/s, positive = receding
    lat: float = 0.0    # sub-satellite point
    lon: float = 0.0
    alt_km: float = 0.0

    def doppler(self, f_hz: float) -> float:
        """Received frequency for a transmitter at f_hz (one-way, first order)."""
        return f_hz * (1.0 - self.range_rate / C_KMS)

    def uplink(self, f_hz: float) -> float:
        """Frequency to transmit so the satellite hears f_hz."""
        return f_hz / (1.0 - self.range_rate / C_KMS)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _jd(t: datetime):
    t = t.astimezone(timezone.utc)
    return jday(t.year, t.month, t.day, t.hour, t.minute, t.second + t.microsecond * 1e-6)


class Satellite:
    """One satellite from a TLE (name + two lines)."""

    def __init__(self, name: str, line1: str, line2: str):
        self.name = name.strip()
        self.line1, self.line2 = line1.rstrip(), line2.rstrip()
        self.rec = Satrec.twoline2rv(self.line1, self.line2, WGS72)
        self.norad = int(self.line1[2:7])

    @property
    def epoch(self) -> datetime:
        jd = self.rec.jdsatepoch + self.rec.jdsatepochF
        return datetime.fromtimestamp((jd - 2440587.5) * 86400.0, tz=timezone.utc)

    def teme(self, t: datetime):
        jd, fr = _jd(t)
        err, r, v = self.rec.sgp4(jd, fr)
        if err:
            raise ValueError(f'SGP4 error {err} for {self.name} at {t.isoformat()}')
        return r, v, jd + fr

    def look(self, obs: Observer, t: datetime) -> Look:
        r, v, jdut = self.teme(t)
        g = gstime(jdut)
        cg, sg = math.cos(g), math.sin(g)
        # TEME -> PEF (rotation about z by GMST)
        x, y, z = cg * r[0] + sg * r[1], -sg * r[0] + cg * r[1], r[2]
        vx = cg * v[0] + sg * v[1] + OMEGA_E * y
        vy = -sg * v[0] + cg * v[1] - OMEGA_E * x
        vz = v[2]
        ox, oy, oz = obs.ecef()
        dx, dy, dz = x - ox, y - oy, z - oz
        lat, lon = math.radians(obs.lat), math.radians(obs.lon)
        sl, cl, so, co = math.sin(lat), math.cos(lat), math.sin(lon), math.cos(lon)
        e = -so * dx + co * dy
        n = -sl * co * dx - sl * so * dy + cl * dz
        u = cl * co * dx + cl * so * dy + sl * dz
        rng = math.sqrt(dx * dx + dy * dy + dz * dz)
        az = math.degrees(math.atan2(e, n)) % 360.0
        el = math.degrees(math.asin(u / rng))
        rr = (dx * vx + dy * vy + dz * vz) / rng
        # sub-satellite point (spherical approximation is fine for display)
        p = math.sqrt(x * x + y * y)
        slat = math.degrees(math.atan2(z, p * (1 - WGS84_F) ** 2))
        slon = math.degrees(math.atan2(y, x))
        return Look(t, az, el, rng, rr, slat, slon, math.sqrt(x * x + y * y + z * z) - WGS84_A)


def load_tle_text(text: str) -> dict[str, Satellite]:
    """Parse 3-line (or 2-line) TLE text. Keys: upper-case names and NORAD numbers as str."""
    lines = [l.rstrip() for l in text.splitlines() if l.strip()]
    sats: dict[str, Satellite] = {}
    i = 0
    while i < len(lines) - 1:
        if lines[i].startswith('1 ') and lines[i + 1].startswith('2 '):
            name, l1, l2 = lines[i][2:7].strip(), lines[i], lines[i + 1]
            i += 2
        elif i + 2 < len(lines) and lines[i + 1].startswith('1 ') and lines[i + 2].startswith('2 '):
            name, l1, l2 = lines[i].lstrip('0 ').strip(), lines[i + 1], lines[i + 2]
            i += 3
        else:
            i += 1
            continue
        try:
            s = Satellite(name, l1, l2)
        except Exception:
            continue
        sats[s.name.upper()] = s
        sats[str(s.norad)] = s
    return sats


def refraction_deg(el_true: float) -> float:
    """Atmospheric refraction (deg, to add to the geometric elevation), Bennett formula; 0 below -1 deg."""
    if el_true <= -1.0:
        return 0.0
    return 1.02 / math.tan(math.radians(el_true + 10.3 / (el_true + 5.11))) / 60.0


# ---------------------------------------------------------------- the Sun
def sun_position(obs: Observer, t: datetime, refraction: bool = True):
    """Apparent (az, el) of the Sun in degrees."""
    jd, fr = _jd(t)
    jdt = jd + fr
    n = jdt - 2451545.0
    T = n / 36525.0
    L = (280.46646 + 36000.76983 * T + 0.0003032 * T * T) % 360.0
    M = math.radians((357.52911 + 35999.05029 * T - 0.0001537 * T * T) % 360.0)
    e = 0.016708634 - 0.000042037 * T
    C = ((1.914602 - 0.004817 * T - 0.000014 * T * T) * math.sin(M) + (0.019993 - 0.000101 * T) * math.sin(2 * M)
         + 0.000289 * math.sin(3 * M))
    true_long = L + C
    omega = math.radians(125.04 - 1934.136 * T)
    lam = math.radians(true_long - 0.00569 - 0.00478 * math.sin(omega))
    eps0 = 23 + (26 + (21.448 - T * (46.815 + T * (0.00059 - T * 0.001813))) / 60) / 60
    eps = math.radians(eps0 + 0.00256 * math.cos(omega))
    ra = math.atan2(math.cos(eps) * math.sin(lam), math.cos(lam))
    dec = math.asin(math.sin(eps) * math.sin(lam))
    gmst = gstime(jdt)                       # radians (mean sidereal time is enough here)
    ha = gmst + math.radians(obs.lon) - ra
    lat = math.radians(obs.lat)
    el = math.asin(math.sin(lat) * math.sin(dec) + math.cos(lat) * math.cos(dec) * math.cos(ha))
    az = math.atan2(-math.cos(dec) * math.sin(ha), math.sin(dec) * math.cos(lat) - math.cos(dec) * math.sin(lat) * math.cos(ha))
    el_d = math.degrees(el)
    if refraction and el_d > -1.0:
        el_d += refraction_deg(el_d)
    _ = e
    return math.degrees(az) % 360.0, el_d


def sun_declination(t: datetime) -> float:
    jd, fr = _jd(t)
    T = (jd + fr - 2451545.0) / 36525.0
    L = (280.46646 + 36000.76983 * T) % 360.0
    M = math.radians((357.52911 + 35999.05029 * T) % 360.0)
    C = (1.914602 - 0.004817 * T) * math.sin(M) + 0.019993 * math.sin(2 * M)
    omega = math.radians(125.04 - 1934.136 * T)
    lam = math.radians(L + C - 0.00569 - 0.00478 * math.sin(omega))
    eps = math.radians(23.439291 - 0.0130042 * T + 0.00256 * math.cos(omega))
    return math.degrees(math.asin(math.sin(eps) * math.sin(lam)))


def maidenhead(lat: float, lon: float, chars: int = 6) -> str:
    lon += 180.0; lat += 90.0
    s = chr(ord('A') + int(lon // 20)) + chr(ord('A') + int(lat // 10))
    s += str(int((lon % 20) // 2)) + str(int((lat % 10) // 1))
    if chars >= 6:
        s += chr(ord('a') + int((lon % 2) * 12)) + chr(ord('a') + int((lat % 1) * 24))
    return s
