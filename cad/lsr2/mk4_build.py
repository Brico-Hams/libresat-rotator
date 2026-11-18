"""LSR-2 = SARCTrac Mk4 replica: FreeCAD 1.1 headless build (called by build.py, LSR2_DESIGN=mk4). Needs FreeCAD; mk4_params.py is the plain-Python side.

Opens third_party/sarctrac-mk4/FreeCAD/Rotator.FCStd read-only (never saved: the editable copy cad/lsr2/LSR2_assembly.FCStd is a baked Part::Feature
document written with saveAs), walks App::Part / group / App::Link / Assembly containers with their placements and groups the solid leaves into instances:
instance = outermost App::Link below the root (else the nearest container, else the leaf), part = mk4_params.classify(). Per instance an STL
(stl/lsr2/<snake>.stl, 0.2 mm), per made part a finished STEP (cnc/lsr2/<snake>.step), per 2 mm laser part a flat DXF (cnc/lsr2/laser/<snake>.dxf),
plus cad/lsr2/LSR2_assembly.step, build/lsr2_render_scene.json and build/lsr2_build_report.json. Export failures are collected and raised at the end.
"""
import json
import math
import os
import time
import FreeCAD as App
import Part
from FreeCAD import Vector as V
import mk4_params as MP

MESH_TOL = 0.2
INTERFERENCE_MM3 = 1.0
INTERFERENCE_LIMIT_S = 120.0
EL_TEST_ANGLES = (-30, 0, 45, 90, 150)


def doc_stem(doc):
    return os.path.splitext(os.path.basename(doc.FileName or ''))[0] or doc.Name


def open_part_doc(stem, src):
    for d in App.listDocuments().values():
        if doc_stem(d).lower() == stem.lower():
            return d
    return App.openDocument(os.path.join(MP.FC_DIR, src))


def walk(obj, parent, own, trail, out, problems, seen, depth=0):
    """Collect the solid leaves below obj as dicts(label, shape in global coordinates, trail, doc).
    parent = placement of obj's parent frame; own = apply obj.Placement (False for the target of an App::Link without LinkTransform)."""
    if depth > 40:
        problems.append('nesting too deep at ' + obj.Label)
        return
    pl = parent * (obj.Placement if own and hasattr(obj, 'Placement') else App.Placement())
    if obj.isDerivedFrom('App::Link'):
        tgt = obj.LinkedObject
        if tgt is None:
            problems.append('unresolved link ' + obj.Label)
            return
        walk(tgt, pl, bool(obj.LinkTransform), trail + [('link', obj.Label)], out, problems, seen, depth + 1)
    elif obj.isDerivedFrom('Part::Feature'):
        sh = obj.Shape
        if sh.isNull() or not sh.Solids:
            return
        if not obj.isDerivedFrom('PartDesign::Body') and any(o.isDerivedFrom('Part::Feature') and not o.isDerivedFrom('PartDesign::Feature') for o in obj.InList):
            return   # input of a boolean / mirror: intermediate, not an instance
        s = sh.copy()
        s.Placement = pl
        k = (obj.Document.Name, obj.Name, tuple(round(v, 3) for v in pl.Base) + tuple(round(v, 4) for v in pl.Rotation.Q))
        if k not in seen:
            seen.add(k)
            out.append(dict(label=obj.Label, shape=s, trail=trail, doc=doc_stem(obj.Document)))
    elif hasattr(obj, 'Group'):
        for c in obj.Group:
            walk(c, pl, True, trail + [('cont', obj.Label)], out, problems, seen, depth + 1)


def instance_key(item):
    links = [n for k, n in item['trail'] if k == 'link']
    conts = [n for k, n in item['trail'] if k == 'cont']
    return links[0] if links else (conts[-1] if conts else item['label'])


def part_shapes(p):
    """Solids of a part file in its own frame (for the finished STEP and the DXF)."""
    d = open_part_doc(p['source_stem'], p['source'])
    items = []
    for r in d.RootObjects:
        walk(r, App.Placement(), True, [], items, [], set())
    if not items:
        raise RuntimeError('no solids in ' + p['source'])
    return [i['shape'] for i in items]


def _to_local(shape, inv):
    s = shape.copy()
    s.Placement = inv.multiply(shape.Placement)
    return s


def write_stl(shape, path):
    try:
        import MeshPart
        MeshPart.meshFromShape(Shape=shape, LinearDeflection=MESH_TOL, AngularDeflection=math.radians(30), Relative=False).write(path)
    except Exception:
        shape.exportStl(path)


def flat_outline(shape):
    """Wires of the largest planar face of every solid, turned into the XY plane (the sheet face of a 2 mm laser part)."""
    planar = [f for f in shape.Faces if isinstance(f.Surface, Part.Plane)]
    if not planar:
        raise RuntimeError('no planar face')
    big = max(planar, key=lambda f: f.Area)
    s = shape.copy()
    s.transformShape(App.Placement(V(), App.Rotation(big.normalAt(0, 0), V(0, 0, 1))).toMatrix())
    wires = []
    for sol in s.Solids:
        tops = [f for f in sol.Faces if isinstance(f.Surface, Part.Plane) and abs(abs(f.normalAt(0, 0).z) - 1) < 1e-6]
        if tops:
            for w in max(tops, key=lambda f: f.Area).Wires:
                w = w.copy()
                w.translate(V(0, 0, -w.BoundBox.ZMin))
                wires.append(w)
    comp = Part.makeCompound(wires)
    bb = comp.BoundBox
    comp.translate(V(-bb.XMin, -bb.YMin, 0))
    return comp


def write_dxf(shape, path):
    d = App.newDocument('dxf_tmp')
    try:
        o = d.addObject('Part::Feature', 'Outline')
        o.Shape = shape
        try:
            import importDXF
            importDXF.export([o], path)
        except Exception:
            import TechDraw
            with open(path, 'w', encoding='utf-8') as fh:
                fh.write(TechDraw.projectToDXF(shape, V(0, 0, 1)))
    finally:
        App.closeDocument(d.Name)


def interference(insts, axis):
    """common() volume of every made EL-group instance (rotated about the EL axis) against every made fixed instance; skipped after INTERFERENCE_LIMIT_S."""
    made = [i for i in insts if i['made']]
    el = [i for i in made if i['group'] == 'el']
    fixed = [i for i in made if i['group'] != 'el']
    res = dict(limit_mm3=INTERFERENCE_MM3, angles_deg=list(EL_TEST_ANGLES), hits=[], worst_mm3=0.0, skipped=None)
    t0 = time.time()
    p, d = V(*axis['point']), V(*axis['dir'])
    for ang in EL_TEST_ANGLES:
        for e in el:
            r = e['comp'].copy()
            r.rotate(p, d, MP.EL_SIGN * ang)
            for f in fixed:
                if time.time() - t0 > INTERFERENCE_LIMIT_S:
                    res['skipped'] = 'interference check skipped after %.0f s (limit %.0f s)' % (time.time() - t0, INTERFERENCE_LIMIT_S)
                    return res
                if not r.BoundBox.intersect(f['comp'].BoundBox):
                    continue
                try:
                    cm = r.common(f['comp'])
                    vol = 0.0 if cm.isNull() else cm.Volume
                except Exception as ex:
                    res['hits'].append(dict(el=e['name'], other=f['name'], angle=ang, error=str(ex)))
                    continue
                res['worst_mm3'] = max(res['worst_mm3'], round(vol, 3))
                if vol > INTERFERENCE_MM3:
                    res['hits'].append(dict(el=e['name'], other=f['name'], angle=ang, mm3=round(vol, 2)))
    res['seconds'] = round(time.time() - t0, 1)
    return res


def build(out, stage=print):
    failures = []
    for d in ('stl/lsr2', 'cnc/lsr2/laser', 'cad/lsr2', 'build'):
        os.makedirs(os.path.join(out, d), exist_ok=True)
    stage('mk4 self-test')
    MP.self_test()

    stage('open ' + MP.ASSEMBLY)
    doc = App.openDocument(os.path.join(MP.FC_DIR, MP.ASSEMBLY))
    stage('walk assembly')
    items, problems, seen = [], [], set()
    for r in doc.RootObjects:
        walk(r, App.Placement(), True, [], items, problems, seen)
    failures += sorted(set(problems))
    if not items:
        raise RuntimeError('no solids found in ' + MP.ASSEMBLY + '; ' + '; '.join(failures))

    by_key = {}
    for it in items:
        by_key.setdefault(instance_key(it), []).append(it)
    insts, used = [], {}
    for key, its in by_key.items():
        found = MP.classify(its[0]['doc'], key)
        part = found or MP.UNKNOWN
        name = MP.snake(key)
        used[name] = used.get(name, 0) + 1
        if used[name] > 1:
            name += '_%d' % used[name]
        made = MP.is_made(part)
        solids = [(it['label'], s) for it in its for s in it['shape'].Solids]
        mass = round(sum(abs(s.Volume) / 1000.0 * MP.DENSITY[MP.LEAF_MATERIAL.get(lbl, part['material'])] for lbl, s in solids), 1) if made else None
        insts.append(dict(name=name, key=key, part=part, group=MP.group_of(key), made=made, vol=sum(abs(s.Volume) for _, s in solids) / 1000.0,
                          mass=mass, comp=Part.makeCompound([it['shape'] for it in its]), known=found is not None))
    stage('%d instances, %d made' % (len(insts), sum(i['made'] for i in insts)))

    stage('STL')
    for i in insts:
        try:
            write_stl(i['comp'], os.path.join(out, 'stl', 'lsr2', i['name'] + '.stl'))
        except Exception as ex:
            failures.append('%s: STL: %s' % (i['name'], ex))

    stage('STEP and DXF per part')
    done = set()
    for i in insts:
        p = i['part']
        if not i['made'] or p['name'] in done:
            continue
        done.add(p['name'])
        try:
            shapes = [x['shape'] for x in by_key[i['key']]]
            if p['source_stem'] != 'Rotator':
                # the stand-alone part file restores without solids (blocked FastenersCmd objects), so take the instance from the assembly
                # and bring it to the origin of its first solid's own frame
                try:
                    shapes = part_shapes(p)
                except Exception:
                    inv = shapes[0].Placement.inverse()
                    shapes = [_to_local(s, inv) for s in shapes]
            comp = Part.makeCompound(shapes)
            comp.exportStep(os.path.join(out, 'cnc', 'lsr2', MP.snake(p['name']) + '.step'))
            if p['process'] == 'laser_2mm':
                write_dxf(flat_outline(comp), os.path.join(out, 'cnc', 'lsr2', 'laser', MP.snake(p['name']) + '.dxf'))
        except Exception as ex:
            failures.append('%s: STEP/DXF: %s' % (p['name'], ex))

    stage('assembly STEP and FCStd')
    try:
        step = os.path.join(out, 'cad', 'lsr2', 'LSR2_assembly.step')
        Part.makeCompound([i['comp'] for i in insts]).exportStep(step)
        # the plain STEP (~120 MB) exceeds GitHub's 100 MB file limit: the repo keeps the zip, the .step is git-ignored
        import zipfile
        with zipfile.ZipFile(step + '.zip', 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as z:
            z.write(step, 'LSR2_assembly.step')
    except Exception as ex:
        failures.append('LSR2_assembly.step: %s' % ex)
    try:
        nd = App.newDocument('LSR2_assembly')
        groups = {c: nd.addObject('App::DocumentObjectGroup', 'G_' + c) for c in MP.COLOURS}
        for c, g in groups.items():
            g.Label = MP.COLOUR_LABEL[c]
        for i in insts:
            o = nd.addObject('Part::Feature', i['name'])
            o.Shape = i['comp']
            o.Label = i['key']
            for prop, val in (('Part', i['part']['name']), ('Material', i['part']['material']), ('Process', i['part']['process']), ('Group', i['group'])):
                o.addProperty('App::PropertyString', prop, 'LSR2')
                setattr(o, prop, val)
            groups[i['part']['colour']].addObject(o)
        nd.recompute()
        nd.saveAs(os.path.join(out, 'cad', 'lsr2', 'LSR2_assembly.FCStd'))
    except Exception as ex:
        failures.append('LSR2_assembly.FCStd: %s' % ex)

    stage('interference')
    inter = interference(insts, MP.EL_AXIS)

    stage('scene and report')
    boxes = {i['name']: i['comp'].BoundBox for i in insts}
    lo = [min(getattr(b, a) for b in boxes.values()) for a in ('XMin', 'YMin', 'ZMin')]
    hi = [max(getattr(b, a) for b in boxes.values()) for a in ('XMax', 'YMax', 'ZMax')]
    mid = [(a + b) / 2 for a, b in zip(lo, hi)]
    explode = {}
    for n, b in boxes.items():
        c = (b.Center.x, b.Center.y, b.Center.z)
        explode[n] = [round(k * (c[j] - mid[j]), 1) for j, k in enumerate((0.6, 0.9, 0.9))]
    ident = [1.0, 0, 0, 0, 0, 1.0, 0, 0, 0, 0, 1.0, 0, 0, 0, 0, 1.0]
    scene = dict(rev='mk4', design='mk4', stl_dir='stl/lsr2', cast_dir='cast/lsr2', cnc_dir='cnc/lsr2', laser_dir='cnc/lsr2/laser',
                 frame='global (STL baked in assembly coordinates)', el_axis=MP.EL_AXIS, az_axis=MP.AZ_AXIS, el_sign=MP.EL_SIGN, el_range=[-30, 150],
                 hero_el=30.0, lid_lift=0.0, floor_z=round(lo[2], 2), el_group=[i['name'] for i in insts if i['group'] == 'el'],
                 category={i['name']: i['part']['colour'] for i in insts}, explode=explode,
                 parts=[dict(name=i['name'], part=i['part']['name'], stl=i['name'] + '.stl', category=i['part']['colour'], matrix=ident,
                             group=i['group'], made=i['made']) for i in insts],
                 part_models={}, laser_parts=[i['name'] for i in insts if i['part']['process'] == 'laser_2mm'], cast_parts=[], cnc_parts=[],
                 closeup_hide=[i['name'] for i in insts if i['part']['name'].startswith('Cover')])
    for i in insts:
        scene['part_models'].setdefault(i['part']['name'], []).append(i['name'])
    with open(os.path.join(out, 'build', 'lsr2_render_scene.json'), 'w', encoding='utf-8') as fh:
        json.dump(scene, fh, indent=1)

    made = [i for i in insts if i['made']]

    def bb(n):
        b = boxes[n]
        return [round(v, 2) for v in (b.XMin, b.YMin, b.ZMin, b.XMax, b.YMax, b.ZMax)]

    report = dict(rev='mk4', design='mk4', source='third_party/sarctrac-mk4/FreeCAD/' + MP.ASSEMBLY, gear_ratio=MP.GEAR_RATIO,
                  parts={i['name']: dict(part=i['part']['name'], process=i['part']['process'], material=i['part']['material'], group=i['group'],
                                         volume_cm3=round(i['vol'], 3), mass_g=i['mass'], bbox=bb(i['name'])) for i in insts},
                  totals=dict(instances=len(insts), made=len(made), bought=len(insts) - len(made), made_volume_cm3=round(sum(i['vol'] for i in made), 2),
                              made_mass_g=round(sum(i['mass'] for i in made), 1), assembly_bbox_mm=[round(v, 1) for v in lo + hi]),
                  interference=inter, missing_from_parts=sorted(i['key'] for i in insts if not i['known']),
                  checks=dict(failures=failures, passed=not failures))
    with open(os.path.join(out, 'build', 'lsr2_build_report.json'), 'w', encoding='utf-8') as fh:
        json.dump(report, fh, indent=2)
    if failures:
        raise RuntimeError('%d mk4 export failures: %s' % (len(failures), '; '.join(failures)))
    return report['totals']
