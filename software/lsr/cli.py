"""`lsr` command line.

  lsr run                      daemon: web UI (:8080) + rotctld (:4533) + tracker
  lsr run --sim                same, with a simulated rotator (no hardware)
  lsr passes ISS [--hours 24]  pass list with the planner decision (normal/flip, wrap)
  lsr track SO-50              track one satellite from the terminal (Ctrl-C to stop)
  lsr tle update               download TLEs (CelesTrak) into the offline cache
  lsr satdb update             import alive amateur transmitters from SatNOGS DB
  lsr sun                      Sun az/el now (for alignment)
  lsr status                   controller status
  lsr gd77 info|clock|keps     OpenGD77 radio utilities
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import time
from datetime import timezone

from . import config as cfgmod
from .astro import Observer, utcnow, sun_position, maidenhead
from .passes import find_passes, plan_pass, Limits
from .rotator import make_rotator, error_text
from .satdb import SatDB
from .tle import TleStore


class Ctx:
    def __init__(self, cfg, sim=False):
        if sim:
            cfg['rotator']['simulate'] = True
        self.cfg = cfg
        self.tles = TleStore(cfg)
        self.satdb = SatDB(cfg['satdb'].get('file') or None)
        self.rot = make_rotator(cfg)
        from .rigs import make_rig
        self.rig = make_rig(cfg)
        from .tracker import Tracker
        self.tracker = Tracker(cfg, self.rot, self.tles, self.satdb, self.rig)

    def gd77_factory(self):
        from .rigs.opengd77 import OpenGD77
        return OpenGD77(**self.cfg['rig']['opengd77'])

    def save_cfg(self):
        return cfgmod.save(self.cfg)


async def _run(ctx: Ctx):
    from aiohttp import web
    from .rotctld import RotctldServer
    from .web.server import make_app
    from .timesync import maybe_set_clock
    cfg = ctx.cfg
    if ctx.tles.age_days() > cfg['tle']['max_age_days']:
        logging.info('TLEs are old or missing: trying to update')
        res = await asyncio.to_thread(ctx.tles.update)
        logging.info('TLE update: %s', res)
    tasks = [asyncio.create_task(ctx.tracker.run())]
    if cfg['rotctld'].get('enabled', True):
        srv = RotctldServer(ctx.rot, ctx.tracker, 0.0, 360.0, cfg['limits']['el_min'], cfg['limits']['el_max'])
        tasks.append(asyncio.create_task(srv.serve(cfg['rotctld']['host'], cfg['rotctld']['port'])))
    app = make_app(ctx)
    runner = web.AppRunner(app); await runner.setup()
    await web.TCPSite(runner, cfg['web']['host'], cfg['web']['port']).start()
    logging.info('web UI on http://%s:%d', cfg['web']['host'], cfg['web']['port'])

    async def clock_guard():
        while True:
            msg = maybe_set_clock(ctx.tracker.status)
            if msg:
                ctx.tracker.message = msg
            await asyncio.sleep(30)
    tasks.append(asyncio.create_task(clock_guard()))
    await asyncio.gather(*tasks)


def main(argv=None):
    ap = argparse.ArgumentParser(prog='lsr', description='LibreSat Rotator head software')
    ap.add_argument('-c', '--config', help='config YAML')
    ap.add_argument('-v', '--verbose', action='store_true')
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('run'); p.add_argument('--sim', action='store_true')
    p = sub.add_parser('passes'); p.add_argument('sat'); p.add_argument('--hours', type=float, default=24); p.add_argument('--min-el', type=float, default=0)
    p = sub.add_parser('track'); p.add_argument('sat'); p.add_argument('--transponder', type=int); p.add_argument('--sim', action='store_true')
    p = sub.add_parser('tle'); p.add_argument('action', choices=['update', 'list'])
    p = sub.add_parser('satdb'); p.add_argument('action', choices=['update', 'list'])
    sub.add_parser('sun')
    p = sub.add_parser('status'); p.add_argument('--sim', action='store_true')
    p = sub.add_parser('gd77'); p.add_argument('action', choices=['info', 'clock', 'keps', 'nmea']); p.add_argument('sats', nargs='*')
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if a.verbose else logging.INFO, format='%(asctime)s %(name)s %(message)s')
    cfg = cfgmod.load(a.config)
    st = cfg['station']
    obs = Observer(st['lat'], st['lon'], st['alt'])

    if a.cmd == 'run':
        ctx = Ctx(cfg, a.sim)
        try:
            asyncio.run(_run(ctx))
        except KeyboardInterrupt:
            pass
        return 0

    if a.cmd == 'tle':
        ts = TleStore(cfg)
        if a.action == 'update':
            for g, r in ts.update().items():
                print(f'{g:10s} {r}')
        else:
            print('\n'.join(ts.names()))
        return 0

    if a.cmd == 'satdb':
        if a.action == 'update':
            print('satellites imported from SatNOGS DB:', SatDB.update_from_satnogs())
        else:
            for e in SatDB().entries.values():
                print(f'{e.norad:6d} {e.name:12s} ' + ' | '.join(t.label for t in e.transponders))
        return 0

    if a.cmd == 'sun':
        az, el = sun_position(obs, utcnow())
        print(f'Sun at {utcnow():%Y-%m-%d %H:%M:%S} UTC from {maidenhead(obs.lat, obs.lon)}: AZ {az:.2f}  EL {el:.2f}')
        return 0

    if a.cmd == 'passes':
        ts = TleStore(cfg); sat = ts.get(a.sat)
        if not sat:
            print('unknown satellite (lsr tle update?)'); return 1
        l = cfg['limits']; lim = Limits(l['az_min'], l['az_max'], l['el_min'], l['el_max'], l['vmax_az'], l['vmax_el'], l.get('anti_windup', False))
        print(f'{sat.name} (NORAD {sat.norad}), TLE epoch {sat.epoch:%Y-%m-%d}, station {maidenhead(obs.lat, obs.lon)}')
        print(f'{"AOS (UTC)":20s} {"LOS":8s} {"max el":>6s} {"AOS az":>6s} {"LOS az":>6s}  plan')
        for ps in find_passes(sat, obs, utcnow(), a.hours, 0.0, a.min_el):
            pl = plan_pass(ps, lim, None, l['allow_flip'])
            plan = f'{pl.mode:6s} wrap {pl.wrap:+5.0f}  peak az {pl.peak_az_rate:5.2f} deg/s' if pl else 'NOT FEASIBLE'
            print(f'{ps.aos.astimezone(timezone.utc):%Y-%m-%d %H:%M:%S} {ps.los:%H:%M:%S} {ps.max_el:6.1f} {ps.aos_az:6.1f} {ps.los_az:6.1f}  {plan}')
        return 0

    if a.cmd == 'status':
        if a.sim:
            cfg['rotator']['simulate'] = True
        rot = make_rotator(cfg)
        s = rot.status()
        print(s)
        for e in error_text(s.get('err', 0)):
            print('  !', e)
        return 0

    if a.cmd == 'track':
        ctx = Ctx(cfg, a.sim)
        ctx.tracker.set_target(a.sat, a.transponder)
        try:
            while True:
                ctx.tracker.step()
                sn = ctx.tracker.snapshot()
                s, st_ = sn.get('sat', {}), sn['status']
                d = sn.get('doppler', {})
                print(f'\r{sn["mode"]:11s} sat {s.get("az", 0):6.1f}/{s.get("el", 0):5.1f}  ant {st_.get("az", 0):6.1f}/{st_.get("el", 0):5.1f}'
                      + (f'  RX {d["rx"] / 1e6:.5f} TX {(d.get("tx") or 0) / 1e6:.5f}' if d else '') + '   ', end='', flush=True)
                if sn['mode'] == 'idle':
                    print('\n' + sn['message']); break
                time.sleep(1.0 / cfg['tracking']['update_hz'])
        except KeyboardInterrupt:
            ctx.tracker.stop(); print()
        return 0

    if a.cmd == 'gd77':
        from .rigs.opengd77 import OpenGD77, sats_from_tracker
        dev = OpenGD77(**cfg['rig']['opengd77'])
        try:
            if a.action == 'info':
                print(dev.radio_info())
            elif a.action == 'clock':
                print('clock set' if dev.sync_clock() else 'radio did not acknowledge')
            elif a.action == 'nmea':
                print('\n'.join(dev.read_nmea(5)))
            else:
                ts, db = TleStore(cfg), SatDB()
                names = a.sats or [e.name for e in db.entries.values()]
                print(dev.upload_keps(sats_from_tracker(ts, db, names)))
        finally:
            dev.close()
        return 0
    return 1


if __name__ == '__main__':
    sys.exit(main())
