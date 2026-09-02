# C2-lite reconstruction memo

Status: **Class-C reviewed; Option A and Bank 2/3 direction selected; paper only**

Date: 2026-07-21

Baseline: Link 35 product SHA-256
`54c731559fdb72d5d1cb8478b9da7e78a422741e4e5267d64b07fe4c6f763a65`

This memo answers the automatic C2-lite disposition triggered by Link 36. It
authorizes no source change, generated artifact, compiler run, product link,
hardware run, capacity debit, promotion or product claim. Link 36 remains a
historical First Red and Link 35 remains the immutable rollback line until a
later, separately approved successor passes its complete gate set.

Bound inputs:

- [Link-35 artifact replay receipt](../../tests/bytecode/dialect-v2/evidence/architecture-blocks/c2.2-product-link35-dma-completion-first-status-pure-replay-receipt.json)
  for product identity and resident walls;
- [current substitution artifacts](../../build/c2.2/substitution/substitution-artifacts.json)
  for the six-image shelf, C2D and capacity dimensions;
- [DMA completion contract](c2.2-runtime-overlay-dma-completion-contract.md)
  for the L10 hardware finding and nine transport seams;
- [KERNAL-unmap contract](c2.2-kernal-unmap-contract.md) for the historical
  115/63-byte floors and automatic C2-lite trigger; and
- [freight triage](../../config/c2-freight-triage.json) for the unchanged
  owner-approved 3/3/3 order.

## Decision summary

“No runtime refill” has two materially different meanings:

1. **No Attic refill at runtime:** retain the 128-byte VM code window and the
   fixed native-overlay VMAs, but stage every execution-time source into
   ordinary Chip RAM before READY. Refills still exist, but they are
   Chip-RAM-to-window copies. Cold catalog/metadata verification and persistent
   session artifacts may remain in Attic.
2. **Literal no-refill:** execute bytecode and native overlay code directly
   from banked storage. This removes the copy window itself and changes the VM
   fetch, call/return, mapping, interrupt and Freezer contracts.

The recommended C2-lite direction is **meaning 1**, subject to a mandatory
fail-fast hardware proof of Chip-RAM-to-window DMA completion before any
product implementation. Meaning 2 is a new execution architecture, not the
bounded successor to Link 35.

Meaning 1 is acceptable only if it removes **all Attic reads from the
execution-time path**. Moving only the 34,403 code bytes while leaving entry,
literal or native-slice refills in Attic would preserve the L10 failure class
under a new label and is therefore rejected.

## 1. What “no runtime refill” means

### 1.1 Option A — Chip-RAM-backed windows

The existing logical model remains:

```text
BCODE -> generation-bound C2D execution record -> 128-byte VM window
L65R slot -> generation-bound native record     -> fixed overlay/Island VMA
```

The source domains change:

- normalized static and session bytecode lives in one session-immutable
  64-KiB Chip-RAM code plane;
- the mutually exclusive Boot and Session L65R families share a second
  64-KiB Chip-RAM native plane;
- C2D remains in Bank 5;
- the complete L65S shelf and persistent session C2I artifacts remain in
  Attic as cold, reconstructible source artifacts;
- no VM call, return, opcode-window refill, literal materialization or L65R
  phase load reads Attic after READY.

This is deliberately called **no runtime Attic refill**, not “no refill.” The
two copy windows survive and so do their range, generation and identity
checks. What retires is the slow and hardware-disproved Attic visibility
assumption in the execution path.

#### Execution-complete C2D view

The current hot path cannot merely redirect its code DMA. It still reads the
C2I metadata header, 16-byte entry record and literal descriptors from Attic.
C2-lite must make the already mutable C2D plane sufficient for execution:

- each unchanged-width 10-byte C2D entry record carries image, Chip-RAM code
  offset, code length, resolution base/count and generation;
- a resolution word denotes either a direct Lisp value or the width-neutral
  positive-even surrogate `(root_ordinal + 1) << 1`. Heap-valued descriptors
  keep their sole mutable value in the canonical root array, so a legal direct
  resolution may never use that positive-even pointer shape;
- the cold decoder still validates the complete immutable C2I descriptor
  stream before it emits either representation;
- the hot materializer reads only C2D and the Chip-RAM code plane. It never
  reopens C2I metadata in Attic;
- static and dynamic code use the same code-plane allocator and the same C2D
  execution record. No second emitter, decoder or hot directory is permitted.

The exact field order and a C2D version decision belong to the later contract,
not this memo. The width-neutral target is a feasibility condition: if the
execution record requires a wider fixed-capacity C2D array, the resulting
Bank-5 debit returns to Class C before implementation.

**Post-review preflight correction.** The original draft's high-bit
distinction is not
collision-free in the actual `obj` ABI: BCODE occupies `$c000..$dffe`, SYMI
occupies `$e000..$fffe`, and negative Fixnums also carry bit 15. The current
composition alone contains 637 compiler-proven direct BCODE resolutions in
`$c1f4..$c496`. The approved
[C2-lite execution contract addendum](c2-lite-execution-contract-addendum.md)
therefore uses no bit-15 tag. Its positive-even surrogate uses the object shape
that can only denote a heap pointer; heap-valued descriptors already live
exclusively in the canonical root array. The correction changes no product
byte.

#### Publication and reset

Static code is staged and content-verified into the code plane before the
initial C2D header publishes. A session append copies normalized code to the
current code watermark, verifies the destination, writes inactive C2D records,
then publishes the C2D header and exports last. Rollback restores the watermark
and leaves any later bytes unreachable. A generation change invalidates both
code-plane watermarks and both native-family bindings before restaging.

The Chip-RAM copy is a cache, never the only persistent copy of user data.
Persistent C2I remains on medium/Attic under the existing COW and identity
rules.

#### Physical-bank prerequisite

The current project map exposes only one uncommitted 64-KiB bank: Bank 1. Bank
4 owns the heap/arenas, Bank 5 owns the mutable session plane, and the present
strategy marks Banks 2/3 ROM-taboo. The runtime-overlay “Bank 3” tag is only a
format tag; its actual storage is Attic at `$08000000`.

Option A needs two simultaneous Chip-RAM tenants after READY:

| Tenant | Current bytes | 64-KiB headroom |
|---|---:|---:|
| normalized bytecode code plane | 34,403 | 31,133 |
| Session L65R native plane | 60,062 | 5,474 |
| **active total** | **94,465** | **36,607 across two banks** |

The 15,605-byte Boot family and the 60,062-byte Session family may share the
native bank because their existing generation/phase-3 contract makes their
lifetimes mutually exclusive. They may not share the bytecode bank: bytecode
and Session native slices are concurrently live.

The reviewed memory-map/Freezer/reset audit selected **both** ROM-taboo banks:
Bank 2 for normalized code and Bank 3 for the lifetime-exclusive native
families. The hardware pre-smoke passed both on core `git-03b24c6b`. The
historical format tag remains non-evidence; the audit and metal result are the
authority. Bank 1 is therefore not consumed or treated as fallback.

#### Mandatory fail-fast hardware pre-smoke

Before a product source change, a standalone, non-product proof target must:

1. write identity-bound patterns into each proposed Chip-RAM source bank;
2. poison a Bank-0 target and launch the exact production DMA job shape;
3. consume the destination immediately after the launch routine returns;
4. repeat code-window lengths and boundary cases, including 1, 7, 16, 127 and
   128 bytes, and representative L65R slice/Island transfers;
5. run with the owned IRQ/frame source active and perform one Freezer
   roundtrip;
6. prove the Boot-to-Session native-plane handoff and old-generation
   invalidation; and
7. record the exact core identity and per-case completion/latency observation.

Acceptance is byte/CRC equality on the immediate post-return read for every
iteration. A delayed convergence, marker-only success or retry loop is a red
result. C2-lite exists to remove the runtime convergence driver, not to move it
to another source bank. Xemu may provide an explicitly non-authoritative dry
variant, but only the device decides.

### 1.2 Option B — literal no-refill, fully banked execution

Option B removes both copy windows. Bytecode fetches directly from a banked
code plane, and native phases execute through bank mapping rather than being
copied to their fixed VMAs.

This is not a smaller Option A:

- the VM PC becomes a bank-aware execution address or gains a separate active
  code-plane identity on every call frame and return;
- `PUSHLIT` can no longer consume the window's patched literal-shaped bytes;
  it must resolve through C2D in the opcode path;
- nested calls, tail calls, closures, non-local exits and stale generations
  gain new bank-state invariants;
- the 53 native slices currently overlap at one VMA. Direct execution requires
  a new mapping/relocation contract rather than the existing copy-overlay ABI;
- owned IRQ/NMI, RUN/STOP, MAP state and Freezer return must preserve or rebuild
  the active execution mapping; and
- all four engines and the bytecode ABI/documentation need a new parity proof.

It could theoretically retire the 128-byte VM buffer and its three owner-tag
bytes, giving a **gross 131-byte ordinary-BSS opportunity**. That is not a net
credit: bank-aware PC/mapping state and direct literal lookup have not been
priced, and no existing product-shaped link proves them.

Option B therefore needs a C2.0-class address/execution addendum, an isolated
hardware fetch/mapping proof and a new substitution plan. It is a valid future
architecture or fallback if Option A's Chip-RAM DMA premise fails, but it is
not recommended for the bounded C2-lite recovery.

### 1.3 Comparison and recommendation

| Property | Option A: Chip-RAM windows | Option B: fully banked |
|---|---|---|
| BCODE/C2I surface | retained | execution interpretation changes |
| 128-byte VM window | retained | retired |
| fixed native overlay VMA | retained | replaced by mapping model |
| hot Attic traffic | forbidden | forbidden |
| required Chip-RAM | two 64-KiB tenants | at least the same storage, plus mapping |
| new hardware truth | bank-to-window DMA completion | banked fetch/mapping, IRQ and Freezer |
| product risk | bounded source/metadata substitution | VM and native execution rewrite |
| recommendation | **probe first** | do not select without Option-A red |

Class-C review selected Option A together with the Bank-2/3 premise. The
fail-fast pre-smoke subsequently passed; the separate contract addendum owns
the remaining format decision.

## 2. Vacancy inventory and capacity credits

### 2.1 Authoritative baseline

Link 35, not the green terminal WPLTO seed and not Link 36, is the only product
baseline:

| Wall | Link 35 headroom |
|---|---:|
| ordinary Bank-0 text | 19 B |
| ordinary Bank-0 BSS | 174 B |
| fixed hot block | 33 B |
| Resident Island | 7 B |
| `$e000` window / active floor | 115 B |
| Boot L65R store | 49,931 B |
| Session L65R store | 5,474 B |
| tightest 1,792-byte runtime slice | 31 B |

The rejected Link-36 package would have consumed 52 B of `$e000`, 31 B of the
fixed block and 7 B of ordinary text for the shared convergence driver. Those
bytes never entered a product. They are **avoided debits**, not reclaimed
product bytes.

### 2.2 Formal floor restoration

The 63-byte floor was authority for the unpromoted terminal WPLTO/Link-36
design only. Its self-destruction clause selected C2-lite before a Link-36
product existed. C2-lite therefore restores the active product authority to
the Link-35 **115-byte floor** and records 63 B as historical rejected-design
geometry.

This restoration is explicit in the future contract/config update. It creates
no 52-byte product credit because Link 35 already has all 115 bytes. A later
C2-lite link may measure additional `$e000` headroom through retired hot
helpers, but no such gain is prebooked here.

### 2.3 Measured hot-path surface, not yet a net claim

The Link-35 ELF provides a bounded gross inventory of functions touched by the
redesign:

| Wall | Link-35 object | Bytes | C2-lite disposition |
|---|---|---:|---|
| Bank-0 text | `c2_product_entry_read` | 887 | replaced by Chip-code/C2D-only refill seam |
| Bank-0 text | `vm_code_load` | 38 | retained or replaced by one Chip-bank DMA seam |
| Bank-0 text | `rtov_dma_submit_wait` | 39 | hot use retires; cold need must move to Boot or remain measured |
| `$e000` | `c2_product_entry_length` | 176 | folded into execution-complete C2D lookup |
| `$e000` | `c2_entry_records` | 615 | replaced by the C2D execution record |
| `$e000` | `c2_stream_product_child_value` | 536 | descriptor read retires; resolution/root lookup remains |
| `$e000` | `c2_source_read` | 123 | forbidden hot; cold stage/append form remains outside the hot closure |
| Resident Island | `c2_stream_product_materialize_entry` | 1,051 | replaced by C2D-only materialization |

These are gross current footprints, not additive credits. Several functions
contain shared cold work, and every replacement has a real cost. Only a
product-shaped Whole-Program-LTO probe may state the net Bank-0, `$e000` or
Island dividend. The memo reserves none of it for freight.

The per-wall accounting position is therefore:

| Currency | Exact baseline/avoided debit | Gross redesign surface | Creditable now |
|---|---:|---:|---:|
| ordinary text | 19 B headroom; 7-B Link-36 debit avoided | 964 B named above | **0 B** |
| ordinary BSS | 174 B headroom | Option A retains the 131-B buffer/tag set | **0 B** |
| fixed block | 33 B headroom; 31-B Link-36 debit avoided | no new C2-lite tenant selected | **0 B** |
| Resident Island | 7 B headroom | 1,051-B materializer | **0 B** |
| `$e000` | restored 115-B authority; 52-B debit avoided | 1,327 B hot record/child/length code, plus 123 B shared source code | **0 B** |
| Attic L65R storage | not a limiting wall | 15,605 B Boot + 60,062 B Session cease to be runtime sources | informational only |
| new Chip planes | no Link-35 tenant | 34,403 B code + 60,062 B Session native | exact new debits |

“Gross redesign surface” bounds the code under review; it is not a promise
that the entire object disappears. The all-zero credit column is intentional:
vacancy becomes spendable only after WPLTO measures the replacements.

### 2.4 Attic and gate disposition

Option A removes these runtime roles:

- Attic code DMA on VM refill/call/return;
- Attic C2I header, entry and descriptor reads during execution;
- Attic L65R reads for Session phase/Island execution;
- frame-bounded content-convergence retry in the hot path; and
- the rejected Link-36 retry-driver package and its 63-byte floor.

It retains these cold roles:

- complete shelf/catalog/region identity verification;
- C2I descriptor decoding and C2D construction;
- persistent session C2I storage and COW publication;
- cold Attic-to-Chip staging with content verification;
- Boot-family transport checks until the Chip native plane is published; and
- every generation, rollback, root, one-emitter/decoder and publish-last gate.

Gates are migrated rather than merely deleted. The hot Attic-address and
convergence gates are replaced by:

- exact Chip-bank ownership/range and non-overlap gates;
- one code-plane watermark derived from active C2D image records;
- “no execution-time Attic edge” over control flow and data relocations;
- stage-before-publish identity and destination-CRC gates;
- immediate-return Chip-DMA hardware evidence; and
- strict generation invalidation for both Chip planes.

The L65R convergence contract remains applicable to cold Attic staging until
a later proof removes its final cold consumer. Historical L10 evidence remains
immutable regardless of the selected architecture.

## 3. New capacity model

### 3.1 Current immutable composition

The generated six-image shelf divides exactly as follows:

| Image | normalized code | C2I metadata |
|---|---:|---:|
| stdlib | 8,293 B | 10,410 B |
| IDE | 11,612 B | 13,108 B |
| IDEX | 2,940 B | 3,152 B |
| M65D | 4,083 B | 1,814 B |
| buffer | 104 B | 230 B |
| compiler tier | 7,371 B | 7,556 B |
| **sum** | **34,403 B** | **36,270 B** |

The L65S header/catalog is 224 B, closing the current shelf at
`224 + 34,403 + 36,270 = 70,897 B`.

### 3.2 Binding currencies under Option A

| Currency | Capacity | Base use | Gross remaining |
|---|---:|---:|---:|
| Chip bytecode plane | 65,536 B | 34,403 B | **31,133 B** |
| Chip native plane, Session lifetime | 65,536 B | 60,062 B | **5,474 B** |
| Chip native plane, Boot lifetime | 65,536 B | 15,605 B | 49,931 B |
| Bank-5 C2D region | 50,816 B | 33,840 B | **16,976 B** |
| C2D images | 64 | 6 | 58 |
| C2D entries | 2,048 | 588 | 1,460 |
| C2D resolutions | 4,096 | 2,264 | 1,832 |
| C2D roots | 1,536 | 283 | 1,253 |
| cold immutable Attic shelf | not a hot budget | 70,897 B | unchanged |
| session Attic artifact arena | 1 MiB | generation-derived watermark | unchanged |

The **composition ceiling is 65,536 normalized code bytes**, not the complete
C2I/shelf byte count. The current foundation consumes 34,403 B, leaving a
combined **31,133-B library/user-code budget** before any later owner-reserved
floor. An append must also fit every remaining C2D dimension and the 16,976-B
Bank-5 byte headroom; the code number alone never authorizes it.

The native growth ceiling remains the existing 64-KiB L65R tenant. The Session
family's 5,474 B is the binding native-slice budget. C2-lite does not widen it
or turn the unused Boot-lifetime space into concurrent Session capacity.

Bank 1 remains the uncommitted user/graphics bank and receives no C2-lite
tenant. Bank 2 owns the typed 31,133-B executable remainder; it is not an
unowned graphics heap. Bank 3 owns the native-family remainder. The selected
contract must keep all three ownership statements explicit before any product
claim.

### 3.3 What is and is not promised

The numbers above are exact input geometry, not a linked-product claim. A
future capacity receipt must still measure:

- code-plane headers/alignment, if any (the target is zero per-image packing
  overhead beyond the emitted code lengths);
- C2D version/repacking cost, required to remain within 50,816 B;
- the two Chip-bank staging descriptors and watermarks;
- the net resident dividend after replacing the hot Attic seams; and
- whether the chosen second physical bank survives the required operating,
  Freezer and reset lifecycle.

No capacity result may sum the 31,133-B code remainder and 5,474-B native
remainder. They are different typed banks and cannot pay each other's debts.

## 4. Freight retriage

The owner-approved MUST/SHOULD/COULD order remains valid. C2-lite changes when
items may be reconsidered, not their rank.

### MUST — part of the C2-lite cut

1. One C2 format/emitter/decoder and all six product images.
2. The execution-complete C2D view, both Chip planes, generation/rollback and
   the no-runtime-Attic gate.
3. The definition-to-first-call cure measured against the pinned 15/16-frame
   cold and 10-frame warm limits.

No lower-ranked freight rides in the C2-lite substitution link. The link must
first expose the real resident dividend and the actual 31,133/5,474-B typed
budgets.

### SHOULD — reconsider after the C2-lite capacity pin

1. **Bitops (`logand`, `logior`, `logxor`, `ash`) move first.** Their compact
   opcode design already passed its ABI gate; the old rejection was a 327-B
   u16 shelf-catalog overflow, a wall the C2 format has removed. Their VM
   handler cost is resident and has not been measured against C2-lite, so they
   receive the first separate WPLTO probe after the hot-path dividend is real,
   not a free ride in the reconstruction.
2. **`gc`/`room`/`error`** retain their shared-carrier contract and follow
   bitops. They may use measured native/code-plane capacity but may not revive
   the rejected resident dispatcher.
3. **`restart-repl`** remains C2.3 freight. C2-lite makes its reset story more
   explicit: both Chip planes are disposable caches, generation invalidation
   precedes restage, and the double-call hardware fixture remains mandatory.

### COULD — unchanged

H/I/J metadata breadth, color-RAM scroll, tick hook and `(time)` remain
separable. The 115-B restored `$e000` floor and any later measured resident
dividend are reserve, not an invitation to re-admit them. `while`, `show`,
parity revalidation and the ship builder remain post-C2 rather than freight in
this cut.

## 5. Migration from Link 35 and acceptance

### 5.1 Ordered migration

1. **Review this memo.** Select Option A or reject it; explicitly decide the
   two physical Chip banks and the Bank-1 user/graphics ownership change.
2. **Fail-fast metal proof before product code.** Run the standalone
   Bank-to-window DMA completion pre-smoke above. A delayed destination rejects
   Option A; no convergence-driver fallback is permitted inside the probe.
3. **Contract addendum.** Pin the C2D execution record, root tag, code/native
   watermarks, publication order, no-runtime-Attic closure and restored
   115-byte `$e000` floor in prose and machine-readable config.
4. **Host/product-shaped probe.** Emit the exact 34,403-B static code plane,
   prove static/session one-emitter parity, exercise rollback/stale handles,
   pack the 15,605/60,062-B native lifetime pair, and run Whole-Program LTO.
   Every wall and the two new bank budgets are reported; no object-sum capacity
   claim is accepted.
5. **One separately authorized product link.** Start from the Link-35 source
   baseline, create a new identity, run every current structure/capacity gate
   plus the replacement gates, and bind all post-link mutable bytes. Link 35
   remains untouched until this succeeds.
6. **Receipt-less hardware presmoke, then C2.2 chain.** Only a structurally
   green identity reaches hardware. Promotion still requires the full fresh
   R4/R5/R6/G5/G6 sequence and single-device value strings.

### 5.2 Presmoke rows

The product presmoke starts again at line 1 and reports:

1. Boot to banner/REPL, including static Chip-plane staging.
2. Definition first call, cold: target 15 frames, hard stability ceiling
   16 frames.
3. Immediate second call, warm: at most 10 frames.
4. Typical Chip refill completion/time, split into bytecode-window and native
   Session-slice observations; Boot staging is reported separately.
5. GC block reads and frame cost.
6. Freezer roundtrip with byte-identical `$e000`, preserved Chip-plane
   identities and a usable resumed REPL.
7. Nested `(eval '(%c2h))`, RUN/STOP rollback and generation invalidation.

The limits remain measurements, not inherited claims. Criterion 1 is easier
only if the device proves it. The two-attempt rule also remains: only a
completed hardware latency attempt consumes one slot; prelink/link First Reds
do not. A first measured red may receive one separately reviewed successor.
A second measured red returns to the owner for product scope; it does not
renew the 1.1 latency exception.

### 5.3 Required negative fixtures

The successor adds at least:

- immediate Chip-DMA destination mismatch;
- code-plane overflow at 65,536 and offset+length wrap;
- code-plane overlap with the native plane or another owner;
- hot control/data edge to either Attic shelf or session arena;
- stale code/native watermark after generation change;
- C2D direct value misclassified as a root and the inverse;
- code published before destination identity succeeds;
- Boot and Session native families simultaneously callable;
- Freezer return with a changed Chip-plane identity; and
- a second emitter, decoder or hot-directory representation.

## Class-C review disposition — 2026-07-21

1. C2-lite is Option A, “no runtime Attic refill.” Option B is rejected for
   this recovery and retained only as a documented fallback if the Chip-RAM
   premise becomes red.
2. Bank 2 is the normalized code plane, Bank 3 is the lifetime-exclusive
   native plane, and Bank 1 retains the user/graphics promise untouched.
3. The execution-complete, unchanged-width C2D direction is accepted. The
   addendum corrects the memo's colliding high-bit suggestion to a
   positive-even canonical-root surrogate. C2D-v6 and that exact encoding were
   approved in the follow-up Class-C review on 2026-07-21.
4. The active `$e000` floor is Link 35's 115 B. The 63-B Link-36 floor is
   historical rejected-design geometry and creates no product credit.

The Bank audit and seven-part device proof are green. The addendum is approved;
the only authorized next action is its host/product-shaped probe. No product
link is authorized.

### Successor amendment — append-final Hybrid (2026-07-22)

The statement above records the Link-35 recovery decision and remains its
historical truth. After the append-final consolidation measured 54 bytes of
actual `$e000` remainder, the owner bound **54 B** as the current successor
floor. The Session-emitter state moves from `$fd08` to `$fd22` and the
predecessor-bound profile RODATA from `$fd12` to `$fd2c`; this resolves the
26-byte `reopen_gap0` overlap without adding a tenant. Any later demand below
54 bytes automatically triggers scope triage, with no fourth floor event.

The separate 32-byte Bank-0 LTO-noise reserve remains unchanged. One
sub-feature cut of at least 24 attributed text bytes must be selected by Alex
before one WPLTO simultaneously tests both currencies and every other wall.
