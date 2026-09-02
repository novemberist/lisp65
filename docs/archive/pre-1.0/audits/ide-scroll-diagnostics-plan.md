# IDE Scroll Diagnostics Plan (retired)

Stand: 2026-07-08. Dieses Dokument war waehrend der Scroll-Debug-Session die
laufende W1-W9-Messmatrix. Die Matrix ist geschlossen: die Root Cause ist nicht
Stack-Tiefe, nicht DMA und nicht IRQ, sondern ein Farb-RAM-Adressierungsfehler.
Die langen Zwischenplaene wurden bewusst entfernt, damit neue Arbeit nicht mehr
auf ueberholte "naechster Test"-Abschnitte aufsetzt.

## Endbefund

Bei 80x25 liegen die Farbzellen ab Zeile 13 jenseits des klassischen 1-KB-
Fensters `$D800-$DBFF`. Alte Screen-Pfade schrieben trotzdem
`((uint8_t *)$D800)[off]` mit `off >= 1024`. Diese Stores landen in
`$DC00-$DFFF`, also in CIA/VIC-I/O. Der kritische Fall war `$DD00`
(CIA2/VIC-Bank-Select): ein Farbwert mit passenden Low-Bits kippte die
angezeigte VIC-Bank. Sichtbar wurde das als der lange verfolgte
"Scroll-Muell".

Der Produktfix ist `CRAM_WINDOW=1024` in `src/screen.c`:

- `scr_init` initialisiert nur `$D800-$DBFF`.
- `scr_put_at` schreibt Farbe nur fuer `off < 1024`.
- `scr_write_span` schreibt Screen-Codes weiter, begrenzt Farbbytes aber auf
  das sichere Fenster.

Damit bleibt Scrolling aktiv und sauber. Zeilen `>=13` haben im Default keine
Per-Zelle-Farbe; das ist ein kosmetischer Verlust, kein Stabilitaetsproblem.

## Verwarfene Spuren

**Soft-Stack-Overflow:** `STACK_GUARD` machte den Fehler zeitweise zu einem
sauberen Abbruch, aber spaetere Wasserzeichen zeigten keinen Stack-Overflow,
waehrend Muell sichtbar war. Der alte Befund war eine Timing-/Layout-
Verschiebung, kein Root-Cause-Beweis. `LISP65_STACK_GUARD` bleibt ein opt-in
Diagnosewerkzeug, kein Default-Core-Feature.

**DMA-Parameter/Descriptor:** W2, W6/W6B und W7 schlossen die normalen
`ext_dma`-/`vm_dma`-Zielparameter sowie CPU-sichtbare Descriptor-Korruption als
primaere Ursache aus. Die DMA-Negativbefunde waren korrekt; der eigentliche
Fehler war ein CPU-Store in den I/O-Bereich.

**IRQ/SCRNPTR:** W5/W8 beobachteten echte SCRNPTR-/VIC-Bank-Kipps. Die
Interpretation "asynchroner IRQ-Schreiber" war aber nur ein Zwischenmodell.
Der spaetere REPL-A/B-Test mit einem einzelnen `screen-put-char` erklaerte den
Kipp direkt ueber den Farbstore nach `$DD00`.

**CRAM2K:** `$D030`/CRAM2K machte die unteren Farbzellen sichtbar, regressierte
aber `load-lib`/Disk-Lib-Laden. CRAM2K bleibt ausgeschlossen.

**Screen-/EDMA-Scroll als Produktfix:** Isolierte EDMA-Screen/Color-Smokes sind
auf echter HW gruen, aber der produktnahe C-Pfad war footprint-rot und loeste
die Root Cause nicht. EDMA bleibt ein Mess-/R&D-Pfad, nicht Default.

## Aktueller Vertrag

- Default-Screenpfad: Clamp auf das sichere `$D800`-Fenster.
- Keine direkte Flat-Store-Loesung nach `$FF80000`; Live-HW sah Flat-Store nach
  Color RAM rot.
- Vollfarbe fuer Zeilen `>=13` nur als separat gegateter Enhanced-DMA-Pfad.
  Der zuerst vorgeschlagene fill-only Helper mit Uniform-Zeilenfarbe in
  `scr_write_span` wurde gemessen und verworfen: Im Core-IDE ist
  `scr_write_span` mangels `LISP65_SCREEN_WRITE_STRING` nicht live, im Full-
  Profil kostet die Integration ca. 199 B Text und reisst das Stack-Gap.
- Ship-Default: B-drop. Clamp bleibt korrekt; Zeilen `>=13` ohne Per-Zelle-
  Farbe sind kosmetisch.
- Kein per-character EDMA im normalen Highlighter-/Tipp-Hotpath. Ein spaeterer
  Bulk-in-Core-Spike darf nur zusammen mit OOM-/Render-Performance gemessen
  werden, nicht isoliert als Farbfeature.
- Kein `m65 -F` im normalen Deploy-/Testworkflow; harter JTAG-Reset bleibt ein
  Notfallwerkzeug fuer echte Freezes.

## Behaltene Artefakte

Diese Artefakte haben weiterhin Mehrwert und bleiben:

- `scripts/hw-color-ram-smoke*`: bestaetigt EDMA-Color-RAM und dokumentiert
  Flat-Store als rot.
- `scripts/hw-edma-screen-smoke*`: isolierter HW-Beweis, dass Screen+Color per
  EDMA technisch funktionieren.
- `build/screen-smoke-host`/`scripts/screen-smoke-main.c`: Host-Regression fuer
  den aktuellen Screen-Treiber.
- `LISP65_STACK_GUARD` und `LISP65_DMA_PROF`: opt-in Diagnoseflags fuer andere
  Speicher-/Performance-Fragen, nicht als aktive Scroll-Hypothese.

Weitere Kontextdetails stehen verdichtet in `docs/ide-performance-analysis.md`,
`docs/mega65-hardware-opportunity-audit.md` und
`docs/mega65-native-budget-strategy.md`.
