# Public Sync Log

The public repository is a curated source snapshot with independent Git
history. Each sync records its user-visible scope and contribution attribution
here.

## v2.2.0 — published 2026-09-10

The owner supplied separate Ship and Publish words after reviewer acceptance
`ebd11c4e`. Public `main` and annotated tag `v2.2.0` were advanced atomically;
the release was uploaded as a draft, downloaded and checked, then published
and downloaded again. No product build or archive repack occurred.

- Public commit: `f0114b352e46a413e65476ebb8cf084ef8ad810a`.
- Annotated tag object: `80d1309a758bb06c4d6c2c4cfe5e3b86c8584ecf`.
- Public tree: `9030d8ddfadebcd616c6ae5102d066c5799d7cc3`, exactly the tree of
  sealed source projection `3609960e530f22e5af16d5852f8b4a2dfd985045`.
  The public commit preserves the existing independent public history; the
  source-projection commit and local Ship tag remain as preparation evidence.
- Release: <https://github.com/novemberist/lisp65/releases/tag/v2.2.0>.
  Published at `2026-09-10T17:53:35Z`; approved release-note body reread exactly.
- Product archive SHA256:
  `2d201a1aebb8a02d3afddcd0f47d78115f59df22501cd909bfc2c30119f39d71`.
- Source archive SHA256:
  `958bc552ca3ce1637a8627db22077179e7a73b11aff5fbd501b9cf5bfc433726`.
- Manifest SHA256:
  `d45f0163fcfafef942851166e5851b721391704550e4666bccefba63ce661ed6`.
- Clean-build receipt SHA256:
  `a42b85e5ca563039094e2ce18b4047ccd164ebdd35aa49fa6bbce97114d2cf19`.

All four published downloads matched the sealed assets byte-for-byte. The
readback receipt is `build/release-v2.2.0/publish-readback.json`, SHA256
`44dd5609ae10c8d027988244acaa275c373421789590d7c59a1a1afe23818210`.
Release scope and limitations are exactly those in `docs/releases/2.2.0.md`:
R2, native wrap and Backspace recovery, pound quasiquote, capacity work and
five manually loaded packages; no Comfort or general native-stack protection.
The tolerated nineteen historical host-gate failures remain explicitly
listed in the Before-Ship checklist, not relabeled as green.

## v1.9.0 — published 2026-08-30

- Routed the native `lisp65>` prompt through the resident insertion-mode line
  editor, retiring the Cursor Left/Right `invalid token` limitation.
- Delivered the native Capture/Hybrid lifecycle and real ring consumer; a
  physical sequence crossing a forced collection ended with
  `raw=seen=stored=taken=136`.
- Kept type-ahead during evaluation, Comfort, balanced multiline input/history,
  delimiter matching, and cursor blink outside the release claim.
- Reproduced the exact 19-role product in two varied fresh public-source clones
  with one WPLTO/link each and no private evidence inputs.
- External contributions included in this sync: **none**.

Published as public `main` commit
`e237fc3da2297119c8a8861d8fb0410044fabbcf`, annotated tag `v1.9.0`
(tag object `ca76036ba2b7e3210c519485932599a548161dae`) and GitHub release
379395123. All four assets matched a fresh downloaded readback.

## v1.8.0 — prepared 2026-08-28

- Shipped the qualified native Capture/Hybrid substrate in a deliberately
  closed state; activation and a lossless-input claim remain v1.9 work.
- Re-proved the 94/94 laboratory loss wall, normalization parity,
  responsiveness and queue-single-owner properties on the final ELF.
- Retained native `INIT.L65`, the A0 empty-journal recovery path, composed
  Bank-2 ownership, MAP geometry and delivered-byte closure from v1.7.
- Documented that Cursor Left/Right editing belongs to explicit `(read-line)`
  through `v16core`, not to the bare native `lisp65>` C collector; replay of
  the sealed v1.7 and v1.8 ELFs proves this is not a regression.
- Kept Comfort, matcher/blink and the native Capture client outside the
  selected product and its release claims.
- External contributions included in this sync: **none**.

The corresponding public commit, tag, and GitHub release are prepared locally.
No public ref or release is changed until the owner gives publication
authorization.

## v1.7.0 — prepared 2026-08-27

- Added the native, once-per-boot `INIT.L65` hook after resident readiness;
  absence is silent and startup errors return to one live native prompt.
- Reduced empty-journal recovery from eight overlay transports and 17,852 CRC
  bytes to two transports and 6,110 CRC bytes through a fully derived,
  fail-closed A0 fast path.
- Added composed Bank-2 ownership, MAP page-congruence at placement time, and
  emitted MAP-tuple equality with linker `LOADADDR` authority.
- Retained the v1.6 `v16core` cursor-navigation package and the delivered-byte,
  MAP-CPU refill, queue-owner, and retired-overlay recovery protections.
- Kept Comfort and delimiter-matcher/blink development freight outside the
  selected product after their bounded hardware rounds did not close.
- External contributions included in this sync: **none**.

The corresponding public commit, tag, and GitHub release are prepared locally.
No public ref or release is changed until the owner gives Halt-B publication
authorization.

## v1.5.0 — prepared 2026-08-18

- Added visible boot and `require` progress, with a clean handoff to the
  `WORKBENCH 1.5.0` banner and prompt.
- Added immediate non-persistent REPL evaluation while retaining the durable
  publication ceremony for definitions and other persistent forms.
- Delivered reversible `trace`/`untrace` with exact BCODE restoration and the
  positional, option-free `defstruct` package with its declared `place`
  dependency.
- Normalized interactive Shift-Space to ordinary space, so the natural Lisp
  typing sequence `) (` cannot inject an invisible PETSCII `$A0` token.
- Replaced content-consuming mutable DMA reads with the hardware-proved MAP
  CPU transport and retained delivery-bound verification for immutable boot
  spans.
- Added release-terminal performance and user-name-headroom contracts. The
  accepted device retained 34 symbol slots and 545 name bytes over the 32/384
  minimum, and booted in 36 seconds versus 31 seconds for v1.4.0.
- External contributions included in this sync: **none**.

The corresponding public commit, tag, and GitHub release are prepared locally.
No public ref or release is changed until the owner gives Halt-#2 publication
authorization.

## v1.4.0 — prepared 2026-08-08

- Promoted the locality-optimized compiler carrier with zero resident growth;
  the structural full-sequence price fell from 788 to 677 seconds and the
  post-require definition price to 179 seconds. These are prices, not
  completion ceilings.
- Added the optional `string-extra` library (`capitalize`, `string-split`) and
  the optional `inspect` library (`who-calls`).
- Kept `trace`, `untrace`, and `defstruct` outside the delivered surface after
  their hardware rows failed their independent delivery conditions.
- Reclassified the virtual editor 56/64 result after a quiet physical 64/64
  acceptance row; no editor product stall is claimed from the transport loss.
- Updated the visible banner to `WORKBENCH 1.4.0` and selected the exact Base
  library D81 at Halt #1 without rebuilding either media variant.
- External contributions included in this sync: **none**.

The corresponding public commit, tag, and GitHub release are prepared locally.
No public ref or release is changed until the owner gives Halt-#2 publication
authorization.

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
