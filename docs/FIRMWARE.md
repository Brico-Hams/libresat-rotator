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
make test                                        # 46 host unit checks (no hardware)
```

There are three ways to flash:

- **USB:** hold BOOTSEL while plugging in the Pico, then copy `lsr1.uf2` to the `RPI-RP2` drive. A running board can enter the bootloader with the `XB` command.
- **From the Pi Zero, in the field:** `software/scripts/flash_pico_from_pi.sh build/lsr1.elf`, through J14 SWD and openocd.
- **Debug probe:** any CMSIS-DAP probe on the SWD pads.

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
- UART0 at 115200 baud, for the Pi Zero on the header.

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
| `XC?` / `XC <key>` | List or read settings |
| `XC <key>=<value>` | Set a setting (saved automatically when idle; `XW` saves now) |
| `XCAL AZ=<deg>` / `XCAL EL=<deg>` | Declare the current position (sun alignment, level boom) |
| `XCAL ELIMU` | The boom IMU now reads the current elevation |
| `XCAL LEVEL` | The base IMU now reads 0/0 (the tripod is level) |
| `XCAL HOMEAZ` | Store the current azimuth as the index magnet azimuth |
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
| `home_az` | 0 | azimuth of the index magnet |
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
| 32 | index magnet not found during HOME | check the magnet polarity, sensor and gap |

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
