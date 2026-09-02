# Workbench TAB/Budget-Reclaim-Audit (2026-07-09)

Stand: 2026-07-09 (Claude, Worktree `claude/ide-tab-budget-audit`).
Auftrag: `docs/collaboration.md` → „Claude Task: Workbench TAB/Budget-Reclaim-Audit".
Basis: `origin/main` @ `2bb7f07` (nach `58f7f92 ide: add tab cycling in minibuffer`).
Vorlaeufer: `docs/ide-budget-hygiene-audit.md` (2026-07-04, Gruppe 1a erledigt,
1b offen).

## 1. Baseline reproduziert

Alle Host-Gates gruen; die von Codex genannten Zahlen sind exakt reproduziert
(die Cross-Toolchain `tools/llvm-mos/` fehlt in diesem Worktree, daher wurde
`workbench-disk-lib-budget-check` direkt gegen die gebauten Manifeste gefahren –
identisches Ergebnis wie das Gate):

```
workbench-disk-lib-budget: PASS resident=319 start=320 disk_lib=184
  load_used=504 post_align=504 cap=512 headroom=8 post_headroom=8
  codebuf=56 codebuf_required=48 codebuf_headroom=8 codebuf_worst=ide-apply-command
bytecode-p0-ide-lib-check: PASS functions=184 cases=70 code_bytes=14237 dir_bytes=1778
workbench-symfn-dynamic-report: PASS instructions=125123/130000 symfn=8649/9000
```

**Bindender Engpass ist die Directory-Slot-Zahl, nicht Code-Bytes.**
`load_used = disk-lib-start(320) + disk_lib-Funktionen(184) = 504`, Cap
`VM_DIR_MAX=512`. Jede entfernte/verschmolzene IDE-Funktion gibt genau
**1 Slot** frei. Code-/EXT-Bytes (10173 code, 26099 ext) sind hier nicht das
Limit. Zweit-engster Wert: `codebuf_headroom=8` (Worst-Case-Objekt
`ide-apply-command`) und `symfn`-Headroom 351 – beide bei Merges beachten,
NICHT bei reinem Loeschen toter Funktionen.

## 2. Methode

`build/bytecode/libs/ide.manifest.json` liefert alle 184 Disk-Lib-Objekte mit
Groesse und Literal-Symbolen. Daraus interner Referenzgraph (eingehender Grad je
Funktion). Cross-Check gegen: resident Stdlib-Manifest (`stdlib-p0`), alle
`lib/*.lisp`, `src/`, alle Test-Suites (`tests/**`, `lib/tests/*.json`) mit
symbolgenauen Lisp-Wortgrenzen. Der Command-Dispatch (`ide-apply-command`) ist
statisch (kein `intern`/`funcall` auf Namen), die 0-Aufrufer-Zaehlung also
verlaesslich (bereits im 2026-07-04-Audit festgestellt, hier bestaetigt).

## 3. Kern-Befund: TAB aktiviert die toten Accessoren NICHT

Zentrale Frage des Auftrags: Hat `58f7f92` (TAB-Cycling) einen der 2026-07-04
als „nur-Test / kein Live-Pfad" markierten Accessoren wieder scharfgeschaltet?

**Nein.** `%ide-mini-tab-value` (der neue TAB-Helper, `lib/ide-ui.lisp:61`)
zykelt ueber eine **vorgegebene `options`-Liste**. Die vier Minibuffer-Starter
liefern diese Optionen aus Datei-/Buffer-Quellen, nicht aus der Symboltabelle:

| Starter | options-Quelle |
| --- | --- |
| `find-file`  (`ide-disk.lisp:357`)  | `(dir)` |
| `write-file` (`ide-disk.lisp:366`)  | `(dir)` |
| `switch-buffer` (`ide-ui.lisp:331`) | `(%ide-buffers-names alist)` |
| `compile-buffer` (`ide-ui.lisp:345`)| `(dir)` |

Damit ist die 2026-07-04 offengelassene Intent-Frage fuer die
Symbol-Introspektion beantwortet: Completion braucht sie nicht.

## 4. Statuswechsel seit 2026-07-04 (wichtig)

Die damalige „Gruppe 1b" (bis zu 9 Slots) ist **teilweise verbraucht**: Die
Buffer-Accessoren sind inzwischen im Live-Pfad, weil die Disk-Persistenz sie
serialisiert:

| Funktion | Status heute | Beleg |
| --- | --- | --- |
| `ide-buffer-file-name` | LIVE – behalten | `ide-disk.lisp:295,296` |
| `ide-buffer-mark`      | LIVE – behalten | `ide-disk.lisp:307` |
| `ide-buffer-mode`      | LIVE – behalten | `ide-disk.lisp:309` |
| `ide-buffer-diagnostics`| LIVE – behalten | `ide-disk.lisp:311` |

Realistisch reclaimbar bleiben aus 1b also nur die Symbol-Introspektion und die
Buffer-Line-Ops (unten).

## 5. Reclaim-Kandidaten (priorisiert)

### Kandidat A — Symbol-Introspektion-Cluster · 4 Slots · EMPFOHLEN
Geschlossener, toter Cluster; 0 Produkt-Aufrufer in `lib/`/`src/`, durch TAB
bestaetigt ungenutzt:

| Funktion | Groesse | Rolle |
| --- | --- | --- |
| `ide-runtime-symbol-names`   | 20 B | oeffentl. Wrapper, 0 Aufrufer |
| `ide-runtime-symbol-entries` | 20 B | oeffentl. Wrapper, 0 Aufrufer |
| `%ide-runtime-symbol-names-from`   | 52 B | nur vom Wrapper gerufen → mit-tot |
| `%ide-runtime-symbol-entries-from` | 69 B | nur vom Wrapper gerufen → mit-tot |

Alle vier in `lib/ide-ui.lisp:701–728`. Slot-Effekt: `disk_lib 184→180`,
`load_used 504→500`, `headroom 8→12`.
- Konfidenz: hoch. Risiko: niedrig (kein Live-Pfad, kein UX-Bezug, kein Merge –
  reines Loeschen, daher codebuf/symfn-neutral).
- Test-Kopplung (Lockstep-Edit noetig): je 5 Suites –
  `tests/bytecode/libs/p0-ide-lib.json` (Disk-Lib-Gate) plus die resident
  Stdlib-Subsets `p0-stdlib-subset.json`, `p0-stdlib-einsuite-subset.json`,
  `p0-stdlib-einsuite-fasl-subset.json`, `p0-stdlib-werkbank-subset.json`.

### Kandidat B — Buffer-Line-Ops · +2 Slots · MITTEL
Vom Aktive-Zeilen-Cache abgeloest (Verdacht 2026-07-04 bestaetigt); kein
Produkt-Aufruf, nur `lib/tests/ide-buffer-eval-cases.json`:

| Funktion | Groesse | Test-Kopplung |
| --- | --- | --- |
| `ide-delete-line` | 25 B | `ide-buffer-eval-cases.json:21` |
| `ide-insert-line` | 26 B | `ide-buffer-eval-cases.json:11,16,96` |

Konfidenz mittel, Risiko niedrig-mittel (nur eigene Testfaelle betroffen).

### NICHT empfohlen — `ide-current-line`
0 Produkt-Aufrufer, aber in Tests als **Pruef-Sonde** fuer *andere* Funktionen
verwendet, z. B. `(string-length (ide-current-line (ide-insert-char …)))`
(`p0-ide-lib.json:176`, `p0-stdlib-subset.json:1193/1298` u. a.). Entfernen
erzwingt Umschreiben fremder, weiterhin gewollter Testfaelle → Aufwand/Risiko
unverhaeltnismaessig fuer 1 Slot. Behalten.

## 6. Reclaim-Rechnung

| Umsetzung | disk_lib | load_used | headroom |
| --- | --- | --- | --- |
| Ist | 184 | 504 | 8 |
| + Kandidat A (4) | 180 | 500 | 12 |
| + A + B (6) | 178 | 498 | 14 |

## 7. Empfehlung / naechster Schritt

- **Kandidat A** als eigener, review-fertiger Commit umsetzen: die vier Defuns
  aus `lib/ide-ui.lisp` entfernen und in denselben Commit die zugehoerigen
  Eintraege/Cases aus den fuenf oben gelisteten Suites herausnehmen.
- Danach Host-Gates (kein Geraet noetig): `make bytecode-p0-ide-lib-check`,
  `make workbench-symfn-dynamic-report` und – nach Toolchain-Build –
  `make workbench-disk-lib-budget-check` + `make check`.
- Kandidat B optional hinterher, wenn 14 statt 12 Headroom gewuenscht ist.
- Strukturell bleibt der grosse Hebel (wie 2026-07-04 vermerkt) das Auslagern
  weiterer Module auf Disk / on-demand-Load; dieser Audit ist der taktische
  Zwischenschritt, um vor dem naechsten IDE-Feature Slot-Luft zu schaffen.

Dieser Worktree editiert nur diese Analyse-Doku, keinen Produktcode – die
Loeschung ist bewusst als Empfehlung an Codex ausgelagert (Auftrag: „Fokus:
Bericht/Empfehlung").
