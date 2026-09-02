# Ship Builder v1 contract

Status: accepted implementation contract for the 1.3 Ship Builder block.

## Public surface

The v1 surface is exactly:

```lisp
(ship "program" :entry 'main)
```

`program` names an L65P-v1 project beside the current project manifest.  The
name must equal the manifest's `name` field.  `:entry` names one function in
the compiled project closure; it must have fixed arity zero.  The result is a
new standalone D81 named `program.d81`.  Refusing to overwrite an existing
image is part of the interface, not an implementation detail.

The host command is the first executable front end for this form.  It parses
the form with the canonical Lisp reader and then invokes the same builder
used by the permanent gates and samples.  A later Workbench convenience
front end may delegate to this builder, but may not define a second project,
closure or media interpretation.

Failures are fail-closed and leave no destination image.  The stable error
classes are: malformed ship form; invalid L65P manifest; unresolved or cyclic
library dependency; unresolved entry; non-zero entry arity; unresolved
dynamic call edge; unsupported target primitive; capacity failure; runtime
link failure; media construction failure; and post-pack verification failure.

## One dependency and identity truth

Project parsing is L65P-v1.  The ship library catalog is adapted into the
canonical L65P index shape and dependency order is obtained from
`l65p_v1.resolve`; the builder does not contain a second graph resolver.  The
resulting generation-1 resolution lock rides on the disk and binds project,
ordered libraries, source list, catalog identity and library identities.

All project functions are compiled.  Library sources become eligible only
through the manifest's `requires` closure.  Of those eligible functions only
the functions reachable from project code and their transitively reachable
library helpers ride.  Direct calls and statically named function targets are
accepted.  A dynamic target that cannot be reduced to a named function is
rejected rather than conservatively dragging an unproved library set onto the
disk.

The closure report records, separately, project functions, eligible library
functions, shipped library functions, direct edges, and rejected edges.
Compiler macros needed to compile a reachable function may participate at
build time; diagnostics, host probes and compiler-only helpers never ride.

## Media contract

The D81 has label `L65APP` and disk id `65`.  These files are mandatory:

| file | role |
| --- | --- |
| `AUTOBOOT.C65` | verified cold stager, the first directory entry |
| `BOOT.ID` | fixed descriptor binding staged files and build identity |
| `RUNTIME.PRG` | evaluator-free redistributable Runtime Core |
| `RUNTIME.BIN` | build-bound Bank-5 preload containing program and closure |
| `APP.L65M` | the same compiled program/closure artifact for audit and reuse |
| `PROJECT.L65P` | the canonical project manifest bytes |
| `SHIP.LOCK` | canonical generation-1 L65P resolution lock |
| `SHIP.JSON` | complete content-addressed ship manifest |
| `LICENSE.TXT` | redistribution notice and source-availability pointer |

`BOOT.ID` v3 contains exactly two 32-byte records: Bank-5 preload to
`$050000`, then the Runtime PRG staged through Bank 4 and copied to its PRG
load address.  Every described file is length- and CRC-bound.  The stager
uses the existing content-defined Chip-RAM readback path before handoff and
enters the Runtime Core at the linked ELF `_start` address.  That address is
bound into the stager; `$2026` is a historical Runtime-Export address, not a
second Ship authority.

The user program, tree-shaken library functions and literal metadata form one
L65M/preload identity.  They are not independently relocated at boot.  The
separate `APP.L65M` file is an audit copy and must be byte-identical to the
payload bound into `RUNTIME.BIN` as reported by `SHIP.JSON`.

The maximum image is the 819,200-byte D81 geometry.  The builder also enforces
the Runtime Core's existing Bank-0, Bank-5, symbol, directory and code-object
ceilings before media construction.  Capacity is measured from emitted
artifacts; it is never inferred from source length.

## Runtime and redistribution boundary

The shipped Runtime Core is the evaluator-free v2 Runtime Core: VM, GC,
symbols, native primitive implementations required by the emitted closure,
and embedded bytecode metadata.  It contains no reader, evaluator, compiler,
REPL, IDE, disk-library resolver, diagnostic carrier, probe, receipt or
toolchain executable.

The Runtime binds the public `key-event`, `write-char`, and frame-counter read
edges directly to its physical keyboard, screen, and KERNAL-jiffy drivers.
This is a Runtime implementation of the same primitive ABI, not a second Lisp
surface. It lets the base `read-line`, `wait`, and `time` composition execute
without importing the Workbench evaluator or its resident screen state.

When the zero-argument entry returns successfully, the Runtime records its
tagged result, publishes `RUNTIME_COMPLETE`, and remains in that completed
state.  A standalone image never falls through to the Workbench or BASIC;
neither is part of its continuation contract.

The Runtime Core is Covered Software distributed in executable form under
MPL-2.0.  `LICENSE.TXT` identifies the license and the public source location
required by MPL section 3.2.  User source and bytecode are separate files in a
Larger Work and are not relicensed by this contract.  No trademark grant is
implied.

## Reproducibility and verification

For a clean source commit, identical project bytes, ship form and toolchain,
two independent fresh checkouts must produce byte-identical D81 files.  The
permanent gate publishes an execution witness with both image hashes, file
count, closure counts, Runtime ELF audit, media verification count and at
least one rejected mutation.  Existence of an image without that witness is
not a ship claim.

The verifier re-opens the D81, verifies its label and directory inventory,
extracts every mandatory file, validates `SHIP.JSON`, recomputes all hashes,
replays the L65P lock, verifies `BOOT.ID`, verifies preload binding in the
Runtime PRG, and audits the linked ELF for the forbidden Workbench/compiler
surface.  It never trusts the build directory alongside the image.
