# Sanierungs- und Neuausrichtungsplan 2026-07-09

Status: verbindlicher Arbeitsvorschlag auf Basis des
[`Projekt-Reviews`](project-review-2026-07-09.md).

## Umsetzungsstand

| Paket | Stand 2026-07-12 | Nachweis |
| --- | --- | --- |
| AP0 | abgeschlossen | `project-realignment-baseline.json`; voller Baseline-Lauf gruen |
| AP1 | abgeschlossen; Host-, Produkt- und echte MEGA65-Abnahme gruen | `make native-reader-conformance`; G5 Reader-Recovery |
| AP2 | Ship-v5 reproduzierbar, in Clean-Tree-G2 promotet und in Live-G5 gruen | Attic-Binding, v5-Selftest, Promotion, Doppelbuild und externer G5-Receipt gruen |
| AP3.1-AP3.4 | abgeschlossen | `config/workbench.mk`; `mk/*.mk`; `make doctor`; `make check` |
| AP4.1-AP4.3 | umgesetzt; Runtime-Overlay bleibt Prototyp, Workbench-Overlay ist in AP4.6 promotet | Lifetime-/Trailer-/Runtime-Core-/Overlay-Gates und Reports unten |
| AP4.4 | Diagnosebuild, Dry-run und echter Canary-/Wipe-/Runtime-Lauf gruen | `make workbench-overlay-stack-probe`; `make hw-workbench-overlay-stack-smoke` |
| AP4.5 | Linker-Floor-Stack-Guard statisch und auf Hardware gruen | `make workbench-overlay-stack-guard`; `make hw-workbench-overlay-stack-guard-smoke` |
| AP4.6 | Guard-Resident bleibt Produktbasis; AP4 ist mit 38-Slot-Attic-Katalog und residenter Insel implementiert, layout-frozen und live abgenommen | Link-, Insel-, Validator-, Ops- und verified-only G5-Gates gruen |
| AP5.1 | Registry mit sechs Vertraegen; G0/G1 und enger Workbench-Surface-Claim in G2 gruen | `config/semantic-contracts.json`; `make semantic-contracts-g2` |
| AP5.2 | L65M-Preflight/Commit und profilgebundener Boot-Fastpath umgesetzt, algorithmisch gehaertet und live abgenommen | Verdikt-Diff, Bulkread-, Transport-/Commit-Ops- und echtes `load-lib`-Gate |
| AP5.3 | gemeinsame Eval-Surface hostseitig auf vier Engines; Workbench-Route als G2-Build-Binding gepinnt, Live-Verhalten bleibt G5-Gap | 17 Cases/22 Formen plus `workbench-eval-surface-v1` |
| AP5.4 | Omission-Vertraege und Bytecode-Compileradapter abgeschlossen | 20 Profile driftfest; C-Compiler und `lcc` bestehen 23 Goldens plus Rel8-Reject |
| AP6 | abgeschlossen; COW-Create/Replace, Fehlervertrag, Fault-Oracle, D81-Diffs und Reset/Remount auf echter Hardware gruen | `config/persistence-contract.json`; `M65D`; 82 Faultpunkte; zwei Creates plus Reset-Read |
| AP7 | abgeschlossen | Produkt-/Runtime-Schnitt, Runtime-Export-v1 und Dokumentindex gruen |
| AP8.0 | abgeschlossen | Dialekt-v1 und getrennte `mod`-/`remainder`-Semantik gepinnt |
| AP8.1 | abgeschlossen | `every`/`some` mit manifestgebundenem G5-Receipt geschlossen |
| AP8.2 | abgeschlossen | Workbench-Golden/Re-Emission, Ship-v2, G4 und vierphasiger Power-Cycle-G5 gruen |

### Sanierungs-WIP vom 2026-07-11

Der aktuelle Link legt alle transienten Images in ein gemeinsames
Linker-`OVERLAY`: eine Bank-0-VMA, getrennte LMA-Spans im L65R-v1-Katalog. Das
Binaerformat behaelt Tag `3`; physisch liegt das Image reset-stabil und
power-volatil ab `$08000000` im Attic RAM. Das
Budget ist auf `38/64` Slots gepinnt. Slots 0-32 tragen Transport,
21-Phasen-L65M-Preflight, sieben Commit- und drei LCC-Installer-Slices. Der
Split-Boot verwendet das 1409-B-One-shot-Overlay fuer `eval_init` und die
profilgebundenen Slots 33-35 fuer Verify/Patches/Entries+Freeze der Bank-5-
Stdlib. Slot 36 ist die L65E-Slice; Slot 37 installiert die build-gebundene
residente Insel fail-closed. Ihr build-only Seed-LMA wird dynamisch hinter
Slot 37 gelegt und ist kein ausgelieferter Produktslot.

Die Vertrauensgrenze ist zweistufig. Fuer die gemeinsam gebaute Bank-5-Stdlib
bindet Ship Buildgate-Ergebnis, Contract-SHA, Build-ID, Laenge und CRC; auf dem
Geraet laeuft genau eine CRC-Pruefung vor der ersten Bootmutation. Disk-Libs
stammen von Laufzeitmedien und behalten den vollen 21-Phasen-Preflight vor
jeder sichtbaren Mutation. Die Fehleridentitaet ist als stabiler 46-Code-
Vertrag gepinnt: 31 nutzererreichbare Workbench-Codes haben Sparse-L65E-
Klartext, 14 Profil-Ausschluesse sind explizit `not-built`, und Code 46 besitzt
residenten Klartext. Das ELF-Drift-Gate
verlangt fuer jeden emittierten Code eine Klassifikation; `Ehh` bleibt der
allokationsfreie, overlay-unabhaengige Fallback.

Gemessener Abschlusslink: Guard-Produkt-Overlaybasis `$c344`, 1851 B Boot-Gap
und 1811 B Post-Boot-Reserve. Die Insel `$1800..$1fff` enthaelt 1108 B
unveraenderliche Koordinatoren und einen 260-B-Rootstack-Annex; 680 B bleiben
eingefroren. Das harte 1024-B-Minimum und das 1536-B-Ziel sind gruen. HW-Math
hat bereits 519 B beigetragen und ist kein verbleibender Hebel; die 385 B
Primitivnamen liegen bereits im Boot-Overlay und sparen resident 0 B. AP4 ist
implementiert und fuer weitere Layoutaenderungen geschlossen. Commit
`5ce25a2` wurde sauber als Ship-v5 promotet; G4 und die an Manifest-SHA
`67c5943259ed2bd3d849a33c6f7909bc16962c1c88271baf32dd36a1058085dd`
gebundene verified-only Live-G5-Matrix sind gruen. Das Manifest bleibt als
Buildartefakt ehrlich `g2-verified-candidate`; der Hardwarepass ist separat
dokumentiert.

## Ziel

Das Projekt soll von einem knappen, schnell wachsenden Workbench-Prototyp zu
einer robusten und reproduzierbaren Entwicklungsbasis werden. Die Sanierung ist
abgeschlossen, wenn:

1. native Nutzereingabe keine Speicherbeschaedigung ausloesen kann;
2. ein sauberer Checkout reproduzierbar gebaut und getestet werden kann;
3. ein benanntes Produktgate alle automatisierbaren Produktvertraege abdeckt;
4. Ship-Artefakte eindeutig auf Quellen, Profil und Toolchain zurueckfuehrbar
   sind;
5. Bank 0 und EXT-Code wieder belastbare Wachstumsreserve besitzen;
6. Persistenz Fehler und partielle Writes kontrolliert behandelt;
7. erst danach Featureentwicklung wieder freigegeben wird.

Geschaetzter Umfang fuer eine Person: vier bis sechs konzentrierte Wochen. Die
Arbeitspakete sind absichtlich einzeln integrierbar; jede Phase muss gruen sein,
bevor die naechste ihre Ergebnisse als Grundlage verwendet.

## Steuerungsregeln

- **Feature-Freeze:** Bis Gate G6 keine neuen IDE-Kommandos, Sprachfamilien,
  Grafik-/Sound-Libraries oder Produktprofile.
- **Ein Produkt:** Workbench bleibt das einzige interaktive Produktprofil.
- **Keine Cap-Diaet:** Speicherprobleme werden nicht durch weiteres Absenken
  von Sicherheits- oder Session-Caps geloest.
- **Kleine Integrationen:** Ein Arbeitspaket wird in wenige nachvollziehbare
  Commits mit eigenem Gate zerlegt.
- **Messung vor Promotion:** Neue C-Primitive und Hotpath-Aenderungen brauchen
  Footprint- und Laufzeitmessung.
- **Dirty ist kein Release:** WIP darf gebaut werden, aber nicht als offizielles
  Ship-Artefakt gelten.

## Ziel-Gates

| Gate | Bedeutung | Muss gruen sein fuer |
| --- | --- | --- |
| G0 `check-source` | Syntax, statische Vertrage, Generator-Selftests | jeden Commit |
| G1 `check-host` | native Host-Smokes, Sanitizer, Oracles, Differentialtests | jeden Merge |
| G2 `check-product` | Workbench-Build, Produkt-Suites, Budgets, Ship-Validierung | jeden Merge |
| G3 `check-emulator` | automatisierbare xmega65-Produktfluesse; derzeit explizit nicht verfuegbar | Releasekandidat |
| G4 `check-hardware-dry-run` | Deploy-Kommandos und Artefakte | jeden Releasekandidat |
| G5 `check-hardware` | echte MEGA65-Abnahmematrix | Release |
| G6 `release` | G0-G5, sauberer Tree, Provenienzmanifest | veroeffentlichtes Paket |

Die exakten Targetnamen duerfen bei der Umsetzung angepasst werden. Die
Trennung der Verantwortlichkeiten ist verbindlich.

Implementierter AP2-Stand: G1 enthaelt G0, G2 enthaelt G1 und `make check` ist
ein Alias fuer G2. G4 und G5 sind separate Dry-Run- bzw. Live-Hardwareziele und
kein Bestandteil von G2. Ein Gate gilt in diesem Plan erst nach einem
tatsaechlichen erfolgreichen Lauf als gruen; die Existenz des Targets allein
ist kein Ergebnis.

## Arbeitspakete

### AP0 - Integrationsbaseline herstellen

**Prioritaet:** sofort  
**Aufwand:** 0,5 bis 1 Tag  
**Abhaengigkeiten:** keine

Arbeiten:

1. Laufende M7-/IDE-/Save-New-Aenderungen entweder als zusammenhaengenden
   Integrationsslice fertigstellen oder in einem benannten WIP-Worktree parken.
2. Die vier aktuell vom Omitted-Defun-Guard gemeldeten IDE-Funktionen in allen
   betroffenen Suite-Profilen bewusst aufnehmen, entfernen oder explizit als
   nicht resident klassifizieren.
3. Auf sauberem Tree `make check`, `make workbench-gate` und
   `make workbench-persistence-gate` ausfuehren.
4. Rote, flaky und hardware-only Faelle in einer kurzen maschinenlesbaren
   Baseline erfassen; keine neue Prosa-Chronik beginnen.

Abnahme:

- `origin/main` bzw. der Integrationscommit hat einen sauberen Arbeitsbaum.
- `make check` ist gruen oder jeder verbleibende Fehler ist als expliziter
  Known-Open-Case mit Owner und Exit-Kriterium registriert.
- Der Produktbuild erzeugt keine neuen Compiler-Warnings.

### AP1 - Nativen Reader und Rootstack absichern

**Prioritaet:** kritisch  
**Aufwand:** 2 bis 4 Tage  
**Abhaengigkeiten:** AP0

Arbeiten:

1. Einen kompakten, geprueften Reserve-Mechanismus fuer Shadow-Roots einfuehren,
   z. B. `GC_RESERVE(n)` vor Root-Bursts. Der Device-Hotpath darf nicht pro
   `GC_PUSH` ungemessen wachsen.
2. Reader-Tiefe explizit deckeln und vor jedem rekursiven Listen-/Sugar-Abstieg
   pruefen. Ueberlauf muss als Readerfehler zur REPL zurueckkehren.
3. Einen eindeutigen nativen Reader-Fehlervertrag definieren: ungeschlossene
   Liste/String, unerwartetes `)`, fehlerhafter dotted tail, Token zu lang und
   Fixnum ausserhalb des Bereichs.
4. Lange Tokens entweder voll konsumieren und ablehnen oder bis zum
   dokumentierten Symbolmaximum korrekt lesen. Sie duerfen nie in mehrere
   Tokens zerfallen.
5. String-Escapes zwischen Vertrag und Produkt angleichen. Falls Escapes nicht
   MVP-Bestandteil sind, muessen Fixture und Sprachinventar das ehrlich sagen;
   bevorzugt wird die kleine korrekte Implementierung.
6. Einen nativen Reader-Testtreiber bauen, der dieselben
   `mvp-reader-cases.json` wie das Python-Oracle ausfuehrt.
7. Boundary-Cases mit ASan/UBSan testen: tiefe Listen, lange Tokens, lange
   Strings, ungueltige dotted pairs, EOF an jeder Tokenposition.

Abnahme:

- Alle Reader-Fixtures laufen gegen Python- und C-Reader mit gleichem Verdikt.
- 1000-fach verschachtelte Eingabe liefert kontrolliert `reader too deep`, ohne
  Out-of-bounds-Zugriff oder C-Stack-Crash.
- ASan/UBSan melden fuer das native Reader-Korpus keinen Fehler.
- REPL, `load` und `compile-string` erholen sich nach jedem Readerfehler.
- Footprint-Delta ist dokumentiert und das Produktgate bleibt gruen.

### AP2 - Gates und Release-Provenienz korrigieren

**Prioritaet:** hoch  
**Aufwand:** 2 bis 3 Tage  
**Abhaengigkeiten:** AP0; kann parallel zu AP1 vorbereitet werden

Arbeiten:

1. Das monolithische `make check` in kumulative G0-G2-Aggregationen und
   separate G3-G5-Ziele schneiden; `make check` darf als Alias fuer G2
   bestehen bleiben.
2. `workbench-gate` auf alle automatisierbaren Produktvertraege erweitern:
   Workbench-Suite, IDE-Lib, Footprint, Disk-Lib-Budget, native Smokes,
   D81-Konsistenz und Ship-Artefaktpruefung.
3. Dry-Run-Ziele im Namen und in der Ausgabe konsequent von echten
   Emulator-/Hardware-Gates trennen.
4. `mvp-ship` standardmaessig bei dirty Tree oder rotem G2 abbrechen lassen.
   Ein lokaler Override darf nur deutlich als unverifiziertes WIP markieren.
5. Manifest erweitern: voller Commit, dirty-Status, Source-Tree-Hash,
   aufgeloestes Profil, Toolversionen, Gate-Ergebnisse und SHA-256 aller
   ausgelieferten Artefakte.
6. Einen `verify-ship`-Pfad bauen, der ein Paket nur aus dem Manifest und den
   Artefakten validiert.
7. Eine minimale CI fuer G0/G1 auf sauberem Checkout einrichten; G2 folgt,
   sobald die llvm-mos-Installation reproduzierbar ist.

Umgesetzt sind die kumulativen G0-G2-Aggregationen, die getrennten G4-/G5-
Targets, der explizit nicht verfuegbare G3-Platzhalter, die Trennung von
`build/ship-candidate/` und `build/ship/`, Clean-Tree-Preflight plus
Quellen-Recheck, Ship-v3 und strikte Offline-Verifikation. Historische
Vollprofil- und Diagnosepfade sind aus dem Standardgate nach
`check-reference` bzw. `reference-diagnostics` verschoben. `ci-check-source`
und `ci-check-host` stellen einen providerneutralen CI-Einstieg fuer G0/G1
bereit: Sie verlangen vor und nach dem Make-Lauf einen sauberen Checkout;
ignorierte Buildausgaben gelten nicht als Quellenveraenderung. Der isolierte
`ci-selftest` ist Bestandteil von G0, die beiden echten CI-Einstiege nicht.

Fuer das historische Ship-v3-Paket verifiziert wurden das kumulative G0-G2
mit `make check`,
G4 mit `make check-hardware-dry-run` und der Doppelbuild mit
`make workbench-reproducibility-check`; alle neun Ship-Dateien waren in zwei
isolierten Guard-Builds byteidentisch.
Commit `a82d68f9502c5e42267d33e1d5e528b760bb61ff` bestand ausserdem die strikte
Clean-Tree-Promotion und die komplette verified-only G5-Matrix auf echter
MEGA65-Hardware. Nach einem dokumentierten externen Ethernet-Transient im
ersten Aggregate bestand ein zweiter, unveraenderter `make check-hardware`-
Gesamtlauf die komplette Matrix in einem Prozess mit Exitcode 0. G3 meldet
weiterhin explizit `NOT AVAILABLE`.

Noch offen sind die Bindung des CI-Vertrags an einen Provider samt
reproduzierbarer llvm-mos-Bereitstellung und ein echter G3-Produktfluss. AP2
ist lokal einschliesslich Release-Provenienz und Hardwarevertrag abgenommen;
die beiden externen Integrationspunkte bleiben eigene Folgeentscheidungen.

Abnahme:

- `mvp-ship` verweigert einen dirty oder ungeprueften G2-Kandidaten; sein
  Ergebnis bleibt `g2-verified-candidate` und behauptet keine Releasefreigabe.
- Zwei Builds desselben Commits und Profils muessen fuer das aktuelle Ship-v5
  alle zehn Paketdateien byteidentisch erzeugen; variable Buildpfade werden nur im
  Repro-Modus kanonisiert.
- `verify-ship` erkennt jede manipulierte Datei.
- Gate-Namen entsprechen ihrer tatsaechlichen Ausfuehrung.

Historischer Ship-v3-Abnahmestand 2026-07-10: Dirty-Tree-Abbruch, vollstaendiges G2, G4,
Ship-v3-Manipulationsselftest, byteidentischer Neun-Dateien-Doppelbuild,
Clean-Commit-Promotion und verified-only G5 sind bestaetigt. G3 bleibt offen.

### AP3 - Build- und Profilstruktur konsolidieren

**Prioritaet:** hoch  
**Aufwand:** 3 bis 5 Tage  
**Abhaengigkeiten:** AP2-Gates als Sicherheitsnetz

Arbeiten:

1. Das Workbench-Profil als explizite, nicht geerbte Konfiguration definieren,
   z. B. `config/workbench.mk` mit einer einzigen `WORKBENCH_DEFINES`-Liste.
2. Produktflags nicht mehr ueber lange `filter-out`-Ketten aus historischen
   Profilen ableiten.
3. Makefile schrittweise in fachliche Module aufteilen. Der Root-Makefile
   bleibt Einstieg; der erste Slice umfasst `mk/toolchain.mk`,
   `mk/workbench.mk` und `mk/gates.mk`.
4. Generatorausgaben pro Suite/Profil namespacen. Kein Target darf fremde
   `stdlib-p0.*`-Artefakte ueberschreiben.
5. `make -j` fuer G0-G2 unterstuetzen oder mit einer maschinenlesbaren
   Begruendung gezielt serialisieren.
6. Historische Targets inventarisieren. Behalten werden nur Produkt,
   benoetigte Referenz, Diagnose mit aktivem Nutzer oder explizites Archiv.
7. Einen `make doctor`-Preflight fuer llvm-mos, Python, Host-CC, `c1541`,
   xmega65 und MEGA65-Tools einfuehren.
8. Toolchain-Version und Bezugsquelle pinnen; Download/Installation darf
   ausserhalb des Repos bleiben, muss aber reproduzierbar beschrieben sein.

Umsetzungsstand AP3.1-AP3.4: `config/workbench.mk` ist die einzige kanonische,
explizite Definition des Produktprofils; seine Flags werden nicht mehr aus
historischen Profilen gefiltert. Die Workbench-Stdlib wird unter
`build/bytecode/profiles/workbench/` erzeugt und kann die generischen
`stdlib-p0.*`-Artefakte nicht mehr ueberschreiben. Der resultierende Build hat
weiter `prg_bytes=41032`; PRG und externes Blob sind SHA-256-identisch zum
Ausgangsstand vor der Umstellung.

Der Root-Makefile setzt `.DEFAULT_GOAL := all` und bindet
`mk/toolchain.mk`, `mk/workbench.mk` und `mk/gates.mk` ein. `make doctor`
prueft standardmaessig die Voraussetzungen fuer G2; `DOCTOR_GATE` akzeptiert
`G0`, `G1`, `G2`, `G4` oder `G5`, `DOCTOR_FORMAT` `text` oder `json`. Der
Doctor ist read-only: Compiler- und D81-Proben laufen in temporaeren
Verzeichnissen ausserhalb des Worktrees. G5 prueft die lokalen Live-Tools,
kontaktiert aber keine Hardware und meldet den echten Hardwarezugang deshalb
bewusst als `deferred`; der G5-Gesamtstatus lautet `ready-with-deferred`.

Der Ship-v5-Verifier kreuzprueft ausser den Paket-Hashes nun auch Suite, Format,
Groesse und SHA-256 des externen Blobs gegen das innere Stdlib-Manifest. Der
Attic-Preload ist zusaetzlich an 28-Bit-Adresse, Laenge, CRC, SHA, Build-ID und
Reset-/Power-Semantik gebunden. Ein Paket besteht exakt aus zehn Dateien,
einschliesslich `manifest.json` und des Runtime-Overlay-Katalogs;
unerwartete Eintraege werden abgelehnt. Temporaere D81-Baudateien entstehen
standardmaessig ausserhalb des Paketverzeichnisses.

Verbleibende Strukturhebel sind das Namespacing der generischen und
historischen Profile, die Trennung des Legacy-Ship-Pfads von `build/ship/`
und eine spaetere, separat abnehmbare Auslagerung nach `mk/bytecode.mk`.

Abnahme:

- Das aufgeloeste Workbench-Profil ist an genau einer Stelle definiert.
- Parallele G0-G2-Ausfuehrung besitzt keine geteilten Generatorpfade.
- Ein frischer Checkout meldet fehlende Abhaengigkeiten vor dem Build konkret.
- Entfernte historische Targets sind im Decision Log kurz begruendet.

### AP4 - Echte Speicherreserve schaffen

**Prioritaet:** hoch  
**Aufwand:** 5 bis 10 Tage  
**Abhaengigkeiten:** AP1-AP3

Arbeiten:

1. Den bereits geplanten `bank0-lifetime-report` implementieren und native
   Symbole als `runtime-hot`, `runtime-cold`, `boot-only`, `dev-only` und
   `bss-cap` klassifizieren.
2. Boot-/Embed-Materialisierung (`md_lit_node`,
   `vm_load_embedded_stdlib`, Registrierungshelfer) als isolierten
   Reclaim-Spike behandeln.
3. Code-/Heap-Overlap oder Overlay-Reclaim nur mit eigenem Host-, Emulator- und
   Hardwaregate integrieren.
4. Externes Code-/Metadata-Layout ebenfalls nach Lebenszeit untersuchen. Das
   IDE-Codefenster darf nicht dauerhaft mit 130 B Reserve arbeiten.
5. Nach Reclaim `LISP65_STACK_GUARD` im Workbench-Produkt aktivieren.
6. Erst dann Caps neu setzen; die Reserve wird nicht sofort fuer Features
   ausgegeben.

Umsetzungsstand AP4.1: `make bank0-lifetime-report` erzeugt deterministische
JSON-/Textreports, dedupliziert ICF-Aliase physisch und klassifiziert alle
grossen Workbench-Allokationen ueber eine versionierte Policy. Selftest und
Policy-Drift laufen in G0/G2. Der damalige AP4.1-Pin verfehlte noch die strukturellen
AP4-Mindestwerte; 2206 B sind als theoretisch boot-only identifiziert, aber
ausdruecklich noch nicht als Bank-0-Reclaim verbucht.

Umsetzungsstand AP4.2a: Der Runtime-Disk-Lib-Loader prueft Code plus Trailer
zunaechst mit einer nicht persistierenden Allokator-Vorschau und committed erst
nach erfolgreicher Registrierung ausschliesslich den Code. Fuer die aktuelle
IDE-Lib bleiben damit statt 51294 B nur 28284 B belegt; 23010 B Trailer werden
wiederverwendbar. G0 prueft die echte Allokatorsemantik und das Budgetmodell,
G2 pinnt Ladepeak und Post-Commit-Reserve separat. Der Workbench-Code kostet
dafuer 84 B Bank 0. Der Nachfolger implementiert den vollstaendigen
21-Phasen-L65M-Preflight vor der ersten Directory-/Symbol-/Heap-Mutation und
einen getrennten siebenphasigen Commit; die Runtime-Core-Promotion bleibt eine
separate Produktentscheidung.

Umsetzungsstand AP4.2b: `config/runtime-core.mk` und `mk/runtime-core.mk`
definieren einen expliziten, evaluatorfreien Messprototyp ohne Vererbung aus
der Workbench. Er bootet `mem`/VM/Registry direkt und startet den manifest-
geprueften 0-Argument-Entry `runtime-main`; der native Host-Smoke liefert 42
und prueft, dass beide Treewalk-Hooks null bleiben. Bei denselben Kern-Caps wie
die Workbench misst der Prototyp 23079 B PRG, Dateiende `$7a26`, 20036 B
Stack-Gap und 15940 B Bank-0-Reserve. Ein `llvm-nm`-Gate verbietet Reader,
REPL, Eval, Treewalk-`apply`, lcc und Compilerpfade. Der Prototyp ist bewusst
noch embedded-only: Disk-Lib-Loader, Runtime-Exportmanifest und Packaging
folgen erst nach dem Zwei-Pass-L65M-Preflight.

Umsetzungsstand AP4.3-Prototyp: Ein profilgebundener Runtime-Core-Linkversuch
trennt 3144 B Boot-Code bei fester VMA `$b800` aus demselben ELF ab. Das
residente PRG sinkt von 23079 auf 19988 B; das rohe Overlay besitzt den echten
Entry `vm_load_embedded_stdlib` bei `$bba8`. Ein deterministischer Packer bindet
VMA/LMA, Entry, Lifetime, Resident-PRG, aufgeloestes Profil und externes
Bytecode-Image per SHA-256; 30 Positiv-/Mutationstests und die strikte
Paketpruefung sind gruen. Der Split bleibt bewusst ausserhalb G0-G2, bis der
Transport entschieden ist. Die Messung zeigt zwei unterschiedliche sinnvolle
Pfade: Runtime Core kann sein Overlay resetfest im flachen PRG behalten
(`prg_file_end` etwa `$81f2`), waehrend die Workbench wegen ihres `$c0c0`-Limits
ein EXT-Staging mit kleinem residentem DMA-Bootstrap benoetigt.

AP4.3a ist fuer den Runtime Core umgesetzt: Das Inline-PRG misst 25075 B,
Dateiende `$81f2`, 3144 B Overlay, 19982 B Boot-Stack und 14936 B Reserve nach
dem 8192-B-Laufzeitbudget. Linker und Audit erzwingen genau einen residenten
Overlay-Aufruf vor `vm_run_dir`.

Historischer AP4.3b-Zwischenstand: Die gesamte einmalige Workbench-Boot-
Transaktion wurde erweitert:
`eval_init`, Primitivregistrierung, Stdlib-Registrierung und `gc_freeze_boot`
liegen hinter einem gemeinsamen Entry. Der strikt gebundene Stage besitzt
18-B-Descriptor, CRC16-CCITT-FALSE, Build-ID und ein kombiniertes 36835-B-
EXT-Image. Host-Smoke, Paket-, Reproduzierbarkeits- und Kontrollflussaudit
sind gruen. Gemessen: 39524 B Resident, 2257 B Overlay, 955 B Boot-Gap und
1764 B Post-Boot-Reserve. Damit sind die harten Minima 512/1024 B und das
Post-Boot-Ziel 1536 B erfuellt; der Boot-Zielwert 1024 B fehlt um 69 B. Der
Prototyp bleibt bis zum Hardware-Watermark und Reclaim-Stress ausserhalb von
Default, G2 und Ship.

AP4.4 besitzt nun eine getrennte, opt-in Diagnosevariante mit Soft-Stack- und
Page-1-Canary sowie verifiziertem Overlay-Wipe. Um die Messung nicht durch den
Scanner selbst zu verfalschen, wertet der JTAG-Readback die Canary-Fenster
extern aus. Der instrumentierte Link bleibt mit 641 B Boot-Gap ueber dem
unveraenderten 512-B-Minimum; 39823 B Resident, 2261 B Overlay und 1453 B
Post-Boot-Reserve erfuellen die harten Gates. Host-Scanner, Readback-Selftest,
Paket-/Kontrollflussaudit und der vollstaendige Hardware-Dry-run sind gruen.
Der echte Geraetelauf misst 452 B Softstack-Marge und 202 B Page-1-Rest;
Overlay-Wipe, IDE-Lib, GC-Stress, Reader-Erholung sowie VM-/Treewalk- und
`funcall`-Bruecken bleiben danach funktionsfaehig. Die nachfolgende AP4.5-
Guard-Abnahme ist ebenfalls gruen.

AP4.5 validiert den Guard als eigene, exakte Overlayvariante. Der Device-
Vergleich verwendet jetzt `__heap_start + 24` statt nur `heap + sizeof heap`
und schuetzt damit den gesamten residenten Floor. Der Link misst 39862 B
Resident, 2245 B Overlay, 631 B Boot-Gap und 1427 B Post-Boot-Reserve. Paket-,
Kontrollfluss- und Footprint-Gates sowie derselbe echte IDE-/VM-Bridge-/GC-/
Abort-Lauf sind gruen.

Historischer Ship-v3-Stand: AP4.6 promotete diese Guard-Variante als einzigen
interaktiven Produktpfad.
`workbench-product`, G2 und Ship-v3 verwenden dasselbe Resident-/Preload-Paar;
der flache Build bleibt explizite Referenz. Ship-v3 bettet die Stage-Bindung in
das weiterhin neun Dateien grosse Paket ein und verifiziert offline
Stdlib-Praefix, Nullpadding, Descriptor, CRC, Payload, ABI und Namepool-Grenze.
Der damalige ABI-gebundene Relink misst 39891 B Resident, 2245 B Overlay, 601 B
Boot-Gap und 1398 B Post-Boot-Reserve; alle harten Minima bleiben gruen.
G4 prueft den lokalen Kandidaten. G5 ist verified-only und verweigert jede
Hardwareaktion, solange kein strikt G2-promotiertes `build/ship/` vorliegt.

AP4-Abschlussstand 2026-07-11: Das Guard-Produkt nutzt `$c344` als gemeinsame
Overlaybasis. Die residente Insel `$1800..$1fff` ist ueber ein namentliches
Inventar auf acht kalte L65M-/Batch-Koordinatoren beschraenkt; zusammen mit dem
Rootstack-Annex sind 1368/2048 B belegt und 680 B eingefroren frei. Boot-Gap
und Post-Boot-Reserve betragen 1851 B und 1811 B. Das AP4-Layout ist damit
implementiert und frozen. Eine weitere Layoutaenderung ist keine Fortsetzung
von AP4, sondern eine neue Scope-Entscheidung. Die verified-only G5-
Hardwarefreigabe fuer Commit `5ce25a2` ist abgeschlossen; AP4 ist geschlossen.

Verbindliche Zielwerte fuer den sanierten Produktpin:

| Budget | Hartes Minimum | Ziel |
| --- | ---: | ---: |
| Reserve ueber gemessenem Stackbedarf | 1024 B | 1536 B |
| PRG-Dateiende bis hartes Limit | 512 B | 1024 B |
| EXT-Codefenster waehrend IDE-Load | 512 B | 1024 B |
| EXT-Codefenster nach IDE-Commit | 16384 B | 22528 B |
| VM-Codebuffer | 8 B | 16 B |
| Directory nach Alignment | 16 Slots | 32 Slots |
| Laufzeitsymbole | 32 Slots | 64 Slots |
| Namepool | 256 B | 512 B |

Aenderungen dieser Grenzwerte brauchen einen expliziten Decision-Log-Eintrag
mit Messung; ein stilles Absenken ist nicht erlaubt.

Abnahme:

- Alle harten Mindestwerte sind maschinell gegatet.
- `LISP65_STACK_GUARD` ist im Produkt aktiv und HW-gruen.
- Reader-, IDE-, Compile-, GC- und Load-Smokes bleiben gruen.
- Mindestens 1024 B Reserve werden nach Integration nicht fuer neue Features
  ausgegeben.

### AP5 - Semantische Wahrheitsquellen zusammenfuehren

**Prioritaet:** mittel bis hoch  
**Aufwand:** 3 bis 5 Tage  
**Abhaengigkeiten:** AP1; AP3 erleichtert die Integration

Stand AP5.1 vom 2026-07-10: `config/semantic-contracts.json` ist der
maschinenlesbare Index fuer normative Vertraege. Der strikte Runner lehnt
unbekannte Felder, Pfad-/Formatdrift, widerspruechliche Required-/Gap-Angaben,
Legacy-Adapter und nicht freigegebene Produktclaims ab. G0 fuehrt das
Python-Reader-Modell sowie Bytecode-VM und -Compiler aus; G1 fuehrt beide
nativen Reader-Profile, ABI-Drift und die native C-VM aus. G2 ist bereits im
Produktgate verdrahtet, meldet ohne Product-Claim aber explizit `SKIP`.
Legacy-LISP64 liegt nur noch in `check-reference`. Direkte Runner-Aufrufe
ersetzen fuer generierte Adapter nicht die Make-Abhaengigkeiten.

Stand AP5.2 vom 2026-07-11: Phase 05 verwendet einen 4096-Bucket-/512-B-
Filter und 120-B-Blockreads; jede Hashgleichheit endet im exakten Vergleich.
56 Bulkread-Fixtures pruefen Kollisionen und Segmentgrenzen. Der
Verdikt-Differenzlauf vergleicht 90090 Szenarien mit 0 Abweichungen, der
MOS-Slice belegt 1792/1792 B. Das Preflight-Ops-Gate pinnt 21 Slice-Loads,
126 CRC-Laeufe, 1016/1500 P05-DMAs und 13968/15000 Gesamt-DMAs.

Der Commit arbeitet phase-major: sieben Slice-Loads und 42 CRC-Laeufe ersetzen
5145/30870 im alten Per-Item-Pfad. Gegatet sind 11620/15000 Quellreads,
31250/40000 Preflight-Symbol-DMAs und 222818/250000 Commit-Namepool-DMAs. Die
Workbench-Lib erreicht Materializer-Tiefe 1; die Vertragsgrenze 9 bleibt im
unguenstigsten Scalar-Pfad mit 486/512 B im Rekursionsframebudget.

Stand AP5.3/AP5.4 vom 2026-07-11: `eval-surface-v1` pinnt 17 gemeinsame
Cases mit 22 Formen gegen Python-P0, nativen C-Treewalk, nativen
C-Compiler/VM und Lisp-`lcc`. Die absichtlich engere Schnittmenge enthaelt
weder globale Wertzellen noch `&rest`, weil die vier Engines dafuer noch
unterschiedliche oeffentliche Routen besitzen; die breiteren bestehenden
C-/Python-Gates behalten diese Abdeckung. Die Registry umfasst jetzt 6
Vertraege, 19 Engines und 20 Adapter. G0 fuehrt 6, G1 13 und G2 einen Adapter
aus. `workbench-eval-surface-v1` erhebt den engen Produktclaim, dass der
ausgelieferte Build die interne Route `TREEWALK_STRIP -> lcc-run -> P0-VM`
bindet. Fixture, Registry und Adapter sind ueber `resolved-profile.txt` in
Ship-v5 gehasht; der finale ELF-Symbolsatz und die P0-Stdlib-Metadaten werden
fail-closed geprueft. Das ist bewusst kein 45GS02-Verhaltensclaim: Die 17
Eval-Cases bleiben fuer den echten Workbench-Pfad bis G5 als Coverage-Gap
sichtbar.

Die Bytecode-Golden-Fixture wird nun auch vom nativen C-Compiler und Lisp-
`lcc` direkt konsumiert. Der neue Adapter fand und schloss einen realen
Defun-Tail-`if`-Drift. Alle 23 positiven Vektoren und der Rel8-Reject stimmen;
sechs Disk-CALLPRIM-Faelle sind fuer die native VM strukturiert und begruendet
als `omitted` klassifiziert, werden aber von beiden Compilern geprueft.
`allow_omitted_*` verwendet `{name, reason}`, verlangt exakt die reale
Differenz aus Quellen und Profil und auditiert 20 final aufgeloeste Suiten in
`check-source`. Aufgeloeste Ausnahmen stehen im Artefaktmanifest.

Arbeiten:

1. Fuer Reader, Eval-Surface, Bytecode-ABI und Disk-Lib-Format je eine normative
   Fixture benennen.
2. Adapter bauen, die dieselben Cases gegen Python-Modell, native C-Komponente,
   Lisp-`lcc` und soweit sinnvoll die echte Produkt-VM ausfuehren.
3. Legacy-LISP64-Oracles deutlich vom lisp65-Produktvertrag trennen.
4. `allow_omitted_*`-Listen begruendungspflichtig machen und unbenutzte Eintraege
   als Fehler behandeln.
5. Native Loader/VM mit fehlerhaften und abgeschnittenen Artefakten fuzz-artig
   pruefen.

Abnahme:

- Jede normative Fixture nennt die Engines, die sie bestehen muessen.
- Kein Host-Oracle behauptet Produktkonformitaet, ohne einen Produktadapter zu
  besitzen.
- ABI- und Reader-Drift fuehren in G1/G2 zu einem klaren Fehler.

### AP6 - Persistenz produktionsfaehig machen

**Prioritaet:** hoch vor Nutzerrelease  
**Aufwand:** 5 bis 8 Tage  
**Abhaengigkeiten:** AP1-AP4

Arbeiten:

1. Entscheiden, ob der einmalige versteckte `tmp`-Rename-Pfad nur MVP-Bruecke
   bleibt oder vollstaendig durch den M7-Allocator ersetzt wird. Die UI darf
   keinen allgemeinen Save-Eindruck erzeugen, wenn nur eine neue Datei moeglich
   ist.
2. Freie Ketten beliebiger benoetigter Laenge allozieren und Directory-Ketten
   ueber den ersten Sektor hinaus behandeln.
3. Fehlervertrag fuer no space, duplicate name, bad name, read/write/verify
   failure und volles Directory definieren.
4. Schreibreihenfolge verbindlich halten: Daten, Verify, BAM, Directory zuletzt.
5. Fuer Fehler vor Directory-Commit eine Rollback-/Leak-Strategie definieren;
   bestehende Dateien duerfen nicht beschaedigt werden.
6. D81-Differenztests fuer Abbruch nach jedem Schreibschritt ergaenzen.
7. Ausschliesslich Wegwerf-D81 auf echter Hardware testen; Reset/Remount/
   Readback gehoert in G5.

Abnahme:

- Mehrere neue Dateien koennen in einer Session angelegt und nach Reset geladen
  werden.
- Tests decken 1-, 2-, N-Sektor-Dateien, volles Medium, volles Directory und
  injizierte Fehler an jedem Commit-Schritt ab.
- Kein Fehlerfall erzeugt einen Directory-Eintrag auf unvollstaendige Daten.
- Hardware-Diff, Reset/Remount und normaler Workbench-`load` sind gruen.

Umsetzungsstand 2026-07-11: abgeschlossen. `M65D` ersetzt den `tmp`-Pfad durch
Create-only und Upsert mit gemeinsamem COW-Kern. Der Host-Oracle deckt 16
Szenarien und 82 Abbruchpunkte ab; die Live-Abnahme erstellt zwei Dateien in
einer Session, ersetzt eine davon, remountet, startet ohne D81-Reupload neu und
liest/evaluiert danach beide persistierten Staende exakt. Directory-Wachstum,
globale Crosslink-Reparatur und Power-Loss-Atomizitaet bleiben ausdruecklich
ausserhalb des AP6-Vertrags.

### AP7 - Produkt-, Runtime- und Dokumentationsschnitt klaeren

**Prioritaet:** mittel  
**Aufwand:** 3 bis 5 Tage  
**Abhaengigkeiten:** AP3-AP6

Stand 2026-07-11: abgeschlossen. Der Audit ist in
`docs/ap7-product-runtime-boundary-audit-2026-07-11.md` dokumentiert.
`config/workbench-product-contract.json` und
`config/runtime-export-contract.json` trennen das interaktive Produkt vom
versiegelten Runtime-Ziel. Runtime Export v1 nutzt das freigegebene resetfeste
Inline-Boot-Overlay und ein exakt sieben Dateien umfassendes, offline
verifizierbares Candidate-Paket; 15132 B Post-Boot-Reserve und byteidentische
Wiederholungsbuilds sind gegatet. Der Dokumentindex klassifiziert alle
getrackten Markdown-Dokumente. Der historische Interim-Release ist namespaced,
generische Release-Targets bleiben ohne G3-G5-Evidenz fail-closed. Das README
nennt genau einen verified-only Workbench-Deploypfad. Sprachredesign-Umsetzung
bleibt AP8 nach M5.

Arbeiten:

1. Workbench-Vertrag auf den stabilen Entwicklungsloop begrenzen: REPL, Editor,
   lcc, Load/Save, Compile/Load-Lib und Fehlererholung.
2. Runtime-Export als separates Zielartefakt definieren, nicht als zweites
   interaktives Produkt: VM/GC, Loader, benoetigte Libraries, Userprogramm und
   Entry Point ohne IDE/lcc.
3. Optionale Libraries konsequent on demand halten; neue Komfortfeatures duerfen
   erst nach Load wieder Sessionbudget verbrauchen.
4. `project-status.md` bleibt einziger aktueller manueller Status. Budgetwerte
   werden aus Reports verlinkt oder generiert, nicht in Strategiedokumenten als
   weiterer "aktueller" Snapshot dupliziert.
5. Historische Audits mit `superseded_by`-Hinweis versehen oder archivieren.
6. README um Voraussetzungen, Build, Teststufen, Ship-Verifikation und erste
   Workbench-Session ergaenzen.

Abnahme:

- Ein neuer Entwickler findet in README genau einen Produktpfad und die
  erforderlichen Werkzeuge.
- Workbench und Runtime-Export haben getrennte, maschinenlesbare Vertraege.
- Keine aktive Dokumentation widerspricht dem aktuellen Produktprofil.

### AP8 - Featureentwicklung kontrolliert wieder oeffnen

**Prioritaet:** zuletzt  
**Aufwand:** fortlaufend  
**Abhaengigkeiten:** G0-G6 und AP0-AP7

Stand 2026-07-12: AP8.0 bis AP8.4 sind abgeschlossen. Dialekt-v1 ist
maschinenlesbar gepinnt; die zwei frueheren Higher-Order-HW-Repros sind mit
einem engen, manifestgebundenen G5-Receipt auf `resolved-g5` gesetzt. AP8.2
hat das nichttriviale Demo durch zwei byteidentische Workbench-Emissionen,
Ship-/Manifest-v2, den reproduzierbaren Sieben-Dateien-Candidate und den
offline gegateten G4 gefuehrt. Der vierphasige Runtime-G5 ist nach je einem
physischen Power-Cycle gruen und unter
`tests/bytecode/runtime/evidence/ap8.2-g5-589844f/` archiviert. Weitere
Sprachmigrationen besitzen nun einen eigenen fail-closed Semantik-/
Migrationsvertrag. AP8.3 friert v1 als Evidenzprofil ein, klassifiziert alle
231 eindeutigen Surface-Namen plus 19 Quellmakros, pinnt die fuenf Familien
samt Budgetprojektion und
trennt die spaetere v2-G5-Promotion vom unveraenderten Politik-SHA. Der
Profilselektor bleibt auf v1; noch keine Produktoberflaeche wurde umgeschaltet.
AP8.4 migriert Prelude/Control als erstes abgeschlossenes Familienpraefix,
bindet `STRICT_ARITY` an v2-CodeObjects und misst die erwarteten Einsparungen
aus realen Inventarartefakten. Die naechste Sprachfamilie ist `lists`.

Erst nach Abschluss der Sanierung wird die Roadmap neu priorisiert. Empfohlene
Reihenfolge:

1. verbleibende Laufzeit-Haenger (`every`/`some`) schliessen;
2. Runtime-Export mit einem realen Demo-/Toolprojekt beweisen;
3. Fehlerdiagnostik und Compile-/Reader-Kontext verbessern;
4. CL-nahe Kernluecken mit hohem Nutzwert schliessen;
5. Grafik, Sound und Sprites als ladbare MEGA65-Libraries entwickeln.

Jedes neue Feature braucht vor Merge:

- Produkt- oder Library-Vertrag;
- Host-/Produktcase;
- Budgetdelta;
- bei Hardwarezugriff ein HW-Gate;
- klare Aussage, ob es resident oder on demand ist.

## Reihenfolge und Meilensteine

### M0 - Stabiler Ausgangspunkt

AP0 abgeschlossen. Sauberer Tree, alle bekannten roten Gates registriert,
keine unklassifizierten WIP-Aenderungen.

### M1 - Sichere Eingabe und verlaessliche Gates

M1 ist erreicht, wenn AP1 und AP2 abgenommen sind: Reader-Speicherfehler sind
beseitigt, native Fixtures und Sanitizer gruen, und der Ship-Prozess verweigert
dirty oder G2-rote Kandidaten.

### M2 - Beherrschbarer Build

M2 ist erreicht, wenn AP3 und AP5 abgeschlossen sind: explizites
Workbench-Profil, getrennte Generatorpfade, reproduzierbarer
Toolchain-Preflight und gemeinsame Fixtures. AP3.1-AP3.4 sowie AP5.1-AP5.4
sind umgesetzt; M2 ist abgeschlossen.

### M3 - Nachhaltiger Produktpin

AP4 ist implementiert und das Layout eingefroren. Der Guard ist aktiv; der
Abschlusslink misst 1851 B Boot-Gap und 1811 B Post-Boot-Reserve und erfuellt
damit auch das 1536-B-Ziel. Der Abschlussstand ist in Clean-Tree-G2 promotet
und in verified-only Live-G5 gruen. M3 und AP4 sind abgeschlossen. Keine
weitere Cap- oder Layout-Diaet.

### M4 - Robuste Persistenz

AP6 abgeschlossen. Allgemeines Save-New mit Fehlerdisziplin, D81-Diffs und
Hardware-Reset/Remount gruen.

### M5 - Klarer Produktschnitt

Abgeschlossen am 2026-07-11. Workbench-Dokumentation und Statusquelle sind
konsolidiert, getrennte Workbench-/Runtime-Exportvertraege sind gegatet und
G0-G6 bilden einen fail-closed Releaseprozess. Das bedeutet keine
Releasefreigabe: G3 ist weiterhin nicht verfuegbar; der Runtime-Export-G5 ist
geschlossen, aber Workbench-Kaltstart/G6 und der allgemeine Releasevertrag
bleiben offen.

## Naechste konkrete Queue

Nach AP0-AP4.6, AP5.1-AP5.4, AP6 und der aktuellen AP2-/G5-Abnahme gilt diese Queue:

1. AP8 nach separater Priorisierung oeffnen; das Sprachredesign bleibt ein
   eigener Semantik-/Migrationsblock nach M5.
2. `C-x C-k`-Latenz beobachten und OOM/Abort/`Ehh` bei aktivem Transport-Latch
   gezielt nachtesten; daraus folgt keine weitere AP4-Layoutarbeit.
3. CI-Provider und llvm-mos-Bereitstellung entscheiden; danach dessen Jobs auf
   `ci-check-source` und `ci-check-host` pinnen.
4. Echten Workbench-xmega65-Produktfluss fuer G3 planen.
5. Generische/historische Bytecode-Profile namespacen, den Legacy-Ship-Pfad
   von `build/ship/` trennen und danach `mk/bytecode.mk` separat auslagern.
6. Runtime Export bleibt ein extern gestagtes Appliance-Ziel; Standalone-Boot
   mit D81/SD-Loader, Recovery und Capabilityvertrag separat planen.

## Fortschrittsformat

`docs/project-status.md` soll waehrend der Sanierung nur diese kompakte Tabelle
pflegen:

```text
Meilenstein: M0..M5
Aktives Arbeitspaket: APx
Branch/Commit:
Gates: G0..G6 = green/red/not-run
Budget: Link auf generierten Report
HW: Datum + Gate + Ergebnis
Blocker:
Naechster Schritt:
```

Ausfuehrliche Messlogs gehoeren in generierte Reports oder datierte Audits,
nicht in den laufenden Status.
