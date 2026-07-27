/* Target-shaped, non-product sizing seams for C2D-v4 nested evaluation.
 *
 * This translation unit is deliberately absent from every product source
 * list.  It prices the owner-authorized placement alternatives with the
 * pinned llvm-mos target compiler while leaving Link 32 and product sources
 * untouched.  External calls model the already existing C2 transport seams;
 * unresolved relocations are retained in the object as provenance.
 */
#include <stdint.h>

#define C2D_IMAGE_CAP 64u
#define C2D_ENTRY_CAP 2048u
#define C2D_ROOT_CAP 1536u
#define C2D_IMAGES_OFFSET 48u
#define C2D_ENTRIES_OFFSET 2096u
#define C2D_ROOTS_OFFSET 30768u
#define C2D_UNWIND_OFFSET 50752u
#define C2D_UNWIND_BYTES 64u
#define C2D_MAX_TRANSIENT_DEPTH 4u

#define PROBE_FN(section_name) \
    __attribute__((noinline, used, section(section_name)))

typedef int16_t probe_obj;

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
extern uint16_t c2_probe_pending_roots;
extern uint8_t c2_probe_c2d_read(uint16_t, void *, uint16_t);
extern uint8_t c2_probe_source_read(const uint8_t *, uint32_t, void *, uint16_t);
extern void c2_probe_gc_mark(probe_obj);
extern uint8_t c2_probe_transaction_begin(uint8_t, uint16_t);
extern uint8_t c2_probe_transaction_end(void);
extern uint8_t c2_probe_mutation_phase(void *);
extern probe_obj c2_probe_execute(uint16_t);
extern uint8_t c2_probe_transient_remove(void *);
extern uint32_t c2_probe_crc32(const void *, uint16_t);
extern uint8_t c2_probe_restore_exports(const uint8_t *);
extern uint8_t c2_probe_restore_ranges(const uint8_t *);
extern uint8_t c2_probe_clear_active_transients(void);
extern void c2_probe_session_invalidate(void);
extern uint8_t c2_probe_overlay_tail_lookup(void *);
extern uint8_t c2_probe_overlay_tail_locate(void *);
extern uint8_t c2_probe_overlay_abort_call(uint8_t, void *);
extern probe_obj c2_probe_intern(const char *);
extern uint8_t c2_probe_emit_reset(void);
extern uint8_t c2_probe_emit_add(probe_obj, probe_obj, uint8_t);
extern uint8_t c2_probe_emit_finalize(uint16_t *);
extern uint8_t c2_probe_append_begin(uint16_t, probe_context *, uint16_t *);
extern uint8_t c2_probe_append_rollback(const probe_context *);
extern uint8_t c2_probe_vm_status;

static uint16_t probe_u16(const uint8_t *p) {
    return (uint16_t)p[0] | (uint16_t)p[1] << 8;
}

static uint32_t probe_u24(const uint8_t *p) {
    return (uint32_t)p[0] | (uint32_t)p[1] << 8 | (uint32_t)p[2] << 16;
}

/* Link-32 algorithm, compiled beside the candidate so the code-size delta is
 * a target-code comparison rather than a host estimate. */
PROBE_FN(".probe.lookup.base")
uint8_t c2_probe_entry_records_v3(uint16_t ordinal, uint8_t directory[10],
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

/* The persistent branch performs the same two reads as Link 32.  A high-tail
 * ordinal validates both edges: directory -> active image slot and active
 * image interval -> ordinal.  It scans no unrelated image record. */
PROBE_FN(".probe.lookup.v4")
uint8_t c2_probe_entry_records_v4(uint16_t ordinal, uint8_t directory[10],
                                  uint8_t image[32], uint8_t entry[16]) {
    uint8_t metadata_header[24], depth, slot, level;
    uint16_t local, entries_offset, base, count;
    uint32_t metadata;
    if (!c2_probe_c2d_read((uint16_t)(c2_probe_runtime.entries_offset
            + ordinal * 10u), directory, 10u)) return 0;
    slot = directory[0];
    if (ordinal < c2_probe_runtime.entry_count) {
        if (slot >= c2_probe_runtime.image_count) return 0;
    } else {
        depth = c2_probe_runtime.transient_depth;
        if (!depth || depth > C2D_MAX_TRANSIENT_DEPTH
            || slot < (uint8_t)(C2D_IMAGE_CAP - depth)
            || slot >= C2D_IMAGE_CAP) return 0;
    }
    if (directory[1] || probe_u16(directory + 8)
        != c2_probe_runtime.generation
        || !c2_probe_c2d_read((uint16_t)(c2_probe_runtime.images_offset
            + slot * 32u), image, 32u)) return 0;
    if (ordinal >= c2_probe_runtime.entry_count) {
        level = (uint8_t)(C2D_IMAGE_CAP - 1u - slot);
        base = probe_u16(image + 6);
        count = probe_u16(image + 8);
        if (image[0] != 2u || image[1] || image[2] != level || image[3]
            || probe_u16(image + 4) != c2_probe_runtime.generation
            || ordinal < base || (uint16_t)(ordinal - base) >= count)
            return 0;
    }
    local = probe_u16(directory + 2);
    metadata = probe_u24(image + 23);
    if (local >= probe_u16(image + 8)
        || !c2_probe_source_read(image, metadata, metadata_header,
                                 sizeof metadata_header)) return 0;
    entries_offset = probe_u16(metadata_header + 14);
    return c2_probe_source_read(image, metadata + entries_offset
                                + (uint32_t)local * 16u, entry, 16u);
}

typedef struct {
    uint16_t ordinal;
    uint8_t *directory;
    uint8_t *image;
    uint8_t *entry;
} probe_tail_lookup_context;

/* Smallest plausible resident change when the Tail resolver is transported
 * as a new Session slice.  It prices the hot persistent branch plus the
 * one-argument overlay context; the Tail implementation itself is charged to
 * its own slice. */
PROBE_FN(".probe.lookup.split-resident")
uint8_t c2_probe_entry_records_v4_split(uint16_t ordinal,
                                        uint8_t directory[10],
                                        uint8_t image[32],
                                        uint8_t entry[16]) {
    probe_tail_lookup_context context;
    uint8_t metadata_header[24];
    uint16_t local, entries_offset;
    uint32_t metadata;
    if (ordinal >= c2_probe_runtime.entry_count) {
        context.ordinal = ordinal;
        context.directory = directory;
        context.image = image;
        context.entry = entry;
        return c2_probe_overlay_tail_lookup(&context);
    }
    if (!c2_probe_c2d_read((uint16_t)(c2_probe_runtime.entries_offset
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

PROBE_FN(".probe.lookup.tail-slice")
uint8_t c2_probe_entry_records_v4_tail(void *opaque) {
    probe_tail_lookup_context *context = opaque;
    uint8_t *directory, *image, depth, slot, level, metadata_header[24];
    uint16_t ordinal, local, entries_offset, base, count;
    uint32_t metadata;
    if (!context) return 0;
    ordinal = context->ordinal;
    directory = context->directory;
    image = context->image;
    depth = c2_probe_runtime.transient_depth;
    if (!depth || depth > C2D_MAX_TRANSIENT_DEPTH
        || !c2_probe_c2d_read((uint16_t)(c2_probe_runtime.entries_offset
            + ordinal * 10u), directory, 10u)) return 0;
    slot = directory[0];
    if (slot < (uint8_t)(C2D_IMAGE_CAP - depth) || slot >= C2D_IMAGE_CAP
        || directory[1] || probe_u16(directory + 8)
            != c2_probe_runtime.generation
        || !c2_probe_c2d_read((uint16_t)(c2_probe_runtime.images_offset
            + slot * 32u), image, 32u)) return 0;
    level = (uint8_t)(C2D_IMAGE_CAP - 1u - slot);
    base = probe_u16(image + 6);
    count = probe_u16(image + 8);
    if (image[0] != 2u || image[1] || image[2] != level || image[3]
        || probe_u16(image + 4) != c2_probe_runtime.generation
        || ordinal < base || (uint16_t)(ordinal - base) >= count) return 0;
    local = probe_u16(directory + 2);
    metadata = probe_u24(image + 23);
    if (local >= count
        || !c2_probe_source_read(image, metadata, metadata_header,
                                 sizeof metadata_header)) return 0;
    entries_offset = probe_u16(metadata_header + 14);
    return c2_probe_source_read(image, metadata + entries_offset
        + (uint32_t)local * 16u, context->entry, 16u);
}

typedef struct {
    uint16_t ordinal;
    uint8_t image_slot;
} probe_tail_locator;

/* Narrower split: the transported side returns only the proven image slot.
 * The resident side then reads the directory and checks its reverse edge to
 * that slot before sharing Link 32's common record path. */
PROBE_FN(".probe.lookup.locator-resident")
uint8_t c2_probe_entry_records_v4_locator(uint16_t ordinal,
                                          uint8_t directory[10],
                                          uint8_t image[32],
                                          uint8_t entry[16]) {
    probe_tail_locator locator;
    uint8_t metadata_header[24], transient = 0;
    uint16_t local, entries_offset;
    uint32_t metadata;
    if (ordinal >= c2_probe_runtime.entry_count) {
        locator.ordinal = ordinal;
        if (!c2_probe_overlay_tail_locate(&locator)) return 0;
        transient = 1;
    }
    if (!c2_probe_c2d_read((uint16_t)(c2_probe_runtime.entries_offset
            + ordinal * 10u), directory, 10u)) return 0;
    if ((transient ? directory[0] != locator.image_slot
                   : directory[0] >= c2_probe_runtime.image_count)
        || directory[1] || probe_u16(directory + 8)
            != c2_probe_runtime.generation) return 0;
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

PROBE_FN(".probe.lookup.tail-locator-slice")
uint8_t c2_probe_entry_records_v4_tail_locator(void *opaque) {
    probe_tail_locator *locator = opaque;
    uint8_t image[32], depth, level;
    uint16_t base, count;
    if (!locator) return 0;
    depth = c2_probe_runtime.transient_depth;
    if (!depth || depth > C2D_MAX_TRANSIENT_DEPTH) return 0;
    for (level = 0; level < depth; ++level) {
        locator->image_slot = (uint8_t)(C2D_IMAGE_CAP - 1u - level);
        if (!c2_probe_c2d_read((uint16_t)(c2_probe_runtime.images_offset
                + locator->image_slot * 32u), image, sizeof image)
            || image[0] != 2u || image[1] || image[2] != level || image[3]
            || probe_u16(image + 4) != c2_probe_runtime.generation) return 0;
        base = probe_u16(image + 6);
        count = probe_u16(image + 8);
        if (locator->ordinal >= base
            && (uint16_t)(locator->ordinal - base) < count) return 1;
    }
    return 0;
}

/* Exact-interval alternative.  Every image descriptor and every root batch
 * is read in a 32-byte B2 block; no root-value DMA is issued. */
PROBE_FN(".probe.gc.exact-tail")
uint8_t c2_probe_gc_exact_high_tail(void) {
    uint8_t image[32], roots[32], depth, level;
    uint16_t base, count, done, n, i;
    depth = c2_probe_runtime.transient_depth;
    if (depth > C2D_MAX_TRANSIENT_DEPTH) return 0;
    for (level = 0; level < depth; ++level) {
        if (!c2_probe_c2d_read((uint16_t)(C2D_IMAGES_OFFSET
                + (C2D_IMAGE_CAP - 1u - level) * 32u), image, sizeof image)
            || image[0] != 2u || image[1] || image[2] != level || image[3]
            || probe_u16(image + 4) != c2_probe_runtime.generation)
            return 0;
        base = probe_u16(image + 14);
        count = probe_u16(image + 16);
        if (base > C2D_ROOT_CAP || count > (uint16_t)(C2D_ROOT_CAP - base))
            return 0;
        for (done = 0; done < count; done = (uint16_t)(done + n)) {
            n = (uint16_t)(count - done);
            if (n > 16u) n = 16u;
            if (!c2_probe_c2d_read((uint16_t)(C2D_ROOTS_OFFSET
                    + (base + done) * 2u), roots, (uint16_t)(n * 2u)))
                return 0;
            for (i = 0; i < n; ++i)
                c2_probe_gc_mark((probe_obj)probe_u16(roots + i * 2u));
        }
    }
    return 1;
}

/* Selected zero-code walker policy: the proven Link-32 B2 loop scans to the
 * high edge while any transient is active.  This helper represents only the
 * control assignment that can be folded into transient publication. */
PROBE_FN(".probe.gc.high-water-control")
void c2_probe_gc_high_water_control(uint8_t transient_depth,
                                    uint16_t persistent_roots) {
    c2_probe_pending_roots = transient_depth ? C2D_ROOT_CAP : persistent_roots;
}

/* Product-shaped serial boundary: mutate under one authenticated transaction,
 * execute with no transaction active, and clean up under a new transaction. */
PROBE_FN(".probe.transaction.serial")
probe_obj c2_probe_serial_transient(uint8_t family, uint16_t generation,
                                    uint16_t ordinal, void *state) {
    probe_obj result;
    if (c2_probe_transaction_begin(family, generation) != 0u
        || !c2_probe_mutation_phase(state)
        || c2_probe_transaction_end() != 0u) return 0;
    result = c2_probe_execute(ordinal);
    if (c2_probe_transaction_begin(family, generation) != 0u
        || !c2_probe_transient_remove(state)
        || c2_probe_transaction_end() != 0u) return 0;
    return result;
}

/* Link-32 transaction lifetime, retained as a same-toolchain baseline. */
PROBE_FN(".probe.install.base")
probe_obj c2_probe_install_v3(probe_obj fnlist, probe_obj definition_name) {
    probe_context before;
    uint16_t length, main;
    uint8_t transient = (uint8_t)(definition_name == c2_probe_intern("t"));
    probe_obj result;
    if (c2_probe_transaction_begin(1u, c2_probe_runtime.generation) != 0u)
        return 0;
    if (c2_probe_emit_reset() != 0u
        || c2_probe_emit_add(fnlist, transient ? 0 : definition_name, 0u) != 0u
        || c2_probe_emit_finalize(&length) != 0u
        || !c2_probe_append_begin(length, &before, &main)) {
        (void)c2_probe_transaction_end();
        c2_probe_vm_status = 1u;
        return 0;
    }
    if (!transient) {
        if (c2_probe_transaction_end() != 0u) return 0;
        return definition_name ? definition_name : (probe_obj)main;
    }
    result = c2_probe_execute(main);
    if (!c2_probe_append_rollback(&before)) {
        (void)c2_probe_transaction_end();
        c2_probe_vm_status = 1u;
        return 0;
    }
    if (c2_probe_transaction_end() != 0u) return 0;
    return result;
}

/* C2D-v4 serial lifetime.  The mutation transaction closes before bytecode
 * runs; Tail removal gets a fresh transaction.  A longjmp is handled by the
 * fixed-journal landing rather than a dead stack checkpoint. */
PROBE_FN(".probe.install.v4")
probe_obj c2_probe_install_v4(probe_obj fnlist, probe_obj definition_name) {
    probe_context before;
    uint16_t length, main;
    uint8_t transient = (uint8_t)(definition_name == c2_probe_intern("t"));
    probe_obj result;
    if (c2_probe_transaction_begin(1u, c2_probe_runtime.generation) != 0u)
        return 0;
    if (c2_probe_emit_reset() != 0u
        || c2_probe_emit_add(fnlist, transient ? 0 : definition_name, 0u) != 0u
        || c2_probe_emit_finalize(&length) != 0u
        || !c2_probe_append_begin(length, &before, &main)
        || c2_probe_transaction_end() != 0u) {
        c2_probe_vm_status = 1u;
        return 0;
    }
    if (!transient)
        return definition_name ? definition_name : (probe_obj)main;
    result = c2_probe_execute(main);
    if (c2_probe_transaction_begin(1u, c2_probe_runtime.generation) != 0u
        || !c2_probe_append_rollback(&before)
        || c2_probe_transaction_end() != 0u) {
        c2_probe_vm_status = 1u;
        return 0;
    }
    return result;
}

/* Longjmp landing.  The fixed Bank-5 journal is fetched as two B2 blocks.
 * No dead C-stack pointer is consumed; invalid identity/range/CRC makes the
 * session unusable instead of attempting guessed cleanup. */
PROBE_FN(".probe.abort.cleanup")
uint8_t c2_probe_abort_cleanup(void) {
    uint8_t journal[C2D_UNWIND_BYTES];
    uint16_t generation, old_depth, target_slot;
    if (!c2_probe_c2d_read(C2D_UNWIND_OFFSET, journal, 32u)
        || !c2_probe_c2d_read(C2D_UNWIND_OFFSET + 32u, journal + 32u, 32u))
        goto invalid;
    if (!(journal[0] | journal[1] | journal[2] | journal[3]))
        return c2_probe_clear_active_transients();
    generation = probe_u16(journal + 8);
    old_depth = probe_u16(journal + 10);
    target_slot = probe_u16(journal + 20);
    if (journal[0] != 'C' || journal[1] != '2' || journal[2] != 'J'
        || journal[3] || journal[4] != 1u || journal[5] != C2D_UNWIND_BYTES
        || !generation || generation != c2_probe_runtime.generation
        || old_depth > C2D_MAX_TRANSIENT_DEPTH || target_slot >= C2D_IMAGE_CAP
        || probe_u16(journal + 22) > C2D_ENTRY_CAP
        || probe_u16(journal + 30) > C2D_ROOT_CAP
        || c2_probe_crc32(journal, 60u)
            != ((uint32_t)journal[60] | (uint32_t)journal[61] << 8
                | (uint32_t)journal[62] << 16 | (uint32_t)journal[63] << 24))
        goto invalid;
    if (!c2_probe_restore_exports(journal)
        || !c2_probe_restore_ranges(journal)
        || !c2_probe_clear_active_transients()) goto invalid;
    return 1;
invalid:
    c2_probe_session_invalidate();
    return 0;
}

/* Resident landing seam; the 709-byte restoration body remains transported. */
PROBE_FN(".probe.abort.facade")
uint8_t c2_probe_abort_facade(void) {
    return c2_probe_overlay_abort_call(36u, (void *)0);
}
