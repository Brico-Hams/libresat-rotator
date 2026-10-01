// LibreSat Rotator LSR-1 — shared parameters (all dimensions in mm)
// Change here, then `make stl`. calc/cycloid_check.py mirrors the reducer values.

$fn = 64;
EPS = 0.01;

// ---------------- printer tolerances
TOL      = 0.20;   // general sliding clearance
PRESS    = 0.05;   // press fit (bearings, dowels): hole = nominal + PRESS
INSERT_M3 = [4.2, 5.7];   // heat-set insert hole d, depth (M3 x 5.7)
INSERT_M4 = [5.6, 8.1];   // heat-set insert hole d, depth (M4 x 8.1)
M3_CLR = 3.4;  M3_HEAD = [6.0, 3.2];
M4_CLR = 4.5;  M4_HEAD = [7.5, 4.2];  M4_NUT_AF = 7.0;
M5_CLR = 5.5;  M5_NUT_AF = 8.0;
M6_NUT_AF = 10.0;

// ---------------- motor (NEMA17)
NEMA_W     = 42.3;
NEMA_HOLE  = 31.0;   // hole pitch
NEMA_PILOT = [22.0, 2.0];
NEMA_SHAFT = 5.0;
NEMA_DFLAT = 4.5;    // across the D-flat
MOTOR_LEN  = 40;     // 17HS4401 = 40, "Lite" pancake 17HS08 = 23
REAR_SHAFT = 12;     // dual-shaft motors: rear shaft length (for the encoder magnet)

// ---------------- cycloidal reducer
N_PINS   = 26;            // fixed ring pins -> LOBES = 25 -> 25:1
LOBES    = N_PINS - 1;
RATIO    = LOBES;
R_PIN    = 36.0;          // ring pin circle radius
PIN_D    = 4.0;           // ring pins: 4 x 20 mm steel dowels (ISO 8734 m6)
PIN_L    = 20.0;
ECC      = 1.0;           // eccentricity
PROFILE_CLR = 0.15;       // tooth running clearance (calc/cycloid_check.py)
DISC_T   = 6.0;           // each disc
DISC_GAP = 0.5;
BORE_R   = R_PIN + 0.4;   // housing bore in the disc zone (pins sit in grooves)

CAM_BRG  = [17, 26, 5];   // 6803-2RS  (d, D, B)  x2
OUT_BRG  = [50, 65, 7];   // 61810-2RS (6810)     x2
OUT_PIN_R = 22.0;
OUT_PIN_D = 4.0;          // 6 x 4 x 30 mm dowels
OUT_PIN_L = 30.0;
N_OUT     = 6;
OUT_HOLE_D = OUT_PIN_D + 2*ECC + 0.3;

// ---------------- actuator axial stack (z = 0 on the motor face)
FLOOR_T  = 6.5;                          // body floor (motor flange)
Z_D1     = FLOOR_T + 0.25;               // disc 1 bottom
Z_D2     = Z_D1 + DISC_T + DISC_GAP;     // disc 2 bottom
Z_DTOP   = Z_D2 + DISC_T;                // top of disc 2
Z_BODY   = Z_DTOP + 0.5;                 // body / front housing split plane
WASHER_T = 2.0;
Z_BRG    = Z_BODY + WASHER_T + 0.5;      // first output bearing
Z_COVER  = Z_BRG + 2*OUT_BRG[2];         // front cover bottom
COVER_T  = 2.5;
Z_FLANGE = Z_COVER + COVER_T + 0.5;      // output face plate bottom
FLANGE_T = 6.0;
ACT_LEN  = Z_FLANGE + FLANGE_T;          // gearbox length (excl. motor)
WALL_R   = 47;                           // body / floor outer radius (actuator is 94 mm across)
ACT_R    = WALL_R;
THRU_R   = 42;                           // 4 x M4 through-bolts (front housing+body -> mounting)
THRU_ANG = [for (j = [0.5, 6.5, 12.5, 19.5]) j*360/N_PINS];  // midway between ring pins (~square)
OUT_R    = 30.5;                         // output face plate radius
OUT_BOLT_R = 24;                         // 6 x M4 heat-set inserts on the output face
FRONT_R  = 40;                           // front housing (bearing seat) outer radius
COVER_INS_R = 36.3;                      // 4 x M3 inserts for the front cover
RET_T    = 5;                            // front housing flange (pin retainer) thickness
HALL_TAB = true;

// ---------------- structure / antenna
STUB_D   = 20.0;    // EL stub tube (20 x 2 aluminium or 20 mm fiberglass)
BOOM_D   = 20.0;    // antenna boom (override per STL: 15/20/22/25)
AXIS_H   = 55;      // EL axis height above the turntable top
TT_T     = 7;       // turntable thickness
X_TOWER  = -22;     // tower plate +x face position (actuator floor bolts here)
TOWER_T  = 8;       // tower plate thickness
TT_R     = 52;      // turntable radius
HALL_R   = 45;      // AZ index magnet / hall sensor radius
BASE_R   = 56;      // base outer radius
BASE_H   = MOTOR_LEN + 26;
