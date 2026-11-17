"""LSR-2 FreeCAD Part helpers shared by body.py, axes.py, visual_parts.py and the route modules (mm, no phase-specific data)."""
import math
import Part
import FreeCAD
from FreeCAD import Vector as V


def box(x0, x1, y0, y1, z0, z1):
    return Part.makeBox(x1 - x0, y1 - y0, z1 - z0, V(x0, y0, z0))


def cyl(r, h, p, d):
    return Part.makeCylinder(r, h, V(*p), V(*d))


def fuse(shapes):
    out = shapes[0]
    for s in shapes[1:]:
        out = out.fuse(s)
    return out


def cut(s, tools):
    for t in tools:
        s = s.cut(t)
    return s


def soft(s, fn, r, pick):
    """Fillet/chamfer the edges chosen by pick(edge); keeps the shape unchanged if OCC refuses."""
    try:
        edges = [e for e in s.Edges if pick(e)]
        return fn(r, edges) if edges else s
    except Exception:
        return s


def hexprism(c, axis, af, h):
    """Hex bolt head / nut: across-flats af, height h, base centre c, along axis."""
    r = af / math.sqrt(3)
    pts = [V(r * math.cos(math.radians(60 * k)), r * math.sin(math.radians(60 * k)), 0) for k in range(6)]
    s = Part.Face(Part.makePolygon(pts + [pts[0]])).extrude(V(0, 0, h))
    s.Placement = FreeCAD.Placement(V(*c), FreeCAD.Rotation(V(0, 0, 1), V(*axis)))
    return s


def bolt(c, axis, d, length, head_af, head_h, nut_af=None, nut_h=0.0):
    """Bolt along axis from c: head at c (outside), shank length, optional nut at the far end."""
    a = V(*axis)
    parts = [hexprism(c, axis, head_af, head_h), cyl(d / 2, length + head_h, (c[0], c[1], c[2]), axis)]
    if nut_af:
        e = V(*c) + a * (head_h + length - nut_h)
        parts.append(hexprism((e.x, e.y, e.z), axis, nut_af, nut_h))
    return fuse(parts)
