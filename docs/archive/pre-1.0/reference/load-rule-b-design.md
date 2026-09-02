# LOAD ins Vollprodukt — Regel-B-Redesign (Design-Dokument)

Stand: 2026-07-04 (Claude). Ziel: natives `(load "name")` von der eingelegten Disk **im
Vollprodukt**, budget-passend, indem die 1581-Dateisystem-Logik nach **Bytecode-Lisp** wandert
(Regel B) und der residente C-Kern nur die echten Hardware-/Puffer-Primitive behält.

## Problem (vermessen, `docs/memory-budget-strategy.md`, `[[budget-frontier]]`)
Der aktuelle C-`io_load_file` (MEGA65_F011_LOAD) ist **1034 B .text** — allein **376 B über**
der 658-B-Reserve, VOR jedem Puffer. Er passt so nicht. Grund: er parst das ganze 1581-FS in C
(Directory-Walk, Namensvergleich mit PETSCII-Fold, Ketten-Folgen, Copy). Das ist Policy-Logik,
die nach Regel B in Bytecode-Lisp gehört; C behält nur den F011-Sektor-Read + den Parse-Puffer.

## Architektur
```
Bytecode-Lisp  (load name)   [lib/, Lane L]
   ├─ Directory-Walk + Namensvergleich (PETSCII-Fold)   via %disk-read-sector / %disk-byte
   └─ Datei gefunden -> (%disk-load-file ft fs)
C-Primitive    [src/, Lane K]           frozene Prim-IDs [docs/bytecode-abi.md §4a, Lane T]
   ├─ %disk-read-sector(track,sektor) -> t/nil     F011-Read 1 CBM-Logiksektor -> DBUF[0..255]
   ├─ %disk-byte(i) -> fixnum                       DBUF[i] (Dir-Eintrag inspizieren)
   └─ %disk-load-file(track,sektor) -> t/nil        1581-Ketten-Folgen -> Parse-Puffer -> load_source
```
Geometrie (HW-bewiesen, `docs/mega65-file-io-research.md`): `f011_read_logical` bleibt der Kern
(vollstaendig neu etablierter F011-Kontext, `$D689=0`, F011-Kmd, `$D680=$81/$82`,
CBM→F011-Mapping; rohe `$D680=2`-SD-Kommandos sind hier verboten). **Neu ggü. heutigem io.c:** direkt
aus dem `$DE00`-Fenster in den Ziel-Puffer kopieren, KEIN Stack-`sec[256]` mehr (spart 256 B
Lade-Zeit-Stack-Spitze — wichtig für den Fit, s. u.).

## Primitiv-Semantik (Lane K)
- **`%disk-read-sector(track, sektor)`** — `track` 1..80, `sektor` 0..39 (CBM-1581 logisch).
  Liest den 256-B-Logiksektor der eingelegten Disk (F011 + Mapping `f011_track=L-1`, `b=S>>1`,
  `seite=(b>=10)`, `f011_sektor=(b%10)+1`, `half=S&1`) nach `DBUF[0..255]`. `t`/`nil`.
- **`%disk-byte(i)`** — `DBUF[i]` (i 0..255) als Fixnum.
- **`%disk-load-file(track, sektor)`** — folgt der 1581-Sektorkette ab (track,sektor) (Link =
  erste 2 Bytes je Sektor; letzter Sektor: track=0, sektor=Byte-Zahl), akkumuliert die 254
  Datenbytes/Sektor in den Parse-Puffer, NUL-terminiert, ruft `load_source`. `t`/`nil`.

## Puffer-Strategie
**EIN** Bank-0-Puffer `DBUF` (Größe = max. Dateigröße). Sequenziell nutzbar: erst Dir-Scan
(braucht 256 B/Sektor), dann Datei-Parse (bis Dateigröße). `%disk-load-file` liest jeden Sektor
DIREKT aus `$DE00` (kein Stack-Scratch) und akkumuliert nach `DBUF`. Der Reader (`read_expr`,
pointer-basiert) parst `DBUF` als NUL-terminierten String — deshalb MUSS der Puffer in Bank 0
und zusammenhängend sein (das ist der harte Grund, warum er nicht ins EXT kann ohne Reader-Umbau).

## Fit-Rechnung (Reserve 658 B nach Dir-Kompaktierung + Codex-Caps)
Residenter Zuwachs (statt der alten 1034 B): `f011_read_logical` (~250) + `%disk-read-sector`
(~40) + `%disk-byte` (~20) + `%disk-load-file` (~180) = **~490 B Code** + `DBUF`.
| DBUF | Code+DBUF | vs 658 | Datei-Max |
|---|---|---|---|
| 168 B | 658 | **passt** (0 Rest) | ~166 B |
| 256 B | 746 | fehlt 88 | ~254 B |
| 512 B | 1002 | fehlt 344 | ~510 B |
**Fazit:** ein *kleiner* Puffer (≤168 B) passt schon jetzt; ein brauchbarer (256–512 B) braucht
zusätzlich **~88–344 B**. Quelle dafür (Lane K, budgetiert für dieses Projekt): **`dir_off`-
Kompaktierung** — Sparse-Block (jedes 8. Offset speichern, ≤7 `dir_len`-Summen/Call, Bank-0-
Arithmetik, KEIN DMA) spart ~416 B → 512-B-Puffer passt mit Rest. Alternativ minimale Cap-Senkung.

Codex-Nachmessung (2026-07-04, aktuelle Caps + Dir-Kompaktierung): der alte C-F011-Pfad ist
weiter kein tragfaehiger Produktpfad. `IO_BUF_MAX=1` erreicht nur `stack_gap=1472/1450`
(22 B Reserve), `IO_BUF_MAX=256` faellt bei `stack_gap=820/1450` durchs Gate. Deshalb bleibt die
658-B-Reserve fuer dieses Rule-B-Design reserviert; `M65VMSTDLIB_MIN_BANK0_RESERVE=640` schuetzt
gegen versehentliche Cap-/C-Wachstums-Ausgaben bis die neue Primitiv-API gemessen ist.

## ABI-Ergänzungen (Lane T)
- **Erledigt (Codex, 2026-07-04):** 3 neue gefrorene Prim-IDs in `docs/bytecode-abi.md §4a`:
  IDs 15/16/17 = `%disk-read-sector`/`%disk-byte`/`%disk-load-file`.
- **Erledigt (Codex, 2026-07-04):** Bytecode-Compiler, Host-VM, C-VM-CALLPRIM und Golden-Vektoren
  kennen diese 3 CALLPRIM-Ziele; Drift-/Compiler-/Oracle-Checks sind gruen.

Aktuelles F011-Produktprofil nach K1/T1 (noch **mit** altem `io_load_file`, also
Uebergangszustand): `DISK_BUF_MAX=1` baut, faellt aber bei `stack_gap=940/1450`; `256` baut,
faellt bei `256/1450`; `512` linkt noch nicht (`.bss` overflow 40 B). Das bestaetigt die
Reihenfolge: Lisp-`(load)` bauen, dann alten C-`io_load_file` im F011-Build entfernen und
das finale DBUF-Profil neu messen.

## Bootstrap
`(load)` wird eine **Bytecode-Lisp-Funktion im gebündelten Stdlib-Blob** (kompiliert aus
`lib/…`, wie jede Stdlib-Fn) — beim Boot normal geladen, KEIN Henne-Ei. Im MEGA65-Build
**ersetzt** sie die C-`P_LOAD`/`io_load_file`-Naht → die alten 1034 B werden im F011-Build
ge-`#ifdef`-t ENTFERNT (Netto-Code-Delta = −1034 + 490 = **−544 B** ggü. der alten F011-Impl).
Host-/C64-Builds behalten den C-`load` (fopen/KERNAL) unverändert.

Stand Codex (2026-07-04): Bytecode-`load` liegt in `lib/stdlib-load.lisp` und wird über
`tests/bytecode/stdlib/p0-stdlib-load-subset.json` als Erweiterung der MVP-Stdlib gebaut.
Nach Claudes EXT-Streaming-Reader gibt es keinen Bank-0-Parse-Puffer mehr; `DISK_BUF_MAX` ist aus
den Load-/Disk-Lib-Profilen entfernt. Das aktuelle `make mvp-vm-stdlib-load-footprint-report`
nutzt `MAX_SYM=332`, `VM_DIR_MAX=250`, `REPL_BUF_MAX=112`, `HIST_MAX=16`, `GC_ROOTS=128`, kein
`LISP65_SCREEN_WRITE_STRING` und ein hartes `M65VMSTDLIB_LOAD_MIN_BANK0_RESERVE=512`. Gemessen:
`boot_required_symbols=324/332`, `entries=242/250`, `stack_gap=2010/1450`,
`bank0_reserve=560/512`. Dateigröße ist im MVP-Profil nicht mehr durch ein kleines Bank-0-DBUF
gedeckelt; der Preis ist, dass dieses Load-Profil fuer REPL-Load-Proofs gedacht ist, nicht fuer
voll interaktives IDE-Rendering mit nativer Bulk-Zeile.

## Lane-Split & Reihenfolge
1. **K (Claude):** die 3 C-Primitive (`io.c`/`eval.c`, gegated MEGA65-F011), `$DE00`-Direkt-Copy
   (kein Stack-`sec`), alten `io_load_file` im F011-Build entfernen; `dir_off`-Kompaktierung für
   das Budget; Host-Stubs, damit `make check` grün bleibt; residenten Footprint MESSEN (Fit
   bestätigen), bevor L baut.
2. **T (Codex):** 3 gefrorene Prim-IDs (§4a) + Bytecode-Compiler-Support; F011-Produktprofil.
3. **L (Codex):** `(load name)` als Bytecode-Lisp in `lib/` (Dir-Walk + PETSCII-Fold + Aufruf
   `%disk-load-file`); zugehörige Host-Eval-Cases.
4. **Integration + HW-Test:** Vollprodukt + gemountete `TESTLIB`-Disk → `(load "testlib")` →
   `(sq 5)`=25 am Geraet (wie der bereits grüne Smoke, aber jetzt im Vollprodukt-REPL).

## Offene Detailpunkte (in K1 zu klären)
- Genaue `DBUF`-Größe (MVP-Entscheid Dateigröße vs. Budget) + ob `dir_off`-Kompaktierung
  gleich mitkommt.
- Lade-Zeit-Stack-Spitze: mit `$DE00`-Direkt-Copy entfällt `sec[256]`; Rest-Stackbedarf gegen
  das 1450-Gate prüfen (Footprint-Tool erweitern? Lane T).
- Fehler-Semantik von `(load)` (nicht gefunden / RNF) im Dialekt.
