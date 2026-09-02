# IDE Editing-Slice Budget/Reuse-Audit (2026-07-09)

Stand: 2026-07-09 (Claude, Worktree `claude/ide-editing-budget-audit`, Basis
`origin/main` @ `665cede`). Report-only. Von Codex nach `main` integriert nach
dem HW-Smoke-Hardening `2070136`; die aktuellen HW-Smoke-Skripte/Dokumente
bleiben unveraendert.

Vorlaeufer:
`docs/ide-tab-budget-audit-2026-07-09.md`,
`docs/ide-line-op-audit-2026-07-09.md`,
`docs/ide-extension-plan.md`.

Ist-Pin: `disk_lib=180`, `load_used=500/512`, Raw-Headroom `12`,
Post-Align-Headroom `8` (`make bytecode-p0-ide-lib-check` PASS,
`functions=180`).

Addendum Codex 2026-07-09: `next-buffer`/`previous-buffer`, `delete-char`,
Minibuffer-History, Search/Goto, Search-Repeat, Statusline-`L<n>`,
`kill-line` und `yank` sind inzwischen umgesetzt. Aktueller Workbench-Pin nach
`ide-yank`: `disk_lib=181`, `load_used=501/512`, Raw-Headroom `11`,
Post-Align-Headroom `8`, `codebuf_required=54/56`;
`workbench-symfn-dynamic-report` bleibt bei `127763` Instruktionen /
`8910` `symfn`-Aufloesungen. Die aktuelle ladbare IDE-Disk-Lib deferred
`ide-region-lines` und `ide-defun-region` als geplante Eval-Region/
Eval-Defun-Helfer; Source, Host-Oracles und Stdlib-Profile behalten sie.

Addendum Codex 2026-07-09b: Word-Edit ist gelandet (`C-o` forward-word,
`C-u` backward-word, `C-w` kill-word; `C-x C-w` bleibt Write-File). Der
aktuelle Host-/Dry-Run-Pin nach zusaetzlichem Disk-Lib-Reclaim ist
`disk_lib=178`, `load_used=498/512`, Raw-Headroom `14`,
Post-Align-Headroom `8`, `codebuf_required=54/56`. Neben
Eval-Region/Eval-Defun deferred `p0-ide-lib.json` auch ungenutzte
Buffer-Accessors; `%ide-disk-clean-buffer` greift fuer diesen Produktpfad
direkt auf das Buffer-Tuple zu.

Addendum Codex 2026-07-09c: Dokumentnavigation und eine schmale Mark/Region-
Familie sind gelandet. Neu: `C-r` backward-kill-word, `C-v`/`C-z` Page
Down/Up, `C-x C-a`/`C-x C-e` Bufferanfang/-ende, `C-SPC` set-mark,
`C-x C-x` exchange point/mark, `C-x C-r` kill-region und `C-x C-y`
copy-region-as-kill. Region/Yank ist bewusst einzeilig; die fruehere
mehrzeilige Variante wurde wegen Objekt-/Heapdruck nicht gepinnt. Directory-
Rename/Delete/Refresh-Hotkeys wurden nicht aufgenommen, weil sichere
Disk-Primitives fehlen und mode-spezifische Printable-Checks den `ide-step`-
Hotpath messbar verteuerten. Aktueller Pin: `disk_lib=201`,
`load_used=521/536`, `post_align=528/536`, Raw-Headroom `15`,
Post-Align-Headroom `8`, `codebuf_required=54/56`;
`workbench-symfn-dynamic-report` bleibt bei `127763` Instruktionen /
`8910` `symfn`-Aufloesungen.

## Kostenmodell aus dem Dispatch

Der Command-Dispatch ist zweistufig und statisch:

- `ide-event-command` (143 B): Key-Code -> Command. Hot Path je Taste. Jede
  neue bare Taste fuegt hier einen Vergleich vor `self-insert` hinzu und
  belastet damit den Self-Insert-Dynamic-Report.
- `%ide-prefix-command` (119 B): `C-x`-Chord-Code -> Command-ID (1001-1008).
- `ide-step` (161 B) -> `ide-apply-command` (214 B, Editing) bzw.
  `%ide-command-action` (122 B, `C-x`-Kommandos).

Kosten-Faustregel: 1 neue benannte Funktion = 1 Directory-Slot. Inline in ein
bestehendes Objekt = 0 Slots, aber Code-Bytes wachsen. Das ist kritisch, weil
mehrere Hot-Objekte nah am 255-B-Objekt-Cap liegen: `%ide-mini-step` 250 B,
`ide-delete-backward-char` 234 B, `ide-render` 218 B, `ide-apply-command` 214 B,
`%ide-render-fast-same-row` 210 B, `ide-insert-char` 193 B. Neue Editing-Logik
gehoert daher in eigene Helfer, nicht inline in diese Objekte.

## Vorhandene Primitiven

| Zweck | Primitiven |
| --- | --- |
| Zeilen splicen | `%ide-lines-insert/-delete/-replace/-split-at`, `%ide-drop-lines`, `%ide-take-lines` |
| Buffer + Cursor atomar | `%ide-buffer-with-lines-point`, `ide-set-point` |
| String im Punkt | `ide-string-prefix/-suffix/-insert-code/-delete-before/-append`, `ide-insert-char` |
| Region lesen | `ide-region-lines`, `ide-region-lines-from` (deferred fuer `eval-region`) |
| Mark | `ide-buffer-mark` (nur Getter; Setter fehlt) |
| Buffer-Liste | `%ide-buffers-alist`, `%ide-buffers-names`, `%ide-buffers-remove`, `%ide-store-buffer`, `%ide-current-buffer` |
| Minibuffer | `%ide-mini-start/-step/-message/-tab-value/-input-append/-input-backspace` |

## Empfohlene Reihenfolge

### 1. `next-buffer` / `previous-buffer`

Billigste Funktion mit hohem UX-Wert; zuerst umsetzen.

Alle Primitiven sind vorhanden: `%ide-buffers-alist`, `%ide-store-buffer` und
`ide-make-buffer`, analog zu `%ide-switch-key`, aber ohne Minibuffer. Der Helfer
waehlt den Nachbarn in der Alist und wrappt am Ende.

Erwartete Kosten: 1 gemeinsamer Helfer (`%ide-cycle-buffer` mit Richtung),
2 Chord-IDs (z. B. 1009/1010) in `%ide-prefix-command` und 2 Zweige in
`%ide-command-action` (122 B, viel Luft). Erwartung: ca. 1-2 Slots. Kein
Hot-Path- und kein Cap-Risiko.

### 2. `delete-char` forward

Billig und hoher Alltagsnutzen.

Spiegel von `ide-delete-backward-char`: in der Zeile per
`ide-string-delete-before` auf Spalte+1 oder per Suffix-Variante; am Zeilenende
Join mit Folgezeile via `%ide-lines-replace` und `%ide-lines-delete`. Nutzt die
gleichen Primitiven wie Rueckwaerts-Delete.

Binding: bare `C-d` (Code 4) ist frei. Code 4 wirkt bisher nur als `C-x`-Chord,
nicht als bare Taste. Umsetzung: ein Zweig in `ide-event-command` (Hot Path),
`ide-step` und eigener Helfer `ide-delete-forward-char`.

Erwartete Kosten: 1 Slot. Kleiner Hot-Path-Aufschlag durch einen
`=`-Vergleich/Taste; daher Symfn-/Self-Insert-Budget im Gate gegenpruefen.

### 3. Kill-Ring-Substrat plus `kill-line`

Mittlere Kosten, aber schaltet die Kill-Familie frei.

Zuerst globaler `*ide-kill-ring*` nach der bestehenden Slot-Konvention von
`%ide-prefix`/`%ide-hint`, dann `kill-line` darauf. `kill-line` kuerzt die
aktuelle Zeile bis Punkt via `ide-string-prefix` und speichert den entfernten
Text; Ganzzeilenfaelle laufen ueber `%ide-lines-delete` und Punkt-Clamp mit
`%ide-buffer-with-lines-point`.

Binding: bare `C-k` (Code 11) ist frei. `C-x C-k` bleibt Compile (1008); keine
Kollision.

Erwartete Kosten: ca. 2 Slots fuer Kill-Store plus `kill-line`. Kein Cap-Risiko
bei eigenem Helfer.

### 4. `yank` (gelandet)

Mittlere Kosten und notwendiges Gegenstueck zum Kill-Ring.

Insert des gespeicherten Strings am Punkt: einzeilig ueber
`ide-string-prefix/-suffix/-append`, mehrzeilig ueber `%ide-lines-*`.
Gelandeter MVP-Slice: einzeiliger String plus einzelner Newline-String. Netto
slot-neutral gegen den vorherigen Disk-Lib-Pin, weil die aktuelle IDE-Disk-Lib
`ide-region-lines` und `ide-defun-region` bis zum Eval-Region-Slice nicht
mitlaedt.

### 5. `set-mark` / `kill-region` / `copy-region-as-kill`

Mittlere bis hohe Kosten.

Braucht zuerst einen Mark-Setter. Das Buffer-Tupel hat das `mark`-Feld bereits;
der Setter ist ein kleiner Tupel-Rebuild analog `%ide-buffer-with-lines-point`.
Region-Lesen via `ide-region-lines` ist vorhanden. `kill-region` kombiniert
Span, `%ide-lines-delete`/Splice, Kill-Ring und Punkt. Region-Highlight im
Render bleibt bewusst spaeter, weil es teuer ist.

Erwartete Kosten: Mark-Setter, `set-mark-command`, `exchange-point-and-mark`,
`kill-region` und `copy-region`, insgesamt ca. 4-5 Slots. Erst nach dem
Kill-Ring sinnvoll.

### 6. Minibuffer-History

Wertvoll, aber durch den Objekt-Cap gebremst.

Global `*ide-mini-history*` plus Hoch/Runter im Minibuffer. `%ide-mini-step`
liegt bei 250/255 B; Up/Down-Zweige direkt dort wuerden den Objekt-Cap sprengen.
Vorher muss der Key-Handler aus `%ide-mini-step` in einen Helfer ausgelagert
werden. Daher trotz Slice-2-Zugehoerigkeit erst nach `next-buffer` /
`previous-buffer` terminieren oder direkt mit dem `%ide-mini-step`-Split
buendeln.

## Weitere sichere Reclaim-Kandidaten

- `%ide-buffer-with-lines` (71 B, 1 Slot): durch den Candidate-B-Reclaim
  verwaist. 0 Produkt-Aufrufer; Live-Editing nutzt
  `%ide-buffer-with-lines-point`. Nur in residenten Stdlib-Subsets referenziert,
  nicht im Disk-Lib-Gate. Erwarteter Reclaim: `disk_lib 180->179`, Headroom
  `12->13`. Vorbehalt: Es ist der natuerliche point-lose Setter. Behalten, falls
  ein Dired-Refresh/Whole-Buffer-Replace-Slice kurzfristig geplant ist;
  ansonsten entfernen, weil der Wrapper trivial reversibel ist.
- `ide-visible-frame-lines` (96 B, 1 Slot): nur test-referenziert
  (`ide-ui-eval-cases.json:62`); Live-Render nutzt
  `ide-visible-frame-lines-from`. Reclaimed im Navigationsalias-Slice.
- `%ide-repeat-self-insert` (1 Slot): war nur Test-/Perf-Helfer; der
  Dynamic-Report schleift jetzt hostseitig zehnmal ueber `ide-step`.
  Reclaimed im Navigationsalias-Slice.
- `ide-render-cursor` (1 Slot): Wrapper um `ide-render-cursor-from`; Live-Render
  nutzt die `*-from`-Variante direkt. Reclaimed im Navigationsalias-Slice.

Die hier genannten Reclaims sind Feinschliff, nicht der strukturelle Hebel; ein
Teil ist inzwischen fuer `delete-char` und die Navigationsaliase verbraucht. Der
groessere Hebel bleibt das Auslagern weiterer Module auf On-Demand-Disk-Libs,
zuerst `ide-disk` gemaess Extension-Plan Slice 2.

Nachzug 2026-07-09: Der deaktivierte Syntax-Overpaint-Cluster
(`%ide-hl-*`) und das tote Render-Line-Paar
(`ide-render-string-at`/`%ide-render-lines-at`) sind im Workbench-Profil
reclaimed. Nach dem anschliessenden File-Target-Guard- und Search-Repeat-Slice
ist der aktuelle Pin nach Gate: `disk_lib=180`, `load_used=500/512`,
`post_align=504/512`, Raw-Headroom `12`, Post-Align-Headroom `8`.

Nachzug `ide-status-line-line-number`: Sichtbare Gutter-Zeilennummern bleiben
zu teuer fuer den MVP-Pin; stattdessen zeigt die Statuszeile die aktuelle
1-basierte Zeile als `L<n>`. Der Versuch, zusaetzlich die Spalte (`L/C`) zu
zeigen, drueckte die lange IDE-Host-Suite ueber das kumulative
Host-Heap-Limit. Line-only kostet keinen weiteren Directory-Slot
(`disk_lib=180`, `load_used=500/512` bleibt). Ein anschliessender
Accessor-Reclaim im Statusline-/Cache-Pfad senkt den dynamischen
Workbench-Trace auf `127861` Instruktionen / `8910` `symfn`-Aufloesungen.

## No-go-Kandidaten

Quell-/API-seitig nicht loeschen:

- `ide-defun-region` (live und fuer geplantes `eval-defun`)
- `ide-region-lines`, `ide-region-lines-from` (deferred fuer `eval-region`)
- `ide-buffer-mark`, `ide-buffer-mode`, `ide-buffer-file-name`,
  `ide-buffer-diagnostics`
- `compile-file`, `compile-buffer-to-file`

Die Manifest-Heuristik fuer "zero inbound" verfehlt Rekursions- und einige
Direktaufrufe. Fuer Reclaims ist Grep gegen `lib/` und `src/` massgeblich.
Profil-Nuance nach `ide-yank`: `p0-ide-lib.json` darf `ide-region-lines` und
`ide-defun-region` temporaer per `remove_functions` aus der ladbaren IDE-Lib
deferieren, weil `lib/ide-eval-request.lisp` dort noch nicht gebuendelt ist.

## Gate-Erweiterungen

Fuer `next-buffer` / `previous-buffer` plus `delete-char`:

- Host-Tests fuer `key-event -> command` der neuen Bindings.
- Host-Tests fuer Buffer-Zyklus mit korrektem Nachbarn und Wraparound.
- Host-Tests fuer `delete-char` mittig, am Zeilenende mit Join und am Buffer-Ende
  als No-op.
- `make bytecode-p0-ide-lib-check`.
- `make workbench-disk-lib-budget-check`.
- `make workbench-symfn-dynamic-report`: Pflicht, weil `delete-char` einen
  Hot-Path-Vergleich in `ide-event-command` einfuegt. `ide-step-self-insert` und
  Render-Budgets duerfen nicht steigen. Bei Bedarf neues Szenario
  `ide-step-delete-forward` ergaenzen.
- Kein neues C im Dev-Core.

Fuer die Kill-/Mark-Familie zusaetzlich: Host-Oracles fuer Kill-Ring-Inhalt und
Punkt nach `kill-line`, `kill-region` und `yank`. Fuer Minibuffer-History ein
Bytecode-Cap-Check nach dem `%ide-mini-step`-Split.

## Kurzfazit

Urspruengliche Reihenfolge: `next-buffer` / `previous-buffer` -> `delete-char`
-> Kill-Ring plus `kill-line` -> `yank` -> `set-mark`/`kill-region` ->
Minibuffer-History nach `%ide-mini-step`-Split. Stand nach Codex-Addenda:
Kill-Word, Backward-Kill-Word, einfache Mark/Region, `yank` und
Minibuffer-History sind umgesetzt; offen bleiben mehrzeilige Region/Yank,
visuelle Markierung und ein mehrstufiger Kill-Ring.

Alle Primitiven fuer die ersten beiden Slices sind vorhanden. Erwartete
Slot-Kosten der Top 2: ca. 2-3, gedeckt durch Headroom 12 und optionalen
`%ide-buffer-with-lines`-Reclaim (+1). Groesstes wiederkehrendes Risiko ist der
255-B-Objekt-Cap, insbesondere `%ide-mini-step` mit 250 B, nicht die
Directory-Slot-Zahl.
