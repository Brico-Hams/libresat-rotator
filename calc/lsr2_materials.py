#!/usr/bin/env python3
"""LSR-2 material and cost budget: CNC plate nesting, sand-casting stock, PLA patterns/prototype.

Writes docs/LSR2_MATERIALS.md. Geometry comes from cad/lsr2/plates.py, process data from params.py.
`python calc/lsr2_materials.py --check` runs the self-test only.
"""
import json, math, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'cad', 'lsr2'))
import params as P  # noqa: E402
import plates as PL  # noqa: E402
import cast_parts as CP  # noqa: E402

PRICE_PLATE_EUR_KG = 9.0    # 6061-T6 plate, full sheet: VERIFY with a quote
PRICE_PLATE_CUT_EUR_KG = 14.0   # same, cut to size (blank + margin per side): VERIFY with a quote
CUT_EUR_PER_M = 1.5         # CNC cutting estimate per metre of cut path: VERIFY
PRICE_A356_EUR_KG = 4.5     # A356 ingot: VERIFY
FOUNDRY_EUR_KG = 8.0        # outsourced sand casting, per kg of casting: VERIFY
OUTSOURCED = True
YIELD = 0.55                # casting mass / poured metal (gating and risers): VERIFY with the foundry
SHEET = (1000.0, 500.0)     # standard sheet, mm: VERIFY
MARGIN, KERF = 10.0, 3.0    # blank margin per side, nesting kerf (mm)
PLA_INFILL, PLA_WALL_CM = 0.30, 0.12
ESTIMATES = {'az_housing': (350.0, 120.0), 'el_bearing_housing': (117.0, 129.0), 'boom_socket': (131.0, 39.0)}   # (finished cm3, machined cm2): ESTIMATE
PRICE_SS_EUR_KG = 6.0       # 1.4404 round bar: VERIFY
SS_G_CM3 = CP.SS_G_CM3
PRICE_PLA_EUR_KG = 20.0     # VERIFY
PRICE_TUBE_EUR_KG = 8.0     # 6063 square tube 40x40x3: VERIFY
BOUGHT = [                  # (item, qty, unit EUR): every price VERIFY with a quote
    ('NMRV030 worm gearbox 80:1, Ø14 hollow', 2, 55.0), ('NEMA23 stepper 2.8 N·m', 2, 18.0), ('6206-2RS bearing (AZ pair + EL pair)', 4, 3.5),
    ('51206 thrust bearing', 1, 6.0), ('Keys DIN 6885 (2x 5x5, 1x 8x7)', 3, 0.5),
    ('M6 U-bolts for the Yagi boom', 4, 1.5), ('M8 U-bolts for the mast', 2, 2.5), ('V-ring seals (AZ + EL VA15/20) + Ø6 cross pin', 1, 3.0),
    ('DIN 471 Ø30 circlip + 3 mm ring under the 51206 (cheaper than a DIN 705 Ø30 set collar, ~4 EUR)', 1, 0.8),
    ('AZ top retaining collar: DIN 705 Ø14 flanged set collar + M6 screw (cheaper than a turned disc)', 1, 2.5),
    ('M8 through-bolts + nuts + washers, boom in the socket (2 sets)', 1, 1.0), ('M6 screws, motors/gearboxes/bracket/hub/housing (about 40)', 1, 4.0),
    ('EL bearing circlips: 2x DIN 471 Ø30 + 2x DIN 472 Ø62', 1, 1.2)]
REPORT = os.path.join(ROOT, 'build', 'lsr2_build_report.json')


def load_report():
    if os.path.exists(REPORT):
        with open(REPORT, encoding='utf-8') as fh:
            r = json.load(fh)
        if 'cast' in r and 'shafts' in r:
            return r
    return None


def finished_area_mm2(size, holes):
    return size[0] * size[1] - sum(math.pi * d * d / 4 for _, _, d in holes)


def cut_length_mm(size, holes):
    return 2 * (size[0] + size[1]) + sum(math.pi * d for _, _, d in holes)


def nest(items, sheet=SHEET, kerf=KERF):
    """Shelf packing of rectangles [(w, h)] on identical sheets; returns the number of sheets."""
    pieces = sorted(((max(w, h) + kerf, min(w, h) + kerf) for w, h in items), key=lambda r: -r[1])
    sheets = []                                  # each sheet: list of shelves [height, used width]
    for w, h in pieces:
        assert w <= sheet[0] and h <= sheet[1], 'blank larger than the sheet'
        for shelves in sheets:
            hit = next((s for s in shelves if h <= s[0] and s[1] + w <= sheet[0]), None)
            if hit:
                hit[1] += w
                break
            if sum(s[0] for s in shelves) + h <= sheet[1]:
                shelves.append([h, w])
                break
        else:
            sheets.append([[h, w]])
    return len(sheets)


def tube_kg():
    w, h, t = P.CROSS_BOOM
    return (w * h - (w - 2 * t) * (h - 2 * t)) * P.CROSS_BOOM_L * 2.70e-6   # 6063, 2.70 g/cm3


def plate_rows():
    rows = []
    for name, p in PL.PLATES.items():
        size = (p['u'][1] - p['u'][0], p['v'][1] - p['v'][0])
        cuts = p['holes']
        area = finished_area_mm2(size, cuts)
        cut = cut_length_mm(size, cuts)
        blank = (size[0] + 2 * MARGIN, size[1] + 2 * MARGIN)
        fin_g = area * p['t'] * P.ALU_PLATE_G_CM3 * 1e-3
        blank_g = blank[0] * blank[1] * p['t'] * P.ALU_PLATE_G_CM3 * 1e-3
        rows.append(dict(name=name, t=p['t'], area_cm2=area / 100, fin_g=fin_g, blank=blank, blank_g=blank_g,
                         waste=100 * (1 - fin_g / blank_g), cut_m=cut / 1000,
                         vol_cm3=area * p['t'] / 1000, surf_cm2=(2 * area + cut * p['t']) / 100))
    return rows


def plate_totals():
    """Per thickness: the cheaper of full sheets (PRICE_PLATE_EUR_KG) and cut-to-size blanks (PRICE_PLATE_CUT_EUR_KG)."""
    rows = plate_rows()
    sheets = {}
    for t in sorted({r['t'] for r in rows}):
        n = nest([r['blank'] for r in rows if r['t'] == t])
        full_kg = n * SHEET[0] * SHEET[1] * t * P.ALU_PLATE_G_CM3 * 1e-6
        cut_kg = sum(r['blank_g'] for r in rows if r['t'] == t) / 1000
        full_eur, cut_eur = full_kg * PRICE_PLATE_EUR_KG, cut_kg * PRICE_PLATE_CUT_EUR_KG
        choice = 'cut-to-size' if cut_eur < full_eur else 'full sheet'
        sheets[t] = dict(n=n, full_kg=full_kg, full_eur=full_eur, cut_kg=cut_kg, cut_eur=cut_eur, choice=choice,
                         kg=cut_kg if choice == 'cut-to-size' else full_kg, eur=min(full_eur, cut_eur))
    stock_kg = sum(s['kg'] for s in sheets.values())
    fin_kg = sum(r['fin_g'] for r in rows) / 1000
    cut_m = sum(r['cut_m'] for r in rows)
    return dict(rows=rows, sheets=sheets, stock_kg=stock_kg, fin_kg=fin_kg, waste=100 * (1 - fin_kg / stock_kg), cut_m=cut_m,
                stock_eur=sum(s['eur'] for s in sheets.values()), cost=sum(s['eur'] for s in sheets.values()) + cut_m * CUT_EUR_PER_M)


def pla_g(volume_cm3, surface_cm2):
    """PLA mass: solid walls plus 30 % infill inside (approximation)."""
    shell = min(volume_cm3, surface_cm2 * PLA_WALL_CM)
    return (shell + PLA_INFILL * (volume_cm3 - shell)) * P.PLA_G_CM3


def casting_budget(name, finished_volume_cm3, machined_area_cm2, yield_=YIELD, outsourced=OUTSOURCED, extra_cm3=0.0):
    """extra_cm3: metal in bores that are cast solid and bored out later."""
    c = P.CAST
    pattern = (finished_volume_cm3 + extra_cm3 + machined_area_cm2 * c['machining'] / 10) * c['shrink'] ** 3
    mass_g = pattern * P.ALU_CAST_G_CM3
    poured_g = mass_g / yield_
    surf = 6 * pattern ** (2 / 3)               # cube-equivalent surface of the pattern
    cost = poured_g / 1000 * PRICE_A356_EUR_KG + (mass_g / 1000 * FOUNDRY_EUR_KG if outsourced else 0.0)
    return dict(name=name, finished=finished_volume_cm3, pattern_cm3=pattern, mass_g=mass_g, poured_g=poured_g,
                pla_g=pla_g(pattern, surf), cost=cost, machined=machined_area_cm2, estimate=True)


def cast_rows():
    """One casting budget per cast part: real CAD values from the build report, else the ESTIMATE rows."""
    rep = load_report()
    if not rep:
        return [casting_budget(n, *v) for n, v in ESTIMATES.items()], [], None
    rows, pats = [], {}
    for n, v in rep['cast'].items():
        c = casting_budget(n, v['volume_cm3'], v['machined_area_cm2'], extra_cm3=v['bore_solid_cm3'])
        c.update(estimate=False, cad_mass_g=v['mass_g'])
        rows.append(c)
        pats[v['pattern']] = (v['pattern_volume_cm3'], v['pattern_area_cm2'])
    cb = rep.get('core_box', {}).get('volume_cm3', 0.0)
    pats['az_housing_corebox'] = (cb, 6 * cb ** (2 / 3))
    return rows, [(n, v, a, pla_g(v, a)) for n, (v, a) in pats.items()], rep


def shaft_rows():
    rep = load_report()
    rows = []
    for n, segs in CP.SHAFTS.items():
        d, ln = CP.shaft_stock(segs)
        fin = rep['shafts'][n]['mass_g'] if rep else CP.shaft_volume_cm3(segs, CP.SHAFT_BORES[n]) * SS_G_CM3
        stock = math.pi * d * d / 4 * ln / 1000 * SS_G_CM3
        rows.append(dict(name=n, d=d, l=ln, stock_g=stock, fin_g=fin, cost=stock / 1000 * PRICE_SS_EUR_KG))
    return rows


def totals():
    pt = plate_totals()
    cast, pats, rep = cast_rows()
    shafts = shaft_rows()
    proto = sum(pla_g(r['vol_cm3'], r['surf_cm2']) for r in pt['rows'])
    pat_g = sum(p[3] for p in pats) if pats else sum(c['pla_g'] for c in cast)
    bought = sum(q * u for _, q, u in BOUGHT) + tube_kg() * PRICE_TUBE_EUR_KG
    al_kg = pt['stock_kg'] + sum(c['poured_g'] for c in cast) / 1000
    fin_kg = pt['fin_kg'] + sum(c['finished'] * P.ALU_CAST_G_CM3 for c in cast) / 1000
    ss_kg = sum(s['stock_g'] for s in shafts) / 1000
    pla_kg = (pat_g + proto) / 1000
    cost = (pt['cost'] + sum(c['cost'] for c in cast) + ss_kg * PRICE_SS_EUR_KG + pla_kg * PRICE_PLA_EUR_KG)
    return dict(plates=pt, cast=cast, patterns=pats, shafts=shafts, proto_g=proto, pat_g=pat_g, al_kg=al_kg, fin_kg=fin_kg,
                ss_kg=ss_kg, pla_kg=pla_kg, cost=cost, bought=bought, total=cost + bought, real=rep is not None)


def report():
    t = totals()
    pt = t['plates']
    o = ['# BricoHams · LibreSat LSR-2: materials and cost budget (generated by calc/lsr2_materials.py)', '',
         '<!-- palette: blue #12263f, orange #e8871e -->',
         'Authors: Anatol EA5KAO, Diego EA5JEF, Pedro Roca Molina.', '',
         'Goal: light and cheap. All plates are 8 mm, no lightening holes (cad/lsr2/plates.py). '
         'Prices, yield and sheet size are generic: **VERIFY** with local quotes.', '',
         f'Parameters (VERIFY): full sheet {PRICE_PLATE_EUR_KG} EUR/kg ({P.PLATE["alloy"]}), cut-to-size {PRICE_PLATE_CUT_EUR_KG} EUR/kg '
         f'(blank + margin), cutting {CUT_EUR_PER_M} EUR/m, '
         f'A356 ingot {PRICE_A356_EUR_KG} EUR/kg, foundry {FOUNDRY_EUR_KG} EUR/kg, yield {YIELD}, sheet {SHEET[0]:g}x{SHEET[1]:g} mm, '
         f'blank margin {MARGIN:g} mm, kerf {KERF:g} mm.', '',
         '## CNC plates (one head)', '',
         '| Plate | t (mm) | Finished area (cm²) | Finished mass (g) | Blank (mm) | Blank mass (g) | Waste (%) | Cut path (m) |',
         '|---|---|---|---|---|---|---|---|']
    for r in pt['rows']:
        o.append(f"| {r['name']} | {r['t']:g} | {r['area_cm2']:.0f} | {r['fin_g']:.0f} | {r['blank'][0]:.0f}x{r['blank'][1]:.0f} | "
                 f"{r['blank_g']:.0f} | {r['waste']:.0f} | {r['cut_m']:.2f} |")
    o += ['', '| Thickness (mm) | Full sheets | Full sheet kg / EUR | Cut-to-size kg / EUR | Choice |', '|---|---|---|---|---|']
    o += [f"| {k:g} | {s['n']} | {s['full_kg']:.2f} / {s['full_eur']:.0f} | {s['cut_kg']:.2f} / {s['cut_eur']:.0f} | **{s['choice']}** |"
          for k, s in pt['sheets'].items()]
    o += ['', f"Plate stock {pt['stock_kg']:.2f} kg for {pt['fin_kg']:.2f} kg finished: total waste {pt['waste']:.0f} %. "
          f"Cost: stock {pt['stock_eur']:.0f} EUR + cutting {pt['cut_m'] * CUT_EUR_PER_M:.0f} EUR "
          f"= **{pt['cost']:.0f} EUR** (the cheaper option per thickness; the choice follows automatically from the prices above).", '',
          '## Sand casting, phase 3 parts' + ('' if t['real'] else ': ESTIMATE (no build report yet, run `make lsr2`)'), '',
          f"Casting metal = (finished + metal in bores cast solid + machined area x {P.CAST['machining']} mm) x shrink^3 "
          f"({P.CAST['shrink']}) at {P.ALU_CAST_G_CM3} g/cm³ (A356); poured metal = casting / {YIELD}. "
          f"Volumes and machined areas come from build/lsr2_build_report.json. "
          f"PLA at {P.PLA_G_CM3} g/cm³, {PLA_INFILL * 100:.0f} % infill, {PLA_WALL_CM * 10:.1f} mm walls.", '',
          '| Part | Finished (cm³) | Machined (cm²) | Casting (g) | Poured (g) | Cost (EUR) |', '|---|---|---|---|---|---|']
    tag = '' if t['real'] else ' (ESTIMATE)'
    for c in t['cast']:
        o.append(f"| {c['name']}{tag} | {c['finished']:.0f} | {c['machined']:.0f} | {c['mass_g']:.0f} | {c['poured_g']:.0f} | {c['cost']:.1f} |")
    o += ['', '| PLA pattern / core box (printed once) | Volume (cm³) | Surface (cm²) | PLA (g) |', '|---|---|---|---|']
    o += [f'| {n} | {v:.0f} | {a:.0f} | {g:.0f} |' for n, v, a, g in t['patterns']]
    if not t['patterns']:
        o.append(f"| patterns (ESTIMATE) | | | {t['pat_g']:.0f} |")
    o += ['', '## Turned shafts (stainless 1.4404)', '',
          f'Stock = finished length + 10 mm, diameter = largest step + 3 mm; {SS_G_CM3} g/cm³; {PRICE_SS_EUR_KG} EUR/kg (VERIFY).', '',
          '| Shaft | Stock Ø x L (mm) | Stock (g) | Finished (g) | Cost (EUR) |', '|---|---|---|---|---|']
    o += [f"| {s['name']} | {s['d']:g} x {s['l']:g} | {s['stock_g']:.0f} | {s['fin_g']:.0f} | {s['cost']:.1f} |" for s in t['shafts']]
    o += ['', 'Dimension tables (axis coordinate from the head frame: z for az_shaft, y for el_shaft):', '',
          '| Shaft | From (mm) | To (mm) | Ø (mm) |', '|---|---|---|---|']
    o += [f'| {n} | {lo:g} | {hi:g} | {d:g} |' for n, segs in CP.SHAFTS.items() for lo, hi, d in segs]
    o += ['', 'az_shaft: HOLLOW, Ø16 bore from the bottom end to z=-1 (stops below the Ø14 step, which stays solid), Ø6 radial cable exit '
          'at z=-4; cables run up the AZ axis, no wrap round the mast. Ø14 h7 x 80 keyed top (key 5x5, slot 40 long) into the gearbox '
          'hollow output and up to the flanged retaining collar (DIN 705 Ø14, M6 set screw), Ø30 bearing seats, no integral collar (the 51206 shaft '
          'washer rests on a DIN 471 circlip + 3 mm ring, see bought '
          'parts), Ø30 bottom in the mast clamp with a Ø6 cross-pin hole. Stock is solid bar drilled from the bottom end (gun drill, '
          'VERIFY with the machinist); stock mass above is the full bar. el_shaft: Ø14 h7 through the EL gearbox hub (key 5, torque only) and 37 mm '
          'beyond it, Ø30 through the two 6206 of the el_bearing_housing (DIN 471 circlips) to the boom_socket hub (key 8x7). Cross-boom tube 6063 '
          f'{P.CROSS_BOOM[0]}x{P.CROSS_BOOM[1]}x{P.CROSS_BOOM[2]} x {P.CROSS_BOOM_L} mm = {tube_kg():.2f} kg (included in the bought-part total). '
          'Files: cnc/lsr2/az_shaft.step, cnc/lsr2/el_shaft.step.', '',
          '## Bought parts (every price VERIFY)', '', '| Item | Qty | Unit (EUR) | Total (EUR) |', '|---|---|---|---|']
    o += [f'| {n} | {q} | {u:.2f} VERIFY | {q * u:.2f} |' for n, q, u in BOUGHT]
    o += ['', f"Full 1:1 PLA prototype of all plates: {t['proto_g'] / 1000:.2f} kg.", '', '## Totals', '',
          '| Item | Value |', '|---|---|',
          f"| Aluminium bought (plate + poured ingot) | {t['al_kg']:.2f} kg |",
          f"| Stainless bar (shafts) | {t['ss_kg']:.2f} kg |",
          f"| PLA (patterns + prototype) at {PRICE_PLA_EUR_KG:g} EUR/kg VERIFY | {t['pla_kg']:.2f} kg |",
          f"| Material + cutting + foundry + PLA cost (VERIFY) | {t['cost']:.0f} EUR |",
          f"| Bought parts (VERIFY) | {t['bought']:.0f} EUR |",
          f"| Total estimated cost (VERIFY) | {t['total']:.0f} EUR |",
          f"| Finished head mass (plates + cast parts, without shafts and bought parts) | {t['fin_kg']:.2f} kg |",
          f"| Finished / bought aluminium | {100 * t['fin_kg'] / t['al_kg']:.0f} % |", '']
    return '\n'.join(o)


def self_test():
    # hand check: 100x50 plate with one 10 mm hole: 5000 - pi*25 = 4921.46 mm2; cut path 300 + 31.416 mm
    assert abs(finished_area_mm2((100, 50), [(0, 0, 10)]) - 4921.46) < 0.01
    assert abs(cut_length_mm((100, 50), [(0, 0, 10)]) - 331.416) < 0.01
    # hand check: 100 cm3 finished, no machining: 100 * 1.013^3 = 103.951 cm3 pattern; * 2.68 = 278.59 g; / 0.55 = 506.52 g
    c = casting_budget('t', 100.0, 0.0)
    assert abs(c['pattern_cm3'] - 103.951) < 0.01 and abs(c['mass_g'] - 278.59) < 0.05 and abs(c['poured_g'] - 506.52) < 0.1
    # with 100 cm2 machined at 2.5 mm: 125 cm3 before shrink
    assert abs(casting_budget('t', 100.0, 100.0)['pattern_cm3'] - 125 * 1.013 ** 3) < 1e-6
    assert nest([(390, 200)] * 2) == 1 and nest([(990, 490)] * 2) == 2
    # hand check, shaft Ø30 x 100: bar Ø33 x 110 = pi*16.5^2*110 = 94.083 cm3 -> 747.96 g at 7.95; finished 70.686 cm3 -> 561.95 g
    d, ln = CP.shaft_stock([(0, 100, 30)])
    assert abs(math.pi * d * d / 4 * ln / 1000 * SS_G_CM3 - 747.96) < 0.05
    assert abs(CP.shaft_volume_cm3([(0, 100, 30)]) * SS_G_CM3 - 561.95) < 0.05
    # hand check, tube Ø30/Ø16 x 100: pi*(225-64)*100 = 50.580 cm3 -> 402.1 g finished (the bar stock above stays solid)
    assert abs(CP.shaft_volume_cm3([(0, 100, 30)], [(0, 100, 16)]) * SS_G_CM3 - 402.1) < 0.05
    assert CP.shaft_stock(CP.AZ_SHAFT) == (33.0, 316.0) and 'az_shaft' in CP.SHAFT_BORES
    assert abs(tube_kg() - 1.319) < 0.002      # hand check: (1600 - 1156) mm2 x 1100 mm x 2.70 g/cm3
    assert abs(casting_budget('t', 100.0, 0.0, extra_cm3=10.0)['pattern_cm3'] - 110 * 1.013 ** 3) < 1e-6
    pt = plate_totals()
    for r in pt['rows']:
        assert abs(r['fin_g'] - PL.mass_g(r['name'])) < 0.01, r['name']
    assert pt['stock_kg'] > pt['fin_kg'] and pt['cost'] > 0
    for s in pt['sheets'].values():
        assert s['eur'] == min(s['full_eur'], s['cut_eur']) and s['kg'] == (s['cut_kg'] if s['choice'] == 'cut-to-size' else s['full_kg'])


if __name__ == '__main__':
    self_test()
    if '--check' in sys.argv:
        print('lsr2_materials self-test OK')
        sys.exit(0)
    with open(os.path.join(ROOT, 'docs', 'LSR2_MATERIALS.md'), 'w', encoding='utf-8') as fh:
        fh.write(report())
    print('wrote docs/LSR2_MATERIALS.md')
