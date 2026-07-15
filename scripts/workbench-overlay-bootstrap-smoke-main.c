/* Native contract smoke for the staged Workbench boot-overlay bootstrap. */
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include "vm_boot_overlay.h"

#define STAGE_BANK 7u
#define STAGE_OFF  0x2200u
#define BUILD_ID   0x91e2a34cUL
#define TEST_VMA   0xb000u
#define TEST_ENTRY 0xb010u
#define PAYLOAD_LEN 64u

static const uint8_t payload[PAYLOAD_LEN] = {
    0x0b,0x30,0x55,0x7a,0x9f,0xc4,0xe9,0x0e,0x33,0x58,0x7d,0xa2,0xc7,0xec,0x11,0x36,
    0x5b,0x80,0xa5,0xca,0xef,0x14,0x39,0x5e,0x83,0xa8,0xcd,0xf2,0x17,0x3c,0x61,0x86,
    0xab,0xd0,0xf5,0x1a,0x3f,0x64,0x89,0xae,0xd3,0xf8,0x1d,0x42,0x67,0x8c,0xb1,0xd6,
    0xfb,0x20,0x45,0x6a,0x8f,0xb4,0xd9,0xfe,0x23,0x48,0x6d,0x92,0xb7,0xdc,0x01,0x26
};

static uint8_t stage[65536];
static uint32_t stage_available;
uint8_t lisp65_boot_overlay_host_target[PAYLOAD_LEN];
const uint16_t lisp65_boot_overlay_host_vma = TEST_VMA;
const uint16_t lisp65_boot_overlay_host_entry = TEST_ENTRY;
const uint16_t lisp65_boot_overlay_host_len = PAYLOAD_LEN;
static unsigned entry_calls;
static uint8_t entry_must_fail;
static uint8_t boot_sequence;
const char *lisp_error_msg;
uint8_t mem_oom;

void eval_init(void) {
    entry_calls++;
    boot_sequence = 1;
    if (entry_must_fail == 1) lisp_error_msg = "synthetic eval-init failure";
    if (entry_must_fail == 4) mem_oom = 1;
}
void vm_code_load(uint8_t bank, uint16_t off, uint16_t len, uint8_t *dst) {
    uint32_t available = 0;
    memset(dst, 0, len);
    if (bank != STAGE_BANK || off >= stage_available) return;
    available = stage_available - off;
    if (available > len) available = len;
    memcpy(dst, stage + off, available);
}

static void put16(uint8_t *p, uint16_t value) {
    p[0] = (uint8_t)value;
    p[1] = (uint8_t)(value >> 8);
}

static void put32(uint8_t *p, uint32_t value) {
    p[0] = (uint8_t)value;
    p[1] = (uint8_t)(value >> 8);
    p[2] = (uint8_t)(value >> 16);
    p[3] = (uint8_t)(value >> 24);
}

static void valid_package(void) {
    uint8_t *h = stage + STAGE_OFF;
    memset(stage, 0, sizeof(stage));
    memset(lisp65_boot_overlay_host_target, 0xa5, sizeof(lisp65_boot_overlay_host_target));
    h[0] = 'L'; h[1] = '6'; h[2] = '5'; h[3] = 'O';
    h[4] = LISP65_BOOT_OVERLAY_VERSION;
    h[5] = LISP65_BOOT_OVERLAY_HEADER_SIZE;
    put32(h + 6, BUILD_ID);
    put16(h + 10, TEST_VMA);
    put16(h + 12, TEST_ENTRY);
    put16(h + 14, PAYLOAD_LEN);
    put16(h + 16, 0xbe28u); /* known CRC-16/CCITT-FALSE for payload[] */
    memcpy(h + LISP65_BOOT_OVERLAY_HEADER_SIZE, payload, sizeof(payload));
    stage_available = STAGE_OFF + LISP65_BOOT_OVERLAY_HEADER_SIZE + PAYLOAD_LEN;
    entry_calls = 0;
    entry_must_fail = 0;
    boot_sequence = 0;
    lisp_error_msg = 0;
    mem_oom = 0;
    vm_boot_overlay_host_reset();
}

static int expect_status(const char *name, uint8_t expected) {
    uint8_t actual = vm_install_staged_boot_overlay();
    if (actual == expected && vm_boot_overlay_status == expected &&
        entry_calls == ((expected == VM_BOOT_OVERLAY_OK || entry_must_fail) ? 1u : 0u))
        return 0;
    fprintf(stderr, "workbench-overlay-bootstrap-smoke: FAIL %s status=%u global=%u calls=%u\n",
            name, actual, vm_boot_overlay_status, entry_calls);
    return 1;
}

int main(void) {
    uint8_t *h = stage + STAGE_OFF;
    int failed = 0;

    valid_package();
    failed |= expect_status("valid", VM_BOOT_OVERLAY_OK);
    if (boot_sequence != 1) {
        fprintf(stderr, "workbench-overlay-bootstrap-smoke: FAIL boot sequence=%u\n",
                boot_sequence);
        failed = 1;
    }
    { uint8_t zero[PAYLOAD_LEN] = {0};
      if (memcmp(lisp65_boot_overlay_host_target, zero, PAYLOAD_LEN) != 0) {
          fprintf(stderr, "workbench-overlay-bootstrap-smoke: FAIL dead payload wipe\n");
          failed = 1;
      } }
    if (vm_install_staged_boot_overlay() != VM_BOOT_OVERLAY_ERR_REENTRY ||
        vm_boot_overlay_status != VM_BOOT_OVERLAY_ERR_REENTRY || entry_calls != 1) {
        fprintf(stderr, "workbench-overlay-bootstrap-smoke: FAIL successful reentry\n");
        failed = 1;
    }

    valid_package(); stage_available = 0;
    failed |= expect_status("missing", VM_BOOT_OVERLAY_ERR_MAGIC);
    stage_available = STAGE_OFF + LISP65_BOOT_OVERLAY_HEADER_SIZE + PAYLOAD_LEN;
    if (vm_install_staged_boot_overlay() != VM_BOOT_OVERLAY_ERR_REENTRY || entry_calls != 0) {
        fprintf(stderr, "workbench-overlay-bootstrap-smoke: FAIL failed-boot reentry\n");
        failed = 1;
    }
    valid_package(); stage_available = STAGE_OFF + 5u;
    failed |= expect_status("truncated descriptor", VM_BOOT_OVERLAY_ERR_HEADER);
    valid_package(); h[0] ^= 1u;
    failed |= expect_status("magic", VM_BOOT_OVERLAY_ERR_MAGIC);
    valid_package(); h[4]++;
    failed |= expect_status("version", VM_BOOT_OVERLAY_ERR_VERSION);
    valid_package(); h[5]--;
    failed |= expect_status("header size", VM_BOOT_OVERLAY_ERR_HEADER);
    valid_package(); h[6] ^= 1u;
    failed |= expect_status("profile", VM_BOOT_OVERLAY_ERR_PROFILE);
    valid_package(); h[10] ^= 1u;
    failed |= expect_status("vma", VM_BOOT_OVERLAY_ERR_VMA);
    valid_package(); h[12] ^= 1u;
    failed |= expect_status("entry", VM_BOOT_OVERLAY_ERR_ENTRY);
    valid_package(); h[14]--;
    failed |= expect_status("length", VM_BOOT_OVERLAY_ERR_LENGTH);
    valid_package(); h[16] ^= 1u;
    failed |= expect_status("descriptor crc", VM_BOOT_OVERLAY_ERR_CRC);
    valid_package(); stage[STAGE_OFF + LISP65_BOOT_OVERLAY_HEADER_SIZE + 7u] ^= 1u;
    failed |= expect_status("payload mutation", VM_BOOT_OVERLAY_ERR_CRC);
    valid_package(); stage_available--;
    failed |= expect_status("truncated payload", VM_BOOT_OVERLAY_ERR_CRC);
    valid_package(); entry_must_fail = 1;
    failed |= expect_status("eval-init failure", VM_BOOT_OVERLAY_ERR_ENTRY_RUN);
    valid_package(); entry_must_fail = 4;
    failed |= expect_status("eval-init oom", VM_BOOT_OVERLAY_ERR_ENTRY_RUN);
    valid_package(); lisp_error_msg = "preexisting boot failure";
    failed |= expect_status("preexisting boot failure", VM_BOOT_OVERLAY_ERR_ENTRY_RUN);
    valid_package(); mem_oom = 1;
    failed |= expect_status("preexisting boot oom", VM_BOOT_OVERLAY_ERR_ENTRY_RUN);

    if (failed) return 1;
    printf("workbench-overlay-bootstrap-smoke: PASS init-only+16 fail-closed cases\n");
    return 0;
}
