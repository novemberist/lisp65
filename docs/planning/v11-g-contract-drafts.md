# 1.1-G contracts: `gc`/`room`, `error`, and the tick hook

Status: owner-approved contracts, 2026-07-17. This document authorizes the
bounded implementation probes for `gc`/`room` and `error`; it does not by
itself authorize their capacity deltas or product promotion. The tick-hook
decision is final for 1.1: defer the complete hook to C2, with no prompt-only
substitute.

Outcome, 2026-07-17: the semantics below remain pinned, but the one authorized
generic-facade/co-pack attempt failed the fixed resident boundary and both
carrier allocations. `gc`, `room`, and `error` are therefore not delivered in
1.1 and move together to C2.2. The "delivery cut to probe" sections are the
historical rejected design, not current implementation authority.

## 1. `gc` and `room`: one private state seam

### Approved public contract

`(gc)` has exact arity zero. It runs one complete synchronous collection and
returns `t` after the collector has finished. It is not a request or a future;
the return value means that collection completed. Direct, `funcall`, and
`apply` routes have identical behavior.

`(room)` has exact arity zero. It does not print. It returns this fixed-order
proper list of eight fixnums:

```text
(heap-free heap-capacity
 symbol-free symbol-capacity
 namepool-free namepool-capacity
 directory-free directory-capacity)
```

The eight counters are one pre-result snapshot. Constructing the result list
may itself consume heap cells; that deliberate observer cost is not folded
back into `heap-free`. Returning data rather than formatted prose keeps the
operation composable and lets a shelf helper provide human-readable output
without resident formatting code.

All reported values must fit the signed 15-bit fixnum. The product build adds
static gates for heap capacity, `MAX_SYM`, `NAMEPOOL`, and `VM_DIR_MAX`; a
future configuration that exceeds 16383 must stop at build time until the
result representation is revised. Counters never wrap or truncate.

### Approved delivery cut to probe

Both public functions use one restricted selector carrier. Selector zero runs
GC; the remaining selectors return the eight snapshot fields. `gc` is a small
resident bytecode wrapper. `room` and its presentation helper are shelf code;
only the carrier is native. The carrier is private in apply/function-kind/
compile-REPL views and is covered by the native-registry cross-parity gate.

A pure `peek` shelf implementation is rejected for the probe. The useful
state is exposed today through C accessors (`mem_free_cells`, `sym_count`,
`sym_pool_used`, `vm_dir_count`); heap-free is computed rather than stored,
and all concrete addresses are build-specific. Publishing those addresses
would turn a link layout into an accidental ABI.

### Required evidence

- direct/`funcall`/`apply` parity for both public functions;
- exact-arity negatives;
- a `room` snapshot with independently read C counters;
- `gc_runs` increases by exactly one and unreachable cells are reclaimed;
- repeated `room` calls have only their documented result-allocation cost;
- real-link capacity deltas cover Bank 0, EXT, fixed overlay, runtime-bank,
  island, installer slice, symbols, Namepool, and Directory.

## 2. `error`: one String payload, existing top-level unwind

### Approved public contract

`(error message)` has exact arity one and accepts only a String. A non-String
uses the ordinary VM type-error path. On success it never returns: it aborts
through the existing top-level unwind, performs the existing runtime-overlay
and L65M abort cleanup, prints exactly `*** ` followed by the String and a
newline, clears the pending payload, and presents a fresh REPL prompt.

Version 1 has no numeric user code, condition object, handler, restart, or
resumable continuation. Those are explicitly deferred to the 1.2 exit/control
work. The String is presentation payload, not a stable machine-readable error
identity.

### Approved delivery cut to probe

The numeric L65E table cannot represent dynamic text and must not pretend to.
The probe therefore adds one private user-error carrier plus a dedicated
pending-String field at the existing abort boundary. The carrier validates the
argument before changing state, captures the object without allocation, and
immediately unwinds. No GC or allocation is permitted between capture and
render. The REPL renders the String before clearing roots and pending state.

This is an extension of the existing error-unwind truth source, not a parallel
exception system. It must reuse `lisp_abort_jump()` cleanup and the one pending
error record. A host call without an active top level may retain the pending
String as a test witness, but it must not claim device return semantics.

### Required evidence

- direct/`funcall`/`apply` all abort with the exact String;
- non-String and wrong-arity paths use the existing type/arity errors and do
  not leave a pending user payload;
- overlay/L65M cleanup runs before the landing path;
- two consecutive errors cannot leak the first message;
- embedded NUL and maximum-length String behavior is pinned byte-for-byte;
- real hardware shows one message and a usable fresh prompt.

## 3. Tick hook: safe placement precedes API and bytes

### Proven constraint

`lisp_poll()` runs inside bytecode, tree-walk loops, and blocking keyboard
waits. Calling Lisp from it would re-enter the VM/evaluator while their C
frames and GC roots are live. The 23-byte jiffy probe proves only that frame
changes can be observed cheaply; it does not prove a safe Lisp callback.

The only presently proven callback boundary is the top-level REPL boundary,
after a form has completed and all transient loader/compiler/disk activity has
retired. A hook dispatched only there is safe, but it is not a timer for a
running expression or game loop. In particular it cannot honestly support
the planned `(time expr)` helper.

### Owner decision

The full tick hook is deferred to C2. There is no `repl-idle-hook` substitute
in 1.1: a prompt-only callback supports neither honest `(time)` semantics nor
game loops and would create a second, deliberately weaker API to explain and
retire. `lisp_poll()` may eventually coalesce elapsed frames into resident
state, but C2 must first introduce an explicit resumable/scheduler boundary
from which Lisp can be called without recursive VM entry. `(time)` and the
`ticks` tombstone move with that work.

A callback from `lisp_poll()` or from an IRQ remains rejected. It is cheap in
bytes but violates evaluator, GC-root, compiler-lifetime, and disk transaction
invariants. No capacity result can authorize an unsafe callback point.

### Evidence required when C2 reopens the hook

- no callback during GC, L65M validation/commit, M65D COW, compiler-tier
  lifetime/retirement, or abort cleanup;
- elapsed-frame coalescing and saturation, including wrap of the hardware
  jiffy source;
- callback error returns cleanly to the REPL and clears the hook according to
  the selected policy;
- repeated callbacks do not grow roots, Directory, symbols, or watermarks;
- physical-frame timing plus an emulator fidelity tag;
- complete capacity delta before product implementation.
