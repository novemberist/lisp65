# Warum SAVE nur vorallozierte Slots kann — und wie BASIC 65 frei speichert

Stand: 2026-07-11. Der technische Vergleich unten dokumentiert den historischen
Slot-SAVE-Ausgangspunkt vom 2026-07-09. AP6 hat die beschriebene Produktluecke
inzwischen mit dem ladbaren `M65D`-COW-Kern geschlossen. Referenz-/Erklaernotiz,
kein neues Gate. Bindet `docs/save-risk-analysis.md`,
`docs/f011-write-calibration.md`, `docs/mega65-file-io-research.md` und
`docs/two-product-workflow.md` zusammen.

## Frage
Warum kann lisp65 aktuell nur in **vorallozierte D81-Slots** speichern statt
beliebige Dateien anzulegen — und wie schafft das mitgelieferte MEGA65-BASIC das
freie Speichern trotz gleicher Hardware?

## Kurzantwort
Es ist **keine Hardware-Grenze**. Der F011-Controller gibt BASIC und lisp65
denselben rohen Sektor-Read/Write. Der Unterschied liegt eine Schicht hoeher:
**die 1581-Filesystem-Logik (BAM-Allokation + Directory-Schreiben).**
BASIC leiht sie sich aus dem **C65-ROM-DOS**; lisp65 blendet dieses ROM fuer RAM
aus und faehrt bewusst am ROM/KERNAL vorbei direkt auf den F011 — und muss die
Allokations-Haelfte daher selbst bauen, was heute noch fehlt.

## Was der Geraete-SAVE heute tut
`io_disk_save_impl` (`src/io.c`, hinter `MEGA65_F011_WRITE`) macht **Overwrite-in-
place in eine bereits existierende Datei-Kette**. Zwei Zeilen sind die Schranke:

- `if (!disk_dir_find(name, &t, &s)) return 0;` — der Name **muss schon** einen
  Directory-Eintrag (Track 40) haben; SAVE legt nie einen an.
- `if (len > disk_chain_capacity(t, s)) return 0;` — die Daten **muessen** in die
  vorhandene Sektorkette passen; die Kette (Links + Endmarke) wird nie veraendert,
  die Slot-Kapazitaet ist bei Anlage fix und waechst/schrumpft nie.

Jeder Sektor geht durch den HW-kalibrierten `io_disk_write_sector` (Read-Modify-
Write des 512-B-Physiksektors + Read-back-Verify); ein falscher Write liefert
sauber `nil`, nie stille Korruption. Ungenutzter Slot-Rest wird mit Spaces
gefuellt, die der Regel-B-`(load)` als Whitespace ueberliest. Die Slots selbst
legt **Host-Tooling** an (z. B. `scripts/hw-disk-roundtrip.sh`: Dummy-Datei mit
Directory-Eintrag + Sektorkette), das Geraet ueberschreibt nur.

## Die harte Grenze
Fuer eine **beliebige/wachsende** Datei fehlen zwei Bausteine am Geraet:

1. **Kein Directory-Writer** — neue Datei = neuer 32-B-Eintrag auf Track 40. Der
   Code kann Track 40 nur lesen (`disk_dir_find`), nie schreiben.
2. **Kein BAM-Allocator** — Wachsen/Neuanlegen = freie Sektoren aus der BAM holen
   und als belegt markieren. Nicht implementiert.

Beides ist der destruktivste, HW-riskanteste Teil (Track 40 ist „heilig"; Risiken
R2/R3/R4/R5 in `save-risk-analysis.md`) und wurde bewusst zugunsten des
bombensicheren In-place-Overwrite zurueckgestellt (MVP-Design,
`two-product-workflow.md` Prio 1, 2026-07-05).

## Wie BASIC 65 es macht
`DSAVE`/`DOPEN`+`APPEND`/`SCRATCH`/`RENAME` delegieren BAM- und Directory-
Verwaltung an das **C65-native DOS im ROM**. Der MEGA65 hat ein internes „dummes"
Laufwerk (nur der F011-Controller, kein eigener Rechner wie beim externen 1581),
deshalb liefert die Host-ROM die komplette 1581-Filesystem-Logik; BASIC ruft sie
nur auf. Belegt in `mega65-file-io-research.md`:337 — *„`RUN"…"`/`DLOAD` aus BASIC
funktioniert, nutzt aber die C65-native DOS im ROM — in Produktion blenden wir das
ROM fuer RAM aus → nur Stopgap."*

## Warum lisp65 die ROM-DOS nicht nutzt
1. **ROM ist in Produktion weggeblendet** (Adressraum als RAM gebraucht) → die
   DOS-Routine ist dann weg.
2. **ROM-/KERNAL-Aufrufe sind im C65-Nativ-Kontext fragil** — brauchen einen MAP-/
   Banking-Zustand, den die llvm-mos-Runtime nicht setzt; `cbm_k_open` crasht, die
   C64-Kompat-Routinen erreichen das interne Laufwerk nicht, `LOAD` haengt am IEC-
   Bus (`mega65-file-io-research.md`:116-125, 335-337).
3. **Bewusste Produktarchitektur**: Lisp spricht den F011 direkt an — kein ROM,
   kein KERNAL, kein hyppo-DOS — fuer Selbst-Enthaltung und HW-Verifizierbarkeit.

## Folge / naechster Schritt
Freies Speichern = die BAM-/Directory-Allokationsschicht selbst nachbauen (in
Lisp/C ueber F011), nicht aus dem ROM leihen. Die F011-Write-Mechanik ist
HW-bestaetigt (`f011-write-calibration.md`), das sichere Protokoll ist in
`save-risk-analysis.md` §57ff skizziert (Neue-Datei-Semantik, Schreibreihenfolge
Daten→BAM→Dir zuletzt, nur Wegwerf-Disks, Read-back-Verify). Vorgezeichnet ist der
Weg in der geplanten `m65-disk`-Parity-Lib (`mega65-basic-parity-libraries.md`:80:
`DSAVE`/`DOPEN`/`APPEND`/`SCRATCH`/`RENAME`/`MKDIR` „ueber F011/D81"). Vertagt
wegen Korruptionsrisiko und Code-Budget (SAVE-Allocator ist deutlich groesser als
LOAD, Risiko R8).

---

# Machbarkeitsstudie: freies Speichern (eigene Analyse, 2026-07-09)

## Verdikt vorab
**Machbar — und billiger als die R8-Sorge nahelegt.** Der teure, HW-riskante Teil
(F011-Sektor-Write mit RMW + Read-back-Verify) ist bereits implementiert,
HW-bestaetigt UND als native Lisp-Primitive exponiert. Was fehlt
(BAM-Allokation + Directory-Schreiben) ist reine Filesystem-Buchhaltung, die
sich in Bytecode-Lisp ueber diese Primitiven schreiben laesst — also ~11 B/Fn
in EXT statt 200–800 B `.text` in Bank 0.

Codex-M0 2026-07-09: Fuer **host-kompilierte** Bytecode-Libs sind
`%disk-poke` und `%disk-write-sector` nun als CALLPRIM-Tail-IDs 21/22 gepinnt
und in Host-Compiler, Host-VM, C-Compiler-Tabelle und C-VM verdrahtet. Das ist
Glue zu vorhandener C-Logik, keine neue F011-Write-Primitive und keine
BAM/Directory-Implementierung in Bank 0. Wegen Workbench-Budget sind diese
beiden C-VM-CALLPRIM-Cases intern/unchecked; eine nutzerseitige Schicht muss
Argumente validieren. Der Device-LCC mappt die zwei Namen noch nicht direkt auf
CALLPRIM, weil das `%lcc-prim`-Codeobjekt sonst das 255-B-Limit reisst.

## Was schon da ist (das schwere ~80 %)
Als `defprim` in `eval.c:1433-1454`, mit folgendem Bytecode-ABI-Stand:

| Primitive | leistet | Bytecode-Stand |
| --- | --- | --- |
| `%disk-read-sector T S` | CBM-Logiksektor in den 256-B-Scratch | CALLPRIM 15 |
| `%disk-byte i` | Byte i aus dem Scratch | CALLPRIM 16 |
| `%disk-poke i v` | Byte i im Scratch setzen | CALLPRIM 21 fuer host-kompilierte Libs; C-VM unchecked |
| `%disk-write-sector T S` | Scratch als Sektor schreiben — **RMW der 512-B-Physik + Read-back-Verify**, `nil` bei Abweichung | CALLPRIM 22 fuer host-kompilierte Libs; C-VM unchecked |
| `%save-staged` | In-place-Save in vorhandene Kette (heutiger Slot-Weg) | bestehender Workbench-Save-Pfad, nicht der freie Allocator |

Dazu in C (Regel-B-Leseweg, HW-gruen): Directory-Walk (`disk_dir_find`,
Eintragsformat s. u.), Sektorketten-Folgen, Ketten-Kapazitaet. Die Geometrie
CBM-1581-logisch ↔ F011-physisch ist gemessen und in `mega65-file-io-research.md`
festgeschrieben.

**Wichtige Randbedingung (aus `io.c`):** Es gibt EINEN gemeinsamen 256-B-Scratch
(`DISK_EXT_DIR`). Read→Poke→Write muss also streng sequenziell laufen; ein
zwischengeschobenes `%disk-read-sector` eines anderen Sektors ueberschreibt den
Scratch. Die Nutzdaten liegen getrennt im EXT-Datei-Puffer (`DISK_EXT_FILE`), das
kollidiert nicht.

## Was fehlt (das leichte ~20 %, reine Buchhaltung)
1. **BAM lesen/parsen** — freie Sektoren je Track abfragen.
2. **Freie-Sektor-Allokation** — Sektor waehlen, im Bitmap als belegt markieren,
   Free-Count-Byte dekrementieren (1581-Interleave beachten).
3. **Ketten-Writer** — allozierte Datensektoren mit korrekten CBM-Links (`+0/+1` =
   next T/S; Endsektor `+0`=0, `+1`=letzter Byte-Offset) verketten und die
   Nutzdaten aus dem EXT-Puffer hineinschreiben.
4. **Directory-Eintrag anlegen** — freien Eintrag finden (oder Dir-Sektor
   nachwachsen), Typ/Name/Start-T-S/Blockzahl schreiben.
5. **Crash-sichere Reihenfolge** — Datensektoren → BAM → Directory-Eintrag ZULETZT
   (ein Abbruch hinterlaesst dann nur harmlos verwaiste Sektoren, keinen
   Dir-Eintrag auf Muell), jeder Write read-back-verifiziert.

## 1581-Layout, das der Allocator braucht (VOR dem Coden am D81 verifizieren)
- **Track 40 = Directory-Track.** T40/S0 = Header: `+0/+1` Link zum ersten
  Dir-Sektor, DOS-Version, Diskname, ID.
- **BAM auf T40/S1 (Tracks 1–40) und T40/S2 (Tracks 41–80).** Pro Track 6 Bytes:
  1 B Free-Count + 5 B (40 Bit) Sektor-Bitmap. (Genaue Byte-Offsets/Reihenfolge
  am echten Image gegenpruefen — c1541-D81 dumpen.)
- **Dir-Eintraege ab T40/S3**, verkettet, 8 × 32 B. Eintragsformat (schon aus
  `disk_dir_find` belegt): `+2` Typ (Bits 0–2; 0 = frei), `+3/+4` Start-T/S,
  `+5..+20` Name (16 B, `$A0`-Padding, GROSS-PETSCII), `+30/+31` Blockzahl LE.
- **RMW-Paarung (R2) gilt auch fuer Track 40**: Dir-/BAM-Sektoren sind ebenfalls
  256-B-Haelften eines 512-B-Physiksektors — `%disk-write-sector` erledigt das,
  aber die Paar-Haelfte darf nie stumm genullt werden.

## Implementierungsideen (priorisiert)

### Idee A — Pure-Lisp-Allocator ueber vorhandene Primitiven. EMPFOHLEN.
Neues Bytecode-Lisp-Modul (z. B. `lib/m65-disk-alloc.lisp` oder in den residenten
Disk-Loader), grob:
`%bam-sector-for-track`, `%bam-free-count`, `%bam-find-free`, `%bam-claim!`,
`%dir-find-free-entry`, `%dir-write-entry!`, `%disk-write-chain`, `save-new`.
Kosten grob: ~10–12 Fn × ~11 B EXT ≈ ~120 B EXT + ~1 Dir-Slot je Fn. **Null neues
C, null Bank-0-`.text`.** Genau der Hebel-B-Fall aus `memory-budget-strategy.md`
(C ~500 B Bank 0 vs. Bytecode-Fn ~11 B EXT).

### Idee B — C nur fuer eine heisse Innenschleife (Fallback).
Falls der Lisp-Bitmap-Scan/Chain-Write zu langsam ist, EINE schmale C-Primitive
(z. B. `%bam-first-free` als reiner Bitmap-Scan). Bewusst letzte Wahl — jede
C-Zeile zahlt Bank-0-`.text`. Erst messen, dann ggf. genau eine Primitive.

### Milestones (streng nach `save-risk-analysis.md`, NUR Wegwerf-Disks)
- **M0 ABI-Glue: erledigt fuer host-kompilierte Libs.** `%disk-poke` und
  `%disk-write-sector` sind CALLPRIM 21/22 in `docs/bytecode-abi.md`,
  `src/compile.c`, `src/vm.c`, Host-Compiler und Host-VM; Drift-/Golden-
  Vektoren sind gruen. Deferred: Device-LCC-Direktmapping und nutzerfeste
  Argumentvalidierung.
- **M1a Host-BAM-Sanity: erledigt.** `make workbench-d81-bam-sanity` liest die
  Workbench-D81 read-only, prueft BAM-Sektorlinks, Free-Counts gegen Bitmap-
  Bits und Directory-Blocksumme. Aktueller Pin: `free_blocks=2777`,
  `file_blocks=383`, `dir_entries=9`, `track40_free=35`.
- **M1b Geraete-BAM-Read/Sanity: erledigt read-only.**
  `make hw-workbench-bam-read-smoke` deployt die Workbench per Etherload und
  liest auf echter MEGA65-HW die BAM-Sektoren T40/S1 und T40/S2 per
  `%disk-read-sector`/`%disk-byte`. Live-Pin vom 2026-07-09: T40/S1 liefert
  `(t 40 2 40 35)`, T40/S2 liefert `(t 0 255 0 39)`. `make check` enthaelt
  nur den Dry-Run des Harness.
- **M2 Ein-Sektor-Alloc: erledigt auf Wegwerf-D81.**
  `make hw-workbench-bam-alloc-smoke` kopiert die Workbench-D81 nach
  `build/hw/workbench-m2-before.d81`, laedt sie als `L65M2.D81`, startet ein
  dediziertes Mini-PRG und markiert T45/S8 in der BAM als belegt. Live-Pin vom
  2026-07-09: sichtbarer Marker `bam alloc pass 4/4`; zurueckgeholtes Image
  unterscheidet sich exakt an zwei Bytes: `0x61a28 32->31` und
  `0x61a2a 0xff->0xfe`. Kein Directory-Eintrag, kein Datensektor-Write.
- **M3 Ketten-Write: erledigt auf Wegwerf-D81.**
  `make hw-workbench-chain-write-smoke` schreibt die Fixture
  `tests/disk/m3-chain-source.lisp` als zweisektorige Quelle T45/S8 -> T45/S9,
  markiert beide Sektoren in der BAM, holt `L65M3.D81` zurueck und prueft den
  D81-Diff hostseitig exakt. Live-Pin vom 2026-07-09: sichtbarer Marker
  `chain write pass 7/7`; Host-Differ `len=275`, `0x61a28 32->30`,
  `0x61a2a 0xff->0xfc`; Workbench-Oracle gegen dieselbe Wegwerf-D81:
  `(%disk-load-file 45 8)` => `"m3-load-ok"`, `(m3-chain-run)` => `737`.
  Kein Directory-Eintrag.
- **M4 Dir-Eintrag: erledigt auf Wegwerf-D81.**
  `make hw-workbench-dir-write-smoke` schreibt die Fixture
  `tests/disk/m4-dir-source.lisp` als zweisektorige Quelle T45/S8 -> T45/S9,
  markiert beide Sektoren in der BAM und schreibt zuletzt den freien
  Directory-Slot T40/S4 Entry 1 als `M4SRC`. Live-Pin vom 2026-07-09:
  sichtbarer Marker `dir write pass 11/11`; Host-Differ `len=276`,
  `dir@0x61c20`, `0x61a28 32->30`, `0x61a2a 0xff->0xfc`; Workbench-Oracle
  gegen dieselbe Wegwerf-D81: `(load "m4src")` => `"m4-load-ok"` und
  `(m4-dir-run)` => `767`. Damit ist der normale Directory-Walk fuer eine neu
  angelegte Datei HW-gruen.
- **M5 Lisp-`save-new`-Prototyp: erledigt auf Wegwerf-D81, jetzt
  M6-kompatibel.**
  `make hw-workbench-save-new-smoke` kopiert die Workbench-D81 nach
  `build/hw/workbench-m5-before.d81`, schreibt den Lisp-Allocator
  `lib/m65-disk-alloc.lisp` als Source-Datei `m5alloc` hinein und startet ein
  dediziertes Mini-PRG. Das PRG laedt `m5alloc` zur Laufzeit, erzeugt per
  `(m65d-save-new-2 "m5src" (m65d-test-payload))` die neue Datei `M5SRC` auf
  den ersten zwei freien T45-Sektoren ab S20 und schreibt den freien
  Directory-Eintrag in T40/S4 zuletzt. Wegen des groesseren Allocator-Source
  sind im aktuellen Workbench-Wegwerf-Image nach `c1541` S26/S27 frei;
  der hardwarefreie Pin erwartet deshalb `name=m5src T45/S26->S27`,
  `dir@0x61c60`, `0x61a28 14->12`, `0x61a2c 0xfc->0xf0`.
- **M6 BAM-Scan/Name/Dir-Slot: erledigt live auf Wegwerf-D81.**
  `make hw-workbench-save-new-scan-smoke` reserviert im Vor-Image zusaetzlich
  T45/S26 in der BAM und baut ein zweites Mini-PRG mit Zielname `m6src`. Der
  Allocator muss dadurch T45/S27 -> S28 aus der BAM waehlen und den Namen
  `M6SRC` in den freien Directory-Slot materialisieren. Live-Pin vom
  2026-07-11: sichtbarer Marker `save new pass 5/5`; Host-Differ
  `name=m6src T45/S27->S28`, `len=373`, `dir@0x61c60`,
  `0x61a28 13->11`, `0x61a2c 0xf8->0xe0`; Workbench-Oracle gegen dieselbe
  Wegwerf-D81: `(load "m6src")` => `"m5-load-ok"` und `(m5-new-run)` =>
  `797`. Dieser Pin beweist den Lisp-seitigen Daten->BAM->Directory-Loop
  inklusive Name, freiem T40/S4-Slot und BAM-Scan. Er bleibt bewusst ein
  Zweissektor-Prototyp auf Track 45, noch kein allgemeiner Dateiallokator.
- **M7 variable Kette/globale BAM-Wahl: live auf echter HW gepinnt.**
  `lib/m65-disk-alloc-var.lisp` stellt den separaten Prototyp
  `(m65d-save-new name src)` bereit. Er berechnet `ceil(len/254)`, scannt freie
  Datensektoren ueber Tracks 1..80 mit ausgelassenem Directory-Track 40,
  schreibt die variable Kette und markiert danach die BAM. Das neue Oracle
  `tools/host-lisp/d81_save_new_diff.py` liest den Allokationsplan aus dem
  Vor-Image und prueft Datenkette, BAM-Counts/Bits und Directory-Slot
  bitgenau. Aktueller Live-Pin: dreisektorige Quelle `M7SRC` mit 676 Bytes auf
  T1/S0 -> T1/S1 -> T1/S2, Directory T40/S4 Entry 3; sichtbarer Marker
  `save new pass 5/5`; Workbench-Oracle `(load "m7src")` =>
  `"m7-load-ok"` und `(m7-var-run) => 907`. Der Harness nutzt `--wait 45`,
  weil der groessere Lisp-Allocator laenger laedt/evaluiert.

### AP6-Produktstand

`M65D` scannt die komplette vorhandene Directory-Kette, alloziert neue Ketten
bis zum gepinnten 8192-B-Limit innerhalb einer BAM-Haelfte und bietet
Create-only sowie Upsert ueber denselben COW-Kern. Daten werden vor BAM-Claim
geschrieben und gelesen/verifiziert; das Directory wird zuletzt veroeffentlicht.
Die stabile Status-ABI 0..9, Latch und `m65d-remount` bilden Fehler nach aussen
ab. Der Fault-Oracle besteht 16 Szenarien an 82 Abbruchpunkten und drei
Negativmutationen. Live sind zwei Creates in einer Session, Replace, Remount
und Read/Eval beider Dateien nach Reset ohne D81-Reupload gruen.

Bewusst offen bleiben nur Directory-Wachstum, globale Crosslink-/Sektor-
Ownership-Reparatur und Power-Loss-Atomizitaet zwischen physischen Writes.

### Sicherheits-Scaffolding (billig, hoher Nutzen)
- **Dry-Run-Modus:** Allokationsplan (Sektorliste, Dir-Slot) berechnen und
  ausgeben OHNE Write — erlaubt Review vor jedem destruktiven Lauf.
- **Read-back-Verify nach JEDEM Write** (hat `%disk-write-sector` schon; im
  Allocator konsequent auf `nil` reagieren, laut abbrechen).
- **Host-seitiger D81-Differ** als Offline-Gate: Image vor/nach dumpen, BAM +
  Directory + Fremdsektoren vergleichen (kein Fremdsektor darf sich aendern).
  Ergaenzt `hw-disk-roundtrip.sh` und braucht keine HW.
- **`(load)` als Oracle:** wie beim Slot-Save schliesst der HW-gruene Leseweg den
  Loop und ist der beste Korrektheits-Check.

## Allokations-spezifische Risiken (zusaetzlich zur R-Liste)
- **Zwei Wahrheiten in der BAM:** Free-Count-Byte und Bitmap muessen konsistent
  bleiben; Standard-Tools (`VALIDATE`) meckern sonst.
- **1581-Interleave/Allokationsreihenfolge:** falsche Reihenfolge macht die Disk
  lesbar, aber unkonventionell — kosmetisch, ausser Fremd-Tools bestehen darauf.
- **Dir-Sektor-Nachwuchs:** ist der Dir-Sektor voll, muss ein neuer Track-40-Sektor
  alloziert + verlinkt werden (zusaetzlicher Fall).
- **Scratch-Sequenzierung** (s. o.): kein fremder Sektor-Read zwischen Read und
  Write desselben BAM/Dir-Sektors.

## Budget: historische Abschaetzung und Messwert
| Ansatz | Bank-0 `.text` | EXT/Slots |
| --- | --- | --- |
| Idee A (pure Lisp) | **~0 fuer Allocator-Logik**; CALLPRIM-Glue fuer `%disk-poke`/`%disk-write-sector` ist als M0 gelandet | ~120 B EXT + ~10–12 Dir-Slots |
| Idee B (1 C-Prim) | ~200–500 B (reisst ggf. die ~134 B Reserve) | wie A minus 1–2 Fn |

Der umgesetzte Lisp-Kern misst 35 Funktionen, 3857 B Code und 6719 B gesamtes
Disk-Lib-Image. Im kumulativen Produktbudget endet AP6 plus IDEX bei 544/552
Directory-Slots, 693/720 Symbolen und 9223/9536 Namepool-Bytes; Bank-0-Layout
und AP4-Slots bleiben unveraendert.

Fazit: Der frueher als R8-Blocker gefuerchtete „SAVE-Allocator ist groesser als
LOAD" gilt nur fuer eine **C**-Implementierung. In Bytecode-Lisp ueber die
F011-Sektor-Primitiven ist freies Speichern budget-vertraeglich; AP6 hat diese
Empfehlung mit Dry-run, Host-D81-Differ, Fault-Oracle und Live-Hardwaregate
umgesetzt.
