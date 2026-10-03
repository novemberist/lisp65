# 2.5.3 — device session

2026-10-03. Reviewer-run session with the owner at the device, in two rounds. Driver
`build/device-253-prep/tools/d253.py` on `session253.py` (runbook `build/device-253-prep/runbook.txt`,
row table `build/device-253-prep/rows-253.json`); receipts under `build/device-253-prep/`. All clocks
named below are the host tool clock (monitor polls), not a stopwatch, unless marked as the owner's.

## Result: PASS, with one unexplained display failure after a Freezer disk swap

- **Medium:** 2.5.3 Final r8, medium `build/card-253-final-r8/media-253/c253.d81` (819,200 bytes, SHA-256
  `7df9db67f16c7218e56c9e4b64dfc0ed512c43771c9c39d9ccd56ddc76e55c2f`), ELF
  `build/card-253-final-r8/wplto/resident-island-seed.prg.elf` (664,176 bytes, SHA-256
  `5eb056e03158578bb51edacbb9bd3064ea97a88b8d7613c1d0c052ae6a63d293`). Every receipt below binds both.
- **All 49 executed groups of phases A, U, O, L and F passed** across the two rounds (33 + 12 + 1 + 1 + 2;
  the 50th table group, `d4-swap-refused` of phase O, was replaced, see "Table adaptations"). The exploratory DMA row (phase X) was
  aborted at its precondition and is not an acceptance row; the optional destructive row (phase Z) ran.
- **Owner physical rows** (`owner-observations.txt`): rows 1, 2, 3, 4 and 6 PASS ("Alle Tests waren positiv
  und das Tippgefühl gut"); row 5 PASS with the observation below; row 7 stopwatch measured.
- **Failure that is not explained:** after a Freezer disk swap at the end of round 1 the display went black (see
  "Black screen after a Freezer swap"). Disks were intact afterwards.

## Round 1 (SD names `D253*.D81`)

| Step | Receipt | SHA-256 | Result |
|---|---|---|---|
| Upload of five disks, read back | `build/device-253-prep/upload-01/receipt.json` | `c24703bc1fcf317b6949e896f72daf5554e02cc6ca82097bd4c4dee2a8e2dd16` | PASS; all five SD files are new names, read back byte-identical (product readback = Final D81 `7df9db67…`) |
| Boot | `build/device-253-prep/boot-01/receipt.json` | `f93e3d18c8a66a6bf01aa707f68cbe0a3253502567511b1bc83b30de6808f10d` | PASS; 21.2 s to Initializing, 42.7 s to the first empty `l65>` |
| Phase A, first part | `build/device-253-prep/rows-01/receipt.json` | `6b70aa7be82e950f1ad875c1413e6e96c73c4510d1ea5e9160bccce64ca99d47` | 26 groups PASS, then a driver HALT at `lcc-f2-ladder` (table, not product: see below) |
| Phase A, rest | `build/device-253-prep/rows-02/receipt.json` | `03ede8858d451b521953b4c36c685a0b42dde294012b09d7462a1d5c4bc8dc58` | 7 groups PASS: `lcc-f2-ladder`, `ide-dirty-eval`, `ide-mark-cleared-by-edit`, `input-limit-641`, `history-limit`, `return-249`, `oom-recovery-local` |
| Phase U (`D253U.D81` via the Freezer) | `build/device-253-prep/disk-u-01/receipt.json` | `d4882c1fab9c2b7579c586d57157f3eb0d217d23be5c2769fb3bb95820bfdff1` | 12 of 12 groups PASS |
| Readback after the power cycle | `build/device-253-prep/readback-01/receipt.json` | `2d9fe70ab3c47d715cc152b35aa3950f597673458895ff4fb28fc0b8ea451752` | PASS; user disk consistent (22 files, no cross-link, no unowned block, `PHYS50` = `x` + source); other, leak and full disks byte-identical to the prepared images |

Phase A covers the inherited 2.5.2 groups (reopening the previous line, multi-line strings, Backspace rows,
IDE load / `C-x q` / re-entry, virtual RUN/STOP, library loading), the new compiler rows (multi-pair `setq`,
odd `setq`, `(car 1 2)`, compiled builtin arity, `nth` on a dotted list, macro use, the nesting ladder), the
`eval-buffer` dirty-cache and mark rows, the 641-byte input limit, the history limit, the 249-character
Return and the out-of-memory recovery of a `let`-local (`*** VM: OUT OF MEMORY` once, then `(+ 1 2)` gave 3
and `(length (list 1 2 3))` gave 3). Phase U on a real disk: remount `0`, IDE saves of 20x40 and 50x40
buffers by command and by editor keys with a byte-identical reload on the host, a typed-and-saved buffer,
buffer switches (one and two buffers), `eval-buffer` of 5 and 50 forms (`(5 DONE NIL)`, `(50 DONE NIL)`), the
lossless load (D3) and the write enable after a verified remount (D2: an aborted save gives status 8, a
remount clears it, then a save returns 0).

Tool-clock figures from phase U (upper bounds, not guarantees): remount of a 9-file disk 35.7 s (36 to 41 s
in later rows); `save-buffer-to` of a 20x40 buffer 37.7 s and of a 50x40 buffer 92.1 s; editor-key save
(`C-x C-w`) 37.2 s and 91.7 s; `eval-buffer` of 5 forms 24.9 s and of 50 forms 217 s.

## Round 2 (power cycle, fresh upload with suffix `A`, names `D253A*.D81`)

| Step | Receipt | SHA-256 | Result |
|---|---|---|---|
| Upload of five disks, read back | `build/device-253-prep/upload-02/receipt.json` | `aa501fccd66e7c647b6f026bae397bb45cf8941a9e6149baff128b9fbcc92751` | PASS; new names, byte-identical readback |
| Boot | `build/device-253-prep/boot-02/receipt.json` | `50f68c38cf6dc6215f9a008f508576d5b037df2a5de350e685348edb889b9d79` | PASS; 21.1 s to Initializing, 42.8 s to the first empty `l65>` |
| Phase O, first attempt | `build/device-253-prep/disk-o-01/receipt.json` | `66a075593e3d6008788e4341a6873e9a7f77c735f9aca6fee1ab962a895960f4` | HALT (fresh-session save returned 8, see below); no write happened |
| Phase O, second attempt | `build/device-253-prep/disk-o-02/receipt.json` | `e805630c79f48beca63d3dc81824c4b7204e220a6649f3496e6b3a39f6a201b1` | PASS: remount of `D253AO.D81` returned 0 after 31.7 s |
| Phase F (`D253AF.D81`, 144 files) | `build/device-253-prep/disk-f-01/receipt.json` | `dde237a4bfc08f8449b891cb9e76330b06a892dcc8dda041468ab820644903ab` | 2 of 2 groups PASS: swap to the other disk gave status 12, then 8; full-directory remount 0 (49 s), replace of `F000` 0, `(length (dir))` 144 |
| Phase L (`D253AL.D81`, leaked block) | `build/device-253-prep/disk-l-01/receipt.json` | `2f7215441daaa176356962071bd8cd980b4daf3e7329669fbaafec7847fb7546` | PASS: `(13 8 13)`, status 13, reads still work (`(length (dir))` 2), a save is refused (`disk allocation inconsistent…`) |
| Exploratory DMA row (phase X) | `build/device-253-prep/dma-01/receipt.json` | `dd57fadf236b478a2a48c5003f86422bf67226332d826221682fa3662772e31a` | aborted at the precondition, no DMA write (see below); not an acceptance row |
| Optional destructive row (phase Z) | `build/device-253-prep/oom-last-01/receipt.json` | `bd4af3498307ffd333e18fb54ab897327f44ae4fd7def93460360f0480343b44` | PASS (see below); session ended, power cycle |
| Readback after the power cycle | `build/device-253-prep/readback-02/receipt.json` | `6ab35e6d037aaa8b0a7ef31dd5f616bbaf6f8582aef5879028895b57f2f95088` | PASS; user disk untouched in this round, other and leak byte-identical to the prepared images, full disk `F000` replaced with 143 siblings intact |

Owner observations and the row table used: `build/device-253-prep/owner-observations.txt`
(`e8eacff3280d96b8a9e9eda2bae963e98c6d6bc10264bf2e30a6e2a1403a1079`) and
`build/device-253-prep/rows-253.json` (`c6deef519b1aaa32571b29f7d4977626b144fb16f4ac97dab5079a0f59ab0830`,
with `device_note` fields on the three adapted groups). The tables in force when each driver halted are
retained as `rows-01-halt-table-copy.json` (`71f4f0f889ea8dd189c193dc1bc659b45a7521c2f1f40dbe556b7b60581295c2`)
and `rows-diskO-halt-table-copy.json` (`440d9f98212d083d10a35a4440f56462122ee0e31aa170e065bab985654ae29e`).

## Owner physical rows

- **Rows 1 to 4 and 6 (PASS):** typing and Backspace (the owner called the feel good), reopening the previous
  line, the two-line string example, physical `C-x q` in the IDE, physical RUN/STOP. Recorded 2026-10-03T10:28Z.
- **Row 5, physical `C-x C-s` on a 50x40 buffer (`PHYS50`, `D253U.D81` mounted): PASS.** The minibuffer showed
  SAVED and the host readback shows `PHYS50` = `x` + source (`readback-01`). **Observation: the save took
  several minutes.** The driver's own editor-key save of the same buffer size took 91.7 s on the tool clock;
  the physical save was clearly slower and was not timed by stopwatch. The cause of the difference is not
  established.
- **Row 7, stopwatch boot:** from Return on `run` about 20 s to `Initializing`, then about 23 s to the REPL
  (`l65>`), together about 43 s (the owner corrected an earlier note of 13 s and 33 s). The tool clock of the
  same session (`boot-02`) gave 21.1 s to Initializing and 42.8 s to the first empty `l65>`; 2.5.2 measured
  40.9 s on the tool clock. The emulator boot cost rose 4.2 to 4.4 % in cycles, which is consistent with about
  two seconds more.

## Black screen after a Freezer swap (not explained)

At the end of round 1, after the owner row 5, the owner mounted `D253O.D81` through the Freezer (the Freezer
list showed the name as `D2530.D81`) and pressed F3 to return. The screen went **black immediately** and
re-opening the Freezer hung; the session was ended and the machine power-cycled. Phases A and U were complete
before this. The host readback afterwards (`readback-01`) proved that **no disk was damaged**: the product
disk and the three untouched disks were byte-identical to what was uploaded, and the user disk was consistent.
In round 2 the owner swapped disks through the Freezer three more times (to `D253AO`, `D253AF` and `D253AL`)
without a repeat. **The cause is not known**: it may be the
Freezer, the core, the mount order, the state of the machine after the long save or the product. It was not
reproduced and no log exists. Treat it as an open observation.

## Table adaptations (documented in `rows-253.json`, not product defects)

1. **`lcc-f2-ladder`: peek forms removed.** Four forms read the scratch gap `$17A0..` with `peek` to prove
   the compile depth. On the device that gap is **not zero**: the first form returned 22 and compiled without
   `*** VM: STACK OVERFLOW`, so the row table's expected value 0 (valid in the emulator) was wrong. The driver
   halted in `rows-01` (error text: result differs, 0 against 22). The four peek forms were removed for the
   device run; the peek-free twin (`161`) and the two nesting-ladder points (9 and `*** VM: STACK OVERFLOW`,
   6 and `*** VM: STACK OVERFLOW`, each followed by `(+ 1 2)` giving 3) prove the compile depth and passed in
   `rows-02`.
2. **Phase O re-ordered after the fresh session.** After the power cycle the O phase ran first in a fresh
   session. `(m65d-save "swap" "x")` returned 8 instead of the expected 12 (driver halt `disk-o-01`, before any
   write): writing is not enabled without a verified remount, which is correct D2 behaviour. The swap test
   was re-ordered: remount the O disk (`disk-o-02`, 0), then swap to the F disk, where the save gave status 12
   and the next save status 8 (`disk-f-01`). The original group `d4-swap-refused` of phase O therefore never
   ran as written; it is replaced by `o-remount-enable` and by `f-swap-refused`. The merged device rows record
   the replaced group as not executed and do not count it as passed.

## Exploratory DMA row (for 2.6, not an acceptance row)

The row's precondition checks that the scratch gap `$17A0..$17FF` is empty before any DMA write. On the device
the check returned **255 instead of 0** (the first session had already seen `$17A0` = 22). The row aborted
before the first DMA poke; only the helper functions were defined and read. **Finding for 2.6: the gap is not
free on the device**, so another, device-verified DMA scratch area is needed. DMA line mode was not tested on
hardware.

## Heap held by data (`oom-last`)

The optional destructive row filled the heap with a global list: `*** VM: OUT OF MEMORY` appeared and the
prompt returned. The receipt records no further drop attempt; the session was ended as the runbook demands.
The documented limit stands: a heap filled by data the program still holds cannot be released from the
keyboard (typing the freeing form needs memory), so a reset is required. The power cycle and a fresh upload
followed (`readback-02`). The recovery of garbage in a `let`-local (phase A, `oom-recovery-local`) passed.

## Not verified

- The cause of the black screen after a Freezer swap (one occurrence, three later swaps without it).
- `ide-save-cow-controls` (write-fault injection; no fault-injection seam exists).
- DMA line mode and any DMA scratch area on the device (2.6).
- Physical editor-key `C-x C-s` timing for large buffers (several minutes, once, unmeasured).
- Stopwatch timing of single rows other than the boot; physical `C-x C-c` remains unavailable.
- The four partial emulator GC-stress scenarios and the editor-key path of the 100x20 save on r8 stay as
  described in the [2.5.3 release notes](../releases/2.5.3.md).
