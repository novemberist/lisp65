# 2.5.2 — Before-Ship

2026-09-30, preparation r1. Ship/Publish has the owner's word recorded in the
[plan journal](post-2.4.0-plan.md) ("2.5.2 Mein Wort: Ja", commit b23ba0f2),
together with the choice of the full release discipline (option A, two
public-source reproductions, commit e835e470). The preparation made no device or
network contacts and no Git writes; the reviewer first commits the documents
and records, then runs the post-commit sealing script
`build/release-v2.5.2/seal-after-commit-r7c.py --final` against the reviewed
release contract.

## Sealed full host run: PASS on the sealed HEAD (third attempt)

Result: `make -k check-host` on HEAD
`6f2cbe9940c48e3f049a2a79fe0a10e071d10b4a`, receipt
`build/release-v2.5.2-check-host-r3/receipt.json` (SHA-256
`c59f4525ddcc43c468349bd8bd81ab81b36799a80156834e2561483af855262d`): exit code 0,
3,824 s, `head_before == head_after`, 24,117 protected files, 50,548 sealed
read-only artifacts, zero changed files, zero changed protected files, zero
changed sealed artifacts. Log: `build/release-v2.5.2-check-host-r3/check-source.log`
(SHA-256 `f1440279c0c028e28ab119838095f11aa589370854802cddb621e887754314fe`).
The run applies to that commit only; the Before-Ship commit that follows adds
documents and records, and the seal script requires the sealed HEAD to be an
ancestor.

Two earlier sealed runs were red and are retained; both reds were understood and
neither was waived:

- **r1** (`build/release-v2.5.2-check-host-r1`, HEAD `ec4a279a`, exit 2,
  4,618 s): one red, `workbench-private-inline-composition-probe`, "receipt
  drift". The probe pinned the SHA-256 of the m65d suite; the directory-link fix
  had changed that suite by adding three regression cases. Fixed by a dated
  successor receipt
  (`tests/bytecode/dialect-v2/evidence/capability-carrier/workbench-private-inline-composition-probe-v252-20260930.json`),
  the Makefile route and the Card-5 receipts r4 (commit `6f2cbe99`). The old
  receipt is unchanged.
- **r2** (`build/release-v2.5.2-check-host-r2`, HEAD `6f2cbe99`, exit 2,
  4,349 s): one red, `workbench-ux-harness-selftest`: a subprocess timeout of 30 s
  in the `full_pass` case (about 19 s when idle). The run was started under
  `ionice -c3` (idle I/O class) next to a foreign four-worker profiling job.
  The same target had passed in r1 and passed three times standalone. r3 reran
  the identical HEAD at normal priority and passed. **The timeout was not
  changed**; this is a timing-margin watch item (see the parked-items register),
  not a fix.

Only r3 is bound in the release contract (`check_host`). Routes that this run
exercises and that did not exist in 2.5.1 are listed in
`build/release-v2.5.2/step5-commands.md` (section 5.3), for example
`v252-public-authority-check`.

## Final seal and two public-source reproductions

Final (O2-lite Seed r7c, one product link, media re-derived without the Seed):
`build/o2-lite-final-r7c/final-identity.json` (SHA-256
`280a0d08e755c249dbb30e23b02b42703a291c946704383ea493b57b30bfd057`, 3,117
bytes) and `build/o2-lite-final-r7c/seal.json` (`o2-lite-final-r7c-seal-v1`,
status PASS, SHA-256
`8f3b379421f1a7ffaa6fae9b9155377145418a1cf094be4c4c2ece71514f09e5`,
9,528 bound inputs, 1,242 retained receipt copies). Final build commit
`c4711ed2d3b2a532ddca2b9d281a14d330448760`; its sealed `make -k check-source`
(`build/o2-lite-check-source-r7c-final-r3/receipt.json`): exit 0, 3,388.7 s,
HEAD unchanged, 23,773 protected files, 49,128 sealed artifacts, no changed
file. Budget: 75 native commands, 1 media transaction, 1 product link, 0 Seed
rebuilds. Media readback (`build/o2-lite-final-r7c/media.json`): all 20 files
read back, 0 unclassified bytes.

| Role | SHA-256 |
|---|---|
| ELF | `4edcc037a3fd729cc124ae40d8c85349889ba17941e3468f1ffe8c2de2aa4abd` |
| PRG | `f74ca2df859d0f521f3926a6e9306f0cb9d53e7fe686c35899239eaca3281972` |
| LTO | `af01c0a83d94429fcc747534cfcd76ad920a050a52d72cba3b07430966c1cf2a` |
| D81 | `ae4e2931bb79bc6d963a2334d67e0777e924c9b34db42ef16567f472c87a300d` |

Two independent reproductions from the public-source export are bound by
`config/c2-v252-r1-reproductions.json` (SHA-256
`24d0b37949357e3a0f0d128c66ccf013204d002f68aac235a8f0a043768483f5`):
`build/release-v2.5.2/repro-r3-1/` (root `/tmp/lisp65-v252-repro-r1-a`,
PYTHONHASHSEED 0, LC_ALL C, TZ UTC) and `repro-r3-2/` (root
`/tmp/lisp65-v252-repro-r1-b`, PYTHONHASHSEED 1, LC_ALL C.UTF-8, TZ
Europe/Busingen). Each: 75 commands consumed, 1 product link, ELF, PRG, LTO
and D81 equal to the Final byte for byte, and the repl-comfort re-emission
(2,095 B blob, 3,725 B package) passes. Toolchain receipt:
`build/release-v2.5.2/reproduction-qualification-r1/toolchain.json`. The
earlier attempts `repro-r1-*` and `repro-r2-*` are stopped record attempts and
are not evidence. Packaging reuses the reproduced bytes; no new product build
or link happens in Before-Ship.

## Device evidence

The [device report](release-2.5.2-device-report.md) is the narrative; raw
receipts are under `build/device-252-prep/`. Medium: `D252.D81`, the Final D81
(`ae4e2931…`), uploaded after a physical power cycle together with a separate
user disk `D252U.D81` and read back byte-identical (`upload-01`). Boot
(`boot-01`), **host tool clock, not a stopwatch**: 20.913 s from RUN to
Initializing, 40.879 s (polling upper bound) to the first empty `l65>` prompt.
Automated rows: 21/21 groups PASS, spread over `rows-02` (HALT after two PASS
rows), `manual-limit-05` (the 641-byte limit row, completed by hand, screens
only) and `rows-04` (18 rows, status PASS); the report lists the driver halts,
none of which was a product defect. Owner physical rows
(`owner-observations.txt`, 07:33Z): "Alle manuellen Tests erfolgreich … Tippgefühl
ist sehr gut" for typing and Backspace, reopening the previous line, the string
example, physical C-x q and RUN/STOP during a running form. Directory-link
fix on a real user disk (`disk-01`, `readback-01`): nine files, F8 survives
saving F0 in entry 0; the host readback after a power cycle shows the product
disk unchanged and the directory chain intact.

Emulator observations on the byte-identical Seed r7c medium: Comfort rows
79/79 (`build/lite-rows-r7c.log`, screen dumps in `build/lite-rows-r7c/`, no
JSON receipt) and Backspace rows 7/7 (`build/lite-bs-rows-r7c/receipt.json`).

The acceptance record `config/c2-v252-r1-target-acceptance.json` binds one raw
(or reviewer-derived) receipt per gate and asserts named fields of it. Its
`PASS` means exactly that the asserted fields hold; it is **not** a claim that
each gate was a single clean PASS run. Where the raw evidence is weaker, the gate
carries a `scope_note` saying so:

- `comfort-rows` binds the PASS receipt `rows-04` (18 rows) and asserts the
  Comfort, string, history and IDE rows in it. The reopen-previous-line rows
  and the 641-byte input-limit row are not in that receipt: `rows-02` is HALT
  (two PASS rows, the third RUNNING) and the limit row was completed by hand
  (`manual-limit-05`: screens only, no receipt). The emulator Comfort rows
  79/79 have no JSON receipt.
- `gc-session` binds a **HALT** progress file (see below). The record asserts
  only true facts of it: Final D81 and ELF, and that allocation 535 has 1,009
  live cells and no out-of-memory before or after. No forced-collection
  scenario completed.
- The device receipts were adapted by the reviewer: the raw receipts bind the
  byte-identical Seed r7c paths, the contract compares the Final paths, so
  `receipt-r7c.json` files rebind medium and ELF (same bytes) and record their
  derivation; the upload adapter adds `new_file_witness` (from the ftp message
  in the transfer logs) and the byte-identical readback. The owner rows are a
  reviewer-authored JSON record of the plain-text owner observation. The paired
  typing record pairs two retained observer receipts.

## Measured limits and accepted cost

- Typing, emulator cycles, same lane (Comfort prompt, 40 characters, one key at a
  time): 2.5.1 **1,635,493** → 2.5.2 **1,130,909** cycles/key, **−30.85 %**
  (about 40.4 → 27.9 ms/key at 40.5 MHz). Receipts
  `build/input-cost-natural-comfort-strings-r1/receipt.json` (2.5.1 medium
  `9978daa1…`) and `build/input-cost-natural-comfort-lite-r7c/receipt.json`
  (Final D81). These are emulator cycle measurements, not physical timings; the
  owner's physical judgement is "Tippgefühl ist sehr gut".
- Input limits: 32 pending lines, 640 bytes of accepted source, 250 characters in
  the active line, ten history entries of at most 250 bytes
  ([release notes](../releases/2.5.2.md)).
- Forced collection at every allocation (emulator, Final D81): no out-of-memory
  event; peak **1,009 live cells** in the reopen-and-refill scenario
  (`build/gc-stress-r7c-reopen-home-delete-refill250-b/progress.json`, 535
  collections, `mem_oom` 0). **All retained runs of this harness are HALT**
  (timeouts near a full heap, and earlier attempts on tooling checks): the
  harness did not complete the scenarios, and this is a watch item for 2.5.3,
  not a pass. The journal figure 1,071 is not in the retained files.
- Boot: see device evidence (tool clock only).

## Known issues and pending physical rows

Known issues carried in [the release notes](../releases/2.5.2.md) and not fixed
in 2.5.2 (planned for 2.5.3 where noted):

- IDE save (`C-x C-s`) and `eval-buffer` build a character list of the whole
  buffer; larger files can load but fail to save or evaluate. Fixture results
  (20–23 lines of 20 characters, 10–12 of 40, 6–7 of 70 with 588 spare heap cells)
  are test results, not guaranteed limits. Heap fix planned for 2.5.3.
- `eval-buffer` GC-root defect: collection during compilation can drop its source
  string and stop evaluation early without an error message. Planned for 2.5.3.
- Host compiler tests: LCC can drop later pairs of a multi-pair `setq` and skip
  surplus arguments to some builtins; confirmation on the release medium is
  pending. Use one assignment per `setq`.
- String literals over 255 bytes fail to compile (`*** VM: BAD BYTECODE`).
- Physical IDE `C-x C-c` remains unavailable (use C-x q); standalone Ship
  RUN/STOP remains independently unverified.

Pending physical rows, honestly open: stopwatch cold boot (only the host tool
clock was measured), physical IDE `C-x C-c`, standalone Ship RUN/STOP.

## Package and reviewer seal

The package contains the four assets (product archive, source archive, manifest,
clean-build receipt), built from the reproduced bytes without a product build or
link (`package-release-r7c.py`, double-pack equality, `verify-local-r7c.py`).
After committing the explicit `commit-paths-r1.txt` list, the reviewer pins the
contract SHA-256 and runs `seal-after-commit-r7c.py --final`, then commits the
proof receipt, tags `proof/v2.5.2`, builds the source projection and publishes as
a separate step. Exact commands: `build/release-v2.5.2/step5-commands.md`
section 6. Public main must still be
`2817f0cffddfdae4438164ce69bdfa5c0e37b52a`; never force-push.
