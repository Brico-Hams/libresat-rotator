"""LSR-2 heavy rotator: single source of parameters for CAD scripts and calc/lsr2_sizing.py.

Units: mm, N, N·m, kg, deg. Values tagged VERIFY come from generic catalogues; measure the real
part with a caliper (or read its own datasheet) and update here before cutting or casting metal.
No geometry here is taken from the SARCTrac Mk5 files (see docs/superpowers/specs/2026-11-16-lsr2-heavy-rotator-design.md §2).
"""

# --- Stepper motor: NEMA23, 57BYG250H class (2.8 N·m, 3 A) -------------------------------
NEMA23 = dict(
    model='57BYG250H-8',                                                  # the motor SARCTrac Mk5 uses (SARCNET); 8-lead, 112 mm body
    face=56.4, hole_square=47.14, hole_d=5.1, pilot_d=38.1, pilot_h=1.6,  # NEMA ICS 16 standard
    shaft_d=8.0, length=112.0,                                            # 8 mm keyed shaft: VERIFY
    t_hold=2.8, i_rated=3.0, steps_rev=200,
)

# --- Worm gearboxes (generic NMRV series, ratio 80:1) ------------------------------------
# m2_rated: output torque rating at i=80 (catalogue, low duty); fr2: output radial load at
# shaft mid-extension; bore: hollow output, DIN 6885 key. All VERIFY with the supplier's sheet.
GEARBOX = {
    'NMRV030': dict(ratio=80, m2_rated=16.7, fr2=1250.0, bore=14.0, key_w=5.0, centre=30.0),
    'NMRV040': dict(ratio=80, m2_rated=31.0, fr2=1800.0, bore=18.0, key_w=6.0, centre=40.0),
    'NMRV050': dict(ratio=80, m2_rated=55.0, fr2=2400.0, bore=25.0, key_w=8.0, centre=50.0),
}
GEARBOX_DEFAULT = 'NMRV030'
# NMRV030 envelope (generic catalogue drawing, oyostepper NMRV030-40-50.pdf). Axes: 'out' = output
# axis, 'worm' = worm axis, 'n' = the third direction. Output centre sits 40 from the worm-free end
# along 'worm' and 40 from the foot along 'n'; worm axis is 30 from the output axis along 'n'.
NMRV030_GEO = dict(
    out_width=56.0, hub_len=63.0, worm_len=80.0, worm_len_flange=95.0, worm_from_end=40.0,
    n_len=97.0, out_from_foot=40.0, face_holes='M6', face_hole_depth=11.0, face_pcd=65.0,
    pilot_clear_d=55.2,   # clearance for the output boss/hub: VERIFY on the real part
)
WORM_EFF_RUN = 0.45      # 80:1 worm at ~150 rpm input (low-speed efficiency, conservative)
GEAR_PEAK_FACTOR = 2.0   # short-term/standstill torque vs rating (catalogue fs, VERIFY)
GEAR_REF_ARM = 0.030     # m: lever from housing face to where fr2 is quoted (VERIFY)

# --- AZ bearing stack ----------------------------------------------------------------------
THRUST = dict(name='51206', d=30.0, D=52.0, H=16.0, C=25.1e3, C0=40.0e3)   # catalogue values
RADIAL = dict(name='6206', d=30.0, D=62.0, B=16.0, C=20.3e3, C0=11.2e3)    # external pair
RADIAL_SPAN = 0.120      # m between the two radial bearings in the AZ housing
# Mk5 (SARCNET) stacks M30x56x3 stainless washers as shims under the 51206; here one replaces the old 3 mm ring, up to SHIM_N_MAX adjust
# the preload. DIN 471 circlip 1.5 mm + SHIM_N_MAX x 3 mm must fit the 10 mm between the shaft washer and the mast clamp (calc checks). VERIFY.
SHIM = dict(name='M30x56x3 washer, A2/A4', d=30.0, D=56.0, t=3.0, n_fitted=1, n_max=2, circlip_t=1.5)

# --- EL head (phase 6b) ---------------------------------------------------------------------
# The one-sided cross boom (along the EL axis) makes a bending moment that only a bearing PAIR can carry (as on AZ).
# 2 x 6206 on a Ø30 shaft section, same bearing as the AZ pair (one stock item): 6205 on Ø25 gives a shaft SF of 1.8 (< 2).
BEARING_EL = RADIAL
EL_BEARING_SPAN = 0.062  # m between the two EL bearing centres (>= 60 mm wanted, VERIFY)
SS_YIELD_MPA = 200.0     # 1.4404 (316L) annealed bar yield: VERIFY with the mill certificate
SS_E_MPA = 193000.0      # stainless modulus: VERIFY
CROSS_BOOM = (40.0, 40.0, 3.0)   # square 6063 tube: width, height, wall (mm): VERIFY with the supplier
CROSS_BOOM_L = 1100.0    # mm: legacy phase-6 boom length (phase 11 boom length is in axes.K)
TUBE_YIELD_MPA = 170.0   # 6063-T6 minimum yield: VERIFY
# Antenna stations along the boom, metres from the socket mouth (VERIFY). The mass is the Yagi payload of calc/lsr2_sizing.py, shared equally.
ANT_POS_Y = (0.45, 0.95)
ANT_BOOM_L, ANT_ELEM_L = 2000.0, 1000.0   # mm, Yagi boom along the pointing direction, elements across: envelope boxes for the EL sweep
SOCKET_MASS_KG = 0.35    # legacy phase-6 socket mass, unused by phase 11
FACE_THREAD_N = 10000.0  # axial capacity of one M6 in the NMRV face (11 mm in cast aluminium) and of an 8.8 screw: VERIFY
EL_COAX_MM = 0.04        # coaxiality of the housing bearing seats and the gearbox hub, bored in one setup with the face recess: VERIFY

# --- Geometry used by the loads ------------------------------------------------------------
EL_AXIS_HEIGHT = 0.30    # m from the upper AZ radial bearing to the EL axis
MAST_D = (40.0, 60.0)    # accepted mast range, mm

# --- Motion ---------------------------------------------------------------------------------
VMAX_DPS = 12.0          # output deg/s (both axes)
MICROSTEP = 2            # DM542 at 400 microsteps/rev as on SARCTrac Mk5 (SARCNET): 1066.7 steps/s at 12 deg/s
AZ_RANGE = (-360.0, 360.0)
EL_RANGE = (-30.0, 150.0)

# --- Photo-interrupter index (SARCTrac Mk5 idea, SARCNET data; our own printed geometry), one per axis ---------------------------
# Printed ASA disc (ring 8 mm wide, 3 mm thick) with one radial notch on its rim; a slotted photo-interrupter (EE-SX1103 class, 5 mm
# gap: VERIFY with the datasheet) straddles the rim. Phase 11: AZ disc is pinned on the stationary Ø14 AZ shaft stub in the free air
# z 115..140 between the body pillar top and the gearbox shelf (PARAMETRIC, VERIFY), its sensor bracket stands on the pillar top (rotates
# with the body, post az_post high); EL disc on the EL shaft (turns with the boom), sensor on the body wall.
INDEX = dict(material='ASA', t=3.0, ring=8.0, notch_arc=4.0, notch_depth=5.0, gap=5.0, fit_clear=0.2,
             sensor_holes=19.0, sensor_hole_d=3.2, az_shaft_d=14.0, az_z=(130.0, 133.0), az_post=12.0, min_notch_deg=4.0, edge_margin_deg=3.0)
# Mk5 uses M14 stainless threaded rod + 5x8 roll pins as the axis shafts; calc/lsr2_sizing.py evaluates it against our turned keyed shafts.
M14_ROD = dict(name='M14 A2-70 threaded rod', d_stress=12.1, yield_mpa=450.0, pin_d=5.0)   # A2-70 Rp0.2 450 MPa, M14x2 stress-area d: VERIFY

# --- Fabrication (casting) ------------------------------------------------------------------
CAST = dict(alloy='A356-T6', shrink=1.013, draft_out=2.0, draft_in=3.0,
            machining=2.5, min_wall=5.0, min_fillet=3.0, max_section_ratio=3.0)
PLATE = dict(alloy='6061-T6 or 5083', thickness=(8.0, 10.0))
LIGHTEN = dict(min_web=6.0, keep_out=20.0)   # mm: web between cut-outs/edges; clear ring around functional holes
ALU_PLATE_G_CM3, ALU_CAST_G_CM3, PLA_G_CM3 = 2.70, 2.68, 1.24

# --- Phase 11c Route A: casting (PARAMETRIC unless noted; every value "to agree with the foundry") -----------------------------------
# One dict per quantity group so shrinkage, draft, stock, wall and fillet stay independent. CAST_PART overrides CAST per part (cad/lsr2/route_a.py).
REV = 'A0'                                   # revision string stamped in the report and the file names of every cast/CNC model
CAST.update(hot_spot_max=2.0,                # largest inscribed sphere / adjacent wall; above it a riser, chill or core is required (route_a.JUNCTIONS)
            pla_fill=0.25,                   # infill fraction of the recoverable printed pattern (volume x this = PLA)
            series=1,                        # castings made per pattern (PLA and pattern cost are divided by this)
            lump_max=2.0,                    # sand lump depth / mean width in the green-sand pattern pockets
            draft_step=4.0,                  # mm per slice of the stacked-offset draft of the printable pattern
            core_print=30.0, core_clear=0.5, # core print length beyond the open face, sand clearance (mm)
            dowel_d=8.0, dowel_len=10.0, dowel_clear=0.3,            # registration pin of the pattern halves / print joints (mm)
            print_margin=6.0)                # usable print volume = inputs print_volume - this per axis (brim, skirt, bed edge)
CAST_PART = {                                # per-part overrides of CAST (empty = the part follows CAST)
    'lid': dict(draft_out=1.0),              # 5 mm flat plate: draft is below the printer resolution anyway
    'saddle': dict(draft_out=1.0),
    'boom_clamp': dict(draft_out=1.0),
}
# Consumable (lost-PLA) pattern: a SEPARATE parameter set, never mixed with CAST. The pattern is the finished-plus-stock solid itself (cavity
# included, sand poured into it), so it has no draft, no cores and no halves. Material, wall and burn-out are decided with the foundry.
CAST_LOST = dict(material='low-ash PLA (e.g. foundry-approved casting filament)', shrink=1.013, machining=3.0, wall=2.0, infill=0.0,
                 vent_d=3.0, note='TO BE APPROVED BY THE FOUNDRY: burn-out strategy, coating, vent and sprue layout')
# --- Phase 11d Route B: CNC from block / plate (PARAMETRIC) --------------------------------------------------------------------------------
CNC = dict(alloys=('6082-T6', '6061-T6'), density=2.70, price_eur_kg=11.0,      # block/plate stock EUR/kg, VERIFY with a quote
           margin=1.5, tab=8.0, plate_t=(10, 12, 15, 20, 25, 30, 40, 50, 60, 80, 100),   # blank margin per face, clamping tab per footprint side, stock thicknesses sold (mm)
           tool_clear_z=15.0,                                                    # spindle-nose and holder clearance subtracted from the z travel
           tools=(dict(name='E12', d=12.0, z=3, reach=36.0, role='rough'), dict(name='E12L', d=12.0, z=3, reach=75.0, role='rough / contour, long reach'),
                  dict(name='E8', d=8.0, z=3, reach=24.0, role='finish'), dict(name='E8L', d=8.0, z=3, reach=50.0, role='finish contour, long reach'),
                  dict(name='E6', d=6.0, z=3, reach=24.0, role='finish small'), dict(name='D8.5', d=8.5, z=2, reach=40.0, role='drill M10 / seat'),
                  dict(name='D5', d=5.0, z=2, reach=30.0, role='drill M6'), dict(name='BH', d=0.0, z=1, reach=90.0, role='boring head')),
           corner_r=6.0,                                                          # inside vertical corners of deep pockets = E12 radius (body cavity floor corners)
           vc=250.0, fz=0.05, rpm_max=12000, ap_rough=0.5, ae_rough=0.5, ap_finish=1.0,   # m/min, mm/tooth, rpm, depth/width of cut as fractions of D: recompute for the real tool/alloy/machine
           mrr_cm3_min=15.0, finish_cm2_min=40.0, setup_min=25.0, rate_eur_h=40.0,                # PARAMETRIC machining time and shop rate
           stock_finish=0.3, z_wall_min=3.0)                                                       # finishing stock per face; thinnest rough wall (mm)
# Numeric manufacturing tolerances until the 11e table fixes them (mm, deg): PARAMETRIC defaults, each tied to the mating component.
TOL = dict(el_coax=0.04, az_el_perp=0.05, flat_lid=0.10, flat_base=0.05, datum_dist=0.10, bore_h7=0.021, seat_6206=0.019, seat_6004=0.016)
