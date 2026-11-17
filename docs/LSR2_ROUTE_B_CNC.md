# BricoHams · LibreSat LSR-2: Ruta B, mecanizado CNC de 3 ejes (Route B, 3-axis CNC)

<!-- palette: blue #12263f, orange #e8871e -->
Authors: Anatol EA5KAO, Diego EA5JEF, Pedro Roca Molina. Revision `params.REV` = **A0**. Binding brief: `reference/BRICOHAMS_LSR2_BRIEF.md`. Code: `cad/lsr2/route_b.py` (self-test and CSV writer: `python cad/lsr2/route_b.py`; solids by `build.py`). Cost: [LSR2_MATERIALS](LSR2_MATERIALS.md). Alternative: [LSR2_ROUTE_A_CASTING](LSR2_ROUTE_A_CASTING.md).

Tags: **DATASHEET** (published, with source), **MEASURE** (needs a caliper), **PARAMETRIC** (our choice, editable in `params.CNC` / `params.TOL` / `inputs.py`).

> **NO NC CODE.** No G-code is generated or shipped. Machine, controller and post-processor are unknown and the simulation is not validated. The feeds and speeds below are PARAMETRIC starting values: **recompute for the real tool, alloy and machine**. Fusion references from the brief: set-up creation <https://help.autodesk.com/view/fusion360/ENU/?contextId=MFG-CREATE-SETUP>, simulation <https://help.autodesk.com/view/fusion360/ENU/?contextId=MFG-SIMULATION>. Work flow: import the `cnc/lsr2/<part>_finished.step`, define the set-ups of the CSV, simulate with stock = `<part>_blank.step`, only then post-process.

## 1. Variants, alloys, blanks (Variantes)

Machine travel (`inputs.cnc_travel`, PARAMETRIC assumption) = 600 x 400 x 100 mm; usable Z = travel - `tool_clear_z` 15 = **85 mm**. Blank = piece bounding box + `margin` 1.5 mm per face + clamping tab 8 mm per side (footprint), thickness snapped to the stock thicknesses `plate_t` sold. All interfaces of the finished solid are kept; `build.py` checks blank contains finished, and the pieces add up to the variant volume.

| Part | Qty | Pieces (machine z) | Alloy (PARAMETRIC; Rp0.2 ~240-250 MPa T6, DATASHEET EN 485-2 / EN 755-2, check the mill certificate) | Fixture |
|---|---|---|---|---|
| body | 1 | 5 bolted z-slabs, each an 80 mm plate | 6082-T6 | fixture plate + toe clamps on tabs, dowels D6 |
| lid | 1 | one plate (12 mm stock) | 6061-T6 | fixture plate + toe clamps |
| mast_bracket | 1 | `tube_clamp` (on its side, joint at z = -60) + `top_plate` bolted to it | 6082-T6 | fixture plate / round-blank fixture |
| yoke_arm | 2 | one flat plate each, y vertical | 6082-T6 | vise with soft jaws |
| saddle | 1 | one plate | 6061-T6 | fixture plate |
| boom_clamp | 2 | one plate each | 6061-T6 | vise or fixture plate |

Alloy rule: 6082 for the loaded parts (more strength per EUR in EU plate), 6061 for plates and blocks that are stiffness- or clamp-governed with cheap off-cuts. Both are choices from the calc and availability; confirm stock with the supplier.

**Machinability rules (self-tested):** internal radii >= tool radius (tool list below); every operation depth <= tool reach; deep inside corners of the body cavity are R6 (the E12 radius, `corner_r`) and the variant adds R6 fillers in the four vertical cavity corners (`machinable('body')`); thinnest rough wall `z_wall_min` 3 mm.

| Tool | Ø (mm) | Flutes | Reach (mm) | Role |
|---|---|---|---|---|
| E12 / E12L | 12 | 3 | 36 / 75 | roughing, contour (long reach) |
| E8 / E8L | 8 | 3 | 24 / 50 | finishing, chamfer (long reach) |
| E6 | 6 | 3 | 24 | small finishing |
| D8.5 / D5 | 8.5 / 5 | 2 | 40 / 30 | drill M10 or seat / M6 |
| BH | boring head | 1 | 90 | bores, line boring |

All PARAMETRIC. The body is **bolted sub-bodies**: the closed cavity (336 mm tall, 300 mm deep) is not machinable in one piece with a reach <= 75 mm. Slab joints (z = -22, 46, 112, 176, 238, 314) avoid the EL boss (z 242..294) and the shelf (140..148).

## 2. Set-up sheets (Hojas de operación)

Common structure per piece (full tables in `cam/lsr2/<part>_setups.csv`, section 3):

1. **S1 first clamping and primary datum**: datum A = ground blank underside on the fixture, B = edge / fixed jaw stop, C = end stop or dowel hole #1 (drilled in the clamping tab). Face, rough with finishing stock `stock_finish` 0.3 mm, finish the lid (rim) face, gasket groove and internal seats **from this set-up**; drill the two flip dowels D6.
2. **S2 flip on verified datums**: flip on the dowels (soft pins), face to thickness, finish the base face, AZ seat and the mast pattern; chamfer 0.5 x 45; remove tabs.
3. **S3 re-orient for EL (body)**: the two coaxial EL bores are finished in **ONE reference**: line boring through the assembled slabs or a verified transfer fixture on the S1 dowels. Gearbox patterns, breather and EL pad are horizontal. **OPEN DECISION**: 4th axis, angle plate, or outsourced horizontal line boring (not within `inputs.cnc_travel`).
4. Cable passages, gearbox patterns, sensor bosses, threads and chamfers in S1/S2 where the features face up (S3 for horizontal ones).
5. **Finish**: deburr, clean (degrease, ultrasonic for threads), chromate conversion (conductive, default) or anodise, with masks on fits, threads and the electrical-continuity zones (lid-body earth lands); final dimensional check after finishing.

## 3. CAM sheet per part (Hojas CAM)

`cam/lsr2/<part>_setups.csv` (generated by `python cad/lsr2/route_b.py` and by `build.py`): columns `part, piece, setup, seq, op, work_offset, blank_orientation, clamp, holder, tool, rpm, feed_mm_min, doc_mm, woc_mm, depth_mm, note`. Work offsets WCS1 (G54) / WCS2 (G55) at the datum corner of each set-up. Starting values (PARAMETRIC: `vc` 250 m/min, `fz` 0.05 mm/tooth, `rpm_max` 12000, rough ap/ae 0.5 D, finish ap 1.0 D with 0.3 mm radial stock; drills and chamfers at half feed): `rpm = min(Vc·1000/(πD), rpm_max)`, `feed = rpm · z · fz`. Hand check: Ø10, 3 flutes -> 7958 rpm, 1194 mm/min. **Recompute for the real tool/alloy/machine.** Boring heads use 2000 rpm / 100 mm/min placeholders.

| Piece type | Sequence (tool) |
|---|---|
| body slab | S1: face (E12) → rough cavity profile (E12L) → rough ribs/pillar pockets (E12) → finish walls, lid face, base face (E8L) → corners R3 (E6) → drill joint pilots M6 + dowels D6 (D5) → bore AZ, gland, drain (BH). S2: face joint B → finish → drill → chamfer. S3 (EL slab): EL bores + pad holes: OPEN DECISION |
| plate (lid, saddle, boom clamp) | S1: face → rough pockets/window/profile (E12) → finish (E6) → holes, dowels (D5) → chamfer (E8). S2: face to thickness → lid underside gasket groove 2 deep and face → chamfer |
| tube clamp | S1: face end A → helical rough bore Ø60.5 (E12L) → lug profile (E8L) → pinch pilots M8, dowels (D5) → bore half length (BH). S2: face end B → bore from B → chamfer; slit by saw |
| top plate (cap) | S1: face → rough cup ring (E12L) → labyrinth ring (E8) → Ø31 pocket (BH) → joint pilots (D5). S2: face, chamfer |
| yoke arm | S1: face → rough profile, boss, flange (E12) → finish; flange top is the saddle datum (E8) → pilot (D8.5) → Ø20 H7 bore + 6x6 keyway (BH, E6). S2: face outer end, chamfer |

## 4. Raw blank and cost

Blank size, mass, removed volume, minutes and EUR come from `route_b.cost` and the build report (`parts.<part>.route_b`): minutes = removed cm³ / `mrr_cm3_min` 15 + set-ups x `setup_min` 25; machine `rate_eur_h` 40 EUR/h; stock `price_eur_kg` 11 EUR/kg (all PARAMETRIC, VERIFY with quotes). Route comparison with the recommendation per part: [LSR2_MATERIALS](LSR2_MATERIALS.md).

## 5. Inspection before release (Inspección)

Numeric tolerances are `params.TOL` (PARAMETRIC defaults until the 11e table fixes them; each is tied to the mating part):

| Check | Tolerance |
|---|---|
| Coaxiality of the two EL bores (one reference) | 0.04 mm |
| AZ axis perpendicular to EL axis | 0.05 mm over the body |
| Lid (rim) face flatness | 0.10 mm |
| Base face flatness | 0.05 mm |
| Datum distances (base to EL axis, AZ to EL) | ±0.10 mm |
| Ø62 / Ø20 H7 bores | +0.021 / 0 mm |
| AZ 6206 seats | 0.019 mm (Ø62 per bearing catalogue, DATASHEET) |
| EL 6004 seats | 0.016 mm (Ø42 per bearing catalogue, DATASHEET) |

Measure with a CMM or surface plate + height gauge + bore gauge, again after finishing. Parts leaving a failed check are re-machined from the stock left on the datum faces only if the stock allows, otherwise rejected.

## 6. Output files

`cnc/lsr2/<part>_finished.step` (the 3-axis variant), `cnc/lsr2/<part>_blank.step` (compound of the blanks; per-piece `<part>_<piece>_*.step` for the multi-piece parts), `cam/lsr2/<part>_setups.csv`.

## 7. Open decisions

1. Real machine travel, controller, post-processor and tool library; simulate before any NC code.
2. Body horizontal features (EL bores, EL gearbox pad, breather): 4th axis, angle plate or outsourced line boring; the body on route B is also expected to be uneconomic (heavy waste), so route A is the expected default.
3. Joint lands, bolts and sealing between the body slabs and between the mast-bracket pieces are not modelled; the slab joints cut the 5 mm walls and create leak paths (sealant or O-ring).
4. Base face flatness is done by contour on the slabs; a final skim after assembly is undecided.
5. Alloy per part (6082 vs 6061) against what the supplier stocks.
6. Finish: chromate conversion (conductive) or anodise, and the masks list.
