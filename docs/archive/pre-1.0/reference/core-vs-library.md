# lisp65 — Was in den C-Kern gehört und was Lisp-Bibliothek wird

Stand: 2026-06-30. Verbindliches Modell für die Grenze zwischen **Lane K** (C-Kern)
und **Lane L** (Lisp-Bibliothek). **Nicht** vom Lisp64-Modell ausgehen (siehe unten).

## Prinzip: minimaler Kern, große Lisp-Bibliothek

Lisp64 hatte einen **fetten residenten Kern** (viele Funktionen in ASM/C), weil der
C64 das erzwang. lisp65 macht das **Gegenteil**: ein **minimaler C-Kern**, und die
Sprache wird größtenteils **in sich selbst** (Lisp) geschrieben. Das ist das klassische
Lisp-Schema — kleiner korrekter Kern, der Rest als Bibliothek, gut testbar und in
Lane L parallel baubar.

**Kern-Philosophie: puristisch minimal** (Entscheidung 2026-06-30). Nur das absolut
Irreduzible kommt in C; alles Ableitbare wird Lisp — auch Komfort wie `mapcar`/`assoc`.
Performance kommt **nicht** durch einen großen Kern, sondern durch **gemessene
Hot-Path-Promotion** (siehe unten).

## Namespace-Modell: Lisp-2 (CL-treu) — Entscheidung 2026-06-30
lisp65 ist ein **Lisp-2** wie Common Lisp: **getrennte Funktions- und Wert-Zellen**
pro Symbol. `(defun f …)` definiert die *Funktion* `f`; eine Variable `f` ist davon
unabhängig. Eine in einer Variablen gehaltene Funktion wird mit `(funcall g …)`
gerufen; `(function f)` / `#'f` holt das Funktionsobjekt. Operator-Position `(op …)`
schlägt **den Funktions-Namensraum** nach, Wert-Position den Wert-Namensraum.
**Wichtig für Lane L:** Bibliothek und Konformitäts-Fixtures müssen CL-Lisp-2-Semantik
annehmen (`funcall`/`#'`, kein Lisp-1-Verhalten).

## Kriterium: etwas kommt nur dann in den C-Kern, wenn mindestens eines gilt
1. **Bootstrap-nötig** — ohne geht kein Lisp: Reader, Printer, Speicher/GC, eval/apply.
2. **Irreduzibel** — echte Spezialform, nicht als Makro über anderes ausdrückbar.
3. **Maschinenzugriff** — Cons-Zellen-Interna, Fixnum-Arithmetik, `peek`/`poke`/
   Register, roher Zeichen-I/O.
4. **Heißer Pfad** — und das **erst nach Messung**, nicht vorab.

Trifft keines zu → **Lisp-Bibliothek**.

## Die Grenze

### C-Kern (Lane K, `src/**`)
- **Spezialformen (IST-Stand M1.3):** `quote`, `quasiquote` (+ `unquote`/
  `unquote-splicing`), `if`, `lambda`, `setq`, `progn`, `defmacro`, `function`,
  **plus der Makro-Expansions-Hook** (eval erkennt Makros und ruft den in Lisp
  geschriebenen Expander). **MVP-Ausnahme 2026-07-02/03:** `defun`, `when`,
  `unless`, `let`, `let*`, `case`, `dotimes`, `dolist` liegen als C-Special-Forms
  im Kern, weil die Prelude-/REPL-Makros im nativen Bank-0-MVP zu viel
  Heap/Quelltext kosten bzw. rekursive Loop-Makros die VM-Frame-Decke treffen.
  **Kein `define`** (kein Scheme);
  `defvar`/`setq` betreffen die Wert-Zelle. lambda-Listen: feste, `&rest`, dotted,
  voll-variadisch.
- **Primitive (Funktionen):**
  - Zellen: `cons`, `car`, `cdr`, `rplaca`, `rplacd`, `nreverse`
  - Gleichheit/Prädikate: `eq`, `eql`, `consp`, `symbolp`, `numberp`, `null`, `atom`
  - Fixnum-Arithmetik: `+ - * / mod`, Vergleiche `= < > <= >=`
  - Funktionsanwendung: `apply`, `funcall`, `eval`
  - Symbole: `intern`, `gensym`, `set`/`symbol-value`, `boundp`
  - I/O/Printer-Primitive: `write-char`, `write-string`, `terpri`, `princ`,
    `prin1`, `print`, `write`, `write-line` (+ Reader/Printer-Basis). Diese
    CL-nahen Printer-Namen sind eine MVP-Footprint-Ausnahme: als eingebettete
    Bytecode-Stdlib-Funktionen sprengten sie das Stack-Gap-Gate, als Kern-
    Primitive sind sie sofort in der REPL nutzbar.
  - Maschine: `peek`, `poke`, `sys`, rohe MEGA65-Registerzugriffe
- **Mechanismen:** Reader, Printer, Allocator + GC, Fehler-/`catch`/`throw`-Basis.

### Lisp-Bibliothek (Lane L, `lib/**`)
- **Kontroll-Makros:** `cond`, `when`, `unless`, `and`, `or`, `case`, `let`, `let*`,
  `dolist`, `dotimes`, `do`, `loop`.
- **Definitionen:** `defun`, `defmacro`, `defvar`, `defparameter`.
- **Listen/Sequenzen:** `list`, `list*`, `append`, `length`, `reverse`, `nth`,
  `nthcdr`, `last`, `member`, `assoc`, `mapcar`, `mapc`, `remove`, `find`, `position`,
  `reduce`, `every`, `some`, …
- **Höhere Schichten:** `format`, `defstruct`, Conditions, Mini-CLOS.
- **MEGA65-BASIC-10-Komfort:** Grafik (`line`/`rect`/`circle`/`plot`), Sound
  (`tone`/`play`), Sprites — **als Lisp über die `poke`/Register-Primitive**, nicht
  als Kern-Code.

## Der Dreh- und Angelpunkt: `lambda` + `define` + Makro-Mechanismus
Sobald diese drei im Kern stehen, lässt sich **fast die gesamte restliche Sprache als
Lisp** schreiben. Das ist der Punkt, ab dem Lane L die Bibliothek aufbauen kann. Der
Makro-Mechanismus ist entscheidend: er verlagert `cond`/`let`/`defun`/… aus dem Kern
in die Bibliothek.

## Bootstrap der Bibliothek (Design, offen im Detail)
Die Lisp-Bibliothek wird als **Prelude** beim Start geladen (eingebettet ins Image
oder von Disk). Dasselbe Prelude soll auf dem Host-Oracle laufen (Konformität). Genaue
Form (eingebettet vs. Disk-LOAD) ist eine spätere Lane-K/L/T-Abstimmung.

## Hot-Path-Promotion (statt fettem Kern)
Eine Lisp-Funktion wandert **nur dann** nach C, wenn ein **Benchmark** zeigt, dass sie
ein echter Engpass ist. Vorgehen: Mess-Spur einrichten, profilieren, gezielt
promoten, Verhalten gegen die Lisp-Version (Oracle/Tests) absichern. Keine
Vorab-Optimierung in den Kern.

## Konsequenz für die Lanes
- **Lane K** liefert den minimalen Kern + die Primitive als stabile Basis.
- **Lane L** baut die gesamte CL-nahe Oberfläche darauf in Lisp.
- Die Naht ist die **Primitiv-/Spezialform-Liste oben** + die Test-Suiten.
