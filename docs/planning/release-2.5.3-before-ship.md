# 2.5.3 — Before-Ship

**Preparation r8, 2026-10-03, after the device session (private HEAD `df495f39` plus the documentation
commit that follows this text).** The device session on a physical MEGA65 **passed** and the owner has
given the word for Ship and Publish of 2.5.3 (plan journal, "2.5.3 device session passed; owner word for
Ship and Publish — 2026-10-03"). What is still open and not claimed: the new sealed `check-host` run on the
documentation commit (**PENDING**), the reviewed release contract and the post-commit seal, and the
publication itself. The preparation made no device or network contact and no Git write; the reviewer first
commits the documents and records, runs the sealed host run, fills the contract, commits it, and then runs
the post-commit sealing script `build/release-v2.5.3/seal-after-commit-r8.py --final`.

## Sealed full host run: r8a green on `df495f39`, r8b PENDING on the release commit

Target: `make -k check-host`, sealed run (read-only mounts, isolated generated tree).

| Run | HEAD | Exit | Seconds | Receipt SHA-256 | Result |
|---|---|---:|---:|---|---|
| r8a `build/release-v2.5.3-check-host-r8a` | `df495f3935c148de38e05cb4968623ba47f44e69` | 0 | 4,078.8 | `40847ffcaed58f51c534c392d4a9c8388fe6d8b9770dc8f3b54163446c85a7bb` | green: no changed file, 0 changed protected files, no changed sealed artifact; 24,888 protected files, 55,340 read-only sealed artifacts; log `build/release-v2.5.3-check-host-r8a/check-source.log` SHA-256 `de4855871253746e40c8d4b617c6e34544a442f1730a4bb29ebc9235c2096431` |
| r8b `build/release-v2.5.3-check-host-r8b` | the documentation commit | **PENDING** | **PENDING** | **PENDING** (receipt path `build/release-v2.5.3-check-host-r8b/receipt.json`) | **PENDING** |

The earlier sealed runs r1, r2 and r3 belong to the withdrawn Final r7 and are history only (never bound).
r8a ran before the device session and before the documents below changed; it is not bound in the release
contract. After the device session the documents, the document gates (a ship-time successor of the bundle
documentation gate, the naming and 2.1 successors and the Card-5 pair r10) and the Makefile routes were
changed, and those are check-host consumers, so a new sealed run on the documentation commit is required. Only
r8b is to be bound in the release contract (`check_host`), and only if it exits 0 with
`head_before == head_after`, no changed file, no changed protected file and no changed sealed artifact. If it
is red, the cause is analysed first; a repair commit means a new sealed run on the new HEAD. The seal script
requires the sealed HEAD to be an ancestor of the Before-Ship HEAD. r8b result, HEAD, seconds, protected
files, sealed artifacts, receipt SHA-256, log SHA-256: **PENDING**.

## Final seal and two public-source reproductions

Final r8 (Seed r8, one product link, media re-derived without the Seed): `build/card-253-final-r8/final-identity.json`
(SHA-256 `92239fcedbb38352b0ccea0507c7969b699a2fcfaf5f8c90068700df65c021af`, 3,108 bytes) and
`build/card-253-final-r8/seal.json` (`card253-final-seal-v1`, status PASS, SHA-256
`bb4a509f99fb539f2e1055bf4d6c7b5ac0b40205d6e96be837fe2f1dcf37d469`, 11,088 bound inputs, 1,425 retained receipt
copies). Source authority `ccc08061b621f43ab4fde7f5a651045d4c87c247`; Final build commit
`751973de8e3472533dc5719cc620b03a554a1871`; its sealed `make -k check-source`
(`build/card-253-check-source-final-r8/receipt.json`): exit 0, 3,206.9 s, HEAD unchanged, 24,574 protected files,
53,734 sealed artifacts, no changed file. Budget: 75 native commands, 1 media transaction, 1 product link, 0 Seed
rebuilds. Media readback (`build/card-253-final-r8/media.json`): all 20 files read back, 0 unclassified bytes. The
earlier Final r7 (D81 `abc9bb49…`) was never shipped.

| Role | Bytes | SHA-256 |
|---|---:|---|
| ELF | 664,176 | `5eb056e03158578bb51edacbb9bd3064ea97a88b8d7613c1d0c052ae6a63d293` |
| PRG | 41,811 | `6bf9dbd59b7ef3c4ef19eaa900f57606d313fbbc106475c1ede0102d3ada63ad` |
| LTO | 651,076 | `0491996a5d530545bb663dbb72712be484190e665addf0318d5de51b86f13c6b` |
| D81 | 819,200 | `7df9db67f16c7218e56c9e4b64dfc0ed512c43771c9c39d9ccd56ddc76e55c2f` |

All four are byte-identical to the Seed r8 (`build/card-253-product-r8`).

Two independent reproductions from the public-source export are bound by
`config/c2-v253-r2-reproductions.json` (SHA-256 `959a4dd4c6a9af6963d050dd13ea094885c4f78d8f9b93979c9080d280d58228`,
12,705 bytes): `build/release-v2.5.3/repro-r2-1/` (root `/tmp/lisp65-v253-repro-r2-a`, PYTHONHASHSEED 0, LC_ALL C,
TZ UTC) and `repro-r2-2/` (root `/tmp/lisp65-v253-repro-r2-b`, PYTHONHASHSEED 1, LC_ALL C.UTF-8, TZ
Europe/Busingen). Each: 75 commands consumed, 1 product link, ELF, PRG, LTO and D81 equal to the Final byte for
byte, and the repl-comfort re-emission passes. Both roots hold the same source manifest (SHA-256
`10fbdc6daf38021744619b318cbb3dd31191f891ab083ca11dd14def85e229ba`). Toolchain receipt:
`build/release-v2.5.3/reproduction-qualification-r2/toolchain.json` (SHA-256
`e4580a83ae7f5b1adc2016ac4000c5bf61c645942c3fc969e4f79971a3e01b21`). Media census:
`config/c2-v253-r2-media-census-receipt.json` (SHA-256
`1a1bc9d9557d34eabece333eed7156c1091cf1b661eedd21d8030c2233e66523`). Reproduction media receipt:
`build/release-v2.5.3/repro-r2-2/public-result/media/receipt.json` (SHA-256
`cc519fa0d08a747985db57af55ba95a9f73d4aa618105e1072d403200d0094bc`). Packaging reuses the reproduced bytes; no
product build or link happens in Before-Ship.

Source delta since the reproductions (bound as `build/release-v2.5.3/allowed-source-delta-r2.json`, an exact
old/new list generated from the final tree): the release documents and the device report, the gate successors
and route changes made after the device session, the planning journal, the parked-items register, the document
index and the acceptance record. None of these is a producer, helper or configuration of the reproduction policy;
the three gate-only inputs the Final replay consumed (the GC-stress driver and the Card-5 pair) are the reviewed
exemptions of the packaging script, each proven by the Final head blob.

## Emulator evidence

All of this is emulator observation (xemu keyboard queue, framebuffer and memory reads, host readback of the D81),
never device timing. The Seed r8 medium (`build/card-253-rows-r8/`, tools `b42aaade`) is byte-identical to the
Final r8 medium (D81 `7df9db67…`, ELF `5eb056e0…`); the receipts record the Seed paths.

- Comfort rows 79/79 (`comfort/receipt.json`), Backspace rows 7/7 (`backspace/receipt.json`), boot to `l65>`
  1,750,546,399, 1,752,973,900 and 1,753,783,562 cycles in three sessions (about 43.2 s at 40.5 MHz) against
  1,679,382,289 for 2.5.2 (+4.2 % to +4.4 %), Comfort typing cost (40 keys, one at a time)
  `build/input-cost-natural-comfort-lite-c253-seed-r8b/receipt.json` 1,146,728 cycles/key against 1,130,909
  (+1.40 %).
- The 37-row record `build/card-253-rows-r8/receipt.json` (SHA-256 recorded in the acceptance file) carries its
  own mixed result and is bound as-is: `lcc-f2-regression` and `lcc-ladder-calibrated` (12/12) PASS,
  `oom-repl-local` and `oom-ide-save-100x40-recovery` PASS, `f1-249-char-after-four-ide-buffers`
  OBSERVED-RECOVERS, `oom-repl-global` **FAIL-NO-DROP** (a heap filled by a global list cannot be released from
  the keyboard), `ide-save-100x40-refusal` OBSERVED (out of memory after about 190 s, prompt back, file intact),
  `ide-save-cow-controls` **NOT RUN** (no fault-injection seam), `ide-buffer-switch-two-keys` failed once on a
  harness expectation and passed under the corrected a, b, a, b order, the rest PASS: saves of 20x40 (739 B) and
  50x40 (1,849 B) and a 100x20 save (1,899 B) with byte-identical host readback, `eval-buffer` of 5 and 50 forms,
  the macro rows, disk rows on prepared images (write enable, D4 `(13 8 13)`, D3 lossless, D5 144 files).
- Forced-collection `eval-buffer` rows (collection at every allocation: 1,688 and 14,205 allocations, all forms
  returned) **passed on the Final r7 medium** (`build/card-253-rows-final-r1/`) and were **not repeated on r8**
  (r8 changes only the `repl()` landing and `lib/lcc`).
- **GC stress** (collection at every allocation, 330 s wall limit per scenario), identical to r7: completed
  `defmacro-gc` 267 collections (peak 568 cells), `defmacro-use-gc` 431 (539), `pending32` 553 (1,012), `join640`
  543 (988), `reopen` 645 (576); **not completed, partial, not passes:** `return250`, `history10`,
  `reopen-home-delete-refill250` and `history-home-delete-refill250` reached the wall limit with a nearly full
  heap (peak 1,009 to 1,011 live cells). `mem_oom` was never set.
- **Capacity of loaded packages** (measured on the r7 medium, not repeated on r8): at boot 7,088 B of code space
  are free; after `ide`, `defstruct`, `buffer`, `inspect`, `place` and `string-extra` 5,388 B, 227 symbols and 52
  images remain. A refusal prints `*** VM: OUT OF MEMORY` and the prompt returns.

## Device evidence: PASSED (2026-10-03)

Narrative: [device report](release-2.5.3-device-report.md); raw receipts under `build/device-253-prep/`, two rounds
with the Final r8 medium (D81 `7df9db67…`, ELF `5eb056e0…`). Round 1 used the names `D253*.D81`; after a black
screen at the end of round 1 (cause unknown, every disk intact on readback) the machine was power-cycled and
round 2 used fresh names with the suffix `A`.

| Receipt | Content | Acceptance gate |
|---|---|---|
| `upload-02/receipt.json` and adapter `receipt-r8.json` | five SD files (round 2), new-name witness, byte-identical readback; `upload-01` is the round-1 upload with the same result | `device-upload` |
| `boot-02/receipt.json` | `mount`, `dload`, `run`; host tool clock 21.1 s to `Initializing`, 42.8 s to the first empty `l65>` (round 1: 21.2 s and 42.7 s) | `device-boot` |
| `rows-01`, `rows-02`, `disk-u-01`, `disk-o-02`, `disk-f-01`, `disk-l-01` and merged `device-rows-r8.json` | 49 executed groups, all PASS (product disk 33, user disk 12, other disk 1, 144-file disk 2, leaked-block disk 1) | `device-rows` |
| `owner-observations.txt` and `owner-rows-r8.json` | physical rows 1 to 4 and 6 PASS, row 5 PASS (took several minutes), row 7 stopwatch about 43 s | `owner-rows` |
| `readback-01`, `readback-02` | host verification of the SD files after each power cycle | evidence for the rows |
| `dma-01`, `oom-last-01`, halted `disk-o-01` | exploratory DMA row aborted at its precondition (scratch gap not free: 255); destructive row; first O attempt (fresh-session save returned 8) | none |

Adaptations (documented in `rows-253.json` with `device_note` fields): the four `peek` forms of `lcc-f2-ladder`
were removed because the scratch gap `$17A0..` is not zero on the device; the O phase was re-ordered after the
fresh session (`d4-swap-refused` of phase O never ran as written; it is replaced by `o-remount-enable` and
`f-swap-refused`) and the merged device rows record it as not executed. Device timings are the host tool clock
(not a stopwatch) except where the owner stopwatch is named.

## Acceptance record

`config/c2-v253-r2-target-acceptance.json` binds one raw (or reviewer-derived) receipt per gate and asserts named
fields of it. Its `PASS` means exactly that the asserted fields hold; it is not a claim that each gate was a single
clean PASS run. Where the evidence is weaker the gate carries a `scope_note`.

- `comfort-rows`, `backspace-rows`: the Seed r8 emulator receipts (79/79, 7/7), not device rows.
- `paired-typing`: pairing of the 2.5.2 and 2.5.3 observer receipts; records **+1.40 %**, an increase, not an
  improvement.
- `gc-session`: the Seed r8 emulator record (`build/card-253-rows-r8/receipt.json`); it asserts the five completed
  scenarios as COMPLETED and the four partial ones as LIMIT, and the honest row results (FAIL-NO-DROP, NOT RUN).
- `device-upload`, `device-boot`, `device-rows`, `owner-rows`: the device session above. The raw boot, rows and
  disk receipts bind the Final D81 and ELF paths; the upload receipt is adapted (adds `new_file_witness` and
  `readback`), the phase receipts of both rounds are merged into one `device-rows` receipt, and the owner rows are
  a reviewer-authored record of the plain-text observations.

## Measured limits and accepted cost

- **Native code:** `.text` 36,559 to 36,899 bytes, **+340 B** (`eval_v2_workbench_service` +336, `main` +2, `repl`
  +2); the owner raised the cap to **+368 B** (2026-10-02). ELF file 662,816 to 664,176 bytes.
- **Library code** (Seed r8 price receipt, against the 2.5.2 medium): M65D 4,086 to 4,373 B (+287), IDE 14,992 to
  15,063 (+71), LCC 8,134 to 8,349 (+215), `nth` 19,807 to 19,814 (+7), +580 B of library code in `CODE.BIN`;
  `idex` and `buffer` unchanged; Comfort library 2,095 B (+0 against the 2.5.2 source, 905 B under its limit).
- **Boot to `l65>`:** emulator +4.2 % to +4.4 % (about +1.8 s). Device: tool clock 42.8 s (2.5.2: 40.9 s), owner
  stopwatch about 20 s to `Initializing` and about 43 s to the REPL.
- **Typing** (emulator cycles): mean 1,130,909 to 1,146,728 cycles/key, **+1.40 %**; steady state unchanged
  (median 1,199,444.5 against 1,199,444.0). Physical feel (owner): good.
- **Remount** (host VM steps / sector reads): blank disk 193,403 / 8, 144 files 230,148 / 313, 1,584 blocks
  342,042 / 1,645. Device tool clock: 9-file disk 35.7 s, 144 files 49.3 s, leaked-block disk 33.0 s.
- **Device save and `eval-buffer` times** (tool clock, upper bounds): `save-buffer-to` 20x40 37.7 s, 50x40
  92.1 s; editor-key save 37.2 s and 91.7 s; `eval-buffer` of 5 forms 24.9 s and of 50 forms 217 s. The owner's
  physical `C-x C-s` on the 50x40 buffer took several minutes (unexplained).
- **Input limits** unchanged: 32 pending lines, 640 bytes, 250 characters in the active line, ten history entries
  of at most 250 bytes.
- **IDE save and `eval-buffer` fixture limits** (host, 588 additional heap cells): 196/119 lines at width 20,
  99/98 at 40 and 57/56 at 70 (without/with edit cache). **Host test results, not guaranteed limits**; saves are
  limited to 8,192 bytes by M65D. Extra heap for a 50x40 save 2,207 to 212 cells, for `eval-buffer` 2,206 to 181.

## Known issues carried

Fixed since 2.5.2 and not listed any more: whole-buffer list in save and `eval-buffer`, silent partial
`eval-buffer`, `%set-macro` name root, single-buffer switch text loss, stale mark, multi-pair `setq`, surplus
builtin arguments, `nth` on dotted tails, loader trimming trailing spaces/CR, full-directory remount,
damaged-allocation-map overwrite, and the dead prompt after `*** VM: OUT OF MEMORY` (the prompt returns).

- **New observations from the device session:** a black screen once after a Freezer disk swap (cause unknown, not
  reproduced in three later swaps, every disk intact); a physical `C-x C-s` on a 50x40 buffer that took several
  minutes.
- **A heap filled by data the program still holds cannot be released from the keyboard** (typing needs memory);
  reset required. On the device the message and the returning prompt were seen; the emulator showed that every
  freeing attempt fails.
- **Closures capturing a `let` variable at the Comfort prompt** give `*** VM: BAD BYTECODE` (same on 2.5.2).
- `mapcan` with more than 12 input elements fails; string literals over 255 bytes fail to compile; physical
  `C-x C-c` is unavailable (use `C-x q`).
- Disk limits: classes that reserve blocks outside file chains (REL, GEOS, a 1581 boot sector) are refused for
  writing; two disks with identical name and ID cannot be told apart; a medium swap before the first write of a
  save reports status 12; **no reclaim** of leaked blocks (planned 2.5.4); a chain changed between the loader's two
  read passes is not rejected; no protection against interrupted physical writes or power loss is claimed.
- Test coverage not achieved: `ide-save-cow-controls` (write-fault controls, no fault-injection seam) was not run
  anywhere; the four partial GC-stress scenarios; the editor-key path of the 100x20 save on r8; forced-collection
  `eval-buffer` on r8 (passed on the Final r7 medium).
- The remaining items under "Other known limitations" of the 2.5.2 notes are unchanged.

## Pending physical rows

Not verified on the device and carried into the contract as pending physical rows: the cause of the black screen
after a Freezer swap; `ide-save-cow-controls` (no seam); DMA on the device and DMA line mode (the scratch gap
`$17A0..$17FF` is not free: 2.6 needs another device-verified DMA scratch area); the editor-key path of the
100x20 save on r8; forced-collection `eval-buffer` on r8; four GC-stress scenarios partial; physical `C-x C-c`
(known issue, not a row). Rows not performed or inconclusive are never marked PASS.

## Package and reviewer seal

The package will contain the four assets (product archive, source archive, manifest, clean-build receipt), built
from the reproduced bytes without a product build or link (`package-release-r8.py`, double-pack equality,
`verify-local-r8.py`). Remaining order: commit the documentation and gate successors, run the sealed `check-host`
r8b as a user unit, fill and pin the release contract, commit the Before-Ship records, run
`seal-after-commit-r8.py --final`, commit the proof receipt and tag `proof/v2.5.3`, build the source projection
(tag `v2.5.3` inside), verify locally, then publication as separate steps (`publish-r8.py` dry run, prepare, push to
branch `release-v253`, draft release, verify draft, publish, verify published). Ship and Publish were authorised
by the owner on 2026-10-03 (plan journal entry in the same commit as the authorization record). Public main must
still be `fde9fb132e32dc71905b0efb98e227678a528695`; never force-push.
