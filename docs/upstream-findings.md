# Upstream Findings

This register collects bugs, documentation gaps, and feature proposals found
while developing lisp65. Each entry records its confidence, local evidence, and
the core of a future upstream issue. Reverify every finding against the current
upstream release before filing it.

Updated: 2026-07-15.

## llvm-mos

Upstream: <https://github.com/llvm-mos/llvm-mos>

### L1 — Variable-shift code-generation bug (verified)

`1u << (i & 7)` was miscompiled for the 45GS02 target. lisp65 uses a fixed
`markbit[8]` table in the GC as a workaround. A minimal reproduction can be
reconstructed from the early-July GC history.

Issue summary: variable shift with a masked count is miscompiled on a MOS
target; attach the reduced test and generated assembly.

### L2 — Mark-stack GC freeze (suspected; reproduction retained)

A mark-stack GC froze deterministically on real MEGA65 hardware while remaining
green on the host. The root cause was not isolated; lisp65 replaced it with a
fixpoint sweep. Reproduction: `docs/gcrepro-mega65.c`.

Issue summary: deterministic real-45GS02 hang with a self-contained
reproduction; suspected code-generation or runtime interaction.

### L3 — KERNAL scrolling crashes llvm-mos programs (verified)

An llvm-mos program crashes when C65/MEGA65 KERNAL screen scrolling triggers.
The isolated hardware reproduction was 336 bytes. A zero-page or calling-
convention conflict is suspected. lisp65 uses its own screen driver.

Issue summary: KERNAL screen scrolling crashes an llvm-mos MEGA65 program;
attach the minimal reproduction and identify the likely convention conflict.

### L4 — Custom sections disappear into the default linker script (docs/feature)

Sections such as `.lisp65_boot` are merged into `.text` by the default script.
Overlay and boot-section layouts therefore require a complete custom linker
script. Request a documented placement hook or example. Working reference:
`scripts/lisp65-mega65-workbench-overlay.ld`.

### L5 — Z-register contract for 45GS02 inline assembly (docs)

llvm-mos uses Z internally. Inline assembly using Q-register operations must
restore Z to zero or execution fails. Request an explicit MOS-target ABI note.

### L6 — LTO reorders DMA-list stores past an MMIO trigger (docs)

Without a `"memory"` clobber, LTO moved DMA-list stores after the MMIO trigger
store. Request a documented MOS MMIO/DMA pattern using a register-free trigger
and a memory clobber. Reference: `src/mem.c` (`ext_dma`).

## mega65-core

Upstream: <https://github.com/MEGA65/mega65-core>

### C1 — Freezer leaves `$D689.BUFSEL=$80` (verified; G6 finding)

After a Freezer disk swap, BUFSEL remains set to the SD buffer. Programs that
expect the F011 buffer at `$DE00` then address the wrong buffer. The Freezer
should restore BUFSEL on exit, or the behavior should be documented prominently.

Evidence: G6 case-4 oracle under the sealed hardware evidence.

### C2 — Transaction-scoped HYPPO mount lock (feature)

A Freezer disk swap can occur during a multi-sector write transaction, and a
guest program cannot lock the mount. Propose user-callable lock/unlock HYPPO
traps for drive-0 attach/detach, scoped to the task and released by reset. This
should be an upstream capability rather than a lisp65 core fork.

Evidence: G6 mid-write media-swap analysis.

### C3 — Flat `[bp],Z` access fails for Bank 4 and Colour RAM (verified)

On real hardware using a 0.97.x core, reads through the flat-access form failed
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

### X1 — F011 sector-write emulation differs from hardware (verified locally)

The write-calibration suite could be completed only on hardware; Xemu write
behavior differed from the real F011 path.

### X2 — SD sector-buffer mapping differs from hardware

The local Xemu version exposed behavior at `$DE00` that differed from real
hardware at `$FFD6E00`, causing buffer-test divergence.

### X3 — Freezer is not emulated

This prevents emulator coverage of the entire Freezer-interaction class,
including G6 findings C1 and C2.

## VICE / c1541

### V1 — `c1541 -validate` is destructive (documentation note, not a bug)

The command rewrites the BAM. lisp65 documentation and evidence handling must
never use it on the only copy of a disk image.

## Filing procedure

1. Reverify against current upstream HEAD or the latest release.
2. Reduce the reproduction so it runs without lisp65 context.
3. Reference lisp65 evidence SHAs, but attach all files needed to reproduce.
4. Discuss C2 with the MEGA65 community before preparing an implementation.
