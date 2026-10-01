# Changelog

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
