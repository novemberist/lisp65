# 2.5.5 — Before-Ship

**Preparation r1, 2026-10-07, after the device session (private HEAD `c9a789fd` plus the documentation commit
that follows this text).** The device session on a physical MEGA65 **passed** as a manual owner session, and
the owner approved Ship and Publish of 2.5.5 and accepted the garbage-collection gate recorded as FAIL on
2026-10-07, after the session ("Freigabe erteilt. Wir folgen deinen Empfehlungen",
`build/device-255-prep/owner-observations.txt`, last line; the reviewer had recommended yes to both). What is
still open and not claimed: the new sealed `check-host` run on the documentation commit (**PENDING**), the
reviewed release contract, the post-commit seal and the publication itself. The preparation made no device or network contact
and no Git write.

## Sealed full host run: r1 green on `c9a789fd`, the run on the release commit PENDING

Target: `make -k check-host`, sealed run (read-only mounts, isolated generated tree).

| Run | HEAD | Exit | Seconds | Receipt SHA-256 | Result |
|---|---|---:|---:|---|---|
| r1 `build/release-v2.5.5-check-host-r1` | `c9a789fd3f3363dea0b9617b9d1b863bdb5194be` | 0 | 4,701.5 | `4a4124b7408e966d0533c6a38484941d20652093f95d51d02914375e0b41aeea` | green: no changed file, 0 changed protected files, no changed sealed artifact; 25,809 protected files, 57,292 read-only sealed artifacts |
| r2 `build/release-v2.5.5-check-host-r2` | the documentation commit | **PENDING** | **PENDING** | **PENDING** | **PENDING** |

r1 ran before the documents below changed. The ship-time documents, their gates and the Card-5 pair are
`check-host` consumers, so a new sealed run on the documentation commit is required, and only that run (r2) is
bound in the release contract.

## Final seal and two public-source reproductions

- Final `build/card-255-final-r1`: ELF `592b2c71c30901d2bb9599d2324678be5cd910865fbbfaf888c5d28ecb2e701f`, LTO
  object `0d01e16f1315101d37effed0002f331a878f652552d41d0b9761269730e11c24`, PRG
  `7a6e6a5195cb667b5719a645b2a11837b77fcf0c5ca5e5b05dd25b198822dc1a`, D81
  `4f0b76ad395ed861da104960859b8d9416750a00684dd4826a1193b14245523b`; byte-identical to the Seed r1b; seal PASS
  (13,578 inputs, 1,734 receipt copies), `seal.json` SHA-256
  `2776060ce564c6a16254a2736fb0cac8dec27f35e0d87b6188e3b622034abcb4`.
- The Seed halted after its link on the instruction pair at `$C473` and was continued as one narrowly pinned
  reviewed class without a second link; the Final inventory ran inside the same class.
- Two clean public-source reproductions (`config/c2-v255-r1-reproductions.json`): 75 commands and one product
  link each, distinct roots, hash seed, locale and time zone; all four artifacts byte-identical to the Final in
  both.
- **Host.** Seed, Final and both reproductions ran on one Fedora 45 host with one set of pinned host tools
  (`c2_v255_r1_toolchain.py`). The release contract therefore admits no host drift: a sealed host tool whose
  bytes differ from the live binary stops the seal. The merged bitcode of `/usr/bin/llvm-link` is an
  intermediate, not an artifact; it is equal in both reproductions (`c6900576…`) and differs from the file the
  Final wrote (`acbc5201…`, same 265,228 bytes) on the same host; recorded, not required; cause not
  investigated. Past releases, 2.5.4 among them, are checked under the historical host pin rule
  (`tools/host-lisp/historical_host_pin_v255_20261007.py`).
- Seven files changed between the reproduction export and the candidate commit (the result of the `pending32`
  repeats in two documents, the document gate and four receipts). None is a producer of the reproductions; they
  are rows of the allowed source delta.

## Emulator evidence (Seed medium, byte-identical to the Final medium)

- Measured editor key cost (`build/card-255-typing-measure-r1`; cycle counter, 40.5 MHz, medians without a
  collection, 2.5.4 against 2.5.5): insert 124.2 to 150.0 ms against 57.3 ms, Backspace at column 20 119.7
  against 60.4 ms, Return on 30 characters 462.9 against 416.3 ms, REPL key to visible glyph 14.0 ms in both;
  all 18 pass rules hold.
- Rows (`build/card-255-rows-r1`, reviews `build/card-255-rows-r1-review*`): no product failure; the 14 new
  rows for the entry store pass; every 2.5.4 row keeps its status. The first review of the new rows has the
  top-level verdict `FAIL` and is bound as such: one row failed through a driver defect and passes in the
  rerun.
- Comfort 79 of 79, Backspace 7 of 7. Typing lane at the Comfort prompt: mean 1,146,716 cycles per key against
  1,146,714 in 2.5.4 (this lane is the REPL prompt, not the IDE editor).
- Not green, unchanged from 2.5.4: `ide-buffer-switch-two-keys`, `ide-save-100x20-keys` (harness expectation),
  `oom-repl-global` (known behaviour).
- `$D703` probe: write applied, product survived a library load; emulator DMA semantics not shown.

## Device evidence: PASSED (2026-10-07, manual owner session)

See the [device report](release-2.5.5-device-report.md): upload and readback byte-identical; boot unchanged at
20 s plus 22 s by stopwatch; typing in the IDE editor, owner: "Stark verbessert, Backspace immer noch leicht
verzögert, stärker wenn Taste gehalten wird"; a held key gave 227 characters in 10 s in the editor and 202 at
the prompt; two buffers with the physical RUN/STOP key complete after re-entry; two saved buffers read back as
expected; 20x40 save in 4 s (2.5.4: 5 s) with a byte-identical readback; Freezer mount without a problem.
Findings: Backspace still slightly delayed; and, not a 2.5.5 matter, Return at the empty prompt leaves Comfort
(documented since 2.5.0).

## Acceptance record and gate set

`config/c2-v255-r1-target-acceptance.json` binds eight gates to raw or adapter receipts. Its status is
`FAIL-GATE-RECORDED: gc-session`.

| Gate | Receipt | Against 2.5.4 |
|---|---|---|
| `comfort-rows` | `build/card-255-rows-r1/comfort/receipt.json` | kept |
| `backspace-rows` | `build/card-255-rows-r1/backspace/receipt.json` | kept |
| `paired-typing` | `build/release-v2.5.5/paired-typing-r1.json` (Comfort REPL lane) | kept |
| `typing-measure` | `build/release-v2.5.5/typing-measure-r1.json` (IDE editor key cost) | added |
| `gc-session` | `build/card-255-gc-r1/summary.json` (status **FAIL**, bound as recorded) | kept |
| `emulator-rows` | `build/release-v2.5.5/emulator-rows-r1.json` (three reviewed records; status REVIEWED) | kept, as one adapter |
| `device-upload` | `build/release-v2.5.5/device-upload-r1.json` | kept, without a driver |
| `owner-rows` | `build/release-v2.5.5/owner-rows-r1.json` | kept; carries the stopwatch boot and the two counts |

**Absent, stated plainly:** there is no `device-boot` receipt (no tool clock) and no `device-rows` receipt (no
automated device rows), because the session had no device driver, as in 2.5.4.

**`gc-session` is FAIL by the committed rules**, as in 2.5.4 (GC-stress session on the Seed medium,
`build/card-255-gc-r1`): six of eight scenarios pass with no out-of-memory; `history10` and
`history-home-delete-refill250` stall on the display defect of long history recall, exactly as on the 2.5.4
Final; collections, allocations and both peaks equal the 2.5.4 Final in every scenario; headroom at the
highest peak 43 of 1,070 cells. One `pending32` attempt ended in a breakpoint timeout; it was not reproduced in
seven repeats (five on the sealed 2.5.5 Final, two on the sealed 2.5.4 Final) and is a coincidence of driver
and emulator, with the mechanism inferred (`build/card-255-gc-pending32-r1/notes.txt`). No scenario covers the
IDE editor under forced collection. The gate is not reworded into a pass: the release contract seals only if
the authorization record names `gc-session` in `accepted_failed_gates` with the owner's decision. **Owner word
2026-10-07: the gate recorded as it is (formally FAIL, figures identical to 2.5.4) is accepted and publication
of 2.5.5 with it is approved** (`build/device-255-prep/owner-observations.txt`, last line). The decision the
owner took for 2.5.4 was not carried over; this is a new word for 2.5.5.

## Pending physical rows

The acceptance record lists them (`pending_physical_rows`): no driver session; the GC-session FAIL and what the
session does not cover; typing figures are emulator measurements and the device has an impression and two
counts only; the Backspace finding; the empty-Return side finding; no record of a power cycle before the
upload; the keymap seam, the long checklist rows and further held-key counts not done on the device; `$D703`
open on hardware; a RUN/STOP in the middle of a key burst covered by the emulator only; type-ahead and the long
remount carried from 2.5.4 and not re-tested; the three emulator rows that are not green and unchanged from
2.5.4; physical `C-x C-c` unavailable.

## Package and reviewer seal

Scripts in `build/release-v2.5.5/` (successors of the 2.5.4 scripts): `release_contract_r1.py`,
`package-release-r1.py`, `verify-local-r1.py`, `seal-after-commit-r1.py`, `commit-package-source-r1.py`,
`publish-r1.py`. The seal exports the committed source, double-packs four assets, verifies them and writes
`tests/bytecode/dialect-v2/evidence/architecture-blocks/v255-before-ship-receipt-r1.json`. The seal script
checks the four sealed host tools by the host rule and never treats them as repository files. Public parent:
`bdaf2dd96a6bf77d7a02cccdf0db148cefe914a1`. Publication is a separate, owner-authorized step.
