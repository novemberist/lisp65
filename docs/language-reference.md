# Dialect V2 Language Reference

This living reference describes the current lisp65 **1.1 Wave 2 candidate**.
The released lisp65 1.0.1 also ships Dialect V2, but it does not contain the
Wave 1 additions called out below. Waves 1 and 2 are hardware-sealed; the
candidate is still not a released version because Wave 3 and the final release
promotion remain open.

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
`or`, `when`, `unless`, `dotimes`, and `dolist`. The historical `do` form and
the public `remainder` name are not part of Dialect V2.

## Functions

The current Wave 1 candidate surface includes:

- arithmetic and comparison: `+`, `-`, `*`, `/`, `mod`, `1+`, `1-`, `=`,
  `/=`, `<`, `>`, `<=`, `>=`, `zerop`, `plusp`, `minusp`;
- lists and pairs: `cons`, `car`, `cdr`, `list`, `append`, `reverse`, `length`,
  `nth`, `nthcdr`, `member`, `assoc`, `find`, `filter`, `mapcar`, `mapc`,
  `reduce`, `every`, `some`, `count`, `position`;
- predicates and equality: `eq`, `eql`, `equal`, `atom`, `consp`,
  `symbolp`, `numberp`, `stringp`, `null`, `not`;
- symbols and functions: `symbol-name`, `boundp`, `function-kind`, `eval`,
  `funcall`, `apply`, `set`, `symbol-value`;
- strings: `string-length`, `string-ref`, `search`;
- reader, output, and system work: `read-from-string`, `write`, `write-char`,
  `terpri`, `load-lib`, `load-libs`, `edit`, and the documented
  IDE/M65D library commands.

`search`, `position`, and `string-ref` use zero-based indexes. A missing search
or position returns `nil`.

`filter` is a Wave 1 candidate addition. `read-from-string` is a Wave 2
candidate addition; neither is present in release 1.0.1. `read-from-string`
reads the first object from a String; malformed input uses the ordinary reader
error path. `restart-repl` is deliberately not part of the 1.1 surface. It is
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
the 1.1 candidate. Their compact implementation requires the catalog-format
evolution planned with C2.2. Consequently `peekw` and `pokew` are also absent:
1.1 exposes byte-sized `peek` and `poke`, but cannot compose a full unsigned
16-bit result within its signed 15-bit fixnum representation.

First-class byte buffers are a Wave 1 candidate addition. They print as the
opaque marker `?`. Read their contents with `buffer-ref` and their length with
`buffer-length`; the marker is not a readable representation. Release 1.0.1
does not provide this Buffer type.

## Wave 1 interactive latency limitation

On the reference MEGA65, the first expression compiled after a persistent
definition typically takes **1.90 to 1.96 seconds**; occasionally longer times
have been observed. Immediately following warm expressions take about
**0.20 seconds**. This is a dated, owner-approved candidate
limitation, not a passed performance target. Entering related definitions as
one block amortizes the compiler-tier reload. The committed cure is the C2
direct-Attic-execution architecture for 1.2; the exception does not renew
silently if C2 leaves that scope.

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
