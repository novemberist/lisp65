# lisp65 1.1 User Guide

## What you need

- A MEGA65 running the stock-core SD-D81 profile used by the release
- The extracted `lisp65-1.1.0` release bundle
- Python 3 on a host computer for the one-time package verification
- One writable 1581 disk image for your work

The bundle supplies both `media/lisp65-product.d81` and a blank convenience
image, `media/lisp65-work.d81`. Any valid non-product 1581 image may be used as
the work disk.

## Verify the bundle

Run from the extracted bundle directory:

```sh
python3 verify.py
```

Do not use a bundle that fails. The verifier checks every packaged file, all 14
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

5. Wait for staging, the lisp65 banner, and the REPL.
6. Load the workbench composition while `L65SYS` is mounted:

   ```lisp
   (load-lib "ide")
   (load-lib "idex")
   (load-lib "m65d")
   ```

   IDEX is optional when its word, page, mark, region, search, and launcher
   commands are not needed. Load M65D before the one-drive swap when the session
   will save or compile files.
7. Swap drive 8 to `media/lisp65-work.d81` or another valid non-product 1581
   disk.
8. Enter the editor with `(edit)`.

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
(compile-buffer-to-lib "demo-lib") ; transactional arbitrary-name output
(load-lib "demo-lib")             ; load the compiled library
```

Persistent compilation no longer uses preallocated `fasl*` slots. `compile-string`
and the editor compiler path save arbitrary library names through the full M65D
copy-on-write transaction: allocation and verified staging happen first,
directory publication happens last, and the transaction remains bound to the
same mounted medium.

Example:

```lisp
(m65d-remount)
(compile-string "(defun answer () 42)" "answer")
(load-lib "answer")
(answer)                           ; => 42
```

## Editor keys

The authoritative 1.1 keymap is generated from the same source as its tests:
[Workbench key bindings](generated/ide-keymap.md). It contains 41 bindings.

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

Save important edits first. The 1.1 escalation ladder is:

1. RUN/STOP aborts the current evaluation and preserves the session.
2. Restart lisp65 from the product disk for a fresh Workbench session. The
   platform Reset button returns to BASIC; it does not restart lisp65.
3. Power-cycle for a fully cold start that also clears Attic state.

`restart-repl` is not part of 1.1. Three bounded pre-C2 implementations failed
their product-semantics or capacity gates; the feature returns with the C2.3
immutable-code/mutable-session architecture.

## Buffers

The optional `buffer` shelf library provides fixed-length mutable byte buffers:

```lisp
(load-lib "buffer")
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

The L65E-v1 overlay maps 60 stable error codes and supplies readable text for
the 43 codes reachable in the Workbench profile. Unknown or unavailable text
uses the allocation-free `Ehh` fallback, where `hh` is the two-digit hexadecimal
code. This is not a general condition system or user-handler API.

Wrong arity, invalid types, and unavailable functions fail loudly. After an
ordinary error the REPL remains usable; a mistyped form does not invalidate the
session.

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
- The sealed profile leaves 334 free symbol entries, 5,079 name-pool bytes, and
  168 directory entries. There is no dependency-safe `unload`.
- The first call after a persistent definition takes about 1.90–1.96 seconds on
  the reference MEGA65; isolated longer observations exist. Warm expressions
  take about 0.20 seconds. Enter related definitions as one block to amortize
  the reload. C2 direct-Attic execution is the committed 1.2 cure.
- M65D/editor saves support 1–8,192 bytes. Evaluator `load` has a separate
  38,400-byte staging ceiling; memory may constrain practical input earlier.
- The compiler builds Workbench L65M modules, not standalone runtimes or
  bootable application disks.
- Function metadata proves exact arity for 101 entries; 34 native or macro
  entries are explicitly unresolved, so complete integrated help is not
  claimed.
- The editor has fixed-capacity buffers and no undo/redo, interactive symbol
  completion, integrated help, or full structural editing.
- The screen scrolls character RAM but not color RAM. Text moving through the
  former banner rows may inherit the banner colors. This is display-only;
  `screen-clear` is not a workaround because it leaves color attributes intact.
- Xemu is a logic and boot-choreography prefilter, not a replacement for real
  F011, SD-buffer, Freezer, reset, media-swap, or timing tests.
- One drive is supported and there is no on-device disk formatter.
- Physical product-disk write protection is not applicable to the tested
  stock-core SD-D81 setup.
- lisp65 is a Common Lisp-inspired subset, not ANSI Common Lisp.
