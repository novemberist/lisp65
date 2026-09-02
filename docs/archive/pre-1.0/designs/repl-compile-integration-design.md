# Design: M6 REPL-Integration — der Compiler ersetzt den Treewalk

Stand: 2026-07-05 (Claude, Lane K). Status: **DESIGN / Go-No-Go + ABI-Abstimmung mit Codex offen.**
Voraussetzung: der geräteseitige Bytecode-Compiler (`src/compile.c`) ist fertig und **semantisch
validiert** (`make compile-run`: kompilieren → CodeObject → `vm_run` → Ergebnis geprüft; Ausdrücke,
Kontrollfluss, Bindungen, `lambda` laufen korrekt). M6 macht ihn zum REPL-Auswerter; M7 entfernt danach
den Treewalk.

## 1. Ziel

Die REPL-Schleife (repl.c:195) tut heute `print_obj(eval(read_expr(&p)))` — Treewalk. M6 ersetzt das
durch **read → compile → assemble → `vm_run` → print**. Danach laufen ALLE Nutzereingaben als Bytecode
(schnell, EIN Ausführungsmodell). M7: `eval_env` + Treewalk-Special-Forms raus (~3,2 KB Bank-0 frei).

## 2. Was fehlt dem Compiler noch für den vollen REPL-Surface

Der Compiler kann Ausdrücke/Kontrollfluss/Bindungen/`lambda`. Für eine echte REPL-Sitzung fehlen vier
Dinge — jedes mit seiner Auflösung:

### 2a. Globale Variablen-Referenz  → **neue Primitive `symbol-value`**
Ein blankes Symbol, das NICHT lokal gebunden ist, ist eine globale Variable (Treewalk: `sym_value`).
Der Compiler meldet das heute als `unsupported`. Auflösung: neue CALLPRIM `symbol-value` (§4a, ID 19).
Codegen: `PUSHLIT <sym>; CALLPRIM 19 1`. (Lisp-2: selten — Globals sind meist Funktionen, nicht Werte.)

### 2b. Globales `setq`  → **neue Primitive `set-symbol-value`**
`(setq gvar val)` mit nicht-lokalem `gvar` (Treewalk: `set_sym_value`). Auflösung: CALLPRIM
`set-symbol-value` (§4a, ID 20). Codegen: `PUSHLIT <gvar>; <val>; CALLPRIM 20 2`. (Der Compiler
entscheidet lokal-vs-global über `resolve_slot`: gebunden → `STOREL`, sonst → diese Prim.)

### 2c. `defun` / `defmacro`  → **REPL-Ebene (KEIN neuer Prim nötig)**
Statt `set-symbol-function` als Bytecode-Prim zu emittieren, behandelt die **REPL-Schleife** Top-Level-
`defun`/`defmacro` als Sonderfall in C (wie der Treewalk sie als Special-Forms behandelt):
1. Rumpf wie ein `lambda` zu einem Helper-CodeObject kompilieren.
2. Blob in die **Compiled-Fn-Region** (§3) anhängen, `vm_dir_add(name, bank, off, len)`,
   `set_sym_function(name, MK_BCODE(di))`. Bei `defmacro`: zusätzlich als Makro markieren (§2d).
Das hält die Bytecode-ABI schlank und spiegelt exakt die Treewalk-Semantik. (Verschachteltes `defun`
im Rumpf ist selten → vorerst `unsupported`.)

### 2d. Makro-Expansion  → **nur für ECHTE User-Makros (großer Vereinfachungs-Befund)**
**Weil der Compiler `when`/`unless`/`and`/`or`/`cond`/`defun`/… als BUILT-INS implementiert, überschattet
er die gleichnamigen Prelude-`defmacro`s.** Die „das Prelude ist auf Makros gebaut"-Sorge aus dem
M5-Scoping ist damit für die Built-ins **aufgelöst** — der Compiler macht sie nativ. Echte
Compile-Zeit-Expansion braucht es nur für **benutzerdefinierte** `defmacro`s. Ablauf beim Compiler,
wenn `(op args…)` und `sym_function(op)` ist ein Makro:
1. Makro-Rumpf (kompiliert, in der Compiled-Fn-Region) per `vm_run` mit den **UN**ausgewerteten `args`
   als Argumente laufen lassen → Expansion (ein `obj`).
2. Die Expansion rekursiv kompilieren (`compile_expr`).
Die Infrastruktur steht: der Compiler hat `vm_run` + `bc_assemble` + die Registrierung. Makro-Marker:
ein eigener BCODE-Tag ODER ein paralleles „ist-Makro"-Bit je Symbol (Design-Detail, §5).

## 3. Runtime-Speicher: wo wohnen laufzeit-kompilierte Funktionen?

Die zentrale Entscheidung. **Wiederverwendung des Disk-Lib-Mechanismus** ([[stufe2-disk-bytecode-libs]]):
- Eine **Compiled-Fn-Region** in erweitertem RAM (Bank 5, hinter Stdlib-Blob/Libs, vor dem Namepool —
  ODER Bank 4), **append-only**, 8er-Block-aligned wie die Disk-Libs (`vm_dir_align8`).
- Jede `defun`/`lambda`-Helper-CodeObject-Blob wird angehängt; `vm_dir_add` registriert
  `name → (bank, off, len)`; `vm_code_load` liest von dort (identische Naht wie Stdlib/Libs/`compile-run`).
- **GC:** kompilierte Fns sind permanent (nie ge-GC't, wie die Stdlib). **Redefinition** (`defun` erneut):
  neuen Blob anhängen + Directory-Eintrag updaten; der alte Blob leakt (akzeptabel; spätere Kompaktierung
  ist ein separater Schritt).
- **Literale** einer kompilierten Fn (`littab`) tragen `obj`-Werte (Heap-Zellen für Listen/Strings). Diese
  müssen **GC-gerootet** sein, solange die Fn lebt → die littab-Objekte in einen permanenten Root-Satz
  (wie die Stdlib-Literale). **Wichtige Härtung**, sonst GC frisst Fn-Literale.

## 4. Die REPL-Schleife (repl.c) — der Swap

Ersetzt `print_obj(eval(read_expr(&p)))` durch (flag-gegatet, s. §6):
```
form = read_expr(&p);
if (is top-level (defun name ...) / (defmacro name ...))  -> §2c: kompilieren, in Compiled-Fn-Region,
                                                             registrieren; print name.
else  -> bc_compile_top(form) ; falls Makro-Aufruf im Baum: §2d expandieren ; assemble Main in die
         Region ; got = vm_run(main) ; print_obj(got).
```
Fehlerpfad: `u.err` → „*** cannot compile: <form>" (sauber, kein Absturz), REPL erholt sich.

## 4a. Vereinheitlichung mit dem Load-System — M6 und `load` sind EIN Ding

**Kernbefund (Abgleich mit `docs/load-system.md` + `docs/load-rule-b-design.md`):** der On-Device-
Compiler verschmilzt die REPL-Integration mit der Zukunft von `load`/`load-lib`/`compile-file`. M6 MUSS
das mitdenken, sonst bauen wir Doppel-/Konfliktpfade.

**(a) `load_source` und der REPL-Swap sind DIESELBE Operation.** `(load "x.LSP")` heißt „lies Source,
werte Top-Level-Formen aus" — heute Treewalk (`load_source`→`eval`), mit M6 **compile-and-run je Form**.
Das ist byte-für-byte der REPL-Swap aus §4. **Regel: EINE Funktion `compile_run_top_form(form)` (kompilieren
in die Compiled-Fn-Region, `defun`/`defmacro`-Sonderfall §2c, sonst `vm_run`), die REPL UND `load_source`
teilen.** `load_source` wird zur Schleife `for each form: compile_run_top_form`. Nicht doppelt bauen.

**(b) `compile-file` (Source → `.LBC`) wird geräte-nativ — `bc_assemble` ist schon der Schreiber.** Das
`.LBC`-Bytecode-Dateiformat aus `load-system.md` **IST das CodeObject-Blob**, das `bc_assemble` erzeugt
und `load-lib` liest. `(compile-file "x.LSP")` = lies Source → je Form `bc_compile_top` → `bc_assemble` →
Blobs + Directory in eine `.LBC` schreiben. Damit produziert der Compiler, der die REPL auswertet,
zugleich ladbare Bytecode-Libs. Der Host-Toolchain-Zwang (`bytecode_p0_compiler.py` als EINZIGE
Lib-Quelle) fällt weg; das Gerät wird selbstständig.

**(c) EINE Compiled-Fn-Region für alles.** REPL-`defun`s, `load_source`-`defun`s UND `load-lib`-Funktionen
teilen sich §3-Region + `vm_dir`. `load-lib` (schon-Bytecode) hängt Blobs direkt an; `load_source`/REPL
kompilieren erst. Gleiche Naht (`vm_dir_add` + `vm_code_load`), gleiches GC-Rooting der littab.

**Strategische Konsequenz:** `load-system.md`s „Source (`.LSP`) und Bytecode (`.LBC`) bedienen denselben
Modulnamen; Bytecode gewinnt, wenn beide da sind" passt exakt: `.LBC` = schneller Pfad (`load-lib`),
`.LSP` = portabler Pfad (`load_source`-compile), `compile-file` = die Brücke. **`load-lib` bleibt
unverändert** (der schon-Bytecode-Fall); M6 fügt den compile-Fall hinzu, nicht ersetzt ihn.

**M6-Reihenfolge-Empfehlung daraus:** zuerst `compile_run_top_form` + Region + `defun` (REPL-Swap §4),
DANN `load_source` daraufsetzen (fast trivial: die Schleife), DANN `compile-file` als Folge-Slice. So
entsteht kein Wegwerf-Code. Lane-Split unverändert (§7); `load`-Bytecode-Lisp bleibt Lane L.

## 5. ABI-Erweiterung (Codex-Pin 2026-07-05 — §4a ist eingefroren, erweiterbar HINTEN)
Neue **CALLPRIM-IDs 19/20** sind vergeben: `19 = symbol-value`, `20 = set-symbol-value`.
ID 21 bleibt vorerst frei; `symbol-function` wird erst vergeben, wenn M6 sie wirklich braucht.
Gespiegelt in `docs/bytecode-abi.md §4a`, `tools/host-lisp/bytecode_p0.py`,
`tools/host-lisp/bytecode_p0_compiler.py`, `src/compile.c`, `src/vm.c`; der Drift-Check hält das
synchron. Die C-VM-Dispatch-Fälle sind bis zur nativen M6-Verdrahtung unter
`LISP65_VM_GLOBAL_PRIMS` gegatet, damit das aktuelle Produkt keine ungenutzte Bank-0-.text zahlt.
Makro-Marker (§2d) ist Lane K (`symbol.c`/`obj.h`), kein ABI-Bruch (nur Runtime-Semantik).

## 6. Rollout — inkrementell, HW-verifiziert (die Kern-Lektion: „linkt ≠ bootet")
1. Host: `compile-run` um Globals/`defun`/User-Makro-Fälle erweitern (mit den neuen Prims + der
   REPL-Ebenen-`defun`-Simulation). Byte-exakt + semantisch grün.
2. Device: REPL-Swap **flag-gegatet** (`LISP65_COMPILE_REPL`), Treewalk bleibt als Fallback. **HW-Deploy**
   + Test (Ausdruck, `defun`+Aufruf, `setq`, User-Makro) — die eine Grenze, die der Host nicht ersetzt.
3. Default-Flip (Compiler wird der REPL-Auswerter). HW-Re-Test.
4. **M7: Treewalk raus** — `eval_env` + Treewalk-Special-Forms entfernen, ~3,2 KB Bank-0 frei; `apply`
   für funcall/apply-von-Bytecode bleibt (Bytecode-Pfad). HW-Verifikation. Erst wenn 1-3 grün.

## 7. Lane-Split
- **K (Claude):** Compiler-Erweiterungen (Globals/Makro-Expansion in `compile.c`), REPL-Schleife
  (`repl.c`), Compiled-Fn-Region + Root-Härtung (`io.c`/`mem.c`), Makro-Marker (`symbol.c`).
- **T (Codex):** ABI-IDs 19-20 (§4a, `bytecode_p0.py`, Drift-Check), Profil-Flags (`LISP65_COMPILE_REPL`),
  Footprint-Gate, HW-Test-Rezept. **ABI-Vergabe interface-first hier ankündigen.**
- **Gemeinsam:** Go-No-Go nach dem Host-Nachweis; jeder Device-Schritt HW-gebootet ([[core-profile-no-hw-boot]]).

**Codex-Nachzug (2026-07-05):** Der T-Scaffold steht separat vom aktuellen Ship-Profil:
`make mvp-vm-stdlib-compile-repl` linkt `src/compile.c` + `src/compile_repl.c` mit
`-DLISP65_COMPILE_REPL` und `-DLISP65_VM_GLOBAL_PRIMS`; `make
mvp-vm-stdlib-compile-repl-footprint-report` misst das harte M6-Budget, sobald das Profil linkt;
`make hw-smoke-compile-repl-dry-run` zeigt den Etherload-Pfad ohne echte Session und ohne
Build-Pflicht. Nach dem `repl.c`-Hook ist der Host-Pfad gruen (`make repl-session`). Claudes
Puffer-Slimming senkte den fetten main+IDE-M6-Linkblocker auf `.text +4183`, `.bss +12694`;
Codex' Compile-REPL-Profil-Default laesst VM-Screen-Prims/`screen-write-string` weg und reduziert
die Caps, womit der Blocker auf `.text +2410`, `.bss +10159` sank. Nach dem Immediate-Lambda-
Codegen (`5fc7375`) ist der aktuelle Blocker `.text +3299`, `.bss +11048`. M7/weitere Profil-Diaet
bleibt damit der naechste harte Geraete-Schritt.
Das ist das Go/No-Go-Messwerkzeug fuer den M6-Swap, nicht der heutige MVP-Ship-Pfad.

## 8. Nutzen am Ende
EIN Ausführungsmodell (Bytecode/`vm_run`), Nutzercode **kompiliert** (schnell statt getreewalkt),
~3,2 KB Bank-0 zurück (Treewalk weg). Der geräteseitige Compiler war ohnehin immer das Ziel; M6/M7 macht
ihn zum Herzstück der REPL.
