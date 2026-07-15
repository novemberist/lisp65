# lisp65 MVP conformance fixtures

This directory contains new lisp65 fixtures. They are not ports of the old
LISP-64 dialect tests. `salvage/lisp/**` is reference material only.

The first fixture layer pins the CL-near reader surface needed by the MVP:

- semicolon line comments;
- `*` as an ordinary symbol/operator, not a comment form;
- case-insensitive symbols with uppercase normalization;
- case-sensitive strings;
- quote expansion to `(QUOTE ...)`;
- quasiquote/unquote expansion to `(QUASIQUOTE ...)`, `(UNQUOTE ...)` and
  `(UNQUOTE-SPLICING ...)`;
- keywords as self-naming symbols;
- proper and dotted lists.

Run the current host oracle with:

```sh
python3 tools/host-lisp/mvp_cl_reader_oracle.py
```

The same versioned JSON fixture is also consumed by both native C reader
profiles. The gate-owned entry points are:

```sh
make semantic-contracts-g0
make semantic-contracts-g1
```

Keeping the fixture data-only avoids baking adapter implementation details into
the conformance contract. Required engines and remaining coverage gaps live in
`config/semantic-contracts.json`.

`mvp-eval-cases.json` pins the evaluator surface that exists at Phase 1/M1.2:
self-evaluation, `quote`, `if`, arithmetic, `cons`/`car`/`cdr` and `eq`. Cases
with an `m1_2_limit` field document behavior that is useful for the current
milestone but should tighten later, such as unknown operators returning `NIL`.

`../prelude-surface.json` is the first contract for Lane L's real library work.
It mirrors `docs/archive/pre-1.0/reference/core-vs-library.md`: core names are the only assumed substrate;
everything under `library` must be implemented in Lisp, staged by dependency.
The current contract is CL-like Lisp-2: `defmacro` is a core special form for
bootstrap, while `defun` is a Prelude macro over `set-symbol-function`.
The `deferred` section is also checked by the surface oracle. It is intentionally
more structured than a TODO list: each postponed symbol records its category,
known Lisp dependencies, required core hooks or blocked substrate, and why it is
not part of the M1 Prelude surface yet.

`prelude-macro-cases.json` pins expected macroexpansions for the first Prelude
macros. These are not runtime tests; they keep Lane L honest about deriving
surface forms from the minimal Core and preserving Lisp-2 function references.
Temporary bindings in expansions are printed as `#:` gensyms to make hygiene part
of the contract instead of relying on fixed helper names.

`../prelude-m1.lisp` is a deliberately small bootstrap Prelude for the current
M1.3 kernel. It uses the native quote/quasiquote reader sugar and `&rest` macro
bodies, but still avoids comments and richer lambda-list keywords until the native
reader/evaluator grow those capabilities. `prelude-m1-macro-cases.json` pins the
temporary M1 expansions separately from the final Prelude target surface.
`prelude-m1-eval-cases.json` evaluates concrete M1 Prelude functions in a small
Host oracle. The native embedded Prelude path is covered separately by
`make check`, which builds the test PRG and checks the XEMU dump for a
Prelude-defined form.
