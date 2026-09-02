# Library-Modularisierung und On-Demand-Libs

> **Aktueller Hinweis (2026-07-08):** Die Modulstrategie bleibt gueltig, aber
> nicht mehr als Plan fuer mehrere Nutzerprodukte. Der neue Produktbeschluss steht
> in `docs/profile-consolidation-strategy.md`: ein sichtbares Workbench-Produkt;
> Dev-Core, Arena-IDE, FASL-Varianten und Runtime-Core sind nur noch Kandidaten,
> Diagnose-/Referenzprofile oder spaetere Exportpfade. On-demand-Libs sind weiter
> der Weg, die Sprache wachsen zu lassen, aber nicht der Anlass fuer Profil-Splits.
> Seit 2026-07-08 baut `make mvp-ship` dieses Workbench-Produktpaket, nicht mehr
> den alten `einsuite-full`-Ship.

Stand: 2026-07-06, nach `einsuite-full`, B3-FASL-HW-Roundtrip und
Dev-Core-Pin (`mvp-vm-stdlib-einsuite-core`, `VM_DIR_MAX=448`,
`MAX_SYM=560`). Dieses Dokument uebersetzt das Sprachinventar aus
`docs/ansi-cl-inventory.md` in eine praktische Modulstrategie fuer
Standardbibliothek, IDE, Compiler und spaetere CL-nahe Erweiterungen.

## Ausgangspunkt

Das heutige MVP-Produkt ist bewusst komfortabel: `make mvp-ship` baut die
Workbench mit REPL, lcc, Stdlib, IDE-on-demand, Disk-`load`/`save`,
Bytecode-Lib-Loader und nativen Screen-Pfaden. Das ist fuer den MVP richtig,
aber nicht das langfristige Modell fuer wachsende Sprache.

Aktuelle Fakten:

- Full-Stdlib-Artefakt: 379 Funktionen, 195 Produktfaelle, ca. 40 KB
  EXT-Image.
- `load-lib` kann vorkompilierte Bytecode-Libraries von Disk on demand laden.
- B3-FASL ist auf echter MEGA65-Hardware gruen: der Legacy-`compile-file`-
  Pfad erzeugt am Geraet einen persistenten L65M/FASL-Container, der nach
  Reboot per Loader registriert und ausgefuehrt wird. In der neuen
  Terminologie ist das `compile-file-to-lib`. FASL-Emitter und Host-Bundles
  schreiben damit dasselbe gepinnte Disk-Lib-Format.
- Dev-Core ist gepinnt: `tests/bytecode/stdlib/p0-stdlib-einsuite-core-subset.json`
  baut 315 residente Entries (align8 320), 13.098 B Bytecode-Region und hat
  im nativen Footprint `status=ok` (`prg_file_end=0xbca0`, Stack-Gap 1810 B).
  FASL/Legacy-`compile-file-to-lib` ist in diesem Profil resident; die IDE
  kommt on demand.
- Geladene Libraries sind append-only: kein Unload, Symbole werden nicht GCt,
  Directory- und Symbolslots bleiben bis zum Reboot belegt.
- On-demand spart also nicht "gratis Speicher", sondern verschiebt die Grenze
  von "alle Features resident" zu "nur der aktuelle Arbeitssatz ist geladen".

Konsequenz: Wir sollten das Full-Produkt als MVP-/Regression-Produkt behalten
und parallel ein modulares Profil aufbauen:

1. **Dev-Core:** REPL + lcc + `load`/`save` + `load-lib` + `compile-file`
   und kleine CL-nahe Basis resident; IDE, Format und groessere Stdlib-Teile
   on demand. User-level `eval`/`eval-string` und nativer Bulk-Renderer bleiben
   im Full-Profil, bis weitere Bank-0-Diaet sie im Dev-Core finanziert.
2. **Runtime-Core spaeter:** kein lcc und keine IDE resident; laedt nur FASL/
   Bytecode-Programme und kleine Runtime-Libs. Unter `LISP65_TREEWALK_STRIP`
   heisst das ohne residenten lcc auch: keine allgemeine Lisp-REPL, sondern ein
   reiner Programm-Launcher (`load`/`load-lib` -> Entry-Point).
3. **Full:** aktuelles Komfortprodukt, solange wir maximale Alltagstauglichkeit
   und einfache HW-Smokes brauchen.

## Produkt-Budget-Einschaetzung

Codex-Einschaetzung (2026-07-07): Das Ziel "IDE + Compiler + Lisp-Libs +
genug Budget fuer echte Programme" bleibt realistisch, aber nur mit der
modularen Produktform oben. Die Budgets sind nicht bequem; ein monolithisches
"alles immer resident"-Image ist keine robuste Zielarchitektur.

Wir muessen zwei Grenzen getrennt behandeln:

1. **Bank-0-Footprint:** residenter C-Code, Tabellen und BSS bestimmen, wie weit
   `__heap_start` nach oben wandert. Jeder neue C-Prim, jede groessere Tabelle
   und jede Cap-Anhebung schrumpft den Stack-Gap. Mehr IDE-/Compilerlogik in
   Lisp/Bytecode ist deshalb grundsaetzlich gut, weil sie Bank 0 schont.
2. **Laufzeit-Tiefe:** Bytecode-Lisp kostet wenig Bank 0, aber normale
   Bytecode-`CALL`s treten ueber `vm_run` wieder in C ein. Tiefe Render- oder
   Compiler-Hotpaths koennen also auch dann den Stack-Gap reissen, wenn sie
   nicht viel residenten C-Code kosten. Hotpaths muessen gemessen, flach
   geschrieben und mit `TAILCALL`/Jumps statt Helfer-Kaskaden gebaut werden.

Daraus folgt der Release-Vertrag:

- **Dev-Core:** klein genug booten, REPL/lcc/FASL/Load-Infrastruktur resident
  halten, IDE und groessere Sprachpakete on demand laden.
- **IDE/Compiler:** weiter so weit wie moeglich in Lisp entwickeln, aber
  Render-/Scroll-/Disk-/Screen-Hardwarepfade als wenige, stabile Kernel-Prims
  behalten.
- **Nutzerprogramme:** fuer Entwicklungs-Sessions ist der aktuelle Arbeitssatz
  begrenzt durch append-only Directory-/Symbol-/Region-Slots; fuer fertige
  Programme brauchen wir ein schlankeres Runtime-Profil ohne IDE und ohne
  residenten lcc.
- **Gates:** jedes Produktprofil muss Bank-0-Footprint, Directory-Headroom,
  Symbol-Headroom, Code-Region und relevante Hotpath-Tiefe separat messen. Ein
  Feature gilt erst als lieferbar, wenn es nicht nur host-gruen ist, sondern
  auch in einem konkreten Profil Budget laesst.

Kurzfassung: lisp65 ist als MEGA65-Lisp-Workstation auslieferbar, wenn der
Kernel klein bleibt und die Sprache als on-demand Bytecode-System waechst. Nicht
realistisch ist ein dauerhaft voll residentes "IDE + Compiler + alle Libraries +
grosses Nutzerprogramm" in einem Bank-0-Budget.

Die konkrete MEGA65-native Budget- und Hardwarestrategie steht in
`docs/mega65-native-budget-strategy.md`.

## Grundregeln

1. **Kern bleibt klein, aber nuetzlich.** Der residente Kern muss genug CL-Gefuehl
   liefern, dass einfache REPL-/User-Programme ohne Boilerplate laufen.
2. **Grobe Bundles statt Funktionssplit.** Eine Lib pro Funktion erzeugt
   Directory-/Symbol-Overhead und Abhaengigkeitslaerm. Eine Lib pro Domain ist
   der richtige Zuschnitt.
3. **V1 bevorzugt Hub-and-Spoke.** On-demand-Libs sollen im ersten Schritt nur
   vom residenten Core abhaengen. Inter-Lib-Abhaengigkeiten kommen erst mit
   Manifest-/Autoload-Unterstuetzung.
4. **Deps werden hostseitig gepinnt.** Jede Disk-Lib-Suite braucht
   `resident_suite` oder `requires`; das Host-Oracle muss fehlende Symbole
   finden, bevor wir ein D81 bauen.
5. **Kein implizites Unload einplanen.** Optionalitaet heisst: vor dem Laden
   sparen, nicht nach dem Laden freigeben.
6. **Jeder Load hat messbare Kosten.** Bundle-Manifeste muessen `dir_slots`
   inklusive align8, `symbol_count_estimate` und `region_bytes` ausweisen. Ein
   Host-Check rechnet `Core + gewaehlte Libs <= Caps`, bevor ein Profil als
   boot- oder session-tauglich gilt.
7. **Doppel-Load-Schutz ist v1-Pflicht.** Eine geladene Lib darf beim zweiten
   `(load-lib "...")` keine weiteren Directory-/Symbol-/Region-Slots
   verbrennen. Eine kleine Registry an einem Halte-Symbol reicht fuer v1;
   Unload bleibt trotzdem ausser Scope.
8. **Gates vor Pilot-Libs.** Dir-Headroom, Code-Objektgroesse und
   Dependency-Checks sind Vorbedingungen. B3 hat gezeigt, dass ein Produkt
   sonst host-gruen und auf HW trotzdem rot sein kann.

## Residenter Core

Der Core ist der gemeinsame Hub. Er sollte so geschnitten sein, dass alle
wichtigen Blattsuiten nur gegen ihn linken koennen.

Empfohlene residente Gruppen:

| Gruppe | Inhalt | Grund |
| --- | --- | --- |
| Sprachbasis | `quote`, `if`, `progn`, `lambda`, `function`, `setq`, `let`, `let*`, `and`, `or`, `cond`, `when`, `unless`, `case`, `dotimes`, `dolist`, einstufiges `quasiquote` | lcc/Compiler-Surface, keine Library-Load-Huerde fuer normale REPL-Formen |
| Definition/Makro | `defun`, `defmacro`, `macroexpand-1`, `function-kind`, `lcc-install`, `%set-macro` | REPL und Self-Hosting |
| Primitive-Bruecken | `+`, `-`, `*`, `/`, `mod`, Vergleiche, `cons`, `car`, `cdr`, `eq`, `eql`, `equal`, Typ-Prims, String-Prims | gemeinsame Basis fuer alle Libs |
| Kleine Listenbasis | `list`, `not`, `identity`, `caar`..`cddr`, `first`, `rest`, `second`, `1+`, `1-`, `zerop`, `append`, `length`, `nth`, `nthcdr`, `reverse`, `last`, `member`, `assoc`, `remove`, `find`, `position`, `mapcar`, `mapc` | von IDE, Strings, lcc, FASL und Nutzer-Code oft gebraucht |
| Kleine Strings | `string=`, `string/=`, `string<`..`string>=`, `string-append`, `substring`, `char`, `char->string` | IDE, Loader-Glue und Alltag |
| Output-Minimum | `write-char`, `write-string`, `terpri`, `princ`, `prin1`, `write`, `print`, `write-line`, `number->string`, `symbol-name` | REPL/Diagnose ohne Zusatzload |
| Disk-Glue | `load`, `save`, `load-lib`, `load-libs`, Disk-Prims | On-demand-Infrastruktur |
| Introspection | `boundp`, `gensym`, `symbol-count`, `symbol-max`; optional `nth-symbol` nur in Diagnosebuilds | IDE, Debugging, Budget-Sicht |

Diskussion:

- `mapcar` gehoert trotz "hoehere Funktion" in den Core, weil Strings, IDE und
  viele kleine Libraries sonst sofort von `collections` abhaengen.
- `getf`/`remf` koennen resident bleiben, weil die `places`-Lib fuer
  `(setf (getf ...))` darauf aufbaut. Wenn Slots eng werden, sind sie ein
  sauberes `plist`-Leaf mit klarer Abhaengigkeit von `places`.
- `max`/`min`/`abs`/`integerp` sind klein und haeufig; sie koennen resident
  bleiben. `fixed` bleibt klar optional.
- `format` gehoert nicht resident. Output ja, `format` nein.

## Bundle-Matrix

Diese Matrix verbindet aktuelle Dateien mit sinnvollen naechsten Erweiterungen.
"Core" meint: keine andere on-demand Lib erforderlich.

| Lib | Aktuelle Quellen/Funktionen | Naechste sinnvolle Erweiterungen | Requires |
| --- | --- | --- | --- |
| `ide` | `ide-status`, `ide-syntax`, `ide-buffer`, `ide-ui` als Disk-Lib | `ide-completion`, `ide-eval-request`, `ide-disk`; spaeter Workflow `open/save/compile/load` | Core + Screen/Key-Bridges + `load-lib` |
| `lcc-dev` | heute resident: `lcc-compile-obj`, `lcc-compile`, `lcc-lits`, `lcc-run` | kann in Runtime-Profil optional werden; Dev-Core behaelt es resident | Core |
| `fasl` | im Dev-Core resident: `lib/lcc-fasl.lisp`, `fasl-emit-scratch`, Legacy-`compile-file-to-lib` + interne Streaming-Emitter | B4: gemeinsamer IDE-Workflow `edit` -> `save` -> `compile-file-to-lib` -> `load-lib`; dieselben Manifest-/Packaging-Felder wie Host-Bundles | Core + `lcc-dev` + `LISP65_FASL`-Prims + Disk-Scratch |
| `collections` | `assq`, `butlast`, multi-`mapcar`, `mapcan`, `remove-if`, `copy-list`, `find-if`, `count`, `list*`, `reduce`, `every`, `some` | `acons`, `pairlis`, `copy-alist`, `copy-tree`, `tree-equal`, `list-length`, `make-list`, `endp`, `tailp`, `ldiff`, `revappend`, `member-if`, `assoc-if`, `rassoc`, `subst*`, `third`..`tenth`, `sets` | Core |
| `strings` | `string-equal`, `string-prefix-p`, `string-suffix-p`, `search`, `string-contains-p`, `string-trim`, case conversion; `string-left/right-trim` | `char-code`, `code-char`, `characterp`, char comparisons, `digit-char-p`, `make-string`, ANSI string aliases, `string-capitalize` | Core, optional `collections` nur wenn `mapcar` nicht resident ist |
| `math` | `max`, `min`, `abs`, `signum`, `evenp`, `oddp`, `integerp`, `clamp` | `rem`, `gcd`, `lcm`, `floor`, `truncate`, `round`, `isqrt`, `integer-length`, `parse-integer` | Core |
| `fixed` | `fx-scale`, `integer->fx`, `fx`, `fx->integer`, `fx+`, `fx-`, `fx*`, `fx/`, `fx<` | Druck-/Parse-Helfer, evtl. `fx<=` etc. | Core + `math` |
| `format` | `integer->string`, kleines `format`; `format-extra` fuer `~S`/Readable-Listen | weitere Direktiven nur selektiv; voller ANSI-Pretty-Printer bleibt ausgeschlossen | Core + Output + Strings |
| `plist` | `getf`, `remf` | stabiler Unterbau fuer `(setf (getf ...))`, Symbol-Plists falls Symbol-Wert-API kommt | Core |
| `control-extra` | `do` als Source-Makro; `dotimes`/`dolist` sind schon Compiler-Surface | `do*`, `prog1`, `prog2`, kleines `loop`, `destructuring-bind` | Core; fuer `block`/`return-from` neue Runtime noetig |
| `reader-printer` | noch nicht Produktlib | `read`, `read-from-string`, `write-to-string`, `prin1-to-string`, `fresh-line` | Core + neue Reader/String-Naeht |
| `places` | `lib/stdlib-places.lisp`: `setf`, `incf`, `decf`, `push`, `pop`; feste Expander fuer Symbol-, `car`-, `cdr`- und `getf`-Places | `psetq`, `psetf`, `pushnew`, `rotatef`; spaeter breiteres Place-Protokoll | Core + `plist`; `symbol-value`/`fboundp` falls CL-nahe Places |
| `conditions-lite` | noch nicht Produktlib | `error`, `warn`, `ignore-errors`, `handler-case`-Subset | Core + `catch`/`throw`/`unwind-protect` Runtime |
| `vectors` | noch nicht moeglich | `vector`, `aref`, `svref`, `make-array`-Subset | neue Objektart |
| `hash` | noch nicht moeglich | `make-hash-table`, `gethash`, `remhash`, `maphash` | Vektor/Array oder native Tabelle + Multiple Values fuer CL-nahe API |
| `struct` | noch nicht moeglich | eingeschraenktes `defstruct` | Objekt-/Slot-Repraesentation oder Listen-Struct-Konvention |
| `packages` | noch nicht Produktziel | `find-symbol`, `intern`, `do-symbols`-Subset | Symbol-Namespace-Design |

## MEGA65-BASIC-65-Komfort

Die CL-nahe Stdlib bleibt getrennt von MEGA65-Hardwarekomfort. Fuer Grafik,
Sound, Sprites, Eingabe, Disk und Systemzugriff ist der detaillierte
Post-MVP-Schnitt in `docs/mega65-basic-parity-libraries.md` gepinnt. Kurzform:

- stabile Namen bleiben praefigiert (`m65-line`, `m65-sound`,
  `m65-joy`, `m65-dir`);
- ein optionales `basic65`-Facade-Bundle darf BASIC-nahe Kurznamen wie `line`,
  `box`, `circle`, `sound`, `play` installieren;
- Low-Level-Register-/Speicherzugriff sitzt in `m65-hw`, nicht in jeder
  Domain-Lib separat;
- `m65-gfx`/`m65-draw`, `m65-sprite`, `m65-sound`, `m65-input`, `m65-disk`
  und `m65-system` werden als grobe on-demand Bundles behandelt;
- Runtime-Naehte wie 28-bit `peek`/`poke`, EDMA, Kanal-I/O und Timer/Tick
  werden nur nach Messung bzw. fuer echte Paritaetsluecken in den Kern gezogen.

## Abhaengigkeitslinien

### Core muss stark genug sein

Die wichtigsten Blattsuiten sollen keine Reihenfolge ausser "Core ist da" haben:

- `strings` braucht `mapcar`, `append`, `string->list`, `list->string`,
  `string-length`, `string-ref`.
- `collections` braucht `funcall`, `apply`, `append`, `reverse`, `length`,
  `assoc`, `eql`.
- `format` braucht Output, `string->list`, `list->string`, `append` und
  Fixnum-Arithmetik.
- `ide` braucht Listenbasis, kleine Strings, Screen/Key-Bridges,
  `symbol-count`/`symbol-max` und `function-kind`; `nth-symbol` ist kein
  Produkt-Dependency mehr.
- `fasl` braucht `lcc-compile-obj`, `rplaca`, `symbol-name`, `string->list`,
  `%fasl-stage`, `%fasl-src`, `%fasl-read-form`, `%fasl-save` und
  Fixnum-Arithmetik.

Daraus folgt: `mapcar`, kleine Strings und Output sollten nicht ausgelagert
werden, wenn wir Dependency-Hoelle vermeiden wollen.

### Manifest- und Kostenmodell

Ab C0 bekommt jede Disk-Lib-Suite ein Manifest. Dieses Manifest ist nicht nur
Beschreibung, sondern ein Budgetvertrag:

```json
{
  "name": "format",
  "provides": ["format", "integer->string"],
  "requires": ["core"],
  "autoload": false,
  "sources": ["lib/stdlib-format.lisp", "lib/stdlib-format-extra.lisp"],
  "cost": {
    "dir_slots": 23,
    "dir_slots_after_align8": 24,
    "symbol_count_estimate": 31,
    "region_bytes": 912
  }
}
```

Host-Tooling sollte dann pruefen:

- alle externen Symbole sind entweder Core, eigene Definitionen oder
  `requires`;
- `requires` sind grob und zyklusfrei;
- die gemessenen Kosten passen zum Zielprofil (`VM_DIR_MAX`, `MAX_SYM`,
  Region-Fenster);
- D81 enthaelt alle angeforderten Lib-Dateien;
- ein optionaler Smoke `(load-libs "...")` laedt die Libs in Manifest-Reihenfolge.

Runtime-v1 kann weiter explizit bleiben:

```lisp
(load-libs "collections" "format")
```

Autoload pro unbekannter Funktion ist nicht v1-tauglich: zu teuer, schwer zu
diagnostizieren, und bei append-only Libs kann ein Tippfehler Slots verbrennen.

FASL-Ausgaben von `compile-file` und Host-gebaute Bundles sind dieselbe
Paketwelt: gleicher L65M-Trailer, gleiche Entry-/Literal-Metadaten, gleicher
Loader, gleiche Registry. Der Host-D81-Packer und der Geraete-FASL-Emitter
duerfen keine parallelen Manifest-Dialekte bilden.

## Standardbibliothek: empfohlener Schnitt

### Core-resident

Bleibt im Dev-Core:

- `prelude-m1`: Definition/Makro-Basis plus kleine Listen-/Praedikatsbasis.
- `stdlib-einsuite-bridges` und `stdlib-bytecode-bridges`: normale
  Funktionsnamen fuer Primitive und Screen/Key-Faehigkeiten.
- `stdlib-output`, `stdlib-load`, `stdlib-load-lib`.
- Kleine Auswahl aus `stdlib-strings`: Vergleiche, `string-append`,
  `substring`, `char`, `char->string`.
- Kleine Auswahl aus `stdlib-lists`: multi-`mapcar` kann resident bleiben,
  weil es viele Libs vereinfacht; der Rest kann ins Bundle.
- `lcc` im Dev-Core, aber nicht zwingend im spaeteren Runtime-Core.

### On-demand aus aktueller Stdlib

Sofort gute Kandidaten:

1. `ide`: groesster Arbeitssatzhebel. `tests/bytecode/libs/p0-ide-lib.json`
   enthaelt jetzt `ide-status`, `ide-syntax`, `ide-buffer` und `ide-ui`; nur
   `ide-launch`/`edit` bleibt resident.
2. `format`: selten gebraucht, relativ klarer Leaf.
3. `fixed`: lisp65-spezialisiert, keine Alltagspflicht.
4. `strings-extra`: Search/Trim/Case und Left/Right-Trim.
5. `collections`: Listen-/Sequence-Breite, besonders wenn Programme nicht alle
   Higher-Order-Funktionen brauchen.
6. `fasl`: Dev-Workflow, nicht Runtime-Pflicht.
7. `places`: `setf`-MVP liegt als reine Lisp-Makro-Lib vor und ist ein guter
   PLACE-Pilot fuer on-demand Makro-Bundles.

Aktueller Packaging-Stand (2026-07-06): `ide`, `format`, `fixed`,
`strings-extra` und `place` haben Disk-Lib-Suiten unter `tests/bytecode/libs/` und koennen
per `make bytecode-p0-pilot-libs-artifacts` als L65M-Libs gebaut werden.
`make bytecode-p0-pilot-libs-d81` packt sie gemeinsam als `IDE`, `FMT`,
`FIXED`, `STRX`, `PLACE`. `place` ist der erste Macro-Pilot: `defmacro`-
Entries setzen im L65M-Entry-Flag Bit0 und werden als `T_MACRO(BCODE)`
registriert. Alle Pilot-Libs linken gegen den Dev-Core-Pin
`p0-stdlib-einsuite-core-subset.json`.

Gemessene Kosten des Pins:

| Artefakt | Dir-Slots | align8 | Region | Symbol-Schaetzung |
| --- | ---: | ---: | ---: | ---: |
| Dev-Core resident | 315 | 320 | 13.098 B | 405 |
| `ide` | 114 | 120 | 5.481 B | 143 |
| `format` | 10 | 16 | 439 B | 14 |
| `fixed` | 16 | 16 | 489 B | 19 |
| `strings-extra` | 2 | 8 | 48 B | 4 |
| `place` | 8 | 8 | 423 B | 21 |

Session-Mathematik aus dem alten Dev-Core-Pin mit `VM_DIR_MAX=448`: Dev-Core +
IDE nutzte 434 Slots und liess 14 Slots Headroom. Der aktuelle Workbench-Pin
nutzt `VM_DIR_MAX=512` fuer die vergroesserte IDE-Lib und einen kleinen
Compile-Roundtrip; Dev-Core + IDE + alle Pilot-Libs gleichzeitig ist trotzdem
bewusst **nicht** das gepinnte Profil. Dafuer waeren weitere Bank-0-Diaet und
ein neuer Session-Budget-Check noetig.

Vorsichtige Kandidaten:

- `math`: klein und oft gebraucht; erst auslagern, wenn Core wirklich enger
  werden muss.
- `plist`: klein, aber fuer `places`/IDE-/Metadatenarbeit wahrscheinlich
  nuetzlich. Kann resident bleiben oder als harte `places`-Abhaengigkeit
  ausgelagert werden.

Nicht auslagern:

- `load`/`load-lib`, Output-Minimum, primitive Bruecken, kleine Listenbasis,
  kleine Strings, lcc im Dev-Core.

## Erweiterungen aus dem ANSI-Inventar

### Phase 1: reine Lisp-Libs ohne neue Objektarten

Diese koennen als on-demand Bundles wachsen:

- `collections`: `acons`, `pairlis`, `copy-alist`, `copy-tree`,
  `tree-equal`, `make-list`, `endp`, `tailp`, `member-if`, `assoc-if`,
  `rassoc`, `subst*`, Set-Operationen auf Listen.
- `strings`: Char-Praedikate, Char-Vergleiche, `code-char`/`char-code`,
  `make-string`, ANSI-String-Aliase, `string-capitalize`.
- `math`: `gcd`, `lcm`, `rem`, einfache Rundungsfunktionen mit einem Wert,
  `parse-integer`, `integer-length`.
- `places`: `setf`-MVP, `incf`, `decf`, `push`, `pop` sind vorhanden; naechste
  Kandidaten sind `psetq`, `psetf`, `pushnew`, `rotatef` und ein sauberer
  once-only-Plan fuer komplexere Places.
- `reader-printer`: String-Reader/-Writer-Funktionen ohne volles Stream-System.
- `format`: weitere kleine Direktiven, aber keine Pretty-Printer-Schicht.

### Phase 2: ABI-v1.1-Projekt noetig

Diese Libraries brauchen nicht nur neue Lisp-Funktionen, sondern eine
bewusste Bytecode-ABI-Erweiterung. `block`/`return-from`, `catch`/`throw`,
`unwind-protect` und Multiple Values muessen als ein eigenes ABI-v1.1-Projekt
geplant werden: VM-Opcodes, lcc-Codegen, Host-VM, Drift-Check, Korpora und
Budget-Messung muessen gemeinsam landen. Danach koennen die Oberflaechen
weiter modular bleiben:

- `control-extra`: `block`, `return-from`, `catch`, `throw`,
  `unwind-protect` als Basis fuer `return`, `prog*`, kleines `loop`.
- `multiple-values`: `values`, `multiple-value-bind`, `nth-value`; danach
  koennen `floor`, `truncate`, `gethash` CL-naeher werden.
- `conditions-lite`: erst nach nichtlokalen Exits sinnvoll.

### Phase 3: neue Objektarten

Erst nach Repraesentationsentscheid:

- `vectors`
- `hash`
- `struct`
- `packages`
- groessere Streams/Pathnames

Diese sollten nicht als "nur Lisp-Lib" gestartet werden.

## Konkrete Dateinamen

CBM-/D81-Dateinamen sollten kurz und stabil sein. Vorschlag:

| Nutzername | D81-Name | Inhalt |
| --- | --- | --- |
| `"ide"` | `IDE` | Editor-Kern |
| `"idex"` | `IDEX` | Completion, Eval-Request, Disk-IDE-Workflow |
| `"coll"` | `COLL` | Collections/List/Sequence/Set |
| `"strx"` | `STRX` | String-/Char-Extras |
| `"math"` | `MATH` | Fixnum-Math-Extras |
| `"fixed"` | `FIXED` | Fixed-Point |
| `"fmt"` | `FMT` | Format-Subset |
| `"fasl"` | `FASL` | FASL-Emitter/compile-file-to-lib |
| `"place"` | `PLACE` | setf/incf/push/pop |
| `"readp"` | `READP` | Reader/Printer-String-Helfer |

Die Lisp-Namen koennen lesbarer bleiben als die D81-Namen, solange der
Directory-Walk die Zielnamen findet. Fuer v1 ist identischer Name in Klein-/
Grossschreibung am wenigsten fehleranfaellig.

## Umsetzungsplan

1. **Vorbedingungs-Gates scharf halten.** `bytecode_p0_stdlib.py` prueft
   Code-Objekte gegen die native 255-B-Grenze und produktnahe Suiten gegen
   `vm_dir_max`/align8-Headroom. Das Dependency-Gate fuer
   `requires`/`resident_suite` ist fuer Disk-Lib-Suiten ebenfalls aktiv.
2. **Dokumentierten Core neu pinnen.** Erledigt: neue Suite
   `tests/bytecode/stdlib/p0-stdlib-einsuite-core-subset.json`, neues Target
   `make mvp-vm-stdlib-einsuite-core` plus
   `make mvp-vm-stdlib-einsuite-core-footprint-report`. Der Pin enthaelt
   `load`, `load-lib`, `save`, lcc, FASL/Legacy-`compile-file-to-lib`, Output
   und kleine Basis; IDE/Format/Fixed/Extras bleiben Disk-Libs.
3. **Bundle-Manifeste einfuehren.** Hostseitig fuer Disk-Libs erledigt:
   `tests/bytecode/libs/*.json` deklarieren `name`, `provides`, `requires`,
   `d81_name` und `resident_suite`; die erzeugten Manifest-Dateien enthalten
   dazu gemessene `cost`-Felder.
4. **Load-Registry einfuehren.** Erledigt: `(load-lib name)` merkt
   erfolgreiche Loads in `*loaded-libs*` und gibt bei Wiederholung ohne neuen
   Disk-/Directory-Load `t` zurueck.
5. **Pilot-Libs bauen.** `ide`, `format`, `fixed`, `strings-extra` und
   `place` sind als L65M-Libs gebaut und gegatet; `place` nutzt Macro-Entries
   (`flags&1`).
6. **Deps-Gate schreiben.** Erledigt fuer Disk-Lib-Suiten:
   `bytecode_p0_stdlib.py` failt kompilierte `CALL`/`TAILCALL`-Ziele, die
   weder in der Lib selbst, noch im residenten Suite-Directory, noch als
   bekannte native Funktionszelle vorhanden sind.
7. **D81-Packaging normalisieren.** Ein gemeinsames Tool baut ein D81 mit
   Core-Testlibs plus Manifest-Report; fuer B4 inklusive vorallozierter
   FASL-Slots und user-`compile-file`-Ausgaben.
8. **B4-Workflow-Gate.** Dev-Core + on-demand IDE + FASL in einem Profil:
   editieren -> save -> compile-file -> reboot/load-lib -> ausfuehren.
9. **Load-Smokes staffeln.** Host-Embed-Oracle -> xemu dry/safe harness ->
   HW nur gezielt. Keine automatischen Langzeit-xemu-Prozesse.
10. **Runtime-Core erst spaeter.** Nach B4 pruefen wir ein zweites Produkt
   ohne residenten lcc fuer reine Programm-Ausfuehrung.
11. **ABI-v1.1-Entscheid separat.** Nonlocal exits und Multiple Values erst
    nach Messung, Design-Doc und Nutzer-Entscheid.

## Offene Designfragen

- Soll `mapcar` dauerhaft resident bleiben oder in `collections` wandern?
  Empfehlung: resident, weil es `strings` und viel User-Code entkoppelt.
- Soll `getf`/`remf` resident bleiben? Empfehlung: ja fuer den aktuellen
  `places`-MVP und `(setf (getf ...))`; spaeter koennen sie als `plist`-Lib
  eine harte Abhaengigkeit von `place` werden.
- Soll `ide-status` resident bleiben? Nein im Dev-Core-Pin: `ide-status` und
  `ide-syntax` sind Teil der IDE-Disk-Lib, nur `edit`/`ide-loaded-p` bleiben
  resident.
- Soll `format` Teil von `strings` sein? Nein. `format` ist ein Verbraucher von
  Strings/Output, kein String-Basisdienst.
- Wie vermeiden wir Doppel-Loads? Antwort: per zentraler Load-Registry in v1.
  `function-kind`/`*-loaded-p` bleibt nur ein Fallback fuer alte Ad-hoc-Libs.
  Vollstaendiges Unload ist kein Ziel fuer v1.
