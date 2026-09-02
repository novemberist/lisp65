# Dialekt-v2-Migrationsvertrag

Stand: 2026-07-13

Dieses Dokument beschreibt den normativen Schnitt fuer die Migration von
Dialekt v1 zu Dialekt v2. Die maschinenlesbaren Autoritaeten sind:

- `config/dialect-contract.json`: eingefrorenes v1-Inventar;
- `config/dialect-migration-contract.json`: Migrationspolitik und Zielmatrix;
- `config/dialect-profile-selection.json`: aktive Profilauswahl;
- `config/bytecode-abi-ledger.json`: dauerhafte P0-ID-Identitaeten;
- `config/dialect-v2-g5-matrix.json`: Hardwarematrix fuer die spaetere
  Produktumschaltung.

Der lokale Entwurf `lisp65-dialect-redesign-2026-07-10.md` ist eine
Planungsquelle, aber kein Produkt- oder Semantikvertrag.

## Profillebenszyklus

Dialekt v1 ist ein `frozen-evidence`-Profil. Es erhaelt keine Features und
keine Backports. Der einzig erlaubte Vorgang ist ein isolierter
Reproduzierbarkeits-Rebuild aus dem gepinnten Source-Commit. Das Profil wird
archiviert, sobald Dialekt v2 die vollstaendige, manifestgebundene
`dialect-v2-product-switch`-G5-Matrix bestanden hat.

Die Bindungspruefung materialisiert dafuer den gepinnten Commit isoliert und
wertet Vertrag, Suite-Manifeste und Quellen ausschliesslich in diesem
Snapshot aus. Sie bindet das eingefrorene v1-Inventar nie an die inzwischen
weiterentwickelten v2-Dateien des Live-Baums.

Dialekt v2 entsteht als separates Migrationsprofil. Es gibt keine
Runtime-Kompatibilitaetsbibliothek und keine alten Runtime-Aliase. Quellcode
wird familienweise migriert. Der Profilselektor darf v2 erst aktivieren, wenn
externe G5-Evidenz die unveraenderte Migrationspolitik, den v2-Vertrag, den
Candidate, die Build-ID und die Familienmessungen bindet. Diese Promotion ist
keine Releasefreigabe; G6 bleibt ein unabhaengiger Vertrag.

Der Workbench-v2-Link und die interne CP5-Hardwarematrix sind inzwischen
geschlossen. Der Capability-/Carrier-Block ist als einziger Architekturblock
atomar promotet; dadurch ist R2 als sequenzielle Familienmigration offen.
Neue AP8-Bloecke brauchen weiterhin einen eigenen expliziten Vertrag. Das
einzige Releaseprodukt bleibt Workbench-v2, Dialekt v1 bleibt reproduzierbare
Evidenz und ist kein Auslieferungskandidat.

Migrationspolitik und Promotionzustand sind getrennt. Dadurch veraendert eine
spaetere Promotion nicht den SHA der Politik, den ihr G5-Receipt beweisen soll.

## Klassifikation

Das Gate loest die realen v1-Surfaces auf und klassifiziert alle 231
eindeutigen oeffentlichen Namen exakt einmal. Die Regeln sind:

1. `%`-Definitionen, Descriptor-Nicht-Exporte und `private_inline_functions`
   sind intern.
2. Jeder oeffentliche v1-Name braucht genau eine explizite Disposition.
3. Ein neuer oeffentlicher Name ohne Klassifikation macht G0 rot.
4. Mehrdeutige Regeln, stale Ausnahmen und Catch-all-Regeln sind ungueltig.
5. `replace` bezeichnet eine Quellmigration, niemals einen Runtime-Alias.
6. `remove-v2` braucht Begruendung und eine explizite Ersatzentscheidung.

Der aktuelle Planungsschnitt umfasst 69 `keep`, 30 `move-library`, 85
`internalize`, 38 `replace`, 6 semantische `redefine` und 3 `remove-v2`.
Drei neue v2-Namen sind deklariert: `filter`, `key-event` und `set`.
Die neun R2-Entscheidungen sind in `config/dialect-v2-r2-decisions.json`
geschlossen und an 17 normative Familienfaelle gebunden. Dazu gehoeren die
gemeinsame nullbasierte Indexachse, das normalisierte `key-event`-Format,
`load-libs` ohne Rollback, die optionale `m65-screen`-Komposition und der
residente `(edit)`-Autoload-Einstieg. Dialekt v1 bleibt unveraendert.

Syntax ist eine eigene Vertragsachse. Spezialformen, Makros, Lambda-Marker und
Reader-Tokens werden nicht aus dem Funktionsinventar abgeleitet. AP8.3 aendert
keine Spezialform. Dialekt v1 behaelt seine historische Lambda-Listen-Syntax;
Dialekt v2 akzeptiert nackte Symbolparameter in der Form
`required* [&optional optional*] [&rest rest]`. Das Gate pinnt beide
Profilinventare und die Reader-Tokens einschliesslich Dot-Syntax exakt. Es partitioniert die 19 aus den Quellen
gelesenen oeffentlichen Makros disjunkt und vollstaendig in beibehaltene und zu
migrierende Makros. 18 davon bleiben Teil der v2-Zieloberflaeche; `do` wird
entfernt. Neue Kontrollflussformen bleiben ein eigener Block.

## Familien und Budgets

Die Reihenfolge ist fest:

1. `prelude-control`
2. `lists`
3. `strings`
4. `system-runtime`
5. `ide`

Eine migrierte Familie braucht den exakt namensgleichen
`dialect-v2-<familie>`-Semantikvertrag mit mindestens zwei Cases-Engines,
einen manifestgebundenen Differential-Receipt und eine positive Mindestbilanz.
Vor der dauerhaften Evidence-Promotion muss ein isolierter Produktlink die
residenten Kosten der Familie im echten v2-Profil messen. VMA-, Reserve- oder
Runtime-Core-Verletzungen halten die Familie auf `in-progress`; ein gruener
Hostvertrag darf diesen Produktbeweis nicht ersetzen.
Migrierte Familien muessen ein abgeschlossenes Praefix der Reihenfolge bilden;
hoechstens eine Familie darf gleichzeitig `in-progress` sein, und auch ihr
muessen alle Vorgaenger bereits als `migrated` vorausgehen.

Die Projektion wird aus dem lebenden v1-Inventar berechnet. Ein Name kostet
`len(name)+1` Namepool-Bytes. Boot- und geladener Arbeitsumfang werden getrennt
ausgewiesen, weil On-demand-Verschiebung und Internalisierung verschiedene
Effekte haben.

| Familie | Loaded Sym | Loaded Namepool | Boot Sym | Boot Namepool | Directory |
| --- | ---: | ---: | ---: | ---: | ---: |
| Prelude/Control | -16 | -108 B | -21 | -132 B | -16 |
| Lists | -13 | -96 B | -26 | -183 B | -13 |
| Strings | -7 | -79 B | -19 | -232 B | -7 |
| System/Runtime | -16 | -205 B | -23 | -296 B | -3 |
| IDE | -72 | -1295 B | -1 | -13 B | 0 |

Prelude/Control ist seit AP8.4 realisiert; seine Messung aus reproduzierbar
gebauten L65M-Profilimages trifft die Projektion exakt. Die gebundenen
Profilcontainer messen 13223 B fuer v1 und 10710 B fuer v2 (`-2513 B`). AP8.5
misst fuer Lists loaded `-13/-96 B`, Boot `-26/-183 B` und Directory `-13`;
sein Containerdelta betraegt `-3284 B`. Die Familienpromotion bleibt jedoch
bis zum bestandenen nativen v2-Produktlink gesperrt.
Diese Artefaktgroessen sind Familienbelege, keine Workbench-Footprints. Die
restlichen Werte sind Zielprojektionen, keine bereits realisierten Gewinne.
Der kumulative Ledger `config/dialect-v2-capacity-ledger.json` trennt die
deployed Lists-Familie (`-18` Directory, `-103 B` rohe Namensdaten, `-273 B`
Code, `-929 B` EXT) von der einmaligen v2-LCC-Profilinfrastruktur (`+21`,
`+827 B`, `+1076 B`, `+3128 B`). Der aktuelle Nettozustand ist deshalb `+3`
Directory, `+724 B` Namensdaten, `+803 B` Code und `+2199 B` EXT; der vertagte native
Block ist ausdruecklich nicht eingerechnet.
Baseline-
und Candidate-Manifeste listen geladene und Boot-Symbole getrennt, pinnen die
Bootmenge als Teilmenge, listen Directory-Eintraege und binden das reale
Artefakt; das Gate berechnet alle Deltas daraus neu. Der Differential-Receipt
bindet ausserdem v1-/v2-Profil, Familien-Fixture sowie die Verdict-SHAs und das
positive Aequivalenzverdikt jeder erforderlichen Engine. Jedes Engine-Verdikt
muss jeden Fall des gebundenen Fixtures exakt einmal enthalten; Teilmengen
sind ungueltig. Nach der letzten Familie wird ein SHA-gebundener
Gesamtvergleich aus allen Familienmessungen und Projektionen Pflicht. Die
Schaetzungen aus dem Redesign-Dokument bleiben
nur Rebase-Eingang, weil HW-Math und 52 private IDE/IDEX/M65D-Helfer bereits
vor AP8.3 realisiert wurden.

## AP8.4: Prelude/Control und ehrliche Aufrufe

`STRICT_ARITY` ist ein CodeObject-Flag des v2-Profils, kein globaler
VM-Schalter. Feste Funktionen akzeptieren exakt `nargs`; `&optional` kodiert
den Bereich `nargs-optional_count..nargs`; `&rest` entfernt nur die obere
Grenze. Dialekt-v1-Artefakte ohne Flag behalten im eingefrorenen v1-Profil das
historische NIL-Padding. Das v1-Produkt lehnt v2-Flags am Profilgate ab; das
harte v2-Profil verlangt `STRICT_ARITY` am Loader- und VM-Gate und fuehrt
flaglosen v1-Code nicht still aus. Das erfasst direkte,
rekursive, `funcall`- und `apply`-Aufrufe. Seit AP8.5 senken Treewalk,
nativer C-Compiler, Python-P0-Compiler und Device-LCC `&optional` im
v2-Profil auf dieses Flagfeld ab. Fehlende optionale Argumente werden mit
`nil` belegt. Default-Formen und `supplied-p` existieren nicht; deshalb sind
"nicht uebergeben" und "explizit nil" im Rumpf absichtlich nicht
unterscheidbar. Dialekt v1 behaelt sein eingefrorenes historisches Verhalten.

`/=` ist in v2 binaer. `defparameter` initialisiert bei jedem Laden neu,
`defvar` nur bei ungebundenem Symbol. `do` und der oeffentliche Name
`remainder` entfallen; `mod` behaelt Floor-Semantik. Opcode `REMAINDER`/24
bleibt aktiv und dauerhaft dekodierbar.

Das normative Fixture umfasst 19 Faelle und laeuft in getrennten v1-/v2-
Prozessen durch Treewalk und nativen C-Compiler/VM, insgesamt 76 Beobachtungen.
Jede echte Profilabweichung bindet eine aufgeloeste Decision-ID; invariante
Faelle duerfen keinen Begruendungsanker tragen. Der Arity-Fehler besitzt den
stabilen Code 48 und den Workbench-Text `wrong argument count`.

Das v1-Profil wird aus dem eingefrorenen Commit
`f6527d25e2035eae5a98dae7431d641515e2fd2e` exportiert und gegen dessen C-,
Header- und Prelude-Quellen gebaut. Das v2-Profil bindet den aktuellen
Kandidaten. Je Profil pinnt ein Build-Receipt Compiler, Defines, alle
Build-Eingaenge, Binary-SHA und Buildprofil-SHA; jedes Verdict bindet diese
beiden SHAs sowie Commit und kombinierten Prelude-SHA. Ein Schema-Check ohne
Ausfuehrung der beiden nativen Engines ist kein AP8.4-Semantikbeweis.

Ein zusaetzliches LCC-Differential pinnt seit AP8.5 29 Faelle beziehungsweise 58
Profilbeobachtungen. Es beweist, dass der v2-Device-Compiler `do`, `do*` und
den oeffentlichen Namen `remainder` nicht mehr lowern kann, waehrend
`dotimes`, `dolist`, `mod` und die historische v1-Surface erhalten bleiben.

## AP8.5: Listen und Praedikate

Die Listenfamilie migriert auf eine kleine, argumentbasierte Surface:

- `member item list [&optional test]` verwendet ohne Test `eq`, ruft einen
  Test als `(test item element)` auf und liefert den originalen Listentail.
- `assoc key alist [&optional test]` verwendet ohne Test `eq`, ruft einen
  Test als `(test key entry-key)` auf und liefert den originalen Eintrag.
- `find predicate list` und `filter predicate list` verlangen ihr Praedikat.
- `assq` und `find-if` haben in v2 keine Runtime-Bindung.
- `count predicate list` und `position predicate list` liegen zusammen mit
  den uebrigen Komfortoperationen in der on-demand geladenen `lists`-Lib.

`putf`, `adjoin`, `union`, `complement` und `sort` sind keine AP8.5-
Bestandsmigration. Sie bleiben im benannten Block `lists-v2-expansion`, bis
ihre Gleichheits-, Mutations- und Sortiervertraege separat beschlossen sind.
Migrationshinweise duerfen bis dahin nicht auf `complement` verweisen;
Negation wird direkt als Lambda ausgedrueckt, etwa
`(filter (lambda (x) (null (funcall predicate x))) list)`.

Die Reihenfolge binaerer Tests ist mit asymmetrischem `<` normativ gepinnt.
Default-`eq` wird mit runtime-frisch erzeugten, strukturell gleichen Conses
gegen versehentliche Literalpool-Identitaet abgegrenzt. `member` und `assoc`
tragen `nargs=3`, `optional_count=1` und `STRICT_ARITY`; `find`, `filter`,
`count` und `position` sind exakt zweistellig.

Unterstuetzt sind endliche Proper Lists beziehungsweise Alists aus
Cons-Eintraegen. Der abgeschlossene Block `lists-malformed-type-errors` stellt
endliche dotted Tails, Nicht-Cons-Alist-Eintraege sowie negative oder
nichtnumerische Indizes von `nth`/`nthcdr` auf den stabilen VM-Typfehlercode 38
um. Ein interner, nicht als Funktionsdesignator sichtbarer Prim-ID-58-Service
fuehrt alle vier Engines durch denselben oeffentlichen Code/Text-Kanal; eine
neue Nutzerfunktion oder ein Condition-System entsteht nicht. Zirkulaere
Listen sind weiterhin ausserhalb des Vertrags; Terminierung wird nicht
garantiert und ein Zykluscheck wird nicht bezahlt.

Das gemeinsame Fixture umfasst nach dem Upgrade 43 Faelle. Es laeuft pro Profil durch nativen
Treewalk, nativen Compiler/VM, Python-P0-Compiler/VM und Device-LCC. Direkte,
`funcall`- und `apply`-Aufrufe, Core-vs.-Library-Tier, NIL-Ambiguitaet,
Malformed-Faelle, Rueckgabeidentitaet und Arity-Grenzen werden aus derselben
Matrix abgeleitet; kein Adapter pflegt eine zweite Erwartungsliste.

Die 344 Beobachtungen und der Receipt v2 binden pro Engine das jeweilige
Profilbinary, den Preload sowie Buildprofil und Source-Commit. Getrennte Core-
und Library-Manifeste werden aus dem echten Callgraph geprueft; `requires`
enthaelt nur oeffentliche Namen. SHA-gebundene Accounting-Dateien weisen
oeffentliche, native und private Definitionen separat aus.

Der spaeter genehmigte Capability-/Carrier-Block hat die portable Surface
fuer `nreverse`, `rplaca` und `rplacd` im realen Produktlink und auf Hardware
geschlossen. Das Lists-Familienritual ist inzwischen gegen den entschiedenen
R2-Vertrag neu erzeugt: 35 Faelle, vier Engines, positive Surface-Bilanz und
der CP5-gebundene Produktnachweis sind gruen. Lists steht deshalb auf
`migrated`. Die Strings-Familie besteht anschliessend 36 Faelle in denselben
vier Engines und trifft ihre Surface-Projektion mit loaded `-7/-79 B`, Boot
`-19/-232 B` und Directory `-7`. Strings, System/Runtime und IDE sind ebenfalls
`migrated`. Am R2-Abschluss stand der Migrationsvertrag deshalb zunaechst auf
`r2-complete`; nach der spaeteren R4-Versiegelung und der vollstaendigen
R5-Verifierbindung steht er nun auf `ready-for-g5`.

Seit Lists gilt `Promotion = Versiegelung` als stehender Vertrag. Jede
kuenftige migrierte Familie muss ein unveraenderliches, im lebenden Register
SHA-gebundenes Archiv mit eigenem Offline-Verifier besitzen. Prelude/Control
ist der einzige vor dieser Doktrin abgeschlossene Bestandsschutzfall; der
Capability-/Carrier-Block wurde rueckwirkend versiegelt. Live-Gates pruefen
das Register, nicht erneut mutable historische Receipt-Referenzen. Der
Strings-Kandidat ist als `dialect-v2-strings-71e1871` versiegelt.

Der System/Runtime-Kandidat besteht 12 gezielte Faelle in vier Engines. Seine
getrennte Loaded-/Boot-/Directory-Messung trifft `-16/-205 B`, `-23/-296 B`
und `-3`; der Familiencontainer ist `3326 B` kleiner. `set` und `key-event`
sind native, registry-generierte Function-Designators. Die optionalen
Bibliotheken `fmt` und `m65-screen` bleiben ausserhalb der garantierten
Workbench-Komposition; die IDE rendert weiterhin ueber native CALLPRIMs.
Der Kandidatencommit `9f9d34b` ist als
`dialect-v2-system-runtime-9f9d34b` versiegelt und aus dem Archiv allein
verifiziert.

IDE besteht seine normative Familie in zwei unabhaengigen Compiler-/VM-
Engines und trifft loaded `-72/-1295 B`, Boot `-1/-13 B`, Directory `0` sowie
`-2004 B` Containerdelta. Der vorausgesetzte Directory-only/L65M-v2-Block ist
implementiert und sein 166-B-Bank-0-Preis vorab autorisiert. Kandidatencommit
`4c947e8` ist als `dialect-v2-ide-4c947e8` versiegelt; das Archiv verifiziert
sich mit 335 Dateien aus sich allein. Der gebundene Produktstand behaelt
127 freie Symbole, 2279 B Namepool, 32 Post-Align-Slots und 16 KiB EXT-
Headroom.

Der atomare Capability-/Carrier-Block aktiviert die v2-Prim-IDs 23
(`nreverse`), 24 (`rplaca`), 25 (`rplacd`), 28 (`%string-codes`), 29
(`%string-from-codes`) und 57 (`boundp`). Die verworfenen Builder 26/27 sind
permanente Tombstones. Die internen Codecs 28/29 werden weder exportiert noch
als Function-Designators akzeptiert. Die Blockpromotion ersetzt nicht die
getrennten Familienreceipts.

System/Runtime fuegt danach Prim-ID 58 (`%list-malformed-error`) als rein
internen Emitter hinzu. Er ist keine Dialekt-Surface und signalisiert den
bereits stabilen Code 38 (`vm: type error`); damit bleibt die Fehlertexttabelle
unveraendert.

## P0-ID-Vertrag

Opcode- und Prim-ID sind von oeffentlichen Namen getrennt. Eine
Sprachmigration darf einen Namen entfernen, ohne eine historische ID
umzunummerieren.

Der Ledger partitioniert beide 8-Bit-Raeume vollstaendig in `active`,
`tombstone` und `reserved`. Es gelten dauerhaft:

- keine Umnummerierung oder Wiederverwendung;
- `active` darf nur zu `active` oder `tombstone` werden;
- `tombstone` bleibt fuer immer `tombstone`;
- Name und Operandenformat eines Tombstones bleiben erhalten;
- Offline-Decoder und Disassembler behalten den historischen Namen.

P0 hat in beiden Profilen 36 aktive Opcodes. `dialect-v1` behaelt exakt 23
aktive Prim-IDs (0--22) und keine Tombstones. `dialect-v2` hat 57 aktive
Prim-IDs, sechs permanente Tombstones (1, 2, 26, 27, 34, 40) und reserviert
63--255. Insbesondere bleiben `REMAINDER`/24 und
`EQL`/55 aktiv und dekodierbar, solange keine spaetere ABI-Entscheidung sie
explizit tombstoned.
Opcode- und Prim-ID-Nummern sind getrennte 8-Bit-Raeume. AP8.5 laesst die
Prim-IDs 23--255 im v1-Profil unallokiert. Eine spaetere Entfernung einer aktiven ID erzeugt einen
permanenten Tombstone, keine wiederverwendbare Nummer.

Die frueher benannte Primitivnamen-Reserve ist bereits ausgeschoepft: Der
Link legt `.lisp65_boot.names` bei `$c741` mit `$17d` beziehungsweise 381 B
vollstaendig in das zurueckgewonnene Boot-Overlay. Eine weitere Verlagerung
spart deshalb 0 residente Bytes. Der benannte Wiedereroeffnungspfad ist ein
gemeinsames natives Lists-/Strings-Kapazitaetsbudget nach der lesenden
Strings-Analyse; ein spaeterer Colour-RAM-/Attic-Rebalance bleibt eine neue,
zustimmungspflichtige Architekturentscheidung.
Das historische B4-`PRINTBOOL` ist keine P0-Identitaet.

## Getrennte Architekturblocks

AP8.3 fuehrt weder Directory-only-Aufrufe noch L65M-v2, Buffer, `unload` oder
neue Kontrollflussformen ein. Abhaengigkeiten werden offen gepinnt:

- Die String-Familie verwendet im Capability-/Carrier-Block ausschliesslich
  interne atomare Slice-/Concat-Konstruktoren. Der oeffentliche
  First-Class-Buffer bleibt ein eigener, nachgelagerter Architekturblock.
- Die IDE-Familie ist nach dem abgeschlossenen Directory-only/L65M-v2-Block
  migriert.
- Directory-only/L65M-v2 ist implementiert; kanonische Stack-Guard-Bindung,
  Bank-Autorisierung, Produktlink und G2-Receipt sind geschlossen. Der
  Formatvertrag bleibt in `config/directory-only-l65m-v2-contract-draft.json`
  trotz des historischen Dateinamens normativ gebunden.
- Export-only-Interning/`require` folgt auf Directory-only/L65M-v2.
- `unload` folgt sowohl auf First-Class-Buffer als auch auf
  Export-only-Interning/`require`.
- Buffer liegt damit verbindlich vor `unload`.

Keiner dieser Bloecke darf still als Voraussetzung einer laufenden
Familienmigration eingefuehrt werden. Das Gate akzeptiert `migrated` nur, wenn
alle explizit benoetigten Bloecke den Zustand `completed` tragen.
`completed` ist kein freies Statusbit: Blockvertrag, G2-Receipt und dessen
nichtleere, SHA-gebundene Evidence-Liste sind Pflicht.

## Profilumschaltung

Die Workbench-Umschaltung ist eine G5-Entscheidung, kein Buildflag.
`config/dialect-v2-g5-matrix.json` pinnt die konkreten Make-Ziele und
Erwartungen fuer:

- vollstaendige Workbench-UX;
- vollstaendige Persistenzmatrix;
- Runtime Export `clean`, `truncated`, `bitflip` und `build-id-mismatch`.

Die Evidenz bindet Profil-ID, Migrations- und Dialektvertrag, Candidate-Manifest,
Build-ID, Source-Commit, Familienmessungen und physische Cycle-IDs. Jeder
Matrixfall bindet zusaetzlich ein formatspezifisches Evidence-JSON samt
nativem Receipt und Rohartefakten. Runtime-Receipts werden erneut durch den
vorhandenen Runtime-Export-Hardware-Oracle verifiziert; Workbench-Receipts
werden durch einen eigenen, SHA-gebundenen und formatspezifischen Verifier aus
ihren Rohbelegen rekonstruiert. Dieser Workbench-Verifier ist im
globalen R5-Stand eigenstaendig implementiert und SHA-gebunden. Vor seiner
ersten Hardwareverwendung lehnt er pro Workbench-Domaene je ein manipuliertes
Artefakt, ein semantisch manipuliertes Rohprotokoll und eine falsche
Produktidentitaet nachweislich ab. Produktidentitaet und Test-Closure besitzen
getrennte SHA-Inventare; Runtime Core bleibt `internal-proof-only` und darf nie
Produktmitglied werden. Der Vertrag steht deshalb auf `ready-for-g5`. Die vier Runtime-Export-Faelle
brauchen vier verschiedene Cycle-IDs; unbenutzte oder nicht deklarierte IDs
sind unzulaessig. Der
Candidate bindet sein Profil, beide Vertrags-SHAs und alle Auslieferungsdateien.
Die v2-Surfaces werden aus den Definitionseintraegen der gebundenen Manifeste
abgeleitet, nicht aus einer zweiten Namensliste. Ohne diese Bindung bleibt
`config/dialect-profile-selection.json` fail-closed auf Dialekt v1.

Vor dem ersten globalen R5-Hardwarefall ist der finale v2-Dialektvertrag nun
materialisiert. `config/dialect-v2-contract.json` bindet den R4-Source-Commit,
den aktuellen Migrationsvertrags-SHA und das kanonische Definitionsmanifest
mit 126 oeffentlichen Namen. Die R5-Fall-Receipts binden seinen SHA bereits;
die Profilselektion konsumiert denselben Vertrag erst nach bestandenem G5.
Die Ausfuehrungsschicht transformiert Rohbelege ausschliesslich in die hier
bereits definierten nativen und aeusseren Fall-Receipt-Formate und verifiziert
beide Schichten sofort. Ein gruenes Produktergebnis bei roter Receipt-Kette
bleibt als Harness-Befund von einem Produktfehler unterscheidbar und kann nach
einem reinen Closure-Fix offline neu verpackt werden.

Normale Workbench- und Runtime-Export-Ship-Gates akzeptieren keine internen
v2-Stagingprofile. Die Marker `abi_profile=dialect-v2` und
`profile_id=v2-capability-candidate` (beim Runtime-Export auch der gleichwertige
Schluessel `profile`) werden vor den regulaeren Paket- und Hashpruefungen
abgelehnt. Eine Freigabe entsteht nicht durch den Marker selbst, sondern erst
durch den vollstaendig validierten Profilwechsel in
`config/dialect-profile-selection.json`: aktives `dialect-v2`, Status
`passed-g5` und die dort SHA-gebundene G5-Evidence muessen gemeinsam gueltig
sein. Bis dahin bleiben solche Artefakte interne Evidence und koennen weder als
normaler Ship noch ueber dessen Promotionpfad ausgeliefert werden.
