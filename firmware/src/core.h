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
