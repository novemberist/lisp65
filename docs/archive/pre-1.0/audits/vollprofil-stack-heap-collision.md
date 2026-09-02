# Vollprofil-„GC-Bug" = Soft-Stack-Überlauf in den Lisp-Heap (ROOT CAUSE)

**Stand:** 2026-07-05 (Claude/Lane K). Abschluss der mehrtägigen Bug-Jagd.
**Verdikt: Es war nie ein GC- oder DMA-Bug. Der C-Soft-Stack überschreibt `heap[]`.**

## Symptom (Wiederholung)
Vollprofil (crfull: Compiler-REPL + eingebetteter 232-Fn-Stdlib-Blob) auf echter MEGA65:
`(+ 1 2)`→3 ✓, `(length '(9 9 9 9))`→4 ✓ (Stdlib aus Blob!), aber `(reverse '(1 2 3))` → endlose
Klammern-Flut (zyklische Struktur) und `(length '(1 ×16))` → 0. Lean-Profil: **alles grün**.

## Die Beweiskette (xemu-Harness, `scripts/xemu-crfull-verify.py`)
1. **GC_STRESS-Build** (GC bei jedem alloc): schon `(+ 1 2)` scheitert, `gc_badobj` springt 0 → 56+.
2. **Phasen-Split von `gc_badobj`**: `gc_bad_roots=0`, `gc_bad_syms=0`, **`gc_bad_cells=3492`** —
   die Müll-Pointer kommen ausschließlich aus der Zell-Traversierung, nicht aus Roots/Symbolen.
3. **Hot-vs-EXT-Split**: `gc_bad_ext=0` (DMA-Lesepfade **sauber**!), Müll nur in **Hot-Zellen**
   (Bank-0-`heap[]`, gar kein DMA) → **kein DMA-Bug**.
4. **Hot-Heap-Dump** (der Durchbruch): Zellen 1–19 = intakte Freelist-Kette (a = nächster Index);
   ab Zelle 20 steht **ASCII-Text** in type/a/b (Typen 52='4', 111='o', 116='t' … = Zeichen).
5. **Symbolkarte**: `heap` endet @0xcfe6, direkt darüber `__stack` @0xd000 — nur **26 Byte** Reserve.
   Der C-Soft-Stack wächst von 0xd000 **nach unten** und klobbert die **oberen** Heap-Zellen
   (die stack-nahen) mit Stack-Frames (lokale Puffer = der ASCII-Text). Untere Zellen (stack-fern)
   bleiben heil. Exaktes Muster eines nach unten wachsenden Stacks.
6. **A/B-Bestätigung**: `.bss` verkleinern (EXT_CELLS 3072→512→256 ⇒ `heap[]` 300+ B tiefer ⇒
   329–369 B Reserve) heilt die 16er-Liste + die meisten Tests. Der **verbleibende Fehler wandert**
   je nach Layout auf einen anderen Test (sq ↔ funcall) — die Signatur einer Layout-abhängigen
   Kollision, **kein** Logik-Bug einer einzelnen Operation.

## Warum Lean grün, Vollprofil rot
Identische GC/VM/Compiler-Logik. Der Unterschied ist rein **`.bss`-Größe**: Lean (kein Blob,
kleineres MAX_SYM/VM_DIR_MAX) → `heap[]` sitzt tiefer → genug Stack-Reserve. Vollprofil (Blob-
Registrierung + 330 Symbole + 242 Dir-Slots + CREPL-Puffer) füllt `.bss` bis ~0xcfe6 → 26 B Reserve
→ jede rekursive Operation (rekursive Stdlib-Fn in `vm_run`, Compiler-Rekursion) überläuft in `heap[]`.
Der GC ist **unschuldig** — er scannt nur den vom Stack zerschossenen Heap und findet Müll-Pointer.

Das erklärt ALLES rückwirkend: „reverse→Zyklus" (Stack klobbert eine Cons-Zelle), „length→0"
(Stack löscht die Listen-Struktur vor/während Compile), die frühere `(sq 5)`→TYPEERROR auf HW,
und warum der Host-Repro IMMER grün war (Host: riesiger nativer Stack, kein 0xd000-Deckel).

## Fix-Plan
**Der Kern: der Vollprofil-Soft-Stack braucht garantierte Reserve über `heap[]`.**

- **F1 — Stack-Guard (Korrektheit, SOFORT):** an den rekursiven Einstiegen (`vm_run`, `compile_expr`,
  `read_expr`) die Stack-Tiefe prüfen und bei Annäherung an `heap`-Top sauber mit `VM_STACKOVER`
  abbrechen statt still zu korrumpieren. Entweder llvm-mos-Soft-Stack-Pointer (Zero-Page) gegen eine
  Grenze, oder ein C-Rekursionstiefen-Zähler (portabler, grobkörniger). Macht aus stiller Korruption
  einen ehrlichen Fehler.
- **F2 — Bank-0-Headroom als Budget-Posten (Kapazität):** ~512–1024 B `.bss` freimachen ⇒ Stack-
  Reserve. Direkt gekoppelt an die Bank-0-Budget-Arbeit (`docs/bank0-full-suite-strategy.md`). Hebel:
  marks-Bitmap (EXT_CELLS), CREPL-Puffer, MAX_SYM/Dir-Arrays, oder Hebel A (Boot-Overlay). Das erklärt
  auch, warum „linkt" bisher irreführend war: der Linker sieht die Stack-Kollision nicht.
- **F3 — Linker-Deckel (strukturell, Lane T/Codex):** die RAM-Region für `.bss` bei z. B. 0xce00
  statt 0xd000 kappen ⇒ ein zu großes `.bss` wird ein **Build-Fehler** statt stiller Laufzeit-Korruption.
  Verwandelt den Budget-Zwang in eine laute Gate.
- **F4 — Rekursionstiefe senken (langfristig):** `vm_run`-Verschachtelung (rekursive Lisp-Calls) auf
  einen expliziten Stack/Trampolin umstellen ⇒ Stack-Verbrauch unabhängig von der Datentiefe. Großer
  VM-Umbau; erst nötig, wenn F1+F2 die realen Fälle nicht abdecken.

**Empfehlung:** F1 (Guard) + F2 (Headroom) zusammen = robust und schnell. F3 als Gate hinterher.
Werkzeug steht: `scripts/xemu-crfull-verify.py` (Blob+PRG-Upload, Matrix-Tasten, Hot-Heap-Dump,
Freelist-Walk, `.bss`-Symbol-Introspektion) reproduziert + misst autonom in xemu.

## F1 ERLEDIGT + F2 BESTÄTIGT (2026-07-05, Commit 5a1542e + Folge)
**F1 (Guard) gebaut + validiert:** `lisp_stack_low()` liest den llvm-mos Soft-Stack-Pointer
`__rc0`/`__rc1` (ZP $02) — NICHT `&local` (das landet in ZP-Pseudoregistern, feuert immer). `vm_run`
bricht vor jedem Frame mit `VM_STACKOVER` ab, wenn der SP heap-Top+24 erreicht. Gegatet unter
`-DLISP65_STACK_GUARD`, Default byte-identisch (39489). Lean (2738 B Reserve): kein Fehlalarm.

**crfull `.bss`-Verbraucher (gemessen, Bank 0):** `cf_code` 816 (CREPL NF×CODESZ — im Vollprofil
fast reiner Overhead, da Stdlib aus dem Blob läuft, der Compiler nur User-Input verarbeitet), `symfn`
660 (MAX_SYM×2), `marks` 392 (Bitmap MAX_CELLS), `namelen` 330, `heap` 300, `cc_lvl` 272,
`gc_rootstack` 256 (GC_ROOTS×2), `dir_len` 242, `asmbuf` 165, `cf` 144, `cf_lit` 132, `cc_scope` 96.

**F2 REZEPT (xemu ALL PASS, 707 B Reserve):** `CREPL_NF=5 CREPL_CODESZ=88` (cf_code 816→440),
`EXT_CELLS=2048` (marks 392→264), `GC_ROOTS=100` (rootstack 256→200) + Guard. Das **komplette
Vollprofil läuft**: `(+ 1 2)`→3, `(length '(9 9 9 9))`→4 (Stdlib aus Blob!), `(length '(1×16))`→16
(DER Bug!), `(sq 5)`→25, `(funcall (adder 10) 5)`→15 (Closure). Datenpunkte: 329 B Reserve reicht für
length-16, ~450 B für sq, **707 B trägt die volle Testsuite**. Build: Scratchpad `fitbuild.sh` →
`build/lisp65-crfit.prg`. HW-Deploy ausstehend.

**➡️ Codex/Lane T (F3):** dieses Rezept als offizielles Makefile-Vollprofil-Target formalisieren +
Linker-`.bss`-Deckel bei ~0xcd00 setzen (Stack-Reserve als Build-Gate statt stiller Laufzeit-Falle).

**Codex-Nachzug (Lane T, 2026-07-05):** `make mvp-vm-stdlib-crfit` formalisiert das HW-grüne
F2-Rezept als eigenes Vollprofil-Target (`MAX_SYM=330`, `VM_DIR_MAX=242`, `GC_ROOTS=100`,
`EXT_CELLS=2048`, `CREPL_NF=5`, `CREPL_CODESZ=88`, `LISP65_STACK_GUARD`). Das neue
`scripts/lisp65-mega65-bss-cap.ld` setzt per Linker-`ASSERT` den `.bss`/Heap-Deckel
(`M65VMSTDLIB_BSS_CAP`, Default `0xcd40`); aktueller Build: `__heap_start=0xcd3e`,
Stack-Gap 706 B, `mvp-vm-stdlib-crfit-footprint-report` status=ok. Seit M4/einsuite-full bleibt
dieses Target als Referenz baubar, ist aber nicht mehr im Produkt-`make check` verdrahtet.
Hebel A bleibt separat: ein echtes custom llvm-mos-Linkerskript, das `.lisp65_boot`
aus der Default-`.text`-Zuordnung herausnimmt, ist noch offen.

## IDE-Capstone-Scope + Hebel A (2026-07-05, Nutzer-Wahl: Hebel A)
**Ziel:** volle Suite = Geräte-Compiler + volle Stdlib + IDE + Screen-Prims, als EIN System auf HW.

**Feasibility vermessen (alles einzeln bezahlbar, nur die Summe sprengt Bank 0):**
- IDE kompiliert zu reinem P0-Bytecode: 96 Fns, 5092 code_bytes, 15 Testfälle grün. Die `%ide-*` sind
  Lisp-`defun`s in `ide-ui.lisp`, KEINE C-Primitive. Echte C-Deps: nur `screen-put-char/size/write-string` (im Kernel vorhanden).
- IDE-Kapazität (VM_DIR_MAX 242→360, MAX_SYM 330→400): linkt, **339 B Reserve** ✅
- Disk-Laden (DISK_LIBS+F011): **+2456 B** ❌ → stattdessen **IDE in den externen Blob EINBETTEN**
  (kombinierte stdlib+IDE-Suite; Tooling da: `BYTECODE_IDE_LIB_SUITE`, `resident_suite`-Mechanik).
- Screen-Prims (VM_SCREEN_PRIMS+SCREEN_WRITE_STRING): **+1678 B .text**.
- **Summe (Compiler+IDE+Stdlib+Screen-Prims): 1339 B über** → braucht Hebel A.

**Hebel A = Boot-Overlay: ~3 KB BOOTFN-Code nach dem Boot vom Soft-Stack überlagern lassen.**
Reclaimbar: `md_lit_node` 1388 + `vm_load_embedded_stdlib` 1188 + `vm_load_ext_metadata` + `md_idx/read/name`
≈ 3 KB — deckt 1339 B + Reserve. `scripts/lisp65-mega65-boot-overlay.ld` existiert (legt `.lisp65_boot`
hinter `.noinit`, 512 B Boot-Stack-Reserve).
**PRÄZISER BLOCKER (2026-07-05):** (1) `M65VMSTDLIB_LDFLAGS` ist LEER → das Overlay-Skript wird nie an
den Linker gegeben. (2) Selbst mit `-Wl,-T,...ld`: das Default-llvm-mos-Skript **merged `.lisp65_boot`
in `.text`** (crfit hat KEINE eigene `.lisp65_boot`-Section) → der Overlay-`KEEP(*(.lisp65_boot))`
findet nichts zum Umlagern, `.bss` schrumpft nicht. **Nötig: vollständiges custom-Linkerskript (auf
Basis des Default), das `.lisp65_boot` aus `.text` AUSSCHLIESST und in die Overlay-Region legt** — reines
`INSERT AFTER` reicht nicht (first-match `.text` greift zuerst). Toolchain-R&D → Codex/Lane T (LDFLAGS+Linker).
**Boot-Risiko:** `md_lit_node` REKURSIERT über verschachtelte Stdlib-Literale — der Boot-Stack darf die
512-B-Reserve nicht sprengen (sonst überschreibt der Boot seinen EIGENEN Overlay-Code). Mit F1-Guard sichtbar.

**Restweg nach Hebel A:** (1) kombinierte stdlib+IDE-Blob-Suite bauen, (2) crfit+dir360/sym400+Screen-Prims+
Overlay → linkt mit Reserve, (3) Blob+PRG deployen, `(ide)` bootet, (4) xemu → HW.


## Disk: DISK_LIBS vs. F011 (Klarstellung 2026-07-05)
Zwei GETRENNTE Mechanismen, nicht verwechseln:
- **DISK_LIBS** (`load-lib`/`vm_load_lib_ext`): laedt BYTECODE-LIBS von Disk. Kostet ~1735 B. **Nicht
  noetig**, da die IDE eingebettet ist (im Blob). DAS wurde "gedroppt" — es geht nichts verloren.
- **F011** (`%disk-read-sector/-byte/-load-file`): roher Disk-Zugriff fuer QUELLDATEIEN (.lisp
  oeffnen/speichern). Kostet nur ~721 B (crfit+F011 = 14 B ueber). Separat + billig.
Die IDE hat AKTUELL kein Datei-Oeffnen/Speichern (keine File-Ops in ide-*.lisp; load/save/%disk-load-file
nicht im Blob). "Dateien in die IDE laden" = Zukunfts-Feature ueber F011, NICHT ueber das gedroppte
DISK_LIBS. SAVE (Disk-WRITE) ist projektweit noch unimplementiert (nur Lesen ist HW-gruen).
**Fuers Hebel-A-Budget:** nach ~3 KB reclaim passt Screen-Prims (~1678) + F011 (~721) = ~2399 B < 3 KB
-> interaktive IDE MIT Datei-Laden budgetaer drin (SAVE bleibt separates Feature).
