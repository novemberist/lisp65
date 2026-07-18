#ifndef LISP65_C1_PHASE_PROBE_H
#define LISP65_C1_PHASE_PROBE_H

#include <stdint.h>

/* A timing build measures exactly one pair of boundaries.  Keeping the probe
 * pairwise is deliberate: the canonical C1 runtime slice has only ten bytes
 * of transport headroom, so a monolithic trace changes the product path it is
 * meant to measure and cannot pass the real link gates. */
#define LISP65_C1_PROBE_SHELF_TRANSFER 1
#define LISP65_C1_PROBE_COMMIT         2
#define LISP65_C1_PROBE_COMPILE        3
#define LISP65_C1_PROBE_RETIRE         4
#define LISP65_C1_PROBE_INSTALL        5
#define LISP65_C1_PROBE_PREFLIGHT      6
#define LISP65_C1_PROBE_COMMIT_ONLY    7
#define LISP65_C1_PROBE_COMMIT_VERIFY  8
#define LISP65_C1_PROBE_COMMIT_APPLY   9
#define LISP65_C1_PROBE_EXPRESSION     10

#define LISP65_C1_PROBE_EDGE_BEGIN 0
#define LISP65_C1_PROBE_EDGE_END   1

#ifdef LISP65_C1_PHASE_TIMING
/* $17a0..$17ff is the profile-bound gap between the 80x50 screen and the
 * immutable resident island at $1800.  A diagnostic image writes its two
 * frame samples there directly: no resident code, BSS or product VMA moves. */
#define LISP65_C1_PHASE_TRACE_BASE 0x17f0u
#ifdef __MEGA65__
#define lisp65_c1_phase_mark_for(probe, edge) \
    do { \
        if (LISP65_C1_PHASE_TIMING == (probe)) { \
            *(volatile uint8_t *)(uintptr_t) \
                (LISP65_C1_PHASE_TRACE_BASE + (edge)) = \
                *(volatile uint8_t *)(uintptr_t)0xd7fau; \
        } \
    } while (0)
#else
#define lisp65_c1_phase_mark_for(probe, edge) \
    do { (void)(probe); (void)(edge); } while (0)
#endif
#else
#define lisp65_c1_phase_mark_for(probe, edge) \
    do { (void)(probe); (void)(edge); } while (0)
#endif

#endif
