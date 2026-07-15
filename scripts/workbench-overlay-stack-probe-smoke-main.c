/* Native array-seam smoke for the opt-in boot stack probe and overlay wipe. */
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include "vm_boot_overlay.h"

#define SOFT_FLOOR 0xc000u
#define SOFT_SIZE  0x0040u
#define HW_INITIAL 0xe0u
#define OVERLAY_SIZE 64u

uint8_t lisp65_boot_probe_host_soft[SOFT_SIZE];
uint16_t lisp65_boot_probe_host_soft_floor = SOFT_FLOOR;
uint16_t lisp65_boot_probe_host_soft_sp = SOFT_FLOOR + SOFT_SIZE;
uint8_t lisp65_boot_probe_host_page1[256];
uint8_t lisp65_boot_probe_host_hw_sp = HW_INITIAL;

uint8_t lisp65_boot_overlay_host_target[OVERLAY_SIZE];
const uint16_t lisp65_boot_overlay_host_vma = 0xb000u;
const uint16_t lisp65_boot_overlay_host_entry = 0xb010u;
const uint16_t lisp65_boot_overlay_host_len = OVERLAY_SIZE;

const char *lisp_error_msg;
uint8_t mem_oom;

void eval_init(void) {}
void vm_load_embedded_stdlib(void) {}
void gc_freeze_boot(void) {}
void vm_code_load(uint8_t bank, uint16_t off, uint16_t len, uint8_t *dst) {
    (void)bank; (void)off; (void)len; (void)dst;
}

static int expect_u16(const char *name, uint16_t got, uint16_t want) {
    if (got == want) return 0;
    fprintf(stderr, "workbench-overlay-stack-probe-smoke: FAIL %s got=%u want=%u\n",
            name, (unsigned)got, (unsigned)want);
    return 1;
}

int main(void) {
    unsigned i;
    int failed = 0;

    memset(lisp65_boot_probe_host_soft, 0, sizeof(lisp65_boot_probe_host_soft));
    memset(lisp65_boot_probe_host_page1, 0, sizeof(lisp65_boot_probe_host_page1));
    vm_boot_stack_probe_begin();
    for (i = 0x30; i < SOFT_SIZE; i++) lisp65_boot_probe_host_soft[i] ^= 0xffu;
    for (i = 0xd4; i <= HW_INITIAL; i++) lisp65_boot_probe_host_page1[i] ^= 0xffu;
    vm_boot_stack_probe_end();

    failed |= expect_u16("complete", lisp65_boot_probe_complete, 1);
    failed |= expect_u16("flags", lisp65_boot_probe_flags, 0);
    failed |= expect_u16("soft initial", lisp65_boot_probe_soft_initial, 0xc040u);
    failed |= expect_u16("soft low", lisp65_boot_probe_soft_low, 0xc030u);
    failed |= expect_u16("soft margin", lisp65_boot_probe_soft_margin, 0x0030u);
    failed |= expect_u16("hw initial", lisp65_boot_probe_hw_initial, HW_INITIAL);
    failed |= expect_u16("hw low", lisp65_boot_probe_hw_low, 0xd4u);
    failed |= expect_u16("hw remaining", lisp65_boot_probe_hw_remaining, 0xd4u);

    memset(lisp65_boot_overlay_host_target, 0x11, sizeof(lisp65_boot_overlay_host_target));
    vm_boot_overlay_wipe();
    failed |= expect_u16("wipe ok", lisp65_boot_overlay_wipe_ok, 1);
    for (i = 0; i < OVERLAY_SIZE; i++) {
        if (lisp65_boot_overlay_host_target[i] != 0) {
            fprintf(stderr, "workbench-overlay-stack-probe-smoke: FAIL wipe byte %u\n", i);
            failed = 1;
            break;
        }
    }

    lisp65_boot_probe_host_soft_sp = SOFT_FLOOR;
    lisp65_boot_probe_host_hw_sp = 0;
    vm_boot_stack_probe_begin();
    vm_boot_stack_probe_end();
    failed |= expect_u16("invalid complete", lisp65_boot_probe_complete, 1);
    failed |= expect_u16("invalid flags", lisp65_boot_probe_flags,
                         LISP65_BOOT_PROBE_SOFT_RANGE_BAD |
                         LISP65_BOOT_PROBE_SOFT_EXHAUSTED |
                         LISP65_BOOT_PROBE_HW_EXHAUSTED);

    if (failed) return 1;
    printf("workbench-overlay-stack-probe-smoke: PASS low-water+wipe+invalid-range\n");
    return 0;
}
