# Workbench Gate

Stand: 2026-07-11. Dieses Dokument pinnt den aktuellen Workbench-Sanierungs-WIP
und die Gates fuer `mvp-ship`. AP4 ist implementiert, layout-frozen und
hardwareabgenommen. Commit `5ce25a2` ist sauber als Ship-v5 promotet; seine an
Manifest-SHA
`67c5943259ed2bd3d849a33c6f7909bc16962c1c88271baf32dd36a1058085dd`
gebundene verified-only Live-G5-Matrix ist gruen.

AP6 ist ebenfalls host-, produkt- und hardwareabgenommen. Das strikt
verifizierte Ship-v5-Paket aus `f64bb41` mit Manifest-SHA
`7d9873915e90102824fad7b379c938f8724d7b9f47770cab4adc5e48544ccb94`
bestand zwei Create-Vorgaenge in einer Session, Replace, Remount, Reset ohne
D81-Reupload und den exakten Load beider Dateien.

AP8.1 bindet den aktuellsten engen Live-Beleg an das saubere Ship-v5 aus
Commit `78083d6` und Manifest-SHA-256
`275723fb7259261c9606cee6a0dcc17c593a4cbf9c77f44b482d7cd031d5e211`.
Die zwei frueheren `every`-/`some`-HW-Repros bestanden in gegenlaeufiger
Reihenfolge nach Persistence-Remount und nach langem IDE+IDEX-Zustand. Der
Receipt unter `tests/bytecode/runtime/evidence/ap8.1-g5-78083d6/` ist auf
diesen Higher-Order-Scope begrenzt und wird von `make
runtime-known-open-check` inklusive Manifest-, Readback-, SHA- und
Screen-Oracles fail-closed validiert. Er erweitert keinen Releaseclaim.

Die Releasekonvergenz ist enger als die Menge interner Kandidaten: Nur die
Workbench unter Dialekt v2 darf Releaseprodukt werden. Dialekt-v1-Pakete sind
eingefrorene Evidenz; Runtime-Core-v2 ist ausschliesslich ein interner,
nicht-shippbarer Beweis. Kein Runtime-Receipt darf Workbench-Linkbudget,
Workbench-G5 oder den globalen Release-Gate ersetzen.

## Kandidat

Target: `workbench-product`; flache Referenz:
`mvp-vm-stdlib-einsuite-core-workbench`.

Kanonisches Profil: `config/workbench.mk`. Es enthaelt die expliziten
Produktflags, Budgets, Suite und Artefaktpfade ohne Vererbung aus historischen
Profilen. Die zugehoerige Stdlib wird unter
`build/bytecode/profiles/workbench/` erzeugt. Der aktuelle Produktlink
kombiniert Guard-Resident, Bank-5-Bootstage und den profilgebundenen
Runtime-Overlay-Katalog im Attic RAM; der aktuelle Footprint steht unten.

Alias:

```sh
make workbench-candidate
make workbench-candidate-footprint-report
```

Feature-Schnitt:

- REPL
- manueller IDE-Start via `(edit)`
- lcc
- Packed-String-Arena
- Disk-Load/Save
- `load-lib`
- `compile-string` als kleiner FASL/L65M-Backend-Pfad
- Buffer-Persistenz-API in der ladbaren IDE-Lib:
  `dir`, `load-file-to-buffer`, `save-buffer-to`, `eval-buffer`,
  `compile-buffer-to-lib` und `compile-file-to-lib`. Persistente Compile-APIs
  tragen im Workbench-MVP explizit `to-lib`; der Editorbefehl `compile-load`
  macht `compile-buffer-to-lib` plus `load-lib`. Die Terminologie ist in
  `docs/ide-api-terminology.md` gepinnt.
- erster Editor-Minibuffer in der ladbaren IDE-Lib:
  `C-x C-f` fragt einen Dateinamen ab, `C-x C-s` speichert den aktuellen
  Buffer, `C-x C-w` schreibt unter abgefragtem Namen, `C-x C-b` wechselt
  Buffer ueber den Minibuffer, `C-x C-n`/`C-x C-p` zyklisieren direkt durch
  offene Buffer, `C-x C-d` oeffnet einen Directory-Buffer, `C-x C-k`
  kompiliert und laedt den aktuellen Buffer in einen abgefragten `fasl*`-Slot,
  `C-d` loescht forward im aktuellen Buffer, `C-f`/`C-b`/`C-n`/`C-p` sind
  Emacs-nahe Navigationsaliase fuer rechts/links/runter/hoch, `C-a`/`C-e`
  springen an Zeilenanfang/-ende, `C-j` ist ein Newline-Alias, `C-v`/`C-z`
  bewegen seitenweise, `C-x C-a`/`C-x C-e` springen an Bufferanfang/-ende,
  `C-k` killt den Zeilenrest, `C-y` yankt den einfachen Kill-Ring, `C-s`
  sucht im aktuellen Buffer, `C-l` springt zu einer Zeilennummer, `C-o`/`C-u`
  bewegen wortweise vor/zurueck, `C-w` killt das naechste Wort und `C-r`
  das vorige Wort; `C-SPC`/`C-x C-x`/`C-x C-r`/`C-x C-y` bieten eine
  einfache, auch mehrzeilige Mark/Region-Familie; `C-x x`/`C-x RET` oeffnen
  einen schmalen M-x-Minibuffer; die
  Statuszeile zeigt die aktuelle 1-basierte Zeile als `L<n>`
- einstufige REPL-History per CRSR-hoch am leeren Prompt
- laengere Single-Line-REPL-Eingaben (`REPL_BUF_MAX=192`, kein automatisches
  Paren-basiertes Weiterlesen)

Nicht enthalten als Produktpfad:

- native Disk-Source-`LISP65_FASL`-Schicht
- Canary-/Wipe-Instrumentierung des separaten Stack-Probes
- EDMA-Scroll default

## Gepinnte Werte

```text
NAMEPOOL=10208
MAX_SYM=752
SYMPOOL_EXT_OFF=0xc680
VM_DIR_MAX=608
GC_ROOTS=128
REPL_BUF_MAX=192
STR_ARENA_SIZE=0x2480
DISK_EXT_BASE=0x6900
DISK_EXT_FILE_MAX=0x9600
guard_product_overlay_base=0xc22c
resident_prg_bytes=39279
combined_preload_bytes=39494
runtime_overlay_image_bytes=54105
boot_overlay_bytes=1588
boot_stack_gap_bytes=1952
post_boot_reserve_bytes=2091
post_boot_reserve_target_headroom=555
runtime_overlay_slots=38/64
resident_island_immutable_bytes=1108
resident_island_annex_bytes=260
resident_island_reserve_bytes=680
error_text_slice_bytes=1290/1320
functions=346
cases=190
objects=347
```

Alle 38 Slices teilen ueber ein Linker-`OVERLAY` dieselbe Bank-0-VMA und haben
getrennte LMAs im L65R-v1-Katalog. Dessen historischer Format-Tag bleibt `3`;
physisch liegt das 64-KB-Image reset-stabil und power-volatil ab `$08000000` im
Attic RAM. Der Split-Boot fuehrt `eval_init` im
1409-B-Bank-5-Overlay aus und verwendet Slots 33-35 fuer den
profilgebundenen Stdlib-Fastpath; Slot 36 enthaelt L65E. Slot 37 installiert
die residente Insel fail-closed. Ihr dynamisch hinter Slot 37 erzeugter
Seed-LMA ist build-only und kein ausgelieferter Katalogeintrag. Die gemeinsam gebaute
Stdlib wird durch Buildgate, Contract-SHA, Build-ID, Laenge und genau eine CRC
vor der ersten Bank-5-Mutation gebunden. Disk-Libs durchlaufen dagegen vor
jeder sichtbaren Mutation den vollen 21-Phasen-Preflight.

Der Fehlervertrag umfasst 59 stabile Codes. L65E liefert Sparse-Klartext fuer
42 gebaute Workbench-Codes, 15 Profil-Ausschluesse sind explizit `not-built`,
Codes 46 und 47 werden resident ausgegeben, und das ELF-Drift-Gate blockiert
unklassifizierte Emissionen.
`Ehh` bezeichnet auch ohne funktionierendes Overlay den stabilen Hex-Code
`hh`. Code 46 besitzt zusaetzlich den residenten, allokationsfreien Hinweis
`E2e catalog missing; redeploy`, weil L65E bei fehlendem Attic selbst nicht
erreichbar ist. Der profilgebundene HW-Math-Ersatz spart gemessen 519 B.

Das harte Post-Boot-Minimum von 1024 B und das unveraenderte 1536-B-Ziel sind
mit 1811 B gruen. Die Insel `$1800..$1fff` belegt 1108 B fuer acht kalte
Koordinatoren und 260 B fuer den Rootstack-Annex; 680 B bleiben eingefroren.
HW-Math hat seine 519 B bereits beigetragen. Die 385 B Primitivnamen liegen
bereits in `.lisp65_boot.names` und ergeben keinen residenten Reclaim.

Diese Werte sind ein MVP-Pin, keine dauerhafte Architekturreserve. Der Pin nutzt
`LISP65_SYMFN_EXT`: die Funktionszellen der Symboltabelle liegen in EXT-RAM.
Der RUN/STOP-IDE-Toggle ist nicht resident; der IDE-Einstieg ist `(edit)`.
Die REPL-History passt nur als Workbench-Sparpfad (`LISP65_REPL_HISTORY_IN_BUF`):
kein separater History-Puffer, sondern Wiederholung des vorhandenen REPL-Buffers
per CRSR-hoch. Der AP1-Reader-Nachzug und identisches Code-Folding ergeben den
oben gepinnten aktuellen WIP-Footprint. Der groessere
REPL-Buffer ist bewusst nur BSS/Stack-Gap: er erlaubt laengere einzeilige
Formen, bringt aber noch keine RETURN-Fortsetzung bei unbalancierten Klammern.
`VM_DIR_MAX=608` deckt den v2-Kompositionspfad ab: Resident
`347 -> align8=352`, IDE-Core mit 150 Funktionen -> 502, IDEX mit 29
Funktionen -> 533 und der gemessene M65D-Kern mit 35 Funktionen -> 571,
post-align 576. 32 Nutzerslots bleiben frei. `ide-capacity-check` bindet M65D als
`measured-manifest-v1`, nicht mehr als Planungsreserve.
`MAX_SYM=752`, `NAMEPOOL=10208` und `SYMPOOL_EXT_OFF=0xc680` decken
Resident+IDE+IDEX+M65D mit 39 Symbolslots und 490 Namensbytes Nutzermarge. Bei
8-KB-Namepool scheiterte der Demo-Compile trotz `symbol-count=616/640` an
`too many symbols`; nach `eval-buffer` reichte auch `NAMEPOOL=9248` nicht mehr
fuer den kombinierten Stdlib+IDE-Lib-Load. Der aktuelle Pin nutzt das externe
Symbol-Layout deshalb bis zur Bank-5-Grenze aus: `SYMPOOL_EXT_OFF+NAMEPOOL`
bleibt bei `$ef20`, also bleiben die nachgelagerten Symboltabellen stabil.
Fuer den Save-New-Pfad waechst die IDE-Lib ueber das alte Diskfenster hinaus;
Workbench pinnt deshalb `STR_ARENA_SIZE=0x2480`, `DISK_EXT_BASE=0x6900` und
`DISK_EXT_FILE_MAX=0x9600`. Das verliert 384 Bytes String-Arena je Halbfenster
und gewinnt 768 Bytes Disk-Lib-Scratch.

Das Disk-Lib-Budget-Gate prueft zusaetzlich das VM-Codepuffer-Limit fuer
on-demand geladene IDE-Bytecode-Objekte. Aktueller Stand:

```text
workbench-disk-lib-budget: PASS resident=319 start=320 disk_lib=181 disk_libs=2
load_used=501 post_align=504 cap=552 headroom=51 post_headroom=48
codebuf=56 codebuf_required=56 codebuf_headroom=0 codebuf_worst=ide-apply-command
ext_code_peak_used=43130 ext_code_peak_headroom=8550
ext_code_post_used=28942 ext_code_post_headroom=22738
runtime_symbols=648 max_sym=720 symbol_headroom=72
runtime_namepool=8539 namepool=9536 namepool_headroom=997
```

Das `LISP65_SYMFN_EXT`-Kostenmodell ist als Host-Trace im Gate. Es ist keine
zyklusgenaue MEGA65-Messung, zaehlt aber die dynamischen Bytecode-`CALL`- und
`TAILCALL`-Aufloesungen; jede davon liest im Workbench-Profil `symfn` aus
EXT-RAM. Aktueller Pin:

```text
make workbench-symfn-dynamic-report
scenarios=15
total_dynamic_instructions=127961
symfn_ext_dynamic_resolutions=8939
symfn_ext_unique_targets=145
symfn_ext_unique_call_sites=293
```

Dominant sind kalte Renderpfade: `ide-render-cold-short` verursacht 2498 und
`ide-render-cold-25-lines` 2627 `symfn`-Aufloesungen; interaktive Einzelschritte
liegen deutlich niedriger (`ide-step-self-insert` 32,
`ide-step-delete-cached` 16). Die drei Compiler-Szenarien
`lcc-compile-small-defun`/`branch`/`closure` liegen bei 94/233/192.

Die L65M-Kosten und die semantische Neutralitaet der Optimierungen sind
permanente Produktgates:

```text
make l65m-verdict-equivalence-gate
verdicts=90090 mismatches=0 bulkread_fixtures=56

make workbench-l65m-transport-ops-report
slice_loads=21 crc_runs=126 p05_dma=1016/1500 total_dma=13968/15000

make workbench-l65m-commit-ops-report
slice_loads=7/7 crc_runs=42 source_reads=11620/15000
preflight_symbol_dma=31250/40000 commit_namepool_dma=222818/250000
materializer_depth=9 scalar_frames=486/512
```

Phase 05 verwendet 4096 Hash-Buckets in 512 B und 120-B-Blockreads, endet bei
Hashgleichheit aber immer im exakten Vergleich. Sein MOS-Slice liegt exakt bei
1792/1792 B. Der phase-major Commit ersetzt 5145 Per-Item-Loads und 30870
CRC-Laeufe des historischen Ablaufs. Diese Zahlen sind Budgets und Driftgates,
nicht nur einmalige Messwerte.

## Automatisches Gate

Die Standardkette ist kumulativ:

```sh
make check-source   # G0
make check-host     # G1, enthaelt G0
make check-product  # G2, enthaelt G1
make check          # Alias fuer G2
```

G0 prueft Syntax, statische Vertraege und Generator-, Ship-Verifier-, Insel-
sowie Bank-0-Lifetime-Selftests.
G1 ergaenzt native Host-Smokes, Sanitizer, Oracles und Differentialtests. G2
ergaenzt Workbench-Build und -Suite, Footprint- und Runtimebudgets,
den policybasierten Bank-0-Lifetime-/Insel-Driftcheck, `SYMFN_EXT`-Exposure,
L65M-Verdikt-/Bulkread-/Ops-Gates, IDE-Lib, D81-Konsistenz sowie die
Offline-Pruefung des lokalen Ship-Kandidaten.
`workbench-gate` ist ebenfalls ein Alias fuer G2.

Normative Semantikvertraege laufen ueber
`config/semantic-contracts.json`: `semantic-contracts-g0` fuehrt reine
Modelladapter aus, `semantic-contracts-g1` die nativen und Drift-Adapter. Das
G1-Make-Ziel erzeugt zuvor alle von `fixture_binding=generated` abhaengigen
Artefakte; ein direkter Runner-Aufruf ersetzt diesen Build-DAG nicht.
`semantic-contracts-g2` ist Bestandteil von `check-product`, meldet ohne
Product-Claim jedoch `SKIP`. Ein Product-Claim wird nur mit einem
fixture-gebundenen, separat freigegebenen G2-Repo-Adapter akzeptiert.

Emulator und Hardware sind getrennt:

```sh
make check-emulator          # G3: derzeit explizit nicht verfuegbar
make check-hardware-dry-run  # G4: nur Deploy-Kommandos/Artefakte
make check-hardware          # G5: echte MEGA65-Abnahmematrix
```

G4 und G5 sind kein Bestandteil von `make check`. Der Kompatibilitaetsalias
`workbench-persistence-gate` kombiniert G2 und G4. Historische Referenzpfade
laufen explizit ueber `make check-reference`; bekannte rote und experimentelle
Diagnosepfade ueber `make reference-diagnostics`.

Vor dem eigentlichen Gate kann die lokale Bereitschaft read-only geprueft
werden:

```sh
make doctor                              # Default: G2, Text
make doctor DOCTOR_GATE=G1
make doctor DOCTOR_GATE=G5 DOCTOR_FORMAT=json
```

Zulaessig sind G0, G1, G2, G4 und G5 sowie `text`/`json`. Der Doctor schreibt
nicht in den Worktree und kontaktiert weder Emulator noch MEGA65. Fuer G5
prueft er die lokalen Live-Tools; Device, Ethernet-Erkennung und Remote-Modus
bleiben als Hardwarezugang `deferred`, der Gesamtstatus lautet
`ready-with-deferred`, und die eigentliche Abnahme muss im echten G5 folgen.

Historischer Ship-v3-Verifikationsstand vom 2026-07-10:

```text
G0-G2  make check                         PASS
G3     make check-emulator                NOT AVAILABLE (erwartet)
G4     make check-hardware-dry-run        PASS
G5     make check-hardware                PASS (package a82d68f)
```

Das Paket wurde aus dem sauberen Commit
`a82d68f9502c5e42267d33e1d5e528b760bb61ff` promotet; Manifest-SHA-256 ist
`cee107a1b4de25a3deb2443fee824341b1dfbef841b109dbb01b9ca975e93f40`.
Guard, UX, BAM-Read und M2-M7 bestanden auf echter Hardware. Ein transienter
`mega65_ftp`-No-response unterbrach den Aggregate vor dem M4-Load-Oracle; die
vollstaendige M4-Wiederholung und M5-M7 bestanden danach mit demselben Paket.
Ein zweiter, unveraenderter `make check-hardware`-Gesamtlauf bestand
anschliessend die komplette Matrix in einem Prozess mit Exitcode 0.
Ohne strikt verifiziertes Manifest bricht `check-hardware` weiterhin vor jeder
Hardwareaktion ab.

Fuer den historischen Ship-v4-Pin sind G0-G2, Clean-Tree-Promotion und G4-Dry-run
gruen. Der Link misst 39644 B Resident, 1653 B Boot-Gap, 3048 B Runtime-Gap
und 1598 B Post-Boot-Reserve; der isolierte Doppelbuild erzeugt alle zehn
Paketdateien byteidentisch.
Commit ist `3f02391b6d462e5511ca93ece3dad9d7183c099c`, Manifest-SHA-256
`456d27134ec20e92f3507e340a9e8a0093460c532f943f82b601dc1f9823684a`.
Live-G5 bleibt offen. Auf Live-Hardware muessen die
einmalige CRC ueber die 34325-B-Stdlib und die Latenz von `C-x C-k` ueber
Compile, drei LCC-Slices und Load-Lib-Preflight/Commit gemessen werden.

Der AP4.4-Overlaypfad bleibt eine getrennte instrumentierte Diagnose:

```sh
make workbench-overlay-stack-probe
make hw-workbench-overlay-stack-smoke-dry-run
make hw-workbench-overlay-stack-smoke
```

Build, Dry-run und echter Hardware-Smoke sind gruen. Gemessen wurden 452 B
Softstack-Marge und 202 B Page-1-Rest; Wipe, IDE-Lib, GC, VM-/Treewalk-
Bruecken und Fehlererholung bestanden. Seine Canary-/Wipe-Instrumentierung ist
nicht Teil des Produktpakets.

Die anschliessende Guard-Variante ist ebenfalls statisch und live gruen:

```sh
make workbench-overlay-stack-guard
make hw-workbench-overlay-stack-guard-smoke-dry-run
make hw-workbench-overlay-stack-guard-smoke
```

Die historische Variante misst 39862 B Resident, 2245 B Overlay, 631 B Boot-Gap und 1427 B Post-
Boot-Reserve. Der Guard prueft `__heap_start + 24`; der Hardwarelauf besteht
IDE-, VM-Bridge-, GC- und Abort-Proben ohne Fehlalarm. AP4.6 hat diese Variante
als kanonischen Workbench-/Ship-Eingang promotet. G4 deployt den lokalen
Candidate; G5 beginnt mit `verify-ship` und verwendet ausschliesslich
`build/ship/`. Der finale ABI-gebundene Produktlink misst nach der Make-/Ship-
historischen Integration 39891 B Resident, 601 B Boot-Gap und 1398 B Post-Boot-Reserve; die
harten Grenzen bleiben unveraendert gruen.

## Ship-Paket

Ein lokaler WIP-Kandidat darf aus einem dirty Tree entstehen:

```sh
make mvp-ship-artifacts
```

Er liegt unter `build/ship-candidate/`, traegt den Status
`unverified-candidate` und wird von G2 als Paketkonsistenzcheck geprueft. Dieser
Pfad ist keine Promotion und keine Release-Freigabe.

Die strikte Promotion lautet:

```sh
make mvp-ship
```

Sie fuehrt einen Clean-Tree-Preflight aus, startet das kumulative G2, vergleicht
danach Commit, Tree und Worktree erneut, promotet den Kandidaten atomar nach
`build/ship/` und ruft die strikte Offline-Verifikation auf. Aendern sich die
Quellen oder ist der Tree dirty, bricht der Pfad ab. Der Paketstatus danach ist
`g2-verified-candidate`; G3 und G5 sind damit nicht behauptet und es handelt
sich noch nicht um ein Release.

Ship-v5-Paketinhalt in beiden Verzeichnissen, exakt zehn Dateien:

- `build/ship/lisp65-mvp-workbench.prg`
- `build/ship/lisp65-mvp-workbench.blob.bin`
- `build/ship/lisp65-mvp-workbench.overlays.bin`
- `build/ship/lisp65-mvp-workbench.d81`
- `build/ship/manifest.json`
- `build/ship/workbench-d81-manifest.txt`
- `build/ship/mvp-vm-stdlib-footprint.txt`
- `build/ship/stdlib-artifact-manifest.json`
- `build/ship/resolved-profile.txt`
- `build/ship/toolchain-report.txt`

Fuer den unverifizierten Pfad ist jeweils `build/ship-candidate/` statt
`build/ship/` einzusetzen. `manifest.json` hat das Format
`lisp65-workbench-ship-v5` und enthaelt fuer jedes ausgelieferte Artefakt
relativen Pfad, Groesse und SHA-256 sowie Commit-/Tree-/Worktree-Provenienz,
aufgeloestes Profil, Toolchain-Report, Gatezustand und Paketstatus. Der
Offline-Check

```sh
make verify-ship
```

akzeptiert nur das strikte `build/ship/`-Paket und erkennt unter anderem
fehlende, zusaetzliche, manipulierte oder ueber Symlinks umgeleitete Dateien.
Zusaetzlich kreuzprueft er Format, Rolle und Suite des inneren
`stdlib-artifact-manifest.json` gegen den Stdlib-Praefix des Combined Preloads.
Nullpadding, L65O-Descriptor, Payload/CRC, ABI/Build-ID, Resident-/Preload-
Paar, Stage-Limit und alle 38 Runtime-Slots werden offline aus den zehn Dateien
rekonstruiert. Der Attic-Preload bindet 28-Bit-Adresse, Laenge, Whole-image-CRC,
SHA, Build-ID, Reset-/Power-Semantik und `redeploy-required`. Das
`error_texts`-Binding pinnt Slot 36, 42 aktive L65E-Codes, 15 bewusst nicht
gebaute Codes und die residenten Codes 46/47 als disjunkte vollstaendige Partition sowie
Tabellenoffset/-laenge, CRC, SHA, Contract-SHA und Build-ID.
Temporaere Slot- und Demo-Dateien des D81-Builds entstehen standardmaessig in
einem automatisch entfernten Temp-Verzeichnis ausserhalb des Pakets.

Der Doppelbuild-Check

```sh
make workbench-reproducibility-check
```

erzeugt zwei isolierte Guard-Builds und zwei getrennte Kandidaten unter
`build/reproducibility/`. Der Ship-v3-Lauf vom 2026-07-09 war gruen; der
historische Ship-v4-Lauf vom 2026-07-10 ist ebenfalls gruen und alle zehn
Paketdateien sind byteidentisch.

Der letzte strikt promotete Ship-v5-Pin wurde aus dem sauberen Commit
`4cff6b9562665765dbeab142660405f536a55fdf` promotet. Das Manifest hat SHA-256
`72a6cb508b29ac65c448a79620c6a82743bd1ec1fc5bc2015a31f67363d828bf` und den
Status `g2-verified-candidate`. Diese Werte sind historisch und werden nicht als
Provenienz des aktuellen AP4-Abschlussstands wiederverwendet.

Der aktuelle Pin stammt aus dem sauberen Commit
`5ce25a2b26ac1be03bd0a1ab1718329bb0c005bc`. Sein Ship-v5-Manifest hat SHA-256
`67c5943259ed2bd3d849a33c6f7909bc16962c1c88271baf32dd36a1058085dd` und
bleibt als immutable Buildartefakt `g2-verified-candidate`. G4 und der externe
Live-G5-Receipt referenzieren exakt diesen SHA. Stage A bestaetigte PRG, Bank 5
und Attic bytegenau; nach Reset/Remount blieben Attic und die installierte
Insel exakt. `load-lib "ide"` lieferte `overlay-ide-ok` in 10 s bei einem
12-s-Budget. Die restliche Guard-/VM-/GC-/Reader-/UX-/Persistenzmatrix bis M7
bestand ebenfalls mit diesem Paket. Commit `a5762e8` haertet anschliessend nur
die Eingabeverifikation der Persistenz-Harnesses und aendert den Produktpin
nicht.

Das D81 enthaelt den IDE-Core als `ide`, den optionalen Komfort-Tier als `idex`,
den COW-Persistenzkern als `m65d` sowie vorallokierte Compile-Zielslots: `an`,
`work`, `out`, `fasl0`, `fasl1`, `fasl2`.
Der Slot `demo` ist mit der kompakten Quelle `demos/d06-numbers.lisp`
vorbefuellt. Gepaddete Save-Ziele wie `work` werden beim Lesen erst auf ihre
effektive Laenge gescannt und dann begrenzt in Cons-Zellen materialisiert; der
HW-Roundtrip `save-buffer-to "work"` -> `load-file-to-buffer "work"` ist gruen.
Fuer Compile-Smokes dienen die vorallokierten Ziele `fasl0` usw. `save-buffer-to`
laedt M65D beim ersten mutierenden Aufruf und verwendet fuer Create und Replace
denselben COW-Pfad. Das Produktlimit betraegt 8192 B; Directory-Wachstum und
Power-Loss-Atomizitaet sind nicht Teil des Vertrags.

`make workbench-d81-bam-sanity` prueft die erzeugte D81 read-only gegen die
1581-BAM: BAM-Sektorlinks, Free-Count-vs-Bitmap und Directory-Blocksumme. Der
aktuelle Pin ist `free_blocks=2782`, `file_blocks=378`, `dir_entries=10`,
`track40_free=35`.

`make hw-workbench-bam-read-smoke` ist der zugehoerige read-only Live-HW-Pin:
Workbench per Etherload deployen, dann per JTAG-REPL die BAM-Sektoren T40/S1
und T40/S2 ueber `%disk-read-sector`/`%disk-byte` lesen. Erwartete Marker:
Beide Formen werden aus genau dem D81 abgeleitet, das der Lauf hochlaedt, und
im Receipt zusammen mit dessen SHA gebunden. Fuer das aktuelle R5-Testmedium
sind das `(t 40 2 40 35)` fuer T40/S1 und `(t 0 255 0 38)` fuer T40/S2; der
historische Lauf vom 2026-07-11 war mit seinem damaligen Medium bei S2 auf 39
gruen. Der Host-/D81-Anteil gehoert zu G2, der Deploy-Dry-Run zu G4 und die
echte Wiederholung zu G5.

`make hw-workbench-bam-alloc-smoke` ist der erste destruktive BAM-Pin, aber
ausdruecklich nur auf einer Wegwerf-Kopie (`L65M2.D81`). Der Harness startet ein
dediziertes Mini-PRG, das T45/S8 in der BAM als belegt markiert, holt das D81
zurueck und laesst `tools/host-lisp/d81_bam_alloc_diff.py` laufen. Live-Pin vom
2026-07-09: sichtbarer Marker `bam alloc pass 4/4`; erlaubter D81-Diff exakt
`0x61a28 39->38` und `0x61a2a 0xff->0xfe`. G2 nutzt den Host-Differ-Selftest,
G4 den hardwarefreien Dry-Run und G5 den Live-Smoke. Der Live-Harness
restauriert danach standardmaessig die aktuelle Workbench, weil der
`mega65_ftp get`-Readback die Maschine in BASIC zuruecklassen kann; `--no-restore`
ist nur fuer explizite Diagnose-Endzustaende gedacht.

`make hw-workbench-chain-write-smoke` ist der M3-Pin fuer eine zweisektorige
Quelle ohne Directory-Eintrag. Der Harness schreibt auf `L65M3.D81`
T45/S8 -> T45/S9, allokiert beide Sektoren in der BAM, prueft den Host-Diff mit
`tools/host-lisp/d81_chain_write_diff.py` und bootet danach die Workbench gegen
dieselbe Wegwerf-D81. Live-Pin vom 2026-07-11: sichtbarer Marker
`chain write pass 7/7`; Host-Diff `len=275`, `0x61a28 39->37`,
`0x61a2a 0xff->0xfc`; Oracle `(%disk-load-file 45 8)` => `"m3-load-ok"` und
`(m3-chain-run)` => `737`. G2 nutzt den Host-Differ-Selftest, G4 den Dry-Run
und G5 den Live-Smoke; der Live-Harness restauriert anschliessend wieder die
Workbench.

`make hw-workbench-dir-write-smoke` ist der M4-Pin fuer eine neu angelegte
Datei mit Directory-Eintrag. Der Harness schreibt auf `L65M4.D81`
T45/S8 -> T45/S9, allokiert beide Sektoren in der BAM und schreibt zuletzt
T40/S4 Entry 2 als `M4SRC`. Der Host-Diff nutzt
`tools/host-lisp/d81_dir_write_diff.py` und erlaubt nur Datenkette, BAM und
diesen 32-B-Dir-Slot. Live-Pin vom 2026-07-11: sichtbarer Marker
`dir write pass 11/11`; Host-Diff `len=276`, `dir@0x61c40`,
`0x61a28 39->37`, `0x61a2a 0xff->0xfc`; Oracle `(load "m4src")` =>
`"m4-load-ok"` und `(m4-dir-run)` => `767`. G2 nutzt den Host-Differ-Selftest,
G4 den Dry-Run und G5 den Live-Smoke; der Live-Harness restauriert
anschliessend wieder die Workbench.

`make hw-workbench-save-new-smoke` ist der M5-Kompatibilitaetspfad fuer den
Lisp-seitigen `save-new`-Allocator-Prototyp. Der Harness arbeitet nur auf der
Wegwerf-D81 `L65M5.D81`, schreibt den Allocator `lib/m65-disk-alloc.lisp` als
lesbare Source-Datei `m5alloc` in das Image, laedt ihn im Mini-PRG zur
Laufzeit und ruft `(m65d-save-new-2 "m5src" (m65d-test-payload))`. Der
aktuelle Allocator sucht einen freien Directory-Slot in T40/S4,
materialisiert den Namen und waehlt zwei freie Datensektoren auf T45 ab S20
aus der BAM. Wegen der groesseren Allocator-Source erwartet der Host-Pin
aktuell `M5SRC` auf T45/S26 -> S27: `len=373`, `dir@0x61c60`,
`0x61a28 14->12`, `0x61a2c 0xfc->0xf0`.

`make hw-workbench-save-new-scan-smoke` ist der M6-Live-Pin fuer denselben
Allocator mit explizitem BAM-Scan-Beweis. Der Harness reserviert im Vor-Image
T45/S26 und baut das Mini-PRG mit Zielname `m6src`; der Allocator muss
dadurch T45/S27 -> S28 waehlen und `M6SRC` in T40/S4 Entry 3 schreiben.
Live-Pin vom 2026-07-11: sichtbarer Marker `save new pass 5/5`; Host-Diff
`name=m6src T45/S27->S28`, `len=373`, `dir@0x61c60`,
`0x61a28 13->11`, `0x61a2c 0xf8->0xe0`; Oracle `(load "m6src")` =>
`"m5-load-ok"` und `(m5-new-run)` => `797`. G2 nutzt Host-Load-Check und
Host-Differ-Selftests, G4 die Dry-Runs und G5 den Live-Smoke; der Harness
restauriert anschliessend wieder die Workbench. Der Pin beweist Name, freien
T40/S4-Slot und BAM-Scan, bleibt aber der stabile Zweissektor-Regressionspfad.

`make hw-workbench-save-new-var-smoke` ist der M7-Live-Pin fuer variable
Kettenlaengen und globale Track-/Sektorwahl. Er schreibt den separaten
Allocator `lib/m65-disk-alloc-var.lisp` als `m7alloc` auf eine Wegwerf-D81 und
ruft im Mini-PRG `(m65d-save-new "m7src" (m65d-test-payload))`. Das
Host-Oracle `tools/host-lisp/d81_save_new_diff.py` berechnet den erwarteten
Allokationsplan aus der BAM des Vor-Images; aktueller Live-Pin:
`M7SRC` mit 676 Bytes auf T1/S0 -> T1/S1 -> T1/S2, Directory T40/S4 Entry 3.
Das Workbench-Oracle ist `(load "m7src")` => `"m7-load-ok"` und
`(m7-var-run)` => `907`. Der sichtbare Marker ist `save new pass 5/5`; der
M7-Harness nutzt `--wait 45`, weil der groessere Lisp-Allocator laenger
laedt/evaluiert. `make hw-workbench-save-new-var-smoke-dry-run` bleibt das
hardwarefreie Gate; noch offen sind Directory-Ketten ueber T40/S4 hinaus sowie
Fehler-/Rollback-Disziplin.

Nach `(load-lib "ide")` oder `(edit)` sind die Persistenzbefehle aus der REPL
verfuegbar. `compile-file-to-lib` ist im Workbench-MVP ein Lisp-Wrapper ueber
Disk-Read plus `compile-string`; die alte native Disk-Source-`LISP65_FASL`-
Schicht bleibt bewusst ausserhalb des Produktpfads. `compile-buffer-to-lib`
schreibt eine L65M/FASL-Lib in den Zielslot; der Editorpfad `compile-load`
laedt sie danach sofort via `load-lib`.
Compile-APIs ohne `to-lib`/`to-fasl` bleiben fuer transiente Compile-Semantik
reserviert.

Im Editor gibt es als ersten direkten Datei-/Buffer-Workflow `C-x C-f`,
`C-x C-s`, `C-x C-w`, `C-x C-b`, `C-x C-n`, `C-x C-p`, `C-x C-d` und
`C-x C-k`. `C-x C-f`, `C-x C-w`, `C-x C-b` und `C-x C-k` oeffnen einen
einzeiligen Minibuffer in der Statuszeile; Defaults werden als `[name]`
angezeigt. Leeres RETURN nutzt diesen Default. Auf der Workbench-D81 steht die
ladbare IDE-Lib als erster Directory-Eintrag; Find/Write filtern
System-/Compile-Slots, sodass `TAB` bei `C-x C-f`/`C-x C-w` mit Source-Slots
wie `demo`/`work` statt `ide`/`fasl*` arbeitet. Source-Open und Source-Save sind
zusaetzlich hart gegatet: `load-file-to-buffer`, `save-buffer-to` und damit
`C-x C-f`, `C-x C-w` sowie Directory-RETURN weisen bekannte System-/Compile-
Slots (`ide`, `idex`, `m65d`, `an`, `out`, `fasl*`) mit `"not source"` ab, bevor sie
Disk-Inhalt als Editorzeilen materialisieren oder ueberschreiben. `C-x C-k`
bleibt davon getrennt und rotiert per `TAB` nur durch `fasl*`-Compile-Ziele.
Die IDE-Compile-Wrapper `compile-buffer-to-lib` und `compile-file-to-lib`
weisen Nicht-FASL-Ziele mit `"not fasl"` ab; `compile-file-to-lib`
weist zusaetzlich Nicht-Source-Eingaben wie `fasl*` mit `"not source"` ab,
bevor Disk-Inhalt als Quelltext gelesen wird.
`C-x C-n` und `C-x C-p`
wechseln ohne Minibuffer zum naechsten bzw. vorherigen offenen Buffer in der
stabilen Buffer-Liste. `C-x C-s` speichert ohne Nachfrage auf den aktuellen
`file-name` bzw. Buffer-Namen. `C-x C-d` oeffnet `*directory*` als gefilterte
Source-Ansicht; `(dir)` in der REPL liefert weiterhin die rohe Directory-Liste.
RETURN auf einer Directory-Zeile oeffnet den gewaehlten Source-Eintrag.
Neue Source-Dateien und Ersetzungen koennen per `(save-buffer-to "name" "buffer")`
oder `C-x C-s`/`C-x C-w` geschrieben werden. Der eigentliche BAM-/COW-Kern
bleibt als `m65d` on demand und damit ausserhalb des IDE-Pflichtartefakts.
Bare-Control-Navigation ist ebenfalls verdrahtet: `C-f`/`C-b` bewegen ein
Zeichen rechts/links, `C-n`/`C-p` eine Zeile runter/hoch, `C-a`/`C-e` an
Zeilenanfang/-ende, `C-j` fuegt wie RETURN eine neue Zeile ein. `C-v`/`C-z`
bewegen um eine Seite minus Statuszeilenpuffer; `C-x C-a`/`C-x C-e` springen
an Bufferanfang/-ende. `C-x`-Prefix gewinnt vor diesen Aliases, daher bleibt
z. B. `C-x C-f` Find-File und `C-x C-b` Bufferwechsel. `C-d` loescht forward:
in der Zeile das Zeichen unter
dem Cursor, am Zeilenende joint es mit der Folgezeile, am Buffer-Ende ist es
ein No-op. `C-k` killt den Zeilenrest in `*ide-kill-ring*`; steht der Cursor am
Zeilenende, joint es die Folgezeile und speichert einen Newline-String.
`C-y` yankt den aktuellen einfachen Kill-Ring am Punkt; ein normaler String
wird in die aktuelle Zeile eingefuegt, ein einzelner Newline-String splittet
die Zeile.
`C-o` bewegt zum Ende des naechsten Worts, `C-u` zum Anfang des vorherigen
Worts. Wortgrenzen sind bewusst einfach: Whitespace und Lisp-Delimiter trennen
Tokens. `C-w` killt das naechste Wort in den einfachen Kill-Ring, `C-r`
killt das vorige Wort; `C-x C-w` bleibt Write-File, weil der Prefix Vorrang hat.
`C-SPC` setzt die Mark, `C-x C-x` tauscht Punkt und Mark, `C-x C-r` killt
eine Region und `C-x C-y` kopiert eine Region in den einfachen Kill-Ring.
Region/Kill-Ring/Yank koennen mehrere Zeilen tragen; visuelle Markierung ist
bewusst nicht Teil dieses Pins.
`C-s` oeffnet einen Search-Minibuffer, zeigt den letzten Suchbegriff als
Default und springt bei neuer Eingabe ab Cursorposition zum Treffer;
`C-s C-s` wiederholt den letzten Suchbegriff ab der naechsten Spalte. `C-l`
oeffnet einen Goto-Line-Minibuffer und nutzt 1-basierte Zeilennummern mit Clamp
auf den vorhandenen Buffer. Im Minibuffer speichert RETURN bzw. `C-j` den
letzten nichtleeren Wert pro Aktion; `C-p`/CRSR-hoch ruft ihn wieder ab,
`C-n`/CRSR-runter und `C-u` leeren die Eingabe. DEL loescht wie Backspace ein
Zeichen rueckwaerts.
`C-x x` und `C-x RET` oeffnen einen schmalen M-x-Minibuffer; im MVP-Command-Set
liegen `find-file`, `save-buffer`, `compile-load`, `goto-line` und
`eval-buffer`. Intern nutzt der Lookup eindeutige Zwei-Zeichen-Prefixe
(`fi`, `sa`, `co`, `go`, `ev`), damit keine Pair-Registry budgetwirksam
resident bleiben muss.
`C-x C-k` spiegelt den aktuellen Buffer in die Buffer-Tabelle, ruft
`compile-buffer-to-lib` auf dem abgefragten Ziel auf und laedt danach per
`load-lib`; die UI bezeichnet das als `Compile+load:`, Default ist `fasl0`,
Erfolgsmeldung ist `"compiled"`,
Fehler kommen aus `(ide-error)`. `TAB` schaltet im Minibuffer durch passende
Source-Datei-, Buffer- bzw. FASL-Zielkandidaten; vorhandener Input dient dabei
als case-insensitiver Prefix-Filter. `C-g` und `ESC` brechen den
Minibuffer ab, ohne die IDE zu verlassen; ausserhalb des Minibuffers bleibt
`ESC` ein IDE-Quit. Plain-letter-Chords wie `C-x b` sind bewusst noch nicht
aktiv, damit normale Zeicheneingabe keinen Prefix-State im Hotpath lesen muss.

Fehlerdetails der REPL-API bleiben aus Kompatibilitaetsgruenden ausserhalb des
Rueckgabewerts: `load-file-to-buffer`, `save-buffer-to`,
`compile-buffer-to-lib` und `compile-file-to-lib` liefern weiter
`t`/`nil`; nach `nil` enthaelt `(ide-error)` z. B. `"source missing"`,
`"slot missing"`, `"too large"` oder `"compile failed"`. Die Editor-
Minibufferpfade fuer Find/Write/Compile laufen ueber dieselben Wrapper, sodass
die Statuszeile dieselben Meldungen zeigt. `compile-string` setzt bei
direkter Nutzung zusaetzlich `(compile-error)`, aktuell u. a. `"bad source"`,
`"bad slot"`, `"slot missing"`, `"too large"` oder `"save failed"`; die
IDE-Compile-Wrapper uebernehmen diese Details in `(ide-error)`.

Minimaler Persistenz-Smoke:

```lisp
(load-lib "ide")                         => t
(dir)                                    => Liste mit ide/demo/work/fasl0/...
(load-file-to-buffer "demo" "demo")       => t
(save-buffer-to "work" "demo")            => t
(save-buffer-to "newsrc" "demo")          => t; M65D wird bei Bedarf geladen
(m65d-status)                              => 0
(m65d-remount)                             => 0
(compile-buffer-to-lib "fasl0" "demo")    => t
(load-lib "fasl0")                         => t
(demo-numbers-run)                        => 42
(compile-string "(defun x () 1)" "noslot") => nil
(compile-error)                           => "slot missing"
```

Der G5-UX-Harness fuehrt zusaetzlich Create und Replace von `ap6src` aus,
legt `z6src` als zweite unabhaengige Datei in derselben Session an, liest alle
Versionen exakt zurueck, validiert `m65d-remount` und startet das
Produkt danach mit derselben remote Wegwerf-D81 ohne erneuten D81-Upload neu.
Erst der anschliessende `(load "ap6src")`- und Ergebnischeck gilt als
Reset-/Remount-Abnahme. Der entsprechende G4-Dry-run ist Bestandteil von
`check-hardware-dry-run`; ein Dry-run ist kein Live-Nachweis.

Der Live-Lauf vom 2026-07-11 ist gruen. Nach Reset lautet der gemeinsame
Read-/Eval-Pin exakt
`(("(defun ap6-persisted () 612)") 612 ("(defun ap6-b () 613)") 613)`.
Danach restauriert der Harness die unveraenderte Ship-D81, damit die erzeugten
AP6-Dateien keine alphabetischen Directory-/TAB-Oracles der restlichen UX-
Matrix beeinflussen.

`m65d-remount` prueft beide BAM-Haelften, die komplette vorhandene
Directory-Linkkette sowie Typ, Startadresse und Blockzahl jedes belegten
Eintrags. Es ist kein Dateisystem-Reparaturtool: Crosslinks bzw. globale
Sektor-Ownership zwischen verschiedenen Dateien werden nicht behauptet.
Der Live-Harness gibt der vollstaendigen Remount-Pruefung ein eigenes
20-s-Fenster; das allgemeine 3-s-Formfenster ist dafuer nicht ausreichend.

MVP-Nutzerfluss:

```lisp
(load-lib "ide")                          => t
(load-file-to-buffer "demo" "demo")       => t
(edit "demo")                             => Quelle inspizieren/bearbeiten
RUN/STOP                                  => zur REPL zurueck
(save-buffer-to "work" "demo")            => t
(compile-buffer-to-lib "fasl0" "demo")     => t
(load-lib "fasl0")                         => t
(demo-numbers-run)                        => 42
```

Dieser Fluss ist absichtlich slot-basiert: `demo` ist die lesbare Quelle,
`work` ein vorallozierter Save-Slot, `fasl0` ein vorallozierter
Compile+Load-Slot.

Der Dry-Run-Deploy prueft Blob-Preload, PRG-Etherload und D81-Mount ohne
Live-Hardware-Aktion:

```sh
make hw-smoke-vm-stdlib-dry-run
```

## HW-Gate

Von Claude am 2026-07-08 bestaetigt:

```lisp
(compile-string "(defun a () 40)(defun b () (+ (a) 2))" "an") => t
(load-lib "an")                                               => t
(b)                                                           => 42
```

Rahmen:

- echter MEGA65
- vorallokierter SEQ-Slot `an`
- `gc_badobj=0`
- `mem_oom=0`
- `gc_runs=5`

Codex-Re-Test am 2026-07-09 bestaetigt den erweiterten Workbench-Pfad auf
echter HW mit dem MVP-D81:

```lisp
(+ 20 22)                                                     => 42
(load-lib "ide")                                             => t
(symbol-max)                                                 => 720
(function-kind (quote compile-buffer-to-lib))                 => bytecode
(C-x C-d / Directory-Open)                                   => "loaded"
(FASL-Open/Save/Compile-Source-Guards)                       => "not source"
(Tab, Buffer-Cycle, Delete-Forward, Kill/Yank, Word-Edit)    => PASS
(Document-Nav, M-x, Multi-line-Region/Yank, Search/Goto)     => PASS
```

Nach dem TAB-Minibuffer-Nachzug, Symbol-Introspektions-Reclaim,
Directory-RETURN-Slice, Candidate-B-Reclaim, direktem Buffer-Zyklus,
Forward-Delete, Minibuffer-History, Search/Goto, Render-Reclaim und
File-Target-Guards plus Minibuffer-Edit, Search-Repeat,
Statusline-Zeilennummer (`L<n>`) mit Accessor-Reclaim im
Statusline-/Cache-Pfad, `C-k`/Kill-Line, `C-y`/Yank, Word-Edit
(`C-o`/`C-u`/`C-w`/`C-r`), Dokumentnavigation, mehrzeiliger Mark/Region-
Familie, schmalem M-x-Pilot, `M-x eval-buffer`, M65D-COW und der `*-to-lib`-API
ist der aktuelle kumulative Host-Pin `disk_lib=214`, `load_used=538/552`,
`post_align=544/552`, `codebuf_required=56/56`, EXT-Code-Peak-Headroom `8528`
und Post-Commit-Headroom `19174`. Der exakte Loaderreport endet bei 683/720
Symbolen und 9110/9536 Namepool-Bytes.
`make hw-workbench-ux-smoke` ist auf echter HW gruen, inklusive
Minibuffer-History/Edit und `M-x eval-buffer` in einer frischen zweiten
Etherload-Session. Der aktuelle
Harness trennt den langen
`load-lib "ide"`-Core-Check von der folgenden `function-kind`-Abfrage, um
JTAG-Virtual-Keyboard-Verluste zu vermeiden.

Codex-Re-Test fuer den Editor-Compile-Befehl bestaetigt danach den
`C-x C-k`-Pfad ueber normalisierte `ide-step`-Events:

```lisp
(%ide-mini-status-line)                                      => "Compile+load: [fasl0]"
(ide-state-message cr)                                       => "compiled"
(cxdemo)                                                     => 42
```

Der alte Core-Compile-Smoke (`compile-string` nach `an`, `load-lib "an"`,
`(b) => 42`) bleibt sinnvoll, sollte aber fuer klare Budgetbeobachtung in einer
frischen Session vor dem IDE-Load laufen.

Details: `docs/workbench-hw-test-2026-07-08.md`.

## Offene Follow-ups nach MVP-Pin

1. `LISP65_SYMFN_EXT`-Performance weiter beobachten: Host-Trace und Gate sind
   vorhanden; Live-HW-Timing ist nur dann noetig, wenn Tipp-/Compile-Latenz
   wieder sichtbar schlechter wird. Der aktuelle Pin hat keinen Symfn-Cache.
2. Native REPL-Mehrzeilenfortsetzung nachziehen, sobald wieder PRG-Ende-Luft
   vorhanden ist: RETURN sammelt weiter, solange Klammern/Strings nicht
   geschlossen sind; sonst Evaluation.
