# Plan after lisp65 2.4.0

Rolling plan of the cycle that starts with the 2.4.0 release (published
2026-09-24, public `main` `d749aba4`, tag object `79c00317`, proof tag
`proof/v2.4.0` at `06806910`, local). The sealed journals of the previous
cycles are `docs/planning/v2.0.0-pre-plan.md`,
`docs/planning/post-2.2.0-plan.md` and `docs/planning/post-2.3.0-plan.md`;
the single index of open items, owner words and by-catch is
`docs/reference/parked-items-register.md`. The standing rules of the earlier
journals continue unchanged and are cited from them by commit.

## Order for the next cycle (accepted)

1. **Definitions Set B** (deferred from the 2.4.0 cycle, preflight
   `definitions-set-b-preflight.md`):
   - (a) safe retirement of persistent images by reachability marking — the
     collector marks no images today, so a marking mechanism comes first;
   - (b) image-slot reuse on redefinition;
   - (d1) promotion of escaped transient callables to persistent
     publications, with the positive `funcall` row as its gate (lifts the
     designed refusal of top-level anonymous `lambda`);
   - the over-cap / `eval` capacity members.
   Air plan before any Seed: projected ≥ 4,113 bytes against the reserves
   below; a slice or Bank-5 owner has to be named.
2. **Comfort**, with its own planning and its own air budget.

Version numbers and the Ship/Publish words stay owner words.

## Capacity watch (the 2.4.0 release world)

| Owner | Free / floor |
|---|---|
| Ordinary text | 1,209 / 32 |
| E000 | 146 / 54 |
| Capture | 136 / 57 |
| Session region 0 / 1 / 2 | 1,351 / 140 / 872 |
| Unique overlay catalog | 63 / 64 used |
| Journal-prepare slice | 1,760 / 1,792 used |

## Owner rows still open on the release-candidate medium

From the [device report](release-candidate-device-report-2026-09-24.md);
none is claimed for 2.4.0:

- RUN/STOP inside a running form;
- cold power cycle (and the stopwatch feel of boot and typing);
- physical `C-x C-c` exit from the IDE;
- row H: Freezer mount of `RC240W.D81`, `m65d-remount`, compile/save/load/call;
- final SD readback from BASIC at rest:
  `python3 -B build/rc240-device-r1/tools/rc240.py readback`.

## Standing rules of the 2.4.0 cycle

- Identity gate for Lisp-plane cards (derived data admitted per family, with
  per-family proof).
- One Codex session per tree.
- A sealed full `check-host` with zero failed and zero tolerated targets
  before every Ship.
- Device expectations are calibrated in the emulator first.

## Journal

### 2.5.5: device session, ship-time layer — 2026-10-07

**Sealed check-host.** r1 on `c9a789fd` is green: exit 0, 4,701 s, HEAD unchanged, no changed file.

**Device session, 2026-10-07, owner at the physical MEGA65** (record:
`docs/planning/release-2.5.5-device-report.md`). `D255.D81` and `D255U.D81` uploaded and read back byte-identical.
Boot by stopwatch unchanged, 20 s plus 22 s. Typing in the IDE editor, owner: "Stark verbessert, Backspace immer
noch leicht verzögert, stärker wenn Taste gehalten wird". A held key gave 227 characters in 10 s in the editor on an
empty line and 202 at the `L65>` prompt (80-column screen); the reviewer reads both as the keyboard repeat rate,
which was not measured; no 2.5.4 device count exists. Two buffers with the physical RUN/STOP key (switches by hand,
RUN/STOP at idle) were complete after re-entry. Two buffers saved with `save-buffer-to` read back as expected after
the power cycle (files `12ONE`, `12TWO`); the 20x40 save took 4 s (2.5.4: 5 s) and is byte-identical to its source.
The product medium is unchanged after the session. Not done on the device: the keymap seam, the long checklist
rows, `$D703`, held-key counts at column 35 and line 20. The checklist said "40 columns per line"; the screen has
80, corrected in the session.

**Findings.** Backspace in the editor is still slightly delayed on the device, more so when the key is held. Side
finding, pre-existing and documented since 2.5.0: Return at the empty `L65>` prompt leaves Comfort; the owner finds
it surprising; a small card is proposed in the register (an empty Return stays in Comfort, leaving gets an explicit
way).

**Reproductions.** Both public-source reproductions equal the Final in ELF, PRG, LTO and D81. The merged bitcode of
the public replay differs from the Final's on the same host (same size), so "host-dependent" did not fully explain
the 2.5.4 difference; cause not investigated.

**Ship-time layer.** Release note and status documents with these results, device report and Before-Ship record,
document gates r2, Card-5 r3. Acceptance record with eight gates: Comfort rows, Backspace rows, the Comfort lane,
the measured editor key cost (new), the reviewed emulator rows, the GC session recorded as FAIL, device upload and
owner rows. Its status is `FAIL-GATE-RECORDED: gc-session`. Five changed routes ran as single sealed targets, all
exit 0.

**Owner word 2026-10-07** (after the session; asked: Ship and Publish of 2.5.5, and acceptance of the GC gate
recorded as FAIL as in 2.5.4 with figures identical to 2.5.4; recommendation yes to both): "Freigabe erteilt. Wir
folgen deinen Empfehlungen". Ship and Publish of 2.5.5 are approved and the GC gate is accepted as recorded.
Neither has been done.

The Backspace finding was part of the session summary the owner approved on;
the GC session was run on the Seed medium, which is byte-identical to the
sealed Final (only `pending32` was repeated on the Final itself).

### 2.5.5: Final sealed, pending32 settled, public authority, reproductions — 2026-10-07

**Final r1.** Sealed check-source on `bb238142`
(`build/card-255-check-source-final-r1`): exit 0, 3,985 s, HEAD unchanged, no
changed file. Final chain: probe, final, seal and seal check pass, one product
link. `build/card-255-final-r1`: D81 `4f0b76ad…245523b` and ELF `592b2c71…`
byte-identical to the Seed. One Seed link, one Final link.

**pending32.** The breakpoint timeout of one GC attempt is not reproduced: 0
of 5 fresh boots on the sealed 2.5.5 Final and 0 of 2 on the 2.5.4 Final, all
with identical figures (`build/card-255-gc-pending32-r1`). The failed attempt
shows the forced allocation inside `gc_collect` with the frame interrupt taken
at the breakpoint boundary: the emulator held the CPU at the first instruction
of the product's interrupt handler while the driver waited for the next
address. It is the only such stop among 50,320 breakpoint stops; how the
emulator produces the coincidence is inferred. Harness, not a product stall.

**Release layer (candidate time).** Release note `docs/releases/2.5.5.md` and
status documents, every device statement pending; the correction of the
2.5.4 statement (the editor is about 10 times, not 30 times, slower than the
REPL) in the status documents and as a dated line on the 2.5.4 note; the
published release text is not edited. Document-gate successors, Card-5 r2 and
a Card-5 product successor. Public-source authority `c2_v255_r1_public_*`:
same form as 2.5.4; Seed, Final and reproductions use one Fedora 45 host and
one pin set; 2.5.4 moves under the historical host pin rule, so the v252,
v253 and v254 routes no longer touch the live host; the residue rule is read
from the medium alone. `AUTOBOOT.C65` keeps six bytes of 2.5.4 slack that the
zeroing step does not cover; they are carried by the tail-repeat rule (2.5.3
precedent) and stated in the documents.

**Reproductions.** Two clean public-source reproductions give ELF
`592b2c71…`, PRG `7a6e6a51…`, LTO `0d01e16f…` and D81 `4f0b76ad…245523b`,
byte-identical to the Final. The merged bitcode differs from the Final's even
on the same host; it is recorded, not required. Seven document files changed
after the export (the pending32 sentence); none is a producer input, they are
allowed-delta rows as in 2.5.4. Ten changed routes ran as single sealed
targets, all exit 0.

**Open for the owner:** Ship and Publish for 2.5.5 and the acceptance of the
GC gate recorded as FAIL (two history stalls, as in 2.5.4).

### 2.5.5: Seed r1b, measured typing cost, emulator rows, Final tools — 2026-10-06

**Seed.** `c255_seed_continue_r1b.py continue` finished on the retained r1
link: `build/card-255-product-r1b`, medium `media-255/c255.d81` sha256
`4f0b76ad…245523b`, ELF `592b2c71…`, build id `0x43a72fbb`, `.text` 36,899 B,
residue 0.

**Measured typing cost** (`build/card-255-typing-measure-r1`; emulator, cycle
counter, 40.5 MHz; 2.5.4 control and 2.5.5 Seed measured the same day, seven
samples per point, medians without a collection):

| Point | 2.5.4 | 2.5.5 | Ratio |
|---|---|---|---|
| Insert, column 1 | 124.2 ms | 57.3 ms | 0.461 |
| Insert, column 20 | 137.1 ms | 57.3 ms | 0.418 |
| Insert, column 39 | 150.0 ms | 57.3 ms | 0.382 |
| Insert, line 20 | 153.5 ms | 57.1 ms | 0.372 |
| Backspace, column 20 | 119.7 ms | 60.4 ms | 0.505 |
| Return, 30 characters | 462.9 ms | 416.3 ms | 0.899 |
| Burst of 8 | 687 ms | 244 ms | 0.355 |
| REPL, key to glyph | 14.0 ms | 14.0 ms | 1.000 |

Every pass rule holds; the largest deviation from the prediction model is
2.3 %. Typing 60 single characters triggers 5 collections instead of 9; with
them the cost is 67 ms per key instead of 152 ms. A collection still costs
about 120 ms and the first key after entering the editor about 90 ms more, in
both versions. Not measured: the physical device.

**Emulator rows on the Seed** (`build/card-255-rows-r1`, reviews
`build/card-255-rows-r1-review-*`): the 14 new behaviour rows for lever L2
(several buffers, switch, exit, re-entry, save and eval of a buffer left by a
switch or after an abort) are reviewed and pass; one of them failed in the
first run through a driver defect (the key counter was read after the abort)
and passes in the rerun. Every 2.5.4 row keeps its status; the three known
rows stay red unchanged. In a boot with the user disk swapped in the STOPPED
line shares its row with leftover status cells; four isolated boots show the
same abort behaviour on 2.5.4 and 2.5.5.

**GC session on the Seed** (`build/card-255-gc-r1`): collections, allocations
per transition and both peaks equal the 2.5.4 Final in every scenario (the
scenarios drive the REPL line editor, not the IDE); headroom 43 cells; the two
history scenarios stall as before, so the gate is recorded as FAIL as in
2.5.4. One `pending32` attempt ended in a breakpoint timeout at collection
471; the rerun passed; cause not found. No scenario covers the IDE editor
under forced collection.

**Final tools** `c255_final_pins/final/replay/seal/final_rehearsal`, row and GC
drivers `c255_rows/emulator/gc_session`. Replay `build/final-255-prep/reviewed-r6`
(13,414 inputs, sha256 `b1ab7176…830b`), Final selftest 127 tests, rehearsal
phases pass with 0 compiles and 0 links. Three provenance rules of the replay,
each pinned and with negative controls: Fedora 44 host-tool hashes are
accepted in old receipts; the two 2.5.4 reproduction records and the 2.5.4
seal are pinned as records and not walked (the 2.5.4 worlds that 2.5.5
consumes are bound file by file); the two host-tool rows of the native
identity may differ by host generation. The replay binds the Python
interpreter: the host must not be updated before the seal.

### 2.5.5 Seed r1: halt after the link, reviewed continuation r1b — 2026-10-06

Pre-chain r1 on tools commit `26be6184` passed with the dry values. Seed r1
(`build/card-255-product-r1`) ran its 75 commands and the one product link and
halted in the inventory on `.lisp65_rt_c2d_00b`: the instruction pair at
`$C473` in `c2_stream_phase_00b` is back in the 2.5.3 order (`sta $0a` /
`clc`; the 2.5.4 baseline has `clc` / `sta $0a`), the mirror image of the
class reviewed in 2.5.4. `.text` is 36,899 B, changed `[]`, immediate only
`main`; no section moved or changed size; eight of nine differing sections
are explained by the existing rules. The order of this pair has now changed
with every build id; the code generator's reason is still not known.

Decision as in 2.5.4: one narrowly pinned reviewed class, no second link.
`c255_seed_continue_r1b.py` binds the retained r1 attempt and runs the
unchanged inventory, media and finish steps into `build/card-255-product-r1b`.
Two dry continuations give the same medium. A standing two-state class for
exactly this pair is proposed in `build/card-255-seed-continue-r1b/notes.txt`
and not implemented.

### 2.5.5: sealed check-source green, Seed tools — 2026-10-06

Sealed check-source on the source candidate `f6333f4a`
(`build/card-255-check-source-r1`): exit 0, 3,837 s, HEAD unchanged, no changed
file. `f6333f4a` is the source authority of the 2.5.5 Seed.

Seed tools `c255_*` (attempt r1, medium `media-255/c255.d81`), baseline the
2.5.4 Final r1. Dry chain green: only the ide image changes (15,223 to
15,081 B, sha256 `27bfa662…`), the other five images and all six packages are
byte-exact against 2.5.4; build id `0x43a72fbb`, SHELF 100,621 B, static code
50,759 B; immediate-shape prediction without a flag; exhaustive product-world
E3 with `c255_e3_product.py`: 0 violations in both shapes, the control fails
in both. Product seams: the two E3 seams of 2.5.4 and the two L2 seams.

Decisions. The reviewed commuting-pair class of 2.5.4 is not carried: the
2.5.4 baseline already holds that order; any unexplained instruction
difference after the link halts as before, and there is no probe link (one
Seed link, one Final link). Host tool pins are the Fedora 45 tools. Because
SHELF.BIN shrinks by two sectors, the unchanged packer would leave 729 bytes
of the 2.5.4 medium in two freed sectors and in the slack of the last sector;
they are zeroed by an explicit, asserted media step (no reader reaches them;
receipt `residue-zeroing.json`); two rehearsals give the same dry medium.
Pass rule for the measured typing row: insert at most 0.60 and Backspace at
most 0.65 of the 2.5.4 control in cycles, Return not slower, growth with column
and row at most 5 %, REPL within 1 %; more than 15 % off the model is a
review, not a pass.

### Owner word: 2.5.5 = typing in the IDE editor — 2026-10-06

**Scope (owner, 2026-10-06).** 2.5.5 is one card: make typing in the IDE
editor faster. Four levers on the Lisp plane, no native change (`.text` stays
36,899 B), E3 edit persistence and the key extension seam unchanged. A
dedicated self-insert path and a native code-object cache are later cards.

**Study** (`build/scope-editor-typing-r1/report.txt`). One plain insert at
line length 20 costs 5,553,702 cycles (137.1 ms) in 2.5.4. 73 % of it is
loading code objects: the VM has one 56-byte execution buffer, so every call,
tail call and return reloads; a call costs about 23,000 cycles before the
callee runs. 23 to 24 % is interpretation; screen work is three cells. A
printable key walked 24 base-table entries and 23 routes (48 tail calls), the
render path makes 35 calls for three cells, and the loop stored a flushed copy
of the buffer before every key (cost growing with column and row, two thirds
of the 75 cells allocated per key).

**Correction.** The typing comparison of 2026-10-05 said "REPL insert
4.17 ms" and, derived from it, "the editor is about 30 times slower than the
REPL". 4.17 ms is the time from the consumed key to the next input poll; the
glyph is on the screen 566,5xx cycles = 14.0 ms after the key is consumed
(`build/scope-editor-typing-r1/r2/repl-echo.json`). The editor is about
10 times slower than the REPL for the same visible effect, not 30 times. The
editor figures (124 to 150 ms) stand. The sentence in
`docs/project-status.md`, in `docs/planning/release-2.5.4-before-ship.md`,
the 4.17 ms in `docs/known-issues.md` and in the published
`docs/releases/2.5.4.md` still carry "30 times / 4.17 ms"; they are pinned or
published and are corrected with the 2.5.5 document layer, not in place. The
published release text is not edited.

**Levers** (`build/card-255-typing-r1/notes.txt`, patches per lever):
- L1: a printable code is the insert command before the base table is
  searched; the insert route stands first.
- L4: the routes of Backspace, Return and the cursor keys follow it. (The
  planned self tail call does not exist: `tailcall_self` is a check, the
  compiler emits an ordinary tail call; a `while` loop is unknown to the IDE
  eval oracle.)
- L3: the one-instruction accessors are written out as `car`/`cdr` in 21
  functions of the key path (72 call sites). `ide-event-command` keeps its two
  accessor calls: the keymap end-to-end gate mutates them.
- L2: the loop stores the buffer once at entry, not before every key. What
  is published per key is unchanged (the E3 publication before the next
  poll).

**Counted on the projected product world** (VM instructions / code-object
reads / cells per insert at length 20): 1,955 / 359 / 95 in 2.5.4,
921 / 145 / 39 with all four levers; no growth with column or row any more.
The read model equals the emulator's `vm_object_load` counts of 2.5.4 exactly
at six points.

**Predicted, not measured:** insert 137 ms to about 57 ms, Backspace 120 to
about 61 ms, Return on a 30-character line 463 to about 416 ms; one collection
per 10 to 11 keys instead of 5 to 6. The prediction is a two-parameter fit to
the 16 measured 2.5.4 emulator points (largest error 5.4 %). A medium with the
changed IDE image needs the native of a real link; the first emulator
measurement comes with the 2.5.5 Seed.

**Proof.** Product world of the final combination (ide image `27bfa662...`,
15,081 B, -142 B against 2.5.4). The E3 sweep was first run with the committed
2.5.4 tool and passed; that tool turned out to be blind in one place (below),
so the proof stands on its successor `c255_e3_product.py`: exhaustive, every VM
instruction boundary, `drain` shape 74,442 points and `run` shape 127,914
points, multi-buffer 10,056 and 27,871, no violation under either rule; the
no-abort text of every case equals the independent reference; the named point
`abc-after-last-poll` keeps "abc". Controls: without the publication 29,812 of
36,037 (`drain`) and 74,548 of 80,800 (`run`) points fail, multi-buffer 5,892
of 8,885 and 23,773 of 26,775; the no-copy control 3,601 in each shape. Every
key code maps to the same command and every command to the same route (2,379
rows per step).

**The E3 tool was blind in the `run` shape.** The 2.5.4 sweep took its
reference texts from the swept world itself; in the `run` shape they came from
the per-key store that L2 removes. In the control without the publication the
`run` shape then reported no violation although that world loses every
finished step, even at the idle prompt. The successor reads its references
from the stepped state, independent of every store, requires the no-abort
texts of the product world to equal them, and requires the control to fail in
both shapes at half of the points or more
(`build/card-255-typing-r1/control-analysis.json`, `notes-phase2.txt`).

**Gates.** Six gates bound the old bytes and have dated successors (keymap
entry point and receipt, exit key path with the source-parity gate, editor
allocation r6, function metadata r8, string codec workloads r4); Card-5 has
the successor `c2_v255_r1_card5.py`. New in check-source:
`c2-v255-editor-key-cost-check`, ceilings on what one editing key costs on
the host VM (library world). The allocation contract does not move; the
string codec workloads run 170 and 48 VM ops fewer.

### 2.5.4 published — 2026-10-06

Sealed check-host r7 on `6e78e898` is green (exit 0, 4,636 s, HEAD unchanged,
no changed file); the release contract r1 binds it. Before-Ship commit
`d7d04023`, proof commit `50550838`, tag `proof/v2.5.4`. The first seal attempt
stopped because the seal script refused the three absolute host-tool rows; the
successor `seal-after-commit-r2.py` checks them by the host rule and the seal
passed on the same commit, with the same four assets.

Published: public `main` `bdaf2dd96a6bf77d7a02cccdf0db148cefe914a1` with parent
`bf9d7c0c4eaeccdd5a4b0265b9e3f3e3b000d387` (no forced push), tag `v2.5.4`,
source projection `151eb121e664e11dc60e6920365b9a320f2b4717`, GitHub release
`v2.5.4` with four assets; draft and published state verified by download
(release body, assets, remote refs, source tree).

Known limits carried by this release: editor typing latency, type-ahead lost
while the editor opens, long `m65d-remount`, overdrawn recall of very long
history entries at the bottom of the screen, 3 cells and 88 bytes less heap
than 2.5.3, `$D703` not checked on hardware. Next cycle, by owner decision:
editor typing first, then sound as a disk package, kernel diet, graphics,
structure editor.

### 2.5.4: device session, typing comparison, GC session, owner decisions — 2026-10-06

**Sealed check-host.** r3 to r5 on `645d3243` were red for environment
reasons: the user quota of `/tmp` (12.8 GB, filled by another project's data),
and in r4 the reviewer's own redirection of `TMPDIR` into the repository,
which the sealed runner cannot serve. With `/tmp` freed (owner permission to
move the other project's directory to disk) r6 is green: exit 0, 4,767 s,
HEAD unchanged, no changed file.

**Device session, 2026-10-05, owner at the physical MEGA65** (record:
`docs/planning/release-2.5.4-device-report.md`). Media uploaded and read back
byte-identical. Boot by stopwatch 20 s to `Initializing` plus 22 s to the
prompt. The physical RUN/STOP key aborts a running form. Edit persistence:
text visible in the editor before RUN/STOP is complete after re-entry. Keymap
seam: `C-x f` unbound reports `UNKNOWN COMMAND`, bound it inserts the
character. IDE save of the 20 by 40 buffer: 5 s (2.5.3: about 38 s), the file
byte-identical to its source on host readback after a power cycle. Not done on
the device: the additional REPL rows, the large saves, the out-of-memory rows
and the `$D703` check.

**Device findings, none new in 2.5.4.** Typing in the IDE editor is clearly
slower than at the REPL; keys are not lost but appear late. Keys typed while
the editor is still opening are lost (entry resets the encoded-input counters;
code older than 2.5.3; type-ahead during evaluation was never claimed).
`(m65d-remount)` takes very long (package byte-identical to 2.5.3).

**Typing comparison in the emulator** (`build/card-254-ide-typing-r1`): editor
insert 122.3 to 148.0 ms per key in 2.5.3 and 124.2 to 150.0 ms in 2.5.4, a
constant 1.8 ms more per key (about 1.5 %); REPL insert 4.17 ms in both. A
collection of about 120 ms falls on roughly every fifth or sixth editor key in
both versions, and a burst is rendered once at its end in both.

**GC session on the sealed Final** (`build/card-254-gc-r2`, wrapper
`c254_gc_session_20261006.py`): six of eight scenarios pass without
out-of-memory; `return250` and `reopen-home-delete-refill250` completed for
the first time. `history10` and `history-home-delete-refill250` stall on a
display defect that the 2.5.3 records show identically: with the prompt at the
bottom of the screen a recalled 250-character entry is drawn over the rows
above without scrolling. Cursor keys, delete and Return work. Against the
2.5.3 Final every collection shows 3 more live cells and 88 more arena bytes;
the highest peak leaves 43 of 1,070 cells (2.5.3: 46). The reasoned cause is
the bounded result print. By its committed rules the gate is recorded as FAIL.

**Owner decisions.** 2026-10-05: the three device findings are released as
known limits; speeding up editor typing is the first card of the next cycle,
before sound. 2026-10-06: the memory price of 3 cells and 88 bytes is
accepted, and 2.5.4 is published with the GC gate recorded as it is.

**Ship-time layer.** Release note and status documents with these results,
Before-Ship and device report, document gates r2, Card-5 r5. Six changed
routes ran as single sealed targets, all exit 0.

### 2.5.4: sealed check-host on the new host, two follow-ups — 2026-10-05

Sealed check-host r1 on `5fb181fd` was red in four targets with one cause,
`dialect-v1 build compiler SHA drift`: both equivalence binaries under
`build/` had been built with the Fedora 44 gcc and survived the host move as
stale make products (make does not track the compiler). They were moved aside
and rebuilt by their own rules; no tracked file changed. After a host compiler
change the two equivalence receipt targets must be rebuilt before a sealed
run.

Sealed check-host r2 on the same commit was red in one target,
`dialect-v2-number-to-string-check`: the committed four-engine verdict pins
the hash of the live v2 equivalence binary, which the rebuild moved from
`335e11a9…` to `2d465206…`. Engine results, case, inputs and result are
identical. Successor `dialect_v2_number_to_string_v254_20261005.py` with the
receipt `four-engine-v254-20261005-verdict.json`: it fails on any difference
from the earlier verdicts other than that binary hash. Route retargeted,
Card-5 r4.

Outside every aggregate and not a host effect:
`dialect-v2-eval-apply-funcall-matrix` fails 6 of 40 runs, with the Fedora 44
binaries as well. It goes into the register with the ship-time documents.

Device: `D254.D81` and `D254U.D81` uploaded on 2026-10-05 and read back
byte-identical (`build/device-254-prep/upload-01`). The session is the
owner's; no result is recorded yet.

### 2.5.4: Final sealed, public authority, reproductions on a new host — 2026-10-04

**Owner word 2026-10-04.** Ship and Publish are pre-approved for 2.5.4. The
release chain, including the device session with the owner, stays the
condition; a device finding stops the publication and goes back to the owner.
Legacy stdlib suites: correct the record (done in the register). Order for
2.6: sound as a disk package, kernel diet, graphics, structure editor.

**Final r1.** Sealed check-source on `4dd1802e`
(`build/card-254-check-source-final-r1`): exit 0, 3,681 s, HEAD unchanged, no
changed file. Final chain: probe, final, seal and seal check pass, one product
link. `build/card-254-final-r1`: ELF `7b951eb9…`, PRG `192138eb…`, LTO
`e9d6dc85…`, D81 `250fdc76…ef5d`, all four byte-identical to the Seed. Link
budget kept: one Seed link, one Final link.

**Release layer (candidate time).** Release note `docs/releases/2.5.4.md` and
the status documents; every device statement reads pending. Successors of the
hash-pinned document gates, Card-5 r3, the 2.5.4 public-source authority
(`c2_v254_r1_public_*`, `config/c2-v254-r1-public-*`). The Lisp plane travels
as compiled manifests and blobs, which covers the projected product IDE with
its two reviewed seams; REPL-COMFORT and DEFSTRUCT travel in the same form and
are re-emitted from the public sources as a check. Accepted without exact
precedent: the slack rule that re-derives the 2.5.3 package index for four
residual `L65INDEX` bytes, and the DEFSTRUCT list-domain waiver as for
REPL-COMFORT. A permanent make route for the product-world E3 proof is not
part of this release; it is a card for the next source candidate.

**Build host moved to Fedora 45** on 2026-10-04, after Final r1 and before the
public reproductions (gcc 16.2.1, LLVM 23.1.2, util-linux 2.42.4, Python
3.15.0rc2). The Fedora 44 host tools are not restored. Final r1 was linked
with the Fedora 44 tools; the two public-source reproductions ran with the
Fedora 45 tools and reproduced ELF, PRG, LTO and D81 byte for byte. The merged
bitcode written by `/usr/bin/llvm-link` is a host-dependent intermediate
(Final host 250,796 B `728903b9…`, reproduction host 265,228 B `e2c2d6a1…`);
it is recorded, not compared.

**Rule "historical host pin"** (`tools/host-lisp/historical_host_pin_20261004.py`):
a host tool row of a past release is accepted when its recorded hash equals
the pin in that release's own committed reproduction policy; the live
`/usr/bin` binary is verified only for the current release (2.5.4,
`c2_v254_r1_toolchain.py`). The rule refuses the current release, a hash that
is not the release's own pin, and a missing record. Affected routes:
`v252-public-authority-check` and `v253-public-authority-check` (era readers
run unchanged under the rule; the live-host selftest is the 2.5.4 toolchain
tool; the 2.5.3 reproduction-gate selftest left the route, its receipt check
stays), `disk-r7-static-plane-check`, `disk-r7-media-check`,
`disk-r7-product-card5-check`, `v254-public-authority-check`. The Before-Ship
contract accepts the three sealed host tools as drift class "host". No
committed tool or receipt was edited. Three committed tools still fail when
called directly on the new host; no route calls them.

### 2.5.4: Seed r1b complete, emulator rows, Final tools — 2026-10-04

**Seed.** `c254_seed_continue_r1b.py continue` finished on the retained r1
link: `build/card-254-product-r1b`, medium `media-254/c254.d81` 819,200 B,
sha256 `250fdc76…ef5d`, ELF sha256 `7b951eb9…5244`, build id `0x829db958`,
`.text` 36,899 B, 0 unclassified bytes, product links of the attempt 1.

**Emulator rows on the Seed medium** (`build/card-254-rows-r1`, continuation
`build/card-254-rows-r1c`, review `build/card-254-rows-r1-review`):

- New 2.5.4 rows: 31 pass automatically, 30 capture-then-review rows accepted
  by the reviewer, no row fails. All 20 E3 abort points and both pending-C-x
  rows read `OK`; the E3 group and the keymap seam group ran in separate
  boots. The RUN/STOP stand-in is a monitor write to the break flag and is
  accepted for the emulator only; the physical key stays a device row.
- `$D703` probe: the write applied, the product survived a library load.
  Whether the emulator's DMA honours the bit is not shown.
- Regression: disk rows pass (including the 144-file remount row), comfort
  79 of 79, backspace 7 of 7, lanes measured.
- Not green, unchanged from 2.5.3: `ide-buffer-switch-two-keys` and
  `ide-save-100x20-keys` fail identically on the 2.5.3 Seed r8 control
  (harness expectation, the first one already recorded so in 2.5.3);
  `oom-repl-global` halts on the strict transport, and with the tolerant
  2.5.3 method the global list is still not released after 8 attempts, the
  2.5.3 r8 result. That row is not accepted; it stays a known behaviour.
- Run r1 lost its last sessions to a host transport fault, not to the
  product: the pinned headless emulator dies of SIGPIPE when the stock monitor
  command closes a connection early under host load. `c254_rows.py` now uses
  one patient connection per command, also for the legacy instruments, and
  counts lost groups as run errors.
- Product observation, same in 2.5.3: the IDE status row is not redrawn when
  its text equals the one drawn last, and old status rows stay on screen
  after an abort or `C-x q`.

**Final tools.** `c254_final_pins.py`, `c254_final.py`, `c254_replay.py`,
`c254_seal.py`, `c254_final_rehearsal.py`, `c254_gc_stress.py`,
`c254_emulator.py`, `c254_rows.py`. Receipts come from r1b, link coordinates
from r1; the continuation tool is pinned separately; the Final inventory runs
inside the reviewed pair class. Replay `build/final-254-prep/reviewed-r1`
(12,185 inputs, sha256 `291b347f…0021`), Final selftest 122 tests, rehearsal
phases pass with 0 compiles and 0 links.

### 2.5.4 Seed r1: halt after the link, reviewed continuation r1b — 2026-10-04

**Pre-chain r1** on tools commit `11da63b3` (authority `04294d56`): selftests,
preflight, exhaustive product-world E3 (381,706 and 52,091 points, 0
violations; controls fail with 170,774, 36,380 and 7,262) and the pre-link
rehearsal passed with the values of the dry chain (build id `0x829db958`,
SHELF 101,155 B, static code 50,901 B, no immediate flag).

**Seed r1** (`build/card-254-product-r1`): all 75 frozen commands ran,
including the one product link. The post-link inventory then halted:
`.lisp65_rt_c2d_00b` held a change no class explains. `.text` is 36,899 B,
changed `[]`, immediate only `main`; no section moved or changed size; error
call sites 51. The unexplained bytes are one adjacent instruction pair in
`c2_stream_phase_00b` at `$C473`: before `sta $0a` / `clc`, now `clc` /
`sta $0a` (bytes `85 0a 18` to `18 85 0a`, the `R_MOS_ADDR8 __rc8` relocation
moves from `$C474` to `$C475`). STA reads A and writes the cell, CLC writes
carry only; no symbol, branch target or inbound relocation lies in the three
bytes. The code generator's reason for the other order is not known.

**Decision.** The pair is accepted as one narrowly pinned reviewed class
(section, offset, both byte strings, both listings, relocation move, both ELF
hashes). No second link: `c254_seed_continue_r1b.py` binds the retained r1
attempt and runs the unchanged inventory, media and finish steps into
`build/card-254-product-r1b`; every other byte is still judged by the
unchanged rules. The link budget (one Seed link, one Final link) holds. The
Final replay must run its inventory inside the same class. Two dry
continuations gave the same medium (819,200 B, sha256 `250fdc76…ef5d`).

**Emulator rows.** Decisions for the row driver drafts
(`build/card-254-final-prep-r1`): all 29 rows with a device-dependent
expectation stay capture-then-review, none passes automatically; the monitor
write to the break flag counts only as an emulator stand-in, the physical
RUN/STOP row stays a device row; the E3 receipt keeps its own pin; the legacy
comfort, backspace and lane instruments stay as in 2.5.3.

### 2.5.4: sealed check-source green; E3 proven on the product world; Seed tools — 2026-10-04

**Sealed check-source r2** (`build/card-254-check-source-r2`) on `04294d56`:
exit 0, 3,412 s, HEAD unchanged, no changed file. `04294d56` is the source
authority for the 2.5.4 Seed. After that commit the plain sealed target
`lcc-nesting-ladder-check` also passed (exit 0, no read-only error).

**E3 on the delivered IDE** (`build/card-254-e3-product-r1`, repeated by the
Seed tooling in `build/card-254-e3-dry-r1a`): the harness world is the emitted
product IDE image itself (15,223 B, 204 objects, sha256 `84a7d3e4…a4aa`). With
the two product seams (publication before the product's `(poll-key)` in
`%ide-drain-pending`; `ide-event-command` reset in `ide`) an abort at every VM
instruction boundary keeps every finished step: 381,706 points and 52,091
multi-buffer points, 0 violations. Both controls fail as required: without the
seams 170,774 violations, without the Return copy 7,262. The Return copy, the
keymap seam, save fix A and the refusal of a save during a source load project
onto the product world without a seam. Decision D-E3: the seams are adopted.
The host proof does not cover aborts inside native primitives, during garbage
collection or at out-of-memory; emulator rows on the Seed and the physical
RUN/STOP row on the device remain required.

**Seed tools** (`c254_*`, attempt r1, medium `media-254/c254.d81`): the Seed
refuses to start unless the exhaustive product-world E3 receipt belongs to
its preflight, its tool bytes and the pinned authority, and unless the emitted
IDE image is the proven one. Native rule: `.text` stays exactly 36,899 B; the
pre-link prediction over 28 immediate sites reports no flag. Dry chain green:
build id `0x829db958`, SHELF 101,155 B, static code 50,901 B; changed images
stdlib-p0 19,860 B, ide 15,223 B, lcc 8,401 B; idex, m65d, buffer exact;
REPL-COMFORT 2,207 B and DEFSTRUCT 1,051 B re-emitted, all six package
envelopes rebound. The object-size limit applies to the stored object length
(`src/vm.c`, `len > 255`): `ide-split-line` and the largest REPL-COMFORT
object are 253 B, so each has 2 B left. Final-side tools follow after the Seed.

### 2.5.4: sealed run r1 red on one gate tool; correction on E3 — 2026-10-04

**Sealed check-source r1** (`build/card-254-check-source-r1`, HEAD `8bd8f1db`):
exit 2, HEAD unchanged, no changed file, one red target,
`lcc-nesting-ladder-check`. Cause: the committed receipt
`lcc-nesting-ladder-v254-20261003.json` binds
`build/lcc-nesting-ladder-v254-20261003-live/resident/suite.json` as an input,
the sealed runner mounts every bound path read-only, and the gate rewrites that
file on every check. Unsealed runs do not show this. No link was spent. Fix:
successor tool `lcc_nesting_ladder_v254_r2_20261004.py` writes only into a
fresh scratch directory and binds stable inputs (the frozen 2.5.3 preflight
resident suite and tracked sources); its ladder equals the 20261003 receipt on
all 35 shapes. Card-5 v254 r2. The committed 20261003 receipt and the Card-5 r1
pair stay as history. Before this commit the fix was run under the real sealed
runner through a wrapper that adds the still-untracked files to the protected
set (eight targets exit 0); the plain sealed target is re-run after the commit.
Rule from now on: a receipt never binds a path its own tool writes, and new
gate tools run once under the sealed runner before a full sealed run.

**Correction to the entry below.** The E3 abort-point sweep (8,425 points) and
the figure "ide 216 objects" describe the library world. The delivered IDE is
built from a frozen older world with 204 objects
(`build/card-253-preflight-r8/projection/ide/sources/`), which has no
`%ide-idle`, `%ide-init` or `%ide-poll`; of the five `lib/ide-ui.lisp` hunks
only `ide-bind-key` and route 14 project onto it. The E3 publication and the
pending `C-x` reset do not reach the product as committed
(`build/card-254-seed-prep-r1/plan.txt`, D-E3). Reviewer decision: keep E3 in
scope through reviewed product seams (publish before the product's
`(poll-key)` in `%ide-drain-pending`; reset `ide-event-command` in `ide`), on
condition that the abort sweep and its no-copy control are repeated on the
projected product sources and that the Seed tooling refuses to run without
that proof. If the product-world sweep fails, the Seed is not started and the
owner decides between 2.5.4 without E3 and a redesign.

### 2.5.4 scope and integrated source candidate — 2026-10-04

Owner word 2026-10-03: continue directly with 2.5.4. Basis
`build/scope-254-r1/report.txt`; reviewer decisions D1–D10: scope = E3
(each finished editing step is stored before the next key poll without
allocating; Return copies the typing list; a pending `C-x` is reset after
RUN/STOP), a lean IDE keymap/extension seam (`ide-bind-key`; an unbound
`C-x` + key shows "unknown command"; built-in keys cannot be overridden), the
closure fix (`(funcall (lambda …) args)` is compiled as the direct form; a
lambda stored at top level stays refused), save fix A (the save string is
built through the staging primitive; every IDE save is refused while a source
load is active — a direct `m65d-save` outside the IDE is not guarded),
`mapcan` beyond 12 results, arity checks for `eq`/`eql`/bit operations, and
three package corrections (bounded Comfort result output: depth over 8, more
than 1,100 conses or a cycle is refused; `defstruct` rejects colliding
generated names; recalled history with a comment submits at once). Native
code +0; 842 B are usable after `.text` in the 2.5.3 ELF. Deferred: save
fix B, `%m65d-mask` private-inline, all native items, block reclaim.

Further reviewer decisions during integration: the editor-allocation budget
is re-baselined for the E3 copy (wrap key 224/201 cells and two collections;
plain keys unchanged); the frozen Werkbank suites stay byte-identical and the
omission audit skips superseded suites; the directory headroom was restored by
folding the two new IDE helpers into their callers instead of lowering the
floors (ide 216 objects, headroom 38/32 as at `22ab180e`).

Three cards (`build/card-254-{ide,lcc,pkg}-r1`) merged in the tree
(`build/card-254-integrate-r1`, `-r2`). Host evidence on the merged tree: E3
sweep 8,425 abort points with 0 violations (the no-copy control fails as
required), seam 768 rows with 0 mismatches, save matrix 10/10, product-path
LCC probes 68/68, nesting ladder not below 2.5.3 on any of 35 shapes, P5
fixpoint green. Prices: ide +160, lcc +52, stdlib-p0 +46 code bytes;
REPL-COMFORT +112, DEFSTRUCT +13; estimated free code at boot about 6,718 B
(7,088 B in 2.5.3). New permanent gates `v254-package-suites-check` and
`dialect-v2-lcc-surface-v254-check`. Unsealed `make -k check-source` exit 0
(`build/card-254-integrate-r1/run4`). Two reds outside the release aggregates
are in the register. Next: sealed check-source, Seed tooling with package
re-emission, Seed, emulator rows, Final.

### 2.5.3 published — 2026-10-03

Public main `bf9d7c0c` (parent `fde9fb13`, tree `55303a9f`, exact source
projection `f572cbe6`), annotated tag `v2.5.3`, GitHub release published as
latest with four assets; draft and published readbacks PASS (release body,
downloaded assets byte-equal, remote refs, source tree). Private chain: Final r8
(D81 `7df9db67…`, ELF `5eb056e0…`), two public-source reproductions, sealed
check-host r8b on `88b2208b` green, device session passed, Before-Ship
`437beff3`; the first post-commit seal stopped before writing because the
acceptance record was missing from the reviewed source delta (delta r3 and
contract r4 in `547613a1`; aborted attempt retained as
`build/release-v2.5.3/r2-sealed-aborted-delta-20261003`); proof commit
`710fc69d`, tag `proof/v2.5.3`. Next: 2.5.4 per the owner's feature roadmap
(E3, small corrections, keymap/extension seam; the out-of-memory fix already
shipped in 2.5.3), then 2.6 (sound, graphics — needs a device-verified DMA
scratch area, the gap $17A0..$17FF is not free on the device — structure editor).

### 2.5.3 device session passed; owner word for Ship and Publish — 2026-10-03

[Device report](release-2.5.3-device-report.md): Final r8 medium `7df9db67…`
(ELF `5eb056e0…`), two rounds. Every executed acceptance group passed (49:
product disk 33, user disk 12, other-identity disk 1, leaked-block disk 1,
144-file disk 2), uploads read back byte-identical, owner physical rows 1 to 4
and 6 PASS (typing feel good), row 5 (physical `C-x C-s` on a 50x40 buffer)
SAVED but took several minutes, stopwatch boot about 43 s from `run` (tool
clock 42.8 s; 2.5.2: 40.9 s). Round 1 ended with a black screen after a Freezer
disk swap (cause unknown, not reproduced in three later swaps; the readback
proved every disk intact); round 2 ran after a power cycle with a fresh upload.
Documented table adaptations: the four `peek` forms of `lcc-f2-ladder` read the
scratch gap `$17A0..`, which is not zero on the device; phase O was re-ordered
after the fresh session (a save without a verified remount returns 8, correct
D2 behaviour; the swap test became remount of the other disk, then swap to the
144-file disk: 12, then 8). The exploratory DMA row aborted at its precondition
(gap not free, check 255): 2.6 needs another device-verified DMA scratch area;
line mode is untested. `oom-last`: message and returning prompt on the device,
reset required for data held by a global list. Not verified: the cause of the
black screen, `ide-save-cow-controls`, DMA line mode.

**Owner word 2026-10-03:** "Dann mach weiter. Freigabe für Ship und Publish
erteilt" — Ship and Publish of 2.5.3 are authorised (Final r8, after the passing
device session). Remaining: the Before-Ship record (new sealed check-host on the
documentation commit, contract, seal), proof commit and tag, source projection,
publication with readbacks.

### 2.5.3 r8: regression fixed, out-of-memory hang fixed; Final r8 sealed — 2026-10-03

The device-session pre-check in the emulator found a regression in Final r7
(`build/card-253-f1f2-compare-r1`): the new `setq` code cost one VM frame per
`setq` while LCC compiles, so ordinary forms such as
`(let ((s 0)) (dotimes (i 1) (setq s (+ s (peek 23 (+ 160 i))))) s)` failed with
`*** VM: STACK OVERFLOW` (2.5.2 compiles them). **Owner decision 2026-10-02:**
Final r7 does not ship; r8 = the nesting-depth fix plus the one-line
out-of-memory landing fix (`mem_oom = 0;` in the `repl()` setjmp landing), and
the native cap is raised slightly ("Obergrenze leicht anheben"): `.text` cap
+368 B over 2.5.2.

Source `ccc08061` (sealed check-source r8a green): nesting ladder over 35
shapes equal to 2.5.2 (new gate `lcc-nesting-ladder-check`), new host gate
`repl-oom-recovery-check`. Seed r8 (`build/card-253-product-r8`, tools
`b42aaade`): `.text` +340 B, changed exactly `eval_v2_workbench_service`
(+336), `main` (+2), `repl` (+2). Emulator rows on Seed r8
(`build/card-253-rows-r8`): F2 forms compile, ladder 12/12, the prompt returns
after `*** VM: OUT OF MEMORY` (plain REPL, IDE 100x40 save, 249-character line
with four IDE buffers); a heap filled by data still held (a global list) cannot
be dropped from the keyboard because typing itself needs memory — reset
required; closures capturing a `let` variable give `*** VM: BAD BYTECODE` at
the Comfort prompt (same in 2.5.2 and r7). Comfort 79/79, Backspace 7/7,
typing and boot equal to r7.

Final r8 (`build/card-253-final-r8`, sealed run
`build/card-253-check-source-final-r8` on `751973de` green): 75 commands, one
link, D81 `7df9db67…`, ELF `5eb056e0…`, LTO `0491996a…`, PRG `6bf9dbd5…`, all
byte-identical to Seed r8; seal PASS (11,088 bindings, 1,425 receipt copies),
`seal.json` `bb4a509f…`. Links spent for 2.5.3: r6, r7, Final r7, Seed r8,
Final r8. Next: release chain on r8 (documents — the out-of-memory hang is
now fixed, reproductions, check-host), device session (owner), Before-Ship;
Ship/Publish need the owner's word.

### 2.5.3 Final r7 byte-identical and sealed; owner decisions; feature roadmap — 2026-10-02

**Source authority** `fe248d46` (chain `63b3f580` → `29c2bdc4` → `c2f19de2` →
`94d4e89f` → `d1937e4b` → `fe248d46`): packed IDE join and `eval-buffer` source
root, `%set-macro` root, IDE buffer-switch/mark state, LCC multi-pair `setq`
(with `DROP` between pairs — an independent review found the stack leak), LCC
arity refusal on the product path (`lib/dialect-v2/lcc-profile.lisp`), `nth`
refusing dotted tails, D2 write enable only after a verified remount, D4
bounded mitigation (status 13, no reclaim), D3 lossless load, D5 full-directory
remount. Sealed `check-source` r3 on `ab4474e8` green.

**Seed.** r5 halted before any compile (the r7c recipe lists one input
twice); r6 linked and halted at the native cap: `.text` 36,559 → 36,897
(+338 B; only `eval_v2_workbench_service` +336 and `main` +2 changed; isolated
price had been +215). **Owner decision 2026-10-01:** accept +338 B, cap +352 B,
replacement Seed r7 with unchanged source. Seed r7 passed
(`build/card-253-product-r7`), ELF byte-identical to the r6 link. Links spent:
r6, r7, Final.

**Final.** Sealed `check-source` `build/card-253-check-source-final-r7c` on
`0a27db52` green (two earlier attempts died with a desktop-app crash, no
receipt, no link spent; long runs now start as systemd user services). Final
`build/card-253-final-r7`: 75 commands, one link, ELF `47519653…`, D81
`abc9bb49…`, all artifacts byte-identical to the Seed; seal PASS (10,758
bindings, 1,393 receipt copies), `seal.json` sha256 `c1f5d8cf…`.

**Emulator rows on the Seed medium** (`build/card-253-rows-r7`): Comfort 79/79,
Backspace 7/7, boot +4.4 % (43.3 s emulator time), typing +1.4 % mean (steady
state unchanged); new rows green for IDE save 20×40/50×40/100×20 with
byte-identical reload, `eval-buffer` 5/50 forms, `%set-macro` incl. forced GC,
`setq`, `nth`, buffer switch/mark and all disk rows. Arity refusal text is
`*** COMPILE FAILED%LCC-ERROR-INVALID-PARAMETER-LIST`.

**Known issue, owner decision 2026-10-01:** after `*** VM: OUT OF MEMORY` the
prompt never returns (`mem_oom` is never cleared on the abort path). Present in
2.5.2 as well (`build/card-253-oom-hang-r1`); 2.5.3 only raises the size at
which a save runs out of memory. Documented in 2.5.3; the one-line fix in
`src/repl.c` is the first item of 2.5.4.

**Other reviewer decisions:** D2/D4 accepted at +298 B m65d (guideline was
about 300 B); structural native attribution for the Seed; legacy pre-1.0
padded files show their padding after D3 (release-note item); `mapcan` beyond
12 arguments stays a known issue.

**Feature roadmap, owner word 2026-10-02 ("Empfehlungen angenommen")**, basis
`build/feature-prestudy-r1/feature-prestudy.txt`: 2.5.4 = OOM fix, E3, two or
three small corrections, a general IDE keymap/extension seam, and a measurement
of the code space loaded packages consume. 2.6 = sound, then graphics, then the
structure editor, all as loadable disk packages, none loaded by default.
Graphics 320×144 in 256 colours without native code (320×200 after a kernel
diet); no GPL code copied from brilliance65 (methods and parameters only);
structure editor text-based on the line buffer; keys `C-x` + letter; packages
`m65-gfx` / `m65-sound` with `gfx-`/`snd-` function names; sound blocking in
2.6 (tick hook or IRQ player is its own card); a native `%dma` primitive only
after a diet and a device measurement; the DMA line-mode device check joins
the 2.5.3 device session.

**Open before Ship:** release documents, public-source reproductions, sealed
check-host, device session (owner), Before-Ship; Ship/Publish 2.5.3 need the
owner's word.

### 2.5.2 published — 2026-09-30

Public main `fde9fb13` (parent `2817f0cf`, tree `78458839`, exact source
projection `52a59370`), annotated tag `v2.5.2`, GitHub release published as
latest with four assets; draft and published readbacks PASS (release body,
downloaded assets byte-equal, remote refs, source tree). Private proof commit
`054ab18d`, tag `proof/v2.5.2`; contract sha256 `ca4ac8ae…`. Next: 2.5.3 per
the scope decisions above (IDE save heap, eval-buffer GC root, LCC setq and
argument checks, set-macro fix).

### 2.5.2 Before-Ship prepared; sealed host run green on the third attempt — 2026-09-30

Public-source reproductions (option A): two clean roots from the export,
`build/release-v2.5.2/repro-r3-1` and `repro-r3-2`, ELF/PRG/LTO/D81 byte-equal
to the Final `ae4e2931…`. Sealed `make -k check-host`: r1 on `ec4a279a` red
(`workbench-private-inline-composition-probe` pinned the m65d suite SHA that the
directory-link fix changed; dated successor receipt, Makefile route, Card-5
receipts r4 in `6f2cbe99`); r2 on `6f2cbe99` red (`workbench-ux-harness-selftest`
timed out at 30 s under `ionice -c3` beside a foreign profiling job; 19 s idle);
r3 on the same HEAD green (`build/release-v2.5.2-check-host-r3`, exit 0, 3,824 s,
0 changed files). Timeout not changed: watch item in the register. Before-Ship
document `release-2.5.2-before-ship.md`, target-acceptance record, reviewer
adapter receipts for the device gates and the release contract are prepared for
review. The acceptance record asserts named fields only: the forced-GC harness
receipts are all HALT and the comfort rows are split over three receipts
(stated in the document). Next: commit the explicit path list, pin the contract
hash, run `seal-after-commit-r7c.py --final`, then package and publish as
separate steps.

### Owner word: 2.5.2 with full release discipline (option A) — 2026-09-30

The r7c product changes the whole static plane, so the 2.5.1 public
reproduction path (library-only packer) does not carry over
(`build/release-v2.5.2/step3-report.md`). Owner chose **option A**: two clean
independent reproductions from the public source export, which needs a new
standalone public packer for all 20 media payloads plus the v252 public
tools, docs/naming/keymap successors and the Card-5 chain (estimate 1–2
working days). Option B (publish with the Final replay as the independent
rebuild, no public-source reproduction) was declined.

### Owner word: 2.5.2 Ship and Publish — 2026-09-30

"2.5.2 Mein Wort: Ja" — the full 2.5.2 chain including Ship and Publish is
authorised (after the passing device session). Final: `build/o2-lite-final-r7c`.

### 2.5.2 device session PASS — 2026-09-30

[Device report](release-2.5.2-device-report.md): Final medium `ae4e2931…`
uploaded fresh after a power cycle; 21/21 automated groups, owner physical rows
PASS ("Tippgefühl ist sehr gut"), directory-link fix confirmed on a real user
disk (F8 survives saving F0 in entry 0; readback verified). Remaining for the
release: Before-Ship, Ship and Publish — **Ship/Publish of 2.5.2 need the
owner's word**. Also recorded: GC stress (forced collection at every
allocation) showed no OOM but up to 1,009/1,071 live cells in the 250-char and
reopen+refill scenarios; the harness is too slow near a full heap to finish
all scenarios (watch item for 2.5.3).

### 2.5.2 Final (Seed r7c) byte-identical and sealed — 2026-09-30

Sealed check-source `build/o2-lite-check-source-r7c-final-r3` on `c4711ed2`:
exit 0, 3,389 s, HEAD unchanged, 0 changed protected files. Final
`build/o2-lite-final-r7c` (one product link, media re-derived without the Seed):
D81 `ae4e2931…`, ELF `4edcc037…` byte-identical to Seed r7c; seal PASS
(9,528 bindings) and seal check PASS. Content: O2-lite (reopen previous line,
admission limits, r6 review repairs), editor slot walks (Comfort typing
1,635,493 → 1,130,909 cycles/key, −30.9 %), `%rl-end` Return heap fix,
directory-link fix in `%m65d-dir-fill`. Emulator on r7c: lite rows 79/79,
backspace rows 7/7. Independent reviews: 2.5.2 candidate diff "freigabefähig",
r7c medium "all deviations explained", Final tooling hardened (F1–F4) and
fixed (r3). Way there: Seed attempts r7/r7b halted on tool issues (retained);
sealed runs final-r1 aborted (uncommitted tree), final-r2 red (replay bound
gate-rebuilt build outputs; fixed in `c4711ed2`). Open: owner device session
(`build/device-252-prep/runbook.md`), then Before-Ship/Ship/Publish — Ship
and Publish of 2.5.2 need the owner's word.

### 2.5.3 scope decisions (delegated to the reviewer) — 2026-09-30

Owner delegated the open 2.5.3 decisions ("Die offenen Entscheidungen überlasse
ich dir"). Basis: `build/scope-253-r1/report.md` (deduplicated inventory,
architecture classes A1–A8, prices) and the architecture review.

- **Scope (one Seed / one Final):** A1 object lifetime — packed IDE join
  (save/eval without whole-buffer list, `build/ide-save-heap-fix-r1/`),
  `eval-buffer` reader-source root (F1), `%set-macro` temporary-name root (F2);
  A2 IDE state — single-buffer switch text loss, stale mark positions;
  A6 LCC multi-pair `setq` (and builtin argument counts if confirmed on the
  product path); A5 disk D2 ownership check before write enable, D3 lossless
  load (trailing spaces/empty lines/CR), D5 full directory remount.
- **D4 (leaked blocks after aborted saves):** 2.5.3 gets the **bounded
  mitigation** only (diagnose inconsistent allocation, refuse further writes on
  unsafe media); the permanent reclaim is a separate 2.5.4 design/repair card.
  Reason: no content loss is evidenced (195 cut points), and a correct reclaim
  needs its own ownership design; bundling it would break the one-cycle budget.
  This replaces the earlier "D4 fix in 2.5.3" wording.
- **Native growth:** 2.5.3 may grow native `.text` by at most **+256 B**, only
  for the F2 fix (measured isolated +215 B, +1 B metadata); no BSS growth.
  No kernel diet in 2.5.3 (VM changes would add risk to a correctness
  release). Colour RAM (+49 B) and the STOP cursor remnant (+354 B) are
  deferred until a 2.5.4 kernel-diet card restores headroom (diet 2/3 found
  −689 B .text in total).
- **Stop rule:** if the candidate does not close D2 or does not fit before the
  Seed, halt cleanly before the Seed and re-scope; no series of attempts.

### Disk review results (partial) and Seed r7 scope — 2026-09-29

The independent disk/recovery review was repeatedly interrupted by Codex's
cyber-safety check and produced no final report; the reviewer evaluated its
recorded data (`build/external-review-disk-integrity-r1/matrix-results.json`,
`supplement-results.json`): 195 injected cut/fail points over 8 save
transactions — no content loss (old or new file always intact), 33 points
leave 1–3 leaked BAM blocks; 17 edge cases (full disk, full directory,
empty, oversize, retry after aborted claim) handled; the only real defect is
the entry-0 directory link (fixed). Loader drops trailing spaces, trailing
empty lines and CR. RUN/STOP recovery part not completed. Owner words:
**Seed r7 = O2-lite + directory-link fix**; leaked blocks and loader
whitespace are known issues in 2.5.2, fixes in 2.5.3.

### Directory-chain defect found; owner: fix it in 2.5.2 — 2026-09-29

Independent disk review (in progress, `build/external-review-disk-integrity-r1/`):
`%m65d-dir-fill` (`lib/m65-disk.lisp`) zeroes all 32 bytes of the target
directory entry, including bytes 0–1, which for entry 0 of a directory
sector hold the link to the next directory sector. Saving into entry 0 on
a disk with more than one directory sector cuts the chain: later files
disappear from the directory while save reports success (data blocks and BAM
stay allocated). Present since the copy-on-write persistence commit
`34d3c4ee` (all releases since 1.0.0, incl. published 2.5.1). Fix: zero
only bytes 2–31. Owner words: **fix in 2.5.2** (new Seed r7, new sealed
run); the running sealed check-source r3 on `d425eb87` was stopped as
superseded; the Final waits for the complete disk review.

### GC-root review: eval-buffer can silently stop early; owner keeps fix for 2.5.3, directly after 2.5.2 — 2026-09-29

`build/external-review-gc-roots-r1/report.md`: (F1, blocking, in 2.5.1)
`eval-buffer` passes an unrooted joined source string to `%cs-read-open`; a
GC during compilation reuses it — host native probe reads 1 of 5 forms with
no error. (F2) `%set-macro` may reuse a collected temporary (gensym) name.
(V1, conditional) an aborted C2 root scan does not prevent the sweep.
Candidate fix `build/ide-save-heap-fix-r1/` roots the reader source.
Owner words: **stay with 2.5.3**, started **directly after 2.5.2**; 2.5.2
release notes carry the known issue incl. the silent partial evaluation.
2.5.3 scope: IDE save/eval without whole-buffer list + reader root (F1) +
`%set-macro` (F2).

### IDE save/eval heap defect confirmed; owner: known issue in 2.5.2, fix in 2.5.3 — 2026-09-29

Independent review `build/external-review-ide-save-heap-r1/report.md`
(host measurement): IDE save (`C-x C-s`) and `eval-buffer` join the whole
buffer into a cons character list (`lib/ide-disk.lisp` `%ide-join-codes-into`
/ `%ide-join`); 50 × 40 chars need ~2,207 cells against ~588 free, so
save/eval fail with `*** VM: OUT OF MEMORY` beyond roughly 20×20, 10–12×40
or 6–7×70 (before any disk write; file and buffer kept). `eval-buffer` also
does not root the reader source string. Present in published 2.5.1.
Owner words: **known issue in the 2.5.2 release notes, fix in 2.5.3**.
Candidate fix study: `build/ide-save-heap-fix-r1/`. Same day, the O2-lite
review (`build/external-review-o2-lite-r1/`) found a blocking reopen heap
case (Home + Delete + refill: 784 cells); Seed r6 fixes it before the Final.

### O2-lite host closure reviewed; owner accepts admission limits; STOP remnant = follow-up card — 2026-09-29

`build/multiline-lite-r2/` (not committed): library 2,864 B (≤ 3,000),
shared resident/native +0; 31 + 7 baseline + 14 admission host rows PASS;
worst case 1,056/1,072 heap cells and 5,846/9,344 arena bytes including a
measured runtime reserve (483 live cells at the empty Comfort prompt).
Owner words: **accept the weighted admission contract** — pending form
≤ 32 lines / 640 B, active line `floor((500−3N)/2)` (250 → 202 at 32
lines), history keeps only forms ≤ 250 B (`*** input limit`,
`*** history limit`). **STOP remnant fix** (`build/stop-remnant-r1/`:
+141 B shared resident, clears all reverse video on reentry) becomes a
**separate follow-up card**; seek a narrower cursor-only fix there.
Next: O2-lite successor Seed per `build/multiline-lite-r2/seed-plan.md`.

### Multi-line editing: owner chooses O2-lite; STOP cursor remnant as own card — 2026-09-29

O2 round 2 (`build/multiline-proto-r2/`): 5,278 B library (+278 B shared
resident), over the 3,000 B ceiling; no cosmetic cut closes the gap.
O2-lite (`build/multiline-lite-r1/`): 2,446 B (+1,386), shared resident
and native +0, ordinary typing −37 instructions/key, 31/31 host rows.
Owner words: **implement O2-lite** (Backspace at an empty continuation
reopens the previous line; marker `[edit previous line]`, corrected line
re-echoed, old transcript kept; Up/Down stay history); a proven form
admission bound precedes the Seed. **Fix the inherited STOP remnant**
(stale reverse cursor after RUN/STOP following Home on a wrapped line,
reproduces on 2.5.1) as its own small card, may ship together.

### Multi-line editing: O2 prototype r1 reviewed; owner: round 2 + O2-lite, bound ≤ 3,000 B — 2026-09-29

Host prototype `build/multiline-proto-r1/` (not committed): behaviour 70/70,
ordinary typing/Backspace −6…−14 % VM instructions, native/shared resident
+0; but library 1,060 → 4,667 B (+3,607; package +5,851), heap RED
(per-character cons chains for retained lines vs a 1,072-cell heap),
cross-line keys 35–90 k instructions, multi-line wrap repaints the whole
viewport, one STOP cursor-cleanup gap. Not Seed-ready; no bound requested.
Owner words: **round 2 of O2** (compact inactive lines, form admission
limit, dirty-row repaint, STOP cleanup, reuse resident editor primitives)
**plus an exact O2-lite price** as fallback; **Comfort library ≤ 3,000 B**
is the owner's worth-it ceiling for O2.

### Multi-line editing: owner decisions after preflight — 2026-09-29

[Preflight](multiline-editing-preflight.md). Owner words: the complaint
meant **lines after Return** (continuations), not soft wrap; scope **O2**
(Backspace at true column zero joins the previous line; Up/Down move
inside the pending form; Return on an earlier line advances, submit only
from the last line when balanced); history is entered **above the first
visual row** or at a fresh empty prompt, an empty continuation stays in
the form, Down returns to the saved draft; **host price prototype first**,
then the reviewer presents the revised library bound for approval before
any Seed. The 1,100 B STRINGS bound stays sealed for its era.

### 2.5.1 PUBLISHED — 2026-09-29

[Publish report](release-2.5.1-publish.md). Public main `2817f0cf` (parent
v2.5.0 `07491638`), tag `v2.5.1`, release latest, four assets read back
byte-identical from draft and published release. Local `proof/v2.5.1` →
`09140968`. Open: stopwatch cold boot, physical RUN/STOP, physical C-x C-c
(known issue). Next: multi-line editing card (preflight; owner word for the
surface change), then the code-object cache decision after re-measurement.

### 2.5.1: sealed host r4 green, device and owner rows PASS; Before-Ship r3 — 2026-09-29

[Before-Ship](release-2.5.1-before-ship.md) and
[device report](release-2.5.1-device-report.md). Sealed full host r4 on
daa35d52: exit 0, 3066.871 s, zero protected/artifact drift. r2/r3 codec
reds converted by dated successors (four then six changed input bindings,
measurements unchanged). Strings Final and both repro-r2 runs agree.
Fresh S251.D81 readback and 13/13 automated device rows passed; owner
physically confirmed the string example, C-x q, and improved typing and
Backspace feel: "Alle manuellen Tests erfolgreich. Tippgefühl bei normalem Tippen und Backspace erheblich verbessert".
Stopwatch cold boot and physical RUN/STOP remain pending; physical C-x C-c
is still a known issue. Multi-line editing follows 2.5.1; continuation
lines cannot be edited after Return and Up/Down walk history.
Scope includes C-x q, Backspace tail, list walks (measured native typing
3.24 M → 1.58 M cycles/key, ~80 → 39 ms) and multi-line strings.
Named Comfort cost remains accepted. Reviewer commits the documents before
post-commit r3 sealing and the delegated Ship/Publish chain. Preparation
makes no Git writes and does not claim publication.

### Comfort multi-line string fix: host closure — Final byte-identical, sealed check-source r4 green, seal PASS — 2026-09-29

Report: [strings-final-report.md](strings-final-report.md). Seal:
`strings-final-20260929.json` (4,031 bindings, sealed at `fac1c746`).

The first seal attempt could not be committed: one receipt copy (the Seed
`inventory.json`, 60 MB) exceeded the 50 MB Git blob limit. The seal tool
now stores such copies as deterministic gzip next to the binding of the
uncompressed source, and the seal was re-taken on the same HEAD. The
uncommitted first attempt is kept in `build/strings-seal-superseded-r1/`.

**Fix:**
- The line scanner carries the in-string state across continuation lines.
- Auto-indent is suppressed inside strings.
- `%rl-end` echoes continuation rows. This also fixes a latent
  indented-row case.

**Numbers:**
- Rows: 72 / 72 (the owner's example, three lines, `\"`, parens inside a
  string).
- Library 1,060 / 1,100. Plane +204 against a cap of +250.
- Proven overlay drift: Session record 22 free 548 → 542, Boot record 4
  90 → 89.

**Budget history:**
1. Seed 1 linked, but its rows showed a display defect.
2. The replacement halted before the link (producer).
3. The card was rebound with a full-derivation probe and linked.
4. Four sealed runs, all converting consumer or environment reds.

**Lessons:**
- Consumers must be verified under reproduced sealed conditions
  (read-only bind mounts), not only directly.
- Seals must never be edited after sealing.

Next: the 2.5.1 chain on the strings Final (docs, reproductions, sealed
`check-host`, device session with the owner, Before-Ship, Ship and
Publish).

### Comfort string fix: replacement Seed halted before the link (producer); rebound once with a probe that derives the full command set — 2026-09-29

The first Seed (`build/strings-product-r1`) linked and passed price,
inventory and media. Its rows found a display defect: a continuation row
at indent 0 vanished or was overwritten. The fix is in `%rl-end` (`f31f79da`,
+46 Bank-2 bytes); the plane cap was raised to +250 (reviewer decision;
measured +204, Bank-2 free 10,751).

The replacement Seed (`build/strings-product-r2`) halted in
`derived_commands` with "frozen stdlib header not reproduced". This was a
producer defect, and no product link was made.

**Reviewer decision under the delegation:** because the fix unblocks users
of the published 2.5.0, the card is rebound once (1 Seed + 1 link, into
fresh directories). The condition is that the budget-free command-probe
must derive the complete command set, including the stdlib header
reproduction, so that such a defect fails before any budget is spent. A
further red parks the fix, and 2.5.1 then ships with the known issue and
its workaround.

### Editor list walks: host closure — Final byte-identical, sealed check-source r3 green, seal PASS — 2026-09-28

Report: [walks-final-report.md](walks-final-report.md). Seal:
`walks-final-20260928.json` (3,966 bindings, sealed at `a0caffea`).

- **Typing (measured lane):** 3.24 M → 1.58 M cycles per key (≈ 80 →
  39 ms) at the native prompt.
- **Backspace (projected from read counts):** 1,233–1,773 → 53 reads per
  key.
- **Price:** native `main` −2 (proven); plane +374 within +400; resident 0.
- **Rows:** 66 / 66 and 7 / 7.

Next: the Comfort multi-line string fix (overlay prepared in
`build/string-scan-r2/`).

### Owner findings at the device: multi-line strings hang Comfort; continuation lines not editable; owner word — string fix in 2.5.1, multi-line editing as a later card — 2026-09-28

The owner reported that `(print "hello` + Return + `     world")` never
evaluates.

**Cause:** `%ide-line-net-depth` (`lib/sexp-depth.lisp`) tracks a string /
escape / comment state while scanning, but returns only the depth. The
continuation then restarts in the normal state, so the second line's `"`
opens a new string and its `)` stays inside that string. The depth stays
1 forever, and an empty line does not end the continuation.
- The workaround is a line with just `)`.
- **Published 2.5.0 is affected** (Comfort is the default REPL).
- The native `lisp65>` reader has no continuation lines; IDE indentation
  can be wrong but does not hang.

The owner also noted two design limitations of the line-committing
Comfort:
- Backspace at the start of a continuation line cannot join the previous
  (already committed) line.
- Cursor Up/Down always walks the history instead of moving between the
  input's lines.

**Owner words:**
1. The string fix is a small card inside **2.5.1**.
2. Ship 2.5.1 with C-x q, the list walks and the string fix, plus honest
   known issues: continuation lines are not editable after Return, Up/Down
   always walk the history, and the 2.5.0 multi-line string hang with its
   workaround.
3. Then a separate card "multi-line editing in Comfort" (design and price
   preflight; its surface change needs the owner's word; the library bound
   of 1,000 bytes must rise).

### Editor list walks: plane bound raised to +400 (reviewer decision); consumers and producer prepared — 2026-09-28

The measured aggregate plane growth is **+374 bytes**: `CODE.BIN` +207,
`SHELF.BIN` +167 (metadata). The card's own bound was +256; the
preflight's +206 counted bytecode only. The Bank-2 static owner keeps
10,799 bytes free, and resident stays 0 bytes.

**Decision under the delegation:** the owner's bound covered resident
bytes only. About 0.6 % of the Bank-2 plane buys a projected ≈ 3× (insert)
and ≈ 20× (Backspace) keystroke latency reduction. The aggregate bound is
+400; per-file bounds stay at 256. Consumer successors, Card-5 (v251 walks)
and `tools/host-lisp/walks_seed_producer.py` are prepared (Codex); one
unrelated legacy LCC diagnostic stays red, as documented in
`build/walks-r3/prep-report.md`.

### Editor list walks preflight: Backspace ~1,200–1,800 reads/key → ~53; owner word — include in 2.5.1 — 2026-09-28

Preflight: `build/editor-walks-r1/preflight.md`. The patch uses direct
state-slot access, cached predecessor links and cursor-pointer reuse.
Price: +206 Bank-2 bytecode bytes, **0 resident bytes**. Projected ms per
key, native prompt at line end, before → after:

| Key | 10 chars | 70 chars |
|---|---|---|
| Insert | 64 → 21 | 64 → 21 |
| Backspace | 343 → 23 | 493 → 23 |

Comfort at 70 chars: insert 56 → 15, Backspace 470 → 18. All suites and 96
framebuffer-equality pairs pass. These are projections from measured read
counts, not device timings.

**Owner word:** include this card in **2.5.1**, which now waits for it. The
sealed `check-host` r1 on `2f732e95` (exit 0, 3,064 s, 0 changed)
qualified the pre-walks candidate and is superseded for the release.

### Owner word: keystroke latency — editor list walks first, then re-measure before any cache — 2026-09-28

The cache preflight (`build/code-object-cache-r1/preflight.md`) found:
- The VM has a single 56-byte execution window, so every foreign call and
  return reloads fragments: 263 `vm_object_load` reads per key at
  `lisp65>` and 278 at `l65>`.
- `nthcdr` (126 reads) and `%length-from` (51 reads) walk the line on every
  key already at 10 characters, and their cost grows with line length.
- The pinned Bank-2 cache (option B: 252 resident bytes, 1 KB Bank-2) would
  save an estimated 0.6–1.2 M of 3.2 M cycles per key.

**Owner word:** first remove the per-key list walks in the line editor. It
should maintain length and cursor tail incrementally (Lisp plane, 0
resident bytes). The cache is decided only after a re-measurement.

### Owner word: keystroke-latency preflight now; resident price bound ≤ 256 B — 2026-09-28

The keystroke attribution (`build/keystroke-latency-r1/attribution.md`)
measured about 3.24 M cycles per key (≈ 80 ms) at the prompt:
- **≈ 70 %** goes to code-object reload and materialization
  (`c2_map_cpu_read` 27 %, `vm_object_load` 17 %,
  `c2_product_entry_record` 14 %, materialize 7.5 %, C2D reads);
- ≈ 22 % is VM interpretation;
- screen, keyboard, KERNAL window and GC together are below 1 %.

2.4.0 behaves the same. Batched keys amortize the cost (≈ 0.58 M cycles
per key at batch 8). The Backspace card had cut interpretation only, which
explains the owner's "barely improved".

**Owner words:**
1. Start a product-free **preflight** for caching the editor's code
   objects now, in parallel to 2.5.1.
2. Resident price bound **≤ 256 bytes**. Bank-2 and Attic may carry the
   bulk.

The card itself is decided after the preflight, with measured numbers.

### Owner word: 2.5.1 release — full chain including Ship and Publish delegated — 2026-09-28

On the reviewer's question, the owner said: "Mein Wort: Ja". The reviewer
takes 2.5.1 (2.5.0 + C-x q + Backspace) through the release chain: docs,
two public reproductions, a sealed `check-host`, the device session on a
fresh medium, Before-Ship, **Ship and Publish**.

### Backspace latency: host closure — Final byte-identical, sealed check-source r2 green, seal PASS — 2026-09-28

Report: [backspace-final-report.md](backspace-final-report.md). Seal:
`backspace-final-20260928.json` (3,361 bindings, sealed at `803189a4`).

- The delete path reuses `(cdr before)`.
- VM instructions per Backspace fall by 7 %, 19 % and 26 % at 10, 40 and
  70 characters.
- Native price is 0; `CODE.BIN` −6 and `SHELF.BIN` −6 bytes.
- Rows 7 / 7 at both prompts. Media D81 `a2872fbd…`.

The world 2.5.0 + C-x q + Backspace is ready for a 2.5.1 candidate. Open:
the Backspace typing feel on the device (a fresh-upload session), and the
2.5.1 release chain (docs, reproductions, sealed `check-host`,
Before-Ship). Ship and Publish were delegated for 2.5.0 only; 2.5.1
needs a fresh owner word.

### IDE key exit UNBLOCKED: device session PASS on a fresh medium — 2026-09-28

[Device report](ide-exit-device-report.md). `IX250B.D81` was a fresh upload
after a power cycle and booted to `l65>` in 40.7 s. C-x q exits to `l65>`
in 1.7 s, re-entry keeps the buffer, a plain `q` inserts, and RUN/STOP in
the editor produces exactly one `*** stopped (run/stop)` before `l65>`.
The block is lifted. The card is host-closed and device-confirmed (virtual
matrix); physical keys stay with the owner.

The world 2.5.0 + C-x q is a release candidate for a later 2.5.x, bundled
with the Backspace card.

### Staging-lifecycle discriminator PASS: fresh 2.5.0 upload boots green — 2026-09-28

The owner power-cycled the device. `CD250B.D81` was uploaded as a new
file, with a byte-identical readback of `137bfa51…`, and booted via BASIC
to `l65>` in 40.7 s; `(+ 4 5)` → 9
(`build/ide-exit-device-r1/discriminator-250-*`).

The disk errors of the IDE session are therefore the known 2.0
staging-lifecycle class, caused by warm resets and re-mounts of already
staged media. They are no product defect of 2.5.0 or of the IDE card.

**Device-driver rule from now on:** no warm reset (`m65 -F`) of a mounted,
staged product medium. Every product boot uses a fresh upload under a new
name after a power cycle, as in the 2.0 choreography. Next: the IDE-exit
medium as the fresh file `IX250B.D81` with the C-x q rows.

### Disk error reclassified as the known staging-lifecycle class (not an IDE-exit or 2.5.0 product defect, pending the fresh-upload discriminator) — 2026-09-28

The control on `CD250.D81` (2.5.0) **also** failed to boot (red border,
`L65SYS DISK ERROR - CHECK MEDIA`). The owner had just power-cycled, the
boot went BASIC `mount` → `run`, and there was no IDE session before it.
The Attic-state hypothesis is therefore withdrawn as well.

The 2.0 release recorded the same symptoms
(`tools/host-lisp/c2_v200_release_strip_device_result.py`,
"nonqualifying_staging_incidents"):
- reuse, remount or restage of an already staged medium gives a red frame
  or `L65SYS DISK ERROR`;
- classification: "SESSION/STAGING-LIFECYCLE EVIDENCE; NO PRODUCT DEFECT
  INFERRED";
- discriminator: a fresh power cycle plus a fresh upload of the same
  medium, with an SHA-identical readback, booted green;
- permanent choreography: every qualifying cold boot restores and rereads
  the bound D81; a prior staged copy is never reused.

This night's session broke that choreography: warm resets and re-mounts
of already staged `IX250.D81` / `CD250.D81`. Next: a power cycle (owner),
then a fresh upload under a new name (`CD250B.D81`) and a boot; then the
IDE-exit medium as a fresh file with the C-x q rows, without warm resets.
The IDE card stays blocked until this passes.

### Correction: the boot medium was NOT written — suspected stale Attic-RAM state after a warm reset inside the IDE — 2026-09-28

The owner power-cycled the device, which returned it to BASIC READY. The
SD readback of `IX250.D81` is **byte-identical** to the uploaded image
(`89014071…`), so the persist-on-exit hypothesis is withdrawn.

Timeline:
1. Rows-01 included C-x q; the warm reset after it booted cleanly.
2. Rows-02 left the IDE **open** ("ello" in the buffer).
3. Every warm reset (`m65 -F`) after that failed closed, until the power
   cycle.

**New hypothesis:** Attic-RAM state (media staging and IDE buffer
persistence) survives a warm reset, and after a reset inside the IDE it
makes the boot-time staging check fail closed. If this holds, it is
independent of the new key and would also affect 2.5.0. Next: a control on
`CD250.D81` (2.5.0): BASIC boot, `(edit)`, type, warm reset. The IDE card
stays blocked until this is attributed.

### IDE key exit: BLOCKED — device boot refuses the medium after the C-x q session (suspected persist-on-exit write to the boot disk) — 2026-09-28

Device session on `IX250.D81`, the IDE-exit Final media (`89014071…`):
- Upload was new and read back byte-identical.
- Boot via BASIC `mount` / `dload` / `run` reached `l65>`.
- **C-x q** left the IDE to `l65>` in 1.7 s, and `(+ 4 5)` → 9.

Hardware resets then led to `L65SYS DISK ERROR - CHECK MEDIA` with a red
border (fail-closed at "LISP65: STAGING MEDIA"). This reproduced without
any polling during boot. One reset in between, taken before the second
IDE session, had booted cleanly to `l65>`.

**Suspected cause:** exit command 1015 (persist-and-return) saves the IDE
buffer onto the mounted boot medium, and the boot-time media integrity
check then refuses it. In the emulator the medium is a read-only copy, so
the rows could not see this. Before this card the path was unreachable,
because `C-x C-c` never arrived.

In the fail-closed state the SD readback timed out (the FTP peer does not
answer). The device needs the owner's hand (power cycle, or Freezer to
change the mounted image) before a readback of `IX250.D81` can confirm
what was written.

**Consequences:**
- The IDE key exit card is **not shippable** as is; the release of this
  world is blocked.
- For 2.5.0: check whether IDE save commands that are reachable today
  corrupt the boot medium the same way. This is a candidate known issue.

### IDE key exit: host closure — Final byte-identical, sealed check-source r4 green, seal PASS — 2026-09-28

Report: [ide-exit-final-report.md](ide-exit-final-report.md). Seal:
`ide-exit-final-20260928.json` (3,067 bindings, 96 copies, sealed at
`9bc8b87a`).

- `C-x q` leaves the IDE with the buffer kept; `C-x C-c` stays logical,
  with its physical limitation documented.
- Price: native 0 / 0 / 0; `SHELF.BIN` +32; Session record 22 +1 (proven
  derived-immediate drift). Inventory has 0 unclassified bytes.
- Rows: seed 10 / 10; the 2.5.0 control shows no exit. Media D81 is
  `89014071…`.
- Final ELF `7716852b…` is byte-identical to the Seed.
- The C-x q device row waits for the device.

Next: the Backspace card. Its patch and host measurement are prepared in
`build/backspace-r2/` (−7 %, −19 % and −26 % VM instructions per Backspace
at 10, 40 and 70 characters; −6 bytecode bytes).

### Reload-burst attribution parked (windmill rule); IDE key exit Seed starts — 2026-09-28

The reload-burst card is diagnostic only, with its tools under
`build/reload-burst-r2/` (runbook, eight selftests). It hit two tool reds of
different classes:
1. a stale pre-filter SHA binding between `prepare` and `lanes` (fixed);
2. `character-plus-taken cutpoint timeout` in the first product-world
   emulator lane (`runs/native-a-2`). The likely cause is the same class as
   the Comfort-default lanes: the product boots into `l65>`, and the
   observer's cutpoint is on the native key path.

The historical re-derivation also shows an accounting residual of 42 cycles
(21–70 on the repair rows) between the bracket total and the summed cost
buckets (`runs/historical-2`). No natural price claims may rest on those
brackets until this is resolved.

The card is **parked** with these findings. The re-entry point is the
runbook plus a lanes world that exits Comfort with a real Return key
(`~typeone 0d`) before arming, or that uses the 2.4.0-INIT control medium.

The IDE key exit producer is committed (`de79ca95`) and its command-probe
passes (budget 0). The rebound Seed now runs alone, at low priority.

### IDE key exit: harness finding was a producer defect (JSON key sorting reordered the disk fixture); rebound Seed starts — 2026-09-28

Diagnosis (`build/ide-exit-r4/harness-report.md`): the "baseline red" of Seed 1
was caused by the new producer itself. It rewrote the suite JSON with
sorted keys, which reordered the virtual disk fixture so that tab
completion skipped `DEMO`. There was no pre-existing harness defect. With
the fix:
- baseline emission passes all 158 historical cases;
- IDE code and metadata are byte-identical to both 2.5.0 reproductions;
- the normal IDE suites (182 cases) pass;
- the command-probe passes (173 inputs, 75 frozen commands).

Both spent attempts were therefore producer defects, still before any
product command. The rebound budget (1/1/1 + 1) now starts.

### IDE key exit: Seed budget spent before any product command; rebound once after a harness diagnosis — 2026-09-28

The Seed and its attributed replacement both halted in host IDE emission
before any native compile or link (`build/ide-exit-r3/seed-report.md`).

- **Seed 1:** `bytecode_p0_stdlib.emit_artifacts` runs historical IDE cases
  automatically. `ide-step-minibuffer-tab-filters-files` fails on the
  **unchanged baseline** (`"Find file: DEMO"` expected, `"Find file: d"`
  observed). The emitted baseline IDE code (14,992 B) and C2I metadata
  (15,216 B) are identical to the published 2.5.0. This is a host-harness
  or environment finding, not a product difference.
- **Replacement:** a defect in the new producer (empty case list).
- **Reach:** not media-only. The shelf feeds the product build ID, the
  shelf length and two CRC16 arrays into the ELF, so the card needs its
  product link.

**Reviewer decision under the delegation.** Both halts precede every
product command and are tool-class, so the card is **rebound once** with
1 Seed / 1 Final / 1 link + one attributed replacement, under one
condition: the harness finding is first diagnosed and fixed as its own
committed tool change, with the baseline emission passing. A further red
parks the card (windmill rule) and the night continues with Backspace.

### Night cards bound (owner delegation): IDE key exit, Backspace, reload-burst attribution, Set B residue — 2026-09-28

The base of every card is the 2.5.0 world: Comfort-default Final, ELF
`d555f01f…`, D81 `137bfa51…`. The cards run one after another; heavy runs
are low-priority and one at a time.

1. **IDE key exit.** Add `C-x q` (codes `[24,113]`, command 1015, route 13)
   as a new binding row in `config/v11-l-lite-keymap.json` and regenerate
   the owned outputs. `C-x C-c` stays a logical binding; its physical
   limitation stays documented. No resident change.
   - Budget: **1 Seed / 1 Final / 1 product link, plus at most one
     attributed replacement Seed.**
   - Gates:
     - price on the built product (native `.text`/`.rodata`/BSS 0 expected;
       plane and literal deltas inventoried);
     - input closure and a classifying inventory;
     - the keymap successor chain and the end-to-end key-path successor
       (Ctrl-X, then unmodified q through the pinned producer, ring,
       primitive 14 and dispatch);
     - emulator rows: exit with buffer kept, re-entry, plain q, Shift-Q,
       Ctrl-Q, C-x Cursor Down, an unknown suffix, synthetic C-x C-c, and
       exactly-once RUN/STOP;
     - sealed `check-source`, then a byte-identical Final;
     - a device row (C-x q) when the device is free.
   - Preflight: `build/ide-exit-r1/preflight.md`.
2. **Backspace latency.** Replace the second head traversal in the delete
   path (preflight `build/backspace-r1/preflight.md`, projected −6 Bank-2
   bytes). Card discipline as above.
   - Gates: a measured per-Backspace attribution at end of line, with a
     host and an emulator lane, and device echo timing when the device is
     free.
   - Target: a measurable latency reduction with no regression in the
     wrap, history or continuation rows.
3. **Reload-burst attribution.** Diagnostic only, no product change
   (`build/reload-burst-r1/preflight.md`).
4. **Set B residue.** Tooling only. Extend the sealed runner's directory
   policy and document the residue; the restart carriers stay
   (`build/setb-residue-r1/preflight.md`).

The windmill rule applies to every card: a second red of a new class, or a
price beyond the bound, halts that card and moves on to the next.

### 2.5.0 published — 2026-09-28

The release is at <https://github.com/novemberist/lisp65/releases/tag/v2.5.0>
(latest, four assets, draft and published readback PASS). Publish report:
[release-2.5.0-publish.md](release-2.5.0-publish.md).
- Public main is `07491638` (parent `d749aba4`), with tag `v2.5.0`.
- Before-Ship is `9665f97f`, with the local tag `proof/v2.5.0`.

The executed chain of this cycle:
- the Comfort-default card (host closure, seal);
- the 2.5.0 docs;
- two reproductions;
- three sealed `check-host` runs (r3 green);
- the device session (18 / 18);
- Before-Ship, Ship and Publish, under the owner's night delegation.

Physical rows remain pending: cold cycle with a stopwatch, the physical
RUN/STOP key, and typing feel.

Next, the night cards the owner granted, in this order:
1. IDE key exit (`C-x q`, `C-x C-c` kept);
2. Backspace;
3. reload-burst attribution;
4. Set B residue.

Heavy runs go one at a time, at low priority.

### 2.5.0: device session PASS, sealed check-host green; owner night delegation — 2026-09-28

**Owner words (2026-09-27, evening), recorded by the reviewer:**
- **Ship and Publish of 2.5.0** are delegated to the reviewer.
- **Device contact** is granted for the automated session. The physical
  rows (stopwatch, physical RUN/STOP key) may stay pending, recorded in the
  release.
- The **named GC cost** of Comfort as default is **accepted**.
- **Night cards after 2.5.0:** Backspace latency; IDE key exit (a new
  working key, `C-x C-c` kept — public surface change granted);
  reload-burst attribution; Set B residue cleanup.
- Work gently on the shared machine: low priority, one heavy run at a time.
  A parallel session may use the device; if it is busy, wait.

**Device session** ([report](comfort-default-device-report.md)):
- `CD250.D81` (`137bfa51…`) was new on the SD card, with a byte-identical
  readback.
- Boot: `Initializing...` at 20.9 s, `l65>` at 40.4 s (about +6.7 s).
- 18 / 18 row groups pass, including RUN/STOP under the default via the
  virtual matrix: `*** stopped (run/stop)` → `l65>`.

**Sealed check-host:**
- **r1** (`8657bbec`): two doc-drift reds, converted in `64c5add5`.
- **r2** (`64c5add5`): one red. The 2.4.0 public authority binds
  `mk/workbench.mk`; converted in `21390b9b`.
- **r3** (`21390b9b`): **exit 0**, 3,697 s, 0 changed protected files.

Two independent public reproductions are byte-identical (`8657bbec`).
Next: Before-Ship record and seal, Ship (assets, local tags), then Publish.

### Comfort default: host closure — Final byte-identical, sealed check-source green, seal PASS — 2026-09-27

Report: `comfort-default-final-report.md`; seal
`comfort-default-final-20260927.json` (53 bindings, 26 receipt copies, sealed
at `42b81911`).

- **Final** (`build/comfort-default-final-r1/`): ELF `d555f01f…`, PRG, LTO
  object and all three media byte-identical to the Seed. Budget closed at 2
  Seeds / 1 Final / 3 links.
- **Gates.** Rows 66/66 plus both controls. Boot +7.65 s (emulator; bound
  +8 s). Native-prompt lanes quiet median 0.991 / 0.985 (isolated) and
  0.999 / 1.003 (product after exit). The Comfort-prompt per-key path is
  identical to the accepted comfort-library world. Matched GC at the native
  prompt: +12 live cells, +2.1 % forced cycles. This is a **named cost** for
  the owner (six packages at boot, five more boot collections).
- **Sealed runs.** r1 (exit 2) exposed Set B's residue, not this card's:
  ten bwrap mount-limit reds (about 12,400 tracked Set B evidence files push
  the per-file protection past `fs.mount-max`), an mtime-stale sealed
  equivalence binary (rebuild byte-identical, mtime refreshed), and the F011
  primitive-15 successor drift on `src/vm.c` (re-recorded by its protocol).
  - Reviewer changes to the sealed runner: collapse fully protected
    directories (`3ac1e3fb`), and exempt gate output directories
    (`42b81911`, after the r3 red).
  - r4 green, 2,352 s, 0 changed.
- **Reviewer decision under the delegation:** the runner change is an
  instrument repair, not a gate relaxation. Every protected file is still
  verified read-only and write-rejected individually, and directory mounts
  additionally forbid new files. Raising `fs.mount-max` would have been a
  host system setting and was not touched.

Next: re-apply and update the parked 2.5.0 preparation
(`build/release-v2.5.0/parked-r1/`: Comfort default, IDE exit known issue,
Backspace note, named GC cost). Then the device session and Ship/Publish,
which are owner words.

### Comfort default replacement Seed: text −3, rows 66/66, exit NIL fixed in the library — 2026-09-27

Replacement Seed (`build/comfort-default-product-r2/`, producer at AUTH
`1447e988`; the reviewer fixed three Seed-1 assumptions in the producer
before the link: ancestor binding instead of HEAD==AUTH, the lookup-free
patch check, and a separate full-map-linker copy for the owned byte so the
baseline pre-probe keeps the Final's linker). Budget now 2 Seeds / 0 Finals
/ 2 links, no replacement left.

- **Price** (reviewer re-measured on the ELF `d555f01f…`): `.text` **−3**,
  `.rodata` +0, one owned NOBITS byte at `$BFF6` (high BSS free 9, floor 5).
  Classifying inventory PASS, zero unclassified bytes; codegen drift only in
  the hooked function (649 → 639 bytes, 18 families with static proofs).
- **Rows** (`tools/host-lisp/comfort_default_rows.py`): the first media
  printed `0` instead of `NIL` on the empty-line exit — `repl-comfort-v250`
  had lost the trailing `nil` of the 2.4.0 library. Library-only fix
  (`1ed9b319`, 960 / 1,000 Bank-2 bytes), media rebuilt from the same ELF
  (`media-r2`, 856 differing bytes confined to the package and index CRCs).
  On media-r2: product **66/66** (boot to `l65>`; nested error, type error,
  lambda refusal and depth refusal land at `l65>` with definitions and
  history; empty line exits to `lisp65>` and errors stay native there;
  `(repl)` re-arms), 2.4.0-INIT control 9/9, no-Comfort control 4/4.
- **Boot:** +309.7 M cycles over 2.4.0 (≈ +7.65 s at 40.5 MHz; bound +8 s).
  Device stopwatch at the owner session.
- RUN/STOP inside a running form under the default is a device row.

Next: lanes at both prompts and matched GC (Codex), consumer successors,
sealed `check-host`, Final, device session with the owner's contact word.

### Comfort default replacement authority: lookup-free hook, +12 text projected — 2026-09-27

The replacement authority (Codex, `build/comfort-default-r2/`) implements the
lookup-free hook: one owned high-BSS byte (0 / 1 / 2; high-BSS free 10 → 9,
floor 5) declared in `config/comfort-default-native/`, its address generated
into `lib/comfort-state-address.lisp` by `tools/host-lisp/comfort_state_address.py`
(with `--check`; the Ship library `m65-hw-registers.lisp` stays unchanged and
its contract gate green), the library writing the byte by byte-poke, the
hook feeding `(repl)` to the native reader. Projection: **+12 ordinary text,
.rodata 0, BSS +1**; zero new call edges (inline-sensitivity check SAFE);
library 957 / 1,000. Committed as the replacement source authority; the
replacement Seed (last of the budget, 2/0/2 after it) follows.

### Comfort default Seed 1 halted on price (+302); attributed replacement Seed for a lookup-free hook — 2026-09-27

Seed 1 (`build/comfort-default-product-r1/`, ELF `b0f24ece…`; AUTH
`d9316a5e`, DIFF_BASE `90b5f9f2`) passes the command, link and E000
probes and halts at the price gate: ordinary text **+302** against the
bound 170 (free 1,209 → 907); `.rodata`, E000, capture, BSS, frames and
metadata unchanged. Attribution: the hook's `sym_lookup` call adds a second
caller, so whole-program LTO stops inlining `sym_lookup` into `intern`
(`intern` 326 → 108, out-of-line `sym_lookup` +349); the non-LTO
projection could not see this.

Reviewer decision (air first): the one attributed replacement Seed is
spent on a **lookup-free hook**. The sticky state becomes one owned byte in
high BSS (5 spendable above the floor; the storage-owner receipt gains the
owner row), written by the library through the existing byte-poke
primitive at an address exported by the build (derived, not hard-coded in
the library source); the hook reads the byte and, when requested, feeds
`(repl)` to the native reader. An unloaded Comfort makes the fed line an
ordinary undefined-function error in the existing recovery path; the
pending state prevents a second attempt. No symbol lookup, no new caller of
`sym_lookup`/`intern`. Bound unchanged at 170; if the replacement also
exceeds it, the card halts and returns to the owner with the options.
Budget after the replacement: 2 Seeds / 0 Finals / 2 links, no further
replacement.

### Comfort default step 1b: resident bound set to 170 on the measured price; source authority committed — 2026-09-27

Step 1b (`build/comfort-default-r1/preflight-report.md`, section 1b) feeds
`(repl)` to the native reader through the existing read/eval/print/recovery
path: no echo, no history entry, the accepted state protocol unchanged,
both constants as text-owned data. Projection against the 2.4.0 Final's
flags: **+164 ordinary text** (lookup/setup 62, value comparison 34,
pending/reader transfer 35, cleanup 33; 23 of them data), **.rodata +0,
BSS +0**; library 969 / 1,000.

Decision (reviewer, under the delegation): the 60-byte figure of the
binding was an unmeasured estimate; the measured form carries no
duplication and no safety slack to trim. The resident bound is set to
**170** (text reserve 1,209 → about 1,045 projected, floor 32). The source
authority for members (a)–(c) is committed with this entry; next the
producer `AUTH`, then the Seed (1/1/1 + one attributed replacement), price
with a classifying inventory, media (six packages + INIT request), the
emulator rows, the consumer successors before the sealed `check-host`, the
Final, and the device session before Ship.

### Comfort default step 1 reviewed: design accepted, hook form rejected on price, library bound 1,000 — 2026-09-27

Codex's preflight (`build/comfort-default-r1/preflight-report.md`) is
accepted in its design: the state lives in the private Lisp value cell
`%comfort-sticky` (NIL / `t` / fixnum 0 pending) with exactly one re-entry
attempt per recovery; `%comfort-history` as a private global root so the
history survives the non-local jump; INIT sets a deferred start request
that the first prompt boundary honours (the REPL never runs inside INIT);
missing Comfort or an unbound `repl` leaves the native prompt. The
conservative edge (an error during input before the first complete source
after a re-entry falls back to `lisp65>`) is accepted — idle RUN/STOP has
no product action, so it arises only from reader/editor failures.

Rejected on price: the hook calls `repl` from C and re-implements the error
status translation (`G/eval.c`), +311 text and +21 `.rodata` (0 free) = 332
against the bound 60. **Step 1b:** the hook must reuse the native loop's
own evaluation and error path instead of duplicating it — the preferred
form is to feed the fixed input line `(repl)` to the native reader as the
next line when `%comfort-sticky` requests it (no echo, one attempt per the
same state protocol), so evaluation, error printing and recovery are the
existing ones; the literal lives as a text-owned data object (precedent:
the startup-message card, `.rodata` 879/0 kept), not in `.rodata`. Target
≤ 60 resident bytes; if the honest minimum is higher, report it with the
per-site bytes rather than trimming the state protocol.

Library: 969 bytes accepted; the library bound is raised from 950 to
**1,000** (Bank-2 room about 7,470 bytes; the 950 was a card-local
guideline, not a capacity wall).

### Owner words: IDE exit as known issue; Backspace card after 2.5.0; "Comfort as default" card bound into 2.5.0 — 2026-09-27

After the owner's device session (`comfort-device-report.md`):

1. **IDE exit:** `C-x C-c` cannot reach the IDE (queue code `$03` drained
   in the KERNAL window since `49566a7f`); RUN/STOP leaves the IDE with the
   buffer kept. 2.5.0 documents this as a known issue and in the user
   guide; a working key exit is a later Lisp card.
2. **Backspace latency** (owner: typing slightly, Backspace very sluggish):
   its own card **after 2.5.0**.
3. **"Comfort as default" is bound into 2.5.0** (owner word on the
   reviewer's recommendation; release date moves by this card). Today an
   error, RUN/STOP or the depth refusal inside Comfort lands at the native
   `lisp65>` because the native recovery path owns the landing; a library
   cannot catch it.

**Card "Comfort default", base = the 2.4.0 world** (nested-error recovery
Final, ELF `66165507…`, D81 `87cb0f6e…`, include/linker/plane authority of
that Final — **not** Card L or Set B; their feature flags stay off).
Members: (a) a resident re-entry hook: after the native recovery lands at
the prompt, if the Comfort-sticky flag is set, re-enter `(repl)` instead of
showing `lisp65>` (the flag is set by `(repl)` on entry and cleared when
Comfort is left deliberately — today the empty line; the preflight decides
whether that stays the exit or needs a named form); (b) `INIT.L65` gains
`(require "repl-comfort")` and `(repl)` so the product starts in Comfort;
(c) the Comfort library changes only as far as (a) needs (flag set/clear).
No public surface beyond "starts in Comfort and stays after errors";
explicit leaving remains possible and documented.
Budget **1 Seed / 1 Final / 1 product link + at most one attributed
replacement Seed**. Gates: price (resident ≤ 60 bytes projected, measured
at Seed; text reserve from 1,209); boot to `l65>` with the added load
measured (emulator and device; target ≤ +8 s over 2.4.0's 32 s); error,
RUN/STOP and depth-refusal rows land at `l65>` with definitions and history
intact; deliberate exit lands at `lisp65>` and stays there; the D1–D23
rows adapted; plain-prompt rows after exit; lanes ≤ 1.02 at both prompts;
matched GC with named cost (six packages at boot); nested-error,
retained-callable and over-cap regressions; sealed `check-host`
consumers prepared first; Final byte-identical. Device session with the
owner's contact word before Ship. The parked 2.5.0 preparation of
Codex (`build/release-v2.5.0/parked-r1/`, patch + archive) is re-applied
and updated after this card.

### Owner word: Comfort surface defaults kept; 2.5.0 release chain starts — 2026-09-27

On the device screens of the automated session the owner kept the three
surface defaults: prompt text `l65>`; multi-line scrollback as shown (first
line with its prompt, continuation rows indented without a prompt); the
over-close message `*** reader: unmatched close parenthesis`. No Lisp-plane
change follows. The 2.5.0 chain starts: release notes and known issues,
v2.5.0 build/bundle authorities (runtime unchanged from 2.4.0, medium =
2.4.0 plus `repl-comfort`), two reproductions, sealed `check-host`, stop
before Ship. Ship and Publish stay owner words; the owner rows at the
machine (RUN/STOP, cold cycle, `C-x C-c`, row H, final SD readback,
column 26) are listed as not verified in the notes unless run before Ship.

### Comfort device session, automated part: D1–D23 pass on the MEGA65 — 2026-09-27

Owner contact word for the automated part; report
[comfort-device-report.md](comfort-device-report.md), receipts
`build/comfort-device-r1/`. `CMF240.D81` new on the SD card, byte-identical
readback; boot to the 2.4.0 prompt; all Comfort rows pass on hardware
including the history ring via the virtual keyboard's Up/Down; two halts
attributed to the driver and to resuming inside an open line across a
monitor reconnect (clean rerun passes). Left to the owner: RUN/STOP,
cold cycle, `C-x C-c`, row H, final readback, column 26, and the three
surface decisions.

### Owner word: Set B frozen; Card L not shipped; release 2.5.0 = 2.4.0 runtime + Comfort library — 2026-09-27

Reviewer review after the Codex phase (HEAD `509a48e0`, 47 commits since
the handover `bad4c939`): Set B consumed 5 Seeds / 0 Finals / 5 links
(ceiling 5/1/5, each replacement owner-authorized). The fifth Seed proves
activation and image reuse (50 redefinitions hold 9 images, boot +0.493 s
over Card L) but halts at `(require "defstruct")` → NIL (the resolver
assumes contiguous code spans; retirement leaves charged holes). The
repair chain (gap-tolerant checks, DMA completion proofs, complete CLEAR
rollback, synchronous publication) is host-green but needs 185 ordinary
text and 32 E000 bytes beyond the reserves. The DMA findings are limits of
predicates under synthetic schedules, not shipped defects of 2.4.0.

Owner word (2026-09-27), on the reviewer's recommendation under the
windmill rule of 2026-09-07 (a mechanism that needs more reserve than it
creates ends the block) and the release-scope rule of 2026-09-23:

1. **Set B is frozen.** All Seeds, candidates, receipts and seals stay
   archived; the fifth Seed (`build/set-b-product-r5`, ELF `139e7775…`,
   D81 `587136f5…`) and `set-b-clear-sync-report.md` are the re-entry
   point. A restart needs an air programme that creates the reserve first
   (at least the measured 185 text / 32 E000 plus Set B's own resident
   price) and a fresh owner binding. Member 5 stays unbound.
2. **Card L is not shipped.** Without a tenant it is ballast (+0.31 s
   boot, one catalog slot, 13 text bytes, a marker). It stays a qualified
   development world and Set B's carrier for a restart.
3. **Release 2.5.0 = the 2.4.0 runtime (ELF `66165507…`) + the Comfort
   library package `repl-comfort`** (medium `bb9b8d56…`,
   `comfort-library-host-report.md`). Before Ship: the Comfort device
   session (`comfort-device-plan.md`, SD name `CMF240.D81`) with the
   owner's three surface decisions (`l65>` prompt, multi-line scrollback,
   over-close message text), folded with the open device rows (RUN/STOP
   in a running form, cold power cycle, physical `C-x C-c`, row H
   persistence, SD readback); release notes and known issues; the usual
   Before-Ship chain (sealed `check-host`, two reproductions, Ship,
   Publish). Version, Ship and Publish remain owner words; the device
   session needs the owner at the machine.

### Set B CLEAR: synchronous publication passes roots, capacity halts — 2026-09-27

Owner “Dann bitte gemäß deiner Empfehlung fortfahren” continues `2a36aabe`:
one isolated synchronous publication/full-rollback repair, renewed host2/
dependency1; native16/8/2 after host success; zero product build/link/Seed/
guest/device. [Report](set-b-clear-sync-report.md). The publication
prerequisite passes 240 host rows/648 root observations, including old and
latest logically published macro roots, duplicate symbols and injected
allocation/undo failures. All three DMA falling controls are detected.
CPU writes are an explicit host seam; target MAP execution is unqualified.

After that host prerequisite, matched native objects price the publication
part before controller extension: ordinary +193 against margin8 → −185;
E000 +57 against25 → −32; high BSS unchanged at margin1. Publish-clear −1
cannot pay another owner. **Capacity halt; full CLEAR controller unauthored.**
No linked placement, complete CLEAR qualification or product admission.

Used host compile/link1, dependency1, native objects4/dependencies4/assembler1;
remaining1/0 and12/4/1, no budget reset or new source form past the halt.
All74 compiler roots unchanged; one isolated candidate with patch, exact
host bodies, rows, objects and disassemblies sealed. Overall5/0/5,
ceiling5/1/5; Card L/public2.4.0 and fifth-Seed load halt unchanged.
Recommend read-only placement/shared MAP reader-writer design before another
source form, naming the169-byte writer,24-byte setter growth and57-byte E000
helper. Preserve all floors, region0 ceiling65205, complete rollback and
late-capsule288-byte reservation; no assumed LTO/controller savings.

### Set B CLEAR implementation: shared-FIFO macro root halt — 2026-09-26

Owner “Dann bitte gemäß deiner Empfehlung fortfahren” continues `0815dce5`,
renewing host2/dependency1 for the isolated full-rollback repair; native
16/8/2 only after host gates, zero product build/link/Seed/guest/device.
[Report](set-b-clear-gc-gate-report.md). Required macro before-image gate
runs before controller authoring: nine exact C bodies, one FIFO for undo
and function writes, sources captured.12 corrected rows/30 root observations;
11 rows pass, N4 loses old macro0006 at allocation4 when FIFO advances
between C2-root walk and symbol-function scan. Journal becomes correct but
the collector has already missed that root; publisher returns0/errors0.
Host root closure only, no sweep, full collector or device corruption claim.

Attempt1's independent immediate function-store seam is excluded;8 diagnostic
rows/20 observations retained. Attempt2 binds actual function transport and
same-engine order. Both compile/links succeed;2/2 host attempts consumed,
1 dependency call (same headers/closure reused explicitly for attempt2).
Total20 C rows/50 observations including excluded evidence. All74 roots and
candidates exact; no controller source form, native pricing or new product.

Halt at producer/root lifetime. No-GC starting at CLEAR alone is too late.
Recommend coherent synchronous CPU stores for compacted undo and canonical
function-cell publication, sharing final-scrub primitive, then complete
CLEAR protocol. Qualify old AND newly allocated macro roots and all existing
rollback/error/READY/boot/identity/floor gates; no immediate duplicate beside
an outstanding DMA write. Proposed next host2/dependency1; native16/8/2
unspent, no product build/link/Seed/Final/guest/device. No budget reset here.
Overall5/0/5, ceiling5/1/5; Card L/public2.4.0 unchanged.
Seal `set-b-clear-gc-gate-20260926.json`.

### Set B source capture: pinned RTL attribution closes host-model premise — 2026-09-26

Owner “Dann bitte gemäß deiner Empfehlung fortfahren” continues `d97b1a30`'s
read-only audit. [Report](set-b-source-capture-report.md). Clean reference
core `a9158930`, entire gs4510 RTL equal to its Git blob: D700/D705 enter DMA,
source read data is latched in reg_t, CPU normal continuation follows last
copy count. This supports capture-before-C-source-reuse on the normal path;
no exact-device identity, memory-controller or destination-drain proof.
Historical Link35 immutable source cannot distinguish capture timing;
Link59 records late destination bytes, no source-reuse trace. Keep both
late-target walls. G6 media profile cannot retrobind older DMA core identity.

Use captured-source/delayed-target model for successor host qualification;
retain deferred-source policy as a falling boundary control, not a claimed
hardware defect. Full rollback/retained capsule/ordered witness/root and
finalizer gates remain. No controller authored or priced in this commission.
Next proposed isolated repair: renewed2 host attempts/1 dependency, then
only after host pass16 native object/8 dependency/2 assembler calls, zero
product build/link/Seed/Final/emulator/device. This read-only commission
does not renew the exhausted host budget or admit the implementation.

Charged zero compiler/dependency/assembler/native/C runs/build/link/Seed/
Final/guest/device. All74 roots/candidates exact; overall5/0/5, ceiling5/1/5.
Card L/public2.4.0 unchanged. Seal `set-b-source-capture-20260926.json`.

### Set B CLEAR C preflight: source-capture contract halt — 2026-09-26

Owner “Dann bitte gemäß deiner Empfehlung fortfahren” continues `b95ba185`,
authorizing its isolated implementation/pricing card and first-red stop.
[Report](set-b-clear-c-preflight-report.md). Exact unedited publisher and
region-writer bodies:4 immediate/captured-source controls pass. Next deferred
source row stops: at second submission the same live journal[4] changed from
00 E0 14 C0 to02 E0 16 C0 (2 bytes), publisher still returns0. No expired
pointer dereference, new controller execution or hardware corruption claim.
Late target visibility does not prove late source fetch; this is a missing
source-capture bridge, not a confirmed third product-defect class.

Halt before authoring the terminal source form or native pricing. Next bind
source consumption independently from destination visibility using existing
transport/archived authority, zero compiler/build/link/Seed/guest/device.
If capture-before-reuse is proven, resume with the captured-source model and
renewed host budget; otherwise stable producer storage/synchronous stores
must join the same repair. Full rollback remains selected; no comparator,
READY, boot or floor relaxation. Remaining qualification rows unexecuted.

Charged2 host compile/link attempts,1 successful shared link,1 dependency;
first failed at fixture static/public declaration conflict, corrected only
that host seam and retained all attempt1 artifacts. Five C rows, four pass
then lifetime/authority halt. Zero native/assembler/product source forms/
build/link/Seed/Final/guest/device;74 roots/candidates exact. Overall5/0/5,
ceiling5/1/5; Card L/public2.4.0 unchanged. No third host compile authorized.
Seal `set-b-clear-c-preflight-20260926.json`.

### Set B CLEAR: owner selects complete rollback; upper-half undo protocol — 2026-09-26

Owner “Dann bitte gemäß deiner Empfehlung fortfahren” continues `fe469f02`;
explicit clarification “Vollständige Rücknahme (empfohlen)” selects restoration
of the failed publishing transaction, not retention of its definition.
[Report](set-b-clear-protocol-report.md). Terminal protocol: after the plan is
consumed, copy compacted4K undo bytes by ordered DMA to the upper half of its
existing8N-byte owner; clear lower4N and C2J, then one trailing read. Timeout
latches ABORT. Keep backup through rollback retries and every fallible caller
finalizer (transaction_end follows append). Final backup scrub is synchronous
CPU work after settlement; no new asynchronous disposal window.

Storage proof checks all1819 counts, N<=1818 within58430–5BCFF, no additional
export bytes or reduced capacity. Capsule288 bytes at5F900–5FA1F;1120 internal
padding bytes remain, tail374 floor intact. No GC/allocation or ordinary
unwind while primary/backup is pending; intercept before interrupt.c root
drop as well as REPL recovery. Bounded native quarantine preserves READY;
permanent non-delivery does not promise ordinary Lisp availability. Public
error43/file nil/capacity OOM and original-error precedence remain bound.
Correction: post-extent pristine late fill is A5, not zero; full image CRC
still precedes runtime initialization.

5745 abstract Python rows pass plus3 falling controls; initial3926-row run
and tools retained. No exact-C, target GC/timing/reset or full append replay
claim. All74 roots/candidates unchanged; zero compiler/dependency/assembler/
C/build/link/Seed/Final/guest/device. Executable price remains unmeasured.
Next proposed single isolated implementation/pricing card: host compile/link
attempts2, host dependency1, native object calls16/dependencies8, assembler2;
zero product build/link/Seed/guest/device. Budget is proposed, not consumed
or granted by this contract commission. Existing floors/region0 ceiling stand.
Overall5/0/5, ceiling5/1/5; Card L/public2.4.0 unchanged.
Seal `set-b-clear-protocol-20260926.json`.

### Set B barrier design: data fits, CLEAR terminal recovery unclosed — 2026-09-26

Owner “Dann bitte gemäß deiner Empfehlung fortfahren” continues `220415d1`.
[Report](set-b-barrier-design-report.md). Exact proposed capsule:256 bytes at
5F900–5F9FF, derived from consumed span packing;1152 internal padding bytes
remain. The separate374-byte tail remains floor. Full8192-byte boot CRC and
runtime write-watch obligations are specified, not relaxed or implemented.

Halt at terminal recovery: CLEAR zeros export before-images before its read
is proven. Retaining C2J/header/control alone cannot recover old function
values after a timeout. Two abstract histories demonstrate the missing
information; no new C/guest/device execution or product-defect class claim.
Public append error is43 BAD BYTECODE (internal streamIO); file nil and
capacity OOM identities stay. Quarantine/root/unwind and native UI closure
remain unbound. Data price is exact; executable price is unmeasured, with
ordinary/E000/capture margins8/25/48 and region0 at its existing ceiling.

No new source form, compiler/dependency/assembler/build/link/Seed/Final/guest/
device; all74 roots and candidates unchanged. Recommend reviewer binding of
undo retention through the terminal decision, forward versus rollback CLEAR,
and safe native quarantine before a coherent implementation/pricing budget.
No further buffer substitution or Seed. Consumed5/0/5, ceiling5/1/5;
Card L/public2.4.0 unchanged. Seal `set-b-barrier-design-20260926.json`.

### Set B DMA destination worksheet: owner and timeout-reentry conflict — 2026-09-26

Owner “Dann bitte gemäß deiner Empfehlung fortfahren” continues `873730db`.
[Report](set-b-barrier-owner-report.md). No admitted disjoint64-byte destination
with retention across timeout found in the bounded existing-owner inventory.
Append scratch tail is at most61 bytes (target offset assertion, no host
sizeof); emitter later fills302. Input ring is a raw IRQ owner, convergence
bytes are descriptors/witnesses, Bank-5 retirement gap leaves24 and the374-byte
tail is entirely floor. Low-BSS gap includes146 bytes of soft frames; its
pre-span margin is8, not the apparent space from ordinary .bss end.

Source-wide alias ledger:177 files,227 textual edges in12 files, conservative
inactive branches included. Recovery explicitly releases/reacquires scratch;
v5_fail can clear READY. Retaining a buffer alone does not retain header/seal
facts or the caller frames addressed by before/main_ordinal. Required bounded
quarantine/reentry transitions are tabled, not claimed implemented or executed.

Halt under the worksheet's no-fitting-owner rule. Recommend one coherent
storage-and-recovery design: price a mutable subowner inside internal late
padding (span projection1408 bytes, starting5F900), with new identity/write-watch
binding and safe CPU sampling/reentry. This is not permission to consume the
sealed padding or374-byte floor. Zero compiler/build/link/Seed/guest/device;
no second source form before the design closes. Candidate and74 roots exact;
overall5/0/5, ceiling5/1/5; Card L/public2.4.0 unchanged.
Seal `set-b-barrier-owner-20260926.json`.

### Set B trailing DMA read: lifetime halt before native pricing — 2026-09-26

Owner “Dann bitte gemäß deiner Empfehlung fortfahren” continues `0089c308`.
[Report](set-b-barrier-read-report.md). One isolated change at the common
completion predicate restores the trailing same-engine read. Exact C at
explicit host seams: 158 content/order rows, one falling MAP control and
one permanent-drop limit give expected outcomes. Next row halts: at timeout
the poll returns0 after64 host attempts with64 bytes still pending to its
function-local destination; data writes completed, committed0. No late
pointer dereference, full publication/replay or native/device defect claim.

The first harness run had a cancelling-XOR oracle error; original halt and
all receipts retained, identical library replayed with the exact correction.
No comparator or product-form change. The lifetime gate is the first genuine
failure; stop before every native object/dependency/capacity call.

One host compile/link/dependency; no second attempt consumed, no product
build/link/Seed/Final/guest/device. All74 compiler roots and maintained product
sources unchanged; candidate parked, size unmeasured. Prior span margins
5/8 and BSS/E000/capture1/25/48 remain prior-world facts. Overall consumed
5/0/5, ceiling5/1/5; Card L/public2.4.0 unchanged.

Next recommend one host-only lifetime/ownership worksheet: an existing disjoint
destination that survives timeout, all access/reuse owners, and bounded safe
timeout/reentry disposition. No assumed cancellation, deadline guarantee,
unbounded wait, READY clear, boot abort or new BSS allowance. Stop if no owner
fits. Zero compiler/build/link/Seed/guest/device; no second repair form yet.
Seal `set-b-barrier-read-20260926.json`.

### Set B transport authority reconciled; isolated completion-reader repair proposed — 2026-09-26

Owner “Dann bitte gemäß deiner Empfehlung fortfahren” continues `a7d4c41d`.
[Report](set-b-front-ordering-report.md). Manual CPU-stall intent verified
against the bound PDF. Relevant historical counterevidence is not limited to
Attic: Link-59 records late CPU-to-Bank2/Bank5 writes while ACTIVE C2J stays
unchanged. The CPU-read migration retains journal/rollback walls; its probe
and release rows do not replace the trailing same-engine DMA witness.
Ordering halt remains; no new hardware/current-world defect claim.

Delayed, eventually ordered writes remain inside the inherited obligation.
Permanent loss/truncation or reordering despite a successful trailing read is
not covered by that witness; its disposition is not silently narrowed here.
The upstream response remains locally recorded (direct web retrieval failed);
the manual and historical Chip-write receipt independently support the result.

Next propose one isolated cold completion-reader form restoring the trailing
DMA read only at the barrier, with the existing MAP reader as falling control.
Exact C ordered-delivery/timeout/lifetime rows, then matched five-unit objects
and all-record packing. Proposed ceiling: two host compile attempts/links,
one host dependency, ten native objects/dependencies; zero product build/link,
Seed/Final/guest/device. One form, no implicit retry or new Seed allocation;
unchanged CRCs, READY behavior, 64-frame bound and every capacity floor.
Permanent-drop behavior remains an explicit limit, not an unearned pass.

This audit: zero compiler/dependency/assembler/C/guest/device executions;
74 roots and candidate unchanged. Air 5/8 and BSS/E000/capture 1/25/48;
consumed 5/0/5, ceiling 5/1/5; Card L/public 2.4.0 unchanged.
Seal `set-b-front-ordering-20260926.json`.

### Set B completion fence: transport-ordering proof halt — 2026-09-26

Owner “Dann bitte gemäß deiner Empfehlung fortfahren” continues `5b401d68`.
[Report](set-b-front-fence-report.md).72 actual-C content checks pass; next
synthetic visibility row halts. The unchanged rollback/data-barrier predicate
accepts a matching already-active C2J while8 prior-write bytes remain pending.
No full publication or replay executed; no hardware/shipped-corruption claim.

July's ordering witness requires a trailing same-engine DMA read; the active
MAP_CPU_TRANSPORT reader is synchronous CPU/MAP with no DMA submission.
The selected CPU transport authorities preserve journal correctness but do not
bind the bridge that excludes the injected visibility schedule. Halt under
the missing-ownership rule, not a fabricated new product defect. Actual source
matches maintained code; candidate and74 roots unchanged.

Next recommend read-only transport-authority reconciliation: bind the CPU/DMA
ordering guarantee and admitted delayed/partial fault domain, or document its
absence and propose the necessary evidence card. No repair or further replay
qualification before disposition. One host compile/link/dependency; zero
native compile/product build/link/Seed/guest/device. Air5/8 and all floors
unchanged; consumed5/0/5, ceiling5/1/5; Card L/public2.4.0 unchanged.
Seal `set-b-front-fence-20260926.json`.

### Set B real caller/writer paths:385 bounded C rows pass — 2026-09-26

Owner “Dann bitte gemäß deiner Empfehlung fortfahren” continues `9013c3fc`.
[Report](set-b-front-paths-report.md). Unchanged span candidate and74 compiler
roots.156 full installer/error rows,91 actual entry/header/unpublish/wipe rows,
138 scanner/certificate/retirement-owner/stage rows pass. Exact BADOPCODE→43,
TYPE→38,OOM→40 and inherited inner-error preservation; no Lisp-form execution.

53 inherited direct sink edges/44 owners now tabled against candidate hooks.
No new linked or indirect/raw-I/O closure claim. Real stage-plane code ignores
zero-write returns and relies on later completion proof; source behavior is
preserved. Full journal/replay/DMA completion and physical raw I/O remain open.
Five host compile attempts/four successes and host links/three dependencies.
Failed compilation and false pre-phase-snapshot range halt retained and
attributed to the harness, with no comparator or product change.

Next recommend host-only actual completion-fence/journal-replay attribution,
including ignored submissions and partial/stale/readback failures; stop on
unexplained accepted partial publication or missing ownership. No new product
form/native compile/build/link/Seed/guest/device. Current5/8-byte margins and
all floors unchanged. Consumed5/0/5, ceiling5/1/5; Card L/public2.4.0 unchanged.
Seal `set-b-front-paths-20260926.json`.

### Set B start/length form: capacity and bounded C qualification pass — 2026-09-26

Owner “Dann bitte gemäß deiner Empfehlung fortfahren” continues `09c7c983`.
[Report](set-b-front-span-report.md). Exact limb validator, start/length passed
after all checks.05b delta132 projects1787/1792,5free; helper50, ordinary776
leaves40/floor32,8margin. All63 records fit; region0 meets65205 ceiling.
Ten native object/ten dependency calls pass; only05b/helper differ from limb,
181 other allocated sections match in bytes/relocations. All74 roots verified.

941 extracted decoder/helper C rows pass, including both falling early05a
controls with partial reads.229 caller/scratch C rows pass: terminal ordering,
transient front exclusion, rollback, taint, scratch/trace cleanup and nonlocal
abort/recovery. Actual transport/stage/publication/rollback are declared seams;
full transient VM caller, raw-writer closure and exact VM errors remain open.
Three host compile attempts, two successes/links, two dependency calls; the
failed first lifetime harness compile is preserved, not counted as a pass.

Next recommend host-only closure of real writer/caller paths on this exact
candidate, bounded-memory C integration where feasible and explicit exact
BAD BYTECODE successors. Price missing hooks before changes; retain all floors
and current5/8-byte margins. Native cold/stack/GC/identity remain later gates.
No product admission or attempt; zero product build/link/Seed/guest/device,
consumed5/0/5, ceiling5/1/5; Card L/public2.4.0 unchanged.
Seal `set-b-front-span-20260926.json`.

### Set B checked-end reuse: larger05b, halt; retain limb control — 2026-09-26

Owner “Dann bitte gemäß deiner Empfehlung fortfahren” continues `3534895c`.
[Report](set-b-front-end-report.md). One isolated05b end-reuse form compiles
successfully but grows27 bytes versus limb. Delta171 projects1826/1792,34 over.
The prior19-byte saving target is not achieved. Helper38 and ordinary764 remain
exact;20 resident margin. Byte/relocation comparison to limb: only05b changes,
182 other sections match. Ten native object compiles/ten dependency calls pass.

All63 records packed: region0 65269/65536,267free but64 above design ceiling;
region3 6784/8192. Other margins and every floor unchanged. Capacity halt before
C; no semantic/lifecycle/native execution or relaxed comparator. Keep the better
limb candidate (1799/1792) as parked control, not an accepted product.

Next propose one isolated start/length helper-interface form over limb: retain
exact05b validation, pass context/start/length after all checks, compute validated
end inside resident helper. Direct matched-object price of both caller/callee;
no assumed codegen saving. Same caps137 overlay growth/58 helper+resident drift,
all-record packing before actual C. One form, halt on failure; no product attempt.
Zero host C/build/link/Seed/guest/device this commission; consumed5/0/5,
ceiling5/1/5. Card L/public2.4.0 unchanged. Seal `set-b-front-end-20260926.json`.

### Set B seven-byte audit: checked-end reuse plan — 2026-09-26

Owner “Dann bitte gemäß deiner Empfehlung fortfahren” continues `724860a3`.
[Report](set-b-front-end-plan-report.md). Existing range checks plus later end
addition cost82 bytes. Propose computing a16-bit end once, refusing end<start
or end>limit at the same row point, and reusing it after all bindings. Keep the
38-byte helper and interface exact; caller setup/JSR/reload35 stays charged.

All1796+38 existing instruction bytes accounted.706,538 range and4,117,976
full-predicate model cases pass, including a falling missing-wrap-guard control.
No C or machine execution. Worksheet39 plus24 spill/liveness allowance gives
replacement63, saving19; allow12 other05b drift to reach unchanged1792 cap.
Ordinary764 retains20 margin; no transfer needed in this design. Compiler fit
unmeasured; every floor and region0 ceiling65205 unchanged.

Next one isolated05b-only form, objects/all-record packing before actual C
fault/lifetime gates; halt on cap/floor failure or unbound successor. No product
attempt. Zero compiler/dependency/assembler/link/Seed/guest/device this analysis;
consumed5/0/5, ceiling5/1/5. Card L/public2.4.0 unchanged.
Seal `set-b-front-end-plan-20260926.json`.

### Set B directory-difference/byte-max: seven-byte05b halt — 2026-09-26

Owner “Dann bitte gemäß deiner Empfehlung fortfahren” continues `d2865265`.
[Report](set-b-front-limb-report.md). One isolated C form implements16-bit
binding differences with upper-byte refusal and an offsetof-based byte-max
helper. Ten matched native object compiles/ten dependency calls pass, including
layout assertions.26 changed/157 unchanged allocated sections;05a/Entries
restored exactly,04+15 retained, other measured deltas unchanged.

Measured savings versus fused form32 overlay/28 resident. Helper38 beats its50
byte target; ordinary764 leaves52/floor32,20margin.05b delta144 exceeds137:
linked projection1799/1792, seven bytes over. All63 records packed: region0
65237/65536,299free, but32 above design ceiling65205; region3 6784/8192.
E000/BSS/capture margins25/1/48 retained. No floor or slice limit relaxed.

Halt before C execution: no semantic/lifecycle/exact-error pass claimed. Next
proposed read-only seven-byte audit including caller setup and20-byte resident
margin; bind one reduction/transfer form before another compilation. No product
attempt. Zero host C/build/link/Seed/guest/device; consumed5/0/5, ceiling5/1/5.
Card L/public2.4.0 unchanged. Seal `set-b-front-limb-20260926.json`.

### Set B joint ABI plan: directory differences and byte-indexed max — 2026-09-26

Owner “Dann bitte gemäß deiner Empfehlung fortfahren” continues `82434b68`.
[Report](set-b-front-abi-report.md). Existing05b1828/helper66 instruction bytes
match objects completely. Target pool240 includes98 bytes of wide arithmetic;
retain all64 bytes of caller end/setup/call/reload in the budget.

Propose16-bit directory differences with explicit upper-byte refusal, retaining
all reads and other checks at the same05b decision. Same context/end helper
interface; byte-indexed cursor via offsetof avoids moving address work into
caller. Algebraic equivalence over24-bit base/offset and16-bit start/length;
4,117,976 predicate cases and589,806 byte-max model cases pass, no C execution.

Instruction-width worksheets122/33 are not measured compiler output. Allocate
caller pool185 (63 bridge/spill allowance), helper50 (17 codegen allowance),
plus16 other05b and8 other resident drift. Targets save55/16; hard05b1792 and
ordinary784 caps unchanged. Region0 ceiling65205 and every floor retained.
Next one isolated C form, matched objects/all-record packing before actual C
fault/lifetime gates; halt on overrun or unbound successor. No product attempt.
Zero compiler/dependency/assembler/link/Seed/guest/device this analysis;
consumed5/0/5, ceiling5/1/5. Card L/public2.4.0 unchanged.
Seal `set-b-front-abi-20260926.json`.

### Set B fused05b/resident-max: dual capacity halt — 2026-09-26

Owner “Dann bitte gemäß deiner Empfehlung fortfahren” continues `d31cb37a`.
[Report](set-b-front-fused-report.md). One isolated form restores05a/Entries,
retains04+15 and folds range refusal into05b's existing row predicate, then
calls the resident pending-max helper. Ten matched object compiles and ten
native dependency calls exit0;26 changed/157 unchanged allocated sections.

Halt before C: helper66 exceeds58 by8;05b+176 exceeds137 by39 (linked
projection1831/1792). Ordinary792 leaves24/floor32. All-record aligned region0
65269/65536 has267free but exceeds the design ceiling65205 by64. Region3
6784/8192; E000/BSS/capture remaining25/1/48. Other measured deltas match the
prior relocation; exact05a/Entries bytes/relocations restored. No floor waived.

Combined new cost242 versus old270 saves28; at least47 more bytes must be
removed,39 overlay and8 resident. Next proposed read-only joint disassembly/
ABI cost audit, including caller setup and helper cursor-address formation,
before another form. No new compilation at that next analysis step. Actual C
error/lifecycle and native cold/stack/GC gates remain open. No product attempt.
Zero host C/build/link/Seed/guest/device; consumed5/0/5, ceiling5/1/5. Card L
accepted, public2.4.0 unchanged. Seal `set-b-front-fused-20260926.json`.

### Set B error-order contract: restore05a, fuse refusal at05b — 2026-09-26

Owner “Dann bitte gemäß deiner Empfehlung fortfahren” continues the read-only
recommendation of `39af7c16`. [Report](set-b-front-order-report.md). Stable boot/
reservation metadata excludes the synthetic range fault; arbitrary late writes
and transport faults remain unclosed, so no domain waiver. IO1/ENTRY5 map to
BAD BYTECODE conditionally through normal transport/rollback; this is source
attribution, not executed diagnostic-state equality or a tolerance.

An added05a base read can itself reverse precedence. Proposed form restores05a
and retains04's measured+15 seed; fuse the domain predicate at05b's existing
row decision, then call a resident pending-max helper. No read/error point or
terminal publication moves. 4,117,976 predicate cases and2,268 order-model rows
pass; these are specification models, not candidate C or lifecycle proof.

Helper plus all resident drift cap58;05b growth cap137. All-record aligned
region0 ceiling65205/65536,331free; E000/BSS/capture margins25/1/48 retained.
Old05b270 requires at least75 net bytes saved even with all58 resident bytes;
fit/cycles/stack unmeasured. Next recommendation: one isolated form, objects/
packing first, actual C fault and lifecycle rows only if it fits. Halt on an
owner/floor failure or unbound successor. No product integration/attempt.
Zero compilers/dependency calls/builds/links/Seeds/guest/device this commission;
consumed5/0/5, ceiling5/1/5. Card L/public2.4.0 unchanged.
Seal `set-b-front-order-20260926.json`.

### Set B04/05a relocation: capacity pass, C error-precedence halt — 2026-09-26

Owner “Dann bitte gemäß deiner Empfehlung fortfahren” continues `775c4083`.
[Report](set-b-front-relocation-report.md). Isolated guard initialization and
05a accumulation fit:04+15/96,05a+328/352; exact05b/Entries restored. Ten native
object/dependency calls each pass,25 changed/157 unchanged allocated sections.
Text726/E00036/BSS4 retain margins58/25/1. All-record aligned packing gives
region0 65397/65536 (139free); region3 6784/8192. No linked product generated.

Actual extracted04/05a/05b C passes39 rows, then halts: execution base60758 plus
entry0 length7 and a later entry1 source-read failure yields candidate ENTRY5;
maintained and previous parked forms yield IO1. Faults target semantic reads,
not shifted call numbers. Synthetic bad execution coordinate: full-chain
reachability and final VM mapping unbound, not a new reproduced product defect.
No tolerance; terminal/lifecycle/full BAD BYTECODE/native gates not continued.

Packing r1 double-counted existing late padding; r2 corrects it with bound
executed source. Host fixture r1 fails unsigned-compare warning; r2 fixes only
scaffold, keeps -Werror. All failures retained. Two host compile attempts,
one success/link, one host dependency call. Zero product build/link/Seed/
guest/device. Consumed5/0/5, ceiling5/1/5; Card L/public2.4.0 unchanged.
Next proposed read-only error-domain/phase-order analysis, preserving failure
precedence and pricing retention of refusal at05b. No new implementation or
product attempt before that contract closes. Seal `set-b-front-relocation-20260926.json`.

### Set B front placement: conditional04/05a form with aggregate cap — 2026-09-26

Owner “Dann bitte gemäß deiner Empfehlung fortfahren” continues the read-only
recommendation after `9a9789b1`. [Report](set-b-front-placement-report.md).
Initialize pending max in the existing04 source guard after validation and
Entries context copy; accumulate in05a, reusing dead header bytes for the
three-byte execution base and existing32-bit at. Restore05b/Entries bodies;
keep later cross-binding and terminal publication. No candidate C generated.

Local air388/665 is not the aggregate budget: Session region0 is65045/65536,
only491free. Proposed delta ceilings04+96/05a+352 give aligned growth448,
maximum65493,43free. These are caps, not measured sizes. No extra overlay
calls/catalog slots/BSS/declarations; stack spills and input stability open.
Conditional INIT adds8 reads/24bytes across8 images;804existing entry visits,
larger transport/CRC/wipe work and cold gate unmeasured.383657 arithmetic
boundary cases,804 captured-coordinate equalities,256 max-composition cases;
three numeric counterexamples and three stated fault obligations, no C proof.

Next proposed isolated04/05a form: matched object plus packing gates first,
then integrated C semantic/fault rows only if every cap fits. New read-fault
precedence/raw-I/O/exact-error gates stay open. No product attempt or sixth
Seed. All74 roots verified; zero compiler/build/link/guest/device in this
commission. Consumed5/0/5, ceiling5/1/5; Card L accepted, public2.4.0 unchanged.
Seal `set-b-front-placement-20260926.json`.

### Set B isolated front integration halts at two overlay owners — 2026-09-26

Owner “Dann bitte gemäß deiner Empfehlung fortfahren” continues `6fcd8207`
with isolated hooks/decoder source and matched object pricing.
[Report](set-b-front-integration-report.md). The parked candidate reuses the
r2 helper, adds terminal-publication/invalidation hooks, seeds the dead decoder
cursor from the old full-prefix scan, accumulates in05b and brackets raw poke.
Eleven source assertions pass; lifecycle semantics/raw-I/O closure remain open.
Generator r1's preprocessor-brace extraction failure is retained; r2 succeeds.

Six object compiles/six dependency calls exit0;25 changed allocated sections,
153 unchanged. Text726 (+100 over wrapper), air90/floor32, margin58; BSS4,
air6/floor5, margin1; E000+36, air79/floor54, margin25. Scanner unchanged.
**Halt:**05b+270 projects1655→1925/1792,133short; Entries+34 projects1771→
1805/1792,13short. Raw objects also exceed the slice limit. No integrated C
fixture, full writer audit, runtime, cold or product gate claimed. No new
product defect; no validation relaxed to fit.

Next proposed host-only read-only ownership/lifetime and capacity plan for
sharing/moving the max calculation and seed initialization, with all call/
transfer/scratch costs. No further implementation or product attempt on this
failed form. Product sources unchanged; zero product build/link/Seed/guest/
device. Consumed5/0/5, ceiling5/1/5; Card L accepted, public2.4.0 unchanged.
Seal `set-b-front-integration-20260926.json`.

### Set B shared-scanner r2 passes isolated C and object envelope — 2026-09-26

Owner “Dann jetzt fortfahren bitte” continues `9a8f04cf` with isolated host C
fixtures and matched non-LTO objects. [Report](set-b-shared-front-report.md).
R1 costs580text/3BSS but actual C longjmp controls expose abandoned marker
and LAST_SLOT restoration gaps. Preserved as a prototype counterexample,
not a new product defect or Seed. R2 adds a persistent saved trace byte and
REFILL ownership bit; its abort hook cleans up before existing forced releases.
That hook order is supplied by the fixture, not installed in the product.

R2 passes4,554 C rows plus2,421 full scratch-lifetime fault rows; tests include
occupied owners, header/table guards, pre/post-entry transport failure, latched
fault persistence, missing DONE, allocator scratch reuse, nonlocal cleanup
and reentrant refusal/raw notification during refill. Exact existing scan and
entry execute; loader/cons/runtime and product recovery remain declared seams.

R2 objects: query448+helpers153+VM25=626text,266saved from892. Free816→190,
floor32, remaining158. BSS4: air6/floor5, only1byte above floor. Existing scanner
record1743/1792 is among162 unchanged allocated sections. Control+83/reset−3
inherited; session extent6784/tail1408, journal72. No linked-size/time claim.

Next proposed host-only work: complete writer/raw-I/O hooks, decoder maximum
and abort ordering in an isolated source tree, then price every affected owner.
Space/stack, real INIT/cold cost, transport/error and product consumer gates
remain open. No product integration or sixth Seed admitted. Consumed5/0/5,
ceiling5/1/5; Card L accepted, public2.4.0 unchanged. Eight object compiles/eight
dependency calls, two host C compiles/links; zero product builds/links/Seeds/
guests/device. Seal `set-b-shared-front-20260926.json`.

### Set B existing scanner offers conditional reuse; lifetime audit complete — 2026-09-26

Owner “Dann bitte gemäß deiner Empfehlung fortfahren” continues `5960ef83`
read-only. [Report](set-b-scanner-reuse-report.md). All74 bound compiler roots
verified. Exact fifth-Seed inventory confirms Session29 entryC356 (321bytes)
and scannerC497 (1422bytes), record1743/1792, air49. The existing request62
scans and publishes done64 without running the reservation branch. Set
transient_first2048 to inspect only the persistent prefix; retain actual
header/count/generation validation and additionally guard entries_offset2096.

Exclusive APPEND scratch is required. Copy low out before release/cons;
never call an unloaded overlay address. Existing entry overwrites diagnostic
LAST_SLOT at C1F4 even if locked, so preserve it on normal returns and bind
nonlocal-abort provenance. Transport checks/wiping remain mandatory; failed
transport may latch a fault even after the entry wrote DONE. No latch reset,
READY-clear or new fatal path proposed. Caller/auth-state proof remains open.

With unchanged helpers103+VM25, the entire new query plus further integration
must fit656 resident bytes. At least108 bytes net reduction is needed before
hooks. Actual saving and cold cost are unmeasured: zero compiler/object/
product/guest/device calls. Next proposed isolated host C wrapper/scan fixture
and matched object pricing must close trace/latch/abort successors first;
no product integration or sixth Seed. Consumed5/0/5, ceiling5/1/5; Card L
accepted, public2.4.0 unchanged. Seal `set-b-scanner-reuse-20260926.json`.

### Set B isolated certificate C passes; resident object admission halted — 2026-09-26

Owner “Bitte fortfahren” continues `117e925b` with the isolated host-only
prototype. [Report](set-b-front-prototype-report.md). Exact parked C passes
4,536 rows: all 2,049 legal counts, 2,421 partial transport failures,
invalidation/abort/refill, raw taint and warm-header successors. Missing-hook
control deliberately returns stale data; it proves no product defect or
complete writer coverage. Actual publication callers remain fixture stubs.

Prototype policy: every notified raw write disables reuse until trusted boot;
successful refill/publication cannot remove taint. No public contract is
adopted. Abort invalidates instead of restoring a pending cursor. No READY
clear, fatal boot path, new GC root or borrowed scratch in the kernel.

Matched native objects: query764, state helpers103, VM25 = **892 resident
bytes**, versus784 available above floor: **108 short**. Projected text air
−76/floor32; BSS3 fits (air7/floor5). Inherited control+83/reset−3 and session
extent6784/tail1408 unchanged projection. All other162 allocated sections
match. Actual hooks and decoder accumulator are absent and unpriced.

**Halt before integration.** No assumed LTO saving or host protocol trace
substitutes for native placement/cold proof. Next proposal: host-only read-only
ownership/lifetime plan for sharing the existing scanner, including overlay
dispatch and scratch discipline before implementation. Scanner-record air49.
No sixth Seed or new product budget requested. Consumed5/0/5, ceiling5/1/5;
Card L accepted; public2.4.0 unchanged. Four object compiles/four dependency
calls, one host C compile/link; zero product builds/links/Seeds/guests/device.
Seal `set-b-front-prototype-20260926.json`; tools and receipts committed.

### Set B validated-front design complete; writer/refill/fault binding still open — 2026-09-26

Owner “Dann bitte gemäß deiner Empfehlung fortfahren” continued `5f9309fb`
as a pure host design/writer audit. [Design](set-b-front-certificate-design.md).
74 existing compiler roots verified;53 direct sink calls/44 owners classified,
zero unclassified direct edges. This is NOT complete indirect/raw-I/O proof.
324 Python model rows include key-ABA, malformed warm-hit and nonlocal recovery
falling controls. No product defect is inferred from these proposed-cache
counterexamples. Audit r1's incorrect macro-provenance assertion is preserved;
r2 binds the actual compiler target cfg and vm.c conditional.

Preferred conditional certificate: front16/state8 (3 new BSS bytes), high
BSS air10→7/floor5. Pending maximum may reuse entry_cursor only under a new
phase contract; journal reconstruction copies CURRENT cursor into predecessor,
so nonlocal recovery must invalidate/refill, never restore it as an undo value.
Seven-byte generation/count/front/flag form fails BSS floor. Phase05b has137
bytes air, existing scan slice49; keeping old scalar refill leaves only97 of
784 resident bytes for other changes. These are envelopes, not new code prices.

Conditional INIT trace785/801/801/804 requires zero additional entry scans
instead of3191 rows, using804 already-validated decoder visits and4 header
reads. No native cost or cold pass. Public poke/raw I/O mediation and warm
fault successors remain explicit binding gates; eliminated read cutpoints
cannot be relabeled passed. Next proposed host-only card: bind those policies,
prototype barriers/recovery refill, then matched-object price; zero product
builds/links/Seeds/device. No implementation or further product budget here.
Consumed5/0/5, ceiling5/1/5; Card L accepted. All compiler/object/product/guest/
device counts zero. Seal `set-b-front-certificate-design-20260926.json`.

### Set B six-entry batch query halted on object air and copy cost — 2026-09-26

Owner “Dann bitte gemäß deiner Empfehlung fortfahren” continued `d8719dc4`
host-only. [Report](set-b-library-load-batch-report.md). Exact candidate C
passes2725 rows: all2049 legal counts,408 empty/partial/full failed reads,
malformed batch boundaries and seeded mutations. All source bytes unchanged.
Lisp/VM/prefix candidate files are byte-identical to prior native form;
canonical packing and indexed SBCL receipts reused, not re-executed.

60-byte automatic batches reduce INIT reader calls3195→537 but retain31942
copied bytes. Existing fifth ELF's exact copy loop alone has floor349751
cycles/8.635827ms versus277701/6.856815ms available, before setup/validation/GC.
Gross added-work bound, not a new boot measurement or future LTO total.
Matched objects need query828+VM25 resident bytes: textair816→−37/floor32,
69bytes short. Frame68bytes (+51 versus prior unlinked helper); buffer lifetime
is local/synchronous, whole linked-stack safety remains unqualified.

**Halt, no sixth Seed.** Next proposed host-only design: validated-front
reuse certificate, complete writer/invalidation audit, owner storage and
remaining-scan price before implementation. No weakened checks or cold gate.
Consumed5/0/5, ceiling5/1/5; Card L accepted. No extra product budget requested.
Four object compiles/four dependency calls, one host C compile/link; zero
product builds/links/Seeds/Finals/device/guests, no new Lisp/SBCL executions.
Seal `set-b-library-load-batch-20260926.json`; all qualification remains open.

### Set B load preflight closed; native query still lacks cold-cost admission — 2026-09-26

Owner “Dann bitte gemäß deiner Empfehlung fortfahren” continued `519a1be2`
host-only. [Report](set-b-library-load-preflight-report.md). No product
build/link/Seed/device/guest; fifth ELF139e7775 and medium587136f5 unchanged.
Canonical before code AND metadata reproduce the consumed stdlib. Full
Lisp scan costs +214 code/+2 entries/+15 resolutions/+0 roots; native query
+57/+0/+3/+0. Both pass eight indexed SBCL cases (twelve requires), including
INIT and fast-note repeats. Captured publication replay is explicit; native
query seam is modeled, with independent actual-C proof: 1,019 fault/oracle
rows pass. Three failed reference-VM instruments are preserved and discarded.

Exact INIT scans785/801/801/804 entries. Full Lisp gross leaf floor823278
cycles (20.328ms) exceeds remaining277701 (6.857ms). Cheaper native form
still projects478650 cycles (11.819ms), before reader/caller/GC. This latter
number is a non-LTO object instruction floor, NOT a bound on an unbuilt LTO
ELF or a native cold measurement. No cold admission can be claimed.

Parked five-file native proposal r2: query662 + VM25 resident bytes;
text816→129/floor32; control+83/reset−3; extent6784/tail1408. Resident total
would439→1126, not admitted. Prefix correction retained; READY unchanged.
**Halt before a sixth Seed.** Next proposed host-only work: bounded batch
query with scratch/stack, full validation and cost/air proof; no additional
product budget requested. Consumed5/0/5, ceiling5/1/5; Card L accepted.
Seal `set-b-library-load-preflight-20260926.json`. Eight native object and
eight dependency calls, four canonical Lisp compiles, one host C compile/link,
two SBCL executions. Product consumer routes/native qualification remain open.

### Set B library-load refusal attributed; repair parked before timing/packing preflight — 2026-09-26

Owner “Freigabe erteilt” continued the existing-Seed attribution proposed in
`19738af1`. [Report](set-b-library-load-attribution-report.md).
Unchanged fifth ELF139e7775/medium587136f5: fresh load T, one definition T,
one replacement then load NIL. Executed predicates isolate the Lisp
resolver's contiguous-code assumption: image8 baseC60D versus expectedC603;
retired ten-byte object remains charged. Generation/reserved/source pass;
changing only the test argument makes the row pass. C2D/Bank2 unchanged at
refusal; capacity arithmetic leaves 9009 code bytes after this library.

Protected-prefix discrepancy confirmed: reset latches six before INIT;
step2 requires actual prefix at first prompt (eight). Parked three-file
repair admits nonoverlapping gaps, scans all entries including tombstones
for charged high-water, and captures the prefix at first quiescent control.
12 targeted Lisp +10 full world +12 actual-C host rows pass. Lisp+214/two
private entries; native control+83/reset−3;82 other allocated sections same.
Projected tenant extent6784/tail1408 (control record480), no authored resident
or BSS growth. Whole packing/root/resolution closure remains open.

Conservative scan costs423144 host VM instructions/4824 reads on804 entries;
not native timing. Existing cold margin6.857ms makes this a material risk.
**No sixth Seed yet:** propose host-only cost/packing/consumer preflight,
0 product builds/links/Seeds/device, before a replacement budget request.
Consumed5/0/5, ceiling5/1/5; Card L accepted; Set B qualification still halted.
Six guests, two object compiles/two dependency calls, one host C compile/link,
no observer build. All failed harness attempts preserved. Seal
`set-b-library-load-attribution-20260926.json`; canonical offline analysisr2.

### Set B fifth Seed activates and reuses images; library-load halt — 2026-09-26

Owner-admitted resident repair executed on source `e0ea5447`, HEAD
`1f9fda66`. [Full report](set-b-fifth-seed-workload-halt-report.md).
ELF `139e7775…`, D81 `587136f5…`: fresh admission, complete linked inventory
(zero unclassified bytes/relocations), 80-record media, positive boot,
resident transaction boundaries and four disarmed-boot controls pass.
Matched cold pair +0.493143 s versus Card L (limit+0.5 s; margin6.857 ms).
Linked text816/32, E000115/54, capture105/57; extent6752/tail1440.

Fifty prompt-by-prompt replacements keep nine images; 50 old entries retire,
all804 original objects remain identical, last callable returns57. Next
`(require "defstruct")` returns **NIL**, expected T: qualification halts.
READY1/arm86, tenant intact, journal magic0; full C2D/Bank2 unchanged across
the refusal. Internal stage/capacity cause unassigned. Exact BAD BYTECODE
successor separately passes with NIL/42 and intended abort disarm.
Instrument failures, independent halt capture and all artifacts preserved.
No later gates, consumers, full source run or Final. Consumed **5/0/5**,
ceiling5/1/5; no implicit sixth attempt. Card L remains accepted.

Propose next host-only existing-Seed attribution/minimization, zero product
builds/links/Seeds/device; also reconcile the step-2 eight-image protected
prefix against the admitted reset's observed six. No further commission or
replacement started. Seal `set-b-fifth-seed-workload-halt-20260926.json`.

### Set B resident transaction repair admitted; fifth attempt — 2026-09-26

Owner **“Freigabe erteilt”** accepts the concrete proposal in `95d36be5`:
exact two-file resident transaction patch, resident admission **439 bytes**,
unchanged 6752-byte tenant extent / 1440-byte tail, and necessary derived
source/delivery identities. Budget ceiling **5 Seeds / 1 Final / 5 product-link
attempts**; consumed before execution **4/0/4**. Exactly one additional
Seed/link attempt; no implicit retry, member5, device or release.

Dated fifth-Seed producer and Final driver are bound separately from their
historical predecessors. All seven consumer implementations are prepared
before the attempt; their execution/receipt closure and eventual Make routes
remain required. Final is bound to
`build/set-b-transaction-check-source-r1/receipt.json`, after complete
qualification, clean status and exact-HEAD exit0. Fresh symbol/E000 and
object admission precedes the link; complete inventory, actual-CRC media,
positive/negative boot, first-retirement boundary, functional/fault/usage,
lanes/GC, consumers and sealed source follow in the proposal's order.
Card L stays accepted until qualification and review. Preserve every tool
and receipt; report at Final or a halt.

### Set B first retirement refusal traced; resident transaction repair proposed — 2026-09-26

Owner “Bitte genau damit fortfahren” continued the host-only commission in
`38f882d6`. [Attribution and concrete repair](set-b-transaction-boundary-repair-proposal.md).
Unchanged fourth Seed `2ba1deb4…`: reset physical read FF→00, OK, arm86;
first control passes quiescence/root/unwind checks, then begin reads busy1,
returns BUSY3 and control returns STATE8. Prompt remains READY1/arm0,
tenants intact, journal zero. This closes the first-failure attribution.

Two-file patch parked under build: resident helper owns begin/end outside
C356; control retains all data/GC/scratch checks. End failure still permits
cleanup before propagating failure to replay. Eleven actual-candidate host C
ownership/fault rows pass. Matched objects: resident+193, control−47;
81 other allocated sections unchanged, no BSS/slot change. Proposed text
air816/floor32; preserve extent6752/tail1440. Resident admission246→439
requires a new binding, not a floor relaxation.

Commission complete; maintained native sources unchanged. One guest, two
object compiles, two dependency-only calls, one host C test compile/link;
zero product links/Seeds/device. Seal
`set-b-transaction-boundary-repair-20260926.json`. Consumed4/0/4; proposed
replacement ceiling5/1/5 requires owner word. No attempt started. Card L
accepted; product qualification remains halted, no member5/device/release.

### Set B fourth Seed inventoried; positive activation halts — 2026-09-26

Owner-admitted reader correction executed on source `958a7d2a`, HEAD
`8c0f3289`. [Report](set-b-fourth-seed-activation-halt-report.md).
ELF `2ba1deb4…`, D81 `a4c24c8a…`: fresh admission, complete physical ELF
inventory (zero unclassified bytes/relocations), 80-record host readback
and three falling host controls pass. Canonical tenant extent6752/tail1440;
text1009/32, E000115/54, capture105/57, highBSS10/5.

One positive guest reaches `LISP65>` with READY1 but retirement arm0;
no arithmetic form or later gate executed. Full tenants intact, journal
zero. Linked control's transaction-begin call conflicts with the executing
overlay busy guard; this is a proved static conflict, not an executed
first-failure trace. Reset and earlier predicates remain untraced on this
ELF. Qualification halted, no retry. Budget consumed **4/0/4**, ceiling
**4/1/4**. Card L Final remains accepted; public2.4.0 unchanged.

All new tools, commands, receipts and artifacts sealed in
`set-b-fourth-seed-activation-halt-20260926.json`. Next proposal: host-only
trace of reset/first retirement on this existing ELF, then price a correct
transaction boundary; zero new Seed/product links pending a new binding.
Consumer routes are prepared, actual successor closure/source run/Final
remain unexecuted. No member5, device or release claim.

### Set B read-path replacement admitted, fourth attempt — 2026-09-26

Owner word: **“Freigabe erteilt”**, accepting the concrete repair and
additional Seed/link attempt in `76cc19b7`. The cumulative ceiling is now
**4 Seeds / 1 Final / 4 product-link attempts**; consumed before this
continuation **3/0/3**. Exactly one further Seed/link attempt, no implicit
retry. The accepted world remains Card L until qualification/review.

Apply the four-file physical-reader patch exactly as priced; journal read
64+8, no selector broadening. Canonical slot59 extent1024, slots60/61/62
offsets4448/5856/6496, total6752/tail1440. Derived source bindings and every
actual delivery/CRC identity follow this form. No member5, device, release,
root removal, tolerance or floor relaxation. Fresh object/symbol/E000 and
packing admission precede the attempt; complete inventory and the ordered
executed gates in [the proposal](set-b-read-path-repair-proposal.md) follow.

Historical producer and sealed tools stay unchanged; the dated fourth-Seed
successor owns the new source authority and output roots. Consumer successor
routes are enumerated before the attempt and must all close before the first
sealed source run. Final driver is bound now to
`build/set-b-read-repair-check-source-r1/receipt.json`, with a hard prerequisite
for the complete qualification closure, exact-HEAD exit0 and empty porcelain.
Report at Seed, Final or a halt; preserve every attempt and receipt.


### Set B read-path repair designed; replacement budget proposed — 2026-09-26

Owner continuation: “Alles klar. Bitte weitermachen”, for the host-only
repair design proposed in `f8d98e3d`. The existing Seed boundary trace now
proves the first reset refusal: return identity `$C3F6` reaches `$2374 JMP
$2B00`, the read destination stays `$FF`, reset returns C2D error3, then
main publishes READY=1 with retirement disarmed. This resolves the earlier
static evidence limit; no new product defect class or tenant damage found.

[Repair proposal](set-b-read-path-repair-proposal.md): call the existing
synchronous physical reader directly from the four C356 overlay owners,
using its canonical declaration; split journal read 64+8. Matched objects:
+25 code bytes only in prepare, +32 canonical delivered bytes, 1440-byte
late tail. Four consumed include differences, 79 unchanged allocated
sections, no BSS/slot growth or E000 change. Patch parked under build and
preserved by the seal; maintained native source and accepted world unchanged.
Two object compiles, two guest launches (one rejected tool trace), zero
product links/Seeds/device contacts. All failed analysis assumptions retained.

Commission complete. Product qualification remains halted, Card L accepted.
Proposed replacement budget: **+1 Seed / +1 product-link attempt**, retaining
one unused Final; cumulative ceiling **4/1/4**, consumed **3/0/3**. This is
not yet granted. Exact source/derived scope, owner air and ordered gates are
in the report. No member5, device or release admission. Seal
`set-b-read-path-repair-20260926.json`.


### Set B inventory closed; positive-medium activation halt — 2026-09-26

Under the owner's existing-Seed continuation (`8a3eac10`), the full inventory
of ELF `1eb22d52…` closes with zero unclassified bytes/relocations. All 373
unchanged inherited function symbols have full instruction/target proofs;
ten admitted access widenings cost +10 bytes. All 80 delivered catalog
records and three disk controls pass independent host readback. Positive
Comfort medium `3fafddc9…`; no new product compile or link.

The sole emulator launch reaches `LISP65>` with READY=1 but the retirement
arm latch is 0: **positive activation gate red; qualification halted**.
Shutdown memory proves all 8,192 tenant bytes intact and the journal zero.
Static linked attribution shows reset and three commit readers calling the
context-selecting facade with unrecognized return identities; they route
to overlay execution instead of physical read. No executed boundary trace
or first-failing-instruction claim. [Report](set-b-seed-qualification-halt-report.md),
seal `set-b-seed-qualification-halt-20260926.json`.

Cumulative charge remains 3 Seed attempts / 0 Finals / 3 product-link
attempts; four delivery-stager links, one guest launch, no device contact
in this continuation. Card L Final stays accepted, release 2.4.0. Proposed
next commission: host-only read-path repair design/ABI and owner-price proof
on this ELF, 0 new Seeds/links, optionally an executed boundary attribution
on this same medium. Any native correction needing another product link
requires a new budget binding. No forced arm, CRC tolerance, member 5 or
further qualification behind the red gate. Full source run/Final unstarted.


### Set B existing Seed: zero-page access family admitted — 2026-09-26

Owner word: “Dann bitte gemäß deiner Empfehlung fortfahren”. This admits
only the ten extra instruction bytes caused by `vm_buf_off` moving from
zero page to ordinary BSS in existing Seed ELF
`1eb22d5282acae5e39c1a1ea37bd749d6e524c9fb45005791b298a26bb5b71cf`.
The named family is LDX/STX/STY zero-page-to-absolute access widening in
`eval_init`, `vm_buf_ensure_mine`, `vm_buffer_call`, and `vm_run_inner`;
code cost +2/+4/+2/+2 bytes. Full instruction, branch-target, relocation
and complete linked-byte inventory proof remain required. Unexplained
changes still halt. No source repair, additional Seed or product link is
authorized; cumulative charge stays 3 Seed attempts / 0 Finals / 3 links.

Continue inventory on the existing artifact, then media/CRC/control and
Comfort preparation, executed boot/capacity/retention/recovery/lanes/GC
gates, consumer successors, fresh exact-HEAD sealed full check and Final
under the existing binding. Member 5, device contact and release actions
remain excluded. The preceding halt receipt is preserved. Card L Final
remains accepted until qualification and review close.

### Set B third Seed linked; zero-page spill inventory halt — 2026-09-26

Authorized by owner word at `7c659dfd`, source authority `7a4e43fa`:
[halt report](set-b-third-seed-inventory-halt-report.md). ELF `1eb22d52…`
links and extracts seven tenants successfully. Actual text free 1009/32,
E000 115/54, capture 105/57; helper/consumer margins 36/59. Padded tenant
extent 6,720 = 6,416 code + 304 zero padding, tail 1,472. All geometry gates
pass. Cumulative charge **3 Seed attempts / 0 Finals / 3 product-link
attempts**, one successful link. No fourth attempt or product execution.

Inventory halt under the “outside the members” rule: new Set B latches
occupy two zero-page bytes; `vm_buf_off` moves `$5C–$5D` → `$BB67–$BB68`.
Ten matched LDX/STX/STY accesses widen to absolute addressing in unchanged
`eval_init`, `vm_buf_ensure_mine`, `vm_buffer_call`, `vm_run_inner` bodies
(+2/+4/+2/+2 bytes). Exact fields/registers and encoded addresses are proved;
no full-inventory or behavioral closure is claimed. Recommend a binding
decision on this named codegen family/cost **on the existing Seed**, followed
by complete inventory with 0 additional links. Media and all executed gates
wait behind inventory closure. Card L remains accepted, release 2.4.0.
Seal: `set-b-third-seed-inventory-halt-20260926.json`.

### Set B third Seed/link authorized — 2026-09-26

Owner word: “zusätzlicher Versuch freigegeben”. This admits source revision
`7a4e43fa`, including the E000 section move and the canonical zero-padded
tenant geometry described in [the placement report](set-b-placement-revision-report.md),
and **one additional Seed with one additional product-link attempt**.
Cumulative ceiling is **3 Seed attempts / 1 Final / 3 product-link attempts**;
the first two attempts remain charged. No fourth Seed/link is implied.
The producer AUTH pointer is rebound to `7a4e43fa`. Fresh outputs use
`build/set-b-product-r3/` and `build/set-b-r1/step4-r4/`.
All actual linked placement, floor, inventory, CRC, media and executed
gates remain required, followed by the exact-HEAD sealed check and Final.
Report at Seed or halt. Member 5 and device contact remain excluded.

### Set B placement revision host-closed; third Seed unbound — 2026-09-26

Owner continuation “Dann fahr bitte direkt fort” commissions the preceding
0/0/0 placement round; [report](set-b-placement-revision-report.md).
Two matched non-LTO objects prove the 40-byte `c2_overlay_call` can move
from resident E000 to existing `reopen_gap1` with identical instructions
and relocation operands, no new E000 edges, and zero total code/BSS delta.
Projected helper margin is 36 bytes at unchanged `$FD22`; receiver/consumer
margin 59, capture air 105/57, E000 air 115/54, reopening debit 323/450.
All linker rules stand. Seven canonical 32-byte backing intervals reserve
6,720 bytes; record payloads include authenticated zero padding and leave
1,472 tail bytes inside the same 8,192-byte owner. Existing validator and
builder agree; 9 host checks and 7 negative controls pass. Initial probe
basename false red, superseded 16-byte proposal and descriptive metadata
refresh are preserved. No executable Seed, product link, emulator or device.

Maintained source/descriptors/producer are revised; `AUTH_PENDING` keeps
Seed admission closed. Cumulative charged budget remains 2 Seed attempts /
0 Finals / 2 product-link attempts. Proposed next binding: one additional
Seed/link, existing Final allocation retained, cumulative ceiling 3/1/3.
No third link is yet authorized. Card L Final remains accepted; public
release 2.4.0. Seal: `set-b-placement-revision-20260926.json`.

### Set B authorized replacement: placement halt — 2026-09-26

Under `7bef0c2c`, producer pointer `9c54936f`, clean execution HEAD
`f4ec7c98`: [replacement halt report](set-b-replacement-seed-halt-report.md).
The journal syntax is corrected; product-link command 75 now fails the
unchanged Comfort helper placement ASSERT. Resident growth is exactly
+31 (`c2_overlay_call` +11, `c2_product_gc_mark_roots` +20), shifting the
unchanged helper end from `$FD07` to `$FD26`, four bytes beyond `$FD22`.
The map/LTO object also confirm slots 59 and 61 each exceed their backing
interval by four bytes. No product ELF/PRG was produced. No tolerance,
third link, media, emulator, device or Final. Cumulative charged budget:
**2 Seed attempts / 0 Finals / 2 product-link attempts**, zero successful
product links. Card L Final remains accepted; public release 2.4.0.
All failed evidence is preserved; seal `set-b-replacement-halt-20260926.json`.
Proposed next commission is a host-only 0/0/0 placement revision for both
constraints before any further Seed/link budget is bound. That revision
has not been executed. Member 5 and all behavioral gates remain unchanged.

### Set B replacement Seed/link authorized by the owner — 2026-09-26

Owner word following halt `9e946c38`: “Freigabe erteilt”. This admits the
isolated one-character linker-script correction (remove the trailing
semicolon from the journal ASSERT inside SECTIONS), a refreshed committed
source authority, and **one replacement Seed with one additional product-link
attempt**. The first attempt remains charged and immutable. New execution
outputs: `build/set-b-product-r2/`, `build/set-b-r1/step4-r3/`.
Cumulative ceiling is now **2 Seed attempts / 1 Final / 2 product-link
attempts**; no third Seed/link is implied. All linked placement, inventory,
air, media, executed and exact-HEAD Final gates stand unchanged. Member 5
and device contact remain excluded. The admitted predicate, journal owner
and product C/Lisp sources are unchanged by the syntax correction.

### Set B step 4: first Seed halted by linker-script syntax — 2026-09-26

Execution of handover `bad4c939`; [halt report](set-b-seed-link-halt-report.md).
Authority, undefined-symbol and E000 object probes pass. Delivered Card L
catalog capacity is 56→63 Session / 17 Boot with no directory growth;
exact tenant placement remains a linked gate (slots 59 and 61 both have
four-byte projected interval overruns). The ONE Seed invoked 74 successful
compiles and one LLVM aggregation; product-link command 75 failed parsing
the newly semicolon-terminated journal ASSERT inside `SECTIONS` in `c.ld`.
The parent `commodore.ld:16` is where the parser reports `malformed number: }`.
Two reduced parser fixtures prove the cause; a one-character patch is
prepared but not applied. No ELF, PRG, map or LTO link output was produced.

Charged: **1 Seed attempt / 0 Finals / 1 product-link attempt**. Replacement
Seed uninvoked. Per the binding, a correction requiring another link halts
for rebinding; no retry. Source authority and accepted Card L world are
unchanged. No media, emulator, device, full sealed check or Final. Seed tools,
failed receipts and diagnostic fixtures are preserved under
`build/set-b-r1/step4-r2/`, sealed by `set-b-seed-link-halt-20260926.json`.
The media adapter's stale READY=0 journal prescription is also recorded for
correction to the step-3b matrix before future qualification, not executed.

### Handover to Codex — 2026-09-26

Claude's usage limit is reached; Codex/GPT takes over for a few days.
Reading order and exact resume point (Set B step 4: the ONE Seed, 0 of the
budget consumed, HEAD `0de1ecba`): [codex-handover-2026-09-26.md](codex-handover-2026-09-26.md).
Member 5 (promotion) stays excluded pending the owner's word.

### Set B step 3/3b: fail-closed corrected, resident bound raised to 246 for the safety logic, source authority committed — 2026-09-26

Reviewer review of Codex's step-3 authority found two sites that would
have reintroduced the session-loss class: boot aborting on a failed
tenant staging or journal reset, and `c2_retire_run` clearing `c2_ready`
on a tenant failure. Step 3b corrected them: staging/reset failure leaves
retirement **disarmed** and the boot reaches READY exactly as on Card L
(the Card L controls stay green); a failure inside scan/commit runs the
journal forward replay first, then disarms retirement for the session
with READY untouched; only a failed replay uses the existing fail-closed
sink, as an explicit gate row (`build/set-b-r1/step3/step3b-gate-matrix.json`).
Slot 56 mode 4 disarms only; slot 62 arms only after a successful readback;
the arm bit lives in the protected-prefix BSS byte (still +2 BSS).

Price after 3b (projections): slices 423 / 1,531 / 1,376 / 964 / 1,362 /
612 / 211 (all ≤ 1,792); resident `c2_retire_run` 155, `repl` +35,
`c2_product_boot` +19, `c2_product_abort_recover` +3, `c2_overlay_call`
+11, `c2_product_gc_mark_roots` +23 = **246 bytes, 5 over the bound of
241**. Decision: **the bound is raised to 246** — the five bytes are the
replay-then-disarm logic, and a smaller number would be bought with the
session-loss behaviour just rejected; ordinary text free projects to
about 984 (floor 32). Slot 59 grew past its old 960-byte placement
interval by four bytes; placement is requalified at link (a link gate,
not a rebind). Everything else of the 2026-09-26 binding holds.

Source authority for members 1–4 is committed with this entry (member 5
still excluded, awaiting the owner's word); the producer's `AUTH` is set
to the authority commit in the following commit. Next: Seed (Codex,
budget 1/1/1 + one attributed replacement), price and complete inventory,
media with the seven tenant records and the four control media, then the
reviewer's rows (tenant-byte watch, disarmed-boot controls, abort
injection matrix incl. replay-then-disarm and replay-failure, capacity
9→63→64/64→refusal, retained handles valid across a retirement, lanes,
GC, regressions), successors before the sealed run, Final.

### Set B step 2b: partition accepted, binding numbers adjusted (reviewer decision) — 2026-09-26

Step 2 (`build/set-b-r1/step2/`) resolved the five prerequisites and they
are the design: (a) at 64 reachable images a replacement gets the clean
`OUT OF MEMORY` with a live prompt, never a partial publication (host model
reproduces 9 → 63 → 64/64 → refusal); (b) retirement runs only at the
native prompt boundary immediately after a collection, with no live form
frame and no transient image; (d) root literals of retired images stay
**charged, not compacted** (root plane 3,072 bytes unchanged, zero release
code); (e) a **72-byte before-image journal with forward replay per
victim**, host model green over 6,637 initial-write and 6,272
recovery-write cuts. Step 2's real prices (scan 2,521, commit 2,757,
resident 750) broke the binding; step 2b (`build/set-b-r1/step2b/`)
re-partitioned:

| Slot | Tenant | Bytes |
|---:|---|---:|
| 56 | control: prompt admission and GC | 431 |
| 57 | scan A: cells and symbols | 1,531 |
| 58 | scan B: roots, resolutions, victim | 1,376 |
| 59 | commit A: prepare and recovery read | 953 |
| 60 | commit B: invalidate, load, move | 1,356 |
| 61 | commit C: final publication and disarm | 602 |
| 62 | boot journal reset | 203 |

Resident +223 bytes (`c2_retire_run` 124, `repl` +35, `c2_product_boot`
+24, `c2_product_abort_recover` +6, `c2_overlay_call` +11 mapped,
`c2_product_gc_mark_roots` +23 mapped) — within the bound 241; ordinary
text free 1,196 → 1,007; BSS +2 (protected-prefix latch, GC read-failure
flag); Bank-5 tenant extent 6,528 of 8,192; the 72-byte retirement journal
lives in the 96-byte gap `$5DE20` (24 unassigned); Session records 63 of
64 (seven tenants 56–62); Boot 17 of 64; region 0 untouched (491 free;
slot 55 shrinks by 67 bytes, not credited).

**Binding adjusted:** seven late-region tenant slots 56–62 instead of two;
the gap owner `card_l_gap` carries the retirement journal; the capacity
watch now reads **Session 63 / 64, one slot left** — every later Session
slice needs a slot plan first. No ceiling is raised. Member 5 (promotion)
still awaits the owner's word and is not part of the source authority.
Next: step 3, source authority for members 1–4 prepared by Codex as staged
changes (authority diff plan `build/set-b-r1/step2b/authority-diff-plan.md`),
committed by the reviewer; then producer, Seed, price, inventory, media
(tenant records replacing the marker), reviewer rows incl. the
abort-injection matrix of (e), successors, sealed run, Final.

### Set B bound on the Card L world, with Card L2 (late-region tenants) folded in — 2026-09-25

Reviewer decision under the delegation, on `set-b-carrier-plan.md` (Codex,
receipts `build/set-b-carrier-plan-r1/`) and the two earlier preflights
(`definitions-set-b-preflight.md`, `set-b-carrier-preflight.md`). Numbers:
the three first-class-buffer slices are slots 48/49/50 (1,166 + 680 +
1,642 = 3,488 bytes) and stay where they are; Set B's scan (1,583) and
commit (1,398) slices become **late-region tenants in slots 56/57**, their
durable source in Bank 5 `$5DE80–$5FE7F` staged from Attic by the Card L
mechanism (five Boot records today → tenant records; Boot 17/64 with full
staging), fetched into the overlay window by the existing absolute-tuple
loader with CRC check; region 0 keeps 491 bytes free, Session 58/64,
resident margin 955 bytes after Set B's 241.

**Card "Set B" bound**, base = the Card L Final (ELF `7e57bc17…`, D81
`ac05fdea…`). Members, in this order inside one card:
1. Late-region tenant mechanism: region-3 producer/validator/media
   implementation, slot-55 tenant CRC binding and readiness enforcement,
   catalog entries for slots 56/57 with the late region as source; the
   marker gives way to the tenant records.
2. Retirement scan slice (slot 56): after a collection, read every place a
   function handle can live while the mark bits are valid; produce the
   unreferenced-image set.
3. Retirement commit slice (slot 57) with image-row compaction and
   re-ownership, activation guard and recovery journal; retained handles
   keep ordinals and code addresses; code holes remain charged (no
   compaction of code).
4. Capacity contract at depth 0: a top-level redefinition reuses a slot;
   the in-form 54-redefinition loop keeps its clean `OUT OF MEMORY` (no
   inside-running-form expansion is implied).
5. Promotion (d1) of escaped transient callables in `%c2-run-expanded`
   (Lisp plane): explicitly admitted surface change — `(setq f (lambda …))`
   at top level becomes valid, the phase-12 refusal is lifted for promoted
   images only, and the positive `funcall` row is the gate. (This is the
   one public-surface change of the cycle; it is what the owner's class-(a)
   known issue promised as "pending Set B promotion".)

Budget **1 Seed / 1 Final / 1 product link, plus at most one attributed
replacement Seed** (cap 2/1/1); a correction that needs another link halts
for rebinding. Gates: §4 of `set-b-carrier-plan.md` verbatim (tenant-byte
preservation across the workload = the Card L write-watch row on the
tenants; the moved/new slices' functionality rows; boot ≤ +0.5 s over the
Card L Final; lanes ≤ 1.02 with the reload-burst class named; matched GC
with attribution; the retained-callable, nested-error and over-cap
regression rows; the Set B rows: redefinition reuses a slot with all
retained handles valid, 64-image cap reached only by distinct definitions,
retirement journal recovery after an injected abort; sealed full
`check-source` with the D1/E25, resolver, media-census, storage-owner,
manifest and Card-5 successors prepared before the run; Final
byte-identical). Halt-and-defer: a second red gate of a new class, any new
defect class, any inventory difference outside the members, or a GC delta
outside the named-cost rule defers Set B; the world then stays the Card L
Final.

Execution split as for Card L: Codex prepares design notes, source
authority, producer, Seed, price and inventory as staged changes and
patches under `build/set-b-r1/` (read-only `.git`, no emulator); the
reviewer commits by pathspec, runs the emulator rows and the sealed run,
links the Final. Step 1 first: design notes with the exact source diff
plan per member and object projections, before any source change.

### Card L: host closure — 2026-09-25

Card L closes on the existing Seed (`7e57bc17…`, one Seed, one Final, one
link; replacement Seed unspent) and the r2 medium (`ac05fdea…`, adopted
by identity). Marker/snapshot proof, negative controls, regression rows
and cold boot pass; matched GC delta is zero; lanes 0.99922 batched and
1.02367 single-key with the deterministic bracket-31 code-object reload
burst accepted as a named cost of the registered class (second witness;
trigger attribution reopened as its own host-only card). Sealed full
`check-source`: r1 exit 2 (three consumer successors: D1/E25 map tuple,
library-require resolver, media-builder census, `ad1ce014`), r2 exit 0 on
`ad1ce014`, r3 exit 0 on `cee48d03` (2,511.6 s, 9,211 protected files,
zero changed); Final linked on `cee48d03`, PRG/ELF/LTO byte-identical to
the Seed. Price: ordinary text 36,564 → 36,577 (free 1,209 → 1,196),
Session slice 597 (slot 55, Session 56/64 after the 256-byte directory
step), Boot 17/64 (five marker records), Bank 5 owners `card_l_gap` and
`card_l_late` declared, all other owners unchanged. Report
`card-l-final-report.md`, seal `card-l-final-20260925.json` (1,111
inputs, 53 receipt copies). Accepted world: the Card L Final. Device rows
(cold boot, marker on hardware) join the batched device list. Next: Set B
on the Card L world (binding to be written with the late region as the
carrier, budget 1/1/1 plus one attributed replacement Seed).

### Card L gates on the r2 media: all green except one lane bracket, accepted as named cost of the registered reload-burst class — 2026-09-25

Reviewer decisions after the emulator rows on the repacked media (r2,
same Seed ELF `7e57bc17…`; first red = media pipeline defect, Session
overflow header CRC not re-bound, attributed and fixed by Codex without a
relink):

- Executed proof: marker staged and byte-identical at the first prompt and
  after every one of 20 workload forms incl. `require "repl-comfort"`,
  the eval loops, the nested error, the over-cap loop and a forced
  collection; zero bytes changed in gap, header and payload
  (`build/card-l-r1/write-watch-r2/`).
- Negative controls: missing, corrupted and displaced marker records boot
  to the identical prompt with `c2_ready` = 1, the region not equal to the
  marker, about +1 s (the 64-frame retry) (`negative-controls-r2/`).
- Matched GC: warmup 5,655,838 / 532 and forced 5,385,995 / 501 in both
  worlds, delta 0 (`build/card-l-gc-*`).
- Regression rows: retained-callable 1/2/16/54, lambda refusal, nested
  error, over-cap, cumulative, 23 usage rows — 83 PASS
  (`build/card-l-regression-r1/`).
- Cold boot (per-world boot instrument r2): prompt identical, zero carrier
  writes, stack low `$CF7C`; Initializing +12,531,720 and prompt
  +12,609,753 cycles (+0.31 s at 40.5 MHz, gate +0.5 s)
  (`build/card-l-native-boot-r2/`). The +0.31 s is the stage copy of
  8,192 bytes plus the CRC pass, the price of the mechanism.
- Lanes (`build/input-cost-natural-card-l-r1/`, two identical attempts):
  batched 0.99922; single-key sum 1.02367 against the ≤ 1.02 gate. 39 of
  40 brackets are ≤ 1.0 (candidate 3,115,930 vs baseline 3,118,858 cycles
  per key); bracket 31 alone carries a deterministic +3,194,244 cycles =
  +934,912 instructions in `c2_map_cpu_read`, `vm_run_inner`,
  `vm_object_load`, `c2_product_entry_record`,
  `c2_stream_product_materialize_entry` — a code-object reload burst with
  no collection (gc counters change only at bracket 12 in both worlds).
  This is the class registered on 2026-09-23 for the anchor Final's
  bracket 38 (934,919 instructions), now with a second witness on a
  different world; the burst position is layout-dependent and it occurs
  once per session. **Accepted as a named cost of that registered class**,
  with the attribution stated; the gate is read as a steady-state gate and
  the steady state is ≤ 1.0. The burst's trigger gets its own host-only
  attribution card in the register (two witnesses now).

Next: Final tools and report draft (Codex), sealed full `check-source` on
the exact HEAD, Final byte-identical to the Seed, seal, closure.

### Card L step 2: marker delivered as five contiguous Boot-family records (reviewer decision) — 2026-09-25

Codex's step 2 (`build/card-l-r1/step2-report.md`, `attic-placement.md`)
derived the Attic placement (Boot tenant base `0x08200000`, existing
records end at offset 19,676, next 256-aligned offset `0x4D00` →
`0x08204D00`), the marker (SHA-256 `b504c29b…`, CRC16 `0x7B72`), the
prices (stage 596 / 640, resident +13 / +20) and a blocker: the pinned
packer refuses data records larger than 1,792 bytes, the marker is 8,192.

Decision (under delegation), no packer policy change: **the marker is
packed as five contiguous Boot-family records, four of 1,792 bytes and one
of 1,024 bytes** (1,792 = 7 × 256, so consecutive 256-aligned placements
are gap-free and the 8,192 bytes are contiguous in the Attic starting at
the first record's address); the stage copies the contiguous span as one
`c2_product_physical_copy` of the sealed total size and verifies the
sealed CRC16 over the whole image; the Boot catalog grows 12 → 17 of 64.
Codex verifies whether Boot-family record payloads are stored contiguously
without interleaved headers at the packer's placement; if headers
interleave, the stage copies record by record from a sealed five-entry
table in the binding record instead, and the report says so. The tuple
binding stays form (a): producer-side write of the sealed values into the
authenticated Session payload of slot 55 after link. Negative controls:
one record missing, one record's byte corrupted, records displaced by one
alignment step; each must leave the region unowned with boot and prompt
unchanged. Set B's later carrier use inherits the same multi-record form.

### Card L step 1 reviewed: marker image decided, Attic placement to be bound before the authority commit — 2026-09-25

Codex's step 1 (`build/card-l-r1/step1-report.md`, patch
`step1-source.patch`, 12 prepared files) is reviewed: stage slice
`src/optional/card_l_stage.c` (592 code + 4 binding bytes, projected),
call at `c2_product_boot` after `c2_publish_exports_from` and before
`c2_ready = 1` under `LISP65_CARD_L_STAGE` (+13 resident bytes projected),
linker owners `card_l_gap` (96) and `card_l_late` (8,192) in the successor
authority `config/card-l-native/`, plane `config/card-l-plane/`, producer
with slot-55 registration. Codex left the size/CRC tuple zero because no
image was bound and refused to invent one — correct.

Reviewer decision (under delegation): **the card stages a marker image**,
8,192 bytes of deterministic content derived by SHA-256 expansion of the
string `lisp65 card L late region marker 2026-09-25` (bytes = repeated
SHA-256 of the string with a 4-byte counter), CRC16 with the overlay
polynomial, tuple sealed in the producer's manifest and written into the
binding record by the producer, delivered as a Boot-family Attic record at
the address the stage reads (the constant `0x08500000` in the sketch must
be replaced by the address the packer actually assigns, derived the way the
boot-name-index Attic records are placed; both go into the same authority
commit). No tenant reads the marker; the positive gate is byte identity of
the staged region with the marker after the workload, the negative gates
are missing, corrupt and displaced records leaving the region unowned.

Order: Codex step 2 binds the Attic placement, the marker and the tuple
(source, producer, medium adapter), re-prices the objects; the reviewer
commits the authority and fills `AUTH`; Codex runs the Seed, price and
inventory; the reviewer runs medium, boot, write-watch, negative rows,
lanes, GC, regressions and the sealed run, then the Final.

### Card L bound: Bank-5 late region staged from Attic (reviewer decision under delegation) — 2026-09-25

Preflight closed: `card-l-write-watch-preflight.md` (Codex, geometry,
census, stage projection; §5 executed proof by the reviewer: zero bytes
changed in `$5DE20–$5FE90` across a 17-step workload on the 2.4.0 world,
header zero after publication, payload dead). Geometry: gap
`$5DE20–$5DE7F` (96), payload `$5DE80–$5FE7F` (8,192), live header
`$5FE80–$5FE89` (10), tail floor 374.

**Card L, bound.** Base: the 2.4.0 release world (ELF `66165507…`, D81
`87cb0f6e…`; the Comfort medium `bb9b8d56…` is a second medium of the same
runtime and must stay loadable). Scope: (1) explicit owners for the late
region (`$5DE80–$5FE7F`) and the gap in the linker/storage-owner receipts,
no tenant yet; (2) a stage mechanism as proposed: after every successful
boot publication and header invalidation, a Session slice (projected
592 bytes: 586 core + 6 adapter, one catalog slot, Session 55 → 56, plus a
13-byte resident call stub and a 4-byte size/CRC binding) copies a sealed
image from the Attic into the late region and verifies its CRC; failure
leaves the region unowned and the boot chain unchanged; (3) the boot-name
index, its publication and its header stay byte-identical in behaviour.
No public Lisp surface change. Budget **one Seed / one Final / one product
link, plus at most one attributed replacement Seed**; a second red gate of
a new class, any new defect class, or any write into the region by anything
but the stage slice defers the card.

Gates: price and complete linked-byte inventory (resident text ≤ +20
bytes, one new Session slice within 1,088 bytes after the 256-byte
directory step — `slice_capacity_preflight_20260924.py` is the instrument —
catalog Session 56/64, Boot 12/64, E000/capture/high-BSS unchanged,
Bank 5 tail floor unchanged); boot ledger within +0.5 s of the 2.4.0 world
with identical prompt; the permanent write-watch row (driver of
`build/card-l-preflight-r2/` extended by a forced collection and the
Comfort package) reads zero writes outside the stage slice and the staged
image byte-identical after the workload; negative rows: missing, corrupt
and displaced Attic image → region unowned, boot and prompt unchanged;
lanes within 1.02; matched GC with attribution; the retained-callable,
nested-error and over-cap regression rows; dated successors for storage-owner,
manifest and Card-5 receipts; fresh sealed full `check-source` on the exact
HEAD, Final byte-identical to the Seed.

Execution split (owner rule of 2026-09-24): Codex prepares source
authority, producer, Seed, price and inventory as staged changes and
patches under `build/card-l-r1/` (its sandbox has a read-only `.git` and
no emulator); the reviewer commits by pathspec and runs the emulator rows
and the sealed run in the main session.

### Comfort library host closure accepted; medium GC shift accepted as named placement cost; Codex corrections landed — 2026-09-25

Reviewer acceptance of `5dc91dbc` (report `comfort-library-host-report.md`,
seal `comfort-library-final-20260924.json`), verified: sealed
`check-source` r2 exit 0 on `c65e407c` with zero changed protected files
(2,664 s); package `repl-comfort` 897 Bank-2 bytes (bound ≤ 950), members
C1–C14 all delivered, no native byte, runtime ELF `66165507…` and 18 of 19
medium files byte-identical to 2.4.0, the index gains one row and the
new file `REPL-COMFORT`; symbols 244 / 5,415 free after IDE and six
packages; recursion depth 15 under Comfort; suite 20/20 restated;
72 emulator rows pass; first red (trailing comment before the appended
closing bracket) fixed in the library only; first sealed-run red (medium
tool census) converted in tools.

**Named cost accepted (reviewer decision):** with the sixth index row the
two startup `require`s collect 5 times instead of 3 before the first
prompt, so the plain prompt's collections shift in placement: forced
5,385,995 → 5,432,257 (+0.86 %), natural +0.12 %, live cells identical
(532 / 501, shadow graph identical); the plain-prompt lanes move to
0.9653 / 0.8608 (faster). This is the medium-layout class (every added
package shifts it), not collector work; accepted as a named cost with the
attribution stated; a PC-instrumented pair as in the GC layout control is
a register item, not a halt. "Lane unchanged" is read as "not slower and
attributed", as the executor read it.

Comfort medium `bb9b8d56…` (`build/comfort-library-medium-r2/packed/cmf240.d81`)
is the device candidate; the device session (`comfort-device-plan.md`,
SD name `CMF240.D81`) settles the three surface defaults (`l65>` prompt;
first line with prompt plus continuation lines as typed; over-close
message `*** reader: unmatched close parenthesis`) — owner's eye. Errors
inside Comfort land at the native prompt by design (definitions survive,
`(repl)` re-enters); landing inside Comfort needs a native hook behind
Set B. By-catch: a column-26 cell blanking on the emulator with and
without Comfort, unattributed. Also noted: `(require "<absent>")` prints
`LOADING …` before `NIL`.

**Codex counter-review of the two preflights (`build/codex-review-2026-09-24/`):**
Set-B carrier 3 ok / 2 corrections, Comfort inventory 6/6 ok. Corrections
landed in the register: Bank 5 has 0 spendable bytes above the 374-byte
floor, the boot name index's 8,192 payload bytes become unused after the
publication while its 10-byte header stays live, plus an unbudgeted
96-byte gap; the mark-hook rejection is 0.317–0.444 % on the 2.4.0
denominator. Tool defect patch (`slice_capacity_preflight_20260924.py`
successor with selftest and `gates.mk` wiring) to be landed by Codex with
a Card-5 dated receipt.

Standing from the owner (2026-09-24): no further Claude subagents; Codex
(`gpt-6-astra`, effort low/medium) executes preflights, reviews and cards.
Next: Codex counter-review of the Comfort host report; landing of the
tool patch; then Card L's budget-free write-watch proof of the Bank-5 late
region.

### Comfort library: host closure — 2026-09-25

The card was run as bound (`180cb993`).
[Report](comfort-library-host-report.md), seal
`comfort-library-final-20260924.json`, device plan
[`comfort-device-plan.md`](comfort-device-plan.md).

**Budget: 0 Seed / 0 Final / 0 product link, 0 device contacts.**
Comfort ships as the sixth package `repl-comfort`: `(require "repl-comfort")`
then `(repl)`.

- **Package:** 897 Bank-2 bytes in 5 objects (≤ 950), 0 native bytes.
  Members C1–C14 are all delivered; none is deferred.
- **Medium:** Comfort D81 `bb9b8d56…`. Runtime ELF `66165507…`,
  `LISP65.PRG` and 18 of the 19 files are byte-identical to 2.4.0.
  `L65INDEX` has 6 rows, the first 5 byte-identical to 2.4.0. No other
  directory record changed.
- **Gates:** D5 with IDE + six packages is **244 / 5,415** free. Depth under
  Comfort is **15** (16 refused; native 16/17). Emulator rows: 72 PASS,
  4 observed, 0 FAIL. Host suite: 19/19 restated + case 20.
- **Sealed full `check-source`:** exit 0 on `c65e407c`, 0 changed
  protected files (2,664 s). The first run on `d62739f3` exited 2 with one
  red, the media-builder enumeration not knowing the Comfort medium
  producer; it was converted in tools only (enumeration v31, `c65e407c`).

**First red, closed in the library:** a `;` comment ending the last input
line swallowed the seam's closing parenthesis (`(+ 1 2) ; )` left Comfort
with `UNCLOSED LIST`). The closing parenthesis now follows a newline, with
no price change (`3a6affc0`). The branch source fails the new case 20.

**For the reviewer and the owner:**

1. **Named cost of the medium change.** The sixth index row makes `INIT.L65`
   run two more boot collections (`gc_runs` 3 → 5; symbols and screen
   identical). This holds even with Comfort not loaded.
   - Matched GC at identical live cells: +6,908 natural (+0.12 %) and
     +46,262 forced (+0.86 %). Both are above the 0.05 % threshold, and no
     PC-level attribution was run.
   - Natural lanes: faster, 0.9653 / 0.8608. The collection phase and cell
     placement moved, and the lanes are not cycle-identical.
   - If "lane unchanged" means cycle-identical, this is a second red of a
     new class and the card halts under its rule; the report reads it as
     not slower and attributed.
2. **An error inside Comfort lands at `lisp65>`, not at `l65>`.** This is
   the prepared design: session code survives and `(repl)` re-enters. A
   landing inside Comfort would need a native hook, which goes behind Set B.

The three surface defaults stand as bound (`l65>`; first line with prompt
and continuation rows as typed; the prepared over-close message) for the
owner's eye at the device session (upload as the new SD file `CMF240.D81`).
The device session closes the card (contact word).

### Owner word: order Comfort (library-only) → Card L → Set B; Comfort card bound — 2026-09-24

Owner word (2026-09-24, evening): the recommended order stands. The three
surface questions were not answered separately; the reviewer binds the
**prepared branch behaviour as the default** and puts them to the owner's
eye at the Comfort device session, where a Lisp-plane change is cheap:
prompt text `l65>` as prepared; scrollback of multi-line input shows the
first line with its prompt and the continuation lines as typed (the
branch form); the over-close refusal uses the prepared branch message
verbatim. Any change the owner asks for at the device session becomes a
Lisp-plane successor of the card, not a new card.

**Comfort card bound: "comfort-library", on the 2.4.0 release world**
(ELF `66165507…`, D81 `87cb0f6e…`). Scope: members C1–C14 of
`comfort-inventory-2026-09-24.md`, delivered as the sixth library package
(name as prepared on `comfort-prepare-now`, loaded with `require`), plus
the branch suite restated for the two shipped display rules. **No native
byte, no resident-plane change, no change to any shipped library**
(any member needing one is deferred behind Set B). Budget: **0 Seed /
0 Final / 0 product link**; one medium (the D81 with the added package;
runtime ELF, PRG and all other medium files byte-identical to 2.4.0), one
emulator prefilter, one device session with the owner. Price gates:
library ≤ 950 bytes; symbols/name bytes after IDE + six packages ≥ 32/384
(D5) with the measured numbers stated; recursion depth under Comfort ≥ 14;
GC matched with the 2.4.0 baseline (5,385,995 forced / 5,655,838 natural)
with any live-cell cost named; per-key natural lane of the plain prompt
unchanged (Comfort is opt-in via `require`). Functional gates on the
emulator: the restated suite 19/19 as executed rows; entry/exit/re-entry;
balanced multi-line input with `defun`, multi-form lines, `require`;
strings and comments in depth counting; over-close refused before eval;
history ring of 10; abort recovery (nested-error row under Comfort);
lossless typing under a forced collection; the retained-callable and
nested-error regression rows unchanged with Comfort loaded. Halt-and-defer:
a member needing a native byte defers the member; library > 950, D5 <
32/384, depth < 14, or a second red gate of a new class defers the card to
after Card L. Closure: report, seal, register rows, plan entry; the device
session with the owner (contact word) closes the card and settles the
three surface questions.

Card L (Bank-5 late region) and Set B follow as bound in the preflight
entry; Card L's write-watch proof is its first, budget-free step and may
run in parallel on the host once the Comfort medium is qualified.

### Both preflights closed; recommended order Comfort (library-only) → Card L (Bank-5 late region) → Set B — 2026-09-24

Reports: `comfort-inventory-2026-09-24.md` (receipts
`build/comfort-inventory-r1/`) and `set-b-carrier-preflight.md`
(`build/set-b-carrier-preflight-r1/`). Both read-only, no build, no
device. Order is the owner's word; the reviewer's reading:

**Comfort is Lisp-plane only on 2.4.0.** The prepared library compiles over
the byte-identical 2.4.0 resident to 897 bytes in five objects, +5 symbols
/ 60 name bytes, zero native bytes; Bank-2 room with IDE and five
packages is 8,367 bytes (derived; reproduces Set A's 8,365), symbols
249 / 5,475 free against the 32 / 384 floor; the branch suite passes 19/19
once two display rules already shipped in 2.4.0 are restated. Members
C1–C14 (entry/exit with `l65>` prompt, balanced multi-line input,
auto-indent, strings/comments in depth counting, over-close refusal before
eval, 10-entry history ring, abort recovery, composed display, lossless
typing under GC, gates/media). Behind Set B: A1's native half (`.rodata`
0 free), A2/A3 matcher/blink until the `$22` mechanism is attributed,
A4/A5 editing wave, A6. Owner's eye needed for: the `l65>` prompt text,
scrollback of multi-line input (first line only or every line), the
over-close message text.

**Set B needs a carrier programme.** Retirement by reachability as two
Session slices (scan 1,583 + commit 1,398 bytes, 2 slots) plus 241
resident bytes and 2 BSS; slot reuse folds into the compaction (0 extra);
promotion (d1) is a Lisp-plane change in `%c2-run-expanded` that lifts the
lambda refusal (owner word); the in-form 54-redefinition loop stays
blocked by C-stack saved state. Carriers: a further Session slice tops
out at 1,088 bytes because the 56th catalog entry pushes the directory
across a 256-byte boundary (**tool defect**: `slice_capacity_preflight.py`
misses that step); Bank 5 has 0 spendable bytes today, but the boot name
index (`$5DE80–$5FE89`, 8,202 bytes) is dead after the boot publication
by source, so a **late region staged from Attic after every boot
publication** is the smallest carrier (stage slice about 638 bytes, 1
slot, about 10 resident bytes; risk: no executed write-watch proof yet);
catalog widening is unnecessary (the built verifier checks per family:
Session 55/64, Boot 12/64 — the register's "unique 63/64" was a reported
value, not a limit) and would cost 32 bytes per slot; reclaimable resident
text at most 422 bytes, unproven. A mark hook inside the collector is
rejected (+0.32–0.44 % per collection, 9 BSS bytes); the scan slice model
costs 0 per ordinary collection and about 6.96 M cycles per retirement
event.

**Recommended order, for the owner's word:**
1. **Comfort library-only card** (C1–C14): 0 Seed / 0 Final / 0 product
   link, one medium, emulator prefilter, then a device session with the
   owner; halts: any native byte or resident-plane change defers the
   member behind Set B; library > 950 bytes, D5 below 32/384, recursion
   depth under Comfort below 14, or a second red gate of a new class
   defers the card.
2. **Card L, Bank-5 late region** (carrier): prove the region unused after
   the stage point (write-watch), stage slice, tool/manifest/storage-owner
   successors; budget 1/1/1 plus one attributed replacement Seed.
3. **Set B** on Card L's world: retirement scan + commit slices with
   compaction, promotion of escaped callables with the positive `funcall`
   row as gate; budget 1/1/1 plus one attributed replacement Seed.
Register rows: the capacity-preflight tool defect; the corrected catalog
watch (per-family counts); `(require "<absent>")` prints `LOADING …`
before `NIL`; the branch Comfort suite is stale against 2.4.0.

### Owner word: two read-only preflights open the cycle; order decided on their numbers — 2026-09-24

Owner word (2026-09-24, afternoon) on the reviewer's recommendation: the
next cycle opens with two budget-free, host-only preflights run in
parallel, and the order Set B / Comfort is decided afterwards on their
numbers. The device is not needed for either and is released to other
sessions (it sits at the 2.4.0 prompt with `RC240.D81` mounted; a normal
reset auto-boots lisp65).

1. **Set-B carrier preflight** (`docs/planning/set-b-carrier-preflight.md`,
   receipts `build/set-b-carrier-preflight-r1/`): which region can carry
   about 4,113 bytes of native text and two overlay-catalog slots for
   Definitions Set B, and at what price — a further Session slice (Session
   regions 1,351/140/872, catalog 63/64), a Bank-5 owner (374 bytes free
   today; what would move), widening the 64-slot catalog itself (which
   tables and gates pin 64), or a Boot-family record; plus whether image
   reachability marking (the collector marks no images today) can be
   prepared without the carrier. Object projections only; no product link.
2. **Comfort inventory** (`docs/planning/comfort-inventory-2026-09-24.md`,
   receipts `build/comfort-inventory-r1/`): the Comfort members as last
   bound (comfort-handover-prep, comfort-prepare-now branches and the
   Comfort planning documents), classified into Lisp-plane-only members
   (cost in Bank 2: plane 49,758 of the 60,758 code limit, plus GC live
   cost and symbol/name floors) and members needing native text or E000;
   per member the user-visible effect, the price projection, the gates and
   whether the owner's eye is needed.

Decision rule announced: if Set B needs a native carrier programme of its
own, Comfort's Lisp-plane-only members go first while the carrier is
prepared; Set B follows when the carrier exists; Comfort members with a
native share stay behind Set B. Both preflights report to the reviewer;
the order is an owner word.
