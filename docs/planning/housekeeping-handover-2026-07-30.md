# Housekeeping handover to the implementation lane

Status: **current** — the parts of the housekeeping block that need a build.
Created 2026-07-30, after the block's own phases closed.

The housekeeping block was a paper-and-tooling block with zero product delta.
Four items cannot be finished that way: they need an ELF, and therefore a
link. They are collected here so they can ride a cycle that builds anyway
rather than justifying a build of their own.

Each item states what would make it green, so it can be worked without
re-deriving the reasoning.

## H-D remainder — comment translation in `lib/`

98 German comment lines remain across eleven Lisp sources:
`lib/lcc.lisp` (34), `lib/lcc-fasl.lisp` (15), `lib/stdlib-places.lisp` (13),
`lib/ide-ui.lisp` (11), `lib/ide-syntax.lisp` (6), `lib/ide-launch.lisp` (5),
`lib/prelude-macros.lisp` (5), `lib/ide-disk.lisp` (4),
`lib/ide-buffer.lisp` (2), `lib/stdlib-load.lisp` (2),
`lib/stdlib-load-lib.lisp` (1).

**Why it needs a link.** The compiler-tier generation binds `lib/lcc.lisp` and
`lib/dialect-v2/lcc-profile.lisp` by raw `sha256`
(`config/c2-bound-artifact-source-parity.json`, class `device-lcc-carrier`).
Editing a comment invalidates the bound carrier's source binding, and the only
honest repair is to regenerate the carrier.

**Green when:** the eleven files hold zero German comment lines, the carrier is
regenerated, and `c2-bound-artifact-source-parity-check` passes against the new
bytes. The bytecode itself must not move — comments are stripped by the reader,
so a byte difference in the emitted carrier means something else changed.

**Method that worked for the C sources** (193 lines, 21 files, zero product
delta *proven*): translate in bounded batches; print the flagged lines with
context first; apply exact-string replacements; verify with the project's own
detector and a syntax check. Then prove no semantic change — for C that was a
preprocessed token-stream comparison with the product compiler; for Lisp the
equivalent is a byte comparison of the emitted bytecode before and after.

## H-C1 — archive the dead sources

Never started. `src/l65m_batch_repeat.s` is still in `src/` and nothing was
moved.

**Why it needs a link.** The phase requires non-linkage to be proven *from the
ELF*, not from intuition — this project has four incidents behind that rule.

**Green when:** each candidate is shown absent from the linked C2-lite product
via `elf_truth`, then moved (not deleted) to a findable archive location, with
every citation of its old path updated. Candidates named in the plan: the L65M
materializer, the C1 compiler tier, the old decoders and emitters,
`lib/m65-disk-alloc*.lisp`, `src/l65m_batch_repeat.s`.

**Warning from this block:** the citation search must include citations that
appear as **JSON string values**, not only code references. Searching only for
code references is exactly how four cited config contracts were archived by
mistake and had to be restored (`766f994f`).

## H-C4 — retired-format decoders

Unverified. The no-dual-decoder rule was never checked in the *linked* product.

**Green when:** the linked product is shown to contain exactly one decoder per
format, and the retired formats (L65S-v3, C2I-v1, C2D-v1…v5, L65R-v1…v3) are
shown **structurally excluded** rather than merely unreferenced.

## H-F2 — clean rebuild against the sealed set

Not run in this block.

**Green when:** `workbench-product` built from a fresh checkout reproduces the
sealed v1.2.2 product set byte-for-byte.

**Note on what is already proven.** The block's own claim — that the comment
translation carries zero product delta — is proven independently and does not
depend on F2: every changed `.c` was preprocessed with
`tools/llvm-mos/bin/mos-mega65-clang -E -P` at `bc11ff7c~1` and at `HEAD`, and
all 13 token streams are byte-identical. F2 is the broader statement about the
whole product set.

## Two findings that belong to this lane, not to housekeeping

- **`check-source` is not green on the head that shipped v1.2.2.** Four gates
  fail identically at `b8405551`: the bound-artifact parity precondition, plus
  three around the v2 `while`/`random` surface whose contracts are committed
  ahead of their sources (`missing=['while']`; `random`/`random-seed` with no
  delivery; `%lcc-while` omitted without a declaration). Decide whether the
  in-flight work lands or the contracts are repinned — and why the acceptance
  chain did not report this.
- **`post_12_housekeeping.py --write` rebinds more than the check demands.**
  Run after an unrelated source change, it also rebound three
  architecture-block receipts whose staleness had nothing to do with that
  change, including one recording an older `lib/lcc.lisp` than the committed
  tree. That silently absorbs other people's in-flight drift into a
  housekeeping commit. The gratuitous rebindings were reverted; the `--write`
  path should be narrowed to what the check actually requires.

## Out of scope for this handover

Parked items stay parked (`docs/reference/parked-items-register.md`). The four
R6/G6 promotion archives (3.1 GB) are an owner decision, not implementation
work: `r6-g6-registered-seal-check` re-runs an isolated offline verifier from
inside the archive and is honestly red until they are materialized.

## Implementation-lane outcome — 2026-07-30

The build-bound lane ran at `647541f6bde71c7d4e12975ad011703458d5de26`.
Its append-only receipt is
`tests/bytecode/dialect-v2/evidence/post-release/post-v1.2-housekeeping-build-lane-receipt-20260730.json`.

- **H-D remainder: complete.** All 98 classified `lib/*.lisp` comment lines
  were translated. The regenerated carrier blob and its executed probe
  payload remained byte-identical. The source-bound candidate identity
  changed, as the raw-source contract requires.
- **H-C1: closed with no further move.** The final C2-lite ELF structurally
  excludes `vm_l65m_batch_repeat` and both retired L65M/L65S section families,
  but `src/l65m_batch_repeat.s` remains an active generic-workbench build and
  gate input and is cited by 49 immutable evidence receipts. Moving it would
  violate this plan's own citation rule. The two `m65-disk-alloc` prototypes
  were already archived under `tests/fixtures/legacy/m65d/`.
- **H-C4: complete.** `c2-linked-format-decoder-closure-check` is now a
  permanent post-link part of `workbench-product`. It proves one strict
  L65S-v4/C2I-v2/C2D-v6 chain and one strict L65R-v4 verifier pair from the
  final ELF and bound artifact headers; eight mutations are rejected.
- **H-F2: First Red, green condition unmet.** A detached, no-local fresh
  checkout ran the public entry point through the full link and produced the
  same post-comment candidate set `f40f958f…`. It correctly failed the
  published v1.2.2 authority `359809d4…` first at `linked-product-elf`.
  This is the already-recorded source/build-identity change, not a hidden
  compiler or carrier-byte change. No seal was repinned and no acceptance,
  promotion or release claim was made.
