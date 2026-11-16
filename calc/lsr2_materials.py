#!/usr/bin/env python3
"""LSR-2 material and cost budget: CNC plate nesting, sand-casting stock, PLA patterns/prototype.

Writes docs/LSR2_MATERIALS.md. Geometry comes from cad/lsr2/plates.py, process data from params.py.
`python calc/lsr2_materials.py --check` runs the self-test only.
"""
import math, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'cad', 'lsr2'))
import params as P  # noqa: E402
import plates as PL  # noqa: E402

PRICE_PLATE_EUR_KG = 9.0    # 6061-T6 plate: VERIFY with a quote
CUT_EUR_PER_M = 1.5         # CNC cutting estimate per metre of cut path: VERIFY
PRICE_A356_EUR_KG = 4.5     # A356 ingot: VERIFY
FOUNDRY_EUR_KG = 8.0        # outsourced sand casting, per kg of casting: VERIFY
OUTSOURCED = True
YIELD = 0.55                # casting mass / poured metal (gating and risers): VERIFY with the foundry
SHEET = (1000.0, 500.0)     # standard sheet, mm: VERIFY
MARGIN, KERF = 10.0, 3.0    # blank margin per side, nesting kerf (mm)
PLA_INFILL, PLA_WALL_CM = 0.30, 0.12
ESTIMATES = {'az_housing': (350.0, 120.0), 'el_hub': (120.0, 60.0)}   # (finished cm3, machined cm2): ESTIMATE


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


def plate_rows():
    rows = []
    for name, p in PL.PLATES.items():
        cuts = PL.cutouts(p)
        area = finished_area_mm2(p['size'], cuts)
        cut = cut_length_mm(p['size'], cuts)
        blank = (p['size'][0] + 2 * MARGIN, p['size'][1] + 2 * MARGIN)
        fin_g = area * p['t'] * P.ALU_PLATE_G_CM3 * 1e-3
        blank_g = blank[0] * blank[1] * p['t'] * P.ALU_PLATE_G_CM3 * 1e-3
        rows.append(dict(name=name, t=p['t'], area_cm2=area / 100, fin_g=fin_g, blank=blank, blank_g=blank_g,
                         waste=100 * (1 - fin_g / blank_g), cut_m=cut / 1000,
                         vol_cm3=area * p['t'] / 1000, surf_cm2=(2 * area + cut * p['t']) / 100))
    return rows


def plate_totals():
    rows = plate_rows()
    sheets = {}
    for t in sorted({r['t'] for r in rows}):
        n = nest([r['blank'] for r in rows if r['t'] == t])
        sheets[t] = (n, n * SHEET[0] * SHEET[1] * t * P.ALU_PLATE_G_CM3 * 1e-6)   # sheets, stock kg
    stock_kg = sum(k for _, k in sheets.values())
    fin_kg = sum(r['fin_g'] for r in rows) / 1000
    cut_m = sum(r['cut_m'] for r in rows)
    return dict(rows=rows, sheets=sheets, stock_kg=stock_kg, fin_kg=fin_kg, waste=100 * (1 - fin_kg / stock_kg), cut_m=cut_m,
                cost=stock_kg * PRICE_PLATE_EUR_KG + cut_m * CUT_EUR_PER_M)


def pla_g(volume_cm3, surface_cm2):
    """PLA mass: solid walls plus 30 % infill inside (approximation)."""
    shell = min(volume_cm3, surface_cm2 * PLA_WALL_CM)
    return (shell + PLA_INFILL * (volume_cm3 - shell)) * P.PLA_G_CM3


def casting_budget(name, finished_volume_cm3, machined_area_cm2, yield_=YIELD, outsourced=OUTSOURCED):
    c = P.CAST
    pattern = (finished_volume_cm3 + machined_area_cm2 * c['machining'] / 10) * c['shrink'] ** 3
    mass_g = pattern * P.ALU_CAST_G_CM3
    poured_g = mass_g / yield_
    surf = 6 * pattern ** (2 / 3)               # cube-equivalent surface of the pattern
    cost = poured_g / 1000 * PRICE_A356_EUR_KG + (mass_g / 1000 * FOUNDRY_EUR_KG if outsourced else 0.0)
    return dict(name=name, finished=finished_volume_cm3, pattern_cm3=pattern, mass_g=mass_g, poured_g=poured_g,
                pla_g=pla_g(pattern, surf), cost=cost)


def totals():
    pt = plate_totals()
    cast = [casting_budget(n, *v) for n, v in ESTIMATES.items()]
    proto = sum(pla_g(r['vol_cm3'], r['surf_cm2']) for r in pt['rows'])
    al_kg = pt['stock_kg'] + sum(c['poured_g'] for c in cast) / 1000
    fin_kg = pt['fin_kg'] + sum(c['finished'] * P.ALU_CAST_G_CM3 for c in cast) / 1000
    pla_kg = (sum(c['pla_g'] for c in cast) + proto) / 1000
    cost = pt['cost'] + sum(c['cost'] for c in cast)
    return dict(plates=pt, cast=cast, proto_g=proto, al_kg=al_kg, fin_kg=fin_kg, pla_kg=pla_kg, cost=cost)


def report():
    t = totals()
    pt = t['plates']
    o = ['# BricoHams · LibreSat LSR-2: materials and cost budget (generated by calc/lsr2_materials.py)', '',
         '<!-- palette: blue #12263f, orange #e8871e -->',
         'Authors: Anatol EA5KAO, Diego EA5JEF, Pedro Roca Molina.', '',
         'Goal: light and cheap. Plates are 8 mm (top 6 mm) with lightening holes (cad/lsr2/plates.py). '
         'Prices, yield and sheet size are generic: **VERIFY** with local quotes.', '',
         f'Parameters (VERIFY): plate {PRICE_PLATE_EUR_KG} EUR/kg ({P.PLATE["alloy"]}), cutting {CUT_EUR_PER_M} EUR/m, '
         f'A356 ingot {PRICE_A356_EUR_KG} EUR/kg, foundry {FOUNDRY_EUR_KG} EUR/kg, yield {YIELD}, sheet {SHEET[0]:g}x{SHEET[1]:g} mm, '
         f'blank margin {MARGIN:g} mm, kerf {KERF:g} mm.', '',
         '## CNC plates (one head)', '',
         '| Plate | t (mm) | Finished area (cm²) | Finished mass (g) | Blank (mm) | Blank mass (g) | Waste (%) | Cut path (m) |',
         '|---|---|---|---|---|---|---|---|']
    for r in pt['rows']:
        o.append(f"| {r['name']} | {r['t']:g} | {r['area_cm2']:.0f} | {r['fin_g']:.0f} | {r['blank'][0]:.0f}x{r['blank'][1]:.0f} | "
                 f"{r['blank_g']:.0f} | {r['waste']:.0f} | {r['cut_m']:.2f} |")
    o += ['', '| Thickness (mm) | Sheets | Stock mass (kg) |', '|---|---|---|']
    o += [f'| {k:g} | {n} | {kg:.2f} |' for k, (n, kg) in pt['sheets'].items()]
    o += ['', f"Plate stock {pt['stock_kg']:.2f} kg for {pt['fin_kg']:.2f} kg finished: total waste {pt['waste']:.0f} %. "
          f"Cost: stock {pt['stock_kg'] * PRICE_PLATE_EUR_KG:.0f} EUR + cutting {pt['cut_m'] * CUT_EUR_PER_M:.0f} EUR "
          f"= **{pt['cost']:.0f} EUR** (full sheets bought; a cut-to-size supplier lowers it).", '',
          '## Sand casting, phase 3 parts: ESTIMATE until phase 3 CAD exists', '',
          f"Pattern volume = (finished + machined area x {P.CAST['machining']} mm) x shrink^3 ({P.CAST['shrink']}); "
          f"casting mass at {P.ALU_CAST_G_CM3} g/cm³ (A356); poured metal = casting / {YIELD}. "
          f"PLA at {P.PLA_G_CM3} g/cm³, {PLA_INFILL * 100:.0f} % infill, {PLA_WALL_CM * 10:.1f} mm walls.", '',
          '| Part (ESTIMATE) | Finished (cm³) | Machined (cm²) | Pattern (cm³) | Casting (g) | Poured (g) | PLA pattern (g) | Cost (EUR) |',
          '|---|---|---|---|---|---|---|---|']
    for c in t['cast']:
        o.append(f"| {c['name']} | {c['finished']:.0f} | {ESTIMATES[c['name']][1]:.0f} | {c['pattern_cm3']:.0f} | "
                 f"{c['mass_g']:.0f} | {c['poured_g']:.0f} | {c['pla_g']:.0f} | {c['cost']:.1f} |")
    o += ['', f"Full 1:1 PLA prototype of all plates: {t['proto_g'] / 1000:.2f} kg.", '', '## Totals', '',
          '| Item | Value |', '|---|---|',
          f"| Aluminium bought (plate + ingot) | {t['al_kg']:.2f} kg |",
          f"| PLA (patterns + prototype) | {t['pla_kg']:.2f} kg |",
          f"| Estimated material + cutting + foundry cost | {t['cost']:.0f} EUR |",
          f"| Finished head mass (plates + cast parts, without bought parts) | {t['fin_kg']:.2f} kg |",
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
    pt = plate_totals()
    for r in pt['rows']:
        assert abs(r['fin_g'] - PL.mass_g(r['name'])) < 0.01, r['name']
    assert pt['stock_kg'] > pt['fin_kg'] and pt['cost'] > 0


if __name__ == '__main__':
    self_test()
    if '--check' in sys.argv:
        print('lsr2_materials self-test OK')
        sys.exit(0)
    with open(os.path.join(ROOT, 'docs', 'LSR2_MATERIALS.md'), 'w', encoding='utf-8') as fh:
        fh.write(report())
    print('wrote docs/LSR2_MATERIALS.md')
