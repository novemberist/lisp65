# Editor input latency — owner report

Status: **host-attributed 2026-07-31, report reproduced structurally** —
registered as a priority candidate for the next direction decision (B3).
The host-first measurement is complete; target timing rows remain for the
next bundled device session.

## The report, verbatim intent

Typing in the editor is extremely laggy, and at moderate typing speed
keystrokes are dropped constantly. In the owner's words: **not usable.**
This is a product-quality statement from the product owner about the
flagship workbench surface; it outranks comfort-level tuning.

## Known history (why this is a return, not a novelty)

The one-second-per-keystroke era of 2026-07-03 was measured and fixed:
2,405 code DMAs per keystroke (mostly unnecessary reloads → the owner
tag), 2–6 GCs per keystroke with O(length) mark passes (→ the spine
marker and the EXT marking window), and an 80 ms-per-GC EXT scan (→ the
min/max window). What remains structural today:

- the editor key path stacks **~24 `vm_run` levels** per keystroke at
  ~1,100 cycles per VM op;
- an isolated collection costs **88–89 frames (~1.8 s)** on hardware and
  its dominant term is **still unattributed** (the parked G3 item);
- keyboard input is polled between redisplay work — there is no
  IRQ-side input capture, so any pause longer than the KERNAL's 10-byte
  buffer at the current typing rate **drops keystrokes**.

The dropped-input symptom is exactly what periodic 1.8-second GC pauses
would produce. That makes this report the strongest candidate yet for
the standing freight-order rule: *if GC work becomes urgent, `room`
moves to the front of any resumed `gc`/`room`/`error` trio.*

## Commission — handed over at the next stop (owner direction 2026-07-30)

The running `require` attribution stays the single active commission; this
measurement is **handed to Codex at its next stop/review point**, not
injected in parallel — one lane, no interleaving confusion. Content of the
handover, unchanged:

1. **Host step/GC accounting per keystroke** on the session runner:
   replay a representative typing burst through the editor path; bind
   steps, allocations and collections per keystroke, and the
   distribution (is it uniformly slow, or fast-with-pauses?).
2. **Attribution split**: how much of a keystroke is VM step cost
   (~24 levels), redisplay, and GC amortization. Paper output: the
   lever list, priced.
3. No device session yet — device rows join the next bundled session
   (`(time)` is now on the device as the measuring instrument, and the
   editor rows ride with whatever session the require work needs
   anyway).

## Host result — 2026-07-31

The product IDE composition was run through the generated Workbench suite,
not the historical resident-only stdlib profile.  The workload is one warm
80-character fill cycle, including the first wrap, on two routes:

| Route | VM steps/key | heap cells/key | derived collections/key | projected GC frames/key |
|---|---:|---:|---:|---:|
| render after every key | 2,726 mean | 169.26 mean | 0.882 | 78.46 |
| ten keys, then one render | 1,204 mean | 47.62 mean | 0.248 | 22.08 |

The distribution is **fast work plus large periodic pauses**, not uniform
slowness.  The edit itself is normally 912 VM steps and 27 cells including
the normalized key event.  Redisplay allocations grow with the cursor
column; the first wrap reaches 722 cells on one key in the serial route.
Under the product's 192-allocation nursery rule that one key can contain
four collections.  Exhaustive placement over all 192 incoming nursery
phases leaves the conclusion unchanged: serial typing causes 70–71
collections over 80 keys; ten-key coalescing causes 19–20.

Combining those exact host counts with the accepted 89-frame target
collection envelope projects about 1.57 seconds of GC per serial key, or
0.44 seconds per coalesced key, before native screen-I/O time.  These are
cost projections, not target timings; the collection phase responsible for
the 89 frames remains unknown.

Authority:
`tests/bytecode/dialect-v2/evidence/post-release/v125-editor-input-latency-host-accounting-receipt.json`.

The reopening condition is therefore met: periodic GC pauses are a credible
mechanism for the owner's dropped-input report.  The `gc`/`room`/`error`
instrument lane returns to the B3 table with **`room` first**.  No collector
change is authorized by this measurement alone.

## Decision linkage

- **B3 menu:** editor performance enters as candidate 5 with owner
  priority; "not usable" outranks the era-comfort candidates.
- **G1/G3 linkage:** if the host accounting confirms GC pauses as the
  dropped-input mechanism, the parked `gc`/`room`/`error` trio's
  reopening condition fires with `room` first — **condition met by the
  2026-07-31 accounting**.
- **Known-issues:** the next release's E2 step carries an honest entry
  (typing latency, dropped input at moderate speed) unless the fix
  lands first.
