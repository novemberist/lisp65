# lisp65

lisp65 is a native, interactive Lisp workbench for the [MEGA65](https://mega65.org/).
It combines a Common Lisp–inspired language, an on-device bytecode compiler, an
Emacs-style full-screen editor, and transactional 1581 disk persistence.

The current release is **lisp65 1.0.0**, which contains **Dialect V2**. Product
and dialect versions are independent; Dialect V1 was an internal development
profile and was never released.

## Highlights

- Native REPL and self-hosted `lcc` compiler on the MEGA65
- Lisp-2 semantics, macros, closures, higher-order functions, and strict arity
- Full-screen editor with Emacs-style navigation and file workflows
- On-demand IDE, IDEX, and M65D libraries
- Copy-on-write disk persistence with read-back verification
- Cold boot from an SD-backed D81 image without a connected development PC
- Reproducible, self-verifying release bundle with hardware-bound receipts

## Get the release

Download `lisp65-1.0.0.tar.gz` from the
[v1.0.0 GitHub release](https://github.com/novemberist/lisp65/releases/tag/v1.0.0).
Release bundles are published as assets and are not stored in the public Git
history.

```sh
tar -xzf lisp65-1.0.0.tar.gz
cd lisp65-1.0.0
python3 verify.py
```

The verifier checks the complete package, its product artifacts, and the
embedded G6 hardware-acceptance seal before you use either disk image.

## First boot

1. Mount `media/lisp65-product.d81` as `L65SYS` in drive 8 and boot it.
2. Wait for the stager to finish and for the REPL to appear.
3. Load the libraries you want while the product disk is still mounted.
4. Swap once to `media/lisp65-work.d81` or any other valid, non-product 1581
   disk before saving user files.

Try this at the REPL:

```lisp
(+ 20 22)
(load-lib "ide")
(load-lib "idex")  ; optional editor extensions
(load-lib "m65d")  ; load before the one-drive disk swap
(edit)
```

M65D accepts any valid 1581 work disk and rejects the product disk by identity.
There is no on-device disk formatter in 1.0.0.

See the [User Guide](docs/user-guide.md) for the editor keys, disk workflow,
error recovery, and current limitations.

## Verification status

Release 1.0.0 is bound to product artifact set `c41b9643…` and G6 seal
`b339a274…`:

- G3: passed as an emulator prefilter
- G5: 14/14 hardware cases passed
- G6: 5/5 profile-applicable hardware cases passed
- Physical product-medium write protection: not applicable to the tested
  stock-core SD-D81 profile

The exact claims, full hashes, toolchain provenance, and negative verification
tests are recorded in the [release receipt](releases/lisp65-1.0.0-receipt.json).
The public [artifact manifest](releases/lisp65-1.0.0-manifest.json) lists the
SHA-256 digest and byte count of every sealed product artifact.

The public repository is a curated source snapshot with independent Git
history. Its `v1.0.0` tag therefore has a different Git object identity from
the private proof tag. The release receipt preserves the authoritative proof
source commit (`5897294…`), while `PUBLIC-SOURCE-MANIFEST.json` binds every file
in the public snapshot to the private cleanup commit from which it was exported.

## Building from source

The source tree is primarily for lisp65 development. It requires GNU Make,
Python 3, a C99 host compiler, `c1541`, LLVM-MOS, and the MEGA65 tools for
hardware deployment. The public repository does not redistribute either
third-party tool bundle; install them separately at the paths described in the
[Development Guide](docs/development.md).

```sh
make doctor DOCTOR_GATE=G2
python3 tools/host-lisp/public_export.py check
make source-syntax-check
make workbench-product
```

Start with the [Development Guide](docs/development.md) before changing product
code or memory budgets. The aggregate `check-source`, `check-host`, and
`check-product` targets consume sealed evidence and are therefore available
only in the private proof repository.

## Documentation

- [User Guide](docs/user-guide.md)
- [Dialect V2 Language Reference](docs/language-reference.md)
- [Development Guide](docs/development.md)
- [Architecture Overview](docs/architecture-overview.md)
- [Documentation Index](docs/README.md)
- [Release Notes for 1.0.0](docs/releases/1.0.0.md)

## Scope

lisp65 is intentionally a practical Common Lisp–inspired subset, not a complete
ANSI Common Lisp implementation. It is native to the MEGA65 and does not target
C64 compatibility. Performance-sensitive work is expected to use coarse native
primitives and MEGA65 hardware services rather than tight bytecode loops.

## Licensing and public distribution

lisp65's original source and documentation are licensed under the
[Mozilla Public License 2.0](LICENSE). See [license scope](LICENSE-SCOPE.md),
[runtime redistribution](RUNTIME-REDISTRIBUTION.md), and
[third-party notices](THIRD-PARTY-NOTICES.md) for the exact boundaries.

The complete proof and development mirror remains private. A separate public
repository is generated from an explicit allowlist; bundled toolchains,
third-party reference PDFs, sealed evidence, and release tarballs in Git/LFS
are excluded.
