# Ein-Suite-Konvergenz: lcc-first-REPL + Treewalk-Diät (Lane K, 2026-07-06)

> **Superseded 2026-07-08:** `einsuite-full` bleibt Referenz/Regression. Das
> aktuelle Produktpaket ist der Workbench-MVP via `make mvp-ship`; siehe
> `docs/project-status.md` und `docs/workbench-gate.md`.

**Status: ✅ ABGESCHLOSSEN 2026-07-06 — Konvergenz vollzogen, einsuite-full = DAS Geräteprodukt (HW pass 17/17).** Nach dem HW-Beweis der Ein-Suite (pass 10/10 auf echter
MEGA65, 8cc7f0f), dem M3-Strip-HW-Beweis und dem M4-Disk-Roundtrip ist der Vollausbau
gepinnt: Treewalk-frei, Disk-load/save resident und Bulk-Render aktiv.
`make mvp-ship` baut dieses Produkt; crfit bleibt nur noch Referenz-/Equivalence-Vehikel.

## Ausgangslage: die 9-KB-Symmetrie (gemessen)

Beide Geräteprodukte tragen ~9 KB „zweite Engine" in Bank-0-.text:

| Produkt | zweite Engine | .text |
|---|---|---|
| Maschinenraum (crfit) | C-Compiler (`compile_expr` & Co., src/compile.c) | **9023 B** |
| Ein-Suite (einsuite) | Treewalk (`eval_env` 3194 + `apply` 3745 + `eval_init` 980 + Brücken) | **9019 B** |

Der ursprüngliche Plan „compile.c im Maschinenraum durch den lcc-Blob ersetzen" ist eine
Sackgasse mit Umweg: ein crfit-auf-lcc wäre architektonisch die Ein-Suite minus IDE — die
Konvergenz endet so oder so bei EINEM Produkt. Der direkte Weg ist, die (bereits HW-bewiesene)
Ein-Suite zum Maschinenraum-Nachfolger auszubauen, statt das alte Produkt zu renovieren.

## Zielbild

**EIN Geräteprodukt** (die Ein-Suite), in dem der lcc-Blob der EINZIGE Compiler ist und jede
REPL-Eingabe lcc-first läuft (kompiliert + auf vm_run ausgeführt — Maschinenraum-Semantik).
Der Treewalk schrumpft auf den Träger-Vertrag und fällt am Ende ganz (crfit/M7 hat bewiesen,
dass das geht). `src/compile.c` bleibt HOST-seitig als Referenz-Engine der Äquivalenz-Suite
(Drift-Wächter tree==C==lcc läuft weiter auf dem Host) — es wird NICHT gelöscht, nur nicht
mehr aufs Gerät gelinkt. crfit bleibt als Host-/Referenz-Vehikel, wird als Geräteprodukt
pensioniert.

Reinvestition des freigeschnittenen .text (~3–4 KB realistisch, s. Budget): Disk resident
(load/save, v2b brauchte ~1231 B), Bulk-Render zurück (~900 B), Rest = Reserve-Polster.

## Warum das dem Äquivalenz-Versprechen dient

Heute hat die Ein-Suite ZWEI Ausführungspfade (Treewalk-eval für REPL-Eingaben, lcc-Bytecode
für Stdlib/Nutzer-defuns) — die Äquivalenz-Suite hält sie deckungsgleich, aber jede neue
Semantik muss ZWEIMAL gebaut werden. lcc-first macht den kompilierten Pfad zum einzigen
Gerätepfad: Drift ist konstruktiv unmöglich statt nur überwacht. Der Host behält den
Treewalk als unabhängiges Orakel.

## Budget-Mathematik (Ein-Suite-ELF, llvm-nm)

- `eval_env` 3194 B — der eigentliche Evaluator: fällt bei Voll-Strip.
- `eval_list` 359 + `eval_body` 285 — fallen mit.
- `apply` 3745 B — enthält apply_prim (die C-Prims): der PRIM-Dispatch BLEIBT (CALLPRIM/
  OP_CALL-Brücke braucht ihn); nur der Treewalk-Closure-Zweig ((params . body)-Lambdas)
  fällt. Schätzung konservativ: ~0,5–1 KB davon.
- `eval_init` 980 B — bleibt (Symbol-Registrierung).
- `eval_vm_bridge` 453 B — bleibt (Träger-Vertrag).
- **Realistischer Gewinn: ~3,8–4,3 KB** (eval_env + list + body + Closure-Zweig von apply).

## Träger-Vertrag (was der lcc-Pfad vom C-Kern weiter braucht)

Aus P5/P6 (docs/lcc-device-design.md): `gensym`/`list`/`rplaca`/`rplacd`/`function-kind`/
`macroexpand-1` + OP_CALL-Miss→Prim-Dispatch. Kritischer Punkt für den Voll-Strip:
**macroexpand-1 nutzt heute eval_env-Mechanik** (rohe Args + eval_body). Am Gerät sind
Makro-Expander aber selbst lcc-kompilierte Bytecode-Objekte → Expansion = funcall auf
BCODE (vm_run), NICHT Treewalk. Die Naht existiert als Design (P4: „P6-Gerät: funcall-auf-
BCODE-Expander"), muss aber implementiert und bewiesen werden, BEVOR eval_env fallen kann.

## Meilensteine

- **M1 — lcc-first-REPL-Flag (`LISP65_LCC_FIRST_REPL`, repl.c):** REPL-Eingaben laufen durch
  `lcc-run` (Blob-Fn via Symbol-Lookup + apply) statt `eval`; Treewalk bleibt als Fallback
  (lcc-run nicht registriert → eval). Semantik ist bereits gate-bewiesen (neunter Diff: 45
  Formen lcc-first == C-Compiler). Beweis: xemu-Harness, dieselben 14 Formen. KEINE
  Profil-Änderung (ad-hoc-Build), kein Pin-Ripple. UX-Preis: ~1 s Compile-Latenz je
  REPL-Zeile (Maschinenraum-Semantik; IDE-Tippen unberührt — die IDE ist schon Bytecode).
- **M2 — Makro-Expander-Naht ✅ (Codex-geschärft: defmacro-Install OHNE eval_env ist Pflicht,
  nicht nur macroexpand-1):** `lcc-run` kompiliert den defmacro-Expander als Lambda, installiert
  ihn anonym und hängt ihn via neuem Prim `%set-macro` (LISP65_LCC_INSTALL) als T_MACRO mit
  BCODE-Payload ans Symbol; `macroexpand-1` UND der eval_env-TCO-Makropfad haben BCODE-Zweige
  (apply auf rohe Args). Gates grün: make check (16 Makro-Formen tree==lcc jetzt über den
  BCODE-Pfad), xemu 13/13 (defmacro→sofortige Nutzung direkt + in kompiliertem defun).
  Budget-Preis am Produkt: prg_file_end 0xbdf2→0xbee1, Gap 1766→1526 (Gate 1450 hält).
- **M3 — Treewalk-Strip ✅ (Flag `LISP65_TREEWALK_STRIP`, Opt-in — KEIN Pin-Flip):**
  eval_env/eval_list/eval_body/quasiquote/make_callable/env-* + Treewalk-Closure-Zweig von
  apply gegatet; `eval()` = apply auf die BCODE-Fn `lcc-run` (eval-string/load_source/P_EVAL
  erben das Routing). Braucht `LISP65_EVAL_PRIMS` im Profil (eval/eval-string waren in der
  Ein-Suite nie registriert — beim Strip Pflicht, sonst ist `(eval …)` aus kompiliertem Code
  undefined). Gate `scripts/xemu-treewalk-strip-verify.py` **ALL PASS 14/14** inkl. Codex'
  Semantik-Pins: `(eval '(defun …))` AUS kompiliertem Code = verschachteltes Kompilieren
  während vm_run (GC_ROOTS=128 hält), eval-string, defmacro, Fehler-Erholung.
  Codex-Profil: `make mvp-vm-stdlib-einsuite-strip` plus eigener Report
  `make mvp-vm-stdlib-einsuite-strip-footprint-report`; das Target baut die
  Ein-Suite-Artefakte vor dem PRG-Build explizit neu.
  **Gemessen: 34298 B / prg_file_end $a5f9, Stack-Gap 7932/1450, Bank-0-Reserve 6482,
  Symbole 460/481, externes Image [0x0000..0x924a) vor SYMPOOL_EXT_OFF $a000.** Damit liegt
  der Strip ~6,4 KB unter dem M2-Produkt-Pin ($bee1) — mehr als die Schätzung, LTO zieht
  qq/env-Maschinerie transitiv mit. Harness-Lektionen: (1) Budget-Kopplung —
  `make …-runtime-budget-check` (Default-Profil) überschreibt `stdlib-p0.*`; Ad-hoc-Builds
  muessen die passende Suite vor dem PRG-Build erzwingen.
  (2) Erwartungswert „5" matcht „lisp65>" in der Zonen-Suche — eindeutige Werte nutzen.
- **M4 — Reinvestition + Pensionierung ✅ KOMPLETT — HW-GRÜN pass 17/17 (Disk-Roundtrip
  auf echter MEGA65, Nutzer-bestätigt): (load) kompiliert Quelltext beim Laden via lcc,
  (save) Overwrite-in-place, Rückladen, Funktionsaufruf. Drei Geräte-Funde auf dem Weg (je
  Selftest-Fang): fehlende load-Kette in der Suite; Region-/Dir-Leck je Eingabe → transiente
  Mains (name=t); Wrapper-Lücken × Sparse-Dir → Abwärts-Stapel am Regions-Deckel
  (vm_ext_code_alloc_transient/pop_transient) + Regions-Deckel = SYMPOOL_EXT_OFF. crfit als
  Geräteprodukt pensioniert (two-product-workflow.md-Kopfnote). Ursprüngliches Design:** Disk (load/save)
  resident in die Ein-Suite, Bulk-Render zurueck; crfit danach aus den Geraeteprodukten
  nehmen (bleibt Host-Referenz). Codex-Profil: `make mvp-vm-stdlib-einsuite-full` plus
  `make mvp-vm-stdlib-einsuite-full-footprint-report`. Flags = M3-Strip +
  `MEGA65_F011_LOAD`, `LISP65_DISK_LIBS`, `MEGA65_F011_WRITE`, `IO_BUF_MAX=1`,
  `LISP65_SCREEN_WRITE_STRING`. Eigene Suite
  `tests/bytecode/stdlib/p0-stdlib-einsuite-full-subset.json`: entfernt den
  Bytecode-`screen-bulk-p`-Fallback, damit der native Capability-Prim sichtbar bleibt.
  Gate-Beleg: `screen-bulk-p` ist kein Blob-Function/Entry; `screen-bulk-p-native` erwartet
  `t`; `ide-render-line-at` verzweigt dann auf `CALLPRIM 12:screen-write-string`.
  **Aktuell gemessen: ca. 40070 B / prg_file_end ca. $bc80 (Limit $c0c0),
  Stack-Gap ca. 2.1 KB/1450, Bank-0-Reserve ca. 0.64 KB (hartes Minimum 0; weiches
  Target 1024 derzeit below-target), Symbole 474/500 (Headroom 26), VM-Dir 367/384,
  externes Image [0x0000..0x96b5) vor SYMPOOL_EXT_OFF $a000.** Die bytegenaue Quelle
  ist `build/bytecode/mvp-vm-stdlib-einsuite-full-footprint.txt`.
  Gate-Beleg:
  Full-Selftest pass 13/13 und Disk-Roundtrip pass 17/17 auf echter MEGA65; die formale
  Produkt-/CI-Pensionierung ist in `Makefile` und `mvp-ship` nachgezogen.

## Risiken / offene Fragen

1. **REPL-Latenz** (~1 s/Zeile): bewusster Produkt-Trade (Nutzer-Entscheid „langsamer Render"
   war analog). Option später: Fixnum/Symbol-Fastpath ohne Compile (winzig).
2. **Fehlerpfade:** lcc-Kompilierfehler müssen sauber als REPL-Fehler landen (setjmp-Pfad),
   nicht als vm_status-Leiche. M1 prüft das mit einer absichtlich kaputten Form.
3. **(eval)-Prim-Semantik:** eval zur Laufzeit IN kompiliertem Code braucht nach M3 lcc-run-
   Routing — Rekursionstiefe (lcc kompiliert während vm_run läuft) am Gerät beweisen
   (GC_ROOTS-Budget! Lektion 0ea22aa: lcc-Multi-fn braucht ~100 Slots).
4. **Koordination:** repl.c/eval.c = Lane K; Profile/Pins/Suiten = Codex. M3/M4 nur nach
   seinem Review der Flag-Architektur.
