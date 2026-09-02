# Directory-only/L65M-v2 – Vertragsvorlage

Status: **zur Implementierung freigegeben**. Die Budgetabweichung ist autorisiert und auf 435 B
neu gepinnt; die kanonische Stack-Guard-Baseline ist geschlossen. Normative
maschinenlesbare Vorlage ist
`config/directory-only-l65m-v2-contract-draft.json`.

Der Host-Probelauf ist abgeschlossen und wartet auf die vereinbarte
Zwischenabnahme. Er erzeugt selbststaendig validierbare v2-Artefakte und ein
SHA-gebundenes Receipt unter
`tests/bytecode/dialect-v2/evidence/directory-only-probe/`.

## Vorbedingung: saubere Produktbaseline

Der frueher rote Default-Stack-Guard war kein Slice-Wachstum durch
System/Runtime: Er baute das generische Vor-v2-Profil und landete bei
`0xc3a6`, 80 B ueber dem Produktlimit. Default- und expliziter v2-Target
adressieren jetzt denselben kanonischen Artefaktsatz.

Die Diagnose hat zugleich eine zweite, unabhaengige Abweichung gefunden: Der
gebundene v2-Link bewegt sich von `0xc22c`/2091 B Reserve auf
`0xc2a4`/1971 B. Die 120 B stammen aus System/Runtime-Produktcode
(`+94 B` residenter Text, `+26 B` residentes Read-only-Material); der
Boot-Overlay waechst zusaetzlich um 81 B. Die bisherige Aussage, 555 B seien
unangetastet, ist deshalb zurueckgezogen. Der einmalige 120-B-Debit ist als
prozedurale Korrektur autorisiert; 435 B sind die neue Bank. Directory-only-
Probelinks verwenden den gebundenen v2-Target und muessen ihr Bank-Delta als
null oder mit vorab gebundener Debit-Autorisierung ausweisen.

Die Abnahme ist geschlossen: Beide Vollbauten liefern exakt dieselben vier
Produkt-SHAs, VMA `$c2a4`, 1971 B Reserve, 435 B Bank und 1751 B Boot-Stack-
Gap. `bank_delta` ist null; die R4-Frist ist damit vorzeitig erfuellt.

## 1. Formatvertrag und Dekodierbarkeit

L65M-v1 bleibt byteweise unveraendert und im v2-Profil ladbar. L65M-v2 nutzt
weiterhin Magic `L65M`, aber Version 2. Ein v1-Loader weist v2 sowie jede
unbekannte Version mit `L65M_ERR_HEADER` ab; alte Bytes erhalten niemals eine
neue Bedeutung.

Ein namenloser v2-Eintrag traegt `name_off = 0xffff`, besitzt weiterhin einen
Directory-Slot und wird durch seinen nullbasierten Entry-Ordinal innerhalb
des Artefakts identifiziert. Er darf kein Macro sein und installiert weder
Symbol noch globale Funktionszelle. Lokale Aufrufe verwenden einen neuen
v2-Literaltyp `entry-ref`; der Commit uebersetzt den Artefaktordinal in das
tatsaechliche BCODE-Directory-Immediate. `OP_CALL` und `OP_TAILCALL` muessen
dafuer Symbol- oder BCODE-Literale akzeptieren. Artefaktuebergreifende lokale
Referenzen bleiben verboten.

Der Sentinel ist dauerhaft ausserhalb des legalen Offsetraums: Jeder echte
`name_off` liegt zwischen `0x0000` und `0xfffe` und zugleich innerhalb der
dekodierten Stringtabelle. Jede spaetere Namepool- oder Colour-RAM-Neuordnung
muss scheitern, bevor ein legaler Name `0xffff` erreichen koennte. Ein v1-
Container mit Sentinel-Eintrag ist `L65M_ERR_ENTRIES`, kein tolerant gelesener
Vorlaeufer. Der v1-Emitter erzeugt ausschliesslich Version 1; Decoder waehlen
Semantik nur ueber die Formatversion, niemals ueber Feature-Sniffing.

Containeruebergreifende Aufrufe bleiben ausschliesslich namensbasiert und
duerfen nur Exporte adressieren. Entry-Ordinale sind nie ein Cross-Container-
ABI.

Ein `entry-ref` darf auch in Funktionsdesignatorposition stehen. Der Commit
materialisiert dort dasselbe BCODE-Immediate; die bereits vorhandenen nativen
`apply`-/`funcall`-Pfade akzeptieren BCODE. Damit bleiben unter anderem
`%ide-fasl-slot-p` und `%ide-source-file-p` anonym, obwohl sie an
`remove-if-not` uebergeben werden.

## 2. Validator- und Commit-Semantik

Die historische Duplikatklasse bleibt ausdruecklich gegatet:

- Benannte Eintraege werden wie in v1 nach dekodiertem Namen auf Duplikate
  geprueft.
- Namenlose Eintraege haben keine Namensduplikate; ihre Identitaet ist der
  strukturell eindeutige Ordinal.
- Phase 05 hasht und vergleicht nur benannte Eintraege. Namenlose ueberspringen
  ausschliesslich den Namenstest, niemals Ordinal-, Range- oder Codepruefungen.
- Phase 05 enumeriert jeden Entry-Index genau einmal und prueft jeden
  `entry-ref` gegen `entry_count`; namenlos bedeutet nie ungeprueft.
- `entry-ref` muss im selben Artefakt liegen. Referenzen auf Macros und
  artefaktfremde Eintraege scheitern.
- Jeder Fehler bleibt transaktional: kein Directory-Slot und keine
  Funktionszelle duerfen teilweise publiziert werden.

Python-Vertrag, nativer Host-Loader und Workbench-Overlay-Validator erhalten
dieselbe v1/v2-Positiv- und Negativmatrix.

## 3. Diagnose-Story

Das Produktgeraet internt fuer namenlose Eintraege keinen Diagnosenamen. Die
stabile Adresse lautet stattdessen:

`Artefakt-SHA + Entry-Ordinal + CodeObject-Offset`.

Das Blob-Manifest bindet dazu Helpername, Quellpfad und Code-SHA. Receipts
binden Manifest-SHA und Artefakt-SHA gemeinsam. Ein Diagnose-Build darf eine
separate Namenstabelle mitfuehren; sie ist kein Produkt-Lookup und kein
oeffentlicher Dialektbestand. Laufzeitfehler nennen mindestens Artefakt-ID und
Ordinal, damit der Host die Quelladresse deterministisch aufloesen kann.
Die reproduzierbare Meldungsform ist `lib <artifact-id> entry #<ordinal>`,
beispielsweise `lib ide entry #57`; der Ordinal ist nullbasiert.

## 4. Messziel fuer IDE und IDEX

Der aktuelle Manifest-Census zaehlt 87 `%`-Directory-Eintraege in IDE und 13
in IDEX. Zusammen mit 40 bereits private-inline kompilierten Helfern ergibt
das 140 private Helfer – die belastbare Form der frueheren ~150-Prognose.

Die erste Blockprojektion lautet daher:

- 100 Directory-only-Eintraege;
- 40 bereits inline, keine zusaetzliche Inline-Ausweitung im Block;
- brutto 100 nicht internierte Symbole und 2006 Namepool-Bytes weniger;
- Directory-Entry-Delta null, weil Namenlosigkeit den Code-Slot nicht
  entfernt;
- die separate IDE-Familien-Netto-Projektion bleibt `-72/-1295 B`.

Die Blockabnahme muss diese Zahlen aus frisch gebauten IDE-/IDEX-Manifesten
neu ableiten und zusaetzlich Containerdelta, Kompositionsmarge sowie den
gebundenen v2-Stack-Guard-Link ausweisen.

Die Probe trifft die Projektion exakt: 87 IDE- plus 13 IDEX-Eintraege werden
anonym, 100 Symbolinternings und 2006 Namepool-Bytes entfallen, das Directory-
Delta bleibt null. 252 Literalstellen werden zu Entry-Refs: 248 direkte
CALL/TAILCALL-Ziele und vier Funktionsdesignatoren. Das physische
Containerdelta ist wegen separatem Align2-Pad `-1714 B` und `-290 B`, zusammen
`-2004 B`; dies aendert die Namepool-Zahl nicht. Aus 39 Symbolslots und 490 B
Namepool-Marge werden projiziert 139 Slots und 2496 B. Die 32 Post-Align-
Directory-Slots bleiben unveraendert. Der Produktlink wurde in der Hostprobe
nicht bewegt; `bank_delta=0`.

## 5. Scope-Grenze und Promotion

Der Block liefert Format, Validator, Commit, lokale Referenzen und Diagnose-
Mapping. Export-only-Interning fuer `require`, `unload`, First-Class-Buffer
und neue IDE-Kommandos bleiben ausserhalb. Insbesondere darf die anonyme
Entry-Mechanik nicht nebenbei zur allgemeinen Import- oder Lebensdauerpolitik
anwachsen.

Promotion verlangt duale v1/v2-Dekodierung, drei Validatorpfade, alle
Negativklassen, null offene R2-Produktlinkfaelle und eine neue Probe gegen den
gebundenen Produktlink. Hardwareautoritaet entsteht erst mit dem spaeteren
IDE-Familienkandidaten.

Das Block-Receipt fuehrt verpflichtend `bank_delta`. Null oder Rueckgewinn
tragen keine Autorisierung; jede Ausgabe bindet eine bereits vor dem Block
erteilte, betragsgleiche Autorisierung fuer genau das gebundene Produkt-SHA-
Paar. Unautorisierte Drift macht das Gate rot.
