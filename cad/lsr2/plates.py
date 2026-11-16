"""LSR-2 head (phase 6, two-block layout): CNC plate definitions, layout envelopes and a minimal DXF writer.

Pure Python (no FreeCAD needed) so the layout and DXF can be tested anywhere; build.py turns these
definitions into solids under freecadcmd. Head frame (mm): AZ axis = Z through the origin, top face of
the base plate at z=0, EL axis along Y at x=0, z=EL_Z. Our own geometry, sized from params.py.

Layout choice (like a photo of a compact worm rotator): both NMRV030 gearboxes have their worm axis along X and
both NEMA23 motors point +X, so the motors are parallel and point the same way. The AZ gearbox (output axis Z)
stands on the base plate; the EL gearbox (output axis Y) hangs with its output face A on the upright el_bracket
at the +Y edge of the base plate. Its face B carries the cast el_bearing_housing (two bearings, see cast_parts.py);
the 40x40 cross boom runs along +Y, coaxial with the EL axis, in the cast boom_socket keyed on the EL shaft.
"""
import math
import params as P

G = P.NMRV030_GEO
T_BASE = T_SPACER = T_BRACKET = 8.0
Y_BR0 = 61.0                          # el_bracket inner face: clears the PCD110 screw head at (0, 55) and the AZ block (y <= 57)
Y_EL_A = Y_BR0 + T_BRACKET            # EL gearbox output face A (on the bracket)
Y_EL_B = Y_EL_A + G['out_width']      # EL gearbox output face B (bearing housing)
Z_EL_FOOT = 0.0                       # EL gearbox foot plane = top face of the base plate
EL_Z = Z_EL_FOOT + G['out_from_foot']
BOOM_W, BOOM_H, BOOM_T = P.CROSS_BOOM
BRACKET_SCREW_X = (-42.0, -20.0, 20.0, 42.0)         # M6 from below into the bracket's tapped bottom edge, y = Y_BR0 + 4
AZ_COLLAR = (-14.0, 14.0, -14.0, 14.0, 68.0, 82.0)    # bought DIN 705 collar (Ø28 x 14) on the AZ shaft top, above the hub boss (67.5)


def face_holes(cx, cy):
    """NMRV output-face pattern: 4 holes on the PCD at 0/90/180/270 deg (catalogue drawing)."""
    r = G['face_pcd'] / 2
    return [(cx + r, cy, 6.6), (cx - r, cy, 6.6), (cx, cy + r, 6.6), (cx, cy - r, 6.6)]


def pcd(cx, cy, d_pcd, n, d, start=0.0):
    return [(cx + d_pcd / 2 * math.cos(math.radians(start + 360 * k / n)),
             cy + d_pcd / 2 * math.sin(math.radians(start + 360 * k / n)), d) for k in range(n)]


# Each plate: u, v = (min, max) world ranges in its 2D frame, w = world position of its -normal face, t thickness,
# holes [(u, v, d)] in WORLD coordinates (through cuts), taps [(u, d)] M6 tap-drills into its bottom edge, notes.
# 'xy' plates lie flat (u=X, v=Y, w=z0); 'xz' plates stand up (u=X, v=Z, w=y0). No lightening holes: the rule
# P.LIGHTEN (web 6, keep-out 20 from functional holes) leaves no room on any of these small plates.
CZ = EL_Z
PLATES = {
    'base': dict(u=(-55.0, 55.0), v=(-62.0, 72.0), w=-T_BASE, t=T_BASE, frame='xy',
                 holes=[(0, 0, G['pilot_clear_d'])] + face_holes(0, 0) + pcd(0, 0, 110, 6, 6.6, 30)
                 + [(x, Y_BR0 + T_BRACKET / 2, 6.6) for x in BRACKET_SCREW_X],
                 notes=['AZ gearbox: 4x M6x25 through spacer', 'PCD110 6x6.6: cast AZ housing (heads on top, M6x20)',
                        'el_bracket: 4x M6x20 from below into its tapped edge']),
    'spacer': dict(u=(-40.0, 40.0), v=(-40.0, 40.0), w=0.0, t=T_SPACER, frame='xy',
                   holes=[(0, 0, G['pilot_clear_d'])] + face_holes(0, 0),
                   notes=['Lifts the AZ gearbox so the NEMA23 clears the base plate']),
    'el_bracket': dict(u=(-48.0, 48.0), v=(0.0, 80.0), w=Y_BR0, t=T_BRACKET, frame='xz',
                       holes=[(0, EL_Z, G['pilot_clear_d'])] + face_holes(0, EL_Z),
                       taps=[(x, 5.0) for x in BRACKET_SCREW_X],
                       notes=['EL gearbox output face A: 4x M6x20', 'Bottom edge: 4x M6 tapped 15 deep at x=-42,-20,20,42 (thickness mid)',
                              'Joint tilt stiffness not calculated: proof-load (VERIFY)']),
}

# Bought parts as boxes (x0, x1, y0, y1, z0, z1) for the interference check.
WORM_X1 = G['worm_len_flange'] - G['worm_from_end']
_az_z0 = T_SPACER
_nz = P.NEMA23['face'] / 2
ENVELOPES = {
    'az_gearbox': (-G['worm_from_end'], WORM_X1, -G['out_from_foot'], G['n_len'] - G['out_from_foot'], _az_z0, _az_z0 + G['out_width']),
    'az_motor': (WORM_X1, WORM_X1 + P.NEMA23['length'], 30.0 - _nz, 30.0 + _nz,
                 _az_z0 + G['out_width'] / 2 - _nz, _az_z0 + G['out_width'] / 2 + _nz),
    'az_collar': AZ_COLLAR,
    # EL gearbox: output axis Y, foot on the base plate, worm along X, motor +X (parallel to the AZ motor)
    'el_gearbox': (-G['worm_from_end'], WORM_X1, Y_EL_A, Y_EL_B, Z_EL_FOOT, Z_EL_FOOT + G['n_len']),
    'el_motor': (WORM_X1, WORM_X1 + P.NEMA23['length'], (Y_EL_A + Y_EL_B) / 2 - _nz, (Y_EL_A + Y_EL_B) / 2 + _nz,
                 EL_Z + 30.0 - _nz, EL_Z + 30.0 + _nz),
}


def plate_box(name):
    """World-space box of a plate: (x0, x1, y0, y1, z0, z1)."""
    p = PLATES[name]
    (u0, u1), (v0, v1), w, t = p['u'], p['v'], p['w'], p['t']
    return (u0, u1, v0, v1, w, w + t) if p['frame'] == 'xy' else (u0, u1, w, w + t, v0, v1)


def area_mm2(name):
    p = PLATES[name]
    return (p['u'][1] - p['u'][0]) * (p['v'][1] - p['v'][0]) - sum(math.pi * d * d / 4 for _, _, d in p['holes'])


def mass_g(name):
    return area_mm2(name) * PLATES[name]['t'] * P.ALU_PLATE_G_CM3 * 1e-3


def box_overlap(a, b, tol=0.01):
    return all(min(a[2 * i + 1], b[2 * i + 1]) - max(a[2 * i], b[2 * i]) > tol for i in range(3))


def write_dxf(name, path):
    """R12 DXF of one plate in its own frame, origin at the plate's lower-left corner (CAM friendly)."""
    p = PLATES[name]
    (u0, u1), (v0, v1) = p['u'], p['v']
    u, v = u1 - u0, v1 - v0
    ents = []
    corners = [(0, 0), (u, 0), (u, v), (0, v)]
    for (a, b), (c, d) in zip(corners, corners[1:] + corners[:1]):
        ents += ['0', 'LINE', '8', 'CUT', '10', f'{a:.3f}', '20', f'{b:.3f}', '11', f'{c:.3f}', '21', f'{d:.3f}']
    for (hu, hv, d) in p['holes']:
        ents += ['0', 'CIRCLE', '8', 'CUT', '10', f'{hu - u0:.3f}', '20', f'{hv - v0:.3f}', '40', f'{d / 2:.3f}']
    for i, note in enumerate([f'LSR-2 {name} - {P.PLATE["alloy"]} {p["t"]:g} mm - BricoHams'] + p['notes']):
        ents += ['0', 'TEXT', '8', 'NOTES', '10', '0', '20', f'{-10 - 6 * i:.1f}', '40', '4', '1', note]
    with open(path, 'w', encoding='ascii', errors='replace') as fh:
        fh.write('\n'.join(['0', 'SECTION', '2', 'ENTITIES'] + ents + ['0', 'ENDSEC', '0', 'EOF']) + '\n')


def self_test():
    for name, p in PLATES.items():
        (u0, u1), (v0, v1) = p['u'], p['v']
        hs = p['holes']
        for (hu, hv, d) in hs:
            assert d / 2 + 3.0 <= hu - u0 <= u1 - u0 - d / 2 - 3.0 and d / 2 + 3.0 <= hv - v0 <= v1 - v0 - d / 2 - 3.0, (name, hu, hv)
        for i in range(len(hs)):
            for j in range(i + 1, len(hs)):
                gap = math.dist(hs[i][:2], hs[j][:2]) - (hs[i][2] + hs[j][2]) / 2
                assert gap >= 1.5, (name, hs[i], hs[j], gap)   # minimum web between holes
        for (tu, td) in p.get('taps', []):                      # 15 deep tapped bottom-edge holes
            assert u0 + 3.0 + td / 2 <= tu <= u1 - 3.0 - td / 2, (name, 'tap edge', tu)
            for (hu, hv, d) in hs:
                dz = max(0.0, v0 - hv, hv - (v0 + 15.0))
                assert math.hypot(hu - tu, dz) - (d + td) / 2 >= 1.5, (name, 'tap vs hole', tu, hu)
        assert not p.get('light'), 'lightening holes need the P.LIGHTEN keep-out check'
    names = list(ENVELOPES)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            assert not box_overlap(ENVELOPES[a], ENVELOPES[b]), (a, b)
        for pl in PLATES:
            assert not box_overlap(ENVELOPES[a], plate_box(pl)), (a, pl)
    pn = list(PLATES)
    for i, a in enumerate(pn):
        for b in pn[i + 1:]:
            assert not box_overlap(plate_box(a), plate_box(b)), (a, b)
    assert Y_EL_B - Y_EL_A == G['out_width'] and EL_Z == Z_EL_FOOT + G['out_from_foot']
    assert abs(ENVELOPES['az_motor'][1] - ENVELOPES['el_motor'][1]) < 1e-9, 'motors parallel, same way, same x reach'
    print('plate mass: %.0f g (%d plates)' % (sum(mass_g(n) for n in PLATES), len(PLATES)))


if __name__ == '__main__':
    self_test()
    print('plates self-test OK; EL axis at z =', EL_Z)
