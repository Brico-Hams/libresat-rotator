"""LSR-2 head build for FreeCAD 1.1 headless (run from the repo root, or set REPO):

    freecadcmd -c "exec(open(r'<repo>/cad/lsr2/build.py').read())"

Builds every plate of plates.PLATES as a Part solid in the head frame, exports DXF/STEP/STL per plate,
the assembly STEP with the bought-part envelopes, and build/lsr2_build_report.json. Raises on failure.
"""
import json, os, sys
import Part
from FreeCAD import Vector as V

ROOT = os.environ.get('REPO') or os.getcwd()
OUT = os.environ.get('LSR2_OUT') or ROOT   # Windows Controlled Folder Access may block freecadcmd writes: build elsewhere, copy back
sys.path.insert(0, os.path.join(ROOT, 'cad', 'lsr2'))
import params as P
import plates as PL

MAX_INTERFERENCE_MM3 = 1.0
for d in ('cnc/lsr2', 'stl/lsr2', 'cast/lsr2', 'build'):
    os.makedirs(os.path.join(OUT, d), exist_ok=True)


def plate_solid(name):
    p = PL.PLATES[name]
    u, v = p['size']
    t = p['t']
    if p['frame'] == 'xy':
        solid = Part.makeBox(u, v, t, V(-u / 2, -v / 2, p['z0']))
        cyls = [Part.makeCylinder(d / 2, t + 2, V(hu, hv, p['z0'] - 1), V(0, 0, 1)) for hu, hv, d in PL.cutouts(p)]
    else:
        z0 = p.get('z0', 0.0)
        solid = Part.makeBox(u, t, v, V(-u / 2, p['y0'], z0))
        cyls = [Part.makeCylinder(d / 2, t + 2, V(hu, p['y0'] - 1, z0 + hv), V(0, 1, 0)) for hu, hv, d in PL.cutouts(p)]
    for c in cyls:
        solid = solid.cut(c)
    return solid


def envelope_solid(b):
    return Part.makeBox(b[1] - b[0], b[3] - b[2], b[5] - b[4], V(b[0], b[2], b[4]))


shapes = {n: plate_solid(n) for n in PL.PLATES}
envs = {n: envelope_solid(b) for n, b in PL.ENVELOPES.items()}
failures = []
report = {'plates': {}, 'envelopes': list(envs), 'checks': {}}

for name, s in shapes.items():
    PL.write_dxf(name, os.path.join(OUT, 'cnc', 'lsr2', name + '.dxf'))
    s.exportStep(os.path.join(OUT, 'cnc', 'lsr2', name + '.step'))
    s.exportStl(os.path.join(OUT, 'stl', 'lsr2', name + '.stl'))
    bb = s.BoundBox
    cm3 = s.Volume / 1000.0
    valid = bool(s.isValid())
    if not valid:
        failures.append(f'{name}: invalid shape')
    if abs(cm3 * P.ALU_PLATE_G_CM3 - PL.mass_g(name)) > 0.5:
        failures.append(f'{name}: solid mass differs from plates.mass_g')
    report['plates'][name] = dict(volume_cm3=round(cm3, 3), mass_g=round(cm3 * P.ALU_PLATE_G_CM3, 1), valid=valid,
                                  bbox=[round(x, 2) for x in (bb.XMin, bb.XMax, bb.YMin, bb.YMax, bb.ZMin, bb.ZMax)])

worst = {}
for pn, ps in shapes.items():
    for en, es in envs.items():
        vol = ps.common(es).Volume
        worst[f'{pn}/{en}'] = round(vol, 4)
        if vol > MAX_INTERFERENCE_MM3:
            failures.append(f'interference {pn}/{en}: {vol:.2f} mm3')
for en, es in envs.items():
    if not es.isValid():
        failures.append(f'{en}: invalid envelope')

# --- phase 3: cast parts, patterns, core box, shafts ------------------------------------------
import cast_parts as CP
SHRINK = P.CAST['shrink']
CP.self_test()
cast = {'az_housing': CP.az_housing(), 'mast_clamp': CP.mast_clamp(), 'el_hub_a': CP.el_hub('a'), 'el_hub_b': CP.el_hub('b')}
shafts = {'az_shaft': CP.az_shaft(), 'el_shaft': CP.el_shaft()}
PAT_OF = {'az_housing': 'az_housing', 'mast_clamp': 'mast_clamp', 'el_hub_a': 'el_hub', 'el_hub_b': 'el_hub'}
pre = {'az_housing': CP.az_housing_pattern(), 'mast_clamp': CP.mast_clamp(True), 'el_hub': CP.el_hub('a', True)}
cores = Part.makeCompound(list(CP.az_cores()))
corebox = CP.az_core_box()


def scaled(s, origin):
    s = s.copy()
    r = s.scale(SHRINK, V(*origin))
    return r if r is not None else s


def dims(s):
    return (s.BoundBox.XLength, s.BoundBox.YLength, s.BoundBox.ZLength)


def bbox(s):
    bb = s.BoundBox
    return [round(x, 2) for x in (bb.XMin, bb.XMax, bb.YMin, bb.YMax, bb.ZMin, bb.ZMax)]


patterns = {n: scaled(s, CP.ORIGIN[n]) for n, s in pre.items()}
for n, s in list(cast.items()) + list(shafts.items()) + list(patterns.items()) + [('az_housing_corebox', corebox), ('az_housing_cores', cores)]:
    if not s.isValid():
        failures.append(f'{n}: invalid shape')
if abs(CP.SEAT_Z[0] - CP.SEAT_Z[1] - P.RADIAL_SPAN * 1000) > 1e-6:
    failures.append('6206 seat centres are not RADIAL_SPAN apart')
if cores.common(cast['az_housing']).Volume > MAX_INTERFERENCE_MM3:
    failures.append('az_housing cores intersect the finished housing')

report['cast'], report['shafts'] = {}, {}
for n, s in cast.items():
    pn = PAT_OF[n]
    pr = pre[pn] if n != 'el_hub_b' else pre[pn].mirror(V(0, 0, 0), V(0, 1, 0))
    if s.cut(pr).Volume > MAX_INTERFERENCE_MM3:
        failures.append(f'{n}: finished part not inside its pattern (machining allowance missing)')
    for i, ax in enumerate('xyz'):
        f, pp, pb = dims(s)[i], dims(patterns[pn])[i], dims(pre[pn])[i]
        if pp - f < (SHRINK - 1) * f - 1e-6:
            failures.append(f'{n}: pattern smaller than part + shrink on {ax}')
        if ax in CP.ALLOW_AXES[pn] and pb - f < P.CAST['machining'] - 1e-6:
            failures.append(f'{n}: pattern lacks machining allowance on {ax}')
    cm3 = s.Volume / 1000.0
    pat = patterns[pn]
    report['cast'][n] = dict(volume_cm3=round(cm3, 3), mass_g=round(cm3 * P.ALU_CAST_G_CM3, 1), valid=bool(s.isValid()),
                             machined_area_cm2=round(CP.machined_area_cm2(pn), 2), bore_solid_cm3=round(CP.bore_solid_cm3(n), 2),
                             bbox=bbox(s), pattern=pn + '_pattern', pattern_volume_cm3=round(pat.Volume / 1000.0, 3),
                             pattern_area_cm2=round(pat.Area / 100.0, 2), pattern_bbox=bbox(pat), parting=CP.PARTING[pn])
for n, s in shafts.items():
    cm3 = s.Volume / 1000.0
    d, ln = CP.shaft_stock(CP.SHAFTS[n])
    report['shafts'][n] = dict(volume_cm3=round(cm3, 3), mass_g=round(cm3 * CP.SS_G_CM3, 1), valid=bool(s.isValid()), bbox=bbox(s),
                               length_mm=CP.shaft_length(CP.SHAFTS[n]), stock_d_mm=d, stock_l_mm=ln,
                               steps=[list(x) for x in CP.SHAFTS[n]], bores=[list(x) for x in CP.SHAFT_BORES[n]])
report['clamp_m20_exit'] = CP.M20_EXIT
report['core_box'] = dict(volume_cm3=round(corebox.Volume / 1000.0, 3), bbox=bbox(corebox))

ALLOWED = {('az_shaft', 'az_gearbox'), ('el_shaft', 'el_gearbox'), ('az_shaft', 'mast_clamp'),
           ('el_shaft', 'el_hub_a'), ('el_shaft', 'el_hub_b')}   # intended fits: shaft in gearbox bore / clamp bore / hub bore
mine = {**cast, **shafts}
others = {**shapes, **envs}
for n, s in mine.items():
    for on, os_ in list(others.items()) + [(k, v) for k, v in mine.items() if k > n]:
        if (n, on) in ALLOWED or (on, n) in ALLOWED or not s.BoundBox.intersect(os_.BoundBox):
            continue
        vol = s.common(os_).Volume
        worst[f'{n}/{on}'] = round(vol, 4)
        if vol > MAX_INTERFERENCE_MM3:
            failures.append(f'interference {n}/{on}: {vol:.2f} mm3')
report['allowed_pairs'] = sorted(' / '.join(p) for p in ALLOWED)

for n, s in cast.items():
    s.exportStep(os.path.join(OUT, 'cast', 'lsr2', n + '.step'))
    s.exportStl(os.path.join(OUT, 'stl', 'lsr2', n + '.stl'))
for n, s in patterns.items():
    s.exportStep(os.path.join(OUT, 'cast', 'lsr2', n + '_pattern.step'))
    s.exportStl(os.path.join(OUT, 'stl', 'lsr2', n + '_pattern.stl'))
for n, s in (('az_housing_corebox', corebox), ('az_housing_cores', cores)):
    s.exportStep(os.path.join(OUT, 'cast', 'lsr2', n + '.step'))
    s.exportStl(os.path.join(OUT, 'stl', 'lsr2', n + '.stl'))
for n, s in shafts.items():
    s.exportStep(os.path.join(OUT, 'cnc', 'lsr2', n + '.step'))
    s.exportStl(os.path.join(OUT, 'stl', 'lsr2', n + '.stl'))

report['checks'] = dict(max_interference_mm3=max(worst.values()), limit_mm3=MAX_INTERFERENCE_MM3,
                        interference_mm3=worst, failures=failures, passed=not failures)
Part.makeCompound(list(shapes.values()) + list(envs.values()) + list(mine.values())).exportStep(
    os.path.join(OUT, 'cnc', 'lsr2', 'lsr2_head_assembly.step'))
with open(os.path.join(OUT, 'build', 'lsr2_build_report.json'), 'w', encoding='utf-8') as fh:
    json.dump(report, fh, indent=2)
if failures:
    raise RuntimeError('LSR-2 build failed: ' + '; '.join(failures))
print('LSR-2 build OK:', len(shapes), 'plates,', len(cast), 'cast parts,', len(shafts), 'shafts')
