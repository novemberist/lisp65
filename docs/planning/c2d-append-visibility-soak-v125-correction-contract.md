# v1.2.5 corrected C2D append-visibility soak

Status: **commissioned successor, 2026-07-31**. Measurement only; zero
product bytes, zero product links.

This is the corrected execution of Part 2 of
`c2d-append-visibility-measurement-contract.md`. The first attempt was not
a soak: it mounted the released product D81, which contains no `L65INDEX`
or `PLACE`, and stopped on the resulting expected `require` `nil` before
batch 1. The v1.2.4 resolver-order defect found along the way was fixed and
released as v1.2.5.

## Bound preconditions

Before a device result can be claimed, the runner must:

1. cold-reset and prove a fresh BASIC `READY.` screen;
2. inventory the mounted package medium and bind visible `L65INDEX`,
   `PLACE`, and `DEFSTRUCT` payloads;
3. upload and read back that exact medium byte-for-byte;
4. deploy the exact Link-82/v1.2.5 product and all seven preloads from the
   already hardware-proved v1.2.5 deployment authority;
5. create the two ordinary persistent helper definitions **before**
   `(require 'place)`, preserving the state that exposed the v1.2.4 bug;
6. require `place` successfully, prove that its row was published at the
   live next slot, and prove C2J `CLEAR`.

Wrong medium, stale product identity, absent package files, or a failed
precondition is harness red, never product evidence.

## Measurement

- 31 batches × 60 transient append/read cycles = 1,860 cycles.
- Batch starts span at least 1,800 seconds of live session time.
- Six additional persistent definitions are introduced at batches
  5/10/15/20/25/30.
- Every batch proves:
  - idempotent `require` leaves the complete C2D plane byte-identical;
  - transient work leaves the complete persistent C2D plane byte-identical;
  - C2J is `CLEAR`, phase owner is none, and the transient watermark is
    quiescent;
  - semantic mismatch, `mem_oom`, and `gc_badobj` deltas remain zero.
- The first mismatch, OOM, red frame, non-exact result, or state invariant
  failure stops feature activity and captures the failed state immediately.

## Pre-registered interpretation

- Clean at ≥1,800 cycles and ≥30 minutes: bounded exoneration of the
  Chip-RAM append/read path at soak scale. The intermittent post-GC OOM
  remains open, but Chip-RAM visibility is retired as its active suspect.
- Any anomaly: no fix is implied. The captured state returns as a named
  Class-C review item before the B3 direction decision.

The runner and receipt are non-promotable measurement artifacts. They make
no C2-full, acceptance, release, or general DMA claim.
