"""LSR-2 phase 7: own worm gearbox LSR-WG30, a drop-in for the bought NMRV030 (mm, N, N·m, deg).

Drop-in = same output faces (PCD 65, 4 x M6), same Ø14 keyed hollow output, hub length 63, Ø55 boss, NEMA23 input flange, 80:1, same envelope
as params.NMRV030_GEO. Only the inside differs (see docs/ARCHITECTURE.md §8): A356 housing in two halves split on the wheel mid-plane,
bought worm (hardened steel) + CuSn12 wheel, 2 x 61905 on the wheel carrier, 2 x 6003 on the worm, lip seals on the output and the input.
Local frame = bought_parts.nmrv030(): output axis Z through the origin, faces z 0..56, worm axis X at y = 30, z = 28, input flange face x = 55.
Pure Python: gear data, forces, efficiency, strength (self_test, used by calc/lsr2_sizing.py). FreeCAD builders import lazily.
Tooth form is NOT modelled (visual solids use the root cylinders). Every catalogue number: VERIFY (params.WG30 carries the tags).
Run: python gearbox.py (self-test); build.py calls build() under freecadcmd.
"""
import math
import os
import params as P

W = P.WG30
NG = P.NMRV030_GEO
AY, ZS = P.GEARBOX['NMRV030']['centre'], W['split_z']      # worm axis y (= centre distance a) and the joint plane z (= worm axis z)
HALVES = ('gearbox_half_low', 'gearbox_half_up')
# Internal cuts (finished sizes, PARAMETRIC): (radius, from, to) about the output axis z; (radius, from, to, machined) about the worm axis x
WHEEL_CUTS = ((21.0, -3.5, 12.5), (19.5, 12.5, 14.0), (24.0, 14.0, 42.0), (19.5, 42.0, 43.5), (21.0, 43.5, 59.5))     # seat, relief, pocket, relief, seat
WORM_CUTS = ((17.5, -36.0, -26.0, 1), (13.0, -26.0, 26.0, 0), (17.5, 26.0, 36.0, 1), (15.0, 36.0, 43.0, 1), (14.0, 43.0, 53.0, 1), (19.3, 53.0, 55.0, 1))
FLANGE_X = NG['worm_len_flange'] - NG['worm_from_end']      # 55: input flange face


# --- gear data (pure Python) ----------------------------------------------------------------------------------------------------------
def gear():
    m, q, z1, z2 = W['m'], W['q'], W['z1'], W['z2']
    d1, d2 = m * q, m * z2
    return dict(d1=d1, d2=d2, a=(d1 + d2) / 2, ratio=z2 / z1, gamma=math.degrees(math.atan2(z1, q)), lead=math.pi * m * z1,
                tip1=d1 + 2 * m, root1=d1 - 2.4 * m, tip2=d2 + 2 * m, root2=d2 - 2.4 * m, q_for_a=2 * AY / m - z2)


def eta(mu):
    """Worm drive efficiency (worm drives): (cos an - mu tan g) / (cos an + mu / tan g)."""
    an, g = math.radians(W['alpha_n']), math.atan2(W['z1'], W['q'])
    return (math.cos(an) - mu * math.tan(g)) / (math.cos(an) + mu / math.tan(g))


def lock(mu):
    """Self-locking factor mu / cos(an) / tan(g), same convention as lsr2_sizing.lock_factor (>= 1.25 required with the dynamic mu)."""
    return mu / math.cos(math.radians(W['alpha_n'])) / math.tan(math.atan2(W['z1'], W['q']))


def t_wheel_bend(sigma):
    """Wheel torque at tooth bending stress sigma (MPa): Lewis Ft = sigma b m Y (Y includes pi), T = Ft d2 / 2."""
    return sigma * W['b2'] * W['m'] * W['y_lewis'] * gear()['d2'] / 2 / 1000.0


def t_wheel_wear():
    """Wheel torque at the surface-durability limit Ft = Kw d2 b (bronze on hardened worm, K in N/mm2)."""
    d2 = gear()['d2']
    return W['k_wear'] * d2 * W['b2'] * d2 / 2 / 1000.0


def forces(t2, mu):
    """Mesh forces (N) at wheel torque t2: tangential on the wheel (= axial on the worm), radial, worm tangential, wheel axial (= worm tangential)."""
    an, g = math.radians(W['alpha_n']), math.atan2(W['z1'], W['q'])
    ft2 = 2000.0 * t2 / gear()['d2']
    fn = ft2 / (math.cos(an) * math.cos(g) - mu * math.sin(g))
    return dict(ft2=ft2, fr=fn * math.sin(an), ft1=fn * (math.cos(an) * math.sin(g) + mu * math.cos(g)))


def a_equal_rating():
    """Centre distance (mm) that would carry the NMRV030 rating, heuristic capacity ~ a^3 (VERIFY with the gear maker)."""
    return AY * (P.GEARBOX['NMRV030']['m2_rated'] / t_wheel_bend(W['sigma_f'])) ** (1.0 / 3.0)


def self_test():
    g = gear()
    assert abs(g['a'] - AY) < 1e-9 and abs(g['q_for_a'] - W['q']) < 1e-9 and g['ratio'] == 80
    assert abs(g['gamma'] - 1.4325) < 1e-3 and abs(g['lead'] - 1.5708) < 1e-3
    # eta(0.05) = (0.93969 - 0.05 * 0.025) / (0.93969 + 0.05 / 0.025) = 0.93844 / 2.93969 = 0.3192
    assert abs(eta(0.05) - 0.3192) < 1e-3 and abs(eta(0.10) - 0.1897) < 1e-3
    # lock(0.05) = 0.05 / 0.93969 / 0.025 = 2.128
    assert abs(lock(0.05) - 2.128) < 2e-3 and lock(W['mu_run']) >= 1.25
    # Lewis fatigue: 50 * 14 * 0.5 * 0.437 = 152.95 N at r = 20 mm -> 3.059 N·m; wear 0.7 * 40 * 14 = 392 N -> 7.84 N·m
    assert abs(t_wheel_bend(50.0) - 3.059) < 2e-3 and abs(t_wheel_wear() - 7.84) < 5e-3
    f = forces(10.0, 0.05)
    assert abs(f['ft2'] - 500.0) < 1e-9 and f['fr'] > 0 and f['ft1'] > 0
    assert W['m'] in (0.4, 0.5, 0.6, 0.8, 1.0, 1.25, 1.5, 2.0) and W['b2'] <= 0.75 * g['d1']
    assert 40.0 < a_equal_rating() < 70.0
    print('gearbox LSR-WG30 self-test OK (a %.1f mm, lead %.2f deg, eta %.2f at mu 0.05, bending limit %.2f N.m)' % (g['a'], g['gamma'], eta(0.05), t_wheel_bend(W['sigma_f'])))


# --- FreeCAD solids (local frame) -------------------------------------------------------------------------------------------------------
def _G():
    import geom
    return geom


def _cz(r, z0, z1):
    return _G().cyl(r, z1 - z0, (0, 0, z0), (0, 0, 1))


def _cx(r, x0, x1):
    return _G().cyl(r, x1 - x0, (x0, AY, ZS), (1, 0, 0))


def exterior():
    """Outer envelope: Ø80 face disc (inside the NMRV030 body), worm tube, transition and NEMA flange (as the bought part), Ø55 bosses, fins under the worm."""
    G = _G()
    ow, wz = NG['out_width'], ZS
    parts = [_cz(W['disc_r'], 0, ow), _cx(22.0, -NG['worm_from_end'], 40.0), G.box(40, 49, AY - 23, AY + 23, wz - 23, wz + 23),
             G.box(49, FLANGE_X, AY - 28.5, AY + 28.5, wz - 28.5, wz + 28.5), _cz(W['boss_r'], -3.5, 0.0), _cz(W['boss_r'], ow, ow + 3.5)]
    parts += [G.box(x - W['fin_t'] / 2, x + W['fin_t'] / 2, 40, 57, 9, ow - 9) for x in W['fin_xs']]
    return G.fuse(parts)


def cuts():
    """Finished internal cuts of both halves: {'wheel', 'worm', 'nema', 'faces'} lists of solids."""
    G = _G()
    h, r = P.NEMA23['hole_square'] / 2, NG['face_pcd'] / 2
    return dict(wheel=[_cz(rr, z0, z1) for rr, z0, z1 in WHEEL_CUTS], worm=[_cx(rr, x0, x1) for rr, x0, x1, _ in WORM_CUTS],
                nema=[G.cyl(P.NEMA23['hole_d'] / 2, 6.0, (49, AY + sy * h, ZS + sz * h), (1, 0, 0)) for sy in (-1, 1) for sz in (-1, 1)],
                faces=[G.cyl(3.0, NG['face_hole_depth'], (hx, hy, z0), (0, 0, 1)) for hx, hy in ((r, 0), (-r, 0), (0, r), (0, -r)) for z0 in (0.0, NG['out_width'] - NG['face_hole_depth'])])


def _half_box(low, pad=0.0):
    z0, z1 = (-10.0, ZS + pad) if low else (ZS - pad, 70.0)
    return _G().box(-60, 70, -60, 90, z0, z1)


def _groove():
    """Sealant / O-ring track in the joint face of the lower half: a ring 1.0..2.5 mm outside the sealed volume
    (wheel pocket + a strip +/-17.5 around the worm axis from the free-end seat to the input seal, a slight over-estimate of the real footprint)."""
    import Part
    from FreeCAD import Vector as V
    G = _G()
    gv = W['groove']
    fp = G.fuse([_cz(WHEEL_CUTS[2][0], ZS - 1.0, ZS), G.box(WORM_CUTS[0][1], WORM_CUTS[3][2], AY - 17.5, AY + 17.5, ZS - 1.0, ZS)])
    face = Part.makeFace(fp.slice(V(0, 0, 1), ZS - 0.5), 'Part::FaceMakerBullseye')
    ring = face.makeOffset2D(gv['outer']).cut(face.makeOffset2D(gv['land']))
    ring.translate(V(0, 0, 0.5))
    groove = ring.extrude(V(0, 0, -gv['depth']))
    return groove if groove.Volume > 0 else groove.reversed()          # the slice face may come out with a downward normal: keep the cutting tool a positive solid


def _joint(low):
    """M5 screws (tapped Ø4.2 in the lower half, clearance + counterbore in the upper), dowel holes Ø5 and the lower-half groove."""
    G = _G()
    out = []
    for x, y in W['screw_pos']:
        out.append(G.cyl(2.1, 12.0, (x, y, ZS - 12.0), (0, 0, 1)) if low else
                   G.fuse([G.cyl(2.75, 30.0, (x, y, ZS), (0, 0, 1)), G.cyl(4.75, 6.0, (x, y, NG['out_width'] - 5.5), (0, 0, 1))]))
    for x, y in W['dowel_pos']:
        out.append(G.cyl(W['dowel_d'] / 2, W['dowel_depth'], (x, y, ZS - W['dowel_depth'] if low else ZS), (0, 0, 1)))
    if low:
        out.append(_groove())
    return out


def finished(low, ext=None):
    """Finished housing half (low = z <= 28, else z >= 28) in the local frame."""
    c = cuts()
    return (ext or exterior()).common(_half_box(low)).cut(_G().fuse(c['wheel'] + c['worm'] + c['nema'] + c['faces'] + _joint(low)))


def _ring(axis_x, r0, r1, a, b):
    f = (lambda r: _cx(r, a, b)) if axis_x else (lambda r: _cz(r, a, b))
    return f(r1).cut(f(r0))


def internals():
    """Visual wheel (carrier tube + root-cylinder rim, Ø14 bore with keyway), worm, bearing rings and lip seals (no tooth form)."""
    G = _G()
    wb, ob = W['wheel_brg'], W['worm_brg']
    wheel = G.fuse([_cz(12.5, -3.5, 59.5), _cz(gear()['root2'] / 2, 21.0, 35.0)]).cut(G.fuse([_cz(7.0, -5.0, 65.0), G.box(-2.5, 2.5, 0.0, 9.3, -5.0, 65.0)]))
    worm = G.fuse([_cx(8.5, -36.0, 52.0), _cx(gear()['root1'] / 2, -26.0, 26.0), _cx(gear()['tip1'] / 2, -14.0, 14.0)]).cut(_cx(5.5, 28.0, 52.0))
    rw, ro = wb['d'] / 2, wb['D'] / 2
    rings = [_ring(False, rw, ro, 3.5, 12.5), _ring(False, rw, ro, 43.5, 52.5), _ring(False, rw, ro, -3.5, 3.5), _ring(False, rw, ro, 52.5, 59.5),
             _ring(True, ob['d'] / 2, ob['D'] / 2, -36.0, -26.0), _ring(True, ob['d'] / 2, ob['D'] / 2, 26.0, 36.0), _ring(True, W['seal_in']['d'] / 2, W['seal_in']['D'] / 2, 36.0, 43.0)]
    return dict(wheel=wheel, worm=worm, bearings=G.fuse(rings))


def assembly():
    """{'half_low', 'half_up', 'wheel', 'worm', 'bearings'} local-frame solids (the build report and the renders use these names)."""
    ext = exterior()
    return dict(half_low=finished(True, ext), half_up=finished(False, ext), **internals())


# --- cast specs (route_a.spec dispatch), core boxes, build ------------------------------------------------------------------------------
def cast_spec(name, stock, plen):
    """Route A spec of one half. Plane: z = joint +/- stock (the joint pad is cast on, machined to z = 28). Cavity: wheel pocket (core extends past the plane).
    Holes (cast-in cores): wheel bore and the stepped worm bore, machined seats r - stock; the cores protrude plen at the open ends."""
    G = _G()
    low = name.endswith('low')
    ext, c = exterior(), cuts()
    hb = _half_box(low)
    pocket = c['wheel'][2]
    blank = ext.common(hb).cut(pocket)
    slab = ext.common(G.box(-60, 70, -60, 90, *((ZS, ZS + stock) if low else (ZS - stock, ZS)))).cut(pocket)      # joint-face pad, machined to z = 28
    ow, bh = NG['out_width'], 3.5
    face = (-stock, 0.0) if low else (ow, ow + stock)                                                               # mounting face outside the boss
    boss = (-bh - stock, -bh) if low else (ow + bh, ow + bh + stock)                                                 # boss end face
    pads = [slab, G.cut(_cz(W['disc_r'], *face), [_cz(W['boss_r'], -bh - 1.0, ow + bh + 1.0)]), _cz(W['boss_r'], *boss),
            G.box(FLANGE_X, FLANGE_X + stock, AY - 28.5, AY + 28.5, ZS - 28.5, ZS + 28.5).common(hb)]
    zl, zh = (boss[0] - plen, ZS + stock + plen) if low else (ZS - stock - plen, boss[1] + plen)
    x_end, worm = FLANGE_X + stock + plen, []
    for k, (r, x0, x1, mach) in enumerate(WORM_CUTS[:-1]):
        s = stock if mach else 0.0
        worm.append(_cx(r - s, x0 + (stock if k == 0 else 0.0), x_end if k == len(WORM_CUTS) - 2 else x1))
    return dict(blank=blank, finished=finished(low, ext), plane=(2, ZS + stock if low else ZS - stock), sides=(-1,) if low else (1,),
                pads=pads, holes=[_cz(WHEEL_CUTS[0][0] - stock, zl, zh)] + worm, cavity=[pocket], keep=[], prints=lambda cl: [])


def build(outdir, stl_dir):
    """Cast outputs of both halves + core boxes + flat visual STLs of the local-frame solids. Returns the report entry (source, halves, areas)."""
    import route_a as RA
    G = _G()
    os.makedirs(stl_dir, exist_ok=True)
    out = dict(source=P.GEARBOX_SOURCE, halves={}, wg30=dict(gear=gear(), eta_run=eta(W['mu_run']), eta_hold=eta(W['mu_hold'])))
    for n in HALVES:
        out['halves'][n] = RA.build_part(n, outdir)
        p = RA.cast_params(n)
        cr = RA.core(RA.spec(n, p['machining'], p['core_print']), p['core_clear'])
        bb = cr.BoundBox
        blk = G.box(bb.XMin - 15, bb.XMax + 15, bb.YMin - 15, bb.YMax + 15, bb.ZMin - 15, bb.ZMax + 15)
        out['halves'][n]['corebox_ok'] = RA._write_all(os.path.join(outdir, n + '_corebox'), RA.scaled(blk.cut(cr), p['shrink']), step=False)    # cut with the exact core, then scale: a boolean against the scaled (B-spline) core never finishes
    parts = assembly()
    for k, s in parts.items():
        s.exportStl(os.path.join(stl_dir, 'gearbox_%s.stl' % k))
    out['housing_area_cm2'] = (parts['half_low'].Area + parts['half_up'].Area) / 100.0
    out['internals_cm3'] = {k: parts[k].Volume / 1000.0 for k in ('wheel', 'worm', 'bearings')}
    return out


if __name__ == '__main__':
    self_test()
