# Arbeitsplan nach Carrier-G5: Weg zum Release und Version 1.1 (v2, 2026-07-12)

Status: Ausfuehrungsplan, **Revision 2 nach Codex-Review** —
Phase R neu geschnitten (die interne 14/14-Matrix ist der Abschluss des
CP5-Hardwarebeweises, nicht der Beginn eines unmittelbar paketierbaren
Releases). Prinzipien unverändert: Probe vor Block, Links statt
Schätzungen, ein Block zur Zeit. Die 120-B-Abweichung vom frueheren 555-B-Pin
und der vorab autorisierte 166-B-Preis des Directory-only/L65M-v2-Blocks sind
vollstaendig verbucht; der aktuelle gebundene v2-Link pinnt 269 B fuer ABI
1.1. Kuenftige Block-Receipts weisen ihr Bank-Delta verpflichtend aus.

## Phase R — Weg zum Release (realistisch: Wochen, nicht Tage)

Fortschritt 2026-07-13: R0 und R1 sind abgeschlossen. Der Carrier-Block ist
mit fuenf SHA-gebundenen Checkpoint-Receipts, reproduzierbarem G5-Archiv,
Host-5-Gate und zum Promotionszeitpunkt fuer ABI 1.1 reservierten 555 B atomar
promotet. Die spaetere R2-Abweichung ist mit einem einmaligen 120-B-Debit
geschlossen. Directory-only/L65M-v2 ist fuer exakt 166 B vorab autorisiert,
implementiert und auf 269 B Bank neu gepinnt.
R2 ist abgeschlossen: Die neun Semantikentscheidungen sind mit 17 normativen
Familienfaellen geschlossen; alle fuenf Familien einschliesslich IDE sind
migriert. Nach Bindung der drei R5-Domain-Verifier und der finalen Matrix
steht der Migrationsvertrag inzwischen auf `ready-for-g5`.
Promotionen werden ab Lists dauerhaft als unveraenderliche, im lebenden
Register SHA-gebundene Archive mit eingebettetem Offline-Verifier vollzogen.
Der Capability-/Carrier-Abschluss ist nach derselben Regel rueckwirkend
versiegelt; spaetere Live-Aenderungen invalidieren historische Beweise nicht.
R3 ist abgeschlossen: Der G3-/G6-Vertrag und die nach Fidelity getaggte
15-Faelle-Matrix sind gruen. Nach dem Fund des historischen ABI-3-Literals im
ABI-4-Batchpraedikat erzeugen zwei in Clone, Hashseed, Zeitzone und Zeitkontext
variierte Frischbauten den vollstaendigen 13-Artefakt-Produktblock
byteidentisch als Set `d92b0aac...` mit Build-ID `2371a2c9`. Der reparierte
Produktstand hat G3 erneut mit exakt 9/9 `emulator-valid` bestanden; die sechs
`hardware-only`-Faelle sind ausdruecklich nicht gelaufen.
R4 ist als separates `r4-product-candidate-5e1314f` versiegelt. Das isoliert
offline verifizierte Archiv bindet alle 13 Produktartefakte unter SHA
`bc05335b...`; das alte Siegel `r4-product-candidate-8c99a66` bleibt
unveraendert als historischer Beleg fuer `d63fd2cb...`. R5 konsumiert nur das
neue Siegel, nicht den lebenden Baum.
Der erneuerte R5-Static-Preflight fuer Lauf `r5-run-20260713-05` war
abgeschlossen: Er materialisierte und verifizierte alle 13 Produktartefakte,
bindet nach zwei reinen Harness-Fixes die getrennte 80-teilige Test-Closure
`37f1ac92...` ohne Produktueberlappung, weist 6/6 abgelehnte
Verifier-Manipulationen nach und schliesst alle 14 Ketten vom Target ueber
Rohbeleg und natives Receipt bis zum normierten Fall-Receipt und seinem
Verifier. Das zusaetzliche Designator-Gate liest 102 anonyme Funktionsnamen
aus den versiegelten IDE-/IDEX-/M65D-Manifesten und weist ueber alle zehn
Harness-Skripte null Funktionsdesignator-Referenzen nach. Candidate
`ab68f63d...` und das getrackte Preflight-Receipt `ec18b164...` meldeten
Hardware `not-run`; die sieben
gruenen Receipts des abgebrochenen Laufs gegen das alte Produktset bleiben
rein historisch. `overlay-stack-guard` und `stdlib-runtime` sind frisch gruen
und nach der letzten Closure-Aenderung offline re-verifiziert. Der erste
`ux-complete`-Anlauf entdeckte vor dem Persistenzschritt einen direkten
Harness-Aufruf einer Directory-only-Funktion; er besitzt kein Receipt. Die
gesamte Klasse direkter und Higher-Order-Funktionsdesignatoren ist statisch
geschlossen. Der anschliessende echte Produktlauf fand jedoch elf anonym
emittierte vertragliche Exporte und den ordinal frueh gebundenen `%ide-x`-
Override. R4/R5 sind deshalb wiedereroeffnet. Der allgemeine
`late_bound_exports`-Vertrag, drei Paritaetsgates, Hook-Audit und realer
IDE→IDEX-Sequenzbeweis sind gruen; die Komposition kostet exakt ein Symbol
und sieben Namepool-Bytes. Der reale Link haelt Bank und Boot-Overlay
bytegenau, und zwei variierte Frischbauten liefern das neue 13-Artefakt-Set
`20760405...` mit Build-ID `d46a2bab` byteidentisch. Der statische
15-Faelle-R3-Preflight ist gebunden. G3 besteht gegen genau dieses Set erneut
9/9 `emulator-valid`; alle sechs `hardware-only`-Faelle bleiben `not-run`.
Das neue R4-Siegel ist auf Cut `312d5ab...` geschlossen. Das isoliert offline
verifizierte Archiv `r4-product-candidate-312d5ab.tar.gz` bindet alle 13
Produktartefakte als Set `20760405...` unter Archiv-SHA `6a674276...`; ein
zweiter Archivbau ist byteidentisch. R5-Lauf `r5-run-20260713-06`
materialisierte ausschliesslich aus diesem Siegel. Seine getrennte 80-teilige
Test-Closure `1c15cf3e...` besitzt null Produktueberlappung; der statische
Preflight `b97a6e78...` schloss alle 14 Receipt-Ketten und 6/6
Verifier-Negativmutationen. Danach bestanden zehn Workbench- und vier
Runtime-Faelle auf echter Hardware, die Runtime-Faelle unter vier eindeutigen
physischen Cycle-IDs. Das selbststaendige
`hardware-acceptance`-Archiv `r5-global-g5-e247b06.tar.gz` ist unter SHA
`af07b7c4...` registriert, wurde zweimal byteidentisch gebaut und isoliert
offline verifiziert. Es bindet G5 14/14 an Produktset `20760405...`; G6 0/6
bleibt `not-run`, der Stand ist nicht releasefaehig. Der finale
Ein-Zeremonie-Neulauf ist dauerhaft verzichtbar, weil die SHA-gebundenen
Fall-Receipts mit Cycle-IDs selbst das Beweisobjekt sind.

G6 begann gegen dieses versiegelte Set und steht historisch ehrlich bei 3/6.
Der vierte Fall `work-media-save-remount-read` fand nach einem Freezer-Swap
einen geerbten `$D689=$80`-Zustand: Der Treiber beschrieb den direkten
SD-Puffer, F011 schrieb den unveränderten F011-Puffer zurück, und das
Readback-Verify stoppte mit Status 7. Das vollständige Work-Medium blieb vor
und nach dem Versuch unter SHA byteidentisch. Der Fund ist als Produktbefund
klassifiziert; die drei grünen G6-Receipts bleiben historische Evidenz nur
für `20760405...`. Der Fix verallgemeinert die Regel auf vollständigen
Registerbesitz je F011-/SD-Transaktion, entfernt den rohen SD-Zwischenschritt,
setzt `$D689=$00` pro Operation und macht den erzwungenen `$80`-Vorzustand zum
permanenten Fall-4-Oracle. Der reale Probelink verbessert die Bankmarge von
269 auf 313 B (+44 B), hält EXT bei 16.439 B und bewegt weder Symbole,
Namepool noch Directory; Neupinnung erfolgt erst nach der Hardwareprobe.
Im selben Neupinnungszyklus wird die Owner-Entscheidung zur
Medienpolitik-Inversion umgesetzt: Jedes valide Nicht-Produkt-1581-Medium
ist beschreibbar, die Produktdisk wird durch `L65SYS` + ID + den
Packer-verifizierten `L65B`-Boot-Strukturmarker (gebunden an
`AUTOBOOT.C65`/`BOOT.ID`/`LISP65.PRG`) erkannt, und der Transaktions-Latch
bindet weiterhin Name+ID+Mount-Generation. Der zuvor uebertragene reine
BUFSEL-Zwischenkandidat ist damit ueberholt und erhaelt keine Evidenz.

Der anschliessende Primitive-Sichten-Block schliesst CALLPRIM, Apply,
`function-kind` und Compile-REPL konstruktiv gegen eine Registry-Einzelquelle.
Der finale 13-Artefakt-Kandidat ist Set `7e761343...`/Build-ID `0546c36c`,
haelt 553 B Bankmarge und 16.419 B EXT und ist als
`r4-product-candidate-bdad615` versiegelt. R5-Lauf
`r5-run-20260714-08` besteht darauf alle zehn Workbench- und vier
Runtime-Faelle mit vier physischen Cycle-IDs. Das selbststaendige
`hardware-acceptance`-Archiv `r5-global-g5-2ce5fe6.tar.gz` ist unter SHA
`cc114451...` registriert, zweimal byteidentisch gebaut, isoliert offline
verifiziert und weist drei Manipulationen ab. G5 ist damit fuer
`7e761343...` passed; G6 bleibt 0/6 `not-run`, Release nein. R6 muss dieses
neue Siegel nun byteidentisch neu materialisieren und den 15-Faelle-Preflight
erneuern, bevor die sechs Hardwarefaelle beginnen.

Der anschliessende G6-Fall 4 fand einen Datenintegritaetsfehler in der
1581-Directory-Behandlung. Nach dem M65D-Schreibfix und der vollstaendigen
T40/S0-Leserbereinigung erzeugen zwei variierte Frischbauten 13/13
byteidentische Produktartefakte als Set `44163b31...`/Build-ID `20733c90`.
Bank, EXT, Symbole, Namepool und Directory bleiben unveraendert. Der neue
Kandidat besteht den G3-Emulatorvorfilter mit 9/9; alle sechs Hardwarefaelle
bleiben `not-run`. R4 ist fuer diese Identitaet als
`r4-product-candidate-07de3cf` unter Archiv-SHA `478607d9...` neu versiegelt;
R5-Lauf `r5-run-20260714-10` konsumiert dieses Siegel ausschliesslich,
materialisiert alle 13 Artefakte und bindet die getrennte 80-teilige Closure
`92897d53...`. Sein statischer Preflight ist 14/14 bereit, weist sechs
Verifier-Manipulationen ab und meldet Hardware weiterhin `not-run`. Die
vollstaendigen Source- und Host-Gates einschliesslich Blank-D81-/BAM-Oracle
sind gruen. Die anschliessende Hardware-Session ist 14/14 gruen: zehn
Workbench-Faelle und vier Runtime-Faelle besitzen jeweils ein unmittelbar
offline verifiziertes, SHA-gebundenes Fall-Receipt. Vier unterschiedliche
physische Runtime-Zyklen sind gebunden; ein Readback-Transportfehler nach
Produktstart blieb als fehlgeschlagene Harnessdiagnose getrennt und wurde
erst nach einem frischen Power-Cycle wiederholt. G6 bleibt 0/6 `not-run` und
Release bleibt bis zum neuen R5-Siegel und der R6-Neumaterialisierung gesperrt.
Das neue `hardware-acceptance`-Siegel `r5-global-g5-29c46a5` ist unter
Archiv-SHA `c9539f8d...` registriert. Es enthaelt 191 Dateien, verifiziert
isoliert offline, ist ueber zwei variierte Packlaeufe byteidentisch und lehnt
drei Manipulationsklassen ab. Sein Claim bleibt eng: G5 14/14 fuer
`44163b31...`, G6 0/6 `not-run`, Release nein. R6 muss ausschliesslich dieses
Siegel neu materialisieren.
R6 hat dies als reine Transformation abgeschlossen: Zwei variierte
Paketlaeufe sind fuer 23/23 Dateien und Modi byteidentisch, Paketset
`2fc2014c...`; alle 13 Produktartefakte und neun L65SYS-Eintraege bleiben
byteidentisch zu R5. Beide eingebetteten Archive verifizieren offline und
drei Paketmanipulationen werden abgelehnt. Der 15-Faelle-G6-Preflight wird
auf genau dieses Paket neu gepinnt; Hardware bleibt bis dahin unberuehrt.
Der neue Preflight ist 15/15 gruen: neun `emulator-valid`-Faelle werden aus
R4 versiegelt konsumiert, sechs `hardware-only`-Faelle sind vollstaendig
gebunden und `not-run`. Maschine, Werkzeuge, Produkt-, Medien- und
Archiv-SHAs stimmen; damit ist G6 fuer den ersten hostfreien Kaltstart bereit.

G6-Fall 5 erzwang danach die transaktionale Medienbindung. Der korrigierte
Produktblock besteht die sechs unabhaengigen Zwei-Medien-Oracles und begrenzt
die Owner-akzeptierte Stock-Core-Restluecke fuer Daten, BAM und Directory auf
hoechstens einen Sektor, terminalen Status 12 und null Folgewrites. Der reale
Link pinnt 381 B Bank sowie exakt 16.384 B EXT; Symbole, Namepool und Directory
bleiben 120/2160/32. Zwei variierte Frischclone-Bauten liefern alle 13
Artefakte byteidentisch als Set `1051d782...`/Build-ID `b0aed08c`; G3 besteht
erneut 9/9, alle sechs Hardware-Bootfaelle bleiben `not-run`. R4 ist auf Cut
`18d8c56...` als `r4-product-candidate-18d8c56` unter Archiv-SHA
`af85e2d7...` versiegelt. Das Archiv umfasst 112 Dateien, verifiziert isoliert
offline, ist ueber zwei Packlaeufe byteidentisch und lehnt manipulierte
Produktbytes, Manifestbindungen sowie einen entfernten G3-Beleg ab. R5 muss
diesen Kandidaten nun frisch in 14 Hardwarefaellen mit vier Cycle-IDs pruefen.
Der statische R5-Preflight fuer Lauf `r5-run-20260714-11` ist bereits gruen:
Er materialisiert alle 13 Produktartefakte ausschliesslich aus dem neuen
Siegel, bindet eine getrennte 80-teilige Test-Closure `8e5232f0...` mit null
Produktueberlappung, weist sechs Verifier-Manipulationen ab und schliesst alle
14 Receipt-Ketten. Sein Receipt `799f0111...` behauptet Hardware weiterhin
ausdruecklich `not-run`.

Die anschliessende Hardwarematrix ist auf genau diesem Satz 14/14 gruen. Zehn
Workbench-Faelle teilen eine gebundene Sitzung; Clean, Truncation, Bitflip und
Build-ID-Mismatch besitzen vier getrennte physische Power-Cycle-IDs. Jedes
Fall-Receipt wurde unmittelbar offline verifiziert. Das append-only
Hardware-Siegel `r5-global-g5-087320c` umfasst 191 Dateien, wurde unter
variiertem Hashseed und variierter Zeitzone zweimal byteidentisch als Archiv
`d2a211e8...` gebaut, verifiziert aus dem Archiv allein und lehnt drei
Manipulationsklassen ab. Sein Claim bleibt G5 14/14 fuer `1051d782...`, G6
0/6 `not-run`, Release nein. R6 konsumiert ausschliesslich dieses Siegel.

Der neue R6-Packer-Cut `10f93c9...` transformiert genau diese versiegelten
Bytes. Zwei ueber Hashseed und Zeitzone variierte Paketlaeufe sind fuer 23/23
Pfade, Modi und Bytes identisch und ergeben Paketset `2089b6fd...`; alle 13
Produktartefakte und neun L65SYS-Eintraege bleiben byteidentisch zu R5,
L65WORK bleibt leer. Beide Pakete verifizieren offline, drei Manipulationen
werden abgelehnt und alle Kapazitaetsdeltas sind null. Das neue
Packer-Receipt `5afcd92c...` ist der einzige Eingang des nun folgenden
15-Faelle-Preflights; G6 bleibt bis zu dessen Abschluss 0/6 `not-run`.

Der statische Preflight auf Cut `68b80f4...` ist 15/15 gruen. Er konsumiert
neun versiegelte G3-Faelle und bindet alle sechs Hardwarefaelle mit Maschine,
Werkzeugen, Produkt-, Medien- und Archiv-SHAs als `ready-not-run`. Das
Receipt besitzt SHA `e0e193c0...`; G6 bleibt vor dem ersten hostfreien
Kaltstart ehrlich 0/6 und Release nein.

Der finale Post-Capture-Planungsguard-Kandidat `a2e5fe2d...` besteht im
R5-Lauf `r5-run-20260715-12` alle zehn Workbench- und vier Runtime-Faelle.
Die Runtime-Faelle binden vier getrennte physische Power-Cycles; zwei reine
Transportstopps vor bzw. nach semantischer Ausfuehrung blieben korrekt ohne
Fall-Receipt und wurden fix-forward wiederholt. Alle 14 gueltigen
Fall-Receipts sind offline verifiziert. Das append-only-Siegel
`r5-global-g5-94abc53` umfasst 191 Dateien, ist in zwei Packlaeufen
byteidentisch (`2e22dc80...`), verifiziert aus dem Archiv allein und lehnt
drei Manipulationsklassen ab. Claim: G5 14/14 fuer `a2e5fe2d...`, G6 0/6
`not-run`, Release nein. R6 konsumiert ausschliesslich dieses Siegel.

Packer-Cut `fda8db0...` transformiert genau diese versiegelten Bytes. Zwei
ueber Hashseed und Zeitzone variierte Paketlaeufe stimmen fuer alle 23 Pfade,
Modi und Bytes ueberein und ergeben Paketset `4b341010...`; alle 13
Produktartefakte und neun L65SYS-Eintraege bleiben byteidentisch zu R5,
L65WORK bleibt leer. Beide Pakete verifizieren offline, drei Manipulationen
werden abgelehnt und alle Kapazitaetsdeltas sind null. Das Packer-Receipt
`e473fcad...` ist der einzige Eingang des folgenden 15-Faelle-Preflights;
G6 bleibt bis zu dessen Abschluss 0/6 `not-run`.

Der statische Preflight auf Cut `7614ad1...` ist 15/15 gruen. Er konsumiert
neun versiegelte G3-Faelle und bindet alle sechs Hardwarefaelle mit Maschine,
Werkzeugen, Produkt-, Medien- und Archiv-SHAs als `ready-not-run`. Das
Receipt besitzt SHA `bfbc324f...`; G6 bleibt vor dem ersten hostfreien
Kaltstart ehrlich 0/6 und Release nein.

Der Status-Single-Source-Kandidat `c41b9643...` besteht im R5-Lauf
`r5-run-20260715-13` alle zehn Workbench- und vier Runtime-Faelle. Die zehn
Workbench-Faelle teilen eine gebundene Sitzung; `clean`, `truncated`,
`bitflip` und `build-id-mismatch` besitzen vier getrennte, physisch
bestaetigte Cycle-IDs. Alle 14 Fall-Receipts wurden unmittelbar und beim
Siegelbau erneut offline verifiziert. Zwei ueber Hashseed und Zeitzone
variierte Packlaeufe erzeugen dasselbe 4.878.961-Byte-Archiv mit 191 Dateien
und SHA `be7b3f17...`. Das append-only Siegel
`r5-global-g5-b40cbe2` verifiziert isoliert ohne Repository und lehnt
Manipulationen an Produktbyte, Fall-Receipt und Top-Receipt ab. Claim: G5
14/14 fuer `c41b9643...`; G6 `not-run`; Release nein. R6 konsumiert
ausschliesslich dieses Siegel.

Packer-Cut `e21f984...` transformiert genau die registrierten R4-/R5-
Siegelbytes. Zwei ueber Hashseed und Zeitzone variierte Laeufe stimmen fuer
24/24 Pfade, Modi und Bytes ueberein und ergeben Paketset `925cda9a...`.
Alle 13 Produktartefakte sowie neun L65SYS-Eintraege bleiben byteidentisch;
L65WORK bleibt leer. Die zusaetzliche 24. Paketdatei gegenueber dem frueheren
Stand ist allein das profilgebundene G6-Hardwareprofil. Beide Pakete
verifizieren offline, und Manipulationen an Produktbyte, Manifest sowie
eingebettetem R5-Archiv werden abgelehnt. Das Packer-Receipt
`a6a20dff...` weist alle Kapazitaetsdeltas als null aus und meldet G6
`not-run(5/5-applicable)` mit sichtbar profilgebundenem WP-N/A; Release nein.

Der statische Preflight auf Cut `499d6df...` ist 15/15 gruen. Er konsumiert
neun versiegelte G3-Faelle, bindet die fuenf anwendbaren Hardwarefaelle mit
Maschine, Core-/ROM-, Produkt-, Medien-, Werkzeug- und Verifier-SHAs als
`ready-not-run` und fuehrt den physischen Produktmedien-WP-Fall als
profilgebundenes N/A. Profil-Receipt `2fec324c...` und Preflight-Receipt
`9a3e5c8c...` verifizieren offline. G6 bleibt 0/5 `not-run`; Release nein.

Der finale G6-Lauf gegen Produktset `c41b9643...` hat alle fuenf im
Stock-Core-SD-D81-Profil anwendbaren Hardwarefaelle bestanden. Der physische
Produktmedien-Schreibschutz bleibt als profilgebundenes N/A sichtbar; der
enge Claim lautet daher 5/5 anwendbar bestanden, 1/1 N/A, Release bis R7
gesperrt. Top-Receipt `edcca70c...` bindet Maschine `TE0000B18447`, Core
`git-03b24c6b`, ROM, Preflight, Ship sowie jedes Fall-Receipt. Das
append-only R6-Siegel `r6-g6-hardware-acceptance-aed1595` besitzt SHA
`b339a274...`, enthaelt 173 Payloaddateien, verifiziert aus dem Archiv allein
und lehnt Manipulationen an Produktbyte, Fall-Receipt und Top-Receipt ab.

Die beiden R7-Manifestvoraussetzungen sind ebenfalls geschlossen. Der
oeffentliche Entwurf ersetzt fuenf hostlokale Toolchain-Pfade durch Rollen
und behaelt ihre SHAs; ein Cross-Midnight-Doppelpack ueber die lokalen Daten
2026-07-14 und 2026-07-16 erzeugt byteidentische Bytes, weil `packed_on` aus
dem gebundenen Commit-Zeitstempel stammt. Produktdelta bleibt null. R7 selbst
beginnt erst mit der noch festzulegenden privaten Releaseidentitaet.

R7 ist am 2026-07-15 als **lisp65 1.0.0 (Dialect V2)** geschlossen. Der
annotierte Tag `v1.0.0` zeigt auf Cut `5897294`. Das selbstverifizierende
Bundle `releases/lisp65-1.0.0.tar.gz` besitzt SHA `5bea5ca9...`, bettet das
registrierte G6-Siegel `b339a274...` ein und kopiert alle 13 Produktartefakte
bytegleich aus dessen versiegeltem R6-Ship. Zwei variierte Packlaeufe sind
byteidentisch; Produktbyte-, Manifest- und Quellsiegel-Manipulation werden
abgelehnt. Produktdelta und alle Kapazitaetsdeltas sind null.

- **R0 Konsistenz:** Migrationsvertrags-SHA neu binden (bindet noch den
  alten CP5-Hauptvertrag), alle Vertragsvalidatoren grün.
- **R1 CP5 transaktional 5/5:** Receipt-Emitter, Evidenzarchiv,
  Host-5-Gate und 555-B-Status gemeinsam schließen.
- **R2 Familienmigration abschließen (abgeschlossen 2026-07-13):** die neun offenen
  Semantikentscheidungen, dann Lists → Strings → System/Runtime → IDE
  samt gepinnter Pflichtblöcke. Das ist der größte Restposten vor dem
  Release; jede Familie nach etabliertem Ritual (Fixture → Receipts →
  Familienbudget, isolierter Link zuerst).
- **R3 G3- und G6-Vertrag bauen (abgeschlossen 2026-07-13):** Release-
  Vertrag + G3-Emulator-Produktfluss (heute hart gesperrt, Makefile) und den **autonomen
  Workbench-Kaltstart/Recovery als eigenen Produktblock** (Bank-5-/
  Attic-Restaging von SD/D81 ohne PC — bisher bewusst vertagt, jetzt
  releasepflichtig; ändert Produktartefakte → neue Identität).
- **R4 Finalen Produktkandidaten versiegeln (abgeschlossen 2026-07-13):** erst hier entsteht
  die Release-Produktidentitaet. Eigener Archivtyp `product-candidate`, alle
  13 Produktbytes und die vollstaendige G3-Evidenz werden selbststaendig
  offline pruefbar eingebettet. Das Siegel bewahrt auch die Grenze G3 9/9,
  Hardware 0/6, G5/G6 offen, nicht releasefaehig.
- **R5 Globale G5-Matrix (abgeschlossen und versiegelt 2026-07-15):** auf exakt diesem finalen Artefaktset. Der statische
  Preflight konsumiert das registrierte R4-Siegel als einzige
  Produktidentitaetsquelle; der lebende Baum ist keine Matrixautoritaet.
  Matrixvertrag, echte Verifier, finale Familienmessungen, Candidate-
  Bindungen, Fall-Receipt-Packer und Negativbeweise sind im versionierten
  Preflight-Receipt gruen. Zehn Workbench- und vier Runtime-Faelle sind
  genau einmal offline verifiziert; vier eindeutige Power-Cycle-IDs sind im
  `hardware-acceptance`-Siegel gebunden.
- **R6 Profilumschaltung, Ship und G6 (abgeschlossen 2026-07-15):** Der
  Promotionspacker ueberfuehrt die bewiesenen Bytes unveraendert ins
  Zwei-Medien-Ship (der interne Kandidat traegt bewusst `shippable=false`).
  Zwei in Hashseed und Zeitzone variierte Laeufe erzeugen 24 byte- und
  modusidentische Dateien. Alle 13 Produktartefakte und alle neun
  L65SYS-Eintraege sind byteidentisch zu R5; L65WORK ist leer. Der
  Standardbibliothek-only-Verifier arbeitet aus dem Paket allein, und drei
  Manipulationen werden abgelehnt. Nach allen produkt-SHA-aendernden Funden
  wurden R4, R5 und R6 regulaer neu gepinnt. Der finale PC-freie Lauf besteht
  die fuenf anwendbaren Hardwarefaelle; ein selbststaendiges
  `hardware-acceptance`-Siegel bindet die komplette Receipt- und
  Rohbelegkette.
  Der physische Produktmedien-WP-Fall bleibt mit sichtbarer N/A-Begruendung
  ausserhalb dieses Profils.
- **R7 Privater Release-Tag (abgeschlossen 2026-07-15),** Bundle, Mirror. („Veröffentlichung“ im
  öffentlichen Sinn ist ein separater späterer Schritt und erfordert
  vorab die Lösung der PDF-Lizenzfrage bzw. das kuratierte Public-Repo.)

## Phase S — Stabilisierung

- **S1 Feedback-Kanal** (`Ehh`-/Statuscode-Meldeweg): vor jeder
  Nutzerverteilung, nicht danach.
- **S2 Zweitgerät/Community-Tester:** als Abnahmeredundanz nur wirksam,
  wenn **vor** dem G6-Lauf eingerichtet; daher explizite Voraussetzung
  für R6, obwohl die organisatorische Arbeit in Phase S liegt.
- **S3 Housekeeping:** Btrfs-Balance, `superseded_by`-Marker,
  Ergonomie-Retrospektive nach ersten echten Nutzerprogrammen.

## Phase 1.1 — Reihenfolge gemäß gepinnten Abhängigkeiten

(Verbindlich laut Migrationsvertrag: Directory-only/L65M-v2 **vor**
Export-Interning; First-Class-Buffer **vor** `unload`; Export-Interning
**vor** `unload`. Export-Interning und `unload` sind getrennte Blöcke.)

1. **Banner** (Spec liegt vor; Budgetreferenz korrigiert auf „aktueller
   Bankstand beim Blockstart“).
2. **First-Class-Buffer** (+ atomare String-Konstruktoren zurück).
3. **Export-only-Interning** auf dem bereits in R2 abgeschlossenen
   Directory-only/L65M-v2-Block.
4. **`unload`.**
5. **Tick-Hook** und **Listen-Prim-Vereinheitlichung**: Einsortierung
   nach gemessenen Bank-0-Kosten (Probe). Bei der Prim-Vereinheitlichung
   gilt: Der Implementierungs-Sonderpfad darf entfallen, die
   codeobjektgebundene STRICT_ARITY-Semantik nicht.

## Leitplanken

- R0–R7 enthalten ausschließlich releasekritische Migration,
  Boot-/Recovery- und Beweisarbeit; keine frei wählbaren Komfort- oder
  1.1-Features. 1.1 startet nach R7.
- Kapazitaet: Ausgabe nur nach Probe, pro Block, mit vorab erteilter
  Autorisierung. Der aktuelle versiegelte Bank-Pin ist 332 B; EXT liegt mit
  16.385 B ein nicht ausgebbares Byte ueber dem Boden und ist fuer 1.0
  eingefroren. Jedes neue Block- und
  Promotionsreceipt enthaelt ein arithmetisch geprueftes `capacity_delta`
  fuer Bank, EXT, Symbole, Namepool und Directory; unautorisierte negative
  Drift ist rot. R4 weist zusaetzlich das Boot-Overlay-Delta aus.
- Der kanonische Default-Stack-Guard zeigt auf denselben Artefaktsatz wie der
  explizite v2-Target. Die vor Directory-only gemessene Baseline war bei
  `$c2a4`/1971 B mit Bank-Delta null gruen; der aktuelle Produktlink liegt bei
  `$c34a`/1805 B und besitzt den autorisierten Block-Debit. Die
  R4-Vorbedingung ist erfuellt.
- Jeder Block einzeln integrierbar und verlustfrei pausierbar.
