# IDE Extension Plan

Stand: 2026-07-09. Dieses Dokument bewertet und priorisiert die naechsten
IDE-Erweiterungen fuer lisp65. Es baut auf `docs/editor-architecture.md`,
`docs/ide-performance-analysis.md` und dem aktuellen Dev-Core/On-Demand-IDE-Modell
auf.

## Ausgangslage

Die IDE ist bereits mehr als ein Mock:

- `(edit)` laedt die IDE on demand und springt per RUN/STOP zwischen REPL und Editor.
- Buffer leben in Lisp als `(name file-name lines point mark modified-p mode locals diagnostics)`.
- Es gibt mehrere Buffer ueber `*ide-buffers*`, eine Command-Loop, Dirty-/Delta-Render,
  Syntax-Highlighting, Auto-Indent bei Return und einfache Cursorbewegung.
- `ide-open`/`ide-save` existieren als Disk-Anbindung in `lib/ide-disk.lisp`, sind aber
  bewusst Werkbank-/Disk-Profil-Material und noch nicht sauberer Live-Standard.
- Ein erster Live-Datei-/Bufferworkflow ist gelandet: `C-x C-f` fragt im
  Minibuffer einen Dateinamen ab, `C-x C-s` speichert den aktuellen
  Buffer-Dateinamen, `C-x C-w` schreibt unter abgefragtem Namen, `C-x C-b`
  wechselt Buffer, `C-x C-n`/`C-x C-p` zyklisieren direkt, `C-x C-d` oeffnet
  `*directory*`, `C-x C-k` kompiliert und laedt den aktuellen Buffer ueber den
  `compile-load`-Pfad (`compile-buffer-to-lib` plus `load-lib`) in einen
  FASL-Slot. Bare-Control-Navigation ist
  als schmaler Alias-Slice gelandet: `C-f`/`C-b`, `C-n`/`C-p`, `C-a`/`C-e`,
  `C-j`; Prefix-Chords gewinnen weiterhin vor den Bare-Aliases.
- Die Statuszeile zeigt als Budget-schonende Alternative zu sichtbaren
  Gutter-Zeilennummern die aktuelle 1-basierte Zeile als `L<n>`.
- Terminologie-Pin: `docs/ide-api-terminology.md`. `compile` ohne `to-lib`
  meint kuenftig transient in die laufende Session; persistente L65M/FASL-
  Ausgabe traegt `to-lib`/`to-fasl`.
- `ide-eval-request.lisp` kann Region/Defun-Source extrahieren, fuehrt aber noch keine
  Live-Eval-/Compile-Aktion aus.

Die harte Grenze ist nicht mehr "geht das theoretisch?", sondern Budget und
Responsiveness:

- Dev-Core ist sehr eng: zuletzt `stack_gap=1476/1450`, nur 26 B Bank-0-Reserve.
- Neue Features sollen primaer als Bytecode-Libs wachsen, nicht als C-Kern.
- Neue C-Primitive brauchen eine explizite Budget-Begruendung.
- Interaktive Pfade muessen durch Host-Oracle, Bytecode-Suite und
  `ide-bytecode-dynamic-report` gehen.

## Bewertungsrahmen

Prioritaet:

- **P0:** noetig fuer eine alltaeglich nutzbare IDE.
- **P1:** hoher Nutzen, sobald P0 stabil ist.
- **P2:** sinnvoll, aber nicht kritisch.
- **P3:** spaeter, riskant oder grosser Umbau.

Kosten:

- **S:** reine Lisp-Funktion/Keymap, geringe Testflaeche.
- **M:** mehrere Buffer-/Render-/Disk-Pfade, neue Tests noetig.
- **L:** Runtime-/Compiler-/Metadatenbedarf oder Performance-Risiko.

## Feature-Bewertung

| Feature | Bewertung | Empfehlung |
| --- | --- | --- |
| Emacs-Keybindings (`C-n`, `C-p`, `C-f`, `C-b`) | P0 / M | Schmaler Alias-Slice gelandet: bare `C-n`/`C-p` bewegen runter/hoch, `C-f`/`C-b` rechts/links. `C-x C-b` bleibt Bufferwechsel, weil der Prefix vor Bare-Aliases gewinnt. Offen: Daten-Keymap statt Dispatch-Code. |
| Key chords (`C-x C-f`, `C-x C-s`) | P0 / M | Erster Budget-schonender Slice gelandet: `C-x C-f`, `C-x C-s`, `C-x C-w`, `C-x C-b`, `C-x C-d`, `C-x C-k`, plus direkte Buffer-Zyklen `C-x C-n`/`C-x C-p`. Plain-letter-Chords wie `C-x b` bleiben offen, weil sie aktuell den normalen Self-Insert-Hotpath verteuern wuerden. Offen: Prefix-State in IDE-State statt global und breiterer Abort-/Command-Dispatch. |
| Buffer durchschalten | P0 / S | Gelandet als `C-x C-b` mit Minibuffer-Default auf den naechsten offenen Buffer; `TAB` schaltet Bufferkandidaten durch, `C-p` ruft die letzte Eingabe derselben Aktion ab. Direkte Zykluscommands: `C-x C-n` vorwaerts, `C-x C-p` rueckwaerts. Offen: ggf. plain `C-x b`. |
| Find file / save buffer | P0 / M | `C-x C-f` fragt freie Dateinamen im Minibuffer ab, `C-x C-s` speichert direkt, `C-x C-w` fragt Zielnamen ab. Defaults sind sichtbar und per leerem RETURN nutzbar; `TAB` schaltet fuer Find/Write nur Source-Slots durch, `C-p` ruft die letzte Eingabe derselben Aktion ab. `C-x C-f`, `C-x C-w` und Directory-RETURN brechen bekannte System-/Compile-Slots (`ide`, `an`, `out`, `tmp`, `fasl*`) mit `"not source"` ab. |
| Dateien auf Disk anzeigen (`dir`) | P0 / M | Gelandet als REPL-Funktion `(dir)` fuer die rohe Directory-Liste und Editor-Command `C-x C-d`, der `*directory*` als gefilterte Source-Ansicht oeffnet. RETURN auf einer Directory-Zeile oeffnet den Eintrag. Refresh ist erneutes `C-x C-d`; Rename/Delete bleiben ohne sichere Disk-Primitives bewusst offen. |
| Delete char/word/line vor/zurueck | P0 / M | Rueckwaerts char, forward-delete (`C-d`), `kill-line` (`C-k`), forward `kill-word` (`C-w`) und backward-kill-word (`C-r`) sind gelandet. Offen: mehrzeilige Region-Loeschung. |
| Zeilen-/Dokumentanfang/-ende | P0 / S-M | `C-a`/`C-e` fuer Zeilenanfang/-ende, `C-x C-a`/`C-x C-e` fuer Bufferanfang/-ende und `C-v`/`C-z` fuer Page Down/Up sind gelandet. |
| Wortbewegung | P1 / M | Gelandet als `C-o` vorwaerts und `C-u` rueckwaerts. Scanner ist bewusst einfach: Whitespace und Lisp-Delimiter trennen Tokens. Offen: bessere Keymap/Meta-Ersatz und ggf. Symbolsyntax-Feinschliff. |
| SEXP-Navigation | P1 / M-L | Auf `ide-defun-region`/Syntax-Scanner aufbauen. Erst top-level/balanced paren vor/zurueck, dann robustere Listennavigation. |
| Copy/Paste / einfacher Kill Ring | P1 / M | Global `*ide-kill-ring*` existiert fuer `C-k`/`C-w`/`C-r`; `C-y` yankt den einfachen Ring. `C-SPC`, `C-x C-x`, `C-x C-r` und `C-x C-y` decken einzeilige Region ab. Offen: mehrzeilige/mehrere Kill-Ring-Eintraege und visuelle Region. |
| Undo/Redo | P1 / L | Nicht als erstes. Einfachster Start: kleine Snapshot-Liste ganzer Buffer nach editierenden Commands, z. B. 8 Schritte. Das ist speicherteuer, aber korrekt. Spaeter inverse Deltas. |
| Set Mark visuell | P1 / M-L | Funktional gelandet: `C-SPC` setzt Mark, `C-x C-x` tauscht Punkt/Mark. Visuelle Region bleibt offen. |
| Zeilennummern | P2 / M | MVP-Kompromiss gelandet: Statuszeile zeigt `L<n>` ohne Gutter. Sichtbare Gutter-Zeilennummern bleiben P2/Toggle, weil sie Spalten und Renderarbeit kosten und Dirty-Render die linke Gutter stabil behandeln muesste. |
| Vertikales Scrollen | P0 / M | Schmaler MVP-Slice gelandet: `C-v`/`C-z` bewegen seitenweise ueber Punktbewegung; der Render haelt den Punkt sichtbar. Separates View-only-Scrolling bleibt offen. |
| Auto-Paren-/Quote-Matching | P1 / M | Erst Auto-Pair beim Insert und Matching-Highlight der Gegenklammer. Muss Escape-/String-/Kommentarzustand respektieren. |
| Paredit-Light, Barf/Slurp | P2-P3 / L | Nach SEXP-Navigation. Diese Commands veraendern Struktur und brauchen solide Parser-/Region-Funktionen plus Undo. |
| Eval/Compile Form/Region/File | P0-P1 / L | Erster persistenter Buffer-Slice gelandet: `C-x C-k` schreibt den aktuellen Buffer per `compile-buffer-to-lib` in einen abgefragten FASL-Slot und laedt ihn, Default `fasl0`. Offen: transientes `compile-buffer`/`eval-defun`, Region, Datei-Workflow und bessere Fehlerspruenge. |
| Docstrings / Parameteranzeige | P2 / L | Braucht Funktionsmetadaten: Arity, Rest-Flag, Docstring, ggf. Source-Ort. Erst fuer Stdlib/Bytecode-Manifest, danach UI. |

## Ergaenzende Features

Diese Punkte sollten in die Planung aufgenommen werden, weil sie den Nutzen stark
erhoehen oder als Infrastruktur fuer die oben genannten Features dienen:

- **Minibuffer/Prompt:** fuer Dateinamen, Bufferwechsel, `M-x`, Suchbegriffe und Fehlermeldungen.
- **`M-x` Command Dispatcher:** reduziert Keybinding-Druck; neue Commands sind sofort erreichbar.
- **Search / incremental search:** `C-s`-Search plus `C-s C-s` fuer naechster Treffer ist gelandet; offen ist echte inkrementelle Suche.
- **Goto line:** erster `C-l`-Goto-Line-Slice ist gelandet; offen sind Fehlersprung-Integration und breitere Zahlen-/Eingabevalidierung.
- **Message area:** Kommandos wie save/eval sollten Status melden, ohne den Buffer zu veraendern.
- **Mode-line-Ausbau:** Buffername, modified flag, Symbolbudget und Zeile sind
  gelandet. Offen: Spalte, ggf. aktiver Prefix.
- **Command registry:** `command-name`, Help-String, Keybinding, Kategorie; Grundlage fuer `M-x`
  und Help.
- **Fehlernavigation:** letzter Eval-/Compile-Fehler springt zur approximierten Stelle.
- **Feature-Module:** IDE weiter modular halten: `ide-core`, `ide-edit`, `ide-disk`,
  `ide-lisp`, `ide-help`, `ide-paredit`.

## Reihenfolge

### Slice 0: Keymap- und State-Fundament

Ziel: alle spaeteren Commands ohne neue Dispatch-Hacks verdrahten.

Umfang:

- Keymap-Datenmodell fuer einfache Keys und Prefix-Sequenzen.
- Prefix-State im IDE-State, z. B. Feld oder Locals-Unterstruktur.
- `C-g`/RUN-STOP als Abort fuer Prefix/Minibuffer, nicht als Datenzeichen.
- `M-x` noch optional, aber Command-Symbole sollten schon einheitlich sein.

Gates:

- Host-Tests fuer `key-event -> command`.
- Bytecode-Suite fuer Prefix-Sequenzen.
- Dynamic-Report darf self-insert/render nicht verschlechtern.

### Slice 1: Grundnavigation und Scrollen

Ziel: Emacs-nahe Basisnavigation im aktuellen Buffer.

Status 2026-07-09: MVP-Slice umgesetzt. Bare `C-f`/`C-b`, `C-n`/`C-p`,
`C-a`/`C-e`, `C-j`, `C-v`/`C-z` sowie `C-x C-a`/`C-x C-e` sind verdrahtet.
`C-v`/`C-z` bewegen den Punkt seitenweise; separates View-only-Scrolling bleibt
offen.

Umfang:

- `C-f`/`C-b` forward/backward char.
- `C-n`/`C-p` next/previous line.
- `C-a`/`C-e` line begin/end.
- `C-x C-a`/`C-x C-e` als Ersatzkeys fuer buffer begin/end.
- `C-v`/`C-z` page down/up.
- Vertikales Scrollen im MVP ueber Punktbewegung; separates View-Scroll spaeter.

Gates:

- Host-Oracle fuer Punkt/row-offset.
- Render-Cache invalidiert bei View-Wechsel sauber.
- Warm-render Budget bleibt im Gate.

### Slice 2: Buffer- und Datei-Workflow

Ziel: Datei bearbeiten, speichern, Buffer wechseln.

Status 2026-07-09: erster schmaler Datei-/Buffer-Slice umgesetzt. `C-x C-f`
nutzt einen einzeiligen Minibuffer fuer freie Dateinamen, `C-x C-s` speichert
direkt, `C-x C-w` schreibt unter abgefragtem Namen, `C-x C-b` wechselt Buffer,
`C-x C-n`/`C-x C-p` zyklisieren direkt durch offene Buffer, `C-x C-d` oeffnet
einen `*directory*`-Buffer, `C-x C-k` schreibt und laedt den aktuellen Buffer in
einen abgefragten FASL-Slot. `C-d` loescht das Zeichen unter dem Cursor bzw.
joint am Zeilenende mit der Folgezeile. `C-k` killt den Zeilenrest in einen
einfachen `*ide-kill-ring*` bzw. joint am Zeilenende die Folgezeile. `C-y`
yankt, `C-o`/`C-u` bewegen wortweise vor/zurueck und `C-w` killt das naechste
Wort. Bare `C-f`/`C-b`/`C-n`/`C-p` sind
Navigationsaliase, `C-a`/`C-e` springen an Zeilenanfang/-ende, `C-j` ist ein
Newline-Alias; `C-x`-Prefix-Chords gewinnen vor diesen Aliases. `C-g` und
`ESC` brechen den Minibuffer
ab, ohne die IDE zu verlassen. Leeres RETURN im Minibuffer nutzt den angezeigten
`[Default]` (`file-name`, Buffer-Name oder naechster Buffer). `TAB` schaltet
passende Datei-, Buffer- und FASL-Zielkandidaten durch; vorhandener Input dient als
case-insensitiver Prefix-Filter. `C-p`/CRSR-hoch ruft den letzten nichtleeren
Wert derselben Minibuffer-Aktion ab, `C-n`/CRSR-runter und `C-u` leeren die
Eingabe. `C-x C-d` zeigt nur editierbare Source-Slots; `C-x C-k` bietet per
`TAB` nur `fasl*`-Zielslots an, und die IDE-Compile-Wrapper rejecten
Nicht-FASL-Ziele mit `"not fasl"`. `C-s` sucht im aktuellen Buffer,
`C-s C-s` springt zum naechsten Treffer desselben Suchbegriffs, `C-l` springt
zu einer 1-basierten Zeilennummer. Die Statuszeile zeigt `L<n>`; Spalte und
Gutter bleiben bewusst offen.

Umfang:

- Weitere `dired`-leichte Kommandos aus `*directory*` (loeschen, rename,
  refresh) bleiben bewusst spaeter.
- Fehleranzeige nutzt bereits `(ide-error)`; naechster Schritt ist direkter
  Sprung von Fehlermeldungen zu sinnvollen Zielaktionen.

Abhaengigkeiten:

- `ide-disk` aus Werkbank in eine saubere On-Demand-Disk-Lib heben.
- Disk-Fehler muessen als Message/Status sichtbar werden.

Gates:

- Host-Tests fuer Buffer-Alist und Dateinamenlogik.
- Disk-Lib-Artefaktcheck.
- Kein neues C im Dev-Core.

### Slice 3: Delete/Kill/Yank/Mark

Ziel: produktives Editieren ohne Reset oder manuelle Rekonstruktion.

Status 2026-07-09: schmaler MVP-Slice umgesetzt. `C-d`, `C-k`, `C-y`,
`C-o`/`C-u`, `C-w`, `C-r`, `C-SPC`, `C-x C-x`, `C-x C-r` und `C-x C-y`
sind Host-/Bytecode-geprueft. Region-Operationen sind bewusst nur einzeilig;
mehrzeilige Region/Yank und visuelle Markierung bleiben offen.

Umfang:

- `delete-char`, `backward-delete-char`.
- `backward-kill-word` als `C-r`; forward `kill-word` ist `C-w`,
  `kill-line` ist `C-k`.
- `set-mark-command`, `exchange-point-and-mark`.
- `kill-region`, `copy-region-as-kill` fuer einzeilige Regionen;
  mehrzeiliges/mehrfaches `yank` bleibt offen.
- Einfacher Kill-Ring: ein globaler Slot zuerst, spaeter Liste.

Abhaengigkeiten:

- Region-Text und Replace-Region ausbauen.
- Mark-Anzeige optional erst nach funktionalem Mark.

Gates:

- Host-Tests fuer Texttransformationen.
- Bytecode-Faelle fuer EOL, BOF/EOF, leere Region, Multi-Line-Kill.
- Dynamic-Budgets fuer self-insert duerfen unveraendert bleiben.

### Slice 4: Eval/Compile aus der IDE

Ziel: die IDE wird zur Lisp-Workspace-Oberflaeche.

Umfang:

- `C-M-x` oder `C-c C-c`: eval/compile defun.
- `C-c C-r`: eval/compile region.
- `C-c C-b`: eval/compile buffer.
- `C-c C-k`: compile-file/save/load-lib Workflow fuer Datei.
- Ergebnis und Fehler in Message Area; Fehlerposition approximativ markieren.

Abhaengigkeiten:

- Entscheiden pro Profil: `eval-string`/`lcc-run` direkt, oder temp-file + `compile-file`
  + `load-lib`.
- Reader/Compiler sollen zumindest Defun-/Region-Kontext melden koennen.

Gates:

- Host-Oracle fuer `ide-eval-request`.
- Device-Safe Smoke ohne Live-xemu-Dauerprozess.
- Fehlerfall: REPL/IDE bleibt bedienbar.

### Slice 5: Lisp-spezifisches Editieren

Ziel: Lisp-Code fuehlt sich wie Lisp-Code an, nicht wie Plain Text.

Umfang:

- Auto-Pair fuer `(`, `"`, optional `[` falls spaeter relevant.
- Matching-Paren-Highlight.
- SEXP forward/backward/up/down.
- Transpose/raise/splice als spaetere Paredit-Light-Commands.
- Barf/Slurp erst nach stabiler SEXP-Navigation und Undo.

Abhaengigkeiten:

- Syntax-Scanner muss Strings/Kommentare respektieren.
- Region/Undo sollte vor strukturveraendernden Commands stehen.

Gates:

- Tests fuer Strings, Kommentare, verschachtelte Listen, unbalancierte Formen.
- Render-Hotpath darf Matching-Highlight nur fuer Cursorumgebung rechnen.

### Slice 6: Help, Completion, Docstrings

Ziel: die IDE erklaert die laufende Lisp-Umgebung.

Umfang:

- `apropos`, `describe`, `symbol-completion` in der UI.
- Parameteranzeige fuer bekannte Funktionen.
- Docstring-Konvention fuer Lisp-Defuns und Stdlib-Manifest.
- Command-Help: Keybinding + Kurzbeschreibung.

Abhaengigkeiten:

- Funktionsmetadaten im Bytecode-/Stdlib-Manifest: Name, Arity, Rest, Macro/Function,
  optional Docstring.
- Runtime-Zugriff auf diese Metadaten oder ladbares Help-Index-File.

Gates:

- Host-Metadaten-Oracle.
- Help-Lib als on-demand Modul, nicht resident im Core.

### Slice 7: Undo/Redo und Visual Polish

Ziel: Fehlbedienung wird billig korrigierbar; UI wirkt weniger roh.

Umfang:

- Undo: zuerst 8 Buffer-Snapshots oder command-level Deltas.
- Redo nach stabiler Undo-Implementierung.
- Visuelle Region.
- Zeilennummern als Toggle.
- Search/Isearch, goto-line, optional Directory-Buffer.

Risiko:

- Undo-Snapshots koennen Heap stark belasten. Snapshot-Undo nur mit kleinen Caps und
  klarer OOM-Meldung; langfristig Deltas.

## Modulare Lib-Aufteilung

Empfohlene Aufteilung, damit Dev-Core schlank bleibt:

- `ide-core`: State, Bufferliste, Command-Loop, Render, einfache Bewegung.
- `ide-edit`: Delete/Kill/Yank/Mark, Word-Motion, Region-Replace.
- `ide-disk`: `find-file`, `save-buffer`, `dir`, Directory-Buffer.
- `ide-lisp`: eval/compile defun/region/buffer/file, SEXP-Navigation, Auto-Pair.
- `ide-help`: completion, apropos, describe, docstrings, command help.
- `ide-paredit`: Barf/Slurp/Splice/Raise, erst spaeter.

`ide-core` bleibt das einzige Modul, das im normalen `(edit)`-Pfad zwingend geladen wird.
Alles andere kann bei erstem Command per `(load-lib ...)` nachgeladen werden.

## Nicht sofort bauen

- Vollstaendiges Emacs-Keyset.
- Mehrfenster-/Frame-System.
- Vollstaendiges Paredit.
- Redo vor Undo-Stabilisierung.
- Docstring-/Arity-UI ohne Metadatenvertrag.
- C-Kernel-Editorlogik fuer Textoperationen.

## Naechster sinnvoller Arbeitsschritt

Nach den P0-Editor-Slices ist der naechste sinnvolle Schnitt nicht noch mehr
Hotpath-Dispatch, sondern gezielte Tiefe:

1. Mehrzeilige Region/Yank sauber implementieren und budgeten.
2. Danach `M-x`/Command-Registry als einheitliche Oberflaeche fuer seltene
   Commands statt weiterer direkter Key-Vergleiche.
3. Danach transiente Eval-/Compile-Commands fuer Defun/Region/Buffer mit
   sichtbarer Fehlerposition.
4. Sichtbare Region, Undo und Lisp-spezifische SEXP-Navigation bleiben die
   naechsten UX-Ausbaukandidaten, aber erst nach stabiler Budgetmessung.
