# Warum es keinen *billigen* Dichtegewinn gibt (Cons-Layout)

Stand: 2026-06-28. Erklärt — konzeptionell, nicht nur per Zahl — warum weder
**Compact2** noch ein naiver **4-Byte-Hauptheap** gegenüber **Classic5** (5 Byte/Knoten)
nennenswert Speicher spart, obwohl „5 → 4 (oder 2) Byte" intuitiv ~20–60 % verspricht.
Die Roh-Messungen/Entscheidung stehen in `architecture.md` §3,
`heap-profile-a2-results-2026-06-24.txt` und im Decision-Report
(`make page-experiment-mainheap-classic4-decision-report`); dieses Doc liefert das
*Warum* und das *Was-bedeutet-das*.

## 1. Das 5. Byte ist Metadaten, kein Verschnitt

Ein Classic5-Knoten ist **4 Byte Nutzlast + 1 Byte Tag**, nicht 5 Byte Nutzlast:

| Objekt | Bytes 0–3 (Car/Cdr) | Byte 4 (Flag/Tag) |
| --- | --- | --- |
| Cons | Car-Zeiger (2) + Cdr-Zeiger (2) | Typ = Cons **+ GC-Mark-Bit** |
| Fixnum | 32-Bit-Wert | Typ = Zahl |
| Symbol | Daten/Next | Typ = Symbol (Name ab Offset 5) |

Alle Objektarten teilen sich **einen** Heap und werden **nur** über dieses Tag-Byte
unterschieden; das GC-Mark-Bit lebt ebenfalls dort. Das Byte ist damit
**irreduzible Pro-Knoten-Information**: Lässt man es weg, kann der Mark/Sweep-GC nicht
mehr entscheiden, ob ein Knoten eine Cons ist (beiden Zeigern folgen), eine Zahl
(keinem) oder ein Symbol (dem Namen). Kein Polster zum Wegsparen.

## 2. „4 Byte" naiv ⇒ netto **null** (das Tag-Byte zieht nur um)

Gemessen (`…-classic4-policy-report`), Mainheap-Range 34030 B:

| Variante | Zellen | Δ vs. Classic5 |
| --- | --- | --- |
| Classic5 (aktiv) | 6806 | — |
| 4-Byte, geometrische Obergrenze | 8507 | **+1701 (~25 %)** |
| 4-Byte **+ voller 1-Byte-State-Sidecar** | 6806 | **+0** |
| 4-Byte **+ gepackter Typ-Nibble + 2 Mark-Bits** | 7164 | +358 (~5 %) |

Die geometrischen +25 % sind genau das, was die Intuition sieht. Aber sobald Typ+Mark
*irgendwo* wieder untergebracht werden müssen: Ein voller Sidecar macht 4+1 = 5 Byte →
**+0**. Bit-Stealing in freie Zeiger-Bits bringt magere ~5 % — und kostet Maskier-/
Shift-CPU bei **jedem** Zugriff (1 MHz, kein Cache).

Die vollen +1701 gibt es **nur** mit *cons-only* 4-Byte-Zellen **plus**
**tagged/immediate Fixnums** (Zahlen belegen keine Knoten mehr) **oder** separater
Speicherung für Zahlen/Strings/Systemknoten. Das ist ein **anderes Objektmodell**,
kein kleinerer Knoten.

## 3. Compact2 *verliert* sogar (Fehlentwurf, kein Zufall)

Compact2 schrumpft die Cons gar nicht: 2 Byte Inline + 2 Byte Daten-Sidecar =
**4 Byte effektiv** (wie 4-Byte) — **plus** 1280 B fixe Page-Maschinerie + ~934 B
residenter Indirektions-Code. Realbuild: **6312 vs 6806** Knoten, PRG **+934 B**. Der
Overhead frisst das eingesparte Byte und mehr; über alle Heapgrößen kein Crossover.

## 4. Ehrlichkeits-Nuance: zwei Zahlen, ein Sachverhalt

- Das Host-Cons-Modell (`compact-model.py`) zeigt 4-Byte −2432 B (~20 %) — **optimistisch**:
  flach 4 B/Cons, ohne zu verbuchen, wohin Typ/Mark gehen.
- Der Realbuild-Policy-Report korrigiert auf **+0** (mit Sidecar).

Beides ist wahr; der Unterschied ist *exakt*, ob das Objektmodell umgebaut wurde.
Die N4-Entscheidung `KEEP-CLASSIC5-DEFAULT` heißt daher **nicht** „4-Byte bringt
nichts", sondern „der echte 4-Byte-Hauptheap ist ohne diesen Umbau **nicht baubar**"
(Probe verliert das Inline-Flagbyte, statische Node-Zone nicht repacked, GC-Policy fehlt).

## 5. Verdikt

- **Nicht unmöglich** — die ~25 % Rohgewinn sind real und „warten".
- **Aber nicht geschenkt** — verriegelt hinter einem echten Redesign:
  **immediate Fixnums + segregierte Objektspeicher + GC ohne Pro-Knoten-Mark-Byte**
  (Pointer-Reversal oder Mark-Bitmap). Das ist im Wesentlichen das MicroLISP-Modell
  ([[microlisp-reference]]).
- Beide Abkürzungen liefern darum unter: Compact2 wegen Maschinerie-Overhead, naives
  4-Byte netto ≈ 0, weil das Tag-Byte nur umzieht.

## 6. Was das für uns bedeutet

1. **Classic5 ist die richtige Default-Wahl — endgültig, nicht „vorläufig mangels
   Messung".** Die Dichtefrage ist kein offener Quick-Win mehr; sie ist ein klar
   umrissenes, *großes* Projekt. Damit ist ein lange offener Strang (P0/P3-Dichte)
   ehrlich geschlossen.
2. **Speicherdisziplin verschiebt sich vom Layout zur Nutzung.** Wenn das Cons-Byte
   nicht billig zu holen ist, zählen die anderen Hebel mehr: residenten Kern klein
   halten (Scope-Disziplin, Feature-Gates), ladbare Libs statt Residenz, Bytecode-
   Dichte, REU/Bank-Switching für Daten. Das deckt sich mit dem Roadmap-Risiko
   „Durchhalten + Speicherdisziplin", nur mit korrigiertem Schwerpunkt.
3. **Wenn Dichte später wirklich gebraucht wird, ist der erste Baustein
   `immediate Fixnums`** — kleine Ganzzahlen als getaggte Zeiger, *auch bei
   beibehaltener 5-Byte-Cons*. In zahlenlastigem Code verschwinden ganze Knoten ohne
   Layout-Umbau (Kosten: ein Tag-Bit pro Zeiger + Deref-Anpassung). Pragmatischer,
   isolierter Einstieg ins „Object-Model-Projekt" — und allein schon nützlich.
4. **Reihenfolge bestätigt:** Die Dichte war als „vor der VM entscheiden, solange
   billig" eingeplant. Befund: sie ist *nicht* billig. Also zu Recht **nicht** vor die
   VM-/Sprachkern-Arbeit gezogen — der wertbestimmende Pfad bleibt VM-Flip + P2
   (lexikalisch), nicht der Heap-Umbau.
5. **Kein verlorener Aufwand:** Die Mess-/Report-Maschinerie (Readiness, Blocker-
   Inventar, Policy, Probe, Decision-Gate) ist die belastbare Grundlage, falls das
   Object-Model-Projekt je startet — sie beziffert vorab exakt, was es kostet und bringt.
