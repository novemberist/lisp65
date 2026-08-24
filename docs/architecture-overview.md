# Architecture Overview

lisp65 is a native MEGA65 workbench assembled from a small resident runtime and
loadable bytecode libraries. The design treats the machine's memory map,
persistent media, and verification artifacts as explicit product interfaces.

## Runtime layers

1. **Resident core** — REPL, reader/evaluator services, bytecode VM, `lcc`
   integration, loader, error recovery, and the minimal hardware bridges.
2. **Bank-2 code plane** — verified static bytecode and session-appended code.
3. **Bank-3 runtime plane** — verified boot and session runtime families.
4. **Bank-5 C2D/session store** — immutable directory prefix, mutable
   generation-bound entries, and a bounded second region for cold rollback
   phases.
5. **Attic shelf** — a cold, power-volatile staging source. The post-READY
   execution path does not read code, records, literals, or native slices from
   Attic memory.
6. **L65M libraries** — on-demand IDE, IDEX, M65D, and user-compiled code.
7. **Boot stager** — a separate artifact that validates and stages the product
   before chaining into the workbench PRG.

Keeping the stager separate preserves the resident Bank-0 budget and lets the
boot path verify product identity before execution.

## Language execution

The interactive evaluator and the native bytecode compiler share a contract-
checked public surface. Primitive identities come from a single registry and are
cross-checked across CALLPRIM, `apply`, `function-kind`, and compile-REPL views.
Dialect V2 uses strict arity metadata on code objects and L65M v2 directory
entries, including anonymous private functions and explicit late-bound exports.

## Editor and libraries

The resident `(edit)` entry point loads the IDE library on demand and starts the
editor. IDEX adds optional navigation and command features. M65D is a separate
copy-on-write persistence library so the editor can remain loaded without
paying the disk-write implementation cost until needed.

## Memory transport

Every mutable reader that consumes memory content does so through CPU reads
under a MAP window, not through DMA. The rule is structural rather than
advisory: a gate rejects any content-consuming DMA read outside the immutable,
CRC-covered boot spans, so the class cannot return by inattention. DMA remains
in use where the payload is immutable and its identity is proven by CRC.

The rule was bought rather than assumed. A DMA transport whose completion
signal could be trusted while its content was not yet visible produced
recurring, order-dependent library-load corruption; moving the readers to CPU
transport removed the class at its root and cost fewer bytes than the guards
it replaced. Readability proofs cover exactly the banks they probed.

## Input contract

The REPL input boundary is WYSIWYG: what the screen shows is what the reader
receives. Characters that would be invisible but semantically different --
notably PETSCII `$A0`, which a shifted keyboard can deliver in place of a
space -- are normalized at the input boundary, and control codes with no
mapping are rejected visibly rather than silently accepted. A line may carry
several forms; they are evaluated left to right, so forms completed before a
later reader error remain in effect.

The v1.6 `v16core` library replaces the native line reader with an
insertion-mode, cursor-following one-line editor. Its navigation bindings come
from the same generated keymap authority as their tests. Balanced multiline
input, history and the separate capture/Comfort path are not part of the v1.6
selected product.

## Media model

Release 1.6.0 uses three D81 roles with one drive:

- `L65SYS` is the immutable product image used for boot and library loading.
- `lisp65-library.d81` carries the one-row `v16core` package used to activate
  the v1.6 REPL line editor.
- A valid non-product 1581 image holds user files.

M65D denies the product medium by identity and binds each transaction to disk
name, disk ID, and mount generation. It verifies written sectors and treats a
mid-transaction medium change as terminal. An independent D81 model validates
filesystem structure and BAM accounting rather than trusting M65D's own readback.

## Capacity model

The principal constrained resources are:

- resident Bank-0 bytes;
- the product-owned `$e000..$ffff` window and its pinned floor;
- fixed resident blocks and the runtime Island;
- the primary and overflow runtime-slice stores;
- Bank-5 C2D append scratch;
- interned symbol slots;
- name-pool bytes;
- L65M directory slots.

Each promoted block reports every affected currency. Releases stop at their
pinned floors rather than treating unused address space as an implicit budget,
and a release contract fixes the user-visible headroom that must survive: free
interned symbol slots and free name-pool bytes are measured on the shipped
medium and compared against contracted minima.

Boot progress is a product surface, not a debugging aid. The staging, heap and
library phases announce themselves, and the library phase carries a decoder
ordinal, so a long boot is legible rather than mute.

## Evidence model

Evidence binds to immutable product-artifact SHAs, not to a mutable working tree.
R4 seals a reproducible candidate, R5 binds the global hardware matrix, R6 binds
autonomous boot and media behavior, and R7 packages exactly those proven bytes.
Every seal is independently verifiable offline and rejects manipulated inputs.

This structure is why release claims remain narrow: emulator results prove only
emulator-valid choreography, while physical timing, reset, storage, and Freezer
behavior require hardware receipts.
