/* Reusable, fail-closed transport for profile-bound Bank-0 runtime overlays. */
#ifndef LISP65_VM_RUNTIME_OVERLAY_H
#define LISP65_VM_RUNTIME_OVERLAY_H

#include <stdint.h>

#define LISP65_RUNTIME_OVERLAY_MAGIC_0          'L'
#define LISP65_RUNTIME_OVERLAY_MAGIC_1          '6'
#define LISP65_RUNTIME_OVERLAY_MAGIC_2          '5'
#define LISP65_RUNTIME_OVERLAY_MAGIC_3          'R'
#ifndef LISP65_RUNTIME_OVERLAY_CATALOG_VERSION
#define LISP65_RUNTIME_OVERLAY_CATALOG_VERSION  1u
#endif
#define LISP65_RUNTIME_OVERLAY_FORMAT_VERSION   \
    LISP65_RUNTIME_OVERLAY_CATALOG_VERSION
#define LISP65_RUNTIME_OVERLAY_HEADER_SIZE      32u
#define LISP65_RUNTIME_OVERLAY_ENTRY_SIZE       32u
#define LISP65_RUNTIME_OVERLAY_ENTRY_ABI_V1     1u
#define LISP65_RUNTIME_OVERLAY_HARD_MAX_SLICE   1792u
#define LISP65_RUNTIME_OVERLAY_HARD_MAX_VMA     0xc356u
#define LISP65_RUNTIME_OVERLAY_HARD_MAX_BOOT_SLICE 4096u
#define LISP65_RUNTIME_OVERLAY_HARD_MAX_SLICES  64u
#define LISP65_RUNTIME_OVERLAY_ENTRY_NOT_RUN    0xffu
#define LISP65_RUNTIME_OVERLAY_APPLICATION_SLOT_BASE 2u
#ifndef LISP65_RUNTIME_ISLAND_INSTALL_SLOT
#define LISP65_RUNTIME_ISLAND_INSTALL_SLOT      37u
#endif
#if defined(LISP65_RTOV_ISLAND_SPLIT_PROBE)
#ifndef LISP65_RUNTIME_ISLAND_FINALIZE_SLOT
#define LISP65_RUNTIME_ISLAND_FINALIZE_SLOT     \
    (LISP65_RUNTIME_ISLAND_INSTALL_SLOT + 1u)
#endif
#endif
#ifndef LISP65_RUNTIME_ISLAND_CARRIER_SLOT
#if defined(LISP65_RTOV_ISLAND_SPLIT_PROBE)
#define LISP65_RUNTIME_ISLAND_CARRIER_SLOT      \
    (LISP65_RUNTIME_ISLAND_FINALIZE_SLOT + 1u)
#else
#define LISP65_RUNTIME_ISLAND_CARRIER_SLOT      \
    (LISP65_RUNTIME_ISLAND_INSTALL_SLOT + 1u)
#endif
#endif
#define LISP65_RUNTIME_ISLAND_ABI_VERSION       1u
#define LISP65_RUNTIME_ISLAND_COOKIE            0x1841u
#define LISP65_RUNTIME_ISLAND_ADDRESS           0x1800u
#define LISP65_RUNTIME_ISLAND_CAPACITY          2048u

#define LISP65_RUNTIME_OVERLAY_FLAG_BOOT        0x0001u
#define LISP65_RUNTIME_OVERLAY_FLAG_RUNTIME     0x0002u
#define LISP65_RUNTIME_OVERLAY_FLAG_REUSABLE    0x0004u
#define LISP65_RUNTIME_OVERLAY_FLAG_DATA_ONLY   0x0008u
#define LISP65_RUNTIME_OVERLAY_DATA_ENTRY_NONE  0xffffu

#define LISP65_RUNTIME_OVERLAY_FAMILY_INACTIVE  0u
#define LISP65_RUNTIME_OVERLAY_FAMILY_BOOT      1u
#define LISP65_RUNTIME_OVERLAY_FAMILY_SESSION   2u

/* CRC-16/CCITT-FALSE, identical to the boot-overlay transport. */
#define LISP65_RUNTIME_OVERLAY_CRC16_POLY       0x1021u
#define LISP65_RUNTIME_OVERLAY_CRC16_INIT       0xffffu
#define LISP65_RTOV_COMPLETION_TIMEOUT_FRAMES   64u

typedef uint8_t (*vm_runtime_overlay_entry_fn)(void *context);

typedef enum {
    VM_RUNTIME_OVERLAY_BATCH_NONE = 0,
    VM_RUNTIME_OVERLAY_BATCH_L65M,
    VM_RUNTIME_OVERLAY_BATCH_COMMIT,
    VM_RUNTIME_OVERLAY_BATCH_LCC
} vm_runtime_overlay_batch_policy;

typedef uint8_t (*vm_runtime_overlay_repeat_predicate_fn)(
    void *context, uint8_t slot, uint8_t last_entry_result);

#if defined(__mos__) && defined(LISP65_RUNTIME_OVERLAY)
#define LISP65_RESIDENT_ISLAND_FN \
    __attribute__((section(".lisp65_resident_island"), noinline, used))
#else
#define LISP65_RESIDENT_ISLAND_FN __attribute__((noinline))
#endif

/* The one-time Link-33 E000 reopening has three explicit packing holes.  The
 * ordinary build keeps the historical Island placement; only the authorized
 * Whole-Program probe opts into these named post-ownership homes. */
#if defined(__mos__) && defined(LISP65_C2_E000_REOPEN)
#define LISP65_C2_REOPEN_GAP0_FN \
    __attribute__((section(".lisp65_c2_kernal_window.reopen_gap0"), noinline, used))
#define LISP65_C2_REOPEN_GAP1_FN \
    __attribute__((section(".lisp65_c2_kernal_window.reopen_gap1"), noinline, used))
#define LISP65_C2_REOPEN_GAP2_FN \
    __attribute__((section(".lisp65_c2_kernal_window.reopen_gap2"), noinline, used))
#define LISP65_C2_REOPEN_TEXT_GAP1_FN LISP65_C2_REOPEN_GAP1_FN
#define LISP65_C2_REOPEN_TEXT_GAP2_FN LISP65_C2_REOPEN_GAP2_FN
#else
#define LISP65_C2_REOPEN_GAP0_FN LISP65_RESIDENT_ISLAND_FN
#define LISP65_C2_REOPEN_GAP1_FN LISP65_RESIDENT_ISLAND_FN
#define LISP65_C2_REOPEN_GAP2_FN LISP65_RESIDENT_ISLAND_FN
#define LISP65_C2_REOPEN_TEXT_GAP1_FN __attribute__((noinline))
#define LISP65_C2_REOPEN_TEXT_GAP2_FN __attribute__((noinline, used))
#endif

typedef enum {
    VM_RUNTIME_OVERLAY_OK = 0,
    VM_RUNTIME_OVERLAY_ERR_ARGUMENT,
    VM_RUNTIME_OVERLAY_ERR_LATCHED,
    VM_RUNTIME_OVERLAY_ERR_BUSY,
    VM_RUNTIME_OVERLAY_ERR_MAGIC,
    VM_RUNTIME_OVERLAY_ERR_VERSION,
    VM_RUNTIME_OVERLAY_ERR_HEADER,
    VM_RUNTIME_OVERLAY_ERR_PROFILE,
    VM_RUNTIME_OVERLAY_ERR_DIRECTORY,
    VM_RUNTIME_OVERLAY_ERR_SLOT,
    VM_RUNTIME_OVERLAY_ERR_VMA,
    VM_RUNTIME_OVERLAY_ERR_ENTRY,
    VM_RUNTIME_OVERLAY_ERR_LENGTH,
    VM_RUNTIME_OVERLAY_ERR_ABI,
    VM_RUNTIME_OVERLAY_ERR_STACK,
    VM_RUNTIME_OVERLAY_ERR_CRC,
    VM_RUNTIME_OVERLAY_ERR_WIPE,
    VM_RUNTIME_OVERLAY_ERR_ABORTED,
    VM_RUNTIME_OVERLAY_ERR_BATCH_LIMIT,
    VM_RUNTIME_OVERLAY_ERR_ISLAND_NOT_READY,
    VM_RUNTIME_OVERLAY_ERR_ISLAND,
    VM_RUNTIME_OVERLAY_ERR_FAMILY,
    VM_RUNTIME_OVERLAY_ERR_COMPLETION_TIMEOUT,
    VM_RUNTIME_OVERLAY_ERR_FAMILY_STAGE
} vm_runtime_overlay_status;

typedef enum {
    VM_RUNTIME_ISLAND_OK = 0,
    VM_RUNTIME_ISLAND_ERR_CONTEXT,
    VM_RUNTIME_ISLAND_ERR_ABI,
    VM_RUNTIME_ISLAND_ERR_COOKIE,
    VM_RUNTIME_ISLAND_ERR_BINDING,
    VM_RUNTIME_ISLAND_ERR_CRC
} vm_runtime_island_status;

#if defined(LISP65_RUNTIME_OVERLAY) || defined(LISP65_RUNTIME_OVERLAY_HOST_TEST)
/* Transport success is independent of the byte returned by the loaded entry. */
vm_runtime_overlay_status vm_runtime_overlay_exec(
    uint8_t slot, void *context, uint8_t *entry_result);

/* C2 lifetime substitution names the expected family at every phase call.
 * A mismatch is rejected before a catalog or payload byte is read. */
vm_runtime_overlay_status vm_runtime_overlay_exec_family(
    uint8_t expected_family, uint16_t expected_generation,
    uint8_t slot, void *context,
    uint8_t *entry_result);

/* BOOT requires generation zero; SESSION requires a nonzero generation and a
 * preceding BOOT family.  Each family execution also matches this latch. */
vm_runtime_overlay_status vm_runtime_overlay_select_family(
    uint8_t family, uint16_t generation);
uint8_t vm_runtime_overlay_family(void);

#ifdef LISP65_C2_LITE_BANK3_STAGING
/* A family is not executable merely because bytes occupy Bank 3.  The cold
 * stage records own invalidation, copy, verification and failure locally.
 * Only the family/generation latch and this diagnostic accessor remain
 * resident; there is no resident transition API to inline into callers. */
vm_runtime_overlay_status vm_runtime_overlay_last_status(void);
#endif

#ifdef LISP65_RUNTIME_OVERLAY_TRANSACTION_AUTH
/* Authenticate immutable family/catalog evidence once per bounded append
 * transaction. Record bounds, payload CRC and wiping remain per slice. */
LISP65_C2_REOPEN_GAP0_FN
vm_runtime_overlay_status vm_runtime_overlay_transaction_begin(
    uint8_t expected_family, uint16_t expected_generation);
LISP65_C2_REOPEN_GAP1_FN
vm_runtime_overlay_status vm_runtime_overlay_transaction_end(void);
#endif

/* Invalid policies, non-batch slots and NULL predicates execute once. */
vm_runtime_overlay_status vm_runtime_overlay_exec_batch(
    uint8_t slot, void *context, uint8_t *entry_result,
    vm_runtime_overlay_batch_policy policy,
    vm_runtime_overlay_repeat_predicate_fn repeat);

/* Boot gate: Slot 37 must install and verify the low-memory island first. */
vm_runtime_overlay_status vm_runtime_overlay_install_island(void);
uint8_t vm_runtime_overlay_island_ready(void);
uint8_t vm_resident_island_install(void *context);

/* Call from the central abort landing path after a slice escaped via longjmp. */
vm_runtime_overlay_status vm_runtime_overlay_abort_cleanup(void);

uint8_t vm_runtime_overlay_fault_latched(void);

#ifdef LISP65_RUNTIME_OVERLAY_HOST_TEST
/* The isolated smoke uses this instead of a device reset between mutations. */
uint8_t vm_runtime_overlay_active(void);
void vm_runtime_overlay_host_reset(void);
void vm_runtime_overlay_host_island_copy_fault(uint8_t enabled);
void vm_runtime_overlay_host_island_frame_fault(uint8_t enabled);
void vm_runtime_overlay_host_assume_island_ready(void);
void vm_runtime_overlay_host_force_transaction_untrusted(void);
uint16_t vm_runtime_overlay_host_transaction_context_calls(void);
uint8_t vm_runtime_overlay_host_island_matches_image(void);
uint8_t vm_runtime_overlay_catalog_verifier(void *context);
uint8_t vm_runtime_overlay_record_verifier(void *context);
#endif
#endif

#endif /* LISP65_VM_RUNTIME_OVERLAY_H */
