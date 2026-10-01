// Hardware-independent logic: kinematics, planner, command and NMEA parsers, CRCs.
#include "core.h"
#include <math.h>
#include <string.h>
#include <stdlib.h>
#include <ctype.h>

// ------------------------------------------------------------------ kinematics
float axis_steps_per_deg(const axis_cfg_t *c) { return (float)c->usteps_rev * c->ratio / 360.0f; }

float axis_pos_to_deg(const axis_cfg_t *c, int32_t pos) {
    return c->offset_deg + (float)c->dir * (float)pos / axis_steps_per_deg(c);
}

int32_t axis_deg_to_pos(const axis_cfg_t *c, float deg) {
    return (int32_t)lroundf((deg - c->offset_deg) * axis_steps_per_deg(c) * (float)c->dir);
}

float clampf(float v, float lo, float hi) { return v < lo ? lo : (v > hi ? hi : v); }

float az_resolve(float req, float cur, float min_deg, float max_deg) {
    if (req < 0.0f || req > 360.0f)              // explicit absolute (wrap chosen by the host)
        return clampf(req, min_deg, max_deg);
    float best = NAN, bestd = 1e9f;
    for (int k = -1; k <= 1; k++) {
        float a = req + 360.0f * (float)k;
        if (a < min_deg - 1e-3f || a > max_deg + 1e-3f) continue;
        float d = fabsf(a - cur);
        if (d < bestd) { bestd = d; best = a; }
    }
    if (isnan(best)) best = clampf(req, min_deg, max_deg);
    return best;
}

// ------------------------------------------------------------------ planner
float plan_step(plan_state_t *s, float err, float vmax, float acc, float dt, float deadband) {
    float v_des = 0.0f;
    float ae = fabsf(err);
    if (ae > deadband) {
        // stop distance aware: v = sqrt(2 a (|e| - deadband/2)), capped
        float vs = sqrtf(2.0f * acc * (ae - 0.5f * deadband));
        v_des = (err > 0 ? 1.0f : -1.0f) * fminf(vmax, vs);
    } else if (fabsf(s->v) < acc * dt * 2.0f) {
        s->v = 0.0f;
        return 0.0f;
    }
    float dv = v_des - s->v, lim = acc * dt;
    if (dv > lim) dv = lim; else if (dv < -lim) dv = -lim;
    s->v += dv;
    return s->v;
}

// ------------------------------------------------------------------ commands
static int ieq(const char *a, const char *b) {
    while (*a && *b) { if (toupper((unsigned char)*a) != toupper((unsigned char)*b)) return 0; a++; b++; }
    return *a == 0 && *b == 0;
}
static int istarts(const char *s, const char *p) {
    while (*p) { if (toupper((unsigned char)*s) != toupper((unsigned char)*p)) return 0; s++; p++; }
    return 1;
}
static int is_number(const char *s) {
    if (!*s) return 0;
    char *end; strtod(s, &end);
    return *end == 0;
}

int parse_line(const char *line, cmd_t *out, int max) {
    char buf[128];
    strncpy(buf, line, sizeof(buf) - 1); buf[sizeof(buf) - 1] = 0;
    int n = 0;
    // extended commands take the whole line
    char *p = buf; while (*p == ' ' || *p == '\t') p++;
    if ((p[0] == 'X' || p[0] == 'x') && n < max) {
        cmd_t *c = &out[n]; memset(c, 0, sizeof(*c));
        char *arg = p + 2; while (*arg == ' ') arg++;
        if (istarts(p, "XS")) c->kind = CMD_XSTATUS;
        else if (istarts(p, "XW")) c->kind = CMD_XSAVE;
        else if (istarts(p, "XG")) c->kind = CMD_XGPS;
        else if (istarts(p, "XT")) c->kind = CMD_XTMC;
        else if (istarts(p, "XB")) c->kind = CMD_XBOOT;
        else if (istarts(p, "XH")) c->kind = CMD_XHELP;
        else if (istarts(p, "XE")) { c->kind = CMD_XENABLE; c->value = (float)atof(arg); }
        else if (istarts(p, "XP")) {            // XP <az> [<el>] : absolute position, no wrap resolution
            char *e1; c->kind = CMD_XPOS;
            c->value = strtof(arg, &e1); c->nvals = (e1 != arg);
            char *e2; c->value2 = strtof(e1, &e2); if (e2 != e1) c->nvals = 2;
        }
        else if (istarts(p, "XCAL")) {
            c->kind = CMD_XCAL; arg = p + 4; while (*arg == ' ') arg++;
            char *eq = strchr(arg, '=');
            if (eq) { *eq = 0; strncpy(c->key, arg, sizeof(c->key) - 1); strncpy(c->sval, eq + 1, sizeof(c->sval) - 1); c->value = (float)atof(eq + 1); }
            else strncpy(c->key, arg, sizeof(c->key) - 1);
        } else if (istarts(p, "XC")) {
            char *eq = strchr(arg, '=');
            if (eq) { *eq = 0; c->kind = CMD_XCONF_SET; strncpy(c->key, arg, sizeof(c->key) - 1); c->value = (float)atof(eq + 1); strncpy(c->sval, eq + 1, sizeof(c->sval) - 1); }
            else { c->kind = CMD_XCONF_GET; strncpy(c->key, arg, sizeof(c->key) - 1); }
            // strip trailing spaces in key
            for (int i = (int)strlen(c->key) - 1; i >= 0 && c->key[i] == ' '; i--) c->key[i] = 0;
        } else c->kind = CMD_UNKNOWN;
        return 1;
    }
    char *save = NULL;
    for (char *t = strtok_r(buf, " \t,", &save); t && n < max; t = strtok_r(NULL, " \t,", &save)) {
        cmd_t c; memset(&c, 0, sizeof(c));
        if (ieq(t, "AZ")) c.kind = CMD_GET_AZ;
        else if (ieq(t, "EL")) c.kind = CMD_GET_EL;
        else if (istarts(t, "AZ") && is_number(t + 2)) { c.kind = CMD_SET_AZ; c.value = (float)atof(t + 2); }
        else if (istarts(t, "EL") && is_number(t + 2)) { c.kind = CMD_SET_EL; c.value = (float)atof(t + 2); }
        else if (ieq(t, "SA")) c.kind = CMD_STOP_AZ;
        else if (ieq(t, "SE")) c.kind = CMD_STOP_EL;
        else if (ieq(t, "ML")) c.kind = CMD_MOVE_L;
        else if (ieq(t, "MR")) c.kind = CMD_MOVE_R;
        else if (ieq(t, "MU")) c.kind = CMD_MOVE_U;
        else if (ieq(t, "MD")) c.kind = CMD_MOVE_D;
        else if (ieq(t, "VE")) c.kind = CMD_VERSION;
        else if (ieq(t, "GS")) c.kind = CMD_STATUS;
        else if (ieq(t, "GE")) c.kind = CMD_ERROR;
        else if (ieq(t, "HOME") || ieq(t, "RESET")) c.kind = CMD_HOME;
        else if (ieq(t, "PARK")) c.kind = CMD_PARK;
        else continue;              // UP000 XXX DN000 XXX and other Easycomm fields are ignored
        out[n++] = c;
    }
    return n;
}

// ------------------------------------------------------------------ NMEA
static int hexv(char c) { return c >= '0' && c <= '9' ? c - '0' : (c >= 'A' && c <= 'F' ? c - 'A' + 10 : (c >= 'a' && c <= 'f' ? c - 'a' + 10 : -1)); }

bool nmea_checksum_ok(const char *s) {
    if (*s != '$') return false;
    uint8_t x = 0; s++;
    while (*s && *s != '*') x ^= (uint8_t)*s++;
    if (*s != '*') return false;
    int h = hexv(s[1]), l = hexv(s[2]);
    return h >= 0 && l >= 0 && ((h << 4) | l) == x;
}

static double nmea_deg(const char *f, const char *hemi) {
    if (!*f) return NAN;
    double v = atof(f);
    int d = (int)(v / 100.0);
    double r = d + (v - d * 100.0) / 60.0;
    if (*hemi == 'S' || *hemi == 'W') r = -r;
    return r;
}

bool nmea_parse(const char *s, gps_fix_t *fix) {
    if (!nmea_checksum_ok(s)) return false;
    char buf[100]; strncpy(buf, s, sizeof(buf) - 1); buf[sizeof(buf) - 1] = 0;
    char *star = strchr(buf, '*'); if (star) *star = 0;
    const char *f[20]; int nf = 0;
    char *q = buf;
    f[nf++] = q;
    while (*q && nf < 20) { if (*q == ',') { *q = 0; f[nf++] = q + 1; } q++; }
    const char *type = f[0] + 3;     // skip $GP / $GN / $GL
    if (strncmp(type, "RMC", 3) == 0 && nf >= 10) {
        fix->valid = f[2][0] == 'A';
        if (strlen(f[1]) >= 6) { fix->hour = (f[1][0]-'0')*10 + f[1][1]-'0'; fix->min = (f[1][2]-'0')*10 + f[1][3]-'0'; fix->sec = (float)atof(f[1] + 4); }
        if (strlen(f[9]) >= 6) { fix->day = (f[9][0]-'0')*10 + f[9][1]-'0'; fix->month = (f[9][2]-'0')*10 + f[9][3]-'0'; fix->year = 2000 + (f[9][4]-'0')*10 + f[9][5]-'0'; }
        if (fix->valid) { fix->lat = nmea_deg(f[3], f[4]); fix->lon = nmea_deg(f[5], f[6]); }
        fix->updates++;
        return true;
    }
    if (strncmp(type, "GGA", 3) == 0 && nf >= 10) {
        fix->fix_quality = atoi(f[6]);
        fix->sats = atoi(f[7]);
        if (*f[9]) fix->alt = (float)atof(f[9]);
        if (fix->fix_quality > 0) { fix->lat = nmea_deg(f[2], f[3]); fix->lon = nmea_deg(f[4], f[5]); }
        return true;
    }
    return false;
}

// ------------------------------------------------------------------ CRCs, IMU
uint8_t tmc_crc8(const uint8_t *data, size_t len) {     // TMC2209 datasheet, section 4.2
    uint8_t crc = 0;
    for (size_t i = 0; i < len; i++) {
        uint8_t b = data[i];
        for (int j = 0; j < 8; j++) {
            if ((crc >> 7) ^ (b & 0x01)) crc = (uint8_t)((crc << 1) ^ 0x07);
            else crc = (uint8_t)(crc << 1);
            b >>= 1;
        }
    }
    return crc;
}

float imu_elevation_deg(float ax, float ay, float az) {
    (void)ax;   // rotation is about the board X axis (along the EL stub)
    return atan2f(ay, az) * 57.29578f;
}

uint32_t crc32_calc(const void *data, size_t len) {
    const uint8_t *p = (const uint8_t *)data; uint32_t c = 0xFFFFFFFFu;
    for (size_t i = 0; i < len; i++) { c ^= p[i]; for (int k = 0; k < 8; k++) c = (c >> 1) ^ (0xEDB88320u & (0u - (c & 1u))); }
    return ~c;
}
