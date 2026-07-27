/* One product truth for resolving and materializing C2 hot literals.
 *
 * The VM refill seam and transported phase 13 deliberately share these
 * functions.  The helper reads only the identity- and generation-bound
 * immutable descriptor stream plus the canonical C2D resolution/root planes;
 * it does not cache a second value representation.
 */
#include "c2-stream-v2-decoder.h"
#include "obj.h"

#ifdef C2_STREAM_PRODUCT_V3

#ifdef LISP65_RUNTIME_OVERLAY
#define C2_HOT_MATERIALIZER \
    __attribute__((noinline, used, section(".lisp65_resident_island")))
#else
#define C2_HOT_MATERIALIZER
#endif

static uint16_t hot_u16(const uint8_t *p) {
    return (uint16_t)p[0] | (uint16_t)p[1] << 8;
}

static uint32_t hot_u24(const uint8_t *p) {
    return (uint32_t)p[0] | (uint32_t)p[1] << 8 | (uint32_t)p[2] << 16;
}

#ifdef LISP65_C2_NESTED_APPEND_V5
/* The v5 high namespace is encoded in the 12-bit BCODE handle itself.  The
 * context field mirrors the authenticated header watermark after publish;
 * no Tail locator or second directory representation exists. */
C2_HOT_MATERIALIZER uint16_t c2_product_handle_normalize(
        c2_stream_context *c, uint16_t handle) {
    if (!c || handle >= 4096u) return 0xffffu;
    if (handle < 2048u)
        return handle < c->entry_count ? handle : 0xffffu;
    if (handle < c->entry_first) return 0xffffu;
    return (uint16_t)(handle - 2048u);
}
#endif

C2_HOT_MATERIALIZER uint8_t c2_stream_product_materialize_entry(
        c2_stream_context *c, uint16_t ordinal,
        uint16_t *hot, uint8_t capacity, uint8_t *hot_count) {
    uint8_t directory[10], image[32], metadata_header[24], entry[16];
    uint32_t meta;
    uint16_t literals_offset, literal_count, resolution_base, first;
    uint8_t count;
    uint16_t i;
    if (!c || !hot || !hot_count || !c->finished || c->phase != 13u)
        return C2_STREAM_ERR_STATE;
    *hot_count = 0;
    if (!c2_entry_records(ordinal, directory, image, entry))
        return C2_STREAM_ERR_ENTRY;
    meta = hot_u24(image + 23);
    if (!c2_stream_shelf_read(meta | (image[0] ? 0x800000UL : 0u),
                              metadata_header, sizeof metadata_header))
        return C2_STREAM_ERR_IO;
    if (image[0]) meta |= 0x800000UL;
    literals_offset = hot_u16(metadata_header + 16);
    literal_count = hot_u16(metadata_header + 12);
    resolution_base = hot_u16(image + 10);
    first = hot_u16(entry + 5); count = entry[7];
    if (count > capacity || first > literal_count
        || count > (uint16_t)(literal_count - first)
        || resolution_base > (image[0] == 2u ? 4096u : c->resolution_count)
        || first > (uint16_t)((image[0] == 2u ? 4096u : c->resolution_count)
                              - resolution_base)
        || count > (uint16_t)((image[0] == 2u ? 4096u : c->resolution_count)
                              - resolution_base - first))
        return C2_STREAM_ERR_ENTRY;
    for (i = 0; i < count; ++i) {
        if (!c2_stream_product_child_value(
                c, meta, literals_offset, resolution_base,
                (uint16_t)(first + i), hot + i)) return C2_STREAM_ERR_IO;
        ++*hot_count;
    }
    return C2_STREAM_OK;
}

#endif
