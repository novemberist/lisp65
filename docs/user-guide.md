# lisp65 2.5.4 — current release boundary

2.5.4 is the current release candidate: its Final is built and sealed; it is not published. Device results for 2.5.4: PASSED on a physical MEGA65 on 2026-10-05 in a manual owner session (boot 42 s by stopwatch; see the [device report](planning/release-2.5.4-device-report.md)); large saves, out-of-memory rows and the `$D703` check were not done on the device, and type-ahead typed while the IDE editor opens is lost. The Before-Ship record is pending. The published release is 2.5.3. Emulator rows on the Seed medium (byte-identical to the Final medium) showed no product failure; three rows are not green and unchanged from 2.5.3 (see the release notes). See the [2.5.4 release notes](releases/2.5.4.md). The 2.5.3, 2.5.2 and 2.5.1 text below is historical.

What 2.5.4 changes for the user:

- An interrupted IDE edit (RUN/STOP while typing) keeps every editing step that had already finished; the key being processed at the abort may be lost. **Only the IDE path is protected: a direct `m65d-save` call is not protected by this mechanism.** The host proof covers aborts at VM instruction boundaries on the delivered IDE image; aborts inside native primitives, during garbage collection or at out-of-memory are the subject of emulator rows (all abort points passed on the Seed medium; the RUN/STOP stand-in there is a monitor write to the break flag and counts for the emulator only) and of one physical RUN/STOP row, which passed on the device for text that was visible before the stop. **Wait until the editor is on screen before typing: type-ahead typed while the editor opens is lost.**
- A loaded package can bind `C-x` plus a printable key with `(ide-bind-key KEY FUNCTION)`. `KEY` is the character code, `FUNCTION` (normally a quoted symbol) receives the current buffer and returns a new buffer, a message string or `nil`. Built-in keys cannot be overridden; an unbound `C-x` plus printable key shows `unknown command`.
- `C-x C-s`, `save-buffer-to` and `eval-buffer` build their source string through the staging primitive. Every IDE save is refused while a source file is loading (`save refused while a file loads`); a direct `m65d-save` outside the IDE is not guarded. On the device the 20x40 save took 5 s by stopwatch (2.5.3: 37.7 s).
- `(funcall (lambda ...) args)` compiles as the direct form (a lambda stored in a top-level form stays refused), `mapcan` accepts more than 12 results, and `eq`, `eql`, `logand`, `logior`, `logxor` and `ash` refuse other than two arguments.
- At the Comfort prompt a result deeper than 8 levels, larger than 1,100 conses or circular is refused with `*** result too deep, too large or circular`; explicit `prin1`/`print` and the native `LISP65>` prompt are not bounded. `defstruct` rejects colliding generated names; a recalled history entry with a comment is submitted at once.

---

# lisp65 2.5.3 — previous release boundary (historical, published)

2.5.3 was published on 2026-10-03. The text below is its boundary at publication; its statements that `mapcan` fails beyond 12 elements, that `eq`/`eql` surplus arguments are dropped or that a physical 50x40 save takes minutes describe 2.5.3, see 2.5.4 above.

2.5.3 is 2.5.2 plus larger IDE saves and `eval-buffer` runs, IDE editing fixes,
compiler fixes and safer disk handling. `C-x C-s`, `save-buffer-to` and
`eval-buffer` no longer build a character list for the whole buffer, and
`eval-buffer` keeps its source alive during compilation instead of stopping
early without a message. With one buffer open, switching buffers no longer
loses text, and every text edit now clears the mark. The compiler assigns
every pair of a multi-pair `setq` and refuses `car`, `cdr`, `consp`, `not`,
`null` (one argument) and `cons`, `mod` (two arguments) with other counts,
including on the product compiler path; the screen shows
`*** COMPILE FAILED%LCC-ERROR-INVALID-PARAMETER-LIST`. `nth` refuses dotted
tails anywhere in the list.

Disks: M65D writes only after a remount that has checked the whole disk
(every file chain against the allocation map). A disk with a doubly used
block, a live block marked free or an allocated block no file owns is refused
with status 13 (`disk allocation inconsistent; disk not written`), and after
an aborted save the next save is refused until a remount passes. There is no
reclaim of leaked blocks yet; a refused disk is repaired with an external
1581 tool or its files are copied to a fresh disk. Loading a file keeps its
exact bytes (trailing spaces, trailing empty lines and carriage returns; a
carriage return is drawn as a blank cell); files written by the pre-1.0
overwrite-in-place `save` now show their space padding. A full 144-file
directory remounts again. IDE save/eval limits in host fixtures are listed in
the [2.5.3 release notes](releases/2.5.3.md); they are test results, not
guaranteed limits.

Fixed in 2.5.3 (known in 2.5.2): after `*** VM: OUT OF MEMORY` the prompt
returns. The sticky out-of-memory flag is now cleared where the REPL regains
control. In emulator runs the prompt came back after runaway garbage in a
`let`-local, after a failed 100x40 IDE save, and while typing a 249-character
line with four IDE buffers (the keys typed after the error land on a new
`L65>` prompt as a continuation line).

New known issue in 2.5.3: a heap filled by data the program still holds (for
example a global list) cannot be released from the keyboard. The prompt
returns and short forms such as `(+ 1 2)` work, but typing the form that would
drop the data (`(setq l nil)`) runs out of memory while it is being typed,
because typing itself needs memory; the Comfort prompt `L65>` is replaced by
the native `LISP65>`, the same keys keep failing and the data stays live. A
reset is required. Runaway garbage, `let`-locals and failed IDE saves recover.
Observed in the emulator; on the device the message and the returning prompt
were seen and the freeing attempt was not repeated.

Observed once on the device in 2.5.3, cause unknown: after mounting a disk
through the Freezer and returning with F3 the display went black and the Freezer
hung; a power cycle was needed and the host readback showed every disk intact.
It did not recur in three later swaps. Save work and keep backups before a
Freezer swap. A physical `C-x C-s` on a 50x40 buffer took several minutes once
(the file was written correctly; wait for SAVED).

Still open in 2.5.3: `mapcan` with more than 12 input elements; individual
string literals over 255 bytes (`*** VM: BAD BYTECODE`); closures that capture
a `let` variable (`*** VM: BAD BYTECODE` at the Comfort prompt, the
anonymous-`lambda` limitation, also in 2.5.2); physical `C-x C-c`
(use `C-x q`); disks with REL files, GEOS files or a 1581 boot sector are
refused for writing; a byte-identical clone disk swapped in after the remount
is not detected; a swap before the first write of a save reports status 12;
no reclaim of leaked blocks; a disk chain changed between the loader's two
read passes is not rejected. Comfort input limits are unchanged from 2.5.2
(32 pending lines, 640 bytes, 250-character line, ten history entries of at
most 250 bytes each).

The compile-time nesting depth of `setq` and `let` forms equals 2.5.2 (gate
`lcc-nesting-ladder-check`, 35 shapes).

Measured so far, in the emulator on the Seed r8 medium (its D81 and ELF are
byte-identical to the Final r8, so the rows ran on the identical medium; see
the release notes): Comfort rows 79/79, Backspace rows 7/7, boot to `l65>`
+4.2 % to +4.4 % cycles against 2.5.2 (unchanged against the unshipped r7
candidate), Comfort typing mean 1,146,728 against 1,130,909 cycles/key
(+1.40 %, per-key median unchanged), native `.text` +340 B (cap +368 B, owner
decision 2026-10-02). These are emulator cycle measurements, not device
timings. Device results for 2.5.3: PASSED on a physical MEGA65 on 2026-10-03 (tool clock: 42.8 s to the first empty `l65>`; owner stopwatch about 43 s from `run`). Capacity (emulator, measured on
the r7 medium of an unshipped candidate and not repeated on r8): 7,088 bytes
of code space free at boot; `require` of `defstruct` costs 1,038 bytes and 24
symbols, `inspect` 558 bytes and 67 symbols, `buffer` 104 bytes; at most 64
code images. Running out of code space or images prints
`*** VM: OUT OF MEMORY` and the prompt returns. See the
[2.5.3 release notes](releases/2.5.3.md) for the complete list.

The 2.5.2 and 2.5.1 text below is historical. Statements there that save and
`eval-buffer` build a whole-buffer list, that the loader removes trailing
spaces and carriage returns, that a full directory is rejected on remount,
that a damaged allocation map can pass mounting, that switching a single
buffer loses text, that a stale mark can misplace typing, and that LCC drops
later `setq` pairs describe 2.5.2, not 2.5.3.

---

# lisp65 2.5.2 — previous release boundary (historical)

2.5.2 was 2.5.1 plus faster line editing, reopening earlier Comfort input and
a disk-directory fix. At an empty Comfort continuation line, Backspace reopens
the previous line (`[edit previous line]`); delete any automatic indentation
first. Up/Down still browse history. Comfort input limits: up to 32 pending
continuation lines, 640 bytes of accepted source including line-feed bytes
and indentation, 250 characters in the active editor line, and ten history
entries of at most 250 bytes each.

Measured emulator typing cost for the 40-character Comfort test falls from
1,635,493 to 1,130,909 cycles/key (−30.85%, about 40.4 → 27.9 ms/key at
40.5 MHz); these are emulator cycle measurements, not physical keyboard
timings. Saving into the first entry of a directory sector no longer erases
the link to the next directory sector. Individual string literals over 255
bytes still fail to compile with `*** VM: BAD BYTECODE`; the 640-byte source
limit does not enlarge the literal format. See the
[2.5.2 release notes](releases/2.5.2.md) for the complete list. 2.5.2 was
published on 2026-09-30.

The 2.5.1 text below is historical. Its statement that continuation lines are
not editable after Return and its older typing figures describe that
predecessor, not 2.5.2.

---

# lisp65 2.5.1 User Guide

## Comfort by default (2.5.1)

The product starts in Comfort at `l65>`. Balanced multiline input, automatic
indentation, string/comment-aware parenthesis tracking and ten-line Up/Down
history are available immediately. Excess closing parentheses print
`*** reader: unmatched close parenthesis` without evaluating the input.
Errors, RUN/STOP aborts and refusals return to `l65>` with definitions and
history intact. An empty line leaves to `lisp65>` and stays native; `(repl)`
re-arms Comfort. Top-level anonymous lambdas outside `defun` remain refused.

Boot takes about +8 s over 2.4.0 in the emulator (+7.65 s measured); the 2.5.0 automated device session
reported about +6.7 s on a host tool clock. Starting in Comfort costs +8 symbols, +105 name bytes,
+1 code image, +7 C2D entries/roots and five more boot collections. After exit
to the native prompt, the matched forced collection has +12 live cells and
+2.1% cycles; natural collection cycles are −1.7%. These are emulator
measurements, not device timings or worst-case pause guarantees. The owner
accepted this named GC cost for the inherited Comfort product.

Use `C-x q` to exit the IDE normally with buffers preserved; release Ctrl
before q. The owner physically confirmed C-x q on the released product.
Physical `C-x C-c` does not reach the IDE and remains a known issue.
Typing latency in the MEASURED native lane falls from 3.24 M -> 1.58 M
cycles/key (approximately 80 -> 39 ms). Backspace code-object reads fall from
roughly 1,200–1,800 -> 53 reads/key in the projected lane. The owner physically
confirmed considerably improved normal typing and Backspace feel. The earlier small Backspace tail change also
reduces host VM instructions. Comfort multi-line strings now evaluate and
display correctly, preserving typed spaces without automatic indentation
inside strings. Continuation lines are not editable after Return; Up/Down
always walk history. The multi-line editing card follows.
See the [2.5.1 release notes](releases/2.5.1-before-ship-r3.md).

## What you need

- A MEGA65 running the stock-core SD-D81 profile used by the release
- The published `lisp65-2.5.1` release bundle
- Python 3 on a host computer for the one-time package verification
- One writable 1581 disk image for your work

The bundle supplies `media/lisp65-product.d81` and a blank convenience image,
`media/lisp65-work.d81`. Any valid non-product 1581 image may be used as the
work disk. The product image contains the resident prompt editor, the IDE,
IDEX, and M65D libraries, and the six disk packages described in
[Product-resident libraries](#product-resident-libraries); there is no
separate optional-library medium.

Since 2.3.0, `IDE`, `IDEX` and `M65D` no longer appear as separate disk
files: their implementations remain in the static product, and the three
`load-lib` forms below still work. This reclaims 193 disk blocks and takes the
2.4.0 medium from 22 to 19 files. The 2.5.1 Comfort-default medium has 20 files.
`BUFFER` remains on disk as the optional L65S package loaded by
`(require "buffer")`; it is not a retired IDE image. The released Strings Final medium passed 13/13 automated device rows on
2026-09-29; the owner physically confirmed C-x q and the multi-line string example.

## Verify the bundle

Run from the extracted bundle directory:

```sh
python3 verify.py
```

Do not use a bundle that fails. The package verifier checks its own files
and evidence. 2.5.1 was published on 2026-09-29 after independent public-source
reproductions, reviewer sealing and the fresh-medium device session. See the
[published release note](releases/2.5.1-before-ship-r3.md) for evidence limits.
Retained Final readback is not bundle verification.

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
   `LOADING LIBRARIES` — then `Initializing...` until the lisp65 banner and
   Comfort prompt `l65>` appear.
6. Use the Comfort editor immediately. An empty line leaves to the native
   `lisp65>` editor; `(repl)` re-arms Comfort.
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

Loading a file into the IDE keeps its exact bytes: trailing spaces, trailing
empty lines and carriage returns are preserved, only line feed separates
lines, and loading then saving is byte-exact. A carriage return is drawn as a
blank cell (one column; the cursor can stand on it and Delete removes it). Files
written by the pre-1.0 overwrite-in-place `save` now show their right-hand
space padding as a final line of spaces; the next IDE save writes it back.

The selected 2.5.1 product checks for `INIT.L65` after the resident world is
ready and before the first banner. The release medium supplies the file, so
the normal release boot evaluates it once per cold boot. An open or
evaluation error returns to one live `lisp65>` prompt and is not retried.

The released `INIT.L65` requires `place`, `string-extra` and `repl-comfort`,
then requests deferred Comfort entry after INIT returns. The packages load without any loading
text: neither the loader's `LOADING` progress line nor `require`'s own
`loading <name>...` echo appears, and the banner renders exactly as it does
without an `INIT.L65`. An interactive `(require ...)` typed at the prompt
keeps its `loading <name>...` echo. `buffer`, `inspect` and `defstruct` are
loaded by hand at the prompt.

`require` accepts a string as well as a quoted symbol: `(require "place")`
returns `nil` if the package is absent. If the resolution table is full, it
reports the existing out-of-memory error; restart from the product disk
before loading further packages. A nested `load` from a loading source is
refused cleanly, with the existing `LOAD: CANNOT OPEN` error and no scratch
corruption, before it can replace the active source stream. `require` inside
`INIT.L65` is supported and supplies the default loading described above.
A library name longer than 16 characters is refused.

Loading both packages by default consumes space earlier; it does not load
them a second time when they are later explicitly required. On the 2.5.1 product, with the IDE and
all six packages including Comfort loaded, capacity is finite; the optional-library
244/5,415 reserve measurement is historical, not a default-product measurement. These independent
limits are not a promise that all can be exhausted simultaneously.

The prompt-only minibuffer frame changes physical heap placement: nine live
cons cells move from the local to the external heap. Its named cost is
**37,665 additional emulated cycles per collection**, about **0.93 ms** at
40.5 MHz, with unchanged collector code and fully attributed CPU/DMA costs.
The fixed 1,160-event input sequence collects once in each world, including
warmup. This is a measured heap-layout cost, not a relaxed GC limit or a
worst-case pause guarantee. Emulator cycle figures are never device
wall-clock timings. Comfort uses a disk library plus the resident recovery hook.

The native prompt also moves up on wrapped lines: when the input wraps,
`lisp65>` stays beside the start of the input on the upper row. Shrinking
back across the wrap boundary moves the prompt down and leaves the released
upper row empty.

A call passes at most 12 arguments, at the prompt and in compiled code, and
`apply` takes a list of at most 12 elements; longer argument lists report a
type error. Fold long value lists instead of passing them as arguments. See
Known Issues, "Non-tail recursion depth bound", for the related frame bound.

The REPL accepts several forms on one input line and evaluates them from left
to right. If a later form has a reader error, earlier forms on that line have
already run; durable changes made by them are not rolled back. The error
applies to the remaining input, not to results already printed.

The native `lisp65>` prompt and explicit `(read-line)` calls use the same
focused insertion-mode editor. Cursor Left/Right and `C-b`/`C-f` move by one
character; `C-a` and `C-e` move to the endpoints; Delete removes backward and
`C-d` removes forward. Movement or deletion beyond an endpoint is a no-op.
The cursor-following viewport preserves the 250-character limit. Prompt, editable input and cursor share an editor-owned logical line,
which may occupy several screen rows. This is a single-logical-line editor. Default Comfort adds
balanced multiline input and history.

A logical line longer than the screen row now soft-wraps onto the row(s)
above it instead of scrolling its own content sideways: the line is laid out
in screen-width windows, anchored at the editor's own (bottom) row, and every
wrapped row keeps the same prompt indent as the first row. Backspace, cursor
movement, and insertion all work correctly across a wrap boundary, including
deleting or reflowing text right at the boundary.

The input queue has one active product owner. Capture is armed while the native
editor reads, and the delivered editor consumes from its ring; the evaluator
does not race it for ordinary events. In the historical 2.0.0 acceptance, a physical-device sequence crossing a
forced collection ended with `raw = seen = stored = taken = 138`. This proves
the interactive read phase used in the acceptance session. It does not promise
type-ahead while Lisp evaluation is running.

The earlier R2-world reading without optional packages was 106 free symbol
slots and 1,458 name bytes; it is not a fresh reading of the expanded library
layout in this release. See
[Product-resident libraries](#product-resident-libraries) for the reading
with all five optional packages loaded and for the required 32/384 floor.

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

The 2.5.1 product D81 carries the static `ide`, `idex`, and `m65d`
implementations, and six disk packages: `buffer`, `place`, `string-extra`,
`inspect`, `defstruct` and `repl-comfort`. Load the libraries you need before swapping to the work disk.
If M65D is already active when the mounted image changes, run
`(m65d-remount)` before loading or saving.

`ide`, `idex`, and `m65d` keep loading with `load-lib` as in earlier
releases:

```lisp
(load-lib "ide")
(load-lib "idex")
(load-lib "m65d")
```

Load an optional package at the native prompt with `require` and either a
string or a quoted symbol, for example `(require "place")` or
`(require 'place)`. `require` interns the package name symbol as an ordinary
side effect of resolving it, the same as typing any other symbol, and returns
`nil` for a missing package; packages listed as dependencies in the library
index are loaded first. Library names given to `load-lib` and `require` are
matched case-insensitively, so `(load-lib "IDE")` and `(load-lib "ide")` are
equivalent. A library file the loader refuses — wrong format, or larger than
the 8,192-byte envelope — returns `nil` and leaves the running world and the
prompt intact.

`place` and `string-extra` are loaded automatically by the `INIT.L65` on the
product disk. Load `buffer`, `inspect` and `defstruct` by hand after the
banner, or from your own source once it is running.

| Package | Names it publishes |
| --- | --- |
| `buffer` | `make-buffer`, `buffer-ref`, `buffer-set!`, `buffer-length`, `bufferp`, `string->buffer`, `buffer->string` |
| `place` | `setf`, `push`, `pop`, `incf`, `decf` |
| `string-extra` | `capitalize`, `string-split` |
| `inspect` | `who-calls`, `trace`, `untrace` |
| `defstruct` | `defstruct` and its generated accessors |

User code shares symbol, name and code capacity with the libraries, so
what you load changes how much room your own program has. Since 2.4.0 the
symbol table holds 1,008 symbols; the name pool occupies the top of bank 1.
In the 2.4.0 device session, with the IDE and all five packages loaded, the
IDE status row showed 761 of 1,008 symbols in use. The 2.3.0 reading was
exactly 32 free symbol slots and 387 free name bytes, against the floor of
32/384. A session's own definitions draw on the same pools, so a working
session shows less. Loading fewer packages leaves more. Symbols, name bytes
and the 64 code images of a session are independent limits and cannot be
assumed to be exhaustible simultaneously.

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
not contain all of their names. `setq` with several pairs assigns every pair in
order and yields the last value; an odd number of arguments is refused. `car`,
`cdr`, `consp`, `not` and `null` need exactly one argument, and `cons` and
`mod` exactly two. In a compiled form such as a `defun` body, any other count
is refused at compile time; the screen shows
`*** COMPILE FAILED%LCC-ERROR-INVALID-PARAMETER-LIST` (the internal name
follows the text directly and does not say which builtin or how many arguments
were expected). The same call typed as a top-level form reports
`*** WRONG ARGUMENT COUNT`. Both are emulator observations on the 2.5.3 Seed
r8 medium; the prompt recovers. An anonymous `lambda` is supported inside a
`defun` body; at the top level it is refused with `VM: BAD BYTECODE`, the
prompt recovers and nothing already defined is affected (see
[Known Issues](known-issues.md)).

Characters are numeric fixnum codes. There is no separate character type and
no `#\` literal syntax (`#'` function quote is the reader's supported `#`
form). Obtain a code with `string-ref` or use a number, compare it with `=`,
and convert case with `char-upcase` or `char-downcase`.

The MEGA65 `£` key is the quasiquote character: `£(1 ,(+ 1 1))` evaluates to
`(1 2)`; `,` means unquote and `,@` means unquote-splicing. On the device,
PETSCII `$5C` is echoed as `£`; in host source files the same byte is written
`\`. ASCII backquote remains accepted. Inside strings, backslash retains its
escape meaning. `(quasiquote …)` and `(unquote …)` spelled out remain
accepted as well.

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
[Workbench key bindings](generated/ide-keymap.md). It contains 42 bindings,
generated from `config/v11-l-lite-keymap.json`, whose status is the L-full
product table. The generated page and the executable consumers are projections
of that same authority.

Important conventions:

Since 2.3.0 the prompt-only minibuffer gives the active input the complete
bottom row: for example `M-x [find-file]`, `Find file: [scratch]` or
`Goto line: `. The buffer name, modified mark and symbol counter are hidden
while entering a command; the cursor follows the displayed input. Leaving or
cancelling the minibuffer restores the normal status row. A missing file name
reports `source missing` and returns the cursor to the buffer.

- `C-x Space` sets the mark. `C-Space` is unavailable because code zero is the
  GETIN empty-queue sentinel. Since 2.5.3 every text edit clears the mark; set
  it again with `C-x Space` before `C-x C-x` or a region command.
- `C-x x` and `C-x Return` open the exact-name command launcher; physical
  Meta/Alt identity is not claimed.
- `C-x q` exits normally and preserves buffers; release Ctrl before q. The
  IDE-exit predecessor passed virtual-keyboard device rows; physical keys remain open.
- Since 2.5.4 a loaded package can bind further `C-x` plus printable-key
  commands with `(ide-bind-key KEY FUNCTION)`; built-in bindings cannot be
  overridden and an unbound `C-x` plus printable key shows `unknown command`.
  A `C-x` prefix left pending by RUN/STOP is reset.
- `C-x C-c` remains logically bound, but physical Ctrl-C is drained before
  the IDE and leaves any pending C-x prefix waiting for the next delivered key.
- RUN/STOP is not an editor key. During evaluation it aborts to a usable REPL
  with `stopped (run/stop)`; while idle it has no product action. Since 2.5.4
  an abort during IDE typing keeps the editing steps that had finished (the
  key being processed may be lost); this protects the IDE path only, not a
  direct `m65d-save`. The emulator rows passed with a monitor write to the
  break flag as the stand-in for the key; the physical RUN/STOP row passed on
  the device (text visible before the stop was complete after re-entry).

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

## Buffers

The optional `buffer` package provides fixed-length mutable byte buffers. It
ships on the 2.4.0 product disk; load it by hand with `require`, as described
in [Product-resident libraries](#product-resident-libraries):

```lisp
(require "buffer")
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
improper (dotted) list spines. `nth` checks the whole list, so a dotted tail
behind the requested element is also a type error. The hot `car` and `cdr` opcodes are the
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

Writing is enabled only by a remount (the editor remounts automatically when
a save needs it). The remount reads the whole directory and every file chain
and compares them with the block allocation map (BAM). If a block is used by
two files, used but marked free, or allocated but owned by no file, the save
reports `disk allocation inconsistent; disk not written` (status 13) and
M65D writes nothing to that disk until a later remount passes. After an
interrupted save (RUN/STOP, error) the next save returns status 8 without
writing and needs a remount, which runs the check again. An interrupted save
can leave unowned blocks behind; in host tests of interruptions between
completed sector writes the old or new file stayed readable, but the disk is
then refused. Copy your files to a fresh disk, or repair the disk with
an external 1581 tool (for example `c1541` `validate`). Disks carrying REL
files, GEOS files or a boot sector are also refused, because their extra
blocks are not reachable through file chains. Reclaiming leaked blocks is
planned for a later release. Two disks with identical name and ID cannot be
told apart, and a swap before the first write of a save reports status 12
although nothing was written. A remount takes one sector read per file block,
so it is slower on a well-filled disk.

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
- Since 2.5.3, `C-x C-s`, `save-buffer-to` and `eval-buffer` no longer build a
  character list for the whole buffer. In host fixtures (588 additional heap
  cells, 8,049 additional arena bytes) the last successful buffer was 196 lines
  of 20 characters, 99 lines of 40 characters or 57 lines of 70 characters
  without the edit cache, and 119, 98 or 56 lines with it. These are host test
  results, not guaranteed limits; other live data, many short lines and the
  evaluated program can need more memory. In emulator runs on the 2.5.3 Seed
  r8 medium, saves of 20x40 and 50x40 lines and `eval-buffer` of 5 and 50 forms
  passed, and a 100x20 save passed in a fresh session; a 100x40 save ran out of
  memory, the prompt returned and nothing was written (next item).
- Out of memory: in 2.5.2 the prompt could stay dead after
  `*** VM: OUT OF MEMORY`; in 2.5.3 it returns (runaway garbage in a
  `let`-local, a failed IDE save, typing with many IDE buffers). **A heap filled
  by data the program still holds (for example a global list) cannot be
  released from the keyboard:** typing the dropping form runs out of memory
  while it is typed, the Comfort prompt gives way to the native `LISP65>` and
  the data stays live. Reset (power-cycle); unsaved buffers are lost. Observed
  in the emulator only. See [Known Issues](known-issues.md).
- Closures that capture a `let` variable, such as
  `(funcall (lambda () (setq s i)))` at the Comfort prompt, gave
  `*** VM: BAD BYTECODE` in 2.5.2 and 2.5.3. 2.5.4 compiles
  `(funcall (lambda ...) args)` as the direct form (the emulator rows on the
  Seed medium passed); a lambda stored in a top-level form stays refused.
- Since 2.5.4 a direct `m65d-save` is not covered by the edit-persistence
  mechanism and does not refuse a save during a source load; both protections
  apply to the IDE path only.
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
