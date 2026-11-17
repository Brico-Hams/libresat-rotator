"""LSR-2 detailed visual models of the bought parts (FreeCAD Part builders, head frame, mm).

Visual only: render_blender.py shows them, the interference checks keep the simple envelopes of plates.ENVELOPES.
The NMRV030 and the NEMA23 follow params.NMRV030_GEO / params.NEMA23 and stay inside (or within ~1 mm of) the envelopes.
"""
import math
import Part
import FreeCAD
from FreeCAD import Vector as V
import params as P
import plates as PL
import cast_parts as CP

G = P.NMRV030_GEO
N = P.NEMA23
EL_Z = PL.EL_Z


from geom import box, cyl, fuse, cut, soft, hexprism, bolt   # noqa: E402,F401  (shared helpers)


def nmrv030(flip=False):
    """NMRV030 in its own frame: output axis Z through the origin (faces z = 0 and 56), worm axis X at y = 30, foot plane y = -40,
    worm-free end x = -40, input flange x = 55. flip builds the mirror image in x (for the EL gearbox, placed with a rotation)."""
    ow = G['out_width']
    xa, xb = -G['worm_from_end'], G['worm_len_flange'] - G['worm_from_end']
    ya, yb = -G['out_from_foot'], G['n_len'] - G['out_from_foot']
    wy, wz = 30.0, ow / 2
    sg = -1.0 if flip else 1.0

    def bx(x0, x1, y0, y1, z0, z1):
        a, b = sorted((sg * x0, sg * x1))
        return box(a, b, y0, y1, z0, z1)

    def cx(r, x0, x1, y, z):
        return cyl(r, abs(x1 - x0), (min(sg * x0, sg * x1), y, z), (1, 0, 0))

    body = bx(xa + 3, 40, ya + 3, 45, 0, ow)
    body = soft(body, lambda r, e: body.makeFillet(r, e), 10.0,
                lambda e: abs(e.Vertexes[0].Z - e.Vertexes[-1].Z) > 1e-6)
    body = soft(body, lambda r, e: body.makeChamfer(r, e), 1.5,
                lambda e: abs(e.BoundBox.ZLength) < 1e-6 and (abs(e.BoundBox.ZMin) < 1e-6 or abs(e.BoundBox.ZMin - ow) < 1e-6))
    parts = [body,
             cyl(25.0, 3.5, (0, 0, -3.5), (0, 0, 1)), cyl(25.0, 3.5, (0, 0, ow), (0, 0, 1)),            # output bosses on both faces
             cx(22.0, xa, 40, wy, wz), cx(19.0, xa, xa + 5, wy, wz),                                    # worm housing + free-end cap
             bx(40, 49, wy - 23, wy + 23, wz - 23, wz + 23),                                              # neck to the input flange
             bx(49, xb, wy - 28.5, wy + 28.5, wz - 28.5, wz + 28.5)]                                      # NEMA23 adapter square 57 x 57
    h = N['hole_square'] / 2
    parts += [cx(5.5, 44, xb, wy + sy * h, wz + sz * h) for sy in (-1, 1) for sz in (-1, 1)]            # 4 screw bosses
    parts += [bx(x0, x1, ya, ya + 3, z0, z1) for x0, x1 in ((xa + 3, xa + 19), (24, 40)) for z0, z1 in ((0, 16), (ow - 16, ow))]   # foot lugs
    parts += [bx(xc - 1.5, xc + 1.5, 40, 57, 9, ow - 9) for xc in (-24, -12, 0, 12, 24)]               # cooling fins
    s = fuse(parts)
    r_pcd = G['face_pcd'] / 2
    tools = [cyl(7.0, ow + 10, (0, 0, -5), (0, 0, 1)), box(-2.5, 2.5, 0, 9.3, -5, ow + 5)]             # hollow hub Ø14 + 5 mm keyway
    for (hx, hy) in ((r_pcd, 0), (-r_pcd, 0), (0, r_pcd), (0, -r_pcd)):
        tools += [cyl(3.0, 12, (hx, hy, -1), (0, 0, 1)), cyl(3.0, 12, (hx, hy, ow - 11), (0, 0, 1))]   # M6 x 11 on PCD65, both faces
    tools += [cyl(N['pilot_d'] / 2 + 0.2, 1.6, (min(sg * xb, sg * (xb - 1.6)), wy, wz), (1, 0, 0)),
              cyl(14.0 / 2, 30, (min(sg * xb, sg * (xb - 30)), wy, wz), (1, 0, 0))]
    tools += [cyl(N['hole_d'] / 2, 11, (min(sg * xb, sg * (xb - 11)), wy + sy * h, wz + sz * h), (1, 0, 0)) for sy in (-1, 1) for sz in (-1, 1)]
    tools += [cyl(3.3, 12, (sg * x, ya - 1, z), (0, 1, 0)) for x in (xa + 11, 32.0) for z in (8.0, ow - 8.0)]   # foot lug holes
    return cut(s, tools)


def place_az_gearbox():
    s = nmrv030(False)
    s.translate(V(0, 0, PL.T_SPACER))
    return s


def place_el_gearbox():
    s = nmrv030(True)
    # local (x, y, z) -> head (-x, Y_EL_A + z, Z_EL_FOOT + out_from_foot + y): a pure rotation, the output axis turns from Z to Y
    s.Placement = FreeCAD.Placement(FreeCAD.Matrix(-1, 0, 0, 0, 0, 0, 1, PL.Y_EL_A, 0, 1, 0, PL.Z_EL_FOOT + G['out_from_foot'], 0, 0, 0, 1))
    return s


def nema23(origin):
    """57BYG250H-8 along +X from the gearbox flange: returns {'body','caps','shaft','cable'} placed at origin = (x, y, z) of the front face centre."""
    f, L, hs = N['face'], N['length'], N['hole_square'] / 2
    cap_t, cap = 11.0, f + 0.8

    def sq(w, x0, x1):
        return box(x0, x1, -w / 2, w / 2, -w / 2, w / 2)

    along_x = lambda e: abs(e.Vertexes[0].X - e.Vertexes[-1].X) > 1e-6
    body = sq(f, cap_t, L - cap_t)
    body = soft(body, lambda r, e: body.makeChamfer(r, e), 4.5, along_x)
    caps = []
    for x0, x1 in ((0, cap_t), (L - cap_t, L)):
        c = sq(cap, x0, x1)
        caps.append(soft(c, lambda r, e: c.makeChamfer(r, e), 4.0, along_x))
    front = cut(caps[0], [cyl(2.55, 9, (-1, sy * hs, sz * hs), (1, 0, 0)) for sy in (-1, 1) for sz in (-1, 1)])   # 4 tapped holes
    front = fuse([front, cyl(N['pilot_d'] / 2, 1.6, (-1.6, 0, 0), (1, 0, 0))])
    rear = fuse([caps[1], cyl(6.0, 6.0, (L, 0, 0), (1, 0, 0))])                                              # rear cable gland
    shaft = cut(cyl(N['shaft_d'] / 2, 21.0, (-21.6, 0, 0), (1, 0, 0)), [box(-18.0, -1.0, -5, 5, 3.5, 5)])    # Ø8 shaft with a flat
    cable = fuse([cyl(2.4, 55.0, (L + 5, 0, 0), (1, 0, 0)), cyl(2.4, 60.0, (L + 60, 0, 0), (math.cos(0.6), 0, -math.sin(0.6)))])
    out = {'body': body, 'caps': Part.makeCompound([front, rear]), 'shaft': shaft, 'cable': cable}
    for s in out.values():
        s.translate(V(*origin))
    return out


def mast():
    """Ø50 x 2 mm galvanised tube, 1.5 m, resting in the V of the mast clamp (the V vertex is at CP.CL_VERTEX)."""
    r = 25.0
    xc = CP.CL_VERTEX - r * math.sqrt(2)
    z0 = CP.Z_CL_TOP - 1500.0
    return cyl(r, 1500.0, (xc, 0, z0), (0, 0, 1)).cut(cyl(r - 2.0, 1502.0, (xc, 0, z0 - 1), (0, 0, 1))), xc


def yagi(yc, boom_len, xs, lens, vshift, driven):
    """Crossed Yagi: Ø30 boom along X on top of the cross boom, Ø6 elements along Y (horizontal) and Z (vertical, shifted by vshift)."""
    zc = EL_Z + PL.BOOM_H / 2 + 15.0
    parts = [cyl(15.0, boom_len, (-boom_len / 2, yc, zc), (1, 0, 0)),
             box(xs[driven] - 25, xs[driven] + 25, yc - 20, yc + 20, zc - 17, zc + 17)]                    # feed-point box
    for x, ln in zip(xs, lens):
        parts.append(cyl(3.0, ln, (x, yc - ln / 2, zc), (0, 1, 0)))
        if abs(x + vshift) >= 45.0 and abs(x + vshift) < boom_len / 2:
            parts.append(cyl(3.0, ln, (x + vshift, yc, zc - ln / 2), (0, 0, 1)))
    return Part.makeCompound(parts)


def u_bolt(z, xc):
    ring = Part.makeTorus(35.0, 4.0, V(xc, 0, z), V(0, 0, 1)).common(box(xc - 60, xc, -50, 50, z - 10, z + 10))
    return [ring] + [cyl(4.0, -20.0 - xc, (xc, sy * 35.0, z), (1, 0, 0)) for sy in (-1, 1)]


def hardware(xc_mast):
    """Stainless fasteners on the visible joints, grouped by the part they move with (exploded view): {name: [shapes]}."""
    base, housing, clamp, socket, ant = [], [], [], [], []
    for k in (0, 1, 2, 4, 5):                                                                                    # PCD110 M6 heads on the base plate (k=3 is the index bracket)
        a = math.radians(30 + 60 * k)
        base.append(hexprism((55 * math.cos(a), 55 * math.sin(a), 0), (0, 0, 1), 10.0, 4.0))
    r, y0 = G['face_pcd'] / 2, CP.BH['y0'] + CP.BH['T_FL']
    for sx, sz in ((1, 0), (-1, 0), (0, 1), (0, -1)):                                                            # M6 heads on the bearing housing flange
        housing.append(hexprism((sx * r, y0, EL_Z + sz * r), (0, 1, 0), 10.0, 4.0))
    for z in CP.CL_UB_Z:                                                                                         # mast U-bolts, nuts on the ear faces
        clamp += u_bolt(z, xc_mast)
        clamp += [hexprism((CP.CL_EAR_X, sy * 35.0, z), (1, 0, 0), 13.0, 6.5) for sy in (-1, 1)]
    h = CP.SOCK
    w2 = h['W'] / 2
    for d in h['bolt_back']:                                                                                     # socket clamp bolts M8
        socket.append(bolt((-w2 - 5.5, h['y0'] + h['L'] - d, EL_Z), (1, 0, 0), 8.0, h['W'] + 6.5, 13.0, 5.5, 13.0, 6.5))
    socket.append(bolt((-16.0, h['y0'] + h['L_HUB'] / 2, EL_Z + h['pinch_z']), (1, 0, 0), 6.0, 29.0, 10.0, 4.0, 10.0, 5.0))   # pinch bolt M6
    for pos in P.ANT_POS_Y:                                                                                      # Yagi boom to cross boom: bolts straddle the tube
        for sx in (-30.0, 30.0):
            ant.append(bolt((sx, CP.SOCK_Y1 + pos * 1000.0, EL_Z + PL.BOOM_H / 2 + 35.0), (0, 0, -1), 6.0, 76.0, 10.0, 4.0, 10.0, 5.0))
    return {'hardware_base': base, 'hardware_housing': housing, 'hardware_clamp': clamp, 'hardware_socket': socket, 'hardware_ant': ant}


def build_all():
    """Returns {name: shape} for stl/lsr2/visual/ (head frame, mm)."""
    out = {}
    out['az_gearbox'] = place_az_gearbox()
    out['el_gearbox'] = place_el_gearbox()
    zc_az = PL.T_SPACER + G['out_width'] / 2
    x_fl = G['worm_len_flange'] - G['worm_from_end']
    for tag, org in (('az', (x_fl, 30.0, zc_az)), ('el', (x_fl, (PL.Y_EL_A + PL.Y_EL_B) / 2, EL_Z + 30.0))):
        for k, s in nema23(org).items():
            out[f'{tag}_motor_{k}'] = s
    m, xc = mast()
    out['mast'] = m
    out['yagi_145'] = yagi(CP.SOCK_Y1 + P.ANT_POS_Y[0] * 1000.0, P.ANT_BOOM_L,
                           [-900, -720, -480, -220, 120, 450, 800, 960], [940, 900, 880, 866, 852, 840, 830, 820], 55.0, 1)
    out['yagi_435'] = yagi(CP.SOCK_Y1 + P.ANT_POS_Y[1] * 1000.0, 800.0,
                           [-390, -310, -235, -160, -80, 80, 160, 240, 320, 390], [345, 330, 320, 312, 305, 299, 294, 290, 286, 282], 25.0, 4)
    for k, shapes in hardware(xc).items():
        out[k] = Part.makeCompound(shapes)
    return out
