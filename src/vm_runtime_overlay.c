/* Resident bootstrap and Attic-backed catalog verifier for runtime overlays. */
#include "vm_runtime_overlay.h"
#include "c2_kernal_layout.h"
#ifdef LISP65_C2_E000_REOPEN
#include "c2_kernal_facade.h"
#endif
#if defined(LISP65_RTOV_CRC_CONVERGENCE) && defined(__mos__)
#include "c2_kernal_runtime.h"
#endif
#ifdef LISP65_C2_LITE_BANK3_STAGING
#include "c2_kernal_facade.h"
#include "c2_kernal_runtime.h"
#include "c2_lite_bank3_stage.h"
#include "c2_product_runtime.h"
#include "c2-stream-decoder.h"
#endif
#ifdef LISP65_C1_COMPILER_TIER
#include "c1_compiler_overlay.h"
#endif

#include <stddef.h>
#include <stdint.h>
#include <string.h>

#if defined(LISP65_RUNTIME_OVERLAY_FORMAT_V2) && \
    (defined(LISP65_RUNTIME_OVERLAY_FORMAT_V3) || \
     defined(LISP65_RUNTIME_OVERLAY_FORMAT_V4))
#error "the C2 product profile permits exactly one L65R decoder"
#endif
#if defined(LISP65_RUNTIME_OVERLAY_FORMAT_V3) && \
    defined(LISP65_RUNTIME_OVERLAY_FORMAT_V4)
#error "the C2 product profile permits exactly one L65R decoder"
#endif
#if defined(LISP65_RUNTIME_OVERLAY_FORMAT_V2) && \
    LISP65_RUNTIME_OVERLAY_FORMAT_VERSION != 2u
#error "the selected product profile requires the strict L65R-v2 decoder"
#endif
#if defined(LISP65_RUNTIME_OVERLAY_FORMAT_V3) && \
    LISP65_RUNTIME_OVERLAY_FORMAT_VERSION != 3u
#error "the C2 product profile requires the strict L65R-v3 decoder"
#endif
#if defined(LISP65_RUNTIME_OVERLAY_FORMAT_V4) && \
    LISP65_RUNTIME_OVERLAY_FORMAT_VERSION != 4u
#error "the C2 product profile requires the strict L65R-v4 decoder"
#endif
#if LISP65_RUNTIME_OVERLAY_FORMAT_VERSION >= 2u && \
    !defined(LISP65_RUNTIME_OVERLAY_LIFETIME_FAMILIES)
#error "L65R DATA_ONLY requires the generation-bound C2 family latch"
#endif

#if defined(LISP65_RUNTIME_OVERLAY) || defined(LISP65_RUNTIME_OVERLAY_HOST_TEST)
#include "vm.h"

#ifdef LISP65_RUNTIME_OVERLAY_HOST_TEST
#define LISP65_RESIDENT_ISLAND_BUILD_ID 0x13579bdfUL
#define LISP65_RESIDENT_ISLAND_ADDRESS LISP65_RUNTIME_ISLAND_ADDRESS
#define LISP65_RESIDENT_ISLAND_CAPACITY LISP65_RUNTIME_ISLAND_CAPACITY
#define LISP65_RESIDENT_ISLAND_LENGTH 4u
#define LISP65_RESIDENT_ISLAND_CRC16 0x5e54u
#define LISP65_RESIDENT_ISLAND_BYTES { 'I', 'S', 'L', 'D' }
#ifndef LISP65_RUNTIME_OVERLAY_CATALOG_VERSION
#define LISP65_RUNTIME_OVERLAY_CATALOG_VERSION 1u
#endif
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
#ifndef LISP65_RUNTIME_OVERLAY_REGION_MAIN
#define LISP65_RUNTIME_OVERLAY_REGION_MAIN          0u
#define LISP65_RUNTIME_OVERLAY_REGION_C2D_OVERFLOW  1u
#define LISP65_RUNTIME_OVERLAY_REGION1_BANK         5u
#define LISP65_RUNTIME_OVERLAY_REGION1_ADDRESS      0xbd00u
#define LISP65_RUNTIME_OVERLAY_REGION1_CAPACITY     2032u
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
#ifdef LISP65_RUNTIME_OVERLAY_LIFETIME_FAMILIES
#ifndef LISP65_RUNTIME_OVERLAY_BOOT_STORAGE_BASE
#define LISP65_RUNTIME_OVERLAY_BOOT_STORAGE_BASE 0x08200000UL
#endif
#ifndef LISP65_RUNTIME_OVERLAY_BOOT_CATALOG_VERIFIER_FILE_OFF
#define LISP65_RUNTIME_OVERLAY_BOOT_CATALOG_VERIFIER_FILE_OFF 0x0200u
#define LISP65_RUNTIME_OVERLAY_BOOT_CATALOG_VERIFIER_FILE_SIZE 8u
#define LISP65_RUNTIME_OVERLAY_BOOT_CATALOG_VERIFIER_ENTRY_OFFSET 0u
#define LISP65_RUNTIME_OVERLAY_BOOT_CATALOG_VERIFIER_CRC16 0x37e8u
#define LISP65_RUNTIME_OVERLAY_BOOT_RECORD_VERIFIER_FILE_OFF 0x0300u
#define LISP65_RUNTIME_OVERLAY_BOOT_RECORD_VERIFIER_FILE_SIZE 8u
#define LISP65_RUNTIME_OVERLAY_BOOT_RECORD_VERIFIER_ENTRY_OFFSET 0u
#define LISP65_RUNTIME_OVERLAY_BOOT_RECORD_VERIFIER_CRC16 0x5afbu
#endif
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
#if LISP65_RUNTIME_OVERLAY_FORMAT_VERSION == 1u
#ifndef LISP65_RESIDENT_ISLAND_BYTES
#error "generated LISP65_RESIDENT_ISLAND_BYTES is required"
#endif
#elif LISP65_RUNTIME_OVERLAY_FORMAT_VERSION != 2u && \
      LISP65_RUNTIME_OVERLAY_FORMAT_VERSION != 3u && \
      LISP65_RUNTIME_OVERLAY_FORMAT_VERSION != 4u
#error "C2 runtime overlay accepts one compile-time L65R version only"
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
#if defined(LISP65_RTOV_ISLAND_SPLIT_PROBE) && \
    LISP65_RUNTIME_ISLAND_FINALIZE_SLOT >= LISP65_RUNTIME_OVERLAY_HARD_MAX_SLICES
#error "resident island finalizer slot exceeds the L65R catalog"
#endif
#if LISP65_RUNTIME_OVERLAY_FORMAT_VERSION >= 2u && \
    LISP65_RUNTIME_ISLAND_CARRIER_SLOT >= LISP65_RUNTIME_OVERLAY_HARD_MAX_SLICES
#error "resident island carrier slot exceeds the L65R catalog"
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
#if LISP65_RUNTIME_OVERLAY_FORMAT_VERSION == 4u
#ifndef LISP65_RUNTIME_OVERLAY_REGION1_CAPACITY
#error "generated L65R-v4 region contract is required"
#endif
#ifndef LISP65_RUNTIME_OVERLAY_REGION1_SOURCE_BASE
#error "generated L65R-v4 region-1 durable source is required"
#endif
#if LISP65_RUNTIME_OVERLAY_REGION_MAIN != 0u || \
    LISP65_RUNTIME_OVERLAY_REGION_C2D_OVERFLOW != 1u || \
    LISP65_RUNTIME_OVERLAY_REGION1_SOURCE_BASE != 0x08300000UL || \
    LISP65_RUNTIME_OVERLAY_REGION1_BANK != 5u || \
    LISP65_RUNTIME_OVERLAY_REGION1_ADDRESS != 0xbd00u || \
    LISP65_RUNTIME_OVERLAY_REGION1_CAPACITY != 2032u
#error "L65R-v4 region-1 geometry differs from the Bank-5 contract"
#endif
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
#ifdef LISP65_RUNTIME_OVERLAY_LIFETIME_FAMILIES
#ifndef LISP65_RUNTIME_OVERLAY_BOOT_STORAGE_BASE
#error "generated LISP65_RUNTIME_OVERLAY_BOOT_STORAGE_BASE is required"
#endif
#ifndef LISP65_RUNTIME_OVERLAY_BOOT_CATALOG_VERIFIER_FILE_OFF
#error "generated boot-family catalog verifier binding is required"
#endif
#ifndef LISP65_RUNTIME_OVERLAY_BOOT_RECORD_VERIFIER_FILE_OFF
#error "generated boot-family record verifier binding is required"
#endif
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
#error "L65R format bank tag is frozen at 3"
#endif
#if LISP65_RUNTIME_OVERLAY_STORAGE_BASE != 0x08000000UL || \
    LISP65_RUNTIME_OVERLAY_STORAGE_MEGABYTE != 0x80u || \
    LISP65_RUNTIME_OVERLAY_STORAGE_WINDOW_BYTES != 0x00010000UL
#error "runtime-overlay storage must be the pinned 64-KB Attic window"
#endif
#ifdef LISP65_RUNTIME_OVERLAY_LIFETIME_FAMILIES
#if LISP65_RUNTIME_OVERLAY_BOOT_STORAGE_BASE != 0x08200000UL
#error "C2 boot-family storage must use the pinned $08200000 tenant"
#endif
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
#error "runtime-overlay verifier payload exceeds the L65R storage window"
#endif

#if defined(__GNUC__) || defined(__clang__)
#define RTOV_CATALOGFN __attribute__((noinline, used, section(".lisp65_rt_rtov_catalog")))
#define RTOV_RECORDFN  __attribute__((noinline, used, section(".lisp65_rt_rtov_record")))
#define RTOV_ISLANDFN  __attribute__((noinline, used, section(".lisp65_rt_island_00")))
#define RTOV_ISLAND2FN __attribute__((noinline, used, section(".lisp65_rt_island_01")))
#define RTOV_ISLANDDATA __attribute__((used, section(".lisp65_rt_island_00_data")))
#define RTOV_NOINLINE  __attribute__((noinline))
#define RTOV_ALWAYS_INLINE __attribute__((always_inline)) inline
#else
#define RTOV_CATALOGFN
#define RTOV_RECORDFN
#define RTOV_ISLANDFN
#define RTOV_ISLAND2FN
#define RTOV_ISLANDDATA
#define RTOV_NOINLINE
#define RTOV_ALWAYS_INLINE inline
#endif

#ifdef LISP65_RUNTIME_OVERLAY_HOST_TEST
extern uint8_t lisp65_resident_island_host_target[
    LISP65_RUNTIME_ISLAND_CAPACITY];
static uint8_t rtov_island_copy_fault;
static uint8_t rtov_island_frame_fault;
static uint16_t rtov_host_island_length;
static uint16_t rtov_host_island_crc;
static uint16_t rtov_transaction_context_calls;
#define RTOV_ISLAND_TARGET lisp65_resident_island_host_target
#else
extern uint8_t __lisp65_resident_island_start[];
extern uint8_t __lisp65_resident_island_end[];
#define RTOV_ISLAND_TARGET __lisp65_resident_island_start
#endif

typedef void (*rtov_read_fn)(uint16_t relative, uint8_t *dst, uint16_t length);
static void rtov_read(uint16_t relative, uint8_t *dst, uint16_t length);
static void rtov_read_region(
    uint8_t region, uint16_t relative, uint8_t *dst, uint16_t length);
static void rtov_read_source(
    uint16_t source_low, uint16_t source_high,
    uint8_t *dst, uint16_t length);

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
    uint8_t count;
    uint8_t buffer[LISP65_RUNTIME_OVERLAY_ENTRY_SIZE];
    uint16_t seal;
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

#if LISP65_RUNTIME_OVERLAY_FORMAT_VERSION == 1u
RTOV_ISLANDDATA static const uint8_t
rtov_island_image[LISP65_RESIDENT_ISLAND_LENGTH] =
    LISP65_RESIDENT_ISLAND_BYTES;
#endif

#ifdef LISP65_RUNTIME_OVERLAY_HOST_TEST
/* Host-only fixtures do not link the target's non-LTO binding table. */
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

#ifdef LISP65_RUNTIME_OVERLAY_LIFETIME_FAMILIES
static const volatile rtov_verifier_tuple
rtov_boot_verifiers[LISP65_RUNTIME_OVERLAY_APPLICATION_SLOT_BASE] = {
    {
        LISP65_RUNTIME_OVERLAY_BOOT_CATALOG_VERIFIER_FILE_OFF,
        LISP65_RUNTIME_OVERLAY_BOOT_CATALOG_VERIFIER_FILE_SIZE,
        LISP65_RUNTIME_OVERLAY_BOOT_CATALOG_VERIFIER_ENTRY_OFFSET,
        LISP65_RUNTIME_OVERLAY_BOOT_CATALOG_VERIFIER_CRC16
    },
    {
        LISP65_RUNTIME_OVERLAY_BOOT_RECORD_VERIFIER_FILE_OFF,
        LISP65_RUNTIME_OVERLAY_BOOT_RECORD_VERIFIER_FILE_SIZE,
        LISP65_RUNTIME_OVERLAY_BOOT_RECORD_VERIFIER_ENTRY_OFFSET,
        LISP65_RUNTIME_OVERLAY_BOOT_RECORD_VERIFIER_CRC16
    }
};
#endif
#else
/* The target table is an assembler-owned 32-byte publish-last section.  Code
 * sees only these external fixed-layout symbols; tuple contents never enter
 * whole-program LTO and therefore cannot perturb slice identity. */
extern const volatile rtov_verifier_tuple
rtov_boot_verifiers[LISP65_RUNTIME_OVERLAY_APPLICATION_SLOT_BASE];
extern const volatile rtov_verifier_tuple
rtov_verifiers[LISP65_RUNTIME_OVERLAY_APPLICATION_SLOT_BASE];
#endif

/* Only the bytes needed to clean the shared execution window survive calls. */
#if defined(__mos__) && \
    (defined(LISP65_RTOV_MINIMAL_RESIDENT_RETRY_PROBE) || \
     defined(LISP65_RTOV_SHARED_RESIDENT_RETRY_PROBE))
/* Linker-visible only for the non-promotable minimal-resident retry probe.
 * The ordinary product keeps this resident byte-count private. */
uint16_t rtov_loaded_len;
#else
static uint16_t rtov_loaded_len;
#endif
static uint8_t rtov_fault;
static uint8_t rtov_busy;
static vm_runtime_overlay_repeat_predicate_fn rtov_repeat;
/* The installer handoff and diagnostic seams retain these named context and
 * result/target slots. Installer-only volatile accesses below prevent
 * anonymous cross-call spills. */
static void *rtov_call_context;
static uint8_t *rtov_call_result;
#define RTOV_INSTALL_CONTEXT (*(void * volatile *)&rtov_call_context)
#define RTOV_INSTALL_TARGET (*(uint8_t * volatile *)&rtov_call_result)
#if defined(LISP65_RTOV_ISLAND_SPLIT_PROBE) || \
    defined(LISP65_RUNTIME_OVERLAY_TRANSACTION_AUTH_ISLAND)
/* The split installer transports the authenticated carrier tuple between its
 * two serial records.  The product transaction profile later reuses the same
 * lifetime-exclusive words for its authenticated catalog outputs. */
static uint16_t rtov_batch_entry;
static uint16_t rtov_batch_crc;
#endif
#if defined(LISP65_RUNTIME_OVERLAY_TRANSACTION_AUTH_ISLAND) || \
    defined(LISP65_RTOV_FLOOR_BREAK_RETRY_PROBE) || \
    (defined(LISP65_C1_COMPILER_TIER) && \
     !defined(LISP65_RUNTIME_OVERLAY_TRANSACTION_AUTH_ISLAND))
#if defined(__mos__) && defined(LISP65_RTOV_FLOOR_BREAK_RETRY_PROBE)
/* Linker-visible only for the purpose-bound fixed retry-call scaffold. */
uint8_t rtov_batch_slot_id;
#else
static uint8_t rtov_batch_slot_id;
#endif
#endif
static uint8_t rtov_island_state;
#ifdef LISP65_RUNTIME_OVERLAY_LIFETIME_FAMILIES
static uint8_t rtov_family;
static uint16_t rtov_family_generation;
#ifdef LISP65_C2_LITE_BANK3_STAGING
#define RTOV_FAMILY_STAGING  0x40u
#define RTOV_FAMILY_VERIFIED 0x80u
#define RTOV_FAMILY_BASE(v)  ((uint8_t)((v) & 0x03u))
#endif
#endif
#ifdef LISP65_RUNTIME_OVERLAY_TRANSACTION_AUTH
/* Valid only while one caller-owned append transaction is active. The cache
 * contains authenticated catalog outputs; record and payload checks remain
 * per slice. */
#ifdef LISP65_RUNTIME_OVERLAY_TRANSACTION_AUTH_ISLAND
/* Batch execution and C2 append transactions are lifetime-exclusive. Reuse
 * the batch tuple rather than spending seven bytes in the full Bank-0 BSS:
 * entry/crc hold the two authenticated u16 catalog outputs and slot_id holds
 * either the untrusted sentinel or the authenticated catalog count. Ordinary
 * batch completion clears slot_id before releasing the shared tuple. */
#define RTOV_TRANSACTION_INACTIVE  0u
#define RTOV_TRANSACTION_UNTRUSTED 0xffu
#define rtov_transaction_payload_off rtov_batch_entry
#define rtov_transaction_image_limit rtov_batch_crc
#define rtov_transaction_count rtov_batch_slot_id
#define RTOV_TRANSACTION_ACTIVE() \
    ((uint8_t)(rtov_repeat == 0 && \
               rtov_transaction_count != RTOV_TRANSACTION_INACTIVE))
#define RTOV_TRANSACTION_TRUSTED() \
    ((uint8_t)(RTOV_TRANSACTION_ACTIVE() && \
               rtov_transaction_count != RTOV_TRANSACTION_UNTRUSTED))
#else
static uint16_t rtov_transaction_payload_off;
static uint16_t rtov_transaction_image_limit;
static uint8_t rtov_transaction_count;
static uint8_t rtov_transaction_active;
static uint8_t rtov_transaction_trusted;
#define RTOV_TRANSACTION_ACTIVE()  rtov_transaction_active
#define RTOV_TRANSACTION_TRUSTED() rtov_transaction_trusted
#endif
#endif

#ifndef LISP65_RUNTIME_OVERLAY_HOST_TEST
#ifdef LISP65_RTOV_DMA_COMPLETION_FENCE
/* The payload job and its one-byte publish-last completion job each own an
 * Enhanced-DMA option list.  A chained job re-enters option parsing, so the
 * second list is explicit rather than inheriting DMA-controller state. */
#define RTOV_EDMA_JOB_BYTES 40u
#define RTOV_EDMA_DONE      0xa5u
/* Private linker-visible storage for the non-LTO completion leaf.  These are
 * not C API symbols; their visibility lets the assembler own the complete
 * trigger/poll critical region without duplicating state. */
volatile uint8_t rtov_edma_complete;
void rtov_dma_submit_wait(void);
#else
#define RTOV_EDMA_JOB_BYTES 20u
#endif
/* Enhanced-DMA options plus one F018B copy descriptor. The high source byte is
 * fixed by the generated Attic binding; each read only patches 16-bit offsets.
 * The completion profile appends another options/descriptor pair. */
__attribute__((used))
#ifdef LISP65_RTOV_DMA_COMPLETION_FENCE
uint8_t
#else
static uint8_t
#endif
rtov_edma_job[RTOV_EDMA_JOB_BYTES] = {
    0x0b, 0x80, LISP65_RUNTIME_OVERLAY_STORAGE_MEGABYTE,
    0x81, 0x00, 0x85, 0x01, 0x00,
#ifdef LISP65_RTOV_DMA_COMPLETION_FENCE
    0x04, 0x00, 0x00, 0x00, 0x00,
#else
    0x00, 0x00, 0x00, 0x00, 0x00,
#endif
    (uint8_t)((LISP65_RUNTIME_OVERLAY_STORAGE_BASE >> 16) & 0x0fu),
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00
#ifdef LISP65_RTOV_DMA_COMPLETION_FENCE
    , 0x0b, 0x80, 0x00, 0x81, 0x00, 0x85, 0x01, 0x00,
    0x03, 0x01, 0x00, RTOV_EDMA_DONE, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00
#endif
};
#endif

#if defined(__mos__) && \
    (defined(LISP65_RTOV_MINIMAL_RESIDENT_RETRY_PROBE) || \
     defined(LISP65_RTOV_SHARED_RESIDENT_RETRY_PROBE))
static RTOV_ISLANDFN uint16_t rtov_crc_byte(uint16_t crc, uint8_t value) {
#else
static uint16_t rtov_crc_byte(uint16_t crc, uint8_t value) {
#endif
    uint8_t bits = 8;
    crc ^= (uint16_t)value << 8;
    do {
        crc = (crc & 0x8000u)
                ? (uint16_t)((crc << 1) ^ LISP65_RUNTIME_OVERLAY_CRC16_POLY)
                : (uint16_t)(crc << 1);
    } while (--bits);
    return crc;
}

#ifdef __mos__
/* Target definition is the named, sized assembler leaf in rtov_crc_mem.s.
 * Keeping the portable definition below for host builds makes the existing
 * reference and mutation suites independent of MOS instruction selection. */
uint16_t rtov_crc_mem(const uint8_t *p, uint16_t length);
#else
static uint16_t rtov_crc_mem(const uint8_t *p, uint16_t length) {
    uint16_t crc = LISP65_RUNTIME_OVERLAY_CRC16_INIT;
    while (length--) crc = rtov_crc_byte(crc, *p++);
    return crc;
}
#endif

#ifdef LISP65_RTOV_CRC_CONVERGENCE
#ifndef __mos__
static uint16_t rtov_host_frame;
#endif

/* One frame source, copied into the temperature domain of each caller.  On
 * target this is the same product-owned $ff83/$ff84 counter exposed by the
 * public handoff helper; keeping the sample inline prevents three cold boot
 * consumers from importing generic convergence machinery into Bank 0. */
static RTOV_ALWAYS_INLINE uint16_t rtov_frame_now_inline(void) {
#ifdef __mos__
    return c2_kernal_frame_count_inline();
#else
    /* Host transports are synchronous. Advancing the model clock keeps an
     * injected mismatch fail-closed instead of turning a host mutation into
     * an infinite loop. */
    return rtov_host_frame++;
#endif
}

static RTOV_ALWAYS_INLINE uint8_t rtov_completion_expired_inline(
        uint16_t start) {
    return (uint16_t)(rtov_frame_now_inline() - start) >=
           LISP65_RTOV_COMPLETION_TIMEOUT_FRAMES;
}

/* The only resident convergence driver.  It wraps the CRC leaf that the hot
 * verifier/application transport already used; all boot-only object shapes
 * own their corresponding loops inside their slices below. */
#if defined(__mos__) && defined(LISP65_RTOV_MINIMAL_RESIDENT_RETRY_PROBE)
uint16_t rtov_crc_retry_start_probe(void);
uint8_t rtov_crc_retry_after_miss_probe(uint16_t expected,
                                        uint16_t start_frame);

static RTOV_ALWAYS_INLINE vm_runtime_overlay_status rtov_crc_converge(
        const uint8_t *bytes, uint16_t length, uint16_t expected) {
    uint16_t start = rtov_crc_retry_start_probe();
    if (rtov_crc_mem(bytes, length) == expected)
        return VM_RUNTIME_OVERLAY_OK;
    return (vm_runtime_overlay_status)
        rtov_crc_retry_after_miss_probe(expected, start);
}
#elif defined(__mos__) && defined(LISP65_RTOV_SHARED_RESIDENT_RETRY_PROBE)
uint8_t rtov_crc_converge_shared_probe(uint16_t expected);

static RTOV_ALWAYS_INLINE vm_runtime_overlay_status rtov_crc_converge(
        const uint8_t *bytes, uint16_t length, uint16_t expected) {
    /* Both resident consumers operate on the one fixed execution window and
     * publish rtov_loaded_len immediately before transport.  Keeping only the
     * expected CRC variable is the commissioned single-driver boundary. */
    (void)bytes;
    (void)length;
    return (vm_runtime_overlay_status)
        rtov_crc_converge_shared_probe(expected);
}
#else
static RTOV_NOINLINE vm_runtime_overlay_status rtov_crc_converge(
        const uint8_t *bytes, uint16_t length, uint16_t expected) {
    uint16_t start = rtov_frame_now_inline();
    do {
        if (rtov_crc_mem(bytes, length) == expected)
            return VM_RUNTIME_OVERLAY_OK;
    } while (!rtov_completion_expired_inline(start));
    return VM_RUNTIME_OVERLAY_ERR_COMPLETION_TIMEOUT;
}
#endif
#endif

#if LISP65_RUNTIME_OVERLAY_FORMAT_VERSION >= 2u
static RTOV_ISLANDFN uint16_t rtov_island_u16(const uint8_t *p) {
    return (uint16_t)(p[0] | ((uint16_t)p[1] << 8));
}

static RTOV_ISLANDFN uint8_t rtov_island_build_id(const uint8_t *p) {
    return p[0] == (uint8_t)LISP65_RUNTIME_OVERLAY_PROFILE_BUILD_ID &&
           p[1] == (uint8_t)(LISP65_RUNTIME_OVERLAY_PROFILE_BUILD_ID >> 8) &&
           p[2] == (uint8_t)(LISP65_RUNTIME_OVERLAY_PROFILE_BUILD_ID >> 16) &&
           p[3] == (uint8_t)(LISP65_RUNTIME_OVERLAY_PROFILE_BUILD_ID >> 24);
}

/* Source authentication belongs to the one boot-only installer slice.  It
 * streams through the resident verifier's already-live 32-byte scratch, so
 * no carrier byte overwrites either the installer or the destination before
 * the immutable source CRC has passed. */
static RTOV_ISLANDFN uint16_t rtov_island_source_crc(
        rtov_verify_context *frame, uint16_t file_off,
        uint16_t file_len) {
    uint16_t crc = LISP65_RUNTIME_OVERLAY_CRC16_INIT;
    while (file_len) {
        uint8_t index = 0;
        uint8_t chunk = file_len > LISP65_RUNTIME_OVERLAY_ENTRY_SIZE
                          ? LISP65_RUNTIME_OVERLAY_ENTRY_SIZE
                          : (uint8_t)file_len;
        frame->read(file_off, frame->buffer, chunk);
        while (index != chunk)
            crc = rtov_crc_byte(crc, frame->buffer[index++]);
        file_off = (uint16_t)(file_off + chunk);
        file_len = (uint16_t)(file_len - chunk);
    }
    return crc;
}

#ifdef LISP65_RTOV_CRC_CONVERGENCE
static RTOV_ISLANDFN uint16_t rtov_island_crc_virtual_zero(
        const volatile uint8_t *bytes, uint8_t length, uint8_t zero_offset) {
    uint16_t crc = LISP65_RUNTIME_OVERLAY_CRC16_INIT;
    uint8_t index = 0;
    do {
        uint8_t value = (index == zero_offset ||
                         index == (uint8_t)(zero_offset + 1u))
                          ? 0u : bytes[index];
        crc = rtov_crc_byte(crc, value);
    } while (++index != length);
    return crc;
}

static RTOV_ISLANDFN vm_runtime_overlay_status rtov_island_record_converge(
        const volatile uint8_t *record) {
    uint16_t start = rtov_frame_now_inline();
    do {
        uint16_t expected = (uint16_t)record[22] |
                            ((uint16_t)record[23] << 8);
        if (expected && rtov_island_crc_virtual_zero(
                record, LISP65_RUNTIME_OVERLAY_ENTRY_SIZE, 22u) == expected)
            return VM_RUNTIME_OVERLAY_OK;
    } while (!rtov_completion_expired_inline(start));
    return VM_RUNTIME_OVERLAY_ERR_COMPLETION_TIMEOUT;
}

static RTOV_ISLANDFN vm_runtime_overlay_status rtov_island_source_converge(
        rtov_verify_context *frame, uint16_t file_off,
        uint16_t file_len, uint16_t expected) {
    uint16_t start = rtov_frame_now_inline();
    do {
        if (rtov_island_source_crc(frame, file_off, file_len) == expected)
            return VM_RUNTIME_OVERLAY_OK;
    } while (!rtov_completion_expired_inline(start));
    return VM_RUNTIME_OVERLAY_ERR_COMPLETION_TIMEOUT;
}

#if defined(LISP65_RTOV_ISLAND_SPLIT_PROBE)
static RTOV_ISLAND2FN vm_runtime_overlay_status rtov_island_target_converge(
#else
static RTOV_ISLANDFN vm_runtime_overlay_status rtov_island_target_converge(
#endif
        const uint8_t *bytes, uint16_t length, uint16_t expected) {
    uint16_t start = rtov_frame_now_inline();
    do {
        if (rtov_crc_mem(bytes, length) == expected)
            return VM_RUNTIME_OVERLAY_OK;
    } while (!rtov_completion_expired_inline(start));
    return VM_RUNTIME_OVERLAY_ERR_COMPLETION_TIMEOUT;
}
#endif

#endif

RTOV_ISLANDFN uint8_t vm_resident_island_install(void *opaque) {
#if LISP65_RUNTIME_OVERLAY_FORMAT_VERSION >= 2u
    /* Slot 8 is boot-only. Its record verifier publishes the authenticated
     * frame through the existing installation seam before this slice is
     * transported. The generic resident dispatcher therefore has no v2 or
     * DATA_ONLY branch and remains a session-hot, format-neutral path. */
    rtov_verify_context *frame =
        (rtov_verify_context *)RTOV_INSTALL_CONTEXT;
    uint16_t file_len = 0;
    uint16_t payload_crc = 0;
#endif
    uint8_t status;
#if LISP65_RUNTIME_OVERLAY_FORMAT_VERSION >= 2u
    if (!frame) return VM_RUNTIME_ISLAND_ERR_CONTEXT;
#else
    if (!opaque) return VM_RUNTIME_ISLAND_ERR_CONTEXT;
    RTOV_INSTALL_CONTEXT = opaque;
#endif
    RTOV_INSTALL_TARGET = (uint8_t *)RTOV_ISLAND_TARGET;
#if LISP65_RUNTIME_OVERLAY_FORMAT_VERSION >= 2u
    {
        uint8_t index;
        uint8_t *record;
        uint16_t end;
        uint16_t file_off;
        /* Slot 8 is the sole installation story.  The resident dispatcher
         * has authenticated this catalog and supplied its exact bounds; this
         * boot-only discriminant decodes only the DATA_ONLY member of L65R-v2.
         * It is never entered through the public/session dispatcher. */
        /* The verifier frame is the sole authenticated handoff.  Its seal was
         * produced after the executable payload CRC passed and covers every
         * byte before the seal itself, including the authenticated Slot-8
         * record in the exclusive scratch.  Check it before that scratch is
         * reused for the carrier: any intervening write fails before a carrier
         * or destination byte is touched. */
#ifdef LISP65_RUNTIME_OVERLAY_HOST_TEST
        if (rtov_island_frame_fault) frame->file_len ^= 1u;
#endif
        record = frame->buffer;
        if (rtov_crc_mem((const uint8_t *)frame,
                         offsetof(rtov_verify_context, seal)) != frame->seal)
            return VM_RUNTIME_ISLAND_ERR_BINDING;
        frame->read((uint16_t)(LISP65_RUNTIME_OVERLAY_HEADER_SIZE +
                               (uint16_t)LISP65_RUNTIME_ISLAND_CARRIER_SLOT *
                               LISP65_RUNTIME_OVERLAY_ENTRY_SIZE),
                    record, LISP65_RUNTIME_OVERLAY_ENTRY_SIZE);
#if (LISP65_RUNTIME_OVERLAY_FORMAT_VERSION == 3u || \
     LISP65_RUNTIME_OVERLAY_FORMAT_VERSION == 4u) && \
    defined(LISP65_RTOV_CRC_CONVERGENCE)
        if (rtov_island_record_converge(record) != VM_RUNTIME_OVERLAY_OK)
            return VM_RUNTIME_OVERLAY_ERR_COMPLETION_TIMEOUT;
#endif
        if (rtov_island_u16(record) !=
                LISP65_RUNTIME_ISLAND_CARRIER_SLOT ||
            rtov_island_u16(record + 2) !=
                (LISP65_RUNTIME_OVERLAY_FLAG_BOOT |
                 LISP65_RUNTIME_OVERLAY_FLAG_DATA_ONLY) ||
            rtov_island_u16(record + 8) != LISP65_RUNTIME_ISLAND_ADDRESS ||
            rtov_island_u16(record + 10) != rtov_island_u16(record + 6) ||
            rtov_island_u16(record + 12) !=
                LISP65_RUNTIME_OVERLAY_DATA_ENTRY_NONE ||
            rtov_island_u16(record + 14) != 0 ||
            !rtov_island_build_id(record + 16))
            return VM_RUNTIME_ISLAND_ERR_BINDING;
#if LISP65_RUNTIME_OVERLAY_FORMAT_VERSION == 4u
        if (record[24] != LISP65_RUNTIME_OVERLAY_REGION_MAIN ||
            record[25] !=
                (uint8_t)((LISP65_RUNTIME_OVERLAY_BOOT_STORAGE_BASE >> 16)
                          & 0x0fu) ||
            record[26] !=
                (uint8_t)(LISP65_RUNTIME_OVERLAY_BOOT_STORAGE_BASE >> 20) ||
            record[27])
            return VM_RUNTIME_ISLAND_ERR_BINDING;
        index = 28u;
#elif LISP65_RUNTIME_OVERLAY_FORMAT_VERSION == 3u
        index = 24u;
#else
        index = 22u;
#endif
        do {
            if (record[index]) return VM_RUNTIME_ISLAND_ERR_BINDING;
        } while (++index != LISP65_RUNTIME_OVERLAY_ENTRY_SIZE);
        file_off = rtov_island_u16(record + 4);
        file_len = rtov_island_u16(record + 6);
        payload_crc = rtov_island_u16(record + 20);
        end = (uint16_t)(file_off + file_len);
        if (!file_len ||
            file_len > LISP65_RUNTIME_OVERLAY_HARD_MAX_SLICE ||
            (file_off & 255u) || file_off < frame->payload_off ||
            (end < file_off && end != 0) ||
            (frame->image_limit &&
             (end < file_off || end > frame->image_limit)))
            return VM_RUNTIME_ISLAND_ERR_CRC;
#ifdef LISP65_RTOV_CRC_CONVERGENCE
        if (rtov_island_source_converge(
                frame, file_off, file_len, payload_crc) !=
            VM_RUNTIME_OVERLAY_OK)
            return VM_RUNTIME_OVERLAY_ERR_COMPLETION_TIMEOUT;
#else
        if (rtov_island_source_crc(frame, file_off, file_len) != payload_crc)
            return VM_RUNTIME_ISLAND_ERR_CRC;
#endif
#ifdef LISP65_RUNTIME_OVERLAY_HOST_TEST
        /* Host evidence consumes the same authenticated final-record identity
         * as the target installer.  A prerequisite seed array is deliberately
         * not a second oracle for v2/v3 carrier bytes. */
        rtov_host_island_length = file_len;
        rtov_host_island_crc = payload_crc;
#endif
#ifdef LISP65_RTOV_ISLAND_SPLIT_PROBE
        /* The authenticated final carrier record is the sole runtime
         * identity.  Its source offset, payload CRC and length cross the
         * serial phase boundary through the installer/batch-exclusive tuple;
         * the prerequisite seed identity is intentionally not consulted.
         * The resident driver loads Phase 01 after this phase returns, so no
         * overlay calls another overlay and no new resident state exists. */
        rtov_batch_entry = file_off;
        rtov_batch_crc = payload_crc;
        RTOV_INSTALL_CONTEXT = (void *)(uintptr_t)file_len;
        return VM_RUNTIME_ISLAND_OK;
#else
        frame->read(file_off, RTOV_INSTALL_TARGET, file_len);
#endif
    }
#else
    /* L65R-v1 embeds the payload in the executable installer. */
    memcpy(RTOV_INSTALL_TARGET, rtov_island_image,
           LISP65_RESIDENT_ISLAND_LENGTH);
#endif
#ifndef LISP65_RTOV_ISLAND_SPLIT_PROBE
#ifdef LISP65_RUNTIME_OVERLAY_HOST_TEST
    if (rtov_island_copy_fault) RTOV_INSTALL_TARGET[0] ^= 1u;
#endif
#ifdef LISP65_RTOV_CRC_CONVERGENCE
    status = (uint8_t)rtov_island_target_converge(
        RTOV_INSTALL_TARGET,
#if LISP65_RUNTIME_OVERLAY_FORMAT_VERSION >= 2u
        file_len, payload_crc);
#else
        LISP65_RESIDENT_ISLAND_LENGTH, LISP65_RESIDENT_ISLAND_CRC16);
#endif
#else
    status = rtov_crc_mem(RTOV_INSTALL_TARGET,
#if LISP65_RUNTIME_OVERLAY_FORMAT_VERSION >= 2u
                          file_len) == payload_crc
#else
                          LISP65_RESIDENT_ISLAND_LENGTH) ==
                     LISP65_RESIDENT_ISLAND_CRC16
#endif
                 ? VM_RUNTIME_ISLAND_OK
                 : VM_RUNTIME_ISLAND_ERR_CRC;
#endif
    opaque = RTOV_INSTALL_CONTEXT;
#if LISP65_RUNTIME_OVERLAY_FORMAT_VERSION == 1u
    ((rtov_island_install_context *)opaque)->status = status;
#else
    (void)opaque;
#endif
    return status;
#endif
}

#ifdef LISP65_RTOV_ISLAND_SPLIT_PROBE
RTOV_ISLAND2FN uint8_t vm_resident_island_finalize(void *opaque) {
    uint8_t status;
    uint16_t file_off = rtov_batch_entry;
    uint16_t file_len = (uint16_t)(uintptr_t)RTOV_INSTALL_CONTEXT;
    uint16_t payload_crc = rtov_batch_crc;
    (void)opaque;
    /* Consume and retire the complete authenticated handoff before touching
     * the destination.  A replay or malformed partial tuple cannot borrow a
     * prerequisite seed constant as a fallback identity. */
    rtov_batch_entry = 0;
    rtov_batch_crc = 0;
    RTOV_INSTALL_CONTEXT = 0;
    if (!file_off || !file_len ||
        file_len > LISP65_RUNTIME_OVERLAY_HARD_MAX_SLICE ||
        (file_off & 255u))
        return VM_RUNTIME_ISLAND_ERR_BINDING;
    rtov_read(file_off, (uint8_t *)RTOV_ISLAND_TARGET, file_len);
#ifdef LISP65_RUNTIME_OVERLAY_HOST_TEST
    if (rtov_island_copy_fault) RTOV_ISLAND_TARGET[0] ^= 1u;
#endif
#ifdef LISP65_RTOV_CRC_CONVERGENCE
    status = (uint8_t)rtov_island_target_converge(
        RTOV_ISLAND_TARGET, file_len, payload_crc);
#else
    status = rtov_crc_mem(RTOV_ISLAND_TARGET,
                          file_len) == payload_crc
                 ? VM_RUNTIME_ISLAND_OK
                 : VM_RUNTIME_ISLAND_ERR_CRC;
#endif
    return status;
}
#endif

static void rtov_read_source(
        uint16_t source_low, uint16_t source_high,
        uint8_t *dst, uint16_t length) {
#ifdef LISP65_RUNTIME_OVERLAY_HOST_TEST
    /* Host storage models the canonical catalog as Bank 3.  Absolute v4
     * sources retain their low 16 bits, while Bank 5 is the only distinct
     * chip-RAM backing that needs a separate model bank. */
    if ((uint8_t)source_high == LISP65_RUNTIME_OVERLAY_REGION1_BANK)
        vm_code_load(
            (uint8_t)LISP65_RUNTIME_OVERLAY_REGION1_BANK,
            source_low, length, dst);
    else
        vm_code_load((uint8_t)LISP65_RUNTIME_OVERLAY_FORMAT_BANK_TAG,
                     source_low, length, dst);
#else
    uint16_t target = (uint16_t)(uintptr_t)dst;
    rtov_edma_job[2] = (uint8_t)(source_high >> 8);
    rtov_edma_job[13] = (uint8_t)source_high;
    rtov_edma_job[9] = (uint8_t)length;
    rtov_edma_job[10] = (uint8_t)(length >> 8);
    rtov_edma_job[11] = (uint8_t)source_low;
    rtov_edma_job[12] = (uint8_t)(source_low >> 8);
    rtov_edma_job[14] = (uint8_t)target;
    rtov_edma_job[15] = (uint8_t)(target >> 8);
#ifdef LISP65_RTOV_DMA_COMPLETION_FENCE
    /* A normal DMAgic job is documented to hold the CPU until completion, but
     * the bound Link-34 hardware trace observed a still-changing destination
     * after an Attic read.  Chain a one-byte Bank-0 fill as the publication
     * witness.  No consumer can run until that ordered marker is visible.
     * Keep maskable aborts outside the descriptor/transfer interval; NMI may
     * round-trip, but cannot mutate this private list or marker. */
    target = (uint16_t)(uintptr_t)&rtov_edma_complete;
    rtov_edma_job[34] = (uint8_t)target;
    rtov_edma_job[35] = (uint8_t)(target >> 8);
#endif
#ifdef LISP65_RTOV_DMA_COMPLETION_FENCE
    /* The external non-LTO leaf is also the compiler barrier: it owns marker
     * reset, interrupt masking, DMA submission, completion polling and status
     * restoration as one target-stable instruction sequence. */
    rtov_dma_submit_wait();
#else
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
#endif
}

static void rtov_read_region(
        uint8_t region, uint16_t relative, uint8_t *dst, uint16_t length) {
    uint32_t storage = LISP65_RUNTIME_OVERLAY_STORAGE_BASE;
#if LISP65_RUNTIME_OVERLAY_FORMAT_VERSION == 4u
    if (region == LISP65_RUNTIME_OVERLAY_REGION_C2D_OVERFLOW)
        storage = ((uint32_t)LISP65_RUNTIME_OVERLAY_REGION1_BANK << 16)
                  + LISP65_RUNTIME_OVERLAY_REGION1_ADDRESS;
    else
#else
    (void)region;
#endif
#ifdef LISP65_RUNTIME_OVERLAY_LIFETIME_FAMILIES
    if (rtov_family == LISP65_RUNTIME_OVERLAY_FAMILY_BOOT)
        storage = LISP65_RUNTIME_OVERLAY_BOOT_STORAGE_BASE;
#ifdef LISP65_C2_LITE_BANK3_STAGING
    else
        storage = 0x00030000UL;
#endif
#endif
    storage += LISP65_RUNTIME_OVERLAY_CATALOG_OFF + relative;
    rtov_read_source(
        (uint16_t)storage,
        (uint16_t)(((storage >> 16) & 0x0fu) | ((storage >> 12) & 0xff00u)),
        dst, length);
}

static void rtov_read(uint16_t relative, uint8_t *dst, uint16_t length) {
    rtov_read_region(
        LISP65_RUNTIME_OVERLAY_REGION_MAIN, relative, dst, length);
}

static uint8_t rtov_wipe(void) {
    volatile uint8_t *target = (volatile uint8_t *)RTOV_TARGET;
    uint16_t i, length = rtov_loaded_len;
    memset((void *)target, 0, length);
    for (i = 0; i < length; i++) if (target[i]) return 0;
    rtov_loaded_len = 0;
    return 1;
}

#ifdef LISP65_RUNTIME_OVERLAY_TRANSACTION_AUTH
static void rtov_transaction_invalidate(void) {
#ifdef LISP65_RUNTIME_OVERLAY_TRANSACTION_AUTH_ISLAND
    /* Clearing the discriminator makes the cached words unreachable. */
    rtov_transaction_count = RTOV_TRANSACTION_INACTIVE;
#else
    rtov_transaction_payload_off = 0;
    rtov_transaction_image_limit = 0;
    rtov_transaction_count = 0;
    rtov_transaction_active = 0;
    rtov_transaction_trusted = 0;
#endif
}

#ifdef LISP65_RUNTIME_OVERLAY_TRANSACTION_AUTH_ISLAND
/* The transaction-only catalog seam is cold, installed before C2 boot and
 * never needed by the boot-time island installer itself. Keep it out of the
 * closed Bank-0 text corridor. Return 0 for a full catalog proof, 1 for the
 * authenticated record-only path and 0xff for an invalid cached slot. */
static LISP65_RESIDENT_ISLAND_FN uint8_t rtov_transaction_context(
        rtov_verify_context *verify, uint8_t publish) {
#ifdef LISP65_RUNTIME_OVERLAY_HOST_TEST
    ++rtov_transaction_context_calls;
#endif
    if (!RTOV_TRANSACTION_ACTIVE()) return 0;
    if (publish) {
        rtov_transaction_payload_off = verify->payload_off;
        rtov_transaction_image_limit = verify->image_limit;
        rtov_transaction_count = verify->count;
        return 0;
    }
    if (!RTOV_TRANSACTION_TRUSTED()) return 0;
    if (verify->slot < LISP65_RUNTIME_OVERLAY_APPLICATION_SLOT_BASE
        || verify->slot >= rtov_transaction_count) return 0xffu;
    verify->payload_off = rtov_transaction_payload_off;
    verify->image_limit = rtov_transaction_image_limit;
    verify->count = rtov_transaction_count;
    return 1;
}

/* The boot installer creates the Island that owns rtov_transaction_context.
 * It may therefore enter that function only after READY has been published.
 * Keep the discriminator test resident; stale bytes at $1800 are untrusted. */
static RTOV_NOINLINE uint8_t rtov_transaction_context_if_ready(
        rtov_verify_context *verify, uint8_t publish) {
    if (!RTOV_TRANSACTION_ACTIVE()) return 0;
    if (rtov_island_state != RTOV_ISLAND_READY) return 0xfeu;
    return rtov_transaction_context(verify, publish);
}
#endif
#endif

static vm_runtime_overlay_status LISP65_C2_FIXED_BANK0_CODE("rtov_fail")
rtov_fail(vm_runtime_overlay_status status) {
#ifdef LISP65_RUNTIME_OVERLAY_TRANSACTION_AUTH
    rtov_transaction_invalidate();
#endif
    rtov_fault = (uint8_t)status;
    if (!rtov_wipe()) rtov_fault = VM_RUNTIME_OVERLAY_ERR_WIPE;
    rtov_busy = 0;
    return (vm_runtime_overlay_status)rtov_fault;
}

#if defined(LISP65_RUNTIME_OVERLAY_LIFETIME_FAMILIES) && \
    defined(LISP65_C2_LITE_BANK3_STAGING)
#ifndef LISP65_RUNTIME_OVERLAY_BOOT_STORAGE_BASE
#error "Bank-3 staging requires the generated Boot-family Attic base"
#endif
#ifndef LISP65_RUNTIME_OVERLAY_STORAGE_BASE
#error "Bank-3 staging requires the generated Session-family Attic base"
#endif

#define C2_LITE_BANK3_PHYSICAL 0x00030000UL
#define C2_LITE_STAGE_BLOCK 32u

typedef struct {
    uint16_t image_size;
    uint16_t crc16;
} c2_lite_family_stage_binding;

/* Filled publish-last from the two final family manifests.  The cold stage
 * records consume these tuples; no transition helper remains resident. */
extern const volatile c2_lite_family_stage_binding
    rtov_family_stage_bindings[2];

#if LISP65_RUNTIME_OVERLAY_FORMAT_VERSION == 4u
/* Region 1 is a product-owned stage, not an externally trusted preload.
 * The authenticated Region-0 header carries the exact size/CRC tuple. */
__attribute__((noinline, used, section(".lisp65_rt_bank3_stage_session")))
static uint8_t c2_lite_stage_session_overflow(void) {
    uint8_t block[C2_LITE_STAGE_BLOCK];
    uint16_t size, expected, start, offset, left, crc;
    c2_facade_vm_code_load(3u, 28u, 4u, block);
    size = (uint16_t)(block[0] | ((uint16_t)block[1] << 8));
    expected = (uint16_t)(block[2] | ((uint16_t)block[3] << 8));
    if (!size || !expected ||
        size > LISP65_RUNTIME_OVERLAY_REGION1_CAPACITY)
        return 0u;
    /* The product shelf previously occupied the Bank-5 destination.  Copy
     * only now, after phase 03 has consumed that shelf, from the disjoint
     * durable Attic tenant.  The target CRC below is the publication proof. */
    c2_product_physical_copy(
        LISP65_RUNTIME_OVERLAY_REGION1_SOURCE_BASE,
        ((uint32_t)LISP65_RUNTIME_OVERLAY_REGION1_BANK << 16)
            + LISP65_RUNTIME_OVERLAY_REGION1_ADDRESS,
        size);
    start = c2_kernal_frame_count_inline();
    do {
        crc = LISP65_RUNTIME_OVERLAY_CRC16_INIT;
        offset = 0u;
        left = size;
        while (left) {
            uint8_t i = 0u;
            uint8_t chunk = left > C2_LITE_STAGE_BLOCK
                ? C2_LITE_STAGE_BLOCK : (uint8_t)left;
            c2_facade_vm_code_load(
                LISP65_RUNTIME_OVERLAY_REGION1_BANK,
                (uint16_t)(LISP65_RUNTIME_OVERLAY_REGION1_ADDRESS + offset),
                chunk, block);
            while (i != chunk) {
                uint8_t bits = 8u;
                crc ^= (uint16_t)block[i++] << 8;
                do {
                    crc = (crc & 0x8000u)
                        ? (uint16_t)((crc << 1)
                            ^ LISP65_RUNTIME_OVERLAY_CRC16_POLY)
                        : (uint16_t)(crc << 1);
                } while (--bits);
            }
            offset = (uint16_t)(offset + chunk);
            left = (uint16_t)(left - chunk);
        }
        if (crc == expected) return 1u;
    } while ((uint16_t)(c2_kernal_frame_count_inline() - start) <
             LISP65_RTOV_COMPLETION_TIMEOUT_FRAMES);
    return 0u;
}
#define C2_LITE_STAGE_SESSION_OVERFLOW(family_value) \
    ((family_value) != LISP65_RUNTIME_OVERLAY_FAMILY_SESSION || \
     c2_lite_stage_session_overflow())
#else
#define C2_LITE_STAGE_SESSION_OVERFLOW(family_value) 1u
#endif

#define C2_LITE_STAGE_BODY(name, section_name, family_value, source_value) \
__attribute__((noinline, used, section(section_name)))                    \
static vm_runtime_overlay_status name(uint16_t generation) {             \
    const volatile c2_lite_family_stage_binding *binding =                \
        &rtov_family_stage_bindings[(family_value) - 1u];                 \
    uint8_t block[C2_LITE_STAGE_BLOCK];                                   \
    uint16_t size = binding->image_size;                                  \
    uint16_t expected = binding->crc16;                                   \
    uint16_t start, offset, left, crc;                                    \
    vm_runtime_overlay_status error =                                    \
        VM_RUNTIME_OVERLAY_ERR_FAMILY_STAGE;                              \
    /* The two entry edges deliberately require opposite transport states: \
     * Boot is an external pre-family record; Session is the final loaded   \
     * Boot-family slice. */                                               \
    if (((family_value) == LISP65_RUNTIME_OVERLAY_FAMILY_BOOT && rtov_busy)\
        || ((family_value) == LISP65_RUNTIME_OVERLAY_FAMILY_SESSION        \
            && !rtov_busy))                                               \
        return VM_RUNTIME_OVERLAY_ERR_BUSY;                               \
    if (rtov_fault) return VM_RUNTIME_OVERLAY_ERR_LATCHED;                \
    if (((family_value) == LISP65_RUNTIME_OVERLAY_FAMILY_BOOT             \
         && (generation                                                  \
             || rtov_family != LISP65_RUNTIME_OVERLAY_FAMILY_INACTIVE))   \
        || ((family_value) == LISP65_RUNTIME_OVERLAY_FAMILY_SESSION       \
            && (!generation                                              \
                || rtov_family != LISP65_RUNTIME_OVERLAY_FAMILY_BOOT)))   \
        goto failed;                                                      \
    /* Generation invalidation is the first state change and precedes every\
     * byte of the replacement family. */                                 \
    rtov_family = (uint8_t)((family_value) | RTOV_FAMILY_STAGING);        \
    rtov_family_generation = generation;                                 \
    if (!size || !expected) goto failed;                                 \
    c2_product_physical_copy((source_value), C2_LITE_BANK3_PHYSICAL, size);\
    start = c2_kernal_frame_count_inline();                               \
    do {                                                                  \
        crc = LISP65_RUNTIME_OVERLAY_CRC16_INIT;                          \
        offset = 0u; left = size;                                         \
        while (left) {                                                    \
            uint8_t i = 0u;                                               \
            uint8_t chunk = left > C2_LITE_STAGE_BLOCK                    \
                ? C2_LITE_STAGE_BLOCK : (uint8_t)left;                    \
            c2_facade_vm_code_load(3u, offset, chunk, block);             \
            while (i != chunk) {                                         \
                uint8_t bits = 8u;                                       \
                crc ^= (uint16_t)block[i++] << 8;                         \
                do {                                                      \
                    crc = (crc & 0x8000u)                                 \
                        ? (uint16_t)((crc << 1) ^                          \
                          LISP65_RUNTIME_OVERLAY_CRC16_POLY)              \
                        : (uint16_t)(crc << 1);                            \
                } while (--bits);                                        \
            }                                                             \
            offset = (uint16_t)(offset + chunk);                          \
            left = (uint16_t)(left - chunk);                              \
        }                                                                 \
        if (crc == expected) {                                            \
            if (rtov_family                                               \
                    != (uint8_t)((family_value) | RTOV_FAMILY_STAGING)    \
                || rtov_family_generation != generation)                 \
                goto failed;                                              \
            if (!C2_LITE_STAGE_SESSION_OVERFLOW(family_value))             \
                goto failed;                                              \
            rtov_family = (uint8_t)((family_value) | RTOV_FAMILY_VERIFIED);\
            return VM_RUNTIME_OVERLAY_OK;                                 \
        }                                                                 \
    } while ((uint16_t)(c2_kernal_frame_count_inline() - start) <         \
             LISP65_RTOV_COMPLETION_TIMEOUT_FRAMES);                      \
failed:                                                                   \
    rtov_family = LISP65_RUNTIME_OVERLAY_FAMILY_INACTIVE;                 \
    rtov_family_generation = 0u;                                         \
    rtov_fault = (uint8_t)error;                                         \
    return error;                                                         \
}

C2_LITE_STAGE_BODY(c2_lite_stage_boot_family_impl,
                   ".lisp65_boot_bank3_stage",
                   LISP65_RUNTIME_OVERLAY_FAMILY_BOOT,
                   LISP65_RUNTIME_OVERLAY_BOOT_STORAGE_BASE)

C2_LITE_STAGE_BODY(c2_lite_stage_session_family_impl,
                   ".lisp65_rt_bank3_stage_session",
                   LISP65_RUNTIME_OVERLAY_FAMILY_SESSION,
                   LISP65_RUNTIME_OVERLAY_STORAGE_BASE)

__attribute__((noinline, used, section(".lisp65_boot_bank3_stage")))
vm_runtime_overlay_status c2_lite_stage_boot_family(void) {
    return c2_lite_stage_boot_family_impl(0u);
}

__attribute__((noinline, used, section(".lisp65_rt_bank3_stage_session")))
uint8_t c2_lite_stage_session_family(void *opaque) {
    c2_stream_context *stream = (c2_stream_context *)opaque;
    if (!stream || !stream->generation) return C2_STREAM_ERR_STATE;
    if (c2_lite_stage_session_family_impl(stream->generation)
        != VM_RUNTIME_OVERLAY_OK) {
        stream->error = C2_STREAM_ERR_FAMILY_STAGE;
        return C2_STREAM_ERR_FAMILY_STAGE;
    }
    return C2_STREAM_OK;
}

#undef C2_LITE_STAGE_BODY
#endif

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

#ifdef LISP65_RTOV_CRC_CONVERGENCE
static RTOV_CATALOGFN uint16_t rtov_c_crc_virtual_zero(
        const volatile uint8_t *bytes, uint8_t length, uint8_t zero_offset) {
    uint16_t crc = LISP65_RUNTIME_OVERLAY_CRC16_INIT;
    uint8_t index = 0;
    do {
        uint8_t value = (index == zero_offset ||
                         index == (uint8_t)(zero_offset + 1u))
                          ? 0u : bytes[index];
        crc = rtov_c_crc_byte(crc, value);
    } while (++index != length);
    return crc;
}
#endif

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

#ifdef LISP65_RTOV_CRC_CONVERGENCE
    {
        uint16_t start = rtov_frame_now_inline();
        do {
            context->read(0, record, sizeof context->buffer);
            directory_crc = rtov_c_u16(record + 26);
            if (rtov_c_crc_virtual_zero(
                    record, sizeof context->buffer, 26u) == directory_crc)
                break;
            if (rtov_completion_expired_inline(start))
                return VM_RUNTIME_OVERLAY_ERR_COMPLETION_TIMEOUT;
        } while (1);
    }
#else
    context->read(0, record, sizeof context->buffer);
    directory_crc = rtov_c_u16(record + 26);
    record[26] = record[27] = 0;
    if (rtov_crc_mem(record, sizeof context->buffer) != directory_crc)
        return VM_RUNTIME_OVERLAY_ERR_CRC;
#endif
    if (record[0] != LISP65_RUNTIME_OVERLAY_MAGIC_0 ||
        record[1] != LISP65_RUNTIME_OVERLAY_MAGIC_1 ||
        record[2] != LISP65_RUNTIME_OVERLAY_MAGIC_2 ||
        record[3] != LISP65_RUNTIME_OVERLAY_MAGIC_3)
        return VM_RUNTIME_OVERLAY_ERR_MAGIC;
    if (record[4] != LISP65_RUNTIME_OVERLAY_FORMAT_VERSION)
        return VM_RUNTIME_OVERLAY_ERR_VERSION;
    count = record[7];
    context->count = count;
    if (record[5] != LISP65_RUNTIME_OVERLAY_HEADER_SIZE ||
        record[6] != LISP65_RUNTIME_OVERLAY_ENTRY_SIZE ||
        !count || count > LISP65_RUNTIME_OVERLAY_HARD_MAX_SLICES ||
        record[8] || record[9] ||
        record[10] != LISP65_RUNTIME_OVERLAY_FORMAT_BANK_TAG || record[11] ||
        rtov_c_u16(record + 16) != LISP65_RUNTIME_OVERLAY_HEADER_SIZE)
        return VM_RUNTIME_OVERLAY_ERR_HEADER;
#if LISP65_RUNTIME_OVERLAY_FORMAT_VERSION == 4u
    end = rtov_c_u16(record + 28);
    directory_crc = rtov_c_u16(record + 30);
    if (end > LISP65_RUNTIME_OVERLAY_REGION1_CAPACITY ||
        ((!end) != (!directory_crc)))
        return VM_RUNTIME_OVERLAY_ERR_HEADER;
#else
    if (record[28] || record[29] || record[30] || record[31])
        return VM_RUNTIME_OVERLAY_ERR_HEADER;
#endif
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
#ifdef LISP65_RTOV_CRC_CONVERGENCE
    {
        uint16_t start = rtov_frame_now_inline();
        do {
            if (rtov_c_crc_ext(
                    context, LISP65_RUNTIME_OVERLAY_HEADER_SIZE,
                    (uint16_t)count * LISP65_RUNTIME_OVERLAY_ENTRY_SIZE) ==
                directory_crc)
                break;
            if (rtov_completion_expired_inline(start))
                return VM_RUNTIME_OVERLAY_ERR_COMPLETION_TIMEOUT;
        } while (1);
    }
#else
    if (rtov_c_crc_ext(context, LISP65_RUNTIME_OVERLAY_HEADER_SIZE,
                       (uint16_t)count * LISP65_RUNTIME_OVERLAY_ENTRY_SIZE) !=
        directory_crc)
        return VM_RUNTIME_OVERLAY_ERR_CRC;
#endif
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

#ifdef LISP65_RTOV_CRC_CONVERGENCE
static RTOV_RECORDFN uint16_t rtov_r_crc_byte(
        uint16_t crc, uint8_t value) {
    uint8_t bits = 8;
    crc ^= (uint16_t)value << 8;
    do {
        crc = (crc & 0x8000u)
                ? (uint16_t)((crc << 1) ^ LISP65_RUNTIME_OVERLAY_CRC16_POLY)
                : (uint16_t)(crc << 1);
    } while (--bits);
    return crc;
}

static RTOV_RECORDFN uint16_t rtov_r_crc_virtual_zero(
        const volatile uint8_t *bytes, uint8_t length, uint8_t zero_offset) {
    uint16_t crc = LISP65_RUNTIME_OVERLAY_CRC16_INIT;
    uint8_t index = 0;
    do {
        uint8_t value = (index == zero_offset ||
                         index == (uint8_t)(zero_offset + 1u))
                          ? 0u : bytes[index];
        crc = rtov_r_crc_byte(crc, value);
    } while (++index != length);
    return crc;
}

static RTOV_RECORDFN vm_runtime_overlay_status rtov_r_record_converge(
        const volatile uint8_t *record) {
    uint16_t start = rtov_frame_now_inline();
    do {
        uint16_t expected = (uint16_t)record[22] |
                            ((uint16_t)record[23] << 8);
        if (expected && rtov_r_crc_virtual_zero(
                record, LISP65_RUNTIME_OVERLAY_ENTRY_SIZE, 22u) == expected)
            return VM_RUNTIME_OVERLAY_OK;
    } while (!rtov_completion_expired_inline(start));
    return VM_RUNTIME_OVERLAY_ERR_COMPLETION_TIMEOUT;
}
#endif

/* Called only after slot 0 integrity-checked the immutable header and directory. */
RTOV_RECORDFN uint8_t vm_runtime_overlay_record_verifier(void *opaque) {
    rtov_verify_context *context = (rtov_verify_context *)opaque;
    uint8_t *record = context->buffer;
    uint16_t execution_limit, size_limit;
#if LISP65_RUNTIME_OVERLAY_FORMAT_VERSION == 4u
    uint8_t source_bank, source_megabyte;
#else
    uint16_t end;
#endif

    context->read((uint16_t)(LISP65_RUNTIME_OVERLAY_HEADER_SIZE +
                             (uint16_t)context->slot *
                             LISP65_RUNTIME_OVERLAY_ENTRY_SIZE),
                  record, sizeof context->buffer);
#if LISP65_RUNTIME_OVERLAY_FORMAT_VERSION == 3u || \
    LISP65_RUNTIME_OVERLAY_FORMAT_VERSION == 4u
#ifdef LISP65_RTOV_CRC_CONVERGENCE
    if (rtov_r_record_converge(record) != VM_RUNTIME_OVERLAY_OK)
        return VM_RUNTIME_OVERLAY_ERR_COMPLETION_TIMEOUT;
#else
#error "L65R-v3 record reads require CRC convergence"
#endif
#endif
    context->flags = rtov_r_u16(record + 2);
#if LISP65_RUNTIME_OVERLAY_FORMAT_VERSION >= 2u
    /* DATA_ONLY has exactly one decoder and one lifetime: the boot installer
     * slice.  Public/session execution rejects it before payload transfer. */
    if (context->flags & LISP65_RUNTIME_OVERLAY_FLAG_DATA_ONLY)
        return VM_RUNTIME_OVERLAY_ERR_ENTRY;
#endif
#if LISP65_RUNTIME_OVERLAY_FORMAT_VERSION == 4u
    source_bank = record[25];
    source_megabyte = record[26];
#endif
    if (rtov_r_u16(record) != context->slot ||
        (context->flags != LISP65_RUNTIME_OVERLAY_FLAG_BOOT &&
         context->flags != (LISP65_RUNTIME_OVERLAY_FLAG_RUNTIME |
                            LISP65_RUNTIME_OVERLAY_FLAG_REUSABLE)) ||
#ifdef LISP65_RUNTIME_OVERLAY_LIFETIME_FAMILIES
        (context->flags == LISP65_RUNTIME_OVERLAY_FLAG_BOOT &&
         rtov_family != LISP65_RUNTIME_OVERLAY_FAMILY_BOOT) ||
#endif
#if LISP65_RUNTIME_OVERLAY_FORMAT_VERSION == 4u
        record[27] ||
#else
        record[24] || record[25] || record[26] || record[27] ||
#endif
        record[28] || record[29] || record[30] || record[31])
        return VM_RUNTIME_OVERLAY_ERR_DIRECTORY;
    if (!rtov_r_build_id(record + 16)) return VM_RUNTIME_OVERLAY_ERR_PROFILE;
    if (rtov_r_u16(record + 8) != RTOV_VMA)
        return VM_RUNTIME_OVERLAY_ERR_VMA;
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
#if LISP65_RUNTIME_OVERLAY_FORMAT_VERSION < 3u
        rtov_r_u16(record + 22) ||
#endif
        (context->file_off & 255u))
        return VM_RUNTIME_OVERLAY_ERR_LENGTH;
#if LISP65_RUNTIME_OVERLAY_FORMAT_VERSION == 4u
    /* The canonical emitter validates region-qualified source bounds, then
     * the cold family stage proves the complete target image CRC before
     * publication.  Record CRC convergence binds these exact bytes at use.
     * Repeating the same region decision here cost 78 bytes in the per-record
     * verifier and created a second proof.  The hot path therefore consumes
     * only the already authenticated absolute source tuple. */
#else
    end = (uint16_t)(context->file_off + context->file_len);
    if (context->file_off < context->payload_off ||
        (end < context->file_off && end != 0) ||
        (context->image_limit &&
         (end < context->file_off || end > context->image_limit)))
        return VM_RUNTIME_OVERLAY_ERR_LENGTH;
#endif

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
#if LISP65_RUNTIME_OVERLAY_FORMAT_VERSION == 4u
    /* L65R-v4 turns the authenticated record tuple into the DMA-native
     * installer frame.  This is a representation change inside the sealed
     * domain, so it must be complete before the producer signs or publishes
     * the frame.  The original installer identity remains available in the
     * CRC-bound record and is consumed from there below. */
    context->slot = source_bank;
    context->count = source_megabyte;
#endif
#if LISP65_RUNTIME_OVERLAY_FORMAT_VERSION >= 2u
    /* The Boot installer record verifier is the producer boundary for the one
     * direct installer frame.  Family and generation are already qualified by
     * vm_runtime_overlay_exec_family at the caller seam; keep only the
     * record-local family cross-check here.  For v4 the record, rather than
     * the transformed slot byte, retains that identity.  Seal the complete
     * final frame and publish its pointer through the one existing
     * installation seam; the resident dispatcher stays format-neutral. */
    if (rtov_family == LISP65_RUNTIME_OVERLAY_FAMILY_BOOT &&
#if LISP65_RUNTIME_OVERLAY_FORMAT_VERSION == 4u
        rtov_r_u16(record) == LISP65_RUNTIME_ISLAND_INSTALL_SLOT) {
#else
        context->slot == LISP65_RUNTIME_ISLAND_INSTALL_SLOT) {
#endif
        if (context->flags != LISP65_RUNTIME_OVERLAY_FLAG_BOOT ||
            rtov_island_state != RTOV_ISLAND_INSTALLING)
            return VM_RUNTIME_OVERLAY_ERR_ENTRY;
        context->seal = rtov_crc_mem(
            (const uint8_t *)context, offsetof(rtov_verify_context, seal));
        RTOV_INSTALL_CONTEXT = context;
    }
#endif
    return VM_RUNTIME_OVERLAY_OK;
}

/* Keep both generated verifier tuples on one value-independent code path. */
static vm_runtime_overlay_status rtov_run_verifier(
    uint16_t file_off, uint16_t file_len, uint16_t entry_off, uint16_t crc,
    rtov_verify_context *context) {
    vm_runtime_overlay_status status;
#if defined(LISP65_C2_ISLAND_DIAGNOSTIC_CRC_LATCH_DOUBLE) || \
    defined(LISP65_C2_ISLAND_DIAGNOSTIC_CRC_LATCH_SINGLE)
    uint16_t observed_crc;
#endif

    rtov_loaded_len = file_len;
    rtov_read(file_off, (uint8_t *)RTOV_TARGET, file_len);
#ifdef LISP65_RTOV_CRC_CONVERGENCE
    status = rtov_crc_converge(
        (const uint8_t *)RTOV_TARGET, file_len, crc);
    if (status != VM_RUNTIME_OVERLAY_OK) return status;
#elif defined(LISP65_C2_ISLAND_DIAGNOSTIC_CRC_LATCH_DOUBLE)
    /* Diagnostic-only timing witness: preserve the first CRC and then repeat
     * the same read immediately.  The two existing context/result words are
     * lifetime-dead on this fail-closed edge, so the probe adds no state. */
    observed_crc = rtov_crc_mem((const uint8_t *)RTOV_TARGET, file_len);
    if (observed_crc != crc) {
        ((volatile uint8_t *)&rtov_call_context)[0] =
            (uint8_t)observed_crc;
        ((volatile uint8_t *)&rtov_call_context)[1] =
            (uint8_t)(observed_crc >> 8);
        observed_crc = rtov_crc_mem((const uint8_t *)RTOV_TARGET, file_len);
        ((volatile uint8_t *)&rtov_call_result)[0] =
            (uint8_t)observed_crc;
        ((volatile uint8_t *)&rtov_call_result)[1] =
            (uint8_t)(observed_crc >> 8);
        return VM_RUNTIME_OVERLAY_ERR_CRC;
    }
#elif defined(LISP65_C2_ISLAND_DIAGNOSTIC_CRC_LATCH_SINGLE)
    /* Capacity fallback: preserve only the first observed CRC in the same
     * lifetime-dead context word.  The expected value remains manifest-bound. */
    observed_crc = rtov_crc_mem((const uint8_t *)RTOV_TARGET, file_len);
    if (observed_crc != crc) {
        ((volatile uint8_t *)&rtov_call_context)[0] =
            (uint8_t)observed_crc;
        ((volatile uint8_t *)&rtov_call_context)[1] =
            (uint8_t)(observed_crc >> 8);
        return VM_RUNTIME_OVERLAY_ERR_CRC;
    }
#else
    if (rtov_crc_mem((const uint8_t *)RTOV_TARGET, file_len) != crc)
        return VM_RUNTIME_OVERLAY_ERR_CRC;
#endif
    status = (vm_runtime_overlay_status)RTOV_CALL(
        (uint16_t)(RTOV_VMA + entry_off), context);
    if (!rtov_wipe()) return VM_RUNTIME_OVERLAY_ERR_WIPE;
    return status;
}

vm_runtime_overlay_status vm_runtime_overlay_exec_family(
    uint8_t expected_family, uint16_t expected_generation,
    uint8_t slot, void *context,
    uint8_t *entry_result) {
    rtov_verify_context verify;
    vm_runtime_overlay_status status;
    const volatile rtov_verifier_tuple *verifier;
    uint16_t entry;
    uint8_t verifier_index;

    if (entry_result) *entry_result = LISP65_RUNTIME_OVERLAY_ENTRY_NOT_RUN;
#ifdef LISP65_RUNTIME_OVERLAY_LIFETIME_FAMILIES
    if ((expected_family != LISP65_RUNTIME_OVERLAY_FAMILY_BOOT
         && expected_family != LISP65_RUNTIME_OVERLAY_FAMILY_SESSION)
        || expected_family != rtov_family
        || expected_generation != rtov_family_generation)
        return VM_RUNTIME_OVERLAY_ERR_FAMILY;
#else
    (void)expected_family;
    (void)expected_generation;
#endif
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
#ifdef LISP65_RUNTIME_OVERLAY_TRANSACTION_AUTH
#ifdef LISP65_RUNTIME_OVERLAY_TRANSACTION_AUTH_ISLAND
    verifier_index = rtov_transaction_context_if_ready(&verify, 0u);
    if (verifier_index == 0xfeu)
        return rtov_fail(VM_RUNTIME_OVERLAY_ERR_ISLAND_NOT_READY);
    if (verifier_index == 0xffu)
        return rtov_fail(VM_RUNTIME_OVERLAY_ERR_SLOT);
#else
    if (RTOV_TRANSACTION_ACTIVE() && RTOV_TRANSACTION_TRUSTED()) {
        if (slot < LISP65_RUNTIME_OVERLAY_APPLICATION_SLOT_BASE
            || slot >= rtov_transaction_count)
            return rtov_fail(VM_RUNTIME_OVERLAY_ERR_SLOT);
        verify.payload_off = rtov_transaction_payload_off;
        verify.image_limit = rtov_transaction_image_limit;
        verify.count = rtov_transaction_count;
        verifier_index = 1;
    }
#endif
#endif
    do {
#ifdef LISP65_RUNTIME_OVERLAY_LIFETIME_FAMILIES
        verifier = (rtov_family == LISP65_RUNTIME_OVERLAY_FAMILY_BOOT
                    ? rtov_boot_verifiers : rtov_verifiers) + verifier_index;
#else
        verifier = rtov_verifiers + verifier_index;
#endif
        status = rtov_run_verifier(verifier->file_off, verifier->file_len,
                                   verifier->entry_off, verifier->crc, &verify);
        if (status != VM_RUNTIME_OVERLAY_OK) {
#ifdef LISP65_C2_ISLAND_DIAGNOSTIC_LATCH
            /* Diagnostic builds preserve the first verifier failure before
             * rtov_fail wipes the execution window and the outer Island
             * installer deliberately maps the transport to generic E2f.
             * Reuse the lifetime-exclusive context/result tuple: after this
             * fail-closed return it has no callable meaning, so no state byte
             * or product-facing error contract is added.  A nonzero saved
             * length means the tuple payload CRC failed before its verifier
             * ran; zero means the named verifier returned the saved status. */
            ((volatile uint8_t *)&rtov_call_context)[0] = verifier_index;
            ((volatile uint8_t *)&rtov_call_context)[1] = (uint8_t)status;
            ((volatile uint8_t *)&rtov_call_result)[0] =
                (uint8_t)rtov_loaded_len;
            ((volatile uint8_t *)&rtov_call_result)[1] =
                (uint8_t)(rtov_loaded_len >> 8);
#endif
            return rtov_fail(status);
        }
#ifdef LISP65_RUNTIME_OVERLAY_TRANSACTION_AUTH
#ifdef LISP65_RUNTIME_OVERLAY_TRANSACTION_AUTH_ISLAND
        if (verifier_index == 0) {
            uint8_t publish = rtov_transaction_context_if_ready(&verify, 1u);
            if (publish == 0xfeu)
                return rtov_fail(VM_RUNTIME_OVERLAY_ERR_ISLAND_NOT_READY);
        }
#else
        if (RTOV_TRANSACTION_ACTIVE() && verifier_index == 0) {
            rtov_transaction_payload_off = verify.payload_off;
            rtov_transaction_image_limit = verify.image_limit;
            rtov_transaction_count = verify.count;
            rtov_transaction_trusted = 1;
        }
#endif
#endif
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
#if LISP65_RUNTIME_OVERLAY_FORMAT_VERSION == 4u
    rtov_read_source(
        verify.file_off,
        (uint16_t)verify.slot | ((uint16_t)verify.count << 8),
        (uint8_t *)RTOV_TARGET, rtov_loaded_len);
#else
    rtov_read(verify.file_off, (uint8_t *)RTOV_TARGET, rtov_loaded_len);
#endif
#ifdef LISP65_RTOV_CRC_CONVERGENCE
    status = rtov_crc_converge(
        (const uint8_t *)RTOV_TARGET, rtov_loaded_len, verify.payload_crc);
    if (status != VM_RUNTIME_OVERLAY_OK) return rtov_fail(status);
#else
    if (rtov_crc_mem((const uint8_t *)RTOV_TARGET, rtov_loaded_len) !=
        verify.payload_crc)
        return rtov_fail(VM_RUNTIME_OVERLAY_ERR_CRC);
#endif
    *entry_result = RTOV_CALL(entry, context);
    if (!rtov_wipe()) return rtov_fail(VM_RUNTIME_OVERLAY_ERR_WIPE);
    rtov_busy = 0;
    return VM_RUNTIME_OVERLAY_OK;
}

vm_runtime_overlay_status vm_runtime_overlay_exec(
    uint8_t slot, void *context, uint8_t *entry_result) {
#ifdef LISP65_RUNTIME_OVERLAY_LIFETIME_FAMILIES
    return vm_runtime_overlay_exec_family(
        rtov_family, rtov_family_generation, slot, context, entry_result);
#else
    return vm_runtime_overlay_exec_family(
        LISP65_RUNTIME_OVERLAY_FAMILY_SESSION, 0u,
        slot, context, entry_result);
#endif
}

#ifdef LISP65_RUNTIME_OVERLAY_TRANSACTION_AUTH
LISP65_C2_REOPEN_GAP0_FN
vm_runtime_overlay_status vm_runtime_overlay_transaction_begin(
    uint8_t expected_family, uint16_t expected_generation) {
    if (rtov_busy || rtov_repeat || RTOV_TRANSACTION_ACTIVE())
        return VM_RUNTIME_OVERLAY_ERR_BUSY;
    if (rtov_fault) return VM_RUNTIME_OVERLAY_ERR_LATCHED;
#ifdef LISP65_RUNTIME_OVERLAY_LIFETIME_FAMILIES
    if (expected_family != LISP65_RUNTIME_OVERLAY_FAMILY_SESSION
        || expected_family != rtov_family
        || !expected_generation
        || expected_generation != rtov_family_generation)
        return VM_RUNTIME_OVERLAY_ERR_FAMILY;
#else
    if (expected_family != LISP65_RUNTIME_OVERLAY_FAMILY_SESSION
        || expected_generation)
        return VM_RUNTIME_OVERLAY_ERR_FAMILY;
#endif
#ifdef LISP65_RUNTIME_OVERLAY_TRANSACTION_AUTH_ISLAND
    rtov_transaction_payload_off = 0;
    rtov_transaction_image_limit = 0;
    rtov_transaction_count = RTOV_TRANSACTION_UNTRUSTED;
#else
    rtov_transaction_payload_off = 0;
    rtov_transaction_image_limit = 0;
    rtov_transaction_count = 0;
    rtov_transaction_trusted = 0;
    rtov_transaction_active = 1;
#endif
    return VM_RUNTIME_OVERLAY_OK;
}

LISP65_C2_REOPEN_GAP2_FN
vm_runtime_overlay_status vm_runtime_overlay_transaction_end(void) {
    vm_runtime_overlay_status status;
    if (!RTOV_TRANSACTION_ACTIVE())
        return rtov_fault ? VM_RUNTIME_OVERLAY_ERR_LATCHED
                          : VM_RUNTIME_OVERLAY_ERR_ARGUMENT;
    status = RTOV_TRANSACTION_TRUSTED() ? VM_RUNTIME_OVERLAY_OK
                                       : VM_RUNTIME_OVERLAY_ERR_HEADER;
    rtov_transaction_invalidate();
    return status;
}
#endif

vm_runtime_overlay_status vm_runtime_overlay_select_family(
    uint8_t family, uint16_t generation) {
#ifdef LISP65_RUNTIME_OVERLAY_LIFETIME_FAMILIES
#ifdef LISP65_RUNTIME_OVERLAY_TRANSACTION_AUTH
    if (RTOV_TRANSACTION_ACTIVE())
        return rtov_fail(VM_RUNTIME_OVERLAY_ERR_BUSY);
#endif
    if (rtov_busy) return VM_RUNTIME_OVERLAY_ERR_BUSY;
    if (rtov_fault) return VM_RUNTIME_OVERLAY_ERR_LATCHED;
#ifdef LISP65_C2_LITE_BANK3_STAGING
    if ((family != LISP65_RUNTIME_OVERLAY_FAMILY_BOOT
         && family != LISP65_RUNTIME_OVERLAY_FAMILY_SESSION)
        || rtov_family != (uint8_t)(family | RTOV_FAMILY_VERIFIED)
        || rtov_family_generation != generation)
        return rtov_fail(VM_RUNTIME_OVERLAY_ERR_FAMILY_STAGE);
#else
    if ((family == LISP65_RUNTIME_OVERLAY_FAMILY_BOOT && generation)
        || (family == LISP65_RUNTIME_OVERLAY_FAMILY_BOOT
            && rtov_family != LISP65_RUNTIME_OVERLAY_FAMILY_INACTIVE)
        || (family == LISP65_RUNTIME_OVERLAY_FAMILY_SESSION
            && (!generation
                || rtov_family != LISP65_RUNTIME_OVERLAY_FAMILY_BOOT)))
        return VM_RUNTIME_OVERLAY_ERR_FAMILY;
    if (family != LISP65_RUNTIME_OVERLAY_FAMILY_BOOT
        && family != LISP65_RUNTIME_OVERLAY_FAMILY_SESSION)
        return VM_RUNTIME_OVERLAY_ERR_FAMILY;
#endif
    if (!rtov_wipe()) return rtov_fail(VM_RUNTIME_OVERLAY_ERR_WIPE);
    rtov_family = family;
    rtov_family_generation = generation;
    return VM_RUNTIME_OVERLAY_OK;
#else
    (void)generation;
    return family == LISP65_RUNTIME_OVERLAY_FAMILY_SESSION
        ? VM_RUNTIME_OVERLAY_OK : VM_RUNTIME_OVERLAY_ERR_FAMILY;
#endif
}

#if defined(LISP65_RUNTIME_OVERLAY_LIFETIME_FAMILIES) && \
    defined(LISP65_C2_LITE_BANK3_STAGING)
vm_runtime_overlay_status vm_runtime_overlay_last_status(void) {
    return (vm_runtime_overlay_status)rtov_fault;
}
#endif

uint8_t vm_runtime_overlay_family(void) {
#ifdef LISP65_RUNTIME_OVERLAY_LIFETIME_FAMILIES
    return rtov_family;
#else
    return LISP65_RUNTIME_OVERLAY_FAMILY_SESSION;
#endif
}

__attribute__((noinline))
vm_runtime_overlay_status vm_runtime_overlay_exec_batch(
    uint8_t slot, void *context, uint8_t *entry_result,
    vm_runtime_overlay_batch_policy policy,
    vm_runtime_overlay_repeat_predicate_fn repeat) {
    vm_runtime_overlay_status status;
    uint16_t remaining = 0xffffu;
    uint8_t whitelisted =
        (uint8_t)((policy == VM_RUNTIME_OVERLAY_BATCH_L65M
                   && slot >= 2u && slot <= 22u)
                  || (policy == VM_RUNTIME_OVERLAY_BATCH_COMMIT
                      && slot >= 23u && slot <= 29u)
                  || (policy == VM_RUNTIME_OVERLAY_BATCH_LCC
                      && slot >= 30u && slot <= 32u));
#ifdef LISP65_RUNTIME_OVERLAY_LIFETIME_FAMILIES
    /* Batch-policy slot ranges are Session-family ABI.  The same numeric
     * slots in Boot name unrelated records and receive no batch privilege. */
    if (rtov_family != LISP65_RUNTIME_OVERLAY_FAMILY_SESSION)
        whitelisted = 0;
#endif
#ifdef LISP65_RUNTIME_OVERLAY_TRANSACTION_AUTH_ISLAND
    if (RTOV_TRANSACTION_ACTIVE()) return VM_RUNTIME_OVERLAY_ERR_BUSY;
#endif
    if (!repeat || !whitelisted)
        return vm_runtime_overlay_exec(slot, context, entry_result);
    if (!entry_result)
        return vm_runtime_overlay_exec(slot, context, entry_result);
    *entry_result = LISP65_RUNTIME_OVERLAY_ENTRY_NOT_RUN;
    if (rtov_island_state != RTOV_ISLAND_READY)
        return VM_RUNTIME_OVERLAY_ERR_ISLAND_NOT_READY;
    do {
        /* E000-S1 retires the Island-resident same-payload loop.  Every
         * repetition now traverses the complete authenticated single-record
         * loader, including copy, target CRC and wipe.  This is deliberately
         * slower but preserves the established single-record semantics. */
        status = vm_runtime_overlay_exec(slot, context, entry_result);
        if (status != VM_RUNTIME_OVERLAY_OK) return status;
        if (!repeat(context, slot, *entry_result))
            return VM_RUNTIME_OVERLAY_OK;
    } while (--remaining);
    return rtov_fail(VM_RUNTIME_OVERLAY_ERR_BATCH_LIMIT);
}

#ifdef LISP65_RTOV_FLOOR_BREAK_RETRY_PROBE
/* The serial Island handoff is the second half of the purpose-bound fixed
 * retry-call scaffold.  Its implementation is the named assembler leaf. */
vm_runtime_overlay_status rtov_install_island_finalize(void);
#endif

RTOV_NOINLINE
vm_runtime_overlay_status vm_runtime_overlay_install_island(void) {
#if LISP65_RUNTIME_OVERLAY_FORMAT_VERSION == 1u
    rtov_island_install_context context;
#endif
    vm_runtime_overlay_status transport;
    uint8_t result = LISP65_RUNTIME_OVERLAY_ENTRY_NOT_RUN;
    if (rtov_island_state == RTOV_ISLAND_READY) return VM_RUNTIME_OVERLAY_OK;
    if (rtov_island_state == RTOV_ISLAND_INSTALLING)
        return VM_RUNTIME_OVERLAY_ERR_BUSY;
    if (rtov_island_state == RTOV_ISLAND_FAILED)
        return VM_RUNTIME_OVERLAY_ERR_ISLAND;
    rtov_island_state = RTOV_ISLAND_INSTALLING;
    /* READY is withheld and arbitrary predecessor bytes are removed before
     * either record is trusted. Every later failure therefore leaves a
     * non-callable, zeroed destination rather than stale Island code. */
    memset((uint8_t *)RTOV_ISLAND_TARGET, 0,
           LISP65_RUNTIME_ISLAND_CAPACITY);
#if LISP65_RUNTIME_OVERLAY_FORMAT_VERSION == 1u
    context.status = VM_RUNTIME_ISLAND_ERR_CONTEXT;
    transport = vm_runtime_overlay_exec_family(
        LISP65_RUNTIME_OVERLAY_FAMILY_BOOT, 0,
        LISP65_RUNTIME_ISLAND_INSTALL_SLOT, &context, &result);
#else
    transport = vm_runtime_overlay_exec_family(
        LISP65_RUNTIME_OVERLAY_FAMILY_BOOT, 0,
        LISP65_RUNTIME_ISLAND_INSTALL_SLOT, 0, &result);
#endif
#ifdef LISP65_RTOV_ISLAND_SPLIT_PROBE
    if (transport == VM_RUNTIME_OVERLAY_OK &&
        result == VM_RUNTIME_ISLAND_OK) {
#ifdef LISP65_RTOV_FLOOR_BREAK_RETRY_PROBE
        transport = rtov_install_island_finalize();
        result = rtov_batch_slot_id;
#else
        result = LISP65_RUNTIME_OVERLAY_ENTRY_NOT_RUN;
        transport = vm_runtime_overlay_exec_family(
            LISP65_RUNTIME_OVERLAY_FAMILY_BOOT, 0,
            LISP65_RUNTIME_ISLAND_FINALIZE_SLOT, 0, &result);
#endif
    }
#endif
    if (transport != VM_RUNTIME_OVERLAY_OK
        || result != VM_RUNTIME_ISLAND_OK
#if LISP65_RUNTIME_OVERLAY_FORMAT_VERSION == 1u
        || context.status != VM_RUNTIME_ISLAND_OK) {
#else
        ) {
#endif
        memset((uint8_t *)RTOV_ISLAND_TARGET, 0,
               LISP65_RUNTIME_ISLAND_CAPACITY);
        rtov_island_state = RTOV_ISLAND_FAILED;
        if (transport == VM_RUNTIME_OVERLAY_OK &&
            result == VM_RUNTIME_OVERLAY_ERR_COMPLETION_TIMEOUT)
            return rtov_fail(VM_RUNTIME_OVERLAY_ERR_COMPLETION_TIMEOUT);
        if (transport == VM_RUNTIME_OVERLAY_OK)
            return rtov_fail(VM_RUNTIME_OVERLAY_ERR_ISLAND);
        /* vm_runtime_overlay_exec already latched and returned the innermost
         * transport/verifier status.  Preserve that first failure; the outer
         * Island lifecycle adds FAILED state and destination cleanup, never a
         * replacement generic E2f status. */
        rtov_busy = 0;
        return transport;
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
#ifdef LISP65_RUNTIME_OVERLAY_TRANSACTION_AUTH
    rtov_transaction_invalidate();
#endif
    if (!rtov_wipe()) {
        rtov_fault = VM_RUNTIME_OVERLAY_ERR_WIPE;
        rtov_busy = 0;
        return VM_RUNTIME_OVERLAY_ERR_WIPE;
    }
    rtov_busy = 0;
#ifdef LISP65_C1_COMPILER_TIER
    /* A longjmp bypasses the Lisp retirement call. Reuse the generic abort
     * landing. The island transaction profile cannot reuse batch_slot_id for
     * the result because that byte is its trust discriminator. */
#ifdef LISP65_RUNTIME_OVERLAY_TRANSACTION_AUTH_ISLAND
    {
        uint8_t result;
        return vm_runtime_overlay_exec(
            LISP65_C1_COMPILER_OVERLAY_SLOT, 0, &result);
    }
#else
    return vm_runtime_overlay_exec(
        LISP65_C1_COMPILER_OVERLAY_SLOT, 0, &rtov_batch_slot_id);
#endif
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
#ifdef LISP65_RUNTIME_OVERLAY_TRANSACTION_AUTH
    rtov_transaction_invalidate();
#endif
#ifdef LISP65_RUNTIME_OVERLAY_LIFETIME_FAMILIES
    rtov_family = LISP65_RUNTIME_OVERLAY_FAMILY_INACTIVE;
    rtov_family_generation = 0;
#endif
    rtov_island_copy_fault = 0;
    rtov_island_frame_fault = 0;
    rtov_host_island_length = 0;
    rtov_host_island_crc = 0;
    rtov_transaction_context_calls = 0;
    memset(lisp65_resident_island_host_target, 0,
           LISP65_RUNTIME_ISLAND_CAPACITY);
}

void vm_runtime_overlay_host_force_busy(uint8_t busy) {
    rtov_busy = busy ? 1u : 0u;
}

void vm_runtime_overlay_host_island_copy_fault(uint8_t enabled) {
    rtov_island_copy_fault = enabled;
}

void vm_runtime_overlay_host_island_frame_fault(uint8_t enabled) {
    rtov_island_frame_fault = enabled;
}

void vm_runtime_overlay_host_assume_island_ready(void) {
    rtov_island_state = RTOV_ISLAND_READY;
}

void vm_runtime_overlay_host_force_transaction_untrusted(void) {
#ifdef LISP65_RUNTIME_OVERLAY_TRANSACTION_AUTH_ISLAND
    rtov_repeat = 0;
    rtov_transaction_count = RTOV_TRANSACTION_UNTRUSTED;
#endif
}

uint16_t vm_runtime_overlay_host_transaction_context_calls(void) {
    return rtov_transaction_context_calls;
}

uint8_t vm_runtime_overlay_host_island_matches_image(void) {
#if LISP65_RUNTIME_OVERLAY_FORMAT_VERSION >= 2u
    return rtov_host_island_length != 0 &&
           rtov_host_island_length <= LISP65_RUNTIME_ISLAND_CAPACITY &&
           rtov_crc_mem(lisp65_resident_island_host_target,
                        rtov_host_island_length) == rtov_host_island_crc;
#else
    return memcmp(lisp65_resident_island_host_target, rtov_island_image,
                  LISP65_RESIDENT_ISLAND_LENGTH) == 0;
#endif
}
#endif
#endif /* LISP65_RUNTIME_OVERLAY || LISP65_RUNTIME_OVERLAY_HOST_TEST */
