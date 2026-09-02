# IDE Editing-Slice Budget/Reuse-Audit (2026-07-09)

Stand: 2026-07-09 (Claude, Worktree `claude/ide-editing-budget-audit`, Basis
`origin/main` @ `665cede`). Report-only. Vorlaeufer:
`docs/ide-tab-budget-audit-2026-07-09.md`, `docs/ide-line-op-audit-2026-07-09.md`,
`docs/ide-extension-plan.md`.

Ist-Pin: `disk_lib=180`, `load_used=500/512`, Raw-Headroom `12`,
Post-Align-Headroom `8` (`make bytecode-p0-ide-lib-check` PASS, `functions=180`).

## Kostenmodell (aus dem Dispatch)

Der Command-Dispatch ist zweistufig und statisch:
- `ide-event-command` (143 B): Key-Code → Command. **Hot Path je Taste.** Jede
  neue *bare*-Taste fuegt hier einen Vergleich vor `self-insert` hinzu →
  belastet den Self-Insert-Dynamic-Report.
- `%ide-prefix-command` (119 B): `C-x`-Chord-Code → Command-ID (1001–1008).
- `ide-step` (161 B) → `ide-apply-command` (214 B, Editing) bzw.
  `%ide-command-action` (122 B, `C-x`-Kommandos).

Kosten-Faustregel: **1 neue benannte Funktion = 1 Directory-Slot.** Inline in ein
bestehendes Objekt = 0 Slots, aber Code-Bytes wachsen — kritisch, weil mehrere
Hot-Objekte nah am 255-B-Objekt-Cap liegen: `%ide-mini-step` **250 B**,
`ide-delete-backward-char` 234, `ide-render` 218, `ide-apply-command` 214,
`%ide-render-fast-same-row` 210, `ide-insert-char` 193. Neue Editing-Logik gehoert
daher in eigene Helfer, nicht inline in diese Objekte.

## Vorhandene Primitiven (wiederverwendbar)

| Zweck | Primitiven (vorhanden) |
| --- | --- |
| Zeilen splicen | `%ide-lines-insert/-delete/-replace/-split-at`, `%ide-drop-lines`, `%ide-take-lines` |
| Buffer + Cursor atomar | `%ide-buffer-with-lines-point`, `ide-set-point` |
| String im Punkt | `ide-string-prefix/-suffix/-insert-code/-delete-before/-append`, `ide-insert-char` |
| Region lesen | `ide-region-lines`, `ide-region-lines-from` (live: `eval-region`) |
| Mark | `ide-buffer-mark` (nur GETTER — Setter fehlt) |
| Buffer-Liste | `%ide-buffers-alist`, `%ide-buffers-names`, `%ide-buffers-remove`, `%ide-store-buffer`, `%ide-current-buffer` |
| Minibuffer | `%ide-mini-start/-step/-message/-tab-value/-input-append/-input-backspace` |

## Empfohlene Reihenfolge (Nutzwert ÷ Kosten)

### 1. `next-buffer` / `previous-buffer` — BILLIGSTE, sofort. Empfohlen zuerst.
Vervollstaendigt Slice 2. Alle Primitiven da: `%ide-buffers-alist` +
`%ide-store-buffer` + `ide-make-buffer`, wie `%ide-switch-key`, nur ohne
Minibuffer — Nachbar in der Alist waehlen (mit Wraparound).
- Kosten: 1 gemeinsamer Helfer (`%ide-cycle-buffer` mit Richtung) + 2 Chord-IDs
  (z. B. 1009/1010) in `%ide-prefix-command` + 2 Zweige in `%ide-command-action`
  (122 B, viel Luft). ~1–2 Slots.
- Kein Hot-Path-, kein Cap-Risiko. Kein neues C.

### 2. `delete-char` (forward) — billig, hoher Alltagsnutzen.
Spiegel von `ide-delete-backward-char`: in Zeile `ide-string-delete-before` auf
Spalte+1 (bzw. Suffix-Variante); am Zeilenende Join mit Folgezeile via
`%ide-lines-replace`+`%ide-lines-delete`. Gleiche Primitiven wie Rueckwaerts-Delete.
- Binding: **bare `C-d` (Code 4) ist frei** (Code 4 wirkt bisher nur als
  `C-x`-Chord, nicht als bare-Taste). Ein Zweig in `ide-event-command` (Hot Path)
  + `ide-step` + eigener Helfer `ide-delete-forward-char`.
- Kosten: 1 Slot. Kleiner Hot-Path-Aufschlag (ein `=`-Vergleich/Taste) →
  Symfn-/Self-Insert-Budget im Gate gegenpruefen.

### 3. Kill-Ring-Substrat + `kill-line` — mittel, schaltet die Kill-Familie frei.
Zuerst globaler `*ide-kill-ring*` (1 Slot-Konvention wie `%ide-prefix`/`%ide-hint`),
dann `kill-line` darauf. `kill-line`: `ide-string-prefix` (bis Punkt kuerzen) +
Store; Ganz-Zeile via `%ide-lines-delete` + Punkt-Clamp mit
`%ide-buffer-with-lines-point`.
- Binding: **bare `C-k` (Code 11) ist frei** (nur `C-x C-k` = compile 1008, keine
  Kollision). Zweig in `ide-event-command` (Hot Path) → Helfer.
- Kosten: ~2 Slots (kill-store + kill-line). Kein Cap-Risiko bei eigenem Helfer.

### 4. `yank` — mittel, Paar zum Kill-Ring.
Insert des gespeicherten Strings am Punkt: einzeilig ueber
`ide-string-prefix/-suffix/-append`; mehrzeilig ueber `%ide-lines-*`. ~1 Slot.

### 5. `set-mark` / `kill-region` / `copy-region-as-kill` — mittel-hoch, teuerste.
Braucht zuerst einen **Mark-Setter** (der Buffer-Tupel hat das `mark`-Feld schon;
kleiner Tupel-Rebuild analog `%ide-buffer-with-lines-point`). Region-Lesen via
`ide-region-lines` vorhanden; `kill-region` = Span + `%ide-lines-delete`/Splice +
Kill-Ring + Punkt. Region-Highlight im Render bewusst spaeter (teuer).
- Kosten: Mark-Setter + `set-mark-command` + `exchange-point-and-mark` +
  `kill-region` + `copy-region` → ~4–5 Slots. Erst nach Kill-Ring sinnvoll.

### 6. Minibuffer-History — wertvoll, aber durch Cap gebremst.
Global `*ide-mini-history*` + Hoch/Runter im Minibuffer. **`%ide-mini-step` liegt
bei 250/255 B** — Up/Down-Zweige direkt dort sprengen den Objekt-Cap. Braucht
zuerst eine Auslagerung des Key-Handlers aus `%ide-mini-step` in einen Helfer.
Daher trotz Slice-2-Zugehoerigkeit NACH next/prev-buffer terminieren oder mit dem
`%ide-mini-step`-Split buendeln.

## Weitere sichere Reclaim-Kandidaten (blockieren keine nahen Slices)

- **`%ide-buffer-with-lines` (71 B, 1 Slot)** — durch den Candidate-B-Reclaim
  verwaist: 0 Produkt-Aufrufer (der point-lose Line-Setter; Live-Editing nutzt
  `%ide-buffer-with-lines-point`). Nur in 4 resident Stdlib-Subsets referenziert
  (NICHT im Disk-Lib-Gate). Reclaim: `disk_lib 180→179`, Headroom `12→13`.
  Milder Vorbehalt: es ist der natuerliche point-lose Setter — falls ein
  `dired`-Refresh/Whole-Buffer-Replace-Slice ihn will, behalten; sonst entfernen
  (3-Zeilen-Wrapper, trivial reversibel).
- **`ide-visible-frame-lines` (96 B, 1 Slot)** — nur test-referenziert
  (`ide-ui-eval-cases.json:62`); Live-Render nutzt die
  `ide-visible-frame-lines-from`-Variante. Reclaim moeglich, aber niederprioritaer.

Gemeinsam ~2 Slots — Feinschliff, nicht der Hebel. Der strukturelle Hebel bleibt
(wie in den Vor-Audits) das Auslagern weiterer Module auf On-Demand-Disk-Lib
(`ide-disk` zuerst, s. Extension-Plan Slice 2 „Abhaengigkeiten").

### No-go (live oder bald gebraucht — NICHT anfassen)
`%ide-repeat-self-insert` (live, `ide-ui.lisp:396`), `%ide-render-lines-at`,
`%ide-hl-walk/-draw/-state-at` (live Syntax/Render, rekursiv),
`ide-defun-region` (live + geplantes `eval-defun`), `ide-region-lines(-from)`
(live `eval-region`), `ide-buffer-mark`/`-mode`/`-file-name`/`-diagnostics`
(live Disk-Persistenz + Mark-Feature), `compile-file`/`compile-buffer-to-file`
(dokumentierte REPL-Legacy-API). Die Manifest-„zero-inbound"-Heuristik verfehlt
Rekursions- und einige Direktaufrufe — Grep gegen `lib/`/`src/` ist maßgeblich.

## Gate-Erweiterungen fuer den empfohlenen Slice

Fuer #1 (next/prev-buffer) + #2 (delete-char):
- **Host-Tests** `key-event → command` fuer die neuen Bindings (`ide-ui-eval-cases`
  bzw. `ide-buffer-eval-cases`): Zyklus waehlt korrekten Nachbarn inkl.
  Wraparound; `delete-char` mittig, am Zeilenende (Join) und am Buffer-Ende (No-op).
- **`bytecode-p0-ide-lib-check`** (Funktionszahl/Objekte) und
  **`workbench-disk-lib-budget-check`** (Slots/Post-Align-Headroom) — pruefen, dass
  `load_used` im Cap bleibt.
- **`workbench-symfn-dynamic-report`** — Pflicht: `delete-char` fuegt einen
  Hot-Path-Vergleich in `ide-event-command` hinzu; `ide-step-self-insert` und
  `ide-render-*`-Budgets duerfen nicht steigen (Plan: „Dynamic-Report darf
  self-insert/render nicht verschlechtern"). Ggf. Budget-Zeile fuer ein neues
  Szenario `ide-step-delete-forward` ergaenzen.
- **Kein neues C im Dev-Core** (Plan Slice 2).

Fuer die Kill-/Mark-Familie zusaetzlich: Host-Oracle fuer Kill-Ring-Inhalt und
Punkt nach `kill-line`/`kill-region`/`yank`; bei Minibuffer-History ein
Bytecode-Cap-Check nach dem `%ide-mini-step`-Split.

## Kurzfazit
Reihenfolge: **next/previous-buffer → delete-char → Kill-Ring+kill-line → yank →
set-mark/kill-region → minibuffer-history (nach %ide-mini-step-Split)**. Alle
Primitiven fuer die ersten beiden sind vorhanden; erwartete Slot-Kosten der
Top-2 ~2–3, gedeckt durch Headroom 12 und den optionalen
`%ide-buffer-with-lines`-Reclaim (+1). Groesstes wiederkehrendes Risiko ist der
255-B-Objekt-Cap (v. a. `%ide-mini-step` 250 B), nicht die Directory-Slots.
