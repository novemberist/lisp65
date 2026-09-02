# v2 Capability-/Carrier-Block

Status: Checkpoint 5 ist mit 14/14 Hardwarefaellen und vier Power-Cycles
geschlossen; die eine atomare Carrier-Promotion ist erfolgt. Normative Quelle
ist `config/v2-capability-carrier-block.json`; dieses Dokument erklaert den Schnitt.

## Ziel und Grenze

Der Block migriert die Listen- und String-Capabilities atomar in das v2-Profil.
Es gibt genau eine Promotion. Teilpromotionen, ein Mischprofil und eine
zwischenzeitlich oeffentliche Capability-Surface sind ausgeschlossen.

Der freigegebene Profil-Split ist keine zweite Promotion und keine
Release-Reihenfolge. Runtime-Core darf den v2-Vertrag intern beweisen, bleibt
aber nicht shippbar und hat weder Release- noch Familienfreigabeeffekt.
Workbench-v2 ist das einzige Releaseprodukt. Linkbudget und interne
Workbench-plus-Runtime-G5-Matrix sind geschlossen. Die einzige aktive
Arbeitslinie ist nun die sequenzielle Dialekt-v2-Familienmigration; neue
AP8-Bloecke brauchen weiterhin einen eigenen expliziten Vertrag.

"Carrier" bezeichnet ausschliesslich die heute residenten C-Semantikpfade
`apply`, `eval_vm_apply` und `eval_vm_bridge`. Es entsteht kein ladbares
Carrier-Artefakt, kein Transportformat und kein Runtime-Plugin-System. Die
link-time Registry verwendet direkte statische Verzweigungen; pro Aufruf gibt
es weder eine Funktionszeigertabelle noch dynamische Registrierung. Das
produktneutrale Cut-Praedikat `LISP65_V2_SERVICE_REGISTRY_CLOSED` darf erst nach
dem jeweiligen Produktinventar gesetzt werden. Es schaltet keine Workbench-
Services frei.

## Fuenf Checkpoints

1. **Vertrag und Surface-Fixtures.** Der maschinenlesbare Vertrag, die direkte,
   `funcall`- und `apply`-Surface sowie die v1/v2-Differenzen sind gebunden. Der
   bestehende Carrier bleibt unveraendert aktiv.
2. **Registry und Null-Miss-Zielgate.** Die link-time Service-Registry ist
   vorhanden. Unbekannte Services liefern einen Null-Miss. Zaehler und Zielgate
   sind vorbereitet; der Carrier bleibt der Rueckfallpfad.
3. **Interne Capabilities.** Prim-IDs 1/2 sind im v2-Profil Tombstones. Native
   Listen- und String-/Span-DMA-Semantik ist intern vollstaendig, aber nicht
   promotet. Der Carrier bleibt aktiv, damit Registry-Misses beobachtbar sind.
4. **Zero Miss und Carrier-Ausbau.** Ein echter Null-Miss-Zaehlerstand von null
   hat das Entfernen der drei Carrier-Funktionen und der zwei Hook-Definitionen
   freigegeben. String-/Span-DMA besteht Bounds-, Fault- und Atomizitaetsgates.
5. **Produktabnahme.** Reale Workbench- und Runtime-Core-Links, aktualisiertes
   Kapazitaetsledger und die vollstaendige G5-Hardwarematrix muessen bestehen.
   Erst danach darf die einzige Promotion stattfinden.

Jeder Checkpoint besitzt ein eigenes `check-host`-Ziel und benoetigt spaeter ein
SHA-gebundenes Receipt. Ein `pending` Checkpoint ist absichtlich rot, wenn sein
Checkpoint-Ziel direkt aufgerufen wird. Der normale Vertragscheck prueft den
Plan, ohne kuenftige Implementierungsevidenz vorzutaueschen.

## Harte Budgets

- Workbench Runtime-Overlay-VMA: hoechstens `$c356`.
- Workbench Post-Boot-Reserve: mindestens 1536 Byte.
- Runtime-Core Post-Boot-Reserve: mindestens 8192 Byte.
- Deploytes Bank-0-Netto: strikt kleiner als 0 Byte. Ein Nullsaldo reicht nicht.
- Nur reale gelinkte Produkt-ELFs duerfen die Promotion finanzieren; Schaetzungen
  und isolierte Objektmessungen sind Diagnose, keine Abnahme.

Layout, residente Insel, Slotzahl und Kapazitaets-Caps sind keine
Finanzierungsquellen. Ihre aktuellen Vertrage sind im Block per SHA gebunden.

## Registry und Prim-IDs

Registry-Aufloesung geschieht link-time und fuehrt auf direkte statische
Branches. Vor Checkpoint 4 faellt ein Registry-Miss auf den bestehenden Carrier
zurueck. Checkpoint 4 verlangt nachweislich null Misses, bevor dieser Pfad
entfernt wird.

Prim-ID 1 (`string->list`) und Prim-ID 2 (`list->string`) bleiben fuer alte
Artefakte dekodierbar. Im v2-Profil sind sie nicht wiederverwendbare Tombstones
und werden als ungueltige Primitive abgelehnt. Der Opcode- und der Prim-ID-Raum
sind getrennte Nummernraeume.

Das v2-Profil belegt 23=`nreverse`, 24=`rplaca`, 25=`rplacd`,
26=`%string-slice`, 27=`%string-concat-list`, 28=`%string-codes` und
29=`%string-from-codes`. Die Listenprims sind
oeffentliche Funktionsdesignatoren mit exakter Aritaet 1/2/2. Die Stringprims
sind interne Emitter-Capabilities mit exakter Aritaet 3/1/1/1; sie werden weder
exportiert noch als Funktionsdesignator angeboten.

Die 14 statischen Workbench-Services belegen 30--33, 35--39 und 41--45.
Prim-ID 34 bleibt als `%save-staged` und Prim-ID 40 als `number->string`
dekodierbar; beide sind nach ihren Bytecode-Verlagerungen nicht
wiederverwendbare v2-Tombstones. Die elf stabil unterscheidbaren
Error-Services belegen 46--56. `boundp`, der interne Listenfehlerkanal, `set`
und `key-event` belegen 57--60; `peek`/`poke` belegen 61/62. Ab 63 ist der
Prim-ID-Raum wieder reserviert.
Code 59 und Prim-ID 56 gehoeren
`%lcc-error-invalid-parameter-list`; alle vier Engines fuehren den
ungueltigen Parameterlistenfall durch `lcc-compile-obj` zu exakt diesem
Code/Sentinel. Die Klartexttabelle dedupliziert den gemeinsamen Text.

## Checkpoint-4-Nachweis

Das v2-Staging-Set liefert 335/335 zum v1-Profil identische Beobachtungen. Sein
Inventar hat nach den Prim-34/40-Retirements bei 465 `CALLPRIM`s und
1801 Directory-Aufrufen weder Misses noch Tombstone-Aufrufe und klassifiziert
exakt 3+14+11=28 Ziele. Der native
Manifest-Harness materialisiert das reale residente v2-Blob und belegt neben
Code 59 auch `eval`, `funcall` und `apply` mit Ergebnis 42.

Der Cut ist ein hartes Profil, kein frei kombinierbares Feature-Flag. Fehlt
eine seiner sechs Voraussetzungen, darunter die produktneutral nachgewiesene
Registry-Schliessung, bricht die Kompilierung ab. Workbench bindet zusaetzlich
ihre 28 Serviceziele; Runtime-Core beweist getrennt null Workbench-IDs. Im gelinkten
ASAN/UBSAN-ELF fehlen `apply`, `eval_vm_apply`, `eval_vm_bridge`,
`vm_treewalk_apply` und `vm_treewalk_call`; `vm_native_apply` und `vm_run`
muessen vorhanden sein. CP4 aendert weder Slot-, Insel- noch Bank-0-Layout.

## String-Codecs und vertagter Builder

Der Promotionsblock behaelt nur die internen Code-List-Codecs 28/29. Der
oeffentliche `substring`- und `string-append`-Pfad baut eine gerootete Codeliste
und materialisiert sie ueber den bestehenden Streaming-Codec. Ein OOM setzt
den VM-Fehler und publiziert kein Ergebnis; transaktionales Arena-Rollback und
Span-DMA sind ausdruecklich nicht Teil dieses Vertrags. Die bereits in
Staging-Evidenz verwendeten Builder-IDs 26/27 bleiben dauerhaft dekodierbare,
nicht wiederverwendbare Tombstones.

Ein neuer atomarer Builder, Span-DMA, Pinnen, Freeze und First-Class-Buffer
bilden den benannten 1.1-Block `buffer-and-string-construction`. Er erhaelt neue
Prim-IDs aus dem dann aktuellen Reserved-Bereich. Damit wird die Garantie
verschoben, ohne den jetzigen Promotionsblock um eine ungeklaerte Buffer-ABI zu
erweitern.

## Rueckbau und Haltbarkeit

Die Checkpoints 1 bis 4 sind einzeln rueckbaubar und einzeln gegatet:

1. Vertrag/Fixtures ohne Runtime-Aenderung.
2. Registry zurueck, Carrier bleibt aktiv.
3. Interne Capabilities/Tombstones zurueck, Carrier bleibt aktiv.
4. Carrier-Ausbau als eine Aenderung zurueck, gebunden an den Zero-Miss-Beweis.

Die Haltbarkeit folgt derselben Staffelung: maschinengepruefte Fixtures,
link-time Registry mit Zaehlergate, Differentialtests mit Carrier-Backstop und
schliesslich Link-Audit fuer Zero Miss und Carrier-Abwesenheit. G5 ist keine
fuenfte Teilpromotion, sondern die letzte Sperre vor der einzigen Promotion.

## Bedienung

```sh
make v2-capability-carrier-contract-check
make v2-capability-carrier-check-host-1
make v2-capability-carrier-check-host-2
make v2-capability-carrier-check-host-3
make v2-capability-carrier-check-host-4
make v2-capability-carrier-check-host-5
make v2-capability-carrier-internal-g5-hw-package
```

Alle fuenf Checkpoints sind durch SHA-gebundene Receipts und Live-Gates
geschlossen. Checkpoint 5 bindet reale Workbench-/Runtime-Core-Links,
Kapazitaetsdelta und die vollstaendige interne Hardwarematrix. Die einmalige
Promotion betrifft nur das weiterhin Ship-gesperrte v2-Stagingprofil; globale
Profilumschaltung und Release bleiben ausgeschlossen.

Der interne G5-Packer bindet jedes von einem der 14 Faelle verwendete PRG,
Blob, Overlay-Image und D81 per SHA. Die Vereinigungsmenge der Case-Artefakte
plus der expliziten Policy-/Verifier-Artefakte muss exakt der Kandidatenmenge
entsprechen; fehlende und fremde Artefakte blockieren bereits den Skeleton-Bau.
Runtime-Core verwendet ein eigenes nicht shippbares v2-Hardwarepaket. Seine vier
Phasen brauchen vier verschiedene bestaetigte Power-Cycle-IDs. Ein Retry ist
nur einmal, vor jeder semantischen Ausfuehrung und Medienmutation, mit frischer
Evidenz und frischer Wegwerf-D81 erlaubt; beide Versuche bleiben im Receipt.

## CP5 Workbench-Symboldifferenz

Der erste reale Workbench-Produktlink bleibt ein harter CP5-Blocker. Die
unveraenderte v1-Baseline endet bei `bss_end=$c34e`, startet das Runtime-Overlay
bei `$c350` und behaelt 1800 B Post-Boot-Reserve. Der v2-Cut erreicht bereits
vor einem Produkt-ELF `bss_end=$d094`: 148 B ueber der physischen Bank-0-Grenze,
3398 B ueber dem v1-Floor und 3392 B ueber dem gepinnten VMA-Maximum `$c356`.

`config/v2-workbench-symbol-diff-policy.json` pinnt diese LTO/ICF-
Produktmetrik getrennt von der Namensattribution. Letztere vergleicht reale
MOS-Relocatable-ELFs aus `-Oz -fno-lto`-Objekten. Ihre Werte erklaeren
Eigentuemerschaft, sind wegen fehlender LTO-, ICF- und Section-GC-Effekte aber
keine Produktfootprints. Die groessten positiven Indikatoren sind
`eval_v2_workbench_service` (2273 B), `vm_native_apply` (1305 B), der Zuwachs
in `vm_callprim` (1182 B), `str_v2_concat` (950 B) und `str_v2_slice` (812 B).
Dem steht insbesondere der weggefallene `apply`-Carrier mit 3677 B gegenueber.

Netto-negativ verlangt mindestens 3399 B real gemessenen Reclaim. Fuer die
Planung gilt pessimistisch 4096 B; Attributionsschaetzungen duerfen nie
promoten. Falls dieser Wert nicht layoutneutral erreicht wird, ist das bereits
vereinbarte Entscheidungsmenue: (a) neue Layoutentscheidung fuer Insel plus
Slice-Cap, (b) De-Residentisierung kalter Capability-/Service-Pfade oder (c)
interner Runtime-Core-Beweis. Der freigegebene Schnitt kombiniert (b) als
alleinigen Release-Pfad mit (c) als releasewirkungsloser Beweissequenz.

Der einmalige layoutneutrale Versuch ist inzwischen geschlossen. Die gemeinsame
String-Transaktion spart isoliert 922 B, der array-basierte VM-Native-Call 303 B;
im gemeinsamen LTO/ICF-Link bleiben wegen ueberlappender Optimierungen 1051 B
realer Reclaim. Der v2-Floor liegt damit weiterhin 2347 B ueber v1 und verfehlt
das 3399-B-Minimum um 2348 B. Das Diagnose-ELF endet bei `bss_end=$cc77` und
passt damit zwar physisch in Bank 0, verletzt aber das Runtime-Overlay-VMA-Limit
`$c356` um 2338 B. Nach dem gepinnten 1450-B-Runtime-Stack verbleiben -546 B
Post-Boot-Reserve statt 1536 B; das Defizit betraegt 2082 B.

Der versuchte Tabellen-Dispatch wurde nach einem realen MOS-Wachstum von 61 B
verworfen. STRICT_ARITY, String-Atomizitaet, Inselinventar, Slotbudget und Layout
blieben unangetastet. Der Einmalversuch darf nicht mit weiteren lokalen
Varianten fortgesetzt werden; die naechste Bewegung ist eine ausdrueckliche
Auswahl aus dem bereits gepinnten Architekturmenue.

Die Layoutoption (a) ist verworfen: 932 B Insel-Headroom plus rund 370 B aus
einem kleineren Slice-Cap ergeben nur etwa 1302 B. Das ist weniger als sowohl
der verbleibende VMA-Ueberzug von 2338 B als auch das Reservedelta von 2082 B.
Den AP4-Freeze zu brechen, ohne den Link zu schliessen, ist damit unzulaessig.

## CP5 String-Caps-Produktlink

Der freigegebene reine Entfernungsschnitt tombstoniert die unbenutzten Builder
26/27 und behaelt die Codecs 28/29. Vier-Engine-Differentiale, GC-/OOM-Gates und
ein Workload-Receipt decken den neuen Code-List-Pfad. Der vollstaendige
stack-guarded Workbench-v2-Link erreicht `runtime_overlay_vma=$c0fa`, 604 B
unter dem Limit `$c356`, sowie 2397 B Post-Boot-Reserve. Das harte Minimum von
1536 B wird um 861 B uebertroffen; gegen die akzeptierte v2-FASL-Baseline
`$c9d0` sinkt der Floor um 2262 B. Slot-, Insel- und Layoutdelta bleiben null.

Der fruehere Seed-/Stub-Sweep hatte 2676 B und damit 1140 B ABI-1.1-Headroom
prognostiziert. Im finalen Produktgraph kostet der Stack-Guard-/Produktanteil
279 B mehr. Die explizite Architekturentscheidung pinnt CP5 auf die
autoritativen 2397 B des vollen Links. Der Unterschied ist als pessimistischer
Korrekturfaktor fuer kuenftige Stub-Projektionen gebunden. Die verbleibenden
861 B sind bis zur G5-Abnahme gebankt und danach ausschliesslich postenweise
nach einem eigenen 1.1-Probelink ausgebbar. Der maschinenlesbare Bericht
`string-caps-cp5-product-link-report.json` bindet Entscheidung,
Produktartefakte und Messwerte per SHA. Der darauf gestartete erste G5-Lauf ist beim
ersten Persistenz-Create rot geworden: Der carrier-freie VM-Apply-Pfad deckt
den in M65D dynamisch verwendeten nativen Funktionsdesignator `boundp` nicht
ab. Dieser Fund hat CP4 formal wiedereroeffnet. Der Abschluss ist nicht eine
weitere Literalsuche, sondern `config/v2-native-function-registry.json` als
Wahrheitsquelle fuer den generierten Apply-Dispatch und die generierte
Primitive-mal-direct/funcall/apply-Matrix. Seit dem G6-Fund vom 14. Juli ist
diese Registry die einzige Klassifikationsquelle fuer alle vier Sichten:
CALLPRIM, Apply-Designator, `function-kind` und Compile-REPL. Sie partitioniert
alle 57 aktiven v2-Prim-IDs in 23 oeffentliche Allsicht-Namen und 34 explizit
sichtbeschraenkte Services mit Begruendung. Vier arithmetische Fold-Namen und
zwoelf Opcode-Designatoren ergaenzen die oeffentliche Designator-Closure; die
Compiler-Intrinsic-Aliase `not`/`null` sind als eigene sichtbeschraenkte Klasse
registriert. Der generierte Kreuzreport muss
in allen Missing-Feldern leer bleiben. Der C-Compile-Dispatch und der
Python-v2-Compiler werden aus der Registry erzeugt; C-VM, LCC und
`function-kind` werden dagegen gegatet.

Die generierte Matrix enthaelt 207 Faelle beziehungsweise 828 Beobachtungen:
39 oeffentliche Namen ueber direct/funcall/apply und `function-kind`, dazu 17
`peek`/`poke`-Negativklassen ueber alle drei Aufrufwege. `peek` hat exakt zwei,
`poke` exakt drei Argumente. Adresse-Highbyte, Adresse-Lowbyte und Schreibwert
sind Fixnums im geschlossenen Bereich 0--255; weder Typen noch Werte werden
implizit maskiert. Ein als `T_PRIM` installierter, aber in der Registry vom
Apply-View ausgeschlossener interner Service endet bei Designator-Verwendung
mit `LISP65_ERR_VM_PRIMITIVE_NOT_DESIGNATOR`. Nicht installierte interne Namen
bleiben davon getrennt und folgen dem normalen Undefined-/Type-Error-Pfad.

Der neue volle stack-guarded Link endet bei `runtime_overlay_vma=$c1d8`, 382 B
unter `$c356`, und bei 2175 B Post-Boot-Reserve. Gegen den alten `$c0fa`-/2397-B-
Link kostet die strukturelle Korrektur 222 B VMA beziehungsweise 222 B Reserve;
639 B ueber dem 1536-B-Hard-Minimum bleiben bis G5 gebankt. CP5 bleibt 4/5,
bis die komplette Matrix auf genau diesem Binary von vorn bestanden ist. Das
alte Failure-Receipt bleibt historischer Trigger und ist keine wiederverwendbare
Teilabnahme.

Der frische G5-Neustart auf Commit `4a11f21` bestaetigt den Designatorabschluss
auf echter Hardware. Der zuvor rote erste Persistenz-Create liefert
`(t nil bytecode)`; Read, zweites Create, Replace, Remount,
Higher-Order-Persistenz und Reset/Reload bestehen ebenfalls. G5 stoppt dennoch
im dritten ausgefuehrten Workbench-Fall: Nach IDE und IDEX stehen 682/720
Symbole, und das lazy M65D kann nicht mehr registriert werden. Der umgekehrte
Kontrolllauf IDE -> M65D -> IDEX verschiebt den Fehler nur auf IDEX und endet
bei 685/720. Das ist ein eigener Produkt-Kompositions-/Kapazitaetsbefund, kein
Carrier-Cut- oder Medienfehler. Das Receipt
`g5-restart-symbol-capacity-failure-receipt.json` bindet Kandidat, Plan,
Hardwarepaket und Rohbelege. CP4 bleibt geschlossen, CP5 bleibt 4/5, 639 B
bleiben gebankt, und nach einem autorisierten Fix beginnt G5 erneut von vorn.

Die autorisierte Schliessung behaelt Persistenz fuer alle Komfortstufen. Eine
Privatisierungsprobe ueber 27 weitere M65D-/IDEX-Helfer gewinnt null Symbole:
25 rel8-Ueberlaeufe und zwei Codeobjekte ueber 255 B machen die etablierte
Inlining-Mechanik hier unbrauchbar. Der echte frische Wasserstand nach
IDE+IDEX (677 Symbole, 9111 Namensbytes, 533 Directory-Eintraege) kalibriert
das damalige Manifestmodell mit +5/+51/0. Seit `peek` und `poke` als LCC-
Prim-Literale auch im statischen Manifest erscheinen, lautet dieselbe
Hardwarekalibrierung +3/+41/0: Beide Namen waren schon vorher durch
`eval_init` vorhanden und duerfen nicht ein zweites Mal gezaehlt werden.

`v2-workbench-library-composition-check` bildet Resident+IDE+IDEX+M65D nun
permanent aus ihren Manifesten. Der neue Pin `MAX_SYM=752`, `NAMEPOOL=10208`,
`VM_DIR_MAX=608`, `SYMPOOL_EXT_OFF=$c680` endet bei 571 Directory-Eintraegen
(576 post-align, 32 frei), 713 Symbolen (39 frei) und 9718 Namensbytes (490
frei). Ein exakter Scanbesuchszaehler plus fuenf Host-Timingpunkte bestaetigt
lineares GC-Wachstum (R² > 0,9999); Zielzyklusautoritaet wird daraus nicht
abgeleitet.

Der reale volle Link kostet gegen den vorigen Kandidaten 84 B und endet bei
`runtime_overlay_vma=$c22c` sowie 2091 B Reserve. Die Ausgabe ist als
Release-Blocker-Ausnahme protokolliert; 555 B bleiben gebankt. Das Receipt
`workbench-library-composition-capacity-receipt.json` bindet Probe,
Hardwarekalibrierung, Manifestgate, GC-Nachweis und Produktlink. CP4 ist damit
hostseitig wieder geschlossen. Die anschliessende produktidentische Matrix ist
mit allen 14 Faellen und vier physischen Power-Cycles bestanden. Ihr
deterministisches Archiv und der Offline-Verifier bilden die CP5-Evidenz; die
555 B bleiben fuer ABI 1.1 reserviert und nur postenweise per Probe ausgebbar.

```sh
make v2-workbench-symbol-diff-check
make v2-workbench-symbol-diff-live \
  V2_WORKBENCH_ATTR_BASELINE_ELF=/path/to/v1-attribution.elf \
  V2_WORKBENCH_ATTR_CANDIDATE_ELF=/path/to/v2-attribution.elf
```
