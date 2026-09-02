# BASIC 65 parity revalidation for the C2-lite workbench

Status: **Phase R complete; paper only, no product authorization**

Date: 2026-07-30

Baseline: released v1.2.3, Link 80

This document replaces the pre-1.0 delivery assumptions in
`docs/archive/pre-1.0/designs/mega65-basic-parity-libraries.md`. It does not
authorize a parity module, a product link, a new native seam, or a device run.
The first pilot still waits for the 1.3 ship-builder decision.

## Evidence vocabulary

Every row below carries one of these fidelity tags. The tags describe the
strongest evidence for the named surface, not for a future module which might
consume it.

| Tag | Meaning |
| --- | --- |
| `HW` | Executed in a released product or an isolated hardware fixture with a bound oracle |
| `ELF` | Present and structurally checked in the linked product, but not exercised as the proposed parity API |
| `HOST` | Executed by a host oracle against the product contract; no target-behaviour claim |
| `PAPER` | Contract or placement proposal only |
| `BLOCKED` | A measured wall or missing contract prevents an implementation claim |

## The five obsolete assumptions

### 1. Delivery is C2 direct execution, not resident or disk-only libraries

The old design divided libraries into resident code and D81 payloads.
C2-lite has a sharper split:

- normalized Lisp code executes from the Bank-2 Chip-RAM plane;
- native cold phases and services execute through the single Bank-3 overlay
  window;
- immutable package identity and dependency resolution use L65P-v1 plus the
  C2D generation;
- session publication remains transactional and append-only.

The released `require` foundation can resolve and publish packages, but the
first parity pilot still waits for the 1.3 ship builder. A source file existing
on a D81 is not yet a shipped package.

### 2. Byte transport is no longer missing

The first-class `Buffer` API is delivered: `make-buffer`, `buffer-length`,
`buffer-ref`, `buffer-set!`, `buffer->string`, and `string->buffer`. Binary
assets, word values, sprite data, palettes, and sector payloads therefore do
not need to masquerade as Strings or lists of characters.

### 3. Bit operations are delivered; the word result still needs a type

`logand`, `logior`, `logxor`, and `ash` are compiler/VM operations and are
hardware-green. They remove the old composition blocker but do not enlarge the
signed 15-bit Fixnum range (`-16384..16383`). A full unsigned word still
cannot be returned as one Fixnum.

The old public names `peekw` and `pokew` remain tombstoned. The parity-layer
replacement is explicitly typed:

```lisp
(m65-word-read address-hi address-lo)        ; => two-byte little-endian Buffer
(m65-word-write address-hi address-lo word)  ; word is a two-byte Buffer
```

The caller may use `buffer-ref` plus the delivered bit operations when a
numeric projection is representable. This reopens word access without
pretending that the numeric representation widened.

### 4. Raster ownership exists; a safe Lisp scheduler boundary does not

The product owns one VIC raster interrupt. The handler acknowledges it,
advances the product frame counter, samples RUN/STOP, and does not call Lisp or
allocate. This is the correct timing substrate, but it is not a callback
boundary.

`lisp_poll()` runs inside live evaluator, VM, keyboard, and GC-root contexts.
Calling Lisp there would recursively enter the evaluator. Calling Lisp in IRQ
context would be worse. The scheduling contract below therefore requires a
resumable VM return to a top-level scheduler before any callback can run.

### 5. Input is an atomic typed event, not GETIN

`key-event` is the public input seam:

- mode `0` is nonblocking and returns `nil` on an empty queue;
- mode `1` is blocking;
- each event captures `(key code modifiers)` from one queue head and dequeues
  it exactly once;
- Control and Meta are event-time modifier bits;
- RUN/STOP is a separate physical abort authority and is not an editor key.

L-lite key codes and the L-full modifier bindings are generated from
`config/v11-l-lite-keymap.json`. New parity code must consume `key-event`;
`read-key`, `poll-key`, GETIN, and private key tables are not alternate
truths.

## Revalidated module graph

There are nine prefixed domain modules plus the optional `basic65` façade.
The graph is deliberately library-heavy:

```text
                              basic65 (optional aliases)
                                         |
       +-----------+-----------+---------+---------+-----------+
       |           |           |                   |           |
    m65-text    m65-gfx     m65-draw          m65-sprite   m65-sound
       |           |           |                   |           |
       |           +-----------+                   +-----------+
       |                 |                                |
    m65-input          m65-hw <--------- m65-disk ---- m65-system
       |                 |
       +-----------------+
              released core surfaces
       Buffer, bitops, key-event, screen, peek/poke, C2/D81
```

| Module | Priority | Direct dependencies | Strongest present evidence | Current disposition |
| --- | ---: | --- | --- | --- |
| `m65-hw` | P1 | core `peek`/`poke`, Buffer, bitops | `HW` for the component primitives; `PAPER` for the module | first pilot, after ship builder |
| `m65-text` | P2 | core screen API, `m65-hw` | `HW` for screen primitives; `BLOCKED` for full Color-RAM scroll | small text helpers are eligible; color rider is not |
| `m65-input` | P2 | `key-event`, `m65-hw` | `HW` for atomic typed keyboard events | keyboard/joystick-first module is eligible after P1 |
| `m65-gfx` | P3 | `m65-hw` | `HW` for isolated Bank-4/EDMA mechanics; `PAPER` for public state | host-oracle-first |
| `m65-draw` | P3 | `m65-gfx` | `HOST` algorithms only when built | start with dot/line/box/circle |
| `m65-disk` | P3 | current C2/D81 and Buffer paths | `HW` for the existing product disk foundation | parity API extends, never duplicates, `lib/m65-disk.lisp` |
| `m65-sprite` | P4 | `m65-hw`, optional `m65-disk` | `PAPER` | direct state/polling first; async motion waits for scheduler |
| `m65-sound` | P4 | `m65-hw` | `PAPER` | direct SID tone first; PLAY/background sequencing waits |
| `m65-system` | P5 | `m65-hw` | `ELF/HW` for selected low-level product seams | explicit danger bundle, never a default dependency |
| `basic65` | P6 | explicitly selected stable modules | `PAPER` | aliases/defaults only, no algorithms |

The previous order put graphics immediately after `m65-hw`. Typed input is now
already a hardware-proven product surface, so `m65-text` and `m65-input` are
the cheaper second step. This does not change P1: every higher module still
depends on one audited low-level address and representation contract.

## Capacity model

Link 80 is the current pricing authority:

| Currency | Headroom | Rule for parity work |
| --- | ---: | --- |
| Bank-2 normalized code | 24,051 B | the only ordinary growth currency |
| Bank-0 text | 243 B | closed; no feature debit |
| `$E000` owned window | 54 B | immutable floor, not credit |
| fixed hot block | 2 B | closed |
| ordinary Bank-0 BSS | 137 B | closed; no new feature state |
| resident island | 50 B | closed |
| Session native family | 113 B | not payload credit; one 512-B quantum already exceeds it |
| one native slice | 1,792 B | hard ceiling, not aggregate capacity |

Library source size is not a price. Each pilot reports the generated Bank-2
bytes and package metadata after the real compiler and packer run. The P1
pilot has a recommended admission envelope of **2,048 Bank-2 bytes**, zero
resident bytes, zero new native records, and no use of the 113-byte Session
remainder. A miss returns to owner review; it does not borrow from a closed
wall.

## `m65-hw` surface after revalidation

The pilot surface is narrower than the old proposal:

- 16-bit CPU-visible reads and writes wrap the existing strict-byte
  `(peek hi lo)` and `(poke hi lo value)` contracts;
- bit helpers are Lisp over byte `peek`/`poke` plus delivered bitops;
- word reads and writes use the two-byte Buffer contract above;
- register constants are generated data, not handwritten duplicates;
- raw `sys` is excluded from the P1 pilot;
- flat 28-bit single-byte access is not claimed;
- public EDMA is excluded until address representation, completion, and
  capacity are jointly closed.

The absence of a flat Fixnum address is intentional. A 28-bit physical address
must be represented as bytes or a Buffer and validated before a native
transport sees it.

## EDMA and the Color-RAM path

The useful hardware fact is real: the isolated screen fixture moved an 80x25
character screen and the 28-bit Color RAM at `$FF80000`, including tail fill,
and passed 7/7 on hardware.

That does not make the rider product-affordable:

- the old resident integration cost **+439 B text and +14 BSS** and failed its
  Bank-0/stack walls;
- the current source, compiled as a non-LTO native overlay, is **622 B code
  plus 20 B job state**;
- Session service packing is 512-byte granular, so 642 raw bytes require a
  **1,024-byte allocation**, 911 bytes more than the current 113-byte Session
  remainder, before a catalog record or dispatcher edge;
- the four-job prototype predates the L10 completion rule. It has no
  content-defined completion proof between jobs and therefore is not a
  product-complete transport implementation.

The linked product already pays for a private 145-byte
`c2_product_physical_copy` and a 20-byte Enhanced-DMA descriptor. That seam is
a transaction transport, not a public EDMA API: it has copy semantics only,
and its callers provide the content fence. Reusing its existence to claim a
general copy/fill surface would erase the very boundary L10 established.

**R4 disposition:** the Color-RAM scroll rider is not affordable in v1.2.4.
It remains parked. The next legitimate price is a product-shaped replacement
which reuses or substitutes existing transport freight, includes
content-defined completion, and fits without a new Session quantum. The M2 L10
re-measurement may change the transport premise, but it does not retroactively
authorize this rider.

## `(time form)` time base

`(time form)` is independent of the tick hook. Its pinned clock is the
product-owned 16-bit raster frame counter:

- low byte `$FF83`, high byte `$FF84`;
- nominal 50 Hz, therefore 20 ms per frame;
- read atomically as high/low/high, retrying if the high bytes differ;
- subtract modulo 16 bits.

The old 23-byte cooperative KERNAL-jiffy observation is only a historical
lower bound. The KERNAL is no longer the runtime clock owner.

The proposed cold Bank-2 macro evaluates `form` exactly once, prints the
elapsed frame count, and returns the form's value. It uses existing `peek`;
it needs no callback, IRQ change, new native primitive, or resident state.
Because one Fixnum cannot represent every 16-bit delta, intervals of 16,384
frames or more (327.68 seconds) fail with a named duration-overflow error
rather than wrap silently. M4 calibrates this base against one known workload
before the candidate can be selected at halt #1.

No Bank-2 byte price is claimed yet. The 23-byte result cannot be transferred
from an obsolete native/KERNAL-jiffy probe to a Lisp macro over the owned
counter.

## Tick-hook scheduling contract draft

This is a design input for halt #1, not an implementation contract.

### Clock and IRQ responsibilities

The raster IRQ only acknowledges the owned source, advances `$FF83/$FF84`,
samples the physical abort source, and returns. It never resolves a function,
touches Lisp objects, allocates, performs DMA, or invokes a callback.

### The only legal callback boundary

A callback may run only after the compiled VM has returned a new
`VM_YIELD_SAFE` result to a top-level scheduler. At that point:

- the VM continuation is explicitly suspended and rooted;
- no C evaluator or primitive frame is live;
- GC is not active;
- no C2J transaction, append, publication, rollback, compiler lifetime,
  Session service, overlay window owner, disk mutation, or abort cleanup is
  active;
- the runtime window is free;
- interrupts are in the owned normal state.

`lisp_poll()`, the IRQ/NMI handlers, a blocking `key-event` primitive, and an
arbitrary tree-walker recursion frame are forbidden callback boundaries.
When a forbidden region spans a due tick, delivery is deferred.

### Scheduling and coalescing

The compiled VM receives a bounded instruction budget. At a legal bytecode
boundary it saves the continuation and returns `VM_YIELD_SAFE`; it does not
call Lisp from inside `vm_run`. The top-level scheduler atomically samples the
frame counter and compares it with the last delivered frame.

At most one callback runs per scheduler turn. Multiple elapsed periods are
coalesced into one Fixnum count and saturate rather than wrap. Normal return
resumes the exact suspended continuation. A callback error disables the hook,
lands at the existing top-level abort boundary, and leaves a usable REPL.

Hook identity and period live in canonical symbol values, so the GC's existing
global-root truth owns them. No private callback registry or second root list
is permitted.

### Required proof before implementation

- bytecode continuation save/resume equivalence, including tail calls and
  streamed code-window refills;
- zero callback entries in every forbidden lifetime above;
- frame wrap, coalescing, saturation, delayed delivery, and callback error;
- RUN/STOP during user code and during the callback;
- no growth of roots, Directory, symbols, C2D watermarks, or overlay records
  over repeated callbacks;
- hardware cadence and emulator fidelity separately tagged;
- one WPLTO with zero closed-wall debit, or an explicit owner decision.

The draft therefore answers where a hook may run. It does not imply that the
required resumable scheduler is small.

## Pilot contract for 1.3

The first pilot is `m65-hw`; no other parity module is allowed to become the
implicit pilot.

### Inputs

- one generated L65P package and dependency record;
- no new native record;
- the Buffer, bitops, strict-byte `peek`/`poke`, and package resolver already
  present in the product;
- generated register constants from one authority file.

### Surface

- byte read/write in the CPU-visible 16-bit address space;
- bit set/clear/test over one byte;
- Buffer-valued little-endian word read/write;
- constant groups for VIC-IV, CIA, SID, F011, and DMAgic;
- no raw `sys`, no flat single-byte 28-bit claim, and no public EDMA.

### Acceptance

1. The 1.3 ship builder emits the package and manifest from a clean checkout.
2. Host RAM oracles execute byte, bit, word, range, and mutation cases.
3. The package stays within 2,048 Bank-2 bytes and has zero resident/native
   delta.
4. Bound package/source parity checks the artifact, not merely the source.
5. One later bundled hardware session checks harmless register reads, a
   disposable RAM byte/word round trip, and package idempotence.
6. Failure cannot mutate I/O, C2D, package locks, or the work medium.

The pilot remains behind the ship-builder decision. This document closes the
revalidation, not the pilot.

## Halt-#1 menu produced by Phase R

| Candidate | Phase-R result |
| --- | --- |
| `(time form)` | architecturally eligible; owned counter pinned, zero native dependency; needs M4 calibration and a Bank-2 price |
| tick-hook implementation | not eligible in this block; scheduling contract drafted, resumable scheduler must be separately commissioned |
| Color-RAM scroll | not affordable in v1.2.4; minimum native allocation exceeds Session headroom and lacks current completion proof |
| parity pilot | contract ready, but waits for the 1.3 ship builder |
| `m65-hw` word access | reopened only as a two-byte Buffer API; old Fixnum `peekw`/`pokew` tombstone remains |

## Claim boundary

This revalidation binds current source, released-product geometry, historical
hardware receipts, and one isolated non-LTO size measurement. It changes no
product source. It proves no new module, time API, callback, EDMA transport,
package, link, or hardware behavior.
