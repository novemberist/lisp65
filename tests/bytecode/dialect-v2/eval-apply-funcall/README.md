# Dialect-v2 eval/apply/funcall pre-carrier contract

`cases.json` is the normative pre-cut fixture for the public dialect-v2
`eval`, `apply`, and `funcall` surface. It uses the existing parameterized
dialect-family runner and records frozen v1 behavior separately from the v2
target. Every cross-profile difference has a decision anchor.

The fixture deliberately precedes the carrier implementation. Its schema and
mutation checks are part of `check-source`; the live matrix is expected to stay
red until the carrier supplies `eval` uniformly to the compiler/VM route and
enforces v2 arity for primitive designators. A green Treewalk-only result is
not sufficient for promotion.

`apply` and `funcall` are already classified as System/Runtime core names.
`eval` is native product surface but is absent from the source-derived public
surface in `config/dialect-contract.json` and therefore from the migration
classification. This is an explicit drift blocker: System/Runtime migration
must classify `eval` before profile promotion. This fixture does not silently
reinterpret the existing source-derived inventory.

Run the pre-carrier checks with:

```sh
make dialect-v2-eval-apply-funcall-check
```

After carrier implementation, run the full differential with:

```sh
make dialect-v2-eval-apply-funcall-matrix
```
