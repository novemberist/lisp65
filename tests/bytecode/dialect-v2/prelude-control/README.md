# AP8.4 Prelude/Control harness contract

`cases.json` is the normative, profile-aware case set. Every case binds one
approved migration decision through `migration_anchor` and records the exact
observation for both profiles and both required engines:

- `native-c-treewalk` uses equivalence mode `tree`;
- `native-c-compiler-vm` uses equivalence mode `vm`.

Build and run the contract with:

```sh
make dialect-v2-prelude-control-matrix
```

The two paths must identify distinct, non-byteidentical binaries. The v1
binary is built from the source export of frozen commit
`f6527d25e2035eae5a98dae7431d641515e2fd2e`; the v2 binary is built from the
candidate profile. Each binary has a build receipt which pins its compiler,
defines, source/header and preload inputs, binary SHA-256, and build-profile
SHA-256. Verdicts carry those bindings plus the combined preload SHA-256.
Both binaries retain the existing harness CLI:

```text
equivalence-check tree|vm FORMS [--preload SOURCE]
```

Each input form produces exactly one `SOURCE => OBSERVATION` line. Lisp errors
are normalized to `!error:<class>` while the harness process exits successfully.
Harness, preload, parse, or cardinality failures remain terminal host errors.

Only a case with at least one cross-profile observation difference carries a
`decision:<id>` migration anchor; invariant control cases carry `null`. Verdict
records copy that value into `decision`. Their `result_sha256` hashes only the
normalized observation, so equal observations have equal hashes across profiles.

The v2 binary boundary must provide the target core used by
`lib/dialect-v2/prelude-control.lisp`, enforce `/=` arity for direct calls,
`funcall`, and `apply`, and suppress the public `remainder` binding and source
`do`. Both modes must honor the supplied profile preload. The frozen v1
compiler/VM intentionally retains its historical `defvar`-as-`setq` behavior;
the fixture records that evidence rather than rewriting it. The current generic
equivalence binary has no profile switch and therefore cannot serve as the v2
binary.

The Device-LCC surface is gated separately by
`make dialect-v2-lcc-surface-check`. Its focused 7-case fixture proves the
same hard cut for `do`, `do*`, and `remainder` while keeping opcode 24
decodable and the frozen v1 behavior reproducible.
