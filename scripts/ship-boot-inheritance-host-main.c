/* Positive execution witness for the Ship boot-inheritance host model. */
#include <stdint.h>
#include <stdio.h>

#include "ship_runtime_io.h"

static uint8_t screen_initializations;
static uint16_t oracle_line;
static uint16_t oracle_wraps;
static uint8_t oracle_mode;

enum {
    ORACLE_STALLED = 0,
    ORACLE_ONE_SHOT = 1,
    ORACLE_RECURRING = 2
};

void scr_init(void) { screen_initializations++; }
void scr_putc(char code) { (void)code; }
void lisp_poll(void) { }

uint16_t lisp65_ship_io_host_raster_step(void) {
    uint16_t event;
    if (oracle_mode == ORACLE_STALLED
        || (oracle_mode == ORACLE_ONE_SHOT && oracle_wraps != 0u))
        return oracle_line;
    oracle_line = (uint16_t)((oracle_line + 1u) % 312u);
    if (oracle_line == 0u) oracle_wraps++;
    event = oracle_line;
    if (oracle_line == 255u) event |= LISP65_SHIP_HOST_RASTER_IRQ;
    return event;
}

static void oracle_reset(uint8_t mode) {
    oracle_line = 0u;
    oracle_wraps = 0u;
    oracle_mode = mode;
}

static uint16_t frame_read(void) {
    uint8_t before;
    uint8_t low;
    uint8_t after;
    do {
        if (!lisp65_ship_io_peek(0xff84u, &before)) return 0xffffu;
        if (!lisp65_ship_io_peek(0xff83u, &low)) return 0xffffu;
        if (!lisp65_ship_io_peek(0xff84u, &after)) return 0xffffu;
    } while (before != after);
    return (uint16_t)((uint16_t)after << 8) | low;
}

int main(void) {
    uint16_t before;
    uint16_t after;
    if (lisp65_ship_io_host_clock_armed()
        || lisp65_ship_io_host_clock_verified()
        || lisp65_ship_io_host_input_armed()
        || lisp65_ship_io_getin(0u) != 0) return 1;
    oracle_reset(ORACLE_ONE_SHOT);
    if (lisp65_ship_io_init() || lisp65_ship_io_host_clock_verified()) return 2;
    oracle_reset(ORACLE_STALLED);
    if (lisp65_ship_io_init() || lisp65_ship_io_host_clock_verified()) return 3;
    oracle_reset(ORACLE_RECURRING);
    before = frame_read();
    if (before != 0u || !lisp65_ship_io_init()) return 4;
    if (!lisp65_ship_io_host_clock_armed()
        || !lisp65_ship_io_host_clock_verified()
        || !lisp65_ship_io_host_input_armed()
        || lisp65_ship_io_host_verified_deltas() != 3u
        || lisp65_ship_io_host_frame_count() < 4u
        || oracle_wraps < 4u || screen_initializations != 3u) return 5;
    after = frame_read();
    if (after <= before || lisp65_ship_io_getin(1u) != 'A') return 6;
    puts("ship-boot-inheritance-host: PASS inherited=0 one-shot=reject stagnant=reject armed=1 verified=1 deltas=3 oracle-wraps=4 input=1 executions=3");
    return 0;
}
