# Known Issues and Retired Exceptions

This is the maintained user-facing issue register for lisp65 1.5.0. Sealed
historical documents retain the wording that was true when they were issued;
this page states the current product boundary.

## Active v1.5.0 issue: boot refill can trust an incomplete DMA read

Status: **latent and timing-dependent; fixed in v1.6.0**

The v1.5.0 boot and library-refill path contains one unverified DMA read. On
unfavorable hardware timing it can accept an incomplete code refill as
successful; the likely visible symptom is a sporadic `*** vm: bad bytecode`
during startup or library loading. Cold-restart from the product disk if this
occurs.

The issue was found after the v1.5.0 release. Its shipped hardware sessions and
ordinary use completed successfully, and no public installation has reported
the symptom. v1.6.0 removes the unchecked path and verifies the final linked
reader. A v1.5.1 backport is not planned; that option remains open if a field
report arrives before v1.6.0 is released.

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

## Active limitation: `defstruct` is positional and visibly slow

v1.5 delivers positional, option-free `defstruct`. A definition publishes a
constructor, predicate, copier, and three functions per slot, so it is a much
heavier durable operation than an ordinary `defun`; wait for its result before
entering another form or opening the Freezer.

The historical red-frame mechanism was narrowed to a terminal control-transfer
corruption but its destroyed immediate return slot prevented naming the exact
writer. v1.5 arms a redundant terminal-return shadow guard. The release session
completed `(defstruct point x y)` and `(make-point 3 4)` with all four mismatch
records empty and no restoration, so the release claims successful guarded
execution, not that the historical writer was caught or healed.

## Retired in 1.5.0: `trace` and `untrace` absent

The Link-92 limitation is closed. v1.5 has a private exact function-cell ABI,
transactional wrapper publication and exact restoration. The hardware release
session traced a call, untraced it and invoked the restored original BCODE with
no trace output.

## Not delivered in 1.3.0: `gc`, `room` and `error`

The three diagnostic commands `(gc)`, `(room)` and `(error)` are not part of
the v1.3.0 user surface. They were designed and specified, then held back on
capacity: their cold read carrier measures 1,724 bytes against a session
deficit of 399, and re-fusing correctness-critical phases for a diagnostic
instrument was judged disproportionate. Nothing else in the product depends on
them; a user simply does not have them.

## Not delivered in 1.3.0: `restart-repl`

`restart-repl` is outside the contracted product surface for this era. A user
who wants a clean image restarts the machine.

## Editor transport finding: physical 64/64

Status: **no current product-stall claim**

One virtual-input diagnostic persisted 56 of 64 requested keys. The release
session then typed 64 keys on the physical keyboard, without observation during
the active window, and the buffer postcondition contained all 64. The virtual
56/64 result therefore points to the known virtual transport seam and is not
evidence of an editor product stall. The faster renderer remains because it
reduces the measured average from about 78 to 24 raster frames per key.

If physical typing stops responding naturally, press RUN/STOP once; cold-start
if the REPL does not recover. Preserve the preceding forms and approximate key
count. Reopening the parked diagnosis requires a natural physical recurrence
with a hardware arrival witness.

## Active v1.6-candidate finding: evaluator polling races Comfort capture

Status: **product mechanism attributed; single-owner fix under qualification**

A v1.6 development measurement slowly produced eight visible Comfort-REPL
characters using 11 physical character attempts. Product counters read
`raw=seen=stored=taken=8`: every event presented at the queue boundary was
read, stored and consumed, while three attempts were absent before that first
witness. The loss did not depend on fast typing or product backlog in this
measurement.

That arithmetic locates the loss before the capture IRQ's raw witness; it does
not prove that the platform failed to create the event. Final-ELF evidence
subsequently found the product's second reader of the same hardware queue:
`lisp_poll()` can consume and acknowledge an ordinary event while the Comfort
capture is armed. Whichever reader runs first owns that event, explaining both
the slow-typing loss and the smaller raw count.

The correction gives an armed capture sole ownership of the hardware queue;
`lisp_poll()` retains RUN/STOP through the independent matrix-pending latch.
Until the corrected final product passes hardware acceptance, repeat a missing
character normally. This finding is not a keyboard/core limitation.

## Active Ship limitation: RUN/STOP source not independently verified

Standalone Ship runtimes poll the historical KERNAL STKEY byte at `$91` for
RUN/STOP. Its meaning under the tested MEGA65 KERNAL has not yet been verified
independently. This does not affect ordinary physical keyboard input or the
hardware-proven `read-line` sample, but Ship programs must not rely on a
release claim for RUN/STOP until that seam is measured.

## Active limitation: a fail-closed stop reports nothing

When the fail-closed guard trips, the system stops safely but prints no
diagnosis — the user sees the stop without being told what caused it. This is a
limitation of the *reporting*, not of the protection: the guard itself is doing
its job, and the stop is deliberate rather than a crash. A capture body that
would report the cause needs three bytes of fixed-block space that are not
available; the resident geometry is closed. If you meet such a stop, the
reproducer and the surrounding session are what the maintainers need.

## Active limitation: an error during runtime-overlay work can stop fail-closed

Status: **pre-existing in v1.5; constructive recovery deferred to v1.7**

An ordinary reader or evaluation error while runtime-overlay code is active
can retire and clear the overlay while a control transfer into that generation
is still live. If that transfer is later taken, the cleared byte is decoded as
BRK and the existing fail-closed handler deliberately stops on a red-bordered
screen instead of returning to the prompt.

Cold-restart lisp65 after such a stop and preserve the form that preceded it.
The shipped v1.5 ELF already contains the same transient overlay phase, the
same relevant transfer origin and the abort/wipe/re-entry path; v1.6 did not
introduce this defect class. The exact observed transfer was reproduced only
on a v1.6 development candidate, so no claim is made that the identical
dynamic carrier was seen on released v1.5 hardware. A v1.7 item owns the
carrier-independent backstop at the execution boundary; v1.6 does not spend
closed resident capacity on a late recovery retrofit.

## Informative performance positions

These measurements are visible by design but carry no release limit:

- one-argument published call: 0 frames in the fresh v1.2.1 G5 run;
- GC envelope: 17 frames for one collection and 96 contract block reads;
- v1.5 cold reset to prompt: 36 seconds, compared with 31 seconds for released
  v1.4.0 on the same device and owner stopwatch. The five-second safety cost is
  accepted and all three boot phases are visible;
- v1.5 direct-path list reads/writes, string access and a published call: zero
  frames inside each timed body in the release session;
- an ordinary durable REPL form remains approximately 1.2 seconds because it
  performs publication and rollback work.

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

## Retired in 1.2.5: order-dependent `require`

Status: **fixed and hardware-proven**

In v1.2.3 and v1.2.4, calling `require` after an ordinary persistent
definition deterministically returned `nil`. The resolver incorrectly treated
every valid Session row as though it had to appear in the package index.

v1.2.5 checks the geometry of every persistent row but applies package
identity checks only to rows that actually match the package index. The
release-terminal hardware case defines two functions, then loads the package
twice; both calls return `t`, the package row is published after the ordinary
rows, the second call is byte-identical and C2J remains CLEAR. The former
“cold-restart and run `require` first” workaround is withdrawn.

Machine-readable authority:
`config/v12-known-issues.json`.
