# Geräte-FASL: compile-file am Gerät (B-Kernstück, Lane K, 2026-07-06)

**Ziel (Nutzer-Entscheid, projekt-bestandsaufnahme §4-B):** Einmal kompilierter User-/Lib-Code
wird als Fast-Load-Datei persistent (CL-.fasl-Analogon). `(compile-file "src" "fasl")` am
Gerät; Laden in Sekundenbruchteilen statt Neu-Kompilieren jeder Session.

## Fundament: alles Lädt-Seitige EXISTIERT

Das Fasl-Format ist das gepinnte Disk-Lib-Format (docs/disk-bytecode-libs-design.md):
`[u16 blob_len][u16 md_len][Code-Blob][L65M-Trailer v1]`, Einträge/Patch-Offsets
BLOB-RELATIV. Loader: `io.c`-Staging (Bank-4-Scratch `DISK_EXT_FILE`) → `ext_disk_stage`
nach Bank 5 (Region-Alloc) → `vm_load_lib_ext` (Relokation + Registrierung + Patches) —
HW-bewiesen (Stufe 2, `load-lib`). **Es fehlt nur der SCHREIB-Weg am Gerät.**

## Architektur (drei Bausteine)

1. **Emitter in Lisp** (`lib/lcc-fasl.lisp`): nimmt Top-Level-Formen, kompiliert via
   `lcc-compile-obj`, emittiert den Container byte-weise über eine Emit-Naht
   (Host-Test: Liste/Puffer; Gerät: `%disk-poke`-Analog in den Bank-4-Scratch).
2. **C-Naht `%fasl-save`** (~150 B): schreibt einen Bank-4-Scratch-Bereich (len Bytes) in
   eine vorallozierte Disk-Kette — Spiegel von `io_disk_save_named`, Quelle EXT statt T_STR
   (binärsicher; Strings als Träger scheiden aus: 1 Zelle/Byte sprengt den Heap).
3. **Vereinheitlichtes `(load "x")`**: Datei wird ohnehin nach `DISK_EXT_FILE` gestaged →
   L65M-Magic-Check entscheidet Quelle (load_source_stream, kompiliert) vs. Fasl
   (Disk-Lib-Pfad). EIN Nutzerbefehl für beide Welten.

## Design-Entscheidungen (v1)

- **Benannte Closure-Helfer statt BCODE-Immediates:** lccs `%lcc-helper`-Marker sind
  Directory-Indizes der EMIT-Session — in einer Fasl wertlos. v1 benennt Helfer
  (`%<fn>-h<j>`), legt sie als eigene Einträge ab; der Marker wird zum SYMBOL-Littab-Patch
  (OP_CLOSURE kann dir_find(sym) — Pfad existiert). Preis: Helfer-Symbole zählen gegen
  MAX_SYM (gebändigt durch A4-Headroom 86 + Fasl-Budgetierung); Gewinn: Loader unverändert.
- **Littab v1-Fläche:** FIX (immediate, gebacken), NIL/T, SYMBOL (Patch+Node). Quoted
  Listen/Strings (CONS/LIST/STRING-Nodes) = v2 — der Emitter lehnt sie v1 LAUT ab
  („fasl: literal unsupported"), kein stilles Falschbacken.
- **defmacro:** v2 (Fasl-Eintrag braucht T_MACRO-Registrierung — Loader-Erweiterung um
  ein Flag-Bit). v1 = defuns (+ Closures). Ebenfalls lauter Abort.
- **Staleness:** Header-`flags`-Feld (u16, bisher 0) trägt ein 8-Bit-Quell-Hash (Summe der
  Quell-Bytes mod 251); `(load)` warnt bei Hash-Mismatch gegen eine optionale Quelldatei
  NICHT automatisch (CBM: keine Zeitstempel) — v1 dokumentierte Nutzerkonvention,
  Hash dient Diagnose.

## Orakel/Gates (Beweisplan)

1. **Format-Orakel (stark, sofort):** der EXISTIERENDE Python-Parser
   (`_check_ext_metadata` in bytecode_p0_stdlib.py) validiert den geräte-emittierten
   Container — Python ist Producer UND unabhängiger Checker des gepinnten Formats.
2. **Verhaltens-Orakel:** Fasl aus dem Emitter → über den echten Loader laden → Funktionen
   aufrufen → Werte == Direkt-Kompilat (Host-Harness, dann xemu, dann HW-Roundtrip:
   compile-file → Reboot → load → läuft).
3. **Byte-Orakel gegen Python (Stretch):** identische Quelle durch Python-Suite-Emitter —
   byte-identisch erst sinnvoll, wenn Pool-Dedup-Reihenfolge gespiegelt ist (v2).

## Meilensteine

- **B1 — Emitter + Format-Orakel (host):** lib/lcc-fasl.lisp emittiert Container für
  defun-Korpus; Python-Parser validiert; Verhaltens-Check host-seitig.
- **B2 — Geräte-Nähte:** `%fasl-save` (C), Emit-Naht in den Bank-4-Scratch, `compile-file`
  als Lisp-Fn; unified `(load)`-Magic-Dispatch.
- **B3 — Geräte-Beweis ✅ HW-GRÜN pass 10/10 (2026-07-06, Nutzer-bestätigt):** compile-file
  → Fasl im Slot (binärsicher, Verify) → Load (C-seitig: io_fasl_find + io_disk_load_lib;
  Lisp-load-lib wartet auf Modularisierung) → (s9 6)→54 + Closure via benanntem Helfer
  mk9-h0 →42. Drei HW-Funde auf dem Weg: (1) Dir-Überlauf 402/408+align8 (Profil-Diät:
  IDE raus aus dem Beweis-Vehikel); (2) 255-B-Objektgrenze schlug STILL zu (%fasl-finish
  386 B → Kaskaden-Split; Kausalkette bis zur All-Padding-Fasl mit ehrlichem Verify-t);
  (3) Testlücke Treewalk-Host vs. BLOB-Emitter (Stage-1-Diagnose fasl-emit-scratch ohne
  Disk deckt sie jetzt). Gate-Lücken (Dir-Headroom, Objektgröße) bei Codex angefragt.
  Slot-Provisionierung via erweitertem Roundtrip-D81-Rezept (FSRC nur-defuns + FASL9).
- **B4 — IDE-Workflow:** ide-save/ide-open in die Full-Suite + Workflow-Gate
  (editieren → save → compile-file → load).
