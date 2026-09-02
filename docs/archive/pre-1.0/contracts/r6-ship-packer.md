# R6 Promotionspacker und Zwei-Medien-Ship

Status: Vertrag fuer den Review-Halt vor dem R6-Static-Preflight.

## Beweisgegenstand

Der R6-Packer baut kein Produkt. Er konsumiert ausschliesslich die im
Promotionsregister gebundenen Archive
`r4-product-candidate-41cf793.tar.gz` und
`r5-global-g5-94abc53.tar.gz`. Die 13 Produktartefakte werden byteidentisch
aus dem R5-Archiv in eine neue Ship-Huelle kopiert. G3-Receipt und
15-Faelle-Bootmatrix stammen byteidentisch aus R4. Der lebende Baum ist keine
Produkt- oder Evidenzquelle.

Compiler, Linker und Disk-Builder sind in diesem Schritt unzulaessig. Das
maschinenlesbare Mapping aller 13 Rollen und das Kapazitaets-Delta stehen in
`config/r6-ship-contract.json`. Jede Produkt-SHA und alle fuenf gepinnten
Kapazitaetsdimensionen bleiben unveraendert.

## Paket

`build/r6/ship/` enthaelt:

- `media/lisp65-product.d81`: das versiegelte, schreibgeschuetzte
  `L65SYS,65` mit exakt neun Eintraegen;
- `media/lisp65-work.d81`: das versiegelte, leere `L65WORK,65` als bequeme
  Beigabe; jede valide Nicht-Produkt-1581 funktioniert ohne Umbenennung;
- alle 13 Produktartefakte als explizit gehashte Komponenten;
- die unveraenderten R4-/R5-Archive und ihre G3-/G5-Receipts;
- das volle Manifest, den AP7-Erstsitzungspfad, die Packerquelle und einen
  Standardbibliothek-only-Offline-Verifier.

Der Verifier prueft aus dem Paket allein die exakte Dateimenge und Modi, beide
eingebetteten Archive mit deren eigenen Verifiern, alle 13 Produktbytes gegen
R5, die neun Dateien in `L65SYS` gegen ihre Komponenten, das leere
`L65WORK`, Toolchain- und Packerprovenienz sowie die Claim-Grenze. Drei
Negativproben muessen ein veraendertes Produktbyte, ein veraendertes Manifest
und ein veraendertes R5-Archiv ablehnen.

## Reproduzierbarkeit und Autoritaet

Zwei Paketlaeufe mit unterschiedlichen `PYTHONHASHSEED`- und `TZ`-Werten
muessen in Pfaden, Modi und Bytes identisch sein. Das getrackte
Packer-Receipt bindet den Vergleich, die drei Negativproben und das
Kapazitaets-Delta.

Das Ergebnis ist medienfertig, aber nicht releasefaehig:

- G3: bestanden, nur Emulator-Vorfilter;
- G5: 14/14 fuer Produktset `a2e5fe2d...` bestanden;
- G6: `not-run`, sechs Hardware-Bootfaelle offen;
- Release: nein.

Erst nach Review dieses Packers darf der getrennte 15-Faelle-Preflight das
Ship konsumieren. Weder dieser Vertrag noch der Packer fuehren G6 aus.
