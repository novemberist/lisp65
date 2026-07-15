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

   `idex` is optional. Loading `m65d` before the swap avoids needing the product
   disk when the first save occurs.
7. Swap drive 8 to `media/lisp65-work.d81` or another valid 1581 disk.
8. Start the editor with `(edit)`.

A D81 selected in the Freezer is not retained across a reboot. Automatic cold
start is possible only when a default disk image has been configured separately
in the MEGA65 Config menu; this guide does not require that configuration.

Any valid non-product 1581 disk is writable; it does not need to be named
`L65WORK`. The system disk is denied by its product identity. SD-backed D81
images on the tested stock core do not expose a virtual physical-write-protect
switch, so the identity check is the relevant protection in that profile.

## REPL essentials

```lisp
(+ 20 22)                         ; evaluate an expression
(dir)                             ; list visible disk entries
(edit)                            ; enter the editor, loading IDE if needed
(load-file-to-buffer "demo")      ; load source into a buffer
(save-buffer-to "demo")           ; save the current buffer
(eval-buffer "demo")              ; evaluate a buffer in this session
(compile-buffer-to-lib "fasl0")   ; compile a buffer to an L65M library slot
(load-lib "fasl0")                ; load the compiled library
```

The persistent compiler writes to preallocated FASL slots. `compile-load` in the
editor combines compilation and loading.

## Editor keys

The editor follows a compact Emacs-style key set. `C-x` means press Control-X,
then the following control key.

| Key | Action |
| --- | --- |
| Arrow keys, `C-b`, `C-f`, `C-p`, `C-n` | Move left, right, up, or down |
| `C-a`, `C-e` | Start or end of line |
| `C-x C-a`, `C-x C-e` | Start or end of buffer |
| `C-v`, `C-z` | Page down or up |
| `C-o`, `C-u` | Move forward or backward by one word |
| `C-d`, Backspace | Delete forward or backward |
| `C-k`, `C-y` | Kill line and yank |
| `C-w`, `C-r` | Kill word and backward-kill word |
| `C-Space` | Set mark |
| `C-x C-x` | Exchange point and mark |
| `C-x C-r`, `C-x C-y` | Kill or copy the region |
| `C-x C-f` | Find a source file |
| `C-x C-s` | Save the current buffer |
| `C-x C-w` | Write the buffer under another name |
| `C-x C-d` | Open the source directory buffer |
| `C-x C-b` | Select a buffer |
| `C-x C-n`, `C-x C-p` | Cycle through buffers |
| `C-x C-k` | Compile the current buffer and load it |

Inside minibuffer prompts, `Tab` cycles candidates and `C-p` recalls the last
input for the same action. `M-x` exposes `find-file`, `save-buffer`,
`compile-load`, `goto-line`, and `eval-buffer`.

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
- One drive is supported; use the documented one-swap workflow.
- There is no on-device disk formatter.
- The editor uses fixed-capacity buffers and intentionally omits undo/redo.
- lisp65 is a Common Lisp–inspired subset, not full ANSI Common Lisp.
- Physical product-disk write protection was not applicable to the tested
  stock-core SD-D81 setup.
