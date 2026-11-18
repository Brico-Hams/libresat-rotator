#!/usr/bin/env python3
"""LSR-2 SARCTrac Mk4 replica bill of materials: the single source of the Mk4 BOM.

scripts/bom.py renders it into docs/BOM_LSR2.md (python scripts/bom.py). Pure Python, no imports from FreeCAD.
Lines 'Rotator Assembly', 'Saddle' and 'Thrust Bearing' are the three parts lists of the SARCNET Mk4 FreeCAD files
(third_party/sarctrac-mk4/mk4_dump.json, spreadsheet cells; item numbers in the ref column).

Single source of the Mk4 masses, costs and stock quantities (calc/lsr2_materials.py, cad/lsr2/inputs.py and scripts/bom.py all read it):
- made-part masses come ONLY from build/lsr2_build_report.json (`parts[...].mass_g`, one entry per instance, see RK below); when the report is missing
  (or is not an mk4 report) the rows fall back to their own estimates (solid volume of the SARCNET part x 2.70 / 8.0 g/cm3), flagged in the md;
- bought-part masses are catalogue values (basis `cat.`) or estimates (basis `est.`) of this file;
- the mass total covers the rotator head, electronics housing, lift arms, saddle and fasteners; it excludes mast, antennas, cables and the indoor PSU;
- every price is an estimate ("est.", EU hobby suppliers, 2026); laser and CNC job prices are quotes to request before ordering.
"""
import json
import math
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORT = os.path.join(ROOT, 'build', 'lsr2_build_report.json')
AL_G_CM3, SS_G_CM3 = 2.70, 8.0
GEARBOX_G, MOTOR_G, ADAPTOR_G = 1400.0, 1000.0, 50.0       # catalogue: NMRV30-G50-D11, NEMA23 23HS32-4004S, 11 -> 8 mm adaptor
LASER, PLATE10, BAR16, SHS, TURNED, BOUGHT = 'laser 2 mm', 'CNC 10 mm plate', 'CNC 16 mm bar', 'SHS cut', 'turned', 'bought'
MOULDED, GASKET = 'moulded / printed', 'cut gasket'
MARGIN_MM = 5.0              # PARAMETRIC: plate blank margin per side (clamping)
CUT_MM = 10.0                # PARAMETRIC: cut-off allowance per sawn or turned piece
BAR_MARGIN_MM = 3.0          # PARAMETRIC: turned bar diameter above the largest step
NEST = 1.30                  # PARAMETRIC: sheet nesting loss, buy 30 % more than the sum of the part rectangles
SHEET_KG_M2 = 2.0 * 2.66     # 2 mm 5754/5083 sheet, 2.66 g/cm3 (same density as the build report)
SHS_KG_M = 0.184 * 2.70      # 25 x 25 x 2 SHS: 184 mm2 x 2.70 g/cm3
ANGLE_KG_M = 0.183 * 2.70    # 32 x 32 x 3 angle: 183 mm2 x 2.70 g/cm3
BAR_T_MM = 16.0              # 16 mm bar stock thickness
NEOPRENE_T_MM, NEOPRENE_G_CM3 = 3.0, 1.25


def al(vol_mm3):
    return vol_mm3 / 1000.0 * AL_G_CM3


def ss(vol_mm3):
    return vol_mm3 / 1000.0 * SS_G_CM3


# (group, item, qty, description, material/spec, process, unit EUR est., mass g each, source/ref, sheet area m2 each)
R, S, T, E = 'Rotator Assembly', 'Saddle', 'Thrust Bearing', 'Electronics and extras'
M8B, M8W, M8N = 'M8 x 40 Hex Bolts', 'M8 Flat Washer', 'M8 Nyloc Nut'
_ROWS = [
    # ---- Rotator Assembly list
    (R, 1, 1, 'Plate (mounting plate)', 'aluminium 6082-T6, 10 mm plate', PLATE10, 25.0, al(186775.6), 'Rotator Assembly #1; part Plate', 0),
    (R, 2, 8, M8B, 'stainless A2-70 M8x40', BOUGHT, 0.30, 21.0, 'Rotator Assembly #2', 0),
    (R, 3, 16, M8W, 'stainless A2 M8', BOUGHT, 0.04, 2.0, 'Rotator Assembly #3', 0),
    (R, 4, 8, M8N, 'stainless A2 M8 nyloc', BOUGHT, 0.12, 6.0, 'Rotator Assembly #4', 0),
    (R, 5, 2, 'Hall Effect Switch (index, one per axis)', 'NJK-5002C, NPN, normally open, 5-30 V, cable', BOUGHT, 3.5, 35.0, 'Rotator Assembly #5', 0),
    (R, 6, 2, 'Pipe Clamp', 'stainless pipe clamp for the Hall switch', BOUGHT, 2.5, 40.0, 'Rotator Assembly #6', 0),
    (R, 7, 4, 'M5 x 16 Cap Screw', 'stainless A2 M5x16', BOUGHT, 0.08, 5.0, 'Rotator Assembly #7', 0),
    (R, 8, 8, 'M5 Flat Washer', 'stainless A2 M5', BOUGHT, 0.02, 0.5, 'Rotator Assembly #8', 0),
    (R, 9, 4, 'M5 Nyloc Nut', 'stainless A2 M5 nyloc', BOUGHT, 0.06, 1.5, 'Rotator Assembly #9', 0),
    (R, 10, 1, 'Elevation Gearbox Assembly: NMRV30-G50-D11 worm gearbox 50:1 + NEMA23 23HS32-4004S + 11->8 mm motor adaptor',
     'worm gearbox 1400 g + motor 1000 g + adaptor 50 g; NEMA23 2.4 N.m, 4.0 A', BOUGHT, 118.0, GEARBOX_G + MOTOR_G + ADAPTOR_G, 'Rotator Assembly #10', 0),
    (R, 11, 1, 'Azimuth Gearbox Assembly: NMRV30-G50-D11 worm gearbox 50:1 + NEMA23 23HS32-4004S + 11->8 mm motor adaptor',
     'worm gearbox 1400 g + motor 1000 g + adaptor 50 g; NEMA23 2.4 N.m, 4.0 A', BOUGHT, 118.0, GEARBOX_G + MOTOR_G + ADAPTOR_G, 'Rotator Assembly #11', 0),
    # ---- Saddle list
    (S, 1, 1, 'Saddle Plate Front', 'aluminium 6082-T6, 10 mm plate', PLATE10, 35.0, al(274847.8), 'Saddle #1; part SaddlePlateFront', 0),
    (S, 2, 1, 'Saddle Plate Right', 'aluminium 6082-T6, 10 mm plate', PLATE10, 25.0, al(146748.5), 'Saddle #2; part SaddlePlateRight', 0),
    (S, 3, 1, 'Saddle Plate Left', 'aluminium 6082-T6, 10 mm plate', PLATE10, 25.0, al(147533.9), 'Saddle #3; part SaddlePlateLeft', 0),
    (S, 4, 2, 'Bar (saddle clamp bar)', 'aluminium 6082-T6, 16 mm bar', BAR16, 6.0, al(22383.0), 'Saddle #4; part Bar', 0),
    (S, 5, 2, 'U-Bolt 40mm', 'stainless A2 U-bolt for 40 mm tube', BOUGHT, 4.0, 90.0, 'Saddle #5', 0),
    (S, 6, 2, 'Neoprene Strip', 'neoprene 3 mm strip, saddle liner', BOUGHT, 1.0, 10.0, 'Saddle #6', 0),
    (S, 7, 1, 'Neodymium Magnet', 'N42 disc magnet for the Hall index', BOUGHT, 1.5, 5.0, 'Saddle #7', 0),
    (S, 8, 8, M8B, 'stainless A2-70 M8x40', BOUGHT, 0.30, 21.0, 'Saddle #8', 0),
    (S, 9, 8, M8N, 'stainless A2 M8 nyloc', BOUGHT, 0.12, 6.0, 'Saddle #9', 0),
    (S, 10, 16, M8W, 'stainless A2 M8', BOUGHT, 0.04, 2.0, 'Saddle #10', 0),
    (S, 11, 4, 'M10 Hex Nut', 'stainless A2 M10', BOUGHT, 0.10, 8.0, 'Saddle #11', 0),
    (S, 12, 4, 'M10 Flat Washer', 'stainless A2 M10', BOUGHT, 0.05, 4.0, 'Saddle #12', 0),
    (S, 13, 2, 'End Stop (mechanical, fail-safe limit)', 'micro switch (EE-SX1103 / MicroSwitch in the files), normally closed wiring', BOUGHT, 3.0, 10.0, 'Saddle #13', 0),
    (S, 14, 1, 'Angle Bracket', 'aluminium angle 32 x 32 x 3, 184 mm', SHS, 8.0, al(32767.2), 'Saddle #14; part Angle', 0),
    # ---- Thrust Bearing list
    (T, 1, 6, 'M5 Flat Washer', 'stainless A2 M5', BOUGHT, 0.02, 0.5, 'Thrust Bearing #1', 0),
    (T, 2, 6, 'M5 x 16 Cap Screw', 'stainless A2 M5x16', BOUGHT, 0.08, 5.0, 'Thrust Bearing #2', 0),
    (T, 3, 1, 'M14 Hub (azimuth hub)', 'stainless 1.4404, turned', TURNED, 30.0, ss(28836.0), 'Thrust Bearing #3; part HubAz', 0),
    (T, 4, 1, 'M6 Flat Washer', 'stainless A2 M6', BOUGHT, 0.03, 1.0, 'Thrust Bearing #4', 0),
    (T, 5, 1, 'M6 x 25 Hex Screw', 'stainless A2 M6x25', BOUGHT, 0.12, 8.0, 'Thrust Bearing #5', 0),
    (T, 6, 1, 'M6 Flat Washer', 'stainless A2 M6', BOUGHT, 0.03, 1.0, 'Thrust Bearing #6', 0),
    (T, 7, 1, 'M30 x 56 x 3 Flat Washer', 'stainless A2 shim washer', BOUGHT, 1.2, 41.0, 'Thrust Bearing #7', 0),
    (T, 8, 1, 'M30 x 56 x 3 Flat Washer', 'stainless A2 shim washer', BOUGHT, 1.2, 41.0, 'Thrust Bearing #8', 0),
    (T, 9, 1, 'M30 x 56 x 3 Flat Washer', 'stainless A2 shim washer', BOUGHT, 1.2, 41.0, 'Thrust Bearing #9', 0),
    (T, 10, 1, 'M30 x 56 x 3 Flat Washer', 'stainless A2 shim washer', BOUGHT, 1.2, 41.0, 'Thrust Bearing #10', 0),
    (T, 11, 1, 'NBR 51206 Thrust Bearing Bottom Race', 'axial ball bearing 51206 (30 x 52 x 16), bottom race', BOUGHT, 6.0, 75.0, 'Thrust Bearing #11', 0),
    (T, 12, 1, 'NBR 51206 Thrust Bearing Ball Cage', '51206 ball cage', BOUGHT, 2.0, 30.0, 'Thrust Bearing #12', 0),
    (T, 13, 1, 'NBR 51206 Thrust Bearing Top Race', '51206 top race', BOUGHT, 6.0, 75.0, 'Thrust Bearing #13', 0),
    (T, 14, 1, '50mm Coupler PVC Pressure Tube Class 18', 'PVC coupler 50 mm, weather cover of the bearing', BOUGHT, 3.0, 120.0, 'Thrust Bearing #14', 0),
    (T, 15, 1, 'NMRV30 Single Ended Shaft', 'stainless 1.4404, turned (part RV30-SHAFT)', TURNED, 30.0, ss(19674.0), 'Thrust Bearing #15; part RV30-SHAFT', 0),
    # ---- Parts of the model that are not rows of the three lists (cover, lift arms, EL hubs, mast bracket)
    (R, 'x1', 1, 'CoverTop', 'aluminium 5754 2 mm sheet, laser-cut and folded/bolted', LASER, 9.0, al(51499.2), 'part CoverTop (208 x 124 mm)', 208 * 124 / 1e6),
    (R, 'x2', 1, 'CoverBottom', 'aluminium 5754 2 mm sheet, laser-cut', LASER, 9.0, al(43130.0), 'part CoverBottom (208 x 124 mm)', 208 * 124 / 1e6),
    (R, 'x3', 1, 'CoverFront', 'aluminium 5754 2 mm sheet, laser-cut', LASER, 8.0, al(45543.5), 'part CoverFront (120 x 190 mm)', 120 * 190 / 1e6),
    (R, 'x4', 1, 'CoverBack', 'aluminium 5754 2 mm sheet, laser-cut', LASER, 8.0, al(45078.5), 'part CoverBack (120 x 190 mm)', 120 * 190 / 1e6),
    (R, 'x5', 2, 'CoverLeft / CoverRight', 'aluminium 5754 2 mm sheet, laser-cut', LASER, 11.0, al(73699.3), 'parts CoverLeft, CoverRight (208 x 190 mm)', 208 * 190 / 1e6),
    (R, 'x6', 8, 'CoverCornerBlock', 'aluminium 6082 16 mm bar, 14 x 16 x 16 mm', BAR16, 1.5, al(3380.3), 'part CoverCornerBlock', 0),
    (R, 'x7', 1, 'Bracket (mast bracket)', 'aluminium 6082-T6, 10 mm plate, 100 x 250 mm', PLATE10, 25.0, al(245853.1), 'part Bracket', 0),
    (R, 'x8', 2, 'LiftArm (25 mm SHS arm with end plates)', 'aluminium SHS 25 x 25 x 2 + 10 mm plate ends', SHS, 18.0, al(296310.1), 'parts LiftArmLeft, LiftArmRight (CAD solid)', 0),
    (R, 'x9', 2, 'EL Hub (HubLeft / HubRight)', 'stainless 1.4404, turned', TURNED, 30.0, ss(28836.0), 'parts HubLeft, HubRight', 0),
    (R, 'x10', 1, 'Bar (mounting-assembly clamp bar)', 'aluminium 6082-T6, 16 mm bar', BAR16, 6.0, al(22383.0), 'part Bar (instance bar003)', 0),
    (R, 'x11', 1, 'Platform (antenna platform)', 'aluminium 6082-T6, 10 mm plate', PLATE10, 25.0, al(116748.0), 'part Platform', 0),
    (R, 'x12', 1, 'EnclosureFront', 'aluminium 5083 2 mm sheet, laser-cut', LASER, 8.0, 77.7, 'part EnclosureFront (104 x 142 mm)', 104 * 142 / 1e6),
    (R, 'x13', 1, 'EnclosureBottom', 'aluminium 5083 2 mm sheet, laser-cut', LASER, 6.0, 53.3, 'part EnclosureBottom (98 x 70 mm)', 98 * 70 / 1e6),
    (R, 'x14', 1, 'EnclosureTop', 'aluminium 5083 2 mm sheet, laser-cut', LASER, 6.0, 54.5, 'part EnclosureTop (98 x 70 mm)', 98 * 70 / 1e6),
    (R, 'x15', 3, 'DustCap', 'neoprene dust cap, moulded or printed in TPU', MOULDED, 2.0, 29.0, 'parts DustCap, DustCapLeft, DustCapRight', 0),
    (R, 'x16', 2, 'MotorGasket', 'neoprene 3 mm sheet, cut gasket', GASKET, 1.0, 4.3, 'parts MotorGasket (2)', 0),
    # ---- Electronics and extras (not in the SARCNET lists)
    (E, 'e1', 2, 'DM542T stepper driver', '18-50 V, 4.5 A peak, opto inputs', BOUGHT, 22.0, 280.0, 'electronics', 0),
    (E, 'e2', 1, 'S-400-48 power supply', '48 V 8.3 A, indoors', BOUGHT, 45.0, 1100.0, 'electronics', 0),
    (E, 'e3', 2, 'XL7015 DC-DC converter', 'one set to 12 V (Hall switches), one to 5 V (ESP8266)', BOUGHT, 3.0, 15.0, 'electronics', 0),
    (E, 'e4', 1, '3.3 V LDO regulator', 'AMS1117-3.3 or similar on a small board', BOUGHT, 0.6, 2.0, 'electronics', 0),
    (E, 'e5', 1, 'Wemos D1 Mini Pro (controller)', 'ESP8266, 16 MB, U.FL connector', BOUGHT, 8.0, 5.0, 'electronics', 0),
    (E, 'e6', 1, 'External 2.4 GHz antenna with U.FL-SMA pigtail', 'SMA 2.4 GHz antenna + pigtail', BOUGHT, 6.0, 30.0, 'electronics', 0),
    (E, 'e7', 1, 'Wemos D1 Mini (PC USB WiFi dongle)', 'ESP8266 on USB, WiFi link to the controller', BOUGHT, 4.0, 5.0, 'electronics', 0),
    (E, 'e8', 1, 'Opto-isolated 48 V power-down detect', 'optocoupler + divider on a small board', BOUGHT, 3.0, 10.0, 'electronics', 0),
    (E, 'e9', 1, 'Deltron 483-0100 diecast housing', 'IP-rated aluminium diecast box for the electronics', BOUGHT, 15.0, 450.0, 'electronics', 0),
    (E, 'e10', 3, 'Cable gland', 'M16 nylon IP68', BOUGHT, 1.2, 20.0, 'electronics', 0),
    (E, 'e11', 1, 'Toggle switch', 'sealed 48 V toggle', BOUGHT, 2.0, 20.0, 'electronics', 0),
    (E, 'e12', 1, 'Tef-Gel', 'anti-seize / anti-corrosion paste, 25 g tube', BOUGHT, 12.0, 60.0, 'electronics', 0),
    (E, 'e13', 1, 'Neoprene gasket / strip (housing and cover)', 'neoprene 1 m x 10 mm', BOUGHT, 4.0, 100.0, 'electronics', 0),
    (E, 'e14', 1, 'Motor, sensor and power cable', 'screened, about 8 m in total', BOUGHT, 10.0, 500.0, 'electronics', 0),
    (E, 'e15', 48, 'Cover screws and nuts', 'stainless M3 x 8 with nuts, cover to corner blocks', BOUGHT, 0.06, 2.0, 'extras', 0),
]


def load_report():
    """The mk4 build report, or None when it is missing or belongs to another design."""
    try:
        with open(REPORT, encoding='utf-8') as fh:
            r = json.load(fh)
    except (OSError, ValueError):
        return None
    return r if r.get('design') == 'mk4' and 'parts' in r else None


# Row -> build-report instances that make it (qty of the row = number of instances); the mass of those rows comes from the report only.
RK = {
    (R, 1): ('plate',), (S, 1): ('saddle_plate_front',), (S, 2): ('saddle_plate_right',), (S, 3): ('saddle_plate_left',),
    (S, 4): ('bar_right', 'bar_left'), (S, 14): ('angle_bracket',), (T, 3): ('hub_az',),
    (R, 'x1'): ('cover_top',), (R, 'x2'): ('cover_bottom',), (R, 'x3'): ('cover_front',), (R, 'x4'): ('cover_back',),
    (R, 'x5'): ('cover_left', 'cover_right'), (R, 'x6'): tuple(f'cover_corner_block{i:03d}' for i in range(1, 9)),
    (R, 'x7'): ('bracket001',), (R, 'x8'): ('lift_arm_left', 'lift_arm_right'), (R, 'x9'): ('hub_left', 'hub_right'),
    (R, 'x10'): ('bar003',), (R, 'x11'): ('platform',), (R, 'x12'): ('enclosure_front',), (R, 'x13'): ('enclosure_bottom',),
    (R, 'x14'): ('enclosure_top',), (R, 'x15'): ('dust_cap', 'dust_cap_left', 'dust_cap_right'), (R, 'x16'): ('motor_gasket001', 'motor_gasket003'),
}
# The report models these catalogue parts as simplified solids (a 1.2 g end stop): their mass is the catalogue value of the BOM row, not the report.
CATALOGUE_SOLIDS = ('pipe_clamp', 'pipe_clamp001', 'end_stop001', 'end_stop002')
CATALOGUE = {(R, 10), (R, 11), (T, 11), (T, 12), (T, 13), (E, 'e1'), (E, 'e2'), (E, 'e3'), (E, 'e5'), (E, 'e9')}   # catalogue masses; every other bought mass is `est.`
EXCLUDED_MASS = {(E, 'e2'), (E, 'e14')}      # indoor PSU and cable run are outside the mass scope
REP = load_report()


def _resolve(rows, rep):
    out, used = [], set()
    for r in rows:
        keys = RK.get((r[0], r[1]))
        if keys and rep:
            ms = [rep['parts'][k].get('mass_g') for k in keys if k in rep['parts']]
            if len(ms) == len(keys) and all(m is not None for m in ms):
                r = r[:7] + (sum(ms) / len(ms),) + r[8:]
                used.add((r[0], r[1]))
        out.append(r)
    return out, used


ROWS, FROM_REPORT = _resolve(_ROWS, REP)
SOURCE = 'report' if REP else 'estimates'


def basis(r):
    k = (r[0], r[1])
    return 'report' if k in FROM_REPORT else 'cat.' if k in CATALOGUE else 'est.'


def row_g(r):
    return 0.0 if (r[0], r[1]) in EXCLUDED_MASS else r[2] * r[7]


def made_g():
    return sum(row_g(r) for r in ROWS if (r[0], r[1]) in FROM_REPORT)


def bought_g():
    """Bought and estimated parts (everything that is not a made part of the build report), mass scope as the total."""
    return sum(row_g(r) for r in ROWS if (r[0], r[1]) not in FROM_REPORT)


def unmapped_report_parts(rep=None):
    """Made parts of the report that no BOM row accounts for (must be empty)."""
    rep = rep or REP
    keys = {k for ks in RK.values() for k in ks} | set(CATALOGUE_SOLIDS)
    return [n for n, v in rep['parts'].items() if v['process'] != 'bought' and v.get('mass_g') is not None and n not in keys]


def report_made_g(rep=None):
    """Report masses of the made parts that the BOM takes from the report (catalogue solids excluded)."""
    rep = rep or REP
    return sum(v['mass_g'] for n, v in rep['parts'].items() if v['process'] != 'bought' and v.get('mass_g') is not None and n not in CATALOGUE_SOLIDS)


def totals():
    eur = sum(r[2] * r[6] for r in ROWS)
    g = sum(row_g(r) for r in ROWS)
    sheet = sum(r[2] * r[9] for r in ROWS)
    plate_g = sum(row_g(r) for r in ROWS if r[5].startswith('CNC'))
    return dict(eur=eur, kg=g / 1000.0, sheet_m2=sheet, plate_kg=plate_g / 1000.0, made_g=made_g(), bought_g=bought_g(), source=SOURCE)


def by_process():
    out = {}
    for r in ROWS:
        e, g = out.get(r[5], (0.0, 0.0))
        out[r[5]] = (e + r[2] * r[6], g + row_g(r))
    return out


ELECTRONICS = {(R, 5), (S, 13)} | {(E, f'e{i}') for i in (1, 3, 4, 5, 6, 7, 8, 9, 10, 11, 14)}
CONSUMABLES = {(S, 6), (E, 'e12'), (E, 'e13'), (R, 'x16')}
GROUPS = ['Gearboxes + motors', 'Drivers + electronics', 'Laser sheet', 'Plate / CNC', 'SHS and angle', 'Turned stainless', 'Fasteners and hardware', 'Consumables', 'PSU']


def cost_group(r):
    k = (r[0], r[1])
    if k in ((R, 10), (R, 11)):
        return GROUPS[0]
    if k == (E, 'e2'):
        return 'PSU'
    if k in ELECTRONICS:
        return GROUPS[1]
    if k in CONSUMABLES:
        return 'Consumables'
    return {LASER: GROUPS[2], PLATE10: GROUPS[3], BAR16: GROUPS[3], SHS: GROUPS[4], TURNED: GROUPS[5]}.get(r[5], GROUPS[6])


def by_group():
    out = dict.fromkeys(GROUPS, 0.0)
    for r in ROWS:
        out[cost_group(r)] += r[2] * r[6]
    return out


def _kg(keys):
    return sum(row_g(r) for r in ROWS if (r[0], r[1]) in keys) / 1000.0


def sizing_masses():
    """Masses (kg) for cad/lsr2/inputs.py, from the same rows as the BOM: one lift arm, saddle with its mounting-assembly parts, stationary part, head box, electronics."""
    lift = next(r for r in ROWS if (r[0], r[1]) == (R, 'x8'))[7] / 1000.0
    return dict(lift_mass=lift, gb_mass=GEARBOX_G / 1000.0, motor_mass=MOTOR_G / 1000.0,
                saddle_mass=sum(row_g(r) for r in ROWS if r[0] == S) / 1000.0 + _kg({(R, 'x10'), (R, 'x11')}),
                stat_mass=_kg({(R, 'x7')}) + sum(row_g(r) for r in ROWS if r[0] == T) / 1000.0,
                head_box=_kg({(R, 1), (R, 'x1'), (R, 'x2'), (R, 'x3'), (R, 'x4'), (R, 'x5'), (R, 'x6'), (R, 'x12'), (R, 'x13'), (R, 'x14')}),
                head_elec=_kg({(E, f'e{i}') for i in (3, 4, 5, 6, 8, 9, 10, 11)}), drivers=_kg({(E, 'e1')}))


def made_parts(rep=None):
    """Per made part of the report (catalogue solids excluded): finished mass and the blank it is cut from."""
    rep = rep or REP
    out = []
    for n, v in rep['parts'].items():
        if v['process'] == 'bought' or v.get('mass_g') is None or n in CATALOGUE_SOLIDS:
            continue
        d = sorted(abs(v['bbox'][i + 3] - v['bbox'][i]) for i in range(3))
        rho = v['mass_g'] / v['volume_cm3'] if v['volume_cm3'] else 0.0      # g/cm3
        p = v['process']
        e = dict(name=n, part=v['part'], process=p, fin_g=v['mass_g'], dims=d, rho=rho)
        if p == 'laser_2mm':
            e.update(net_m2=v['volume_cm3'] * 1000 / 2.0 / 1e6, rect_m2=d[2] * d[1] / 1e6)
            e['stock_g'] = e['rect_m2'] * 1e6 * 2.0 / 1000 * rho
        elif p == 'cnc_plate_10mm':
            e['stock_g'] = max(v['mass_g'], (d[2] + 2 * MARGIN_MM) * (d[1] + 2 * MARGIN_MM) * 10.0 / 1000 * rho)
        elif p == 'cnc_block_16mm' or (p == 'sawn_bar' and v['part'] == 'Bar'):
            e['len_mm'] = d[2] + CUT_MM
            e['stock_g'] = max(v['mass_g'], e['len_mm'] * max(BAR_T_MM, d[0]) * d[1] / 1000 * rho)
        elif p == 'sawn_bar':
            e['len_mm'] = d[2] + CUT_MM
            e['stock_g'] = e['len_mm'] * ANGLE_KG_M
        elif p == 'shs_25':
            e['len_mm'] = d[2] + CUT_MM
            e['stock_g'] = e['len_mm'] * SHS_KG_M
        elif p == 'turned':
            e['bar'] = (max(d[0], d[1]) + BAR_MARGIN_MM, d[2] + CUT_MM)
            e['stock_g'] = max(v['mass_g'], math.pi * e['bar'][0] ** 2 / 4 * e['bar'][1] / 1000 * rho)
        elif p == 'cut_gasket':
            e.update(rect_m2=d[2] * d[1] / 1e6, t=d[0])
            e['stock_g'] = e['rect_m2'] * 1e6 * d[0] / 1000 * NEOPRENE_G_CM3
        else:
            e['stock_g'] = v['mass_g']
        out.append(e)
    return out


def stock(parts=None):
    """Buy-in quantities per stock, from made_parts() (None without a report): sheet incl. 30 % nesting, plate blanks, 16 mm bar, SHS, angle, stainless round, neoprene."""
    if parts is None:
        if not REP:
            return None
        parts = made_parts()

    def sel(*procs, part=None):
        return [e for e in parts if e['process'] in procs and (part is None or e['part'] == part)]
    sheet = sel('laser_2mm')
    plate = sel('cnc_plate_10mm')
    bar = sel('cnc_block_16mm') + sel('sawn_bar', part='Bar')
    shs = sel('shs_25')
    angle = sel('sawn_bar', part='Angle')
    ss_r = sel('turned')
    neo = sel('cut_gasket')
    rect = sum(e['rect_m2'] for e in sheet)
    shaft_fin = next(r for r in ROWS if (r[0], r[1]) == (T, 15))[7]        # not in the report: est., bar = 2 x finished mass
    return dict(sheet_net_m2=sum(e['net_m2'] for e in sheet), sheet_rect_m2=rect, sheet_m2=rect * NEST, sheet_kg=rect * NEST * SHEET_KG_M2,
                plate_fin_kg=sum(e['fin_g'] for e in plate) / 1000, plate_kg=sum(e['stock_g'] for e in plate) / 1000,
                bar_m=sum(e['len_mm'] for e in bar) / 1000, bar_kg=sum(e['stock_g'] for e in bar) / 1000,
                shs_m=sum(e['len_mm'] for e in shs) / 1000, shs_kg=sum(e['stock_g'] for e in shs) / 1000,
                angle_m=sum(e['len_mm'] for e in angle) / 1000, angle_kg=sum(e['stock_g'] for e in angle) / 1000,
                ss_kg=(sum(e['stock_g'] for e in ss_r) + 2.0 * shaft_fin) / 1000, ss_n=len(ss_r) + 1,
                neo_m2=sum(e['rect_m2'] for e in neo) * NEST, neo_kg=sum(e['stock_g'] for e in neo) * NEST / 1000)


def markdown():
    """Mk4 BOM section as a list of markdown lines."""
    t = totals()
    st = stock()
    o = ['## SARCTrac Mk4 replica (LSR2_DESIGN=mk4, default)\n',
         'Source: `calc/lsr2_mk4_bom.py`, the single source of the Mk4 cost, mass and stock quantities. Lines `Rotator Assembly`, `Saddle` and `Thrust Bearing` are the three parts lists of the SARCNET Mk4 FreeCAD files '
         '(MIT licence, `third_party/sarctrac-mk4/`); the item number is in the last column. Lines marked `x` are model parts that are not rows of those lists '
         '(laser-cut cover and enclosure, corner blocks, mast bracket, platform, lift arms, EL hubs, dust caps, gaskets) and the electronics block is the Mk4 electronics. '
         'Every price is an estimate (**est.**, EU hobby suppliers, 2026); laser and CNC job prices are quotes to request before ordering. '
         + ('Made-part masses are the finished solids of `build/lsr2_build_report.json` (basis `report`, one value per part). '
            if REP else '**`build/lsr2_build_report.json` (mk4) was not found: made-part masses below are the BOM estimates (solid volume x 2.70 / 8.0 g/cm3), not the report.** ')
         + 'Bought masses are catalogue values (`cat.`) or estimates (`est.`). The report models the pipe clamps and end stops as simplified solids; their catalogue masses are used.\n',
         '| Item | Qty | Description | Material / spec | Process | Unit EUR (est.) | Total EUR (est.) | Mass g (each) | Source / ref |',
         '|---|---|---|---|---|---|---|---|---|']
    for r in ROWS:
        grp, item, q, desc, mat, proc, u, m, ref, _ = r
        o.append(f'| {grp[:3] if grp != E else "El"}-{item} | {q} | {desc} | {mat} | {proc} | {u:.2f} | {q * u:.2f} | {m:.1f} ({basis(r)}) | {ref} |')
    o += ['', '### Totals (est.)\n', '| Item | Value |', '|---|---|',
          f'| **Cost, one rotator (incl. PSU and motor/sensor cable; without mast, antennas and coax run)** | **{t["eur"]:.0f} EUR (est.)** |',
          f'| **Mass, rotator head, electronics housing, lift arms, saddle and fasteners** | **{t["kg"]:.2f} kg** |',
          f'| of which made parts ({SOURCE}) | {t["made_g"]:.0f} g |',
          f'| of which bought parts and estimates (catalogue / est.) | {t["bought_g"]:.0f} g |',
          f'| Aluminium sheet, 2 mm laser parts (sum of the part rectangles, before nesting) | {t["sheet_m2"]:.3f} m2 |',
          f'| Aluminium plate and bar to machine (10 mm plate, 16 mm bar; finished mass) | {t["plate_kg"]:.2f} kg |',
          '', 'Mass scope: included are the rotator head (mounting plate, covers, corner blocks, enclosure, platform), the electronics housing with the drivers, the two gearbox + motor assemblies, '
          'the lift arms, the saddle and the thrust bearing stack, and all fasteners. Excluded: mast, antennas, cables (and the motor/sensor cable in this list) and the indoor 48 V PSU. '
          'The cost total does include the PSU and the motor/sensor cable.', '']
    gr = by_group()
    o += ['| Cost group | EUR (est.) |', '|---|---|'] + [f'| {k} | {v:.0f} |' for k, v in gr.items()] + [f'| **Total** | **{sum(gr.values()):.0f}** |', '']
    o += ['| Process | Cost EUR (est.) | Mass kg |', '|---|---|---|']
    for p, (e, g) in by_process().items():
        o.append(f'| {p} | {e:.0f} | {g / 1000:.2f} |')
    o += ['']
    if st:
        o += ['### Stock to buy (incl. nesting and blank margin)\n',
              f'Computed from the part bounding boxes of the build report: sheet = sum of the part rectangles + {int((NEST - 1) * 100)} % nesting; plate blank = bounding box + {MARGIN_MM:g} mm per side x 10 mm; '
              f'16 mm bar = 16 mm x part width x (length + {CUT_MM:g} mm cut); SHS and angle length + {CUT_MM:g} mm cut per piece; stainless round = largest step + {BAR_MARGIN_MM:g} mm. '
              'The same numbers are in [LSR2_MATERIALS](LSR2_MATERIALS.md).\n',
              '| Stock | Quantity | Mass kg |', '|---|---|---|',
              f'| 2 mm 5754/5083 sheet (laser parts, net {st["sheet_net_m2"]:.3f} m2 of material, rectangles {st["sheet_rect_m2"]:.3f} m2) | {st["sheet_m2"]:.2f} m2 | {st["sheet_kg"]:.2f} |',
              f'| 10 mm 6082 plate (blanks; finished {st["plate_fin_kg"]:.2f} kg) | | {st["plate_kg"]:.2f} |',
              f'| 16 mm 6082 bar | {st["bar_m"]:.2f} m of cut pieces | {st["bar_kg"]:.2f} |',
              f'| 25 x 25 x 2 SHS | {st["shs_m"]:.2f} m | {st["shs_kg"]:.2f} |',
              f'| 32 x 32 x 3 angle | {st["angle_m"]:.2f} m | {st["angle_kg"]:.2f} |',
              f'| Stainless 1.4404 round ({st["ss_n"]} turned parts: 3 hubs + the NMRV30 shaft, est.) | | {st["ss_kg"]:.2f} |',
              f'| 3 mm neoprene sheet (motor gaskets) | {st["neo_m2"]:.3f} m2 | {st["neo_kg"]:.2f} |', '']
    o += ['The two worm gearbox assemblies (NMRV30-G50-D11, 23HS32-4004S, adaptor) dominate the cost and the mass. The lift-arm solid of the report includes the steel counterweight leaf of the SARCNET part file. '
          'See [LSR2_MK4](LSR2_MK4.md) for the build and [OPEN_ITEMS](OPEN_ITEMS.md).\n']
    return o


if __name__ == '__main__':
    print('\n'.join(markdown()))
