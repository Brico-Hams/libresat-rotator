# Changelog

## Unreleased: LSR-2 phase 6c (SARCTrac Mk5 alignment, SARCNET data)
- **Firmware 1.1.0:** LSR-2 at 400 microsteps/rev, EasyComm II 9600 8N1 default, photo-interrupter index homing, `XCAL BACKLASH` / `XCAL HOMEEL`, 48 V power-loss detect with save to flash (error bit 64); `main.cpp` preprocessor lines repaired.
- **Software:** optional pass-planner anti-windup (`Limits.anti_windup`, default off).
- **CAD/BOM:** index discs and sensor bracket (`cad/lsr2/index_parts.py`), M30×56×3 shim, 57BYG250H-8, electronics BOM, budget-build section.
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
