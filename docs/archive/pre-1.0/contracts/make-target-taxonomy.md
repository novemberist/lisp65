# Make Target Taxonomy

Stand: 2026-07-11. Dieses Dokument klassifiziert die relevanten Makefile-Targets
als Produkt, Diagnose, Referenz, Runtime-Export-Vorarbeit oder historisch. Ziel
ist, dass `make check` nicht versehentlich alte Profilvarianten als aktuelle
Produktgates behandelt.

## Produkt

| Target | Rolle |
| --- | --- |
| `workbench-product` / `workbench-candidate` | Kanonischer Guard-Resident plus gebundener Combined Preload. |
| `workbench-product-footprint-report` / `workbench-candidate-footprint-report` | Kanonisches Guard-/Overlay-Footprint-Gate. |
| `bank0-lifetime-report` | ICF-deduplizierter, policybasierter Bank-0-Lifetime- und Drift-Report des flachen Referenzbuilds; Bestandteil von G2. |
| `bank0-island-inventory-report` | Namentliches Inventar der residenten Insel und ihres Rootstack-Annex; Bestandteil von G2. |
| `workbench-gate` | Alias fuer das kumulative Produktgate G2 (`check-product`). |
| `workbench-symfn-dynamic-report` | Workbench-Host-Trace fuer `SYMFN_EXT`-CALL/TAILCALL-Exposure. |
| `l65m-verdict-equivalence-gate` | Vorher-/Nachher-Verdiktdiff fuer den L65M-Validator, einschliesslich Bulkread-/Kollisionsfaellen. |
| `l65m-bulkread-fixture-check` | Generator-/Driftcheck der segment- und blockgrenzenbezogenen Bulkread-Fixtures. |
| `workbench-l65m-transport-ops-report` | G2-Budget fuer Preflight-Slice-Loads, CRCs und Scratch-DMAs. |
| `workbench-l65m-commit-ops-report` | G2-Budget fuer phase-major Commit, Quellreads, Symbol-/Namepool-DMAs und Rekursionstiefe. |
| `workbench-persistence-gate` | Kompatibilitaetsalias fuer G2 plus G4. |
| `workbench-ship-d81` | D81 mit ladbarer IDE-Lib und vorallokierten Compile-Zielslots. |
| `workbench-d81-bam-sanity` | Read-only BAM-/Directory-Konsistenzcheck fuer die Workbench-D81. |
| `mvp-ship-artifacts` / `mvp-ship-wip` | Dirty-tree-toleranter, manifestierter `unverified-candidate` unter `build/ship-candidate/`. |
| `workbench-ship-artifacts-check` | Nicht-strikte Offline-Pruefung des lokalen Kandidaten; Bestandteil von G2. |
| `workbench-reproducibility-check` | Zwei isolierte Guard-Builds; bytegenauer Vergleich aller zehn Paketdateien. |
| `mvp-ship` | Clean-Tree-Preflight, G2, Quellen-Recheck, Promotion nach `build/ship/` und strikte Verifikation. Ergebnis bleibt `g2-verified-candidate`. |
| `verify-ship` | Strikte Offline-Pruefung eines bereits promoteten Pakets aus Manifest und Artefakten. |
| `release` / `ship-check` / `ship-release` | Fail-closed reserviert; solange G3-G5-Evidenz und ein freigegebener Releasevertrag fehlen, wird kein aktuelles Release erzeugt. |

Das Produktprofil ist ausschliesslich in `config/workbench.mk` definiert; seine
Generatorausgaben liegen unter `build/bytecode/profiles/workbench/`. Der
Root-Makefile behaelt `.DEFAULT_GOAL := all` und delegiert Toolchain, Produkt
und Gates an `mk/toolchain.mk`, `mk/workbench.mk` und `mk/gates.mk`.

## Standard-CI/Gates

Die Gate-Namen beschreiben eine kumulative, serialisierte Kette:

| Gate | Target | Inhalt |
| --- | --- | --- |
| G0 | `check-source` | Syntax, statische Vertraege, P0-Generatoren, Safety-Checks sowie Ship-, Insel- und Bank-0-Lifetime-Selftests. |
| G1 | `check-host` | G0 plus Host-/Compiler-/VM-Oracles, native Smokes, Sanitizer, Runtime-Core-Boot-Smoke und Differentialtests. |
| G2 | `check-product` | G1 plus Guard-Workbench, Overlay-Paket/Kontrollfluss/Footprint, Bank-0-/Insel- und L65M-Verdikt-/Ops-Budgets, Runtime-Core-Prototyp/Audit, IDE-Lib, D81-Differenz-/Konsistenzchecks und Ship-v5-Candidate-Verifikation. |
| G3 | `check-emulator` | Derzeit explizit nicht verfuegbar und mit Fehlerstatus beendet; kein belastbarer Workbench-xmega65-Produktfluss. |
| G4 | `check-hardware-dry-run` | Nur Deploy-Kommandos und Artefaktpfade, ohne Live-Hardware-Aktion. |
| G5 | `check-hardware` | Verified-only MEGA65-Abnahmematrix aus `build/ship/`, einschliesslich der destruktiven Wegwerf-D81-Fluesse. |

`make check` ist ein Alias fuer G2. G3-G5 werden nicht implizit ausgefuehrt.
`make doctor` prueft standardmaessig read-only die G2-Voraussetzungen.
`DOCTOR_GATE=G0|G1|G2|G4|G5` und `DOCTOR_FORMAT=text|json` waehlen Vertrag und
Ausgabe. Der G5-Doctor prueft lokale Tools, fuehrt aber keine Live-Aktion aus;
echter Hardwarezugang bleibt `deferred`, der Gesamtstatus ist deshalb
`ready-with-deferred`.
`ci-check-source` und `ci-check-host` sind die providerneutralen aeusseren
Einstiege fuer G0 bzw. das kumulative G1. Beide verweigern staged, unstaged und
untracked Quellen vor dem Lauf, fuehren exakt `check-source` bzw. `check-host`
aus und verlangen danach erneut einen sauberen Tree. Ignorierte Buildausgaben
sind zulaessig. Es gibt keinen Dirty-Override. `ci-selftest` prueft diesen
Vertrag in temporaeren Git-Repositories und ist Bestandteil von G0; die echten
`ci-check-*`-Targets sind wegen Clean-Tree-Pruefung und Rekursion nicht selbst
Teil von G0-G2.

Exitcodes des CI-Einstiegs: `0` Erfolg, `1` rotes Make-Gate, `2` dirty vor dem
Lauf, `3` dirty nach dem Lauf, `4` Infrastrukturfehler, `5` roter Selftest und
`64` ungueltiger Aufruf. Eine Provider-YAML und die llvm-mos-Bereitstellung
sind noch nicht gepinnt; Provider-Jobs sollen spaeter nur diese Einstiege
aufrufen.

G4 umfasst die benannten `hw-*-dry-run`-Pfade fuer den lokalen Ship-v5-
Kandidaten, UX, BAM-Lesen sowie M2-M7-Schreibpfade. G5 beginnt mit
`verify-ship`, setzt fuer alle korrespondierenden Live-Targets
`MVP_VM_SHIP_DIR=build/ship` und baut dort niemals einen Kandidaten. Ein
Dry-Run darf weder als Emulator- noch als Hardwarebeweis zitiert werden.

## Diagnose

Diese Targets sind nuetzlich, aber nicht als Produktversprechen zu lesen:

- `bank0-reclaim-report`
- `screen-edma-scroll-footprint-delta`
- `mvp-vm-stdlib-einsuite-core-edma-scroll-footprint-report`
- `hw-stress-*`
- `hw-demo-suite`
- `mvp-vm-stdlib-known-open-diagnostic`
- einzelne `xemu-*`-Smokes; sie bilden derzeit kein G3-Produktgate

## Referenz

Diese Targets erhalten historische oder semantische Vergleichspfade:

- `check-reference` als explizite, nicht kumulative Referenzaggregation
- `workbench-reference` und `workbench-reference-footprint-report` fuer den
  frueheren flachen Workbench-Link
- `reference-diagnostics` fuer bekannte rote oder experimentelle
  Vollprofil-, Access-, Color-RAM- und EDMA-Pfade
- `mvp-vm-stdlib-einsuite-full`
- `mvp-vm-stdlib-einsuite-full-footprint-report`
- `mvp-vm-stdlib-einsuite-core`
- `mvp-vm-stdlib-einsuite-core-footprint-report`
- `mvp-vm-stdlib-einsuite-fasl`
- `mvp-vm-stdlib-einsuite-fasl-footprint-report`
- `mvp-vm-stdlib-crfit`
- `mvp-vm-stdlib-crfit-footprint-report`
- `mvp-vm-stdlib-s5-proof`
- `interim-ship`
- `legacy-interim-ship-check` / `legacy-interim-ship-release`; historische
  Aggregate und Bundles ausschliesslich unter `build/legacy-interim-ship/`
  bzw. `build/release/legacy-interim/`

Wichtig: `mvp-vm-stdlib-einsuite-core` enthaelt den alten nativen
Disk-Source-FASL-Pfad und ist nach `compile-string` nicht mehr gruen im
Standard-Footprint. Insbesondere
`mvp-vm-stdlib-einsuite-full-footprint-report` darf nur ueber
`reference-diagnostics`, nicht ueber G0-G2 laufen.

## Runtime-Export-Vorarbeit

Noch kein Produktpin:

- `runtime-core-prototype` baut den expliziten evaluatorfreien Messkern;
- `runtime-core-footprint-report` pinnt aktuell mindestens 8 KiB Bank-0- und
  Stack-Reserve;
- `runtime-core-audit` prueft Entry-Vertrag und verbotene Dev-Symbole;
- `runtime-core-smoke` bootet den nativen Kern im Hostmodell bis Ergebnis 42;
- `runtime-core-prototype-check` aggregiert Build, Footprint, Audit und Smoke;
- `runtime-core-overlay-link-prototype` erzeugt den nicht-default fixed-VMA-
  Linkversuch samt getrenntem Resident-PRG und Rohsektion;
- `runtime-core-overlay-prototype` packt das profilgebundene Overlay;
- `runtime-core-overlay-package-verify` prueft alle Build-/ABI-Bindungen strikt;
- `overlay-package-selftest` prueft den generischen Packer mit Mutationstests;
- `workbench-overlay-bootstrap-smoke` prueft Descriptor, CRC und fail-closed
  Entry-/Fehlerfaelle im Hostmodell;
- `workbench-overlay-prototype` erzeugt die ungesicherte Referenz aus Resident,
  Raw-Overlay und kombiniertem EXT-Preload;
- `workbench-overlay-package-verify` prueft ELF-, Profil- und Paketbindungen;
- `workbench-overlay-control-audit` prueft den einzigen residenten Einstieg,
  die Transaktionsreihenfolge und unerwartete Overlay-Aliase;
- `workbench-overlay-footprint-audit` prueft 512 B Boot-Minimum, 1024 B
  Post-Boot-Minimum sowie die getrennten Zielwerte 1024/1536 B; der
  AP4-Abschlusslink ist mit 1851 B Boot-Gap und 1811 B Post-Boot-Reserve gruen;
- `workbench-overlay-reproducibility-check` vergleicht alle Deploy- und
  Bindungsartefakte aus zwei unabhaengigen Builds;
- `workbench-overlay-stack-probe` baut die getrennte AP4.4-Canary-/Wipe-
  Diagnosevariante und fuehrt ihre Host-, Paket-, Kontrollfluss- und
  Footprint-Gates aus;
- `hw-stack-probe-readback-selftest` prueft Decoder und Grenzmutationen;
- `hw-workbench-overlay-stack-readback[-dry-run]` liest Soft-/Page-1-Canaries
  per JTAG oder validiert den ELF-/Kommandvertrag offline;
- `hw-workbench-overlay-stack-smoke[-dry-run]` orchestriert die instrumentierte
  Diagnose aus Combined Preload, D81, Readback sowie REPL-, IDE-, GC- und
  Abort-Recovery;
- `workbench-overlay-stack-guard` baut die exakte Overlayvariante mit
  `LISP65_STACK_GUARD` und Linker-Floor-Schwelle;
- `hw-workbench-overlay-stack-guard-smoke[-dry-run]` fuehrt denselben Runtime-
  Workflow ohne Canary-Instrumentierung aus; der Dry-run ist in G4. Der
  verified-only G5-Einstieg deployt die drei Dateien aus `build/ship/`;
- kuenftiger Runtime-Loader/FASL/L65M-Export nach vollstaendigem Preflight;
- Library-D81-/L65M-Packaging
- `load-lib`-/Disk-Lib-Artefakte

Diese Targets duerfen kleiner sein als die Workbench, ersetzen aber nicht den
interaktiven Workbench-Loop.

## Historisch/Obsolete

Historische C64/GO64-Smokes und Prelude-only-Ship-Pfade sind kein MEGA65-
Produktgate. Sie duerfen nur explizit laufen, z. B. ueber `legacy-c64-check`,
`interim-ship` oder `legacy-interim-ship-check`, und sollen nicht in neue
Produktdoku wandern. Der Legacy-Interim-Pfad ist von `build/ship/` getrennt;
die generischen Release-Einstiege leiten niemals still auf ihn weiter.

Offener Strukturhebel ist die spaetere Auslagerung der breiten Bytecode-Regeln
nach `mk/bytecode.mk`.
