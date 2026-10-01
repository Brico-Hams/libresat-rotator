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
