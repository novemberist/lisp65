# Known Issues and Retired Exceptions

This is the maintained user-facing issue register for lisp65 1.2.4. Sealed
historical documents retain the wording that was true when they were issued;
this page states the current product boundary.

## Active product limitation: Freezer during a definition

Status: **documented; C2.3-deferred**

Enter the Freezer only while the REPL prompt is visible or the evaluator is
otherwise idle. Freezer entry during a persistent definition or append
transaction is not supported in C2.2.

If it happens:

1. Return from the Freezer with F3.
2. Cold-restart lisp65 from the product disk.
3. Re-enter the interrupted definition before relying on it.

Idle Freezer entry and return are hardware-proven for the 1.2 product identity.
Freezer entry while a definition is open is not. The C2.2 cross-invariant
matrix classifies that crossing as documented/C2.3-deferred, and no release
receipt may relabel it as proven.

## Active hardware-profile limitation: interrupt-generating cartridges

Status: **unsupported while C2-lite owns the interrupt vectors**

Do not use a cartridge that generates interrupts while lisp65 is running.
Passive storage, RAM, and utility cartridges that do not assert `/IRQ` or
`/NMI` are unaffected.

lisp65 cannot turn off or acknowledge cartridge interrupts in a
device-independent way. A single isolated interrupt within a raster-delimited
episode is tolerated, but a held or repeatedly asserted cartridge causes an
interrupt storm that deliberately stops the product on a red-bordered screen.
Cold-restart without the interrupt-generating cartridge before continuing.

## Active intermittent issue: post-GC out of memory

Status: **observed once; not reproduced**

One hardware run allocated 1,200 short-lived cons cells inside a `while` loop
and ended with:

```text
*** vm: out of memory
```

The same follow-up workload completed without the error, and the host and
modeled extended-heap lanes also completed. No fix is claimed. If an
out-of-memory error appears despite a small live data set, preserve the exact
form and preceding steps, restart lisp65, and include those details in a bug
report. The permanent reproducer remains in the test suite.

## Active intermittent issue: `require` can return `nil`

Status: **observed once; not reproduced after a cold start**

Late in one long hardware session, `(require 'place)` returned `nil` instead
of `t`. A cold restart cleared the symptom: two subsequent loads returned `t`,
and the second left the already-loaded library state byte-for-byte unchanged.
No cause or fix is claimed.

If `require` unexpectedly returns `nil`, cold-restart lisp65 and retry the
command once. If it happens again, preserve the requested library name and the
preceding session steps in a bug report. A standing read-only diagnostic is
retained for a second sighting.

## Not delivered in 1.2.4: `defstruct` and dynamic packages

`defstruct` and the associated dynamic package-loading freight are not part of
the v1.2.4 user surface. Their host-side designs and test artifacts are
development material, not commands promised by this release.

## Not delivered in 1.2.4: `gc`, `room` and `error`

The three diagnostic commands `(gc)`, `(room)` and `(error)` are not part of
the v1.2.4 user surface. They were designed and specified, then held back on
capacity: their cold read carrier measures 1,724 bytes against a session
deficit of 399, and re-fusing correctness-critical phases for a diagnostic
instrument was judged disproportionate. Nothing else in the product depends on
them; a user simply does not have them.

## Not delivered in 1.2.4: `restart-repl`

`restart-repl` is outside the contracted product surface for this era. A user
who wants a clean image restarts the machine.

## Active limitation: a fail-closed stop reports nothing

When the fail-closed guard trips, the system stops safely but prints no
diagnosis — the user sees the stop without being told what caused it. This is a
limitation of the *reporting*, not of the protection: the guard itself is doing
its job, and the stop is deliberate rather than a crash. A capture body that
would report the cause needs three bytes of fixed-block space that are not
available; the resident geometry is closed. If you meet such a stop, the
reproducer and the surrounding session are what the maintainers need.

## Informative performance positions

These measurements are visible by design but carry no release limit:

- one-argument published call: 0 frames in the fresh v1.2.1 G5 run;
- GC envelope: 17 frames for one collection and 96 contract block reads;
- cold boot: a 27.653-second upper bound from BASIC `RUN` to a captured screen
  during C2-lite stabilization. The prompt may have appeared earlier.

The argument and GC values are measurements, not hard release limits. The
nullary first-call and warm-call ceilings remain the claims below.

An additional v1.2.2 measurement found no frame difference between 1,000
otherwise identical `boundp` and `symbol-value` operations. The 2-byte
Bank-5 symbol-value read path therefore contributes less than half a frame
when projected across the 480 such reads in the isolated 89-frame collection
envelope. It is not the dominant GC term; that dominant term remains
unattributed. This is an informative measurement, not a GC latency claim.

## Retired: 1.1 definition-to-first-call latency exception

Status: **retired by the promoted 1.2 product**

The 1.1 exception allowed a first call after persistent definition to take
95--98 frames, with a 10-frame warm call, while requiring C2 as the non-
renewable 1.2 cure. It did not change the performance target and could not
renew automatically.

The retirement conditions are all satisfied:

- measurement separated product execution from harness and transport time;
- the acceptance ceilings were fixed before measurement at 16 frames first
  call and 10 frames warm;
- the Link-66 hardware run measured 1 frame first call and 0 frames warm;
- the final G5 repeat measured 0 and 0 frames;
- nested evaluation and RUN/STOP abort left the C2D state byte-identical;
- fresh G5 and G6 bound the same final product identity;
- promotion sealed the exact product and package sets.

Retirement scope remains intentionally narrow. v1.2.1 also measured the
one-argument direct-call path at zero frames, but does not turn that informative
value into a hard limit. No GC or cold-boot performance claim is created.

Machine-readable authority:
`config/v12-known-issues.json`.
