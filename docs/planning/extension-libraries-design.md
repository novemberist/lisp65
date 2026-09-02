# Extension libraries design: defstruct, loop-lite, format (2026-07-17)

Status: design draft (Claude, architecture review), for owner discussion.
No implementation is authorized by this document; every library follows the
normal probe-first block process when it is scheduled.

## Ground rules

1. **Shelf libraries only.** Nothing here touches Bank 0, EXT residency,
   overlay, island or the boot path. Cost currencies are: directory entries
   (168 free), exported symbols (297 free), name pool (4,594 B), and heap at
   load time. Export-only interning keeps internals free; `%`-helpers stay
   anonymous.
2. **Designed against the real surface**, not against ANSI memory. Native
   special forms are exactly: `quote progn if let let* setq function lambda
   quasiquote and or cond when unless dotimes dolist`. `setf`/`incf`/`decf`/
   `push`/`pop` exist (stdlib-places); `format` exists with a small
   directive set; `gensym`, `&rest`, `&optional` exist; STRICT_ARITY holds.
3. **The dialect stays deliberately trimmed.** These libraries are optional
   vocabulary, not core growth. Full ANSI `loop`, CLOS, `&key` remain out,
   per the standing exclusions.

## C2-era transport and composition doctrine (post-v1.2)

The C2-lite work supplies the operating rules for every future library,
manifest and workbench feature.  These are design constraints, not a claim
that the listed libraries have already been implemented.

1. **Hot execution is Chip-RAM-only.** Attic/HyperRAM is a cold, reconstructible
   shelf source and cache; no library instruction, entry record, literal or
   native slice may depend on an Attic read after publication.  A cold loader
   stages the complete execution plane into Chip RAM, verifies the *target*
   contents, then publishes.  The old marker/busy assumption is forbidden:
   completion is content-defined (normally target CRC), with a fail-closed
   bound.
2. **Transform, verify, seal, publish — in that order.** Region selection,
   absolute source-address derivation and record normalization happen before
   the authenticated record is sealed.  READY or a manifest-generation switch
   is always last.  A consumer never re-derives an identity that the canonical
   emitter can provide, and static plus dynamic paths share one emitter.
3. **Append work is suffix work.** Loading one new library must scan, copy,
   verify, publish and roll back only the new suffix.  Re-reading a static
   prefix is both a latency bug and, for an Attic-backed prefix, a transport
   contract violation.  The journal becomes ACTIVE and content-verified before
   mutation; payload writes converge before publish or wipe; journal CLEAR
   converges last.  Abort leaves byte-identical counters, records and payload.
4. **Regions are explicit data, not hot branches.** If a future manifest spans
   more than one storage region, the emitter resolves the region to a validated
   absolute source address at stage time.  The hot loader remains regions-blind.
   Unknown region IDs and old format versions fail strictly; no dual decoder is
   carried for an unshipped format.
5. **Temperature governs residence.** Library parsing, verification, rollback
   and diagnostics are cold phase code.  Resident state is limited to the
   published family/generation seam and the smallest error transport.  Small
   sequential phases may share one packed slice with distinct entries; this is
   preferred to paying another 256-byte packing quantum.
6. **Errors keep one truth.** The first, innermost status survives cleanup.
   Outer library/manifest layers may attach a symbol, ordinal or phase detail
   through the existing typed channel, but may not replace the cause with a
   generic load error.
7. **Transport assumptions need a metal proof.** A new source/destination
   class gets a fail-fast device smoke before library architecture relies on
   it.  Host fixtures still prove bounds, mutation rejection and publish order;
   Xemu is useful diagnosis, never the authority for DMA visibility.

Capacity accounting follows the same doctrine: avoided future debits are not
free bytes, and only the linked map grants a credit.  The already paired
`random`/ring-buffer proposal below remains the preferred example of sharing a
real substrate rather than introducing parallel state.

## The structural discovery that shapes everything

**Dialect V2 has no early-exit construct.** No `while`, no `block`/
`return-from`, no `catch`/`throw`, no `tagbody`/`go`. All iteration is
bounded (`dotimes`/`dolist`) or recursive (stack-costly on this machine).
Consequences:

- Any macro library can offer only **bounded** iteration; "loop until
  condition" is inexpressible as a pure library.
- This gap will resurface when 1.1-G restores `error` (signaling wants an
  unwind path) and whenever user code needs "search until found" without
  consing intermediate results.
- **Committed 1.2 item (owner, 2026-07-17):** one minimal non-local-exit
  primitive (either a `while` special form or a VM-supported `catch`/`throw`
  pair — not both), designed together with the `error` restoration since they
  share the unwind machinery. Everything below is designed to work *without*
  it, and to get better when it arrives.

## Library 1: `defstruct` (highest value, fully feasible today)

Evidence of need: the IDE hand-rolls the same "rebuild N-slot list with one
field changed" pattern eight times (`%ide-state-with-*`, `%ide-buffer-with-*`,
`%ide-disk-clean-buffer`); m65-disk walks fixed record layouts with car/cdr
chains. `defstruct` is the missing abstraction, and it is a pure macro over
existing primitives (`nth`, `setf`, `list`).

### Proposed surface (lean, Lisp-2, no options soup)

```lisp
(defstruct point x y)              ; positional slots only
;; generates:
(make-point x y)                   ; STRICT_ARITY positional constructor
(point-p obj)                      ; type predicate (tagged head)
(point-x p) (point-y p)            ; readers
(point-with-x p v) …               ; functional update (the IDE pattern!)
(copy-point p)
```

- Representation: tagged list `(point x y)` — `point-p` checks the head
  symbol. Cheap, GC-friendly, printable, works with `equal`.
- `setf` support: register each reader in the places table so
  `(setf (point-x p) v)` mutates in place (one `%putf` entry per slot at
  load time; stdlib-places already supports registration by extension).
- **No** `:constructor`/`:conc-name`/`:include` options in v1 of the
  library. One shape, predictable cost.
- Symbol cost per struct with N slots: 1 (maker) + 1 (predicate) + N
  (readers) + N (with-updates) + 1 (copier) interned **only if the defining
  library exports them**; structs defined inside a library with
  export-only interning pay only for what they export.
- Docstring/metadata: rides the 1.1-G metadata contract (shelf index), zero
  device bytes.

### Optional stage 2: `defstruct/packed` (buffer-backed)

`(defstruct/packed sprite (x 2) (y 2) (color 1))` — fixed-offset byte fields
over a first-class buffer (1.1-E), readers/writers via `buffer-ref`/
`buffer-set!`. This is the DMA-friendly record type for gfx/io work and the
natural companion to a future `m65-gfx`. Needs multiply-free offset
computation (constant folding in the macro expander — offsets are known at
expansion time). Stage 2 only after plain defstruct has real users.

## Library 2: `loop-lite` (bounded clauses only, honest subset)

Full ANSI `loop` stays excluded: it is a compiler-sized macro, and its
`while`/`until`/`thereis` clauses are unimplementable without non-local
exit. What *is* cleanly implementable is the bounded-comprehension subset,
expanding to `dotimes`/`dolist` + accumulator:

```lisp
(loop for x in xs collect (f x))          ; → dolist + reverse-accumulate
(loop for i from 1 to 10 sum (g i))       ; → dotimes + accumulator
(loop for x in xs when (p x) count t)     ; when/unless filters
(loop for x in xs do (side-effect x))
```

- Clause grammar (fixed, no extensions): `for VAR in LIST` | `for VAR from
  A to B [by S]`, then `collect` | `sum` | `count` | `do`, optionally
  guarded by `when`/`unless`. One accumulator per loop. Nothing else.
- Explicitly rejected clauses (documented in the library header): `while`,
  `until`, `repeat`, `thereis`, `always`, `finally`, multiple accumulators,
  destructuring. If the 1.2 non-local-exit primitive lands, `while`/`until`
  become a small additive extension.
- Expansion cost: pure compile-time; runtime is exactly the dotimes/dolist
  the user would have written. No new runtime functions needed except a
  shared `%loop-collect` reverse-accumulator (1 anonymous helper).
- Honest question for the owner: is this worth a library, given `mapcar`/
  `filter`/`reduce` already cover most of it? Value is readability for
  numeric ranges (`from/to`) and mixed filter+accumulate without
  intermediate lists. Priority below defstruct.

## Library 3: `format` extensions (build on the existing library)

`format` already exists (`~a`-class basics, integer→string). Extension set,
chosen for 8-bit usefulness, in priority order:

1. `~x` / `~b` — hex and binary integer output (register work, peek/poke
   debugging; hex is *the* missing directive on this platform).
2. Column control: `~Nd` fixed-width right-aligned integers (tables at the
   REPL; screen is 80 columns, alignment matters more than on ttys).
3. `~{ … ~}` list iteration — replaces the common `mapc`+`princ` boilerplate.
4. `~%` if not already present; `~~` literal tilde.

Explicitly out: floating-point directives (no floats), `~:`/`~@` modifier
combinatorics beyond the above, justification blocks. Cost: string/arith
code in the existing shelf library, no new symbols beyond none (directives
are characters, not symbols) — the cheapest of the three libraries.

## Sequencing recommendation

1. **`defstruct`** — highest observed need (IDE, m65-disk), zero language
   risk, immediate internal consumer: the wave-3 IDE polish could adopt it
   for new code (not a retrofit of shipped code without its own block).
2. **`format` extensions** — cheapest, immediately useful at the REPL,
   pairs well with the 1.1-G error-text library (readable diagnostics).
3. **`loop-lite`** — nice-to-have; decide after defstruct ships whether the
   demand is real (public-repo feedback counts here too).
4. **Language item — adopted into 1.2 planning (owner, 2026-07-17):** one
   minimal non-local-exit primitive, co-designed with the `error`
   restoration (shared unwind), as the enabler for `while`/`until`,
   early-exit search, and user-level condition handling. Recorded in the
   1.2 section of the development plan; product change with the full
   process, not a library.

Timing: design costs nothing now; implementation is post-wave-1 material —
natural slots are alongside wave 2/3 as independent shelf blocks, or the
1.2 ecosystem phase together with parity libraries. None of it may displace
the committed wave content.

## Further candidates (owner-approved list, 2026-07-17)

Design note that governs all of them: CL's sequence functions depend on
`&key` (`:test`, `:key`), which the dialect deliberately lacks. Our variants
take fixed arity — an explicit predicate argument and `-if` variants instead
of keyword combinatorics.

1. **`sort` + `remove-duplicates`** — list merge sort with an explicit
   predicate (`(sort xs '<)`), plus a single equal-based
   `remove-duplicates`. The biggest missing everyday workhorses (dir
   listings, tables, scores). Second priority after `defstruct`.
   **Correction (owner, 2026-07-17): no `-if` variants** — the migration
   contract deliberately consolidated `remove`/`remove-if`/`remove-if-not`
   into `filter` with specified rewrites; retrofitting them would reopen
   the "one form instead of N nuances" decision. The sanctioned road for
   negation is a tiny `complement` library helper, which the redesign text
   itself names.
2. **`parse-integer` + character-class predicates** (`digit-char-p`,
   `alpha-char-p`) — tiny; natural partner of the 1.1-G
   `read-from-string`; also the clean fix for the IDE's two-digit
   goto-line parser.
3. **`random`** — **implementable today in pure Lisp; the bitwise-ops
   dependency is withdrawn** (reviewer + owner, 2026-07-20). Core: additive
   lagged-Fibonacci generator, lags (24, 55) —
   `X(n) = (mod (+ X(n-24) X(n-55)) 16384)`. Addition and `mod` only: no
   multiplication overflow at 15-bit fixnums, no bit operations, period
   ≈ 2^68. State is a 55-slot ring buffer, which makes candidate 6 its
   natural substrate. `(random n)` uses rejection sampling above the
   largest multiple of n (correct for any n ≤ 16384; plain `mod` would
   bias). Seeding layers: explicit `(random-seed k)` for reproducible
   runs (a feature for games — replays, debugging), otherwise mixed
   hardware entropy via existing peek/poke: raster line `$D012`, CIA
   timer bytes, SID voice-3 noise readback `$D41B`, and — strongest —
   frames-until-first-keypress from the typed input queue. When the C2.2
   bitops freight lands, the core may switch to xorshift16 (smaller
   state, faster) behind the same interface; that is an optimization,
   not a prerequisite. Essential for the games niche.
4. **`(time expr)`** — REPL macro over the tick-hook frame source
   (**depends on 1.1-G tick hook**); first question every community user
   asks of their code.
5. **Alist utilities** (`acons`, `alist-update`) — micro addition to the
   existing assoc world.
6. **Ring buffer / queue over `defstruct/packed`** — stage-2 companion of
   the packed-struct idea (event handling, game loops), not standalone.

7. **Fixed-point arithmetic (`fixed`)** — added 2026-07-27 (owner request;
   the `(fac 9)`/economy-simulation thread). Both historical blockers fell
   with v1.2.x freight: `ash`/bitops are hardware-green (Link 67), and the
   MEGA65 hardware math unit ($D768+, already driven via the mega65_math
   overrides) covers the 32-bit multiply intermediates that 15-bit fixnums
   cannot hold. Design questions pinned for the probe:
   - **Format:** 8.8 across a fixnum pair (precise, boxed as a tagged
     defstruct-style pair) vs 7.8 inside one fixnum (fast, GC-free);
     recommendation: start with single-fixnum 7.8 for game math, keep the
     pair variant as stage 2.
   - **Rounding:** commercial (half-up) — the economy-sim use case.
   - **Print/read:** `12.50` both ways; read side rides `parse-integer`
     machinery (candidate 2).
   - **Division** is the honest hard part: HW math unit helps, but sign
     handling and rescaling need the same care the multiply path gets;
     one or two narrow native primitives at most, following the
     `%c2d-byte` minimal-seam pattern — orchestration stays in Lisp.
   - Priority: after `defstruct` and the `random`/ring-buffer pair — it is
     their natural continuation (records, dice, then prices).
   Pure library land: zero resident bytes expected; Bank-2 plus at most a
   leaf-sized native seam, measured not assumed.

Deliberately excluded as decadent for this machine: hash tables (the
redesign decision stands — at our data sizes `assoc` beats any hash
infrastructure), `pprint`, a stream abstraction, pathnames, bignums.

## BASIC 65 parity libraries — status pointer

Fully designed pre-1.0:
`docs/archive/pre-1.0/designs/mega65-basic-parity-libraries.md` (nine
modules, bundle matrix, per-module API drafts, parity stages A/B/C, pilot
order, test strategy). Predates Dialect V2, the shelf, and the buffer type,
so it needs a **revalidation pass** before implementation (capacity model,
tick hook now in 1.1-G, `edma` promised to the gfx library by the
classification session, `defstruct/packed` as the natural sprite/record
carrier). The 1.2 scope memo covers this revalidation as a scheduling item
(owner, 2026-07-17).

## Inspiration from the ancestors (Scheme / Interlisp / Maclisp / Logo), 2026-07-17

Not commitments — a curated watch list for the 1.2 memo and the parity-lib
revalidation:

1. **Pinned TCO (Scheme):** the VM has tail-call paths but no *contractual*
   guarantee. On a 1.5 KB stack budget, a pinned "tail calls are free" turns
   recursion from hazard into idiom, and would inform the 1.2 `while`/named-
   `let` design. Likely zero code cost; real test obligation. Strongest
   candidate on this list.
2. **SRFI-style library specs (Scheme culture):** small numbered specs per
   shelf library — a natural first contribution ramp for the public repo.
3. **`(who-calls 'f)` from the shelf metadata index (Interlisp MASTERSCOPE):**
   the 1.1-G host-generated call graph, exposed in ide-help; zero resident
   bytes.
4. **Polite DWIM (Interlisp):** never auto-correct (fail-closed culture), but
   CL-name hints in the error-text library ("`do` is undefined — see
   `dotimes`/`while`"), fed by the migration contract's rewrite table.
5. **`trace`/`untrace` (Maclisp/LispM):** cheap function-cell wrapping;
   together with `(time)` the complete onboard "why is my program doing
   that" kit.
6. **`m65-turtle` (Logo):** turtle module over `m65-draw` in the parity
   phase — the education/community hook of the 8-bit era.
7. **ISLisp as positioning reference:** the ISO-standardized small Lisp-2 is
   the closest existing norm to Dialect V2 (it has `while`); deviations from
   it should be explainable — most are.

Deliberately not pursued: `dynamic-wind`, continuations, the numeric tower,
closure object systems — infrastructure cost exceeds value on this machine.

## defstruct stage 3 (demand-gated): `defgeneric`-lite — exact-type multiple dispatch

Julia-style dispatch on structs, without CLOS (owner inquiry 2026-07-17).
Feasible and small precisely because our `defstruct` has no `:include`/no
hierarchy: dispatch is **exact-type only**, which eliminates class
precedence, method combination, `call-next-method` and ambiguity rules.
What remains: a table `(type₁ type₂ …) → fn`, `type-of` per argument (car
of the tagged struct; existing predicates for primitives), one assoc, one
funcall.

- `defgeneric` creates the table + dispatcher (one exported symbol);
  `defmethod` adds an entry (methods anonymous).
- Honest cost model, documented like GC hygiene: every generic call pays
  runtime lookup (no JIT specialization as in Julia) — not for frame loops.
- The counterargument stays valid: for a closed set of types, a `cond` over
  predicates is cheaper and idiomatic. Generics earn their keep only for
  **open extension** — library B adds a method for its own type without
  patching library A. That is an ecosystem argument, so the trigger is
  ecosystem demand (public-repo contributions, parity/game libraries; the
  canonical multi-dispatch case `(collide ship asteroid)` lives in our
  games niche).
- Gate (same pattern as unload / import stage 2): ship `defstruct` first;
  build this only when real cross-library polymorphism demand appears.

## IDE concept (1.2-era candidate): definition editing, SEdit-inspired

Owner idea 2026-07-17: `(edit 'hello-world)` opens a narrow buffer holding
just that definition; saving splices it back into its source file and
re-evaluates it.

Key architectural difference from Medley: after the single-engine cut,
definitions exist only as bytecode — source is not retained in the image.
So this is the **file-indexed** variant of SEdit, not structure editing:

- A definition-location registry (name → file + form position), written by
  `load` for user files and carried as an extra column of the 1.1-G shelf
  metadata index for libraries — the same index that feeds `who-calls`
  (Interlisp precedent: file package and MASTERSCOPE shared infrastructure).
- The 1.1-H SEXP scanner finds and bounds the top-level form; the editor
  narrows to it; write-back uses the existing M65D COW save path.
- **Drift honesty is mandatory:** on open, verify the recorded position
  really holds `(defun <name> …)`; otherwise re-scan or fail closed
  ("definition moved") — never splice blind.
- **Dual-commit order is defined:** file COW first, then re-eval; on
  compile failure the file is written, the session keeps the old
  definition, and the user is told explicitly.

Not 1.1 material (waves are committed). A prime 1.2 IDE-era candidate: it
rewards three things already being built (SEXP scanner, metadata index,
COW save) with a capability no other 8-bit system has. The 1.2 scope memo
should list it alongside who-calls as the "Interlisp dividend" of the
metadata work.

Addendum (owner, 2026-07-17) — two further dividends that raise its
priority for the 1.2 memo:

- **Performance mitigation:** editor costs (line model, render hot path,
  scrolling — the known, not-fully-solved IDE debt) scale with buffer size.
  Definition buffers are 10–50 lines, so the common editing case moves onto
  a structurally cheap path instead of optimizing the expensive one — the
  same move the Attic shelf made for media ergonomics.
- **Syntax highlighting returns, honestly tiered:** highlighting was
  disabled for full-file cost reasons. In a narrowed buffer the 1.1-H
  scanner runs over ~30 lines for negligible cost, and the per-cell color
  window already exists (the banner uses it). Policy: full-file buffers
  stay uncolored (documented), definition buffers get highlighting — a
  capability bound to buffer size rather than globally switched off.

Second addendum (owner, 2026-07-17) — platform-native framing and staging:

Definition-granular work is the *native* interaction grammar of 8-bit
machines (`LIST 100-200` in BASIC); whole-file editing is the PC import.
`(edit 'name)` returns to that rhythm with names instead of line numbers as
the address space. Staging that falls out of the BASIC parallel: **stage 1
`(show 'name)`** — display-only, needs just the location registry + SEXP
scanner, no splice-back, no dual commit, no drift-splice risk; it pays for
the registry infrastructure and is immediately useful. **Stage 2
`(edit 'name)`** adds the narrow buffer with write-back on the proven
foundation.

Strategic note (owner, 2026-07-17): the definition-centric workflow is also
the IDE's **fallback line** — if a costly editor feature ever fails its
capacity probe, "REPL + show/edit-definition with narrow, fully-equipped
buffers" is a complete development workflow that needs the expensive
features (large undo, full-text search, smooth large-file scrolling) far
less, because the unit of work is small. The workbench does not have to be
a small Emacs; it can be a large Interlisp. Guardrails: this is a hedge for
future capacity decisions, not a reason to trim the committed wave-3 scope;
and the hedge is only real if its ingredients (location registry, scanner,
`show`) exist before the next big editor capacity decision — schedule
`(show 'name)` early in the 1.2 memo.

Third addendum (owner, 2026-07-17) — the definition algebra:

Beyond `show`/`edit`: `remove-def`, `copy-def` (file A → file B) and
`move-def` complete the set — new *verbs* on the same three-primitive
machinery (locate via registry, extract via scanner, splice via COW save);
Interlisp's file-package operation set (`DELDEF`/`MOVD` lineage), not
feature creep. Hard boundaries: **file-to-file only** — source is not
retained after compilation (deliberate non-decision), so REPL-born
definitions are honestly rejected ("no source location"); and **`move` is a
two-file transaction with defined half-failure semantics**: write B first,
then remove from A — an abort leaves the definition duplicated (safe),
never lost; the reverse order is forbidden (same publish-last thinking as
the M65D directory commit). Strategic link: this algebra is the
ship-builder's little sibling (assembling files from definitions is
proto-packaging) — the 1.2 memo should weigh them together. Staging stays
strict: `show` → `edit` → algebra; each stage proves the machinery for the
next, and the most dangerous verb never rides on the least-proven base.

7. **`input` library — line input for user programs** (owner inquiry
   2026-07-17): the product has public key-level input through `key-event`
   but no `read-line`; programs must hand-roll echo/backspace
   loops. A small shelf library `(read-line)` (optional prompt argument)
   over `(key-event 1)` + the screen driver completes the input pipeline:
   `(read-from-string (read-line "N: "))` is BASIC `INPUT` parity with zero
   resident bytes — the INPUT-side counterpart of the parity blueprint's
   `m65-input` (GET-side) module; `parse-integer` (candidate 2) is the
   third member of the family. Deliberately rejected: exposing the C REPL
   line editor as a primitive (entangled with prompt/history/status
   mechanics; the library costs nothing resident).
   **Surface audit (Codex, 2026-07-18):** `key-event` is present in
   `config/dialect-v2-surface.json` and is the sanctioned API; `read-key`
   and `poll-key` are explicitly restricted compatibility names whose
   migration rewrites are `(key-event 1)` and `(key-event 0)`. There is no
   public-input surface gap.

8. **`fx` — fixed-point over the hardware math unit** (owner inquiry
   2026-07-17; **owner-activated 2026-07-30: named core of the post-1.2.3
   block** — the 1.2.3 device session carries a passive `$D770` probe to
   de-risk the route, see `1.2.3-work-plan.md`): a legacy software fixed-point library exists
   (`lib/stdlib-fixed.lisp`, scale 128, division by recursive repeated
   subtraction). It has a historical pilot manifest, tests and explicit
   Make targets, but is absent from the current Workbench shelf and public
   surface; no product path loads it. Classify it in the two-generation
   cleanup batch (expected: archive with tombstone "superseded by future
   HW-backed fx"). The real item is redesign-reserved: the math unit's
   32-bit product
   yields fixed-point fraction bits for free (read the right result-register
   bytes), so an HW-backed `fx` library belongs in the parity/gfx era as
   the companion of `m65-sprite` and `defstruct/packed`. Format note: the
   fixnum width bounds the format (no full unsigned 16-bit, see the
   `peekw` design stop) — a signed ~8.7 format fits screen coordinates
   with subpixels, which is the actual 8-bit games use case.

9. **`long` — 32-bit integers as a shelf library** (owner scenario
   2026-07-17: economy-simulation games with millions). Honest staircase:
   **stage 0 is no library at all** — scaled units (money stored in
   thousands: fixnum range × 1,000 = ±16.3 million, displayed via format)
   is how the classic C64 economy games (Hanse, Kaiser) modeled it; often
   that is modeling, not a workaround. **Stage 1** when true arbitrary
   values are needed: signed 32-bit as a fixnum pair (hi×32768+lo, range
   ±2 billion); add/sub with carry in Lisp, multiply and divide via the
   math unit's native 32-bit inputs ($D770+, peek/poke from the library);
   `long->string` with thousands grouping for display (a natural `~:d`-like
   format extension). Synergy: `defstruct/packed` gaining 4-byte field
   widths would make longs first-class in game state (packed, DMA- and
   M65D-friendly). Demand-gated like all candidates; the fixnum
   representation is never touched.

## Library composition system (owner direction 2026-07-17): no import boilerplate

Goal: users must not open every source file with dozens of load-lib lines.
Three layers:

1. **`require` (idempotent load)** — already a deliberate deferral in the
   migration contract ("export-only-interning-require"); its precondition
   (1.1-B export-only interning) is satisfied since wave 1. Reviving it is
   redeeming a parked contract item, not new surface. One line per
   dependency, safe to repeat, order-tolerant.
2. **Project manifest + `(load-project "name")`** — one file per program
   declaring required libraries and own sources in order; source files stay
   boilerplate-free. Strategic identity: **this manifest is the ship
   builder's input format** (`ship` needs the same dependency/source
   declaration for tree shaking), and the 1.2 memo explicitly permits
   read-only ship-surface freeze work — defining the manifest format *is*
   that freeze. Built once, it serves session ergonomics immediately and
   packaging in 1.3; no throwaway format.
3. **Unbound-symbol hint from the metadata index** — the 1.1-G index knows
   which library exports which symbol; the error path says "sort is
   provided by library 'seq' — (require 'seq)". Polite-DWIM lineage: the
   error becomes directions, never a hidden auto-load; fail-closed stands.
   True autoload stays a demand-gated later option.

Net user experience: one manifest per project, one require per exploratory
REPL need, zero import blocks in source files.

## Comfort REPL as a shelf library (owner inquiry 2026-07-17)

How much REPL convenience is affordable? Reframed: almost nothing more in
the resident C REPL (192-byte line buffer, deliberately minimal), almost
everything as a shelf library — a Lisp `(repl)` read loop over `(key-event 1)`
that feeds the *same* eval/compile path, paying for features from heap
instead of Bank 0:

- **history** — heap string ring (~2 KB for ten lines), configurable,
  clean OOM message;
- **evaluate only on balanced parens** — the 1.1-H scanner (built for the
  IDE anyway); Return inside an open form continues input;
- **auto-indent for multi-line forms** — same scanner depth × 2 spaces;
- **bonus:** heap-built input is not bound by the C REPL's 192-byte line —
  long multi-line forms become possible at all.

Two hard rules: (1) input layer only, never semantics — hand off to the
identical evaluation path (no second truth source for what a form does);
(2) the native C REPL stays the boot and fail-closed fallback path, like
the disk fallback behind the shelf. Dependency convergence:
`read-from-string` (in build) + input library (candidate 7) + 1.1-H
scanner (wave 3) — timing is post-wave-3 / 1.2 era, a natural neighbor of
`show`.

## Boot init file (owner concern 2026-07-17): batteries included, removable

The modularity concern: core conveniences (M65D, IDE, comfort REPL) hidden
behind manual per-session loads would make every boot a 20-minute setup.
Resolution: **`INIT.L65` on the user's work medium**, auto-loaded at the
end of boot (the existing boot-commit hook that draws the banner is the
place — after stdlib, before prompt). Plain Lisp forms, typically
`require` lines. **The shipped L65WORK.D81 includes a sensible default
init** (m65d, ide, later repl-comfort), so out-of-the-box means a fully
configured workbench; minimalists delete lines and reclaim the resources.
Media policy alignment: user configuration lives on the writable user
medium, the sealed product disk stays configuration-free.

Fail-closed rules: (1) a broken init aborts with a clear message and boots
on to the bare REPL — booting without the work medium is always the
rescue path; (2) init runs strictly after full system boot; (3) the
default init's cost (shelf load seconds, session resources) is documented
in its own comment header where users edit it. Mechanism cost: one small
resident hook ("if INIT.L65 exists on the mounted medium, load it"),
probe-first as always; it is the session-side half of the same pattern
whose project-side half is the manifest (`load-project`).

## Attic usage rule (owner discussion 2026-07-18): cache, never storage

Reset-persistent Attic can confuse the "reset gives me a fresh machine"
intuition. The product's answer is a strict split — **reset = fresh
session, warm cache; power cycle = everything cold** (mental model: a RAM
disk — reset-proof like a disk, power-volatile unlike one) — plus a
platform law for every current and future Attic tenant (shelf, metadata
index, location registry, future gfx assets):

1. **Verifiable:** every Attic structure carries SHA/generation binding;
   stale or corrupt content is detected, never silently reused (the shelf
   catalog is the precedent).
2. **Reconstructible:** a source path always exists; failure falls closed
   to it (disk fallback).
3. **Never the only copy of user data** — power loss must never lose
   anything the user owns. Attic is cache, never storage.

User-facing duties: one user-guide paragraph explaining the split (wave-2/3
documentation rider), and eventually an explicit cold-start valve
(`(restage)` or a boot-held key) so "really everything fresh" is a gesture,
not a power plug. Invisible staleness — a problem that survives reset and
nobody understands why — is the failure mode this rule exists to prevent.

## Design principle (owner discussion 2026-07-18): definition, file, manifest — what is a buffer?

Interlisp could say "the image is the truth, files are generated
serializations." lisp65 structurally cannot: since the single-engine cut,
only bytecode survives `defun` — **the file is the only source truth that
exists.** The resulting model for the definition workbench:

> The **definition** is the unit of thought (show/edit/who-calls; the
> location registry knows where it lives so the user need not). The
> **file** is the unit of truth and transaction (M65D COW, shipping,
> collaboration, backup) — not hidden, but demoted from workplace to
> storage. The **manifest** is the unit of composition. The **buffer** is
> an editor implementation detail, not a user concept.

Files can never fully disappear, for three honest reasons: (1) **load
order is semantics** (compile-on-load: macros before use, defvar order) —
position stays a visible property and in-file `move-def` becomes an
ordering tool; (2) **not everything is a definition** — top-level
side-effect forms (init code, require lines) have no name in the
definition address space; the whole-file view remains for them, or better,
the manifest makes them explicit; (3) **the birth question** — where does
a NEW definition live? Answer: the project manifest declares a default
target file; `(edit 'new)` creates there, explicit override once if
wanted.

Historical warning taken seriously: image-centric systems half-died of
drift, versioning and sharing. This model avoids that constructively —
the file never stops being the truth; we build Interlisp *ergonomics* on
file *substance*. SEdit feel, Git-compatible reality.

Addendum (owner, 2026-07-18) — **both workflows are first-class, forever:**
the traditional path (whole-file editing, plain `(load)`, programs without
manifests, PC-side editing via mega65_ftp or the public repo) stays fully
supported; the definition workbench is additive verbs over the same files,
never a replacement regime. Mixing is the expected normal case, and it is
safe by construction: the location registry treats files as externally
mutable at all times (the drift rule — verify-at-position, rescan or fail
closed — covers internal moves, whole-file edits, and off-device edits
identically). Source files stay plain text with no workbench markers or
special comments — intelligence lives in registry and scanner, never in
the file. Same pattern as the init file and the comfort REPL: ergonomics
offered, never mandated.

Addendum (owner insight 2026-07-18) — **the manifest is the write-target
authority.** Retrospective: the fasl-slot saga ("slot missing", the
erratum, the rejected write-guard probe) was pain of *naming freedom*, not
of writing — and the slots were, in hindsight, a degenerate manifest:
numbered project targets without the concept. In the definition model,
compile persistence targets manifest-declared artifacts by default
("update the project's fasl"); free user-chosen names remain possible
(both-workflows principle) but are the explicit special case, not the
beginner's default. The transactional write machinery (1.1-M) was never
the detour — the definition workbench writes *more* often (every
edit-splice is a COW file rewrite), so media binding and denylist were
foundation for both worlds. Meta-lesson, same family as the u16 catalog:
surfaces shaped before the interaction model is chosen become the model's
debt. This time the model precedes the implementation.

Addendum (owner discussion 2026-07-18) — **how definitions are born.** No
silent auto-persistence: the REPL stays scratch space (sacred), and the
architecture cannot persist after the fact anyway (post-`defun` only
bytecode exists — source must be captured at the *input* while still
text). Staged model: (1) **primary birth path `(edit 'new)`** — unknown
name opens an empty template in the narrow buffer; saving splices the form
to the END of the manifest's default target file (load-order-correct:
new code may use everything before it), registers, evaluates. Same
gesture, transaction and registry as editing. (2) **REPL definitions stay
session-only, honestly labeled** — `(edit 'foo)` on one reports
"session-only" and offers the template as its road home. (3) **Later
bridge, demand-gated: capture + `(keep 'name)`** — the comfort REPL
(input layer!) retains the source text of the last N session definitions
in heap (few KB); `keep` splices the captured text into the default file.
Capture lives in heap, never Attic (it would be the only copy of user
text — forbidden by the Attic rule); power loss loses unpromoted scratch,
as scratch should. The full Smalltalk changes-journal (auto-append every
definition) is deliberately not first: one COW write per definition,
blurred scratch boundary; stays a demand-gated stage three.

Follow-up (owner, 2026-07-18) — **one file is the start, not the fate.**
The default target means small projects live in a single file, which is
the platform-native order (one program = one listing) and is made *more*
tolerable by definition views (nobody opens the file whole). Splitting is
a cheap later harvest, not an upfront duty: `move-def` reorganizes along
real seams when they appear, the manifest can hold many files and change
the birth target anytime, and the 38,400-B source-load limit caps file
growth physically — but crossing it becomes a move-def afternoon instead
of an editor-surgery crisis.

Correction (owner catch, 2026-07-18) — **the real device-side file cap is
the 8,192-B M65D save limit** (`m65-disk.lisp` rejects larger payloads),
not the 38,400-B *load* ceiling quoted above. Asymmetry: the device can
load 38.4-KB files (e.g. PC-authored) but write only 8-KB ones — and since
every edit-splice is a whole-file COW rewrite, the definition workbench
would be read-only on any file over 8 KB. Named prerequisite for the
1.2 workbench: **chunked save** — the COW transaction accepts the payload
in slot-sized chunks from repeated buffer fills (an extension of the
1.1-M buffer-payload seam; the sector-chain machinery already writes
arbitrary lengths), targeting **write parity with the 38,400-B load
limit**. Until then, one-file projects cap at ~8 KB and split earlier
than the previous paragraph suggested.

10. **File management — `delete-file`, `rename-file`, `copy-file`** (owner
    request 2026-07-18): BASIC/DOS parity (SCRATCH/RENAME/COPY are platform
    vocabulary) and workbench substrate (`move-def` needs target creation
    and post-consolidation cleanup). CL-canonical names (`delete-file` and
    `rename-file` are standard CL). All three run *through* the M65D
    transactional layer: chain free + directory retirement, transactional
    entry rewrite with collision check, and — crucially — the **L65SYS
    denylist applies** (file management must not bypass the one protection
    promise). Numeric status ABI, negative matrix (missing file, name
    collision, product medium). No `create-file`: creation-on-save is the
    Lisp way and exists via `m65d-save`. Design note: `copy-file` as
    **chain duplication** (sector-chain copy, new chain, publish last)
    escapes the 8,192-B save limit from day one — 38.4-KB-capable before
    chunked save exists. Delivery target: the 1.2 workbench group (where
    move-def needs it and C2's catalog relief funds the m65d container
    growth); a 1.1 delivery would need a probe against the 367-B catalog
    headroom.

## Owner idea list triage (2026-07-19): remaining Interlisp distance

Owner-collected ideas mapped against the standing agenda. Already covered:
function metadata (1.1-G index + location registry + who-calls),
apropos/describe (J), compiler cross-references (host call graph → J),
Lisp-aware editor (H/L-lite/show), logical-workspace principle (= the
file-truth doctrine; manifest + init file cover the reproducible half).

**Adopted additions:**
1. **Definition history** — best find: the M65D COW machinery already
   creates an old chain on every edit-splice and currently frees it
   immediately; retaining N generations makes `(previous-definition
   'foo)` disk bookkeeping instead of VM magic (Interlisp UNDO on file
   substance). Workbench stage, demand-gated depth.
2. **`(inspect)`** as the unified presentation of five already-planned
   data sources (value cell, function kind/arity, index docs, registry
   origin, call graph). J-era; mostly formatting once the sources exist.
3. **`(save-workspace)`** as a small delta over manifest+init: a
   serializable-subset globals snapshot; behind the manifest format.
4. **Far horizon (post-C2): break loop + VM stack introspection** —
   needs resumable frames and :retry/:return semantics beyond even
   catch/throw; the 1.2 decision (`error` aborts to top level, no
   handlers) deliberately stands. C2's scheduler boundary and unwind work
   are its natural prerequisites.

**Rejected with rationale: symbol properties (putprop/get/remprop).**
Collides with two paid decisions: metadata lives off-device in the
SHA-bound index (putprop-docstrings would re-intern documentation as heap
conses — the exact pattern the metadata contract rejected), and a plist
slot per symbol costs MAX_SYM-fold table bytes. User-level use cases
(game objects, hardware descriptions) are already served: `getf`/`remf`
work on lists, and a game object here is a plist value or a future
defstruct. Docstrings take the already-decided index road.

Tombstone (owner question 2026-07-19) — **heap-image system: never an
option, structurally.** (1) Post-`defun` only bytecode exists — a heap
dump preserves a world that can run but never be edited again; images
and compile-on-load-without-source-retention exclude each other. (2) An
image is an opaque, unverifiable, unversionable blob of session history —
the antithesis of the SHA-reconstructible identity model, with
cross-release format debt (Interlisp/Smalltalk's forty-year pain; the
logical-workspace decision is that lesson distilled). (3) The platform
already ships a machine-image system — the Freezer — for literal
session pause/resume, warts documented (BUFSEL, mount risks). What
legitimately remains is adopted: `(save-workspace)` as the logical,
diffable session record; and image *technique* applied only where it is
sound — pristine boot-state images (restart-repl attic image, C2's
immutable code images), the one state that is source-reconstructible and
SHA-bindable by definition. Images of the beginning of time: yes. Images
of the middle of history: never.
