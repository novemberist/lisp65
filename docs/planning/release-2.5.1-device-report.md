# 2.5.1 — device session

2026-09-29. Reviewer-run session with the owner at the device. Driver:
`build/release-v2.5.1-device-r1/tools/s251.py`, derived from
`build/ide-exit-device-r1/tools/ix250.py`. This report reads existing receipts;
preparation made no device contact.

## Result: PASS

- **Medium:** `01-upload-01/receipt.json` records new `S251.D81` and a
  byte-identical SD readback, SHA-256
  `9978daa146b89cf71ad1d3f290d80cf74b197911e7854859f9e4aa9bb2fce441`.
- **Boot:** `boot-01/receipt.json`: 20.895 s to Initializing and 40.454 s
  to `l65>` from RUN, using the host tool clock. The owner power cycle
  before the session is reported in the reviewer handoff; the driver
  receipt explicitly records `power_cycle: false` and monitor resets.
  It does not independently attest a physical cold-boot stopwatch result.
- **Rows:** `rows-01/receipt.json`, 13/13 PASS. All receipt paths above are
  relative to `build/release-v2.5.1-device-r1/`.

| Receipt row | Result |
|---|---|
| default | `(+ 1 2)` → 3 |
| str-owner-example | `(print "hello` Return, five spaces then `world")`: evaluates, spaces retained |
| str-three-lines | Three-line string length → 5 |
| str-parens-inside | Parentheses inside a multi-line string: length → 5 |
| str-then-eval | Evaluation after the string → 3 |
| str-overclose-still | Unmatched close parenthesis reader error |
| bs-eol, bs-multi, bs-long, bs-continuation | Four Backspace rows PASS |
| ide-load | `(load-lib "ide")` → T |
| ide-exit-cxq | C-x q exits; subsequent evaluation → 9 |
| ide-reenter-kept | HELLO buffer retained; exit again |

The four string-related success rows include the post-string evaluation;
only three actually enter multi-line strings. The escaped-quote row was
not typed on device: the virtual keyboard map has no backslash. Its
coverage is emulator `build/strings-rows-r2/receipt.json` (72/72 PASS),
not a device result.

## Owner physical observations

Owner result, verbatim from the reviewer handoff (not embedded in the
machine receipts):

> Alle manuellen Tests erfolgreich. Tippgefühl bei normalem Tippen und Backspace erheblich verbessert

The owner physically tested typing and Backspace feel, the string example,
and C-x q in the IDE. These observations close those physical rows; they
are qualitative and do not establish device cycles/key.

## Still open

Stopwatch cold boot and physical RUN/STOP remain pending. Physical IDE
C-x C-c remains a known issue. Continuation lines stay uneditable after
Return; Up/Down walk history. The multi-line editing card follows 2.5.1.
