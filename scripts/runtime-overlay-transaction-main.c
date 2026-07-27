/* Host proof for generation-bound runtime-overlay transaction authentication. */
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include "vm_runtime_overlay.h"

#define TEST_VMA 0x9000u
#define TEST_LIMIT LISP65_RUNTIME_OVERLAY_HARD_MAX_SLICE
#define TEST_BUILD_ID 0x13579bdfUL
#define TEST_ENTRY_1 LISP65_RUNTIME_OVERLAY_APPLICATION_SLOT_BASE
#define TEST_ENTRY_2 (LISP65_RUNTIME_OVERLAY_APPLICATION_SLOT_BASE + 1u)
#define TEST_OFF_CATALOG 0x0500u
#define TEST_OFF_RECORD 0x0600u
#define TEST_OFF_1 0x0700u
#define TEST_OFF_2 0x0800u
#define TEST_OFF_ISLAND 0x0900u
#define TEST_ENTRY_1_RECORD (32u + TEST_ENTRY_1 * 32u)
#define TEST_ENTRY_2_RECORD (32u + TEST_ENTRY_2 * 32u)
#define TEST_ISLAND_RECORD \
    (32u + LISP65_RUNTIME_ISLAND_INSTALL_SLOT * 32u)

uint8_t lisp65_runtime_overlay_host_target[TEST_LIMIT];
const uint16_t lisp65_runtime_overlay_host_vma = TEST_VMA;
uint16_t lisp65_runtime_overlay_host_limit = TEST_VMA + TEST_LIMIT;
uint16_t lisp65_runtime_overlay_host_soft_sp = 0xffffu;
uint8_t lisp65_resident_island_host_target[LISP65_RUNTIME_ISLAND_CAPACITY];

static uint8_t bank3[65536];
static const uint8_t catalog_verifier[] = {
    'R', 'T', 'O', 'V', 'C', '1', 0xa5, 0x5a
};
static const uint8_t record_verifier[] = {
    'R', 'T', 'O', 'V', 'R', '1', 0xa5, 0x5a
};
static const uint8_t payload1[] = { 0x41, 0x31, 0xa5, 0x5a };
static const uint8_t payload2[] = { 0x42, 0x32, 0xa5, 0x5a };
static const uint8_t island_installer[] = {
    'R', 'T', 'I', 'S', 'L', 'D', 0xa5, 0x5a
};
static unsigned catalog_calls;
static unsigned record_calls;
static unsigned payload_calls;
static unsigned repeat_calls;
static int failed;

static uint8_t stop_after_one(
        void *context, uint8_t slot, uint8_t last_entry_result) {
    (void)context;
    (void)slot;
    (void)last_entry_result;
    return 0;
}

static uint8_t repeat_exactly_twice(
        void *context, uint8_t slot, uint8_t last_entry_result) {
    (void)context;
    (void)slot;
    (void)last_entry_result;
    return repeat_calls++ == 0u;
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

static void expect(int condition, const char *name) {
    if (condition) return;
    fprintf(stderr, "runtime-overlay-transaction: FAIL %s\n", name);
    ++failed;
}

void vm_code_load(uint8_t bank, uint16_t off, uint16_t length, uint8_t *dst) {
    if (bank != 3 || (uint32_t)off + length > sizeof bank3) {
        memset(dst, 0, length);
        return;
    }
    memcpy(dst, bank3 + off, length);
}

uint8_t vm_runtime_overlay_host_call(uint16_t entry, void *opaque) {
    if (entry == TEST_VMA
        && !memcmp(lisp65_runtime_overlay_host_target, catalog_verifier,
                   sizeof catalog_verifier)) {
        ++catalog_calls;
        return vm_runtime_overlay_catalog_verifier(opaque);
    }
    if (entry == TEST_VMA
        && !memcmp(lisp65_runtime_overlay_host_target, record_verifier,
                   sizeof record_verifier)) {
        ++record_calls;
        return vm_runtime_overlay_record_verifier(opaque);
    }
    if (entry == TEST_VMA
        && !memcmp(lisp65_runtime_overlay_host_target, island_installer,
                   sizeof island_installer))
        return vm_resident_island_install(opaque);
    ++payload_calls;
    return entry == TEST_VMA ? 0u : 1u;
}

static void fill_entry(uint8_t *entry, uint16_t id, uint16_t file_off,
                       uint16_t file_len, const uint8_t *payload) {
    put16(entry, id);
    put16(entry + 2, LISP65_RUNTIME_OVERLAY_FLAG_RUNTIME |
                       LISP65_RUNTIME_OVERLAY_FLAG_REUSABLE);
    put16(entry + 4, file_off);
    put16(entry + 6, file_len);
    put16(entry + 8, TEST_VMA);
    put16(entry + 10, file_len);
    put16(entry + 12, 0);
    put16(entry + 14, LISP65_RUNTIME_OVERLAY_ENTRY_ABI_V1);
    put32(entry + 16, TEST_BUILD_ID);
    put16(entry + 20, crc16(payload, file_len));
}

static void finish_header(void) {
    uint16_t crc;
    bank3[26] = bank3[27] = 0;
    crc = crc16(bank3, LISP65_RUNTIME_OVERLAY_HEADER_SIZE);
    put16(bank3 + 26, crc);
}

static void finish_directory(void) {
    put16(bank3 + 24, crc16(bank3 + 32,
                            (uint16_t)bank3[7] * 32u));
    finish_header();
}

static void make_catalog(void) {
    memset(bank3, 0, sizeof bank3);
    bank3[0] = LISP65_RUNTIME_OVERLAY_MAGIC_0;
    bank3[1] = LISP65_RUNTIME_OVERLAY_MAGIC_1;
    bank3[2] = LISP65_RUNTIME_OVERLAY_MAGIC_2;
    bank3[3] = LISP65_RUNTIME_OVERLAY_MAGIC_3;
    bank3[4] = LISP65_RUNTIME_OVERLAY_FORMAT_VERSION;
    bank3[5] = LISP65_RUNTIME_OVERLAY_HEADER_SIZE;
    bank3[6] = LISP65_RUNTIME_OVERLAY_ENTRY_SIZE;
    bank3[7] = (uint8_t)(LISP65_RUNTIME_ISLAND_INSTALL_SLOT + 1u);
    bank3[10] = 3;
    put32(bank3 + 12, TEST_BUILD_ID);
    put16(bank3 + 16, 32);
    put16(bank3 + 18, TEST_OFF_CATALOG);
    put32(bank3 + 20, TEST_OFF_ISLAND + sizeof island_installer);
    fill_entry(bank3 + 32, 0, TEST_OFF_CATALOG,
               sizeof catalog_verifier, catalog_verifier);
    fill_entry(bank3 + 64, 1, TEST_OFF_RECORD,
               sizeof record_verifier, record_verifier);
    fill_entry(bank3 + TEST_ENTRY_1_RECORD, TEST_ENTRY_1, TEST_OFF_1,
               sizeof payload1, payload1);
    fill_entry(bank3 + TEST_ENTRY_2_RECORD, TEST_ENTRY_2, TEST_OFF_2,
               sizeof payload2, payload2);
    fill_entry(bank3 + TEST_ISLAND_RECORD,
               LISP65_RUNTIME_ISLAND_INSTALL_SLOT, TEST_OFF_ISLAND,
               sizeof island_installer, island_installer);
    put16(bank3 + TEST_ISLAND_RECORD + 2,
          LISP65_RUNTIME_OVERLAY_FLAG_BOOT);
    memcpy(bank3 + 0x0200u, catalog_verifier, sizeof catalog_verifier);
    memcpy(bank3 + 0x0300u, record_verifier, sizeof record_verifier);
    memcpy(bank3 + TEST_OFF_CATALOG, catalog_verifier,
           sizeof catalog_verifier);
    memcpy(bank3 + TEST_OFF_RECORD, record_verifier,
           sizeof record_verifier);
    memcpy(bank3 + TEST_OFF_1, payload1, sizeof payload1);
    memcpy(bank3 + TEST_OFF_2, payload2, sizeof payload2);
    memcpy(bank3 + TEST_OFF_ISLAND, island_installer,
           sizeof island_installer);
    finish_directory();
}

static void select_session(uint16_t generation) {
    expect(vm_runtime_overlay_select_family(
               LISP65_RUNTIME_OVERLAY_FAMILY_BOOT, 0u)
               == VM_RUNTIME_OVERLAY_OK,
           "select boot family");
    expect(vm_runtime_overlay_select_family(
               LISP65_RUNTIME_OVERLAY_FAMILY_SESSION, generation)
               == VM_RUNTIME_OVERLAY_OK,
           "select session family");
}

static void reset_session(uint16_t generation) {
    vm_runtime_overlay_host_reset();
    memset(lisp65_runtime_overlay_host_target, 0,
           sizeof lisp65_runtime_overlay_host_target);
    vm_runtime_overlay_host_assume_island_ready();
    select_session(generation);
}

static void catalog_once_per_transaction(void) {
    uint8_t result = 0xff;
    make_catalog(); reset_session(7u);
    catalog_calls = record_calls = payload_calls = 0;
    expect(vm_runtime_overlay_transaction_begin(
               LISP65_RUNTIME_OVERLAY_FAMILY_SESSION, 7u)
               == VM_RUNTIME_OVERLAY_OK,
           "begin first transaction");
    expect(vm_runtime_overlay_exec_family(
               LISP65_RUNTIME_OVERLAY_FAMILY_SESSION, 7u,
               TEST_ENTRY_1, 0, &result) == VM_RUNTIME_OVERLAY_OK,
           "first transaction first slice");
    expect(vm_runtime_overlay_exec_family(
               LISP65_RUNTIME_OVERLAY_FAMILY_SESSION, 7u,
               TEST_ENTRY_2, 0, &result) == VM_RUNTIME_OVERLAY_OK,
           "first transaction second slice");
    expect(vm_runtime_overlay_transaction_end() == VM_RUNTIME_OVERLAY_OK,
           "end first transaction");
    expect(catalog_calls == 1 && record_calls == 2 && payload_calls == 2,
           "catalog once and record/payload per slice");
    expect(vm_runtime_overlay_transaction_begin(
               LISP65_RUNTIME_OVERLAY_FAMILY_SESSION, 7u)
               == VM_RUNTIME_OVERLAY_OK,
           "begin second transaction");
    expect(vm_runtime_overlay_exec_family(
               LISP65_RUNTIME_OVERLAY_FAMILY_SESSION, 7u,
               TEST_ENTRY_1, 0, &result) == VM_RUNTIME_OVERLAY_OK,
           "second transaction first slice");
    expect(vm_runtime_overlay_transaction_end() == VM_RUNTIME_OVERLAY_OK,
           "end second transaction");
    expect(catalog_calls == 2 && record_calls == 3 && payload_calls == 3,
           "new transaction reauthenticates catalog");
}

static void mutation_between_transactions(void) {
    uint8_t result = 0xff;
    make_catalog(); reset_session(9u);
    expect(vm_runtime_overlay_transaction_begin(
               LISP65_RUNTIME_OVERLAY_FAMILY_SESSION, 9u)
               == VM_RUNTIME_OVERLAY_OK,
           "mutation baseline begin");
    expect(vm_runtime_overlay_exec_family(
               LISP65_RUNTIME_OVERLAY_FAMILY_SESSION, 9u,
               TEST_ENTRY_1, 0, &result) == VM_RUNTIME_OVERLAY_OK,
           "mutation baseline slice");
    expect(vm_runtime_overlay_transaction_end() == VM_RUNTIME_OVERLAY_OK,
           "mutation baseline end");
    bank3[TEST_OFF_1] ^= 1u;
    result = 0xff;
    expect(vm_runtime_overlay_transaction_begin(
               LISP65_RUNTIME_OVERLAY_FAMILY_SESSION, 9u)
               == VM_RUNTIME_OVERLAY_OK,
           "mutation second begin");
    expect(vm_runtime_overlay_exec_family(
               LISP65_RUNTIME_OVERLAY_FAMILY_SESSION, 9u,
               TEST_ENTRY_1, 0, &result) == VM_RUNTIME_OVERLAY_ERR_CRC,
           "between-transaction payload mutation rejected");
    expect(result == LISP65_RUNTIME_OVERLAY_ENTRY_NOT_RUN,
           "mutated payload never called");
    expect(vm_runtime_overlay_fault_latched(),
           "mutated payload latches fault");
}

static void generation_reauthenticates(void) {
    uint8_t result = 0xff;
    make_catalog(); reset_session(11u);
    expect(vm_runtime_overlay_transaction_begin(
               LISP65_RUNTIME_OVERLAY_FAMILY_SESSION, 11u)
               == VM_RUNTIME_OVERLAY_OK,
           "generation baseline begin");
    expect(vm_runtime_overlay_exec_family(
               LISP65_RUNTIME_OVERLAY_FAMILY_SESSION, 11u,
               TEST_ENTRY_1, 0, &result) == VM_RUNTIME_OVERLAY_OK,
           "generation baseline slice");
    expect(vm_runtime_overlay_transaction_end() == VM_RUNTIME_OVERLAY_OK,
           "generation baseline end");
    /* A generation change is a cold-boot transition.  The family machine
     * deliberately rejects Session -> Boot reselection in a live session. */
    vm_runtime_overlay_host_reset();
    vm_runtime_overlay_host_assume_island_ready();
    select_session(12u);
    bank3[12] ^= 1u;
    finish_header();
    expect(vm_runtime_overlay_transaction_begin(
               LISP65_RUNTIME_OVERLAY_FAMILY_SESSION, 12u)
               == VM_RUNTIME_OVERLAY_OK,
           "new generation begin");
    result = 0xff;
    expect(vm_runtime_overlay_exec_family(
               LISP65_RUNTIME_OVERLAY_FAMILY_SESSION, 12u,
               TEST_ENTRY_1, 0, &result) == VM_RUNTIME_OVERLAY_ERR_PROFILE,
           "new generation reauthentication rejects identity drift");
    expect(result == LISP65_RUNTIME_OVERLAY_ENTRY_NOT_RUN,
           "stale generation never called");
}

static void generation_switch_while_active(void) {
    uint8_t result = 0xff;
    make_catalog(); reset_session(13u);
    expect(vm_runtime_overlay_transaction_begin(
               LISP65_RUNTIME_OVERLAY_FAMILY_SESSION, 13u)
               == VM_RUNTIME_OVERLAY_OK,
           "active-switch begin");
    expect(vm_runtime_overlay_exec_family(
               LISP65_RUNTIME_OVERLAY_FAMILY_SESSION, 13u,
               TEST_ENTRY_1, 0, &result) == VM_RUNTIME_OVERLAY_OK,
           "active-switch first slice");
    expect(vm_runtime_overlay_select_family(
               LISP65_RUNTIME_OVERLAY_FAMILY_BOOT, 0u)
               == VM_RUNTIME_OVERLAY_ERR_BUSY,
           "active generation switch rejected");
    result = 0xff;
    expect(vm_runtime_overlay_exec_family(
               LISP65_RUNTIME_OVERLAY_FAMILY_SESSION, 13u,
               TEST_ENTRY_2, 0, &result) == VM_RUNTIME_OVERLAY_ERR_LATCHED,
           "active generation switch fails closed");
    expect(result == LISP65_RUNTIME_OVERLAY_ENTRY_NOT_RUN,
           "post-switch payload never called");
}

static void batch_transaction_lifetimes_are_exclusive(void) {
    uint8_t result = 0xff;
    make_catalog(); reset_session(15u);
    vm_runtime_overlay_host_assume_island_ready();
    expect(vm_runtime_overlay_exec_batch(
               TEST_ENTRY_1, 0, &result,
               VM_RUNTIME_OVERLAY_BATCH_L65M, stop_after_one)
               == VM_RUNTIME_OVERLAY_OK,
           "batch completes before transaction");
    expect(vm_runtime_overlay_transaction_begin(
               LISP65_RUNTIME_OVERLAY_FAMILY_SESSION, 15u)
               == VM_RUNTIME_OVERLAY_OK,
           "completed batch releases shared tuple");
    result = 0xff;
    expect(vm_runtime_overlay_exec_batch(
               TEST_ENTRY_1, 0, &result,
               VM_RUNTIME_OVERLAY_BATCH_L65M, stop_after_one)
               == VM_RUNTIME_OVERLAY_ERR_BUSY,
           "batch rejected during transaction");
    expect(vm_runtime_overlay_exec_family(
               LISP65_RUNTIME_OVERLAY_FAMILY_SESSION, 15u,
               TEST_ENTRY_1, 0, &result) == VM_RUNTIME_OVERLAY_OK,
           "direct transaction slice remains usable after batch rejection");
    expect(vm_runtime_overlay_transaction_end() == VM_RUNTIME_OVERLAY_OK,
           "transaction releases shared tuple");
}

static void batch_s1_repeats_the_complete_single_record_path(void) {
    uint8_t result = 0xff;
    make_catalog(); reset_session(16u);
    catalog_calls = record_calls = payload_calls = repeat_calls = 0;
    expect(vm_runtime_overlay_exec_batch(
               TEST_ENTRY_1, 0, &result,
               VM_RUNTIME_OVERLAY_BATCH_L65M, repeat_exactly_twice)
               == VM_RUNTIME_OVERLAY_OK,
           "E000-S1 two-record batch completes");
    expect(result == 0u && repeat_calls == 2u,
           "E000-S1 predicate observes both completed records");
    expect(catalog_calls == 2u && record_calls == 2u && payload_calls == 2u,
           "E000-S1 repeats catalog record and payload proof");
}

static void stale_predecessor_island_is_never_entered(
        const char *fixture_path) {
    FILE *stream;
    size_t length;
    make_catalog();
    vm_runtime_overlay_host_reset();
    stream = fopen(fixture_path, "rb");
    expect(stream != 0, "open exact Link-30 predecessor Island");
    if (!stream) return;
    length = fread(lisp65_resident_island_host_target, 1,
                   sizeof lisp65_resident_island_host_target, stream);
    expect(!ferror(stream), "read exact Link-30 predecessor Island");
    expect(fgetc(stream) == EOF, "Link-30 predecessor fits Island");
    fclose(stream);
    expect(length == 1291u, "exact Link-30 predecessor length");
    expect(vm_runtime_overlay_select_family(
               LISP65_RUNTIME_OVERLAY_FAMILY_BOOT, 0u)
               == VM_RUNTIME_OVERLAY_OK,
           "select boot family for stale-Island installer");
    catalog_calls = record_calls = payload_calls = 0;
    expect(vm_runtime_overlay_install_island() == VM_RUNTIME_OVERLAY_OK,
           "installer replaces exact Link-30 predecessor");
    expect(vm_runtime_overlay_island_ready(),
           "stale predecessor replacement publishes ready");
    expect(vm_runtime_overlay_host_transaction_context_calls() == 0,
           "installer never enters stale transaction context");
    expect(vm_runtime_overlay_host_island_matches_image(),
           "installed Island matches current generated image");
}

static void active_transaction_before_install_fails_closed(void) {
    uint8_t result = 0;
    make_catalog();
    vm_runtime_overlay_host_reset();
    expect(vm_runtime_overlay_select_family(
               LISP65_RUNTIME_OVERLAY_FAMILY_BOOT, 0u)
               == VM_RUNTIME_OVERLAY_OK,
           "select boot family for not-ready mutation");
    vm_runtime_overlay_host_force_transaction_untrusted();
    expect(vm_runtime_overlay_exec_family(
               LISP65_RUNTIME_OVERLAY_FAMILY_BOOT, 0u,
               TEST_ENTRY_1, 0, &result)
               == VM_RUNTIME_OVERLAY_ERR_ISLAND_NOT_READY,
           "active transaction before Island readiness fails closed");
    expect(result == LISP65_RUNTIME_OVERLAY_ENTRY_NOT_RUN,
           "not-ready transaction never executes payload");
    expect(vm_runtime_overlay_host_transaction_context_calls() == 0,
           "not-ready transaction never enters stale Island context");
}

int main(int argc, char **argv) {
    catalog_once_per_transaction();
    mutation_between_transactions();
    generation_reauthenticates();
    generation_switch_while_active();
    batch_transaction_lifetimes_are_exclusive();
    batch_s1_repeats_the_complete_single_record_path();
    active_transaction_before_install_fails_closed();
    if (argc == 2)
        stale_predecessor_island_is_never_entered(argv[1]);
    else if (argc != 1)
        expect(0, "usage: runtime-overlay-transaction [link30-island.bin]");
    if (failed) {
        fprintf(stderr, "runtime-overlay-transaction: FAIL failures=%d\n", failed);
        return 1;
    }
    printf("runtime-overlay-transaction: PASS catalog=once-per-transaction "
           "record+payload=per-slice same-generation-mutation=crc-red "
           "generation-change=reauthenticated batch-state=lifetime-exclusive "
           "batch-S1=full-single-record-repeat");
    if (argc == 2)
        printf(" stale-predecessor=exact-link30 preinstall-island-calls=0");
    putchar('\n');
    return 0;
}
