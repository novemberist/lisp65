/* Pointer-free work ABI for transactional L65M commit overlay slices. */
#ifndef LISP65_L65M_COMMIT_OVERLAY_H
#define LISP65_L65M_COMMIT_OVERLAY_H

#include <stdint.h>

#include "l65m_validate.h"

#define L65M_COMMIT_OVERLAY_ABI_VERSION 4u
#define L65M_COMMIT_OVERLAY_COOKIE_BASE 0x65c0u

enum {
    L65M_COMMIT_PHASE_VERIFY = 0,
    L65M_COMMIT_PHASE_PATCH_RECORD,
    L65M_COMMIT_PHASE_MATERIALIZE_SHAPE,
    L65M_COMMIT_PHASE_MATERIALIZE_SCALARS,
    L65M_COMMIT_PHASE_MATERIALIZE_STRINGS,
    L65M_COMMIT_PHASE_PATCH_PUBLISH,
    L65M_COMMIT_PHASE_ENTRIES,
    L65M_COMMIT_PHASE_COUNT
};

/* Temporary source-level compatibility for the resident reservation handoff. */
#define L65M_COMMIT_PHASE_STATE L65M_COMMIT_PHASE_VERIFY

typedef enum {
    L65M_COMMIT_TRANSPORT_OK = 0,
    L65M_COMMIT_TRANSPORT_CONTEXT,
    L65M_COMMIT_TRANSPORT_ABI,
    L65M_COMMIT_TRANSPORT_COOKIE,
    L65M_COMMIT_TRANSPORT_REENTRY,
    L65M_COMMIT_TRANSPORT_PHASE
} l65m_commit_transport_status;

typedef struct {
    uint16_t abi_version;
    uint16_t cookie;
    uint8_t context_size;
    uint8_t expected_phase;
    uint8_t busy;
    uint8_t transport_status;
    uint8_t commit_status;
    uint8_t finished;
    uint8_t repeat_phase;
    uint8_t format_version;

    uint16_t cursor;
    uint16_t pending_off;

    uint16_t source_length;
    uint16_t source_metadata_off;
    uint16_t code_base;
    uint16_t entry_count;
    uint16_t patch_count;
    uint16_t entries_off;
    uint16_t index_off;
    uint16_t nodes_off;
    uint16_t patches_off;
    uint16_t strings_off;
    uint16_t dir_before;
    uint16_t symbols_before;
    uint16_t namepool_before;
    uint16_t heap_free_before;
    uint16_t arena_used_before;
    uint16_t roots_before;
} l65m_commit_work;

#define L65M_COMMIT_CONTEXT_SIZE ((uint8_t)sizeof(l65m_commit_work))

#ifdef __mos__
_Static_assert(sizeof(l65m_commit_work) <= 48u,
               "L65M commit overlay work ABI exceeds 48 bytes");
#endif

l65m_status l65m_commit_work_prepare(l65m_commit_work *work,
                                     const l65m_source *source,
                                     const l65m_plan *plan);
void l65m_commit_work_release(void);
void l65m_commit_abort_cleanup(void);

uint8_t l65m_commit_phase_verify(void *context);
uint8_t l65m_commit_phase_patch_record(void *context);
uint8_t l65m_commit_phase_materialize_shape(void *context);
uint8_t l65m_commit_phase_materialize_scalars(void *context);
uint8_t l65m_commit_phase_materialize_strings(void *context);
uint8_t l65m_commit_phase_patch_publish(void *context);
uint8_t l65m_commit_phase_entries(void *context);

#ifdef L65M_COMMIT_OVERLAY_HOST_DIRECT
l65m_status l65m_commit_run_direct(const l65m_source *source, const l65m_plan *plan);
#endif

#endif /* LISP65_L65M_COMMIT_OVERLAY_H */
