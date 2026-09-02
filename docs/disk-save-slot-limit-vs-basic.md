# Warum SAVE nur vorallozierte Slots kann — und wie BASIC 65 frei speichert

Stand: 2026-07-09 (Claude, Recherche auf Nutzerfrage). Referenz-/Erklaernotiz,
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
HW-bestaetigt UND als Lisp-Primitive exponiert. Was fehlt (BAM-Allokation +
Directory-Schreiben) ist reine Filesystem-Buchhaltung, die sich **vollstaendig in
Bytecode-Lisp** ueber die vorhandenen Primitiven schreiben laesst — also ~11 B/Fn
in EXT statt 200–800 B `.text` in Bank 0. Damit faellt die R8-Wand (`.text`
~134 B Reserve, `memory-budget-strategy.md`) als Blocker praktisch weg, solange
KEINE neue C-Primitive dazukommt.

## Was schon da ist (das schwere ~80 %)
Als `defprim` in `eval.c:1433-1454`, alle Lisp/Bytecode-sichtbar:

| Primitive | leistet |
| --- | --- |
| `%disk-read-sector T S` | CBM-Logiksektor in den 256-B-Scratch |
| `%disk-byte i` | Byte i aus dem Scratch |
| `%disk-poke i v` | Byte i im Scratch setzen |
| `%disk-write-sector T S` | Scratch als Sektor schreiben — **RMW der 512-B-Physik + Read-back-Verify**, `nil` bei Abweichung |
| `%save-staged` | In-place-Save in vorhandene Kette (heutiger Slot-Weg) |

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
- **M1 BAM-Read/Sanity:** BAM-Sektor lesen, Free-Counts gegen einen bekannten
  Leerstand pruefen; nur lesen, nichts schreiben.
- **M2 Ein-Sektor-Alloc:** einen freien Sektor in bekannt-freiem Bereich (NICHT
  Track 40/Fremddaten) markieren + BAM zurueckschreiben + read-back; noch KEIN Dir.
- **M3 Ketten-Write:** Nutzdaten in die frisch allozierten Sektoren mit korrekten
  Links schreiben, ueber den bewiesenen `(load)` per Start-T/S zurueckziehen.
- **M4 Dir-Eintrag:** einen freien Dir-Eintrag schreiben (Track 40 zuletzt), dann
  `(load "name")` findet die Datei ueber den normalen Dir-Walk.
- **M5 `(save-new "name" str)`:** volle Kette in crash-sicherer Reihenfolge, jeder
  Write verifiziert; Loop-Schluss = HW-gruener `(load)` liest das Ergebnis.

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

## Budget-Abschaetzung
| Ansatz | Bank-0 `.text` | EXT/Slots |
| --- | --- | --- |
| Idee A (pure Lisp) | **~0** | ~120 B EXT + ~10–12 Dir-Slots |
| Idee B (1 C-Prim) | ~200–500 B (reisst ggf. die ~134 B Reserve) | wie A minus 1–2 Fn |

Fazit: Der frueher als R8-Blocker gefuerchtete „SAVE-Allocator ist groesser als
LOAD" gilt nur fuer eine **C**-Implementierung. In Bytecode-Lisp ueber die schon
exponierten Sektor-Primitiven ist freies Speichern budget-vertraeglich; der echte
Restaufwand ist HW-Verifikation der Schreibpfade auf Track 40 (BAM/Dir) nach dem
M1–M5-Protokoll, nicht Code-Platz. Empfehlung: als eigener, HW-getakteter Block
nach dem M1–M5-Muster, Idee A, mit Dry-Run + Host-D81-Differ als Offline-Gates.
