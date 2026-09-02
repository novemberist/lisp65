# Upstream verification round — 2026-07-19

This report is a filing gate, not a product claim. It records which historical
lisp65 findings still have enough current evidence to take upstream and which
ones must remain local until a fresh hardware reproduction exists.

## 2026-07-27 local-evidence refresh

The upstream revisions checked in this report have not been silently advanced.
Phase U instead refreshed the local evidence and produced
[`upstream-owner-bundle-2026-07-27.md`](upstream-owner-bundle-2026-07-27.md).
It:

- retains the L1 not-reproduced verdict and filing bar;
- confirms that L4–L7 still match the current lisp65 implementation;
- binds the archived L8 output-section and `/DISCARD/` failures;
- records the exact Link-32/33 L9 instruction/relocation differential; and
- adds the L10 691-ms curve, the later `git-03b24c6b` campaign context and the
  G5 normal-versus-Enhanced rail observations without retroactively assigning
  a core ID to the historical measurement.

Current-upstream re-verification remains mandatory immediately before filing.

## Pinned upstream state

| Project | Revision checked | Verification mode |
|---|---|---|
| llvm-mos | `8be0546128a55e78c63ca571d466aa72a782cd36` | current AUR compiler in the `arch` distrobox; source checkout |
| llvm-mos-sdk | `d0b137e5fd443fda1f70bf98ecd739cc131e18f9` | source checkout; local executable tests use the repository's pinned SDK link closure |
| mega65-core | `a9158930665763c592d004c895d52eff4a9eefc3` | source checkout only |
| Xemu | `40dfef0d1d5f56be2469492715c12bdb32c75b67` | source checkout only |
| MEGA65 User Guide | `2d0c444a7f086fcc6c4aed9bbaf5ccc17a19ef60` | source/document checkout |

The accepted lisp65 hardware receipts were recorded on core
`git-03b24c6b` (`03b24c6b9d0e456f762fdca0d2dd66ec3c3e1fc6`), not on the
current core revision above. Source continuity is useful evidence but is not a
substitute for a current-core hardware run.

## Filing disposition

| Finding | Result | Filing disposition |
|---|---|---|
| L1 variable shift | **not reproduced** | hold; do not file as a compiler bug |
| L2 mark-stack freeze | historical hardware repro, cause unknown | hold until current-toolchain hardware rerun |
| L3 KERNAL scroll | current 294-byte candidate built; not rerun on hardware | one hardware smoke required before filing |
| L4 custom sections | current documentation/ergonomics proposal | may file as a docs/feature request |
| L5 45GS02 Z invariant | absent from current inline-asm page | may propose a target-specific documentation note |
| L6 DMA/MMIO barrier | no target-specific pattern found in current docs | may propose a documentation example |
| L7 28-bit physical address vs. `uintptr_t` | no explicit MEGA65-domain warning found | documentation suggestion only; not a compiler bug |
| C1 Freezer/BUFSEL | historical hardware proof; current source remains consistent with the mechanism | comment on existing core issue #674; offer current-core retest |
| C2 mount lock | still a valid feature proposal | sound out upstream before filing |
| C3 flat access | historical hardware proof only | current-core hardware rerun required |
| C6 virtual D81 write protect | current core source still enables attached-image writes | feature request remains current |
| X1 F011 timing | current source still labels behavior incomplete/immediate | issue is current, but attach a standalone differential repro |
| X2 SD/F011 buffer mapping | current source explicitly keeps an SD-only workaround | issue is current |
| X3 Freezer | current source says Freezer is not enabled | issue is current |

## llvm-mos details

### L1 — negative result

`tools/upstream-repros/variable_shift_mask.c` contains both the reduced
`1u << (i & 7)` expression and the original bitmap-update shape. It exits zero
under both:

- pinned compiler `c798c31416f72b395c658b5502d281a162387ab1`;
- current compiler `8be0546128a55e78c63ca571d466aa72a782cd36`.

Both simulator runs completed in 3,162 cycles with every expected mask and
cumulative bitmap value correct. The historical GC failure was real, but this
round cannot isolate it to the claimed shift expression. L1 is therefore
reclassified from “verified compiler bug” to “historical workaround; reduced
claim not reproduced”. Reconstructing a larger historical GC context is
allowed, but filing the present claim is not.

### L3 — ready for one hardware smoke, not for filing

`tools/upstream-repros/mega65_kernal_scroll.c` builds with current llvm-mos to
a 294-byte PRG:

```text
sha256 d439a7bb775ed160af6fc8274ed8a8a24bc783b8326f8c9afeb106fc12f8ab2f
```

Build command:

```sh
/opt/llvm-mos/bin/mos-clang \
  --config "$PWD/tools/llvm-mos/bin/mos-mega65.cfg" -Os \
  tools/upstream-repros/mega65_kernal_scroll.c \
  -o build/upstream-verification/mega65-kernal-scroll-head.prg
```

The program clears the screen, emits 32 numbered lines through KERNAL CHROUT,
then prints `OK`. It becomes an issue attachment only after a fresh run records
the actual screen/terminal behavior and current hardware core identity.

### L5, L6 and L7 — documentation scope

The current official C Inline Assembly page documents GCC constraints and says
the compiler tracks C/V but not N/Z. It does not state the MEGA65/45GS02 rule
that Q-register inline assembly must restore Z to zero. The checked pages also
do not provide a target-specific DMA-list/MMIO-trigger barrier example or an
explicit warning that a 28-bit MEGA65 physical endpoint is not a C pointer in
the 16-bit target address model.

These are documentation proposals. In particular, L7 must never be phrased as
a compiler defect: llvm-mos warned about the lossy conversion, and a 16-bit
`uintptr_t` is correct for its C pointer domain.

## mega65-core details

### C1 — current source supports the historical diagnosis

On current source, `src/hyppo/dos.asm` still sets `$D689.7` for the direct SD
buffer. `src/hyppo/freeze.asm` snapshots and restores `$D680..$D70F`, including
`$D689`, around Freezer work. The historical hardware run showed that the value
captured/restored across the user-visible swap can be `$80`; lisp65 consequently
had to establish `$D689=$00` at every F011 transaction.

Core issue [#674](https://github.com/MEGA65/mega65-core/issues/674), “A 1581
does not work anymore once the freezer was accessed”, remains open and is a
plausible symptom of this root cause. The preferred first contact is a concise
root-cause comment on #674, explicitly separating:

- hardware reproduction on core `03b24c6b…`;
- source re-verification on core `a915893…`;
- an offer to rerun a candidate/current core on real hardware.

Issue [#729](https://github.com/MEGA65/mega65-core/issues/729) remains related
context for mount lifetime, not a duplicate of the BUFSEL mechanism.

### C3 — source intent is not current hardware evidence

Current `gs4510.vhdl` still contains the flat-32 address path and explicit
Colour RAM routing at `$FF80000`. That confirms the documented intent, but it
does not decide whether current hardware matches it. C3 stays blocked on the
existing `hw-access-smoke` being rerun after installing a current core.

## Xemu details

The typed event queue is now present in `targets/mega65/input_devices.c`,
including `$D60A` modifier/queue state, `$D619` PETSCII and dequeue/flush
semantics. The old keyboard-queue gap is closed and should be acknowledged in
any Xemu contact.

Three gaps remain explicit in current source:

- `hypervisor.c` reports `FREEZER is not enabled in Xemu currently`, while
  `configdb.c` labels the switch `NOT YET WORKING`;
- `sdcard.c` says the F011 buffer is not integrated into its 4 KiB buffer model;
- the same file fixes the I/O-mapped window to the SD buffer and describes the
  attempted combined SD/F011 mapping as reverted.

X2 and X3 are therefore source-confirmed current gaps. X1 also remains
credible, but its eventual issue should carry a small observable F011 timing or
status differential rather than a general statement about emulator fidelity.

## Owner handoff

No issue was filed by this round. The immediately useful owner actions are:

1. comment on mega65-core #674 with the C1 root-cause analysis;
2. run the 294-byte L3 PRG once on hardware before filing the llvm-mos issue;
3. decide whether X2/X3 should be one focused Xemu issue or two;
4. sound out the mount-lock proposal before turning C2 into a formal request.

L1 and C3 remain blocked exactly as described above; neither should be filed
from historical inference alone.
