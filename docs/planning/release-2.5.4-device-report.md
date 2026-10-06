# 2.5.4 — device session

**Date 2026-10-05, physical MEGA65, owner at the keyboard.** Product medium `D254.D81` = the 2.5.4 Final r1
medium (`build/card-254-final-r1/media-254/c254.d81`, 819,200 bytes, SHA-256
`250fdc763ae9e5b04cf149a6f2a7a3aa9fb293ff8da58e9a703e0c601efaef5d`), user disk `D254U.D81` (SHA-256
`d607dc23427aec91a4c2b10506c0117829648c6623071299a9213a6c4468e603` before the session). The complete record is
`build/device-254-prep/owner-observations.txt` (timestamps in UTC, owner words in German); this report adds
nothing to it.

## Result: PASS, as a manual owner session

Unlike the 2.5.3 session there was **no device driver**: every row was typed and judged by the owner at the
physical keyboard. There is therefore no tool-clock boot time and there are no automated device rows; boot is a
stopwatch value. Rows that were not done are listed at the end and are not claimed.

## Upload and readback

| Disk | Uploaded | Readback after upload | Readback after the session and a power cycle |
|---|---|---|---|
| `D254.D81` | new file on the SD card (transfer log: "does not yet exist on the file system") | byte-identical to the Final medium | unchanged, SHA-256 `250fdc76…ef5d` |
| `D254U.D81` | new file on the SD card | byte-identical to its source | SHA-256 `e8c0d728…a343`: one new file `OUT20X40` (739 bytes), byte-identical to `SRC20X40`; every other file unchanged; allocation map valid (11 entries, 3,106 blocks free) |

Transfer tool `tools/m65tools/mega65_ftp` (put, then get of the same name); logs and readback files under
`build/device-254-prep/upload-01` and `build/device-254-prep/readback-01`. A first local copy of the user disk
was altered on the host by `c1541 -validate`; it is kept under a name that says so and is not used. Whether the
MEGA65 was power-cycled before the upload was not recorded.

## Owner rows

| Row | Result | Observation |
|---|---|---|
| Boot by stopwatch | measured | 20 s to `Initializing`, then 22 s more to `L65>`: 42 s (2.5.3: about 20 s + 23 s) |
| Physical RUN/STOP at the prompt | PASS | `(while t nil)` aborted with `*** STOPPED (RUN/STOP)`, `L65>` back, `(+ 4 5)` gave 9 |
| Edit persistence with the physical RUN/STOP key | PASS | wait for the editor, type `abcdefgh`, RUN/STOP, reopen: text complete and identical to what was visible before the stop |
| Keymap seam, unbound key | PASS | `C-x f` showed `UNKNOWN COMMAND` in the status row |
| Keymap seam, bound key | PASS | after `(ide-bind-key 102 'seam-bang)` `C-x f` inserted `!` (text `AB!`) |
| IDE save 20x40 with `save-buffer-to` | PASS | 5 s by stopwatch (2.5.3 device reference 37.7 s, driver clock); file byte-identical on host readback |
| Freezer mount of `D254U.D81` and return | PASS | no problem reported |

Keys appear immediately on the device, so a RUN/STOP in the middle of a key burst cannot be produced by hand.
That case is covered only by the emulator rows (all 20 abort points on the Seed medium).

## Findings (none a 2.5.4 regression by current evidence)

1. **Type-ahead while the editor opens is lost.** Typing immediately after Return on `(ide "p1")` showed only
   `fgh` of `abcdefgh`. The editor entry resets the encoded-input counters (`(poke 188 252..255 0)` in `ide`,
   introduced by `1520bc2f`, before 2.5.3). The user guide and the known issues already do not claim type-ahead
   while an evaluation is running.
2. **Typing in the IDE editor is clearly slower than at the REPL.** Owner: the typing feel is considerably
   worse than in the REPL; when typing fast, letters arrive late; no characters are lost; no difference between
   typing and Backspace. The owner could not compare with the 2.5.3 editor ("we have not tested the editor for a
   long time") and notes that the editor was never really good and was never actively optimised.
   Emulator comparison of the editor (cycle counter, 40.5 MHz, Seed medium, 2.5.3 against 2.5.4): insert 122.3 against 124.2 ms per key at line length 1 and 148.0 against 150.0 ms at length 39, Backspace 104.9–130.4 against 106.7–132.5 ms, Return after 30 characters 460.6 against 462.9 ms; the ratio is about 1.013–1.017, a constant +73k cycles (1.8 ms) per key. A REPL insert costs 4.17 ms in both versions. In both versions a collection of 116–123 ms falls on about one in five or six editor keys, and a burst of keys is drawn once at its end. So 2.5.4 does not make the editor meaningfully slower; the editor is about 30 times slower per key than the REPL in both versions. Source: `build/card-254-ide-typing-r1/notes.txt` (emulator, not a device measurement).
3. **`(m65d-remount)` took very long.** No seconds recorded; owner: "I think it was always like that". The M65D
   image is byte-identical to 2.5.3; the emulator needs about 26 s.

## Owner release of the findings

The owner released the three findings as known limits for 2.5.4 on 2026-10-05; faster editor typing is the first card of the next cycle.

## Not done on the device

- the additional REPL rows of the checklist;
- large saves (50x40, 100x20) and the physical `C-x C-s` path (the save row used `save-buffer-to`);
- the out-of-memory rows;
- the `$D703` check: it stays open on hardware (the emulator probe survived; the emulator's DMA semantics are
  not shown);
- a comparison of IDE typing with the 2.5.3 editor on the device;
- whether the MEGA65 was power-cycled before the upload was not recorded.
