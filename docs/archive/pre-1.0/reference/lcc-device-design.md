# P6: lcc am Gerät — Runtime-Vertrag, Nähte, Profil-Rechnung (Ein-Suite-Umstich)

**Stand 2026-07-06 (Lane K). Voraussetzung: P0–P5 komplett** — lcc (lib/lcc.lisp) kompiliert
die volle Sprachfläche inkl. Closures + Makros, ist selbst-kompilierend (Fixpunkt, 8. Gate-Diff)
und **geräte-ladbar** (255-B-Objektgrenze eingehalten; der Fixpunkt-Test erzwang die Splits).
Plan-Rahmen: docs/self-hosting-plan.md; Produkt-Kontext: docs/two-product-workflow.md.

## Zielbild (die Wiedervereinigung)

**Ein-Suite-Stufe 1 = Werkbank + lcc-Blob:** das heutige Default-Produkt (Treewalk + IDE +
Screen + eval-Naht) bekommt lcc als Bytecode in Bank 5 dazu. Damit: interaktive IDE UND
schneller kompilierter Nutzercode in EINEM Produkt — der 12-KB-C-Compiler (der Trennungsgrund)
wird nie resident. save/load (v2b) bleibt parallelstrang; der Maschinenraum (crfit) bleibt
bestehen, bis lcc am Gerät bewiesen ist — danach ist er obsolet (die Ein-Suite ersetzt beide).

## Runtime-Vertrag (von P5 empirisch kartiert)

Das Bytecode-lcc braucht zur Laufzeit — zusätzlich zu vm_run/Opcodes/CALLPRIMs — diese
Träger-Funktionen über die **OP_CALL-Miss→vm_treewalk_call-Brücke** (im Treewalk-Produkt
mit LISP65_VM BEREITS vorhanden und aktiv):

| Funktion | Träger heute | Am Gerät (Ein-Suite) |
|---|---|---|
| `list` | Treewalk-Prim / Blob-defun | Blob-Stdlib ✓ (vorhanden) |
| `gensym` | Treewalk-Prim | Brücke ✓ (Treewalk bleibt!) |
| `rplaca`/`rplacd` | Treewalk-Prims | Brücke ✓ |
| `function-kind` | Treewalk-Prim | Brücke ✓ |
| `macroexpand-1` | Treewalk-Prim, Gate `LISP65_MACROEXPAND_PRIM` | **Gate ins Profil** (~150 B) |
| `append` (qq-Lowering-Emission) | Blob-Stdlib | ✓ vorhanden |

Kern-Einsicht: weil die Ein-Suite den TREEWALK BEHÄLT (als eval/Brücke/Makro-Träger), braucht
lcc **keine neuen CALLPRIMs** — nur das macroexpand-Gate. Makro-Expander leben als T_MACRO im
Treewalk (defmacro via eval), exakt wie im Harness bewiesen.

## Die zwei neuen C-Nähte (einzige residente Kosten)

1. **`LISP65_MACROEXPAND_PRIM`** (eval.c, existiert): ~150 B.
2. **`lcc-install` (NEU, Treewalk-Prim, Gate `LISP65_LCC_INSTALL`)**: nimmt lccs Ausgabe
   (fn-Liste mit Marker-Literalen) und macht Registrierung — dieselbe Code-Object-Struktur wie
   der Harness, aber am Gerät direkt gestreamt: Header+littab+Byte-Liste → Bank-5-Region
   (vm_ext_code_alloc, der GETEILTE Allokator!) → vm_dir_add → Marker→MK_BCODE(di) → Main:
   set_sym_function bzw. BCODE-Wert zurück. Kein residenter C-Compiler und kein bc_assemble-
   Link nötig; die Prim-Logik bleibt der einzige .text-Posten.
   littab-GC: Blob-Literale wie im Harness an einer Halte-Struktur rooten (symval-Kette
   oder Region-littab-Rooting — Design wie M6-Lektion).

Danach ist ALLES Weitere Lisp: `(lcc-run form)` (Blob-Fn) orchestriert
compile-obj → lcc-install → funcall — der REPL-Swap ist eine Lisp-Entscheidung
(repl.c ruft eval; eine Blob-Hook-Fn kann lcc-first mit Treewalk-Fallback fahren).

## Blob-Weg (P6a)

lcc.lisp geht als Quelle in eine **erweiterte Suite** (Werkbank-Suite + lcc): der
Host-Python-Compiler kompiliert lccs Fläche nachweislich (Byte-Orakel!); Calls auf
Träger-Fns sind late-bound CALL-Symbole ✓. Alternativ (später, Kür): lcc kompiliert
sich selbst für den Blob (P5-Mechanik host-seitig).

## Kapazitäts-/Budget-Rechnung (Codex-Grundlage)

| Posten | Schätzung |
|---|---|
| lcc-Blob (Bank 5) | ~5–8 KB EXT — unkritisch (Bank 5 hat >40 KB frei) |
| Dir-Einträge | +~55 (lcc-defuns) → VM_DIR_MAX 250→~330 ≈ +260 B Bank-0-.bss |
| Symbole | +~55 defun-Namen +~40 littab-Syms → MAX_SYM 385→~500 ≈ +345 B |
| macroexpand-Gate | ~150 B .text |
| lcc-install-Direktemitter | ~250–400 B .text |
| **Summe Stufe 1** | **~1,2–1,4 KB** gegen die 640er-Reserve → Diät-Runde nötig, |
| | aber HALB so groß wie v2b+lcc zusammen (~2,5 KB) — deshalb Stufen! |

Diät-Kandidaten (bekannt): Rest-MAX_SYM-Feintuning, REPL_BUF, EXT_CELLS, VM_CODEBUF;
strukturell: EXT-Symtab-Tür #1 bleibt der große Hebel, falls Stufe 1 nicht reicht.

## P6c-Messstand (Codex, 2026-07-06)

`make mvp-vm-stdlib-einsuite` baut den nativen Ein-Suite-Kandidaten: Werkbank-Blob
inkl. lcc, `LISP65_LCC_INSTALL`, `LISP65_LCC_INSTALL_CLOSURES`,
`LISP65_MACROEXPAND_PRIM`, VM-Screen-Prims und langsamen VM-Screen-Prims;
C-Compiler/compile-repl, F011-Disk-Glue und C-Bulk-Renderer bleiben resident draussen.
`lcc-install` schreibt Code-Objekte direkt in die gemeinsame Bank-5-Region
(`vm_ext_code_alloc`), daher ist kein `bc_assemble`-/`compile.c`-Link mehr noetig.

Nutzer-Entscheid P6c: **IDE + lcc, langsamer Render**. Das Default-Produkt behaelt
`LISP65_SCREEN_WRITE_STRING` und damit den schnellen Bulk-Pfad. Die Ein-Suite droppt dieses
Gate, definiert `(screen-bulk-p)` im Blob/Fallback als `nil` und rendert IDE-Zeilen ueber
`screen-put-char` plus Clear-to-EOL. Derselbe IDE-Code verzweigt ueber `screen-bulk-p`: Bulk
wenn vorhanden, put-char-Fallback sonst. Syntax-Overpaint bleibt unveraendert auf
`screen-put-char`.

Aktueller Footprint (`make mvp-vm-stdlib-einsuite-footprint-report`): **status=ok**.
`prg_file_end=0xbdf2` gegen Limit `0xc0c0`, Stack-Gap 1766 B, Bank-0-Reserve 316 B.
Boot-Caps: `required_symbols=461` (`static_required_symbols=453` + gemessene Korrektur 8),
`MAX_SYM=481`, Headroom 20; `VM_CODEBUF=56`, required 52, Headroom 4. Artefakt:
356 Bytecode-Objekte, `external_image_bytes=37407`, `prg_bytes=40435`. Profil-Caps:
`HEAP_CELLS=48`, `GC_ROOTS=128`, `EXT_CELLS=384`, `VM_DIR_MAX=384`. Nach der eingebetteten
Stdlib-Registrierung richtet `vm_dir_align8` das Directory fuer die naechste sparse Code-
Region aus; bei 356 initialen Eintraegen bleiben 28 Directory-Slots fuer `lcc-install`.
Die Output-Diaet bleibt Teil dieses Profils: `write-string`, `terpri`, `princ`, `write`,
`print`, `write-line` liegen als Bytecode-Blob vor; nativ bleiben nur `write-char` und
`prin1`. Zusaetzlich traegt `LISP65_TREEWALK_STDLIB_BRIDGES` Ein-Suite-only Bridges fuer
residente Basisnamen wie Arithmetik, Vergleiche, `cons`/`car`/`cdr`, `eq`/`eql` und String-
Predikate/-Zugriffe als Bytecode. Die VM-Opcodes bleiben erhalten, aber die doppelten
Treewalk-`defprim`-Faelle verschwinden aus Bank 0. Disk-Glue (`stdlib-load`, `ide-disk`) ist
bewusst nicht in dieser Ein-Suite, weil das Profil keine F011-Prims traegt; Load/Save bleiben
separate Disk-Profile.

Bank-5-Layout P6c: Das externe Stdlib-Image liegt ab `0x050000` und belegt aktuell
`[0x0000..0x921f)`. Der Symbol-Namepool ist in diesem Profil deshalb explizit auf
`SYMPOOL_EXT_OFF=0xa000` geschoben (`[0xa000..0xc000)`); `symval` und `nameoff` leiten ihre
Offsets relativ zu `SYMPOOL_EXT_OFF` ab. Der Footprint-Report gatet diese Kollision als
`external_image_sympool_status=ok/overlap`, damit L65M-Trailer/Stringpool- und SYMPOOL-Layouts
nicht erst im xemu-Boot korrupt werden.

## Verifikationsplan

1. **P6a Host**: Suite werkbank+lcc baut; Blob-Roundtrip-Check (bestehende Gates) grün.
2. **P6b Host**: lcc-install-Prim + `(lcc-run …)`; neuer neunter Gate-Diff: REPL-Simulation
   lcc-first == C-Compiler-vm-Modus auf dem Lauf-Korpus.
3. **P6c xemu**: Ein-Suite-Kandidat bootet; (lcc-run '(defun sq...)) + (sq 5)->25,
   capturing `(defun ad (n) (lambda (x) (+ x n)))` -> `((ad 2) 40)` -> 42 und IDE parallel.
   Codex startet keine Live-xemu/etherload-Sessions; der aktuelle Re-Test liegt bei Lane K.
4. **P6d HW**: Nutzer-Session; danach Umstich-Entscheidung (Maschinenraum-Zukunft, crfit-
   Gate bleibt bis dahin als C-Compiler-Referenz für die Orakel!).

## Bekannte P6c-Follow-ups

`lcc-install` kann im aktuellen Ein-Suite-Produkt Single-Fn-Defuns, capture-freie Helper-Fns
und capturing Closure-Factories installieren. Das Produktprofil aktiviert dafuer
`LISP65_LCC_INSTALL_CLOSURES`; der Host-Gate `make lcc-install-device-smoke` pinnt `sq`,
capture-freies `mk` und capturing `ad`. Der Closure-Zusatz war zunaechst rot
(`prg_file_end` oberhalb `0xc0c0`); die aktuelle Bank-0-Diaet verschiebt doppelte
Treewalk-Stdlib-Prims in Ein-Suite-Bytecode-Bridges und macht das Profil wieder gruen.

## Nicht-Ziele Stufe 1
&rest in lcc (Stdlib kommt aus dem Host-Blob), nested-quasiquote, save/load (v2b-Strang),
Treewalk-Entfernung (er ist Träger!), Maschinenraum-Abschaltung (erst nach HW-Beweis).
