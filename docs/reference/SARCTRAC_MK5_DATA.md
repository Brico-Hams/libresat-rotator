# SARCTrac Mk5 — published technical data (reference for LSR-2)

Source: SARCNET, https://www.sarcnet.org/sarctrac-mk5.html (read 2026-11-16; the page is marked "under construction" and many items are TBD). Facts are paraphrased; SARCNET owns the design. No SARCNET CAD file or drawing geometry is used in this repo (their files carry no licence). Items flagged ⚠ are ambiguous or contradictory on the page.

## Specifications
| Item | Mk5 value |
|---|---|
| Range | AZ ±360°, EL −30…150° |
| Speed | 2 rpm = 12°/s, both axes |
| Torque | 1.7 kg·m (≈ 16.7 N·m) |
| Load | 128 kg radial (gearbox) ⚠ spec list says "130 kg.m" |
| Accuracy | better than ±0.1° |
| Mode | shortest path, configurable anti-windup (unwinds cables between passes) |
| Protocol | AMSAT EasyComm II with position feedback, 9600 baud 8N1; serial terminal (PuTTY) for manual control, debug, calibration, configuration, simulation |
| Link | dedicated Wi-Fi (rotator = access point + Telnet server; PC = USB Wi-Fi dongle with Telnet client), ~30 m ⚠ 2.4 GHz in specs, 2.4/5 GHz module and 5 GHz antenna elsewhere |
| Trackers tested | PstRotator, Gpredict, SatPC32, Orbitron |
| Payload | 1.8 m dish or a pair of large cross/circularly-polarised Yagis |

## Mechanics
- AZ shaft vertical, carries all weight; 51206 thrust bearing (smaller-bore ring on top) plus 4 × M30×56×3 stainless washers so axial load goes to the gearbox housing, not the gearbox bearings; shaft free to slide in its keyway; circlip left unloaded.
- Thrust bearing in a short PVC pipe sealed to the AZ gearbox housing with silicone, small gap at the bottom; inspect every few years.
- EL uses the same gearbox type.
- Output shafts: stainless M14 threaded rod, keyed with 5×8 mm roll pins, clamped onto the hollow gearbox shafts with nuts/washers.
- Saddle, shaft hubs and mast platform: hardware-store galvanised-iron angle brackets (value engineering, ~30 % cost saving vs Mk4 bespoke aluminium).
- Electronics in a laser-cut metal enclosure; six laser-cut cover panels.
- Garage fabrication: cut-off saw and drill press; Tef-Gel on practically every joint instead of grease.

## Drive
- Gearbox NMRV30, worm 80:1, through hollow output Ø14 keyed (double), input Ø11 keyed, 57×57 NEMA23 flange, max 1.7 kg·m, max radial 128 kg.
- Motor 57BYG250H-8 NEMA23, 112 mm, 2.8 N·m, 3.0 A, 1.8°, Ø8 shaft with flat.
- Drivers 2 × DM542 (20–50 V, ≤ 4.2 A, opto-isolated step/dir, ≥ 5 V logic → 3.3→5 V level converter, idle-current reduction, ≥ 400 microsteps/rev).
- 400 microsteps/rev × 80:1 at 2 rpm → 1066 steps/s (motor 160 rpm) ⚠ page also says 320 rpm.

## Electronics and power
- Controller Elecrow Pico W5 (Pico 2W compatible, 2.4/5 GHz Wi-Fi), U.FL connector added for an external antenna on an SMA bulkhead.
- 48 V DC supply S-400-48 indoors; XL7015 buck (5–80 V in) to 5 V for controller and photosensors; 5→3.3 V level converter; 48 V opto-isolated supply-detect circuit to save position on power loss; Veroboard assembly.

## Sensing and calibration
- Per axis: photo-interrupter disc with one index slot on the rotating shaft, photosensor on the stationary housing (2 photosensors). ⚠ another paragraph says Hall index switches were replaced by "end-stops and smarter software".
- One-off calibration script stores north/horizon reference and gearbox backlash in flash; on sudden power loss the controller stops and saves the reference offset.

## Software
- MicroPython on the microcontroller: "SARCTRAC Server" (AP, Telnet, command interpreter, position/speed controller); companion desktop programs SARCTRAC Earth / Space.
