# lisp65 — Bytecode-ABI (P0, der Vertrag Compiler ↔ VM)

**Stand: 2026-07-12. P0 GEPINNT, CodeObject-Arity additiv erweitert.**
Dies ist die *einzige* Schnittstelle zwischen Codex' Compiler/Host-VM (Lanes T) und Claudes
C-VM + Streaming-Loader (Lane K). Solange dieser Vertrag steht, arbeiten beide Lanes unabhängig
(Plan: `docs/bytecode-parallel-plan.md`). Basis + Freeze-Disziplin von
`../lisp64v2026/docs/bytecode-v1.md`, angepasst an das lisp65-obj-Modell und um Streaming erweitert.

> **Freeze-Disziplin:** Opcode-Nummern und Byte-Layouts sind ab Pinnen stabil. **Neue Opcodes
> kommen hinten dazu** (nie Nummern umbelegen). Änderungen hier vorher in `collaboration.md`
> ankündigen (Interface-Regel). Quelle der Wahrheit für Opcode-Nummern = dieses Dokument; ein
> Drift-Check (Codex, T4) hält Compiler/VM/Doc synchron.

## 1. Wertemodell (WICHTIG — anders als bytecode-v1)

Der VM-Wert-Stack hält **`obj`** (die native lisp65-16-Bit-getaggte Referenz aus `src/obj.h`),
KEINE 32-Bit-Ints wie die alte C64-VM:
- `NIL   = 0`
- `Fixnum= (n<<1)|1`, 15-Bit signed (`MKFIX`/`FIXVAL`)
- `Zeiger= gerade, != 0` (Zellindex<<1; Zelltyp in der Zelle)

**Konsequenzen:**
- Arithmetik-Opcodes operieren auf **15-Bit-Fixnums**, **signed, Wraparound in 15 Bit**
  (Ergebnis mod 2^15, als Fixnum re-getaggt). Nicht-Fixnum-Operanden = VM-Status `TypeError`.
  **`DIV`/`REMAINDER` durch 0 → `TypeError`** (kein Trap/Crash).
- `T` = das internierte Symbol `t` (die VM hält seinen `obj` im Root-Kontext, s.u.), `NIL`=0.
- Boolesche Ergebnisse: wahr → `t`, falsch → `NIL`.
- Datenzugriff (`CONS/CAR/CDR/…`) läuft über die **hot cons-Heap-Accessoren** (`src/obj.h`).
  Laufzeit-Zellen bleiben hot in Bank 0.

## 2. Code-Objekt-Format (im Build erzeugt, im erw. RAM abgelegt)

Ein kompiliertes Code-Objekt (eine Funktion) ist eine flache Byte-Sequenz:

| Offset | Größe | Feld | Bedeutung |
| ---: | ---: | --- | --- |
| 0 | 1 | `magic` | `$B5` (lisp65-Bytecode-Code-Objekt; vgl. bytecode-v1 `$B4`) |
| 1 | 1 | `nargs` | Anzahl fixer Parameter (0..255) |
| 2 | 1 | `nlocals` | zusätzliche lokale Frame-Slots (LET/temporär) |
| 3 | 1 | `flags` | CodeObject-Flags; Belegung und Arity-Semantik siehe unten |
| 4–5 | 2 | `code_len` | Länge der Payload in Bytes (LE) |
| 6 | 1 | `nlits` | Anzahl Literaltabellen-Einträge |
| 7… | 2·nlits | `littab` | Literaltabelle: je Eintrag ein `obj` (LE, 2 Byte) |
| … | code_len | `payload` | die Bytecode-Sequenz |

**Literale:** jeder Eintrag ist ein fertiger `obj`. Fixnums/`NIL`/`t` stehen direkt drin.
Zusammengesetzte Literale (Listen/Strings/Symbole) werden beim **Laden** des Code-Directorys in
den hot-Heap materialisiert und der Tabelleneintrag auf den erzeugten `obj` gesetzt (Loader-Aufgabe,
Detail in §5). `PUSHLIT idx` schiebt `littab[idx]`.

**GC-Rooting (verbindlich):** Die materialisierten Literaltabellen ALLER geladenen Code-Objekte
sind **permanente GC-Roots** — `gc_collect` traversiert sie zusätzlich zu Symbolen + gc_rootstack
(die geladenen Literaltabellen liegen als hot Bank-0-Array vor; ihre `obj`-Einträge werden gemarkt).
Damit überleben komplexe Literale den GC unabhängig davon, ob gerade ein PUSHLIT sie auf dem Stack hält.

**Embed-Literal-Artefakt:** Das eingefrorene Host-Artefaktformat fuer diese Loader-Aufgabe
(`lisp65_bc_literal_node`, Kind-Codes 0..7, `literal_patches[]`, Runtime-Symbole
`lisp65_stdlib_blob`/`lisp65_embed`) ist in `docs/bytecode-embed-loader.md` spezifiziert.
Die Bytecode-ABI bleibt das flache Code-Objektformat; die Literal-Node-Tabellen sind Loader-
Metadaten und aendern die Bytes des Code-Objekts nicht.

### 2a. CodeObject-Flags und Arity

Das vorhandene Header-Byte an Offset 3 wird ohne Format- oder Laengenaenderung
vollstaendig belegt:

| Bits | Name | Bedeutung |
| ---: | --- | --- |
| 0 | `REST` | Funktion besitzt `&rest`; der Restwert liegt im ersten zusaetzlichen Local-Slot |
| 1 | `STRICT_ARITY` | VM prueft die im Artefakt gebundene Argumentzahl vor dem Frame-Aufbau |
| 7..2 | `optional_count` | Anzahl optionaler Parameter, unsigned 6 Bit (`0..63`) |

Dabei bezeichnet `nargs` die maximale Anzahl nicht-`&rest`-Parameter. Es gilt:

```text
required_count = nargs - optional_count
ohne REST: required_count <= actual_count <= nargs
mit REST:  required_count <= actual_count
```

`optional_count > 0` ist nur zusammen mit `STRICT_ARITY` gueltig und darf
`nargs` nicht ueberschreiten. `REST` verlangt mindestens einen Local-Slot fuer
die erzeugte Restliste. Verletzt ein CodeObject diese Forminvarianten, lehnen
Preflight beziehungsweise VM es als ungueltigen Bytecode ab. Eine gueltige,
aber nicht passende Argumentzahl liefert den getrennten VM-Status `ArityError`
beziehungsweise den stabilen Fehlercode `wrong-argument-count`.

Dialect-v1-Artefakte bleiben bytegenau ausfuehrbar: Ist `STRICT_ARITY` nicht
gesetzt, muss `optional_count` null sein und die historische Semantik bleibt
erhalten. Fehlende feste Argumente werden mit `NIL` aufgefuellt; ueberzaehlige
Argumente werden verworfen, sofern `REST` sie nicht sammelt. Dialect-v2-Emitter
setzen `STRICT_ARITY`; dadurch kann etwa ein binaeres `/=` weder still fehlende
noch zusaetzliche Argumente akzeptieren. Das harte v2-Loader-/VM-Profil verlangt
das Flag; flaglose v1-Artefakte bleiben dauerhaft dekodierbar, werden dort aber
nicht mit laxem NIL-Padding ausgefuehrt.

Der Python-Compiler behaelt `strict_arity=False` als Default und damit seine
v1-Bytes; das v2-Profil setzt die Option fuer Hauptfunktion und Lambda-Helper.
Der residente LCC bleibt ebenfalls v1-unveraendert. Erst das v2-Build laedt
`lib/dialect-v2/lcc-profile.lisp`, das `%lcc-finish` mit `STRICT_ARITY`
ersetzt und die entfernten `do`-/`remainder`-Lowerings ausblendet.
Source-Lowering fuer optionale Parameter ist noch nicht
Teil dieses Blocks; `optional_count` definiert und reserviert bereits dessen
Artefaktsemantik, die Quellsprache emittiert derzeit aber null optionale
Parameter.

Die Belegung ist maschinenlesbar in
`config/code-object-arity-contract.json` gebunden. Der Host-Report
`tools/host-lisp/code_object_arity_contract.py` prueft Layout, Forminvarianten,
Executor-/Validator-Drift und das native Codegroessenbudget. Er erhebt keine
Zyklus-Latenzbehauptung; Zielzyklen bleiben bis zu einer Hardwaremessung
ausdruecklich `not-measured`.

**Nicht verwechseln:** Directory-Entry-Flags sind ein eigener Bitraum. Dort
markiert Bit 0 weiterhin einen Makroeintrag (`T_MACRO(BCODE)`), und alle anderen
Bits bleiben reserviert. Directory-Entry-Flags werden nicht in das CodeObject-
Headerfeld uebernommen.

## 3. Operandenformate

| Kürzel | Bytes | Bedeutung |
| --- | ---: | --- |
| `none` | 0 | kein Operand |
| `u8` | 1 | vorzeichenlos |
| `s8` | 1 | vorzeichenbehaftet |
| `idx` | 1 | Literaltabellen-Index (0..254; 255 reserviert) |
| `rel8` | 1 | signed, relativ zum **folgenden** Opcode-Byte (Branch) |
| `u16` | 2 | LE |
| `idx+u8` | 2 | Byte 0 = Literaltabellen-Index (Callee-Symbol), Byte 1 = Arg-Anzahl (CALL/TAILCALL) |
| `pid+u8` | 2 | Byte 0 = **gefrorene Prim-ID** (§4a), Byte 1 = Arg-Anzahl (CALLPRIM) |

> `u8u8` (Frame-Tiefe+Slot) ist **reserviert** für die spätere lexikalische LOADL/STOREL
> (Closures, Opcodes ≥64). Im v1-Kern haben LOADL/STOREL nur `u8` (Slot im aktuellen Frame).

## 4. ISA v1 (Kern — eingefroren beim Pinnen; erweiterbar hinten)

Nummern folgen bytecode-v1, wo die Semantik passt; lisp65-Ergänzungen sind markiert (**L**).

| # | Mnemonic | Op | Wirkung (Stack) |
| ---: | --- | --- | --- |
| 0 | HALT | none | VM anhalten, TOS = Ergebnis |
| 1 | PUSHI8 | s8 | push Fixnum(imm) |
| 2 | ADD | none | a b → a+b (Fixnum) |
| 6 | PUSHLIT | idx | push littab[idx] |
| 11–13 | PUSHARG0/1/2 | none | push Argument 0/1/2 des aktuellen Frames |
| 14 | SUB | none | a b → a-b |
| 15 | MUL | none | a b → a*b |
| 16 | DIV | none | a b → a/b |
| **17** | **MOD** (L) | none | a b → Common-Lisp-`mod` (Rest hat das Vorzeichen des Divisors) |
| 18 | LESS | none | a b → (a<b) → t|nil |
| 19 | GREATER | none | a b → (a>b) |
| 24 | REMAINDER | none | a b → truncierender C-Rest `a % b` (Vorzeichen des Dividenden) |
| 28 | JMPREL | rel8 | unbedingter Sprung |
| 29 | JFALSEREL | rel8 | Sprung wenn TOS = NIL (pop) |
| 30 | EQ | none | a b → (eq a b) |
| 42 | NOT | none | a → (null a) |
| 43 | PUSHNIL | none | push NIL |
| 44 | PUSHT | none | push t |
| 5 | RET | none | Frame verlassen, TOS = Rückgabe |
| **51** | **CONS** (L) | none | a b → (cons a b) — alloziert hot |
| **52** | **CAR** (L) | none | a → (car a) |
| **53** | **CDR** (L) | none | a → (cdr a) |
| **54** | **CONSP** (L) | none | a → (consp a) → t|nil |
| **55** | **EQL** (L) | none | a b → (eql a b) |
| **56** | **PUSHARGN** (L) | u8 | push Argument n (n>2) |
| **57** | **LOADL** (L) | u8 | push Frame-Slot n (0..nargs+nlocals-1) |
| **58** | **STOREL** (L) | u8 | pop → Frame-Slot n |
| **59** | **DROP** (L) | none | TOS verwerfen |
| **60** | **CALL** (L) | idx+u8 | Callee = littab[idx] (Symbol), u8 Args auf Stack. Laufzeit-Auflösung: Directory-Treffer → VM-Code-Root; **Fehltreffer → Tree-Walker-Bridge** (§5) |
| **61** | **CALLPRIM** (L) | pid+u8 | C-Primitive via **gefrorene Prim-ID** (§4a), u8 Args |
| **62** | **TAILCALL** (L) | idx+u8 | wie CALL, aber Frame wiederverwenden (TCO); nur bei VM-Code-Root-Treffer, sonst wie CALL |
| **63** | **CLOSURE** (L) | idx+u8 | Closure bauen: Byte 0 = Helper-Symbol in `littab`, Byte 1 = Anzahl Upvalues; poppt Upvalue-Werte, pusht `T_CLOSURE` |
| **64** | **UPVAL** (L) | u8 | push Upvalue n des aktuellen Closure-Frames |
| **65** | **SETUPVAL** (L) | u8 | pop Wert und schreibe Upvalue n des aktuellen Closure-Frames; Phase-2-ABI fuer per-Closure-mutierbare Captures |

P0-Slot 17 war vor dieser Erweiterung ungueltig und wurde von allen P0-Decodern
abgelehnt. Das historische, nicht P0-kompatible Referenzformat verwendete 17 als
`PRINTBOOL`; dessen Artefakte waren bereits vor `MOD` keine gueltigen P0-Objekte.

**Compiler-Surface (P0, 2026-07-02):** `dotimes` und `dolist` werden direkt in
`LOADL`/`STOREL` plus `JMPREL`/`JFALSEREL` geloopt, nicht ueber rekursive
Lisp-Makros. Die rel8-Operands begrenzen v1-Loop-Bodies auf den lokalen
Sprungbereich; der Compiler muss bei Ueberlauf hart mit einer rel8-Diagnose
abbrechen. `dotimes` wertet das Result mit `var=count` aus, `dolist` mit
`var=nil`. Die Loop-Variable ist eine mutierte Binding-Zelle; spaetere Closures
sehen daher den letzten Wert. Literale aus der `littab` sind permanent gerootet
und geteilt: destruktive Operationen wie `nreverse`/`rplaca`/`rplacd` auf
gequoteten Literalen haben wie in CL undefinierte Programmsemantik.

> **Nummern 66+ = reserviert** (frei für Erweiterungen). **`nlits` ist `u8`** → max **255 Literale
> je Code-Objekt** (reicht für eine Funktion). `PUSHLIT16` + `nlits=u16` sind **zurückgestellt**
> (erst falls ein Objekt >255 Literale braucht; dann Opcode ≥66 + Header-Bump, angekündigt).
> **Provisorisch (Opcodes ≥66, nach v1-Kern grün auf HW):** `&rest`-Sammlung, lexikalische
> LOADL/STOREL (`u8u8`, falls OP_UPVAL nicht reicht),
> `MAPCAR`-Fastpath, Directory-Index-Fast-Call (u16, als CALL-Optimierung).

## 4a. Gefrorene Prim-ID-Tabelle (für CALLPRIM — stabile ABI, NICHT die eval.c-enum)

CALLPRIM adressiert C-Primitive über **stabile, hier eingefrorene** IDs — **entkoppelt** von der
`P_*`-`enum`-Reihenfolge in `src/eval.c`. Die C-VM übersetzt Prim-ID → Primitive (eigener
Switch/Tabelle in der VM), sodass die enum in eval.c frei umsortiert werden darf. Häufige Ops
(ADD/CAR/CONS/…) sind eigene Opcodes und stehen NICHT hier. CALLPRIM ist für die restlichen
Stdlib-Primitive. Startsatz (weitere kommen hinten dazu, nie umnummeriert):

| Prim-ID | Primitive |
| ---: | --- |
| 0 | `stringp` |
| 1 | `string->list` |
| 2 | `list->string` |
| 3 | `string-length` |
| 4 | `string-ref` |
| 5 | `symbolp` |
| 6 | `numberp` |
| 7 | `apply` |
| 8 | `funcall` |
| 9 | `screen-size` |
| 10 | `screen-clear` |
| 11 | `screen-put-char` |
| 12 | `screen-write-string` |
| 13 | `read-key` |
| 14 | `poll-key` |
| 15 | `%disk-read-sector` |
| 16 | `%disk-byte` |
| 17 | `%disk-load-file` |
| 18 | `%disk-load-lib` |
| 19 | `symbol-value` |
| 20 | `set-symbol-value` |
| 21 | `%disk-poke` |
| 22 | `%disk-write-sector` |
| 23 | `nreverse` |
| 24 | `rplaca` |
| 25 | `rplacd` |
| 26 | `%string-slice` |
| 27 | `%string-concat-list` |
| 28 | `%string-codes` |
| 29 | `%string-from-codes` |
| 30 | `%cs-read-open` |
| 31 | `%fasl-read-form` |
| 32 | `%fasl-stage` |
| 33 | `%fasl-stage-get` |
| 34 | `%save-staged` |
| 35 | `%set-macro` |
| 36 | `function-kind` |
| 37 | `gensym` |
| 38 | `lcc-install` |
| 39 | `macroexpand-1` |
| 40 | `number->string` |
| 41 | `prin1` |
| 42 | `symbol-count` |
| 43 | `symbol-max` |
| 44 | `symbol-name` |
| 45 | `write-char` |
| 46 | `%fasl-error-entries-overflow` |
| 47 | `%fasl-error-nodes-overflow` |
| 48 | `%fasl-error-not-a-defun` |
| 49 | `%fasl-error-output-overflow` |
| 50 | `%fasl-error-patches-overflow` |
| 51 | `%fasl-error-strings-overflow` |
| 52 | `%fasl-error-too-many-helpers` |
| 53 | `%fasl-error-unsupported-literal` |
| 54 | `%fasl-error-window-overflow` |
| 55 | `%lcc-error-do-body-too-big` |
| 56 | `%lcc-error-invalid-parameter-list` |
| 57 | `boundp` |
| 58 | `%list-malformed-error` |
| 59 | `set` |
| 60 | `key-event` |
| 61 | `peek` |
| 62 | `poke` |

Die Tabelle erhaelt Decoder-Namen unabhaengig vom Profilstatus. Prim-ID 34 ist
im eingefrorenen v1-Profil weiterhin `%save-staged`; im v2-Profil ist sie nach
der FASL-Bytecode-Verlagerung ein permanenter Tombstone. Neue v2-Artefakte
duerfen ID 34 nicht emittieren, die ID wird nie wiederverwendet.

Opcode-IDs und Prim-IDs sind getrennte 8-Bit-Nummernraeume. Die Prim-IDs
0--22 bleiben im eingefrorenen `dialect-v1` aktiv; 23--255 bleiben dort
reserviert. `dialect-v2` fuehrt 23--57 ein und tombstoned die historischen
Konverter 1 (`string->list`), 2 (`list->string`) sowie den nach Bank 5
verlagerten Service 40 (`number->string`) permanent; ID 40 bleibt im
eingefrorenen v1-Profil reserviert und 63--255 bleiben in v2 reserviert.
Tombstones behalten Namen und Dekodierbarkeit, duerfen aber nicht mehr
emittiert oder wiederverwendet werden. Die IDs 26--29 sind ausschliesslich interne Compiler-/VM-
Capabilities: Sie werden nicht exportiert und weder `funcall` noch `apply`
darf sie als Function-Designator aufloesen. Direkte CALLPRIM-Absenkung bleibt
internen Library-Quellen vorbehalten. IDs 28/29 tragen nur den mechanischen
Workbench-v2-Artefaktabschluss; sie stellen die entfernten Konverternamen nicht
als Dialektoberflaeche wieder her. `nreverse`, `rplaca` und `rplacd` sind
dagegen oeffentliche v2-Function-Designators. IDs 30--56 bilden die statische
Artifact-Closure-Service-Schicht. Prozent-Namen sind keine Function-Designators;
die Native Services 36--45 duerfen ueber `funcall`/`apply` aufgeloest werden.
Bis der residente C-Dispatcher implementiert ist, bleibt ihr eigener
Staging-Dispatch-Gate rot; ABI-Allokation und Emitter behaupten keine Semantik.

> Verbindlich: Diese Tabelle ist die Quelle der Wahrheit. `src/vm.c` bietet den stabilen
> Dispatch `vm_callprim(u8, ...)`; die Host-VM spiegelt dieselbe Tabelle. Der Drift-Check (T4)
> hält Compiler/VM/Host-VM/Doc synchron.
>
> M0-Disk-Write-Caveat (2026-07-09): Prim-IDs 21/22 sind Maschinenraum-IDs fuer
> host-kompilierte Disk-Allocator-Libs. Die C-VM-Cases sind aus Workbench-
> Budgetgruenden intern/unchecked; keine Arity-/Typvalidierung. Eine
> user-sichtbare Schicht muss vor dem Aufruf validieren. Der Device-LCC mappt
> diese Namen direkt auf CALLPRIM; sie bleiben dennoch interne Compiler-Surface.

## 5. Code-Directory + Streaming-Layout (lisp65-neu, der HW-taugliche Teil)

Alle Code-Objekte der Stdlib liegen **flach hintereinander im erweiterten RAM** (ab einer
Basis-Bank, z. B. `$50000`). Ein **Directory** (im hot Bank-0, klein) indiziert sie:

| Feld je Directory-Eintrag | Größe | Bedeutung |
| --- | ---: | --- |
| `name_sym` | 2 | `obj` des Funktions-Symbols (hot interniert), LE |
| `ext_addr` | 3 | Adresse des Code-Objekts im erw. RAM: Byte 0 `off_lo`, Byte 1 `off_hi`, Byte 2 `bank` (flach = `bank*$10000 + off`) |
| `obj_len` | 2 | Gesamtlänge des Code-Objekts (Header+littab+payload), LE |

- **Aufruf-Auflösung (symbolbasiert):** `CALL`/`TAILCALL` liefern per `idx` das Callee-**Symbol**
  (`littab[idx]`, ein interniertes hot-Symbol). Die VM sucht es im Directory über `name_sym`
  (wenige Einträge, hot → linearer Scan oder ein Symbol→Eintrag-Index). **Treffer** → das Code-Objekt
  wird gestreamt + ausgeführt (VM-Code-Root). **Fehltreffer** → die VM reicht Symbol+Args an den
  **Tree-Walker** durch (Hybrid-Bridge, wie bytecode-v1 §REPL-Integration). *(Ein direkter
  Directory-Index-Fast-Call ist eine spätere Optimierung, Opcode ≥63 — im v1-Kern gibt es NUR den
  symbolbasierten Weg.)*
- **Streaming (Lane K):** die VM hält einen kleinen **hot Payload-Puffer** (z. B. 256 B). Der
  Program-Counter läuft über die flache `ext_addr+offset`; überschreitet er das Pufferfenster,
  füllt ein **Bulk-DMA** (bewiesen 🟢) das nächste Segment nach. **Kein** Einzelzellen-DMA während
  der Ausführung. Header + Literaltabelle werden beim Laden **einmal** in hot kopiert (klein).

## 6. Ausführungsmodell (VM, Lane K)
Stack-VM: Wert-Stack (obj), Return-/Frame-Stack (Frames: Basiszeiger auf Args+Locals im hot-Heap
oder in einem hot-Frame-Array), Root-Kontext (hält `t`, das Directory, den Fixnum-Overflow-Modus).
Opcode holen (aus dem hot Payload-Puffer, per Streaming nachgefüllt) → bounds-check → Dispatch.
Statuscodes: `OK, Halt, BadOpcode, TypeError, StackOver, HeapOOM, DirMiss,
StepLimit, ArityError`.

## 7. Goldene Testvektoren (Cross-Lane-Naht)
Ablage `tests/bytecode/` (Lane T). Je Fall: `{ quelltext, code_obj_hex, args, ergebnis_obj }`.
- Codex: Compiler erzeugt `code_obj_hex`; Host-VM liefert `ergebnis_obj`.
- Claude: die C-VM lädt `code_obj_hex`, führt mit `args` aus, muss `ergebnis_obj` liefern.
Startsatz (Phase-1-Spike, hand-verifizierbar): Identität, `(+ a b)`, `(if (< a b) a b)`,
`(cons a b)` + `car`/`cdr`, eine rekursive Fn mit `CALL` (z. B. `length`).

## 8. Review-Runde 1 (Codex, 2026-07-01) — alle 7 Punkte adressiert
1. **CALL/TAILCALL/CALLPRIM-Operandformen** → §3 definiert `idx+u8` (CALL/TAILCALL) und `pid+u8`
   (CALLPRIM) explizit.
2. **LOADL/STOREL widersprüchlich** → v1-Kern nutzt **`u8`** (Slot im aktuellen Frame); `u8u8`
   (Tiefe+Slot) ist reserviert für die lexikalische Variante (Closures, ≥64).
3. **Fallback-Semantik** → CALL/TAILCALL sind **symbolbasiert** (`idx` = Callee-Symbol in der
   Literaltabelle): Directory-Treffer → VM-Code-Root; **Fehltreffer → Tree-Walker-Bridge** (§5).
   (Directory-Index-Fast-Call ist eine spätere Optimierung, ≥63.)
4. **GC-Rooting geladener Literale** → §2: alle geladenen Literaltabellen sind **permanente
   GC-Roots** (in `gc_collect` mitmarkiert).
5. **PUSHLIT16 vs. `nlits`** → PUSHLIT16 gestrichen; `nlits` bleibt `u8` (max 255 Literale/Objekt);
   >255 ist eine spätere Erweiterung.
6. **CALLPRIM/enum-Stabilität** → §4a: **eigene gefrorene Prim-ID-Tabelle**, entkoppelt von der
   eval.c-enum; VM bietet `prim_by_id(u8)`.
7. **Opcode 54** → eindeutig **CONSP**.

## 9. Finale Entscheidungen (v3, Codex-Vorschlaege uebernommen) — P0 gepinnt
- **Frame-Repräsentation:** hot **Frame-Array**. Ein Frame = zusammenhängende Slots: **Args zuerst,
  dann Locals** (Slot `0..nargs-1` = Args, `nargs..nargs+nlocals-1` = Locals). LOADL/STOREL indizieren
  **linear** (`u8` = Slot); PUSHARG0/1/2/PUSHARGN = Kürzel für LOADL 0/1/2/n. Das Frame-Array ist ein
  **GC-Root** (Slots werden gemarkt).
- **Directory-`ext_addr`-Encoding:** **`off_lo, off_hi, bank`** (3 Byte, §5); flach = `bank*$10000+off`.
- **Fixnum-Semantik:** signed **15-Bit-Wrap**; `DIV`/`REMAINDER` durch 0 → **`TypeError`** (final, §1).
- **Closure/lexikalische LOADL:** Opcodes **≥64 reserviert**, Detail-Encoding bei der Erweiterung
  (nach v1-Kern grün auf HW). `&rest` und die Arity-Grenzen liegen dagegen im bestehenden
  CodeObject-Flagbyte und benoetigen keinen Opcode.

**P0-Pin (Codex, 2026-07-01):** Dieser Vertrag ist ab jetzt die stabile Schnittstelle
zwischen Compiler, Host-VM, C-VM, Disassembler und goldenen Testvektoren. Opcode-Nummern,
Operandformate, Code-Objekt-Header, Directory-Layout, Prim-ID-Tabelle und Frame-/Fixnum-
Semantik sind eingefroren. Neue Opcode- und Prim-Identitaeten kommen nur hinten dazu.
Die additive Arity-Erweiterung belegt das bereits vorhandene Flagbyte, laesst v1-Bytes
unveraendert dekodierbar und ist durch den maschinenlesbaren Vertrag aus §2a gebunden.
