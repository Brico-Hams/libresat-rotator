"""LSR-2 phase 11d, Route B: 3-axis CNC from 6082-T6 / 6061-T6 block or plate. Machinable variant, blanks, set-up sheets and CAM CSVs (mm).

Machine travel comes from inputs.py (cnc_travel, PARAMETRIC assumption); tools, feeds, rates and tolerances from params.CNC / params.TOL (PARAMETRIC).
The body is not machinable in one piece (336 mm tall, cavity 300 mm deep, tool reach <= 75 mm): it is split by CSG into bolted z-slabs.
Horizontal features (EL bores, EL gearbox pad, breather) cannot be reached by a vertical 3-axis spindle on a slab: the sheets flag them
as OPEN DECISION (4th axis / angle plate / horizontal line-boring outsourced). NO NC CODE is generated: machine, controller, post-processor
and simulation are unknown; the feeds and speeds below are starting values, "recompute for the real tool/alloy/machine".
Fusion references (brief): https://help.autodesk.com/view/fusion360/ENU/?contextId=MFG-CREATE-SETUP and ...?contextId=MFG-SIMULATION
Run: python route_b.py  (pure-Python self-test + writes cam/lsr2/<part>_setups.csv); build.py calls build_all() under freecadcmd.
"""
import csv
import math
import os
import params as P
import inputs as IN
import body as B
import axes as AX

C = P.CNC
K = AX.K
ZE = K['z_el']
Z_SLABS = (-22.0, 46.0, 112.0, 176.0, 238.0, B.Z_RIM)        # body slab joints (PARAMETRIC): EL boss (z 242..294) and shelf (140..148) stay inside one slab
YB = (82.0, 82.0, 82.0, 82.0, 86.0)                          # half width of each body slab incl. bosses / side plates
# (part, piece, lo, hi, machine-z axis index): boxes in the part frame; the blank is derived from them
PIECES = [('body', 'slab%d' % (i + 1), (B.BX[0], -YB[i], Z_SLABS[i]), (B.BX[1], YB[i], Z_SLABS[i + 1]), 2) for i in range(5)] + [
    ('lid', 'lid', (B.BX[0], -B.BY, B.Z_RIM), (B.BX[1], B.BY, B.Z_LID), 2),
    ('mast_bracket', 'tube_clamp', (-38.0, -38.0, -160.0), (58.0, 38.0, -60.0), 1),          # lies on its side: the Ø76 tube (76) is the machine z
    ('mast_bracket', 'top_plate', (-55.0, -55.0, -60.0), (55.0, 55.0, -2.0), 2),             # bolted to the tube clamp at z = -60 (joint lands: open decision)
    ('yoke_arm', 'yoke_arm', (-20.0, min(K['arm_y'][0], 88.0), ZE - 20.0), (50.0, K['arm_boss_end'], ZE + K['saddle_h']), 1),
    ('saddle', 'saddle', (K['saddle_a'][0], -K['saddle_y'], ZE + K['saddle_h']), (K['saddle_a'][1], K['saddle_y'], ZE + K['saddle_h'] + K['saddle_t']), 2),
    ('boom_clamp', 'boom_clamp', (K['saddle_a'][0], K['block_y'] - K['block_w'] / 2, ZE + K['saddle_h'] + K['saddle_t'] + K['boom_w']),
     (K['saddle_a'][1], K['block_y'] + K['block_w'] / 2, ZE + K['saddle_h'] + K['saddle_t'] + K['boom_w'] + K['block_t']), 2)]
PARTS = ('body', 'lid', 'mast_bracket', 'yoke_arm', 'saddle', 'boom_clamp')
QTY = {'body': 1, 'lid': 1, 'mast_bracket': 1, 'yoke_arm': 2, 'saddle': 1, 'boom_clamp': 2}
# Alloy per part (PARAMETRIC; Rp0.2 ~240-250 MPa for both in T6 per EN 485-2 / EN 755-2, DATASHEET: check the mill certificate): 6082 for the loaded
# parts (more strength per EUR in EU plate), 6061 for the plates and blocks that are stiffness- or clamp-governed and where off-cuts are cheap.
ALLOY = {'body': '6082-T6', 'lid': '6061-T6', 'mast_bracket': '6082-T6', 'yoke_arm': '6082-T6', 'saddle': '6061-T6', 'boom_clamp': '6061-T6'}
TOOLS = {t['name']: t for t in C['tools']}
Z_USABLE = IN.I['cnc_travel'][2] * 1000.0 - C['tool_clear_z']


def snap(t):
    return next(p for p in C['plate_t'] if p >= t)


def blank_dims(piece):
    """(x, y, z) of the stock in the part frame and the machine-z index: bbox + margin on every face + clamping tab, thickness snapped to a plate."""
    _, _, lo, hi, zi = piece
    dims = [h - l for l, h in zip(lo, hi)]
    out = [d + 2 * C['margin'] + (0 if i == zi else 2 * C['tab']) for i, d in enumerate(dims)]
    out[zi] = snap(dims[zi] + 2 * C['margin'])
    return out, zi


def fits_machine(piece):
    dims, zi = blank_dims(piece)
    foot = sorted(d for i, d in enumerate(dims) if i != zi)
    tx, ty, tz = [v * 1000.0 for v in IN.I['cnc_travel']]
    return dims[zi] <= tz - C['tool_clear_z'] and foot[0] <= min(tx, ty) and foot[1] <= max(tx, ty)


def blank_kg(part):
    return sum(math.prod(blank_dims(p)[0]) for p in PIECES if p[0] == part) / 1e6 * C['density']


def cost(part, finished_cm3, setups=None):
    """Block-stock cost: blank mass, removed volume, machining minutes (removal / MRR + set-ups) and EUR (stock + machine time), per part (qty 1)."""
    bk = blank_kg(part)
    removed = bk / C['density'] * 1000.0 - finished_cm3
    n_set = setups if setups is not None else sum(len(SETUPS[TYPE[p[1]]]) for p in PIECES if p[0] == part)
    minutes = removed / C['mrr_cm3_min'] + n_set * C['setup_min']
    return dict(blank_kg=bk, removed_cm3=removed, minutes=minutes, stock_eur=bk * C['price_eur_kg'], machine_eur=minutes / 60.0 * C['rate_eur_h'])


def cutting(tool, kind, depth):
    """Starting values rpm / feed / doc / woc for a tool and operation kind: PARAMETRIC, recompute for the real tool, alloy and machine."""
    t = TOOLS[tool]
    if t['d'] == 0:
        return 2000, 100, 0.0, 0.0
    rpm = min(C['vc'] * 1000.0 / (math.pi * t['d']), C['rpm_max'])
    feed = rpm * t['z'] * C['fz']
    if kind == 'rough':
        return round(rpm), round(feed), C['ap_rough'] * t['d'], C['ae_rough'] * t['d']
    if kind == 'finish':
        return round(rpm), round(feed), C['ap_finish'] * t['d'], C['stock_finish']
    if kind == 'face':
        return round(rpm), round(feed), 1.0, 0.8 * t['d']
    return round(rpm), round(feed * 0.5), 0.0, 0.0          # drilling / chamfer: half feed


# --- set-up sheets: op = (kind, tool, depth mm, smallest inside radius mm (0 = none), text). One list per piece type. ----------------------
S1_NOTE = 'datum A = ground blank underside on the fixture, B = edge stop, C = dowel hole #1 (drilled in the clamping tab)'
SETUPS = {
    'slab': [
        dict(name='S1 joint face A up', orient='machine z = part z, joint face A up', clamp='fixture plate, 6 toe clamps on the tabs', datum=S1_NOTE, ops=[
            ('face', 'E12', 2, 0, 'face joint face A, skim 0.5'),
            ('rough', 'E12L', 66, B.W + 1, 'rough the through-cavity profile (tabs kept), inside corners R6 from params.CNC corner_r'),
            ('rough', 'E12', 20, 6, 'rough ribs, shelf, pillar pockets with finishing stock'),
            ('finish', 'E8L', 36, 4, 'finish walls and lid (rim) face by contour to mid depth; base face by contour: check flat_base'),
            ('finish', 'E6', 20, 3, 'finish rib and wall corners R3'),
            ('drill', 'D5', 20, 0, 'joint bolt pilots M6 (tap after) and 2 dowel holes D6 for the flip, reamed'),
            ('bore', 'BH', 66, 0, 'AZ bore, gland, drain and lid-screw bores with 0.3 stock; AZ bore finished by line boring after assembly')]),
        dict(name='S2 flip, joint face B up', orient='flipped 180 deg about x on the dowels', clamp='same plate, soft pins in the D6 holes (verified datum)', datum='A = joint face B from S1 (flatness checked), pins = S1 dowels', ops=[
            ('face', 'E12', 2, 0, 'face joint face B to the slab thickness'),
            ('finish', 'E8L', 36, 4, 'second half of the walls and lid face contour, blend at mid depth, remove tabs'),
            ('drill', 'D5', 20, 0, 'joint bolt pilots M6, chamfer, cable passages and sensor bosses where present'),
            ('chamfer', 'E8', 1, 0, 'chamfer 0.5 x 45 all edges and hole mouths')]),
        dict(name='S3 horizontal features (OPEN DECISION)', orient='slab on an angle plate: EL axis / gearbox pad / breather facing up', clamp='angle plate or 4th axis: NOT within inputs cnc_travel',
             datum='transfer fixture on the S1 dowels; one reference for the coaxial EL bores', ops=[
            ('bore', 'BH', 40, 0, 'EL bores Ø32.. in the EL slab (coaxial, one reference, tolerance TOL el_coax), seat bore from the cavity; or outsource horizontal line boring'),
            ('drill', 'D5', 20, 0, 'EL gearbox pad holes M6, breather Ø8: horizontal, 4th axis or outsourced')])],
    'plate': [
        dict(name='S1 top face up', orient='plate flat, datum face down', clamp='vise with soft jaws (small) or fixture plate + toe clamps (lid, saddle)', datum='A = ground blank underside, B = fixed jaw / edge stop, C = end stop', ops=[
            ('face', 'E12', 2, 0, 'face top, skim 0.5'),
            ('rough', 'E12', 6, 6, 'rough pockets, window and outer profile (tabs kept), gasket groove on the lid underside is cut in S2'),
            ('finish', 'E6', 6, 3, 'finish pockets and outer profile'),
            ('drill', 'D5', 12, 0, 'through holes (reamed where fits) and screw holes; dowel holes D6 for the flip'),
            ('chamfer', 'E8', 1, 0, 'chamfer 0.5 x 45')]),
        dict(name='S2 flip', orient='flipped on the dowels', clamp='soft pins in the D6 holes', datum='A = face machined in S1, pins = S1 dowels', ops=[
            ('face', 'E12', 2, 0, 'face to thickness'),
            ('finish', 'E6', 3, 3, 'lid underside: gasket groove 2 deep and face finished from this setup; saddle window from the other face'),
            ('chamfer', 'E8', 1, 0, 'chamfer 0.5 x 45, remove tabs')])],
    'tube': [
        dict(name='S1 end A up', orient='tube lying on its side, axis along machine x (76 across z)', clamp='fixture plate + 4 toe clamps on tabs', datum='A = ground blank underside, B = side stop, C = dowel hole', ops=[
            ('face', 'E12', 2, 0, 'face end A'),
            ('rough', 'E12L', 50, 12, 'rough bore Ø60.5 helically to mid length, 0.3 stock; lugs and slit pocket'),
            ('finish', 'E8L', 36, 4, 'finish the lug profile'),
            ('drill', 'D5', 20, 0, 'pinch bolt pilots M8 (D6.8) across the slit, dowel holes D6'),
            ('bore', 'BH', 50, 0, 'bore Ø60.5 to size from end A (half length)')]),
        dict(name='S2 flip, end B up', orient='flipped 180 deg about x', clamp='soft pins', datum='A = end A face from S1', ops=[
            ('face', 'E12', 2, 0, 'face end B to length'),
            ('bore', 'BH', 50, 0, 'bore Ø60.5 from end B, blend at mid length, check straightness'),
            ('chamfer', 'E8', 1, 0, 'chamfer bore mouths and edges; slit saw cut or E3 slitting')])],
    'cap': [
        dict(name='S1 flange face up', orient='vertical, mating face up', clamp='fixture plate, round blank, 4 toe clamps', datum='A = ground underside, B/C = tab dowels', ops=[
            ('face', 'E12', 2, 0, 'face the mating face'),
            ('rough', 'E12L', 40, 6, 'rough cup ring and core outline'),
            ('finish', 'E8', 24, 4, 'finish labyrinth ring R47..55 and outline'),
            ('bore', 'BH', 35, 0, 'Ø31 shaft pocket 35 deep, 0.3 stock'),
            ('drill', 'D5', 12, 0, 'joint bolt pilots M6 to the tube clamp, Ø6 cross pin pilot')]),
        dict(name='S2 flip', orient='flipped on dowels', clamp='soft pins', datum='A = face from S1', ops=[
            ('face', 'E12', 2, 0, 'face the joint face to the thickness'),
            ('chamfer', 'E8', 1, 0, 'chamfer; remove tabs')])],
    'arm': [
        dict(name='S1 inner face up', orient='plate flat, y vertical (machine z), inner face up', clamp='vise with soft jaws (Ø20 boss profile stop)', datum='A = ground underside, B = fixed jaw, C = end stop', ops=[
            ('face', 'E12', 2, 0, 'face inner face'),
            ('rough', 'E12', 25, 6, 'rough the arm profile, boss and flange with stock'),
            ('finish', 'E8', 24, 4, 'finish profile; flange top face at +125 above the EL axis is the saddle datum'),
            ('drill', 'D8.5', 25, 0, 'through hole pilot for the Ø20 bore; M6 holes in the flange'),
            ('bore', 'BH', 25, 0, 'Ø20 H7 bore, then 6 x 6 key way by slotting (E6) in the same set-up')]),
        dict(name='S2 flip, outer face up', orient='flipped 180 deg on dowels', clamp='soft jaws', datum='A = inner face from S1', ops=[
            ('face', 'E12', 2, 0, 'face outer boss end to the length 25'),
            ('chamfer', 'E8', 1, 0, 'chamfer bore mouth and edges')])]}
TYPE = {'slab1': 'slab', 'slab2': 'slab', 'slab3': 'slab', 'slab4': 'slab', 'slab5': 'slab', 'lid': 'plate', 'saddle': 'plate', 'boom_clamp': 'plate',
        'tube_clamp': 'tube', 'top_plate': 'cap', 'yoke_arm': 'arm'}
INSPECT = [('EL bore coaxiality (both bores, one reference)', 'el_coax'), ('AZ axis perpendicular to EL axis', 'az_el_perp'), ('lid (rim) face flatness', 'flat_lid'),
           ('base face flatness', 'flat_base'), ('datum distances (base to EL axis, AZ to EL)', 'datum_dist'), ('AZ 6206 seats', 'seat_6206'), ('EL 6004 seats', 'seat_6004'),
           ('Ø62 / Ø20 H7 bores', 'bore_h7')]
POST = ['deburr and chamfer all edges', 'clean (degrease, ultrasonic for threads)', 'finish: chromate conversion (conductive, default) or anodise (masks on fits, threads and the electrical-continuity zones: lid-body earth lands)',
        'final dimensional check after finishing (fits and threads are masked, so coating thickness does not move them)']


def setup_rows(part):
    rows = []
    for p in PIECES:
        if p[0] != part:
            continue
        seq = 0
        for si, s in enumerate(SETUPS[TYPE[p[1]]], 1):
            for kind, tool, depth, rmin, text in s['ops']:
                seq += 1
                rpm, feed, doc, woc = cutting(tool, kind, depth)
                holder = 'boring head holder (per machine)' if tool == 'BH' else 'ER32 collet'
                rows.append(dict(part=part, piece=p[1], setup=s['name'], seq=seq, op=kind, work_offset='WCS%d (G5%d) at the datum corner' % (si, 3 + si),
                                 blank_orientation=s['orient'], clamp=s['clamp'], holder=holder, tool=tool, rpm=rpm, feed_mm_min=feed, doc_mm=doc, woc_mm=woc,
                                 depth_mm=depth, note=text + ' | starting values: recompute for the real tool/alloy/machine; no NC code'))
    return rows


def write_csv(part, outdir):
    os.makedirs(outdir, exist_ok=True)
    rows = setup_rows(part)
    with open(os.path.join(outdir, part + '_setups.csv'), 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    return len(rows)


def self_test():
    assert abs(cutting('E8', 'rough', 10)[0] - 9947) <= 1 and abs(cutting('E12', 'rough', 10)[1] - 3 * 0.05 * 250000 / (math.pi * 12)) <= 1
    assert abs(250.0 * 1000 / (math.pi * 10) * 3 * 0.05 - 1193.7) < 0.2                   # hand check: D10, Vc 250, z 3, fz 0.05 -> 7958 rpm, 1194 mm/min
    assert snap(63 + 2 * C['margin']) == 80 and snap(8 + 2 * C['margin']) == 12 and abs(Z_USABLE - 85.0) < 1e-6
    for p in PIECES:
        dims, zi = blank_dims(p)
        assert fits_machine(p), (p[1], dims)
        for k in range(3):
            assert dims[k] >= p[3][k] - p[2][k] + (2 * C['margin'] if k != zi else 0) - 1e-6
    assert [p[1] for p in PIECES if p[0] == 'body'] == ['slab%d' % i for i in range(1, 6)]
    assert all(Z_SLABS[i] < Z_SLABS[i + 1] for i in range(5)) and not any(Z_SLABS[i] < ZE + 26 and ZE - 26 < Z_SLABS[i] for i in range(6))      # no joint through the EL boss
    for part in PARTS:
        assert part in ALLOY and any(p[0] == part for p in PIECES)
        for p in (q for q in PIECES if q[0] == part):
            for s in SETUPS[TYPE[p[1]]]:
                for kind, tool, depth, rmin, text in s['ops']:
                    t = TOOLS[tool]
                    assert depth <= t['reach'], (part, p[1], s['name'], tool, depth, t['reach'])            # pocket depth within the tool reach
                    assert rmin == 0 or t['d'] == 0 or rmin >= t['d'] / 2, (part, p[1], s['name'], tool, rmin)    # inside radius not below the tool radius
        assert setup_rows(part) and all(r['rpm'] > 0 and r['feed_mm_min'] > 0 for r in setup_rows(part))
    assert all(tol in P.TOL for _, tol in INSPECT)
    print('route B self-test OK (blank total body %.1f kg, lid %.1f kg)' % (blank_kg('body'), blank_kg('lid')))


# --- FreeCAD part -------------------------------------------------------------------------------------------------------------------
def machinable(part):
    """Finished solid of the 3-axis variant: finished + R6 fillers in the four vertical inside corners of the body cavity (the tool leaves that radius)."""
    import geom as G
    import body as BD
    import axes as AXX
    fin = {'body': BD.body, 'lid': BD.lid, 'mast_bracket': AXX.mast_bracket}.get(part)
    fin = fin() if fin else (AXX.yoke_arm(1) if part == 'yoke_arm' else AXX.saddle() if part == 'saddle' else AXX.boom_clamp(1))
    if part != 'body':
        return fin
    r, w = C['corner_r'], BD.W
    fills = []
    for cx, ex in ((BD.BX[0] + w, 1), (BD.BX[1] - w, -1)):
        for cy, ey in ((-BD.BY + w, 1), (BD.BY - w, -1)):
            ax, ay = cx + ex * r, cy + ey * r                               # arc centre of the R6 corner left by the tool
            blk = G.box(min(cx, ax), max(cx, ax), min(cy, ay), max(cy, ay), w, BD.Z_RIM)
            fills.append(blk.cut(G.cyl(r, BD.Z_RIM - w, (ax, ay, w), (0, 0, 1))))
    return fin.fuse(fills)


def build_part(part, outdir):
    import geom as G
    import Part
    os.makedirs(outdir, exist_ok=True)
    fin = machinable(part)
    assert fin.isValid(), part + ': machinable variant invalid'
    pieces, blanks, vol = [], [], 0.0
    for p in (q for q in PIECES if q[0] == part):
        _, name, lo, hi, zi = p
        piece = fin.common(G.box(lo[0], hi[0], lo[1], hi[1], lo[2], hi[2]))
        dims, _ = blank_dims(p)
        m = C['margin']
        bl = [l - m - (0 if i == zi else C['tab']) for i, l in enumerate(lo)]
        bh = [bl[i] + dims[i] for i in range(3)]
        blank = G.box(bl[0], bh[0], bl[1], bh[1], bl[2], bh[2])
        left = piece.cut(blank)
        assert piece.isValid() and blank.isValid() and (left.isNull() or left.Volume < 1.0), '%s/%s: blank must contain the finished piece' % (part, name)
        vol += piece.Volume
        pieces.append((name, piece))
        blanks.append(blank)
        if len([q for q in PIECES if q[0] == part]) > 1:
            piece.exportStep(os.path.join(outdir, '%s_%s_finished.step' % (part, name)))
            blank.exportStep(os.path.join(outdir, '%s_%s_blank.step' % (part, name)))
    assert abs(vol - fin.Volume) < 1e-3 * fin.Volume + 1.0, part + ': pieces do not add up to the variant'
    fin.exportStep(os.path.join(outdir, part + '_finished.step'))
    Part.makeCompound(blanks).exportStep(os.path.join(outdir, part + '_blank.step'))
    c = cost(part, fin.Volume / 1000.0)
    return dict(alloy=ALLOY[part], qty=QTY[part], finished_cm3=fin.Volume / 1000.0, blank_cm3=sum(b.Volume for b in blanks) / 1000.0, pieces=[n for n, _ in pieces],
                setups=sum(len(SETUPS[TYPE[n]]) for n, _ in pieces), **{k: round(v, 3) for k, v in c.items()})


def build_all(outdir):
    return {p: build_part(p, outdir) for p in PARTS}


if __name__ == '__main__':
    self_test()
    cam = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'cam', 'lsr2')
    print('CAM rows:', {p: write_csv(p, cam) for p in PARTS}, '(no NC code: see docs/LSR2_ROUTE_B_CNC.md)')
