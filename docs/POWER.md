# Portable power

The LSR-CTL accepts **9–24 V** on the XT30 (J1) or the 5.5 × 2.1 mm jack (J2). Use only one at a time.

The input is protected by:
- a 2.5 A PTC fuse;
- a reverse-polarity P-MOSFET;
- a 24 V TVS diode.

From that rail:
- the motors run directly from VM;
- the on-board 5 V / 2 A buck converter feeds the Pi Zero 2 W and the Pico.

## Recommended sources

| Source | Wh (usable) | Runtime at 4 W average | Notes |
|---|---|---|---|
| **LiFePO4 12.8 V 6 Ah** (4S, with BMS) | ≈ 69 | ≈ 17 h | Best choice: flat 13 V, safe chemistry, −10 °C discharge. XT30 lead. |
| LiFePO4 12.8 V 12 Ah | ≈ 138 | ≈ 34 h | Also powers a 5 W HT or the FTX-1 Field charger |
| **USB-C PD power bank ≥ 20 000 mAh** with a **12 V PD trigger cable** | ≈ 63 | ≈ 15 h | The bank must support PD 12 V or 15 V at ≥ 1.5 A. A 20 V trigger also works. Avoid 28 V (EPR). |
| 3S Li-ion 18650 pack (11.1 V, 3.5 Ah) | ≈ 35 | ≈ 9 h | Needs a protected pack with a BMS |
| Car socket (13.8 V) | – | – | Through a 5.5 × 2.1 lead with an inline fuse |

The energy figures come from `calc/sizing.py` (see [SIZING](SIZING.md)):

| State | Power at 12 V |
|---|---|
| Tracking: both motors at 0.9 A run current | ≈ 7 W |
| Idle between passes: motors holding at 35 % | ≈ 2.8 W |
| Pi Zero 2 W (Wi-Fi AP) + Pico + GPS | ≈ 1.7 W |
| **Average with 30 % of the time tracking** | **≈ 4 W** |

## Saving energy in the field

- Between sessions: `XE 0` frees the motors (about 1.8 W saved). The azimuth reference is cleared; the saved position or HOME restores it, and the elevation comes back from the IMU.
- Reduce `ihold` to 25 % in calm weather.
- Run the Pi without the hotspot and use the phone's own hotspot: about 0.3 W saved.

## Wiring and safety

- **XT30 polarity:** the flat side is negative. The board survives reversed polarity, but the battery lead must be fused **at the battery** (5 A blade fuse).
- Keep the motor cables away from the antenna coax. Each motor is driven by a chopper at about 40 kHz; the TMC2209 StealthChop is quiet, but long unshielded leads radiate.
  - Twist each coil pair.
  - Add a clip-on ferrite (mix 31) on each motor cable at the e-box.
- **FTX-1 and other radios:** power them from their own battery, or from the same LiFePO4 through a separate fused lead.
  - Do **not** take radio power from the LSR-CTL board.
  - Connect the grounds through the coax and USB only, to avoid ground loops.
- **Below about 0 °C:** LiFePO4 must not be **charged**. Discharge is fine down to −20 °C.
