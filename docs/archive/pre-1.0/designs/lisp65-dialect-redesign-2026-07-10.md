# lisp65-Dialekt-Redesign: Hardware-orientierte Sprachverschlankung (2026-07-10)

Status: Designvorschlag (Claude), kein Produktvertrag. Baut auf dem
Hardware-DeepDive (`mega65-hardware-deepdive-2026-07-10.md`) und den
Ist-Messwerten des Workbench-Pins auf. Einordnung in den Sanierungsplan:
Die Symbolökonomie-Stufen 1–2 (§6) zahlen direkt auf die AP4-Reserveziele
ein; alles Übrige ist Post-G6-Material (AP8) und respektiert den
Feature-Freeze. Normativer Ort für die Umsetzung wären die AP5-Fixtures
(Sprachinventar), nicht dieses Dokument.

> **Aktualisierung 2026-07-11 (nach AP4-Abschluss und IDE-Kapazitätsphase):**
> Mehrere Vorschläge sind inzwischen produktiv, teils in abgewandelter Form:
>
> - **HW-Math (§3):** umgesetzt — die Softmult-/Softdiv-Ablösung hat 519 B
>   in den AP4-Baseline-Link eingebracht. Als Polster ist dieser Hebel
>   damit verbraucht.
> - **Entsymbolisierung (§6.1):** erste realisierte Variante — die
>   IDE-Kapazitätsphase kompiliert 40 interne `%ide-*`-Helfer privat inline
>   (IR-Markierung im Hostcompiler, fail-closed-Guards; siehe
>   `ide-capacity-remediation-2026-07-11.md`). Das ist konservativer als
>   Directory-only, erreicht aber dasselbe Ziel ohne ABI-Änderung. Für die
>   Stdlib steht die Entscheidung Directory-only vs. Inline noch aus.
> - **Tiering/Paketsystem (§6.2):** dem Modell entsprechend umgesetzt —
>   `IDE` (Pflichtkern, 152 Einträge) + `IDEX` (Komfort, 29) als getrennte
>   Disk-Libs mit fail-closed Hook; `M65D` als eigene on-demand
>   Persistenz-Lib; die Lib-Manifeste tragen `provides`/`requires`, und der
>   L65M-Preflight prüft Symbol-/Directory-/Namepool-Budget vor dem Commit.
>   Offen bleiben Export-Listen-Interning und LIFO-`unload`.
> - **Fehlerkanal (§4):** die Richtung „Code + Text, ein Kanal“ ist mit der
>   L65E-Sparse-Texttabelle (Slot 36, 45 Codes/31 Texte, `Ehh`-Fallback)
>   und der 10-Code-Persistenz-ABI (`persistence-contract.json`) produktiv.
> - **Ist-Zahlen (§1):** überholt. Nach AP4/IDE-Split/M65D gilt:
>   Post-Boot-Reserve 1811 B (statt 274), Projektion 544/552 Directory,
>   ~693/720 Symbole, ~9,2/9,5 KB Namepool. Die Analyse-Aussage bleibt
>   gültig (Benennung ist die knappste Ressource), die Dringlichkeit hat
>   sich durch die umgesetzten Maßnahmen aber von „akut“ zu „strukturell“
>   verschoben.
> - **§10-Nachträge:** Fehlertext-Diät umgesetzt (L65E); als deklarierte
>   Reserven verbleiben nur noch die Primitivnamen-Tabelle (~300–400 B)
>   und 932 B eingefrorener Insel-Headroom.

Ziele (Auftrag):

1. Eleganz und Expressivität von Common Lisp (Lisp-2) im Kern beibehalten.
2. Sprachkern/Stdlib drastisch und hardwareorientiert verschlanken.
3. Echten Budgetgewinn erzielen, vorrangig bei Symbolen/Namepool.
4. Erweiterbarkeit über Bibliotheken mit einfachem Paketsystem.

---

## 1. Ist-Analyse: Wo die Sprache heute wirklich drückt

Die knappste Ressource ist nicht Heap oder Code, sondern **Benennung**:

| Ressource | Pin (Workbench, 2026-07-09) | Frei |
| --- | --- | ---: |
| Laufzeitsymbole (`MAX_SYM`) | 690 / 720 | **30** |
| Namepool | 9316 / 9568 B | **252 B** |
| VM-Directory (Bytecode-Funktionen) | 539 / 552 (post-align 544) | 8–13 |
| Bank-0-Reserve | 274 B | — |

Dazu die Strukturanalyse der Bytecode-Stdlib (Suite-Profile, 2026-07-10):

- Einsuite-Profil: **385 Funktionen, davon 206 (53 %) `%`-interne Helfer**;
  reine Namenslast ~4,8 KB.
- Residentes 264er-Profil (`stdlib-p0.manifest.json`): 115 von 264 intern
  (44 %), **1872 von 3548 Namensbytes** entfallen auf Helfer, die kein
  Nutzer je aufruft.
- Die ladbare IDE-Lib bringt weitere ~219 Einträge, überwiegend `%ide-…`
  mit sehr langen Namen (`%ide-disk-effective-sector` = 26 Zeichen — jedes
  Zeichen ist ein Namepool-Byte).
- Implementierungsmuster wie `filter → %filter-into`,
  `%reduce-from`, `%count-from` (Akkumulator-Splits wegen Tail-Call-Form)
  verdoppeln systematisch die Symbolzahl pro exportierter Funktion.

**Kernbefund:** Rund die Hälfte des Symbol-/Namensbudgets bezahlt heute
nicht die Sprache, sondern ihre Implementierungstechnik. Ein Redesign, das
nur CL-Funktionen streicht, aber dieses Muster behält, verfehlt den
größten Hebel.

Zweiter Befund: Die CL-Nähe kostet vor allem an drei Stellen — (a)
Aliase/Nuancen-Duplikate (`first`/`car`-Familie, `remove-if` +
`remove-if-not` + `count-if` + `find-if` + `position-if` als je eigene
Kette), (b) generische Sequenzfunktionen über Listen *und* Strings,
(c) die String-Schicht, die historisch über Zeichenlisten
(`%char-list=`, `%case-fold-list`, …) implementiert ist, obwohl die
Packed-String-Arena existiert.

Dritter Befund (aus dem DeepDive): Die Hardware gibt Operationen her, die
die Sprache heute in Software nachbaut — 840 B llvm-mos-Arithmetik trotz
HW-Multiplier/Divider; Zeichenlisten-Strings trotz DMA; kein Sprachzugang
zu DMA/Audio/VIC-IV außer rohem `peek`/`poke`.

---

## 2. Designprinzipien

1. **Lisp-2-Kern bleibt.** Getrennte Funktions-/Wertzellen, `defun`,
   `defmacro` + Quasiquote, `#'`/`funcall`/`apply`, lexikalische Bindung
   wie geplant. Das ist die Eleganz, die erhalten wird — sie kostet fast
   nichts, weil sie Mechanik ist, nicht Vokabular.
2. **Benennung ist die Leitwährung.** Jede Designentscheidung wird zuerst
   in Symbolslots und Namepool-Bytes bewertet, dann in Code-Bytes, dann in
   Zyklen. (Das inverse Modell zu CL, wo Namen gratis sind.)
3. **Eine Form pro Bedeutung.** Keine Nuancen-Duplikate: eine
   Gleichheitsstufung, eine Filterfunktion mit Prädikat, ein Map. Wo CL
   drei Namen hat, wählt lisp65 den allgemeinsten und macht die Nuance zum
   Argument.
4. **Pay for what you load.** Der residente Kern deckt REPL, Editor-Loop
   und Maschinenzugriff. Alles andere — auch CL-Komfort — ist ladbare
   Bibliothek und gibt seine Symbole beim Entladen zurück (§6.2).
5. **Die Hardware ist die Stdlib.** Für Grafik/Sound/Disk ist nicht CL das
   Vorbild, sondern BASIC 65: dessen Kommandoflächen sind erprobte,
   nutzergerechte Kapselungen der realen Chips (Bundle-Plan existiert in
   `mega65-basic-parity-libraries.md`). Fähigkeitsparität über VIC-IV-Modi,
   nicht Mechanismusparität mit Bitplanes.
6. **Kein ANSI-Anspruch, aber CL-Muskelgedächtnis.** Wer CL kann, soll
   lisp65 flüssig schreiben; wer lisp65-Code liest, soll ihn als Lisp
   erkennen. Abweichungen werden zentral dokumentiert und in Fixtures
   gepinnt (AP5), nicht verstreut.

---

## 3. Der Sprachkern (resident)

### Spezialformen (unverändert schlank)

`quote`, `if`, `lambda`, `setq`, `progn`, `defmacro` (+ Quasiquote),
`function`, `defun`, `let`/`let*`, `when`/`unless`, `case`, `dotimes`/
`dolist`, `catch`/`throw`-Basis. (Ist-Stand aus `core-vs-library.md`;
die MVP-Ausnahmen bleiben, sie haben sich bewährt.)

### Residente Primitive — Zielliste (~70 Namen)

| Gruppe | Namen |
| --- | --- |
| Zellen | `cons car cdr rplaca rplacd list append nreverse length nth nthcdr` |
| Listen-Arbeit | `member assoc mapcar mapc filter find` (Prädikat optional, Default `eq`; `assoc` ersetzt das heutige `assq`) |
| Prädikate | `eq equal null atom consp symbolp numberp stringp zerop` |
| Arithmetik | `+ - * / mod = < > <= >= min max abs logand logior logxor ash` |
| Funktional | `apply funcall eval` |
| Symbole | `intern gensym symbol-value set boundp` |
| Strings (Arena) | `string-length string-ref substring string-append string= string<` |
| Bytes/Buffer | `make-buffer buffer-ref buffer-set! buffer-length` (§7) |
| I/O | `princ prin1 print terpri write-char read read-from-string` |
| Maschine | `peek poke peekw pokew edma sector-read sector-write key-event ticks` |
| System | `load load-lib require gc room error` |

Bewusst **nicht** resident (→ Bibliothek oder gestrichen, §4/§5):
`format`, `setf`-Familie, `reduce`/`every`/`some`, Plists, `sort`,
Festkomma, sämtliche Grafik/Sound, `string-upcase`-Familie,
Trim/Search-Familie.

Benannte CL-Komfort-Bündel (ladbar, je mit Export-Liste nach §6.2):

- **`lists`**: `reduce every some mapcan count position butlast copy-list
  adjoin union complement sort` sowie die Plist-Fläche `getf putf remf`.
- **`str`**: Trim/Case/Search/Prefix-Familie, neu über Arena/Buffer.
- **`fmt`**: `format`-Teilmenge (`~a ~s ~d ~%`), `write`/`write-line`.
- **`places`**: `setf incf decf push pop` über festem Place-Satz.
- **`fixed`**: Festkomma über HW-Divider (Ist-Lib, portiert).

Anmerkungen:

- `logand/logior/logxor/ash` sind neu im Kern: Bitoperationen sind auf
  dieser Plattform Grundvokabular (Register-Masken!), in CL aber billig —
  vier Primitive ersetzen dutzendfach `peek`-Bastelei in Libs.
- `*`, `/`, `mod` laufen über die HW-Math-Einheit (DeepDive §5/§13.A.1) —
  **seit AP4 umgesetzt** (519 B Bank-0-Gewinn im Baseline-Link).
- `equal` ist die einzige strukturelle Gleichheit; `eql` entfällt
  (Fixnums sind immediate — `eq` deckt CLs `eql`-Kernfall ab). `string=`
  bleibt, weil Strings gepackt sind und `equal` sie delegiert.

---

## 4. Streich- und Konsolidierungsliste (gegenüber CL und Ist-Stdlib)

### Ersatzlos (im Sinne von: nie resident, kein Lib-Versprechen)

- Rationals, Bignums, Floats, Complex; `values`/Multiple-Values;
  CLOS/`defclass`/Generics; Condition-System mit Restarts; `loop`-Makro;
  Pathnames/Streams-Hierarchie; Unicode-/Zeichenklassen-Apparat;
  `&key`-Lambda-Listen (nur `&optional`/`&rest`); Packages nach CL-Art.
- Begründung durchgängig: 16-Bit-Fixnum-ABI, ein Gerät, ein Nutzer,
  kein OS — die Abstraktionen hätten keinen Gegenstand.

### Konsolidiert (eine Form statt N Nuancen)

| CL / Ist-Stand | lisp65-Redesign |
| --- | --- |
| `first…fourth`, `cadr`-Familie | nur `car/cdr/nth` (Aliase sind reine Namepool-Kosten) |
| `remove-if` + `remove-if-not` + `count-if` + `find-if` + `position-if` (+ je `%…-into`/`%…-from`) | `filter pred lst`, `find pred lst`, `count pred lst`, `position pred lst` — Prädikat immer explizit, `-not` via `complement` (Lib) |
| `mapcar/mapc/mapcan` | `mapcar` + `mapc` resident; `mapcan` → Lib |
| `member/assoc` mit `:test/:key` | `member x lst` (`eq`-basiert) + optionales Prädikat-Argument; kein Keyword-Parsing |
| `eq/eql/equal/equalp/string=/char=` | `eq` + `equal` + `string=` |
| `mod/rem`-Paar | nur `mod` (HW-Divider-Semantik dokumentieren und pinnen) |
| `princ/prin1/print/write/write-line/write-string/terpri` (7 Namen resident) | `princ prin1 print terpri write-char` (5); `write`/`write-line` → Lib-Aliase |
| String-Trim/-Case/-Search-Familie (34 Funktionen in `stdlib-strings.lisp`) | Arena-basierte Minimalfläche im Kern (6), Rest als `str`-Lib **neu über Buffer-Primitive statt Zeichenlisten** |
| `setf`+`incf`+`decf`+`push`+`pop`+Places-Apparat (8 Defs + Expander) | `setf`-Light als Lib-Makro über festem Place-Satz (`car`, `cdr`, `nth`, `symbol-value`, `buffer-ref`); kein generischer Expander |
| `do` (allgemein) | gestrichen; `dotimes/dolist/while` decken die realen Nutzungen, `do` bei Bedarf als Lib-Makro |

Der Effekt ist zweifach: weniger exportierte Namen **und** — wichtiger —
der Wegfall der internen Ketten dahinter (jede gestrichene
`…-if-not`-Variante nimmt ihre `%…-into`-Helfer mit).

### Fehlerbehandlung

Kein Condition-System. Ein Fehler ist `(code . message)` auf einem
einzigen Kanal (`lisp_abort`-Mechanik + `reader_status`-Vorbild aus AP1):
`(error code msg)`, `catch/throw` für Nichtlokales, `(on-error handler
thunk)` als Lib-Makro darüber. Das deckt REPL-Erholung, IDE-Statuszeile
und Bibliotheksfehler ab — mehr braucht ein Ein-Nutzer-System nicht.

---

## 5. BASIC-10/65-Paritätsfläche als Sprachbestandteil zweiter Klasse

Die Paritätsplanung (`mega65-basic-parity-libraries.md`) bleibt gültig und
wird zum **Hauptwachstumspfad der Sprache erklärt** — statt weiterer
CL-Annäherung. Prioritäten aus dem DeepDive geschärft:

1. `m65-hw` (Registerkonstanten, `edma`, Knock, `key-event`, `ticks`) —
   dünn, resident nur `peek/poke/edma`-Primitive.
2. `m65-disk` (Ist-Stand produktisieren) + später `disk-attach`
   (HYPPO-`d81attach`, nach Klärung der Kontextfrage).
3. `m65-sound`: Sample-Playback über Audio-DMA (kein Tick nötig),
   SID-Register-API; Sequencer (`play`) erst mit Tick-Hook.
4. `m65-gfx`/`m65-sprite`: VIC-IV-Fähigkeitsparität (FCM/SEAM statt
   Bitplanes), `LOADIFF`-Import als Asset-Weg.
5. `basic65`-Facade für Umsteiger.

Adresskonvention für alle Maschinen-Prims (aus BASIC 65 übernommen, im
DeepDive als kopierwürdig identifiziert): **Adressen < `$10000` sind
bankrelativ, Adressen ≥ `$10000` sind flache 28-Bit-Adressen.** Ein
Muster, null Sonder-API, deckt Chip-RAM, Colour-RAM (`$FF80000`) und
Attic (`$8000000`) ab. Implementierung intern via DMA (Flat-Access ist
HW-rot, DeepDive §2).

---

## 6. Das Herzstück: Symbol- und Namensraum-Redesign

### 6.1 Stufe 1 — Interne Helfer entsymbolisieren (größter Einzelhebel)

Heute interniert jeder `%`-Helfer ein volles Symbol (Name im Namepool,
Slot in `MAX_SYM`, Directory-Eintrag). Vorschlag: Der Compiler (`lcc` und
Host-Generator) erhält `(defun-local …)` bzw. behandelt `%`-Präfix als
**lib-lokal**: Der Helfer bekommt nur einen Directory-Index; Aufrufe
innerhalb der Lib werden zur Compile-Zeit auf den Index gebunden
(CALL/TAILCALL tragen ohnehin Directory-Indizes). Kein Interning, kein
Namepool-Eintrag, keine `symfn`-DMA-Auflösung zur Laufzeit.

Konservativ gerechnet (Basis: 264er-Manifest + IDE-Lib):

| Posten | heute | nach Stufe 1 |
| --- | --- | --- |
| Symbole der `%`-Helfer (resident + IDE-Lib geladen) | ~115 + ~150 | **0** |
| Namepool der Helfer | ~1,9 KB + ~2,5 KB | **0** |
| `MAX_SYM`-Pin | 720 (690 belegt) | realistisch **≤ 512** |
| Namepool-Pin | 9568 (9316 belegt) | realistisch **≤ 6 KB** |

Sekundäreffekte: kleinere EXT-Symboltabellen (Bank-5-Layout entspannt
sich, `SYMPOOL_EXT_OFF` kann steigen → mehr EXT-Codefenster), weniger
`symfn`-Lookups im CALL-Hotpath (heute 8939 dynamische Auflösungen im
Workbench-Slice — jeder Helfer-Call zahlt DMA), schnellere GC-Scans der
Symboltabelle. Debugging bleibt möglich: das Blob-Manifest behält die
Namen; ein Diagnose-Build kann sie optional mit-internieren.

Risiken: `eval`-basierte Aufrufe interner Helfer (Tests!) brauchen die
Diagnose-Variante; `allow_omitted_defuns`-Maschinerie und Suite-Formate
müssen Directory-only-Einträge kennen. Das ist genau die Art Arbeit, die
in AP5 (Fixtures/Adapter) ohnehin ansteht — deshalb dort andocken.

### 6.2 Stufe 2 — Minimal-Paketsystem: Lib-Segmente mit Export-Liste

Kein CL-Package-System (kein `use`, kein Shadowing, keine
Doppelpunkt-Syntax im Reader). Stattdessen das Modell, das der bestehende
`load-lib`-Mechanismus fast schon nahelegt:

- Jede Lib deklariert einen Kopf:
  `(provide gfx (export rect line palette sprite!) (require m65-hw))`.
- **Nur exportierte Namen werden global interniert.** Alle anderen
  Definitionen der Lib sind Directory-only (Stufe 1).
- Die Symbole einer Lib werden als **Segment** interniert (Symboltabelle
  und Namepool sind Append-Strukturen — ein Segment ist ein
  Wasserzeichen-Paar). `(unload 'gfx)` setzt Directory, Symbol- und
  Namepool-Wasserzeichen zurück, sofern keine spätere Lib darüber liegt
  (LIFO-Entladung; genau wie der bestehende EXT-Code-Abwärtsstapel).
- `require` ist idempotent, lädt von der eingelegten D81 (`load-lib`-
  Unterbau) und prüft das Budgetdelta aus dem Lib-Manifest **vor** dem
  Laden („lib needs 34 symbols, 12 free“ statt mittendrin OOM).
- Namenskollisionen: letzte Definition gewinnt, mit REPL-Warnung —
  CL-Shadowing-Komplexität ist den Preis nicht wert.

Damit wird das Symbolbudget von einer globalen Session-Grenze zu einer
**Pro-Arbeitslast-Grenze**: Editor-Session lädt `ide`, Grafik-Session lädt
`gfx` — beide müssen nicht gleichzeitig passen.

### 6.3 Stufe 3 — Namensdiät

- Exportierte Namen ≤ 12 Zeichen als Richtwert (Namepool!); interne Namen
  sind nach Stufe 1 gratis, dürfen also beliebig sprechend sein — die
  heutige Ökonomie ist genau invers.
- Keyword-Symbole sparsam: Keywords internieren wie Symbole. Wo heute
  `:foo`-Optionen wären, nimmt das Redesign Positionsargumente oder
  Fixnum-Flags (Registerkultur der Plattform).
- Der Reader lehnt Namen > 31 Zeichen bereits ab (AP1-Vertrag) — das
  Redesign macht die Grenze zur bewussten Konvention statt zur Falle.

---

## 7. Datenstrukturen: schlank und DMA-gerecht

- **Fixnum 15 Bit** (Ist, `obj`-ABI) bleibt das einzige Zahlenformat des
  Kerns. Festkomma 16.16/32.32 als `fixed`-Lib über den HW-Divider (der
  den Bruchanteil gratis liefert, DeepDive §5) — deckt Grafik-Mathematik
  ab, ohne Float-Illusionen.
- **Strings = Packed-Byte-Arena** (Ist) als einzige String-Repräsentation;
  die Zeichenlisten-Implementierung der String-Lib wird ersetzt (das
  entfernt allein ~15 `%char-list-*`-Helfer samt Cons-Druck).
- **Buffer als neuer First-Class-Typ:** ein Byte-Vektor, dessen Payload
  außerhalb des Cons-Heaps liegt (Bank 4/EXT oder — für kalte Assets —
  Attic), beschrieben durch `(bank, addr, len)` im Objektheader.
  `buffer-ref/set!` sind Prims; `edma` akzeptiert Buffer direkt.
  Damit sind Samples, Sprites, Screens, Sektorpuffer und FASL-Staging
  **dasselbe Sprachobjekt**, und die Grafik-/Sound-Libs brauchen keine
  eigenen Speicherkonzepte. (Der Disk-Scratch und die String-Arena sind
  heute schon genau das — nur ohne Sprachzugang.)
- **Vektoren:** nur eindimensional, Fixnum-indiziert, als Lib über Buffer
  (Wortbreite 2 B) — kein `make-array`-Apparat, keine displaced arrays.
- **Alists sind die Key-Value-Struktur der Plattform:** nur Conses, kein
  eigener Typ, `assoc` resident (§3). Keine Hashtabellen im Kern — bei den
  realistischen Größen (Dutzende Einträge) schlägt lineare Suche über
  Conses jede Hash-Infrastruktur; die einzige „echte“ Hashstruktur des
  Systems bleibt die Symboltabelle selbst. Wer Symbol-Keys hat, nutzt
  ohnehin Symbolwert/-eigenschaft.
- **Plists:** komplett in die `lists`-Lib (`getf putf remf`, §3) — sie
  sind ein Idiom, kein Grundbaustein, und ihre Keyword-Keys kosten
  Namepool (§6.3).

---

## 8. Budget-Abschätzung (konservativ, gegen Ist-Pin)

| Maßnahme | Symbole | Namepool | Bank 0 | Anmerkung |
| --- | ---: | ---: | ---: | --- |
| Stufe 1 resident (115 Helfer) | −115 | −1,9 KB | ±0 | Directory bleibt gleich groß |
| Stufe 1 IDE-Lib (~150 Helfer) | −150* | −2,5 KB* | ±0 | *nur solange geladen |
| Konsolidierung §4 (Aliase, Ketten, Do/Places) | −30…−45 | −0,5 KB | −0,3…−0,6 KB Blob | weniger Bytecode, weniger Fixups |
| HW-Math-Prims | ±0 | ±0 | −450…−520 B | DeepDive §13.A.1, gemessen |
| String-Lib auf Arena/Buffer | −15 | −0,3 KB | ±0 | plus deutlich weniger GC-Druck |
| Keyword-/Namensdiät | −10…−20 | −0,3 KB | ±0 | laufende Disziplin |

Realistisches Gesamtbild nach Stufen 1–3: `MAX_SYM` von 720 auf **≈ 480–512**
und Namepool von 9568 auf **≈ 5,5–6,5 KB** pinbar — das gibt dem Bank-5-
Layout (Namepool + Symboltabellen + EXT-Code teilen sich 64 KB) mehrere KB
zurück und macht die Session-Kapazität erstmals planbar statt „bis zum
nächsten Cap-Shift“. Dazu ~0,8–1,1 KB Bank-0-Gewinn (HW-Math +
Blob-Verkleinerung), der direkt auf die AP4-Zielwerte einzahlt.

---

## 9. Migrationspfad (gestuft, sanierungskonform)

1. **Jetzt (parallel zur Sanierung, nur Papier/Fixtures):** Dieses Design
   reviewen; in AP5 die normative Sprachinventar-Fixture so anlegen, dass
   sie zwischen „Kern“, „Lib“ und „gestrichen“ unterscheidet — dann ist
   das Redesign eine Fixture-Änderung, kein Wildwuchs.
2. **Mit AP4 (falls Reserve knapp):** HW-Math-Prims (gemessener Hebel)
   und ggf. Stufe 1 nur für die IDE-Lib (die Helfer sind dort am
   langnamigsten). Beides ändert keine Sprachsemantik.
3. **AP5/AP7:** Directory-only-Einträge in Suite-Formate und
   Omitted-Guard aufnehmen; `provide/require/export`-Kopf als
   Lib-Manifest-Format definieren (deckt sich mit dem geplanten
   Runtime-Export-Vertrag).
4. **Post-G6 (AP8):** Konsolidierung §4 als eigene Meilensteine, je mit
   Fixture-Delta + Budgetreport; danach Paritäts-Libs in der Reihenfolge
   §5. Die `cl-compat`-Idee des Vorgängerprojekts wird bewusst **nicht**
   wiederbelebt — Kompatibilitätsschichten sind auf dieser Plattform
   Namepool-Leasingverträge.

## 10. Nachtrag: Potential unterhalb der Sprachebene (Messung 2026-07-10)

Nachgemessen am Workbench-ELF (`llvm-nm`/`llvm-size`); Text gesamt 39,2 KB.

### 10.1 String-Diät im Bank-0-Image (~2 KB Bestand)

Das PRG trägt ~2083 Bytes String-Literale (.rodata 1828 B): Fehlertexte
(`"vm: stack overflow"`, `"reader: unclosed list"`, …) **und** die Namen
der C-Primitive (`"number->string"`, `"write-char"`, …), die `eval_init`
beim Boot interniert. Beides ist doppelt teuer: Bank-0-Bytes plus
Namepool-Einträge. Hebel:

- Fehlertexte → Fehlercodes + Texttabelle: **umgesetzt** als L65E-v1-Slice
  (Slot 36, Sparse-Tabelle 45 Codes/31 Texte, `Ehh`-Fallback resident).
- Primitivnamen-Tabelle in den Blob verlagern (wird nur beim Boot-Intern
  gebraucht): **noch offen** — letzte deklarierte rodata-Reserve
  (~300–400 B) neben dem eingefrorenen Insel-Headroom.

### 10.2 VM/ISA-Audit (der größte Codeposten)

`vm_run` (7,4 KB) + `vm_callprim` (4,2 KB) + `apply` (4,0 KB) +
`vm_frame_fill` (0,6 KB) ≈ **16 KB = 40 % des gesamten Texts**. Kandidaten:

- Opcode-Inventur gegen reale Häufigkeit (die JTAG-Op-Zähler existieren):
  selten genutzte Opcodes/CALLPRIM-Einträge in Bytecode/Lisp verlagern,
  häufige Folgen als Superinstruktionen prüfen — beides erst nach Messung.
- Directory-Metadaten kosten Bank-0-BSS pro Slot (`dir_len` allein 552 B
  bei `VM_DIR_MAX=552`) — jede Directory-Diät (Redesign §6) zahlt also
  auch in Bank 0 aus.
- FASL-/Disk-Lib-Format: Nach §6.1 können Namen von Directory-only-
  Einträgen aus den Disk-Libs entfallen — kleinere D81-Libs, schnellere
  Loads, weniger Namepool beim Laden.

### 10.3 Die Ein-Engine-Frage (post-G6, groß)

Der Treewalk-Pfad (`eval`-Familie 1,6 KB + großen Teilen von `apply`,
zusammen ~5,6 KB) existiert neben der Bytecode-VM. Ein REPL, der jede
Form durch `lcc`/Bytecode schickt, würde (a) mehrere KB Bank 0 freigeben,
(b) die im Review als F7 kritisierte doppelte semantische Wahrheitsquelle
tilgen und (c) den Bereich des offenen `every`/`some`-HW-Hängers
strukturell entfernen. Hohes Risiko/hoher Umbau — nur als eigener
Meilenstein mit Differentialtests, aber als Zielbild festhalten:
**eine Semantik-Engine auf dem Gerät.**

### 10.4 Toolchain-Nachbrenner (billige Experimente)

`--icf=all` ist seit AP1 im Produktlink. Ergänzend messen: `-Oz` (falls
nicht aktiv), llvm-Machine-Outliner, `-fmerge-all-constants`. Jeder
Prozentpunkt auf 39 KB Text ist ~400 B — dieselbe Größenordnung wie ein
mittlerer Reclaim-Spike, für einen Flag-Versuch.

### 10.5 Geprüft und verworfen

- **cdr-Coding** (Listenkompression à la Lisp-Maschine): spart Heap, kostet
  aber Komplexität in GC/rplacd und passt nicht zum 16-Bit-`obj`-ABI mit
  EXT-Zellen. Heap ist zudem nicht die knappste Ressource.
- **NaN-/Pointer-Tagging-Tricks**: bei 16-Bit-Fixnums ist das bestehende
  1-Bit-Tag bereits optimal.

## 11. Offene Fragen

1. Tail-Call-Splits (`%…-into`-Muster) nach Stufe 1: bleiben als
   Directory-only-Paare oder löst ein Compiler-Feature (Loop-Konversion)
   sie ganz auf?
2. `unload`-LIFO vs. echte Segmentverwaltung: reicht LIFO für die realen
   Sessions (IDE ↔ gfx-Wechsel), oder braucht es Kompaktierung?
3. Buffer-GC: Pinning-Regeln für DMA-Ziele (GC darf Payload nicht
   bewegen — bei Fixpoint-Sweep ohne Kompaktierung heute trivial, bei
   späterem Copying-GC ein Vertrag).
4. `mod`-Semantik final pinnen (HW-Divider ist unsigned; CL-`mod` vs.
   Dividenden-Vorzeichen — einmal entscheiden, in Fixture nageln).
5. PETSCII/ASCII-Politik der String-Fläche (Directory-Namen sind
   Shift-PETSCII, REPL ist ASCII-nah — eine Konvertierungsstelle
   definieren).
