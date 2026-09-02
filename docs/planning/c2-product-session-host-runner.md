# Product-shaped C2 Session host runner

Status: permanent host gate, introduced 2026-07-28.

## The gap it closes

Before this gate, host tests covered the compiler, C2 emitter, Session append,
C2D resolution, hot materialization, and VM separately.  No host runner crossed
all of those boundaries in one execution.  The historical
`build/repl-session-host` test is not evidence for the C2 path: it installs code
through the pre-C2 REPL store.

That gap made a dynamic cross-entry question device-only.  It also meant that
host-green library freight had not executed a dynamically published symbolic
cross-reference through C2D before reaching hardware.

## Permanent path

`tools/host-lisp/c2_product_session_host.py` provides the reusable
`ProductSessionHost` API:

1. compile one definition under the dialect-v2 ABI;
2. construct the compiler semantic manifest;
3. pass it through the single C2I-v2 emitter;
4. append it as a persistent C2D-v6 Session image;
5. materialize the published entry from its C2D entry, resolution, and root
   records;
6. execute only the materialized object in the reference VM.

The fixture first appends `g` and `h` separately and executes `h`, which
tail-calls `g`.  It additionally requires `h`'s raw materialized literal to be
the exact result of the runner's canonical target `intern("g")`, using the
product `MK_SYMI` formula.  A merely SYMI-shaped value does not pass.

Its second case is the real Link-73 reproducer:

```lisp
(defun %is (n)
  (if (> n 0)
      (progn (intern "abc") (%is (- n 1)))
      t))
```

With argument 3, the host path performs three resolved Prim-68 calls to
`intern`, three resolved self-tailcalls through `%is`'s materialized SYMI
literal, and returns `t`.  The case therefore does **not** reproduce the target
failure.  This excludes a shared compiler/emitter/append/C2D-resolution/VM
logic fault.

The Python reference VM dispatches Prim 68 directly to its host interner; it
does not implement `vm_buffer_call`, `vm_codebuf`, or `BUF_ENSURE_MINE`.
Therefore the runner also builds a companion C-target lane from the real
`src/vm.c` and `src/intern_service_overlay.c`.  That lane executes, three times:

1. the real Prim-68 validation and `vm_buffer_call`;
2. owner invalidation before the synchronous context overwrites `vm_codebuf`;
3. a modeled, byte-checked Bank-3-to-$C356 record copy;
4. the real cold intern service;
5. the real `BUF_ENSURE_MINE` prefix and full-header reload;
6. the reloaded `%is` literal-1 identity check before recursive TAILCALL.

It reports three record copies, three 7-byte prefix reloads, three complete
header reloads, three correct `%is` literal checks, and result `t`, under ASan
and UBSan.  Thus takeover and reload are also host-entlasted.  Remaining
target-only surface is the physical runtime-overlay transport and its
family/generation, DMA, IRQ, CPU, and ABI state.

The runner exposes `snapshot_entry()` so a two-timepoint fixture can compare a
published entry before and after a modeled service action without changing the
emitter or append path.  `%is` and future library freight should extend this
runner rather than build private Session models.

`append_compiled_definition()` is the corresponding detached-CodeObject seam.
It accepts output from the product-bound compiler carrier while retaining the
same C2I-v2 emission, persistent C2D-v6 append, and materialization stages.
The Link-75 require attribution uses it in two lanes: all 32 Place/defstruct
forms as separate images for exact source cutpoints, and the same output as
two append-shaped library images.  This avoids substituting the Python
reference compiler when the compiler carrier itself is the object under test.

The latter lane is **not** a resolver execution.  It does not call the compiled
`require`, `%l65i-parse`, `%require-resolve`, or `%c2d-byte`; its Prim-67 call
count is zero.  The older require host gate likewise executes a Python
L65P/index/session model rather than `lib/stdlib-require.lisp`.  Consequently
the actual Lisp resolver and its C2D byte reads remain a separate host boundary
and must pass before a target-only attribution is claimed.

That separate boundary is closed by
`tools/host-lisp/c2_link75_real_require_resolver_host.py`.  It executes the
exact Link-75 stdlib CodeObjects against the exact Link-75 C2D and defstruct
D81.  The first `(require 'defstruct)` performs 399 real Prim-67 calls, reads
the index from the D81, publishes `place` before `defstruct`, and returns `t`.
The second call performs no load and leaves C2D and Bank 2 byteidentical.
Six mutations pin the C2D oracle, live watermark, L65I media, publish-after-load
requirement, loaded identity, and static source-slot shape.

The Prim-18 library loader remains modeled at its target boundary: exact L65S
artifacts are published into the mutable C2D plane with the current target v6
Session-row semantics.  Physical Bank-5 reads, DMA completion, IRQ state,
45GS02 semantics, and target ABI therefore remain outside the host claim.

## Gate placement

Run directly:

```sh
make c2-product-session-host-check
```

The same fixture is a mandatory lane of `make equivalence-check`.
Its bound result is recorded in
`tests/bytecode/dialect-v2/evidence/architecture-blocks/c2.2-product-session-host-runner-receipt.json`.

## Claim boundary

This is host integration evidence.  It uses the canonical compiler, C2I-v2
emitter, C2D-v6 append/materialization model, reference VM, and a second lane
compiled from the real C VM and intern-service sources.  It does not execute
the linked 45GS02 product and therefore cannot prove or disprove target-only
physical DMA, family/generation-cell, IRQ, CPU-semantics, or target-ABI faults.
The C lane does prove the `vm_codebuf` takeover and subsequent reload logic
with the physical transfer replaced by one checked memory copy.  No product
byte, product link, Xemu run, or hardware run is produced.

The host interner is isolated and deterministic.  The proof is the equality
between the materialized raw word and that interner's `intern("g")`; the
numeric symbol ordinal is not claimed to equal the live Link-73 session's
ordinal.

The failed Link-73 Xemu boot remains a separate tooling question; it is not
used as product evidence and is not retried by this gate.

## Equivalence-gate outage found during introduction

The uncommitted Treewalk `intern` primitive began calling
`primitive_exact_arity`, while that helper was still compiled only for
`LISP65_DIALECT_V2`.  The change is absent from committed `HEAD`
(`49566a7f`) and is present in the working tree no later than the
`src/eval.c` timestamp `2026-07-27 14:55:40 +0200`.

Consequently both non-v2 harness profiles built at the start of
`scripts/equivalence-check.sh` failed:

- the `CONTROL_SF` Treewalk/compiler profile;
- the disk-macro Treewalk/compiler profile.

The dialect-v2 product profile was not affected: it already compiled the
helper.  The carrier-cut profile was also outside the affected `apply_prim`
surface.

Because the first harness compilation is fail-fast, none of the following
lanes ran while the working-tree change was present: CONTROL_SF parity,
disk-macro parity, `case`, macro-only semantics, LCC byte oracle, quote
emission parity, C2D-v6 Session execution, LCC execution parity, macro/LCC
parity, the LCC fixed point, or the LCC-first REPL.

The repair makes only `primitive_exact_arity` common to every non-carrier
Treewalk profile.  The byte-argument helper remains dialect-v2-only.  A full
`make equivalence-check` after the repair passes every lane, including
93/93 forms in both primary routes, 97 LCC oracle forms, 20 quote-stage
equalities plus 20 mutations, two C2D Session cases plus 12 mutations, and all
LCC execution/fixed-point lanes.

The class is closed by a completion canary rather than by relying on the shell
driver's presence.  The driver removes any stale completion receipt before it
starts, journals the eleven canonical lanes in order, and emits a new bound
receipt only after all lanes completed with status zero.  Missing, reordered,
extra, or red lanes are rejected; five mutations pin those directions.  The
public `workbench-product` target depends on the fresh canary check, so a clean
product build cannot silently omit a broken or absent equivalence lane.

An additional, non-blocking profile audit found a separate First Red:
`build/equivalence/dialect-v2-native-function-check` compiles native string
codecs without `LISP65_INTERN_SESSION_SERVICE`, while `vm_string_arg_p` was
defined only with that service.  This was not the `primitive_exact_arity`
incident and did not affect the service-enabled product profile.

The First Red is closed in commit `3585ae60788d8cfa4299f3056d5ff7d49b234aca`:
the one helper definition is now guarded by
`LISP65_INTERN_SESSION_SERVICE || LISP65_V2_NATIVE_STRING_CODECS`.  The
service-free native-codec lane is rebuilt and actually executed by the
v1.2.1 Phase-C gate: 40 entries, three routes, four engines and 844
evaluations.  This is an execution witness, not merely a successful compile.
