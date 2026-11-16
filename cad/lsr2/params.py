"""LSR-2 heavy rotator: single source of parameters for CAD scripts and calc/lsr2_sizing.py.

Units: mm, N, N·m, kg, deg. Values tagged VERIFY come from generic catalogues; measure the real
part with a caliper (or read its own datasheet) and update here before cutting or casting metal.
No geometry here is taken from the SARCTrac Mk5 files (see docs/superpowers/specs/2026-11-16-lsr2-heavy-rotator-design.md §2).
"""

# --- Stepper motor: NEMA23, 57BYG250H class (2.8 N·m, 3 A) -------------------------------
NEMA23 = dict(
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

# --- Geometry used by the loads ------------------------------------------------------------
EL_AXIS_HEIGHT = 0.30    # m from the upper AZ radial bearing to the EL axis
MAST_D = (40.0, 60.0)    # accepted mast range, mm

# --- Motion ---------------------------------------------------------------------------------
VMAX_DPS = 12.0          # output deg/s (both axes)
MICROSTEP = 8
AZ_RANGE = (-360.0, 360.0)
EL_RANGE = (-30.0, 150.0)

# --- Fabrication (casting) ------------------------------------------------------------------
CAST = dict(alloy='A356-T6', shrink=1.013, draft_out=2.0, draft_in=3.0,
            machining=2.5, min_wall=5.0, min_fillet=3.0, max_section_ratio=3.0)
PLATE = dict(alloy='6061-T6 or 5083', thickness=(8.0, 10.0))
LIGHTEN = dict(min_web=6.0, keep_out=20.0)   # mm: web between cut-outs/edges; clear ring around functional holes
ALU_PLATE_G_CM3, ALU_CAST_G_CM3, PLA_G_CM3 = 2.70, 2.68, 1.24
