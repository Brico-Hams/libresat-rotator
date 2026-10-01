// Hardware drivers for the LSR-CTL board.
#include "hw.h"
#include "config.h"
#include <string.h>
#include <math.h>
#include "pico/stdlib.h"
#include "hardware/pio.h"
#include "hardware/i2c.h"
#include "hardware/uart.h"
#include "hardware/flash.h"
#include "hardware/sync.h"
#include "tmc_uart.pio.h"

// =========================================================== TMC2209 over PIO UART
static PIO tmc_pio = pio0;
static uint sm_tx, sm_rx;

void tmc_init(void) {
    uint off_tx = pio_add_program(tmc_pio, &tmc_tx_program);
    uint off_rx = pio_add_program(tmc_pio, &tmc_rx_program);
    sm_tx = pio_claim_unused_sm(tmc_pio, true);
    sm_rx = pio_claim_unused_sm(tmc_pio, true);
    tmc_tx_init(tmc_pio, sm_tx, off_tx, PIN_TMC_TX, TMC_BAUD);
    tmc_rx_init(tmc_pio, sm_rx, off_rx, PIN_TMC_RX, TMC_BAUD);
}

static void rx_flush(void) { while (!pio_sm_is_rx_fifo_empty(tmc_pio, sm_rx)) (void)pio_sm_get(tmc_pio, sm_rx); }

static bool rx_byte(uint8_t *b, uint32_t timeout_us) {
    absolute_time_t t = make_timeout_time_us(timeout_us);
    while (pio_sm_is_rx_fifo_empty(tmc_pio, sm_rx)) if (time_reached(t)) return false;
    *b = (uint8_t)(pio_sm_get(tmc_pio, sm_rx) >> 24);
    return true;
}

static void tx_bytes(const uint8_t *d, int n) {
    for (int i = 0; i < n; i++) pio_sm_put_blocking(tmc_pio, sm_tx, d[i]);
}

bool tmc_write(uint8_t addr, uint8_t reg, uint32_t val) {
    uint8_t d[8] = {0x05, addr, (uint8_t)(reg | 0x80), (uint8_t)(val >> 24), (uint8_t)(val >> 16), (uint8_t)(val >> 8), (uint8_t)val, 0};
    d[7] = tmc_crc8(d, 7);
    rx_flush();
    tx_bytes(d, 8);
    uint8_t e;                                   // single wire: our own bytes echo back
    for (int i = 0; i < 8; i++) if (!rx_byte(&e, 2000)) return false;
    sleep_us(200);
    return true;
}

bool tmc_read(uint8_t addr, uint8_t reg, uint32_t *val) {
    uint8_t d[4] = {0x05, addr, reg, 0};
    d[3] = tmc_crc8(d, 3);
    rx_flush();
    tx_bytes(d, 4);
    uint8_t e, r[8];
    for (int i = 0; i < 4; i++) if (!rx_byte(&e, 2000)) return false;    // echo
    for (int i = 0; i < 8; i++) if (!rx_byte(&r[i], 5000)) return false;
    if (r[0] != 0x05 || r[1] != 0xFF || tmc_crc8(r, 7) != r[7]) return false;
    *val = ((uint32_t)r[3] << 24) | ((uint32_t)r[4] << 16) | ((uint32_t)r[5] << 8) | r[6];
    return true;
}

bool tmc_configure(uint8_t addr, int irun_ma, int ihold_pct, int microsteps, bool reverse) {
    // Rsense 0.11 ohm (StepStick standard): I_rms = (CS+1)/32 * 0.325 / (0.11+0.02) / sqrt(2)
    int cs = (int)lroundf(irun_ma / 1000.0f * 32.0f * 1.41421f * 0.13f / 0.325f) - 1;
    if (cs < 0) cs = 0; if (cs > 31) cs = 31;
    int ch = cs * ihold_pct / 100; if (ch > 31) ch = 31;
    int mres = 4;   // 16
    switch (microsteps) { case 256: mres = 0; break; case 128: mres = 1; break; case 64: mres = 2; break;
                      case 32: mres = 3; break; case 16: mres = 4; break; case 8: mres = 5; break; case 4: mres = 6; break; }
    uint32_t cnt0 = 0, cnt1 = 0;
    bool ok = tmc_read(addr, 0x02, &cnt0);                                       // IFCNT
    uint32_t gconf = (1u << 6) | (1u << 7) | (1u << 8) | (reverse ? (1u << 3) : 0);   // pdn_disable, mstep_reg_select, multistep_filt
    tmc_write(addr, 0x00, gconf);
    tmc_write(addr, 0x10, (uint32_t)ch | ((uint32_t)cs << 8) | (8u << 16));    // IHOLD_IRUN, IHOLDDELAY 8
    tmc_write(addr, 0x11, 20);                                                    // TPOWERDOWN ~0.4 s
    tmc_write(addr, 0x6C, 0x10000053u | ((uint32_t)mres << 24));                 // CHOPCONF: intpol, toff 3, hstrt 5, tbl 2
    tmc_write(addr, 0x70, 0xC10D0024u);                                           // PWMCONF default (StealthChop auto)
    ok = ok && tmc_read(addr, 0x02, &cnt1);
    return ok && ((cnt1 - cnt0) & 0xFF) == 5;
}

// =========================================================== I2C sensors
static i2c_inst_t *bus_of(int b) { return b == 0 ? i2c0 : i2c1; }

void sensors_init(void) {
    i2c_init(i2c0, 400000);           // AZ side: short leads inside the base
    i2c_init(i2c1, 100000);           // EL side: ~1.5 m of CAT5e through the cable loop
    gpio_set_function(PIN_SDA0, GPIO_FUNC_I2C); gpio_set_function(PIN_SCL0, GPIO_FUNC_I2C);
    gpio_set_function(PIN_SDA1, GPIO_FUNC_I2C); gpio_set_function(PIN_SCL1, GPIO_FUNC_I2C);
    gpio_pull_up(PIN_SDA0); gpio_pull_up(PIN_SCL0); gpio_pull_up(PIN_SDA1); gpio_pull_up(PIN_SCL1);
}

static bool reg_read(int b, uint8_t addr, uint8_t reg, uint8_t *dst, size_t n) {
    if (i2c_write_timeout_us(bus_of(b), addr, &reg, 1, true, 2000) != 1) return false;
    return i2c_read_timeout_us(bus_of(b), addr, dst, n, false, 3000) == (int)n;
}
static bool reg_write(int b, uint8_t addr, uint8_t reg, uint8_t v) {
    uint8_t d[2] = {reg, v};
    return i2c_write_timeout_us(bus_of(b), addr, d, 2, false, 2000) == 2;
}

bool as5600_read(int bus, uint16_t *raw, uint8_t *status) {
    uint8_t st, d[2];
    if (!reg_read(bus, AS5600_ADDR, 0x0B, &st, 1)) return false;
    if (!reg_read(bus, AS5600_ADDR, 0x0C, d, 2)) return false;
    *status = st;
    *raw = (uint16_t)(((d[0] & 0x0F) << 8) | d[1]);
    return true;
}

bool mpu_init(int bus) {
    uint8_t who;
    if (!reg_read(bus, MPU_ADDR, 0x75, &who, 1)) return false;
    if (who != 0x68 && who != 0x70 && who != 0x71 && who != 0x73 && who != 0x98) return false;
    reg_write(bus, MPU_ADDR, 0x6B, 0x01);      // wake, PLL
    reg_write(bus, MPU_ADDR, 0x1A, 0x06);      // DLPF ~5 Hz
    reg_write(bus, MPU_ADDR, 0x1C, 0x00);      // +-2 g
    return true;
}

bool mpu_read(int bus, float *ax, float *ay, float *az) {
    uint8_t d[6];
    if (!reg_read(bus, MPU_ADDR, 0x3B, d, 6)) return false;
    *ax = (int16_t)((d[0] << 8) | d[1]) / 16384.0f;
    *ay = (int16_t)((d[2] << 8) | d[3]) / 16384.0f;
    *az = (int16_t)((d[4] << 8) | d[5]) / 16384.0f;
    return true;
}

// =========================================================== GPS
static char gps_line[100];
static int gps_len = 0;

void gps_init(void) {
    uart_init(uart1, GPS_BAUD);
    gpio_set_function(PIN_GPS_TX, GPIO_FUNC_UART);
    gpio_set_function(PIN_GPS_RX, GPIO_FUNC_UART);
    gpio_init(PIN_GPS_PPS); gpio_set_dir(PIN_GPS_PPS, GPIO_IN);
}

void gps_poll(gps_fix_t *fix) {
    while (uart_is_readable(uart1)) {
        char c = uart_getc(uart1);
        if (c == '$') gps_len = 0;
        if (c == '\r' || c == '\n') {
            if (gps_len > 6) { gps_line[gps_len] = 0; nmea_parse(gps_line, fix); }
            gps_len = 0;
        } else if (gps_len < (int)sizeof(gps_line) - 1) gps_line[gps_len++] = c;
    }
}

// =========================================================== settings (last 4 KB sector)
#define SETTINGS_OFFSET (PICO_FLASH_SIZE_BYTES - FLASH_SECTOR_SIZE)

void settings_defaults(settings_t *s) {
    memset(s, 0, sizeof(*s));
    s->magic = SETTINGS_MAGIC; s->version = 1; s->size = sizeof(*s);
    s->ratio[0] = s->ratio[1] = DEF_RATIO;
    s->microsteps = DEF_MICROSTEPS;
    s->dir[0] = s->dir[1] = 1;
    s->min_deg[0] = DEF_AZ_MIN; s->max_deg[0] = DEF_AZ_MAX;
    s->min_deg[1] = DEF_EL_MIN; s->max_deg[1] = DEF_EL_MAX;
    s->vmax[0] = DEF_VMAX_AZ; s->vmax[1] = DEF_VMAX_EL;
    s->acc[0] = DEF_ACC_AZ; s->acc[1] = DEF_ACC_EL;
    s->irun_ma[0] = s->irun_ma[1] = DEF_IRUN_MA; s->ihold_pct = DEF_IHOLD_PCT;
    s->deadband = DEF_DEADBAND;
    s->imu_el_dir = 1.0f;
    s->park_az = 0.0f; s->park_el = 90.0f;
    s->enc_dir[0] = s->enc_dir[1] = 1;
    s->use_imu_el = 1;
}

bool settings_load(settings_t *s) {
    const settings_t *f = (const settings_t *)(XIP_BASE + SETTINGS_OFFSET);
    if (f->magic != SETTINGS_MAGIC || f->size != sizeof(settings_t)) return false;
    if (crc32_calc(f, offsetof(settings_t, crc)) != f->crc) return false;
    memcpy(s, f, sizeof(*s));
    return true;
}

void settings_save(settings_t *s) {
    static uint8_t page[FLASH_SECTOR_SIZE] __attribute__((aligned(4)));
    s->magic = SETTINGS_MAGIC; s->size = sizeof(*s);
    s->crc = crc32_calc(s, offsetof(settings_t, crc));
    memset(page, 0xFF, sizeof(page));
    memcpy(page, s, sizeof(*s));
    uint32_t irq = save_and_disable_interrupts();
    flash_range_erase(SETTINGS_OFFSET, FLASH_SECTOR_SIZE);
    flash_range_program(SETTINGS_OFFSET, page, FLASH_SECTOR_SIZE);
    restore_interrupts(irq);
}
