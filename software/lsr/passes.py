"""Pass prediction and the rotator pass planner (cable wrap + elevation "flip").

The planner turns a pass into a smooth, feasible az/el trajectory for an az range of
[az_min, az_max] (e.g. 0..450 deg of cable wrap) and el range [0, el_max] (180 enables flip):

  normal : az = sat az (+k*360), el = sat el
  flip   : az = sat az + 180 (+k*360), el = 180 - sat el   (antenna goes "over the top")

Near-overhead passes need an extremely fast azimuth in normal mode (a 89 deg pass needs
> 50 deg/s around TCA); flip mode keeps the azimuth almost still. The planner evaluates every
(mode, wrap) candidate and picks the feasible one with the lowest peak azimuth rate, then the
shortest slew from where the rotator is now.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from .astro import Observer, Satellite, Look


@dataclass
class Pass:
    sat: str
    aos: datetime
    tca: datetime
    los: datetime
    max_el: float
    aos_az: float
    los_az: float
    track: list = field(default_factory=list)      # [(t, az, el)] at `step` s

    @property
    def duration(self) -> float:
        return (self.los - self.aos).total_seconds()

    def as_dict(self):
        return dict(sat=self.sat, aos=self.aos.isoformat(), tca=self.tca.isoformat(), los=self.los.isoformat(),
                    max_el=round(self.max_el, 1), aos_az=round(self.aos_az, 1), los_az=round(self.los_az, 1),
                    duration=round(self.duration))


def _el(sat: Satellite, obs: Observer, t: datetime) -> float:
    return sat.look(obs, t).el


def _bisect(sat, obs, t0, t1, rising, min_el, tol=0.5):
    while (t1 - t0).total_seconds() > tol:
        tm = t0 + (t1 - t0) / 2
        above = _el(sat, obs, tm) >= min_el
        if above == rising:
            t1 = tm
        else:
            t0 = tm
    return t1 if rising else t0


def find_passes(sat: Satellite, obs: Observer, start: datetime, hours: float = 24.0,
                min_el: float = 0.0, min_max_el: float = 0.0, step: float = 1.0) -> list[Pass]:
    """All passes in [start, start+hours] whose maximum elevation >= min_max_el."""
    out: list[Pass] = []
    coarse = 30.0
    t = start
    end = start + timedelta(hours=hours)
    prev_up = _el(sat, obs, t) >= min_el
    aos = start if prev_up else None
    while t < end:
        tn = t + timedelta(seconds=coarse)
        up = _el(sat, obs, tn) >= min_el
        if up and not prev_up:
            aos = _bisect(sat, obs, t, tn, True, min_el)
        elif prev_up and not up and aos is not None:
            los = _bisect(sat, obs, t, tn, False, min_el)
            p = _build(sat, obs, aos, los, step)
            if p.max_el >= min_max_el:
                out.append(p)
            aos = None
        prev_up, t = up, tn
    return out


def _build(sat, obs, aos, los, step) -> Pass:
    n = max(2, int((los - aos).total_seconds() / step) + 1)
    track = []
    best = (-90.0, aos)
    for i in range(n):
        ti = aos + timedelta(seconds=min(i * step, (los - aos).total_seconds()))
        lk = sat.look(obs, ti)
        track.append((ti, lk.az, lk.el))
        if lk.el > best[0]:
            best = (lk.el, ti)
    return Pass(sat.name, aos, best[1], los, best[0], track[0][1], track[-1][1], track)


def next_pass(sat: Satellite, obs: Observer, start: datetime, hours: float = 48.0, min_max_el: float = 5.0):
    ps = find_passes(sat, obs, start, hours, 0.0, min_max_el)
    return ps[0] if ps else None


# ------------------------------------------------------------------ planner
@dataclass
class Limits:
    az_min: float = 0.0
    az_max: float = 450.0
    el_min: float = 0.0
    el_max: float = 180.0
    vmax_az: float = 20.0       # deg/s (firmware vmax_az)
    vmax_el: float = 15.0
    anti_windup: bool = False   # choose the wrap that leaves the cable near mid-range (config limits.anti_windup)


@dataclass
class Plan:
    mode: str                   # 'normal' | 'flip' (starts normal, ends over the top) | 'flip-rev'
    wrap: float                 # k*360 added to the azimuth
    points: list                # [(t, az_cmd, el_cmd)]
    peak_az_rate: float
    peak_el_rate: float
    slew_deg: float
    feasible: bool = True
    max_error: float = 0.0          # worst pointing error (deg) of the trajectory          # False: the path had to be clipped at an az limit (rotator unwinds)

    def at(self, t: datetime):
        """Interpolated (az, el) command at time t (clamped to the pass)."""
        pts = self.points
        if t <= pts[0][0]:
            return pts[0][1], pts[0][2]
        if t >= pts[-1][0]:
            return pts[-1][1], pts[-1][2]
        lo, hi = 0, len(pts) - 1
        while hi - lo > 1:
            mid = (lo + hi) // 2
            if pts[mid][0] <= t:
                lo = mid
            else:
                hi = mid
        (t0, a0, e0), (t1, a1, e1) = pts[lo], pts[hi]
        f = (t - t0).total_seconds() / max(1e-9, (t1 - t0).total_seconds())
        return a0 + f * (a1 - a0), e0 + f * (e1 - e0)

    def as_dict(self):
        return dict(mode=self.mode, wrap=self.wrap, feasible=self.feasible, peak_az_rate=round(self.peak_az_rate, 2),
                    peak_el_rate=round(self.peak_el_rate, 2), slew_deg=round(self.slew_deg, 1), max_error=round(self.max_error, 2),
                    start=[round(self.points[0][1], 1), round(self.points[0][2], 1)],
                    end=[round(self.points[-1][1], 1), round(self.points[-1][2], 1)])


def _unwrap(seq):
    out, prev = [], None
    for a in seq:
        if prev is not None:
            while a - prev > 180:
                a -= 360
            while a - prev < -180:
                a += 360
        out.append(a)
        prev = a
    return out


def _flip_track(p: Pass, start_rep: int, rate: float):
    """Over-the-top trajectory: azimuth is rate-limited and follows whichever of the two joint
    solutions (az, el) / (az+180, 180-el) is closer; elevation (0..180) is the projection of the
    satellite onto the antenna's vertical plane, so the pointing error stays tiny even when the
    azimuth cannot follow the zenith crossing. Returns (az[], el[], max_error_deg)."""
    az_out, el_out, err = [], [], 0.0
    cur = None
    prev_t = None
    for t, sa, se in p.track:
        se = max(0.0, se)
        if cur is None:
            cur = sa if start_rep == 0 else sa + 180.0
        else:
            dt = (t - prev_t).total_seconds()
            cands = [sa, sa + 180.0]
            tgt = min(cands, key=lambda c: abs((c - cur + 180.0) % 360.0 - 180.0))
            d = (tgt - cur + 180.0) % 360.0 - 180.0
            cur += max(-rate * dt, min(rate * dt, d))
        prev_t = t
        da = math.radians(sa - cur)
        e = math.radians(se)
        el = math.degrees(math.atan2(math.sin(e), math.cos(e) * math.cos(da)))
        el = min(180.0, max(0.0, el))
        err = max(err, math.degrees(math.asin(min(1.0, abs(math.cos(e) * math.sin(da))))))
        az_out.append(cur); el_out.append(el)
    return az_out, el_out, err


def plan_pass(p: Pass, lim: Limits, current_az: float | None = None, allow_flip: bool = True,
              max_error: float = 5.0) -> Plan | None:
    """Choose the trajectory for a pass. Candidates: 'normal' (el <= 90, exact) and, if el_max >= 180,
    'flip' / 'flip-rev' (over the top, azimuth rate-limited to 80 % of vmax_az, error <= max_error)."""
    ts = [x[0] for x in p.track]
    candidates, clipped = [], []
    variants = [('normal', None)]
    if allow_flip and lim.el_max >= 180.0:
        variants += [('flip', 0), ('flip-rev', 1)]
    for mode, rep in variants:
        perr = 0.0
        if mode == 'normal':
            az = _unwrap([x[1] for x in p.track]); el = [max(0.0, x[2]) for x in p.track]
        else:
            az, el, perr = _flip_track(p, rep, 0.8 * lim.vmax_az)
            if perr > max_error:
                continue
        base = az[0] % 360.0
        az = [a - (az[0] - base) for a in az]            # start in [0,360)
        for k in (-720, -360, 0, 360, 720):
            a = [x + k for x in az]
            out = sum(1 for x in a if x < lim.az_min - 1e-6 or x > lim.az_max + 1e-6)
            if out:
                clipped.append((out, mode, k, a, el))
                continue
            if min(el) < lim.el_min - 1e-6 or max(el) > lim.el_max + 1e-6:
                continue
            rates_a = [abs(a[i + 1] - a[i]) / max(1e-6, (ts[i + 1] - ts[i]).total_seconds()) for i in range(len(a) - 1)]
            rates_e = [abs(el[i + 1] - el[i]) / max(1e-6, (ts[i + 1] - ts[i]).total_seconds()) for i in range(len(el) - 1)]
            slew = abs(a[0] - current_az) if current_az is not None else 0.0
            pl = Plan(mode, float(k), list(zip(ts, a, el)), max(rates_a or [0]), max(rates_e or [0]), slew)
            pl.max_error = perr
            candidates.append(pl)
    if not candidates:
        # no wrap fits the whole pass: clip at the limit (the rotator unwinds once during the pass)
        if not clipped:
            return None
        out, mode, k, a, el = min(clipped, key=lambda c: c[0])
        a = [min(max(x, lim.az_min), lim.az_max) for x in a]
        rates_a = [abs(a[i + 1] - a[i]) / max(1e-6, (ts[i + 1] - ts[i]).total_seconds()) for i in range(len(a) - 1)]
        pl = Plan(mode, float(k), list(zip(ts, a, el)), max(rates_a or [0]), 0.0,
                  abs(a[0] - current_az) if current_az is not None else 0.0, feasible=False)
        pl.max_error = 0.0
        return pl

    def score(c: Plan):
        over = max(0.0, c.peak_az_rate - 0.8 * lim.vmax_az)      # too fast for the rotator
        flips = max(e for _, _, e in c.points) > 90.0
        pen = (0.0 if c.mode == 'normal' else 0.3) + (0.2 if flips and c.points[0][2] > 90.0 else 0.0)
        # anti-windup (as SARCTrac Mk5): prefer the wrap that ends near the middle of the range, so the cable unwinds between passes
        wind = abs(c.points[-1][1] - 0.5 * (lim.az_min + lim.az_max)) / max(0.5 * (lim.az_max - lim.az_min), 1e-6) if lim.anti_windup else 0.0
        return (over > 1e-6, round(over, 3), c.slew_deg / max(lim.vmax_az, 1e-6) / 30.0 + pen + c.max_error / 10.0 + wind)
    return min(candidates, key=score)
