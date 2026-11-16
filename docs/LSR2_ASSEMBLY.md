# BricoHams · LibreSat LSR-2: assembly guide

Authors: Anatol EA5KAO, Diego EA5JEF, Pedro Roca Molina.

Parts and prices: [BOM_LSR2](BOM_LSR2.md). Design and checks: [ARCHITECTURE](ARCHITECTURE.md), [LSR2_SIZING](LSR2_SIZING.md), [LSR2_MATERIALS](LSR2_MATERIALS.md). Every torque, fit and catalogue value below is **VERIFY** against your real parts.

![LSR-2 assembly](img/lsr2_assembly.png)

![LSR-2 exploded view](img/lsr2_exploded.png)

![LSR-2 cast parts and their patterns](img/lsr2_patterns.png)

Axes: AZ is Z through the origin, the top face of `base` is z = 0, EL runs along Y. Use A4 fasteners and put Tef-Gel on every thread (step 7).

## 0. Measure the real NMRV030 (VERIFY gate)

1. Measure both gearboxes with a caliper: output face, hollow bore (Ø14 H7), key, centre height, flange pitch, motor flange (tool: caliper, 0.02 mm).
2. Edit `NMRV030_GEO` and `GEARBOX` in `cad/lsr2/params.py`, run `make lsr2` (self-tests and the interference check must pass), commit the new STEP/DXF/STL.
3. Do not order metal before this passes.

## 1. Print the PLA 1:1 prototype and fit-test

1. Print the plates from `stl/lsr2/` (PLA, 3 walls, 20 % infill; about 1.2 kg).
2. Check: gearbox and NEMA23 clearance to `base`, `spacer`, `spacer_el` (the motor is 56.4 wide, the gearbox 56); 4 gearbox bolt patterns; Ø32 bore for the 6201; the 6 × Ø6.6 PCD 110 holes; the M20 gland hole; tapped-edge hole positions line up between plates (use M6 screws in the printed holes).
3. Tool: caliper, real gearboxes and bearings. Fix `params.py`, repeat step 0 if anything is off.

## 2. Order the CNC plates

1. Files: `cnc/lsr2/{base,spacer,spacer_el,side_a,side_b,top}.dxf` (notes in the DXF text) and `.step`.
2. Material: 6061-T6 or 5083, 8 mm (`top` 6 mm). Ask for cut-to-size blanks: this is cheaper than full sheets (76 % waste, [LSR2_MATERIALS](LSR2_MATERIALS.md)).
3. Tolerances: general ±0.2 mm; **6201 bore Ø32 H7 in `side_b` finished on a mill** (router tolerance is not enough); gearbox bolt holes ±0.1 mm.
4. Edge taps M6 × 15 deep (top and bottom of `side_a` and `side_b`, x = ±60, ±150): drill Ø5 by hand and tap by hand (tap M6, cutting oil), perpendicular to the edge.
5. Deburr all edges and holes (file, deburring tool). Check the bore with a Ø32 go gauge or the 6201.

## 3. Casting

1. Print the patterns and the core box in PLA from `stl/lsr2/`: `az_housing_pattern`, `az_housing_corebox`/`az_housing_cores`, `mast_clamp_pattern`, `el_hub_pattern` (STEP in `cast/lsr2/`). Sand and seal the surfaces; the pattern maker adds the 2° draft on prismatic parts and 3 mm fillets.
2. Send to the foundry (A356-T6, shrink 1.013 VERIFY) with the parting notes:
   - `az_housing`: parting z = −8 (flange face), one drag half; core A on the flange face (cope), core B through the lip hole (drag);
   - `mast_clamp`: parting z = −175 (boss top), drag only, bore cast solid;
   - `el_hub`: parting through the EL axis, two halves with 2 dowels, bore cast solid; one pattern casts both hubs.
3. Machining list after casting (2.5 mm allowance): `az_housing`: bearing seats Ø62 H7 (6206) and the 51206 seat, flange face, 6 × M6 × 12 taps on PCD 110 (drill Ø5); `mast_clamp`: bore Ø30 H7 and V groove, Ø6 cross-pin hole (reamed through the shaft at step 5), U-bolt ear faces; `el_hub_a/b`: bore Ø14 H7 (key 5) and Ø12 H7 (key 4), pinch slit, boom-clamp faces and pinch screw holes.
4. Proof-load the first mast clamp before relying on it (step 9).

## 4. Turn the shafts

Material stainless 1.4404, bars Ø33 × 299 (AZ) and Ø17 × 262 (EL). Tool: lathe, gun drill for the AZ bore.

| Shaft | From (mm) | To (mm) | Ø (mm) |
|---|---|---|---|
| az_shaft | −225 | 1 | 30 |
| az_shaft | 1 | 64 | 14 h7 |
| el_shaft | −126 | −63 | 12 |
| el_shaft | −63 | 126 | 14 h7 |

1. `az_shaft`: hollow, Ø16 bore from the bottom end to z = −1 (the Ø14 step stays solid, VERIFY gun drilling with the machinist); Ø6 radial cable exit at z = −4; Ø30 bearing seats (bearing fit k6-j6, VERIFY); Ø6 cross-pin hole in the bottom Ø30.
2. Keyways: Ø14 top 5 × 5, slot 40 long (AZ); `el_shaft` key 5 × 5 on the Ø14 and 4 × 4 on the Ø12 (VERIFY against the hubs). Test the key fit with the real keys and gearbox bore (push fit, no rocking).
3. Deburr, polish the seal surface for the V-ring, cut the circlip groove for the DIN 471 Ø30 ring (position from `params.py`, VERIFY).

## 5. AZ unit

1. Press the two 6206-2RS into `az_housing` (arbor press, push on the outer ring only; check the Ø62 H7 seats first).
2. Fit the 51206 (bore ring on the shaft washer side: the tight ring is the shaft washer) and the V-ring on the shaft; fit the DIN 471 circlip and the 3 mm ring below the shaft washer.
3. Slide the shaft through the housing; no free play along the axis (check by hand).
4. Fit the mast clamp on the shaft bottom, drive the Ø6 cross pin (light hammer, pin punch), then mount the housing under `base` with 6 × M6 × 20 (torque 8 N·m, VERIFY, Tef-Gel).
5. Pull the cable through the hollow shaft: bottom open end, up the Ø16 bore, out of the Ø6 hole at z = −4 above the upper bearing; leave a service loop (the head only twists ±360°, no wrap round the mast).
6. Clamp the mast clamp on the mast (40-60 mm) with the 2 M8 U-bolts (torque 12 N·m, VERIFY; do not exceed the nut-seat rating; A4-80 or 8.8).

## 6. Head frame

1. `base` on the bench, top face up. Fit `spacer`, the AZ gearbox (key 5 × 5, shaft goes into the hollow output) and 4 × M6 × 25 through the spacer (8 N·m); fit the NEMA23 (4 × M5, 4 N·m, VERIFY).
2. Stand `side_a` and `side_b` on the base: 8 × M6 × 20 from below into the tapped edges (8 N·m, thread lock not needed with Tef-Gel).
3. Mount the EL gearbox on `side_a` with `spacer_el` (4 × M6 × 20, VERIFY length), the motor pointing −X (the AZ motor +X: balances the head).
4. Press the 6201-2RS into the `side_b` Ø32 bore (arbor press, outer ring).
5. Slide `el_shaft` through hub A, `side_a`, the gearbox hollow output (key 5) and the 6201 (shoulder at y = −63 against the 6201), then hub B (Ø12, key 4).
6. Fit `top` with 8 × M6 × 16 into the side plate top edges.
7. Hub pinch screws 2 × M6 × 30 (6 N·m, VERIFY); clamp the Yagi booms in the hubs/boom U-bolts (4 × M6, 6 N·m).

## 7. Corrosion protection

1. Tef-Gel or Duralac on every aluminium-steel joint: housing/shaft, screws in plate taps, U-bolts on the clamp, hub on shaft.
2. A4 fasteners only (A4-80 for the U-bolts); no zinc steel against aluminium outdoors.
3. Keep the drain hole in `az_housing` clear and facing down; V-ring and 6206-2RS prevent dust and water ingress, check them once a year.
4. Paint or anodise is optional; mask bearing seats and threads.

## 8. Electronics hook-up and first power-up

1. Wiring: refer to [ELECTRONICS](ELECTRONICS.md), section "LSR-2 external drivers": LSR-CTL step/dir/enable to 2 × DM542, DM542 to NEMA23, AS5600 encoders to the board, 24-48 V supply with fuse, cable gland M20 in `side_b`.
2. Set DM542 current to the motor rating (NEMA23 2.8 N·m: about 3 A, VERIFY) and microstepping 1/8 (4267 steps/s at 12°/s).
3. Firmware: see [FIRMWARE](FIRMWARE.md) (`LSR_DRIVER=EXT_STEPDIR`, `lsr2` profile, in progress).
4. First power-up without the antenna: free motion through ±5° on each axis, check direction, then set the encoder zero (north for AZ, horizon for EL) and run the calibration from the web UI.

## 9. Acceptance tests

| Test | How | Pass (VERIFY) |
|---|---|---|
| Backlash | dial gauge at 1 m radius, push by hand both ways | record the value; compensate in the firmware |
| Speed | command 360° and time it | 12°/s without missed steps |
| Holding | motor power off / on, push the boom | position held, no creep (worm self-locks) |
| Encoder zero | go to 0° and 90°, compare with a compass and level | error ≤ 1° |
| Wind-loaded hold | antenna on, wind or a pull of the survival moment in a safe test | no slip of the mast clamp or the shaft |

Safety, from [LSR2_SIZING](LSR2_SIZING.md): **proof-load the first mast clamp** before putting the antenna on it (the preload bending of the clamp arms is not calculated). Wind limits are tracking 60 km/h and parked 100 km/h for a crossed Yagi pair; park the antenna in strong wind. Work with the power supply off and keep fingers out of the head while the drivers are enabled.
