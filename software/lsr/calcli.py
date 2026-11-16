"""`lsr calibrate ...` and `lsr pointing fit` (thin glue between the CLI, the rotator and calibration.py / pointing.py)."""
from __future__ import annotations

import json
import time
from pathlib import Path

from . import calibration as cal
from . import config as cfgmod
from .astro import Observer
from .pointing import FIT_DEFAULT, NAMES, PointingModel, Point, load_points, save_points
from .rotator import make_rotator

ACCEPT_RMS_DEG = 0.1


def _base(rot):
    return getattr(rot, 'base', rot) if type(rot).__name__ == 'CorrectedRotator' else rot


def _points_path(cfg) -> Path:
    return Path(cfg['calibration']['points_file']).expanduser()


def _add_point(cfg, res, note):
    p = cal.point_from(res, note)
    if p:
        path = _points_path(cfg)
        path.parent.mkdir(parents=True, exist_ok=True)
        pts = load_points(str(path)) if path.exists() else []
        save_points(str(path), pts + [p])


def _move_fn(base, sleep=time.sleep):
    def move(az, el):
        base.set_pos(az, el)
        sleep(0.2)
        cal.wait_idle(base, 60.0, sleep=sleep)
    return move


def run_step(step: str, cfg: dict, rot, sim: bool = False, mark: tuple | None = None, ellipsoid: bool = False) -> dict:
    base = _base(rot)
    cc = cfg['calibration']
    st = base.status() or {}
    obs, when, src = cal.station_and_time(st, cfg)
    if step == 'level':
        res = cal.calibrate_level(lambda: tuple(base.raw()['acc_base']), threshold=cc['level_threshold_deg'])
    elif step == 'compass':
        raw = base.raw() if hasattr(base, 'raw') else {}
        if not cc['magnetometer'].get('enabled') or not (raw or {}).get('mag'):
            res = cal.calibrate_compass(None, None, 0.0)
        else:
            mc, mv = cal.MagCal(), _move_fn(base)
            for az in range(0, 360, 15):                  # one slow turn of the base IMU through all headings
                mv(az, st.get('el', 0.0))
                mc.add(base.raw()['mag'])
            (mc.fit_ellipsoid if ellipsoid else mc.fit_minmax)()
            decl, dsrc = cal.resolve_declination(cfg, obs, when)
            res = cal.calibrate_compass(lambda: base.raw()['mag'], lambda: tuple(base.raw()['acc_base']), decl, mc,
                                        source=dsrc)
            res['magcal'] = mc.as_dict()
    elif step in ('sun', 'sun-manual'):
        model = PointingModel.from_config(cfg['pointing'])
        if step == 'sun-manual':
            az, el = mark if mark else base.get_pos()
            res = cal.sun_mark(obs, when, az, el, model)
        elif sim:
            world = cal.SimSunWorld(obs, PointingModel({'az_off': 3.1, 'el_off': -1.2}), cal.gps_clock(when), noise=0.005)
            res = cal.sun_scan(world.move, world.read, obs, cal.gps_clock(when), model, cc['sun_sensor']['span'],
                               cc['sun_sensor']['step'])
        else:
            cmd = cc['sun_sensor'].get('command')
            if not cmd:
                return dict(valid=False, status='set calibration.sun_sensor.command (prints one number) or use sun-manual')
            res = cal.sun_scan(_move_fn(base), cal.command_sensor(cmd), obs, cal.gps_clock(when), model,
                               cc['sun_sensor']['span'], cc['sun_sensor']['step'])
        if res.get('point'):
            _add_point(cfg, res, step)
    elif step == 'index':
        res = cal.calibrate_index(base)
    else:
        raise ValueError(f'unknown calibration step {step!r}')
    res['position_source'] = src
    out = cal.save_result(cfg, step, res)
    cal.apply_to_pointing(cfg)
    cfgmod.save(cfg)
    return out


def calibrate(cfg: dict, step: str, sim: bool = False, mark: tuple | None = None, ellipsoid: bool = False) -> int:
    if sim:
        cfg['rotator']['simulate'] = True
    rot = make_rotator(cfg)
    steps = ('level', 'compass', 'sun', 'index') if step == 'all' else (step,)
    code = 0
    for s in steps:
        if step == 'all' and s == 'sun' and not sim and not cfg['calibration']['sun_sensor'].get('command'):
            print('sun: skipped (no sun sensor configured; run `lsr calibrate sun-manual`)')
            continue
        res = run_step(s, cfg, rot, sim, mark, ellipsoid)
        print(f'{s:8s} {"OK " if res.get("valid") else "-- "} {res.get("status", "")}  '
              + json.dumps({k: v for k, v in res.items() if k not in ('status', 'time', 'magcal', 'valid')}))
        code |= 0 if res.get('valid') or res.get('skipped') else 1
    return code


def pointing_fit(cfg: dict, csv_path: str, terms: str | None = None, save: bool = False, enable: bool = False) -> int:
    pts = load_points(csv_path)
    n = len(pts)
    if n < 2:
        print('need at least 2 calibration points')
        return 1
    names = [t.strip() for t in terms.split(',')] if terms else list(NAMES[:len(NAMES) if n >= 12 else 4 if n >= 6 else 2])
    model = PointingModel(refraction=cfg['pointing'].get('refraction', False))     # fresh fit from the raw mount readings
    before = model.evaluate(pts)
    res = model.fit(pts, names)
    print(f'{n} points, terms: {", ".join(names)}')
    print(f'RMS before correction {before.rms:.3f} deg -> after {res.rms:.3f} deg (max {res.max_err:.3f} deg)')
    for k in NAMES:
        print(f'  {k:8s} {res.params[k]:+8.4f} deg' + ('' if k in names else '   (not fitted)'))
    ok = res.rms < ACCEPT_RMS_DEG
    print('acceptance (RMS < 0.1 deg):', 'PASS' if ok else 'FAIL: add points over the whole sky or check the mechanics')
    if save:
        cfg['pointing'].update(params=dict(res.params), rms=round(res.rms, 4), n=n)
        if enable and ok:
            cfg['pointing']['enabled'] = True
        print('saved to', cfgmod.save(cfg))
    return 0 if ok else 2
