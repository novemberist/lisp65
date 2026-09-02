# Dialect V2 Language Reference

This living reference describes **lisp65 2.0.1**. The language remains
Dialect V2.

Dialect V2 is a small Common Lisp–inspired Lisp-2 for the MEGA65. It is
intentionally not ANSI Common Lisp.

## Evaluation model

- Function and value namespaces are separate.
- `nil` is false and the empty list; `t` is true. Both evaluate to themselves.
- Symbols are case-insensitive. Strings retain their character data.
- Fixnums are signed 15-bit two's-complement values in the range -16,384
  through +16,383. The remaining bit of the 16-bit cell is the runtime tag.
- Arithmetic wraps silently modulo 2^15. There is no overflow error; this is
  deterministic language behavior, not an implementation accident.
- Function calls use strict arity in Dialect V2.
- Lambda lists support required parameters, `&optional`, and `&rest`.
  Missing optional arguments become `nil`; default forms and supplied-p
  variables are not available.

```lisp
(defun greet (name &optional punctuation)
  (list name punctuation))

(greet "MEGA65")        ; => ("MEGA65" nil)
```

For example, a conventional recursive factorial returns 7,552 for `(fac 8)`:
the mathematical result 40,320 wraps modulo 32,768. Later multiplications use
the already wrapped predecessor. A BASIC-style `?OVERFLOW ERROR` is therefore
not produced. Per-operation overflow checks are intentionally absent from the
VM hot path; bignums and floating-point numbers are outside the current
dialect.

## Reader and core forms

The reader supports lists, dotted pairs, symbols, fixnums, strings, quote
(`'`), function quote (`#'`), and line comments beginning with `;`.

Core definition and control forms include `defun`, `defmacro`, `lambda`,
`quote`, `function`, `if`, `cond`, `let`, `let*`, `setq`, `progn`, `and`,
`or`, `when`, `unless`, `case`, `dotimes`, `dolist`, and `while`. Function
parameters may include `&rest`, and `setq` updates local bindings as well as
global values. These forms are lowered by the compiler; they are language
syntax rather than function bindings, so their absence from a generated
function-name list does not mean that the language lacks them.

Two global-definition macros, `defvar` and `defparameter`, complete the set:

```lisp
(defvar name [init])      ; assigns init only when name is not already bound
(defparameter name init)  ; always assigns init
```

Both return the name as a symbol.

The historical `do` and `do*` forms are deliberately not Dialect V2 compiler
forms; use `dotimes`, `dolist`, or `while`. `remainder` is a different case:
it remains a callable resident function, but it is not a Dialect V2
source-operation and is not part of the generated public-surface metadata.
Prefer `mod` in new code.

Characters are fixnum character codes. There is no separate character type
and no `#\` character-literal syntax; the reader's supported `#` syntax is
function quote, `#'`. Obtain codes from `string-ref` or write them as ordinary
numbers. Compare them with `=`, use ordinary arithmetic when useful, and use
`char-upcase` or `char-downcase` for case conversion; both take and return a
fixnum code.

Dialect V2 includes:

```lisp
(while test form*)
```

`test` is evaluated before every iteration. `nil` terminates; every other
value continues. Body forms run left-to-right and their values are discarded;
an empty body is legal. Normal termination returns `nil`. `while` adds no
binding or non-local-exit extent.

The compiler uses the existing signed `JFALSEREL`/`JMPREL` bytecode. In a
large streamed CodeObject, a backward edge whose target lies outside the
current 128-byte VM code window reloads that target window. Such a layout
therefore pays one target-window refill per admitted iteration, in addition
to any forward refill required by the body. This is a documented performance
property; it does not change loop semantics. For tight loops, keep the loop
body small or place it in a small helper function so that the backward edge
stays within one code window.

## Functions

The released surface includes:

- arithmetic and comparison: `+`, `-`, `*`, `/`, `mod`, `1+`, `1-`, `abs`,
  `max`, `min`, `=`, `/=`, `<`, `>`, `<=`, `>=`, `zerop`, `plusp`, `minusp`;
- bitwise arithmetic: `logand`, `logior`, `logxor`, `ash`, each taking exactly
  two arguments;
- lists and pairs: `cons`, `car`, `cdr`, `list`, `list*`, `append`, `reverse`,
  `nreverse`, `length`, `nth`, `nthcdr`, `last`, `butlast`, `copy-list`,
  `member`, `assoc`, `find`, `filter`, `mapcar`, `mapcan`, `mapc`, `reduce`,
  `every`, `some`, `count`, `position`, `rplaca`, `rplacd`;
- property lists: `getf`, `remf`;
- predicates and equality: `eq`, `eql`, `equal`, `atom`, `consp`,
  `symbolp`, `numberp`, `stringp`, `null`, `not`;
- symbols and functions: `symbol-name`, `boundp`, `function-kind`, `eval`,
  `funcall`, `apply`, `set`, `symbol-value`, `gensym`, `intern`;
- fixed-point arithmetic: `q`, `int->q`, `q->int`, `q+`, `q-`, `q*`,
  `q/`, `q->string`;
- random numbers: `random`, `random-seed`;
- input: `read-line` (a Bank-2 last-row editor), plus low-level `key-event`
  for polling or raw events;
- timing: `time`, `wait`;
- strings and character codes: `string-length`, `string-ref`, `char`,
  `char->string`, `number->string`, `search`, `string-trim`, `string-upcase`,
  `string-downcase`, `char-upcase`, `char-downcase`, `string=`, `string<`,
  `string-equal`, `string-prefix-p`, `string-suffix-p`, `string-append`,
  `substring`;
- output: `write`, `write-char`, `write-string`, `write-line`, `princ`,
  `prin1`, `print`, `terpri`;
- screen: `screen-size`, `screen-clear`, `screen-put-char`;
- reader and system work: `read-from-string`, `load`, `load-lib`, `load-libs`,
  `edit`, and the IDE/M65D library commands below.

`search`, `position`, and `string-ref` use zero-based indexes. A missing search
or position returns `nil`.

Short notes on the less obvious names:

- `(abs n)`, `(max n …)` and `(min n …)` take at least one number; `max` and
  `min` accept any number of further arguments.
- `(list* item … tail)` conses the leading items onto the final argument, so
  `(list* 1 2 '(3))` is `(1 2 3)`.
- `(butlast xs [n])` drops the last `n` elements, defaulting to one.
- `(copy-list xs)` returns a fresh top-level copy.
- `(mapcan fn list …)` applies `fn` like `mapcar` and appends the results.
- `(nreverse xs)`, `(rplaca cons x)` and `(rplacd cons x)` mutate the cells
  they are given and return the reversed list or the modified cons.
- `(getf plist key [default])` reads a property-list value and `(remf plist
  key)` returns the plist without that key; both require a well-formed plist.
- `(gensym)` returns a fresh symbol and `(intern "name")` returns the symbol
  for a string.
- `(prin1 x)` prints the machine-readable form, `(princ x)` prints a string
  without quoting and otherwise behaves like `prin1`, `(write-string s)` and
  `(write-line s)` print a string with and without a trailing newline, and
  `(number->string n)` converts a fixnum to a string.
- `(char string index)` is `string-ref` under its Common Lisp name;
  `(char->string code)` builds a one-character string.
- `(screen-size)` returns `(columns rows)` and
  `(screen-put-char x y code [attribute])` writes one cell.

The IDE library adds `(ide)`, `(ide-buffers)`, `(dir)`,
`(load-file-to-buffer file [buffer])`, `(save-buffer-to file [buffer])`,
`(eval-buffer buffer)`, `(compile-buffer-to-lib slot [buffer])` and
`(compile-file-to-lib source slot)`. The M65D library adds `(m65d-status)`,
`(m65d-remount)`, `(m65d-save name string)` and
`(m65d-save-new name string)`. Both libraries live on the product disk and
must be loaded with `load-lib`; see the [User Guide](user-guide.md).

### Names outside the 2.0.1 medium

The generated public-surface metadata index is a host-side population. Several
of its names belong to libraries that the 2.0.1 product disk does not carry,
so they are documented modules without a 2.0.1 delivery claim:

- generalized places from the `place` library: `setf`, `push`, `pop`, `incf`,
  `decf`;
- byte buffers from the `buffer` library: `make-buffer`, `buffer-ref`,
  `buffer-set!`, `buffer-length`, `bufferp`, `string->buffer`,
  `buffer->string`;
- extra strings from the `string-extra` library: `capitalize`, `string-split`;
- inspection from the `inspect` library: `who-calls`, `trace`, `untrace`;
- positional structures from the `defstruct` library.

`runtime-main` is the fixed-arity entry name of a standalone Ship runtime, not
a Workbench command. `screen-write-string` keeps a stable native identity but
the canonical Workbench product ships no Lisp wrapper for it; use
`write-string` or `screen-put-char`.

`trace` and `untrace` take an unquoted function name as macro input. Tracing
publishes a wrapper transactionally, saves the exact original function-cell
value and prints ordered `trace-enter`/`trace-exit` records. `untrace`
restores the captured value exactly.

`(defstruct name slot*)` is positional and option-free. It publishes
`make-NAME`, `NAME-p`, `copy-NAME`, `NAME-SLOT`, `NAME-set-SLOT`, and
`NAME-with-SLOT` functions. Records are tagged lists. Setters mutate the given
record; `with` functions return a copied record with one changed field. The
defining macro is a durable multi-definition operation and is visibly slower
than an ordinary expression.

The higher-order sequence functions `every`, `some`, `filter`, `mapcar`, and
`reduce` traverse cons lists, not packed strings. Dialect V2 does not expose
the former `string->list` and `list->string` conversion names. For
character-wise work, use an index loop with `dotimes`, `string-length`, and
`string-ref`. Use `search`, `substring`, `string-prefix-p`,
`string-suffix-p`, `string-equal`, and the case-conversion functions directly
for string work.

## List-domain errors

Since 2.0.0 the public list and sequence functions reject an unsupported
argument domain instead of returning a plausible but invalid value. Passing a
non-list where a proper list is required — or a non-number where a count is
required — raises the VM type error `vm: type error` and returns to one live
prompt. `(length "abc")` is the canonical example; it no longer answers with a
number.

The functions with this behavior are `append`, `length`, `nth`, `nthcdr`,
`reverse`, `last`, `member`, `assoc`, `mapcar`, `mapcan`, `mapc`, `find`,
`position`, `butlast`, `copy-list`, `count`, `reduce`, `every`, `some`,
`getf` and `remf`. Improper (dotted) list spines are rejected the same way.

The hot `car` and `cdr` opcodes are deliberately excluded from this
discipline: `(car nil)` and `(car 1)` both return `nil`. A fully checked
implementation was measured but did not fit the resident text budget without
an unacceptable per-key latency cost, so the inconsistency is documented
rather than hidden. It is also recorded in
[Known Issues](known-issues.md).

## Further behavior

`random` returns an unbiased value from zero through one less than its positive
fixnum argument. `(random-seed seed)` makes a run reproducible; otherwise the
first call seeds from read-only MEGA65 timer state and human input timing. The
generator is suitable for games and simulations, not cryptography.

The fixed-point functions use signed Q8.7 values stored as ordinary fixnums:
one raw unit is 1/128 and the representable range is -128.0 through
127.9921875. `(q whole raw-fraction)` constructs a value, where the optional
second argument is an exact signed count of 1/128 units. `int->q` converts an
integer, `q->int` truncates toward zero, `q+` and `q-` are exact within the
range, and `q*`/`q/` round to nearest with ties away from zero.
`q->string` returns the exact finite decimal representation. Overflow and
division by zero use the ordinary arithmetic error path.

`(time form)` evaluates `form` exactly once, prints its elapsed raster-frame
count, and returns the form's value unchanged. The counter is read atomically
and calibrated at approximately 50 Hz; a duration of 16,384 frames or more
fails explicitly instead of silently wrapping.

`(read-line)` blocks for one insertion-mode editable line and returns a packed
string. The native `lisp65>` prompt uses the same editor. Cursor Left/Right and
`C-b`/`C-f` move, `C-a`/`C-e` select endpoints, DEL removes backward and `C-d`
removes forward. Lines are bounded to 250 characters; further printable input
is ignored until deletion or RETURN. `(key-event 0)` polls and `(key-event 1)` blocks, returning
`(key code modifiers)` when an event is available. RUN/STOP remains the global
abort and is never returned as ordinary input.

At the interactive boundary, PETSCII Shift-Space `$A0` is normalized to the
ordinary space byte `$20`; display-equivalent whitespace therefore cannot
silently become a symbol character. Non-displayable control input is rejected.

`(wait frames)` blocks for zero through 16,383 raster frames and returns
`nil`. It uses the same atomic counter as `time`; RUN/STOP can abort the wait.

`read-from-string` reads the first object from a String; malformed input uses
the ordinary reader error path.

`restart-repl` is deliberately not part of the released surface. It is
reserved for the immutable-code/mutable-session architecture after three
bounded earlier designs failed their hardware or capacity gates. Restart from
the product disk for a fresh session.

`gc`, `room`, and `(error string)` have pinned semantics but are not
delivered: their one permitted carrier/pack attempt exceeded both the resident
boundary and a runtime-slice cap. They remain deferred to a later
format/carrier design rather than exposed as partially delivered names.

`peekw` and `pokew` are also absent. The release exposes byte-sized `peek` and
`poke`, but cannot compose a full unsigned 16-bit result within its signed
15-bit fixnum representation. The bitwise functions `logand`, `logior`,
`logxor` and `ash` are delivered and listed above; use them to compose or
decompose 16-bit values yourself, within the fixnum range.

Native primitive visibility and restrictions are classified in
`config/v2-native-function-registry.json`; the generated public-surface
population is
`tests/bytecode/dialect-v2/evidence/architecture-blocks/v11-function-metadata-index.json`,
and library manifests define the loadable surface. Neither file alone is a
list of everything a session can call: the resident library suite also
publishes ordinary functions that carry no public-surface metadata.

Byte buffers print as the opaque marker `?`, which is not a readable
representation; read their contents with `buffer-ref` and their length with
`buffer-length`. The `buffer` library is not on the 2.0.1 product disk.

## Interactive latency boundary

Ordinary non-persistent expressions use the direct path introduced in v1.5 and begin at the
interactive price: nested arithmetic, list access, function calls and structure
accessors no longer pay the transient append/rollback ceremony. Durable forms
such as `setq`, `defun`, `defmacro`, and macros that expand into definitions
still perform publication and rollback work; an ordinary such form costs about
1.2 seconds on the accepted MEGA65. That visible moment is a documented
architecture boundary, not a cost paid by already compiled program loops.

## Calls and errors

Public functions support direct calls and, where classified as function
designators, `funcall` and `apply`. Hardware/internal primitives beginning with
`%` are not user API.

Wrong arity, invalid types, and unavailable functions fail loudly, and since
2.0.0 an unsupported list domain does too. The REPL
recovers after an error; a failed form does not invalidate the session. Disk
status and recovery rules are documented separately in the [User Guide](user-guide.md).

## Libraries and persistence

`load-lib` installs one L65M library. `load-libs` processes names in order and
stops at the first error; it does not roll back libraries already installed.
Load IDE, optional IDEX, and M65D from the product disk before the one-drive
swap described in the [User Guide](user-guide.md).

## Deliberate limits

Dialect V2 has no CLOS, packages, keyword arguments, bignums, ratios, floats,
multiple values, restart system, or general on-device disk formatter. These are
limits of the released product, not implied roadmap promises.
