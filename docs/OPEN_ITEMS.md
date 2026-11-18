# Open items (Puntos abiertos)

> **Update (phase 12):** the default LSR-2 design is now the SARCNET SARCTrac Mk4 replica (`LSR2_DESIGN=mk4`, files under the MIT licence in `third_party/sarctrac-mk4`, see [LSR2_MK4](LSR2_MK4.md)); the cast/CNC design is the optional variant (`LSR2_DESIGN=cast`). Items O1-O2 and the casting items below apply to the cast variant (the NMRV30-G50 of the Mk4 needs the same caliper check). Mk4 open items are in the section "Mk4 replica (phase 12)" at the end.

Authors: Anatol EA5KAO, Diego EA5JEF, Pedro Roca Molina (BricoHams). **One place** for everything that cannot be closed from the repository and needs the real world: a caliper, a quote, a test, a compile on the target. Everything else (calculations, geometry, documents) is generated or written and is checked by `make verify`. Tags follow [LSR2_INPUTS](LSR2_INPUTS.md): MEASURE = needs an instrument, QUOTE = needs a supplier price or process agreement, TEST = needs a bench or field test, DECIDE = owner decision.

When an item is closed, put the measured value in `cad/lsr2/inputs.py` or `params.py`, re-run `make calc lsr2`, and delete the row here with the date.

## Hardware measurements and parts

| ID | Item | Tag | Owner action | How to close |
|---|---|---|---|---|
| O1 | NMRV030 input bore Ø11 versus the motor shaft Ø8 (flat) | MEASURE | caliper both purchased parts | enter `adapter_od`, `adapter_id`, `adapter_len` in `inputs.py`; keep the bushing or buy a supplier Ø8 input kit ([LSR2_SIZING](LSR2_SIZING.md) §12) |
| O2 | NMRV030 output face: pilot Ø, boss, PCD 65 holes, hub length, centre height, hollow bore Ø14 H7, key | MEASURE | caliper, bore gauge | update `params.NMRV030_GEO`; re-run `make lsr2`; fits in [LSR2_TOLERANCES](LSR2_TOLERANCES.md) |
| O3 | NMRV030 torsional stiffness, backlash, rating and radial load (supplier sheet), peak factor | MEASURE / QUOTE | ask the seller for the datasheet; bench `XCAL BACKLASH` | `params.GEARBOX`, `inputs.gb_stiff`, `gb_backlash`; SIZING §10 |
| O4 | Motor winding resistance and torque-speed curve on the DM542T at 48 V | MEASURE / TEST | multimeter; bench curve | `inputs.motor_r`, `motor_usable`; SIZING §5 and §15 |
| O5 | Real supply current at 12°/s, both axes (`supply_k`) and flash-save time (`save_ms`) | TEST | clamp meter on the 48 V rail (S1-8); scope on PWRFAIL | `inputs.supply_k`, `save_ms`; SIZING §15 hold-up must stay ≥ 2 x |
| O6 | Antenna masses, CG, projected areas, boom stations | MEASURE | weigh and balance the real Yagis | `inputs.ant*` rows; SIZING all sections |
| O7 | Mast: diameter, wall, material, free height, guying | MEASURE | caliper, supplier | `inputs.mast_*`; SIZING §8 |
| O8 | Cable types and ODs (7-core harness, LMR-240), gland ranges | MEASURE | buy the cables, caliper | `cad/lsr2/cables.py` `GLAND_CABLES`; SIZING §16 |
| O9 | One coax through a boom-centre diplexer versus two coax lines | DECIDE | choose; two lines need a second gland and a CAD change | `cables.py` and `body.GLANDS`; ELECTRONICS |
| O10 | Wi-Fi module and sealed bulkhead antenna, or wired link | DECIDE | choose | ELECTRONICS "Optional Wi-Fi antenna bulkhead" |
| O11 | EL index disc position and sensor part (EE-SX1103 class gap) | DECIDE / MEASURE | choose, check the datasheet | `params.INDEX`; ELECTRONICS |

## Manufacturing and quotes

| ID | Item | Tag | Owner action | How to close |
|---|---|---|---|---|
| O12 | Foundry: alloy and temper (A356-T6), shrinkage, draft, minimum wall and fillet, riser and chill layout, price | QUOTE | send [LSR2_ROUTE_A_CASTING](LSR2_ROUTE_A_CASTING.md) with the preform STEP | `params.CAST`, `CAST_PART`; hot-spot rows in the route A report |
| O13 | Casting yield and proof-load of the first casting (clamp seat, boom clamp, saddle) | TEST | proof-load the first casting to 1.5 x the survival load; X-ray or dye penetrant | record in [LSR2_INSPECTION](LSR2_INSPECTION.md); update `inputs.a356_yield` |
| O14 | CNC shop: machine travel, tooling, rate, 6082-T6 / 6061-T6 stock price | QUOTE | send [LSR2_ROUTE_B_CNC](LSR2_ROUTE_B_CNC.md) | `params.CNC`, `inputs.cnc_travel` |
| O15 | Circlip grooves (DIN 471 Ø30 on the shafts, DIN 472 in the bearing seats) and the 51206 housing-washer recess | MEASURE | caliper the bought circlips and washers; groove widths and depths are cut by the shop to the DIN 471/472 table of the actual ring | machining list in [LSR2_TOLERANCES](LSR2_TOLERANCES.md); first-article sheet |
| O16 | Printer bed (256 mm assumed) | MEASURE | check the real printer | `inputs.print_volume`; pattern split in route A |
| O17 | Foundry route for the consumable (lost-PLA) variant | QUOTE | ask the foundry | `params.CAST_LOST` (not sized) |
| O18 | Fillets on cast parts: radius `min_fillet` is checked in the self-test and listed on the drawings; foundry may ask for a larger one | QUOTE | agree with the foundry | `params.CAST['min_fillet']` |

## Tests

| ID | Item | Tag | Owner action | How to close |
|---|---|---|---|---|
| O19 | Worm holds under vibrating wind with the drive off (no brake) | TEST | S2-2 drift test, then a shake test | if it creeps, add a spring-applied brake ([LSR2_RISKS](LSR2_RISKS.md)) |
| O20 | Sealing target (spray test) and condensation control | TEST | S2-4; no IP rating is claimed before it | [LSR2_TEST_PLAN](LSR2_TEST_PLAN.md) results table |
| O21 | VHF/UHF noise of motors and drivers | TEST | S2-5 | ferrites, chopping frequency |
| O22 | Pointing residual < 0.1° with the target antenna | TEST | S3-1 | [LSR2_ACCEPTANCE](LSR2_ACCEPTANCE.md) section 3 |
| O23 | Mast clamp proof load of the real part | TEST | S2-3 and the first-casting proof load (O13) | SIZING §8 already checks the preload and leg stress analytically |

## Software and firmware

| ID | Item | Tag | Owner action | How to close |
|---|---|---|---|---|
| O24 | Firmware compile on the target (Pico SDK 2.x, ARM GCC) with `LSR_DRIVER=EXT_STEPDIR` | TEST | `make -C firmware` on a machine with the toolchain, flash, run `XR` | [FIRMWARE](FIRMWARE.md) |
| O25 | Official NOAA WMM2025.COF coefficients for the magnetic declination | MEASURE | download the file from NOAA and replace the table | [CALIBRATION](CALIBRATION.md) "Magnetic declination" |
| O26 | LSR-1 items: TMC2209 module pinout, AP63205 pinout, FTX-1 `FB` and CAT tone syntax, OpenGD77 keps upload | TEST | verify with the parts | [ELECTRONICS](ELECTRONICS.md), [SOFTWARE](SOFTWARE.md) |
| O27 | `Limits.anti_windup` in the live tracker needs a one-line change in `software/lsr/tracker.py` | DECIDE | owner edits tracker.py | [FIRMWARE](FIRMWARE.md) |

## Mk4 replica (phase 12)

| ID | Item | Tag | Owner action | How to close |
|---|---|---|---|---|
| O30 | Regenerate sizing, inputs and BOM for the Mk4 default (the committed numbers were produced for the cast variant) | TEST | run `python calc/lsr2_sizing.py --check`, `python scripts/bom.py`, `make calc lsr2` | commit the regenerated `LSR2_SIZING.md`, `LSR2_INPUTS.md`, `BOM_LSR2.md`; flag every row below target |
| O31 | NMRV30-G50 output rating 13.0 N·m (10.4 N·m allowed) against the 60 km/h wind torque of the 1270 mm antennas | QUOTE | gearbox catalogue rating from the supplier | see the "Below target (drive)" paragraph of [LSR2_SIZING](LSR2_SIZING.md) |
| O32 | Worm starts and lead angle of the 50:1 unit (self-locking assumed 2.3°) | MEASURE | count the starts | `inputs.py` |
| O33 | Mk4 prices are estimates (EU hobby suppliers, 2026) | QUOTE | quotes for laser 2 mm, CNC 10 mm plate, SHS cut | `calc/lsr2_mk4_bom.py` |
| O34 | Firmware: NJK-5002C level shifting (12 V sensor, 3.3 V pin), end-stop wiring (NC in series with ENA), Wemos D1 Mini Pro WiFi link | TEST | bench test | [LSR2_MK4](LSR2_MK4.md), [LSR2_TEST_PLAN](LSR2_TEST_PLAN.md) |

## Decisions already taken (not open)

- **Design choice (phase 12).** LSR-2 is a replica of the SARCNET SARCTrac Mk4 (default, MIT files in `third_party/sarctrac-mk4`); the cast/CNC design stays optional (`LSR2_DESIGN=cast`).
- **Weather cover.** A separate printed ASA cover for the gearboxes and motors is **not designed**: in the Mk5-schematic architecture the motors and gearboxes are inside the gasketed aluminium body, whose lid, glands, breather and drain are the weather protection. A cover would only add mass. Revisit only if the spray test (O20) fails.
- **AZ cable path.** The AZ shaft is a solid Ø14 stub, so there is no bore fill check; the harness is wrapped round the mast bracket and goes through the M16 gland ([LSR2_SIZING](LSR2_SIZING.md) §16).
- **Mast clamp bending and EL joint tilt.** The old phase-6 `el_bracket` and `mast_clamp` casting no longer exist; the U-bolt preload, leg stress, slip and crush are computed in SIZING §8, and the EL load path is bearing-based (SIZING §7).
- **Other design decisions** are listed in the "Open decisions" section of [LSR2_INPUTS](LSR2_INPUTS.md).
