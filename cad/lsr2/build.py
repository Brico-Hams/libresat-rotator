"""LSR-2 phase 11 head build for FreeCAD 1.1 headless (run from the repo root, or set REPO):

    freecadcmd -c "exec(open(r'<repo>/cad/lsr2/build.py').read())"

Builds the Mk5-schematic head (body, lid, mast bracket, yoke arms, saddle, boom, clamps, lift arms, counterweights, shafts), runs the EL sweep,
then both manufacturing routes of every structural part: Route A (cast/lsr2/<part>_{finished,preform,pattern}.step|stl|3mf, cores, lost-PLA)
and Route B (cnc/lsr2/<part>_{finished,blank}.step + cam/lsr2/<part>_setups.csv), with their checks. Writes build/lsr2_build_report.json
(key `parts` feeds calc/lsr2_materials.py and scripts/bom.py). Raises on failure. Stale phase-6 files are not deleted here.
"""
import json, math, os, sys
import Part
from FreeCAD import Vector as V

ROOT = os.environ.get('REPO') or os.getcwd()
OUT = os.environ.get('LSR2_OUT') or ROOT   # Windows Controlled Folder Access may block freecadcmd writes: build elsewhere, copy back
sys.path.insert(0, os.path.join(ROOT, 'cad', 'lsr2'))
import params as P
import body as BD
import axes as AX
import route_a as RA
import route_b as RB

MAX_INTERFERENCE_MM3 = 1.0
CW_KG = 1.02                                  # PARAMETRIC counterweight mass per side
for d in ('cnc/lsr2', 'stl/lsr2', 'cast/lsr2', 'cam/lsr2', 'build'):
    os.makedirs(os.path.join(OUT, d), exist_ok=True)
for m in (BD, AX, RA, RB):
    m.self_test()

K = AX.K
failures = []
fin = {'body': BD.body(), 'lid': BD.lid(), 'mast_bracket': AX.mast_bracket(), 'yoke_arm': AX.yoke_arm(1), 'yoke_arm_neg': AX.yoke_arm(-1),
       'saddle': AX.saddle(), 'boom_clamp': AX.boom_clamp(1), 'boom_clamp_neg': AX.boom_clamp(-1)}
other = {'boom': AX.boom(), 'lift_arm_pos': AX.lift_arm(1), 'lift_arm_neg': AX.lift_arm(-1),
         'counterweight_pos': AX.counterweight(1, CW_KG), 'counterweight_neg': AX.counterweight(-1, CW_KG)}
shafts = {'az_shaft': AX.az_shaft(), 'el_shaft': AX.el_shaft(), 'el_sleeve': AX.el_sleeve()}
for n, s in {**fin, **other, **shafts}.items():
    if not s.isValid():
        failures.append(f'{n}: invalid shape')

# EL sweep: yoke, saddle, boom, clamps, lift arms and counterweights turn about the EL axis (y, x = 0, z = z_el); elevation up = rotation about -y
moving = {n: s for n, s in {**fin, **other}.items() if n.split('_')[0] in ('yoke', 'saddle', 'boom', 'lift', 'counterweight')}
static = {'body': fin['body'], 'lid': fin['lid'], 'mast_bracket': fin['mast_bracket']}
worst, sweep_worst, sweep_at = {}, 0.0, None
for ang in range(int(P.EL_RANGE[0]), int(P.EL_RANGE[1]) + 1, 5):
    for mn, ms in moving.items():
        r = ms.copy()
        r.rotate(V(0, 0, K['z_el']), V(0, 1, 0), -ang)
        for sn, ss in static.items():
            if not r.BoundBox.intersect(ss.BoundBox):
                continue
            cm = r.common(ss)
            vol = 0.0 if cm.isNull() else cm.Volume
            if vol > sweep_worst:
                sweep_worst, sweep_at = vol, f'{mn}/{sn}@{ang}'
            if vol > MAX_INTERFERENCE_MM3:
                failures.append(f'EL sweep {mn}/{sn} at {ang} deg: {vol:.2f} mm3')
for a, b in (('body', 'lid'), ('body', 'mast_bracket'), ('lid', 'mast_bracket')):
    cm = fin[a].common(fin[b])
    worst[f'{a}/{b}'] = 0.0 if cm.isNull() else round(cm.Volume, 4)
    if worst[f'{a}/{b}'] > MAX_INTERFERENCE_MM3:
        failures.append(f'interference {a}/{b}: {worst[f"{a}/{b}"]:.2f} mm3')

# --- routes A and B for every structural part (yoke arm / clamp: side +1 is built, the other is its mirror image) -----------------------
cast_dir, cnc_dir = os.path.join(OUT, 'cast', 'lsr2'), os.path.join(OUT, 'cnc', 'lsr2')
route_a = RA.build_all(cast_dir)
route_b = RB.build_all(cnc_dir)
for n in RB.PARTS:
    RB.write_csv(n, os.path.join(OUT, 'cam', 'lsr2'))
parts = {n: dict(qty=RA.QTY[n], finished_cm3=route_a[n]['finished_cm3'], route_a=route_a[n], route_b=route_b[n]) for n in RA.PARTS}
for n, p in parts.items():
    if n != 'body' and abs(p['route_b']['finished_cm3'] - p['finished_cm3']) > 0.05 * p['finished_cm3'] + 0.5:
        failures.append(f'{n}: route B variant volume differs from the finished solid by more than 5 %')

# --- other exports and the report ---------------------------------------------------------------------------------------------------
for n, s in shafts.items():
    s.exportStep(os.path.join(cnc_dir, n + '.step'))
for n, s in {**fin, **other, **shafts}.items():   # whole-head STL set for scripts/render_lsr2.py and the Blender renders
    s.exportStl(os.path.join(OUT, 'stl', 'lsr2', n + '.stl'))
report = dict(rev=P.REV, parts=parts, shafts={}, items={}, mass_check={})
for n, s in shafts.items():
    cm3 = s.Volume / 1000.0
    d, ln = AX.shaft_stock(AX.SHAFTS[n])
    report['shafts'][n] = dict(volume_cm3=round(cm3, 3), mass_g=round(cm3 * AX.SS_G_CM3, 1), length_mm=AX.shaft_length(AX.SHAFTS[n]), stock_d_mm=d, stock_l_mm=ln,
                               steps=[list(x) for x in AX.SHAFTS[n]], bores=[list(x) for x in AX.SHAFT_BORES[n]])
bm = other['boom']
report['items']['cross_boom'] = dict(volume_cm3=round(bm.Volume / 1000.0, 3), mass_g=round(bm.Volume / 1000.0 * 2.70, 1),
                                     section_mm=[K['boom_w'], K['boom_w'], K['boom_t']], length_mm=K['boom_len'])
for n, est in {'body': 5.4, 'lid': 1.3}.items():   # inputs.HEAD estimates (kg): flagged when > 10 % apart, never a failure
    kg = parts[n]['finished_cm3'] * P.ALU_CAST_G_CM3 / 1000.0
    report['mass_check'][n] = dict(finished_kg=round(kg, 3), inputs_kg=est, differs_over_10pct=abs(kg - est) > 0.1 * est)
report['checks'] = dict(limit_mm3=MAX_INTERFERENCE_MM3, interference_mm3=worst, failures=failures, passed=not failures,
                        el_sweep=dict(range_deg=list(P.EL_RANGE), step_deg=5, moving=sorted(moving), worst_mm3=round(sweep_worst, 4), worst_at=sweep_at))
Part.makeCompound(list(fin.values()) + list(other.values()) + list(shafts.values())).exportStep(os.path.join(cnc_dir, 'lsr2_head_assembly.step'))
with open(os.path.join(OUT, 'build', 'lsr2_build_report.json'), 'w', encoding='utf-8') as fh:
    json.dump(report, fh, indent=2)
if failures:
    raise RuntimeError('LSR-2 build failed: ' + '; '.join(failures))
print('LSR-2 phase 11 build OK:', len(parts), 'structural parts, routes A and B,', len(shafts), 'shafts')
