#!/usr/bin/env python3
"""LSR-2 sizing for the Mk5-schematic architecture (phase 11a): loads, torques, bearings, stiffness, clamps, fixings, pointing error.

No geometry import: every input comes from cad/lsr2/inputs.py (tagged DATASHEET / MEASURE / PARAMETRIC) and the surviving hardware
constants of cad/lsr2/params.py. Run:  python calc/lsr2_sizing.py          -> writes docs/LSR2_SIZING.md and docs/LSR2_INPUTS.md
              python calc/lsr2_sizing.py --check  -> self-test + every safety factor against its target; exit 1 on failure
Frames: see cad/lsr2/inputs.py. Forces are (Fx, Fy, Fz, x, y, z) in the AZ frame (origin at the body bottom mounting face).
"""
import math, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'cad', 'lsr2'))
import params as PR  # noqa: E402
import inputs as IN  # noqa: E402
import gearbox as GBX  # noqa: E402  (pure-Python gear data of the own gearbox LSR-WG30, phase 7)

I = IN.I
G = 9.81
GB = PR.GEARBOX[PR.GEARBOX_DEFAULT]
RATIO, RATED = GB['ratio'], GB['m2_rated']
PEAK = RATED * PR.GEAR_PEAK_FACTOR            # PARAMETRIC peak: catalogue fs, VERIFY
ETA = PR.WORM_EFF_RUN
R2D = 180.0 / math.pi
ES = list(range(-30, 151, 5))
PSIS = list(range(0, 360, 15))
ALPHA = math.radians(I['acc_dps2'])
OMEGA = math.radians(I['vmax_dps'])
J_R = I['rotor_j'] * RATIO ** 2               # motor rotor inertia reflected to the output
ELPT = (I['el_x_off'], 0.0, I['z_el'])
AZPT = (0.0, 0.0, I['az_brg_z'])
ZC = sum(I['clamp_z']) / 2
CLAMP_SPAN = I['clamp_z'][0] - I['clamp_z'][1]
BRG_EL = dict(name='6004', C=9.95e3, C0=5.0e3)  # DATASHEET catalogue values (SKF 6004), Ø20 seats
AS_BOLT = {'M5': 14.2e-6, 'M6': 20.1e-6, 'M8': 36.6e-6, 'M10': 58.0e-6, 'M12': 84.3e-6}   # ISO 898-1 stress areas
CHK = []


def g(v, n=4):
    return f'{v:.{n}g}'


def tbl(head, rows):
    return ['| ' + ' | '.join(head) + ' |', '|' + '---|' * len(head)] + ['| ' + ' | '.join(str(c) for c in r) + ' |' for r in rows] + ['']


def chk(sec, name, dem, cap, tgt, note='', opt=False):
    """Capacity / demand safety factor against its target; optional rows are reported but never fail --check."""
    CHK.append(dict(sec=sec, name=name, dem=dem, cap=cap, tgt=tgt, sf=cap / dem if dem > 0 else float('inf'), note=note, opt=opt))


# ---- Model: moving group about EL, head about AZ ------------------------------------------------------------------------------
def boom_mass():
    w, t = I['boom_w'], I['boom_t']
    return I['boom_rho'] * (w * w - (w - 2 * t) ** 2) * I['boom_len']


def build():
    """Moving-group items (name, m, a, y, h) with the counterweight of each side sized to balance that side about EL."""
    bm, ca, lv = boom_mass(), I['ant_cg_a'], I['cw_lever']
    ants, mov, side = [], [], []
    for k in ('145', '435'):
        an = dict(n=k + ' MHz', m=I['ant' + k + '_mass'], y=I['ant' + k + '_y'], bl=I['ant' + k + '_boom'],
                  el=I['ant' + k + '_elem'], As=I['ant' + k + '_as'], Af=I['ant' + k + '_af'])
        sg = 1 if an['y'] > 0 else -1
        A = (an['m'] + I['lift_mass'] / 2) * ca
        H = (an['m'] + I['lift_mass'] / 2) * I['ant_h'] + bm / 2 * I['boom_h'] + I['saddle_mass'] / 2 * I['saddle_h'] + I['yoke_mass'] * I['yoke_h']
        mm = math.hypot(A, H)
        an['mcw'] = mm / lv
        mov += [(an['n'] + ' antenna', an['m'], ca, an['y'], I['ant_h']),
                (an['n'] + ' lift arm', I['lift_mass'], ca / 2, an['y'], I['ant_h'] / 2),
                (an['n'] + ' counterweight', an['mcw'], -A / mm * lv, sg * (I['boom_len'] / 2 - 0.05), -H / mm * lv)]
        ants.append(an)
        side.append((A, H))
    mov += [('cross boom', bm, 0.0, 0.0, I['boom_h']), ('saddle plate + clamps', I['saddle_mass'], 0.0, 0.0, I['saddle_h']),
            ('yoke arm +y', I['yoke_mass'], 0.0, I['ly'] / 2, I['yoke_h']), ('yoke arm -y', I['yoke_mass'], 0.0, -I['ly'] / 2, I['yoke_h']),
            ('EL shaft', I['el_shaft_mass'], 0.0, 0.0, 0.0)]
    return ants, mov, side


ANTS, MOV, SIDE = build()
HEAD = [(n, m, x, y, z) for n, m, x, y, z, *_ in IN.HEAD]
M_MOV = sum(m for _, m, *_ in MOV)
M_HEAD = sum(m for _, m, *_ in HEAD)
M_TOT = M_MOV + M_HEAD + I['stat_mass']


def P(a, y, h, e):
    c, s = math.cos(math.radians(e)), math.sin(math.radians(e))
    return (I['el_x_off'] + a * c - h * s, y, I['z_el'] + a * s + h * c)


def q_dyn(kmh):
    return 0.5 * I['air_rho'] * (kmh / 3.6) ** 2


def wind(e, psi, kmh):
    """Wind forces from azimuth psi at elevation e: (moving group, fixed head). Force along the wind at the centre of pressure."""
    q = q_dyn(kmh)
    cp, sp = math.cos(math.radians(psi)), math.sin(math.radians(psi))

    def F(area, cd):
        f = q * cd * area
        return (f * cp, f * sp, 0.0)

    cth = abs(math.cos(math.radians(e)) * cp)          # |boresight . wind|
    sth = math.sqrt(max(0.0, 1 - cth * cth))
    mov = [F(an['Af'] * cth + an['As'] * sth, I['cd_ant']) + P(I['ant_cg_a'] + I['ant_cp_dx'], an['y'], I['ant_h'], e) for an in ANTS]
    mov.append(F(I['boom_w'] * I['boom_len'] * abs(cp) + I['boom_w'] ** 2 * abs(sp), I['cd_boom']) + P(0.0, 0.0, I['boom_h'], e))
    return mov, [F(I['body_area'], I['cd_body']) + (0.0, 0.0, I['body_cp_z'])]


def grav(e):
    return ([(0.0, 0.0, -m * G) + P(a, y, h, e) for _, m, a, y, h in MOV],
            [(0.0, 0.0, -m * G, x, y, z) for _, m, x, y, z in HEAD])


def red(fs, pt):
    """Resultant force and moment (Fx, Fy, Fz, Mx, My, Mz) of the forces about the point pt."""
    out = [0.0] * 6
    for fx, fy, fz, x, y, z in fs:
        rx, ry, rz = x - pt[0], y - pt[1], z - pt[2]
        for i, v in enumerate((fx, fy, fz, ry * fz - rz * fy, rz * fx - rx * fz, rx * fy - ry * fx)):
            out[i] += v
    return out


def case(e, psi, kmh):
    wm, wf = wind(e, psi, kmh)
    gm, gh = grav(e)
    allw, mov, everything = wm + wf, wm + gm, wm + wf + gm + gh
    s, ly = I['el_span'], I['ly']
    Fx, Fy, Fz, Mx, _, Mz = red(mov, ELPT)
    R1 = (-Fx / 2 + Mz / s, -Fz / 2 - Mx / s)
    R2 = (-Fx / 2 - Mz / s, -Fz / 2 + Mx / s)
    Rl = (-Fx / 2 + Mz / ly, -Fz / 2 - Mx / ly)         # same formula with the yoke-arm span: arm loads on the shaft are -Rl
    mb = math.hypot(*[ly / 2 * (-Rl[k]) + s / 2 * R1[k] for k in (0, 1)])
    az = red(everything, AZPT)
    cl, cw = red(everything, (0.0, 0.0, ZC)), red(allw, (0.0, 0.0, ZC))
    return dict(tau_az=abs(red(allw, (0.0, 0.0, 0.0))[5]), tau_el=abs(red(wm, ELPT)[4]),
                el_r=max(math.hypot(*R1), math.hypot(*R2)), el_ax=abs(Fy), mb=mb,
                az_up=math.hypot(az[3], az[4]) / I['az_span'],
                az_lo=math.hypot(-az[0] + az[4] / I['az_span'], -az[1] - az[3] / I['az_span']), az_fz=-az[2],
                m_cl=math.hypot(cl[3], cl[4]), f_h=math.hypot(cl[0], cl[1]), mw=math.hypot(cw[3], cw[4]), fw=math.hypot(cw[0], cw[1]),
                fy_w=abs(sum(f[1] for f in wm)))


def peak(kmh, es=ES, psis=PSIS):
    best = {}
    for e in es:
        for psi in psis:
            for k, v in case(e, psi, kmh).items():
                if v > best.get(k, -1.0):
                    best[k] = v
    return best


def inertia_el():
    return sum(m * (a * a + h * h) for _, m, a, y, h in MOV) + sum(an['m'] * an['bl'] ** 2 / 12 for an in ANTS)


def inertia_az(e):
    tot = 0.0
    for _, m, a, y, h in MOV:
        x, yy, _z = P(a, y, h, e)
        tot += m * (x * x + yy * yy)
    tot += sum(m * (x * x + y * y) for _, m, x, y, z in HEAD)
    tot += sum(an['m'] / 12 * (an['bl'] ** 2 * math.cos(math.radians(e)) ** 2 + an['el'] ** 2) for an in ANTS)
    return tot + boom_mass() * I['boom_len'] ** 2 / 12


def stop(i_ax, r):
    """Bumper impact at vmax: energy, force, torque at the stop radius, bumper stroke."""
    it, k = i_ax + J_R, I['bumper_k']
    f = OMEGA * math.sqrt(k * it)
    return 0.5 * it * OMEGA ** 2, f, f * r, f / k


def life_years(C, p, deg_per_pass):
    return (C / p) ** 3 * 1e6 / (I['passes_per_day'] * 365 * deg_per_pass / 360)


def p_dyn(fr, fa):
    return max(fr, 0.56 * fr + 1.6 * fa)


def p_stat(fr, fa):
    return max(fr, 0.6 * fr + 0.5 * fa)


def motor_torque(rpm):
    c = I['motor_curve']
    if rpm <= c[0][0]:
        return c[0][1]
    for (r0, t0), (r1, t1) in zip(c, c[1:]):
        if rpm <= r1:
            return t0 + (t1 - t0) * (rpm - r0) / (r1 - r0)
    return c[-1][1]


def lock_factor(mu):
    return mu / math.cos(math.radians(I['worm_alpha'])) / math.tan(math.radians(I['worm_lead_deg']))


def mast():
    D, t = I['mast_od'], I['mast_t']
    d = D - 2 * t
    ix, a = math.pi / 64 * (D ** 4 - d ** 4), math.pi / 4 * (D * D - d * d)
    return dict(I=ix, Z=ix / (D / 2), EI=I['mast_e'] * ix, GJ=I['mast_g'] * 2 * ix, m=I['mast_rho'] * a * I['mast_free_h'])


def keyed_sections(d=0.014, b=0.005, t1=0.003):
    k = b * t1 * (d - t1) ** 2 / (2 * d)
    return math.pi * d ** 3 / 32 - k, math.pi * d ** 3 / 16 - k


def rod_sections():
    dr, dh = I['rod_d'], I['pin_d']
    return math.pi * dr ** 3 / 32 - dh * dr ** 2 / 6, math.pi * dr ** 3 / 16 - dh * dr ** 2 / 6


def shaft_decision(mb_s, mb_op, t_op):
    """Keyed turned shaft vs Mk5 M14 rod + roll pin: static von Mises at the gearbox peak/rated torque, fatigue at the operating load."""
    zk, wk = keyed_sections()
    zr, wr = rod_sections()
    out = {}
    for name, z, w, dd, rm, y, (kb, kt), ks in (('keyed Ø14 turned', zk, wk, 0.014, I['shaft_rm'], I['shaft_yield'], I['kf_keyway'], 0.8),
                                                ('M14 rod + 5x8 pin', zr, wr, I['rod_d'], I['rod_rm'], I['rod_yield'], I['kf_thread'], 0.9)):
        st = lambda T: y / math.hypot(mb_s / z, math.sqrt(3) * T / w)
        sb, ta = 32 * mb_op / (math.pi * dd ** 3) * kb, 16 * t_op / (math.pi * dd ** 3) * kt
        se = 0.45 * rm * ks * 0.9 * 0.9
        out[name] = dict(Z=z, W=w, sf_peak=st(PEAK), sf_rated=st(RATED), sig=math.hypot(sb, math.sqrt(3) * ta), se=se)
    return out


# ---- Evaluation -----------------------------------------------------------------------------------------------------------------
def wg30(R):
    """Phase 7: own worm gearbox LSR-WG30 (cad/lsr2/gearbox.py): tooth strength, bearings, housing, efficiency, thermal. Rows are reported but gate --check only
    when GEARBOX_SOURCE = 'lsr_wg30' (the default head uses the bought NMRV030); the self-locking row always gates. Every allowable: VERIFY with the gear maker."""
    W, sec = PR.WG30, 'LSR-WG30 (own gearbox)'
    own = PR.GEARBOX_SOURCE == 'lsr_wg30'
    t_op, t_surv = max(R['taz'], R['tel']), max(R['ps']['tau_az'], R['ps']['tau_el'])
    T = dict(fat=GBX.t_wheel_bend(W['sigma_f']), stat=GBX.t_wheel_bend(W['rp02']), wear=GBX.t_wheel_wear())
    f = GBX.forces(t_surv, W['mu_hold'])
    wb, ob = W['wheel_brg'], W['worm_brg']
    half_w, half_o = math.hypot(f['ft2'], f['fr']) / 2, math.hypot(f['fr'], f['ft1']) / 2
    p0_w, p0_o = max(half_w, 0.6 * half_w + 0.5 * f['ft1']), max(half_o, 0.6 * half_o + 0.5 * f['ft2'])
    wall, sig_h = W['boss_r'] - wb['D'] / 2, W['hold_kc'] * half_w / ((W['boss_r'] - wb['D'] / 2) * wb['B'])
    eta_r, eta_h = GBX.eta(W['mu_run']), GBX.eta(W['mu_hold'])
    avail = R['tm'] * I['motor_usable'] * RATIO * eta_r
    p_out = t_op * OMEGA
    loss = p_out * (1 / eta_r - 1)
    dt_cont = loss / (W['h_conv'] * W['area_m2'])
    chk(sec, 'wheel tooth bending, fatigue, at the worst operating torque', t_op, T['fat'], I['service_factor'], 'N·m (Lewis, sigma_f %g MPa, VERIFY)' % W['sigma_f'], not own)
    chk(sec, 'wheel surface durability at the worst operating torque', t_op, T['wear'], I['service_factor'], 'N·m (K %g N/mm², VERIFY)' % W['k_wear'], not own)
    chk(sec, 'wheel tooth static bending at the standstill holding torque (peak)', PEAK, T['stat'], 1.0, 'N·m (Rp0.2 %g MPa, peak = %g x rating)' % (W['rp02'], PR.GEAR_PEAK_FACTOR), not own)
    chk(sec, 'wheel tooth static bending at the survival torque', t_surv, T['stat'], 1.5, 'N·m', not own)
    chk(sec, f'wheel bearing {wb["name"]} static P0 at the survival torque', p0_w, wb['C0'] / 2, 1.0, 'N vs C0/2 (VERIFY C0)', not own)
    chk(sec, f'worm bearing {ob["name"]} static P0 (fixed one, axial = wheel tangential force)', p0_o, ob['C0'] / 2, 1.0, 'N vs C0/2 (VERIFY C0)', not own)
    chk(sec, 'housing: bearing seat ring stress at the survival torque', sig_h, W['a356_yield'], 1.5, f'MPa, wall {wall:g} x {wb["B"]:g} mm, Kc {W["hold_kc"]:g}; external loads go to the dedicated bearings', not own)
    chk(sec, 'worm self-locking factor with dynamic friction', I['lock_min_dyn'], GBX.lock(W['mu_run']), 1.0, 'factor mu/cos(alpha)/tan(lead), lead %.2f deg' % GBX.gear()['gamma'])
    chk(sec, 'motor torque margin with the LSR-WG30 efficiency', t_op, avail, 1.5, 'N·m at the output (eta %.2f instead of %.2f)' % (eta_r, ETA), not own)
    chk(sec, 'housing temperature rise, continuous at the worst torque and vmax', dt_cont, 40.0, 1.0, 'K (conservative: no duty cycle, natural convection)', not own)
    return dict(gear=GBX.gear(), T=T, f=f, t_op=t_op, t_surv=t_surv, half_w=half_w, half_o=half_o, p0_w=p0_w, p0_o=p0_o, sig_h=sig_h, wall=wall, eta_r=eta_r, eta_h=eta_h,
                avail=avail, loss=loss, dt_cont=dt_cont, dt_duty=dt_cont * W['duty'], a_eq=GBX.a_equal_rating(), own=own)


def evaluate():
    CHK.clear()
    R = {}
    # mass and gravity balance
    chk('Mass', 'total mass (head + payload + stationary)', M_TOT, I['max_mass'], 1.0, 'kg, LIGHT goal')
    sum_a, sum_h = sum(s[0] for s in SIDE), sum(s[1] for s in SIDE)
    lv = I['cw_lever']
    R['g_nocw'] = G * math.hypot(sum_a, sum_h)
    R['mcw_tot'] = sum(an['mcw'] for an in ANTS)
    R['mcw_min'] = max(0.0, (math.hypot(sum_a, sum_h) - I['cw_res_max'] / G) / lv)
    R['res'] = G * (sum(an['m'] for an in ANTS) * I['cg_err'] + R['mcw_tot'] * lv * I['cw_tol'])      # before the CG is measured
    R['res_trim'] = G * R['mcw_tot'] * lv * I['cw_tol']                                                # after trimming on the real CG
    chk('EL gravity balance', 'residual gravity torque (CG and counterweight tolerances)', R['res'], I['cw_res_max'], 1.0, 'N·m')
    chk('EL gravity balance', 'counterweight mass incl. hardware >= hardware alone', I['cw_hw'], min(an['mcw'] for an in ANTS), 1.0, 'kg')
    # wind sweeps
    op, sv, ac = peak(I['wind_op']), peak(I['wind_surv']), peak(I['wind_acc'])
    rows = [(e, peak(I['wind_surv'], [e])) for e in range(-30, 151, 5)]
    R['e_park'] = min(rows, key=lambda r: max(r[1]['tau_az'], r[1]['tau_el']))[0]
    ps = peak(I['wind_surv'], [R['e_park']])
    p130 = peak(I['wind_surv_opt'], [R['e_park']])
    R.update(op=op, sv=sv, ac=ac, ps=ps, p130=p130)
    R['sweep'] = [(e, peak(I['wind_op'], [e]), peak(I['wind_surv'], [e])) for e in (-30, 0, 30, 60, 90, 120, 150)]
    R['park'] = [(e, peak(I['wind_surv'], [e])) for e in (0, 90, R['e_park'])]
    # acceleration, motor, gearbox
    R['iel'], R['iaz'] = inertia_el(), max(inertia_az(e) for e in ES)
    R['taz'] = op['tau_az'] + (R['iaz'] + J_R) * ALPHA
    R['tel'] = op['tau_el'] + R['res'] + (R['iel'] + J_R) * ALPHA
    allowed = RATED / I['service_factor']
    chk('Gearbox (service factor)', 'AZ output torque at 60 km/h + acceleration', R['taz'], allowed, 1.0, f'N·m vs rating {RATED}/SF {I["service_factor"]}')
    chk('Gearbox (service factor)', 'EL output torque at 60 km/h + residual + acceleration', R['tel'], allowed, 1.0, 'N·m')
    R['rpm'] = I['vmax_dps'] / 360 * 60 * RATIO
    R['tm'] = motor_torque(R['rpm'])
    R['avail'] = R['tm'] * I['motor_usable'] * RATIO * ETA
    chk('Motor', f'torque margin at {I["vmax_dps"]:g} deg/s ({R["rpm"]:.0f} rpm motor)', max(R['taz'], R['tel']), R['avail'], 1.5, 'N·m at the output')
    R['stall_out'] = PR.NEMA23['t_hold'] * RATIO * ETA
    # mechanical stops
    R['stops'] = []
    for nm, iax, r in (('AZ', R['iaz'], I['stop_r'][0]), ('EL', R['iel'], I['stop_r'][1])):
        e_, f_, t_, s_ = stop(iax, r)
        R['stops'].append((nm, e_, f_, t_, s_))
        chk('Mechanical stops', f'{nm} bumper impact torque at vmax', t_, PEAK, 2.0, f'N·m vs gearbox peak {PEAK:g}')
        chk('Mechanical stops', f'{nm} bumper stroke', s_, I['bumper_stroke'], 1.5, 'm')
    R['soft_margin'] = math.degrees(OMEGA) ** 2 / (2 * I['acc_dps2']) + I['vmax_dps'] * I['latency_s']
    # bearings
    uplift = q_dyn(I['wind_surv']) * I['cl_ant'] * sum(an['As'] for an in ANTS)
    R['uplift'] = uplift
    chk('Bearings', 'AZ circlip retention vs wind uplift', uplift, I['circlip_n'], 2.0, 'N')
    rad, thr = PR.RADIAL, PR.THRUST
    az_s, az_o = max(ps['az_up'], ps['az_lo']), max(op['az_up'], op['az_lo'])
    chk('Bearings', f'AZ radial {rad["name"]}: static P0 (survival, parked)', az_s, rad['C0'] / 2, 1.0, f'N vs C0/2 (s0 >= 2)')
    yrs = life_years(rad['C'], az_o, I['az_travel_pass'])
    chk('Bearings', f'AZ radial {rad["name"]}: L10 life at duty', I['life_years'], yrs, 1.0, f'years (P = {az_o:.0f} N, 60 km/h worst case)')
    chk('Bearings', f'AZ thrust {thr["name"]}: static (weight + survival)', ps['az_fz'], thr['C0'] / 2, 1.0, 'N vs C0/2')
    chk('Bearings', f'AZ thrust {thr["name"]}: L10 life', I['life_years'], life_years(thr['C'], op['az_fz'], I['az_travel_pass']), 1.0, 'years')
    el_p0 = p_stat(ps['el_r'], ps['el_ax'])
    el_p = p_dyn(op['el_r'], op['el_ax'])
    chk('Bearings', f'EL {BRG_EL["name"]}: static (locating bearing, survival)', el_p0, BRG_EL['C0'] / 2, 1.0, 'N vs C0/2')
    chk('Bearings', f'EL {BRG_EL["name"]}: L10 life', I['life_years'], life_years(BRG_EL['C'], el_p, I['el_travel_pass']), 1.0, f'years (P = {el_p:.0f} N)')
    R['brg'] = dict(az_s=az_s, az_o=az_o, az_yrs=yrs, el_p0=el_p0, el_p=el_p)
    chk('Gearbox', 'radial load from bearing/bore coaxiality', 48 * I['shaft_e'] * math.pi / 64 * 0.014 ** 4 * max(0.0, I['coax_err'] - I['fit_clear']) / I['el_span'] ** 3,
        0.2 * GB['fr2'], 1.0, 'N vs 0.2 x fr2 (dedicated bearings carry the external loads)')
    # mast
    m = mast()
    R['mast'] = m
    h = I['mast_free_h']
    m_base = ps['m_cl'] + ps['f_h'] * h + q_dyn(I['wind_surv']) * 1.2 * I['mast_od'] * h * h / 2
    R['m_base'] = m_base
    chk('Mast', 'bending stress at the base (survival)', m_base / m['Z'], I['mast_yield'], 1.5, 'Pa')
    m_head = M_TOT
    R['fn'] = math.sqrt(3 * m['EI'] / h ** 3 / (m_head + 0.2357 * m['m'])) / (2 * math.pi)
    R['fn_t'] = math.sqrt(m['GJ'] / h / R['iaz']) / (2 * math.pi)
    t_acc = I['vmax_dps'] / I['acc_dps2']
    R['fn_req'] = I['mast_min_fn_factor'] / t_acc
    chk('Mast', 'bending natural frequency vs tracking ramp', R['fn_req'], R['fn'], 1.0, f'Hz ({I["mast_min_fn_factor"]:g} x 1/t_acc)')
    chk('Mast', 'torsional natural frequency vs tracking ramp', R['fn_req'], R['fn_t'], 1.0, 'Hz')
    # clamps
    pre, d_leg = I['ubolt_leg_pre'], ps['m_cl'] / CLAMP_SPAN / 2
    R['d_leg'] = d_leg
    chk('Clamps', 'mast U-bolt: preload kept under survival overturning', d_leg, pre, 1.5, 'N per leg')
    chk('Clamps', 'mast U-bolt: leg stress (preload + overturning)', pre + d_leg, AS_BOLT['M8'] * I['bolt_rp'], 1.5, 'N, M8 8.8 yield load')
    r_min = I['mast_range'][0] / 2
    R['t_slip'] = I['mu_clamp'] * math.sqrt(2) * 2 * pre * r_min * 2
    chk('Clamps', 'mast clamp slip torque (2 clamps, V faces) vs gearbox peak', PEAK, R['t_slip'], 2.0, 'N·m')
    sig = (2 * pre / (I['mast_od'] * I['clamp_w'])) * (I['mast_od'] / 2 / I['mast_t']) * I['crush_kloc']
    R['crush'] = sig
    chk('Clamps', 'mast tube crush under the clamp', sig, I['mast_yield'], 1.5, 'Pa (design mast Ø60.3 x 3.6)')
    t_boom = I['mu_clamp'] * 4 * I['boom_clamp_leg_pre'] * I['boom_w'] / 2
    R['t_boom'] = t_boom
    chk('Clamps', 'boom twist slip in the saddle vs EL torque (survival)', ps['tau_el'], t_boom, 2.0, 'N·m')
    chk('Clamps', 'boom axial slip in the saddle vs wind', ps['fy_w'], I['mu_clamp'] * 4 * I['boom_clamp_leg_pre'], 2.0, 'N')
    # keys (DIN 6885)
    R['keys'] = []
    for nm, d, b, t2, l, T, hub in (('EL/AZ gearbox hub, Ø14 5x5x40', 14, 5, 2.3, I['key_len_hub'], PEAK, I['shaft_yield']),
                                    ('EL yoke arm, Ø20 6x6x25 (T/2 each)', 20, 6, 2.8, I['key_len_arm'], PEAK / 2, min(I['shaft_yield'], I['a356_yield']))):
        d_, b_, t_ = d / 1000, b / 1000, t2 / 1000
        tau = 2 * T / (d_ * b_ * l)
        pr = 2 * T / (d_ * t_ * l * 0.75)
        R['keys'].append((nm, T, tau, pr))
        chk('Keys', nm + ': shear', tau, 0.58 * I['shaft_yield'], 2.0, 'Pa at the gearbox peak torque')
        chk('Keys', nm + ': bearing pressure', pr, hub, 2.0, 'Pa at the gearbox peak torque')
    # bolts (VDI 2230 simplified)
    R['bolts'] = []
    for nm, a in AS_BOLT.items():
        d = float(nm[1:]) / 1000
        fm = 0.7 * I['bolt_rp'] * a
        R['bolts'].append((nm, a * 1e6, fm, I['nut_k'] * d * fm))
    f_sh = PEAK / (4 * PR.NMRV030_GEO['face_pcd'] / 2000)
    chk('Bolts', 'gearbox face M6 x4: friction grip vs torque', f_sh, 0.15 * 0.7 * I['bolt_rp'] * AS_BOLT['M6'], 2.0, 'N per bolt, mu 0.15')
    # EL/AZ shaft decision
    mb_s, mb_op = ps['mb'], op['mb']
    R['shaft'] = shaft_decision(mb_s, mb_op, R['tel'])
    kd = R['shaft']['keyed Ø14 turned']
    chk('Shaft', 'keyed Ø14: static von Mises at gearbox peak', I['shaft_yield'] / kd['sf_peak'], I['shaft_yield'], 2.0, 'Pa')
    chk('Shaft', 'keyed Ø14: fatigue at operating load', kd['sig'], kd['se'], 1.5, 'Pa')
    # input adapter
    chk('Input adapter', 'Ø8 -> Ø11 bushing set-screw holding torque vs 2 x motor holding torque', 2 * PR.NEMA23['t_hold'], I['adapter_hold'], 1.0, 'N·m')
    # pointing error at the accuracy wind
    h_ = I['mast_free_h']
    tz = ac['tau_az']
    te = ac['tau_el'] + R['res_trim']
    phi = (ac['fw'] * h_ ** 2 / 2 + ac['mw'] * h_) / m['EI']
    jp = lambda d: math.pi * d ** 4 / 32
    gs = I['shaft_g']
    am, per = (I['boom_w'] - I['boom_t']) ** 2, 4 * (I['boom_w'] - I['boom_t'])
    jb = 4 * am ** 2 * I['boom_t'] / per
    half = 360 / (PR.NEMA23['steps_rev'] * PR.MICROSTEP * RATIO) / 2
    play_az, play_el = 2 * I['brg_play'] / I['az_span'] * R2D, 2 * I['brg_play'] / I['el_span'] * R2D
    az_fix = [('resolution (half microstep)', half), ('backlash residual after compensation', I['bl_repeat']), ('bearing-play tilt', play_az)]
    az_load = [('gearbox torsion', tz / I['gb_stiff'] * R2D),
               ('AZ shaft torsion (Ø14 + Ø30)', tz * (I['az_sec14_len'] / (gs * jp(0.014)) + I['az_sec30_len'] / (gs * jp(0.030))) * R2D),
               ('mast torsion', tz * h_ / m['GJ'] * R2D), ('mast tilt', phi * R2D)]
    el_fix = [('resolution (half microstep)', half), ('backlash residual after compensation', I['bl_repeat']), ('bearing-play tilt', play_el),
              ('trimmed gravity residual / gearbox', R['res_trim'] / I['gb_stiff'] * R2D)]
    el_load = [('gearbox torsion', ac['tau_el'] / I['gb_stiff'] * R2D),
               ('EL shaft torsion (Ø14 + Ø20 per arm)', ac['tau_el'] * (I['el_sec14_len'] / (gs * jp(0.014)) + I['el_sec20_len'] / (gs * jp(0.020)) / 2) * R2D),
               ('boom torsion (half length)', ac['tau_el'] / 2 * (I['boom_len'] / 2) / (I['boom_g'] * jb) * R2D), ('mast tilt', phi * R2D)]
    pt = {}
    for nm, fix, load in (('AZ', az_fix, az_load), ('EL', el_fix, el_load)):
        f, l = sum(v for _, v in fix), sum(v for _, v in load)
        vlim = I['wind_acc'] * math.sqrt(max(0.0, 0.1 - f) / l) if l > 0 else float('inf')
        pt[nm] = dict(fix=fix, load=load, f=f, l=l, tot=f + l, vlim=vlim)
        chk('Pointing error', f'{nm} total at {I["wind_acc"]:g} km/h (target < 0.1 deg)', f + l, 0.1, 1.0, 'deg, linear sum of the terms')
    R['pt'] = pt
    R['half'] = half
    # raw backlash (information) and chain
    keyslack = lambda d: math.degrees(I['key_clear'] / (d / 2))
    in_play = math.degrees(I['key_clear'] / (I['adapter_od'] / 2000)) / RATIO
    R['bl_raw'] = dict(AZ=I['gb_backlash'] + keyslack(0.014) + in_play, EL=I['gb_backlash'] + keyslack(0.014) + keyslack(0.020) + in_play, gb=I['gb_backlash'], key14=keyslack(0.014), key20=keyslack(0.020), inp=in_play)
    # power loss and parking
    R['lock_s'], R['lock_d'] = lock_factor(I['worm_mu_static']), lock_factor(I['worm_mu_dyn'])
    chk('Power loss', 'worm self-locking factor with dynamic friction', I['lock_min_dyn'], R['lock_d'], 1.0, 'factor mu/cos(alpha)/tan(lead)')
    chk('Power loss', 'AZ holding torque, survival, parked at the best elevation', ps['tau_az'], PEAK, 1.5, 'N·m vs gearbox peak')
    chk('Power loss', 'EL holding torque, survival, parked at the best elevation', ps['tau_el'], PEAK, 1.5, 'N·m vs gearbox peak')
    chk('Survival 130 km/h (option)', 'AZ holding torque', p130['tau_az'], PEAK, 1.5, 'N·m, reported only', True)
    chk('Survival 130 km/h (option)', 'EL holding torque', p130['tau_el'], PEAK, 1.5, 'N·m, reported only', True)
    R['wg30'] = wg30(R)
    return R


# ---- Reports --------------------------------------------------------------------------------------------------------------------
def report(R):
    L = ['# LSR-2 sizing (Mk5-schematic architecture)', '',
         'Generated by `python calc/lsr2_sizing.py` from `cad/lsr2/inputs.py` and `cad/lsr2/params.py`. Do not edit by hand. '
         'Inputs and open decisions: [LSR2_INPUTS.md](LSR2_INPUTS.md). Each number carries its tag in the inputs table '
         '(DATASHEET / MEASURE / PARAMETRIC); results are only as good as the MEASURE rows.', '']
    fails = [c for c in CHK if not c['opt'] and c['sf'] < c['tgt']]
    L += [f'**Result: {"all safety factors meet their target" if not fails else str(len(fails)) + " check(s) below target"}.** '
          f'Total mass {M_TOT:.1f} kg (limit {I["max_mass"]:g}); moving group {M_MOV:.1f} kg; head {M_HEAD:.1f} kg; '
          f'worst case taken over elevation {ES[0]}..{ES[-1]} deg and wind azimuth 0..345 deg.', '']
    L += ['## 1. Safety-factor summary', '']
    secs = []
    for c in CHK:
        if c['sec'] not in secs:
            secs.append(c['sec'])
    for s in secs:
        L += [f'### {s}', '']
        L += tbl(['Check', 'Demand', 'Capacity', 'SF', 'Target', 'OK', 'Note'],
                 [(c['name'], g(c['dem']), g(c['cap']), g(c['sf'], 3), g(c['tgt'], 2), ('✅' if c['sf'] >= c['tgt'] else ('➖' if c['opt'] else '❌')), c['note']) for c in CHK if c['sec'] == s])
    L += ['## 2. Gravity balance on EL', '']
    L += tbl(['Item', 'Value'], [('Moment without counterweights (both sides)', f'{R["g_nocw"]:.2f} N·m (max over elevation)'),
                                ('Counterweights (balanced, incl. hardware)', ' + '.join(f'{an["mcw"]:.2f} kg' for an in ANTS) + f' = {R["mcw_tot"]:.2f} kg at {I["cw_lever"]*1000:.0f} mm'),
                                ('Minimum total counterweight for a residual <= ' + f'{I["cw_res_max"]:g} N·m', f'{R["mcw_min"]:.2f} kg'),
                                ('Residual before the CG is measured', f'{R["res"]:.2f} N·m'),
                                ('Residual after trimming (cw tolerance only)', f'{R["res_trim"]:.3f} N·m')])
    L += [f'Counterweights are adjustable (clamped on a threaded arm), so trimming on the real CG removes the antenna-CG term. '
          f'Moving group about EL: {R["iel"]:.2f} kg·m² (+ rotor {J_R:.2f} reflected); head + antennas about AZ: {R["iaz"]:.2f} kg·m² worst case.', '']
    L += ['## 3. Wind torque vs elevation (worst azimuth, N·m)', '']
    L += tbl(['EL deg', f'AZ @ {I["wind_op"]:g} km/h', f'EL @ {I["wind_op"]:g} km/h', f'AZ @ {I["wind_surv"]:g} km/h', f'EL @ {I["wind_surv"]:g} km/h'],
             [(e, g(o['tau_az'], 3), g(o['tau_el'], 3), g(s['tau_az'], 3), g(s['tau_el'], 3)) for e, o, s in R['sweep']])
    L += [f'Dynamic pressure q({I["wind_op"]:g} km/h) = {q_dyn(I["wind_op"]):.1f} Pa, q({I["wind_surv"]:g}) = {q_dyn(I["wind_surv"]):.1f} Pa. '
          f'Antenna area A = Af cos(t) + As sin(t), t = angle between boresight and wind, force at the centre of pressure.', '']
    L += ['## 4. Parking in survival wind', '']
    L += tbl(['Parked EL deg', 'AZ torque N·m', 'EL torque N·m'], [(e, g(p['tau_az'], 3), g(p['tau_el'], 3)) for e, p in R['park']])
    L += [f'Best elevation on the sweep: {R["e_park"]} deg (minimises the larger of the two torques; compare the zenith and horizon rows above). '
          f'130 km/h option at that elevation: AZ {R["p130"]["tau_az"]:.1f}, EL {R["p130"]["tau_el"]:.1f} N·m '
          f'against the peak {PEAK:g} N·m (reported, not a gate).', '']
    L += ['## 5. Motor and gearbox', '']
    L += tbl(['Item', 'Value'], [(f'Motor speed at {I["vmax_dps"]:g} deg/s', f'{R["rpm"]:.0f} rpm; step rate {I["vmax_dps"]/360*PR.NEMA23["steps_rev"]*PR.MICROSTEP*RATIO:.1f} steps/s'),
                                ('Torque from the curve (MEASURE, typical NEMA23)', f'{R["tm"]:.2f} N·m x {I["motor_usable"]} usable'),
                                ('Available at the output', f'{R["avail"]:.1f} N·m (x {RATIO} x eta {ETA})'),
                                ('Required AZ / EL (60 km/h + acceleration)', f'{R["taz"]:.1f} / {R["tel"]:.1f} N·m'),
                                ('Gearbox allowed (rating / service factor)', f'{RATED / I["service_factor"]:.1f} N·m; peak {PEAK:g} N·m'),
                                ('Motor stall torque at the output', f'{R["stall_out"]:.0f} N·m, above the gearbox peak: stops are soft first (see 6)')])
    L += ['The motor can overload the gearbox: keep the firmware soft limits, a bumper per stop and, if the bench shows it, reduce the DM542 current.', '']
    L += ['## 6. Mechanical stops', '']
    L += tbl(['Axis', 'Energy J', 'Force N', 'Torque N·m', 'Stroke mm'], [(n, g(e, 3), g(f, 3), g(t, 3), g(s * 1000, 3)) for n, e, f, t, s in R['stops']])
    L += [f'Bumper k = {I["bumper_k"]:g} N/m (PARAMETRIC). Software deceleration from vmax needs {R["soft_margin"]:.1f} deg between the soft limit and the '
          f'mechanical stop (v²/2a + v·latency); inside that margin the bumper takes the rest.', '']
    L += ['## 7. Bearing loads', '']
    b = R['brg']
    L += tbl(['Bearing', 'Survival, parked (N)', '60 km/h worst case (N)'],
             [('AZ radial pair (max of upper / lower)', g(b['az_s'], 4), g(b['az_o'], 4)), ('AZ thrust (axial)', g(R['ps']['az_fz'], 4), g(R['op']['az_fz'], 4)),
              ('EL 6004 (radial / axial on the locating one)', f'{R["ps"]["el_r"]:.0f} / {R["ps"]["el_ax"]:.0f}', f'{R["op"]["el_r"]:.0f} / {R["op"]["el_ax"]:.0f}'),
              ('Overturning moment at the mast clamp (N·m)', g(R['ps']['m_cl'], 4), g(R['op']['m_cl'], 4))])
    L += ['Gearboxes only transmit torque; the external loads go to these bearings. EL shaft bending at the hub: '
          f'{R["ps"]["mb"]:.1f} N·m survival, {R["op"]["mb"]:.1f} N·m operating.', '']
    L += ['## 8. Mast and clamps', '']
    m = R['mast']
    L += tbl(['Item', 'Value'], [('Mast', f'Ø{I["mast_od"]*1000:.1f} x {I["mast_t"]*1000:.1f} mm, I = {m["I"]:.4g} m⁴, EI = {m["EI"]/1000:.1f} kN·m², free height {I["mast_free_h"]:g} m'),
                                ('Base moment, survival', f'{R["m_base"]:.0f} N·m ({R["m_base"]/m["Z"]/1e6:.0f} MPa)'),
                                ('Natural frequency bending / torsion', f'{R["fn"]:.1f} / {R["fn_t"]:.1f} Hz, required >= {R["fn_req"]:.1f} Hz'),
                                ('U-bolt leg load change', f'{R["d_leg"]:.0f} N on {I["ubolt_leg_pre"]:g} N preload'),
                                ('Clamp slip torque / crush stress', f'{R["t_slip"]:.0f} N·m / {R["crush"]/1e6:.0f} MPa'),
                                ('Boom twist slip torque', f'{R["t_boom"]:.0f} N·m')])
    L += ['Installation: ' + I['install'] + '.', '']
    L += ['## 9. Keys and bolts', '']
    L += tbl(['Key (DIN 6885)', 'T N·m', 'Shear MPa', 'Pressure MPa'], [(n, g(T, 3), g(t / 1e6, 3), g(p / 1e6, 3)) for n, T, t, p in R['keys']])
    L += tbl(['Bolt 8.8', 'As mm²', 'Preload 0.7 Rp·As (N)', 'Tightening torque K·d·F (N·m)'], [(n, g(a, 3), f'{fm:.0f}', g(t, 3)) for n, a, fm, t in R['bolts']])
    L += [f'K = {I["nut_k"]} with anti-seize. Simplified VDI 2230: no embedding or load-introduction factors; verify critical joints with the full method.', '']
    L += ['## 10. Pointing error and resolution chain', '']
    for nm in ('AZ', 'EL'):
        p = R['pt'][nm]
        L += [f'### {nm}', '']
        L += tbl(['Term', 'deg', 'Kind'], [(n, g(v, 3), 'fixed') for n, v in p['fix']] + [(n, g(v, 3), f'load, at {I["wind_acc"]:g} km/h') for n, v in p['load']] +
                 [('**Total**', f'**{p["tot"]:.3f}**', 'target < 0.1')])
        L += [f'Error vs wind: ' + ', '.join(f'{v:g} km/h: {p["f"] + p["l"] * (v / I["wind_acc"]) ** 2:.3f} deg' for v in (10, 25, 40, 60)) +
              f'. The 0.1 deg target holds up to {p["vlim"]:.0f} km/h.', '']
    bl = R['bl_raw']
    L += [f'Resolution: {360 / (PR.NEMA23["steps_rev"] * PR.MICROSTEP * RATIO):.5f} deg per microstep ({PR.NEMA23["steps_rev"] * PR.MICROSTEP} microsteps/rev through {RATIO}:1). '
          f'Raw backlash AZ {bl["AZ"]:.2f} deg, EL {bl["EL"]:.2f} deg (gearbox {bl["gb"]:.2f} + keys {bl["key14"]:.2f}/{bl["key20"]:.2f} + input {bl["inp"]:.3f}): '
          f'above 0.1 deg, so the firmware reversal compensation is required; the budget uses the residual {I["bl_repeat"]:g} deg (MEASURE with XCAL BACKLASH).', '']
    L += ['## 11. Power loss', '']
    L += tbl(['Item', 'Value'], [('Self-locking factor, static / dynamic friction', f'{R["lock_s"]:.2f} / {R["lock_d"]:.2f} (need >= {I["lock_min_dyn"]})'),
                                ('Survival torque at the best parking elevation AZ / EL', f'{R["ps"]["tau_az"]:.1f} / {R["ps"]["tau_el"]:.1f} N·m'),
                                ('Verdict', 'no brake needed if the bench test confirms the worm holds under vibration; park at the best elevation before power-off')])
    L += ['## 12. Gearbox input adapter (NMRV030 Ø11 bore vs 57BYG250H-8 Ø8 shaft)', '']
    L += tbl(['Part', 'Dimension', 'Tag'], [('Keyed bushing OD (fits the gearbox bore)', f'Ø{I["adapter_od"]:g} mm, key {I["adapter_key"]}', 'DATASHEET (caliper the real bore)'),
                                          ('Bushing ID (motor shaft with flat)', f'Ø{I["adapter_id"]:g} mm', 'DATASHEET (caliper the flat)'),
                                          ('Length', f'{I["adapter_len"]:g} mm', 'MEASURE'), ('Retention', I['adapter_screws'], 'PARAMETRIC'),
                                          ('Holding torque', f'{I["adapter_hold"]:g} N·m vs 2 x {PR.NEMA23["t_hold"]} N·m motor', 'MEASURE (pull test)')])
    L += ['Alternative: a supplier NEMA23 input kit with an Ø8 bore (no bushing, no extra play); preferred if the price is similar. Decide after the caliper check.', '']
    L += ['## 13. EL / AZ shaft decision: Mk5 M14 rod + 5x8 roll pins vs a turned keyed shaft', '']
    kd, rd = R['shaft']['keyed Ø14 turned'], R['shaft']['M14 rod + 5x8 pin']
    L += tbl(['Criterion', 'Keyed Ø14 turned 1.4404 +C700', 'M14 A2-70 rod + 5x8 pin'],
             [('Net bending / torsion modulus (mm³)', f'{kd["Z"]*1e9:.1f} / {kd["W"]*1e9:.0f}', f'{rd["Z"]*1e9:.1f} / {rd["W"]*1e9:.0f}'),
              (f'Static SF at gearbox peak {PEAK:g} N·m', g(kd['sf_peak'], 3), g(rd['sf_peak'], 3)), (f'Static SF at rated {RATED:g} N·m', g(kd['sf_rated'], 3), g(rd['sf_rated'], 3)),
              ('Fatigue SF at the operating load (Kf keyway 1.8/1.6; thread 2.8)', g(kd['se'] / kd['sig'], 3), g(rd['se'] / rd['sig'], 3)),
              ('Fit and play', 'H7/g6 seat, P9 key: slack ~0.16 deg at the output', 'thread and pin hole: larger slack, pin shear '
               f'{PEAK / (I["rod_d"] / 2) / (2 * math.pi / 4 * I["pin_d"] ** 2) / 1e6:.0f} MPa at peak (MEASURE the pin steel)'),
              ('Replacement', 'turn one shaft, press fit, keys are standard', 'cheapest and field-replaceable (Mk5 choice)')])
    L += ['**Decision: turned keyed shaft** (higher margin at the gearbox peak and a defined fit). The M14 rod is acceptable only with a torque limit '
          f'<= {RATED:g} N·m (rated, not peak) and an inspection of the roll-pin holes. Keep the M14 rod as the low-cost fallback.', '']
    w, gd = R['wg30'], R['wg30']['gear']
    L += ['## 14. LSR-WG30: our own worm gearbox (phase 7)', '']
    L += [f'Drop-in for the NMRV030 (same faces, Ø14 keyed hollow output, Ø55 boss, NEMA23 flange, 80:1, same envelope); source in the head: **{PR.GEARBOX_SOURCE}**. '
          f'Rows of this section gate `--check` only when `GEARBOX_SOURCE = lsr_wg30`; the self-locking row always gates. All allowables are VERIFY (gear maker, catalogue).', '']
    L += tbl(['Item', 'Value', 'Tag'], [
        ('Gear set', f'z1 = {PR.WG30["z1"]}, z2 = {PR.WG30["z2"]}, m = {PR.WG30["m"]}, q = {PR.WG30["q"]:g}, alpha_n = {PR.WG30["alpha_n"]:g} deg', 'PARAMETRIC'),
        ('Pitch diameters', f'worm {gd["d1"]:g}, wheel {gd["d2"]:g}; centre a = (d1 + d2) / 2 = {gd["a"]:g} mm = NMRV030 centre', 'a = 30 fixed by the NEMA23 flange axis'),
        ('Lead angle, lead', f'{gd["gamma"]:.3f} deg, {gd["lead"]:.3f} mm per turn', 'tan g = z1 / q'),
        ('Tip / root', f'worm Ø{gd["tip1"]:g} / Ø{gd["root1"]:g}, wheel Ø{gd["tip2"]:g} / Ø{gd["root2"]:g}, wheel width {PR.WG30["b2"]:g}', 'PARAMETRIC'),
        ('Self-locking factor, mu 0.05 / 0.10', f'{GBX.lock(0.05):.2f} / {GBX.lock(0.10):.2f} (need >= {I["lock_min_dyn"]} with the dynamic value)', 'VERIFY mu'),
        ('Efficiency, mu 0.05 / 0.10', f'{w["eta_r"]:.3f} / {w["eta_h"]:.3f} (NMRV030 value used above: {ETA})', 'VERIFY'),
        ('Motor torque at the output with this efficiency', f'{w["avail"]:.1f} N·m vs {w["t_op"]:.1f} N·m required', 'MEASURE the motor curve'),
        ('Wheel torque limits (bending fatigue / bending static / wear)', f'{w["T"]["fat"]:.2f} / {w["T"]["stat"]:.2f} / {w["T"]["wear"]:.2f} N·m', 'Lewis Y = 0.437, VERIFY'),
        ('Reference: NMRV030 rating / peak', f'{RATED:g} / {PEAK:g} N·m', 'DATASHEET, VERIFY'),
        ('Survival torque / mesh forces (mu 0.10)', f'{w["t_surv"]:.1f} N·m: wheel tangential {w["f"]["ft2"]:.0f} N, radial {w["f"]["fr"]:.0f} N, worm tangential {w["f"]["ft1"]:.0f} N', 'calc'),
        ('Bearing P0 wheel / worm (per bearing)', f'{w["p0_w"]:.0f} / {w["p0_o"]:.0f} N vs C0/2 {PR.WG30["wheel_brg"]["C0"] / 2:.0f} / {PR.WG30["worm_brg"]["C0"] / 2:.0f} N', 'VERIFY C0'),
        ('Housing seat ring stress', f'{w["sig_h"]:.1f} MPa vs A356 yield {PR.WG30["a356_yield"]:g} MPa (wall {w["wall"]:g} mm)', 'VERIFY'),
        ('Heat at the worst continuous operating point', f'{w["loss"]:.1f} W loss; {w["dt_cont"]:.0f} K rise continuous, {w["dt_duty"]:.0f} K at the satellite duty ({PR.WG30["duty"]:.0%})', 'PARAMETRIC duty')])
    L += [f'**Verdict.** A single-stage 80:1 worm at a = {gd["a"]:g} mm with the only standard module that fits (m = {PR.WG30["m"]}) carries about {w["T"]["fat"]:.1f} N·m (bending, fatigue) '
          f'and {w["T"]["wear"]:.1f} N·m (wear), against the {RATED:g} N·m rating of the bought NMRV030: roughly {RATED / w["T"]["fat"]:.0f} times short. Capacity grows with the cube of the centre distance; '
          f'parity needs a ≈ {w["a_eq"]:.0f} mm (an NMRV050-class envelope, heavier and dearer). A two-stage or coaxial pre-stage cannot fit inside the NMRV030 envelope because the NEMA23 flange axis '
          f'is the worm axis. The geometry, patterns, bearings and interfaces are complete and drop-in, but with these gears the **LSR-WG30 is an option for light duty (holding at stand-still with a '
          f'lower wind survival, or a different gear set), not a replacement for the NMRV030 at the loads of this head: keep the bought NMRV030.** The cost comparison is in [LSR2_MATERIALS](LSR2_MATERIALS.md).', '']
    return '\n'.join(L)


def inputs_md():
    L = ['# LSR-2 input data and open decisions', '',
         'Generated by `python calc/lsr2_sizing.py` from `cad/lsr2/inputs.py` (single source). Do not edit by hand. '
         'DATASHEET = published by a maker or a standard; MEASURE = needs a caliper, scale or bench test; PARAMETRIC = our own choice, editable.', '']
    groups = []
    for r in IN.ROWS:
        if r[0] not in groups:
            groups.append(r[0])
    for gname in groups:
        L += [f'## {gname}', '']
        L += tbl(['Key', 'Value', 'Unit', 'Tag', 'Note'], [(f'`{k}`', str(v).replace('|', '/'), u, t, n.replace('|', '/')) for gg, k, v, u, t, n in IN.ROWS if gg == gname])
    L += ['## Head items that rotate with AZ (not EL)', '']
    L += tbl(['Item', 'Mass kg', 'x, y, z m', 'Tag', 'Note'], [(n, g(m, 3), f'{x:g}, {y:g}, {z:g}', t, nt) for n, m, x, y, z, t, nt in IN.HEAD])
    L += ['## Open decisions', ''] + [f'{i + 1}. {d}' for i, d in enumerate(IN.OPEN_DECISIONS)] + ['']
    return '\n'.join(L)


# ---- Self-test ------------------------------------------------------------------------------------------------------------------
def firmware_profile():
    p = os.path.join(ROOT, 'firmware', 'src', 'core.cpp')
    if not os.path.exists(p):
        return None
    m = re.search(r'\{"LSR-2",(.*?)\}', open(p, encoding='utf-8').read())
    return [float(x) for x in re.findall(r'[-\d.]+(?=f)', m.group(1))] if m else None


def self_test():
    # q(60 km/h) = 0.5 * 1.225 * (60/3.6)^2 = 0.6125 * 277.78 = 170.1 Pa
    assert abs(q_dyn(60) - 170.1) < 0.1, q_dyn(60)
    # step rate at 12 deg/s: 12/360 rev/s * 80 * 200 * 2 = 1066.7 steps/s
    assert abs(12 / 360 * RATIO * PR.NEMA23['steps_rev'] * PR.MICROSTEP - 1066.67) < 0.01
    # mast Ø60.3 x 3.6: I = pi/64 (0.0603^4 - 0.0531^4) = 0.049087 * 5.2709e-6 = 2.587e-7 m^4
    assert abs(mast()['I'] - 2.587e-7) < 1e-10, mast()['I']
    # keyed Ø14 5x5 (t1 3.0): Z_net = pi*14^3/32 - 5*3*11^2/(2*14) = 269.39 - 64.82 = 204.57 mm^3
    assert abs(keyed_sections()[0] * 1e9 - 204.6) < 0.1
    # lock factor, dynamic: 0.05 / cos20 / tan2.3 = 0.05321 / 0.040157 = 1.325
    assert abs(lock_factor(0.05) - 1.325) < 0.005 and abs(lock_factor(0.10) - 2.650) < 0.01
    # motor curve at 160 rpm: 2.4 - 0.6 * (2.4 - 2.0) = 2.16 N·m
    assert abs(motor_torque(160) - 2.16) < 1e-9
    # LSR-WG30: efficiency at mu 0.05 = 0.3192, so the motor gives 2.16 * 0.8 * 80 * 0.3192 = 44.1 N·m at the output; wheel bending limit 3.06 N·m
    GBX.self_test()
    assert abs(motor_torque(160) * 0.8 * 80 * GBX.eta(0.05) - 44.1) < 0.1 and abs(GBX.t_wheel_bend(50.0) - 3.059) < 2e-3
    # stop energy for I_total = 1 kg·m²: 0.5 * 1 * 0.20944^2 = 0.02193 J (vmax 12 deg/s)
    assert abs(stop(1.0 - J_R, 1.0)[0] - 0.02193) < 1e-4
    # life: (10)^3 * 1e6 revs / (12 passes * 365 * 300/360 rev) = 1e9 / 3650 = 273973 years
    assert abs(life_years(10.0, 1.0, 300.0) - 273973.0) < 5.0
    # each counterweight balances its side exactly: gravity torque about EL is zero at any elevation
    for e in (0, 37, 90, 150):
        assert abs(G * sum(m * (a * math.cos(math.radians(e)) - h * math.sin(math.radians(e))) for _, m, a, y, h in MOV)) < 1e-9
    prof = firmware_profile()
    if prof:
        assert abs(prof[-4] - I['vmax_dps']) < 1e-6 and abs(prof[-2] - I['acc_dps2']) < 1e-6, prof


def main():
    self_test()
    R = evaluate()
    fails = [c for c in CHK if not c['opt'] and c['sf'] < c['tgt']]
    if '--check' in sys.argv:
        for c in fails:
            print(f'FAIL {c["sec"]}: {c["name"]} SF {c["sf"]:.2f} < {c["tgt"]:g}')
        print('lsr2_sizing: ' + ('self-test OK, all safety factors meet their target' if not fails else f'{len(fails)} check(s) below target'))
        sys.exit(1 if fails else 0)
    for name, text in (('LSR2_SIZING.md', report(R)), ('LSR2_INPUTS.md', inputs_md())):
        with open(os.path.join(ROOT, 'docs', name), 'w', encoding='utf-8', newline='\n') as f:
            f.write(text)
    print(f'lsr2_sizing: wrote docs/LSR2_SIZING.md and docs/LSR2_INPUTS.md; {len(fails)} check(s) below target')


if __name__ == '__main__':
    main()
