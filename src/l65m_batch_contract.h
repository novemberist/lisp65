/* Shared C/assembler contract for the immutable L65M batch predicate. */
#ifndef LISP65_L65M_BATCH_CONTRACT_H
#define LISP65_L65M_BATCH_CONTRACT_H

#include <stddef.h>
#include <stdint.h>

#include "l65m_commit_overlay.h"
#include "l65m_overlay_abi.h"
#include "vm_runtime_overlay.h"

enum {
    VM_RTOV_PREFLIGHT_SLOT_BASE = LISP65_RUNTIME_OVERLAY_APPLICATION_SLOT_BASE,
    VM_RTOV_COMMIT_SLOT_BASE = VM_RTOV_PREFLIGHT_SLOT_BASE + L65M_OVERLAY_PHASE_COUNT,
    VM_RTOV_REQUIRED_SLOT_COUNT = VM_RTOV_COMMIT_SLOT_BASE + L65M_COMMIT_PHASE_COUNT
};

typedef struct {
    uint16_t abi_version;
    uint16_t cookie;
    uint8_t context_size;
    uint8_t expected_phase;
    uint8_t busy;
    uint8_t transport_status;
    uint8_t operation_status;
    uint8_t finished;
    uint8_t repeat_phase;
} vm_l65m_batch_header;

#define VM_BATCH_OFFSET_MATCH(type, member) \
    _Static_assert(offsetof(type, member) == \
                   offsetof(vm_l65m_batch_header, member), \
                   #type " batch header drift: " #member)
VM_BATCH_OFFSET_MATCH(l65m_overlay_work, abi_version);
VM_BATCH_OFFSET_MATCH(l65m_overlay_work, cookie);
VM_BATCH_OFFSET_MATCH(l65m_overlay_work, context_size);
VM_BATCH_OFFSET_MATCH(l65m_overlay_work, expected_phase);
VM_BATCH_OFFSET_MATCH(l65m_overlay_work, busy);
VM_BATCH_OFFSET_MATCH(l65m_overlay_work, transport_status);
_Static_assert(offsetof(l65m_overlay_work, validation_status) ==
               offsetof(vm_l65m_batch_header, operation_status),
               "preflight batch operation-status drift");
VM_BATCH_OFFSET_MATCH(l65m_overlay_work, finished);
VM_BATCH_OFFSET_MATCH(l65m_overlay_work, repeat_phase);
VM_BATCH_OFFSET_MATCH(l65m_commit_work, abi_version);
VM_BATCH_OFFSET_MATCH(l65m_commit_work, cookie);
VM_BATCH_OFFSET_MATCH(l65m_commit_work, context_size);
VM_BATCH_OFFSET_MATCH(l65m_commit_work, expected_phase);
VM_BATCH_OFFSET_MATCH(l65m_commit_work, busy);
VM_BATCH_OFFSET_MATCH(l65m_commit_work, transport_status);
_Static_assert(offsetof(l65m_commit_work, commit_status) ==
               offsetof(vm_l65m_batch_header, operation_status),
               "commit batch operation-status drift");
VM_BATCH_OFFSET_MATCH(l65m_commit_work, finished);
VM_BATCH_OFFSET_MATCH(l65m_commit_work, repeat_phase);
#undef VM_BATCH_OFFSET_MATCH

#endif /* LISP65_L65M_BATCH_CONTRACT_H */
