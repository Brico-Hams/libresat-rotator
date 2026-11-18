# BricoHams · LibreSat LSR-2: assembly guide

Authors: Anatol EA5KAO, Diego EA5JEF, Pedro Roca Molina.

> **Default design:** the SARCTrac Mk4 replica (SARCNET FreeCAD files, MIT, `third_party/sarctrac-mk4`, [LSR2_MK4](LSR2_MK4.md)). Part A below is its assembly order; part B (from "Optional cast/CNC variant") describes the optional cast/CNC variant (`LSR2_DESIGN=cast`). The fastener, torque, cabling and corrosion rules apply to both.

Parts and prices: [BOM_LSR2](BOM_LSR2.md). Design and checks: [ARCHITECTURE](ARCHITECTURE.md), [LSR2_SIZING](LSR2_SIZING.md), [LSR2_MATERIALS](LSR2_MATERIALS.md). Every torque, fit and catalogue value below is **VERIFY** against your real parts. Drawings of the Mk4 parts and assemblies (SARCNET PDFs): [third_party/sarctrac-mk4/FreeCAD/Drawings/](../third_party/sarctrac-mk4/FreeCAD/Drawings/); wiring: [drawings/LSR2_wiring.svg](drawings/LSR2_wiring.svg); acceptance: [LSR2_ACCEPTANCE](LSR2_ACCEPTANCE.md); what is still open: [OPEN_ITEMS](OPEN_ITEMS.md).

![LSR-2 Mk4 exploded view, rendered](img/lsr2_exploded_real.png)

*Render, not a photo, of the Mk4 replica. Balloon numbers = BOM "Pos" column ([BOM_LSR2](BOM_LSR2.md)); editable model `cad/lsr2/LSR2_assembly.FCStd`.*

## Part A. Mk4 assembly order (default)

Follow the three SARCNET assembly drawings: [Thrust Bearing Assembly](../third_party/sarctrac-mk4/FreeCAD/Drawings/Thrust%20Bearing%20Assembly.pdf), [Saddle Assembly](../third_party/sarctrac-mk4/FreeCAD/Drawings/Saddle%20Assembly.pdf) and [Rotator Assembly](../third_party/sarctrac-mk4/FreeCAD/Drawings/Rotator%20Assembly.pdf). Use Tef-Gel on all stainless threads and aluminium–steel joints. Datums and fits: [LSR2_TOLERANCES](LSR2_TOLERANCES.md); first-article check: [LSR2_INSPECTION](LSR2_INSPECTION.md); tests after assembly: [LSR2_TEST_PLAN](LSR2_TEST_PLAN.md).

1. **Check the parts** against [LSR2_INSPECTION](LSR2_INSPECTION.md): laser-cut 2 mm parts ±0.1 mm, CNC [Plate](../third_party/sarctrac-mk4/FreeCAD/Drawings/Plate.pdf) (gearbox spigot bores and bearing seats), [Angle](../third_party/sarctrac-mk4/FreeCAD/Drawings/Angle.pdf), [Bracket](../third_party/sarctrac-mk4/FreeCAD/Drawings/Bracket.pdf), [Platform](../third_party/sarctrac-mk4/FreeCAD/Drawings/Platform.pdf) and [Bar](../third_party/sarctrac-mk4/FreeCAD/Drawings/Bar.pdf).
2. **Thrust bearing assembly:** stack the 4 × M30×56×3 washers, the 51206 races and cage on the stainless azimuth hub, as in the Thrust Bearing Assembly drawing; grease, and fit the PVC coupler as the seal. Check that the stack turns freely with no axial play.
3. **Rotator assembly:** bolt the two NMRV30-G50-D11 gearboxes to the 10 mm plate (8 × M8×40 with washers and nyloc), fit the 23HS32-4004S motors with the 11 → 8 mm adaptors and [motor gaskets](../third_party/sarctrac-mk4/FreeCAD/Drawings/Motor%20Gasket.pdf); fit the AZ hub with its thrust stack on the AZ gearbox output; mount the [end stops](../third_party/sarctrac-mk4/FreeCAD/Drawings/End%20Stop.pdf), the magnet and the NJK-5002C Hall switches.
4. **Saddle assembly:** assemble the saddle plates ([left](../third_party/sarctrac-mk4/FreeCAD/Drawings/Saddle%20Plate%20Left.pdf), [right](../third_party/sarctrac-mk4/FreeCAD/Drawings/Saddle%20Plate%20Right.pdf), [front](../third_party/sarctrac-mk4/FreeCAD/Drawings/Saddle%20Plate%20Front.pdf)) with the platform and bar, the 2 × 40 mm U-bolts for the mast and the EL hub; then the 25 mm SHS lift arms.
5. **Electronics:** mount the Deltron 483-0100 housing and the laser-cut [enclosure](../third_party/sarctrac-mk4/FreeCAD/Drawings/Enclosure%20Front.pdf) (with bottom and top), the DM542T drivers, S-400-48 wiring (PSU indoors), XL7015 modules, controller and cable gland; see [ELECTRONICS](ELECTRONICS.md). Neoprene gasket under the cover.
6. **Cover:** fit the 16 mm [corner blocks](../third_party/sarctrac-mk4/FreeCAD/Drawings/Cover%20Corner%20Block.pdf) and the six 2 mm cover panels ([top](../third_party/sarctrac-mk4/FreeCAD/Drawings/Cover%20Top.pdf), [bottom](../third_party/sarctrac-mk4/FreeCAD/Drawings/Cover%20Bottom.pdf), [front](../third_party/sarctrac-mk4/FreeCAD/Drawings/Cover%20Front.pdf), [back](../third_party/sarctrac-mk4/FreeCAD/Drawings/Cover%20Back.pdf), [left](../third_party/sarctrac-mk4/FreeCAD/Drawings/Cover%20Left.pdf), [right](../third_party/sarctrac-mk4/FreeCAD/Drawings/Cover%20Right.pdf)).
7. **Hook-up and first power-up:** DM542T current for 4.0 A and **400 microsteps/rev** (666.7 steps/s at 12°/s on the 50:1 gearbox); free motion through ±5° on each axis, direction check, end stops, index; then calibrate (section 9b) and run [LSR2_TEST_PLAN](LSR2_TEST_PLAN.md).

The tightening torques of section 2 apply to the M5/M8/M10 bolts here too.

## Part B. Optional cast/CNC variant

The sections below describe the optional cast/CNC variant (`LSR2_DESIGN=cast`: aluminium open-box body, NMRV030 80:1). Frame: origin at the centre of the body bottom mounting face, AZ = Z (vertical), EL axis horizontal along Y at z = 268 mm, boresight X. Use A4 fasteners and Tef-Gel on every thread. Every value below is **VERIFY** against the real parts.

## 0. Gate: measure the real NMRV030 (MEASURE)

1. Caliper both gearboxes: output face, hollow bore Ø14 H7, key, centre height, flange pitch, motor flange (0.02 mm).
2. Edit `NMRV030_GEO` in `cad/lsr2/params.py`, run `make lsr2` and check that self-tests and the interference check pass. Do not order metal before this.

## 1. Parts in hand (Piezas)

Route A: PLA patterns from `cast/lsr2/` to the foundry, then machining per the tolerance table. Route B: blanks from `cnc/lsr2/` (slab stack, bolt and dowel, then line-bore). The first article goes through [LSR2_INSPECTION](LSR2_INSPECTION.md). Bought parts are numbered as in the BOM.

## 2. Fasteners and tightening torques (Pares de apriete)

Class 8.8 (A4-80 in the field: use 70 % of the value, VERIFY), K = 0.15 lubricated, preload 0.7·Rp·As, from the simplified VDI 2230 table of [LSR2_SIZING](LSR2_SIZING.md):

| Bolt | Preload (N) | Torque (N·m) | Used on |
|---|---|---|---|
| M5 | 6362 | 4.8 | lid, motors |
| M6 | 9005 | 8.1 | gearbox flanges, bearing caps |
| M8 | 16397 | 19.7 | clamp blocks, saddle |
| M10 | 25984 | 39 | mast bracket U-bolts (preload 5000 N per leg is enough: stop at 12 N·m, VERIFY) |
| M12 | 37766 | 68 | not used |

Boom clamp legs: 3000 N preload each. Re-torque after the first week.

## 3. Installation order

1. Mast bracket on the mast: slide the AZ shaft into its pocket and pin it (cross pin Ø6). Clamp with the U-bolts.
2. Bearings and seals (section 4); fit the 51206 + shim + circlip on the shaft and lower the body (lid removed) onto it. The lower and upper 6206 and the circlip go in from the pillar ends before the shelf plate.
3. AZ gearbox bolted to the shelf plate from below (ball-end key, 26 mm of air), motor on its flange, key on the Ø14 stub (section 5).
4. EL gearbox on the +y wall pad from outside (4 × M6, PCD 65), motor on it. Both motors lie on the same side.
5. 6004 bearings and seals in the wall bosses, EL shaft through (Ø14 end into the gearbox hub, with key), sleeve on the +y side.
6. Yoke arms on the Ø20 shaft ends (keys), saddle, boom and clamp blocks, lift arms, antennas and counterweights (section 6).
7. Drivers on the −y wall with thermal pads, harness through the bottom glands, gasket, lid (M5, torque above).

## 4. Bearing and seal fitting

1. Check the seats first against the tolerance table (T-numbers in [LSR2_TOLERANCES](LSR2_TOLERANCES.md)): 6206 and 6004 seats J7, shafts j6/g6 per the bearing maker.
2. Press on the ring that carries the interference only (arbor press, outer ring into the housing, inner ring onto the shaft); never through the balls. Warm the housing to 80 °C only if the press is not available.
3. The 51206: tight ring (shaft washer) on the shaft; preload with the shim (a second shim if axial play appears).
4. Lip seals and V-rings: grease the lip, push square, shaft surface Ra ≤ 0.8 µm. Gasket cord in the groove (2 mm deep, 3 mm wide), splice at the lid middle.

## 5. Gearbox coupling

Gearboxes only transmit torque: the external loads go through the dedicated bearings. Slide the gearbox hollow output on the keyed shaft with Tef-Gel (push fit, no rocking), bolt the flange with the torque above, and fit the motor with M5 screws. Do not force the shaft against the worm wheel; the shaft must be free axially in the gearbox hub (the bearings locate it).

## 5b. Own gearbox LSR-WG30 assembly (only with `GEARBOX_SOURCE = 'lsr_wg30'`)

1. Machine both halves (seats, bores, joint faces, taps, dowel holes, see the cast spec) and deburr; check the dowel holes and the bearing seats with the inspection sheet. Clean all cast cavities of sand.
2. Press the 2 × 61905 (DATASHEET 25×42×9, VERIFY) onto the wheel carrier seats with the wheel on the carrier (CuSn12 rim, keyed or pressed, VERIFY), and the 2 × 6003 on the worm; circlip plus a shim set (0.1 and 0.2 mm) locate the worm axially.
3. Lay the lower half on the bench, fit the output seal (lip towards the oil), place the wheel assembly and then the worm; check the mesh pattern with marking blue and shim the worm axially until the backlash is 0.05-0.15 mm at the output (dial gauge on a lever arm, MEASURE).
4. Gasket: liquid gasket (anaerobic or RTV, VERIFY) as a thin bead around the joint groove, or a Ø2 O-ring cord in it. Fit the 2 dowels, close the upper half, tighten the 4 M5 screws in a cross pattern to 5 N·m (PARAMETRIC) and re-check the backlash and the free rotation by hand (no tight spot).
5. Fill with about 40 g of NLGI 00 grease (VERIFY) through the open upper half before closing, or through the worm tunnel; fit the input seal and the NEMA23 motor.
6. Run-in: 10 minutes at low speed both directions, then check the housing temperature (hand-warm) and re-tighten the screws.

## 6. Yoke, saddle, boom, counterweights and balance

1. Yoke arms on the shaft ends with keys and axial retainers; saddle bolted between the arms.
2. Boom (parallel to the EL axis) in the saddle and clamp blocks, torque 8.1 N·m, 3000 N per leg.
3. Lift arms and antennas at the boom ends; counterweights slide on the Ø10 rods.
4. Balance with the drivers off: set the boom horizontal, move the counterweights until the boom does not move at EL 0, 45 and 90°. The target residual torque is ≤ 1.5 N·m (MEASURE with the force gauge). Lock the counterweights and mark the position.

## 7. Cabling

1. Harness through the M16 gland, coax through the M12 gland; a drip loop (the cable goes down below the gland and then rises) outside each gland.
2. Bend radius ≥ 10 × OD; LMR-240 static minimum 25.4 mm. Do not tension the wrap on the AZ axis (±360° of travel); EL coax in a loose coil.
3. Strain relief at the gland; cable ties on the boom every 0.3 m; ferrites on the motor cables.
4. Check the travel by hand through the full envelope before powering up ([LSR2_TEST_PLAN](LSR2_TEST_PLAN.md) S1-5).

## 8. Corrosion protection

1. Tef-Gel (Duralac as an alternative) on every aluminium-steel joint and stainless thread.
2. A4 fasteners only; no zinc steel against aluminium outdoors; keep the drain Ø4 clear and facing down.
3. Paint or anodise is optional; mask bearing seats, threads and the gasket groove.

## 9. Electronics hook-up and first power-up

1. Wiring: [ELECTRONICS](ELECTRONICS.md), section "LSR-2 external drivers" (drivers on the inner wall, glands, optional Wi-Fi bulkhead antenna).
2. DM542T current to the motor rating (23HS32-4004S: 4.0 A; cast variant 57BYG250H-8 3 A, VERIFY) and **400 microsteps/rev**; 666.7 steps/s at 12°/s on the 50:1 gearbox (1066.7 with 80:1 in the cast variant).
3. Firmware: [FIRMWARE](FIRMWARE.md) (`LSR_DRIVER=EXT_STEPDIR`, `lsr2` profile, EasyComm II 9600 8N1).
4. First power-up without the antenna: free motion through ±5° on each axis, check the direction, then the one-off calibration below.

## 9b. One-off calibration (Mk5 style)

Calibrate once, with the antenna off:

1. **Index hardware.** AZ disc inside the pillar on the Ø14 stub (ASA, 3 mm), AZ sensor on the shelf bracket; EL disc position is an open decision (see ELECTRONICS). Wire the sensors to J9 (AZ) and J10 (EL). VERIFY: gap 5 mm, disc 3 mm.
2. **North / horizon reference.** Put the head so that the AZ notch edge is at true north (compass + declination; the notch edge is wire 360°), then `XCAL HOMEAZ` stores it. Put the boom level (spirit level on the tube): `XCAL EL=0`, then `XCAL HOMEEL` stores the horizon index.
3. **Backlash to flash.** Send `XCAL BACKLASH`: both axes search their index from both sides and the measured backlash is stored as `backlash_az` / `backlash_el`; `XW` writes it. Check with a dial gauge at 1 m radius that the residual is < 0.1° (VERIFY). Repeat after the first week of use (the worm wears in).
4. **Check.** `HOME`, then command north and the horizon and verify with the compass and the level. Normal start-up after that is `HOME` or just power on (position restored from flash).
5. **Power loss test.** Switch off the 48 V with the head at a known angle: after power on `XS` must show the saved position and error 64 cleared after `XE 1` (VERIFY the capacitor hold-up with a scope on the 5 V rail).

**Bearing and seal inspection.** Every 6 months for the first year, then every 2 years (VERIFY): open the lid, check the 51206, 6206, 6004 and the seals for water and rust, re-grease with a water-resistant grease and replace seals if cracked. Adjust the preload with the second shim if axial play appears.

**Compatible trackers** (EasyComm II, 9600 8N1): PstRotator, Gpredict, SatPC32 and Orbitron, plus our `lsr` software and Hamlib `rotctld -m 202`.

## 10. Acceptance

Progressive acceptance (unloaded, test loads, target antenna) with pass criteria and a results table: [LSR2_TEST_PLAN](LSR2_TEST_PLAN.md). Risks: [LSR2_RISKS](LSR2_RISKS.md). Safety, from [LSR2_SIZING](LSR2_SIZING.md): **proof-load the first mast bracket and the first boom clamp** before fitting the antenna (clamp-arm bending is not calculated). Wind limits are tracking 60 km/h and parked 100 km/h for a crossed Yagi pair; park the antenna in strong wind. Work with the power supply off and keep fingers out of the head while the drivers are enabled.
