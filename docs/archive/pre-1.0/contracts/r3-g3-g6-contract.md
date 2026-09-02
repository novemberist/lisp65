# R3-Vertrag: G3-Vorfilter und autonomer G6-Kaltstart

Status: Produktblock implementiert, kompletter variierter Produkt-Doppelbau
und statischer 15-Faelle-Preflight bestanden. G3 hat alle neun
`emulator-valid`-Faelle bestanden. Im aktiven Stock-Core-SD-D81-Profil sind
fuenf `hardware-only`-Faelle anwendbar; der physische Write-Protect-Fall ist
manifestgebunden `n/a`, weil kein physisches Medium und kein virtueller
Read-only-Schalter vorhanden ist. Der exakte 13-Artefakt-Kandidat wird nach
jedem Produkt-SHA-Wechsel unter R4 neu versiegelt.

Der maschinenlesbare Vorlaufvertrag ist `config/r3-g3-g6-contract.json`, die
Fallmatrix `tests/bytecode/dialect-v2/r3-boot/cases.json`. Die abgeschlossene
G3-/R4-Autoritaet liegt im registrierten R4-Siegel. R3 folgt strikt der
Reihenfolge Vertrag, Harness-Skeleton, Stager-Produktblock, G3,
R4-Kandidatensiegel, globale G5-Matrix und G6. Keiner der hier beschriebenen
Probenbefunde erteilt Release-Autoritaet.

## Fidelity-Grenze

Xemu ist fuer den Kaltstart ein Vorfilter, Hardware bleibt der Arbiter. Jeder
Fall traegt genau einen Fidelity-Tag:

- `emulator-valid` belegt statische Bindungen, Katalog- und Staginglogik,
  Kontrollfluss sowie die Medienpolicy ohne physische Timingbehauptung;
- `hardware-only` belegt F011-/SD-/DMA-, Reset-, Power-Cycle- oder reale
  Medienwechsel-Eigenschaften.

G3 bedeutet ausschliesslich, dass alle neun `emulator-valid`-Faelle auf dem
gebundenen Emulatorstack bestanden sind. Insbesondere behauptet G3 nichts
ueber F011-Timing, die reale SD-Pufferadresse, DMA-Timing oder physische
Reset-Semantik. G6 setzt gebundenes G3, den versiegelten R4-Kandidaten und
dessen globale G5-Evidenz voraus; es umfasst alle im gebundenen Profil
anwendbaren Hardwarefaelle auf demselben ROM-/Core-/Produktartefaktsatz und
ein explizites, manifestgebundenes N/A-Receipt fuer jeden nicht anwendbaren
Fall. Ein kuenstlicher PASS per JTAG oder Core-Manipulation ist verboten.

## Zwei-Disketten-Modell

Der verifizierte Alltag benutzt nur Laufwerk 8. Laufwerk 9 ist ausdruecklich
unverifizierter Nicht-Scope und wird vom Preflight abgelehnt.

1. `L65SYS,65` ist das schreibgeschuetzte Produktmedium. Es enthaelt Stager,
   Workbench-PRG, Bank-5-Preload, Attic-Katalog, Profil und IDE/IDEX/M65D.
2. Die Workbench bootet, staged, kettet und laedt die residente Komposition.
3. Danach fordert sie genau einmal zum Wechsel auf ein valides eigenes
   1581-Medium auf; dessen Name und ID sind frei.
4. Erst nach erfolgreicher Validierung als Nicht-Produktmedium wird der
   Swap-Latch geloescht; die Nutzersitzung schreibt auf dieses Medium.

Das Ship-Paket liefert eine vorformatierte, leere `L65WORK.D81` als
Bequemlichkeitskopie mit. Einen On-Device-Formatter gibt es in 1.0 nicht;
jede anderweitig valide 1581-Diskette funktioniert jedoch ohne Umbenennung.
Nur die Produktdisk wird durch die Konjunktion aus Name `L65SYS`, ID `65` und
dem Packer-verifizierten Boot-Strukturmarker `L65B` an Header-Offset 29 erkannt
und abgelehnt. Der Packer bindet den Marker an die verifizierten Pflichteintraege
`AUTOBOOT.C65`, `BOOT.ID`, `LISP65.PRG`. Zwei gleich benannte Medien bleiben durch ein bei jedem
erfolgreichen Remount frisch erzeugtes Generation-Token unterscheidbar.

Die D81-Datei selbst besitzt im verwendeten Abbildformat kein belastbares,
selbstvollstreckendes Schreibschutzbit. Deshalb traegt das Paket die
Schreibschutzentscheidung als SHA-gebundenen Mount-Descriptor plus Dateimodus
`0444`; der reale Hardwarefall prueft zusaetzlich den physischen
Schreibschutz. Das ist keine Emulatorbehauptung ueber physische Medien.

M65D klassifiziert das Medium vor jedem Write und nochmals vor dem
Directory-Publish. Die mehrfaktorielle Produktidentitaet fuehrt vor jeder
Mutation zu `product-media-read-only`; sonst ist jedes valide 1581-Medium
beschreibbar. Der Transaktions-Latch bindet das frische Mount-Token sowie
den vollstaendigen kanonischen 16-Byte-Namen, beide ID-Bytes und den exakten
Hardware-Mount-Token aus D68B/D68C--D68F. Status 8 bezeichnet nur einen vor
Transaktionsbeginn erkannten Swap und darf genau einen Remount-Retry ausloesen.
Ein Wechsel nach Transaktionsbeginn liefert den terminalen Status 12
`media-changed-during-transaction`; weder IDE noch M65D remounten oder
wiederholen dann automatisch. Der Nutzer prueft das eingelegte Medium und
startet den Save explizit neu. Der fruehere Status `wrong-work-media` (11)
bleibt ein nie emittierter Tombstone.

Das native D68B--D68F-Token wird unmittelbar nach der gueltigen
Medienklassifikation und vor der transaktionsgebundenen Planung erfasst.
Scheitert ein nachfolgender Planungs-Read mit Status 6, wird er genau dann zu
terminalem Status 12 umklassifiziert, wenn das Token inzwischen abweicht.
Bei unveraendertem Token bleibt der echte Lesefehler Status 6. Beide Wege
enden vor dem ersten Write; ein automatischer Remount-Retry ist fuer den
umklassifizierten Status 12 verboten.

Der native Sektorpfad prueft D68B--D68F vor dem RMW-Read, nach dem Read,
als letzte Praedikatsfolge vor dem Write-Kommando, nach BUSY sowie vor und
nach dem unabhaengigen Readback. BAM- und Directory-Writes besitzen damit
die gleiche Vor-/Nachwache wie Datenwrites und werden vor dem naechsten
Transaktionsschritt erneut geprueft. Das unvermeidbare Restfenster zwischen
letztem D68F-Read und `STA $D081` wird aus dem finalen Produktdisassembly in
Zyklen belegt. Die Owner-Entscheidung vom 2026-07-14 akzeptiert dieses Fenster
auf dem offiziellen Stock-Core als ausdrueckliche Vertragsgrenze: Es gibt
keinen Atomizitaetsanspruch gegen einen Freezer zwischen letzter Pruefung und
Schreibtrigger. Hoestens ein bereits gestarteter Daten-, BAM- oder
Directory-Sektor kann das neu eingelegte Medium treffen; die Nachpruefung
liefert danach terminal Status 12, weitere Writes und automatische Retries
sind verboten. Das ist keine Power-Loss-Analogie: Ein Metadatensektor von A
auf B ueberquert die Mediengrenze und kann Bs Dateisystem beschaedigen.

Track 40/Sektor 0 ist ausschliesslich Linkwurzel und 1581-Header; dort gibt es
keine Directory-Slots. Der erste zulaessige Entry-Sektor ist T40/S3. Jeder
produktive `load`-/`load-lib`-/IDE-Dateisuchpfad beginnt deshalb auf T40/S3;
der listenbildende `dir`-Walker darf die Linkwurzel lesen, ueberspringt dort
aber alle acht 32-Byte-Bereiche. Dieselbe Null-Slot-Regel gilt fuer R3-/R6-
Offline-Parser. Ein wie ein Dateieintrag praeparierter Header muss fail-closed
ignoriert werden.

Jeder Blank-D81-Save wird nach Create, Replace und Mehrsektor-Ketten durch zwei vom
M65D-Walker unabhaengige Host-Zeugen abgenommen: der volle D81-Parser sieht
exakt die sichtbare Datei und `d81_bam_sanity` belegt, dass die allokierten
Datenbloecke exakt den sichtbaren Ketten entsprechen. T40/S0 darf dabei nicht
einmal als Write-Ziel erscheinen und bleibt byteidentisch. Header-Write,
Blockleck, Doppelbelegung oder eine Abweichung von 3160 Datenbloecken stoppen
das Gate. Ein M65D-Eigenreadback ist dafuer ausdruecklich keine Autoritaet.
Zusaetzlich injiziert die Hostmatrix einen D68B--D68F-Wechsel unmittelbar vor
dem Daten-, BAM- und Directory-Write. Je Phase werden Quell- und Ziel-D81 als
vollstaendige, unabhaengig geparste Abbilder geprueft; das Zielmedium darf nie
veraendert sein. Drei getrennte adversariale Faelle injizieren ausserdem nach
der letzten Wache und vor dem Kommando je genau einen Daten-, BAM- und
Directory-Write. Sie sind als `known-contract-boundary-characterized`, nie als
Sicherheits-PASS, gewertet: A bleibt fuer den isolierten Befehl byteidentisch,
B aendert hoechstens den einen Zielsektor, danach folgen Status 12 und null
weitere Writes. Nach diesen sechs automatisierten Faellen bleibt genau eine
reale Freezer-Bestaetigung auf Hardware; beide Medien werden danach geprueft.

## Eigenstaendiger Stager

`AUTOBOOT.C65` kettet in ein separates Stager-PRG. Der Stager laeuft vor dem
Produkt und darf dort freien Maschinen-RAM benutzen. Er ist nicht in das
Workbench-PRG gelinkt; alle bestehenden Produktartefakte muessen byteidentisch
bleiben. Sowohl Workbench-Bank-0-Delta als auch Boot-Overlay-Delta muessen
null sein.

Seine geschlossene Zustandsfolge lautet:

1. kompilierte Stager-ID gegen Descriptor, Produkt-PRG, Katalog, Profil und
   Libraries desselben Produktsets pruefen;
2. Bank-5-Preload und Attic-Katalog pruefen;
3. bei beiden gueltigen Bereichen ohne Restage fortfahren;
4. bei fehlendem oder CRC-rotem Katalog beide Bereiche vollstaendig vom
   Produktmedium restagen; Teilrestage ist verboten;
5. nach jedem Restage beide Bereiche erneut pruefen;
6. nach hoechstens zwei fehlgeschlagenen Versuchen mit
   `L65SYS DISK ERROR - CHECK MEDIA` halten;
7. erst nach erfolgreicher Re-Verifikation in das exakt gebundene
   Workbench-PRG ketten.

Power-Verlust ist damit vom Reset unterschieden: Ein power-fester Katalog wird
nicht behauptet. Der Kernfall `power-cycle-autoboot-restage-repl` muss auf
Hardware von einem fluechtigen Zustand ohne Host, JTAG, Etherload oder
getippten BOOT-Befehl bis zur REPL gelangen.

## Fallmatrix

| Fall | Fidelity | Gate | Kernaussage |
| --- | --- | --- | --- |
| `artifact-preflight-exact-set` | emulator-valid | G3 | Vollstaendige Bindung von Targets, Verifiern, ROM, Emulator und Medien vor Start |
| `catalog-crc-reject-restage` | emulator-valid | G3 | CRC-roter Katalog wird nie gekettet; Vollrestage |
| `catalog-missing-restage` | emulator-valid | G3 | Fehlende Bank-5-/Attic-Daten erzwingen Vollrestage |
| `catalog-valid-stage-chain` | emulator-valid | G3 | Gueltiger Zustand nimmt den Fastpath zum gebundenen Produkt |
| `drive9-rejected` | emulator-valid | G3 | Laufwerk 9 wird vor jedem Device-Zugriff abgelehnt |
| `product-media-identity-write-reject` | emulator-valid | G3 | Save auf der mehrfaktoriell erkannten L65SYS-Produktdisk endet vor der ersten Mutation |
| `product-prg-byte-identity` | emulator-valid | G3 | Separater Stager bewegt kein bestehendes Produkt-SHA und keine Bank-0-Bytes |
| `stager-entry-chain-control` | emulator-valid | G3 | Geordnete Phasen erreichen die Produktuebergabe exakt einmal |
| `arbitrary-user-media-save-remount-read` | emulator-valid | G3 | Beliebig benanntes valides Nicht-Produktmedium besteht Save/Remount/Read; unabhaengiger Blank-D81-/BAM-Zeuge deckt Create, Replace und Mehrsektor-Ketten ab |
| `disk-swap-resident-composition` | hardware-only | G6 | IDE+IDEX+M65D bleiben ueber den Ein-Laufwerk-Wechsel resident und aufrufbar |
| `mid-write-media-swap-abort` | hardware-only | G6 | Ein Planungs-Read-Paar pinnt Status 12 bei Tokenwechsel und Status 6 bei stabilem Token jeweils vor jedem Write; drei normale Tokenwechsel enden vor dem Kommando mit Status 12; drei adversariale Faelle pinnen die akzeptierte Grenze auf hoechstens einen fremden Sektor und eine reale Freezer-Bestaetigung bleibt innerhalb derselben Grenze |
| `power-cycle-autoboot-restage-repl` | hardware-only | G6 | Power-Cycle, Autoboot, Restage und REPL ohne PC |
| `product-medium-physical-write-protect` | hardware-only | G6 | Physisches Medium: Raw-Write wird verworfen; Stock-Core-SD-D81-Profil: manifestgebunden n/a, kein synthetischer PASS |
| `warm-reset-valid-catalog-fastpath` | hardware-only | G6 | Reset-erhaltener Katalog nimmt ohne Restage den Fastpath |
| `work-media-save-remount-read` | hardware-only | G6 | Create/Read/Replace/Remount/Read auf dem Workmedium |

Vor jedem Emulator- oder Hardwarelauf ist der statische exakte
15-Faelle-Preflight Pflicht. Kein Target darf ein ungebundenes Artefakt oder
einen ungebundenen Verifier referenzieren.

Der Produktguard misst zwischen dem letzten Lesen von `D68F` und dem
Abschluss des Schreibens nach `D081` 30 CPU-Zyklen, davon 26 nach Abschluss
des Register-Reads (nominal 740,741 ns bei 40,5 MHz). Dieses Fenster ist
nicht atomar: Der RESTORE-/Freezer-Trap kann an einer Guest-Instruktionsgrenze
unterbrechen; eine Trefferwahrscheinlichkeit ist nicht gemessen und wird nicht
behauptet, das Fenster wiederholt sich fuer jeden Sektor-Write. Der Owner
akzeptiert die exakt charakterisierte Ein-Sektor-Schadensgrenze fuer 1.0 auf
dem Stock-Core. Der Registerguard liefert danach terminalen Status 12 und
stoppt die Transaktion. Ein Drive-0-Mount-Lock wird ohne Projekt-Fork als
Upstream-Vorschlag fuer den offiziellen `mega65-core` gefuehrt; er ist keine
1.0-Releasebedingung.

## ROM-, Core- und Receipt-Bindung

Der Vertrag bindet Wrapper und inneres xmega65-Binary, dessen Build-ID, ROM,
SD-Basis, Compilerkonfiguration und D81-Werkzeug per SHA. Der vollstaendige
lokale Environment-Check ist ein eigener Pflichtlauf unmittelbar vor G3; das
portable Quell-Gate benoetigt die lokale ROM-/SD-Installation nicht.

Jedes Hardware-Receipt bindet mindestens Maschinenseriennummer, Core-ID,
Core-Version, ROM-SHA, Produktartefaktsatz-SHA, beide D81-SHAs, eine eindeutige
physische Cycle-ID und die SHA der Roh-Evidenz. Reset- und Power-Faelle teilen
keine Cycle-ID.

## Reproduzierbare Baseline, historische Probe und Produktblock

Das R2-Siegel band den historischen Produkt-SHA `01fcdddd96ff...`, enthielt
aber weder dessen Produktbytes noch alle generierten Produktinputs. Auch die
eingebetteten D81s enthalten nur Bibliotheken und Testslots. Ein historischer
Binaerdiff war deshalb nicht mehr moeglich; die Einbahn-Grenze bleibt
unangetastet.

Zwei unabhaengige, frische Clones von Commit `99634e79f33...` wurden mit
verschiedenen `PYTHONHASHSEED`-Werten, Zeitzonen und
`SOURCE_DATE_EPOCH`-Werten 2000/2030 gebaut. Beide erzeugten byteidentisch den
Produkt-SHA `da4c72a2254a...`, den achtteiligen Artefaktsatz
`06bc10b9a618...`, VMA `$c34a`, 1805 B Reserve und 269 B Bank. Damit ist keine
aktive Hash-, Zeit- oder Checkout-Nichtdeterministik nachweisbar; der R2-Fund
ist als unversiegelte Live-Buildzustands-Provenienzluecke klassifiziert.

Der Uebergang `01fcdddd...` -> `da4c72a2...` ist mit `bank_delta=0` im
Identitaetsreceipt gebunden. R2 bleibt historisch unveraendert; R3 startet auf
der reproduzierbaren neuen Baseline.

Das historische Launcher-Receipt
`tests/bytecode/dialect-v2/evidence/r3/launcher-probe-receipt.json` steht auf
`passed-not-implemented`. Es baut deterministisch:

- einen 128-B-Strukturstager mit geschlossenen Phasenmarkern, aber ohne
  Medien-I/O und ohne Produktkette;
- eine 819200-B-Produkt-D81 `L65SYS,65` samt gebundenem Mount-Descriptor;
- eine 819200-B-Work-D81 `L65WORK,65`.

Diese Identitaet bleibt ein versiegeltes Probenobjekt. Das Live-Gate versucht
nicht mehr, das historische Receipt gegen den weiterentwickelten Baum neu zu
bauen.

Der reale Produktblock aus Commit `3c0da518ad46...` wurde danach in zwei
frischen, abgetrennten Clones mit verschiedenen `PYTHONHASHSEED`-,
`SOURCE_DATE_EPOCH`-, Zeitzonen- und Kalenderdatumswerten vollstaendig neu
gebaut. In beiden Bauten waren alle 13 Artefakte, Candidate-Manifest und
Produktreceipt byteidentisch. Der gebundene Produktartefaktsatz ist
`d63fd2cb43c139794d8c0a9514fc845cc45cf49a703c1a1d21b92e2db2f71f76`,
die Stager-/Descriptor-Build-ID `fa377c50`.

Der Produktblock enthaelt einen 5118-B-Stager, einen 240-B-Descriptor mit
sieben Records, die exakte Produkt-D81, die leere Work-D81 und den
schreibgeschuetzten Mount-Descriptor. Das Workbench-PRG und das Boot-Overlay
bleiben byteidentisch zu ihrer Baseline. Die 143 IDE-/M65D-Hostfaelle und die
fuenf IDEX-Faelle sind gruen. Weder Emulator noch Hardware wurden fuer dieses
Receipt gestartet.

## Kapazitaetsabschluss

Der fehlgeschlagene erste Produktlink lag bei 16012 B EXT-Headroom. Der
einmalige, marginal gemessene und verhaltensneutrale Reclaim schliesst bei
16439 B: 55 B ueber dem unveraenderten 16-KiB-Nutzerboden. Die finalen
Kompositionswerte sind:

- Bankreserve 269 B, Delta 0;
- EXT-Headroom 16439 B, Kredit +55 B gegen den 16384-B-Boden;
- 121 freie Symbole;
- 2162 B freier Namepool;
- 32 freie Directory-Eintraege nach Align;
- Boot-Overlay-Delta 0.

Die Symbol- und Namepool-Debits gegen die direkte Vorblock-Baseline sind
vorab autorisiert und bleiben ueber ihren gepinnten Boeden. Ab diesem Block
ersetzt das fuenfdimensionale Pflichtfeld `capacity_delta` die reine
Bankbetrachtung fuer jede kuenftige Block- oder Release-Promotion. Bank, EXT,
Symbole, Namepool und Directory muessen jeweils Kredit/null oder durch eine
vorher gebundene Autorisierung gedeckt sein.

### Medienguard-Neupinnung vom 2026-07-14

Der transaktionsgebundene D68B--D68F-Guard verschiebt die reale Runtime-VMA
gegen das letzte R4-Siegel um 172 B. Der gebundene Symboldiff weist 380 B neue
Guard-Pfade und zugleich 217 B Kredit aus der `vm_callprim`-Konsolidierung
aus; die benannte Nettosumme von 163 B plus 9 B Alignment ergibt exakt den
residenten Debit. Die Owner-Entscheidung autorisiert diesen releasekritischen
Sicherheitsaufwand und pinnt die Bankreserve auf 381 B beziehungsweise 1917 B
Post-Boot-Reserve bei unveraendertem 1536-B-Releaseboden.

Nach dem Planungstatus-Single-Source-Abschluss liegt der EXT-Post-Headroom bei
16385 B, ein Byte ueber dem unveraenderten 16384-B-Boden. Diese Restmarge ist
fuer 1.0 funktional null: EXT ist im 1.0-Zug eingefroren, und kein weiterer
Debit ist autorisierbar, auch nicht um ein Byte. Jeder EXT-beruehrende Fix
muss gleichzeitig strukturelle Entlastung liefern. Die benannte
strukturelle Entlastung bleibt das Attic-Regal in 1.1, das die Library-FASLs
aus dieser EXT-Gleichung nimmt. Symbole, Namepool und Directory bleiben bei
120, 2160 B und 32 Eintraegen.

## Bedienung und naechster Halt

```sh
make r3-g3-g6-contract-check
make r3-product-block-check
make r3-product-reproducibility-check
make r3-g3-static-preflight-check
make r3-g3-g6-environment-check
make workbench-product-reproducibility-check
make workbench-product-reproducibility-preflight
make promotion-preflight-check
```

G3 schloss mit 9/9 `emulator-valid`; die damaligen sechs
`hardware-only`-Faelle blieben `not-run`. Die aktuelle Profilauswertung
teilt sie in fuenf anwendbare Faelle und einen expliziten N/A-Fall. Der finale
R4-Cut `8c99a664...` reproduzierte alle 13 Artefakte
unter den variierten Frischclone-Achsen exakt als Set `d63fd2cb...`. Das
zweimal byteidentisch erzeugte und isoliert offline verifizierte
`product-candidate`-Archiv ist im Promotionsregister an SHA `8ca3992e...`
gebunden.

Die globale G5-Matrix ist fuer das spaetere R4-Produktset `20760405...`
hardwaregruen und als `hardware-acceptance`-Archiv `af07b7c4...` versiegelt:
14/14 Faelle, vier eindeutige physische Cycle-IDs, Produkt-SHA-Delta null.
Der lebende Baum ist keine Produktautoritaet. Die fuenf anwendbaren
`hardware-only`-Bootfaelle bleiben bis G6 `not-run`; R6 konsumiert die
versiegelten R4-/R5-Beweisobjekte und bindet das N/A-Receipt an sein exaktes
Manifest.
