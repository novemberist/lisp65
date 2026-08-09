/* Evaluator-free physical I/O for standalone Ship Runtime images. */
#include <stdint.h>

#include "interrupt.h"
#include "mega65_raster_timebase.h"
#include "screen.h"
#include "ship_runtime_io.h"

#define LISP65_SHIP_PROGRESS_DELTAS 3u

static uint16_t ship_frame_read(void);
static uint16_t ship_raster_read(void);
static uint8_t ship_reference_wrap(void);

/* A frame boundary is the high-to-low transition of the raster's ninth bit.
 * D012 alone decreases twice per 312-line frame (255->256 and 311->0), so it
 * cannot distinguish the real frame boundary.  The stagnant-sample bound
 * turns a dead raster into a clean boot failure. */
static uint8_t ship_reference_wrap(void) {
    uint16_t previous = ship_raster_read();
    uint16_t stagnant = 0u;
    for (;;) {
        uint16_t current = ship_raster_read();
        if ((previous & 0x100u) && !(current & 0x100u)) return 1u;
        if (current == previous) {
            if (++stagnant == 0u) return 0u;
        } else {
            stagnant = 0u;
        }
        previous = current;
    }
}

/* The counter and the reference are deliberately different mechanisms.  A
 * proof that asks only whether the counter changed once can accept unrelated
 * scratch traffic.  Synchronize on one reference wrap, then require one
 * monotonic counter step at each of three further reference wraps. */
static uint8_t ship_frame_prove_progress(void) {
    uint8_t sample;
    uint16_t previous;
    if (!ship_reference_wrap()) return 0u;
    previous = ship_frame_read();
    for (sample = 0u; sample < LISP65_SHIP_PROGRESS_DELTAS; ++sample) {
        uint16_t current;
        if (!ship_reference_wrap()) return 0u;
        current = ship_frame_read();
        if ((uint16_t)(current - previous) != 1u) return 0u;
        previous = current;
    }
    return 1u;
}

#ifdef __mos__
#include <cbm.h>

volatile uint8_t lisp65_ship_frame_lo;
volatile uint8_t lisp65_ship_frame_hi;
volatile uint8_t lisp65_ship_old_irq[2];
static uint8_t lisp65_ship_old_vic_mask;

extern void lisp65_ship_timebase_irq(void);

#ifdef LISP65_SHIP_QUEUE_DIAGNOSTIC
/* Non-promotable Link-86 discriminator.  The serial monitor sees RAM under
 * mapped I/O, so target code must sample the live queue and publish the
 * observation into ordinary RAM.  The first present event is latched: a
 * later GETIN poll cannot erase the evidence before the monitor reads it. */
#define SHIP_QUEUE_DIAG_RAM \
    __attribute__((used, section(".bss.lisp65_ship_queue_diag")))
volatile uint8_t lisp65_ship_queue_diag_samples SHIP_QUEUE_DIAG_RAM;
volatile uint8_t lisp65_ship_queue_diag_last_state SHIP_QUEUE_DIAG_RAM;
volatile uint8_t lisp65_ship_queue_diag_last_code SHIP_QUEUE_DIAG_RAM;
volatile uint8_t lisp65_ship_queue_diag_latched SHIP_QUEUE_DIAG_RAM;
volatile uint8_t lisp65_ship_queue_diag_latched_state SHIP_QUEUE_DIAG_RAM;
volatile uint8_t lisp65_ship_queue_diag_latched_code SHIP_QUEUE_DIAG_RAM;

static void ship_queue_diag_sample(void) {
    uint8_t state = *(volatile uint8_t *)0xd60a;
    uint8_t code = *(volatile uint8_t *)0xd619;
    lisp65_ship_queue_diag_last_state = state;
    lisp65_ship_queue_diag_last_code = code;
    if (lisp65_ship_queue_diag_samples != 0xffu)
        lisp65_ship_queue_diag_samples++;
    if (!lisp65_ship_queue_diag_latched && (state & 0x80u)) {
        lisp65_ship_queue_diag_latched_state = state;
        lisp65_ship_queue_diag_latched_code = code;
        lisp65_ship_queue_diag_latched = 1u;
    }
}
#endif

/* The public $FF83/$FF84 clock contract is composition-owned.  Workbench owns
 * those cells in its mapped E000 window; Ship keeps the KERNAL mapped and
 * therefore backs the same logical surface with this private IRQ counter. */
static uint16_t ship_frame_read(void) {
    uint8_t before;
    uint8_t after;
    uint8_t value;
    do {
        before = lisp65_ship_frame_hi;
        value = lisp65_ship_frame_lo;
        after = lisp65_ship_frame_hi;
    } while (before != after);
    return (uint16_t)((uint16_t)after << 8) | value;
}

/* Read the complete 9-bit raster without accepting a torn D011/D012 sample.
 * D011 bit 7 is sampled on both sides of D012; if it moved at the boundary,
 * retry until both bytes describe the same half-frame. */
static uint16_t ship_raster_read(void) {
    volatile uint8_t *control = (volatile uint8_t *)0xd011;
    volatile uint8_t *raster = (volatile uint8_t *)0xd012;
    uint8_t high_before;
    uint8_t low;
    uint8_t high_after;
    do {
        high_before = *control & 0x80u;
        low = *raster;
        high_after = *control & 0x80u;
    } while (high_before != high_after);
    return (uint16_t)(((uint16_t)high_after << 1) | low);
}

static uint8_t ship_timebase_armed(void) {
    uint16_t handler = (uint16_t)(uintptr_t)lisp65_ship_timebase_irq;
    return (uint8_t)(lisp65_raster_timebase_armed()
        && *(volatile uint8_t *)0x0314 == (uint8_t)handler
        && *(volatile uint8_t *)0x0315 == (uint8_t)(handler >> 8));
}

static void ship_timebase_restore(void) {
    *(volatile uint8_t *)0xd01a = lisp65_ship_old_vic_mask;
    *(volatile uint8_t *)0x0314 = lisp65_ship_old_irq[0];
    *(volatile uint8_t *)0x0315 = lisp65_ship_old_irq[1];
}

/* The cold stager enters under SEI.  Install a Ship-owned counter before the
 * shared VIC arm sequence, retain the KERNAL handler as the chained service
 * owner, and publish success only after three independently observed deltas. */
uint8_t lisp65_ship_io_init(void) {
    uint16_t handler = (uint16_t)(uintptr_t)lisp65_ship_timebase_irq;
    scr_init();
    __asm__ volatile("sei" ::: "memory");
    lisp65_ship_frame_lo = 0u;
    lisp65_ship_frame_hi = 0u;
    lisp65_ship_old_irq[0] = *(volatile uint8_t *)0x0314;
    lisp65_ship_old_irq[1] = *(volatile uint8_t *)0x0315;
    lisp65_ship_old_vic_mask = *(volatile uint8_t *)0xd01a;
    *(volatile uint8_t *)0x0314 = (uint8_t)handler;
    *(volatile uint8_t *)0x0315 = (uint8_t)(handler >> 8);
    lisp65_raster_timebase_arm();
    if (!ship_timebase_armed()) {
        ship_timebase_restore();
        return 0u;
    }
    __asm__ volatile("cli" ::: "memory");
    if (ship_frame_prove_progress()) return 1u;
    __asm__ volatile("sei" ::: "memory");
    ship_timebase_restore();
    return 0u;
}

int lisp65_ship_io_getin(uint8_t blocking) {
    int value;
    do {
        lisp_poll();
#ifdef LISP65_SHIP_QUEUE_DIAGNOSTIC
        ship_queue_diag_sample();
#endif
        value = cbm_k_getin();
    } while (blocking && value == 0);
    return value;
}

void lisp65_ship_io_putc(uint8_t code) {
    scr_putc((char)code);
}

uint8_t lisp65_ship_io_peek(uint16_t address, uint8_t *value) {
#ifdef LISP65_SHIP_QUEUE_DIAGNOSTIC
    /* Keep the witness alive even if the sample has not crossed its initial
     * frame wait yet.  This is the same non-consuming sampler as the GETIN
     * edge, not a second queue implementation. */
    ship_queue_diag_sample();
#endif
    /* Same public logical clock as Workbench, composition-owned backing. */
    if (address == 0xff83u) {
        *value = lisp65_ship_frame_lo;
        return 1u;
    }
    if (address == 0xff84u) {
        *value = lisp65_ship_frame_hi;
        return 1u;
    }
    return 0u;
}

uint16_t lisp65_ship_io_frame_count(void) { return ship_frame_read(); }

#else

/* The native host execution is a real VM/bytecode lane.  Only the physical
 * devices are deterministic fixtures: one line for the interactive sample
 * and one raster tick after each complete high/low/high observation. */
static const uint8_t host_input[] = {'A', 'd', 'a', 13};
static uint16_t host_input_pos;
static uint16_t host_output_count;
static uint32_t host_output_hash;
static uint16_t host_frames;
static uint8_t host_clock_armed;
static uint8_t host_clock_verified;
static uint8_t host_input_armed;
static uint8_t host_verified_deltas;

static void host_frame_tick(void) { host_frames++; }

static uint16_t ship_frame_read(void) { return host_frames; }

/* The host witness supplies the complete raster sample and a distinct IRQ
 * pulse.  Ship executes the same 9-bit transition detector as the target;
 * it no longer receives a pre-interpreted logical wrap event. */
static uint16_t ship_raster_read(void) {
    uint16_t event = lisp65_ship_io_host_raster_step();
    if (event & LISP65_SHIP_HOST_RASTER_IRQ) host_frame_tick();
    return event & LISP65_SHIP_HOST_RASTER_MASK;
}

static void host_reference_poll(void) {
    if (host_clock_armed) (void)ship_raster_read();
}

uint8_t lisp65_ship_io_init(void) {
    host_input_pos = 0;
    host_output_count = 0;
    host_output_hash = 2166136261u;
    host_frames = 0;
    host_clock_armed = 0;
    host_clock_verified = 0;
    host_input_armed = 0;
    host_verified_deltas = 0;
    scr_init();
    host_clock_armed = 1u;
    host_input_armed = 1u;
    if (!ship_frame_prove_progress()) return 0u;
    host_verified_deltas = LISP65_SHIP_PROGRESS_DELTAS;
    host_clock_verified = 1u;
    return 1u;
}

int lisp65_ship_io_getin(uint8_t blocking) {
    (void)blocking;
    if (!host_input_armed) return 0;
    if (host_input_pos >= sizeof host_input) return 0;
    return host_input[host_input_pos++];
}

void lisp65_ship_io_putc(uint8_t code) {
    host_output_hash = (host_output_hash ^ code) * 16777619u;
    host_output_count++;
    scr_putc((char)code);
}

uint8_t lisp65_ship_io_peek(uint16_t address, uint8_t *value) {
    host_reference_poll();
    if (address == 0xff84u) {
        *value = (uint8_t)(host_frames >> 8);
        return 1u;
    }
    if (address == 0xff83u) {
        *value = (uint8_t)host_frames;
        return 1u;
    }
    return 0u;
}

uint16_t lisp65_ship_io_frame_count(void) { return ship_frame_read(); }

uint16_t lisp65_ship_io_input_used(void) { return host_input_pos; }
uint16_t lisp65_ship_io_output_count(void) { return host_output_count; }
uint32_t lisp65_ship_io_output_hash(void) { return host_output_hash; }
uint8_t lisp65_ship_io_host_clock_armed(void) { return host_clock_armed; }
uint8_t lisp65_ship_io_host_clock_verified(void) { return host_clock_verified; }
uint8_t lisp65_ship_io_host_input_armed(void) { return host_input_armed; }
uint16_t lisp65_ship_io_host_frame_count(void) { return host_frames; }
uint8_t lisp65_ship_io_host_verified_deltas(void) { return host_verified_deltas; }

#endif
