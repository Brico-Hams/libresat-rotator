#!/usr/bin/env python3
"""LSR-2 phase 11 material and cost budget: per-route (A cast / B CNC) metal, waste, PLA, machining time and cost per structural part,
the route comparison with the cheaper default route per part, turned shafts and bought parts.

Writes docs/LSR2_MATERIALS.md. Geometry comes from build/lsr2_build_report.json (key `parts`), process data from cad/lsr2/params.py.
`python calc/lsr2_materials.py --check` runs the self-test only. Every price and rate is PARAMETRIC / VERIFY with a quote.
"""
import json, math, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'cad', 'lsr2'))
import params as P  # noqa: E402
import axes as AX  # noqa: E402

C = P.CNC
PRICE_A356_EUR_KG = 4.5     # PARAMETRIC (VERIFY): A356 ingot
FOUNDRY_EUR_KG = 8.0        # PARAMETRIC (VERIFY): outsourced sand casting, per kg of casting
YIELD = 0.55                # PARAMETRIC: casting mass / poured metal (gating and risers), to agree with the foundry
PRICE_SS_EUR_KG = 6.0       # PARAMETRIC (VERIFY): 1.4404 round bar
PRICE_PLA_EUR_KG = 20.0     # PARAMETRIC (VERIFY)
PRICE_TUBE_EUR_KG = 8.0     # PARAMETRIC (VERIFY): 6063 square tube 40x40x3
A_SETUPS = 2                # PARAMETRIC: machining set-ups of a cast part (datums + faces, then seats and threads)
TIE = 0.05                  # costs within 5 % count as equal: the lighter route wins (light and cheap)
BOUGHT = [                  # (item, qty, unit EUR): every price VERIFY with a quote
    ('NMRV030 worm gearbox 80:1, Ø14 hollow', 2, 55.0), ('NEMA23 stepper 57BYG250H-8 2.8 N·m', 2, 18.0),
    ('6206-2RS bearing (AZ pair)', 2, 3.5), ('6004-2RS bearing (EL pair, one each side of the body)', 2, 2.5),
    ('51206 thrust bearing', 1, 6.0), ('Keys DIN 6885 (2x 5x5, 1x 6x6)', 3, 0.5),
    ('M6 U-bolts for the Yagi boom', 4, 1.5), ('M8 U-bolts for the mast', 2, 2.5), ('V-ring seals (AZ + EL) + Ø6 cross pin', 1, 3.0),
    ('DIN 471 Ø30 circlip + M30x56x3 stainless washer shim(s) under the 51206 (Mk5 shim)', 2, 0.7),
    ('AZ top retaining collar: DIN 705 Ø14 flanged set collar + M6 screw', 1, 2.5),
    ('M6 screws, motors/gearboxes/yoke/lid (about 60)', 1, 6.0),
    ('EL bearing circlips: 2x DIN 472 Ø42 + AZ seat circlips', 1, 1.2),
    ('Lid gasket cord + 2x slotted photo-interrupter (EE-SX1103 class, index; actuator design open)', 1, 7.0)]
REPORT = os.path.join(ROOT, 'build', 'lsr2_build_report.json')
PARTS = ('body', 'lid', 'mast_bracket', 'yoke_arm', 'saddle', 'boom_clamp')
# Phase 7: own gearbox LSR-WG30 (cad/lsr2/gearbox.py) vs the bought NMRV030; every price VERIFY with a quote
GB_GEARSET = ('Worm Ø20 hardened steel + CuSn12 wheel z80 m0.5 (catalogue pair, quote)', 1, 25.0)
GB_HARDWARE = [('61905-2RS wheel bearing 25x42x9', 2, 3.0), ('6003-2RS worm bearing 17x35x10', 2, 1.5), ('Lip seal TC 25x42x7 (output)', 2, 0.6),
               ('Lip seal TC 17x30x7 (input)', 1, 0.5), ('M5 socket screws (joint)', 4, 0.1), ('Dowel pin Ø5 ISO 8734', 2, 0.15),
               ('Circlip Ø17 + shim set (worm backlash)', 2, 0.3), ('Grease NLGI 00 + sealant', 1, 0.8), ('Input key 4x4', 1, 0.3)]
GB_FINISH_MIN = 20.0        # PARAMETRIC: machining minutes per unit beyond the stock pads (bearing seats, bores, joint faces, taps, dowel holes)
GB_JIG_EUR = 10.0           # PARAMETRIC: drilling / boring fixture, once per batch
GB_COREBOX_EUR = 6.0        # PARAMETRIC: printed core box per half, once per batch
GB_NMRV_EUR = BOUGHT[0][2]  # bought NMRV030 unit price
GB_QTY_MAX = 1000


def load_report():
    if not os.path.exists(REPORT):
        sys.exit('build/lsr2_build_report.json missing: run `make lsr2` (FreeCAD build) first')
    with open(REPORT, encoding='utf-8') as fh:
        r = json.load(fh)
    if r.get('design') != 'mk4' and 'parts' not in r:
        sys.exit('build/lsr2_build_report.json is a phase-6 report: rebuild with the phase-11 cad/lsr2/build.py')
    return r


def pla_g(cm3):
    return cm3 * P.PLA_G_CM3


def route_a(v, qty):
    """Route A cost of one part from its build-report entry: poured A356, foundry, PLA pattern + cores, machining of the stock pads."""
    cast_g = v['cast_cm3'] * P.ALU_CAST_G_CM3
    poured_g = cast_g / YIELD
    metal = poured_g / 1000 * PRICE_A356_EUR_KG + cast_g / 1000 * FOUNDRY_EUR_KG
    minutes = v['machined_cm2'] * v['stock_mm'] / 10 / C['mrr_cm3_min'] + A_SETUPS * C['setup_min']
    machine = minutes / 60 * C['rate_eur_h']
    pla = pla_g(v['pla_cm3'] + v['core_cm3'] * P.CAST['pla_fill']) / P.CAST['series']
    fin_g = v['finished_cm3'] * P.ALU_CAST_G_CM3
    return dict(route='A', alloy='A356-T6', fin_g=fin_g, stock_g=poured_g, waste=100 * (1 - fin_g / poured_g), pla_g=pla, minutes=minutes,
                metal_eur=qty * metal, machine_eur=qty * machine, pla_eur=pla / 1000 * PRICE_PLA_EUR_KG, eur=qty * (metal + machine) + pla / 1000 * PRICE_PLA_EUR_KG)


def route_b(v, qty):
    """Route B cost of one part from its build-report entry (cad/lsr2/route_b.cost: block stock + machining minutes at the PARAMETRIC removal rate)."""
    fin_g = v['finished_cm3'] * C['density']
    stock_g = v['blank_kg'] * 1000
    return dict(route='B', alloy=v['alloy'], fin_g=fin_g, stock_g=stock_g, waste=100 * (1 - fin_g / stock_g), pla_g=0.0, minutes=v['minutes'],
                metal_eur=qty * v['stock_eur'], machine_eur=qty * v['machine_eur'], pla_eur=0.0, eur=qty * (v['stock_eur'] + v['machine_eur']))


def pick(a, b):
    """Default route: the cheaper; within TIE the lighter."""
    if abs(a['eur'] - b['eur']) <= TIE * min(a['eur'], b['eur']):
        return 'A' if a['fin_g'] <= b['fin_g'] else 'B'
    return 'A' if a['eur'] < b['eur'] else 'B'


def compare(parts):
    out = {}
    for n in PARTS:
        v = parts[n]
        q = v['qty']
        a, b = route_a(v['route_a'], q), route_b(v['route_b'], q)
        out[n] = dict(qty=q, A=a, B=b, default=pick(a, b))
    return out


def tube_kg(rep=None):
    return rep['items']['cross_boom']['mass_g'] / 1000 if rep else AX.K['boom_len'] * (AX.K['boom_w'] ** 2 - (AX.K['boom_w'] - 2 * AX.K['boom_t']) ** 2) * 2.70e-6


def shaft_rows(rep):
    rows = []
    for n, segs in AX.SHAFTS.items():
        d, ln = AX.shaft_stock(segs)
        stock = math.pi * d * d / 4 * ln / 1000 * AX.SS_G_CM3
        rows.append(dict(name=n, d=d, l=ln, stock_g=stock, fin_g=rep['shafts'][n]['mass_g'], cost=stock / 1000 * PRICE_SS_EUR_KG))
    return rows


def totals(rep=None):
    rep = rep or load_report()
    cmp_ = compare(rep['parts'])
    shafts = shaft_rows(rep)
    chosen = {n: c[c['default']] for n, c in cmp_.items()}
    bought = sum(q * u for _, q, u in BOUGHT) + tube_kg(rep) * PRICE_TUBE_EUR_KG
    fab_eur = sum(c['eur'] - c['pla_eur'] for c in chosen.values()) + sum(s['cost'] for s in shafts)
    pla_kg = sum(c['pla_g'] for c in chosen.values()) / 1000
    fab_g = sum(cmp_[n]['qty'] * chosen[n]['fin_g'] for n in PARTS) + sum(s['fin_g'] for s in shafts)
    return dict(cmp=cmp_, shafts=shafts, chosen=chosen, fab_g=fab_g, fab_eur=fab_eur, pla_kg=pla_kg, pla_eur=pla_kg * PRICE_PLA_EUR_KG,
                bought=bought, total=fab_eur + pla_kg * PRICE_PLA_EUR_KG + bought, rep=rep)


def gearbox_costs(halves):
    """LSR-WG30 own unit cost from the build-report entries of its two halves: variable part (metal, machining, gear set, hardware) + fixed batch part
    (patterns, cores, core boxes, jig, machine set-ups) / batch size; break-even batch against the bought NMRV030 (None = never)."""
    metal = cut_min = fixed = 0.0
    for v in halves.values():
        metal += route_a(v, 1)['metal_eur']
        cut_min += v['machined_cm2'] * v['stock_mm'] / 10 / C['mrr_cm3_min']
        fixed += pla_g(v['pla_cm3'] + v['core_cm3'] * P.CAST['pla_fill']) / 1000 * PRICE_PLA_EUR_KG + GB_COREBOX_EUR + A_SETUPS * C['setup_min'] / 60 * C['rate_eur_h']
    fixed += GB_JIG_EUR
    hw = sum(q * u for _, q, u in GB_HARDWARE)
    var = metal + (cut_min + GB_FINISH_MIN) / 60 * C['rate_eur_h'] + GB_GEARSET[2] + hw
    unit = lambda n: var + fixed / n
    return dict(metal=metal, cut_min=cut_min, machine=(cut_min + GB_FINISH_MIN) / 60 * C['rate_eur_h'], gearset=GB_GEARSET[2], hardware=hw, var=var, fixed=fixed, unit=unit,
                breakeven=next((n for n in range(1, GB_QTY_MAX + 1) if unit(n) < GB_NMRV_EUR), None))


def gearbox_section(rep):
    g = rep.get('gearbox', {}).get('halves')
    if not g:
        return ['## NMRV030 bought vs LSR-WG30 own', '', 'Not available: rebuild with the phase-7 `cad/lsr2/build.py` (report key `gearbox`).', '']
    c = gearbox_costs(g)
    o = ['## NMRV030 bought vs LSR-WG30 own (phase 7, every price VERIFY)', '',
         'LSR-WG30 = A356 housing in two cast halves (route A, patterns and core boxes printed) + bought worm/bronze wheel + bearings and seals; drop-in for the NMRV030. '
         f'Machining: stock pads from the build report plus {GB_FINISH_MIN:g} min per unit for seats, bores, joint faces, taps and dowel holes (PARAMETRIC). '
         'Batch costs (patterns, core boxes, jig, machine set-ups of both halves) are shared by the units poured together.', '',
         '| Item | EUR per unit |', '|---|---|',
         f"| Metal + foundry (both halves, yield {YIELD}) | {c['metal']:.1f} |", f"| Machining ({c['cut_min']:.1f} min pads + {GB_FINISH_MIN:g} min finishing) | {c['machine']:.1f} |",
         f"| Gear set ({GB_GEARSET[0]}) | {c['gearset']:.1f} |", f"| Bearings, seals, screws, dowels, grease ({sum(q for _, q, _ in GB_HARDWARE)} pieces) | {c['hardware']:.1f} |",
         f"| **Variable cost per unit** | **{c['var']:.1f}** |", f"| Fixed batch cost (patterns, cores, core boxes, jig, set-ups) | {c['fixed']:.1f} per batch |", '',
         '| Case | NMRV030 bought (EUR) | LSR-WG30 own (EUR) | Difference (EUR) |', '|---|---|---|---|']
    for lbl, n in (('1 unit', 1), ('2 units (one rotator, batch of 2)', 2), ('10 units (batch of 10)', 10), ('100 units (batch of 100)', 100)):
        own = c['unit'](n) * n
        o.append(f'| {lbl} | {GB_NMRV_EUR * n:.0f} | {own:.0f} | {own - GB_NMRV_EUR * n:+.0f} |')
    be = c['breakeven']
    o += ['', f'Break-even batch size: ' + (f'**{be} units**' if be else f"**none**: even with the fixed cost spread over {GB_QTY_MAX} units the own unit costs {c['unit'](GB_QTY_MAX):.0f} EUR, "
                                             f"above the bought {GB_NMRV_EUR:.0f} EUR") + '.',
          '', '**Recommendation: keep the bought NMRV030** ' + ('and revisit the LSR-WG30 only when casting in batches above the break-even size. ' if be else
                                                                'unless the gear set or the machining get much cheaper. ') +
          'The own unit is not cheaper and, with a m0.5 gear set at a = 30 mm, it carries about a fifth of the NMRV030 torque (docs/LSR2_SIZING.md §14); '
          'its value is a known, repairable, drop-in design for a future larger-centre version or a batch run.', '']
    return o


def design_of(rep):
    return rep.get('design', 'cast')


def mk4_analysis(rep):
    """Materials per process from the mk4 build report (made parts, via lsr2_mk4_bom.made_parts) and the Mk4 BOM (bought masses, costs, total)."""
    import lsr2_mk4_bom as B
    rows = B.made_parts(rep)
    other = [e for e in rows if e['process'] not in ('laser_2mm', 'cnc_plate_10mm', 'shs_25', 'turned')]
    made_g = {}
    for e in rows:
        made_g[e['process']] = made_g.get(e['process'], 0.0) + e['fin_g']
    fab_g = sum(made_g.values())
    rep_g = B.report_made_g(rep)
    bought_g = B.bought_g()
    bt = B.totals()
    kg = (fab_g + bought_g) / 1000.0
    assert abs(kg - bt['kg']) <= 0.01, (kg, bt['kg'])       # the materials total is the BOM total
    return dict(rows=rows, made_g=made_g, fab_g=fab_g, rep_g=rep_g, bought_g=bought_g, bom=bt, by_process=B.by_process(), other=other,
                kg=kg, eur=bt['eur'], groups=B.by_group(), stock=B.stock(rows), unmapped=B.unmapped_report_parts(rep))


def report_mk4(rep):
    import lsr2_mk4_bom as B
    a = mk4_analysis(rep)
    rows = a['rows']

    def grp(p):
        return [r for r in rows if r['process'] == p]
    o = ['# BricoHams · LibreSat LSR-2: materials and cost budget, SARCTrac Mk4 replica (generated by calc/lsr2_materials.py)', '',
         '<!-- palette: blue #12263f, orange #e8871e -->',
         'Authors: Anatol EA5KAO, Diego EA5JEF, Pedro Roca Molina.', '',
         'Design `LSR2_DESIGN=mk4` (default). **Single source:** made-part masses come only from `build/lsr2_build_report.json` (finished solids of the SARCNET Mk4 files, one value per part), '
         'bought-part masses (catalogue or est.) and all costs from `calc/lsr2_mk4_bom.py`; `scripts/bom.py` writes [BOM_LSR2](BOM_LSR2.md) from the same function, '
         'so both documents carry the same total mass, cost and buy-in quantities. '
         f'Blank estimates: sheet = part rectangle (bounding box) + {int((B.NEST - 1) * 100)} % nesting; plate blank = bounding box + {B.MARGIN_MM:g} mm per side; '
         f'{B.CUT_MM:g} mm cut-off per sawn or turned piece; stainless bar = largest step + {B.BAR_MARGIN_MM:g} mm.', '',
         '## Scope of the mass total', '',
         'Included: rotator head (10 mm mounting plate, 2 mm covers, corner blocks, enclosure, platform), electronics housing with the drivers and controller, the two gearbox + motor assemblies, '
         'lift arms (the report solid includes the steel counterweight leaf of the SARCNET part file), saddle with U-bolts and clamp bars, thrust bearing stack, mast bracket and all fasteners. '
         'Excluded: mast, antennas, cables (including the 8 m motor/sensor cable) and the indoor 48 V PSU. The cost total of [BOM_LSR2](BOM_LSR2.md) includes the PSU and the cable. '
         'The pipe clamps and end stops are catalogue parts: the report models them as simplified solids, the catalogue mass is used.', '',
         '## Laser-cut 2 mm aluminium sheet', '', '| Part | Net area (m2) | Part rectangle (m2) | Finished (g) | Rectangle as sheet (g) |', '|---|---|---|---|---|']
    L = grp('laser_2mm')
    o += [f"| {r['name']} | {r['net_m2']:.4f} | {r['rect_m2']:.4f} | {r['fin_g']:.0f} | {r['stock_g']:.0f} |" for r in L]
    o += [f"| **Total** | **{sum(r['net_m2'] for r in L):.3f}** | **{sum(r['rect_m2'] for r in L):.3f}** | **{sum(r['fin_g'] for r in L):.0f}** | **{sum(r['stock_g'] for r in L):.0f}** |", '',
          '## 10 mm aluminium plate (CNC)', '', '| Part | Finished (g) | Plate blank incl. margin (g) | Waste (%) |', '|---|---|---|---|']
    Pl = grp('cnc_plate_10mm')
    o += [f"| {r['name']} | {r['fin_g']:.0f} | {r['stock_g']:.0f} | {100 * (1 - r['fin_g'] / r['stock_g']):.0f} |" for r in Pl]
    o += [f"| **Total** | **{sum(r['fin_g'] for r in Pl):.0f}** | **{sum(r['stock_g'] for r in Pl):.0f}** | |", '',
          '## 25 x 25 x 2 SHS', '', '| Part | Length incl. cut-off (mm) | Finished incl. end plates and counterweight (g) |', '|---|---|---|']
    S = grp('shs_25')
    o += [f"| {r['name']} | {r['len_mm']:.0f} | {r['fin_g']:.0f} |" for r in S]
    o += [f"| **Total** | **{sum(r['len_mm'] for r in S):.0f}** | **{sum(r['fin_g'] for r in S):.0f}** |", '',
          '## Turned stainless', '', '| Part | Bar Ø x L (mm) | Finished (g) | Bar stock (g) |', '|---|---|---|---|']
    T = grp('turned')
    o += [f"| {r['name']} | {r['bar'][0]:g} x {r['bar'][1]:g} | {r['fin_g']:.0f} | {r['stock_g']:.0f} |" for r in T]
    o += [f"| **Total** | | **{sum(r['fin_g'] for r in T):.0f}** | **{sum(r['stock_g'] for r in T):.0f}** |", '']
    if a['other']:
        o += ['## Other made parts (16 mm bar, angle, gaskets, dust caps; finished mass)', '', '| Part | Process | Finished (g) | Stock (g) |', '|---|---|---|---|']
        o += [f"| {r['name']} | {r['process']} | {r['fin_g']:.0f} | {r['stock_g']:.0f} |" for r in a['other']]
        o += ['']
    st = a['stock']
    o += ['## Buy-in quantities (same table in BOM_LSR2)', '', '| Stock | Quantity | Mass kg |', '|---|---|---|',
          f"| 2 mm 5754/5083 sheet incl. {int((B.NEST - 1) * 100)} % nesting | {st['sheet_m2']:.2f} m2 | {st['sheet_kg']:.2f} |",
          f"| 10 mm 6082 plate, blanks incl. margin | | {st['plate_kg']:.2f} |",
          f"| 16 mm 6082 bar | {st['bar_m']:.2f} m of cut pieces | {st['bar_kg']:.2f} |",
          f"| 25 x 25 x 2 SHS | {st['shs_m']:.2f} m | {st['shs_kg']:.2f} |",
          f"| 32 x 32 x 3 angle | {st['angle_m']:.2f} m | {st['angle_kg']:.2f} |",
          f"| Stainless 1.4404 round ({st['ss_n']} turned parts, shaft est.) | | {st['ss_kg']:.2f} |",
          f"| 3 mm neoprene sheet (motor gaskets) | {st['neo_m2']:.3f} m2 | {st['neo_kg']:.2f} |", '']
    o += ['## Bought parts', '', f"Bought parts and estimates (gearboxes, motors, hardware, electronics; catalogue or est., without PSU and cable) weigh {a['bought_g']:.0f} g in the Mk4 BOM; "
          'the line items and prices are in [BOM_LSR2](BOM_LSR2.md).', '',
          '## Totals', '', '| Item | Value |', '|---|---|',
          f"| Fabricated mass, made parts (report) | {a['fab_g']:.0f} g (report made parts {a['rep_g']:.0f} g without the catalogue solids) |",
          f"| Bought mass (BOM, catalogue / est.) | {a['bought_g']:.0f} g |",
          f"| **Total mass (= BOM_LSR2 total)** | **{a['kg']:.2f} kg** |",
          f"| **Total estimated cost, rotator and electronics (BOM, est.)** | **{a['eur']:.0f} EUR** |", '',
          '| Cost group (BOM, est.) | EUR |', '|---|---|']
    o += [f'| {k} | {v:.0f} |' for k, v in a['groups'].items()]
    o += ['', '| Process (BOM) | Cost EUR (est.) | Mass kg |', '|---|---|---|']
    o += [f'| {p} | {e:.0f} | {g / 1000:.2f} |' for p, (e, g) in a['by_process'].items()]
    o += ['', 'Prices are estimates (EU hobby suppliers, 2026); laser and CNC job prices are quotes to request.', '',
          '## Cast variant', '',
          'The earlier cast/CNC open-box design (route A / route B comparison, shafts, own LSR-WG30 gearbox) is optional and is generated by this script with `LSR2_DESIGN=cast` '
          '(build the cast variant first, then `python calc/lsr2_materials.py`).', '']
    return '\n'.join(o), a



def report():
    return report_cast()


def report_cast():
    t = totals()
    o = ['# BricoHams · LibreSat LSR-2: materials and cost budget, both routes (generated by calc/lsr2_materials.py)', '',
         '<!-- palette: blue #12263f, orange #e8871e -->',
         'Authors: Anatol EA5KAO, Diego EA5JEF, Pedro Roca Molina.', '',
         'Goal: light and cheap. Geometry from `build/lsr2_build_report.json` (phase-11 build); every price, rate and yield is PARAMETRIC and '
         '**VERIFY** with local quotes. Route A = printed pattern, sand-cast A356-T6, machining of the stock pads; route B = 3-axis CNC from 6082/6061 block.', '',
         f'Parameters: A356 ingot {PRICE_A356_EUR_KG} EUR/kg, foundry {FOUNDRY_EUR_KG} EUR/kg of casting, yield {YIELD}, shrink {P.CAST["shrink"]}, '
         f'PLA {PRICE_PLA_EUR_KG:g} EUR/kg at {P.PLA_G_CM3} g/cm³ with {P.CAST["pla_fill"] * 100:.0f} % fill, series {P.CAST["series"]} '
         f'(pattern shared by that many rotators), CNC block {C["price_eur_kg"]} EUR/kg, removal rate {C["mrr_cm3_min"]} cm³/min, '
         f'set-up {C["setup_min"]} min, machine {C["rate_eur_h"]} EUR/h, cast machining {A_SETUPS} set-ups.', '',
         '## Route comparison per part (all quantities of one rotator)', '',
         '| Part | Qty | Route | Alloy | Finished (g each) | Stock (g each) | Waste (%) | PLA (g) | Machining (min each) | Cost (EUR) | Default |',
         '|---|---|---|---|---|---|---|---|---|---|---|']
    for n, c in t['cmp'].items():
        for r in 'AB':
            x = c[r]
            o.append(f"| {n} | {c['qty']} | {r} | {x['alloy']} | {x['fin_g']:.0f} | {x['stock_g']:.0f} | {x['waste']:.0f} | {x['pla_g']:.0f} | "
                     f"{x['minutes']:.0f} | {x['eur']:.1f} | {'**yes**' if c['default'] == r else ''} |")
    o += ['', 'Route B cost counts the number of set-ups of docs/LSR2_ROUTE_B_CNC.md; the body is machined as bolted slabs (joint sealing is an open decision) '
          'and some of its horizontal features need a 4th axis or an angle plate (also open), so its route-B number is optimistic. '
          'Default route per part = cheaper; within 5 % the lighter.', '',
          '## Turned shafts (stainless 1.4404)', '',
          f'Stock = finished length + 10 mm, diameter = largest step + 3 mm; {AX.SS_G_CM3} g/cm³; {PRICE_SS_EUR_KG} EUR/kg (VERIFY).', '',
          '| Shaft | Stock Ø x L (mm) | Stock (g) | Finished (g) | Cost (EUR) |', '|---|---|---|---|---|']
    o += [f"| {s['name']} | {s['d']:g} x {s['l']:g} | {s['stock_g']:.0f} | {s['fin_g']:.0f} | {s['cost']:.1f} |" for s in t['shafts']]
    o += ['', f'Cross boom 6063 {AX.K["boom_w"]:g}x{AX.K["boom_w"]:g}x{AX.K["boom_t"]:g} x {AX.K["boom_len"]:g} mm = {tube_kg(t["rep"]):.2f} kg (in the bought-part total).', '',
          '## Bought parts (every price VERIFY)', '', '| Item | Qty | Unit (EUR) | Total (EUR) |', '|---|---|---|---|']
    o += [f'| {n} | {q} | {u:.2f} VERIFY | {q * u:.2f} |' for n, q, u in BOUGHT]
    o += ['', '## Totals (default routes)', '', '| Item | Value |', '|---|---|',
          f"| Fabricated finished mass (structural parts + shafts) | {t['fab_g']:.0f} g |",
          f"| Fabricated cost, metal + foundry/blank + machining + shafts (VERIFY) | {t['fab_eur']:.0f} EUR |",
          f"| PLA patterns and cores at {PRICE_PLA_EUR_KG:g} EUR/kg (VERIFY) | {t['pla_kg']:.2f} kg / {t['pla_eur']:.0f} EUR |",
          f"| Bought parts incl. cross boom (VERIFY) | {t['bought']:.0f} EUR |",
          f"| Total estimated cost (VERIFY) | {t['total']:.0f} EUR |", '',
          'The phase-6 figure (3605 g fabricated, 429 EUR) belonged to the two-block layout and is no longer a reference.', ''] + gearbox_section(t['rep'])
    return '\n'.join(o)


def self_test():
    # hand check, route A: 100 cm3 cast -> 268 g casting, 487.27 g poured; pads 10 cm2 x 3 mm = 3 cm3 at the removal rate + 2 set-ups
    v = dict(cast_cm3=100.0, finished_cm3=90.0, machined_cm2=10.0, stock_mm=3.0, pla_cm3=20.0, core_cm3=0.0)
    a = route_a(v, 2)
    assert abs(a['stock_g'] - 487.27) < 0.01 and abs(a['minutes'] - (3.0 / C['mrr_cm3_min'] + A_SETUPS * C['setup_min'])) < 1e-9
    assert abs(a['eur'] - (a['metal_eur'] + a['machine_eur'] + a['pla_eur'])) < 1e-9
    # hand check, route B: 500 cm3 finished in a 2.7 kg (1000 cm3) blank: 50 % waste, 29.7 + 40 EUR
    b = route_b(dict(finished_cm3=500.0, blank_kg=2.7, alloy='6082-T6', minutes=60.0, stock_eur=29.7, machine_eur=40.0), 1)
    assert abs(b['waste'] - 50.0) < 1e-6 and abs(b['eur'] - 69.7) < 1e-9
    assert pick(dict(eur=100.0, fin_g=500), dict(eur=102.0, fin_g=450)) == 'B'      # within 5 %: the lighter
    assert pick(dict(eur=100.0, fin_g=500), dict(eur=150.0, fin_g=400)) == 'A'      # clearly cheaper
    assert abs(tube_kg() - 1.6 * 1000 * 0.444 * 2.70e-3 * 1.0) < 0.01                  # hand check: (1600 - 1156) mm2 x 1600 mm x 2.70 g/cm3 = 1.918 kg
    # LSR-WG30: two halves of 100 cm3 cast: metal 2 x 4.337 = 8.673; machining (0.4 + 20) min x 40 / 60 = 13.6; gear set 25; hardware 13.1 -> 60.37 EUR > NMRV030 55: never
    gc = gearbox_costs({'l': v, 'u': v})
    assert abs(gc['var'] - 60.373) < 0.01 and gc['breakeven'] is None and gc['unit'](1) > gc['unit'](10) > gc['var']
    assert abs(sum(q * u for _, q, u in GB_HARDWARE) - 13.1) < 1e-9
    d, ln = AX.shaft_stock([(0, 100, 30)])
    assert abs(math.pi * d * d / 4 * ln / 1000 * AX.SS_G_CM3 - 747.96) < 0.05           # hand check: Ø33 x 110 bar at 7.95 g/cm3


if __name__ == '__main__':
    self_test()
    if '--check' in sys.argv:
        print('lsr2_materials self-test OK')
        sys.exit(0)
    rep = load_report()
    if design_of(rep) == 'mk4':
        text, a = report_mk4(rep)
        import lsr2_mk4_bom as B
        assert not a['unmapped'], a['unmapped']                              # every made part of the report is a BOM row
        assert abs(a['fab_g'] - a['rep_g']) <= 0.05 * len(rep['parts']) + 0.1, (a['fab_g'], a['rep_g'])   # per-part rounding of mass_g only
        assert abs(a['kg'] - B.totals()['kg']) <= 0.01, (a['kg'], B.totals()['kg'])   # same total as scripts/bom.py
        with open(os.path.join(ROOT, 'docs', 'LSR2_MATERIALS.md'), 'w', encoding='utf-8') as fh:
            fh.write(text)
        print('wrote docs/LSR2_MATERIALS.md')
        print(f"LSR-2 total {a['eur']:.0f} EUR, {a['kg']:.2f} kg (fabricated {a['fab_g']:.0f} g, report {a['rep_g']:.0f} g)")
        sys.exit(0)
    with open(os.path.join(ROOT, 'docs', 'LSR2_MATERIALS.md'), 'w', encoding='utf-8') as fh:
        fh.write(report_cast())
    print('wrote docs/LSR2_MATERIALS.md')
