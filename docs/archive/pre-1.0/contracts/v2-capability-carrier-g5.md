# Interne CP5-G5-Abnahme

Status: Die interne Hardwarematrix ist bestanden. Dieser Nachweis erteilt keine
globale Profilumschaltung und keine Auslieferungsfreigabe.

Das reproduzierbare Evidenzarchiv wurde auf Source-Commit
`e9232a2739898e913272c241efd560446c48a8b3` versiegelt und
bindet die Produktidentitaet
`67400c05a96f18dbfb69941c8a7a1ff8bd6fb9c2ba1baa665c6a5f3a86fb6ed8`.
Alle zehn Workbench- und alle vier Runtime-Core-Faelle sind verifiziert. Die
vier Runtime-Phasen liefen unter vier verschiedenen bestaetigten physischen
Power-Cycles. Das Top-Level-Receipt
`build/cp5-g5-v2-bound/receipts/g5.json` hat darin die SHA
`b1bf091a82d1b7070bebdd288e27bc5254f3c20763ebf7b2da9eb03ead7d33fd`
und liefert:

```text
v2-capability-carrier-internal-g5-receipt: PASS cases=14 physical_power_cycles=4 g5=passed
```

## Evidenzidentitaet und Preflight

Ein G5-Kandidat ist die kanonische Menge der sechs Produktartefakt-SHAs:
Runtime-Core-PRG und -Preload sowie Workbench-PRG, -Preload, Attic-Katalog und
D81. Reine Harness-, Verifier-, Receipt- oder Paketierungsaenderungen bewegen
diese Identitaet nicht. Bereits bestandene, SHA-gebundene Fall-Receipts bleiben
dann gueltig; nur fehlende Faelle laufen nach. Ein Delta an mindestens einer
Produkt-SHA erzwingt dagegen den vollstaendigen Neulauf.

Vor jedem physischen Fall ist der statische 14-Faelle-Preflight Pflicht. Er
revalidiert Kandidat und beide Hardwarepakete, loest alle Targets auf und
bindet Target- und Recipe-SHAs ohne Seiteneffekt. Der aktuelle Preflight
`build/cp5-g5-v2-bound/preflight/preflight-e8a452c128fad0d5.json` hat die SHA
`4b6cef6a39336fb2aa9d27a673d17d72403cbcf5c238bea2efaf691acbd86656`
und meldet `PASS cases=14`, `side_effects=none`. Der bereits bestandene erste
Workbench-Fall bleibt gemaess der freigegebenen Doktrin an seinen frueheren,
ebenfalls gruenen Preflight gebunden.

Spaete Harnessfehler werden fix-forward diagnostiziert. Ein optionaler
Ein-Zeremonie-Lauf ist erst nach gruenem Preflight zulaessig, fuer diese
Abnahme aber nicht erforderlich.

## Verifizierte Matrix

Die Workbench-Domain umfasst drei UX- und sieben Persistenzfaelle. Bewiesen
sind insbesondere IDE+IDEX+M65D mit Nutzermarge, `some => 3`, `every => t`,
M-x/eval-buffer, Create/Read/Replace/Remount/Reset sowie die historischen
Disk-Oracles bis `907`. Das Reset-Oracle ist exakt
`(("(defun ap6-persisted () 612)") 612 ("(defun ap6-b () 613)") 613)`.

Der Runtime Core besteht aus `clean => 42` sowie terminalen Truncation-,
Build-ID- und Bitflip-Fehlern mit den Detailcodes `1`, `2` und `3`. Die
Cycle-IDs sind:

- `g5-67400c05-runtime-clean-01`
- `g5-67400c05-runtime-truncated-01`
- `g5-67400c05-runtime-build-id-01`
- `g5-67400c05-runtime-bitflip-01`

Die drei im Archiv erneut verifizierten Domain-Receipts und ihre SHAs sind:

- Workbench UX: `ed72409b859db2c41f80023a15fc853f04eb392f0720639a54f8b7a0d551daae`
- Workbench Persistenz: `1a7578a6f62d2980f85ce793438ec2e7ba813849973a6d47e7cad13d107c5cca`
- Runtime Core: `d5fd74f6b69ec3941009cdb0456b2d087863bbd2dfe5d56b6b333b11a06bae83`

## Zwei getrennte Autoritaeten

`config/v2-capability-carrier-g5-candidate.json` beschreibt ausschliesslich
die Hardwareabnahme des internen Profils `dialect-v2-capability-carrier`.
Kandidat und Hardwarepakete bleiben `shippable=false`, tragen
`release_authorization=none` und aktivieren weder `dialect-v2` noch den
normalen Workbench- oder Runtime-Export-Ship-Pfad.

Die endgueltige Profilumschaltung bleibt allein beim Vertrag
`config/dialect-v2-g5-matrix.json` mit der ID `dialect-v2-product-switch`.
Dessen Receipt setzt alle migrierten Familien, alle geschlossenen
Semantikentscheidungen und die globale Hardwarematrix voraus. Die interne
Matrix darf dafuer nicht als Ersatzbeleg wiederverwendet werden.

Der CP5-Hauptvertrag bleibt von der globalen Autoritaet getrennt, ist nun aber
transaktional geschlossen: Das versionierte Archiv, sein eigener Offline-
Verifier, der Checkpoint-5-Emitter und das Host-5-Gate binden dieselben 14
Faelle und vier Power-Cycles. Der Carrier-Block ist damit einmalig in das
weiterhin nicht shippbare Stagingprofil promotet. Das ist die Voraussetzung
fuer R2, nicht die globale Dialektumschaltung.

## Host-Bedienung

```sh
make v2-capability-carrier-internal-g5-check
make v2-cp5-g5-archive-check
make v2-capability-carrier-check-host-5
python3 tools/host-lisp/v2_capability_carrier_g5.py selftest
python3 tools/host-lisp/v2_capability_carrier_g5.py \
  verify-receipt \
  --receipt build/cp5-g5-v2-bound/receipts/g5.json
```

Der interne Packer erzeugt absichtlich kein normales Ship-Paket. Ein
vollstaendiger Kandidaten-Neubau, Preflight und Hardwarelauf bleiben fuer jede
geaenderte Produkt-SHA verpflichtend.
