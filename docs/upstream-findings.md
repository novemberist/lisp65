# Upstream Findings

This register collects bugs, documentation gaps, and feature proposals found
while developing lisp65. Each entry records its confidence, local evidence, and
the core of a future upstream issue. Reverify every finding against the current
upstream release before filing it.

Updated: 2026-07-27. Current-upstream verification details remain in
[`upstream-verification-2026-07-19.md`](upstream-verification-2026-07-19.md).
A refreshed, paste-ready L4–L10 packet is retained in the private proof
repository. Nothing was filed while preparing it.

## llvm-mos

Upstream: <https://github.com/llvm-mos/llvm-mos>

### L1 — Variable-shift workaround (reduced compiler claim not reproduced)

The early-July GC failed with `1u << (i & 7)` in its bitmap path, and lisp65
retains a fixed `markbit[8]` table as the safe implementation. The 2026-07-19
verification round reconstructed both the reduced expression and the original
bitmap-update shape, however, and both the pinned and current compilers passed
the simulator oracle.

Do not file the reduced expression as an llvm-mos bug. Evidence:
`tools/upstream-repros/variable_shift_mask.c`. A future report requires a
larger reproduction that actually retains the historical failure.

### L2 — Mark-stack GC freeze (suspected; reproduction retained)

A mark-stack GC froze deterministically on real MEGA65 hardware while remaining
green on the host. The root cause was not isolated; lisp65 replaced it with a
fixpoint sweep. Reproduction: `docs/gcrepro-mega65.c`.

Issue summary: deterministic real-45GS02 hang with a self-contained
reproduction; suspected code-generation or runtime interaction.

### L3 — KERNAL scrolling crashes llvm-mos programs (historical; current smoke pending)

An llvm-mos program crashes when C65/MEGA65 KERNAL screen scrolling triggers.
The isolated historical hardware reproduction was 336 bytes. A zero-page or
calling-convention conflict is suspected. lisp65 uses its own screen driver.
The current-toolchain replacement is a 294-byte PRG at
`tools/upstream-repros/mega65_kernal_scroll.c`; it has not yet been rerun on
hardware and therefore is not filing-ready.

Issue summary: KERNAL screen scrolling crashes an llvm-mos MEGA65 program;
attach the minimal reproduction and identify the likely convention conflict.

### L4 — Custom sections disappear into the default linker script (docs/feature)

Sections such as `.lisp65_boot` are merged into `.text` by the default script.
Overlay and boot-section layouts therefore require a complete custom linker
script. Request a documented placement hook or example. Working reference:
`scripts/lisp65-mega65-workbench-overlay.ld`. This remains true for the
current C2-lite source: the custom script is the sole placement truth, not an
optional legacy path.

### L5 — Z-register contract for 45GS02 inline assembly (docs; current gap checked)

llvm-mos uses Z internally. Inline assembly using Q-register operations must
restore Z to zero or execution fails. The current local gate derives every
C-called assembler function from the final ELF and verifies Z=0 on every
return/tail edge, so a newly added leaf cannot evade the rule through a stale
list. Request an explicit MOS-target ABI note.

### L6 — LTO reorders DMA-list stores past an MMIO trigger (docs; current gap checked)

Without a `"memory"` clobber, LTO moved DMA-list stores after the MMIO trigger
store. Request a documented MOS MMIO/DMA pattern using a register-free trigger
and a memory clobber. The hardened shape remains live in `src/mem.c`
(`ext_dma`): ordinary RAM list stores followed by register-free inline
assembly with `"a", "memory"`.

### L7 — 28-bit DMA addresses versus 16-bit `uintptr_t` (docs only)

The llvm-mos C pointer model for this target is 16-bit, while MEGA65
DMA/Attic endpoints are 28-bit physical addresses. Converting `$00050000`
through `uintptr_t` therefore changes the value to zero; the pinned compiler
correctly warned about that conversion. lisp65 now requires physical endpoints
to remain `uint32_t` values or explicit DMA-list bytes and forbids routing them
through pointer types.

The 2026-07-19 documentation check found no explicit MEGA65-domain warning.
Any upstream text must remain a documentation example rather than a compiler
bug. Evidence: the failed bounded `restart-repl` Attic-recovery probe and the
later G5 tool attribution in which normal F018B truncated `$08000000` to
`$00000000`.

### L8 — lld orphan handling precedes `.llvm_sympart` script disposition (candidate)

With the pinned llvm-mos lld, `--emit-relocs` plus `--lto-obj-path` exposes a
15-byte non-ALLOC `SHT_LLVM_SYMPART` input section. Under
`--orphan-handling=error`, lld reports that section as being placed in
`.llvm_sympart` and aborts even when the linker script either gives it an exact
address-zero INFO output with `KEEP` or names it in `/DISCARD/`. The saved LTO
object and both failed linker scripts are SHA-bound local evidence.

This is only a candidate, not a bug claim. Reduce the behavior outside lisp65
and compare it with current upstream lld before deciding whether it is a defect
or an undocumented ordering constraint in LTO partition handling. The
2026-07-27 owner packet binds the exact output-section and `/DISCARD/`
failures, the saved 15-byte section and the warning-wrapper final inventory.

### L9 — WPLTO `DEW` selects the wrong zero-page operand (candidate)

With pinned llvm-mos `c798c314…`, Link 33 compiled `rtov_crc_mem` so that the
loop tested the 16-bit length at `$7d/$7e` but emitted `DEW $16`. The length
therefore never changed and the first runtime-overlay CRC loop did not reach
its first DMA operation. Link 32 compiled the same source as two correct
bytewise `DEC` operations; the Link-33 ELF, LTO object, disassembly and hardware
First-Red capture are SHA-bound.

The local fix expresses the decrement as two target-stable byte operations and
every C2 product link now rejects `DEW` or a missing byte decrement. Upstream
work remains deliberately separate: reduce the Link-32/33 difference to a
minimal WPLTO reproducer, reproduce against current upstream HEAD, then decide
whether to file a code-generation defect. No compiler claim beyond the pinned
local artifact is made yet. The owner packet records the exact differential:
both loops test `$7d/$7e`; Link 32 decrements that length bytewise, while Link
33 emits `DEW $16` against `__rc20/__rc21`, already in the LTO object before
final linking.

## mega65-core

Upstream: <https://github.com/MEGA65/mega65-core>

### C1 — Freezer leaves `$D689.BUFSEL=$80` (historical hardware; current source checked)

After a Freezer disk swap, BUFSEL remains set to the SD buffer. Programs that
expect the F011 buffer at `$DE00` then address the wrong buffer. The Freezer
should restore BUFSEL on exit, or the behavior should be documented prominently.

Evidence: G6 case-4 oracle under the sealed hardware evidence, run on core
`03b24c6b…`. Current core source `a915893…` still contains the direct-SD
BUFSEL set and whole-register-range Freezer snapshot/restore consistent with
the diagnosis. Open core issue #674 is a plausible matching symptom; prefer a
root-cause comment there and clearly label the two different core revisions.

### C2 — Transaction-scoped HYPPO mount lock (feature)

A Freezer disk swap can occur during a multi-sector write transaction, and a
guest program cannot lock the mount. Propose user-callable lock/unlock HYPPO
traps for drive-0 attach/detach, scoped to the task and released by reset. This
should be an upstream capability rather than a lisp65 core fork.

Evidence: G6 mid-write media-swap analysis.

### C3 — Flat `[bp],Z` access fails for Bank 4 and Colour RAM (current hardware rerun pending)

On real hardware using an older 0.97.x core, reads through the flat-access form failed
for Bank 4 (`0xff`) and `$FF80000`, while Bank-0 high RAM passed. This conflicts
with the recommendation in MEGA65 Book appendix K-11 and is either a core bug or
a documentation error. Reproduction: `hw-access-smoke` and its readback scripts.

### C4 — Document memory survival across reset

Measurements show HYPPO restages the C65 ROM into `$20000–$3ffff` and overwrites
Bank 1 on reset. Bank 5 and Attic survive reset, while nothing survives a power
cycle. Request a reset-survival table in the I/O-map or user documentation.

### C5 — HYPPO DOS unavailable after Etherload boot (suspected)

After Etherload boot, `dos_disk_count==0` and `selectdrive` returns
`$80 no_such_disk`. Clarify whether this is expected uninitialized DOS state or
a HYPPO defect.

### C6 — Read-only switch for virtual D81 images (feature)

The stock-core Freezer mounts D81 images writable and offers no per-image
read-only switch. A physical floppy write-protect signal therefore does not
exist in an SD-D81 setup. Propose a Freezer control or HYPPO attach option that
clears write enable and exposes the state in mount status.

Reference: `config/g6-hardware-profile.json`, tested against core
`a9158930665763c592d004c895d52eff4a9eefc3`. In `src/hyppo/dos.asm`,
`dos_attach` sets `d81_image_flag_write_en` after a successful attach.

### L10 — Enhanced-DMA returns before an Attic-sourced target is stable (candidate)

The MEGA65 Chipset Reference and current User Guide source say that CPU
instruction execution remains stopped until a DMAgic job has completed.
Nevertheless, one bounded Link-34 hardware diagnostic observed two different
wrong CPU CRCs (`$8e92`, then `$e092`) over the same 1,156-byte Bank-0 target
immediately after an Enhanced-DMA copy from Attic memory; the bound source CRC
is `$b47f`. No software write or mapping change occurred between the reads.

The Link-35 follow-up then disproved the local ordered-marker workaround. A
same-size two-byte diagnostic patch held execution on the first failed CRC,
before verifier entry or wipe, while three read-only JTAG captures measured
the same 1,156-byte destination:

| Time after launch command | CRC | Bytes differing from expected |
| ---: | ---: | ---: |
| 1 ms | `$e8d8` | 1,133 |
| 691 ms | `$e856` | 0 |
| 2,381 ms | `$e856` | 0 |

The chained marker was already `$a5`; the immutable source stayed
byte-identical. Thus the marker reports job acceptance/ordering, not
CPU-visible completion, and the target converges afterward.

This is a mega65-core candidate despite the historical `L10` identifier. The
device runs did not capture their exact core revision, so no claim is made
against current development HEAD. The subsequent Chip-RAM prefilter bound
machine `TE0000B18447` to core `git-03b24c6b` and observed immediate normal
`$d700` transfers, but that later identity cannot be retroactively assigned to
the 691-ms run.

The G5 acceptance-tool campaign supplies corroborating, not causal, evidence:
normal F018B correctly served 20-bit Chip-RAM roles but truncated the
`$08000000` Attic destination to zero; the final green tool used Enhanced
`$d705` only for Attic roles and required content-defined readback retry. A
reduced L10 rerun must record core ID, core version/build, device model and job
bytes before an upstream defect submission. Only then decide whether the
defect is a slow-memory completion/drain bug or a documentation mismatch.
Local product work specifies content-defined completion independently of
upstream disposition. Contract:
`docs/planning/c2.2-runtime-overlay-dma-completion-contract.md`.

## MEGA65 documentation

### D1 — Multiplier/divider missing from the Chipset Reference

Registers `$D768–$D77F` appear in MEGA65 Book appendix K but not beside the
other `$D7xx` registers in the Chipset Reference.

### D2 — Document the BUFSEL/Freezer interaction

The relationship among `$D689.7`, `$D680=$81`, and Freezer activity deserves a
warning in the F011/SD documentation.

### D3 — Make `setname` page alignment prominent

The name buffer must be page-aligned below `$7e00`. The Hypervisor appendix
mentions this, but violating it produces the difficult-to-diagnose
`$10 invalid address` status.

## Xemu / xmega65

Upstream: <https://github.com/lgblgblgb/xemu>

Some items may already be documented. Check the current Xemu release and M65
project-status notes before filing.

### X1 — F011 sector-write emulation differs from hardware (current source still incomplete)

The write-calibration suite could be completed only on hardware; Xemu write
behavior differed from the real F011 path. Current Xemu source still documents
immediate/incomplete F011 behavior. File only with a reduced observable
differential.

### X2 — SD sector-buffer mapping differs from hardware (current source confirmed)

Current Xemu source says the F011 buffer is not integrated into the shared
buffer model and deliberately retains an SD-only I/O mapping after reverting
the combined mapping. This matches the local `$DE00`/`$FFD6E00` divergence.

### X3 — Freezer is not emulated (current source confirmed)

Current `hypervisor.c` reports that Freezer is not enabled and `configdb.c`
marks the option `NOT YET WORKING`. This prevents emulator coverage of the
entire Freezer-interaction class, including G6 findings C1 and C2.

## VICE / c1541

### V1 — `c1541 -validate` is destructive (documentation note, not a bug)

The command rewrites the BAM. lisp65 documentation and evidence handling must
never use it on the only copy of a disk image.

## Filing procedure

1. Reverify against current upstream HEAD or the latest release.
2. Reduce the reproduction so it runs without lisp65 context.
3. Reference lisp65 evidence SHAs, but attach all files needed to reproduce.
4. Discuss C2 with the MEGA65 community before preparing an implementation.
