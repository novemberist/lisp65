# Native REPL Surface Handoff

Stand: 2026-07-03. Dieses Dokument dokumentiert die Entscheidung, wie die
interaktive native REPL dieselben Surface-Forms bekommt, die der Host-Bytecode-
Compiler bereits lowern kann.

## Problem

Der MVP-Produktpfad startet den nativen Tree-Walker plus eingebettete Bytecode-
Stdlib. Die Bytecode-Stdlib enthaelt kompilierte Funktionen, aber keine
materialisierten Makro-Bindings fuer interaktive Eingaben. Dadurch sind Formen wie
`when`, `unless`, `let*` und `case` im Compilerpfad verfuegbar, in der nativen REPL
aber als Known-Open dokumentiert.

Maschinenlesbare Repros: `tests/bytecode/runtime/p0-runtime-known-open.json`.

## Optionen

| Option | Beschreibung | Vorteil | Risiko |
| --- | --- | --- | --- |
| A. Boot-Makros materialisieren | Beim Boot eine kleine Makro-Schicht fuer die REPL in den Tree-Walker laden. | CL-nahe Semantik, nutzt vorhandenen Makro-Mechanismus, wenig neue C-Logik. | Hot-Heap- und Symbol-Footprint; Transitivitaet der Makros muss bewusst klein bleiben. |
| B. Tree-Walker-Special-Forms | `when`/`unless`/`let*`/`case` direkt in `eval.c` behandeln. | Kein Makro-Bootstrap, gut vorhersagbarer Footprint. | Verschiebt ableitbare Library-Semantik in den Kern und widerspricht der Core-vs-Library-Grenze. |
| C. REPL durch Compilerpfad | Interaktive Eingaben zuerst kompilieren, dann per VM ausfuehren; Eval bleibt Fallback. | Langfristig sauberer Nutzerpfad, gleiche Semantik wie Bytecode. | Groesserer Umbau: Makroexpansion, Fehlerorte, Fallback und Debugging muessen stabil sein. |

## Empfehlung fuer den MVP

Option A ist der kleinste Semantik-Fix fuer den MVP. Der Kern besitzt bereits
`defmacro`, Quasiquote, `&rest`, `gensym` und den Makro-Expansion-Hook. Die
fehlende Schicht ist nicht eine neue Primitive, sondern die Boot-Materialisierung
der interaktiven Makros.

Der MVP-Slice sollte klein bleiben:

- `when` und `unless` direkt als Makros ueber `if`/`progn`
- `let` und `let*`, weil `case` ueber `let` expandiert
- `cond`, `and`, `or`, weil `case` und typische REPL-Ausdruecke davon profitieren
- `case` plus die vorhandenen `%case-*` Helper aus der kompilierten Stdlib

`do`, `dotimes` und `dolist` koennen spaeter folgen. Sie sind nuetzlich, aber fuer
das Schliessen der aktuellen Known-Open-Liste nicht noetig.

## Ergebnis 2026-07-03

Der getestete Boot-Makro-Pfad war fuer das aktuelle Produktprofil nicht tragfaehig:

- eingebettete `repl_surface_src` als residenter C-String riss das Stack-Gap;
- Platzierung in `.lisp65_boot` riss wegen der flachen PRG-Datei das
  `$c000`-File-End-Gate;
- selbst stark minifizierte Source blieb zu teuer gegen die knappe Bank-0-Luecke.

Finale MVP-Entscheidung: `case` ist wie `when`/`unless`/`let`/`let*` eine kleine
native Tree-Walker-Special-Form-Ausnahme. Damit sind die sechs bisherigen nativen
REPL-Repros aktiv durch `make repl-surface-smoke` gedeckt, ohne Boot-Source in das
Produkt-PRG zu legen. `cond`/`and`/`or` bleiben Library-/Compiler-Surface und werden
nicht als neues MVP-Gate behandelt.

## Testvertrag

Die frueheren REPL-Repros sind aus `p0-runtime-known-open.json` entfernt und liegen
im aktiven nativen REPL-Smoke:

```lisp
(when t 41 42)                                      ; => 42
(when nil 41)                                      ; => nil
(unless nil 6 7)                                   ; => 7
(let* ((x 1) (y (1+ x))) y)                         ; => 2
(case 'b ((a c) 1) ((b d) 2) (otherwise 3))         ; => 2
(case 'q ((a c) 1) (otherwise 3))                   ; => 3
```

Done-Kriterium:

- die obigen Formen laufen in der nativen interaktiven REPL;
- `make runtime-known-open-check` wird angepasst, sodass diese Forms nicht mehr als
  Known-Open gefuehrt werden;
- der Produkt-Build bleibt unter dem harten Stack-Gap-Gate aus
  `make mvp-vm-stdlib-footprint-report`.

## Nicht-Ziele

- kein breiter neuer C-Kern fuer ableitbare Kontrollformen jenseits der dokumentierten
  MVP-Footprint-Ausnahmen;
- keine Wiederaufnahme von Disk-`load`;
- kein automatischer `xmega65`-Start im Standardcheck.
