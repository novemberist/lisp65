/* Reusable, fail-closed transport for profile-bound Bank-0 runtime overlays. */
#ifndef LISP65_VM_RUNTIME_OVERLAY_H
#define LISP65_VM_RUNTIME_OVERLAY_H

#include <stdint.h>

#define LISP65_RUNTIME_OVERLAY_MAGIC_0          'L'
#define LISP65_RUNTIME_OVERLAY_MAGIC_1          '6'
#define LISP65_RUNTIME_OVERLAY_MAGIC_2          '5'
#define LISP65_RUNTIME_OVERLAY_MAGIC_3          'R'
#define LISP65_RUNTIME_OVERLAY_FORMAT_VERSION   1u
#define LISP65_RUNTIME_OVERLAY_HEADER_SIZE      32u
#define LISP65_RUNTIME_OVERLAY_ENTRY_SIZE       32u
#define LISP65_RUNTIME_OVERLAY_ENTRY_ABI_V1     1u
#define LISP65_RUNTIME_OVERLAY_HARD_MAX_SLICE   1792u
#define LISP65_RUNTIME_OVERLAY_HARD_MAX_VMA     0xc356u
#define LISP65_RUNTIME_OVERLAY_HARD_MAX_BOOT_SLICE 4096u
#define LISP65_RUNTIME_OVERLAY_HARD_MAX_SLICES  64u
#define LISP65_RUNTIME_OVERLAY_ENTRY_NOT_RUN    0xffu
#define LISP65_RUNTIME_OVERLAY_APPLICATION_SLOT_BASE 2u
#define LISP65_RUNTIME_ISLAND_INSTALL_SLOT      37u
#define LISP65_RUNTIME_ISLAND_ABI_VERSION       1u
#define LISP65_RUNTIME_ISLAND_COOKIE            0x1841u
#define LISP65_RUNTIME_ISLAND_ADDRESS           0x1800u
#define LISP65_RUNTIME_ISLAND_CAPACITY          2048u

#define LISP65_RUNTIME_OVERLAY_FLAG_BOOT        0x0001u
#define LISP65_RUNTIME_OVERLAY_FLAG_RUNTIME     0x0002u
#define LISP65_RUNTIME_OVERLAY_FLAG_REUSABLE    0x0004u

/* CRC-16/CCITT-FALSE, identical to the boot-overlay transport. */
#define LISP65_RUNTIME_OVERLAY_CRC16_POLY       0x1021u
#define LISP65_RUNTIME_OVERLAY_CRC16_INIT       0xffffu

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
    VM_RUNTIME_OVERLAY_ERR_ISLAND
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

/* Invalid policies, non-batch slots and NULL predicates execute once. */
vm_runtime_overlay_status vm_runtime_overlay_exec_batch(
    uint8_t slot, void *context, uint8_t *entry_result,
    vm_runtime_overlay_batch_policy policy,
    vm_runtime_overlay_repeat_predicate_fn repeat);

LISP65_RESIDENT_ISLAND_FN
vm_runtime_overlay_status vm_runtime_overlay_exec_batch_island(
    uint8_t slot, void *context, uint8_t *entry_result,
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
void vm_runtime_overlay_host_assume_island_ready(void);
uint8_t vm_runtime_overlay_catalog_verifier(void *context);
uint8_t vm_runtime_overlay_record_verifier(void *context);
#endif
#endif

#endif /* LISP65_VM_RUNTIME_OVERLAY_H */
