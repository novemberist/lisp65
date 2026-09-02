# LISP 64 — Dialekt vs. Common Lisp (aktuelle Referenz)

Stand: 2026-06-28. Zweck: die bekannten Abweichungen des LISP-64-Dialekts von
Common Lisp an **einer** Stelle festhalten — als Grundlage für **Phase 6 Stufe 2
(P2)**, den lexikalischen/CL-konformen Schnitt (`development-plan.md` P2,
`roadmap.md`). Die host-verifizierbaren Punkte sind in
`lisp/dialect-vs-cl-tests.lsp` **gepinnt** (Pinning-Tests, im Aggregat
`run-tests.sh`): sie nageln das *aktuelle* Verhalten fest, machen Divergenzen
sichtbar und müssen sich ändern, wenn P2 den CL-Schnitt macht.

Kontext: `architecture.md` (Technik), Memory `host-string-primitives`,
`dialect-semantics`, `f-is-false-atom`.

## 1. Semantische Abweichungen (host-verifiziert, gepinnt)

| Konstrukt | LISP-64-Dialekt | Common Lisp |
| --- | --- | --- |
| `*` | **Kommentarzeichen**, keine Multiplikation; Multiplikation = `TIMES` | `*` = Multiplikation |
| Subtraktion/Negation | **getrennt:** `(DIFFERENCE x y)` = x−y (binär); `(MINUS x)` = −x (**unär**, weitere Argumente ignoriert). Arithmetik allgemein über MacLisp-Namen `PLUS`/`DIFFERENCE`/`TIMES`/`QUOTIENT`/`MINUS`/`ADD1`/`SUB1`; `+ - * /` nur als Host-prelude-Aliase | `-` ist beides: binär subtrahieren **und** unär negieren |
| `LAST` | letztes **Element**: `(LAST '(1 2 3))` → `3` | letzter Cons → `(3)` |
| `NTH` | `(NTH liste n)`, **1-basiert**, liefert die **Teilliste** ab Position n: `(NTH '(a b c d) 2)` → `(b c d)`; Element via `(CAR (NTH …))` | `(nth n liste)`, 0-basiert, liefert das **Element** |
| `MOD` | = `REMAINDER` (Vorzeichen des **Dividenden**): `(MOD -7 3)` → `-1` | `(MOD -7 3)` → `2` (Vorzeichen des Divisors); `(REM -7 3)` → `-1` |

Hinweis: Das in dieser Session ergänzte `cl-compat:REM` ist **konsistent zum
Dialekt-`MOD`** definiert (`= REMAINDER`), nicht zur CL-`REM`/`MOD`-Unterscheidung.
Eine echte CL-konforme `MOD`/`REM`-Trennung gehört in den P2-Schnitt.

## 2. Native-Runtime-Eigenheiten (NICHT im Host-Interpreter modelliert)

Diese gelten für den **C64-Native-Build**, nicht für `tools/host-lisp/lisp64.py`
— daher nicht host-pinnbar, aber für Gerätearbeit wichtig:

- **`F` ist der False-Atom-Sonderfall.** `(DE F …)` lässt sich definieren, ein
  späterer Aufruf `(F …)` endet aber als `UNDEFINED FUNCTION` (False/NIL-Pfad).
  Befund aus dem R2-Smoke (2026-06-28). Der **Host** behandelt `F` als normales
  Symbol (`(SETQ F 7)` → `7`). → In Tests/Code nie `F` als Funktions-/Variablenname
  verwenden; neutrale Namen (`G`, `V`, …). Memory `f-is-false-atom`.
- **`PROG`-Marken sind nicht reentrant.** Ein `PROG` mit **zwei** `GO`-Schleifen
  (z. B. Clear-Loop `L` + Freeze-Loop `M`) bzw. das Aufrufen einer PROG-haltigen
  Funktion aus einem PROG heraus bricht den Kontrollfluss auf dem Native-Build
  (Top-Level-`PROG` mit *einem* Label funktioniert). Konsequenz auch in `cl-compat`:
  `DOTIMES`/`DOLIST` nutzen die feste Marke `LOOP` und sind daher **nicht
  verschachtelbar**; `CASE`/`ECASE` (LAMBDA-gebunden) hingegen schon. Auf dem Host
  tritt die Grenze nicht auf. Befund aus dem Platform-Device-Smoke (2026-06-28).

## 3. Auf dem Host nicht baubare CL-Features (Interpreter-Ebene)

- **String-Manipulation.** Der Host-Interpreter hat keine Primitive für
  String-Länge, Zeichen-Indizierung oder Zeichen→Code (`(LENGTH "abc")` → `0`;
  `GETCHAR` indiziert nicht; kein `EXPLODE`/`INTERN`/`SYMBOL-NAME`). Vorhanden:
  `STRINGP`, `CHAR` (= **Code→Zeichen**, `(CHAR 65)` → `"A"`), `READ-FROM-STRING`.
  → CL-String-Funktionen (`STRING-UPCASE`, `CHAR`-Index, `STRING=`,
  `CONCATENATE`, `SUBSEQ` auf Strings) sind **nicht als ladbare Lisp-Lib**
  implementierbar; das wäre Interpreter-Arbeit. Memory `host-string-primitives`.

## 4. Bereits CL-konform über `cl-compat.lsp` (Stufe 1)

Die Kompatibilitätsschicht bildet viele CL-Namen auf Dialekt-Primitive ab. Diese
Session ergänzt (host-getestet, `cl-compat-tests` PASS=97):

- **Control/Utility:** `CASE`/`ECASE` (verschachtelbar), `IDENTITY`, `GETF`,
  `ACONS`, `PAIRLIS`.
- **Listen:** `COPY-LIST`/`COPY-TREE`/`COPY-ALIST`, `REVAPPEND`, `LIST*`,
  `MAKE-LIST`, `ADJOIN`, `SUBST`.
- **Zahlen:** `PLUSP`, `REM`, `SIGNUM`, `EXPT`, `MAX`/`MIN`, `GCD`/`LCM`.
- **Higher-order:** `MAPCON`, `NOTANY`, `NOTEVERY`, `DELETE-IF`.
- **Typen/alist:** `SYMBOLP`, `TYPEP`, `RASSOC`; `SET-DIFFERENCE` (lib-sets).

Schon vorher vorhanden u. a.: `WHEN`/`UNLESS`, `DOLIST`/`DOTIMES`, `LET*`, `SETF`,
`INCF`/`DECF`, `REDUCE`, `EVERY`/`SOME`, `FIND`/`POSITION`, `REMOVE-IF`,
`BUTLAST`, `NTHCDR`, `PUSH`/`POP`.

## 5. Fexpr/Makro statt `defmacro`

`DE` definiert eine Funktion (Argumente werden **ausgewertet**, EXPR-Semantik wie
ein CL-`defun`). `DF` definiert einen **FEXPR** (unausgewertete Argumente), `DM`
einen **Makro**. CL kennt keine Fexprs und nutzt `defmacro` + Auswertungsregeln;
der CL-konforme Pfad (Makros/Backquote) ist Teil von P2. Bindungsdetails von
`DF`/`DM` siehe Memory `dialect-semantics`.

## 6. Was hier (noch) NICHT steht

`NULL`/`ATOM`/`CONSP`/`LISTP`/`NUMBERP`/`MEMBER`/`ASSOC`/`EQ`/`EQUAL`/`REMOVE`
verhalten sich für die Kernfälle CL-nah (z. B. `(MEMBER 2 '(1 2 3))` → `(2 3)`,
`(ASSOC 2 …)` mit Zahlschlüssel, `EQ` auf Fixnums → `T`). Feinheiten der
`EQ`/`EQL`/`EQUAL`-Stufung und der `:test`/`:key`-Schlüsselwortargumente sind
bewusst dem P2-Schnitt vorbehalten und hier nicht gepinnt.
