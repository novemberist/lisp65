/* Stable shared-library seam for the host L65M before/after verdict diff. */
#include <stdint.h>
#include <string.h>

#include "l65m_validate.h"

enum { L65M_VERDICT_SUMMARY_WORDS = 30 };
enum {
    L65M_EXISTS_NONE = 0,
    L65M_EXISTS_SOME = 1,
    L65M_EXISTS_ALL = 2
};
enum {
    L65M_CAP_GENEROUS = 0,
    L65M_CAP_SYMBOL_UNDER = 1,
    L65M_CAP_SYMBOL_EXACT = 2,
    L65M_CAP_SYMBOL_OVER = 3,
    L65M_CAP_NAMEPOOL_UNDER = 4,
    L65M_CAP_NAMEPOOL_EXACT = 5,
    L65M_CAP_NAMEPOOL_OVER = 6
};

typedef struct {
    const uint8_t *data;
    uint16_t length;
} bytes_source;

static uint8_t read_bytes(void *opaque, uint16_t off, uint8_t *dst, uint16_t len) {
    bytes_source *source = (bytes_source *)opaque;
    if (off > source->length || len > (uint16_t)(source->length - off)) return 0;
    if (len) memcpy(dst, source->data + off, len);
    return 1;
}

static uint8_t configured_symbol_exists(void *opaque, const char *name) {
    const uint8_t mode = *(const uint8_t *)opaque;
    if (mode == L65M_EXISTS_ALL) return 1;
    if (mode == L65M_EXISTS_SOME)
        return (uint8_t)(((uint8_t)name[0] & 1u) != 0);
    return 0;
}

uint8_t l65m_verdict_diff_run(const uint8_t *data, uint16_t length,
                              uint8_t exists_mode, uint8_t capacity_mode,
                              uint16_t *summary, uint16_t summary_words) {
    bytes_source bytes = { data, length };
    l65m_source source = { read_bytes, &bytes, length };
    l65m_limits limits;
    l65m_plan plan;
    l65m_status status;

    uint16_t required_symbols, required_name_bytes;

    if (exists_mode > L65M_EXISTS_ALL || capacity_mode > L65M_CAP_NAMEPOOL_OVER)
        return L65M_ERR_ARGUMENT;
    memset(&limits, 0, sizeof limits);
    limits.dir_capacity = 4095;
    limits.symbol_capacity = 65535;
    limits.namepool_capacity = 65535;
    limits.heap_free = 65535;
    limits.arena_capacity = 65535;
    limits.roots_capacity = 255;
    limits.string_arena = 1;
    limits.symbol_exists = configured_symbol_exists;
    limits.symbol_ctx = &exists_mode;
    memset(&plan, 0, sizeof plan);
    status = l65m_validate(&source, 0, &limits, &plan);
    required_symbols = plan.new_symbols;
    required_name_bytes = plan.new_name_bytes;

    if (status == L65M_OK && capacity_mode != L65M_CAP_GENEROUS) {
        if (capacity_mode == L65M_CAP_SYMBOL_UNDER)
            limits.symbol_capacity = required_symbols ? (uint16_t)(required_symbols - 1u) : 0u;
        else if (capacity_mode == L65M_CAP_SYMBOL_EXACT)
            limits.symbol_capacity = required_symbols;
        else if (capacity_mode == L65M_CAP_SYMBOL_OVER)
            limits.symbol_capacity = required_symbols == 0xffffu
                                   ? required_symbols : (uint16_t)(required_symbols + 1u);
        else if (capacity_mode == L65M_CAP_NAMEPOOL_UNDER)
            limits.namepool_capacity = required_name_bytes
                                     ? (uint16_t)(required_name_bytes - 1u) : 0u;
        else if (capacity_mode == L65M_CAP_NAMEPOOL_EXACT)
            limits.namepool_capacity = required_name_bytes;
        else
            limits.namepool_capacity = required_name_bytes == 0xffffu
                                     ? required_name_bytes
                                     : (uint16_t)(required_name_bytes + 1u);
        memset(&plan, 0, sizeof plan);
        status = l65m_validate(&source, 0, &limits, &plan);
    }

    if (summary && summary_words >= L65M_VERDICT_SUMMARY_WORDS) {
        summary[0] = plan.source_length;
        summary[1] = plan.source_crc16;
        summary[2] = plan.source_blob_off;
        summary[3] = plan.source_metadata_off;
        summary[4] = plan.code_base;
        summary[5] = plan.blob_len;
        summary[6] = plan.metadata_len;
        summary[7] = plan.entry_count;
        summary[8] = plan.index_count;
        summary[9] = plan.node_count;
        summary[10] = plan.patch_count;
        summary[11] = plan.entries_off;
        summary[12] = plan.index_off;
        summary[13] = plan.nodes_off;
        summary[14] = plan.patches_off;
        summary[15] = plan.strings_off;
        summary[16] = plan.strings_bytes;
        summary[17] = plan.dir_before;
        summary[18] = plan.dir_after;
        summary[19] = plan.symbols_before;
        summary[20] = plan.namepool_before;
        summary[21] = plan.heap_free_before;
        summary[22] = plan.arena_used_before;
        summary[23] = plan.roots_before;
        summary[24] = plan.new_symbols;
        summary[25] = plan.new_name_bytes;
        summary[26] = plan.heap_cells;
        summary[27] = plan.arena_bytes;
        summary[28] = plan.root_slots;
        summary[29] = plan.max_graph_depth;
    }
    return (uint8_t)status;
}
