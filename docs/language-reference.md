# Dialect V2 Language Reference

This living reference describes **lisp65 1.5.0**. The language remains
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
function-name list does not mean that the language lacks them. The historical
`do` form and the public `remainder` name are not part of Dialect V2.

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

- arithmetic and comparison: `+`, `-`, `*`, `/`, `mod`, `1+`, `1-`, `=`,
  `/=`, `<`, `>`, `<=`, `>=`, `zerop`, `plusp`, `minusp`;
- lists and pairs: `cons`, `car`, `cdr`, `list`, `append`, `reverse`, `length`,
  `nth`, `nthcdr`, `member`, `assoc`, `find`, `filter`, `mapcar`, `mapc`,
  `reduce`, `every`, `some`, `count`, `position`;
- predicates and equality: `eq`, `eql`, `equal`, `atom`, `consp`,
  `symbolp`, `numberp`, `stringp`, `null`, `not`;
- symbols and functions: `symbol-name`, `boundp`, `function-kind`, `eval`,
  `funcall`, `apply`, `set`, `symbol-value`;
- fixed-point arithmetic: `q`, `int->q`, `q->int`, `q+`, `q-`, `q*`,
  `q/`, `q->string`;
- random numbers: `random`, `random-seed`;
- input: `read-line` (a Bank-2 last-row editor), plus low-level `key-event`
  for polling or raw events;
- timing: `time`, `wait`;
- optional strings from the string-extra library: `capitalize`, `string-split`;
- optional inspection from the inspect library: `who-calls`, `trace`,
  `untrace`;
- optional positional structures from the defstruct library: `defstruct` and
  its generated constructor, predicate, copier, accessors, setters and
  functional updaters;
- strings and character codes: `string-length`, `string-ref`, `search`,
  `string-trim`, `string-upcase`, `string-downcase`, `char-upcase`,
  `char-downcase`, `string=`, `string<`, `string-equal`, `string-prefix-p`,
  `string-suffix-p`, `string-append`, `substring`;
- reader, output, and system work: `read-from-string`, `write`, `write-char`,
  `terpri`, `load-lib`, `load-libs`, `edit`, and the documented
  IDE/M65D library commands.

`search`, `position`, and `string-ref` use zero-based indexes. A missing search
or position returns `nil`.

`trace` and `untrace` take an unquoted function name as macro input. Tracing
publishes a wrapper transactionally, saves the exact original function-cell
value and prints ordered `trace-enter`/`trace-exit` records. `untrace` restores
the captured value exactly.

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

`(read-line)` blocks for one editable line, echoes accepted printable input,
uses DEL to erase, terminates on RETURN, and returns a packed string. Lines are
bounded to 250 characters; further printable input is ignored until DEL or
RETURN. `(key-event 0)` polls and `(key-event 1)` blocks, returning
`(key code modifiers)` when an event is available. RUN/STOP remains the global
abort and is never returned as ordinary input.

At the interactive boundary, PETSCII Shift-Space `$A0` is normalized to the
ordinary space byte `$20`; display-equivalent whitespace therefore cannot
silently become a symbol character. Non-displayable control input is rejected.

`(wait frames)` blocks for zero through 16,383 raster frames and returns
`nil`. It uses the same atomic counter as `time`; RUN/STOP can abort the wait.

`filter` and `read-from-string` were added in 1.1. `read-from-string` reads the
first object from a String; malformed input uses the ordinary reader error
path. `restart-repl` is deliberately not part of the 1.1 surface. It is
reserved for the C2 immutable-code/mutable-session architecture after three
bounded pre-C2 designs failed their hardware or capacity gates.

`gc`, `room`, and `(error string)` have pinned semantics but are not delivered
by the 1.1 profile: their one permitted carrier/pack attempt exceeded both the
resident boundary and a runtime-slice cap. They are deferred together to the
C2.2 format/carrier work rather than exposed as partially delivered names.

The complete native visibility and restriction inventory is generated from
`config/v2-native-function-registry.json`; library manifests define the
loadable surface.

Bitwise functions `logand`, `logior`, `logxor`, and `ash` are not available in
1.1. Their compact implementation requires the catalog-format
evolution planned with C2.2. Consequently `peekw` and `pokew` are also absent:
1.1 exposes byte-sized `peek` and `poke`, but cannot compose a full unsigned
16-bit result within its signed 15-bit fixnum representation.

First-class byte buffers were added in 1.1. They print as the opaque marker
`?`. Read their contents with `buffer-ref` and their length with
`buffer-length`; the marker is not a readable representation.

## Interactive latency boundary

Ordinary non-persistent expressions use the v1.5 direct path and begin at the
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

Wrong arity, invalid types, and unavailable functions fail loudly. The REPL
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
