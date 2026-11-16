# Calibration and field use

## Once, at home (bench calibration)

1. **Motor directions.**
   - Send `MR` (azimuth jog clockwise seen from above, i.e. increasing azimuth) and `MU` (elevation up).
   - If either turns the wrong way, set `XC dir_az=-1` or `XC dir_el=-1`.
2. **Encoders.**
   - Command `AZ90` and watch `XS slips=`. It must stay at 0.
   - If it rises on every move, the encoder sense is reversed: set `XC enc_az=-1` (and the same for elevation).
3. **Boom IMU.**
   - Put a bubble level on the boom and level it with `MU`/`MD`.
   - Send `XCAL EL=0`, then `XCAL ELIMU`.
   - Raise the boom to 45° (phone inclinometer) and check that `XS imu_el` ≈ 45. If it reads −45, set `XC imu_el_dir=-1` and repeat.
4. **Base IMU.** With the base on a level surface, send `XCAL LEVEL`.
5. **Index.**
   - Send `HOME`. The rotator turns until the magnet passes the sensor.
   - Then sun-align (below) and send `XCAL HOMEAZ`. From then on `HOME` restores true azimuth with no Sun.
6. **Update TLEs and the satellite list** (internet needed):
   - `lsr tle update`;
   - optionally `lsr satdb update`;
   - for OpenGD77 radios: *Upload keps*, then *Sync clock*.

## Phase 8: automatic calibration (optional)

Steps 2, 4 and 5 above can be done by the software: `lsr calibrate level|compass|sun|sun-manual|index|all`, then `lsr pointing fit <points.csv> --save --enable`. Procedure, sensors and acceptance (residual RMS < 0.1°) in [CALIBRATION](CALIBRATION.md).

## In the field: about 10 minutes

| Step | Action | Check |
|---|---|---|
| 1 | Set up the tripod; bolt the rotator on with the right adapter. Hang the battery from the tripod hook. | |
| 2 | Level the tripod legs | Web UI **Calibrate** → tilt < 0.5° on both axes |
| 3 | Mount the antenna at its CG, the sun sight on top. Connect the coax and the cable loop. | The boom turns 0→180° without touching anything (jog `MU`) |
| 4 | Power on: XT30 or PD cable. Join the `LibreSat-Rotator` Wi-Fi and open `10.42.0.1:8080`. | Status pill green; the locator shows "(GPS)" after 1–2 min |
| 5 | **True north with the Sun:** jog until the Sun's light spot through the pinhole lands on the target's cross-hair, then press **Antenna is on the Sun**. | `XS err` clears bit 1. Azimuth error ≈ the alignment precision (< 1°). |
| 6 | No Sun (night or clouds)? Use `HOME` if the index azimuth is stored, or align the base **N** arrow to a known landmark bearing and send `XCAL AZ=<bearing>`. | |
| 7 | Pick the satellite and transponder, then **Track**. | The rotator prepositions 2 min before AOS. The plan (normal/flip) shows under the satellite selector. |
| 8 | Radio: FTX-1 with SUB as TX and satellite full duplex; the CTCSS tone for FM birds. With OpenGD77, select Satellite → the same satellite. | RX/TX frequencies move on the **Radio** tab |

**Linear transponders:** tune the downlink with the MAIN knob. The uplink follows. Find yourself by sending a short CW or voice and listening to your own downlink.

**When done:** **Park** (elevation 90°: the boom vertical has the least wind load), then power off. In strong wind take the antenna down; the cycloid is not self-locking when unpowered.

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `err=1` after power-up | The position changed while powered off (someone turned it). Run HOME or the sun alignment. |
| `err=2` | Boom IMU not answering: check the CAT5e Y split, J8, and that I²C1 runs at 100 kHz. |
| `err=4` | TMC UART not answering: the module pinout differs (close JP1/JP2) or there is no motor power. |
| `slips` keeps rising | Too much load or wind, or the encoder sense is reversed. Raise `irun` to 1200, balance the antenna, check `enc_dir`. |
| Grinding or knocking in an actuator | Discs mounted in the same phase (they must be 180° apart), the cam has slipped, or `PROFILE_CLR` is too small |
| Pointing is right in the north, wrong in the south | The tripod is not level: re-check the tilt |
| Doppler is heard drifting at TCA | Old TLE (> 1–2 weeks) or a wrong clock: check that the locator shows (GPS) and the TLE age in Setup |
