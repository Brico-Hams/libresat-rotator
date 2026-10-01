"""Tracking engine: pass planning, rotator steering, Doppler, GPS position, sun calibration."""
from __future__ import annotations

import asyncio
import logging
import math
from datetime import timedelta

from .astro import Observer, utcnow, sun_position, maidenhead
from .doppler import DopplerEngine
from .passes import Limits, find_passes, plan_pass

log = logging.getLogger('lsr.tracker')


class Tracker:
    def __init__(self, cfg, rot, tles, satdb, rig=None):
        self.cfg, self.rot, self.tles, self.satdb, self.rig = cfg, rot, tles, satdb, rig
        st = cfg['station']
        self.obs = Observer(st['lat'], st['lon'], st['alt'])
        l = cfg['limits']
        self.limits = Limits(l['az_min'], l['az_max'], l['el_min'], l['el_max'], l['vmax_az'], l['vmax_el'])
        self.target = None              # satellite name
        self.tp_index = None
        self.pass_ = None
        self.plan = None
        self.doppler = None
        self.mode = 'idle'              # idle | waiting | preposition | tracking | manual | external
        self.status = {}
        self.look = None
        self.last_cmd = None
        self.message = ''
        self.gps_source = 'config'
        self._parked = False

    # ---------------------------------------------------------- commands
    def set_target(self, name: str, tp_index: int | None = None):
        sat = self.tles.get(name)
        if not sat:
            raise KeyError(f'no TLE for {name} (update TLEs or add it)')
        self.target, self.tp_index = sat.name, tp_index
        self.pass_ = self.plan = None
        self.doppler = None
        self.mode = 'waiting'
        self._parked = False
        self.message = f'target {sat.name}'

    def stop(self):
        self.target = None
        self.pass_ = self.plan = self.doppler = None
        self.mode = 'idle'
        self.rot.stop()

    def manual(self, az: float, el: float):
        self.target = None; self.plan = None; self.doppler = None
        self.mode = 'manual'
        self.rot.set_pos(az, el)

    def external(self):
        """A rotctld client (Gpredict, Look4Sat, SatNOGS) took control."""
        if self.mode != 'external':
            self.target = None; self.plan = None; self.doppler = None
            self.mode = 'external'

    def transponders(self, name: str | None = None):
        sat = self.tles.get(name or self.target or '')
        e = self.satdb.get(sat.norad) if sat else None
        return e.transponders if e else []

    def sun_align(self, el_too: bool = False) -> dict:
        az, el = sun_position(self.obs, utcnow())
        if el < 5:
            raise ValueError(f'the Sun is too low ({el:.1f} deg)')
        self.rot.cal('AZ', az)
        if el_too:
            self.rot.cal('EL', el)
        return {'sun_az': round(az, 2), 'sun_el': round(el, 2), 'el_set': el_too}

    def passes(self, name: str, hours: float = 24.0, min_el: float | None = None):
        sat = self.tles.get(name)
        if not sat:
            return []
        me = self.cfg['tracking']['min_pass_el'] if min_el is None else min_el
        out = []
        for p in find_passes(sat, self.obs, utcnow() - timedelta(minutes=20), hours, 0.0, me):
            if p.los < utcnow():
                continue
            pl = plan_pass(p, self.limits, self.status.get('az'), self.cfg['limits']['allow_flip'])
            d = p.as_dict(); d['plan'] = pl.as_dict() if pl else None
            d['track'] = [[round(a, 1), round(e, 1)] for _, a, e in p.track[::10]]
            out.append(d)
        return out

    # ---------------------------------------------------------- loop
    def _update_station_from_gps(self):
        g = self.status.get('gps')
        if not self.cfg['station'].get('use_gps') or not isinstance(g, list) or len(g) < 5 or not g[0]:
            return
        lat, lon, alt = float(g[2]), float(g[3]), float(g[4])
        d = math.hypot(lat - self.obs.lat, (lon - self.obs.lon) * math.cos(math.radians(lat))) * 111.0
        if d > 0.1 or abs(alt - self.obs.alt) > 50:
            self.obs = Observer(lat, lon, alt)
            self.gps_source = 'gps'
            self.pass_ = self.plan = None          # re-plan with the new position
            log.info('station from GPS: %.5f %.5f %.0f m (%s)', lat, lon, alt, maidenhead(lat, lon))

    def _new_pass(self, sat, now):
        ps = find_passes(sat, self.obs, now - timedelta(minutes=25), 36.0, 0.0, self.cfg['tracking']['min_pass_el'])
        ps = [p for p in ps if p.los > now]
        if not ps:
            return None, None
        p = ps[0]
        plan = plan_pass(p, self.limits, self.status.get('az'), self.cfg['limits']['allow_flip'])
        return p, plan

    def step(self):
        """One control cycle (called at tracking.update_hz)."""
        try:
            self.status = self.rot.status() or self.status
        except Exception as e:
            self.message = f'controller: {e}'
        self._update_station_from_gps()
        now = utcnow()
        tr = self.cfg['tracking']
        if not self.target:
            self.look = None
            return
        sat = self.tles.get(self.target)
        self.look = sat.look(self.obs, now)
        if self.pass_ is None or now > self.pass_.los + timedelta(seconds=2):
            if self.pass_ is not None and now > self.pass_.los:          # pass finished
                if self.doppler:
                    self.doppler = None
                if tr['park_after_pass'] and not self._parked:
                    self.rot.set_abs(*tr['park']); self._parked = True
                if not tr['auto_next']:
                    self.mode = 'idle'; self.message = f'{self.target}: pass finished'; self.target = None
                    self.pass_ = self.plan = None
                    return
            self.pass_, self.plan = self._new_pass(sat, now)
            if self.pass_ is None:
                self.message = f'{self.target}: no pass above {tr["min_pass_el"]} deg in 36 h'
                return
            if self.plan is None:
                self.message = 'pass not feasible with the configured limits'
        p, plan = self.pass_, self.plan
        if plan is None:
            return
        lead = timedelta(seconds=tr['lead_s'])
        if now < p.aos - timedelta(seconds=tr['preposition_s']):
            self.mode = 'waiting'
        elif now < p.aos:
            self.mode = 'preposition'
            az, el = plan.points[0][1], plan.points[0][2]
            self._cmd(az, el)
            self._parked = False
            self._doppler_tick()
        else:
            self.mode = 'tracking'
            az, el = plan.at(now + lead)
            self._cmd(az, el)
            self._parked = False
            self._doppler_tick()

    def _cmd(self, az, el):
        c = (round(az, 2), round(el, 2))
        if c != self.last_cmd:
            self.rot.set_abs(*c)
            self.last_cmd = c

    def _doppler_tick(self):
        tps = self.transponders()
        if not tps or self.look is None:
            return
        idx = self.tp_index if self.tp_index is not None and self.tp_index < len(tps) else 0
        if self.doppler is None or self.doppler.tp is not tps[idx]:
            self.doppler = DopplerEngine(tps[idx], self.rig, self.cfg['doppler'])
        try:
            self.doppler.tick(self.look.range_rate)
        except Exception as e:
            self.message = f'rig: {e}'

    async def run(self):
        period = 1.0 / float(self.cfg['tracking']['update_hz'])
        while True:
            try:
                await asyncio.to_thread(self.step)
            except Exception as e:                      # keep running in the field
                log.exception('tracker step failed')
                self.message = f'error: {e}'
            await asyncio.sleep(period)

    def snapshot(self) -> dict:
        lk = self.look
        d = dict(mode=self.mode, target=self.target, message=self.message, status=self.status,
                 station=dict(lat=self.obs.lat, lon=self.obs.lon, alt=self.obs.alt,
                              locator=maidenhead(self.obs.lat, self.obs.lon), source=self.gps_source),
                 time=utcnow().isoformat())
        if lk:
            d['sat'] = dict(az=round(lk.az, 2), el=round(lk.el, 2), range_km=round(lk.range_km, 1),
                            range_rate=round(lk.range_rate, 3), lat=round(lk.lat, 2), lon=round(lk.lon, 2), alt_km=round(lk.alt_km))
        if self.pass_:
            d['pass'] = self.pass_.as_dict()
            d['pass']['track'] = [[round(a, 1), round(e, 1)] for _, a, e in self.pass_.track[::5]]
        if self.plan:
            d['plan'] = self.plan.as_dict()
        if self.doppler and self.doppler.st.rx:
            st = self.doppler.st
            d['doppler'] = dict(rx=st.rx, tx=st.tx, down_sat=st.down_sat, transponder=self.doppler.tp.label)
        sun_az, sun_el = sun_position(self.obs, utcnow())
        d['sun'] = dict(az=round(sun_az, 2), el=round(sun_el, 2))
        return d
