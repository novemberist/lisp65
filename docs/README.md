# Documentation

This index is the curated entry point for the live lisp65 documentation.
Documents not linked from the first three sections are implementation records,
machine-bound contracts, proposals, or historical material; they are not user
instructions for release 1.0.1.

## Users

- [User Guide](user-guide.md) — verify, boot, edit, save, and recover
- [Dialect V2 Language Reference](language-reference.md) — released syntax and surface
- [Release Notes 1.0.1](releases/1.0.1.md) — package correction and inherited proof
- [Release Notes 1.0.0](releases/1.0.0.md) — original shipped features and limits
- [Architecture Overview](architecture-overview.md) — the product in one page

## Contributors

- [Development Guide](development.md) — build, test, evidence, and change rules
- [External Toolchain Setup](toolchain-setup.md) — exact compiler/tool pins and fetch/verify workflow
- [Upstream Findings](upstream-findings.md) — MEGA65 core/tooling requests
- [Implementation Contracts](implementation-contracts.md) — authorities and gates

## Private proof repository

Current status, active planning, sealed promotion archives, and operational
runbooks remain in the private proof repository. They are deliberately not
part of the curated public snapshot and are not required to build or use the
released product.

Machine-readable files under `config/` and sealed receipts remain authoritative
when prose and generated values differ.

## Historical material

Pre-1.0 plans, audits, stop memos, collaboration logs, and superseded design
notes are retained for provenance. They may use German, reflect obsolete paths,
or describe candidates that never shipped. Historical material must not be used
as an operational runbook.

The private repository's machine-checked classification is in
`config/document-index.json`. Sealed evidence may preserve historical German
claim strings; changing those strings would invalidate the evidence and is
therefore outside the translation effort.
