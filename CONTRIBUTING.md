# Contributing to lisp65

This repository is a curated public source snapshot of a private proof
repository. The split keeps hardware receipts, licensed reference material,
and operational evidence out of the public history while making the complete
product source available for inspection and development. Public issues and
contributions are welcome; accepted changes are applied to the proof
repository, validated there, and returned in a later credited public sync.

## Before opening a change

- Search existing issues first.
- Keep one behavioral change per proposal.
- Explain the MEGA65 hardware or emulator context.
- Include the smallest reproducible Lisp form or source diff.
- Do not attach ROMs, proprietary manuals, credentials, private paths, or
  multi-hundred-megabyte diagnostic captures.

For a source change, run at least:

```sh
python3 tools/host-lisp/public_export.py selftest
python3 tools/host-lisp/public_export.py check
make source-syntax-check
python3 tools/host-lisp/asm_c_constant_contract.py selftest
```

The public repository cannot reproduce sealed hardware acceptance by itself.
It also does not yet expose a supported clean-build entry point for the exact
C2-lite 1.2 product; use the release bundle and its offline verifier for the
released binary identity. The historical `workbench-product` target describes
the retired 1.1 tier model and is not a 1.2 release build.
Maintainers run the applicable private capacity, identity, mutation, and
hardware gates before publishing an accepted change.

## Developer Certificate of Origin

Every contributed commit must carry a `Signed-off-by` trailer certifying the
[Developer Certificate of Origin 1.1](https://developercertificate.org/):

```sh
git commit -s
```

Use your real name and an email address you are entitled to use. A maintainer
may ask you to amend unsigned commits before evaluation.

## Contribution flow

1. Open an issue or pull request against the public snapshot.
2. Maintainers review the idea and preserve author attribution.
3. Accepted commits are reapplied to the private proof repository rather than
   merged directly into the public history.
4. The private tree runs product-capacity and evidence gates.
5. The next curated public sync credits the contributor and publishes the
   resulting source.

This process means public pull-request commit IDs are not release authorities.
Release notes and receipts bind the exact tested product artifacts.

## Sync cadence

The public snapshot is refreshed for every release and otherwise at least once
every four weeks while development is active. Each sync is recorded in
[the public sync log](docs/public-sync-log.md), including external contribution
credit or an explicit statement that none were included.
