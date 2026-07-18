# Development Guide

## Start here

lisp65 is developed as a capacity-constrained hardware product. A source change
is not complete merely because it compiles or passes a host test: product bytes,
memory floors, artifact identity, and evidence bindings are part of the change.

Release 1.0.0 is immutable. New work starts from the post-release branch and
must not amend its product or R4/R5/G6 archive bytes. The private proof mirror
had one owner-approved transport-only rewrite on 2026-07-18; the public release
tag did not move, and recording-time private commit IDs remain resolvable
through the checked transport map.

## Toolchain

The normal source gates require:

- Git
- GNU Make
- Python 3
- a C99 host compiler
- `c1541`
- an LLVM-MOS installation exposed as `tools/llvm-mos/bin/`
- a MEGA65 tools installation exposed as `tools/m65tools/` for hardware
  deployment

These third-party bundles are present in the private development environment
but are deliberately absent from the curated public repository. Use the
[external toolchain setup](toolchain-setup.md) to fetch and verify the pinned
LLVM-MOS release and to install the optional hardware tools. Both local paths
are ignored by Git; `LLVM_MOS_ROOT` and `M65TOOLS_ROOT` may point elsewhere.

Run the read-only prerequisite check first:

```sh
make doctor DOCTOR_GATE=G2
```

## Public source gates

The curated public repository contains the product source, build system, host
models, and unsealed fixtures. Its self-contained entry points are:

```sh
python3 tools/host-lisp/public_export.py selftest
python3 tools/host-lisp/public_export.py check
make source-syntax-check
make workbench-product
```

The first two commands verify the curated file boundary and reject private
paths, credentials, LFS objects, and bundled binary tools. The Make targets
check source syntax and build the canonical Workbench product with a separately
installed toolchain. Do not use a bare `make`: the historical default target
still describes the retired monolithic profile and is not the released
Workbench build.

## Private proof gates

The complete private mirror additionally provides the sealed evidence consumed
by these cumulative gates. Archives are ignored local caches materialized from
their SHA-bound private release assets; they are never committed or stored in
Git LFS:

```sh
python3 tools/host-lisp/evidence_archive_assets.py remote-check
python3 tools/host-lisp/evidence_archive_assets.py materialize --all
```

A normal full clone contains the object graph required to resolve historical
recording-time commit IDs. Bootstrap those local aliases with:

```sh
make history-transport-bootstrap
```

A `--single-branch` clone is intentionally insufficient. Fetch all private
branch/tag objects first if the bootstrap reports a missing transport target;
the diagnostic prints the exact `git fetch` command and fails closed rather
than installing a partial alias set.

The cumulative gates are:

```sh
make check-source
make check-host
make check-product
```

They are not public-source CI targets: omitting materialization while
pretending those gates still ran would weaken their claim. `make check` remains
the cumulative private MVP/product gate used by older workflows. Hardware
targets are never implied by a host-only command.

Before or after publishing documentation, compare the complete curated export
with the public checkout and verify the frozen release-document boundary:

```sh
python3 tools/host-lisp/public_export.py compare /path/to/public/lisp65
python3 tools/host-lisp/publication_drift.py --public-root /path/to/public/lisp65
```

The first command requires byte parity for every exported and tracked public
file. The second also verifies the release-bundle SHA and the immutable bundled
README classification. The tag-time README is never rewritten; current online
documents supersede it for usage instructions through an explicit release-page
notice.

## Change rules

1. **Probe first.** Measure a real differential link before accepting a memory
   estimate.
2. **Report every capacity delta.** Bank 0, EXT, symbol slots, name-pool bytes,
   and directory slots must be explicit in block receipts.
3. **Treat EXT as frozen for the 1.0 baseline.** The released candidate has one
   measured byte of margin and no further debit is authorized without structural
   relief.
4. **One source of truth.** Generated or parity-checked registries must cover all
   primitive and dispatch views.
5. **Fail closed.** A case cannot pass without a verified, identity-bound receipt.
6. **Product identity matters.** Any product-artifact SHA change invalidates
   inherited hardware receipts and requires the applicable fresh matrix.
7. **Seals are append-only.** Corrections create new documents and seals; sealed
   archives are never amended.
8. **Preserve claim limits.** Emulator, host, and hardware results must say
   exactly which domain they prove.
9. **Keep physical addresses out of pointer types.** The llvm-mos C address
   model uses 16-bit pointers and `uintptr_t`; MEGA65 DMA/Attic addresses are
   28-bit physical values. Carry them as `uint32_t` or as explicit DMA-list
   bytes. Cast through a pointer type only for a proven Bank-0 C object, never
   for a physical DMA endpoint.

## Documentation rules

- Write active user and contributor documentation in English.
- Keep user instructions separate from implementation contracts and evidence.
- Mark proposals as proposals; do not describe them as shipped behavior.
- Historical evidence may retain its original language and exact frozen claims.
- Keep the private export and public checkout byte-identical. Classify immutable
  release documentation explicitly instead of silently editing a sealed asset.
- Add every tracked Markdown file under `docs/` to
  `config/document-index.json` with the correct class.
- Run `make document-index-check` after adding, moving, or removing a document.

## Product and evidence flow

The current architecture uses the following chain:

1. Source and host gates establish semantic and structural correctness.
2. A reproducible product build creates the artifact-set identity.
3. R4 seals the product candidate.
4. R5 consumes R4 and binds the global hardware matrix.
5. R6 packages the same bytes and binds G6 boot/media acceptance.
6. R7 wraps the sealed product bytes in a self-verifying release bundle.

Harness-only repairs may retain already verified case receipts only when product
SHAs are unchanged and the offline verifier binds those receipts to the new
manifest. Product changes require fresh product-bound hardware evidence.

## Repository map

| Path | Purpose |
| --- | --- |
| `src/` | resident runtime, evaluator, VM, compiler, and platform code |
| `lib/` | Lisp standard library, IDE, compiler, and disk libraries |
| `products/` | separately built product components |
| `config/` | machine-readable contracts and registries |
| `tests/` | semantic, capacity, package, and evidence fixtures |
| `tools/host-lisp/` | host models, generators, verifiers, and packers |
| `scripts/` | build, emulator, deployment, and hardware harnesses |
| `docs/` | user docs, contracts, proposals, and historical records |
| `releases/` | small release receipts; bundles are GitHub Release assets |

The curated public snapshot is defined by
`config/public-export-policy.json`. Check it with:

```sh
python3 tools/host-lisp/public_export.py check
```

## Before committing

- Check `git status` and preserve unrelated user work.
- Run the relevant focused tests and the complete automated gates.
- Confirm that generated files and receipts are bound to the intended commit.
- Explain unexpected capacity gains as carefully as losses.
- In the full private proof mirror, use its
  `scripts/push-github-verified.sh` for a normal mirror push. It verifies
  archive assets, the 50 MB index/history ceiling, the promotion register,
  exact branch and tag equality via `git ls-remote`, and an empty Git LFS
  dry-run. `make proof-hooks-install` enables the private mirror's tracked
  pre-commit and pre-push gates. New promotion-v3 and G6-v2 seal manifests
  record `remote_source_binding.remote_head` and require their source commit to
  have reached that branch. These proof-transport scripts, hooks, receipts, and
  private asset inventory are deliberately absent from the curated public
  snapshot; they are not needed to build or use the product.

## GitHub repository metadata

The intended public-facing description and topics are declared in
`config/github-repository-metadata.json`. Apply them only from an authenticated
GitHub CLI session, then read the repository metadata back and compare it with
the file. Repository access and source licensing are separate decisions; do not
make a private repository public merely to update its description.
