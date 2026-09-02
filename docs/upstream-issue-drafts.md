# Upstream issue drafts (prioritized)

Companion to [upstream-findings.md](upstream-findings.md). Status 2026-07-27.
The verification result is recorded in
[upstream-verification-2026-07-19.md](upstream-verification-2026-07-19.md).
The consolidated L4–L11 owner packet, including exact evidence and filing
bars, is
[upstream-owner-bundle-2026-07-27.md](upstream-owner-bundle-2026-07-27.md).
Only sections explicitly marked **owner-ready** may be pasted upstream.

**Before filing anything:** re-verify against current upstream (AUR
`llvm-mos-bin` distrobox for L1–L3; current MEGA65 core for C1/C3; current
Xemu for X1–X3). File nothing that reproduces only on our pinned July-2026
states without saying so.

## Verification disposition

| State | Items | Rationale |
| --- | --- | --- |
| Owner-ready | C1 root-cause comment on core #674 | Historical hardware evidence plus current-source continuity; revisions are explicitly separated |
| One hardware smoke missing | L3, C3 | Current source/binary prepared, but no current-core hardware claim |
| Hold | L1, L2 | L1 reduced claim did not reproduce; L2 remains unroot-caused |
| Docs/proposals | C2, L4–L7, C4, C6, D1–D3 | Current enough to discuss, with the stated confidence limits |
| Reduced repro required | L8, L9 | Local artifacts are conclusive for the pinned toolchain, but neither is a current-upstream standalone reproduction |
| Discussion with hard claim limit | L10 | 691-ms historical curve is bound; exact core was not captured, so current-core defect filing remains blocked |
| Emulator | X1–X3 | X2/X3 source-confirmed; X1 still needs a reduced differential |
| — | V1 | Internal documentation note, no upstream issue |

---

## L3 (llvm-mos) — KERNAL screen scrolling crash

**Status: not owner-ready — run the attached current binary on hardware once.**

**Title:** `MEGA65: PRGs crash when KERNAL screen scrolling triggers (zero-page clash?)`

> Any PRG built with llvm-mos crashes on the MEGA65 as soon as the C65/MEGA65
> KERNAL performs a screen scroll (e.g. printing past the bottom row via
> CHROUT). Hardware-isolated 2026-07-02 on a MEGA65 (core `03b24c6b…`, stock
> KERNAL); reproduces deterministically.
>
> Attached is a 294-byte standalone repro built from
> `tools/upstream-repros/mega65_kernal_scroll.c`. It prints 32 numbered lines
> through CHROUT and then prints `OK`.
>
> Our working hypothesis is a zero-page convention clash: the KERNAL scroll
> routine touches ZP locations that the llvm-mos runtime (imaginary
> registers `__rc*`) considers its own. We worked around it with a custom
> screen driver that never lets the KERNAL scroll.
>
> Built with llvm-mos `8be0546128a55e78c63ca571d466aa72a782cd36`
> on 2026-07-19; PRG SHA-256
> `d439a7bb775ed160af6fc8274ed8a8a24bc783b8326f8c9afeb106fc12f8ab2f`.
> Hardware result: **pending; do not paste before it is recorded**.

## L1 (llvm-mos) — Variable-shift claim

**Status: closed for filing — reduced claim not reproduced.**

`tools/upstream-repros/variable_shift_mask.c` passed under both pinned compiler
`c798c314…` and current compiler `8be05461…` (3,162 simulator cycles, exit
zero). The historical GC failure remains documented, but the causal compiler
claim is not supported by the reconstructed expression. Do not file this
issue unless a larger reproducer actually fails.

## C1 (mega65-core) — Freezer leaves $D689 bit 7 (BUFSEL) set after disk swap

**Status: owner-ready as a root-cause comment on existing issue #674, not as
a new duplicate issue.**

**Title:** `Freezer exits with $D689 BUFSEL=1 after disk swap; programs using the $DE00 F011 buffer window silently write to the wrong buffer`

> Sequence: program uses the F011 sector buffer mapped at $DE00 → user
> enters the Freezer, swaps the D81 image, resumes → `$D689` bit 7 (BUFSEL)
> is now set, so the $DE00 window addresses the SD buffer instead of the
> F011 buffer. The resumed program continues with no observable error and
> reads/writes the wrong buffer.
>
> Hardware sequence on core `03b24c6b…`: boot with an SD-backed D81, enter the
> Freezer, attach another D81, resume, then read `$D689`; the inherited value
> was `$80`. A following F011 write modified the direct SD buffer while the
> F011 command wrote its unchanged own buffer; readback verification rejected
> the mismatch and the D81 remained byte-identical.
>
> Current source `a9158930665763c592d004c895d52eff4a9eefc3` still sets
> `$D689.7` for direct SD access and snapshots/restores `$D680..$D70F` around
> Freezer work, consistent with the diagnosis. This may explain open issue
> #674, “A 1581 does not work anymore once the freezer was accessed”. lisp65
> now forces `$D689=$00` for every F011 transaction. We can rerun a candidate
> or current core on real hardware.

## P2-1 (C2, mega65-core) — Feature proposal: HYPPO mount-lock for write transactions

**Note: sound out on Discord/forum first, then file as a discussion/PR.**

**Title:** `Proposal: user-callable HYPPO traps to lock/unlock drive-0 mount during multi-sector write transactions`

> A Freezer disk swap can occur in the middle of a multi-sector write
> transaction. The program has no way to prevent or even detect the swap
> window; in the worst case a BAM/directory sector belonging to disk A is
> written to disk B (we reproduced exactly this during hardware acceptance;
> media boundary crossed, both disks damaged).
>
> Proposal: two user-callable HYPPO traps — `mount_lock` / `mount_unlock`
> for drive-0 attach/detach, task-bound, cleared by reset — so a program can
> bracket a transaction. No polling, no busy-wait; the Freezer would refuse
> (or defer) image swaps while the lock is held.
>
> We have a worked design sketch (trap numbers, semantics, failure modes,
> reset behavior) and a real product that would adopt it immediately; happy
> to turn this into a PR if the approach is acceptable.

## P2-2 (L6, llvm-mos) — Documentation: LTO reorders stores across MMIO trigger stores

**Title:** `Docs: recommended MMIO/DMA pattern for mos targets (LTO store reordering)`

> With LTO, stores populating a DMA list in RAM were legally reordered past
> the MMIO store that triggers the DMA (volatile only orders the trigger,
> not the plain-RAM list writes). Classic trap on this platform; cost us a
> hardware debugging round.
>
> Suggestion: a short section in the mos target docs — populate DMA
> lists/buffers, then issue the trigger store via inline asm with a
> `"memory"` clobber (or an equivalent compiler barrier). We can contribute
> the text and a worked example.

## P2-3 (L5, llvm-mos) — Documentation: Z register contract for 45GS02 inline asm

**Title:** `Docs: inline asm on 45GS02 must restore Z=0 (Q-register ops)`

> llvm-mos-generated code relies on the 45GS02 Z register being 0. Inline
> asm using Q-register ops (`NEG NEG` prefixes etc.) alters Z; failing to
> restore Z=0 causes misbehavior far from the asm site. Undocumented; cost
> us a hardware debugging round. Suggest one paragraph in the mos target
> docs. We can contribute the text.

## P2-4 (L7, llvm-mos) — Documentation: MEGA65 physical addresses are not C pointers

**Title:** `Docs: distinguish 16-bit C pointers from wider platform physical/DMA addresses`

> On the MEGA65 target, `uintptr_t` correctly represents the 16-bit C pointer
> domain, while DMA and Attic endpoints are 28-bit physical values. Routing a
> value such as `$00050000` through `uintptr_t` truncates it; current mos-clang
> warns, but the platform-domain distinction is easy to miss.
>
> Suggestion: add a short target example that keeps physical endpoints in a
> fixed-width integer or writes their bytes directly into the DMA list, and
> reserves pointer types for C-addressable objects. This is a documentation
> request, not a compiler-bug report.

## P2-5 (C3, mega65-core or mega65-user-guide) — Flat memory access fails against bank 4 / colour RAM (contradicts the book)

**Re-verify on current core before filing; decide bug-vs-doc based on result.**

**Title:** `Flat memory access ([ptr],Z) fails for bank 4 and $FF80000 on real hardware; book App. K recommends it`

> The MEGA65 book (Appendix K-11) recommends 32-bit flat memory access as
> the preferred single-access idiom. On real hardware (stock core
> `03b24c6b…`,
> measured 2026-07-07) reads against bank 4 return $FF
> (`flat_bank4_obs=FAIL`) and reads against colour RAM $FF80000 fail
> (`flat_cell_obs=FAIL`); only bank-0 high RAM behaves as documented.
> Repro and readback procedure:
> `docs/archive/pre-1.0/reference/hardware-stress-tests.md`. Either the core deviates from the book or
> the book overpromises — both are worth an issue; we don't presume which.
>
> **Current-core hardware result is still pending; do not paste yet.**

## P3-1 (L2, llvm-mos) — Deterministic hang on real hardware with markstack GC (repro included, not root-caused)

**Status: hold. Frame honestly as "repro, cause unknown" — we never fully
root-caused it, and no current-toolchain hardware rerun exists.**

**Title:** `Deterministic hang on 45GS02 hardware, host build fine (repro included)`

> The attached `gcrepro-mega65.c` hangs deterministically on real MEGA65
> hardware while the equivalent host build runs correctly. We replaced the
> algorithm (markstack → fixpoint sweep) and never fully root-caused it, so
> this may be a codegen issue or a subtle error on our side — filing it
> because the repro is small and deterministic. Historical result only; a
> current-toolchain hardware rerun is required before filing.

## P3-2 (L4, llvm-mos) — Default linker script merges custom sections into .text

**Title:** `Custom output sections require a fully custom linker script; document or provide a hook`

> Sections like `.lisp65_boot` are silently merged into `.text` by the
> default mos linker scripts, which breaks overlay/boot layouts. A fully
> custom script works (reference:
> `scripts/lisp65-mega65-workbench-overlay.ld`), but the cliff
> from "default works" to "write everything yourself" is steep. Suggestion:
> document the pattern, or provide an include/hook for placeable custom
> sections.

## P3-3 (C4, mega65-user-guide) — Document memory survival across reset

**Title:** `Docs: which memory survives reset (measured matrix)`

> Measured on stock core `03b24c6b…`: on reset, HYPPO restages the C65 ROM to
> $20000–$3FFFF and also overwrites bank 1; bank 5 survives byte-exact;
> Attic RAM survives SHA-exact; nothing survives a power cycle. None of
> this is currently documented and it materially affects software design
> (caches, staging areas). We can contribute a "memory survival across
> reset" table for the iomap/User's Guide.

## P3-4 (C6, mega65-core) — Feature request: virtual write-protect for SD-backed D81 images

**Title:** `Virtual write-protect toggle for SD-backed D81 images`

> Physical floppies have a write-protect tab; SD-backed D81 images have no
> equivalent. Use case: master/product disks that should be mount-protected
> the way a physical disk can be. Today the only defense is software-side
> identity checking in every program that writes. A per-image WP flag
> (e.g. in the mount UI / D81 attach call) would close this gap.

## P3-5 (D1–D3, mega65 docs) — Three small documentation gaps

File as one issue or three tiny ones, maintainer's preference:

> 1. **Math unit missing from the Chipset Reference:** $D768–$D77F
>    (multiplier/divider) is documented only in book Appendix K, while all
>    other $D7xx registers are in the Chipset Reference.
> 2. **BUFSEL/Freezer interaction:** `$D689.7`, the `$D680=$81` mapping and
>    Freezer activity interact surprisingly (see mega65-core #674 and the C1
>    root-cause comment above);
>    deserves a warning box in the F011/SD section.
> 3. **`setname` alignment:** the requirement (page-aligned buffer below
>    $7E00) is easy to miss in the hypervisor appendix and produces a hard
>    to diagnose `$10 invalid address`; worth stating at the call site.

## P4 (C5, X1–X3) — Questions and emulator gaps

- **C5 (mega65-core, question):** after etherload boot, HYPPO DOS reports
  `dos_disk_count==0` and `selectdrive` fails with `$80 no_such_disk` — bug
  or expected uninitialized state? File as a question.
- **X1 (Xemu):** current source still describes immediate/incomplete F011
  behavior. Prepare a reduced status/timing differential before filing.
- **X2 (Xemu):** current `sdcard.c` explicitly keeps an SD-only mapped buffer
  and says the F011 buffer is not integrated. Source-confirmed current gap.
- **X3 (Xemu):** current `hypervisor.c` says Freezer is not enabled and the
  option remains `NOT YET WORKING`. Source-confirmed current gap.
- **Resolved keyboard note:** `$D60A/$D619` queue behavior is implemented in
  current `input_devices.c`; thank upstream and do not include it as a gap.

---

## Filing checklist (per issue)

1. Re-verify on current upstream; no placeholders or inferred current-hardware
   claims may remain.
2. Attach the standalone repro (no lisp65 context needed to run it).
3. Reference our receipt SHAs only as provenance, not as required reading.
4. Link related issues to each other (C1 ↔ D2, C3 ↔ book).
5. After filing: record the issue URL in `upstream-findings.md` next to the
   entry.

## Dedupe / pre-verification research (Claude, 2026-07-18, via GitHub API)

- **L1 (shift miscompile):** no upstream match found, but the 2026-07-19
  reduced re-verification passed under both pinned and current compilers.
  Filing is closed unless a failing larger reproduction is recovered.
- **L3 (KERNAL scroll crash):** no direct match; adjacent context only
  (llvm-mos #459 "interrupt C generation inadequate for CBM machines" —
  reference it as related IRQ/ZP-convention context, not a duplicate).
- **C1 (freezer BUFSEL):** no direct match, **but mega65-core #674 "A 1581
  does not work anymore once the freezer was accessed" (open) is very
  plausibly the same root cause reported as a symptom.** Our filing should
  cross-reference it ("possibly explains #674") — root-cause explanations
  for existing open symptom issues are the highest-value form of first
  contact. Also adjacent: #729 (images unmounted on freezer exit) for the
  C2 mount-lock proposal's problem framing.
- **C3 (flat access vs bank 4):** no upstream match — unreported.
- **L7 (uintptr_t width):** llvm-mos wiki spot-checks found no prominent
  documentation of the 16-bit `uintptr_t` / 28-bit physical-address split —
  consistent with "documentation trap" classification; Codex's distrobox
  round does the authoritative doc check before wording.
