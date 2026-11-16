"""Mobile web UI + JSON API (aiohttp). Open http://<pi>:8080 from the phone on the rotator hotspot."""
from __future__ import annotations

import asyncio
import json
import math
from pathlib import Path

from aiohttp import web

STATIC = Path(__file__).resolve().parent / 'static'


def _clean(o):
    """JSON without NaN/inf (browsers reject them)."""
    if isinstance(o, float):
        return None if (math.isnan(o) or math.isinf(o)) else o
    if isinstance(o, dict):
        return {k: _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_clean(v) for v in o]
    return o


def jr(data, status=200):
    return web.json_response(_clean(data), status=status, dumps=lambda d: json.dumps(d, default=str))


def make_app(ctx) -> web.Application:
    """ctx: object with .tracker .rot .tles .satdb .cfg .gd77_factory .save_cfg()"""
    app = web.Application()
    tr = ctx.tracker
    r = web.RouteTableDef()

    @r.get('/')
    async def index(_):
        return web.FileResponse(STATIC / 'index.html')

    @r.get('/api/status')
    async def status(_):
        return jr(tr.snapshot())

    @r.get('/api/sats')
    async def sats(req):
        q = req.query.get('q', '').upper()
        names = [n for n in ctx.tles.names() if q in n.upper()][:200]
        known = {e.name.upper() for e in ctx.satdb.entries.values()}
        return jr({'sats': names, 'with_transponders': [n for n in names if n.upper() in known or
                   (ctx.tles.get(n) and ctx.satdb.get(ctx.tles.get(n).norad))], 'tle_age_days': ctx.tles.age_days()})

    @r.get('/api/transponders')
    async def transponders(req):
        return jr([t.as_dict() for t in tr.transponders(req.query.get('sat'))])

    @r.get('/api/passes')
    async def passes(req):
        sat = req.query.get('sat')
        hours = float(req.query.get('hours', 24))
        return jr(await asyncio.to_thread(tr.passes, sat, hours))

    @r.get('/api/upcoming')
    async def upcoming(req):
        """Next passes of every satellite that has a transponder entry."""
        hours = float(req.query.get('hours', 6))
        out = []
        for e in ctx.satdb.entries.values():
            s = ctx.tles.get(str(e.norad))
            if s:
                for p in await asyncio.to_thread(tr.passes, s.name, hours):
                    p['label'] = e.name; out.append(p)
        out.sort(key=lambda p: p['aos'])
        return jr(out)

    async def body(req):
        try:
            return await req.json()
        except Exception:
            return {}

    @r.post('/api/track')
    async def track(req):
        b = await body(req)
        try:
            tr.set_target(b['sat'], b.get('transponder'))
        except KeyError as e:
            return jr({'error': str(e)}, 400)
        return jr({'ok': True, 'target': tr.target})

    @r.post('/api/stop')
    async def stop(_):
        await asyncio.to_thread(tr.stop); return jr({'ok': True})

    @r.post('/api/goto')
    async def goto(req):
        b = await body(req)
        await asyncio.to_thread(tr.manual, float(b['az']), float(b['el'])); return jr({'ok': True})

    @r.post('/api/jog')
    async def jog(req):
        b = await body(req)
        tr.mode = 'manual'; tr.target = None
        await asyncio.to_thread(ctx.rot.jog, b['dir']); return jr({'ok': True})

    @r.post('/api/park')
    async def park(_):
        tr.target = None; tr.mode = 'manual'
        await asyncio.to_thread(ctx.rot.park); return jr({'ok': True})

    @r.post('/api/home')
    async def home(_):
        await asyncio.to_thread(ctx.rot.home); return jr({'ok': True})

    @r.post('/api/cal/{what}')
    async def cal(req):
        what = req.match_info['what']
        b = await body(req)
        try:
            if what == 'sun':
                return jr(await asyncio.to_thread(tr.sun_align, bool(b.get('el'))))
            if what == 'level':
                return jr({'result': await asyncio.to_thread(ctx.rot.cal, 'LEVEL')})
            if what == 'elimu':
                return jr({'result': await asyncio.to_thread(ctx.rot.cal, 'ELIMU')})
            if what == 'az':
                return jr({'result': await asyncio.to_thread(ctx.rot.cal, 'AZ', float(b['value']))})
            if what == 'el':
                return jr({'result': await asyncio.to_thread(ctx.rot.cal, 'EL', float(b['value']))})
            if what == 'homeaz':
                return jr({'result': await asyncio.to_thread(ctx.rot.cal, 'HOMEAZ')})
        except Exception as e:
            return jr({'error': str(e)}, 400)
        return jr({'error': 'unknown calibration'}, 404)

    @r.get('/api/calibration')
    async def calibration_status(_):
        from .. import calibration as calmod
        cs = getattr(ctx.rot, 'control_status', None)
        return jr({'steps': calmod.summary(ctx.cfg), 'pointing': ctx.cfg.get('pointing', {}),
                   'control': cs() if cs else None})

    @r.post('/api/calibrate/{step}')
    async def calibrate_step(req):
        from .. import calcli
        step = req.match_info['step']
        b = await body(req)
        if step not in ('level', 'compass', 'sun', 'sun-manual', 'index'):
            return jr({'error': 'unknown calibration step'}, 404)
        mark = (float(b['az']), float(b['el'])) if step == 'sun-manual' and 'az' in b and 'el' in b else None
        try:
            return jr(await asyncio.to_thread(calcli.run_step, step, ctx.cfg, ctx.rot, False, mark))
        except Exception as e:
            return jr({'error': str(e)}, 400)

    @r.post('/api/control/clear')
    async def control_clear(_):
        fn = getattr(ctx.rot, 'clear_faults', None)
        if fn:
            fn()
        return jr({'ok': bool(fn)})

    @r.post('/api/tle/update')
    async def tle_update(_):
        return jr(await asyncio.to_thread(ctx.tles.update))

    @r.post('/api/tle/add')
    async def tle_add(req):
        b = await body(req)
        return jr({'added': ctx.tles.add_text(b.get('text', ''))})

    @r.get('/api/config')
    async def get_config(_):
        c = {k: v for k, v in ctx.cfg.items() if not k.startswith('_')}
        return jr(c)

    @r.post('/api/station')
    async def station(req):
        b = await body(req)
        st = ctx.cfg['station']
        for k in ('lat', 'lon', 'alt'):
            if k in b:
                st[k] = float(b[k])
        if 'use_gps' in b:
            st['use_gps'] = bool(b['use_gps'])
        from ..astro import Observer
        tr.obs = Observer(st['lat'], st['lon'], st['alt']); tr.gps_source = 'manual'
        tr.pass_ = tr.plan = None
        return jr({'ok': True, 'saved': ctx.save_cfg()})

    @r.post('/api/gd77/{action}')
    async def gd77(req):
        action = req.match_info['action']
        b = await body(req)
        try:
            dev = ctx.gd77_factory()
            if action == 'clock':
                ok = await asyncio.to_thread(dev.sync_clock)
                return jr({'ok': ok})
            if action == 'info':
                return jr(await asyncio.to_thread(dev.radio_info))
            if action == 'keps':
                from ..rigs.opengd77 import sats_from_tracker
                names = b.get('sats') or [e.name for e in ctx.satdb.entries.values()]
                sats = sats_from_tracker(ctx.tles, ctx.satdb, names)
                return jr(await asyncio.to_thread(dev.upload_keps, sats))
        except Exception as e:
            return jr({'error': str(e)}, 500)
        finally:
            try:
                dev.close()
            except Exception:
                pass
        return jr({'error': 'unknown action'}, 404)

    app.add_routes(r)
    app.router.add_static('/static/', STATIC)
    return app
