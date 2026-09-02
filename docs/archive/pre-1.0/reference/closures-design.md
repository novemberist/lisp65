# M-closures — capturing Closures im Bytecode-Compiler (Design)

**Status:** ✅ **KOMPLETT (2026-07-05, Claude/Lane K)** — Phasen 1 (flach lesend), 2 (mutierbar per-Closure),
3 (mehrstufig transitiv) laufen end-to-end OHNE Treewalk. Pflicht-Meilenstein **VOR M7** (Treewalk raus):
ohne ihn verlöre die Sprache Closures (`T_CLOSURE`). Reihenfolge M6 → **M-closures ✓** → M7 erfüllt; M7 ist
für Closures nicht mehr blockiert. Nur optional offen: 2b (voll geteilt-mutierbar, geboxte Upvalues).

## Problem
Der P0-Compiler lehnt capturing Closures ab: eine freie Variable im Lambda-Rumpf (weder Param
noch lokal noch global) → `err=1` (`compile.c:206`/`543`, via `outer_slot_exists`). Der Treewalk
kann sie (`make_callable(T_CLOSURE, params, body, env)` — volle Env-Capture, `eval.c:529`). Solange
der Compiler das nicht kann, ist „Treewalk raus" ein Sprach-Rückschritt.

Beispiel, das heute `err=1` gibt, im Treewalk aber läuft:
```lisp
(defun adder (n) (lambda (x) (+ x n)))   ; n ist im Lambda frei -> Capture
(funcall (adder 10) 5)                    ; => 15
```

## Was schon da ist
- **Freie-Var-Erkennung** (halb): `outer_slot_exists(name)` (`compile.c:71`) scannt `[0, cc_scopebase)`
  und findet Vars äußerer Funktions-Scopes. Aktuell nur zum Ablehnen — muss zum **Sammeln** werden.
- **`cc_scopebase`** blendet äußere Scopes aus (`resolve_slot` scannt `[cc_scopebase, cc_scopen)`).
- **`T_CLOSURE`-Tag** existiert (`obj.h:47`), `MK_BCODE`/`BCODE_IDX` sind Immediates.
- Lambda-Helfer sind schon eigene CodeObjects (`compile_lambda_helper`, `bc_unit.fn[1..]`).

## Design

### 1. Closure-Objekt (Runtime)
Eine Closure = **Bytecode-Fn (Dir-Index) + eingefangene Upvalue-Werte**. Darstellung als Heap-Zelle
mit dem vorhandenen `T_CLOSURE`-Tag:
```
T_CLOSURE-Zelle:  cell_a = MK_BCODE(di)      (welcher Code)
                  cell_b = (uv0 uv1 ...)     (cons-Liste der eingefangenen Werte)
```
Wenige Upvalues je Closure → cons-Liste reicht (Zugriff O(i), typ. 1–3). GC sieht beide Felder.

### 2. Freie-Var-Analyse (Compiler)
Beim Kompilieren eines Lambda-Rumpfs: statt `outer_slot_exists → err` die freie Variable in eine
**Upvalue-Liste dieser Closure** aufnehmen (dedupliziert, stabile Reihenfolge = Upvalue-Index).
Referenz im Rumpf → `OP_UPVAL <index>` statt `err`. Zuweisung an eine freie Var (`setq`) → Phase 2
(boxed), vorerst weiter `err` (nur lesende Capture in Phase 1).

### 3. Closure-Erzeugung (Codegen + neuer Opcode)
Wo heute `PUSHLIT <Helfer-Symbol>` steht (Lambda ohne Capture), bei Capture stattdessen:
```
; für jede Upvalue in Reihenfolge: den Wert im ERZEUGENDEN Scope pushen
;   (lokaler Slot -> LOADL, oder selbst eine Upvalue -> UPVAL   [verschachtelte Closures])
OP_CLOSURE <helfer-lit> <n-upvals>
```
`OP_CLOSURE` poppt `n-upvals` Werte, baut die Upvalue-Liste, allokiert die `T_CLOSURE`-Zelle
(`cell_a=MK_BCODE(di des Helfers)`, `cell_b=Liste`), pusht sie. **Ohne** freie Var bleibt es beim
reinen `PUSHLIT` (Fast-Path, kein Closure-Objekt, keine Allokation) — Nicht-Closures kosten nichts.

### 4. Upvalue-Zugriff (Codegen + neuer Opcode)
Im Closure-Rumpf: freie Var Nr. i → `OP_UPVAL <i>` → pusht `nth(i, upvals)` des laufenden Frames.

### 5. Aufruf einer Closure (Runtime)
`CALL`/`apply`/`vm_native_apply` bekommen als Callee eine `T_CLOSURE`-Zelle:
- Dir-Index aus `cell_a` (`BCODE_IDX`), Upvalue-Liste aus `cell_b`.
- `vm_run` braucht einen **Frame-Upvalue-Zeiger**, den `OP_UPVAL` liest. Vorschlag: `vm_run`-Signatur
  um `obj upvals` erweitern (NIL für Nicht-Closures) — rippelt nur intern (Lane K, `vm.c`).
- `dir_find`/`sym_function` liefern für benannte defuns weiter `MK_BCODE` (kein Closure-Overhead);
  Closures entstehen nur aus `lambda`/`function`-mit-Capture zur Laufzeit.

### 6. Phasen
- **Phase 1 — Flat-Closures (Werte kopieren) — ✅ FERTIG (`948606e`).** Upvalues = **Snapshot** der Werte bei
  Closure-Erzeugung, einstufige Capture (`cc_outer_base` grenzt den unmittelbar äusseren Scope ab). Deckt den
  Großteil ab (`adder`, Mapping-Closures, Partial-Application, param-lose Closures). Lesend; `setq` einer freien
  Var → noch `err`. Byte-exakt (compile-smoke) + end-to-end (prelude-load-run, ohne Treewalk).
- **Phase 2 — mutierbare Capture — ✅ FERTIG (`38215aa`, ABI `OP_SETUPVAL=65`).** `setq` einer freien Var →
  `resolve_uv` (fängt sie als Upvalue) + `OP_SETUPVAL <i>` (Wert poppen, Upvalue schreiben) + `OP_UPVAL <i>`
  (setq liefert den Wert). Runtime: `OP_SETUPVAL` schreibt via `cell_set_a` die i-te Zelle von `vm_upvals` —
  da das `cell_b` der Closure IST, **über Aufrufe persistent (per-Closure)**. Verifiziert: `make-counter` läuft
  1,2,3,4; zweiter Zähler unabhängig. **Voll geteilt-mutierbar** (mehrere Closures über EINE Bindung) bräuchte
  geboxte Upvalues (Slot→Box-Promotion, `rplaca` im Geräte-VM) — optionaler, grösserer Schritt (2b).
- **Phase 3 — mehrstufige/transitive Capture — ✅ FERTIG (`7bad498`, ABI-frei, Compiler-only).** Umbau der
  Upvalue-Sammlung auf einen **Pro-Ebenen-Stack** (`cc_lvl[CC_FNDEPTH]`, `cc_depth`) mit Quelle je Upvalue
  (`via_upval`: äusseres Local via `emit_arg` vs. äussere Upvalue via `OP_UPVAL`). Rekursiver Resolver
  `resolve_uv(name, L)` fängt eine >1 Ebene aussen liegende Var transitiv ein (jede Zwischen-Fn fängt sie mit).
  Runtime UNVERÄNDERT (Phase-1-`OP_UPVAL` liest an der Creation-Site die Upvalues der äusseren Closure → Kette
  entsteht automatisch). Verifiziert: `(((outer3 1) 2) 3) => 6` end-to-end ohne Treewalk.

## ABI-Erweiterung (gepinnt — Codex, 2026-07-05)
Neue **Opcodes** (kein CALLPRIM): `OP_CLOSURE = 63`, `OP_UPVAL = 64`,
`OP_SETUPVAL = 65`.
Gespiegelt in `src/vm.h`, `docs/bytecode-abi.md` und `tools/host-lisp/bytecode_p0.py`;
`bytecode-p0-drift-check` hält die Tabellen synchron.

## Lane-Split
- **K (compile.c):** Freie-Var-Analyse (Sammeln statt `err`), `OP_CLOSURE`/`OP_UPVAL`-Codegen, Upvalue-Index-Map; Phase 2: `setq` freier Vars → `OP_SETUPVAL`.
- **K (vm.c):** `T_CLOSURE`-Bytecode-Objekt, `OP_CLOSURE`/`OP_UPVAL`-Handler, `vm_run`-Upvalue-Frame, Closure-Aufruf in CALL/apply; Phase 2: `OP_SETUPVAL`-Handler.
- **T (Codex):** Opcode-IDs, `docs/bytecode-abi.md`, `tools/host-lisp` Host-Compiler/VM-Spiegel, Drift-Check, Host-Gate-Härtung.

## Verifikation
Host-Gate `closure-run` (analog `prelude-load-run`): `adder`/Partial-Application/Mapping-Closure kompiliert
→ `vm_run` → Ergebnis geprüft; byte-exakte `OP_CLOSURE`/`OP_UPVAL`-Fälle in `compile-smoke`. Default-Produkt
budgetneutral (Closure-Pfad unter `LISP65_COMPILE_REPL`; Nicht-Closures unverändert `PUSHLIT`).
