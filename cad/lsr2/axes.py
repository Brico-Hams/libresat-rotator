"""LSR-2 phase 11b: axes, yoke, saddle, boom, lift arms, counterweights, mast bracket and bearings (head frame, mm).

Frame: origin = centre of the body bottom mounting face, z up = AZ axis, x forward = boresight at EL 0, y along the EL axis and the cross boom.
The EL axis is the line (x = 0, z = K['z_el']) along y. a = distance along the boresight from the EL axis, h = height above it (at EL 0).
Tags: D = DATASHEET (source named), M = MEASURE (caliper), P = PARAMETRIC (our choice, editable).
Pure-Python numbers are importable without FreeCAD; the builders use a lazy `import visual_parts` (FreeCAD).
Our own geometry. Catalogue sizes (bearings, circlips, seals) are D in the maker catalogues and VERIFY on the bought part.
"""
import math
import inputs as IN

SS_G_CM3 = 7.95      # D: 1.4404 / 316L, ISO density
STEEL_G_CM3 = 7.85   # D: carbon steel (counterweights)

Z_EL = round(IN.I['z_el'] * 1000.0)   # P, from inputs (layout_study.py proves it clears the AZ gearbox)
K = dict(
    z_el=Z_EL, y_c=30.0,                        # P EL gearbox hub centre on the +y wall (layout A)
    x_back=50.0, x_front=180.0, hw=73.0, wall=5.0, rim=314.0, lid_t=5.0,   # P body outer envelope and wall (params.CAST min_wall 5)
    zf=148.0,                                   # P AZ gearbox lower face (on the shelf plate)
    shelf=(140.0, 148.0),                       # P free-standing shelf plate z range (8 mm), 26 mm of air below for the M6 bolts
    # AZ stack (P): 51206 z -8..8 in the floor recess, 6206 pair, shoulder at z 111, Ø14 stub into the gearbox hub
    az_51206=(-8.0, 8.0), az_brg=((15.0, 31.0), (95.0, 111.0)), az_shoulder=111.0, az_top=190.0, az_bot=-50.0,
    pillar_r=40.0, pillar_top=115.0, az_bore_top=97.0,
    # EL stack (P): 6004 pair at y = +-76, Ø20 shaft on the -y side, Ø14 through the hub, sleeve Ø20/14 on the +y side
    el_brg_y=76.0, boss_r=26.0, boss_y=86.0, el_shaft_y=(-120.0, 121.0), el_step_y=-3.0, el_sleeve_y=(63.0, 120.0),
    # yoke, saddle, boom (P); arm length from layout_study.min_arm()
    arm_y=(95.0, 105.0), arm_boss_end=120.0, arm_h=119.0, saddle_h=125.0, saddle_t=8.0, saddle_a=(-10.0, 60.0), saddle_y=105.0,
    boom_w=40.0, boom_t=3.0, boom_len=1600.0, block_t=10.0, block_y=60.0, block_w=30.0,
    lift_y=650.0, lift_t=8.0, foot_t=6.0, yagi_h=0.0, cw_rod_d=10.0, cw_d=30.0, cw_x=-200.0, cw_rod_h=30.0, cw_rod_dy=30.0,
    ant_a=50.0,                                  # antenna boom centre ahead of the EL axis (= inputs ant_cg_a)
)
K['boom_axis_h'] = K['saddle_h'] + K['saddle_t'] + K['boom_w'] / 2          # 153 (the inputs table rounds up to boom_h 155 incl. gap)
K['boom_a'] = 25.0                                                          # boom centre a (saddle centre)

# --- bearings (D: maker catalogues; VERIFY) ---------------------------------------------------------------------------------------
BRG = {'6206': dict(d=30.0, D=62.0, B=16.0), '6004': dict(d=20.0, D=42.0, B=12.0), '51206': dict(d=30.0, D=52.0, B=16.0)}

# --- shafts: segments (lo, hi, d) along the shaft axis in mm; the shaft data feeds calc/lsr2_materials.py ----------------------------
AZ_SHAFT = [(K['az_bot'], K['az_shoulder'], 30.0), (K['az_shoulder'], K['az_top'], 14.0)]
AZ_BORE = (K['az_bot'], K['az_bore_top'], 16.0)       # lightening blind bore from the bottom end (P)
EL_SHAFT = [(K['el_shaft_y'][0], K['el_step_y'], 20.0), (K['el_step_y'], K['el_shaft_y'][1], 14.0)]
EL_SLEEVE = [(K['el_sleeve_y'][0], K['el_sleeve_y'][1], 20.0)]
SHAFTS = {'az_shaft': AZ_SHAFT, 'el_shaft': EL_SHAFT, 'el_sleeve': EL_SLEEVE}
SHAFT_BORES = {'az_shaft': [AZ_BORE], 'el_shaft': [], 'el_sleeve': [(K['el_sleeve_y'][0], K['el_sleeve_y'][1], 14.0)]}


def shaft_volume_cm3(segs, bores=()):
    v = sum(math.pi * d * d / 4 * (hi - lo) for lo, hi, d in segs) - sum(math.pi * d * d / 4 * (hi - lo) for lo, hi, d in bores)
    return v / 1000.0


def shaft_length(segs):
    return max(h for _, h, _ in segs) - min(lo for lo, _, _ in segs)


def shaft_stock(segs):
    """Round bar: finished length + 10 mm, largest step + 3 mm."""
    return max(d for _, _, d in segs) + 3.0, shaft_length(segs) + 10.0


def cw_length(mass_kg):
    """Steel counterweight cylinder Ø30 for a counterweight of `mass_kg` that includes the Ø10 rod (the rod is added separately)."""
    rod = math.pi * (K['cw_rod_d'] / 2) ** 2 * 345.0 * STEEL_G_CM3 / 1e6
    return max(20.0, (mass_kg - rod) * 1e6 / (STEEL_G_CM3 * math.pi * (K['cw_d'] / 2) ** 2))


def rot_point(a, h, e_deg):
    """Point (a, h) of the moving group at elevation e (same convention as calc/lsr2_sizing.P): returns (x, z) in the body frame."""
    c, s = math.cos(math.radians(e_deg)), math.sin(math.radians(e_deg))
    return (a * c - h * s, K['z_el'] + a * s + h * c)


def self_test():
    assert K['z_el'] == 268 and shaft_stock(AZ_SHAFT) == (33.0, 250.0)
    assert abs(shaft_volume_cm3(EL_SHAFT) * SS_G_CM3 - 444.0) < 5.0
    assert abs(rot_point(1.0, 0.0, 90.0)[1] - (K['z_el'] + 1.0)) < 1e-9
    assert K['arm_y'][0] > K['boss_y']                      # arms clear of the bearing bosses
    assert K['az_brg'][0][1] <= K['az_brg'][1][0] - 60.0     # radial span ~80 mm centre to centre
    assert 0 < cw_length(1.02) < 300


# ---- builders (FreeCAD) ---------------------------------------------------------------------------------------------------------
def _vp():
    import visual_parts as VP
    return VP


def _prism_xz(pts, y0, y1, z_off):
    """Polygon given as (x, h) pairs in the plane y = y0, extruded to y1; h is measured from z_off."""
    import Part
    from FreeCAD import Vector as V
    p = [V(x, y0, z_off + h) for x, h in pts]
    return Part.Face(Part.makePolygon(p + [p[0]])).extrude(V(0, y1 - y0, 0))


def az_shaft():
    VP = _vp()
    s = VP.fuse([VP.cyl(15.0, K['az_shoulder'] - K['az_bot'], (0, 0, K['az_bot']), (0, 0, 1)),
                 VP.cyl(7.0, K['az_top'] - K['az_shoulder'], (0, 0, K['az_shoulder']), (0, 0, 1))])
    cuts = [VP.cyl(8.0, K['az_bore_top'] - K['az_bot'], (0, 0, K['az_bot']), (0, 0, 1)),
            VP.cyl(3.0, 40.0, (0, -20, -36.0), (0, 1, 0)),                       # Ø6 cross pin through the mast bracket
            VP.box(-2.5, 2.5, 4.5, 8.0, K['zf'] + 2.0, K['zf'] + 42.0)]          # keyway of the 5x5x40 key in the gearbox hub
    return VP.cut(s, cuts)


def el_shaft():
    VP = _vp()
    ze, (y0, y1), ys = K['z_el'], K['el_shaft_y'], K['el_step_y']
    s = VP.fuse([VP.cyl(10.0, ys - y0, (0, y0, ze), (0, 1, 0)), VP.cyl(7.0, y1 - ys, (0, ys, ze), (0, 1, 0))])
    keys = [VP.box(-2.5, 2.5, K['y_c'] - 26.0, K['y_c'] + 14.0, ze + 4.5, ze + 8.0),            # 5x5x40 hub key way
            VP.box(-3.0, 3.0, y0 + 2.0, y0 + 27.0, ze + 7.0, ze + 10.5)]                         # 6x6x25 arm key way
    return VP.cut(s, keys)


def el_sleeve():
    VP = _vp()
    y0, y1 = K['el_sleeve_y']
    return VP.cut(VP.cyl(10.0, y1 - y0, (0, y0, K['z_el']), (0, 1, 0)), [VP.cyl(7.0, y1 - y0 + 2, (0, y0 - 1, K['z_el']), (0, 1, 0))])


def bearing(name, centre, axis):
    """Ring envelope of a bearing (bore d, OD D, width B) centred at `centre` along `axis`."""
    VP = _vp()
    b = BRG[name]
    c = [centre[i] - axis[i] * b['B'] / 2 for i in range(3)]
    return VP.cut(VP.cyl(b['D'] / 2, b['B'], c, axis), [VP.cyl(b['d'] / 2, b['B'] + 2, [c[i] - axis[i] for i in range(3)], axis)])


def az_bearings():
    out = {'brg_az_lower': bearing('6206', (0, 0, sum(K['az_brg'][0]) / 2), (0, 0, 1)),
           'brg_az_upper': bearing('6206', (0, 0, sum(K['az_brg'][1]) / 2), (0, 0, 1)),
           'brg_az_thrust': bearing('51206', (0, 0, sum(K['az_51206']) / 2), (0, 0, 1))}
    return out


def el_bearings():
    return {'brg_el_pos': bearing('6004', (0, K['el_brg_y'], K['z_el']), (0, 1, 0)),
            'brg_el_neg': bearing('6004', (0, -K['el_brg_y'], K['z_el']), (0, 1, 0))}


def mast_bracket():
    """Split-clamp mast bracket: tube OD76 / bore Ø60.5 (mast bore z -160..-60), slit + 2 M8 pinch lugs, core with the Ø30 shaft pocket,
    top disc and the labyrinth cup ring (R47..55) that overlaps the body skirt (R40..45). One finished solid (cast or CNC)."""
    VP = _vp()
    tube = VP.cyl(38.0, 100.0, (0, 0, -160), (0, 0, 1))
    core = VP.cyl(38.0, 38.0, (0, 0, -60), (0, 0, 1))
    disc = VP.cyl(55.0, 6.0, (0, 0, -22), (0, 0, 1))
    cup = VP.cut(VP.cyl(55.0, 14.0, (0, 0, -16), (0, 0, 1)), [VP.cyl(47.0, 16.0, (0, 0, -17), (0, 0, 1))])
    lugs = [VP.box(30, 58, -16, 16, z - 12, z + 12) for z in (-80.0, -140.0)]
    s = VP.fuse([tube, core, disc, cup] + lugs)
    cuts = [VP.cyl(30.25, 101.0, (0, 0, -161), (0, 0, 1)),                       # mast bore
            VP.cyl(15.5, 40.0, (0, 0, -50), (0, 0, 1)),                          # Ø31 shaft pocket (shaft Ø30 + clearance), web z -60..-50 stops the mast
            VP.box(30, 70, -2, 2, -161, -59),                                    # slit
            VP.cyl(3.0, 80.0, (0, -40, -36.0), (0, 1, 0))]                       # Ø6 cross pin
    cuts += [VP.cyl(4.2, 40.0, (44, -20, z), (0, 1, 0)) for z in (-80.0, -140.0)]     # M8 pinch bolts across the slit
    return VP.cut(s, cuts)


def yoke_arm(side):
    """One U-yoke arm (side = +1 / -1 along y): plate, rounded foot around the axis, outboard keyed boss and the top flange to the saddle."""
    VP = _vp()
    ze = K['z_el']
    y0, y1 = K['arm_y']
    if side > 0:
        ya, yb, yf0, yf1, yb1 = y0, y1, 88.0, 112.0, K['arm_boss_end']
    else:
        ya, yb, yf0, yf1, yb1 = -y1, -y0, -112.0, -88.0, -K['arm_boss_end']
    plate = _prism_xz([(-20, 0), (20, 0), (50, K['arm_h']), (0, K['arm_h'])], ya, yb, ze)
    foot = VP.cyl(20.0, yb - ya, (0, ya, ze), (0, 1, 0))
    flange = VP.box(0.0, 50.0, yf0, yf1, ze + K['arm_h'], ze + K['saddle_h'])
    if side > 0:
        boss = VP.cyl(20.0, yb1 - ya, (0, ya, ze), (0, 1, 0))
    else:
        boss = VP.cyl(20.0, yb - yb1, (0, yb1, ze), (0, 1, 0))
    s = VP.fuse([plate, foot, flange, boss])
    ylo = min(ya, yb1)
    cuts = [VP.cyl(10.0, abs(yb1 - (ya if side > 0 else yb)) + 2, (0, ylo - 1, ze), (0, 1, 0)),     # Ø20 bore
            VP.box(-3.0, 3.0, ylo - 1, ylo + 27.0, ze + 9.0, ze + 10.5)]                           # 6x6x25 key way
    cuts += [VP.cyl(3.2, 12.0, (x, yc, ze + K['arm_h'] - 3.0), (0, 0, 1)) for x in (10.0, 40.0) for yc in (side * 93.0, side * 107.0)]
    return VP.cut(s, cuts)


def saddle():
    VP = _vp()
    ze = K['z_el']
    a0, a1 = K['saddle_a']
    z0 = ze + K['saddle_h']
    s = VP.box(a0, a1, -K['saddle_y'], K['saddle_y'], z0, z0 + K['saddle_t'])
    cuts = [VP.box(K['boom_a'] - 14.0, K['boom_a'] + 14.0, -38.0, 38.0, z0 - 1, z0 + K['saddle_t'] + 1)]
    cuts += [VP.cyl(3.2, 12.0, (x, sg * yc, z0 - 2.0), (0, 0, 1)) for x in (10.0, 40.0) for sg in (-1, 1) for yc in (93.0, 107.0)]
    cuts += [VP.cyl(3.2, 12.0, (x, sg * K['block_y'] + dy, z0 - 2.0), (0, 0, 1)) for x in (0.0, 50.0) for sg in (-1, 1) for dy in (-9.0, 9.0)]
    return VP.cut(s, cuts)


def boom():
    VP = _vp()
    w, t, ze = K['boom_w'], K['boom_t'], K['z_el']
    z0 = ze + K['saddle_h'] + K['saddle_t']
    a0 = K['boom_a'] - w / 2
    o = VP.box(a0, a0 + w, -K['boom_len'] / 2, K['boom_len'] / 2, z0, z0 + w)
    return VP.cut(o, [VP.box(a0 + t, a0 + w - t, -K['boom_len'] / 2 - 1, K['boom_len'] / 2 + 1, z0 + t, z0 + w - t)])


def boom_clamp(side):
    """Interchangeable top clamp block (the 40 x 40 square seat); a round-boom variant swaps it for a V-groove block."""
    VP = _vp()
    ze = K['z_el']
    a0, a1 = K['saddle_a']
    z0 = ze + K['saddle_h'] + K['saddle_t'] + K['boom_w']
    yc = side * K['block_y']
    s = VP.box(a0, a1, yc - K['block_w'] / 2, yc + K['block_w'] / 2, z0, z0 + K['block_t'])
    return VP.cut(s, [VP.cyl(3.2, K['block_t'] + 2, (x, yc + dy, z0 - 1), (0, 0, 1)) for x in (0.0, 50.0) for dy in (-9.0, 9.0)])


def clamp_bolts():
    """8 x M6x35 hex bolts through the two clamp blocks and the saddle (nuts under the saddle)."""
    VP = _vp()
    ze = K['z_el']
    z0 = ze + K['saddle_h'] + K['saddle_t'] + K['boom_w'] + K['block_t']
    out = []
    for sg in (-1, 1):
        for x in (0.0, 50.0):
            for dy in (-9.0, 9.0):
                b = VP.bolt((x, sg * K['block_y'] + dy, z0), (0, 0, -1), 6.0, 38.0, 10.0, 4.0)
                out.append(b)
    return out


def lift_arm(side):
    """Flat bar against the front face of the boom, foot plate on top of the Yagi boom (U-bolts + strap not modelled as solids)."""
    VP = _vp()
    ze = K['z_el']
    yc = side * K['lift_y']
    a0 = K['boom_a'] + K['boom_w'] / 2
    z_top = ze + K['saddle_h'] + K['saddle_t'] + K['boom_w']
    z_foot = ze + K['yagi_h'] + 15.0
    bar = VP.box(a0, a0 + K['lift_t'], yc - 15.0, yc + 40.0, z_foot, z_top)
    foot = VP.box(K['ant_a'] - 25.0, K['ant_a'] + 25.0, yc - 15.0, yc + 40.0, z_foot, z_foot + K['foot_t'])
    s = VP.fuse([bar, foot])
    return VP.cut(s, [VP.cyl(3.2, 30.0, (a0 - 4.0, yc + dy, ze + K['saddle_h'] + K['saddle_t'] + 20.0), (1, 0, 0)) for dy in (0.0, 24.0)])


def counterweight(side, mass_kg):
    """Steel weight Ø30 on a Ø10 rod, slides along the rod (set screw); the rod ends against the lift-arm bar."""
    VP = _vp()
    ze = K['z_el']
    yc = side * K['lift_y'] + K['cw_rod_dy']
    zc = ze + K['cw_rod_h']
    x_end = K['boom_a'] + K['boom_w'] / 2
    rod = VP.cyl(K['cw_rod_d'] / 2, x_end - (-300.0), (-300.0, yc, zc), (1, 0, 0))
    L = cw_length(mass_kg)
    w = VP.cyl(K['cw_d'] / 2, L, (K['cw_x'] - L / 2, yc, zc), (1, 0, 0))
    return VP.fuse([rod, w])


if __name__ == '__main__':
    self_test()
    print('axes self-test OK; z_el', K['z_el'])
