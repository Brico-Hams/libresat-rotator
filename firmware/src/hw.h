// Hardware drivers: TMC2209 (PIO UART), AS5600, MPU-6050, GPS UART, flash settings.
#pragma once
#include <stdint.h>
#include <stdbool.h>
#include "core.h"

// ---------------- TMC2209
void     tmc_init(void);
bool     tmc_write(uint8_t addr, uint8_t reg, uint32_t val);
bool     tmc_read(uint8_t addr, uint8_t reg, uint32_t *val);
bool     tmc_configure(uint8_t addr, int irun_ma, int ihold_pct, int microsteps, bool reverse);

// ---------------- I2C sensors (bus 0 = AZ side, 1 = EL side)
void     sensors_init(void);
bool     as5600_read(int bus, uint16_t *raw, uint8_t *status);
bool     mpu_init(int bus);
bool     mpu_read(int bus, float *ax, float *ay, float *az);

// ---------------- GPS
void     gps_init(void);
void     gps_poll(gps_fix_t *fix);          // non-blocking, parses complete sentences

// ---------------- settings in the last flash sector
#define SETTINGS_MAGIC 0x4C535231u        // "LSR1"
typedef struct {
    uint32_t magic, version, size;
    float    ratio[2];
    int32_t  microsteps;
    int32_t  dir[2];
    float    offset[2];
    float    min_deg[2], max_deg[2];
    float    vmax[2], acc[2];
    int32_t  irun_ma[2], ihold_pct;
    float    deadband;
    float    imu_el_zero, imu_el_dir;       // boom IMU calibration
    float    tilt_zero[2];                  // base IMU level calibration (roll, pitch)
    float    park_az, park_el;
    float    home_az;                       // azimuth of the AZ index (LSR-1 hall magnet; LSR-2 lower edge of the slot)
    float    home_el;                       // LSR-2: elevation of the EL index slot edge (horizon = 0)
    float    backlash[2];                   // output backlash in deg (XCAL BACKLASH), applied to the reported/controlled angle
    int32_t  enc_dir[2];                    // encoder sense vs step direction (+1/-1, 0 = disabled)
    int32_t  last_pos[2];                   // position saved when idle (microsteps)
    uint16_t last_enc[2];                   // encoder raw at that moment
    int32_t  last_valid;
    int32_t  use_imu_el;                    // 1: elevation referenced from the boom IMU at boot
    int32_t  reserved[8];
    uint32_t crc;
} settings_t;

void     settings_defaults(settings_t *s);
bool     settings_load(settings_t *s);
void     settings_save(settings_t *s);
