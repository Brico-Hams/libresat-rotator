# Test plan

## 1. Automated (run on every change: `make test`)

| ID | What | Where | Pass criterion |
|---|---|---|---|
| T-U1 | Firmware core: kinematics, cable-wrap resolution, planner (no overshoot, follows 1°/s with < 0.1° lag), Easycomm/LSR parser, NMEA, CRC | `firmware/test/test_core.cpp` | 46 checks, 0 failures |
| T-U2 | Look angles and range rate vs Skyfield; Sun vs equinox/solstice; locator | `software/tests/test_astro.py` | \|Δaz\|, \|Δel\| < 0.01°; \|Δṙ\| < 2 m/s |
| T-U3 | Passes and planner: limits respected, line of sight within 5° in flip, high pass uses flip under 0.8·vmax | `test_passes.py` | all pass |
| T-U4 | Doppler FM / linear inverting with knob follow; SatDB | `test_doppler.py` | exact formulas, 1 Hz |
| T-U5 | rotctld protocol (p/P/S/K, dump_state v1, extended `+`) | `test_rotctld.py` | Hamlib-compatible replies |
| T-U6 | FTX-1 command strings and serial I/O; Hamlib VFO-mode commands | `test_rigs.py` | byte-exact |
| T-U7 | OpenGD77 keps block **byte-identical to WebCPS**; custom-data patching; clock-sync byte sequence | `test_opengd77.py` | byte-exact |
| T-U8 | Full simulated pass: preposition → tracking → idle, Doppler and tone to the radio, pointing error | `test_tracker.py` | error < 3° (simulated mechanics) |
| T-C1 | Cycloid meshing over a full cycle | `calc/cycloid_check.py` | clearance 0.05–0.3 mm, envelope inside the bore |
| T-P1 | PCB DRC | `hardware/pcb/lsr_ctl_drc.rpt` | 0 unconnected, 0 clearance errors |
| T-M0 | Every STL watertight | `make verify` | all True |

## 2. Bench tests (one rotator, before the first field day)

Record the results in the table at the end.

| ID | Test | Method | Pass criterion |
|---|---|---|---|
| T-E1 | Power protection | Current-limited supply: 12 V, reversed polarity, 26 V | VM 0 V when reversed; 5 V within ±3 %; nothing warm |
| T-E2 | Idle consumption | 12 V, motors enabled at rest | ≤ 3.5 W (sizing: 2.8 W) |
| T-E3 | TMC UART | `XT` | both `ok=1`, `ot=0 s2g=0 ola=0 olb=0` with the motors connected |
| T-E4 | Sensors | `XS` | `enc=1,1`, `imu_el` within 1° of an inclinometer, `tilt` < 0.3° on a level table, `gps=1,…` outdoors within 2 min |
| T-M1 | Gear ratio | Mark the output; command 360° | the mark returns within 0.5° |
| T-M2 | Repeatability | 20 × `AZ0 → AZ180 → AZ0` and `EL0 → EL90 → EL0`, measure with a dial or laser on the wall | ≤ 0.3° spread |
| T-M3 | Backlash | Laser pointer on the stub, 3 m from a wall; push the output by hand both ways at rest | ≤ 0.5° (≤ 26 mm spot movement at 3 m) |
| T-M4 | Holding torque | Lever on the stub (0.2 m) with weights; motors holding at full current | EL slips above ≥ 3 Nm (1.5 kg at 0.2 m) |
| T-M5 | Running torque | Same lever, command EL 0 → 60° at 5°/s | no `slips` with 1.0 kg at 0.2 m (2 Nm) |
| T-M6 | Speed | `AZ0` → `AZ180` | 9–10 s (20°/s with ramps), no slips |
| T-M7 | Thermal | 1 h continuous tracking simulation (`lsr track` on a high-pass satellite in `auto_next`) | drivers < 70 °C, motors < 60 °C, printed parts unchanged |
| T-S1 | rotctld | `rotctl -m 2 -r lsr.local:4533`: `P 120 30`, `p` | moves, reports |
| T-S2 | FTX-1 CAT | `lsr track SO-50` with the FTX-1 connected, before AOS | MAIN shows ~436.80x MHz, SUB ~145.85x MHz, modes FM/FM; values change during the pass |
| T-S3 | Knob follow | Linear satellite (RS-44): turn the MAIN knob 5 kHz up | SUB moves 5 kHz down (inverting) within 1 s |
| T-S4 | OpenGD77 | `lsr gd77 info`, then `clock` | model and build reported; the radio clock equals UTC ±1 s |

## 3. Acceptance (field)

| ID | Test | Pass criterion |
|---|---|---|
| T-F1 | Sun-tracking accuracy: after the sun alignment, track the Sun for 1 h (Manual → go to the Sun position every 5 min) | the spot stays on the target (≤ 1°) |
| T-F2 | Real pass: FM satellite, max el > 60°, with a SpaceQuad-class antenna | continuous copy from 5° to 5°; Doppler-corrected audio without retuning |
| T-F3 | Flip pass > 80° | the planner chooses flip; no loss of signal around TCA |
| T-F4 | Battery runtime: LiFePO4 6 Ah, normal session | ≥ 12 h |
| T-F5 | Packing: everything except the tripod and antenna in one bag | ≤ 3 kg, ≤ 10 min to set up |

## Results sheet

| ID | Date | Result | Notes |
|---|---|---|---|
| | | | |
