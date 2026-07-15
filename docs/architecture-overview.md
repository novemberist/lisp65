# Architecture Overview

lisp65 is a native MEGA65 workbench assembled from a small resident runtime and
loadable bytecode libraries. The design treats the machine's memory map,
persistent media, and verification artifacts as explicit product interfaces.

## Runtime layers

1. **Resident core** — REPL, reader/evaluator services, bytecode VM, `lcc`
   integration, loader, error recovery, and the minimal hardware bridges.
2. **Bank-5 preload** — the bound standard-library prefix needed at boot.
3. **Attic catalog** — reset-persistent, power-volatile overlay metadata.
4. **L65M libraries** — on-demand IDE, IDEX, M65D, and user-compiled code.
5. **Boot stager** — a separate artifact that validates and stages the product
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

## Media model

Release 1.0.0 uses two D81 images with one drive:

- `L65SYS` is the immutable product image used for boot and library loading.
- A valid non-product 1581 image holds user files.

M65D denies the product medium by identity and binds each transaction to disk
name, disk ID, and mount generation. It verifies written sectors and treats a
mid-transaction medium change as terminal. An independent D81 model validates
filesystem structure and BAM accounting rather than trusting M65D's own readback.

## Capacity model

The principal constrained resources are:

- resident Bank-0 bytes;
- EXT bytes used by the product image;
- interned symbol slots;
- name-pool bytes;
- L65M directory slots.

Each promoted block reports all five deltas. Release 1.0.0 deliberately stops at
the pinned floors rather than reclaiming capacity without a concrete need.

## Evidence model

Evidence binds to immutable product-artifact SHAs, not to a mutable working tree.
R4 seals a reproducible candidate, R5 binds the global hardware matrix, R6 binds
autonomous boot and media behavior, and R7 packages exactly those proven bytes.
Every seal is independently verifiable offline and rejects manipulated inputs.

This structure is why release claims remain narrow: emulator results prove only
emulator-valid choreography, while physical timing, reset, storage, and Freezer
behavior require hardware receipts.
