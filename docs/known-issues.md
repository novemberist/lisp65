# Known Issues and Retired Exceptions

This is the maintained user-facing issue register for lisp65 2.4.0. Sealed
historical documents retain the wording that was true when they were issued;
this page states the current product boundary.

The first three sections describe the current product: limitations that are
live, names that are deliberately not delivered, and informative measurements.
The final section preserves entries that were closed in an earlier release.

## Active product limitations

### Anonymous `lambda` outside `defun` bodies refused

Status: **known limitation of 2.4.0; designed refusal until promotion of
escaping callables**

Anonymous `lambda` forms are supported inside `defun` bodies; at the top
level they are refused with `VM: BAD BYTECODE`, the prompt recovers and
nothing already defined is affected.

This applies to every anonymous `lambda` in a top-level form outside a
`defun` body: `setq`/`setf`, `mapcar`, `funcall` and `let` forms alike.
Closures returned from functions defined with `defun` work. On the 2.4.0
device session, `(progn (setq savedlambda (lambda () 27)) 19)` gave the
exact `*** VM: BAD BYTECODE` at a live prompt, and `(+ 4 5)` then returned 9.
The same refusal occurs in 2.3.0. A top-level anonymous callable lives in a
temporary code image that is retired at the end of its form; until such
callables can be promoted to persistent publications, the refusal prevents
a later call through a dangling handle. Workaround: place the `lambda`
inside a `defun` body, or define a named function with `defun` instead.

### `require` inside a temporary compiled form

Status: **safe rejection shipped in 2.4.0 (accepted on device on a development world); full retirement repair deferred**

The transient-retirement fallback refuses `require` whenever temporary code
handles are live, before reading or publishing a package. This includes
already-loaded packages: `(time (require "inspect"))` returns `nil`, not a
load-time measurement. Use plain `require`, then use the package from a
separate prompt form. Native tests cover all five packages, subsequent use,
and byteidentity of previously published code after normal return and abort.
This contains the loading route; it does not repair general temporary-code
retirement. The full repair needs a separate placement card. See the
[fallback device report](planning/transient-retirement-device-report.md).

On the affected Storage-Owner and native-CRC worlds, `require` inside
`time`, or another form whose temporary code reaches the
Bank-2 code limit, can return `nil` without loading the package. For example,
`(time (require "inspect"))` is rejected while plain `(require "inspect")`
loads successfully. Use the plain form; a timed rejection is not a package
load measurement.

The affected resolver assumed the bank-end value 65,536 where the native
allocator uses its reserved-owner boundary, 60,758 on these worlds. This
is a resolver capacity-check defect, not evidence of an index-CRC or F011
failure. The Resolver successor consumes the native ownership facts; all
five fresh packages return `t` inside `time` on the native emulator and recover
to the prompt. That return is not sufficient to establish a usable load:
on the quarantined, unguarded Resolver successor, fresh `(time (require "defstruct"))` returns
frames and `t`, but the enclosing temporary-form cleanup wipes the package's
1,031 code bytes while retaining its directory entries. A subsequent
`defstruct` fails with `VM: BAD BYTECODE`, even with one slot. Plain
`require` in a fresh session passes the corresponding five-slot control.
Do not use that quarantined development world. The abort control also
demonstrates seven retained `buffer` entries with 104 erased code bytes.
The physical `467 t`
is a return witness only, not acceptance of package usability. See the
[timed-package attribution](planning/resolver-timed-package-attribution.md).
The earlier device rejection is not reclassified as a successful load. The reproduction
establishes these development worlds; it does not claim a new test of the
public 2.3.0 release. See the
[executed attribution](planning/index-crc-device-time-attribution.md) and
[host closure](planning/resolver-owner-final-report.md).

### 64 persistent code-image slots

Status: **2.4.0 ships grouped publication and a clean capacity refusal; slot reuse and persistent retirement remain open**

In 2.4.0 a session has 64 code-image slots. A definition group that no longer
fits is refused with `*** VM: OUT OF MEMORY`; the prompt stays live and earlier
definitions keep working. This includes a definition loop running inside a
form: on the 2.4.0 device session, from 15 images,
`(dotimes (n 60) (eval '(defun capn () 7)))` stopped at 63/64 images with
`*** VM: OUT OF MEMORY`, and `(capn)` then returned 7. A redefinition still
consumes an image, and slots are not reused. The development-world history
below explains how the limit was measured.

On the accepted post-2.3.0 world `cd656ff9…`, the directory has 64 image
slots. Eight are occupied after standard boot, eleven after all five packages
are loaded. A successful persistent definition consumes another image,
including a redefinition of the same function. A package may contain several
functions in one image; image count is not function count or free code bytes.

A five-slot `defstruct` generates **18** separate definitions: constructor,
predicate, copier, and reader/setter/functional-updater for each slot. From
eleven images, two such structures reach 47. The third publishes seventeen
definitions, reaches 64, and fails on the eighteenth with `VM: BAD BYTECODE`
instead of a capacity message. The partially defined structure is not an
atomic success; do not rely on it. A further ordinary definition is refused
with the same misleading message. In the measured native sequence the prompt
remains live, arithmetic and a previous structure's accessor still work,
and previous code-object bytes remain unchanged. This is not a general
failure-atomicity guarantee for compound forms.

Restart from the product medium before exhausting this capacity. Raising
symbol or code-byte limits alone does not raise the image limit. These are
executed development-world measurements, not a fresh test of public 2.3.0.

Set-A successor (2026-09-17): a five-slot group now publishes its 18 entries
in **one** image. The complete group at image 64 passes; the next group is
refused with OOM, with prior directory/code unchanged, recovery 9 and the old
accessor 42. On 2026-09-23 the physical Put-Kit batch also reached 64,
refused the next group with OOM, preserved all 897 previous directory/code
objects, and returned recovery 9 and accessor 42. See the
[device report](planning/put-kit-device-report.md). Redefinition still
consumes images; persistent slot reuse and
compaction remain Set B. The historical three-structure failure above must
not be presented as the current development behavior. See the
[Set-A final report](planning/definition-set-a-final-report.md).

### Non-tail recursion depth bound (raised from the 2.0.1/2.1.0 cliff)

Status: **changed in 2.2.0; documented depth and recovery rows accepted on device**

Non-tail Lisp calls no longer re-enter natively on the CPU hardware stack:
each call runs as a VM call frame on a soft stack of 16 frames. The
2.0.1/2.1.0 hardware-stack cliff (depth 12 returned, depth 13 fell into a
repeated `E29` loop needing a reset) no longer applies in that form.

In the documented host, emulator and device test, non-tail recursion at depth 16 returns
correctly and depth 17 is refused with a VM stack-overflow error while the
`lisp65>` prompt stays live:

```lisp
(defun sp-depth (n) (if (= n 0) 0 (+ 1 (sp-depth (- n 1)))))
(sp-depth 16)                      ; => 16
(sp-depth 17)                      ; refused, prompt stays live
```

The same 16-frame bound applies inside the compiler. Deep forms may be
refused; 16 is not a general safe source-nesting depth. The compiler's measured
self-compile peak is 26 frames, beyond this release's capacity.

The first long-line device test exposed a separate retirement-cleanup defect.
That defect is repaired in 2.2.0: the repeated 40-argument form now
returns the existing type error and a live prompt, followed by `(+ 4 5)` → 9.
Direct argument evaluation is iterative; this does not increase the existing
12-argument call/apply limit. Host tests separately prove recovery from stack
errors in direct evaluation and compilation of a top-level form.

A separate, older bound is the call protocol itself: a call passes at most
12 arguments (`VM_MAXARGS`), whether compiled or evaluated at the prompt,
and `apply` accepts a list of at most 12 elements. A call with more
arguments reports a type error at the prompt; it never worked in any release
because every VM frame reserves exactly 13 operand slots. Pass many values
as a list and fold them (`(let ((s 0)) (dolist (x xs s) (setq s (+ s x))))`)
or split the call. Raising the bound is registered with its price.

Tail calls are unaffected, as before. Printing deeply nested lists is a
separate native recursion path; the previously measured printer overflow at
23 nested list levels is not changed by this bound and is not re-measured
in this release.

### Unbound global reads as `nil`

Status: **documented; permissive by owner decision**

Reading an unbound global symbol evaluates to `nil` instead of raising an
error, the same permissive shape as the hot `car`/`cdr` opcodes above. A
checked variant was priced (an estimated 37 additional bytes on a hot path,
touching five suites that rely on unbound-reads-as-`nil` through
`load-lib`) and is kept in the register as an option; it is not shipped.

### Freezer during a definition

Status: **documented; deferred**

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

### Interrupt-generating cartridges

Status: **unsupported while C2-lite owns the interrupt vectors**

Do not use a cartridge that generates interrupts while lisp65 is running.
Passive storage, RAM, and utility cartridges that do not assert `/IRQ` or
`/NMI` are unaffected.

lisp65 cannot turn off or acknowledge cartridge interrupts in a
device-independent way. A single isolated interrupt within a raster-delimited
episode is tolerated, but a held or repeatedly asserted cartridge causes an
interrupt storm that deliberately stops the product on a red-bordered screen.
Cold-restart without the interrupt-generating cartridge before continuing.

### Post-GC out of memory

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

### A fail-closed stop reports nothing

When the fail-closed guard trips, the system stops safely but prints no
diagnosis — the user sees the stop without being told what caused it. This is a
limitation of the *reporting*, not of the protection: the guard itself is doing
its job, and the stop is deliberate rather than a crash. A capture body that
would report the cause needs three bytes of fixed-block space that are not
available; the resident geometry is closed. If you meet such a stop, the
reproducer and the surrounding session are what the maintainers need.

### Ship: RUN/STOP source not independently verified

Standalone Ship runtimes poll the historical KERNAL STKEY byte at `$91` for
RUN/STOP. Its meaning under the tested MEGA65 KERNAL has not yet been verified
independently. This does not affect ordinary physical keyboard input or the
hardware-proven `read-line` sample, but Ship programs must not rely on a
release claim for RUN/STOP until that seam is measured.

### Editor transport finding: physical 64/64

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

### 2.4.0 rows not yet verified on the device

Status: **open; owner rows**

The 2.4.0 device session was driven automatically, without the owner at the
machine. These rows were not run on the 2.4.0 medium and no claim is made
for them:

- RUN/STOP inside a running form. The host cannot inject it; the product
  reads RUN/STOP from the keyboard matrix.
- A cold power cycle, and the stopwatch feel of boot and typing.
- The physical `C-x C-c` exit from the IDE. The virtual keyboard cannot
  deliver `C-c`, because the product drains key-queue code `$03`; the IDE
  was left by a normal reset instead.
- Compile, save, reload and call on a writable copy of the medium, and the
  end-of-session SD readback of the uploaded files.

See the [device report](planning/release-candidate-device-report-2026-09-24.md).

## Names and packages not delivered in 2.4.0

The `inspect` package (`trace`/`untrace`) is delivered again since 2.3.0:
the Link-92 mechanism was closed in 1.5.0 and the functions existed as a
module, but no release between 1.6.0 and 2.3.0 placed the `inspect` row on
the selected medium. It is delivered on the 2.3.0 and 2.4.0 product disks
and loads by hand with `require`; see
"Retired in 2.3.0: library packages load by hand; not supported from
`INIT.L65`" below.

### `gc`, `room` and `error`

The three diagnostic commands `(gc)`, `(room)` and `(error)` are not part of
the user surface. They were designed and specified, then held back on
capacity: their cold read carrier measures 1,724 bytes against a session
deficit of 399, and re-fusing correctness-critical phases for a diagnostic
instrument was judged disproportionate. Nothing else in the product depends on
them; a user simply does not have them.

### `restart-repl`

`restart-repl` is outside the contracted product surface. A user who wants a
clean image restarts the machine.

### Delimiter matcher and cursor blink

Status: **hardware blocker preserved; absent from the selected product**

The shared resumable delimiter scanner, line-editor/IDE matcher, and idle
cursor blink passed host qualification but were not accepted on hardware. The
device build first exposed a publication-boundary arity defect and then hung
on the first cursor-left operation after loading. Under the predeclared
anti-rabbit-hole rule the whole block was descoped after its single repair
round. No matcher or blink claim is made for 1.7.0 or any release since, and
none of that diagnostic or feature freight is present in the selected product.

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

## Retired entries

These entries are closed. They are kept for provenance and are not current
product limitations.

### Retired in 2.4.0: a `defun` published inside a running form is destroyed

Status: **defect shipped in 2.3.0; fixed in 2.4.0**

In 2.3.0, a `defun` published from inside a running form (e.g. `eval` inside
`dotimes`) is silently destroyed; the next call fails with
`VM: BAD BYTECODE`; earlier definitions are intact. Workaround in 2.3.0:
define functions at top level. The cleanup of the form's temporary code
used the location of the last persistent publication and wiped that live
object.

2.4.0 fixes it: the cleanup wipes only the retiring temporary image's own
code. On the 2.4.0 device session, `(dotimes (n 1) (eval '(defun f1 () 7)))`
returned `NIL` and `(f1)` then returned 7.

### Retired in 2.4.0: an error inside `eval` within a running form loses the session

Status: **defect shipped in 2.3.0; fixed in 2.4.0**

In 2.3.0, an error inside `eval` called from within a running form (e.g.
inside `dotimes` or `let`) leaves the REPL without a prompt; reset required;
nothing already defined is lost. The fast recovery path ran its rollback
without first writing the journal, timed out and disabled every published
Lisp call, including the prompt. A definition loop running past the 64-image
cap inside a form is one instance.

2.4.0 fixes it: recovery retires the form's temporary code exactly as a
normal form does. On the 2.4.0 device session,
`(let ((q 1)) (eval '(capzz)))` gave the exact
`*** UNDEFINED FUNCTION: CAPZZ` at a live prompt and `(+ 4 5)` then returned
9. RUN/STOP inside a running form was not tested on the device (see above).

### Retired in 2.4.0: `compile-string` missing private compiler bridge

Status: **inherited defect found after 2.3.0; fixed in 2.4.0 (Set A); confirmed on the physical Put-Kit development world, not re-run on the 2.4.0 medium**

The documented form `(compile-string "(defun answer () 42)" "answer")`
is affected by a missing private primitive lowering: the delivered source
compiler calls the absent `%c2-control` function instead of primitive 66.
On the accepted development world, a positive compilation fails with
`UNDEFINED FUNCTION: %C2-CONTROL`; subsequent `(+ 4 5)` returns 9.
Do not treat the presence of `compile-string`, or its successful rejection
of invalid arguments, as evidence that compiling and saving works.

The Definitions card carries the bridge correction and a separate anonymous
helper relocation correction. Its acceptance must compile, publish, and call
the result natively, including a later definition containing a lambda helper.
Both corrections subsequently passed native host acceptance in
[Definitions Set A](planning/definition-set-a-final-report.md), including
compile/save/reload/call returning 7 and a later anonymous helper returning
42. On 2026-09-22 the same positive paths passed on the physical Put-Kit
world: first call 7, later helper 42, followed by SD readback of both new
files and all 19 previous files unchanged. See the
[current device report](planning/put-kit-device-report.md). This does not
change the published 2.3.0 bytes. The failure description above records
the predecessor. See the
[prerequisite attribution](planning/definition-group-pricing-r2.md).

### Retired in 2.3.0: IDE minibuffer display

Status: **reworked and device-accepted in 2.3.0**

In 2.2.0 the IDE could display only the first character of a minibuffer input
such as `demo1234`, and the cursor could appear inside the displayed prefix.
Emulator measurements of 2.2.0 showed roughly 0.2 seconds per minibuffer key,
increasing with input length, and 6.3 seconds to open the minibuffer.

2.3.0 delivers the minibuffer rework. The open path no longer rebuilds the
buffer area: opening `M-x` and Find-file went from about 278 M cycles
(≈ 6.9 s) to about 21 M cycles (≈ 0.5 s), and 16 typed keys from 171.7 M
cycles (≈ 4.2 s) to 49.5 M cycles (≈ 1.2 s). Every key is at or below its
2.2.0 cost, per-key work is O(1) in input length, and the whole pending key
queue is drained before one render. These are emulator cycles at 40.5 MHz,
not device wall-clock timings.

On the device, 17 rapidly typed characters appeared complete and in order.
That is a witness for that sequence, not a general zero-loss guarantee.
`C-g` restored the status row, re-entry showed empty input, and a missing
file name reported `source missing` and returned the cursor to the buffer.
While the minibuffer is active the bottom row shows only the prompt and the
input; the status row returns on exit or cancel.

### Retired in 2.3.0: interactive Ship sample cannot be built from the sources

Status: **repaired and device-accepted in 2.3.0**

The 2.2.0 interactive Ship sample's selected editor dependencies and input
interface did not close over the standalone runtime, so that sample could not
be built from the published 2.2.0 source archive. The main product was never
affected, and the `hello`, `random-q`, `long-runner` and `parity-toy` samples
were unaffected.

2.3.0 derives a standalone editor variant from the same product source over
the public input interface, and the sample builds again. On the device the
standalone sample boots to a blue screen, accepts `alex` and Return, and
prints `Hello, alex!`.

### Retired in 2.3.0: library packages load by hand; not supported from `INIT.L65`

Status: **default `INIT.L65` loading delivered in 2.3.0**

In 2.2.0 a library load from `INIT.L65` corrupted the source loader's sector
scratch, so a `require` executed from `INIT.L65` could leave the reader in an
unclosed-list state before the banner appeared. Packages had to be loaded by
hand at the prompt.

The 2.3.0 product disk ships an `INIT.L65` containing `(require "place")` and
`(require "string-extra")`. Both load at boot without any loading text —
neither the loader's `LOADING` line nor `require`'s own `loading <name>...`
echo — and the banner renders as it does without an `INIT.L65`. An
interactive `(require ...)` at the prompt keeps its echo. `buffer`,
`inspect` and `defstruct` continue to load by hand at the prompt. `require` now accepts a string as well as a quoted
symbol and returns `nil` for a missing package. A nested `load` from a loading
source is refused cleanly, without scratch corruption; `require` inside
`INIT.L65` is supported and supplies the default loading described above.
A library name longer than 16 characters is refused.

The product D81 carries the static `ide`, `idex` and `m65d` implementations
and their `load-lib` routes, plus the five optional packages:

| Package | Names it publishes |
| --- | --- |
| `buffer` | `make-buffer`, `buffer-ref`, `buffer-set!`, `buffer-length`, `bufferp`, `string->buffer`, `buffer->string` |
| `place` | `setf`, `push`, `pop`, `incf`, `decf` |
| `string-extra` | `capitalize`, `string-split` |
| `inspect` | `who-calls`, `trace`, `untrace` |
| `defstruct` | `defstruct` and its generated accessors |

With the IDE and all five packages loaded, the symbol reserve is exactly
32 free symbols and 387 free name bytes, against the 32/384 floor.

### Retired in 1.9.0: ordinary prompt input lost around collection

Status: **fixed and measured on physical hardware in v1.9.0**

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

The correction gives armed capture sole ownership of the hardware queue;
`lisp_poll()` retains RUN/STOP through the independent matrix-pending latch.
v1.9 delivers that capture path and makes the native editor its real consumer.
A fixed physical input sequence crossed a forced collection and ended with
`raw=seen=stored=taken=136`; the 2.0.0 acceptance repeated the case and ended
with 138. The equal, nonzero counters prove arrival, capture, storage, and
consumption in the delivered world; the earlier consumer mutation ends with
`taken=0` and remains a permanent counterexample.

This closes ordinary input loss while the native prompt is reading. It does
not claim type-ahead while evaluation is running. The larger Comfort REPL,
balanced multiline input, and history remain deferred despite sharing some of
the now-delivered input substrate.

### Retired in 1.9.0: Cursor Left/Right rejected at the native prompt

Status: **fixed and hardware-proven in v1.9.0**

The v1.7 and v1.8 native `lisp65>` prompt used a small C line collector.
Cursor Left or Cursor Right therefore rejected the current line with
`*** reader: invalid token`. This was not a v1.8 regression: sealed-ELF replay
showed the same collector in v1.7, while the v1.6 cursor acceptance had covered
only explicit Lisp `(read-line)` calls.

v1.9 routes the native prompt through the insertion-mode editor. Prompt,
editable text, and cursor share one editor-owned line; Cursor Left/Right,
insertion, and deletion were accepted on physical hardware, and the old error
did not appear. The editor is resident product freight and needs no optional
package or startup form.

### Retired in 1.6.0: boot refill can trust an incomplete DMA read

Status: **fixed and structurally gated in v1.6.0**

The v1.5.0 boot and library-refill path contains one unverified DMA read. On
unfavorable hardware timing it can accept an incomplete code refill as
successful; the likely visible symptom is a sporadic `*** vm: bad bytecode`
during startup or library loading. Cold-restart from the product disk if this
occurs.

The issue was found after the v1.5.0 release. Its shipped hardware sessions and
ordinary use completed successfully, and no public installation reported the
symptom before v1.6.0. v1.6.0 removes the unchecked path, verifies the final
linked reader, and rejects unsafe content-consuming DMA readers in generated
code as well as authored sources. No v1.5.1 backport is planned.

### Retired in 1.6.0: retired-overlay recovery can re-enter cleared code

Status: **execution-boundary backstop shipped and hardware-observed**

An ordinary reader or evaluation error while runtime-overlay code is active
can retire and clear the overlay while a control transfer into that generation
is still live. If that transfer is later taken, the cleared byte is decoded as
BRK and the existing fail-closed handler deliberately stops on a red-bordered
screen instead of returning to the prompt.

The shipped v1.5 ELF already contained the transient overlay phase and its
abort/wipe/re-entry class. v1.6 adds a carrier-independent execution-boundary
backstop and sanitizes all seven restored control/status register pairs before
the recovery return completes. The accepted hardware session deliberately
raised the ordinary type error `(>= nil 32)` and returned to a usable native
prompt; a following list form evaluated normally.

The claim is bounded to the shipped retired-window detector and recovery path.
An unrelated fail-closed stop can still present a red border without a text
diagnosis, as documented above.

### Retired in 1.5.0: `trace` and `untrace` absent

The Link-92 limitation is closed. v1.5 gained a private exact function-cell
ABI, transactional wrapper publication and exact restoration. The hardware
release session traced a call, untraced it and invoked the restored original
BCODE with no trace output.

This closed the mechanism, not the delivery: the `inspect` package that
publishes `trace` and `untrace` has not been on the selected product medium
since 1.6.0. See "Optional library packages are not on the product disk".

### Retired in 1.2.5: order-dependent `require`

Status: **fixed and hardware-proven**

In v1.2.3 and v1.2.4, calling `require` after an ordinary persistent
definition deterministically returned `nil`. The resolver incorrectly treated
every valid Session row as though it had to appear in the package index.

v1.2.5 checks the geometry of every persistent row but applies package
identity checks only to rows that actually match the package index. The
release-terminal hardware case defines two functions, then loads the package
twice; both calls return `t`, the package row is published after the ordinary
rows, the second call is byte-identical and C2J remains CLEAR. The former
"cold-restart and run `require` first" workaround is withdrawn.

### Retired: 1.1 definition-to-first-call latency exception

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

### Historical v1.5 optional-library limitation: `defstruct`

v1.5 delivered positional, option-free `defstruct`. A definition publishes a
constructor, predicate, copier, and three functions per slot, so it is a much
heavier durable operation than an ordinary `defun`; wait for its result before
entering another form or opening the Freezer.

The historical red-frame mechanism was narrowed to a terminal control-transfer
corruption but its destroyed immediate return slot prevented naming the exact
writer. v1.5 arms a redundant terminal-return shadow guard. The release session
completed `(defstruct point x y)` and `(make-point 3 4)` with all four mismatch
records empty and no restoration, so the v1.5 release claims successful
guarded execution, not that the historical writer was caught or healed. No
selected medium since v1.6 includes `defstruct`, so this paragraph creates no
delivery claim for any later release.

Machine-readable authority:
`config/v12-known-issues.json`.
