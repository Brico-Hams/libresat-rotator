"""LSR-2 rotor, Mk5-style arrangement (vertical plate, EL gearbox high, AZ gearbox low), as a FULLY CONSTRAINED parametric Autodesk Fusion model.

Arrangement and function replicated from the public architecture description; own dimensions only (cad/lsr2/params.py, inputs.py,
NMRV030 catalogue envelope, NEMA23 standard); no third-party CAD geometry.
Assembly frame (mm), design pose el_angle = az_angle = 0: X = EL axis, Y = worm axis (motors and cover on +Y, plate at Y <= 0),
Z = up (AZ axis), origin on the AZ axis at the AZ gearbox centre. Radial direction of the EL group at angle el: (0, -sin el, cos el).
Every part is sketched in its own local frame (sketches on the XY origin plane, extruded along local Z) and placed with an
occurrence transform computed from the user parameters (no joints); EL parts rotate about the EL axis, EL + AZ parts about the AZ axis.
Run: exec in Fusion (LSR2_DIR/LSR2_OUT optional) or main(out_dir).
Report: <out>/build/lsr2_mk5_layout_report.json, STEP: <out>/cad/lsr2/LSR2_mk5_layout.step.
"""
import json
import math
import os
import sys
import traceback

try:
    HERE = os.path.dirname(os.path.abspath(__file__))
except NameError:
    HERE = os.path.join(os.environ.get('LSR2_DIR', os.getcwd()), 'cad', 'lsr2', 'fusion')
LSR2 = os.environ.get('LSR2_DIR') and os.path.join(os.environ['LSR2_DIR'], 'cad', 'lsr2')
if not LSR2 or not os.path.exists(os.path.join(LSR2, 'params.py')):
    LSR2 = os.path.dirname(HERE)
REPO = os.path.dirname(os.path.dirname(LSR2))
if LSR2 not in sys.path:
    sys.path.insert(0, LSR2)

import adsk.core as core      # noqa: E402  (only available inside Fusion)
import adsk.fusion as fusion  # noqa: E402
import params as P            # noqa: E402
import inputs as I            # noqa: E402

CM = 0.1  # mm -> cm (Fusion internal unit)
GB, GEO, N23 = P.GEARBOX[P.GEARBOX_DEFAULT], P.NMRV030_GEO, P.NEMA23
RHO_AL = P.CNC['density']            # g/cm3
RHO_STEEL = I.I.get('mast_rho', 7850.0) / 1000.0
RHO_MOTOR_EQ = 2.9                   # g/cm3 equivalent density of a NEMA23 (about 1 kg for the 56.4 x 56.4 x 112 envelope)
FAILS, WARN = [], []


def user_params():
    """(name, expression, unit, comment); numbers are mm unless the unit is ''."""
    mm = lambda v: '%g mm' % v
    return [
        ('plate_t', mm(P.PLATE['thickness'][1]), 'mm', 'base plate thickness'),
        ('plate_margin', mm(6), 'mm', 'plate margin around the gearbox footprint'),
        ('el_angle', '45 deg', 'deg', 'elevation pose of the EL group (0 = boresight +Y horizontal, 90 = up); side-view photo pose'),
        ('az_angle', '0 deg', 'deg', 'azimuth pose of everything above the mast bracket'),
        ('gb_dz', mm(130), 'mm', 'EL gearbox output axis above the AZ gearbox output axis (EL high, AZ low)'),
        ('gb_w', mm(GEO['worm_len']), 'mm', 'gearbox length along the worm axis'),
        ('gb_n', mm(GEO['n_len']), 'mm', 'gearbox height foot to top'),
        ('gb_out', mm(GEO['out_width']), 'mm', 'gearbox width along the output axis'),
        ('gb_x_free', mm(GEO['worm_from_end']), 'mm', 'output axis to the worm-free end'),
        ('gb_foot', mm(GEO['out_from_foot']), 'mm', 'output axis height above the foot / plate'),
        ('gb_worm_off', mm(GB['centre']), 'mm', 'worm axis offset from the output axis (away from the foot)'),
        ('gb_pcd', mm(GEO['face_pcd']), 'mm', 'output face bolt circle, 4 x M6'),
        ('gb_screw_d', mm(6), 'mm', 'M6'),
        ('gb_hole_depth', mm(GEO['face_hole_depth']), 'mm', 'tapped hole depth'),
        ('hub_bore', mm(GB['bore']), 'mm', 'hollow output bore H8'),
        ('hub_len', mm(GEO['hub_len']), 'mm', 'hub length (bore passes the body and both bosses)'),
        ('boss_d', mm(55), 'mm', 'output boss diameter'),
        ('boss_h', mm(5), 'mm', 'output boss height'),
        ('fin_n', '5', '', 'cooling fins per gearbox'),
        ('fin_pitch', mm(12), 'mm', 'fin pitch'),
        ('fin_t', mm(2), 'mm', 'fin thickness'),
        ('fin_h', mm(4), 'mm', 'fin height'),
        ('motor_face', mm(N23['face']), 'mm', 'NEMA23 frame square'),
        ('motor_bolt_sq', mm(N23['hole_square']), 'mm', 'NEMA23 bolt square'),
        ('motor_len', mm(N23['length']), 'mm', 'motor body length'),
        ('motor_flange_t', mm(8), 'mm', 'motor flange thickness (clearance holes)'),
        ('motor_hole_d', mm(N23['hole_d']), 'mm', 'motor flange hole'),
        ('motor_cb_d', mm(8.5), 'mm', 'motor corner pocket for the M5 head'),
        ('el_shaft_d', 'hub_bore', 'mm', 'EL through shaft diameter (fits the H8 bore)'),
        ('plate_bot', 'gb_out / 2 + boss_h + 16 mm', 'mm', 'plate bottom edge below the AZ gearbox axis'),
        ('plate_top', 'gb_dz + gb_foot + plate_margin', 'mm', 'plate top edge above the AZ gearbox axis'),
        ('plate_W', '2 * (gb_n - gb_foot + plate_margin)', 'mm', 'plate width (X)'),
        ('plate_H', 'plate_bot + plate_top', 'mm', 'plate height (Z)'),
        ('cov_t', mm(2), 'mm', 'cover panel thickness (transparent)'),
        ('cov_hw', mm(70), 'mm', 'cover inner half width (X)'),
        ('cov_d', 'gb_w + motor_len + 8 mm', 'mm', 'cover inner depth from the plate face (Y), motors inside'),
        ('cov_zt', 'plate_top + 6 mm', 'mm', 'cover inner top'),
        ('shaft_hole_d', mm(20), 'mm', 'cover end panel hole for the EL shaft'),
        ('az_hole_d', mm(34), 'mm', 'cover bottom panel hole for the AZ shaft'),
        ('hub_x', 'cov_hw + cov_t + 4 mm', 'mm', 'EL hub flange inner face from the plate centre line (outside the cover)'),
        ('flange_d', mm(76), 'mm', 'EL hub flange diameter'),
        ('flange_t', mm(10), 'mm', 'EL hub flange thickness'),
        ('flange_bc', mm(60), 'mm', 'EL hub flange bolt circle, 6 holes'),
        ('flange_bolt_d', mm(5.5), 'mm', 'EL hub flange hole'),
        ('bracket_t', mm(12), 'mm', 'bracket arm thickness (X)'),
        ('br_w', mm(30), 'mm', 'bracket arm width'),
        ('shaft_stick', mm(10), 'mm', 'EL shaft stick-out beyond each bracket'),
        ('el_shaft_len', '2 * (hub_x + flange_t + bracket_t + shaft_stick)', 'mm', 'EL shaft length'),
        ('arm_h', mm(230), 'mm', 'boom axis distance from the EL axis (own choice: saddle clears the plate at EL 150)'),
        ('boom_w', mm(I.I['boom_w'] * 1000.0), 'mm', 'boom square tube'),
        ('boom_t', mm(I.I['boom_t'] * 1000.0), 'mm', 'boom tube wall'),
        ('boom_len', mm(I.I['boom_len'] * 1000.0), 'mm', 'boom length, parallel to the EL axis'),
        ('saddle_t', mm(8), 'mm', 'saddle plate thickness'),
        ('saddle_w', mm(80), 'mm', 'saddle plate width'),
        ('saddle_L', '2 * (hub_x + flange_t + bracket_t)', 'mm', 'saddle plate length (between the bracket outer faces)'),
        ('cl_t', mm(6), 'mm', 'boom clamp band thickness'),
        ('cl_w', mm(16), 'mm', 'boom clamp band width'),
        ('cl_x', mm(60), 'mm', 'boom clamp band station from the centre'),
        ('sad_r0', 'arm_h - boom_w / 2 - cl_t - saddle_t', 'mm', 'saddle underside radius from the EL axis'),
        ('la_x', mm(abs(I.I['ant145_y']) * 1000.0), 'mm', 'lift arm station along the boom (antenna stations)'),
        ('la_w', mm(30), 'mm', 'lift arm width (X)'),
        ('la_t', mm(8), 'mm', 'lift arm thickness'),
        ('la_off', 'boom_w / 2 + la_t / 2', 'mm', 'lift arm offset from the boom axis (beside the boom)'),
        ('cw_r', mm(200), 'mm', 'counterweight centre radius below the EL axis'),
        ('cw_a', mm(70), 'mm', 'counterweight block side'),
        ('cw_h', mm(100), 'mm', 'counterweight block height (radial)'),
        ('ant_r', 'arm_h + 60 mm', 'mm', 'antenna boom radius from the EL axis (above the boom)'),
        ('ant_bw', mm(20), 'mm', 'antenna boom square side'),
        ('ant_fwd', mm(I.I['ant_cg_a'] * 1000.0), 'mm', 'antenna boom centre ahead of the lift arm'),
        ('a145_len', mm(I.I['ant145_boom'] * 1000.0), 'mm', '145 MHz Yagi boom length'),
        ('a145_el', mm(I.I['ant145_elem'] * 1000.0), 'mm', '145 MHz longest element'),
        ('a435_len', mm(I.I['ant435_boom'] * 1000.0), 'mm', '435 MHz Yagi boom length'),
        ('a435_el', mm(I.I['ant435_elem'] * 1000.0), 'mm', '435 MHz longest element'),
        ('yagi_n', '8', '', 'elements per Yagi'),
        ('yagi_pitch', mm(250), 'mm', 'element spacing'),
        ('yagi_rod', mm(6), 'mm', 'element square section'),
        ('idx_t', mm(3), 'mm', 'index disc thickness'),
        ('idx_x0', 'gb_out / 2 + boss_h + 5 mm', 'mm', 'EL index disc inner face from the plate centre line'),
        ('idz0', 'gb_out / 2 + boss_h + 7 mm', 'mm', 'AZ index disc top below the AZ gearbox axis'),
        ('notch_w', mm(3), 'mm', 'index notch width'),
        ('notch_d', mm(4), 'mm', 'index notch depth'),
        ('sens_w', mm(12), 'mm', 'slotted sensor size along the disc axis'),
        ('sens_d', mm(14), 'mm', 'slotted sensor size across'),
        ('sens_h', mm(12), 'mm', 'slotted sensor height'),
        ('sens_slit', mm(4), 'mm', 'sensor slot width'),
        ('sens_depth', mm(6), 'mm', 'sensor slot depth'),
        ('azs_top', 'gb_out / 2 + boss_h + 3 mm', 'mm', 'AZ shaft top above the AZ gearbox axis'),
        ('az_d', mm(P.THRUST['d']), 'mm', 'AZ shaft diameter at the bearing (51206 bore)'),
        ('thr_D', mm(P.THRUST['D']), 'mm', '51206 outer diameter'),
        ('thr_H', mm(P.THRUST['H']), 'mm', '51206 height'),
        ('hous_h', mm(30), 'mm', 'thrust bearing housing height'),
        ('hous_w', mm(80), 'mm', 'thrust bearing housing width (X)'),
        ('hous_bore', mm(32), 'mm', 'housing through bore'),
        ('mb_gap', mm(5), 'mm', 'gap between the thrust housing and the mast bracket'),
        ('mb_top', 'plate_bot + cov_t + hous_h + mb_gap', 'mm', 'mast bracket top below the AZ gearbox axis'),
        ('mb_w', mm(100), 'mm', 'mast bracket width (X)'),
        ('mb_d', mm(50), 'mm', 'mast bracket depth (Y)'),
        ('mb_h', mm(110), 'mm', 'mast bracket height'),
        ('mb_bore', mm(60), 'mm', 'AZ shaft seat depth in the mast bracket'),
        ('mast_d', mm(I.I['mast_od'] * 1000.0), 'mm', 'mast tube outer diameter'),
        ('mast_t', mm(I.I['mast_t'] * 1000.0), 'mm', 'mast tube wall'),
        ('mast_len', mm(400), 'mm', 'mast tube length shown'),
        ('ub_t', mm(6), 'mm', 'U-bolt band thickness'),
        ('ub_h', mm(16), 'mm', 'U-bolt band height'),
        ('ub_lug_w', mm(40), 'mm', 'U-bolt lug width'),
        ('ub_z1', mm(25), 'mm', 'upper U-bolt top below the bracket top'),
        ('ub_z2', mm(75), 'mm', 'lower U-bolt top below the bracket top'),
        ('mast_y', 'gb_x_free + mb_d / 2 + ub_t + mast_d / 2', 'mm', 'mast axis offset from the AZ axis (Y)'),
        ('enc_w', mm(130), 'mm', 'enclosure width (X)'),
        ('enc_d', mm(95), 'mm', 'enclosure depth (Y)'),
        ('enc_h', mm(90), 'mm', 'enclosure height'),
        ('enc_t', mm(3), 'mm', 'enclosure wall and lid thickness'),
        ('enc_x0', 'cov_hw + cov_t + 2 mm', 'mm', 'enclosure inner side face (beside the cover, right of the plate)'),
        ('enc_y0', mm(10), 'mm', 'enclosure front-to-plate offset (Y)'),
        ('enc_gx', mm(26), 'mm', 'cable gland X from the enclosure centre'),
        ('enc_gy', mm(12.5), 'mm', 'cable gland Y from the enclosure centre'),
        ('enc_wx', mm(45), 'mm', 'WiFi bulkhead X from the enclosure centre'),
        ('enc_wy', mm(25), 'mm', 'WiFi bulkhead Y from the enclosure centre (negative side)'),
        ('enc_screw_d', mm(7), 'mm', 'lid screw head'),
        ('enc_screw_h', mm(2), 'mm', 'lid screw head height'),
        ('enc_screw_in', mm(6), 'mm', 'lid screw inset from the corner'),
        ('gland_d', mm(22), 'mm', 'cable gland body'),
        ('gland_thread', mm(16), 'mm', 'cable gland M16 thread'),
        ('gland_h', mm(10), 'mm', 'cable gland body height'),
        ('gland_in', mm(5), 'mm', 'thread length inside the floor'),
        ('wifi_hole', mm(7), 'mm', 'lid hole for the WiFi bulkhead'),
        ('wifi_flange', mm(12), 'mm', 'WiFi bulkhead flange'),
        ('wifi_thread', mm(6.5), 'mm', 'WiFi bulkhead thread'),
        ('wifi_up', mm(4), 'mm', 'bulkhead thread above the lid'),
        ('wifi_ant_d', mm(8), 'mm', 'WiFi antenna diameter'),
        ('wifi_ant_len', mm(110), 'mm', 'WiFi antenna length'),
        ('hs_l', mm(90), 'mm', 'driver heatsink length'),
        ('hs_h', mm(38), 'mm', 'driver heatsink height'),
        ('hs_base', mm(4), 'mm', 'heatsink base thickness'),
        ('hs_fin_n', '5', '', 'heatsink fins'),
        ('hs_fin_pitch', mm(7), 'mm', 'heatsink fin pitch'),
        ('hs_fin_t', mm(2), 'mm', 'heatsink fin thickness'),
        ('hs_fin_h', mm(15), 'mm', 'heatsink fin height'),
        ('pcb_w', mm(55), 'mm', 'controller PCB width'),
        ('pcb_d', mm(50), 'mm', 'controller PCB depth'),
        ('pcb_t', mm(1.6), 'mm', 'PCB thickness'),
        ('dc_w', mm(55), 'mm', '5 V DC converter width'),
        ('dc_d', mm(25), 'mm', '5 V DC converter depth'),
        ('dc_h', mm(18), 'mm', '5 V DC converter height'),
    ]


class Sk:
    def __init__(self, comp, name):
        self.name = comp.name + '/' + name
        self.sk = comp.sketches.add(comp.xYConstructionPlane)
        self.sk.name = name
        self.xa = self.sk.project(comp.xConstructionAxis).item(0)
        self.ya = self.sk.project(comp.yConstructionAxis).item(0)
        self.o = self.sk.originPoint


def p3(x, y):
    return core.Point3D.create(x * CM, y * CM, 0)


def dim(s, a, b, orient, expr):
    ax, ay, bx, by = a.geometry.x, a.geometry.y, b.geometry.x, b.geometry.y
    d = s.sk.sketchDimensions.addDistanceDimension(a, b, orient, core.Point3D.create((ax + bx) / 2 + 0.5, (ay + by) / 2 + 0.5, 0))
    d.parameter.expression = expr


def hdim(s, a, b, expr):
    dim(s, a, b, fusion.DimensionOrientations.HorizontalDimensionOrientation, expr)


def vdim(s, a, b, expr):
    dim(s, a, b, fusion.DimensionOrientations.VerticalDimensionOrientation, expr)


def pin(s, pt, x, y, ex, ey):
    """Fix a point from the origin: coincident when on an axis, else two distance dimensions."""
    if abs(x) < 1e-9 and abs(y) < 1e-9:
        s.sk.geometricConstraints.addCoincident(pt, s.o)
        return
    if abs(x) < 1e-9:
        s.sk.geometricConstraints.addCoincident(pt, s.ya)
    else:
        hdim(s, s.o, pt, ex)
    if abs(y) < 1e-9:
        s.sk.geometricConstraints.addCoincident(pt, s.xa)
    else:
        vdim(s, s.o, pt, ey)


def rect(s, cx, cy, w, h, ecx, ecy, ew, eh):
    """Centred rectangle: H/V lines, width/height dimensions, centre = midpoint of a construction diagonal pinned to the origin."""
    lines = s.sk.sketchCurves.sketchLines
    ls = lines.addTwoPointRectangle(p3(cx - w / 2, cy - h / 2), p3(cx + w / 2, cy + h / 2))
    for i in range(4):
        ln = ls.item(i)
        horiz = abs(ln.startSketchPoint.geometry.y - ln.endSketchPoint.geometry.y) < 1e-9
        (s.sk.geometricConstraints.addHorizontal if horiz else s.sk.geometricConstraints.addVertical)(ln)
    pts = [ls.item(i).startSketchPoint for i in range(4)]

    def at(x, y):
        return [q for q in pts if abs(q.geometry.x - x * CM) < 1e-6 and abs(q.geometry.y - y * CM) < 1e-6][0]
    bl, br, tr, tl = at(cx - w / 2, cy - h / 2), at(cx + w / 2, cy - h / 2), at(cx + w / 2, cy + h / 2), at(cx - w / 2, cy + h / 2)
    hdim(s, bl, br, ew)
    vdim(s, bl, tl, eh)

    def edge(c, size, ec, es):
        v = c - size / 2
        ex = '(%s) - (%s) / 2' % (ec if ec else '0 mm', es)
        return v, ('abs(%s)' % ex if v < 0 else ex)
    xl, exl = edge(cx, w, ecx, ew)
    yl, eyl = edge(cy, h, ecy, eh)
    pin(s, bl, xl, yl, exl, eyl)


def circle(s, cx, cy, d, ecx=None, ecy=None, ed=None, concentric=None, pos=True):
    c = s.sk.sketchCurves.sketchCircles.addByCenterRadius(p3(cx, cy), d / 2 * CM)
    if concentric is not None:
        s.sk.geometricConstraints.addConcentric(c, concentric)
    elif pos:
        pin(s, c.centerSketchPoint, cx, cy, ecx, ecy)
    if ed:
        dd = s.sk.sketchDimensions.addDiameterDimension(c, core.Point3D.create((cx + d * 0.8) * CM, (cy + d * 0.8) * CM, 0))
        dd.parameter.expression = ed
    return c


def mirror(s, a, b, axis):
    s.sk.geometricConstraints.addSymmetry(a.centerSketchPoint, b.centerSketchPoint, axis)


def holes4(s, ax, ay, d, eax, eay, ed):
    """4 equal holes at (+-ax, +-ay): one pinned, three mirrored about the axes."""
    h0 = circle(s, ax, ay, d, eax, eay, ed)
    h1 = circle(s, -ax, ay, d, pos=False)
    h2 = circle(s, ax, -ay, d, pos=False)
    h3 = circle(s, -ax, -ay, d, pos=False)
    mirror(s, h0, h1, s.ya)
    mirror(s, h0, h2, s.xa)
    mirror(s, h1, h3, s.xa)
    for h in (h1, h2, h3):
        s.sk.geometricConstraints.addEqual(h0, h)


def holes6(s, r, d, er, ed):
    """6 equal holes on a bolt circle of radius r (first on +X)."""
    c, sn = r * math.cos(math.radians(60)), r * math.sin(math.radians(60))
    h0 = circle(s, r, 0, d, er, None, ed)
    h1 = circle(s, c, sn, d, '%s * cos(60 deg)' % er, '%s * sin(60 deg)' % er)
    h2 = circle(s, -c, sn, d, pos=False)
    h3 = circle(s, -r, 0, d, pos=False)
    h4 = circle(s, -c, -sn, d, pos=False)
    h5 = circle(s, c, -sn, d, pos=False)
    mirror(s, h1, h2, s.ya)
    mirror(s, h0, h3, s.ya)
    mirror(s, h2, h4, s.xa)
    mirror(s, h1, h5, s.xa)
    for h in (h1, h2, h3, h4, h5):
        s.sk.geometricConstraints.addEqual(h0, h)


def profiles(sk):
    return [sk.profiles.item(i) for i in range(sk.profiles.count)]


def check(s):
    if not s.sk.isFullyConstrained:
        FAILS.append(s.name)


def extrude(comp, s, start, length, op='new', allp=False):
    ops = {'new': fusion.FeatureOperations.NewBodyFeatureOperation, 'join': fusion.FeatureOperations.JoinFeatureOperation,
           'cut': fusion.FeatureOperations.CutFeatureOperation}
    if allp:
        prof = core.ObjectCollection.create()
        for q in profiles(s.sk):
            prof.add(q)
    else:
        prof = max(profiles(s.sk), key=lambda q: (q.profileLoops.count, q.areaProperties().area))
    inp = comp.features.extrudeFeatures.createInput(prof, ops[op])
    inp.startExtent = fusion.OffsetStartDefinition.create(core.ValueInput.createByString(start))
    inp.setOneSideExtent(fusion.DistanceExtentDefinition.create(core.ValueInput.createByString(length)), fusion.ExtentDirections.PositiveExtentDirection)
    return comp.features.extrudeFeatures.add(inp)


def mat(o, xv, yv, zv):
    m = core.Matrix3D.create()
    m.setWithCoordinateSystem(core.Point3D.create(o[0] * CM, o[1] * CM, o[2] * CM), core.Vector3D.create(*xv), core.Vector3D.create(*yv), core.Vector3D.create(*zv))
    return m


# local frames as (x, y, z) world directions of the part axes; local +z is the extrusion direction
FZ = ((1, 0, 0), (0, 1, 0), (0, 0, 1))
FX = ((0, 1, 0), (0, 0, 1), (1, 0, 0))        # local z -> +X, local y -> up
FXM = ((0, -1, 0), (0, 0, 1), (-1, 0, 0))     # mirrored: local z -> -X, local y -> up
FM = ((1, 0, 0), (0, 0, 1), (0, -1, 0))       # local z -> -Y (plate, front panel, heatsinks)
FS = ((0, 0, 1), (0, -1, 0), (1, 0, 0))       # local z -> +X, local x -> up
FELG = ((0, 1, 0), (0, 0, -1), (-1, 0, 0))    # EL gearbox: worm +Y, n down, output along X
FAZG = ((0, 1, 0), (-1, 0, 0), (0, 0, 1))     # AZ gearbox: worm +Y, n -X, output vertical
FMOT = ((1, 0, 0), (0, 0, -1), (0, 1, 0))     # motor: local z (shaft) -> +Y

VAL = {}  # user parameter values in mm (unitless as is), filled by build()


def E(x):
    return float(x) if not isinstance(x, str) else float(eval(x, {'__builtins__': {}, 'abs': abs}, VAL))


def mag(e):
    """Expression for the magnitude of a signed expression (None when zero), used for distances to the origin."""
    if not isinstance(e, str):
        return None
    return e if E(e) >= 0 else 'abs(%s)' % e


def X(v):
    return '0 mm' if v == 0 else v


def Rct(s, w, h, cx=0, cy=0):
    rect(s, E(cx), E(cy), E(w), E(h), cx if isinstance(cx, str) else None, cy if isinstance(cy, str) else None, w, h)


def Cir(s, d, cx=0, cy=0, conc=None):
    return circle(s, E(cx), E(cy), E(d), mag(cx), mag(cy), d, concentric=conc)


def prism(c, w, h, length, start=0, cx=0, cy=0, op='new', name='prism'):
    s = Sk(c, name)
    Rct(s, w, h, cx, cy)
    check(s)
    return extrude(c, s, X(start), length, op)


def disc(c, d, length, start=0, bore=None, cx=0, cy=0, op='new', name='disc'):
    s = Sk(c, name)
    o = Cir(s, d, cx, cy)
    if bore:
        Cir(s, bore, cx, cy, conc=o)
    check(s)
    return extrude(c, s, X(start), length, op)


def pattern(c, feat, axis, n, pitch):
    ents = core.ObjectCollection.create()
    ents.add(feat)
    pat = c.features.rectangularPatternFeatures
    pat.add(pat.createInput(ents, axis, core.ValueInput.createByString(n), core.ValueInput.createByString(pitch),
                            fusion.PatternDistanceType.SpacingPatternDistanceType))


def mat(o, xv, yv, zv):
    m = core.Matrix3D.create()
    m.setWithCoordinateSystem(core.Point3D.create(o[0] * CM, o[1] * CM, o[2] * CM), core.Vector3D.create(*xv), core.Vector3D.create(*yv), core.Vector3D.create(*zv))
    return m


def _rv(v, d, a):
    """Rodrigues rotation of the vector v about the unit axis d by a radians."""
    c, s = math.cos(a), math.sin(a)
    dot = sum(p * q for p, q in zip(v, d))
    cr = (d[1] * v[2] - d[2] * v[1], d[2] * v[0] - d[0] * v[2], d[0] * v[1] - d[1] * v[0])
    return tuple(v[i] * c + cr[i] * s + d[i] * dot * (1 - c) for i in range(3))


def _rp(p, p0, d, a):
    v = _rv(tuple(p[i] - p0[i] for i in range(3)), d, a)
    return tuple(p0[i] + v[i] for i in range(3))


def pose(f, group, el, az, el_pt, az_pt):
    """Matrix of a part frame f = (origin, axes) for the groups: 'fixed' (mast side), 'az' (rotates about the AZ axis), 'el' (EL, then AZ)."""
    o, ax = f[0], list(f[1])
    if group == 'el':
        o = _rp(o, el_pt, (1, 0, 0), el)
        ax = [_rv(v, (1, 0, 0), el) for v in ax]
    if group in ('el', 'az'):
        o = _rp(o, az_pt, (0, 0, 1), az)
        ax = [_rv(v, (0, 0, 1), az) for v in ax]
    return mat(o, *ax)


def build(out):
    app = core.Application.get()
    doc = app.documents.add(core.DocumentTypes.FusionDesignDocumentType)
    doc.name = 'LSR2_mk5_layout'
    design = fusion.Design.cast(app.activeProduct)
    design.designType = fusion.DesignTypes.ParametricDesignType
    root = design.rootComponent
    for n, e, u, c in user_params():
        if u:
            design.userParameters.add(n, core.ValueInput.createByString(e), u, c)
        else:
            design.userParameters.add(n, core.ValueInput.createByReal(float(e)), '', c)

    def V(n):
        p = design.userParameters.itemByName(n)
        return p.value * (10.0 if p.unit == 'mm' else 1.0)

    for n, e, u, c in user_params():
        if u != 'deg':
            VAL[n] = V(n)
    el0, az0 = V('el_angle'), V('az_angle')  # radians
    xf, dz = VAL['gb_x_free'], VAL['gb_dz']
    EL_PT, AZ_PT = (0.0, xf, dz), (0.0, xf, 0.0)
    comps, occs, PL = {}, {}, []

    def new(name, o, axes, grp):
        occ = root.occurrences.addNewComponent(pose((o, axes), grp, el0, az0, EL_PT, AZ_PT))
        occ.component.name = name
        comps[name] = occ.component
        occs.setdefault(name, []).append(occ)
        PL.append((occ, (o, axes), grp, name))
        return occ.component

    def put(comp, o, axes, grp):
        occ = root.occurrences.addExistingComponent(comp, pose((o, axes), grp, el0, az0, EL_PT, AZ_PT))
        occs.setdefault(comp.name, []).append(occ)
        PL.append((occ, (o, axes), grp, comp.name))

    half = VAL['gb_out'] / 2
    fin_n = int(round(VAL['fin_n']))
    plate_bot = VAL['plate_bot']

    # ---- vertical aluminium plate (backbone): XZ plane, thickness towards -Y
    c = new('plate', (0, 0, 0), FM, 'az')
    prism(c, 'plate_W', 'plate_H', 'plate_t', 0, 0, '(plate_top - plate_bot) / 2', name='plate')

    # ---- gearboxes (local x = worm axis, y = n direction, z = output axis; origin on the output axis)
    def gearbox(name, o, axes):
        c = new(name, o, axes, 'az')
        s = Sk(c, 'body')
        rect(s, VAL['gb_w'] / 2 - VAL['gb_x_free'], VAL['gb_n'] / 2 - VAL['gb_foot'], VAL['gb_w'], VAL['gb_n'],
             'gb_w / 2 - gb_x_free', 'gb_n / 2 - gb_foot', 'gb_w', 'gb_n')
        circle(s, 0, 0, VAL['hub_bore'], ed='hub_bore')
        check(s)
        extrude(c, s, '-gb_out / 2', 'gb_out')
        s = Sk(c, 'boss')
        outer = circle(s, 0, 0, VAL['boss_d'], ed='boss_d')
        circle(s, 0, 0, VAL['hub_bore'], ed='hub_bore', concentric=outer)
        check(s)
        extrude(c, s, 'gb_out / 2', 'boss_h', 'join')
        extrude(c, s, '-gb_out / 2 - boss_h', 'boss_h', 'join')
        s = Sk(c, 'face_holes')
        a = VAL['gb_pcd'] / 2 * math.cos(math.radians(45))
        holes4(s, a, a, VAL['gb_screw_d'], 'gb_pcd / 2 * cos(45 deg)', 'gb_pcd / 2 * cos(45 deg)', 'gb_screw_d')
        check(s)
        extrude(c, s, 'gb_out / 2 - gb_hole_depth', 'gb_hole_depth', 'cut', True)
        extrude(c, s, '-gb_out / 2', 'gb_hole_depth', 'cut', True)
        s = Sk(c, 'fin')
        top = VAL['gb_n'] - VAL['gb_foot']
        rect(s, -(fin_n - 1) * VAL['fin_pitch'] / 2, top + VAL['fin_h'] / 2, VAL['fin_t'], VAL['fin_h'],
             '-(fin_n - 1) * fin_pitch / 2', 'gb_n - gb_foot + fin_h / 2', 'fin_t', 'fin_h')
        check(s)
        pattern(c, extrude(c, s, '-gb_out / 2', 'gb_out', 'join'), c.xConstructionAxis, 'fin_n', 'fin_pitch')

    gearbox('el_gearbox', (0, xf, dz), FELG)
    gearbox('az_gearbox', (0, xf, 0), FAZG)

    # ---- NEMA23 motors on +Y, side by side (parallel worm axes), EL motor above the AZ motor
    def motor(name, o):
        c = new(name, o, FMOT, 'az')
        s = Sk(c, 'body')
        rect(s, 0, 0, VAL['motor_face'], VAL['motor_face'], None, None, 'motor_face', 'motor_face')
        check(s)
        extrude(c, s, '0 mm', 'motor_len')
        a = VAL['motor_bolt_sq'] / 2
        s = Sk(c, 'flange_holes')
        holes4(s, a, a, VAL['motor_hole_d'], 'motor_bolt_sq / 2', 'motor_bolt_sq / 2', 'motor_hole_d')
        check(s)
        extrude(c, s, '0 mm', 'motor_flange_t', 'cut', True)
        s = Sk(c, 'head_pockets')
        holes4(s, a, a, VAL['motor_cb_d'], 'motor_bolt_sq / 2', 'motor_bolt_sq / 2', 'motor_cb_d')
        check(s)
        extrude(c, s, 'motor_flange_t', 'motor_len - motor_flange_t', 'cut', True)

    motor('el_motor', (0, VAL['gb_w'], dz - VAL['gb_worm_off']))
    motor('az_motor', (-VAL['gb_worm_off'], VAL['gb_w'], 0))

    # ---- cover (transparent panels enclosing plate front, gearboxes and motors)
    ztop_cov, zbot_cov = VAL['cov_zt'], -(plate_bot + VAL['cov_t'])
    c = new('cover_end', (VAL['cov_hw'], 0, 0), FX, 'az')
    s = Sk(c, 'panel')
    Rct(s, 'cov_d + cov_t', 'cov_zt + plate_bot + 2 * cov_t', '(cov_d + cov_t) / 2', '(cov_zt - plate_bot) / 2')
    Cir(s, 'shaft_hole_d', 'gb_x_free', 'gb_dz')
    check(s)
    extrude(c, s, '0 mm', 'cov_t')
    put(c, (-VAL['cov_hw'] - VAL['cov_t'], 0, 0), FX, 'az')
    c = new('cover_top', (0, 0, ztop_cov), FZ, 'az')
    prism(c, '2 * cov_hw', 'cov_d + cov_t', 'cov_t', 0, 0, '(cov_d + cov_t) / 2', name='panel')
    c = new('cover_bottom', (0, 0, zbot_cov), FZ, 'az')
    s = Sk(c, 'panel')
    Rct(s, '2 * cov_hw', 'cov_d + cov_t', 0, '(cov_d + cov_t) / 2')
    Cir(s, 'az_hole_d', 0, 'gb_x_free')
    check(s)
    extrude(c, s, '0 mm', 'cov_t')
    c = new('cover_front', (0, VAL['cov_d'] + VAL['cov_t'], 0), FM, 'az')
    prism(c, '2 * cov_hw', 'cov_zt + plate_bot', 'cov_t', 0, 0, '(cov_zt - plate_bot) / 2', name='panel')

    # ---- EL shaft (horizontal, through both gearbox bosses, out on both sides of the cover) and its index disc
    c = new('el_shaft', (0, xf, dz), FX, 'el')
    disc(c, 'el_shaft_d', 'el_shaft_len', '-el_shaft_len / 2', name='shaft')
    c = new('index_disc_el', (0, xf, dz), FX, 'el')
    disc(c, 'gb_out', 'idx_t', 'idx_x0', bore='el_shaft_d', name='disc')
    s = Sk(c, 'notch')
    Rct(s, 'notch_w', '2 * notch_d', 0, 'gb_out / 2')
    check(s)
    extrude(c, s, 'idx_x0', 'idx_t', 'cut')

    def sensor(name, o, axes):
        c = new(name, o, axes, 'az')
        prism(c, 'sens_w', 'sens_d', 'sens_h', name='body')
        s = Sk(c, 'slot')
        Rct(s, 'sens_slit', 'sens_d + sens_slit')
        check(s)
        extrude(c, s, '0 mm', 'sens_depth', 'cut')

    sensor('sensor_el', (VAL['idx_x0'] + VAL['idx_t'] / 2, xf, dz + half - VAL['sens_depth']), FZ)

    # ---- EL hubs (flange on each shaft end, outside the cover) and bracket arms rising to the saddle
    for side, fl, fb, sgn in (('L', FELG, FXM, -1), ('R', FX, FX, 1)):
        c = new('el_hub_' + side, (0, xf, dz), fl, 'el')
        s = Sk(c, 'flange')
        outer = Cir(s, 'flange_d')
        Cir(s, 'el_shaft_d', conc=outer)
        holes6(s, VAL['flange_bc'] / 2, VAL['flange_bolt_d'], 'flange_bc / 2', 'flange_bolt_d')
        check(s)
        extrude(c, s, 'hub_x', 'flange_t')
        c = new('bracket_' + side, (0, xf, dz), fb, 'el')
        s = Sk(c, 'arm')
        Rct(s, 'br_w', 'sad_r0 + br_w / 2', 0, '(sad_r0 - br_w / 2) / 2')
        Cir(s, 'el_shaft_d')
        check(s)
        extrude(c, s, 'hub_x + flange_t', 'bracket_t')

    # ---- saddle, boom clamps, boom
    az_ = dz + VAL['arm_h']
    c = new('saddle_plate', (0, xf, dz + VAL['sad_r0']), FZ, 'el')
    prism(c, 'saddle_L', 'saddle_w', 'saddle_t', name='plate')
    c = new('boom_clamp', (VAL['cl_x'], xf, az_), FX, 'el')
    s = Sk(c, 'band')
    Rct(s, 'boom_w + 2 * cl_t', 'boom_w + 2 * cl_t')
    Rct(s, 'boom_w', 'boom_w')
    check(s)
    extrude(c, s, '-cl_w / 2', 'cl_w')
    put(c, (-VAL['cl_x'], xf, az_), FX, 'el')
    c = new('boom', (0, xf, az_), FX, 'el')
    s = Sk(c, 'tube')
    Rct(s, 'boom_w', 'boom_w')
    Rct(s, 'boom_w - 2 * boom_t', 'boom_w - 2 * boom_t')
    check(s)
    extrude(c, s, '-boom_len / 2', 'boom_len')

    # ---- lift arms (one beside the boom at each antenna station): antenna above, counterweight below
    for side, sgn, ant in (('L', -1, 'a145'), ('R', 1, 'a435')):
        px = sgn * VAL['la_x']
        c = new('lift_arm_' + side, (px, xf, dz), FZ, 'el')
        prism(c, 'la_w', 'la_t', 'ant_r - ant_bw / 2 + cw_r - cw_h / 2', '-(cw_r - cw_h / 2)', 0, 'la_off', name='plate')
        c = new('counterweight_' + side, (px, xf, dz), FZ, 'el')
        prism(c, 'cw_a', 'cw_a', 'cw_h', '-cw_r - cw_h / 2', 0, 'la_off', name='block')
        c = new('antenna_' + side, (px, xf, dz + VAL['ant_r'] - VAL['ant_bw'] / 2), FZ, 'el')
        prism(c, 'ant_bw', ant + '_len', 'ant_bw', 0, 0, 'ant_fwd', name='boom')
        s = Sk(c, 'element')
        Rct(s, ant + '_el', 'yagi_rod', 0, 'ant_fwd - (yagi_n - 1) * yagi_pitch / 2')
        check(s)
        pattern(c, extrude(c, s, '(ant_bw - yagi_rod) / 2', 'yagi_rod', 'join'), c.yConstructionAxis, 'yagi_n', 'yagi_pitch')

    # ---- AZ side: shaft (fixed to the mast bracket), index disc, thrust bearing and housing at the plate bottom, mast bracket, U-bolts, mast
    c = new('az_shaft', (0, xf, 0), FZ, 'fixed')
    disc(c, 'hub_bore', 'plate_bot + azs_top', '-plate_bot', name='upper')
    disc(c, 'az_d', 'mb_top + mb_bore - plate_bot', '-(mb_top + mb_bore)', op='join', name='lower')
    c = new('index_disc_az', (0, xf, -(VAL['idz0'] + VAL['idx_t'])), FZ, 'fixed')
    disc(c, 'gb_out', 'idx_t', bore='hub_bore', name='disc')
    s = Sk(c, 'notch')
    Rct(s, '2 * notch_d', 'notch_w', 'gb_out / 2', 0)
    check(s)
    extrude(c, s, '0 mm', 'idx_t', 'cut')
    sensor('sensor_az', (half - VAL['sens_depth'], xf, -(VAL['idz0'] + VAL['idx_t'] / 2)), FS)
    z_h = -(plate_bot + VAL['cov_t'])
    c = new('thrust_housing', (0, xf, z_h), FZ, 'az')
    prism(c, 'hous_w', 'gb_x_free + thr_D / 2', 'hous_h', '-hous_h', 0, '(thr_D / 2 - gb_x_free) / 2', name='block')
    disc(c, 'thr_D', 'thr_H', '-thr_H', op='cut', name='pocket')
    disc(c, 'hous_bore', 'hous_h', '-hous_h', op='cut', name='bore')
    c = new('thrust_bearing', (0, xf, z_h), FZ, 'az')
    disc(c, 'thr_D', 'thr_H', '-thr_H', bore='az_d', name='ring')
    mb_z = -VAL['mb_top']
    c = new('mast_bracket', (0, xf, mb_z), FZ, 'fixed')
    prism(c, 'mb_w', 'mb_d', 'mb_h', '-mb_h', name='block')
    disc(c, 'az_d', 'mb_bore', '-mb_bore', op='cut', name='seat')
    c = new('mast_tube', (0, VAL['mast_y'], mb_z), FZ, 'fixed')
    disc(c, 'mast_d', 'mast_len', '-mast_len', bore='mast_d - 2 * mast_t', name='tube')
    c = new('u_bolt', (0, VAL['mast_y'], mb_z - VAL['ub_z1'] - VAL['ub_h']), FZ, 'fixed')
    disc(c, 'mast_d + 2 * ub_t', 'ub_h', bore='mast_d', name='band')
    prism(c, 'ub_lug_w', 'ub_t', 'ub_h', 0, 0, '-(mast_d / 2 + ub_t / 2)', op='join', name='lug')
    put(c, (0, VAL['mast_y'], mb_z - VAL['ub_z2'] - VAL['ub_h']), FZ, 'fixed')

    # ---- electronics enclosure (right of the plate, transparent lid) and its contents
    xc, yc = VAL['enc_x0'] + VAL['enc_w'] / 2, VAL['enc_y0'] + VAL['enc_d'] / 2
    zf = -plate_bot
    zl = zf + VAL['enc_h'] - VAL['enc_t']
    c = new('enclosure', (xc, yc, zf), FZ, 'az')
    s = Sk(c, 'walls')
    Rct(s, 'enc_w', 'enc_d')
    Rct(s, 'enc_w - 2 * enc_t', 'enc_d - 2 * enc_t')
    check(s)
    extrude(c, s, '0 mm', 'enc_h - enc_t')
    s = Sk(c, 'floor')
    Rct(s, 'enc_w', 'enc_d')
    Cir(s, 'gland_thread', 'enc_gx', 'enc_gy')
    check(s)
    extrude(c, s, '0 mm', 'enc_t', 'join')
    c = new('enclosure_lid', (xc, yc, zl), FZ, 'az')
    s = Sk(c, 'lid')
    Rct(s, 'enc_w', 'enc_d')
    Cir(s, 'wifi_hole', 'enc_wx', '-enc_wy')
    check(s)
    extrude(c, s, '0 mm', 'enc_t')
    sh = VAL['enc_screw_in']
    corners = [(xc + sx * (VAL['enc_w'] / 2 - sh), yc + sy * (VAL['enc_d'] / 2 - sh)) for sx in (-1, 1) for sy in (-1, 1)]
    c = new('enc_screw', (corners[0][0], corners[0][1], zl + VAL['enc_t']), FZ, 'az')
    disc(c, 'enc_screw_d', 'enc_screw_h', name='head')
    for px, py in corners[1:]:
        put(c, (px, py, zl + VAL['enc_t']), FZ, 'az')
    c = new('cable_gland', (xc + VAL['enc_gx'], yc + VAL['enc_gy'], zf - VAL['gland_h']), FZ, 'az')
    disc(c, 'gland_d', 'gland_h', name='body')
    disc(c, 'gland_thread', 'enc_t + gland_in', 'gland_h', op='join', name='thread')
    wx, wy = xc + VAL['enc_wx'], yc - VAL['enc_wy']
    c = new('wifi_bulkhead', (wx, wy, zl - VAL['enc_t']), FZ, 'az')
    disc(c, 'wifi_flange', 'enc_t', name='flange')
    disc(c, 'wifi_thread', 'enc_t + wifi_up', 'enc_t', op='join', name='thread')  # ends where the antenna starts (was 3 mm into it)
    c = new('wifi_antenna', (wx, wy, zl + VAL['enc_t'] + VAL['wifi_up']), FZ, 'az')
    disc(c, 'wifi_ant_d', 'wifi_ant_len', name='antenna')
    y_wall = VAL['enc_y0'] + VAL['enc_d'] - VAL['enc_t']
    z_lo, z_hi = zf + VAL['enc_t'], zl
    for name, zc in (('heatsink_el', z_hi - 1 - VAL['hs_h'] / 2), ('heatsink_az', z_lo + 1 + VAL['hs_h'] / 2)):
        c = new(name, (xc, y_wall, zc), FM, 'az')
        prism(c, 'hs_l', 'hs_h', 'hs_base', name='base')
        s = Sk(c, 'fin')
        Rct(s, 'hs_l', 'hs_fin_t', 0, '-(hs_fin_n - 1) * hs_fin_pitch / 2')
        check(s)
        pattern(c, extrude(c, s, 'hs_base', 'hs_fin_h', 'join'), c.yConstructionAxis, 'hs_fin_n', 'hs_fin_pitch')
    pin_ = VAL['enc_t'] + 3.0
    c = new('controller_pcb', (VAL['enc_x0'] + pin_ + VAL['pcb_w'] / 2, VAL['enc_y0'] + pin_ + VAL['pcb_d'] / 2, z_lo), FZ, 'az')
    prism(c, 'pcb_w', 'pcb_d', 'pcb_t', name='board')
    c = new('dcdc_5v', (VAL['enc_x0'] + VAL['enc_w'] - pin_ - VAL['dc_w'] / 2, VAL['enc_y0'] + pin_ + VAL['dc_d'] / 2, z_lo), FZ, 'az')
    prism(c, 'dc_w', 'dc_d', 'dc_h', name='module')

    # ---- appearances
    def appearance(key, cands, rgba):
        lib = app.materialLibraries.itemByName('Fusion Appearance Library')
        found = None
        if lib:
            for cn in cands:  # candidates in preference order, matched as case-insensitive substrings
                for i in range(lib.appearances.count):
                    a = lib.appearances.item(i)
                    if cn.lower() in a.name.lower():
                        found = a
                        break
                if found:
                    break
        if found:
            WARN.append('appearance %s -> library "%s"' % (key, found.name))
            try:
                return design.appearances.itemByName(key) or design.appearances.addByCopy(found, key)
            except Exception:
                return design.appearances.itemByName(key) or found
        WARN.append('appearance %s not found in the Fusion Appearance Library; colour only' % key)
        return None

    def colourise(ap, rgba):
        if not ap:
            return
        try:
            for prop in ap.appearanceProperties:
                cp = core.ColorProperty.cast(prop)
                if cp and prop.name.lower() in ('color', 'tint color') and rgba:
                    cp.value = core.Color.create(*rgba)
        except Exception:
            WARN.append('colour override failed for ' + ap.name)

    al = appearance('lsr2_aluminium', ['Aluminum - Satin', 'Aluminum', 'Aluminium'], None)
    blk = appearance('lsr2_black', ['Plastic - Matte (Black)', 'Paint - Enamel Glossy (Black)', 'Black'], None)
    colourise(blk, (20, 20, 20, 255))
    gl = appearance('lsr2_glass', ['Glass - Clear', 'Glass'], None)
    st = appearance('lsr2_steel', ['Steel - Satin', 'Steel'], None)
    base = lambda n: n.rsplit('_', 1)[0] if n.endswith(('_L', '_R')) else n
    blk_parts = ('el_motor', 'az_motor', 'index_disc_el', 'index_disc_az', 'sensor_el', 'sensor_az', 'heatsink_el', 'heatsink_az')
    glass_parts = ('cover_end', 'cover_top', 'cover_bottom', 'cover_front', 'enclosure_lid')
    steel_parts = ('el_shaft', 'az_shaft', 'mast_tube', 'u_bolt', 'counterweight_L', 'counterweight_R', 'enc_screw')
    kind = {n: (blk if n in blk_parts else gl if n in glass_parts else st if n in steel_parts else al) for n in comps}
    rho = {n: RHO_AL for n in comps}
    for n in glass_parts:
        rho[n] = 1.19
    for n in steel_parts:
        rho[n] = RHO_STEEL
    rho.update(controller_pcb=1.9, dcdc_5v=1.5, cable_gland=1.1, wifi_bulkhead=8.5, wifi_antenna=1.0)
    vols = {n: sum(b.volume for b in cp.bRepBodies) for n, cp in comps.items()}
    # bought parts and antennas: equivalent density so the mass equals the inputs.py value
    for n, kg in (('el_gearbox', I.I['gb_mass']), ('az_gearbox', I.I['gb_mass']), ('el_motor', I.I['motor_mass']), ('az_motor', I.I['motor_mass']),
                  ('antenna_L', I.I['ant145_mass']), ('antenna_R', I.I['ant435_mass'])):
        rho[n] = kg * 1000.0 / vols[n]
    for n, cp in comps.items():
        for b in cp.bRepBodies:
            b.name = n
            if kind.get(n):
                b.appearance = kind[n]

    # ---- report
    parts = {}
    for n, cp in comps.items():
        vol = vols[n]
        cnt = len(occs[n])
        parts[n] = dict(instances=cnt, volume_cm3=round(vol, 3), mass_kg_each=round(vol * rho[n] / 1000.0, 4), mass_kg_total=round(vol * rho[n] / 1000.0 * cnt, 4),
                        density_g_cm3=round(rho[n], 3))

    def set_pose(el, az):
        for occ, f, grp, n in PL:
            m = pose(f, grp, el, az, EL_PT, AZ_PT)
            try:
                occ.transform2 = m
            except Exception:
                occ.transform = m

    def group_cg(groups):
        mt, acc = 0.0, [0.0, 0.0, 0.0]
        for occ, f, grp, n in PL:
            if grp in groups:
                for b in occ.bRepBodies:
                    pp = b.physicalProperties
                    m = pp.volume * rho[n] / 1000.0
                    cm = pp.centerOfMass
                    mt += m
                    for i, q in enumerate((cm.x, cm.y, cm.z)):
                        acc[i] += m * q * 10.0
        return mt, [a / mt for a in acc]

    def interference():
        method = 'design.analyzeInterference (coincident faces excluded)'
        items = []
        try:
            ents = core.ObjectCollection.create()
            for occ, f, grp, n in PL:
                ents.add(occ)
            ii = design.createInterferenceInput(ents)
            ii.areCoincidentFacesIncluded = False
            res = design.analyzeInterference(ii)

            def nm(e):
                ctx = getattr(e, 'assemblyContext', None)
                return ctx.name if ctx else (e.name if getattr(e, 'name', None) else '?')
            for i in range(res.count):
                r = res.item(i)
                ib = r.interferenceBody
                items.append(dict(a=nm(r.entityOne), b=nm(r.entityTwo), volume_cm3=round(ib.volume, 5) if ib else None))
        except Exception as e:
            method = 'pairwise bounding boxes (analyzeInterference failed: %s)' % e
            L = [o for o, *_ in PL]
            for i in range(len(L)):
                for j in range(i + 1, len(L)):
                    p, q = L[i].boundingBox, L[j].boundingBox
                    if all(p.minPoint.asArray()[k] < q.maxPoint.asArray()[k] - 1e-4 and q.minPoint.asArray()[k] < p.maxPoint.asArray()[k] - 1e-4 for k in range(3)):
                        items.append(dict(a=L[i].name, b=L[j].name, volume_cm3=None))
        return method, items

    def cg_report():
        out_ = {}
        for key, groups in (('el_group', ('el',)), ('az_group', ('el', 'az'))):
            m, cg = group_cg(groups)
            rel = [round(cg[0], 2), round(cg[1] - xf, 2), round(cg[2] - (dz if key == 'el_group' else 0.0), 2)]
            out_[key] = dict(mass_kg=round(m, 3), cg_mm=[round(v, 2) for v in cg],
                             cg_rel_axis_mm=rel, gravity_torque_about_axis_Nm=round(m * 9.81 * (rel[1] if key == 'el_group' else math.hypot(rel[0], rel[1])) / 1000.0, 3))
        return out_

    poses = []
    method = None
    for el_deg, az_deg in ((-30, 0), (0, 0), (45, 0), (90, 0), (150, 0)):
        set_pose(math.radians(el_deg), math.radians(az_deg))
        method, items = interference()
        poses.append(dict(el_deg=el_deg, az_deg=az_deg, interference_count=len(items), interferences=items,
                          interfering_pairs=['%s <-> %s' % (i['a'], i['b']) for i in items], groups=cg_report()))
    set_pose(el0, az0)
    bb = root.boundingBox
    live = [o for v in occs.values() for o in v]
    rep = dict(
        model='LSR-2 Mk5-style rotor: vertical plate, EL NMRV030 high, AZ NMRV030 low, motors on the same side, EL shaft with hubs/brackets/saddle/boom/lift arms/antennas/counterweights, '
              'AZ shaft through a 51206 thrust housing into a U-bolt mast bracket, cover, electronics enclosure',
        provenance='arrangement replicated, own dimensions, no third-party CAD geometry',
        placement='occurrence transforms derived from the user parameters (no joints); el_angle / az_angle rotate the EL and AZ groups',
        pose_deg=dict(el=round(math.degrees(el0), 3), az=round(math.degrees(az0), 3)),
        components=sorted(comps), occurrences=len(live), parts=parts,
        total_mass_kg=round(sum(v['mass_kg_total'] for v in parts.values()), 3),
        moving_groups=cg_report(),
        bbox_mm=dict(min=[round(x * 10, 2) for x in bb.minPoint.asArray()], max=[round(x * 10, 2) for x in bb.maxPoint.asArray()]),
        interference=dict(method=method, poses=poses),
        sketches_checked_not_fully_constrained=list(FAILS), appearance_warnings=list(WARN),
        user_parameters=[n for n, *_ in user_params()])
    os.makedirs(os.path.join(out, 'build'), exist_ok=True)
    with open(os.path.join(out, 'build', 'lsr2_mk5_layout_report.json'), 'w') as f:
        json.dump(rep, f, indent=1)
    step_dir = os.path.join(out, 'cad', 'lsr2')
    os.makedirs(step_dir, exist_ok=True)
    em = design.exportManager
    em.execute(em.createSTEPExportOptions(os.path.join(step_dir, 'LSR2_mk5_layout.step'), root))
    if FAILS:
        raise AssertionError('sketches not fully constrained: %s' % FAILS)
    return rep


def main(out_dir=None):
    out = out_dir or os.environ.get('LSR2_OUT') or REPO
    return build(os.path.abspath(out))


def run(context):
    ui = core.Application.get().userInterface
    try:
        rep = main()
        ui.messageBox('LSR-2 Mk5 layout OK, %d occurrences, %.2f kg' % (rep['occurrences'], rep['total_mass_kg']))
    except Exception:
        ui.messageBox('LSR-2 Mk5 layout failed:\n' + traceback.format_exc())
