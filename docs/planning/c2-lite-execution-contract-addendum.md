# C2-lite Chip-plane execution contract addendum

Status: **Class-C approved export-symbol-domain successor product link and
immediate receipt-less line-1 presmoke after a fully green link**

Date: 2026-07-21

Machine-readable companion: `config/c2-lite-execution-contract.json`

Hardware prerequisite evidence:
`c2-lite-chipram-hardware-prefilter-result.md`

This addendum instantiates Option A from the reviewed C2-lite reconstruction
memo. The product-shaped Whole-Program LTO and pure gate replay were green,
and the then-authorized first C2-lite product link inherited no green gate.
Link 37 reached hardware and exposed a missing product obligation: the hot
native reader consumed Bank 3 although the product had never staged either
family there.  External preloading is forbidden because it would bypass the
obligation under test.  Class C therefore authorizes the product staging
source and exactly one product-shaped WPLTO probe; a successor product link,
hardware and promotion remain unauthorized. Link 35 remains the immutable
rollback line.

## Outcome

C2-lite retains the 128-byte VM code window and the fixed L65R overlay/Island
VMAs, but removes every Attic read from the execution-time closure:

```text
BCODE -> generation-bound C2D-v6 entry -> Bank 2 -> VM window
L65R  -> generation-bound family record -> Bank 3 -> overlay/Island VMA
```

Bank 2 is the sole normalized bytecode plane. Bank 3 is the sole native plane,
shared by Boot and Session only through their already-proved mutually exclusive
lifetimes. Bank 1 remains wholly outside C2-lite and retains the user/graphics
promise.

The complete shelf, C2I metadata and persistent session artifacts remain cold,
identity-bound, reconstructible Attic tenants. They may be read during a
closed staging/append transaction. After a callable is published, VM call,
return, opcode refill, literal materialization and native phase loading can
consume only C2D, Bank 2 and Bank 3.

## Hardware premise — passed

The non-product proof ran on device core `git-03b24c6b` and passed the memo's
seven-part protocol:

- full identity-bound patterns in Banks 2 and 3;
- the exact 12-byte production F018A list and `$d700` trigger;
- first-post-return consumption with no retry or delayed-success path;
- lengths 1, 7, 16, 127, 128, 1,761 and 1,781 bytes;
- owned IRQ/NMI/frame source and one Freezer roundtrip;
- Bank-3 Boot-to-Session replacement with stale-generation rejection; and
- exact core identity plus per-case raster observations.

All 12 directional bank/case combinations passed. The raster deltas were
`0,0,1,1,0,0,0,0,0,0,2,1`. Both complete 64-KiB identities survived the
Freezer; both banks remained writable. The proof is a receipt-less fail-fast
prefilter, not product acceptance. Xemu was not run and would not be
authoritative.

## Physical ownership

| Bank | Physical range | Sole live tenant | Current bytes | Headroom |
|---|---|---|---:|---:|
| 2 | `$020000..$02ffff` | normalized static/session code plane | 34,542 | 30,994 |
| 3 | `$030000..$03ffff` | Session L65R family | 60,062 | 5,474 |
| 3, Boot lifetime | same physical bank | Boot L65R family | 15,605 | 49,931 |
| 1 | `$010000..$01ffff` | user/graphics promise | 0 C2-lite | 65,536 |

Banks 2/3 are unlocked only after the owned-runtime handoff. Addresses remain
explicit `bank:u8 + offset:u16` values or DMA-list fields and never pass
through the target's 16-bit `uintptr_t`.

Both planes are disposable caches. Platform reset restages ROM over Banks 2/3
and exits the product; a new product session invalidates every C2D/code/native
binding before reconstruction. Power-cycle carries no survival claim. A
Freezer return must preserve both complete identities, the active generation,
immediate DMA behavior and subsequent writeability.

## C2D-v6 execution-complete view

C2D-v5 has not shipped. C2D-v6 replaces it before the first C2 product without
compatibility debt. The decoder is strict: v6 rejects v5, v5 rejects v6, and
no candidate contains both. The 48-byte header, 32-byte image records,
10-byte entry records and two-byte resolution/root records keep their widths;
the 50,816-byte Bank-5 region and all four capacity counts remain unchanged.

The 10-byte entry becomes:

| Offset | Field | Rule |
|---:|---|---|
| 0 | `image_slot_u8` | active, current-generation image |
| 1 | `literal_count_u8` | exact C2I entry count; observed maximum 23 |
| 2 | `code_offset_u16` | bank-relative offset in Bank 2 |
| 4 | `code_length_u16` | legal 1..65,535 |
| 6 | `resolution_base_u16` | first word in the C2D resolution plane |
| 8 | `session_generation_u16` | nonzero and equal to the published header |

`uint32(code_offset) + code_length` must be at most 65,536. The literal range
must close inside the active C2D resolution count. Image slot remains an
identity/provenance edge; the hot path does not reopen that image's C2I or
Attic source record.

### Resolution union — memo correction

The memo's provisional high-bit root tag is rejected. Bit 15 is already live
in direct values: BCODE is `$c000..$dffe`, SYMI is `$e000..$fffe`, and negative
Fixnums are high-bit odd values. The current six-image closure contains 637
direct BCODE resolutions in `$c1f4..$c496`; a high-bit decoder would
misclassify every one.

C2D-v6 instead encodes a canonical root reference as:

```text
root_ref = (root_ordinal + 1) << 1
```

Legal root references are nonzero, positive and even, presently
`$0002..$0c00` for the 1,536-root capacity. That object shape normally means a
heap pointer. It is available inside the resolution *union* because heap-valued
C2I kinds never store their pointer directly there: their sole mutable value
lives in the canonical `root_values` array. All other descriptor kinds store
their canonical direct `obj`, which must be NIL, odd, or negative and therefore
cannot collide with a root reference.

The hot materializer classifies a positive-even word as a root reference,
subtracts one after shifting, proves the ordinal below the active root count,
and reads the sole canonical root value. Every other word is a direct `obj` and
must fail if it has the positive-even heap-pointer shape. A moving/copying GC or
any new direct descriptor kind that can yield a positive-even object requires
a new resolution contract before implementation.

This remains width-neutral. It adds no resolution array, bitset or Bank-5 byte.
The corrected tag was approved by Class C on 2026-07-21.

Collision freedom is a permanent probe gate, not a one-time derivation. Every
future C2 probe must test the root-surrogate set against the complete legal
Fixnum, BCODE, SYMI and Native/direct domains before it can report green; a new
object domain therefore cannot enter without extending and passing this gate.
The pinned boundary fixtures include ordinal 0 mapping to `$0002`, ordinal
1,535 mapping to `$0c00`, rejection of ordinal 1,536, and both directions of
the direct-value/root-reference misclassification.

## Plane allocation and publication

Static code is packed from Bank-2 offset zero without per-image padding beyond
the emitted code lengths. Persistent session code grows upward. Transient eval
code grows downward from 65,536. The low and high watermarks are arithmetic
derivatives of active C2D entries, never separately maintained truths.

Publication is ordered:

1. verify the cold shelf/session artifact and C2I descriptor stream;
2. reserve non-overlapping Bank-2 code and C2D ranges;
3. copy code into Bank 2 and verify the exact destination bytes/CRC;
4. resolve literals into inactive C2D resolution/root ranges;
5. write inactive C2D-v6 image and entry records;
6. while the verified cold source is still available, capture a complete export
   plan containing the interned symbol, its previous function value and the
   target C2D ordinal/macro bit; the plan contains no source locator;
7. publish the C2D header/handle watermark;
8. publish export function cells from the captured plan; and
9. publish READY last of all.

The first Link-42 hardware run completed all thirteen decode phases and
captured 353 source-free export rows, then stopped fail-closed immediately
before export publication.  Every row contained the canonical value returned
by `intern`: an even SYMI in `$e000..$fffe`.  The publication preflight still
required `IS_PTR`, a positive heap-cell reference, and therefore rejected all
353 legal symbols beginning with row zero (`$e2a2`).  READY remained zero and
the export journal rolled back to zero entries.

The plan field is not a generic symbol-shaped object.  It is specifically a
canonical interned symbol and is therefore accepted by `IS_SYMI` only.  Heap
pointers (including a `T_SYM` gensym), NIL, Fixnums, BCODE and odd or
out-of-range damaged SYMI values are format/state errors before the first
function cell changes.  The active co-resident publisher and the mutually
exclusive legacy C2-lite publisher use this same `obj.h` predicate.  A
permanent product-shaped fixture consumes the exact 353-row hardware plan and
pins every rejected foreign domain.

The static six-image builder and the dynamic append path use the same portable
`c2d_v6_emit_entry_row` routine for every ten-byte execution entry.  Rebuilding
the byte layout in either host or target code is forbidden.  The routine binds
image slot, literal count, Bank-2 code offset, nonzero code length, resolution
base and generation and rejects every range overflow before emitting a byte.

The image metadata locator is cold provenance only.  A boot decoder may derive
the static C2I location from the already authenticated shelf record; a closed
append transaction may use its private staged-source coordinates.  Neither
coordinate is published in the final C2D-v6 image.  After READY, no reachable
control or data edge may interpret image bytes 23..27 as a locator.  Export
publication therefore consumes only the captured C2D plan and canonical
interned SYMI objects, never C2I or Attic bytes.

The product-shaped WPLTO accepted all 353 rows from the exact Link-42 hardware
plan and rejected heap pointers, NIL, Fixnums, BCODE and damaged SYMI values.
Class C consequently authorizes exactly one successor product link from the
unchanged Link-42 source baseline plus this predicate correction.  Every
ordinary and C2-lite structural, capacity, final-Island and publish-last gate
runs fresh; no green result is inherited.  A fully green successor proceeds
without another review stop to receipt-less presmoke line 1.  The line-1
First-Red budget remains 1/3 consumed and no completed latency measurement has
yet consumed either of the two latency attempts.

Rollback invalidates handles before restoring ranges. Persistent descendants
committed by a nested operation remain below the persistent low edge and cannot
be erased by a transient high-edge rollback. Code beyond a restored watermark
may remain physically, but is unreachable.

Bank 3 is staged by family. Boot generation is invalidated before the Session
family overwrites the bank. The complete packed family is destination-verified
before its family/generation binding publishes. Boot and Session can never be
callable simultaneously; a phase record names only a checked offset/length
inside the currently published family.

### Product staging state machine

Bank 3 does not acquire an owner merely because bytes occupy it.  The four
states are `INACTIVE`, `STAGING`, `VERIFIED` and the published family.  Both
`STAGING` and `VERIFIED` are deliberately non-callable.  `select_family` may
publish only an exact `VERIFIED` family/generation pair.

The Boot family cannot stage itself.  Its cold stager is therefore a distinct
pre-family L65O record, installed and executed after the KERNAL-ownership
handoff but before the independent Workbench record and before
`c2_product_prepare_boot`.  The Session stager is a distinct final Boot-family
slice after decoder phase 03: the serial resident driver loads it while Boot is
still selected, and its code is already executing from Bank 0 when it replaces
the family latch with `STAGING`.  Boot is therefore invalidated before the
first Bank-3 overwrite without an overlay ever loading another overlay.  Only
after complete destination identity does the cold slice leave `VERIFIED`; the
resident coordinator publishes Session after it returns.

Invalidation, copy, destination verification and failure handling live in the
two cold stage bodies.  The resident product retains only family/generation
state and the publish gate; there is no resident begin/verified/fail transition
API whose control body can be duplicated into hot callers.

Bootstrap record loading is a fixed trust chain, not a generic resident record
abstraction.  The resident loader authenticates exactly Record 1, the
pre-family stager.  Record 1 then parses the one fixed Workbench successor and
source-verifies its payload in unpublished Bank-2 scratch.  Because installing
the Workbench payload overwrites Record 1's own Bank-0 VMA, the cold entry ends
with a tail jump into one minimal resident commit seam.  That seam has no
descriptor parser: it copies only the already verified Bank-2 image, rechecks
the final Bank-0 destination CRC, executes Workbench, wipes the VMA and returns
directly to the original loader return address.  It is a sized Non-LTO
assembler leaf, not a second C implementation.  The fixed successor geometry
is a six-byte resident immutable table; Record 1 consumes that table and owns
no relocation to its `NOCROSSREFS` overlay sibling.  The later C2-lite Bank-2
stage replaces this unpublished scratch before any READY or handle
publication.

### Final Resident-Island identity

The prerequisite Resident-Island seed link is not a runtime identity source.
It exists to make the circular product layout linkable, but it cannot know the
absolute references selected by the sole final product link.  Link 41 exposed
that distinction: the 1,618-byte seed and final Island differed in twenty
link-resolved bytes, so their CRCs were respectively `$72b1` and `$56d6`.
Bank 3 held the final carrier byte-identically, yet the installer correctly
rejected it because it still compared the final record with the stale seed
CRC.

The strict L65R-v3 `DATA_ONLY` carrier record is therefore the only runtime
authority for the final Island source offset, length and CRC.  Phase 00 accepts
those fields only after record self-CRC, family/flag/VMA/ABI/build-id, source
bounds and complete source-payload CRC have succeeded.  It publishes the
three values through the existing installer/batch-lifetime-exclusive words
`rtov_batch_entry`, `rtov_batch_crc` and `rtov_call_context`.  Phase 01 copies
the words into locals and clears the handoff before reading the destination.
It then proves the complete target CRC before returning success; READY remains
last.  This adds no BSS byte and no overlay-to-overlay edge.

`LISP65_RESIDENT_ISLAND_LENGTH` and
`LISP65_RESIDENT_ISLAND_CRC16` remain legal build-prerequisite and host-fixture
descriptions, but the v2/v3 target installer and finalizer may neither accept
nor reject a final carrier by comparing against them.  Bounds, record CRC,
source CRC, destination CRC and fail-closed wipe are unchanged.

Every product-shaped WPLTO and product link runs one permanent identity gate.
It parses the emitted final record and payload, extracts the actual final
`.lisp65_resident_island` bytes from a disposable ELF copy, and requires equal
length, CRC and SHA.  Record-length, record-CRC, payload and final-section
mutations must each fail, as must reintroduction of a target seed-identity
comparison or a partial/replayed phase handoff.

The historical 32-byte non-LTO verifier table remains an unchanged prefix.
Eight publish-last bytes follow it: positive-u16 `(image_size, whole_crc16)`
for Boot, then Session, both derived from the final pack manifests after the
sole link.  Thus no compiled placeholder, stale planning size or second CRC
formula can authorize Bank 3.  Together with the two existing KERNAL-window
CRC operands, the complete post-link mutation domain is 42 bytes.  A zero,
missing, stale, wrong-family, wrong-generation or mismatching tuple returns
the specific `VM_RUNTIME_OVERLAY_ERR_FAMILY_STAGE` before publication.

Restage first clears READY, which invalidates the Bank-2 execution plane.  The
same operation resets the native-family generation; Boot-to-Session then
invalidates the Boot latch before replacement.  Consequently neither Chip
plane can retain callable stale state across restage or a family transition.

## No-runtime-Attic closure

After READY, the transitive control-flow and data-relocation closure of these
consumers must contain no Attic source address or Enhanced-DMA option:

- VM entry, call, return, tail call and opcode-window refill;
- literal materialization and root resolution;
- L65R phase and Resident-Island loading;
- GC scans of C2 roots; and
- event, RUN/STOP, Freezer-return and error paths capable of resuming Lisp.

Cold boot and a closed append/load transaction may consume Attic only to
construct an unpublished Chip/C2D generation. No caller may execute the bytes
being staged. The existing L10 content-convergence contract continues to guard
those cold transports until a separate proof retires its last cold use.

The source/link gate checks both control-flow and relocation/data edges. A
direct Attic address, a hidden second hot directory, a second emitter/decoder,
or an execution path using an immutable C2I entry/descriptor is a hard error.

## Semantic slice pack

The 1,792-byte runtime-slice cap is unchanged.  The first real v6 Cold-Plan
WPLTO found five transported phases above that cap.  They are divided only at
semantic ownership boundaries:

| Former phase | Successor phases | Handoff |
|---|---|---|
| decoder `05` | `05a` immutable-entry validation; `05b` C2D-v6 execution-row cross-binding | context `reserved` marker |
| `reserve_transient` | directory/source bounds; Bank-2 high-edge reservation | append-record byte 20 |
| `reserve_persistent` | count/source placement; Bank-2 low-edge reservation | append-record byte 20 |
| `stage` | copy plus destination verification; predecessor snapshot plus inactive-plane clearing | append-record byte 21 |
| `publish_plan` | cold coordinate/target scan; name resolution into the final source-free rows | append-record byte 22 plus per-row marker |

Every marker occupies an already reserved byte, is cleared by its consumer and
adds neither resident state nor a cross-phase pointer.  Skipping a producer,
replaying it, presenting the wrong marker or consuming a non-raw plan row is a
format/state error.  The resident driver is the sole sequencer.  No overlay
phase may load or call another overlay phase.

The added transports and catalog records are not free: the probe charges their
complete packed size to the Session Bank-3 family.  A split is green only if
each successor is at most 1,792 bytes, every product wall remains green, the
115-byte `$e000` floor holds and the complete Session family fits in 65,536
bytes.

## Session aggregate diet by co-residence

The five semantic splits are individually correct but their first complete
pack occupies 66,206 bytes, 670 bytes beyond the hard 65,536-byte Bank-3
family boundary.  The payload grew from 53,627 to 57,857 bytes (+4,230), while
packaging grew from 8,227 to 8,349 bytes.  Objectwise attribution assigns
+4,698 bytes to the five split groups and a net -468 bytes to every other
Session slice combined: the positive growth is local to the newly divided
work, not a diffuse bank-layout failure.

Two adjacent pairs therefore become atomic co-resident slices:

- `crc` followed by `metadata` becomes `crc_metadata`.  Its two predecessor
  payloads total 1,738 bytes, so the combined WPLTO section must remain at or
  below the unchanged 1,792-byte slice cap.
- `publish_names` followed by `publish_cells` becomes `publish_exports`.
  The combined entry preflights the complete immutable export plan before the
  first cell changes; publication then consumes those proven rows without
  repeating their tag/range checks.  This section must be at most 1,024 bytes,
  crossing the required additional pack quantum while remaining below the
  slice cap.

The resident driver remains the only overlay loader; a fused entry performs
only its two already-adjacent operations and cannot call or load an overlay.
The two catalog records disappear, but the cap, 256-byte pack quantum, family
bank and format remain unchanged.  Skip, replay, wrong-order and wrong-marker
fixtures cover both internal halves.  The fusion adds no handoff field or
pointer.

Removing two catalog records alone models 65,694 bytes and is insufficient.
Crossing the publication slice from five quanta to four models 65,438 bytes,
98 bytes under the bank boundary.  These are falsifiable planning numbers;
only the single authorized Whole-Program-LTO pack may book the result.

### Roots/fronts aggregate recovery

The family-qualified v6 record verifier subsequently grows from 1,454 to
1,568 bytes.  It remains below the 1,792-byte slice cap but crosses one
256-byte pack quantum, moving the complete Session family from 65,438 to
65,694 bytes.  The adjacent `roots` and `fronts` phases recover that exact
quantum without changing the record format, pack quantum, bank or cap.

They occupy one `.lisp65_rt_c2append_roots_fronts` section and one catalog
record.  The measured section is 1,473 bytes, leaving 319 bytes under the cap.
It contains two sized entry bodies plus a single transported dispatcher.  The
resident serial driver calls the physical record twice, first selecting roots
and then fronts.  Fronts-only rollback is legal only through its explicit
selection.  Append source-record byte 23 is dead after the fused
`crc_metadata` phase and becomes the cutpoint marker; this adds zero resident
bytes and zero pointers.

Missing, foreign, skipped and replayed selectors fail before an entry body
changes state.  Both entry bodies remain in the same section and neither can
load or call an overlay.  The WPLTO pack contains 50 Session records and
closes again at exactly 65,438 bytes with 98 bytes headroom.  The former
`.lisp65_rt_c2append_roots` and `.lisp65_rt_c2append_fronts` sections must be
absent from the final ELF.

## Floors, budgets and claim boundary

The Link-35 predecessor floor was restored to **115 B**. The 63-B Link-36
floor is historical rejected-design geometry. This was not a 52-B credit:
Link 35 never spent those bytes. The current Hybrid successor geometry is
defined below and does not rewrite either historical fact.

No gross retirement estimate is spendable. A separately authorized
product-shaped WPLTO probe must report ordinary text/BSS, fixed block, Resident
Island, `$e000`, Bank-5 C2D, both Chip planes and every native slice. It must
preserve the active floor, the 50,816-B C2D region and all current caps. Any
actual C2D widening or Bank-5 debit returns to Class C.

### Append-final Hybrid floor — owner decision 2026-07-22

The active C2-lite `$e000` floor is **54 B**. The predecessor-bound layout is
explicit: `reopen_gap0` occupies `$fca2..$fd21`, the ten-byte Session-emitter
state occupies `$fd22..$fd2b`, and the 342-byte profile RODATA begins at
`$fd2c`. The gap therefore ends exactly where the state begins; the former
26-byte `$fd08..$fd21` overlap is zero. No new tenant or product byte is
created by this geometry correction.

The 54-byte floor is self-defending. Any future window demand below it
automatically enters scope triage. There is no negotiation, exception, or
fourth floor event. Independently, Bank-0 text must retain at least **32 B**
of standing LTO-noise room. The measured eight-byte remainder therefore
requires one owner-selected scope cut of at least 24 current text bytes before
the single authorized WPLTO may run.

Alex selected `numeric-early-errors` on 2026-07-22. The four early deployment
statuses E2e/E2f/E3d/E3e retain their stable numeric rendering, overlay-first
attempt and generic hexadecimal fallback; only their resident prose sentences
are removed. The selected branch occupies 81 attributed bytes in the bound
failed-WPLTO LTO object. No cursor, disk-status, status-identity or fail-closed
behavior is cut. Exactly one combined WPLTO is authorized for this profile.

## C2-lite publish-last geometry

The extended 40-byte runtime-overlay verifier table is pinned at **`$b9cd`**
for the Bank-3-staging C2-lite profile.  `$b99b` remains historical C2-lite
geometry from before the chained bootstrap, and the pre-C2-lite `$b954` pin
remains the truth for its own Link-35-era receipts; neither history is
rewritten.  The SHA-bound WPLTO ELF places the exact 40-byte Non-LTO section
and all seven public boundary symbols at `$b9cd..$b9f4`.

The six runtime-verifier tuples occupy 40 named bytes: the historical 32-byte
prefix plus the eight-byte Boot/Session family-stage suffix.  Together with
the two KERNAL-window CRC operands, publish-last may change exactly **42 named
product bytes**.  Any other byte, table size, symbol order or profile/address
pairing is a hard error.  Class C authorized artifact-only completion of the
already linked, SHA-bound WPLTO bytes; this authorization permits no compiler
or linker run and preserves Link 35.

## Permanent negative matrix

The successor contract requires at least:

- strict C2D-v5/v6 rejection in both directions;
- high-bit BCODE, SYMI and negative-Fixnum direct values misread as roots;
- zero, odd, out-of-range and reordered root surrogates;
- a direct descriptor producing a positive-even heap-pointer shape;
- code offset+length wrap and the exact 65,536 boundary;
- persistent/transient Bank-2 edge collision;
- code or native family published before destination identity succeeds;
- stale code/native binding after reset or generation change;
- simultaneous callable Boot and Session native families;
- any hot control/data edge into Attic or C2I metadata;
- any post-READY consumer of the retired image metadata locator;
- an injected Attic/C2I read after READY, including one disguised as export
  publication;
- a dynamic C2D-v6 entry row that differs by one byte from static emission of
  the same six fields;
- skip, replay and wrong-marker transitions at every semantic split;
- any overlay-to-overlay call introduced by a split;
- a second emitter, decoder, materializer or hot directory;
- Freezer identity or post-return writeability loss; and
- any lowering of the restored 115-B `$e000` floor.

## Review decision and next gate

C2D-v6 with the positive-even canonical-root surrogate, the five semantic
slice cuts and the two-slice co-resident aggregate diet were approved on
2026-07-21. Their product-shaped WPLTO closes at 65,438 bytes, leaving 98
bytes in the Session Bank-3 family; the pure replay reports every resident
wall positive and `$e000` with 528 bytes headroom over the restored 115-byte
floor.

Class C subsequently authorized exactly one first C2-lite product link. It
must create a new identity from the Link-35 source baseline and freshly prove
all ordinary gates plus no-runtime-Attic closure, Bank-2/Bank-3 ownership,
stage-before-publish ordering, low/high watermark correctness, generation and
stale-handle rejection, and every named post-link byte. Any First Red stops the
link and blocks hardware. Only a fully green link may proceed to the separate
seven-line receipt-less hardware presmoke; no promotion or acceptance is
authorized here.

## Symmetric Bank-2 target staging (2026-07-22)

Link 43 completed all thirteen cold decoder phases and published READY, but
the first banner entry read the 1,731-byte Workbench bootstrap scratch that
still occupied Bank 2.  The emitted 34,403-byte static code plane had been
proved only as a host artifact; no product phase had copied it to Bank 2 or
verified the destination.  The prompt then hid the banner VM failure because
`repl` discarded `vm_run_dir`'s status.  This is product First Red **2/3**;
no latency measurement completed, so the latency count remains **0/2**.

Bank 2 and Bank 3 now have the same staging contract.  Each cold record is
source-authenticated, physically copied to its unpublished Chip coordinate,
read back from the actual destination, and accepted only when the record-bound
content CRC matches.  Phase 03 authenticates all six Shelf code records;
phase 03b consumes a reserved-byte cutpoint, copies those exact records to the
C2D-v6 execution offsets, and proves every Bank-2 destination CRC before the
Session family can be selected.  It adds no state byte or pointer.  The sole
physical-copy seam and the same bounded readback/timeout protocol serve both
Chip planes; their record-native CRC widths remain authoritative (CRC-32 for
Shelf code, CRC-16 for packed native families).

READY is dominated by both target proofs.  The stage-before-publish gate is a
linked target-dataflow gate, not a host-artifact assertion: it requires the
phase-03b copy and Bank-2 readback edges, their exact six record/coordinate/CRC
bindings, the Bank-3 VERIFIED-family edge, and only then export and READY
publication.  Leaving the authenticated Workbench scratch in Bank 2 is a
permanent negative fixture and must fail before READY.  Skip, replay, wrong
cutpoint, wrong target coordinate, corrupted destination and timeout are also
hard failures.

The REPL banner is part of the same publication claim.  A banner VM status
other than `VM_OK` or `VM_HALT` is preserved as the innermost status, rendered,
and returns without publishing a prompt.  A prompt can therefore no longer
stand in for a banner execution that was never checked.

Class C authorizes this contract/source correction, one product-shaped WPLTO
and, only after every gate and wall is green, one successor product link and
immediate receipt-less line-1 presmoke.  A new product-class line-1 First Red
would consume the third and final budget slot and stops for formal review; no
further fix cycle is implied.

### Target-stage WPLTO disposition

The first product-shaped WPLTO stopped before a product link.  Phase 03b was
1,847 bytes against the immutable 1,792-byte slice cap, and using
`vm_status_message()` to report the banner failure pulled a second resident
error vocabulary into Bank 0: 193 bytes of strings plus a 20-byte switch
table.  Ordinary BSS did not grow; the added immutable text moved it into the
fixed block.  This prelink First Red consumes neither a line-1 hardware slot
nor a latency attempt.

The approved correction assigns each fact to its semantic phase.  Phase 02a
proves the Shelf/C2D record counts, source coordinates and lengths, then leaves
marker `$2a`.  The first WPLTO placement made 02a 1,923 bytes against the
1,792-byte cap; phase 02b remained 243 bytes with 1,549 bytes free.  Therefore
phase 02b, the existing record-close phase, proves the C2D-v6 Bank-2 target
coordinate sequence and exact 34,542-byte closure before publishing phase 3.
No slice, catalog record, transport or new cutpoint is added.  Phase 03
authenticates the immutable Shelf payloads.  Phase 03b consumes those already
bound facts and owns only physical copy plus target-CRC convergence; it must
not rebuild the record binding.

The REPL consumes the inner VM status through `vm_status_error_code()` and the
existing numeric error renderer.  It neither calls `vm_status_message()` nor
adds another resident error table, and it returns before emitting a prompt.
Class C authorizes exactly one complete WPLTO of this 02b placement with all
cutpoint, target-flow, Workbench-scratch and numeric-error mutations.  Only a
fully green result may continue to the already authorized successor product
link and line-1 smoke.
