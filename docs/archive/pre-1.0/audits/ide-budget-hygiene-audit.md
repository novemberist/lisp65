# Budget-Hygiene-Audit: 242 Bytecode-Objekte → Slot-Reclaim

Stand: 2026-07-04 (Claude, Lane K — **Analyse**; Ausführung = Lane L/T, s. u.).
Grundlage: `build/bytecode/stdlib-p0.manifest.json` (`functions`=242), Referenz-Zählung
über `lib/*.lisp` + `src/` + Tests, symbolgenaue Lisp-Wortgrenzen.

## Motiv
Footprint-Report (`59ce050`): **Directory 242/244 (2 frei), Symbole 323/332 (~9 frei)**,
Namepool 115 B frei, Bank-0-`.text`-Reserve 22 B. Neue Bytecode-Lisp-Funktionen (Hebel B)
kosten je 1 Directory-Slot + 1 Symbol + Namepool → nach ~2 Funktionen ist `VM_DIR_MAX` voll.
Caps hochsetzen frisst die 22 B `.text`-Reserve (Overflow). Also: erst Slots zurückgewinnen.

## Methode & Kern-Befund
44 der 242 Objekte haben **0 interne (lib-)Aufrufer UND 0 `src/`-Referenz**. Aber **alle 44
haben Test-Referenzen** → **kein versehentlich toter Code**; das Aufräumen nach der
Perf-Kampagne hat sauber gearbeitet. Der Dispatch (`ide-apply-command`) ist **statisch**
(kein `intern`/`funcall`), die 0-Aufrufer-Zählung also verlässlich. Die 44 teilen sich in:

## Gruppe 1 — IDE-Funktionen ohne Live-Pfad (18) → RECLAIM-Kandidaten
Live-Einstieg ist `(ide)` → `ide-run` → `ide-render` (nutzt
`ide-visible-frame-lines` + `%ide-render-dirty-lines-at` + Render-Cache) und `ide-step` /
`read-key` / `%ide-drain-pending`. Folgende sind von dort NICHT erreichbar (nur Tests):

**1a. Hoch — durch den Perf-Umbau abgelöst (Live-Pfad nutzt neuere Variante):**
| Funktion | abgelöst durch |
| --- | --- |
| `ide-frame-lines` | `ide-visible-frame-lines` |
| `ide-render-line-text` | `%ide-render-dirty-lines-at` / `ide-render-line-at` |
| `ide-cursor-code` | inline in `ide-render-cursor` (`string-ref`) |
| `ide-poll-step` | Live-Loop nutzt `read-key` |
| `ide-read-step` | Live-Loop nutzt `read-key` + `%ide-drain-pending` |
| `%ide-state-with-message` | interner Setter, 0 Aufrufer |
| `%ide-state-with-view` | interner Setter, 0 Aufrufer |
| `%ide-dirty-line-p` | interner Helper, 0 Aufrufer |
| `ide-event-modifiers` | Event-Helper, 0 Aufrufer |

**1b. Mittel — ungenutzte Accessoren/Ops; Lane L bestätigt, ob für geplante Features reserviert
(Completion/Symbol-Browser/Diagnostics):**
`ide-current-line`, `ide-delete-line`, `ide-insert-line` (Buffer-Ops, nur in `ide-buffer.lisp`
+ Tests — evtl. durch Aktive-Zeilen-Cache abgelöst), `ide-buffer-diagnostics`,
`ide-buffer-file-name`, `ide-buffer-mark`, `ide-buffer-mode` (Buffer-Accessoren),
`ide-runtime-symbol-names`, `ide-runtime-symbol-entries` (Symbol-Introspektion).

Nachtrag 2026-07-09: `ide-runtime-symbol-*` und die point-losen Wrapper
`ide-delete-line`/`ide-insert-line` sind reclaimed; siehe
`docs/ide-tab-budget-audit-2026-07-09.md` und
`docs/ide-line-op-audit-2026-07-09.md`.

## Gruppe 2 — öffentliche Stdlib-API (26) → BEHALTEN (kein Delete)
0 interne Aufrufer, weil es **Blatt-API** ist, die der *User* ruft; alle getestet:
`abs oddp signum integerp nonnegativep nonpositivep butlast copy-list assq mapcan count-if
position position-if remove-if remove-if-not char->string char-upcase null string-trim
string-equal string-contains-p string-suffix-p string/= string<= string>= string>`.
Kein Hygiene-Delete (das schrumpft die Sprache). Selten genutzte davon sind **Kandidaten für
Hebel F** (auf Disk auslagern, on demand laden) — erst nach der LOAD-Produkt-Integration.

## Reclaim-Rechnung (wenn Lane L Gruppe 1 entfernt)
| | Directory | Symbole | Namepool |
| --- | --- | --- | --- |
| nur 1a (9) | 2→**11** frei | 9→**18** frei | +~180 B |
| 1a+1b (18) | 2→**20** frei | 9→**27** frei | +~360 B |

Plus EXT-Blob-Code/Literale (nicht Bank 0). **Wichtig:** das gibt SLOT-Headroom in den
fix dimensionierten Arrays frei, nicht die 22 B `.text`-Reserve. Optional danach die Caps
senken (`VM_DIR_MAX`, `MAX_SYM`) → das wandelt Slots in `.text`-Bytes (~5–6 B/Slot).

## Ausführung — Lane L/T (nicht Lane K)
`lib/ide-*.lisp` + die Host-Eval-Cases (`lib/tests/ide-ui-eval-cases.json` u. a.) gehören
Lane L. Entfernen muss Funktion + zugehörige Test-Cases **im Gleichschritt** (sonst `make
check` rot). Lane K liefert nur diese Analyse. Empfehlung: **1a zuerst** (hohe Konfidenz),
1b nach Intent-Klärung durch Lane L. Danach Footprint-Report neu ziehen (Headroom sichtbar).

## Codex-Nachzug (2026-07-04)
**1a erledigt.** Entfernt wurden die 9 hoch-konfident abgeloesten IDE-Funktionen aus
`lib/ide-ui.lisp` samt Host-/Bytecode-Cases. Zusaetzlich fielen zwei direkte Folge-Helpers
des geloeschten Padding/Dirty-Helper-Pfads (`%ide-row=`, `ide-space-string`/
`%ide-space-codes-into`). Das Produkt-Bundle steht danach bei **230 Objekten** und
**178 Produkt-Cases**; `ide-bytecode-cost-report` meldet **94 IDE-Funktionen**.

Konservative Cap-Senkung ist aktiv: `MAX_SYM=320` (311 belegt, Headroom 9) und
`VM_DIR_MAX=238` (230 belegt, Headroom 8). Damit steigt die Bank-0-Reserve von 22 auf
**126 B** (`stack_gap=1576/1450`, `bank0_bss_bytes=4622`). Gruppe 1b bleibt offen, bis
Lane L entschieden hat, ob Completion/Diagnostics/Symbol-Browser die Accessoren brauchen.

## Verdikt
Der Blob war **nicht mit versehentlichem totem Code aufgebläht** — die 242 Funktionen waren
absichtlich getestet; die Slot-Enge war echte Nachfrage, kein Müll. Nach dem Codex-Nachzug ist
die hoch-konfidente 1a-Gruppe entfernt. Aktuell offen bleibt Gruppe 1b: bis zu **9 weitere
Directory-/Symbol-Slots**, aber nur nach Intent-Klärung fuer Completion/Diagnostics/
Symbol-Browser. Die strukturelle Entlastung bleibt Hebel F (Stdlib/IDE-Module auf Disk) nach
der LOAD-Integration; dieser Audit ist der taktische Zwischenschritt.
