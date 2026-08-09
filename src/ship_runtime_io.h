/* Standalone Ship Runtime I/O seam.
 *
 * This is deliberately not a Workbench service: shipped images have no
 * evaluator, phase driver or C2 KERNAL ownership.  The Runtime binds the
 * already-public bytecode primitives to the platform devices directly.
 */
#ifndef LISP65_SHIP_RUNTIME_IO_H
#define LISP65_SHIP_RUNTIME_IO_H

#include <stdint.h>

#define LISP65_SHIP_KEY_RUN_STOP 0x03u

uint8_t lisp65_ship_io_init(void);
int lisp65_ship_io_getin(uint8_t blocking);
void lisp65_ship_io_putc(uint8_t code);
uint8_t lisp65_ship_io_peek(uint16_t address, uint8_t *value);
uint16_t lisp65_ship_io_frame_count(void);

#ifndef __mos__
/* Supplied by each host witness as a complete 9-bit raster sample plus an
 * independent modeled IRQ pulse.  Ship itself must recognize frame wraps. */
#define LISP65_SHIP_HOST_RASTER_MASK 0x01ffu
#define LISP65_SHIP_HOST_RASTER_IRQ 0x8000u
uint16_t lisp65_ship_io_host_raster_step(void);
uint16_t lisp65_ship_io_input_used(void);
uint16_t lisp65_ship_io_output_count(void);
uint32_t lisp65_ship_io_output_hash(void);
uint8_t lisp65_ship_io_host_clock_armed(void);
uint8_t lisp65_ship_io_host_clock_verified(void);
uint8_t lisp65_ship_io_host_input_armed(void);
uint16_t lisp65_ship_io_host_frame_count(void);
uint8_t lisp65_ship_io_host_verified_deltas(void);
#endif

#endif /* LISP65_SHIP_RUNTIME_IO_H */
