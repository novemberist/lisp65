# Interner Runtime-Core-v2-Proof

Status: hostseitiger, versiegelter Beweis. Kein Release und kein Hardware-G5.

## Zweck und Grenze

Der Runtime Core ist das erste Profil, das den dialect-v2 Capability-/Carrier-
Schnitt physisch tragen kann. Dieser Proof baut deshalb ein echtes
Carrier-Cut-PRG und prueft dessen Runtime-Verhalten, Linkflaeche und
Bank-0-Budget. Er aendert weder das aktive Dialektprofil noch den
Workbench-Releasevertrag. Checkpoint 5 bleibt offen.

Der Kandidat ist absichtlich nicht auslieferbar:

- `shippable=false`, `release_authorization=none` und
  `hardware_g5_claim=none` sind Vertragsfelder und Mutationstest-Gates;
- das aufgeloeste Profil traegt `abi_profile=dialect-v2`, sodass der normale
  Ship-Guard es fail-closed ablehnt;
- Kandidatenformat und Dateiinventar sind vom Runtime-Export-Shipformat
  verschieden;
- kein `release`, `ship-check`, `check-hardware` oder CP5-Target konsumiert
  den Kandidaten.

## Provenienz

Das Runtime-Artefakt wird durch den Python-P0-Generator erzeugt. Der Proof
bindet zusaetzlich das CP4-Differential mit 335 von 335 gleichen Beobachtungen.
Das abgeleitete CP4-Receipt wird bewusst nicht zurueckgebunden, weil der
Hauptvertrag den Proof bindet und sonst ein SHA-Zyklus entstuende. Die
Carrier-Abwesenheit wird direkt am Proof-ELF geprueft. Das ist kein
Workbench-emittiertes Golden und kein
PC-freier Build. Diese beiden Claims bleiben ausdruecklich falsch, bis der
Workbench-v2-Releasepfad sie selbst beweist.

## Host- und Linkbeweis

`config/v2-runtime-core-proof.json` pinnt Suite, ABI-Ledger, Service-Registry,
Generator, Linkerskript und CP4-Evidenz. Das Buildprofil setzt vollstaendig:

- dialect-v2 und `STRICT_ARITY`,
- native Listen-/String-Capabilities,
- produktgebundene geschlossene Runtime-Core-Registry,
- `TREEWALK_STRIP` und `LISP65_V2_CARRIER_CUT`.

Der Host-Smoke bootet das eingebettete v2-Artefakt, ruft `runtime-main` auf und
fordert exakt das Ergebnis 42. Der ELF-Audit verlangt die VM-Aufruf- und
Hardware-Orakelsymbole und verbietet Eval-, Treewalk-Carrier- und Workbench-
Service-Symbole. Zwei unabhaengige Links muessen byteidentische PRGs und ELFs
erzeugen.

## Kapazitaet

Die reale LTO/ICF-Messung ist als Vertrag gepinnt:

| Metrik | Wert |
| --- | ---: |
| PRG | 26514 B |
| resident | 22997 B |
| Boot-Overlay | 3513 B |
| Post-Boot-Reserve | 13866 B |
| harter Mindestwert | 8192 B, PASS |
| Zielwert | 12288 B, um 1578 B uebertroffen |

Der Zielmiss ist sichtbar und `report-only-not-promotion`. Deshalb ist dieses
Artefakt ein interner Proof, aber kein bestehender Runtime-Export-Kandidat.

## Bedienung

```sh
make v2-runtime-core-proof-contract-check
make v2-runtime-core-proof-check
```

Der zweite Target erzeugt unter `build/products/runtime-core-v2-proof/` den
Doppelbuild, Host-Smoke, Footprint, Runtime-/ELF-Audits,
Reproduzierbarkeitsreport und den versiegelten Kandidaten. Der abschliessende
Verifier liest jedes Artefakt erneut, prueft SHA/Laenge, Preload-Build-ID,
PRG-Bindung, v2-Manifest, Registry, Budgets und die normale Ship-Ablehnung.
Sechs Mutationen am realen Kandidaten pruefen zusaetzlich Manifest- und
Metrikfaelschung, PRG-/Preload-Bitflip, Profilfreigabe und Dateiverlust.

Hardwareplanung, Power-Cycle-Receipts, CP5-Abschluss, Familienpromotion und
Workbench-De-Residentierung liegen ausserhalb dieses Blocks.
