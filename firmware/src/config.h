// LibreSat Rotator LSR-1 firmware — board pin map and compile-time defaults (LSR-CTL v1.0)
#pragma once

#define FW_NAME     "LSR-1"
#define FW_VERSION  "1.0.0"

// ---------------- pins (Raspberry Pi Pico GPIO numbers)
#define PIN_PI_TX        0    // UART0 TX -> Pi GPIO15 (RXD)
#define PIN_PI_RX        1    // UART0 RX <- Pi GPIO14 (TXD)
#define PIN_GPS_TX       4    // UART1 TX -> GPS RX
#define PIN_GPS_RX       5    // UART1 RX <- GPS TX
#define PIN_GPS_PPS      6
#define PIN_BTN          7    // PARK/STOP button to GND
#define PIN_TMC_TX       8    // PIO UART TX (through 1k) -> PDN_UART
#define PIN_TMC_RX       9    // PIO UART RX  <- PDN_UART
#define PIN_STEP_AZ     10
#define PIN_DIR_AZ      11
#define PIN_STEP_EL     12
#define PIN_DIR_EL      13
#define PIN_NEN         14    // driver enable, active low (10k pull-up on board)
#define PIN_LED         15
#define PIN_SDA0        16    // I2C0: AZ encoder + base IMU
#define PIN_SCL0        17
#define PIN_SDA1        18    // I2C1: EL encoder + boom IMU
#define PIN_SCL1        19
#define PIN_HALL_AZ     20    // AZ index (active low, DRV5032FB / AH1806 at 3.3 V)
#define PIN_HALL_EL     21    // optional EL index / limit
#define PIN_VSENSE      26    // ADC0: VM / 11
#define ADC_VSENSE       0
#define PIN_ONBOARD_LED 25    // plain Pico; Pico W uses the CYW43 LED (not driven)

// ---------------- serial
#define PI_BAUD     115200
#define GPS_BAUD      9600
#define TMC_BAUD    115200

// ---------------- motion defaults (all overridable with XC key=value, stored in flash)
#define DEF_RATIO        25.0f     // printed cycloid 25:1
#define DEF_MICROSTEPS   16
#define DEF_FULLSTEPS   200
#define DEF_VMAX_AZ      20.0f     // deg/s at the output
#define DEF_VMAX_EL      15.0f
#define DEF_ACC_AZ       25.0f     // deg/s^2
#define DEF_ACC_EL       20.0f
#define DEF_AZ_MIN        0.0f     // mechanical range (cable wrap): 0..450 deg
#define DEF_AZ_MAX      450.0f
#define DEF_EL_MIN        0.0f
#define DEF_EL_MAX      180.0f     // 0..180 allows "flip" passes
#define DEF_IRUN_MA     900        // TMC2209 RMS run current
#define DEF_IHOLD_PCT    35        // hold current (% of run)
#define DEF_DEADBAND     0.05f     // deg

#define STEP_ISR_HZ   25000        // step generator tick
#define PLAN_HZ         500        // planner / encoder loop
#define IMU_HZ           50

// ---------------- sensors
#define AS5600_ADDR   0x36
#define MPU_ADDR      0x68
#define ENC_CPR       4096
