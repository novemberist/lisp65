# Automatisiertes Testen auf echter MEGA65-Hardware

Stand: 2026-07-11. Der Hardware-Pfad ist nicht mehr nur vorbereitet: Die
aktuellen B4-/Heap-/IDE-Diagnosen wurden auf echter MEGA65-Hardware gefahren.
Die zentrale Trennung bleibt:

- **Etherload/FTP** ist der Deploy- und Datei-Readback-Pfad über Ethernet/IPv6.
- **JTAG/`m65`** ist der reichere Diagnosepfad für Reset, Tastatur, Screenshot und
  Speicher-/Zähler-Dumps.

## Werkzeuge (`tools/m65tools/`)

| Tool | Rolle | Transport |
| --- | --- | --- |
| `etherload` | PRG laden/starten, Binärblob laden, D81 mounten, Jump-Entry | Ethernet/IPv6 |
| `mega65_ftp` | Dateien von/zur SD-Karte kopieren, z. B. D81 hochladen oder Ergebnisdatei holen | Ethernet (`-e`) oder seriell |
| `m65` | Reset, Tasten tippen, Screenshot/Textscreen, Speicherbereiche sichern | seriell über USB-UART/JTAG |
| `coretool`/`bit2core`/`bit2mcs`/`romdiff` | Core-/ROM-Werkzeuge | nicht test-relevant |

`etherload` und `mega65_ftp -e` reichen für sichtbare Selftests und
dateibasierte Marker. Sobald ein Test Tastatureingaben automatisieren,
Screenshots/Textscreen prüfen oder Runtime-Zähler per Speicher-Dump auslesen
soll, braucht er `m65` über das JTAG-/UART-Kabel.

## Aktuelle Topologie

Die aktuelle Arbeitsnotiz in `docs/collaboration.md` dokumentiert:

- `m65` hängt an `/dev/ttyUSB1`.
- Ethernet hängt direkt am PC, Interface `enp35s0`, Link-Local IPv6.
- Das SHIFT+£-Scharfstellen fuer Remote/Etherload ist ein Hypervisor-Laufzeitflag.
  Etherload-Deploys/Soft-Resets erhalten dieses Flag; ein harter JTAG-Reset
  (`m65 -F`) loescht es.
- Normaler Workflow: direkt per `etherload` deployen, egal ob aktuell BASIC oder
  das Lisp-Produkt laeuft. Kein `m65 -F` vor normalen Deploys.
- `m65 -F` ist ein Notfallwerkzeug fuer echte Freezes. Danach muss am Geraet
  einmal wieder per SHIFT+£ scharfgestellt werden.

### Reset-Ueberlebensmatrix

| Speicherregion | Soft-/Etherload-Reset | Power-Cycle | Workbench-Rolle |
| --- | --- | --- | --- |
| Banks 1-3 | nicht stabil; ROM-/Reset-Restaging darf Inhalte ersetzen | nicht stabil | keine persistenten Runtime-Preloads |
| Bank 5 | stabil | nicht stabil | Combined Stdlib-/Boot-Preload |
| Attic RAM ab `$08000000` | stabil | nicht stabil | profilgebundener L65R-v1-Runtime-Katalog |

Keiner dieser Preloads ist power-fest. Nach einem Kaltstart muss Ship-v5 Bank 5
und Attic erneut deployen. Fehlt der Attic-Katalog, zeigt der residente
Fehlerpfad `E2e catalog missing; redeploy`. Die bisherigen Workbench-G5-Läufe
belegen Reset/Remount nach vorherigem Staging innerhalb einer versorgten
Session, keinen autonomen Kaltstart nach Power-Cycle. Dieser Workbench-
Cold-Start-/Recoveryvertrag bleibt G6-offen.

Runtime Export verwendet im aktuellen Appliance-Profil nur Bank 5 und das
Inline-Overlay im PRG, keinen Attic-Katalog und keine D81/SD. Ein autonomes
Nachladen ist der getrennte Block **Runtime Export Standalone Boot** und
braucht D81/SD-Loader, Recovery und einen expliziten Capabilityvertrag.

Die konkrete IPv6-Adresse kann per Discovery ermittelt oder explizit übergeben
werden:

```sh
tools/m65tools/etherload --discover
sh scripts/run-on-mega65.sh --ip 'fe80::...%enp35s0' ...
```

## Etherload-Loop

Der gemeinsame Wrapper ist `scripts/run-on-mega65.sh`. Er kann ohne Hardware per
`--dry-run` geprüft werden.

```sh
# PRG laden und starten:
sh scripts/run-on-mega65.sh --run build/test.prg

# VM-Stdlib-/Code-Blob in Bank 5 vorladen, dann PRG starten:
sh scripts/run-on-mega65.sh \
  --preload-bin 0x050000 build/bytecode/stdlib-p0.ext.bin \
  --run build/test.prg

# D81 mounten, vorher muss die D81 per mega65_ftp auf die SD gelegt worden sein:
tools/m65tools/mega65_ftp -e -y -c 'put build/f011/test.d81 TEST.D81'
sh scripts/run-on-mega65.sh \
  --mount TEST.D81 \
  --preload-bin 0x050000 build/bytecode/stdlib-p0.ext.bin \
  --run build/test.prg

# Datei vom Gerät zurückholen und Marker prüfen:
sh scripts/run-on-mega65.sh \
  --run --result M65OK --expect OK build/test.prg
```

Wichtige Optionen:

- `--dry-run`: Kommandos nur ausgeben; sicher für lokale Checks.
- `--ip <ipv6%iface>`: feste Link-Local-Adresse statt Discovery.
- `--preload-bin <addr> <file>`: Binärartefakt per `etherload --halt -b` laden.
- `--mount <NAME.D81>`: D81 aus dem SD-Root mounten.
- `--result <SDFILE> --out <local> --expect <string>`: Datei-Readback über
  `mega65_ftp` plus Markerprüfung.

## Runtime-Export-G4/G5-Vertrag

Der AP8.2-Runtime-Export ist extern gestaged. Ship-/Manifest-v2 bindet
Whole-image- und Payload-Laengen, Build-ID, CRC/SHA und das symbolische
Hardware-Oracle. Dieses wird aus dem exakten ELF gewonnen und enthaelt die
aufgeloesten Symbole `lisp65_runtime_state`, `lisp65_runtime_result` und
`lisp65_runtime_preload_detail`; Hardwareadressen werden nicht manuell
gepinnt. Der Ship-v2-Verifier prueft ausserdem den genau einmal im PRG
vorhandenen `L65P`-Record fuer Payload-Laenge, Whole-image-CRC und Build-ID.
Der Runtime Core liest denselben Record volatil; das Manifest kann deshalb
keine vom ausgefuehrten PRG abweichende Preload-Bindung behaupten.

G4 ist abgeschlossen und nur ein lokaler Planlauf. Er verifiziert Paket,
Manifest-v2 und Oracle und gibt die geplanten Bank-5-, PRG- und
Readback-Schritte aus. Er startet weder `m65` noch Etherload/FTP, erzeugt
keinen Hardwarezustand und enthaelt keine D81-, SD- oder Attic-Aktion. Der
Plan ist maschinell `offline=true` und `side_effects=false`; er ist keine
Live-Evidenz. Der volle Candidate-Check einschliesslich zweitem
byteidentischem Sieben-Dateien-Paketbuild und G4 ist gruen.

Der echte G5 wird pro Phase nach einem ausdruecklich bestaetigten Power-Cycle
gefahren. Vor dem Staging muss der Bank-5-Readback vom erwarteten Preload-SHA
abweichen; ein gleicher Digest belegt nur erhaltenen RAM und verwirft den
Cold-Boot-Claim. Danach wird der Zielspan geleert beziehungsweise exakt
gestaged, vollstaendig gelesen und erst nach SHA-/CRC-Pruefung gestartet.

Die vier Phasen sind:

1. `clean`: terminaler Complete-State und das manifestgebundene Resultat exakt.
2. `truncated`: geleerter Zielspan, gekuerztes Artefakt, terminal
   `RUNTIME_PRELOAD_ERROR` mit Laengen-Detailcode und `NIL`.
3. `bitflip`: ein gepinnter Payload-Bitflip, derselbe terminale Fehler mit
   CRC-Detailcode und `NIL`.
4. `build-id-mismatch`: ein Preload aus einem anderen verifizierten Profil, derselbe
   terminale Fehler mit Build-ID-Detailcode und `NIL`.

Jede Phase bindet Manifest-/Oracle-SHA, Profil-Build-ID, Cycle-ID,
Bediener-Attestierung, Pre-stage-Digest, Full-span-Readbacks sowie rohe State-,
Result- und Preload-Detail-Bytes in einem atomaren fail-closed Receipt.
Der Runtime Core prueft Laenge, Build-ID und CRC des vollstaendigen gebundenen
Preloads aus Payload und Trailer vor
`vm_load_embedded_stdlib`; bei jedem Fehler wird der benannte Entry nicht
ausgefuehrt. Host-Harness, Mutations-Selftests und exakte Oracles fuer alle vier
Phasen sind abgeschlossen. Der echte Lauf vom 2026-07-12 ist nach vier
getrennten physischen Power-Cycles gruen: `clean` ergab State `3`, Fixnum `42`
und Detail `0`; die drei Korruptionsfaelle ergaben State `$e4`, `NIL` und die
Details `1`, `3` und `2`. Der selbststaendig wiederverifizierbare Satz aus
Candidate, Fremdprofil, Oracle, Receipts und Rohbytes liegt unter
`tests/bytecode/runtime/evidence/ap8.2-g5-589844f/`.

Der reproduzierbare Operatorpfad ist:

```sh
make runtime-export-g5-ready
# MEGA65 physisch aus- und wieder einschalten, dann:
make runtime-export-g5-clean RUNTIME_EXPORT_G5_POWER_CYCLE_TOKEN=POWER-CYCLED RUNTIME_EXPORT_G5_CYCLE_ID=ap82-clean-01
# Erneut physisch aus- und einschalten, dann:
make runtime-export-g5-truncated RUNTIME_EXPORT_G5_POWER_CYCLE_TOKEN=POWER-CYCLED RUNTIME_EXPORT_G5_CYCLE_ID=ap82-truncated-02
# Erneut physisch aus- und einschalten, dann:
make runtime-export-g5-bitflip RUNTIME_EXPORT_G5_POWER_CYCLE_TOKEN=POWER-CYCLED RUNTIME_EXPORT_G5_CYCLE_ID=ap82-bitflip-03
# Erneut physisch aus- und einschalten, dann:
make runtime-export-g5-build-id-mismatch RUNTIME_EXPORT_G5_POWER_CYCLE_TOKEN=POWER-CYCLED RUNTIME_EXPORT_G5_CYCLE_ID=ap82-build-id-04
make runtime-export-g5-suite-verify
```

Jede Phase verweigert ein vorhandenes Evidence-Verzeichnis. Fuer ein anderes
JTAG-Geraet beziehungsweise Toolverzeichnis werden
`RUNTIME_EXPORT_G5_DEVICE` und `RUNTIME_EXPORT_G5_TOOLS` explizit gesetzt.

## Vorhandene Hardware-Scripts

Diese Scripts sind die kanonischen Startpunkte:

| Script/Target | Zweck | Erwartung |
| --- | --- | --- |
| `scripts/hw-runtime-export-reemit.sh` | Runtime-Demo mit verifiziertem Workbench-Ship-v5 auf Wegwerf-D81 erneut emittieren und kanonisch erfassen | Workbench-L65M und abgeleiteter Bank-5-Payload byteidentisch zum Golden; bewusst nicht bytegleicher Python-P0-Pfad nur als Differential-Oracle; kein G5-Claim |
| `make runtime-export-g4` / `scripts/runtime-export-deploy.sh --gate G4` | Ship-v2 und symbolisches ELF-Oracle offline verifizieren und den exakten Runtime-Deploy-/Readback-Plan erzeugen | `offline=true`, `side_effects=false`, keine ausgefuehrten Hardware-, D81-, SD- oder Attic-Aktionen |
| `make runtime-export-g5-{clean,truncated,bitflip,build-id-mismatch}` | Nach jeweils eigenem bestaetigten Power-Cycle genau eine Runtime-G5-Phase in ein frisches Evidence-Verzeichnis fahren | Exakter State/Result/Detail-Verdikt; abschliessend `make runtime-export-g5-suite-verify` mit vier verschiedenen Cycle-IDs |
| `make hw-workbench-overlay-stack-guard-verified-smoke` / `scripts/hw-workbench-overlay-stack-smoke.sh` | Ship-v5-D81 zwingend hochladen, PRG/Bank 5/Attic an kanonische Adressen haltend per JTAG stagen, alle drei SHAs lesen, dann per Etherload resetten/remounten/starten, Attic erneut lesen und echten `load-lib`-Preflight ausfuehren | gleicher Manifest-Receipt in beiden Phasen, alle drei Preload-SHAs vor Ausfuehrung exakt, Attic-SHA nach Reset exakt, letztes REPL-Ergebnis am finalen leeren Prompt exakt |
| `make hw-smoke-vm-stdlib-selftest` / `scripts/hw-smoke-vm-stdlib-selftest.sh` | Basis-VM-Stdlib-Selftest | grüner Rahmen, `lisp65 hw-selftest pass ...` |
| `make hw-workbench-ux-smoke` / `scripts/hw-workbench-ux-smoke.sh` | MVP-Workbench deployen, IDE-Lib laden und interaktive UX-/AP6-Pfade per JTAG-REPL pruefen | Zwei Creates, Read, Replace, Remount und Reset ohne D81-Reupload; danach Editor-, Directory-, Compile- und M-x-Oracles |
| `make hw-workbench-bam-read-smoke` / `scripts/hw-workbench-bam-read-smoke.sh` | Workbench-D81 deployen und 1581-BAM read-only ueber die Lisp-Disk-Prims auf echter HW lesen | `42`; beide BAM-Formen bytegenau aus dem hochgeladenen, SHA-gebundenen D81 abgeleitet (aktuelles R5-Medium: `(t 40 2 40 35)`, `(t 0 255 0 38)`) |
| `make hw-workbench-bam-alloc-smoke` / `scripts/hw-workbench-bam-alloc-smoke.sh` | Wegwerf-D81 `L65M2.D81` deployen, T45/S8 in der BAM belegen, D81 zurueckholen und Host-Diff pruefen | sichtbarer Marker `bam alloc pass 4/4`; D81-Diff exakt zwei BAM-Bytes |
| `make hw-workbench-chain-write-smoke` / `scripts/hw-workbench-chain-write-smoke.sh` | Wegwerf-D81 `L65M3.D81` deployen, T45/S8->S9 als Quellkette schreiben, D81 zurueckholen, Workbench-Load-Oracle ausfuehren | `chain write pass 7/7`, `"m3-load-ok"`, `737` |
| `make hw-workbench-dir-write-smoke` / `scripts/hw-workbench-dir-write-smoke.sh` | Wegwerf-D81 `L65M4.D81` deployen, T45/S8->S9 als Quellkette schreiben, Directory-Slot T40/S4 Entry 2 zuletzt anlegen, D81 zurueckholen, normalen Workbench-`load`-Oracle ausfuehren | `dir write pass 11/11`, `"m4-load-ok"`, `767` |
| `make hw-workbench-save-new-smoke` / `scripts/hw-workbench-save-new-smoke.sh` | Wegwerf-D81 `L65M5.D81` deployen, Lisp-Allocator `m5alloc` von D81 laden, `M5SRC` per Lisp-Zweissektor-Prototyp anlegen, D81 zurueckholen, normalen Workbench-`load`-Oracle ausfuehren | `save new pass 5/5`, `"m5-load-ok"`, `797` |
| `make hw-workbench-save-new-scan-smoke` / `scripts/hw-workbench-save-new-smoke.sh` | Wegwerf-D81 `L65M6.D81` deployen, T45/S26 im Vor-Image reservieren, Lisp-Allocator muss `M6SRC` auf T45/S27->S28 anlegen, D81 zurueckholen, normalen Workbench-`load`-Oracle ausfuehren | `save new pass 5/5`, `"m5-load-ok"`, `797` |
| `make hw-workbench-save-new-var-smoke` / `scripts/hw-workbench-save-new-smoke.sh` | Wegwerf-D81 `L65M7.D81` deployen, Lisp-Allocator `m7alloc` von D81 laden, `M7SRC` per BAM-geplanter variabler Kette anlegen, D81 zurueckholen, normalen Workbench-`load`-Oracle ausfuehren | `save new pass 5/5`, `"m7-load-ok"`, `907` |
| `scripts/hw-smoke-einsuite.sh --full` | Ein-Suite/full ohne Disk-Roundtrip | grüner Rahmen, `einsuite hw-selftest pass 13/13` |
| `scripts/hw-disk-roundtrip.sh` | Full+Disk `(load)`/`(save)`-Roundtrip gegen D81 | grüner Rahmen, `pass 17/17` |
| `scripts/hw-disk-roundtrip.sh --fasl` | FASL-Compile/Load-Roundtrip | grüner Rahmen, `pass 10/10` |
| `scripts/hw-b4-workflow.sh` | Dev-Core: IDE + PLACE on-demand, Source-Slot, `compile-file`, FASL-Load | grüner Rahmen, `pass 10/10` |
| `make hw-stress-full` / `scripts/hw-stress-full.sh` | Full-Profil-Stress: LCC, Listen-/Closure-Churn, Macro, Runtime-Health | grüner Rahmen, `stress pass 15/15` |
| `make hw-stress-deep` / `scripts/hw-stress-full.sh --deep 1/2` | Zwei optionale Deep-Dive-Shards: GC-Lifetime, VM-Thrash, Recovery, Strings, IDE-Buffer, Numeric, Screen-Health | `stress deep1 pass 5/5`, danach `stress deep2 pass 5/5` |
| `make hw-stress-redeploy` / `scripts/hw-stress-redeploy.sh` | Wiederholte Etherload-Deploys ohne Hard-Reset, finaler JTAG-Readback + Textmarker-Check | final `stress pass 15/15` |

`scripts/hw-workbench-ux-smoke.sh` ist absichtlich transportschonend: die
JTAG-REPL-Formen verwenden kurze Marker und wiederverwenden das temporaere
State-Symbol `x`, damit der Smoke selbst nicht das knappe Lisp-Symbolbudget
verbraucht. Die `core-load`- und `directory-open`-Phasen haben laengere
Capture-Waits (`IDE_LOAD_WAIT_SEC` bzw. `LOAD_WAIT_SEC`, Default jeweils 12s),
weil sie echte Disk-Loads ausloesen.
Mini-History wird auf HW direkt geprimt; der Disk-Load-Pfad ist separat durch
`directory-open` abgedeckt.

Jede UX-Phase zieht nach jeder einzelnen Setup-Form einen Text-Capture und
prueft deren Echo, bevor die naechste Zustandsaenderung gesendet wird. Das
abschliessende Ergebnis wird exakt aus dem neuesten REPL-Segment zwischen dem
letzten Form-Prompt und dem darauffolgenden Prompt gelesen. Form-Echos werden
auch ueber 80-Spalten-Wrapping rekonstruiert; Marker im Eingabetext, partielle
Ergebnisse oder Werte aus frueheren Phasen koennen daher keinen PASS mehr
erzeugen. Vor RETURN wird das aktive Prompt-Echo geprueft. Bei
einer Abweichung wird die noch nicht ausgefuehrte Zeile per INST/DEL verworfen
und der danach leere Prompt ebenfalls per Capture bestaetigt. Erst dann wird die
Form bis zu zweimal neu eingegeben; nur ein exaktes Echo wird abgeschickt. Das
ist der Pre-submit-Retry fuer jede Form: maximal drei Eingabeversuche, aber keine
Wiederholung einer Ausfuehrung. Davon getrennt ist der erste `core-arith`-Check
ein idempotenter Post-submit-Sentinel mit prozessspezifischem Ergebnis-Marker.
Nur bei einem nach der Ausfuehrung abweichenden Echo ist genau eine Wiederholung
dieses Sentinels erlaubt, und beide Versuche behalten getrennte Artefakte. Ein
korrekt eingegebener, aber fachlich falscher Ausdruck,
ein unvollstaendiger Capture, Timeouts und alle folgenden zustandsbehafteten
UX-Phasen werden nie automatisch wiederholt. Damit kann ein Transportfehler
keine zustandsaendernde Form ausfuehren. Setup-Schritte muessen ein sichtbares
Ergebnis liefern; `***`-Laufzeitfehler brechen die Phase ab. CR und Tilde sind
im Formtransport verboten, weil `m65` sie als RETURN beziehungsweise
Steuertasten-Escape interpretiert. Jeder `m65`-Prozess besitzt zusaetzlich zum
normalen Timeout einen harten Kill-Nachlauf. Die `~z`/`~Z`-Pausen der gepinnten
`m65`-Version werden nicht verwendet.
Ein Host-Selftest mit einem zustandsbehafteten Fake-`m65` pinnt dabei sowohl
den erfolgreichen zweiten Versuch als auch das fail-closed Verhalten nach drei
abweichenden Eingaben: Ohne exaktes Echo wird kein RETURN gesendet.

Der verified-only G5-Lauf vom 2026-07-10 bindet diese Abnahme an Commit
`a82d68f9502c5e42267d33e1d5e528b760bb61ff` und Manifest-SHA-256
`cee107a1b4de25a3deb2443fee824341b1dfbef841b109dbb01b9ca975e93f40`.
Der reale Sentinel benoetigte einmal einen sicheren Pre-submit-Retry; alle 27
UX-Phasen und 144 Formen bestanden. BAM-Read sowie M2-M7 bestanden Marker,
Host-Diff, Readback, Workbench-Load/Run und Restore. Ein einmaliger Ethernet-
No-response vor dem M4-Load-Oracle wurde durch einen vollstaendigen M4-Lauf mit
demselben Paket als Infrastrukturtransient klassifiziert. Ein zweiter,
unveraenderter `make check-hardware`-Gesamtlauf bestand danach alle genannten
Phasen in einem Prozess mit Exitcode 0.

Der aktuelle verified-only G5-Abschluss vom 2026-07-11 bindet Commit
`5ce25a2b26ac1be03bd0a1ab1718329bb0c005bc` an das Ship-v5-Manifest mit
SHA-256
`67c5943259ed2bd3d849a33c6f7909bc16962c1c88271baf32dd36a1058085dd`.
Das Manifest bleibt als unveraenderliches Buildartefakt korrekt
`g2-verified-candidate`; der G5-Receipt ist ein separater Hardwarebeleg. Stage
A bestaetigte PRG-Payload (39669 B, SHA-256 `fe1edb7d...a15ed6`, CRC `e5a3`),
Bank 5 (35987 B, SHA-256 `d97552f8...68bf3f`, CRC `d47c`) und Attic-Katalog
(54105 B, SHA-256 `55f1a6ad...5967e`, CRC `b972`) bytegenau. Nach
Reset/Remount blieben Attic und die installierte 1108-B-Insel (SHA-256
`b17c4e52...e61429`, CRC `aa0c`) exakt. `load-lib "ide"` lieferte
`overlay-ide-ok` in 10 s bei einem 12-s-Budget. Die restlichen Guard-, VM-,
GC-, Reader-, UX-, BAM- und M2-M7-Ziele bestanden komponentenweise mit
demselben Paket. Ein Eingabe- und ein Ethernet-Transient wurden erkannt; nur
die betroffenen Ziele wurden vollstaendig wiederholt. Commit `a5762e8` haertet
danach die Pre-submit-Eingabeverifikation der vier betroffenen Persistenz-
Harnesses, ohne Produktbytes oder Manifest-Pin zu aendern.

Der AP6-Abschlusslauf vom 2026-07-11 verwendete das strikt verifizierte
Ship-v5-Paket aus Commit `f64bb41`; Manifest-SHA-256
`7d9873915e90102824fad7b379c938f8724d7b9f47770cab4adc5e48544ccb94`.
In einer Session wurden `ap6src` und `z6src` neu angelegt, exakt gelesen und
`ap6src` ersetzt. `m65d-remount` lieferte `0`; nach Reset ohne D81-Reupload
ergab der gemeinsame Read-/Eval-Check exakt
`(("(defun ap6-persisted () 612)") 612 ("(defun ap6-b () 613)") 613)`.
Vor der restlichen UX-Matrix deployt der Harness wieder die unveraenderte
Ship-D81; Persistenz-Fixtures beeinflussen dadurch keine Directory-/TAB-Oracles.

Der enge AP8.1-G5-Receipt vom 2026-07-11 bindet das saubere Ship-v5 aus Commit
`78083d6b79df189e97c617577f7b89d62d4a3219` an Manifest-SHA-256
`275723fb7259261c9606cee6a0dcc17c593a4cbf9c77f44b482d7cd031d5e211`.
Er archiviert verifiziertes Manifest, Live-Memory-Receipt, Stage-/Post-Reset-
Readbacks und vier Higher-Order-Screens. Die exakten Apostroph-Sourcen fuer
`every` und `some` wurden je zweimal nach Persistence-Remount und nach langem
IDE+IDEX-Zustand geladen; die Reihenfolge war `every`/`some` und danach
`some`/`every`. Der UX-Block war gruen, bevor ein Etherload-No-response den
Aggregate spaeter unterbrach. Der Receipt attestiert die nachfolgenden
Komponenten nicht und behauptet deshalb bewusst keinen ununterbrochenen
Exit-0-Gesamtlauf oder allgemeinen Release-G5.

`scripts/hw-workbench-bam-read-smoke.sh` ist der schmale Live-Pin fuer den
read-only D81-BAM-Lesepfad. Er deployt die Workbench-D81, liest T40/S1 und
T40/S2 via `%disk-read-sector`/`%disk-byte` und prueft wenige BAM-Bytes gegen
die aus genau dem hochgeladenen D81 abgeleiteten Host-Orakel. R5 bindet das
Medium zusaetzlich als Receipt-Rohartefakt und gegen die Test-Closure. Der Standardgate nutzt nur
`hw-workbench-bam-read-smoke-dry-run`; der Live-Lauf bleibt explizit.

`scripts/hw-workbench-bam-alloc-smoke.sh` ist der erste Schreib-Pin fuer
1581-BAM-Metadaten. Er benutzt bewusst ein dediziertes Mini-PRG statt
JTAG-getippter Lisp-Schreibformen, weil verlorene virtuelle Tastaturzeichen bei
destruktiven Tests nicht akzeptabel sind. Der Test schreibt nur auf die
Wegwerf-D81 `L65M2.D81`, holt sie danach per `mega65_ftp get` zurueck und
erzwingt den Host-Differ `d81_bam_alloc_diff.py`. Weil der `mega65_ftp`-
Readback die Maschine aus dem Testprogramm herauswerfen und in BASIC
zuruecklassen kann, deployt der Harness danach standardmaessig wieder die
aktuelle Workbench. Fuer reine Diagnose-Endzustaende gibt es `--no-restore`.

`scripts/hw-workbench-chain-write-smoke.sh` erweitert diesen Pfad auf eine echte
zweisektorige Datei-Kette. Das Mini-PRG schreibt T45/S8 -> T45/S9, aktualisiert
die BAM, der Host-Differ prueft den kompletten D81-Diff, und danach bootet der
Harness die Workbench gegen die mutierte Wegwerf-D81. Das Oracle ist
`%disk-load-file` ab Start-T/S plus Ausfuehrung der geladenen Funktion. Auch
dieser Harness restauriert anschliessend standardmaessig die aktuelle Workbench.

`scripts/hw-workbench-dir-write-smoke.sh` pinnt den naechsten Schritt: dieselbe
zweisektorige Kette wird zuletzt mit einem Directory-Eintrag `M4SRC` in T40/S4
Entry 2 sichtbar gemacht. Der Host-Differ erzwingt Datenkette, BAM und genau
diesen 32-B-Dir-Slot; das Workbench-Oracle nutzt danach bewusst normales
`(load "m4src")` statt `%disk-load-file`, damit der regulaere Directory-Walk
mitgeprueft ist. Der Harness restauriert danach standardmaessig wieder die
aktuelle Workbench.

`scripts/hw-workbench-save-new-smoke.sh` schliesst den Lisp-`save-new`-
Prototyp-Loop. Der Harness erzeugt eine Wegwerf-D81, schreibt den Lisp-
Allocator als Source-Datei hinein, startet ein dediziertes Mini-PRG und laesst
dieses den Allocator zur Laufzeit per normalem `load` laden. M5/M6 nutzen den
stabilen Zweissektor-Allocator `m5alloc`: M5 erwartet T45/S26 -> S27 fuer
`M5SRC`, M6 reserviert vorher T45/S26 und erwartet dadurch T45/S27 -> S28 fuer
`M6SRC`; M6 ist am 2026-07-11 live auf echter MEGA65-HW gruen. M7 nutzt den
separaten Allocator `m7alloc` und das generische Host-Oracle
`tools/host-lisp/d81_save_new_diff.py`; der Live-Pin plant `M7SRC` als
dreisektorige Kette T1/S0 -> T1/S1 -> T1/S2. Nach sichtbarem Marker
`save new pass 5/5` holt der Harness das D81 zurueck, erzwingt den Host-Diff
und bootet die Workbench gegen dieselbe Wegwerf-D81. Das Workbench-Oracle
nutzt normales `(load "<name>")`; danach muss M5/M6 `(m5-new-run)` `797` und
M7 `(m7-var-run)` `907` liefern. M7 nutzt `--wait 45`, weil der groessere
Lisp-Allocator laenger laedt/evaluiert. Der Harness restauriert anschliessend
standardmaessig wieder die aktuelle Workbench. Diese M5-M7-Slices bleiben
historische Regressionspfade; das Produktfeature ist der AP6-M65D-COW-Kern.

Die komplexeren D81-Flows legen zuerst ein Image per `mega65_ftp` auf die SD und
starten danach über `run-on-mega65.sh --mount ... --preload-bin 0x050000 ...`.

## JTAG-/`m65`-Diagnose

JTAG ist im Repo noch kein vollständig gekapseltes Shell-Harness; die bewährten
Bausteine sind aber klar:

```sh
# Nur nach echtem Freeze: harter Reset; loescht das SHIFT+£-Remote-Flag.
tools/m65tools/m65 -l /dev/ttyUSB1 -F

# REPL-Form tippen und RETURN senden. Achtung: `-T` sendet RETURN bereits
# selbst; kein zusaetzliches `\n` in den String einbetten, sonst wird es als
# Text mitgetippt.
tools/m65tools/m65 -l /dev/ttyUSB1 -T '(+ 1 2)'

# Sicherer REPL-Einzeiler: erst aktives Echo pruefen, dann RETURN senden.
scripts/hw-jtag-repl.sh --verified-input --input-retry-wait 0.2 \
  --timeout 20 --timeout-kill-after 2 --form '(+ 1 2)' --expect '3'

# Host-Regressionen fuer Parser, Pre-submit und Post-submit ausfuehren:
make workbench-ux-harness-selftest

# Text-/PNG-Screenshot ziehen. Bei diesem m65-Build ohne Leerzeichen/=
# schreiben; sonst wird der Dateiname als PRG oder mit fuehrendem "=" genutzt.
tools/m65tools/m65 -l /dev/ttyUSB1 -Sbuild/hw/screen.png

# Speicherbereich sichern; Adressen vorher z. B. aus llvm-nm des .elf holen:
tools/m65tools/m65 -l /dev/ttyUSB1 --memsave 0xADDR:0xEND=build/hw/dump.bin
```

Hinweis zu Watchpoints: Der aktuell eingecheckte `m65`-Build bietet per
`--help` einen PC-Breakpoint (`-B`) sowie Screenshot/`--memsave`, aber keine
sichtbare CLI-Option zum Setzen eines Speicher-Write-Watchpoints. Debug-Pläne
sollten sich daher auf Software-Latches, Border-Codes, Screenshots und
`--memsave`-Dumps stuetzen, bis ein verifizierter Monitor-Watchpoint-Pfad
existiert.

Für Diagnose-Builds sind besonders nützlich:

- `gc_runs`, `gc_badobj`, `mem_oom` aus `src/mem.c`/`src/mem.h`.
- Mit `-DLISP65_DMA_PROF`: `dma_cell`, `dma_code`, `dma_wr`, `dma_sym`,
  `perf_allocs`, `perf_vm_ops`.
- Statische Allokator-Zustände wie `alloc_high`/`gc_frozen` können trotz `static`
  über das ELF-Symbolbild/`llvm-nm` für Debug-Dumps gefunden werden, wie die
  xemu-Diagnose bereits vormacht.

`scripts/hw-jtag-counters.py` automatisiert den Standardfall: Es löst bekannte
Zählersymbole aus dem PRG-ELF auf, dump't sie per `m65 --memsave`, dekodiert
Little-Endian-Werte und schreibt einen Report nach `build/hw`.

`scripts/hw-jtag-repl.sh` automatisiert den einfachen REPL-Fall. Ohne
`--verified-input` sendet es eine oder mehrere einzeilige Formen per `m65 -T`.
Der sichere Workbench-Pfad verwendet `--verified-input`: komplette Form per
`m65 -t`, aktiven Screenshot exakt pruefen und RETURN erst danach separat
senden. `--input-retry-wait` steuert nur die Wartezeit um einen Pre-submit-Retry;
`--timeout` und `--timeout-kill-after` begrenzen jeden `m65`-Prozess. Danach
zieht das Script einen Screenshot plus bereinigten Textdump und kann mit
`--expect` einen sichtbaren Marker pruefen. Es verwendet keinen Reset und ist
fuer interaktive Workbench-Retests gedacht, nachdem das Produkt bereits per
Etherload laeuft.

Der aktuelle IDE-Performance-Bericht (`docs/ide-performance-analysis.md`) nutzt
genau dieses Muster: Lisp-Benchmarks werden über die serielle Tastatur eingegeben,
danach werden Runtime-Zähler per `--memsave` ausgelesen.

Weitere Stress-Test-Szenarien und der erste autonome Full-HW-Stresslauf stehen in
`docs/hardware-stress-tests.md`.

## Sicherheitsregeln

- Standardmäßig zuerst `--dry-run` ausführen und die resultierenden Kommandos
  prüfen.
- Keine Live-`xmega65`-/Etherload-/JTAG-Sessions aus Scripts starten, wenn das
  nicht ausdrücklich gewollt ist. Frühere liegengebliebene Emulatorinstanzen
  haben den Host bereits ausgelastet.
- Für Etherload-HW-Tests gilt die PRG-Ende-Invariante des jeweiligen Targets.
  Historische Targets nutzen `prg_file_end < $C000`; der aktuelle
  Workbench-Pin hat ein eigenes Gate bis `$C0C0` und misst aktuell
  `prg_file_end=0xc04f`. Vor HW-Deploy nicht blind alte Limits umgehen, sondern
  das passende Footprint-Gate verwenden.
- Die `build/bytecode/stdlib-p0.*`-Artefakte sind gekoppelt. Keine konkurrierenden
  Builds unterschiedlicher Stdlib-Profile parallel laufen lassen.
- D81-Tests schreiben teilweise in vorallozierte Slots. Test-Images nicht mit
  Arbeits-/Nutzerdaten mischen.
- Sichtbare Tests enden absichtlich in einer Endlosschleife, damit Rahmenfarbe und
  Ergebniszeile stehen bleiben. Fuer den naechsten Lauf normalerweise direkt
  wieder per Etherload deployen; `m65 -F` nur bei echtem Freeze verwenden, weil
  danach SHIFT+£ erneut noetig ist.

## Empfohlene Reihenfolge

1. Lokal: `make ...-dry-run` oder jeweiliges Script mit `--dry-run`.
2. Sicherstellen, dass Remote/Etherload am Geraet scharf ist. Wenn es noch steht,
   keinen Reset ausloesen.
3. Falls D81 gebraucht wird: `mega65_ftp -e -y -c 'put ... NAME.D81'`.
4. PRG/Blob per `run-on-mega65.sh` deployen.
5. Bei sichtbaren Tests Rahmenfarbe/Ergebniszeile prüfen.
6. Bei Diagnose-Tests per JTAG Screenshot oder Speicher-Dump ziehen.
7. Nur bei Freeze: `m65 -l /dev/ttyUSB1 -F`, danach am Geraet wieder SHIFT+£.
