// Hardware-independent logic (compiled into the firmware AND the host unit tests).
#pragma once
#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>

// ------------------------------------------------------------------ axis kinematics
typedef struct {
    float ratio;          // gearbox reduction
    int   usteps_rev;     // microsteps per motor revolution
    int   dir;            // +1 / -1 (mechanical sense)
    float offset_deg;     // angle when pos == 0
    float min_deg, max_deg;
    float vmax, acc;      // deg/s, deg/s^2
    float deadband;       // deg
} axis_cfg_t;

float   axis_steps_per_deg(const axis_cfg_t *c);
float   axis_pos_to_deg(const axis_cfg_t *c, int32_t pos);
int32_t axis_deg_to_pos(const axis_cfg_t *c, float deg);

// Choose the physical azimuth for a requested one. 0..360 requests are mapped to the
// equivalent angle (a, a+360, a-360) that is inside [min,max] and closest to `cur`.
// Requests outside 0..360 are taken as absolute (explicit wrap selection by the host).
float   az_resolve(float req, float cur, float min_deg, float max_deg);
float   clampf(float v, float lo, float hi);

// ------------------------------------------------------------------ model profiles (LSR_MODEL 1 | 2)
// Wire/internal azimuth frame: LSR-1 0..450; LSR-2 0..720 = user -360..+360 (internal = user + az_user_offset).
typedef struct {
    const char *name;
    float ratio;
    int   microsteps;
    float az_min, az_max;       // internal frame
    float az_user_offset;
    float el_min, el_max;
    float vmax_az, vmax_el;     // deg/s
    float acc_az, acc_el;       // deg/s^2
    bool  flip;                 // EL beyond 90 used for "flip" passes
} lsr_model_t;

const lsr_model_t *lsr_model(int model);               // 1 or 2 (anything else = 1)
float lsr_az_to_internal(const lsr_model_t *m, float user_deg);
float lsr_az_to_user(const lsr_model_t *m, float internal_deg);
float lsr_clamp_az_user(const lsr_model_t *m, float user_deg);   // result in the user frame
float lsr_clamp_el(const lsr_model_t *m, float deg);

// ------------------------------------------------------------------ external STEP/DIR drivers (DM542, TMC5160)
// Limits (DM542 datasheet, VERIFY): STEP pulse >= 2.5 us, DIR set-up >= 5 us before the first STEP edge,
// ENA must be settled >= 200 ms before the first STEP. Values below are rounded up to whole microseconds.
#define SD_PULSE_MIN_US     3u
#define SD_DIR_SETUP_US     5u
#define SD_ENABLE_SETTLE_US 200000u

typedef struct {
    int      dir;               // last DIR level driven: -1, 0 = never, +1
    bool     step_hi;
    uint32_t t_dir, t_rise;     // timestamps in us (wrap-safe)
} sd_axis_t;

void sd_init(sd_axis_t *s);
// Call every tick. `want_step` requests one pulse in direction `want_dir` (+1/-1). `ready` = enable settled.
// Lowers a pulse after >= SD_PULSE_MIN_US. Returns true only on the tick the STEP rising edge is issued;
// a direction change first moves DIR and defers the step until SD_DIR_SETUP_US has elapsed.
bool sd_tick(sd_axis_t *s, uint32_t now_us, bool ready, int want_dir, bool want_step);

typedef struct { bool on; uint32_t t_on; } sd_enable_t;
void sd_enable_set(sd_enable_t *e, bool on, uint32_t now_us);
bool sd_enable_ready(const sd_enable_t *e, uint32_t now_us);   // on and settled

// ------------------------------------------------------------------ index homing (slotted disc + photo-interrupter) and backlash
// One slot per output revolution. The state machine runs in the axis angle frame (it only needs relative angles) and is
// driven by the planner: target/vmax are its outputs, `slot` = the slot is in the beam.
//   SEEK1/SEEK2 sweep (6 deg/s) to the farther limit, then the other, until the slot shows; CLEAR backs out below the lower edge;
//   MARGIN goes 2 deg further; APPR comes back at 1 deg/s and stops on the lower edge (high->low): `ref` asks the caller to set
//   angle := home (nearest multiple of 360 deg to the old estimate inside the limits). With `cal`: BL_IN goes 2 deg into the slot,
//   BL_BACK returns to the same edge (low->high); edge_fwd - angle there = backlash (deg of output). The slot must be >= 4 deg wide
//   and its edges >= 3 deg inside the limits.
#define IDX_SEEK_DPS   6.0f
#define IDX_CLEAR_DPS  4.0f
#define IDX_FINE_DPS   1.0f
#define IDX_MARGIN_DEG 2.0f
#define IDX_PERIOD_DEG 360.0f
typedef enum { IDX_IDLE = 0, IDX_SEEK1, IDX_SEEK2, IDX_CLEAR, IDX_MARGIN, IDX_APPR, IDX_BL_IN, IDX_BL_BACK, IDX_DONE, IDX_FAIL } idx_state_t;
typedef struct {
    idx_state_t st;
    bool  cal, ref;
    float lo, hi, far_lim, near_lim;
    float home_base, home;      // slot edge angle (one turn) and the resolved one
    float target, vmax;         // outputs for the planner
    float edge_fwd, backlash;   // backlash in deg (output)
} idx_t;

void  idx_start(idx_t *x, bool cal, float lo, float hi, float home, float now, bool slot);
void  idx_tick(idx_t *x, float now, bool slot);
float idx_resolve(float est, float home, float period, float lo, float hi);
// Output angle from the motor-side angle: after a move in the - direction the output lags by the backlash.
float backlash_out(float motor_deg, int side, float backlash_deg);

// ------------------------------------------------------------------ 48 V power-loss detect (LSR-2)
// Feed the raw "48 V gone" level every loop. Returns true once, when the loss has lasted PWR_DEBOUNCE_US (save the position now).
// The state clears (returns false) when the power has been back for the same time, so a glitch re-arms it.
#define PWR_DEBOUNCE_US 5000u
typedef struct { bool lost, cand; uint32_t t0; } pwr_t;
bool pwr_tick(pwr_t *p, uint32_t now_us, bool raw_loss);

// ------------------------------------------------------------------ velocity planner
// Square-root (trapezoidal) profile: v_des = sign(e) * min(vmax, sqrt(2 a |e|)), slewed by a.
typedef struct { float v; } plan_state_t;
float   plan_step(plan_state_t *s, float err_deg, float vmax, float acc, float dt, float deadband);

// ------------------------------------------------------------------ Easycomm II / LSR commands
typedef enum {
    CMD_NONE = 0, CMD_GET_AZ, CMD_GET_EL, CMD_SET_AZ, CMD_SET_EL, CMD_STOP_AZ, CMD_STOP_EL,
    CMD_MOVE_L, CMD_MOVE_R, CMD_MOVE_U, CMD_MOVE_D, CMD_VERSION, CMD_STATUS, CMD_ERROR,
    CMD_HOME, CMD_PARK, CMD_XSTATUS, CMD_XCONF_SET, CMD_XCONF_GET, CMD_XSAVE, CMD_XCAL,
    CMD_XGPS, CMD_XTMC, CMD_XBOOT, CMD_XHELP, CMD_XENABLE, CMD_XPOS, CMD_UNKNOWN
} cmd_kind_t;

typedef struct {
    cmd_kind_t kind;
    float      value;
    float      value2;
    int        nvals;
    char       key[24];
    char       sval[32];
} cmd_t;

// Parse one line into up to `max` commands. Returns the count.
// "AZ EL" -> {GET_AZ, GET_EL}; "AZ123.4 EL45" -> {SET_AZ, SET_EL}; unknown tokens (UP000 XXX ...) ignored.
int parse_line(const char *line, cmd_t *out, int max);

// ------------------------------------------------------------------ NMEA
typedef struct {
    bool  valid;            // RMC status A
    int   fix_quality;      // GGA
    int   sats;
    double lat, lon;        // degrees
    float alt;              // m
    int   year, month, day, hour, min;
    float sec;
    uint32_t updates;
} gps_fix_t;

// Feed one complete NMEA sentence (starting with '$', without CR/LF). Returns true if used.
bool nmea_parse(const char *s, gps_fix_t *fix);
bool nmea_checksum_ok(const char *s);

// ------------------------------------------------------------------ misc
uint8_t tmc_crc8(const uint8_t *data, size_t len);
float   imu_elevation_deg(float ax, float ay, float az);   // boom IMU, board X along the stub
uint32_t crc32_calc(const void *data, size_t len);
