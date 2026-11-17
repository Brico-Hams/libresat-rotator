# LSR-2 body and lid in Autodesk Fusion (alternative build)

`cad/lsr2/lsr2_fusion_build.py` rebuilds the LSR-2 main body and lid as **parametric Fusion features** (sketches, extrudes, shell, fillet, taper/draft, scale, plain blocks for the CNC blanks). It exists because the FreeCAD build (`cad/lsr2/build.py`) hangs right after exporting `cast/lsr2/body_core.step`, in the route A / route B derivation of the body (`route_a.py`, `route_b.py`, `body.py`: pattern, lost-PLA, hot-spot and mesh steps).

**FreeCAD stays the reference build.** Fusion is a free-for-personal-use, closed-source tool, not open source: use this script to get patterns, blanks and STEP/STL files when FreeCAD stalls, then cross-check with the FreeCAD report once it runs again. Dimensions and parameters come from `params.py` and `inputs.py` (plain Python, no FreeCAD imports); the body geometry constants are copied from `body.py`, so update both when the body changes.

## What it replaces

| FreeCAD | Fusion |
|---|---|
| `body.body()`, `body.lid()` | `*_finished` components |
| `route_a.preform()` (finished + machining stock) | `*_preform` |
| `route_a` pattern (preform × shrink, draft, cores) | `*_pattern` (taper from `draft_out` / `draft_lid`, Scale by `shrink`), `body_core` (cavity + core print) |
| `route_b` blanks | `*_blank` (margin, clamping tab, plate thickness from `params.CNC`) |

Not covered: lost-PLA variant, hot-spot analysis, pattern halves/print splitting, all other parts (gearbox, yoke, shafts, assembly).

## Run

1. Fusion: **Utilities > Scripts and Add-Ins > Scripts > "+" (add existing script) > select the folder `cad/lsr2`** (the file `lsr2_fusion_build.py`; a Fusion script also needs a `.manifest`, which Fusion offers to create when you add the file) **> Run**.
2. Or call it through the Fusion MCP server / another script: `import lsr2_fusion_build; lsr2_fusion_build.main(r'C:\out')`. Output directory: argument, else `LSR2_FUSION_OUT`, else `<repo>/build/fusion`.

Outputs, same names as the FreeCAD build:

- `<out>/cast/lsr2/{body,lid}_{finished,preform,pattern}.step|stl` and `body_core.step|stl`
- `<out>/cnc/lsr2/{body,lid}_finished.step|stl` and `{body,lid}_blank.step|stl`
- `<out>/build/lsr2_fusion_report.json`: per part volume (cm³), mass (g, densities from `params.py`: cast Al 2.68, PLA 1.24 × infill 0.25, CNC stock 2.70), bounding box (mm), `isValid`, the invariant results and warnings
- `cad/lsr2/fusion/LSR2_body.f3d`: the editable design

Editable **user parameters** (Modify > Change Parameters): `shrink`, `wall`, `stock`, `fillet`, `draft_out`, `draft_in`, `draft_lid`, `core_print`, `blank_margin`, `blank_tab`. `shrink`, `wall`, `stock`, `fillet`, `draft_*` drive features directly; the part dimensions stay numeric sketches.

## Checks (as the FreeCAD self-tests)

The script asserts: every body valid; preform contains finished; blank contains finished (Boolean difference < 1 mm³); pattern encloses preform × shrink and its volume ≥ preform × shrink³; preform larger than finished. A failed invariant raises an error after the report is written.

## Status

Written without a Fusion session available: first run may need small API adjustments (face/edge selection for the shell and fillet, taper sign). Warnings are listed in the report.

## Layout model: vertical plate, Mk5-style rotor (`cad/lsr2/fusion/lsr2_mk5_layout.py`)

A fully constrained parametric Fusion model of the LSR-2 rotor in the SARCTrac Mk5 arrangement. Arrangement replicated, own dimensions, no third-party CAD geometry: every size comes from `params.py` / `inputs.py` (NMRV030 envelope, NEMA23 57x57 with 47.14 bolt square, 51206 thrust bearing, mast, boom and antenna inputs) and is held as a Fusion user parameter.

**Arrangement (front view, plate vertical)**

- A vertical aluminium **plate** is the backbone. The **EL gearbox** (NMRV030) is mounted high, the **AZ gearbox** (NMRV030) low, same orientation, fins under the bodies, 4 face holes PCD65 M6.
- **EL motor** and **AZ motor** (NEMA23) sit on the same side, one above the other, parallel, input flanges facing the same way.
- **AZ shaft**: vertical, out of the AZ hollow output, down through a **thrust-bearing housing** (51206) at the bottom edge of the plate into the **mast bracket**, which clamps the **mast** with two U-bolts. The bracket is fixed to the AZ shaft; plate and everything above rotate around it.
- **EL shaft**: horizontal through the EL hollow output, protruding on both sides beyond the **cover**, with a hub at each end and an **index disc** (with slotted sensor) on one end; the AZ shaft carries its own index disc and sensor.
- **bracket_L/R** rise from the shaft ends to the **saddle plate**; two **boom clamps** hold the **boom** (horizontal, parallel to the EL shaft). At each boom end a **lift arm** carries an **antenna** above (Yagi boom plus elements) and a **counterweight** below.
- A transparent **cover** encloses plate, gearboxes and motors. A transparent-lid **enclosure** (4 corner screws) on the right side holds the WiFi bulkhead and antenna, controller PCB, 5 V DC-DC, two finned driver heatsinks (EL, AZ) and a cable gland at the bottom.

```
 PC + USB dongle (micro controller + WiFi antenna)
        :  wireless link (WiFi)
        v
 +--------------------- enclosure (side of the plate) ------------------+        +-----------+
 | WiFi antenna -> micro controller -> EL motor controller -> EL motor  |        |  external |
 |                        |          -> AZ motor controller -> AZ motor |<-gland-|  POWER    |
 |                 5 V DC converter                                      |        |  SUPPLY   |
 +-----------------------------------------------------------------------+        +-----------+
 rotor: motor -> NMRV030 -> EL shaft -> brackets -> saddle -> boom -> lift arms -> antennas / counterweights
        motor -> NMRV030 -> AZ shaft -> thrust bearing -> mast bracket (2 U-bolts) -> mast
```

Only the rotor is modelled; PC, dongle and PSU appear only in this block diagram.

**Model**

- One component per part: `plate`, `cover_*`, `enclosure`, `enclosure_lid`, `enc_screw`, `cable_gland`, `wifi_bulkhead`, `wifi_antenna`, `heatsink_el/az`, `controller_pcb`, `dcdc_5v`, `el_gearbox`, `az_gearbox`, `el_motor`, `az_motor`, `el_shaft`, `index_disc_el/az`, `sensor_el/az`, `thrust_housing`, `thrust_bearing`, `az_shaft`, `mast_bracket`, `u_bolt`, `mast_tube`, `el_hub_L/R`, `bracket_L/R`, `saddle_plate`, `boom_clamp`, `boom`, `lift_arm_L/R`, `antenna_L/R`, `counterweight_L/R`. Repeated parts are occurrences of one component.
- User parameters `el_angle` (default 45 deg) and `az_angle` (default 0) rotate the moving groups: EL group (shaft ends, hubs, brackets, saddle, clamps, boom, arms, antennas, counterweights) about the EL axis; AZ group (everything above the mast bracket) about the AZ axis. Default pose matches the side-view photo (elevation 45).
- Every sketch lies on the origin plane of its component and is fully constrained (geometric constraints plus dimensions that are parameter expressions). The script checks `sketch.isFullyConstrained` after each sketch and raises with the failing sketch names.
- Placement uses occurrence transforms computed from the parameters (no joints); re-run after changing a parameter.
- Run like the body script (`run(context)` or `main(out_dir)`). Outputs: `build/lsr2_mk5_layout_report.json` (mass per part, CG and gravity torque of the moving groups, bounding box, interference at el -30, 0, 45, 90, 150 with az 0, `sketches_checked_not_fully_constrained` = []) and `cad/lsr2/LSR2_mk5_layout.step`.
- Not yet run in Fusion: first run may need small API adjustments (transform setting, interference analysis fall back to bounding boxes with a warning).
