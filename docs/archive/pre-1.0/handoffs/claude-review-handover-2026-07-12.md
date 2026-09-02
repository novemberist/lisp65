# Review-Übergabedossier (Claude, 2026-07-12)

Zweck: Institutionelles Gedächtnis der Architektur-Review-Rolle, serialisiert
zum Modellwechsel. Für jeden künftigen Reviewer (Alex, Nachfolgemodell,
Codex-Selbstprüfung). Ergänzt die fünf Analyse-Dokumente (Hardware-DeepDive,
Dialekt-Redesign, IDE-Diät, Kapazitätsanalyse, Produktstrategie-Notizen).

## 1. Stehende Entscheidungen (nicht neu verhandeln)

- **Release = v2, einmal, richtig.** Kein v1-Ship (Nutzerentscheidung:
  Breaking Changes bei Nutzern > Wartezeit). Release-Definition ist
  gedeckelt: heutiger v2-Sprachvertrag + Workbench-Link + G5-Matrix.
  Alles Weitere (Tick-Hook, Buffer, unload, Prim-Vereinheitlichung) ist 1.1.
- **v1 = eingefrorener Evidenz-Anker**, kein Produkt. AP4-Layout, Insel
  (680 B, korrigiert) und Slots bleiben eingefroren; Reserve über 1536 B
  ist nach G5 reinvestierbar, darunter nur per Architekturentscheidung.
- **Reinvestition erst nach G5-Abnahme.** Das ~1140-B-Polster ist das
  1.1-Budget (Reihenfolge: Tick-Hook+Builder → unload → Prim-Block).
- Nutzerpräferenz dokumentiert: Zeileneditieren unantastbar,
  REPL-History notfalls verhandelbar.

## 2. Gelernte Review-Regeln (teuer bezahlt — durchsetzen!)

1. **Der Link ist die Schätzung.** Quellcode-Korridore nur für reine
   Entfernungen; Umstrukturierungen brauchen Prototyp-Link vor Freigabe.
2. **Attribution ≠ marginale Entfernbarkeit** (ICF/LTO-Faltung). Kandidaten
   nur per Stub-Link-Probe bewerten (Marginal-Sweep-Methode).
3. **Pessimum statt Mittelwert** bei Spannweiten > 50 %.
4. **Reine Entfernungen liefern, zustandsbehaftete Gateways nicht** —
   gefaltete Koordinatoren + neues Protokoll = negative Bilanz.
5. Divergenzen v1/v2 nur mit Vertragsanker im Receipt (kein offenes Tor).
6. Tombstones nie wiederverwenden; nie promotete IDs bleiben reservierbar.
7. Scheiterns-Menü vor jedem riskanten Block benennen; Einmalversuche
   sind einmalig.
8. Jede Auflage als Fixture/Gate formulieren, nicht als Prosa.

## 3. Offene Auflagen auf freigegebenen Blöcken

- **String-Caps-Split (freigegeben):** Fixtures identisch über Code-List-
  Pfad (inkl. Atomizität); Latenz-/GC-Receipt für stringlastige Pfade
  gegen kumulatives Budget; Builder-Neuentwurf als benannter 1.1-Block;
  Überschuss banken.
- **CP5/G5:** Ship-Sperre bis volle Matrix; G5 hat historisch 3× Veto
  eingelegt — Hardware-Fund = begrenzte Diagnose, kein Alarm.
- Fehlercode-Namensräume (M65D 0–9 vs. Compile-Sentinels) sauber halten;
  L65E-Auswahlregel: nutzererreichbar = Text, intern = Ehh.

## 4. Risikoregister (Stand heute)

- **Einzelgerät-Risiko unversichert** (ein MEGA65 trägt alle G5-Evidenz) —
  billigste offene Versicherung: Zweitgerät/Community-Tester.
- Btrfs-Baum eingefroren; Ext4-Klon autoritativ; Bundle-Ritual beibehalten.
- Menschlicher Atem = kritische Ressource; Blockstruktur erlaubt
  verlustfreie Pausen beliebiger Länge.
- Plan-B-Memo obsolet (Szenario A übertroffen), bleibt als Referenz.

## 5. Post-Release-Landkarte (Kurzform, Details in Strategienotizen)

1.1: Tick-Hook (öffnet MOVSPR/PLAY/Tracker), Builder/Buffer-Block,
unload, Prim-Vereinheitlichung. Danach: Symbolökonomie-Reste
(Entsymbolisierung Stdlib, Export-Interning), Cap-Rebalance
(Colour-RAM/Attic), Paritätslibs, Editor-Standalone (Runtime-Export-Demo),
lisp65c-Bundle, C64-Ziel, Tracker als Schaufenster. Ein-Engine: erledigt.
Ergonomie-Retrospektive nach ersten echten Nutzerprogrammen.

## 6. Arbeitsweise mit Codex (bewährt)

Codex liefert messbasiert und ehrlich (korrigiert auch den Reviewer);
Review-Beitrag ist: adversariale Vollständigkeit (Randfälle als Fixtures),
Gedächtnis über Blockgrenzen (dieses Dossier), Schutz der Produktebene
(Nutzerentscheidungen gegen lokale Optimierung verteidigen). Vorlagen nie
pauschal ablehnen — mit Bedingungen härten. Zustimmungspflichtig bleiben:
ABI (IDs/Tombstones), Layout, Scope, Verträge.
