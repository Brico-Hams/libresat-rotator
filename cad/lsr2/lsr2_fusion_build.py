"""LSR-2 main body and lid in Autodesk Fusion (Fusion 360), parametric alternative to the FreeCAD route A / route B derivation.

Run from Fusion: Utilities > Scripts and Add-Ins > Scripts > add this folder > Run (entry point run(context)).
Or call main(out_dir) from the Fusion MCP server / another script. Output dir: argument, else env LSR2_FUSION_OUT, else <repo>/build/fusion.
Pattern order: preform geometry + outward draft (adds material) -> scale x shrink about the origin -> measured as the final body.
MCP-friendly: parametric only for finished/preform/pattern/core (they use user-parameter expressions); then design.designType switches to
DirectDesignType for blanks and exports so no timeline recompute happens and build() returns quickly.
Units: params.py is mm; the Fusion API is cm, every length is converted with mm().
Writes <out>/cast/lsr2/{body,lid}_{finished,preform,pattern}.step|stl, body_core.step|stl, <out>/cnc/lsr2/{body,lid}_{finished,blank}.step|stl,
<out>/build/lsr2_fusion_report.json and cad/lsr2/fusion/LSR2_body.f3d (when writable). FreeCAD (cad/lsr2/build.py) stays the reference build.
"""
import json
import os
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
LSR2 = HERE if os.path.exists(os.path.join(HERE, 'params.py')) else os.path.dirname(HERE)
REPO = os.path.dirname(os.path.dirname(LSR2))
F3D_DIR = os.path.join(LSR2, 'fusion')
if LSR2 not in sys.path:
    sys.path.insert(0, LSR2)

import adsk.core as core      # noqa: E402  (only available inside Fusion)
import adsk.fusion as fusion  # noqa: E402
import params as P            # noqa: E402  plain Python, no FreeCAD
import inputs as I            # noqa: E402,F401  imported so a broken import fails early

C = P.CAST
BX, BY = (-50.0, 180.0), 73.0
Z_RIM, Z_LID, Z_EL, BOSS_Y = 314.0, 319.0, 268.0, 86.0
GASKET = dict(outer=(-49.0, 179.0, 72.0), inner=(-46.0, 176.0, 69.0), depth=2.0)
LID_SCREWS = [(-40, -64), (10, -64), (60, -64), (110, -64), (160, -64), (110, 64), (160, 64), (171, -30), (171, 30), (-41, -20)]
GLANDS = [(70.0, -40.0, 14.0, 16.5), (70.0, 40.0, 11.0, 12.5)]
DRAIN = (150.0, 0.0, 4.0)
DRIVER_PAD = dict(x=(54.0, 176.0), z=(20.0, 178.0), t=3.0)
BREATHER = (180.0, -30.0, 250.0, 8.0)
TOL_CM3 = 0.001       # 1 mm3
WARNINGS = []
JOIN, CUT, NEW = (fusion.FeatureOperations.JoinFeatureOperation, fusion.FeatureOperations.CutFeatureOperation,
                  fusion.FeatureOperations.NewBodyFeatureOperation)


def mm(v):
    return v / 10.0


def warn(msg):
    WARNINGS.append(msg)


def set_params(design):
    """User parameters that drive shrink, draft, stock, wall, fillet (editable in Modify > Change Parameters)."""
    up = design.userParameters
    spec = [('shrink', str(C['shrink']), '', 'alloy shrinkage factor'), ('wall', '%g mm' % C['min_wall'], 'mm', 'casting wall'),
            ('stock', '%g mm' % C['machining'], 'mm', 'machining stock per face'), ('fillet', '%g mm' % C['min_fillet'], 'mm', 'vertical edge fillet'),
            ('draft_out', '%g deg' % C['draft_out'], 'deg', 'outer draft'), ('draft_in', '%g deg' % C['draft_in'], 'deg', 'core (inner) draft'),
            ('draft_lid', '%g deg' % P.CAST_PART['lid']['draft_out'], 'deg', 'lid draft'), ('core_print', '%g mm' % C['core_print'], 'mm', 'core print beyond the open face'),
            ('blank_margin', '%g mm' % P.CNC['margin'], 'mm', 'CNC blank margin per face'), ('blank_tab', '%g mm' % P.CNC['tab'], 'mm', 'CNC clamping tab')]
    for name, expr, unit, comment in spec:
        p = up.itemByName(name)
        if p:
            p.expression = expr
        else:
            up.add(name, core.ValueInput.createByString(expr), unit, comment)


AXIS_VEC = {'x': (1, 0, 0), 'y': (0, 1, 0), 'z': (0, 0, 1)}


def base_plane(comp, axis):
    return {'x': comp.yZConstructionPlane, 'y': comp.xZConstructionPlane, 'z': comp.xYConstructionPlane}[axis]


def pt(axis, a, b):
    """Model point (cm) on the plane through the origin normal to `axis`, in-plane mm coords a, b (x,y,z order of the other two axes)."""
    c = {'x': (0, a, b), 'y': (a, 0, b), 'z': (a, b, 0)}[axis]
    return core.Point3D.create(mm(c[0]), mm(c[1]), mm(c[2]))


def extrude(comp, axis, z0, z1, draw, op, taper=None, name=None):
    """Sketch on the base plane of `axis`, extrude from coordinate z0 to z1 (mm). draw(sketch, to_sk) adds curves.
    Offset and distance are signed with the sketch normal, so the result does not depend on how Fusion orients the plane."""
    sk = comp.sketches.add(base_plane(comp, axis))
    nrm = sk.xDirection.crossProduct(sk.yDirection)
    v = AXIS_VEC[axis]
    s = 1.0 if (nrm.x * v[0] + nrm.y * v[1] + nrm.z * v[2]) > 0 else -1.0
    draw(sk, lambda a, b: sk.modelToSketchSpace(pt(axis, a, b)))
    prof = core.ObjectCollection.create()
    for p in sk.profiles:
        prof.add(p)
    ei = comp.features.extrudeFeatures.createInput(prof, op)
    ei.startExtent = fusion.OffsetStartDefinition.create(core.ValueInput.createByReal(s * mm(z0)))
    ang = core.ValueInput.createByString(taper) if taper else core.ValueInput.createByReal(0)
    extent = fusion.DistanceExtentDefinition.create(core.ValueInput.createByReal(mm(z1 - z0)))
    direction = fusion.ExtentDirections.PositiveExtentDirection if s > 0 else fusion.ExtentDirections.NegativeExtentDirection
    ei.setOneSideExtent(extent, direction, ang)
    f = comp.features.extrudeFeatures.add(ei)
    if name:
        f.name = name
    return f


def box(comp, x0, x1, y0, y1, z0, z1, op, taper=None, name=None):
    def draw(sk, to):
        sk.sketchCurves.sketchLines.addTwoPointRectangle(to(x0, y0), to(x1, y1))
    return extrude(comp, 'z', z0, z1, draw, op, taper, name)


def cyl(comp, r, length, c0, axis, op, name=None):
    """Cylinder radius r (mm), length along `axis` starting at c0 = (x, y, z) (mm)."""
    idx = {'x': 0, 'y': 1, 'z': 2}
    a, b = {'x': ('y', 'z'), 'y': ('x', 'z'), 'z': ('x', 'y')}[axis]
    ca, cb, start = c0[idx[a]], c0[idx[b]], c0[idx[axis]]

    def draw(sk, to):
        sk.sketchCurves.sketchCircles.addByCenterRadius(to(ca, cb), mm(r))
    return extrude(comp, axis, start, start + length, draw, op, None, name)


def new_comp(root, name):
    occ = root.occurrences.addNewComponent(core.Matrix3D.create())
    occ.component.name = name
    return occ.component


def top_face(body, z_mm):
    for f in body.faces:
        if f.geometry.surfaceType == core.SurfaceTypes.PlaneSurfaceType and f.geometry.normal.z > 0.99 and abs(f.centroid.z - mm(z_mm)) < 0.01:
            return f
    return None


def _corner_edges(body, r_mm, stock=0.0):
    """Vertical (draft-tolerant) straight edges between two planar faces at the outer or cavity box corners.
    Skips cylinder seams, rib/pad/shelf edges, short edges and edges whose faces are narrower than the radius."""
    x0, x1 = BX
    w = C['min_wall']
    tol = 20.0
    corners = [(x, y) for x in (x0 - stock, x1 + stock, x0 + w, x1 - w) for y in (-BY - stock, BY + stock, -BY + w, BY - w)]
    out = []
    for e in body.edges:
        if e.geometry.curveType != core.Curve3DTypes.Line3DCurveType:
            continue
        bb = e.boundingBox
        dz = (bb.maxPoint.z - bb.minPoint.z) * 10.0
        dh = max(bb.maxPoint.x - bb.minPoint.x, bb.maxPoint.y - bb.minPoint.y) * 10.0
        if dz < max(2.0 * r_mm, 100.0) or dh > 0.2 * dz or e.faces.count != 2:
            continue
        if any(f.geometry.surfaceType != core.SurfaceTypes.PlaneSurfaceType for f in e.faces):
            continue
        if any(max(f.boundingBox.maxPoint.x - f.boundingBox.minPoint.x, f.boundingBox.maxPoint.y - f.boundingBox.minPoint.y) * 10.0 <= r_mm for f in e.faces):
            continue
        mx, my = (bb.maxPoint.x + bb.minPoint.x) * 5.0, (bb.maxPoint.y + bb.minPoint.y) * 5.0
        if any(abs(mx - cx) < tol and abs(my - cy) < tol for cx, cy in corners):
            out.append(e)
    return out


def _try_fillet(comp, edges, value):
    try:
        fi = comp.features.filletFeatures.createInput()
        coll = core.ObjectCollection.create()
        for e in edges:
            coll.add(e)
        fi.edgeSetInputs.addConstantRadiusEdgeSet(coll, value, False)
        comp.features.filletFeatures.add(fi)
        return True
    except RuntimeError:
        return False


def fillet_vertical(comp, body, r_expr, stock=0.0):
    r = C['min_fillet']
    if not _corner_edges(body, r, stock):
        return warn('FILLET: no eligible vertical corner edge found')
    full, half = core.ValueInput.createByString(r_expr), core.ValueInput.createByReal(mm(r / 2.0))
    # one feature for the whole group, then half radius, then edge by edge (re-selected: a failed add leaves the body unchanged)
    if _try_fillet(comp, _corner_edges(body, r, stock), full):
        return
    warn('FILLET: group fillet at %g mm failed' % r)
    if _try_fillet(comp, _corner_edges(comp.bRepBodies.item(0), r, stock), half):
        return warn('FILLET: group fillet applied at half radius %g mm (< min_fillet %g)' % (r / 2.0, r))
    n = len(_corner_edges(comp.bRepBodies.item(0), r, stock))
    done = failed = 0
    for _ in range(n):
        todo = _corner_edges(comp.bRepBodies.item(0), r, stock)
        if len(todo) <= failed:
            break
        e = todo[failed]
        if _try_fillet(comp, [e], full):
            done += 1
        elif _try_fillet(comp, [e], half):
            done += 1
            warn('FILLET: edge at half radius %g mm (< min_fillet %g)' % (r / 2.0, r))
        else:
            failed += 1
            warn('FILLET: edge not filleted (radius %g and %g mm both failed)' % (r, r / 2.0))
    if failed:
        warn('FILLET: %d vertical edge(s) left sharp' % failed)


def build_body(comp, stock=0.0, draft=None, holes=True, core_only=False):
    """stock: grow the outer skin and bosses (mm; preform/pattern), the cavity stays the finished one.
    draft: signed taper expression of the outer skin; it must ADD material (outer walls widen toward the open rim; the shell keeps the wall, so the cavity follows). holes: cut the machined holes (finished only).
    core_only: the cavity volume plus the core print (sand core / printed core box)."""
    w = C['min_wall']
    s = stock
    x0, x1 = BX
    if core_only:
        box(comp, x0 + w, x1 - w, -BY + w, BY - w, w, Z_RIM, NEW, None, 'cavity core')
        box(comp, x0 + w, x1 - w, -BY + w, BY - w, Z_RIM, Z_RIM + C['core_print'], JOIN, None, 'core print')
        return comp.bRepBodies.item(0)
    box(comp, x0 - s, x1 + s, -BY - s, BY + s, -s, Z_RIM, NEW, draft, 'outer')
    body = comp.bRepBodies.item(0)
    top = top_face(body, Z_RIM)
    if top is None:
        raise RuntimeError('rim face not found for the shell')
    sh = comp.features.shellFeatures
    rm = core.ObjectCollection.create()
    rm.add(top)
    si = sh.createInput(rm, False)
    si.insideThickness = core.ValueInput.createByString('wall + stock' if s else 'wall')
    sh.add(si)
    for x, y, R, _ in GLANDS:
        cyl(comp, R + s, 22.0 + s, (x, y, -22.0 - s), 'z', JOIN, 'gland boss')
    cyl(comp, 44.0 + s, 12.0 + s, (0, 0, -12.0 - s), 'z', JOIN, 'AZ boss')
    for x, y in LID_SCREWS:
        cyl(comp, 4.5, Z_RIM - w - 2, (x, y, w - 0.5), 'z', JOIN, 'screw post')
    for y in (-30.0, 30.0, -45.0, 45.0):
        box(comp, 50.0, 172.0, y - w / 2, y + w / 2, w - 0.5, w + 20.0, JOIN, None, 'rib')
    for sg in (-1, 1):
        yo = BY - 0.5 if sg > 0 else -BY - 9.0
        box(comp, 70.0, 160.0, yo, yo + 9.5, 10.0, 185.0, JOIN, None, 'side pad')
        cyl(comp, 26.0 + s, BOSS_Y - BY + 7.0, (0, (BY - 7.0) if sg > 0 else -BOSS_Y, Z_EL), 'y', JOIN, 'EL boss')
    box(comp, DRIVER_PAD['x'][0], DRIVER_PAD['x'][1], -BY + w - 0.5, -BY + w + DRIVER_PAD['t'], DRIVER_PAD['z'][0], DRIVER_PAD['z'][1], JOIN, None, 'driver pad')
    box(comp, -44.0, 52.0, 58.0, BY - w + 0.5, 218.0, 310.0, JOIN, None, 'electronics shelf')
    box(comp, -45.0, 60.0, -BY + w - 0.5, BY - w + 0.5, 140.0, 148.0, JOIN, None, 'gearbox shelf')
    cyl(comp, 40.0, 115.0, (0, 0, w - 0.5), 'z', JOIN, 'AZ pillar')
    cyl(comp, BREATHER[3], 6.0, (BREATHER[0] - 0.5, BREATHER[1], BREATHER[2]), 'x', JOIN, 'breather boss')
    if holes:
        cyl(comp, 31.0, 100.0, (0, 0, 15.0), 'z', CUT, 'AZ bore')
        cyl(comp, 26.5, 16.0, (0, 0, -8.0), 'z', CUT, 'AZ seat')
        cyl(comp, 8.5, 40.0, (0, 0, 100.0), 'z', CUT, 'index shaft hole')
        cyl(comp, 10.0, 14.0, (0, 0, 138.0), 'z', CUT, 'gearbox shelf hole')
        cyl(comp, DRAIN[2] / 2, 8.0, (DRAIN[0], DRAIN[1], -1.0), 'z', CUT, 'drain')
        for x, y, _, d in GLANDS:
            cyl(comp, d / 2, 30.0, (x, y, -23.0), 'z', CUT, 'gland hole')
        for x, y in LID_SCREWS:
            cyl(comp, 2.1, 14.0, (x, y, Z_RIM - 14.0), 'z', CUT, 'lid screw M5 tap')
        for sg in (-1, 1):
            ya = sg * 66.0
            cyl(comp, 21.0, 16.0, (0, ya if sg > 0 else ya - 16.0, Z_EL), 'y', CUT, '6004 seat')
            cyl(comp, 16.0, 4.0, (0, sg * 82.0 if sg > 0 else -86.0, Z_EL), 'y', CUT, 'seal bore')
            cyl(comp, 11.0, 20.0, (0, (BY - 18.0) if sg > 0 else -BY - 2.0, Z_EL), 'y', CUT, 'shaft clearance')
    fillet_vertical(comp, comp.bRepBodies.item(0), 'fillet', s)
    return comp.bRepBodies.item(0)


def build_lid(comp, stock=0.0, draft=None, holes=True):
    s = stock
    x0, x1 = BX
    box(comp, x0 - s, x1 + s, -BY - s, BY + s, Z_RIM - s, Z_LID + s, NEW, draft, 'lid plate')
    if holes:
        g = GASKET

        def draw(sk, to):
            ln = sk.sketchCurves.sketchLines
            ln.addTwoPointRectangle(to(g['outer'][0], -g['outer'][2]), to(g['outer'][1], g['outer'][2]))
            ln.addTwoPointRectangle(to(g['inner'][0], -g['inner'][2]), to(g['inner'][1], g['inner'][2]))
        gasket_groove(comp, draw, Z_RIM, Z_RIM + g['depth'])
        for x, y in LID_SCREWS:
            cyl(comp, 2.75, C['min_wall'] + 2, (x, y, Z_RIM - 1), 'z', CUT, 'lid screw clearance')
    return comp.bRepBodies.item(0)


def gasket_groove(comp, draw, z0, z1):
    """Cut only the ring profile (the one with two loops) between the outer and inner gasket rectangles."""
    sk = comp.sketches.add(comp.xYConstructionPlane)
    nrm = sk.xDirection.crossProduct(sk.yDirection)
    s = 1.0 if nrm.z > 0 else -1.0
    draw(sk, lambda a, b: sk.modelToSketchSpace(core.Point3D.create(mm(a), mm(b), 0)))
    prof = core.ObjectCollection.create()
    for p in sk.profiles:
        if p.profileLoops.count == 2:
            prof.add(p)
    if prof.count == 0:
        return warn('gasket ring profile not found')
    ei = comp.features.extrudeFeatures.createInput(prof, CUT)
    ei.startExtent = fusion.OffsetStartDefinition.create(core.ValueInput.createByReal(s * mm(z0)))
    ei.setOneSideExtent(fusion.DistanceExtentDefinition.create(core.ValueInput.createByReal(mm(z1 - z0))),
                        fusion.ExtentDirections.PositiveExtentDirection if s > 0 else fusion.ExtentDirections.NegativeExtentDirection)
    comp.features.extrudeFeatures.add(ei).name = 'gasket groove'


def build_blank(comp, lo, hi):
    """Route B block: margin on every face, clamping tabs on the footprint sides, thickness snapped up to a stock plate; z is the machine axis."""
    m, t = P.CNC['margin'], P.CNC['tab']
    d = [hi[i] - lo[i] + 2 * m + (0 if i == 2 else 2 * t) for i in range(3)]
    need = d[2]
    d[2] = next((p for p in P.CNC['plate_t'] if p >= need), need)
    box(comp, lo[0] - m - t, lo[0] - m - t + d[0], lo[1] - m - t, lo[1] - m - t + d[1], lo[2] - m, lo[2] - m + d[2], NEW, None, 'blank')
    return comp.bRepBodies.item(0)


def scale_body(comp, body, factor_expr):
    body = body.nativeObject or body  # never a proxy
    pt = body.parentComponent.originConstructionPoint  # origin of the component that owns the body
    feats = body.parentComponent.features.scaleFeatures

    def attempt(vi):
        col = core.ObjectCollection.create()
        col.add(body)
        return feats.add(feats.createInput(col, pt, vi))

    try:
        return attempt(core.ValueInput.createByString(factor_expr))
    except RuntimeError as e:
        param = fusion.Design.cast(core.Application.get().activeProduct).userParameters.itemByName(factor_expr)
        val = param.value if param else float(factor_expr)
        warn('scale_body: parametric scale "%s" rejected (%s); used numeric %g, link to parameter lost' % (factor_expr, e, val))
        return attempt(core.ValueInput.createByReal(val))


def measure(body):
    bb = body.boundingBox
    return dict(vol=body.volume, volume_cm3=round(body.volume, 3), isValid=bool(body.isValid),
                bbox_mm=[round(10 * v, 3) for v in (bb.minPoint.x, bb.minPoint.y, bb.minPoint.z, bb.maxPoint.x, bb.maxPoint.y, bb.maxPoint.z)])


def difference_cm3(a, b):
    """Volume of a that lies outside b (cm3), on temporary copies."""
    tbm = fusion.TemporaryBRepManager.get()
    ta, tb = tbm.copy(a), tbm.copy(b)
    tbm.booleanOperation(ta, tb, fusion.BooleanTypes.DifferenceBooleanType)
    return ta.volume if ta.faces.count else 0.0


def export_all(design, comp, body, base, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    em = design.exportManager
    em.execute(em.createSTEPExportOptions(os.path.join(out_dir, base + '.step'), comp))
    stl = em.createSTLExportOptions(body, os.path.join(out_dir, base + '.stl'))
    stl.meshRefinement = fusion.MeshRefinementSettings.MeshRefinementHigh
    stl.sendToPrintUtility = False
    em.execute(stl)


def build(out):
    app = core.Application.get()
    doc = app.documents.add(core.DocumentTypes.FusionDesignDocumentType)
    doc.name = 'LSR2_body'
    design = fusion.Design.cast(app.activeProduct)
    design.designType = fusion.DesignTypes.ParametricDesignType
    root = design.rootComponent
    set_params(design)
    shrink, stock = C['shrink'], C['machining']
    bodies = {}

    def make(name, fn, **kw):
        comp = new_comp(root, name)
        bodies[name] = (comp, fn(comp, **kw))

    for part, fn, d in (('body', build_body, 'draft_out'), ('lid', build_lid, 'draft_lid')):
        make(part + '_finished', fn)
        make(part + '_preform', fn, stock=stock, holes=False)
        pre_vol = bodies[part + '_preform'][1].volume
        # Round 4 showed the previous '-' taper removed material: the sign is now positive (widens toward the rim).
        make(part + '_pattern', fn, stock=stock, draft=d, holes=False)
        pc, pb = bodies[part + '_pattern']
        scale_body(pc, pb, 'shrink')
        final = pc.bRepBodies.item(0)  # re-read: the final scaled pattern body is the one measured
        if final.volume < pre_vol * shrink ** 3:
            warn('%s_pattern: volume %.1f < preform x shrink^3 %.1f, draft sign or scale is wrong' % (part, final.volume, pre_vol * shrink ** 3))
    make('body_core', build_body, core_only=True)
    # Expression-driven features are done; plain numeric blanks and exports run in direct mode (no timeline recompute, keeps MCP calls fast).
    try:
        design.designType = fusion.DesignTypes.DirectDesignType
    except Exception as e:
        warn('direct design switch failed, staying parametric: %s' % e)
    for part in ('body', 'lid'):
        bb = bodies[part + '_finished'][1].boundingBox
        make(part + '_blank', build_blank, lo=[10 * bb.minPoint.x, 10 * bb.minPoint.y, 10 * bb.minPoint.z], hi=[10 * bb.maxPoint.x, 10 * bb.maxPoint.y, 10 * bb.maxPoint.z])

    cast_dir, cnc_dir = os.path.join(out, 'cast', 'lsr2'), os.path.join(out, 'cnc', 'lsr2')
    rep = {}
    for name, (comp, b) in bodies.items():
        b = comp.bRepBodies.item(0)
        bodies[name] = (comp, b)
        m = measure(b)
        if name.endswith('blank'):
            dens, dirs = P.CNC['density'], (cnc_dir,)
        elif name.endswith('pattern') or name.endswith('core'):
            dens, dirs = P.PLA_G_CM3 * C['pla_fill'], (cast_dir,)       # printed pattern at its infill
        elif name.endswith('finished'):
            dens, dirs = P.ALU_CAST_G_CM3, (cast_dir, cnc_dir)
        else:
            dens, dirs = P.ALU_CAST_G_CM3, (cast_dir,)
        m['mass_g'] = round(m.pop('vol') * dens, 1)
        m['density_g_cm3'] = dens
        rep[name] = m
        for d in dirs:
            export_all(design, comp, b, name, d)

    checks = {}
    for part in ('body', 'lid'):
        f, pre, pat, bl = (bodies[part + s][1] for s in ('_finished', '_preform', '_pattern', '_blank'))
        checks[part + ': preform contains finished'] = difference_cm3(f, pre) < TOL_CM3
        checks[part + ': blank contains finished'] = difference_cm3(f, bl) < TOL_CM3
        a, c = pre.boundingBox, pat.boundingBox
        lo_w = [shrink * v for v in (a.minPoint.x, a.minPoint.y, a.minPoint.z)]
        hi_w = [shrink * v for v in (a.maxPoint.x, a.maxPoint.y, a.maxPoint.z)]
        lo_g, hi_g = (c.minPoint.x, c.minPoint.y, c.minPoint.z), (c.maxPoint.x, c.maxPoint.y, c.maxPoint.z)
        checks[part + ': pattern encloses preform x shrink (bbox)'] = all(g <= w + 1e-4 for g, w in zip(lo_g, lo_w)) and all(g >= w - 1e-4 for g, w in zip(hi_g, hi_w))
        checks[part + ': pattern volume >= preform x shrink^3'] = pat.volume >= pre.volume * shrink ** 3 - TOL_CM3
        checks[part + ': preform bigger than finished'] = pre.volume > f.volume
    checks['all bodies valid'] = all(v['isValid'] for v in rep.values())

    report = dict(revision=P.REV, params=dict(shrink=shrink, draft_out=C['draft_out'], draft_in=C['draft_in'], stock=stock, wall=C['min_wall'], fillet=C['min_fillet']),
                  parts=rep, checks=checks, warnings=WARNINGS)
    try:
        os.makedirs(F3D_DIR, exist_ok=True)
        design.exportManager.execute(design.exportManager.createFusionArchiveExportOptions(os.path.join(F3D_DIR, 'LSR2_body.f3d')))
    except Exception:
        warn('f3d not saved: ' + traceback.format_exc(limit=1))
    os.makedirs(os.path.join(out, 'build'), exist_ok=True)
    with open(os.path.join(out, 'build', 'lsr2_fusion_report.json'), 'w') as fh:
        json.dump(report, fh, indent=2)
    bad = [k for k, v in checks.items() if not v]
    assert not bad, 'LSR2 Fusion invariants failed: %s' % bad
    return report


def main(out_dir=None):
    out = out_dir or (sys.argv[1] if len(sys.argv) > 1 else None) or os.environ.get('LSR2_FUSION_OUT') or os.path.join(REPO, 'build', 'fusion')
    return build(os.path.abspath(out))


def run(context):
    ui = core.Application.get().userInterface
    try:
        rep = main()
        ui.messageBox('LSR-2 Fusion build OK\n' + json.dumps({k: v['volume_cm3'] for k, v in rep['parts'].items()}, indent=1))
    except Exception:
        ui.messageBox('LSR-2 Fusion build failed:\n' + traceback.format_exc())
