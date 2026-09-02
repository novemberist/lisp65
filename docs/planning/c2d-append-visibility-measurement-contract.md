# Chip-RAM append visibility — measurement contract

Status: **commissioned 2026-07-30** (reviewer, under the standing concern
review with the owner). Zero product bytes; measurement only.

## The question, stated before any number exists

L10 is now reproduced on the current core: Attic DMA writes converge only
after ~714 ms (at 2 ms, 1132/1156 bytes differ). C2-lite removed runtime
Attic reads for exactly this reason. The Link-77 post-GC OOM remains one
unattributed observation on a **Chip-RAM Bank-5/C2D path**. The former
second member of that family, Link-80 `require` `nil`, has since been
attributed to a resolver-contract defect: ordinary persistent Session rows
are rejected because their identities are absent from L65INDEX. It is no
longer evidence for a Chip-RAM visibility problem. Whether a milder Chip-RAM
variant of L10 exists remains worth measuring, but this contract now has one
intermittent trigger rather than two.

Pre-registered interpretations, fixed now:

- **Any CRC mismatch at immediate read-back** on the Chip-RAM curve means
  a Chip-RAM visibility variant exists → the publish-last write path gets
  a named review item (Class C, owner table). One mismatch is enough; the
  count and delay profile are the data.
- **All points exact across all cycles** is a bounded exoneration: it
  does not close the intermittent family (the anomalies may be elsewhere),
  but it retires the "Chip-RAM L10 variant" hypothesis at the measured
  cycle count, and the family's next suspect becomes session-accumulated
  state rather than transport.
- These rows are measurement, not acceptance: they cannot make any chain
  red, and a red chain row does not invalidate them.

## Part 1 — curve rows, riding the v1.2.4 G5 session (no extra contact)

Precedent: the v1.2.2 G2 measurement rode G5 as extra rows. Same rules:
after the acceptance rows are complete, in the same live session.

1. **Chip-RAM curve, L10-comparable:** one product-pattern DMA append to
   Bank 5 (256 bytes), then DMA read-back at the same probe points as the
   L10 instrument (immediate, 2 ms, 100 ms, 714 ms), CRC per point.
2. **Repetition for frequency:** the immediate-read cycle repeated 20
   times, mismatch counter reported even when zero.
3. The **require peek map** (trace `0x0000c1f4`, header `0x00050000`,
   requested row derived from the live pre-require image count) captured
   once after the rows. A fixed `$500f0` address is forbidden after prior
   appends.

## Part 2 — the soak session (first item after the v1.2.4 release)

The anomalies appeared **late in long sessions**; a curve cannot see
that. One dedicated post-release session, cold-reset rule as always:

- ≥ 1,800 append/read cycles spread over ≥ 30 minutes of genuine session
  life (definitions and GC activity), CRC per cycle, running mismatch and
  GC counters on screen;
- on the **first** mismatch or any anomaly signature (`nil`, OOM): stop
  feature activity, capture the peek map against the failed state
  immediately — this is the second-sighting protocol the parked rows
  have been waiting for, executed proactively instead of passively;
- a clean soak binds its cycle count as the exoneration figure.

**Harness correction before any retry:** the first post-v1.2.4 attempt
mounted only the released product D81, which contains no L65INDEX or package
artifacts, and therefore stopped on an expected `require` `nil` before batch
1. A corrected harness must inventory and bind the mounted package medium
before calling `require`. It must also resolve the separately attributed
“require after persistent append” product policy rather than hiding it by
reordering setup forms. The soak remains not started.

## Boundaries

No product fix, no link, no C2-full work, no publish-path change follows
from this contract directly — findings return as prepared Class-C items.
Host dry-runs prove the scripts; the timing claims are device-only (xemu
does not model DMA timing). The instruments to reuse: the L10 curve
driver, the Link-80 peek map, the M1 atomic-transaction harness rule.
