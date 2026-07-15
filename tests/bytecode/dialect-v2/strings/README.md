# Dialect-v2 Strings core contract

`cases.json` pins the six-name core surface: the native `string-length` and
`string-ref` primitives plus `substring`, `string-append`, `string=`, and
`string<` from `lib/dialect-v2/strings-core.lisp`.

The v2 constructors use the private code-list codecs:

- `substring` and `string-append` build code lists and materialize them once
  through the private `%string-from-codes` codec;
- construction retains the established rooted streaming codec; the VM returns
  its result only on `VM_OK`, so OOM cannot expose a partial string to Lisp.

Neither constructor exposes a character-list conversion surface. The former
public `string->list` and `list->string` names are absent in v2. Prim-IDs 26 and 27
are permanent tombstones after their staging use; Prim-IDs 28 and 29 remain
private codecs. The ABI-1.1 `buffer-and-string-construction-block` owns the
future atomic builder/span-DMA design and must allocate new Prim-IDs.

The reduced `&optional` syntax has no supplied-p value. Consequently an
explicit `nil` end argument to `substring` is indistinguishable from an
omitted end argument in v2; the fixture pins that behavior. Prim-IDs 28 and 29
remain compiler-internal and are not valid `funcall` or `apply` designators.
The `%v2-string...` comparison helpers are private implementation names, not
members of the dialect surface.

The differential fixture uses the shared family runner with frozen v1 and the
v2 candidate across native Treewalk and native compiler/VM engines. It covers
direct, `funcall`, and `apply` calls, empty and multi-string construction,
lexicographic comparison, strict half-open bounds, converter removal, and
private-capability non-export. Cross-profile differences carry explicit
decision anchors; invariant observations carry `null`.

Schema and mutation checks can run before runtime integration:

```sh
python3 tools/host-lisp/dialect_v2_prelude_control.py \
  --fixture tests/bytecode/dialect-v2/strings/cases.json selftest
```

The live matrix is expected to remain red until both native capability IDs and
the v2 carrier boundary are available in the candidate harness. Fixture green
alone does not promote the family.
