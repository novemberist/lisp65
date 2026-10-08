# 2.5.5 — device session

**Date 2026-10-07, physical MEGA65, owner at the keyboard.** Product medium `D255.D81` = the 2.5.5 Final r1
medium (`build/card-255-final-r1/media-255/c255.d81`, 819,200 bytes, SHA-256
`4f0b76ad395ed861da104960859b8d9416750a00684dd4826a1193b14245523b`), user disk `D255U.D81` (SHA-256
`d607dc23427aec91a4c2b10506c0117829648c6623071299a9213a6c4468e603` before the session). The complete record is
`build/device-255-prep/owner-observations.txt` (timestamps in UTC, owner words in German); this report adds
nothing to it.

## Result: PASS, as a manual owner session

As in the 2.5.4 session there was **no device driver**: every row was typed and judged by the owner at the
physical keyboard. There is therefore no tool-clock boot time and there are no automated device rows; boot and
the save time are stopwatch values, and the two typing counts are the owner's counts. Rows that were not done
are listed at the end and are not claimed.

## Upload and readback

| Disk | Uploaded | Readback after upload | Readback after the session and a power cycle |
|---|---|---|---|
| `D255.D81` | new file on the SD card (transfer log: "does not yet exist on the file system") | byte-identical to the Final medium | unchanged, SHA-256 `4f0b76ad…523b` |
| `D255U.D81` | new file on the SD card | byte-identical to its source | SHA-256 `88578236…d52f`: three new files, `12ONE`, `12TWO` and `OUT20X40`; every other file unchanged; allocation map valid (13 entries) |

Transfer tool `tools/m65tools/mega65_ftp` (put, then get of the same name); logs and readback files under
`build/device-255-prep/upload-01` and `build/device-255-prep/readback-01`. The readback images are kept
untouched; the checks ran on a working copy. Whether the MEGA65 was power-cycled before the upload was not
recorded.

## Owner rows

| Row | Result | Observation |
|---|---|---|
| Boot by stopwatch | measured | unchanged: 20 s to `Initializing`, then 22 s to `L65>`. Owner: "Block1: Unveränder 20 + 22s" |
| Typing feel in the IDE editor | PASS, with the finding below | Owner: "Stark verbessert, Backspace immer noch leicht verzögert, stärker wenn Taste gehalten wird" (strongly improved; Backspace still slightly delayed, more so when the key is held) |
| Held key in the editor, empty line | measured | 227 characters in 10 s (owner count, 80-column screen) |
| Held key at the `L65>` prompt | measured | 202 characters in 10 s (owner count) |
| Two buffers with the physical RUN/STOP key | PASS | two buffers, edit, switch with `C-x C-p` and `C-x C-n` by hand, edit, RUN/STOP at idle, re-enter both: `ONE` = `FIRSTX`, `TWO` = `ABY` / `Z` as expected. Owner: "ja, hat alles funktioniert" |
| Freezer mount of `D255U.D81`, `m65d`, remount | PASS | Owner: "Alles wie erwartet" |
| Saving two buffers | PASS | both `save-buffer-to` calls returned `T`; host readback: `12ONE` = `alpha`, line feed, `gamma` (11 bytes); `12TWO` = `beta-delta` (10 bytes); exactly as expected |
| IDE save 20x40 with `save-buffer-to` | PASS | load `T`, save `T` in 4 s by stopwatch (2.5.4 device: 5 s); `OUT20X40` (739 bytes) byte-identical to `SRC20X40` on host readback |

The owner typed the two file names with the digit one instead of the letter l, so the files are named `12ONE`
and `12TWO`. Their contents are what the row expects.

**Reading of the two held-key counts (reviewer, not a measurement).** Both counts are about 20 to 23 characters
per second (about 44 ms per character in the editor). The REPL needs 14 ms per key in the emulator, so its
count is limited by the keyboard repeat rate, and the editor now reaches the same ceiling. The repeat rate
itself was not measured. No 2.5.4 device count exists for a held key. Emulator burst figures for comparison:
2.5.5 244 ms per 8 keys and 1,129 ms per 32 keys (30 to 35 ms per key); 2.5.4 687 and 2,327 ms (73 to 86 ms
per key).

The RUN/STOP row was at idle. A RUN/STOP in the middle of a key burst cannot be produced by hand; that case is
covered only by the emulator rows.

## Findings

1. **Backspace in the IDE editor is still slightly delayed, more so when the key is held** (owner, same
   sentence as the typing row). In the emulator Backspace costs 60.4 ms per key in 2.5.5 (2.5.4: 106.7 to
   132.6 ms) and an insert 57.3 ms.
2. **Side finding, not a 2.5.5 matter: Return at the empty `L65>` prompt leads to the native `LISP65>`
   prompt.** Owner: "das kann kaum so gewollt sein". This is the documented behaviour since 2.5.0 (an empty
   line leaves Comfort; `(repl)` re-arms it). The owner finds it surprising. A small card is proposed in the
   parked-items register: an empty Return stays in Comfort, and leaving gets an explicit way.

## Checklist error (not a finding)

The checklist said "40 columns per line". That was wrong: the screen has 80 columns. It was corrected during
the session, and the counts above are counts on the 80-column screen.

## Not done on the device

- the keymap seam rows (unchanged against 2.5.4; the emulator rows are identical);
- the long checklist rows;
- the `$D703` check: it stays open on hardware (the emulator probe survived; the emulator's DMA semantics are
  not shown);
- held-key counts at column 35 and at line 20;
- whether the MEGA65 was power-cycled before the upload was not recorded.

## Owner word after the session

2026-10-07T21:42:44Z, last line of the observations file. Asked: Ship and Publish of 2.5.5, yes or no; and
acceptance of the garbage-collection gate recorded as FAIL as in 2.5.4, with figures identical to 2.5.4; the
reviewer's recommendation was yes to both. Owner: "Freigabe erteilt. Wir folgen deinen Empfehlungen" (release
granted; we follow your recommendations). The word is bound through the authorization record of the Before-Ship
step.
