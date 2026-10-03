/* One source of truth for arming the MEGA65 raster time base.
 *
 * Workbench installs its own IRQ owner; Ship retains the KERNAL vector.  Both
 * nevertheless require the same VIC-side transition from inherited firmware
 * state to one acknowledged, enabled raster source.  Keep the sequence inline:
 * Workbench's handoff geometry is pinned and must not acquire a call edge. */
#ifndef LISP65_MEGA65_RASTER_TIMEBASE_H
#define LISP65_MEGA65_RASTER_TIMEBASE_H

#include <stdint.h>

#define LISP65_RASTER_IRQ_ENABLE_MASK 0x01u

static __attribute__((always_inline)) inline
void lisp65_raster_timebase_arm(void) {
    *(volatile uint8_t *)0xd012 = 0xffu;
    *(volatile uint8_t *)0xd011 &= 0x7fu;
    *(volatile uint8_t *)0xd019 = 0xffu;
    *(volatile uint8_t *)0xd01a = LISP65_RASTER_IRQ_ENABLE_MASK;
}

static __attribute__((always_inline)) inline
uint8_t lisp65_raster_timebase_armed(void) {
    return (uint8_t)(*(volatile uint8_t *)0xd01a
                     & LISP65_RASTER_IRQ_ENABLE_MASK);
}

#endif /* LISP65_MEGA65_RASTER_TIMEBASE_H */
