"""LSR-2 phase 11b layout study: two candidate arrangements of the Mk5-schematic body, compared and chosen numerically.

Both have the AZ gearbox low, the EL gearbox high and both motors on the same side (front, +x):
  A  parallel stacked: both motors on the +y side one above the other, EL gearbox on the +y wall, both drivers on the -y inner wall.
  B  staggered: EL gearbox and motor on the -y wall, AZ motor on the +y side, one driver on each inner wall.
Pure Python (no FreeCAD). `python cad/lsr2/layout_study.py` writes docs/LSR2_LAYOUT_STUDY.md; no argument needed for the self-test (--check).
Dimensions in mm; tags D (datasheet), M (measure), P (parametric) as in inputs.py. The AABB solver uses params.NMRV030_GEO-like boxes:
NMRV030 local box x -40..49, y -40..57 (fins), z 0..56 + 3.5 mm bosses; NEMA23 57 x 57, motor from the gearbox flange x 55 to 167 (M, caliper).
"""
import math
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import inputs as IN
import axes as AX

GAP = 3.0                         # P solver clearance between envelopes
GB = dict(x=(-40.0, 49.0), y=(-40.0, 57.0), w=56.0, boss=3.5)     # M NMRV030 local box
MOTOR_HALF, MOTOR_X = 28.5, (40.0, 167.0)                        # M NEMA23 envelope (57 mm face + caps)
BODY = dict(x=(-AX.K['x_back'], AX.K['x_front']), z_lid=AX.K['rim'] + AX.K['lid_t'])
DRIVER = dict(size=(118.0, 75.5, 34.0), watt=10.0)               # M DM542 body; P 10 W dissipated each at 48 V (bench to confirm)
DT_LIMIT = 30.0                                                    # P allowed driver wall temperature rise (K)
H_NAT, RIB_GAIN = 8.0, 1.8                                         # P natural convection W/m2K and external rib gain


def az_top(zf):
    return zf + GB['w'] + GB['boss']


def min_z_el(zf):
    """Lowest EL axis height that keeps the EL gearbox box (z_el - 57 .. z_el + 40) GAP above the AZ gearbox box (same x/y footprint)."""
    return math.ceil(az_top(zf) + GAP + GB['y'][1])


def _sat_overlap(poly, rect):
    """Convex polygon [(x, z)] against an axis-aligned rect (x0, x1, z0, z1): separating-axis test."""
    x0, x1, z0, z1 = rect
    rp = [(x0, z0), (x1, z0), (x1, z1), (x0, z1)]
    axes = [(1.0, 0.0), (0.0, 1.0)]
    for i in range(len(poly)):
        dx, dz = poly[(i + 1) % len(poly)][0] - poly[i][0], poly[(i + 1) % len(poly)][1] - poly[i][1]
        n = math.hypot(dx, dz)
        axes.append((-dz / n, dx / n))
    for ax, az in axes:
        pa = [ax * p[0] + az * p[1] for p in poly]
        pb = [ax * p[0] + az * p[1] for p in rp]
        if max(pa) < min(pb) or max(pb) < min(pa):
            return False
    return True


def moving_boxes(h0):
    """Boxes (a0, a1, h0, h1) of the moving group inside the body footprint in y: saddle, boom, top clamp blocks (arms and lift arms are outside y +-86)."""
    a0, a1 = AX.K['saddle_a']
    t, w = AX.K['saddle_t'], AX.K['boom_w']
    ba = AX.K['boom_a']
    return [(a0, a1, h0, h0 + t), (ba - w / 2, ba + w / 2, h0 + t, h0 + t + w), (a0, a1, h0 + t + w, h0 + t + w + AX.K['block_t'])]


def sweep_clear(h0, x_back, z_el, e_range=(-30.0, 150.0), step=2.0):
    """True if the saddle group clears the body rectangle (inflated by GAP) for every elevation; returns (ok, worst_e)."""
    rect = (-x_back - GAP, BODY['x'][1] + GAP, -GAP, BODY['z_lid'] + GAP)
    e = e_range[0]
    while e <= e_range[1] + 1e-9:
        for a0, a1, b0, b1 in moving_boxes(h0):
            poly = []
            for a, h in ((a0, b0), (a1, b0), (a1, b1), (a0, b1)):
                x = a * math.cos(math.radians(e)) - h * math.sin(math.radians(e))
                z = z_el + a * math.sin(math.radians(e)) + h * math.cos(math.radians(e))
                poly.append((x, z))
            if _sat_overlap(poly, rect):
                return False, e
        e += step
    return True, None


def min_arm(x_back, z_el):
    """Shortest yoke arm (saddle underside height h0, 5 mm steps) with no saddle/boom/clamp collision with the body over EL -30..150."""
    for h0 in range(60, 700, 5):
        if sweep_clear(float(h0), x_back, z_el)[0]:
            return float(h0)
    return None


def _head(option):
    """Head items (name, kg, x, y, z) in m for the option, from inputs.HEAD with the option's y positions."""
    items = []
    for n, m, x, y, z, *_ in IN.HEAD:
        if option == 'B' and n.startswith('EL '):
            y = -0.032
        if option == 'B' and n.startswith('2 x DM542'):
            items += [(n + ' (+y wall)', m / 2, x, 0.051, 0.24), (n + ' (-y wall)', m / 2, x, -0.051, 0.06)]
            continue
        items.append((n, m, x, y, z))
    return items


def cg(items):
    m = sum(i[1] for i in items)
    return m, [sum(i[1] * i[k] for i in items) / m * 1000.0 for k in (2, 3, 4)]


def driver_dt(watt_per_wall):
    wall = 230e-3 * 314e-3                                # inner wall plate area 0.23 x 0.314 m (outer rib side exposed)
    return watt_per_wall / (H_NAT * wall * RIB_GAIN)


def study():
    zf = AX.K['pillar_top'] + 25.0 + (AX.K['shelf'][1] - AX.K['shelf'][0])
    z_el = min_z_el(zf)
    rear = AX.K['x_back'] + MOTOR_X[1] - 55.0 + 8.0 + 5.0          # body rear wall if the motors point rearward (P): motor 112 long + wall
    arm_front = min_arm(AX.K['x_back'], z_el)
    arm_rear = min_arm(rear, z_el)
    rows = {}
    for o in ('A', 'B'):
        mass, c = cg(_head(o))
        watt = DRIVER['watt'] * (2 if o == 'A' else 1)
        rows[o] = dict(
            z_el=z_el, mass=mass, cg=c,
            fixed=(BODY['x'][1] - BODY['x'][0], 2 * AX.K['boss_y'], BODY['z_lid'] + 22.0),
            dt=driver_dt(watt),
            motors='stacked on the +y side (y 1.5..58.5)' if o == 'A' else 'staggered: AZ +y (1.5..58.5), EL -y (-60.5..-3.5)',
            drivers='both on the -y inner wall (z 22..176), one thermal path' if o == 'A' else 'one per inner wall (EL side +y high, -y low), two paths',
            service='one wall to open for drivers; gearbox faces bolted from outside' if o == 'A' else 'two walls to open; more harness runs across the body',
            pen_service=0 if o == 'A' else 1, pen_heat=0 if driver_dt(watt) <= DT_LIMIT else 2, pen_hidden=0)
    pen = lambda r: r['pen_service'] + r['pen_heat'] + r['pen_hidden']
    score = {o: (rows[o]['z_el'], rows[o]['fixed'][0] * rows[o]['fixed'][1] * rows[o]['fixed'][2], pen(rows[o]), abs(rows[o]['cg'][1])) for o in rows}
    choice = min(score, key=lambda o: score[o])
    ant_r = math.hypot(1010.0, AX.K['lift_y'] + 470.0)
    return dict(rows=rows, score=score, choice=choice, z_el=z_el, zf=zf, arm_front=arm_front, arm_rear=arm_rear, rear_x_back=rear,
                r_fixed=math.hypot(BODY['x'][1], AX.K['boss_y']), r_boom=math.hypot(180.0, AX.K['boom_len'] / 2), r_ant=ant_r)


SEQ = [
    '1 Bolt the mast bracket on the mast, slide the AZ shaft into its pocket and pin it (cross pin Ø6).',
    '2 Fit the 51206 + shim + circlip on the shaft, lower the body (lid removed) onto it; the lower and upper 6206 and the DIN 472 circlip go in from the pillar bottom/top before the shelf plate.',
    '3 Bolt the AZ gearbox on the shelf plate from below (ball-end key, 26 mm of air), motor on its flange, key the Ø14 stub.',
    '4 Bolt the EL gearbox to the +y wall pad from outside (4 x M6 PCD65), fit the motor.',
    '5 Fit the 6004 + seals in the wall bosses, slide the EL shaft through (Ø14 end into the hub, key), then the sleeve on the +y side.',
    '6 Mount the two yoke arms on the Ø20 ends (keys), the saddle, the boom and the clamp blocks; balance on the sliding counterweights.',
    '7 Drivers on the -y wall with thermal pads, harness through the bottom glands, close the lid with its gasket.',
]


def markdown(r):
    a, b = r['rows']['A'], r['rows']['B']
    f = lambda v: '%.0f' % v
    L = ['# LSR-2 layout study (phase 11b)', '',
         'Generated by `python cad/lsr2/layout_study.py`; do not edit by hand. Dimensions in mm, frame as in `cad/lsr2/axes.py`. '
         'Every number is PARAMETRIC (our choice) unless the note says DATASHEET or MEASURE; NMRV030 and NEMA23 envelopes are MEASURE (caliper).', '',
         '## Candidates', '',
         '* **A, parallel stacked**: AZ gearbox low (face at z %s), EL gearbox high on the +y wall, both motors forward (+x) on the +y side, one above the other; both drivers on the -y inner wall.' % f(r['zf']),
         '* **B, staggered**: as A but the EL gearbox and motor are on the -y wall, so the motors sit on opposite sides; one driver per inner wall.', '',
         '## Comparison', '',
         '| Item | A parallel stacked | B staggered |', '|---|---|---|',
         '| EL axis height z_el | %s | %s |' % (f(a['z_el']), f(b['z_el'])),
         '| Fixed envelope x * y * z | %s * %s * %s | %s * %s * %s |' % (tuple(f(v) for v in a['fixed']) + tuple(f(v) for v in b['fixed'])),
         '| Swept envelope (radius about AZ: body / boom at worst EL / 145 MHz Yagi) | %s / %s / %s | same |' % (f(r['r_fixed']), f(r['r_boom']), f(r['r_ant'])),
         '| Head mass (kg, inputs.HEAD) | %.2f | %.2f |' % (a['mass'], b['mass']),
         '| Head CG x, y, z (mm) | %s | %s |' % (', '.join(f(v) for v in a['cg']), ', '.join(f(v) for v in b['cg'])),
         '| Motors | %s | %s |' % (a['motors'], b['motors']),
         '| Drivers and thermal path | %s | %s |' % (a['drivers'], b['drivers']),
         '| Driver wall temperature rise (ESTIMATE, %.0f W each, h %.0f W/m2K, rib gain %.1f) | %.0f K | %.0f K |' % (DRIVER['watt'], H_NAT, RIB_GAIN, a['dt'], b['dt']),
         '| Service and screw access | %s | %s |' % (a['service'], b['service']),
         '| Penalty points (service + heat + hidden fasteners) | %d | %d |' % (a['pen_service'] + a['pen_heat'] + a['pen_hidden'], b['pen_service'] + b['pen_heat'] + b['pen_hidden']),
         '| Assembly | same sequence below | same, plus a second harness run |', '',
         '## Choice', '',
         'Score tuple (z_el, fixed volume, penalties, |CG y|): A %s, B %s. **%s is chosen**: same z_el and envelope (the AZ gearbox top, %s mm + %s mm clearance + the 57 mm EL gearbox half-box set z_el), '
         'the driver temperature rise is inside the %s K limit for both, A has one service wall and one harness run. The honest cost is a head CG offset of %s mm in y (a few N·m on the AZ axis; '
         'bearing load negligible, see calc/lsr2_sizing.py).' % (
             tuple(round(v, 1) for v in r['score']['A']), tuple(round(v, 1) for v in r['score']['B']), r['choice'], f(AX.K['zf'] + 59.5), f(GAP), f(DT_LIMIT), f(a['cg'][1])), '',
         '## Yoke arm length (solver, EL -30..150, saddle + boom + clamp blocks against the body box + %s mm)' % f(GAP), '',
         '| Motors | Body rear wall | Shortest arm (saddle underside above the EL axis) |', '|---|---|---|',
         '| forward (chosen) | x = -%s | %s mm |' % (f(AX.K['x_back']), f(r['arm_front'])),
         '| rearward (open decision) | x = -%s | %s mm |' % (f(r['rear_x_back']), 'none below 700' if r['arm_rear'] is None else f(r['arm_rear']) + ' mm'), '',
         'The brief says "same side" without a direction. Forward keeps the body rear wall 50 mm behind the EL axis, which is what lets the saddle clear it at EL 150 with a %s mm arm; '
         'rearward would need the longer arm of the table. Open decision, see docs/ARCHITECTURE.md.' % f(r['arm_front']), '',
         '## Assembly sequence', ''] + SEQ + ['']
    return '\n'.join(L)


def self_test():
    r = study()
    assert r['z_el'] == AX.K['z_el'] == min_z_el(AX.K['zf']), r['z_el']
    assert r['arm_front'] is not None and r['arm_front'] <= AX.K['saddle_h'], r['arm_front']
    assert sweep_clear(AX.K['saddle_h'], AX.K['x_back'], r['z_el'])[0]
    assert not sweep_clear(AX.K['saddle_h'] - 30.0, AX.K['x_back'], r['z_el'])[0]
    assert r['arm_rear'] is None or r['arm_rear'] > r['arm_front']
    assert r['choice'] == 'A'
    assert abs(r['rows']['A']['mass'] - sum(m for _, m, *_ in IN.HEAD)) < 1e-9
    assert all(d['dt'] <= DT_LIMIT for d in r['rows'].values())
    return r


if __name__ == '__main__':
    res = self_test()
    if '--check' not in sys.argv:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'docs', 'LSR2_LAYOUT_STUDY.md')
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(markdown(res) + '\n')
    print('layout_study OK; choice %s, z_el %d, arm %s (rear variant %s)' % (res['choice'], res['z_el'], res['arm_front'], res['arm_rear']))
