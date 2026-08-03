# Public Sync Log

The public repository is a curated source snapshot with independent Git
history. Each sync records its user-visible scope and contribution attribution
here.

## v1.3.0 — prepared 2026-08-03

- Added the reproducible Ship Builder and four standalone sample projects,
  including physical-keyboard `read-line` input on a bootable application D81.
- Added public `read-line`, `key-event`, and `wait` surfaces and renamed the
  pre-advertisement Q8.7 `fx` family to the domain-specific `q` family.
- Shipped the lower-allocation editor renderer and its permanent per-key gate.
- Staged the complete Bank-5 reset domain, including a cleared C2J journal,
  and made standalone runtimes establish and prove their own frame clock.
- Updated the visible banner to `WORKBENCH 1.3.0` and rebound the permanent
  public clean-build gate to the Link-88 19-role product identity.
- External contributions included in this sync: **none**.

The corresponding public commit, tag, and GitHub release are prepared locally.
No public ref or release is changed until the owner gives Halt-#2 publication
authorization.

## v1.2.5 — prepared 2026-07-31

- Corrected `require` so ordinary persistent definitions created earlier in
  the same session no longer make package resolution return `nil`.
- Added a permanent source gate and release-terminal hardware row for
  `require` after two ordinary persistent appends.
- Rebound the permanent public clean-build gate to the Link-82 19-role
  product identity.
- Kept the accepted product banner at `WORKBENCH 1.2.4`; v1.2.5 is a package
  correction over those product bytes.
- External contributions included in this sync: **none**.

The corresponding public commit, tag, and GitHub release are prepared locally.
No public ref or release is changed until the owner gives Halt-#2 publication
authorization.

## v1.2.4 — published 2026-07-30

- Added signed Q8.7 fixed-point arithmetic (`fx` and its conversion and
  arithmetic helpers) to the base composition.
- Added `(time form)` with value preservation and measured raster-frame
  reporting.
- Rebound the permanent public clean-build gate to the Link-81 19-role
  product identity.
- External contributions included in this sync: **none**.

Public commit `65426c454df405dddb6c4d4a7457039b40938bae`, annotated tag
`v1.2.4`, and the corresponding GitHub release were published and
readback-verified.

## v1.2.3 — prepared 2026-07-30

- Bound the native `while` form and base-composition `random`/`random-seed`
  implementation into the reproducible public product snapshot.
- Bound the generation-aware fast path for repeated `require` calls.
- Carried the Ethernet, Auto-IEC, and audio-DMA interrupt-ownership hardening
  into the public product.
- Updated the REPL banner to display `WORKBENCH 1.2.3`.
- Rebound the permanent public clean-build gate to the fresh v1.2.3 19-role
  product identity.
- External contributions included in this sync: **none**.

The corresponding public commit, tag, and GitHub release are prepared locally.
No public ref or release is changed until the owner gives Halt-B publication
authorization.

## v1.2.2 — prepared 2026-07-29

- Fixed undefined-function diagnostics so they report the complete symbol
  name instead of a truncated or padded fragment.
- Removed the corresponding Known Issue and carried all other product
  boundaries forward unchanged.
- Rebound the permanent public clean-build gate to the fresh v1.2.2 19-role
  product identity.
- External contributions included in this sync: **none**.

The corresponding public commit, tag, and GitHub release are prepared locally.
No public ref or release is changed until the owner gives Halt-B publication
authorization.

## v1.2.1 — prepared 2026-07-29

- Added the native Dialect V2 `while` form and documented its streamed-backedge
  refill cost.
- Added the base-composition `random` and `random-seed` functions.
- Extended the published direct-call path to fixed-argument functions.
- Added the generation-bound fast path for repeated `require` resolution.
- Hardened internal interrupt ownership for Ethernet, Auto-IEC, and audio DMA.
- Updated user documentation and the maintained Known Issues for the
  v1.2.1 hardware boundary.
- Rebound the permanent public clean-build gate to the fresh v1.2.1 19-role
  product identity.
- External contributions included in this sync: **none**.

The corresponding public commit, tag, and GitHub release are prepared locally.
No public ref or release is changed until the owner gives Halt-B publication
authorization.

## v1.2.0 — prepared 2026-07-27

- Added C2-lite runtime, staging, transaction, and verification sources.
- Added the L-full generated input path and current generated keymap.
- Added lisp65 1.2.0 release notes and the maintained known-issues register.
- Added contributor/DCO guidance and GitHub issue templates.
- Updated user, architecture, development, and implementation documentation to
  the promoted 1.2 boundary.
- Replaced the retired 1.1 public product entry with the C2-lite single-emitter
  `workbench-product` path.
- Added a permanent two-fresh-clone gate that reproduces all 19 sealed product
  and media roles; the R6 bundle remains the hardware-acceptance authority.
- External contributions included in this sync: **none**.

The corresponding public commit is prepared locally and is not published until
the owner gives the Phase-R publish authorization.
