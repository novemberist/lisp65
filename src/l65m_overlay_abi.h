/* ABI shared by the resident L65M work block and on-demand validator slices. */
#ifndef LISP65_L65M_OVERLAY_ABI_H
#define LISP65_L65M_OVERLAY_ABI_H

#include "l65m_validate.h"

#define L65M_OVERLAY_ABI_VERSION 2u
#define L65M_OVERLAY_COOKIE_BASE 0x65a0u
/* Covers the 319-entry/854-literal product while bounding a stuck phase. */
#define L65M_OVERLAY_REPEAT_LIMIT 65535u

typedef enum {
    L65M_OV_TRANSPORT_OK = 0,
    L65M_OV_TRANSPORT_CONTEXT = 1,
    L65M_OV_TRANSPORT_ABI = 2,
    L65M_OV_TRANSPORT_COOKIE = 3,
    L65M_OV_TRANSPORT_REENTRY = 4,
    L65M_OV_TRANSPORT_PHASE = 5,
    L65M_OV_TRANSPORT_REPEAT_LIMIT = 6
} l65m_overlay_transport_status;

enum {
    L65M_PHASE_00_CONTAINER = 0,
    L65M_PHASE_01_HEADER,
    L65M_PHASE_02_SECTIONS,
    L65M_PHASE_03_STRINGS,
    L65M_PHASE_04_ENTRIES,
    L65M_PHASE_05_ENTRY_NAMES,
    L65M_PHASE_06_CODE,
    L65M_PHASE_07_INDICES,
    L65M_PHASE_08_NODES,
    L65M_PHASE_09_NODE_STRINGS,
    L65M_PHASE_10_GRAPH,
    L65M_PHASE_11_PATCHES,
    L65M_PHASE_12_ROOT_KEEP_COST,
    L65M_PHASE_13_TOPOLOGY_COST,
    L65M_PHASE_14_STRING_COST,
    L65M_PHASE_15_ENTRY_SYMBOLS,
    L65M_PHASE_16_NODE_SYMBOLS,
    L65M_PHASE_17_NODE_ENTRY_DEDUP,
    L65M_PHASE_18_IMPLICIT_SYMBOLS,
    L65M_PHASE_19_TABLE_CAPACITIES,
    L65M_PHASE_20_MEMORY_CAPACITIES,
    L65M_OVERLAY_PHASE_COUNT
};

typedef struct {
    uint16_t abi_version;
    uint16_t cookie;
    uint8_t context_size;
    uint8_t expected_phase;
    uint8_t busy;
    uint8_t transport_status;
    uint8_t validation_status;
    uint8_t finished;
    uint8_t repeat_phase;
    uint16_t repeat_count;
    const l65m_source *source_ref;
    const l65m_limits *limits_ref;
    l65m_plan *plan_ref;

    uint16_t entry_end;
    uint16_t macro_cells;
    uint16_t heap_total;
    uint16_t arena_total;
    uint16_t arena_available;
    uint16_t symbols_total;
    uint16_t name_bytes_total;
    uint16_t *cost_total_ref;
    uint16_t cost_cap;
    uint8_t flags;
    uint8_t byte_cursor;
    uint8_t cost_extra;
    uint16_t cursor_a;
    uint16_t cursor_b;

} l65m_overlay_work;

#define L65M_OVERLAY_CONTEXT_SIZE ((uint8_t)sizeof(l65m_overlay_work))

#ifdef __mos__
_Static_assert(sizeof(l65m_overlay_work) <= 48u, "L65M overlay work ABI exceeds 48 bytes");
#endif

typedef uint8_t (*l65m_overlay_entry_fn)(void *context);

void l65m_overlay_work_init(l65m_overlay_work *work, const l65m_source *source,
                            uint16_t code_base, const l65m_limits *limits,
                            l65m_plan *plan);
uint8_t l65m_overlay_guard(void *context, uint8_t phase, uint8_t status, uint8_t leaving);
uint8_t l65m_overlay_record(void *context, uint8_t kind, uint16_t index, void *dst);
uint8_t l65m_overlay_metadata(void *context, uint16_t off, void *dst, uint16_t length);

uint8_t l65m_overlay_phase_00(void *context);
uint8_t l65m_overlay_phase_01(void *context);
uint8_t l65m_overlay_phase_02(void *context);
uint8_t l65m_overlay_phase_03(void *context);
uint8_t l65m_overlay_phase_04(void *context);
uint8_t l65m_overlay_phase_05(void *context);
uint8_t l65m_overlay_phase_06(void *context);
uint8_t l65m_overlay_phase_07(void *context);
uint8_t l65m_overlay_phase_08(void *context);
uint8_t l65m_overlay_phase_09(void *context);
uint8_t l65m_overlay_phase_10(void *context);
uint8_t l65m_overlay_phase_11(void *context);
uint8_t l65m_overlay_phase_12(void *context);
uint8_t l65m_overlay_phase_13(void *context);
uint8_t l65m_overlay_phase_14(void *context);
uint8_t l65m_overlay_phase_15(void *context);
uint8_t l65m_overlay_phase_16(void *context);
uint8_t l65m_overlay_phase_17(void *context);
uint8_t l65m_overlay_phase_18(void *context);
uint8_t l65m_overlay_phase_19(void *context);
uint8_t l65m_overlay_phase_20(void *context);

#endif /* LISP65_L65M_OVERLAY_ABI_H */
