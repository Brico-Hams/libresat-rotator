#!/usr/bin/env python3
"""LSR-2 engineering budget: wind torque, gearbox rating, worm holding and AZ bearing loads.

Writes docs/LSR2_SIZING.md. Inputs live in cad/lsr2/params.py (hardware) and PAYLOADS below.
`python calc/lsr2_sizing.py --check` runs the self-test only.
"""
import math, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'cad', 'lsr2'))
import params as P  # noqa: E402
import cast_parts as CP  # noqa: E402

G, RHO = 9.81, 1.225
WIND_OP_KMH, WIND_SURV_KMH = 60.0, 100.0   # operating (tracking) and survival (parked, worm holding)
MOTOR_DYN_FRACTION = 0.70                  # NEMA23 at ~160 rpm on 48 V / DM542: ~70 % of holding torque
S0_MIN = 2.0                               # static safety factor wanted on rolling bearings
A356_ALLOW_MPA, A356_E_MPA = 80.0, 72000.0  # sand-cast A356-T6 design allowable and modulus: VERIFY with the foundry
SF_CAST, SF_CLAMP = 3.0, 2.0               # wanted safety factors: cast housing ribs, mast clamp
UBOLT_PRELOAD_N, MU_CLAMP = 8000.0, 0.2    # per M8 U-bolt (2 legs, 4 kN per leg), friction on the V faces: VERIFY
M8_AS_MM2, UBOLT_RP_MPA = 36.6, 600.0      # M8 stress area, A4-80 / 8.8 U-bolts (4.6 grade is NOT enough): VERIFY

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
    for r in rows:
        r['ok'] = r['sf'] >= r['need']
    return p['name'], rows


def structural_ok():
    return all(r['ok'] for r in structural()[1])


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
               'Clamp preload bending of the arms is not covered: proof-load the first casting (**VERIFY**).\n')
    out.append('| Part | Check | Demand | Capacity / allowable | SF | Needed | Result |')
    out.append('|---|---|---|---|---|---|---|')
    for r in srows:
        out.append(f"| {r['part']} | {r['check']} | {r['value']:.1f} {r['unit']} | {r['limit']:.1f} {r['unit']} | {r['sf']:.1f} | "
                   f"{r['need']:g} | {'✅' if r['ok'] else '❌'} |")
    out.append('')

    gb = P.GEARBOX[P.GEARBOX_DEFAULT]
    out.append('## Motion\n')
    out.append(f'{P.VMAX_DPS:.0f}°/s at the output = {P.VMAX_DPS / 6 * gb["ratio"]:.0f} rpm at the motor, '
               f'{step_rate(gb):.0f} steps/s at 1/{P.MICROSTEP} microstep (well inside RP2040 PIO and DM542 limits).\n')

    out.append('## Recommendation\n')
    for p in PAYLOADS:
        first = next((g for g in P.GEARBOX if ok(evaluate(p, g))), None)
        out.append(f'- {p["name"]}: ' + (f'**{first}**' if first else '**none of the NMRV sizes**: use a slewing drive or reduce the payload'))
    return '\n'.join(out) + '\n'


def self_test():
    assert abs(q(60) - 170.2) < 0.5, q(60)
    assert abs(step_rate(P.GEARBOX['NMRV030']) - 4266.7) < 1
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
    assert len(rows) == 6
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
