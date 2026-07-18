/* Integrated host report for the L65M repeat-batch transport shape. */
#include <errno.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "l65m_overlay_abi.h"
#include "vm_runtime_overlay.h"
#include "l65m-bulkread-cases.h"
#ifdef LISP65_C1_TRUST_FASTPATH_PROBE
#include "obj.h"
#include "dialect-v2/libs/lcc-contract.h"
#endif

#define TEST_VMA                 0x9000u
#define TEST_LIMIT               LISP65_RUNTIME_OVERLAY_HARD_MAX_SLICE
#define TEST_BUILD_ID            0x13579bdfUL
#define TEST_MIN_SLOT_COUNT      (LISP65_RUNTIME_OVERLAY_APPLICATION_SLOT_BASE + \
                                  L65M_OVERLAY_PHASE_COUNT)
#define TEST_CATALOG_OFF         0x1000u
#define TEST_RECORD_OFF          0x1100u
#define TEST_APPLICATION_OFF     0x1200u
#define TEST_APPLICATION_SIZE    8u
#define SCRATCH_DMA_TOTAL_BUDGET 15000u
#define SCRATCH_DMA_PHASE_05_BUDGET 1500u
#define SCRATCH_DMA_PHASE_15_BUDGET 500u
#define SCRATCH_DMA_PHASE_16_BUDGET 750u

enum {
    TRANSPORT_INGRESS_CRCS = 3,
    TRANSPORT_EGRESS_CRCS = 1,
    CATALOG_METADATA_CRCS = 2
};

typedef uint8_t (*phase_fn)(void *context);

typedef struct {
    const uint8_t *data;
    uint16_t length;
    uint32_t reads;
    uint32_t read_bytes;
    uint32_t dma_calls;
} file_source;

typedef struct {
    uint32_t iterations;
    uint32_t source_reads;
    uint32_t source_read_bytes;
    uint32_t scratch_dma_calls_contracted;
    uint32_t scratch_dma_calls_projected;
    uint32_t catalog_verifier_loads;
    uint32_t catalog_header_loads;
    uint32_t catalog_directory_loads;
    uint32_t record_verifier_loads;
    uint32_t record_data_loads;
    uint32_t application_loads;
    uint32_t ingress_crcs;
    uint32_t egress_crcs;
    uint32_t catalog_metadata_crcs;
} phase_ops;

typedef struct {
    unsigned batch_calls;
    unsigned single_calls;
    unsigned batch_policy_refs;
    unsigned repeat_predicate_refs;
    unsigned phase_loops;
    unsigned do_loops;
} integration_audit;

typedef struct {
    unsigned bulk_read_refs;
    unsigned byte_get_refs;
} scratch_source_audit;

static const char *const phase_names[L65M_OVERLAY_PHASE_COUNT] = {
    "container", "header", "sections", "strings", "entries", "entry-names",
    "code", "indices", "nodes", "node-strings", "graph", "patches",
    "root-keep-cost", "topology-cost", "string-cost", "entry-symbols",
    "node-symbols", "node-entry-dedup", "implicit-symbols", "table-capacities",
    "memory-capacities"
};

static const phase_fn phase_functions[L65M_OVERLAY_PHASE_COUNT] = {
    l65m_overlay_phase_00, l65m_overlay_phase_01, l65m_overlay_phase_02,
    l65m_overlay_phase_03, l65m_overlay_phase_04, l65m_overlay_phase_05,
    l65m_overlay_phase_06, l65m_overlay_phase_07, l65m_overlay_phase_08,
    l65m_overlay_phase_09, l65m_overlay_phase_10, l65m_overlay_phase_11,
    l65m_overlay_phase_12, l65m_overlay_phase_13, l65m_overlay_phase_14,
    l65m_overlay_phase_15, l65m_overlay_phase_16, l65m_overlay_phase_17,
    l65m_overlay_phase_18, l65m_overlay_phase_19, l65m_overlay_phase_20
};

static uint32_t phase_scratch_dma_budget(unsigned phase) {
    if (phase == 5u) return SCRATCH_DMA_PHASE_05_BUDGET;
    if (phase == 15u) return SCRATCH_DMA_PHASE_15_BUDGET;
    if (phase == 16u) return SCRATCH_DMA_PHASE_16_BUDGET;
    return 3000u;
}

uint8_t lisp65_runtime_overlay_host_target[TEST_LIMIT];
const uint16_t lisp65_runtime_overlay_host_vma = TEST_VMA;
uint16_t lisp65_runtime_overlay_host_limit = TEST_VMA + TEST_LIMIT;
uint16_t lisp65_runtime_overlay_host_soft_sp = 0xffffu;
uint8_t lisp65_resident_island_host_target[
    LISP65_RUNTIME_ISLAND_CAPACITY];

static uint8_t attic[65536];
static const uint8_t catalog_verifier[] = {
    'R', 'T', 'O', 'V', 'C', '1', 0xa5, 0x5a
};
static const uint8_t record_verifier[] = {
    'R', 'T', 'O', 'V', 'R', '1', 0xa5, 0x5a
};
static phase_ops *active_ops;
static unsigned active_phase;
static uint8_t tamper_application;
static unsigned app_calls;
static unsigned unexpected_loads;
static uint8_t test_slot_count = LISP65_RUNTIME_ISLAND_INSTALL_SLOT + 1u;

static unsigned count_text(const char *text, const char *needle) {
    unsigned count = 0;
    size_t length = strlen(needle);
    while ((text = strstr(text, needle)) != 0) {
        count++;
        text += length;
    }
    return count;
}

static unsigned audit_integration_body(
    const char *body, integration_audit *audit, FILE *errors) {
    unsigned violations = 0;
    memset(audit, 0, sizeof *audit);
    audit->batch_calls = count_text(body, "vm_runtime_overlay_exec_batch(");
    audit->single_calls = count_text(body, "vm_runtime_overlay_exec(");
    audit->batch_policy_refs = count_text(body, "VM_RUNTIME_OVERLAY_BATCH_L65M");
    audit->repeat_predicate_refs = count_text(body, "vm_l65m_batch_repeat");
    audit->phase_loops = count_text(
        body, "for (phase = 0; phase < L65M_OVERLAY_PHASE_COUNT; phase++)");
    audit->do_loops = count_text(body, "do {") + count_text(body, "do{");
#define AUDIT_REQUIRE(condition, message) do { \
    if (!(condition)) { \
        if (errors) fprintf(errors, "integration=%s\n", (message)); \
        violations++; \
    } \
} while (0)
    AUDIT_REQUIRE(audit->batch_calls == 1, "preflight-batch-call-count-not-one");
    AUDIT_REQUIRE(audit->single_calls == 0, "preflight-contains-single-exec");
    AUDIT_REQUIRE(audit->batch_policy_refs == 1, "preflight-l65m-policy-count-not-one");
    AUDIT_REQUIRE(audit->repeat_predicate_refs == 1,
                  "preflight-repeat-predicate-count-not-one");
    AUDIT_REQUIRE(audit->phase_loops == 1, "preflight-phase-loop-count-not-one");
    AUDIT_REQUIRE(audit->do_loops == 0, "preflight-contains-inner-do-loop");
#undef AUDIT_REQUIRE
    return violations;
}

static char *read_text_file(const char *path, size_t *length_out) {
    FILE *stream = fopen(path, "rb");
    char *text;
    long length;
    if (!stream || fseek(stream, 0, SEEK_END) || (length = ftell(stream)) < 0 ||
        fseek(stream, 0, SEEK_SET)) {
        if (stream) fclose(stream);
        return 0;
    }
    text = (char *)malloc((size_t)length + 1u);
    if (!text || fread(text, 1, (size_t)length, stream) != (size_t)length) {
        free(text);
        fclose(stream);
        return 0;
    }
    fclose(stream);
    text[length] = 0;
    *length_out = (size_t)length;
    return text;
}

static unsigned audit_integration_file(
    const char *path, integration_audit *audit, FILE *errors) {
    static const char signature[] = "l65m_status vm_preflight_lib_ext";
    size_t file_length, body_length;
    char *text = read_text_file(path, &file_length);
    char *start, *open, *cursor, *body;
    unsigned depth = 0, violations;
    (void)file_length;
    if (!text) {
        if (errors) fprintf(errors, "integration=cannot-read-%s\n", path);
        return 1;
    }
    start = strstr(text, signature);
    open = start ? strchr(start, '{') : 0;
    if (!open) {
        if (errors) fprintf(errors, "integration=vm-preflight-function-missing\n");
        free(text);
        return 1;
    }
    cursor = open;
    do {
        if (*cursor == '{') depth++;
        else if (*cursor == '}') depth--;
        cursor++;
    } while (depth && *cursor);
    if (depth) {
        if (errors) fprintf(errors, "integration=vm-preflight-function-unclosed\n");
        free(text);
        return 1;
    }
    body_length = (size_t)(cursor - open);
    body = (char *)malloc(body_length + 1u);
    if (!body) {
        free(text);
        return 1;
    }
    memcpy(body, open, body_length);
    body[body_length] = 0;
    violations = audit_integration_body(body, audit, errors);
    free(body);
    free(text);
    return violations;
}

static unsigned audit_scratch_source_file(
    const char *path, scratch_source_audit *audit, FILE *errors) {
    static const char signature[] = "static uint8_t disk_lib_read";
    size_t file_length, body_length;
    char *text = read_text_file(path, &file_length);
    char *start, *open, *cursor, *body;
    unsigned depth = 0, violations = 0;
    (void)file_length;
    memset(audit, 0, sizeof *audit);
    if (!text) {
        if (errors) fprintf(errors, "scratch-source=cannot-read-%s\n", path);
        return 1;
    }
    start = strstr(text, signature);
    open = start ? strchr(start, '{') : 0;
    if (!open) {
        if (errors) fprintf(errors, "scratch-source=disk-lib-read-function-missing\n");
        free(text);
        return 1;
    }
    cursor = open;
    do {
        if (*cursor == '{') depth++;
        else if (*cursor == '}') depth--;
        cursor++;
    } while (depth && *cursor);
    if (depth) {
        if (errors) fprintf(errors, "scratch-source=disk-lib-read-function-unclosed\n");
        free(text);
        return 1;
    }
    body_length = (size_t)(cursor - open);
    body = (char *)malloc(body_length + 1u);
    if (!body) {
        free(text);
        return 1;
    }
    memcpy(body, open, body_length);
    body[body_length] = 0;
    audit->bulk_read_refs = count_text(body, "ext_disk_read(");
    audit->byte_get_refs = count_text(body, "ext_disk_get(");
    if (audit->bulk_read_refs != 1u) {
        if (errors) fprintf(errors, "scratch-source=ext-disk-read-count-not-one\n");
        violations++;
    }
    if (audit->byte_get_refs != 0u) {
        if (errors) fprintf(errors, "scratch-source=contains-byte-get\n");
        violations++;
    }
    free(body);
    free(text);
    return violations;
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

static uint16_t application_off(unsigned phase) {
    return (uint16_t)(TEST_APPLICATION_OFF + phase * 0x0100u);
}

static const uint8_t *application_payload(unsigned phase) {
    return attic + application_off(phase);
}

static void fill_record(uint8_t *record, uint16_t slot, uint16_t file_off,
                        const uint8_t *payload) {
    put16(record, slot);
    put16(record + 2, LISP65_RUNTIME_OVERLAY_FLAG_RUNTIME |
                         LISP65_RUNTIME_OVERLAY_FLAG_REUSABLE);
    put16(record + 4, file_off);
    put16(record + 6, TEST_APPLICATION_SIZE);
    put16(record + 8, TEST_VMA);
    put16(record + 10, TEST_APPLICATION_SIZE);
    put16(record + 12, 0);
    put16(record + 14, LISP65_RUNTIME_OVERLAY_ENTRY_ABI_V1);
    put32(record + 16, TEST_BUILD_ID);
    put16(record + 20, crc16(payload, TEST_APPLICATION_SIZE));
}

static void make_catalog(void) {
    uint8_t *record;
    uint16_t directory_bytes = test_slot_count * LISP65_RUNTIME_OVERLAY_ENTRY_SIZE;
    uint16_t payload_off = (uint16_t)((LISP65_RUNTIME_OVERLAY_HEADER_SIZE +
                                      directory_bytes + 255u) & 0xff00u);
    unsigned phase, slot;
    memset(attic, 0, sizeof attic);
    memcpy(attic + TEST_CATALOG_OFF, catalog_verifier, sizeof catalog_verifier);
    memcpy(attic + TEST_RECORD_OFF, record_verifier, sizeof record_verifier);
    for (phase = 0; phase < L65M_OVERLAY_PHASE_COUNT; phase++) {
        uint8_t *payload = attic + application_off(phase);
        payload[0] = 'L'; payload[1] = '6'; payload[2] = '5'; payload[3] = 'P';
        payload[4] = 'H'; payload[5] = (uint8_t)phase; payload[6] = 0xa5;
        payload[7] = 0x5a;
    }
    attic[0] = LISP65_RUNTIME_OVERLAY_MAGIC_0;
    attic[1] = LISP65_RUNTIME_OVERLAY_MAGIC_1;
    attic[2] = LISP65_RUNTIME_OVERLAY_MAGIC_2;
    attic[3] = LISP65_RUNTIME_OVERLAY_MAGIC_3;
    attic[4] = LISP65_RUNTIME_OVERLAY_FORMAT_VERSION;
    attic[5] = LISP65_RUNTIME_OVERLAY_HEADER_SIZE;
    attic[6] = LISP65_RUNTIME_OVERLAY_ENTRY_SIZE;
    attic[7] = test_slot_count;
    attic[10] = 3;
    put32(attic + 12, TEST_BUILD_ID);
    put16(attic + 16, LISP65_RUNTIME_OVERLAY_HEADER_SIZE);
    put16(attic + 18, payload_off);
    put32(attic + 20, application_off(L65M_OVERLAY_PHASE_COUNT - 1u) +
                         TEST_APPLICATION_SIZE);
    record = attic + LISP65_RUNTIME_OVERLAY_HEADER_SIZE;
    fill_record(record, 0, TEST_CATALOG_OFF, catalog_verifier);
    record += LISP65_RUNTIME_OVERLAY_ENTRY_SIZE;
    fill_record(record, 1, TEST_RECORD_OFF, record_verifier);
    for (phase = 0; phase < L65M_OVERLAY_PHASE_COUNT; phase++) {
        record += LISP65_RUNTIME_OVERLAY_ENTRY_SIZE;
        fill_record(record, (uint16_t)(LISP65_RUNTIME_OVERLAY_APPLICATION_SLOT_BASE + phase),
                    application_off(phase), application_payload(phase));
    }
    for (slot = TEST_MIN_SLOT_COUNT; slot < test_slot_count; slot++) {
        record += LISP65_RUNTIME_OVERLAY_ENTRY_SIZE;
        put16(record, (uint16_t)slot);
    }
    put16(attic + 24, crc16(attic + LISP65_RUNTIME_OVERLAY_HEADER_SIZE,
                            directory_bytes));
    put16(attic + 26, 0);
    put16(attic + 26, crc16(attic, LISP65_RUNTIME_OVERLAY_HEADER_SIZE));
}

void vm_code_load(uint8_t bank, uint16_t off, uint16_t length, uint8_t *dst) {
    if (active_ops) {
        if (dst == lisp65_runtime_overlay_host_target && off == TEST_CATALOG_OFF)
            active_ops->catalog_verifier_loads++;
        else if (dst == lisp65_runtime_overlay_host_target && off == TEST_RECORD_OFF)
            active_ops->record_verifier_loads++;
        else if (dst == lisp65_runtime_overlay_host_target &&
                 off == application_off(active_phase))
            active_ops->application_loads++;
        else if (off == 0 && length == LISP65_RUNTIME_OVERLAY_HEADER_SIZE)
            active_ops->catalog_header_loads++;
        else if (length == LISP65_RUNTIME_OVERLAY_ENTRY_SIZE &&
                 off == LISP65_RUNTIME_OVERLAY_HEADER_SIZE +
                        (LISP65_RUNTIME_OVERLAY_APPLICATION_SLOT_BASE + active_phase) *
                        LISP65_RUNTIME_OVERLAY_ENTRY_SIZE &&
                 active_ops->record_verifier_loads)
            active_ops->record_data_loads++;
        else if (length == LISP65_RUNTIME_OVERLAY_ENTRY_SIZE &&
                 off >= LISP65_RUNTIME_OVERLAY_HEADER_SIZE &&
                 off < LISP65_RUNTIME_OVERLAY_HEADER_SIZE +
                       test_slot_count * LISP65_RUNTIME_OVERLAY_ENTRY_SIZE)
            active_ops->catalog_directory_loads++;
        else
            unexpected_loads++;
    }
    if (bank != 3 || (uint32_t)off + length > sizeof attic) {
        memset(dst, 0, length);
        return;
    }
    memcpy(dst, attic + off, length);
}

uint8_t vm_runtime_overlay_host_call(uint16_t entry, void *context) {
    if (entry == TEST_VMA &&
        memcmp(lisp65_runtime_overlay_host_target, catalog_verifier,
               sizeof catalog_verifier) == 0)
        return vm_runtime_overlay_catalog_verifier(context);
    if (entry == TEST_VMA &&
        memcmp(lisp65_runtime_overlay_host_target, record_verifier,
               sizeof record_verifier) == 0)
        return vm_runtime_overlay_record_verifier(context);
    if (entry != TEST_VMA || !active_ops ||
        memcmp(lisp65_runtime_overlay_host_target, application_payload(active_phase),
               TEST_APPLICATION_SIZE) != 0)
        return L65M_ERR_STATE;
    app_calls++;
    if (tamper_application)
        lisp65_runtime_overlay_host_target[TEST_APPLICATION_SIZE - 1u] ^= 1u;
    return phase_functions[active_phase](context);
}

static uint8_t repeat_phase(void *context, uint8_t slot, uint8_t entry_result) {
    l65m_overlay_work *work = (l65m_overlay_work *)context;
    if (!work || slot != LISP65_RUNTIME_OVERLAY_APPLICATION_SLOT_BASE + active_phase)
        return 0;
    return (uint8_t)(entry_result == L65M_OK && work->repeat_phase &&
                     work->expected_phase == active_phase && !work->finished);
}

static uint8_t read_file(void *opaque, uint16_t off, uint8_t *dst, uint16_t length) {
    file_source *source = (file_source *)opaque;
    source->reads++;
    source->read_bytes += length;
    if (length) source->dma_calls++;
    if (off > source->length || length > (uint16_t)(source->length - off)) return 0;
    if (length) memcpy(dst, source->data + off, length);
    return 1;
}

static uint8_t no_symbol_exists(void *opaque, const char *name) {
    (void)opaque;
    (void)name;
    return 0;
}

static int load_image(const char *path, file_source *source) {
    FILE *stream = fopen(path, "rb");
    long size;
    uint8_t *data;
    if (!stream) {
        fprintf(stderr, "l65m-transport-ops: cannot open %s: %s\n", path,
                strerror(errno));
        return 0;
    }
    if (fseek(stream, 0, SEEK_END) || (size = ftell(stream)) <= 0 ||
        size > 65535L || fseek(stream, 0, SEEK_SET)) {
        fprintf(stderr, "l65m-transport-ops: invalid image size for %s\n", path);
        fclose(stream);
        return 0;
    }
    data = (uint8_t *)malloc((size_t)size);
    if (!data || fread(data, 1, (size_t)size, stream) != (size_t)size) {
        fprintf(stderr, "l65m-transport-ops: cannot read %s\n", path);
        free(data);
        fclose(stream);
        return 0;
    }
    fclose(stream);
    source->data = data;
    source->length = (uint16_t)size;
    source->reads = 0;
    source->read_bytes = 0;
    source->dma_calls = 0;
    return 1;
}

#ifdef LISP65_C1_TRUST_FASTPATH_PROBE
static file_source *c1_fastpath_source;

static uint8_t read_c1_fastpath(void *opaque, uint16_t off, uint8_t *dst,
                                uint16_t length) {
    (void)opaque;
    return read_file(c1_fastpath_source, off, dst, length);
}

static void c1_fastpath_limits(l65m_limits *limits) {
    memset(limits, 0, sizeof *limits);
    limits->dir_capacity = 608u;
    limits->symbol_capacity = 752u;
    limits->namepool_capacity = 10208u;
    limits->heap_free = 1024u;
    limits->arena_capacity = 9280u;
    limits->roots_capacity = 128u;
    limits->string_arena = 1u;
    limits->symbol_exists = no_symbol_exists;
}

static l65m_status c1_fastpath_phase(l65m_overlay_work *work,
                                     unsigned phase) {
    l65m_status status;
    do {
        status = (l65m_status)phase_functions[phase](work);
    } while (status == L65M_OK && work->expected_phase == phase);
    return status;
}

static int c1_fastpath_capacity_case(file_source *bytes,
                                     l65m_limits *limits,
                                     l65m_status expected) {
    l65m_source source = {
        read_c1_fastpath,
        (void *)(uintptr_t)((uint16_t)MK_SYMI(1u) | 1u),
        LISP65_C1_COMPILER_CONTAINER_BYTES
    };
    l65m_plan plan;
    l65m_overlay_work work;
    l65m_status status;
    c1_fastpath_source = bytes;
    l65m_overlay_work_init(&work, &source, 0x4200u, limits, &plan);
    status = c1_fastpath_phase(&work, 0u);
    if (status != expected || source.ctx !=
            (void *)(uintptr_t)(uint16_t)MK_SYMI(1u))
        return 0;
    return expected != L65M_OK || (work.flags & 128u) != 0;
}

static int c1_fastpath_selftest(const char *image_path) {
    file_source bytes = { 0 };
    l65m_source source;
    l65m_limits limits;
    l65m_plan plan;
    l65m_overlay_work work;
    l65m_status status = L65M_OK;
    unsigned phase;
    unsigned failures = 0;
    uint32_t reads_before;
    static const struct {
        const char *name;
        l65m_status expected;
        unsigned field;
    } capacity_cases[] = {
        { "directory", L65M_ERR_DIRECTORY, 0u },
        { "symbols", L65M_ERR_SYMBOLS, 1u },
        { "namepool", L65M_ERR_NAMEPOOL, 2u },
        { "heap", L65M_ERR_HEAP, 3u },
        { "roots", L65M_ERR_ROOTS, 4u },
        { "arena", L65M_ERR_ARENA, 5u }
    };

    if (!load_image(image_path, &bytes)) return 1;
    if (bytes.length != LISP65_C1_COMPILER_CONTAINER_BYTES) {
        fprintf(stderr, "c1-fastpath-selftest: generated length mismatch\n");
        free((void *)bytes.data);
        return 1;
    }
    c1_fastpath_source = &bytes;
    source.read = read_c1_fastpath;
    source.ctx = (void *)(uintptr_t)((uint16_t)MK_SYMI(1u) | 1u);
    source.length = bytes.length;
    c1_fastpath_limits(&limits);
    limits.dir_count = 3u;
    limits.symbol_count = 17u;
    limits.namepool_used = 99u;
    limits.heap_free = 900u;
    limits.arena_used = 23u;
    limits.roots_used = 7u;
    l65m_overlay_work_init(&work, &source, 0x4200u, &limits, &plan);
    reads_before = bytes.reads;
    for (phase = 0; phase <= 3u && status == L65M_OK; phase++)
        status = c1_fastpath_phase(&work, phase);
    if (status != L65M_OK || !work.finished ||
        work.expected_phase != L65M_OVERLAY_PHASE_COUNT ||
        !(work.flags & 128u) || bytes.reads != reads_before ||
        source.ctx != (void *)(uintptr_t)(uint16_t)MK_SYMI(1u))
        failures++;
#define C1_EXPECT(field, value) do { if (plan.field != (value)) failures++; } while (0)
    C1_EXPECT(source_length, LISP65_C1_COMPILER_CONTAINER_BYTES);
    C1_EXPECT(source_crc16, LISP65_C1_COMPILER_CONTAINER_CRC16);
    C1_EXPECT(source_blob_off, 4u);
    C1_EXPECT(source_metadata_off, 4u + LISP65_C1_COMPILER_BLOB_BYTES);
    C1_EXPECT(blob_len, LISP65_C1_COMPILER_BLOB_BYTES);
    C1_EXPECT(metadata_len, LISP65_C1_PLAN_METADATA_BYTES);
    C1_EXPECT(entry_count, LISP65_C1_COMPILER_ENTRY_COUNT);
    C1_EXPECT(index_count, LISP65_C1_PLAN_INDEX_COUNT);
    C1_EXPECT(node_count, LISP65_C1_PLAN_NODE_COUNT);
    C1_EXPECT(patch_count, LISP65_C1_PLAN_PATCH_COUNT);
    C1_EXPECT(entries_off, LISP65_C1_PLAN_ENTRIES_OFF);
    C1_EXPECT(index_off, LISP65_C1_PLAN_INDEX_OFF);
    C1_EXPECT(nodes_off, LISP65_C1_PLAN_NODES_OFF);
    C1_EXPECT(patches_off, LISP65_C1_PLAN_PATCHES_OFF);
    C1_EXPECT(strings_off, LISP65_C1_PLAN_STRINGS_OFF);
    C1_EXPECT(strings_bytes, LISP65_C1_PLAN_STRINGS_BYTES);
    C1_EXPECT(new_symbols, LISP65_C1_PLAN_SYMBOL_CEILING);
    C1_EXPECT(new_name_bytes, LISP65_C1_PLAN_NAME_BYTES_CEILING);
    C1_EXPECT(heap_cells, LISP65_C1_PLAN_HEAP_CELLS);
    C1_EXPECT(arena_bytes, LISP65_C1_PLAN_ARENA_BYTES);
    C1_EXPECT(root_slots, LISP65_C1_PLAN_ROOT_SLOTS);
    C1_EXPECT(max_graph_depth, 0x80u | LISP65_C1_PLAN_MAX_GRAPH_DEPTH);
    C1_EXPECT(format_version, LISP65_C1_COMPILER_FORMAT_VERSION);
    C1_EXPECT(code_base, 0x4200u);
    C1_EXPECT(dir_before, limits.dir_count);
    C1_EXPECT(dir_after, 8u + LISP65_C1_COMPILER_ENTRY_COUNT);
    C1_EXPECT(symbols_before, limits.symbol_count);
    C1_EXPECT(namepool_before, limits.namepool_used);
    C1_EXPECT(heap_free_before, limits.heap_free);
    C1_EXPECT(arena_used_before, limits.arena_used);
    C1_EXPECT(roots_before, limits.roots_used);
#undef C1_EXPECT

    /* An untagged source and a tagged wrong-length source must not inherit
     * the trusted plan. */
    source.ctx = (void *)(uintptr_t)(uint16_t)MK_SYMI(1u);
    source.length = bytes.length;
    bytes.reads = 0;
    l65m_overlay_work_init(&work, &source, 0x4200u, &limits, &plan);
    status = c1_fastpath_phase(&work, 0u);
    if (status != L65M_OK || (work.flags & 128u) || !bytes.reads ||
        work.expected_phase != 1u) failures++;

    source.ctx = (void *)(uintptr_t)((uint16_t)MK_SYMI(1u) | 1u);
    source.length = (uint16_t)(bytes.length - 1u);
    bytes.reads = 0;
    l65m_overlay_work_init(&work, &source, 0x4200u, &limits, &plan);
    status = c1_fastpath_phase(&work, 0u);
    if (status != L65M_ERR_CONTAINER || (work.flags & 128u) || !bytes.reads)
        failures++;

    for (phase = 0; phase < sizeof capacity_cases / sizeof capacity_cases[0];
         phase++) {
        c1_fastpath_limits(&limits);
        switch (capacity_cases[phase].field) {
        case 0: limits.dir_capacity = LISP65_C1_COMPILER_ENTRY_COUNT - 1u; break;
        case 1: limits.symbol_capacity = LISP65_C1_PLAN_SYMBOL_CEILING - 1u; break;
        case 2: limits.namepool_capacity = LISP65_C1_PLAN_NAME_BYTES_CEILING - 1u; break;
        case 3: limits.heap_free = LISP65_C1_PLAN_HEAP_CELLS - 1u; break;
        case 4: limits.roots_capacity = LISP65_C1_PLAN_ROOT_SLOTS - 1u; break;
        default: limits.arena_capacity = LISP65_C1_PLAN_ARENA_BYTES - 1u; break;
        }
        if (!c1_fastpath_capacity_case(&bytes, &limits,
                                       capacity_cases[phase].expected)) {
            fprintf(stderr, "c1-fastpath-selftest: capacity case failed: %s\n",
                    capacity_cases[phase].name);
            failures++;
        }
    }
    free((void *)bytes.data);
    if (failures) {
        fprintf(stderr, "c1-fastpath-selftest: FAIL failures=%u\n", failures);
        return 1;
    }
    printf("c1-fastpath-selftest: PASS exact-plan=28 no-source-reads=yes "
           "fallbacks=2 capacity-rejections=6 commit-crc-bound=%04x\n",
           (unsigned)LISP65_C1_COMPILER_CONTAINER_CRC16);
    return 0;
}
#endif

static unsigned check_phase(unsigned phase, const phase_ops *ops, FILE *errors) {
    unsigned violations = 0;
#define REQUIRE(condition, message) do { \
    if (!(condition)) { \
        if (errors) fprintf(errors, "phase_%02u=%s\n", phase, (message)); \
        violations++; \
    } \
} while (0)
    REQUIRE(ops->iterations > 0, "no-logical-iteration");
    REQUIRE(ops->scratch_dma_calls_contracted == ops->source_reads,
            "source-read-call-not-counted-as-scratch-dma");
    REQUIRE(ops->scratch_dma_calls_projected == ops->scratch_dma_calls_contracted,
            "scratch-dma-projection-mismatch");
    REQUIRE(ops->scratch_dma_calls_projected <= phase_scratch_dma_budget(phase),
            "scratch-dma-phase-budget-exceeded");
    REQUIRE(ops->catalog_verifier_loads == 1, "catalog-verifier-not-loaded-once");
    REQUIRE(ops->catalog_header_loads == 1, "catalog-header-not-loaded-once");
    REQUIRE(ops->catalog_directory_loads == test_slot_count,
            "catalog-directory-not-loaded-once");
    REQUIRE(ops->record_verifier_loads == 1, "record-verifier-not-loaded-once");
    REQUIRE(ops->record_data_loads == 1, "application-record-not-loaded-once");
    REQUIRE(ops->application_loads == 1, "application-slice-not-loaded-once");
    REQUIRE(ops->ingress_crcs == TRANSPORT_INGRESS_CRCS,
            "transport-ingress-crc-count-not-three");
    REQUIRE(ops->egress_crcs == TRANSPORT_EGRESS_CRCS,
            "batch-completion-crc-count-not-one");
    if (ops->iterations > 1) {
        REQUIRE(ops->application_loads < ops->iterations,
                "application-slice-reloaded-per-iteration");
        REQUIRE(ops->ingress_crcs + ops->egress_crcs < ops->iterations * 3u,
                "transport-crc-repeated-per-iteration");
    }
#undef REQUIRE
    return violations;
}

static unsigned check_total(const phase_ops *ops, FILE *errors) {
    unsigned violations = 0;
    if (ops->scratch_dma_calls_contracted != ops->scratch_dma_calls_projected) {
        if (errors) fprintf(errors, "total=scratch-dma-projection-mismatch\n");
        violations++;
    }
    if (ops->scratch_dma_calls_projected > SCRATCH_DMA_TOTAL_BUDGET) {
        if (errors) {
            fprintf(errors, "total=scratch-dma-budget-exceeded projected=%lu budget=%u\n",
                    (unsigned long)ops->scratch_dma_calls_projected,
                    (unsigned)SCRATCH_DMA_TOTAL_BUDGET);
        }
        violations++;
    }
    return violations;
}

static int selftest(void) {
    phase_ops good = { 17, 99, 777, 99, 99, 1, 1,
                       LISP65_RUNTIME_ISLAND_INSTALL_SLOT + 1u, 1, 1, 1,
                       TRANSPORT_INGRESS_CRCS, TRANSPORT_EGRESS_CRCS,
                       CATALOG_METADATA_CRCS };
    phase_ops reload = good;
    phase_ops total;
    l65m_overlay_work work;
    uint8_t result = LISP65_RUNTIME_OVERLAY_ENTRY_NOT_RUN;
    vm_runtime_overlay_status status;
    integration_audit audit;
    scratch_source_audit scratch_audit;
    uint16_t fixture_index;
    static const char good_integration[] =
        "{ for (phase = 0; phase < L65M_OVERLAY_PHASE_COUNT; phase++) "
        "vm_runtime_overlay_exec_batch(slot, &work, &result, "
        "VM_RUNTIME_OVERLAY_BATCH_L65M, vm_l65m_batch_repeat); }";
    static const char reload_integration[] =
        "{ for (phase = 0; phase < L65M_OVERLAY_PHASE_COUNT; phase++) { do { "
        "vm_runtime_overlay_exec(slot, &work, &result); } while (repeat); } }";
    static const char good_scratch_source[] =
        "{ ext_disk_read((uint16_t)(BASE + off), dst, len); return 1; }";
    static const char byte_scratch_source[] =
        "{ while (len--) *dst++ = ext_disk_get(off++); return 1; }";
    if (check_phase(5, &good, 0)) return 1;
    reload.catalog_verifier_loads = reload.catalog_header_loads = reload.iterations;
    test_slot_count = LISP65_RUNTIME_ISLAND_INSTALL_SLOT + 1u;
    reload.catalog_directory_loads = reload.iterations * test_slot_count;
    reload.record_verifier_loads = reload.record_data_loads = reload.iterations;
    reload.application_loads = reload.iterations;
    reload.ingress_crcs = reload.iterations * 3u;
    if (!check_phase(5, &reload, 0)) {
        fprintf(stderr, "l65m-transport-ops-selftest: reload mutation survived\n");
        return 1;
    }
    good.scratch_dma_calls_contracted = SCRATCH_DMA_PHASE_05_BUDGET + 1u;
    good.scratch_dma_calls_projected = good.scratch_dma_calls_contracted;
    good.source_reads = good.scratch_dma_calls_contracted;
    if (!check_phase(5, &good, 0)) {
        fprintf(stderr, "l65m-transport-ops-selftest: phase DMA budget mutation survived\n");
        return 1;
    }
    good.source_reads = 99;
    good.scratch_dma_calls_contracted = 99;
    good.scratch_dma_calls_projected = 98;
    if (!check_phase(5, &good, 0)) {
        fprintf(stderr, "l65m-transport-ops-selftest: DMA projection mutation survived\n");
        return 1;
    }
    good.scratch_dma_calls_projected = 99;
    total = good;
    total.scratch_dma_calls_contracted = SCRATCH_DMA_TOTAL_BUDGET + 1u;
    total.scratch_dma_calls_projected = total.scratch_dma_calls_contracted;
    if (!check_total(&total, 0)) {
        fprintf(stderr, "l65m-transport-ops-selftest: total DMA budget mutation survived\n");
        return 1;
    }
    good.egress_crcs = 0;
    if (!check_phase(5, &good, 0)) {
        fprintf(stderr, "l65m-transport-ops-selftest: missing egress CRC survived\n");
        return 1;
    }
    if (audit_integration_body(good_integration, &audit, 0)) {
        fprintf(stderr, "l65m-transport-ops-selftest: valid integration rejected\n");
        return 1;
    }
    if (!audit_integration_body(reload_integration, &audit, 0)) {
        fprintf(stderr, "l65m-transport-ops-selftest: reload integration survived\n");
        return 1;
    }
    memset(&scratch_audit, 0, sizeof scratch_audit);
    scratch_audit.bulk_read_refs = count_text(good_scratch_source, "ext_disk_read(");
    scratch_audit.byte_get_refs = count_text(good_scratch_source, "ext_disk_get(");
    if (scratch_audit.bulk_read_refs != 1 || scratch_audit.byte_get_refs) {
        fprintf(stderr, "l65m-transport-ops-selftest: bulk scratch adapter rejected\n");
        return 1;
    }
    scratch_audit.bulk_read_refs = count_text(byte_scratch_source, "ext_disk_read(");
    scratch_audit.byte_get_refs = count_text(byte_scratch_source, "ext_disk_get(");
    if (scratch_audit.bulk_read_refs == 1 && !scratch_audit.byte_get_refs) {
        fprintf(stderr, "l65m-transport-ops-selftest: byte scratch adapter survived\n");
        return 1;
    }

    make_catalog();
    memset(&work, 0, sizeof work);
    active_phase = 0;
    active_ops = &good;
    tamper_application = 1;
    app_calls = unexpected_loads = 0;
    vm_runtime_overlay_host_reset();
    vm_runtime_overlay_host_assume_island_ready();
    status = vm_runtime_overlay_exec_batch(
        LISP65_RUNTIME_OVERLAY_APPLICATION_SLOT_BASE, &work, &result,
        VM_RUNTIME_OVERLAY_BATCH_L65M, repeat_phase);
    tamper_application = 0;
    active_ops = 0;
    if (status != VM_RUNTIME_OVERLAY_ERR_CRC || app_calls != 1 || unexpected_loads) {
        fprintf(stderr, "l65m-transport-ops-selftest: egress CRC not observed "
                        "status=%u calls=%u unexpected-loads=%u\n",
                (unsigned)status, app_calls, unexpected_loads);
        return 1;
    }
    vm_runtime_overlay_host_reset();
    for (fixture_index = 0; fixture_index < l65m_bulkread_case_count;
         fixture_index++) {
        const l65m_bulkread_case *test = &l65m_bulkread_cases[fixture_index];
        file_source fixture = { test->data, test->length, 0, 0, 0 };
        l65m_source fixture_source = { read_file, &fixture, test->length };
        l65m_limits fixture_limits;
        l65m_plan fixture_plan;
        l65m_overlay_work fixture_work;
        l65m_status verdict = L65M_OK;
        unsigned fixture_phase;
        memset(&fixture_limits, 0, sizeof fixture_limits);
        fixture_limits.dir_capacity = 4095;
        fixture_limits.symbol_capacity = 65535;
        fixture_limits.namepool_capacity = 65535;
        fixture_limits.heap_free = 65535;
        fixture_limits.arena_capacity = 65535;
        fixture_limits.roots_capacity = 255;
        fixture_limits.string_arena = 1;
        fixture_limits.symbol_exists = no_symbol_exists;
        l65m_overlay_work_init(
            &fixture_work, &fixture_source, 0, &fixture_limits, &fixture_plan);
        for (fixture_phase = 0; fixture_phase < L65M_OVERLAY_PHASE_COUNT;
             fixture_phase++) {
            do {
                verdict = (l65m_status)phase_functions[fixture_phase](&fixture_work);
                if (verdict != L65M_OK) break;
            } while (fixture_work.expected_phase == fixture_phase);
            if (verdict != L65M_OK) break;
        }
        if (verdict != test->expected_status) {
            fprintf(stderr,
                    "l65m-transport-ops-selftest: oracle verdict mismatch "
                    "case=%s expected=%u actual=%u\n",
                    test->name, (unsigned)test->expected_status, (unsigned)verdict);
            return 1;
        }
        if (verdict == L65M_OK
            && fixture_plan.new_symbols != test->expected_new_symbols) {
            fprintf(stderr,
                    "l65m-transport-ops-selftest: symbol-union mismatch "
                    "case=%s expected=%u actual=%u\n",
                    test->name, (unsigned)test->expected_new_symbols,
                    (unsigned)fixture_plan.new_symbols);
            return 1;
        }
        if (verdict == L65M_OK
            && fixture_plan.patch_count != test->expected_patches) {
            fprintf(stderr,
                    "l65m-transport-ops-selftest: patch-count mismatch "
                    "case=%s expected=%u actual=%u\n",
                    test->name, (unsigned)test->expected_patches,
                    (unsigned)fixture_plan.patch_count);
            return 1;
        }
    }
    printf("l65m-transport-ops-selftest: PASS "
           "reload+egress-count+live-CRC+oracle-fixtures=%u\n",
           (unsigned)l65m_bulkread_case_count);
    return 0;
}

static int run_report(const char *image_path, const char *integration_path,
                      const char *scratch_source_path, const char *out_path,
                      int check) {
    file_source bytes = { 0 };
    l65m_source source;
    l65m_limits limits;
    l65m_plan plan;
    l65m_overlay_work work;
    phase_ops ops[L65M_OVERLAY_PHASE_COUNT];
    phase_ops total;
    FILE *out = stdout;
    uint32_t before_reads;
    uint32_t before_read_bytes, before_dma_calls;
    unsigned phase, violations = 0;
    uint8_t result;
    vm_runtime_overlay_status transport;
    integration_audit audit;
    scratch_source_audit scratch_audit;

    memset(&total, 0, sizeof total);
    if (!integration_path) {
        fprintf(stderr, "l65m-transport-ops: --integration is required\n");
        return 2;
    }
    if (!scratch_source_path) {
        fprintf(stderr, "l65m-transport-ops: --scratch-source is required\n");
        return 2;
    }
    violations += audit_integration_file(integration_path, &audit, stderr);
    violations += audit_scratch_source_file(scratch_source_path, &scratch_audit, stderr);
    if (!load_image(image_path, &bytes)) return 1;
    make_catalog();
    source.read = read_file; source.ctx = &bytes; source.length = bytes.length;
    memset(&limits, 0, sizeof limits);
    limits.dir_capacity = 4095; limits.symbol_capacity = 65535;
    limits.namepool_capacity = 65535; limits.heap_free = 65535;
    limits.arena_capacity = 65535; limits.roots_capacity = 255;
    limits.string_arena = 1; limits.symbol_exists = no_symbol_exists;
    l65m_overlay_work_init(&work, &source, 0, &limits, &plan);
    vm_runtime_overlay_host_reset();
    vm_runtime_overlay_host_assume_island_ready();

    for (phase = 0; phase < L65M_OVERLAY_PHASE_COUNT; phase++) {
        phase_ops *current = &ops[phase];
        memset(current, 0, sizeof *current);
        active_phase = phase; active_ops = current;
        app_calls = unexpected_loads = 0;
        before_reads = bytes.reads;
        before_read_bytes = bytes.read_bytes;
        before_dma_calls = bytes.dma_calls;
        result = LISP65_RUNTIME_OVERLAY_ENTRY_NOT_RUN;
        transport = vm_runtime_overlay_exec_batch(
            (uint8_t)(LISP65_RUNTIME_OVERLAY_APPLICATION_SLOT_BASE + phase),
            &work, &result, VM_RUNTIME_OVERLAY_BATCH_L65M, repeat_phase);
        current->iterations = app_calls;
        current->source_reads = bytes.reads - before_reads;
        current->source_read_bytes = bytes.read_bytes - before_read_bytes;
        current->scratch_dma_calls_contracted = bytes.dma_calls - before_dma_calls;
        /* Project the audited one-DMA adapter contract onto each source callback. */
        current->scratch_dma_calls_projected =
            current->source_reads * scratch_audit.bulk_read_refs;
        current->ingress_crcs = current->catalog_verifier_loads +
                                current->record_verifier_loads +
                                current->application_loads;
        current->egress_crcs = transport == VM_RUNTIME_OVERLAY_OK ? 1u : 0u;
        current->catalog_metadata_crcs = CATALOG_METADATA_CRCS;
        active_ops = 0;
        if (transport != VM_RUNTIME_OVERLAY_OK || result != L65M_OK ||
            work.transport_status != L65M_OV_TRANSPORT_OK || unexpected_loads) {
            fprintf(stderr, "l65m-transport-ops: phase %u (%s) failed transport=%u "
                            "result=%u l65m-transport=%u iterations=%u "
                            "unexpected-loads=%u\n",
                    phase, phase_names[phase], (unsigned)transport, (unsigned)result,
                    (unsigned)work.transport_status, app_calls, unexpected_loads);
            free((void *)bytes.data);
            return 1;
        }
        violations += check_phase(phase, current, stderr);
#define ADD(field) total.field += current->field
        ADD(iterations); ADD(source_reads); ADD(source_read_bytes);
        ADD(scratch_dma_calls_contracted); ADD(scratch_dma_calls_projected);
        ADD(catalog_verifier_loads);
        ADD(catalog_header_loads); ADD(catalog_directory_loads);
        ADD(record_verifier_loads); ADD(record_data_loads); ADD(application_loads);
        ADD(ingress_crcs); ADD(egress_crcs); ADD(catalog_metadata_crcs);
#undef ADD
    }
    if (!work.finished || work.expected_phase != L65M_OVERLAY_PHASE_COUNT) {
        fprintf(stderr, "l65m-transport-ops: validator did not finish\n");
        free((void *)bytes.data);
        return 1;
    }
    violations += check_total(&total, stderr);

    if (out_path && !(out = fopen(out_path, "w"))) {
        fprintf(stderr, "l65m-transport-ops: cannot write %s: %s\n", out_path,
                strerror(errno));
        free((void *)bytes.data);
        return 1;
    }
    fprintf(out, "schema=lisp65-l65m-transport-ops-v2\nartifact=%s\nartifact_bytes=%u\n",
            image_path, bytes.length);
    fprintf(out, "entry_count=%u\nindex_count=%u\nnode_count=%u\npatch_count=%u\n",
            plan.entry_count, plan.index_count, plan.node_count, plan.patch_count);
    fprintf(out, "source_length=%u\nsource_crc16=%04x\nsource_blob_off=%u\n"
                 "source_metadata_off=%u\nblob_len=%u\nmetadata_len=%u\n",
            plan.source_length, plan.source_crc16, plan.source_blob_off,
            plan.source_metadata_off, plan.blob_len, plan.metadata_len);
    fprintf(out, "entries_off=%u\nindex_off=%u\nnodes_off=%u\npatches_off=%u\n"
                 "strings_off=%u\nstrings_bytes=%u\n",
            plan.entries_off, plan.index_off, plan.nodes_off, plan.patches_off,
            plan.strings_off, plan.strings_bytes);
    fprintf(out, "new_symbols=%u\nnew_name_bytes=%u\nheap_cells=%u\n"
                 "arena_bytes=%u\nroot_slots=%u\nmax_graph_depth=%u\n"
                 "format_version=%u\n",
            plan.new_symbols, plan.new_name_bytes, plan.heap_cells,
            plan.arena_bytes, plan.root_slots, plan.max_graph_depth,
            plan.format_version);
    fprintf(out, "runtime_catalog_slots=%u\nsemantics=repeat-batch-ingress-and-egress-crc\n",
            test_slot_count);
    fprintf(out, "integration_source=%s\nintegration_batch_calls=%u\n",
            integration_path, audit.batch_calls);
    fprintf(out, "integration_single_exec_calls=%u\nintegration_l65m_policy_refs=%u\n",
            audit.single_calls, audit.batch_policy_refs);
    fprintf(out, "integration_repeat_predicate_refs=%u\nintegration_phase_loops=%u\n",
            audit.repeat_predicate_refs, audit.phase_loops);
    fprintf(out, "integration_inner_do_loops=%u\n", audit.do_loops);
    fprintf(out, "scratch_source=%s\nscratch_source_bulk_read_refs=%u\n"
                 "scratch_source_byte_get_refs=%u\n"
                 "bulkread_oracle_fixture_cases=%u\n",
            scratch_source_path, scratch_audit.bulk_read_refs,
            scratch_audit.byte_get_refs, (unsigned)l65m_bulkread_case_count);
    for (phase = 0; phase < L65M_OVERLAY_PHASE_COUNT; phase++) {
        const phase_ops *current = &ops[phase];
        fprintf(out, "phase=%02u name=%s logical_iterations=%lu source_read_calls=%lu "
                     "source_read_bytes=%lu scratch_dma_calls_contracted=%lu "
                     "scratch_dma_calls_projected=%lu scratch_dma_budget=%lu "
                     "catalog_verifier_loads=%lu catalog_header_loads=%lu "
                     "catalog_directory_loads=%lu record_verifier_loads=%lu "
                     "record_data_loads=%lu application_slice_loads=%lu "
                     "ingress_crc_runs=%lu egress_crc_runs=%lu "
                     "catalog_metadata_crc_runs=%lu\n",
                phase, phase_names[phase], (unsigned long)current->iterations,
                (unsigned long)current->source_reads,
                (unsigned long)current->source_read_bytes,
                (unsigned long)current->scratch_dma_calls_contracted,
                (unsigned long)current->scratch_dma_calls_projected,
                (unsigned long)phase_scratch_dma_budget(phase),
                (unsigned long)current->catalog_verifier_loads,
                (unsigned long)current->catalog_header_loads,
                (unsigned long)current->catalog_directory_loads,
                (unsigned long)current->record_verifier_loads,
                (unsigned long)current->record_data_loads,
                (unsigned long)current->application_loads,
                (unsigned long)current->ingress_crcs,
                (unsigned long)current->egress_crcs,
                (unsigned long)current->catalog_metadata_crcs);
    }
    fprintf(out, "total_logical_iterations=%lu\ntotal_source_read_calls=%lu\n"
                 "total_source_read_bytes=%lu\n",
            (unsigned long)total.iterations, (unsigned long)total.source_reads,
            (unsigned long)total.source_read_bytes);
    fprintf(out, "total_scratch_dma_calls_contracted=%lu\n"
                 "total_scratch_dma_calls_projected=%lu\n"
                 "total_scratch_dma_budget=%u\n",
            (unsigned long)total.scratch_dma_calls_contracted,
            (unsigned long)total.scratch_dma_calls_projected,
            (unsigned)SCRATCH_DMA_TOTAL_BUDGET);
    fprintf(out, "total_catalog_verifier_loads=%lu\ntotal_catalog_header_loads=%lu\n",
            (unsigned long)total.catalog_verifier_loads,
            (unsigned long)total.catalog_header_loads);
    fprintf(out, "total_catalog_directory_loads=%lu\ntotal_record_verifier_loads=%lu\n",
            (unsigned long)total.catalog_directory_loads,
            (unsigned long)total.record_verifier_loads);
    fprintf(out, "total_record_data_loads=%lu\ntotal_application_slice_loads=%lu\n",
            (unsigned long)total.record_data_loads,
            (unsigned long)total.application_loads);
    fprintf(out, "total_ingress_crc_runs=%lu\ntotal_egress_crc_runs=%lu\n",
            (unsigned long)total.ingress_crcs, (unsigned long)total.egress_crcs);
    fprintf(out, "total_catalog_metadata_crc_runs=%lu\ntotal_crc_runs=%lu\n",
            (unsigned long)total.catalog_metadata_crcs,
            (unsigned long)(total.ingress_crcs + total.egress_crcs +
                            total.catalog_metadata_crcs));
    fprintf(out, "legacy_application_slice_loads=%lu\nlegacy_crc_runs=%lu\n",
            (unsigned long)total.iterations,
            (unsigned long)(total.iterations *
                            (TRANSPORT_INGRESS_CRCS + CATALOG_METADATA_CRCS)));
    fprintf(out, "violations=%u\ngate=%s\n", violations,
            violations ? "FAIL" : "PASS");
    if (out_path) fclose(out);
    free((void *)bytes.data);
    if (violations && check) return 1;
    printf("l65m-transport-ops: %s phases=%u iterations=%lu app-loads=%lu "
           "crc-runs=%lu report=%s\n",
           violations ? "FAIL" : "PASS", (unsigned)L65M_OVERLAY_PHASE_COUNT,
           (unsigned long)total.iterations, (unsigned long)total.application_loads,
           (unsigned long)(total.ingress_crcs + total.egress_crcs +
                           total.catalog_metadata_crcs),
           out_path ? out_path : "stdout");
    return 0;
}

static void usage(const char *program) {
    fprintf(stderr, "usage: %s --selftest | --image PATH --integration C "
                    "--scratch-source C [--out PATH] [--check]"
#ifdef LISP65_C1_TRUST_FASTPATH_PROBE
                    " | --fastpath-selftest --image PATH"
#endif
                    "\n",
            program);
}

int main(int argc, char **argv) {
    const char *image = 0, *integration = 0, *scratch_source = 0, *out = 0;
    int check = 0, run_selftest = 0, i;
#ifdef LISP65_C1_TRUST_FASTPATH_PROBE
    int run_fastpath_selftest = 0;
#endif
    for (i = 1; i < argc; i++) {
        if (!strcmp(argv[i], "--selftest")) run_selftest = 1;
#ifdef LISP65_C1_TRUST_FASTPATH_PROBE
        else if (!strcmp(argv[i], "--fastpath-selftest"))
            run_fastpath_selftest = 1;
#endif
        else if (!strcmp(argv[i], "--check")) check = 1;
        else if (!strcmp(argv[i], "--image") && i + 1 < argc) image = argv[++i];
        else if (!strcmp(argv[i], "--integration") && i + 1 < argc)
            integration = argv[++i];
        else if (!strcmp(argv[i], "--scratch-source") && i + 1 < argc)
            scratch_source = argv[++i];
        else if (!strcmp(argv[i], "--out") && i + 1 < argc) out = argv[++i];
        else { usage(argv[0]); return 2; }
    }
    if (run_selftest)
        return image || integration || scratch_source || out || check
                   ? (usage(argv[0]), 2) : selftest();
#ifdef LISP65_C1_TRUST_FASTPATH_PROBE
    if (run_fastpath_selftest)
        return !image || integration || scratch_source || out || check
                   ? (usage(argv[0]), 2) : c1_fastpath_selftest(image);
#endif
    if (!image) { usage(argv[0]); return 2; }
    return run_report(image, integration, scratch_source, out, check);
}
