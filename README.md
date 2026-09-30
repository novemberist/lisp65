# lisp65

## Comfort by default (2.5.1)

The product starts in Comfort at `l65>`. Balanced multiline input, automatic
indentation, string/comment-aware parenthesis tracking and ten-line Up/Down
history are available immediately. Excess closing parentheses print
`*** reader: unmatched close parenthesis` without evaluating the input.
Errors, RUN/STOP aborts and refusals return to `l65>` with definitions and
history intact. An empty line leaves to `lisp65>` and stays native; `(repl)`
re-arms Comfort. Top-level anonymous lambdas outside `defun` remain refused.

Boot takes about +8 s over 2.4.0 in the emulator (+7.65 s measured); the 2.5.0 automated device session
reported about +6.7 s on a host tool clock. Starting in Comfort costs +8 symbols, +105 name bytes,
+1 code image, +7 C2D entries/roots and five more boot collections. After exit
to the native prompt, the matched forced collection has +12 live cells and
+2.1% cycles; natural collection cycles are −1.7%. These are emulator
measurements, not device timings or worst-case pause guarantees. The owner
accepted this named GC cost for the inherited Comfort product.

Use `C-x q` to exit the IDE normally with buffers preserved; release Ctrl
before q. The owner physically confirmed C-x q on the released product.
Physical `C-x C-c` does not reach the IDE and remains a known issue.
Typing latency in the MEASURED native lane falls from 3.24 M -> 1.58 M
cycles/key (approximately 80 -> 39 ms). Backspace code-object reads fall from
roughly 1,200–1,800 -> 53 reads/key in the projected lane. The owner physically
confirmed considerably improved normal typing and Backspace feel. The earlier small Backspace tail change also
reduces host VM instructions. Comfort multi-line strings now evaluate and
display correctly, preserving typed spaces without automatic indentation
inside strings. Continuation lines are not editable after Return; Up/Down
always walk history. The multi-line editing card follows.
See the [2.5.1 release notes](docs/releases/2.5.1-before-ship-r3.md).

lisp65 is a native, interactive Lisp workbench for the
[MEGA65](https://mega65.org/). It combines a Common Lisp-inspired language,
an on-device bytecode compiler, an Emacs-style full-screen editor, and
transactional 1581 disk persistence. This repository is a curated public
source snapshot of a private proof repository; accepted public changes are
validated there and returned in credited syncs.

The published baseline is **lisp65 2.5.1**, published on 2026-09-29, using
**Dialect V2**. **2.5.2** is in release preparation: its Final is sealed and its device session passed; it is not yet published (see the [2.5.2 release notes](docs/releases/2.5.2.md)). 2.5.1 is a
product release: the qualified product still displays `WORKBENCH 2.0.0` in
its boot banner; the published package version is 2.5.1. See the
[2.5.1 release notes](docs/releases/2.5.1-before-ship-r3.md) for the change summary and
evidence boundary.

## Highlights

- 2.5.1: C-x q exits the IDE; editor list walks reduce measured native typing
  latency; Comfort multi-line strings evaluate and display correctly.
- 2.5.0: Comfort starts automatically at `l65>`.

- 2.4.0: faster start and use. On the device, RUN to the prompt took 32.7 s
  (tool clock), with `Initializing...` shown until the banner is ready. On
  the emulator, each `require` is at least 11.24 s faster, a five-slot
  `defstruct` fell from 31.21 s to 16.84 s, and the cost per typed key at the
  native prompt by about 38 %.
- 2.4.0: the symbol table holds 1,008 symbols instead of 795, a `defstruct`
  publishes as one code image, `compile-string` works, and a definition
  group beyond the 64-image capacity is refused with `OUT OF MEMORY` at a
  live prompt.
- 2.4.0: two 2.3.0 defects are fixed. A `defun` published from inside a
  running form survives, and an error raised through `eval` inside a running
  form returns to a live prompt with the exact error.

- Native REPL and self-hosted `lcc` compiler on the MEGA65
- Lisp-2 semantics, macros, closures, higher-order functions, and strict arity
- Full-screen editor with one generated-and-tested L-full keymap
- Explicit list-domain errors instead of plausible but invalid results in
  twenty-one Tier-1 library functions
- On-demand IDE, IDEX, and M65D libraries from the product disk
- C2-lite Chip-RAM execution with verified, publish-last cold staging
- Native `while` and an unbiased, seedable `random`
- Q8.7 fixed-point arithmetic, `(time form)`, `wait`, and `read-line`
- A reproducible Ship Builder for standalone bootable application D81s
- A lower-allocation editor renderer measured at about 3× the former speed
- Native `lisp65>` prompt with insertion-mode cursor navigation
- Lossless prompt input across garbage collection on physical hardware
- Native once-per-boot `INIT.L65` hook with fail-safe prompt recovery
- Faster fully derived empty-journal recovery
- Native Capture/Hybrid input with one queue owner and a delivered ring consumer
- Immediate non-persistent REPL expressions, with durable state changes kept on
  the transactional publication path
- Visible `STAGING MEDIA`, `BUILDING HEAP`, and `LOADING LIBRARIES` boot phases
- MAP-based CPU transport for mutable content, eliminating completion trust
  from every content-consuming mutable reader
- Published nullary and fixed-argument calls on the direct-call path
- Copy-on-write saves and persistent compilation with read-back verification
- Byte-identical rollback and a usable REPL after RUN/STOP
- Start from an SD-backed D81 image without a connected development PC
- Reproducible, self-verifying release bundle with hardware-bound receipts

## Get the release

The published baseline is `lisp65-2.5.1.tar.gz` from
the [v2.5.1 GitHub release](https://github.com/novemberist/lisp65/releases/tag/v2.5.1).
Release bundles are GitHub Release assets and are not stored in Git history.

```sh
tar -xzf lisp65-2.5.1.tar.gz
cd lisp65-2.5.1
python3 verify.py
```

Do not use a bundle that fails verification. The verifier checks every package
file, the promoted product and package identities, and the embedded G5/G6
hardware-acceptance bindings without consulting the repository or the network.

See the [2.5.1 release notes](docs/releases/2.5.1-before-ship-r3.md) for the complete change
summary and evidence boundary.

## Reproduce the 2.5.1 release

Export a fresh source tree with `tools/host-lisp/c2_v251_r2_20260929_public_source.py`,
install the pinned LLVM-MOS toolchain there, and run sequentially:

```sh
PYTHONDONTWRITEBYTECODE=1 nice -n 18 ionice -c3 python3 -B tools/host-lisp/c2_v251_r2_20260929_public_product.py build
PYTHONDONTWRITEBYTECODE=1 nice -n 18 ionice -c3 python3 -B tools/host-lisp/c2_v251_r2_20260929_public_product.py check
```

The build requires no existing build directory. It checks the Strings Final
ELF, PRG, LTO and D81 identities and records every child command. See
`config/c2-v251-r2-20260929-public-build-authority.json` and the 2.5.1 release notes.

## Historical 2.4.0 reproduction

Use the pinned toolchain declared by the source snapshot, then run
`make workbench-product-v240-build` in a fresh checkout and
`make workbench-product-v240-verify` to check the result. The build refuses
an existing output directory; do not use an older default product target
to reproduce this release. See `config/c2-v240-public-native/manifest.json`
and `config/c2-v240-public-plane/README.md` for projection provenance. Two
independent release-chain reproductions match the ELF, the linked and the
completed PRG, the profile, all 13 media artifact roles, all 19 delivered
files and the D81.

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

5. Follow the three visible boot phases and `Initializing...`, then wait for
   the banner and REPL.
6. Use Cursor Left/Right, insertion and deletion directly at `lisp65>`.
7. Load the composition from `L65SYS`:

   ```lisp
   (load-lib "ide")
   (load-lib "idex")  ; optional editor extensions
   (load-lib "m65d")  ; persistence and compiler output
   ```

8. Swap once to `media/lisp65-work.d81` or any valid non-product 1581 disk.
9. Enter the editor with `(edit)`.

The MEGA65 does not retain a D81 selected in the Freezer across a reboot. An
automatic cold start therefore requires a default disk image configured in the
MEGA65 Config menu; this procedure does not assume one.

M65D accepts any valid non-product 1581 disk and denies `L65SYS` by product
identity. There is no on-device disk formatter in 2.5.1.

See the [User Guide](docs/user-guide.md) for the complete workflow and the
[generated keymap](docs/generated/ide-keymap.md) for the authoritative editor
bindings.

## Maturity, known limitations, and roadmap

**lisp65 2.5.1 is an early, hardware-validated release.** It is suitable for
exploration, learning, and small projects with reliable backups. It should not
be treated as a general-purpose production environment for irreplaceable data,
unattended operation, or large applications.

| Current limitation | Practical effect | Planned direction |
| --- | --- | --- |
| Focused REPL editing | The native `lisp65>` prompt has lossless insertion-mode line editing. Default Comfort adds balanced multiline input and history. | Type-ahead during evaluation remains later work. |
| Structural editor display work deferred | Delimiter matching and cursor blinking passed host qualification but did not pass their bounded hardware round. | The full block remains sealed for a later release; v2.0 makes no matcher/blink claim. |
| Permissive hot `car`/`cdr` opcodes | Tier-1 library functions raise a VM type error on an unsupported domain, but the hot opcodes stay permissive: `(car nil)` and `(car 1)` both return `nil`. | A fully checked Tier-2 implementation was measured but did not fit the resident text budget; it remains sealed for the 2.x series. |
| Finite session metadata | Definitions are append-only and there is no dependency-safe `unload`. A session has 64 code images; a redefinition consumes a new one. At capacity a definition is refused with `OUT OF MEMORY` at a live prompt; a product-disk restart frees the images. | The C2D session store separates immutable code from mutable session state; slot reuse and dependency-aware reclamation remain later work. |
| Top-level anonymous `lambda` refused | An anonymous `lambda` outside a `defun` body is refused with `VM: BAD BYTECODE`; the prompt recovers and nothing already defined is affected. Lambdas inside `defun` bodies work. | Set B is frozen; this limitation remains in 2.5.1. |
| Freezer during a definition | Idle Freezer entry is hardware-proven. Entering the Freezer while a persistent definition/append is active is not supported. | Return with F3 and cold-restart before relying on the interrupted definition. The crossing is explicit C2.3 work. |
| Intermittent post-GC OOM | One 1,200-allocation `while` workload ended with `vm: out of memory`; the follow-up run did not reproduce it. | Preserve the exact form and preceding steps if it recurs; the reproducer remains in the test suite. |
| Fresh-session workflow | RUN/STOP aborts evaluation but keeps the session. The MEGA65 Reset button returns to BASIC rather than restarting lisp65. | Restart from the product disk for a fresh session; power-cycle for a cold start. `restart-repl` returns with C2.3. |
| Standalone scope | The Ship Builder packages L65P-v1 projects; it does not capture arbitrary live Workbench session state. | Start from one of the five supplied Ship projects and declare the entry and library closure. |
| Editor safety and discoverability | Editor buffers have fixed capacities. There is no undo/redo, interactive completion, integrated help, or full structural editing. | These remain measured later work; no release date is promised. |
| File sizes are bounded | M65D and editor saves support 1–8,192 bytes. Evaluator `load` has a separate 38,400-byte staging ceiling; memory may become the practical limit earlier. | Larger files require a future storage/runtime design. |
| Xemu-only use has limited fidelity | Xemu is useful for logic and boot choreography, but F011 writes, SD buffer mapping, Freezer behavior, reset semantics, and timing remain hardware claims. | Emulator-valid tests remain a prefilter, never a hardware substitute. |
| Storage workflow remains narrow | One drive is supported, there is no on-device formatter, and a documented Freezer race can let at most one already-started sector cross a media boundary before status 12 stops further writes. | Keep backups. Multi-drive and core-assisted mount locking remain later work. |
| Banner colors persist after scrolling | The screen driver scrolls character cells but not color RAM, so text crossing the former banner rows can inherit its colors. Data and program state are unaffected. | A later color-RAM-aware scroll path must preserve the native post-boot ownership contract. |
| Function metadata is incomplete | Complete integrated help is not claimed for every native and macro entry. | Full metadata coverage and integrated help remain later work. |

The six disk packages include `buffer`, `place`, `string-extra`, `inspect`,
`defstruct` and `repl-comfort`. The 2.5.1 `INIT.L65` loads
`place`, `string-extra` and `repl-comfort` at boot; load the other three
by hand with `require`, for example `(require "buffer")`.
The physical product-medium write-protect case is not
applicable to the tested stock-core SD-D81 profile because it exposes no
physical or virtual write-protect medium.

These roadmap statements describe intent, not delivery promises. Every change
remains conditional on measured capacity, reproducible builds, and hardware
acceptance.

## Verification status

The published 2.5.1 medium passed 13/13 automated device rows on 2026-09-29.
The owner physically confirmed C-x q, the multi-line string example, and
improved typing/Backspace feel. Stopwatch cold boot and physical RUN/STOP
remain open; physical C-x C-c remains unavailable. See the
[published release note](docs/releases/2.5.1-before-ship-r3.md) for claim limits.

### Historical 2.4.0 verification

Release 2.4.0 was checked on one physical MEGA65 in an automated session
(virtual keyboard, owner not at the machine):

- the product D81 booted to a settled prompt, RUN to the prompt in 32.7 s
  (tool clock, not a stopwatch);
- the IDE and the five packages loaded; `setf`, `capitalize`, `who-calls`
  and `buffer-length` answered;
- `M-x` with 17 typed characters and a 17-character REPL line arrived
  complete and in order;
- three five-slot structures took the session from 761 to 822 symbols, each
  accessor returning 42;
- a `defun` published inside `dotimes`/`eval` returned 7, a nested `eval`
  error returned to a live prompt with the exact error, and a definition loop
  past the image capacity stopped with `OUT OF MEMORY` at a live prompt.

RUN/STOP inside a running form, a cold power cycle, the physical `C-x C-c`
IDE exit and the compile/save/reload row were not run on this medium. Exact
hashes and claim limits are recorded in the
[2.4.0 release notes](docs/releases/2.4.0.md). The maintained limitations and
retired exceptions are in
[Known Issues and Retired Exceptions](docs/known-issues.md).

The public repository is a curated source snapshot with independent Git
history. Its Git commit and tag object IDs therefore differ from the private
proof repository; the release receipt binds the public package back to the
authoritative product and evidence SHAs.

## Building from source

The source tree is primarily for lisp65 development. It requires GNU Make,
Python 3, and a C99 host compiler for the self-contained source gates. Some
development targets additionally require `c1541`, LLVM-MOS, and the MEGA65
tools. The public repository does not redistribute third-party tool bundles.

```sh
python3 tools/host-lisp/public_export.py selftest
python3 tools/host-lisp/public_export.py check
make source-syntax-check
python3 tools/host-lisp/asm_c_constant_contract.py selftest
```

The [Development Guide](docs/development.md) is the single authority for the
clone, doctor, build, D81 inspection, and deploy commands. Aggregate proof gates
that consume sealed evidence are available only in the private proof repository.
The public product path uses the single C2 emitter, one WPLTO closure, and the
canonical media packer. The 2.5.1 reproduction checks the Strings Final native and media identities;
its product medium contains 20 files. The line editor is resident product freight.
The independently verifiable release bundle remains the
authority for hardware-acceptance claims.

## Documentation

- [User Guide](docs/user-guide.md)
- [Dialect V2 Language Reference](docs/language-reference.md)
- [Generated IDE Keymap](docs/generated/ide-keymap.md)
- [Release Notes for 2.5.1](docs/releases/2.5.1-before-ship-r3.md)
- [Release Notes for 2.5.0](docs/releases/2.5.0.md)
- [Release Notes for 2.4.0](docs/releases/2.4.0.md)
- [Release Notes for 2.3.0](docs/releases/2.3.0.md)
- [Release Notes for 2.2.0](docs/releases/2.2.0.md)
- [Release Notes for 2.0.1](docs/releases/2.0.1.md)
- [Release Notes for 2.0.0](docs/releases/2.0.0.md)
- [Release Notes for 1.9.0](docs/releases/1.9.0.md)
- [Release Notes for 1.8.0](docs/releases/1.8.0.md)
- [Release Notes for 1.7.0](docs/releases/1.7.0.md)
- [Release Notes for 1.6.0](docs/releases/1.6.0.md)
- [Release Notes for 1.5.0](docs/releases/1.5.0.md)
- [Known Issues and Retired Exceptions](docs/known-issues.md)
- [Contributing](CONTRIBUTING.md)
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
