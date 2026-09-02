# Reference Material

These files are development references, not product contracts. Their hashes
pin the snapshots used by hardware and documentation audits.

Run this check for the small snapshots retained in the private proof tree:

```sh
sha256sum -c docs/reference/SHA256SUMS
```

## External large reference

`mega65-book.pdf` is no longer stored in Git or Git LFS. It is a third-party,
1,455-page snapshot built on 2026-04-08 from the official
[MEGA65 User Guide source](https://github.com/MEGA65/mega65-user-guide).

| Field | Bound value |
| --- | --- |
| Historical repository path | `docs/reference/mega65-book.pdf` |
| SHA-256 | `c974a43257a141d30a606d84a3fabc6959c02934749f109244914688c379f786` |
| Size | `77,655,882` bytes |
| Pages | `1,455` |
| Snapshot creation date | `2026-04-08` |

The exact historical bytes remain in the verified pre-rewrite backup. Do not
substitute a newer upstream build under this identity: download or rebuild a
new snapshot, record its own SHA-256, and re-run any page-bound audit that uses
it.

## Retained snapshots

| File | Role |
| --- | --- |
| `MEGA65_BASIC_65_Referenzhandbuch.pdf` | BASIC 65 API reference |
| `mega65-chipset-reference.pdf` | Chipset and register reference |
| `mega65-userguide.pdf` | User workflow and platform behavior reference |
