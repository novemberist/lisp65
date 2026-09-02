# R6/G6: statischer Preflight und Hardware-Runbook

Status: freigegebener G6-Ausfuehrungsvertrag. Der statische 15-Faelle-
Preflight muss vor der ersten physischen Aktion gruen sein.

## Autoritaet und Grenze

G6 konsumiert das R6-Ship-Paket; es baut kein Produkt. Die neun
`emulator-valid`-Faelle konsumieren ihre im eingebetteten R4-Archiv
versiegelten G3-Receipts. Fuenf `hardware-only`-Faelle sind im aktiven
Stock-Core-SD-D81-Profil anwendbar und werden auf einem gemeinsamen,
neu versiegelten Produktset ausgefuehrt. Der physische Write-Protect-Fall ist
mit einem an genau dieses Ship-Manifest gebundenen Profil-Receipt `n/a`.
Jedes Hardware-Receipt bindet die
Maschinenseriennummer, Core-ID und -Version, ROM-, Produkt- und Medien-SHAs,
seine Rohbelege sowie bei Power-/Reset-Faellen eine eindeutige Cycle-ID.

Ein Fall besteht erst nach `case-receipt-check`. Ein sichtbares Ergebnis ohne
vollstaendige Receipt-Kette bleibt `not-run` oder `failed-evidence`; ein
Harnessfehler wird nicht als Produktfehler umgedeutet.

## Fuenf anwendbare Hardwarefaelle und ein Profil-N/A

1. `power-cycle-autoboot-restage-repl`: L65SYS einlegen, physisch aus- und
   einschalten, bis zum sichtbaren `lisp65>` keinerlei Hostkommando; danach
   Screen sowie Bank-5-/Attic-Readback erfassen. Der Attic-Bereich bleibt
   byteidentisch. Bank 5 wird dagegen beim Produktstart vertragsgemaess an
   den im versiegelten Stdlib-Manifest aufgelisteten Literal-Slots
   materialisiert: Das Oracle verlangt deshalb Byteidentitaet ausserhalb
   exakt dieser Slots und fuer den gesamten angehaengten Boot-Overlay, nicht
   die unmoegliche Identitaet des bereits committed Preloads.
2. `warm-reset-valid-catalog-fastpath`: Regionen vor dem Reset lesen,
   physischen Reset ausloesen, Regionen und REPL danach erneut belegen.
3. `disk-swap-resident-composition`: IDE, IDEX und M65D auf L65SYS laden,
   einmal auf ein valides Nicht-Produktmedium beliebigen Namens wechseln und
   dieselbe Komposition samt gebundener Medienidentitaet pruefen.
4. `work-media-save-remount-read`: ausschliesslich ein beliebig benanntes,
   valides Nicht-Produkt-1581 als Wegwerfmedium verwenden. Unmittelbar vor
   dem ersten Save mit
   `(poke 214 137 128)` den durch Freezer/Monitor simulierbaren
   Direct-SD-Zustand erzwingen und `$D689` als genau ein Byte `80` sichern.
   Dann Create, Read, Replace, Remount und Read ausfuehren. `m65d-save`,
   `m65d-save-new`, `m65d-remount` und `m65d-status` melden Erfolg dabei als
   den Fixnum-Status `0`, nicht als `t`. Nach der
   Transaktion `$D689` erneut als genau ein Byte sichern; das Receipt fordert
   `00`. Vor-/Nachmedium und Disk-Oracle bleiben wie bisher gebunden. Damit
   prueft der Fall permanent, dass jede Transaktion ihren F011-Kontext selbst
   uebernimmt; ein realer Freezer ist fuer die Regression nicht erforderlich.
5. `mid-write-media-swap-abort`: Die drei Phasen vor Daten-, BAM- und
   Directory-Write werden zuerst automatisiert durch direkte Aenderung des
   D68B/D68C--D68F-Mount-Tokens injiziert. Jede Injektion muss terminalen
   Status 12 liefern; Status 8 und der IDE-Remount-Retry sind nach
   Transaktionsbeginn verboten. Ein unabhaengiger Vollabbild-Parser prueft
   Quellmedium A und Zielmedium B je Phase, insbesondere null veraenderte
   Sektoren auf B. Danach charakterisieren drei getrennte adversariale
   Injektionen das Stock-Core-Restfenster fuer Daten-, BAM- und
   Directory-Write: Je Fall bleibt A fuer den isolierten Befehl
   byteidentisch, genau hoechstens ein Sektor auf B darf sich aendern, Status
   12 folgt und danach kein weiterer Write. Diese drei Ergebnisse heissen
   ausdruecklich nicht Sicherheits-PASS.

   Erst danach folgt genau eine manuelle Bestaetigung mit dem realen Freezer
   waehrend eines langen COW-Writes. Der zeitgestreckte Trigger muss den
   produktiven Rueckschreibpfad spiegeln: Der Rueckgabewert des nativen
   Klassifizierers wird mit `%m65d-set` veroeffentlicht; ein direkter Aufruf
   des Klassifizierers ist als Harness-Abkuerzung unzulaessig. Die innere
   Triggersequenz lautet daher normativ
   `(%m65d-set (%disk-write-sector (%m65d-run-authorized name src nil)) nil)`.
   Erwartet werden
   terminale Rueckgabe 12, persistenter `m65d-status` 12, kein automatischer
   Retry und null weitere Writes nach der Erkennung. Die
   Vollabbilder muessen belegen, dass B gegenueber seiner sauberen Baseline
   null oder einen Sektor geaendert hat und A nur einen gueltigen
   precommit- oder vollstaendig committed Zustand zeigt. Ein Ein-Sektor-Fund
   liegt innerhalb der vom Owner akzeptierten Grenze, ist aber kein
   Sicherheits-PASS. Beide Name+ID-Identitaeten, Mount-Tokens,
   Terminaldiagnose und Vor-/Nachabbilder werden als eigene Rohbelege
   gebunden. Vor einem expliziten neuen Save sind beide Medien zu pruefen.
   Medium B wird vor jeder Wiederverwendung byteidentisch aus dem gesicherten
   `G6B.D81` wiederhergestellt; ein fehlgeschlagenes B bleibt Beweisstueck.
6. `product-medium-physical-write-protect` ist im Profil
   `stock-core-sd-d81` nicht ausfuehrbar: Es gibt kein physisches Medium und
   der Stock-Freezer besitzt keinen virtuellen Write-Protect-Schalter. Das
   Profil-Receipt bindet diese Einstufung an das exakte Ship-Manifest und
   weist zugleich aus, dass kein Produktcode auf ein eigenes F011-WP-Signal
   verzweigt. JTAG-Pokes, Core-Aenderungen und synthetische PASS-Receipts sind
   verboten. Bei spaeterem Einsatz einer echten Diskette wird der Fall wieder
   anwendbar und muss den Raw-Write samt Vollabbildvergleich ausfuehren.

Die Reihenfolge darf fuer sichere Medienhandhabung angepasst werden; Power-
und Resetfaelle brauchen jedoch eigene Cycle-IDs. Fix-forward ist nur fuer
Harness-/Verifierfehler bei unveraenderten Produkt-SHAs erlaubt.

## R7-Vorbedingungen

`config/r7-release-prerequisites.json` schliesst die zwei nicht
G6-blockierenden Manifestkorrekturen: Der oeffentliche Manifestentwurf benutzt
fuenf Rollennamen statt hostlokaler absoluter Pfade, und `packed_on` stammt
aus dem gebundenen Source-Commit-Zeitstempel. Zwei byteidentische Packlaeufe
wurden unter lokalen Datumsstaenden 2026-07-14 und 2026-07-16 erzeugt. Der
Receipt bindet Produktdelta null; beide Voraussetzungen sind damit fuer R7
geschlossen, ohne die in G6 bewiesenen Produktbytes zu bewegen.

## G6-Abschluss und Siegel

Ein gruenes Aggregat im Build-Baum ist noch keine Promotion. Vor R7 wird es
als eigener Archivtyp `lisp65-r6-g6-hardware-archive-v1` versiegelt. Das
Archiv bettet das vollstaendige R6-Ship, alle fuenf anwendbaren Fall-Receipts
samt Rohbelegen, den profilgebundenen N/A-Beleg, den statischen Preflight und
die zu ihrer erneuten Pruefung benoetigten Verifier ein. Zwei unter
unterschiedlichem `PYTHONHASHSEED` und unterschiedlicher Zeitzone erzeugte
Packlaeufe muessen byteidentisch sein. Die Offline-Pruefung laeuft gegen das
Archiv allein; Manipulationen an Produktbyte, Fall-Receipt und Top-Receipt
muessen abgelehnt werden.

Das Siegel bleibt vom Typ `hardware-acceptance`. Sein enger Claim lautet:
G3 ist nur als Emulatorvorfilter bestanden, G5 ist fuer das gebundene
Produktset bestanden, G6 ist fuer 5/5 im aktiven Profil anwendbare
Hardwarefaelle bestanden, physischer Produktmedien-Schreibschutz bleibt
sichtbar N/A, und Release bleibt bis R7 gesperrt.

## R7-Abschluss

Der private Release `v1.0.0` konsumiert dieses registrierte Siegel ohne
Produktneubau. Das Bundle `releases/lisp65-1.0.0.tar.gz`/`5bea5ca9...`
enthaelt alle 13 Produktartefakte byteidentisch zum versiegelten R6-Ship,
das G6-Siegel selbst, ein pfadbereinigtes Manifest und einen
Standardbibliothek-only-Verifier. Der annotierte Tag zeigt auf `5897294` und
nennt G6 5/5 anwendbar bestanden sowie den profilgebundenen WP-N/A-Fall.
