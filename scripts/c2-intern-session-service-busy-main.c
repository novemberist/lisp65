/* Host witness for the Session-service occupied-window contract. */
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include "vm_runtime_overlay.h"

#define TEST_VMA 0xc356u
#define TEST_BYTES LISP65_RUNTIME_OVERLAY_HARD_MAX_SLICE

uint8_t lisp65_runtime_overlay_host_target[TEST_BYTES];
const uint16_t lisp65_runtime_overlay_host_vma = TEST_VMA;
uint16_t lisp65_runtime_overlay_host_limit = TEST_VMA + TEST_BYTES;
uint16_t lisp65_runtime_overlay_host_soft_sp = 0xffffu;
uint8_t lisp65_resident_island_host_target[LISP65_RUNTIME_ISLAND_CAPACITY];

void vm_code_load(uint8_t bank, uint16_t off, uint16_t length, uint8_t *dst) {
    (void)bank; (void)off;
    memset(dst, 0, length);
}

uint8_t vm_runtime_overlay_host_call(uint16_t entry, void *context) {
    (void)entry; (void)context;
    return 0xfeu;
}

static void seed_window(uint8_t *before) {
    uint16_t i;
    for (i = 0; i < TEST_BYTES; ++i)
        lisp65_runtime_overlay_host_target[i] =
            (uint8_t)(i ^ (uint16_t)(i >> 3) ^ 0xa5u);
    memcpy(before, lisp65_runtime_overlay_host_target, TEST_BYTES);
}

static int rejected_unchanged(
        uint8_t family, uint16_t generation, uint8_t *before) {
    uint8_t result = 0x5au;
    vm_runtime_overlay_status status = vm_runtime_overlay_exec_family(
        family, generation, 63u, before, &result);
    return status == VM_RUNTIME_OVERLAY_ERR_FAMILY
        && result == LISP65_RUNTIME_OVERLAY_ENTRY_NOT_RUN
        && memcmp(before, lisp65_runtime_overlay_host_target,
                  TEST_BYTES) == 0;
}

int main(void) {
    uint8_t before[TEST_BYTES];
    uint8_t result = 0x5au;
    vm_runtime_overlay_status status;

    /* Inactive, Boot, zero-generation and stale-generation requests are all
     * rejected before the shared execution window changes. */
    vm_runtime_overlay_host_reset();
    seed_window(before);
    if (!rejected_unchanged(
            LISP65_RUNTIME_OVERLAY_FAMILY_SESSION, 7u, before))
        return 2;
    vm_runtime_overlay_host_reset();
    if (vm_runtime_overlay_select_family(
            LISP65_RUNTIME_OVERLAY_FAMILY_BOOT, 0u)
            != VM_RUNTIME_OVERLAY_OK)
        return 3;
    seed_window(before);
    if (!rejected_unchanged(
            LISP65_RUNTIME_OVERLAY_FAMILY_SESSION, 7u, before))
        return 4;
    if (vm_runtime_overlay_select_family(
            LISP65_RUNTIME_OVERLAY_FAMILY_SESSION, 7u)
            != VM_RUNTIME_OVERLAY_OK) {
        fputs("c2-intern-session-service-busy: FAIL family\n", stderr);
        return 1;
    }
    seed_window(before);
    if (!rejected_unchanged(
            LISP65_RUNTIME_OVERLAY_FAMILY_SESSION, 0u, before)
        || !rejected_unchanged(
            LISP65_RUNTIME_OVERLAY_FAMILY_SESSION, 8u, before))
        return 5;

    vm_runtime_overlay_host_force_busy(1u);
    status = vm_runtime_overlay_exec(63u, before, &result);
    if (status != VM_RUNTIME_OVERLAY_ERR_BUSY
        || result != LISP65_RUNTIME_OVERLAY_ENTRY_NOT_RUN
        || memcmp(before, lisp65_runtime_overlay_host_target,
                  sizeof before) != 0
        || !vm_runtime_overlay_active()) {
        fputs("c2-intern-session-service-busy: FAIL\n", stderr);
        return 1;
    }
    vm_runtime_overlay_host_force_busy(0u);
    puts("c2-intern-session-service-busy: PASS bytes=1792 "
         "transport=ERR_BUSY entry=NOT_RUN window=byte-identical "
         "family-negatives=4");
    return 0;
}
