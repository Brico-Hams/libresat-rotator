"""LSR-2 phase 3: A356 cast parts, their sand-casting patterns and the turned stainless shafts.

Pure-Python parameters (importable without FreeCAD) plus FreeCAD builders (lazy `import Part`) used by build.py.
Head frame as in plates.py: AZ axis = Z through the origin, base plate bottom at z=-8, EL axis along Y at z=EL_Z.
Our own geometry. Catalogue-derived numbers (bearing, washer, U-bolt sizes) are VERIFY on the real parts.

Casting choices (light and cheap):
  az_housing  two short bearing rings joined by 4 ribs (open window between the seats) and 6 bolt lugs instead of a
              tube and a flange disc. The two ring bores are CORED (boring 2 x 16 mm of solid would remove ~100 cm3
              of metal); the cores are drafted 3 deg and need a small core box. Outer faces: 2 deg draft in the profile.
  mast_clamp  bore cast solid and bored: a Ø25 core would save ~110 g of metal (~0.5 EUR), not worth a core box.
  el_bearing_housing  PCD65 flange on the EL gearbox output face B, two rings (2 x 6206, 62 mm apart) joined to the flange by 4 ribs at 45 deg
              (the bolt heads sit in the window between flange and first ring; tighten with a ball-end hex key from the side).
              Rings, seats and bores are machined from solid: coring two Ø62 bores would save ~6 EUR of metal per part
              but needs a core box, not worth it for one unit.
  boom_socket A356 casting: keyed Ø30 hub (pinch slit + M6) on the EL shaft end, then a 40.5 x 40.5 x 80 deep square socket for the
              40x40x3 cross-boom tube, locked by 2 x M8 through-bolts. One part replaces saddle_hub + saddle_plate + 2 clamp plates
              (about 0.4 kg and 4 parts less than a CNC end plate with 2 angle brackets, which also needs a hub). The pocket is
              formed by one prismatic sand core (print at the mouth), no machining.
  az_shaft    hollow (Ø16 bore, cables up the AZ axis), no integral collar; see AZ_BORE.
Prismatic ribs, strips and blocks carry no draft in CAD: the pattern maker adds 2 deg (wall >= 6 mm leaves room).
"""
import math
import params as P
import plates as PL

C = P.CAST
A = C['machining']
T2, T3 = math.tan(math.radians(C['draft_out'])), math.tan(math.radians(C['draft_in']))
EL_Z = PL.EL_Z
SPAN = P.RADIAL_SPAN * 1000.0

# --- az_housing (hangs under the base plate, rotates with the head) ----------------------------
Z0 = -PL.T_BASE                        # flange face (parting plane): touches the base plate underside
SEAT_W = P.RADIAL['B']                 # 6206 width
SEAT_Z = (Z0 - SEAT_W / 2, Z0 - SEAT_W / 2 - SPAN)   # seat centres: upper bearing hard against the base plate
R_SEAT = 31.0                          # machined Ø62 H7
R_BASE = 42.0                          # outer ring radius at the flange (drafted narrower downwards)
RING_A_BOT = Z0 - SEAT_W
RING_B_TOP = SEAT_Z[1] + SEAT_W / 2 + 2.0
Z_LIP_TOP = SEAT_Z[1] - SEAT_W / 2     # bearing rests on the lip
Z_BOT = Z_LIP_TOP - 8.0                # lip 8 mm: 3 mm washer recess leaves 5 mm
R_RECESS, H_RECESS = 26.5, 3.0         # Ø53 recess for the 51206 housing washer (Ø52): VERIFY
R_LIPHOLE = 18.0                       # cored Ø36 clearance for the Ø30 shaft
PCD_R, BOSS_R, BOSS_H, TAP_D, TAP_DEPTH = 55.0, 8.0, 16.0, 5.0, 12.0   # 6 x M6x12 (Ø5 drill)
LUG_T, RIB_T, RIB_R_IN, RIB_R_OUT = 6.0, 8.0, 32.0, 55.0   # ribs sized by calc/lsr2_sizing.py (6 x 13 mm failed SF 3)
DRAIN_D, DRAIN_R = 4.0, 22.0
R_CORE = R_SEAT - A                    # cored bore radius at the free end of each core
PRINT_L = 20.0
Z_TOP_P = Z0 + A
Z_BOT_P = Z_BOT - A


def r_out(z):
    return R_BASE + T2 * (z - Z0)


def r_rib(z):
    return RIB_R_OUT + T2 * (z - Z0)


def r_corebore(z, z_free):
    return R_CORE - T3 * abs(z - z_free)


def r_liphole(z):
    return R_LIPHOLE + T3 * (z - Z_LIP_TOP)


# --- mast_clamp (stationary, below the thrust collar) -------------------------------------------
Z_CL_TOP, Z_CL_BOT = -175.0, -235.0
CL_R, SHAFT_D = 21.0, 30.0
CL_PIN_Z, PIN_D = -200.0, 6.0
# V groove 90 deg; arms to (-41, +-24); ears to y=+-45. CL_T = arm thickness, thickened 6 -> 11 mm after the
# arm bending check in calc/lsr2_sizing.py; the ear nut face follows the arm's outer line so the washer seat stays flat.
CL_VERTEX, CL_ARM, CL_EAR_Y, CL_T = -17.0, 24.0, 45.0, 11.0
CL_UB_Y, CL_UB_Z, UB8_D = 35.0, (-190.0, -220.0), 9.0
CL_EAR_Y0 = 26.5
CL_OUT_X = CL_VERTEX + CL_T * math.sqrt(2)           # outer vertex of the V
CL_EAR_X = CL_OUT_X - CL_EAR_Y0                       # ear nut face (x); ear spans -41 .. CL_EAR_X
CL_STRIP = [(-41, 45), (CL_EAR_X, 45), (CL_EAR_X, CL_EAR_Y0), (CL_OUT_X, 0), (CL_EAR_X, -CL_EAR_Y0), (CL_EAR_X, -45),
            (-41, -45), (-41, -CL_ARM), (CL_VERTEX, 0), (-41, CL_ARM)]
# M20 cable gland in the clamp: needs 20 mm of bore length plus 5 mm walls each side below the shaft end. Not available
# (see CL_FREE), so the cables leave through the open Ø30 bore end and no M20 hole is modelled.
M20_D = 20.0

# --- el_bearing_housing: bolted on the EL gearbox output face B (PCD65), local y from that face ---------------
# Machined recess R26 (not the plate pilot R27.6: it would leave a 1.6 mm web to the PCD65 holes) clears the 3.5 mm hub boss; boss diameter VERIFY.
# ring1 = floating bearing (2 mm lip on the gearbox side), ring2 = fixed bearing (2 DIN 472 circlips, 2 mm each side). Ring 1 sits 35 mm
# from the face so that the Ø14 stub between the hub and the bearing is long enough to stay soft (see calc/lsr2_sizing.py).
BH = dict(y0=PL.Y_EL_B, R_FL=44.0, T_FL=8.0, R_B=36.0, R_REC=26.0, T_REC=4.0, R_FBORE=12.0,
          ring1=(35.0, 55.0), ring2=(97.0, 117.0), lip=2.0, circlip=2.0, R_LIP=25.0, R_SEAT=P.RADIAL['D'] / 2,
          rib_t=9.0, rib_x=(32.0, 43.5), rib_y=(8.0, 107.0))
BH['L'] = BH['ring2'][1]
BRG_Y = (BH['y0'] + BH['ring1'][0] + BH['lip'] + P.BEARING_EL['B'] / 2,            # bearing centres, absolute y
         BH['y0'] + BH['ring2'][0] + BH['circlip'] + P.BEARING_EL['B'] / 2)
# --- boom_socket: keyed Ø30 hub on the EL shaft end, then the square socket, y0 = 5 mm (V-ring) past the housing end ---
SOCK = dict(y0=BH['y0'] + BH['L'] + 5.0, L_HUB=30.0, R_HUB=24.0, bore=30.0, key=8.0, t2=3.3, web=6.0, W=51.0,
            pocket=40.5, depth=80.0, lug=(24.0, (-36.0, -12.0)), slit=2.0, pinch_z=-27.0, bolt_back=(20.0, 60.0), bolt_d=9.0, print_l=15.0)
SOCK['L'] = SOCK['L_HUB'] + SOCK['web'] + SOCK['depth']
SOCK_Y1 = SOCK['y0'] + SOCK['L']                  # socket mouth: antenna stations are measured from here

# --- shafts, (lo, hi, d) along their axis (Z for az, Y for el) ------------------------------------
# No integral collar: the 51206 shaft washer (z=-165) rests on a bought DIN 471 Ø30 circlip + 3 mm ring, so the bar
# stock is Ø30 + 3 mm. Circlip (~0.3 EUR) + ring (~0.5 EUR) beat a DIN 705 Ø30 set collar (~4 EUR, 20 mm wide: does
# not fit the 10 mm between the washer and the clamp). Prices and DIN sizes VERIFY.
# AZ top: bought DIN 705 Ø14 collar (about 1.5 EUR, no extra fabricated part) beats a turned disc + M6 into the 1.4404 shaft top.
AZ_SHAFT = [(-225.0, 1.0, 30.0), (1.0, 81.0, 14.0)]
# EL shaft: Ø14 h7 (key 5) inside the gearbox hub, which then only transmits torque, and 37 mm beyond it; shoulder against the inner ring
# of the first 6206; Ø30 through both bearings (DIN 471 circlips either side of the fixed one) to the socket hub (key 8x7), 1 mm short of the hub end.
_Y_SHOULDER = BH['y0'] + BH['ring1'][0] + BH['lip']
EL_SHAFT = [(PL.Y_EL_A + 1.0, _Y_SHOULDER, 14.0), (_Y_SHOULDER, SOCK['y0'] + SOCK['L_HUB'] - 1.0, 30.0)]
SHAFTS = {'az_shaft': AZ_SHAFT, 'el_shaft': EL_SHAFT}
# Hollow AZ shaft: Ø16 bore from the bottom end up to z=-1. It stops below the Ø30 -> Ø14 step at z=1, so the keyed Ø14
# top (no room for a Ø16 bore) stays solid. Cables go up the bore and leave through a Ø6 radial hole at z=-4
# (inside the base plate hole, above the upper bearing, which starts at z=-8); no wrap round the mast.
# The Ø6 cross pin at CL_PIN_Z crosses the bore: cables pass beside the pin. Cable slot in spacer: VERIFY, not modelled.
AZ_BORE = (-225.0, -1.0, 16.0)
AZ_EXIT_D, AZ_EXIT_Z = 6.0, -4.0
SHAFT_BORES = {'az_shaft': [AZ_BORE], 'el_shaft': []}
CL_FREE = AZ_SHAFT[0][0] - Z_CL_BOT                   # clamp bore left empty below the shaft end
M20_EXIT = CL_R - SHAFT_D / 2 >= C['min_wall'] and (CL_FREE - M20_D) / 2 >= C['min_wall']   # False: 10 mm free
SS_G_CM3 = 7.95

ORIGIN = {'az_housing': (0, 0, Z0), 'mast_clamp': (0, 0, Z_CL_TOP), 'el_bearing_housing': (0, BH['y0'], EL_Z),
          'boom_socket': (0, SOCK['y0'], EL_Z)}
ALLOW_AXES = {'az_housing': 'z', 'mast_clamp': 'z', 'el_bearing_housing': 'y', 'boom_socket': 'y'}   # axes on which machining allowance adds size
PARTING = {
    'az_housing': 'Parting plane z=-8 (flange face, flat). Single drag half: all outer draft opens towards the flange. '
                  'Core prints: A on the flange face (cope), B through the lip hole (drag); cores in az_housing_corebox.',
    'mast_clamp': 'Parting plane z=-175 (boss top). Drag only, strip and boss drafted 2 deg by the pattern maker; bore cast solid.',
    'el_bearing_housing': 'Parting plane at the flange face (y = EL gearbox face B): flange in the cope, rings and ribs in the drag; '
                          'drafted 2 deg by the pattern maker; all bores cast solid and bored in one setup (coaxiality of the seats and the face recess).',
    'boom_socket': 'Parting plane at the mouth face: body in the drag, hub up; the 40.5 pocket is formed by one prismatic sand core '
                   '(15 mm print at the mouth, 2 deg draft by the pattern maker; core box not modelled); Ø30 bore cast solid and bored, slit sawn.',
}


def shaft_volume_cm3(segs, bores=()):
    """Turned volume minus coaxial bores [(lo, hi, d)] (keyways and cross holes ignored)."""
    v = sum(math.pi * d * d / 4 * (hi - lo) for lo, hi, d in segs) - sum(math.pi * d * d / 4 * (hi - lo) for lo, hi, d in bores)
    return v / 1000.0


def shaft_length(segs):
    return max(h for _, h, _ in segs) - min(l for l, _, _ in segs)


def shaft_stock(segs):
    """Round bar: finished length + 10 mm, largest step + 3 mm."""
    return max(d for _, _, d in segs) + 3.0, shaft_length(segs) + 10.0


def machined_area_cm2(name):
    """Areas (mm2 -> cm2) of the faces flagged as machined, matching the pattern allowance."""
    pi = math.pi
    if name == 'az_housing':
        a = pi * (R_BASE ** 2 - R_SEAT ** 2) + 6 * ((PCD_R + BOSS_R - R_BASE) * 2 * BOSS_R + pi * BOSS_R ** 2 / 2)
        a += 2 * pi * 2 * R_SEAT * SEAT_W                                  # two seats
        a += pi * (R_SEAT ** 2 - R_LIPHOLE ** 2)                           # lip top (bearing face)
        a += pi * (R_RECESS ** 2 - r_liphole(Z_BOT + H_RECESS) ** 2) + pi * 2 * R_RECESS * H_RECESS   # recess
        a += pi * (r_out(Z_BOT) ** 2 - R_RECESS ** 2)                      # V-ring land
    elif name == 'mast_clamp':
        a = pi * SHAFT_D * (Z_CL_TOP - Z_CL_BOT) + pi * (CL_R ** 2 - (SHAFT_D / 2) ** 2)
    elif name == 'el_bearing_housing':
        b = BH
        a = pi * (b['R_FL'] ** 2 - b['R_REC'] ** 2) + pi * (b['R_REC'] ** 2 - b['R_FBORE'] ** 2)    # flange face, recess floor
        a += 2 * 2 * pi * b['R_SEAT'] * P.BEARING_EL['B'] + pi * (b['R_B'] ** 2 - b['R_SEAT'] ** 2)   # two seats, ring 2 end face
    else:
        s = SOCK
        a = pi * s['bore'] * s['L_HUB'] + pi * (s['R_HUB'] ** 2 - (s['bore'] / 2) ** 2)             # bore, hub end face
    return a / 100.0


def bore_solid_cm3(name):
    """Metal cast into bores that are drilled/bored out later (extra poured metal)."""
    if name == 'mast_clamp':
        return math.pi * (SHAFT_D / 2) ** 2 * (Z_CL_TOP - Z_CL_BOT) / 1000.0
    if name == 'el_bearing_housing':
        b = BH
        r1, r2 = b['ring1'], b['ring2']
        v = b['R_REC'] ** 2 * b['T_REC'] + b['R_FBORE'] ** 2 * b['T_FL'] + b['R_LIP'] ** 2 * b['lip'] \
            + b['R_SEAT'] ** 2 * ((r1[1] - r1[0] - b['lip']) + (r2[1] - r2[0]))
        return math.pi * v / 1000.0
    if name == 'boom_socket':
        return math.pi * (SOCK['bore'] / 2) ** 2 * SOCK['L_HUB'] / 1000.0
    return 0.0


# --- FreeCAD builders ---------------------------------------------------------------------------
def _v(*a):
    from FreeCAD import Vector
    return Vector(*a)


def _rev(pts):
    import Part
    p = [_v(r, 0, z) for r, z in pts]
    return Part.Face(Part.makePolygon(p + [p[0]])).revolve(_v(0, 0, 0), _v(0, 0, 1), 360)


def _rot(s, deg):
    s.rotate(_v(0, 0, 0), _v(0, 0, 1), deg)
    return s


def _fuse(shapes):
    out = shapes[0]
    for s in shapes[1:]:
        out = out.fuse(s)
    return out


def _cut(s, tools):
    for t in tools:
        s = s.cut(t)
    return s


def az_housing(cast=False):
    """Finished housing (cast=False) or the unscaled pattern body without core prints (cast=True)."""
    import Part
    zt = Z0 + (A if cast else 0.0)
    zb = Z_BOT - (A if cast else 0.0)
    r0 = 0.0 if cast else R_SEAT
    parts = [_rev([(r0, zt), (r_out(zt), zt), (r_out(RING_A_BOT), RING_A_BOT), (r0, RING_A_BOT)])]
    if cast:
        parts.append(_rev([(0, RING_B_TOP), (r_out(RING_B_TOP), RING_B_TOP), (r_out(zb), zb), (0, zb)]))
    else:
        zr = Z_BOT + H_RECESS
        parts.append(_rev([(R_SEAT, RING_B_TOP), (r_out(RING_B_TOP), RING_B_TOP), (r_out(Z_BOT), Z_BOT),
                           (R_RECESS, Z_BOT), (R_RECESS, zr), (r_liphole(zr), zr), (R_LIPHOLE, Z_LIP_TOP),
                           (R_SEAT, Z_LIP_TOP)]))
    for k in range(4):
        rib = Part.Face(Part.makePolygon([_v(x, -RIB_T / 2, z) for x, z in
                                          [(RIB_R_IN, -20.0), (r_rib(-20.0), -20.0), (r_rib(-130.0), -130.0),
                                           (RIB_R_IN, -130.0), (RIB_R_IN, -20.0)]])).extrude(_v(0, RIB_T, 0))
        parts.append(_rot(rib, 45 + 90 * k))
    for k in range(6):
        ang = 30 + 60 * k
        lug = Part.makeBox(PCD_R - RIB_R_IN, 2 * BOSS_R, LUG_T + (zt - Z0), _v(RIB_R_IN, -BOSS_R, Z0 - LUG_T))
        boss = Part.makeCylinder(BOSS_R, BOSS_H + (zt - Z0), _v(PCD_R, 0, Z0 - BOSS_H), _v(0, 0, 1))
        parts += [_rot(lug, ang), _rot(boss, ang)]
    s = _fuse(parts)
    if cast:
        return s
    holes = [_rot(Part.makeCylinder(TAP_D / 2, TAP_DEPTH + 1, _v(PCD_R, 0, Z0 + 1), _v(0, 0, -1)), 30 + 60 * k)
             for k in range(6)]
    holes.append(Part.makeCylinder(DRAIN_D / 2, 8.0, _v(DRAIN_R, 0, Z_LIP_TOP - 6.0), _v(0, 0, 1)))
    return _cut(s, holes)


def az_cores():
    """Core A (flange side) and core B (lip side), each with its core print, as revolved solids."""
    zp_a = Z_TOP_P + PRINT_L
    zp_b = Z_BOT_P - PRINT_L
    za_free, zb_free = RING_A_BOT, RING_B_TOP
    a = _rev([(0, zp_a), (r_corebore(zp_a, za_free), zp_a), (R_CORE, za_free), (0, za_free)])
    b = _rev([(0, zb_free), (R_CORE, zb_free), (r_corebore(Z_LIP_TOP, zb_free), Z_LIP_TOP), (R_LIPHOLE, Z_LIP_TOP),
              (r_liphole(zp_b), zp_b), (0, zp_b)])
    return a, b


def az_housing_pattern():
    """Solid pattern (unscaled): housing body + the two core prints that stick out of the faces."""
    za_free = RING_A_BOT
    zp_a = Z_TOP_P + PRINT_L
    zp_b = Z_BOT_P - PRINT_L
    pa = _rev([(0, Z_TOP_P), (r_corebore(Z_TOP_P, za_free), Z_TOP_P), (r_corebore(zp_a, za_free), zp_a), (0, zp_a)])
    pb = _rev([(0, Z_BOT_P), (r_liphole(Z_BOT_P), Z_BOT_P), (r_liphole(zp_b), zp_b), (0, zp_b)])
    return _fuse([az_housing(True), pa, pb])


def az_core_box():
    """Open-top box with the two upright core cavities (cores rammed standing; print end up)."""
    import Part
    out = []
    a, b = az_cores()
    for dx, core, shift, r_top in ((0.0, a, -RING_A_BOT, r_corebore(Z_TOP_P + PRINT_L, RING_A_BOT)),
                                   (80.0, b, -(Z_BOT_P - PRINT_L), R_CORE)):
        core.translate(_v(dx, 0, shift))
        bb = core.BoundBox
        blk = Part.makeBox(80, 70, bb.ZMax + 9, _v(dx - 40, -35, -6))
        tool = core.fuse(Part.makeCylinder(r_top, 6, _v(dx, 0, bb.ZMax - 1), _v(0, 0, 1)))
        out.append(blk.cut(tool))
    return Part.makeCompound(out)


def mast_clamp(cast=False):
    import Part
    a = A if cast else 0.0
    boss = Part.makeCylinder(CL_R, Z_CL_TOP - Z_CL_BOT + a, _v(0, 0, Z_CL_BOT), _v(0, 0, 1))
    pts = [_v(x, y, Z_CL_BOT) for x, y in CL_STRIP]
    strip = Part.Face(Part.makePolygon(pts + [pts[0]])).extrude(_v(0, 0, Z_CL_TOP - Z_CL_BOT))
    s = boss.fuse(strip)
    if cast:
        return s
    tools = [Part.makeCylinder(SHAFT_D / 2, Z_CL_TOP - Z_CL_BOT + 2, _v(0, 0, Z_CL_BOT - 1), _v(0, 0, 1)),
             Part.makeCylinder(PIN_D / 2, 50, _v(0, -25, CL_PIN_Z), _v(0, 1, 0))]
    tools += [Part.makeCylinder(UB8_D / 2, 30, _v(-50, sy * CL_UB_Y, z), _v(1, 0, 0)) for sy in (1, -1) for z in CL_UB_Z]
    return _cut(s, tools)


def el_bearing_housing(cast=False):
    """PCD65 flange (y0 = EL gearbox output face B), 4 ribs at 45 deg, two bearing rings; cast=True gives the pattern body."""
    import Part
    b = BH
    a = A if cast else 0.0
    y0, ax = b['y0'], _v(0, 1, 0)
    (r1a, r1b), (r2a, r2b) = b['ring1'], b['ring2']
    parts = [Part.makeCylinder(b['R_FL'], b['T_FL'] + a, _v(0, y0 - a, EL_Z), ax),
             Part.makeCylinder(b['R_B'], r1b - r1a, _v(0, y0 + r1a, EL_Z), ax),
             Part.makeCylinder(b['R_B'], r2b - r2a + a, _v(0, y0 + r2a, EL_Z), ax)]
    for k in range(4):
        rib = Part.makeBox(b['rib_x'][1] - b['rib_x'][0], b['rib_y'][1] - b['rib_y'][0], b['rib_t'],
                           _v(b['rib_x'][0], y0 + b['rib_y'][0], EL_Z - b['rib_t'] / 2))
        rib.rotate(_v(0, 0, EL_Z), ax, 45 + 90 * k)
        parts.append(rib)
    s = _fuse(parts)
    if cast:
        return s
    tools = [Part.makeCylinder(b['R_REC'], b['T_REC'] + 1, _v(0, y0 - 1, EL_Z), ax),
             Part.makeCylinder(b['R_FBORE'], b['T_FL'] + 2, _v(0, y0 - 1, EL_Z), ax),
             Part.makeCylinder(b['R_LIP'], b['lip'] + 1, _v(0, y0 + r1a - 1, EL_Z), ax),
             Part.makeCylinder(b['R_SEAT'], r1b - r1a - b['lip'] + 1, _v(0, y0 + r1a + b['lip'], EL_Z), ax),
             Part.makeCylinder(b['R_SEAT'], r2b - r2a + 2, _v(0, y0 + r2a - 1, EL_Z), ax)]
    r = P.NMRV030_GEO['face_pcd'] / 2
    tools += [Part.makeCylinder(3.3, b['T_FL'] + 2, _v(sx * r, y0 - 1, EL_Z + sz * r), ax) for sx, sz in ((1, 0), (-1, 0), (0, 1), (0, -1))]
    return _cut(s, tools)


def boom_socket(cast=False):
    """Keyed Ø30 hub with pinch slit, then the 40.5 square socket (cored) for the cross-boom tube; cast=True gives the pattern body."""
    import Part
    h = SOCK
    a = A if cast else 0.0
    y0, ax = h['y0'], _v(0, 1, 0)
    lw, (lz0, lz1) = h['lug']
    w2 = h['W'] / 2
    parts = [Part.makeCylinder(h['R_HUB'], h['L_HUB'] + a, _v(0, y0 - a, EL_Z), ax),
             Part.makeBox(lw, h['L_HUB'] + a, lz1 - lz0, _v(-lw / 2, y0 - a, EL_Z + lz0)),
             Part.makeBox(h['W'], h['L'] - h['L_HUB'], h['W'], _v(-w2, y0 + h['L_HUB'], EL_Z - w2))]
    if cast:
        parts.append(Part.makeBox(h['pocket'], h['print_l'], h['pocket'], _v(-h['pocket'] / 2, y0 + h['L'], EL_Z - h['pocket'] / 2)))
        return _fuse(parts)
    s = _fuse(parts)
    pk = h['pocket']
    tools = [Part.makeCylinder(h['bore'] / 2, h['L_HUB'] + 1, _v(0, y0 - 1, EL_Z), ax),
             Part.makeBox(h['key'], h['L_HUB'] + 1, h['bore'] / 2 + h['t2'], _v(-h['key'] / 2, y0 - 1, EL_Z)),
             Part.makeBox(h['slit'], h['L_HUB'] + 1, 23.0, _v(-h['slit'] / 2, y0 - 1, EL_Z + lz0 - 1.0)),
             Part.makeCylinder(3.3, lw + 4, _v(-lw / 2 - 2, y0 + h['L_HUB'] / 2, EL_Z + h['pinch_z']), _v(1, 0, 0)),
             Part.makeBox(pk, h['depth'] + 1, pk, _v(-pk / 2, y0 + h['L'] - h['depth'], EL_Z - pk / 2))]
    tools += [Part.makeCylinder(h['bolt_d'] / 2, h['W'] + 4, _v(-w2 - 2, y0 + h['L'] - d, EL_Z), _v(1, 0, 0)) for d in h['bolt_back']]
    return _cut(s, tools)


def _stack(segs, axis):
    import Part
    d = _v(*axis)
    base = (lambda lo: _v(0, 0, lo)) if axis == (0, 0, 1) else (lambda lo: _v(0, lo, EL_Z))
    return _fuse([Part.makeCylinder(dia / 2, hi - lo, base(lo), d) for lo, hi, dia in segs])


def az_shaft():
    import Part
    s = _stack(AZ_SHAFT, (0, 0, 1))
    key = Part.makeBox(5.0, 4.0, 40.0, _v(-2.5, 4.0, 20.0))          # DIN 6885 5x5 slot, depth 3 below the Ø14 surface (y=7)
    pin = Part.makeCylinder(PIN_D / 2, 40, _v(0, -20, CL_PIN_Z), _v(0, 1, 0))
    bore = Part.makeCylinder(AZ_BORE[2] / 2, AZ_BORE[1] - AZ_BORE[0] + 1, _v(0, 0, AZ_BORE[0] - 1), _v(0, 0, 1))
    exit_ = Part.makeCylinder(AZ_EXIT_D / 2, 20, _v(0, 0, AZ_EXIT_Z), _v(0, -1, 0))
    return _cut(s, [key, pin, bore, exit_])


def el_shaft():
    import Part
    s = _stack(EL_SHAFT, (0, 1, 0))
    slots = [Part.makeBox(5.0, 50.0, 4.0, _v(-2.5, PL.Y_EL_A + 4.0, EL_Z + 4.0)),                 # gearbox key 5, slot depth 3
             Part.makeBox(8.0, 26.0, 5.0, _v(-4.0, SOCK['y0'] + 2.0, EL_Z + 11.0))]                    # socket key 8x7, slot depth 4
    return _cut(s, slots)


def self_test():
    assert abs(SEAT_Z[0] - SEAT_Z[1] - P.RADIAL_SPAN * 1000) < 1e-9
    assert Z_BOT < Z_LIP_TOP < RING_B_TOP < RING_A_BOT
    assert r_out(RING_B_TOP) - R_SEAT >= C['min_wall'] and r_out(Z_BOT) - R_RECESS >= C['min_wall']
    assert (Z_LIP_TOP - Z_BOT) - H_RECESS >= C['min_wall'] and RIB_T >= C['min_wall'] and CL_T >= C['min_wall']
    assert BOSS_R - TAP_D / 2 >= C['min_wall'] and BOSS_H / LUG_T <= C['max_section_ratio']
    assert TAP_DEPTH < BOSS_H and R_CORE <= R_SEAT - A
    assert CL_R - SHAFT_D / 2 >= C['min_wall']
    b, h = BH, SOCK
    pcd_r = P.NMRV030_GEO['face_pcd'] / 2
    bw = P.BEARING_EL['B']
    assert b['R_B'] - b['R_SEAT'] >= C['min_wall'] and b['T_FL'] >= C['min_wall'] and b['R_FL'] - pcd_r - 3.3 >= C['min_wall']
    assert pcd_r - 3.3 - b['R_REC'] >= 3.0 and 2 * b['R_SEAT'] == P.BEARING_EL['D']
    assert b['ring1'][0] + b['lip'] + bw <= b['ring1'][1] and b['ring2'][0] + 2 * b['circlip'] + bw <= b['ring2'][1]
    assert abs((BRG_Y[1] - BRG_Y[0]) - P.EL_BEARING_SPAN * 1000) < 1e-9 and BRG_Y[1] - BRG_Y[0] >= 60.0
    assert P.BEARING_EL['d'] == EL_SHAFT[1][2] == h['bore']
    assert b['ring1'][0] - b['T_FL'] >= 14.0, 'window for the bolt heads and the hex key'
    assert math.hypot(b['rib_x'][0], b['rib_t'] / 2) > b['R_SEAT'] and math.hypot(b['rib_x'][1], b['rib_t'] / 2) <= b['R_FL'] and b['rib_t'] >= C['min_wall']
    assert h['R_HUB'] - h['bore'] / 2 - h['t2'] >= C['min_wall'] and (h['W'] - h['pocket']) / 2 >= C['min_wall'] and h['web'] >= C['min_wall']
    assert h['pinch_z'] - 3.3 - h['lug'][1][0] >= C['min_wall'] and h['pinch_z'] + h['bore'] / 2 + 3.3 <= -C['min_wall']
    assert h['pocket'] == P.CROSS_BOOM[0] + 0.5 and h['depth'] == 80.0 and h['W'] / 2 >= h['R_HUB'] and max(h['bolt_back']) + h['bolt_d'] / 2 <= h['depth']
    assert h['y0'] - (b['y0'] + b['L']) >= 5.0, 'V-ring room between housing end and hub'
    assert abs(shaft_length(AZ_SHAFT) - 306.0) < 1e-9 and AZ_SHAFT[-1][1] - AZ_SHAFT[-1][0] == 80.0
    assert shaft_stock(AZ_SHAFT) == (33.0, 316.0)                       # Ø30 + 3 mm bar, no collar
    assert shaft_stock(EL_SHAFT) == (33.0, 216.0) and EL_SHAFT[0][1] - EL_SHAFT[0][0] == 92.0
    lo, hi, bd = AZ_BORE
    assert hi < AZ_SHAFT[-1][0] and lo == AZ_SHAFT[0][0]                # bore ends below the solid Ø14 section
    assert (SHAFT_D - bd) / 2 >= C['min_wall'] and AZ_EXIT_Z - AZ_EXIT_D / 2 >= Z0 and AZ_EXIT_Z + AZ_EXIT_D / 2 <= hi
    assert CL_EAR_Y - (CL_UB_Y + UB8_D / 2) >= C['min_wall'] and CL_EAR_X - (-41.0) >= C['min_wall'] and not M20_EXIT
    # hand check: Ø30 x 100 mm = pi * 225 * 100 = 70.686 cm3; tube Ø30/Ø16 x 100 = pi * (225 - 64) * 100 = 50.580 cm3 = 402.1 g
    assert abs(shaft_volume_cm3([(0, 100, 30)]) - 70.686) < 1e-3
    assert abs(shaft_volume_cm3([(0, 100, 30)], [(0, 100, 16)]) - 50.580) < 1e-3
    assert abs(shaft_volume_cm3([(0, 100, 30)], [(0, 100, 16)]) * SS_G_CM3 - 402.1) < 0.05
    assert shaft_stock([(0, 100, 30)]) == (33.0, 110.0)
    for n in ('az_housing', 'mast_clamp', 'el_bearing_housing', 'boom_socket'):
        assert machined_area_cm2(n) > 0


if __name__ == '__main__':
    self_test()
    print('cast_parts self-test OK; 6206 seat centres', SEAT_Z)
