# Post-v1.2.5 B3 direction menu

Status: **owner-disposed 2026-07-31: editor latency leads the next block**
(`1.2.6-work-plan.md`). Successor order noted: ship builder, tick hook,
C2.3, then the uncertain defstruct restart. It consolidates the editor attribution and the completed corrected
soak into one decision.

## Facts now on the table

- v1.2.5 is published; `require` after ordinary persistent appends is fixed,
  permanently host-gated, and hardware-proved.
- The corrected soak completed 1,860 cycles over 1,815 seconds with 44
  collections, eight persistent definitions and 32 successful `require`
  rows. There were zero semantic mismatches, OOMs or bad-object reports.
  Complete C2D snapshots stayed byteidentical across every idempotent
  `require` and transient batch. Chip-RAM append visibility is therefore
  retired as the active suspect at this soak scale. The old post-GC OOM
  remains a single unreproduced observation.
- The editor complaint is host-attributed, not anecdotal: serial redisplay
  allocates 169.26 cells/key and derives 0.882 collections/key; ten-key
  coalescing still allocates 47.62 cells/key and derives 0.248
  collections/key. A wrap key reaches 722 cells and can contain four
  collections. With the accepted 89-frame target collection envelope this
  is a credible mechanism for visible stalls and dropped input.
- Resident geometry remains closed. New work must live in Bank 2, an
  existing overlay/cold phase, or not ship.

## Decision table

| Candidate | User value | First bounded block | Known price / risk | Exit from the block |
|---|---|---|---|---|
| **1. Editor latency** | Repairs the flagship surface the owner called “not usable” | Contract an allocation ceiling; remove per-render typed-line list materialization in Bank 2; retain/cohere input coalescing; reopen a smaller `room`-first instrument only if it fits without correctness-phase fusion | Best-attributed candidate. Existing G1 trio is 399 B over the Session geometry, so it cannot be revived unchanged. No resident byte is available | Host allocation gate shows no multi-GC key and a large reduction from 169.26 cells/key; one target typing/queue session measures latency and dropped input |
| **2. Ship builder** | Delivers the 1.3 promise: `(ship "program" :entry 'main)` → standalone D81; unlocks the parity pilot | Freeze media/entry contract, build host ship image and reproducibility lane before hardware | Largest scope and largest ecosystem unlock; crosses product/media tooling but need not touch resident geometry | Two clean builds produce the same bootable image; one bundled boot/entry session |
| **3. Tick hook** | Enables game scheduling and MOVSPR/PLAY/SOUND-class work | Promote the drafted `VM_YIELD_SAFE`/top-level-only scheduler contract, then host scheduling model | Medium architectural scope; must prove no callback inside GC, append, overlay or publication ownership | Deterministic host schedule plus one device cadence/abort session |
| **4. C2.3 / `restart-repl`** | Composition switching and practical relief from the closed Session wall | Contract restart boundary and state disposal; host-first composition transition | Medium architectural scope; deliberately touches lifecycle and restart semantics | Clean restart swaps composition without stale Session identity or published-state leakage |
| **5. `defstruct` restart** | Reopens the dynamic-library vocabulary lane (`long`, packed structures, more libraries) | Re-read R-1/R-2/R-3 and attribute the fail-closed transition before any fix | Highest uncertainty. IRQ candidates were exhausted; the guard blackbox did not fit; resident geometry is closed | One attributed mechanism and a separately priced non-resident fix, or re-park |

## Recommendation

**Lead with editor latency.** It is the only candidate with an owner-declared
usability failure and a measured mechanism. The first implementation target
should be the Bank-2 renderer allocation shape, not the collector: eliminate
the temporary typed-line materialization and pin the result with the existing
80-key accounting lane. `room` remains the first GC instrument, but its old
three-service carrier is not silently resurrected; a smaller form must earn
its own map without touching rollback, publication or journal phases.

Pre-registered stop rules for that block:

1. no resident delta and no Session correctness-phase refusion;
2. host allocation gate before product link;
3. if the renderer cannot push the worst key below one nursery interval
   without a new semantic compromise, return a priced Class-C choice instead
   of tuning blindly;
4. one bundled target session only after the host shape is green.

Choosing another candidate is valid, but it knowingly leaves the measured
editor usability defect in place.
