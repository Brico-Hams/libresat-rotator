# LSR-2 acceptance checklist (Lista de aceptación)

Authors: Anatol EA5KAO, Diego EA5JEF, Pedro Roca Molina (BricoHams). One page that ties the three layers of evidence: the **calculated** checks ([LSR2_SIZING](LSR2_SIZING.md), `make verify`), the **bench** tests ([LSR2_TEST_PLAN](LSR2_TEST_PLAN.md)) and the **calibration** acceptance ([CALIBRATION](CALIBRATION.md)). A line is signed only when its closing evidence exists. Items that need the real world are tracked in [OPEN_ITEMS](OPEN_ITEMS.md).

## 1. Before metal: the model

| # | Check | Command / source | Pass |
|---|---|---|---|
| A1 | Every safety factor in LSR2_SIZING meets its target (loads, bearings, clamps, keys, bolts, pointing error, power, hold-up) | `python calc/lsr2_sizing.py --check` | exit 0 |
| A2 | Materials, mass and cost within the limits of the brief | `python calc/lsr2_materials.py --check` | exit 0 |
| A3 | Cast parts follow the foundry rules (wall, fillet R ≥ `min_fillet`, draft, hot spots) and the pure-Python self-tests of `cad/lsr2/*.py` pass | `make lsr2` | no assertion |
| A4 | Parts are watertight and the EL sweep (-30…150°) is free of collisions | `python scripts/verify_stl.py`, `docs/img/lsr2_el_sweep.png` | no failure |
| A5 | Firmware and software tests | `make test` | all pass |
| A6 | Drawings, BOM and wiring regenerated | `make lsr2` (`docs/drawings/`, `docs/BOM_LSR2.md`) | files updated |

## 2. First article and bench (physical)

| # | Calculated value being confirmed | Test | Acceptance |
|---|---|---|---|
| B1 | Part dimensions, fits, datums | [LSR2_INSPECTION](LSR2_INSPECTION.md) / S0-1 | in tolerance |
| B2 | Mass ≤ limit | S0-3 | ≤ 28 kg with antenna |
| B3 | Bearing play, free rotation | S0-2 | ≤ 0.05 mm at 1 m lever |
| B4 | Speed 12°/s, 1066.7 steps/s | S1-4 | reached without stall |
| B5 | Backlash (SIZING §10) | S1-3 | residual ≤ 0.02° |
| B6 | Repeatability | S1-2, S2-2 | ≤ 0.05° |
| B7 | Power budget (SIZING §15) | S1-8 (ammeter on the 48 V rail) | peak ≤ prediction; record the real supply current |
| B8 | Hold-up for the power-loss save | S1-7 | position recovered ≤ 0.1° in 20 cuts |
| B9 | Gearbox torque (SIZING §5) | S2-6 | ≤ 13.4 N·m in operation |
| B10 | Balance residual | S2-1 | ≤ 1.5 N·m |
| B11 | Wind deflection and clamp slip | S2-3 | ≤ 0.1° at the equivalent of 25 km/h; no slip |
| B12 | Sealing | S2-4 | no water; only the passed level is claimed |
| B13 | VHF/UHF noise | S2-5 | ≤ 1 dB rise |
| B14 | Temperature | S1-8 | driver wall ≤ 60 °C |

## 3. Pointing accuracy (the deciding acceptance)

| # | Step | Acceptance |
|---|---|---|
| C1 | Level, GPS, Sun, index/backlash calibration ([CALIBRATION](CALIBRATION.md) steps 1–6) | every step completes |
| C2 | `lsr pointing fit` over at least 12 marks across the sky (30 for the full test S3-1) | residual RMS **< 0.1°** |
| C3 | Enable `pointing` and `control`; five satellite passes with Doppler (S3-2) | no loss of lock, path within 0.1° |
| C4 | Re-inspection after a week of weather (S3-4) | no corrosion, bolts at torque |

## 4. Sign-off

| Stage | Date | Who | Test configuration | Result |
|---|---|---|---|---|
| A (model) | | | commit: | |
| B (bench, stages 0–2) | | | | |
| C (pointing, stage 3) | | | | |
