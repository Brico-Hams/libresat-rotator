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
for d in ('cnc/lsr2', 'stl/lsr2', 'build'):
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

report['checks'] = dict(max_interference_mm3=max(worst.values()), limit_mm3=MAX_INTERFERENCE_MM3,
                        interference_mm3=worst, failures=failures, passed=not failures)
Part.makeCompound(list(shapes.values()) + list(envs.values())).exportStep(
    os.path.join(OUT, 'cnc', 'lsr2', 'lsr2_head_assembly.step'))
with open(os.path.join(OUT, 'build', 'lsr2_build_report.json'), 'w', encoding='utf-8') as fh:
    json.dump(report, fh, indent=2)
if failures:
    raise RuntimeError('LSR-2 build failed: ' + '; '.join(failures))
print('LSR-2 build OK:', len(shapes), 'plates')
