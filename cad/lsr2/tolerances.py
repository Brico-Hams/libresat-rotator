"""LSR-2 phase 11e: tolerance table (datums, tolerances, ISO fits, finishes, justification) and the generator of docs/LSR2_TOLERANCES.md and docs/LSR2_INSPECTION.md.

Run: python tolerances.py  (self-test, then writes both documents; pure Python, no imports beyond params.py).
Tags: D = DATASHEET (ISO 286-2 limits, ISO 492 normal bearing class, catalogue sizes), P = PARAMETRIC (our choice, editable here), M = MEASURE (shop capability: ask the shop).
Fit choices follow the usual bearing-maker practice (SKF / FAG "recommended fits": point load on the stationary ring and slow motion -> loose or transition fit
on that ring, light load on an aluminium housing -> J7 instead of a tight N7/P7 because aluminium expands about twice as much as the steel outer ring). VERIFY with the
maker's table for the real bearing and load before the first cut. Numeric zone = total tolerance zone width in mm of the checked characteristic.
"""
import os
import params as P

DATUMS = [('A', 'Body bottom mounting face (the face on the mast bracket); flatness 0.05; all heights are measured from it.'),
          ('B', 'AZ axis: common axis of the two 6206 seats (Ø62) in the pillar.'),
          ('C', 'EL axis: common axis of the two 6004 seats (Ø42) in the side wall bosses; height 268 above A.')]
T = P.TOL
# local additions (PARAMETRIC): not in params.TOL because only the drawings and the inspection use them
LOCAL = dict(az_coax=0.04, gb_pos=0.05, saddle_par=0.10, groove_d=0.10, groove_w=0.20, seal_h8=0.039, thrust_h11=0.19, shaft_g6=0.013, seal_run=0.13, mast_bore=0.30,
             pocket=0.10, keyway=0.03, thread_pos=0.30, stub_coax=0.02, pocket_perp=0.10)

# ISO 286-2 limits in µm (upper, lower), DATASHEET; bearing OD / bore: ISO 492 normal class (upper 0, lower -dmp)
ISO = {('62', 'J7'): (18, -12), ('42', 'J7'): (14, -11), ('30', 'g6'): (-7, -20), ('30', 'j6'): (8, -5), ('20', 'h6'): (0, -13), ('20', 'H7'): (21, 0),
       ('32', 'H8'): (39, 0), ('53', 'H11'): (190, 0), ('14', 'g6'): (-6, -17), ('14', 'H7'): (18, 0), ('20', 'h11'): (0, -130)}
BEARING = {'6206 OD 62': (0, -13), '6004 OD 42': (0, -11), '6206 bore 30': (0, -10), '51206 shaft washer bore 30': (0, -10), '6004 bore 20': (0, -10)}
PAIRS = [('62 J7 housing / 6206 outer ring', ('62', 'J7'), '6206 OD 62', True), ('42 J7 housing / 6004 outer ring', ('42', 'J7'), '6004 OD 42', True),
         ('Ø30 g6 shaft / 6206 inner ring', ('30', 'g6'), '6206 bore 30', False), ('Ø30 j6 shaft / 51206 shaft washer', ('30', 'j6'), '51206 shaft washer bore 30', False),
         ('Ø20 h6 shaft / 6004 inner ring', ('20', 'h6'), '6004 bore 20', False)]

# (id, feature, part, datum, nominal, tolerance text, numeric zone mm, Ra, cast-route capability mm, CNC-route capability mm, justification, inspection method, tag)
ROWS = [
    ('T01', 'Mounting face (datum A)', 'body', '-', 'plane', 'flatness 0.05', T['flat_base'], 3.2, 0.03, 0.02,
     'Mates the mast bracket top disc and its labyrinth skirt: a flat face keeps AZ and the whole head level without shims. Cast stock pad machined in one pass; CNC face milled.',
     'surface plate, dial indicator or feeler', 'P'),
    ('T02', 'AZ 6206 seats (2)', 'body', 'B', 'Ø62', 'J7 (+0.018/-0.012), cylindricity %.3f' % T['seat_6206'], T['seat_6206'], 1.6, 0.012, 0.010,
     'Outer rings of the 6206 pair (ISO 492 normal class, 0/-0.013): transition fit J7, loose enough to fit in aluminium, no creep at slow tracking. Bored with the housing in one setup.',
     'bore gauge or air gauge at 2 heights, 2 angles', 'P'),
    ('T03', 'AZ seat coaxiality (2 x Ø62)', 'body', 'B', 'axis', 'coaxial Ø%.2f' % LOCAL['az_coax'], LOCAL['az_coax'], None, 0.02, 0.03,
     'Radial span of the pair is 80 mm; a misaligned pair preloads the bearings and shortens life. Route A: both seats bored from the underside in one setup. '
     'Route B: the pillar lies in two bolted slabs, so the stack is doweled and line-bored after bolting (open decision, LSR2_ROUTE_B_CNC).',
     'expanding mandrel + dial indicator, or CMM', 'P'),
    ('T04', 'AZ 51206 housing washer recess', 'body', 'B', 'Ø53', 'H11 (+0.19/0), floor flatness and squareness 0.03', LOCAL['thrust_h11'], 3.2, 0.05, 0.03,
     'Housing washer of the thrust bearing is radially free (maker practice: it must not be guided by the housing); the floor squareness to AZ keeps the load even on the balls.',
     'bore gauge, indicator on the floor while turning', 'P'),
    ('T05', 'EL 6004 seats (2)', 'body', 'C', 'Ø42', 'J7 (+0.014/-0.011), cylindricity %.3f' % T['seat_6004'], T['seat_6004'], 1.6, 0.012, 0.010,
     'Outer rings of the 6004 pair (0/-0.011): transition fit J7 as the 6206 seats. Fitted from inside the box, circlip inside.',
     'bore gauge', 'P'),
    ('T06', 'EL seat coaxiality (2 x Ø42)', 'body', 'C', 'axis', 'coaxial Ø%.2f (el_coax)' % T['el_coax'], T['el_coax'], None, 0.02, 0.03,
     'Span 152 mm between the two seats; the through-shaft runs in both. Route A: boring bar through both walls in one setup. Route B: horizontal bores need a 4th axis, angle plate '
     'or outsourced line boring (open decision): capability 0.03 is the assumed worst case.',
     'mandrel through both seats + dial indicator, or CMM', 'P'),
    ('T07', 'AZ axis perpendicular to EL axis', 'body', 'B / C', 'axis', 'perpendicular Ø%.2f over 152 mm (az_el_perp)' % T['az_el_perp'], T['az_el_perp'], None, 0.03, 0.04,
     'Sets the non-perpendicularity term of the pointing model: 0.05 mm over 152 mm is 0.019 deg, well under the 0.1 deg target before calibration (CALIBRATION).',
     'two mandrels + height gauge, or CMM', 'P'),
    ('T08', 'EL axis height above datum A', 'body', 'A', '268', '+-%.2f (datum_dist)' % (T['datum_dist'] / 2), T['datum_dist'], None, 0.04, 0.04,
     'Fixes the arm length, the sweep clearance at EL -30..150 and the balance geometry; 0.1 mm zone is far below the 3 mm sweep clearance margin.',
     'height gauge on mandrel, or CMM', 'P'),
    ('T09', 'Lid face and body rim flatness', 'lid, body', 'rim', 'plane', 'flatness %.2f (flat_lid)' % T['flat_lid'], T['flat_lid'], 3.2, 0.05, 0.03,
     'Gasket groove plus 10 M5 screws; a cord seal tolerates 0.1 mm if the compression is 20 percent (0.5 mm of a Ø2.5 cord).',
     'surface plate + feeler gauge', 'P'),
    ('T10', 'Gasket groove depth', 'lid', 'lid face', '2.0', '+0.10/0', LOCAL['groove_d'], 1.6, 0.05, 0.03,
     'Cord seal Ø2.5: depth 2.0 gives 20 percent compression (maker range about 15-25 percent). VERIFY with the cord maker gland table.',
     'depth micrometer', 'P'),
    ('T11', 'Gasket groove width', 'lid', 'lid face', '3.0', '+0.20/0', LOCAL['groove_w'], 1.6, 0.10, 0.05,
     'Groove fill (cord area / groove area) is 82 percent at the nominal width: room to spread without overfilling. Corners R >= 1.5.',
     'pin gauge or optical comparator', 'P'),
    ('T12', 'Shaft seal bores (EL, 2)', 'body', 'C', 'Ø32', 'H8 (+0.039/0)', LOCAL['seal_h8'], 1.6, 0.02, 0.02,
     'Rotary lip seal OD seat, usual maker practice H8, Ra 1.6-3.2; no scratches along the axis (leak path).',
     'bore gauge, visual', 'P'),
    ('T13', 'EL gearbox pad position and flatness', 'body', 'C', 'pad on +y wall', 'hub axis to EL axis Ø%.2f, pad flatness 0.05' % LOCAL['gb_pos'], LOCAL['gb_pos'], 3.2, 0.03, 0.03,
     'The gearbox only transmits torque: its hub must sit on the EL axis within the Ø14 H7/g6 clearance plus key slack, or it takes a radial load from the shaft.',
     'pin through the hub bore + indicator, flatness on a plate', 'P'),
    ('T14', 'AZ gearbox shelf', 'body', 'B', 'plate z 140-148', 'flatness 0.05, squareness to AZ 0.05, 4 x M6 position Ø%.2f' % LOCAL['thread_pos'], 0.05, 3.2, 0.03, 0.03,
     'Gearbox hub coaxial with the AZ shaft stub (same reason as T13); shelf is machined from below in one setup with the bearing seats.',
     'indicator on the shelf with the AZ mandrel, thread gauge', 'P'),
    ('T15', 'Yoke arm bore (2)', 'yoke_arm', 'C', 'Ø20', 'H7 (+0.021/0) (bore_h7)', T['bore_h7'], 1.6, 0.012, 0.010,
     'Mates the Ø20 h6 EL shaft (clearance 0..34 um) locked by a 6 x 6 key and the clamp; the arms are loose parts, so each is bored in one setup and the key slot is cut after.',
     'plug gauge', 'P'),
    ('T16', 'Yoke arm key way', 'yoke_arm', 'bore', '6', 'Js9 (+-0.015)', LOCAL['keyway'], 3.2, 0.02, 0.02,
     'Parallel key DIN 6885 in the shaft N9 slot: torque only, 6 N.m peak (SIZING).', 'slot gauge or pin', 'P'),
    ('T17', 'Saddle seat parallel to EL axis', 'yoke_arm, saddle', 'C', 'plane', 'parallel %.2f over 140 mm' % LOCAL['saddle_par'], LOCAL['saddle_par'], 3.2, 0.05, 0.04,
     'Boom skew of 0.1 mm over 140 mm is 0.04 deg: a collimation term that the pointing model removes (CALIBRATION); no need for a tighter, dearer tolerance.',
     'surface plate on the arms mounted on a mandrel', 'P'),
    ('T18', 'Saddle plate and boom clamp seats', 'saddle, boom_clamp', '-', 'planes', 'flatness %.2f, seat width 40 +0.2/0' % T['flat_lid'], T['flat_lid'], 3.2, 0.05, 0.03,
     'Boom tube 40 x 40 x 3 extrusion tolerance (MEASURE the real tube): the clamp preload 3000 N per leg closes any gap; crush limit checked in SIZING.',
     'feeler + caliper', 'P'),
    ('T19', 'Mast bore of the bracket', 'mast_bracket', 'B', 'Ø60.5', '+0.30/0, roundness 0.2, slit 4 mm', LOCAL['mast_bore'], 6.3, 0.10, 0.05,
     'Design mast Ø60.3 x 3.6; the slit and two M8 pinch bolts close the bore on it (slip torque 113 N.m, SIZING). Tube tolerance of the real mast decides the slit width (MEASURE).',
     'bore gauge or go/no-go ring', 'P'),
    ('T20', 'AZ shaft pocket of the bracket', 'mast_bracket', 'B', 'Ø31', '+0.10/0, squareness to the top face 0.10', LOCAL['pocket'], 3.2, 0.03, 0.02,
     'Accepts the Ø30 shaft pinned by a Ø6 cross pin; the hole is reamed through both parts at assembly (drill together), so its position needs no tolerance.',
     'plug gauge', 'P'),
    ('T21', 'AZ shaft bearing seats Ø30', 'az_shaft', 'B', 'Ø30', 'g6 (-0.007/-0.020); thrust washer seat j6 (+0.008/-0.005)', LOCAL['shaft_g6'], 0.8, 0.005, 0.005,
     'Stationary inner ring (the shaft is fixed to the mast): loose-transition fit g6 for the 6206, j6 for the 51206 shaft washer (maker practice for thrust bearings).',
     'micrometer', 'P'),
    ('T22', 'AZ shaft Ø30 to Ø14 stub coaxiality', 'az_shaft', 'B', 'axis', 'coaxial Ø%.2f' % LOCAL['stub_coax'], LOCAL['stub_coax'], None, 0.01, 0.01,
     'Ø14 g6 stub in the gearbox hub H7 (clearance 6..35 um): turned in the same setup as the bearing seats.', 'V-blocks + indicator', 'P'),
    ('T23', 'EL shaft bearing seats Ø20', 'el_shaft', 'C', 'Ø20', 'h6 (0/-0.013)', LOCAL['shaft_g6'], 0.8, 0.005, 0.005,
     'Inner rings of the 6004 pair (0/-0.010): the load direction is fixed relative to the rotating shaft, so a light transition-to-clearance fit is acceptable (VERIFY with the maker).',
     'micrometer', 'P'),
    ('T24', 'Lip-seal running surfaces', 'el_shaft, el_sleeve', 'C', 'Ø20', 'h11 (0/-0.13), Ra 0.2-0.8, no lead marks', LOCAL['seal_run'], 0.4, 0.01, 0.01,
     'Rotary seal maker practice: hardness and no spiral marks matter more than size; turned with a plunge cut or ground. Stainless is acceptable.',
     'profilometer, visual', 'P'),
    ('T25', 'Lid screw holes', 'lid, body', 'rim', 'M5 / Ø5.5', 'position Ø%.2f, thread 6H' % LOCAL['thread_pos'], LOCAL['thread_pos'], 3.2, 0.10, 0.05,
     'Clearance holes Ø5.5 in the lid absorb the position error; thread inserts or helicoil in the cast aluminium.', 'thread gauge, pin gauge', 'P'),
]
CAST_ROWS = ROWS

# Mk4 replica (default design). Nominals are on the SARCNET drawings in third_party/sarctrac-mk4/FreeCAD/Drawings (Plate, Rotator Assembly, Thrust Bearing Assembly, Cover *, Enclosure *);
# the tolerances are our PARAMETRIC choices (laser-cut sheet and 3-axis CNC plate): VERIFY with the real gearbox and bearing before cutting.
# Same 13 fields as ROWS; capabilities: laser = route A column, CNC plate = route B column.
MK4_ROWS = [
    ('M01', 'Plate datum face (gearbox side)', 'Plate 10 mm', '-', 'plane', 'flatness 0.10', 0.10, 3.2, 0.05, 0.03,
     'Both NMRV30 gearbox flanges and the saddle bolt on it: a flat face keeps the AZ and EL gearboxes parallel without shims.', 'surface plate + feeler', 'P'),
    ('M02', 'AZ gearbox spigot bore', 'Plate 10 mm', 'M01', 'per Plate.pdf', 'H8 (+0.039/0), position Ø0.10 to the AZ axis', 0.10, 1.6, 0.05, 0.03,
     'Pilot of the NMRV30-G50-D11 output flange: the gearbox is located by the spigot and bolted with 4 x M8; MEASURE the real gearbox spigot diameter first.',
     'bore gauge, CMM or pin + indicator', 'P'),
    ('M03', 'EL gearbox spigot bore', 'Plate 10 mm', 'M01', 'per Plate.pdf', 'H8 (+0.039/0), position Ø0.10 to the EL axis', 0.10, 1.6, 0.05, 0.03,
     'Same as M02 for the EL gearbox; the AZ-EL position sets the sweep clearance of the lift arms.', 'bore gauge, CMM', 'P'),
    ('M04', 'Thrust-bearing seat (51206 housing washer)', 'Plate 10 mm', 'M01', 'per Thrust Bearing Assembly.pdf', 'H11 (+0.19/0), floor flatness 0.05', 0.19, 3.2, 0.05, 0.03,
     'The housing washer is radially free (maker practice); the seat floor squareness keeps the load even on the balls.', 'bore gauge, indicator on the floor', 'P'),
    ('M05', 'Hub bore on the stainless azimuth hub', 'Hub (turned)', '-', 'per drawing', 'H7 (+0.021/0) bore, g6 shaft seat', 0.021, 1.6, 0.01, 0.01,
     'The hub rides on the gearbox output (11 mm key bore of the NMRV30 hollow shaft) and carries the shaft washer of the 51206 (j6 seat).', 'plug gauge, micrometer', 'P'),
    ('M06', 'Saddle plates (3) and platform', 'Saddle Plate Left/Right/Front, Platform', 'M01', 'planes', 'hole position Ø0.20, flatness 0.10', 0.20, 3.2, 0.10, 0.05,
     'Assembled with M8 bolts and the 2 x 40 mm U-bolts; the position error is absorbed by clearance holes; parallelism to the EL axis is removed by the pointing model.', 'caliper, feeler', 'P'),
    ('M07', 'Laser-cut 2 mm outline (cover and enclosure panels)', 'Cover Top/Bottom/Front/Back/Left/Right, Enclosure Front/Bottom/Top', '-', 'per drawings', '+-0.10', 0.20, 3.2, 0.10, 0.10,
     'Laser-cut 2 mm 5754/5083 sheet: +-0.1 mm is a normal cutting tolerance; panels meet at the 16 mm corner blocks with neoprene gasket, so it is not critical.', 'caliper, flat template', 'P'),
    ('M08', 'Laser-cut holes and slots (2 mm)', 'Cover and enclosure panels', '-', 'per drawings', '+-0.10, hole position +-0.15', 0.30, 3.2, 0.10, 0.10,
     'M5 screws into the 16 mm corner blocks, M16/M12 glands and the housing cut-outs: clearance absorbs the position error.', 'pin gauge', 'P'),
    ('M09', 'Corner blocks (16 mm)', 'Cover Corner Block (8)', '-', 'per drawing', 'size +-0.10, tapped holes position 0.20', 0.20, 3.2, 0.10, 0.05,
     'The cover panels bolt on them: the tapped holes must line up with the laser-cut holes.', 'thread gauge, caliper', 'P'),
    ('M10', 'Lift arms (25 x 25 x 2 SHS) and bracket / angle', 'Lift Arm, Bracket, Angle', '-', 'per drawings', 'length +-0.5, hole position 0.30', 0.30, 6.3, 0.20, 0.10,
     'Extrusion and saw-cut tolerances; the counterweight leaf and the boom bolts use clearance holes; balance is set at assembly.', 'caliper, tape', 'P'),
]
MK4_FINISHES = [('Machined fits and seats', 'Ra 0.8-1.6, no scratches along the axis, deburr and chamfer 0.5 x 45 deg'),
                ('Laser-cut edges', 'deburr; no heat discolouration on seating faces'),
                ('Aluminium parts', 'chromate conversion (conductive) or anodise; mask fits and threads'),
                ('Stainless hubs', 'passivate; Tef-Gel on every joint with aluminium (galvanic corrosion at the coast)'),
                ('Fasteners', 'A2/A4 with Tef-Gel; torques in LSR2_ASSEMBLY')]
MK4_NOTE = ('Mk4 default (SARCNET drawings in `third_party/sarctrac-mk4/FreeCAD/Drawings/`): laser-cut 2 mm +-0.1 mm, CNC plate fits for the gearbox spigots and the bearing seats. '
            'The datums are the plate face (M01) and the AZ / EL axes of the spigots. The cast-variant table (T01-T25: body, lid, shafts) is in the Optional cast/CNC variant section.')
FINISHES = [('Machined fits and seats', 'Ra 0.8-1.6, no scratches along the axis, deburr and chamfer 0.5 x 45 deg'),
            ('Gasket groove and lid face', 'Ra 1.6 flanks, 3.2 face'),
            ('Cast surfaces', 'as cast Ra 12.5, shot-blast; no machining except the marked pads (stock %.1f mm per face, params.CAST)' % P.CAST['machining']),
            ('Aluminium parts', 'chromate conversion (conductive, default) or anodise; mask fits, threads and the electrical-continuity lands of lid and body'),
            ('Stainless shafts', 'passivate; Tef-Gel on every joint with aluminium (galvanic corrosion at the coast)'),
            ('Fasteners', 'A4-70 with Tef-Gel; torques in LSR2_ASSEMBLY')]
CASTING = ('Sand casting A356-T6: general tolerance class ISO 8062-3 CT 9-10 (DATASHEET class; read the value for each nominal size in the standard); '
           'machining stock %.1f mm per face (params.CAST, PARAMETRIC) absorbs it on the marked pads; everything else stays as cast. Printed pattern shrink factor %.3f.' %
           (P.CAST['machining'], P.CAST['shrink']))


def fit_rows():
    out = []
    for name, key, br, housing in PAIRS:
        a, b = ISO[key], BEARING[br]
        lo_h, hi_h = (a[1], a[0]) if housing else (b[1], b[0])   # hole limits
        lo_s, hi_s = (b[1], b[0]) if housing else (a[1], a[0])   # shaft limits
        out.append((name, max(hi_h - lo_s, 0), hi_s - lo_h if hi_s > lo_h else 0, hi_h - lo_s, lo_h - hi_s))
    return out


def self_test():
    for rows in (ROWS, MK4_ROWS):
        ids = [r[0] for r in rows]
        assert len(ids) == len(set(ids)) and all(len(r) == 13 for r in rows)
        for r in rows:
            assert r[6] >= r[8] and r[6] >= r[9], (r[0], 'tolerance zone tighter than the process capability')
    assert not {r[0] for r in ROWS} & {r[0] for r in MK4_ROWS}
    assert all(k in T for k in ('el_coax', 'az_el_perp', 'flat_lid', 'flat_base', 'datum_dist', 'bore_h7', 'seat_6206', 'seat_6004'))
    assert all(v[0] > v[1] for v in ISO.values()) and all(v[0] > v[1] for v in BEARING.values())
    assert ISO[('62', 'J7')][0] - ISO[('62', 'J7')][1] == 30 and ISO[('20', 'H7')][0] == 21 and ISO[('20', 'h6')][1] == -13
    for name, max_clear, _, mc, mi in fit_rows():
        assert mc > mi, name
    print('tolerances self-test OK (%d Mk4 rows, %d cast-variant rows)' % (len(MK4_ROWS), len(ROWS)))


def _table(rows):
    o = ['| ID | Feature | Part | Datum | Nominal (mm) | Tolerance / fit | Ra (µm) | Justification (mating part and process) | Tag |', '|---|---|---|---|---|---|---|---|---|']
    return o + ['| %s | %s | %s | %s | %s | %s | %s | %s | %s |' % (r[0], r[1], r[2], r[3], r[4], r[5], '' if r[7] is None else '%g' % r[7], r[10], r[12]) for r in rows]


def _capability(rows, a, b):
    o = ['| ID | Zone | %s | %s | Margin (zone / worst capability) |' % (a, b), '|---|---|---|---|---|']
    return o + ['| %s | %g | %g | %g | %.1f |' % (r[0], r[6], r[8], r[9], r[6] / max(r[8], r[9])) for r in rows]


def tolerances_md():
    o = ['# LSR-2 tolerances, fits and finishes (generated by `cad/lsr2/tolerances.py`)\n',
         'Authors: Anatol EA5KAO, Diego EA5JEF, Pedro Roca Molina (BricoHams). REV %s. Source of every number: `cad/lsr2/tolerances.py` and `cad/lsr2/params.py` (`TOL`). '
         'Tags: **D** DATASHEET (ISO 286-2 limits, ISO 492 normal bearing class), **P** PARAMETRIC (our choice, editable in the table), **M** MEASURE (shop capability: ask the shop). '
         'Fits follow the bearing-maker practice described in the script docstring: **VERIFY with the maker table for the real bearing and load before the first cut**. '
         'Related: [inspection sheet](LSR2_INSPECTION.md), [sizing](LSR2_SIZING.md), [Mk4 design](LSR2_MK4.md), [risks](LSR2_RISKS.md).\n' % P.REV,
         '## SARCTrac Mk4 replica (default design)\n', MK4_NOTE + '\n']
    o += _table(MK4_ROWS)
    o += ['\n### Process capability check (zone against the assumed shop capability, mm)\n',
          'Capabilities are **MEASURE** placeholders (typical laser and 3-axis CNC values, to be replaced with the quotes). The self-test fails if a zone is tighter than either capability.\n']
    o += _capability(MK4_ROWS, 'Laser / sheet', 'CNC plate')
    o += ['\n### Finishes\n', '| Surface | Finish |', '|---|---|'] + ['| %s | %s |' % f for f in MK4_FINISHES]
    o += ['\n## Optional cast/CNC variant (`LSR2_DESIGN=cast`)\n',
          'The rest of this document applies only to the optional cast/CNC variant ([route A](LSR2_ROUTE_A_CASTING.md), [route B](LSR2_ROUTE_B_CNC.md)).\n',
          '### Datums\n', '| Datum | Definition |', '|---|---|'] + ['| %s | %s |' % d for d in DATUMS]
    o += ['\n### Tolerance table\n']
    o += _table(ROWS)
    o += ['\n### Fits calculated from ISO 286-2 and ISO 492 limits (µm)\n', 'Hole = housing or bearing bore, shaft = shaft or bearing outer ring. Positive = clearance, negative = interference.\n',
          '| Pair | Max clearance | Max interference |', '|---|---|---|']
    o += ['| %s | %d | %d |' % (n, mc, -mi) if mi < 0 else '| %s | %d | 0 (clearance only, min %d) |' % (n, mc, mi) for n, _, _, mc, mi in fit_rows()]
    o += ['\n### Process capability check (zone against the assumed shop capability, mm)\n',
          'Capabilities are **MEASURE** placeholders (typical shop values, to be replaced with the foundry and CNC shop numbers). The self-test fails if a zone is tighter than either capability.\n']
    o += _capability(ROWS, 'Route A (cast + machining)', 'Route B (CNC)')
    o += ['\n### Casting and finishes\n', CASTING + '\n', '| Surface | Finish |', '|---|---|'] + ['| %s | %s |' % f for f in FINISHES]
    o += ['\n## Open decisions\n', '- Mk4: real gearbox spigot, bearing seat and hub dimensions (MEASURE the bought parts against the SARCNET drawings); laser and CNC shop capabilities from the quotes.',
          '- Cast variant: horizontal EL bores on route B (4th axis, angle plate or outsourced line boring): decides T06 and T13 capability.',
          '- Cast variant: doweling and line-boring the bolted slab stack of the body (T03).',
          '- Real shop capabilities and the foundry CT class: replace the MEASURE capabilities and re-run the self-test.',
          '- Fit selection (J7 / g6 / h6 / j6) to be confirmed with the maker table for the final load case; a tighter housing fit raises the preload risk in aluminium.',
          '- Real mast and boom tube tolerances (MEASURE the first sample).']
    return '\n'.join(o) + '\n'


def inspection_md():
    hdr = ['| ID | Feature | Part | Datum | Nominal (mm) | Tolerance | Method / gauge | Result | OK |', '|---|---|---|---|---|---|---|---|---|']
    o = ['# LSR-2 inspection sheet (generated by `cad/lsr2/tolerances.py`)\n',
         'Fill the **Result** column on the first article and on every batch; the reason for each tolerance is in [LSR2_TOLERANCES](LSR2_TOLERANCES.md). Rev %s. '
         'Serial: ______  Date: ______  Inspector: ______  Plate / bar lot: ______\n' % P.REV,
         '## SARCTrac Mk4 replica (default design)\n',
         'One sheet per plate, saddle set, hub set, cover set and lift-arm pair; nominals from the SARCNET drawings in `third_party/sarctrac-mk4/FreeCAD/Drawings/`.\n'] + hdr
    o += ['| %s | %s | %s | %s | %s | %s | %s | | |' % (r[0], r[1], r[2], r[3], r[4], r[5], r[11]) for r in MK4_ROWS]
    o += ['', 'Also record: mass of each part against `docs/BOM_LSR2.md` (made-part masses come from the build report), thread check of every tapped hole, burrs on laser-cut edges, and the free rotation torque '
          'of the thrust-bearing stack after fitting (hand feel, then the bench value in [LSR2_TEST_PLAN](LSR2_TEST_PLAN.md)).',
          '\n## Optional cast/CNC variant (`LSR2_DESIGN=cast`)\n',
          'One sheet per finished body, lid, mast bracket, yoke arm pair, saddle and shaft. Casting heat / bar lot: ______\n'] + hdr
    o += ['| %s | %s | %s | %s | %s | %s | %s | | |' % (r[0], r[1], r[2], r[3], r[4], r[5], r[11]) for r in ROWS]
    o += ['', 'Also record (cast variant): visual (porosity, cold shuts, cracks at seats).']
    return '\n'.join(o) + '\n'


if __name__ == '__main__':
    self_test()
    docs = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'docs')
    for name, text in (('LSR2_TOLERANCES.md', tolerances_md()), ('LSR2_INSPECTION.md', inspection_md())):
        with open(os.path.join(docs, name), 'w', encoding='utf-8', newline='\n') as fh:
            fh.write(text)
    print('wrote docs/LSR2_TOLERANCES.md and docs/LSR2_INSPECTION.md')
