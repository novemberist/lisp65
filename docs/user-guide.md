# lisp65 1.0 User Guide

## What you need

- A MEGA65 running the stock-core SD-D81 profile used by the release
- The extracted `lisp65-1.0.0` release bundle
- Python 3 on a host computer for the one-time package verification
- One writable 1581 disk image for your work

The bundle supplies both `media/lisp65-product.d81` and a blank
`media/lisp65-work.d81`.

## Verify the bundle

Run the verifier from the extracted bundle directory:

```sh
python3 verify.py
```

Do not use a bundle that fails verification. The verifier checks every packaged
file and the embedded hardware-acceptance evidence without consulting the live
source repository.

## Start from BASIC and perform the one-drive swap

1. Make `media/lisp65-product.d81` available on the MEGA65 SD card.
2. Power on the MEGA65 and wait for the BASIC 65 prompt.
3. Mount the product D81 in drive 8 using the Freezer, then return to BASIC
   without rebooting. If the image is accessible by name on the SD card, you
   can use BASIC's `MOUNT` command instead.
4. At the BASIC prompt, load and run the stager:

   ```basic
   DLOAD "AUTOBOOT.C65",U8
   RUN
   ```

5. Wait for staging to complete and for the Lisp REPL to appear.
6. Load the editor and persistence composition while `L65SYS` is mounted:

   ```lisp
   (load-lib "ide")
   (load-lib "idex")
   (load-lib "m65d")
   ```

   `idex` is optional only when its word, page, mark, region, search, and command-
   launcher features are not needed. Loading `m65d` before the swap is required
   for saving after the product disk is no longer mounted.
7. Swap drive 8 to `media/lisp65-work.d81` or another valid 1581 disk.
8. Start the editor with `(edit)`.

A D81 selected in the Freezer is not retained across a reboot. Automatic cold
start is possible only when a default disk image has been configured separately
in the MEGA65 Config menu; this guide does not require that configuration.

Any valid non-product 1581 disk is writable; it does not need to be named
`L65WORK`. The system disk is denied by its product identity. SD-backed D81
images on the tested stock core do not expose a virtual physical-write-protect
switch, so the identity check is the relevant protection in that profile.

## IDE input erratum for 1.0.0

The 1.0.0 editor implementation and its physical keyboard interface do not have
the same verified feature surface. The editor receives a KERNAL/PETSCII code,
not a complete MEGA65 key event with Control, MEGA, and Alt state. Existing
hardware UX receipts inject normalized key codes directly into the dispatcher;
they prove the editor backends on hardware but not every physical key chord.

The practical 1.0.0 rules are:

- Load `ide`, `idex`, and `m65d` while `L65SYS` is mounted. The immutable
  `README-FIRST.txt` in the release bundle omits the latter two loads; this live
  guide supersedes it.
- Use `C-x x` or `C-x Return` for the command launcher. Physical `M-x` is not
  implemented, despite the original table wording.
- `C-Space` is broken: its zero code collides with the driver's empty-queue
  sentinel. Mark and region commands are consequently not usable through the
  documented keyboard workflow.
- Arrow navigation is known to work. Other Control and `C-x` chords have tested
  command backends but no bound physical-key acceptance case and should be
  treated as experimental in 1.0.0.
- For a reliable save, exit the editor with Run/Stop and call
  `(save-buffer-to "file" "buffer")` at the REPL. M65D must already have been
  loaded before the disk swap.
- Persistent compilation requires an existing preallocated FASL target. The
  supplied blank `lisp65-work.d81` contains no such targets, so
  `compile-buffer-to-lib` and `compile-load` report `slot missing` unless the
  work medium was provisioned externally.

The planned 1.0.1 patch repairs the bundled load instructions and supplies
`fasl0`--`fasl2`, without changing the keyboard driver. The modifier-aware
keyboard path and a hardware-bound case for every documented binding are 1.1
work.

## REPL essentials

```lisp
(+ 20 22)                         ; evaluate an expression
(dir)                             ; list visible disk entries
(edit)                            ; enter the editor, loading IDE if needed
(load-file-to-buffer "demo")      ; load source into a buffer
(save-buffer-to "demo")           ; save the current buffer
(eval-buffer "demo")              ; evaluate a buffer in this session
(compile-buffer-to-lib "fasl0")   ; requires a preallocated L65M library slot
(load-lib "fasl0")                ; load the compiled library
```

The persistent compiler writes only to preallocated FASL slots. The blank work
D81 supplied with 1.0.0 has none; `compile-load` combines compilation and loading
only on externally provisioned media.

## Editor keys

The editor intends to provide the compact Emacs-style key set below. `C-x` means
press Control-X, then the following control key. For 1.0.0 this table describes
the dispatcher/backend mapping, not a complete physical-key acceptance claim;
see the erratum above.

| Key | Action | Tier / 1.0.0 note |
| --- | --- | --- |
| Arrow keys, `C-b`, `C-f`, `C-p`, `C-n` | Move left, right, up, or down | IDE; arrows hardware-observed, Control aliases not fully bound |
| `C-a`, `C-e` | Start or end of line | IDE; physical chord not fully bound |
| `C-x C-a`, `C-x C-e` | Start or end of buffer | IDEX; physical chord not fully bound |
| `C-v`, `C-z` | Page down or up | IDEX; physical chord not fully bound |
| `C-o`, `C-u` | Move forward or backward by one word | IDEX; physical chord not fully bound |
| `C-d`, Backspace | Delete forward or backward | IDE |
| `C-k`, `C-y` | Kill line and yank | IDE; physical Control chord not fully bound |
| `C-w`, `C-r` | Kill word and backward-kill word | IDEX; physical chord not fully bound |
| `C-Space` | Set mark | IDEX; broken in 1.0.0 |
| `C-x C-x` | Exchange point and mark | IDEX; depends on a mark that cannot be set through `C-Space` |
| `C-x C-r`, `C-x C-y` | Kill or copy the region | IDEX; depends on a mark that cannot be set through `C-Space` |
| `C-x C-f` | Find a source file | IDE; physical chord not fully bound |
| `C-x C-s` | Save the current buffer | IDE; physical chord not fully bound; use the REPL API when needed |
| `C-x C-w` | Write the buffer under another name | IDE; physical chord not fully bound |
| `C-x C-d` | Open the source directory buffer | IDE; physical chord not fully bound |
| `C-x C-b` | Select a buffer | IDE; physical chord not fully bound |
| `C-x C-n`, `C-x C-p` | Cycle through buffers | IDE; physical chord not fully bound |
| `C-x C-k` | Compile the current buffer and load it | IDE; requires a preallocated FASL slot absent from the supplied work D81 |

Inside minibuffer prompts, `Tab` cycles candidates and `C-p` recalls the last
input for the same action; these physical bindings are not end-to-end accepted
in 1.0.0. With IDEX loaded, `C-x x` or `C-x Return` opens the command launcher
for `find-file`, `save-buffer`, `compile-load`, `goto-line`, and `eval-buffer`.
There is no physical `M-x` binding in 1.0.0.

## Disk safety and recovery

M65D binds a transaction to the mounted medium and verifies writes. If a save
reports `medium changed during write; check both disks`, the transaction is
terminal and is not retried automatically.

1. Do not start another save.
2. Preserve images of both disks.
3. Validate the newly inserted disk with an independent 1581 tool such as
   `c1541` or the repository D81 oracle.
4. Check the most recently edited file on both media.
5. Restore the work disk from its last known-good copy if either the filesystem
   or file contents are uncertain.
6. Mount the intended disk explicitly and start a new save.

The measured Freezer race has an honest residual bound: at most one already
started sector may reach a newly inserted medium before status 12 stops all
further writes. The release does not claim atomicity inside that narrow window.

## Current limitations

- Release 1.0.0 is intended for exploration and small, backed-up projects, not
  irreplaceable data or unattended production use.
- The released baseline leaves 120 symbol entries, 2,160 name-pool bytes, and
  32 L65M directory entries. Library loads and definitions are append-only;
  there is no `unload`, and exhausting a pool requires a restart.
- The on-device compiler builds L65M modules for the current Workbench; it does
  not create standalone runtimes or bootable application disks.
- M65D and editor saves accept payloads from 1 through 8,192 bytes. Evaluator
  `load` has a separate 38,400-byte staging ceiling, but editor heap and string
  capacity may become the practical limit earlier. The maximum supported
  editable load/save round trip is therefore 8 KiB.
- Xemu is useful for logic and boot-choreography checks but is not a complete
  replacement for a MEGA65. F011 writes, SD buffer mapping, Freezer behavior,
  reset behavior, and hardware timing are not fully covered in an emulator-only
  setup.
- One drive is supported; use the documented one-swap workflow.
- There is no on-device disk formatter.
- The physical editor input path is not fully bound to the documented keymap;
  `C-Space` is broken and physical `M-x` is not implemented.
- The supplied blank work D81 contains no preallocated FASL target, so persistent
  compilation needs externally provisioned media.
- The editor uses fixed-capacity buffers and intentionally omits undo/redo.
- lisp65 is a Common Lisp–inspired subset, not full ANSI Common Lisp.
- Physical product-disk write protection was not applicable to the tested
  stock-core SD-D81 setup.
