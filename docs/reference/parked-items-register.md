# Parked-items register

2026-10-04 **2.5.4 object-size reserve** (`src/vm.c`, `len > 255`; `docs/planning/post-2.4.0-plan.md`, journal 2026-10-04 "Seed tools"): the object-size limit applies to the stored object length. `ide-split-line` and the largest REPL-COMFORT object are 253 B stored length against the 255 B limit, so each has 2 B of reserve. Any change that grows either object by more than 2 B needs a split or a new design before it can be loaded. Related 2.5.4 limits stated in the release notes (`docs/releases/2.5.4.md`): a direct `m65d-save` call is not protected by the edit-persistence mechanism (only the IDE path is) and does not refuse a save during a source load; the host proof of edit persistence covers aborts at VM instruction boundaries on the delivered IDE image, not aborts inside native primitives, during garbage collection or at out-of-memory (emulator rows on the Seed medium passed for those; one physical RUN/STOP row on the device is pending); explicit `prin1`/`print` and the native `LISP65>` prompt remain unbounded on a cyclic list (RP1 bounds only the Comfort result print).

2026-10-05 **2.5.4 device session and host follow-ups** (`docs/planning/release-2.5.4-device-report.md`, `build/device-254-prep/owner-observations.txt`): (1) **Type-ahead while the IDE editor opens is lost**: keys typed right after Return on `(ide "name")` do not arrive (of `abcdefgh` only `fgh`); the editor entry resets the encoded-input counters (`(poke 188 252..255 0)` in `ide`, from `1520bc2f`, before 2.5.3); not a 2.5.4 regression; documented limit, candidate for the editor card. (2) **IDE typing latency (owner priority, card for the next cycle)**: typing in the IDE editor is clearly slower than at the REPL on the device; keys are not lost, they appear late; the editor was never actively optimised; emulator comparison (`build/card-254-ide-typing-r1/notes.txt`): editor insert 122.3 against 124.2 ms (length 1) to 148.0 against 150.0 ms (length 39) for 2.5.3 against 2.5.4, a constant +73k cycles (1.8 ms) per key; REPL insert 4.17 ms in both; a collection of 116–123 ms on about one in five or six editor keys in both; owner word 2026-10-05: released as a known limit for 2.5.4, "speed up editor typing" is the FIRST card of the next cycle, before sound. (3) **`(m65d-remount)` duration** on the device is very long (no seconds recorded; owner: believed unchanged; M65D image byte-identical to 2.5.3; emulator about 26 s): candidate, together with the deferred second save fix (remount owner map). (4) **`$D703` open on hardware**: not checked in the device session; the emulator probe survived, emulator DMA semantics unproven; needed before 2.6 sound/graphics DMA work. (5) **`dialect-v2-eval-apply-funcall-matrix` red, standalone**: 6 of 40 runs fail (`apply-bcode-result` on dialect-v1 treewalk; `funcall-primitive-too-many` on both dialect-v2 engines; `direct-eval-atom`, `direct-eval-form`, `funcall-eval-form` on dialect-v2 compiler-vm); the target is in no aggregate and nothing consumes it; not a host effect (identical with the Fedora 44 and the Fedora 45 equivalence binaries); decide between repairing the expectations and retiring the target. (6) **Not done on the device in 2.5.4**: large saves (50x40, 100x20), out-of-memory rows, additional REPL rows, physical `C-x C-s`; no device driver session (no tool-clock boot, no automated device rows) and no GC-stress session exist for 2.5.4. (7) **Host compiler changes**: the two equivalence host binaries and their build receipts are local make products that record the compiler; after a host compiler change they must be rebuilt before a sealed run, and a committed receipt that pins a host-built binary needs a dated successor (2026-10-05: `dialect_v2_number_to_string_v254_20261005.py`). Optional hardening: make the compiler identity a make prerequisite. (8) **History recall of very long entries overdraws** (pre-existing, display only): with the prompt at the bottom of the screen a recalled 250-character entry is drawn over the three rows above without scrolling and stale cells remain; cursor keys, Delete and Return work and the value is right; identical in the 2.5.3 records; it stalls the GC scenarios `history10` and `history-home-delete-refill250`, so Return of such an entry and delete/refill inside one are not covered under forced collection. (9) **Memory cost of 2.5.4**: constant +3 live cells and +88 arena bytes against the 2.5.3 Final at every collection (reasoned cause: the bounded result print RP1, `%lt-fit`, `%lt-write` and its message string); headroom at the highest forced peak 43 of 1,070 cells (2.5.3: 46); gate `gc-session` recorded as FAIL (`build/card-254-gc-r2/summary.json`); owner word 2026-10-06: cost accepted, publication with the gate recorded as it is approved. (10) **GC driver**: after a STALL the driver's emulator process lingers for more than 300 s and the next scenario is refused; run a scenario after a STALL in its own unit; the committed `compare()` refuses real receipt pairs (lists against tuples). Wrapper `tools/host-lisp/c254_gc_session_20261006.py`. (11) **Device upload**: whether the MEGA65 was power-cycled before the upload was not recorded in the 2.5.4 session (2.5.3 had an operator acknowledgement). (12) The owner released the three device limits (IDE typing latency, type-ahead while the editor opens, long `m65d-remount`) for 2.5.4 on 2026-10-05.

2026-10-04 **2.5.4 release-time observations** (`docs/planning/post-2.4.0-plan.md`, journal 2026-10-04 "Seed r1" and "Seed r1b complete, emulator rows, Final tools"): (1) **IDE status-row redraw** (product observation, same in 2.5.3): the IDE status row is not redrawn when its text equals the one drawn last, and old status rows stay on screen after an abort or `C-x q`; not fixed in 2.5.4, candidate for a later IDE card. (2) **Reviewed commuting instruction pair at `$C473`** (`c2_stream_phase_00b`, section `.lisp65_rt_c2d_00b`): the 2.5.4 Seed link emitted `clc` / `sta $0a` where the predecessor had `sta $0a` / `clc` (bytes `85 0a 18` to `18 85 0a`; the `R_MOS_ADDR8 __rc8` relocation moves from `$C474` to `$C475`). The pair is accepted as one narrowly pinned reviewed class (`tools/host-lisp/c254_seed_continue_r1b.py`; the Final inventory runs inside the same class). **The code generator's reason for the other order is not known.** A later release that sees another such pair must not widen this class; it needs its own review, and the cause in the code generator is an open question. (3) **`$D703` probe**: in the emulator the write applied and the product survived a library load; whether the emulator's DMA honours the bit is not shown, so the DMA semantics are unproven and the device check stays open (relevant for 2.6). (4) **RUN/STOP stand-in**: the monitor write to the break flag is accepted for the emulator only; the physical RUN/STOP row for edit persistence is a device row.

2026-10-04 **Legacy stdlib suites: record corrected (owner decision "correct the record")**. The row "Legacy stdlib suite drift / red `check-host`" below and earlier notes describe seven of thirteen (2026-09-05) and later one of thirteen legacy suites as red. That finding is superseded as a gate finding: the study of 2026-09-29 (`build/legacy-stdlib-decision-r1/report.md`, local) found the mandatory legacy run green with 12 suites and 1,707 cases and the four freshly generated Dialect V2 product suites green with 426 cases. Only the Workbench codemod template suite `p0-stdlib-einsuite-core-workbench-subset` fails when it is run directly under dialect v1 (`poke` is absent from the v1 directory); it is excluded from the mandatory run by derivation from `config/v2-workbench-artifact-closure.json`, which is the intended separation. No product defect. The existing separation stays; the two alternative patches of the study (extend the v1 Workbench coverage, or move the template out) are not adopted. The figures are those of the study and were not re-measured for this entry.

2026-10-04 **2.5.4 integration: two reds outside check-source/check-host** (`build/card-254-integrate-r2/notes.txt`): (1) `dialect-v2-lcc-compile-error-check` — its selftest fails with "resident manifest omits lcc-compile-obj"; only consumer `v2-capability-carrier-check-host-4`, which no release aggregate runs; not caused by 2.5.4. (2) `v2-workbench-library-composition-check` (legacy Workbench composition; gates `check-product` and `r3-product-block-build`) — already red at `22ab180e`: post-load code headroom 14,394 B against a floor of 16,384 B (2.5.4: 14,188 B). New with 2.5.4 in the same target: the IDE core library file is 38,599 B against a cap of 38,400 B (38,219 B before). The directory checks of that target pass (headroom 38/32, as before). The 2.5.3 Seed passed while this target was red, so the product Seed does not run it; confirm that for the 2.5.4 producer before the Seed. Either meet the floors (about 2,200 B of code and 199 B of IDE file) or retire the legacy target by a dated successor.

2026-09-30 **2.5.2 harness watch items** (`docs/planning/release-2.5.2-before-ship.md`): (1) `workbench-ux-harness-selftest` (full_pass case) has a 30 s subprocess timeout with about 19 s idle runtime; it failed in sealed check-host r2 under `ionice -c3` beside a foreign four-worker job and passed in r1, r3 and three standalone runs. Timeout unchanged; margin is thin, so a busy host can turn it red. Candidate for 2.5.3: raise the timeout or reduce the case, and note that sealed runs should not use the idle I/O class. (2) The forced-GC stress harness (`build/gc-stress-r7c-*`) never completed a scenario on the 2.5.2 Final: every retained receipt is HALT (transition timeouts near a full heap, earlier attempts on tooling checks). Recorded facts only: peak 1,009 live cells, `mem_oom` 0 over 535 collections. The acceptance gate `gc-session` asserts those facts, not a completed scenario. Harness fix or a faster driver is a 2.5.3 watch item.

2026-09-30 **Cross-compiler drift review** (`build/external-review-crosscompiler-drift-r1/report.md`, 102 targeted rows vs. /home/alex/Videos/lisp65-native-prototype): D1a product LCC multi-pair `setq` returns 1 instead of 3 — now reproduced with the delivered product compiler bytecode (confirms the earlier C1); D1b product LCC accepts surplus builtin arguments (e.g. `car` with two) and drops them incl. side effects; D2 `mapcan` 12-argument limit (fixed in the cross-compiler library); D3 `nth` on a dotted tail returns a prefix element where docs promise refusal; D4 name collision in `case`/`or` in the shared Python host compiler (cross-compiler adapter repairs it); D5 reader splits at all bytes 1–32 while the cross-compiler keeps 22 control bytes in symbols. P1: equivalence tests compare against the C compiler / own stdlib instead of the shipped LCC + resident library. 40/47 frozen cross-compiler reference files byte-identical to the product; no shared binary-ABI drift. Inputs for 2.5.3 (LCC fixes; consider porting cross-compiler library fixes) and for the test setup (compare against the delivered LCC).

2026-09-30 **Open review findings** (`build/external-review-open-r1/report.md`, 53 host cases, all unchanged since 2.5.1): F1 IDE single-buffer switch reactivates an old state — freshly typed characters silently lost (high); F2 mark survives edits with invalid coordinates, typing may create an extra line; F3 `defstruct` generated names not checked against each other (slot `p` collides with the predicate); F4 `mapcan` spreads its result into function arguments and fails beyond 12 input elements. 2.5.3 candidates.

2026-09-30 **Architecture review** (`build/external-review-architecture-r1/report.md`): root cause = implicit contracts between subsystems. Classes: object lifetime (native interfaces rely on caller GC roots; a tail call can break it), IDE state versions (text/buffer list/caches can diverge; an old state can win), memory shape (displayable ≠ savable buffer), session length (redefinitions consume code-image slots, not reclaimed), disk recovery (COW protects the swap, not orphaned blocks), host-model limits, GC mark passes 2 vs 256 for the same 256 reachable cells depending on layout (device time unmeasured), build structure (historical artefacts define the active product; source fixes need projection). Owner agreed: 2.5.3 scope organised by these classes — first lifetime/state contracts + packed IDE join, then disk recovery and code-slot reuse as design work.

2026-09-29 **Compiler differential review (partial; no final report)** (`build/external-review-compiler-diff-r1/`, 8,192 programs × 3 paths + 2,048 edge cases): C1 on-device compiler LCC `%lcc-setq` (`lib/lcc.lisp:396`) compiles only the first pair of a multi-pair `(setq a 1 b 2 …)`; later assignments are silently dropped (C compiler executes all) — wrong results without a message; C2 LCC does not fully check the argument count of some built-in operations; surplus arguments may not be evaluated at all (side effects such as output vanish). Both reproduced in the native host test; transfer to today's product path still to be confirmed. High-priority 2.5.3 candidates.

2026-09-29 **Reader/printer review backlog** (`build/external-review-reader-printer-r1/report.md`; 65,536 fixnum round trips and 37/37 reader fixtures PASS): B1 printing a cyclic list never terminates (no cycle guard); B2 printed symbol names can change type/name/identity when read back (e.g. symbols that look like numbers, case/special characters); B3 `intern` silently truncates at an embedded NUL; B4 strings with NUL cannot be printed/read back; B5 screen output shows several byte values as spaces; B6 backward paren-match scan (`lib/sexp-depth.lisp`) overflows its fixnum state at nesting depth 17 (wrong highlight in Comfort/IDE); docs: write-string/write-line newline description swapped, round-trip limits undocumented. Candidates for 2.5.3+ triage.

2026-09-29 **2.5.3 disk/recovery backlog** from the completed independent reviews (`build/external-review-disk-integrity-r1/report.md`, `build/external-review-stop-recovery-r1/report.md`): D2 count-consistent but wrong BAM accepted → cross-linked overwrite (only on already-damaged disks; add chain/BAM ownership check), D3 IDE load drops trailing spaces/empty lines/CR, D4 leaked BAM blocks after aborted save, D5 full directory (144) refused on remount, D6 chain shortened between read passes accepted (conditional), R1 RUN/STOP drops the current IDE input batch (3 chars in host proof), V1 abort during arena relocation (injected only), V2 possibly sticky OOM flag (source suspicion). D1 (directory link) fixed in 2.5.2. Plus 2.5.3 IDE save/eval heap + reader root + `%set-macro` root.

2026-09-29 **IDE save/eval heap defect** (in published 2.5.1): whole-buffer cons list on save / `eval-buffer` → `*** VM: OUT OF MEMORY` beyond ~20×20 / 10–12×40 / 6–7×70 chars; no data loss; reader source string unrooted in `eval-buffer`. Known issue in 2.5.2; **fix card for 2.5.3** ([review](../../build/external-review-ide-save-heap-r1/report.md), candidate `build/ide-save-heap-fix-r1/`).

2026-09-29 **STOP reverse-cursor remnant** (inherited from 2.5.1): RUN/STOP after Home on a wrapped Comfort line leaves a stale reverse cursor one row above the new prompt. Cosmetic. Host proposal `build/stop-remnant-r1/` (+141 B shared resident, clears all reverse video on reentry) not accepted as is; follow-up card after O2-lite, look for a cursor-only fix.

2026-09-29 **2.5.1 PUBLISHED** ([report](../planning/release-2.5.1-publish.md)): public main `2817f0cf`, release latest, four assets verified. Open: stopwatch cold boot, physical RUN/STOP, physical C-x C-c (known issue). Next card: multi-line editing in Comfort (owner word for the surface change); code-object cache after re-measurement; reload-burst parked.

2026-09-29 **2.5.1 Before-Ship r3** ([report](../planning/release-2.5.1-before-ship.md); [device](../planning/release-2.5.1-device-report.md)): sealed host r4 green; fresh Strings Final S251.D81 device rows 13/13 PASS. Owner physical typing/Backspace feel, string example and C-x q PASS, superseding those open rows below. Stopwatch cold boot and physical RUN/STOP remain open. Physical C-x C-c remains known. Continuation lines uneditable after Return; Up/Down walk history. Multi-line editing follows 2.5.1; code-object cache remains a later re-measurement decision. Scope includes the small Backspace tail change and measured list-walk typing reduction. Ship/Publish delegated; not yet published.

2026-09-29 **Comfort multi-line string fix host-closed** ([report](../planning/strings-final-report.md); seal `strings-final-20260929.json`). 2.5.0 known issue until 2.5.1: a string spanning continuation lines hangs Comfort (workaround: a line with just `)`). Candidate 2.5.1 = 2.5.0 + C-x q + list walks + string fix. Follow-up card: multi-line editing in Comfort (owner word needed for the surface change).

2026-09-28 **Editor list walks host-closed** ([report](../planning/walks-final-report.md)): measured typing 80 → 39 ms/key (native lane); Backspace reads 1,233–1,773 → 53/key (projected). Open: device typing feel. Follow-ups: Comfort multi-line string fix (in progress, 2.5.1), multi-line editing card (after 2.5.1), code-object cache (decide after re-measurement).

2026-09-28 **Backspace latency host-closed** ([report](../planning/backspace-final-report.md)): −7/−19/−26 % VM instructions per Backspace (10/40/70 chars), native 0, plane −12. Candidate 2.5.1 = 2.5.0 + C-x q + Backspace (Final D81 `a2872fbd…`). Open: device typing feel; 2.5.1 release chain needs a fresh owner word for Ship/Publish.

2026-09-28 **IDE key exit (C-x q) host-closed** ([report](../planning/ide-exit-final-report.md)); world = 2.5.0 + C-x q (ELF `7716852b…`, D81 `89014071…`), not yet released. Open: device row C-x q; physical `C-x C-c` stays a known issue (transport change out of scope). **Reload-burst attribution parked** (two tool reds; 42-cycle accounting residual in historical brackets) — re-entry `build/reload-burst-r2/RUNBOOK.md`.

2026-09-28 **2.5.0 published** (Comfort as default;
[publish report](../planning/release-2.5.0-publish.md)). Open device rows
(physical, owner): cold cycle with stopwatch, physical RUN/STOP key, typing
feel. Known issues carried: physical IDE `C-x C-c`, Backspace latency.

2026-09-27 **Comfort default: host closure PASS** (`comfort-default-final-report.md`,
seal `comfort-default-final-20260927.json`): the product boots into Comfort
and stays there across errors and refusals; text −3, one owned BSS byte;
Final byte-identical (ELF `d555f01f…`), sealed check-source r4 green on
`42b81911`. Named cost for the owner: six packages at boot (+8 symbols,
+105 name bytes, five more boot collections, +12 live cells and +2.1 %
forced-collection cycles at the native prompt), boot about +7.65 s (emulator).
Open: device session before Ship (boot stopwatch, RUN/STOP under the
default, typing feel). Two findings for later cards: (1) the Set B freeze
left about 12,400 tracked evidence files and six feature-guarded lines in
`src/vm.c`; the sealed runner now collapses fully protected directories to
stay under `fs.mount-max` (25,255 + 1,079 mounts; the budget shrinks again
with every large evidence commit); (2) a lone pasted newline is lost by the
Xemu HWA paste — drivers must send a real Return key (`~typeone 0d`).

2026-09-27 **Set B frozen (owner word, windmill rule):** 5 Seeds / 0 Finals /
5 links consumed; fifth Seed activates and reuses images but halts at
library load (contiguous-span assumption vs retirement holes); the repair
chain needs 185 ordinary text + 32 E000 bytes beyond the reserves.
Re-entry: `build/set-b-product-r5`, `set-b-fifth-seed-workload-halt-report.md`,
`set-b-clear-sync-report.md`. Reopening condition: an air programme that
first creates the reserve, then a fresh owner binding. Card L stays a
qualified, unshipped development world (carrier for a restart).

2026-09-27 **Set B synchronous publication root proof and capacity halt**:
[report](../planning/set-b-clear-sync-report.md). CPU undo/function-cell
stores pass240 host rows/648 observations for old and latest logical macro
roots, duplicates and allocation/undo failures; three DMA falling controls
detected. Matched native prerequisite price: ordinary+193/margin−185,
E000+57/margin−32, high BSS+0/margin1. Halt before terminal controller;
no full CLEAR, target MAP execution or linked placement claim. Owner full
rollback and all floors unchanged. Next read-only shared MAP transport and
placement plan; no new source form or assumed future savings.

2026-09-27 **Set B synchronous publication ledger**:
One isolated source form; host compile/link1 of2, dependency1 of1; native
objects4 of16, dependencies4 of8, assembler1 of2 after host prerequisite
success. Remaining1/0 and12/4/1; no reset. Zero terminal-controller forms,
product builds/links/Seeds/Finals/guest/device;74 compiler roots unchanged.
Complete candidate, patch, commands, rows and matched objects archived in
seal `set-b-clear-sync-20260927.json`. Overall5/0/5, ceiling5/1/5;
Card L/public2.4.0 and fifth-Seed load halt unchanged.

2026-09-26 **Set B CLEAR macro before-image root halt**:
[report](../planning/set-b-clear-gc-gate-report.md). Corrected shared FIFO
preserves source capture and write order. At fourth macro allocation, C2
root scan sees old plan, FIFO advances, symbol scan sees replacements:
old0006 missed (mask0B/0F), eventual undo bytes correct, publisher returns0.
12 corrected rows/30 observations,11 rows pass. Host root-closure failure,
not an executed sweep or hardware defect. Stalled controls cover old roots
only; newly allocated wrapper roots remain a successor obligation. No-GC
starting only at CLEAR cannot close publication lifetime.

2026-09-26 **Set B CLEAR GC ledger and repair scope**:
Attempt1 independent function-store seam excluded and archived (8 rows/20
observations); attempt2 binds actual function-cell transport and shared FIFO.
Host compile/link2/2, dependency1; total20 C rows/50 observations including
excluded evidence. Zero native/assembler/product form/build/link/Seed/guest/
device;74 roots/candidates unchanged. Next proposed coherent synchronous
CPU undo/function stores plus full CLEAR, host2/dependency1; unspent native
16/8/2 after host pass, no product attempt. No budget renewed by report.
Overall5/0/5, ceiling5/1/5; Card L/public2.4.0 unchanged.
Seal `set-b-clear-gc-gate-20260926.json`.

2026-09-26 **Set B source-capture authority disposition**:
[report](../planning/set-b-source-capture-report.md). Pinned clean core
`a9158930` RTL equals Git blob; normal DMA copy captures source bytes before
CPU continuation. Captured-source/delayed-target model now has a concrete
reference-source basis. Historical immutable-source/late-target observations
do not establish deferred source fetch. Keep the deferred-source falling
control and all late-write/root/retained-destination/rollback gates; exact
historical device core remains unbound. No product admission or third class.

2026-09-26 **Set B source-capture audit ledger and implementation successor**:
Zero compiler/dependency/assembler/native/C execution/build/link/Seed/Final/
guest/device;74 roots/candidates unchanged. Prior host attempts remain2/2.
Propose renewed host2/dependency1, then native objects16/dependencies8/asm2
only after host success, one isolated full-rollback source form;0 product
build/link/Seed/guest/device. Not authorized by this read-only audit.
Overall5/0/5, ceiling5/1/5; Card L/public2.4.0 unchanged.
Seal `set-b-source-capture-20260926.json`.

2026-09-26 **Set B CLEAR exact-C source-lifetime halt**:
[report](../planning/set-b-clear-c-preflight-report.md). Four immediate/source-
captured controls pass. Deferred-source policy observes2 changed bytes at
second submission of the same live journal[4]; original publisher returns0.
No expired pointer read or proof that hardware uses that policy. Source
capture-before-reuse is a distinct unbound premise from delayed target
visibility. Halt before new terminal implementation; no third defect class
or completed recovery qualification claimed. Owner full rollback retained.

2026-09-26 **Set B CLEAR preflight ledger and next authority binding**:
Host compile/link attempts2 (first fixture declaration failure archived),
successful link1, dependency1; five C rows,4 pass then halt. Zero native/
assembler/product form/build/link/Seed/guest/device. All74 roots/candidates
exact. Next read-only source-consumption authority audit; only then resume
same repair with renewed host budget, or include stable producer sources/
synchronous stores. No native pricing around the lifetime gate. Overall5/0/5,
ceiling5/1/5; Card L/public2.4.0 unchanged.
Seal `set-b-clear-c-preflight-20260926.json`.

2026-09-26 **Set B CLEAR contract: full rollback selected by owner**:
[report](../planning/set-b-clear-protocol-report.md). Retain undo in the consumed
export plan's upper half; ordered copy before lower-half/C2J clear and trailing
read. ABORT is sticky after timeout. Retain backup through repeated rollback
and post-CLEAR transaction-end failures; scrub synchronously after settlement.
All1819 count bounds and5745 abstract rows pass;3 falling controls detected.
No target execution or full append-recovery proof claimed. Native quarantine
must precede allocation/GC/root drop/ordinary unwind and retain READY.

2026-09-26 **Set B terminal ledger and proposed implementation**: zero new
export bytes;288-byte capsule,1120 late padding left,374 tail floor untouched.
Pristine post-extent fill corrected to A5; no CRC relaxation. Zero compiler/
dependency/assembler/C/product/guest/device;74 roots/candidates exact. Proposed
one source form with host compile/link attempts2 and dependency1; native
objects16/dependencies8, assembler2; no product build/link/Seed. Not yet an
implementation authorization or executable price. Overall5/0/5, ceiling5/1/5;
Card L/public2.4.0 unchanged. Seal `set-b-clear-protocol-20260926.json`.

2026-09-26 **Set B barrier design halt: CLEAR terminal recovery**:
[report](../planning/set-b-barrier-design-report.md). Proposed256-byte capsule
fits at5F900–5F9FF;1152 internal padding bytes remain, tail374 untouched.
CLEAR may erase export undo before trailing-read delivery; retained header/
C2J/control cannot determine the old function value. Two abstract histories,
not a product run or third defect class. General rollback and quarantine's
live-session/root/abort contract remain unclosed. Public failure43 BAD BYTECODE;
internal streamIO is not a new public error. No product form admitted.

2026-09-26 **Set B design ledger and next decision**: zero compiler/dependency/
assembler/C/build/link/Seed/Final/guest/device;74 roots and candidates exact.
Data price256, executable price unmeasured; inherited ordinary/E000/capture
margins8/25/48 and region0 ceiling unchanged. Next reviewer binding: preserve
undo through the terminal decision, define forward/rollback CLEAR outcomes
and safe native quarantine; then a coherent implementation/pricing commission
with explicit budget. No further local buffer experiment or new Seed.
Overall5/0/5, ceiling5/1/5; Card L/public2.4.0 unchanged.
Seal `set-b-barrier-design-20260926.json`.

2026-09-26 **Set B destination worksheet: no admitted owner with safe reentry**:
[report](../planning/set-b-barrier-owner-report.md). Scratch tail at most61/64;
emitter/recovery overwrite it after release. Larger input/convergence owners
are live; retirement gap24, Bank-5 tail374 entirely floor. The low gap includes
146-byte soft frames. Recovery releases both scratch owners and can clear
READY; retained scratch also contains pointers into returning caller frames.
177 files/227 lexical edges bound; no executed reentry or universal RAM
impossibility claim. Halt before another source form.

2026-09-26 **Set B owner ledger and coherent redesign proposal**: zero compiler/
dependency/assembler/C/product/guest/device, unchanged candidate and74 roots.
Next one host-only storage-and-recovery design for a mutable subowner of sealed
late-region padding (projected1408 bytes, not spendable until a new ownership/
identity/write-watch binding). Bound exact errors, durable facts and bounded
quarantine/reentry; no extra BSS, tail-floor consumption, READY clear or boot
abort. No source/build/Seed yet. Overall5/0/5, ceiling5/1/5; Card L/public2.4.0
unchanged. Seal `set-b-barrier-owner-20260926.json`.

2026-09-26 **Set B trailing-read repair halted at destination lifetime**:
[report](../planning/set-b-barrier-read-report.md). One isolated form restores
ordering in the contract model; 158 content/order rows and two expected
controls. At host attempt64 timeout, the poll returns with64 read bytes still
pending into its function-local destination. No ownership handoff/cancellation
proven; no post-return write executed or hardware defect claimed. Stop before
native pricing. Initial cancelling-XOR oracle error retained and corrected
by replaying the unchanged C library.

2026-09-26 **Set B barrier ledger and lifetime worksheet**: one host compile/
link/dependency, zero native objects/dependencies/product/guest/device. Candidate
parked and unpriced; all74 roots exact. Existing span air5/8 and BSS/E000/
capture1/25/48 is not a capacity claim for the new form. Next existing-owner
destination/quarantine/reuse worksheet, bounded timeout and live session;
no extra BSS, READY clear, boot abort, assumed deadline or second form. Zero
compiler/build/link/Seed/guest/device proposed. Overall5/0/5, ceiling5/1/5;
Card L/public2.4.0 unchanged. Seal `set-b-barrier-read-20260926.json`.

2026-09-26 **Set B ordering authority audit complete; halt retained**:
[report](../planning/set-b-front-ordering-report.md). Manual CPU-stall intent
verified, but Link-59 records relevant late CPU-to-Chip writes (nine-byte
Bank-2 span, five changed bytes; two Bank-5 bytes). Accepted MAP/CPU reads
do not bind a replacement write-drain witness. The inherited delayed-write
obligation remains; permanent loss/reordering coverage is not claimed.
No new hardware defect or partial publication asserted.

2026-09-26 **Set B ordering ledger and proposed barrier repair**: zero
compiler/dependency/assembler/C/product/guest/device executions. All 74 roots
and candidate exact; air 5/8, BSS/E000/capture 1/25/48; consumed 5/0/5,
ceiling 5/1/5. Next one isolated cold trailing-DMA reader form, exact C
ordered-delivery and timeout controls then matched-object capacity; proposed
host compile attempts/links at most two, host dependency one, native objects/
dependencies ten; no product build/link/Seed/Final/guest/device. No new Seed
allocated. Card L/public 2.4.0 unchanged. Seal `set-b-front-ordering-20260926.json`.

2026-09-26 **Set B completion ordering halt**:
[report](../planning/set-b-front-fence-report.md).72 exact-C content checks
pass; matching old C2J lets the actual barrier accept a synthetic state with8
prior-write bytes pending. No full publication/replay or native defect claim.
Unchanged source; missing ordering bridge between historical trailing DMA-read
witness and active synchronous MAP/CPU reader. Stop before replay/repair.

2026-09-26 **Set B fence ledger and next authority audit**: one successful host
C compile/link/dependency; zero native compile/product build/link/Seed/guest/
device. Next read-only binding of CPU-after-DMA completion and the admitted
fault domain; no guarantee assumed from synchronous read alone. Candidate
margins5/8 and floors unchanged; consumed5/0/5, ceiling5/1/5;
Card L/public2.4.0 unchanged. Seal `set-b-front-fence-20260926.json`.

2026-09-26 **Set B real caller/writer host paths qualified at declared seams**:
[report](../planning/set-b-front-paths-report.md).156 caller/error +91 writer/
rollback +138 query/stage C rows pass. Full installer and real selected writer
functions; BADOPCODE→43 remains exact. No real Lisp-form/native proof claimed.
53 inherited sink edges/44 owners bound to candidate hooks; raw I/O remains open.

2026-09-26 **Set B paths ledger and completion-fence obligation**: five host
compile attempts/four successes and links/three dependencies; failed harness
compile and false snapshot-range halt preserved. Stage zero-write returns are
ignored by unchanged source; next actual completion/replay attribution with
partial/stale/readback faults. No source/air change:05b5free,ordinary8margin.
Zero native compile/product build/link/Seed/guest/device; consumed5/0/5,
ceiling5/1/5; Card L/public2.4.0 unchanged. Seal `set-b-front-paths-20260926.json`.

2026-09-26 **Set B start/length capacity and bounded C gates pass**:
[report](../planning/set-b-front-span-report.md).05b1787/1792,5free;
helper50, ordinary776 leaves40/floor32,8margin. All63 records fit, region0
65205/65536; BSS/E000/capture margins1/25/48. Only05b/helper differ from limb;
181 other allocated sections match. Candidate isolated, not product-admitted.

2026-09-26 **Set B span qualification ledger and remaining closure**:
941 decoder/helper +229 caller/scratch C rows pass, both falling error controls
retained.10 native objects/10 dependencies;3 host compile attempts/2 successes
and host links/2 dependencies. First harness compile failure archived. Real
writers/transport/full transient caller/raw-write closure and exact VM errors
remain open; next host-only closure before native cold/stack/GC/identity gates.
Zero product build/link/Seed/guest/device; consumed5/0/5, ceiling5/1/5;
Card L/public2.4.0 unchanged. Seal `set-b-front-span-20260926.json`.

2026-09-26 **Set B checked-end reuse rejected at capacity**:
[report](../planning/set-b-front-end-report.md).05b grows27 versus limb, linked
1826/1792 (34over); no actual-C gate started. Helper38/ordinary764 unchanged,
20 resident margin. Against limb only05b changes;182 allocated sections match
in bytes/relocations. Keep limb's seven-byte-over form as best parked control.

2026-09-26 **Set B end-reuse ledger and next form**: ten successful native object
and ten dependency calls; region0 65269/65536 (267free,64 above design ceiling),
region3 6784/8192; all floors retained. Next one isolated start/length helper
interface over limb, exact validator, direct joint caller/callee object pricing
under unchanged137/58 caps before C. Zero host C/product build/link/Seed/guest/
device; consumed5/0/5, ceiling5/1/5; Card L/public2.4.0 unchanged.
Seal `set-b-front-end-20260926.json`.

2026-09-26 **Set B seven-byte audit complete: checked-end reuse proposed**:
[report](../planning/set-b-front-end-plan-report.md). Compute end once, retain
explicit wrap/limit refusal and all other checks, pass only after full acceptance.
706,538 range/4,117,976 address model cases pass; missing-wrap control falls.
All1834 caller/helper instruction bytes accounted; no actual C qualification.

2026-09-26 **Set B end-reuse design ledger**:82-byte pool→63 target (39 symbolic
core+24 spill/liveness allowance),19 saved plus12 further05b drift. Hard1792
slice/784 ordinary/65205 region0 caps unchanged. Helper38/ABI unchanged; ordinary
764 retains20 margin. Fit unmeasured. Next one isolated05b-only form, capacity
before C. Zero compiler/link/Seed/guest/device; consumed5/0/5, ceiling5/1/5;
Card L/public2.4.0 unchanged. Seal `set-b-front-end-plan-20260926.json`.

2026-09-26 **Set B directory-difference/byte-max capacity halt**:
[report](../planning/set-b-front-limb-report.md).05b saves32 bytes but remains
seven over: delta144/cap137, linked1799/1792. Helper66→38 now fits; ordinary764
leaves52/floor32,20margin. No C execution after failed capacity gate. Next
read-only audit of seven overlay bytes plus caller costs/resident margin before
one further bound form; no floor waiver or new semantic defect claimed.

2026-09-26 **Set B byte-max owner ledger**: ten successful native object and ten
dependency calls;26 changed/157 unchanged sections.05a/Entries exact,04+15.
All63 records: region0 65237/65536 (299free,32 above design ceiling), region3
6784/8192; E000/BSS/capture margins25/1/48. Zero host C/product build/link/Seed/
guest/device; consumed5/0/5, ceiling5/1/5; Card L/public2.4.0 unchanged.
Seal `set-b-front-limb-20260926.json`.

2026-09-26 **Set B joint ABI cost plan complete, fit unmeasured**:
[report](../planning/set-b-front-abi-report.md). Directory-anchored16-bit checks
retain upper-byte refusal and exact read/error order; same-interface byte-indexed
pending max. All1894 existing caller/helper instruction bytes accounted.
4,117,976 predicate/589,806 byte-max model cases pass, no C or ABI execution.

2026-09-26 **Set B ABI design ledger**: target pool240→185 (worksheet122 plus
63 bridge/spill allowance); helper66→50 (worksheet33 plus17). Allow16 further
05b and8 resident drift; unchanged hard caps1792/784 and region0 ceiling65205.
These are allocations, not compiler predictions. Next one isolated C form;
objects/packing first, actual C only after all caps/floors pass. Zero compiler/
link/Seed/guest/device; consumed5/0/5, ceiling5/1/5; Card L/public2.4.0 unchanged.
Seal `set-b-front-abi-20260926.json`.

2026-09-26 **Set B fused05b/resident-max capacity halt**:
[report](../planning/set-b-front-fused-report.md). Helper66/cap58;05b+176/cap137,
linked1831/1792; ordinary792 leaves24/floor32. Exact05a/Entries restored,04+15
retained. Capacity rejects the one isolated form before C; no semantic defect,
error-order pass or lifecycle pass claimed. Next read-only joint disassembly/
ABI audit for39 overlay plus8 resident bytes saved, no floor waiver.

2026-09-26 **Set B fused form owner ledger**:26 changed/157 unchanged allocated
sections; ten successful native object compiles and ten dependency calls.
All63 records packed: region0 65269/65536 (267free,64 above design ceiling),
region3 6784/8192; E000/BSS/capture margins25/1/48. No host C/product build/
link/Seed/guest/device; consumed5/0/5, ceiling5/1/5. Card L/public2.4.0 unchanged.
Seal `set-b-front-fused-20260926.json`.

2026-09-26 **Set B error-order analysis complete, implementation unqualified**:
[report](../planning/set-b-front-order-report.md). Additional05a base read also
changes fault precedence; restore05a and keep refusal/accumulation at05b's row
point. Stable range-domain and conditional outer BAD BYTECODE mapping documented,
no waiver.4,117,976 predicate comparisons/2,268 order-model rows pass; no new C,
transport/lifecycle or exact runtime successor proof.

2026-09-26 **Set B fused05b/resident-max proposed ledger**:04 retains+15;
helper plus resident drift cap58,05b cap+137, aligned region0 max65205/65536
(331free), E000/BSS/capture margins25/1/48. At least75 net bytes must disappear
versus old monolithic05b even if all58 resident bytes are used. Fit and native
cost unmeasured. Next isolated object/packing gates before actual C; no product
attempt. Zero compiler/build/link/Seed/guest/device; consumed5/0/5, ceiling5/1/5.
Card L accepted, public2.4.0 unchanged. Seal `set-b-front-order-20260926.json`.

2026-09-26 **Set B04/05a C successor: error-precedence halt**:
[report](../planning/set-b-front-relocation-report.md).39 selected C rows pass;
first combined bad-range/later-source-read fault changes IO1 to ENTRY5.
Exact extracted phases, semantic read injection; synthetic execution-plane
mutation, supported-domain reachability and final VM error mapping unbound.
No new shipped defect/data corruption claimed; no tolerance or further lifecycle
qualification. Next read-only fault-domain/phase-order analysis before another form.

2026-09-26 **Set B relocation object/packing ledger passes**:04+15/96,05a+328/
352,05b and Entries restored byte/relocation-identical. Region0 65397/65536,
139free; region3 6784/8192. Text726/E00036/BSS4 margins58/25/1;25 changed/157
unchanged sections. Ten native compiles/dependency calls each; two host compile
attempts, one success/link, one host dependency call. Packing/scaffold failures
and corrections retained. Zero product/guest/device; consumed5/0/5, ceiling5/1/5.
Card L accepted, public2.4.0 unchanged. Seal `set-b-front-relocation-20260926.json`.

2026-09-26 **Set B front placement/lifetime plan complete**:
[report](../planning/set-b-front-placement-report.md). Proposed04 guard seed
and05a provisional max; use dead header bytes for execution base, retain exact
05b/Entries bodies and terminal certification.383657 arithmetic cases,804
captured entries,256 suffix cases; no candidate C or integrated fault proof.
Extra base reads introduce open fault-precedence/stability gates; no new defect.

2026-09-26 **Set B placement aggregate ledger**:04/05a caps+96/+352 (unmeasured),
aligned growth448; Session region0 max65493/65536,43free. Existing record air
388/665 alone is insufficient; initial aggregate air491. Text/E000/BSS margins
58/25/1 retained as gates, no additional catalog record. Conditional8 reads/
24bytes and up to1344 extra payload bytes across3 decodes; cold/stack unpriced.
Next isolated form must pass objects/packing before C fault qualification.
Zero compiler/product/guest/device; consumed5/0/5, ceiling5/1/5; Card L accepted.
Seal `set-b-front-placement-20260926.json`.

2026-09-26 **Set B isolated front integration: overlay halt**:
[report](../planning/set-b-front-integration-report.md). Hook/decoder/raw-poke
candidate parked; unchanged r2 helper,11 source-order assertions, no integrated
semantic fixture or complete writer/raw-I/O closure. Original generator's
extraction failure retained. No new product defect or relaxed exact error.
Six object compiles/six dependency calls exit0; zero product/guest/device.
Consumed5/0/5, ceiling5/1/5; Card L accepted, public2.4.0 unchanged.

2026-09-26 **Set B integrated owner ledger**: text726, air90/floor32 (58margin),
BSS4, air6/floor5 (1margin), E000+36, air79/floor54 (25margin).05b+270:
linked projection1925/1792,133short; Entries+34:1805/1792,13short. Raw objects
1922/1823 also fail1792. Journal reconstruction−10; inherited control+83/reset−3;
scanner1743/1792 unchanged.25 allocated sections changed,153 unchanged. No
new linked layout/packing/time claim. Next proposed read-only owner/capacity
plan covering both slices before another isolated implementation. No sixth
Seed. Seal `set-b-front-integration-20260926.json`.

2026-09-26 **Set B shared scanner r2: isolated C proof complete**:
[report](../planning/set-b-shared-front-report.md). 4,554 C rows plus2,421
scratch-lifetime faults; exact existing scanner/entry, transport/cons and
recovery hook ordering explicitly stubbed. R1 longjmp marker/trace gaps
preserved; r2 persistent trace plus REFILL cleanup resolves them under the
proposed pre-recovery hook. No real RUN/STOP/INIT/native error gate claimed.
No new product defect; consumed5/0/5, ceiling5/1/5; Card L accepted.

2026-09-26 **Set B shared scanner object ledger**: r2 query448+helpers153+
VM25=626text,266saved; air190/floor32, remaining158. BSS4 givesair6/floor5,
remaining1. Existing scanner1743/1792 unchanged;162 allocated sections in total
match. Inherited control+83/reset−3; extent6784/tail1408, journal72. Eight
object compiles/eight dependency calls/two host C compiles+links; zero product/
guest/device. Next proposed isolated hook/decoder integration and owner price;
no sixth Seed or product admission. Seal `set-b-shared-front-20260926.json`.

2026-09-26 **Set B scanner-sharing lifetime audit complete**:
[report](../planning/set-b-scanner-reuse-report.md). Existing Session29 request62
can scan persistent rows with transient_first2048, done64; resident wrapper
must validate header/count/generation/table base, acquire APPEND exclusively,
copy result before release/cons and preserve diagnostic byte302. Transport
failure can latch fault; normal provenance restoration and nonlocal-abort
successors remain explicit gates. No new behavior executed or defect claimed.

2026-09-26 **Set B scanner-sharing space ledger**: existing scanner1422+
entry321=1743/1792, air49. Reusing its request needs no new entry by design;
exact codegen is unpriced. Helpers103+VM25 leave656 for query and integration;
need at least108 net reduction before hooks, no claimed1422-byte saving.
74 compiler roots verified, zero compiler/build/link/Seed/guest/device.
Consumed5/0/5, ceiling5/1/5; Card L accepted. Next proposed isolated host
wrapper/scan fixture plus object price, no product attempt.
Seal `set-b-scanner-reuse-20260926.json`.

2026-09-26 **Set B isolated certificate C: semantic pass, admission halt**:
[report](../planning/set-b-front-prototype-report.md). 4,536 actual-C rows,
2,049 legal counts and2,421 partial-read failures; abort/refill, BUSY, raw
taint and warm-header successor executed. Raw taint until trusted boot is a
prototype policy only. Missing-hook falling control yields stale data; no
new product defect. Writer hooks/decoder accumulation and real INIT remain
open. Zero product/guest/device; consumed5/0/5, ceiling5/1/5; Card L accepted.

2026-09-26 **Set B certificate object space ledger**: query764+helpers103+
VM25=892 resident bytes versus784 available,108short; textair−76/floor32.
BSS3 fits, air7/floor5. Control+83/reset−3 inherited; extent6784/tail1408.
162 other allocated sections unchanged. Four object compiles/four dependency
calls and one host C compile/link. Halt before integration; no new Seed or
extra budget requested. Next proposed host-only read-only scanner sharing
and lifetime plan must prove overlay/scratch ownership (recordair49).
Seal `set-b-front-prototype-20260926.json`.

2026-09-26 **Set B front-certificate conditional design; no implementation**:
[design](../planning/set-b-front-certificate-design.md). 53 direct sink edges,
44 classified owners,74 compiler roots verified; raw/indirect write closure
remains open. 324 model rows reject generation/count-only and implicit cursor
undo designs. Recovery copies current entry_cursor to predecessor: invalidate
and refill if the field gains front meaning. These are design counterexamples,
not new product defects. Public poke/raw I/O and warm-read fault successor need
binding. No compiler/product/guest/device use; consumed5/0/5, ceiling5/1/5.

2026-09-26 **Set B certificate storage and scan ledger**: preferred front16/
state8 adds3 BSS bytes, air7/floor5; seven-byte copied-key design fails (air3).
Phase05b137 bytes air; existing scanner49; scalar-refill retention leaves97
resident bytes for other additions. Code sizes unmeasured. Conditional INIT
eliminates3191 additional row scans, adds accumulator work to804 existing
visits and retains4 eight-byte header reads. No cold pass. Next proposed
host-only barrier/refill prototype needs explicit mutation/fault binding.
Seal `set-b-front-certificate-design-20260926.json`. Card L stays accepted.

2026-09-26 **Set B bounded batch query: semantic pass, admission halt**:
[report](../planning/set-b-library-load-batch-report.md). 60-byte/six-entry
form passes2725 actual-C rows, including all legal counts and408 partial
transport failures. Lisp/VM/prefix unchanged from native r2; old packing and
SBCL receipts reused. No product/guest/device execution. Consumed5/0/5,
ceiling5/1/5; Card L accepted. No sixth Seed or extra product budget requested.

2026-09-26 **Set B batch space/copy/stack ledger**: query828+VM25 resident;
textair−37 versus floor32 (69short), hypothetical resident admission1292,
not admitted. No new BSS; control+83/reset−3, extent6784/tail1408 unchanged
projection. Local software frame68/buffer60, caller/callee high-water still
open. INIT537 reads/31942 bytes; exact existing copy-loop gross floor349751
cycles/8.635827ms versus277701/6.856815ms remaining. No new boot/LTO claim.
Next proposal: host-only validated-front certificate design, complete writer
and invalidation coverage, storage/scan pricing before implementation.
Seal `set-b-library-load-batch-20260926.json`.

2026-09-26 **Set B indexed-load preflight closed; cold-cost admission halt**:
[report](../planning/set-b-library-load-preflight-report.md). Both candidate
forms pass eight SBCL cases/twelve requires, including INIT and fast-note;
publication replay and native-query model are declared seams. Independent
actual-C query passes1,019 rows. Canonical code/metadata before match consumed
stdlib. Full Lisp delta214/2/15/0, native57/0/3/0 (code/entries/resolutions/roots).
No product builds/links/Seeds/device/guests. Card L accepted; consumed5/0/5,
ceiling5/1/5. Three reference-VM/experimental collector failures discarded
and sealed, not product/GC evidence. Seven product-consumer routes remain open.

2026-09-26 **Set B native query price; no sixth Seed admission**: INIT scans
3191 rows. Full Lisp exact-ELF leaf floor823278 cycles/20.328ms; native
non-LTO object loop projection478650/11.819ms versus277701/6.857ms margin.
Native projection is not a future LTO bound or executed cold timing.
Parked r2 query+662/VM+25, textair129/floor32; resident admission would1126
from439, not approved. Control+83/reset−3, extent6784/tail1408. New private
selector17 needs native binding; READY/prefix checks retained. Next proposal:
bounded batch query host-only with scratch/stack and cost/air proof. No extra
product budget requested. Seal `set-b-library-load-preflight-20260926.json`.

2026-09-26 **Set B load cause closed; repair not Seed-ready**:
[report](../planning/set-b-library-load-attribution-report.md). Existing fifth
Seed needs one replacement to reproduce NIL. Lisp persistent-row code-base
predicate rejects C60D versus C603; all other row predicates pass. Charged
retired code creates the ten-byte gap. No capacity shortage/append error:
projected library leaves9009 code bytes. Fresh/one-definition controls T.
Six private guests; existing ELF/media immutable. Qualification still halted,
Card L accepted, consumed5/0/5 with no further Seed/link authorized.

2026-09-26 **Set B resolver/prefix repair cost ledger**: parked three-file
patch in `build/set-b-load-repair-proposal-r5/authored.patch`; 12 targeted
Lisp,10 world-gate,12 C latch/refusal rows pass. Lisp+214/two private entries;
control+83/reset−3 matched objects;82 other sections unchanged. Projected
control record448→480, extent6752→6784, tail1440→1408; reset record256 retained.
First-prompt capture corrects observed six versus design eight. No READY
relaxation. Full entry scan423144 host VM steps/4824 reads at804 entries;
native timing unmeasured, existing cold margin6.857ms. Next: host-only
cost/packing and indexed/fast-note consumer closure before replacement budget.
Seal `set-b-library-load-attribution-20260926.json`.

2026-09-26 **Attribution harness multi-pair setq limitation**: r1 initialized
three globals in one setq, but delivered `%lcc-setq` handles its first pair;
the generation predicate then refused the wrong test argument. r2 uses
single-pair forms and closes attribution. Separate native `compile_setq`
supports pairs; no broader compiler parity conclusion or product repair here.
Raw r1 preserved; this row prevents treating it as directory corruption.

2026-09-26 **Set B fifth Seed workload halt**:
[report](../planning/set-b-fifth-seed-workload-halt-report.md). ELF139e7775,
D81587136f5; complete inventory/readback, positive and negative boot,
resident begin/end and 50 prompt replacements pass. Nine images remain;
all804 original objects unchanged. Next require defstruct→NIL instead of T;
READY1/arm86, full C2D/Bank2 unchanged, tenants intact. Cause unassigned.
Exact lambda BAD BYTECODE/NIL/42 successor passes. Qualification halted;
consumed5/0/5, ceiling5/1/5; no sixth Seed or Final. Card L accepted.

2026-09-26 **Set B fifth cost/remaining ledger**: text816/32, E000115/54,
capture105/57, highBSS10/5, tenant extent6752/tail1440. Cold+19,972,299 cycles
(+0.493143 s), margin277,701 cycles (6.857 ms). Natural lanes, matched GC,
hot-range, full native fault/capacity/carrier/usage and consumer closure
remain unexecuted/unclosed; no inherited cost exception. Fifteen guests,
six observer builds (failed instrumentation retained), one product link,
four delivery-stager links. Proposed existing-Seed load-refusal attribution
and six/eight-prefix reconciliation is not launched. All evidence sealed in
`set-b-fifth-seed-workload-halt-20260926.json`; no device or release claim.

2026-09-26 **Set B fifth attempt admitted**: owner “Freigabe erteilt”
on `95d36be5`; ceiling5/1/5, consumed4/0/4 before execution. Exact parked
resident/control patch, resident439, tenant extent6752/tail1440 unchanged.
Seven dated consumer implementations and Final driver prepared; ordered
executed gates remain required. No implicit retry/member5/device/release.
Card L remains accepted; activation and all later receipts determine status.

2026-09-26 **Set B transaction-boundary repair proposed**:
[executed attribution and patch](../planning/set-b-transaction-boundary-repair-proposal.md).
Fourth Seed `2ba1deb4…`: reset OK/armed; first control begin sees busy1,
returns3, control returns8; later READY1/arm0, tenants/journal intact.
Parked resident begin/end helper plus control ownership removal; cleanup
still runs on end failure. Eleven candidate host C fault rows PASS.
Matched objects resident+193/control−47, 81 other allocated sections same;
text air projection816/32, extent6752/tail1440. Admission246→439 proposed.
One guest, two objects, two dependency calls, one host C test link; zero
product links/Seeds/device. Consumed4/0/4, proposed ceiling5/1/5 ungranted.
Maintained native sources unchanged, Card L accepted, qualification halted.
Seal `set-b-transaction-boundary-repair-20260926.json`.

2026-09-26 **Set B fourth Seed activation halt**:
[report](../planning/set-b-fourth-seed-activation-halt-report.md), source
`958a7d2a`, execution`8c0f3289`, ELF`2ba1deb4…`, D81`a4c24c8a…`.
Four-reader repair linked; complete inventory zero unclassified
bytes/relocations; 80-record media readback and three host controls pass.
One guest: prompt/READY1, arm0; no subsequent form. Tenants intact,
journal zero. Static control transaction-begin versus overlay-busy conflict
proved, first executed failure remains unknown. Qualification halted;
consumed4/0/4, ceiling4/1/4, no retry. Next proposal: host-only boundary
trace and repair pricing on the existing ELF, no new Seed/link. All tools
and receipts sealed: `set-b-fourth-seed-activation-halt-20260926.json`.
Card L accepted; source run/Final, actual consumers and device rows pending.

2026-09-26 **Set B read-path replacement admitted**: owner “Freigabe erteilt”
on proposal `76cc19b7`; ceiling4/1/4, consumed3/0/3 before execution. Exact
four-file patch, 64+8 read, extent6752/tail1440. New fourth-Seed source/command
successor; old producer/tools retained. Fresh admission, full inventory,
ordered guest gates, consumer closure, exact-HEAD sealed source and Final
identity required. No implicit retry, member5, device or release. Card L
remains accepted; attempt and qualification receipts determine later status.


2026-09-26 **Set B read-path repair designed; new Seed unbound**:
[proposal and executed attribution](../planning/set-b-read-path-repair-proposal.md).
Unchanged Seed `1eb22d52…`: reset reader return identity C3F6 selects overlay
execution at2374; read sentinel unchanged, reset error3, READY1/arm0 at prompt.
Candidate calls the real synchronous reader from four C356 owners and splits
72 into64+8. Matched object closure: four include changes, +25 prepare bytes,
79 other allocated sections unchanged, no BSS/slot/E000 growth. Canonical
record +32, late extent6752/tail1440; three geometry controls reject.
Two object compiles, two guest launches (one invalid trace), no product link,
Seed or device. Proposal patch and all receipts sealed; product source unchanged.
Current charge3/0/3; proposed ceiling4/1/4 needs a new owner budget word.
Card L remains accepted; activation/Final halted. Seal
`set-b-read-path-repair-20260926.json`.


2026-09-26 **Set B inventory closed; positive activation halt**:
[report](../planning/set-b-seed-qualification-halt-report.md), scope admission
`8a3eac10`, unchanged ELF `1eb22d52…`, medium `3fafddc9…`. Complete linked
inventory: zero unexplained bytes/relocations; +10 access-widening bytes
proved, no new codegen family. Host readback: 80 records, seven tenants,
three falling disk controls; corrected temporal journal injection pending.
One guest launch: prompt visible, READY=1, retirement latch=0. Tenant image
intact, journal zero. Exact static selector proof: new reset/commit reader
return identities route to overlay execution, not physical read. Boundary
trace still needed to distinguish first refusal from later disarm; no
corruption claim. Halt; Card L remains accepted. Proposed 0-Seed/0-link
repair-design commission, rebuilt product requires a new budget binding.
Charged 3 Seed attempts / 0 Finals / 3 product-link attempts; no additional
product build, no device. Seal `set-b-seed-qualification-halt-20260926.json`.

2026-09-26 **Set B third Seed linked; inventory scope halt**:
[report](../planning/set-b-third-seed-inventory-halt-report.md), authority
`7a4e43fa`, execution `7c659dfd`, ELF `1eb22d52…`. Geometry passes:
text 1009/32, E000 115/54, capture 105/57, tenant extent 6720, tail 1472.
Two new zero-page latches displace `vm_buf_off` to `$BB67–$BB68`; ten
LDX/STX/STY instructions widen in four unchanged function bodies (+10 bytes).
Exact access witnesses retained; complete inventory/behavior not closed.
Under the bound outside-members rule, defer media/execution for a decision
on this named codegen family using the existing Seed (no new link needed).
Charged 3 Seed attempts / 0 Finals / 3 product links, one successful link.
Card L remains accepted; seal `set-b-third-seed-inventory-halt-20260926.json`.

2026-09-26 **Set B placement revision host-closed; Seed unbound**:
[report](../planning/set-b-placement-revision-report.md). A section-only move
of the 40-byte `c2_overlay_call` to E000 gap1 has matching object instructions
and relocation operands, zero new low edges, zero added code/BSS. Projected
helper margin 36, receiver margin 59, capture 105/57, E000 115/54. Canonical
32-byte padded intervals reserve 6,720 / 8,192 bytes; every padding byte is
charged and authenticated. Unchanged builder/validator: 9 passing host
checks, 7 rejected controls. Two object compiles, no product link/Seed or
execution. Initial basename false red and 16-byte proposal are retained.
Source revision uses AUTH_PENDING; cumulative charged 2/0/2, proposed next
ceiling 3/1/3 requires a new binding. Card L Final stays accepted. Seal:
`set-b-placement-revision-20260926.json`.

2026-09-26 **Set B replacement: placement halt**, authority `7bef0c2c`,
execution HEAD `f4ec7c98`; [report](../planning/set-b-replacement-seed-halt-report.md).
The admitted semicolon correction passes syntax. Product link now rejects
Comfort helper end `$FD26` against fixed `$FD22`: resident growth +31 is
fully attributed to `c2_overlay_call` +11 and GC-root marking +20; capture
assembly is unchanged. Failed-link map/LTO also confirm four-byte backing
interval overruns in slots 59 and 61. No product ELF/PRG, media or execution.
Charged cumulative 2 Seed attempts / 0 Finals / 2 product-link attempts;
replacement consumed, no third link authorized. Proposed host-only 0/0/0
placement revision addresses both constraints before another Seed binding.
No floors or roots relaxed; Card L Final remains accepted. Seal:
`set-b-replacement-halt-20260926.json`. Previous halt evidence is preserved.

2026-09-26 **Set B first Seed: linker-syntax halt**, authority `4f843a79`,
handover `bad4c939`; [report](../planning/set-b-seed-link-halt-report.md).
Green source, symbol and E000 probes; product link command 75 rejects a
trailing semicolon on the journal ASSERT inside included `c.ld`/SECTIONS.
Cause reproduced by two synthetic parser fixtures; one-character patch
prepared, not applied. Charged 1 Seed / 0 Finals / 1 product-link attempt;
no executable Seed exists. Further product link needs rebinding; replacement
Seed uninvoked. Keep Card L accepted. Slots 59/61 placement and every media /
guest / Final gate remain open. Media journal control must follow corrected
step 3b (boot disarmed with READY=1; failed replay explicitly fail-closed),
not the adapter's older READY=0 prescription. Seal:
`set-b-seed-link-halt-20260926.json`. Object probes do not validate linker
grammar; reduced grammar admission is needed before a replacement link.

2026-09-25 **Card L closed on the host** (`card-l-final-report.md`, seal
`card-l-final-20260925.json`): Bank-5 late region `$5DE80–$5FE7F` and gap
`$5DE20–$5DE7F` are named owners; the Session slot-55 stage slice copies
the five Boot-family marker records (8,192 bytes, CRC16 `0x7B72`) after
the boot publication; executed proof zero bytes changed across the
workload; controls refuse cleanly. Limits: snapshot proof, not writer PCs;
device cold boot and marker on hardware batched. First red = media
pipeline (Session overflow header CRC), tool class, fixed without relink.

2026-09-25 **code-object reload burst: second witness** — Card L single-key
bracket 31 (+934,912 instructions in `c2_map_cpu_read`, `vm_run_inner`,
`vm_object_load`, `c2_product_entry_record`), deterministic, no
collection; anchor Final bracket 38 was the first. Named cost accepted on
Card L; **reopened** as its own host-only attribution card (trigger,
layout dependence, once-per-session behaviour).

2026-09-25 **Codex counter-review corrections (Set-B carrier preflight):**
Bank 5 has 0 spendable bytes above the 374-byte tail floor; after the
boot publication the boot name index's **8,192 payload bytes** become
unused while its **10-byte header stays live** (post-publication readers:
`c2_append_publish_plan_resolve_phase` → `c2_boot_name_index_head_get` →
`c2_boot_name_index_read`; index reads are guarded off by the zero
header); a separate **96-byte gap** at `$5DE20–$5DE7F` is unbudgeted. The
mark-hook rejection is **0.317–0.444 %** on the 2.4.0 denominator
5,385,995. Comfort inventory: all six claims verified. Receipts:
`build/codex-review-2026-09-24/task1-review.md`, `task1-artifact-checks.json`.

2026-09-25 **Comfort medium GC placement shift, named cost accepted:** the
sixth index row makes the startup `require`s collect 5 instead of 3
times; plain-prompt forced collection 5,385,995 → 5,432,257 (+0.86 %),
natural +0.12 %, live cells and shadow graph identical; lanes 0.9653 /
0.8608. Class: medium layout (every added package shifts it). Open: a
PC-instrumented pair as in the GC layout control; the column-26 cell
blanking on the emulator (by-catch, unattributed).

2026-09-25 **Comfort library host-closed** (binding `180cb993`;
[report](../planning/comfort-library-host-report.md), seal
`comfort-library-final-20260924.json`, Comfort D81 `bb9b8d56…`, 0/0/0).
Sixth package `repl-comfort`, 897 B, C1–C14 delivered, runtime and 18 files
unchanged. Open: the device session with the owner
([plan](../planning/comfort-device-plan.md), SD name `CMF240.D81`) and the
three surface questions (prompt `l65>`, multi-line scrollback, over-close
text). Named cost for acceptance: the sixth `L65INDEX` row gives two more
boot collections (`gc_runs` 3 → 5). Plain-prompt matched GC is +6,908 /
+46,262 cycles (+0.12 / +0.86 %) at identical live cells, and the natural
lanes are faster (0.9653 / 0.8608), not cycle-identical. Every future
package added to a medium with `INIT.L65` carries the same class of shift.
`repl` is 249 B (object-slack exception stated). An error inside Comfort
lands at `lisp65>` (by design; a landing inside Comfort needs a native
hook, behind Set B).

2026-09-25 by-catch (Comfort library card):
(a) The prepared branch library (`comfort-prepare-now`, and the era-bound
`lib/repl-comfort.lisp`) wraps the input as `"(progn " source ")"`, so a
trailing `;` comment swallows the `)`. It is fixed only in
`lib/repl-comfort-v240.lisp`; the old file is unshipped and untouched.
(b) Emulator: a single screen cell in **column 26** is blanked during some
operations (`require`, `load-lib`, evaluation). It shows up with and without
Comfort on the 2.4.0 D81 (inventory native rows `(STRING-LENGTH "("`,
`(REQUIRE "INSPECT"`). Not attributed; to be watched at the device session.

2026-09-24 **capacity watch corrected**: the overlay catalog is checked per
family in the built verifier (`cpx #$41` at `$C5EC`): Session 55/64,
Boot 12/64; the "unique 63/64" figure carried since the boot-name-index
card was a reported value, not a limit. A further Session slice tops out
at **1,088 bytes**, not 1,351, because the 56th catalog entry pushes the
directory across a 256-byte boundary. **Tool defect:**
`tools/host-lisp/slice_capacity_preflight.py` misses that 256-byte step;
successor needed before the next slice card (`set-b-carrier-preflight.md`).

2026-09-24 Set B carrier decision: Bank 5 has 0 spendable bytes (374 =
floor), but the boot name index `$5DE80–$5FE89` (8,202 bytes) is dead after
the boot publication by source → candidate **late region staged from Attic**
(Card L). Reopening of the mark-hook form rejected: +0.32–0.44 % per
collection. Register keeps: no executed write-watch proof of the region yet.

2026-09-24 by-catch (Comfort inventory): `(require "<absent>")` prints
`LOADING …` before returning `NIL` (2.4.0); the branch Comfort suite
(comfort-prepare-now) is stale against 2.4.0's two shipped display rules
(echo of the accepted line with its prompt; prompt moves up on a wrapped
line) — 5/19 pass unchanged, 19/19 with the rules restated.

2026-09-24 **nested-error recovery Final (host)**
([report](../planning/nested-error-recovery-final-report.md), seal
`nested-error-recovery-final-20260924.json`, Final ELF `66165507…`). The
nested-error session loss (shipped in 2.3.0) is closed on the host: errors
raised through `eval` inside running forms, over-cap definition loops and
depth-2 nesting recover with the exact error and a live prompt, nothing
published changes. Named placement GC cost accepted (`eaf59c62`): +2,905 /
+2,641 cycles per collection. Open: RUN/STOP inside a running form
(not injectable on the host, batched device row), device rows (owner word).

2026-09-23 **nested-error recovery halted at the GC named-cost rule**
(binding `44c021ee`, authority `90b5f9f2`;
[report](../planning/nested-error-recovery-halt-report.md), seal
`nested-error-recovery-halt-20260923.json`). One Seed (`66165507…`), no
Final. The fix works in the post-halt diagnostic rows (nested and depth-2
errors recover with a live prompt, nothing changes in the directory or Bank
2), but the fast path's growth of 145 bytes moves ten GC branch sites across
pages: +2,905 / +2,751 placement cycles (0.051 % of a collection, above the
0.05 % named cost). A 5-byte pad projects to about 0.006 %. The session-loss
defect stays open (shipped in 2.3.0) until the reviewer decides between the
replacement Seed and deferral.

2026-09-23 **corrected: nested-error session loss (supersedes the over-cap
row of the same day).** Any error raised through `eval` inside a running
top-level form leaves the session without a prompt: the fast recovery
path `c2_abort_empty_journal_derived` (`6398ae4b`) skips the journal
write, its checksum check times out and clears `c2_ready`; every
published Lisp call, prompt and `read-line` included, then fails. Verified
on the repair Final, the anchor and **public 2.3.0** (`(let ((q 1))
(eval '(capzz)))`, 9 images). Fail-closed, no corruption. The over-cap
loop is one instance. Status: **product defect, card bound** ("nested-error
recovery", plan entry 2026-09-23). Known-issues candidate for 2.3.0 (owner
wording): "An error inside `eval` called from within a running form (e.g.
inside `dotimes` or `let`) leaves the REPL without a prompt; reset
required; nothing already defined is lost." Open: RUN/STOP inside a
running form (same landing by source, unmeasured).

2026-09-23 **class (a) scope corrected:** every anonymous `lambda` in a
top-level form outside a `defun` body is refused with `VM: BAD BYTECODE`
(`setq`/`setf`, `mapcar`, `funcall`, `let` forms alike); lambdas inside
`defun` bodies and closures returned from them work. Designed refusal
pending Set B promotion (next cycle). Known-issues candidate (owner
wording): "Anonymous `lambda` forms are supported inside `defun` bodies;
at the top level they are refused with `VM: BAD BYTECODE`, the prompt
recovers and nothing already defined is affected."

2026-09-23 **Definitions Set B members (a) retirement, (b) slot reuse,
(d1) promotion deferred to the next cycle**: projected air ≥ 4,113 B
(sketch, unmeasured) against 1,354 B text reserve and 374 B Bank 5, ≥ 2
catalog slots against 1 free; the collector marks no images today, so
retirement by reachability needs a marking mechanism first. Reopening:
next-cycle binding with an air plan (a slice or Bank-5 owner) and the
positive `funcall` row for class (a) as its gate. Preflight:
`definitions-set-b-preflight.md`.

2026-09-23 **over-cap definition loop does not recover** (found by the repair
card, present on the anchor and the repair Final): running
`(dotimes (n N) (eval '(defun f () 7)))` past the 64-image cap in one boot
prints repeated `*** VM: UNDEFINED FUNCTION` and never returns a prompt
(900 s observed), whereas the direct top-level sequence refuses image 65
with `OUT OF MEMORY` and a live prompt. Status: **product defect**, the
`eval`-inside-a-running-form path fails to recover from the capacity
refusal; probably behind the attribution card's cumulative N = 54 runs
recorded as host crashes. Owner of the fix: Definitions Set B (capacity
and error members). Reopening/closing condition: a bound row with the
over-cap loop returning to a live prompt with exact error and the
directory unchanged.

2026-09-23 retained-callable repair Final accepted (`03dd59b4`): world
ELF `815b60a5…`, D81 `fdb95e71…`; class (b) closed on the host; journal
slice 1,760/1,792; two consumer successors dated 20260923 plus a Card-5
receipt for the `gates.mk` change.

2026-09-23 **retained-callable repair Final (member 2)**
([report](../planning/retained-callable-repair-final-report.md), seal
`retained-callable-repair-final-20260923.json`, Final ELF `815b60a5…`).
Class (b) closed on the host: the transient-retirement wipe uses the retiring
image's own span; N = 1/2/16/54 publish valid objects. Class (a) stays a
designed refusal pending Set B promotion (exact `BAD BYTECODE`, nothing
published). New observation, pre-existing on the anchor: publishing past the
64-image cap from inside a running form (e.g. 28 images, then a 54-iteration
`eval`/`defun` loop) loops on `*** VM: UNDEFINED FUNCTION` without a prompt;
parked for its own card. Device rows pending (owner word).

2026-09-23 **class (a) reclassified: designed refusal pending Set B promotion.**
The repair Seed (`65995b51`) showed that lifting the phase-12 refusal lets
a callable escape a transient image that is retired at the end of its
form (`funcall` → `UNDEFINED FUNCTION #FFE`, handle 4094 dangling). Until
Definitions Set B promotes escaping callables to persistent publications,
the refusal stays; member 1 of the repair card is withdrawn. Reopening
condition: Set B binding with a promotion mechanism and the positive
`funcall` row as its gate. Also noted, unattributed: the anchor Final's
single-key lane has one bracket with 934,919 extra code-object-reload
instructions that the repair Seed does not show.

2026-09-23 **retained-callable repair halted at gate 3** (binding `d3d5044b`,
authority `e0be22c1`; [report](../planning/retained-callable-repair-halt-report.md),
seal `retained-callable-repair-halt-20260923.json`). One Seed (`41861dd7…`),
no Final. Both members behave as bound on the lambda form (no install
refusal; the retirement wipe covers the transient image's own span), but the
anonymous callable stored by `setq` outlives its transient image:
`(funcall savedlambda)` → `VM: UNDEFINED FUNCTION #FFE` (handle 4094 of a
retired image). New class (c), retained-callable lifetime; possible
wrong-function call after ordinal reuse is untested. Reopening needs a
reviewer decision on scope (callable lifetime/promotion) and on the source
authority already at HEAD; a replacement Seed was not spent.

2026-09-23 **retained-callable family attributed; repair card bound**
(`retained-callable-writer-attribution.md`, seal
`retained-callable-writer-attribution-20260923.json`). Class (a): phase-12
decoder clause compares the decoded handle without the transient +2048 →
every anonymous callable retained in a transient image is refused. Class
(b): `c2_append_rollback_prepare_phase` leaves `code_len` /
`C2AW_CHIP_CODE_BASE` from the last persistent publication, so the
transient-retirement wipe zeroes that live object; N = 1 suffices
(`(dotimes (n 1) (eval '(defun f () 7)))`), one object per form.
**Both classes reproduce on the public 2.3.0 medium** (D81 `d98e6d75…`,
lambda refusal; wipe at N = 1 entry 825 `$C9CC` and N = 54 entry 878
`$CBDE`). Known-issues candidates for the 2.3.0 successor (wording and
publication are an owner word): (1) "A `lambda` stored by a top-level
`setq`/`setf` is refused with `VM: BAD BYTECODE`; the prompt recovers and
nothing already defined is affected." (2) "A `defun` published from inside
a running form (e.g. `eval` inside `dotimes`) is silently destroyed; the
next call fails with `VM: BAD BYTECODE`; earlier definitions are intact.
Workaround: define functions at top level." Repair card bound in the plan
(host-only, 1/1/1 on the anchor Final); reopening of the family after the
repair Final only through its negative gates.

2026-09-23 **retained-callable attribution: explicit corruption halt**, authority
`43448850`; [report](../planning/retained-callable-attribution-halt-report.md),
seal `retained-callable-attribution-halt-20260923.json`. Lambda: phase-12
transient-handle mismatch (4094 versus 2046), first VM error store `$2953`,
804 prior published objects preserved. Capfill: loop returns nil and
publishes handle 878, but its ten bytes at Bank 2 `$CC23` are zero before
use; first VM error store `$5440`. This is a distinct invalid-published-code
class, not a tolerated refused shape. Exact destructive writer unproved.
No further product execution after recognition; 0 builds/links/Seeds/device
contacts. Four probe receipts retained, including the r1 observer failure;
offline report/seal tools assert captured bytes without replaying the product.
Remaining shape matrix, persistence/reset, repair air and budget are deferred
by the halt. Reopening requires reviewer/owner binding for destructive-write
attribution; proposed host-only budget 0/0/0 is not started. Definitions Set B
remains blocked. Existing exact-error successor and identity gates stand.

2026-09-23 **cache remaining gain on accepted anchor: below 15%, parked**.
Authority `a982b117`; [projection report](../planning/anchor-cache-remaining-gain-report.md).
Qualified r6 observes 558.025 / 87.175 record lookups and 928.475 / 143.825
C2D reads per key. Nominal single/batched ratios 0.908946712 / 0.928738814;
saving 302,947 / 47,327 cycles, 7.480 / 1.169 ms per key. Single-key gain
**9.1053%** fails the 15% decision threshold even before the unchanged
sensitivity allowance. No replacement Seed proposed; **128 ordinary text
bytes stay in reserve**. r3 host/native/device evidence stays valid for
r3; no cache Final. Reopening requires reviewer/owner word on a new
qualifying form or decision rule. This measurement consumes no build,
link or Seed. The retained-callable defect's attribution is next in the
plan after the decision on this number; no repair is claimed here.

2026-09-23 **dirty-anchor Final closed**, authority `e9ef6d57`:
[Final report](../planning/dirty-anchor-final-report.md), seal
`dirty-anchor-final-20260923.json`. Fresh sealed full source exit 0 on
`17a12ed3`, immediately followed by one Final; PRG/ELF/LTO/Bank-2 equal
the admitted Seed, existing D81 `05070eb3…` read back. Natural single-key
0.6169468613, batched 0.7119577173. Budget consumed **1/1/1**.
The +318 forced / +325 unforced duplicate-root cost below is carried
unchanged. Physical 17-key/cold-boot batch remains queued. Cache Final
remains deferred until remaining natural-lane gain on this anchor world
is measured; no cache Seed/Final was added here.

2026-09-23 dirty-anchor GC ledger, accepted by `e9ef6d57`: **+318
forced / +325 unforced cycles** are a named live cost of the duplicate
anchor argument root (39 → 40 roots; 501 / 532 marks unchanged). Forced
attribution: +22 `gc_collect` and +79 `gc_mark1` instructions. Canonical
graph, symbols and frozen cells remain equal; collector bytes and addresses
are unchanged. The exact comparator still halts on root-population equality;
no root is removed and no placement tolerance is used. Receipt:
`build/dirty-anchor-card-r1/gc-accepted.json`, preserving `gc-halt.json`.
Final released after usage and a fresh sealed green full source check.

2026-09-23 dirty-anchor usage successor: all 23 native rows pass in both
Put-Kit and the existing anchor Seed. The registered anonymous-callable
case still produces exactly `*** VM: BAD BYTECODE`; the following named
call, saved named call, eval and named call return 8, 8, 12, 8. This preserves
the defect, not a tolerance. Receipts: `build/dirty-anchor-usage-{baseline,candidate}-r1/receipt.json`.
Physical 17-key and cold-boot rows remain in the batched device list.

2026-09-23 `%ide-mini-input` private inline (`build/ide-mini-inline-r2/`,
host suite 158 cases) **rejected** under air > performance: +27 Bank-2
bytes for a mean-unit projection of about 70,386 cycles/key, 2.75 % of r3
IDE service time. Reopening condition: a Bank-2 saving of at least 27 bytes
in the same card, or an owner word that re-weights performance. The earlier
larger-inline and no-gain access experiments stay in their directories.

2026-09-23 cache candidate r3 update: the 20 % rule is met by projection
(0.5436 / 0.7438 half-subtree, `741f7361`), but the Final is deferred to
the dirty-anchor world (plan entry 2026-09-23, anchor card) because the
anchor removes the calls whose lookups the cache serves; remaining cache
gain to be measured there (estimate about 290 k cycles/key, about 9 %).

2026-09-23 native by-catch, second member of the retained-callable family:
the top-level form `(progn (setq savedlambda (lambda () 27)) 19)` prints
`*** VM: BAD BYTECODE` at a live prompt on the accepted Put-Kit world and on
the cache candidate r3 (`build/code-object-cache-usage-baseline-r4/18-screen.txt`,
`…-candidate-r4/18-screen.txt`, identical SHA). Subsequent arithmetic and
eval recover. With the 2026-09-22 `dotimes`/`eval` `capfill` case this is one
family: an anonymous callable retained through a non-`defun` path. Status:
**product defect, not tolerated**; host-only attribution card bound directly
before Definitions Set B (plan entry 2026-09-23). No device reproduction yet.

2026-09-23 code-object cache candidate r3 held pending the Final decision
rule (plan entry 2026-09-23): local source commit `ed617afb`, ordinary text
1,226/32, E000 193/54, capture 183/57, natural lane 0.906255 / 0.916763,
matched GC +0.02666 %. Budget 2/1/1 bound retroactively; Seeds consumed 2,
Final and link unconsumed. Reopening condition: call/render attribution on
both worlds reaches the 20 % per-key rule; otherwise the 128 text bytes
return to the reserve and r3 stays a qualified held world.

2026-09-22 native by-catch on Put-Kit: a capacity-input shortcut using
`(dotimes (n 54) (eval '(defun capfill () 7)))` reaches 63 images and returns
`nil`, but subsequent `(capfill)` reports `VM: BAD BYTECODE` at a live prompt.
The independent direct top-level capacity sequence passes all 61 rows.
See the [device-batch host prefilter report](../planning/put-kit-device-prefilter-report.md)
and its two receipts. No device reproduction or causal attribution is claimed;
carry this executed case into the general retirement boundary investigation.


2026-09-22 current-status overlay: [Project Status](../project-status.md)
records the Put-Kit world and the newly accepted execution order. Historical
rows below keep their original evidence. In particular, Definitions Set A
host-closes the compiler bridge, helper relocation, clean image-capacity error
and atomic grouped publication; persistent retirement stays open. The old
“catalog full” world is superseded by the current 63/64 unique slots. The
physical fallback session already crossed 795 with 803 symbols on September
16; the new-medium batch repeats that boundary. These corrections do not
transfer predecessor device acceptance to the current medium.


Status: **current** — single authoritative list of everything deliberately
set aside. Created by the housekeeping block, 2026-07-29.

Before this register the parked strands lived in six separate documents and
mainly in the heads of the owner and the reviewer. One line per item: what
is parked, why, where its restart package is, and what would reopen it.

Rule: an item leaves this register only by being reopened with an explicit
commission, or by being closed with a receipt. Nothing is removed silently.

**2026-09-18 correction to the historical boot-ledger row below:** its
"almost entirely wait time" explanation was a hypothesis, not a measured
result, and is superseded for the accepted Set-A world by
`docs/planning/boot-ledger-set-a-report.md`. The emulator reproduces
35.50 s equivalent before the initializing call and 11.78 s in INIT/banner,
with exact phase accounting. Stager CRC32 contributes 7.209 s; the product
world's remote reader contributes 9.900 s exclusive, alongside string-record
and intern work. Shared-overlay function attribution remains explicitly
partial. The owner's hardware times remain separate; no F011/SD or DMA
latency conclusion is inferred. Host phase-ledger scope is closed, physical
per-phase timestamps are not supplied. The existing boot-snapshot idea is
still parked, not commissioned by these measurements.

| Item | Why parked | Restart package | What would reopen it |
|---|---|---|---|
| **RESOLVED placement: startup-feedback constant-data capacity halt (2026-09-14)** | The 2.3.0 ordinary `.rodata` is exactly full at 879 bytes, ending at `$B98C`. The first startup-feedback Seed adds the 18-byte native message there and overlaps the fixed verifier owner. All 28 input members compared, only the string pool grows. The preflight checked script identity but omitted the message's data-region price; free ordinary text is not free `.rodata` | Historical `docs/planning/startup-feedback-seed-halt.md`; `build/startup-feedback-r1/halt-attribution.json`; source `b1906952`. Closure: `f5fb2d27`, source `c968ebfd`, `docs/planning/startup-feedback-final-report.md` | Named, sized ALLOC-only data at `$AAC6..$AAD8` in ordinary text; `.rodata` and verifier unchanged. Object projection, old-rodata failure and final scanner controls pass. Final pair/medium byteidentical to replacement Seed, total 2/1/1, text 2,264/32; no BSS/E000/Capture/name change. `.rodata` is permanently priced at every final link and new constants in preflight. The card's physical startup witness remains pending separately |
| **CLOSED: Housekeeping group 2 host/product boundary (2026-09-11)** | Retiring the shelf exposed a FORCE product-link edge through the old Guard/FASL acceptance. Under `01a06b2f`, this host edge now performs only a historical receipt seal/consistency check, not artifact re-acceptance; 15 source bindings and five controls pass. Live banner visual/VM coverage is an explicit independent host edge, with omission control | `37255c67`, `47e9d30a`; `build/housekeeping-20260910/check-host-group2-r2.json` and `.log`; closing group-2 section of `post-2.2.0-plan.md` | Closed under the explicit narrowed claim. Full run: exactly ten expected reds, no unexpected errors, G1 29/29, 7,451 unchanged files. No product build. The five lost artifacts remain separately registered; original artifact acceptance was not replayed |
| **Archived Phase H/U branches (2026-09-10)** | Owner chose archival, not discard, of uncited old strands with non-trivial product diffs | Local `archive/post-2.2.0/phase-h-housekeeping` at `43cfeb94a8cc80c86b8ffd441f767d48ac53b297`; `archive/post-2.2.0/phase-u-upstream` at `04d02a83d4ccd0ccaade74a51d786baad7250593`; verified pre-removal bundle and exact population in the post-2.2.0 plan | Explicit recommission and attribution against the current product; no product work inferred |
| **CLOSED: residual old Comfort seed directory (2026-09-10)** | Owner removed the directory manually; Codex verified path absence and deleted the retained local branch `codex/comfort-stack-seed-r1` | Tip `ee4de944` remains in the verified pre-removal bundle; `build/housekeeping-20260910/comfort-directory-closure.md` supplements the original partial-removal receipt | Closed; no permission changes or remote deletion by Codex, no product defect |
| **`defstruct` and dynamic library freight** | `(defstruct point x y)` escapes control flow into runtime data and executes BRK; the exact PC/return-state corruptor remains open | `docs/planning/c2.2-link75-defstruct-red-frame-owner-decision.md`; 1.6 restart package; P2 and terminal-ingress receipts; IRQ-origin, BRK-stack-forensics, stack-rescue, F018B-coverage and consumed-span result receipts | **ATTRIBUTION CLOSED 2026-08-10; OWNER FIX DISPOSITION REQUIRED.** **P2 DESK CLOSED 2026-08-09** remains authoritative: the **completion-edge append hypothesis is desk-falsified**, and the **current-carrier terminal-ingress ring** supplied the later capture. The active `$E327 → c2_facade_vm_code_load` was pre-submit between `PHA $A1BB` and `PLA $A1CE`. The closing target-owned row then captured every byte of the only two consumed spans: owner 656/window 29 is exact 3/3 and owner 696/window 10 exact 16/16 against same-stop physical C2D/Bank-2 source truth. Staleness is fully refuted for the escape path; defstruct is not a proved F018B-family member and creates no ownership-recharter basis. No further evidence row is permitted. The remaining class is local terminal-ingress control corruption whose exact immediate edge BRK destroyed. Reopening now requires the owner-commissioned structural fix form: stack/return-vector guards at terminal ingress, preserving ordinary control flow and all journal/refill contracts; the guard must prevent execution from escaping into data without claiming the unrecoverable corruptor. |
| **`gc` / `room` / `error` trio (G1) — reopening condition met, awaiting B3 commission** | Cold read carrier measures 1,724 B and adds 512 B of pack quanta; session deficit 399 B. Re-fusing correctness-critical phases for a diagnostic instrument is disproportionate. The 2026-07-31 editor accounting now derives 0.882 collections/key on serial redisplay and 0.248 under ten-key coalescing, so `room` is urgent; urgency does not create capacity | `docs/planning/c2.2-f3-state-error-carrier-contract.md`; first-red receipts `c2.2-v1.2.2-g1-*`; `docs/planning/post-v1.2.5-editor-input-latency-host-attribution.md` | Explicit B3 commission of a smaller `room`-first carrier that leaves rollback/publish/journal phases untouched, or new Session-store headroom |
| **GC envelope cut (G3)** | No dominant term is provable. Measured on hardware: a symbol-value read costs < 20 µs, so all 480 GC reads are ≤ 0.5 of 89 frames. Trace, arena and sweep have no target numbers | `tests/bytecode/dialect-v2/evidence/architecture-blocks/c2.2-v1.2.2-g2-gc-work-attribution-receipt.json`; v1.2.2 measurement rows | Target instrumentation for the remaining phases — which today needs `room`, i.e. G1 |
| **`require` after ordinary persistent appends — mechanism attributed** | The strict active-universe proof treats every source-kind-1 Session row as a package identity. Ordinary `defun` rows are absent from L65INDEX, so the resolver returns `nil` in `%require-world` before media staging. The exact v1.2.4 host matrix is `t` without helper appends and `nil` after `%s`/`%sr`; the original Link-80 observation is explained. The apparent soak “second sighting” is excluded because that harness mounted no package medium | `post-v124-require-prior-append-h1-receipt-20260730.json`; owner table `docs/planning/post-v1.2.4-require-second-sighting-owner-review.md` | Owner chooses: accept geometrically valid non-index user rows, add a package/user row discriminator, or constrain/withdraw the dynamic-loader surface. No fix, link or hardware run is authorized yet; B3 remains closed pending that product-policy decision |
| **Intermittent post-GC out-of-memory** | Observed once in a `while` allocation workload; 1,200 allocations in the follow-up session ran clean. Not reproduced, not explained | Link-77 bundled hardware receipt; fixture retained | A second sighting, or a GC change that touches the same paths |
| **Fail-closed guard black box** | The guard reports nothing when it fires. A capture body in Bank-0 text needs a 3-byte facade vector; the fixed block has 2 | `tests/bytecode/dialect-v2/evidence/architecture-blocks/c2.2-v1.2.2-fail-closed-blackbox-terminal-first-red.json` | Any geometry change freeing three fixed-block bytes — **or** an inline-in-window minimal capture, which needs no vector at all (design note, not authorized) |
| **DELIVERED in v1.6.0: retired-overlay execution-boundary backstop** | Three device instances proved carrier enumeration incomplete. The released boundary catches execution in retired overlay space and sanitizes all seven CSR pairs before recovery; the hardware acceptance returned from `(>= nil 32)` to a usable prompt | Backstop, recovery-sanitization, item-1 candidate and D5 receipts; public publication receipt `v160-public-publication-receipt-20260825.json` | Closed by v1.6.0 publication. Reopen only on a released-world failure of the same boundary; no parked implementation remains |
| **DELIVERED in v1.6.0: verified MAP-CPU boot refill** | The generated boot refill had inherited a silent DMA-success path. The released product routes it through the same CPU/MAP content transport and convergence rule as every mutable reader; final-ELF closure reports zero unsafe content-DMA readers | Boot-refill DMA closure/fix, item-1 candidate and public publication receipts | Closed by v1.6.0 publication. Any new content reader must enter the structural final-ELF closure rather than reopening this row |
| **DELIVERED in v1.6.0: packed-facade media proof** | An ELF-only proof once missed a zeroed facade in the packed PRG. Completion now materializes and byte-compares the delivered facade against ElfTruth before media publication | Shipped-facade repair, item-1 media and public package receipts | Closed by v1.6.0 publication. The permanent rule is that the claim chain ends at the shipped byte |
| **DELIVERED in v1.6.0: hardware-queue single ownership** | The evaluator drain and an armed development capture could both consume the same hardware queue. The selected product's linked readers are classified and the simultaneous-owner edge is structurally absent | Queue-single-owner replacement/current-candidate reproof and item-1 candidate receipts | Closed by v1.6.0 publication. The deferred Comfort row inherits the single-owner gate when capture returns |
| **DELIVERED in v1.6.0: transitive MAP-nesting prohibition** | Two individually safe relocated bodies composed into an unsafe nested MAP lifetime. Every mapped tenant in the released final control-flow graph is now rejected if it can reach another MAP enter/leave | Nested-MAP swap, backstop final gate and item-1 candidate receipts | Closed by v1.6.0 publication. Every future MAP-arena tenant joins the derived graph |
| **C2.3: `restart-repl`** | Out of the C2.2 product surface by contract | Cross-invariant rows E3/E4; `docs/planning/c2.0-address-identity-contract.md` §5 | Commissioning C2.3 |
| **C2.3: freezer during an active definition** | Cutpoints 1–2 proven, cutpoints 3–4 not; documented limitation shipped in the release notes | Cross-invariant row C1; Link-58 cutpoint receipts | Commissioning C2.3 |
| **Attic runtime refill (the C2-full promise)** | Withdrawn when the DMA visibility finding (L10) made runtime Attic reads unsafe in the execution path | The complete C2-full contract set, deliberately not dismantled | An upstream core fix for L10, or a device generation that proves the transport. The 2026-07-30 step is done: L10 re-measured and reproduced on the current core (714 ms), filed upstream 2026-07-31. **Upstream responded 2026-08-25 (issue 670, dansanderson): the documented CPU-stall guarantee is confirmed as intended to cover Enhanced Attic reads — our measured 691/714 ms convergence is therefore a violation of intended behavior, not a documentation gap; a standalone reduced reproducer was requested. Bounded side task after the Comfort acceptance: build the reproducer from the existing L10 instrument (host prep needs no device; verification rides a planned contact) and post it.** **Standing trigger since then (owner realism: upstream is low-activity, no filing is awaited): on every new stable mega65-core release the owner adopts, the L10 curve re-measures with the existing instrument — one session ride. We open our own gate; upstream mail is a bonus. Self-owned workaround paths named 2026-08-10 (owner-approved) — the promise no longer hangs on upstream alone: (1) CPU-side Attic transport via 28-bit addressing, bypassing DMA entirely (a 2-KB window prices at well under 1 ms of CPU copy at 40 MHz — likely cheaper than the measured 714 ms L10 worst case); (2) verified DMA via the era's content-defined convergence discipline (find-first-difference, bounded spin, fail-closed) — trust content, never the completion signal. Successor candidate "C2-full without third parties" queued behind the standing sequence (defstruct closure → fix disposition → startup/require experience block → v1.5): Phase A characterizes L10's exact shape (DMA-only? write-freshness? bounded latency?) with the existing instrument plus CPU-vs-DMA comparison rows, then the priced transport decision** |
| **Upstream filings L4–L11** | **CLOSED 2026-07-31: filed by the owner.** L4–L7 as llvm-mos issues, L10 as a documentation question on `MEGA65/mega65-user-guide` (the authorized surface; core Discussions remain disabled), L11 as a documentation correction on `mega65-core`. L8/L9 stay not-file-ready as optional Codex background (reduction outside lisp65 required) — they are tracked in the bundle, not here | `docs/upstream-owner-bundle-2026-07-27.md` (issue URLs may be appended there when convenient) | Reopened only if an upstream maintainer requests a reproduction — that request returns as a commissioned item. **First upstream fruit 2026-08-10: llvm-mos maintainer (johnwbyrd) accepted the Z=0 ABI documentation request (llvm-mos#581) and proposed the wiki C-calling-convention page; the owner replied same day with agreement and suggested wording, offering to review the wiki text. No action owed; watch for the wiki edit** |
| **Color-RAM scroll (banner color ghost)** | Display-only. Phase R re-priced the current source: 622 B code + 20 B state requires a 1,024-B Session allocation, 911 B beyond the 113-B remainder before catalog/dispatch freight; the four-job prototype also predates the L10 completion contract | `docs/planning/basic65-parity-revalidation-2026-07-30.md`; the 28-bit `$FF80000` mechanics remain hardware-green in `docs/archive/pre-1.0/reference/mega65-hardware-opportunity-audit.md` | A substitutive product-shaped transport that includes content-defined completion and fits without another Session quantum; M2 may change the L10 premise but does not authorize the rider |
| **BASIC 65 parity libraries (circle/line/screen/sound…)** | Revalidated for C2-lite as nine prefixed modules plus an optional façade; no module was implemented. The P1 `m65-hw` pilot has a 2,048-Bank-2-byte, zero-resident/native contract | `docs/planning/basic65-parity-revalidation-2026-07-30.md`; receipt `c2.2-v1.2.4-basic65-parity-revalidation-receipt.json` | The 1.3 ship-builder decision; the revalidation itself is closed |
| **Editor key-56 stall (v1.2.6 block)** | Deterministic on Link 83 device (55 keys ok, key 56 unprocessed 120 s, clean state, RUN/STOP recovers); host-side no regression (byteidentical editor opcodes vs v1.2.5, ASan/UBSan clean; the leaner allocation moves the first collection to ~key 56). Twelve device contacts across four method generations produced no queue/GC/PC read; every loss was setup/classifier, each hardened permanently (cold reset, context asserts by buffer peek, arrival proof, folded expectation table, hang-triggered one-stop) | `c2.2-v1.2.6-editor-jtag-method-review.md` (ten-contact audit, four alternatives); Phase-D desk receipt `c2.3-v1.6-editor-d1-desk-attribution-receipt.json`; renderer improvement (24.025 vs 78 frames/key) ships in v1.3.0; v1.2.6 closed | **Desk attribution reported 2026-08-04, still parked:** the quiet row proves 56/64 persisted with no monitor crossing, but `$E035` is the ordinary `c2_kernal_event_poll` no-event return, not a collector/spin PC; `gc_runs=9` has no pre-key baseline, and virtual submissions have no per-key arrival witness. Thus monitor crossing is not necessary, while the claimed product-stall mechanism is unproved. Reopen on a naturally reproduced stall with hardware arrival plus pre/post GC and caller/stack witness, or a product-side witness that cannot be skipped by partial virtual delivery. **Physical disconfirmation 2026-08-05 (1.6 closing appointment, D1): 64 physical owner-typed keys, 64 buffered, editor healthy — the stall does not reproduce physically; the 56/64 virtual finding attributes toward virtual-input transport loss. The known-issues stall entry is softened accordingly at the next release edit; the row stays parked under its existing reopen condition**. **Doc action done (verified 2026-08-18):** `docs/known-issues.md` carries "Editor transport finding: physical 64/64" with status *no current product-stall claim*; it shipped in v1.4.0 and is still current in v1.5.0. Only the reopen condition remains open. |
| **Tick hook** | The scheduling boundary and abort/coalescing policy are review-ready, but the current recursive VM has no explicit continuation plane. The lower bound is 16 bytes per frame / at least 384 mutable bytes at the observed 24-frame depth, which exceeds every closed resident allowance | `docs/planning/c2.3-v1.4-tick-hook-scheduler-design.md`; `docs/planning/basic65-parity-revalidation-2026-07-30.md`; raster IRQ ownership and `$FF83/$FF84` are delivered substrate | An owner-commissioned continuation-state/stack-ownership block; only after that plane is proved may a yield/resume WPLTO be attempted |
| **1.4 parity pilot + DMA content-convergence freight** | The attributed refill fix (F018B `$D700` submission consumed as content completion; L10 DMA-visibility class, proven second member) does not fit the closed resident geometry in any tried form (947 B per-site, 841 B compact vs 243 B text / 54 B E000); narrowing the protected set would leave proven class members unprotected | `docs/planning/1.4-parity-pilot-work-plan.md` (eight-contact attribution, dispatcher opcode-view witness, host-green convergence fix 8/8+15/15, 13-site sweep, parity-toy sample); receipts `c2.3-v1.4-link90-*`/`link91-*` | The commissioned stack/overlay ownership block delivers a placement in which the convergence primitive fits; Link 91 is the first hardware step after reopening |
| **1.5 stack/overlay ownership block** | Halt 2 red at product scale: the one WPLTO card fails the simultaneous state geometry (BSS +1,089 B, ZP +2 B, `.noinit` drift 1,161 B, overlay-floor drift 1,773 B, far body 1,433 vs 1,499 B) although Phase C is permanently gated green; continuation is a new architecture commission, not a correction in the chosen row | `docs/planning/1.5-stack-overlay-ownership-work-plan.md`; ownership contract `config/c2-stack-overlay-ownership-contract.json`; inventory + pricing receipts; the Phase-C gate stays live in `check-source` | Successors 1.7 and 1.8 were commissioned and reached the final disposition recorded in the next row; this row no longer self-reopens the parity pilot |
| **1.5–1.8 ownership chain / full-map programme (final)** | The narrowly re-authorized second 1.8 card passed compiler, seed link, final product link and both repaired 190/190 section inventories, then stopped at the downstream assembler-leaf ABI closure: `c2_physical_read_converged` and `vm_code_load_converged` lack ABI policies. The owner clause makes a second red of every class terminal; the later driver lookup error is secondary | `docs/planning/1.8-full-map-ownership-work-plan.md`; the original and repair product-card First-Red receipts; `c2.3-v1.8-full-map-phase-c-gate-receipt.json`; the repaired Phase-C gate remains live in `check-source` | Final under the 1.5–1.8 charters: no retry, third repair, Link 91, hardware run or 1.9 placement block. Only a new explicit owner commission, treating ABI-policy closure as a separate programme, may reopen it |
| **1.9 ownership recharter (final)** | Phase A closed the complete acceptance vocabulary (190 sections, 17 ABI policies covering 13 derived callers, 92 driver tokens, 378 mutations); Phase B replayed the exact failure object twice and both 190/190 terminal inventories at zero compile/WPLTO/device cost. The sole card invocation then stopped before WPLTO because inherited host gates redated SHA-bound historical receipts before the vocabulary check consumed them. This is an acceptance-order/harness red, but the charter's any-red edge is explicit and terminal | `docs/planning/1.9-full-map-recharter-final-park.md`; the v1.9 vocabulary and replay receipts; `c2.3-v1.9-full-map-recharter-product-card-first-red.json` | Final under the 1.9 charter: no retry, WPLTO, Link 91 or hardware. A future commission would need new owner grounds and must include immutable receipt reconstruction/order in its pre-card vocabulary; none is implied here |
| **Golden-layout ownership inversion (final, replacement consumed)** | The reviewed golden and its one exact comparison remain green. The original card stopped before WPLTO at the inherited F1 `product_build_id` pin. The owner then authorized exactly one exceptionless replacement: its committed path gate removed `static_gate`, proved zero non-geometric product preconditions and rejected six regressions, but the sole invocation stopped during producer construction because `receipts/defstruct-static-plane-authority.json` was absent. No WPLTO, linked candidate ELF, golden comparison or device action occurred in either card | `docs/planning/golden-layout-inversion-final-park.md`; original `c2.3-golden-layout-inversion-product-card-first-red.json`; terminal replacement `c2.3-golden-layout-inversion-replacement-product-card-final-red.json`; golden SHA `65a13501…7b4f7` | Final and unappealable under owner commit `e4d03191`: its “red of any kind” clause permits no repair, retry, second replacement, Link 91 or device tail. The golden remains banked evidence without a product-geometry claim |
| **`trace`/`untrace` (inspect pair) — DELIVERED in v1.5.0** | **HARDWARE-GREEN 2026-08-10.** The private exact `%function-cell` ABI, persistent named wrapper and journaled installation preserve the original BCODE. On Link 95 the six physical rows passed: require, probe definition, trace, ordered enter/exit with result 5, untrace, and an exact restored call returning 5 without new trace output. The final whole-screen false red was replayed with a latest-form-scoped oracle and zero additional device accesses. This closes the implementation/acceptance item without publishing it. | Link-92 descope authorities `c2.3-v1.12-link92-r5-trace-{host-attribution,fix-library-scope}.json`; successor ABI/link/media authorities; hardware result `c2.3-link95-trace-hardware-result-receipt.json`; `docs/planning/trace-core-abi-work-plan.md` | **CLOSED AND DELIVERED 2026-08-18 (v1.5.0).** The release block the row awaited was the v1.5 freight train: `trace`/`untrace` ship in v1.5.0, documented in the user guide and language reference, and the D-session row passed on the shipped media with exact BCODE restoration. The row carries no open work and stays only as the record of its own closure. |
| **Boot snapshot (pre-published boot image)** | Named successor candidate 2026-08-16 (owner-approved), inspired by Clamiga's precompiled boot FASLs (92 s → 9 s cold start on 68k): instead of decoding and publishing 6 images / 755 entries / 21k reads on every boot, produce the post-LOADING-LIBRARIES state **once at build time**, place it on the medium as a CRC-covered snapshot role, and boot by loading plus verifying it — the decode/publish work leaves the cold path entirely. Newly feasible because the era delivered exactly the prerequisites: delivery-bound CRC truth per span, media-world identity, the media-builder enumeration, and full-span verification | This register row; `docs/planning/startup-require-experience-work-plan.md` (natural home: the experience block's biggest lever); Clamiga reference for the pattern | An owner commission after the v1.5 release train; prices Phase-A-style against the measured boot ledger; sacred publication/journal contracts untouched (the snapshot is a *cache* of published truth, never asubstitute for the journal — invalidation = world-ID mismatch → fall back to the full decode path) |
| **REPL trailing-input error context** | Multi-form input correctly evaluates left to right, but the generic trailing `reader: syntax error` does not say that preceding forms have already run. That is especially confusing after a durable form; line atomicity would be disproportionate and would remove useful Lisp behavior | `docs/user-guide.md` § REPL essentials; the multi-form loop in `src/repl.c`; v1.5 D5 hardware observation `(time (string-ref "abc" 1)))` | A post-v1.5 UX commission with resident-byte pricing for a trailing-input-specific diagnostic, for example `reader: syntax error in trailing input: )`; no line-atomic transaction |
| **v1.7 Comfort freight set** | Deferred intact by owner decision `3c60ab50`: balanced input, history, capture, adaptive hybrid service, `l65>`/composed display ownership and the sealed `(repl)` fault file are one restart package. The clean v1.6 product proves all Comfort and diagnosis-only sections absent; nothing is discarded | `docs/planning/v1.7.0-pre-plan.md`; sealed v1.6 plan and complete Input-Fidelity evidence chain, beginning with the sealed `(repl)` fault file | An explicit v1.7 commission cut from the pre-plan. It starts by reproducing the sealed fault in a diagnostic world, then builds acceptance media from a clean product world; public `key-event` versus armed capture remains an explicit ownership question |
| **DELIVERED in v1.6.0: REPL cursor navigation** | The Bank-2 `read-line` editor ships Cursor Left/Right, `C-b`/`C-f`, `C-a`/`C-e`, backward Delete, `C-d`, insert-in-place and endpoint no-ops from the generated keymap. Hardware acceptance confirmed insertion, navigation parity, endpoints, deletion and continued prompt recovery | Cursor host receipt, item-1 candidate/media/device/D5 receipts and v1.6.0 public publication receipt | Closed by v1.6.0 publication. Further editing-surface work belongs to the v1.7 Comfort/matcher/blink rows |
| **v1.9 native-prompt cursor-control handling and default-editor policy** | A bare `lisp65>` boot uses the minimal C collector. Cursor Left/Right are PETSCII controls there and currently abort the partial line as `reader: invalid token`; `v16core` changes explicit Lisp `(read-line)` calls, not that collector. The v1.8 substrate D-session first made this boundary visible because it correctly loaded zero optional roles | `src/repl.c`; v1.6 item-1 session/result (explicit `(read-line)` after requiring `v16core`); v1.8 substrate v3 session/result; maintained Known Issue | Price two forms separately: (A) recognize known navigation controls as harmless no-ops in the minimal collector; (B) route/default-load the Bank-2 editor, including symbol, service-time and one-drive boot visibility. Also make the bare-boot/no-optional-library surface its own pre-library row group in every future release D-session. No silent promotion from `(read-line)` evidence to prompt evidence |
| **Bound product profile is stale against the v1.5 sources** | `c2-bound-artifact-source-parity-check` reports a real hash drift on `build/post-promotion/v112/compiler/lcc.manifest.json`: the bound Link-95 product profile predates the library-source changes that shipped in v1.5.0, so the (source, bound artifact) pair no longer matches. The emitter was proven **deterministic** (two consecutive emissions agree byte for byte), so this is genuine staleness of the binding, not nondeterminism. Exposed -- not caused -- by the 2.2 housekeeping block: a `check-source` selftest re-emits the carrier, which is also why `check-source` is not idempotent today (an early gate verifies an artifact that a later target in the same run rewrites) | `config/c2-l-full-product-profile.json` (`authority` block); `docs/reference/gate-and-tool-register.md`, "Bound-artifact parity: the fresh-clone question, decided" | A product link cycle that rebinds the profile authority. That is a product act, not housekeeping, so it belongs to the next product card; until it runs, this is the single named entry of the release exception list. The idempotence defect is separable and can be fixed on its own |
| **`make workbench-product` is wedged after the v1.5 release** | The target routes through the frozen v1.5 public driver: with `build/c2.3/v1.5.0-public-selected/candidate-manifest.json` absent it chooses `build`, and `build` refuses with "v1.5 public build is one-shot" because the guard tests `BUILD.exists()` — a directory that the same tool's own `ide-check` preflight already created (it holds only `ide-check/` and `ide-codemod/`). A sibling action of one tool therefore blocks the everyday product target, and with it the product link cycle that every stale product authority needs | `tools/host-lisp/c2_v150_public_product.py` (`BUILD`, `build()`); `mk/workbench.mk:847` | A product card: point the one-shot guard at the output the build itself owns rather than the shared parent, or route the everyday target back to the canonical product builder and leave the frozen public driver to the release path. Prerequisite for the authority-rebind card |
| **Recovery complete-quiescence A upgrade — parked consumer, no work order** | The complete born-derived probe would reduce the sealed empty recovery path from 2 overlays / 6,110 CRC bytes to 0/0. Its integrated card missed the ordinary-text boundary by 10 bytes; the accepted A0 world leaves 66 text bytes but the complete form needs a further 142-byte integrated movement. A0 is closed and remains the product truth | `docs/planning/v1.7.0-recovery-service-time-pricing-report.md`; `docs/planning/v1.7.0-recovery-quiescence-card-report.md`; A First-Red and A0 final receipts; `docs/planning/v1.7.0-pre-plan.md` Block-R closure | Only an independently commissioned ordinary-text reclaim that proves sufficient born-derived contiguous capacity. The complete A form is the pre-registered beneficiary of such a reclaim; this row itself commissions neither reclaim nor upgrade |
| **v1.7 native `INIT.L65` hook — host/product closed, hardware pending** | The native-only form evaluates `(load "init.l65")` at the existing safe banner seam after `setjmp` and before `lisp65>`. The final product costs 10 Bank-2 bytes, shrinks resident text by 43 bytes, adds no names/slots/state, keeps absent init silent and routes load/evaluation errors through native recovery. Scope and Acceptance are green over the frozen pair; the final witness was resumed read-only from ElfTruth/CFG facts. The canonical prompt swap and Comfort remain outside this form | `docs/planning/v1.7.0-init-l65-implementation-report.md`; final card and r4 Resume receipts; `config/c2-v17-init-l65-r4-resume-contract.json`; `docs/planning/v1.7.0-pre-plan.md` Block I authority | Fresh Same-World media and the owner-held Block-I session. The same contact carries the A0 error-to-prompt perception row; no Comfort or prompt-policy freight opens implicitly |
| **Canonical prompt swap with default Comfort startup** | The intended final composition ends in `(repl)`: Comfort owns `lisp65>`, while the native C fallback is visibly marked. That policy depends on an accepted Comfort path and is not part of the native-only INIT block | `docs/planning/extension-libraries-design.md`; sealed Comfort freight and `(repl)` evidence; `docs/planning/v1.7.0-pre-plan.md` | A future explicit Comfort reopen after its recovery-service gate; native INIT implementation alone does not reopen this row |
| **IDE editor service time (same disease, worse)** | The v1.2.6 era measured ~24 frames per key in the IDE editor (after the renderer improvement from 78). The input-fidelity saga proved the mechanism behind such numbers: a synchronous Lisp edit/render path behind the five-deep key-event queue loses keystrokes in steady state whenever service time exceeds typing cadence -- the IDE editor almost certainly shares it, more severely than the REPL line ever did | The service-time pricing (`93fcff1b`): measured ladder, adaptive-hybrid pattern (native scalar drain, bundled edit/render, adaptive batching), the ring as a resident facility whose lifetime could cover IDE sessions, the responsiveness row as the acceptance bar | A v1.7-era candidate: its own pricing round (full-screen render amortizes differently than one line), measured before priced, riding the proven pattern rather than re-researching it |
| **Paren and quote matcher, active in all three editing surfaces (owner request 2026-08-20)** | Visual matching of parentheses and string quotes, automatically active — no opt-in — in the REPL line editor, the Comfort REPL and the IDE editor. Ground is favorable: `lib/sexp-depth.lisp` is already the single shared scanner (parens in strings and after comments handled) and gains the matcher as its third consumer; all three surfaces are Bank-2 Lisp sharing the generated keymap, so zero resident cost is plausible. Constraints bound with the row: (1) the matcher runs on the per-key hot path, so it is priced against the standing **responsiveness row** before implementation — highlight work must not eat the ~29 % service margin (adaptive/idle rendering in scope); (2) "REPL" means the Bank-2 line editor, not the native C fallback, which stays deliberately minimal; (3) any new named helper triggers the standing symbol pricing round (floor 32 at device, bias rule applies) | `lib/sexp-depth.lisp`; the service-time pricing methodology (`93fcff1b`); the single-source keymap; **superseded restart base: the sealed v1.7 Block-3 implementation (three review-green cards, r10 pair, composed-map/MAP-congruence gates) and the `$22` first-Left attribution — a return starts from these cards, not from scratch** | The v1.8 Block-3 return: first the host-side `$22` reproduction over the publication-boundary fixture, then the sealed cards |
| **Blinking cursor in the editing surfaces (owner inquiry 2026-08-20)** | The prerequisites exist as of the input-fidelity work: the owned raster IRQ maintains a frame counter (`C2K_FRAME_LO/HI`, `$FF83/$FF84`), and the fixed `%read-line-loop` has an explicit idle phase (NIL from the non-blocking take) that can consume it — toggle the point attribute every ~30 frames while idle, zero work while typing, no allocation, responsiveness untouched. First pricing question: whether the product's video mode has VIC-III/IV extended attributes enabled, in which case the hardware blink bit makes it a set bit instead of a loop | The capture receipt's equate table; `lib/stdlib-read-line.lisp` idle phase; MEGA65 VIC-IV attribute documentation; **superseded restart base: the sealed v1.7 Block-3 cards (software blink via `%frame-low`/`$FF83`, hardware blink rejected with three named delivery gaps) — a return starts there** | Returns together with the matcher via the v1.8 Block-3 return |
| **Symbol-economy study — commissioned 2026-09-09 (was optional): user-program headroom is an owner currency** | The selected v1.6 product has 105 free slots and 1,413 free name bytes, so the former zero-margin emergency is gone. The useful question remains architectural: public versus private names, directory-only anonymization and the residual cost of an INIT-loaded default library set | The published v1.6 D5 receipt; library manifests; who-calls purge evidence; R1 relocation precedent | Optional v1.7 study after Comfort and INIT are priced. A new projected pressure may promote it; old v1.5/Comfort-world pressure may not |
| **Historical v1.6 refill witness and first-event latch tooling** | The refill trace witness, MAP-arena installer and proposed first-event latch were diagnosis freight. The clean selected product proves them absent; the fault records remain useful evidence, but acceptance no longer carries their bytes | Sealed witness/latch pricing, device captures and clean-product receipts; logical first-red archive in `v160-post-release-housekeeping-receipt.json` | No product reopen. A v1.7 diagnostic world may reuse the tools only under the instrument law; the clean acceptance world must remove them again |
| **Domain discipline for public functions (owner finding 2026-08-28)** | One policy, two observed instances: a public function must reject an argument from a domain it cannot mean. `(car 1)` returns `nil` because `OP_CAR` tests `IS_PTR` only (`src/vm.c:2260`), and `(length "Teststring")` returns 2 because the library walk (`lib/prelude-m1.lisp:145`) reaches `cell_b` of a string object and reinterprets its internals as cons fields — a silent-wrong-answer class, and the field-reinterpretation half can feed nonsense values into later operations and GC traversal. Target semantics: `car`/`cdr` accept cons and `nil` only (`(car nil)` → `nil` stays, it is load-bearing idiom); `length` accepts lists, a string is a type error whose message points at `string-length`. Severity ranking (owner, 2026-08-28): the `length` half is the worse one precisely because it *succeeds* — a returned number teaches the user that `length` is the general length function and `string-length` merely a variant, and the wrong model surfaces far from its cause; an error would have taught nothing false. Its type error should therefore name `string-length`. **Tier 1 (`length` and the other library sequence walks) needs no owner breaking-change word**: the old result was garbage read out of foreign object fields, and no promise can rest on a meaningless value — so it is cheap, cold-path and may land early and independently. **Tier 2 (`car`/`cdr` domain check) needs both** a hot-path measurement and the owner's word. Two costs to price honestly: (1) `OP_CAR`/`OP_CDR` are the VM's hottest opcodes, so a `cell_type` check is measured against the responsiveness wall before it is chosen — library-level guards are cheap and can land first (cold tier first); (2) `(car 1)` → `nil` is shipped, documented behavior since v1.3, so the change is a breaking change and belongs in release notes by owner word | `src/vm.c` OP_CAR/OP_CDR; `lib/prelude-m1.lisp` `length`/`%length-from`; the standing responsiveness wall and measured-codegen rule | A bounded next-cycle block. Owner expectation (2026-08-28): these two are samples, not the population — so step one is a **mechanical audit of the whole executed public surface**, not a per-function hunt. Build a matrix of every public function (the 139-record public metadata index is the population authority) against representative out-of-domain arguments (number, string, symbol, `nil`, list, function) and classify each observed outcome as *error raised* / *documented-permissive* / *silently wrong*. It must run **profile-faithful** — against the product primitive table, never the host VM's independent implementations (the CALLPRIM-12 lesson). Zero product bytes. The classified matrix then becomes a **permanent contract table** under enforce-what-you-record: no later change may flip a cell silently, and every new public symbol ships its domain row. Only the silently-wrong class is freight; it is fixed in the tiers above, priced, with the breaking half decided by the owner |
| **Long input line legibility (owner finding 2026-08-28) — COMMISSIONED 2026-09-07 as the native-prompt line-wrap card** | Once a line scrolls past the screen edge the typist cannot track what was typed or where the cursor is; this made a bound acceptance row impossible for a human to execute correctly. Candidates: wrapping instead of horizontal scroll, or a position/length indicator | The v1.6 cursor card's viewport model (cursor-following window, narrow repaint edge); the redesigned six-short-lines acceptance row | An editing-wave candidate; prices against the per-key service time like every editor change |
| **Definition-granular workflow: `(show 'name)` / `(edit 'name)`** (owner idea 2026-07-17; **recovered by the 2026-08-28 audit follow-up — it had never been registered**, living only in `docs/planning/extension-libraries-design.md` and the v1.2 scope memo) | `(edit 'hello-world)` opens a narrow buffer holding just that definition; saving splices it back into its source file and re-evaluates it. Because definitions exist only as bytecode after the single-engine cut, this is the **file-indexed** variant of SEdit, not structure editing. Architecture already worked out: a definition-location registry (name → file + form position) written by `load` and carried as an extra column of the shelf metadata index that already feeds `who-calls`; the SEXP scanner bounds the top-level form; write-back over the existing COW save path. **Drift honesty mandatory** (verify the recorded position really holds `(defun <name> …)`, else re-scan or fail closed — never splice blind) and **dual-commit order defined** (file COW first, then re-eval; on compile failure the file is written, the session keeps the old definition, and the user is told). Staged: **stage 1 `(show 'name)`** is display-only — registry plus scanner, no splice-back, no drift-splice risk, immediately useful and it pays for the registry; **stage 2 `(edit 'name)`** adds the narrow buffer and write-back on that proven foundation. Three dividends raise its priority: (1) it *mitigates* the IDE service-time debt instead of paying it — 10-50-line buffers move the common case onto a structurally cheap path; (2) syntax highlighting returns honestly tiered (full-file buffers stay uncolored, definition buffers get it — a capability bound to buffer size); (3) it is the IDE's **fallback line**: REPL plus show/edit-definition is a complete workflow that needs large undo, full-text search and smooth large-file scrolling far less, because the unit of work is small. Platform-native framing: definition-granular work is the 8-bit interaction grammar (`LIST 100-200`), with names instead of line numbers as the address space | `docs/planning/extension-libraries-design.md` (concept, both addenda, staging and guardrails); `docs/planning/v1.2-scope-memo.md`; the delivered SEXP scanner (`lib/sexp-depth.lisp`), the shelf metadata index behind `who-calls`, and the COW save path | A 2.x-era candidate and the natural companion of any IDE service-time work — **stage 1 must be compared against renderer optimization before pillar 3 of v2.0 is priced**, since avoiding the expensive path may beat speeding it up |
| **Auto-closing delimiters (owner request 2026-08-28)** | Typing `(` or `"` inserts the closing partner and places the cursor between the pair; requested by the owner as the matcher's editing sibling. Distinct from the visual matcher: this *writes into the buffer*, so it is editor semantics, not paint — the pricing must resolve its interaction with insertion/deletion, with the Comfort over-close rejection rule, and with typing an explicit closer over an auto-inserted one (skip-over vs. duplicate). Expected to be toggleable; the off state must cost nothing on the key path | The sealed Block-3 scanner/editor cards; the v1.6 cursor card's insertion model (`%rl-put` splice); the Comfort over-close rule evidence | An editing-wave candidate behind the v1.8 Block-3 return: own pricing round (buffer semantics + symbols + service time), never folded silently into the visual matcher return |
| **Boot-phase timing ledger (owner observation 2026-09-02)** | Under Xemu the REPL boots almost instantly; on the device the same boot takes close to a minute (36 s at v1.5, grown since). Xemu emulates the CPU at nominal speed and syncs to 50 Hz, so compute-bound phases should cost similar wall time — the gap is therefore almost entirely **wait time**, in exactly the classes the DWX blind-spot contract keeps device-mandatory: SD/F011 sector latency, HyperRAM wait states on Attic/Bank-5 reads through MAP (the prime suspect — boot CRC/decode loops walk library content byte by byte, and that content lives in HyperRAM on the device and in plain RAM in Xemu), and DMA/completion timing. This reframes the parked boot-snapshot idea: caching decoded state only helps if decoding is the cost; if sector reads and HyperRAM access dominate, the levers are fewer and larger reads, boot-loop-friendly library layout, or a more compact boot image | The existing frame counter `$FF83/$FF84` (armed from the raster IRQ) as the timestamp source; the audit of 2026-09-05 (S12: ledger has no phase split; S4: 346,298 shelf reads in LOADING LIBRARIES) as the hypothesis list to apportion; the v1.5 36-s boot baseline; the DWX prefilter as the zero-wait reference | A measurement card, host and device: frame-counter timestamps at every boot phase boundary on both worlds, the per-phase delta apportions the minute and names which phases grew since v1.5. Pillar-3 boot work prices only against that ledger, never against the snapshot assumption |
| **Typing-latency polish (owner observation 2026-09-02)** | Typing has always trailed slightly and Backspace can feel laggy — independent of the post-1.9 regressions, present in the hardware-green v1.9 path itself. Three named cost sources: (1) the serial per-key chain (~0.77 frames event→heap→splice→render before the echo); (2) Backspace repaints the line remainder as a list walk with per-cell VM writes — the cheaper form is a screen blit (shift cells left, clear one) instead of re-rendering from the list; (3) the periodic GC hitch: ~4 heap cells per key, 192-cell nursery, a ~88-frame collection every ~48 keys — the capture ring removed the *loss*, not the *pause*; the sealed hybrid scalar-drain design (consume events without heap cells) is the standing lever. Measure-first is mandatory: the new native-cycles-per-key lane apportions the three shares before anything is built | The v1.6 cursor card allocation model; the sealed hybrid/adaptive pricing (0.768 f/c); the two-lane responsiveness authority plus the commissioned native-cycles lane | A 2.x candidate after DWX: one measurement card over the delivered world, then priced levers in measured order |
| **Code review 2026-09-03 — correctness sweep (block 2.6 candidate)** | Product defects found by the project-wide review, each small and host-provable: unchecked `sidx()` for `setq`/`set-symbol-function`/`%set-macro` on non-symbols (OOB writes into Bank-0 tables, `src/symbol.c:195`, `src/eval.c:1673`); F011 read layer with no error evaluation and an always-true `io_disk_read_sector` (`src/io.c:68-120`); silent mark-stack overflow in iterative `gc_mark` (`src/mem.c:445-456`); `&rest` fill past the frame guard (`src/vm.c:1909`); `%disk-poke`/POP-underflow continuing with NIL operands; unchecked `SLOT(n)` and no `pc<payload_len`; non-volatile spin-up loop (`src/io.c:77`); `%lcc-tail-if` rel8 hole unchecked (`lib/lcc.lisp:663`); silent `nil` for cons-but-not-lambda operators (`lib/lcc.lisp:536`); `%case-key-test` relying on permissive `car` (`lib/prelude-m1.lisp:55` — prerequisite of the tier-2 return); `find`/`member`/`assoc` defined twice in one chain; minibuffer cursor offset by the painted `M-x` prefix (`lib/ide-ui.lisp:855` vs `:999` — verify on device); six-to-eight hand-written F018/EDMA descriptor builders whose own comments warn about the `"memory"` clobber (one `static inline` seam, `src/mem.c:230` et al.); `io_attic_load_lib` declared with two signatures (`src/io.h:41` vs `src/io.c:657`) | `docs/planning/2026-09-03-project-code-review.md` sections A and B; reviewer verification marks | A bounded block after DWX: one card per family, mutation each, zero device contacts; `%case-key-test` before any tier-2 attempt |
| **Code review 2026-09-03 — documentation truth and bundle-docs gate (2.0.1 candidate)** | The shipped 2.0.0 bundle's `docs/user-guide.md` says "lisp65 1.9.0" and points at `lisp65-1.9.0/`; README, project-status, language-reference, known-issues and docs/README all still say 1.9.0; README lacks 1.8.0/2.0.0 note links. The language reference declares `do`, `remainder`, `logand/logior/logxor/ash`, `string->list`/`list->string` absent though they exist; 40 delivered public names are undocumented (`setf`, `push`, `pop`, `incf`, `decf`, `defvar`, `defparameter`, `max`, `min`, `abs`, …); the guide's Buffers chapter loads a library not on the medium; the tier-1 behavior change and the `car`/`cdr` permissiveness appear nowhere but the release notes; several counts drift (error codes 60/43→63/44, arity 101/34→103/36, examples four→five, counters 136→138, D5). The Halt-B check did not cover bundled docs | `docs/planning/2026-09-03-project-code-review.md` section D2/D3; `docs-drift-audit.md` in the review evidence directory | A 2.0.1 docs fix plus a permanent Halt-B gate: bundled docs carry the release version, and the documented public surface is checked mechanically against the public metadata index (the domain-audit pattern) |
| **Code review 2026-09-03 — build integrity** | `workbench-product*` verifies existing artifacts instead of building when the candidate manifest exists (`mk/workbench.mk:850-896`): after a source change it prints FULL PASS for old bytes; six parallel product-build scripts and seven authority JSONs; three documents name three different "current" build commands; parse-time shell in every `make` with silent empty seal ids outside git; toolchain verification not on the product path; absolute user paths in tracked config; `/tmp` logs; a make target writing receipts into the tracked tree | `docs/planning/2026-09-03-project-code-review.md` section D1, D4-D7, D9-D10 (config: 36 hand-copied `bab9ec3a…` media hashes without a deriving authority, two corpse files, ten archive candidates; default `make` builds the legacy treewalk `.prg`, no `make help`); `build-audit.md`, `config-audit.md` | With block 2.6: source-signature or explicit build/verify split, `check-product` depending on toolchain verify, one parametrized product script, `development.md` as the single build authority with a clone→doctor→build→D81→deploy walkthrough |
| **Code review 2026-09-03 — host tool layer refactor** | 1,747 files as an append-only archive: card boilerplate copied ~1,000× (`require` 1,260 files/359 variants, `bind` 1,052, `load` 859, `canonical` 611, `run` 220/148 variants); pins against the house rule (`0xC356` in 95 files vs 5 derived callers, one card monkeypatching the derivation); `date.today()` in 163 receipt writers vs 5 `stable_recorded_on()` callers; ~405 unreachable files (~100k lines); `c2_product_substitution_link.py` at 9,244 lines with 49 globals imported under 7 aliases; the release card transitively loads 508 modules via `PREV.PREV…` constant chains | `docs/planning/2026-09-03-project-code-review.md` section C; `tools-review.md`, `unreachable-tools.txt` | Its own block after DWX, zero product bytes: `card_base.py` mandatory for new cards (lint gate), `stable_recorded_on` mandatory, pin sweep over check-source-reachable files, then attic after import de-tangling, `LinkConfig` last |
| **Code review 2026-09-03 — library hygiene and provenance** | `lib/` is no longer the built truth (eight codemod-copied files); dead resident `%compile-slot-*`/`%c1-compile*`; five byte-identical directory walks; two error strategies (`(mod 1 0)` vs undefined `%…-error-*`); two parallel `trace` pairs; a v1.3 who-calls index; ~12 duplicated tiny helpers costing slots; `compile-buffer-to-lib` fasl-slot gating contradicting the guide. Provenance: `THIRD-PARTY-NOTICES.md` lacks mega65-tools and Xemu (two tracked patches without upstream commit/licence headers), cc65 spike binaries tracked | `docs/planning/2026-09-03-project-code-review.md` sections B4-B13, D8 | Ride the next library card (tier 2 / Comfort media) for the hygiene items; provenance is a small standalone fix any time |
| **House style codification and targeted idiom review (owner-agreed 2026-09-03)** | Agreed after the 2026-09-03 project-wide review: a broad style/efficiency pass is not worth it — efficiency on this platform is measured, never read (codegen shape, LTO folding, MAP reads per step), and a second backlog before the first is worked off would be backlog on backlog. Two targeted forms instead, **after block 2.6 and the tool-layer refactor** (both move the style baseline): (1) a **house style document** per language, codifying what the gates and plans already learned — C: declared-width state cells, one DMA-descriptor seam, no bare `$ff8x` literals, fail-closed instead of returning after an abort; Lisp: one error strategy, helper naming, the 255-byte split pattern, `consp` over reliance on permissive `car`; Python: `card_base`, `stable_recorded_on`, derived addresses — with lint gates where cheap; (2) a **deep idiom review of three places only**: `lib/lcc.lisp` (the compiler, where idiomatic clarity pays most and the worst Lisp finding lived), the `#ifdef` feature matrix in `src/eval.c`/`src/vm.c` (preparation for its consolidation, which is product bytes and a block of its own), and the editor library — the latter with the DWX cycle profile in hand, so efficiency remarks are measurements | `docs/planning/2026-09-03-project-code-review.md`; the gate-and-tool register (the rule corpus to codify); the DWX cycle probe | After 2.6 and the tool-layer refactor close; the house-style document first (cheap), the three-place review second |
| **A7 — `pc < payload_len` before fetch (deferred from block 2.6, 2026-09-04)** | A code object without a terminal `RET` runs into stale `vm_codebuf` bytes (streaming: foreign streamed bytes) silently (`src/vm.c:2121-2203`). The direct per-fetch guard was priced in all three lanes on the card-3 successor: batch 26.178 % margin green, but single keystroke **1.022461× against the 1.02× wall — red**; bytes were not the wall (340 text reserve). The wall is held on principle: typing latency is a registered user complaint and per-fetch costs compound. Mitigations already shipped or in flight: F011 reads now fail closed (card 2), code objects come from our own compiler which always emits a terminal `RET`, `%lcc-tail-if` rel8 is fixed in card 4. Residual exposure: a compiler defect or a corrupted library object — documented as a known limitation | `docs/planning/2.6-card3-vm-a7-pricing-report.md`; `block-2.6-card3-vm-a7-pricing.json` | A **sentinel format card** (≥ 792 Bank-2 bytes): every code object carries a terminal sentinel checked once at load, no hot-path cost; touches `lcc.lisp`, the Python reference compiler and the FASL emitter as a format version. Freight for a 2.x cycle, not a correctness sweep |
| **A15 string-builder latch (deferred from Block 2.6 Card 6, 2026-09-04)** | The low-severity latch correctly rejects a closed/superseded string handle and prevents a stale `str_close` from clearing the active builder, but Whole-Program LTO folds the changed close into three sites in E000-resident `c2_stream_name_value`: **833 → 855 bytes**. E000 then has 45 against its 54-byte floor and only 35 against the 57-byte capture watch. All 25 E000 functions remain post-boot reachable; Bank-2 placement would make the owner's Shelf read MAP-in-MAP; ordinary text, Island and the host facade provide no legal free seam. Low-severity hardening does not consume the arena in which input fidelity already died | `docs/planning/2.6-card6-small-hardening-e000-pricing-report.md`; `block-2.6-card6-small-hardening-e000-pricing.json`; frozen first-red receipt | An essentially free **≥22-byte E000 reclaim** with a named dead/relocatable owner, or a legal non-nesting cold/facade placement. Until then Card 6 omits only this latch; A10–A14 and the remaining A15 hardening stay |
| **Line-editor word motion and `C-k` kill-to-end** | Explicitly excluded from the v1.6 cursor-navigation commission ("Word motion and `C-k` remain outside this card, exactly as commissioned") and never parked since — recovered by the 2026-08-28 lost-feature audit | The accepted v1.6 cursor card (`docs/planning/v1.6.0-repl-cursor-navigation-report.md`): sentinel-chain editor, generated keymap block, allocation model; bare `C-k` (code 11) verified free in the keymap audit | A small editing-polish candidate once an editing wave reopens; same pricing walls as the cursor card (keymap single source, 255-byte objects, no resident state) |
| **v1.6 items 3/4 heritage: Attic-write boundary and startup levers** | Deferred whole by the "Posten 1 allein" descope (2026-08-24); carried only in v1.7 pre-plan block 6, which closes with v1.7 — re-registered here by the 2026-08-28 audit so the closing plan does not take them along. They carry no inherited delivery promise | `docs/planning/v1.6.0-freight-work-plan.md` items 3/4; the startup/require-experience pricing era; the Attic read/refill row above holds the *read* half — this row is the *write*-boundary and startup-lever half | An owner-weighted v1.8+ block after current geometry and value are re-established; the C2-full row's transport decision naturally precedes the write boundary |
| **Sealed `$8040` mid-instruction cycle file** | Unresolved diagnostic-world observation from the input-fidelity era; core-witness pricing was closed by the owner premise (no core debugging). Sealed, but previously carried only in narrative plans — row added by the 2026-08-28 audit | The sealed capture and attribution in the v1.6 freight plan's input-fidelity chapters; diagnostic-world artifact-candidate classification | Only a diagnostic world under the instrument law, or an upstream/core-generation change that makes the question testable within owner limits |
| **Standalone Ship RUN/STOP `$91` seam** | Ship still polls the historical KERNAL STKEY byte `$91`; the MEGA65 KERNAL contract for that byte has not been verified and may be wrong.  This did not cause the interactive sample silence: the sample was blocked earlier on an unarmed jiffy | `docs/planning/1.3-link84-closing-first-red-review.md` (host/ELF attribution and jiffy split) | A separate target capture or ROM-contract reading that names the MEGA65 RUN/STOP source; never folded into the time-base fix |
| **Legacy stdlib suite drift / red `check-host` — CLOSED with receipt 2026-09-05** | Seven of thirteen legacy suites under `tests/bytecode/stdlib/` failed from five causes (pinned `functions` list, the v1.2.6 renderer split, the v1.7 sticky-depth contract, a dead candidate's headroom claim, and a dialect-v1 shadow of the dialect-v2 Workbench surface); all sat in `check-host`, never in `check-source` | `docs/planning/2026-09-05-gate-drift-card-report.md` (one decision line per check, coverage named for every retired check); sealed audit under `tests/bytecode/dialect-v2/evidence/reviews/2026-09-05-performance-audit/` | Record corrected 2026-10-04 (see the dated entry at the top: mandatory run green with 12 suites and 1,707 cases on 2026-09-29). Closed for the commissioned scope (`bytecode-p0-stdlib-check` green, 12 suites, 1704 cases); `check-host` itself stays red on 20 further pre-existing gates — see the next row. Standing rule: `check-host` is on the Before-Ship owner checklist; the Workbench template suite is excluded from the standalone dialect-v1 run by derivation from `config/v2-workbench-artifact-closure.json` |
| **Performance audit 2026-09-05 — contract-bound findings (default not pursued)** | S10 unconditional restage (cold-boot choreography wants fresh truth), S9 source-then-destination CRC16 of the boot overlay, S6 validate-before-mutate export publication, I3 `(load)` pass-1 length as stream terminator, I5 M65D header re-read per data sector (R3 design), I6 pair RMW (Bytecode ABI §4a frozen), L7b `nthcdr` tail validation (Tier-1 product transformation), direct DMA from the F011 sector buffer. Each is a documented safety structure whose removal would change a guarantee, not a redundancy | `tests/bytecode/dialect-v2/evidence/reviews/2026-09-05-performance-audit/audit-rev2c.md` sections 3–6 | Owner decision per item with an equivalent proof named first; never a side effect of an optimization card |
| **Performance audit 2026-09-05 — optimization candidates (measure first)** | Transport granularity at four single-byte DMA sites (I1 sector read, I2 RMW fill + readback compare, I10 session emitter, S8 freelist build; one 16-byte Bank-0 block pattern), `string_record` O(n²) pool walk (S5), bulk shelf reads for LOADING LIBRARIES (S4), editor-open double read (I7), per-CALL directory cache (R2), native CRC16 for `require` (I9, measured 62 % of a repeat), editor L1/L2, GC bitmap sweep (R4). The audit's central thesis (per-byte transport dominates device wall time) is a hypothesis until the boot-phase ledger measures it | Disposition item 3 in `v2.0.0-pre-plan.md`; current floors text 196/32, BSS 181/202 | Only after the boot-phase measurement card; one product-byte card per item, priced against the phase ledger and the two-lane responsiveness wall; a card whose gain the ledger cannot see is not built |
| **Derived call-closure guard for the resident legacy suites (from the gate-drift card, 2026-09-05)** | The suite runner's `dependency_gate` proves every `CALL`/`TAILCALL` target statically, but the resident suites would need a pinned `allowed_external_calls` list of the 29 renderer helpers that the IDE library delivers — a new source-text pin. The affordable form derives the allowed externals from `allow_omitted_defuns`. `bytecode_p0_stdlib.py` is SHA-bound in product receipts (`config/v2-runtime-core-proof.json`, the source-parity contract), so the change is a tool-layer card with a parity rebind, not a docs card | `tools/host-lisp/bytecode_p0_stdlib.py` `_validate_dependency_expectations`; the gate-drift card report | The tool-layer refactor strand (`card_base.py`) picks it up; until then the recurrence guard is the Before-Ship `check-host` run |
| **`config/dialect-profile-selection.json` reads as stale (observed 2026-09-05)** | The file names `dialect-v1` as `active_profile` and `dialect-v2` as `planning` with promotion `not-requested`, while every product suite carries `abi_profile: dialect-v2` and v2.0 shipped as Dialect V2. `dialect_ship_guard.py` refuses to ship the staging profile without a passed-G5 authorization bound there, so the field is a promotion gate, not a description — but a reader will misread it | `tools/host-lisp/dialect_ship_guard.py`, `tools/host-lisp/dialect_migration_contract.py`, the `dialect-contract-check` gate (green) | Codex states the intended meaning in the file's own words or binds the promotion the v2.0 release implies; owner decision if a G5 authorization is what is missing |
| **Residual `check-host` inventory — CLOSED 2026-09-11 (housekeeping groups 1–4, `648b9aea`): zero tolerated historical reds, `check-source` without red; only the two named product-defect reds remain (Mini8 IDE minibuffer display, Ship interactive sample), each with its closing card; population 19 → 13 → 10 → 5 → 0; historical gate-drift population and dispositions retained below** | The full `make -k check-host` after the gate-drift card shows 20 further red targets, every one reproduced red on a clean HEAD without the card's changes: `consp` unknown to the MVP prelude/eval oracles (block 2.6 `%case-key-test`), duplicate `not` between resident and IDE lib suites, m65d lib drift, a second dialect-v1 Workbench-template run in `mk/workbench.mk`, ship-fleet `dependency_gate` against the v1.7 scanner omissions, library shelf beyond the u16 catalog, the chain-walker inventory expecting the pre-F011-repair stager guard, capacity/number-to-string/prelude-evidence receipts, string-codec and private-inline pins, pre-split IDE reports, a wave-3 dry variant; `runtime-overlay-transport-smoke` (seven failures reproduced on the unmodified renderer world, found by card 2a); `c2-while-check` rewrites its tracked receipt on check and rebuilds the while carrier from the live `lcc.lisp`, after which the `check-source` gate `c2-v110-persistent-performance-check` is red (correction 2026-09-10: the constant `EXPECTED_CARRIER_SHA` no longer exists, `01326d32` replaced it with `expected_carrier_binding()` derived from the four-view receipt; the real red is that a forensic Link-82 carrier is compared with a file `c2-while-check` rebuilds from live `lib/lcc.lisp` on every run; era-binding the sealed snapshot path clears both the `check-host` and the tolerated `check-source` red) — a block-2.6 card-4 follow-up | `docs/planning/2026-09-05-gate-drift-card-report.md`, section "Residual `check-host` red inventory"; logs in the card's scratchpad | Current ten targets are named in the group-2 closing section of `docs/planning/post-2.2.0-plan.md`, with full-run evidence `build/housekeeping-20260910/check-host-group2-r2.json`. Historical disposition per gate: repair (the `consp` oracles and the F011 chain-walker guard are real follow-ups of block 2.6 and the F011 repair), re-record (living receipts), or leave `check-host`; until then `check-host` is not a green gate and `check-source` remains the closing protocol |
| **Standing rule (owner word 2026-09-11): a red gate may be tolerated only with an attribution that it hides no live claim; the tolerated list is a debt account with target zero by the next release** | This cycle's housekeeping found that tolerated "historical" reds had hidden live checks three times (banner VM hid the visual check; Mini8 hid the IDE minibuffer defect; the Ship fleet hid the unbuildable interactive sample); two of those defects shipped in 2.2.0 | `docs/planning/post-2.2.0-plan.md` (housekeeping groups 1–3, Mini8, Ship) | Every tolerated entry names (1) its attribution, (2) the proof that no downstream target or claim runs only behind it (its dependents executed with the red target bypassed), (3) a closing card; a product-defect red is never on the tolerated list but on the defect list; the Before-Ship checklist of the next release requires zero tolerated `check-host` targets, or each remaining one carries an owner word |
| **Unrun sealed suite: `p0-repl-comfort.json` is red on today's tree (`function not in directory: %rl-poll`) and no Make target runs it (found 2026-09-11, Comfort prep)** | Twelve old card tools reference it; no gate notices its red. A sealed suite that nothing executes is the same blind spot as a tolerated red, one step further out; `lib/stdlib-read-line.lisp` is not the product editor (the product uses `stdlib-read-line-native.lisp`), which is why `%rl-poll` is absent | `docs/planning/comfort-handover-prep.md` §by-catch | Comfort card rebases the suite onto the 2.2.0 resident and wires it into the host gate; the assumption inventory adds a census of sealed suites and receipts that no target executes |
| **CLOSED: live banner VM profile and visual oracle (2026-09-11)** | Missing F011 profile define caused the harness failure; afterward the visual expectation used 1.4.0 instead of the delivered `WORKBENCH 2.0.0`. First differing write is now diagnosed; expected text comes from the SHA-bound delivered banner source, never the observed writes | `42516051`, `82be1cc3`, `ee759d5d`, `47e9d30a`; full group-2 r2 log: native C-VM codebuf 56, row 9; missing-F011 mutation rejected; visual 228 writes, 9,277 steps, eleven controls | Closed, with explicit live `check-host` coverage preserved independently of the narrowed historical FASL seal. No product rendering defect claimed |
| **CLOSED: retired Attic library shelf prerequisites (2026-09-11)** | The obsolete shelf is no longer a prerequisite of the live buffer or guard paths, nor a product-readiness file test. Its explicit targets verify the archived v1.1 world, not live v2 libraries. Earlier shorthand that both dependents executed was corrected: buffer passed; the exposed guard product-link edge instead required the separately authorized historical seal conversion | `07c30a75`; `build/housekeeping-20260910/attic-era-conversion-final.log` (65,090 bytes, five libraries, seven C negative cases, eight era controls); full group-2 r2 log | Closed as retirement/era-binding, no catalog expansion or product bytes. Removes two members of the tolerated host population; historical shelf claim stays confined to v1.1 |
| **Lost historical build artifacts: five bound artifacts of the guard/FASL acceptance at `b4b14208` (including its original ELF) exist in no loose file and none of 195 archives (found 2026-09-10)** | All sources match `b4b14208`, but the receipt's artifact SHAs cannot be re-derived: today's path holds different bytes. The acceptance they certified was a real device/host acceptance of its era; it is no longer artifact-reproducible | `15abcc4b` (Codex report) | The era-bound target becomes a **receipt seal and consistency check** (sources at the era commit, internal SHA consistency of the receipt, no artifact re-acceptance) and says so in its name and claim; the five artifacts are recorded as lost here. If the owner holds an archive of that era, the artifact check can be restored |
| **PRODUCT DEFECT — hardware-stack cliff at Lisp call depth (measured 2026-09-06, v2.0.1)** | `OP_CALL` re-enters the VM natively (`vm_run_dir` → `vm_run_inner`, `src/vm.c`), so every non-tail Lisp call nests native frames on the 256-byte 6502 hardware stack: measured 12 bytes per recursion level; the published v2.0.1 wraps the stack at **n = 13** non-tail levels at the native prompt and falls into the repeated `E29` loop (Comfort today: n = 9). The wrap silently overwrites the oldest page-1 frames; there is no hardware-SP guard (`LISP65_STACK_GUARD` checks only the soft stack). Found by the Comfort device session's E29 host attribution | `docs/planning/2026-09-05-comfort-perf-e29-host-attribution.md`; `build/v2.1/comfort-buffered-repair-device-r1/stack-repair-pricing-r1/recursion-depth-report.md` (restart package); the stack-watermark lane bound there | Three strands, in order: (1) **hardware-stack floor at VM re-entry** as a v2.1 hardening card — converts the silent wrap into a clean abort, ships with a Known-Issue line (owner word for the public text); (2) Comfort trampoline (Comfort's own repair); (3) **VM iterative CALL** (VM frames on the soft stack instead of native recursion) as an owner-commissioned architecture block — the only form that removes the cliff; priced against both responsiveness lanes before commission. Measured 2026-09-06 (Codex): the **printer** reaches the cliff at 23-deep list nesting (native recursion); the reader rejects depth 32 cleanly with proven recovery (the model for the floor); `mapcar` and `append` at lengths 20/50 are correct with minimum SP 33 and 100/99; `format` is not on the release medium. So the floor card guards **both** sites — VM re-entry and printer recursion — through one shared hardware-SP floor helper, priced against both responsiveness lanes; everyday stdlib is not on the cliff, which keeps this a Known Issue rather than a 2.1 blocker. Under Comfort (2026-09-06, twelve bound runs): `mapcar` 20/50 wraps **while compiling the test form**, the precompiled body runs at minimum SP 64/63 and `append` at 52/51 — the deepest consumer is the compiler suffix invoked under Comfort's live frames, so compiling at base depth (the trampoline) is Comfort's root repair, not a library defect |

| **PRODUCT DEFECT — L65E renderer long-branch target (attributed 2026-09-06)** | The frozen product's `F3 3F 01` at `$C35A` reaches `$C49B`, one byte before `.Lerr_context`. The same complete failing path is byteidentical in the published v2.0.1 ELF (`96ba6709…`), not introduced by the Comfort trampoline. RAM-only execution of the unchanged renderer with a null context executes unintended `ASL $A9` (`$55 → $AA`) and returns success 0 instead of context error 1. PC+2 semantics are executed in the diagnostic Xemu and cross-checked against the pinned `03b24c6b…` core source; no device reproduction or RTL simulation is claimed | `build/v2.1/comfort-buffered-repair-device-r1/stack-repair-pricing-r1/renderer-attribution-and-pricing-halt.md`; matching JSON and `renderer-branch-attribution-r1/receipt.json` bind raw traces, product/release identities and exact path bytes | Separate core-product finding, **not Comfort freight**. More than error text: unintended write and wrong status. It blocks the current complete error-path closure/reserve certificate; the ordinary valid stack-error route has not been shown to take this null-context branch. Assembler/linker-stage origin remains open. The one pricing round is **HALTED** with closure, derived reserve, combined responsiveness and final carrier/admission debts; no renderer fix, second approach, product build or contact authorized by this registration |
| **Comfort (v1.7 freight set) — third descope, 2026-09-06, from v2.1** | The combined stack card could not fit Comfort's native hand-over: the byte program (trampoline through the existing REPL loop ≤ 80, `%repl-enter` ≤ 60 without a new prim id, one shared floor helper ≤ 12 per checkpoint) was missed at every native owner; replacement seed +970 ordinary text, 663 bytes over the mapped-facade wall, with 194 bytes of ordinary text free. The Lisp side (135 Bank-2 bytes, non-consuming Prim-20 query) is fine. Two rounds spent (C5 display, composition). Comfort itself surfaced three real product defects that v2.1 ships fixes for | `docs/planning/v2.1-comfort-stack-product-report.md`; `build/v2.1/comfort-stack-composition-r1/`, `build/v2.1/stack-repair-renderer-pricing-r1/` (trampoline SP 40, admission, E29 attribution, watermark lane); the Comfort media card and device rows; `docs/planning/v2.0.0-pre-plan.md` DESCOPE 2026-09-06 | Sealed return conditions: (a) the VM architecture block (iterative CALL, 2.2) landed; or (b) a deresidentization card frees ≥ 1,000 ordinary text bytes with the facade wall re-derived; or (c) a native hand-over proven on a seed at ≤ 190 bytes. Owner commission either way |
| **Hardware-SP floor — deferred to the capacity block (VM strand), 2026-09-06** | Measured on the hardening seed: the product's legitimate deepest path (`mapcar` at 50) leaves 33 bytes of hardware stack; the measured IRQ/NMI reserve (15) plus abort reserve (12) is 27. No threshold can both reserve them and pass the bound smokes (T = 98 refused `(time …)`); the floor's clean recovery (refusal, prompt return, next evaluation) is executed evidence. The helper (+154 text with the selector) and its measurement receipts are the restart package | `docs/planning/v2.1-hardware-sp-fallback-report.md`; `build/v2.1/hardware-sp-fallback-r1-evidence/` (17-row envelope, threshold receipt `296213e2…`) | The capacity block's VM strand (iterative CALL) adopts the floor as its acceptance instrument: after the depth reduction the same measurement must yield a floor that reserves 27 and refuses no bound row |
| **By-catch from the capacity block and the R2 host phase (2026-09-07)** | Findings that are not product defects but must not live only in prose: (1) the DWX fork's breakpoint PC match is bank/MAP-unaware — a breakpoint on `main_entry` never fires while `c2_decode_from` fires too early; the card-0 PC observer's MAP-aware matching is the model (`boot-phase-ledger-card-prep.md`); (2) the `dwx_*` tool chain cannot be imported outside the main worktree — a 508-module import chain reads `build/` receipts at import time (audit H4/H13, refactor strand); (3) under soft frames, `OP_TAILCALL` into an uncompiled function must pop a VM frame — caught by the lcc fixpoint oracle, regression row on the R2 branch (not in the product); (4) a `-Werror` unused-function red on the l65m native-loader profile when a guard is nested wrongly (`LISP65_DISK_LIBS` inside `MEGA65_F011_LOAD`) — the twelve-profile matrix on the kernel-diet branch now covers it; (5) `c2-while-check` and `c2-interrupt-ownership` rewrite tracked receipts during `check` (two writing checks; the receipts sit uncommitted for deliberate sealing); (6) `runtime-overlay-transport-smoke` shows seven failures on the unmodified world (in the `check-host` residual inventory); (7) the resident image runs within 33 bytes of the hardware-stack limit on `mapcar` 50 (Known Issue, measured) | the subagent branches `worktree-agent-ae304ea899be25d3d`, `kernel-diet-audit`, `worktree-agent-a2c90a05b3d267a24`, `worktree-agent-a78986b3dcfa9c8cd` (all local, unpushed) and the pre-plan entries of 2026-09-07 | Tool-layer items go to the refactor strand; (3) and (4) close with the R2 and diet cards; (5) and (6) with the `check-host` owner decision |
| **GC root stack: unguarded pushes — attributed 2026-09-07, latent, fix priced** | Of 56 root-push sites surviving the product configuration, one is unguarded in the product: `vm_callprim`'s apply/funcall arms push n + 1 slots after the operand guard admitted a full stack (`vm.c:1537`, ASan global-buffer-overflow with a synthetic driver). The quasiquote overrun (`qq_list`, 42 atoms at 128 roots, `eval.c:1564`) is **not** in the product (`LISP65_TREEWALK_STRIP`). No pure-Lisp input filling the operand stack to exactly `GC_ROOTS` before a `funcall` was found; the measured root watermark over the equivalence corpus is 14 of 128. Latent, not a Known Issue. Fix: three exact reserves refusing with the existing statuses (`VM_STACKOVER`, `RECURSION_TOO_DEEP`), **+137 bytes** on the product configuration, identity green (golden run 38/7 byte-identical, 197,161-line trace identical, sanitizers clean) | `docs/planning/gc-root-overflow-attribution.md` on branch `gc-root-bound` (`48e3c14b`, fix `5dca1d3a`) | Rides with the R2 product card (soft frames spend roots per level); coverage gap to close in a bundled session row: a large `defmacro` body or a long literal list compiled through lcc at 128 roots |
| **Quasiquote on the MEGA65 keyboard — DECIDED 2026-09-08: `£`** | The reader accepts ASCII backquote (96) as quasiquote and `,` as unquote (`src/reader.c:323`), but no documented decision exists on how a device user types it: the C65/MEGA65 keyboard has no backquote key; PETSCII `$60` (SHIFT+`*` on Commodore layouts) may or may not reach the reader as 96 through the key driver, and `src/petscii_normalization.h` maps only letters. Separate from the owner's `'x` → `nil` report (apostrophe is PETSCII `$27`, read as `quote`; that report is under host attribution on branch `macro-quote-nil`) | `src/reader.c`, `src/petscii_normalization.h`, `config/c2-v160-input-service-hybrid-contract.json` | Probe done (no key yields 96). Corrected attribution: `$5C` passes the input path intact and is read as a one-character symbol; only the screen echo blanked it (`src/screen.c:69`). Owner word: `£` becomes quasiquote — card prepared on branch `pound-quasiquote-card` (`a040a84a`): reader sugar on `\\` outside strings, screen glyph, host compiler reader parity, contract amendment; +35 bytes, user guide, dialect-contract amendment. Former text: One device row in the next bundled session: press SHIFT+`*` (and any other candidate key) at the prompt and read `` `(1 ,(+ 1 1)) ``. If no key yields 96: an owner decision on an alternative quasiquote character in the dialect (public surface; e.g. `^` or `@`), documented in the user guide |
| **`'` dropped by the hardware virtual-keyboard transport (recurring; attributed 2026-09-07)** | The `m65 -t/-T` virtual keyboard used by `scripts/hw-jtag-repl.sh` silently drops the apostrophe (ASCII→key-matrix conversion inside the external `m65` binary); receipts since Link 64 and Link 92 say "the m65 apostrophe path is not an input authority". The owner's `cap-macro` report was this: `(list + x 1)` compiled as a global value read of `+`, which is unbound as a value → `nil`. The Xemu `~typehex` path passes `$27` correctly | `docs/planning/macro-quote-nil-attribution.md` on branch `macro-quote-nil` (`17a52f55`); `tools/host-lisp/c2_link64_c1_quote_transport_first_red.py`; `scripts/hw-jtag-repl.sh:70-80` validates only LF/CR/`~` | Tool-layer: `hw-jtag-repl.sh` refuses `'` the way it refuses `~` (fail loudly instead of silently), or hex-encodes like the Xemu path; device rows that need quotes use `(quote …)` until then |
| **Unbound global symbol reads as `nil` (dialect decision owed, 2026-09-07)** | `sym_value` (`src/symbol.c:232`) returns the value cell without consulting the boundness bitmap set at `:233`; a bare unbound symbol evaluates to `nil` silently (this is what turned the dropped-apostrophe macro into `(nil 5 1)`). Same permissive class as the documented `car`/`cdr` behaviour | `src/symbol.c:232-233`, `lib/lcc.lisp:193-202` (`%lcc-var` global read) | Priced 2026-09-08 (branch `unbound-variable-error`, `daeb791a`): +37 bytes text (vm.c only; the eval.c guard is dead under the product profile), 0 BSS, ~9–11 instructions on every compiled global read (per-form, possibly per-keystroke — a lane obligation), reusing the existing undefined-function code (wording imprecise; a new code would be a contract change). Fallout: 5 of 13 stdlib suites depend on unbound → `nil` through `load-lib`'s `(symbol-value '*loaded-libs*)` with no `defvar` — a latent stdlib reliance that any error variant must fix first. By-catch: the host oracle's two CALLPRIM-19 implementations already disagree on unbound reads. Owner decision for the dialect: keep permissive (document in the user guide next to `car`/`cdr`) or price an unbound-variable error (a Tier-2-class domain check on the hot global-read path; priced against both lanes before any commission) |
| **Root stack not unwound on abort paths (found 2026-09-07 as `lcc-install`; re-attributed 2026-09-09: four slots per abort from the callers' skipped epilogues, fixed at the producer `lisp_abort_jump` on `r2-card`)** | On `blob too large` (`src/lcc_install_overlay.c:236`) and similar error returns, `gc_rootsp` is left at 11 instead of 0 — a root leak per failed install, repeated failures walk toward the root bound | `docs/planning/macro-quote-nil-attribution.md` §side observations | Joins the R2 root-bound card (exact reserves and unwinding on every error return) |
| **Reader parity: toolchain reader vs `src/reader.c` (found 2026-09-08)** | Two divergences left standing by the £ card: (1) in `tools/host-lisp/bytecode_p0_compiler.py` the characters `'`, `"`, `,` start a token but do not terminate one (`(a,b)` lexes as the symbol `a,b`), while `src/reader.c` terminates on them; closing it requires deciding the `#'` two-character sugar first (the toolchain reader has no branch for it; no `#'` exists in `lib/**` or any suite today); (2) the toolchain tokenizer's string branch has no escape handling, unlike `src/reader.c:239/270` — the two readers do not agree on what a string escape means | `docs/planning/pound-quasiquote-card-prep.md` §5; `bytecode_p0_compiler.py:113-117, 145-155` | A reader-parity card (host tool + conformance cases) after the £ card; owner word only if `#'` semantics change on the public surface |
| **Assembler `.zeropage` declarations of ordinary C statics (found 2026-09-08, A seed halt)** | `src/c2_kernal_window.s` and `src/c2_boot_chain_commit.s` declared five plain C statics `.zeropage` (`c2_backstop_rtov_busy`, `c2_backstop_rtov_loaded_len`, `lisp_toplevel_active`, `c2_backstop_pending_code`, `vm_boot_overlay_status`); none is owned by an explicit zero-page section, so their 8-bit relocations only held while LTO's automatic zero-page promotion happened to pick them. Lever A's layout moved `pending_code` to `$B9ED` and the seed link failed on two `R_MOS_ADDR8` relocations. Only `mem_oom` is contract-owned (`LISP65_C2_FIXED_ZP`). Latent in every shipped product: any layout change could have tripped it | `docs/planning/capacity-lever-a-product-report.md`; `build/capacity/lever-a-r1/seed-stop-attribution.json`; correction `lever-a-zp-contract@ecc51fa4` (declarations dropped, +6/+4 text bytes per unit, all ten relocations `R_MOS_ADDR16`, proven per unit with the product compiler) | Rides the A card re-seed; a `check-source` gate that rejects `.zeropage` on symbols outside the fixed zero-page contract is a candidate for the check-host follow-ups |
| **Initialized zero-page load image occupies its slot fully, 12/12 bytes (found 2026-09-09, R2 final)** | The owned linker fixes `.text` at `$2023`; the twelve bytes after the BASIC header are the only room for `.zp.data` initializers. R2's layout let LTO promote `vm_buf_bank`/`vm_buf_off` (initializers `$FF`) into that image (15 bytes) and the seed link overlapped the startup opcodes; repaired by explicit runtime initialization (+8 boot-overlay bytes). The slot now has zero spare capacity: any future initialized cell that LTO places in zero page breaks the link. The new pre-WPLTO extent gate catches it before a build | `build/r2-product-r1/final-halt-report.md`; `build/r2-product-r2/card-report.md`; `c2_product_substitution_link.py` `full_map_platform_c_ld` | Standing rule: new zero-page cells are zero-initialized with runtime setup, never load-initialized. If a card genuinely needs more initialized ZP, a placement card moves the text origin (LOADADDR/tuple contracts) rather than squeezing |
| **Latent: the Bank-2 code allocator's upper bound is the bank end (65,536), not the card-2b carrier start (60,758) (found 2026-09-09, library card front attribution)** | The consumed allocator can reserve up to the bank end although the disk-window carrier of card 2b owns `$2ED56..` since v2.1; the unchanged helper reproduces it on the host with the sealed boot directory table. No actual overwrite proven (user code has not reached the front); an inherited owner gap of the card-2b era | `build/library-delivery-r1/front-attribution/report.md` | Closed in the library delivery card as a composed native member: the derived owner bound applies to reservation, write and rollback, with executed boundary tests and a bank-end mutation that must fail; the new Bank-2 function-cell-table owner uses the same bound |
| **Bank inventory after boot (derived 2026-09-09): bank 1 wholly free by owner reservation; bank 5 tiles exactly to `$60000` at zero slack; the bank-2 "hole" is the append arena, not free** | Free after boot: bank 1 65,536 (no media role targets it; no DMA/far-write site names it; held by the owner's user/graphics promise, no reset survival), bank 2 185, bank 3 210 (session plane copied from Attic), bank 4 256 (EXT heap, string arena, disk scratch), bank 5 0 (`50816 + 10208 + 752×6 = 65536`). The 12,907-byte bank-2 run read as a hole is `c2_lite_bank2_fronts`, the append arena that every `define`/`defstruct` writes under `LISP65_C2_LITE_COLD_EVICTION`; it is user-program space. Attic above `$8500000` is ~3 MiB but CPU-MAP transport only (64 bytes per call; DMA excluded by L10). An LMA in banks 1–4 in the linked ELF is a staging artifact, not a device destination | `docs/planning/bank-inventory.md` (`bank-inventory-prep@1f0fcd5a`); `docs/planning/c2-lite-bank-ownership-audit.md` | Owner ruling 2026-09-11: the storage-owner card **may take up to 16 KB at the top of bank 1** for the symbol store (48 KB contiguous below stay reserved for user/graphics), on condition that the card first proves no recovery path depends on the symbol store surviving a reset (bank 5 and Attic survive, bank 1 does not); if a path depends on it, the card falls back to Attic and prices it |
| **E000 resident inventory (derived 2026-09-09): 7,882 of 8,125 window bytes are placement convenience; 425 bytes move to Bank-0 text with no stub (tier 1)** | Contract-bound residents are 159 bytes (vectors, IRQ, NMI, RESET, state; 243 with the queue driver and capture pair); the MAP-switch category is empty (the window is mapped once at `c2_kernal_take_ownership()`, never switched; `ld:656-660`). Tier 1 (zero outbound edges, cold, Bank-0 callers only): `c2_stream_gc_checkpoint` 191, `c2_product_physical_copy` 145, `c2_session_emit_reset` 47, `c2_header_counts` 42 = 425. Tier 2 (cold, facade edges, no E000 caller) 4,254. Alternative: the self-contained `c2_append_begin` package 1,172 bytes. No padding is reclaimable (CALLPRIM pad is a dialect width `== 168`; `$FFF0` pad is a vector congruence). The binding gate is the capture watch 57/57 (holes A and B), not the 54 floor; floor 54 is chosen (`c2-append-final-hybrid-contract.json`, 8,192 − 8,138), the watch 57 = 54 + 3 is the derived number. The pricing tool's relocation verdict never evaluated ordinary Bank-0 text (2,825 free after R2) | `docs/planning/e000-resident-inventory.md` (`e000-inventory-prep@4a47c62d`); `config/c2-vm-dirmiss-detail-e000-evacuation-contract.json` (admission test) | Tier 1 landed in the library card's seed 6 (2026-09-09; the sequencing step had to stay resident on the unchanged entry form, `placement-proof.json`): 425 bytes moved, text reserve 2,389/32, capture watch 458/57. Tier 2 and the `c2_append_begin` package remain the next E000 levers |
| **Residue of the withdrawn fail-closed black-box contract in E000: `c2_kernal_output_cell` (4 bytes, zero callers, zero relocations) and two unnamed state bytes `$FF8E/$FF8F` (found 2026-09-09)** | Only citation is `config/c2-fail-closed-blackbox-contract.json` with status `terminal-first-red-withdrawn`; six bytes with no live purpose. Also: `retired_window_brk_classifier`/`retired_window_resume` are defined in `src/c2_kernal_window.s` but link at `$21B7`/`$21F7`, not in the window | `e000-resident-inventory.md` §by-catch | Owner ruling 2026-09-11: **remove** (the dead function and the two state bytes), riding the next card that touches `c2_kernal_window.s`; the misfiled functions move to their real owner file in the same card |
| **Ownership contracts stale by `$4000` against the R2 world; sealed bank-2 hole drifted 12,963 → 12,907; `src/mem.c` asserts bank 4 free and not free 750 lines apart (found 2026-09-09, bank inventory)** | Three by-catch items from the inventory: contract addresses in the C2 ownership contracts no longer match the R2 link map by `$4000`; the card-2b sealed hole figure is 56 bytes stale; two contradictory static assertions on bank 4 in `mem.c` | `bank-inventory.md` §by-catch | Contract rebind and the `mem.c` assertion pair go into the storage-owner card's preflight; the hole figure is retired with the append-arena correction above |
| **Native cycle lane: first-sample boot-phase offset dominates the mean (found 2026-09-08, £ seed)** | The native CPU/DMA adapter reports mean cycles per character over 40 keys (single lane) or 5 batches of 8 (batch lane). In the £ seed receipt the whole batch delta (+882,838 of +882,838 cycles) sits in sample 1; samples 2–5 differ by ≤265 cycles. The single lane shows the same: sample 1 −1,546,745, the other 39 within ±1,400. Sample 1 includes the boot/warm-up phase before the first key, so with n=5 one phase offset moves the batch mean by 2.6 %. A's 0.991× batch reading was most likely the same artifact in the other direction. The reported ratios are therefore not per-character costs | `build/pound-quasiquote-seed-native-lanes-r1/receipt.json` (`cycle_deltas` per row); `build/capacity/lever-a-r1/r2-native-lanes.log` | Adapter correction bound in the pre-plan (steady-state ratio excludes sample 1 and is the wall; sample 1 reported separately); receipts of A and £ re-read under it, no re-measurement |
| **Native cycle lane: a multi-million-cycle event lands on a varying sample index (found 2026-09-08, £ final)** | Byte-identical seed and final £ worlds: in the seed run the event sat in sample 1 (−1,546,745 cycles vs control); in the final run sample 1 differs by only −33,443 but index 8 carries +3,203,542 (4,005,529 → 7,209,071), all other 38 indices within ±130. The first-sample rule of `80382cd1` therefore does not isolate it; the stationary single ratio 1.0160 is that one sample. Mechanism unattributed (a periodic pass of roughly 1.5–3.2 M cycles; candidates: a collection, a blink/frame-bound repaint) | `build/pound-quasiquote-final-native-lanes-r1/receipt.json`, `…seed-native-lanes-r1/receipt.json` (`cycle_deltas`) | Paired-index rule bound in the pre-plan (line-wrap card converts the adapter); attribute the event once with the PC-histogram observer on the diagnostic world |
| **Native single-key lane counted a cursor screen write as a completed key (found 2026-09-08, line-wrap attribution round)** | The lane's capture point fires on a screen write; the cursor paint before the first key was counted as a stimulus, so every single-key run shows 39 consumed inputs (39 `a` plus cursor) against 40 claimed. The PC witness shows sample 1 executing only `screen-put-char`, no key-event call. This is the 61,000-cycle sample 1 seen since the A card and the origin of the 'first-sample' phase artifacts; the index-7 deviation of the line-wrap seed vanished on both repeats. Batch lanes are unaffected (40/40). Instrument defect; no product input loss established. A's and £'s single-key ratios compared like with like under the same defect and stand as measured | `docs/planning/line-wrap-product-report.md` (`85a87671`); attribution-round receipts under `build/line-wrap-r1/` | Conversion bound in the pre-plan: per-stimulus completion proven by expected character and consumed event counter, cursor write as failing mutation; both unchanged worlds re-measured; the two earlier lane rows are re-read under it |
| **Per-keystroke native cost grows linearly with line length (found 2026-09-08; attributed 2026-09-09: cycles/key = 3,308,713 + 100,392 × n, the slope is `nthcdr` in `%rl-put`, Θ(n) per keystroke; idle share under 0.01 %)** | Single-key lane samples rise monotonically 3,403,181 → 7,117,949 cycles over 40 keys, about +100 k cycles per additional character on the line (identical on A and £ worlds). Emulated CPU/DMA cycles between capture points, so idle polling is included; no wall-clock claim. Still: a per-key cost proportional to line length points at an O(n) pass per keystroke in the native prompt path (matcher scan, repaint or line copy) | same receipts, `cycle_deltas` of the `batch_cap: 1` rows | Owner priority 2 candidate: attribute with the PC histogram before the Comfort hand-over; the line-wrap card must not add another O(n) pass |
| **Bank-2 call cost: about 50 k cycles per Lisp call, 73 % of it re-resolving the callee's code from the banked product image (found 2026-09-09, per-key attribution)** | Per additional character: 2 VM invocations, 1 primitive, 3 directory lookups, 18 product-entry lookups, 44 banked reads; `c2_map_cpu_read` 26 %, `vm_run_inner` 21 %, `vm_object_load`, `c2_product_entry_record`, `c2_stream_product_materialize_entry`. The fixed 3.3 M-cycle term per key has the same composition. This is the dominant latency mechanism of the whole Bank-2 surface, not of the editor alone | `docs/planning/per-key-cost-attribution.md` (`per-key-cost-attribution@c9857ae8`); `build/per-key-cost-attribution-r1/` | Owner-priority-2 candidate card "code-object cache": an engine-side cache of resolved code objects (option D), priced at a final link against the post-R2 reserve; the owner weighs headroom against latency. Editor-side options: (A) carry the first dirty cell (blocked by the 255-byte cap of `%read-line-loop` and the full state list), (B) cdr chains for constant-index accessors (1–2 M of the fixed term), (C) drop `nthcdr`'s base-case `length` walk (a Tier-1 contract decision, see the audit rule) |
| **`vm_buf_ensure_mine` loads the code-object header twice per return (found 2026-09-13, cache prep)** | `src/vm.c:2091` and `:2097` both load the header; caching `nlits` removes one load per return at no RAM cost | `docs/planning/code-object-cache-prep.md` §by-catch | Free member of the code-object cache card (priced with it) |
| **C2D attribution gap: 18 entry-record lookups per character should give 36 `c2_stream_c2d_read` entries, 30 were measured (found 2026-09-13)** | Six reads unaccounted for in the per-key attribution; `c2_source_read` has no symbol in the linked product (inlined into `c2_product_entry_record` and `vm_object_load`), so PC attributions mis-name the source transport | same report §by-catch | The cache card re-derives the C2D read population with the inlined transport named before leaning on the 73 % figure |
| **Two E000 figures cited as current: `e000-resident-inventory.md` says 67/54 (R2 world, before the tier-1 evacuation), the Ship and minibuffer reports say 468 → 345/54 (after it) (noted 2026-09-13)** | Not a contradiction but two worlds; the inventory document predates the library card's 425-byte evacuation and must say so | same report §by-catch | A dated banner on the inventory document with the next docs commit; the register's E000 rows already carry the evacuation |
| **GC hot path is page-crossing sensitive: a 20-byte text shift added two page crossings in the MAP reader, +18,255 cycles per collection (found 2026-09-10, retirement repair final)** | Any card that shifts ordinary text can move the GC's hot branches across a 256-byte boundary; the GC wall (545–760-cycle noise) then reads red without a semantic change. Same mechanism can hit the native key lanes | `build/retirement-repair-r1/final-halt.md` | Alignment contract bound: hot GC ranges placed without internal page crossings and asserted at link time; misaligned form is the failing mutation. Candidate for the assumption inventory: enumerate all hot ranges (GC, key path, DMA read facade) under the same assertion |
| **Standing rule (owner delegated to the reviewer, 2026-09-12): a placement-only GC delta of at most 0.05 % of a collection is accepted as a named cost** | Today's threshold is about 2,400 cycles (0.05 % of 4,829,889), roughly 60 µs at 40.5 MHz. Conditions: the delta is fully attributed to placement (page crossings, absolute versus zero-page accesses) with no unexplained remainder; the alignment lever is projected first and taken when it costs a few bytes (the 12-byte pad of the retirement repair is the precedent); the card report states the cycles, the attribution and the bytes not spent. Anything larger, anything not placement, and any growth in the number of collections still halts. The 110-cycle noise band stays the instrument's resolution, not the acceptance criterion | `docs/planning/post-2.2.0-plan.md` (INIT card rounds; `build/init-repair-r2/gc-placement-report.md`: 49 bytes to remove 416 cycles was refused) | Applies from the INIT card on; the assumption inventory's hot-range page-crossing gates keep flagging crossings so the lever stays available |
| **PC-histogram lane runs die with SIGPIPE (exit 141) when a second emulator runs concurrently (found 2026-09-09)** | The monitor client reconnects per command and xemu does not ignore SIGPIPE; 3 of 4 lane attempts died mid-run while another agent's emulator ran. Instrument flakiness, no product finding | `per-key-cost-attribution.md` §by-catch | Tool follow-up: serialize emulator runs per host or ignore SIGPIPE in the DWX fork; report entry-PC call counts alongside instruction counts (symbol-range aliasing) |
| **Instrument defect: uppercase JTAG virtual-keyboard input; repair accepted, retained-history inventory closed with explicit unproven rows (2026-09-12)** | `NESTED.L65` arrived as `.65`; the old preflight accepted modifier-only input. This explains the controlled repeat, not the earlier manual `nil`. Three additional 2026-07-08 tool/result pairs show `IDE` becoming empty and two `Find file: ` prompts becoming `ind file: `; they are not witnesses for the intended inputs. No loader defect follows. | `build/init-repair-device-r2/uppercase-transport-attribution.md`; `docs/planning/historical-transport-inventory.md`; `build/historical-transport-inventory-r1/proof-use-receipt.json` | Retained source/intent/raw-write candidates and unresolved history are explicitly non-admitted as input-identity proof; still-needed claims require a fresh witness before reuse. This is not reconstruction of every past physical input. INIT INNER/NESTED retain repaired transport, public V2 length/first-character echoes and visible full forms; manual 16/17-name rows retain separate visual-only proof. `string->list` was an invalid public-V2 test, not the standing echo prescription. The combined session still needs qualification and contact authority; its verified IDE load and M-x entry replace reliance on old malformed inputs. |
| **Producer reuses predecessor generated data units for a new Plane (found 2026-09-08, line-wrap seed E25)** | `pound_quasiquote_product_card.materialize` replaces every generated translation unit with the predecessor's qualified copies; correct while the Plane is unchanged (£), wrong for a new Shelf/C2D world. The line-wrap seed booted with `{E}25`: `c2-stream-phase-02a.c` carried £'s twelve 16-bit delivery CRCs, all disagreeing with the packed records (first Shelf record compiled `2c4f`, actual `3e4f`); the decoder rejected correctly. Member of the bound≠consumed / stale-derived-consumer family; no editor defect established | `docs/planning/line-wrap-product-report.md` §Cause; `build/line-wrap-r1/boot-oracle-attribution.json` | Conversion round approved: derive the world-derived data-consumer population from the selected Plane, regenerate it, pre-WPLTO gate comparing both phase-02a tables to the selected records (old £ tables = regression mutation); a producer must never inherit generated data across a Plane change |
| **Class: a producer resolves an input by availability instead of by binding (2026-09-09 CRC inheritance; 2026-09-10 public projection fell back to `scripts/` decoders)** | The public 2.2.0 producer's include gate proved that `c2-stream-decoder.c`/`c2-stream-v2-decoder.c` resolved, not that they resolved to the bound generated source; the `scripts/` fallback supplied older implementations, changing C2D version, record check and root encoding in six overlay sections that reach `BOOT.BIN`/`SESSION.BIN` while the PRG stayed identical. Same shape as the line-wrap producer inheriting £'s CRC tables | `build/release-v2.2.0/producer-input-attribution.md`; `build/line-wrap-r1/` producer halt | Standing rule (bound 9d0f3a8f): every producer input is resolved by SHA against a transitively closed projection; fallbacks outside the projection are removed from search paths; a resolution outside the projection fails. Member of the assumption inventory card |
| **`c2_m65_hw_gate.py` rewrites the sealed v1.4 host-first receipt on check (found 2026-09-08, line-wrap full runs)** | The gate writes the live `base_suite` size/SHA into `c2.3-v1.4-m65-hw-host-first-receipt.json` (7,647 → 18,833 bytes after the wrap cases joined the owner suite), turning a sealed era receipt into a working-tree modification on every full run. Same family as the E000 pricing receipt before its era binding (`14c956a1`). Working-tree change reverted by the reviewer, not sealed | `tools/host-lisp/c2_m65_hw_gate.py:28`; `c2_v14_link89_device_session.py:36`; `c2_v14_link90_parity_toy_close.py:29` | Joins `check-host-followups`: bind the gate to the sealed suite content of its era (read at the sealing commit), never to the live file; selftest fails on a live-file read |
| **`%ide-dir-scan-directory` returns a silently truncated listing on fuel exhaustion (found 2026-09-08, chain-walker guard)** | `lib/ide-disk.lisp:254`: with fuel 0 the walker returns the reversed accumulator, indistinguishable from a complete listing; `dir` calls it with fuel 64, so exhaustion means a directory chain longer than 64 sectors or a cycle that passed `%disk-directory-link-valid-p`. The read-failure branch of the same walker returns `nil`. Executed: `(%ide-dir-scan-directory 40 0 0 '(77))` → `(77)` | `build/check-host-followups-r1/status-008fd557.md` | Bound: the walker's partial result is a declared, named exit in the guard inventory until converted; conversion to the `nil` error exit (same as read failure) rides the next Bank-2 product card as a composed member, after which the partial result is a failing mutation |
| **Product defect: line-wrap `%rl-cut` leaves the old cursor cell reverse after Backspace (found 2026-09-09, A/£/wrap device session)** | Device RAM: `lisp65> ` followed by ten `$A0` cells at columns 9..18 after ten characters and ten Backspaces (owner: every Backspace leaves a white box). Source attribution: the unchanged-lift branch of `%rl-cut` repaints `[next-position, length)` with the OLD length exclusive, so the cell after the old end, painted as the reverse-space cursor (attr 129 → bit 7 in the screen code), is never repainted; the pre-wrap cut painted through `edge = length − start + 1`. Line-wrap card regression; the lift-drop branch blanks its released row and is unaffected | `build/a-pound-wrap-device-session-r1/device/observations.md` (receipt `b2277110…`); `lib/stdlib-read-line.lisp` `%rl-cut`; `git show 520352a6:lib/stdlib-read-line.lisp` | One repair round on the wrap card (`wrap-backspace-repair` branch in preparation: stop = length + 1, exact-row regression cases); device re-check row in the next session |
| **Product defect: the L65INDEX file-chain reader uses the directory link guard, so an index longer than one sector cannot be read (found 2026-09-09, library card final)** | `%l65i-next-byte` (`lib/stdlib-require.lisp`) validates the index file's next-sector link with `%disk-directory-link-valid-p`, which admits only track 40; with eight libraries the 272-byte index continues from track 18/34 to 18/35 and `(require 'buffer)` returns `nil`. Executed on the packed bytecode and confirmed in the stopped emulator state. The other four callers of the guard (`%load-scan-directory`, `%load-lib-scan-directory`, `%compile-slot-find`, `%ide-disk-find`) walk the directory and use it correctly. Latent since the index reader was written; exposed by the fifth-to-eighth library | `build/library-delivery-r8/final-card-report.md` | Repair round of the library card: a file-chain validity predicate for data files (track 1..80, sector < 40, no self-link, fuel), derived population of every file-chain reader in `lib/` and its guard, host case with a two-sector index on track 18, directory contract untouched with its own regression control |
| **Product defect: `require` inside a disk-loaded source (`INIT.L65`) overwrites the source loader's sector scratch (found 2026-09-09, library card INIT row)** | The source loader keeps the unread rest of the current INIT file sector in the 256-byte directory scratch (`disk_source_fetch` continues from it); `require`'s index reader uses the same scratch (`ext_disk_get`, base `$6900` bank 4) and overwrites it with L65INDEX sector 18/36, so the reader sees index bytes and NULs instead of source: `LOADING PLACE...` then `READER: UNCLOSED LIST`, no banner. Two simultaneous owners of one scratch; latent since INIT loading exists, exposed by the first `INIT.L65` that loads a library | `build/library-delivery-r12/card-report.md` (RAM and final ELF evidence) | Owner decision 2026-09-09: **A, with the condition that the repair is not deferred**: this release ships without `INIT.L65`, packages load by hand; the repair (own scratch for the index reader, or the INIT source read whole before evaluation) is the **first card after the R2 release**, ahead of the storage-owner card, together with the string-form `require` and the default load's return; member of the assumption inventory: scratch ownership |
| **Product defect: a nested `load` inside `INIT.L65` runs the inner file, then the outer INIT stops silently (found 2026-09-11, INIT repair prep)** | The source loader keeps one set of stream state; a nested `load` replaces it and the outer stream does not resume. Separate from the scratch clobber, which the loader-side repair closes | `docs/planning/init-require-repair-prep.md` §by-catch | Member of the INIT/require repair card: make the loader state reentrant (save/restore across a nested load) or refuse a nested load with a loud error, whichever prices smaller; a silent stop is not acceptable |
| **Usability: `load` returns a bare `nil` for a file that is not on the disk, while a missing file inside a nested load reports `LOAD: CANNOT OPEN` (found 2026-09-12, INIT device session)** | The owner mistyped a name and saw only `nil`, with no hint that the file was missing; the same condition one level deeper prints an error. Reviewer-verified from the uploaded medium's directory: it holds 29 entries and neither `NESTED.L65` nor `INNER.L65`, so the `nil` was correct behaviour for a missing file | `build/init-repair-device-r2/load-halt-report.md`; directory of `INITFIX-upload-readback.d81` | Next Bank-2 card that touches the loader: a missing file reports the same error as the nested case (no new error surface needed, `LOAD: CANNOT OPEN` exists); `require` keeps `nil` for "not in the index" |
| **`load` answers `nil` both for "not on the disk" and for "too large for the file window" (found 2026-09-12, host reproduction)** | Five entries of the device image exceed `DISK_FILE_MAX` (38,400): `CODE.BIN`, `C2D.BIN`, `SESSION.BIN`, `SHELF.BIN`, `LISP65.PRG`; `%ide-disk-find` returns a start for all five, so the name matches and only the size refuses. The two conditions are therefore not distinguishable from the answer, and a session's `LOAD: CANNOT OPEN` and a bare `nil` are not interchangeable observations | `docs/planning/nested-load-repro.md` §by-catch | Same loader card as the missing-file message: distinct reports for not-found, too-large and open-failure |
| **Product defect: a lookup name longer than 16 characters silently resolves to the 16-character file (found 2026-09-11, host D81 widening B2; confirmed in `lib/`)** | The shared Lisp matcher `%load-name-match-at` (used by `load`, the `load-lib` disk fallback, `%ide-disk-find`, `%compile-slot-find` and M65D's target check) and the C `disk_dir_find` compare 16 positions only, so `(load-lib "abcdefghijklmnopq")` returns `t` and loads `abcdefghijklmnop`; `m65d-save` refuses names over 16 and the product shelf lookup refuses over 8 | `docs/planning/dir-find-header-attribution.md` §4; `docs/planning/host-d81-model-widening.md` §by-catch | Proven 2026-09-12 on the real device image: in 2.2.0 `(load "ABCDEFGHIJKLMNOPQ")` returns `t` and **streams the 16-character file 18/28**, i.e. it hands the wrong chain start to `load`, the IDE read/save path and the FASL slot writer; the card's guard returns `nil` instead. All four callers funnel through `%load-entry-match-p`, so the one guard fixes the family; `%m65d-name-ok-p` already refuses names over 16 before any scan. Member of the INIT/require repair card, now with its executed row |
| **Product defect (host-executed): the IDE status row stops repainting while minibuffer input changes, and the minibuffer cursor sits inside the prefix (found 2026-09-11, housekeeping Mini8)** | `%ide-status-current-p` (`lib/ide-ui.lisp:798`) compares buffer name, modified flag, message and line but not the minibuffer input; `%ide-mini-set` (`:57`) keeps message code 1005 without invalidating the status cache, so after `M-x Find file: d` the row stays at `d` while the input holds `demo1234`; forcing invalidation shows the full text. Separately the cursor column (`:999`) is the length of `ide-status-line`, whose mini branch (`:597`) omits the `buffer M-x` prefix the renderer (`:855`) draws, so the cursor lands inside the displayed text. Input is not lost. Executed on the generated dialect-v2 IDE on the host VM. **2.2.0 is affected:** the released `roles/library-ide.bin` is byte-identical (SHA `525746bb…`) to the base build and every implicated function hashes the same; both defects first ship in 2.2.0 (status cache and idle blink from the v1.2.6 work; the prefix drawn since then); the device blink start `%ide-idle-mini-start` has the same column bug. Device not yet checked | `build/housekeeping-20260910/mini8-attribution.md`, `mini8-screen-probe.py` | Repair prepared on `ide-minibuffer-repair-prep@9328c62e` (`%ide-mini-set` clears the status cache; one prefixed parts list feeds renderer, render cursor and idle blink; IDE core +40 code / +14 dir bytes, largest object 252; per-key render 2,966 → 5,410 VM steps within the 95,000 budget); composed into the INIT/require card; the Mini8 row's oracle becomes the exact screen-content check (placeholder read as failing mutation); Known Issues entry lands with that card's docs member (the v220 bundle-docs gate binds the current Known Issues) |
| **Device red: the repaired IDE minibuffer shows a display overlay, a strong delay and suspected key loss (found 2026-09-12, INIT card device session)** | The reviewer-prepared repair makes `%ide-mini-set` clear the status cache, so every minibuffer key repaints the whole status row; on the host that read 2,966 → 5,410 VM steps inside the 95,000-step budget, but the device pays about 50 k cycles per Bank-2 call, and no native lane ever measured the IDE minibuffer path (the lanes measure the native prompt). **Owner 2026-09-12: the typing was aborted because it was unbearably slow, and while typing characters were definitely lost; the owner judges the minibuffer implementation as a whole to be bad.** The defects are latency and key loss together; session stopped at that row, sealed; no repair or memory write on the device | INIT card device session (Codex report); `docs/planning/ide-minibuffer-repair-prep.md` | Three symptoms attributed separately host-side before any repair form: overlay (which writer owns the overwritten cells), delay (native cycles per minibuffer key on the diagnostic world), key loss (queue depth during the repaint). Then either an incremental repaint (only changed cells) priced on the card, or the IDE member is descoped from the INIT card and returns with the Comfort card |
| **Product defect: opening the IDE minibuffer eagerly builds the file-completion list, including two real disk sector reads (found 2026-09-12, minibuffer pricing)** | `%ide-find-key` (`lib/ide-disk.lisp:520-526`) calls `(dir)` on open to build the completion list only TAB reads. Measured on the pinned emulator: `C-x C-f` costs **251.6 M cycles on 2.2.0 / 262.6 M on the INIT world, about 6.3 s at 40 MHz**, 28–31 keystrokes' worth, in both worlds. **The disk is not the cost**: every disk/F011 symbol together is 0.077 % of its 78 M instructions; it is Bank-2 interpretation. Present in 2.2.0; no repaint form touches it | `docs/planning/ide-repaint-forms.md` (branch `ide-repaint-forms@a7fec393`) | Own repair, can land independently of the repaint rework: the completion list is built lazily on TAB; host rows for open cost, TAB still completing, and no sector read on open |
| **The IDE key path polls `$d60a` and never arms the capture ring, unlike the native prompt (found 2026-09-12)** | Guard row in the emulator: injecting 16 characters moved the visible count 24 → 26 while `C2K_INPUT_EVENTS_{RAW,SEEN,STORED,TAKEN}` stayed `[7,7,7,7]`, so the IDE reads keys by polling and the hardware capture path is not involved. **No drop counter exists on that path, and the guard row supports no claim in either direction about lost keys**; the owner reports losses at speed, and at 0.2 s per key the poll gaps are long | same report §emulator lane | Minibuffer rework card: the IDE takes the same event-queue input path as the native prompt (or arms capture), so a burst is consumed from a queue rather than sampled; the burst row with accept/consume/drop counters is the proof |
| **The reported "status row not cleared" does not reproduce on the host; the 2.2.0 cursor column marching through the prompt looks identical (found 2026-09-12)** | All six measured variants pad the row to full width on entry and re-entry, over long and short previous rows; what does reproduce is 2.2.0's cursor column taken from the unprefixed status text, landing at column 20 inside the prompt and moving through it (`-- scratch M________________cratch] -- 557/330` after 16 keys) | same report §2 | The rework card keeps the row-ownership rows anyway (cheap) and fixes the cursor column at its root; the device row decides whether the owner's observation is the cursor artefact |
| **Product defect: public 2.2.0 Ship interactive sample cannot be built (found 2026-09-11, housekeeping ship-fleet)** | Executed from the downloaded, SHA-verified public source archive: its core catalog selects the unprojected editor and reaches six calls to five absent `%sexp-*` implementations. Emission rejects before a native image exists; no device failure of the released REPL is claimed. Selecting the actual public product source closes all calls, but exposes a separate ABI mismatch: `%rl-render` calls private `key-event 2`, while the standalone Runtime lacks `LISP65_V160_INPUT_HYBRID` and returns TypeError. The product source also depends on Capture initialization and raw-code semantics; a flag alone is not a proven fix | `build/housekeeping-20260910/ship-public-release-probe.json`; `ship-selected-attribution.json`; `ship-selection-halt.md` | Catalog selection prototype consumes the same public projection source owner, with no matcher/function list or external-call exemption; three closure mutations fail. Sample fleet held at the native host ABI mismatch. Owner/reviewer decision needed for standalone input adaptation versus separately commissioning that work. Known Issues entry for the public build failure belongs to the INIT docs member, as authorized; existing published archives untouched |
| **Source defect, not in the 2.2.0 product: `disk_dir_find` (`src/io.c`) starts its directory walk at the header sector 40/0 and treats the header as file entry 0 (found 2026-09-11)** | A lookup of the disk name minus its first character (`65sys`, `65work` on the release media) returns a false hit with start 0/204; in builds that link it the load reports not-found, a content save fails and an empty save returns success without writing; nothing writes a wrong sector. The 2.2.0 ELF does not link the function or any caller (`LISP65_V2_CARRIER_CUT` removes the `P_SAVE` path; none of 40 sampled ELFs link it); `lib/lcc-fasl.lisp` `compile-string` has the same start but is historical | `docs/planning/dir-find-header-attribution.md` (ELF evidence, caller table, collision table; harness on branch `dir-find-header-attribution@0f1c5af9`) | One-constant fix (`sector = 3`) rides the INIT/require repair card, which touches `src/io.c`; the harness joins its host rows |
| **The file-window limit is profile-dependent: `src/obj.h` defaults `DISK_EXT_FILE_MAX` to `0x9300`, the product profile sets `0x9600` (38,400) (found 2026-09-11)** | A build without the product define silently has a 768-byte smaller window; the IDE library is at 92 % of the product figure | `docs/planning/host-d81-model-widening.md` §by-catch B4 | Assumption-inventory member: the default removed or asserted equal to the product value |
| **`equal` compares strings by identity, not content (found 2026-09-11)** | A cache or lookup keyed with `equal` silently misses on equal-content strings; the reviewer's own binding for string-form `require` assumed `equal` and would have disabled the fast path. The prep uses `string=` | same report | Documented behaviour to state in the language reference with the next docs round; the assumption inventory checks every `equal` on strings in `lib/` |
| **Product defect: the retirement guard assumes fixed hardware-stack offsets (+7/+8) and corrupts a return address when the cleanup prologue pushes one more register (found 2026-09-09, device red)** | `c2_rtov_retire_continuations` reads the two return addresses at fixed offsets after TSX; the final cleanup prologue now saves one more register byte, so the guard reads across the extra push, overwrites return-address bytes, and cleanup returns to `$1047` instead of `$3047` before `longjmp`: the fail-closed halt seen on the device after a stack error. Executed and captured on the host on the release ELF. The layout shift comes from the kernel cards (shared entry / soft frames); the guard's assumption is the defect | `build/library-release-return-attribution-r1/report.md`; `build/library-release-device-r1/device/red-report.md` | Repair first: the guard derives its offsets from the actual frame (a frame descriptor or a marker pushed by the prologue), never fixed constants; executed recovery rows for a stack error raised during direct evaluation and during compilation of a top-level form, each ending at a live prompt; the fixed-offset form is the failing mutation |
| **Product limit: direct evaluation of a call's arguments uses one soft frame per argument (`%c2-direct-values`), so more than 15 arguments raise a stack error (found 2026-09-09)** | 12 arguments evaluate; 13/14 hit the 12-argument `apply` limit (type error, a separate documented contract); 15 and 40 exhaust the 16 frames inside `%c2-direct-values`. Pre-R2 the same forms hit the 13-level hardware cliff (repeated E29), so no form with more than 12 arguments ever worked on the device | same report | Bank-2 member of the repair card: `%c2-direct-values` iterative with an accumulator (frame-constant), host rows at 12/13/15/40 arguments; the 12-argument `apply` limit stays and is documented in the guide |
| **Owner-visible contract: at most 12 arguments per call, VM-wide (`VM_MAXARGS 12`, since the VM exists; surfaced 2026-09-09)** | `src/vm.h:124`: primitives receive `argv[12]`, `apply` is capped at 12 (`VM_APPLY_MAXARGS`), compiled `OP_CALL` with more than 12 arguments is `VM_BADOPCODE`, and every frame reserves 13 operand slots on the root stack (`GC_ROOTS=128` in the product). So `(+ a … )` with 13 arguments and `(apply '+ list)` with a list longer than 12 both fail, at the REPL and in compiled code; a `&rest` function receives at most 12 actual arguments per call. Raising the constant costs root-stack slots per frame (recursion budget), the argv arrays, and the 8-bit call protocol | `src/vm.c:821-828, 1098-1127, 2368, 2498-2598`; `lib/lcc.lisp` §VARIADIC (n-ary `+` compiles to a generic call, not a fold) | Documented in the guide and Known Issues for this release. Priced option after the release: (a) `VM_MAXARGS` 16 or 24 against root-stack slots per frame and BSS; (b) variadic primitives folded pairwise by the compiler and by `apply` (no argv bound for `+ - * / < > = list append …`), which removes the limit where users meet it most; owner weighs |
| **Instrument gap: host oracle `screen-put-char` ignores the attribute, so reverse-video residue is invisible to `expect_screen_rows` (found 2026-09-09)** | `tools/host-lisp/bytecode_p0.py` prim 11 stores `code & 0xFF` regardless of attr; the product ORs bit 7 into the screen code when `attr & 0x80` (`src/screen.c` `scr_put_at`, `scr_write_span`). Every framebuffer expectation derived on the host therefore compared `$20` where the device holds `$A0`; the wrap card's Backspace rows passed on the host for this reason | `bytecode_p0.py:1842`; `src/screen.c:181,204` | Oracle models bit 7 exactly as the product; suite runner gains exact-code rows with a residue-detecting selftest; existing rows keep their 7-bit comparison unless converted (same repair branch) |
| **Instrument gap: the IDE host harness ran with a permissive `nthcdr` instead of the product's Tier-1 domain, so a malformed status-cache list passed on the host and failed natively (found 2026-09-13, minibuffer rework r2)** | The nameless composition marked the pending suffix by ending the eight-cell status cache in `t`; `%ide-mini-drawn` calls `nthcdr` on it, whose shipped rest validation reaches `%length-from` with `xs = t` and raises prim 58 `%list-malformed-error`; the host harness's permissive `nthcdr` accepted the dotted list. With the product domain bound, the host reproduces the native failure; the carrier string stays EQ-identical natively (the reviewer's EQ hypothesis was wrong, the dotted tail was the cause) | `build/minibuffer-native-attribution-full/report.md` | Every IDE/editor host suite binds the product's Tier-1 list domain (the permissive form is the failing mutation); assumption-inventory member: host harnesses that substitute permissive primitives |
| **Instrument gap: the IDE host per-key lane measured a path that is not the product's (3,542 VM ops on the host against 5,881 executed natively for the same key) (found 2026-09-13, minibuffer r3 attribution)** | The host harness enters the minibuffer through `ide-step`/`ide-render` directly, while the product runs `%ide-poll` → drain → render through the input owner; the call count per key was therefore invisible: r3 makes 535 CALL/TAILCALL per key against 234 on 2.2.0, 626 code materializations against 298, and 76 % of the extra native instructions are code resolution, refill and the shared MAP reader. Same class as the native-prompt lanes before witnessed readiness | `build/minibuffer-r3-key-attribution/report.md` | The IDE host lane enters through the product's poll path and reports CALL/TAILCALL and materialization counts per key beside VM ops; a call-count budget per key becomes a gate of any editor card (2.2.0's 234 as the ceiling until the cache card changes the price) |
| **`scr_put_at` comment contradicts its code for the reverse bit (found 2026-09-09, repair prep)** | `src/screen.c` says attr < 0 leaves colour AND RVS untouched; the code builds the screen code unconditionally from `to_screen(c)`, so attr < 0 clears bit 7. Harmless for read-line (attr is only 1 or 129); the host oracle mirrors the code, not the comment | `src/screen.c:172-183`; `docs/planning/wrap-backspace-repair-prep.md` §by-catch | Comment fix rides the next card that touches `screen.c`; if a caller ever relies on attr < 0 preserving RVS, that is the defect, not this note |
| **`v210-bundle-docs-check` pins the released v2.1.0 source world through `config/c2-v210-renderer-profile.txt` but asserts only one of its three files (found 2026-09-09, R2 assembly)** | The profile pins `src/eval.c`, `src/vm.c` and `src/interrupt.c` of the released world; the gate reds on `eval.c` (the `gc-root-bound` change) yet was silent while `vm.c` drifted through the A and diet cards. A released-world pin belongs to its era, not to the moving working branch | `mk/` target `v210-bundle-docs-check`; `config/c2-v210-renderer-profile.txt`; `r2-card-prep.md` §by-catch 2 | Era-bind the gate to the v2.1.0 release commit (read the pinned files there), and assert all three or none; composed tool member of the R2 card, not a product-round re-derivation |
| **Owner commission: ship every successfully built library package on the release medium (owner word 2026-09-09)** | The 2.1.0 product D81 carries only `ide`, `idex`, `m65d`; `buffer`, `place` (`setf`/`push`/`pop`/`incf`/`decf`), `string-extra`, `inspect`, `defstruct` exist as modules and pass the host suites but are on no release medium since 1.6.0. Owner: this was never released as a descope; everything successfully built ships unless the disk is full. The register's older "parity library pricing (Bank 2, hole 12,963)" item is absorbed here | `docs/known-issues.md` §Optional library packages; `docs/user-guide.md` §Product-resident libraries; `lib/` modules | Card after R2 ("library delivery"): (1) derive why each package left the medium (capacity, dialect, or omission) before anything else; (2) build each under dialect V2; every package goes on the product D81 (no product bytes; media only) with a load row per package on host and one device session; (3) the `load-lib` footprint of each package against the Bank-2 arena is a User Guide figure (what loads alongside what), not a delivery condition: a package that does not fit alone is a defect to repair, never a reason to omit it; (4) User Guide and Known Issues rewritten. Standing rule from the owner's word: delivery is the default for everything built and verified; any omission from a release medium needs the owner's word, not the other way round. Public surface: owner sees the wording |
| **Owner commission (2026-09-09): assumption inventory and edge worlds, so that implicit limits fail loudly before a rebuild finds them** | The week's four latent defects share one form: a numeric or placement assumption never written as a contract (index fits one sector; a cell lands in zero page; the allocator ends before the carrier; the facade is 98 bytes). Code reading cannot see them; they exist only in the built artifact | This register's rows of 2026-09-08/09; `lisp65-audit-verification-rule` (source ≠ product) | Card after the R2 release, host-only, three parts: (1) **assumption inventory**: derive every implicit numeric limit in `lib/` and `src/` and make each either a derived, asserted contract or a written one, with the failing mutation; (2) **edge worlds**: generated media and worlds at the edges (1/4/8/20 libraries, multi-sector index, user code at the Bank-2 front, symbol table at its last slot) as property rows in the release check, on the host D81 model; (3) **ownership watchdog** in the DWX fork: write traps on every owner boundary (carrier, ZP slot, E000 holes) while the suites run, as a tool patch in parallel. Owner priority: it moves finds from rebuilds to checks |
| **Latent: ordinary zero page may grow over the two DMA completion flags without a link error (found 2026-09-11, assumption inventory; reviewer-verified on the 2.2.0 map)** | `.lisp65_c2_convergence_zp` holds `c2_dma_verify_done` at `$87` and `c2_edma_probe_done` at `$88` (`src/c2_platform_dma.c:33`); the link assertion only requires `ADDR(.zp)+SIZEOF(.zp) <= 0x89` and the product links with `--no-check-sections` (`c2_product_substitution_link.py:1326`), so one or two more bytes of ordinary zero page would overlap the flags silently; headroom today 0 | `docs/planning/assumption-inventory-1.md` §2 item 1; release map lines 555-559 | Assertion A1: the `.zp` bound derived from the convergence owner's start, with a mutation; rides the next product link (byte-identical expected); a host check over the release map guards until then |
| **Latent: three more fixed hardware-stack offset sites of the retirement-guard kind (found 2026-09-11)** | The symbol-22 fault latch assumes `intern` pushes exactly 4 bytes (the storage-owner card changes `intern`); the MAP selector identifies its two callers by return offsets `+$4B`/`+$B0`, checked only by a v2.1-era selftest; the BRK classifier assumes the IRQ handler pushes exactly 4 bytes. Each holds by coincidence today | same report §2 item 4 | Host gates A4–A6 over the linked ELF before the storage-owner card; the storage-owner card re-derives the latch offset or gives it a descriptor as the retirement repair did |
| **C2D resolutions at 87.4 % with all five packages loaded; exhaustion makes `require` return `nil`, indistinguishable from not found (found 2026-09-11)** | 516 of 4,096 free. Silent failure mode | same report §2 item 3 | Host gate A10 (budget check); the INIT repair card gives `require` a distinct error for resolution exhaustion |
| **Latent: the disk window ends exactly at `0x10000` and nothing asserts it; growth wraps the 16-bit offset into the EXT cell heap (found 2026-09-11)** | Headroom 0 | same report §2 item 5 | Assertion A2 (`#error`), rides the next product link |
| **Corrections from the assumption inventory (2026-09-11)** | (1) The unguarded GC root push row is fixed in the release (`GC_CAN_RESERVE`, R2 card). (2) `dir`'s read-failure branch returns a partial list, not `nil`. (3) The 2.2.0 link report's bank-0 BSS headroom of 1,177 is measured to the wrong owner; the real figure is 164. (4) The ABI gate labels two linked files not-linked. (5) `bank-inventory.md` and `e000-resident-inventory.md` describe the R2 world, not 2.2.0. (6) The host D81 model holds only the first 8 directory files, truncates names to 16 characters and accepts only track/sector (1,2) for `load-file`/`load-lib`, so host results on multi-library or long-name worlds are silent, not negative | same report §by-catch | (1)–(5) corrected in their documents by the next card touching them; (6) resolved on branch `host-d81-model-widening@4f8f4bef` (1581 geometry, chains from any start, named-sector read failures, 38,400-byte limit, edge-world generator with 42 presets); Codex lands it with the Q-gate receipt successor, since `bytecode_p0.py` is SHA-pinned |
| **Owner goal: all optional packages loadable together without friction (owner word 2026-09-09)** | Today the Bank-2 arena is one region shared by the stdlib, the prompt editor and every loaded package, largest hole under 13 KB. The goal is that a user can load many or all optional packages at once. Correction 2026-09-09 (library delivery prep): loaded disk libraries are placed in bank 5 between the stdlib blob end and `SYMPOOL_EXT_OFF=0xc680`, measured post-load headroom 18,303 bytes; the 12,963-byte figure is the native `$2xxxx` hole of card 2b and is NOT a `load-lib` budget. Second correction 2026-09-09 (Codex, `library-authority-halt.md`): the `VM_DIR_MAX=608` directory is legacy code excluded from the product; the consumed VM takes the C2D branch (`vm_dir_capacity()` 2048), and the current Plane already holds 761 entries in six images. The prep's directory analysis was made against source not in the product (audit-rule class: source ≠ product). The real load constraints are the live C2D entries, roots, resolutions, append high-watermarks and physical carrier capacity; the library card prices against those owners, with no `VM_DIR_MAX` change | Capacity card 2b (`capacity-disk-window-card2b-report.md`); library delivery card (footprint per package under dialect V2) | Measured by the library delivery card; then priced as a Bank-2 carrier card after R2 and before the Comfort hand-over, so the number is on the table for the next feature-release decision. No feasibility doubt; a sequencing item |
| **Host D81 model loads one library per image (found 2026-09-09, library delivery prep)** | `bytecode_p0.py` prim 18 accepts only track/sector (1,2), so a host case cannot load two packages into one world; the goal "all optional packages loadable together" has no host evidence path until the model is widened. Pinned by a suite row expecting `nil` that fails loudly once widened | `tests/bytecode/libs/p0-stdlib-optional-packages.json`; `library-delivery-prep.md` §7 | Tool member of the library delivery card: widen the model to several libraries per image, mirroring the product loader's placement, with a multi-load host row |
| **Naming trap: `strings-extra` (STRX trim helpers) vs `string-extra` (capitalize/string-split) (found 2026-09-09)** | Only `strings-extra` has Makefile artifact and `-d81` targets; the owner's package is `string-extra` (`p0-string-extra.json`). One letter apart; a media change using the wrong name would ship the wrong library | `library-delivery-prep.md` §6; Makefile targets | The library card's media config names `p0-string-extra.json` explicitly and a selftest asserts both names resolve to distinct artifacts |
| **Owner currency: user-program headroom, measured per release (owner word 2026-09-09; 2026-09-09 library pricing: all five packages need ≥ 757 symbols / 10,839 name bytes against 752 / 10,208, deficit 5 slots / 631 bytes before any user program; symbol and name storage is the wall, not C2D or code space; R2 world measured at the smoke/D5 stop without packages: 106 free symbols, 1,458 free name bytes, 1,286 C2D entries; library world with all five packages loaded by hand: 32 free symbols, 384 name bytes, 8,593 user-code bytes — the release figure)** | User code is Bank-2 bytecode and draws on the same pools as the libraries. Current product (bound profile, D5 of the A/£/wrap session): code directory 608 slots / 399 used / 209 free; interned symbols 752 / 107 free; name pool 10,208 bytes / 1,467 free; Bank-2 arena largest hole under 13 KB. The kernel rebuild (A, diet, R2) frees Bank-0 text and the hardware stack, not these pools; R2 raises user recursion depth 13 → 16 with a clean error. Symbols are the tightest pool: every user function, global and keyword interns one, and each loaded package subtracts (`defstruct` accessors especially) | `config/c2-lite-public-build-authority.json` (`MAX_SYM=752`, `NAMEPOOL=10208`, `VM_DIR_MAX=608`); `docs/user-guide.md` D5 line; stdlib manifest `objects: 399` | Reported per release next to the text reserve: free symbols, name bytes, directory slots, Bank-2 hole, each measured with every optional package loaded; the symbol-economy study is commissioned after the library delivery card (which yields the packages' symbol cost) |
| **Stale symbol-store constants: `config/workbench.mk:261-263`, `c2_product_substitution_link.py:4160` and several tools still state 752 symbols / 10,208 name bytes; the 2.2.0 product has 795 / 11,293 (found 2026-09-11, storage-owner prep)** | Layout (a) of the library card grew the store by 2 + 4 slots and the pool; the literal copies were not derived. Same class as the facade's 98-byte literal | `docs/planning/storage-owner-prep.md` §by-catch | Storage-owner card derives every copy from `symbol.o`/the link map, with a drift mutation; member of the assumption inventory |
| **The bank-1 user/graphics reservation is a documented contract, not a protection: `poke` can drive the DMA registers and write any bank, including the symbol store (found 2026-09-11)** | Same as bank 5 today. The 48 KB / 16 KB split in bank 1 is enforced only by documentation; a user program that DMA-writes into `$1C000..$1FFFF` corrupts the name pool | same report | User Guide states the reserved range with the storage-owner card; a DMA-register guard is out of scope and not planned |
| **The MAP reader's admitted-region list (`c2_v21_map_mask_fix.py:43-47`) does not cover the bank-5 symbol region or the bank-2 function cells that 2.2.0 reads (found 2026-09-11)** | The reviewer's subagent found no check that admits those regions; either another check does it or 2.2.0 reads outside the admitted list without a gate | same report | First task of the storage-owner card: find the check or add the regions with their failing mutation |
| **Eleven-cell matcher fixture costs 904 → 932 VM steps under the wrap source (found 2026-09-08, historical Block3 hot-path check)** | The historical check's raw fixture (not the selected nine-cell product population) rises 3.1 % against its unchanged 913 ceiling with the line-wrap editor; the check now consumes its sealed pre-wrap source world and passes. The final packed world's own lanes (VM 1.0013× single / 0.952× batch; native 1.001× / 0.982×) stay authoritative. Recorded as a cost signal on a fixture, not a defect | `docs/planning/line-wrap-product-report.md` §Seven attributed consumers | Read together with the linear per-key cost row when the native prompt path is attributed for owner priority 2 |

## Startup feedback observation — 2026-09-14

| Item | Observed scope | Evidence | Disposition |
|---|---|---|---|
| **CLOSED: startup feedback after INIT echo suppression** | The released 2.3.0 medium `d98e6d75…` has a silent blue interval before the banner. Alex subsequently confirmed the German-message mechanism on `7c6b9e80…`, but identified its language inconsistency. That observation is not acceptance of the English replacement | Original `docs/planning/init-echo-device-report.md`; German `build/startup-feedback-device-r1/mechanism-seal.json`; current `docs/planning/startup-feedback-english-final-report.md` | `1a90f6a1`, source `9ea4e872`: English `Initializing...`, 17-byte data object, final medium `0d42ec5e…`, total 3/2/2. All Host gates and full write-neutral check-source pass, text 2,265/32, currency 32/387. Fresh English coldboot passed on 2026-09-15: owner confirms message visible, fully removed by banner, live prompt, no package echo. `docs/planning/startup-feedback-english-device-report.md`, seal `cbffbade…`; owner observation, pre-use readback only, no inherited German acceptance |
| **CLOSED: German relay wording in an English product** | `Initialisiere...` was bound literally from the German relay, despite an otherwise English product surface. The owner identified the inconsistency after confirming the mechanism at the device | `1a90f6a1`; `build/startup-feedback-device-r1/mechanism-seal.json`; `docs/planning/startup-feedback-english-final-report.md` | Replaced by `Initializing...`; compiled exact-screen control rejects the German wording. Standing review rule: product strings are checked for English before binding. Old German mechanism proof retained; English coldboot passed separately on 2026-09-15, `docs/planning/startup-feedback-english-device-report.md`, seal `cbffbade…` |

## Native diet and placement — 2026-09-20

| Item | Observed scope | Evidence | Disposition |
|---|---|---|---|
| **`ov_crc16`: the last bitwise CRC-16/CCITT-FALSE copy beside the proven leaf, 78 resident text bytes** | The diet card left it untouched because the assembler-leaf ABI gate binds its boot-chain call site (`jsr ov_crc16` with local pointer/length), and the commit leaf must call it exactly once. Pointing the symbol at `rtov_crc_mem` would recover about 75 bytes | `docs/planning/native-diet-placement-final-report.md`; `tools/host-lisp/c2_asm_leaf_abi_gate.py:393-433`; seal `native-diet-placement-final.json` | Next diet candidate, and the first one to reach for if a card needs 25 more bytes: it touches two gate contracts (the commit-leaf call identity and the CRC caller inventory), so it needs its own pre-qualification before a Seed |
| **Boot-only resident text: `vm_install_staged_boot_overlay` (467) and `vm_runtime_overlay_install_island` (211)** | A relocation-based call graph over the accepted ELF shows these two as the only resident functions reached from `main` alone and never after the prompt; `repl` and everything it calls stay live. Moving them into a boot carrier is blocked on an entry/return ownership plan, since the first installs the overlay it would live in and the second is a step of the verified boot chain | same report §Findings; method binding `229733f5` | Own card with the proven entry/return ownership plan; the static evidence is on file and needs no repetition |
| **The nibble CRC32 costs more cycles than the bit loop it replaces** | Boot ledger on the card's world: `crc32_update` 2.163 → 2.625 s. The overlay aggregate drops 0.50 s because `shelf_crc32` became phase-local, so the whole boot still ends 0.15 s earlier. The table form is a text trade, never a boot optimization | seal `native-diet-placement-final.json` §boot_ledger; `docs/planning/boot-ledger-set-a-report.md` | If a later card wants those cycles back, price a byte-plane form against the text it costs; do not cite the nibble table as a boot gain |
| **The delivery stager derivation predates the stager CRC32 card** | The media chain inherited from the INIT-echo card derives its stager source without that card's one-function delta, so the first pack of this card's medium carried the old bit-loop stager | `docs/planning/native-diet-placement-final-report.md` §Findings; `tools/host-lisp/native_diet_seed_media.py` | Every card using this media chain applies the delta and asserts byte-identity with `build/stager-crc32-r2/stager-main.c`, as this card's adapter does; a shared media helper would remove the repetition |
| **Append name search stays parked, now with the diet's outcome** | The full transient index needed 2,204–2,300 text bytes against the reserve; the diet recovered 575, so the reserve is 1,805 with a 32-byte floor. The per-append cache (982 bytes for 1.97 s on `inspect`) is affordable again on paper | `docs/planning/append-local-index-pricing.md`; this card's price | Re-decide after the boot-time name index card (owner word 2026-09-19), whose measurement covers the same mechanism |

## Boot-time name index — 2026-09-20

| Item | Observed scope | Evidence | Disposition |
|---|---|---|---|
| **Export publication interns linearly after the decoder: ≈ 500 names, ≈ 2.6 s of the boot's 9.8 s name-resolution cost** | The boot census (2,071 phase-8 requests, 10.5 s) mixes two populations: the decoder's phase 10 (1,564 kind-5/8 records over six images, ≈ 7.2 s) and the sliced append publication's plan-resolve (the last census names are exported function names). The index card covers only the decoder; the publication runs inside the validate-before-mutate publish structure and stays linear | `build/boot-name-index-admission-r1/receipt.json`; `build/native-diet-intern-census-r1/capture-r1/intern.txt`; plan entry 2026-09-20 (index card bound) | Follow-up after the index card: price extending the index's validity to the whole boot world preparation so plan-resolve can use it, against the publish structure's own contract; not silently folded into the index card |
| **Overlay catalog full: the index card takes slots 63 and 64 of 64** | The diet world uses 62; shape C adds slices `10a` and `10b`. No slot remains for the code-object cache, the far-reader island or Set B; the catalog capacity (`LISP65_RUNTIME_OVERLAY_HARD_MAX_SLICES`) is now a wall | `tools/host-lisp/c2_product_substitution_link.py` `C2_DECODER_SLICES`; `runtime_overlay_bank.py` | Capacity item: any later card needing a slice must state the slot in its preflight; growing the catalog is its own placement question |
| **Bank-5 free tail re-bound: 8,576 → 374 by the index card** | The storage card's floor protected that card's gain; no resident consumer owns the tail. The index card declares an 8,192-byte transient owner (index 2,048 + queue 6,144 + 10-byte resume header) that is live only during boot decode | `config/storage-owner-manifest.json` `floors.bank5_free`; plan entry 2026-09-20 | Set B (retirement carrier) re-binds again from 384 with its own owner plan; the transient owner must be disjoint-asserted against the three symbol tables and swept by the transport gate |
| **Session overlay bank full: region 0 at 64,558 of 65,536 bytes before the index card's two slices** | 49 Session slices sum to 57,622 bytes; the 256-byte payload alignment adds ≈ 5.1 KB; region 1 (Bank-5 overflow, 2,032) has 76 bytes free and region 2 (card2b store, 1,622) 872. Slices `10a` (1,671) and `10b` (1,755) overflow region 0 by 2,779 bytes plus alignment. The boot family's 45 KB are unusable: it is dead after phase 3 and `vm_runtime_overlay_select_family` refuses to return to it | `build/native-diet-seed-medium-r5/materialized/runtime-overlays-session-final.json`; `build/boot-name-index-product-r4/wplto/`; medium log of 2026-09-21 (`bank-overflow … c2-decode-10a exceeds L65R region 0 capacity 65536`) | Owner word 2026-09-21: capacity card first, bound the same day (payload alignment 32 for Session slices, catalog end 256, boot family untouched, budget 1/1/1 on the diet world; 128 → −384, 64 → +896, 32 → +1,888 free with 55 slices), then the index card resumes with 1/1/1 on that world. The alignment is a format pin (`runtime_overlay_bank.py`, manifest policy, loader page rounding), so the capacity card carries its own preflight of every consumer |
| **Preflight gap: slice cards must state payload capacity, not only catalog slots** | The index preflight registered the catalog (64 of 64) and never summed the Session bank's payload; four Seeds later the packer found the wall. The r4 world is otherwise green: price +705, both slices under the cap, fixed-facade gate passed | plan entry 2026-09-21; `docs/planning/boot-name-index-interim-report.md` | Standing rule for every card that adds a slice: preflight prints region 0/1/2 free bytes after alignment for the intended family, alongside the slot |
| **Session bank capacity recovered: alignment 32 leaves 5,362 bytes free in region 0 on the diet world (≈ 1,890 after the index card's two slices)** | The capacity card (authority `0ed9e98d`, one Seed, one Final) moved the Session per-slice payload alignment to 32; catalog end and boot family stay at 256. No text, floor, boot or lane price; GC +5 cycles warmup. Nine `check-source` consumers converted without product change | `docs/planning/session-bank-capacity-final-report.md`; seal `session-bank-alignment-final.json` | Capacity watch: every later Session slice states the region-0 free bytes after alignment 32; the index card's Seed 5 records the first figure |
| **Cards on a shared tree carry each other's sources** | The capacity card found the parked index card's `symbol.c` and manifest floor in the tree but not in the accepted world; the export is now feature-bound (`0ed9e98d`), the floor carried and gated (`linker-floor-carried.json`) | same report §Findings; `tools/host-lisp/session_bank_alignment_producer.py` `PRIOR_BASE` | Standing rule: every tree change since the accepted world that is not the card's own is listed, gated and priced in the producer |
| **Boot-time name index closed: cold boot −6.7 s; Session region 0 keeps 1,893 bytes, catalog 63 of 64** | Shape C on the capacity world: decoder segment 25.11 → 18.39 s, publication 11.77 → 11.79 s, text +705, E000 +196; GC at equal state +0.09 % cycles with identical live cells, collector untouched | `docs/planning/boot-name-index-final-report.md`; seal `boot-name-index-final.json` | Capacity watch: the next Session slice must fit 1,893 bytes at alignment 32 and take the last unique slot; the GC cycle delta is a stated finding for the next card that moves resident text |
| **GC at equal state drifts with resident layout, not with GC code** | +4,964 warmup / +4,819 forced cycles on the index world at identical 532 / 501 live cells; the card touches no collector code; the diet card's repetition spread was ±110 | seal `boot-name-index-final.json` §gc_equal_state; `build/gc-layout-drift-r1/report.md` (collector bytes identical modulo relocation; delta ∝ live cells; static page-cross count fell) | Before the next resident-text card, measure GC against a layout-only control (same bytes, moved) to separate layout from code; until then the GC gate reads "state equal, cycles stated" |
| **Export publication resolves through the index: cold boot −2.1 s; region 0 keeps 1,253 bytes** | Read-only form (hash, seam read, full-name confirmation; misses linear): 423 hits / 84 misses over 507 names, tables byte-identical; text +9, resolve slice 1,376 of 1,792, region 0 +640 | `docs/planning/export-publication-final-report.md`; seal `export-publication-final.json` | Capacity watch: the next Session slice fits 1,253 bytes at alignment 32 and takes the last unique slot; the remaining ≈ 0.3 s (84 misses) needs the put/catch-up kit resident, priced against the text reserve |
| **Segment gates are named from the boundary table, not from the census position** | The export card's binding put its gate on `initializing-emit`; the ledger placed the publication inside the island segment (18.39 → 16.28 s) with `initializing-emit` unchanged | `build/export-publication-boot-ledger-r1/capture-r1/analysis.json` | Standing rule for boot-time cards: locate the member's boundary pair in `analysis.json` of the predecessor capture before binding a segment gate |
| **Slice registration is link-tool runtime, not world state** | The export producer inherited a world whose linker script carried the index records, but the tool's catalog starts from its own pre-index population; the first Seed halted at the section inventory | `build/export-publication-r1/slice-registration.json`; Seed 1 world `build/export-publication-product-r1` | Every producer on a world with `10a`/`10b` calls the registration and proves the slots against the product header before its Seed; the capacity preflight tool reports the catalog from the medium, not from the tool |
| **`ov_crc16` retired: 78 resident text bytes recovered, reserve 1,169** | Both callers reach the proven leaf directly; wrapper form refused by the ABI gate (tail `jmp`); the leaf's caller inventory now holds fourteen direct edges; no boot claim for the leaf | `docs/planning/ov-crc16-final-report.md`; seal `ov-crc16-final.json` | Register row of the diet card closed; the next air candidates are the boot-only resident text (678 bytes, entry/return ownership plan) and nothing smaller is left in the CRC family |

## Post-descope capacity watch

Re-derived on 2026-08-25 from the exact linked ELF published as v1.6.0
(`82bc474e…`), its item-1 candidate receipt, and the D5 result — never from a
Comfort or witness predecessor:

| Currency | Current selected-product result |
|---|---:|
| Free interned symbol slots | 105 |
| Free name-pool bytes | 1,413 |
| Ordinary Bank-0 text | 273 bytes free |
| Mapped far-service arena | 11 of 1,499 bytes free |
| E000 total / largest contiguous hole | 195 / 159 bytes |
| Mapped product-cold arena | 47 of 371 bytes free |
| Diagnostic arena | absent from the selected product |

Aggregate free space is not placement capacity: an indivisible tenant prices
against the largest suitable hole. The symbol-economy study is consequently
optional rather than urgent, while far-service remains the thinnest current
arena.

Owner SD-card note after publication: retain the released
`lisp65-product.d81`, `lisp65-library.d81` and `lisp65-work.d81` set, plus
none of the v1.6 candidate or diagnostic images — **released set plus none**.

## Notes that belong with the list

- **Definitions pricing: missing native emitter bridge and masked local
  helper relocation (2026-09-17).** On accepted Retirement world
  `cd656ff9…`, native `compile-string` reports undefined `%c2-control`,
  then arithmetic returns 9. The consumed runtime calls its missing name
  instead of the implemented Prim 66. Behind that, the exact emitter C
  leaf emits a per-definition helper index without its group-image base;
  this second case is leaf-proven, not end-to-end native-proven yet.
  Neither candidate fix is landed; declared-group pricing holds for
  disposition. First affected release not attributed. See
  `docs/planning/definition-group-pricing-r2.md`.

- **Single publication versus sequential visibility (2026-09-17).**
  Pricing under `2a0abd35` executes a native mixed `progn`: define 5,
  call it, redefine 6, return the saved 5; the next call returns 6.
  Gathering all definitions before or after intervening evaluations is
  not equivalent. A generated definition group can use the existing
  multi-function emitter; arbitrary top-level atomic publication needs
  provisional sequential visibility and an explicit side-effect contract.
  No implementation or scope reduction assumed. Partial adapter price:
  137 native text bytes and 47 Bank-2 bytes, not the card's total price.
  See `docs/planning/definition-publication-pricing.md`.

- **Persistent retirement needs callable liveness, not just a rebound
  name (2026-09-17).** The native Definitions ledger reproduces 31.21 s
  for a five-slot structure, eighteen publications. A separately saved
  exact function cell remains callable after redefinition (old result 5,
  new result 6), as required by delivered trace/untrace restoration.
  Batch-image siblings also remain owners. Existing transient/overlay
  retirement is not a persistent image free-list; do not apply its suffix
  cleanup to a still-live old callable. Definitions card holds before
  implementation for explicit liveness/reuse scope and pricing; fifty
  unretained redefinitions remain the recommended constant-count gate.
  No product change. See `docs/planning/definition-path-ledger.md`.

- **Append name-resolution cost, executed (2026-09-16).** On accepted
  Retirement world `cd656ff9…`, inspect's native Append costs 5.037 seconds
  at 40.5 MHz; 3.315 seconds are decoder name resolution, including 39,933
  Bank-1 candidate-name reads. A four-bit saturated length prefilter leaves
  repeated full-name comparisons; publication resolution also repeats
  lookups. Buffer and defstruct cost 0.906 and 2.241 seconds. Each package
  publishes one image, with content-dependent work: this is not a uniform
  per-code-byte cost. CPU/IRQ/DMA accounting closes exactly; all package
  uses and old-code identity checks pass. No repair, lookup cache, BSS owner
  or relaxed verifier has been authorized by this measurement. See
  `docs/planning/append-native-cost-attribution.md`.

- **64-image attribution corrected and executed (2026-09-16).** The
  accepted world boots with 8 images; all five packages bring that to 11.
  Each complete five-slot structure adds 18 (3 + 3 per slot); 17 was the
  partial third structure at the limit, not a successful structure's cost.
  Redefinition consumes another image too. At 64/64 the rejected eighteenth
  definition leaves `storec-with-e` unbound; seventeen siblings remain.
  The native PC witness at $2818 identifies `c2_product_install` translating
  append refusal into `VM_BADOPCODE`. The prompt does return: arithmetic,
  an old accessor and a second refusal/recovery pass, with previous code
  bytes unchanged. This is a misleading capacity error plus partial
  compound publication, not a demonstrated dead prompt. Larger capacity
  needs pricing of the Bank-5 image records and their shared transient
  population; a clean resource error and compound-definition policy remain
  repair scope, not implemented by this attribution. See
  `docs/planning/image-capacity-attribution.md` and its native receipts.

- **Persistent image capacity during a third structure (2026-09-16).**
  An extra, uncommissioned stress probe after all five packages and IDE
  reaches persistent-image counts 11, 29, 47, then 64/64 while defining
  three five-slot structures. Both the unchanged Resolver predecessor and
  the transient-retirement fallback report `VM: BAD BYTECODE` at the third;
  17 images of that structure have been published, with 819 symbols used.
  Previously published code objects remain byteidentical. This is a
  pre-existing capacity observation, not a passed test or an established
  slot limit. Post-error recovery and multi-definition failure atomicity
  were not established by this stopped probe. Capacity reporting and
  partial-definition behavior need a separate disposition; no repair or
  capacity change is included in the fallback card. The bound two-structure
  workload already crosses 795 and passes with timed intern (802 symbols),
  accessor 42 and recovery 9. See
  `docs/planning/transient-retirement-final-report.md` and its sealed
  `storage-capacity-observation.json` input.

- **CRC resolver follow-ups (`2bc3960b`, 2026-09-15).** The accepted native
  CRC card spends 345 text bytes; its validated local/EXT CRC helper alone
  occupies 388. A smaller table-less implementation is a later diet
  candidate, not a change to the accepted Seed. The two retained CRC Cons
  states and their heap-layout effects cost 24,882 cycles per collection
  (0.614 ms at 40.5 MHz), fully attributed with unchanged collection code.
  Releasing those states after parsing belongs to the next resolver card,
  with both success and rejection paths proved and two retained cells as
  the expected gain. The remaining parser work and native append are
  separate measured optimization classes; this card does not claim to
  remove them. See `docs/planning/post-2.3.0-plan.md` and
  `build/index-crc-r1/gc-closure.json`.

- **Timed fresh package load can retain entries with erased code
  (Resolver world, 2026-09-16; product halt).** After fresh
  `(time (require "defstruct"))` returns `t`, 21 persistent entries
  remain but their 1,031 Bank-2 code bytes are zero. Temporary rollback
  reconstructs counts without replacing the shared scratch's last
  persistent code base/length, which the code-wipe phase consumes.
  Native execution rejects ordinal 835 at the object magic check, not
  argument-pop; one slot already fails. Plain loading passes two
  five-slot structures and accessor 42. No slot limit is established.
  The instrument checked `t` and unrelated arithmetic, not subsequent
  package use or retained code. Repair requires a bound scope/budget
  and a post-return package-use/code-preservation gate; no repair build
  is authorized by this finding. Physical `467 t` remains a return
  witness only; Storage beyond-795 is still open. See
  `docs/planning/resolver-timed-package-attribution.md` for evidence
  and the limits of the writer attribution.

- **Append name-bucket saturation (2026-09-16, measured cost, not a new
  correctness defect).** The source assumption that long-name collisions
  are rare is false for the accepted package population: 250 of 667 initial
  names saturate length4, and 41,120 of inspect's 42,736 name comparisons
  use that bucket. An unlimited zero-cost per-Append cache saves at most
  2.003 seconds, below the bound three-second target. Adding a nibble needs
  504 bytes against five spendable high-BSS bytes. Replacing length4 with
  hash4 is a separately priced encoding proposal, not an admitted product
  change; it also increases buffer comparisons. Native after-lane and cache
  lifetime proofs remain open. See
  `docs/planning/append-name-search-pricing.md` and its evidence seal.

  Admission update under `ee100e7e`: hash4 replacement fails the per-intern
  +30-percent comparison wall. On the same 667-name live table, 205 of 672
  host-executed queries fail, including `zq` at 45 versus 13 comparisons.
  Symbol results remain correct. This is a rejected performance form,
  not a product correctness defect; no product build was made. Full boot
  parity and native candidate timing remain open. See
  `docs/planning/append-name-hash-admission-halt.md`.

  Append-local pricing under `c1e15660`: the derived Bank-5 tail fits the
  index data, but the two full-index code sketches cost 2,300 / 2,204
  projected text bytes against reserve 1,459/32. Rebuilding the complete
  index for each of eighteen small definition Appends costs 1.775089 s in
  the native leaf projection, more than their entire old name-call cost of
  0.555790 s. A cheap package lookup is not automatically a cheap per-form
  installation. The narrower cache projects 982 text / 2,050 transient
  Bank-5 bytes, saves 1.973749 s on the inspect name sequence but adds
  14.104 ms on the eighteen-image sequence. Actual caller/abort wiring and
  full product lanes remain open; no product build. See
  `docs/planning/append-local-index-pricing.md` and its seal.

- **`compile-string` positive-path suite gap (2026-09-17).** The delivered
  private source-compiler bridge calls the missing `%c2-control` name instead
  of primitive 66. The documented positive example fails natively while
  arithmetic recovery returns 9. The Workbench subset suite
  `p0-stdlib-einsuite-core-workbench-subset.json` checks function presence and
  invalid source/destination arguments, not successful compilation, save,
  load, and execution. The C1 entry-seam inventory describes that route;
  its inventory check is not an executed native end-to-end witness. The
  Definitions card must supply that missing positive route and the old
  lowering as a falling control. The suite census must distinguish such
  presence/negative checks from product-profile execution; a host primitive
  66 stub cannot certify emission or publication. Binding `b6752d53` admits
  this prerequisite and the separately witnessed emitter helper-base fix.
  See `docs/planning/definition-group-pricing-r2.md`; native price and
  end-to-end repair acceptance remain open.

- **Prim-66 staged Buffer conversion bypasses its overlay transport
  (2026-09-17, native preflight halt).** Correcting the missing private
  lowering exposes a direct call from resident `vm_callprim` to
  `buf_from_stage` in the unloaded Buffer-allocation window. The native
  classifier captures zero window bytes and the matching caller return;
  the retired-window backstop supplies E3E. This is not a disk/CRC failure.
  Admission and pricing of the transport correction are pending; no Seed.
  The same consumed-call inventory also finds `%buffer-read` unresolved in
  `%c2-compile-save`, so the C2 bridge projection is four functions and
  minus five Bank-2 bytes. See
  `docs/planning/definition-compiler-bridge-halt.md`.

- **Persistent image reachability does not define reusable C2D topology
  (2026-09-17).** A product-domain execution of the real resolver over native
  C2D bytes accepts the original prefix but rejects removal/renumbering of
  a middle image while later code stays at its original address. Faking
  contiguous offsets passes that predicate but lies about the code owner;
  it is not a fix. The native entry scan likewise assumes a dense valid
  prefix. Slot reuse therefore needs an explicit representation contract
  covering resolver, entry handles, allocator, mark closure and rollback;
  the existing transient cleanup is not persistent retirement. No new
  product defect or fourth prerequisite is claimed. Pricing recommendation:
  keep live addresses and BCODE ordinals stable, represent dead entries
  explicitly, and report code holes separately from free image slots.
  See `docs/planning/definition-group-retirement-boundary.md`.
  Follow-up under `38644f6e`: `docs/planning/definition-retirement-pricing.md`
  records the non-callable-row native recovery witness and 105 host
  transaction cutpoints. The owner-reuse sketch is 4,113 code bytes before
  GC/adapters; its 2,723-byte recovery dependency group exceeds the 1,792-byte
  slice limit. Cold-carrier/phase placement is not yet granted or priced;
  no retirement is installed and no Seed consumed. Image slots and retired
  Directory ordinals are separate currencies; the sketch reuses only the
  former and keeps code gaps charged.
  Placement follow-up under `da42d6f5`: the consumed table end leaves
  8,672 bytes, but the retained manifest floor is 8,576, so only 96 are
  available for a new carrier. Core plus journal would leave 4,521,
  short by 4,055 before GC/control. The authorized split is selected:
  group publication and prerequisites first; persistent retirement next
  with a new placement plan. The redefinition limit remains in the first
  card. No floor is spent and no carrier replay is claimed. See
  `docs/planning/definition-retirement-placement.md`.
  Under `91cbb479`, Set B may explicitly rebind that historical Bank-5
  free-space floor with a declared cold carrier and a new measured floor;
  no resident consumer owns the tail. Set A remains separate. Its current
  +160 Bank-2-byte projection raises a different authority question:
  8,365 user-code bytes versus the manifest's 8,432. That value has not been
  silently rebound; see `docs/planning/definition-set-a-currency-preflight.md`.

- **Capacity is a candidate fact, not an inherited mood.** The post-descope
  product recovered substantial text and symbol room, but far-service remains
  thin and an indivisible tenant still needs a contiguous hole. Every future
  feature re-derives the currencies it actually consumes.
- **Two of these items are each other's instrument.** G3 needs target phase
  numbers; those need `room`; `room` is G1. Whoever reopens one should
  consider reopening both.
