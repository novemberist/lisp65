# lisp65

lisp65 is a native, interactive Lisp workbench for the
[MEGA65](https://mega65.org/). It combines a Common Lisp-inspired language,
an on-device bytecode compiler, an Emacs-style full-screen editor, and
transactional 1581 disk persistence. This repository is a curated public
source snapshot of a private proof repository; accepted public changes are
validated there and returned in credited syncs.

The current release is **lisp65 1.8.0**, using **Dialect V2**.

## Highlights

- Native REPL and self-hosted `lcc` compiler on the MEGA65
- Lisp-2 semantics, macros, closures, higher-order functions, and strict arity
- Full-screen editor with one generated-and-tested L-full keymap
- On-demand IDE, IDEX, M65D, and first-class Buffer libraries
- C2-lite Chip-RAM execution with verified, publish-last cold staging
- Native `while` and an unbiased, seedable `random`
- Q8.7 fixed-point arithmetic, `(time form)`, `wait`, and `read-line`
- A reproducible Ship Builder for standalone bootable application D81s
- A lower-allocation editor renderer measured at about 3× the former speed
- Optional `v16core` library with insertion-mode REPL cursor navigation
- Native once-per-boot `INIT.L65` hook with fail-safe prompt recovery
- Faster fully derived empty-journal recovery
- Qualified native Capture/Hybrid substrate, shipped closed for v1.9 activation
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

Download `lisp65-1.8.0.tar.gz` from the
[v1.8.0 GitHub release](https://github.com/novemberist/lisp65/releases/tag/v1.8.0).
Release bundles are GitHub Release assets and are not stored in Git history.

```sh
tar -xzf lisp65-1.8.0.tar.gz
cd lisp65-1.8.0
python3 verify.py
```

Do not use a bundle that fails verification. The verifier checks every package
file, the promoted product and package identities, and the embedded G5/G6
hardware-acceptance bindings without consulting the repository or the network.

See the [1.8.0 release notes](docs/releases/1.8.0.md) for the complete change
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

5. Follow the three visible boot phases, then wait for the banner and REPL.
6. Mount `media/lisp65-library.d81` and activate the optional REPL line editor:

   ```lisp
   (require 'v16core)
   ```

7. Restore `L65SYS` and load the composition:

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
identity. There is no on-device disk formatter in 1.8.0.

See the [User Guide](docs/user-guide.md) for the complete workflow and the
[generated keymap](docs/generated/ide-keymap.md) for the authoritative editor
bindings.

## Maturity, known limitations, and roadmap

**lisp65 1.8.0 is an early, hardware-validated release.** It is suitable for
exploration, learning, and small projects with reliable backups. It should not
be treated as a general-purpose production environment for irreplaceable data,
unattended operation, or large applications.

| Current limitation | Practical effect | Planned direction |
| --- | --- | --- |
| Focused REPL editing | `v16core` adds insertion-mode cursor navigation to `(read-line)`. The bare `lisp65>` prompt remains a minimal C collector; balanced multiline input, history and Comfort are not delivered. | Capture is qualified but closed; native-client activation and Comfort remain later work. |
| Structural editor display work deferred | Delimiter matching and cursor blinking passed host qualification but did not pass their bounded hardware round. | The full block remains sealed for a later release; v1.8 makes no matcher/blink claim. |
| Finite session metadata | Definitions are append-only and there is no dependency-safe `unload`; exhaustion requires a product-disk restart. | The C2D session store separates immutable code from mutable session state; dependency-aware reclamation remains later work. |
| Freezer during a definition | Idle Freezer entry is hardware-proven. Entering the Freezer while a persistent definition/append is active is not supported. | Return with F3 and cold-restart before relying on the interrupted definition. The crossing is explicit C2.3 work. |
| Intermittent post-GC OOM | One 1,200-allocation `while` workload ended with `vm: out of memory`; the follow-up run did not reproduce it. | Preserve the exact form and preceding steps if it recurs; the reproducer remains in the test suite. |
| Fresh-session workflow | RUN/STOP aborts evaluation but keeps the session. The MEGA65 Reset button returns to BASIC rather than restarting lisp65. | Restart from the product disk for a fresh session; power-cycle for a cold start. `restart-repl` returns with C2.3. |
| Standalone scope | The Ship Builder packages L65P-v1 projects; it does not capture arbitrary live Workbench session state. | Start from one of the four supplied Ship projects and declare the entry and library closure. |
| Editor safety and discoverability | Buffers have fixed capacities. There is no undo/redo, interactive completion, integrated help, or full structural editing. | These remain measured post-1.2 work; no release date is promised. |
| File sizes are bounded | M65D and editor saves support 1–8,192 bytes. Evaluator `load` has a separate 38,400-byte staging ceiling; memory may become the practical limit earlier. | Larger files require a future storage/runtime design. |
| Xemu-only use has limited fidelity | Xemu is useful for logic and boot choreography, but F011 writes, SD buffer mapping, Freezer behavior, reset semantics, and timing remain hardware claims. | Emulator-valid tests remain a prefilter, never a hardware substitute. |
| Storage workflow remains narrow | One drive is supported, there is no on-device formatter, and a documented Freezer race can let at most one already-started sector cross a media boundary before status 12 stops further writes. | Keep backups. Multi-drive and core-assisted mount locking remain later work. |
| Banner colors persist after scrolling | The screen driver scrolls character cells but not color RAM, so text crossing the former banner rows can inherit its colors. Data and program state are unaffected. | A later color-RAM-aware scroll path must preserve the native post-boot ownership contract. |
| Function metadata is incomplete | Complete integrated help is not claimed for every native and macro entry. | Full metadata coverage and integrated help remain later work. |

Buffers print as the opaque marker `?`; inspect them with `buffer-ref` and
`buffer-length`. The physical product-medium write-protect case is not
applicable to the tested stock-core SD-D81 profile because it exposes no
physical or virtual write-protect medium.

These roadmap statements describe intent, not delivery promises. Every change
remains conditional on measured capacity, reproducible builds, and hardware
acceptance.

## Verification status

Release 1.8.0 binds artifact set
`cb6fee08d9f1b639a8d746edac0005e7398b02cf9acd781520ce3c99fc70d8ed`,
resident PRG
`4200c960a881af4822e9092c51555966837a7729c362682a933ae67a23f28aac`
and one-row library D81
`a89f28c32306d84028c469f8ee0b0c6f0d0eb42532a925b5338a64183ccd4768`:

- insertion, mixed cursor/control movement, endpoint movement, backward and
  forward deletion, and boundary no-ops passed on one physical MEGA65;
- an ordinary type error returned to a usable native prompt through the new
  retired-overlay execution backstop;
- valid and failing `INIT.L65` variants ran once before the first prompt, with
  a failing form returning promptly to a usable native REPL;
- the stopped D5 session retained 113 free symbol slots and 1,506 free name
  bytes, above the mandatory 32/384 user floor; and
- two varied fresh public clones reproduced all 22 selected roles with zero
  private evidence inputs.

Exact hashes and claim limits are recorded in the
[1.8.0 release notes](docs/releases/1.8.0.md). The maintained limitations and
retired 1.1 latency exception are in
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

Start with the [Development Guide](docs/development.md). Aggregate proof gates
that consume sealed evidence are available only in the private proof repository.
With the pinned LLVM-MOS SDK and `c1541` installed, the public C2-lite build is:

```sh
make clean
make workbench-product-v180
```

The target uses the single C2 emitter, one WPLTO closure, and the canonical
media packer. Its final gate requires all 19 product roles and the three-role
`v16core` library medium to reproduce the sealed 1.8.0 artifact-set identity.
The independently verifiable release bundle remains the
authority for hardware-acceptance claims.

## Documentation

- [User Guide](docs/user-guide.md)
- [Dialect V2 Language Reference](docs/language-reference.md)
- [Generated IDE Keymap](docs/generated/ide-keymap.md)
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
