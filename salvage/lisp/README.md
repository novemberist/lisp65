# Salvaged LISP 64 Libraries

This directory preserves dialect-pure LISP 64 libraries, tests, demonstrations,
and hardware experiments recovered during the early project phases. They are
historical reference material and are not part of the released lisp65 product.

The sources can still be useful for comparing semantics or recovering an
algorithm. They target the host reference interpreter in `tools/host-lisp/` and,
where noted by the filename, the original C64 LOAD path.

## Dialect notes

- `;` line comments are a host-side convenience. The original LISP 64 reader
  accepts the S-expression comment form `(* ...)` instead.
- In LISP 64, `*` starts a comment; multiplication is named `TIMES`.
- Files whose names contain `c64-load` or `savefmt-c64-smoke` were constrained by
  the original device reader and SAVE record format.

## Contents

The collection falls into four broad groups:

- compatibility and language experiments: `prelude.lsp`, `conformance.lsp`,
  `cl-compat.lsp`, macros, sequences, structures, conditions, and Mini-CLOS;
- editor and module experiments: IDE, paredit, autoload, and module libraries;
- historical platform work: C64 and MEGA65 hardware, terminal, keyboard,
  graphics, sound, and portable platform-layer prototypes;
- tests and measurements: conformance suites, LOAD/SAVE smoke cases,
  cross-checks, demonstrations, and benchmarks.

File names and adjacent test files are the authoritative guide to individual
experiments. Historical design documents referenced by these sources now live
under `docs/archive/pre-1.0/`; their paths and commands may no longer match the
current tree.

## Running the host archive

Run the historical host suites with:

```sh
sh tools/host-lisp/run-tests.sh
```

Or invoke the reference interpreter directly, for example:

```sh
python3 tools/host-lisp/lisp64.py \
  salvage/lisp/prelude.lsp salvage/lisp/conformance.lsp
```

These checks preserve historical behavior. Current lisp65 development and
release validation use the gates documented in `docs/development.md`.
