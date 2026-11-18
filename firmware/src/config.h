// LibreSat Rotator firmware — board pin map and compile-time defaults (LSR-CTL v1.0)
#pragma once

// ---------------- build selection (CMake: -DLSR_MODEL=1|2, -DLSR_DRIVER=TMC2209_UART|EXT_STEPDIR)
#define TMC2209_UART 1             // LSR-1: internal TMC2209 on UART, STEP/DIR on the board
#define EXT_STEPDIR  2             // LSR-2: external DM542 / TMC5160 in STEP/DIR mode, no UART calls
#ifndef LSR_MODEL
#define LSR_MODEL 1
#endif
#ifndef LSR_DRIVER
#if LSR_MODEL == 2
#define LSR_DRIVER EXT_STEPDIR
#else
#define LSR_DRIVER TMC2209_UART
#endif
#endif

#if LSR_MODEL == 2
#define FW_NAME     "LSR-2"
#else
#define FW_NAME     "LSR-1"
#endif
#define FW_VERSION  "1.1.0"

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
#define PIN_HALL_AZ     20    // AZ index (active low). LSR-1: DRV5032FB / AH1806 at 3.3 V. LSR-2 Mk4: NJK-5002C NPN Hall switch (12 V supply, open collector)
#define PIN_HALL_EL     21    // EL index. LSR-2 Mk4: NJK-5002C; LSR-1: optional index / limit
#define PIN_PWRFAIL     22    // LSR-2: 48 V opto-isolated power-loss detect (high = 48 V gone), see PWR_* below
#define PIN_VSENSE      26    // ADC0: VM / 11
#define ADC_VSENSE       0
#define PIN_ONBOARD_LED 25    // plain Pico; Pico W uses the CYW43 LED (not driven)

// EXT_STEPDIR: STEP/DIR stay on GPIO10..13; one enable per axis on the free pins GPIO2/GPIO3.
// PIN_NEN (GPIO14) is not driven by the drivers in this mode.
#define PIN_EN_AZ        2
#define PIN_EN_EL        3
#define EXT_STEP_ACTIVE  1    // pin level while the STEP pulse is high (after the buffer/opto stage)
#define EXT_DIR_POS_LEVEL 1   // DIR pin level for +1
#define EXT_EN_ACTIVE    0    // DM542 ENA is often active-low: enabled = low, disabled = high (VERIFY)

// LSR-2 index. Mk4 replica: NJK-5002C NPN Hall switch (SARCNET Hall Effect Switch) per axis, magnet on the moving part; the open-collector output
// pulls the pin LOW while the magnet is in range (active low = IDX_SLOT_LEVEL 0). The sensor runs on 12 V (XL7015), so the output is pulled up to
// 3.3 V on the RP2040 side only (the NPN open collector never drives the pin high: no 5 V/12 V on the GPIO; add a 10 k series resistor + 3.3 V
// pull-up on the controller board). The earlier phase-11 design used a photo-interrupter + slotted disc with the same logic level.
// Mechanical end stops (microswitches on the saddle, SARCNET "End Stop") are a fail-safe independent of the firmware: wired normally closed in
// series with the driver enable (ENA) of the axis, so a pressed switch or a cut wire disables that driver in hardware. No GPIO is needed;
// to also read them add a spare input with the same pull-up logic (the firmware limits and the bumpers act first). LSR-1 keeps its hall sensor.
#define IDX_SLOT_LEVEL   0
// LSR-2 power-loss detect: the opto transistor pulls PIN_PWRFAIL low while 48 V is present. On loss the firmware stops the
// motors and saves the position to flash (bulk capacitance on the 48 V rail keeps the 5 V buck alive for the ~60 ms write).
// Armed only after 48 V has been seen once since boot, so a bench build without the circuit still works.
#define PWR_LOSS_LEVEL   1

// ---------------- serial
#if LSR_MODEL == 2
#define PI_BAUD       9600       // EasyComm II 9600 8N1: what SARCTrac Mk5 trackers (PstRotator, Gpredict, SatPC32, Orbitron) expect
#else
#define PI_BAUD     115200
#endif
#define GPS_BAUD      9600
#define TMC_BAUD    115200

// ---------------- motion defaults (all overridable with XC key=value, stored in flash)
// ratio, microsteps, ranges, vmax and acc per axis come from the model profile (core.cpp: lsr_model()).
#define DEF_FULLSTEPS   200
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
