/* Product-shaped host fixture for the selected strict L65R data-carrier path. */
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include "vm_runtime_overlay.h"

#define TEST_VMA 0xc356u
#define TEST_LIMIT LISP65_RUNTIME_OVERLAY_HARD_MAX_SLICE
#define TEST_BUILD_ID 0x13579bdfUL
#define INSTALLER_SLOT LISP65_RUNTIME_ISLAND_INSTALL_SLOT
#define CARRIER_SLOT LISP65_RUNTIME_ISLAND_CARRIER_SLOT
#define TEST_RECORD_COUNT (CARRIER_SLOT + 1u)
#define CATALOG_OFF 0x0500u
#define RECORD_OFF 0x0600u
#define INSTALLER_OFF 0x0d00u
#define CARRIER_OFF 0x0e00u
#define CARRIER_RECORD (32u + CARRIER_SLOT * 32u)

uint8_t lisp65_runtime_overlay_host_target[TEST_LIMIT];
const uint16_t lisp65_runtime_overlay_host_vma = TEST_VMA;
uint16_t lisp65_runtime_overlay_host_limit = TEST_VMA + TEST_LIMIT;
uint16_t lisp65_runtime_overlay_host_soft_sp = 0xffffu;
uint8_t lisp65_resident_island_host_target[LISP65_RUNTIME_ISLAND_CAPACITY];

static uint8_t bank3[65536];
static unsigned calls;
static unsigned carrier_calls;
static int failed;
static const uint8_t catalog_verifier[] = {'R','T','O','V','C','1',0xa5,0x5a};
static const uint8_t record_verifier[] = {'R','T','O','V','R','1',0xa5,0x5a};
static const uint8_t installer[] = {'I','N','S','2'};
static const uint8_t carrier[] = {'I','S','L','D'};
static const uint8_t dummy[] = {'D'};

static uint8_t stop_after_one(
        void *context, uint8_t slot, uint8_t last_entry_result) {
    (void)context;
    (void)slot;
    (void)last_entry_result;
    return 0;
}

static void put16(uint8_t *p, uint16_t value) {
    p[0] = (uint8_t)value;
    p[1] = (uint8_t)(value >> 8);
}

static void put32(uint8_t *p, uint32_t value) {
    put16(p, (uint16_t)value);
    put16(p + 2, (uint16_t)(value >> 16));
}

static uint16_t crc16(const uint8_t *p, uint16_t length) {
    uint16_t crc = LISP65_RUNTIME_OVERLAY_CRC16_INIT;
    while (length--) {
        uint8_t bits = 8;
        crc ^= (uint16_t)*p++ << 8;
        while (bits--)
            crc = (crc & 0x8000u)
                ? (uint16_t)((crc << 1) ^ LISP65_RUNTIME_OVERLAY_CRC16_POLY)
                : (uint16_t)(crc << 1);
    }
    return crc;
}

static void finish_header(void) {
    bank3[26] = bank3[27] = 0;
    put16(bank3 + 26, crc16(bank3, 32));
}

static void finish_directory_crc(void) {
    put16(bank3 + 24, crc16(bank3 + 32, TEST_RECORD_COUNT * 32u));
    finish_header();
}

static void finish_directory(void) {
#if LISP65_RUNTIME_OVERLAY_FORMAT_VERSION >= 3u
    uint8_t slot;
    for (slot = 0; slot < TEST_RECORD_COUNT; ++slot) {
        uint8_t *entry = bank3 + 32u + (uint16_t)slot * 32u;
        put16(entry + 22, 0);
        put16(entry + 22, crc16(entry, 32));
    }
#endif
    finish_directory_crc();
}

static void record(uint8_t slot, uint16_t flags, uint16_t off,
                   const uint8_t *payload, uint16_t length,
                   uint16_t vma, uint16_t entry, uint16_t abi) {
    uint8_t *p = bank3 + 32u + (uint16_t)slot * 32u;
    put16(p, slot); put16(p + 2, flags); put16(p + 4, off);
    put16(p + 6, length); put16(p + 8, vma); put16(p + 10, length);
    put16(p + 12, entry); put16(p + 14, abi);
    put32(p + 16, TEST_BUILD_ID); put16(p + 20, crc16(payload, length));
    put16(p + 22, 0); put32(p + 24, 0); put32(p + 28, 0);
#if LISP65_RUNTIME_OVERLAY_FORMAT_VERSION == 4u
    /* Region 0 is staged at $08200000.  v4 authenticates the absolute source
     * tuple; the host transport models every non-Bank-5 source with bank3. */
    p[24] = 0;
    p[25] = 0;
    p[26] = 0x82;
#endif
    memcpy(bank3 + off, payload, length);
}

static void make_catalog(void) {
    uint8_t slot;
    memset(bank3, 0, sizeof bank3);
    memcpy(bank3, "L65R", 4);
    bank3[4] = LISP65_RUNTIME_OVERLAY_FORMAT_VERSION;
    bank3[5] = 32;
    bank3[6] = 32; bank3[7] = TEST_RECORD_COUNT; bank3[10] = 3;
    put32(bank3 + 12, TEST_BUILD_ID); put16(bank3 + 16, 32);
    put16(bank3 + 18, 0x0200); put32(bank3 + 20, CARRIER_OFF + 4u);
    record(0, 6, CATALOG_OFF, catalog_verifier, sizeof catalog_verifier,
           TEST_VMA, 0, 1);
    record(1, 6, RECORD_OFF, record_verifier, sizeof record_verifier,
           TEST_VMA, 0, 1);
    for (slot = 2; slot < INSTALLER_SLOT; ++slot)
        record(slot, 1, (uint16_t)(0x0700u + (uint16_t)(slot - 2u) * 0x100u),
               dummy, sizeof dummy, TEST_VMA, 0, 1);
    record(INSTALLER_SLOT, 1, INSTALLER_OFF, installer, sizeof installer,
           TEST_VMA, 0, 1);
    record(CARRIER_SLOT, 9, CARRIER_OFF, carrier, sizeof carrier,
           LISP65_RUNTIME_ISLAND_ADDRESS,
           LISP65_RUNTIME_OVERLAY_DATA_ENTRY_NONE, 0);
    finish_directory();
}

void vm_code_load(uint8_t bank, uint16_t off, uint16_t length, uint8_t *dst) {
    if (bank != 3 || (uint32_t)off + length > sizeof bank3) {
        memset(dst, 0, length);
        return;
    }
    memcpy(dst, bank3 + off, length);
}

uint8_t vm_runtime_overlay_host_call(uint16_t entry, void *opaque) {
    calls++;
    if (entry != TEST_VMA) return 0xfeu;
    if (!memcmp(lisp65_runtime_overlay_host_target, catalog_verifier,
                sizeof catalog_verifier))
        return vm_runtime_overlay_catalog_verifier(opaque);
    if (!memcmp(lisp65_runtime_overlay_host_target, record_verifier,
                sizeof record_verifier))
        return vm_runtime_overlay_record_verifier(opaque);
    if (!memcmp(lisp65_runtime_overlay_host_target, installer,
                sizeof installer))
        return vm_resident_island_install(opaque);
    if (!memcmp(lisp65_runtime_overlay_host_target, carrier, sizeof carrier))
        carrier_calls++;
    return 0xfdu;
}

static void expect(int condition, const char *label) {
    if (condition) return;
    fprintf(stderr, "c2-l65r-v2-product: FAIL %s\n", label);
    failed++;
}

static int zero_island(void) {
    uint16_t i;
    for (i = 0; i < LISP65_RUNTIME_ISLAND_CAPACITY; ++i)
        if (lisp65_resident_island_host_target[i]) return 0;
    return 1;
}

static void boot_reset(void) {
    vm_runtime_overlay_host_reset();
    expect(vm_runtime_overlay_select_family(
               LISP65_RUNTIME_OVERLAY_FAMILY_BOOT, 0) ==
               VM_RUNTIME_OVERLAY_OK,
           "fresh boot family selected");
}

static void session_reset(void) {
    boot_reset();
    expect(vm_runtime_overlay_select_family(
               LISP65_RUNTIME_OVERLAY_FAMILY_SESSION, 1) ==
               VM_RUNTIME_OVERLAY_OK,
           "fresh session family selected");
}

/* A dense slot number is meaningful only together with its lifetime family.
 * Exercise the complete 2 x 2 x 2 matrix: Boot/Session family, ordinary/
 * installer-number slot, and Boot/runtime record flags. */
static void family_slot_cartesian(void) {
    uint8_t result;
    vm_runtime_overlay_status status;

    /* Boot, ordinary slot: both ordinary runtime and cold Boot records are
     * legal; the numeric installer exception must not leak to this slot. */
    make_catalog(); boot_reset(); result = 0xff;
    status = vm_runtime_overlay_exec_family(
        LISP65_RUNTIME_OVERLAY_FAMILY_BOOT, 0, 2, 0, &result);
    expect(status == VM_RUNTIME_OVERLAY_OK,
           "matrix boot ordinary boot-record accepted");
    make_catalog(); record(2, 6, 0x0700, dummy, sizeof dummy,
                            TEST_VMA, 0, 1); finish_directory();
    boot_reset(); result = 0xff;
    status = vm_runtime_overlay_exec_family(
        LISP65_RUNTIME_OVERLAY_FAMILY_BOOT, 0, 2, 0, &result);
    expect(status == VM_RUNTIME_OVERLAY_OK,
           "matrix boot ordinary runtime-record accepted");

    /* Boot, installer number: only the Boot record under the installing
     * state is the installer. A runtime record at the same number is not. */
    make_catalog(); boot_reset();
    expect(vm_runtime_overlay_install_island() == VM_RUNTIME_OVERLAY_OK,
           "matrix boot installer boot-record accepted");
    make_catalog(); record(INSTALLER_SLOT, 6, INSTALLER_OFF,
                            dummy, sizeof dummy, TEST_VMA, 0, 1);
    finish_directory(); boot_reset(); result = 0xff;
    status = vm_runtime_overlay_exec_family(
        LISP65_RUNTIME_OVERLAY_FAMILY_BOOT, 0,
        INSTALLER_SLOT, 0, &result);
    expect(status == VM_RUNTIME_OVERLAY_ERR_ENTRY &&
           result == LISP65_RUNTIME_OVERLAY_ENTRY_NOT_RUN,
           "matrix boot installer runtime-record rejected");

    /* Session, ordinary slot: runtime is legal; Boot-only data is not. */
    make_catalog(); session_reset(); result = 0xff;
    status = vm_runtime_overlay_exec_family(
        LISP65_RUNTIME_OVERLAY_FAMILY_SESSION, 1, 2, 0, &result);
    expect(status == VM_RUNTIME_OVERLAY_ERR_DIRECTORY &&
           result == LISP65_RUNTIME_OVERLAY_ENTRY_NOT_RUN,
           "matrix session ordinary boot-record rejected");
    make_catalog(); record(2, 6, 0x0700, dummy, sizeof dummy,
                            TEST_VMA, 0, 1); finish_directory();
    session_reset(); result = 0xff;
    status = vm_runtime_overlay_exec_family(
        LISP65_RUNTIME_OVERLAY_FAMILY_SESSION, 1, 2, 0, &result);
    expect(status == VM_RUNTIME_OVERLAY_OK,
           "matrix session ordinary runtime-record accepted");

    /* Session, the colliding installer number: it is an ordinary Session
     * slot. Runtime is legal; a Boot installer record remains forbidden. */
    make_catalog(); session_reset(); result = 0xff;
    status = vm_runtime_overlay_exec_family(
        LISP65_RUNTIME_OVERLAY_FAMILY_SESSION, 1,
        INSTALLER_SLOT, 0, &result);
    expect(status == VM_RUNTIME_OVERLAY_ERR_DIRECTORY &&
           result == LISP65_RUNTIME_OVERLAY_ENTRY_NOT_RUN,
           "matrix session installer-number boot-record rejected");
    make_catalog(); record(INSTALLER_SLOT, 6, INSTALLER_OFF,
                            dummy, sizeof dummy, TEST_VMA, 0, 1);
    finish_directory(); session_reset(); result = 0xff;
    status = vm_runtime_overlay_exec_family(
        LISP65_RUNTIME_OVERLAY_FAMILY_SESSION, 1,
        INSTALLER_SLOT, 0, &result);
    expect(status == VM_RUNTIME_OVERLAY_OK,
           "matrix session installer-number runtime-record accepted");

    /* The two remaining numeric-slot consumers are family-qualified too:
     * installer entry is Boot-only, and batch slot ranges are Session ABI. */
    expect(vm_runtime_overlay_install_island() ==
               VM_RUNTIME_OVERLAY_ERR_FAMILY,
           "matrix session cannot enter Boot installer API");
    make_catalog(); record(2, 6, 0x0700, dummy, sizeof dummy,
                            TEST_VMA, 0, 1); finish_directory();
    boot_reset(); result = 0xff;
    status = vm_runtime_overlay_exec_batch(
        2, 0, &result, VM_RUNTIME_OVERLAY_BATCH_L65M, stop_after_one);
    expect(status == VM_RUNTIME_OVERLAY_OK,
           "matrix Boot slot receives no Session batch privilege");
}

static void positive(void) {
    vm_runtime_overlay_status status;
    make_catalog(); boot_reset(); calls = carrier_calls = 0;
    status = vm_runtime_overlay_install_island();
    if (status != VM_RUNTIME_OVERLAY_OK)
        fprintf(stderr, "c2-l65r-v2-product: install status=%u calls=%u\n",
                (unsigned)status, calls);
    expect(status == VM_RUNTIME_OVERLAY_OK,
           "two-record install");
    expect(vm_runtime_overlay_island_ready(), "READY published last");
    expect(vm_runtime_overlay_host_island_matches_image(), "target identity");
    expect(calls == 3 && carrier_calls == 0,
           "carrier transported but never dispatched");
}

static void public_carrier_rejected(void) {
    uint8_t result = 0;
    vm_runtime_overlay_status status;
    make_catalog(); boot_reset(); carrier_calls = 0;
    status = vm_runtime_overlay_exec(CARRIER_SLOT, 0, &result);
    if (status != VM_RUNTIME_OVERLAY_ERR_ENTRY)
        fprintf(stderr, "c2-l65r-v2-product: public status=%u\n",
                (unsigned)status);
    expect(status == VM_RUNTIME_OVERLAY_ERR_ENTRY,
           "public carrier execution rejected");
    expect(result == LISP65_RUNTIME_OVERLAY_ENTRY_NOT_RUN && !carrier_calls,
           "carrier rejected before dispatch");
}

static void reject_install(const char *label,
                           vm_runtime_overlay_status expected) {
    vm_runtime_overlay_status status;
    boot_reset();
    memset(lisp65_resident_island_host_target, 0xa5,
           sizeof lisp65_resident_island_host_target);
    status = vm_runtime_overlay_install_island();
    expect(status == expected, label);
    expect(!vm_runtime_overlay_island_ready() && zero_island(),
           "failure clears READY and wipes destination");
}

static void boot_lifetime_closed(void) {
    make_catalog(); boot_reset();
    expect(vm_runtime_overlay_install_island() == VM_RUNTIME_OVERLAY_OK,
           "lifetime fixture installed Island");
    expect(vm_runtime_overlay_select_family(
               LISP65_RUNTIME_OVERLAY_FAMILY_SESSION, 1) ==
               VM_RUNTIME_OVERLAY_OK,
           "session family selected after boot");
    expect(vm_runtime_overlay_select_family(
               LISP65_RUNTIME_OVERLAY_FAMILY_BOOT, 0) ==
               VM_RUNTIME_OVERLAY_ERR_FAMILY,
           "session cannot re-enter boot family");
}

static void negatives(void) {
    make_catalog(); bank3[4] = 1; finish_header();
    reject_install("v1 rejected with inner VERSION status",
                   VM_RUNTIME_OVERLAY_ERR_VERSION);
    make_catalog(); put16(bank3 + CARRIER_RECORD + 2, 1); finish_directory();
    reject_install("missing DATA_ONLY rejected", VM_RUNTIME_OVERLAY_ERR_ISLAND);
    make_catalog(); put16(bank3 + CARRIER_RECORD + 2, 0x19); finish_directory();
    reject_install("unknown DATA_ONLY flags rejected",
                   VM_RUNTIME_OVERLAY_ERR_ISLAND);
    make_catalog(); put16(bank3 + CARRIER_RECORD + 12, 0); finish_directory();
    reject_install("callable carrier rejected", VM_RUNTIME_OVERLAY_ERR_ISLAND);
    make_catalog(); put16(bank3 + CARRIER_RECORD + 14, 1); finish_directory();
    reject_install("carrier ABI one rejected", VM_RUNTIME_OVERLAY_ERR_ISLAND);
    make_catalog(); put16(bank3 + CARRIER_RECORD + 8, TEST_VMA); finish_directory();
    reject_install("carrier destination rejected", VM_RUNTIME_OVERLAY_ERR_ISLAND);
#if LISP65_RUNTIME_OVERLAY_FORMAT_VERSION == 4u
    make_catalog(); bank3[CARRIER_RECORD + 27] = 1; finish_directory();
#else
    make_catalog(); put32(bank3 + CARRIER_RECORD + 24, 1); finish_directory();
#endif
    reject_install("carrier capability rejected", VM_RUNTIME_OVERLAY_ERR_ISLAND);
#if LISP65_RUNTIME_OVERLAY_FORMAT_VERSION >= 3u
    make_catalog(); bank3[CARRIER_RECORD + 22] ^= 1u; finish_directory_crc();
    reject_install("wrong record CRC times out",
                   VM_RUNTIME_OVERLAY_ERR_COMPLETION_TIMEOUT);
    make_catalog(); put16(bank3 + CARRIER_RECORD + 22, 0u);
    finish_directory_crc();
    reject_install("zero record CRC times out",
                   VM_RUNTIME_OVERLAY_ERR_COMPLETION_TIMEOUT);
#endif
    make_catalog(); bank3[CARRIER_OFF] ^= 1;
#ifdef LISP65_RTOV_CRC_CONVERGENCE
    reject_install("source CRC rejected",
                   VM_RUNTIME_OVERLAY_ERR_COMPLETION_TIMEOUT);
#else
    reject_install("source CRC rejected", VM_RUNTIME_OVERLAY_ERR_ISLAND);
#endif
    make_catalog(); boot_reset();
    vm_runtime_overlay_host_island_copy_fault(1);
#ifdef LISP65_RTOV_CRC_CONVERGENCE
    expect(vm_runtime_overlay_install_island() ==
               VM_RUNTIME_OVERLAY_ERR_COMPLETION_TIMEOUT,
           "destination CRC rejected");
#else
    expect(vm_runtime_overlay_install_island() == VM_RUNTIME_OVERLAY_ERR_ISLAND,
           "destination CRC rejected");
#endif
    expect(zero_island(), "destination CRC failure wipes Island");
    make_catalog(); boot_reset();
    vm_runtime_overlay_host_island_frame_fault(1);
    expect(vm_runtime_overlay_install_island() == VM_RUNTIME_OVERLAY_ERR_ISLAND,
           "post-auth verifier-frame mutation rejected");
    expect(zero_island(), "frame mutation rejected before installation");
}

int main(void) {
    positive(); public_carrier_rejected(); negatives(); boot_lifetime_closed();
    family_slot_cartesian();
    if (failed) return 1;
#if LISP65_RUNTIME_OVERLAY_FORMAT_VERSION >= 3u
    puts("c2-l65r-product: PASS publish-last+14 fail-closed cases family-slot=8/8 consumers=4/4");
#else
    puts("c2-l65r-product: PASS publish-last+12 fail-closed cases family-slot=8/8 consumers=4/4");
#endif
    return 0;
}
