# Dialect V2 Language Reference

This living reference describes the current lisp65 **1.1 Wave 1 candidate**.
The released lisp65 1.0.1 also ships Dialect V2, but it does not contain the
Wave 1 additions called out below. The candidate is not a released version and
remains subject to the complete hardware acceptance and sealing chain.

Dialect V2 is a small Common Lisp–inspired Lisp-2 for the MEGA65. It is
intentionally not ANSI Common Lisp.

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
- output and system work: `write`, `write-char`, `terpri`, `load-lib`,
  `load-libs`, `edit`, and the documented IDE/M65D library commands.

`search`, `position`, and `string-ref` use zero-based indexes. A missing search
or position returns `nil`.

`filter` is a Wave 1 candidate addition and is not present in release 1.0.1.

The complete native visibility and restriction inventory is generated from
`config/v2-native-function-registry.json`; library manifests define the
loadable surface.

First-class byte buffers are a Wave 1 candidate addition. They print as the
opaque marker `?`. Read their contents with `buffer-ref` and their length with
`buffer-length`; the marker is not a readable representation. Release 1.0.1
does not provide this Buffer type.

## Wave 1 interactive latency limitation

On the reference MEGA65, the first expression compiled after a persistent
definition takes about **1.90 seconds**. Immediately following warm expressions
take about **0.20 seconds**. This is a dated, owner-approved candidate
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
