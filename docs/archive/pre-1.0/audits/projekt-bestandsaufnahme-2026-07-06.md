# lisp65 — Bestandsaufnahme (2026-07-06, nach Abschluss der Ein-Suite-Konvergenz)

**Anlass:** M1–M4 der Konvergenz sind abgeschlossen, `einsuite-full` ist als DAS Geräteprodukt
gepinnt und hardware-bewiesen (pass 17/17 inkl. Disk-Roundtrip). Ehrliches Verdikt: wo wir
stehen, was existiert, was offen ist, was als Nächstes lohnt.

## 1. Was lisp65 heute IST

**Ein selbst-gehostetes Lisp-System für den MEGA65** — ein Produkt, `make mvp-ship`:
PRG ~40 KB (Bank 0) + externes Bytecode-Image ~38 KB (Bank 5, etherload `-b 0x050000`).

- **Compiler = lcc** (`lib/lcc.lisp`, ~60 Funktionen in lisp65 selbst geschrieben): kompiliert
  am Gerät jede Eingabe zu Bytecode. Selbst-kompilierend (P5-Fixpunkt: lcc(lcc) == lcc).
  Der Treewalk ist vom Gerät gestrippt — lcc ist der einzige Evaluator (`eval`, `eval-string`,
  `load` routen alle durch ihn). ~9 KB Bank-0-.text wurden so frei und reinvestiert.
- **Sprachumfang am Gerät:** defun/lambda mit capturing closures (OP_CLOSURE/UPVAL/SETUPVAL),
  defmacro mit Bytecode-Expandern, quasiquote (einstufig), let/let*/setq, cond/and/or/when/
  unless, TCO in Tail-Position, variadische Arithmetik/Vergleichsketten (Bridges), Strings
  (Kern), verschachteltes `eval` (kompilieren WÄHREND vm_run läuft).
- **IDE resident:** `(ide)` ⇄ REPL, Multi-Buffer, Syntax-Highlighting, Auto-Indent,
  O(1)-Insert (Aktive-Zeilen-Cache), nativer Bulk-Render, Statuszeile. Editor-Kern wächst
  in Lisp (Blob), nicht in C.
- **Disk resident:** `(load "name")` liest CBM-Ketten via F011 und KOMPILIERT Quelltext beim
  Laden; `(save "name" str)` schreibt Overwrite-in-place mit Readback-Verify in vorallozierte
  Slots; dazu Regel-B-Bytecode-Libs (`load-lib`). Werkbank→Disk→Maschinenraum-Loop komplett.
- **Speichermodell:** Bank 0 = Kern (~40 KB, Deckel $c0c0/BSS $cd40), Bank 4 = EXT-Heap
  (Fixpoint-Sweep-GC), Bank 5 = Code-Image [0..~$96b9) + lcc-Region (aufwärts) + transienter
  Main-Stapel (abwärts vom Deckel $a000) + Symbol-Namepool [$a000..$c000) + SYMVAL/NAMEOFF-EXT.

**Finale Pins (Ship 36c1197):** `status=ok`, `prg_file_end=$bc85` (Limit $c0c0),
Stack-Gap 2090/1450, Symbole 474/500 (Wand ~580), VM-Dir ~377/384.

## 2. Die Beweis-Infrastruktur (das eigentliche Kapital)

- **Äquivalenz-Suite** (`make check`, ~10 Gate-Diffs): Treewalk == C-Compiler == lcc ==
  Python-Referenz, Byte-Orakel + Lauf-Orakel + Fixpunkt + Makro-Korpus + lcc-first-REPL-Diff.
  Drift ist konstruktiv unmöglich am Gerät (EIN Evaluator) und messbar am Host (drei Engines).
- **Budget-Gates:** Footprint-Report je Profil (prg_end/stack-gap/Bank-0-Reserve/Symbol- und
  Dir-Headroom, external-image×sympool-Kollision), Runtime-Budget, boot-symcount (ehrliche
  C-Symbol-Zählung), Geräte-Symbol-Audit (`--symbol-audit`).
- **xemu-Harnesse** (autonom, Monitor-Socket + $D615): `xemu-einsuite-verify` (Wrapper-Formen
  + IDE), `xemu-treewalk-strip-verify` (nackte Formen, eval-Verschachtelung, Fehlerpfad),
  Selftest-Gegenproben. Scroll-fest, Blob-gekoppelt.
- **HW-Selftests** (etherload, visuelles Verdikt + `[abort: …]`-Diagnose):
  `hw-smoke-einsuite.sh` (Basis/--strip/--full) und `hw-disk-roundtrip.sh` (c1541-D81 +
  mega65_ftp + mount). Vier ship-fähige Rezepte, alle heute HW-grün gefahren.
- **Host-Referenzen:** `src/compile.c` (C-Compiler) + crfit-Profil bleiben baubar als
  Referenz-Vehikel; Python-Compiler baut die Blobs (Cross-Compilation).

## 3. Ehrliche offene Kanten

1. **REPL-Latenz** ~1 s/Zeile (jede Eingabe kompiliert). Bewusster Trade; Fixnum/Symbol-
   Fastpath wäre billig. IDE-Tippen ist NICHT betroffen.
2. **lcc-Region klein:** Fenster Image-Ende→$a000 ≈ 2,3 KB für persistente Nutzer-defuns
   einer Session (~30–60 defuns) + Disk-Lib-Staging. **Trailer-Reclaim (~22 KB)** ist die
   bekannte nächste Reserve (Trailer ist boot-only), braucht Allokator-Umbau mit Codex.
3. **VM-Dir-Headroom** ~7 freie Slots nach Boot (377/384) — Session-Deckel für defuns;
   VM_DIR_MAX-Anhebung kostet .bss (~2 B/Slot), Gap 2090 hat Luft.
4. **save legt keine Dateien an** (Overwrite-in-place in vorallozierte Ketten, kein BAM) —
   für echte Projekte braucht es Slot-Provisionierung (u01-Tooling, offen bei Codex) oder BAM.
5. **Bewusste Mini-Lecks:** Ausdruck, der defuns installiert, lässt sein transientes Main
   stehen; gensym-Symbole werden nie ge-GC't (Watermark-Idee dokumentiert).
6. **xemu-F011 defekt** → Disk nur auf echter HW testbar (Roundtrip-Rezept existiert).
7. **Sprachlücken:** nested quasiquote (P4-Rest), &rest in lcc, CL-Subset dünn (format,
   Sequenzen teils nur Host/cl-compat), Fehlermeldungen knapp ("***" ohne Kontext im Produkt).
8. **Symbol-Decke** 474/500 (Wand ~580): Wachstum der Stdlib braucht bald die
   EXT-Symboltabellen-Vollstufe (docs/symbol-table-ext-design.md).

## 4. Sinnvolle nächste Schritte (Empfehlung in dieser Reihenfolge)

- **A. Konsolidierung der Session-Kapazität (kurz, hoher Hebel):** Trailer-Reclaim nach Boot
  (~22 KB Region statt 2,3), VM_DIR-Headroom anheben, REPL-Fastpath für Atome. Danach sind
  lange Live-Sessions realistisch statt nur Selftests.
- **B. Der Produkt-Workflow als Gate (inkl. FASL-Modell, Nutzer-Entscheid 2026-07-06):**
  eine ECHTE IDE-Session auf dem Full-Produkt am Gerät — editieren → `(ide-save)` → `(load)`
  → laufen — als HW-Workflow-Selftest; ide-disk.lisp wartet darauf (+ Slot-Provisionierung).
  **Kernstück: `compile-file` am Gerät = L65M-Emitter in Lisp** (lcc-Objektlisten →
  Container-Bytes → binärsicherer Disk-Write): einmal kompilierter User-/Lib-Code wird als
  Fast-Load-Datei persistent (CL-.fasl-Analogon; Ladeseite `vm_load_lib_ext` EXISTIERT).
  Eleganz-Ziel: EIN `(load "x")`, das am L65M-Magic Quelle vs. Fasl erkennt. Neues Orakel:
  Geräte-Fasl == Host-Fasl (Python-Emitter) byte-identisch. Staleness: Quell-Hash-Byte im
  Trailer oder Nutzerkonvention (CBM hat keine Zeitstempel). VORAUSSETZUNG: A (Fasl-Staging
  frisst Region — 2,3 KB tragen genau eine kleine Lib).
- **C. Sprache in Lisp wachsen lassen:** nested-qq, &rest, format/Sequenzen als ladbare Libs
  — kostet dank lcc + Disk-Libs kein Bank-0 mehr. Feature-Gate-Disziplin gilt weiter.
- **D. Release-Schnitt:** `mvp-ship` + README/Anleitung (Remote-Modus, D81-Vorbereitung,
  Erste-Schritte-Session) → teilbarer Stand für Dritte.
- Später/optional: BAM-echtes save, GC-/Compile-Perf, Symbol-EXT-Vollstufe, lisp65-Ideen
  aus post-mvp-vision (Overlays, größere Programme via Trailer-Reclaim).

**Kurzfazit:** Die Vision „Lisp-System + Compiler + IDE in einem, selbst-gehostet, auf echter
Hardware" ist erreicht und beweisgesichert. Was fehlt, ist keine Architektur mehr, sondern
Alltagstauglichkeit: Session-Kapazität (A) und der geschlossene Editier-Workflow (B).
