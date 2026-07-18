/* Resident bootstrap and Attic-backed catalog verifier for runtime overlays. */
#include "vm_runtime_overlay.h"
#ifdef LISP65_C1_COMPILER_TIER
#include "c1_compiler_overlay.h"
#endif

#include <stddef.h>
#include <stdint.h>
#include <string.h>

#if defined(LISP65_RUNTIME_OVERLAY) || defined(LISP65_RUNTIME_OVERLAY_HOST_TEST)
#include "vm.h"

#ifdef LISP65_RUNTIME_OVERLAY_HOST_TEST
#define LISP65_RESIDENT_ISLAND_BUILD_ID 0x13579bdfUL
#define LISP65_RESIDENT_ISLAND_ADDRESS LISP65_RUNTIME_ISLAND_ADDRESS
#define LISP65_RESIDENT_ISLAND_CAPACITY LISP65_RUNTIME_ISLAND_CAPACITY
#define LISP65_RESIDENT_ISLAND_LENGTH 4u
#define LISP65_RESIDENT_ISLAND_CRC16 0x5e54u
#define LISP65_RESIDENT_ISLAND_BYTES { 'I', 'S', 'L', 'D' }
#ifndef LISP65_RUNTIME_OVERLAY_FORMAT_BANK_TAG
#define LISP65_RUNTIME_OVERLAY_FORMAT_BANK_TAG      3u
#endif
#ifndef LISP65_RUNTIME_OVERLAY_STORAGE_BASE
#define LISP65_RUNTIME_OVERLAY_STORAGE_BASE         0x08000000UL
#endif
#ifndef LISP65_RUNTIME_OVERLAY_STORAGE_MEGABYTE
#define LISP65_RUNTIME_OVERLAY_STORAGE_MEGABYTE     0x80u
#endif
#ifndef LISP65_RUNTIME_OVERLAY_STORAGE_WINDOW_BYTES
#define LISP65_RUNTIME_OVERLAY_STORAGE_WINDOW_BYTES 0x00010000UL
#endif
#ifndef LISP65_RUNTIME_OVERLAY_CATALOG_OFF
#define LISP65_RUNTIME_OVERLAY_CATALOG_OFF          0u
#endif
#ifndef LISP65_RUNTIME_OVERLAY_PROFILE_BUILD_ID
#define LISP65_RUNTIME_OVERLAY_PROFILE_BUILD_ID     0x13579bdfUL
#endif
#ifndef LISP65_RUNTIME_OVERLAY_MAX_SLICE_BYTES
#define LISP65_RUNTIME_OVERLAY_MAX_SLICE_BYTES      1792u
#endif
#ifndef LISP65_RUNTIME_OVERLAY_BOOT_MAX_SLICE_BYTES
#define LISP65_RUNTIME_OVERLAY_BOOT_MAX_SLICE_BYTES 4096u
#endif
#ifndef LISP65_RUNTIME_OVERLAY_ENTRY_ABI
#define LISP65_RUNTIME_OVERLAY_ENTRY_ABI            LISP65_RUNTIME_OVERLAY_ENTRY_ABI_V1
#endif
#ifndef LISP65_RUNTIME_OVERLAY_CATALOG_VERIFIER_FILE_OFF
#define LISP65_RUNTIME_OVERLAY_CATALOG_VERIFIER_FILE_OFF    0x0500u
#endif
#ifndef LISP65_RUNTIME_OVERLAY_CATALOG_VERIFIER_FILE_SIZE
#define LISP65_RUNTIME_OVERLAY_CATALOG_VERIFIER_FILE_SIZE   8u
#endif
#ifndef LISP65_RUNTIME_OVERLAY_CATALOG_VERIFIER_ENTRY_OFFSET
#define LISP65_RUNTIME_OVERLAY_CATALOG_VERIFIER_ENTRY_OFFSET 0u
#endif
#ifndef LISP65_RUNTIME_OVERLAY_CATALOG_VERIFIER_CRC16
#define LISP65_RUNTIME_OVERLAY_CATALOG_VERIFIER_CRC16       0x37e8u
#endif
#ifndef LISP65_RUNTIME_OVERLAY_RECORD_VERIFIER_FILE_OFF
#define LISP65_RUNTIME_OVERLAY_RECORD_VERIFIER_FILE_OFF     0x0600u
#endif
#ifndef LISP65_RUNTIME_OVERLAY_RECORD_VERIFIER_FILE_SIZE
#define LISP65_RUNTIME_OVERLAY_RECORD_VERIFIER_FILE_SIZE    8u
#endif
#ifndef LISP65_RUNTIME_OVERLAY_RECORD_VERIFIER_ENTRY_OFFSET
#define LISP65_RUNTIME_OVERLAY_RECORD_VERIFIER_ENTRY_OFFSET 0u
#endif
#ifndef LISP65_RUNTIME_OVERLAY_RECORD_VERIFIER_CRC16
#define LISP65_RUNTIME_OVERLAY_RECORD_VERIFIER_CRC16        0x5afbu
#endif
extern uint8_t lisp65_runtime_overlay_host_target[];
extern const uint16_t lisp65_runtime_overlay_host_vma;
extern uint16_t lisp65_runtime_overlay_host_limit;
extern uint16_t lisp65_runtime_overlay_host_soft_sp;
extern uint8_t vm_runtime_overlay_host_call(uint16_t entry, void *context);
#define RTOV_VMA        lisp65_runtime_overlay_host_vma
#define RTOV_LIMIT      lisp65_runtime_overlay_host_limit
#define RTOV_BOOT_LIMIT lisp65_runtime_overlay_host_limit
#define RTOV_SOFT_SP()  lisp65_runtime_overlay_host_soft_sp
#define RTOV_TARGET     lisp65_runtime_overlay_host_target
#define RTOV_CALL(e, c) vm_runtime_overlay_host_call((e), (c))
#else
#ifndef LISP65_RUNTIME_OVERLAY_FORMAT_BANK_TAG
#error "generated LISP65_RUNTIME_OVERLAY_FORMAT_BANK_TAG is required"
#endif
#ifndef LISP65_RESIDENT_ISLAND_BUILD_ID
#error "generated LISP65_RESIDENT_ISLAND_BUILD_ID is required"
#endif
#ifndef LISP65_RESIDENT_ISLAND_ADDRESS
#error "generated LISP65_RESIDENT_ISLAND_ADDRESS is required"
#endif
#ifndef LISP65_RESIDENT_ISLAND_CAPACITY
#error "generated LISP65_RESIDENT_ISLAND_CAPACITY is required"
#endif
#ifndef LISP65_RESIDENT_ISLAND_LENGTH
#error "generated LISP65_RESIDENT_ISLAND_LENGTH is required"
#endif
#ifndef LISP65_RESIDENT_ISLAND_CRC16
#error "generated LISP65_RESIDENT_ISLAND_CRC16 is required"
#endif
#ifndef LISP65_RESIDENT_ISLAND_BYTES
#error "generated LISP65_RESIDENT_ISLAND_BYTES is required"
#endif

#if LISP65_RESIDENT_ISLAND_ADDRESS != LISP65_RUNTIME_ISLAND_ADDRESS || \
    LISP65_RESIDENT_ISLAND_CAPACITY != LISP65_RUNTIME_ISLAND_CAPACITY
#error "resident island must use the pinned $1800-$1fff window"
#endif
#if LISP65_RESIDENT_ISLAND_BUILD_ID != LISP65_RUNTIME_OVERLAY_PROFILE_BUILD_ID
#error "resident island build ID must match the L65R catalog"
#endif
#if LISP65_RESIDENT_ISLAND_LENGTH == 0 || \
    LISP65_RESIDENT_ISLAND_LENGTH > LISP65_RESIDENT_ISLAND_CAPACITY
#error "resident island length is outside its fixed image"
#endif
#if LISP65_RUNTIME_ISLAND_INSTALL_SLOT >= LISP65_RUNTIME_OVERLAY_HARD_MAX_SLICES
#error "resident island installer slot exceeds the L65R catalog"
#endif
#ifndef LISP65_RUNTIME_OVERLAY_STORAGE_BASE
#error "generated LISP65_RUNTIME_OVERLAY_STORAGE_BASE is required"
#endif
#ifndef LISP65_RUNTIME_OVERLAY_STORAGE_MEGABYTE
#error "generated LISP65_RUNTIME_OVERLAY_STORAGE_MEGABYTE is required"
#endif
#ifndef LISP65_RUNTIME_OVERLAY_STORAGE_WINDOW_BYTES
#error "generated LISP65_RUNTIME_OVERLAY_STORAGE_WINDOW_BYTES is required"
#endif
#ifndef LISP65_RUNTIME_OVERLAY_CATALOG_OFF
#error "generated LISP65_RUNTIME_OVERLAY_CATALOG_OFF is required"
#endif
#ifndef LISP65_RUNTIME_OVERLAY_PROFILE_BUILD_ID
#error "generated LISP65_RUNTIME_OVERLAY_PROFILE_BUILD_ID is required"
#endif
#ifndef LISP65_RUNTIME_OVERLAY_MAX_SLICE_BYTES
#error "generated LISP65_RUNTIME_OVERLAY_MAX_SLICE_BYTES is required"
#endif
#ifndef LISP65_RUNTIME_OVERLAY_BOOT_MAX_SLICE_BYTES
#error "generated LISP65_RUNTIME_OVERLAY_BOOT_MAX_SLICE_BYTES is required"
#endif
#ifndef LISP65_RUNTIME_OVERLAY_ENTRY_ABI
#error "generated LISP65_RUNTIME_OVERLAY_ENTRY_ABI is required"
#endif
#ifndef LISP65_RUNTIME_OVERLAY_CATALOG_VERIFIER_FILE_OFF
#error "generated LISP65_RUNTIME_OVERLAY_CATALOG_VERIFIER_FILE_OFF is required"
#endif
#ifndef LISP65_RUNTIME_OVERLAY_CATALOG_VERIFIER_FILE_SIZE
#error "generated LISP65_RUNTIME_OVERLAY_CATALOG_VERIFIER_FILE_SIZE is required"
#endif
#ifndef LISP65_RUNTIME_OVERLAY_CATALOG_VERIFIER_ENTRY_OFFSET
#error "generated LISP65_RUNTIME_OVERLAY_CATALOG_VERIFIER_ENTRY_OFFSET is required"
#endif
#ifndef LISP65_RUNTIME_OVERLAY_CATALOG_VERIFIER_CRC16
#error "generated LISP65_RUNTIME_OVERLAY_CATALOG_VERIFIER_CRC16 is required"
#endif
#ifndef LISP65_RUNTIME_OVERLAY_RECORD_VERIFIER_FILE_OFF
#error "generated LISP65_RUNTIME_OVERLAY_RECORD_VERIFIER_FILE_OFF is required"
#endif
#ifndef LISP65_RUNTIME_OVERLAY_RECORD_VERIFIER_FILE_SIZE
#error "generated LISP65_RUNTIME_OVERLAY_RECORD_VERIFIER_FILE_SIZE is required"
#endif
#ifndef LISP65_RUNTIME_OVERLAY_RECORD_VERIFIER_ENTRY_OFFSET
#error "generated LISP65_RUNTIME_OVERLAY_RECORD_VERIFIER_ENTRY_OFFSET is required"
#endif
#ifndef LISP65_RUNTIME_OVERLAY_RECORD_VERIFIER_CRC16
#error "generated LISP65_RUNTIME_OVERLAY_RECORD_VERIFIER_CRC16 is required"
#endif
extern uint8_t __lisp65_workbench_runtime_overlay_vma[];
extern uint8_t __lisp65_workbench_runtime_overlay_limit[];
extern uint8_t __lisp65_workbench_boot_slice_limit[];
#define RTOV_VMA        ((uint16_t)(uintptr_t)__lisp65_workbench_runtime_overlay_vma)
#define RTOV_LIMIT      ((uint16_t)(uintptr_t)__lisp65_workbench_runtime_overlay_limit)
#define RTOV_BOOT_LIMIT ((uint16_t)(uintptr_t)__lisp65_workbench_boot_slice_limit)
#define RTOV_SOFT_SP()  (*(volatile uint16_t *)0x0002u)
#define RTOV_TARGET     __lisp65_workbench_runtime_overlay_vma
#define RTOV_CALL(e, c) (((vm_runtime_overlay_entry_fn)(uintptr_t)(e))((c)))
#endif

#if LISP65_RUNTIME_OVERLAY_FORMAT_BANK_TAG != 3
#error "L65R-v1 format bank tag is frozen at 3"
#endif
#if LISP65_RUNTIME_OVERLAY_STORAGE_BASE != 0x08000000UL || \
    LISP65_RUNTIME_OVERLAY_STORAGE_MEGABYTE != 0x80u || \
    LISP65_RUNTIME_OVERLAY_STORAGE_WINDOW_BYTES != 0x00010000UL
#error "runtime-overlay storage must be the pinned 64-KB Attic window"
#endif
#if LISP65_RUNTIME_OVERLAY_CATALOG_OFF != 0
#error "runtime-overlay Attic catalog is pinned to offset zero"
#endif
#if LISP65_RUNTIME_OVERLAY_MAX_SLICE_BYTES == 0 || \
    LISP65_RUNTIME_OVERLAY_MAX_SLICE_BYTES > LISP65_RUNTIME_OVERLAY_HARD_MAX_SLICE
#error "runtime-overlay slice limit must be in 1..1792"
#endif
#if LISP65_RUNTIME_OVERLAY_BOOT_MAX_SLICE_BYTES == 0 || \
    LISP65_RUNTIME_OVERLAY_BOOT_MAX_SLICE_BYTES > LISP65_RUNTIME_OVERLAY_HARD_MAX_BOOT_SLICE
#error "boot-overlay slice limit must be in 1..4096"
#endif
#if LISP65_RUNTIME_OVERLAY_ENTRY_ABI != LISP65_RUNTIME_OVERLAY_ENTRY_ABI_V1
#error "runtime-overlay entry ABI must be version 1"
#endif
#if LISP65_RUNTIME_OVERLAY_CATALOG_VERIFIER_FILE_SIZE == 0 || \
    LISP65_RUNTIME_OVERLAY_CATALOG_VERIFIER_FILE_SIZE > LISP65_RUNTIME_OVERLAY_HARD_MAX_SLICE || \
    LISP65_RUNTIME_OVERLAY_RECORD_VERIFIER_FILE_SIZE == 0 || \
    LISP65_RUNTIME_OVERLAY_RECORD_VERIFIER_FILE_SIZE > LISP65_RUNTIME_OVERLAY_HARD_MAX_SLICE
#error "runtime-overlay verifier length is outside the execution window"
#endif
#if LISP65_RUNTIME_OVERLAY_CATALOG_VERIFIER_ENTRY_OFFSET >= LISP65_RUNTIME_OVERLAY_CATALOG_VERIFIER_FILE_SIZE || \
    LISP65_RUNTIME_OVERLAY_RECORD_VERIFIER_ENTRY_OFFSET >= LISP65_RUNTIME_OVERLAY_RECORD_VERIFIER_FILE_SIZE
#error "runtime-overlay verifier entry lies outside its payload"
#endif
#if (LISP65_RUNTIME_OVERLAY_CATALOG_VERIFIER_FILE_OFF & 255u) || \
    (LISP65_RUNTIME_OVERLAY_RECORD_VERIFIER_FILE_OFF & 255u)
#error "runtime-overlay verifier payload is not 256-byte aligned"
#endif
#if LISP65_RUNTIME_OVERLAY_CATALOG_VERIFIER_FILE_OFF > \
        (0x10000UL - LISP65_RUNTIME_OVERLAY_CATALOG_VERIFIER_FILE_SIZE) || \
    LISP65_RUNTIME_OVERLAY_RECORD_VERIFIER_FILE_OFF > \
        (0x10000UL - LISP65_RUNTIME_OVERLAY_RECORD_VERIFIER_FILE_SIZE)
#error "runtime-overlay verifier payload exceeds the L65R-v1 storage window"
#endif

#if defined(__GNUC__) || defined(__clang__)
#define RTOV_CATALOGFN __attribute__((noinline, used, section(".lisp65_rt_rtov_catalog")))
#define RTOV_RECORDFN  __attribute__((noinline, used, section(".lisp65_rt_rtov_record")))
#define RTOV_ISLANDFN  __attribute__((noinline, used, section(".lisp65_rt_island_00")))
#define RTOV_ISLANDDATA __attribute__((used, section(".lisp65_rt_island_00_data")))
#define RTOV_NOINLINE  __attribute__((noinline))
#else
#define RTOV_CATALOGFN
#define RTOV_RECORDFN
#define RTOV_ISLANDFN
#define RTOV_ISLANDDATA
#define RTOV_NOINLINE
#endif

#ifdef LISP65_RUNTIME_OVERLAY_HOST_TEST
extern uint8_t lisp65_resident_island_host_target[
    LISP65_RUNTIME_ISLAND_CAPACITY];
static uint8_t rtov_island_copy_fault;
#define RTOV_ISLAND_TARGET lisp65_resident_island_host_target
#else
extern uint8_t __lisp65_resident_island_start[];
extern uint8_t __lisp65_resident_island_end[];
#define RTOV_ISLAND_TARGET __lisp65_resident_island_start
#endif

typedef void (*rtov_read_fn)(uint16_t relative, uint8_t *dst, uint16_t length);

typedef struct {
    rtov_read_fn read;
    uint16_t file_off;
    uint16_t file_len;
    uint16_t entry_off;
    uint16_t payload_crc;
    uint16_t payload_off;
    uint16_t image_limit;
    uint16_t flags;
    uint8_t slot;
    uint8_t buffer[LISP65_RUNTIME_OVERLAY_ENTRY_SIZE];
} rtov_verify_context;

typedef struct {
    uint16_t file_off;
    uint16_t file_len;
    uint16_t entry_off;
    uint16_t crc;
} rtov_verifier_tuple;

typedef struct {
    uint8_t status;
} rtov_island_install_context;

enum {
    RTOV_ISLAND_UNINSTALLED = 0,
    RTOV_ISLAND_INSTALLING,
    RTOV_ISLAND_READY,
    RTOV_ISLAND_FAILED
};

RTOV_ISLANDDATA static const uint8_t
rtov_island_image[LISP65_RESIDENT_ISLAND_LENGTH] =
    LISP65_RESIDENT_ISLAND_BYTES;

/* Volatile prevents prepare sentinels and final bindings changing code shape. */
static const volatile rtov_verifier_tuple
rtov_verifiers[LISP65_RUNTIME_OVERLAY_APPLICATION_SLOT_BASE] = {
    {
        LISP65_RUNTIME_OVERLAY_CATALOG_VERIFIER_FILE_OFF,
        LISP65_RUNTIME_OVERLAY_CATALOG_VERIFIER_FILE_SIZE,
        LISP65_RUNTIME_OVERLAY_CATALOG_VERIFIER_ENTRY_OFFSET,
        LISP65_RUNTIME_OVERLAY_CATALOG_VERIFIER_CRC16
    },
    {
        LISP65_RUNTIME_OVERLAY_RECORD_VERIFIER_FILE_OFF,
        LISP65_RUNTIME_OVERLAY_RECORD_VERIFIER_FILE_SIZE,
        LISP65_RUNTIME_OVERLAY_RECORD_VERIFIER_ENTRY_OFFSET,
        LISP65_RUNTIME_OVERLAY_RECORD_VERIFIER_CRC16
    }
};

/* Only the bytes needed to clean the shared execution window survive calls. */
static uint16_t rtov_loaded_len;
static uint8_t rtov_fault;
static uint8_t rtov_busy;
static vm_runtime_overlay_repeat_predicate_fn rtov_repeat;
/* The installer and the resident batch loop cannot run concurrently: the
 * installer completes before the island becomes ready, while batches require
 * the ready state. Keep their context and result/target in these named slots;
 * installer-only volatile accesses below prevent anonymous cross-call spills
 * without changing the resident batch-loop code shape. */
static void *rtov_call_context;
static uint8_t *rtov_call_result;
#define RTOV_INSTALL_CONTEXT (*(void * volatile *)&rtov_call_context)
#define RTOV_INSTALL_TARGET (*(uint8_t * volatile *)&rtov_call_result)
static uint16_t rtov_batch_entry;
static uint16_t rtov_batch_crc;
static uint8_t rtov_batch_slot_id;
static uint8_t rtov_island_state;

#ifndef LISP65_RUNTIME_OVERLAY_HOST_TEST
/* Enhanced-DMA options plus one F018B copy descriptor. The high source byte is
 * fixed by the generated Attic binding; each read only patches 16-bit offsets. */
__attribute__((used)) static uint8_t rtov_edma_job[20] = {
    0x0b, 0x80, LISP65_RUNTIME_OVERLAY_STORAGE_MEGABYTE,
    0x81, 0x00, 0x85, 0x01, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00,
    (uint8_t)((LISP65_RUNTIME_OVERLAY_STORAGE_BASE >> 16) & 0x0fu),
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00
};
#endif

static uint16_t rtov_crc_byte(uint16_t crc, uint8_t value) {
    uint8_t bits = 8;
    crc ^= (uint16_t)value << 8;
    do {
        crc = (crc & 0x8000u)
                ? (uint16_t)((crc << 1) ^ LISP65_RUNTIME_OVERLAY_CRC16_POLY)
                : (uint16_t)(crc << 1);
    } while (--bits);
    return crc;
}

static RTOV_NOINLINE uint16_t rtov_crc_mem(
    const uint8_t *p, uint16_t length) {
    uint16_t crc = LISP65_RUNTIME_OVERLAY_CRC16_INIT;
    while (length--) crc = rtov_crc_byte(crc, *p++);
    return crc;
}

RTOV_ISLANDFN uint8_t vm_resident_island_install(void *opaque) {
    uint8_t status;
    if (!opaque) return VM_RUNTIME_ISLAND_ERR_CONTEXT;
    RTOV_INSTALL_CONTEXT = opaque;
    RTOV_INSTALL_TARGET = (uint8_t *)RTOV_ISLAND_TARGET;
    /* Profile/build identity, entry ABI, source bounds, and source CRC are
     * already checked by vm_runtime_overlay_exec before this boot-only entry.
     * The installer owns only the destination copy and its independent CRC. */
    memcpy(RTOV_INSTALL_TARGET, rtov_island_image,
           LISP65_RESIDENT_ISLAND_LENGTH);
#ifdef LISP65_RUNTIME_OVERLAY_HOST_TEST
    if (rtov_island_copy_fault) RTOV_INSTALL_TARGET[0] ^= 1u;
#endif
    status = rtov_crc_mem(RTOV_INSTALL_TARGET,
                          LISP65_RESIDENT_ISLAND_LENGTH) ==
                     LISP65_RESIDENT_ISLAND_CRC16
                 ? VM_RUNTIME_ISLAND_OK
                 : VM_RUNTIME_ISLAND_ERR_CRC;
    opaque = RTOV_INSTALL_CONTEXT;
    ((rtov_island_install_context *)opaque)->status = status;
    return status;
}

static void rtov_read(uint16_t relative, uint8_t *dst, uint16_t length) {
#ifdef LISP65_RUNTIME_OVERLAY_HOST_TEST
    vm_code_load((uint8_t)LISP65_RUNTIME_OVERLAY_FORMAT_BANK_TAG,
                 (uint16_t)(LISP65_RUNTIME_OVERLAY_CATALOG_OFF + relative),
                 length, dst);
#else
    uint16_t target = (uint16_t)(uintptr_t)dst;
    relative = (uint16_t)(LISP65_RUNTIME_OVERLAY_CATALOG_OFF + relative);
    rtov_edma_job[9] = (uint8_t)length;
    rtov_edma_job[10] = (uint8_t)(length >> 8);
    rtov_edma_job[11] = (uint8_t)relative;
    rtov_edma_job[12] = (uint8_t)(relative >> 8);
    rtov_edma_job[14] = (uint8_t)target;
    rtov_edma_job[15] = (uint8_t)(target >> 8);
    __asm__ volatile(
        "lda #1\n\t"
        "sta $d703\n\t"
        "lda #0\n\t"
        "sta $d702\n\t"
        "sta $d704\n\t"
        "lda #mos16hi(rtov_edma_job)\n\t"
        "sta $d701\n\t"
        "lda #mos16lo(rtov_edma_job)\n\t"
        "sta $d705\n\t"
        ::: "a", "memory");
#endif
}

static uint8_t rtov_wipe(void) {
    volatile uint8_t *target = (volatile uint8_t *)RTOV_TARGET;
    uint16_t i, length = rtov_loaded_len;
    memset((void *)target, 0, length);
    for (i = 0; i < length; i++) if (target[i]) return 0;
    rtov_loaded_len = 0;
    return 1;
}

static vm_runtime_overlay_status rtov_fail(vm_runtime_overlay_status status) {
    rtov_fault = (uint8_t)status;
    if (!rtov_wipe()) rtov_fault = VM_RUNTIME_OVERLAY_ERR_WIPE;
    rtov_busy = 0;
    return (vm_runtime_overlay_status)rtov_fault;
}

static RTOV_CATALOGFN uint16_t rtov_c_u16(const uint8_t *p) {
    return (uint16_t)(p[0] | ((uint16_t)p[1] << 8));
}

static RTOV_CATALOGFN uint8_t rtov_c_build_id(const uint8_t *p) {
    return p[0] == (uint8_t)LISP65_RUNTIME_OVERLAY_PROFILE_BUILD_ID &&
           p[1] == (uint8_t)(LISP65_RUNTIME_OVERLAY_PROFILE_BUILD_ID >> 8) &&
           p[2] == (uint8_t)(LISP65_RUNTIME_OVERLAY_PROFILE_BUILD_ID >> 16) &&
           p[3] == (uint8_t)(LISP65_RUNTIME_OVERLAY_PROFILE_BUILD_ID >> 24);
}

static RTOV_CATALOGFN uint16_t rtov_c_crc_byte(uint16_t crc, uint8_t value) {
    uint8_t bits = 8;
    crc ^= (uint16_t)value << 8;
    do {
        crc = (crc & 0x8000u)
                ? (uint16_t)((crc << 1) ^ LISP65_RUNTIME_OVERLAY_CRC16_POLY)
                : (uint16_t)(crc << 1);
    } while (--bits);
    return crc;
}

static RTOV_CATALOGFN uint16_t rtov_c_crc_ext(
    rtov_verify_context *context, uint16_t relative, uint16_t length) {
    uint16_t crc = LISP65_RUNTIME_OVERLAY_CRC16_INIT;
    while (length) {
        uint8_t i, chunk = length > sizeof context->buffer
                                ? sizeof context->buffer : (uint8_t)length;
        context->read(relative, context->buffer, chunk);
        i = 0;
        do crc = rtov_c_crc_byte(crc, context->buffer[i]); while (++i != chunk);
        relative = (uint16_t)(relative + chunk);
        length = (uint16_t)(length - chunk);
    }
    return crc;
}

/* Integrity-checked by resident CRC before execution; Attic is a bound preload. */
RTOV_CATALOGFN uint8_t vm_runtime_overlay_catalog_verifier(void *opaque) {
    rtov_verify_context *context = (rtov_verify_context *)opaque;
    uint8_t *record = context->buffer;
    uint16_t directory_crc, end;
    uint8_t count, image_full;

    context->read(0, record, sizeof context->buffer);
    if (record[0] != LISP65_RUNTIME_OVERLAY_MAGIC_0 ||
        record[1] != LISP65_RUNTIME_OVERLAY_MAGIC_1 ||
        record[2] != LISP65_RUNTIME_OVERLAY_MAGIC_2 ||
        record[3] != LISP65_RUNTIME_OVERLAY_MAGIC_3)
        return VM_RUNTIME_OVERLAY_ERR_MAGIC;
    if (record[4] != LISP65_RUNTIME_OVERLAY_FORMAT_VERSION)
        return VM_RUNTIME_OVERLAY_ERR_VERSION;
    directory_crc = rtov_c_u16(record + 26);
    record[26] = record[27] = 0;
    if (rtov_crc_mem(record, sizeof context->buffer) != directory_crc)
        return VM_RUNTIME_OVERLAY_ERR_CRC;

    count = record[7];
    if (record[5] != LISP65_RUNTIME_OVERLAY_HEADER_SIZE ||
        record[6] != LISP65_RUNTIME_OVERLAY_ENTRY_SIZE ||
        !count || count > LISP65_RUNTIME_OVERLAY_HARD_MAX_SLICES ||
        record[8] || record[9] ||
        record[10] != LISP65_RUNTIME_OVERLAY_FORMAT_BANK_TAG || record[11] ||
        rtov_c_u16(record + 16) != LISP65_RUNTIME_OVERLAY_HEADER_SIZE ||
        record[28] || record[29] || record[30] || record[31])
        return VM_RUNTIME_OVERLAY_ERR_HEADER;
    if (!rtov_c_build_id(record + 12)) return VM_RUNTIME_OVERLAY_ERR_PROFILE;
    if (context->slot < LISP65_RUNTIME_OVERLAY_APPLICATION_SLOT_BASE ||
        context->slot >= count)
        return VM_RUNTIME_OVERLAY_ERR_SLOT;

    context->payload_off = rtov_c_u16(record + 18);
    end = (uint16_t)(LISP65_RUNTIME_OVERLAY_HEADER_SIZE +
                     (uint16_t)count * LISP65_RUNTIME_OVERLAY_ENTRY_SIZE);
    end = (uint16_t)((end + 255u) & 0xff00u);
    if (context->payload_off != end) return VM_RUNTIME_OVERLAY_ERR_DIRECTORY;
    context->image_limit = rtov_c_u16(record + 20);
    image_full = record[22] == 1 && !record[23] && !context->image_limit;
    if (!image_full && (record[22] || record[23] ||
                        context->image_limit < context->payload_off))
        return VM_RUNTIME_OVERLAY_ERR_LENGTH;
    directory_crc = rtov_c_u16(record + 24);
    if (rtov_c_crc_ext(context, LISP65_RUNTIME_OVERLAY_HEADER_SIZE,
                       (uint16_t)count * LISP65_RUNTIME_OVERLAY_ENTRY_SIZE) !=
        directory_crc)
        return VM_RUNTIME_OVERLAY_ERR_CRC;
    return VM_RUNTIME_OVERLAY_OK;
}

static RTOV_RECORDFN uint16_t rtov_r_u16(const uint8_t *p) {
    return (uint16_t)(p[0] | ((uint16_t)p[1] << 8));
}

static RTOV_RECORDFN uint8_t rtov_r_build_id(const uint8_t *p) {
    return p[0] == (uint8_t)LISP65_RUNTIME_OVERLAY_PROFILE_BUILD_ID &&
           p[1] == (uint8_t)(LISP65_RUNTIME_OVERLAY_PROFILE_BUILD_ID >> 8) &&
           p[2] == (uint8_t)(LISP65_RUNTIME_OVERLAY_PROFILE_BUILD_ID >> 16) &&
           p[3] == (uint8_t)(LISP65_RUNTIME_OVERLAY_PROFILE_BUILD_ID >> 24);
}

/* Called only after slot 0 integrity-checked the immutable header and directory. */
RTOV_RECORDFN uint8_t vm_runtime_overlay_record_verifier(void *opaque) {
    rtov_verify_context *context = (rtov_verify_context *)opaque;
    uint8_t *record = context->buffer;
    uint16_t end, execution_limit, size_limit;

    context->read((uint16_t)(LISP65_RUNTIME_OVERLAY_HEADER_SIZE +
                             (uint16_t)context->slot *
                             LISP65_RUNTIME_OVERLAY_ENTRY_SIZE),
                  record, sizeof context->buffer);
    context->flags = rtov_r_u16(record + 2);
    if (rtov_r_u16(record) != context->slot ||
        (context->flags != LISP65_RUNTIME_OVERLAY_FLAG_BOOT &&
         context->flags != (LISP65_RUNTIME_OVERLAY_FLAG_RUNTIME |
                            LISP65_RUNTIME_OVERLAY_FLAG_REUSABLE)) ||
        record[24] || record[25] || record[26] || record[27] ||
        record[28] || record[29] || record[30] || record[31])
        return VM_RUNTIME_OVERLAY_ERR_DIRECTORY;
    if (!rtov_r_build_id(record + 16)) return VM_RUNTIME_OVERLAY_ERR_PROFILE;
    if (rtov_r_u16(record + 8) != RTOV_VMA) return VM_RUNTIME_OVERLAY_ERR_VMA;
    if (rtov_r_u16(record + 14) != LISP65_RUNTIME_OVERLAY_ENTRY_ABI)
        return VM_RUNTIME_OVERLAY_ERR_ABI;

    context->file_off = rtov_r_u16(record + 4);
    context->file_len = rtov_r_u16(record + 6);
    size_limit = context->flags == LISP65_RUNTIME_OVERLAY_FLAG_BOOT
                   ? LISP65_RUNTIME_OVERLAY_BOOT_MAX_SLICE_BYTES
                   : LISP65_RUNTIME_OVERLAY_MAX_SLICE_BYTES;
    if (!context->file_len ||
        context->file_len > size_limit ||
        rtov_r_u16(record + 10) != context->file_len ||
        rtov_r_u16(record + 22) || context->file_off < context->payload_off ||
        (context->file_off & 255u))
        return VM_RUNTIME_OVERLAY_ERR_LENGTH;
    end = (uint16_t)(context->file_off + context->file_len);
    if ((end < context->file_off && end != 0) ||
        (context->image_limit &&
         (end < context->file_off || end > context->image_limit)))
        return VM_RUNTIME_OVERLAY_ERR_LENGTH;

    context->entry_off = rtov_r_u16(record + 12);
    if (context->entry_off >= context->file_len ||
        (uint16_t)(RTOV_VMA + context->entry_off) < RTOV_VMA)
        return VM_RUNTIME_OVERLAY_ERR_ENTRY;
    execution_limit = context->flags == LISP65_RUNTIME_OVERLAY_FLAG_BOOT
                        ? RTOV_BOOT_LIMIT : RTOV_LIMIT;
    if (execution_limit <= RTOV_VMA ||
        context->file_len > (uint16_t)(execution_limit - RTOV_VMA) ||
        RTOV_SOFT_SP() <= execution_limit)
        return VM_RUNTIME_OVERLAY_ERR_STACK;
    context->payload_crc = rtov_r_u16(record + 20);
    return VM_RUNTIME_OVERLAY_OK;
}

/* Keep both generated verifier tuples on one value-independent code path. */
static vm_runtime_overlay_status rtov_run_verifier(
    uint16_t file_off, uint16_t file_len, uint16_t entry_off, uint16_t crc,
    rtov_verify_context *context) {
    vm_runtime_overlay_status status;

    rtov_loaded_len = file_len;
    rtov_read(file_off, (uint8_t *)RTOV_TARGET, file_len);
    if (rtov_crc_mem((const uint8_t *)RTOV_TARGET, file_len) != crc)
        return VM_RUNTIME_OVERLAY_ERR_CRC;
    status = (vm_runtime_overlay_status)RTOV_CALL(
        (uint16_t)(RTOV_VMA + entry_off), context);
    if (!rtov_wipe()) return VM_RUNTIME_OVERLAY_ERR_WIPE;
    return status;
}

static LISP65_RESIDENT_ISLAND_FN
vm_runtime_overlay_status rtov_run_batch(void) {
    uint16_t remaining = 0xffffu;
    do {
        *rtov_call_result = RTOV_CALL(rtov_batch_entry, rtov_call_context);
        if (!rtov_repeat(rtov_call_context, rtov_batch_slot_id,
                         *rtov_call_result))
            break;
    } while (--remaining);
    if (rtov_crc_mem((const uint8_t *)RTOV_TARGET, rtov_loaded_len) !=
        rtov_batch_crc)
        return rtov_fail(VM_RUNTIME_OVERLAY_ERR_CRC);
    if (!remaining) return rtov_fail(VM_RUNTIME_OVERLAY_ERR_BATCH_LIMIT);
    if (!rtov_wipe()) return rtov_fail(VM_RUNTIME_OVERLAY_ERR_WIPE);
    rtov_busy = 0;
    return VM_RUNTIME_OVERLAY_OK;
}

vm_runtime_overlay_status vm_runtime_overlay_exec(
    uint8_t slot, void *context, uint8_t *entry_result) {
    rtov_verify_context verify;
    vm_runtime_overlay_status status;
    const volatile rtov_verifier_tuple *verifier;
    uint16_t entry;
    uint8_t verifier_index;

    if (entry_result) *entry_result = LISP65_RUNTIME_OVERLAY_ENTRY_NOT_RUN;
    if (rtov_busy) return VM_RUNTIME_OVERLAY_ERR_BUSY;
    if (rtov_fault) {
        if (!rtov_wipe()) rtov_fault = VM_RUNTIME_OVERLAY_ERR_WIPE;
        return rtov_fault == VM_RUNTIME_OVERLAY_ERR_WIPE
                ? VM_RUNTIME_OVERLAY_ERR_WIPE : VM_RUNTIME_OVERLAY_ERR_LATCHED;
    }
    if (!entry_result) return rtov_fail(VM_RUNTIME_OVERLAY_ERR_ARGUMENT);
    rtov_busy = 1;
    if (!rtov_wipe()) return rtov_fail(VM_RUNTIME_OVERLAY_ERR_WIPE);
    if (RTOV_VMA > LISP65_RUNTIME_OVERLAY_HARD_MAX_VMA ||
        RTOV_LIMIT <= RTOV_VMA ||
        LISP65_RUNTIME_OVERLAY_MAX_SLICE_BYTES >
            (uint16_t)(RTOV_LIMIT - RTOV_VMA) ||
        RTOV_SOFT_SP() <= RTOV_LIMIT)
        return rtov_fail(VM_RUNTIME_OVERLAY_ERR_STACK);

    verify.read = rtov_read;
    verify.slot = slot;
    verifier_index = 0;
    do {
        verifier = rtov_verifiers + verifier_index;
        status = rtov_run_verifier(verifier->file_off, verifier->file_len,
                                   verifier->entry_off, verifier->crc, &verify);
        if (status != VM_RUNTIME_OVERLAY_OK) return rtov_fail(status);
    } while (++verifier_index != LISP65_RUNTIME_OVERLAY_APPLICATION_SLOT_BASE);

    /* Recheck copy bounds at the resident trust boundary. */
    if (!verify.file_len ||
        verify.file_len > (verify.flags == LISP65_RUNTIME_OVERLAY_FLAG_BOOT
                             ? LISP65_RUNTIME_OVERLAY_BOOT_MAX_SLICE_BYTES
                             : LISP65_RUNTIME_OVERLAY_MAX_SLICE_BYTES) ||
        verify.entry_off >= verify.file_len)
        return rtov_fail(VM_RUNTIME_OVERLAY_ERR_LENGTH);
    entry = (uint16_t)(RTOV_VMA + verify.entry_off);
    if (entry < RTOV_VMA) return rtov_fail(VM_RUNTIME_OVERLAY_ERR_ENTRY);

    rtov_loaded_len = verify.file_len;
    rtov_read(verify.file_off, (uint8_t *)RTOV_TARGET, rtov_loaded_len);
    if (rtov_crc_mem((const uint8_t *)RTOV_TARGET, rtov_loaded_len) !=
        verify.payload_crc)
        return rtov_fail(VM_RUNTIME_OVERLAY_ERR_CRC);
    if (rtov_repeat) {
        rtov_batch_entry = entry;
        rtov_batch_crc = verify.payload_crc;
        return rtov_run_batch();
    }
    *entry_result = RTOV_CALL(entry, context);
    if (!rtov_wipe()) return rtov_fail(VM_RUNTIME_OVERLAY_ERR_WIPE);
    rtov_busy = 0;
    return VM_RUNTIME_OVERLAY_OK;
}

vm_runtime_overlay_status vm_runtime_overlay_exec_batch(
    uint8_t slot, void *context, uint8_t *entry_result,
    vm_runtime_overlay_batch_policy policy,
    vm_runtime_overlay_repeat_predicate_fn repeat) {
    uint8_t whitelisted =
        (uint8_t)((policy == VM_RUNTIME_OVERLAY_BATCH_L65M
                   && slot >= 2u && slot <= 22u)
                  || (policy == VM_RUNTIME_OVERLAY_BATCH_COMMIT
                      && slot >= 23u && slot <= 29u)
                  || (policy == VM_RUNTIME_OVERLAY_BATCH_LCC
                      && slot >= 30u && slot <= 32u));
    if (!repeat || !whitelisted)
        return vm_runtime_overlay_exec(slot, context, entry_result);
    if (!entry_result)
        return vm_runtime_overlay_exec(slot, context, entry_result);
    *entry_result = LISP65_RUNTIME_OVERLAY_ENTRY_NOT_RUN;
    if (rtov_island_state != RTOV_ISLAND_READY)
        return VM_RUNTIME_OVERLAY_ERR_ISLAND_NOT_READY;
    return vm_runtime_overlay_exec_batch_island(
        slot, context, entry_result, repeat);
}

LISP65_RESIDENT_ISLAND_FN
vm_runtime_overlay_status vm_runtime_overlay_exec_batch_island(
    uint8_t slot, void *context, uint8_t *entry_result,
    vm_runtime_overlay_repeat_predicate_fn repeat) {
    vm_runtime_overlay_status status;
    if (rtov_busy) return vm_runtime_overlay_exec(slot, context, entry_result);
    rtov_repeat = repeat;
    rtov_call_context = context;
    rtov_call_result = entry_result;
    rtov_batch_slot_id = slot;
    status = vm_runtime_overlay_exec(slot, context, entry_result);
    rtov_repeat = 0;
    return status;
}

vm_runtime_overlay_status vm_runtime_overlay_install_island(void) {
    rtov_island_install_context context;
    vm_runtime_overlay_status transport;
    uint8_t result = LISP65_RUNTIME_OVERLAY_ENTRY_NOT_RUN;
    if (rtov_island_state == RTOV_ISLAND_READY) return VM_RUNTIME_OVERLAY_OK;
    if (rtov_island_state == RTOV_ISLAND_INSTALLING)
        return VM_RUNTIME_OVERLAY_ERR_BUSY;
    if (rtov_island_state == RTOV_ISLAND_FAILED)
        return VM_RUNTIME_OVERLAY_ERR_ISLAND;
    rtov_island_state = RTOV_ISLAND_INSTALLING;
    context.status = VM_RUNTIME_ISLAND_ERR_CONTEXT;
    transport = vm_runtime_overlay_exec(
        LISP65_RUNTIME_ISLAND_INSTALL_SLOT, &context, &result);
    if (transport != VM_RUNTIME_OVERLAY_OK
        || result != VM_RUNTIME_ISLAND_OK
        || context.status != VM_RUNTIME_ISLAND_OK) {
        rtov_island_state = RTOV_ISLAND_FAILED;
        if (transport == VM_RUNTIME_OVERLAY_OK)
            return rtov_fail(VM_RUNTIME_OVERLAY_ERR_ISLAND);
        rtov_fault = VM_RUNTIME_OVERLAY_ERR_ISLAND;
        rtov_busy = 0;
        return VM_RUNTIME_OVERLAY_ERR_ISLAND;
    }
    rtov_island_state = RTOV_ISLAND_READY;
    return VM_RUNTIME_OVERLAY_OK;
}

uint8_t vm_runtime_overlay_island_ready(void) {
    return rtov_island_state == RTOV_ISLAND_READY;
}

vm_runtime_overlay_status vm_runtime_overlay_abort_cleanup(void) {
#ifndef LISP65_C1_COMPILER_TIER
    uint8_t was_busy = rtov_busy;
#endif
    rtov_repeat = 0;
    if (!rtov_wipe()) {
        rtov_fault = VM_RUNTIME_OVERLAY_ERR_WIPE;
        rtov_busy = 0;
        return VM_RUNTIME_OVERLAY_ERR_WIPE;
    }
    rtov_busy = 0;
#ifdef LISP65_C1_COMPILER_TIER
    /* A longjmp bypasses the Lisp retirement call.  Reuse the generic abort
     * landing and a transport-global byte that is dead outside batch mode;
     * this keeps the cleanup trigger out of both the copied island and a new
     * resident checkpoint. */
    return vm_runtime_overlay_exec(
        LISP65_C1_COMPILER_OVERLAY_SLOT, 0, &rtov_batch_slot_id);
#else
    if (rtov_fault) return VM_RUNTIME_OVERLAY_ERR_LATCHED;
    return was_busy ? VM_RUNTIME_OVERLAY_ERR_ABORTED : VM_RUNTIME_OVERLAY_OK;
#endif
}

uint8_t vm_runtime_overlay_fault_latched(void) {
    return rtov_fault != 0;
}

#ifdef LISP65_RUNTIME_OVERLAY_HOST_TEST
uint8_t vm_runtime_overlay_active(void) {
    return rtov_busy;
}

void vm_runtime_overlay_host_reset(void) {
    (void)rtov_wipe();
    rtov_fault = 0;
    rtov_busy = 0;
    rtov_repeat = 0;
    rtov_island_state = RTOV_ISLAND_UNINSTALLED;
    rtov_island_copy_fault = 0;
    memset(lisp65_resident_island_host_target, 0,
           LISP65_RUNTIME_ISLAND_CAPACITY);
}

void vm_runtime_overlay_host_island_copy_fault(uint8_t enabled) {
    rtov_island_copy_fault = enabled;
}

void vm_runtime_overlay_host_assume_island_ready(void) {
    rtov_island_state = RTOV_ISLAND_READY;
}
#endif
#endif /* LISP65_RUNTIME_OVERLAY || LISP65_RUNTIME_OVERLAY_HOST_TEST */
