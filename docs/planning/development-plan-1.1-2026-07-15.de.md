# Entwicklungsplan 1.1: Politur von Sprache und IDE (2026-07-15)

Status: freigegeben (Alex, 2026-07-15) — inkl. Umpriorisierung
Ship-Builder → 1.2 (Update §15a).
Voraussetzung: v1.0.0 getaggt und gepusht (R7 abgeschlossen). 1.1 startet
erst danach — keine Vermischung mit Release-Restarbeiten.

Schwerpunktsetzung (Owner, 2026-07-15): **Politur der IDE und der Sprache
im Vordergrund**, zusätzlich zu den bereits gepinnten 1.1-Punkten.
Konsequenz für §15a (Ship-Builder „direkt nach den Kapazitätsblöcken"):
siehe Abschnitt 7 — Empfehlung: Ship-Builder wird das 1.2-Leitthema.

---

## 1. Ausgangslage: Kapazität ist die erste Politur

Versiegelter Stand nach R7:

| Budget       | Stand                | Bewertung |
|--------------|----------------------|-----------|
| Bank 0       | 332 B über 1536-Ziel | ausgabefähig nur per Block-Autorisierung |
| EXT          | 16.385 B, Boden 16.384 | **eingefroren — 1 B Marge, kein Debit autorisierbar** |
| Symbole      | 120 frei             | eng für Help-/Completion-Features |
| Namepool     | 2160 B frei          | ausreichend, aber Docstrings/Metadaten drücken hier |
| Directory    | 32 frei              | eng für neue IDE-Libs |

Daraus folgt die Grundarchitektur des Plans: **Erst strukturelle
Entlastung (Welle 1), dann Sprach- und IDE-Politur (Wellen 2–3).**
Jede Politur, die auch nur ein Byte EXT, ein Symbol oder einen
Directory-Slot kostet, ist vor der Entlastung nicht autorisierbar.
Das ist keine Bürokratie, sondern die Lehre aus dem Endspiel: Wir
polieren nicht gegen einen Boden mit 1 B Marge.

## 2. Hausregeln (unverändert aus dem Release-Zug)

1. Probe-first: realer Differenzlink vor jeder Freigabe; der Link ist
   der Kostenvoranschlag.
2. Jedes Block-/Promotionsreceipt trägt ein arithmetisch geprüftes
   `capacity_delta` (Bank, EXT, Symbole, Namepool, Directory).
3. Kapazitätsausgabe nur mit vorab erteilter Autorisierung, pro Block.
4. Jeder Block einzeln integrierbar und verlustfrei pausierbar.
5. Gepinnte Abhängigkeiten aus dem Migrationsvertrag bleiben verbindlich:
   Directory-only/L65M-v2 (✓ erledigt in R2) **vor** Export-Interning;
   First-Class-Buffer **vor** `unload`; Export-Interning **vor** `unload`.
6. Neue `%`-Helfer regulär klassifizieren (Omitted-Guard); Gates tragen
   ihre Limits im Wertstring.

## 3. Hardware-Abnahme-Kadenz: Wellen statt Einzelläufe

Jede Promotion mit geänderten Produkt-SHAs erzwingt laut Resume-Doktrin
einen vollen G6-Hardwarelauf. Für 1.1 wäre ein Lauf pro Block
unverhältnismäßig. Daher:

- Blöcke werden zu **drei Wellen** gebündelt; pro Welle genau eine
  R4/R5/R6-Neupinnung + ein voller G6-Lauf am Ende.
- Innerhalb einer Welle: Host-Gates, Suite, M65D-Fälle, Doppelbau pro
  Block wie gehabt; die Hardware-Abnahme sammelt.
- Eine Welle ist erst „geliefert", wenn ihr G6-Lauf grün ist. Bis dahin
  gilt der letzte versiegelte Stand (1.0.0 bzw. Vorwelle) als Produkt.
- Ein Release-Tag `v1.1.0` erst nach Welle 3; optional `v1.1.0-beta`
  nach Welle 2, falls Community-Tester (S2) früh Futter brauchen.

## 4. Welle 1 — Strukturelle Entlastung (Kapazitätsblöcke)

### Block 1.1-A: Attic-Bibliotheksregal (§15b)

Stager staged beim Boot zusätzlich die Lib-FASLs ins Attic; `load-lib`
liest fortan von dort. Null Swaps, reset-persistent, keine Änderung am
Medienmodell.

- **Politur-Doppelrolle:** (a) Medien-Ergonomie (kein Swap-Zwang mehr),
  (b) *macht Nachladen billig* — Voraussetzung dafür, dass IDE-Politur
  als nachladbare Module (`ide-lisp`, `ide-help`) kommen darf, statt
  gegen den residenten Kern zu drücken.
- Abgrenzung: Kein neues Medienmodell, kein Mehrlaufwerk. Reset-, nicht
  power-persistent (Attic-Vertrag); Kaltstageflow bleibt der Stager.
- Gates: Attic-SHA-Verifikation nach Stage; Fallback auf Diskpfad, wenn
  Attic-Katalog fehlt/invalid (fail-closed auf den 1.0-Flow); G6-Fall
  „Reset zwischen Stage und load-lib".

### Block 1.1-B: Export-only-Interning

Auf dem in R2 abgeschlossenen Directory-only/L65M-v2-Block. Nur
Export-Symbole werden interniert; Lib-interne Namen bleiben anonym.

- Erwartung: Symbol- und Namepool-Rückgewinn (Messung maßgeblich, keine
  Zahl versprochen). Das ist das Budget, aus dem Help/Completion und
  Docstring-Metadaten (Welle 3) bezahlt werden.
- Gates: Paritätslauf geladener Libs v. vorher/nachher; Wasserzeichen-
  Receipt Symbole/Namepool.

### Block 1.1-C: EXT-Entlastung (Pflichtergebnis der Welle)

Kein eigenes Feature, sondern ein **verbindliches Wellenziel**: Nach
Welle 1 muss die EXT-Marge wieder zweistellig (Ziel ≥ 64 B, hart ≥ 16 B)
sein — durch Tier-Auslagerung von Stdlib-Anteilen auf das jetzt billige
Regal (A) und die Interning-Gewinne (B). Erst damit wird der
EXT-Freeze aufgehoben; bis dahin bleibt er in jeder Autorisierung
stehen.

- Offene Klärung (vor Blockstart, Messauftrag an Codex): Welche
  Blob-Anteile sind regal-fähig, was ist der reale EXT-Rückgewinn pro
  Kandidat? Probe-first, Tabelle vor Entscheidung.

### Block 1.1-D: Banner „λ LISP65" (Spec liegt vor)

Bewusst ans Ende von Welle 1: Die Spec veranschlagt ~150–200 B Blob —
**vor Blockstart klären, ob der Blob gegen die EXT-Metrik zählt.** Falls
ja, ist der Banner ohne 1.1-C nicht autorisierbar; falls nein, kann er
vorgezogen werden. Budgetreferenz laut Arbeitsplan: aktueller Bankstand
beim Blockstart. Die Welle bekommt damit ein sichtbares Gesicht — der
erste Boot nach Welle 1 sieht anders aus.

## 5. Welle 2 — Sprachpolitur

### Block 1.1-E: First-Class-Buffer + atomare String-Konstruktoren

Bereits gepinnt (Migrationsvertrag, vor `unload`). Sprachlich der
größte Einzelgewinn: DMA-gerechte Datenfläche als echter Typ statt
Behelfe; die im String-Caps-Split geopferten atomaren Konstruktoren
kommen zurück.

- Gates: GC-Vertrag (Fixpoint-Sweep verschiebt nicht — Buffer-Pinning
  bleibt trivial, das muss so bleiben); OOM-fail-closed; Host-Oracle.

### Block 1.1-F: `unload`

Nach E und B (gepinnte Reihenfolge). Namepool-Wasserzeichen-Rückgabe
gemäß Redesign §6.2 (nur wenn keine spätere Lib darüber liegt — LIFO
ehrlich dokumentieren, nicht verschleiern).

### Block 1.1-G: Sprachpolitur-Paket (klein, messbar, einzeln probiert)

1. **Fehlermeldungs-Politur:** `Ehh`-Codes bleiben der residente
   Vertrag; eine *nachladbare* Fehlertext-Lib (vom Regal) übersetzt
   Codes in Klartext + Ein-Zeilen-Hinweis am REPL. Resident ±0 ist das
   Designziel; alles Erklärende liegt im Regal.
2. **Tick-Hook** (bereits gelistet): Einsortierung nach gemessenen
   Bank-0-Kosten (Probe zuerst).
3. **Listen-Prim-Vereinheitlichung** (bereits gelistet): Der
   Implementierungs-Sonderpfad darf entfallen, die codeobjektgebundene
   STRICT_ARITY-Semantik nicht.
4. **Metadaten-Vertrag** (Fundament für Welle 3): Funktionsmetadaten
   (Name, Arity, `&optional`-Signatur, Macro/Function, optionaler
   Docstring) im Stdlib-/L65M-Manifest, **host-seitig generiert, als
   Regal-Datei ausgeliefert** — resident null Bytes, kein
   Symbol-/Namepool-Druck (deshalb nach B). Docstrings sind
   Manifest-Daten, keine Heap-Objekte.

Explizit **nicht** in der Sprachpolitur: `&key`, CLOS-artiges, Restarts,
`import`-Stufe 2 (bleibt am vertagten Kriterium „reale Libs legen
Ausschnitte nahe"), jede Änderung an STRICT_ARITY oder der
Fehlercode-Semantik. Die Sprache ist bewusst beschnitten; Politur heißt
hier: das Vorhandene angenehmer machen, nicht die Fläche vergrößern.

## 6. Welle 3 — IDE-Politur

Alle neuen Anteile als nachladbare Regal-Module gemäß der modularen
Aufteilung des Extension-Plans (`ide-lisp`, `ide-help`); `ide-core`
bleibt der einzige zwingend geladene Teil. Directory-Slots: pro neuem
Modul einer — bei 32 freien Slots tragfähig, aber im `capacity_delta`
ausweisen.

### Block 1.1-H: `ide-lisp` — Lisp-Gefühl im Editor (Extension-Plan Slice 5)

- Auto-Pair für `(` und `"`.
- Matching-Paren-Highlight (nur Cursorumgebung im Render-Hotpath).
- SEXP-Navigation forward/backward/up/down.
- Syntax-Scanner respektiert Strings/Kommentare (Gate: Tests für
  Strings, Kommentare, Verschachtelung, unbalancierte Formen).
- **Nicht:** Barf/Slurp/Paredit — erst nach stabilem Undo (H2) und nur
  bei realem Bedarf.

### Block 1.1-I: Editier-Sicherheit (Slice 7, Kernanteil)

- Undo zuerst als command-level Deltas oder wenige Buffer-Snapshots mit
  kleinem Cap und klarer OOM-Meldung (Heap-Risiko aus dem
  Extension-Plan ernst nehmen); Redo erst nach stabilem Undo.
- Isearch + goto-line.
- Visuelle Region; Zeilennummern-Toggle.

### Block 1.1-J: `ide-help` — die IDE erklärt die Umgebung (Slice 6)

Setzt den Metadaten-Vertrag aus 1.1-G voraus (harte Abhängigkeit).

- `apropos`, `describe`, Symbol-Completion in der UI.
- Parameteranzeige (Arity/`&optional`) für bekannte Funktionen.
- Command-Help: Keybinding + Kurzbeschreibung.
- Alles on-demand vom Regal; Gate: Host-Metadaten-Oracle.

Reihenfolge innerhalb der Welle: H → I → J (J zuletzt, weil es als
einziges den Metadaten-Vertrag braucht und am ehesten schieben darf,
ohne die Welle zu blockieren).

## 7. Ship-Builder: Empfehlung 1.2-Leitthema

§15a (Owner, 2026-07-13) setzte den Ship-Builder „direkt nach den
1.1-Kapazitätsblöcken, vor Paritätslibs". Die neue Schwerpunktsetzung
(Politur im Vordergrund) kollidiert damit. Empfehlung:

- **1.1 = Kapazität + Politur (Wellen 1–3), Ship-Builder = 1.2-Leitthema.**
- Begründung: Der Ship-Builder *profitiert* von Welle 1 (Regal-Layout
  ist dasselbe, das `ship` schreibt) und von Welle 2 (Tree-Shaking
  gegen den Metadaten-/Graph-Bestand). Ihn nach der Politur zu bauen
  macht ihn billiger und besser, nicht später schlechter.
- Das 1.0-README benennt den Übergangszustand bereits ehrlich; die
  Zusage „committetes Produktversprechen" bleibt unangetastet — nur die
  Versionsnummer, unter der sie eingelöst wird, ist 1.2.
- **Owner-Entscheidung 2026-07-15: bestätigt.** Ship-Builder ist das
  1.2-Leitthema; §15a der Produktstrategie-Notizen ist entsprechend
  aktualisiert. Damit ist dieser Plan (Wellen 1–3) die verbindliche
  1.1-Reihenfolge.

## 8. Nicht in 1.1

- Mehrlaufwerk (1.x, eigener Vertragsblock; Eintrittskarte
  `$D080`-Verifikation steht aus).
- Vollständiges Paredit, Mehrfenster, vollständiges Emacs-Keyset.
- `import`-Stufe 2, C64-Runtime-Ziel, Paritätslibs.
- Jede EXT-Ausgabe vor Erfüllung des Wellenziels 1.1-C.
- Core-Fork jeder Art; Mount-Lock (C2) und virtueller WP-Schalter (C6)
  bleiben Upstream-Vorschläge.

## 9. Offene Klärungen vor Wellenstart (Aufträge an Codex, read-only)

1. Banner-Blob: zählt er gegen die EXT-Metrik? (entscheidet Position
   von 1.1-D).
2. Regal-Fähigkeitstabelle: welche Stdlib-/Blob-Anteile sind
   auslagerbar, realer EXT-Rückgewinn pro Kandidat (Probe).
3. Interning-Rückgewinn: gemessene Symbol-/Namepool-Deltas für die
   geladenen Standard-Libs.
4. Metadaten-Format: Manifest-Erweiterung vs. separates Help-Index-File
   (Empfehlung: separates Regal-File, Manifest nur um SHA-Verweis
   ergänzt — hält L65M stabil).
5. Undo-Kostenmodell: Delta- vs. Snapshot-Messung an realen
   Edit-Sessions.

## 10. Definition of Done (1.1)

- Drei Wellen G6-grün, `v1.1.0` getaggt, Mirror + ls-remote verifiziert.
- EXT-Freeze aufgehoben mit dokumentierter Marge ≥ 64 B (Ziel).
- Kein Symbol-/Namepool-/Directory-Boden verletzt; alle Deltas
  autorisiert und arithmetisch geschlossen.
- README/Docs: Banner, Regal-Flow, `unload`-LIFO-Regel, Help-Kommandos
  dokumentiert; Änderungsliste gegenüber 1.0.0 vollständig.
- Upstream-Register um neue Funde ergänzt (laufende Pflicht).
