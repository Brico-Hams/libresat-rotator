"""LSR-2 cable routing: coax clock-spring coil at each EL bearing side, harness wrap around the mast bracket.
Frame as body.py. Coax type PARAMETRIC (LMR-240 default; datasheet OD/min bend radius to VERIFY), harness OD PARAMETRIC.
Run: python cables.py (pure-Python self-test); build.py imports coax_coil() and harness_wrap() under FreeCAD.
"""
import math

COAX = dict(name='LMR-240', od=6.1, bend_r_min=25.4, note='DATASHEET LMR-240 OD 6.1 mm, static bend 25.4 mm: VERIFY vs vendor')
# Cables leaving the body, per gland (hole d from body.GLANDS). PARAMETRIC ODs, VERIFY with the real cable; the AZ shaft is solid (Ø14 stub),
# so the harness does not pass through a bore: it wraps round the mast bracket (WRAP) and leaves through the bottom glands.
GLAND_CABLES = {
    'M16 harness': dict(range=(4.0, 10.0), hole=16.5, cables=[('7 x 0.75 mm2 screened: 48 V (2 cores each rail), TX, RX, GND', 9.0)]),
    'M12 coax': dict(range=(3.0, 6.5), hole=12.5, cables=[('LMR-240 coax (one feed line, VHF/UHF diplexer at the boom centre)', 6.1)]),
}
HARNESS = dict(od=GLAND_CABLES['M16 harness']['cables'][0][1], note='PARAMETRIC: one multicore cable from the list above')
EL_COIL = dict(y=90.5, major_r=65.0, turns=1, z_el=268.0)         # slab y 87..94 outboard of the bearing seal
WRAP = dict(r=90.0, z=(-60.0, -25.0), turns=1.5, clamp_z=-110.0, loop_mm=300.0)   # helical wrap around the mast bracket
EL_TRAVEL = (-30.0, 150.0)
AZ_TURNS = 1.0                                                      # +-180 deg about the reference (PARAMETRIC, wrap vs slip ring open)


def wrap_length_mm():
    return WRAP['turns'] * math.hypot(2 * math.pi * WRAP['r'], (WRAP['z'][1] - WRAP['z'][0]) / WRAP['turns']) + WRAP['loop_mm']


def gland_bundle_od(cables, packing=0.55):
    """Outer diameter of the round bundle that holds the cables at the given area packing factor (single cable: its own OD)."""
    return cables[0][1] if len(cables) == 1 else math.sqrt(sum(od * od for _, od in cables) / packing)


def self_test():
    for n, gl in GLAND_CABLES.items():
        assert gl['range'][0] <= gland_bundle_od(gl['cables']) <= gl['range'][1] < gl['hole'], n
    assert WRAP['r'] >= 10 * HARNESS['od'] and EL_COIL['major_r'] >= 10 * COAX['od']
    assert EL_COIL['major_r'] >= COAX['bend_r_min'] * 2 and EL_COIL['major_r'] >= 10 * COAX['od']
    assert WRAP['r'] >= 10 * HARNESS['od'] * 0.64 and WRAP['r'] >= 3 * COAX['bend_r_min']
    assert wrap_length_mm() > 2 * math.pi * WRAP['r']
    assert WRAP['clamp_z'] < WRAP['z'][0] and EL_COIL['y'] > 86.0
    print('cables self-test OK  wrap=%.0f mm  EL coil sweep %s' % (wrap_length_mm(), EL_TRAVEL))


def coax_coil(side):
    """Torus coil on the EL axis, one per side, for the EL swing of the antenna feed lines."""
    import Part
    from FreeCAD import Vector as V
    return Part.makeTorus(EL_COIL['major_r'], COAX['od'] / 2, V(0, side * EL_COIL['y'], EL_COIL['z_el']), V(0, 1, 0))


def harness_wrap(n=36):
    """Helical wrap of the harness around the mast bracket as chained cylinders."""
    import Part
    from FreeCAD import Vector as V
    z0, z1 = WRAP['z']
    pts = [V(WRAP['r'] * math.cos(2 * math.pi * WRAP['turns'] * k / n), WRAP['r'] * math.sin(2 * math.pi * WRAP['turns'] * k / n),
             z1 + (z0 - z1) * k / n) for k in range(n + 1)]
    segs = [Part.makeCylinder(HARNESS['od'] / 2, (b - a).Length, a, b - a) for a, b in zip(pts, pts[1:])]
    out = segs[0]
    for s in segs[1:]:
        out = out.fuse(s)
    return out


if __name__ == '__main__':
    self_test()
