/* R2 host harness: deep non-tail VM recursion, the soft-frame bound, and abort
 * across nested VM frames.
 *
 * The same binary is built twice by the make target: once with
 * -DLISP65_VM_SOFT_FRAMES and once without.  Every semantic expectation below
 * must hold in both builds; only the depth instrumentation (native C-stack
 * bytes per Lisp call level, and the soft-frame accessors) differs.
 *
 * Deliberately hand-assembled: no compiler/reader dependency, so the vectors
 * stay stable and the payload can be forced across the streamed code window.
 *
 *   deep(n) = 0        if n < 1     (via the native tree-walker bridge "probe")
 *   deep(n) = 1 + deep(n-1)         otherwise            <- NON-tail
 *
 * Exit 0 = PASS. */
#include <stdio.h>
#include <string.h>
#include <setjmp.h>
#include <stdint.h>
#include "obj.h"
#include "mem.h"
#include "symbol.h"
#include "vm.h"
#include "interrupt.h"

#ifndef VM_CODEBUF
#define VM_CODEBUF 128   /* mirrors the vm.c default; only used for the banner */
#endif

/* The bound deliverable is a 16-level private frame array on the product's
 * GC_ROOTS=128 budget, so this harness runs in two shapes:
 *
 *  - WIDE: a large root stack and (ON) a large frame stack.  These builds carry
 *    the equivalence rows at depth 200 and 2000, where OFF and ON must agree.
 *  - PRODUCT-SHAPED: GC_ROOTS=128 and the shipped VM_SOFT_FRAME_MAX.  These
 *    builds carry the depth proof of the Known Issue (docs/known-issues.md,
 *    E29): the depths that used to end in the E29 loop now return, and one
 *    level past the bound refuses cleanly instead of corrupting page 1.
 *
 * Every semantic row that both shapes can run is run by both. */
#if defined(LISP65_VM_SOFT_FRAMES)
#ifndef VM_SOFT_FRAME_MAX
#define VM_SOFT_FRAME_MAX 16
#endif
#if (GC_ROOTS) >= 16384 && (VM_SOFT_FRAME_MAX) >= 2001
#define SF_WIDE_PROFILE 1
#endif
#else
#if (GC_ROOTS) >= 16384
#define SF_WIDE_PROFILE 1
#endif
#endif

/* Platform seam: the host VM reads code_store instead of banked device RAM.
 * The store spans the full 16-bit offset range on purpose: the second code
 * object is placed above 0x8000 so that a frame has to carry bit 15 of `off`.
 * That bit is the one field the root-stack frame encoding (lever B) cannot fit
 * in a single 15-bit slot, so it must be exercised. */
#define CODE_STORE_SIZE 0x10000
#define DEEPT_OFF       0xc000u
static uint8_t code_store[CODE_STORE_SIZE];
void vm_code_load(uint8_t bank, uint16_t off, uint16_t len, uint8_t *dst) {
    (void)bank; memcpy(dst, code_store + off, len);
}

static int failed = 0;
static void check(const char *what, int ok, const char *detail) {
    printf("%-52s %s%s%s\n", what, ok ? "OK" : "FAIL",
           detail && *detail ? "  " : "", detail ? detail : "");
    if (!ok) failed++;
}

/* ---- the probe bridge: the innermost native re-entry of a deep run ------- */
enum { PROBE_RETURN0 = 0, PROBE_ABORT = 1 };
static uint8_t probe_mode = PROBE_RETURN0;
static uintptr_t probe_frame_mark;    /* address of a local in the deepest bridge,
                                       * kept as an integer: only the delta is used */
static uint16_t probe_soft_depth;     /* frame-stack depth seen at the bottom */
static uint32_t probe_calls;

static obj probe_bridge(obj sym, const obj *args, uint8_t n) {
    volatile char marker = 0;
    (void)sym; (void)args; (void)n;
    probe_frame_mark = (uintptr_t)(void *)&marker;
    probe_calls++;
#ifdef LISP65_VM_SOFT_FRAMES
    probe_soft_depth = vm_soft_frame_depth();
#else
    probe_soft_depth = 0;
#endif
    if (probe_mode == PROBE_ABORT)
        lisp_abort_code(LISP65_ERR_VM_STACK);
    return MKFIX(0);
}

/* ---- the code object ---------------------------------------------------- */
#define NLITS 2
#define HDRLEN (CO_OFF_LITTAB + 2 * NLITS)

static const uint8_t payload[] = {
    OP_PUSHARG0,               /* 0  n            */
    OP_PUSHI8, 1,              /* 1               */
    OP_LESS,                   /* 3  n < 1 ?      */
    OP_JFALSEREL, 4,           /* 4  -> 10        */
    OP_CALL, 1, 0,             /* 6  (probe)      */
    OP_RET,                    /* 9               */
    OP_PUSHI8, 1,              /* 10              */
    OP_PUSHARG0,               /* 12              */
    OP_PUSHI8, 1,              /* 13              */
    OP_SUB,                    /* 15  n-1         */
    OP_CALL, 0, 1,             /* 16  deep(n-1)   */
    OP_ADD,                    /* 19  1 + ...     */
    OP_RET                     /* 20              */
};
/* Same function, except that the base case leaves the frame by TAIL-calling the
 * uncompiled symbol.  In the native build that is a plain C return of the whole
 * activation; with soft frames it must pop exactly ONE VM frame.  Getting that
 * wrong silently discards every suspended caller, which is what the lcc
 * self-compile oracle caught. */
static uint8_t payload_tail[] = {
    OP_PUSHARG0,               /* 0               */
    OP_PUSHI8, 1,              /* 1               */
    OP_LESS,                   /* 3               */
    OP_JFALSEREL, 4,           /* 4  -> 10        */
    OP_TAILCALL, 1, 0,         /* 6  tail (probe) */
    OP_RET,                    /* 9  (unreached)  */
    OP_PUSHI8, 1,              /* 10              */
    OP_PUSHARG0,               /* 12              */
    OP_PUSHI8, 1,              /* 13              */
    OP_SUB,                    /* 15              */
    OP_CALL, 0, 1,             /* 16  deept(n-1)  */
    OP_ADD,                    /* 19              */
    OP_RET                     /* 20              */
};
#define OBJLEN ((uint16_t)(HDRLEN + sizeof payload))

static int deep_di, deept_di;
static uint16_t deept_off;

static void write_header(uint8_t *o, const uint8_t *body, uint16_t bodylen) {
    o[CO_OFF_MAGIC] = CO_MAGIC;
    o[CO_OFF_NARGS] = 1;
    o[CO_OFF_NLOCS] = 0;
    o[CO_OFF_FLAGS] = 0;
    o[CO_OFF_CLEN]  = (uint8_t)bodylen;
    o[CO_OFF_CLEN + 1] = 0;
    o[CO_OFF_NLITS] = NLITS;
    memcpy(o + HDRLEN, body, bodylen);
}

static void put_lit(uint8_t *o, int slot, obj v) {
    o[CO_OFF_LITTAB + 2 * slot] = (uint8_t)((uint16_t)v & 0xffu);
    o[CO_OFF_LITTAB + 2 * slot + 1] = (uint8_t)(((uint16_t)v >> 8) & 0xffu);
}

static void build_objects(void) {
    obj probe_sym = intern("probe");
    memset(code_store, 0, sizeof code_store);
    deept_off = DEEPT_OFF;
    write_header(code_store, payload, (uint16_t)sizeof payload);
    write_header(code_store + deept_off, payload_tail, (uint16_t)sizeof payload_tail);

    vm_dir_reset();
    deep_di  = vm_dir_add(intern("deep"),  0, 0, OBJLEN);
    /* The directory reconstructs offsets sparsely and demands contiguity inside
     * an 8-entry block, so a second code source has to start its own block. */
    vm_dir_align8();
    deept_di = vm_dir_add(intern("deept"), 0, deept_off, OBJLEN);
    if (deep_di < 0 || deept_di < 0) {
        puts("vm-soft-frames: FAIL (directory registration)");
        failed++;
    }
    /* lit0 = the callee itself (BCODE immediate -> directory index directly),
     * lit1 = an uncompiled symbol -> tree-walker bridge (native re-entry). */
    put_lit(code_store, 0, MK_BCODE((uint16_t)deep_di));
    put_lit(code_store, 1, probe_sym);
    put_lit(code_store + deept_off, 0, MK_BCODE((uint16_t)deept_di));
    put_lit(code_store + deept_off, 1, probe_sym);
}

static obj run_deep(int16_t n) {
    obj arg = MKFIX(n);
    vm_status = VM_OK;
    return vm_run(0, 0, OBJLEN, &arg, 1);
}

static obj run_deept(int16_t n) {
    obj arg = MKFIX(n);
    vm_status = VM_OK;
    return vm_run(0, deept_off, OBJLEN, &arg, 1);
}

/* ---- expectations ------------------------------------------------------- */
static void expect_depth(int16_t n) {
    char what[64];
    obj got;
    probe_mode = PROBE_RETURN0;
    gc_rootsp = 0;
    got = run_deep(n);
    snprintf(what, sizeof what, "deep(%d) == %d, status VM_OK", (int)n, (int)n);
    check(what, vm_status == VM_OK && IS_FIX(got) && FIXVAL(got) == n, "");
    if (!(vm_status == VM_OK && IS_FIX(got) && FIXVAL(got) == n))
        printf("      status=%u fix=%d val=%d\n", vm_status,
               (int)(IS_FIX(got) != 0), IS_FIX(got) ? FIXVAL(got) : 0);
}

static void expect_depth_tail(int16_t n) {
    char what[80];
    obj got;
    probe_mode = PROBE_RETURN0;
    gc_rootsp = 0;
    got = run_deept(n);
    snprintf(what, sizeof what,
             "deept(%d) == %d (base case leaves via TAILCALL to the bridge)",
             (int)n, (int)n);
    check(what, vm_status == VM_OK && IS_FIX(got) && FIXVAL(got) == n, "");
    if (!(vm_status == VM_OK && IS_FIX(got) && FIXVAL(got) == n))
        printf("      status=%u fix=%d val=%d\n", vm_status,
               (int)(IS_FIX(got) != 0), IS_FIX(got) ? FIXVAL(got) : 0);
}

#ifdef LISP65_VM_SOFT_FRAMES
static void expect_overflow(int16_t n) {
    char what[80];
    obj got;
    probe_mode = PROBE_RETURN0;
    gc_rootsp = 0;
    got = run_deep(n);
    (void)got;
    snprintf(what, sizeof what, "deep(%d) -> clean VM_STACKOVER (no crash)", (int)n);
    check(what, vm_status == VM_STACKOVER, "");
    if (vm_status != VM_STACKOVER) printf("      status=%u\n", vm_status);
    /* the root stack must be handed back to the caller unchanged */
    check("  root stack fully unwound after the overflow", gc_rootsp == 0, "");
    check("  soft frame stack fully unwound after the overflow",
          vm_soft_frame_depth() == 0, "");
}
#endif

static int probe_soft_depth_ok(void) {
#ifdef LISP65_VM_SOFT_FRAMES
    return probe_soft_depth > 0;
#else
    return 1;   /* no frame stack in this build; depth lives on the C stack */
#endif
}

static void expect_abort_then_recover(int16_t n) {
    char what[80];
    int landed;
    probe_mode = PROBE_ABORT;
    gc_rootsp = 0;
    lisp65_error_clear();
    lisp_toplevel_active = 1;
    if (setjmp(lisp_toplevel) == 0) {
        (void)run_deep(n);
        landed = 0;
    } else {
        landed = 1;
    }
    lisp_toplevel_active = 0;
    snprintf(what, sizeof what, "abort at depth %d reaches the toplevel landing", (int)n);
    check(what, landed, "");
    check("  the abort was raised below the top VM frame",
          probe_soft_depth_ok(), "");
    /* what the toplevel landing does today, unchanged by this feature */
    gc_rootsp = 0;
    lisp65_error_clear();
    /* NOTE: no vm_soft_frame_reset() here on purpose.  The private array's
     * entry-time purge must self-heal from the orphaned frames a longjmp left
     * behind; asserting the recovery WITHOUT an explicit reset is what gives
     * that invariant its only coverage. */

    probe_mode = PROBE_RETURN0;
    {
        obj got = run_deep(7);
        check("  the next evaluation after the abort is correct",
              vm_status == VM_OK && IS_FIX(got) && FIXVAL(got) == 7, "");
        if (!(vm_status == VM_OK && IS_FIX(got) && FIXVAL(got) == 7))
            printf("      status=%u val=%d\n", vm_status,
                   IS_FIX(got) ? FIXVAL(got) : -999);
    }
#ifdef LISP65_VM_SOFT_FRAMES
    check("  soft frame stack is empty again after the recovery",
          vm_soft_frame_depth() == 0, "");
#endif
}

/* How deep can this build actually go before the clean VM_STACKOVER?  Reported,
 * never asserted: the answer depends on GC_ROOTS, on the frame storage and, in
 * the OFF build on the host, on nothing at all except GC_ROOTS (the device's
 * hardware-stack cliff has no host equivalent). */
static int16_t probe_max_depth(void) {
    int16_t lo = 0, hi = 20000;
    probe_mode = PROBE_RETURN0;
    while (lo < hi) {
        int16_t mid = (int16_t)(lo + (hi - lo + 1) / 2);
        gc_rootsp = 0;
        (void)run_deep(mid);
        if (vm_status == VM_OK) lo = mid; else hi = (int16_t)(mid - 1);
    }
    gc_rootsp = 0;
    vm_status = VM_OK;
    return lo;
}

int main(void) {
    char detail[96];
    mem_init();
    vm_init();
    vm_treewalk_call = probe_bridge;
    build_objects();

#ifdef LISP65_VM_SOFT_FRAMES
    printf("build: LISP65_VM_SOFT_FRAMES=ON  capacity=%u  VM_CODEBUF=%d GC_ROOTS=%d\n",
           (unsigned)vm_soft_frame_capacity(), (int)VM_CODEBUF, (int)GC_ROOTS);
#else
    printf("build: LISP65_VM_SOFT_FRAMES=OFF VM_CODEBUF=%d GC_ROOTS=%d\n",
           (int)VM_CODEBUF, (int)GC_ROOTS);
#endif

    expect_depth(1);
    expect_depth(10);
    expect_depth_tail(1);
    expect_depth_tail(10);
#ifdef SF_WIDE_PROFILE
    expect_depth(200);
    expect_depth(2000);
    expect_depth_tail(200);
    expect_depth_tail(2000);
#else
    /* Product-shaped profile: the depth proof of the Known Issue.  On the
     * device today this path overflows the 256-byte hardware stack at 13
     * levels and enters the repeated E29 loop (docs/known-issues.md).  With
     * the feature it returns, and one level past the frame bound refuses with
     * the same VM_STACKOVER the resource already raises. */
    expect_depth(13);
    expect_depth_tail(13);
#ifdef LISP65_VM_SOFT_FRAMES
    expect_depth((int16_t)vm_soft_frame_capacity());
    expect_depth_tail((int16_t)vm_soft_frame_capacity());
#else
    expect_depth(16);
    expect_depth_tail(16);
#endif
#endif

    /* native C-stack bytes per Lisp call level, measured at the deepest
     * native re-entry (the tree-walker bridge) of two runs.  The span has to
     * fit the profile's own depth budget. */
    {
        uintptr_t m1, m2;
        long per_level;
        int16_t span;
#ifdef SF_WIDE_PROFILE
        span = 100;
#else
        span = 12;
#endif
        probe_mode = PROBE_RETURN0;
        gc_rootsp = 0; (void)run_deep(1);   m1 = probe_frame_mark;
        gc_rootsp = 0; (void)run_deep((int16_t)(1 + span)); m2 = probe_frame_mark;
        /* the host C stack grows down: m1 (depth 1) is the higher address */
        per_level = (long)(m1 - m2) / span;
        snprintf(detail, sizeof detail, "(%ld host bytes/level)", per_level);
#if defined(__SANITIZE_ADDRESS__) || defined(LISP65_SF_NO_STACK_PROBE)
        /* ASan relocates locals onto a shadow "fake stack"; the frame-address
         * delta stops being a measurement of the C stack, so this row is
         * reported but not asserted in sanitizer builds. */
        printf("%-52s SKIP  %s (sanitizer build)\n",
               "native C-stack bytes per Lisp call level", detail);
#elif defined(LISP65_VM_SOFT_FRAMES)
        check("VM->VM call costs 0 native C-stack bytes per level",
              per_level == 0, detail);
#else
        check("baseline: VM->VM call costs native C-stack bytes per level",
              per_level > 0, detail);
#endif
    }

#ifdef SF_WIDE_PROFILE
    expect_abort_then_recover(50);
#else
    expect_abort_then_recover(12);
#endif

#ifdef LISP65_VM_SOFT_FRAMES
    /* One level past the bound is the row that matters for the product: the
     * FIRST refused depth must be clean, not merely some depth far beyond it. */
    expect_overflow((int16_t)(vm_soft_frame_capacity() + 1u));
    expect_overflow((int16_t)(vm_soft_frame_capacity() + 10u));
    printf("soft frame high water: %u of %u\n",
           (unsigned)vm_soft_frame_high_water(),
           (unsigned)vm_soft_frame_capacity());
#else
    printf("(no soft-frame bound in this build; depth is bounded by the "
           "native C stack and GC_ROOTS)\n");
#endif

    printf("max non-tail depth reached before a clean VM_STACKOVER: %d\n",
           (int)probe_max_depth());

    printf("vm-soft-frames: %s (failures=%d)\n", failed ? "FAIL" : "PASS", failed);
    return failed ? 1 : 0;
}
