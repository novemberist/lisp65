# Promotion Archive Policy

Status: active for every block, family, product-candidate, and hardware-
acceptance promotion.

The machine-readable policy is `config/promotion-archive-policy.json`, the
live register is `config/promotion-register.json`, and the release-asset
inventory is `config/evidence-archive-assets.json`. Those files take
precedence over this overview.

## A promotion is a sealed state

A promotion binds evidence to a completed state, never to the mutable working
tree. Each promotion creates a deterministic archive containing:

- promotion identity, type, source commit, and bounded claims;
- the observed private-mirror `remote_head`, proving that the source commit was
  already reachable remotely when new evidence was sealed;
- an inventory and SHA-256 digest for every embedded file;
- every transitively referenced mutable input as exact bytes or an explicit
  content-SHA binding;
- a verifier that needs only Python's standard library.

Product promotions use policy v2: every product byte stream named by the
reproducibility receipt must be embedded. A content-SHA reference alone is not
enough for product bytes.

## Reproducibility and offline verification

Before sealing a product, run two complete builds from separate fresh clones
while varying at least `PYTHONHASHSEED`, `SOURCE_DATE_EPOCH`, time zone, and
calendar context. Product artifacts must be byte-identical.

The self-containment test extracts only the archive into a fresh empty
directory and runs `verify.py` there. It must not consult the repository,
working tree, or network. Use:

```sh
make promotion-preflight-check
make promotion-register-check
```

## Promotion types and consumers

- `product-candidate` seals the complete reproducible product artifact set and
  its claim limits.
- `hardware-acceptance` consumes a registered product-candidate seal and binds
  its unchanged identity to verified case receipts and physical cycle IDs.
- R5 consumes R4; R6 consumes the registered R5 evidence; no stage rebuilds a
  product from the live tree merely for convenience.

The optional one-ceremony rerun is permanently unnecessary once SHA-bound case
receipts and cycle IDs exist. It must not be reintroduced as a promotion gate.

## Append-only boundary and transport

A sealed archive is never amended. Errata are new documents referencing the
seal; replacement evidence receives a new promotion ID and archive. Archive
bytes are private GitHub release assets, not Git or Git LFS objects. A local
archive path is an ignored cache and is accepted only when its size and SHA-256
match the release-asset inventory.

The live tree validates policy, registry schema, asset identity, unique
subjects, and the absence of archives or blobs above 50,000,000 bytes from
both the Git index and branch/tag history. The versioned pre-commit hook blocks
the index violation; the pre-push hook and verified push ritual block historical
violations. It does not rerun every historical proof after unrelated source
changes. Use:

```sh
python3 tools/host-lisp/evidence_archive_assets.py remote-check
python3 tools/host-lisp/evidence_archive_assets.py materialize path/to/archive.tar.gz
python3 tools/host-lisp/evidence_archive_assets.py index-size-gate
python3 tools/host-lisp/evidence_archive_assets.py history-size-gate
```

New promotion-v3 and hardware-acceptance-v2 packers fail closed when their
source commit is not an ancestor of the recorded private branch head. Their
archive manifests record `remote_source_binding.remote_head`, the recording-
time identity, and its transport-rewrite-resolved identity. Their embedded
offline verifiers reject a deleted or malformed binding. Historical v2/v1
archives sealed before this rule remain immutable and are accepted without
retrofitted fields.

## Release 1.0.0

The full promotion history remains in `config/promotion-register.json`. The
final hardware-acceptance seal for 1.0.0 is:

- promotion: `r6-g6-hardware-acceptance-aed1595`
- archive SHA-256: `b339a274a97c947025ce66b09cd54ce5af73e24d8a99328fcb0659ffa605ddba`
- claim: 5/5 applicable G6 hardware cases passed; physical write-protect is N/A
  for the stock-core SD-D81 profile

Historical archives and their original-language claim strings are immutable.
