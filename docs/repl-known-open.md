# REPL Runtime Reproduction Registry

Updated: 2026-07-15. The machine-readable source is
`tests/bytecode/runtime/p0-runtime-known-open.json`; the fail-closed gate is
`make runtime-known-open-check`.

## Current state

No active runtime known-open cases remain:

- `known-open=0`
- `resolved-g5=2`

The former native REPL surface gap for `when`, `unless`, `let*`, and `case`
remains closed by `make repl-surface-smoke`. The two former hardware-only
higher-order reproductions are now manifest-bound and closed on real MEGA65
hardware:

- `(every (function plusp) '(1 2 3))` -> `t`
- `(some (function (lambda (x) (if (> x 2) x nil))) '(1 2 3))` -> `3`

The authoritative narrow receipt is
`tests/bytecode/runtime/evidence/ap8.1-g5-78083d6/receipt.json`. It binds commit
`78083d6b79df189e97c617577f7b89d62d4a3219` and Ship-v5 manifest
`275723fb7259261c9606cee6a0dcc17c593a4cbf9c77f44b482d7cd031d5e211`.
Both exact apostrophe source forms ran twice after a persistence remount and
twice after a long IDE+IDEX search/repeat state, with reversed ordering between
the two states.

This closure means that the historical hang is not reproducible in the four
pinned product phases. It does not claim a root cause, a general evaluator
proof, or an independent release claim.

## Historical diagnostic

The minimal diagnostic PRG using `-DVM_STEP_LIMIT` and
`-DLISP65_VM_DIAGNOSTICS` remains available for historical reproduction:

```sh
make mvp-vm-stdlib-known-open-diagnostic
make hw-known-open-diagnostic-dry-run
scripts/hw-known-open-diagnostic.sh --no-build
```

It embeds only `plusp`, `every`, and `some`, so it is not product evidence. The
closure comes exclusively from the verified-only Workbench G5 harness.

## Gate contract

Registry v2 allows `known-open` and `resolved-g5`. Every resolved case must
reference a checked-in receipt and exactly two product phases; an open case must
not carry a resolution. The gate also checks:

- unique cases, statuses, surfaces, and native REPL handoffs;
- repository-relative evidence paths without traversal or symlinks;
- receipt and file SHA-256 values plus a complete evidence inventory;
- a clean commit/tree, Workbench profile, manifest status, and G0–G2;
- live-memory receipts and byte-identical staged/post-reset readbacks;
- exact apostrophe materialization, two loads per state, and reversed ordering;
- the final semantic result and empty follow-up prompt through
  `repl_screen_check`;
- 15 negative mutations covering status, receipt, provenance, state, and
  evidence drift.
