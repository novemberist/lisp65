# Post-1.2.4 roadmap — two tracks, one owner checklist

Status: **current, 2026-07-31** — v1.2.5 published and readback-verified;
the deterministic prior-append `require` defect is fixed and permanently
gated. The corrected package-bound soak is complete and clean. Track A is
closed; B3 is now the owner's prepared direction decision.

## Track A — implementation lane (Codex)

A1. **Finish the publish ritual** (**complete**): push the public
    candidate, tag, release with the four assets, download-and-verify
    readback, final publication receipt. Reviewer checks it afterwards.
A2. **The soak session** — first post-release item, contract already
    bound (`c2d-append-visibility-measurement-contract.md`, part 2):
    ≥1,800 append/read cycles over ≥30 minutes of genuine session life,
    cold-reset rule, second-sighting peek protocol on first anomaly.
    Outcome shapes everything after it:
    - **clean** → the Chip-RAM transport hypothesis is retired at soak
      scale; the intermittent family's next suspect is
      session-accumulated state; the direction decision (B3) proceeds
      unblocked;
    - **mismatch/anomaly** → the prepared Class-C publish-last review
      item goes to the owner table first; the direction decision waits.

    **Disposition 2026-07-30:** stopped before batch 1 because the harness
    mounted only the released product D81; that medium contains no
    `L65INDEX`, `PLACE` or `DEFSTRUCT`. The resulting `require` `nil` is
    therefore not a product second sighting. The captured C2D/C2J/phase
    bytes remain valid raw evidence, but their old boundary-1 product
    interpretation is superseded.

    The required host-first follow-up independently found a real, deterministic
    ordering defect: against valid product-bound package media, the exact
    v1.2.4 resolver returns `t` from the six-image boot state and `nil` after
    the exact `%s`/`%sr` persistent appends. `%require-world` rejects the first
    ordinary Session row because its identity is not in L65INDEX, before any
    media-stage or append call. Authority:
    `tests/bytecode/dialect-v2/evidence/post-release/post-v124-require-prior-append-h1-receipt-20260730.json`.
    Owner table:
    `docs/planning/post-v1.2.4-require-second-sighting-owner-review.md`.

    **Corrected successor prepared 2026-07-31:** v1.2.5 fixed the attributed
    resolver contract, and
    `c2d-append-visibility-soak-v125-correction-contract.md` now binds the
    exact Link-82 product, the already hardware-proved package D81, its
    `L65INDEX`/`PLACE`/`DEFSTRUCT` inventory, all seven preloads, and the
    original two-helper-before-`require` order. The 30-minute/1,800-cycle
    measurement then completed: **1,860 cycles over 1,815 seconds, 44
    collections, eight persistent definitions, 32 successful `require`
    rows, zero mismatch/OOM/`gc_badobj`**. C2J was `CLEAR`, phase owner none,
    and complete C2D readbacks were byteidentical across every idempotent
    `require` and transient batch. The package upload/readback was
    byteidentical. This is the pre-registered bounded exoneration: Chip-RAM
    append visibility is retired as the active suspect for the single
    Link-77 post-GC OOM; that OOM itself remains open as a one-time
    observation.

    Authority:
    `tests/bytecode/dialect-v2/evidence/post-release/post-v125-corrected-soak-hardware-receipt-20260731.json`.
    One harness-first-red before batch 1 (m65 stderr mixed into screen text)
    was preserved separately and closed by a stream-separation selftest.
A3. **Upstream bundle refresh** (**complete**, Class A, paper): update the L10 section
    of `docs/upstream-owner-bundle-2026-07-27.md` with the current-core
    reproduction (2 ms: 1132/1156 bytes wrong, CRC `$1490`; exact at
    714 ms and 2,414 ms, CRC `$E856`) and run the bundle's stated final
    upstream recheck against current llvm-mos / mega65-core HEADs, so
    every paste-ready bar is discharged and the owner only pastes.
    Report which items remain paste-ready afterwards.

    Disposition 2026-07-30: L4 was narrowed because the current Porting
    guide already documents the general complete-script case. L4–L7 and
    L11 remain owner-paste-ready after current-doc/current-HEAD and duplicate
    searches. L10 now carries both measured curves and its claim limits, but
    its mandated target is unavailable: `MEGA65/mega65-core` reports
    Discussions disabled. It must not be filed as an Issue. Machine authority:
    `tests/bytecode/dialect-v2/evidence/post-release/post-v124-upstream-bundle-refresh-receipt-20260730.json`.
A4. **L8/L9 reduction** (optional, low priority, background): both are
    "not file-ready" until reduced outside lisp65 and rerun on current
    toolchains. Only worth doing when idle; never blocks anything.

## Track B — owner checklist

### B1. After Codex reports A1 complete — nothing to do

The reviewer verifies the publication (assets, SHAs, receipt) as with
every release. You only hear about it if something is wrong.

### B2. File the upstream items (A3 recheck done)

Five items are currently copy-paste-ready from the bundle document
(`docs/upstream-owner-bundle-2026-07-27.md`). Codex's A3 refresh will
has discharged their final-recheck bars, so each step is: open the target,
paste the section's **Paste-ready text**, submit. L10's text is ready but its
submission surface is blocked; keep it queued rather than turning it into an
Issue.

| Step | Where | What | Item |
|---|---|---|---|
| 1 | github.com/llvm-mos/llvm-mos → Issues → New | custom-section placement (documentation/ergonomics proposal) | L4 |
| 2 | same | 45GS02 Z-register invariant (target ABI documentation) | L5 |
| 3 | same | DMA-list stores / MMIO trigger (MMIO+LTO documentation) | L6 |
| 4 | same | 16-bit pointers vs 28-bit addresses (documentation; explicitly *not* a compiler bug) | L7 |
| queued | github.com/MEGA65/mega65-core → **Discussions** (not Issues) | Attic Enhanced-DMA completion visibility, with both curves and the written claim limits; repository Discussions are currently disabled | L10 |
| 5 | mega65-core → Issues (documentation correction) | Audio-DMA interrupt documentation vs tested/current-core RTL; closed #811 is implementation history, not the docs fix | L11 |

Rules that protect you: paste only sections whose filing state permits
it; do not strengthen any claim beyond the written text (L7 and L10
carry explicit "we are not claiming a bug" limits); if an upstream
maintainer asks for a reproduction, that request comes back here as a
commissioned item — you never improvise one in the thread.

**Question you answer in this step:** none for L4–L7/L11 — their texts are
final. L10 waits for an approved discussion surface. If that surface opens
after the soak and the soak finds a Chip-RAM anomaly, the discussion gains a
second data point; otherwise the two existing curves remain the complete
packet.

### B3. The direction decision — after the soak, one question

When A2's result is on the table, the reviewer prepares a one-table
Class-C menu for the next block. The candidates, honestly
characterized, so you can start thinking now:

1. **Ship builder (the 1.3 promise).** `(ship "program" :entry 'main)`
   → standalone bootable D81. The standing product order — "a
   redistributable ship path precedes ecosystem breadth" — and it
   unlocks the parity pilot (`m65-hw`, 2,048-byte envelope, fully
   revalidated and waiting). Largest scope, largest unlock.
2. **Tick hook implementation.** The contract is drafted
   (`VM_YIELD_SAFE`, top-level scheduler only); this is the enabler for
   MOVSPR/PLAY/SOUND-class parity — the games era. Medium scope;
   requires the separately-proved resumable scheduler.
3. **defstruct restart** (R-1/R-2/R-3 package). Reopens the parked
   fail-closed cause hunt; also the gate for `long` and
   `defstruct/packed`. Uncertain scope — it starts with an unattributed
   hardware fault.
4. **C2.3 / `restart-repl`** (composition switching). The clean partial
   answer to the full session wall (113 B) and the practical Attic
   payoff without L10. Medium scope, architectural.
5. **Editor input latency** (owner-reported 2026-07-30, **owner
   priority: "not usable"**): laggy typing, dropped keystrokes at
   moderate speed on released v1.2.4. Host-first measurement is complete:
   serial redisplay allocates 169.26 cells/key and derives 0.882
   collections/key; ten-key coalescing still derives 0.248. The observed
   shape is fast work plus 89-frame pauses, with a four-collection wrap
   spike. Authority:
   `post-v1.2.5-editor-input-latency-host-attribution.md`. The
   `gc`/`room`/`error` reopening condition has fired with `room` first.
   An owner "not usable" on the flagship surface outranks era-comfort
   candidates in this menu.

**Question you will answer:** which one leads the next block (they are
not mutually exclusive forever — this picks the *next* era's core, as fx
picked 1.2.4's). No answer needed until the soak lands.

**Current gate:** none. The v1.2.5 `require` repair is released and its exact
prior-append acceptance row is hardware-green; the corrected soak is clean.
B3 is open. None of its direction candidates is commissioned until the
owner chooses one.

### B4. Standing items, unchanged

- The four R6/G6 archives and the promotion-archive cache policy: green,
  nothing to do.
- `gc`/`room`/`error`, color-scroll, `long`, parity pilot: parked with
  registered reopening conditions; they surface via B3 or capacity
  changes, not via your checklist.

## Order of events

```
done     A1 publish ritual ──→ reviewer verification
done     A3 bundle refresh ──→ B2 five owner filings; L10 queued
stopped  A2 v1.2.4 attempt ──→ wrong medium before batch 1
done     H1 attribution ──→ v1.2.5 Option-A fix and permanent gate
done     corrected A2 ──→ clean 1,860-cycle/30-minute soak
open     B3 direction decision
```


## Sequence confirmed by owner — 2026-07-31 (balance review)

Prompted by the owner's question whether the project parks more than it
delivers, the balance was drawn (six releases this era; every completed
attribution landed on our side, never the core; exactly one parked item
is core-gated). Confirmed sequence:

1. **Now:** the fail-closed load attribution (running, Class B,
   host-first) — also the defstruct gate.
2. **Next block: the ship builder** — the 1.3 promise, the largest
   user-value item independent of every park; it unlocks the parity
   pipeline. Its work plan is written when the attribution reports.
3. **Owner, parallel:** the L4–L7/L11 upstream filings (paste-ready) and
   L10 when a discussion surface opens — so the one true core dependency
   lives upstream with our curves attached.

Standing lesson booked from the editor series: for state-dependent
target-only faults, the Option-3 product-witness class is the
medium-term answer; twelve contacts for zero peeks must not repeat.
