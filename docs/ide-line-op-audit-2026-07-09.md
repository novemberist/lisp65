# Candidate-B Line-Op-Audit: `ide-delete-line` / `ide-insert-line` (2026-07-09)

Stand: 2026-07-09 (Claude, Worktree `claude/ide-line-op-audit`, Basis
`origin/main` @ `ad67376`). Report-only Nachzug zu
`docs/ide-tab-budget-audit-2026-07-09.md` (Kandidat B) nach Candidate-A-Merge
(`d0355c4`, Ist: `disk_lib=180`, `load_used=500/512`, Raw-Headroom `12`,
Post-Align-Headroom `8`).

## Frage
Sind `ide-delete-line`/`ide-insert-line` sicher reclaimbar (+2 Slots) oder fuer
nahe Editor-Slices (`kill-line`, `kill-region`, Undo, Directory-Buffer) wertvoll?

## Befund

**1. Kein Produkt-Aufrufer.** `ide-delete-line`/`ide-insert-line`
(`lib/ide-buffer.lisp:168,179`) werden nirgends in `lib/`/`src/` gerufen — nur
in Tests (`make bytecode-p0-ide-lib-check` PASS, `functions=180`).

**2. Der Live-Editier-Pfad nutzt sie NICHT und kann sie nicht nutzen.** RETURN
(`ide-split-line`) und Backspace/Zeilen-Join (`ide-delete-backward-char`) rufen
die internen Primitiven `%ide-lines-insert` / `%ide-lines-delete` /
`%ide-lines-replace` **direkt** auf und aktualisieren Zeilen UND Cursor atomar
via `%ide-buffer-with-lines-point`. Die beiden Wrapper nutzen dagegen den
point-losen `%ide-buffer-with-lines` — sie lassen den Punkt stehen und sind
damit fuer echte Editier-Kommandos (die nach dem Loeschen/Einfuegen den Cursor
neu setzen und clampen muessen) ungeeignet.

**3. Die geplanten Slices bauen auf den Primitiven, nicht auf den Wrappern.**
Laut `docs/ide-extension-plan.md`:
- `kill-line`/`kill-region`/`yank` (Z. 63,67; P1): muessen Point + `*ide-kill-ring*`
  fuehren → wie `ide-delete-backward-char` direkt auf `%ide-lines-delete` +
  Point-Handling. `ide-delete-line` (fixer Index, kein Point) ist kein Fit.
- Undo/Redo (Z. 68; P1): **Ganz-Buffer-Snapshots** → gar keine Line-Ops.
- Directory-Buffer-Auswahl (Z. 62): Lesen/Oeffnen, kein Zeilen-Insert/Delete
  ueber diese API.
- `eval-region` ist bereits live und nutzt `ide-region-lines`
  (`ide-eval-request.lisp:13`), nicht die Line-Ops.

Das wiederverwendbare Substrat (`%ide-lines-*` + `%ide-buffer-with-lines-point`)
bleibt in jedem Fall erhalten; die zwei Wrapper liefern darueber hinaus keinen
Reuse-Hebel fuer die geplanten Features.

## Empfehlung: RECLAIM (2 Slots), niedriges Risiko

`disk_lib 180→178`, `load_used 500→498`, Raw-Headroom `12→14`
(Post-Align-Headroom `8→10`). Reines Loeschen, kein Merge → codebuf-/symfn-neutral.

Test-Kopplung (Lockstep-Edit noetig; NICHT im Disk-Lib-Gate `p0-ide-lib.json`):
`lib/tests/ide-buffer-eval-cases.json` (Cases `ide-insert-line-*`,
`ide-delete-line-middle`, plus die `modified-p`-Probe Z. 96) und die vier
resident Stdlib-Subsets `p0-stdlib-subset.json`,
`p0-stdlib-einsuite-subset.json`, `p0-stdlib-einsuite-fasl-subset.json`,
`p0-stdlib-werkbank-subset.json`.

## Gegenargument (ehrlich, aber nachrangig)
Beide sind je 25/26 B kleine, index-basierte „ganze-Zeile"-Bausteine. Falls
irgendwann eine programmatische/point-lose Ganz-Zeilen-API gewuenscht ist (z. B.
ein Directory-Buffer, der seine Zeilenliste neu aufbaut), waeren sie bequem.
Das ist aber spekulativ und trivial reversibel: beide sind 3-Zeilen-Wrapper ueber
`%ide-lines-insert`/`%ide-lines-delete` und jederzeit fuer je 1 Slot
wieder-addierbar. Bei Raw-Headroom 12 vor dem naechsten Feature ueberwiegt
„jetzt reclaimen, bei echtem Bedarf billig zurueckholen".

Wer stattdessen einen kleinen API-Puffer vor dem kill-line-Slice halten will,
kann die zwei Slots vertretbar behalten — die Entscheidung ist wegen der
trivialen Reversibilitaet risikoarm in beide Richtungen.
