# Golden-layout inversion — one-time artifact review

Status: **golden artifact and single comparison gate green; awaiting the
owner's one-time golden review**

Date: 2026-08-09

## Outcome first

The restart inversion is built without a product compile, WPLTO or device
contact. The two terminal v1.8 ELFs that proved the zero-deficit geometry
independently emit one byte-identical layout artifact:

| Item | Bound value |
| --- | --- |
| Golden artifact | `tests/bytecode/dialect-v2/golden-layout/c2-full-map-owned-layout-v1.json` |
| Bytes | 26,436 |
| SHA-256 | `65a13501c36db615f356bb7f992dcbb1c6a6f932fcf1968bf34646f9cbc7b4f7` |
| Allocatable section identities | 103 |
| Boundary symbols | 28 |
| Terminal seed ELF | `969c311350c4761f71c002aa59f9712d0bbf52a441f73e179b2ae4df9ec23e82` |
| Terminal final ELF | `64e269eaf820cdd1ee5f1eb35da32c404793bb4b2104be8290fa7483450c7fc4` |

The seed and final ELF hashes differ, but their extracted layouts are exactly
the same bytes. The golden therefore records the proven geometry, not one ELF
container identity.

## The inversion

The card acceptance has one operation:

```text
canonical(candidate linked-ELF layout bytes)
    ==
SHA-bound reviewed golden layout bytes
```

There is no acceptance-checker pipeline, external checker vocabulary or
receipt-order dependency. The extractor enumerates every allocatable section
from structured ELF truth, records its identity, VMA, LMA where file-backed,
size, alignment, type and flags, and sorts by section identity before
serialization. The same artifact records the 28 linker boundary symbols that
close data/BSS, heap, overlay, resident-island, mapped-far and zero-page
geometry.

The expected bytes never come from the candidate. Their SHA-256 is a literal
gate constant and the candidate is only the left-hand side of the one exact
comparison.

## Sensitivity and independence

Twelve mutations are rejected:

- deleted and added sections;
- changed VMA, LMA, size, alignment, section type or flags;
- deleted, added or moved boundary symbols; and
- changed artifact format.

Reversing the ELF section input order and then applying the artifact's
identity sort reproduces the exact golden bytes. This closes the historical
acceptance-order class rather than moving it into the new gate.

Permanent entry point:

```text
make c2-golden-layout-inversion-check
```

It is wired into `check-source`. The historical 1.8/1.9 gates remain as
immutable case law, but the future card does not consume them as its
acceptance pipeline.

## Scope and next edge

This review package performed:

- two terminal ELF layout extractions;
- two exact golden comparisons;
- twelve rejected mutations; and
- zero product compiles, WPLTO probes, device contacts, Link 91 actions or
  parity/release changes.

Machine-readable receipt:
`tests/bytecode/dialect-v2/evidence/architecture-blocks/c2.3-golden-layout-inversion-review-receipt.json`.

## Review decision requested

Recommendation: **accept this golden artifact once and authorize exactly one
product-shaped card under the single comparison gate.**

Green card → 1.5 Halt 2 reopens, then the preserved parity pilot and Link 91.
Red card → final ownership park with the inversion exhausted. No retry or
second golden is implied.


## One-time golden review — 2026-08-09 (reviewer, under the approved direction plan)

**Accepted.** Verified in review: the expected bytes never derive from
the candidate (the SHA-256 is a literal gate constant); both terminal
v1.8 ELFs — differing as containers — emit byte-identical layout
artifacts, so the golden records the proven zero-deficit geometry
itself; the artifact carries every allocatable section identity with
VMA/LMA/size/alignment/type/flags plus the 28 boundary symbols that
close every owned geometry family; twelve mutations cover deletion,
addition, every field class, boundary-symbol moves and format drift;
and input-order reversal reproduces the exact golden bytes — the
meta-level race of the three final parks is structurally impossible
in a single exact comparison.

**Authorized: exactly one product card** under the golden gate, per
the approved direction plan. Green reopens 1.5 Halt 2 and the parity
pilot, making Link 91 the bundled session's first row; red parks the
programme with the inversion also exhausted and returns to the owner
as a final disposition. No device, no retry, claims in rows.

## Product-card outcome — 2026-08-09

**First Red; final park.**  The single card command was invoked once and
stopped before WPLTO at an inherited F1 static-plane identity check.  All
geometric counts and the 47,282 Bank-2 bytes matched; only the historical
`product_build_id` pin differed (`0x293611ce` expected, `0x2e90e85f`
observed).  No linked ELF existed and the golden comparison was never reached.

The runner had incorrectly retained that non-geometric precondition before the
approved one-operation acceptance edge.  Nevertheless the authorization's
red row is binding: no retry, second golden, Link 91 or device action.  Full
disposition: `docs/planning/golden-layout-inversion-final-park.md`.
