# Candidate-B Line-Op-Audit: `ide-delete-line` / `ide-insert-line` (2026-07-09)

Stand: 2026-07-09. Claude-Audit aus Branch `claude/ide-line-op-audit`,
reviewed und umgesetzt durch Codex auf aktuellem `main` nach dem
Directory-RETURN-Slice.

## Frage

Sind `ide-delete-line`/`ide-insert-line` sicher reclaimbar oder fuer nahe
Editor-Slices (`kill-line`, `kill-region`, Undo, Directory-Buffer) wertvoll?

## Befund

1. **Kein Produkt-Aufrufer.** Beide Funktionen wurden nirgends in `lib/` oder
   `src/` gerufen. Die einzigen Referenzen lagen in Host-Oracle-Cases und
   Bytecode-Subset-Listen.
2. **Der Live-Editierpfad nutzt sie nicht.** RETURN (`ide-split-line`) und
   Backspace/Zeilen-Join (`ide-delete-backward-char`) rufen die internen
   Primitiven `%ide-lines-insert`, `%ide-lines-delete` und
   `%ide-lines-replace` direkt und aktualisieren Zeilen plus Cursor atomar via
   `%ide-buffer-with-lines-point`. Die Wrapper waren point-los
   (`%ide-buffer-with-lines`) und damit fuer echte Editor-Kommandos kein guter
   Fit.
3. **Geplante Slices bauen auf den Primitiven.** `kill-line`,
   `kill-region`/`yank` und kuenftige Region-Operationen muessen Point und
   Kill-Ring fuehren. Undo/Redo soll zunaechst ueber Buffer-Snapshots laufen.
   Directory-Buffer-Auswahl liest oder oeffnet Eintraege, braucht aber keine
   point-lose Insert/Delete-Line-API.

Das wiederverwendbare Substrat (`%ide-lines-*` plus
`%ide-buffer-with-lines-point`) bleibt erhalten; entfernt wurden nur zwei
duenne oeffentliche Wrapper.

## Entscheidung

Reclaim umgesetzt. Begruendung: niedriger Nutzwert, keine Produkt-Aufrufer,
trivial reversibel, und das Projekt braucht aktuell jeden Disk-Lib-Slot.

Effekt nach Umsetzung:

```text
bytecode-p0-ide-lib-check: PASS functions=180 cases=71 objects=251
  code_bytes=14210 dir_bytes=1757
workbench-disk-lib-budget: PASS resident=319 start=320 disk_lib=180
  load_used=500 post_align=504 cap=512 headroom=12 post_headroom=8
  codebuf=56 codebuf_required=48 codebuf_headroom=8
```

Damit holt Candidate B die zwei Slots des Directory-RETURN-Slices wieder
zurueck: `disk_lib 182->180`, `load_used 502->500`, Raw-Headroom `10->12`.
Der Post-Align-Headroom bleibt wegen Align8 weiterhin `8`.

## Risiko

Extern waere eine point-lose Ganz-Zeilen-API denkbar, sie ist aber aktuell nicht
Teil eines Nutzer-Workflows. Falls spaeter benoetigt, lassen sich beide Wrapper
als Drei-Zeilen-Funktionen ueber `%ide-lines-insert`/`%ide-lines-delete` wieder
hinzufuegen.
