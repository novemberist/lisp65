# lisp65

lisp65 is a native, interactive Lisp workbench for the [MEGA65](https://mega65.org/).
It combines a Common Lisp–inspired language, an on-device bytecode compiler, an
Emacs-style full-screen editor, and transactional 1581 disk persistence.

The current release is **lisp65 1.0.1**, which uses **Dialect V2**. Release
1.0.1 is a packaging and documentation correction; its 13 product artifacts
are byte-identical to the hardware-accepted 1.0.0 product set.

## Highlights

- Native REPL and self-hosted `lcc` compiler on the MEGA65
- Lisp-2 semantics, macros, closures, higher-order functions, and strict arity
- Full-screen editor with Emacs-style navigation and file workflows
- On-demand IDE, IDEX, and M65D libraries
- Copy-on-write disk persistence with read-back verification
- Start from an SD-backed D81 image without a connected development PC
- Reproducible, self-verifying release bundle with hardware-bound receipts

## Get the release

Download `lisp65-1.0.1.tar.gz` from the
[v1.0.1 GitHub release](https://github.com/novemberist/lisp65/releases/tag/v1.0.1).
Release bundles are published as assets and are not stored in the public Git
history.

```sh
tar -xzf lisp65-1.0.1.tar.gz
cd lisp65-1.0.1
python3 verify.py
```

The verifier checks the complete package, its product artifacts, and the
embedded G6 hardware-acceptance seal before you use either disk image.

The 1.0.1 archive corrects the first-session instructions while preserving all
13 product artifacts byte-for-byte. The original 1.0.0 archive and tag remain
immutable historical evidence. See the [1.0.1 release notes](docs/releases/1.0.1.md)
for the exact package-only delta.

## First start from BASIC

1. Make `media/lisp65-product.d81` available on the MEGA65 SD card.
2. Power on the MEGA65 and wait for the BASIC 65 prompt.
3. Mount the product D81 in drive 8 using the Freezer, then return to BASIC
   without rebooting. You can instead use BASIC's `MOUNT` command if the image
   is accessible by name on the SD card.
4. Start the lisp65 boot stager from BASIC:

   ```basic
   DLOAD "AUTOBOOT.C65",U8
   RUN
   ```

5. Wait for the stager to finish and for the REPL to appear.
6. Load the libraries you want while the product disk is still mounted.
7. Swap once to `media/lisp65-work.d81` or any other valid, non-product 1581
   disk before saving user files.

The MEGA65 does not retain a D81 selected in the Freezer across a reboot. An
automatic cold start therefore requires separately configuring a default disk
image in the MEGA65 Config menu; it is not assumed by this procedure.

Try this at the REPL:

```lisp
(+ 20 22)
(load-lib "ide")
(load-lib "idex")  ; optional editor extensions
(load-lib "m65d")  ; load before the one-drive disk swap
(edit)
```

M65D accepts any valid 1581 work disk and rejects the product disk by identity.
There is no on-device disk formatter in 1.0.1.

See the [User Guide](docs/user-guide.md) for the editor keys, disk workflow,
error recovery, and current limitations.

## IDE input erratum for 1.0.0

A post-release end-to-end audit found that the editor backends are more complete
than the physical keyboard path that exposes them. Release 1.0.0 reads a
KERNAL/PETSCII code but does not retain the MEGA65 Control, MEGA, or Alt state.
The hardware UX receipts injected normalized key events after that boundary, so
they do not prove every documented physical chord.

- Load `ide`, `idex`, and `m65d` from `L65SYS` before the one-drive swap. The
  1.0.0 bundled `README-FIRST.txt` listed only `ide`; 1.0.1 corrects that
  package instruction.
- The command launcher implemented by 1.0.0 is `C-x x` or `C-x Return`, not
  physical `M-x`, and it requires IDEX.
- `C-Space` cannot reach the 1.0.0 dispatcher and must be treated as broken.
  Mark- and region-based keyboard workflows are therefore not usable as
  documented.
- Other Control and `C-x` bindings have working dispatcher/backend tests, but
  their physical keyboard path was not accepted end to end. Treat them as
  experimental; for a reliable save, leave the editor and call
  `save-buffer-to` explicitly after loading M65D.
- `compile-load` and `compile-buffer-to-lib` require an existing, preallocated
  FASL target. The supplied blank work D81 contains no `fasl0`--`fasl2` slots,
  so persistent on-device compilation is not available out of the box in the
  supplied bundle.

Release 1.0.1 ships these documentation corrections and the corrected load
order without changing product bytes. It deliberately does not provision FASL
slots: the legacy compiler writer does not share M65D's product-media guard or
transaction binding. Persistent compilation remains unavailable on the blank
work image until the transactional 1.1 redesign. The modifier-aware MEGA65
keyboard driver and fully bound keymap also belong to 1.1.

## Maturity, known limitations, and roadmap

**lisp65 1.0.1 is an early, hardware-validated release.** It is suitable for
exploration, learning, and small projects with reliable backups. It should not
yet be treated as a general-purpose production environment for irreplaceable
data, unattended operation, or large applications.

| Current limitation | Practical effect | Planned direction |
| --- | --- | --- |
| Finite session metadata | The released baseline leaves 120 symbol entries, 2,160 name-pool bytes, and 32 L65M directory entries. Libraries and definitions are append-only in 1.0.0; there is no `unload`, so a long or heavily composed session can exhaust a pool and require a restart. | 1.1 plans export-only interning, measured capacity relief, and dependency-safe LIFO `unload`. |
| Libraries come from the product medium | With one drive, IDE, IDEX, and M65D must be loaded before swapping from the product D81 to a work disk. | The 1.1 Attic library shelf is intended to remove the post-boot library-disk dependency. |
| IDE keyboard path is incomplete | Arrow navigation is usable, but the 1.0.0 input path loses modifier identity. `C-Space` is broken, physical `M-x` is not implemented, and the other documented chords lack an end-to-end physical-key receipt. | 1.0.1 corrects packaging and documentation only. 1.1 replaces the input path and binds every documented key. |
| Blank work media has no compiler targets | Persistent compilation requires an existing preallocated FASL slot, but the supplied blank work D81 has no `fasl0`--`fasl2`; `compile-load` therefore reports `slot missing` without externally provisioned media. | 1.1 replaces the slot writer with the M65D copy-on-write transaction and removes preallocated slots. |
| No standalone application builder | The on-device compiler creates and loads L65M modules for the current Workbench. It cannot yet produce a self-contained runtime or bootable application disk. | An on-device ship builder is the lead goal for 1.2. |
| Editor safety and discoverability are limited | Buffers have fixed capacities. There is no undo/redo, interactive symbol completion, integrated help, or full Lisp-aware structural editing. | 1.1 plans measured undo, incremental search, S-expression navigation, completion, and help; full Paredit is not promised. |
| File sizes are bounded | M65D and editor saves accept payloads from 1 through 8,192 bytes, so 8 KiB is the maximum supported editable load/save round trip. Evaluator `load` has a separate 38,400-byte staging ceiling; editor memory may become the practical limit before that. | 1.1 buffer work targets safer construction and better capacity use, but no larger file-size limit is currently promised. |
| Xemu-only use has limited fidelity | Xemu is useful for evaluator, compiler, editor, and boot-choreography checks, but it is not a complete substitute for a MEGA65. Known local gaps include F011 sector writes, SD buffer mapping, and the missing Freezer; reset, timing, and media-swap behavior remain hardware-only claims. | Emulator-valid tests remain a prefilter. Broader emulator-only support depends partly on upstream Xemu behavior and has no promised release date. |
| Storage workflow remains narrow | Release 1.0.1 supports one drive, has no on-device formatter, and retains a documented Freezer media-swap race in which at most one already-started sector can cross the media boundary before writes stop. | Keep backups now. Multi-drive support and stronger core-assisted mount locking remain later work, without a promised release date. |

These roadmap items describe current intent, not release dates or compatibility
promises. Each change remains conditional on measured capacity, reproducible
builds, and hardware acceptance.

## Verification status

Release 1.0.1 reuses product artifact set `c41b9643…` and G6 seal
`b339a274…`:

- G3: passed as an emulator prefilter
- G5: 14/14 hardware cases passed
- G6: 5/5 profile-applicable hardware cases passed
- Physical product-medium write protection: not applicable to the tested
  stock-core SD-D81 profile

The exact claims, full hashes, toolchain provenance, and negative verification
tests are recorded in the [1.0.1 release receipt](releases/lisp65-1.0.1-receipt.json).
The public [1.0.1 artifact manifest](releases/lisp65-1.0.1-manifest.json) lists the
SHA-256 digest and byte count of every sealed product artifact.

The public repository is a curated source snapshot with independent Git
history. Its tags therefore have different Git object identities from the
private proof tags. The 1.0.1 release receipt preserves authoritative proof
source commit `5479471…` (the 1.0.0 receipt retains `5897294…`), while
`PUBLIC-SOURCE-MANIFEST.json` binds every file in the public snapshot to the
private cleanup commit from which it was exported.

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
- [Release Notes for 1.0.1](docs/releases/1.0.1.md)
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
