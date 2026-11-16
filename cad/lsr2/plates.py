"""LSR-2 head: CNC plate definitions, layout envelopes and a minimal DXF writer.

Pure Python (no FreeCAD needed) so the layout and DXF can be tested anywhere; build.py turns these
definitions into solids under freecadcmd. Head frame (mm): AZ axis = Z through the origin, top face of
the base plate at z=0, EL axis along Y at x=0, z=EL_Z. Our own geometry, sized from params.py.
"""
import math
import params as P

G = P.NMRV030_GEO
T_BASE, T_SIDE, T_TOP, T_SPACER = 8.0, 8.0, 6.0, 8.0
L = 370.0                      # head length along X (AZ motor +X, EL motor -X: balances the head)
Y_IN = 65.0                    # inner face of each side plate, |y|
H_SIDE = 185.0                 # side plate height above the base plate
Z_EL_FOOT = 72.0               # EL gearbox foot face (clears the AZ stack top at T_SPACER + 56 = 64)
EL_Z = Z_EL_FOOT + G['out_from_foot']
FIX_X = (-150.0, -60.0, 60.0, 150.0)   # plate-to-plate M6 screws (into tapped plate edges)
FIX_Y = Y_IN + T_SIDE / 2


def face_holes(cx, cy):
    """NMRV output-face pattern: 4 holes on the PCD at 0/90/180/270 deg (catalogue drawing)."""
    r = G['face_pcd'] / 2
    return [(cx + r, cy, 6.6), (cx - r, cy, 6.6), (cx, cy + r, 6.6), (cx, cy - r, 6.6)]


def pcd(cx, cy, d_pcd, n, d, start=0.0):
    return [(cx + d_pcd / 2 * math.cos(math.radians(start + 360 * k / n)),
             cy + d_pcd / 2 * math.sin(math.radians(start + 360 * k / n)), d) for k in range(n)]


# Each plate: size (u, v) in its own 2D frame, thickness, holes [(u, v, d)], light [(u, v, d)] lightening
# holes, notes, and its placement: 'xy' plates lie flat (u=X, v=Y) at z0; 'xz' plates stand up
# (u=X, v=Z above z0, default 0) at y0 (their -Y face). 'xy' hole v is centred on the plate, 'xz' v starts at its bottom edge.
PLATES = {
    'base': dict(size=(L, 2 * (Y_IN + T_SIDE + 5.0)), t=T_BASE, frame='xy', z0=-T_BASE,
                 holes=[(0, 0, G['pilot_clear_d'])] + face_holes(0, 0) + pcd(0, 0, 110, 6, 6.6, 30)
                 + [(x, s * FIX_Y, 6.6) for x in FIX_X for s in (1, -1)],
                 light=[(-115.0, 0.0, 90.0), (115.0, 0.0, 90.0)],
                 notes=['AZ gearbox: 4x M6x25 through spacer', 'PCD110 6x6.6: cast AZ housing (phase 3)',
                        'Side plates: 8x M6x20 from below']),
    'spacer': dict(size=(80.0, 80.0), t=T_SPACER, frame='xy', z0=0.0, centred=True,
                   holes=[(0, 0, G['pilot_clear_d'])] + face_holes(0, 0),
                   notes=['Lifts the AZ gearbox so the NEMA23 clears the base plate']),
    'spacer_el': dict(size=(80.0, 80.0), t=T_SPACER, frame='xz', y0=Y_IN - T_SPACER, z0=EL_Z - 40.0,
                      holes=[(0, 40.0, G['pilot_clear_d'])] + face_holes(0, 40.0),
                      notes=['Between the EL gearbox output face and side_a: the NEMA23 (56.4) is wider than the gearbox (56)']),
    'side_a': dict(size=(L, H_SIDE), t=T_SIDE, frame='xz', y0=Y_IN,
                   holes=[(0, EL_Z, G['pilot_clear_d'])] + face_holes(0, EL_Z),
                   light=[(-105.0, EL_Z, 70.0), (105.0, EL_Z, 70.0)],
                   notes=['EL gearbox output face inside: 4x M6x20', 'Edges: 4x M6 tapped 15 deep top and bottom at x=+-60, +-150']),
    'side_b': dict(size=(L, H_SIDE), t=T_SIDE, frame='xz', y0=-Y_IN - T_SIDE,
                   holes=[(0, EL_Z, 32.0), (150.0, 40.0, 20.5)],
                   light=[(-100.0, EL_Z, 70.0), (100.0, EL_Z, 70.0)],
                   notes=['Bore 32 H7 for 6201-2RS (finish on a mill: router tolerance is not enough)',
                          'M20 cable gland at x=150', 'Edges: 4x M6 tapped 15 deep top and bottom at x=+-60, +-150']),
    'top': dict(size=(L, 2 * (Y_IN + T_SIDE + 5.0)), t=T_TOP, frame='xy', z0=H_SIDE,
                holes=[(x, s * FIX_Y, 6.6) for x in FIX_X for s in (1, -1)],
                notes=['8x M6x16 into the side plate top edges']),
}

# Bought parts as boxes (x0, x1, y0, y1, z0, z1) for the interference check.
_el_y0 = Y_IN - T_SPACER - G['out_width']      # EL gearbox sits behind spacer_el
_az_worm_y = -G['out_from_foot'] + G['out_from_foot'] + 30.0      # worm 30 from output along 'n'
_az_z0 = T_SPACER
_az_worm_z = _az_z0 + G['out_width'] / 2
ENVELOPES = {
    'az_gearbox': (-G['worm_from_end'], G['worm_len_flange'] - G['worm_from_end'],
                   -G['out_from_foot'], G['n_len'] - G['out_from_foot'], _az_z0, _az_z0 + G['out_width']),
    'az_motor': (G['worm_len_flange'] - G['worm_from_end'], G['worm_len_flange'] - G['worm_from_end'] + P.NEMA23['length'],
                 _az_worm_y - P.NEMA23['face'] / 2, _az_worm_y + P.NEMA23['face'] / 2,
                 _az_worm_z - P.NEMA23['face'] / 2, _az_worm_z + P.NEMA23['face'] / 2),
    'el_gearbox': (-(G['worm_len_flange'] - G['worm_from_end']), G['worm_from_end'],
                   _el_y0, Y_IN - T_SPACER, Z_EL_FOOT, Z_EL_FOOT + G['n_len']),
    'el_motor': (-(G['worm_len_flange'] - G['worm_from_end']) - P.NEMA23['length'], -(G['worm_len_flange'] - G['worm_from_end']),
                 _el_y0 + G['out_width'] / 2 - P.NEMA23['face'] / 2, _el_y0 + G['out_width'] / 2 + P.NEMA23['face'] / 2,
                 EL_Z + 30.0 - P.NEMA23['face'] / 2, EL_Z + 30.0 + P.NEMA23['face'] / 2),
}


def plate_box(name):
    """World-space box of a plate: (x0, x1, y0, y1, z0, z1)."""
    p = PLATES[name]
    u, v = p['size']
    if p['frame'] == 'xy':
        return (-u / 2, u / 2, -v / 2, v / 2, p['z0'], p['z0'] + p['t'])
    z0 = p.get('z0', 0.0)
    return (-u / 2, u / 2, p['y0'], p['y0'] + p['t'], z0, z0 + v)


def cutouts(p):
    """All through-cuts of a plate: functional holes then lightening holes, [(u, v, d)]."""
    return p['holes'] + p.get('light', [])


def area_mm2(name):
    p = PLATES[name]
    return p['size'][0] * p['size'][1] - sum(math.pi * d * d / 4 for _, _, d in cutouts(p))


def mass_g(name):
    return area_mm2(name) * PLATES[name]['t'] * P.ALU_PLATE_G_CM3 * 1e-3


def box_overlap(a, b, tol=0.01):
    return all(min(a[2 * i + 1], b[2 * i + 1]) - max(a[2 * i], b[2 * i]) > tol for i in range(3))


def write_dxf(name, path):
    """R12 DXF of one plate in its own frame, origin at the plate's lower-left corner (CAM friendly)."""
    p = PLATES[name]
    u, v = p['size']
    ou = u / 2
    ov = v / 2 if p['frame'] == 'xy' else 0.0
    ents = []
    corners = [(0, 0), (u, 0), (u, v), (0, v)]
    for (a, b), (c, d) in zip(corners, corners[1:] + corners[:1]):
        ents += ['0', 'LINE', '8', 'CUT', '10', f'{a:.3f}', '20', f'{b:.3f}', '11', f'{c:.3f}', '21', f'{d:.3f}']
    for (hu, hv, d) in cutouts(p):
        ents += ['0', 'CIRCLE', '8', 'CUT', '10', f'{hu + ou:.3f}', '20', f'{hv + ov:.3f}', '40', f'{d / 2:.3f}']
    for i, note in enumerate([f'LSR-2 {name} - {P.PLATE["alloy"]} {p["t"]:g} mm - BricoHams'] + p['notes']):
        ents += ['0', 'TEXT', '8', 'NOTES', '10', '0', '20', f'{-10 - 6 * i:.1f}', '40', '4', '1', note]
    with open(path, 'w', encoding='ascii', errors='replace') as fh:
        fh.write('\n'.join(['0', 'SECTION', '2', 'ENTITIES'] + ents + ['0', 'ENDSEC', '0', 'EOF']) + '\n')


def self_test():
    for name, p in PLATES.items():
        u, v = p['size']
        ou, ov = u / 2, (v / 2 if p['frame'] == 'xy' else 0.0)
        for (hu, hv, d) in p['holes']:
            assert d / 2 + 3.0 <= hu + ou <= u - d / 2 - 3.0 and d / 2 + 3.0 <= hv + ov <= v - d / 2 - 3.0, (name, hu, hv)
        hs = p['holes']
        for i in range(len(hs)):
            for j in range(i + 1, len(hs)):
                gap = math.dist(hs[i][:2], hs[j][:2]) - (hs[i][2] + hs[j][2]) / 2
                assert gap >= 1.5, (name, hs[i], hs[j], gap)   # minimum web between holes
    assert not PLATES['top'].get('light'), 'no lightening in the 6 mm top plate'
    web, keep = P.LIGHTEN['min_web'], P.LIGHTEN['keep_out']
    for name, p in PLATES.items():
        u, v = p['size']
        ov = v / 2 if p['frame'] == 'xy' else 0.0
        light = p.get('light', [])
        # tapped edge screws of the side plates count as fixing holes (M6 tap drill 5)
        fixed = [(h, w, d) for h, w, d in p['holes']]
        if p['frame'] == 'xz' and name.startswith('side'):
            fixed += [(x, z, 5.0) for x in FIX_X for z in (0.0, v)]
        for i, (a, b, d) in enumerate(light):
            assert d / 2 + web <= a + u / 2 and a + u / 2 <= u - d / 2 - web, (name, 'edge u', a)
            assert d / 2 + web <= b + ov and b + ov <= v - d / 2 - web, (name, 'edge v', b)
            for (c, e, dd) in fixed:
                assert math.dist((a, b), (c, e)) - (d + dd) / 2 >= keep, (name, 'keep-out', (a, b), (c, e))
            for (c, e, dd) in light[i + 1:]:
                assert math.dist((a, b), (c, e)) - (d + dd) / 2 >= web, (name, 'web', (a, b), (c, e))
    new = sum(mass_g(n) for n in PLATES)
    base = sum(PLATES[n]['size'][0] * PLATES[n]['size'][1] * t for n, t in
               [('base', 10.0), ('side_a', 10.0), ('side_b', 10.0), ('top', T_TOP), ('spacer', T_SPACER)]) * P.ALU_PLATE_G_CM3 * 1e-3
    print(f'plate mass: {new:.0f} g (lightened 8 mm) vs {base:.0f} g (unlightened 10 mm baseline)')
    assert new < base, (new, base)
    names = list(ENVELOPES)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            assert not box_overlap(ENVELOPES[a], ENVELOPES[b]), (a, b)
        for pl in PLATES:
            assert not box_overlap(ENVELOPES[a], plate_box(pl)), (a, pl)
    assert EL_Z + 30.0 + P.NEMA23['face'] / 2 < H_SIDE - 5, 'EL motor must clear the top plate'
    assert ENVELOPES['az_motor'][1] < L / 2 and -ENVELOPES['el_motor'][0] < L / 2, 'motors inside the head'


if __name__ == '__main__':
    self_test()
    print('plates self-test OK; EL axis at z =', EL_Z)
