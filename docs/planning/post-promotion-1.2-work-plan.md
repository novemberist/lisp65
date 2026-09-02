# Post-promotion work plan — v1.2 release and early 1.2.x

Status: **original plan complete; `require` foundation proven, `defstruct` parked**

Phase-R receipt:
`tests/bytecode/dialect-v2/evidence/post-release/v12-public-sync-preparation-receipt.json`.
No public ref, tag, release, product byte, or hardware state was changed.

Seal baseline: `c2-lite-r6-g6-hardware-acceptance-19aa835`,
product set `37998ce7…941d`. Product delta of every phase below is zero
unless a phase explicitly says otherwise.

## Ground rules (carry over from the intervention regime)

### Positive execution witnesses for permanent gates

“Artifact built” is not “gate executed.” Every new or changed permanent gate
therefore records `executed_cases` and an independently pinned
`expected_cases`. The chain canary accepts only `executed_cases > 0` and exact
equality; a missing, uninvoked, or partially run lane is red even when the
surrounding process exits zero. Variants count separately: a built but
unexecuted EXT, profile, or packaged-artifact lane is not evidence.

- Work **host-first**. Hardware needs are *collected*, not spent: every
  phase notes its device demand, and all demands are batched into at most
  **two bundled device sessions** (S1 mid-plan, S2 final).
- Delegation stays as commissioned: Class A (checkers/harness/replays)
  and the 32-byte convicted-one-liner rule run autonomously with batched
  reports. Class C halts are ONLY the numbered review points below.
- First-red discipline, receipts, SHA binding, claim hygiene: unchanged.
  In a bundled device session, First Red is **dependency-scoped**: it stops
  the failing row and every later row whose validity or state depends on it.
  Independent passive observations and feature-disjoint rows continue in
  the same physical session while the device remains in a defined, live
  state and the observation cannot overwrite evidence from the failure.
  A red fail-closed frame, crash, corrupted state or otherwise undefined
  device state remains terminal for the whole session.
- If any phase stalls on a Class-C question, skip to the next phase and
  queue the question; do not idle.
- **Stuck-debugging rule (owner-instructed 2026-07-27).** Long hunts are
  reviewed, not extended blindly. Stop and consult the reviewer before
  continuing whenever any of these is true:
  - the same symptom survived **two** attributed fixes (the third attempt
    is a review point, not a third guess — cf. the Slot-39 length saga:
    volatile copy → volatile source → stateless derivation);
  - a diagnosis has consumed **three** device sessions, or any hold/patch
    route was declared exhausted;
  - the evidence contains a **contradiction** between two proven layers
    (e.g. "linked truth says $0001, hardware says $0301") — a contradiction
    means a shared model assumption is wrong, and finding it is a reading
    task, not a search task;
  - the next proposed step is a fix whose mechanism is not yet attributed
    ("geraten"), or a fix that only moves the symptom.
  What to bring to the consultation: the exact contradiction or the
  surviving symptom, what each layer *proves* versus *assumes*, and the
  candidate discriminators already ruled out. What NOT to do: another
  hold variant, another hardware run, or a speculative product byte.
  Rationale: every deep bug of the C2 era was ultimately closed by a
  reading step (register liveness, ABI, CPU semantics), not by another
  capture — and the reviewer is cheap while device sessions and owner
  attention are not.
- **A lesson that lives only in a comment is not a lesson.** Any newly
  discovered platform, CPU or toolchain quirk gets a gate, or a written
  justification why no gate is possible. Prose alone does not close a
  class (precedent: the 65CE02 `STZ` = *store Z register* semantics were
  documented in a comment at link 19 and cost the link-71 frame overwrite
  regardless).
- **Z is a two-way ABI boundary.** The permanent source-derived assembler
  gate proves both that every `STZ` consumes Z=0 and that every regular
  handwritten return/tail or ASM-to-external call delivers Z=0. Interrupt
  entries separately prove restoration of the arbitrary interrupted Z.
  Source-only comments and leaf allowlists are not boundary evidence.

## Phase R — Release v1.2 (paper/host only, no device)

R1. Release-notes draft from the promotion evidence: cure retirement
    (1-frame cold / 0-frame warm vs the dated 1.1 exception), KERNAL
    takeover + L-full keys, crash tolerance (byte-identical rollback,
    usable REPL after break), DIRMISS name diagnostics, C2-lite
    foundation, documented limitation (freezer during active definition
    → C2.3), informative positions (68-frame argument call, GC envelope,
    27-s boot including staging).
R2. Retirement certificate for the 1.1 latency exception in the known-
    issues register; erratum text for the freezer limitation.
R3. Docs commit + index + push with tag/refset ritual.
R4. Public-repo sync per §15c: curated patch set, archive gate, DCO.
    Prepare fully; **do not push the public release**.
→ **Class-C halt #1:** owner reviews release notes + scope (slim release
   recommended) and gives the publish go. One decision.

## Phase U — Upstream package (paper only)

U1. Refresh L4–L7 drafts against current repo state; keep the L1
    NOT-reproduced verdict and the filing bar.
U2. Finalize L8 (lld /DISCARD/ vs .llvm_sympart) with the archived
    minimal repro references.
U3. Finalize L9 (llvm-mos DEW codegen) with the link-32/33 byte diff.
U4. Finalize L10 (DMA visibility vs spec) with the 691-ms curve,
    core git-03b24c6b, and the enhanced-vs-normal rail observations from
    the G5 tool saga as corroborating notes.
U5. One paste-ready bundle document for the owner; nothing is filed by
    Codex. (L3's pending hardware smoke rides device session S2 if the
    owner wants it; otherwise it stays parked.)
→ No halt. Deliverable lands in the owner's queue.

## Phase F — 1.2.x freight, host-first (prioritized worklist, 2026-07-27)

Ordering rule: strictly host-first; an item blocked on review is parked
and the next item starts. Nothing reaches hardware before session S1.

F1. **N-ary direct call** — priority 1 (user-visible latency, known
    approach). Contract note first: which call shapes qualify (published
    entry, fixed arity, no &rest?), what falls back to the ceremony.
    Lisp-level implementation on the healed nullary pattern, host parity
    + equivalence suites, WPLTO. Expected cost: Bank-2 bytes, zero
    resident — verify, don't assume.
F2. **Bitops** — priority 2 (unblocks `random`/xorshift, games niche).
    Revive the ABA-gated opcode cut against C2-lite truth: VM dispatch
    cases are resident (134-B text reserve is the wall); catalog/ABI
    freight rides Bank 2/5. Full negative classes from the original cut,
    plus dialect-surface doc updates.
F3. **gc/room/error trio** — priority 3 (SHOULD freight, host-green
    since 1.1; contract: shared carrier, no resident dispatcher).
    Re-derive the shared-carrier cut against C2-lite phases; expected to
    be overlay-only. If its WPLTO shows any resident demand, park it for
    halt #2 discussion rather than negotiating walls.
F4. **Argument-call measurement harness** — prepare the S1 lines now
    (n-ary cold/warm, bitops smoke vectors, gc/room/error smoke,
    regression lines for nullary + boot) so S1 stays one session.
F5. **Stretch, only if F1–F4 are parked on review:** host-side design
    probe for `while`-vs-`catch/throw` (the committed 1.2 non-local-exit
    decision) — paper contract comparing both against the unwind
    machinery that C2-lite now actually has (C2J landing, transient
    edge). No implementation; feeds the post-F review.
→ **Class-C halt #2:** all WPLTO balances reviewed together, then ONE
   product link carrying the approved subset (F1 mandatory; F2/F3 if
   green), then **device session S1**: bundled presmoke per F4. Single
   session, instruments preloaded, sammelsitzung rules.

Completion (2026-07-27): halt #2 approved F1+F2 and parked F3.  Link 67
contains exactly F1+F2.  S1 passed 12/12 rows on hardware after one
harness-invalid attempt with zero accepted product rows: n-ary call
`1f/20ms` cold and `0f/0ms` warm, nullary regression `0f/0ms` both times,
bitops positive/negative behavior, usable REPL and idle-Freezer identity.
F5 selected `while`; implementation remains a later freight item.

## Phase H — Housekeeping (Class A, fully autonomous, interleaved)

H1. Finish the elf_truth migration for all remaining gates; retire the
    last private ELF views.
H2. Receipt/index hygiene: document index green, evidence tree
    consistency check, promotion register cross-check.
H3. Archive dead files (lib/m65-disk-alloc*.lisp) per the old phase-4
    backlog; German-comment go-forward check on files touched since
    v1.1.0 (live files only, sealed fixtures exempt).
H4. Idea-store maintenance: fold the C2-era lessons that are marked for
    the workbench/library era into extension-libraries-design.md
    (transport doctrine for libraries, random/ring-buffer pairing note
    already present).
→ No halts. Batched report.

## Phase W — Workbench-era ramp (design only, no code)

W1. Re-derive the library/workbench capacity budgets from the sealed
    v1.2 geometry (session store, Bank-5 scratch, C2D dimensions) so the
    first library probes start from numbers, not estimates.
W2. Draft the `require`/manifest v1 contract against the C2-lite append
    machinery (explicit cold loads, restart-repl as composition switch
    pending C2.3).
→ **Class-C halt #3:** review of W1/W2 opens the library era.

Halt #3 package (2026-07-27): **review-ready**.  W1 derives the nonfungible
Bank-2, C2D, Session-store and resident currencies from the sealed v1.2 set
and Link 67.  W2 proposes strict L65P-v1, one generated identity-bound
library index, a generated resolution lock and explicit generation-scoped
`require`.  The paper gate rejected 24 mutations.  No implementation,
product byte, product link or hardware run is authorized before the review.

Review note:
`docs/planning/c2.2-workbench-era-ramp-halt3.md`.
Receipt:
`tests/bytecode/dialect-v2/evidence/architecture-blocks/c2.2-phase-w-workbench-ramp-halt3-receipt.json`.

Disposition (2026-07-27): all three Halt-#3 decisions accepted.  The
host-first `require`/index/L65P-v1 probe was authorized and has passed:
one canonical-reader data form, one generated identity-bound index, one
resolution lock, generation-scoped idempotence, 12 append cutpoints and
38 negative mutations.  The measured probe impact is zero resident bytes,
zero product bytes, zero links and zero hardware runs.  Target implementation
was not yet authorized at this point.  The first freight order was
`defstruct`, then `random` on the ring buffer with lagged-Fibonacci baseline
and an xorshift option.

Superseding disposition (2026-07-28): the `require` foundation is hardware
proven (`t` on first load and generation-idempotent repeat), but
`(defstruct point x y)` entered the red fail-closed frame.  Owner-selected
Option A parks `defstruct` and removes it from active 1.2.x freight.  No next
library is activated automatically.  The complete First-Red/restart package,
including the R-1 IRQ gap, R-2 latency attribution and R-3 method note, is:
`docs/planning/c2.2-link75-defstruct-red-frame-owner-decision.md`.

## Device sessions

- **S1** (after halt #2): F1/F2 measurement + regression lines. One
  session, all instruments preloaded, dependency-scoped First Red per the
  ground rule above.
- **S2** (optional, owner's call): release-medium spot check of the
  public artifacts + L3 smoke if the owner wants to file it.

## Explicitly out of scope

C2.3 items (restart-repl, freezer-during-definition, E3/E4), ship
builder, `while`/`show`/parity revalidation beyond what release notes
state, and any resident-capacity negotiation — the terminal geometry of
the seal stands until a 1.2.x cut earns its own review.
