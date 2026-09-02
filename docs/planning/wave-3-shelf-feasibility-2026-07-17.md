# Wave 3 shelf feasibility at the L65S-v3 boundary

Status: owner decision resolved; bounded v4 probe failed; Route A/L-lite active.

Date: 2026-07-17

## Question

Can Wave 3 deliver L-lite, `ide-lisp`, editing safety and `ide-help` on the
canonical five-container shelf, or must the shelf-catalog evolution planned
for C2 be pulled forward?

## Bound facts

The restored canonical L65S-v3 shelf is **65,368 bytes**. Its current device
decoder requires the total shelf length, every record offset and every
container length to fit in 16 bits. The inclusive encoding ceiling is 65,535,
so only **167 bytes** remain.

Each additional catalog record is 32 bytes. Therefore:

| New records | Record bytes | Maximum combined new payload | Result |
| ---: | ---: | ---: | --- |
| 0 | 0 | 167 | Existing containers may grow by at most 167 B in total. |
| 1 | 32 | 135 | At most one exceptionally small module can fit. |
| 2 | 64 | 103 | Two nonempty feature modules are not credible. |
| 3 | 96 | 71 | H/I/J cannot be represented as separate modules. |
| 4 | 128 | 39 | H/I/J plus a metadata record is structurally impossible. |

The rejected `room` candidate is a useful measured lower bound rather than a
projection: its smallest complete L65M container was 128 bytes, so one record
plus that payload consumed 160 of the 167 available bytes and left 7. No
Wave-3 feature module has been measured at or below 135 bytes, and none may be
authorized by assuming that it will.

These are catalog/storage bounds only. Bank 0, EXT, runtime-overlay bank,
resident island and installer slices remain separate gates.

## What remains possible without catalog evolution

### L-lite

L-lite is feasible in principle because its approved cut rebinds and proves
the existing GETIN path. Its generated keymap documentation, virtual input
fixtures and physical samples do not require a new shelf module. It still
needs an implementation receipt with **shelf delta ±0**; this note does not
pre-authorize any resident or overlay bytes.

### H, I and J

The current plan defines new components as loadable shelf modules. Under the
167-byte absolute remainder:

- `ide-lisp` cannot be planned as a new module without a measured container of
  at most 135 bytes;
- editing safety cannot assume that folding code into IDE/IDEX avoids the
  limit, because growth of existing containers consumes the same 167-byte
  total;
- `ide-help` additionally needs its separate SHA-bound metadata file and is
  therefore the least compatible with the current shelf;
- delivering H, I and J as separate records is impossible even before one
  byte of feature payload is emitted.

Host-only work can continue: contracts, generated keymap/test inputs, scanner
fixtures, undo traces and the metadata schema. Product delivery cannot.

## Route A — shelf-free Wave 3

Ship only L-lite and any genuinely shelf-neutral corrections in 1.1. Move H,
I and J behind C2. The 1.1 claim must then be narrowed explicitly; the current
Wave-3 feature list cannot remain a release promise.

Benefits:

- no new shelf format or loader in the 1.1 train;
- no duplicate acceptance cycle for an intermediate staging-only format;
- preserves the C2 rule that address evolution is designed once.

Costs:

- most IDE polish moves to 1.2;
- the 1.1 release becomes primarily the Wave-1/Wave-2 architecture release;
- H/I/J contracts may advance, but no product-facing implementation can be
  claimed.

## Route B — pull a catalog sub-block forward

A cleanly isolatable cut exists in principle, but it is larger than changing
one integer field. Call it **L65S-v4 staging catalog**, not direct Attic
execution:

1. give shelf totals and record source offsets an extended (at least 24-bit)
   representation while retaining the current u16 per-container length and
   38,400-byte staging limit;
2. replace the hard-coded five-name resolver and fixed record count with a
   bounded catalog lookup;
3. update both device decoders (`attic_library_shelf.c` and the C1 fast-path
   decoder in `io.c`), the host builder/verifier, headers, negative fixtures,
   ship/preflight bindings and reset/restage cases;
4. continue copying the selected L65M container into the existing scratch and
   use the unchanged validator/commit path — no direct Attic code execution is
   claimed;
5. define the extended source address as the staging subset of the C2.0
   address/identity contract, so C2 can reuse it rather than introducing a
   second incompatible address type.

This separation is semantically honest: it changes **where a source container
is found**, not **where bytecode executes**. It is not yet capacity-authorized.
The decoder changes live in the shelf runtime slices, while the fixed product
overlay currently has no spare bytes; a real link must therefore prove every
budget before Route B can be chosen.

Route B also has a proof cost even if its byte cost is small: a new product
identity, strict old/new decoder behavior, complete catalog mutation tests,
reset/restage coverage, and a fresh product acceptance chain. C2 later needs a
second acceptance step when execution changes from staging to direct Attic
addresses.

## Route C — widen and split load-time metadata

The test-bench audit identified 36,260 B of load-time metadata. Its exact,
receipt-confirmed composition is:

- 17,370 B literal nodes;
- 6,900 B literal patches;
- 3,474 B literal index (27,744 B literal machinery in total);
- 5,347 B raw string pool, 5,350 B including regional alignment;
- 2,976 B entry tables and 190 B metadata headers.

The 55.6% figure uses the 65,176-B shelf payload region as denominator; the
same metadata are 55.5% of the complete 65,368-B shelf. A plain D81 side file
is not admissible: after the documented single disk swap it would no longer be
available, regressing the reset-fast/load-after-swap contract. Two
identity-safe shapes were therefore assessed inside L65S-v4:

1. **Widening only:** u24 shelf source offsets, unchanged contiguous L65M
   containers. This reuses the address type in C2.0 but not its metadata
   boundary.
2. **Widening plus regions:** the same u24 catalog, with prefix+immutable code
   and load-time metadata stored as separate regions in the same
   reset-persistent shelf artifact. Staging reconstructs the exact original
   L65M byte stream before the unchanged validator/commit path. This pays the
   first part of C2.0's code/metadata separation without adding a second boot
   artifact.

Both modeled layouts are 65,367 B and reconstruct all five current containers
byteidentically. Reserving four 32-B records for `ide-lisp`, editing safety,
`ide-help` and the metadata index leaves **458,793 B combined future region
space** inside the deliberately bounded 512-KiB probe envelope. This is an
aggregate format/storage projection, not a claim about unbuilt module sizes or
a release capacity authorization.

## Decision gate

Before choosing Route B, one bounded format probe must report:

- exact L65S-v4 header/record layout and strict version rules;
- maximum shelf and record count;
- exact deltas for Bank 0, EXT, fixed overlay, runtime-overlay bank, resident
  island and installer slice;
- unchanged L65M container bytes and commit semantics;
- old sealed L65S-v3 evidence remaining historical rather than rewritten;
- a C2.0 contract reference proving that the new source address is reusable.

If that one probe cannot fit all hard budgets, Route A follows without a
catalog-reclaim series.

## Decision and measured outcome (2026-07-18)

Owner authorized one real-link attempt, selected the regions variant, and
pre-authorized automatic fallback to Route A on any red hard gate. The host
format, strict version/mutation checks and byteidentical reconstruction passed.
The one product link did not:

- `.lisp65_rt_l65s` measured 3,326 B against the 1,792-B maximum runtime-slice
  window (1,534 B over);
- the same section ended at `$d054`, overflowing the fixed runtime-overlay link
  region by 84 B;
- the name slice was green at 1,326/1,792 B, but later capacity gates were not
  reached because the seed link stopped fail-closed.

The one-attempt rule therefore fired. No pure-widening retry, decoder diet,
boundary shaving or reclaim series is permitted in the 1.1 train. All product
changes were rolled back byteidentically, L65S-v3 is restored at 65,368 B with
167 B u16 headroom, and the v4 work remains C2.0 design evidence only. Bound
receipts:

- `tests/bytecode/dialect-v2/evidence/architecture-blocks/v11-shelf-metadata-audit-receipt.json`;
- `tests/bytecode/dialect-v2/evidence/architecture-blocks/v11-l65s-v4-layout-model-receipt.json`;
- `tests/bytecode/dialect-v2/evidence/architecture-blocks/v11-l65s-v4-one-attempt-outcome-receipt.json`.

## Resulting Wave-3 scope

Proceed with L-lite and host-only contract work in 1.1. H/I/J and the shelf
metadata module move behind C2. The scope reduction is explicit rather than
silent; L65S-v4 is neither a product format nor capacity-authorized. The
separate 17-name cleanup remains authorized for the Wave-2 repin and does not
depend on v4.
