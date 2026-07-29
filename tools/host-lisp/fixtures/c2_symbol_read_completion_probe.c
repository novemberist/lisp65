/* Link-75 non-promotable symbol-read completion probe.
 *
 * This payload replaces only the error-renderer overlay in a diagnostic
 * Session-family identity.  It never ships in a product.  The caller enters
 * through the ordinary L65E context edge after deliberately requesting a
 * missing function; the context itself is irrelevant to this measurement.
 *
 * Safety:
 *   - C2J must be CLEAR and no append/emitter transaction may be live.
 *   - The only Chip-RAM write is [0x8430,0x8470), the Link-75 unpublished
 *     append scratch immediately after the published C2D image.
 *   - Product code, published C2D, symbol cells and Service records are
 *     read-only.
 */
#include <stdint.h>
#include <stddef.h>

#include "eval.h"
#include "obj.h"
#include "symbol.h"

#define PROBE_SECTION \
    __attribute__((section(".lisp65_rt_l65e"), noinline, used))
#define PROBE_DATA \
    __attribute__((section(".lisp65_rt_l65e_data"), used))
#define PROBE_RODATA \
    __attribute__((section(".lisp65_rt_l65e_rodata"), used))

#define PROBE_BATCHES 3u
#define PROBE_ITERATIONS 256u
#define PROBE_BITMAP_BYTES 32u
#define PROBE_RECORD_BYTES 64u
#define PROBE_C2D_SCRATCH 0x8430u
#define PROBE_C2D_MAGIC_WORD 0x3243u
#define PROBE_COMPLETE 0xa5u

enum {
    PROBE_FAIL_NONE = 0u,
    PROBE_FAIL_SINGLE_IMMEDIATE = 1u,
    PROBE_FAIL_SINGLE_SETTLED = 2u,
    PROBE_FAIL_PAIRED_FIRST = 3u,
    PROBE_FAIL_PAIRED_SECOND = 4u,
    PROBE_FAIL_PRIM67 = 5u,
    PROBE_FAIL_RECORD_ROUNDTRIP = 6u,
    PROBE_FAIL_CELL_WORD = 7u
};

typedef struct {
    uint8_t magic[4];
    uint8_t version;
    uint8_t status;
    uint8_t completed_batches;
    uint8_t first_failure_step;
    uint8_t first_failure_batch;
    uint8_t first_failure_iteration;
    uint8_t first_failure_byte;
    uint8_t reserved[5];
    uint8_t prim67_failures[PROBE_BATCHES][PROBE_BITMAP_BYTES];
    uint8_t roundtrip_failures[PROBE_BATCHES][PROBE_BITMAP_BYTES];
    uint8_t cell_failures[PROBE_BATCHES][PROBE_BITMAP_BYTES];
} symbol_read_completion_trace;

_Static_assert(sizeof(symbol_read_completion_trace) == 304u,
               "diagnostic trace must exactly own phase scratch");
_Static_assert(
    offsetof(symbol_read_completion_trace, prim67_failures) == 16u &&
    offsetof(symbol_read_completion_trace, roundtrip_failures) == 112u &&
    offsetof(symbol_read_completion_trace, cell_failures) == 208u,
    "diagnostic trace capture offsets drifted");

typedef struct {
    uint16_t first_expected;
    uint16_t first_observed;
    uint16_t single_immediate_mismatches;
    uint16_t single_settled_mismatches;
    uint16_t paired_first_mismatches;
    uint16_t paired_second_mismatches;
    uint16_t observation_hash[PROBE_BATCHES];
    uint8_t single_immediate[2];
    uint8_t single_settled[2];
    uint8_t paired_first[2];
    uint8_t paired_second[2];
    obj prim67_args[2];
    uint8_t record_buffer[PROBE_RECORD_BYTES];
    obj cell_word;
} symbol_read_completion_witness;

_Static_assert(
    sizeof(symbol_read_completion_witness) == 96u &&
    offsetof(symbol_read_completion_witness,
             single_immediate_mismatches) == 4u &&
    offsetof(symbol_read_completion_witness, observation_hash) == 12u &&
    offsetof(symbol_read_completion_witness, single_immediate) == 18u &&
    offsetof(symbol_read_completion_witness, record_buffer) == 30u &&
    offsetof(symbol_read_completion_witness, cell_word) == 94u,
    "diagnostic witness capture offsets drifted");

volatile symbol_read_completion_witness
    lisp65_symbol_read_completion_witness PROBE_DATA = {0};

extern obj vm_c2d_byte(obj *args);
extern uint8_t lisp65_c2_phase_scratch[304];
extern uint16_t rtov_crc_mem(const uint8_t *bytes, uint16_t length);
extern void c2_facade_target_c2_dma(
    uint16_t source, uint8_t source_bank,
    uint16_t target, uint8_t target_bank, uint16_t length);

static const uint8_t bit_mask[8] PROBE_RODATA =
    {1u, 2u, 4u, 8u, 16u, 32u, 64u, 128u};

static PROBE_SECTION void mark_failure(
        volatile uint8_t bitmap[PROBE_BITMAP_BYTES],
        uint8_t iteration) {
    bitmap[iteration >> 3] |= bit_mask[iteration & 7u];
}

static PROBE_SECTION void first_failure(
        uint8_t step, uint8_t batch, uint8_t iteration, uint8_t byte,
        uint16_t expected, uint16_t observed) {
    volatile symbol_read_completion_trace *trace =
        (volatile symbol_read_completion_trace *)(void *)
            lisp65_c2_phase_scratch;
    volatile symbol_read_completion_witness *w =
        &lisp65_symbol_read_completion_witness;
    if (trace->first_failure_step) return;
    trace->first_failure_step = step;
    trace->first_failure_batch = batch;
    trace->first_failure_iteration = iteration;
    trace->first_failure_byte = byte;
    w->first_expected = expected;
    w->first_observed = observed;
}

static PROBE_SECTION void copy_two_from_c2d(volatile uint8_t *destination) {
    c2_facade_target_c2_dma(
        0u, 5u, (uint16_t)(uintptr_t)destination, 0u, 2u);
}

PROBE_SECTION uint8_t lisp65_error_overlay_entry(void *unused) {
    volatile symbol_read_completion_trace *trace =
        (volatile symbol_read_completion_trace *)(void *)
            lisp65_c2_phase_scratch;
    volatile symbol_read_completion_witness *w =
        &lisp65_symbol_read_completion_witness;
    uint8_t batch;

    (void)unused;
    trace->magic[0] = 'S';
    trace->magic[1] = 'R';
    trace->magic[2] = 'D';
    trace->magic[3] = '2';
    trace->version = 2u;
    trace->status = 0u;
    trace->completed_batches = 0u;
    trace->first_failure_step = 0u;
    trace->first_failure_batch = 0xffu;
    trace->first_failure_iteration = 0xffu;
    trace->first_failure_byte = 0xffu;
    for (batch = 0u; batch < PROBE_BATCHES; ++batch) {
        uint16_t hash = 0x65e2u;
        uint8_t iteration = 0u;
        uint8_t clear = 0u;
        do {
            trace->prim67_failures[batch][clear] = 0u;
            trace->roundtrip_failures[batch][clear] = 0u;
            trace->cell_failures[batch][clear] = 0u;
            ++clear;
        } while (clear < PROBE_BITMAP_BYTES);
        do {
            uint8_t byte;
            uint8_t mismatch = 0u;
            obj result;

            w->single_immediate[0] = 0x5au;
            w->single_immediate[1] = 0xa5u;
            copy_two_from_c2d(w->single_immediate);
            if (w->single_immediate[0] != 0x43u ||
                    w->single_immediate[1] != 0x32u) {
                ++w->single_immediate_mismatches;
            }
            __asm__ volatile(
                "ldx #0\n"
                "1:\n"
                "dex\n"
                "bne 1b\n"
                ::: "x", "memory");
            w->single_settled[0] = w->single_immediate[0];
            w->single_settled[1] = w->single_immediate[1];
            if (w->single_settled[0] != 0x43u ||
                    w->single_settled[1] != 0x32u) {
                ++w->single_settled_mismatches;
            }

            w->paired_first[0] = 0x3cu;
            w->paired_first[1] = 0xc3u;
            w->paired_second[0] = 0x69u;
            w->paired_second[1] = 0x96u;
            copy_two_from_c2d(w->paired_first);
            copy_two_from_c2d(w->paired_second);
            if (w->paired_first[0] != 0x43u ||
                    w->paired_first[1] != 0x32u) {
                ++w->paired_first_mismatches;
            }
            if (w->paired_second[0] != 0x43u ||
                    w->paired_second[1] != 0x32u) {
                ++w->paired_second_mismatches;
            }

            w->prim67_args[0] = MKFIX(0);
            w->prim67_args[1] = MKFIX(0);
            result = vm_c2d_byte((obj *)(void *)w->prim67_args);
            if (result != MKFIX(0x43)) {
                mark_failure(trace->prim67_failures[batch], iteration);
                first_failure(
                    PROBE_FAIL_PRIM67, batch, iteration, 0u,
                    (uint16_t)MKFIX(0x43), (uint16_t)result);
            }
            for (byte = 0u; byte < PROBE_RECORD_BYTES; ++byte) {
                uint8_t value =
                    (uint8_t)(0xa5u ^ iteration ^ (uint8_t)(byte * 3u));
                w->record_buffer[byte] = value;
            }
            c2_facade_target_c2_dma(
                (uint16_t)(uintptr_t)w->record_buffer, 0u,
                PROBE_C2D_SCRATCH, 5u, PROBE_RECORD_BYTES);
            for (byte = 0u; byte < PROBE_RECORD_BYTES; ++byte)
                w->record_buffer[byte] =
                    (uint8_t)~(0xa5u ^ iteration ^
                               (uint8_t)(byte * 3u));
            c2_facade_target_c2_dma(
                PROBE_C2D_SCRATCH, 5u,
                (uint16_t)(uintptr_t)w->record_buffer, 0u,
                PROBE_RECORD_BYTES);
            for (byte = 0u; byte < PROBE_RECORD_BYTES; ++byte) {
                uint8_t expected =
                    (uint8_t)(0xa5u ^ iteration ^ (uint8_t)(byte * 3u));
                uint8_t observed = w->record_buffer[byte];
                if (observed != expected && !mismatch) {
                    mismatch = 1u;
                    first_failure(
                        PROBE_FAIL_RECORD_ROUNDTRIP, batch, iteration,
                        byte, expected, observed);
                }
            }
            if (mismatch)
                mark_failure(trace->roundtrip_failures[batch], iteration);

            w->cell_word = sym_value(lisp_t);
            if (w->cell_word != lisp_t) {
                mark_failure(trace->cell_failures[batch], iteration);
                first_failure(
                    PROBE_FAIL_CELL_WORD, batch, iteration, 0u,
                    (uint16_t)lisp_t, (uint16_t)w->cell_word);
            }
            hash = (uint16_t)((hash << 1) | (hash >> 15));
            hash ^= (uint16_t)result;
            hash ^= rtov_crc_mem(
                (const uint8_t *)(const void *)w->record_buffer,
                PROBE_RECORD_BYTES);
            hash ^= (uint16_t)w->cell_word;
            hash ^= iteration;
            ++iteration;
        } while (iteration);
        w->observation_hash[batch] = hash;
        trace->completed_batches = (uint8_t)(batch + 1u);
    }
    trace->status = PROBE_COMPLETE;
    __asm__ volatile("sei" ::: "memory");
    for (;;) { }
}
