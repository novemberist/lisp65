# Post-v1.2.5 editor input-latency host attribution

Status: **complete, 2026-07-31** — host-only, zero product bytes, zero
links, zero hardware contacts.

## Answer

The owner's “not usable” report has a measured structural mechanism:
**redisplay allocation churn repeatedly crosses the nursery threshold and
therefore schedules 89-frame collections while input is not being polled.**
The editor is not uniformly slow.  Ordinary keys are interrupted by long,
phase-dependent pauses; that is exactly the shape that overflows the
KERNAL's ten-byte input buffer and drops characters.

The lane executed the generated C2-lite IDE product composition through the
P0 host VM.  It warmed a modified buffer, typed one complete 79-column fill
cycle plus the first wrapped character, and counted each key separately.
All 192 possible incoming values of `allocs_since_gc` were evaluated against
the product's pre-allocation nursery check.

| Quantity | Render every key | 10-key coalescing |
|---|---:|---:|
| keys / renders | 80 / 80 | 80 / 8 |
| mean VM steps per key | 2,726.14 | 1,204.44 |
| mean heap cells per key | 169.26 | 47.62 |
| steady-state collections per key | 0.882 | 0.248 |
| collections over 80 keys, all phase offsets | 70–71 | 19–20 |
| keys carrying a collection, all phase offsets | 61–62 | 16–18 |
| projected GC frames per key | 78.46 | 22.08 |

The first wrap is the sharpest point.  In the serial route it allocates 722
cells and can carry four collections on one key.  Coalescing is valuable—it
cuts the mean collection rate by 72%—but it clusters the remaining work at
batch boundaries and cannot make a 1.8-second collection safe for a
ten-character hardware queue.

## Attribution

- **Edit step:** normally 912 VM instructions and 24 cells; the native
  normalized event contributes three more cells.
- **Redisplay:** grows with the typed column because the current line is
  materialized through temporary lists.  It dominates allocation churn.
- **GC:** the accepted whole-collection cost is 89 frames.  The target phase
  that owns those frames remains unknown, so no collector fix is attributed.
- **VM floor:** the historical 1,100-cycle instruction estimate gives about
  75 ms/key on the serial route and 33 ms/key with coalescing, excluding
  native screen I/O and GC.  It is real but secondary to the collection
  envelope.

## Priced lever order

1. Remove per-render typed-line materialization in the Bank-2 IDE library.
   This attacks the measured allocator directly and does not touch the
   closed resident geometry.
2. Retain and strengthen render coalescing.  It is already effective, but is
   a mitigation rather than closure.
3. Reopen the parked `gc`/`room`/`error` instrument lane with `room` first.
   The target GC phase must be measured before collector work is proposed.
4. Treat VM dispatch/call-depth reduction as the residual floor, after the
   allocation/GC path.

## Authority and limits

Machine receipt:
`tests/bytecode/dialect-v2/evidence/post-release/v125-editor-input-latency-host-accounting-receipt.json`.

The host instruction and allocation counts are exact for the bound generated
IDE suite.  Collection placement is derived from the shipped 192-allocation
nursery rule.  The host does not execute target DMA, screen timing, or GC
phase timing; the 89-frame value is the separately accepted hardware
authority.  Device rows remain scheduled for the next bundled session.
