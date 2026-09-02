# Work plan — startup, require & REPL experience

Status: **commissioned 2026-08-10 (owner), sequenced strictly behind
the defstruct closing row** — no work on this block starts before the
consumed-span row has closed the escape attribution and its fix
disposition has been taken. Reviewer charter; Codex phases it then.

## The one sentence

Turn waiting into explained, bounded work and shrink what can honestly
be shrunk: price the boot, require and per-form REPL pipelines with the
existing instruments, ship liveness feedback first, then the priced
speed levers — all host-first, zero device until the acceptance
session.

## The owner's problem statement (2026-08-10)

Cold start takes on the order of a minute to a standing REPL; a
single `require` takes seconds; both are one-time costs but a user
cannot distinguish a working system from a hung one. Perceived
hanging is a product defect now that users exist.

The 2026-08-11 owner battery adds the third experience pillar:
**REPL per-form reactivity.** Work inside `(time …)` is healthy —
calls, reads, writes and five allocations complete in 0–1 frames —
while nested or special top-level forms feel seconds-slow before the
timed body can begin. This is interactive pipeline latency, not game
loop or accessor latency.

## Phase A — pricing (the instruments exist)

Bind, with the 1.10/1.11 pricing machinery, where the seconds go:

- Boot: ROM/BASIC splash (machine-owned, bind its share honestly),
  stager transport for the 50,816-byte reset domain, EXT freelist
  build (4,096 two-byte DMAs), `mem_init`, banner/REPL bring-up.
- `require`: resolver index reads (612 Prim-67 reads measured),
  active-universe proof, media staging, decode/publish.
- REPL form: native reader and four-cell LCC-first wrapper; outer
  macro expansion/classification; exact delivered compiler carrier;
  transient emit/append/install/execute/rollback. Keep exact host
  counts, historical projections and target station timings visibly
  separate.

Exit: a priced ledger naming each phase's cost and its owner
(machine vs product), with execution witnesses.

## Phase B — liveness first (the cheap big win)

- Boot progress lines from the first product-owned instruction
  (stager, heap build, library scan, REPL) — plain text, Bank-2/boot
  bytes only.
- `require` echoes its intent immediately ("loading <name>…")
  before work begins; result after.
- A slow top-level form gets a product-owned life sign only if Phase A
  proves the feedback can neither cross nor perturb its transient
  transaction. Otherwise the correct liveness design is a prompt-side
  state transition before RETURN, followed by one terminal result.
- Bounds: zero resident bytes beyond the closed geometry, no timing
  contract changes without re-pricing the session choreography
  constants (the 27.653 s bound and the 45 s window are consumers).

## Phase C — priced speed levers (only what Phase A justifies)

Candidates, each priced before pursued, correctness gates as walls:
freelist build in larger DMA jobs; stager transport width;
prompt-first ordering of non-critical init behind the REPL where the
reset-domain contracts allow; require index batching. For the REPL,
first widen the already proven direct path to semantically complete
forms, then price reuse/amortisation of the transient ceremony without
weakening publication or rollback; reader/compiler work comes only if
the residual ledger justifies it. An honest "no material lever" is a
valid exit.

The release edge is explicit: **no seconds-per-form interaction**.
The permanent performance smoke carries one published direct call,
one nested compiled form, `setq`, allocation inside `(time …)`, and a
string operation. A compiled game-loop hardware row remains a separate
acceptance claim; healthy timed bodies are strong evidence, not that
acceptance by themselves.

## Bounds

House rules verbatim (host-first, witnesses, one-card discipline
where cards arise, sacred publication/journal contracts untouched);
single owner touchpoint at the closing summary; freight joins the
v1.5 train beside trace.

## Third-pillar implementation record — 2026-08-11

The accepted `48164d54` attribution is now an implementation boundary,
not merely a price.  The product's already-proven direct call lane is
recursively closed over bound variable reads and nested published
bytecode calls.  Thus ordinary nested arithmetic, list reads,
accessors such as `(point-y test)`, and list construction execute
without the transient append/install/rollback ceremony.  The
historical literal-only domain remains an exact subset and the VM's
CodeObject header remains the sole arity authority.

The persistent wall is explicit and executable: `setq`, `defun`,
`defmacro`, macro-generated definitions, other special forms,
unbound values, undefined operators and malformed calls retain the
compiler path; every definition still reaches exactly one
`lcc-install`.  Six direct cases, eight fallback/authority cases and
eleven source/contract/publication mutations cover the boundary, including
left-to-right nested evaluation.  The candidate costs two additional
Bank-2 objects, 72 code bytes, 214 external-image bytes and fourteen
directory bytes; resident and transaction-state deltas are zero.  The
Link-95 product-owned `%c2-top-level-macro-p` cell remains published;
the replay is forbidden to satisfy that edge from the compiler's
anonymous `%lcc-macro-p` entry.

The mandated amortisation pricing also has an honest negative result.
The remaining C2 product lane is indivisibly emit → authenticated
append → execute → rollback.  The only existing reusable transient
installer is the compile-time-exclusive legacy lane whose return
would restore the rejected dual decoder/address domain; a mutable C2
slot still lacks address, root, generation and publication ownership.
Skipping append/rollback violates the walls, while batching separate
REPL forms does not improve first-form latency.  Consequently the
safe material delivery is direct-expression widening; `setq` and
definitions remain at the measured 60/62-frame ceremony price.

This is deliberately not relabelled as a fully green experience or
release edge: the requested sub-0.5-second price for ceremony forms
needs a separately owned transient-execution architecture.  No
product link, hardware or release claim is made by this host-first
step.  Permanent authority:
`c2.3-repl-direct-expression-receipt.json`.

## Pillars one and two implementation record — 2026-08-11

The remaining liveness work is host-green under the accepted `236eba09`
boundary.  Cold boot now writes three plain progress lines from the owner that
performs each piece of work: `LISP65: STAGING MEDIA` in the separate AUTOBOOT
stager before its I/O path, `LISP65: BUILDING HEAP` in the disposable boot
overlay before `mem_init` constructs the heap, and `LISP65: LOADING LIBRARIES`
in transported decoder phase 00 before C2D validation or reads.  `scr_init`
later clears these provisional rows; the already delivered Bank-2
`WORKBENCH 1.4.0` banner and `lisp65>` prompt remain the single terminal life
sign.

The stores are behind the explicit successor-product activation seam
`LISP65_STARTUP_REQUIRE_EXPERIENCE`.  Historical and diagnostic media that
recompile the shared stager therefore remain byteidentical; the v1.5 session
builder must opt in deliberately.  A missing opt-in is a red candidate, never
an excuse to reinterpret an old medium.

An owner-shaped target micro-compilation prices the three expansions at 116
stager bytes, 116 disposable-overlay bytes and 133 transported-slice bytes.
They introduce no stored string, mutable state or resident byte.  These are
exact compiler prices for the isolated expansions, not a product-link or
target-wall claim.  The 27.653-second cold-boot bound and 45-second release
acceptance window remain consumers and are unchanged.

The successor-source `require` emits `loading <name>...` plus newline
immediately after its symbol check and before the fast-loaded test, index
parse, resolver or any persistent loader work.  Its producer substitutes the
one accepted definition deterministically; historical product worlds retain
their exact source and media identity until the v1.5 builder opts in.  The
ordinary REPL echo of `t` or `nil` remains the only terminal result.  The real
P0 compiler/VM execution witness covers a fast-loaded request, a slow resolver
request and a non-symbol request; the last emits nothing.  Against the
accepted direct-expression plane the change costs 32 code bytes and 110
external Bank-2 image bytes, with no new object, directory entry, resident
byte or mutable state.

Twenty mutations enforce message identity, owner-relative header reachability,
the explicit successor-product/source activation seams,
volatile screen geometry,
phase order, dynamic library naming, absence of duplicate result output,
zero-resident accounting and both inherited timing/baseline authorities.  The
permanent receipt is
`c2.3-startup-require-experience-receipt.json`.  This remains a host-first
delivery: no product link, hardware acceptance or release claim is made here;
the already planned bundled v1.5 session owns those claims.


## Long-term lever ledger — 2026-08-16 (owner-endorsed direction)

The owner confirms startup and require latency as a priority concern;
the levers, with their honest floor, are recorded here so the block's
Phase C starts from a ledger instead of a memory:

- **Immovable floor:** ~20 s C65 ROM/BASIC splash before the first
  product byte — machine-owned, out of scope forever.
- **Lever 0, free and imminent — the honest baseline:** the next
  owner-observed D1 with the counting ordinal yields the first real
  post-CPU-transport boot duration (the ~6.5 s/read DMA-convergence
  era numbers are obsolete).
- **Lever 1, the big one — the boot snapshot** (registered
  2026-08-16 in the parked-items register): decode/publication leaves
  the cold path; target picture **boot ≈ splash (20 s) + stager/heap
  (seconds) + snapshot load+CRC (seconds)** — half a minute total,
  two-thirds of it the machine's own.
- **Lever 2 — require:** (a) bundle the resolver's 612 single index
  reads into bulk reads; (b) bake standard libraries
  (`string-extra`, `inspect`) into the boot snapshot — require
  becomes instant for them, priced honestly against the name-arena
  headroom contract (32 slots / 384 bytes, never breached); (c) the
  decode share already rides the CPU transport.
- **Lever 3 — small but compounding:** stager bulk-DMA batches for
  the 50,816-byte restage; freelist build in large jobs instead of
  4,096 two-byte ones.
- **Sequencing:** baseline measurement falls out of the pending D1;
  the v1.5 train completes first; then this block's Phase C runs the
  ledger, snapshot first. Target sentence, owner-facing: **under 30
  seconds to the prompt, require felt-instant for the standard
  libraries.**