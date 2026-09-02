# v2 Capability/Carrier Registry

Status: Checkpoint 4 closed. The normative sources are
`config/workbench-native-service-registry.json` and
`config/v2-capability-carrier-block.json`.

## Purpose

The registry is a build/link-time inventory, not a runtime dispatch layer. It
binds every generic `CALL` and `TAILCALL` target in the shipped Workbench
artifacts and proves which targets are still served by the existing C carrier.
Runtime function pointers and dynamic registration are forbidden; execution
remains a direct static branch.

`LISP65_V2_SERVICE_REGISTRY_CLOSED` denotes only the result of such a product
inventory. It does not activate a service and, in particular, is not an alias
for `LISP65_V2_WORKBENCH_SERVICES`. The Workbench sets both flags after closing
its 28-target inventory. Runtime Core sets only the generic closure flag after
its own allow-set gate passes. This prevents an evaluator-free product from
pulling the Workbench dispatcher or its eleven error sentinels into the link.

## Baseline

The Checkpoint-2 link inventory covers Resident, IDE, IDEX and M65D:

- 1,733 directory calls;
- 385 `CALLPRIM` calls;
- 63 not-yet-statically-bound `CALL`/`TAILCALL` sites;
- 29 not-yet-statically-bound targets;
- 53 native carrier-service calls;
- 10 intentional error sentinels.

Current mode remains an exact v1 allowlist: added, removed or count-changing
misses make the gate red. Zero-miss mode deliberately ignores this allowlist
and remains red while even one site is unresolved. Only an actual zero count
could release Checkpoint 4 and the carrier expansion.

## v2 staging closure

The internal v2 artifact set still consists of exactly Resident, IDE, IDEX and
M65D. The deterministic codemod changed 73 call sites; the bound differential
receipt compares 335 observations and reports zero differences from v1
behavior. The current inventory measures:

- 1,801 directory calls and 465 `CALLPRIM` calls;
- zero unresolved `CALL`/`TAILCALL` sites and zero unresolved targets;
- zero calls to v2 tombstones 1/2/34/40;
- 28 fully observed target classifications: three list `CALLPRIM`s, 14 static
  native services and 11 error services.

The number 28 is not an informal intermediate count. The closure manifest,
receipt and drift gate pin the exact partition. Primitive IDs 30--33, 35--39
and 41--45 carry native services; 34 and 40 are the permanent `%save-staged`
and `number->string` tombstones; 46--56 carry error services; the free/reserved
range begins at 57. The new code-59 service has its own diagnostic identity but
physically shares the text `compile failed` with the other compiler errors.

## Gates

```sh
make workbench-service-call-inventory-selftest
make workbench-service-call-inventory-current
make workbench-service-call-inventory-zero-miss
make workbench-service-call-inventory-staging
make v2-capability-carrier-check-host-2
make v2-capability-carrier-check-host-4
```

The v1 current mode remains green as a frozen evidence baseline; its zero-miss
target remains red by design. The separate v2 staging mode is zero-miss-ready
and is checked by the Checkpoint-4 gate together with the real carrier-cut ELF.
The ship lock keeps the staging profile unshippable through CP5.

## Runtime Core closure

`config/runtime-core-v2-service-registry.json` binds the internal v2 Runtime
Core artifact separately. The contract forbids tombstones 1/2 and the entire
Workbench service range 30--56, requires `STRICT_ARITY` in every CodeObject and
classifies every `CALL`, `TAILCALL` and `CALLPRIM` exactly. The first Runtime
App state contains four internal directory calls to `runtime-step`, no
`CALLPRIM`s, and no unresolved or unclassified sites. Every new site makes the
gate red until the product classification is deliberately extended.

```sh
make v2-runtime-core-service-inventory-check
make v2-callprim-runtime-cut-host-check
make v2-callprim-runtime-cut-mos-link
```
