# lisp65 1.1 Development Plan

Status: approved by Alex on 2026-07-15. This English document is the canonical
planning view; the original owner wording is retained in
`development-plan-1.1-2026-07-15.de.md`.

The 1.1 theme is language and IDE polish after structural capacity relief. The
on-device ship builder has moved to 1.2 and remains a committed product goal.

## Starting capacity

The measurement baseline is the published `v1.0.1` product set
`c41b9643ada1195f48c384d9d582a3d870a68c4ccc3dee9500dc86a7f009c165`
at private commit `471435024d86b1f535bfb4116551f37f307ca1f0`. Pre-wave probes may
materialize temporary builds, but do not alter or repin that product identity.

| Resource | Released baseline | Rule |
| --- | ---: | --- |
| Bank 0 | 332 bytes above the 1,536-byte target | debit only through block authorization |
| EXT | 16,385 bytes against a 16,384-byte floor | frozen; one byte is not spendable margin |
| Symbols | 120 free | tight for help and completion |
| Name pool | 2,160 bytes free | usable, but metadata must stay off-device where possible |
| Directory | 32 free entries | every new library must report its cost |

Capacity relief therefore precedes polish. Probe-first links and complete
capacity deltas remain mandatory for every block.

## Standing rules

1. The real differential link is the estimate.
2. Every block receipt reports Bank 0, EXT, symbols, name pool, and directory.
3. Capacity is spent only after block-specific authorization.
4. Every block must be independently integrable and safely pausable.
5. Dependency order remains: Directory-only/L65M v2 before export-only
   interning; first-class buffers before unload; export-only interning before
   unload.
6. New private `%` helpers must pass the normal classification gate.
7. Gate values state their evidence limits explicitly.
8. The curated public snapshot is synchronized at every release and at least
   every four weeks (owner decision 2026-07-15).
9. ~~A second-device or community tester as a hard prerequisite for the
   first product-SHA-bound wave hardware run~~ — **removed by owner decision
   2026-07-16 (not currently practicable).** Consequences: wave G6 runs rest
   on the single reference device, and every G6 claim carries
   "single-device" in its value string (claim hygiene). Partial substitute:
   the optional post-wave-2 beta puts real community hardware behind the
   seal instead of before it. Revisit trigger: a hardware-owning contributor
   appearing through the public repository makes S2 cheap to reinstate.

## Acceptance cadence

1.1 is delivered in three waves. Product-SHA-changing blocks receive complete
automated gates and reproducibility checks while being integrated; each wave
ends with one R4/R5/R6 repin and full applicable G6 hardware run.

**Process rule added 2026-07-18 ("fail fast, seal slow")** — after three
end-of-chain hardware finds (banner wiring, stager fuel, restart jump)
each forced a full chain rerun: (1) before every chain start, a short
**receipt-less, non-authoritative hardware pre-smoke** touches only the
behavioral surfaces that are new or changed in this cycle — it proves
nothing and replaces nothing; it only moves the cheapest possible failure
to the front, turning the chain from discoverer into confirmer; (2) every
hardware-only case gets a G5 **emulator dry-variant marked
non-authoritative** where the emulator plausibly models the mechanism
(never a substitute for the hardware claim); (3) within G6, **new cases
run first**, proven veterans last.

The previous sealed wave remains the product until the next wave is hardware-
green. Tag `v1.1.0` only after wave 3. A beta after wave 2 is optional if real
community testers need it. **Owner decision 2026-07-17: no `v1.1.0-alpha`
after the wave-1 seal** — the MEGA65 community is small, sealing costs real
time, and the owner prefers surprising with a feature-complete release;
development time wins over an interim release of unquantifiable benefit.

## Before the waves: IDE finding response (owner-approved 2026-07-15)

The confirmed 1.0 IDE finding (keyboard path loses modifiers; C-Space
structurally unreachable; documented M-x does not exist; sealed README-FIRST
never loads M65D/IDEX before the swap; compile fails on the blank work disk)
is handled in three stages:

1. **Immediate erratum (zero product bytes):** a known-issues section shipped
   with — not after — the public repository launch: M-x is really C-x x /
   C-x Return; IDEX dependencies; C-Space defective; compile requires a
   provisioned medium; load M65D and IDEX before the swap. Additionally:
   persistent compilation only targets prepared `fasl*` slots on the work
   medium, and `compile-string` currently lacks the M65D media-binding and
   transaction guarantees — avoid media changes while compiling. Publishing
   the old user-guide claims unchanged would break the §15c transparency
   commitments on day one.
2. **1.0.1-light (bundle repairs only; probe outcome 2026-07-15):** corrected
   README-FIRST (load M65D + IDEX before the swap), documentation and release
   notes. **No FASL slot provisioning and no product-code change.** The
   probe-gated Bank-0 guard came back red (+258 B overlay shift against a
   74 B window; receipt
   `…/post-release/product-media-write-guard-capacity-probe-receipt.json`,
   including the structural refutation of a cached-identity token bit: the
   native token holds only $D68B–$D68F, the identity latch is M65D-Lisp-side,
   and a Lisp-supplied authorization bit would not be trustworthy on a path
   that asserts its own authorization). Consequently slots stay out — without
   the guard, "slot missing" remains an accidental but effective barrier on
   the unguarded write path — and the trustworthy fix is the 1.1-M
   transaction seam. Acceptance scope: the 13 product artifacts stay
   byte-identical (set c41b9643…), so per the resume doctrine no new hardware
   power-cycles are required — deterministic R6/R7 repack, 13/13 identity
   gate against the existing seal, fresh static preflight against the changed
   package manifest, offline reverification and rebinding of the existing G6
   receipts, new package seal, tag v1.0.1.
3. **Structural rework in 1.1:** block 1.1-L (keyboard, wave 3) and block
   1.1-M (transactional FASL save, wave 2) below.
4. **`filter` delivery gap (measurement 8, 2026-07-15) — fixed and
   authorized 2026-07-16** (−91 B EXT, −3 symbols, −40 B name pool; Bank and
   overlay ±0 with byte-identical boot overlay; receipt
   `…/v11-filter-delivery-block-receipt.json`). Proven by four-engine list
   parity plus new direct/funcall/apply cases; the
   surface↔manifest↔reference **cross-parity gate is live** and also closes
   the `eval` public-surface drift. The erratum entry retires with the
   wave-1 seal.

Standing lesson recorded here: every documented key binding is a claim and
needs a bound proof. The user-guide keymap table must be generated from the
same source as the binding test list, so documentation can never again claim
more than is tested.

## Wave 1: structural relief

**Sealed 2026-07-17.** The accepted product set is
`e14de21a23823d70d90df0988a5424b436af89f1ebae21772950dcec7857549f`.
All five applicable G6 hardware cases passed on the single reference device;
the write-protect-only profile case remains not applicable. The self-contained
wave seal is
`tests/bytecode/dialect-v2/evidence/promotions/r6-g6-hardware-acceptance-d4bde68.tar.gz`
(SHA-256 `bf54360470945fa64911d2f53fba36dcd64b0563e9e9802deff317044e2940ca`).
Wave 2 work may now start; this paragraph records acceptance and does not
convert the planning document into a release claim.

### 1.1-A — Attic library shelf (implemented; capacity authorized 2026-07-15:
−49 B Bank / −26 B EXT, promotion clear)

The stager also places library FASLs in Attic RAM. `load-lib` reads them there,
removing the post-boot library disk dependency while remaining reset-persistent
and power-volatile.

- Keep the two-media persistence model unchanged.
- Verify the staged catalog by SHA.
- If the Attic catalog is absent or invalid, fail closed to the proven 1.0 disk
  path.
- Add a G6 case for reset between staging and `load-lib`.

Rationale corrected by pre-wave measurement 2: the shelf recovers **zero EXT
bytes** (it changes where libraries are read from, not where code resides).
The block stands on media ergonomics plus being the load mechanism for the
polish modules — not on EXT relief — and is compatible with either future
1.1-C cut (direct Attic execution presupposes libraries in Attic anyway).

### 1.1-B — Export-only interning (completed 2026-07-15: +45 symbols,
+742 B name pool, +25 B EXT recovered)

Intern only exported symbols; leave library-private functions anonymous.
Authorized basis is the measured floor of **45 symbols / 742 name-pool
bytes**. The 17 public-looking command/data names stay classified as
"public until revoked" and are re-evaluated after 1.1-L/1.1-J, when the
generated keymap and the SHA-bound shelf index can resolve command names
without interned symbols. Gate behavior parity for every loaded library and
record before/after watermarks.

### 1.1-E — First-class buffer and atomic string constructors (implemented;
capacity authorized 2026-07-15: −20 B Bank, EXT exactly neutral)

Review outcome: facade architecture accepted (46 B resident transport, ops in
runtime-overlay slices, helpers on the shelf); buffer print form withdrawn —
superseded 2026-07-16: there is no safe generic fallback (`T_BUF` hits the
printer's list branch), so a minimal safe print form or clean error is a
must-fix before the wave seal (see 1.1-C carried obligations);
L65S-v1→v2 strict jump approved solely because no sealed product ever shipped
L65S-v1. Carried into the C1 gate: measured compile-time before/after the cut
or a batched write seam (byte-wise `buffer-set!` has no performance claim for
the compiler path), and explicit overlay-headroom reporting (base $c350 is
6 B under the cap).

**Moved into wave 1 (2026-07-15) as the 1.1-C/C1 dependency** (the
compiler-tier cut needs the detached output buffer). Hard design condition at
zero EXT margin: **EXT-neutral** — native primitives resident in Bank 0,
all Lisp helpers as a shelf library (the mechanism 1.1-A just created). An
E that itself costs EXT bytes would deadlock the wave (E blocked → C1
blocked → no relief).

Introduce a DMA-suitable first-class buffer type and restore atomic string
construction without returning to heap-expensive workarounds.

- Preserve non-moving fixed-point collection semantics.
- Fail closed on OOM.
- Bind behavior to an independent host oracle.

### 1.1-C — Required EXT relief (C1 REOPENED 2026-07-16 after G5 findings;
wave 1 not sealable until resolved)

The wave-1 G5 run found two independent C1 product regressions and stopped
correctly at 0/14 (no case receipt, R4 historical evidence):

1. **Correctness:** `lcc-run`, `eval`, `eval-buffer`, `compile-string` fail
   nested (`*** vm: bad bytecode`; the later "undefined function" is a
   follow-on) because `vm_embed.c` categorically forbids C1 rollback during
   an active transient main — exactly the seams the memo listed as public
   entry points, none of which had its own gate case. Fix direction: allow
   rollback when the persistent region provably lies entirely below the
   transient area, with a permanent overlap gate. **The memo's seam list
   becomes the generated case list — one permanent hardware case per seam.**
2. **Runtime:** `load-lib "ide"` 6 s → 11 s (+83%, 1 s under the 12 s gate);
   the compiler is shelf-loaded and retired for practically every non-atomic
   REPL form. The existing C1 performance gate honestly claimed only the
   batched DMA seam; end-to-end REPL latency was unproven and is now
   measured. Plan: phase measurement (shelf transfer, commit, compile,
   retirement, installation), then a real REPL runtime gate against the
   1.0.1 hardware baseline. Candidate direction: deferred retirement
   (retire only before a foreign allocation needs the space — LIFO-safe,
   amortizes bursts like `load-lib` to one transfer).

Progress 2026-07-16: the correctness block is green on hardware (all four
entry seams, including the full `compile-string` write/reload/execute
round-trip; receipt `…/c1-entry-seam-hardware-receipt.json`, SHA 91ade19d…).
Bonus find fixed: the FASL-slot loader passed the whole 8,192 B chain to the
length-strict validator despite a 72 B container — trusted disk carriers are
now bound to the declared container length. Reopening deltas authorized:
−49 B Bank (288 B over target), −50 B overlay (**30 B headroom — the wave-3
1.1-L conflict, +68 B, is open again; no L start without a sourced overlay
plan**). Phase table (SHA b8f85114…): shelf transfer 20 ms, **L65M
preflight/commit 3.50 s**, compile 80 ms, retirement <20 ms, installation
320 ms. Next step: retention/lease prototype (amortizes repeats; LIFO-safe
"retire before foreign allocation") plus cold-path work — primary candidate
**validate-at-stage, trust-by-SHA**: full L65M validation once at staging,
commit of an unchanged SHA-verified shelf image takes a fast path, any SHA
mismatch falls back fail-closed to full validation. Rollback/C2 remains
premature until this lever is measured.

**Owner verdict 2026-07-16: the lease + SHA-fast-path candidate FAILS the
bar.** Hardware: cold 3 s, warm 2 s per non-atomic form, `load-lib` 6 s
(that half passed). 2–3 s per REPL expression is unacceptable for an
interactive product; the pending deltas (−22 B Bank, overlay 30→0 B,
+1,280 B runtime-overlay bank) are **withheld** — no capacity is spent on a
state that stays unacceptable. Open question to answer first: what exactly
composes the warm 2 s — hypothesis: LIFO forces retirement per `defun`
because result installation is itself a foreign allocation above the tier,
so the lease can never survive a definition. Three directions, in order of
preference: (1) decouple result installation from the tier region
(structural fix, measure first), (2) invert the default — compiler resident
as in 1.0.1, retirement only on explicit command or real EXT pressure
(requires reopened EXT arithmetic: floor must carry filter + banner + a
permanently resident compiler), (3) C1 rollback + C2 re-evaluation, now a
real option with known unwind costs. The correctness fix stays authorized
regardless.

**Performance reopening 2026-07-16: promotion suspended again.** The earlier
owner acceptance remains valid only for a definitions-free warm sequence:
**260 ms vs 200 ms resident-equivalent (+60 ms)**. It did not measure the
core developer loop after the definition had retired the compiler tier. The
exact owner sequence was repeated on Probe 11 (resident SHA `9a11fab4…`):
fresh `(+ 1 2)`, warm `(+ 1 2)`, `(defun test () 't)`, first `(test)`, second
`(test)`. Harness-inclusive timings remain diagnostic only. A frame counter
started after retirement and stopped after the first subsequent compile/call
measured **95 frames / 1.90 s**; the immediately following warm call measured
**10 frames / 0.20 s**. Receipt:
`…/v11-c1-definition-call-reopening-probe-receipt.json`.

The contradiction is resolved: the old 280-ms "next definition" probe began
inside an already compiled outer form and therefore excluded the top-level
compiler reload. The trusted-stage path does run after retirement, but it
skips only the L65M preflight. The generic commit still verifies, patches,
materializes and publishes the unchanged 9,420-B compiler image (663 patches,
144 directory entries); the earlier "reload <20 ms" claim incorrectly
confused compile-only time with the whole reload/commit. Trust has not expired
because of allocation history, so merely restoring its discriminator cannot
remove this cost.

The runtime gate now contains a separate generated
`definition → first call` case and fails closed until an owner-bound ceiling
exists. The previous −22 B Bank, overlay 30→0 B and +1,280 B runtime-overlay
capacity authorization is **suspended**, not promotable. Both already rejected
alternatives remain rejected (independent installation overlaps the fixed
overlay; resident compiler misses the EXT floor). The one authorized
identity-bound restore/cache probe has now also failed its capacity gate; the
choice therefore returns to the owner.

**Definition→call follow-up 2026-07-16 — measured, diagnosis closed:** on the
exact Probe-11 product the first call after a definition costs
95 frames = 1.90 s (following calls 10 frames = 0.20 s); the accepted 260 ms
claim covered only the definitions-free warm path. The phase contradiction is
resolved: trusted-stage skips preflight, but generic commit/patch/materialize/
publish remains. No acceptable ceiling has been set for this cycle.

**Definition→call cycle, resolved diagnosis (2026-07-16):** trusted-stage
skips only the L65M preflight; the generic commit still verifies and
publishes 9,420 B, 663 patches and 144 directory entries on every reload —
that is the 1.90 s. The earlier <20 ms figure described compile-only with a
loaded compiler. Capacity authorization suspended; permanent
definition→first-call hardware case added; the latency tool fails closed
until an owner-confirmed threshold exists.

**Bounded identity-restore probe — capacity-red and fully rolled back
(2026-07-16):** the single authorized attempt cached the validated/patched
compiler image and tried to restore it without the generic commit. A real
product link stopped first: `l65m-commit-00` grew 1,403→1,895 B against the
fixed 1,792-B slice limit; the C1 lifetime grew 1,728→1,908 B against the same
limit; and `l65m-commit-01` alone required another 512-B packed allocation
while the runtime-overlay bank had only 64 B free. The resident-island part
(1,531→1,637 B of 2,048 B) fit, but cannot make the complete design
admissible. Receipt:
`…/v11-c1-identity-restore-capacity-probe-receipt.json`.

The capacity gate correctly ran before hardware. Reset safety, repeated-cycle
leak freedom and the after-frame measurement are therefore **not run**, not
passed. All restore code was removed; a clean product relink passed and
restored the pre-probe section sizes (1,403/564/1,186/1,728 B), resident-island
payload (1,531 B), runtime-overlay image (65,472 B), resident PRG (39,561 B)
and preload (17,047 B). The rollback does not claim regeneration of the
historical Probe-11 SHAs: its live provenance inputs have changed since that
artifact, whose identity remains bound only by its historical receipt.

The bounded-attempt allowance is exhausted; there is no follow-on tuning
sweep. Promotion and capacity authorization remain suspended. **Owner decision
now required:** either (a) a dated exception that documents the 1.90-s first
call after a definition as a 1.1 limitation and commits C2 as the named 1.2
cure (an exception, not a moved performance bar), or (b) C1 rollback plus
immediate C2 replanning, including the known `filter` and banner unwind costs.

**DECISION 2026-07-16 (owner delegated to reviewer; both concur): dated
exception adopted.** The identity-restore probe came back capacity-red on
three independent budgets (l65m-commit slice 1,895/1,792 B, C1 lifetime
1,908/1,792 B, +512 B packed against 64 B runtime bank) and was fully rolled
back; all three fast-cycle designs are now exhaustively refuted at measured,
independent limits. The alternative — C1 rollback — would unwind 9.2 KB of
relief plus `filter` plus the banner and turn C2 into an emergency project.
Terms of the exception: (1) 1.90 s is never presented as a passed bar; the
latency gate carries "documented limitation, cure C2/1.2" in its value
string and attests stability, not acceptance. The initial 96-frame
quantization tolerance was superseded on 2026-07-17 by the owner-confirmed
**95..98-frame measured session band**: twelve consecutive definition/call
cycles yielded 95, 97, 95, 97, 96, 95, 96, 96, 98, 95, 98, 96 frames
(mean 96.17), with no demonstrated growth or plateau. This is a measured-band
correction, not an iteratively widened performance target: any value above 98
stops, the unexplained historical 110-frame observation remains visible but
does not widen the gate, and the documented user claim stays "approximately
1.90 s". The bound receipt is
`tests/bytecode/dialect-v2/evidence/r5/c1-definition-call-session-band-authorization-receipt.json`;
performance-bar=not-passed is unchanged; (2) the wave-seal user
documentation states the exact numbers (first call after a definition 1.90 s,
warm 0.20 s) plus the batching hint; (3) **C2 is hereby a committed 1.2
item** — the named cure, not a candidate; (4) the exception is dated: if C2
slips out of 1.2, it does not roll over silently but returns for owner
confirmation. Pre-promotion blocker: the `v11-c1-gate-check` stop in the
workbench differential (baseline cannot resolve `poke` in the directory)
must be explained — harness drift or real directory regression — before any
promotion.

**`poke` blocker closed 2026-07-16 — harness drift, product regression
refuted.** Exactly one live-baseline case failed: the new Wave-1 banner was
being executed in the historical profile, which correctly has no ABI-v2
`poke`. The product candidate supplies prim 62 through CALLPRIM, apply,
`function-kind` and compile-REPL; its banner case passes. Continuing the live
baseline also exposed a second drift: the source M65D suite already points at
the generated dialect-v2 resident suite, so IDE composition receives both old
and new resident definitions. Structural fix: the differential now consumes
the SHA-bound post-filter observation receipt as its immutable baseline and
enumerates the banner as the sole intentional addition. Result: 4 artifacts,
357 cases, zero differences. Receipt:
`…/v11-c1-poke-differential-diagnosis.json`. No product path changed.

**Integration capacity stop 2026-07-16 — closed by owner authorization.** After the
`poke` repair, the complete C1 gate reached the real final-profile link and
correctly stopped on resident-code drift. Compared with the sealed Wave-1 R4
candidate, the reopening adds **88 B persistent EXT**: `eval-runtime` grows
1,225→1,306 B (+81 B) for lease reuse, mandatory retirement before
persistent installation and the resident Buffer predicate; `stdlib-load-lib`
grows 413→420 B (+7 B) for the last-op retirement guard. The arithmetic is
exact: standard-composition headroom 25,161→25,073 B, leaving 8,689 B above
the 16-KiB floor. The same change removes the nonresident `bufferp` literal,
so the corrected runtime census gains one symbol and eight name-pool bytes;
directory stays unchanged. The already authorized Bank and overlay sums close
exactly (−49−22 = −71 B Bank; −50−30 = −80 B overlay). Receipt:
`…/v11-c1-wave1-integration-capacity-drift-receipt.json`. The owner authorized
the exact **−88 B EXT** debit on 2026-07-16; the binding authorization is
`config/v11-c1-wave1-integration-capacity-authorization.json`. The completed
integration gate is recorded in
`…/v11-c1-wave1-integration-block-receipt.json`: status
`passed-not-promoted`, EXT 25,073 B (8,689 B above the floor), Bank 1,802 B
(266 B above target), 298 free symbols, 4,602 name-pool bytes, 168 directory
entries, zero overlay headroom and 64 B runtime-overlay-bank headroom. Its
latency value remains `performance-bar=not-passed` with the dated C2/1.2
exception; the authorization does not relabel it as a pass. Promotion is now
free, subject to the regular R4/R5/R6 and fresh hardware chain.

**Fresh-clone determinism stop 2026-07-16 — structurally closed before R3.**
The first varied double-build attempt stopped inside its second clone because
the provisional runtime-overlay bootstrap installer and the final installer
first differed at byte 31. The provisional Sentinel header caused a different
whole-program spill choice: 1,765 B for the provisional installer versus
1,759 B for the final-header installer. That bootstrap link is not shipped and
exists only to derive the verifier header. A first attempted repair using a
second final-header link was also rejected: whole-program code generation is
not a stable byte-identity boundary across separate link invocations. The build
now separates the actual claims: the provisional link derives the header,
while the shipped 65,472-B overlay image and manifest must be the exact
reconstruction of all 44 slices from the one final product ELF, including slot
37's resident-island installer. The existing `header-mode verify` independently
rejects any packed verifier slice that differs from the header-generating link.
The corrected binding passes, then the C1 gate stops on the resulting profile
repin: the build-ID-dependent whole-program allocation grows slot 37 from
1,759 to 1,765 B, reducing its private 1,792-B slice margin from 33 to 27 B.
The fixed runtime-overlay image remains 65,472 B; its C1 lifetime slice retains
64 B. Bank 1,802 B, EXT 25,073 B, overlay 1,669 B/base headroom zero, symbols,
name pool and directory are unchanged. The owner authorized the exact six-byte
slice-headroom debit on 2026-07-16 and repinned the margin to 27 B. The live
gate consumes the dedicated authorization; future profile-build-ID movement
continues to stop rather than being hidden. If this becomes recurring noise in
Wave 2/3, a separately reviewed lower-bound tolerance may replace exact-byte
repinning, but no such tolerance is authorized here. Diagnosis:
`…/v11-c1-bootstrap-final-link-determinism-diagnosis.json`.

**Final-link allocation nondeterminism stop 2026-07-16 — the remaining
class is now structurally closed.** The subsequent R3 varied double-build
proved that the discarded second-link experiment had exposed a real product
problem rather than merely an unsuitable comparison boundary: repeated final
links with identical inputs alternated between 133,760- and 133,764-byte ELFs.
`vm_resident_island_install` let LLVM-MOS preserve its context and copy-target
pointers either in zero page or in anonymous `.noinit` storage. That choice
changed slot 37 by six bytes and therefore changed the product identity.

The installer now binds both cross-call values to the two already-existing
runtime call slots. Volatile installer-only accesses force reloads from those
named locations, while the mutually exclusive resident batch path keeps its
original non-volatile code shape. A permanent final-product gate requires the
named context symbol and rejects any anonymous `.noinit` byte. Eight forced
final relinks are byte-identical, the runtime-overlay host matrix remains
green, the resident-island payload remains 1,531 B, and the installer shrinks
from the owner-authorized 1,765 B to 1,743 B: headroom is corrected upward
from 27 to 49 B, a 22-B credit with no new debit. The canonical varied
fresh-clone double-build remains mandatory before R3 promotion. Diagnosis:
`…/v11-c1-final-link-allocation-determinism-diagnosis.json`; measured credit:
`config/v11-c1-final-link-allocation-determinism.json`.

**G5 chain-write lifetime stop 2026-07-16 — correction and capacity repins
owner-authorized, not yet promoted.** The fresh Wave-1 G5 run passed and bound five
of fourteen cases, then stopped without a case receipt when the exact 275-byte,
two-sector source fixture failed after its first evaluated top-level form with
`reader: unclosed list`. Disk mutation, links and independent D81 oracles were
correct. Hardware diagnostics found reader position 209/275 and the unread
`DISK_EXT_FILE` tail replaced by the C1 compiler container: `load_source_stream`
evaluates each form through resident `lcc-run`, whose compiler staging reused
the source scratch before the reader lifetime ended.

The correction streams one 1581 sector at a time through the disjoint 256-byte
directory scratch; the public 38,400-byte load ceiling is unchanged. A permanent
model reproduces the observed 209/275 replacement (shared scratch corrupts,
disjoint scratch remains byte-identical). The resident fetcher costs 137 B. In
the same probe, removal of duplicate installer context checks saves 110 B while
preserving the outer profile/build/ABI/source-CRC checks and the installer's
independent destination CRC. Net slot-37 cost is +27 B (1,743→1,770 B); actual
headroom is 49→22 B, or **27→22 B (−5 B)** against the latest owner pin. The
resident-island payload grows 1,531→1,668 B and its post-annex reserve falls
256→120 B. Bank improves by 103 B, and EXT, boot overlay, runtime-overlay bank,
symbols, name pool and directory are unchanged. Receipt:
`…/v11-c1-source-stream-lifetime-correction-probe-receipt.json`. The owner
authorized both exact repins on 2026-07-16; the binding artifact is
`config/v11-c1-source-stream-lifetime-capacity-authorization.json`. The island
is now watch-listed alongside overlay and the runtime-overlay bank: every future
capacity delta states its island delta, and 1.1-M must measure its island demand
explicitly. The product-SHA change requires the canonical varied fresh-clone
build and all fourteen G5 cases fresh.

**The optimization bar is set before optimizing** (owner-confirmed
2026-07-16):
`load-lib` within ~15% of the 1.0.1 baseline and no perceptible single-form
REPL latency. Decision context stated openly: a C1 rollback now also unwinds
`filter` (−91 B) and the banner (−376 B), both paid from C1 gains — the
realistic alternative relief would be pulling C2 forward. Correctness is
fixed first regardless.

C1 met the full memo gate: exactly 9,573 B excluded, 329 B named residual
control/result seam, peak budget proven (3,118 B headroom during temporary
load), batched DMA write seam, identical compile results, 10/10 lifecycle
cases, permanent gate `make v11-c1-gate-check`. **The EXT freeze is lifted**
— post-block margin is 9,244 B over the floor; normal per-block
authorization discipline applies again. Two carried obligations before the
wave seal:

1. **Buffer printing — fixed and authorized 2026-07-16** (−3 B Bank, −2 B
   overlay headroom; receipt `…/v11-buffer-printer-fix-probe-receipt.json`):
   buffers print as an opaque `?`, fail-closed; `T_BUF` can no longer reach
   the list printer. The richer `#<?>` form was rejected (+18 B overlay,
   gate violation) and remains a wave-3 candidate only if overlay relief
   lands. Wave-seal documentation duty: the language reference states the
   `?` print form and points to `buffer-ref`/`buffer-length`.
2. **Overlay is the new scarce currency:** 2 B base headroom after the
   printer fix (was 4 B after C1), while the 1.1-L pre-probe measured +68 B
   overlay. Overlay gets its own budget line and rule (like Bank/EXT); the
   remaining wave-1 blocks (`filter`, banner) must prove overlay neutrality
   in their receipts; and wave 3 needs a sourced plan for L's overlay bytes
   before authorization.

Ledger correction 2026-07-16 (authorized): the C1 closing check found the
validation asserted zero instead of the planned 53 symbols / 418 name-pool
bytes, alongside a stale disk-scratch address and an inconsistent symbol-name
limit — all three fixed. Hardware steady-state measurement (cold first form
→ 42, second identical call → zero further consumption) repins the ledger to
**297 free symbols / 4,594 B name pool**; Bank (337 B), EXT (25,161 B),
overlay (80 B, byte-identical) and directory (168) are unchanged. Product SHA
changes as expected; R4/R5/R6 rerun regularly. `screen-write-string` is
closed: optional dialect capability, explicitly excluded from the workbench
profile, replaced by `screen-bulk-p`, exception covered by the profile parity
gate, never promised by the published surface.

Original re-scope record follows.

The original premise (move stdlib tiers onto the shelf) recovers zero EXT
bytes and is void. The real levers are both large:

- (i) **compiler-tier deresidentization** (`lcc.lisp`, `lcc-fasl.lisp`,
  `lcc-profile.lisp`, exactly 9,573 code bytes) — requires a proven
  dependency cut, preferably over the existing overlay/staging machinery;
- (ii) **direct Attic execution / extended code addressing** (19,228 B
  potential) — an intervention in the innermost engine contract, classified
  pre-1.0 as "post-G6, large"; choosing it would change the character of 1.1
  from polish to architecture-plus-polish.

**Memo delivered 2026-07-15**
([v1.1-c-ext-relief-design-memo.md](v1.1-c-ext-relief-design-memo.md)):
recommendation **C1 (compiler-tier deresidentization, 9,573 B gross)**;
C2 (direct Attic execution) is deferred from 1.1 but, following the dated C1
latency exception, is a **committed 1.2 cure rather than a candidate**. Its
decisive problem is correctness (stale post-reset object bindings), not just
effort. Advisor and implementer concur; **the owner approved C1 on
2026-07-15**, bound by `config/v11-c1-architecture-decision.json`. Key
structural consequence: C1 depends on the detached-buffer
seam, so **1.1-E moves into wave 1** (see its EXT-neutrality condition), or a
non-EXT temporary execution window must be proved by prototype first. The
memo's authorization gate (exact 9,573-byte exclusion, named link deviations,
≥64 B post-block margin, zero compiler-private references after retirement,
identical compile results, fail-closed rollback) is adopted as the promotion
gate. Targets unchanged: at least 64 B margin, hard minimum 16 B before
unfreezing EXT.

**Capacity state after the authorized 1.1-A promotion (−49 B Bank,
−26 B EXT): EXT margin is exactly zero — absolute freeze.** The only next
EXT-touching act is the C1 transaction itself; this explicitly includes the
`filter` manifest fix (rides the wave-1 seal after C1, paid from its gains),
1.1-D and 1.1-M. Wave 1 cannot seal without a successful C1.

### 1.1-D — “λ LISP65” banner (probe authorized 2026-07-16: −351 B EXT,
−2 symbols, −25 B name pool, −8 directory; +81 B Bank, +80 B overlay)

Implemented per the approved [banner specification](repl-banner-spec-1.1.md)
with five accepted contract corrections (generator-bound ordinal seam — the
native REPL owns `scr_init()` and the first prompt; coordinate table over the
contradictory ASCII sketch; 235 real glyphs; ASCII hyphen pending a pinned
middle-dot mapping; boot overlay size-equal but not byte-identical from the
VMA shift). The bundled REPL type correction (byte-sized cursor/length/status,
build-time `REPL_BUF_MAX ≤ 255` guard) yields the +80 B overlay margin that
resolves the wave-3 1.1-L conflict (+68 B) ahead of time. Conditions carried:
the authorization artifact names why 8 directory entries and 2 symbols were
needed despite the spec's inline goal, and **the wave does not seal before
the hardware screenshot (visual acceptance) with the detector calibrated to
235 glyphs**; the spec file is updated with the corrections in the same pass.

Addendum 2026-07-16: the first hardware screenshot caught a real wiring gap —
the banner was in the product blob, but `repl.c` compiled the old fallback
(truth-source class again). Structural fix authorized (further −3 B Bank,
−2 B overlay → 337 B bank margin, 80 B overlay headroom, 1.1-L still fits
with 12 B to spare): banner declared mandatory, build aborts on a missing
ordinal, negative test with a bannerless header, disassembly proof. Diagnosis:
`…/v11-repl-banner-native-binding-diagnosis.json`. Screenshot to be repeated
after the fix lands.

### 1.1-K — Toolchain externalization (closes F9)

Status: completed on 2026-07-15. The manifest-fetched varied double build
reproduced all 13 sealed product artifacts (set `c41b9643…`); both exact
archives are stored under private tag `toolchain-v1.0.1` and were downloaded
again byte-identically. Receipts:
`…/post-release/toolchain-externalization-receipt.json` and
`…/post-release/toolchain-archive-mirror-receipt.json`. Product and hardware
identities are unchanged.

Owner request 2026-07-15: no third-party binaries in the curated public
repository. Publication already satisfies that boundary; this block makes the
separately installed LLVM-MOS and MEGA65 tool bundles reproducible instead of
environment-local. The first-party `tools/host-lisp/` sources remain in the
repository and are not part of the binary externalization. The principle is
identity over distribution: the evidence chain needs the exact third-party
toolchain to be *identifiable and retrievable*, not shipped alongside the
product.

- **In the repository, text only:** a toolchain manifest (per tool: upstream
  URL + commit, SHA-256 of the binaries, retrieval/build path) plus a
  fetch-and-verify script. Setup distinguishes an exact binary-SHA match from
  a source rebuild. A rebuild at the pinned source commit is usable for
  development, but it becomes proof-equivalent only after reproducing the
  sealed product SHAs; the source commit alone is not an identity claim.
- **Private binary archive:** today's `tools/llvm-mos/` and
  `tools/m65tools/` binaries become a release asset on the private mirror
  (like the evidence archives; never in git history). The binary SHAs are the
  primary pin ("these bytes"); the source commit is the weaker second line of
  defense, since an LLVM rebuild from the same commit is not guaranteed
  bit-identical.
- **Nothing is shipped publicly** (redistribution would be permitted by the
  licenses, but is unnecessary surface).
- Reference state: llvm-mos `c798c314…` from the R3/G3-G6 contract and the
  m65tools state from the R6 manifest. Host tooling remains bound through the
  repository commit and the existing product/evidence manifests.
- Classification: harness/process work; changes no product SHAs and needs no
  G6 share. It may run at any point during wave 1.
- Gate: a double build from a freshly manifest-fetched toolchain must
  reproduce the sealed product SHAs; only then may the private third-party
  binary directories leave the tree.
- Out of scope here: any toolchain *upgrade* (newer llvm-mos) remains its own
  block with a full acceptance cycle. The AUR/distrobox environment serves
  only upstream verification of the findings register (L1–L6), never the
  product build.

## Wave 2: language polish

**Wave-2 seal documentation duty (owner, 2026-07-17): document fixnum
semantics in the language reference** — 15-bit two's complement
(−16,384…+16,383, one tag bit of the 16-bit cell), all arithmetic silently
wraps modulo 2¹⁵, no overflow error by design (per-op checks are
unaffordable on the VM hot path; wraparound is deterministic and wanted for
mask/counter work; bignums and floats are deliberately excluded). Include
the factorial example — `(fac 8)` = 40,320 → 7,552 — verified live on
hardware by the owner; it is didactically exact because later values
multiply the already-wrapped predecessor. A BASIC migrant expects
`?OVERFLOW ERROR`; the reference must say why they get −8,448 instead.

### 1.1-F — `unload` — DEFERRED out of 1.1 (owner decision 2026-07-17)

Deferred on the import-stage-2 pattern: postponed until real usage demonstrably
demands it (public-repository feedback is the trigger). Rationale corrected by
owner decision 2026-07-18: the former leg (a), "a fresh session is cheap",
does **not** hold before C2 — platform Reset exits to BASIC and a fresh 1.1
session requires a product-disk restart. Deferral rests solely on (b) the C1 compiler
tier now being a LIFO tenant with lease/retirement mechanics, so general
`unload` would have to interlock with that machinery — a new interaction
class with real matrix cost; (c) the LIFO restriction confines practical use
to top-of-stack cases anyway. The contract pins ("buffers before unload,
interning before unload") were dependencies *for* unload, not an obligation
to ship it — both are satisfied if it returns. There is no replacement
primitive in 1.1; the documented recovery is save → product-disk restart → load.
`restart-repl` returns as named C2.3 freight after immutable code and mutable
session state are separated.
If unload returns later, the original scope stands: honest LIFO watermark
reclamation, a library unloads only when nothing sits above it.

### 1.1-M — Transactional FASL save (depends on 1.1-E)

**Re-scoped 2026-07-17 (owner-approved): composition over new machinery.**
Since wave 1, the pieces exist on both ends: C1 already compiles into a
detached buffer, and M65D already owns the full COW transaction with media
binding and denylist — it merely lacks a buffer payload. The preferred cut is
therefore: teach `m65d-save` to accept a buffer (library extension, financed
from EXT where the margin is, not from island/runtime bank where it is not),
route `compile-string` persistence through it, and retire the legacy
two-argument sector writer. The 600-byte decision avoided allocator/directory
commit costs that M65D has since become — shipped and hardware-proven.
**Commissioned: a comparison probe** (composition cut vs. dedicated
transaction seam) with island/runtime-bank deltas as the first criterion.

**Comparison probe complete and composition cut owner-approved (2026-07-17).** The real-link
receipt is
`tests/bytecode/dialect-v2/evidence/architecture-blocks/v11-m-transactional-fasl-comparison-probe-receipt.json`.
Both candidates pass the 38 existing M65D cases plus a Buffer save and invalid
payload case; the positive case is checked by the independent D81/BAM
witnesses. Both retire the nine legacy slot-writer functions, preserve the
compiler-tier image byte-for-byte, and leave the fixed overlay, 120-byte
resident-island reserve, reusable runtime-slice maximum, and 22-byte installer
slice reserve unchanged. Against the Wave-1 baseline, composition gains 727 B
post-load EXT, 10 symbols, 203 B Namepool, seven raw Directory entries and 8 B
Bank reserve. It also crosses one runtime-bank packing page, increasing bank
headroom from 64 to 320 B; the receipt attributes this to the smaller
boot-fastpath verifier after removal of the resident slot metadata. The
dedicated entry has no semantic advantage and costs, relative to composition,
45 B post-load EXT, one symbol, 17 B Namepool, one raw Directory entry, 119 B
of M65D container and the 256-byte packing credit. **Probe recommendation:
composition.** The probe remains historical `passed-not-promoted`; its selected
cut is now the implementation baseline.

**Canonical implementation complete; capacity repin owner-authorized
(2026-07-17).** Receipt:
`tests/bytecode/dialect-v2/evidence/architecture-blocks/v11-m-transactional-fasl-implementation-receipt.json`.
The implementation reproduces the selected probe exactly on every measured
capacity axis. It passes all 40 M65D cases (38 inherited plus Buffer save and
invalid payload), with the positive Buffer case independently witnessed by
the D81 filesystem and BAM models. The compiler tier remains byte-identical,
the fixed-slot writer's nine resident functions are absent, and the live
chain-walker inventory closes at 18 walkers / zero deviations. Against the
Wave-1 baseline the requested repin is entirely positive: **+8 B Bank reserve,
+727 B post-load EXT headroom, +10 symbols, +203 B Namepool, +7 Directory
entries and +256 B runtime-overlay-bank headroom**; fixed overlay, resident
island, maximum reusable runtime slice and installer slice are unchanged.
The exact positive repin is bound by
`config/v11-m-transactional-fasl-capacity-authorization.json`; no debit or
frozen-budget exception is hidden in the block. Status is
`implemented-passed-authorized-not-wave-promoted`: the block may enter the
next Wave-2 candidate, while end-to-end `compile-string` and arbitrary-name
persistence remain hardware claims for the fresh Wave-2 cycle.

Closes the confirmed compile-persistence finding structurally. The missing
bridge is "M65D COW transaction with binary payload from the FASL staging
window" — and the first-class buffer (1.1-E) is exactly that carrier.

- Compiler output becomes a buffer; `m65d-save` accepts a buffer payload;
  persistent compilation runs through the full M65D COW transaction: allocate
  a new chain, write and verify from staging, publish the directory entry
  last, free the old chain.
- Media binding holds across the whole transaction (same token semantics as
  the G6 case-5 fix), and the L65SYS denylist applies. The rejected 1.0.1
  Bank-0 guard never shipped; M is the first trusted transactional path for
  persistent compiler output.
- The probe reports resident-island demand explicitly. The island enters this
  block with only 120 B reserve; no implicit transaction or buffer state may
  consume it without a measured capacity delta and prior authorization.
- **Preallocated `fasl*` slots are abolished** along with the historic
  two-argument write seam; `compile-string` targets any free space on any
  valid non-product medium. Slot provisioning on the work D81 dies with them.
- The 600-byte decision that created the fixed writer is not reversed but
  obsoleted: M65D and the buffer type now exist; the probe decides what the
  bridge really costs (EXT is touched — wave-1 relief is a prerequisite).

### 1.1-G — Small language-polish package

Status corrected by owner decision 2026-07-18: the Wave-2 green surface is
`read-from-string` only. The earlier combined (`read-from-string`,
`restart-repl`) implementation was capacity-authorized (−49 B Bank, −41 B EXT, −2 symbols,
−30 B name pool; runtime-overlay bank 320→64 B via pack-stage granularity —
23 B real growth booked as one 256-B stage), but hardware rejected all three
bounded pre-C2 restart architectures. The rejected implementation receipt is
historical; the current candidate removes the wrapper and resident action and
measures a separate credit-only scope correction. Contracts approved as drafted in
`v11-g-contract-drafts.md`: `gc`/`room` (private selector carrier, fixed
eight-counter list, no printing, static 15-bit build gates), `(error
string)` (existing top-level unwind, no handlers/codes/restarts before
1.2). **Tick hook fully deferred to C2 — no `repl-idle-hook` substitute**
(a hook that supports neither `(time)` nor game loops mainly generates
explanation debt; `lisp_poll()` is proven unsafe as a callback point and
no capacity figure can authorize an unsafe one). `(time)` moves to the C2
era with it; the `ticks` tombstone points at the C2 hook; the parity
revalidation input becomes "tick: C2".

Update 2026-07-17, gc/room/error implementation: semantically green
(direct/funcall/apply, NUL and 9,344-B max string, exact unwind, fixed
eight-counter form at exactly 16 cons cells per two calls) but
architecturally unlinkable — resident 352 B over the VMA boundary
(vm_callprim +281 B dominant) and the shelf name lookup crossing a pack
stage (+192 B runtime bank). **Authorized: exactly one bounded
architecture attempt** (generic overlay facade for private carriers —
generic as in amortizable across future carriers, per the 1.1-E facade
precedent — plus catalog-neutral room delivery and a structural pack
plan); both deficits must vanish in one real link, no cap loosening, no
reclaim series; on failure option 2 (defer trio to C2.2, roll back)
applies without further tuning. Semantic evidence survives either
outcome. **Standing-budget delivery after fallback: shelf catalog at
65,368/65,535 — 167 B headroom** (the rejected six-container candidate had
only 7 B). Consequence: wave 3's shelf modules (H/I/J, metadata file) still do
not fit before catalog relief: one 32-B record leaves only 135 B payload.
Commissioned: a short wave-3 feasibility
note after the trio attempt — option (a) shrink wave 3 to shelf-free
content and move H/I/J behind C2, vs. option (b) examine whether the
u16→u24 catalog evolution can be cleanly excised from C2.0 and pulled
forward; owner decides on numbers.

**Test-bench audits and bounded v4 decision, 2026-07-18.** The audit is now
receipt-confirmed rather than inferred from manifests: 36,260 B of metadata
are 55.6% of the 65,176-B shelf payload region (55.5% of the complete
65,368-B shelf). Literal nodes 17,370 + patches 6,900 + index 3,474 =
27,744 B; the raw string pool is 5,347 B, or 5,350 B including regional
alignment. The important correction is architectural: moving these bytes to
a D81-only side file would break the one-swap/media-independence contract.
Metadata separation is therefore a **v4 region-layout variant in the same
reset-persistent, identity-bound Attic artifact**, not a no-format-change
shortcut. The receipt is
`tests/bytecode/dialect-v2/evidence/architecture-blocks/v11-shelf-metadata-audit-receipt.json`.

Owner authorized exactly one L65S-v4 probe, comparing pure u16→u24 widening
with widening plus immutable-code/load-time-metadata regions. Both host
models are 65,367 B, reconstruct all five current L65M containers
byteidentically, and leave 458,793 B of combined future region space after
four Wave-3 records inside the explicitly probe-only 512-KiB envelope. The
regions variant was selected because it costs no shelf byte over pure widening
and is reusable C2.0 contract work. **The one real product link failed the
hard gates:** the stage slice was 3,326 B against 1,792 B (1,534 B over), and
the fixed runtime-overlay link region overflowed by 84 B. Per the authorized
one-attempt rule there is no simplification, tuning or reclaim retry:
**Wave 3 falls back to L-lite; H/I/J and shelf metadata delivery move behind
C2.** Product sources and L65S-v3 were restored byteidentically. Bound outcome:
`tests/bytecode/dialect-v2/evidence/architecture-blocks/v11-l65s-v4-one-attempt-outcome-receipt.json`.

Independent audit decisions survive the fallback. Export-only interning never
shrunk shelf names (symbol literal nodes retain their names; the 45/742
recovery was Bank-0-only). The M-x launcher is already string→id: 16 of the
17 "public until revoked" names are authorized for anonymization, while
`bytecode` follows the 1.1-G kind contract. This work is **not** part of the
failed format probe; it is bundled once with the Wave-2 repin (about 18
name-echo cases and three SHA-bound differential receipts). About 2 KiB of
runtime-bank boundary shaving remains parked as reserve; no sweep runs without
concrete need. The refreshed IDE diet belongs to L-lite (dispatcher tables,
M-x duplicate removal and de-interning); `ide-syntax` is load-bearing and no
longer a removal candidate. The line model on Buffer primitives and deeper
tiering remain separately unassigned. The prepared classification and its
source/manifests audit are bound in
`tests/bytecode/dialect-v2/evidence/architecture-blocks/v11-wave2-policy-name-audit-receipt.json`:
16 names / 182 B are revocable, `bytecode` remains, and the public M-x spelling
`save-buffer` (ID 1001) is kept distinct from the internal `write-file` token.

The authorized attempt's pre-link pack plan is pinned in
`config/v11-g-private-service-pack-plan.json`: one generic service-id facade,
state co-packed into the existing 243-B padding of `lcc-install-02`, dynamic
user-error handling/rendering co-packed into the existing 181-B padding of
`lcc-install-01`, and `room` delivered as standard resident bytecode rather
than a sixth shelf record. The only admissible successful link keeps the
five-container shelf at 65,368 B and the packed runtime-overlay bank at or
below its accepted 65,472 B; crossing either existing pack boundary triggers
the already authorized C2.2 fallback without a second architecture attempt.

**Outcome 2026-07-17 — attempt exhausted, fallback active.** The single real
link ended with BSS at `$c43a`, **228 B beyond** the fixed `$c356` boundary.
The generic error carrier occupied 2,007 B (**215 B over** its 1,792-B hard
window); the state carrier occupied 1,560 B (**280 B over** its planned
1,280-B co-pack allocation). This is a failure of both required fit axes, not
a near-pass. Per the pre-authorized rule there is no second tuning or reclaim
round: `gc`, `room`, and `error` have been removed from the 1.1 ABI, product
surface, bytecode and shelf. Their proven semantics remain pinned in
`config/v11-g-state-error-contract.json` and move together to C2.2. The final
outcome receipt binds the failed map/log, the semantic observations and the
byteidentical delivery-source rollback:
`tests/bytecode/dialect-v2/evidence/architecture-blocks/v11-g-state-error-implementation-probe-receipt.json`.

- **Closed 2026-07-18 — error-text delivery:** the requested loadable mapping
  already exists as the canonical L65E-v1 reusable runtime-overlay library
  (slice 36). It binds 60 stable codes, selects 43 Workbench texts, omits 17
  not-built/resident-only texts, and retains the resident `Ehh` fallback.
  Linked size is 1,240 B against the existing 1,320-B slice; every capacity
  delta is zero. No duplicate shelf library or public lookup primitive is
  introduced. Receipt:
  `tests/bytecode/dialect-v2/evidence/architecture-blocks/v11-wave2-error-text-library-receipt.json`.
- **Promoted in the common repin 2026-07-18 — list primitive unification:** Treewalk and
  CALLPRIM now share the `nreverse`/`rplaca`/`rplacd` mutation core while
  retaining their route-specific strict-arity and error checks. The existing
  list suites remain green (172 four-route/engine evaluations, 16 Python-P0,
  86 LCC) and native-registry cross parity remains 828/828. Isolated real
  links against commit `5720f16` attribute −108 B to `vm_callprim`, +96 B to
  the shared/Treewalk path, hence **+12 B Bank reserve** with every other
  frozen dimension unchanged. The owner authorized the credit and the common
  Wave-2 repin absorbed it. The isolated attribution remains bound in
  `tests/bytecode/dialect-v2/evidence/architecture-blocks/v11-wave2-list-primitive-unification-probe-receipt.json`.
- **Contract closed 2026-07-18 — function metadata:** a deterministic,
  SHA-bound host index now carries name, public kind, visibility, arity state,
  optional signature and optional docstring. Exact arity is decoded from the
  bound code object rather than copied into a help table. The current index
  has 135 public records: 101 exact arities and 34 explicit unresolved
  native/macro authorities; all signatures and docstrings remain null rather
  than guessed. Therefore `ide-help` is deliberately **not ready**. Device
  delivery no longer claims the failed 1.1 shelf path: after the one L65S-v4
  attempt, the identity-bound reset-persistent index moves with H/I/J behind
  C2; a D81-only side file remains forbidden. Current capacity delta is zero.
  Contract and receipt:
  `config/v11-function-metadata-contract.json` and
  `tests/bytecode/dialect-v2/evidence/architecture-blocks/v11-function-metadata-contract-receipt.json`.

**Common Wave-2 repin closed 2026-07-18.** The real commit-bound link against
baseline `5720f16` measures +12 B Bank reserve (1,849 → 1,861), +16 symbol
headroom (303 → 319), +182 B Namepool headroom (4,702 → 4,884), and +200 B
u16 shelf headroom (167 → 367). The last gain is the on-device consequence of
replacing the 16 symbol literals: IDE loses 182 name bytes, one 10-byte literal
node, one 4-byte patch and one 2-byte index record; its external image and the
five-container shelf both shrink by 200 B. Peak EXT headroom improves by 200 B
and post-load EXT headroom by 2 B. Bank, Overlay, runtime bank, island,
installer, Directory and code-buffer pins do not regress. All 18 policy-name
echo cases pass; the four-artifact differential closes 378 cases with zero
unexplained differences. Receipt:
`tests/bytecode/dialect-v2/evidence/architecture-blocks/v11-wave2-common-repin-receipt.json`.
At this historical point, hardware remained explicitly not-run until the fresh
Wave-2 G5/G6 cycle.

**Wave-2 acceptance sealed 2026-07-18.** The final product set
`5c7c17f8b441f8acd4f5d57ac9dd17db852f1884f7450611985e13489cc0ffb6`
passed the fresh G5 matrix `14/14`; promotion `r5-global-g5-4408e85` binds
archive SHA-256 `7a2c0247d386bae39c3250d903144a15ccae2e2c7355c623a4d881a3558aaea9`.
G6 then passed all `5/5` cases applicable to the single-device stock-core
SD-D81 profile. The physical product-medium write-protect case remains
explicitly `n/a` because that profile exposes no physical or virtual
write-protect medium. Promotion `r6-g6-hardware-acceptance-9733ba6` binds the
self-contained archive SHA-256
`20ce83962fdc6236f3eb808d3c7946381a2c8c0cdcd0ae1b01a25b7cd601da20`;
varied-environment double packing, isolated offline verification, and all
three archive-manipulation negatives passed.

The hardware run includes arbitrary-name `compile-string` through the full
M65D COW transaction, the Regal reset path, and the remaining product/media
cases. The seal retains the metadata limit in its value string:
`101-exact/34-unresolved-no-complete-help-claim`. It does not claim a complete
help surface or release promotion. The historical `fasl*` slot and unbound
compiler-write errata therefore retire for this candidate, while release
1.0.1 retains them. `restart-repl` remains absent under the owner scope
decision above and is C2.3 freight. Wave 2 is closed; compact Wave 3 (L-lite)
is the next 1.1 product work.

**Wave-2 acceptance reopened 2026-07-18 — fail-fast rule paid immediately.**
The first G6 run proved that `$FFFC` returns to BASIC. The owner-authorized
three-byte direct repair (`LDX #$FF; TXS; JMP _start`) then failed the new
receipt-less hardware pre-smoke: no fresh banner or prompt appeared, so no
R3/R4/R5 restart was begun. A single bounded recovery design attempted to
preserve the pristine 16-KiB Bank-5 window in Bank 7 before CRT entry. JTAG
readback invalidated its premise before a valid product run: MEGA65 Fast RAM
ends at `$5ffff` (Banks 0--5), and `$70000` remained 16,023 zero bytes even
immediately after a reported injection. Both prototypes were rolled back;
the resident and linked PRGs are byteidentical to the common-repin candidate,
Bank reserve is 1,861 B, and neither the authorized 3 B nor the unapproved
24-B/426-B recovery costs are booked. At this historical point `restart-repl`
again blocked the Wave-2 seal. The then-next design was a fresh reviewed probe: either a valid Attic-to-
Bank-5 restore that reuses existing enhanced-DMA machinery, or a complete
in-process-reset contract. Diagnosis receipt:
`tests/bytecode/dialect-v2/evidence/architecture-blocks/v11-restart-repl-self-restart-probe-receipt.json`.

**Bounded Attic-recovery probe failed and rolled back 2026-07-18.** The owner
authorized exactly one attempt to make the pristine Bank-5 image a proper
reconstructible Attic tenant at `$08200000`, with full SHA-256 identity,
generation, header CRC32 and payload CRC32 before and after restore. The host
integrity negatives, generated-constant parity and the separate stager fit
passed (6,842/16,384 B; chain trampoline 35/64 B). The one permitted real
product link then stopped at its first seed link: resident code moved the
unchanged 2,246-B BSS front from `$ba4b` to `$bf56` (+1,291 B), added 32 B
`.noinit`, and ended at `$c83c`, 1,254 B across the fixed runtime-overlay VMA
`$c356`. Independently, llvm-mos proved that `uintptr_t` is 16-bit here, so
the draft conversion of physical Bank-5 address `$00050000` truncated to
zero. No candidate PRG existed, no second link or hardware smoke ran, no
capacity debit was booked, and all probe source changes were removed. The
C2 transfer is now sharper: live Bank 5 is session-mutated, but a correct
resident whole-image identity/restore mechanism does not fit the current
pre-C2 boundary. Receipt:
`tests/bytecode/dialect-v2/evidence/architecture-blocks/v11-restart-repl-attic-recovery-probe-receipt.json`.
The failed probe closed pending an owner decision and must not become an
incremental tuning series; the following decision resolves that stop by scope.

**Owner scope decision 2026-07-18 — defer, do not delete.** `restart-repl`
leaves the 1.1 surface and becomes named C2.3 freight. This resolves the
feature-specific R3 stop once the current product, surface, differential and
G6 contracts prove the name absent. The user-facing 1.1 escalation ladder is
RUN/STOP (abort, keep session) → product-disk restart (fresh Lisp65 session) →
power cycle (cold machine). The two diagnosis receipts remain immutable C2
inputs and the C2.3 hardware case invokes the eventual function twice to prove
stack and mutable-state idempotence. No fourth pre-C2 restart design is
authorized. The complete rebuilt product graph measures this scope correction
as a credit only: **+46 B post-boot Bank reserve, −36 B resident EXT image,
+14 B EXT-code headroom, +1 symbol and +13 B Namepool**; Boot overlay,
runtime-overlay bank/slices, island, installer slice, Directory and shelf are
unchanged. The live metadata boundary consequently becomes 135 records
(101 exact, 34 unresolved). Exact values are bound by
`tests/bytecode/dialect-v2/evidence/architecture-blocks/v11-restart-repl-wave2-scope-correction-receipt.json`
and await the common capacity repin before R3 resumes.
- **Bitwise operations `logand logior logxor ash`** (added 2026-07-15): the
  redesign's resident target list included them ("essential on this
  hardware"), but they were silently lost between the design document and
  the v2 migration contract (no decision-log entry, no tombstone). Without
  them, `peek`/`poke` users must mask register bits with `mod` arithmetic.
  Pre-check outcome (measurement 8): **no dormant opcodes** — the frozen
  P0 v1/v2 ABI set never contained bitwise opcodes, so all four take the
  regular probe path (new opcodes or natives; do not confuse the historical
  v1 opcodes 26/27/32 with the string-builder prim-ID tombstones 26/27, a
  separate number space). Symbol cost (4) is drawn from the 1.1-B recovery
  and reported in the capacity delta. `peekw`/`pokew` ride this probe and
  are taken only if nearly free (owner classification 2026-07-16).
  **DEFERRED TO C2.2 (owner-confirmed 2026-07-17):** the architecture probe
  found both cuts red at hard independent caps (runtime slice +603 B over
  its 1,792-B lid; compact v2 opcodes pass the ABI gate but push the shelf
  to 65,862 B, +327 B over the u16 catalog). C2's extended addressing
  replaces exactly that catalog encoding, so a reclaim squeeze into a
  format C2 retires would be throwaway work. Triple anchor against a fourth
  silent loss: (a) fixed slot in **C2.2** (catalog/format evolution),
  (b) the language reference documents the absence — including that the
  `peekw` tombstone route "compose from peek/poke + ash" is not walkable
  in 1.1, (c) decision-log entry. **New standing budget discovered:** the
  shelf catalog is u16-bounded and nearly full — Codex reports current
  shelf size and catalog headroom as a standing budget line **before any
  wave-3 planning** (wave 3 wants to add shelf modules; this may be its
  hidden blocker). **Standing measurement 2026-07-17:** the accepted pre-block
  canonical five-container shelf is **65,368 B of 65,535 B**, leaving **167 B**
  catalog headroom. The rejected `room` candidate added a 128-B container and
  one 32-B catalog record: **65,528 B**, only **7 B** headroom. After the
  authorized carrier attempt failed, that record was removed; the standing
  receipt binds the restored five-container shelf and retains 7 B only as
  rejected-candidate history:
  `tests/bytecode/dialect-v2/evidence/architecture-blocks/v11-shelf-catalog-headroom-receipt.json`.
- **Restored primitives from the classification session (owner, 2026-07-16):**
  `error`, `gc`, `room`, `read-from-string` — each probe-first, symbols
  reported against the 1.1-B recovery. `ticks` is absorbed by the tick hook
  above; it gets no separate primitive.
- **`(restart-repl)` — DEFERRED TO C2.3** (owner scope correction
  2026-07-18): platform reset, direct CRT re-entry and an identity-bound Attic
  whole-image restore independently failed. All three failures point to the
  missing C2.0 immutable-code/mutable-session split. Wave 2 exports no name and
  makes no partial behavior claim. C2.3 inherits the double-invocation hardware
  case, unchanged-media requirement and both diagnosis receipts covering the
  three attempted architectures.

Explicitly out of scope: `&key`, CLOS-like systems, restarts, import stage 2,
and any weakening of strict arity or stable error semantics.

**Probe round 2026-07-17 — passed, not promoted.** The bounded real-link
comparison is bound by
`tests/bytecode/dialect-v2/evidence/architecture-blocks/v11-g-language-polish-probe-receipt.json`:

- `read-from-string` is the cleanest result: it composes the existing string
  reader, costs 0 B Bank and 53 B resident EXT (one symbol, 17 name bytes),
  and has direct/`funcall`/`apply` host observations. `gc` also links, at the
  conservative shared-dispatch price of 90 B Bank and 26 B resident EXT.
- The direct resident C cut for all four bitops is rejected by the real link
  (441 B overlap with the fixed runtime-overlay VMA after the one permitted
  16-bit rewrite). The next legitimate comparison is compact VM opcodes
  versus a funded runtime slice; no third micro-optimization pass is allowed.
- `peekw`/`pokew` stop before pricing: the current fixnum cannot represent a
  full unsigned 16-bit read. A representation decision or an explicit
  tombstone must precede implementation.
- `room` with a resident two-element list result is rejected (144 B overlap).
  Its result shape and counter-overflow contract must be pinned before an
  alternate shelf/status-carrier cut is measured. `error` likewise stops at
  the contract boundary: the numeric error overlay has no dynamic user
  payload ABI, so a new stable code alone would not deliver `(error message)`.
- `restart-repl` links at the same conservative 90-B shared-dispatch Bank
  price plus 36 B resident EXT; it remains `passed-not-promoted` until a real
  MEGA65 proves the intended fresh-session outcome, Attic restaging, REPL
  return and unchanged M65D media. The probe's then-current reset-vector
  mechanism was later hardware-rejected as recorded below. Cooperative jiffy
  observation costs 23 B Bank, but is explicitly
  only a tick-hook lower bound: nested VM polling is not a safe Lisp callback
  point and no scheduling contract is yet pinned.

These per-variant figures are absolute links and are not additive: `gc` and
`restart-repl` deliberately share the conservative probe dispatcher. No new
Prim-ID was allocated and no canonical product source was changed.

**Owner decisions after the probe (2026-07-17; restart portion superseded
2026-07-18).** `read-from-string` is released for canonical implementation
under `config/v11-g-green-surface-contract.json`; `restart-repl` is removed
from 1.1 and carried by C2.3. `peekw`/`pokew` are closed by
`config/v11-g-word-access-tombstone.json`: the signed 15-bit fixnum cannot
represent the full unsigned word result, so the owner rule "nearly free or
tombstone" removes the names from 1.1. Their former composition route is also
unavailable in 1.1 because `ash`/`logior` are deferred to C2.2. The completed
compact-opcode versus runtime-slice comparison includes ABI-ledger,
disassembler and four-engine consequences. `gc`/`room` and `error` now have
owner-approved contracts and may enter bounded implementation probes. The
tick hook is wholly deferred to C2 with no prompt-only substitute.

**Bitops architecture comparison stop (2026-07-17).** The isolated real-link
comparison is bound by
`tests/bytecode/dialect-v2/evidence/architecture-blocks/v11-g-bitops-architecture-probe-receipt.json`.
Neither authorized cut fits the pinned product, so no ABI or product change is
promoted. The runtime-slice cut grows the C1 compiler-lifetime slice to 2,395 B,
603 B beyond its 1,792-B stack-safe cap. The compact opcode cut passes the
extended ABI-ledger gate while leaving dialect-v1 IDs 20–23 reserved, but its
required v2 LCC emitter additions grow the five-library Attic shelf to 65,862 B,
327 B beyond the u16 catalog limit. The comparison also exposes one permanent
gate consequence: LCC parity must classify overlapping opcode and Prim-ID
numbers by canonical name and view, never by number alone. The next legitimate
choice is explicit deferral or a separately measured ≥327-B shelf reclaim;
neither the slice cap nor the catalog format may be weakened inside 1.1-G.
Four-engine acceptance remains mandatory only after a fitting architecture is
selected; the rejected variants earn no delivery claim.

**Historical Green-surface implementation authorization (2026-07-17;
superseded in part 2026-07-18).** The then-canonical
`read-from-string`/`restart-repl` implementation is host- and real-link green
and capacity-authorized for inclusion in the Wave-2 candidate. Receipt:
`tests/bytecode/dialect-v2/evidence/architecture-blocks/v11-g-green-surface-implementation-receipt.json`.
Against the authorized 1.1-M implementation it measures −49 B Bank, −41 B
post-load EXT, −2 symbols and −30 B Namepool; Directory, fixed overlay,
resident island, maximum runtime slice and installer slice are unchanged.
The changed whole-program link grows `boot-fastpath-verify` 1783→1806 B; that
crosses one 256-byte packing boundary and returns runtime-overlay-bank
headroom 320→64 B. The 256-byte packing debit is fully attributed; the
individual 23-byte linker movement is not assigned a stronger cause without
an isolated build. Semantics cover direct/`funcall`/`apply`, first-object,
type and both arity negatives, a host restart witness, and one linked
`jmp ($fffc)`; device restart remains `not-run` for Wave-2 G6.

The contract-first drafts are collected in
`docs/planning/v11-g-contract-drafts.md`. They recommend one selector carrier
for synchronous `gc` plus nonprinting fixed-shape `room`, a one-String dynamic
payload on the existing abort boundary for `error`, and deferral of a full
tick callback to C2 because only the top-level REPL boundary is presently
reentrancy-safe. All three decisions are owner-approved. No prompt-only hook
ships in 1.1.

**State/error implementation architecture stop (2026-07-17).** The bounded
canonical implementation probe was semantically green but could not produce a
valid product link. ABI identity was complete (36 opcodes, 69 Prim IDs), all
native views were cross-parity green (828/828), and `gc`/`room`/`error` passed
their direct/`funcall`/`apply`, type and arity gates. The focused C oracle
also proves exact dynamic error text (including embedded NUL and the maximum
9,344-B product String), canonical cleanup, synchronous one-shot GC and
allocation-free counter reads. In that rejected candidate, `room` was a shelf
library; a repeated-call
gate proves exactly eight result conses per call.

The real product link nevertheless stops fail-closed: a detached rebuild of
accepted commit `0da2d57` ends at `$c31d` with 57 B before the fixed `$c356`
runtime-overlay VMA, while
the candidate ends at `$c4b6`, an exact **352-B overlap**. The resident
boundary moved by 409 B; the map attributes 281 B to `vm_callprim` and 2 B to
the pending user-String root, leaving 126 B deliberately unattributed without
isolated links. A second independent cap is also red: the shelf name-lookup
slice grows 1,252→1,314 B, crossing a 256-B packing boundary. Against the
accepted 65,472-B runtime-overlay bank (64 B headroom), the deterministic
packed consequence is 65,728 B, **192 B over the bank**. The candidate stops
before a bank image exists, so this is explicitly a projection from exact map
sizes and the pinned pack contract, not a fabricated artifact. No capacity
delta or delivery authorization is requested because no valid link exists.
Receipt:
`tests/bytecode/dialect-v2/evidence/architecture-blocks/v11-g-state-error-implementation-probe-receipt.json`.

This was an architecture stop, not permission for a VMA/floor relaxation or a
micro-reclaim loop. The subsequently authorized single generic-facade/co-pack
attempt also failed its resident and carrier-window gates (see the final
outcome above), so the pre-agreed C2.2 fallback is now definitive for 1.1.
These three names are absent from the 1.1 public surface; only their semantic
contract and rejected-probe evidence remain.

**Probe-provenance correction.** The first 1.1-M plumbing added convenience
targets to `mk/workbench.mk`; that file is itself a hashed product-contract
input, so even target-only edits changed the build ID. The targets have been
removed and M/G probes are invoked directly through their Python tools. A
fresh canonical R3 build after the correction reproduces the sealed Wave-1
product set `e14de21a23823d70d90df0988a5424b436af89f1ebae21772950dcec7857549f`.
Future probe entrypoints must remain outside product-hashed build inputs.

## Wave 3: IDE polish

New components are loadable shelf modules. `ide-core` remains the only required
editor component. Wave 3 opens with the keyboard truth path (1.1-L); every
other wave-3 block builds on it — IDE polish on an unproven input path would
be polish on sand.

**Catalog feasibility stop (2026-07-17).** The final 1.1-G fallback restores
the canonical L65S-v3 shelf to 65,368/65,535 B, but 167 B still cannot carry
H/I/J: one new 32-B record leaves only 135 B payload, while three records leave
71 B combined before feature code. L-lite can proceed shelf-neutral; H/I/J
must not start until the owner chooses between a shelf-free 1.1 Wave 3 and one
bounded L65S-v4 staging-catalog probe derived from the C2.0 address contract.
Decision input: `docs/planning/wave-3-shelf-feasibility-2026-07-17.md`.

### 1.1-L — Keyboard truth path (entry block, prerequisite for H/I/J)

**Split 2026-07-17 (owner-approved) — L-lite ships in wave 3, L-full is
deferred to structural overlay relief** (realistically the C2 train in 1.2;
overlay stands at 0 B against the driver's measured +68 B).

**Wave-3 rider (owner hardware find, 2026-07-18): scroll must move color
RAM with screen RAM.** The banner is the product's first per-cell color
consumer and exposed a missing contract: the screen driver's scroll DMA
moves the character matrix but not the color window, so the banner's
yellow/gray cells stay fixed and mask white text scrolling through them.
Fix: a second DMA job mirroring the scroll over the color-RAM window plus
default-color fill of the newly exposed bottom row — the semantically
right contract (color is part of scrolled content) and the cheap one
(a few dozen Bank-0 bytes, microseconds of DMA; probe-first as always).
The band-aid "banner clears its colors on first scroll" is rejected: the
1.2 definition-buffer syntax highlighting would resurrect the ghost
immediately. New visual gate case: scroll past the banner → no color
masking (the screenshot detector already knows the banner glyphs). Found
before any release ships it — no user ever sees the ghost if this rides
wave 3.

**L-lite (wave 3, overlay ±0) — binding truth on the existing GETIN path:**

- **RUN/STOP joins the binding matrix as its most safety-critical entry**
  (owner inquiry 2026-07-18): the evaluation break exists
  (`lisp_poll()` reads the KERNAL STKEY flag $91 → clean top-level abort,
  "stopped (run/stop)") and gets a permanent hardware case — running
  evaluation → RUN/STOP → defined message + usable prompt. Wave-seal doc
  duty: the user guide presents the full escalation ladder in one place —
  **scope-corrected 2026-07-18 after the three restart probes**: RUN/STOP
  aborts and keeps the session; restarting Lisp65 from the product disk gives
  a fresh session (platform Reset first exits to BASIC); power cycle makes
  everything cold. `restart-repl` is C2.3 freight, not a 1.1 step.
  Note: the break's
  KERNAL dependency is recorded as a passive entry in the C2.0 KERNAL
  residency audit.
- **RUN/STOP loses its editor bindings (owner decision 2026-07-18) — one
  key, one meaning.** Today RUN/STOP carries three roles: abort, open
  editor (REPL toggle, `repl.c` LISP65_REPL_IDE_TOGGLE), and exit editor
  (`%ide-quit-key-p`, added because the command loop was otherwise
  inescapable). Both editor bindings are removed; RUN/STOP means only
  "abort running evaluation" (idle: no-op). Replacement exit: **`C-x C-c`**
  (code 3 is free in the prefix table); `(edit)` remains the way in; ESC
  keeps its minibuffer-cancel role. The proven B4 property "exit preserves
  the buffer" migrates as a bound case onto the new chord. Documentation
  states the abort landing rule: aborting an editor-initiated evaluation
  unwinds to the REPL; `(edit)` resumes the preserved buffer.

- Every documented binding gets a bound proof: one permanent hardware case
  per binding (virtual injection for the full set plus a small physical
  sample per acceptance run); the user-guide keymap table and the test list
  are generated from one source.
- Broken bindings are re-bound to reachable chords instead of waiting for
  the driver: C-Space is constructively unreachable on GETIN (code 0 =
  "queue empty"), so set-mark moves to e.g. `C-x Space`; the ROM
  control-code assumptions become per-binding proven facts instead of
  assumptions.
- No new driver, no modifier claims: the documentation continues to state
  that Meta/MEGA/Alt chords do not exist and M-x is C-x x / C-x Return.

**L-full (deferred, returns with overlay relief):**

- Switch input to the MEGA65 typed-event queue (`$D60A`/`$D619`), produce
  `(key code modifiers)` from that single hardware source, retire the
  GETIN heuristics (shift reconstruction, code 0 collision), and make the
  keymap modifier-based (`control`+`space`, `meta`+`x`).
- Pre-conditions already resolved: Xemu implements the typed queue (source
  parity at `40dfef0d1d5f`) — emulator differential coverage plus physical
  sample; the driver-path probe measured −62 B Bank 0 / +68 B overlay.
- H/I/J build on binding truth (L-lite), not on the driver — the wave-3
  dependency is satisfied by L-lite.

### 1.1-H — `ide-lisp`

- automatic pairs for `(` and `"`;
- matching-parenthesis highlight near point;
- forward/backward/up/down S-expression movement;
- scanner correctness through strings, comments, nesting, and unbalanced input.

Paredit-style slurp/barf remains out until undo is proven.

### 1.1-I — Editing safety

- Undo first, using command deltas as the default representation (pre-wave
  measurement 5: deltas need 11.84% of snapshot payload across 20 real
  commits); clear OOM behavior is mandatory. Redo follows only after stable
  undo.
- Incremental search and goto-line.
- Visible region and line-number toggle.

### 1.1-J — `ide-help`

Depends on the metadata contract from 1.1-G.

- `apropos`, `describe`, and UI symbol completion;
- parameter display for known function signatures;
- command help with key binding and short description;
- all metadata loaded on demand from the shelf and checked by a host oracle.

Order within wave 3 is L → H → I → J. Help may move out without blocking the
safety and Lisp-editing improvements if its measured cost does not fit; L may
not move — it gates the wave.

## Committed 1.2 lead themes: ship builder and C2

The on-device ship builder and C2 direct Attic execution are the two committed
1.2 lead themes. Their ordering and scope split remain a later owner decision;
their inclusion does not. **Commissioned (owner, 2026-07-17): a short 1.2
scope memo after the wave-1 seal** (ordering, dependencies, what the dated
1.90-s exception forces about C2 timing). Owner tendency on record: C2 leads;
the ship builder can comfortably arrive in a later version, since no user
will finish shippable programs within the next months.

Draft delivered for owner review:
`docs/planning/v1.2-scope-memo.md`. It recommends C2 as the non-deferrable
1.2 lead, the ship builder in 1.3, `while` as the single control-flow repair,
an early read-only `(show 'name)` slice, and parity-design revalidation without
committing a parity module to the 1.2 binary. Those recommendations do not
become product scope until the memo's four owner decisions are recorded.

**Added to 1.2 planning (owner, 2026-07-17): one minimal non-local-exit
primitive.** Dialect V2 currently has no early-exit construct at all (no
`while`, `block`/`return-from`, `catch`/`throw`, `tagbody`/`go`; iteration
is bounded or recursive). Sharpened 2026-07-17: this is not merely
desirable — the redesign's consolidation table justified deleting `do` with
"`dotimes`/`dolist`/`while` cover the real usages", i.e. **the redesign
assumed `while` exists; it was never implemented** — a silent target-list
loss in the special-form category, which measurement 8 (names diff) could
not see. That gives the `while`-as-special-form option extra weight over
`catch`/`throw` in the design choice. Scope: exactly one mechanism — either a `while`
special form or a VM-supported `catch`/`throw` pair, not both — co-designed
with the `error` restoration from 1.1-G, since signaling and early exit
share the unwind machinery. It unlocks `while`/`until` for `loop-lite`,
early-exit search without consing, and user-level condition handling (see
`extension-libraries-design.md`). The 1.2 scope memo must cover it alongside
C2 and the ship builder; as a language/VM change it takes the full block
process with probe and acceptance.

**Also for the 1.2 scope memo (owner, 2026-07-17):** the revalidation pass
for the pre-1.0 BASIC 65 parity-library design
(`docs/archive/pre-1.0/designs/mega65-basic-parity-libraries.md`) — the
design is complete but predates Dialect V2, the shelf, the buffer type and
the 1.1-G tick-hook placement; the memo schedules when revalidation and the
pilot module happen relative to C2 and the ship builder. The ship builder benefits directly from the shelf
layout and metadata graph created in 1.1. C2 is the named cure for the dated
1.90-s definition-call limitation and must return for explicit owner approval
if it slips out of 1.2. These are delivery-version decisions, not weakened
product commitments: users must eventually be able to create a standalone
bootable application disk, and the interactive definition cycle must lose its
documented C1 reload delay.

## Not in 1.1

- multi-drive support;
- full Paredit, multiple windows, or a complete Emacs key set;
- import stage 2, C64 runtime target, or parity-library expansion;
- any EXT spending before 1.1-C meets its relief threshold;
- a core fork; mount locking and virtual write protection remain upstream
  proposals.

## Required pre-wave measurements

Status: all seven completed on 2026-07-15. The machine-readable report and its
human decision table are in `docs/planning/measurements/`. Measurements 2 and
3 remain the mandatory review input before any 1.1-A/B/C product work starts.

1. Does the banner blob count against the EXT metric?
2. Which stdlib/blob components can move to the shelf, and what exact EXT bytes
   does each recover?
3. What symbol and name-pool bytes does export-only interning recover for the
   standard composition?
4. Should help metadata extend a manifest or use a separate SHA-bound shelf
   index? The preferred answer is a separate index.
5. What is the measured cost of delta-based versus snapshot-based undo on real
   editing sessions?
6. Does Xemu emulate the `$D60A`/`$D619` typed-event keyboard queue? If not,
   the 1.1-L binding cases are hardware-only and the gap is an
   upstream-register candidate.
7. Probe: Bank-0 cost of the event-queue keyboard driver path (1.1-L).
8. **Redesign target-list diff — completed 2026-07-15.** Corrected inputs: 83
   target names, 75 real registry function/classification names. Result: 35
   native, 26 shipped resident bytecode, 5 deliberately deferred (documented
   in the migration contract), **17 silently lost with no tombstone or
   decision-log reference**: `filter logand logior logxor ash intern read
   read-from-string peekw pokew edma sector-read sector-write ticks gc room
   error`. Consequences:
   - **`filter` is a confirmed delivery bug** (declared in the canonical
     surface and the language reference, implementation exists, missing from
     the sealed resident manifest; no alternative lists library on the
     product D81). Erratum addition immediately. At the authorized
     zero-EXT-margin A/B state, the manifest fix waits for the wave-1 seal
     after C1 and is paid from C1's measured gain; it does not ride the A/B
     integration point. Structural closure is a generated **cross-parity
     gate: surface JSON ↔ packaged resident manifest ↔ language reference**,
     which also covers the `eval` public-surface drift found in the same
     measurement.
   - Bitwise pre-check outcome: no dormant v2 opcodes (the v1 opcodes 26/27/32
     predate the frozen P0 profile; `ash` never had one; prim-ID tombstones
     26/27 are a separate number space). All four take the regular probe
     path within 1.1-G.
   - **Owner classification completed 2026-07-16** — every verdict gets a
     decision-log entry; the "silently lost" class is hereby empty:
     - **(a) Restoration candidates → 1.1-G with probe:** `error` (library
       authors currently cannot signal their own errors), `gc` and `room`
       (asserted verbatim by product strategy §9), `read-from-string` (the
       only path from data to Lisp values; buffers make it more relevant).
     - **(b) Tombstoned as superseded:** `sector-read`/`sector-write` →
       M65D API (raw sector access below the transaction layer would breach
       the media contract), `ticks` → tick hook (1.1-G).
     - **(c) Deliberately not resident:** `edma` → promised to the future
       `m65-gfx` library behind a safe API, not as a raw primitive;
       `peekw`/`pokew` → cheap riders on the 1.1-G bitwise probe — taken if
       nearly free alongside the bitops, otherwise tombstoned as "compose
       from peek/poke + ash"; `intern`/`read` → deferred with an honest
       entry "not in 1.1, re-evaluate on reader/metaprogramming demand"
       (both raise symbol-economy questions orthogonal to 1.1-B).

## Definition of done

- all three waves are G6-green and `v1.1.0` is tagged and remotely verified;
- EXT has at least the documented target margin of 64 bytes;
- no symbol, name-pool, directory, Bank-0, or EXT floor is violated;
- every capacity delta is authorized and arithmetically closed;
- user documentation covers the banner, shelf flow, product-disk restart workflow,
  help commands, and the complete change list from 1.0.0;
- every documented key binding has a bound test case, and the user-guide
  keymap table is generated from the same source as the binding test list;
- persistent compilation runs through the M65D COW transaction with full
  media binding and denylist; preallocated `fasl*` slots no longer exist;
- the toolchain manifest and verify script are in the tree, the private
  binary archive is uploaded and SHA-verified, and the private LLVM-MOS and
  m65tools directories are removed only after the manifest-fetched double
  build reproduced the sealed product SHAs;
- new platform findings are recorded in the upstream register.

## Housekeeping backlog — repo consistency sweep 2026-07-17

Read-only sweep (four parallel reviews: living docs, config/registries, tree
hygiene, claims-vs-product). Full drafts for the urgent part were handed to
Codex via the owner; this section is the durable record. Nothing here blocks
the wave-1 seal chain except where marked.

### URGENT — documentation truth hotfix (apply outside a running gate pass)

The public repository already carries these falsehoods (verified against
`novemberist/lisp65` main); after the fixes pass the gates, run an
out-of-cadence public hotfix sync with a changelog line.

1. `docs/language-reference.md`: reframe, do not delete — banner must say the
   reference documents the 1.1 wave-1 candidate and that released 1.0.1 lacks
   the items marked "1.1 wave 1" (`filter` line 41, buffer section 59–61);
   **remove `listp` (43) and `value` (46), which exist nowhere** (`value` →
   `symbol-value` if a replacement entry is wanted); add the 1.9 s
   definition→first-call note (dated exception, cure C2/1.2).
2. `docs/project-status.md`: stale since 2026-07-15 ("1.1 has not started");
   update to the real state or replace the "only manual status doc"
   self-declaration with a pointer to this plan.
3. `README.md:122`: roadmap cell no longer promises `unload` for 1.1 and now
   records the owner-corrected product-disk restart workflow; `restart-repl`
   is C2.3 freight (supersedes the 2026-07-17 interim wording).
4. Gate hardening: extend the cross-parity gate with the reverse direction —
   every function name listed in the language reference must exist in
   surface/registry/lib. `listp`/`value` prove this direction is missing.

### Post-seal batch (owner decisions where marked)

- **Evidence archives back in git, mixed mechanism:** 30 tracked tarballs
  (~4.07 GB) under `tests/bytecode/dialect-v2/evidence/promotions/` plus both
  release tarballs in-tree; 11 files via LFS, the rest plain git blobs — both
  contradict the 2026-07-14 policy (archives → release assets; no LFS for
  archives due to quota). Own housekeeping block: migrate to release assets,
  unify the mechanism, wire the policy as a gate. **OWNER-DECIDED
  2026-07-17: yes, retroactively** — all existing archives (including the
  fresh wave-1 seal tarball) migrate, not just future ones; history rewrite
  discipline as in the July repair (verified off-site copies first, tag/seal
  integrity proven after).
  **ESCALATED TO FIRST ACTION AFTER THE WAVE-2 RUN (2026-07-18) — the
  backup path is currently blocked:** the proof repo is 26 commits behind
  (remote branch still at the wave-1 seal `f982ba1`), and the wave-2 R4
  candidate seal sits in the unpushed history as a **660 MB plain git blob**
  (not LFS-covered) that GitHub's pre-receive would reject — a push is
  impossible without the already-decided history surgery, which must not
  run during the acceptance chain. Interim protection is in place: verified
  incremental bundle of all 26 commits at
  `/home/alex/Videos/lisp65-backups/lisp65-wave2-unpushed-20260718.bundle`
  (661 MB, base f982ba1 = on GitHub; owner copies it to a second medium).
  Fixed order after the wave-2 seal, before L-lite starts: (1) history
  surgery per the decided retroactive migration, July protocol; (2) push +
  ls-remote for branch and tags with a completion report; (3) root fixes —
  upstream tracking for the working branch, a `remote_head` field in every
  evidence-binding receipt so "silently unpushed" becomes a red receipt
  line, the sync line as a mandatory report field; (4) a size gate on the
  evidence-commit path so archive blobs can never re-enter git (the July
  ban was policy prose; it regrew through the seal machinery — make it a
  gate).
  **CLOSED 2026-07-18 after the Wave-2 seal:** the final inventory contains
  39 archives / 8,210,842,025 bytes. All bytes were SHA-verified on a separate
  Nextcloud-backed volume and uploaded to private release
  `proof-evidence-wave2-20260718`; GitHub reports matching size and SHA-256
  digest for all 40 assets including the inventory. The deterministic rewrite
  maps recording head `0f7ba4d…` to transport head `6fb5a3d…`, removes every
  `.tar.gz` plus `docs/reference/mega65-book.pdf` from branch/tag history, and
  reduces the largest remaining Git blob below 7 MB. The committed transport
  map preserves recording-commit identities. Archive paths are now ignored,
  materializable SHA-checked caches, and a 100-MB/history-path gate prevents
  recurrence. The new promotion/G6 packer gate records `remote_head` and
  rejects a source commit that is not already its ancestor; historical seals
  remain immutable. **CLOSED completely 2026-07-18:** atomic force-with-lease
  publication moved all 13 branch/tag refs, post-push `ls-remote` matched
  13/13, upstream tracking now follows the working branch, and
  `history-transport-rewrite-push-receipt.json` binds closure commit
  `aa0c90a…`, `remote_head`, the transport map, push plan, and release-asset
  inventory. The standard push ritual verifies that receipt and reports
  `remote_head` plus `sync=local-and-remote-head-equal`.
- **`docs/reference/mega65-book.pdf` (77 MB third-party PDF)** tracked and
  likely publicly synced via `docs/reference/**`: move to a reference
  manifest (URL + SHA) instead of the tree. **OWNER-DECIDED 2026-07-17:
  yes.**
- **Closed 2026-07-17 without changing SHA-bound contracts:** compatibility
  pointers at `docs/bytecode-abi.md` and
  `docs/ap85-native-list-primitives-stop-memo-2026-07-12.md` now resolve the
  stale paths to their canonical contract/archive locations. The frozen
  Dialect V1 contract and pre-1.0 capacity block remain byte-identical.
- **Closed 2026-07-17:** `docs/upstream-issue-drafts.md` and
  `docs/planning/extension-libraries-design.md` are classified in
  `config/document-index.json`. The issue drafts are explicitly excluded
  from the public export until issues are filed; the planning design remains
  private under the standing `docs/planning/**` policy unless separately
  promoted to public documentation.
- `docs/v2-capability-carrier-registry.md`: living doc entirely in German —
  translate or archive per the language policy.
- **Closed by owner correction 2026-07-18:** `docs/decision-log.md` is a living
  append-only chronology, not a frozen pre-1.0 record. It remains at its stable
  path and carries a header explaining that historical language and path strings
  are provenance. The 2026-07-17 archive-move decision is revoked; no
  compatibility pointer or relocation is required.
- `screen-write-string`: still an active registry callprim
  (`config/v2-native-function-registry.json:47`) and defined in
  `lib/stdlib-bytecode-bridges.lisp:33` despite the workbench-profile
  exclusion — confirm the intended consistency (capability declared vs. dead
  code).
- `docs/user-guide.md:1`: title says "1.0", body targets 1.0.1.
- `config/dialect-migration-contract.json:491` cites the superseded root copy
  of the dialect redesign instead of the archive copy.
- Orphan-candidate scripts (zero inbound references found; verify against
  dynamically constructed names before removing): `scripts/deploy-repl.sh`,
  `scripts/push-github-verified.sh`, `scripts/hw-c1-entry-seam-smoke.sh`,
  `scripts/gc-extheap-repro.c`, `scripts/f011-demolib.lisp`,
  `tools/host-lisp/check-stage3-native-smokes.py`,
  `tools/host-lisp/dialect_v2_family_artifact.py`,
  `tools/host-lisp/dialect_v2_r2_decisions.py`,
  `tools/host-lisp/primitive_view_bank_attribution.py`.
- Inverse documentation gap (fold into the 1.1-G metadata contract, which
  makes the function list generatable): `nreverse`, `rplaca`, `rplacd`,
  `gensym`, `prin1`, `macroexpand-1`, `peek`, `poke`, `screen-size`,
  `screen-clear`, `screen-put-char`, and library `format` exist but are
  absent from the language reference.

### Verified clean (no action)

Erratum coverage complete and correct in all living docs; all markdown links
in live docs resolve; ship builder consistently scoped to 1.2; capacity
constants consistent across ~20 config files (EXT floor uniformly 16,384;
REPL_BUF_MAX 192 within the 2..255 contract); no TODO/FIXME debt in product
code; no tracked files matching gitignore; `tools/llvm-mos` and
`tools/m65tools` verified untracked after externalization; no duplicate doc
content; `build/` fully ignored.

## Code sweep addendum — 2026-07-17 (C + Lisp review)

Read-only three-part review (src/ C core; lib/ core Lisp; lib/ide*.lisp).
Hard paths verified clean: GC root discipline, symbol bounds hardening,
F011 unmap pairing on every error return, C1 transaction accounting, cursor
math, keymap value-uniqueness. Findings:

The `disk_source_fetch()` corrupt-final-sector clamp found by this sweep was
closed in the 2026-07-17 stager fix cycle. Its zero-link negative case and the
shared greater-than-255-sector/self-reference/zero-tail chain-walker gates are
bound by the cycle receipt; it is no longer an open backlog item.

### Bug-suspects

1. `lib/ide-ui.lisp:243`: sticky C-x prefix — the unrecognized-key
   fall-through does not clear the prefix state. Fix with L-lite; add to the
   binding matrix.
2. `lib/ide-disk.lisp:482`: goto-line parses only two digits ("150" → line
   15, silently, no digit validation). Fix in wave 3 (1.1-I).
3. `src/attic_library_shelf.c:260` vs `src/io.c:608`: `io_attic_load_lib`
   defined twice with incompatible signatures, separated only by build
   macros; probe build has a silent caller/definition ABI mismatch.

### Structural (with named healing places)

- **IDE magic-number surface, measured:** ~46 distinct raw integers over ~90
  comparison sites, zero named constants/tables; plus 13× repeated
  prefix-reset boilerplate, 8× hand-rolled struct copies, two ~10-deep if
  towers (`ide-apply-command`, `%ide-cmd-action`). **The L-lite generated
  keymap block explicitly absorbs this refactor** (table dispatch kills the
  magic numbers, the boilerplate, and bug 2 in one pass).
- **Core-Lisp two-generation seam:** `m65-disk.lisp` predates the idioms
  (8-deep if-ladders instead of and/member; car-cdr chains instead of nth;
  set-symbol-value on literals instead of setq); `((lambda (x) …) expr)`
  instead of `let` in six files; mixed `'` vs `(quote)` inside
  eval-runtime.lisp; `1+`/`(+ x 1)` split tree-wide. Real duplicates:
  `%v2-reverse-into`≙`%v2-library-reverse-into`,
  `%v2-prepend-reversed`≙`%v2-append2-rev`, `copy-list`/`mapcan` across
  tiers. **Dead files to archive:** `lib/m65-disk-alloc.lisp`,
  `lib/m65-disk-alloc-var.lisp` (superseded prototypes with name collisions
  against live code). Suggested vehicle: a small wave-2/3 idiom-cleanup
  batch, probe-first, behavior-neutral, four-engine parity as gate.

### Confirm-intent questions

- `runtime-main` in the public surface is a text-adventure demo state
  machine — confirm it is the intentional AP8 runtime-export sample.
- `src/vm.c:667` re-interns "shift" on every shifted keystroke; the eval.c
  twin caches the symbol (comment claims they match). Align.
- `load`/`load-lib` return bare `nil` on all failures while M65D has a
  documented numeric status ABI — consider unifying when 1.1-G restores
  `error`.
- `$DE00` window is a raw literal at ~6 sites in io.c while the command
  registers have named constants — name it.

## Work sequence after the wave-2 seal (reviewer plan, 2026-07-18)

Phase 1 — wave 3 / L-lite now: fail-fast parts 2+3 (G5 dry variants, new
cases first) wired this wave; pre-smoke every new behavioral surface; the
single L-lite pass (generated keymap/test/doc tables absorbing magic
numbers, prefix boilerplate, if towers, M-x duplicates + 2-char launcher
fix, sticky C-x, goto-line, C-Space rebind, RUN/STOP cleanup with C-x C-c
exit and migrated B4 buffer-preservation case, RUN/STOP abort as the
matrix's safety-critical entry); the color-scroll rider with its visual
gate; then repin → run → seal. Phase 2 — v1.1.0 release closure: tag +
full push ritual, three-wave release notes, erratum retirements (now that
the user guide describes the new product), known limitations (1.90–1.96 s,
cure C2), generated keymap docs, bundle as release asset, public sync with
changelog. Phase 3 — parallel read-only in wait windows: C2.0 contract
draft (inherited assets per the 1.2 memo) + KERNAL residency audit
(incl. passive STKEY), and the upstream verification round in the
distrobox filling the issue-draft placeholders. Phase 4 — after the tag:
the behavior-neutral idiom/legacy batch (dead allocator files, m65-disk
modernization, orphan-script verification, German capability-carrier doc),
then 1.2 proper per the scope memo (C2.0 → C2.1 refill decision → C2.2
freight → C2.3 cure + restart-repl → while → show → parity revalidation).
Reviewer halts: L-lite receipts, release checklist before the tag, C2.0
draft, batch receipt.

L-lite probe status 2026-07-18: core probe-green (41 bindings / 5 M-x
commands / 6 test+doc artifacts from one generated source; sticky C-x,
multi-digit goto-line, exact M-x matching and the two-char launcher fixed;
C-x Space sets mark; C-x C-c exits preserving buffers; RUN/STOP
editor-keymap removal complete; fail-fast regime wired: six new cases
first, three non-authoritative dry classes, receipt-less pre-smoke).
Core capacity: Bank/fixed overlays/runtime bank/island/installer ±0,
directory −8, peak-EXT −236 B against post-EXT +734 B, +14 symbols,
+182 B name pool, +78 B shelf headroom. **Color-scroll rider host-proven
(17/17) but structurally blocked** (resident +338 B over VMA; runtime bank
effectively 0 B — container 65,472/65,536 with the next 256-aligned
payload at 65,536). **Authorized 2026-07-18: exactly one targeted
near-boundary shaving attempt** on the eight audit-identified slices
(≤48 B into their final stage; ~2 KB parked reserve, first concrete need):
behavior-neutral proven by four-engine parity, varied-relink stability
shown (alignment is part of link identity), one real link with all
budgets, no cap changes, no second tuning round; the opened quantum
belongs to the rider, surplus shavings return unbooked to reserve. On
failure: rider falls to C2, L-lite pins without it, v1.1.0 documents the
color ghost as a known issue with cure reference.

**Attempt result 2026-07-18:** the bounded attempt hit its first red hard
gate and therefore took the automatic fallback. Only audited slices 21 and
32 were touched; slice 21 stayed at 796 B, while slice 32 shrank from 1,037
to 957 B and exposed one 256-B packing quantum. The canonical recursive
product target did not inherit the rider define, however, so the rider
section was empty and the stack-safe-window assertion stopped the link.
Under the one-attempt rule this is a terminal integration failure, not an
invitation to fix forward: all shaving and product-integration changes were
rolled back, the recovered quantum was not retained, and the rider is C2
freight. L-lite proceeds without color-safe scrolling; v1.1.0 must list the
color ghost as a known issue. The failed-attempt arithmetic and claim limits
are bound in the L-lite probe receipt.

**Owner decision 2026-07-18: one NEW authorized rider attempt (option A).**
The first attempt failed on wiring, not capacity (slice 32 provenly shrank
1,037→957 B and opened the quantum; the recursive product target did not
take the rider define — empty rider section: the banner-ordinal class).
Scope of the new attempt: re-apply the proven shave; harden the wiring per
the banner pattern (**rider define mandatory, build aborts on an empty
rider section, negative test with a riderless define**); one real link
with all budgets **including the previously n/a proofs** (four-engine
behavior parity over shaved slices, varied double-link stability); the
opened quantum belongs to the rider, surplus shavings return unbooked.
On failure: final fallback (known issue with C2 cure reference), no third
round. This is a new decision reached at the table the one-attempt rule
forced us back to — not an erosion of that rule; the wiring hardening
remains an earned gate even if the attempt fails.

**Authorized retry result 2026-07-18: final fallback.** The proven Slice-32
shave again reached 957 B and its 25-case installer smoke passed. The first
real integration gate then stopped before the product link: the runtime-bank
layout linter requires an exact unconditional nonempty/size assertion for
every declared slice, while the hardened rider used a conditional assertion
so the C2-deferred product remains buildable without the slice. Under the
explicit first-red-gate rule, this ends the retry: no assertion rewrite, no
negative build, no parity/relink claims and no third round. All shave and
product-integration changes were rolled back; the 256-B diagnostic quantum
is unbooked. The earned binding hardening remains as C2-ready infrastructure
(mandatory-define source guard, conditional nonempty-section linker gate and
mutation-tested host check). L-lite pins without the rider, and v1.1.0 lists
the color ghost as a known issue with a C2 cure reference.

**Repin authorization 2026-07-19:** owner and review authorized the L-lite
repin without the rider at the already measured core deltas (Directory −8,
peak-EXT headroom −236 B against post-EXT headroom +734 B, +14 symbols,
+182 B Namepool and +78 B shelf headroom). The release Known Issue is pinned
in `docs/releases/1.1-wave-3-candidate.md`. Its proposed `screen-clear`
workaround was rejected after source and host-model verification: `scr_clear`
clears character cells and homes the cursor but does not reset color RAM.
The receipt-less pre-smoke therefore covers only the six new keymap/editor
surfaces; the deferred color ghost is a documented limitation, not a pass
criterion.

- **German source comments (owner sweep request, 2026-07-19):** measured
  ~1,311 German comment lines in 46 files — src/ carries 61% (mem.c 110,
  eval.c 106, vm.c 97: the oldest core files), lib/ 18% (lcc.lisp,
  ide-ui.lisp); tools/host-lisp is already clean (1 line). Three-layer
  policy: (1) **go-forward gate now** — added/changed comment lines must
  be English (diff-based check-source addition, conservative matcher);
  (2) **boy-scout rule** — any block touching a file translates its
  comments (behavior-neutral by definition); (3) **phase-4 batch** for the
  stable core files. Key fact: comment changes are binary-neutral (product
  artifacts stay byte-identical), so the batch follows the 1.0.1-light
  pattern — identity gate, no hardware rerun. Exempt as provenance:
  sealed evidence, the decision log, `.de.md` originals.

## C2.2 active implementation ledger — 2026-07-20

The C2D-v5 transient-handle and nested-append contracts remain semantically
green, but no successor to the protected Link-32 product is authorized yet.
The first product-shaped capacity pass stopped on the append and rollback
slices; their authorized semantic reslice produced six cap-green phases and
zero resident transition bytes.  Its next C2J phase then stopped at 2,749 B.

**Authorized validation/reconstruction split result:** the final C2J boundary
is green at 970 B for validation and 1,176 B for reconstruction.  Validation
performs the sole 64-byte Bank-5 read; reconstruction consumes that exact
snapshot through the existing exclusive phase scratch and cannot reread the
journal.  All 20 append phases now fit the immutable 1,792-B cap; the tightest
is `publish_cells` at 1,730 B (62 B headroom).

The serial driver, permanent no-overlay-calls-overlay closure gate and B2
RUN/STOP fixture are also green.  The closure inventory covers 20/20 phases
with zero forbidden edges and four red mutations.  All 18 RUN/STOP injection
cases use the same central C2J landing as ordinary errors, restore unfinished
state byte-identically and preserve committed persistent descendants.  The
session store projects to 59,294/65,536 B across 45 slices (**6,242 B
headroom**); `$e000` shows a 110-B target-object credit and declared BSS and
Island deltas are zero.  The relocatable compiler's 13-B static-stack
diagnostic is recorded but is not a final BSS claim; llvm-mos assigns that
storage at whole-program LTO.  Even that conservative value fits the known
19-B BSS remainder with 6 B; the successor link must remeasure the actual wall.

Receipt:
`c2.2-nested-append-v5-prelink-receipt.json`, SHA-256
`09c3f83f9a698bf1f6ac9a0e50d4c1540238e956f8a4c1eefc65c8b1b49fb3a0`.
Link 32 remains byte-identical and protected.  No successor product link or
hardware run has occurred; the next step is the separately reviewed product
link with all structural and capacity gates fresh.

**Whole-Program correction and coordinated-residency First Red, 2026-07-20:**
the separately authorized Link-33 seed proved that target-object sums were not
capacity evidence under Whole-Program LTO: text, BSS, Island and `$e000` all
diverged at the final layout. Future C2 prelink receipts therefore require one
product-shaped Whole-Program-LTO dry measurement; object sums remain
attribution only. The owner-ordered cold/hot placement then moved C2J abort
control into a 132-B Session overlay, retained the hot handle normalizer and
materializer in the Island, and moved 336 B of emitter roots from `$e000` to a
disjoint Bank-5 DMA region. The one authorized dry link improved headroom by
108 B text, 98 B BSS and 336 B `$e000`, but left three walls red: Bank-0 text
-162 B, ordinary BSS -167 B and Resident Island -228 B; `$e000` is +531 B.
The installer payload was already Boot-family freight and offers zero further
legal Island credit. No product link was run. The outcome is bound by
`c2.2-link33-coordinated-residency-placement-probe-receipt.json`; any next
placement requires a fresh owner/review decision, including a formal window
reopening if that route is chosen.
