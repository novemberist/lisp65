# Trace core-ABI work plan

Status: **Link 93 host/media green; hardware acceptance pending.**

The v1.4 trace attribution proved an information-theoretic boundary: the
released ABI could classify a function cell as bytecode but could not read its
exact value.  `set-symbol-function` also returned the replacement rather than
the displaced value.  A library-only `untrace` therefore could not restore two
different bytecode cells correctly and was deliberately removed from v1.4.

## Contract

`%function-cell` is a private prebuilt-library capability over the previously
unused arities of restricted carrier Prim 20 (`set-symbol-value`).  Its
one-argument carrier mode returns the exact current function-cell object; its
three-argument carrier mode (symbol, replacement, private marker 69) atomically
swaps the cell and returns the exact prior object.  The Lisp wrapper presents
the intended one/two-argument ABI.  `%function-cell` is absent from `apply`,
`function-kind`, the native registry and the public reference.  Reusing the
existing carrier range is also a placement invariant: it does not grow the
closed E000 jump table.  The exact access stays on the carrier's existing
resident dispatch seam; the unrelated intern Session service remains byte- and
ownership-separate.

`trace` prepares the exact prior value, then expands to a real top-level
`defun` of the named function.  The existing C2 publisher owns both the
persistent wrapper and its function-cell publication in one journaled
transaction.  The wrapper calls the saved exact cell through `apply`.
`untrace` uses the private swap and verifies the displaced value before it
forgets the saved binding.  No transient helper may become the owner of a
surviving function cell.

## Phases

1. Add the private ABI and regenerate every native-function view.
2. Build the next-release `inspect` candidate and prove exact getter/swap,
   traced call, restoration, publication rollback and duplicate operations.
3. Bind the historical v1.4 descope to its sealed authority rather than the
   live ABI; new capability must not rewrite old release history.
4. Produce one new product link and inspect medium.  No v1.4 artifact is an
   input or output.
5. Add one acceptance row to the already planned bundled device session:
   trace a defined function, observe enter/result/exit, untrace it, and prove
   its original behavior returns without trace output.

The block has no release claim.  Successful hardware acceptance makes
`trace`/`untrace` eligible for the next release scope; it does not publish
them by itself.

## Link-93 closure — 2026-08-09

The exact ABI and the private `inspect` candidate are linked and closed on
fresh post-v1.4 artifacts.  The accepted placement keeps the new modes on the
existing resident Prim-20 dispatch seam and shares one resident
extended-heap-aware symbol predicate across all six native arms that need the
same truth.  It adds no native ID and leaves `.rodata.vm_callprim` at 168
bytes.  The completed product has 354 bytes of Bank-0 text headroom, 54 bytes
of E000 headroom, 137 bytes of ordinary BSS headroom, two fixed-hot bytes and
50 resident-island bytes.  The packed Session family remains closed at 52
catalog records plus one 399-byte service, with 113 bytes of headroom.

The route to that placement is part of the evidence.  Two direct-Prim-69 seed
links were rejected when the immutable call table grew from 168 to 170 bytes;
a cold intern-service form was rejected at 276 bytes beyond its packed Session
region; and an unfactored resident form linked but missed the permanent
32-byte text wall with only 14 bytes free.  None is reclassified as a product
success.  The shared-predicate form is the sole successful product link.

Artifact completion performed no compiler or linker run.  The final PRG is
SHA-256 `15c6e0817ae1a3ace7a3e4d576e3c238d268cbcf9c25e98842dd0b912b9d3f62`.
The canonical product manifest binds 14 pre-media roles; the acceptance media
bind 19 shared roles, a one-row `inspect` index with 29 rejected mutations,
and successful readback.  Seventeen Link/media mutations include direct
replacement of the product and both D81 identities.  The permanent authority is
`c2.3-trace-core-abi-link93-receipt.json`.

No hardware run, public-surface change or release claim is implied.  The
remaining row is physical acceptance of exact trace and restoration under the
standing persistent-by-default observation policy.

The first staging attempt ran no form: a second `mega65_ftp -F` tried to
install its helper over the already-live Workbench and injected GO64/Y into
the product input queue.  The corrected runner now uploads and reads back both
D81s in one helper lifetime under fresh BASIC, mounts the product last, and
requires the owner to mount the library physically through the Freezer after
boot.  A permanent shared gate makes every post-boot FTP invocation impossible
in this runner and in the bundled defstruct runner.  This is harness evidence,
not a Link-93 result.

Because the host-, link- and device-preparation receipts bind this plan, the
authorized choreography addition is rebound loudly through that receipt chain.
The Link-93 product and library D81 identities remain
`57afdf35587106ad4b813da2cfecf5220276863a939591c0667750e4e712b315` and
`5e282937436e6d2656590490734d800fcd9fecb4b3a740a3ec39009cdeb5a1bd`;
neither artifact is rebuilt or changed.

That row is now mechanically prepared in
`config/c2-trace-core-abi-device-session.json`.  It binds the exact product and
library D81s, forbids the repeatedly lossy virtual-input transport, and uses
six owner-typed forms.  Every mutating form receives a quiet floor and exactly
one postcondition observation; no monitor access or screen polling may cross
an active form.  The traced call must show ordered enter/exit markers and the
exact result `5`; after `untrace`, the same call must return `5` with neither
marker.  Nineteen mutations guard authority/media identity, input, ordering, quietness,
restoration and claim limits.  Preparation authority:
`c2.3-trace-core-abi-link93-device-preparation-receipt.json`.
