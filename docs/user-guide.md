# lisp65 2.0.1 User Guide

## What you need

- A MEGA65 running the stock-core SD-D81 profile used by the release
- The extracted `lisp65-2.0.1` release bundle
- Python 3 on a host computer for the one-time package verification
- One writable 1581 disk image for your work

The bundle supplies `media/lisp65-product.d81` and a blank convenience image,
`media/lisp65-work.d81`. Any valid non-product 1581 image may be used as the
work disk. The product image contains the resident prompt editor and the IDE,
IDEX, and M65D libraries; there is no separate optional-library medium.

## Verify the bundle

Run from the extracted bundle directory:

```sh
python3 verify.py
```

Do not use a bundle that fails. The verifier checks every packaged file, all 19
product artifacts, and the embedded hardware-acceptance evidence without using
the live repository or network.

## Start from BASIC and perform the one-drive swap

1. Copy `media/lisp65-product.d81` to the MEGA65 SD card.
2. Power on the MEGA65 and wait for the BASIC 65 prompt.
3. Mount the product D81 in drive 8 using the Freezer, then return to BASIC
   without rebooting. BASIC's `MOUNT` command is also suitable when the image is
   accessible by name.
4. Load and run the stager:

   ```basic
   DLOAD "AUTOBOOT.C65",U8
   RUN
   ```

5. Follow the three visible phases — `STAGING MEDIA`, `BUILDING HEAP`, and
   `LOADING LIBRARIES` — then wait for the lisp65 banner and REPL.
6. Use Cursor Left/Right, insertion, and deletion directly at `lisp65>`; the
   one-line prompt editor is resident and needs no library load.
7. Load the workbench composition while `L65SYS` remains mounted. These are the
   full-screen editor and persistence libraries, not the prompt editor:

   ```lisp
   (load-lib "ide")
   (load-lib "idex")
   (load-lib "m65d")
   ```

   IDEX is optional when its word, page, mark, region, search, and launcher
   commands are not needed. Load M65D before the one-drive swap when the session
   will save or compile files.
8. Swap drive 8 to `media/lisp65-work.d81` or another valid non-product 1581
   disk.
9. Enter the editor with `(edit)`.

A D81 mounted through the Freezer is not retained across a reboot. Automatic
cold start requires a default disk configured separately in the MEGA65 Config
menu; this guide does not assume that configuration.

The system disk is denied by product identity. SD-backed D81 images on the
tested stock core expose no virtual physical-write-protect switch, so identity
denial is the applicable protection in this profile.

## REPL essentials

```lisp
(+ 20 22)                         ; evaluate an expression
(dir)                             ; list visible disk entries
(edit)                            ; enter the editor, loading IDE if needed
(load-file-to-buffer "demo")      ; load source into a buffer
(save-buffer-to "demo")           ; save the current buffer
(eval-buffer "demo")              ; evaluate a buffer in this session
(compile-buffer-to-lib "fasl1")   ; compile a buffer into an existing fasl slot
(load-lib "fasl1")                ; load the compiled library
```

`compile-buffer-to-lib` and `compile-file-to-lib` write only into a
preallocated slot whose name begins with `fasl`, and only when that slot
already exists on the mounted disk. Any other destination name sets the
`ide-error` reason `not fasl`, and a missing slot sets `slot missing`. To
publish a library under an arbitrary name, use `compile-string` directly, as
shown below.

The selected 2.0.1 product checks for `INIT.L65` after the resident world is
ready and before the first banner. The release medium deliberately omits the
file, so the normal release boot takes the silent absence path. On a derived
medium that supplies it, the file is evaluated once per cold boot. An open or
evaluation error returns to one live `lisp65>` prompt and is not retried.

The REPL accepts several forms on one input line and evaluates them from left
to right. If a later form has a reader error, earlier forms on that line have
already run; durable changes made by them are not rolled back. The error
applies to the remaining input, not to results already printed.

The native `lisp65>` prompt and explicit `(read-line)` calls use the same
focused insertion-mode editor. Cursor Left/Right and `C-b`/`C-f` move by one
character; `C-a` and `C-e` move to the endpoints; Delete removes backward and
`C-d` removes forward. Movement or deletion beyond an endpoint is a no-op.
The cursor-following viewport preserves the 250-character limit. Prompt,
editable input, and cursor share one editor-owned line. This is still a
single-line editor, not the deferred balanced multiline/history Comfort REPL.

The input queue has one active product owner. Capture is armed while the native
editor reads, and the delivered editor consumes from its ring; the evaluator
does not race it for ordinary events. A physical-device sequence crossing a
forced collection ended with `raw = seen = stored = taken = 138`. This proves
the interactive read phase used in the acceptance session. It does not promise
type-ahead while Lisp evaluation is running.

The release-terminal capacity reading for this unchanged product world is
107 free symbol slots and 1,467 free name bytes, above the required 32/384
floor.

`compile-string` saves an arbitrary library name through the full M65D
copy-on-write transaction: allocation and verified staging happen first,
directory publication happens last, and the transaction remains bound to the
same mounted medium. It does not need a preallocated `fasl*` slot; the two
IDE compile commands above still do.

Example:

```lisp
(m65d-remount)
(compile-string "(defun answer () 42)" "answer")
(load-lib "answer")
(answer)                           ; => 42
```

### Product-resident libraries

The 2.0.1 product D81 contains `ide`, `idex`, and `m65d`, and no other library
role. Load the libraries you need before swapping to the work disk. If M65D is
already active when the mounted image changes, run `(m65d-remount)` before
loading or saving. Historical optional packages such as `buffer`,
`string-extra`, `inspect`, `place`, and `defstruct` are not part of the
selected 2.0.1 medium or its hardware claim; `(load-lib "buffer")` and the
other package names therefore have nothing to load on the release disk.

Interactive Shift-Space is normalized to ordinary space. This matters for the
natural Lisp typing sequence `) (`, where Shift may remain held between the two
parentheses even though the screen displays an ordinary-looking space.

Boot library reads use the verified CPU/MAP refill path; the release verifier
also checks that the packed PRG contains the same resident facade bytes as the
linked product. A successful boot therefore does not treat an unverified DMA
completion signal as proof that library code is ready. The empty-journal
recovery path first derives quiescence from all 64 C2J bytes and skips six of
the eight former overlay transports; any uncertainty uses the unchanged
serial verifier.

## Build a standalone disk

The Ship Builder turns an L65P-v1 project into a bootable D81 whose entry has
fixed arity zero. From the source bundle, this command exercises the public
Ship form through its host front end:

```sh
python3 tools/host-lisp/ship_builder.py build \
  --form '(ship "interactive" :entry '\''main)' \
  --project examples/ship/interactive/project.l65p \
  --out interactive.d81
```

The destination must not already exist. A successful image contains the cold
stager, evaluator-free Runtime Core, the project's tree-shaken library closure,
the resolution lock, the project manifest, and its redistribution notice. A
failure leaves no partial destination image. Mount the resulting D81 as a boot
disk and cold-start the MEGA65; it does not require the Workbench disk.

The five supplied examples under `examples/ship/` cover a minimal entry
(`hello`), interactive `read-line` input (`interactive`), a long-running
computation (`long-runner`), `random` with Q8.7 math (`random-q`), and a small
parity toy (`parity-toy`). Start from one of their `project.l65p` files when
creating a new project.

## Iteration and random numbers

`while` evaluates its body while its test remains non-`nil`:

```lisp
(setq n 0)
(while (< n 10)
  (setq n (+ n 1)))
```

A tight loop is fastest when its compiled body stays within one streamed code
window. A backward jump across a window boundary reloads that window once per
iteration.

`random` returns an unbiased fixnum below a positive bound. Use `random-seed`
when a run must be repeatable:

```lisp
(random-seed 123)
(random 6)                         ; => 0 through 5
```

This generator is suitable for programs and games, not cryptography.

### Fixed-point numbers (`q`)

lisp65 numbers are 15-bit integers. For positions, speeds and anything
that moves by less than a whole unit per step, the `q` functions treat an
ordinary number as a **Q8.7 fixed-point value**: the low 7 bits are the
fraction. Raw `128` means `1.0`, raw `192` means `1.5`.

- Range: `-128.0` through `127.9921875`, step `0.0078125` (1/128).
- A Q8.7 value **is** a normal number — store it in lists and variables,
  and compare with plain `<`, `=`, `>`. No library needs loading.

```lisp
(int->q 3)          ; 3.0        (raw 384)
(q 1 64)            ; 1.5        (1 whole + 64/128)
(q+ a b) (q- a b)  ; add, subtract
(q* a b) (q/ a b)  ; multiply, divide (round to nearest)
(q->int a)          ; truncate toward zero
(q->string a)       ; exact decimal text, e.g. "1.5"
```

Sub-pixel movement, the typical use:

```lisp
(setq x (int->q 100))       ; start at pixel 100
(setq v (q 0 32))           ; 0.25 pixels per step
(setq x (q+ x v))           ; each step
(q->int x)                  ; whole pixel for drawing
```

Four steps accumulate to exactly one pixel. Multiplication and division
round to the nearest 1/128, exact halves away from zero. Overflow and
division by zero raise the normal arithmetic error — values never wrap or
saturate silently. `q->string` always prints at least one fractional
digit, and every q value has an exact, finite decimal form.

One rule inherited from the hardware: `q*` and `q/` use the MEGA65 math
unit, the same one ordinary `*` and `/` use. That is why they are fast;
nothing about it is visible in normal use.

### Measuring a form

`(time form)` evaluates `form` exactly once, prints the elapsed number of
raster frames, and returns the form's value unchanged:

```lisp
(time (random 100))            ; prints elapsed frames, returns the number
```

The release measured the frame counter at 51.966 Hz on the accepted hardware
session. Durations of 16,384 frames or more fail with a duration-overflow error
instead of wrapping silently.

### Keyboard input and pacing

`read-line` is the normal text-input interface for Workbench code and shipped
programs. It echoes printable input, supports DEL, stops on RETURN, and returns
a string:

```lisp
(setq name (read-line))
```

To read a number, parse the returned text and validate the object explicitly:

```lisp
(setq input (read-line))
(setq value (read-from-string input))
(if (numberp value)
    (write value)
    (write "Please enter a number"))
```

Ordinary non-numeric input such as `hello` reads as a symbol and is rejected
by `numberp`. Syntactically broken input takes the normal reader-error path.
`read-from-string` is not limited to numbers: it reads any Lisp form, so a
list-shaped command can be accepted without a separate command parser.

The line editor is implemented entirely in Lisp and owns the final screen row
while it is active. Lines longer than the screen width keep their newest
characters visible there; the returned string still retains the full line.

The maximum line length is 250 characters. Extra printable keys are ignored
until DEL or RETURN; RUN/STOP always aborts instead of becoming input.

For event-driven code, `(key-event 0)` polls and `(key-event 1)` waits. An
event has the form `(key code modifiers)`. `read-line` is preferred unless the
program needs individual key presses.

`wait` delays by raster frames using the same clock as `time`:

```lisp
(wait 26)                 ; about half a second on the accepted hardware
```

The admitted range is 0 through 16,383 frames, and RUN/STOP can interrupt a
wait. This is suitable for simple animation pacing without a tick callback.

### Language forms, characters, and string traversal

The compiler supports `let`, `let*`, local `setq`, ordinary parameters and
`&rest`, `while`, `dotimes`, `dolist`, `when`, `unless`, `cond`, `case`,
`lambda` and closures, `defun`, and `defmacro`. These are compiler-lowered
language forms, not ordinary functions; generated function lists therefore do
not contain all of their names.

Characters are numeric fixnum codes. There is no separate character type and
no `#\` literal syntax (`#'` function quote is the reader's supported `#`
form). Obtain a code with `string-ref` or use a number, compare it with `=`,
and convert case with `char-upcase` or `char-downcase`.

`every`, `some`, `filter`, `mapcar`, and `reduce` walk lists rather than
strings. Dialect V2 does not expose the former `string->list` and
`list->string` conversion names. For character-by-character work, iterate by
index instead:

```lisp
(dotimes (i (string-length text))
  (write-char (char-upcase (string-ref text i))))
```

Use direct operations such as `search`, `substring`, `string-prefix-p`,
`string-suffix-p`, `string-equal`, `string-trim`, `string-upcase`, and
`string-downcase` for packed strings.

## Editor keys

The authoritative L-full keymap is generated from the same source as its
tests:
[Workbench key bindings](generated/ide-keymap.md). It contains 41 bindings,
generated from `config/v11-l-lite-keymap.json`, whose status is the L-full
product table. The generated page and the executable consumers are projections
of that same authority.

Important conventions:

- `C-x Space` sets the mark. `C-Space` is unavailable because code zero is the
  GETIN empty-queue sentinel.
- `C-x x` and `C-x Return` open the exact-name command launcher; physical
  Meta/Alt identity is not claimed.
- `C-x C-c` returns to the REPL and preserves the active buffer.
- RUN/STOP is not an editor key. During evaluation it aborts to a usable REPL
  with `stopped (run/stop)`; while idle it has no product action.

The generated table, dispatcher data, evaluation cases, and hardware matrix are
derived from one registry. A documented binding therefore cannot be added
without its corresponding test declaration.

## Fresh sessions and recovery ladder

Save important edits first. The escalation ladder is:

1. RUN/STOP aborts the current evaluation and preserves the session.
2. Restart lisp65 from the product disk for a fresh Workbench session. The
   platform Reset button returns to BASIC; it does not restart lisp65.
3. Power-cycle for a fully cold start that also clears Attic state.

`restart-repl` is not part of the released surface. Three bounded earlier
implementations failed their product-semantics or capacity gates; the feature
is reserved for the immutable-code/mutable-session architecture.

## Buffers (not on the 2.0.1 medium)

The optional `buffer` shelf library provides fixed-length mutable byte
buffers. Like `string-extra`, `inspect`, `place`, and `defstruct`, it is **not
part of the 2.0.1 product disk**, so the sequence below cannot be run from the
release medium. It is documented here because the module and its contract are
still maintained:

```lisp
(load-lib "buffer")               ; not present on the 2.0.1 product disk
(setq b (make-buffer 16))
(buffer-set! b 0 65)
(buffer-ref b 0)                  ; => 65
(buffer-length b)                 ; => 16
```

A Buffer prints as the opaque marker `?`; this is not a readable
representation. Use `buffer-ref` and `buffer-length` to inspect it. Converting a
Buffer to a String transfers ownership and invalidates subsequent Buffer
operations on that object, as specified in the
[Buffer contract](contracts/first-class-buffer.md).

## Errors

The L65E-v1 overlay maps 63 stable error codes and supplies readable text for
the 44 codes reachable in the Workbench profile, 41 of which are addressed to
the user and three to maintainers. Unknown or unavailable text
uses the allocation-free `Ehh` fallback, where `hh` is the two-digit hexadecimal
code. This is not a general condition system or user-handler API.

Wrong arity, invalid types, and unavailable functions fail loudly. After an
ordinary error the REPL remains usable; a mistyped form does not invalidate the
session.

Since 2.0.0 the public list functions also fail loudly on an unsupported
argument domain instead of returning a plausible but invalid value:

```lisp
(length "abc")                    ; *** vm: type error
```

This covers `append`, `length`, `nth`, `nthcdr`, `reverse`, `last`, `member`,
`assoc`, `mapcar`, `mapcan`, `mapc`, `find`, `position`, `butlast`,
`copy-list`, `count`, `reduce`, `every`, `some`, `getf`, and `remf`, including
improper (dotted) list spines. The hot `car` and `cdr` opcodes are the
documented exception: `(car nil)` and `(car 1)` both return `nil`. See
[Known Issues](known-issues.md).

The v1.6 recovery boundary also catches a transfer into a retired overlay and
sanitizes restored control-state pairs before returning to the native prompt.
This was hardware-observed with an ordinary type error followed by a successful
list evaluation. It does not turn unrelated fail-closed faults into recoverable
conditions.

## Disk safety and recovery

M65D binds each transaction to the mounted medium and verifies writes. If a
save reports `medium changed during write; check both disks`, status 12 is
terminal and the operation is not retried automatically.

1. Do not start another save.
2. Preserve images of both disks.
3. Validate the newly inserted disk with an independent 1581 tool such as
   `c1541` or the repository D81 oracle.
4. Check the most recently edited file on both media.
5. Restore the work disk from its last known-good copy if filesystem or file
   contents are uncertain.
6. Mount the intended disk explicitly and begin a new save.

The measured Freezer race has an honest residual bound: at most one already
started sector may reach a newly inserted medium before status 12 stops all
further writes. The release does not claim atomicity inside that window.

## Current limitations

- Use backups. This release is intended for exploration and small projects,
  not irreplaceable data or unattended production use.
- Open the Freezer only while the REPL prompt is visible or the evaluator is
  otherwise idle. Freezer entry during a persistent definition/append
  transaction is not supported in C2.2; that crossing remains a named C2.3
  obligation. If it happens, return with F3 and cold-restart lisp65 before
  relying on the interrupted definition.
- Session metadata is finite and there is no dependency-safe `unload`.
- The dated 1.1 definition-to-first-call exception is retired. The 1.2
  acceptance measured a newly published nullary call at 1 frame cold and
  0 frames warm, with claimed ceilings of 16 and 10 frames respectively.
  The fresh v1.2.1 acceptance run also measured the one-argument direct-call
  path at 0 frames; that informative value is not a separate hard limit.
- Do not use interrupt-generating cartridges while lisp65 is running. Passive
  cartridges are unaffected; a held cartridge interrupt deliberately stops
  the product on a red-bordered screen.
- Undefined-function errors report the complete function name.
- One post-GC out-of-memory event in a 1,200-allocation `while` workload was
  not reproduced by the follow-up run. Preserve the exact form and preceding
  steps if a small-live-set OOM recurs.
- M65D/editor saves support 1–8,192 bytes. Evaluator `load` has a separate
  38,400-byte staging ceiling; memory may constrain practical input earlier.
- The Ship Builder creates bootable application disks from L65P-v1 projects,
  but does not turn arbitrary live Workbench session state into an image.
- Function metadata proves exact arity for 103 of its 139 entries; 36 native
  or macro entries are explicitly unresolved, so complete integrated help is
  not claimed.
- The editor has fixed-capacity buffers and no undo/redo, interactive symbol
  completion, integrated help, or full structural editing.
- A virtual-input diagnostic delivered only 56 of 64 requested keys, but the
  release session persisted 64 of 64 physical keystrokes with no observation
  during the typing window. No editor product stall is claimed from the
  virtual result. Preserve the preceding session if physical typing ever
  stops responding naturally.
- The screen scrolls character RAM but not color RAM. Text moving through the
  former banner rows may inherit the banner colors. This is display-only;
  `screen-clear` is not a workaround because it leaves color attributes intact.
- Xemu is a logic and boot-choreography prefilter, not a replacement for real
  F011, SD-buffer, Freezer, reset, media-swap, or timing tests.
- One drive is supported and there is no on-device disk formatter.
- Physical product-disk write protection is not applicable to the tested
  stock-core SD-D81 setup.
- lisp65 is a Common Lisp-inspired subset, not ANSI Common Lisp.
