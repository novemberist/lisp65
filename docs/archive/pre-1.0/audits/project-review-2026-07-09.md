# Projekt-Review 2026-07-09

Status: technische Bestandsaufnahme und Ausgangsbasis fuer die Sanierung.
Der daraus abgeleitete Arbeitsplan steht in
[`project-realignment-plan-2026-07-09.md`](project-realignment-plan-2026-07-09.md).

Dieses Dokument bewertet den aktuellen Workbench-Produktpfad, nicht die
historischen C64-/Prelude-Profile. Laufende, nicht eingecheckte M7-/IDE-Arbeit
wurde als aktueller Integrationsstand betrachtet, aber nicht mit dem Zustand von
`origin/main` gleichgesetzt.

## Kurzurteil

lisp65 ist kein ungeordneter Prototyp. Das Projekt hat ein nachvollziehbares
Zielbild, eine grundsaetzlich tragfaehige Schichtenarchitektur und eine fuer ein
Bare-Metal-/Retro-System ungewoehnlich starke Beweisinfrastruktur. Besonders
wertvoll sind die explizite Bytecode-ABI, Differentialtests, Footprint-Gates und
echte Hardwaretests.

Der Engpass ist inzwischen nicht mehr fehlende Funktionalitaet, sondern
Systemkontrolle. Produktcode, Speicherlayout, Buildprofile, Oracles und
Releaseprozess sind so eng gekoppelt, dass kleine Features wiederholt mehrere
Kapazitaetsgrenzen verschieben. Gleichzeitig liegen an der nativen
Eingabegrenze konkrete Korrektheits- und Speichersicherheitsfehler. Weitere
Featurearbeit wuerde diese Lage verschaerfen.

**Verdikt:** Der Workbench-MVP ist als technisch beeindruckender Prototyp
belastbar, aber noch nicht als robustes, reproduzierbares Produkt. Vor neuen
Sprach-, IDE- oder Hardwarefeatures braucht das Projekt eine begrenzte
Sanierungsphase mit Fokus auf native Sicherheit, harte Produktgates,
Speicherreserve und Buildkonsolidierung.

## Bewerteter Scope

| Bereich | Aktueller Inhalt |
| --- | --- |
| C-Kern | Objektmodell, GC, Symboltabelle, Reader/Printer, VM, Eval-/Compiler-Bruecken, F011-I/O, Screen, REPL |
| Lisp-Schicht | Stdlib, selbstgehosteter `lcc`, IDE, Persistenz- und Compile-Workflows |
| Host-Werkzeuge | Referenzinterpreter, P0-Compiler/VM, Artefaktgeneratoren, Budget- und Driftpruefer |
| Produkt | Workbench-PRG, externes Stdlib-Blob, D81 mit IDE und Arbeits-/Compile-Slots |
| Verifikation | Host-Oracles, Differentialtests, C-Smokes, Footprint-Gates, Emulator-/HW-Harnesse |
| Planung | Status, Decision Log, Strategie-, Audit- und Hardwaredokumente |

Das langfristige Ziel umfasst zusaetzlich CL-nahe Sprache, Emacs-nahe
Editorergonomie, Runtime-Export und BASIC-10-aehnliche Grafik-/Sound-Libraries.
Dieser Gesamtscope ist sinnvoll als Vision, aber nicht als naechster gemeinsamer
Meilenstein. Der aktuelle Ressourcenstand traegt zunaechst nur einen
Stabilitaets- und Konsolidierungsmeilenstein.

## Staerken

### S1: Tragfaehige logische Schichtung

Der kleine native Kern, Lisp/Bytecode fuer wachsende Funktionalitaet und
On-Demand-Libraries sind fuer den MEGA65 die richtige Richtung. Bank 0 bleibt
der heisse Maschinenraum; Sprache, IDE und Libraries koennen ausserhalb davon
wachsen. Die Konsolidierung auf eine sichtbare Workbench statt mehrerer
Nutzerprofile war ebenfalls richtig.

### S2: Explizite Vertraege

Bytecode-ABI, Closure-Vertrag, Load-/Disk-Lib-Formate und Kern-vs.-Library-Grenze
sind dokumentiert. Driftpruefer und Golden Vectors machen viele sonst implizite
Annahmen maschinenlesbar.

### S3: Breite Beweisinfrastruktur

Treewalk, C-Compiler, Lisp-`lcc`, Python-P0-Modell und C-VM werden auf mehreren
Ebenen gegeneinander geprueft. Dazu kommen Budgetreports, D81-Differenzmodelle,
Dry-Runs und echte Hardware-Sessions. Diese Infrastruktur ist das groesste
Kapital des Projekts und muss erhalten werden.

### S4: Messbasierte Hardwarearbeit

Viele Entscheidungen beruhen auf realen PRG-Enden, Stack-Gaps, DMA-Exposure,
JTAG-Countern und Hardware-Smokes. Das Projekt dokumentiert auch gescheiterte
Varianten und bekannte offene Faelle statt sie zu verstecken.

## Priorisierte Befunde

### F1 - Kritisch: Native Reader-Eingabe kann den Rootstack ueberschreiben

`GC_PUSH` schreibt ungeprueft nach `gc_rootstack[gc_rootsp++]`. `read_list`
belegt pro Verschachtelung zwei Slots und ruft den Reader rekursiv, ohne vorher
Kapazitaet oder Tiefe zu pruefen. Bei `GC_ROOTS=128` reicht eine 70-fach
verschachtelte Form fuer einen reproduzierbaren globalen Buffer-Overflow.

Ein Host-Probe gegen den unveraenderten C-Reader lieferte unter ASan:

```text
ERROR: AddressSanitizer: global-buffer-overflow
WRITE of size 2 in read_list
0 bytes after global variable 'gc_rootstack' of size 256
```

Auf dem MEGA65 bedeutet das keine saubere Fehlermeldung, sondern potenziell
stille Speicherbeschaedigung, falsche Ergebnisse oder Haenger. Betroffen sind
alle Pfade, die native Source lesen: REPL, `load` und Compile-/Eval-Bruecken.

### F2 - Hoch: Der native Reader erfuellt den deklarierten Reader-Vertrag nicht

`lib/tests/mvp-reader-cases.json` verlangt Fehler fuer ungeschlossene Listen,
ungeschlossene Strings und ungueltige dotted pairs. Diese Cases laufen gegen
einen separaten Python-Reader. Der C-Reader:

- akzeptiert EOF in einer Liste als gueltiges Listenende;
- akzeptiert weitere Tokens nach einem dotted tail;
- akzeptiert ungeschlossene Strings;
- behandelt ein unerwartetes `)` als `NIL`;
- implementiert die im Host-Vertrag getesteten String-Escapes nicht;
- beendet Tokens nach 31 Zeichen, konsumiert den Rest aber nicht und erzeugt
  daraus ein zweites Token.

Der native Probe bestaetigte alle sechs Abweichungen ohne gesetzte
Fehlermeldung. Damit prueft der aktuelle Host-Reader-Guard eine Zielspezifikation,
nicht die Produktimplementierung.

### F3 - Hoch: Der Produktpin besitzt keine nachhaltige Reserve

Der am 2026-07-09 gemessene Workbench-Stand liegt gleichzeitig an mehreren
Grenzen:

| Budget | Messwert |
| --- | ---: |
| PRG-Ende | `0xc0bc` bei Limit `< 0xc0c0` |
| Stack-Gap | 1612 B bei Mindestbedarf 1450 B |
| Reserve ueber Mindest-Stack-Gap | 162 B bei sichtbarem Ziel 1024 B |
| VM-Codebuffer | 2 B Headroom |
| EXT-Codefenster nach IDE-Load | 130 B Headroom |
| Directory nach Alignment | 8 Slots Headroom |
| Laufzeitsymbole | 26 Slots Headroom |
| Namepool | 137 B Headroom |
| Disk-Dateifenster | 325 B Headroom |

Das Footprint-Gate bleibt gruen, weil die harte Mindestreserve fuer dieses
Profil `0` ist. `LISP65_STACK_GUARD` ist im Produkt nicht aktiv. Der sichtbare
1-KB-Reservewert ist nur ein Reportziel und kein Abnahmekriterium.

Diese Lage erklaert die wiederholten Verschiebungen von String-Arena,
Diskfenster, Namepool, Symboltabellen und Directory-Caps. Das ist fuer einen
MVP-Pin vertretbar, aber keine Basis fuer weiteres Featurewachstum.

### F4 - Hoch: Gate-Namen und tatsaechliche Abdeckung stimmen nicht ueberein

`workbench-gate` haengt nur vom Workbench-Footprint-Report ab. Das
`workbench-persistence-gate` prueft IDE-Lib, Budgets, dynamische Host-Exposure
und einen Deploy-Dry-Run, aber keine echte Emulator- oder Hardwareausfuehrung.
`make check` ist ein sehr breites Sammelziel, bricht jedoch beim ersten Fehler
ab und vermischt Produkt-, Referenz-, Generator-, Ship- und Dry-Run-Aufgaben.

Folgen:

- Ein "gruenes Workbench-Gate" ist kein vollstaendiger Produktnachweis.
- Ein Ship-Paket kann erzeugt werden, obwohl `make check` rot ist.
- Die Kategorien schnell, produktnah, Emulator und echte Hardware sind fuer
  Entwickler und Releases nicht eindeutig getrennt.

### F5 - Hoch: Der aktuelle Integrationsstand ist rot, aber ship-faehig

Auf dem vorliegenden, nicht eingecheckten Arbeitsstand liefen
`make workbench-gate` und `make workbench-persistence-gate` gruen. Das volle
`make check` brach dagegen in `bytecode-p0-stdlib-check` ab, weil vier neue
IDE-Definitionen nicht in allen betroffenen Suite-Profilen klassifiziert waren:

```text
%ide-dir-entry-index
%ide-dir-write-name
%ide-disk-rename-tmp
%ide-save-new-source
```

Der Omitted-Defun-Guard arbeitet hier korrekt. Das Prozessproblem ist, dass
`mvp-ship` trotzdem Artefakte erzeugt. WIP und Releasekandidat sind technisch
nicht ausreichend getrennt.

### F6 - Hoch: Ship-Artefakte sind nicht eindeutig reproduzierbar

Das Ship-Manifest zeichnet Commit, Dateinamen und Groessen auf, aber nicht:

- ob der Arbeitsbaum dirty war;
- den Diff- oder einen Source-Tree-Hash;
- SHA-256 fuer PRG, Blob und D81;
- llvm-mos-, Host-C-, Python- und `c1541`-Versionen;
- das vollstaendige aufgeloeste Produktprofil als eigenes Artefakt;
- das Ergebnis des verpflichtenden Produktgates.

Im Review wurde aus einem stark veraenderten Arbeitsbaum ein Ship-Paket mit
`git_commit=97a462e` erzeugt. Das Manifest sieht dadurch wie ein Artefakt des
sauberen Commits aus, obwohl es diesen Zustand nicht repraesentiert.

### F7 - Mittel: Zu viele semantische Wahrheitsquellen

Legacy-Interpreter, neuer Python-Reader/Evaluator, Python-P0-VM,
Python-Compiler, C-VM, C-Compiler, Lisp-`lcc` und echte Hardware modellieren
ueberlappende Ausschnitte. Die Differentialtests begrenzen Drift, aber nicht
jede Oberflaeche ist vertikal bis zum Produktcode durchverdrahtet. Der
Reader-Vertragsbruch ist der konkrete Beleg dafuer.

Langfristig braucht jede Sprach-/ABI-Oberflaeche genau eine normative Fixture
und Adapter, die dieselben Cases gegen alle relevanten Engines ausfuehren.

### F8 - Mittel: Build- und Profilkomplexitaet sind selbst ein Fehlerrisiko

Der Root-Makefile umfasst ueber 2100 Zeilen und etwa 300 Targets. Das Produkt
wird aus geerbten CFLAG-Listen plus langen `filter-out`-/Ergaenzungsfolgen
gebildet. Mehr als 80 Feature-Makros beeinflussen den C-Code. Mehrere
Generatorziele teilen dieselben `build/bytecode/stdlib-p0.*`-Pfade und duerfen
nicht parallel laufen.

Das erschwert:

- die Frage, welche Features exakt im Produkt aktiv sind;
- inkrementelle und parallele Builds;
- isolierte Tests verschiedener Profile;
- das Entfernen historischer Varianten;
- reproduzierbare CI-Ausfuehrung.

### F9 - Mittel: Toolchain- und CI-Vertrag fehlen

Das Makefile erwartet `tools/llvm-mos/bin`, `c1541`, Python, einen Host-C-
Compiler und je nach Ziel xmega65 bzw. MEGA65-Werkzeuge. Die mehrere hundert MB
grosse llvm-mos-Toolchain ist korrekt ignoriert, aber es gibt keinen gepinnten
Bootstrap-/Installationspfad und keine CI-Konfiguration, die einen sauberen
Checkout reproduzierbar baut.

### F10 - Mittel: Offene Produktrisiken sind groesser als die aktuelle Roadmap

Dokumentiert bleiben Hardware-Haenger bei Higher-Order-Sequenzfaellen sowie
fehlende harte Fehler-/Rollback-Disziplin und Directory-Kettenfortsetzung beim
freien Speichern. Diese Risiken betreffen Laufzeitstabilitaet und Nutzerdaten.
Sie haben Vorrang vor weiteren IDE-Kommandos, CL-Komfort oder Grafik/Sound.

### F11 - Niedrig bis mittel: Dokumentation ist stark, aber zu redundant

Die Dokumentation enthaelt wertvolle Messungen und Entscheidungsgruende, aber
aktuelle Budgetwerte werden in vielen Strategie-, Status-, Audit- und
Handoff-Dateien dupliziert. Dadurch bleiben aeltere Texte mit Formulierungen wie
"aktueller Pin" auffindbar, obwohl `project-status.md` bereits andere Werte
enthaelt. Gemessene Snapshots sollten kuenftig generiert oder nur an einer
Stelle als aktuell bezeichnet werden.

## Gesamtbewertung

| Bereich | Bewertung | Begruendung |
| --- | --- | --- |
| Zielbild | stark | Klare MEGA65-native Workbench-Vision und sinnvolle Nicht-Ziele |
| Logische Architektur | gut | Kleiner Kern, Bytecode/Lisp, EXT-RAM und On-Demand-Libs passen zur Plattform |
| Physische Architektur | angespannt | Globale Zustaende, Feature-Makros und Speicherlayout koppeln viele Module |
| Native Robustheit | unzureichend | Reader-Speicherfehler und schwache Syntaxfehlergrenzen |
| Tests | stark mit Luecken | Breite Differentialsuite, aber nicht alle Oracles treffen den Produktcode |
| Build/Release | unzureichend | Monolithische Gates, keine CI, keine saubere Artefaktprovenienz |
| Dokumentation | inhaltlich stark | Gute Evidenz, aber zu viele konkurrierende aktuelle Snapshots |
| Release-Reife | MVP-Prototyp | Funktional und hardwarebewiesen, noch nicht robust/reproduzierbar genug |

## Sofortige Leitplanken

Bis die Exit-Kriterien des Sanierungsplans erreicht sind, gelten:

1. Keine neuen Produktfeatures und keine neuen Nutzerprofile.
2. Keine weitere Finanzierung durch kleinere `GC_ROOTS`, `VM_DIR_MAX`,
   `MAX_SYM`, Stack-Gates oder andere Caps.
3. Kein Release aus einem dirty Arbeitsbaum und kein Release bei rotem
   Produktgate.
4. Native Eingabe-, Loader- und Persistenzgrenzen werden vor Komfortfeatures
   gehaertet.
5. Historische Profile bleiben nur, wenn ein benannter Regressionstest sie
   braucht.
6. Neue Messwerte werden nicht manuell in mehrere aktuelle Dokumente kopiert.

## Review-Verifikation

Ausgefuehrt auf dem Arbeitsstand vom 2026-07-09:

| Pruefung | Ergebnis |
| --- | --- |
| `make check` | rot: vier nicht klassifizierte IDE-Defuns |
| `make workbench-gate` | gruen, ein Compiler-Warning in `src/vm.c` |
| `make workbench-persistence-gate` | gruen; Hardwareteil nur Dry-Run |
| Python `py_compile` fuer getrackte `.py` | gruen |
| `sh -n` fuer getrackte `.sh` | gruen |
| Native Reader-Grenzprobe | mehrere Vertragsabweichungen bestaetigt |
| Native Reader-ASan-Probe | Rootstack-Overflow bestaetigt |
| Echte Hardware | im Review nicht erneut ausgefuehrt; bestehende Logs/Doku ausgewertet |

