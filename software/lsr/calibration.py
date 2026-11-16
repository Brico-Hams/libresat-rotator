"""Automatic calibration (each step usable alone): level, compass north, sun, index/backlash.

Results go into cfg['calibration'][<step>] (saved with config.save) with a validity flag; invalid or missing results are
never applied (safe defaults = identity). `apply_to_pointing` turns the valid results into pointing-model terms.
Ideas credited to the SARCNET MK1 derivatives (aleiei/Rotator7, Nathan-Busse/SarcnetMiniSatelliteTrackerMK1, see
docs/reference/SARCNET_ROTATOR_REPOS.md): per-axis min/max (hard-iron) magnetometer calibration, low-pass alpha 0.02,
ellipsoid fit back to a sphere, declination for true north, calibration validity check with safe defaults.
Own implementation. Sun calibration needs no magnetometer and is the most accurate north/horizon reference.
"""
from __future__ import annotations

import math
import random
import re
import subprocess
import time
from datetime import datetime, timezone

from . import geomag
from .astro import Observer, sun_position
from .lsq import lstsq, solve
from .pointing import LIMITS, PointingModel, Point, wrap180

LEVEL_THRESHOLD_DEG = 0.5
LP_ALPHA = 0.02


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


# ------------------------------------------------------------------ a. level
def tilt_from_accel(ax: float, ay: float, az: float) -> tuple[float, float]:
    """(roll, pitch) in deg, same convention as the firmware (LEVEL): roll = atan2(ay, az), pitch = atan2(-ax, hypot(ay, az))."""
    return (math.degrees(math.atan2(ay, az)), math.degrees(math.atan2(-ax, math.hypot(ay, az))))


def _average(read, n, delay, sleep):
    acc = []
    for _ in range(n):
        acc.append(tuple(read()))
        if delay:
            sleep(delay)
    mean = [sum(c) / len(acc) for c in zip(*acc)]
    std = [math.sqrt(sum((v - m) ** 2 for v in c) / len(acc)) for c, m in zip(zip(*acc), mean)]
    return mean, std


def calibrate_level(read_accel, n: int = 50, delay: float = 0.02, threshold: float = LEVEL_THRESHOLD_DEG,
                    max_noise: float = 0.2, sleep=time.sleep) -> dict:
    """Base IMU averaged at rest -> mount tilt. tilt_n / tilt_e = tilt of the azimuth axis towards the az-0 direction (x)
    and towards +90 deg (y), the pointing-model terms. ok = total tilt <= threshold; valid = the measurement itself is usable."""
    m, s = _average(read_accel, n, delay, sleep)
    g = math.sqrt(sum(v * v for v in m))
    if not all(math.isfinite(v) for v in m) or g < 0.5 or g > 1.5:
        return dict(valid=False, ok=False, status='accelerometer reading invalid (|a| must be ~1 g)')
    roll, pitch = tilt_from_accel(*m)
    total = math.hypot(roll, pitch)
    noise = max(math.degrees(v / g) for v in s)
    valid = noise <= max_noise and total <= 15.0
    return dict(valid=valid, ok=valid and total <= threshold, roll=round(roll, 3), pitch=round(pitch, 3),
                tilt_n=round(pitch, 3), tilt_e=round(-roll, 3), total=round(total, 3), noise=round(noise, 4),
                threshold=threshold,
                status=('level ok' if total <= threshold else f'tilt {total:.2f} deg: adjust the legs or keep the correction')
                if valid else 'not at rest or tilt > 15 deg: repeat')


# ------------------------------------------------------------------ b. compass
class LowPass:
    def __init__(self, alpha: float = LP_ALPHA):
        self.alpha, self.y = alpha, None

    def __call__(self, x):
        self.y = list(x) if self.y is None else [y + self.alpha * (v - y) for y, v in zip(self.y, x)]
        return self.y


class MagCal:
    """Hard-iron (per-axis min/max) and optional axis-aligned ellipsoid (soft-iron) magnetometer calibration."""

    def __init__(self):
        self.samples: list[tuple[float, float, float]] = []
        self.offset = [0.0, 0.0, 0.0]
        self.scale = [1.0, 1.0, 1.0]

    def add(self, m):
        self.samples.append(tuple(float(v) for v in m))

    def fit_minmax(self):
        lo = [min(s[i] for s in self.samples) for i in range(3)]
        hi = [max(s[i] for s in self.samples) for i in range(3)]
        self.offset = [(a + b) / 2 for a, b in zip(lo, hi)]
        rad = [(b - a) / 2 for a, b in zip(lo, hi)]
        mean = sum(rad) / 3
        self.scale = [mean / r if r > 1e-9 else 1.0 for r in rad]
        return self

    def fit_ellipsoid(self):
        """Least squares a x^2 + b y^2 + c z^2 + d x + e y + f z = 1 -> centre and per-axis radii -> offset and scale."""
        rows = [[x * x, y * y, z * z, x, y, z] for x, y, z in self.samples]
        a, b, c, d, e, f = lstsq(rows, [1.0] * len(rows))
        cx, cy, cz = -d / (2 * a), -e / (2 * b), -f / (2 * c)
        k = 1 + a * cx * cx + b * cy * cy + c * cz * cz
        rad = [math.sqrt(k / v) for v in (a, b, c)]
        mean = sum(rad) / 3
        self.offset, self.scale = [cx, cy, cz], [mean / r for r in rad]
        return self

    def apply(self, m):
        return [(v - o) * s for v, o, s in zip(m, self.offset, self.scale)]

    def as_dict(self):
        return dict(offset=[round(v, 4) for v in self.offset], scale=[round(v, 5) for v in self.scale])

    def load(self, d: dict):
        self.offset, self.scale = list(d['offset']), list(d['scale'])
        return self


def tilt_compensated_heading(m, roll: float, pitch: float) -> float:
    """Magnetic heading (deg 0..360) of the body x axis from a hard/soft-iron corrected field (x forward, y right, z down
    convention, roll/pitch from tilt_from_accel)."""
    r, p = math.radians(roll), math.radians(pitch)
    xh = m[0] * math.cos(p) + (m[1] * math.sin(r) + m[2] * math.cos(r)) * math.sin(p)
    yh = m[1] * math.cos(r) - m[2] * math.sin(r)
    return math.degrees(math.atan2(-yh, xh)) % 360.0


def calibrate_compass(read_mag, read_accel, declination: float, magcal: MagCal | None = None, n: int = 400,
                      alpha: float = LP_ALPHA, delay: float = 0.02, sleep=time.sleep, source: str = 'manual') -> dict:
    """Heading of the base x axis (= mount az 0) -> true-north offset az_off = magnetic heading + declination.
    read_mag None (no magnetometer fitted: MPU-6050 has none) -> skipped with a clear status."""
    if read_mag is None:
        return dict(valid=False, skipped=True, status='skipped: no magnetometer configured (use the sun calibration)')
    lp, la = LowPass(alpha), LowPass(alpha)
    mc = magcal or MagCal()
    for _ in range(n):
        m, a = lp(mc.apply(read_mag())), la(read_accel())
        if delay:
            sleep(delay)
    roll, pitch = tilt_from_accel(*a)
    mag_h = tilt_compensated_heading(m, roll, pitch)
    true_h = (mag_h + declination) % 360.0
    off = wrap180(true_h)
    return dict(valid=math.isfinite(off), mag_heading=round(mag_h, 3), declination=round(declination, 3),
                declination_source=source, az_off=round(off, 3), status='ok')


def resolve_declination(cfg: dict, obs: Observer, when: datetime | None = None) -> tuple[float, str]:
    d = geomag.declination(obs.lat, obs.lon, obs.alt, when)
    if d is not None:
        return d, 'WMM2025'
    man = cfg.get('calibration', {}).get('declination')
    return (float(man), 'manual') if man is not None else (0.0, 'default 0 (no WMM2025.COF, no manual value)')


# ------------------------------------------------------------------ c. sun
def sun_sky(obs: Observer, when: datetime) -> tuple[float, float]:
    return sun_position(obs, when, refraction=False)       # geometric: the pointing model owns refraction


def solve_offsets(model: PointingModel, sky: tuple[float, float], mount: tuple[float, float]) -> tuple[float, float]:
    """az_off / el_off that make the model map `mount` onto `sky` (other terms unchanged; a few iterations for the tilt)."""
    m = PointingModel(model.p, model.refraction)
    for _ in range(4):
        sa, se = m.to_sky(*mount)
        m.p['az_off'] += wrap180(sky[0] - sa)
        m.p['el_off'] += sky[1] - se
    return m.p['az_off'], m.p['el_off']


def fit_peak(samples, floor_frac: float = 0.15, floor: float | None = None):
    """2-D Gaussian peak by a weighted log-paraboloid fit of the top of the scan. samples = [(x, y, value)];
    floor = background level (default: just below the scan minimum). Returns (x0, y0, contrast, floor) or None."""
    vals = [v for _, _, v in samples]
    lo, hi = min(vals), max(vals)
    if not all(math.isfinite(v) for v in vals) or hi - lo <= 1e-12:
        return None
    if floor is None:
        floor = lo - 0.01 * (hi - lo)
    if hi <= floor:
        return None
    top = [(x, y, v - floor) for x, y, v in samples if v - floor >= floor_frac * (hi - floor)]
    if len(top) < 6:
        return None
    rows = [[1.0, x, y, x * x, y * y, x * y] for x, y, _ in top]
    try:
        c = lstsq(rows, [math.log(v) for _, _, v in top], [v * v for _, _, v in top])
        if c[3] >= 0 or c[4] >= 0:
            return None
        x0, y0 = solve([[2 * c[3], c[5]], [c[5], 2 * c[4]]], [-c[1], -c[2]])
    except ValueError:
        return None
    return x0, y0, (hi - lo) / (abs(hi) + abs(lo)), floor


def raster(span: float, step: float) -> list[tuple[float, float]]:
    """Boustrophedon grid of on-sky offsets (dx, dy) in [-span, span]."""
    k = int(round(span / step))
    pts = []
    for j, iy in enumerate(range(-k, k + 1)):
        xs = list(range(-k, k + 1))
        pts += [(ix * step, iy * step) for ix in (xs if j % 2 == 0 else xs[::-1])]
    return pts


def sun_scan(move, read, obs: Observer, now=now_utc, model: PointingModel | None = None, span: float = 6.0,
             step: float = 1.5, refine: bool = True, settle=None) -> dict:
    """Raster the mount around the predicted Sun position. move(mount_az, mount_el) commands the raw mount (no pointing
    correction, must return when settled), read() is the pluggable sun sensor (photodiode ADC, SDR noise power ...).
    The Sun drifts, so every sample is stored relative to the Sun at its own time. Returns the new az_off/el_off."""
    model = model or PointingModel()
    def cosel(el):
        return max(0.1, math.cos(math.radians(el)))

    cx = cy = 0.0                                         # centre of the current pass, on-sky offset from the model's Sun
    n = 0
    contrast, floor = 0.0, None
    for sp, st in ((span, step), (span / 3.0, step / 3.0)) if refine else ((span, step),):
        samples = []
        for dx, dy in raster(sp, st):
            sa, se = sun_sky(obs, now())
            ma, me = model.to_mount(sa, se)
            caz, cel = ma + (cx + dx) / cosel(se), me + cy + dy
            move(caz, cel)
            if settle:
                settle()
            v = read()
            sa2, se2 = sun_sky(obs, now())                # the Sun moved while we settled: store the offset from it
            ma2, me2 = model.to_mount(sa2, se2)
            samples.append(((caz - ma2) * cosel(se2), cel - me2, v))
        fit = fit_peak(samples, floor=floor)              # pass 2 reuses the background level seen by the wide pass
        if fit is None or abs(fit[0] - cx) > sp or abs(fit[1] - cy) > sp:
            return dict(valid=False, ok=False, status='no Sun peak inside the scan (check sensor, pointing, clouds)')
        if floor is None:
            contrast, floor = fit[2], fit[3]
        cx, cy, n = fit[0], fit[1], n + len(samples)
    sa, se = sun_sky(obs, now())
    ma, me = model.to_mount(sa, se)
    peak = (ma + cx / cosel(se), me + cy)
    az_off, el_off = solve_offsets(model, (sa, se), peak)
    ok = contrast >= 0.2 and abs(az_off) <= LIMITS['az_off'] and abs(el_off) <= LIMITS['el_off']
    return dict(valid=ok, ok=ok, az_off=round(az_off, 4), el_off=round(el_off, 4), contrast=round(contrast, 3),
                n=n, method='scan', status='ok' if ok else 'weak peak: repeat in clear sky',
                point=dict(sky_az=sa, sky_el=se, mount_az=peak[0], mount_el=peak[1]))


def sun_mark(obs: Observer, when: datetime, mount_az: float, mount_el: float, model: PointingModel | None = None) -> dict:
    """Manual variant: the operator centred the Sun in the pinhole/shadow sight and pressed 'mark'."""
    model = model or PointingModel()
    sa, se = sun_sky(obs, when)
    if se < 5.0:
        return dict(valid=False, ok=False, status=f'Sun too low (el {se:.1f} deg)')
    az_off, el_off = solve_offsets(model, (sa, se), (mount_az, mount_el))
    ok = abs(az_off) <= LIMITS['az_off'] and abs(el_off) <= LIMITS['el_off']
    return dict(valid=ok, ok=ok, az_off=round(az_off, 4), el_off=round(el_off, 4), method='manual', n=1,
                status='ok' if ok else 'offset out of range: wrong mark?',
                point=dict(sky_az=sa, sky_el=se, mount_az=mount_az, mount_el=mount_el))


def point_from(result: dict, note: str = 'sun') -> Point | None:
    p = result.get('point')
    return Point(p['sky_az'], p['sky_el'], p['mount_az'], p['mount_el'], 1.0, note) if p else None


class SimSunWorld:
    """Synthetic mount + Gaussian Sun sensor for tests and `lsr calibrate sun --sim`."""

    def __init__(self, obs: Observer, truth: PointingModel, now=now_utc, sigma: float = 2.0, noise: float = 0.0,
                 background: float = 0.05, seed: int = 1):
        self.obs, self.truth, self.now, self.sigma, self.noise, self.bg = obs, truth, now, sigma, noise, background
        self.mount = (0.0, 0.0)
        self.rng = random.Random(seed)

    def move(self, az, el):
        self.mount = (az, el)

    def read(self) -> float:
        sa, se = self.truth.to_sky(*self.mount)
        ua, ue = sun_sky(self.obs, self.now())
        a1, e1, a2, e2 = map(math.radians, (sa, se, ua, ue))
        c = math.sin(e1) * math.sin(e2) + math.cos(e1) * math.cos(e2) * math.cos(a1 - a2)
        sep = math.degrees(math.acos(max(-1.0, min(1.0, c))))
        return self.bg + math.exp(-sep * sep / (2 * self.sigma ** 2)) + self.rng.gauss(0.0, self.noise)


def command_sensor(cmd: str, timeout: float = 5.0):
    """Sun sensor from an external program that prints one number (ADC reader, rtl_power wrapper...)."""
    def read() -> float:
        out = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout).stdout
        m = re.search(r'[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?', out)
        if not m:
            raise IOError(f'sun sensor command printed no number: {cmd!r}')
        return float(m.group())
    return read


# ------------------------------------------------------------------ d. index and backlash
def measure_backlash(move, read_out, pos: float, approach: float = 3.0) -> float:
    """Approach `pos` from below and from above (move() returns when settled), compare the OUTPUT encoder readings."""
    move(pos - approach); move(pos); a = read_out()
    move(pos + approach); move(pos); b = read_out()
    return abs(b - a)


def wait_idle(rot, timeout: float = 300.0, need_ref: bool = False, clock=time.monotonic, sleep=time.sleep) -> bool:
    t0 = clock()
    while clock() - t0 < timeout:
        st = rot.status()
        if st and list(st.get('mode', [1, 1])) == [0, 0] and (not need_ref or list(st.get('ref', [0, 0])) == [1, 1]):
            return True
        sleep(0.5)
    return False


def calibrate_index(rot, clock=time.monotonic, sleep=time.sleep, timeout: float = 300.0) -> dict:
    """Home both axes on the index, then measure the backlash: LSR-2 firmware does it itself (XCAL BACKLASH: both
    directions onto the photo-interrupter edge); otherwise use the output encoders vs the commanded position."""
    rot.home()
    if not wait_idle(rot, timeout, True, clock, sleep):
        return dict(valid=False, ok=False, status='homing on the index did not finish (see XS err bits)')
    if getattr(rot, 'model', 'lsr1') == 'lsr2':
        rot.cal('BACKLASH')
        sleep(0.5)
        if not wait_idle(rot, timeout, True, clock, sleep):
            return dict(valid=False, ok=False, status='firmware backlash measurement did not finish')
        bl, method = list((rot.raw() or {}).get('backlash') or [0.0, 0.0]), 'index (firmware)'
    else:
        raw = rot.raw() if hasattr(rot, 'raw') else None
        if not raw or any(v is None or not math.isfinite(v) for v in raw.get('enc', [None])):
            return dict(valid=False, ok=False, status='no output encoder: backlash not measurable')
        bl = []
        for ax in (0, 1):
            def mv(p, ax=ax):
                cur = rot.get_pos()
                tgt = [cur[0], cur[1]]
                tgt[ax] = p
                rot.set_pos(*tgt)
                sleep(0.3)
                wait_idle(rot, 60.0, False, clock, sleep)
            bl.append(measure_backlash(mv, lambda ax=ax: rot.raw()['enc'][ax], rot.get_pos()[ax]))
        method = 'encoder vs step'
    ok = all(math.isfinite(v) and 0.0 <= v <= 2.0 for v in bl)
    return dict(valid=ok, ok=ok, backlash_az=round(bl[0], 3), backlash_el=round(bl[1], 3), method=method,
                status='ok' if ok else 'backlash out of range 0..2 deg: check the mechanics')


# ------------------------------------------------------------------ station data, persistence
def station_and_time(status: dict | None, cfg: dict) -> tuple[Observer, datetime, str]:
    """GPS time and position from the controller status (XS gps=,utc=) when valid, else config / system clock."""
    st = cfg['station']
    g = (status or {}).get('gps')
    if isinstance(g, list) and len(g) >= 5 and g[0] and g[1] and (g[2] or g[3]):
        obs = Observer(float(g[2]), float(g[3]), float(g[4]))
        src = 'gps'
    else:
        obs, src = Observer(st['lat'], st['lon'], st['alt']), 'config'
    when = now_utc()
    u = (status or {}).get('utc')
    if src == 'gps' and isinstance(u, str):
        try:
            when = datetime.strptime(u.replace('Z', '')[:19], '%Y-%m-%dT%H:%M:%S').replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    return obs, when, src


def gps_clock(when: datetime):
    """Clock callable that continues from the GPS time read now (system clock only supplies the elapsed time)."""
    off = when - now_utc()
    return lambda: now_utc() + off


STEPS = ('level', 'compass', 'sun', 'index')


def save_result(cfg: dict, step: str, result: dict) -> dict:
    result = {k: v for k, v in result.items() if k != 'point'}
    result['time'] = now_utc().strftime('%Y-%m-%dT%H:%M:%SZ')
    cfg.setdefault('calibration', {})[step] = result
    return result


def is_valid(cfg: dict, step: str) -> bool:
    r = (cfg.get('calibration') or {}).get(step)
    if not isinstance(r, dict) or not r.get('valid'):
        return False
    keys = {'level': ('tilt_n', 'tilt_e'), 'compass': ('az_off',), 'sun': ('az_off', 'el_off'),
            'index': ('backlash_az', 'backlash_el')}[step]
    try:
        vals = [float(r[k]) for k in keys]
    except (KeyError, TypeError, ValueError):
        return False
    lim = 2.0 if step == 'index' else (15.0 if step == 'level' else 180.0)
    return all(math.isfinite(v) and abs(v) <= lim for v in vals)


def apply_to_pointing(cfg: dict) -> dict:
    """Copy the VALID results into cfg['pointing'] (sun beats compass for az_off; the firmware keeps the backlash it measured)."""
    pc = cfg.setdefault('pointing', {})
    p = pc.setdefault('params', {})
    cal = cfg.get('calibration', {})
    if is_valid(cfg, 'level'):
        p['tilt_n'], p['tilt_e'] = cal['level']['tilt_n'], cal['level']['tilt_e']
    if is_valid(cfg, 'sun'):
        p['az_off'], p['el_off'] = cal['sun']['az_off'], cal['sun']['el_off']
    elif is_valid(cfg, 'compass'):
        p['az_off'] = cal['compass']['az_off']
    if is_valid(cfg, 'index') and 'firmware' not in cal['index'].get('method', ''):
        pc['backlash_az'], pc['backlash_el'] = cal['index']['backlash_az'], cal['index']['backlash_el']
    return pc


def summary(cfg: dict) -> list[dict]:
    """One row per step for the web table / `lsr calibrate` output."""
    rows = []
    for s in STEPS:
        r = (cfg.get('calibration') or {}).get(s) or {}
        rows.append(dict(step=s, valid=is_valid(cfg, s), time=r.get('time', ''), status=r.get('status', 'not done'),
                         values={k: v for k, v in r.items() if k in ('tilt_n', 'tilt_e', 'total', 'az_off', 'el_off',
                                                                     'backlash_az', 'backlash_el', 'declination')}))
    return rows
