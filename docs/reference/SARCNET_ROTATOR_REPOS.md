# Community repositories reviewed for LSR-2 (2026-11-16)

Reviewed at the owner's request. Only ideas and published facts are used; any code we write is our own implementation, credited below. LibreSat firmware/software is GPL-3.0-or-later.

| Repository | What it is | Licence | Used for LSR-2 |
|---|---|---|---|
| [aleiei/Rotator7](https://github.com/aleiei/Rotator7) | Az/el rotator controller derived from the SARCNET MK1 Mini Rotator (ATmega328P, LSM303AGR magnetometer + accelerometer, RS-485 half-duplex with MAX485, Hamlib rotctld, SDRangel trackers) | GPL derivative of SARCNET MK1 (GPL, version not stated upstream) | Ideas: per-axis min/max magnetometer calibration (offset = (max+min)/2, scale = (max-min)/2), first-order low-pass filters on sensor (alpha ~0.02) and motor commands (alpha ~0.5), calibration stored in non-volatile memory with validity check and safe defaults, azimuth wind-up tracking by ±360 offsets, RS-485 link for long cable runs, calibration feedback (beeper) |
| [Nathan-Busse/SarcnetMiniSatelliteTrackerMK1](https://github.com/Nathan-Busse/SarcnetMiniSatelliteTrackerMK1) | Build and calibration guide for the SARCNET Mini Satellite Tracker Mk1 (GY-511 / LSM303DLHC) | none stated | Ideas: 12-point / full-sphere magnetometer calibration, hard-iron vs soft-iron explanation, ellipsoid fit back to a sphere, magnetic declination from the NOAA calculator for true north |
| [vinuni-vishc/sarcnet](https://github.com/vinuni-vishc/sarcnet) | Deep-learning model "SarcNet" (medical imaging) | none | Not related to rotators: not used |
| [vinuni-vishc/d-sarcnet](https://github.com/vinuni-vishc/d-sarcnet) | Deep-learning model "D-SarcNet" | none | Not related: not used |
| [PrathamMalviya1103/SarcNet-Data-Mining-Project](https://github.com/PrathamMalviya1103/SarcNet-Data-Mining-Project) | Sarcasm-detection notebooks | none | Not related: not used |
| [mikaelpfonseca/ais_on_rasp](https://github.com/mikaelpfonseca/ais_on_rasp) | Script to install a SARCNET-based AIS ship receiver on a Raspberry Pi | none | Not a rotator: not used (possible future station add-on) |

The existing BricoHams code in Brico-Hams/antenaSatCommrotor `rotor/sensors.py` already implements a compass calibration and a tilt-compensated true heading; LSR-2 reuses the same approach (same authors).
