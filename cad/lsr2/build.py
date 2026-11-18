"""LSR-2 head build for FreeCAD 1.1 headless (run from the repo root, or set REPO):

    freecadcmd -c "exec(open(r'<repo>/cad/lsr2/build.py').read())"

LSR2_DESIGN=mk4 (default): replica of the SARCTrac Mk4 (SARCNET, MIT, third_party/sarctrac-mk4): mk4_build.py exports STL / STEP / DXF / scene / report from
the original Rotator.FCStd. LSR2_DESIGN=cast: the optional phase 11 cast / CNC open-box variant described below (untouched).

Phase 11 (cast): Builds the Mk5-schematic head (body, lid, mast bracket, yoke arms, saddle, boom, clamps, lift arms, counterweights, shafts), runs the EL sweep,
then both manufacturing routes of every structural part: Route A (cast/lsr2/<part>_{finished,preform,pattern}.step|stl|3mf, cores, lost-PLA)
and Route B (cnc/lsr2/<part>_{finished,blank}.step + cam/lsr2/<part>_setups.csv), with their checks. Writes build/lsr2_build_report.json
(key `parts` feeds calc/lsr2_materials.py and scripts/bom.py). Phase 11e: also bought-part visual models (stl/lsr2/visual), route B blank STLs, the editable
cad/lsr2/LSR2_assembly.FCStd (groups Bought / Machined / Cast / Printed pattern, Spreadsheet Params), cad/lsr2/LSR2_assembly.step and
build/lsr2_render_scene.json (assembly_doc.py, parts_table.py, bought_parts.py). Raises on failure. Stale phase-6 files are not deleted here.
Phase 7: the LSR-WG30 gearbox halves (cast/lsr2/gearbox_half_*, core boxes, stl/lsr2/gearbox_*.stl, report key `gearbox`) are always built; the head uses the bought
NMRV030 envelope unless LSR2_GEARBOX=lsr_wg30 (params.GEARBOX_SOURCE), which swaps in the real housings and adds the gearbox interference / EL sweep checks.
Second variant: LSR2_GEARBOX=lsr_wg30 LSR2_OUT=<other folder> freecadcmd -c "exec(open(r'<repo>/cad/lsr2/build.py').read())".
"""
import json, math, os, sys
import Part
from FreeCAD import Vector as V

ROOT = os.environ.get('REPO') or os.getcwd()
OUT = os.environ.get('LSR2_OUT') or ROOT   # Windows Controlled Folder Access may block freecadcmd writes: build elsewhere, copy back
def _hard_exit(code):
    """End the process without DLL/thread teardown: ExitProcess (os._exit) can hang in FreeCAD/OCCT on Windows after the build has finished.
    Every print already flushes; flushing stderr here could block forever on a pipe nobody drains, so it is not done."""
    if os.name == 'nt':
        try:
            import ctypes
            k32 = ctypes.WinDLL('kernel32')   # typed pseudo handle (-1), otherwise TerminateProcess fails; tried first, it needs no helper process
            k32.GetCurrentProcess.restype = ctypes.c_void_p
            k32.TerminateProcess.argtypes = [ctypes.c_void_p, ctypes.c_uint]
            k32.TerminateProcess(k32.GetCurrentProcess(), code)
        except BaseException:
            pass
        try:                                  # NtTerminateProcess(NULL handle) ends the calling process without any user-mode teardown
            ctypes.WinDLL('ntdll').NtTerminateProcess(ctypes.c_void_p(0), ctypes.c_long(code))
        except BaseException:
            pass
        try:                                  # fallback: an external taskkill ends the process even when in-process exit hangs in OCCT/FreeCAD teardown
            import subprocess
            subprocess.run(['taskkill', '/F', '/PID', str(os.getpid())], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=20)
        except BaseException:
            pass
    os._exit(code)


if '_BUILD_INNER' not in globals():        # freecadcmd -c swallows tracebacks: run the whole script once more inside try/except and print/save the traceback
    import traceback
    _BUILD_INNER = True
    try:
        exec(compile(open(os.path.join(ROOT, 'cad', 'lsr2', 'build.py'), encoding='utf-8').read(), 'build.py', 'exec'), globals())
    except BaseException:
        _tb = traceback.format_exc()
        print('BUILD_FAILED\n' + _tb, flush=True)
        for _d in (OUT, ROOT):
            try:
                os.makedirs(os.path.join(_d, 'build'), exist_ok=True)
                with open(os.path.join(_d, 'build', 'lsr2_build_error.txt'), 'w', encoding='utf-8') as _fh:
                    _fh.write(_tb)
            except OSError:
                pass
        _hard_exit(1)                      # SystemExit inside freecadcmd -c can drop into the interactive console and hang on stdin: hard-exit instead
    _hard_exit(0)
sys.path.insert(0, os.path.join(ROOT, 'cad', 'lsr2'))
DESIGN = (os.environ.get('LSR2_DESIGN') or 'mk4').lower()   # 'mk4' = SARCTrac Mk4 replica (default), 'cast' = phase 11 cast / CNC open-box head


def stage(msg):
    """Flushed progress line: a native FreeCAD crash or kill loses buffered stdout, so the last stage printed names the failing step."""
    print('BUILD_STAGE', msg, flush=True)
    try:                                       # freecadcmd may lose stdout and the traceback: the log file survives a crash
        with open(os.path.join(OUT, 'build', 'lsr2_build_stage.log'), 'a', encoding='utf-8') as fh:
            fh.write(msg + '\n')
    except OSError:
        pass


os.makedirs(os.path.join(OUT, 'build'), exist_ok=True)
if os.path.exists(os.path.join(OUT, 'build', 'lsr2_build_stage.log')):
    os.remove(os.path.join(OUT, 'build', 'lsr2_build_stage.log'))
if DESIGN not in ('mk4', 'cast'):
    print('LSR-2 build failed: LSR2_DESIGN must be mk4 or cast, got ' + DESIGN, flush=True)
    _hard_exit(1)
if DESIGN == 'mk4':
    import mk4_build as MB
    import parts_table as PT
    import tolerances as TL
    try:
        _totals = MB.build(OUT, stage)         # raises with the list of failed exports; writes scene, report, STL / STEP / DXF
        stage('parts table and tolerances')
        PT.self_test()                         # reads the scene just written
        TL.self_test()
    except BaseException:
        print('LSR-2 build failed (see build/lsr2_build_report.json and the traceback below)', flush=True)
        raise
    print('LSR-2 phase 11 build OK: mk4 replica,', _totals['instances'], 'instances,', _totals['made'], 'made parts, made mass', _totals['made_mass_g'], 'g', flush=True)
    _hard_exit(0)
import params as P
import body as BD
import axes as AX
import route_a as RA
import route_b as RB
import parts_table as PT
import bought_parts as BP
import gearbox as GBX

MAX_INTERFERENCE_MM3 = 1.0
CW_KG = 1.02                                  # PARAMETRIC counterweight mass per side


stage('self-tests')
for d in ('cnc/lsr2', 'stl/lsr2/visual', 'cast/lsr2', 'cam/lsr2', 'build', 'cad/lsr2'):
    os.makedirs(os.path.join(OUT, d), exist_ok=True)
for m in (BD, AX, RA, RB, PT, GBX):
    m.self_test()

K = AX.K
failures = []
stage('head solids')
fin = {'body': BD.body(), 'lid': BD.lid(), 'mast_bracket': AX.mast_bracket(), 'yoke_arm': AX.yoke_arm(1), 'yoke_arm_neg': AX.yoke_arm(-1),
       'saddle': AX.saddle(), 'boom_clamp': AX.boom_clamp(1), 'boom_clamp_neg': AX.boom_clamp(-1)}
other = {'boom': AX.boom(), 'lift_arm_pos': AX.lift_arm(1), 'lift_arm_neg': AX.lift_arm(-1),
         'counterweight_pos': AX.counterweight(1, CW_KG), 'counterweight_neg': AX.counterweight(-1, CW_KG)}
shafts = {'az_shaft': AX.az_shaft(), 'el_shaft': AX.el_shaft(), 'el_sleeve': AX.el_sleeve()}
for n, s in {**fin, **other, **shafts}.items():
    if not s.isValid():
        failures.append(f'{n}: invalid shape')

stage('EL sweep')
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


def vol0(a, b):
    cm = a.common(b)
    return 0.0 if cm.isNull() else cm.Volume


# Gearbox (phase 7): the bought NMRV030 envelope is the reference; with GEARBOX_SOURCE = 'lsr_wg30' the real housing may not interfere more than the envelope does.
stage('gearbox interference')
wg30 = P.GEARBOX_SOURCE == 'lsr_wg30'
env = BP.gearbox_solids('envelope')
hous = BP.gearbox_solids('housing') if wg30 else None
gb_int = {}
for k in ('az', 'el'):
    for sn, ss in static.items():
        gb_int[f'{k}/{sn}'] = dict(envelope=round(vol0(env[k], ss), 3))
        if wg30:
            gb_int[f'{k}/{sn}']['housing'] = round(vol0(hous[k], ss), 3)
            if gb_int[f'{k}/{sn}']['housing'] > gb_int[f'{k}/{sn}']['envelope'] + MAX_INTERFERENCE_MM3:
                failures.append(f'gearbox {k} housing / {sn}: {gb_int[f"{k}/{sn}"]["housing"]:.2f} mm3 (envelope {gb_int[f"{k}/{sn}"]["envelope"]:.2f})')
gb_sweep = 0.0
if wg30:                                      # EL sweep of the moving group against the real housings (not only the static body parts)
    for ang in range(int(P.EL_RANGE[0]), int(P.EL_RANGE[1]) + 1, 5):
        for mn, ms in moving.items():
            r = ms.copy()
            r.rotate(V(0, 0, K['z_el']), V(0, 1, 0), -ang)
            for k in ('az', 'el'):
                if r.BoundBox.intersect(hous[k].BoundBox):
                    over = vol0(r, hous[k]) - vol0(r, env[k])
                    gb_sweep = max(gb_sweep, over)
                    if over > MAX_INTERFERENCE_MM3:
                        failures.append(f'EL sweep {mn}/{k} gearbox housing at {ang} deg: {over:.2f} mm3 more than the envelope')

# --- routes A and B for every structural part (yoke arm / clamp: side +1 is built, the other is its mirror image) -----------------------
cast_dir, cnc_dir = os.path.join(OUT, 'cast', 'lsr2'), os.path.join(OUT, 'cnc', 'lsr2')
stage('route A')
route_a = RA.build_all(cast_dir)
stage('gearbox halves')
gearbox_report = GBX.build(cast_dir, os.path.join(OUT, 'stl', 'lsr2'))    # LSR-WG30 halves, core boxes, visual STLs: always built, used when GEARBOX_SOURCE = 'lsr_wg30'
gearbox_report.update(interference_mm3=gb_int, el_sweep_extra_mm3=round(gb_sweep, 4))
stage('route B')
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
for n, s in {**fin, **other, **shafts}.items():   # whole-head STL set for the Blender renders
    s.exportStl(os.path.join(OUT, 'stl', 'lsr2', n + '.stl'))
stage('exports and bought parts')
bought = BP.build_all()                           # bought parts and customer items: visual models, never part of the fabricated mass
for n, s in bought.items():
    s.exportStl(os.path.join(OUT, 'stl', 'lsr2', 'visual', n + '.stl'))
    s.exportStl(os.path.join(OUT, 'stl', 'lsr2', n + '.stl'))   # flat copy too: copy-back of stl/lsr2/*.stl and drawings.py find it without the subfolder
for n in RB.PARTS:                                # route B blanks as STL for the "CNC blanks" render
    Part.read(os.path.join(cnc_dir, n + '_blank.step')).exportStl(os.path.join(cnc_dir, n + '_blank.stl'))
report = dict(rev=P.REV, parts=parts, shafts={}, items={}, mass_check={}, gearbox=gearbox_report)
for n, s in shafts.items():
    cm3 = s.Volume / 1000.0
    d, ln = AX.shaft_stock(AX.SHAFTS[n])
    report['shafts'][n] = dict(volume_cm3=round(cm3, 3), mass_g=round(cm3 * AX.SS_G_CM3, 1), length_mm=AX.shaft_length(AX.SHAFTS[n]), stock_d_mm=d, stock_l_mm=ln,
                               steps=[list(x) for x in AX.SHAFTS[n]], bores=[list(x) for x in AX.SHAFT_BORES[n]])
bm = other['boom']
report['items']['cross_boom'] = dict(volume_cm3=round(bm.Volume / 1000.0, 3), mass_g=round(bm.Volume / 1000.0 * 2.70, 1),
                                     section_mm=[K['boom_w'], K['boom_w'], K['boom_t']], length_mm=K['boom_len'])
report['items']['lift_arm'] = dict(volume_cm3=round(other['lift_arm_pos'].Volume / 1000.0, 3), mass_g=round(other['lift_arm_pos'].Volume / 1000.0 * 2.70, 1))
report['items']['counterweight'] = dict(mass_g=CW_KG * 1000.0, length_mm=round(AX.cw_length(CW_KG), 1))
for n, est in {'body': 5.4, 'lid': 1.3}.items():   # inputs.HEAD estimates (kg): flagged when > 10 % apart, never a failure
    kg = parts[n]['finished_cm3'] * P.ALU_CAST_G_CM3 / 1000.0
    report['mass_check'][n] = dict(finished_kg=round(kg, 3), inputs_kg=est, differs_over_10pct=abs(kg - est) > 0.1 * est)
report['checks'] = dict(limit_mm3=MAX_INTERFERENCE_MM3, interference_mm3=worst, failures=failures, passed=not failures,
                        el_sweep=dict(range_deg=list(P.EL_RANGE), step_deg=5, moving=sorted(moving), worst_mm3=round(sweep_worst, 4), worst_at=sweep_at))
Part.makeCompound(list(fin.values()) + list(other.values()) + list(shafts.values())).exportStep(os.path.join(cnc_dir, 'lsr2_head_assembly.step'))
stage('assembly document')
import assembly_doc as AD
head = {**fin, **other, **shafts, **bought}
missing = sorted(set(PT.BY_MODEL) - set(head))
if missing:
    failures.append('parts_table models without a shape: ' + ', '.join(missing))
else:
    scene = AD.build(OUT, head, cast_dir, dict(stl_dir='stl/lsr2', cast_dir='cast/lsr2', cnc_dir='cnc/lsr2', floor_z=BP.MAST_BOTTOM, lid_lift=PT.EXPLODE['lid'][2],
                                               cast_parts=list(RA.PARTS), cnc_parts=list(RB.PARTS), hero_el=30.0))
    AD.save_scene(OUT, scene)
with open(os.path.join(OUT, 'build', 'lsr2_build_report.json'), 'w', encoding='utf-8') as fh:
    json.dump(report, fh, indent=2)
if failures:
    print('LSR-2 build failed: ' + '; '.join(failures), flush=True)
    _hard_exit(1)
print('LSR-2 phase 11 build OK:', len(parts), 'structural parts, routes A and B,', len(shafts), 'shafts', flush=True)
_hard_exit(0)   # freecadcmd otherwise drops into its interactive console and waits on stdin forever
