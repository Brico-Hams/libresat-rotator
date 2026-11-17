"""LSR-2 phase 11c, Route A: sand casting (A356-T6) from a printed pattern. Models, checks and exports for every cast part (mm).

Three solids per part: FINISHED (body.py / axes.py), PREFORM (finished + machining stock on the datum/fit faces, fine holes and fits left solid,
only the cored holes of `spec` cast in) and PATTERN (preform x shrink, additive draft, core prints; halves split at the parting plane).
Two separate processes, never mixed: recoverable pattern (params.CAST / CAST_PART, drafted halves + cores) and consumable lost-PLA
(params.CAST_LOST, no draft, no cores). Every value: PARAMETRIC (params.py) "to agree with the foundry"; alloy A356-T6.
Pure Python (no FreeCAD): hot-spot formulas, writers (STL / 3MF / watertight), split counts, self_test. FreeCAD builders import lazily.
Run: python route_a.py (self-test); build.py calls build_all() under freecadcmd.
"""
import math
import os
import struct
import zipfile
import params as P
import inputs as IN

PARTS = ('body', 'lid', 'mast_bracket', 'yoke_arm', 'saddle', 'boom_clamp')
QTY = {'body': 1, 'lid': 1, 'mast_bracket': 1, 'yoke_arm': 2, 'saddle': 1, 'boom_clamp': 2}     # yoke arm / clamp: side +1 modelled, the other mirrored


def cast_params(part):
    """CAST with the per-part overrides of params.CAST_PART (shrinkage, draft, stock, wall, fillet are independent keys)."""
    return dict(P.CAST, **P.CAST_PART.get(part, {}))


# --- hot-spot check: largest inscribed sphere / adjacent wall (pure Python) ----------------------------------------------------------
def d_tee(t, s, r):
    """Inscribed diameter at a rib (thickness s) meeting a wall (thickness t) with fillets r on both sides."""
    return 2.0 * ((s / 2 + r) ** 2 + (t + r) ** 2 - r * r) / (2.0 * (t + 2 * r))


def d_elbow(t, r):
    """Inscribed diameter at the inside-filleted (r), sharp-outside corner of two walls of thickness t."""
    return 2.0 * (math.sqrt(2) * (t + r) - r) / (1.0 + math.sqrt(2))


def junctions(part):
    """(name, inscribed diameter, adjacent wall, mitigation). A ratio above CAST['hot_spot_max'] needs a non-empty mitigation (riser, chill, core)."""
    p = cast_params(part)
    W, r, s = p['min_wall'], p['min_fillet'], p['machining']
    tee, ell = d_tee(W, W, r), d_elbow(W, r)
    if part == 'body':
        return [('wall-rib tee', tee, W, ''), ('wall corner', ell, W, ''), ('lid-screw post on wall', d_tee(W, 8.0, r), W, ''),
                ('EL boss on side plate (boss 20 deep, plate+wall 14)', 20.0, 14.0, ''),
                ('AZ pillar ring (r40, cast bore r%.1f)' % (31.0 - s), 40.0 - (31.0 - s), W, 'chill at the pillar foot and riser on the pillar top; foundry to confirm'),
                ('AZ neck + floor + pillar foot block (z -12..15)', 27.0, W, 'chill under the neck; riser through the AZ core print; foundry to confirm')]
    if part == 'lid':
        return [('plate', W + s, W + s, '')]
    if part == 'mast_bracket':
        return [('tube ring (r38, cast bore r%.2f)' % (30.25 - s), 38.0 - (30.25 - s), 38.0 - (30.25 - s), ''),
                ('pinch lug 24 x 28 x 32', 24.0, 38.0 - (30.25 - s), 'chill on the lug, feed from the tube; or CNC route'),
                ('shaft-pocket ring (r38, cast r%.1f)' % (15.5 - s), 38.0 - (15.5 - s), 6.0, 'riser at the cup centre; or CNC route')]
    if part == 'yoke_arm':
        t_arm = 10.0
        return [('boss ring (r20, cast bore r%.1f)' % (10.0 - s), 20.0 - (10.0 - s), t_arm, ''), ('plate-flange tee', d_tee(t_arm, 6.0, r), t_arm, '')]
    if part == 'saddle':
        return [('plate 8 + stock', 8.0 + 2 * s, 8.0 + 2 * s, '')]
    return [('block 10 + stock', 10.0 + 2 * s, 10.0 + 2 * s, '')]


def hot_spot_report(part):
    lim = cast_params(part)['hot_spot_max']
    return [dict(name=n, d=round(d, 2), wall=round(w, 2), ratio=round(d / w, 2), ok=d / w <= lim, mitigation=m) for n, d, w, m in junctions(part)]


def lump_ok(depth, width, lump_max=None):
    """Sand lump (window or pocket in the pattern): depth / width must stay below CAST['lump_max'] or the lump breaks on draw."""
    return depth / width <= (lump_max or P.CAST['lump_max'])


def draft_offset(angle_deg, height):
    """Material added per face at the parting plane for a draft angle over `height` (mm)."""
    return math.tan(math.radians(angle_deg)) * height


# --- print sizing, dowels, writers (pure Python) -------------------------------------------------------------------------------------
def print_fit():
    """Largest piece edge (mm): print volume of inputs.py minus the margin and the protruding key length (the keys are added after the split)."""
    pv = [v * 1000.0 for v in IN.I['print_volume']]
    return [v - P.CAST['print_margin'] - P.CAST['dowel_len'] for v in pv]


def piece_count(dims, fit):
    """Pieces after bisecting each over-size axis (midpoint cuts): product of 2^k with the least k so that dim / 2^k <= fit."""
    n = 1
    for d, f in zip(dims, fit):
        k = 0
        while d / 2 ** k > f:
            k += 1
        n *= 2 ** k
    return n


def flask_dowels(bbox, axis, outset=25.0):
    """Two registration-dowel positions on the parting plane, at opposite corners outside the part bbox (xmin,ymin,zmin,xmax,ymax,zmax)."""
    i, j = [k for k in range(3) if k != axis]
    lo, hi = (bbox[i] - outset, bbox[j] - outset), (bbox[i + 3] + outset, bbox[j + 3] + outset)
    return [lo, hi]


def weld(verts, tris, nd=4):
    idx, out_v, out_t = {}, [], []
    for t in tris:
        ids = []
        for k in t:
            key = tuple(round(c, nd) for c in verts[k])
            if key not in idx:
                idx[key] = len(out_v)
                out_v.append(key)
            ids.append(idx[key])
        if len(set(ids)) == 3:
            out_t.append(tuple(ids))
    return out_v, out_t


def watertight(tris):
    """Closed 2-manifold test: every directed edge exactly once and its reverse exactly once."""
    cnt = {}
    for a, b, c in tris:
        for e in ((a, b), (b, c), (c, a)):
            cnt[e] = cnt.get(e, 0) + 1
    return bool(cnt) and all(n == 1 and cnt.get((e[1], e[0])) == 1 for e, n in cnt.items())


def write_stl(path, verts, tris):
    with open(path, 'wb') as f:
        f.write(b'LSR-2 route A'.ljust(80, b' '))
        f.write(struct.pack('<I', len(tris)))
        for a, b, c in tris:
            va, vb, vc = verts[a], verts[b], verts[c]
            u, w = [vb[k] - va[k] for k in range(3)], [vc[k] - va[k] for k in range(3)]
            n = (u[1] * w[2] - u[2] * w[1], u[2] * w[0] - u[0] * w[2], u[0] * w[1] - u[1] * w[0])
            m = math.sqrt(sum(x * x for x in n)) or 1.0
            f.write(struct.pack('<12fH', n[0] / m, n[1] / m, n[2] / m, *va, *vb, *vc, 0))


def write_3mf(path, objects):
    """3MF (zip: [Content_Types].xml, _rels/.rels, 3D/3dmodel.model). objects = [(name, verts, tris)], laid out side by side along x."""
    res, items, x = [], [], 0.0
    for i, (name, v, t) in enumerate(objects, 1):
        xs = [p[0] for p in v]
        tx = x - min(xs)
        x = tx + max(xs) + 10.0
        mesh = ''.join('<vertex x="%.4f" y="%.4f" z="%.4f"/>' % p for p in v)
        tri = ''.join('<triangle v1="%d" v2="%d" v3="%d"/>' % a for a in t)
        res.append('<object id="%d" name="%s" type="model"><mesh><vertices>%s</vertices><triangles>%s</triangles></mesh></object>' % (i, name, mesh, tri))
        items.append('<item objectid="%d" transform="1 0 0 0 1 0 0 0 1 %.4f 0 0"/>' % (i, tx))
    model = ('<?xml version="1.0" encoding="UTF-8"?><model unit="millimeter" xml:lang="en-US" xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02">'
             '<resources>%s</resources><build>%s</build></model>' % (''.join(res), ''.join(items)))
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('[Content_Types].xml', '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                   '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                   '<Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/></Types>')
        z.writestr('_rels/.rels', '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                   '<Relationship Target="/3D/3dmodel.model" Id="rel0" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/></Relationships>')
        z.writestr('3D/3dmodel.model', model)


# --- per-part data for the docs (orientation, supports, check points; moulding layout) ----------------------------------------------
PRINT_GUIDE = {
    'body': dict(orient='each half parting face down (widest section on the bed)', supports='none on drafted faces; core-print stubs print as stand-alone cylinders',
                 joints='pin D8 / socket D8.6, 10 deep, on every cut', checks='x 230 +/- 0.5, y 2 x 86, boss centre z 268 from the parting face, cavity box x/y after shrink'),
    'lid': dict(orient='flat, top (parting) face down', supports='none', joints='pin D8 / socket D8.6', checks='length 230, width 146, thickness after stock'),
    'mast_bracket': dict(orient='each half parting face down', supports='none (bore and cup are cores, not pattern cavities)', joints='pin D8 / socket D8.6',
                         checks='tube OD 76, lug span, print stub diameters'),
    'yoke_arm': dict(orient='upper half plate down on the parting plane (z = EL axis)', supports='none', joints='pin D8 / socket D8.6',
                     checks='boss centre height, flange top height above the axis plane (125), core-print stub centre'),
    'saddle': dict(orient='flat, parting face down', supports='none (the window is a drafted lump)', joints='pin D8 / socket D8.6', checks='window 28 x 76, plate 8 + stock'),
    'boom_clamp': dict(orient='flat, parting face down', supports='none', joints='not split (fits the bed)', checks='block 50+ x 30 x 10 + stock'),
}
MOULD = {
    'body': dict(plane='y = 0, draw along +y / -y (cope and drag)', cores='1 dry-sand core: cavity + AZ prong, print on the open top (z)', loose='none after the y draw (no undercut)',
                 gating='sketch: sprue + choke at the rear low corner (x -50), ingates along the floor edge; risers on the AZ pillar top and the rim; vents on the core print'),
    'lid': dict(plane='top face (z = 319), plate in the drag', cores='none', loose='none', gating='sketch: edge gate at a short side, 2 vents at the far corners'),
    'mast_bracket': dict(plane='y = 0, draw along y', cores='2: bore (blind, print at z = -160) and cup + pocket (print on top)', loose='none', gating='sketch: ingate at the tube foot, riser on the lugs'),
    'yoke_arm': dict(plane='z = EL axis, draw along z', cores='1 through the bore with a print at each end', loose='none', gating='sketch: ingate at the foot, riser on the flange top'),
    'saddle': dict(plane='top face', cores='none (window is a sand lump)', loose='none', gating='sketch: edge gate, vents at the corners'),
    'boom_clamp': dict(plane='top face', cores='none', loose='none', gating='sketch: edge gate'),
}


def self_test():
    assert abs(d_tee(5, 5, 3) - 7.75) < 1e-6 and abs(d_elbow(5, 3) - 6.887) < 1e-3
    assert abs(draft_offset(2.0, 86.0) - 3.0) < 0.01
    assert piece_count((240, 100, 366), (240, 240, 240)) == 2 and piece_count((200, 90, 80), (240, 240, 240)) == 1
    assert len(print_fit()) == 3 and all(200 < f < 256 for f in print_fit())
    assert flask_dowels((0, 0, 0, 100, 50, 10), 2) == [(-25.0, -25.0), (125.0, 75.0)]
    v, t = [(0, 0, 0), (1, 0, 0), (0, 1, 0), (0, 0, 1)], [(0, 2, 1), (0, 1, 3), (1, 2, 3), (0, 3, 2)]
    assert watertight(t) and not watertight(t[:3])
    wv, wt = weld(v + v, t + [(4, 0, 4)])
    assert len(wv) == 4 and len(wt) == 4
    import tempfile
    d = tempfile.mkdtemp()
    write_stl(os.path.join(d, 'a.stl'), v, t)
    assert os.path.getsize(os.path.join(d, 'a.stl')) == 84 + 50 * 4
    write_3mf(os.path.join(d, 'a.3mf'), [('a', v, t), ('b', v, t)])
    with zipfile.ZipFile(os.path.join(d, 'a.3mf')) as z:
        assert z.read('3D/3dmodel.model').count(b'<object ') == 2 and '[Content_Types].xml' in z.namelist()
    assert lump_ok(8.0, 28.0) and not lump_ok(80.0, 20.0)
    for part in PARTS:
        p = cast_params(part)
        assert p['shrink'] > 1.0 and p['draft_out'] > 0 and p['machining'] > 0 and p['min_wall'] >= 5.0 and p['min_fillet'] > 0
        for j in hot_spot_report(part):
            assert j['ok'] or j['mitigation'], (part, j)
    assert P.CAST_LOST['shrink'] > 1.0 and 'draft_out' not in P.CAST_LOST
    flagged = sum(1 for part in PARTS for j in hot_spot_report(part) if not j['ok'])
    print('route A self-test OK (%d hot spots rely on a declared mitigation)' % flagged)


# --- FreeCAD part: specs, preform, pattern, cores, splitting, exports ----------------------------------------------------------------
def spec(name, stock, plen):
    """Solids of one part: blank (before cuts), finished, pads (machining stock), holes (cast-in cores), keep (cast-in void, no core),
    cavity (air in the blank filled by the pattern and formed by a core), prints(clear) = core prints, plane = (axis, coordinate), sides."""
    import geom as G
    import body as B
    import axes as AX
    K = AX.K
    x0, x1, BY, W = B.BX[0], B.BX[1], B.BY, B.W
    zy, zz = (0, 1, 0), (0, 0, 1)
    s = dict(holes=[], keep=[], cavity=[], prints=lambda c: [])
    if name == 'body':
        def inner(z0, z1):
            return G.box(x0 + W, x1 - W, -BY + W, BY - W, z0, z1)
        s.update(blank=B.body(True), finished=B.body(), plane=(1, 0.0), sides=(1, -1),
                 pads=[G.cyl(44.0, stock, (0, 0, -12 - stock), zz), G.cut(G.box(x0, x1, -BY, BY, B.Z_RIM, B.Z_RIM + stock), [inner(B.Z_RIM - 1, B.Z_RIM + stock + 1)]),
                       G.cyl(26.0, stock, (0, B.BOSS_Y, B.Z_EL), zy), G.cyl(26.0, stock, (0, -B.BOSS_Y - stock, B.Z_EL), zy),
                       G.box(-44.0, 52.0, 58.0 - stock, 58.0, 218.0, 310.0), G.box(-45.0, 60.0, -BY + W, BY - W, 148.0, 148.0 + stock)],
                 holes=[G.cyl(31.0 - stock, 100.0, (0, 0, 15.0), zz)], cavity=[inner(W, B.Z_RIM + stock)],
                 prints=lambda c: [G.box(x0 + W + c, x1 - W - c, -BY + W + c, BY - W - c, B.Z_RIM + stock, B.Z_RIM + stock + plen)])
    elif name == 'lid':
        s.update(blank=B.lid(True), finished=B.lid(), plane=(2, B.Z_LID), sides=(-1,), pads=[G.box(x0, x1, -BY, BY, B.Z_RIM - stock, B.Z_RIM)])
    elif name == 'mast_bracket':
        zb = -160.0 - stock
        s.update(blank=AX.mast_bracket(True), finished=AX.mast_bracket(), plane=(1, 0.0), sides=(1, -1), pads=[G.cyl(38.0, stock, (0, 0, zb), zz)],
                 holes=[G.cyl(30.25 - stock, -60.0 - zb, (0, 0, zb), zz), G.cyl(15.5 - stock, 33.0, (0, 0, -50.0), zz)], cavity=[G.cyl(47.0, 16.0, (0, 0, -17.0), zz)],
                 prints=lambda c: [G.cyl(30.25 - stock - c, plen, (0, 0, zb - plen), zz), G.cyl(47.0 - c, plen, (0, 0, -1.0), zz)])
    elif name == 'yoke_arm':
        ze, y1 = K['z_el'], K['arm_boss_end']
        s.update(blank=AX.yoke_arm(1, True), finished=AX.yoke_arm(1), plane=(2, float(ze)), sides=(1, -1),
                 pads=[G.box(0.0, 50.0, 88.0, 112.0, ze + K['saddle_h'], ze + K['saddle_h'] + stock), G.cyl(20.0, stock, (0, y1, ze), zy)],
                 holes=[G.cyl(10.0 - stock, y1 + stock - K['arm_y'][0], (0, K['arm_y'][0], ze), zy)],
                 prints=lambda c: [G.cyl(10.0 - stock - c, plen, (0, y1 + stock, ze), zy), G.cyl(10.0 - stock - c, plen, (0, K['arm_y'][0] - plen, ze), zy)])
    elif name == 'saddle':
        ze, t = K['z_el'], K['saddle_t']
        z0, a0, a1, sy = ze + K['saddle_h'], K['saddle_a'][0], K['saddle_a'][1], K['saddle_y']
        s.update(blank=AX.saddle(True), finished=AX.saddle(), plane=(2, z0 + t + stock), sides=(-1,),
                 pads=[G.box(a0, a1, -sy, sy, z0 - stock, z0), G.box(a0, a1, -sy, sy, z0 + t, z0 + t + stock)],
                 keep=[G.box(K['boom_a'] - 14.0, K['boom_a'] + 14.0, -38.0, 38.0, z0 - stock - 1, z0 + t + stock + 1)])
    else:
        ze, bt = K['z_el'], K['block_t']
        z0, a0, a1, yc, hw = ze + K['saddle_h'] + K['saddle_t'] + K['boom_w'], K['saddle_a'][0], K['saddle_a'][1], K['block_y'], K['block_w'] / 2
        s.update(blank=AX.boom_clamp(1, True), finished=AX.boom_clamp(1), plane=(2, z0 + bt + stock), sides=(-1,),
                 pads=[G.box(a0, a1, yc - hw, yc + hw, z0 - stock, z0), G.box(a0, a1, yc - hw, yc + hw, z0 + bt, z0 + bt + stock)])
    return s


def _fuse(shapes):
    return shapes[0].multiFuse(shapes[1:]) if len(shapes) > 1 else shapes[0]


def _bp(sp):
    return _fuse([sp['blank']] + sp['pads'])


def preform(sp):
    out = _bp(sp)
    gone = sp['holes'] + sp['keep']
    return out.cut(_fuse(gone)) if gone else out


def core(sp, clear):
    bp = _bp(sp)
    parts = [c.cut(bp) for c in sp['cavity']] + sp['holes'] + sp['prints'](clear)
    return _fuse(parts) if parts else None


def pattern_base(sp):
    out = _fuse([_bp(sp)] + sp['cavity'] + sp['prints'](0.0))
    return out.cut(_fuse(sp['keep'])) if sp['keep'] else out


def scaled(shape, f):
    import FreeCAD
    m = FreeCAD.Matrix()
    m.scale(f, f, f)
    return shape.transformGeometry(m)


def draft_half(half, axis, c, sg, p):
    """Additive draft by a stack of offset slices: outer faces and lumps taper by draft_out / draft_in, widest at the parting plane."""
    import Part
    from FreeCAD import Vector as V
    n = V(*[1.0 if i == axis else 0.0 for i in range(3)])
    bb = half.BoundBox
    lo, hi = (bb.XMin, bb.YMin, bb.ZMin)[axis], (bb.XMax, bb.YMax, bb.ZMax)[axis]
    H = hi - c if sg > 0 else c - lo
    slabs, t = [], 0.0
    while t < H - 1e-6:
        dt = min(p['draft_step'], H - t)
        tm = t + dt / 2
        wires = half.slice(n, c + sg * tm)
        if wires:
            faces = Part.makeFace(wires, 'Part::FaceMakerBullseye').Faces
            for fc in faces:
                reg = Part.Face(fc.OuterWire).makeOffset2D(draft_offset(p['draft_out'], H - tm))
                for w in fc.Wires:
                    if not w.isSame(fc.OuterWire):
                        try:
                            reg = reg.cut(Part.Face(w).makeOffset2D(-draft_offset(p['draft_in'], H - tm)))
                        except Exception:
                            pass
                reg.translate(n * (-sg * dt / 2))
                slabs.append(reg.extrude(n * (sg * dt)))
        t += dt
    return half.fuse(_fuse(slabs)).removeSplitter() if slabs else half


def pattern_halves(sp, p):
    """Scaled, drafted halves of the pattern: [(side, solid)] and the assembled raw pattern."""
    import geom as G
    axis, c = sp['plane']
    f = p['shrink']
    sb, cc = scaled(pattern_base(sp), f), c * f
    big = 1.0e4
    halves = []
    for sg in sp['sides']:
        lo, hi = (cc, cc + big) if sg > 0 else (cc - big, cc)
        ext = [(-big, big)] * 3
        ext[axis] = (lo, hi)
        h = sb.common(G.box(*[v for e in ext for v in e]))
        halves.append((sg, draft_half(h, axis, cc, sg, p)))
    return halves, (_fuse([h for _, h in halves]).removeSplitter() if len(halves) > 1 else halves[0][1])


def orient(shape, axis, sg):
    """Rotate so the parting plane is the bed (z = 0) and the half stands on it; returns the shape at the origin."""
    from FreeCAD import Vector as V
    s = shape.copy()
    if axis == 2 and sg < 0:
        s.rotate(V(0, 0, 0), V(1, 0, 0), 180)
    elif axis == 0:
        s.rotate(V(0, 0, 0), V(0, 1, 0), -90 * sg)
    elif axis == 1:
        s.rotate(V(0, 0, 0), V(1, 0, 0), 90 * sg)
    bb = s.BoundBox
    s.translate(V(-bb.XMin, -bb.YMin, -bb.ZMin))
    return s


def _find_keys(s, ax, mid, r, dd, n=2):
    """Up to n key positions on the cut plane where the solid is present on both sides over the key depth and the key radius."""
    from FreeCAD import Vector as V
    bb = s.BoundBox
    lo, hi = (bb.XMin, bb.YMin, bb.ZMin), (bb.XMax, bb.YMax, bb.ZMax)
    i, j = [k for k in range(3) if k != ax]
    found = []
    u = lo[i] + r + 2
    while u < hi[i] - r - 2:
        v = lo[j] + r + 2
        while v < hi[j] - r - 2:
            ok = True
            for off in (-3.0, dd + 1.0):
                for du, dv in ((0, 0), (r + 1, 0), (-r - 1, 0), (0, r + 1), (0, -r - 1)):
                    q = [0.0, 0.0, 0.0]
                    q[ax], q[i], q[j] = mid + off, u + du, v + dv
                    if not s.isInside(V(*q), 1e-6, True):
                        ok = False
            if ok:
                found.append((u, v))
            v += 10.0
        u += 10.0
    if len(found) < 2:
        return found
    a = found[0]
    return [a, max(found, key=lambda q: (q[0] - a[0]) ** 2 + (q[1] - a[1]) ** 2)][:n]


def split_to_fit(shape, fit, p):
    """Bisect over-size pieces at their midpoint and add one pin / socket pair per key position on every cut. Returns the list of pieces."""
    import geom as G
    nodes = []

    def rec(s):
        if s.isNull() or s.Volume < 1.0:
            return []
        # the default BoundBox of a boolean result can be loose (surface poles) and never shrink; use the tight one
        bb = s.optimalBoundingBox(True, False) if hasattr(s, 'optimalBoundingBox') else s.BoundBox
        dims = (bb.XLength, bb.YLength, bb.ZLength)
        ax = max(range(3), key=lambda k: dims[k] - fit[k])
        if dims[ax] <= fit[ax]:
            return [[s]]
        mid = (bb.XMin, bb.YMin, bb.ZMin)[ax] + dims[ax] / 2
        big = 1.0e4
        ext_lo, ext_hi = [(-big, big)] * 3, [(-big, big)] * 3
        ext_lo[ax], ext_hi[ax] = (-big, mid), (mid, big)
        a = rec(s.common(G.box(*[v for e in ext_lo for v in e])))
        b = rec(s.common(G.box(*[v for e in ext_hi for v in e])))
        nodes.append((s, ax, mid, a, b))
        return a + b
    leaves = rec(shape)
    r, dd, cl = p['dowel_d'] / 2, p['dowel_len'], p['dowel_clear']
    for s, ax, mid, a, b in nodes:
        d = [0.0, 0.0, 0.0]
        d[ax] = 1.0
        for u, v in _find_keys(s, ax, mid, r, dd):
            q = [0.0, 0.0, 0.0]
            i, j = [k for k in range(3) if k != ax]
            q[i], q[j] = u, v
            q[ax] = mid - 2.0
            pin = G.cyl(r, dd + 2.0, tuple(q), tuple(d))
            q[ax] = mid
            sock = G.cyl(r + cl, dd + 0.5, tuple(q), tuple(d))
            for leaf in a:
                leaf[0] = leaf[0].fuse(pin) if leaf[0].common(pin).Volume > 1.0 else leaf[0]
            for leaf in b:
                leaf[0] = leaf[0].cut(sock) if leaf[0].common(sock).Volume > 1.0 else leaf[0]
    return [l[0] for l in leaves]


def mesh(shape, tol=0.05):
    v, t = shape.tessellate(tol)
    return weld([(p.x, p.y, p.z) for p in v], t)


def _write_all(base, shape, step=True):
    """STEP + welded STL + 3MF of one shape; returns watertight flag."""
    v, t = mesh(shape)
    if step:
        shape.exportStep(base + '.step')
    write_stl(base + '.stl', v, t)
    write_3mf(base + '.3mf', [(os.path.basename(base), v, t)])
    return watertight(t)


def vol(shape):
    """Volume of a boolean result; OCC returns a null shape (not an empty one) when nothing is left."""
    return 0.0 if shape.isNull() else shape.Volume


def cutvol(a, b):
    """Volume of a minus b; FreeCAD may raise 'Null shape' instead of returning an empty shape when nothing is left."""
    try:
        return vol(a.cut(b))
    except ValueError:
        return 0.0


def build_part(name, outdir):
    """Build, check and export one cast part; raises AssertionError on a failed check. Returns the report entry."""
    p = cast_params(name)
    stock = p['machining']
    sp = spec(name, stock, p['core_print'])
    fin, pre = sp['finished'], preform(sp)
    gone = sp['holes'] + sp['keep']
    hk = _fuse(gone) if gone else None
    assert fin.isValid() and pre.isValid() and cutvol(fin, pre) < 1.0, name + ': preform must contain the finished part'
    for pad in sp['pads']:
        lost = vol(pad.common(hk)) if hk else 0.0
        assert cutvol(pad, pre) <= lost + 1.0, name + ': a stock pad is missing from the preform'
    halves, raw = pattern_halves(sp, p)
    spre = scaled(pre, p['shrink'])
    assert raw.isValid() and cutvol(spre, raw) < 1.0, name + ': scaled preform must lie inside the pattern'
    bb, pb = raw.BoundBox, pre.BoundBox
    assert bb.XLength >= p['shrink'] * pb.XLength - 0.01 and bb.YLength >= p['shrink'] * pb.YLength - 0.01 and bb.ZLength >= p['shrink'] * pb.ZLength - 0.01, name
    cr = core(sp, p['core_clear'])
    if cr is not None:
        assert cr.isValid() and vol(cr.common(pre)) < 1.0, name + ': core overlaps the preform'
    os.makedirs(outdir, exist_ok=True)
    pf = lambda sfx: os.path.join(outdir, '%s_%s' % (name, sfx))
    ok = {'finished': _write_all(pf('finished'), fin), 'preform': _write_all(pf('preform'), pre), 'pattern': _write_all(pf('pattern'), raw)}
    if cr is not None:
        cr.exportStep(pf('core') + '.step')
    fit, pv = print_fit(), [v * 1000.0 for v in IN.I['print_volume']]
    pieces, objs = [], []
    for sg, h in halves:
        for pc in split_to_fit(orient(h, sp['plane'][0], sg), fit, p):
            assert pc.isValid(), name + ': invalid pattern piece'
            v, t = mesh(pc)
            assert watertight(t), name + ': pattern piece not watertight'
            b = pc.BoundBox
            assert max(b.XLength - pv[0], b.YLength - pv[1], b.ZLength - pv[2]) <= 0, name + ': piece exceeds the print volume'
            write_stl(pf('pattern_p%d' % (len(pieces) + 1)) + '.stl', v, t)
            objs.append(('%s_pattern_p%d' % (name, len(pieces) + 1), v, t))
            pieces.append(round(pc.Volume / 1000.0, 1))
    write_3mf(pf('pattern') + '.3mf', objs)
    mock = split_to_fit(fin.copy(), fit, p)
    mobjs = []
    for k, pc in enumerate(mock):
        v, t = mesh(pc)
        mobjs.append(('%s_mockup_%d' % (name, k + 1), v, t))
    write_3mf(pf('mockup') + '.3mf', mobjs)
    lost = lost_pla(name, outdir)
    for part, flag in ok.items():
        assert flag, '%s %s mesh is not watertight' % (name, part)
    pad_area = sum(pad.Volume / stock for pad in sp['pads']) / 100.0
    return dict(rev=P.REV, qty=QTY[name], finished_cm3=fin.Volume / 1000.0, preform_cm3=pre.Volume / 1000.0, cast_cm3=pre.Volume / 1000.0,
                pattern_cm3=raw.Volume / 1000.0, pla_cm3=raw.Volume / 1000.0 * p['pla_fill'], core_cm3=cr.Volume / 1000.0 if cr is not None else 0.0,
                machined_cm2=pad_area, pattern_pieces=len(pieces), mockup_pieces=len(mock), stock_mm=stock, hot_spots=hot_spot_report(name), lost_pla=lost,
                dowels=flask_dowels((pb.XMin, pb.YMin, pb.ZMin, pb.XMax, pb.YMax, pb.ZMax), sp['plane'][0]))


def lost_pla(name, outdir):
    """CONSUMABLE lost-PLA variant (params.CAST_LOST only): hollow shell of the preform with CAST_LOST stock, scaled by its own shrinkage."""
    L = P.CAST_LOST
    sp = spec(name, L['machining'], 0.0)
    pre = preform(sp)
    pat = scaled(pre, L['shrink'])
    assert pat.isValid(), name + ': lost-PLA pattern invalid'
    ok = _write_all(os.path.join(outdir, name + '_lostpla'), pat)
    return dict(stock_mm=L['machining'], cast_cm3=pre.Volume / 1000.0, pla_cm3=pat.Area * L['wall'] / 1000.0, watertight=ok)


def build_all(outdir):
    return {n: build_part(n, outdir) for n in PARTS}


if __name__ == '__main__':
    self_test()
