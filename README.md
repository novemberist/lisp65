# lisp65

lisp65 is a native, interactive Lisp workbench for the
[MEGA65](https://mega65.org/). It combines a Common Lisp-inspired language,
an on-device bytecode compiler, an Emacs-style full-screen editor, and
transactional 1581 disk persistence.

The current release is **lisp65 1.1.0**, using **Dialect V2**.

## Highlights

- Native REPL and self-hosted `lcc` compiler on the MEGA65
- Lisp-2 semantics, macros, closures, higher-order functions, and strict arity
- Full-screen editor with 41 generated-and-tested key bindings
- On-demand IDE, IDEX, M65D, and first-class Buffer libraries
- Attic-backed library shelf: staged libraries remain available after the disk swap
- Copy-on-write saves and persistent compilation with read-back verification
- Start from an SD-backed D81 image without a connected development PC
- Reproducible, self-verifying release bundle with hardware-bound receipts

## Get the release

Download `lisp65-1.1.0.tar.gz` from the
[v1.1.0 GitHub release](https://github.com/novemberist/lisp65/releases/tag/v1.1.0).
Release bundles are GitHub Release assets and are not stored in Git history.

```sh
tar -xzf lisp65-1.1.0.tar.gz
cd lisp65-1.1.0
python3 verify.py
```

Do not use a bundle that fails verification. The verifier checks every package
file, all 14 sealed product artifacts, and the embedded Wave 3 hardware-
acceptance seal without consulting the repository or the network.

See the [1.1.0 release notes](docs/releases/1.1.0.md) for the complete change
summary and evidence boundary.

## First start from BASIC

1. Copy `media/lisp65-product.d81` to the MEGA65 SD card.
2. Power on the MEGA65 and wait for the BASIC 65 prompt.
3. Mount the product D81 in drive 8 using the Freezer, then return to BASIC
   without rebooting. You may instead use BASIC's `MOUNT` command when the
   image is accessible by name.
4. Start the boot stager:

   ```basic
   DLOAD "AUTOBOOT.C65",U8
   RUN
   ```

5. Wait for the banner and REPL.
6. Load the composition while `L65SYS` is still mounted:

   ```lisp
   (load-lib "ide")
   (load-lib "idex")  ; optional editor extensions
   (load-lib "m65d")  ; persistence and compiler output
   ```

7. Swap once to `media/lisp65-work.d81` or any valid non-product 1581 disk.
8. Enter the editor with `(edit)`.

The MEGA65 does not retain a D81 selected in the Freezer across a reboot. An
automatic cold start therefore requires a default disk image configured in the
MEGA65 Config menu; this procedure does not assume one.

M65D accepts any valid non-product 1581 disk and denies `L65SYS` by product
identity. There is no on-device disk formatter in 1.1.0.

See the [User Guide](docs/user-guide.md) for the complete workflow and the
[generated keymap](docs/generated/ide-keymap.md) for the authoritative editor
bindings.

## Maturity, known limitations, and roadmap

**lisp65 1.1.0 is an early, hardware-validated release.** It is suitable for
exploration, learning, and small projects with reliable backups. It should not
be treated as a general-purpose production environment for irreplaceable data,
unattended operation, or large applications.

| Current limitation | Practical effect | Planned direction |
| --- | --- | --- |
| Finite session metadata | The sealed profile leaves 334 symbol entries, 5,079 name-pool bytes, and 168 directory entries. Definitions are append-only and there is no dependency-safe `unload`; exhaustion requires a product-disk restart. | C2 separates immutable code from mutable session state; `unload` remains a later dependency-aware feature. |
| Definition-to-call latency | The first call after a persistent definition takes about 1.90–1.96 seconds on the reference machine; isolated longer observations exist. Warm expressions take about 0.20 seconds. | Enter related definitions as one block to amortize the reload. C2 direct-Attic execution is the committed 1.2 cure. |
| Fresh-session workflow | RUN/STOP aborts evaluation but keeps the session. The MEGA65 Reset button returns to BASIC rather than restarting lisp65. | Restart from the product disk for a fresh session; power-cycle for a cold start. `restart-repl` returns with C2.3. |
| No standalone application builder | The compiler creates L65M modules for the current Workbench; it does not produce a self-contained runtime or bootable application disk. | A ship-builder remains a 1.2 product goal. |
| Editor safety and discoverability | Buffers have fixed capacities. There is no undo/redo, interactive completion, integrated help, or full structural editing. | These remain measured post-1.1 work; no release date is promised. |
| File sizes are bounded | M65D and editor saves support 1–8,192 bytes. Evaluator `load` has a separate 38,400-byte staging ceiling; memory may become the practical limit earlier. | Larger files require a future storage/runtime design. |
| Xemu-only use has limited fidelity | Xemu is useful for logic and boot choreography, but F011 writes, SD buffer mapping, Freezer behavior, reset semantics, and timing remain hardware claims. | Emulator-valid tests remain a prefilter, never a hardware substitute. |
| Storage workflow remains narrow | One drive is supported, there is no on-device formatter, and a documented Freezer race can let at most one already-started sector cross a media boundary before status 12 stops further writes. | Keep backups. Multi-drive and core-assisted mount locking remain later work. |
| Banner colors persist after scrolling | The screen driver scrolls character cells but not color RAM, so text crossing the former banner rows can inherit its colors. Data and program state are unaffected. | The color-RAM rider requires the C2 runtime-layout evolution. |
| Function metadata is incomplete | Exact arity is proven for 101 entries; 34 native or macro entries remain explicitly unresolved, so no complete integrated-help claim is made. | C2.2 supplies the metadata/carrier evolution. |

Buffers print as the opaque marker `?`; inspect them with `buffer-ref` and
`buffer-length`. The physical product-medium write-protect case is not
applicable to the tested stock-core SD-D81 profile because it exposes no
physical or virtual write-protect medium.

These roadmap statements describe intent, not delivery promises. Every change
remains conditional on measured capacity, reproducible builds, and hardware
acceptance.

## Verification status

Release 1.1.0 binds product artifact set
`048639695dd7ad9c35bd8e92b2ec4c0fba1e365385cfc680e90bb3ba1a860024`:

- G3: passed as an emulator prefilter
- G5: 14/14 hardware cases passed
- G6: 5/5 profile-applicable hardware cases passed on one physical MEGA65
- Physical product-medium write protection: not applicable in the tested
  stock-core SD-D81 profile

The G6 acceptance archive is self-contained, verified offline, reproducibly
packed, and rejects deliberate mutations. Exact hashes and toolchain provenance
are recorded in the [1.1.0 release receipt](releases/lisp65-1.1.0-receipt.json)
and [manifest](releases/lisp65-1.1.0-manifest.json).

The public repository is a curated source snapshot with independent Git
history. Its Git commit and tag object IDs therefore differ from the private
proof repository; the release receipt binds the public package back to the
authoritative product and evidence SHAs.

## Building from source

The source tree is primarily for lisp65 development. It requires GNU Make,
Python 3, a C99 host compiler, `c1541`, LLVM-MOS, and the MEGA65 tools. The
public repository does not redistribute third-party tool bundles.

```sh
make doctor DOCTOR_GATE=G2
python3 tools/host-lisp/public_export.py check
make source-syntax-check
make workbench-product
```

Start with the [Development Guide](docs/development.md). Aggregate proof gates
that consume sealed evidence are available only in the private proof repository.

## Documentation

- [User Guide](docs/user-guide.md)
- [Dialect V2 Language Reference](docs/language-reference.md)
- [Generated IDE Keymap](docs/generated/ide-keymap.md)
- [Release Notes for 1.1.0](docs/releases/1.1.0.md)
- [Development Guide](docs/development.md)
- [Architecture Overview](docs/architecture-overview.md)
- [Documentation Index](docs/README.md)

## Scope and licensing

lisp65 is intentionally a practical Common Lisp-inspired subset, not a complete
ANSI Common Lisp implementation. It is native to the MEGA65 and does not target
C64 compatibility.

lisp65's original source and documentation are licensed under the
[Mozilla Public License 2.0](LICENSE). See [license scope](LICENSE-SCOPE.md),
[runtime redistribution](RUNTIME-REDISTRIBUTION.md), and
[third-party notices](THIRD-PARTY-NOTICES.md) for the exact boundaries.

The complete proof/development mirror remains private. The public repository is
generated from an explicit allowlist; bundled toolchains, reference PDFs,
sealed evidence, and release tarballs in Git/LFS are excluded.
