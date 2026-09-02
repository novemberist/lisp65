# Produktstrategie-Notizen nach M5 (2026-07-11)

Status: historische, strukturierte Gesprächszusammenfassung (Alex + Claude),
kein Vertrag und kein aktueller Release-Status. Der Ursprungstext beschreibt
den Stand nach M0–M5, als G3/G6 noch offen waren; spätere, datierte
Owner-Entscheidungen wurden als Nachträge erhalten. Seit 2026-07-15 ist
`v1.0.0` mit Dialect V2 veröffentlicht. Für die weitere Entwicklung gilt der
[kanonische 1.1-Plan](development-plan-1.1.md).

Historische Bezugsdokumente:
[Dialekt-Redesign](../archive/pre-1.0/designs/lisp65-dialect-redesign-2026-07-10.md),
[IDE-Diät](../archive/pre-1.0/designs/lisp65-ide-diet-2026-07-10.md),
[Kapazitätsanalyse](../archive/pre-1.0/reference/capacity-scaling-analysis-2026-07-11.md)
und
[MEGA65-Hardwareanalyse](../archive/pre-1.0/reference/mega65-hardware-deepdive-2026-07-10.md).

## 1. Auslieferung und Endnutzer-Erlebnis

- Die Overlay-/Preflight-Architektur ist für den Nutzer unsichtbar; Bedienung
  bleibt: einschalten → REPL → `(edit)`. Kaltstart-Kette: D81/SD → Autoboot →
  PRG → nativer Loader staged Bank-5-Preload + Attic-Katalog (Attic ist
  reset-fest, nicht power-fest).
- **Eine D81 als Zielformat** ist realistisch (Suite < 200 KB von 800 KB).
  Empfehlung: Produkt-Disk logisch read-only, Nutzerarbeit auf Work-D81.
- **G6-Abnahmefall:** stromlos → SD rein → ohne PC bis REPL + Load/Save-
  Roundtrip. Das ist zugleich der AP7-README-Pfad.
- Das `REM INJECT`-Prompt beim Deploy ist der Eingabekanal-Verifikations-
  marker des gehärteten Harness (Tipp-Beweis vor echten Kommandos), kein
  Fehler; ggf. Flag für Schnell-Iterationen.

## 2. Positionierung

- Nische: **einzige ernsthafte interaktive Hochsprache auf dem Gerät** —
  konkurriert weder mit Cross-C/ASM (andere Kategorie) noch mit BASIC 65 als
  ROM-Standard. Einzigartig: Lisp-2 + Makros + selbstgehosteter Compiler +
  transaktionale Persistenz + Emacs-Bedienung, hardwareverifiziert.
- BASIC-Parität ist erreichbar und asymmetrisch: BASICs „Magie“ = Register-
  APIs + DMA + ein IRQ-Tick (der Tick-Hook ist die eine echte Lücke, schaltet
  MOVSPR/PLAY/SOUND gemeinsam frei). BASIC kann umgekehrt nie Makros/GC/
  Compiler nachrüsten. Bewusst nicht einholen: Floats, IEC, REL-Dateien.
- Performance (gemessen ~1100 Zyklen/VM-Op): Rechenschleifen 30–100× langsamer
  als C/ASM, Anwendungsebene ~10–20×, grobkörnige DMA-/Primitive-Arbeit
  ≈ C-Geschwindigkeit; gegen BASIC mindestens gleichauf. Hebelreserve:
  symfn-Cache, Superinstruktionen, Ein-Engine (~2–3×). Für die Nische kein
  Engpass; Hot-Path-Promotion ist der Ausweg für Einzelfälle.
- „Mehr als ein Spielzeug“: belegt durch Persistenzvertrag/Oracle, ASan-festen
  Reader, Provenienz-Ships. Sozial bewiesen erst durch Release + erste fremde
  Nutzung.

## 3. PC-freie Entwicklung als Zielbild

- **Anwendungen PC-frei: realistisch, Kern existiert** (Edit → lcc-Compile →
  FASL → Load → COW-Save, HW-abgenommen). Fehlende Bausteine sind Lisp-Libs
  über vorhandenen Primitiven: Ship-Builder (BAM/Directory-Logik ist bereits
  Lisp), `d81attach` (HYPPO-Kontextfrage klären), on-device Runtime-Export.
- **System bleibt Cross-Dev by design** (C-Kern, Blob, Katalog = „Firmware“);
  Beweisinfrastruktur bleibt PC-seitig.

## 4. Budget-Grenzen: System vs. Nutzer

- Bank-0-/Overlay-/Slot-Budgets sind reine Systemanatomie — Nutzercode
  (Bytecode in EXT) konkurriert nie darum.
- Geteilte Session-Ressourcen (Symbole, Namepool, Directory, Heap, 8-KB-Slots)
  erben Nutzer als **vertragliche, fail-closed Grenzen mit Klartext und
  Budget-Preflight** — Kategorie „38911 BYTES FREE“, kein Minenfeld.
  Voraussetzung für komfortable App-Größen: Symbolökonomie + Cap-Rebalance
  (siehe capacity-scaling-analysis).

## 5. RAM-Bank-Bilanz für Nutzerprogramme

- Bank 0 System; Banken 4/5 sind *Nutzer-Infrastruktur* (Heap/Arena bzw.
  Nutzercode-Region); Banken 2/3 ROM-tabu; **Bank 1 (64 KB) von uns unberührt
  → als Nutzer-/Grafikbank deklarieren** (session-transient, Reset-Caveat);
  30 KB Colour-RAM und ~8 MB Attic praktisch frei.
- Knappe Währung ist VIC-Sichtbarkeit, nicht RAM. Standardmuster für
  `m65-gfx`: Assets kalt im Attic → DMA-Staging nach Bank 1 → VIC zeigt
  Bank 1; `EXGLYPH` als zusätzliches Ventil. (BASICs Bitplanes belegen
  dieselben Banken 4/5 — unsere Lage ist nicht schlechter.)

## 6. Editor als eigenständiges Produkt (Post-G6)

- Der IDE-Editor als Standalone-Texteditor = **ideales erstes Runtime-Export-
  Demo (AP8 Punkt 2)**: gleiche Codebasis, anderes Profil/Verpackung; besetzt
  eine unbesetzte Nische (Vollbild-Editor mit sicherem Speichern) und wirkt
  als Community-Türöffner für die Suite.
- Grenzen ehrlich ausweisen: 8-KB-Slots, nur SEQ/Text (keine tokenisierten
  BASIC-PRGs), PETSCII/ASCII-Politik vorher entscheiden. **Strikt nach G6.**

## 7. Historische nächste Schritte (Reihenfolge)

Diese Liste dokumentiert die Planung vom 2026-07-11. G3/G6 und der
1.0-Releaseprozess sind inzwischen abgeschlossen; sie ist keine offene
Arbeitsliste.

1. G3/G6-Releaseprozess; untracked Analyse-Dokumente committen oder bewusst
   ausschließen (sauberer Tree).
2. G6-Abnahme inkl. Kaltstart-User-Flow (§1).
3. Post-G6 / AP8: Dialekt-Umsetzung (Symbolökonomie zuerst) → Cap-Rebalance →
   Tick-Hook + Paritätslibs → Editor-Export → Ship-Builder/`d81attach` →
   `lisp65c`-Bundle (§14).

## 14. Compiler-Topologie: lcc überall, Python als Schiedsrichter

- `lcc` ist nicht gerätegebunden: Er läuft heute schon auf dem PC — im
  Python-P0-VM-Modell der Differentialsuiten. **Kein C-Rewrite des
  Cross-Compilers**: Ein handgeschriebener C-Compiler wäre eine vierte
  Emitter-Wahrheitsquelle (F7-Lektion) ohne Vorteil.
- **`lisp65c`-Bundle als AP8-Baustein:** VM (nativer Host-Build von
  `src/vm.c`) + Stdlib + lcc als CLI (`lisp65c prog.lisp -o prog.l65m`),
  Datei-Shims statt DMA. Erzeugt bit-identische Artefakte zum Gerät
  (dieselbe Compiler-Ausführung), validiert beim Packen gegen die
  Zielprofil-Limits (L65M-Maschinerie). Türöffner für reine
  PC-Entwickler; nutzt dieselben Zutaten wie Runtime-Appliance und
  Editor-Export.
- Rollenbild: Workbench = On-Device-Entwicklung; `lisp65c` = PC-Pfad;
  Python-VM/-Compiler = unabhängiges Differential-Oracle (versioniert
  gepinnt, F9); Golden-Artefakte bleiben Workbench-emittiert (AP8.2)
  mit Re-Emissions-Diff.

## 15a. Distribution als Produktversprechen (Owner-Entscheidung 2026-07-13)

Alex stuft das 1.0-Verteilmodell (Quelle/FASL nur unter Suite-Besitzern,
kein Standalone-Versand) als **nur übergangsweise akzeptabel** ein. Daraus:

- **Ship-Builder wird committetes Produktversprechen**, nicht 1.x-Option:
  `(ship "programm" :entry 'main)` erzeugt auf dem Gerät eine eigenständig
  bootende D81 (Stager + Runtime-Core + Closure-Libs tree-shaken +
  Nutzer-FASL + Autoboot).
- Abhängigkeitsanalyse: braucht weder Export-Interning noch unload noch
  Buffer — Zutaten (Runtime-Export 4/4 HW-bewiesen, requires-Closure,
  M65D-Schreibpfad, Stager) existieren. Fehlend: Packzeit-Closure +
  Tree-Shaking, D81-Boot-Layout-Authoring aus Lisp, Runtime-Core-Promotion
  von internal-proof-only zu redistributierbar (einmalige
  Layout-Zertifizierung), Fehler-Oberfläche ohne Workbench.
- Priorität ~~direkt nach den 1.1-Kapazitätsblöcken~~ — **aktualisiert
  (Owner-Entscheidung 2026-07-15): Ship-Builder wird das 1.2-Leitthema.**
  1.1 gehört der Politur von Sprache und IDE (siehe
  [1.1-Entwicklungsplan](development-plan-1.1.md)); der Ship-Builder profitiert
  davon direkt (Regal-Layout aus Welle 1 = `ship`-Layout, Tree-Shaking
  nutzt den Metadaten-Vertrag aus Welle 2). Das committete
  Produktversprechen bleibt unverändert, weiterhin vor Paritätslibs —
  „Nutzer können veröffentlichen" macht aus der Umgebung ein Ökosystem.
- Lizenz muss Runtime-Redistribution mit Nutzerprogrammen ausdrücklich
  erlauben (Runtime-Exception-Muster) — Bedingung der Lizenzentscheidung.
- 1.0-README benennt den Zustand ehrlich als Übergang.

## 15b. Medien-Ergonomie: Attic-Regal (1.1) und Mehrlaufwerk (1.x)

Kontext: Zwei-Disketten-Modell erzeugt Swap-Zwang bei Lib-Loads. 1.0 löst
das dokumentiert per Ein-Swap-Flow (im Ship-Manifest als
`single_drive_flow` gepinnt: boot → stage → Komposition laden → einmal
auf die Work-Disk wechseln).

**Owner-Entscheidung 2026-07-13 — Medienpolitik-Inversion:** Die
Allowlist (nur `L65WORK,65` beschreibbar) entfällt zugunsten einer
Denylist: beschreibbar ist jedes valide 1581-Medium, das nicht
mehrfaktoriell als System-/Produktdisk erkannt wird (Name `L65SYS` + ID
+ Boot-Signatur, plus Mount-WP). Latch bindet weiterhin
Name+ID+Mount-Generation, jetzt mit beliebiger Identität; alle
COW-/Verify-Garantien unverändert. `L65WORK.D81` bleibt bequeme
Paketbeigabe ohne Namenszwang. Begründung: Disketten-Namenskultur der
Plattform respektieren; Schutzbedarf liegt beim Produktmedium, nicht bei
Nutzermedien. Umsetzung im BUFSEL-Neupinnungszyklus (ein gemeinsamer
R4/R5/G6-Durchlauf).

- **Attic-Bibliotheksregal (1.1-Kandidat, strukturelle Lösung):** Stager
  staged beim Boot zusätzlich die Lib-FASLs ins Attic; `load-lib` liest
  fortan von dort. Null Swaps, reset-persistent, **keine Änderung am
  Medienmodell** — fügt sich in den bestehenden Stager-/L65R-Pfad.
  Einsortierung: nach den Kapazitätsblöcken, natürliche Ergänzung zum
  Ship-Builder (§15a), der dasselbe Layout schreibt.
- **Mehrlaufwerk (1.x, eigener Vertragsblock):** löst *Daten*-Workflows
  (Projekt- + Daten-Disk, Disk-zu-Disk-Kopie), nicht primär die
  Lib-Ergonomie. Preis ist ein echtes Vertragskapitel: Unit-Semantik in
  der gesamten Persistenz-API, Latch/Identität pro Laufwerk, neue
  Fehlerklassen. Eintrittskarte: Verifikation der Drive-Select-Bits
  (`$D080`, bewusst vertagter Known-Open). Hilft nur SD-Image-Nutzern
  (physisch existiert ein Laufwerk).

## 15c. Öffentliches Repo: kuratiertes Modell — Pflichtenheft (2026-07-15)

Owner-Entscheidung: Das öffentliche GitHub-Repo ist ein **kuratierter
Export** des privaten Arbeitsrepos (privat bleiben Beweisketten,
Evidenz-Archive, versiegelte Receipts). Externe Mitarbeit (Issues, PRs)
ist erwünscht und wird wie folgt verarbeitet: PRs werden öffentlich
reviewt, bei Annahme als Patch ins private Repo übernommen (`git am` /
cherry-pick mit `--author`, Urheberschaft bleibt), durchlaufen dort die
Hausregeln (Probe, capacity_delta, Suite, ggf. Hardware-Abnahme) und
erscheinen mit dem nächsten Sync im Snapshot; der PR wird mit Verweis
geschlossen. **PRs werden nie direkt im Snapshot gemergt.**

**Technische Voraussetzungen (Anforderungen an die Kurator-Infrastruktur):**

1. **Extern baubar und testbar:** Snapshot enthält Toolchain-Manifest +
   Fetch-/Verify-Skript (F9, Block 1.1-K) und den öffentlichen Kern der
   Testsuite. Ohne das sind externe PRs blind. F9 ist damit
   Voraussetzung für Mitarbeit, nicht nur Hygiene.
2. **Pfadstabilität des Exports:** Verzeichnisstruktur 1:1 erhalten,
   damit Patches vom Snapshot sauber auf den privaten Baum applizieren.
   Kein Umsortieren/Umbenennen durch den Kurator.
3. **CONTRIBUTING.md + DCO:** Mechanismus ehrlich erklären (keine
   Direkt-Merges; produktberührende Beiträge durchlaufen Kapazitäts-
   und ggf. Hardware-Abnahme — Doku/Libs schnell, Core langsam);
   `Signed-off-by` (DCO) als Herkunftsklärung, entschieden **vor** dem
   ersten angenommenen Fremdbeitrag. Issue-Templates fragen
   Produktversion (Tag/SHA), Hardware vs. Xemu und Repro-Schritte ab
   (erfüllt zugleich S1-Feedback-Kanal).

**Transparenz-Zusagen (machen das Modell ehrlich statt Fassade):**

1. **Deklaration im ersten Absatz** von README/CONTRIBUTING: kuratierter
   Export, Begründung (versiegelte Evidenz nützt öffentlich niemandem),
   Sync-Kadenz.
2. **Sync-Kadenz als Zusage:** Sync zu jedem Release und mindestens
   alle **4 Wochen** (Owner-Entscheidung 2026-07-15). Ein still veraltender
   Spiegel liest sich als totes Projekt — unregelmäßige Syncs sind das
   größte reale Risiko des Modells.
3. **Changelog pro Sync**, übernommene Fremdbeiträge namentlich mit
   PR-Rückverweis; bei intern modifizierten Patches ein Satz
   „applied with changes: …".
4. **Öffentliche Grob-Roadmap** (die 1.1-Wellen) und die Gewohnheit,
   Issues früh mit „in Arbeit für Welle X" zu beantworten. Keine
   Behauptung von „community-driven development" — die wahre Aussage
   ist: „Beiträge willkommen; entwickelt wird in einem privaten Baum
   mit Hardware-Abnahme", formuliert als Qualitätsversprechen.

**Bekannte Ausbaustufe:** Wächst die Zahl aktiver Contributor über eine
Handvoll, ist die Inversion (öffentliches Arbeitsrepo, privat nur
versiegelte Evidenz) die transparente Endform. Die Kurator-
Infrastruktur darf nichts bauen, was diese Tür zusperrt.

## 15. Selektiver Funktions-Import (zweistufig)

Machbarkeit: L65M kennt bereits per-Funktion Code-Spannen, einen
Graph- und einen Patches-Durchgang (Validator-Phasen 10/11) — selektiver
Import = transitive Hülle über den Call-Graphen + Index-Relokation.

- **Stufe 1 (zuerst, billig): Tree-Shaking zur Packzeit** im
  Ship-Builder/`lisp65c` — Dead-Function-Elimination gegen die
  App-Entry-Points beim Paketieren. Kein Runtime-Umbau; trifft
  Runtime-Export und C64-Ziel („nutzt 3 von 40 → zahlt 3“).
- **Stufe 2 (später): `(import lib (fn …))` in der Session** — gehört in
  den vertagten Block „Directory-only/L65M-v2 + `unload`“, nicht davor.
  Auflagen: Manifest-Flag *import-safe* (keine Top-Level-Seiteneffekte
  außer Definitionen; sonst fail-closed nur Ganzladung),
  Load-Zeit-Relokation der Directory-Indizes, LIFO-Fragmentierung
  beachten. Lohnt erst, wenn reale Libs kleine Ausschnitte großer
  Pakete nahelegen (plausibel bei gfx/sound, nicht bei lists) —
  Tiering + Export-only-Interning holen den Großteil vorher.

## 8. Toolchain-Bilanz: llvm-mos

Netto klar richtig: ELF-Werkzeuge tragen die gesamte Gate-Kultur
(llvm-nm/size-Reports, Custom-Linkerskript mit OVERLAY/ASSERTs, LTO/ICF,
Symbol-Override für HW-Math). Bezahlte Narbenliste (alle eingezäunt):
LTO-Reordering der DMA-Trigger (`"memory"`-Clobber), Shift-Codegen-Bug,
Markstack-GC-Freeze, Z-Register vs. Q-Ops, KERNAL-Scroll-Crash,
Default-Linkerskript. Regel: an den Rändern (Inline-Asm, MMIO, Layout)
misstrauen und auf HW beweisen. Offene Schwächen: Toolchain-Pinning/CI
(F9) und Nischenabhängigkeit — abgefedert durch Bytecode-Anteil.

## 9. GC aus Nutzersicht

Vollautomatisch, allokationsgetrieben, fail-closed bei OOM; `(gc)`/`(room)`
sind Instrumente, keine Pflichten. Nutzer-Hygiene nur im Echtzeitpfad
(nicht im Frame-/Tick-Loop consen, Buffer wiederverwenden, optional `(gc)`
vor kritischen Passagen). Fixpoint-Sweep verschiebt nichts → DMA-Ziele
stabil, Buffer-Pinning trivial; Audio-DMA läuft durch GC-Pausen weiter.

## 10. C64 als Runtime-Export-Ziel (Folgeprojekt)

Kein neues Projekt: Dialekt v1, Bytecode-ABI, lcc, Oracles sind
plattformneutral; nötig ist eine neue Plattformschicht + Mini-Profil.
Zuschnitt: **Entwickeln auf MEGA65/Host, ausliefern auf C64** — nur
VM+GC+Loader+Programm (AP7-Export), kein Editor (1 MHz!). REU als
empfohlenes EXT-Tiering (≈ unser ext_dma-Muster), sonst Load-only-
Miniprofil. HW-Math-Override fällt per Profil automatisch auf compiler-rt
zurück; `provides`/`requires` wird zum Capability-Check. Billige
Vorbereitung jetzt: Primitive in den Fixtures als core-portabel vs.
plattformgebunden taggen.

## 11. BASIC-Interop

Vier Richtungen, klar bewertet: (1) Datei-Interop über SEQ/D81 = trivial,
der Standardweg; (2) BASIC→Lisp per SYS-ABI auf den Export-Entrypoints =
machbarer Post-AP8-Baustein; (3) Lisp→BASIC-ROM-Aufrufe (z. B. Float-
Paket) = **abraten** (Zeropage-/MAP-/IRQ-Konflikte; KERNAL-Lektion);
(4) sauberer `(quit)`-Ausstieg nach BASIC = billige Goodwill-Politur.

## 12. Performance-Positionierung

Erwartung Bytecode vs. BASIC 65: Faktor 2–5 (BASIC re-parst Ausdrücke,
scannt Variablen linear, rechnet alles in 5-Byte-Floats; wir haben
Compile-Zeit-Auflösung + HW-Math; unser Gift ist symfn-DMA pro CALL) —
**ungemessen**: Benchmark-Paar (Sieb/Fib/String-Sort, beide Sprachen,
HW, µs-Timer) als kleines Release-Artefakt einplanen. Einordnung: bei
50 Hz haben beide Sprachen nur ~400–800 Ops/Statements pro Frame — auf
dieser Maschine orchestriert die Sprache, die Hardware arbeitet. Der
echte Unterschied ist der Fluchtweg: Hot-Path-Promotion (eine Funktion
→ C-Prim) statt BASICs Assembler-Klippe. Geschwindigkeit = Beweispunkt,
nicht Verkaufsargument.

## 13. Anwendungsklassen (Tracker, Paint u. ä.)

These: Diese Apps waren auf 8-Bit komplexitäts-, nicht CPU-limitiert —
Lisp ist dort strukturell im Vorteil. Faustregel: Innenschleifen →
Hardware/Prims (DMA-Linien ~40 MPix/s, Transparenz-Token = HW-Pinsel,
SID/Audio-DMA), Zustands-/Werkzeuglogik → Lisp, große Daten → Buffer +
Attic + transaktionale Disk (8 MB Attic als Undo-Puffer!). **Tracker
zuerst** (braucht genau Tick-Hook + Audio-Lib + Buffer; Live-Coding an
laufender Musik als unkopierbares Feature; Tick muss allokationsfrei
sein). Paint danach (Flood-Fill als Prim-Kandidat; braucht
Ketten-Persistenz für Dateien > 8 KB — bekannte M65D-Erweiterung).
