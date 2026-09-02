# Profilgebundenes Overlay-Paket

Status: generisches AP4.3-Format; Runtime-Core bleibt Prototyp. AP4 ist im
Workbench-Produkt implementiert, layout-frozen, sauber als Ship-v5 promotet
und live in G5 abgenommen. Der historische
AP4.6-/Ship-v3-Vertrag ist historisch live abgenommen. Die unten beschriebene
Ship-v5-Erweiterung ist in Clean-Tree-G2, G4 und Live-G5 verifiziert.

`tools/host-lisp/overlay_package.py` erzeugt ein Verzeichnis mit exakt zwei
Dateien:

- `overlay.bin`: rohe, separat zu ladende Overlay-Sektion;
- `manifest.json`: deterministisches Manifest im Schema
  `lisp65-profile-overlay-v1`.

Das Manifest bindet das Overlay an ein konkretes Produktprofil. Es enthaelt
Bank-0-VMA (`base`, `end`), Raw-Groesse, die Adresse und den Symbolnamen des
aufrufbaren Entry, LMA/Lademodus und Stagingmodus. `lifetime.class` und
`lifetime.reclaim_point` machen explizit, ab wann der Bereich wiederverwendet
werden darf. Die ABI-Bindung besteht aus einer versionierten Contract-ID, dem
SHA-256 des Contract-Artefakts und dem SHA-256 des residenten PRG. Dessen
Load-Adresse und File-Ende werden ebenfalls gepinnt.

Der Packer akzeptiert Basis und Entry getrennt. Der Entry muss innerhalb des
Raw-Overlay-Spans liegen, aber nicht am Sektionsanfang. `end` muss exakt
`base + size` entsprechen. Fuer das Resident-PRG gilt
`Dateigroesse = file_end - load_base + 2`, einschliesslich PRG-Load-Header.

Beispiel fuer den Runtime-Core-Prototyp:

```sh
python3 tools/host-lisp/overlay_package.py pack \
  --overlay build/products/runtime-core/overlay-prototype/lisp65-runtime-core-overlay.bin \
  --out-dir build/products/runtime-core/overlay-prototype/package \
  --profile runtime-core \
  --base 0xb800 --end 0xc448 \
  --entry 0xbba8 --entry-symbol vm_load_embedded_stdlib \
  --load-base 0xb800 --load-mode fixed-vma-raw \
  --staging-mode separate-image \
  --lifetime boot-only --reclaim-point before-deep-stack \
  --resident build/products/runtime-core/overlay-prototype/lisp65-runtime-core-resident.prg \
  --resident-load-base 0x2001 --resident-file-end 0x6e13 \
  --abi-id runtime-core-overlay-abi-v1 \
  --abi-contract build/products/runtime-core/overlay-prototype/resolved-profile.txt
```

Die strikte Offline-Pruefung verlangt dieselben erwarteten Bindungen mit
`--expect-*`; dadurch reicht ein intern konsistentes, aber fuer ein anderes
Profil oder Resident-Binary gebautes Paket nicht aus. `make
overlay-package-selftest` prueft deterministische Ausgabe und positive sowie
manipulierte Pakete. Eine Aufnahme in `check-source` oder `check-product`
erfolgt erst nach Architektur- und Deployment-Abnahme.

## Workbench-Transportvertrag

Die Workbench besitzt zwei gebundene Preloads. Der Bank-5-Preload beginnt bei
`$050000`: `tools/host-lisp/workbench_overlay_stage.py` richtet den Stage-
Beginn nach dem Stdlib-Praefix auf 256 B aus und schreibt einen 18-B-Descriptor
(`L65O`, Version, Headergroesse, 32-Bit-Build-ID, VMA, Entry, Laenge und
CRC16-CCITT-FALSE), direkt gefolgt vom einmaligen Boot-Payload. Der aktuelle
Abschluss-Pin enthaelt 34325 B Stdlib, ein 1409-B-Boot-Overlay fuer `eval_init`
und insgesamt 35987 B Combined Preload.

Die wiederverwendbaren und profilgebundenen Slices liegen als eigener Katalog
ab `$08000000` im Attic RAM. L65R-v1 und sein historischer Format-Tag `3`
bleiben unveraendert; das physische Storage-Binding ist davon getrennt. Der
Linker legt alle Images in dasselbe `OVERLAY`: gemeinsame
Bank-0-Ausfuehrungs-VMA, getrennte LMAs. Dadurch ist die Lifetime-Ueberlagerung
explizit und jeder Katalogeintrag kann unabhaengig transportiert, auf Laenge,
Build-ID und CRC geprueft und danach in dasselbe Fenster kopiert werden. Das
Slot-Gate pinnt `38/64`: zwei Transport-Verifier, 21 L65M-Preflight-Phasen,
sieben Commit-Phasen, drei LCC-Installer, die Boot-Fastpath-Slots 33-35 und
Slot 36 fuer L65E. Slot 37 ist der fail-closed Installer fuer die residente
Insel. Ein dynamisch hinter Slot 37 erzeugter Seed-LMA dient nur dem Build der
Insel und ist weder Katalogeintrag noch Ship-Artefakt.

Der Split-Boot trennt Verantwortungen: Das Bank-5-Boot-Overlay fuehrt
`eval_init` aus, Slots 33-35 erledigen Verify, Literal-Patches sowie
Entries+Freeze der profilgebundenen Stdlib. Die Buildpipeline beweist deren
Semantik und bindet Gate-Ergebnis, Contract-SHA, Build-ID, Laenge und CRC.
Auf dem Geraet laeuft genau eine Whole-image-CRC vor der ersten Bank-5-
Bootmutation. Laufzeitmedien erhalten diesen Vertrauensvorschuss nicht:
Disk-Libs durchlaufen den vollen 21-Phasen-Preflight vor der Commit-Phase.

Aktueller AP4-Abschlusslink: gemeinsame Guard-Produkt-Overlaybasis `$c344`,
1851 B Boot-Gap und 1811 B Post-Boot-Reserve. Das harte 1024-B-Minimum und das
1536-B-Ziel sind gruen. Die residente Insel `$1800..$1fff` enthaelt 1108 B
unveraenderliche Koordinatoren und einen 260-B-Rootstack-Annex; 680 B bleiben
eingefroren. Der HW-Math-Ersatz hat bereits 519 B beigetragen und ist kein
verbleibender Reservehebel. Die 385 B Primitivnamen liegen bereits in
`.lisp65_boot.names`; ihre Verlagerung spart resident 0 B. Eine neue
Clean-Tree-Promotion und Live-G5 sind fuer Commit `5ce25a2` abgeschlossen. Der
fruehere Ship-v3-Live-Lauf mit
452 B Softstack-Marge und 202 B Page-1-Rest bleibt ein historischer Nachweis
fuer das damalige Paket.

## L65E-Fehlertexte

L65E-v1 ist eine erweiterbare, sparse Tabelle mit Anzahl und gepackten
Code-zu-Textspan-Referenzen. Identische Referenzen teilen genau einen
Payload-Text. Der stabile Vertrag umfasst 59 Codes. L65E-Klartext ist fuer 42
im Workbench nutzbare Reader-, Persistenz-, Compile-/Load-, OOM-, Stack- und
Runtimepfade enthalten; 15 nicht gebaute Profilpfade sind begruendet
`not-built`, Codes 46 und 47 werden resident geliefert. Die Codes 49 bis 59
binden neun getrennte FASL-Fehler und die LCC-Fehler fuer einen zu grossen
do-Rumpf sowie eine ungueltige Parameterliste dauerhaft an einen physisch
geteilten Text `compile failed`; ihre stabilen Codes tragen die genaue Diagnose
und duerfen nie wiederverwendet werden. Der 33 Zeichen lange Sentinel
`%lcc-error-invalid-parameter-list` ist ein ausschliesslich intern durch
`vm_init` vorinternierter Name. Dafuer akzeptiert der C-Internierungspfad bis
zu 33 Zeichen; der oeffentliche Reader-Vertrag bleibt unveraendert bei maximal
31 Zeichen. Ein
ELF-Drift-Gate vergleicht alle emittierten Codes mit dieser Klassifikation.
Der Renderer alloziert nicht. Ist Transport oder Slice nicht verfuegbar,
bleibt `Ehh` resident: `hh` ist der zweistellige stabile Hex-Code und mit
Build-/Hardwarekontext zu melden. Codes 46 und 47 besitzen zusaetzlich
residente, allokationsfreie Deployment-Hinweise.

## L65M-Validator und Commit

Phase 05 verwendet einen 4096-Bucket-/512-B-Filter und liest Namen in
120-B-Bloecken. Hashgleichheit ist nur eine Vorpruefung; das Verdikt folgt
immer aus dem exakten Vergleich. 56 Bulkread-Fixtures decken Kollisionen,
ueberspannte Segmentgrenzen und exakte Enden ab. Das Vorher-/Nachher-Gate
vergleicht 90090 Verdikte ohne Abweichung. Der P05-Slice belegt exakt
1792/1792 B.

Der Preflight verwendet Repeat-Batches mit CRC an beiden Batchgrenzen. Fuer die
Workbench-IDE-Lib sind 21 Slice-Loads und 126 CRC-Laeufe gepinnt; P05 liegt bei
1016/1500 Scratch-DMAs, der Gesamt-Preflight bei 13968/15000. Der Commit ist
phase-major und benoetigt sieben Loads sowie 42 CRC-Laeufe statt historisch
5145/30870. Seine permanenten Budgets sind 11620/15000 Quellreads,
31250/40000 Preflight-Symbol-DMAs und 222818/250000 Commit-Namepool-DMAs. Die
Workbench-Lib erreicht Materializer-Tiefe 1; die Vertragsgrenze 9 bleibt im
Scalar-Worstcase mit 486/512 B im gepinnten Framebudget.

## Ship-v5-Projektion

Das Produktpaket besitzt exakt zehn Dateien: die acht bisherigen Nutzartefakte,
die Runtime-Overlay-Bank und `manifest.json`. `manifest.json` im Format
`lisp65-workbench-ship-v5` bindet Resident-PRG, Bank-5-Combined-Preload und
Attic-Runtime-Katalog an denselben Profil-/ABI-Vertrag. Der Offline-Verifier
rekonstruiert Stdlib-Praefix, Nullpadding, Descriptor, Payload/CRC,
Stage-Grenze, Build-ID und alle 38 Slotzuweisungen.

Das Attic-Preload-Record pinnt `attic-ram`, 28-Bit-Adresse, Laenge,
Whole-image-CRC16, SHA-256, Build-ID, `reset-stable-power-volatile` und
`redeploy-required`. Ship-v3 und Ship-v4 bleiben read-only verifizierbar;
Producer und Finalizer erzeugen ausschliesslich Ship-v5.

Das zusaetzliche `error_texts`-Binding pinnt Slot 36, Profil, stabile
Codeanzahl sowie aktive, bewusst ausgelassene und residente Codes als disjunkte
vollstaendige Partition, dazu Tabellenoffset/-laenge,
CRC16, SHA-256, Contract-SHA und Build-ID. Die `stdlib_trust`-Kette bindet das
semantische Buildgate und die Laufzeit-CRC an dasselbe ausgelieferte Artefakt.
Der aus Commit `4cff6b9` promotete Ship-v5 ist ein historischer
Offline-Nachweis. Der aktuelle AP4-Abschlussstand wurde aus Commit `5ce25a2`
promotet; sein Manifest hat SHA-256
`67c5943259ed2bd3d849a33c6f7909bc16962c1c88271baf32dd36a1058085dd`.
Der zweistufige G5-Readback, Reset/Remount, Insel-Readback und echte
`load-lib`-Preflight sind gruen. Das immutable Manifest bleibt dabei korrekt
`g2-verified-candidate`; G5 ist externer Abnahmenachweis.
