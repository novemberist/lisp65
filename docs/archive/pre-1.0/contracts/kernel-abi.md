# lisp65 — Kernel-ABI (Lane K → Lane L/T)

Der **stabile Vertrag**, gegen den Lane L (Bibliothek) und Lane T (Harness) bauen.
Änderungen kündigt Lane K vorher in `docs/collaboration.md` an. Stand: 2026-07-02.

## Objektmodell (`src/obj.h`)
- `obj` = 16-Bit getaggt: `NIL=0`; Fixnum `(n<<1)|1` (15-Bit signed); Zeiger = gerade, ≠0.
- Zelltypen: `T_CONS, T_SYM, T_PRIM, T_CLOSURE, T_MACRO, T_STR`.
- **String** = `T_STR`-Zelle, `a` = Liste von **Zeichen-Codes (Fixnums)**, `b`=NIL.
  Ein **Zeichen ist ein Fixnum** (PETSCII/ASCII-Code) — es gibt (noch) keinen Char-Typ.
- **Mit `-DLISP65_STRING_ARENA` (Packed-Byte-Strings, IDE-OOM-Kapazitätsfix):** ein
  `T_STR` ist EINE Zelle, `a` = **Länge (Fixnum)**, `b` = **Byte-Offset (Fixnum)** in eine
  Byte-Arena; der Text liegt als rohe Bytes in der Arena (GC = mark-compact). Die
  char-listen-Repräsentation und die Arena-Repräsentation existieren **nie gemischt** —
  ein Build ist entweder das eine oder das andere. Kern-Accessoren `str_len(s)`,
  `str_byte(s,i)`, `str_copy_out`, `str_from_bytes`, `str_from_charlist`, Streaming
  `str_open`/`str_putc`/`str_close` (`src/mem.{c,h}`). **Grenze:** Länge (`a`) und Offset
  (`b`) sind positive Fixnums → **max 16383 Bytes pro String** (`STR_MAX_BYTES=0x3FFF`);
  darüber liefert der Builder ehrlich `mem_oom` (kein Wrap in negative Länge). Design/Status:
  `docs/ide-oom-packed-strings-design.md`.

## Primitive (in `set-symbol-function` gebunden, aufrufbar)
Arithmetik/Vergleich: `+ - * mod < > = <= >=`
Listen/Kern: `cons car cdr rplaca rplacd nreverse eq eql list funcall apply set-symbol-function gensym boundp`
Maschine: `peek poke load` (`load` nur Host/Embedded; Disk-`load` ist vertagt, s. file-io-doc)

### Fixnum-/Number-Vertrag (Post-MVP-P1)
- Es gibt aktuell genau einen numerischen Nutzertyp: **Fixnum**. `numberp` bedeutet
  daher "ist Fixnum"; ein separater Integer-/Bignum-/Float-Typ existiert nicht.
- Portable Fixnum-Werte liegen im 15-Bit-signed-Bereich **-16384..16383**. Diese Grenze
  folgt aus dem `obj`-Tagging `(n << 1) | 1` in einem 16-Bit-Objektwort.
- `+`, `-`, `*` und die darauf aufbauenden Library-Funktionen haben nur dann portable
  Semantik, wenn Eingaben **und Ergebnis** in diesem Bereich bleiben. Overflow ist
  absichtlich **kein** Sprachvertrag; aktuelle C-/VM-Pfade koennen dabei wrap/truncate
  und Tests duerfen sich darauf nicht stuetzen.
- `mod` folgt fuer Nicht-Null-Divisoren der CL-Richtung: das Ergebnis hat das Vorzeichen
  des Divisors. Divisor `0` ist ausserhalb des portablen Vertrags; keine Library oder
  Konformitaets-Case darf sich darauf verlassen.
- Vergleiche `<`, `>`, `=`, `<=`, `>=` akzeptieren Fixnums und liefern `t`/`nil`.
  Die Prelude-/Stdlib-Prädikate `zerop`, `plusp`, `minusp`, `evenp`, `oddp` und
  `signum` bauen auf diesem Vertrag auf.
- `abs` ist portabel fuer alle Fixnums ausser dem kleinsten Wert `-16384`, dessen
  positives Gegenstueck im 15-Bit-Bereich nicht darstellbar ist.

### String-Primitive (NEU 2026-07-01)
| Form | Ergebnis |
| --- | --- |
| `(stringp x)` | `t`, wenn `x` ein String ist, sonst `nil` |
| `(string->list s)` | Liste der Zeichen-Codes (Fixnums). Default: **teilt** die interne Liste (nicht kopieren+mutieren). Mit `-DLISP65_STRING_ARENA`: liefert eine **frische** Liste (die Arena hat keine interne Zellliste) — der Aufrufer darf sie frei mutieren |
| `(list->string l)` | neuer String aus einer Liste von Zeichen-Codes |
| `(string-length s)` | Anzahl Zeichen (Fixnum) |
| `(string-ref s i)` | Zeichen-Code an Index `i` (0-basiert; out-of-range → `lisp_abort`) |

**Bewusst NICHT im Kern** (Lane L baut sie aus obigen + Listen-Ops):
`substring`, `string-append`, `string=`, `string-upcase/downcase`, `char->string`,
`string->symbol`/`symbol->string` (Letztere brauchen evtl. einen Kern-Helfer → bei Bedarf anfragen).

> **Lane L/T Pflicht:** Der Host-Oracle `tools/host-lisp/lisp64.py` muss diese fünf
> String-Primitive **spiegeln**, sonst können String-Konformitätstests nicht gegen das
> Oracle laufen (lisp64.py hatte bisher keine String-Manipulation).

## Grenzen (aktuell) & geplante Anhebung (K-A)
| Grenze | jetzt | Anmerkung |
| --- | --- | --- |
| Symbole `MAX_SYM` | **uint16-Index, Default 384** (2026-07-01) | `#ifndef`-überschreibbar: `-DMAX_SYM=1024` etc.; bis 65534 möglich |
| Namenspool `NAMEPOOL` | Default 3072 B | `#ifndef`-überschreibbar; mit `MAX_SYM` mit anheben |
| Heap `HEAP_CELLS` | 1536 (mega65-Deploy 1200) | → größerer Heap über flachen MEGA65-Speicher (offen, K-A) |

**Symbol-Decke aufgehoben (2026-07-01):** Die alte 255-Grenze ist weg — Index/`nsym`/
`sym_count`/`sym_nth` sind jetzt `uint16`. Lane L kann die Stdlib **frei breit** bauen.
Für große Builds (mega65/Voll-Lib) `-DMAX_SYM=…` **und** `-DNAMEPOOL=…` setzen (Lane T im
Build). Historische C64/GO64-Smokes sind nur noch `legacy-xc64-*` und kein Standard-Gate.
Header-Änderung: `sym_count`/`sym_nth` sind jetzt `uint16_t` (rippelt nur in `mem.c`).

## Heap-Skalierung MEGA65 (K-A, Design — Implementierung gestaffelt)
**Befund:** Das `obj`-Encoding trägt bereits bis **32766 Zellen** (~160 KB; `obj`=int16,
Index=`obj>>1`). Engpass ist nur, dass `Cell heap[]` in adressierbaren RAM passen muss.
Bank 0 (~44 KB, mit Code/Stack geteilt) erlaubt real ~1200–1500 Zellen — daher die enge
mega65-Deploy-Grenze. **Echte Skalierung = Heap in Far-Memory** (jenseits `$FFFF`, z. B.
flacher Bereich ab `$40000`), CPU-Zugriff via 45gs02-Flat-Adressierung (`lda [zp],z`).

**Implementierungsplan (gestaffelt, weil großer Eingriff):**
1. **Accessor-Naht zuerst:** `CELL(o).a/.b/.type` (heute Struct-Member-Lvalue) hinter
   Inline-Zugriffe kapseln: `cell_a(o)/cell_b(o)/cell_type(o)` + `set_cell_a/ b/ type`.
   Host = direkter Array-Zugriff (unverändert schnell); mega65-Far-Variante = Flat-Read/
   Write auf `HEAP_BASE + index*5`. **Rippelt durch eval/reader/printer/mem/symbol** →
   vor Umsetzung in `collaboration.md` ankündigen (reiner mechanischer Ersatz, keine Semantik).
2. **Far-Heap hinter Flag** `-DMEGA65_FAR_HEAP=$40000`: `alloc`/Freelist/`gc_collect`
   arbeiten über die Accessoren; `marks[]` bleibt klein (1 Byte/Zelle, kann in Bank 0 oder
   ebenfalls far). Offline in xemu validierbar (mega65-Build + Dump), dann HW-Bestätigung.
3. **Default-Flip** erst nach HW-grün (Produkt-Entscheidung).
**Status:** Design fixiert; Schritt 1 (Accessor-Naht) ist der nächste konkrete K-A-Code-
Schritt. Bis dahin bleibt der Array-Heap (Default 1536 / mega65-Deploy 1200) maßgeblich.

## Eval/Semantik (unverändert, Referenz)
Lisp-2 (getrennte Wert-/Funktionszelle), lexikalische Closures, `quote`/quasiquote
(`` ` ``/`,`/`,@`), `if/lambda/setq/progn/defmacro/function`, `&rest` (dotted/variadisch),
dotted-pair-Reader `(a . b)`. `F` ist der False-Atom-Sonderfall — nicht als Name nutzen.
GC: Mark-Sweep, nur in `alloc()`; lebende objs über Allokationen via `GC_PUSH` schützen.
