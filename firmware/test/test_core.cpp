// Host unit tests for the hardware-independent firmware logic:  make -C firmware test
#include "../src/core.h"
#include <cstdio>
#include <cmath>
#include <cstring>

static int fails = 0, checks = 0;
#define CHECK(c) do { checks++; if (!(c)) { fails++; std::printf("FAIL %s:%d  %s\n", __FILE__, __LINE__, #c); } } while (0)
#define NEAR(a, b, e) CHECK(std::fabs((double)(a) - (double)(b)) <= (e))

int main() {
    // kinematics
    axis_cfg_t c = {25.0f, 3200, 1, 10.0f, 0, 450, 20, 25, 0.05f};
    NEAR(axis_steps_per_deg(&c), 3200 * 25 / 360.0, 1e-3);
    NEAR(axis_pos_to_deg(&c, axis_deg_to_pos(&c, 123.4f)), 123.4, 0.01);
    c.dir = -1; NEAR(axis_pos_to_deg(&c, axis_deg_to_pos(&c, 77.7f)), 77.7, 0.01);

    // azimuth wrap selection (range 0..450)
    NEAR(az_resolve(10, 350, 0, 450), 370, 1e-4);     // continue through north
    NEAR(az_resolve(10, 100, 0, 450), 10, 1e-4);
    NEAR(az_resolve(80, 440, 0, 450), 440, 1e-4);     // 80+360 is inside the wrap and closest
    NEAR(az_resolve(100, 440, 0, 450), 100, 1e-4);    // 460 is beyond 450 -> unwind
    NEAR(az_resolve(359, 5, 0, 450), 359, 1e-4);      // 359-360 = -1 is out of range
    NEAR(az_resolve(400, 0, 0, 450), 400, 1e-4);      // explicit absolute
    NEAR(az_resolve(-20, 0, 0, 450), 0, 1e-4);        // clamped

    // model profiles: LSR-1 unchanged, LSR-2 per cad/lsr2/params.py
    const lsr_model_t *m1 = lsr_model(1), *m2 = lsr_model(2);
    CHECK(m1->ratio == 25.0f && m1->microsteps == 16 && m1->az_min == 0 && m1->az_max == 450);
    CHECK(m1->el_min == 0 && m1->el_max == 180 && m1->vmax_az == 20 && m1->vmax_el == 15 && m1->flip);
    CHECK(m1->acc_az == 25 && m1->acc_el == 20 && m1->az_user_offset == 0);
    CHECK(lsr_model(7) == m1);
    CHECK(m2->ratio == 80.0f && m2->microsteps == 2 && m2->vmax_az == 12 && m2->vmax_el == 12 && !m2->flip);
    axis_cfg_t a1 = {m1->ratio, m1->microsteps * 200, 1, 0, m1->az_min, m1->az_max, 20, 25, 0.05f};
    axis_cfg_t a2 = {m2->ratio, m2->microsteps * 200, 1, 0, m2->az_min, m2->az_max, 12, 10, 0.05f};
    NEAR(axis_steps_per_deg(&a1), 3200 * 25 / 360.0, 1e-3);          // 222.22
    NEAR(axis_steps_per_deg(&a2), 400 * 80 / 360.0, 1e-3);           // 88.89 (Mk5: 400 microsteps/rev, DM542 DIP switches)
    NEAR(12.0 * axis_steps_per_deg(&a2), 1066.7, 0.1);               // step rate at vmax = Mk5 1066 steps/s, motor 160 rpm
    // LSR-2 ranges: AZ -360..+360 user = 0..720 internal, EL -30..150
    NEAR(lsr_az_to_internal(m2, -360), 0, 1e-4); NEAR(lsr_az_to_internal(m2, 360), 720, 1e-4);
    NEAR(lsr_az_to_user(m2, 360), 0, 1e-4);
    NEAR(lsr_clamp_az_user(m2, -400), -360, 1e-4); NEAR(lsr_clamp_az_user(m2, 400), 360, 1e-4);
    NEAR(lsr_clamp_az_user(m2, 123), 123, 1e-4);
    NEAR(lsr_clamp_el(m2, -45), -30, 1e-4); NEAR(lsr_clamp_el(m2, 170), 150, 1e-4); NEAR(lsr_clamp_el(m2, 10), 10, 1e-4);
    NEAR(lsr_clamp_el(m1, 170), 170, 1e-4); NEAR(lsr_clamp_el(m1, -5), 0, 1e-4);
    NEAR(az_resolve(10, 700, m2->az_min, m2->az_max), 370, 1e-4);   // same wrap logic on 0..720
    NEAR(az_resolve(10, 100, m2->az_min, m2->az_max), 10, 1e-4);
    NEAR(az_resolve(100, 450, m2->az_min, m2->az_max), 460, 1e-4);

    // external STEP/DIR sequencing
    {
        sd_axis_t s; sd_init(&s);
        CHECK(!sd_tick(&s, 1000, false, 1, true));                  // not enabled yet: no step
        CHECK(!sd_tick(&s, 1010, true, 1, true) && s.dir == 1);     // DIR moves first, no step
        CHECK(!sd_tick(&s, 1010 + SD_DIR_SETUP_US - 1, true, 1, true));   // set-up not elapsed
        CHECK(sd_tick(&s, 1010 + SD_DIR_SETUP_US, true, 1, true) && s.step_hi);
        uint32_t t0 = 1010 + SD_DIR_SETUP_US;
        CHECK(!sd_tick(&s, t0 + SD_PULSE_MIN_US - 1, true, 1, true) && s.step_hi);   // pulse still high
        CHECK(!sd_tick(&s, t0 + SD_PULSE_MIN_US, false, 1, false) && !s.step_hi);    // >= min width, then low
        CHECK(sd_tick(&s, t0 + 2 * SD_PULSE_MIN_US, true, 1, true));                // same dir: step at once
        uint32_t t1 = t0 + 2 * SD_PULSE_MIN_US;
        sd_tick(&s, t1 + 10, true, -1, true);                                       // reversal: DIR first
        CHECK(s.dir == -1 && !s.step_hi);
        CHECK(sd_tick(&s, t1 + 10 + SD_DIR_SETUP_US, true, -1, true));
        sd_axis_t w; sd_init(&w);                                   // wrap-safe timestamps
        sd_tick(&w, 0xFFFFFFFFu - 2, true, 1, true);
        CHECK(sd_tick(&w, 0xFFFFFFFFu - 2 + SD_DIR_SETUP_US, true, 1, true));
        CHECK(SD_PULSE_MIN_US >= 3 && SD_DIR_SETUP_US >= 5 && SD_ENABLE_SETTLE_US >= 200000);

        sd_enable_t e = {false, 0};
        CHECK(!sd_enable_ready(&e, 5000000));
        sd_enable_set(&e, true, 1000);
        CHECK(!sd_enable_ready(&e, 1000 + SD_ENABLE_SETTLE_US - 1));
        CHECK(sd_enable_ready(&e, 1000 + SD_ENABLE_SETTLE_US));
        sd_enable_set(&e, true, 999999);                            // repeated enable does not restart the delay
        CHECK(sd_enable_ready(&e, 1000 + SD_ENABLE_SETTLE_US));
        sd_enable_set(&e, false, 2000000);
        CHECK(!sd_enable_ready(&e, 3000000));
        sd_enable_set(&e, true, 3000000);
        CHECK(!sd_enable_ready(&e, 3000000 + 1000));                // re-enable waits again
    }

    // index homing + backlash on a simulated axis: one 8 deg slot per turn, play of 0.4 deg, wrong initial angle estimate
    {
        const float BL = 0.4f, dt = 0.002f;
        struct Case { float o0, off0; bool cal; } cases[] = {{200, 40, true}, {365, 40, true}, {700, -40, true}, {50, 40, false}, {10, -40, true}, {400, 25, false}};
        for (const Case &cs : cases) {
            float m = cs.o0, o = cs.o0, off = cs.off0, o_ref = -1;       // m motor, o output (true frame), off = estimate - m
            auto in_slot = [](float ang) { float r = std::fmod(ang, 360.0f); return r >= 0 && r < 8.0f; };
            idx_t x; idx_start(&x, cs.cal, 0, 720, 360, m + off, in_slot(o));
            int guard = 0;
            while (x.st != IDX_DONE && x.st != IDX_FAIL && guard++ < 3000000) {
                idx_tick(&x, m + off, in_slot(o));
                if (x.ref) { x.ref = false; off = x.home - m; o_ref = o; }
                if (x.st == IDX_DONE || x.st == IDX_FAIL) break;
                float d = clampf(x.target - (m + off), -x.vmax * dt, x.vmax * dt);
                m += d; o = std::fmin(std::fmax(o, m), m + BL);                // backlash: the output stays inside [m, m + BL]
            }
            CHECK(x.st == IDX_DONE);
            NEAR(x.home, o_ref, 0.01);                                       // referenced to the real edge (multiple of 360)
            NEAR(std::fmod(o_ref, 360.0f), 0, 0.02);                         // approached from the + side: no backlash in the reference
            if (cs.cal) NEAR(x.backlash, BL, 0.02);
        }
        idx_t f; idx_start(&f, false, 0, 720, 360, 100, false);              // no slot anywhere: both sweeps end in FAIL
        for (int i = 0; i < 1000000 && f.st != IDX_FAIL; i++) idx_tick(&f, std::fmin(std::fmax(f.target, 0.0f), 720.0f), false);
        CHECK(f.st == IDX_FAIL);
        NEAR(idx_resolve(370, 360, 360, 0, 720), 360, 1e-4); NEAR(idx_resolve(20, 360, 360, 0, 720), 0, 1e-4);
        NEAR(idx_resolve(500, 360, 360, 0, 720), 360, 1e-4); NEAR(idx_resolve(600, 360, 360, 0, 720), 720, 1e-4);
        NEAR(idx_resolve(50, 0, 360, -30, 150), 0, 1e-4);                    // EL: only one slot inside the range
        NEAR(backlash_out(10.0f, 1, 0.4f), 10.0, 1e-5); NEAR(backlash_out(10.0f, -1, 0.4f), 10.4, 1e-5);
        NEAR(backlash_out(10.0f, -1, 0.0f), 10.0, 1e-5);
    }

    // 48 V power-loss detect: debounced, one event per loss, re-arms after the power is back
    {
        pwr_t g = {false, false, 0};                                         // 3 ms glitch is ignored
        pwr_tick(&g, 1000, true); pwr_tick(&g, 4000, false);
        CHECK(!pwr_tick(&g, 4000 + PWR_DEBOUNCE_US + 10, false) && !g.lost);
        pwr_t q = {false, false, 0};
        pwr_tick(&q, 1000, true);
        CHECK(pwr_tick(&q, 1000 + PWR_DEBOUNCE_US, true) && q.lost);         // confirmed: save now
        CHECK(!pwr_tick(&q, 1000 + 2 * PWR_DEBOUNCE_US, true));             // only once
        pwr_tick(&q, 100000, false);
        CHECK(!pwr_tick(&q, 100000 + PWR_DEBOUNCE_US, false) && !q.lost);   // power back: cleared, no event
        pwr_tick(&q, 200000, true);
        CHECK(pwr_tick(&q, 200000 + PWR_DEBOUNCE_US, true));                 // re-armed
        pwr_t w = {false, false, 0xFFFFFFFFu - 2};                           // wrap-safe timestamps
        pwr_tick(&w, 0xFFFFFFFFu - 2, true);
        CHECK(pwr_tick(&w, 0xFFFFFFFFu - 2 + PWR_DEBOUNCE_US, true));
    }

    // planner: reaches target, no overshoot, respects vmax
    plan_state_t p = {0}; double x = 0, tgt = 90, dt = 0.002, vmax = 20, a = 25, peak = 0, maxx = 0;
    for (int i = 0; i < 20000; i++) { double v = plan_step(&p, (float)(tgt - x), (float)vmax, (float)a, (float)dt, 0.05f); x += v * dt; peak = std::fmax(peak, std::fabs(v)); maxx = std::fmax(maxx, x); }
    NEAR(x, tgt, 0.05); CHECK(peak <= vmax + 1e-3); CHECK(maxx <= tgt + 0.06);
    // planner: follows a moving target (LEO pass, 1 deg/s) with small lag
    p.v = 0; x = 0; double t = 0, lag = 0;
    for (int i = 0; i < 10000; i++) { t += dt; double tg = 1.0 * t; double v = plan_step(&p, (float)(tg - x), 20, 25, (float)dt, 0.05f); x += v * dt; if (t > 5) lag = std::fmax(lag, std::fabs(tg - x)); }
    CHECK(lag < 0.1);

    // command parser
    cmd_t cm[8]; int n;
    n = parse_line("AZ EL", cm, 8); CHECK(n == 2 && cm[0].kind == CMD_GET_AZ && cm[1].kind == CMD_GET_EL);
    n = parse_line("AZ123.4 EL45.0 UP000 XXX DN000 XXX", cm, 8);
    CHECK(n == 2 && cm[0].kind == CMD_SET_AZ && cm[1].kind == CMD_SET_EL); NEAR(cm[0].value, 123.4, 1e-4); NEAR(cm[1].value, 45, 1e-4);
    n = parse_line("SA SE", cm, 8); CHECK(n == 2 && cm[0].kind == CMD_STOP_AZ && cm[1].kind == CMD_STOP_EL);
    n = parse_line("VE", cm, 8); CHECK(n == 1 && cm[0].kind == CMD_VERSION);
    n = parse_line("XC vmax_az=12.5", cm, 8); CHECK(n == 1 && cm[0].kind == CMD_XCONF_SET && !std::strcmp(cm[0].key, "vmax_az")); NEAR(cm[0].value, 12.5, 1e-4);
    n = parse_line("XC?", cm, 8); CHECK(n == 1 && cm[0].kind == CMD_XCONF_GET);
    n = parse_line("XCAL AZ=181.5", cm, 8); CHECK(n == 1 && cm[0].kind == CMD_XCAL && !std::strcmp(cm[0].key, "AZ")); NEAR(cm[0].value, 181.5, 1e-4);
    n = parse_line("XCAL BACKLASH", cm, 8); CHECK(n == 1 && cm[0].kind == CMD_XCAL && !std::strcmp(cm[0].key, "BACKLASH"));
    n = parse_line("XS", cm, 8); CHECK(n == 1 && cm[0].kind == CMD_XSTATUS);
    n = parse_line("XP 395.5 12.25", cm, 8); CHECK(n == 1 && cm[0].kind == CMD_XPOS && cm[0].nvals == 2); NEAR(cm[0].value, 395.5, 1e-4); NEAR(cm[0].value2, 12.25, 1e-4);
    n = parse_line("az-5", cm, 8); CHECK(n == 1 && cm[0].kind == CMD_SET_AZ); NEAR(cm[0].value, -5, 1e-4);

    // NMEA (checksums computed for these sentences)
    gps_fix_t f; std::memset(&f, 0, sizeof f);
    CHECK(nmea_parse("$GPRMC,123519,A,4807.038,N,01131.000,E,022.4,084.4,230394,003.1,W*6A", &f));
    CHECK(f.valid); NEAR(f.lat, 48.1173, 1e-4); NEAR(f.lon, 11.516667, 1e-4); CHECK(f.year == 2094 || f.year == 1994 || f.year == 2094);
    CHECK(f.hour == 12 && f.min == 35); NEAR(f.sec, 19, 1e-3);
    CHECK(nmea_parse("$GPGGA,123519,4807.038,N,01131.000,E,1,08,0.9,545.4,M,46.9,M,,*47", &f));
    CHECK(f.sats == 8 && f.fix_quality == 1); NEAR(f.alt, 545.4, 1e-3);
    CHECK(!nmea_parse("$GPGGA,123519,4807.038,N,01131.000,E,1,08,0.9,545.4,M,46.9,M,,*48", &f));

    // TMC CRC: a reply frame must verify with the same polynomial
    unsigned char d[8] = {0x05, 0xFF, 0x02, 0x00, 0x00, 0x00, 0x05, 0};
    d[7] = tmc_crc8(d, 7); CHECK(tmc_crc8(d, 7) == d[7]);

    // IMU elevation: rotation about board X
    NEAR(imu_elevation_deg(0, 0, 1), 0, 1e-3);
    NEAR(imu_elevation_deg(0, 1, 0), 90, 1e-3);
    NEAR(crc32_calc("123456789", 9), 0xCBF43926u, 0);

    std::printf("%d checks, %d failures\n", checks, fails);
    return fails ? 1 : 0;
}
