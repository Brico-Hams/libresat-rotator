"""Pointing correction model: true sky az/el <-> mount az/el, plus least-squares fit from calibration points.

Forward model (mount reading -> sky), all angles in degrees, small terms added in the platform frame, then an exact
rotation of the tilted azimuth axis (Rodrigues), then optional refraction removal:
  az' = az + az_off + ecc_sin sin(az) + ecc_cos cos(az) + nonperp tan(el) + collim / cos(el)
  el' = el + el_off
  (az', el') --rotate azimuth axis towards north by tilt_n and towards east by tilt_e--> sky
Commanded positions use the iterative inverse; direction-dependent backlash is a separate, stateful compensation
(BacklashComp) so that command and report stay exact inverses. The term set follows the usual telescope-pointing
practice (index errors, tilt, non-perpendicularity, collimation, encoder eccentricity); the idea of a fitted model with a
residual RMS is the one used by SARCTrac Mk5 style trackers. Own implementation.
"""
from __future__ import annotations

import csv
import math
from dataclasses import dataclass, field

from .astro import refraction_deg
from .lsq import lstsq

NAMES = ('az_off', 'el_off', 'tilt_n', 'tilt_e', 'nonperp', 'collim', 'ecc_sin', 'ecc_cos')
FIT_DEFAULT = NAMES
LIMITS = {'az_off': 180.0, 'el_off': 20.0, 'tilt_n': 10.0, 'tilt_e': 10.0, 'nonperp': 5.0, 'collim': 5.0,
          'ecc_sin': 3.0, 'ecc_cos': 3.0}


def wrap180(a: float) -> float:
    return (a + 180.0) % 360.0 - 180.0


class PointingModel:
    def __init__(self, params: dict | None = None, refraction: bool = False):
        self.p = {k: 0.0 for k in NAMES}
        for k, v in (params or {}).items():
            if k in self.p:
                self.p[k] = float(v)
        self.refraction = bool(refraction)

    @classmethod
    def from_config(cls, c: dict) -> 'PointingModel':
        return cls((c or {}).get('params'), (c or {}).get('refraction', False))

    def is_valid(self) -> bool:
        return all(math.isfinite(v) and abs(v) <= LIMITS[k] for k, v in self.p.items())

    def _sky_apparent(self, az: float, el: float):
        p = self.p
        flip = el > 90.0                                 # LSR-1 flip passes (el up to 180): fold, correct, unfold
        a, e = (az + 180.0, 180.0 - el) if flip else (az, el)
        ec = max(-85.0, min(85.0, e))
        ra = math.radians(a)
        a1 = (a + p['az_off'] + p['ecc_sin'] * math.sin(ra) + p['ecc_cos'] * math.cos(ra)
              + p['nonperp'] * math.tan(math.radians(ec)) + p['collim'] / math.cos(math.radians(ec)))
        e1 = e + p['el_off']
        tn, te = math.radians(p['tilt_n']), math.radians(p['tilt_e'])
        tau = math.hypot(tn, te)
        if tau > 1e-12:
            a1r, e1r = math.radians(a1), math.radians(e1)
            v = (math.cos(e1r) * math.sin(a1r), math.cos(e1r) * math.cos(a1r), math.sin(e1r))
            s, c = math.sin(tau), math.cos(tau)
            k = (-tn / tau, te / tau, 0.0)               # unit axis z x n
            kv = (k[1] * v[2] - k[2] * v[1], k[2] * v[0] - k[0] * v[2], k[0] * v[1] - k[1] * v[0])
            kd = k[0] * v[0] + k[1] * v[1] + k[2] * v[2]
            w = [v[i] * c + kv[i] * s + k[i] * kd * (1 - c) for i in range(3)]
            a1 = a1 + wrap180(math.degrees(math.atan2(w[0], w[1])) - a1)
            e1 = math.degrees(math.asin(max(-1.0, min(1.0, w[2]))))
        daz = a1 - a
        de = e1 - e
        return (az + daz, el - de if flip else el + de)

    def to_sky(self, az: float, el: float) -> tuple[float, float]:
        """Mount reading -> true sky position."""
        sa, se = self._sky_apparent(az, el)
        if self.refraction:
            t = se
            for _ in range(6):
                t = se - refraction_deg(t)
            se = t
        return sa, se

    def to_mount(self, az: float, el: float) -> tuple[float, float]:
        """True sky position -> mount position to command (inverse of to_sky, fixed-point iteration)."""
        tgt_az, tgt_el = az, el + (refraction_deg(el) if self.refraction else 0.0)
        ma, me = tgt_az, tgt_el
        for _ in range(10):
            sa, se = self._sky_apparent(ma, me)
            da, de = wrap180(sa - tgt_az), se - tgt_el
            ma, me = ma - da, me - de
            if abs(da) < 1e-9 and abs(de) < 1e-9:
                break
        return ma, me

    def fit(self, points: list['Point'], names=FIT_DEFAULT, iters: int = 30) -> 'FitResult':
        """Gauss-Newton fit of the chosen parameters (others keep their value); updates self.p."""
        names = list(names)
        if len(points) < len(names):
            raise ValueError(f'need at least {len(names)} points to fit {len(names)} terms, got {len(points)}')

        def resid(model):
            out = []
            for pt in points:
                sa, se = model.to_sky(pt.mount_az, pt.mount_el)
                out += [wrap180(pt.sky_az - sa) * math.cos(math.radians(pt.sky_el)) * pt.weight, (pt.sky_el - se) * pt.weight]
            return out

        for _ in range(iters):
            r0 = resid(self)
            jac = []
            for nm in names:
                h = 1e-4
                hi, lo = PointingModel(self.p, self.refraction), PointingModel(self.p, self.refraction)
                hi.p[nm] += h; lo.p[nm] -= h
                rh, rl = resid(hi), resid(lo)
                jac.append([(a - b) / (2 * h) for a, b in zip(rh, rl)])
            rows = [[jac[j][i] for j in range(len(names))] for i in range(len(r0))]
            dx = lstsq(rows, r0, ridge=1e-9)
            for nm, d in zip(names, dx):
                self.p[nm] -= d                          # dx solves J_r dx = r (r = observed - predicted)
            if max(abs(d) for d in dx) < 1e-9:
                break
        return self.evaluate(points)

    def evaluate(self, points: list['Point']) -> 'FitResult':
        res = []
        for pt in points:
            sa, se = self.to_sky(pt.mount_az, pt.mount_el)
            res.append(math.hypot(wrap180(pt.sky_az - sa) * math.cos(math.radians(pt.sky_el)), pt.sky_el - se))
        rms = math.sqrt(sum(r * r for r in res) / len(res)) if res else float('nan')
        return FitResult(dict(self.p), rms, len(points), max(res) if res else float('nan'), res)


@dataclass
class Point:
    sky_az: float
    sky_el: float          # true (geometric) elevation
    mount_az: float
    mount_el: float
    weight: float = 1.0
    note: str = ''


@dataclass
class FitResult:
    params: dict
    rms: float             # on-sky residual, deg
    n: int
    max_err: float
    residuals: list = field(default_factory=list)


def load_points(path: str) -> list[Point]:
    """CSV with columns sky_az,sky_el,mount_az,mount_el[,weight[,note]]; header and '#' comments allowed."""
    pts = []
    with open(path, newline='') as f:
        for row in csv.reader(f):
            if not row or row[0].strip().startswith('#'):
                continue
            try:
                v = [float(x) for x in row[:4]]
            except ValueError:
                continue                                  # header
            pts.append(Point(*v, weight=float(row[4]) if len(row) > 4 and row[4].strip() else 1.0,
                             note=row[5].strip() if len(row) > 5 else ''))
    return pts


def save_points(path: str, points: list[Point]):
    with open(path, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['sky_az', 'sky_el', 'mount_az', 'mount_el', 'weight', 'note'])
        for p in points:
            w.writerow([f'{p.sky_az:.4f}', f'{p.sky_el:.4f}', f'{p.mount_az:.4f}', f'{p.mount_el:.4f}', p.weight, p.note])


class BacklashComp:
    """Direction-dependent backlash compensation per axis. Commanded: target + dir*b/2; reported: reading - dir*b/2
    (dir = sign of the last commanded motion). Zero backlash = identity."""

    def __init__(self, az: float = 0.0, el: float = 0.0):
        self.b = [float(az), float(el)]
        self.dir = [0, 0]
        self.last = [None, None]

    def command(self, axis: int, target: float) -> float:
        if self.last[axis] is not None and abs(target - self.last[axis]) > 1e-6:
            self.dir[axis] = 1 if target > self.last[axis] else -1
        self.last[axis] = target
        return target + self.dir[axis] * self.b[axis] / 2.0

    def report(self, axis: int, reading: float) -> float:
        return reading - self.dir[axis] * self.b[axis] / 2.0


class Pointing:
    """Runtime wrapper used by rotator.CorrectedRotator: model + backlash state."""

    def __init__(self, cfg: dict):
        c = cfg.get('pointing', {}) if 'pointing' in cfg else cfg
        self.model = PointingModel.from_config(c)
        self.comp = BacklashComp(c.get('backlash_az', 0.0), c.get('backlash_el', 0.0))
        self.last_ant = None
        if not self.model.is_valid():                      # safe default: identity
            self.model = PointingModel(refraction=False)

    def command(self, az: float, el: float) -> tuple[float, float]:
        ma, me = self.model.to_mount(az, el)
        self.last_ant = (ma, me)                          # where the ANTENNA must end up (before backlash compensation)
        return self.comp.command(0, ma), self.comp.command(1, me)

    def report(self, az: float, el: float) -> tuple[float, float]:
        return self.model.to_sky(self.comp.report(0, az), self.comp.report(1, el))
