/* R3 G3 deterministic-media trace wrapper.
 *
 * This translation unit includes the product stager source itself.  Only the
 * F011/SD/DMA boundary is replaced by R3_G3_TRACE; the four emulator-valid
 * stager cases execute the real descriptor, restage, re-verification and
 * chain-control functions.  r3-g3-descriptor-fixture.c is generated from the
 * candidate's SHA-bound boot.id immediately before compilation.
 */
#include <stdint.h>

#ifndef R3_G3_SCENARIO
#error "R3_G3_SCENARIO is required"
#endif

#define R3_G3_TRACE 1
#define main r3_product_main
#include "r3-cold-stager-main.c"
#undef main

extern const uint8_t r3_g3_descriptor_fixture[R3_DESCRIPTOR_BYTES];

static void trace_text(const char *text) {
    volatile uint8_t *out = (volatile uint8_t *)0xc000;
    while (*text) *out++ = (uint8_t)*text++;
    *out = 0;
}

static const char *case_name(void) {
#if R3_G3_SCENARIO == 1
    return "catalog-crc-reject-restage";
#elif R3_G3_SCENARIO == 2
    return "catalog-missing-restage";
#elif R3_G3_SCENARIO == 3
    return "catalog-valid-stage-chain";
#elif R3_G3_SCENARIO == 4
    return "stager-entry-chain-control";
#else
#error "unsupported R3_G3_SCENARIO"
#endif
}

int main(void) {
    uint8_t index;
    uint8_t initial_valid = R3_G3_SCENARIO == 3 ? 1u : 0u;
    uint8_t restaged;
    uint8_t ok = 1;
    uint32_t profile_build_id;
    const uint8_t *product;
    static char pass_line[112];
    char *out = pass_line;
    static const char prefix[] = "G3 PASS ";
    static const char suffix_fast[] = " restage=0 reverify=1 chain=1";
    static const char suffix_stage[] = " restage=1 reverify=1 chain=1";
    const char *text;

    io_enable();
    for (index = 0; index < R3_DESCRIPTOR_BYTES; index++)
        descriptor[index] = r3_g3_descriptor_fixture[index];
    r3_g3_memory_valid = initial_valid;
    r3_g3_disk_valid = 1;
    r3_g3_stage_mask = 0;
    r3_g3_stage_count = 0;
    r3_g3_media_checks = 0;
    r3_g3_product_selected = 0;
    r3_g3_handoffs = 0;

    ok = product_media_identity() && validate_descriptor();
    profile_build_id = rd32(descriptor + 12);
    restaged = staged_state_valid(profile_build_id) ? 0u : 1u;
    if (ok && restaged && !restage_and_reverify(profile_build_id)) ok = 0;
    for (index = 0; ok && index < R3_DESCRIPTOR_RECORDS; index++) {
        const uint8_t *record = record_at(index);
        if (record[0] != R3_ROLE_BANK5 && record[0] != R3_ROLE_ATTIC &&
            record[0] != R3_ROLE_PRODUCT && !disk_record(record, 0)) ok = 0;
    }
    product = find_role(R3_ROLE_PRODUCT);
    if (!product || rd32(product + 4) != R3_PRODUCT_STAGE ||
        !(product[1] & R3_FLAG_PRG) || !disk_record(product, 1) ||
        !staged_state_valid(profile_build_id)) ok = 0;
    if (ok) prepare_chain(product);

    if (r3_g3_handoffs != 1u || r3_g3_product_selected != 1u ||
        r3_g3_media_checks != (uint8_t)(restaged ? 2u : 1u)) ok = 0;
    if (restaged) {
        if (r3_g3_stage_count != 2u || r3_g3_stage_mask != 3u ||
            r3_g3_stage_order[0] != R3_ROLE_BANK5 ||
            r3_g3_stage_order[1] != R3_ROLE_ATTIC) ok = 0;
    } else if (r3_g3_stage_count || r3_g3_stage_mask) ok = 0;

    if (!ok) {
        trace_text("G3 FAIL stager-trace");
        for (;;) __asm__ volatile("nop");
    }
    text = prefix;
    while (*text) *out++ = *text++;
    text = case_name();
    while (*text) *out++ = *text++;
    text = restaged ? suffix_stage : suffix_fast;
    while (*text) *out++ = *text++;
    *out = 0;
    trace_text(pass_line);
    for (;;) __asm__ volatile("nop");
    return 0;
}
