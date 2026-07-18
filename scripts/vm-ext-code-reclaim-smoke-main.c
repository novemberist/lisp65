/* Host smoke for the runtime disk-lib reclaim protocol.
 *
 * This links the real vm_ext_code_alloc implementation and exercises the exact
 * preview -> stage/load -> blob-only commit orchestration used by io.c. Device
 * I/O and io_disk_lib_staged itself are deliberately not part of this test.
 */
#include <stdint.h>
#include <stdio.h>

#include "vm_embed.h"

static unsigned stage_calls;
static unsigned load_calls;
static uint8_t load_result;
static uint8_t interleave_persistent_alloc;
static uint16_t interleave_at;

static void mock_stage(uint16_t base, uint16_t total) {
    (void)base;
    (void)total;
    stage_calls++;
}

static uint8_t mock_load(void) {
    load_calls++;
    if (interleave_persistent_alloc)
        interleave_at = vm_ext_code_alloc(1, 1);
    return load_result;
}

static uint8_t install_staged_lib(uint16_t blob_len, uint16_t metadata_len) {
    uint32_t total = (uint32_t)blob_len + metadata_len;
    uint16_t base;

    if (total > 0xffffu) return 0;
    base = vm_ext_code_alloc((uint16_t)total, 0);
    if (base == 0xffffu) return 0;
    mock_stage(base, (uint16_t)total);
    if (!mock_load()) return 0;
    return vm_ext_code_alloc(blob_len, 1) == base;
}

static int expect_u16(const char *name, uint16_t got, uint16_t want) {
    if (got == want) return 0;
    fprintf(stderr, "vm-ext-code-reclaim-smoke: FAIL %s: got=$%04x want=$%04x\n",
            name, got, want);
    return 1;
}

static int expect_uint(const char *name, unsigned got, unsigned want) {
    if (got == want) return 0;
    fprintf(stderr, "vm-ext-code-reclaim-smoke: FAIL %s: got=%u want=%u\n",
            name, got, want);
    return 1;
}

static int expect_true(const char *name, int value) {
    if (value) return 0;
    fprintf(stderr, "vm-ext-code-reclaim-smoke: FAIL %s\n", name);
    return 1;
}

int main(void) {
    uint16_t transient_at, nested_at;
    unsigned stages_before, loads_before;
    int failed = 0;

    /* A loader error must leave the high-water mark at its original base. */
    load_result = 0;
    failed |= expect_true("metadata failure reported", !install_staged_lib(32, 40));
    failed |= expect_uint("metadata failure staged once", stage_calls, 1);
    failed |= expect_uint("metadata failure loaded once", load_calls, 1);
    failed |= expect_u16("metadata failure rolls back", vm_ext_code_alloc(0, 0), 0);

    /* A successful load retains only the blob, not its temporary trailer. */
    load_result = 1;
    failed |= expect_true("first install succeeds", install_staged_lib(32, 40));
    failed |= expect_u16("first next base is blob end", vm_ext_code_alloc(0, 0), 32);
    failed |= expect_u16("reclaimed trailer is reusable", vm_ext_code_alloc(224, 0), 32);
    failed |= expect_true("second install succeeds", install_staged_lib(16, 40));
    failed |= expect_u16("second next base is blob sum", vm_ext_code_alloc(0, 0), 48);

    /* Peak capacity includes metadata even when the blob alone would fit. */
    stages_before = stage_calls;
    loads_before = load_calls;
    failed |= expect_true("peak overflow rejected", !install_staged_lib(200, 40));
    failed |= expect_uint("peak overflow does not stage", stage_calls, stages_before);
    failed |= expect_uint("peak overflow does not load", load_calls, loads_before);
    failed |= expect_u16("peak overflow preserves base", vm_ext_code_alloc(0, 0), 48);

    /* The final base comparison detects an unexpected persistent allocation. */
    interleave_persistent_alloc = 1;
    failed |= expect_true("base mismatch rejected", !install_staged_lib(16, 40));
    failed |= expect_u16("interleaved allocation starts at preview base", interleave_at, 48);
    failed |= expect_u16("mismatch remains visible in high-water", vm_ext_code_alloc(0, 0), 65);
    interleave_persistent_alloc = 0;

    /* Active transient code lowers the preview ceiling; equality is allowed. */
    transient_at = vm_ext_code_alloc_transient(16);
    failed |= expect_u16("transient allocation", transient_at, 240);
    failed |= expect_u16("preview reaches transient exactly", vm_ext_code_alloc(175, 0), 65);
    failed |= expect_u16("preview cannot cross transient", vm_ext_code_alloc(176, 0), 0xffffu);

    /* C1 may retire persistent code while eval/lcc-run's transient caller is
     * live.  The two ranges are disjoint, and retirement must not pop or move
     * the downward transient stack. */
    failed |= expect_true("disjoint truncate under transient",
                          vm_ext_code_truncate(48));
    failed |= expect_u16("truncate changes persistent watermark only",
                         vm_ext_code_watermark(), 48);
    nested_at = vm_ext_code_alloc_transient(8);
    failed |= expect_u16("transient stack survives truncate", nested_at, 232);
    vm_ext_code_pop_transient(nested_at, 8);
    failed |= expect_u16("restored transient still bounds persistent preview",
                         vm_ext_code_alloc(192, 0), 48);
    failed |= expect_u16("restored transient rejects overlap",
                         vm_ext_code_alloc(193, 0), 0xffffu);
    vm_ext_code_pop_transient(transient_at, 16);

    failed |= expect_true("truncate outside region rejected",
                          !vm_ext_code_truncate(0xffffu));
    failed |= expect_true("truncate above current rejected",
                          !vm_ext_code_truncate(49));

    /* Only a corrupted state can cross the ranges because both allocators
     * gate the boundary.  Inject it and prove rollback does not hide it. */
    vm_ext_code_test_state(96, 80);
    failed |= expect_true("overlapping persistent and transient ranges rejected",
                          !vm_ext_code_truncate(48));
    failed |= expect_u16("overlap rejection preserves persistent watermark",
                         vm_ext_code_watermark(), 96);
    failed |= expect_u16("overlap rejection preserves transient watermark",
                         vm_ext_code_test_transient(), 80);
    vm_ext_code_test_state(48, 0);

    /* The region limit itself is inclusive for the end address. */
    failed |= expect_u16("persistent exact-limit allocation", vm_ext_code_alloc(208, 1), 48);
    failed |= expect_u16("high-water reaches limit", vm_ext_code_alloc(0, 0), 256);
    failed |= expect_u16("allocation beyond limit rejected", vm_ext_code_alloc(1, 1), 0xffffu);
    failed |= expect_u16("transient beyond full region rejected",
                         vm_ext_code_alloc_transient(1), 0xffffu);

    if (failed) return 1;
    printf("vm-ext-code-reclaim-smoke: PASS\n");
    return 0;
}
