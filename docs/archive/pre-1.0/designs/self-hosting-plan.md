# Self-Hosting: der Compiler in Lisp (Wiedervereinigungs-Tür #3)

**Start 2026-07-05 (Nutzer-Auftrag; aus docs/post-mvp-vision.md Strang A3 + docs/two-product-workflow.md).**
Ziel: den geräteseitigen Bytecode-Compiler (heute src/compile.c + compile_repl.c, ~12 KB Bank-0-
Fußabdruck) als **Lisp-Programm** neu schreiben, host-crosskompiliert als **Bytecode in Bank 5**
ausliefern (~0 Bank-0-Kosten) — und damit Werkbank + Compiler wieder in EINEM Produkt vereinen.

## Der Gewinn (Kurzfassung, Details in der Diskussion 2026-07-05)
1. **Ein-Suite zurück**: IDE+Farben+Buffer+save/open+schneller Compiler in einem Produkt; die
   Zwei-Produkte-Trennung existiert NUR wegen der 12 KB C-Compiler in Bank 0.
2. **Bank-0-Wand strukturell entlastet**: künftige Compiler-Features = Bank-5-Bytes.
3. **Makro-Lücke (M5/M4) löst sich**: der Compiler läuft auf der VM → Expander aufrufen ist trivial.
4. **Selbst-verbesserbares System**: Compiler in der eigenen IDE editierbar/sicherbar/ladbar.
5. **Tor zu Strang A4** (45GS02-Native-Backend).

## Ehrliche Kosten/Risiken
- Volle Codegen-Fläche neu (M1–M7, Closures 3-phasig, immediate-Lambda) im Dialekt (Listen,
  15-Bit-Fixnums, keine Arrays) — mehrwöchig, phasenweise.
- Bootstrap: Host-Python-Compiler muss den Lisp-Compiler kompilieren (Fläche reicht voraussichtlich —
  er trägt heute Stdlib+IDE).
- Compile-Tempo Gerät: Kaltpfad (load/defun), Bytecode >> Treewalk — akzeptabel.

## Das dreifache Orakel (warum das Risiko klein ist)
Der Lisp-Compiler (Arbeitsname **lcc**) wird gegen DREI existierende Wahrheiten entwickelt:
1. **Byte-Orakel**: emittierter Bytecode == Host-Python-Compiler (bytecode_p0_compiler.py),
   byte-exakt je Form (compile-smoke-Muster). Gleiche ABI (docs/bytecode-abi.md, gepinnt).
2. **Semantik-Orakel**: Ergebnis-Gleichheit via Äquivalenz-Suite (tests/equivalence/forms.lisp,
   93 Formen, make-check-Gate) — lcc-kompilierte Formen laufen auf derselben Host-VM.
3. **C-Referenz**: src/compile.c bleibt bis zum Umstich die Produktions-Referenz (und danach
   Fallback-Gate, bis lcc auf HW bewiesen ist).

## Phasen
- **P0 Spike (jetzt)**: lib/lcc.lisp kompiliert AUSDRÜCKE (Literale, Arithmetik/Vergleiche,
  if/progn, quote) zu Byte-LISTEN; Host-Treiber vergleicht byte-exakt gegen den Python-Compiler.
  Beweist: Codegen im Dialekt ist praktikabel (Emission, Branch-Patching mit Listen).
- **P1 Bindungen**: let/let*/lokales setq (Slot-Vergabe), Aufrufe (CALL/CALLPRIM-Tabelle).
- **P2 defun + Funktionsobjekte**: bc_assemble-Äquivalent (Header+littab+Code als Byte-Liste),
  Registrierungs-Naht (auf dem Gerät: %region-put-artige Prims — Naht-Design in P2).
- **P3 Closures** (3 Phasen wie im C-Compiler; OP_CLOSURE/UPVAL/SETUPVAL).
- **P4 Makros**: defmacro/quasiquote — der strukturelle Bonus des Self-Hostings.
- **P5 Selbst-Kompilation**: lcc kompiliert lcc (Fixpunkt-Test: Output byte-identisch).
- **P6 Geräte-Naht + Umstich**: REPL-Swap auf lcc (Bytecode), C-Compiler raus, Ein-Suite-Profil.

## Nicht-Ziele des Spikes
Optimierung, Native-Backend, Geräte-Integration (P6-Thema), Performance-Tuning.

## Budget-/Kapazitäts-Notizen
lcc als Blob-Erweiterung: Dir-Slots + Symbole (Bank-5-seitig via EXT-Symtab-Anteile) — die
VM_DIR_MAX/MAX_SYM-Achsen wachsen; Ein-Suite-Profil rechnet OHNE die 12 KB C-Compiler, dafür
mit lcc-Blob (~geschätzt 8–15 KB Bank 5) + Compile-Zeit-Heap (EXT, transient je Funktion).
