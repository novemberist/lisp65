# Post-v1.2.4 `require` after persistent appends — owner review

Status: **owner decision 2026-07-31: fix per Option A, then a small
correction release.** Commission at the end of this document. Attribution
state: completed 2026-07-30 on the host, zero product bytes, zero links,
zero hardware runs.

## Outcome first

H1 is confirmed. The exact v1.2.4 resolver, the bound compiler carrier and
the canonical persistent-append model produce this matrix:

| Mounted medium | Prior persistent appends | Result | Loader calls |
|---|---:|---:|---:|
| released product D81 | 0 | `nil` | 0 |
| released product D81 | `%s`, `%sr` | `nil` | 0 |
| product-ID-bound library D81 | 0 | `t` | 1 (`place`) |
| product-ID-bound library D81 | `%s`, `%sr` | `nil` | 0 |

The two ordinary definitions are the discriminator. With valid library
media, `require` succeeds from the six-image boot state and deterministically
fails after the two exact soak helpers. The failure is fully host-reproduced;
no target discriminator or four-seam ELF campaign is needed.

Machine authority:
`tests/bytecode/dialect-v2/evidence/post-release/post-v124-require-prior-append-h1-receipt-20260730.json`.

## Attributed mechanism

The failure is in the resolver's world proof, before media staging:

1. `%require-world` calls `%require-active-prefix` over every persistent C2D
   image row.
2. `%require-active-prefix` requires each row's combined identity to occur in
   `L65INDEX`.
3. Ordinary persistent definitions use the same source-kind-1 C2D row class
   as dynamically loaded libraries, but their identities are naturally not
   present in the package index.
4. At slot 6, `%require-index-row-for-image` therefore returns `nil`;
   `%require-world` returns `nil`; the resolver never calls
   `%disk-load-lib`.

The failing host lane executed 139 real Prim-67 C2D reads and entered
`%require-active-prefix` once and `%require-index-row-for-image` three times,
but entered neither `%require-load-plan` nor `%disk-load-lib`. The successful
zero-append lane executed 439 Prim-67 reads, called the loader once and
published `place`.

This is a **contract defect**, not a DMA or append-completion defect. The
active-universe rule assumes that every persistent Session row is a library
row. C2D-v6 carries no discriminator between an ordinary user definition and
a package append, so strict rejection of every identity absent from L65INDEX
makes `require` order-dependent.

## Correction to the apparent second sighting

The post-release soak did not mount library media. It mounted only
`15-lisp65-product.d81`, whose directory contains neither `L65INDEX`,
`PLACE`, nor `DEFSTRUCT`; its paired work D81 is empty. Consequently that
run's `nil` is an expected missing-package result and **does not count as a
second product sighting**. Its captured bytes remain valid raw evidence:
the two helper rows were published and no `place` row appeared. Only the
old product interpretation is superseded.

The host matrix nevertheless reproduces the real defect with a v1.2.4
product-ID-bound library D81. It also explains the original Link-80
observation, which used valid library media after many persistent
definitions. The earlier cold retries succeeded because they ran before
ordinary persistent appends.

Two harness defects are therefore recorded separately:

- every hardware `require` fixture must prove that the mounted medium
  contains `L65INDEX` and each requested L65S artifact before it may make a
  product claim;
- target-shaped host fixtures must preserve the product's 4096 transient
  watermark and sequential Session source slots after modeled appends. The
  generic host lacks those two owners, so the H1 fixture restores them
  explicitly before running the resolver.

## Owner decision now required

The mechanism is attributed; the remaining question is product policy:

| Option | Meaning | Trade-off |
|---|---|---|
| **A — accept non-index persistent rows during the world walk** | Prove the geometry of every persistent row, but treat only identities present in L65INDEX as loaded libraries. Ordinary user definitions no longer block later `require`. | Smallest likely Bank-2-only repair. The existing “foreign identity always fails” mutation and contract must be narrowed because the format cannot distinguish foreign packages from user definitions. |
| **B — add an explicit package/user row discriminator** | Widen or version the persistent-row contract so strict package-universe validation remains possible. | Strongest distinction, but it is a format/geometry decision rather than a small resolver fix. |
| **C — withdraw or constrain `require`** | Document “load packages before the first persistent definition”, or withdraw dynamic loading until a later format. | No immediate product change, but preserves a surprising order-dependent user surface. |

## Owner commission — 2026-07-31 (Option A chosen)

1. **The fix:** correct `%require-world` / `%require-active-prefix` to the
   true invariant — every persistent C2D row is validated geometrically,
   but only rows whose identity occurs in L65INDEX are treated as library
   rows; ordinary Session definitions are legitimate non-index rows and
   must not fail the world proof. No format change. The existing
   "foreign identity always fails" mutation and contract are narrowed
   accordingly, with the narrowing named in the receipt.
2. **The class closer (binding condition):** a permanent host lane AND an
   acceptance-session row for "require after persistent appends" — the
   exact state-space gap that every green instrument avoided. Execution
   witness like every permanent check.
3. **v1.2.5 as a small honest correction release** (the 1.2.2 DIRMISS
   pattern): the fix, the corrected known-issues entry (deterministic,
   not intermittent; the cold-start workaround text is withdrawn), and
   release notes that say plainly what was wrong and for whom. Standard
   chain under the A1 rule; the usual two owner halts.
4. **After the release, in order:** the editor input-latency host
   accounting (handed over at this stop per the owner's direction —
   `editor-input-latency-owner-report-2026-07-30.md`), then the corrected
   soak (the harness must mount and bind the package medium), then the B3
   direction menu with everything on the table.

## Historical hardware observation

The cold soak setup appended `%s` and `%sr`, returned `nil` from
`(require 'place)`, and captured C2D image count 8, helper rows 6–7, empty
slot 8, C2J CLEAR, phase owner NONE, and no OOM/badobj. The corrected dynamic
slot calculation and capture labels remain sound. The missing library medium
means those bytes prove only that no package load occurred, not why a valid
package load would fail.

The 30-minute/1,800-cycle soak never started. The short-scale v1.2.4
Chip-RAM curve remains valid; this run adds no Chip-RAM or L10 evidence.
