# Commission: while/random delivered-head disposition

Status: **completed 2026-07-30** — implementation lane (Codex).
Reviewer contact rule applies: on complex problems or grinding debugging,
align with the reviewer before searching further.

Completion receipt:
`tests/bytecode/dialect-v2/evidence/architecture-blocks/while-random-disposition-receipt-2026-07-30.json`.
Both surfaces remain landed; no repin was required. All 56 recovered patch
hunks were individually rejected as parked G1 work, and all named gates are
green except the separately documented bound-carrier tier-generation
precondition.

## The situation

`check-source` was not green on `b8405551`, the head that shipped v1.2.2,
and it is not green today. Four gates fail identically there and here:

1. `dialect-v2-prelude-evidence-selftest` — `v1 macro source/contract
   drift: missing=['while']`: the contract lists `while` among the v1
   macros, but none of `lib/prelude-m1.lisp`, `lib/stdlib-control.lisp`,
   `lib/stdlib-places.lisp` defines it any more.
2. `v11-surface-delivery-parity-check` — `random` and `random-seed` are in
   the language reference with no surface, registry or library delivery.
3. `bytecode-p0-omission-contract-check` — `%lcc-proper-list-p`, `%lcc-rel8`,
   `%lcc-while` omitted without declaration in
   `tests/bytecode/demos/p0-demo-suite.json`.
4. `v11-function-metadata-selftest` and `workbench-ux-harness-selftest`,
   downstream of the same surface state.

Root cause of the silence is closed: the release chain never required
`check-source` (see the binding rule in
`docs/reference/gate-and-tool-register.md`). This commission is about the
reds themselves.

## Recovered work to triage first

On 2026-07-29 the housekeeping block fast-forwarded a dirty working copy;
its content was backed up and has now been secured at
`~/Videos/lisp65-recovered-work-20260729/` (a 1,258-line
`tracked-modifications.patch` plus an `untracked/` set whose files are
meanwhile all in the tree). The patch still applies forward-clean at
`a98ba0da`, so it was never landed. It touches `error_overlay`,
`buffer_overlay`, `c2_random_base_gate.py`, `error-texts.json` (a code-64
user-message row), the state-error-carrier contract and the 1.2.2 worklist.

**Task 0:** sight the patch. For each hunk: land it, or reject it with one
line of reasoning in the receipt. Do not let it rot as a patch file — after
this triage the backup directory can be deleted.

## The disposition itself

**Task 1:** establish the actual state of the v2 `while` and `random`
surface work (phase V). Then choose per surface, with reasoning:

- **Land it:** finish the sources the committed contracts already promise,
  through the normal chain (host-first, first-red discipline, execution
  witnesses). This is the preferred outcome if the work is close.
- **Repin it:** if the work is far from landing, repin the contracts to the
  delivered surface so the four gates are green on truth rather than on
  promises. A repin is a Class-C item: prepare it, do not decide it —
  bring it to the owner halt.

**Task 2:** whichever path, the exit criterion is fixed: **all four gates
green on a clean tree**, so that `check-source` is green (minus the one
documented parity precondition) for the first time since v1.2.2 shipped.

## Ground rules

Unchanged: substitutive-never-additive, receipts with execution witnesses,
dependency-sharp first red, no inherited green. The resident geometry is
closed; nothing here authorizes resident bytes. No release, no promotion —
this ends at a Class-C halt with results on the table.
