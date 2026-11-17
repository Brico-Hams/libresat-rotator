"""LSR-2 main body: aluminium open box with ribs + removable lid. One finished solid serves route A (casting) and B (CNC).

Frame (mm): origin = centre of the bottom mounting face, z up = AZ axis, x forward (boresight at EL 0), y along the EL axis.
Every number: PARAMETRIC unless noted; bearing/gearbox sizes are DATASHEET (see axes.py / params.NMRV030_GEO).
Run: python body.py  (pure-Python self-test); build.py imports body() and lid() under FreeCAD.
"""
import params as P

W = P.CAST['min_wall']                      # wall / rib thickness from the casting rules
BX = (-50.0, 180.0)                         # outer x extent
BY = 73.0                                   # outer half-width in y
Z_RIM, Z_LID = 314.0, 319.0                 # box rim, lid top
Z_EL = 268.0                                # EL axis height (axes.K['z_el'])
BOSS_Y = 86.0                               # EL bearing boss outer end face (axes.K['boss_y']): the 6004 (y 70..82) and its seal (82..86) sit inside it
Y_CTR = 30.0                                # EL gearbox centre line in y
GASKET = dict(outer=(-49.0, 179.0, 72.0), inner=(-46.0, 176.0, 69.0), depth=2.0)    # lid-underside groove (x0, x1, half-y)
LID_SCREWS = [(-40, -64), (10, -64), (60, -64), (110, -64), (160, -64), (110, 64), (160, 64), (171, -30), (171, 30), (-41, -20)]
GLANDS = [(70.0, -40.0, 14.0, 16.5), (70.0, 40.0, 11.0, 12.5)]      # x, y, boss R, hole d: harness M16 / coax M12
DRAIN = (150.0, 0.0, 4.0)
DRIVER_PAD = dict(x=(54.0, 176.0), z=(20.0, 178.0), t=3.0)          # thermal pad on the inner face of the -y wall (y -BY+W .. -BY+W+t)
NAMEPLATE = dict(y=(-30.0, 30.0), z=(100.0, 122.0), depth=1.0)      # BricoHams plate on the front face (logo per docs/BRANDING.md)
BREATHER = (180.0, -30.0, 250.0, 8.0)                               # front wall, away from the EL sweep at the rear


def self_test():
    assert W >= 5.0 and BY - W > 40.0
    g = GASKET
    assert g['outer'][0] < g['inner'][0] < g['inner'][1] < g['outer'][1] and BY - W <= g['inner'][2] < g['outer'][2] < BY
    assert g['inner'][0] <= BX[0] + W and g['inner'][1] >= BX[1] - W and BX[0] < g['outer'][0] and g['outer'][1] < BX[1]   # groove sits on the wall top
    for x, y in LID_SCREWS:
        assert BX[0] + 4 <= x <= BX[1] - 4 and abs(y) <= BY - 4, (x, y)
    assert Z_LID - Z_RIM == W and Z_EL < Z_RIM - 26
    assert DRIVER_PAD['t'] > 0 and -BY + W + DRIVER_PAD['t'] < -30.0 - W / 2   # pad stays clear of the rib at y = -30
    print('body self-test OK')


def body(blank=False):
    import geom as VP
    box, cyl, fuse, cut = VP.box, VP.cyl, VP.fuse, VP.cut
    x0, x1 = BX
    shell = cut(box(x0, x1, -BY, BY, 0, Z_RIM), [box(x0 + W, x1 - W, -BY + W, BY - W, W, Z_RIM + 1)])
    add = [cyl(44.0, 12.0, (0, 0, -12), (0, 0, 1))]
    add += [cyl(R, 22.0, (x, y, -22), (0, 0, 1)) for x, y, R, _ in GLANDS]
    for x, y in LID_SCREWS:
        add.append(cyl(4.5, Z_RIM - W - 2, (x, y, W), (0, 0, 1)))   # R4.5 overlaps the wall by 0.5: a tangent R4 post made a non-manifold edge
    for y in (-30.0, 30.0, -45.0, 45.0):
        add.append(box(50.0, 172.0, y - W / 2, y + W / 2, W, W + 20.0))
    for s in (-1, 1):
        yo = BY if s > 0 else -BY - 9.0
        add.append(box(70.0, 160.0, yo, yo + 9.0, 10.0, 185.0))
        add.append(cyl(26.0, BOSS_Y - BY + 7.0, (0, s * (BY - 7.0) if s > 0 else -BOSS_Y, Z_EL), (0, 1, 0)))
    add.append(box(*DRIVER_PAD['x'], -BY + W, -BY + W + DRIVER_PAD['t'], *DRIVER_PAD['z']))
    add.append(box(-44.0, 52.0, 58.0, BY - W, 218.0, 310.0))
    add.append(box(-45.0, 60.0, -BY + W, BY - W, 140.0, 148.0))
    add.append(cyl(40.0, 115.0, (0, 0, W), (0, 0, 1)))
    add.append(cyl(BREATHER[3], 6.0, (BREATHER[0], BREATHER[1], BREATHER[2]), (1, 0, 0)))
    s = fuse([shell] + add)
    if blank:                                              # solid before every cut: route A/B clip their stock and fills to it
        return s
    cuts = [cyl(31.0, 115.0 - 15.0, (0, 0, 15.0), (0, 0, 1)), cyl(26.5, 16.0, (0, 0, -8.0), (0, 0, 1)),
            cyl(8.5, 40.0, (0, 0, 100.0), (0, 0, 1)), cyl(10.0, 14.0, (0, 0, 138.0), (0, 0, 1)),
            cyl(DRAIN[2] / 2, 8.0, (DRAIN[0], DRAIN[1], -1.0), (0, 0, 1))]
    cuts += [cyl(d / 2, 30.0, (x, y, -23.0), (0, 0, 1)) for x, y, _, d in GLANDS]
    cuts += [cyl(2.1, 14.0, (x, y, Z_RIM - 14.0), (0, 0, 1)) for x, y in LID_SCREWS]
    for sgn in (-1, 1):                                    # EL bearing seats (6004) open to the cavity (fitted from inside, circlip inside) + seal bores
        ya = sgn * 66.0
        cuts.append(cyl(21.0, 16.0, (0, ya if sgn > 0 else ya - 16.0, Z_EL), (0, 1, 0)))
        cuts.append(cyl(16.0, 4.0, (0, sgn * 82.0 if sgn > 0 else -86.0, Z_EL), (0, 1, 0)))
        cuts.append(cyl(11.0, 20.0, (0, (BY - 18.0) if sgn > 0 else -BY - 2.0, Z_EL), (0, 1, 0)))
    s = cut(s, cuts)
    s = VP.soft(s, lambda r, e: s.makeFillet(r, e), 3.0, lambda e: abs(e.Vertexes[0].Point.z - e.Vertexes[-1].Point.z) > 100.0 and e.Length > 100)
    return s


def lid(blank=False):
    import geom as VP
    box, cyl, cut = VP.box, VP.cyl, VP.cut
    x0, x1 = BX
    s = box(x0, x1, -BY, BY, Z_RIM, Z_LID)
    if blank:
        return s
    g = GASKET
    ring = cut(box(g['outer'][0], g['outer'][1], -g['outer'][2], g['outer'][2], Z_RIM, Z_RIM + g['depth']),
               [box(g['inner'][0], g['inner'][1], -g['inner'][2], g['inner'][2], Z_RIM - 1, Z_RIM + g['depth'] + 1)])
    s = cut(s, [ring] + [cyl(2.75, W + 2, (x, y, Z_RIM - 1), (0, 0, 1)) for x, y in LID_SCREWS])
    return s


if __name__ == '__main__':
    self_test()
