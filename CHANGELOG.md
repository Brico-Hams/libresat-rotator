# Changelog

## Unreleased: single source for LSR-2 Mk4 mass, cost and stock
- **BOM/materials:** `calc/lsr2_mk4_bom.py` is the only source of the Mk4 total: made-part masses from `build/lsr2_build_report.json` (fallback: own estimates, stated in the document), bought-part masses from catalogue values; cost groups, process subtotals and buy-in quantities per stock. `calc/lsr2_materials.py` takes its total from it and asserts equality; `cad/lsr2/inputs.py` reads the masses for the sizing. Mass scope: rotator head, electronics housing, lift arms, saddle and fasteners (no mast, antennas, cables, indoor PSU).
- **Docs:** README, ARCHITECTURE, ELECTRONICS, FIRMWARE, ASSEMBLY (order from the SARCNET assembly drawings), tolerances/inspection (Mk4 laser and CNC plate rows; generator `cad/lsr2/tolerances.py`), routes A/B headers and captions now describe the Mk4 default; the cast/CNC open box is labelled as the optional variant; stale 80:1, DM542, 57BYG250H-8 figures replaced.

## Unreleased: LSR-2 phase 12 (SARCTrac Mk4 replica, default design)
- **Design:** LSR-2 is now a replica of the SARCNET SARCTrac Mk4, built from the SARCNET FreeCAD files under the MIT licence (`third_party/sarctrac-mk4`, see PROVENANCE.md). The phase-11 cast/CNC design is the optional variant `LSR2_DESIGN=cast`; there no SARCNET geometry is used.
- **BOM:** `docs/BOM_LSR2.md` now has the three SARCNET parts lists plus electronics (generator `calc/lsr2_mk4_bom.py`, `scripts/bom.py`); the cast BOM is a separate section.
- **Sizing:** gearbox ratio is a parameter (50 for Mk4, 80 for cast); motor 23HS32-4004S 2.4 N·m, 48 V; new powered-holding-torque check. Regenerate the reports with `make calc`; any check below target is reported as such.
- **Firmware:** LSR-2 profile ratio 80 → 50 (666.7 steps/s at 12 °/s); NJK-5002C Hall index and end stops documented. LSR-1 unchanged.
- **Docs:** new `docs/LSR2_MK4.md`; README, ARCHITECTURE, OPEN_ITEMS, assembly, test plan, risks and Fusion docs updated.

## Earlier: LSR-2 phase 6c (SARCTrac Mk5 alignment, SARCNET data)
- **Firmware 1.1.0:** LSR-2 at 400 microsteps/rev, EasyComm II 9600 8N1 default, photo-interrupter index homing, `XCAL BACKLASH` / `XCAL HOMEEL`, 48 V power-loss detect with save to flash (error bit 64); `main.cpp` preprocessor lines repaired.
- **Software:** optional pass-planner anti-windup (`Limits.anti_windup`, default off).
- **CAD/BOM:** index discs and sensor bracket (`cad/lsr2/axes.py`), M30×56×3 shim, 57BYG250H-8, electronics BOM, budget-build section.
- **Docs:** Mk5 decision table in ARCHITECTURE §7b, calibration and inspection procedure, tracker list.

## 1.0.0 — 2026-10-01
First complete release:
- **Mechanics:** printed 25:1 cycloid actuators, base and head, tripod adapters (3/8″, 5/8″, 35 mm, mast), antenna clamps, sun sight, e-box.
- **Electronics:** LSR-CTL board (Pico + 2 × TMC2209 + 5 V buck + Pi Zero 2 W socket), autorouted and DRC-clean, with Gerbers.
- **Firmware:** Easycomm II + LSR extensions, closed loop with AS5600, IMU elevation, hall index, GPS, flash settings.
- **Head software:**
  - tracker with the flip / cable-wrap planner;
  - rotctld server and mobile web UI;
  - FTX-1 CAT, Hamlib and OpenGD77 tools;
  - simulator and tests.
- **Documentation:** in English.
