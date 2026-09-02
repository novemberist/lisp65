# ANSI-CL-Inventar fuer lisp65

Stand: 2026-07-08, nach Workbench-MVP-Pin. Dieses Dokument ist eine
Planungsinventur, kein Konformitaetsversprechen. Es beschreibt, welche
Common-Lisp-nahe Oberflaeche lisp65 heute hat, was nur host-/source-getestet
ist und welche ANSI-CL-Familien theoretisch fehlen.

Lokale Gegenprobe fuer diesen Stand:

- Produktprofil: `tests/bytecode/stdlib/p0-stdlib-einsuite-core-workbench-subset.json`
- IDE-Disk-Lib: `tests/bytecode/libs/p0-ide-lib.json`
- Produkt-Bytecode-Artefakte: 315 residente Stdlib-Entries im externen Blob,
  131 IDE-Entries on demand vom D81
- Kernel-Primitive: 65 `defprim`-Registrierungen in `src/eval.c`
- Aktuelles Geraeteprodukt: `make mvp-ship` /
  `mvp-vm-stdlib-einsuite-core-workbench`
- Native FASL-B1-Schicht: Referenz/Diagnose; das Produkt nutzt
  `compile-string` plus vorallokierte Compile-Zielslots

Referenzen:

- CLHS Symbol Index: https://www.lispworks.com/documentation/HyperSpec/Front/X_AllSym.htm
- CLHS Special Operators: https://www.lispworks.com/documentation/HyperSpec/Body/03_ababa.htm

## Einordnung

Voller ANSI CL ist fuer lisp65 auf dem MEGA65 kein realistisches Produktziel.
ANSI CL setzt Objektarten und Runtime-Schichten voraus, die lisp65 aktuell
bewusst nicht hat: Packages, Streams, Pathnames, Arrays/Vektoren,
Hash-Tabellen, Conditions/Restarts, CLOS, volle numerische Tower,
Multiple Values, Readtables, Deklarations-/Compiler-Umgebung und eine breite
Pretty-Printer-Schicht.

Das heutige Ziel ist stattdessen:

1. Ein kleines, selbst-gehostetes Lisp-System auf echter MEGA65-Hardware.
2. Ein CL-nahes Kerngefuehl fuer REPL, IDE, Listen, Fixnums, Symbole, Strings
   und Makros.
3. Lisp-Libraries und lcc/FASL-Ausbau, bevor neue Dinge in Bank 0 wandern.

## Ist-Stand

### Produktmodell

Das Geraeteprodukt ist die Workbench:

- `lcc` ist der Geraete-Evaluator. REPL, `eval`, `eval-string` und
  `(load ...)` routen in den Bytecode-Compiler/-VM-Pfad.
- Der alte Treewalk ist aus dem Produktprofil gestripped. Host-Treewalk und
  `src/compile.c` bleiben Referenz-Engines fuer Aequivalenztests.
- Das Produkt-Blob enthaelt Stdlib, lcc und den Lisp-Teil des Disk-Loads.
- Die IDE ist on demand als D81-Disk-Lib verfuegbar; `(edit)` laedt `ide` und
  startet die MEGA65-IDE.
- Disk ist resident: `(load "name")` kompiliert Source von F011/D81;
  `(save "name" string)` schreibt Overwrite-in-place in vorallozierte Slots.
- Legacy-`compile-string` schreibt L65M/FASL-Code in vorallokierte D81-Slots,
  danach macht `(load-lib "slot")` die Definitionen nutzbar. In der neuen
  Terminologie ist das `compile-string-to-lib`. Nach `nil` liefert
  `(compile-error)` einfache Workbench-Fehlerdetails wie `"slot missing"` oder
  `"too large"`.
- Nach `(load-lib "ide")` oder `(edit)` liefert die ladbare IDE-Lib eine
  schmale Persistenz-API: `load-file-to-buffer`, `save-buffer-to`,
  `eval-buffer`, `compile-buffer-to-lib`, `compile-file-to-lib`.
  `compile-file-to-lib` ist ein lisp65-Workbench-Wrapper ueber Disk-Read plus
  `compile-string` nach L65M/FASL-Slot, kein ANSI-CL-`compile-file` mit
  Pathnames. Neue Terminologie: `compile` ohne `to-lib` meint kuenftig
  transient; persistente L65M/FASL-Ausgabe traegt `to-lib`/`to-fasl`.

### Formen und Makros

Produktnah direkt durch lcc unterstuetzt:

- Special-/Compiler-Forms: `quote`, `if`, `progn`, `lambda`, `function`,
  `setq`, `let`, `let*`
- Lowerings im Compiler/lcc: `and`, `or`, `cond`, `when`, `unless`,
  `case`, `dotimes`, `dolist`, einstufiges `quasiquote`
- Top-Level-/Runtime-Install: `defun` via `lcc-install`; `defmacro` via
  BCODE-Expander und `%set-macro`
- Makro-Naht: `function-kind` + `macroexpand-1` fuer Expansionen vor dem
  Kompilieren

Source-/Host-getestet, aber nicht zwingend als vorinstallierte Produktmakros
zu verstehen:

`do`, die Prelude-Makrovarianten von `defparameter`/`defvar`, sowie die
Disk-Makro-Route fuer `cond`/`and`/`or`/`case`.

Wichtige Einschraenkungen:

- lcc kann heute feste Parameter, `&rest` und Closures. `&rest` in
  Immediate-Lambdas ist im C-Compilerpfad noch ein Randfall.
- `quasiquote` ist einstufig. Nested quasiquote ist offen.
- `case` ist direkt im Compiler fuer atomare Keys vorhanden; Listenkeys sind
  ueber die Disk-Makro-Route getestet, aber nicht im direkten C-Lowering.
- `defparameter`/`defvar` sind im Boot-/Source-Pfad behandelt; volle
  ANSI-`defvar`-Semantik ist nicht als Produktversprechen zu lesen.

### Kernel-Primitive

Aktuell Lisp-visible `defprim`-Namen:

`+`, `-`, `*`, `/`, `mod`, `<`, `>`, `=`, `<=`, `>=`, `cons`, `car`, `cdr`,
`eq`, `eql`, `list`, `funcall`, `apply`, `set-symbol-function`, `gensym`,
`boundp`, `peek`, `poke`, `load`, `save`, `eval`, `eval-string`,
`macroexpand-1`, `lcc-install`, `%set-macro`, `stringp`, `numberp`,
`symbolp`, `string->list`, `list->string`, `string-length`, `string-ref`,
`write-char`, `write-string`, `prin1`, `screen-bulk-p`, `terpri`, `princ`,
`print`, `write`, `write-line`, `nreverse`, `rplaca`, `rplacd`,
`symbol-count`, `symbol-max`, `number->string`, `symbol-name`,
`function-kind`, `screen-size`, `screen-clear`, `screen-put-char`,
`screen-write-string`, `read-key`, `poll-key`, `%disk-read-sector`,
`%disk-byte`, `%disk-poke`, `%disk-write-sector`.

`nth-symbol` existiert nur noch als opt-in Diagnose-Primitive
(`LISP65_NTH_SYMBOL_PRIM`), nicht im Workbench-Produktpin.

Teilweise ANSI-kompatibel heisst hier: Fixnum-Arithmetik statt voller
numerischer Tower; Zeichen sind Fixnum-Codes; Strings sind eigene `T_STR`-
Objekte mit Listen-Konvertierung; Output ignoriert ANSI-Stream-/Keyword-
Argumente weitgehend.

### CL-nahe Produktfunktionen

Im Full-Produkt sind diese CL-nahen sichtbaren Namen vorhanden:

`not`, `identity`, `list`, `+`, `*`, `-`, `/`, `mod`, `<`, `>`, `=`, `<=`,
`>=`, `/=`, `cons`, `car`, `cdr`, `eq`, `eql`, `equal`, `consp`, `atom`,
`null`, `numberp`, `integerp`, `symbolp`, `stringp`, `boundp`, `gensym`,
`funcall`, `apply`, `eval`, `macroexpand-1`, `set-symbol-function`,
`rplaca`, `rplacd`, `nreverse`, `caar`, `cadr`, `cdar`, `cddr`, `first`,
`rest`, `second`, `1+`, `1-`, `zerop`, `plusp`, `minusp`, `append`,
`length`, `nth`, `nthcdr`, `reverse`, `last`, `member`, `assoc`, `remove`,
`find`, `position`, `mapc`, `butlast`, `mapcar`, `mapcan`, `remove-if`,
`remove-if-not`, `copy-list`, `find-if`, `position-if`, `count`, `count-if`,
`list*`, `reduce`, `every`, `some`, `max`, `min`, `abs`, `signum`, `evenp`,
`oddp`, `getf`, `remf`, `string=`, `string/=`, `string<`, `string>`,
`string<=`, `string>=`, `string-equal`, `search`, `string-trim`,
`string-upcase`, `string-downcase`, `char`, `char-upcase`, `char-downcase`,
`symbol-name`, `write-char`, `write-string`, `terpri`, `princ`, `prin1`,
`write`, `print`, `write-line`.

Zusaetzliche lisp65-Namen im Produkt, nicht ANSI CL:

`string-append`, `substring`, `string-prefix-p`, `string-suffix-p`,
`string-contains-p`, `char->string`, `nonnegativep`, `nonpositivep`,
`clamp`, `assq`, `screen-*`, `read-key`, `poll-key`, `symbol-count`,
`symbol-max`, `number->string`, `function-kind`, `lcc-compile`,
`lcc-compile-obj`, `lcc-lits`, `lcc-run`, `ide-*`, `load`, `save`.

Die vielen `%...`-Namen sind interne Helfer und keine stabile Sprachebene.

### Source-/Host-getestet, nicht Produktkern

- `format`: kleines Subset (`~A`, `~S`, `~D`, `~%`, `~~`) host- und
  bytecode-getestet, aber nicht im aktuellen Full-Produkt-Blob.
- `string-left-trim`, `string-right-trim`: Source vorhanden, nicht im
  Full-Produkt-Blob.
- Fixed-Point-Erweiterung: `fx-scale`, `integer->fx`, `fx`,
  `fx->integer`, `fx+`, `fx-`, `fx*`, `fx/`, `fx<`.
- `load-lib`, `load-libs`: Source-/Profilarbeit fuer Bytecode-Libs; die
  aktuellen Full-Produktfunktionen enthalten den Source-Load-Pfad `(load)`.
- `lib/lcc-fasl.lisp`: B1-Emitter fuer das gepinnte Disk-Lib-/FASL-Format;
  durch Format-Orakel geprueft, Integration ins Full-Produkt ist B2.

## Essentiell

Diese Gruppe bringt das groesste CL-Gefuehl pro investierter
Runtime-Komplexitaet. Sie sollte vor grossen ANSI-Familien kommen.

### lcc-Sprachluecken

Bereits da:

`defun`, `defmacro`, `lambda`, feste Parameter, `&rest`, Closures/Captures,
BCODE-Makros, `macroexpand-1`, `eval`, `eval-string`, `load`, `and`, `or`,
`cond`, `when`, `unless`, `case`, `dotimes`, `dolist`, `let`, `let*`,
`setq`, einstufiges `quasiquote`.

Fehlt oder eingeschraenkt:

Nested quasiquote, `&rest` in Immediate-Lambdas, `case`-Listenkeys im
direkten Compilerpfad, `do` als direkte Produktform, volle
`defparameter`/`defvar`-Semantik und robustere Fehlermeldungen mit Kontext
statt knappem Abort.

Warum essentiell: Das sind keine grossen ANSI-Familien, sondern Luecken im
heutigen Selbst-Hosting-Pfad.

### Places und Mutation

Bereits da:

`setq`, `boundp`, `set-symbol-function`, `rplaca`, `rplacd`, `nreverse`,
`car`, `cdr`, `cons`, `getf`, `remf`.

Fehlt:

`setf`, `psetf`, `psetq`, `incf`, `decf`, `push`, `pop`, `pushnew`,
`rotatef`, `shiftf`, `set`, `symbol-value`, `symbol-function`, `fboundp`,
`fdefinition`, `makunbound`, `fmakunbound`.

Warum essentiell: Ohne `setf`-Familie fehlen CL-typische Places. Fuer eine
erste Version reichen feste Expansions fuer Variablen, `car`, `cdr`,
`symbol-value` und `getf`; generalisierte Setf-Expander koennen spaeter kommen.

### Reader/Printer-Minimum

Bereits da:

Reader intern, `eval-string`, `load`, `write-char`, `write-string`,
`terpri`, `prin1`, `princ`, `print`, `write`, `write-line`,
`number->string`, `symbol-name`.

Fehlt:

`read`, `read-from-string`, `read-char`, `peek-char`, `unread-char`,
`read-line`, `read-delimited-list`, `prin1-to-string`, `princ-to-string`,
`write-to-string`, `fresh-line`, `finish-output`, `force-output`,
`clear-input`, `clear-output`.

Warum essentiell: Die IDE und Nutzer-Libraries brauchen Lisp-visible Reader-/
Printer-Helfer. Streams koennen zunaechst ignoriert oder auf `t`/`nil`
beschraenkt werden.

### Lokale Funktionen und nichtlokale Exits

Bereits da:

Globale Funktionen, Closures, `funcall`, `apply`, Tailcalls im lcc-Pfad.

Fehlt:

Special Operators `block`, `return-from`, `catch`, `throw`,
`unwind-protect`, `flet`, `labels`, `macrolet`, `tagbody`, `go`.

Darauf aufbauend fehlen:

`return`, `prog`, `prog*`, `prog1`, `prog2`, `do*`, ein kleines `loop`,
`destructuring-bind`.

Warum essentiell: `block`/`return-from`, `catch`/`throw` und
`unwind-protect` sind die Basis fuer kontrollierte Abbrueche, Error-Recovery
und spaetere Conditions. `flet`/`labels` machen lokale Hilfsfunktionen
moeglich.

### Multiple Values

Fehlt komplett:

`values`, `values-list`, `multiple-value-bind`, `multiple-value-call`,
`multiple-value-list`, `multiple-value-prog1`, `multiple-value-setq`,
`nth-value`.

Warum essentiell: Viele ANSI-Funktionen liefern optionale Nebenwerte
(`floor`, `truncate`, `gethash`, `find-symbol`, Reader-/Parser-Funktionen).
Ohne Multiple Values bleibt die API entweder nicht-ANSI oder muss Nebenwerte
verlieren.

### Typ- und Praedikatsbasis

Bereits da:

`consp`, `atom`, `null`, `numberp`, `symbolp`, `stringp`, `integerp`,
`eq`, `eql`, `equal`, `function-kind`.

Fehlt:

`listp`, `endp`, `functionp`, `compiled-function-p`, `characterp`,
`typep`, `type-of`, `subtypep`, `constantp`, `keywordp`, `streamp`,
`pathnamep`, `arrayp`, `vectorp`, `hash-table-p`.

Warum essentiell: Ein Teil kann sofort als Praedikate auf vorhandenen Typen
kommen; der Rest muss bis zu den jeweiligen Objektarten warten.

## Sinnvoll und machbar

Diese Gruppe ist groesstenteils als Lisp-Library auf heutigen Conses, Fixnums,
Symbolen und Strings machbar. Sie ist nicht voll ANSI, aber fuer Nutzerprogramme
wertvoll.

### Listen, Baeume und Alists

Bereits teilweise da:

`append`, `length`, `nth`, `nthcdr`, `reverse`, `nreverse`, `last`,
`member`, `assoc`, `assq`, `remove`, `find`, `position`, `copy-list`,
`butlast`, `mapcar`, `mapc`, `mapcan`, `remove-if`, `remove-if-not`,
`find-if`, `position-if`, `count`, `count-if`, `list*`.

Fehlt:

`acons`, `pairlis`, `copy-alist`, `copy-tree`, `tree-equal`,
`list-length`, `make-list`, `endp`, `tailp`, `ldiff`, `revappend`,
`nconc`, `nreconc`, `nbutlast`, `member-if`, `member-if-not`,
`assoc-if`, `assoc-if-not`, `rassoc`, `rassoc-if`, `rassoc-if-not`,
`subst`, `subst-if`, `subst-if-not`, `sublis`, `nsublis`, `nsubst`,
`nsubst-if`, `nsubst-if-not`.

Auch sinnvoll: alle `c[ad]+r`-Kombinationen bis vier Ebenen (`caaar`,
`caddr`, `cadddr`, `cddddr`, ...), sowie `third` bis `tenth`.

### Sequenzen auf Listen/Strings

Bereits teilweise da:

`length`, `reverse`, `find`, `position`, `count`, `remove`, `search`,
`mapcar`, `mapc`, `mapcan`, `reduce`, `every`, `some`, `find-if`,
`position-if`, `count-if`.

Fehlt:

`map`, `map-into`, `mapl`, `maplist`, `mapcon`, `notany`, `notevery`,
`find-if-not`, `position-if-not`, `count-if-not`, `remove-duplicates`,
`delete`, `delete-if`, `delete-if-not`, `delete-duplicates`, `substitute`,
`substitute-if`, `substitute-if-not`, `nsubstitute`, `nsubstitute-if`,
`nsubstitute-if-not`, `replace`, `fill`, `mismatch`, `sort`, `stable-sort`,
`merge`.

Einschraenkung: Ohne Vektoren/Arrays sollten diese zunaechst nur Listen und
Strings abdecken.

### Mengen auf Listen

Fehlt:

`adjoin`, `union`, `intersection`, `set-difference`, `set-exclusive-or`,
`subsetp`, `nunion`, `nintersection`, `nset-difference`,
`nset-exclusive-or`.

Machbar als Lisp-Library mit `eql`/`equal`-Tests; `:key`/`:test`/`:test-not`
koennen schrittweise folgen.

### ASCII-/PETSCII-nahe Zeichen und Strings

Bereits da:

`string=`, `string/=`, `string<`, `string>`, `string<=`, `string>=`,
`string-equal`, `string-trim`, `string-upcase`, `string-downcase`,
`char`, `char-upcase`, `char-downcase`, `search`, plus lisp65-Namen
`string-append`, `substring`, `string-prefix-p`, `string-suffix-p`,
`string-contains-p`, `char->string`.

Source-/host-getestet:

`string-left-trim`, `string-right-trim`.

Fehlt:

`char-code`, `code-char`, `char-int`, `character`, `characterp`,
`standard-char-p`, `graphic-char-p`, `alpha-char-p`, `alphanumericp`,
`digit-char`, `digit-char-p`, `both-case-p`, `upper-case-p`,
`lower-case-p`, `char=`, `char/=`, `char<`, `char>`, `char<=`,
`char>=`, `char-equal`, `char-not-equal`, `char-lessp`,
`char-greaterp`, `char-not-lessp`, `char-not-greaterp`, `string`,
`make-string`, `string-not-equal`, `string-lessp`, `string-greaterp`,
`string-not-lessp`, `string-not-greaterp`, `string-capitalize`,
`nstring-upcase`, `nstring-downcase`, `nstring-capitalize`.

Machbar als ASCII-/PETSCII-nahe Schicht; volle ANSI-Character-Semantik ist
separat.

### Fixnum-Math und Bits

Bereits da:

`+`, `-`, `*`, `/`, `mod`, Vergleiche, `1+`, `1-`, `abs`, `signum`,
`evenp`, `oddp`, `max`, `min`, `integerp`, `number->string`.

Fehlt:

`rem`, `gcd`, `lcm`, `floor`, `ceiling`, `truncate`, `round`, `isqrt`,
`integer-length`, `parse-integer`, `numerator`, `denominator`, `boole`,
`logand`, `logior`, `logxor`, `logeqv`, `lognand`, `lognor`,
`logandc1`, `logandc2`, `logorc1`, `logorc2`, `lognot`, `logtest`,
`logbitp`, `logcount`, `ash`, `ldb`, `ldb-test`, `mask-field`,
`deposit-field`, `byte`, `byte-size`, `byte-position`, `dpb`.

Machbar fuer Fixnums. Volle ANSI-Rundung mit Nebenwerten wird sauber erst mit
Multiple Values.

### Kleine Funktions-Helfer

Bereits da:

`identity`, `funcall`, `apply`.

Fehlt:

`complement`, `constantly`.

## Eingeschraenkt moeglich

Diese Gruppe ist grundsaetzlich machbar, braucht aber neue Objektarten,
Runtime-Vertraege oder deutlich mehr Speicher. Sie sollte nicht als reine
Stdlib-Arbeit begonnen werden.

### Packages und Symbol-Namespace

Intern vorhanden:

`intern` existiert im C-Kern, ist aber nicht Lisp-visible als CL-Package-API.
`symbol-name`, `symbol-count` und `symbol-max` geben eine kleine
lisp65-Introspektionsbasis; `nth-symbol` ist nur als opt-in Diagnose-Primitive
baubar.

Fehlt:

`defpackage`, `in-package`, `make-package`, `find-package`,
`delete-package`, `rename-package`, `list-all-packages`, `package-name`,
`package-nicknames`, `package-use-list`, `package-used-by-list`,
`package-shadowing-symbols`, `packagep`, `intern`, `find-symbol`,
`find-all-symbols`, `export`, `unexport`, `import`, `shadow`,
`shadowing-import`, `use-package`, `unuse-package`, `unintern`,
`do-symbols`, `do-external-symbols`, `do-all-symbols`,
`with-package-iterator`.

### Streams, Dateien und Pathnames

Vorhanden als lisp65-spezifischer Pfad:

`load` und `save` fuer F011/D81, plus interne `%disk-*`-Primitive. Das ist
kein ANSI-Stream-/Pathname-System.

Fehlt:

`open`, `close`, `with-open-file`, `with-open-stream`, `streamp`,
`input-stream-p`, `output-stream-p`, `interactive-stream-p`,
`open-stream-p`, `stream-element-type`, `stream-external-format`,
`make-string-input-stream`, `make-string-output-stream`,
`get-output-stream-string`, `make-broadcast-stream`,
`make-concatenated-stream`, `make-echo-stream`, `make-synonym-stream`,
`make-two-way-stream`, `read-byte`, `write-byte`, `read-sequence`,
`write-sequence`, `listen`, `clear-input`, `clear-output`,
`finish-output`, `force-output`, `probe-file`, `truename`, `rename-file`,
`delete-file`, `file-author`, `file-write-date`, `file-length`,
`file-position`, `file-string-length`, `directory`,
`ensure-directories-exist`, `pathname`, `make-pathname`, `pathnamep`,
`pathname-host`, `pathname-device`, `pathname-directory`, `pathname-name`,
`pathname-type`, `pathname-version`, `namestring`, `parse-namestring`,
`merge-pathnames`, `translate-pathname`, `logical-pathname`,
`translate-logical-pathname`, `load-logical-pathname-translations`.

### Arrays, Vektoren und Bit-Vektoren

Fehlt:

`make-array`, `aref`, `row-major-aref`, `svref`, `vector`, `vectorp`,
`simple-vector-p`, `arrayp`, `array-rank`, `array-dimension`,
`array-dimensions`, `array-total-size`, `array-in-bounds-p`,
`array-row-major-index`, `array-element-type`, `array-has-fill-pointer-p`,
`fill-pointer`, `vector-push`, `vector-push-extend`, `vector-pop`,
`adjust-array`, `adjustable-array-p`, `array-displacement`, `bit`, `sbit`,
`bit-vector-p`, `simple-bit-vector-p`, `bit-and`, `bit-ior`, `bit-xor`,
`bit-eqv`, `bit-nand`, `bit-nor`, `bit-andc1`, `bit-andc2`, `bit-orc1`,
`bit-orc2`, `bit-not`.

Ohne kompakte Vektor-/Array-Repraesentation waeren diese auf Conses zu teuer
und nicht ANSI-aehnlich genug.

### Hash-Tabellen

Fehlt:

`make-hash-table`, `hash-table-p`, `gethash`, `remhash`, `clrhash`,
`maphash`, `hash-table-count`, `hash-table-size`, `hash-table-test`,
`hash-table-rehash-size`, `hash-table-rehash-threshold`,
`with-hash-table-iterator`, `sxhash`.

Braucht eine native oder sehr sorgfaeltige Library-Repraesentation.

### Conditions und Restarts

Fehlt:

`condition`, `error`, `cerror`, `signal`, `warn`, `break`,
`invoke-debugger`, `handler-bind`, `handler-case`, `ignore-errors`,
`restart-bind`, `restart-case`, `with-simple-restart`,
`with-condition-restarts`, `compute-restarts`, `find-restart`,
`invoke-restart`, `invoke-restart-interactively`, `abort`, `continue`,
`muffle-warning`, `store-value`, `use-value`, `assert`, `check-type`,
`type-error-datum`, `type-error-expected-type`, `cell-error-name`,
`file-error-pathname`, `stream-error-stream`,
`simple-condition-format-control`, `simple-condition-format-arguments`.

Ein kleines Fehlermodell ist essentiell; ANSI Conditions komplett sind eine
eigene Runtime-Schicht.

### Type-System, Deklarationen und Compiler-Umgebung

Vorhanden als lisp65-System:

`lcc-compile`, `lcc-compile-obj`, `lcc-lits`, `lcc-run`, `function-kind`,
Bytecode-VM, Host-C-Compiler-Referenz, Python-Blob-Builder,
B1-FASL-Emitter (`lib/lcc-fasl.lisp`).

Fehlt als ANSI-CL-Oberflaeche:

`deftype`, `typep`, `subtypep`, `coerce`,
`upgraded-array-element-type`, `upgraded-complex-part-type`, `declare`,
`declaim`, `proclaim`, `the`, `locally`, `special`, `dynamic-extent`,
`inline`, `notinline`, `ftype`, `type`, `optimize`, `speed`, `safety`,
`space`, `debug`, `compilation-speed`, `eval-when`, `macro-function`,
`macroexpand`, `compiler-macro-function`, `define-compiler-macro`,
`compile`, `compile-file`, `compile-file-pathname`,
`with-compilation-unit`, `disassemble`.

Das lisp65-eigene FASL-Modell ist mit B1 begonnen: der Lisp-Emitter schreibt
das gepinnte Disk-Lib-Format. B2/B3 muessen noch `%fasl-save`,
Magic-Dispatch im Loader und Slot-Provisionierung schliessen. Das ist
sinnvoll, aber nicht dasselbe wie ANSI `compile-file` mit Pathnames,
Policies und Compiler-Environment.

### Strukturen und kleine Objekte

Fehlt:

`defstruct`, `copy-structure`, `structure-object`-nahe Semantik,
`print-unreadable-object`.

Machbar als eingeschraenktes Post-MVP-Feature, sobald eine stabile
Objekt-/Slot-Repraesentation existiert. Eine Liste/Plist-Emulation waere
einfach, aber nur begrenzt ANSI-aehnlich.

### CLOS und Generic Functions

Fehlt:

`defclass`, `defgeneric`, `defmethod`, `make-instance`, `slot-value`,
`slot-boundp`, `slot-exists-p`, `slot-makunbound`, `with-accessors`,
`with-slots`, `class-of`, `find-class`, `class-name`, `change-class`,
`allocate-instance`, `initialize-instance`, `reinitialize-instance`,
`shared-initialize`, `update-instance-for-redefined-class`,
`update-instance-for-different-class`, `make-instances-obsolete`,
`ensure-generic-function`, `add-method`, `remove-method`, `find-method`,
`compute-applicable-methods`, `call-next-method`, `next-method-p`,
`no-applicable-method`, `no-next-method`, `method-qualifiers`,
`function-keywords`, `define-method-combination`,
`method-combination-error`, `invalid-method-error`.

Ein Mini-CLOS ist denkbar; ANSI CLOS voll ist fuer das Zielsystem sehr teuer.

### Readtables und Reader-Makros

Fehlt:

`readtablep`, `copy-readtable`, `readtable-case`, `get-macro-character`,
`set-macro-character`, `make-dispatch-macro-character`,
`get-dispatch-macro-character`, `set-dispatch-macro-character`,
`set-syntax-from-char`, `read-preserving-whitespace`.

Der aktuelle Reader ist bewusst klein. Ein voll konfigurierbarer ANSI-Reader
ist spaet.

## Ausgeschlossen aus dem MEGA65-Produktziel

Diese Gruppe ist nicht mathematisch unmoeglich, aber fuer lisp65 auf dem
MEGA65 nicht sinnvoll als Ziel "voller ANSI CL". Teile koennen hostseitig,
als optionale Libraries oder als stark eingeschraenkte Varianten entstehen.

### Voller numerischer Tower

Ausgeschlossen fuer das on-device Produktziel:

Bignums, Ratios, komplexe Zahlen, Floats und die volle generische Arithmetik:
`bignum`, `ratio`, `rational`, `rationalp`, `rationalize`, `float`,
`floatp`, `short-float`, `single-float`, `double-float`, `long-float`,
`complex`, `complexp`, `realp`, `realpart`, `imagpart`, `conjugate`,
`phase`, `cis`, `sqrt`, `isqrt` mit grossen Zahlen, `exp`, `expt`, `log`,
`sin`, `cos`, `tan`, `asin`, `acos`, `atan`, `sinh`, `cosh`, `tanh`,
`asinh`, `acosh`, `atanh`, `decode-float`, `integer-decode-float`,
`scale-float`, `float-digits`, `float-precision`, `float-radix`,
`float-sign`.

Fixnums und lisp65-Fixed-Point bleiben der pragmatische Pfad.

### Voller Pretty Printer und FORMAT

Ausgeschlossen fuer das on-device Produktziel als ANSI-vollstaendige Variante:

`format` komplett, `formatter`, `pprint`, `pprint-fill`, `pprint-linear`,
`pprint-tabular`, `pprint-logical-block`, `pprint-pop`,
`pprint-exit-if-list-exhausted`, `pprint-newline`, `pprint-indent`,
`pprint-tab`, `pprint-dispatch`, `copy-pprint-dispatch`,
`set-pprint-dispatch`.

Ein kleines `format`-Subset bleibt sinnvoll und existiert bereits
host-/bytecode-getestet.

### Voller ANSI-Compiler/Debugger/Development-Stack

Ausgeschlossen als exakte ANSI-Schicht im on-device Produkt:

`step`, `trace`, `untrace`, `time`, `room`, `ed`, `inspect`,
`describe`, `describe-object`, `documentation`, `dribble`, `apropos`,
`apropos-list` in voller ANSI-Semantik.

lisp65 hat stattdessen eigene IDE-/Compiler-/Introspektionspfade (`ide-*`,
`lcc-*`, `symbol-count`, `symbol-max`, `function-kind`; `nth-symbol` optional
im Diagnosebuild). Diese sollen wachsen,
muessen aber nicht ANSI-identisch sein.

### Volle Host-/System-Umgebung

Ausgeschlossen oder nur als sehr kleine Stubs sinnvoll:

`machine-instance`, `machine-type`, `machine-version`, `software-type`,
`software-version`, `lisp-implementation-type`,
`lisp-implementation-version`, `short-site-name`, `long-site-name`,
`get-universal-time`, `decode-universal-time`, `encode-universal-time`,
`get-decoded-time`, `get-internal-real-time`, `get-internal-run-time`,
`sleep`, `y-or-n-p`, `yes-or-no-p`.

### Vollstaendige Unicode-/Character-Semantik

Ausgeschlossen fuer das on-device Produktziel:

`base-char`, `extended-char`, `standard-char` im ANSI-Sinn, volle
Case-Mappings, Unicode-Namen und locale-nahe Semantik.

ASCII/PETSCII-nahe Fixnum-Zeichen sind ausreichend fuer lisp65.

## Empfohlene Reihenfolge

1. **lcc-Sprache schliessen:** nested quasiquote, `case`-Listenkeys im
   direkten Compilerpfad oder bewusst nur per Makro-Route, `do`,
   `defvar`/`defparameter`-Semantik pinnen, bessere Fehlertexte.
2. **Reader/Printer-Objekt-API:** `read-from-string`, `read`, `write-to-string`,
   `prin1-to-string`, `princ-to-string`, `fresh-line`.
3. **Setf-MVP:** feste Places fuer Variablen, `car`, `cdr`, `symbol-value`,
   `getf`; darauf `incf`, `decf`, `push`, `pop`.
4. **Kontrollfluss:** `block`/`return-from`, `catch`/`throw`,
   `unwind-protect`; danach `return`, `prog1`, `prog2`, kleines `loop`.
5. **Multiple Values:** Runtime-Vertrag + `values`/`multiple-value-bind`;
   danach `floor`/`truncate`/`gethash`-aehnliche APIs sauber designen.
6. **Listen-/String-Breite als ladbare Libs:** `member-if`, `assoc-if`,
   `rassoc`, `copy-tree`, `tree-equal`, `make-list`, `third`..`tenth`,
   `char-code`/`code-char`, ANSI-String-Aliase.
7. **Neue Objektarten:** Vektoren zuerst, dann Hash-Tabellen, dann Packages
   oder Streams je nach IDE-/Load-Prioritaet.

## Nicht verwechseln

- "Name vorhanden" heisst nicht "ANSI-vollstaendige Semantik". Viele Namen
  sind absichtlich Fixnum-/Listen-/String-Subsets.
- "Produktfunktion" heisst nicht "CL-Sprachebene": `ide-*`, `lcc-*`,
  `screen-*`, `%disk-*` und `%...` sind lisp65-spezifisch oder intern.
- "Machbar" heisst nicht "in den Kern". Der Default bleibt: Library zuerst,
  Kernel nur fuer Bootstrap, echte Irreduzibilitaet, Maschinenzugriff oder
  gemessene Hot Paths.
- "Ausgeschlossen" meint das MEGA65-Produktziel. Host-Tools duerfen groessere
  ANSI-nahe Oberflaechen haben, wenn sie der Entwicklung helfen.
