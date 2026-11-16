"""LSR-2 photo-interrupter index parts: printed ASA notch discs (AZ on the collar, EL on the boom_socket hub) and the sensor brackets.

The index idea (one slotted disc + slotted photosensor per axis) is published by SARCNET for the SARCTrac Mk5; this geometry is ours.
Pure-Python numbers (notch angle) are testable anywhere; the builders need FreeCAD and are used by build.py.
"""
import math
import params as P
import cast_parts as CP

I = P.INDEX
AZ_DISC = dict(bore=I['az_shaft_d'] + I['fit_clear'], z=I['az_z'])
EL_DISC = dict(bore=2 * CP.SOCK['R_HUB'] + I['fit_clear'], y=CP.SOCK['y0'] + 1.0)   # 1 mm in from the hub face
for _d in (AZ_DISC, EL_DISC):
    _d['r_out'] = _d['bore'] / 2 + I['ring']
    _d['notch_deg'] = math.degrees(I['notch_arc'] / _d['r_out'])
    _d['r_sensor'] = _d['r_out'] - I['notch_depth'] / 2    # the interrupter gap is centred on the notch depth
BRACKET = dict(t=3.0, foot=(24.0, 16.0), post_w=12.0, pad=(30.0, 12.0))
AZ_BRACKET = dict(foot_z=115.0)   # foot on the body pillar top (z 115); post height I['az_post'] puts the sensor slot at the disc (z 130..133)


def _v(*a):
    from FreeCAD import Vector
    return Vector(*a)


def disc(d, axis):
    """Notch disc as a solid in the head frame: AZ about Z, EL about Y (hub-profile bore is cut by build.py for the EL disc)."""
    import Part
    t = I['t']
    if axis == 'z':
        z0 = d['z'][0]
        s = Part.makeCylinder(d['r_out'], t, _v(0, 0, z0), _v(0, 0, 1)).cut(Part.makeCylinder(d['bore'] / 2, t + 2, _v(0, 0, z0 - 1), _v(0, 0, 1)))
        notch = Part.makeBox(I['notch_depth'] + 1, 2 * d['r_out'] * math.sin(math.radians(d['notch_deg'] / 2)), t + 2,
                             _v(d['r_out'] - I['notch_depth'], -d['r_out'] * math.sin(math.radians(d['notch_deg'] / 2)), z0 - 1))
        return s.cut(notch)
    y0 = d['y']
    s = Part.makeCylinder(d['r_out'], t, _v(0, y0, CP.EL_Z), _v(0, 1, 0)).cut(Part.makeCylinder(d['bore'] / 2, t + 2, _v(0, y0 - 1, CP.EL_Z), _v(0, 1, 0)))
    w = 2 * d['r_out'] * math.sin(math.radians(d['notch_deg'] / 2))
    notch = Part.makeBox(I['notch_depth'] + 1, t + 2, w, _v(d['r_out'] - I['notch_depth'], y0 - 1, CP.EL_Z - w / 2))   # +x side = pointing direction at el 0
    return s.cut(notch)


def bracket(post_h=60.0):
    """Printed ASA L bracket in its own frame (foot on z=0, post up, pad toward +x); one design for both axes (post_h 60 EL, I['az_post'] AZ), 2 x M3 on the sensor holes."""
    import Part
    b = BRACKET
    fx, fy = b['foot']
    foot = Part.makeBox(fx, fy, b['t'], _v(0, 0, 0))
    post = Part.makeBox(b['t'], fy, post_h, _v(0, 0, 0))
    padx, pady = b['pad']
    pad = Part.makeBox(padx, pady, b['t'], _v(0, (fy - pady) / 2, post_h - b['t']))
    s = foot.fuse(post).fuse(pad)
    holes = [Part.makeCylinder(I['sensor_hole_d'] / 2, b['t'] + 2, _v(padx / 2 + sx * I['sensor_holes'] / 2, fy / 2, post_h - b['t'] - 1), _v(0, 0, 1))
             for sx in (-1, 1)]
    holes.append(Part.makeCylinder(3.3, b['t'] + 2, _v(fx - 8.0, fy / 2, -1), _v(0, 0, 1)))   # M6 bolt / zip-tie anchor
    for h in holes:
        s = s.cut(h)
    return s


def self_test():
    for d in (AZ_DISC, EL_DISC):
        assert d['notch_deg'] >= I['min_notch_deg'] + 2.0, d          # firmware needs >= min_notch_deg of slot; margin for the edge position
        assert I['ring'] - I['notch_depth'] >= 3.0                    # printed web left under the notch
        assert I['t'] < I['gap']                                      # disc fits the 5 mm interrupter gap
    assert AZ_DISC['z'][1] - AZ_DISC['z'][0] == I['t']
    assert 115.0 < AZ_DISC['z'][0] and AZ_DISC['z'][1] + I['gap'] < 140.0   # disc and slotted sensor stay between pillar top and shelf
    assert AZ_BRACKET['foot_z'] + I['az_post'] <= AZ_DISC['z'][1] + 1.0
    assert I['sensor_holes'] + I['sensor_hole_d'] + 2 * 3.0 <= BRACKET['pad'][0]


if __name__ == '__main__':
    self_test()
    print('index_parts self-test OK; notch deg AZ %.1f EL %.1f' % (AZ_DISC['notch_deg'], EL_DISC['notch_deg']))
