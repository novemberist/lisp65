#ifndef LISP65_C2_STREAM_DECODER_H
#define LISP65_C2_STREAM_DECODER_H

#include <stdint.h>

/*
 * Product-shaped C2.1 decoder state.  The runtime-overlay transport owns one
 * instance and passes it unchanged between phases.  No pointer into immutable
 * Attic data or the mutable Bank-5 plane is retained here.
 */
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
#ifdef C2_STREAM_PRODUCT_V3
    uint16_t roots_offset;
#endif
    uint16_t image_cursor;
    uint16_t entry_cursor;
    uint16_t resolution_cursor;
    uint16_t pair_depth_max;
    /* A session append validates and resolves only the newly staged suffix.
     * These four cursors are zero for the immutable boot decode.  Keeping the
     * suffix bounds in the shared decoder context prevents an append-only
     * "mini decoder" from becoming a second format truth. */
    uint16_t image_first;
    uint16_t entry_first;
    uint16_t resolution_first;
    uint16_t root_first;
    uint8_t phase;
    uint8_t finished;
    uint8_t error;
    uint8_t reserved;
} c2_stream_context;

/* Product-only phase-06a failure provenance.  The split already owns
 * reserved as its 0 -> 0x6a handoff byte; intermediate values name the last
 * read class attempted and survive fail-closed unwind without new state. */
#define LISP65_C2_PHASE_06A_CUT_IMAGE_RECORD 0x61u
#define LISP65_C2_PHASE_06A_CUT_METADATA_HEADER 0x62u
#define LISP65_C2_PHASE_06A_CUT_ENTRY_RECORD 0x63u
#define LISP65_C2_PHASE_06A_CUT_CODE_HEADER 0x64u
#define LISP65_C2_PHASE_06A_CUT_LITERAL_BLOCK 0x65u
#define LISP65_C2_PHASE_06A_COMPLETE 0x6au

/*
 * The root count/cursor reuse two transport fields that phases 1--6 leave
 * untouched.  Keep the alias in the common header for the C2D-v3 phase-00
 * translation unit; C2D-v2 proof builds receive the same aliases through the
 * v2 header below.
 */
#ifdef C2_STREAM_PRODUCT_V3
#define c2_root_count image_cursor
#define c2_root_cursor pair_depth_max
#endif

enum {
    C2_STREAM_OK = 0,
    C2_STREAM_ERR_IO = 1,
    C2_STREAM_ERR_SHELF = 2,
    C2_STREAM_ERR_C2D = 3,
    C2_STREAM_ERR_C2I = 4,
    C2_STREAM_ERR_ENTRY = 5,
    C2_STREAM_ERR_DESCRIPTOR = 6,
    C2_STREAM_ERR_RESOLUTION = 7,
    C2_STREAM_ERR_STATE = 8,
    C2_STREAM_ERR_FAMILY_STAGE = 9,
    C2_STREAM_ERR_CODE_STAGE = 10
};

/*
 * These five operations are the product seam.  C2.1 host and target proofs
 * provide bounded implementations; C2.2 binds them to Enhanced DMA, the
 * Bank-5 mutable plane and the runtime object allocator.
 */
uint8_t c2_stream_shelf_read(uint32_t offset, void *dst, uint16_t length);
uint8_t c2_stream_c2d_read(uint16_t offset, void *dst, uint16_t length);
uint8_t c2_stream_c2d_write(uint16_t offset, const void *src, uint16_t length);
/*
 * Kind 3 materializes one string value.  Kinds 5 and 8 must resolve through
 * the canonical symbol interner: equal byte spellings have equal identity.
 * Kind 5 additionally requires compiler-proven exported-call resolution;
 * kind 8 is a data symbol and is invisible to call-graph consumers.
 */
uint8_t c2_stream_name_value(uint8_t kind, uint32_t shelf_offset,
                             uint16_t length, uint16_t *value);
uint8_t c2_stream_pair_value(uint16_t car, uint16_t cdr, uint16_t *value);

#ifdef C2_STREAM_PRODUCT_V3
/* Product-only immutable helpers live in the owned $e000 resident domain.
 * Keeping them outside the transported phase payloads lets the already
 * proven whole-phase decoder fit the 1792-byte overlay cap without weakening
 * any catalog, record or payload verification. */
uint8_t c2_stream_product_image_read(c2_stream_context *context,
                                     uint16_t image, uint8_t out[20]);
#ifdef LISP65_C2_LITE_COLD_EVICTION
/* Phase 04's cold, co-resident append-source barrier.  The implementation
 * consumes the one active transaction rather than carrying a second seal in
 * the decoder context. */
uint8_t c2_append_source_domain_guard(const c2_stream_context *context);
#endif
uint8_t c2_stream_product_string_record_any(uint32_t pool,
                                             uint16_t pool_bytes,
                                             uint32_t wanted,
                                             uint16_t *length,
                                             uint32_t *payload);
uint8_t c2_stream_product_string_record(uint32_t pool,
                                         uint16_t pool_bytes,
                                         uint32_t wanted,
                                         uint16_t expected,
                                         uint32_t *payload);
uint8_t c2_stream_product_canonical_name(uint32_t shelf_offset,
                                          uint16_t length);
#ifndef LISP65_C2_LITE_COLD_EVICTION
uint8_t c2_stream_product_child_value(c2_stream_context *context,
                                       uint32_t metadata,
                                       uint16_t literals_offset,
                                       uint16_t resolution_base,
                                       uint16_t local,
                                       uint16_t *value);
/* The sole product entry-record and hot-literal seams.  Both phase 13 and the
 * VM refill path call the same entry-level materializer; neither may carry a
 * private record walker or descriptor interpreter. */
uint8_t c2_entry_records(uint16_t ordinal, uint8_t directory[10],
                         uint8_t image[32], uint8_t entry[16]);
#endif
#ifdef LISP65_C2_NESTED_APPEND_V5
uint16_t c2_product_handle_normalize(c2_stream_context *context,
                                     uint16_t handle);
#endif
uint8_t c2_stream_product_materialize_entry(
        c2_stream_context *context, uint16_t ordinal,
        uint16_t *hot_values, uint8_t hot_capacity, uint8_t *hot_count);
#endif

void c2_stream_init(c2_stream_context *context, uint32_t shelf_bytes,
                    uint16_t c2d_bytes);
uint8_t c2_stream_phase_00(void *context);
uint8_t c2_stream_phase_00b(void *context);
uint8_t c2_stream_phase_01(void *context);
uint8_t c2_stream_phase_02(void *context);
uint8_t c2_stream_phase_02a(void *context);
uint8_t c2_stream_phase_02b(void *context);
uint8_t c2_stream_phase_03(void *context);
uint8_t c2_stream_phase_03b(void *context);
uint8_t c2_stream_phase_04(void *context);
uint8_t c2_stream_phase_05(void *context);
uint8_t c2_stream_phase_06(void *context);
uint8_t c2_stream_phase_06a(void *context);
uint8_t c2_stream_phase_06b(void *context);
uint8_t c2_stream_phase_07(void *context);
uint8_t c2_stream_phase_08(void *context);
uint8_t c2_stream_phase_09(void *context);

#endif
