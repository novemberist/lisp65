# 2.5.2 — device session

2026-09-30. Reviewer-run session with the owner at the device. Driver
`build/device-252-prep/tools/d252.py` (runbook `build/device-252-prep/runbook.md`);
receipts under `build/device-252-prep/`.

## Result: PASS

- **Media:** after a power cycle, `D252.D81` (2.5.2 Final, SHA-256
  `ae4e2931bb79bc6d963a2334d67e0777e924c9b34db42ef16567f472c87a300d`) and the
  separate user disk `D252U.D81` were uploaded as new SD files and read back
  byte-identical (`upload-01`).
- **Boot** (`boot-01`): 20.9 s to Initializing, 40.9 s to `l65>` (host tool clock).
- **Automated rows** (virtual keyboard): all 21 groups PASS across `rows-01`
  (first two), `manual-limit-05` (641-byte limit, completed by hand after a
  driver halt) and `rows-04` (remaining 18): reopen previous line once and
  twice, `*** input limit` at 641 bytes, `*** history limit`, ten-entry history
  ring, multi-line strings, Backspace rows, IDE load / C-x q / re-entry,
  virtual RUN/STOP at the prompt and in the IDE, loading `ide` and `m65d`.
- **Owner physical rows** (`owner-observations.txt`), verbatim: "Alle manuellen
  Tests erfolgreich … Tippgefühl ist sehr gut" — typing and Backspace, reopening
  the previous line, the owner string example, physical C-x q in the IDE and
  physical RUN/STOP during a running form.
- **Directory-link fix** (`disk-01`, user disk mounted via the Freezer): nine
  files F0–F8, F0 in entry 0 of the first directory sector, F8 in the next
  sector. `(m65d-save "f0" "new0")` → 0; `(dir)` lists all nine files, also after
  `(m65d-remount)`. Host readback after a power cycle (`readback-01`): product
  disk unchanged (`ae4e2931…`), F0 = `new0`, F8 = `OLD8`, directory chain intact.

## Driver halts on the way (not product defects)

- The inherited screen decoder maps screen codes 27/29 (`[`, `]`) to spaces, so
  the driver first missed `[edit previous line]`; the device shows the brackets.
- Wrapped prompted input repeats the 5-column prompt margin on every wrapped row;
  the driver first assumed 80 columns.
- After a Return that makes the pending form larger than ~259 bytes, the display
  lags while the accepted slow path runs; keys typed meanwhile stayed queued and
  appeared afterwards (no key lost). The driver now waits longer there.

## Still open

Stopwatch cold boot (tool clock only). Physical IDE `C-x C-c` remains a known issue.
