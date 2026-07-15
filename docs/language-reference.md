# Dialect V2 Language Reference

lisp65 1.0.1 ships Dialect V2, a small Common Lisp–inspired Lisp-2 for the
MEGA65. It is intentionally not ANSI Common Lisp.

## Evaluation model

- Function and value namespaces are separate.
- `nil` is false and the empty list; `t` is true. Both evaluate to themselves.
- Symbols are case-insensitive. Strings retain their character data.
- Fixnums are signed 15-bit values and wrap within the tagged fixnum range.
- Function calls use strict arity in Dialect V2.
- Lambda lists support required parameters, `&optional`, and `&rest`.
  Missing optional arguments become `nil`; default forms and supplied-p
  variables are not available.

```lisp
(defun greet (name &optional punctuation)
  (list name punctuation))

(greet "MEGA65")        ; => ("MEGA65" nil)
```

## Reader and core forms

The reader supports lists, dotted pairs, symbols, fixnums, strings, quote
(`'`), function quote (`#'`), and line comments beginning with `;`.

Core definition and control forms include `defun`, `defmacro`, `lambda`,
`quote`, `function`, `if`, `cond`, `let`, `let*`, `setq`, `progn`, `and`,
`or`, `when`, `unless`, `dotimes`, and `dolist`. The historical `do` form and
the public `remainder` name are not part of Dialect V2.

## Functions

The released surface includes:

- arithmetic and comparison: `+`, `-`, `*`, `/`, `mod`, `1+`, `1-`, `=`,
  `/=`, `<`, `>`, `<=`, `>=`, `zerop`, `plusp`, `minusp`;
- lists and pairs: `cons`, `car`, `cdr`, `list`, `append`, `reverse`, `length`,
  `nth`, `nthcdr`, `member`, `assoc`, `find`, `filter`, `mapcar`, `mapc`,
  `reduce`, `every`, `some`, `count`, `position`;
- predicates and equality: `eq`, `eql`, `equal`, `atom`, `consp`, `listp`,
  `symbolp`, `numberp`, `stringp`, `null`, `not`;
- symbols and functions: `symbol-name`, `boundp`, `function-kind`, `funcall`,
  `apply`, `set`, `value`;
- strings and conversion: `string-length`, `string-ref`, `string->list`,
  `list->string`, `search`;
- output and system work: `write`, `write-char`, `terpri`, `load-lib`,
  `load-libs`, `edit`, and the documented IDE/M65D library commands.

`search`, `position`, and `string-ref` use zero-based indexes. A missing search
or position returns `nil`.

The complete native visibility and restriction inventory is generated from
`config/v2-native-function-registry.json`; library manifests define the
loadable surface.

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
