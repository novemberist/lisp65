# MEGA65-Nativ Datei-I/O — Recherche & Plan (Lane K)

> ## ✅ KONTEXT-KORREKTUR 2026-07-13 (G6, echte Hardware)
> Der historische Befund „`$D680=$81` allein gibt 0“ war kein Nachweis, dass
> vor jedem F011-Zugriff ein rohes SD-Read `$D680=$02` nötig ist. `$D689.7`
> wählt, welcher der zwei Puffer im `$DE00`-Fenster erscheint; der Freezer
> hinterließ `$D689=$80` (direkter SD-Puffer). Dadurch änderte der SAVE-Pfad
> den falschen Puffer, während F011 den unveränderten alten Sektor schrieb.
> Das Readback-Verify erkannte die Abweichung als Status 7; die vollständige
> Work-D81 blieb byteidentisch. Der kanonische Pfad besitzt seitdem jede
> Transaktion vollständig: I/O-Unlock, `$D080=$60`, Track/Sektor/Seite,
> `$D689=$00`, F011-Kommando, `$D680=$81` nur während der Kopie und danach
> `$D680=$82`. `$D68B` bleibt Hypervisor-Mount-Autorität und wird vom Produkt
> nie geschrieben; Medium-Name/-ID und die bestehenden Readback-Oracles
> validieren den Mount. Der erzwungene Vorzustand `$D689=$80` ist permanenter
> Bestandteil von `work-media-save-remount-read`.

> ## ✅ HW-DURCHBRUCH 2026-07-04 (Claude, mit Nutzer am Geraet): F011-Leseweg bewiesen
> Nach ~10 Read-only-Proben per etherload am echten Geraet ist der Kern-Blocker gelöst
> und die ARCHITEKTUR geklärt. **Produkt-Modell (Nutzer-Entscheid): Lisp exponiert NUR
> „die eingelegte Disk" (LOAD/SAVE per Dateiname); NIE rohen SD-Zugriff, keine D81-Namen,
> keine Ordner. Mounten ist Sache des Systems (Freezer/Boot-Menü), nicht von Lisp.**
>
> **HW-bestätigte Fakten (alle am Geraet gemessen):**
> 1. **SD-Sektor-Read funktioniert** über `io_enable` ($D02F-Knock $47/$53) → `$D680=2`
>    (Sektor in $D681-4) → warten → `$D680=$81` → aus `$DE00` lesen. Sektor 0 gibt `55 aa`
>    (MBR). Der alte „$DE00-Müll"-Befund war vermutlich fehlendes io_enable / alter Core.
> 2. **FAT32-Parse funktioniert** (MBR→BPB→Wurzelverzeichnis→8.3-Namen; echte SD-Dateien
>    gelistet). ABER: nur zur Diagnose — NICHT das Produkt (rohe SD-Navigation ist tabu).
> 3. **Mounten einer D81 SPERRT rohe SD-Reads:** mit gemounteter Disk liefert JEDER
>    `$D680`-Read denselben stehenden Puffer, egal welcher Sektor. → Der „D81-Image von
>    der SD via FAT lesen"-Weg (io.c `-DMEGA65_F011_LOAD`) ist eine SACKGASSE, sobald eine
>    Disk eingelegt ist. Man MUSS über den F011.
> 4. **F011-Read der eingelegten Disk funktioniert** (rnf=0, DRQ gesetzt): `$D080=$60`
>    (Motor) → `$D081=$20` (spinup) → `$D084/85/86` = Track/Sektor/Seite → `$D081=$40`
>    (read) → auf `!($D082 & $80)` (BUSY) warten.
> 5. **F011-Puffer lesen — DER gelöste Knackpunkt:** NICHT via `$D087` (gab 0), NICHT via
>    Flat-`$FFD6C00` (gab 0), NICHT via `$D680=$81`+`$DE00` allein (gab 0). **FUNKTIONIERT
>    via `$D680=2` → `$D680=$81` → aus `$DE00` lesen** — liefert echte, SEKTORSPEZIFISCHE
>    Daten (t1s0 ≠ t40s1 im selben Lauf bewiesen). DMAgic-Kopie aus `$FFD6C00` gab 0
>    (Adressierung war falsch) — wird aber nicht gebraucht.
> 6. **etherload-Artefakte (Test-Harness):** Reset hängt Freezer-Mounts aus; `-m <datei>`
>    mountet (Datei muss im SD-ROOT liegen, exakter 8.3-Name — `intro1.d81` ≠ `INTRO01.D81`!);
>    `-m` + Autoboot-Disk startet das Disk-Programm STATT `-r`-PRG (für Tests eine
>    Nicht-Autoboot-Disk wie `mega65.d81` nehmen).
>
> **✅ GEOMETRIE GELÖST 2026-07-04 (Kalibrier-Disk am Geraet):** Eigene `CALIB.D81` (jeder
> 512-B-Sektor mit linearer Block-Nr gestempelt) auf SD hochgeladen (`mega65_ftp`), per
> `etherload -m CALIB.D81` gemountet, Raster aus (Track,Sektor,Seite) via F011 gelesen. Alle
> gültigen Messpunkte (Sektor ≥ 1) passen exakt auf:
> ```
> block = f011_track*20 + seite*10 + (sektor-1)     [f011_track 0..79, seite 0..1, sektor 1..10]
> ```
> Das ist das Standard-D81-Layout (jeder physische Track = 20 × 512-B-Blöcke = 40 × 256-B
> CBM-Sektoren). Daraus die vollständige **CBM-1581-logisch → F011-physisch**-Abbildung:
> ```
> logisch: track L (1..80), sektor Sl (0..39, je 256 B)
>   b    = Sl >> 1            # 0..19  welcher 512-B-Block im Track
>   half = Sl & 1             # 0 = untere 256 B, 1 = obere 256 B
>   f011_track  = L - 1       # 0..79
>   seite       = (b >= 10) ? 1 : 0
>   f011_sektor = (b % 10) + 1   # 1..10
>   -> F011-Read(f011_track, seite, f011_sektor) -> 512-B-Puffer
>   logischer 256-B-Sektor = puffer[half*256 .. half*256+255]
> ```
> Quercheck: `block = f011_track*20+seite*10+(sektor-1) = (L-1)*20 + Sl/2` = D81-Byte-Offset
> `((L-1)*40 + Sl)*256`. Gültige Bereiche: sektor 1..10, track 0..79 (Sektor 0 & Track 80
> lieferten `blk 0000` = ungültig; werden nie erzeugt). 1581-Directory liegt logisch auf
> Track 40 → f011_track 39. **Keine offenen HW-Fragen mehr für den Leseweg.**
>
> **✅ LESEWEG END-ZU-END HW-VALIDIERT 2026-07-04:** Eigene Test-D81 (`TEST.D81`, c1541,
> SEQ-Datei `TESTLIB` = 319 B, spannt BEIDE 256-B-Hälften/2 Sektoren) auf SD, gemountet,
> standalone `loadprobe` (spiegelt `io_load_file` exakt) gelesen → `found y`, Start t39/s0,
> 2 Sektoren, 319 B byte-genau über die Sektorgrenze (inkl. High-Half `$DF00`). Damit ist
> die KOMPLETTE Kette bewiesen: Geometrie + M1-Puffer + Directory-Walk (T40) + Sektorkette
> + High-Half. **NEUER BEFUND — PETSCII-Namen:** Verzeichnisnamen stehen PETSCII-shift
> (`A-Z = $C1..$DA`), NICHT ASCII `$41..$5A`. Der alte `io.c`-Vergleich (ASCII-Upcase) hätte
> NIE gematcht (latenter Bug). Fix: charset-toleranter Vergleich `(byte & $7F)` + `a-z`-Fold,
> Padding `$20` — matcht `$41..$5A` UND `$C1..$DA`. `io.c` umgeschrieben+committet (`dc2cb84`),
> `chain[]/sbuf[]`/FAT raus (-1348 B BSS im F011-Build), `make check` grün.
>
> **✅✅ PRODUKT-LEVEL HW-GRÜN 2026-07-04:** Nicht mehr nur die Standalone-Probe — der ECHTE
> lisp65-Kern (`eval_init` + `eval` + `io.c`) im F011-Smoke-Build (`HEAP=128`, EXT-Heap,
> `IO_BUF=512`, kanonische `TESTLIB` = `(set-symbol-function 'sq (lambda (x)(* x x)))`) am
> Geraet: `mount-base=0003b8b4` (≠0, Disk gesehen), `(load "testlib")`→non-nil, **`(sq 5)`=25**.
> D. h. der komplette Weg (Boot → Datei von eingelegter Disk lesen → parsen → auswerten →
> Funktion aufrufen) läuft im Produkt-Build. Es fehlt NUR noch die Verdrahtung ins VOLLE
> Stdlib-Produkt (Budget, s. Codex-Nachzug unten).
> **HW-sichtbarer Smoke-Nachzug (Codex):** `make f011-load-hw-visible` baut eine Variante
> ohne Xemu-Test-Exit und mit Endlosschleife nach der Ausgabe, plus das passende
> `lisp65-f011-defd81-sd.img`. Der bisherige `f011-load-test` bleibt fuer Dump-/Xemu-Smokes.
>
> **BEKANNTE GRENZE — nur Laufwerk 0 / Gerät 8:** `f011_read_logical` setzt `$D080=$60`
> (Drive-Select-Bits=0) → liest nur „Image #0". MEGA65 kann Gerät 8 UND 9 gemountet haben;
> das zweite ist aktuell unsichtbar. Erweiterung = Laufwerks-Param → Drive-Select-Bits in
> `$D080` (exakte Kodierung ERST am Gerät verifizieren). Passt zum Commodore-Modell
> (`(load "name" 9)`); MVP = Gerät 8. Bewusst vertagt.
>
> **Build-Profil-Nachzug (Codex, 2026-07-04):** Die alten pre-EXT-F011-Profile sind
> nicht mehr passend (`f011-interim-ship` overflowt `.bss` weiter). Die kleinen
> F011-Smokes bauen wieder mit `-Oz`, `HEAP=128`, EXT-Heap und Produkt-Symbolbudgets.
> `f011-load-test` nutzt jetzt `TESTLIB` (256 B, 2 SEQ-Bloecke), laedt
> `(load "testlib")` und prueft `(sq 5)`; `f011-stdlib-test` baut mit
> 512-B-Stdlib-Chunks (max aktuell 501 B). Das volle MVP-VM-Stdlib-Produktprofil
> bleibt mit `-DMEGA65_F011_LOAD` rot: selbst `IO_BUF_MAX=1` liefert nur
> `stack_gap=836/1450`; mit 512-B-Puffer linkt es knapp nicht. Produktintegration
> braucht also A-Reclaim oder ein bewusst schlankeres Disk-Profil; die Smokes sind
> fuer den naechsten echten HW-Lauf vorbereitet.
>
> **Konsequenz für die Umsetzung:** kleiner C-Primitiv `disk-read-sector(t,s)` / später
> `disk-write-sector` (F011 + M1-Puffer), darüber die 1581-Verzeichnis/Datei-Logik als Lisp;
> Lisp-API nur `(load name)`/`(save name)` auf der eingelegten Disk. F011 ist SIMPLER als
> der SD-FAT-Weg (Controller macht Mount/Fragmentierung/Disk-Grenze selbst = auch sicher).

Stand: 2026-06-30. Frage: Wie liest `(load "name")` eine Datei im **MEGA65-Nativ-Modus**?

> **STAND 2026-07-01 (nach HW-Test): Logik fertig, EIN HW-Baustein offen.** Der
> `src/io.c`-Pfad (`-DMEGA65_F011_LOAD`) liest die gemountete D81 fragmentierungssicher
> (MBR→BPB→FAT-Cluster-Kette + 1581-Parser), offline in xemu END-zu-END bewiesen
> (`(load "demolib")`→`(sq 5)`=25; fragmentierte reale Disk erzwang den FAT-Ketten-Leser).
> **KRITISCHER BEFUND (HW):** Der SD-Sektorpuffer wird von **xemu nur bei `$DE00`**, von
> **echter HW nur bei `$FFD6E00`** (flat/DMA) bereitgestellt — xemu kann den HW-Puffer-Weg
> grundsätzlich NICHT abbilden. io.c erkennt das zur Laufzeit (Flat-Probe der MBR-Signatur),
> aber der **Flat-`$FFD6E00`-Pfad ist auf HW noch unbestätigt** → **eine fokussierte
> HW-Methoden-Runde** (welcher Puffer-Weg liefert `55 aa`) steht aus. Zusätzlich passt die
> volle F011-REPL wegen `sbuf`/`chain`-BSS nicht mehr in Bank 0 → braucht die Heap-Skalierung
> (K-A). Default AUS. hyppo-DOS verworfen. Interim: eingebettete Lib.

## Befund: harter, projektbekannter Blocker

- **`(load …)` crasht im Nativ-Modus bei `cbm_k_open()`** (KERNAL OPEN, `$FFC0`). Per
  Geräte-Bisektion (Border-Checkpoints) eindeutig isoliert: setnam/setlfs laufen, OPEN
  crasht (Regenbogen-Streifen).
- **Ursache:** Die C64-Stil-KERNAL-Datei-Routinen brauchen einen bestimmten MEGA65/C65
  **MAP-/ROM-Banking-Zustand**, den die llvm-mos-Runtime nicht setzt. Belegt durch die
  eigene Projekt-Historie: `docs/reference/mega65-lisp-start-path.md` dokumentiert
  seitenweise, dass KERNAL-Aufrufe im C65-Kontext ROM-/KERNAL-Vektoren statt RAM sehen
  (`$fffc`→`4f fa …`), dass MAP-Flips nötig sind (`hyppo_get/set_mapping` `$76`) und dass
  **kein KERNAL-/I/O-Code im umgemappten Fenster laufen darf**. Der alte lisp64-Strang
  hat device-`(LOAD 8 …)` deshalb **nie grün** bekommen (host-simuliert).
- **Toolchain:** llvm-mos hat **kein `fopen` für mega65** (in `stdio.h` deklariert, nirgends
  implementiert) — also kein stdio-Pfad auf dem Gerät.
- **mega65-libc** liest Dateien per **direktem SD-Karten-Zugriff + FAT32-Parser**
  (`sdcard.c`+`fat32.c`) — riesig, nicht sinnvoll portierbar; `fopen`/`fread` dort kommen
  aus der cc65-Toolchain.

## Mitigation (aktiv, committet)

`io_load_file` ist auf `__MEGA65__` ein No-op-Stub (`return 0`) → `load` meldet sauber
`*** load: cannot open` statt zu crashen. Die Nativ-REPL bleibt stabil. Host-Backend
(fopen) ist verifiziert; c64-Backend (KERNAL) steht, ist aber auf echter HW noch nicht
bestätigt.

## Wege (bewertet)

1. **Hypervisor-DOS-Traps (hyppo) — EMPFOHLEN.** Der MEGA65-Hypervisor läuft im eigenen
   Kontext (trap-basiert), unabhängig vom KERNAL-/MAP-Problem. Er bietet DOS-Funktionen
   (setname/findfirst/open/read/close), die FAT32 intern erledigen. **Braucht:** das
   exakte hyppo-DOS-Trap-Protokoll (Trap-Adressen, Funktionsnummern in A, Register-
   konvention, Block-Read/EOF). Quelle: MEGA65-`mega65-core/src/hyppo` bzw. die offizielle
   Hypervisor-Services-Doku. Moderater Code, aber **geräte-iterationsintensiv** zu testen.
2. **KERNAL + exaktes MAP-Save/Restore** (`hyppo_get/set_mapping $76`, 45GS02-Flat-
   Adressierung). Fragil (siehe start-path-Notizen); KERNAL-OPEN bleibt im MAP-Fenster
   riskant.
3. **Direkter SD/FAT32** (wie mega65-libc). Zu groß.

## Prototyp-Stand (hyppo-DOS-Traps, ~20 Geräte-Runden, Border-Checkpoint-Diagnostik)

**Trap-Mechanismus funktioniert** (auf echter HW bestätigt): Register A/X/Y/Z setzen, dann
`STA $D640` + **`NOP`** (Pflicht), Ergebnisse danach in A/X/Y/Carry. `LDZ #imm` = `A3`.
Erfolg = Carry SET (`sec`), Fehler = Carry CLEAR (`clc`), Code via `geterrorcode`→A.

**Trap-Tabelle (A-Wert = der `;; $XX`-Kommentar in dos.asm; A&$7E indiziert):**
setname `$2E`, opendir `$12`, readdir `$14`, openfile `$18`, readfile `$1A`, closefile `$20`,
findfirst `$30`, findnext `$32`, findfile `$34`, **loadfile `$36`** (find+open+read in einem,
X:Y:Z=24-Bit-Ladeadresse), geterrorcode `$38`, cdrootdir `$3C`, selectdrive `$06` (X=Laufwerk).

**Was auf HW funktioniert:** `selectdrive(0)` ✓, `cdrootdir` ✓, `setname("DEMOLIB")` ✓
(Carry je gesetzt). Die rohe Datei `DEMOLIB` (172 B) liegt bestätigt auf der SD-Wurzel.
**Wichtig: hyppo-DOS liest SD-FAT32-Dateien, NICHT das Innere eines gemounteten D81;** und
**`selectdrive(0)` ist nötig**, sonst `findfile`→`$05 not_two_fats` (FS nicht ausgewählt).

**BLOCKER:** Nach erfolgreichem selectdrive+cdrootdir+setname scheitern `findfile` (Code
`$FB`) und `loadfile` (Code `$67`) — beides **keine dokumentierten `dos_errorcode_*`**
(konsistent über Runs, also deterministisch, evtl. aus der SD/FAT-Schicht durchgereicht
oder Lade-Adress-/DMA-Problem). Nächste Hypothesen: (a) findfirst `$30` statt findfile
nutzen (dokumentierter Namens-Suchpfad); (b) Lade-Adresse für loadfile prüfen (DMA-Ziel,
evtl. nicht bank-0-Pointer wie erwartet); (c) interne find-Routine von readfileintomemory
(findfirst vs findfile) gegenlesen; (d) ob `dos_error_code` Werte aus sd/fat durchreicht.

## Update nach manuellem Pfad (Runde ~22)

Auch der manuelle `findfirst($30)+openfile($18)+readfile($1A)`-Pfad scheitert: `findfirst`
meldet „nicht gefunden" mit FAT-/Disk-Fehler (Code-Nibble 5 → `$05 not_two_fats` oder
`$85 invalid_cluster`), obwohl selectdrive(0)+cdrootdir+setname davor laufen und die Datei
nachweislich auf der SD-Wurzel liegt (per `mega65_ftp dir` bestätigt; auch klein
geschrieben für LFN-Match getestet). loadfile gibt `$67`, findfile `$FB` — beides
nicht-dokumentiert.

**Korrektur nach Codex-Review:** `scripts/run-on-mega65.sh --run` ist ebenfalls nur
`etherload -r`; das ist **kein** alternativer BASIC65-Startpfad. Der rote Befund laesst
sich damit nicht durch den Wrapper allein entkraeften. Sinnvoller ist jetzt Isolation im
gleichen Startkontext: `setname`-Carry wirklich pruefen, Z-Laenge variieren
(exkl./inkl. NUL), Gross-/Kleinschreibung und 8.3-Dateinamen getrennt testen.

**Codex-Probe-Matrix:** `make hyppo-probe-matrix` baut minimalistische PRGs aus
`scripts/mega65-hyppo-load-probe.c`:

- `demolib-l6/l7/l8` und `DEMOLIB-l6/l7/l8`: gleicher Namepointer, Z-Laenge 6/7/8.
- `demolib-lsp-l11/l12` und `DEMOLIB-LSP-l11/l12`: 8.3/Extension-Varianten,
  Z-Laenge ohne/mit NUL.
- Die Probe nutzt bewusst `findfirst -> openfile -> readfile`, **nicht** `loadfile $36`,
  damit Namenssuche und DMA-/Ladeadresse nicht vermischt werden.
- Farbcodes: weiss = `setname`-Fail, rot = `findfirst`-Fail, tuerkis =
  `selectdrive/openfile`-Fail, gruen+BG `$08` = erstes Byte `'('` gelesen.

**Nächste Ansätze (für eine fokussierte Folge-Session):** (a) Matrix auf echter HW laufen
lassen und den ersten funktionierenden Namen/Z-Laengen-Vertrag in `io.c` uebernehmen;
(b) falls alle Varianten bei `findfirst` mit FAT-Fehlern scheitern, gegen ein bekannt
funktionierendes hyppo-Lade-Programm (z. B. ein MEGA65-Loader-Beispiel) byte-/trace-weise
vergleichen; (c) prüfen, ob ein vollständiger SD/FAT-Re-Init nötig ist (Partitionstabelle
neu lesen) oder ob ein wirklich anderer Startpfad als `etherload -r` gebraucht wird;
(d) MEGA65-Hardware-Debugging (m65-Monitor) statt Border-Farb-Diagnostik.

**Geknackt ist:** Trap-Mechanismus, Trap-Tabelle, selectdrive/cdrootdir/setname, die
Fehler-/Carry-Konvention. Das ist der Großteil; offen bleibt die find/read-FAT-Schicht.

## DURCHBRUCH (2026-06-30): nativer Load in xemu END-zu-END bestätigt

**Wendepunkt:** Statt weiter auf echter HW im Blindflug (Rahmenfarben) zu iterieren, läuft
die hyppo-Probe jetzt in **xemu (`xmega65`) gegen die echte SD** —
`/home/alex/.local/share/xemu-lgb/mega65/mega65.img` (4-GB-Image, FAT32-Partition @ LBA 2048
= Byte-Offset 1048576). Entscheidend: xemu macht einen **vollen hyppo-Kaltboot** (liest die
Partitionstabelle → `dos_disk_count` wird befüllt), **dann** wird das Test-PRG per `-prg`
injiziert. Und: **xemu loggt jeden HDOS-Trap im Klartext** (`HDOS: entering/leaving function
#$XX … carry SET/CLEAR`) — kein Rätselraten mehr über Rahmenfarben.

Setup (reproduzierbar):
```sh
# Testdatei in die FAT32-Wurzel der SD legen (mtools; hyppo liest SD-FAT32 direkt):
printf '(defun sq (x) (* x x))\n' > demolib
MTOOLS_SKIP_CHECK=1 mcopy -o -i mega65.img@@1048576 demolib ::DEMOLIB
# Probe im Kaltboot laufen lassen, Trap-Log lesen:
xmega65 -sdimg mega65.img -prgmode 65 -prg xload.prg \
        -headless -testing -sleepless -besure -fastboot -prgexit
```

**Ergebnis (alle sechs Traps carry SET, 23-Byte-Datei korrekt gelesen):**
```
selectdrive(0) → carry SET     cdrootdir → carry SET
setname        → carry SET, "selected filename is [demolib]"
findfirst      → carry SET     openfile  → carry SET (fd)
readfile       → carry SET, X=$17 (=23 Bytes, exakt demolibs Größe)
```

**Zwei harte ABI-Funde (vorher unbekannt, Ursache aller alten find/read-Fehler):**

1. **Der setname-Name-Puffer MUSS page-aligned sein.** hyppo liest den Namen ab der
   **Page-Basis** (`Y<<8`); das Low-Byte des X/Y-Zeigers wird verworfen. Mit einem
   nicht-ausgerichteten Namen (`$21A2`) las hyppo ab `$2100`, fand Müll (`invalid character
   $0B`), der Name kam **leer** an → `findfirst` → `$88 file_not_found`. Mit
   `__attribute__((aligned(256)))` las hyppo `[demolib]` korrekt und fand die Datei sofort.
   → In `src/io.c` umgesetzt: `static char namebuf[64] __attribute__((aligned(256)))`,
   Name vor `setname` dorthin kopieren.
2. **`selectdrive(0)`/`cdrootdir` müssen carry SET liefern** und tun das im Kaltboot-Kontext.
   Der alte „selectdrive scheitert immer"-Befund war **HW-/Start-kontextspezifisch**
   (`dos_disk_count==0` im etherload-Inject), **keine** generelle Unmöglichkeit.

**Damit ist die Frage „lösbar oder unmöglich?" beantwortet: LÖSBAR, bewiesen.** Der native
Lade-Pfad funktioniert vollständig, sobald das Programm in einem Kontext mit befüllter
Disk-Liste läuft. `src/io.c` (`-DMEGA65_HYPPO_LOAD`) enthält jetzt das korrigierte Binding
(beide Fixes), kompiliert sauber, Default weiterhin AUS.

**Einzig offen — kein Sprach-/Code-Problem, sondern Deploy:** Liefert der **reale**
MEGA65-Start (etherload-Inject) `dos_disk_count > 0`? In xemu ja (Kaltboot vor Inject); auf
echter HW gab Codex' (nicht-page-alignte) Probe selectdrive carry CLEAR. Nächster Schritt:
**die korrigierte Probe einmal auf echter HW** laufen lassen. Falls selectdrive dort weiter
CLEAR gibt, ist die Lösung ein anderer Start-/Ladepfad (z. B. PRG von der SD über den
MEGA65-eigenen Loader statt etherload-Inject), nicht eine Code-Änderung.

Beweis-Log: `native-load-proof.log` (im Session-Scratchpad gesichert).

## FINALE Root Cause + Entscheidung (Runde ~26, mit Codex' gehärteter Probe)

> **Überholt durch den Durchbruch oben.** Der hier beschriebene „selectdrive scheitert
> immer"-Befund stimmt nur für den etherload-Inject-Kontext auf echter HW; im Kaltboot
> (xemu, und vermutlich jeder normal gestartete Pfad) ist `dos_disk_count > 0` und der
> komplette Lade-Pfad läuft. Bleibt als Historie stehen.

**Echte Wurzel, jetzt sicher:** `selectdrive(0)` scheitert **konsistent**, weil
`dos_disk_count == 0` (Quelle: `dos_set_current_disk` prüft `cpx dos_disk_count`, sonst
`no_such_disk $80`). Die Disk-Liste wird **nur** von `dos_read_partitiontable` befüllt —
**kein User-Trap**, läuft nur im vollen hyppo-Kaltboot. In unserem Programm-Kontext ist sie
**null**. **Reframe:** Claudes frühere „selectdrive ok"-Läufe waren Fehlmessungen (alte
Probe prüfte die Carry nicht); selectdrive war **von Anfang an** gescheitert, und die
nachgelagerten `$67`/`$FB` waren bloß Müll vom Arbeiten ohne Disk. Codex' gehärtete Probe
(setname-Carry geprüft, Fehlercode-Anzeige) hat das aufgedeckt.

**Getestete Start-Varianten — alle `dos_disk_count == 0`:** `etherload -r`, `-m`+`-r`,
`mega65_ftp dir`+`-r`, Kaltstart+`-r`, **`-j` (reset-frei)**. Auch der reset-freie `-j`
(Boot-DOS-Zustand erhalten) zeigte selectdrive-Fail → der DOS-Zustand ist selbst direkt
nach Boot in unserem Programm-Kontext nicht sichtbar. (Hyppo/HDOS-Version laut User 1.2/1.3
— Standard, ändert nichts.) Es ist **nicht** Name/Länge/loadfile/find/etherload-vs-RUN.

**ENTSCHEIDUNG (mit User): native disk-`load` VERTAGT.** Keine Regression in den C64-Modus
(verlöre 80-Spalten, Banking/8-MB-Pfad, MEGA65-HW — gegen das Projektziel). Native REPL
bleibt (load = sauberer Fehler-Stub; `io.c`-hyppo-Binding fertig + gated). MVP nutzt
`load_source`/eingebettete Libs. Native disk-load = **fokussierter Folge-Block** mit
besseren Werkzeugen (m65-Monitor; Vergleich gegen ein bekannt funktionierendes hyppo-
Lade-Programm; klären, wie ein normal gestartetes MEGA65-Programm `dos_disk_count` sieht —
vermutlich braucht es einen Start-/DOS-Init-Pfad, den `etherload` nicht liefert).

## GELÖST (offline) — F011/SD-Mount-Leser (2026-07-01)

Der produktions-korrekte Pfad (kein ROM/KERNAL/hyppo-DOS) liest die **gemountete D81**
direkt. In `src/io.c` integriert hinter `-DMEGA65_F011_LOAD`. **End-zu-End in xemu bewiesen:**
`(load "demolib")` → `(sq 5)` = 25; `io_load_file("demolib")` liefert exakt die 23 Bytes.

**Mechanismus (alles validiert):**
1. `mega65_io_enable()` — Knock `STA $D02F=#$47` dann `#$53` (erweitertes I/O freischalten;
   **war der Hauptfehler** der früheren Versuche).
2. Mount-SD-Basis aus **`$D68C-$D68F`** (32-bit, die SD-Sektornummer der gemounteten Image #0).
3. Roh-SD-Read: Sektor → `$D681-$D684`, `STA $D680=#2`, warten `while (PEEK($D680)&3)`.
4. **Puffer ins `$DE00`-Fenster: `STA $D680=#$81`**, dann 512 B aus `$DE00` lesen.
   (CPU-Flat-Read von `$FFD6E00/C00` gibt 0 — nur das `$DE00`-Fenster funktioniert.)
5. **1581-Parser:** 256-B-Logiksektoren (2 je 512-B-SD-Sektor; `lin=(T-1)*40+S`,
   `sd=base+lin/2`, Hälfte=`lin&1`). Directory ab Track40/Sektor0-Link, 8 Einträge/Sektor
   (`+2` Typ, `+3/+4` erste t/s, `+5..20` Name, $A0-gepaddet, GROSS-PETSCII). Datei über
   Sektorkette (`+0/+1` = next t/s; `t=0` → letzter, `s` = letzter Byte-Offset, Daten ab `+2`).

**Offline-Harness (so reproduzieren):** xemus *externer* Mount ist virtuell (roh-SD sieht
ihn nicht). Stattdessen Test-D81 SD-**intern** injizieren und `-defd81fromsd` nutzen:
`dd`/python schreibt die D81 an Image-Byte `11552*512`; `hdos/mega65.d81` wegnehmen;
`xmega65 -sdimg … -defd81fromsd -prg test.prg …`. Dann ist `$D68C-F`=11552 und alles real lesbar.

**Noch offen (HW, gebündelt):** (a) reale Mount-Basis-Semantik — auf echter HW gab der
Freezer-Mount `base`=229492, aber `base+780` ≠ Header (entweder FAT-**Fragmentierung** der
D81-Datei oder andere Basis-Bedeutung beim externen Mount). (b) Fragmentierte Dateien
brauchen FAT-Chain-Folgen (oder kontiguierte D81 voraussetzen). → korrigierte Probe einmal
auf echter HW mit Freezer-Mount prüfen; falls fragmentiert, FAT32-Cluster-Kette ergänzen.
**Deploy:** F011-REPL baut bei `-DHEAP_CELLS=1150` (der Leser braucht ~184 B mehr als der Stub).

## Direkt-Disk via F011 / Sektor-Lesen (2026-07-01)

**Warum nicht die bequemen Schichten:**
- **hyppo-DOS** (der xemu-„Durchbruch"): auf echter HW **tot** — `selectdrive(0)` gibt
  `$80 no_such_disk`, weil `dos_disk_count==0` im Programm-/etherload-Kontext und auch nach
  normalem Boot (mega65_ftp-Reset, Freezer-Mount, `RUN`). Der xemu-Erfolg war ein
  xemu-Artefakt (dessen HDOS-Schicht befüllt die Disk-Liste). Real-HW: konsistent türkis.
- **C64-KERNAL** (`cbm_k_open`/`cbm_k_load`): im C65-Nativ-Modus erreichen die C64-Kompat-
  Routinen das **interne Laufwerk nicht** — `OPEN` → Fehler **2**, `LOAD` → **hängt**
  (wartet auf IEC-Serienbus). `RUN"…"`/`DLOAD` aus BASIC funktioniert, nutzt aber die
  **C65-native DOS im ROM** — in Produktion blenden wir das ROM für RAM aus → nur Stopgap.
- **Konsequenz:** produktions-korrekt ist der **direkte F011-Zugriff** (kein ROM-/hyppo-/
  IEC-Bedarf). Genau der Disk-Controller, der die gemountete D81 bereitstellt.

**GEKNACKT & offline am echten MBR bewiesen — der Sektorpuffer-Lesemechanismus:**
1. `mega65_io_enable()` — Knock `STA $D02F=#$47` dann `#$53` (erweitertes I/O/VIC-IV freischalten).
   **War der Hauptfehler: ohne diesen Knock sind die erweiterten Register/Puffer tot.**
2. Sektor lesen (roh-SD): Sektornr. nach `$D681-$D684` (32-bit LE), `STA $D680=#2`,
   warten `while (PEEK($D680) & 3)`.
3. **Puffer ins `$DE00`-Fenster mappen: `STA $D680=#$81`** (Unmap `#$82`). DIESES Mapping
   war das fehlende Stück beim F011-Versuch.
4. 512 Bytes aus `$DE00-$DFFF` lesen. (CPU-**Flat**-Read von `$FFD6E00`/`$FFD6C00` via
   `lda [zp],z` liefert **0** — nur das `$DE00`-Fenster bzw. DMA funktioniert.)
   Verifiziert: roh-SD-Sektor 0 → `$DFFE/$DFFF = $55 $AA` (MBR-Signatur), exakt wie im Image.

**Zwei noch UNFERTIGE Wege zum Lesen der gemounteten D81 (HW-Befunde):**
- **Weg A — roh-SD über Mount-Register:** `$D68C-$D68F` = SD-Sektor der gemounteten
  Image #0. Auf echter HW echte Sektornr. (`229492`, nicht der virtuelle Pool wie in xemu).
  ABER `base+780` (linearer D81-Offset des Track-40-Headers) trifft **nicht** den Header
  (`28 03 44…`) — also ist `base` nicht der Datei-Anfang ODER die D81-Datei liegt
  **fragmentiert** auf der FAT32 (dann muss man der Cluster-Kette folgen). Offen.
- **Weg B — F011:** `read sector` (`$D080=#$60` Motor, spinup `$D081=#$20`, Track/Sektor/
  Seite `$D084/85/86`, read `$D081=#$40`) setzt **RDREQ** (Erfolg), aber `$D680=#$81` mappt
  den **SD-Puffer**, nicht den F011-Puffer (`$FFD6C00`). Es fehlt: F011-Puffer ins `$DE00`
  mappen ODER per **DMAgic** aus `$FFD6C00` kopieren. Offen.

**xemu-Limitation:** extern gemountete D81 (`-8` / `hdos/mega65.d81`) ist ein **virtueller**
Mount-Pool (ab Sektor 8388608); rohe `$D680`-Reads sehen ihn **nicht**. Offline lässt sich
daher nur der Mechanismus (roh-SD aufs Image) prüfen, nicht das Lesen der gemounteten Disk.
Für Offline-Tests müsste die D81 SD-**intern** im Image liegen (Default bei Sektor 11552).

**Nächste Schritte (Hintergrund-R&D, Quellcode statt Raten):**
1. mega65-core hyppo lesen: wie `dos_d81attach`/Mount die SD-Sektornr. ablegt (Semantik von
   `$D68C-F`) und ob FAT-Fragmentierung berücksichtigt werden muss.
2. F011-Sektorpuffer-Zugriff klären: Register/Bit, das `$FFD6C00` ins `$DE00` mappt — sonst
   DMAgic-Kopie `$FFD6C00 → RAM`.
3. Dann minimaler 1581-Leser (Header/BAM Track 40, Directory-Kette, Datei-Sektorkette).
4. In `src/io.c` als `__MEGA65__`-Pfad hinter einem Flag, Default erst AN wenn HW-grün.

## Plan

- **Nächster Schritt:** hyppo-DOS-Trap-Spezifikation beschaffen (mega65-core/Doku), dann
  ein minimales `open+read+close` in `io.c` (`__MEGA65__`-Zweig) prototypen, mit Border-
  Checkpoint-Diagnostik auf dem Gerät iterieren.
- Bis dahin: load_source für eingebettete Libs (Phase 0, Codex' Harness) + die saubere
  Fehlermeldung auf Nativ. Disk-`load` ist ein **fokussierter eigener Block**.
- Langfristig entlastet das flache 8-MB/Banking-Modell (§4.3) auch hier (mehr RAM, klarere
  Memory-Map).
