# Comfort track — Interlisp tools and string pair

Status: **host-green development material 2026-08-06**. Commissioned as
the gap-filler beside the 1.9 recharter; all freight is built and permanently
gated, but packaging and public delivery remain deferred.

## Freight (host-first, Bank 2, zero resident, all Class A/B)

1. `who-calls` from the host-generated shelf metadata.
2. `trace`/`untrace` by function-cell wrapping.
3. `capitalize` and `string-split` on the delivered base string
   library (the four-liners of the 1.3 successor menu).

## Bounds

- Host-green through the existing source/artifact equivalence and
  surface-parity gate patterns; sized against the Bank-2 budget.
- **No release, no device session, no public-surface claim inside
  this track** — delivery packaging waits for the next release block,
  where the standard ritual (owner halts, device rows) applies. Until
  then everything is development material behind gates.
- The one-truth rule and tombstone discipline apply to any new name.

## Execution record

All five names are implemented in ten Bank-2 code objects and execute through
13 source cases. The disk-library artifact costs 5,807 bytes including its
container/literal metadata (713 code bytes, 70 directory bytes), leaving
12,431 bytes against the bound 18,238-byte Link-90 Bank-2 headroom. Resident
delta and device contacts are both zero.

- `who-calls` is generated exactly from the compiler-proven
  `directory_only.entry_refs` of the v1.3 IDEX and M65D shelves: 109 exact
  edges over 50 targets. Generic kind-8 symbol literals remain forbidden as
  call evidence.
- `trace` and `untrace` are macro entries. Their treewalk-evaluated expansion
  captures the real function-cell value before installation, roots it in
  `*comfort-trace-bindings*`, invokes the captured callable rather than the
  wrapped name, and restores that exact value on `untrace`. No new native
  primitive or resident byte is required.
- `capitalize` and `string-split` use only delivered dialect-v2 string
  operations. The converter tombstones are absent. Splitting preserves empty
  fields; an empty separator returns a singleton containing the original
  string.

The permanent `comfort-track-check` rejects 17 scope, metadata, trace,
tombstone and budget mutations. Its receipt is
`tests/bytecode/dialect-v2/evidence/architecture-blocks/comfort-track-host-first-receipt.json`.
None of the five names was added to the public surface; a later release block
must still perform its normal packaging, device and owner-halt ritual.


## Reviewer acceptance — 2026-08-06

Accepted host-green: `who-calls` (109 exact call edges),
`trace`/`untrace`, `capitalize`, `string-split`; 10 objects, 13
cases, 17 mutations; Bank 2 +5,807 B against 12,431 B remaining
headroom, resident +0. Publication stays deliberately deferred to the
next release block, where the standard ritual (owner halts, surface
parity binding, device rows) applies. Until then: development
material behind gates, no surface claim.