# 2.5.4 — Before-Ship

**Preparation r1, 2026-10-05, after the device session (private HEAD `645d3243` plus the documentation commit
that follows this text).** The device session on a physical MEGA65 **passed** as a manual owner session, and
the owner has pre-approved Ship and Publish of 2.5.4 (plan journal), released the three device findings as
known limits (2026-10-05) and accepted the memory cost with the GC gate recorded as FAIL (2026-10-06). What is still open and not claimed: the
new sealed `check-host` run on the documentation commit (**PENDING**), the reviewed release contract, the
post-commit seal and the publication itself. The preparation made no device or network contact and no Git
write.

## Sealed full host run: r6 green on `645d3243`, r7 PENDING on the release commit

Target: `make -k check-host`, sealed run (read-only mounts, isolated generated tree).

| Run | HEAD | Exit | Seconds | Receipt SHA-256 | Result |
|---|---|---:|---:|---|---|
| r6 `build/release-v2.5.4-check-host-r6` | `645d324311ec057c6efd6e253afddce5308bcef2` | 0 | 4,766.5 | `b23feb736711fb5ff280f079b87e391162e7020ae0247769c8caa3e2f50f79c0` | green: no changed file, 0 changed protected files, no changed sealed artifact; 25,378 protected files, 56,343 read-only sealed artifacts |
| r7 `build/release-v2.5.4-check-host-r7` | the documentation commit | **PENDING** | **PENDING** | **PENDING** | **PENDING** |

Runs r1 to r5 were red for environment reasons after the build host moved to Fedora 45 (stale equivalence host
binaries, a receipt that pinned one of them, a `/tmp` quota, a temporary directory inside the repository); the
plan journal records each. r6 ran before the documents below changed. The ship-time documents, their gates and
the Card-5 pair are `check-host` consumers, so a new sealed run on the documentation commit is required, and
only that run (r7) is bound in the release contract.

## Final seal and two public-source reproductions

- Final `build/card-254-final-r1`: ELF `7b951eb9c92bc8797278903465b7483b3168a0eb935237a8f62ea3757f205244`, LTO
  object `e9d6dc850e01dac45efb0dc1163ac3b463a5d26e00a49c3107380073da472afc`, PRG
  `192138eb70b4dc46a992e95651f52180a4e1687cd138b9347f8e3b77e37d70c4`, D81
  `250fdc763ae9e5b04cf149a6f2a7a3aa9fb293ff8da58e9a703e0c601efaef5d`; byte-identical to the Seed r1b; seal PASS
  (12,348 inputs, 1,582 receipt copies), `seal.json` SHA-256
  `7b70c025ef66de595e1d2c050e6d65d54ed9d34243c807c8faf4618fda8e5603`.
- Two clean public-source reproductions (`config/c2-v254-r1-reproductions.json`): 75 commands and one product
  link each, distinct roots, hash seed, locale and time zone; all four artifacts byte-identical to the Final in
  both.
- **Host.** The Final was linked with the Fedora 44 host tools. The build host was upgraded to Fedora 45 on
  2026-10-04; both reproductions ran with the Fedora 45 host tools (`c2_v254_r1_toolchain.py`). The merged
  bitcode of `/usr/bin/llvm-link` is a host-dependent intermediate (Final host 250,796 B `728903b9…`,
  reproduction host 265,228 B `e2c2d6a1…`), recorded and not compared. Three sealed inputs of the Final are the
  Fedora 44 binaries `/usr/bin/gcc`, `/usr/bin/llvm-link` and `/usr/bin/setarch`; the release contract admits
  them as drift class "host" (sealed hash = Final-host pin, live hash = reproduction-host pin). Past releases
  are checked under the historical host pin rule (`tools/host-lisp/historical_host_pin_20261004.py`).

## Emulator evidence (Seed medium, byte-identical to the Final medium)

- New 2.5.4 rows (`build/card-254-rows-r1`, continuation `-r1c`, review `build/card-254-rows-r1-review`): no
  product failure; all 20 edit-persistence abort points and both pending-`C-x` rows `OK`; keymap seam rows pass.
  The review's top-level verdict is `FAIL` and is bound as such: it reflects sessions run r1 lost to a host
  transport fault, which r1c repeated.
- Comfort 79 of 79, Backspace 7 of 7. Typing lane at the Comfort prompt: mean 1,146,714 cycles per key against
  1,146,728 in 2.5.3 (this lane is the REPL prompt, not the IDE editor).
- Not green, unchanged from 2.5.3: `ide-buffer-switch-two-keys`, `ide-save-100x20-keys` (harness expectation),
  `oom-repl-global` (known behaviour).
- `$D703` probe: write applied, product survived a library load; emulator DMA semantics not shown.

## Device evidence: PASSED (2026-10-05, manual owner session)

See the [device report](release-2.5.4-device-report.md): upload and readback byte-identical, boot 42 s by
stopwatch, physical RUN/STOP at the prompt and in the editor, keymap seam, 20x40 IDE save in 5 s (2.5.3:
37.7 s) with a byte-identical readback, Freezer swap without a problem. Findings without a 2.5.4 regression by
current evidence: type-ahead lost while the editor opens, IDE typing slower than the REPL, slow
`(m65d-remount)`.

## Acceptance record and gate set

`config/c2-v254-r1-target-acceptance.json` binds seven gates to raw or adapter receipts. Its status is
`FAIL-GATE-RECORDED: gc-session`.

| Gate | Receipt | Against 2.5.3 |
|---|---|---|
| `comfort-rows` | `build/card-254-rows-r1c/comfort/receipt.json` | kept |
| `backspace-rows` | `build/card-254-rows-r1c/backspace/receipt.json` | kept |
| `paired-typing` | `build/release-v2.5.4/paired-typing-r1.json` | kept |
| `gc-session` | `build/card-254-gc-r2/summary.json` (status **FAIL**, bound as recorded) | kept |
| `emulator-rows` | `build/card-254-rows-r1-review/reviewed.json` (status REVIEWED) | added |
| `device-upload` | `build/release-v2.5.4/device-upload-r1.json` | kept, without a driver |
| `owner-rows` | `build/release-v2.5.4/owner-rows-r1.json` | kept; carries the stopwatch boot |

**Absent against 2.5.3, stated plainly:** there is no `device-boot` receipt (no tool clock) and no
`device-rows` receipt (no automated device rows), because the session had no device driver.

**`gc-session` is FAIL by the committed rules** (GC-stress session on the sealed Final, 2026-10-06, wrapper
`tools/host-lisp/c254_gc_session_20261006.py`): six of eight scenarios pass with no out-of-memory, two of them
(`return250`, `reopen-home-delete-refill250`) for the first time; `history10` and
`history-home-delete-refill250` stall on a display defect identical in the 2.5.3 records (a recalled
250-character entry at the bottom of the screen is drawn over the rows above); and both peak comparisons exceed
the 2.5.3 Final by a constant +3 live cells and +88 arena bytes (headroom at the highest peak 43 of 1,070
cells; 2.5.3: 46). Not covered: Return of a recalled 250-character entry and delete/refill inside one under
forced collection. **Owner word 2026-10-06: the memory cost is accepted and publication with the gate recorded
as it is (formally FAIL) is approved** (`build/device-254-prep/owner-observations.txt`, last line). The gate is
not reworded into a pass: the release contract seals only because the authorization record names `gc-session`
in `accepted_failed_gates` with that decision.

The owner released the three device findings as known limits for 2.5.4 on 2026-10-05; faster editor typing is
the first card of the next cycle. Emulator comparison of the editor: 2.5.4 is 1.3 to 1.7 % slower per key than
2.5.3 (a constant 1.8 ms); the editor is about 30 times slower per key than the REPL in both versions.

## Pending physical rows

The acceptance record lists them (`pending_physical_rows`): no driver session; the GC-session FAIL, its memory
cost and what it does not cover; no record of a power cycle before the upload; large
saves, out-of-memory rows, additional REPL rows and physical `C-x C-s` not done on the device; `$D703` open on
hardware; a RUN/STOP in the middle of a key burst covered by the emulator only; the three findings; the three
emulator rows that are not green and unchanged from 2.5.3; physical `C-x C-c` unavailable.

## Package and reviewer seal

Scripts in `build/release-v2.5.4/` (successors of the 2.5.3 r8 scripts): `release_contract_r1.py`,
`package-release-r1.py`, `verify-local-r1.py`, `seal-after-commit-r1.py`, `commit-package-source-r1.py`,
`publish-r1.py`. The seal exports the committed source, double-packs four assets, verifies them and writes
`tests/bytecode/dialect-v2/evidence/architecture-blocks/v254-before-ship-receipt-r1.json`. Public parent:
`bf9d7c0c4eaeccdd5a4b0265b9e3f3e3b000d387`. Publication is a separate, owner-authorized step.
