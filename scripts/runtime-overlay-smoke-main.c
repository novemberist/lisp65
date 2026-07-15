/* Native mutation smoke for the reusable runtime-overlay transport. */
#include <stdint.h>
#include <setjmp.h>
#include <stdio.h>
#include <string.h>

#include "vm_boot_fastpath.h"
#include "vm_runtime_overlay.h"

#define TEST_VMA       0x9000u
#define TEST_LIMIT     LISP65_RUNTIME_OVERLAY_HARD_MAX_SLICE
#define TEST_BUILD_ID  0x13579bdfUL
#define TEST_CATALOG_VERIFIER 0u
#define TEST_RECORD_VERIFIER  1u
#define TEST_ENTRY_1           LISP65_RUNTIME_OVERLAY_APPLICATION_SLOT_BASE
#define TEST_ENTRY_2           (LISP65_RUNTIME_OVERLAY_APPLICATION_SLOT_BASE + 1u)
#define TEST_ISLAND_INSTALLER  LISP65_RUNTIME_ISLAND_INSTALL_SLOT
#define TEST_OFF_CATALOG       0x0500u
#define TEST_OFF_RECORD        0x0600u
#define TEST_OFF_1             0x0700u
#define TEST_OFF_2             0x0800u
#define TEST_OFF_ISLAND        0x0900u
#define TEST_OFF_BOUNDARY      0x2000u
#define TEST_ENTRY_1_RECORD    (32u + TEST_ENTRY_1 * 32u)
#define TEST_ENTRY_2_RECORD    (32u + TEST_ENTRY_2 * 32u)
#define TEST_ISLAND_RECORD     (32u + TEST_ISLAND_INSTALLER * 32u)

uint8_t lisp65_runtime_overlay_host_target[TEST_LIMIT];
const uint16_t lisp65_runtime_overlay_host_vma = TEST_VMA;
uint16_t lisp65_runtime_overlay_host_limit;
uint16_t lisp65_runtime_overlay_host_soft_sp;
uint8_t lisp65_resident_island_host_target[
    LISP65_RUNTIME_ISLAND_CAPACITY];
static uint8_t bank3[65536];
static const uint8_t catalog_verifier[] = {
    'R', 'T', 'O', 'V', 'C', '1', 0xa5, 0x5a
};
static const uint8_t record_verifier[] = {
    'R', 'T', 'O', 'V', 'R', '1', 0xa5, 0x5a
};
static const uint8_t payload1[] = { 0x41, 0x50, 0x35, 0x2e, 0x32, 0xa5, 0x5a, 0x11 };
static const uint8_t payload2[] = { 0x52, 0x55, 0x4e, 0x54, 0x49, 0x4d, 0x45 };
static const uint8_t island_installer[] = {
    'R', 'T', 'I', 'S', 'L', 'D', 0xa5, 0x5a
};
static uint8_t boundary_payload[TEST_LIMIT];
static const uint8_t *expected_payload;
static uint16_t expected_length;
static uint16_t expected_entry;
static unsigned entry_calls;
static unsigned verifier_calls;
static unsigned load_calls;
static unsigned predicate_calls;
static unsigned batch_target_calls;
static int failed;
static jmp_buf abort_target;

static void expect(int condition, const char *name);

typedef struct {
    uint8_t result;
    uint8_t reenter;
    uint8_t abort_jump;
    vm_runtime_overlay_status nested_status;
    uint8_t nested_result;
    uint16_t abort_after_call;
    uint16_t tamper_after_call;
} entry_context;

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
        while (bits--) {
            if (crc & 0x8000u)
                crc = (uint16_t)((crc << 1) ^ LISP65_RUNTIME_OVERLAY_CRC16_POLY);
            else
                crc = (uint16_t)(crc << 1);
        }
    }
    return crc;
}

void vm_code_load(uint8_t bank, uint16_t off, uint16_t length, uint8_t *dst) {
    load_calls++;
    if (bank != 3 || (uint32_t)off + length > sizeof bank3) {
        memset(dst, 0, length);
        return;
    }
    memcpy(dst, bank3 + off, length);
}

uint8_t vm_runtime_overlay_host_call(uint16_t entry, void *opaque) {
    entry_context *context = (entry_context *)opaque;
    if (entry == TEST_VMA &&
        memcmp(lisp65_runtime_overlay_host_target, catalog_verifier,
               sizeof catalog_verifier) == 0) {
        verifier_calls++;
        return vm_runtime_overlay_catalog_verifier(opaque);
    }
    if (entry == TEST_VMA &&
        memcmp(lisp65_runtime_overlay_host_target, record_verifier,
               sizeof record_verifier) == 0) {
        verifier_calls++;
        return vm_runtime_overlay_record_verifier(opaque);
    }
    if (entry == TEST_VMA &&
        memcmp(lisp65_runtime_overlay_host_target, island_installer,
               sizeof island_installer) == 0)
        return vm_resident_island_install(opaque);
    entry_calls++;
    if (entry != expected_entry) {
        fprintf(stderr, "runtime-overlay-smoke: FAIL entry got=0x%04x want=0x%04x\n",
                entry, expected_entry);
        failed++;
    }
    if (memcmp(lisp65_runtime_overlay_host_target, expected_payload, expected_length) != 0) {
        fprintf(stderr, "runtime-overlay-smoke: FAIL entry payload mismatch\n");
        failed++;
    }
    if (context->reenter) {
        context->nested_result = 0;
        context->nested_status = vm_runtime_overlay_exec(
            TEST_ENTRY_2, context, &context->nested_result);
    }
    if (context->tamper_after_call == entry_calls)
        lisp65_runtime_overlay_host_target[0] ^= 1u;
    if (context->abort_after_call == entry_calls) longjmp(abort_target, 1);
    if (context->abort_jump) longjmp(abort_target, 1);
    return context->result;
}

static uint8_t repeat_to_target(
    void *opaque, uint8_t slot, uint8_t last_entry_result) {
    entry_context *context = (entry_context *)opaque;
    predicate_calls++;
    expect(context != 0, "batch predicate context");
    expect(slot == TEST_ENTRY_1, "batch predicate slot");
    expect(last_entry_result == context->result, "batch predicate result");
    return entry_calls < batch_target_calls;
}

static void fill_entry(uint8_t *entry, uint16_t id, uint16_t file_off,
                       uint16_t file_len, uint16_t entry_off,
                       const uint8_t *payload) {
    put16(entry, id);
    put16(entry + 2, LISP65_RUNTIME_OVERLAY_FLAG_RUNTIME |
                       LISP65_RUNTIME_OVERLAY_FLAG_REUSABLE);
    put16(entry + 4, file_off);
    put16(entry + 6, file_len);
    put16(entry + 8, TEST_VMA);
    put16(entry + 10, file_len);
    put16(entry + 12, entry_off);
    put16(entry + 14, LISP65_RUNTIME_OVERLAY_ENTRY_ABI_V1);
    put32(entry + 16, TEST_BUILD_ID);
    put16(entry + 20, crc16(payload, file_len));
    put16(entry + 22, 0);
    put32(entry + 24, 0);
    put32(entry + 28, 0);
}

static void finish_header(void) {
    uint16_t crc;
    bank3[26] = bank3[27] = 0;
    crc = crc16(bank3, LISP65_RUNTIME_OVERLAY_HEADER_SIZE);
    put16(bank3 + 26, crc);
}

static void finish_directory(void) {
    put16(bank3 + 24, crc16(bank3 + 32,
                            (uint16_t)bank3[7] *
                            LISP65_RUNTIME_OVERLAY_ENTRY_SIZE));
    finish_header();
}

static void make_catalog(void) {
    memset(bank3, 0, sizeof bank3);
    lisp65_runtime_overlay_host_limit = TEST_VMA + TEST_LIMIT;
    lisp65_runtime_overlay_host_soft_sp = 0xffffu;
    bank3[0] = LISP65_RUNTIME_OVERLAY_MAGIC_0;
    bank3[1] = LISP65_RUNTIME_OVERLAY_MAGIC_1;
    bank3[2] = LISP65_RUNTIME_OVERLAY_MAGIC_2;
    bank3[3] = LISP65_RUNTIME_OVERLAY_MAGIC_3;
    bank3[4] = LISP65_RUNTIME_OVERLAY_FORMAT_VERSION;
    bank3[5] = LISP65_RUNTIME_OVERLAY_HEADER_SIZE;
    bank3[6] = LISP65_RUNTIME_OVERLAY_ENTRY_SIZE;
    bank3[7] = (uint8_t)(TEST_ISLAND_INSTALLER + 1u);
    put16(bank3 + 8, 0);
    bank3[10] = 3;
    bank3[11] = 0;
    put32(bank3 + 12, TEST_BUILD_ID);
    put16(bank3 + 16, 32);
    put16(bank3 + 18, TEST_OFF_CATALOG);
    put32(bank3 + 20, TEST_OFF_ISLAND + sizeof island_installer);
    put32(bank3 + 28, 0);
    fill_entry(bank3 + 32, TEST_CATALOG_VERIFIER, TEST_OFF_CATALOG,
               sizeof catalog_verifier, 0, catalog_verifier);
    fill_entry(bank3 + 64, TEST_RECORD_VERIFIER, TEST_OFF_RECORD,
               sizeof record_verifier, 0, record_verifier);
    fill_entry(bank3 + TEST_ENTRY_1_RECORD, TEST_ENTRY_1, TEST_OFF_1,
               sizeof payload1, 2, payload1);
    fill_entry(bank3 + TEST_ENTRY_2_RECORD, TEST_ENTRY_2, TEST_OFF_2,
               sizeof payload2, 1, payload2);
    fill_entry(bank3 + TEST_ISLAND_RECORD, TEST_ISLAND_INSTALLER,
               TEST_OFF_ISLAND, sizeof island_installer, 0,
               island_installer);
    put16(bank3 + TEST_ISLAND_RECORD + 2,
          LISP65_RUNTIME_OVERLAY_FLAG_BOOT);
    memcpy(bank3 + TEST_OFF_CATALOG, catalog_verifier, sizeof catalog_verifier);
    memcpy(bank3 + TEST_OFF_RECORD, record_verifier, sizeof record_verifier);
    memcpy(bank3 + TEST_OFF_1, payload1, sizeof payload1);
    memcpy(bank3 + TEST_OFF_2, payload2, sizeof payload2);
    memcpy(bank3 + TEST_OFF_ISLAND, island_installer,
           sizeof island_installer);
    finish_directory();
}

static int range_is(uint16_t first, uint16_t end, uint8_t value) {
    uint16_t i;
    for (i = first; i < end; i++)
        if (lisp65_runtime_overlay_host_target[i] != value) return 0;
    return 1;
}

static void expect(int condition, const char *name) {
    if (condition) return;
    fprintf(stderr, "runtime-overlay-smoke: FAIL %s\n", name);
    failed++;
}

typedef void (*mutation_fn)(void);

static vm_runtime_overlay_status reject(const char *name, mutation_fn mutate,
                                        vm_runtime_overlay_status expected) {
    entry_context context = { 0 };
    uint8_t result = 0;
    vm_runtime_overlay_status status, rejected_status;
    make_catalog();
    mutate();
    memset(lisp65_runtime_overlay_host_target, 0,
           sizeof lisp65_runtime_overlay_host_target);
    vm_runtime_overlay_host_reset();
    entry_calls = 0;
    verifier_calls = 0;
    status = vm_runtime_overlay_exec(TEST_ENTRY_1, &context, &result);
    if (status != expected) {
        fprintf(stderr, "runtime-overlay-smoke: FAIL %s status=%u expected=%u\n",
                name, (unsigned)status, (unsigned)expected);
        failed++;
    }
    rejected_status = status;
    expect(result == LISP65_RUNTIME_OVERLAY_ENTRY_NOT_RUN, name);
    expect(entry_calls == 0, name);
    expect(vm_runtime_overlay_fault_latched(), name);
    expect(range_is(0, TEST_LIMIT, 0), name);
    status = vm_runtime_overlay_exec(TEST_ENTRY_1, &context, &result);
    expect(status == VM_RUNTIME_OVERLAY_ERR_LATCHED, name);
    vm_runtime_overlay_host_reset();
    return rejected_status;
}

static void reject_catalog(const char *name, mutation_fn mutate,
                           vm_runtime_overlay_status expected) {
    vm_runtime_overlay_status status = reject(name, mutate, expected);
    expect(vm_boot_fastpath_transport_status(status) ==
           VM_BOOT_FASTPATH_ERR_CATALOG, name);
}

static void m_magic(void) { bank3[0] ^= 1; }
static void m_missing(void) { memset(bank3, 0, sizeof bank3); }
static void m_version(void) { bank3[4]++; finish_header(); }
static void m_header_size(void) { bank3[5]--; finish_header(); }
static void m_entry_size(void) { bank3[6]--; finish_header(); }
static void m_count(void) { bank3[7] = 0; finish_header(); }
static void m_count_large(void) {
    bank3[7] = (uint8_t)(LISP65_RUNTIME_OVERLAY_HARD_MAX_SLICES + 1u);
    finish_header();
}
static void m_header_flags(void) { put16(bank3 + 8, 1); finish_header(); }
static void m_bank(void) { bank3[10] = 4; finish_header(); }
static void m_header_reserved8(void) { bank3[11] = 1; finish_header(); }
static void m_profile(void) { bank3[12] ^= 1; finish_header(); }
static void m_dir_off(void) { put16(bank3 + 16, 34); finish_header(); }
static void m_payload_off(void) { put16(bank3 + 18, 0x0200); finish_header(); }
static void m_image_size(void) {
    put32(bank3 + 20, TEST_OFF_1 + sizeof payload1 - 1u);
    finish_header();
}
static void m_dir_crc(void) { bank3[24] ^= 1; finish_header(); }
static void m_header_crc(void) { bank3[26] ^= 1; }
static void m_header_reserved32(void) { put32(bank3 + 28, 1); finish_header(); }
static void m_id_order(void) { put16(bank3 + TEST_ENTRY_1_RECORD, TEST_ENTRY_2); finish_directory(); }
static void m_flags(void) {
    put16(bank3 + TEST_ENTRY_1_RECORD + 2,
          LISP65_RUNTIME_OVERLAY_FLAG_BOOT | LISP65_RUNTIME_OVERLAY_FLAG_RUNTIME);
    finish_directory();
}
static void m_file_off(void) { put16(bank3 + TEST_ENTRY_1_RECORD + 4, TEST_OFF_1 + 1); finish_directory(); }
static void m_file_len(void) { put16(bank3 + TEST_ENTRY_1_RECORD + 6, 0); put16(bank3 + TEST_ENTRY_1_RECORD + 10, 0); finish_directory(); }
static void m_vma(void) { put16(bank3 + TEST_ENTRY_1_RECORD + 8, TEST_VMA + 2); finish_directory(); }
static void m_mem_len(void) { put16(bank3 + TEST_ENTRY_1_RECORD + 10, sizeof payload1 + 1); finish_directory(); }
static void m_entry_off(void) { put16(bank3 + TEST_ENTRY_1_RECORD + 12, sizeof payload1); finish_directory(); }
static void m_abi(void) { put16(bank3 + TEST_ENTRY_1_RECORD + 14, 2); finish_directory(); }
static void m_slice_build(void) { bank3[TEST_ENTRY_1_RECORD + 16] ^= 1; finish_directory(); }
static void m_payload_crc_field(void) { bank3[TEST_ENTRY_1_RECORD + 20] ^= 1; finish_directory(); }
static void m_bss(void) { put16(bank3 + TEST_ENTRY_1_RECORD + 22, 1); finish_directory(); }
static void m_capability(void) { put32(bank3 + TEST_ENTRY_1_RECORD + 24, 1); finish_directory(); }
static void m_entry_reserved(void) { put32(bank3 + TEST_ENTRY_1_RECORD + 28, 1); finish_directory(); }
static void m_directory_crc(void) { bank3[TEST_ENTRY_1_RECORD + 20] ^= 1; }
static void m_payload_crc(void) { bank3[TEST_OFF_1] ^= 1; }
static void m_catalog_verifier_crc(void) { bank3[TEST_OFF_CATALOG] ^= 1; }
static void m_record_verifier_crc(void) { bank3[TEST_OFF_RECORD] ^= 1; }
static void m_too_large(void) {
    put16(bank3 + TEST_ENTRY_1_RECORD + 6, TEST_LIMIT + 1);
    put16(bank3 + TEST_ENTRY_1_RECORD + 10, TEST_LIMIT + 1);
    finish_directory();
}
static void m_window_boundary(void) {
    lisp65_runtime_overlay_host_limit = TEST_VMA + sizeof payload1 - 1u;
}
static void m_swap(void) {
    uint8_t temp[32];
    memcpy(temp, bank3 + TEST_ENTRY_1_RECORD, sizeof temp);
    memcpy(bank3 + TEST_ENTRY_1_RECORD, bank3 + TEST_ENTRY_2_RECORD, sizeof temp);
    memcpy(bank3 + TEST_ENTRY_2_RECORD, temp, sizeof temp);
    finish_directory();
}
static void positive_and_semantic(void) {
    entry_context context = { .result = 8 };
    uint8_t result = 0;
    vm_runtime_overlay_status status;
    make_catalog();
    vm_runtime_overlay_host_reset();
    memset(lisp65_runtime_overlay_host_target, 0xcc,
           sizeof lisp65_runtime_overlay_host_target);
    entry_calls = 0;
    verifier_calls = 0;
    expected_payload = payload1;
    expected_length = sizeof payload1;
    expected_entry = TEST_VMA + 2;
    status = vm_runtime_overlay_exec(TEST_ENTRY_1, &context, &result);
    expect(status == VM_RUNTIME_OVERLAY_OK, "semantic transport");
    expect(result == 8, "semantic result");
    expect(!vm_runtime_overlay_fault_latched(), "semantic latch");
    expect(range_is(0, sizeof payload1, 0), "semantic wipe");
    expect(range_is(sizeof payload1, TEST_LIMIT, 0xcc), "semantic exact wipe");

    context.result = 0;
    expected_payload = payload2;
    expected_length = sizeof payload2;
    expected_entry = TEST_VMA + 1;
    status = vm_runtime_overlay_exec(TEST_ENTRY_2, &context, &result);
    expect(status == VM_RUNTIME_OVERLAY_OK && result == 0, "reusable second slot");
    expect(entry_calls == 2, "reusable entry count");
    expect(verifier_calls == 4, "reusable verifier count");
    expect(range_is(0, sizeof payload2, 0), "reusable wipe");
    expect(range_is(sizeof payload2, sizeof payload1, 0), "reusable prior wipe");
    expect(range_is(sizeof payload1, TEST_LIMIT, 0xcc), "reusable exact wipe");
}

static void runtime_size_boundary(void) {
    entry_context context = { .result = 0x70u };
    uint8_t result = LISP65_RUNTIME_OVERLAY_ENTRY_NOT_RUN;
    vm_runtime_overlay_status status;
    uint16_t i;

    make_catalog();
    for (i = 0; i < TEST_LIMIT; i++)
        boundary_payload[i] = (uint8_t)(i ^ (i >> 8));
    fill_entry(bank3 + TEST_ENTRY_1_RECORD, TEST_ENTRY_1, TEST_OFF_BOUNDARY,
               TEST_LIMIT, TEST_LIMIT - 1u, boundary_payload);
    memcpy(bank3 + TEST_OFF_BOUNDARY, boundary_payload, TEST_LIMIT);
    put32(bank3 + 20, TEST_OFF_BOUNDARY + TEST_LIMIT);
    finish_directory();
    vm_runtime_overlay_host_reset();
    memset(lisp65_runtime_overlay_host_target, 0xcc,
           sizeof lisp65_runtime_overlay_host_target);
    entry_calls = verifier_calls = 0;
    expected_payload = boundary_payload;
    expected_length = TEST_LIMIT;
    expected_entry = TEST_VMA + TEST_LIMIT - 1u;
    status = vm_runtime_overlay_exec(TEST_ENTRY_1, &context, &result);
    expect(status == VM_RUNTIME_OVERLAY_OK && result == 0x70u,
           "1792-byte runtime boundary");
    expect(entry_calls == 1 && verifier_calls == 2,
           "1792-byte runtime boundary calls");
    expect(range_is(0, TEST_LIMIT, 0), "1792-byte runtime boundary wipe");
}

static void boot_slot(void) {
    entry_context context = { .result = 7 };
    uint8_t result = 0;
    vm_runtime_overlay_status status;
    make_catalog();
    put16(bank3 + TEST_ENTRY_1_RECORD + 2, LISP65_RUNTIME_OVERLAY_FLAG_BOOT);
    finish_directory();
    vm_runtime_overlay_host_reset();
    expected_payload = payload1;
    expected_length = sizeof payload1;
    expected_entry = TEST_VMA + 2;
    status = vm_runtime_overlay_exec(TEST_ENTRY_1, &context, &result);
    expect(status == VM_RUNTIME_OVERLAY_OK && result == 7,
           "profile-bound boot slot");
    expect(!vm_runtime_overlay_fault_latched(), "boot slot does not latch");
}

static void missing_slot(void) {
    entry_context context = { 0 };
    uint8_t result = 0;
    vm_runtime_overlay_status status;
    make_catalog();
    vm_runtime_overlay_host_reset();
    entry_calls = 0;
    status = vm_runtime_overlay_exec(99, &context, &result);
    expect(status == VM_RUNTIME_OVERLAY_ERR_SLOT, "missing slot");
    expect(result == LISP65_RUNTIME_OVERLAY_ENTRY_NOT_RUN, "missing slot result");
    expect(vm_runtime_overlay_fault_latched(), "missing slot latch");
    expect(entry_calls == 0 && range_is(0, TEST_LIMIT, 0), "missing slot isolation");
    vm_runtime_overlay_host_reset();
}

static void stack_boundary(void) {
    entry_context context = { 0 };
    uint8_t result = 0;
    vm_runtime_overlay_status status;
    make_catalog();
    vm_runtime_overlay_host_reset();
    memset(lisp65_runtime_overlay_host_target, 0xcc,
           sizeof lisp65_runtime_overlay_host_target);
    lisp65_runtime_overlay_host_soft_sp = lisp65_runtime_overlay_host_limit;
    entry_calls = 0;
    status = vm_runtime_overlay_exec(TEST_ENTRY_1, &context, &result);
    expect(status == VM_RUNTIME_OVERLAY_ERR_STACK, "soft-stack boundary");
    expect(result == LISP65_RUNTIME_OVERLAY_ENTRY_NOT_RUN, "soft-stack result");
    expect(vm_runtime_overlay_fault_latched(), "soft-stack latch");
    expect(entry_calls == 0, "soft-stack entry isolation");
    expect(range_is(0, TEST_LIMIT, 0xcc), "soft-stack target unchanged");
    vm_runtime_overlay_host_reset();
}

static void reentry(void) {
    entry_context context = { .reenter = 1 };
    uint8_t result = 0;
    vm_runtime_overlay_status status;
    make_catalog();
    vm_runtime_overlay_host_reset();
    memset(lisp65_runtime_overlay_host_target, 0xcc,
           sizeof lisp65_runtime_overlay_host_target);
    entry_calls = 0;
    expected_payload = payload1;
    expected_length = sizeof payload1;
    expected_entry = TEST_VMA + 2;
    status = vm_runtime_overlay_exec(TEST_ENTRY_1, &context, &result);
    expect(context.nested_status == VM_RUNTIME_OVERLAY_ERR_BUSY, "nested busy");
    expect(context.nested_result == LISP65_RUNTIME_OVERLAY_ENTRY_NOT_RUN,
           "nested result");
    expect(status == VM_RUNTIME_OVERLAY_OK, "outer survives rejected reentry");
    expect(!vm_runtime_overlay_fault_latched(), "reentry does not latch");
    expect(entry_calls == 1 && range_is(0, sizeof payload1, 0), "reentry wipe");
    expect(range_is(sizeof payload1, TEST_LIMIT, 0xcc), "reentry exact wipe");
    context.reenter = 0;
    status = vm_runtime_overlay_exec(TEST_ENTRY_1, &context, &result);
    expect(status == VM_RUNTIME_OVERLAY_OK, "transport reusable after reentry");
    vm_runtime_overlay_host_reset();
}

static void argument_failure(void) {
    entry_context context = { 0 };
    vm_runtime_overlay_status status;
    make_catalog();
    vm_runtime_overlay_host_reset();
    status = vm_runtime_overlay_exec(TEST_ENTRY_1, &context, 0);
    expect(status == VM_RUNTIME_OVERLAY_ERR_ARGUMENT, "null result argument");
    expect(vm_runtime_overlay_fault_latched(), "argument latch");
    vm_runtime_overlay_host_reset();
}

static void semantic_error_recovery(void) {
    entry_context context = { .result = 0xfeu };
    uint8_t result = 0;
    vm_runtime_overlay_status status;
    make_catalog();
    vm_runtime_overlay_host_reset();
    memset(lisp65_runtime_overlay_host_target, 0xcc,
           sizeof lisp65_runtime_overlay_host_target);
    entry_calls = 0;
    expected_payload = payload1;
    expected_length = sizeof payload1;
    expected_entry = TEST_VMA + 2;
    status = vm_runtime_overlay_exec(TEST_ENTRY_1, &context, &result);
    expect(status == VM_RUNTIME_OVERLAY_OK && result == 0xfeu,
           "semantic error result");
    expect(!vm_runtime_overlay_active(), "semantic error releases busy");
    expect(!vm_runtime_overlay_fault_latched(), "semantic error does not latch");
    context.result = 0;
    status = vm_runtime_overlay_exec(TEST_ENTRY_1, &context, &result);
    expect(status == VM_RUNTIME_OVERLAY_OK && result == 0,
           "transport reusable after semantic error");
    expect(entry_calls == 2, "semantic error recovery calls");
}

static void island_boot_gate(void) {
    entry_context context = { .result = 9 };
    uint8_t result = 0;
    vm_runtime_overlay_status status;
    make_catalog();
    vm_runtime_overlay_host_reset();
    status = vm_runtime_overlay_exec_batch(
        TEST_ENTRY_1, &context, &result, VM_RUNTIME_OVERLAY_BATCH_L65M,
        repeat_to_target);
    expect(status == VM_RUNTIME_OVERLAY_ERR_ISLAND_NOT_READY,
           "batch rejected before island install");
    expect(result == LISP65_RUNTIME_OVERLAY_ENTRY_NOT_RUN,
           "pre-island batch result");
    expect(!vm_runtime_overlay_fault_latched(),
           "pre-island batch does not poison installer");
    status = vm_runtime_overlay_install_island();
    expect(status == VM_RUNTIME_OVERLAY_OK,
           "island installer transport");
    expect(vm_runtime_overlay_island_ready(), "island ready latch");
    expect(memcmp(lisp65_resident_island_host_target, "ISLD", 4) == 0,
           "island target image");
    expect(vm_runtime_overlay_install_island() == VM_RUNTIME_OVERLAY_OK,
           "island installer idempotent");
}

static void island_copy_crc_failure(void) {
    vm_runtime_overlay_status status;
    make_catalog();
    vm_runtime_overlay_host_reset();
    vm_runtime_overlay_host_island_copy_fault(1);
    status = vm_runtime_overlay_install_island();
    expect(status == VM_RUNTIME_OVERLAY_ERR_ISLAND,
           "island target crc failure");
    expect(!vm_runtime_overlay_island_ready(), "island crc not ready");
    expect(vm_runtime_overlay_fault_latched(), "island crc latches transport");
    vm_runtime_overlay_host_reset();
}

static void island_payload_crc_failure(void) {
    vm_runtime_overlay_status status;
    make_catalog();
    bank3[TEST_OFF_ISLAND] ^= 1u;
    vm_runtime_overlay_host_reset();
    status = vm_runtime_overlay_install_island();
    expect(status == VM_RUNTIME_OVERLAY_ERR_ISLAND,
           "island source crc failure");
    expect(!vm_runtime_overlay_island_ready(), "island source not ready");
    expect(vm_runtime_overlay_fault_latched(),
           "island source failure latches transport");
    vm_runtime_overlay_host_reset();
}

static void island_missing_slot_failure(void) {
    vm_runtime_overlay_status status;
    make_catalog();
    bank3[7] = LISP65_RUNTIME_ISLAND_INSTALL_SLOT;
    finish_directory();
    vm_runtime_overlay_host_reset();
    status = vm_runtime_overlay_install_island();
    expect(status == VM_RUNTIME_OVERLAY_ERR_ISLAND,
           "island missing slot failure");
    expect(!vm_runtime_overlay_island_ready(), "missing island not ready");
    expect(vm_runtime_overlay_fault_latched(),
           "missing island latches transport");
    vm_runtime_overlay_host_reset();
}

static void prepare_batch_island(void) {
    expect(vm_runtime_overlay_install_island() == VM_RUNTIME_OVERLAY_OK,
           "batch island preparation");
    expect(vm_runtime_overlay_island_ready(), "batch island ready");
    entry_calls = verifier_calls = load_calls = predicate_calls = 0;
}

static void batch_positive_and_ops(void) {
    entry_context context = { .result = 9 };
    uint8_t result = LISP65_RUNTIME_OVERLAY_ENTRY_NOT_RUN;
    vm_runtime_overlay_status status;
    make_catalog();
    vm_runtime_overlay_host_reset();
    prepare_batch_island();
    memset(lisp65_runtime_overlay_host_target, 0xcc,
           sizeof lisp65_runtime_overlay_host_target);
    entry_calls = verifier_calls = load_calls = predicate_calls = 0;
    batch_target_calls = 3;
    expected_payload = payload1;
    expected_length = sizeof payload1;
    expected_entry = TEST_VMA + 2;
    status = vm_runtime_overlay_exec_batch(
        TEST_ENTRY_1, &context, &result, VM_RUNTIME_OVERLAY_BATCH_L65M,
        repeat_to_target);
    expect(status == VM_RUNTIME_OVERLAY_OK && result == 9,
           "batch positive result");
    expect(entry_calls == 3 && predicate_calls == 3,
           "batch positive iterations");
    expect(verifier_calls == 2, "batch verifies catalog and record once");
    expect(load_calls == 43, "batch loads catalog record and payload once");
    expect(!vm_runtime_overlay_active() && !vm_runtime_overlay_fault_latched(),
           "batch releases transport");
    expect(range_is(0, sizeof payload1, 0), "batch wipe");
    expect(range_is(sizeof payload1, TEST_LIMIT, 0xcc), "batch exact wipe");
}

static void batch_final_crc(void) {
    entry_context context = { .result = 3, .tamper_after_call = 1 };
    uint8_t result = LISP65_RUNTIME_OVERLAY_ENTRY_NOT_RUN;
    vm_runtime_overlay_status status;
    make_catalog();
    vm_runtime_overlay_host_reset();
    prepare_batch_island();
    memset(lisp65_runtime_overlay_host_target, 0xcc,
           sizeof lisp65_runtime_overlay_host_target);
    entry_calls = predicate_calls = 0;
    batch_target_calls = 1;
    expected_payload = payload1;
    expected_length = sizeof payload1;
    expected_entry = TEST_VMA + 2;
    status = vm_runtime_overlay_exec_batch(
        TEST_ENTRY_1, &context, &result, VM_RUNTIME_OVERLAY_BATCH_L65M,
        repeat_to_target);
    expect(status == VM_RUNTIME_OVERLAY_ERR_CRC, "batch final crc");
    expect(entry_calls == 1 && predicate_calls == 1, "batch final crc calls");
    expect(vm_runtime_overlay_fault_latched(), "batch final crc latch");
    expect(!vm_runtime_overlay_active(), "batch final crc releases busy");
    expect(range_is(0, sizeof payload1, 0), "batch final crc wipe");
    vm_runtime_overlay_host_reset();
}

static void batch_fallback_case(
    const char *name, vm_runtime_overlay_batch_policy policy,
    vm_runtime_overlay_repeat_predicate_fn repeat) {
    entry_context context = { .result = 5 };
    uint8_t result = LISP65_RUNTIME_OVERLAY_ENTRY_NOT_RUN;
    vm_runtime_overlay_status status;
    make_catalog();
    vm_runtime_overlay_host_reset();
    entry_calls = verifier_calls = load_calls = predicate_calls = 0;
    batch_target_calls = 3;
    expected_payload = payload1;
    expected_length = sizeof payload1;
    expected_entry = TEST_VMA + 2;
    status = vm_runtime_overlay_exec_batch(
        TEST_ENTRY_1, &context, &result, policy, repeat);
    expect(status == VM_RUNTIME_OVERLAY_OK && result == 5, name);
    expect(entry_calls == 1 && predicate_calls == 0, name);
    expect(verifier_calls == 2 && load_calls == 43, name);
    expect(!vm_runtime_overlay_fault_latched(), name);
}

static void batch_fallbacks(void) {
    batch_fallback_case("batch NONE fallback", VM_RUNTIME_OVERLAY_BATCH_NONE,
                        repeat_to_target);
    batch_fallback_case("batch invalid-policy fallback",
                        (vm_runtime_overlay_batch_policy)99,
                        repeat_to_target);
    batch_fallback_case("batch commit non-whitelist fallback",
                        VM_RUNTIME_OVERLAY_BATCH_COMMIT, repeat_to_target);
    batch_fallback_case("batch non-whitelist fallback",
                        VM_RUNTIME_OVERLAY_BATCH_LCC, repeat_to_target);
    batch_fallback_case("batch null-predicate fallback",
                        VM_RUNTIME_OVERLAY_BATCH_L65M, 0);
}

static void batch_limit(void) {
    entry_context context = { .result = 6 };
    uint8_t result = LISP65_RUNTIME_OVERLAY_ENTRY_NOT_RUN;
    vm_runtime_overlay_status status;
    make_catalog();
    vm_runtime_overlay_host_reset();
    prepare_batch_island();
    entry_calls = predicate_calls = 0;
    batch_target_calls = 65536u;
    expected_payload = payload1;
    expected_length = sizeof payload1;
    expected_entry = TEST_VMA + 2;
    status = vm_runtime_overlay_exec_batch(
        TEST_ENTRY_1, &context, &result, VM_RUNTIME_OVERLAY_BATCH_L65M,
        repeat_to_target);
    expect(status == VM_RUNTIME_OVERLAY_ERR_BATCH_LIMIT, "batch hard limit");
    expect(entry_calls == 65535u && predicate_calls == 65535u,
           "batch hard limit count");
    expect(result == 6, "batch hard limit last result");
    expect(vm_runtime_overlay_fault_latched(), "batch hard limit latch");
    expect(!vm_runtime_overlay_active(), "batch hard limit releases busy");
    expect(range_is(0, sizeof payload1, 0), "batch hard limit wipe");
    vm_runtime_overlay_host_reset();
}

static void batch_abort_cleanup_recovery(void) {
    entry_context context = { .abort_after_call = 2 };
    uint8_t result = LISP65_RUNTIME_OVERLAY_ENTRY_NOT_RUN;
    vm_runtime_overlay_status status;
    make_catalog();
    vm_runtime_overlay_host_reset();
    prepare_batch_island();
    memset(lisp65_runtime_overlay_host_target, 0xcc,
           sizeof lisp65_runtime_overlay_host_target);
    entry_calls = predicate_calls = 0;
    batch_target_calls = 3;
    expected_payload = payload1;
    expected_length = sizeof payload1;
    expected_entry = TEST_VMA + 2;
    if (setjmp(abort_target) == 0) {
        (void)vm_runtime_overlay_exec_batch(
            TEST_ENTRY_1, &context, &result, VM_RUNTIME_OVERLAY_BATCH_L65M,
            repeat_to_target);
        expect(0, "batch abort escaped active slice");
        return;
    }
    expect(entry_calls == 2 && predicate_calls == 1, "batch abort call count");
    expect(vm_runtime_overlay_active(), "batch abort leaves active marker");
    status = vm_runtime_overlay_abort_cleanup();
    expect(status == VM_RUNTIME_OVERLAY_ERR_ABORTED, "batch abort cleanup status");
    expect(!vm_runtime_overlay_active(), "batch abort cleanup releases busy");
    expect(!vm_runtime_overlay_fault_latched(), "batch abort cleanup no latch");
    expect(vm_runtime_overlay_island_ready(),
           "batch abort cleanup preserves island readiness");
    expect(range_is(0, sizeof payload1, 0), "batch abort cleanup wipe");
    context.abort_after_call = 0;
    status = vm_runtime_overlay_exec(TEST_ENTRY_1, &context, &result);
    expect(status == VM_RUNTIME_OVERLAY_OK && result == 0,
           "transport reusable after batch abort");
}

static void abort_cleanup_recovery(void) {
    entry_context context = { .abort_jump = 1 };
    uint8_t result = 0;
    vm_runtime_overlay_status status;
    make_catalog();
    vm_runtime_overlay_host_reset();
    memset(lisp65_runtime_overlay_host_target, 0xcc,
           sizeof lisp65_runtime_overlay_host_target);
    entry_calls = 0;
    expected_payload = payload1;
    expected_length = sizeof payload1;
    expected_entry = TEST_VMA + 2;
    if (setjmp(abort_target) == 0) {
        (void)vm_runtime_overlay_exec(TEST_ENTRY_1, &context, &result);
        expect(0, "abort escaped active slice");
        return;
    }
    expect(vm_runtime_overlay_active(), "abort leaves active marker");
    status = vm_runtime_overlay_abort_cleanup();
    expect(status == VM_RUNTIME_OVERLAY_ERR_ABORTED, "abort cleanup status");
    expect(!vm_runtime_overlay_active(), "abort cleanup releases busy");
    expect(!vm_runtime_overlay_fault_latched(), "abort cleanup does not latch");
    expect(range_is(0, sizeof payload1, 0), "abort cleanup wipe");
    expect(range_is(sizeof payload1, TEST_LIMIT, 0xcc), "abort cleanup exact wipe");
    context.abort_jump = 0;
    result = LISP65_RUNTIME_OVERLAY_ENTRY_NOT_RUN;
    status = vm_runtime_overlay_exec(TEST_ENTRY_1, &context, &result);
    expect(status == VM_RUNTIME_OVERLAY_OK && result == 0,
           "transport reusable after abort");
    expect(entry_calls == 2, "abort recovery calls");
}

int main(void) {
    positive_and_semantic();
    runtime_size_boundary();
    boot_slot();
    reject("missing-storage", m_missing, VM_RUNTIME_OVERLAY_ERR_CRC);
    reject("magic", m_magic, VM_RUNTIME_OVERLAY_ERR_MAGIC);
    reject_catalog("version-to-boot-catalog", m_version,
                   VM_RUNTIME_OVERLAY_ERR_VERSION);
    reject("header-size", m_header_size, VM_RUNTIME_OVERLAY_ERR_HEADER);
    reject("entry-size", m_entry_size, VM_RUNTIME_OVERLAY_ERR_HEADER);
    reject("count", m_count, VM_RUNTIME_OVERLAY_ERR_HEADER);
    reject("count-large", m_count_large, VM_RUNTIME_OVERLAY_ERR_HEADER);
    reject("header-flags", m_header_flags, VM_RUNTIME_OVERLAY_ERR_HEADER);
    reject("bank", m_bank, VM_RUNTIME_OVERLAY_ERR_HEADER);
    reject("header-reserved-byte", m_header_reserved8, VM_RUNTIME_OVERLAY_ERR_HEADER);
    reject_catalog("build-id-to-boot-catalog", m_profile,
                   VM_RUNTIME_OVERLAY_ERR_PROFILE);
    reject("directory-offset", m_dir_off, VM_RUNTIME_OVERLAY_ERR_HEADER);
    reject("payload-offset", m_payload_off, VM_RUNTIME_OVERLAY_ERR_DIRECTORY);
    reject("image-size", m_image_size, VM_RUNTIME_OVERLAY_ERR_LENGTH);
    reject("directory-crc-field", m_dir_crc, VM_RUNTIME_OVERLAY_ERR_CRC);
    reject("header-crc", m_header_crc, VM_RUNTIME_OVERLAY_ERR_CRC);
    reject("header-reserved-word", m_header_reserved32, VM_RUNTIME_OVERLAY_ERR_HEADER);
    reject("id-order", m_id_order, VM_RUNTIME_OVERLAY_ERR_DIRECTORY);
    reject("flags", m_flags, VM_RUNTIME_OVERLAY_ERR_DIRECTORY);
    reject("file-offset", m_file_off, VM_RUNTIME_OVERLAY_ERR_LENGTH);
    reject("file-length", m_file_len, VM_RUNTIME_OVERLAY_ERR_LENGTH);
    reject("vma", m_vma, VM_RUNTIME_OVERLAY_ERR_VMA);
    reject("memory-length", m_mem_len, VM_RUNTIME_OVERLAY_ERR_LENGTH);
    reject("entry-offset", m_entry_off, VM_RUNTIME_OVERLAY_ERR_ENTRY);
    reject("abi", m_abi, VM_RUNTIME_OVERLAY_ERR_ABI);
    reject("slice-build-id", m_slice_build, VM_RUNTIME_OVERLAY_ERR_PROFILE);
    reject("payload-crc-field", m_payload_crc_field, VM_RUNTIME_OVERLAY_ERR_CRC);
    reject("bss", m_bss, VM_RUNTIME_OVERLAY_ERR_LENGTH);
    reject("capability", m_capability, VM_RUNTIME_OVERLAY_ERR_DIRECTORY);
    reject("entry-reserved", m_entry_reserved, VM_RUNTIME_OVERLAY_ERR_DIRECTORY);
    reject("directory-crc", m_directory_crc, VM_RUNTIME_OVERLAY_ERR_CRC);
    reject("catalog-verifier-crc", m_catalog_verifier_crc,
           VM_RUNTIME_OVERLAY_ERR_CRC);
    reject("record-verifier-crc", m_record_verifier_crc,
           VM_RUNTIME_OVERLAY_ERR_CRC);
    reject("payload-crc", m_payload_crc, VM_RUNTIME_OVERLAY_ERR_CRC);
    reject("slice-limit", m_too_large, VM_RUNTIME_OVERLAY_ERR_LENGTH);
    reject("window-boundary", m_window_boundary, VM_RUNTIME_OVERLAY_ERR_STACK);
    reject("slot-swap", m_swap, VM_RUNTIME_OVERLAY_ERR_DIRECTORY);
    missing_slot();
    stack_boundary();
    argument_failure();
    reentry();
    semantic_error_recovery();
    island_boot_gate();
    island_copy_crc_failure();
    island_payload_crc_failure();
    island_missing_slot_failure();
    batch_positive_and_ops();
    batch_final_crc();
    batch_fallbacks();
    batch_limit();
    batch_abort_cleanup_recovery();
    abort_cleanup_recovery();
    if (failed) {
        fprintf(stderr, "runtime-overlay-smoke: FAIL failures=%d\n", failed);
        return 1;
    }
    printf("runtime-overlay-smoke: PASS reusable+batch+45 fail-closed cases\n");
    return 0;
}
