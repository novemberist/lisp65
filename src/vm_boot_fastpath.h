/* Profile-bound Bank-5 stdlib boot transaction executed from Bank-3 slices. */
#ifndef LISP65_VM_BOOT_FASTPATH_H
#define LISP65_VM_BOOT_FASTPATH_H

#include <stdint.h>

#include "obj.h"
#include "vm_runtime_overlay.h"

#define VM_BOOT_FASTPATH_ABI_VERSION 2u
#define VM_BOOT_FASTPATH_COOKIE_BASE 0x65b0u
#define VM_BOOT_FASTPATH_CRC_PASSES 1u
#define VM_BOOT_FASTPATH_OVERLAY_CALLS 3u

enum {
    VM_BOOT_FASTPATH_PHASE_VERIFY = 0,
    VM_BOOT_FASTPATH_PHASE_PATCHES,
    VM_BOOT_FASTPATH_PHASE_ENTRIES,
    VM_BOOT_FASTPATH_PHASE_COUNT
};

typedef enum {
    VM_BOOT_FASTPATH_OK = 0,
    VM_BOOT_FASTPATH_ERR_CONTEXT,
    VM_BOOT_FASTPATH_ERR_ABI,
    VM_BOOT_FASTPATH_ERR_COOKIE,
    VM_BOOT_FASTPATH_ERR_REENTRY,
    VM_BOOT_FASTPATH_ERR_PHASE,
    VM_BOOT_FASTPATH_ERR_PROFILE,
    VM_BOOT_FASTPATH_ERR_STATE,
    VM_BOOT_FASTPATH_ERR_CRC,
    VM_BOOT_FASTPATH_ERR_SOURCE,
    VM_BOOT_FASTPATH_ERR_NODE,
    VM_BOOT_FASTPATH_ERR_HEAP,
    VM_BOOT_FASTPATH_ERR_DIRECTORY,
    VM_BOOT_FASTPATH_ERR_CATALOG
} vm_boot_fastpath_status;

static inline vm_boot_fastpath_status
vm_boot_fastpath_transport_status(vm_runtime_overlay_status status) {
    if (status == VM_RUNTIME_OVERLAY_OK) return VM_BOOT_FASTPATH_OK;
    /* Content/compatibility failures are 4..13 plus CRC at 15; STACK at
     * 14 and every transport lifecycle failure remain internal state. */
    if (status >= VM_RUNTIME_OVERLAY_ERR_MAGIC &&
        status <= VM_RUNTIME_OVERLAY_ERR_CRC &&
        status != VM_RUNTIME_OVERLAY_ERR_STACK)
        return VM_BOOT_FASTPATH_ERR_CATALOG;
    return VM_BOOT_FASTPATH_ERR_STATE;
}

typedef struct {
    uint16_t abi_version;
    uint16_t cookie;
    uint8_t expected_phase;
    uint8_t busy;
    uint8_t status;
    uint8_t finished;
    uint8_t crc_passes;
    uint8_t overlay_calls;
    uint16_t cursor;
    uint16_t crc_bytes;
    uint16_t fix_literals;
    uint16_t symbol_literals;
    uint16_t string_literals;
} vm_boot_fastpath_work;

#ifdef __mos__
_Static_assert(sizeof(vm_boot_fastpath_work) <= 20u,
               "boot-fastpath work ABI exceeds 20 bytes");
#endif

void vm_boot_fastpath_prepare(vm_boot_fastpath_work *work);
uint8_t vm_boot_fastpath_phase_verify(void *context);
uint8_t vm_boot_fastpath_phase_patches(void *context);
uint8_t vm_boot_fastpath_phase_entries(void *context);

#endif /* LISP65_VM_BOOT_FASTPATH_H */
