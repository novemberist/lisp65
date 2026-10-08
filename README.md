# lisp65

## Comfort by default (since 2.5.0)

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
inside strings. Since 2.5.2, Backspace at an empty continuation line reopens
the previous line (`[edit previous line]`); Up/Down browse history.
See the [2.5.1 release notes](docs/releases/2.5.1-before-ship-r3.md) and the
[2.5.2 release notes](docs/releases/2.5.2.md).

lisp65 is a native, interactive Lisp workbench for the
[MEGA65](https://mega65.org/). It combines a Common Lisp-inspired language,
an on-device bytecode compiler, an Emacs-style full-screen editor, and
transactional 1581 disk persistence. This repository is a curated public
source snapshot of a private proof repository; accepted public changes are
validated there and returned in credited syncs.

The published baseline is **lisp65 2.5.4**, published on 2026-10-06, using
**Dialect V2** (public main `bdaf2dd9`, tag `v2.5.4`; see the
[2.5.4 release notes](docs/releases/2.5.4.md) and the
[device report](docs/planning/release-2.5.4-device-report.md)). **2.5.5** is the
current release candidate and is **not published**: its Final is built and
sealed and its device session passed, but it is not published and its
Before-Ship record is pending (see the [2.5.5 release notes](docs/releases/2.5.5.md)
and the [device report](docs/planning/release-2.5.5-device-report.md)). The
qualified product still displays `WORKBENCH 2.0.0` in its boot banner; the
published package version is 2.5.4. The known issues listed in the release
notes apply to the published release.

## Highlights

- 2.5.5 (release candidate, not published): typing in the IDE editor is
  faster. In the emulator a plain insert costs 57 ms instead of 124 to 150 ms
  and Backspace 60 ms instead of 107 to 133 ms, and the cost no longer grows
  with the column or the line (an emulator measurement, not a device timing).
  A garbage collection still costs about 120 ms and Return about 0.4 s. Native
  `.text` is unchanged; only the IDE library changes. The emulator rows on the
  Seed medium showed no product failure; the device session passed on
  2026-10-07 (manual owner session; the owner found typing strongly improved,
  Backspace still slightly delayed).
- 2.5.4: finished editing steps survive an
  interrupted IDE edit (RUN/STOP) when saving goes through the IDE, a key-binding
  seam `ide-bind-key` for packages (`C-x` plus a printable key), a cheaper IDE
  save string, `(funcall (lambda ...) args)` compiled as the direct form,
  `mapcan` with more than 12 results, argument-count checks for `eq`, `eql` and
  the bit operations, and three package corrections (bounded Comfort result
  output, `defstruct` name collisions, recalled history with a comment). Native
  `.text` is unchanged. The emulator rows on the Seed medium showed no product
  failure; the device session passed on 2026-10-05 (manual owner session).
- 2.5.3: larger IDE saves and
  `eval-buffer` runs, a lossless file load, disk writes only after a check of
  the whole disk, multi-pair `setq` and builtin argument counts in the
  compiler, and the prompt now returns after `*** VM: OUT OF MEMORY` (a heap
  filled by data the program still holds, such as a global list, still cannot
  be released from the keyboard and needs a reset).
- 2.5.2: Backspace reopens the previous Comfort line; measured emulator typing
  cost per key falls by 30.85 %; saving into the first entry of a directory
  sector no longer hides later directory entries.
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

The published baseline is `lisp65-2.5.4.tar.gz` from
the [v2.5.4 GitHub release](https://github.com/novemberist/lisp65/releases/tag/v2.5.4).
2.5.5 is a release candidate and is not available as a release.
Release bundles are GitHub Release assets and are not stored in Git history.

```sh
tar -xzf lisp65-2.5.4.tar.gz
cd lisp65-2.5.4
python3 verify.py
```

Do not use a bundle that fails verification. The verifier checks every package
file, the promoted product and package identities, and the embedded G5/G6
hardware-acceptance bindings without consulting the repository or the network.

See the [2.5.4 release notes](docs/releases/2.5.4.md) for the complete change
summary and evidence boundary.

## Reproduce the 2.5.2 release

Export a fresh source tree with `tools/host-lisp/c2_v252_r1_public_source.py`,
install the pinned LLVM-MOS toolchain there, and run sequentially:

```sh
PYTHONDONTWRITEBYTECODE=1 nice -n 18 ionice -c3 python3 -B tools/host-lisp/c2_v252_r1_public_product.py build
PYTHONDONTWRITEBYTECODE=1 nice -n 18 ionice -c3 python3 -B tools/host-lisp/c2_v252_r1_public_product.py check
```

The build requires no existing build directory. It checks the 2.5.2 Final
ELF, PRG, LTO and D81 identities and records every child command. See
`config/c2-v252-r1-public-build-authority.json` and the 2.5.2 release notes.
The 2.5.1 reproduction remains available through
`tools/host-lisp/c2_v251_r2_20260929_public_product.py`.

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
identity. There is no on-device disk formatter in 2.5.2.

See the [User Guide](docs/user-guide.md) for the complete workflow and the
[generated keymap](docs/generated/ide-keymap.md) for the authoritative editor
bindings.

## Maturity, known limitations, and roadmap

**lisp65 2.5.2 is an early, hardware-validated release.** It is suitable for
exploration, learning, and small projects with reliable backups. It should not
be treated as a general-purpose production environment for irreplaceable data,
unattended operation, or large applications.

| Current limitation | Practical effect | Planned direction |
| --- | --- | --- |
| Focused REPL editing | The native `lisp65>` prompt has lossless insertion-mode line editing. Default Comfort adds balanced multiline input and history. | Type-ahead during evaluation remains later work. |
| Structural editor display work deferred | Delimiter matching and cursor blinking passed host qualification but did not pass their bounded hardware round. | The full block remains sealed for a later release; v2.0 makes no matcher/blink claim. |
| Permissive hot `car`/`cdr` opcodes | Tier-1 library functions raise a VM type error on an unsupported domain, but the hot opcodes stay permissive: `(car nil)` and `(car 1)` both return `nil`. | A fully checked Tier-2 implementation was measured but did not fit the resident text budget; it remains sealed for the 2.x series. |
| Finite session metadata | Definitions are append-only and there is no dependency-safe `unload`. A session has 64 code images; a redefinition consumes a new one. At capacity a definition is refused with `OUT OF MEMORY` at a live prompt; a product-disk restart frees the images. | The C2D session store separates immutable code from mutable session state; slot reuse and dependency-aware reclamation remain later work. |
| Top-level anonymous `lambda` refused | An anonymous `lambda` outside a `defun` body is refused with `VM: BAD BYTECODE`; the prompt recovers and nothing already defined is affected. Lambdas inside `defun` bodies work. This includes `(funcall (lambda () ...))` at the Comfort prompt when the lambda captures a `let` variable (same in 2.5.2 and 2.5.3). 2.5.4 compiles `(funcall (lambda ...) args)` as the direct form; a lambda stored in a top-level form stays refused (both observed in the emulator on the Seed medium). | Set B is frozen; the stored-lambda refusal remains in 2.5.4. |
| Freezer during a definition | Idle Freezer entry is hardware-proven. Entering the Freezer while a persistent definition/append is active is not supported. | Return with F3 and cold-restart before relying on the interrupted definition. The crossing is explicit C2.3 work. |
| Heap held by live data cannot be released from the keyboard | In 2.5.2 the prompt could stay dead after `*** VM: OUT OF MEMORY`; the 2.5.3 candidate returns to the prompt (runaway garbage in a `let`-local, a failed IDE save, typing with many IDE buffers). If the heap is filled by data the program still holds, for example a global list, typing the form that drops it runs out of memory while it is typed, the Comfort prompt gives way to the native `LISP65>` and the data stays live. Observed in emulator runs. | Reset (power cycle); unsaved buffers are lost. |
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

The published 2.5.2 medium (D81 SHA-256 `ae4e2931bb79bc6d963a2334d67e0777e924c9b34db42ef16567f472c87a300d`)
passed a device session on 2026-09-30: all 21 automated groups passed, the
host tool clock measured 40.9 s to the `l65>` prompt, and the owner
physically confirmed typing and Backspace feel, reopening the previous line,
C-x q and RUN/STOP during a running form. The directory-link fix was confirmed
with a real user disk. Stopwatch cold boot remains open and physical C-x C-c
remains unavailable. See the
[2.5.2 release notes](docs/releases/2.5.2.md).

The 2.5.3 release passed a device session on 2026-10-03 (two rounds,
Final r8 medium D81 SHA-256 `7df9db67f16c7218e56c9e4b64dfc0ed512c43771c9c39d9ccd56ddc76e55c2f`):
all 49 executed automated groups passed, the host tool clock measured 42.8 s to
the `l65>` prompt (owner stopwatch about 43 s), and the owner physically
confirmed typing and Backspace feel, reopening the previous line, the string
example, C-x q, RUN/STOP and a physical C-x C-s on a 50x40 buffer. Two
observations remain unexplained: the display went black once after a Freezer
disk swap (every disk was intact afterwards; it did not recur in three later
swaps), and the physical save of the 50x40 buffer took several minutes. See
the [device report](docs/planning/release-2.5.3-device-report.md) and the
[2.5.3 release notes](docs/releases/2.5.3.md). 2.5.3 was published on
2026-10-03.

The 2.5.4 release passed a device session on 2026-10-05 (manual
owner session, Final medium D81 SHA-256 `250fdc763ae9e5b04cf149a6f2a7a3aa9fb293ff8da58e9a703e0c601efaef5d`,
read back byte-identical): boot took 42 s by the owner's stopwatch, physical
RUN/STOP aborted a running form and kept the visible editor text, the keymap
seam worked, and the 20x40 IDE save took 5 s (2.5.3: 37.7 s) with a
byte-identical readback. Findings, none a 2.5.4 regression by current
evidence: type-ahead typed while the editor opens is lost, typing in the IDE
editor is clearly slower than at the REPL, and `(m65d-remount)` is slow. Large
saves, out-of-memory rows and the `$D703` check were not done on the device.
See the [device report](docs/planning/release-2.5.4-device-report.md) and the
[2.5.4 release notes](docs/releases/2.5.4.md). 2.5.4 was published on
2026-10-06. Correction of a statement published with 2.5.4: the editor was
about 10 times slower than the REPL, not 30 times (the REPL glyph is visible
14.0 ms after the key; 4.17 ms was the time to the next input poll).

The 2.5.5 release candidate passed a device session on 2026-10-07 (manual
owner session, Final medium D81 SHA-256 `4f0b76ad395ed861da104960859b8d9416750a00684dd4826a1193b14245523b`,
read back byte-identical): boot unchanged at 20 s plus 22 s by the owner's
stopwatch; the owner found typing in the IDE editor strongly improved, with
Backspace still slightly delayed, more so when the key is held; a held key
gave 227 characters in 10 s in the editor and 202 at the prompt; two buffers
survived the physical RUN/STOP key, and two saved buffers and a 20x40 save
(4 s; 2.5.4: 5 s) read back as expected. The keymap seam, the long checklist
rows and the `$D703` check were not done on the device. The typing times in
the release notes are emulator measurements. See the
[device report](docs/planning/release-2.5.5-device-report.md) and the
[2.5.5 release notes](docs/releases/2.5.5.md). The Before-Ship record and
publication are pending.

### Historical 2.5.1 verification

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
canonical media packer. The 2.5.2 reproduction checks the O2-lite Final native and media identities
(ELF, PRG, LTO object and D81); the 2.5.1 reproduction checks the Strings Final.
The 2.5.1 product medium contains 20 files. The line editor is resident product freight.
The independently verifiable release bundle remains the
authority for hardware-acceptance claims.

## Documentation

- [User Guide](docs/user-guide.md)
- [Dialect V2 Language Reference](docs/language-reference.md)
- [Generated IDE Keymap](docs/generated/ide-keymap.md)
- [Release Notes for 2.5.5 (release candidate)](docs/releases/2.5.5.md)
- [Release Notes for 2.5.4](docs/releases/2.5.4.md)
- [Release Notes for 2.5.3](docs/releases/2.5.3.md)
- [Release Notes for 2.5.2](docs/releases/2.5.2.md)
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
