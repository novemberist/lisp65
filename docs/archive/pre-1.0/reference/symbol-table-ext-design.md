# Symboltabelle -> EXT (Skalierung der Symbol-Namensgrenzen)

Stand: 2026-07-09. Status: **teilweise umgesetzt**.
`symval`/`nameoff`-Auslagerung existieren bereits als opt-in Pfade; der
Workbench-MVP-Pin nutzt zusaetzlich `LISP65_SYMFN_EXT`, `NAMEPOOL=9536` und
`SYMPOOL_EXT_OFF=0xc9e0`, um IDE-On-Demand bei `MAX_SYM=720` zu ermoeglichen.
Dieses Dokument bleibt die
Designnotiz fuer die vollstaendige Skalierung, ist aber nicht mehr "noch nicht
umgesetzt".
Auslöser: der Modeline-Budget-Zähler zeigte, wie eng das Symbol-Budget ist. Ein Build-only-Versuch
mit MAX_SYM 330→600 zeigte, dass die Symbol-Arrays selbst die Bank-0-Wand treffen: das PRG baut,
fällt aber durch das harte Footprint-Gate (`stack_gap=334/1450`). Selbst MAX_SYM=430 mit gekürztem
Produktprofil hat nur `bank0_reserve=34/640`. Das Hauptprofil bleibt deshalb vorerst bei
MAX_SYM=330; dies hier ist der strukturelle Weg für WIRKLICH große Programme.

## Was zählt (und was nicht)
`(symbol-count)` = distinkte **globale Namen**: `defun`-Funktionen + globale Variablen + gequotete
Symbole (`'foo`). **NICHT** dabei: lokale Variablen / Funktionsargumente (die sind lexikalische
Frame-Slots, `LOADL`/`STOREL`) und Programm**daten** (Heap-Zellen). Der Budget-Druck ist also
kleiner, als „hunderte Variablen" klingt — aber für große Programme real.

## Die ZWEI Bank-0-Grenzen (beide müssen fallen)
1. **Symbol-Arrays** `nameoff[MAX_SYM]` + `symval[MAX_SYM]` + `symfn[MAX_SYM]` = **6 B/Symbol**,
   Bank 0. Build-only-Decke gemessen: **MAX_SYM ~640** (900 überläuft Bank-0-BSS um 1504 B);
   ship-gate-grün ist das ohne Auslagerung deutlich früher nicht.
2. **Namepool-Kapazitaet:** mit `LISP65_NAMEOFF_EXT` und `SYMPOOL_EXT` ist der
   Workbench-MVP inzwischen auf `NAMEPOOL=9536` gepinnt. Der HW-Test zeigte,
   dass 8 KiB Namepool trotz `symbol-count=616/640` noch mit `too many symbols`
   scheitern kann; die Namensgrenze ist also ein reales zweites Budget neben
   `MAX_SYM`.

→ Effektive Decke nach Array-Auslagerung ist heute nicht nur `MAX_SYM`, sondern
das Produkt aus Symbolslots, Namepool und Directory-Slots. Der aktuelle
Workbench-Pin (`MAX_SYM=720`, `VM_DIR_MAX=552`, `NAMEPOOL=9536`,
`SYMPOOL_EXT_OFF=0xc9e0`) ist eine MVP-Bruecke, kein dauerhaftes
Skalierungsmodell fuer grosse Programme.

Der 2026-07-09-Workbench-Nachzug nutzt einen balancierten
Code/Namepool-/Diskfenster-Trade: `SYMPOOL_EXT_OFF` liegt bei `$c9e0`,
`NAMEPOOL` bei 9536. Damit bleibt das externe Code-/Metadatenfenster am
Load-Peak gerade gross genug fuer die ladbare IDE-Lib
(`ext_code_peak_headroom=386`); nach Trailer-Reclaim bleiben 23396 B. Der
kombinierte Stdlib+IDE-Lib-Load hat wieder Namepool-Reserve
(`runtime_namepool=9403/9536`). `SYMPOOL_EXT_OFF +
NAMEPOOL` bleibt weiter `$ef20`; `symval`, `nameoff` und `symfn` behalten also
ihre Lage und das Gesamt-Layout endet weiterhin exakt an der Bank-5-Grenze.

## Ansatz (bewährtes Muster wiederverwenden)
Genau wie `SYMPOOL_EXT` (Namepool) und `LISP65_EXT_HEAP` (Heap): heißer Bank-0-Teil + EXT-Überlauf,
DMA nur im kalten Zweig. Zwei Teile:

**Teil A — Arrays nach EXT.** `symval`/`symfn`/`nameoff` = je 2 B/Symbol, Bank 0.

**PERF-ANALYSE (2026-07-04, am Code verifiziert — korrigiert eine frühere Fehlannahme):**
- **`symfn` HEISS — im Workbench-MVP trotzdem nach EXT.** Frühere Annahme „CALLs laufen übers
  Directory, nicht symfn" war FALSCH: `dir_find` (vm.c:123) ruft `sym_function` → liest `symfn`.
  Jeder Bytecode-CALL löst so auf. Der MVP-Pin akzeptiert diesen Hotpath-DMA-Trade-off, weil die
  IDE-Disk-Lib sonst an Symbol-Headroom scheitert. Aktuelle Implementierung: EXT-Speicher plus
  Bank-0-Pointer-Bitmap fuer GC; kein MRU-/Slot-Cache, da Cache-Varianten das PRG-Ende-Gate
  sprengten.
- **`symval` KALT für Bytecode — ERSTER Schritt.** vm.c liest `symval` NICHT; nur der Treewalk-
  Interpreter (eval.c:585, selten — Stdlib/Editor sind Bytecode) und der GC (mem.c:317, periodisch)
  lesen es. → sicher nach EXT. GC-Kosten mildern: nur GEBUNDENE Symbole markieren (Bank-0-`symbnd`-
  Bitmap prüfen, dann nur die wenigen globalen Werte per DMA lesen).
- **`nameoff` HEISS beim Internen — später, mit Split.** Der Intern-Scan liest `nameoff[i]` O(nsym)
  (via `NLEN4`-Vorfilter). Bei EXT: Längen-Nibble in ein separates Bank-0-`uint8`-Array
  (Vorfilter DMA-frei) + nur den 16-Bit-Offset nach EXT (löst zugleich Teil B). Intern bleibt schnell.

**SYMFN_EXT-Exposure-Gate (2026-07-08):** `make workbench-symfn-dynamic-report`
zaehlt im Host-P0-Trace alle dynamischen Bytecode-`CALL`/`TAILCALL`-Operationen;
im Workbench-Profil entspricht jede davon einem `sym_function(target)`-Lookup
aus EXT-RAM. Aktueller Pin: 15 IDE-/Compiler-Szenarien, 127961 Host-
Instruktionen, 8939 dynamische `symfn`-Aufloesungen, 145 Ziele, 293 Call-Sites.
Die Messung ist **nicht zyklusgenau** und modelliert keine DMA-Timings, schuetzt
aber gegen unbemerkte Lookup-Explosionen. Dominant sind kalte Renderpfade
(`ide-render-cold-short` 2469, `ide-render-cold-25-lines` 2596); interaktive
Einzelschritte sind deutlich kleiner (`ide-step-self-insert` 31,
`ide-step-delete-cached` 15), Compiler-Szenarien liegen bei 94/233/192.

**Reihenfolge (aktualisiert):** (1) `symval` → EXT (kalt). (2) `nameoff` → EXT mit Längen-Split
(löst Teil B in einem Aufwasch). (3) `symfn` → EXT nur fuer Profile, die den Symbol-Headroom
wirklich brauchen; Workbench tut das jetzt. Fuer Post-MVP muss Performance entscheiden, ob ein
Cache, Directory-Shortcut oder anderer CALL-Pfad noetig ist.

**EXT-Heimat `symval`:** Bank 5 hinter dem Namepool. Historische Messprofile nutzten
`SYMPOOL_EXT_OFF`+`NAMEPOOL` = $9000; der aktuelle P6c-Ein-Suite-Pin schiebt den Namepool wegen
des groesseren externen Images auf `$a000..$c000`. Nur `#ifdef __mos__` DMA;
Host behält Bank-0-Array (host-testbar). DMA-Härtungs-Regel
(`memory`-Clobber, s. `[[native-load-solved]]`/mem.c) beachten.

**Teil B — Namepool-Offset verbreitern.** `nameoff` 12-Bit-Offset → 16-Bit (Längen-Vorfilter-Nibble
opfern oder separat halten). Dann `NAMEPOOL` > 4096 (nur durch EXT begrenzt) → tausende Namen.
- Der Längen-Vorfilter war eine DMA-Sparoptimierung (Namensvergleich ohne EXT-Read bei Längen-
  Mismatch). Trade-off neu bewerten: bei EXT-Namepool ist der Vorfilter wertvoller, aber 12 Bit zu
  wenig — evtl. Länge in ein separates `uint8`-Array (Bank 0 oder EXT).

## Prerequisiten / Reihenfolge
- Zuerst **Teil B** (Namepool-Offset) — das ist die aktuelle Wand (~580) und wohl der einfachere
  Schritt (Kodierung + ein evtl. Längen-Array). Danach ist MAX_SYM (Array-Decke ~640) wieder die
  Grenze → **Teil A** (Arrays → EXT) für den Sprung in die Tausende.
- Perf messen (xemu/HW) vor und nach — globaler Zugriff darf den REPL/Editor nicht bremsen.

## Lane
K (`src/symbol.c`, `src/mem.c`, `src/obj.h`). Reine C-Runtime. Kein Bytecode-ABI-Bruch (die
Symbol-Semantik bleibt; nur die Speicherung wandert).
