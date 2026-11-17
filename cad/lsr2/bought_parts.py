"""LSR-2 phase 11e: visual models of the bought parts in the head frame (FreeCAD Part builders, mm). Visual models of the bought parts in the head frame.

Frame as axes.py: origin = centre of the body bottom face, z = AZ axis, x boresight, y along the EL axis. Sizes: params.NMRV030_GEO / NEMA23
(DATASHEET catalogue, VERIFY with a caliper), DM542 housing 118 x 75 x 34 (MEASURE), mast Ø60.3 x 3.6 (inputs.mast_od, PARAMETRIC), Yagi element
lengths are PARAMETRIC visual placeholders (the real antenna is an open decision). Visual only: the interference checks use the real fabricated parts.
"""
import math
import Part
import FreeCAD
from FreeCAD import Vector as V
import params as P
import axes as AX
import body as BD
from geom import box, cyl, fuse, cut, soft, bolt

G, N, K = P.NMRV030_GEO, P.NEMA23, AX.K
MAST_BOTTOM = -1400.0                       # PARAMETRIC visible mast length below the bracket web (z = -60)


def nmrv030():
    """NMRV030 in its own frame: output axis Z through the origin (faces z 0..56), worm axis X at y = 30, foot plane y = -40, input flange x = 55."""
    ow = G['out_width']
    xa, xb = -G['worm_from_end'], G['worm_len_flange'] - G['worm_from_end']
    ya = -G['out_from_foot']
    wy, wz = 30.0, ow / 2
    body = box(xa + 3, 40, ya + 3, 45, 0, ow)
    body = soft(body, lambda r, e: body.makeFillet(r, e), 10.0, lambda e: abs(e.Vertexes[0].Z - e.Vertexes[-1].Z) > 1e-6)
    cx = lambda r, x0, x1, y, z: cyl(r, x1 - x0, (x0, y, z), (1, 0, 0))
    h = N['hole_square'] / 2
    parts = [body, cyl(25.0, 3.5, (0, 0, -3.5), (0, 0, 1)), cyl(25.0, 3.5, (0, 0, ow), (0, 0, 1)),
             cx(22.0, xa, 40, wy, wz), cx(19.0, xa, xa + 5, wy, wz), box(40, 49, wy - 23, wy + 23, wz - 23, wz + 23),
             box(49, xb, wy - 28.5, wy + 28.5, wz - 28.5, wz + 28.5)]
    parts += [box(x0, x1, ya, ya + 3, z0, z1) for x0, x1 in ((xa + 3, xa + 19), (24, 40)) for z0, z1 in ((0, 16), (ow - 16, ow))]
    parts += [box(xc - 1.5, xc + 1.5, 40, 57, 9, ow - 9) for xc in (-24, -12, 0, 12, 24)]
    r = G['face_pcd'] / 2
    tools = [cyl(7.0, ow + 10, (0, 0, -5), (0, 0, 1)), box(-2.5, 2.5, 0, 9.3, -5, ow + 5)]
    for hx, hy in ((r, 0), (-r, 0), (0, r), (0, -r)):
        tools += [cyl(3.0, 12, (hx, hy, -1), (0, 0, 1)), cyl(3.0, 12, (hx, hy, ow - 11), (0, 0, 1))]
    tools += [cx(N['hole_d'] / 2, xb - 11, xb, wy + sy * h, wz + sz * h) for sy in (-1, 1) for sz in (-1, 1)]
    return cut(fuse(parts), tools)


def nema23(origin):
    """57BYG250H-8 along +X from the gearbox flange, front face centre at origin; one compound (body, caps, shaft, cable)."""
    f, L, hs = N['face'], N['length'], N['hole_square'] / 2
    cap_t, cap = 11.0, f + 0.8
    sq = lambda w, x0, x1: box(x0, x1, -w / 2, w / 2, -w / 2, w / 2)
    along_x = lambda e: abs(e.Vertexes[0].X - e.Vertexes[-1].X) > 1e-6
    body = sq(f, cap_t, L - cap_t)
    body = soft(body, lambda r, e: body.makeChamfer(r, e), 4.5, along_x)
    caps = [sq(cap, 0, cap_t), sq(cap, L - cap_t, L)]
    caps = [soft(c, lambda r, e, c=c: c.makeChamfer(r, e), 4.0, along_x) for c in caps]
    front = cut(caps[0], [cyl(2.55, 9, (-1, sy * hs, sz * hs), (1, 0, 0)) for sy in (-1, 1) for sz in (-1, 1)])
    rear = fuse([caps[1], cyl(6.0, 6.0, (L, 0, 0), (1, 0, 0))])
    shaft = cyl(N['shaft_d'] / 2, 21.0, (-21.6, 0, 0), (1, 0, 0))
    cable = fuse([cyl(2.4, 55.0, (L + 5, 0, 0), (1, 0, 0)), cyl(2.4, 60.0, (L + 60, 0, 0), (math.cos(0.6), 0, -math.sin(0.6)))])
    s = Part.makeCompound([body, front, rear, shaft, cable])
    s.translate(V(*origin))
    return s


def az_gearbox():
    s = nmrv030()
    s.translate(V(0, 0, K['zf']))
    return s


def el_gearbox():
    """Output axis along y (hub y 2..58 about the hub centre K['y_c']), foot on the +z side, worm axis forward: local (x, y, z) -> (x, y_c - 28 + z, z_el - y)."""
    s = nmrv030()
    s.Placement = FreeCAD.Placement(FreeCAD.Matrix(1, 0, 0, 0, 0, 0, 1, K['y_c'] - G['out_width'] / 2, 0, -1, 0, K['z_el'], 0, 0, 0, 1))
    return s


def motors():
    x_fl = G['worm_len_flange'] - G['worm_from_end']
    return {'az_motor': nema23((x_fl, K['y_c'], K['zf'] + G['out_width'] / 2)),
            'el_motor': nema23((x_fl, K['y_c'], K['z_el'] - 30.0))}


def drivers():
    """Two DM542 on the thermal pad of the inner -y wall, one above the other, fins towards the pad: PARAMETRIC placement."""
    y0 = -BD.BY + BD.W + BD.DRIVER_PAD['t']
    return Part.makeCompound([box(70.0, 70.0 + 118.0, y0, y0 + 34.0, z, z + 75.0) for z in (30.0, 110.0)])


def mast():
    """Ø60.3 x 3.6 tube from the bracket web (z = -60) down to MAST_BOTTOM."""
    return cut(cyl(30.15, -60.0 - MAST_BOTTOM, (0, 0, MAST_BOTTOM), (0, 0, 1)), [cyl(26.55, -58.0 - MAST_BOTTOM, (0, 0, MAST_BOTTOM - 1), (0, 0, 1))])


def yagi(side, boom_len, x_el, lens, vshift):
    """Crossed Yagi on the lift arm foot plate (boom Ø30 along x, horizontal elements along y, vertical ones along z), PARAMETRIC placeholder."""
    yc = side * K['lift_y'] + 5.0
    zc = K['z_el'] + K['yagi_h'] + 15.0 + K['foot_t'] + 15.0
    parts = [cyl(15.0, boom_len, (K['ant_a'] - boom_len / 2, yc, zc), (1, 0, 0))]
    for x, ln in zip(x_el, lens):
        parts.append(cyl(3.0, ln, (K['ant_a'] + x, yc - ln / 2, zc), (0, 1, 0)))
        parts.append(cyl(3.0, ln, (K['ant_a'] + x + vshift, yc, zc - ln / 2), (0, 0, 1)))
    return Part.makeCompound(parts)


def build_all():
    """{name: shape} of every bought / visual part in the head frame, keyed like parts_table.PARTS models."""
    out = {'az_gearbox': az_gearbox(), 'el_gearbox': el_gearbox(), 'drivers': drivers(), 'mast': mast()}
    out.update(motors())
    out.update(AX.az_bearings())
    out.update(AX.el_bearings())
    out['clamp_bolts'] = Part.makeCompound(AX.clamp_bolts())
    out['yagi_145'] = yagi(-1, 2000.0, [-900, -650, -380, -120, 180, 480, 780, 950], [940, 900, 880, 866, 852, 840, 830, 820], 55.0)
    out['yagi_435'] = yagi(1, 2000.0, [-950, -700, -450, -200, 50, 300, 550, 800, 950], [345, 330, 320, 312, 305, 299, 294, 290, 286], 25.0)
    return out
