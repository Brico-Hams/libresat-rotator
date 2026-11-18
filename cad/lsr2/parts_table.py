"""LSR-2 phase 11e: one table of every assembly part: balloon number, CAD model names, category, material, route, quantity and BOM key.

Single source for build.py (FCStd groups, labels), scripts/drawings.py (balloons, legend) and scripts/bom.py (Pos column).
Categories: bought, machined (turned / cut / CNC), cast (route A sand casting + machining; route B CNC is the alternative), printed (PLA pattern of a cast part).
LSR2_DESIGN=mk4 (default): the table is mk4_params.PARTS (SARCTrac Mk4 replica); model names, quantities and exploded offsets come from build/lsr2_render_scene.json
(written by build.py), colour = render colour category (aluminium sheet / plate, steel, motors, gearbox, rubber, electronics, antenna).
LSR2_DESIGN=cast: the phase 11 cast table below. Run: python parts_table.py (self-test).
"""
import json
import os
import sys
BOUGHT, MACHINED, CAST, PRINTED = 'Bought', 'Machined', 'Cast', 'Printed pattern'
CATEGORIES = (BOUGHT, MACHINED, CAST, PRINTED)
COLOURS = {BOUGHT: '#8a8f98', MACHINED: '#2f6fb2', CAST: '#b5651d', PRINTED: '#3a9d5d'}   # drawing legend: no orange (reserved for identification / controls)
DESIGN = (os.environ.get('LSR2_DESIGN') or 'mk4').lower()
_HERE = os.path.dirname(os.path.abspath(__file__))

# (balloon, label, category, material, route, qty, ref = BOM key or None, CAD model names)
ROWS = [
    (1, 'Body (open box, ribs)', CAST, 'A356-T6 (A) / 6082-T6 (B)', 'A cast + machining / B CNC slabs', 1, 'body', ('body',)),
    (2, 'Lid with gasket groove', CAST, 'A356-T6 (A) / 6061-T6 (B)', 'A / B', 1, 'lid', ('lid',)),
    (3, 'Mast clamp bracket', CAST, 'A356-T6 (A) / 6082-T6 (B)', 'A / B', 1, 'mast_bracket', ('mast_bracket',)),
    (4, 'AZ shaft', MACHINED, '1.4404 bar', 'turned + keyway', 1, 'shafts.az_shaft', ('az_shaft',)),
    (5, 'EL through-shaft', MACHINED, '1.4404 bar', 'turned + keyways', 1, 'shafts.el_shaft', ('el_shaft',)),
    (6, 'EL sleeve', MACHINED, '1.4404 bar', 'turned', 1, 'shafts.el_sleeve', ('el_sleeve',)),
    (7, 'Yoke arm', CAST, 'A356-T6 (A) / 6082-T6 (B)', 'A / B', 2, 'yoke_arm', ('yoke_arm', 'yoke_arm_neg')),
    (8, 'Saddle plate', CAST, 'A356-T6 (A) / 6061-T6 (B)', 'A / B', 1, 'saddle', ('saddle',)),
    (9, 'Boom clamp block', CAST, 'A356-T6 (A) / 6061-T6 (B)', 'A / B', 2, 'boom_clamp', ('boom_clamp', 'boom_clamp_neg')),
    (10, 'Cross boom 40x40x3', BOUGHT, '6063-T6 square tube', 'saw cut', 1, 'boom', ('boom',)),
    (11, 'Lift arm', MACHINED, '6063 flat bar + plate', 'sawn, drilled', 2, 'lift_arm', ('lift_arm_pos', 'lift_arm_neg')),
    (12, 'Counterweight', MACHINED, 'S235 steel slug + rod', 'sawn, turned', 2, 'counterweight', ('counterweight_pos', 'counterweight_neg')),
    (13, 'AZ gearbox NMRV030', BOUGHT, 'cast Al housing, bronze worm wheel', 'catalogue', 1, 'gearbox', ('az_gearbox',)),
    (14, 'EL gearbox NMRV030', BOUGHT, 'as 13', 'catalogue', 1, 'gearbox', ('el_gearbox',)),
    (15, 'AZ motor NEMA23', BOUGHT, '57BYG250H-8', 'catalogue', 1, 'motor', ('az_motor',)),
    (16, 'EL motor NEMA23', BOUGHT, '57BYG250H-8', 'catalogue', 1, 'motor', ('el_motor',)),
    (17, 'Bearing 6206-2RS (AZ)', BOUGHT, 'bearing steel', 'catalogue', 2, 'brg6206', ('brg_az_lower', 'brg_az_upper')),
    (18, 'Thrust bearing 51206 (AZ)', BOUGHT, 'bearing steel', 'catalogue', 1, 'brg51206', ('brg_az_thrust',)),
    (19, 'Bearing 6004-2RS (EL)', BOUGHT, 'bearing steel', 'catalogue', 2, 'brg6004', ('brg_el_pos', 'brg_el_neg')),
    (20, 'Driver DM542 (inner wall)', BOUGHT, 'catalogue module', 'catalogue', 2, 'driver', ('drivers',)),
    (21, 'Boom clamp bolts M6', BOUGHT, 'A4-70', 'catalogue', 8, 'clamp_bolts', ('clamp_bolts',)),
    (22, 'Mast (customer, not in BOM)', BOUGHT, 'steel tube 60.3 x 3.6', 'customer', 1, None, ('mast',)),
    (23, 'Yagi 145 MHz (customer)', BOUGHT, 'aluminium', 'customer', 1, None, ('yagi_145',)),
    (24, 'Yagi 435 MHz (customer)', BOUGHT, 'aluminium', 'customer', 1, None, ('yagi_435',)),
]
PARTS = [dict(pos=r[0], label=r[1], cat=r[2], material=r[3], route=r[4], qty=r[5], ref=r[6], models=r[7]) for r in ROWS]
# Exploded-view offsets (dx, dy, dz) in mm from the assembled head frame: PARAMETRIC, shared by the drawings and the Blender renders
EXPLODE = {'lid': (0, 0, 260), 'mast': (0, 0, -420), 'mast_bracket': (0, 0, -200), 'az_shaft': (0, 0, -120), 'brg_az_thrust': (0, 0, -80),
           'brg_az_lower': (0, 0, -40), 'brg_az_upper': (0, 0, 40), 'az_motor': (150, 0, 0), 'el_motor': (150, 0, 0), 'drivers': (0, 110, 0),
           'el_shaft': (0, -200, 0), 'el_sleeve': (0, 200, 0), 'brg_el_pos': (0, 60, 0), 'brg_el_neg': (0, -60, 0),
           'yoke_arm': (0, 150, 100), 'yoke_arm_neg': (0, -150, 100), 'saddle': (0, 0, 100), 'boom': (0, 0, 200),
           'boom_clamp': (0, 0, 300), 'boom_clamp_neg': (0, 0, 300), 'clamp_bolts': (0, 0, 380),
           'lift_arm_pos': (0, 120, 200), 'lift_arm_neg': (0, -120, 200), 'counterweight_pos': (0, 120, 200), 'counterweight_neg': (0, -120, 200),
           'yagi_145': (0, 0, 300), 'yagi_435': (0, 0, 300)}
LEGEND = [(c, COLOURS[c]) for c in CATEGORIES]


def _mk4_table():
    """(PARTS, EXPLODE, LEGEND) of the Mk4 replica; instance names and offsets from the last build's scene (a part not yet built lists its snake_case name)."""
    if _HERE not in sys.path:
        sys.path.insert(0, _HERE)
    import mk4_params as MP
    root = os.path.dirname(os.path.dirname(_HERE))
    scene = {}
    for p in (os.path.join(os.environ.get('LSR2_OUT') or root, 'build', 'lsr2_render_scene.json'), os.path.join(root, 'build', 'lsr2_render_scene.json')):
        if os.path.exists(p):
            with open(p, encoding='utf-8') as fh:
                cand = json.load(fh)
            if cand.get('design') == 'mk4':      # a cast-variant scene left in build/ must not feed the mk4 table
                scene = cand
                break
    models = scene.get('part_models', {})
    parts = []
    for p in MP.PARTS + [MP.UNKNOWN]:
        ms = tuple(models.get(p['name']) or (() if p is MP.UNKNOWN else (MP.snake(p['name']),)))
        if ms:
            parts.append(dict(pos=len(parts) + 1, label=p['name'], cat=MACHINED if MP.is_made(p) else BOUGHT, material=p['material'], route=p['process'],
                              qty=len(ms), ref=None, models=ms, colour=MP.COLOURS[p['colour']], colour_cat=p['colour']))
    return parts, {k: tuple(v) for k, v in scene.get('explode', {}).items()}, [(MP.COLOUR_LABEL[c], h) for c, h in MP.COLOURS.items()]


if DESIGN == 'mk4':
    PARTS, EXPLODE, LEGEND = _mk4_table()
BY_MODEL = {m: p for p in PARTS for m in p['models']}


def reload():
    """Re-read the mk4 table from the scene on disk, in place (build.py imports this module before the scene is written, so it may hold a stale one)."""
    if DESIGN != 'mk4':
        return
    parts, explode, legend = _mk4_table()
    PARTS[:] = parts
    LEGEND[:] = legend
    EXPLODE.clear()
    EXPLODE.update(explode)
    BY_MODEL.clear()
    BY_MODEL.update({m: p for p in PARTS for m in p['models']})


def pos_for(ref):
    """Balloon numbers of a BOM key, as text for the Pos column."""
    return ', '.join(str(p['pos']) for p in PARTS if ref and p['ref'] == ref)


def cat_of(model):
    """Category of a CAD model name; pattern models are '<part>_pattern'."""
    return PRINTED if model.endswith('_pattern') else BY_MODEL[model]['cat']


def colour_of(model):
    """Hex colour of a CAD model: its render colour category (mk4) or the category colour."""
    p = BY_MODEL.get(model)
    if p is None and not model.endswith('_pattern'):
        return '#8a8f98'
    return p['colour'] if p and p.get('colour') else COLOURS[cat_of(model)]


def self_test():
    reload()
    assert [p['pos'] for p in PARTS] == list(range(1, len(PARTS) + 1))
    assert len(BY_MODEL) == sum(len(p['models']) for p in PARTS)
    assert all(p['cat'] in CATEGORIES and p['qty'] >= 1 for p in PARTS)
    if DESIGN == 'cast':
        assert sum(len(p['models']) for p in PARTS if p['cat'] == CAST) == 8 and cat_of('body_pattern') == PRINTED
    assert set(EXPLODE) <= set(BY_MODEL), 'exploded offsets for unknown models: %s' % sorted(set(EXPLODE) - set(BY_MODEL))
    print('parts_table self-test OK (%s, %d balloons)' % (DESIGN, len(PARTS)))


if __name__ == '__main__':
    self_test()
