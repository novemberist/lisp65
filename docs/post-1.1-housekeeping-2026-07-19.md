# Post-1.1 housekeeping — structural pass

Status: completed identity-neutral pass; product-source modernization remains a
separate 1.2 decision.

This pass removes misleading live-tree clutter without changing the v1.1.0
product artifacts or rewriting historical evidence.

## Outcomes

### Product-bound M65D fixtures retain their sealed paths

The two early save-new allocators were labelled dead in the planning backlog,
but the reference audit found that both remain active inputs to the historical
G5 persistence fixtures. A first cleanup pass moved them into
`tests/fixtures/legacy/m65d/`; the fresh-product gate then proved that the move
changed `config/semantic-contracts.json`, which is a raw-SHA input to the
resolved product profile and its embedded build ID.

The move was therefore reverted. These files remain at their v1.1.0 paths:

- `lib/m65-disk-alloc.lisp` — the historical fixed two-sector M5/M6 fixture;
- `lib/m65-disk-alloc-var.lisp` — the historical variable-chain M7 fixture.

Their location is historical compatibility, not a supported-library claim.
The Make targets, semantic contract and R5 closure retain the sealed paths and
both fixtures still pass their host load checks. A later C2 product-identity
cycle may relocate them together with the normal acceptance chain.

### Orphan classification

Six genuinely unreferenced one-shot files were removed. Git history remains the
archive for these non-normative helpers:

- `scripts/deploy-repl.sh`;
- `scripts/hw-c1-entry-seam-smoke.sh`;
- `scripts/gc-extheap-repro.c`;
- `scripts/f011-demolib.lisp`;
- `tools/host-lisp/check-stage3-native-smokes.py`;
- `tools/host-lisp/primitive_view_bank_attribution.py`.

Three backlog candidates were false positives and remain live:

- `scripts/push-github-verified.sh` is bound by the public-export and
  remote-source contracts;
- `dialect_v2_family_artifact.py` is imported by the Prelude evidence tool;
- `dialect_v2_r2_decisions.py` is imported by the migration-contract tool.

### Documentation and language policy

- `docs/v2-capability-carrier-registry.md` is now English while preserving its
  normative source pointers and gate commands.
- The migration contract deliberately keeps the compatibility pointer to the
  archived dialect redesign. Its exact path is bound into the frozen measured
  budget comparison; changing it would rewrite historical evidence. The
  pointer itself resolves to the archive and states that it is non-normative.
- `comment-language-check` now rejects newly added German source comments
  relative to `v1.1.0`. Its conservative matcher is mutation-tested; sealed
  evidence, the decision log and historical `.de.md` documents are outside its
  source scope.

## Deliberate boundary

The proposed idiom rewrite of `lib/m65-disk.lisp` is not part of this pass.
Unlike comment translation or fixture relocation, recompiling that file changes
the product artifact set and therefore requires a capacity receipt and the
normal product-identity acceptance chain. It should be evaluated as an
authorized 1.2 product refactor after the C2.0 contract review, not smuggled
into an identity-neutral cleanup commit.

The remaining translation of pre-existing German product-source comments was
tested as a separate commit and rejected. The resolved profile binds raw source
SHA-256 values, so comment-only edits change the embedded build ID and fail the
14-artifact identity gate even when compiled instructions are otherwise
unchanged. Those comments therefore remain frozen for the v1.1 line and become
ordinary, explicitly product-changing C2/1.2 work. No product gate was relaxed
and the failed candidate was not promoted.

After restoring the product-bound fixture paths, the canonical varied
fresh-clone double build passed for all 14 artifacts with the v1.1.0 product-set
SHA `048639695dd7ad9c35bd8e92b2ec4c0fba1e365385cfc680e90bb3ba1a860024`.
The receipt is
`tests/bytecode/dialect-v2/evidence/post-release/post-1.1-housekeeping-product-identity-receipt.json`.
