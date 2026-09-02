# Gate and tool register

Status: **current** — what must keep running, and what is merely kept.
Created by the housekeeping block, 2026-07-29.

This register exists because of a recurring failure family that cost this
project four separate incidents: **an artifact existing is not an artifact
working.** Gates checked sources instead of packed artifacts; a chain failed
to build for two days and therefore proved nothing; a smoke test built its
variant but never executed it; a lesson lived in a comment instead of a
gate. The countermeasures are recorded here so they cannot quietly decay.

## The three aggregators

Everything that must keep running hangs below one of three targets. If a
check is not reachable from one of these, it does not run.

| Aggregator | Direct prerequisites | Purpose |
|---|---:|---|
| `check-source` | 100 | Source-level contracts, inventories, comment language, bound-artifact parity |
| `workbench-product` | 5 | Product build; pulls the completion canary, the ASM/ABI self-test, interrupt ownership, the GC EXT-DMA lane and the freezer authority gate |
| `equivalence-check` | 1 + canary | The full equivalence lanes across both main routes |

The Ship Builder adds four named targets; the machine graph, rather than this
human summary, remains the authority for the total target count.

## The execution witness

`equivalence-completion-canary-check` is the answer to "a chain that does
not run proves nothing". It requires the chain to report a **non-zero and
expected** number of actually executed lanes and cases — the current
authority is **11 lanes, 447 executed cases**. A build failure, a skipped
variant or a silently dropped lane makes it red rather than absent.

`workbench-product` requires the canary, so the product cannot be built on
the strength of a chain that did not execute.

## Named permanent gates worth knowing by name

These were each created after a real incident and each closes a class:

- **Bound-artifact source parity** — compares what is *packed into the
  product* against the source, not the source against itself. Created after
  the stale LCC carrier shipped a compiler whose primitive table predated
  `intern` and `%c2d-byte`.
- **Profile parity** (bidirectional) — the product must carry exactly the
  contracted dialect switches, neither fewer nor more. Created after 27
  links were built from a profile with none of the eight switches set.
- **Section inventory, profile-derived** — the set of ELF sections is
  derived from the canonical profile, not from a frozen list of names.
- **ASM/ABI gate, ELF-derived prüflings** — every assembler function with C
  callers is checked automatically; the set is derived from the ELF, so a
  new leaf cannot escape by not being on a list.
- **Z-boundary gate** — both directions: every `STZ` consumes `Z = 0`, and
  every handwritten return or ASM-to-external call delivers `Z = 0`.
  Interrupt entries separately prove restoration of the interrupted Z.
  Created after the 65CE02 `STZ` = *store Z register* semantics, documented
  in a comment since link 19, corrupted a DMA length at link 71.
- **Orphan handling** — `--orphan-handling=error` plus a six-name
  allowlist; every section has a declared fate or the link fails.
- **Interrupt ownership** — the masked-source policy, with the register
  read-back proven on hardware.
- **Mapped Bank-2 service ownership** — inspects the generated linker script
  and a final linked micro-ELF against the independently reviewed Halt-1
  constants. It owns the 12-byte compiler-stack arena, constant `$C354`
  overlay floor, convergence state/ZP, 98-byte MAP facade and 1,499-byte
  Bank-2 service; executes MAP/unmap and cross-map IRQ cases, replays the
  8/8 convergence plus 15/15 mutations and the 13-site/11-consumer DMA sweep,
  and rejects derived-floor, orphan, ordinary-BSS, missing-route, overlap,
  recursive-bootstrap, missing-unmap, hidden-IRQ and self-oracle mutations.
- **Full-map ownership** — replaces llvm-mos' inherited `c.ld` ordinary
  outputs with the Phase-B-owned rodata/binding/data/BSS/noinit chain, while
  explicitly preserving the already-proven PRG header, ZP initializer LMA and
  text predecessor. It routes all 84 Phase-A inputs exactly once, executes
  distinct data-copy/BSS-zero/noinit/static-stack/heap/overlay sentinels,
  requires two byteidentical clean micro links and two byteidentical relinks
  of the SHA-bound v1.7 LTO object, and rejects 14 ownership/oracle mutations.
  The product-object replay is permanently non-promotable: zero product
  compiles, zero fresh WPLTO and zero hardware contacts.
- **v1.2.4 fx source/artifact equivalence** — executes the real Q8.7
  implementation from source and from its emitted artifact against an
  independently modeled math-register file. It requires positive I/O
  witnesses and rejects scale, rounding, result-byte, transaction-ownership,
  packaging and built-but-not-run mutations. Target measurements must place
  every math-unit input write and every result read in one Lisp evaluation:
  the REPL renderer uses the same unit, so returning to the prompt between
  writes and reads invalidates the experiment.
- **v1.2.4 `(time form)` source/artifact equivalence** — executes the
  high-low-high frame-counter read, modulo delta, borrow, wrap and explicit
  16,384-frame overflow boundary in both source and emitted-artifact lanes.
  It proves single evaluation and result preservation, requires zero
  resident/native dependency, and rejects 11 mutation families.
- **Ship Builder contract, sample fleet and reproducibility** — parses the
  public `(ship "program" :entry 'main)` form with the canonical reader,
  resolves the L65P-v1 dependency lock with the canonical resolver, builds
  and host-executes all three contracted D81 samples, reopens all 27 required
  media members, and compares two independent builds byte-for-byte.  The
  stricter release form performs both builds from independent fresh source
  archives.  Its positive witness reports three sample executions and two
  reproducibility executions; an image that merely exists proves nothing.
- **Require after ordinary Session appends** — compiles the current resolver,
  appends two ordinary definitions through the real compiler/emitter/C2D
  host path, and then executes `require` against product-bound package media.
  It preserves the v1.2.4 `t`/`nil` H1 receipt as the historical negative
  case, requires `t` after the Option-A contract fix, and rejects malformed
  source ordinal, generation, code base, zero size and indexed-size cases.
  The paired hardware row remains mandatory for the next acceptance session.
- **Complete Bank-5 reset-domain restage** — requires media role 2 to expand
  the canonical 33,840-byte C2D prefix into the full 50,816-byte reset
  domain, with the entire inactive suffix and all 64 C2J bytes zero, before
  the authenticated Boot scratch is staged and before the product can make
  READY true.  It rejects prefix-only restage, stale suffix/C2J bytes,
  prefix drift, reversed write order and a missing staging transform.  The
  execution witness reports seven cases.  Created after the Link-84
  RUN/STOP capture proved that stale C2J bytes correctly drove the journal
  validator fail-closed.
- **Standalone Ship boot inheritance** — starts the host model with clock and
  input explicitly unarmed, executes the real Ship I/O seam, and requires a
  Ship-owned raster-IRQ counter behind the logical `$FF83/$FF84` surface to
  make three successive unit advances.  Progress is synchronized and sampled
  against the complete 9-bit `$D011/$D012` high-to-low transition; the target
  installs a 23-byte IRQ wrapper, acknowledges its owned VIC source, reads
  back `$D01A` and the vector, and still chains the inherited KERNAL IRQ.
  The host executes two negative witnesses (a one-shot twitch and a stagnant
  clock) before the recurring positive witness.  It also executes all 312
  starting phases of the real 312-line raster: the complete oracle passes
  312/312, while the former `$D012`-low rule passes 0/312.  Twenty-two
  mutations bind that distinction plus the target object and relocations.
  Created after physical samples exposed first that the earlier `$A1/$A2`
  gate reproduced the runtime's false clock assumption, then that a synthetic
  wrap callback omitted the ninth raster bit.  Standing rule: a gate may not
  use either the code assumption or a simplified register model as its oracle.
- **Streamed code-window content convergence** — routes all four VM
  object/header/payload refill paths through one bounded seam in both Ship and
  C2-lite Workbench.  An immutable source-probe/marker chain first makes one
  source byte independently visible, finds the first byte that differs from
  the current window, and the single primary submit is accepted only when
  that destination byte matches before the 64-frame boundary.  The resident
  witness is one byte; host/device lanes retain the exhaustive whole-window
  comparison.  Non-convergence fails closed, with no primary resubmission
  loop.  The host model executes eight timing/wrap cases and the gate rejects
  fifteen mutations, including loss of either product, completion-metadata or
  shared-descriptor oracles.  Created after Link 90
  contact 8 fetched the pre-refill byte `$0B` although the refill metadata
  named the correct `$0024` window.
- **Mapped Far-Service assembly equivalence and state ownership** — keeps the
  host-green C convergence bodies as reference authority while executing the
  independently linked 874-byte assembly artifact at the contracted
  `$78B2`/`$02B8B2` identity.  Both D700 and D705 entries run all eight
  convergence cases (16 artifact/reference comparisons); the inherited 15
  class mutations and ten assembly-seam mutations stay sharp.  The enclosing
  v1.7 state gate executes all 72 inventoried state inputs exactly once,
  stack shapes 3/4/6/12 plus the rejected 13-byte case, ZP capacity and
  capacity+1, and two clean byteidentical assembly links.  This closes the
  optimizer-sized far-body class without calling padding, partition steering
  or a current LTO output an identity.  Targets:
  `c2-mapped-far-asm-equivalence-check` and
  `c2-v17-state-ownership-phase-c-check`.
- **Defstruct stopped-state diagnostic identity** — derives one explicitly
  non-promotable sibling from the exact Link-82 ELF/PRG and unchanged library
  medium.  It binds every resident/window byte difference, two unowned code
  caves and one 65-byte ordinary-RAM record; retains the last two refill views;
  and places the independent opcode read in the dispatcher before diagnostic
  bookkeeping, where stale streamed code cannot skip it.  The explicit
  `c2-v16-defstruct-phase-c-check` executes six synthetic R/A/I/G stopped
  states and rejects 26 sentinel, tag, oracle, placement, helper-input, quiet-policy
  and unclassified-outcome mutations.  Its D1 side reads the pre-key buffer
  directly from the live heap/string state and rejects a non-empty context
  fixture; the single post-key read either proves all 64 characters or retains
  the stopped queue/GC/PC packet.  It is intentionally not a
  `check-source` prerequisite because its released Link-82 inputs are
  materialized forensic authorities rather than fresh-clone source inputs.
- **Defstruct D2 launch-choreography closure** — closes the BASIC-launch
  ambiguity that consumed the original Phase-D contacts without reaching a
  measured form.  The corrected rider submits one virtual RETURN and proves
  entry with an enumerated RAM store after the complete `$00/$01` RAM-mapping pair;
  it no longer depends on monitor-breakpoint retention.  Its screen classifier
  accepts `run:`/`RUN:` case-insensitively but rejects BREAK, monitor and
  register-display markers even when RUN remains in scrollback.  The dry-run
  binds the now-exhausted virtual strand, rejects 18 closure mutations, eight
  entry-witness mutations and three launch-screen mutations, and changes zero
  product bytes.  Its current appointment is fail-closed at zero virtual and
  zero physical contacts after the corrected physical launch failed to reach
  a REPL; D2 was not entered.  Target:
  `c2-v16-d2-choreography-check` (explicit because it binds materialized
  Link-82 forensic inputs).
- **Defstruct D2 physical-launch fallback** — closes the virtual launch strand
  after its sixth setup First Red.  It removes only the boot-only entry hook
  and its temporary record routine from the non-promotable sibling, restores
  the canonical 65-byte R/A/I/G reset, and leaves every measurement hook
  unchanged.  Nine mutations reject retained bootstrap code, measurement or
  product drift, promotion, any reopening of the virtual loop, and the observed
  binary-stage failure whose BASIC end pointer did not enclose the loaded PRG.
  The runner separates cold staging from the owner's physical `RUN`+RETURN and from the
  one-shot quiet continuation; the latter repeats all context asserts, the
  120/180-second silent windows and three stable record reads.  Target:
  `c2-v16-d2-physical-fallback-check` (explicit materialized Link-82 input).
- **Defstruct boot-order and durable-witness closure** — binds the consumed
  `$E18D/$E1BF` samples to the exact Link-82 boot graph and rejects the
  impossible reading “root marking before the EXT freelist build”.  It derives
  the diagnostic-only `$B5C3` witness from the 96-range placement inventory,
  the 72-input state census and the 1.8 simultaneous-live ledger.  The
  selftest overlays every post-ownership owner range on the fixed witness in
  turn and requires every ownership collision to fail; the fourth
  decision-table row remains fail-closed.
  Target: `c2-v16-boot-order-durable-witness-check` (explicit materialized
  Link-82 input; it authorizes no device contact).
- **Defstruct mapping-aware stopped data + boot-GC closure** — separates
  instruction identity (CPU-resolved view plus owner binding) from data
  identity (same-stop mapping capture plus physical RAM-underlay read).  Its
  six-row plan rejects ROM-overlaid raw data, missing mapping state, wrong
  physical banks, and physical-underlay code claims.  The same closure parses
  the SHA-bound Link-82 C2D/shelf pair and exact boot sources: 340 materialized
  roots plus one macro wrapper leave 683 of 1,024 EXT-first cells, while the
  banner allocates none.  It therefore closes healthy pre-prompt collection
  as unreachable without promoting the single `$3B0D` snapshot to a liveness
  or culprit claim.  Target: `c2-v16-mapping-data-boot-gc-check` (explicit
  materialized inputs; 16 rejected mutations; no contact authorization).
- **Defstruct durable boot-progress appointment** — derives a non-promotable
  Link-82 sibling by changing exactly the two operand bytes that redirect the
  `$202C` entry stamp from the overwritten `$C07A` record byte to owned
  `$B5C3`.  It binds `$B9F0/$B9F1` (`gc_runs`) to the linked 16-bit increment
  at every collection entry, requires reset-sentinel readback after every
  load and before physical `RUN`, and rejects fourteen identity, oracle,
  choreography and claim mutations.  Target:
  `c2-v16-durable-progress-check` (explicit materialized input; one physical
  row only under the separately recorded owner authorization).  After that
  one-shot row was consumed, the target became a compatibility alias of the
  result closure; the historical preparation receipt is never rebound merely
  because the plan gained its result section.
- **Defstruct durable-progress result closure** — binds the consumed fourth
  row: three post-entry root-scan PCs alongside reset-valued `$B5C3` and
  zero-valued `gc_runs`.  It independently checks the staged payload and both
  prelaunch sentinel readbacks, rejects eleven overclaim mutations, and keeps
  product-hang, allocation-loop, progress, F018B, R/A/I/G and new-contact
  claims closed.  Target: `c2-v16-durable-progress-result-check` (explicit
  materialized device evidence; CPU remains stopped).  The row was subsequently
  consumed by the identity/view attribution below; this target is now its
  compatibility alias, and the historical receipt is never rebound for later
  append-only plan growth.
- **Defstruct durable-progress identity/view attribution** — binds both
  candidate `$E000` byte streams and proves that the captured PC/X signature
  belongs to the MEGA65 KERNAL's descending table-search loop, not the product
  root scan.  It also binds the pinned monitor contract: `m0000xxxx` reads
  unresolved physical bank-0 memory, while only `$0777xxxx` requests the
  executing CPU's mapped view; the historical runner discarded the MAPH/MAPL
  and ROM-enable fields supplied by `r`.  The control prompt remains a
  separate successful-launch postcondition and is not promoted into proof of
  diagnostic entry.  Fourteen mutations keep root-scan, product, F018B,
  R/A/I/G and contact claims closed.  Target:
  `c2-v16-identity-view-attribution-check` (explicit materialized forensic
  evidence; desk-only, CPU remains stopped).
- **Defstruct corrected-view launch correction** — consumes the follow-up
  contact through `$0777xxxx`, retains MAPH/MAPL and the ROM-enable field in
  every sample, and resolves ownership before symbols. The three stopped
  samples show a non-product C65/BOOT high-MAP context, but the historical
  runner entered the monitor and sent `t1` immediately after the owner's RUN,
  with no bound quiet interval. The launch outcome is therefore explicitly
  undecidable; the former no-handover claim is withdrawn. Twenty-one mutations
  keep physical-view, mapping, owner, early-observation and product/F018B/
  R/A/I/G overclaims closed. Target: `c2-v16-corrected-view-result-check`
  (explicit materialized forensic evidence; CPU remains stopped).
- **Defstruct corrected-view quiet choreography** — binds the owner-authorized
  one-shot repeat. Capture invocation must follow the physical
  launch, then performs no serial/monitor access for at least the bound
  27.653-second cold-boot upper bound. The sample floor is
  `27.653/32.653/37.653` seconds; an early `t1` and a revoked authorization are
  both loud mutations among twenty rejected cases. Target:
  `c2-v16-corrected-view-quiet-preparation-check` (explicit owner-authorized
  one-contact preparation; no Lisp form or R/A/I/G measurement authorized).
- **Defstruct corrected-view quiet result** — closes that consumed contact
  against the previously bound live high-MAP E000 authority. It requires the
  owner's physical `READY.` → RUN/RETURN → monitor observation, the complete
  27.653-second quiet floor, three CPU-view samples, `$8300/$82A0` mapping and
  three reset `$D7` entry witnesses. The observed stream must equal the
  historical non-product C65/BOOT stream and differ from the diagnostic
  window; its exact backing image remains deliberately unnamed. Eighteen
  mutations keep product-hang, exact-ROM, F018B, R/A/I/G, form and recontact
  claims closed. Target: `c2-v16-corrected-view-quiet-result-check`
  (explicit materialized forensic evidence; CPU remains stopped).
- **Defstruct physical-RUN handover desk boundary** — compares the green
  physical control with the consumed quiet diagnostic launch. It proves an
  identical BASIC program and `$2023..$202B` bootstrap prefix, fixes the first
  executable delta at `$202C`, and requires the three reset entry witnesses.
  The runner comparison names the diagnostic prelaunch monitor crossing as
  the only unpaired post-READY, pre-owner action. Seventeen mutations keep it
  a leading setup hypothesis rather than a causal claim and authorize no
  contact. Target: `c2-v16-physical-run-handover-desk-check` (explicit
  artifact/runner closure).
- **Defstruct control-shaped launch discriminator** — binds the authorized
  one-shot physical launch using the diagnostic bytes but the control's
  pre-owner choreography. After the checked READY screen, the owner RUN is the
  next device action: no prelaunch monitor-sync, `t1`, read or `t0`. The first
  later monitor entry remains behind the 27.653-second quiet floor. Fourteen
  mutations include source-level reinsertion of the forbidden crossing and
  early-`t1`; no measured form or R/A/I/G row is authorized. Target:
  `c2-v16-control-shaped-discriminator-check` (explicit owner-authorized
  preparation; CPU will remain stopped after the device row).
- **Defstruct control-shaped discriminator result** — closes the consumed
  no-prelaunch launch against the historical live-E000 owner class. Removing
  monitor-sync/`t1`/reads/`t0` did not change the physical monitor/no-entry
  outcome; the prelaunch-monitor hypothesis is therefore falsified. The
  residual boundary is target-side and before `$202C`, but remains
  unattributed. Eighteen mutations reject restoration of the hypothesis and
  every product-hang, exact-backing, F018B, R/A/I/G, form and recontact
  overclaim. Target: `c2-v16-control-shaped-result-check` (explicit consumed
  device/desk closure; CPU remains stopped).
- **Defstruct residual-launch boundary attribution** — closes the diagnostic
  bootstrap mechanism without another device contact. It requires the exact
  physical payload through `$C25C`, the BASIC end pointer `$C25D`, the
  `$202C` call and `$C03F` body, then independently proves that ROMC is still
  enabled when the call fetches its target. The control clears ROMC in low RAM;
  the diagnostic moved that clear behind its own C000 call, so the CPU sees C65
  ROM instead of the delivered witness routine. Twenty-three mutations keep the
  absent post-RUN PC, physical-vs-CPU delivery distinction, diagnostic-only
  scope and no-contact/no-fix boundary honest. Target:
  `c2-v16-residual-launch-boundary-check` (explicit materialized forensic
  evidence; CPU remains stopped).
- **Defstruct bootstrap visibility and ROMC repair** — structurally walks the
  linked low-RAM bootstrap with inherited `$D030` state and rejects every
  transfer into a mapped region until its visibility has been established.
  The repaired diagnostic keeps `LDX #$44; STX $D030` at `$202C`, moves the
  `$C03F` call to `$2031`, and replays only the displaced four low-RAM bytes
  before stamping `$B5C3`. A linked-image mutation restores the historical
  hidden-callee form and must fail. The gate also re-runs the seven Phase-C
  witnesses and 26 Phase-C mutations, compares PRG/ELF bootstrap and record
  bytes, independently models semantic equivalence through `$2035`, and
  requires exact control identity outside the enumerated diagnostic delta.
  Target: `c2-v16-bootstrap-romc-repair-check` (explicit materialized
  forensic evidence; zero product bytes and no contact).
- **Linked format-decoder closure** — reads the final product through
  `ElfTruth`, requires exactly one linked C2 phase for every contracted slot
  and one L65R catalog/record verifier, and binds that inventory to the
  strict L65S-v4, C2I-v2, C2D-v6 and L65R-v4 artifact headers and profile
  selection. Created when housekeeping found that the no-dual-decoder rule
  had never been checked in the *linked* product. It rejects eight mutations
  and is invoked by `workbench-product` after the canonical product exists.
- **Archive gate** — blocks archives and oversized blobs at index, commit,
  history and push. Verified working: of 41 promotion archives, zero are
  tracked.

## Tool classification

Machine-readable: `config/tool-classification.json` (generated, with
method and counts).

| Class | Count | Meaning |
|---|---:|---|
| live | 500 | Reachable from `Makefile` / `mk` / `scripts`, directly or through Python imports |
| probe | 406 | Built for a single investigation and not reachable from the build |

**Probes are deliberately neither moved nor deleted.** 214 of them are named
in bound, immutable receipts; a receipt whose citation target has moved is a
broken citation, which is worse than an untidy directory. The classification
makes the distinction legible; it does not act on it.

## Bound-artifact parity: the fresh-clone question, decided

`c2-bound-artifact-source-parity-check` verifies parity between the *bound
product* and the sources — but its input is a **link-chain output**, so on a
fresh clone (or after `build/` is cleaned) there is no artifact to check.
For a while that made `check-source` permanently red, which trains people to
ignore red. Three dispositions were on the table; the owner commissioned the
resolution on 2026-07-30 and a combination of 1 and 2 landed:

- **`check-source` (default form).** Parity is a property of the
  (source, bound artifact) *pair*. When the product-manifest entry point
  named by the profile authority does not exist — the cleanly absent,
  fresh-clone state — the gate reports **`NOT CLAIMED`** with the producing
  step named, and exits green *without asserting parity*. This is not a
  silent skip: the status line is explicit, and the assertion the gate would
  have made is owed by the acceptance chain instead. Any *partially* present
  state (entry point exists, pieces missing or stale) stays a hard failure —
  the stale-carrier incident had everything present, only old, and that
  detection is untouched.
- **Acceptance chain (required form).** A new
  `c2-bound-artifact-source-parity-required-check` treats absence as a hard
  failure and is a prerequisite of `r4-product-candidate-check`: no product
  candidate enters acceptance without current source parity. Deliberately
  *not* wired inside `workbench-product` — a link cycle repairs a stale
  binding by building first and rebinding after, so a mid-build hook would
  be a chicken-and-egg block.
- **Teeth:** `absent-invariants=3` in the selftest — required mode refuses
  an absent product; the tier receipt resolves through the carrier's own
  bound suite reference (new layout) *and* the legacy directory convention;
  a carrier with no tier receipt at all stays red.

Two defects fell out of implementing this:

1. **The old red had quietly changed meaning.** The gate derived the tier
   receipt path by directory convention (`<carrier-dir>/compiler-tier/`),
   and the phase-V layout moved the receipt next to the suite. So the
   "precondition" red on this tree was also a layout mismatch — with a full
   build present, the gate was still red. Fixed: the receipt is now located
   through the suite reference the carrier itself binds, which is authority,
   not convention.
2. **With that fixed, the gate immediately did its real job:** it reports
   `product-bound manifest hash drift: …/libs/ide.manifest.json`. True — the
   bound product authority is the 07-29 random-while link, and the 07-30
   comment/while cycles regenerated the library manifests underneath it.
   This is the named current `check-source` red on this tree; it resolves
   when the next product link cycle rebinds the profile authority, and it
   stands on the release-rule exception list until then.

## `check-source` on a clean tree: every red, sorted by cause

The housekeeping block ran `check-source` to completion and attributed every
red. Nothing here is a guess: each "pre-existing" verdict was checked by
running the same target in a detached worktree at `b8405551`, the head on
which v1.2.2 was published.

### Pre-existing — red at the released head too

Verified failing identically at `b8405551`:

- `c2-bound-artifact-source-parity-check` — at the time attributed as the
  fresh-clone precondition; the 2026-07-30 disposition (previous section)
  later showed the red on built trees was also a tier-receipt layout
  mismatch, now fixed.
- `dialect-v2-prelude-evidence-selftest` — `v1 macro source/contract drift:
  missing=['while']`. The contract lists `while` among the v1 macros that
  migrated to v2, but none of the three v1 macro sources
  (`lib/prelude-m1.lisp`, `lib/stdlib-control.lisp`,
  `lib/stdlib-places.lisp`) defines it any more.
- `v11-surface-delivery-parity-check` — `random` and `random-seed` are in the
  language reference with no surface, registry or library delivery.
- `bytecode-p0-omission-contract-check` — `%lcc-proper-list-p`, `%lcc-rel8`
  and `%lcc-while` are omitted without being declared in
  `tests/bytecode/demos/p0-demo-suite.json`.
- `v11-function-metadata-selftest` (`current public metadata coverage drift`)
  and `workbench-ux-harness-selftest` (`exact latest REPL result must pass`),
  both downstream of the same `while`/`random` surface state.

**This is the finding that matters more than any individual red:
`check-source` was not green on the head that shipped v1.2.2.** The contracts
for the v2 `while` and `random` surface are committed; the sources that would
satisfy them are not. This block deliberately repaired none of it — that is
implementation work, not housekeeping.

**Root cause, established 2026-07-30:** the release chain never asks. R4, R5,
R6, G5, G6 and the public clean-build gate require the equivalence chain and
the product build, but no rule anywhere requires `check-source` for a
release. Four red source gates therefore shipped without anything lying —
the chain reported exactly what it was asked to check.

**Binding rule (owner decision, 2026-07-30):** every future release plan's
pre-chain hygiene phase (the A1 step) requires **`check-source` green, or a
named, reasoned exception list reviewed at the Class-C halt A**. A red that
is neither fixed nor named in that list blocks the release. The documented
`c2-bound-artifact-source-parity-check` precondition (red before any link by
construction) is the standing first entry of that exception list until its
own Class-C disposition lands.

### Caused by the block, and resolved

The block deleted the 11 GB local materialization of the 41 registered
promotion archives, on the strength of
`config/promotion-archive-policy.json`, which declares
`archive_transport.local_materialization = "ignored-cache-verified-before-use"`
with `config/evidence-archive-assets.json` as the authority. All 41 register
SHAs are covered by that inventory. Two consumers, however, required the
local copy to be present — so the policy line and those consumers
contradicted each other, and the deletion exposed the contradiction rather
than creating it.

Owner disposition, 2026-07-30: **resolve the contradiction**, do not
re-download. Both consumers now treat the local copy as the cache the policy
says it is, and neither lost a tooth:

- **`tools/host-lisp/dialect_migration_contract.py`** (`dialect-migration-selftest`, now
  green). `_sealed_snapshot_contains` no longer aborts on the first absent
  archive; it verifies every *present* archive exactly as before and reports
  the absent ones by id. A new fallback, `_git_history_contains`, resolves
  historical evidence out of this repository's own history of that exact
  path — which is what made the red disappear entirely: the one piece of
  evidence that needed the fallback,
  `tests/bytecode/dialect-v2/evidence/r3/product-block-receipt.json` at
  `fa0db9eb…`, is committed at `2362a3d0`. A sealed archive is a snapshot of
  the tree at a promotion's source commit, so for git-tracked evidence the
  repository proves the same thing — without a downloadable asset.
  Teeth, proven by `archive-cache-invariants=3` plus two new mutations:
  an absent archive whose SHA is in *neither* the tree nor the inventory is a
  hard failure; a *present* archive whose bytes do not match its bound SHA is
  still tampering, not a cache miss; and the git fallback rejects a SHA that
  was never committed at that path.
- **`tools/host-lisp/r6_g6_seal.py`** (`r6-g6-registered-seal-check`, **still red, by
  design**). This gate does not only check identity: it extracts the archive
  and re-runs the isolated offline verifier from inside it. There is no
  substitute for those bytes, and skipping the step would turn the gate into
  a no-op — the exact failure family this register exists to prevent. So the
  failure stays; it now only *says what to do*, naming the archive, its
  inventory coverage and its destination path. Four archives (3.1 GB of the
  original 11) are what this gate needs; materializing them is an owner call,
  and until then the red is honest rather than mysterious.

## Permanent clauses of the 2.0/2.1 era

Added by the post-v1.5 housekeeping block, 2026-08-18.

These clauses were each bought with a red card and then lived where they were
born -- as appendices inside the era's rolling work plans, which is exactly
where nobody looks them up. Each row names the rule, the gate that owns it,
and the mutation that proves the gate still bites. A clause without an owning
gate is a wish, not a rule.

| Clause | Owning gate | Mutation that proves it bites |
|---|---|---|
| **Born derived.** A new checker derives its expectations; it never pins an address, size, count, set or opcode that the world can move. Opcode claims are semantic equivalence, never mnemonic identity. | `c2-v21-pinned-constant-sweep-check` | A pinned constant reintroduced into a checker is rejected |
| **Additive provenance.** New provenance is added alongside the existing authority; it never substitutes `authority.kind`. | `c2-v20-vma-golden-review-rebind-check` | A rebind that replaces rather than adds is rejected |
| **Real consumers, actual output.** A schema gate executes the real consumer against real producer output, never a synthetic fixture. | `c2-v21-postlink-schema-check` | `replace-actual-output-with-synthetic` and `skip-real-consumer` are rejected |
| **One name, one owner, one body.** A symbol, module or directory has exactly one owner and one implementation. | `c2-elf-truth-migration-check` | A second hand-written ELF column parser outside the pin is rejected |
| **Structural enumeration.** Every medium builder is enumerated; discovery runs independently of the registry, so a new builder or a stale registry both fail. | `c2-media-builder-closure-enumeration-check` | A builder present in the tree but absent from the registry is rejected |
| **Sealed evidence is read in its own era.** A sealed receipt binds provenance at the commit that sealed it, never at the working tree. Live content checks stay live. | `evidence_era.py` selftest, plus every gate that imports it | An era view that collapses onto the living source is rejected |
| **Claims stay inside their rows.** A gate's message states the act it actually detected, not a stronger act it merely correlates with. | `c2-elf-truth-migration-check` | Naming a column tool while delegating to an accountable parser must not be reported as hand parsing |
| **Comment language.** Source comments stay in the project's committed baseline language. | `comment-language-check` | A comment in another language is rejected |
| **Every document is classified.** Every tracked `docs/*.md` file carries exactly one class in the document index. | `document-index-check` | An unindexed tracked document and an indexed missing document both fail |
| **Raw access is ownership.** A placement composes allocated ELF sections with fixed-address data accesses, named capacity, range writers/wipes, mapping aliases, loader initialization and temporal scratch ownership. An allegedly inactive claimant is proved inactive; section absence alone never establishes vacancy. | `c2-v200-symbol22-first-fault-repricing-check`; `c2.3-v2.0-symbol22-first-fault-product-card-r1-owner-red.json` | A section-only map that hides the 64 active terminal-return-guard accesses, an omitted claimant class, or an assumed-inactive guard is rejected |

## Permanent clauses of the input-fidelity/v1.6 era

Harvested by the post-v1.6 housekeeping block, 2026-08-25. These clauses
apply beyond the Comfort branch that bought many of them. The selected v1.6
product does not contain Comfort, but the gates remain permanent because the
failure classes are architectural rather than feature-local.

| Clause | Owning gate | Mutation that proves it bites |
|---|---|---|
| **Instrument law.** A claim-bearing instrument has a named atomic origin, proves that observing does not change the observed path, and is removed by default after attribution. | `c2-v160-bound-origin-measurement-result-check`, `c2-v160-refill-boundary-witness-media-repair-check`, `c2-v160-clean-product-candidate-check` | A non-zero/unbound origin, a witness that changes the product path, and diagnostic freight surviving in the clean product world are rejected |
| **Single owner and defined-state handoff.** A shared resource has one owner at a time; transfer to the next owner leaves the resource in a stated condition. Separate models of each writer or reader do not prove the composed resource. | `c2-v160-queue-single-owner-replacement-check`, `c2-v160-display-ownership-card-check` | An armed `lisp_poll` queue read, a missing legitimate public reader, prompt/cursor separation, and stale framebuffer residue are rejected |
| **Final-world and shipped-byte claims.** A product claim is proved on the final linked image, and its chain continues through every packaging hop to the byte delivered on media. | `c2-v160-hybrid-live-stack-replacement-check`, `c2-v160-refill-boundary-witness-media-repair-check` | Isolated-object/synthetic-profile substitution and null or partial packed facades are rejected |
| **Phase-owned guards and outputs.** A guard belongs to the phase whose invariant it protects; every writable output belongs to that phase's root. A later read-only phase asserts the produced identity rather than replaying a pre-production absence guard. | `c2_v160_input_fidelity_phase_guard_replacement_card.py`, `c2_v160_input_service_hybrid_phase_output_replacement_card.py` | A production guard fired during scope, a scope without SHA identity, a report in a sealed root, and an output outside its phase are rejected |
| **Enforce what is recorded.** Every claim-relevant receipt field is an asserted wall, not passive telemetry. | `c2_v160_input_service_hybrid_final_world_card.py` | `recorded-loss-not-enforced` is rejected alongside absent final-ELF consumer membership |
| **Forecasts are floors.** A price is a lower bound that the linked result may improve on, never an equality the result must hit. Actual capacity remains candidate-derived. | `c2-v160-active-frame-liveness-check` | Falling below the forecast and restoring an equality pin are rejected; exceeding the forecast remains green |
| **Whole-program text prices are linked facts.** A fragment or micro-prototype may select a candidate, but only the final linked candidate can establish ordinary-text capacity. | `c2-v190-native-prompt-editor-r5-pricing-check` | A fragment price presented as final capacity, a fixed facade address, a VMA/LMA split and failure to follow final text growth are rejected |
| **Coverage is derived, not enumerated.** Populations, features, mutations, callers and additive components come from their live graph or registry. A hand list is not a completeness proof. | `c2-v160-boot-refill-selector-bypass-mutation-set-resume-check`, `c2-v160-boot-refill-feature-union-resume-check` | A hidden graph consumer, omitted active feature, removed required mutation, outside-owner caller and unregistered additive component are rejected |
| **Domain-aware addresses.** In overlapping MAP arenas an address alone is not an identity; analyses key by section/mapping domain and address. | `c2-v160-boot-refill-selector-bypass-mutation-set-resume-check` | An address-only MAP-range edge and a path reaching a consumer under the wrong mapping domain are rejected |
| **Declared-width shared state.** A state cell observed by assembly declares the width its ABI owns; optimizer-provided narrowing is borrowed, not contractual. | `c2-v160-item1-only-candidate-check` | A widened `lisp_toplevel_active`, an allocating alias, and a non-identical owner/alias address are rejected on the final ELF |
| **Diagnostic freight lives in diagnostic worlds.** Product acceptance contains product and durable health telemetry only. One-shot witnesses, installers and latches remain sealed evidence outside the selected product. | `c2-v160-clean-product-candidate-check` | Any refill-witness feature, source, section, token or trace origin surviving in the selected product is rejected |
| **Anti-rabbit-hole triage.** A clean-product finding receives one bounded classification: daily-use blocker gets at most one fix round before descope; rare/cosmetic findings become Known Issues. No new instrument or higher release bar appears inside that decision. | `c2-v160-post-release-housekeeping-check` and the sealed v1.6 finish-plan acceptance | A housekeeping device/product claim is rejected; the selected v1.6 world proves Comfort and diagnostic freight absent rather than carrying an open diagnosis into release |

## Permanent clauses of the v1.7-v1.9 composition era

Harvested by Block 2.5 after v1.9.0.  Each rule below is tied to the
sealed receipt that bought it and to the living gate that keeps it sharp.

| Clause | Owning gate and sealed evidence | Mutation that proves it bites |
|---|---|---|
| **Bank-2 capacity is composed ownership, not aggregate tail.** Every physical byte has one named owner; capacity is the largest contiguous hole in the composed map. | `c2_bank2_composed_ownership.py`; `c2.3-v1.7-ide-idle-blink-product-card-r10-receipt.json` | A static-plane/far-service overlap, missing mapped tenant, unnamed congruence gap or unnamed end reserve is rejected |
| **MAP placement is page-congruent at placement time.** Every shared MAP offset is derived and divisible by `$100`; unencodable placement never reaches tuple emission. | `c2_bank2_composed_ownership.py`; `c2.3-v1.7-block3-r10-map-geometry-preflight-red.json` | `non-page-congruent-LOADADDR` and `non-page-congruent-offset` are rejected |
| **Emitted MAP tuple equals final `LOADADDR`.** The tuple and tenant LMAs consume one linker authority; neither may move alone. | `c2_v17_ide_idle_blink_product_card_r10.py`; `c2.3-v1.7-ide-idle-blink-product-card-r10-receipt.json` | `move-LMA-without-tuple-follow` and `mutate-tuple-without-LMA-reason` are rejected |
| **Delivered instrumentation proves consumption, not only arming.** The final client must take from the armed ring; `taken = 0` is red even if capture stores every event. | `c2_v190_block_a_delivered_consumer_repair.py`; `c2.3-v1.9-block-a-delivered-consumer-repair-r8-receipt.json` | The delivered-queue predecessor reproduces `raw=seen=stored=94, taken=0` and is rejected |
| **Whole-program text prices are final-link facts.** A fragment price may choose a candidate, never certify capacity. | `c2-v190-native-prompt-editor-r5-pricing-check`; `c2.3-v1.9-native-prompt-editor-card-r5-placement-pricing.json` | Fragment-as-final capacity, a fixed facade VMA and failure to follow final text growth are rejected |
| **One surface has one positioning model.** Control bytes position only if the delivered driver interprets them that way; prompt, input and cursor share the framebuffer owner's coordinates. | `c2_v190_native_prompt_editor_display_repair_r7.py`; `c2.3-v1.9-native-prompt-editor-display-repair-r7-receipt.json` | The device state with prompt at row 9/column 25 and cursor at row 24, plus split positioning ownership, is rejected |
| **Candidate inputs prove bound equals consumed; both populations are derived.** Consumer nodes come from the build graph. Authority-derived constants come from perturbing every scalar leaf of the explicitly bound candidate manifest through the real definition renderer; active force-includes, output roots and LOADADDR geometry join the same materialized inventory. No historical authority is a silent default: an unbound authority fails before compilation. | `consolidated-consumption-authority-check`, `c2-v200-symbol22-build-id-rebind-check`; Block-2.5 consolidation and `$22` build-ID rebind reports | A missing real flag, path/value or LMA/tuple divergence, newly added product without a receipt, omitted manifest constant/source consumer/category, stale manifest path/content, wrong output root and missing explicit authority are rejected |
| **Every prelink pin has one authority.** Literal pins and inherited candidate-dependent closures are enumerated together before a WPLTO. | `consolidated-consumption-authority-check`; `c2.3-v1.9-native-prompt-editor-display-repair-r7-era-conversion.json` | Omitting any of the 7+6 members or losing a closure's era policy is rejected |
| **Every public name owns a domain row.** The released product profile, including CALLPRIM tombstones, executes six representative domain vectors for every metadata-public symbol. | `public-surface-domain-audit-check`; `config/public-surface-domain-contract.json` | A missing public row, changed cell or invented delivered primitive is rejected before any domain repair |
| **Public vocabulary is inventoried before it changes.** Capability names and implementation/era names remain distinct, and the migration policy follows the newer owner decision rather than an obsolete alias assumption. | `public-naming-audit-check`; `config/public-naming-audit.json` | A missing public function, an implementation name relabelled as capability or restored mandatory-alias policy is rejected |

### The era-bound provenance rule, in full

This is the clause the 2026-08-18 block had to add, because four gates had
already been paying for its absence.

A sealed receipt witnesses the world of its own run. When such a receipt binds
a path in the *working tree* -- its own driver, a sibling gate's source, a
release contract -- then every later edit to that path drifts a record that did
not change. The project paid for that drift twice with rebind receipts
(2026-08-14, 2026-08-16), and the second rebind then drifted in turn: the
treadmill has no last step.

The rule: **provenance is read at the sealing commit; content is verified
live.** `tools/host-lisp/evidence_era.py` is the single body. A gate names its
own `SEAL_ERA_COMMIT` -- the commit that last wrote its receipt -- and binds
identity through the shared helper. Whatever the gate actually gates (media
artifacts, counts, geometry, readbacks, schema conformance) keeps running
against today's tree, unchanged.

Two corollaries, both bought on 2026-08-18:

- **A historical gate never polices living documentation.** The v1.1.2
  split-media gate required the user guide to state that tracing is not
  delivered. That was true of the v1.4.0 world and stayed true until v1.5.0
  shipped `trace`/`untrace` -- at which point the gate was demanding that
  today's documentation deny a shipped feature. The guide and the language
  reference are now read at the commit that reclosed that medium, mutation
  base included.
- **A sealed snapshot is not a content authority.** The post-link schema
  receipt is sealed inside a card's final red, so it cannot follow the tree --
  but what it gates is schema conformance, not file bytes. Identity and every
  consumed and produced key still compare exactly; the digest of a file that
  is revalidated on every run no longer has to match the snapshot.

**Known scope, stated rather than implied:** 274 tool sources bind their own
driver into a receipt. The rule bites only when such a tool is edited, so the
remaining sites are latent, not broken. They are not converted pre-emptively;
each converts when it is next touched, and new gates use the shared helper
from the start.

## How to keep this register true

Add an entry when a gate is created that closes a class. Do not add an entry
for every `*-check` target — 364 of those exist and the aggregators already
own them. When a gate is retired, say so here and say why; a gate that
disappears without a line in this file is exactly the failure this register
was built to prevent.
