#!/usr/bin/env python3
"""LSR-2 engineering budget: wind torque, gearbox rating, worm holding, AZ bearing loads and the one-sided EL boom head.

Writes docs/LSR2_SIZING.md. Inputs live in cad/lsr2/params.py (hardware) and PAYLOADS below.
`python calc/lsr2_sizing.py --check` runs the self-test only.
"""
import math, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'cad', 'lsr2'))
import params as P  # noqa: E402
import cast_parts as CP  # noqa: E402
import plates as PL  # noqa: E402

G, RHO = 9.81, 1.225
WIND_OP_KMH, WIND_SURV_KMH = 60.0, 100.0   # operating (tracking) and survival (parked, worm holding)
MOTOR_DYN_FRACTION = 0.70                  # NEMA23 at ~160 rpm on 48 V / DM542: ~70 % of holding torque
S0_MIN = 2.0                               # static safety factor wanted on rolling bearings
A356_ALLOW_MPA, A356_E_MPA = 80.0, 72000.0  # sand-cast A356-T6 design allowable and modulus: VERIFY with the foundry
SF_CAST, SF_CLAMP = 3.0, 2.0               # wanted safety factors: cast housing ribs, mast clamp
UBOLT_PRELOAD_N, MU_CLAMP = 8000.0, 0.2    # per M8 U-bolt (2 legs, 4 kN per leg), friction on the V faces: VERIFY
M8_AS_MM2, UBOLT_RP_MPA = 36.6, 600.0      # M8 stress area, A4-80 / 8.8 U-bolts (4.6 grade is NOT enough): VERIFY
M6_AS_MM2 = 20.1                           # M6 stress area (8.8 housing bolts, same proof stress)

# kind 'yagi': moment = F * cp_offset.  kind 'dish': moment = q * A * D * cm * solidity
# (cm ~ 0.12 worst-angle aerodynamic moment coefficient for a parabolic dish about its mount).
PAYLOADS = [
    dict(name='Crossed Yagi pair 145/435, ~2 m booms', kind='yagi', mass=6.0, area=0.35, cd=1.2, cp_offset=0.15, imbalance=0.02),
    dict(name='Dish 1.2 m, mesh (solidity 0.5)', kind='dish', mass=8.0, D=1.2, solidity=0.5, cd=1.4, cm=0.12, imbalance=0.02),
    dict(name='Dish 1.2 m, solid', kind='dish', mass=12.0, D=1.2, solidity=1.0, cd=1.4, cm=0.12, imbalance=0.02),
    dict(name='Dish 1.8 m, mesh (solidity 0.5)', kind='dish', mass=15.0, D=1.8, solidity=0.5, cd=1.4, cm=0.12, imbalance=0.03),
    dict(name='Dish 1.8 m, solid', kind='dish', mass=25.0, D=1.8, solidity=1.0, cd=1.4, cm=0.12, imbalance=0.03),
]


def q(kmh):
    v = kmh / 3.6
    return 0.5 * RHO * v * v


def loads(p, kmh):
    """Return (axis torque N·m, horizontal wind force N) for payload p at wind speed kmh."""
    if p['kind'] == 'yagi':
        f = q(kmh) * p['cd'] * p['area']
        m = f * p['cp_offset']
    else:
        a = 3.14159265 * p['D'] ** 2 / 4
        f = q(kmh) * p['cd'] * a * p['solidity']
        m = q(kmh) * a * p['D'] * p['cm'] * p['solidity']
    return m + p['mass'] * G * p['imbalance'], f


def motor_out(gb):
    return P.NEMA23['t_hold'] * MOTOR_DYN_FRACTION * gb['ratio'] * P.WORM_EFF_RUN


def evaluate(p, gb_name):
    gb = P.GEARBOX[gb_name]
    t_op, _ = loads(p, WIND_OP_KMH)
    t_surv, f_surv = loads(p, WIND_SURV_KMH)
    m_over = f_surv * P.EL_AXIS_HEIGHT
    fr_upper = m_over / P.RADIAL_SPAN + f_surv          # conservative: whole shear on the upper bearing
    return dict(
        t_op=t_op, t_avail=min(gb['m2_rated'], motor_out(gb)),
        t_surv=t_surv, t_hold=gb['m2_rated'] * P.GEAR_PEAK_FACTOR,
        m_over=m_over, m_gear_allow=gb['fr2'] * P.GEAR_REF_ARM,
        s0_radial=P.RADIAL['C0'] / fr_upper,
        s0_thrust=P.THRUST['C0'] / ((p['mass'] + 8.0) * G),  # +8 kg for the EL head itself
    )


def ok(r):
    return r['t_op'] <= r['t_avail'] and r['t_surv'] <= r['t_hold'] and r['s0_radial'] >= S0_MIN


def step_rate(gb):
    return P.VMAX_DPS / 360.0 * gb['ratio'] * P.NEMA23['steps_rev'] * P.MICROSTEP


def euler_n(e_mpa, i_mm4, length_mm, k):
    """Euler buckling load (N) of a column with effective length factor k."""
    return math.pi ** 2 * e_mpa * i_mm4 / (k * length_mm) ** 2


def design_payload():
    """Heaviest-loaded payload that the default gearbox accepts (survival overturning moment)."""
    fit = [p for p in PAYLOADS if ok(evaluate(p, P.GEARBOX_DEFAULT))]
    return max(fit, key=lambda p: evaluate(p, P.GEARBOX_DEFAULT)['m_over'])


def structural():
    """Cast-part checks in the survival wind, geometry from cad/lsr2/cast_parts.py. Returns (payload name, rows)."""
    p = design_payload()
    f = loads(p, WIND_SURV_KMH)[1]                                  # N, horizontal wind force at the EL axis
    rows = []

    def add(part, check, value, unit, limit, need):
        rows.append(dict(part=part, check=check, value=value, unit=unit, limit=limit, sf=limit / value, need=need))

    # az_housing ribs: 4 ribs at 45 deg between the bearing rings, moment axis through two of them (worst case)
    m_h = f * P.EL_AXIS_HEIGHT                                      # N·m at the housing
    z_a, z_b = CP.RING_A_BOT, CP.RING_B_TOP
    l_free = z_a - z_b                                              # free rib length between the rings, mm
    b = CP.r_rib(z_b) - CP.RIB_R_IN                                 # narrowest rib width (radial, drafted), mm
    t = CP.RIB_T
    r_c = (CP.RIB_R_IN + CP.r_rib((z_a + z_b) / 2)) / 2000.0        # rib centroid radius, m
    n_ax = m_h / (2 * r_c)                                          # couple over the rib radius: 2 ribs carry the moment
    v = m_h / P.RADIAL_SPAN / (4 * math.cos(math.radians(45)))      # lower-bearing shear shared by 4 ribs, in the rib plane
    s_ax, s_b = n_ax / (t * b), (v * l_free / 2) / (t * b * b / 6)  # fixed-guided rib: M = V L / 2
    add('az_housing rib', f'axial force {n_ax:.0f} N + bending from shear {v:.0f} N', s_ax + s_b, 'MPa', A356_ALLOW_MPA, SF_CAST)
    add('az_housing rib', f'Euler buckling, K=0.5, L={l_free:.0f} mm, {t:g}x{b:.1f} mm', n_ax,
        'N', euler_n(A356_E_MPA, b * t ** 3 / 12, l_free, 0.5), SF_CAST)

    # mast_clamp: lever from the EL axis to the clamp mid-height
    lever = (CP.EL_Z - (CP.Z_CL_TOP + CP.Z_CL_BOT) / 2) / 1000.0
    m_c = f * lever
    t_leg = m_c / ((CP.CL_UB_Z[0] - CP.CL_UB_Z[1]) / 1000.0) / 2   # wind tension per leg: couple over the two U-bolt levels
    r_min = P.MAST_D[0] / 2                                         # smallest accepted mast: worst lever and friction radius
    add('mast_clamp U-bolt', f'wind tension {t_leg:.0f} N per leg vs preload per leg', t_leg, 'N', UBOLT_PRELOAD_N / 2, SF_CLAMP)
    add('mast_clamp U-bolt', 'preload + wind per leg vs M8 yield', UBOLT_PRELOAD_N / 2 + t_leg, 'N', M8_AS_MM2 * UBOLT_RP_MPA, SF_CLAMP)
    d = CP.CL_UB_Y - r_min / math.sqrt(2)                           # leg to the mast tangent point on the arm, mm
    w = (CP.Z_CL_TOP - CP.Z_CL_BOT) / 2                             # strip height carried by each leg, mm
    add('mast_clamp arm', f'bending, arm {CP.CL_T:g} mm, lever {d:.1f} mm, width {w:g} mm',
        t_leg * d / (w * CP.CL_T ** 2 / 6), 'MPa', A356_ALLOW_MPA, SF_CLAMP)
    t_fr = MU_CLAMP * math.sqrt(2) * 2 * UBOLT_PRELOAD_N * r_min / 1000.0   # 90 deg V: friction on both faces
    t_hold = P.GEARBOX[P.GEARBOX_DEFAULT]['m2_rated'] * P.GEAR_PEAK_FACTOR
    add('mast_clamp friction', f'gearbox standstill torque {t_hold:.1f} N·m vs friction torque', t_hold, 'N·m', t_fr, SF_CLAMP)

    # EL head (phase 6b): one-sided boom along the EL axis, two 6206 in the el_bearing_housing, Ø14 stub in the gearbox hub
    h = el_head(p)
    d_sh = P.BEARING_EL['d'] / 1000.0
    s_b, s_t = 32 * h['m_b2'] / (math.pi * d_sh ** 3) / 1e6, 16 * h['t_el'] / (math.pi * d_sh ** 3) / 1e6
    add('el_shaft Ø30', f'von Mises at the outer bearing, M {h["m_b2"]:.1f} N·m + T {h["t_el"]:.1f} N·m',
        math.sqrt(s_b ** 2 + 3 * s_t ** 2), 'MPa', P.SS_YIELD_MPA, SF_CLAMP)
    add('el bearing pair', f'static load {max(h["r1"], h["r2"]):.0f} N on the outer {P.BEARING_EL["name"]} vs C0', max(h['r1'], h['r2']),
        'N', P.BEARING_EL['C0'], S0_MIN)
    fr2 = P.GEARBOX[P.GEARBOX_DEFAULT]['fr2']
    add('EL gearbox output', f'radial load {h["f_gb"]:.0f} N from coaxiality {P.EL_COAX_MM:g} mm + shaft flex vs 0.2 fr2', h['f_gb'],
        'N', 0.2 * fr2, 1.0)
    b_r = (CP.BH['rib_x'][1] - CP.BH['rib_x'][0])
    t_r = CP.BH['rib_t']
    yc = (CP.BH['rib_x'][0] + CP.BH['rib_x'][1]) / 2 * math.sin(math.radians(45))
    i_tot = 4 * (b_r * t_r * yc ** 2 + (b_r ** 3 * t_r / 12 + t_r ** 3 * b_r / 12) / 2)    # 4 ribs at 45 deg, mm4
    c = (CP.BH['rib_x'][1] + t_r / 2) * math.sin(math.radians(45))
    add('el_bearing_housing ribs', f'bending {h["m_fl"]:.0f} N·m at the flange, 4 ribs {b_r:g}x{t_r:g} mm', h['m_fl'] * 1000 * c / i_tot,
        'MPa', A356_ALLOW_MPA, SF_CAST)
    r_pcd = P.NMRV030_GEO['face_pcd'] / 2000.0
    t_bolt = h['m_fl'] / (2 * r_pcd)                                # couple over two bolts, conservative
    add('el_bearing_housing bolts', f'M6 tension {t_bolt:.0f} N vs min(thread in the gearbox, proof)', t_bolt, 'N',
        min(P.FACE_THREAD_N, M6_AS_MM2 * UBOLT_RP_MPA), SF_CLAMP)
    z_t = (P.CROSS_BOOM[0] ** 4 - (P.CROSS_BOOM[0] - 2 * P.CROSS_BOOM[2]) ** 4) / (6 * P.CROSS_BOOM[0])   # mm3
    add('cross-boom tube', f'bending {h["m_tube"]:.0f} N·m at the socket mouth', h['m_tube'] * 1000 / z_t, 'MPa', P.TUBE_YIELD_MPA, SF_CLAMP)
    for r in rows:
        r['ok'] = r['sf'] >= r['need']
    return p['name'], rows


def el_head(p):
    """Survival loads of payload p on the one-sided boom, split over the two EL bearings (N, N·m, m).

    The payload (weight + wind) is shared by the ANT_POS_Y stations; wind and weight act at 90 deg to each other (combined by hypot,
    conservative: the wind can come from any side). Loads outboard of the outer bearing give M_b2; R1/R2 are the bearing reactions.
    """
    t_el, f_w = loads(p, WIND_SURV_KMH)
    w = p['mass'] * G
    span = P.EL_BEARING_SPAN
    y_b2, y_b1 = CP.BRG_Y[1], CP.BRG_Y[0]
    tube_kg = (P.CROSS_BOOM[0] ** 2 - (P.CROSS_BOOM[0] - 2 * P.CROSS_BOOM[2]) ** 2) * P.CROSS_BOOM_L * P.ALU_PLATE_G_CM3 * 1e-6
    sock_y = CP.SOCK['y0'] + CP.SOCK['L'] / 2
    tube_y = CP.SOCK_Y1 - CP.SOCK['depth'] + P.CROSS_BOOM_L / 2
    n = len(P.ANT_POS_Y)
    arms = [(CP.SOCK_Y1 - y_b2) / 1000.0 + pos for pos in P.ANT_POS_Y]
    mx = sum(f_w / n * a for a in arms)
    wz = w + tube_kg * G + P.SOCKET_MASS_KG * G
    mz = sum(w / n * a for a in arms) + tube_kg * G * (tube_y - y_b2) / 1000.0 + P.SOCKET_MASS_KG * G * (sock_y - y_b2) / 1000.0
    f_x, f_z = f_w, wz
    m_b2 = math.hypot(mx, mz)
    r2 = math.hypot(f_x + mx / span, f_z + mz / span)
    r1 = m_b2 / span
    lf = (y_b2 - CP.BH['y0']) / 1000.0                              # loads' moment arm about the housing flange (face B)
    m_fl = math.hypot(mx + f_x * lf, mz + f_z * lf)
    # gearbox radial load: coaxiality error + slope of the Ø30 shaft between the bearings, acting on the Ø14 stub as a cantilever
    e_pa = P.SS_E_MPA * 1e6
    i30, i14 = math.pi * 0.030 ** 4 / 64, math.pi * 0.014 ** 4 / 64
    l_stub = (y_b1 - (PL.Y_EL_A + P.NMRV030_GEO['out_width'] / 2)) / 1000.0   # hub centre to the first bearing
    theta = m_b2 * span / (6 * e_pa * i30)
    f_gb = 3 * e_pa * i14 / l_stub ** 3 * (P.EL_COAX_MM * 1e-3 + theta * l_stub)
    # boom tube bending at the socket mouth
    mt_x = sum(f_w / n * pos for pos in P.ANT_POS_Y)
    mt_z = sum(w / n * pos for pos in P.ANT_POS_Y) + tube_kg * G * (tube_y - CP.SOCK_Y1) / 1000.0
    return dict(t_el=t_el, m_b2=m_b2, r1=r1, r2=r2, m_fl=m_fl, f_gb=f_gb, m_tube=math.hypot(mt_x, mt_z), tube_kg=tube_kg)


def structural_ok():
    return all(r['ok'] for r in structural()[1])


def mk5_options():
    """Mk5 options that the checks decide on (SARCNET): M14 threaded rod as shaft, M30x56x3 shim stack under the 51206.

    EL: the rod would carry the whole boom bending at the outer bearing (our Ø30 turned shaft carries it today).
    AZ: the rod would replace the Ø14 gearbox section, torque only (standstill torque of the gearbox, as the clamp check).
    """
    h = el_head(design_payload())
    d = P.M14_ROD['d_stress'] / 1000.0
    s_b, s_t = 32 * h['m_b2'] / (math.pi * d ** 3) / 1e6, 16 * h['t_el'] / (math.pi * d ** 3) / 1e6
    el_vm = math.sqrt(s_b ** 2 + 3 * s_t ** 2)
    t_hold = P.GEARBOX[P.GEARBOX_DEFAULT]['m2_rated'] * P.GEAR_PEAK_FACTOR
    az_vm = math.sqrt(3) * 16 * t_hold / (math.pi * d ** 3) / 1e6
    gap = CP.Z_BOT - CP.Z_CL_TOP                                    # shaft washer to mast clamp, mm
    sh = P.SHIM
    return dict(el_vm=el_vm, el_sf=P.M14_ROD['yield_mpa'] / el_vm, az_vm=az_vm, az_sf=P.M14_ROD['yield_mpa'] / az_vm,
                gap=gap, stack=sh['circlip_t'] + sh['n_max'] * sh['t'])


def report():
    pname, srows = structural()
    out = ['# LSR-2 engineering budget (generated by calc/lsr2_sizing.py)\n',
           f'Wind: tracking {WIND_OP_KMH:.0f} km/h ({q(WIND_OP_KMH):.0f} Pa), survival parked {WIND_SURV_KMH:.0f} km/h '
           f'({q(WIND_SURV_KMH):.0f} Pa). Motor NEMA23 {P.NEMA23["t_hold"]} N·m holding, {MOTOR_DYN_FRACTION:.0%} usable at speed; '
           f'worm efficiency {P.WORM_EFF_RUN:.0%}. Gearbox data are generic catalogue values: **verify with your supplier**.\n',
           '## Torque per payload (worst axis) and gearbox choice\n',
           '| Payload | Track torque (N·m) | Survival torque (N·m) | NMRV030 | NMRV040 | NMRV050 |',
           '|---|---|---|---|---|---|']
    for p in PAYLOADS:
        cells = []
        for gb in P.GEARBOX:
            r = evaluate(p, gb)
            cells.append(('✅' if ok(r) else '❌') + f' {r["t_avail"]:.0f}/{r["t_hold"]:.0f}')
        r0 = evaluate(p, P.GEARBOX_DEFAULT)
        out.append(f'| {p["name"]} | {r0["t_op"]:.1f} | {r0["t_surv"]:.1f} | ' + ' | '.join(cells) + ' |')
    out.append('\nCell = ✅/❌ and "available tracking torque / standstill holding torque" (N·m). ✅ needs both, plus the AZ bearing check below.\n')

    out.append('## AZ overturning moment (survival wind)\n')
    out.append(f'EL axis {P.EL_AXIS_HEIGHT * 1000:.0f} mm above the upper AZ bearing; external {P.RADIAL["name"]} pair, '
               f'{P.RADIAL_SPAN * 1000:.0f} mm apart, plus {P.THRUST["name"]} thrust bearing.\n')
    out.append('| Payload | Overturning (N·m) | Gearbox alone allows (NMRV030) | s0 radial pair | s0 thrust |')
    out.append('|---|---|---|---|---|')
    for p in PAYLOADS:
        r = evaluate(p, P.GEARBOX_DEFAULT)
        out.append(f'| {p["name"]} | {r["m_over"]:.0f} | {r["m_gear_allow"]:.0f} | {r["s0_radial"]:.1f} | {r["s0_thrust"]:.0f} |')
    out.append('\n**Finding:** the worm gearbox output bearings cannot carry the overturning moment of any payload above. '
               'LSR-2 therefore puts the AZ shaft in its own radial bearing pair plus the thrust bearing (cast housing), and the '
               'gearbox only transmits torque through the keyed shaft. This differs from the Mk5 load path.\n')

    out.append('## Structural checks of the cast parts (survival wind)\n')
    out.append(f'Payload {pname}, {WIND_SURV_KMH:.0f} km/h, parked. Geometry from cad/lsr2/cast_parts.py. A356-T6 sand allowable '
               f'{A356_ALLOW_MPA:.0f} MPa and E {A356_E_MPA / 1000:.0f} GPa (**VERIFY** with the foundry). U-bolts: {UBOLT_PRELOAD_N / 1000:g} kN preload '
               f'per M8 U-bolt (2 legs), friction mu {MU_CLAMP}, class A4-80 or 8.8 (**VERIFY**). Rib model: the moment axis runs through '
               'two of the four ribs (couple over the rib radius), the lower-bearing shear bends the ribs fixed-guided in their '
               'strong plane. Arm model: cantilever from the mast tangent point to the U-bolt leg, worst case for the smallest mast. '
               'Clamp preload bending of the arms is not covered: proof-load the first casting (**VERIFY**).\n'
               f'EL head (phase 6b): one-sided boom along the EL axis, Yagi payload, survival wind. Weight and wind of the two Yagis (stations at '
               f'{", ".join(f"{x:g}" for x in P.ANT_POS_Y)} m from the socket mouth), the tube and the socket give a bending moment at the outer '
               f'of the two {P.BEARING_EL["name"]} bearings ({P.EL_BEARING_SPAN * 1000:.0f} mm apart, in the el_bearing_housing); wind and weight '
               f'are combined at 90 deg (conservative). The Ø14 shaft section in the gearbox hub then only transmits torque; its radial load follows '
               f'from {P.EL_COAX_MM:g} mm coaxiality plus the slope of the Ø30 section (cantilever stub model, **VERIFY**), limit 0.2 fr2. Shaft yield '
               f'{P.SS_YIELD_MPA:.0f} MPa (1.4404, **VERIFY**), von Mises with bending and torsion on the {P.BEARING_EL["d"]:g} mm section; '
               f'keyway stress concentration, the keyed Ø14 section torsion (SF about 2), fatigue and the el_bracket joint tilt are not covered: '
               f'proof-load the first unit (**VERIFY**). Housing bolts: moment over a PCD65 couple, thread strength in the NMRV face '
               f'{P.FACE_THREAD_N / 1000:g} kN per M6 (**VERIFY**). Tube: 6063-T6, {P.TUBE_YIELD_MPA:.0f} MPa (**VERIFY**).\n')
    out.append('**Finding:** with the boom one-sided along the EL axis, the antenna moment is far beyond what the gearbox hub carries, so '
               'the EL axis needs a bearing pair exactly like AZ (the Ø14 gearbox section stays torque-only).\n')
    out.append('| Part | Check | Demand | Capacity / allowable | SF | Needed | Result |')
    out.append('|---|---|---|---|---|---|---|')
    for r in srows:
        out.append(f"| {r['part']} | {r['check']} | {r['value']:.1f} {r['unit']} | {r['limit']:.1f} {r['unit']} | {r['sf']:.1f} | "
                   f"{r['need']:g} | {'✅' if r['ok'] else '❌'} |")
    out.append('')

    gb = P.GEARBOX[P.GEARBOX_DEFAULT]
    out.append('## Motion\n')
    out.append(f'{P.VMAX_DPS:.0f}°/s at the output = {P.VMAX_DPS / 6 * gb["ratio"]:.0f} rpm at the motor, '
               f'{step_rate(gb):.0f} steps/s at {P.NEMA23["steps_rev"] * P.MICROSTEP} microsteps/rev (DM542 as on SARCTrac Mk5, SARCNET; well inside RP2040 PIO and DM542 limits).\n')

    o = mk5_options()
    out.append('## Mk5 options decided by the checks\n')
    out.append(f'- **M14 threaded rod as EL shaft** (Mk5): von Mises {o["el_vm"]:.0f} MPa at the outer bearing vs {P.M14_ROD["yield_mpa"]:.0f} MPa '
               f'({P.M14_ROD["name"]}), SF {o["el_sf"]:.1f} (needed {SF_CLAMP:g}) {"✅" if o["el_sf"] >= SF_CLAMP else "❌ keep the turned Ø30 shaft"}.')
    out.append(f'- **M14 rod as AZ gearbox section** (torque only, standstill torque): von Mises {o["az_vm"]:.0f} MPa, SF {o["az_sf"]:.1f}; '
               'it passes as a stub but the AZ shaft must stay one Ø30 piece (bearing seats, Ø16 cable bore), so no saving.')
    out.append(f'- **M30x56x3 shims under the 51206**: circlip + {P.SHIM["n_max"]} washers = {o["stack"]:.1f} mm of the {o["gap"]:.1f} mm to the mast clamp '
               f'{"✅" if o["stack"] <= o["gap"] - 1.0 else "❌"} (1 mm spare).\n')

    out.append('## Recommendation\n')
    for p in PAYLOADS:
        first = next((g for g in P.GEARBOX if ok(evaluate(p, g))), None)
        out.append(f'- {p["name"]}: ' + (f'**{first}**' if first else '**none of the NMRV sizes**: use a slewing drive or reduce the payload'))
    return '\n'.join(out) + '\n'


def self_test():
    assert abs(q(60) - 170.2) < 0.5, q(60)
    assert abs(step_rate(P.GEARBOX['NMRV030']) - 1066.7) < 1       # 12/360*80*200*2, Mk5 400 microsteps/rev
    o = mk5_options()
    assert o['el_sf'] < SF_CLAMP, 'M14 rod must fail the EL bending check (turned Ø30 shaft stays)'
    assert o['stack'] <= o['gap'] - 1.0, 'shim stack must fit between the 51206 shaft washer and the mast clamp'
    yagi, dish18 = PAYLOADS[0], PAYLOADS[-1]
    assert ok(evaluate(yagi, 'NMRV030')), 'Yagi pair should fit the NMRV030'
    assert not ok(evaluate(dish18, 'NMRV030')), '1.8 m solid dish must not pass on NMRV030'
    # hand check, Yagi at 60 km/h: 170.2 Pa * 1.2 * 0.35 * 0.15 + 6 * 9.81 * 0.02 = 10.72 + 1.18
    assert abs(evaluate(yagi, 'NMRV030')['t_op'] - 11.90) < 0.05
    assert evaluate(yagi, 'NMRV030')['m_over'] > evaluate(yagi, 'NMRV030')['m_gear_allow'], 'gearbox alone must fail overturning'
    # hand checks: rib couple 60 N·m over r=0.04 m with 2 ribs = 750 N; Euler E=72000, I=100, L=100, K=0.5 = 28424.5 N
    assert abs(60.0 / (2 * 0.04) - 750.0) < 1e-9 and abs(euler_n(72000.0, 100.0, 100.0, 0.5) - 28424.5) < 1.0
    assert design_payload() is yagi
    rows = structural()[1]
    assert len(rows) == 12
    h = el_head(yagi)
    assert h['tube_kg'] > 1.3 and 100 < h['m_b2'] < 400 and h['r2'] > h['r1'] > 0 and h['f_gb'] < 0.2 * P.GEARBOX['NMRV030']['fr2']
    # hand check: sigma_b = 32 M / (pi d3) = 32 * 100 / (pi * 0.03^3) = 37.73 MPa
    assert abs(32 * 100 / (math.pi * 0.03 ** 3) / 1e6 - 37.73) < 0.05
    # hand check: 40x40x3 tube Z = (40^4 - 34^4) / (6 * 40) = 5098.6 mm3
    assert abs((40 ** 4 - 34 ** 4) / 240 - 5098.6) < 0.1
    for r in rows:
        assert r['ok'], f"structural check failed: {r['part']} {r['check']} SF {r['sf']:.2f} < {r['need']:g}"


if __name__ == '__main__':
    self_test()
    if '--check' in sys.argv:
        print('lsr2_sizing self-test OK')
        sys.exit(0)
    text = report()
    with open(os.path.join(ROOT, 'docs', 'LSR2_SIZING.md'), 'w', encoding='utf-8') as fh:
        fh.write(text)
    print('wrote docs/LSR2_SIZING.md')  # no echo: emoji break cp1252 consoles
