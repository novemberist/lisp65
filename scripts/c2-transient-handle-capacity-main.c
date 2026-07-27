/* Target-shaped, non-product sizing seam for the C2D transient-handle
 * contract.  This translation unit is deliberately absent from every
 * product source list.  It compares Link-32's persistent-only entry lookup
 * with the proposed 12-bit low/high handle normalization using the pinned
 * llvm-mos target compiler.
 */
#include <stdint.h>

#define C2D_ENTRY_CAP 2048u
#define C2D_HANDLE_CAP 4096u

#define PROBE_FN(section_name) \
    __attribute__((noinline, used, section(section_name)))

typedef struct {
    uint32_t shelf_bytes;
    uint32_t catalog_crc32;
    uint16_t c2d_bytes;
    uint16_t generation;
    uint16_t image_count;
    uint16_t entry_count;
    uint16_t resolution_count;
    uint16_t images_offset;
    uint16_t entries_offset;
    uint16_t resolutions_offset;
    uint16_t roots_offset;
    uint16_t root_count;
    uint16_t entry_cursor;
    uint16_t resolution_cursor;
    uint16_t root_cursor;
    uint16_t image_first;
    uint16_t entry_first;
    uint16_t resolution_first;
    uint16_t root_first;
    uint8_t phase;
    uint8_t finished;
    uint8_t error;
    uint8_t transient_depth;
} probe_context;

extern probe_context c2_probe_runtime;
extern uint16_t c2_probe_transient_watermark;
extern uint8_t c2_probe_c2d_read(uint16_t, void *, uint16_t);
extern uint8_t c2_probe_source_read(const uint8_t *, uint32_t, void *, uint16_t);

static uint16_t probe_u16(const uint8_t *p) {
    return (uint16_t)p[0] | (uint16_t)p[1] << 8;
}

static uint32_t probe_u24(const uint8_t *p) {
    return (uint32_t)p[0] | (uint32_t)p[1] << 8 | (uint32_t)p[2] << 16;
}

/* Link-32 algorithm, retained as the calibration baseline. */
PROBE_FN(".probe.handle.lookup-base")
uint8_t c2_probe_entry_records_base(uint16_t ordinal, uint8_t directory[10],
                                    uint8_t image[32], uint8_t entry[16]) {
    uint8_t metadata_header[24];
    uint16_t local, entries_offset;
    uint32_t metadata;
    if (ordinal >= c2_probe_runtime.entry_count
        || !c2_probe_c2d_read((uint16_t)(c2_probe_runtime.entries_offset
            + ordinal * 10u), directory, 10u)) return 0;
    if (directory[0] >= c2_probe_runtime.image_count || directory[1]
        || probe_u16(directory + 8) != c2_probe_runtime.generation) return 0;
    if (!c2_probe_c2d_read((uint16_t)(c2_probe_runtime.images_offset
        + directory[0] * 32u), image, 32u)) return 0;
    local = probe_u16(directory + 2);
    metadata = probe_u24(image + 23);
    if (local >= probe_u16(image + 8)
        || !c2_probe_source_read(image, metadata, metadata_header,
                                 sizeof metadata_header)) return 0;
    entries_offset = probe_u16(metadata_header + 14);
    return c2_probe_source_read(image, metadata + entries_offset
                                + (uint32_t)local * 16u, entry, 16u);
}

/* Publish/remove control seam.  A single watermark store is the
 * visibility marker; the real implementation must perform it inside the
 * existing non-GC-interruptible publication/abort critical section. */
PROBE_FN(".probe.handle.state-publish")
void c2_probe_handle_state_publish(uint16_t depth, uint16_t count) {
    (void)depth;
    c2_probe_transient_watermark = (uint16_t)(C2D_HANDLE_CAP - count);
}

/* Island-shaped normalization candidate.  0xffff is outside the 12-bit
 * BCODE namespace and is therefore an unambiguous invalid result. */
PROBE_FN(".probe.handle.normalizer")
uint16_t c2_probe_handle_normalize(uint16_t handle) {
    if (handle < C2D_ENTRY_CAP)
        return handle < c2_probe_runtime.entry_count ? handle : 0xffffu;
    /* Callers pass BCODE_IDX, whose type gate already proves 0..4095. */
    if (handle < c2_probe_transient_watermark) return 0xffffu;
    return (uint16_t)(handle - C2D_ENTRY_CAP);
}

/* Same common record path as Link 32; only the old ordinal<count predicate
 * becomes one fixed-Island call and one sentinel check. */
PROBE_FN(".probe.handle.lookup-normalized")
uint8_t c2_probe_entry_records_normalized(uint16_t handle,
                                          uint8_t directory[10],
                                          uint8_t image[32],
                                          uint8_t entry[16]) {
    uint8_t metadata_header[24];
    uint16_t ordinal, local, entries_offset;
    uint32_t metadata;
    ordinal = c2_probe_handle_normalize(handle);
    if (ordinal == 0xffffu
        || !c2_probe_c2d_read((uint16_t)(c2_probe_runtime.entries_offset
            + ordinal * 10u), directory, 10u)) return 0;
    if (directory[1]
        || probe_u16(directory + 8) != c2_probe_runtime.generation) return 0;
    if (!c2_probe_c2d_read((uint16_t)(c2_probe_runtime.images_offset
        + directory[0] * 32u), image, 32u)) return 0;
    local = probe_u16(directory + 2);
    metadata = probe_u24(image + 23);
    if (local >= probe_u16(image + 8)
        || !c2_probe_source_read(image, metadata, metadata_header,
                                 sizeof metadata_header)) return 0;
    entries_offset = probe_u16(metadata_header + 14);
    return c2_probe_source_read(image, metadata + entries_offset
                                + (uint32_t)local * 16u, entry, 16u);
}
