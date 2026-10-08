/* generated C2-lite C2D-v6 hot materializer; non-product probe */
#include "c2-stream-v2-decoder.h"
#include "obj.h"
#ifdef C2_STREAM_PRODUCT_V3
#ifdef LISP65_RUNTIME_OVERLAY
#define C2_HOT __attribute__((noinline, used, section(".lisp65_resident_island")))
#else
#define C2_HOT
#endif
extern uint8_t c2_product_entry_record(uint16_t, uint8_t[10], uint16_t *);
static uint16_t hot_u16(const uint8_t *p) {
    return (uint16_t)p[0] | (uint16_t)p[1] << 8;
}
#ifdef LISP65_C2_NESTED_APPEND_V5
C2_HOT uint16_t c2_product_handle_normalize(c2_stream_context *c,
                                             uint16_t handle) {
    if (!c || handle >= 4096u) return 0xffffu;
    if (handle < 2048u) return handle < c->entry_count ? handle : 0xffffu;
    if (handle < c->entry_first) return 0xffffu;
    return (uint16_t)(handle - 2048u);
}
#endif
C2_HOT uint8_t c2_stream_product_materialize_entry(
        c2_stream_context *c, uint16_t ordinal, uint16_t *hot,
        uint8_t capacity, uint8_t *hot_count) {
    uint8_t row[10], b[2], count, i, transient;
    uint16_t physical, word, root, base, resolution_limit, root_limit;
    if (!c || !hot || !hot_count || !c->finished || c->phase != 13u)
        return C2_STREAM_ERR_STATE;
    *hot_count = 0; transient = (uint8_t)(ordinal >= 2048u);
    if (!c2_product_entry_record(ordinal, row, &physical))
        return C2_STREAM_ERR_ENTRY;
    (void)physical; count = row[1]; base = hot_u16(row + 6);
    resolution_limit = transient ? 4096u : c->resolution_count;
    root_limit = transient ? 1536u : c->c2_root_count;
    if (count > capacity || base > resolution_limit
        || count > (uint16_t)(resolution_limit - base))
        return C2_STREAM_ERR_ENTRY;
    for (i = 0; i < count; ++i) {
        if (!c2_stream_c2d_read((uint16_t)(c->resolutions_offset
                + (base + i) * 2u), b, 2u)) return C2_STREAM_ERR_IO;
        word = hot_u16(b);
        if (word && word < 0x8000u && !(word & 1u)) {
            root = (uint16_t)((word >> 1) - 1u);
            if (root >= root_limit
                || !c2_stream_c2d_read((uint16_t)(c->roots_offset
                    + root * 2u), b, 2u)) return C2_STREAM_ERR_RESOLUTION;
            word = hot_u16(b);
            if (!word || word >= 0x8000u || (word & 1u))
                return C2_STREAM_ERR_RESOLUTION;
        }
        hot[i] = word; ++*hot_count;
    }
    return C2_STREAM_OK;
}
#endif
