# Project-wide housekeeping block

Status: **commissioned by owner 2026-07-29, after v1.2.2**

Baseline: released v1.2.2, public main `43a7ba63…`, tag `e7cfba34…`.
Product delta of this entire block is **zero** unless a phase explicitly
says otherwise and passes the normal gates.

## Why now

Four releases, one abandoned architecture (C2-full), its successor
(C2-lite), a closed resident geometry and six parked work strands have
accumulated material whose status currently lives mainly in the heads of
the owner and the reviewer. That is the debt this block repays.

## Non-negotiable rules for this block

1. **Bound evidence is immutable.** Receipts, seals, promotion records and
   hardware captures are never edited, moved silently or "tidied". They may
   be *indexed* and *classified*; they are never rewritten.
2. **Nothing is removed that something cites.** Before any deletion or
   move: search gates, configs, Makefiles, docs and receipts for references.
   A missing citation target is a broken gate, and a broken gate is worse
   than a messy tree.
3. **First-red discipline applies to housekeeping too.** A sweep is exactly
   the situation that breeds "gate checks the source instead of the
   artifact" defects. Every phase ends with its own receipt.
4. **The block ends with a full verification pass** (see H-F). Housekeeping
   that is not verified is not housekeeping.

## Phase H-A — Inventory only, no changes (do this first)

Classify **everything** into `live` / `historical` / `dead`, with a
one-line reason each. No file is touched in this phase.

A1. **Planning documents** (~226 indexed). Live = a contract or plan that
    still binds behaviour. Historical = a true record of a decision or a
    first red, kept for citation. Dead = superseded with no citation.
A2. **Config contracts** (`config/*.json`). Which bind the current product?
    Which describe retired formats (L65S-v3, C2I-v1, C2D-v1…v5, L65R-v1…v3)?
    Flag anything a gate still reads.
A3. **Tools** (`tools/host-lisp/*.py`). Split **permanent gates** (wired into
    `check-source` / `workbench-product` / equivalence) from **one-off
    probes** built for a single investigation. Name each one's owner phase.
A4. **Sources.** Retired subsystems still in the tree: L65M materializer,
    C1 compiler tier, old decoders/emitters, `lib/m65-disk-alloc*.lisp`,
    `src/l65m_batch_repeat.s` (proven not linked in the C2-lite profile).
    For each: still compiled? still linked? cited by a gate?
A5. **Evidence tree.** Count and group by era. Propose a *grouping* scheme
    only — no deletion, no rewriting.
→ **Class-C halt 1:** owner/reviewer review the inventory and approve what
   may be touched. Nothing moves before this.

## Phase H-B — Documentation consolidation

B1. **Split live contracts from historical record** in the index: two
    clearly marked sections, so a reader can tell in one glance what still
    binds and what merely happened.
B2. **One parked-items register.** Today the parked strands live in six
    documents. One register, one line each: what is parked, why, what the
    restart package is, what would reopen it. Items: `defstruct` /
    dynamic library freight, `gc`/`room`/`error` trio, GC envelope cut (G3),
    the intermittent unreproduced post-GC OOM, the mute fail-closed guard,
    C2.3 (restart-repl, freezer-during-definition).
B3. **One permanent-gate register.** Every gate that must keep running:
    purpose, what it would catch, where it is wired, and its execution
    witness. This is the antidote to the "gates die with their carriers"
    family, which cost this project four separate incidents.
B4. **Known-issues audit.** Verify the published known-issues list is
    complete against B2 — every parked item that a user could encounter has
    a user-language entry.

## Phase H-C — Source and tool debt

C1. Archive dead sources approved in H-A (move, do not delete; keep them
    findable). Prove non-linkage from the ELF, not from intuition.
C2. Retire one-off probe tools or move them to a clearly marked
    `probes/` area so nobody mistakes them for gates.
C3. Finish the `elf_truth` migration if any private ELF view survives, and
    retire it. (Long-standing H1 item.)
C4. Retired-format decoders: confirm the no-dual-decoder rule holds in the
    *linked* product, and that dead format code is not merely unreferenced
    but structurally excluded.

## Phase H-D — Comment language

D1. Complete the German→English translation of live source comments
    (~1,311 lines mapped historically; sealed fixtures remain exempt —
    their SHA identity binds their bytes). Boy-scout rule stays for future
    edits; this phase closes the backlog in bounded batches.
D2. Verify the go-forward gate covers every live file.

## Phase H-E — Repository and infrastructure hygiene

E1. `git gc`; verify the archive gate (index/commit/history/push) still
    rejects its four classes.
E2. Delete or archive the obsolete 661 MB wave-2 bundle in
    `~/Videos/lisp65-backups/` — owner action, reviewer recommends deleting
    it: it predates the history surgery and is superseded by release assets.
E3. Verify the public repository is in sync with v1.2.2 and that the
    clean-build gate reproduces the sealed product set from a fresh clone.
E4. Cross-check the promotion register against the four published releases.

## Phase H-F — Closing verification (mandatory)

F1. Full equivalence chain with execution witness (lane count and case
    count non-zero and as expected).
F2. `workbench-product` clean build from a fresh checkout, reproducing the
    sealed v1.2.2 product set byte-for-byte.
F3. Document index green; receipt tree consistent; every citation in the
    two new registers resolves.
F4. One closing receipt for the whole block.
→ **Class-C halt 2:** results reviewed; block closed.

## Explicitly out of scope

Any product-behaviour change, any parked-item work, any capacity
renegotiation, any release. This block ships nothing; it makes the next
thing that ships cheaper.
