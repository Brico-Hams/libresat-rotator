# Firmware (RP2040)

The source is in `firmware/src/`:

| File | What it holds |
|---|---|
| `core.cpp` | Hardware-independent logic: kinematics, the planner, parsers and CRCs. It is unit-tested on the PC. |
| `hw.cpp` | Drivers: TMC2209 over a PIO UART, AS5600, MPU-6050, GPS and flash settings. |
| `main.cpp` | Motion, the closed loop, referencing and the protocol. |
| `config.h` | Pins and defaults. |

## Build and flash

```bash
export PICO_SDK_PATH=/path/to/pico-sdk          # 2.x, with lib/tinyusb
cd firmware && make                              # -> build/lsr1.uf2  (PICO_BOARD=pico2 for a Pico 2)
make lsr2                                        # -> build-lsr2/lsr2.uf2  (LSR-2, external drivers)
make test                                        # host unit checks (no hardware, plain g++ -std=c++17)
```

CMake options: `-DLSR_MODEL=1|2` (default 1) picks the axis profile, `-DLSR_DRIVER=TMC2209_UART|EXT_STEPDIR` picks the driver (default `EXT_STEPDIR` when `LSR_MODEL=2`, else `TMC2209_UART`). Settings saved in flash carry the model, so an LSR-1 build ignores LSR-2 settings and vice versa.

There are three ways to flash:

- **USB:** hold BOOTSEL while plugging in the Pico, then copy `lsr1.uf2` (or `lsr2.uf2`) to the `RPI-RP2` drive. A running board can enter the bootloader with the `XB` command.
- **From the Pi Zero, in the field:** `software/scripts/flash_pico_from_pi.sh build/lsr1.elf`, through J14 SWD and openocd.
- **Debug probe:** any CMSIS-DAP probe on the SWD pads.

## LSR-2 external drivers

One firmware drives both rotators. The profile comes from `lsr_model()` in `core.cpp`:

| | LSR-1 (`LSR_MODEL=1`) | LSR-2 (`LSR_MODEL=2`) |
|---|---|---|
| Gearbox / microsteps | cycloid 25:1 / 16 | NMRV30 50:1 (Mk4 default; 80:1 in the cast variant: set `ratio` in the profile) / 2 (400 microsteps/rev; 55.6 steps/° at 50:1, 666.7 steps/s at 12 °/s) |
| AZ range (wire frame) | 0..450° | 0..720°, i.e. user −360..+360° (wire = user + 360); same wrap logic |
| EL range | 0..180° (flip) | −30..150°, no flip |
| vmax / acc | 20 / 15 °/s, 25 / 20 °/s² | 12 °/s, 10 °/s² |
| Serial | 115200 | 9600 8N1 (EasyComm II default, as Mk5) |
| Index | hall magnet (AZ) | photo-interrupter + notch disc per axis (GP20 AZ, GP21 EL), `HOME` and backlash calibration |
| Power loss | – | `PIN_PWRFAIL` GP22: opto-isolated 48 V detect, position saved to flash |

With `LSR_DRIVER=EXT_STEPDIR` (DM542T, or a TMC5160 in step/dir mode, behind opto-isolated inputs) the firmware makes no TMC UART call: `XT` answers `XT n/a ext driver`, and `tmc=0,0` / error bit 4 are not used. STEP and DIR stay on the LSR-1 pins; the enables are per axis:

| Signal | GPIO | Notes |
|---|---|---|
| STEP AZ / DIR AZ | GP10 / GP11 | as LSR-1 |
| STEP EL / DIR EL | GP12 / GP13 | as LSR-1 |
| ENABLE AZ / EL | GP2 / GP3 | free pins; not routed on LSR-CTL v1.0, take them from the header with a wire |

Levels are set in `config.h`: `EXT_STEP_ACTIVE`, `EXT_DIR_POS_LEVEL`, `EXT_EN_ACTIVE` (default 0: enabled = low, disabled = high, as the DM542T ENA is usually active-low; check your driver). Timing is set by constants in `core.h` and enforced by `sd_tick()` (host-tested):

| Limit | Constant | Value | DM542T datasheet |
|---|---|---|---|
| STEP pulse width | `SD_PULSE_MIN_US` | 3 µs (the 40 µs tick gives 40 µs) | ≥ 2.5 µs, VERIFY |
| DIR set-up before the first STEP edge | `SD_DIR_SETUP_US` | 5 µs | ≥ 5 µs, VERIFY |
| ENABLE settled before the first STEP | `SD_ENABLE_SETTLE_US` | 200 ms (also after `XE 1`) | ≥ 200 ms, VERIFY |

At 12 °/s the step rate is 666.7 steps/s on the 50:1 gearbox (50 × 400 / 30; 1066.7 steps/s with 80:1 in the cast variant), far below the optocoupler limit. The wiring is in [ELECTRONICS](ELECTRONICS.md#lsr-2-external-drivers).

### LSR-2 index, backlash and power loss (Mk5-style, SARCNET)

- **Index.** One slotted photo-interrupter per axis reads a notch in a printed disc. The slot edge is the reference: AZ = north (wire 360°), EL = horizon (0°). `HOME` on LSR-2 searches both axes: seek at 6°/s, clear the slot at 4°/s, creep over the edge at 1°/s always coming from the positive side (so the reference is backlash-free), then park 2° past it. The AZ slot repeats every 360°, so the firmware takes the multiple of 360° nearest to the position estimate: if power was lost without a save, unwind the cable by hand to north before `HOME`. Error bit 32 = slot not found.
- **Backlash.** `XCAL BACKLASH` runs the index search and also crosses the edge from the other side: the difference is the backlash of the gearbox and couplings, stored as `backlash_az` / `backlash_el` (degrees, saved to flash with `XW`). The planner then adds it on every reversal so the output follows the commanded angle; a one-off calibration at assembly, as in the Mk5. `XCAL HOMEEL` stores the current elevation as the EL index angle (`home_el`).
- **Power loss.** The 48 V opto input on GP22 goes high when the supply fails; after 5 ms of debounce the firmware stops the motors, disables the drivers, saves the position and the backlash side to flash and sets error bit 64 (`E_PWR`). When 48 V returns the drivers are re-enabled. Detection is armed only after 48 V has been seen once. The 2200 µF bulk capacitor on the 48 V rail holds the XL7015 long enough for the ~60 ms flash write (VERIFY).
- **Serial.** EasyComm II at 9600 8N1 is the LSR-2 default on UART0 (`PI_BAUD`), as the Mk5 trackers expect; USB CDC ignores the baud rate. Compatible trackers: **PstRotator, Gpredict, SatPC32 and Orbitron** (EasyComm II), plus our own path through Hamlib `rotctld -m 202` and the `lsr` software.
- **Anti-windup.** Shortest-path slewing is native (±360° range, the planner picks the wrap equivalent nearest to the target). `software/lsr` has an optional `anti_windup` limit (profile key `limits.anti_windup`, default off; CLI planner) that prefers the pass geometry ending near the middle of the AZ range, so the cable is unwound between passes. The firmware needs nothing for it. Wiring it into the live tracker takes one line in `tracker.py`: pass `l.get('anti_windup', False)` as the last argument of `Limits(...)`; this file is not touched in phase 6c.

## How it works

| Function | Implementation |
|---|---|
| Step generation | 25 kHz timer IRQ, Q16 phase accumulator per axis, 40 µs step pulses, DIR set-up one tick before the first step. Maximum 12.5 kHz, i.e. 56°/s at the output with 16 microsteps. |
| Motion profile | 500 Hz square-root profile, v = min(vmax, √(2·a·\|e\|)), slewed by the acceleration. No overshoot. It follows a 1°/s target with less than 0.1° lag (unit test). |
| Closed loop | Every 2 ms the AS5600 count is unwrapped and compared with the step counter. If they differ by more than 2 electrical cycles (128 µsteps), the counter is re-synchronised to the encoder (`slips` counter in `XS`). |
| Drivers | TMC2209 over a single-wire UART, addresses 0 (AZ) and 1 (EL). Run current from `irun_*`, hold at `ihold` %, StealthChop, 16 µsteps with interpolation. If the UART does not answer, the error bit 4 is set and the drivers run on their defaults (Vref pot, MS pins). |
| AZ reference | At boot the saved position is accepted if the encoder angle matches the saved angle (± 64 counts). Otherwise the axis is "not referenced" (error 1): run `HOME`, use the sun alignment or send `XCAL AZ=`. `HOME` turns up to +380° at 8°/s looking for the hall magnet, then −380°. |
| EL reference | At boot the elevation is taken from the boom accelerometer: `imu_el=1`, 40 samples. |
| Persistence | Settings and position go to the last 4 KB flash sector, CRC-protected, written after 3 s at rest. Stepping pauses for about 50 ms during the write. |
| Safety | Watchdog 2 s, supply monitor (error 16 below 8.5 V), button: short press stops, 2 s press parks. |
| GPS | NMEA RMC and GGA on UART1 at 9600 baud. Position, altitude, satellite count and UTC are reported in `XS` and `XG`. |

## Protocol

There are two ports with the same commands:
- USB CDC, for a PC, a Pi 4/5 or Hamlib directly;
- UART0 at 115200 baud (9600 8N1 on LSR-2, the EasyComm II default), for the Pi Zero on the header.

Lines end with CR, LF or `;`.

### Easycomm II (Hamlib `rotctld -m 202`, SatNOGS, Gpredict through rotctld)

| Command | Reply | Meaning |
|---|---|---|
| `AZ EL` | `AZ123.4 EL45.0` | position (azimuth reported 0–360) |
| `AZ123.4 EL45.0` | – | go to. Values 0–360 take the cable-wrap equivalent nearest to the current target. Values outside 0–360 are absolute. |
| `SA` / `SE` | – | stop azimuth / elevation (with deceleration) |
| `ML` `MR` `MU` `MD` | – | jog left / right / up / down until `SA`/`SE` |
| `VE` | `VELSR-1 1.0.0` | version |
| `GS` | `GS1` idle, `GS2` moving, +8 on error | status |
| `GE` | `GE<n>` | error bits (table below) |
| `HOME` / `RESET` | – | search the AZ index magnet |
| `PARK` | – | go to `park_az`, `park_el` |

Hamlib's Easycomm extras (`UP000 XXX DN000 XXX`) are accepted and ignored.

### LSR extensions

| Command | Meaning |
|---|---|
| `XP <az> <el>` | Absolute position on the cable-wrap scale (e.g. `XP 395.5 120`). The Pi's pass planner uses it. |
| `XS` | Full status line: `az el taz tel vaz vel mode ref err vin enc slips tmc imu_el tilt gps utc up` |
| `XR` | Raw sensors for the head calibration: `accb=` base and `accl=` boom accelerometer (g), `mag=na` (no magnetometer on the MPU-6050), `enc=` output-encoder angles, `step=` step-count angles, `idx=` index slot levels, `bl=` backlash per axis (the `backlash_az/el` keys of `XC` set it). Unreadable values print `nan`. LSR-1 behaviour is unchanged. |
| `XC?` / `XC <key>` | List or read settings |
| `XC <key>=<value>` | Set a setting (saved automatically when idle; `XW` saves now) |
| `XCAL AZ=<deg>` / `XCAL EL=<deg>` | Declare the current position (sun alignment, level boom) |
| `XCAL ELIMU` | The boom IMU now reads the current elevation |
| `XCAL LEVEL` | The base IMU now reads 0/0 (the tripod is level) |
| `XCAL HOMEAZ` | Store the current azimuth as the index magnet azimuth |
| `XCAL BACKLASH` | LSR-2: index search on both axes plus backlash measurement, stored in flash |
| `XCAL HOMEEL` | LSR-2: store the current elevation as the EL index angle |
| `XE 0` / `XE 1` | Disable or enable the drivers. The motor encoders keep tracking the position while the motors are free; without encoders the AZ reference is cleared. |
| `XG` | GPS fix details |
| `XT` | TMC2209 diagnostics (DRV_STATUS: over-temperature, short to ground, open load) |
| `XB` | Reboot into the USB bootloader |
| `XH` | Help |

### Settings (`XC`)

| Key | Default | |
|---|---|---|
| `ratio_az`, `ratio_el` | 25 | gearbox ratio |
| `usteps` | 16 | microsteps |
| `dir_az`, `dir_el` | 1 | motor sense |
| `vmax_az`, `vmax_el` | 20, 15 °/s | maximum speed |
| `acc_az`, `acc_el` | 25, 20 °/s² | acceleration |
| `min_az`, `max_az` | 0, 450 | cable wrap |
| `min_el`, `max_el` | 0, 180 | set `max_el=90` without flip |
| `irun_az`, `irun_el` | 900 mA | RMS run current (up to 1200 with the heatsinks and the vented box) |
| `ihold` | 35 % | hold current |
| `deadband` | 0.05° | |
| `park_az`, `park_el` | 0, 90 | |
| `home_az` | 0 | azimuth of the index magnet / slot edge |
| `home_el` | 0 | LSR-2: elevation of the EL slot edge |
| `backlash_az`, `backlash_el` | 0 | LSR-2: measured backlash (°), `XCAL BACKLASH` |
| `enc_az`, `enc_el` | 1 | encoder sense; 0 disables the encoder |
| `imu_el`, `imu_el_dir`, `imu_el_zero` | 1, 1, 0 | boom IMU referencing |

### Error bits (`GE`, `XS err=`)

| Bit | Meaning | Action |
|---|---|---|
| 1 | AZ not referenced | `HOME`, sun alignment or `XCAL AZ=` |
| 2 | EL not referenced | check the boom IMU (J8), or `XCAL EL=0` with the boom level |
| 4 | TMC UART not answering | check the module pinout, JP1/JP2 and the power |
| 8 | encoder missing or magnet not detected | check the gap (1–2 mm) and the cable |
| 16 | supply below 8.5 V | charge the battery |
| 32 | index magnet / slot not found during HOME | check the magnet polarity or the notch disc, sensor and gap |
| 64 | 48 V lost (LSR-2) | position was saved; restore power, then check the reference or `HOME` |

## Example session

```
> VE
VELSR-1 1.0.0
> XS
XS az=0.00 el=12.40 taz=0.00 tel=12.40 ... ref=0,1 err=1 vin=13.10 enc=1,1 ... tmc=1,1 imu_el=12.38 tilt=0.21,-0.10 gps=1,9,40.416800,-3.703800,652.0 ...
> HOME
> AZ EL
AZ0.0 EL12.4
> AZ180 EL45
> XP 395 30          (absolute: 35 deg after one full turn of the cable wrap)
```
