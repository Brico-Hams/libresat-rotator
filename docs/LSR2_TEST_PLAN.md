# LSR-2 prototype test plan (Pruebas del prototipo)

Authors: Anatol EA5KAO, Diego EA5JEF, Pedro Roca Molina (BricoHams). REV A0, phase 11e. Progressive tests of the first prototype, in three stages: **unloaded**, **with test loads**, **with the target antenna** once the supports have been validated. A stage starts only when the previous one is signed off. Predicted values come from [LSR2_SIZING](LSR2_SIZING.md); the calibration chain is in [CALIBRATION](CALIBRATION.md); inspection of the parts before this plan is [LSR2_INSPECTION](LSR2_INSPECTION.md); risks are in [LSR2_RISKS](LSR2_RISKS.md).

## Fixed bench (Banco fijo)

- Mast stub: a Ø60.3 x 3.6 steel tube (1 m, **PARAMETRIC**, the design mast) welded or clamped to a rigid steel plate bolted to a bench or the floor; the mast bracket is clamped on it with the torque table of [LSR2_ASSEMBLY](LSR2_ASSEMBLY.md).
- Instruments: dial indicator (0.01 mm) on a magnetic base with a 1 m lever bar (0.01 mm at 1 m = 0.0006°), digital inclinometer 0.01°, force gauge 0-100 N, stopwatch or the firmware step counter, thermocouples or an IR thermometer, ammeter on the 48 V rail, an SDR or receiver for the noise test, a scale (kg), a water supply with a nozzle for the spray test.
- Firmware: `lsr2` profile (EasyComm II 9600 8N1), `XR` raw data and XCAL commands; software logs to a CSV (time, commanded, encoder, current, temperature, wind if available). Every result is entered in the table at the end with the **test configuration** (loads, firmware revision, ambient temperature, wind).

## Stage 0: before powering the head

| ID | Test | Method | Acceptance |
|---|---|---|---|
| S0-1 | Parts inspected | [LSR2_INSPECTION](LSR2_INSPECTION.md) first-article sheet | every row inside tolerance |
| S0-2 | Bearing free torque and play | rotate each axis by hand, dial indicator on the end of the boom | smooth, no axial play on AZ, radial play ≤ 0.05 mm at the boom end per 1 m lever (PARAMETRIC) |
| S0-3 | Mass | scale | ≤ 28 kg with antenna, body+lid within 10 % of the `inputs.HEAD` estimates |

## Stage 1: unloaded (head only)

| ID | Test | Method | Acceptance |
|---|---|---|---|
| S1-1 | Run-in | 30 full-range cycles per axis at 6 then 12°/s | no abnormal noise or heating; no lost steps (encoder agrees) |
| S1-2 | Repeatability | 5 positions per axis, 20 approaches each, from both directions, dial indicator or inclinometer | ≤ 0.05° (50 % of the pointing budget) |
| S1-3 | Backlash | `XCAL BACKLASH` plus the external reference | raw about 0.5° (SIZING predicts AZ 0.50°, EL 0.61°); firmware residual ≤ 0.02° |
| S1-4 | Speed and acceleration | time 360° AZ and 180° EL, step counter | 12°/s reached, 1066.7 steps/s at 400 microsteps/rev, no stall |
| S1-5 | Contact-free travel | slow full travel AZ ±360°, EL -30…150° with the real harness and coax | no contact between boom, yoke, lift arms and body, cables not stressed, bend radius ≥ 10 × OD (min distance logged) |
| S1-6 | Stopping and soft limits | approach each limit at 12°/s, bumper test | stops inside the 9.6° margin, no hard-stop impact, stop distance recorded |
| S1-7 | Reference recovery | power cut during motion (20 times), restart, home on the index sensors | position recovered to ≤ 0.1° each time; the 2200 µF bank saves the position (PWRFAIL) |
| S1-8 | Temperature | 30 min of continuous tracking at 3 A, ambient noted | driver wall ≤ 60 °C and no thermal shutdown (PARAMETRIC; check the DM542 datasheet limit) |

## Stage 2: test loads

Dead weights on the boom (clamped, not on the antenna foot plates): a mass pair that reproduces the design payload moment (6 kg crossed-Yagi pair at the ±0.65 m stations, CG 0.05 m ahead of the EL axis, MEASURE the real value), then 50 % and 150 % of it.

| ID | Test | Method | Acceptance |
|---|---|---|---|
| S2-1 | Balance | adjust the counterweights until the residual EL torque (motor current at rest at EL 0, 45, 90°) is minimal | residual ≤ 1.5 N·m (`cw_res_max`) |
| S2-2 | Speed, drift and repeatability under load | repeat S1-2 and S1-4 with the load; hold a position 24 h with the inclinometer | repeatability ≤ 0.05°, 12°/s kept, drift ≤ 0.02° per 24 h, no creep of the worm |
| S2-3 | Wind surrogate | force gauge on the boom end (20 N, 40 N, side and end-on); also on the mast clamp and the clamp blocks | deflection and torsion consistent with SIZING (pointing error ≤ 0.1° at the equivalent of 25 km/h, 0.094° AZ / 0.090° EL predicted); no clamp slip |
| S2-4 | **Sealing: water spray test** | closed head, harness fitted: spray from all directions (IPX4-style, 10 min, nozzle per IEC 60529); then open the lid and inspect with dry paper and a moisture indicator | no water inside. **No IP rating is claimed before this passes**, and only the level actually passed is claimed |
| S2-5 | VHF/UHF noise | receiver on the coax of a dummy antenna at 145 and 435 MHz, drivers idle and moving | noise floor rise ≤ 1 dB (PARAMETRIC); if not, ferrites, chopping frequency and shielding per ELECTRONICS |
| S2-6 | Gearbox torque | log the motor current over a tracked pass and a 12°/s slew | output torque ≤ 13.4 N·m allowed (SF 1.25) in operation |

## Stage 3: with the target antenna

Only after S2 is signed off and the supports (mast clamp, boom clamps, saddle) show no slip.

| ID | Test | Method | Acceptance |
|---|---|---|---|
| S3-1 | Pointing | calibrate (level, GPS, Sun, index/backlash), then `lsr pointing fit` over 30+ points; Sun tracking for an hour | pointing residual RMS **< 0.1°** ([CALIBRATION](CALIBRATION.md)) in wind ≤ 25 km/h |
| S3-2 | Satellite passes | five passes with Doppler on 145 and 435 MHz | no lost lock, no stall faults, tracked path within 0.1° of the planned |
| S3-3 | Weather | log rain, wind and temperature for a week; park rule in strong wind | no water inside after the rain, no clamp slip, ambient and driver temperature recorded |
| S3-4 | Re-inspect | open the lid, re-torque, check gasket and bearings | no corrosion, bolts at torque, no play increase |

## Results to publish (Resultados)

Fill one row per test, run it with the configuration used, and publish the table with the measured envelope (sweep, mass, speed, accuracy). Predicted values are the SIZING numbers.

| Test ID | Configuration (load, antenna, firmware rev, ambient °C, wind km/h) | Predicted | Measured | Criterion | Pass |
|---|---|---|---|---|---|
| S1-2 | | repeat ≤ 0.05° | | ≤ 0.05° | |
| S1-3 | | AZ 0.50°, EL 0.61° raw | | residual ≤ 0.02° | |
| S1-4 | | 12°/s | | 12°/s | |
| S1-5 | | no contact | | no contact | |
| S1-6 | | margin 9.6° | | no impact | |
| S1-7 | | recovery | | ≤ 0.1° | |
| S1-8 | | driver wall | | ≤ 60 °C | |
| S2-1 | | ≤ 1.5 N·m | | ≤ 1.5 N·m | |
| S2-2 | | drift | | ≤ 0.02° / 24 h | |
| S2-3 | | 0.094° / 0.090° at 25 km/h | | ≤ 0.1° | |
| S2-4 | | tested, not claimed | | no water | |
| S2-5 | | noise floor | | ≤ 1 dB | |
| S2-6 | | ≤ 13.4 N·m | | ≤ 13.4 N·m | |
| S3-1 | | RMS | | < 0.1° | |
| S3-2 | | passes | | no loss of lock | |

Measured envelope to publish: sweep (AZ ±360°, EL -30…150°), total mass, speed under load, repeatability, backlash after compensation, temperature at 3 A, tested sealing level, test configuration.
