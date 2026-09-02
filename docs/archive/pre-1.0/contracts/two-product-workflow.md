# lisp65: Zwei-Produkte-Entscheidung + Anti-Drift-Regeln

> **AKTUELLER HINWEIS (2026-07-08): Auch die spaeteren Zwischenlinien "Full",
> "Dev-Core", "Arena-IDE" und "Runtime-Core spaeter" sind nicht mehr als mehrere
> Nutzerprodukte zu lesen. Der aktuelle Beschluss steht in
> `docs/profile-consolidation-strategy.md`: ein sichtbares Workbench-Produkt,
> alle anderen Targets nur Diagnose/Referenz/Historie. Dieses Dokument bleibt
> Architektur-Historie und Anti-Drift-Regelwerk.**

> **⛳ SUPERSEDED (2026-07-06, docs/einsuite-convergence-design.md): Die Konvergenz ist
> vollzogen — `make mvp-vm-stdlib-einsuite-full` ist DAS Geräteprodukt** (IDE + selbst-
> gehosteter lcc-Compiler als einziger Evaluator + Disk-load/save + nativer Bulk-Render;
> HW-bewiesen pass 17/17 inkl. Disk-Roundtrip). Der Self-Hosting-Compiler löste die unten
> beschriebene arithmetische Grenze: lcc lebt als Bytecode im erweiterten RAM statt als
> ~9-KB-C-Compiler in Bank 0. **Werkbank und Maschinenraum sind als Geräteprodukte
> PENSIONIERT; crfit bleibt Host-Referenz-Vehikel der Äquivalenz-Suite** (Drift-Wache
> tree==C==lcc läuft host-seitig weiter; die Anti-Drift-Regeln unten GELTEN FORT).
> Dieses Dokument bleibt als Architektur-Historie und Regelwerk erhalten. Die historischen
> Tabellen und Prioritaeten unten sind nicht mehr als aktueller Produktplan zu lesen.

## Historischer Stand vor M4

**Entscheidung (Nutzer, 2026-07-05):** lisp65 wird als ZWEI Produkte weiterentwickelt.
Die Ein-Suite (Compiler + interaktive IDE resident in Bank 0) ist nach dem Letzte-Pass-Verdikt
(unten) aufgegeben — nicht aus Bequemlichkeit, sondern an einer arithmetischen Grenze.

## Die zwei Produkte

| | **Werkbank** | **Maschinenraum** |
|---|---|---|
| Target | `make mvp-vm-stdlib` (Ship: `build-mvp-vm-ship.sh`) | `make mvp-vm-stdlib-crfit` |
| Ausführung frischer Formen | Treewalk (`eval_env`, langsam, korrekt) | Geräte-Bytecode-Compiler (schnell) |
| Stdlib+IDE | Bytecode-Blob resident (232 Objekte), `(ide)` interaktiv | Bytecode-Blob resident, KEINE Render-Prims |
| Screen-Render | `VM_SCREEN_PRIMS` + `SCREEN_WRITE_STRING` ✅ | — (passt nicht, s. Verdikt) |
| Rolle | Schreiben, editieren, semantisch testen | `(load "file")` → on-device kompiliert → schnell laufen |
| Beweis-Stand | interaktive IDE xemu-grün (`scripts/xemu-ide-verify.py`); IDE historisch HW-grün | Compiler-REPL + (load) HW-grün auf echter MEGA65 |

## Workflow-Loop

```
1. Werkbank booten → REPL → (ide) → Code schreiben; Quit ⇄ REPL testen (ein Heap!)
2. Datei auf D81 sichern                                [SAVE — Prio 1, in Arbeit]
3. Maschinenraum booten (etherload: Sekunden / SD-Menü)
   → (load "prog") → kompiliert, läuft schnell
4. zurück zu 1 für die nächste Iteration
```
Drittes Bein (Ship-Pfad): Host-Compiler → Blob für fertige Programme.

## Letzte-Pass-Verdikt (warum keine Ein-Suite)

Ziel „Compiler + Render + IDE resident" ist 965 B über Budget; alle Hebel vermessen (2026-07-05):
- Hebel A (Boot-Overlay): recycelt nur LAUFZEIT-Speicher; der Boot-Zeit-Peak in Bank 0 bleibt
  (Codex-Messung: mit Overlay 969 B über statt 965). Tot für diesen Zweck.
- Render-in-Bytecode via peek/poke-Prims (~1150 B .text-Ersparnis): endet trotzdem ~300 B unter
  der 700-B-Laufzeit-Stack-Reserve — die tiefe IDE-Chains schon bei 707 B rissen.
- S5 (Boot-Ballast ganz weg): +420 B Symbol-/Dir-Wachstum frisst den Gewinn; ~1 KB kurz.
- symfn/namelen→EXT (990 B): einziger ausreichend großer Hebel — symfn ist heiß (dir_find
  je Aufruf), EXT = DMA pro Call = ruiniert genau die Compiler-Geschwindigkeit.
Struktur der Wand: Compiler (~12 KB) + Render (≥0,25–1,4 KB) + Symboltabellen (~1 KB) +
Laufzeit-Stack (≥0,7 KB) > freies Bank 0. Es fehlt nicht 1 KB an einer Stelle, sondern an dreien.

**Offene Türen zur Wiedervereinigung** (alles echte Projekte; alles Gebaute bleibt Fundament):
1. EXT-Symboltabelle mit symfn-Cache (docs/symbol-table-ext-design.md);
2. MAP-Code-Banking;
3. **Self-Hosting (docs/post-mvp-vision.md, Strang A3): der Compiler SELBST als Bytecode in
   Bank 5** — der ~12-KB-C-Compiler in Bank 0 IST der Grund der Produkt-Trennung; ein in Lisp
   geschriebener, host-crosskompilierter Compiler kostet ~0 Bank 0 und würde Werkbank+Compiler
   in EINEM Produkt vereinen (Treewalk bleibt Bootstrap/Fallback). Voraussetzungen existieren
   seit 2026-07-05: Bytecode-ABI gepinnt, Blob-Ladeweg, Äquivalenz-Suite als Semantik-Wächter.

## Anti-Drift-Regeln (verbindlich)

Die zwei Produkte sind ZWEI PROFILE EINES QUELLBAUMS, keine Forks:

1. **Ein Quellbaum.** Features landen ungegated in `src/**`/`lib/**`; `#ifdef`-Gates NUR wenn
   Budget es erzwingt (Feature-Gate-Disziplin). Nie produkt-spezifische Kopien von Logik.
2. **Eine Semantik.** Treewalk und Compiler müssen dieselben Ergebnisse liefern. Bestehende
   Gates: `compile-smoke` (byte-exakt), `compile-run`/`repl-session`/`prelude-load-run`
   (Compiler-Semantik). AUSZUBAUEN: Äquivalenz-Suite, die dieselben Formen durch `eval` UND
   `compile_run_top_form` schickt und Ergebnisse vergleicht (Lane K, geplant).
3. **Eine ABI.** Bytecode v1 gepinnt; `make bytecode-p0-drift-check` (docs/vm.h/host/CALLPRIM)
   bleibt Pflicht-Gate. Neue Prims: ABI-Erweiterung IMMER mit Codex koordiniert + drift-gecheckt.
4. **Eine Stdlib/IDE-Quelle.** `lib/**` wird EINMAL geschrieben; Produkte unterscheiden sich nur
   in der Suite-Auswahl (Subset-JSONs) — nie in abweichenden Fn-Definitionen.
5. **Historisch: beide Produkte in `make check`.** Seit M4 gilt stattdessen: Das aktuelle
   Geräteprodukt `mvp-vm-stdlib-einsuite-full` ist Produktgate; crfit bleibt baubar und
   als Referenz-/Equivalence-Fahrzeug nutzbar, aber nicht mehr als Geräteprodukt-Pflichtgate.
6. **Budget-Kopplung je Produkt.** lib+Suite+Makefile-Profil = EIN Artefakt (Referenz-Commit-
   Pins, Codex' Gates G1–G3) — gilt für beide Profile getrennt.

## Prioritätenliste (Stand 2026-07-05)

1. **SAVE** — Disk-Write-Primitiv + `(save ...)`: schließt den Werkbank→Maschinenraum-Loop.
   MVP-Design: Overwrite-in-place in vorallozierte D81-Datei-Slots (kein BAM-Management);
   CBM-Ketten-kompatibel, damit der HW-grüne Regel-B-(load) sie liest. Lane K (io.c/vm.c),
   D81-Slot-Tooling Lane T.
2. **eval-Naht in der IDE** — `eval` + `read-from-string` als Prims exponieren (heute nicht
   im Lisp sichtbar; ide-eval-request.lisp-Plumbing existiert schon) → Defun-at-point-Eval
   ohne Editor-Exit. Ändert das eingefrorene Default-Produkt → Gate-Re-Pin mit Codex.
3. **HW-Verifikation** der interaktiven IDE (xemu→echte MEGA65).
4. Maschinenraum-Pflege: volles Prelude im crfit-Profil (Bank-0-Diät, Codex), S5 als Option.
