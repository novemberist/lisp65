# AP8.5 native list primitives: stop memo

Date: 2026-07-12

Status: deferred after the single approved layout-neutral prototype

## Decision

The v2 Lists family keeps the local exact-arity correction for the existing
Treewalk primitives `nreverse`, `rplaca`, and `rplacd`. The portable native
VM/Runtime-Core unification is deferred. Prim-IDs 23 through 25 were never
shipped and are not allocated or tombstoned.

The migration remains `in-progress`. Strings implementation and final Lists
evidence promotion remain blocked, while read-only Strings capacity analysis
is allowed.

## Product measurements

The canonical dialect-v1 Workbench remains green:

- runtime-overlay VMA: `$c350`
- VMA ceiling: `$c356`
- post-boot reserve: 1800 B
- reserve target: 1536 B

The first three-primitive v2 prototype failed closed:

- runtime-overlay VMA: `$c4da`
- delta from v1: 394 B
- VMA deficit: 388 B
- hypothetical post-boot reserve: 1406 B

The single approved reduced prototype moved `nreverse` to v2 bytecode and
kept only native `rplaca`/`rplacd`. It also split the Device-LCC Prim mapper
below the 255-B CodeObject limit. It still failed:

- runtime-overlay VMA: `$c46a`
- delta from v1: 282 B
- VMA deficit: 276 B
- hypothetical post-boot reserve: 1518 B
- reserve-target deficit: 18 B

One `vm_callprim` consolidation was tried once. It added 4 B instead of
saving space and was removed. No second code diet, island use, slot, VMA, or
layout change was attempted.

## Performance measurement

The prototype benchmark used a 100-element input and compared the actual
pre-prototype filter tail with bytecode `nreverse`:

| Path | VM steps | Cons allocations | rplacd CALLPRIMs |
| --- | ---: | ---: | ---: |
| copy-reverse filter | 2365 | 100 | 0 |
| bytecode-nreverse filter | 2520 | 50 | 50 |

The bytecode path added 155 visible VM steps (`+6.6%`) and removed 50 Cons
allocations (`-50%`). A direct diagnostic `nreverse-100` comparison measured
2 visible wrapper steps for the native primitive and 1310 steps for bytecode.
The native loop's 100 internal pointer rewrites are not VM steps, so this
second comparison is diagnostic only.

## Correctness mitigation

The v2 Treewalk primitives now enforce exact arity 1/2/2 for direct,
`funcall`, and `apply` calls. This closes the silent NIL-padding and ignored
extra-argument bug in the Workbench path without allocating ABI identities.

Runtime-Core portability is not claimed. The migration contract blocks Lists
promotion until `v2-native-list-primitives` is completed and the full
Workbench/Runtime-Core matrix is green.

## Reopening path

Reopening requires one combined native-capability budget after the read-only
Strings audit, so Lists and Strings do not independently consume Bank-0
headroom. A later Colour-RAM/Attic rebalance is the named structural candidate;
it requires a new user-approved scope decision.

The former primitive-name-table reserve is not available. The current linkmap
places the table in `.lisp65_boot.names` at `$c741`, size `$17d` (381 B), in
the reclaimed boot overlay. Moving it again changes the resident floor by
0 B. The island remains frozen to cold L65M/Batch coordinators.

## Exit criteria

All conditions are mandatory:

- Workbench runtime-overlay VMA is at or below `$c356`.
- Workbench post-boot reserve is at least 1536 B.
- Runtime-Core stays above its hard Bank-0 minimum.
- Direct, `funcall`, and `apply` semantics agree across all required engines.
- The Workbench and Runtime-Core run the same portable v2 artifact semantics.
- No island reclassification, slot addition, VMA relaxation, or AP4 layout
  change occurs without a new user-approved architecture decision.
- Evidence and the cumulative capacity ledger are regenerated from the final
  product binaries only after the product links pass.
