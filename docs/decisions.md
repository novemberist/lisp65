# Standing Decisions

This file summarizes concise decisions that remain active after release 1.0.0.
The full append-only chronology, including new decisions and historical entries
whose original language and paths remain untouched, lives in
[`decision-log.md`](decision-log.md).

## 2026-07-15 — Release identity

lisp65 1.0.0 is the first product release and contains Dialect V2. The
annotated tag `v1.0.0` points to source commit `5897294…`; product bytes come
only from G6 seal `b339a274…`. Dialect V1 was never released.

## 2026-07-15 — Product boundary

The Workbench is the only interactive and redistributable product identity.
Runtime Core and Runtime Export remain internal proof carriers and must not be
added to the product artifact set to simplify a test harness.

## 2026-07-15 — Evidence identity

Evidence binds to a set of product-artifact SHAs. Harness, verifier, or package
changes do not invalidate a passed case when product SHAs are unchanged and the
receipt is reverified against the new manifest. Any product-SHA change requires
fresh applicable hardware cases. Sealed archives are append-only.

## 2026-07-15 — Capacity accounting

Every promoted block reports deltas for Bank 0, EXT, symbols, name-pool bytes,
and directory slots. A non-zero delta requires authorization before promotion.
EXT is frozen at the 1.0 baseline until a structural relief block creates a new
measured margin.

## 2026-07-15 — Media policy

M65D uses a denylist: every valid 1581 medium is writable unless it is identified
as the product/system disk. Transactions bind to name, disk ID, and mount
generation. A medium change after transaction start is terminal and is never
retried automatically.

## 2026-07-15 — Stock-core compatibility

lisp65 remains compatible with the official MEGA65 core used by the release.
Core-level hardening ideas are proposed upstream; the product does not require a
private FPGA-core fork.

## 2026-07-15 — Documentation language and audiences

Active user and contributor documentation and new source comments are written
in English. Historical archives may retain their original language. Frozen
evidence claims are never translated in place. User guidance, internal
contracts, proposals, and historical records must remain visibly separated.
Release-1.0 C and Lisp source comments remain byte-for-byte unchanged where the
sealed ELF or family evidence binds the complete source file; translating those
files would create a new product/evidence identity. New 1.1 source starts in
English.
The post-1.0 relocation preserves historical path strings inside frozen
machine contracts and receipts. Evidence-bound compatibility paths remain in
place; other live tools resolve archived files explicitly. Sealed promotion
archives, release claims, and product bytes remain unchanged.

## 2026-07-15 — Public repository topology

The complete working mirror remains private and is the authority for sealed
evidence, release history, and internal planning. Public distribution uses a
separate repository produced from an explicit allowlist. The public repository
contains product source for inspection and development, active English
documentation, useful public tests and examples, upstream findings, release
manifests, and checksums. The exact C2-lite 1.2 product is supplied by its
self-verifying release bundle; a supported public clean-build entry point is
not yet part of the snapshot. It
does not contain sealed evidence archives, internal plans, private operational
records, bundled toolchains, third-party reference material, or release
tarballs in Git/LFS. End-user bundles are published as release assets. The
executable allowlist is `config/public-export-policy.json`; a public export
fails on local absolute paths, non-fixture email addresses, high-confidence
secret patterns, Git LFS pointers, large files, or bundled ELF tools.

## 2026-07-15 — Source and runtime license

Original lisp65 material is licensed under MPL 2.0. File-level copyleft keeps
changes to lisp65 files available while allowing independently authored user
programs and FASLs to use terms chosen by their authors. A standing runtime
redistribution notice explains the MPL Larger Work boundary and the source and
notice duties for distributors. It is an explanation of the standard license,
not a custom license exception. Third-party toolchains, manuals, and reference
material remain under their own terms and outside the curated export.

## 2026-07-15 — Remote verification

The private GitHub remote is an off-site mirror. Every release or completed
promotion push is followed by `git ls-remote` equality checks for the branch
and the complete local/remote tag refset, plus a Git LFS dry-run showing no
pending objects.

## 2026-07-17 — Hardware procedures use public product surfaces

Operator-assisted hardware procedures may not call private library helpers by
name. Directory-only entries are deliberately anonymous and are not a stable
test API. The G6 mid-write Freezer case enters through public `m65d-save`; its
red-border cue occurs immediately before that public call. Terminal return 12,
persistent `m65d-status` 12, and the independent two-media oracle together
prove that the medium changed after token capture. Any other result is a
receipt-less retry, never evidence.

## 2026-07-18 — Proof archives use release assets, not Git or Git LFS

The owner-approved one-time transport rewrite moved all 39 tracked proof and
release archives (8,210,842,025 bytes) to private GitHub release assets bound
by `config/evidence-archive-assets.json`. The rewrite also removed the 77-MB
third-party MEGA65 book snapshot in favor of a URL/SHA reference manifest.
Recording-time commit SHAs remain evidence identities and resolve to current
transport commits through `config/history-transport-map-20260718.json`.
Product bytes, archive bytes, sealed claims, and semantic history are
unchanged. Future archives are ignored local caches after construction and
must pass the history-size gate plus remote digest verification; neither Git
nor Git LFS is an allowed archive transport.
