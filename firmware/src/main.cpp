// LibreSat Rotator LSR-1 — RP2040 firmware
// Easycomm II compatible (Hamlib model 202 / 204, Gpredict, SatNOGS), plus LSR "X" extensions.
// Two command ports: USB CDC (PC / Pi 4/5 over USB) and UART0 (Pi Zero 2 W on the board header).
//
// Motion: 25 kHz step generator (timer IRQ) + 500 Hz square-root velocity planner per axis.
// Closed loop: AS5600 on each motor's rear shaft detects lost steps and re-synchronises.
// Reference: AZ from the saved position (verified by the encoder) or the hall index (HOME);
//            EL from the boom accelerometer at power-up (no endstops needed).

#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <math.h>
#include "pico/stdlib.h"
#include "pico/bootrom.h"
#include "hardware/gpio.h"
#include "hardware/uart.h"
#include "hardware/adc.h"
#include "hardware/watchdog.h"
#include "hardware/sync.h"
#include "config.h"
#include "core.h"
#include "hw.h"

enum { AZ = 0, EL = 1 };
static const char *AXN[2] = {"AZ", "EL"};

static settings_t S;
static axis_cfg_t AX[2];

// ----------------------------------------------------------- step generator (IRQ)
static volatile int32_t  pos[2];          // microsteps
static volatile int32_t  vel_q16[2];      // microsteps per tick, Q16, signed
static uint32_t          acc_q16[2];
static int               dir_state[2] = {0, 0};
static const uint        PIN_STEP[2] = {PIN_STEP_AZ, PIN_STEP_EL};
static const uint        PIN_DIR[2] = {PIN_DIR_AZ, PIN_DIR_EL};
static repeating_timer_t step_timer;

#if LSR_DRIVER == EXT_STEPDIR
static const uint PIN_EN[2] = {PIN_EN_AZ, PIN_EN_EL};
static sd_axis_t   sd[2];
static sd_enable_t sd_en;

static void drivers_enable(bool on) {
    sd_enable_set(&sd_en, on, time_us_32());
    for (int a = 0; a < 2; a++) gpio_put(PIN_EN[a], on ? EXT_EN_ACTIVE : !EXT_EN_ACTIVE);
}

static bool step_isr(repeating_timer_t *) {
    uint32_t now = time_us_32();
    bool ready = sd_enable_ready(&sd_en, now);
    for (int a = 0; a < 2; a++) {
        int32_t v = vel_q16[a];
        int sgn = v >= 0 ? 1 : -1;
        bool want = false;
        if (v != 0 && ready) { acc_q16[a] += (uint32_t)(v > 0 ? v : -v); want = acc_q16[a] >= 65536u; }
        if (sd_tick(&sd[a], now, ready, sgn, want)) { acc_q16[a] -= 65536u; pos[a] += sgn; }
        gpio_put(PIN_STEP[a], sd[a].step_hi ? EXT_STEP_ACTIVE : !EXT_STEP_ACTIVE);
        if (sd[a].dir) gpio_put(PIN_DIR[a], (sd[a].dir > 0) == (EXT_DIR_POS_LEVEL != 0));
    }
    return true;
}
#else
static void drivers_enable(bool on) { gpio_put(PIN_NEN, !on); }

static bool step_isr(repeating_timer_t *) {
    gpio_put(PIN_STEP_AZ, 0); gpio_put(PIN_STEP_EL, 0);
    for (int a = 0; a < 2; a++) {
        int32_t v = vel_q16[a];
        if (v == 0) continue;
        int sgn = v > 0 ? 1 : -1;
        if (sgn != dir_state[a]) {                        // DIR set-up: change now, step next tick
            gpio_put(PIN_DIR[a], sgn > 0);
            dir_state[a] = sgn;
            continue;
        }
        acc_q16[a] += (uint32_t)(v > 0 ? v : -v);
        if (acc_q16[a] >= 65536u) {
            acc_q16[a] -= 65536u;
            gpio_put(PIN_STEP[a], 1);
            pos[a] += sgn;
        }
    }
    return true;
}
#endif

static int32_t pos_get(int a) { return pos[a]; }
static void pos_set(int a, int32_t p) { uint32_t s = save_and_disable_interrupts(); pos[a] = p; restore_interrupts(s); }

// ----------------------------------------------------------- state
typedef enum { M_IDLE, M_GOTO, M_JOG, M_HOME_FWD, M_HOME_REV, M_IDX } mode_t2;
static mode_t2 mode[2] = {M_IDLE, M_IDLE};
static float   target[2];
static plan_state_t plan[2];
static int     bl_side[2] = {1, 1};        // last direction of motion (backlash side)
static idx_t   idx[2];                     // LSR-2 index homing / backlash calibration
static pwr_t   pwr;
static bool    pwr_seen_ok = false;
static bool    referenced[2];
static bool    enc_ok[2], imu_ok[2], tmc_ok[2];
static uint16_t enc_raw_last[2];
static int32_t enc_count[2];               // unwrapped encoder counts
static int32_t enc_base[2];                // pos - enc_us at last sync
static uint32_t slips[2];
static float   imu_el_deg = NAN, tilt[2] = {NAN, NAN};
static float   vin = 0;
static gps_fix_t gps;
static uint32_t errors = 0;
static bool    drivers_on = true;
static absolute_time_t last_motion;
static bool    dirty = false;

#define E_AZ_REF   1
#define E_EL_REF   2
#define E_TMC      4
#define E_ENC      8
#define E_LOWV    16
#define E_HOME    32
#define E_PWR     64                       // LSR-2: 48 V lost (motors stopped, position saved)

static void apply_cfg(void) {
    for (int a = 0; a < 2; a++) {
        AX[a].ratio = S.ratio[a];
        AX[a].usteps_rev = S.microsteps * DEF_FULLSTEPS;
        AX[a].dir = S.dir[a] >= 0 ? 1 : -1;
        AX[a].offset_deg = S.offset[a];
        AX[a].min_deg = S.min_deg[a]; AX[a].max_deg = S.max_deg[a];
        AX[a].vmax = S.vmax[a]; AX[a].acc = S.acc[a];
        AX[a].deadband = S.deadband;
    }
}

static float raw_deg(int a) { return axis_pos_to_deg(&AX[a], pos_get(a)); }
// Controlled/reported angle: motor angle plus the backlash when the last move was in the - direction (0 = no calibration).
static float cur_deg(int a) { return mode[a] == M_IDX ? raw_deg(a) : backlash_out(raw_deg(a), bl_side[a], S.backlash[a]); }

static void set_current_deg(int a, float deg) {     // re-reference without moving
    float c = cur_deg(a) - raw_deg(a);
    AX[a].offset_deg = S.offset[a] = deg - c - (float)AX[a].dir * (float)pos_get(a) / axis_steps_per_deg(&AX[a]);
    target[a] = deg; mode[a] = M_IDLE; plan[a].v = 0; vel_q16[a] = 0;
    referenced[a] = true; dirty = true;
}

static void stop_axis(int a) {                     // decelerate to a stop (no overshoot)
    float v = plan[a].v;
    target[a] = cur_deg(a) + v * fabsf(v) / (2.0f * AX[a].acc);
    mode[a] = M_GOTO;
}
static void goto_deg(int a, float d) {
    if (a == AZ) d = az_resolve(d, mode[AZ] == M_GOTO ? target[AZ] : cur_deg(AZ), AX[AZ].min_deg, AX[AZ].max_deg);
    else d = clampf(d, AX[EL].min_deg, AX[EL].max_deg);
    target[a] = d; mode[a] = M_GOTO;
}

// ----------------------------------------------------------- encoders / closed loop
static void encoder_update(int a) {
    if (S.enc_dir[a] == 0) { enc_ok[a] = false; return; }
    uint16_t raw; uint8_t st;
    if (!as5600_read(a, &raw, &st) || !(st & 0x20)) { enc_ok[a] = false; return; }
    if (!enc_ok[a]) {                                  // (re)acquired: sync to the step counter
        enc_raw_last[a] = raw; enc_count[a] = 0; enc_ok[a] = true;
        enc_base[a] = pos_get(a);
        return;
    }
    int d = (int)raw - (int)enc_raw_last[a];
    if (d > ENC_CPR / 2) d -= ENC_CPR; else if (d < -ENC_CPR / 2) d += ENC_CPR;
    enc_raw_last[a] = raw;
    enc_count[a] += d * S.enc_dir[a];
    int32_t enc_us = (int32_t)((int64_t)enc_count[a] * AX[a].usteps_rev / ENC_CPR);
    int32_t est = enc_base[a] + enc_us;
    int32_t err = pos_get(a) - est;
    int32_t thr = AX[a].usteps_rev / 25;              // ~2 electrical cycles
    if (err > thr || err < -thr) {                     // lost steps: trust the encoder
        pos_set(a, est);
        slips[a]++;
    }
}

// ----------------------------------------------------------- planner (500 Hz)
static void planner(float dt) {
    for (int a = 0; a < 2; a++) {
        float now = cur_deg(a);
#if LSR_MODEL == 2
        if (mode[a] == M_IDX) {                         // index homing / backlash calibration (state machine in core.cpp)
            idx_tick(&idx[a], now, gpio_get(a == AZ ? PIN_HALL_AZ : PIN_HALL_EL) == IDX_SLOT_LEVEL);
            if (idx[a].ref) {
                idx[a].ref = false;
                set_current_deg(a, idx[a].home); mode[a] = M_IDX; now = idx[a].home;
                errors &= ~(a == AZ ? E_AZ_REF : E_EL_REF);
            }
            if (idx[a].st == IDX_DONE) {
                if (idx[a].cal) { S.backlash[a] = idx[a].backlash; dirty = true; }
                bl_side[a] = 1; mode[a] = M_GOTO; target[a] = idx[a].home; errors &= ~E_HOME;
            } else if (idx[a].st == IDX_FAIL) {
                mode[a] = M_GOTO; target[a] = now; errors |= E_HOME;
            } else target[a] = idx[a].target;
        }
#else
        if (mode[a] == M_HOME_FWD || mode[a] == M_HOME_REV) {
            if (!gpio_get(PIN_HALL_AZ)) {              // magnet found
                set_current_deg(AZ, S.home_az);
                mode[AZ] = M_GOTO; target[AZ] = S.home_az;
                errors &= ~(E_AZ_REF | E_HOME);
            } else if (fabsf(target[a] - now) < 0.2f) {
                if (mode[a] == M_HOME_FWD) { mode[a] = M_HOME_REV; target[a] = now - 380.0f; }
                else { mode[a] = M_GOTO; target[a] = now; errors |= E_HOME; }
            }
        }
#endif
        float tgt = target[a];
        bool homing = mode[a] == M_HOME_FWD || mode[a] == M_HOME_REV || mode[a] == M_IDX;
        if (referenced[a] || mode[a] == M_JOG || homing) {
            if (!homing) tgt = clampf(tgt, AX[a].min_deg, AX[a].max_deg);
        }
        float vmax = mode[a] == M_IDX ? idx[a].vmax : (homing ? 8.0f : AX[a].vmax);
        float v = (mode[a] == M_IDLE) ? 0.0f : plan_step(&plan[a], tgt - now, vmax, AX[a].acc, dt, AX[a].deadband);
        if (mode[a] == M_GOTO && v == 0.0f && fabsf(tgt - now) <= AX[a].deadband) mode[a] = M_IDLE;
        float spt = v * axis_steps_per_deg(&AX[a]) * (float)AX[a].dir / (float)STEP_ISR_HZ;   // steps per tick
        vel_q16[a] = drivers_on ? (int32_t)lroundf(spt * 65536.0f) : 0;
        if (v != 0.0f) { last_motion = get_absolute_time(); bl_side[a] = v > 0.0f ? 1 : -1; }
    }
}

// ----------------------------------------------------------- IMUs
static void imu_update(void) {
    float x, y, z;
    if (imu_ok[EL] && mpu_read(EL, &x, &y, &z)) {
        float raw = imu_elevation_deg(x, y, z);
        float e = S.imu_el_dir * (raw - S.imu_el_zero);
        while (e < -90.0f) e += 360.0f; while (e >= 270.0f) e -= 360.0f;
        imu_el_deg = isnan(imu_el_deg) ? e : imu_el_deg + 0.2f * (e - imu_el_deg);
    }
    if (imu_ok[AZ] && mpu_read(AZ, &x, &y, &z)) {
        float roll = atan2f(y, z) * 57.29578f - S.tilt_zero[0];
        float pitch = atan2f(-x, sqrtf(y * y + z * z)) * 57.29578f - S.tilt_zero[1];
        tilt[0] = roll; tilt[1] = pitch;
    }
}

// ----------------------------------------------------------- persistence of the position
static void save_position(void) {
    S.last_pos[AZ] = pos_get(AZ); S.last_pos[EL] = pos_get(EL);
    S.last_enc[AZ] = enc_raw_last[AZ]; S.last_enc[EL] = enc_raw_last[EL];
    S.last_valid = referenced[AZ] ? 1 : 0;
    S.reserved[1] = (bl_side[AZ] < 0 ? 1 : 0) | (bl_side[EL] < 0 ? 2 : 0);    // backlash side at standstill
    settings_save(&S);
    dirty = false;
}

static void restore_position(void) {
    for (int a = 0; a < 2; a++) bl_side[a] = (S.reserved[1] >> a & 1) ? -1 : 1;
    // AZ (and EL without IMU): accept the saved position if the encoder still reads the same angle
    for (int a = 0; a < 2; a++) {
        referenced[a] = false;
        if (!S.last_valid) continue;
        uint16_t raw; uint8_t st;
        if (S.enc_dir[a] != 0 && as5600_read(a, &raw, &st) && (st & 0x20)) {
            int d = (int)raw - (int)S.last_enc[a];
            if (d > ENC_CPR / 2) d -= ENC_CPR; else if (d < -ENC_CPR / 2) d += ENC_CPR;
            if (abs(d) < 64) {
                pos_set(a, S.last_pos[a] + d * S.enc_dir[a] * AX[a].usteps_rev / ENC_CPR);
                referenced[a] = true;
            }
        } else if (S.enc_dir[a] == 0) {               // no encoder: trust the saved value
            pos_set(a, S.last_pos[a]); referenced[a] = true;
        }
    }
    if (S.use_imu_el && imu_ok[EL]) {                  // elevation from gravity
        for (int i = 0; i < 40; i++) { imu_update(); sleep_ms(20); }
        if (!isnan(imu_el_deg)) {
            float e = imu_el_deg;
            pos_set(EL, axis_deg_to_pos(&AX[EL], e));
            referenced[EL] = true;
        }
    }
    for (int a = 0; a < 2; a++) { target[a] = cur_deg(a); mode[a] = M_IDLE; }
    if (!referenced[AZ]) errors |= E_AZ_REF;
    if (!referenced[EL]) errors |= E_EL_REF;
}

// ----------------------------------------------------------- LSR-2: index homing, calibration, power loss
#if LSR_MODEL == 2
static void start_index(bool cal) {
    for (int a = 0; a < 2; a++) {
        bool slot = gpio_get(a == AZ ? PIN_HALL_AZ : PIN_HALL_EL) == IDX_SLOT_LEVEL;
        idx_start(&idx[a], cal, AX[a].min_deg, AX[a].max_deg, a == AZ ? S.home_az : S.home_el, raw_deg(a), slot);
        plan[a].v = 0; vel_q16[a] = 0; mode[a] = M_IDX;
    }
}

static void power_lost(void) {                        // 48 V gone: stop at once (less load on the dying rail), keep the position
    for (int a = 0; a < 2; a++) { vel_q16[a] = 0; plan[a].v = 0; mode[a] = M_IDLE; target[a] = cur_deg(a); }
    drivers_on = false; drivers_enable(false);
    save_position();
    errors |= E_PWR;
}

static void power_back(void) { drivers_on = true; drivers_enable(true); errors &= ~E_PWR; }
#endif

// ----------------------------------------------------------- output helpers
typedef void (*out_fn)(const char *);
static void out_usb(const char *s) { fputs(s, stdout); fflush(stdout); }
static void out_uart(const char *s) { uart_puts(uart0, s); }

static float az_report(float d) { d = fmodf(d, 360.0f); if (d < 0) d += 360.0f; return d; }

typedef struct { const char *key; float *f; int32_t *i; const char *help; } conf_t;
static conf_t CONF[] = {
    {"ratio_az", &S.ratio[0], NULL, "gear ratio AZ"}, {"ratio_el", &S.ratio[1], NULL, "gear ratio EL"},
    {"usteps", NULL, &S.microsteps, "microsteps (8/16/32/64)"},
    {"dir_az", NULL, &S.dir[0], "+1/-1"}, {"dir_el", NULL, &S.dir[1], "+1/-1"},
    {"vmax_az", &S.vmax[0], NULL, "deg/s"}, {"vmax_el", &S.vmax[1], NULL, "deg/s"},
    {"acc_az", &S.acc[0], NULL, "deg/s2"}, {"acc_el", &S.acc[1], NULL, "deg/s2"},
    {"min_az", &S.min_deg[0], NULL, "deg"}, {"max_az", &S.max_deg[0], NULL, "deg (cable wrap)"},
    {"min_el", &S.min_deg[1], NULL, "deg"}, {"max_el", &S.max_deg[1], NULL, "deg (180 = flip)"},
    {"irun_az", NULL, &S.irun_ma[0], "mA rms"}, {"irun_el", NULL, &S.irun_ma[1], "mA rms"},
    {"ihold", NULL, &S.ihold_pct, "% of run current"},
    {"deadband", &S.deadband, NULL, "deg"},
    {"park_az", &S.park_az, NULL, "deg"}, {"park_el", &S.park_el, NULL, "deg"},
    {"home_az", &S.home_az, NULL, "azimuth of the index (internal frame)"}, {"home_el", &S.home_el, NULL, "elevation of the index edge"},
    {"backlash_az", &S.backlash[0], NULL, "deg, set by XCAL BACKLASH"}, {"backlash_el", &S.backlash[1], NULL, "deg, set by XCAL BACKLASH"},
    {"enc_az", NULL, &S.enc_dir[0], "encoder +1/-1/0=off"}, {"enc_el", NULL, &S.enc_dir[1], "encoder +1/-1/0=off"},
    {"imu_el", NULL, &S.use_imu_el, "1 = EL referenced by the boom IMU"},
    {"imu_el_dir", &S.imu_el_dir, NULL, "+1/-1"}, {"imu_el_zero", &S.imu_el_zero, NULL, "raw IMU angle at EL 0"},
};

static void configure_drivers(void) {
#if LSR_DRIVER == TMC2209_UART
    for (int a = 0; a < 2; a++) {
        tmc_ok[a] = tmc_configure((uint8_t)a, S.irun_ma[a], S.ihold_pct, S.microsteps, false);
    }
    if (!tmc_ok[0] || !tmc_ok[1]) errors |= E_TMC; else errors &= ~E_TMC;
#else
    errors &= ~E_TMC;                       // no UART driver: tmc=0,0 in XS means "not applicable"
#endif
}

static void status_line(out_fn out) {
    char b[400];
    snprintf(b, sizeof(b),
        "XS az=%.2f el=%.2f taz=%.2f tel=%.2f vaz=%.2f vel=%.2f mode=%d,%d ref=%d,%d err=%lu vin=%.2f "
        "enc=%d,%d slips=%lu,%lu tmc=%d,%d imu_el=%.2f tilt=%.2f,%.2f "
        "gps=%d,%d,%.6f,%.6f,%.1f utc=%04d-%02d-%02dT%02d:%02d:%05.2fZ up=%lu\r\n",
        cur_deg(AZ), cur_deg(EL), target[AZ], target[EL], plan[AZ].v, plan[EL].v, mode[AZ], mode[EL],
        referenced[AZ], referenced[EL], (unsigned long)errors, vin, enc_ok[AZ], enc_ok[EL],
        (unsigned long)slips[AZ], (unsigned long)slips[EL], tmc_ok[AZ], tmc_ok[EL],
        imu_el_deg, tilt[0], tilt[1], gps.valid, gps.sats, gps.lat, gps.lon, gps.alt,
        gps.year, gps.month, gps.day, gps.hour, gps.min, gps.sec,
        (unsigned long)(to_ms_since_boot(get_absolute_time()) / 1000));
    out(b);
}

static void handle(const char *line, out_fn out) {
    cmd_t c[8];
    int n = parse_line(line, c, 8);
    char b[200];
    bool want_az = false, want_el = false;
    for (int i = 0; i < n; i++) {
        switch (c[i].kind) {
        case CMD_GET_AZ: want_az = true; break;
        case CMD_GET_EL: want_el = true; break;
        case CMD_SET_AZ: goto_deg(AZ, c[i].value); break;
        case CMD_SET_EL: goto_deg(EL, c[i].value); break;
        case CMD_STOP_AZ: stop_axis(AZ); break;
        case CMD_STOP_EL: stop_axis(EL); break;
        case CMD_MOVE_L: mode[AZ] = M_JOG; target[AZ] = AX[AZ].min_deg; break;
        case CMD_MOVE_R: mode[AZ] = M_JOG; target[AZ] = AX[AZ].max_deg; break;
        case CMD_MOVE_D: mode[EL] = M_JOG; target[EL] = AX[EL].min_deg; break;
        case CMD_MOVE_U: mode[EL] = M_JOG; target[EL] = AX[EL].max_deg; break;
        case CMD_VERSION: out("VE" FW_NAME " " FW_VERSION "\r\n"); break;
        case CMD_STATUS: {
            int gs = (mode[AZ] == M_IDLE && mode[EL] == M_IDLE) ? 1 : 2;
            if (errors) gs |= 8;
            snprintf(b, sizeof(b), "GS%d\r\n", gs); out(b); break; }
        case CMD_ERROR: snprintf(b, sizeof(b), "GE%lu\r\n", (unsigned long)errors); out(b); break;
        case CMD_HOME:
#if LSR_MODEL == 2
            start_index(false);                          // both axes: seek the photo-interrupter slot, reference on its lower edge
#else
            mode[AZ] = M_HOME_FWD; target[AZ] = cur_deg(AZ) + 380.0f;
#endif
            break;
        case CMD_PARK: goto_deg(AZ, S.park_az); goto_deg(EL, S.park_el); break;
        case CMD_XPOS:                                   // host-planned absolute azimuth (cable wrap chosen by the host)
            if (c[i].nvals >= 1) { target[AZ] = clampf(c[i].value, AX[AZ].min_deg, AX[AZ].max_deg); mode[AZ] = M_GOTO; }
            if (c[i].nvals >= 2) { target[EL] = clampf(c[i].value2, AX[EL].min_deg, AX[EL].max_deg); mode[EL] = M_GOTO; }
            break;
        case CMD_XSTATUS: status_line(out); break;
        case CMD_XRAW: {                                 // raw sensor readings for the head-side calibration (Phase 8)
            float v[2][3];
            for (int a = 0; a < 2; a++) if (!(imu_ok[a] && mpu_read((uint8_t)a, &v[a][0], &v[a][1], &v[a][2]))) v[a][0] = v[a][1] = v[a][2] = NAN;
            float eo[2];
            for (int a = 0; a < 2; a++) eo[a] = enc_ok[a] ? axis_enc_to_deg(&AX[a], enc_base[a], enc_count[a], ENC_CPR) : NAN;
            int s0 = gpio_get(PIN_HALL_AZ) == IDX_SLOT_LEVEL, s1 = gpio_get(PIN_HALL_EL) == IDX_SLOT_LEVEL;
            snprintf(b, sizeof(b), "XR accb=%.4f,%.4f,%.4f accl=%.4f,%.4f,%.4f mag=na enc=%.3f,%.3f step=%.3f,%.3f idx=%d,%d bl=%.3f,%.3f\r\n",
                     v[AZ][0], v[AZ][1], v[AZ][2], v[EL][0], v[EL][1], v[EL][2], eo[AZ], eo[EL], raw_deg(AZ), raw_deg(EL),
                     s0, s1, S.backlash[AZ], S.backlash[EL]);
            out(b); break; }
        case CMD_XSAVE: save_position(); out("XW ok\r\n"); break;
        case CMD_XENABLE:
            drivers_on = c[i].value != 0.0f; drivers_enable(drivers_on);
            if (!drivers_on && S.enc_dir[AZ] == 0) { referenced[AZ] = false; errors |= E_AZ_REF; }   // with an encoder the position keeps being tracked
            snprintf(b, sizeof(b), "XE %d\r\n", drivers_on); out(b); break;
        case CMD_XBOOT: out("XB rebooting to USB bootloader\r\n"); sleep_ms(50); reset_usb_boot(0, 0); break;
        case CMD_XGPS:
            snprintf(b, sizeof(b), "XG valid=%d q=%d sats=%d lat=%.6f lon=%.6f alt=%.1f utc=%04d-%02d-%02dT%02d:%02d:%05.2fZ n=%lu\r\n",
                     gps.valid, gps.fix_quality, gps.sats, gps.lat, gps.lon, gps.alt, gps.year, gps.month, gps.day,
                     gps.hour, gps.min, gps.sec, (unsigned long)gps.updates);
            out(b); break;
        case CMD_XTMC:
#if LSR_DRIVER == EXT_STEPDIR
            out("XT n/a ext driver\r\n");
            break;
#endif
            for (int a = 0; a < 2; a++) {
                uint32_t ds = 0, cnt = 0; bool ok = tmc_read((uint8_t)a, 0x6F, &ds) && tmc_read((uint8_t)a, 0x02, &cnt);
                snprintf(b, sizeof(b), "XT %s ok=%d drv_status=0x%08lx ifcnt=%lu ot=%d otpw=%d s2g=%d ola=%d olb=%d\r\n", AXN[a], ok,
                         (unsigned long)ds, (unsigned long)cnt, (int)(ds >> 1 & 1), (int)(ds & 1), (int)((ds >> 2 & 3) != 0),
                         (int)(ds >> 6 & 1), (int)(ds >> 7 & 1));
                out(b);
            }
            break;
        case CMD_XCONF_GET:
            for (size_t k = 0; k < sizeof(CONF) / sizeof(CONF[0]); k++) {
                if (c[i].key[0] && c[i].key[0] != '?' && strcmp(c[i].key, CONF[k].key)) continue;
                if (CONF[k].f) snprintf(b, sizeof(b), "XC %s=%.4f  # %s\r\n", CONF[k].key, *CONF[k].f, CONF[k].help);
                else snprintf(b, sizeof(b), "XC %s=%ld  # %s\r\n", CONF[k].key, (long)*CONF[k].i, CONF[k].help);
                out(b);
            }
            break;
        case CMD_XCONF_SET: {
            bool found = false;
            for (size_t k = 0; k < sizeof(CONF) / sizeof(CONF[0]); k++) if (!strcmp(c[i].key, CONF[k].key)) {
                if (CONF[k].f) *CONF[k].f = c[i].value; else *CONF[k].i = (int32_t)lroundf(c[i].value);
                found = true;
            }
            if (found) {
                float keep[2] = {cur_deg(AZ), cur_deg(EL)};
                apply_cfg();
                dirty = true;
                for (int a = 0; a < 2; a++) if (referenced[a]) set_current_deg(a, keep[a]);   // ratio/dir changes keep the angle
                if (!strncmp(c[i].key, "irun", 4) || !strcmp(c[i].key, "ihold") || !strcmp(c[i].key, "usteps")) configure_drivers();
                snprintf(b, sizeof(b), "XC ok %s\r\n", c[i].key);
            } else snprintf(b, sizeof(b), "XC unknown key '%s' (XC? lists keys)\r\n", c[i].key);
            out(b);
            break; }
        case CMD_XCAL:
            if (!strcmp(c[i].key, "AZ") && c[i].sval[0]) { set_current_deg(AZ, c[i].value); errors &= ~E_AZ_REF; }
            else if (!strcmp(c[i].key, "EL") && c[i].sval[0]) { set_current_deg(EL, c[i].value); errors &= ~E_EL_REF; }
            else if (!strcmp(c[i].key, "ELIMU")) {          // IMU now reads the current elevation
                float x, y, z;
                if (imu_ok[EL] && mpu_read(EL, &x, &y, &z)) {
                    S.imu_el_zero = imu_elevation_deg(x, y, z) - cur_deg(EL) / S.imu_el_dir; imu_el_deg = NAN; dirty = true;
                }
            } else if (!strcmp(c[i].key, "LEVEL")) {        // base IMU: current attitude = level
                float x, y, z;
                if (imu_ok[AZ] && mpu_read(AZ, &x, &y, &z)) {
                    S.tilt_zero[0] = atan2f(y, z) * 57.29578f; S.tilt_zero[1] = atan2f(-x, sqrtf(y * y + z * z)) * 57.29578f; dirty = true;
                }
            } else if (!strcmp(c[i].key, "HOMEAZ")) { S.home_az = cur_deg(AZ); dirty = true; }
            else if (!strcmp(c[i].key, "HOMEEL")) { S.home_el = cur_deg(EL); dirty = true; }
#if LSR_MODEL == 2
            else if (!strcmp(c[i].key, "BACKLASH")) {       // one-off: reference on the index, measure the backlash, store it in flash
                start_index(true); out("XCAL BACKLASH started (both axes, wait for mode=0,0 then XW)\r\n"); break;
            }
#endif
            else { out("XCAL keys: AZ=<deg> EL=<deg> ELIMU LEVEL HOMEAZ HOMEEL BACKLASH\r\n"); break; }
            snprintf(b, sizeof(b), "XCAL ok az=%.2f el=%.2f\r\n", cur_deg(AZ), cur_deg(EL)); out(b);
            break;
        case CMD_XHELP:
            out("Easycomm: AZ EL | AZ<deg> EL<deg> | SA SE | ML MR MU MD | VE GS GE | HOME PARK\r\n"
                "LSR: XP az el (absolute) | XS status | XR raw sensors | XC? | XC key=val | XW save | XCAL AZ=..|EL=..|ELIMU|LEVEL|HOMEAZ|HOMEEL|BACKLASH | XE 0/1 | XG | XT | XB\r\n");
            break;
        default: break;
        }
    }
    if (want_az && want_el) { snprintf(b, sizeof(b), "AZ%.1f EL%.1f\r\n", az_report(cur_deg(AZ)), cur_deg(EL)); out(b); }
    else if (want_az) { snprintf(b, sizeof(b), "AZ%.1f\r\n", az_report(cur_deg(AZ))); out(b); }
    else if (want_el) { snprintf(b, sizeof(b), "EL%.1f\r\n", cur_deg(EL)); out(b); }
}

// ----------------------------------------------------------- line input
typedef struct { char buf[128]; int n; } linebuf_t;
static void feed(linebuf_t *lb, int ch, out_fn out) {
    if (ch == '\r' || ch == '\n' || ch == ';') {
        if (lb->n) { lb->buf[lb->n] = 0; handle(lb->buf, out); lb->n = 0; }
    } else if (lb->n < (int)sizeof(lb->buf) - 1) lb->buf[lb->n++] = (char)ch;
}

// ----------------------------------------------------------- main
int main(void) {
    stdio_usb_init();
    uart_init(uart0, PI_BAUD);
    gpio_set_function(PIN_PI_TX, GPIO_FUNC_UART); gpio_set_function(PIN_PI_RX, GPIO_FUNC_UART);

    for (int a = 0; a < 2; a++) { gpio_init(PIN_STEP[a]); gpio_set_dir(PIN_STEP[a], GPIO_OUT); gpio_init(PIN_DIR[a]); gpio_set_dir(PIN_DIR[a], GPIO_OUT); }
    gpio_init(PIN_NEN); gpio_set_dir(PIN_NEN, GPIO_OUT); gpio_put(PIN_NEN, 1);
#if LSR_DRIVER == EXT_STEPDIR
    for (int a = 0; a < 2; a++) { gpio_init(PIN_EN[a]); gpio_set_dir(PIN_EN[a], GPIO_OUT); gpio_put(PIN_EN[a], !EXT_EN_ACTIVE); }
    sd_init(&sd[0]); sd_init(&sd[1]);
#endif
    gpio_init(PIN_LED); gpio_set_dir(PIN_LED, GPIO_OUT);
    gpio_init(PIN_BTN); gpio_set_dir(PIN_BTN, GPIO_IN); gpio_pull_up(PIN_BTN);
    gpio_init(PIN_HALL_AZ); gpio_set_dir(PIN_HALL_AZ, GPIO_IN); gpio_pull_up(PIN_HALL_AZ);
    gpio_init(PIN_HALL_EL); gpio_set_dir(PIN_HALL_EL, GPIO_IN); gpio_pull_up(PIN_HALL_EL);
    gpio_init(PIN_PWRFAIL); gpio_set_dir(PIN_PWRFAIL, GPIO_IN); gpio_pull_up(PIN_PWRFAIL);
    adc_init(); adc_gpio_init(PIN_VSENSE); adc_select_input(ADC_VSENSE);

    if (!settings_load(&S)) settings_defaults(&S);
    apply_cfg();
    sensors_init();
    gps_init();
#if LSR_DRIVER == TMC2209_UART
    tmc_init();
#endif
    sleep_ms(300);                       // let VM settle before talking to the drivers
    configure_drivers();
    imu_ok[EL] = mpu_init(EL);
    imu_ok[AZ] = mpu_init(AZ);
    restore_position();
    for (int a = 0; a < 2; a++) encoder_update(a);
    drivers_enable(true);
    add_repeating_timer_us(-(1000000 / STEP_ISR_HZ), step_isr, NULL, &step_timer);
    watchdog_enable(2000, true);

    linebuf_t lb_usb = {{0}, 0}, lb_uart = {{0}, 0};
    absolute_time_t t_plan = get_absolute_time(), t_imu = t_plan, t_slow = t_plan;
    last_motion = t_plan;
    uint32_t btn_down_ms = 0, tick = 0;

    while (true) {
        watchdog_update();
        int ch;
        while ((ch = getchar_timeout_us(0)) != PICO_ERROR_TIMEOUT) feed(&lb_usb, ch, out_usb);
        while (uart_is_readable(uart0)) feed(&lb_uart, uart_getc(uart0), out_uart);
        gps_poll(&gps);
#if LSR_MODEL == 2
        {   // every loop pass (not the 10 Hz tick): the flash write must start within a few ms of the loss
            bool loss = gpio_get(PIN_PWRFAIL) == PWR_LOSS_LEVEL;
            if (!loss) pwr_seen_ok = true;
            if (pwr_seen_ok) {
                bool was_lost = pwr.lost;
                if (pwr_tick(&pwr, time_us_32(), loss)) power_lost();
                else if (was_lost && !pwr.lost) power_back();
            }
        }
#endif

        absolute_time_t now = get_absolute_time();
        if (absolute_time_diff_us(t_plan, now) >= 1000000 / PLAN_HZ) {
            float dt = absolute_time_diff_us(t_plan, now) / 1e6f; t_plan = now;
            encoder_update(AZ); encoder_update(EL);
            planner(dt);
        }
        if (absolute_time_diff_us(t_imu, now) >= 1000000 / IMU_HZ) { t_imu = now; imu_update(); }
        if (absolute_time_diff_us(t_slow, now) >= 100000) {          // 10 Hz housekeeping
            t_slow = now; tick++;
            vin = adc_read() * 3.3f / 4095.0f * 11.0f;
            if (vin < 8.5f && vin > 1.0f) errors |= E_LOWV; else errors &= ~E_LOWV;
            if ((!enc_ok[AZ] && S.enc_dir[AZ]) || (!enc_ok[EL] && S.enc_dir[EL])) errors |= E_ENC; else errors &= ~E_ENC;
            // button: short = stop, long (2 s) = park
            if (!gpio_get(PIN_BTN)) { btn_down_ms += 100; if (btn_down_ms == 2000) handle("PARK", out_usb); }
            else { if (btn_down_ms > 0 && btn_down_ms < 2000) { stop_axis(AZ); stop_axis(EL); } btn_down_ms = 0; }
            // LED: slow = idle, fast = moving, double flash = error
            bool moving = mode[AZ] != M_IDLE || mode[EL] != M_IDLE;
            bool led = errors ? (tick % 10 == 0 || tick % 10 == 2) : (moving ? (tick & 1) : (tick % 10 < 5));
            gpio_put(PIN_LED, led);
            // save the position after 3 s at rest (the flash write pauses stepping for ~50 ms)
            if (!moving && absolute_time_diff_us(last_motion, now) > 3000000 &&
                (dirty || S.last_pos[AZ] != pos_get(AZ) || S.last_pos[EL] != pos_get(EL))) save_position();
        }
    }
}
