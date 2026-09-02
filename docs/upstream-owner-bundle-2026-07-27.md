# Upstream owner bundle — L4–L11

Status: **final upstream recheck complete 2026-07-30; nothing filed**

Prepared: 2026-07-27 from private source
`084d51b1019b98ac0784c98842ef5950195d1cbd`; refreshed after v1.2.4
from private source `9b097f02e6ed052c107de5929d54717c4a8b8e19`.

This packet refreshes the llvm-mos findings L4–L9 and the historical
mega65-core findings L10–L11 against the current lisp65 repository. It deliberately
separates observations, documentation requests, bug candidates and filing
bars. The owner may paste only a section whose **Filing state** permits it,
after the stated final upstream recheck.

No issue, discussion, comment, pull request or other external action was
created while preparing this packet.

## Executive disposition

| ID | Upstream | Classification | Filing state |
|---|---|---|---|
| L1 | llvm-mos | historical workaround | **do not file**: reduced claim still does not reproduce |
| L3 | llvm-mos | historical hardware candidate | parked for device session S2; current binary has not run on hardware |
| L4 | llvm-mos | documentation/ergonomics proposal | **owner-paste-ready**, narrowed after current-doc search |
| L5 | llvm-mos | target ABI documentation proposal | **owner-paste-ready**, final recheck complete |
| L6 | llvm-mos | MMIO/LTO documentation proposal | **owner-paste-ready**, final recheck complete |
| L7 | llvm-mos | address-domain documentation proposal | owner-paste-ready; explicitly not a compiler bug |
| L8 | lld/llvm-mos | linker behavior candidate | **not file-ready** until reduced outside lisp65 and rerun on current lld |
| L9 | llvm-mos | WPLTO code-generation candidate | **not file-ready** until reduced and rerun on current llvm-mos |
| L10 | mega65-core/docs | DMA completion discussion with two measured curves | **text ready, target blocked**: repository Discussions are disabled; do not file as an Issue |
| L11 | mega65-core/docs | Audio-DMA documentation contradiction | **owner-paste-ready**, current Core/Guide recheck complete |

The final 2026-07-30 upstream recheck used:

- llvm-mos `8b616af9434fca963025615b4c752dd4dd5e0294`;
- llvm-mos-sdk `61e4e1ad5e85c3be980a9ef10c1ece869e8de319`;
- mega65-core `a9158930665763c592d004c895d52eff4a9eefc3`;
- MEGA65 User Guide `0210345cd9cf19629010277732280e9e7248771e`;
- the current llvm-mos Linker Script, Porting, FAQ and C Inline Assembly
  pages; and
- fresh issue-title/body searches in both upstream repositories.

No matching open report was found for L4–L7, L10 or the L11 documentation
correction. mega65-core issue
[#811](https://github.com/MEGA65/mega65-core/issues/811) is the closed
implementation history for Audio-DMA IRQs, not a documentation correction;
it strengthens L11's provenance. The mega65-core repository reports
`hasDiscussionsEnabled=false`, so L10 cannot currently be submitted to the
owner-mandated Discussions surface. This packet does not authorize silently
turning it into an Issue.

## L4 — custom-section placement

### Current local state

lisp65 still needs the complete custom linker script
`scripts/lisp65-mega65-workbench-overlay.ld`. The current product uses many
named boot, overlay, fixed-facade and runtime sections; the default platform
script is not an equivalent build path.

The final recheck found that the current Porting guide already documents the
complete-script pattern and `INCLUDE c.ld`, while the FAQ documents
allocatable/retained custom sections with `KEEP`. That satisfies the broad
"show a complete linker script" half of the original request. What remains
unclear is the application-level case: extending an installed platform's
default layout with a few VMA/LMA sections while retaining its standard
sections and assertions. The proposal is narrowed to that gap.

### Paste-ready text

**Title:** `Docs: extending an installed platform linker layout with custom VMA/LMA sections`

> We use named C/assembly sections for boot code and mutually exclusive
> overlays at distinct VMAs and LMAs.
>
> The current Porting guide already gives a complete-script example using
> `INCLUDE c.ld`, and the FAQ explains allocatable/retained custom sections.
> Those answer how to own a new platform script. What we could not find is
> the supported pattern for an application that starts from an installed
> platform target and wants to add a small number of output sections while
> retaining that target's standard sections, symbols and assertions.
>
> Is there a supported additive `-T`/`INCLUDE`/`INSERT` pattern for that
> application-level case? If so, could the linker or SDK documentation show
> a minimal example? If not, would an include/hook mechanism for platform
> layouts be acceptable?
>
> This is a documentation/ergonomics proposal. We are not claiming that the
> current default script violates its documented behavior.

**Filing state:** owner-paste-ready. The 2026-07-30 current-doc and issue
search found the general complete-script documentation but no
application-level extension example or matching report; keep the narrowed
wording above.

## L5 — 45GS02 Z-register invariant

### Current local state

The current product contains several hand-written assembler functions. The
permanent `c2_asm_leaf_abi_gate.py` derives C-called assembler functions from
the final ELF rather than from a maintained list, verifies their actual call
edges and requires Z=0 at each return or tail entry into C. The final Link-66
receipt passed both the complete assembler ABI gate and the CRC-leaf
equivalence gate.

This is stronger local evidence that the rule matters, but it remains a
target ABI documentation request. It does not prove a compiler defect.

### Paste-ready text

**Title:** `Document the Z=0 ABI invariant for MEGA65/45GS02 inline assembly`

> llvm-mos-generated MEGA65 code relies on the 45GS02 Z register being zero
> at C function boundaries. Hand-written assembly using Q-register operations
> or explicit Z operations can leave Z nonzero; subsequent generated code may
> then fail far from the assembly site.
>
> Our local rule is now structural: every assembler-defined function called
> from C is derived from the linked ELF, every real call edge is inspected,
> and every return or tail entry into C must establish Z=0.
>
> Could the MOS target ABI / inline-assembly documentation state this
> invariant explicitly and include a minimal restore example such as
> `ldz #0` before returning to generated C?
>
> This is a documentation request, not a compiler-bug report.

**Filing state:** owner-paste-ready. The 2026-07-30 current ABI,
inline-assembly and issue search still omits the architectural Z-register
boundary invariant.

## L6 — DMA-list stores and the MMIO trigger

### Current local state

`src/mem.c::ext_dma` still contains the hardened shape that fixed the original
failure: populate the ordinary RAM list, then issue the `$d700` trigger in
register-free inline assembly with an `"a", "memory"` clobber. The comment and
implementation agree. The old shape used register operands and no memory
clobber; under LTO, list stores could move after the volatile MMIO trigger.

### Paste-ready text

**Title:** `Docs: show the compiler-barrier pattern for RAM descriptors followed by an MMIO trigger`

> A volatile store to an MMIO trigger orders that volatile access, but it
> does not by itself tell the optimizer that preceding ordinary-RAM stores
> populate a descriptor consumed by the device.
>
> With whole-program LTO, our stores to a 12-byte DMA list moved across the
> trigger store. DMAgic then observed a partially prepared list. The stable
> local pattern is:
>
> ```c
> /* populate dma_list[] first */
> __asm__ volatile(
>     "lda #mos16hi(dma_list)\n\t"
>     "sta $d701\n\t"
>     "lda #mos16lo(dma_list)\n\t"
>     "sta $d700\n\t"
>     ::: "a", "memory");
> ```
>
> Could the llvm-mos inline-assembly or platform documentation include an
> MMIO/DMA example that explains why the `"memory"` clobber is required?
> The exact registers are platform-specific; the compiler-ordering rule is
> general.

**Filing state:** owner-paste-ready after the 2026-07-30 documentation and
issue recheck. Do not claim that a volatile-only C expression is a compiler
defect.

## L7 — 16-bit C pointers versus 28-bit physical addresses

### Current local state

C2-lite contracts now treat physical addresses as their own domain:
`bank:u8 + offset:u16`, `uint32_t`, or explicit descriptor bytes. Runtime
addresses at or above `$00100000` never travel through `uintptr_t`. The G5
acceptance-tool saga independently demonstrated the consequence at a larger
scale: a normal F018B list carries only 20 address bits, so role 4's intended
`$08000000` Attic destination encoded as `$00000000` until the transport was
selected by address domain.

The compiler correctly warned about the earlier lossy conversion. This is not
a compiler bug.

### Paste-ready text

**Title:** `Docs: distinguish the C pointer domain from wider platform physical addresses`

> On the llvm-mos MEGA65 target, `uintptr_t` correctly represents the
> 16-bit C pointer domain. MEGA65 DMA/Attic endpoints are wider physical
> values. Passing a value such as `$00050000` or `$08000000` through
> `uintptr_t` truncates it; the compiler can warn, but the platform-domain
> distinction is easy to miss.
>
> Our product now carries physical endpoints as `uint32_t`,
> `bank:u8 + offset:u16`, or explicit DMA-list bytes, and reserves C pointer
> types for CPU-addressable C objects.
>
> Could the target documentation include one example that makes this
> distinction explicit? This is a documentation request. A 16-bit
> `uintptr_t` is correct for the target's C pointer model.

**Filing state:** owner-paste-ready after the 2026-07-30 documentation and
issue recheck; documentation only.

## L8 — `.llvm_sympart` and orphan handling

### Bound local observation

Pinned lld, invoked with `--emit-relocs`, `--lto-obj-path` and
`--orphan-handling=error`, produced a saved LTO object containing one
15-byte, non-ALLOC `SHT_LLVM_SYMPART` section:

1. An exact address-zero INFO output section with `KEEP(*(.llvm_sympart))`
   and assertions still produced the hard orphan diagnostic.
2. Naming `.llvm_sympart` in `/DISCARD/` still produced the same hard orphan
   diagnostic before a final ELF existed.
3. Changing only this diagnostic to an exactly matched warning allowed the
   final ELF to be produced. The compensating inventory then observed one
   15-byte, address-zero, non-ALLOC `.llvm_sympart`, zero runtime load bytes
   and 57 retained relocation sections.

Primary immutable receipts:

- `c2.2-link28-v2-profile-data-placement-orphan-first-red-receipt.json`,
  immutable-tree SHA-256
  `eb7d4de780aef1e285aa8078274b41ad44c4159196aa8d57caeac8f7871098ff`;
- `c2.2-link28-v2-profile-data-placement-discard-first-red-receipt.json`,
  immutable-tree SHA-256
  `4a438802879626ee323e3c13e96bf2f00c8c1ff9deeb4f436c2b04e8eb0d8d7d`;
- `c2.2-link28-v2-profile-data-placement-wrapper-inventory-order-first-red-receipt.json`,
  final ELF SHA-256
  `92b9eac60ba766a0ba30cee97ca34c07a28076e6e00800ca1c62a740f3acb339`
  and saved LTO object SHA-256
  `7fd609bbffdca8ec0dcab9d53494222bfb9fa7f8dbd052864ea7ae5edb536223`.

The archived minimal-evidence roots are:

- `tests/bytecode/dialect-v2/evidence/architecture-blocks/artifacts/c2-link28-v2-profile-data-placement-orphan-first-red-20260720/root`;
- `tests/bytecode/dialect-v2/evidence/architecture-blocks/artifacts/c2-link28-v2-profile-data-placement-discard-first-red-20260720/root`; and
- `tests/bytecode/dialect-v2/evidence/architecture-blocks/artifacts/c2-link28-v2-profile-data-placement-wrapper-inventory-order-first-red-20260720/root`.

### Draft for use after reduction

**Title:** `lld: --orphan-handling=error fires for .llvm_sympart before an explicit output or /DISCARD/ disposition`

> A whole-program LTO link using `--lto-obj-path`, `--emit-relocs` and
> `--orphan-handling=error` leaves a 15-byte non-ALLOC
> `SHT_LLVM_SYMPART` section in the saved LTO object.
>
> lld reports:
>
> ```text
> input.lto.o:(.llvm_sympart) is being placed in '.llvm_sympart'
> ```
>
> and aborts even when the script either:
>
> - defines an exact `.llvm_sympart` INFO output with `KEEP`; or
> - names `*(.llvm_sympart)` in `/DISCARD/`.
>
> Relaxing orphan handling to a warning produces a final ELF containing one
> 15-byte, address-zero, non-ALLOC `.llvm_sympart` with no runtime load
> bytes. This suggests that orphan classification for this LTO partition
> section occurs before the script disposition can satisfy the hard orphan
> policy.
>
> Is this ordering intentional for `SHT_LLVM_SYMPART`, or should an explicit
> output/discard command satisfy `--orphan-handling=error`?
>
> Attached: reduced source, both linker scripts, commands, saved LTO object,
> stderr and section inventory.

**Filing state:** not file-ready. First extract the archived objects/scripts
into a standalone, non-lisp65 reproduction and rerun it on current upstream
lld. If current lld does not reproduce, retain this only as pinned historical
behavior.

## L9 — wrong `DEW` operand under WPLTO

### Bound Link-32/Link-33 differential

The source shape in both links was:

```c
while (length--)
    crc = rtov_crc_byte(crc, *p++);
```

No source change was required to trigger the difference.

| Property | Link 32 | Link 33 |
|---|---|---|
| loop test | length shadow at `$7d/$7e` | length shadow at `$7d/$7e` |
| decrement | bytewise `DEC` form; no `DEW` | `DEW $16` |
| decremented object | tested length | `__rc20/__rc21`, not the tested length |
| runtime result | loop progresses | 1,156-byte CRC loop never reaches zero |

The wrong `DEW` is already present in the saved LTO object before the final
link: instruction offset `$14`, operand relocation offset `$15`, relocation
target `__rc20`. The Link-33 hardware First Red stopped before the first DMA
operation. Receipt:
`c2.2-product-link33-crc-loop-hardware-first-red-diagnosis.json`,
SHA-256
`7b644e0aaa8ffcbf48c2aaaec444f5dfa232ac27871f53813793d72c03d89e06`.

The shipped local replacement is a named 66-byte assembler function. Five
vectors, including lengths 1,156 and 4,097, were instruction-executed against
the C oracle, and the permanent codegen gate rejects `DEW` or an incomplete
two-byte decrement. This proves the workaround, not the upstream cause.

### Draft for use after reduction

**Title:** `WPLTO: 16-bit post-decrement emits DEW against the wrong zero-page object`

> With pinned llvm-mos
> `c798c31416f72b395c658b5502d281a162387ab1`, whole-program LTO compiled a
> CRC loop whose termination test reads a 16-bit length shadow at `$7d/$7e`
> but whose decrement is `DEW $16`.
>
> The saved LTO object already contains the bad instruction and relocates its
> operand to `__rc20`; this is present before final linking. A previous
> whole-program layout compiled the same source shape to a correct bytewise
> decrement. On hardware, the bad form loops forever because the tested
> length never changes.
>
> Source shape:
>
> ```c
> while (length--)
>     crc = crc_byte(crc, *p++);
> ```
>
> Attached: minimal sources, both WPLTO link commands/objects, disassembly,
> relocation dump and a host/simulator oracle.

**Filing state:** not file-ready. Reduce the Link-32/33 difference to a
standalone WPLTO case and reproduce on current llvm-mos HEAD. The present
claim is limited to pinned `c798c314…`; layout sensitivity is observed, not
yet explained.

## L10 — Attic Enhanced-DMA completion visibility

### Bound historical observation

The MEGA65 Chipset Reference and User Guide describe CPU execution as stopped
until a DMAgic job completes. In the bounded Link-34/35 diagnostic, an
Enhanced-DMA copy moved 1,156 bytes from Attic source `$08200200` to Bank-0
destination `$c356`.

Immediately after the job, two CPU CRC passes were both wrong and different:
`$8e92`, then `$e092`; expected source CRC was `$b47f`. A chained `$a5`
marker was then also shown not to be a completion witness.

A same-size two-byte hold patch stopped before verifier entry and wipe.
Three read-only captures of the destination gave:

| Time after launch command | CRC | Differing bytes |
|---:|---:|---:|
| 1 ms | `$e8d8` | 1,133 / 1,156 |
| 691 ms | `$e856` | 0 |
| 2,381 ms | `$e856` | 0 |

The immutable source remained byte-identical and the marker was already
`$a5`. Primary receipt:
`c2.2-link35-hold-before-wipe-cycle2-hardware-receipt.json`, SHA-256
`e8ac3f794d8d8030d15c84b9885c134833faad096420580e99a734d55d291fb6`.

### Core identity boundary

The Link-34/35 captures did **not** record their exact core revision. They
must not be retroactively labelled as a current-core result.

The subsequent C2-lite Chip-RAM hardware prefilter did bind machine
`TE0000B18447` to core register bytes `6b4cb203`, core `git-03b24c6b`. It
observed 12/12 immediate normal-F018A `$d700`
Chip-RAM transfers with zero delayed successes. This is useful campaign and
transport-class context, not proof that the earlier 691-ms run used that core
or that current mega65-core HEAD reproduces the defect.

### Current-core reproduction (v1.2.4 Phase M)

The bounded Phase-M rerun recorded core register bytes `6b4cb203`, the
project's registered `git-03b24c6b` core identity, before launching the same
1,156-byte Enhanced Attic-to-Bank-0 copy. The source CRC and expected target
CRC were `$e856`.

| Time after launch command | CRC | Differing bytes |
|---:|---:|---:|
| 2 ms | `$1490` | 1,132 / 1,156 |
| 714 ms | `$e856` | 0 |
| 2,414 ms | `$e856` | 0 |

This reproduces delayed CPU-visible convergence on the registered current
project core rather than merely corroborating the historical observation.
The bound hardware receipt is
`c2.2-v1.2.4-phase-m-hardware-receipt.json`, SHA-256
`b821f41a37426b97c701256f0b0abebf3e76196264210c756a697c639cadc724`.
The local product rule remains content-defined completion with a bounded
readback retry. This evidence strengthens an upstream discussion and request
for contract clarification; it does not establish the internal controller
mechanism or current upstream-HEAD behavior.

### G5 corroborating transport observations

The final acceptance-tool campaign added two narrower observations:

1. A private `$d705` Enhanced path did not provide a usable standalone
   write/readback result in the early cold-stager context.
2. Replacing all roles with normal `$d700` F018B proved that this rail carries
   only 20 address bits: intended Attic role 4 destination `$08000000`
   encoded as `$00000000`, leaving 64,144 target bytes different.
3. The final green tool therefore used normal `$d700` F018B for Chip-RAM
   roles 1–3 and Enhanced `$d705` F018B for Attic roles 4–8, with
   content-defined poison-once/readback retry and a bounded timeout.

These observations are committed acceptance-tool evidence at
`efbdef80ec20856e27fb6e606c84925e9735c615`. They corroborate the local rule
that Enhanced+Attic completion must be proved by target content. They do not
establish the same root cause as the Link-35 delayed visibility and do not
turn an acceptance-tool failure into a core defect claim.

### Paste-ready discussion text

**Title:** `DMAgic Enhanced Attic copy: CPU-visible target converged hundreds of milliseconds after trigger return`

> We observed two MEGA65 hardware runs in which an Enhanced-DMA copy from
> Attic memory to a 1,156-byte Bank-0 target was not yet stable when CPU code
> resumed.
>
> The historical run did not capture its exact core revision. Two immediate
> CPU CRC passes were different and wrong, and a chained one-byte fill marker
> was already visible. A hold-before-wipe diagnostic measured:
>
> | after launch | destination CRC | bytes differing |
> |---:|---:|---:|
> | 1 ms | `$e8d8` | 1,133 |
> | 691 ms | `$e856` | 0 |
> | 2,381 ms | `$e856` | 0 |
>
> We then repeated the same-size Enhanced Attic-to-Bank-0 transfer while
> recording the project's registered core identity `git-03b24c6b`:
>
> | after launch | destination CRC | bytes differing |
> |---:|---:|---:|
> | 2 ms | `$1490` | 1,132 |
> | 714 ms | `$e856` | 0 |
> | 2,414 ms | `$e856` | 0 |
>
> In both runs the Attic source was unchanged and no software write or mapping
> change occurred between captures. Our local product rule is therefore
> content-defined completion with a bounded target-CRC/readback retry;
> neither return from the trigger nor a chained marker is accepted as
> completion.
>
> Evidence limits: `git-03b24c6b` is the exact tested project core identity,
> not current upstream mega65-core HEAD, and this is not yet a standalone
> reduced reproducer. We are not claiming an internal controller mechanism.
> The current User Guide still says the CPU pauses until the DMA job is
> complete and that no additional wait logic is required.
>
> Does the documented CPU-stall guarantee include draining slow Attic reads
> into a CPU-visible target for Enhanced jobs, or is an additional completion
> contract required?

**Filing state:** text ready for an upstream discussion or documentation
question with the evidence limits intact. Submission is presently blocked:
the 2026-07-30 API recheck reports that Discussions are disabled for
`MEGA65/mega65-core`, and the owner explicitly forbade filing L10 as an Issue.
Do not improvise another target.

**Surface resolution (reviewer, 2026-07-31):** the API recheck confirms
`MEGA65/mega65-core` Discussions remain disabled while
`MEGA65/mega65-user-guide` accepts Issues. The quoted stall guarantee is
User-Guide text, so a **documentation-question Issue on
`MEGA65/mega65-user-guide`** is the second form this filing state already
permits, at its natural home — authorized as L10's submission surface.
Title and body unchanged; attach the two bound curve receipts
(`c2.2-link35-hold-before-wipe-cycle2-hardware-receipt.json` and
`c2.2-v1.2.4-phase-m-hardware-receipt.json`) as issue attachments. Attach both bound curve receipts and
source/job bytes once the approved discussion surface exists; describe the
G5 rail observations only as corroborating local context.

## L11 — Audio-DMA interrupt documentation contradicts tested-core RTL

### Bound current observation

The current MEGA65 User Guide source at
`0210345cd9cf19629010277732280e9e7248771e` still says:
“The audio DMA subsystem cannot presently generate interrupts.” The exact
hardware-accepted core `03b24c6b9d0e456f762fdca0d2dd66ec3c3e1fc6`
implements the opposite:

- [`gs4510.vhdl` lines 4533–4549](https://github.com/MEGA65/mega65-core/blob/03b24c6b9d0e456f762fdca0d2dd66ec3c3e1fc6/src/vhdl/gs4510.vhdl#L4533-L4549)
  gate each of four channel events with `audio_dma_irqenb(i)`, set the
  corresponding flag and clear its one-shot enable; and
- [lines 4551–4553](https://github.com/MEGA65/mega65-core/blob/03b24c6b9d0e456f762fdca0d2dd66ec3c3e1fc6/src/vhdl/gs4510.vhdl#L4551-L4553)
  set both `irq_internal` and CPU `irq_pending`.

The final upstream recheck found the same behavior at current mega65-core
HEAD `a9158930665763c592d004c895d52eff4a9eefc3`: the enable/event logic is at
lines 4552–4567 and asserts `irq_internal`/`irq_pending` at lines 4570–4573.
Closed issue #811 records that the IRQ feature was implemented, tested and
merged into `development` in 2024; the prose simply did not follow it.

This is a documentation-class finding. lisp65 now clears the four flags and
four enables at `$D713` before it enables its owned raster IRQ. Product use of
Audio-DMA is not required for the policy: firmware or the hypervisor can leave
an enable armed before ownership.

### Paste-ready text

**Title:** `Docs: Audio-DMA can assert CPU irq_pending in current core`

> The current User Guide source
> (`0210345cd9cf19629010277732280e9e7248771e`) says that the Audio-DMA
> subsystem cannot generate interrupts. In exact tested core
> `03b24c6b9d0e456f762fdca0d2dd66ec3c3e1fc6`, the GS4510 implementation
> gates each channel event with `audio_dma_irqenb(i)`, sets its interrupt
> flag, and then sets `irq_internal` and CPU `irq_pending`
> (`src/vhdl/gs4510.vhdl`, lines 4533–4553).
>
> Current `development` HEAD
> `a9158930665763c592d004c895d52eff4a9eefc3` retains the same route at
> lines 4552–4573. Closed issue #811 records that Audio-DMA IRQ support was
> implemented, tested and merged in 2024, so this appears to be stale
> documentation rather than unexpected core behavior.
>
> Could the Audio-DMA section and `$D713` register description be updated to
> describe the four enable/flag pairs and their CPU interrupt route? Our
> software now clears `$D713` during interrupt ownership because inherited
> firmware or hypervisor state may otherwise leave a channel interrupt armed.
>
> This is a documentation correction against a named core revision, not a
> claim that the core behavior is defective.

**Filing state:** owner-paste-ready. The 2026-07-30 current Core/Guide and
issue recheck confirms the implementation/text mismatch and finds no
documentation-correction report. Mention closed issue #811 as implementation
history, not as the requested documentation fix.

## Owner filing checklist

Final recheck is complete for L4–L7 and L11. Before any paste:

1. if filing after 2026-07-30, repeat the current upstream
   issues/discussions and documentation search;
2. name the exact compiler/core/docs revision being discussed;
3. attach only standalone files required to reproduce;
4. keep L4–L7 in documentation/proposal language;
5. do not file L8/L9 until their current-upstream reductions fail;
6. do not attribute the historical L10 curve to `git-03b24c6b`;
7. keep L1 closed unless a larger failing reproduction is recovered; and
8. keep L3 parked until the planned S2 hardware smoke records its result; and
9. use the revisions bound at the top of this packet; and
10. do not file L10 until the owner-approved discussion surface exists.

Nothing in this packet authorizes Codex to file upstream.
