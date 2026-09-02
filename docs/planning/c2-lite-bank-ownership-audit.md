# C2-lite Bank 2/3 ownership audit

Status: **structurally green; hardware outcome recorded separately**

Date: 2026-07-21

Scope: read-only memory-map, MAP, reset and Freezer audit for the C2-lite
Option-A prerequisite. This audit authorizes no product source change, product
link, capacity debit, promotion or product claim. Bank 1 remains outside the
selected design and retains the user/graphics promise.

## Verdict

Both ROM-taboo Chip-RAM banks are structurally available as **session-transient,
reconstructible C2-lite caches** after the product has taken KERNAL ownership:

| Physical bank | Proposed sole tenant | Active bytes | Headroom | Verdict before metal |
|---|---|---:|---:|---|
| Bank 2, `$020000-$02ffff` | normalized static and session bytecode plane | 34,403 | 31,133 | conditionally usable |
| Bank 3, `$030000-$03ffff` | lifetime-exclusive Boot/Session L65R native plane | 60,062 session maximum | 5,474 | conditionally usable |
| Bank 1, `$010000-$01ffff` | user/graphics promise | 0 C2-lite | 65,536 | **untouched** |

The condition remains material: the standalone seven-part hardware pre-smoke
must prove immediate Chip-RAM DMA completion, write enablement, Freezer
survival and the Boot-to-Session generation handoff on the device. Its outcome
is a separate evidence layer in
`docs/planning/c2-lite-chipram-hardware-prefilter-result.md`; this source audit
does not absorb or circularly bind its own hardware result. Either bank failing
or any delayed convergence makes Option A red and does not authorize Bank 1.

## Bound evidence

1. The pinned MEGA65 chipset reference, SHA-256
   `107610ae3ea9f7e3f1e78915dcbe2cae1a6f404ca2e538762524a7e58cced220`,
   identifies Bank 2 and Bank 3 as the two halves of the C65 ROM **or RAM**
   (PDF page 18, printed page 4). It states that all or part of the complete
   128 KiB ROM space can be used as RAM after Hypervisor write protection is
   removed, and that the built-in Freezer covers the first 384 KiB, including
   those banks (PDF page 19, printed page 5).
2. The same reference specifies the ROM write-enable mechanism and states that
   MAP or DMA can address the backing RAM directly (PDF page 24, printed page
   10). The official DMA description says that the processor stops executing
   until an ordinary DMA job completes (PDF page 84, printed page 70). L10 has
   disproved relying on that statement for Attic/HyperRAM; the metal proof must
   therefore establish it independently for Chip-RAM sources.
3. Current upstream core source at
   `a9158930665763c592d004c895d52eff4a9eefc3` confirms that `$020000-$03ffff`
   is Chip RAM, with write protection applied to exactly that 128 KiB range
   (`src/vhdl/gs4510.vhdl`, read decode 2222-2235 and write gate 3638-3649).
   The idempotent memory trap disables protection with `$D641`, A=`$02`
   (`src/hyppo/mem.asm`, 120-128); the toggle trap is deliberately not used.
4. Current upstream Freezer source saves one contiguous six-bank region from
   `$000000`, explicitly described as “384KB RAM (includes the 128KB ROM
   area)” (`src/hyppo/freeze.asm`, 1145-1149). This is structural source
   evidence, not a pass for the device core; the pre-smoke must still perform
   and verify a real Freezer roundtrip.
5. The project’s 2026-07-10 hardware matrix on core `git-03b24c6b` measured
   that reset restages the 128 KiB C65 ROM over `$020000-$03ffff` and also
   overwrites Bank 1. Current Hypervisor source independently shows reset
   clearing the ROM-protect state, loading a 128-KiB `MEGA65.ROM` at `$020000`,
   and re-enabling protection before transfer to the ROM reset vector
   (`src/hyppo/main.asm`, 434-456, 1320-1334, 1441-1443, 2113-2118).
6. The current product takes KERNAL/window ownership before any C2 boot
   decoder or runtime-overlay installation (`src/main.c`, 108-173), and maps
   only Bank-0 block 7 into `$e000-$ffff` while retaining the `$d000` I/O
   aperture (`src/c2_kernal_map.s`, 13-34). The existing KERNAL-freedom gates
   therefore provide the required cut: after ownership, no product path may
   consume the C65 ROM bytes that C2-lite replaces.

The upstream checkout is a source audit at its current pinned commit, not a
claim that the hardware runs that commit. The pre-smoke receipt must record the
device’s exact core identity. Xemu remains non-authoritative.

## Ownership and lifetime rules

1. **Acquire late.** Banks 2/3 may be unlocked and overwritten only after the
   product has completed the firmware-to-owned-runtime handoff. No boot path
   that can return to C65 ROM may run afterward.
2. **One tenant per live bank.** Bank 2 is the bytecode code plane. Bank 3 is
   the native plane; Boot and Session families share it only through the
   already-proved lifetime exclusion. Bank 1 is not a C2-lite fallback.
3. **Caches only.** Neither bank is an authoritative or sole copy. Immutable
   shelf/session sources remain on medium or in Attic under their existing
   identity and COW rules.
4. **Reset destroys authority.** A platform reset exits the product and
   replaces Banks 2/3 with ROM. All code/native watermarks, handles and native
   family bindings are invalid before any subsequent restage. No warm-reset
   fast path may consume these banks.
5. **Freezer preserves bytes, not assumptions.** Freeze/thaw must return both
   banks byte-identical, preserve the active generation, preserve immediate
   bank-to-window DMA, and leave the ROM region writable for later session
   appends. If write protection is changed in the Freezer, the product must
   re-establish and verify write access before the next append; it may never
   infer writeability from the pre-Freezer state.
6. **Physical addressing remains non-pointer.** Bank 2/3 addresses travel as
   bank plus u16 offset or explicit DMA fields. They never pass through the
   platform’s 16-bit C pointer type.

## Reset and Freezer matrix

| Event | Bank 2 code plane | Bank 3 native plane | Required product state |
|---|---|---|---|
| initial post-ownership staging | populated and destination-verified | Boot family populated and verified | not READY until both bindings publish |
| Boot-to-Session handoff | unchanged | Boot generation invalidated, Session family replaces it | publication last; no Boot handle callable |
| session append | append within low watermark | unchanged | write access verified; rollback restores watermark |
| Freezer entry/return | must be byte-identical | must be byte-identical | generation and immediate DMA still valid; frame source resumes |
| platform reset | overwritten by ROM; never trusted | overwritten by ROM; never trusted | product exited; all bindings invalid before restage |
| power cycle | no survival claim | no survival claim | disk/mount cold boot only |

## Metal-proof gate

The audit advances to hardware only if one non-product proof target implements
the memo’s seven cases without retry or delayed-convergence logic:

1. identity-bound source patterns in **both** banks;
2. poisoned Bank-0 destinations and the production F018A DMA trigger shape;
3. immediate CPU consumption after the trigger routine returns;
4. lengths 1, 7, 16, 127 and 128 plus 1,761-byte Session-slice and 1,781-byte
   Island-shaped transfers;
5. owned IRQ/frame source active and one Freezer roundtrip, with complete bank
   identities and post-return writeability checked;
6. Boot-to-Session replacement of Bank 3 and rejection of the old generation;
7. exact device core identity and per-case frame/latency observations.

Acceptance is exact bytes plus CRC on the first post-return observation. A
second observation is diagnostic only and cannot turn a first mismatch green.
No retry loop is permitted. A red result selects the already documented
Option-B fallback for a new Class-C decision; it does not authorize Bank 1.
