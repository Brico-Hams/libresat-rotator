// LibreSat Rotator LSR-1 — parametric printed parts
// Usage: openscad -D 'PART="act_body"' -o act_body.stl lsr.scad
// PART list: see the dispatcher at the bottom (or `make stl`).
// Coordinates: actuator axis = +z, z = 0 on the motor mounting face.

include <lsr_params.scad>

PART = "assembly";
BOOM = BOOM_D;          // antenna boom diameter for clamps (round)
BOOM_SQ = 0;            // >0: square boom side (e.g. 20) for boom clamps
NUT = "3/8";            // tripod adapter: "3/8" (photo tripod, + 1/4 reducer) or "5/8" (survey tripod)
MAST_D = 32;            // mast clamp adapter: mast diameter
ANT_L = 700;
AZ_DEG = 0;             // assembly pose
EL_DEG = 20;
EXPLODE = 0;            // act_assembly explode distance            // antenna boom length drawn in the assembly
EBOX = [104, 84, 40];   // e-box inner size: LSR-CTL 100 x 80 on 16 mm standoffs, Pi Zero 2 W hanging under it

// =================================================================== helpers
module ring(r1, r2, h) difference() { cylinder(r = r2, h = h); translate([0, 0, -EPS]) cylinder(r = r1, h = h + 2*EPS); }
module at_circle(n, r, a0 = 0) for (i = [0:n-1]) rotate(a0 + i*360/n) translate([r, 0, 0]) children();
module at_angles(list, r) for (a = list) rotate(a) translate([r, 0, 0]) children();
module hexagon(af, h) cylinder(d = af/cos(30), h = h, $fn = 6);
module rounded_box(s, r = 3) hull() for (x = [r, s[0]-r], y = [r, s[1]-r]) translate([x, y, 0]) cylinder(r = r, h = s[2]);
module label(t, s = 5, d = 0.6) linear_extrude(d + EPS) text(t, size = s, halign = "center", valign = "center", font = "Liberation Sans:style=Bold");

function cyc_pt(t) = let(
    N = N_PINS, R = R_PIN, Rr = PIN_D/2 + PROFILE_CLR, E = ECC,
    psi = atan2(sin((1 - N)*t), R/(E*N) - cos((1 - N)*t)))
    [R*cos(t) - Rr*cos(t + psi) - E*cos(N*t), -R*sin(t) + Rr*sin(t + psi) + E*sin(N*t)];
module cyc_profile() polygon([for (i = [0:LOBES*24 - 1]) cyc_pt(i*360/(LOBES*24))]);

module d_shaft(h, clr = 0.1) intersection() {
    cylinder(d = NEMA_SHAFT + 2*clr, h = h, $fn = 40);
    translate([-(NEMA_SHAFT/2 + 1), -(NEMA_SHAFT/2 + 1), 0]) cube([NEMA_SHAFT + 2, NEMA_DFLAT + clr - NEMA_SHAFT/2 + NEMA_SHAFT/2 + 1, h]);
}

// =================================================================== actuator
// --- body: motor flange floor + ring-pin wall (print floor down, no supports)
module act_body() difference() {
    union() {
        cylinder(r = WALL_R, h = FLOOR_T);
        ring(BORE_R, WALL_R, Z_BODY);
    }
    // motor pilot + cam clearance
    translate([0, 0, -EPS]) cylinder(d = NEMA_PILOT[0] + 0.4, h = NEMA_PILOT[1] + 0.2);
    translate([0, 0, -EPS]) cylinder(d = 14, h = FLOOR_T + 1);
    // motor screws M3x8, heads recessed below the floor top (discs run above)
    for (x = [-1, 1], y = [-1, 1]) translate([x*NEMA_HOLE/2, y*NEMA_HOLE/2, 0]) {
        translate([0, 0, -EPS]) cylinder(d = M3_CLR, h = FLOOR_T + 1);
        translate([0, 0, FLOOR_T - 3.3]) cylinder(d = M3_HEAD[0] + 0.4, h = 4);
    }
    // ring pin grooves (full height) + 3.5 mm deep seats in the floor
    at_circle(N_PINS, R_PIN) {
        translate([0, 0, FLOOR_T - 3.5]) cylinder(d = PIN_D + PRESS, h = Z_BODY, $fn = 24);
    }
    // through-bolts M4
    at_angles(THRU_ANG, THRU_R) translate([0, 0, -EPS]) cylinder(d = M4_CLR, h = Z_BODY + 1, $fn = 24);
    // cable notch for the AZ rear encoder is in the encoder cap; index arrow
    translate([WALL_R - 0.6, 0, FLOOR_T/2]) rotate([0, 90, 0]) linear_extrude(1) polygon([[-2, -2], [2, 0], [-2, 2]]);
}

// --- front housing: pin retainer flange + output bearing seat
module act_front(hall = HALL_TAB) difference() {
    union() {
        cylinder(r = WALL_R, h = RET_T);
        cylinder(r = FRONT_R, h = Z_COVER - Z_BODY);
        if (hall) hall_tab();
    }
    // washer clearance + rear bearing shoulder (outer ring only)
    translate([0, 0, -EPS]) cylinder(r = 31, h = Z_COVER);
    // bearing seat (inserted from the front)
    translate([0, 0, Z_BRG - Z_BODY]) cylinder(d = OUT_BRG[1] + PRESS, h = 2*OUT_BRG[2] + 1);
    // ring pin seats
    at_circle(N_PINS, R_PIN) translate([0, 0, -EPS]) cylinder(d = PIN_D + PRESS, h = 3.5, $fn = 24);
    // through-bolts
    at_angles(THRU_ANG, THRU_R) translate([0, 0, -EPS]) cylinder(d = M4_CLR, h = RET_T + 1, $fn = 24);
    // front cover inserts
    at_circle(4, COVER_INS_R, 45) translate([0, 0, Z_COVER - Z_BODY - INSERT_M3[1]]) cylinder(d = INSERT_M3[0], h = INSERT_M3[1] + 1, $fn = 24);
}
module hall_tab() {
    // DRV5032FB / AH1806 3.3 V hall switch (TO-92) facing +z just below the turntable; magnet in the turntable
    top = ACT_LEN - 1.5 - Z_BODY;
    difference() {
        hull() {
            translate([FRONT_R - 6, -7, 0]) cube([1, 14, top]);
            translate([HALL_R + 3, -5, top - 10]) cube([1, 10, 10]);
            translate([FRONT_R - 6, -7, 0]) cube([HALL_R + 3 - FRONT_R + 7, 14, 1]);
        }
        translate([HALL_R - 2.3, -1.8, top - 2]) cube([4.6, 3.6, 2 + EPS]);                // sensor body
        translate([HALL_R - 1.5, -1.2, RET_T + 1]) cube([3, 2.4, top]);                     // legs / wires down
        translate([HALL_R - 1.5, -1.2, RET_T + 1]) cube([12, 2.4, 3]);                     // ...and out sideways
    }
}

// --- front cover: clamps the outer rings of the output bearings
module act_cover() difference() {
    cylinder(r = FRONT_R, h = COVER_T);
    translate([0, 0, -EPS]) cylinder(r = 30.9, h = COVER_T + 1);
    at_circle(4, COVER_INS_R, 45) translate([0, 0, -EPS]) cylinder(d = M3_CLR, h = COVER_T + 1, $fn = 24);
}

// --- output: hub (in bearings) + neck + face plate; 6 output dowels pressed from below
module act_output() difference() {
    union() {
        translate([0, 0, Z_BRG]) cylinder(d = OUT_BRG[0] - 0.02, h = Z_COVER - Z_BRG + EPS);
        translate([0, 0, Z_COVER]) cylinder(r = 27, h = Z_FLANGE - Z_COVER + EPS);
        translate([0, 0, Z_FLANGE]) cylinder(r = OUT_R, h = FLANGE_T);
    }
    // output dowels
    at_circle(N_OUT, OUT_PIN_R) translate([0, 0, Z_BRG - EPS]) cylinder(d = OUT_PIN_D + PRESS - 0.05, h = 16, $fn = 24);
    // washer screws M3 (self-tapping, 2.6 pilot) between the dowels
    at_circle(3, 15, 30) translate([0, 0, Z_BRG - EPS]) cylinder(d = 2.6, h = 10, $fn = 16);
    // motor shaft end clearance
    translate([0, 0, Z_BRG - EPS]) cylinder(d = 9, h = 6);
    // load inserts M4 on the face (between dowels)
    at_circle(6, OUT_BOLT_R, 30) translate([0, 0, ACT_LEN - INSERT_M4[1]]) cylinder(d = INSERT_M4[0], h = INSERT_M4[1] + 1, $fn = 24);
    // centre pilot recess (8 mm) for the mating parts
    translate([0, 0, ACT_LEN - 2]) cylinder(d = 16.2, h = 3);
}

// --- washer: retains the hub from the motor side (inner ring of the rear bearing)
module act_washer() difference() {
    cylinder(r = 28, h = WASHER_T);
    translate([0, 0, -EPS]) cylinder(d = 9, h = 5);
    at_circle(N_OUT, OUT_PIN_R) translate([0, 0, -EPS]) cylinder(d = OUT_PIN_D + 0.3, h = 5, $fn = 24);
    at_circle(3, 15, 30) translate([0, 0, -EPS]) { cylinder(d = M3_CLR, h = 5, $fn = 16); }
}

// --- cycloid disc (print 2; the second is mounted rotated 180 deg)
module act_disc() difference() {
    linear_extrude(DISC_T) cyc_profile();
    translate([0, 0, -EPS]) cylinder(d = CAM_BRG[1] + PRESS, h = DISC_T + 1, $fn = 96);
    at_circle(N_OUT, OUT_PIN_R) translate([0, 0, -EPS]) cylinder(d = OUT_HOLE_D, h = DISC_T + 1, $fn = 40);
    // orientation mark: the two discs go in with the marks 180 deg apart
    translate([R_PIN - PIN_D/2 - ECC - 4, 0, DISC_T - 0.6]) cylinder(d = 2, h = 1);
}

// --- double eccentric cam on the motor D-shaft (bearings 6803 pressed on)
module act_cam() {
    z0 = NEMA_PILOT[1] + 0.4;
    b1 = Z_D1 + DISC_T/2 - CAM_BRG[2]/2;               // bearing 1 bottom
    zm = Z_D1 + DISC_T + DISC_GAP/2;                    // between discs
    difference() {
        union() {
            translate([0, 0, z0]) cylinder(d = 12, h = b1 - z0 + EPS);
            translate([ECC, 0, b1]) cylinder(d = CAM_BRG[0] - 0.02, h = zm - b1 + EPS, $fn = 72);
            translate([-ECC, 0, zm]) cylinder(d = CAM_BRG[0] - 0.02, h = Z_DTOP - zm, $fn = 72);
            // shoulders that locate the inner rings
            translate([ECC, 0, b1 - 0.6]) cylinder(d = 19.5, h = 0.6 + EPS, $fn = 72);
        }
        translate([0, 0, z0 - 1]) d_shaft(Z_DTOP + 2);
    }
}

// --- rear encoder cap: AS5600 board over a 6 x 2.5 mm diametric magnet on the rear shaft
AS5600_BOARD = [23.5, 23.5];   // measure your module
AS5600_HOLES = 15.5;           // M2.5 hole pitch (diagonal pair); slots allow +-2 mm
module enc_cap() {
    L = 14;                    // sleeve over the motor rear
    H = REAR_SHAFT + 4.5;      // board underside above the motor rear face
    w = NEMA_W + 0.6;
    difference() {
        union() {
            translate([-w/2 - 2.4, -w/2 - 2.4, 0]) cube([w + 4.8, w + 4.8, L + H + 2]);
        }
        translate([-w/2, -w/2, -EPS]) cube([w, w, L + EPS]);                            // motor body
        translate([0, 0, L - EPS]) cylinder(r = 15, h = H + EPS);                        // magnet room
        translate([-AS5600_BOARD[0]/2 - 0.3, -AS5600_BOARD[1]/2 - 0.3, L + H - EPS]) cube([AS5600_BOARD[0] + 0.6, AS5600_BOARD[1] + 0.6, 3]);
        // board fixing slots
        for (s = [-1, 1]) hull() for (d = [-2, 2]) translate([s*(AS5600_HOLES/2 + d), 0, L]) cylinder(d = 2.7, h = H + 5, $fn = 16);
        // grub screws M3 against the motor body
        for (a = [0, 90]) rotate(a) translate([w/2 - 1, 0, L/2]) rotate([0, 90, 0]) cylinder(d = 2.6, h = 6, $fn = 16);
        // cable exit
        translate([-6, w/2 - 1, L + 1]) cube([12, 5, H]);
    }
}

// =================================================================== azimuth base
NUT_POCKET = 8;
module base() {
    rim_t = 9;
    difference() {
        union() {
            ring(BASE_R - 3.5, BASE_R, BASE_H);
            translate([0, 0, BASE_H - rim_t]) ring(35, BASE_R, rim_t);
            cylinder(r = BASE_R, h = 5);
            at_circle(4, 30, 45) cylinder(d = 13, h = 10);                   // adapter insert bosses
            // e-box mounting pad
            translate([-BASE_R - 4, -22, 0]) cube([8, 44, 46]);
        }
        // central hole in the floor (cables / adapter nut)
        translate([0, 0, -EPS]) cylinder(d = 40, h = 11);
        // adapter inserts M4 from below
        at_circle(4, 30, 45) translate([0, 0, -EPS]) cylinder(d = INSERT_M4[0], h = INSERT_M4[1], $fn = 24);
        // actuator through-bolts + nut traps from below
        at_angles(THRU_ANG, THRU_R) {
            translate([0, 0, BASE_H - rim_t - 1]) cylinder(d = M4_CLR, h = rim_t + 2, $fn = 24);
            translate([0, 0, BASE_H - rim_t - EPS]) hexagon(M4_NUT_AF + 0.3, 4);
        }
        // cable exit (motor + encoder of AZ, and head loop entry) towards the e-box
        translate([-BASE_R - 5, -11, 8]) cube([20, 22, 16]);
        // e-box bolts M4 (inserts in the pad)
        for (z = [14, 38]) for (y = [-14, 14]) translate([-BASE_R - 4 - EPS, y, z]) rotate([0, 90, 0]) cylinder(d = INSERT_M4[0], h = INSERT_M4[1], $fn = 24);
        // north arrow on the rim (AZ = 0 reference, pointing +x)
        translate([BASE_R - 0.6, 0, BASE_H - 5]) rotate([90, 0, 90]) label("N", 5, 0.8);
        // drain / vent holes
        at_circle(6, 44, 0) translate([0, 0, -EPS]) cylinder(d = 4, h = 6, $fn = 16);
    }
}

// --- tripod / stand adapters (bolt to the base floor with 4 x M4 x 12)
module adapter_plate(h) difference() {
    cylinder(r = 40, h = h);
    at_circle(4, 30, 45) {
        translate([0, 0, -EPS]) cylinder(d = M4_CLR, h = h + 1, $fn = 24);
        translate([0, 0, -EPS]) cylinder(d = M4_HEAD[0] + 0.5, h = h - 5, $fn = 24);
    }
}
module adapter_nut(kind = NUT) {
    // captive nut faces the tripod screw: 3/8-16 (photo, use a brass 3/8->1/4 reducer for 1/4-20) or 5/8-11 (survey)
    af = kind == "5/8" ? 23.9 : 14.4;  nt = kind == "5/8" ? 14.4 : 8.4;  bolt = kind == "5/8" ? 16.3 : 9.8;
    h = nt + 6;
    difference() {
        adapter_plate(h);
        translate([0, 0, -EPS]) cylinder(d = bolt, h = h + 1);
        translate([0, 0, h - nt]) hexagon(af + 0.3, nt + 1);
        translate([0, 0, h - 0.6]) label(kind == "5/8" ? "5/8-11" : "3/8-16", 4);
    }
}
module adapter_spigot35() {   // 35 mm speaker-stand / lighting-stand pole
    difference() {
        union() { adapter_plate(8); translate([0, 0, -60]) cylinder(d = 47, h = 60 + EPS); }
        translate([0, 0, -60 - EPS]) cylinder(d = 35.6, h = 64);
        // M6 thumb screw with captive nut
        translate([0, 0, -30]) rotate([0, 90, 0]) { cylinder(d = 6.5, h = 30); translate([0, 0, 19.5]) rotate(30) hexagon(M6_NUT_AF + 0.3, 5.5); }
    }
}
module adapter_mast(d = MAST_D) {   // tube mast 20..50 mm: split socket with 2 x M5
    o = d + 14;
    difference() {
        union() { adapter_plate(8); translate([0, 0, -60]) cylinder(d = o, h = 60 + EPS); translate([d/2, -9, -60]) cube([10, 18, 60]); }
        translate([0, 0, -60 - EPS]) cylinder(d = d + 0.4, h = 64);
        translate([d/2 - 2, -1, -60 - EPS]) cube([14, 2, 60]);
        for (z = [-48, -15]) translate([d/2 + 5, 12, z]) rotate([90, 0, 0]) { cylinder(d = M5_CLR, h = 24, $fn = 20); hexagon(M5_NUT_AF + 0.3, 4); }
    }
}

// =================================================================== head (turntable + EL tower), one piece
module head() {
    zt = TT_T;                        // turntable top
    za = zt + AXIS_H;                 // EL axis
    ph = za + 50;                     // tower height
    difference() {
        union() {
            cylinder(r = TT_R, h = zt);
            translate([X_TOWER - TOWER_T, -50, 0]) cube([TOWER_T, 100, ph]);
            // gussets (both sides of the motor, and in front under the actuator)
            for (y = [-50, 50 - 7]) translate([X_TOWER - TOWER_T + EPS, y, 0]) rotate([90, 0, 0]) translate([0, 0, -7])
                linear_extrude(7) polygon([[0, 0], [0, za - 8], [-20, 0]]);
            for (y = [-50, 50 - 7]) translate([X_TOWER - EPS, y, 0]) rotate([90, 0, 0]) translate([0, 0, -7])
                linear_extrude(7) polygon([[0, 0], [0, 26], [26, 0]]);
        }
        // turntable bolts to the AZ output face (counterbored from the top)
        at_circle(6, OUT_BOLT_R, 30) {
            translate([0, 0, -EPS]) cylinder(d = M4_CLR, h = zt + 1, $fn = 24);
            translate([0, 0, 2.5]) cylinder(d = M4_HEAD[0] + 0.6, h = zt, $fn = 24);
        }
        translate([0, 0, -EPS]) cylinder(d = 16, h = 2.2);       // pilot clearance
        // index magnet 6 x 3 under the turntable
        translate([HALL_R, 0, -EPS]) cylinder(d = 6.2, h = 3.2, $fn = 24);
        // motor + encoder cap pass through the tower
        translate([X_TOWER - TOWER_T - 1, 0, za]) rotate([0, 90, 0]) translate([-(NEMA_W + 6)/2, -(NEMA_W + 6)/2, 0]) cube([NEMA_W + 6, NEMA_W + 6, TOWER_T + 2]);
        translate([X_TOWER - TOWER_T - 1, 0, za]) rotate([0, 90, 0]) cylinder(d = NEMA_PILOT[0] + 4, h = TOWER_T + 2);
        // EL actuator through-bolts M4 (nuts on the -x side)
        translate([X_TOWER, 0, za]) rotate([0, -90, 0]) at_angles(THRU_ANG, THRU_R) {
            translate([0, 0, -EPS]) cylinder(d = M4_CLR, h = TOWER_T + 1, $fn = 24);
            translate([0, 0, TOWER_T - 3.5]) hexagon(M4_NUT_AF + 0.3, 4);
        }
        // cable holes (EL motor + sensors down to the loop)
        translate([X_TOWER - TOWER_T - 1, 30, zt + 8]) rotate([0, 90, 0]) cylinder(d = 10, h = TOWER_T + 2);
        translate([X_TOWER - TOWER_T - 1, -30, zt + 8]) rotate([0, 90, 0]) cylinder(d = 10, h = TOWER_T + 2);
        // cable-tie slots at the turntable rim
        for (a = [150, 210]) rotate(a) translate([TT_R - 6, -2, -EPS]) cube([3, 4, zt + 1]);
        translate([X_TOWER - TOWER_T + 0.6, 0, ph - 14]) rotate([90, 0, -90]) label("LSR-1", 7, 0.8);
    }
}

// =================================================================== EL stub socket (on the EL output face)
module stub_socket() {
    L = 52; o = STUB_D + 12;
    difference() {
        union() {
            cylinder(r = OUT_R, h = 8);
            cylinder(d = o, h = 8 + L);
            translate([o/2 - 2, -9, 8 + 6]) cube([10, 18, L - 6]);                 // pinch lugs
            translate([-11, -o/2 - 6, 8]) cube([22, 8, 20]);                        // IMU pad (side)
        }
        at_circle(6, OUT_BOLT_R, 30) {
            translate([0, 0, -EPS]) cylinder(d = M4_CLR, h = 9, $fn = 24);
            translate([0, 0, 4]) cylinder(d = M4_HEAD[0] + 0.6, h = 60, $fn = 24);
        }
        translate([0, 0, -EPS]) cylinder(d = 16.0, h = 2.0 + EPS);                 // centre pilot (mates with the 16.2 recess)
        translate([0, 0, 10]) cylinder(d = STUB_D + 0.3, h = L + 1);
        translate([o/2 - 4, -1, 10]) cube([16, 2, L + 1]);                          // split
        for (z = [8 + 16, 8 + L - 10]) translate([o/2 + 3, 12, z]) rotate([90, 0, 0]) { cylinder(d = M4_CLR, h = 24, $fn = 20); hexagon(M4_NUT_AF + 0.3, 4); }
        // GY-521 (MPU-6050) on the side pad: x axis of the board along the stub
        translate([-10.75, -o/2 - 6 - EPS, 9]) cube([21.5, 1.2, 16.5]);
        for (z = [12, 24]) translate([-6, -o/2 - 6 - EPS, z]) rotate([-90, 0, 0]) cylinder(d = 2.2, h = 6, $fn = 12);
        translate([0, -o/2 - 1, 30]) rotate([90, 0, 0]) linear_extrude(1) text("IMU X->", size = 3, halign = "center");
    }
}

// =================================================================== antenna side
// cross clamp: stub (along x) x antenna boom (along y)
module boom_clamp(bd = BOOM, sq = BOOM_SQ) {
    bw = sq > 0 ? sq : bd;
    zA = 0; zB = STUB_D/2 + bw/2 + 5;
    s = max(STUB_D, bw) + 14;
    difference() {
        translate([-s/2, -s/2, -STUB_D/2 - 7]) cube([s, s, zB + bw/2 + 7 + STUB_D/2 + 7]);
        rotate([0, 90, 0]) cylinder(d = STUB_D + 0.3, h = s + 2, center = true);
        translate([0, 0, zB]) rotate([90, 0, 0]) if (sq > 0) cube([sq + 0.4, sq + 0.4, s + 2], center = true); else cylinder(d = bd + 0.3, h = s + 2, center = true);
        // split slots
        translate([-s/2 - 1, -1, -STUB_D/2 - 8]) cube([s + 2, 2, STUB_D/2 + 8]);
        translate([-1, -s/2 - 1, zB]) cube([2, s + 2, bw/2 + 8]);
        // pinch bolts
        for (x = [-s/4, s/4]) translate([x, s/2 + 1, -STUB_D/2 - 3.5]) rotate([90, 0, 0]) { cylinder(d = M4_CLR, h = s + 2, $fn = 20); translate([0, 0, s - 3]) hexagon(M4_NUT_AF + 0.3, 5); }
        for (y = [-s/4, s/4]) translate([-s/2 - 1, y, zB + bw/2 + 3.5]) rotate([0, 90, 0]) { cylinder(d = M4_CLR, h = s + 2, $fn = 20); translate([0, 0, s - 3]) rotate(30) hexagon(M4_NUT_AF + 0.3, 5); }
    }
}

// counterweight: clamps on the boom, M8 bolt hangs washers / nuts
module counterweight_clamp(bd = BOOM) difference() {
    union() { cylinder(d = bd + 12, h = 24); translate([-12, bd/2 + 2, 0]) cube([24, 14, 24]); translate([-12, -bd/2 - 12, 0]) cube([24, 10, 24]); }
    translate([0, 0, -EPS]) cylinder(d = bd + 0.3, h = 25);
    translate([-1, -bd/2 - 13, -EPS]) cube([2, 14, 25]);
    translate([-13, -bd/2 - 7, 12]) rotate([0, 90, 0]) { cylinder(d = M4_CLR, h = 26, $fn = 20); hexagon(M4_NUT_AF + 0.3, 4); }
    translate([0, bd/2 + 1, 12]) rotate([-90, 0, 0]) { cylinder(d = 8.4, h = 20); translate([0, 0, 3]) rotate(30) hexagon(13.3, 7); }
}

// sun sight: pinhole vane (front) + target vane (rear), 80 mm apart, parallel to the boom
module sun_sight(bd = BOOM) {
    L = 90; hgt = bd/2 + 22;
    difference() {
        union() {
            translate([-L/2, -7, 0]) cube([L, 14, 5]);
            for (x = [-L/2, L/2 - 4]) translate([x, -12, 0]) cube([4, 24, hgt + 8]);
        }
        // boom saddle (rests on top of the boom, held with two cable ties)
        translate([0, 0, -bd/2 + 1.2]) rotate([0, 90, 0]) cylinder(d = bd + 0.4, h = L + 2, center = true);
        for (x = [-L/4, L/4]) translate([x - 2, -8, -EPS]) cube([4, 16, 2]);
        // pinhole in the front vane, crosshair rings on the rear vane
        translate([L/2 - 5, 0, hgt]) rotate([0, 90, 0]) cylinder(d = 1.5, h = 7, $fn = 16);
        translate([-L/2 + 3.4, 0, hgt]) rotate([0, 90, 0]) for (r = [2, 5]) difference() { cylinder(r = r + 0.35, h = 1, $fn = 48); translate([0, 0, -EPS]) cylinder(r = r - 0.35, h = 2, $fn = 48); }
        translate([-L/2 + 3.4, -0.35, hgt - 8]) cube([1, 0.7, 16]);
        translate([-L/2 + 3.4, -8, hgt - 0.35]) cube([1, 16, 0.7]);
    }
}

// cable clip for the AZ loop (snaps on 6 mm cable bundles, screws to the turntable slots with a tie)
module cable_clip(d = 9) difference() {
    union() { cylinder(d = d + 5, h = 8); translate([-(d + 5)/2, -d/2 - 6, 0]) cube([d + 5, 6, 8]); }
    translate([0, 0, -EPS]) cylinder(d = d, h = 9);
    translate([-d/3, 0, -EPS]) cube([2*d/3, d, 9]);
    translate([-1.8, -d/2 - 7, 2]) cube([3.6, 8, 4]);
}

// =================================================================== electronics box (PCB + Pi Zero 2 W + GPS on the lid)
EB_W = 3;
module ebox() {
    s = [EBOX[0] + 2*EB_W, EBOX[1] + 2*EB_W, EBOX[2] + EB_W];
    SO = 16;                                    // PCB standoff height (Pi Zero hangs below the board)
    pcb_z = EB_W + SO + 1.6;                    // PCB top surface
    bx = EB_W + (EBOX[0] - 100)/2; by = EB_W + (EBOX[1] - 80)/2;   // PCB origin
    difference() {
        rounded_box(s, 4);
        translate([EB_W, EB_W, EB_W]) rounded_box([EBOX[0], EBOX[1], EBOX[2] + 1], 2);
        // right wall: XT30 + DC jack (board edge x = 100, y 8..38)
        translate([s[0] - EB_W - 1, by + 8, pcb_z - 2]) cube([EB_W + 2, 31, 14]);
        // left wall: Pico USB (board y ~ 60)
        translate([-1, by + 53, pcb_z + 6]) cube([EB_W + 2, 14, 10]);
        // front wall (board y = 0 side): 2 x PG7 for the sensor cables; back wall: 2 x PG7 for the motors
        for (x = [30, 74]) translate([bx + x, -1, pcb_z + 12]) rotate([-90, 0, 0]) cylinder(d = 12.6, h = EB_W + 2);
        for (x = [62, 82]) translate([bx + x, s[1] - EB_W - 1, pcb_z + 12]) rotate([-90, 0, 0]) cylinder(d = 12.6, h = EB_W + 2);
        // vents over the drivers (back wall, high) and low on the left wall
        for (i = [0:5]) translate([bx + 56 + i*7, s[1] - EB_W - 1, pcb_z + 22]) cube([3, EB_W + 2, 10]);
        for (i = [0:5]) translate([-1, by + 10 + i*7, EB_W + 4]) cube([EB_W + 2, 3, 10]);
        // floor: 4 x M4 countersunk to the base pad (28 x 24 mm pattern, clear of the Pi Zero)
        for (dx = [-14, 14], y = [58, 82]) translate([s[0]/2 + dx, y, -EPS]) { cylinder(d = M4_CLR, h = 10, $fn = 20); translate([0, 0, EB_W - 2.2]) cylinder(d1 = M4_CLR, d2 = 8.6, h = 2.2 + 2*EPS, $fn = 24); }
    }
    // corner posts with M3 inserts for the lid
    for (x = [EB_W + 3, s[0] - EB_W - 3], y = [EB_W + 3, s[1] - EB_W - 3]) translate([x, y, 0]) difference() {
        cylinder(d = 8, h = s[2]);
        translate([0, 0, s[2] - INSERT_M3[1]]) cylinder(d = INSERT_M3[0], h = INSERT_M3[1] + 1, $fn = 20);
    }
    // PCB standoffs (M3 inserts, 93 x 73 hole pattern)
    for (x = [3.5, 96.5], y = [3.5, 76.5]) translate([bx + x, by + y, EB_W - EPS]) difference() {
        cylinder(d = 7, h = SO);
        translate([0, 0, SO - INSERT_M3[1]]) cylinder(d = INSERT_M3[0], h = INSERT_M3[1] + 1, $fn = 20);
    }
}
// L-bracket: base side pad (vertical, 4 x M4) -> horizontal shelf for the e-box floor (lid + GPS face the sky)
module ebox_bracket() {
    // x < 0 is the base; the shelf points away from it
    difference() {
        union() {
            translate([0, -22, 0]) cube([8, 44, 46]);                     // against the base pad
            translate([0, -22, 0]) cube([70, 44, 7]);                     // shelf
            for (y = [-22, 15]) translate([0, y + 7, 0]) rotate([90, 0, 0])
                linear_extrude(7) polygon([[8, 7], [8, 40], [48, 7]]);    // gussets
        }
        for (z = [14, 38], y = [-14, 14]) translate([-1, y, z]) rotate([0, 90, 0]) cylinder(d = M4_CLR, h = 12, $fn = 20);
        // shelf: 4 x M4 heat-set inserts matching the e-box floor (28 x 24)
        for (x = [32, 56], y = [-14, 14]) translate([x, y, -EPS]) cylinder(d = INSERT_M4[0], h = 8, $fn = 20);
    }
}
module ebox_lid() {
    s = [EBOX[0] + 2*EB_W, EBOX[1] + 2*EB_W];
    difference() {
        union() {
            rounded_box([s[0], s[1], 2.4], 4);
            translate([EB_W + 0.3, EB_W + 0.3, 2.4 - EPS]) difference() { rounded_box([EBOX[0] - 0.6, EBOX[1] - 0.6, 3], 2); translate([1.6, 1.6, -EPS]) rounded_box([EBOX[0] - 3.8, EBOX[1] - 3.8, 4], 1); }
        }
        for (x = [EB_W + 3, s[0] - EB_W - 3], y = [EB_W + 3, s[1] - EB_W - 3]) translate([x, y, -EPS]) { cylinder(d = M3_CLR, h = 10, $fn = 16); cylinder(d = M3_HEAD[0] + 0.4, h = 1.2, $fn = 24); }
        // GPS patch window (ATGM336H / NEO-M8N 25 x 25 ceramic patch faces up through a 0.6 mm skin)
        translate([s[0] - 40, s[1]/2 - 14, 0.6]) cube([28, 28, 3]);
        // 12 mm bubble level
        translate([22, s[1]/2, 0.8]) cylinder(d = 12.4, h = 3);
        translate([s[0]/2, 12, -EPS]) mirror([1, 0, 0]) linear_extrude(0.6) text("LibreSat Rotator LSR-1", size = 5, halign = "center", font = "Liberation Sans:style=Bold");
    }
}

// =================================================================== assembly (visual check)
module act_assembly(explode = 0) {
    color("dimgray") translate([-NEMA_W/2, -NEMA_W/2, -MOTOR_LEN]) cube([NEMA_W, NEMA_W, MOTOR_LEN]);
    color("orange") act_body();
    color("gold") translate([0, 0, Z_BODY + explode]) act_front();
    color("silver") for (z = [Z_BRG, Z_BRG + OUT_BRG[2]]) translate([0, 0, z + explode]) ring(OUT_BRG[0]/2, OUT_BRG[1]/2, OUT_BRG[2]);
    color("gold") translate([0, 0, Z_COVER + 2*explode]) act_cover();
    color("tomato") translate([0, 0, 2*explode]) act_output();
    color("skyblue") translate([0, 0, Z_BRG - WASHER_T + explode/2]) act_washer();
    color("lightgreen") translate([ECC, 0, Z_D1]) act_disc();
    color("seagreen") translate([-ECC, 0, Z_D2]) rotate(180) act_disc();
    color("white") act_cam();
    color("silver") at_circle(N_PINS, R_PIN) translate([0, 0, FLOOR_T - 3.5]) cylinder(d = PIN_D, h = PIN_L, $fn = 12);
    color("orange") translate([0, 0, -MOTOR_LEN]) mirror([0, 0, 1]) enc_cap();
}
module assembly() {
    color("orange") base();
    translate([0, 0, BASE_H]) {
        act_assembly();
        translate([0, 0, ACT_LEN]) rotate(AZ_DEG) {
            color("darkorange") head();
            za = TT_T + AXIS_H;
            translate([X_TOWER, 0, za]) rotate([0, 90, 0]) rotate([0, 0, 0]) {
                act_assembly();
                translate([0, 0, ACT_LEN]) rotate(-EL_DEG) {
                    color("darkorange") stub_socket();
                    color("lightgray") translate([0, 0, 10]) cylinder(d = STUB_D, h = 240);
                    translate([0, 0, 190]) rotate([0, -90, 0]) {
                        color("orange") boom_clamp();
                        // antenna boom (indicative, 1 m)
                        color("lightgray") translate([0, 0, STUB_D/2 + BOOM/2 + 5]) rotate([90, 0, 0]) cylinder(d = BOOM, h = ANT_L, center = true);
                    }
                }
            }
        }
    }
    color("orange") translate([0, 0, -14.4]) adapter_nut("3/8");
    // e-box on its shelf bracket, lid (GPS) facing the sky
    translate([-BASE_R - 4, 0, 0]) mirror([1, 0, 0]) color("darkorange") ebox_bracket();
    translate([-34, -55, 7]) rotate(90) { color("orange") ebox(); color("gold") translate([0, 0, EBOX[2] + EB_W + 2.4 + 0.5]) mirror([0, 0, 1]) ebox_lid(); }
    // tripod head (indicative)
    color("dimgray") translate([0, 0, -14.4 - 40]) cylinder(d = 60, h = 40);
}

// =================================================================== dispatcher
if (PART == "act_body") act_body();
else if (PART == "act_front") act_front(true);
else if (PART == "act_front_nohall") act_front(false);
else if (PART == "act_cover") act_cover();
else if (PART == "act_output") translate([0, 0, ACT_LEN]) rotate([180, 0, 0]) act_output();
else if (PART == "act_washer") act_washer();
else if (PART == "act_disc") act_disc();
else if (PART == "act_cam") translate([0, 0, -(NEMA_PILOT[1] + 0.4)]) act_cam();
else if (PART == "enc_cap") translate([0, 0, REAR_SHAFT + 4.5 + 16]) rotate([180, 0, 0]) enc_cap();
else if (PART == "base") base();
else if (PART == "adapter_nut") translate([0, 0, NUT == "5/8" ? 20.4 : 14.4]) rotate([180, 0, 0]) adapter_nut(NUT);
else if (PART == "adapter_spigot35") translate([0, 0, 8]) rotate([180, 0, 0]) adapter_spigot35();
else if (PART == "adapter_mast") translate([0, 0, 8]) rotate([180, 0, 0]) adapter_mast(MAST_D);
else if (PART == "head") head();
else if (PART == "stub_socket") stub_socket();
else if (PART == "boom_clamp") translate([0, 0, STUB_D/2 + 7]) boom_clamp(BOOM, BOOM_SQ);
else if (PART == "counterweight_clamp") counterweight_clamp(BOOM);
else if (PART == "sun_sight") sun_sight(BOOM);
else if (PART == "cable_clip") cable_clip();
else if (PART == "ebox") ebox();
else if (PART == "ebox_lid") ebox_lid();
else if (PART == "ebox_bracket") ebox_bracket();
else if (PART == "act_assembly") act_assembly(EXPLODE);
else if (PART == "act_section") difference() { act_assembly(); translate([-200, -200, -200]) cube([400, 200, 400]); }
else assembly();
