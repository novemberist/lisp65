# External toolchain setup

lisp65 does not redistribute third-party compiler or MEGA65 utility binaries in
the public source repository. Their exact release bytes, upstream commits and
SHA-256 identities are pinned in
[`config/toolchain-manifest.json`](../config/toolchain-manifest.json).

## Product builds

The released product was built with LLVM-MOS SDK v23.0.1. Fetch and verify that
exact public release into the ignored `tools/llvm-mos/` directory:

```sh
python3 tools/host-lisp/toolchain_external.py selftest
python3 tools/host-lisp/toolchain_external.py fetch --tool-root tools
python3 tools/host-lisp/toolchain_external.py verify --tool-root tools --product-build-only
make workbench-product
```

The fetch command verifies the archive before extraction and then verifies the
complete installed tree. A source build at the pinned LLVM-MOS commits is valid
for development, but it is not proof-equivalent merely because the commits
match: it must first reproduce the sealed product-artifact SHAs.

Set `LLVM_MOS_ROOT` to use an installation elsewhere. The default remains
`tools/llvm-mos`, so existing proof builds retain identical command lines.

## Hardware deployment tools

MEGA65 tools are not needed to compile the product. Hardware deployment also
requires the exact `c5bf0ccd…` utilities. The original Linux CI asset is no
longer a stable public download, so its exact archive is preserved as a private
proof-mirror release asset. Contributors may instead build the pinned upstream
commit for development and point `M65TOOLS_ROOT` at it.

If the exact archive is available locally, install and verify it together with
LLVM-MOS:

```sh
python3 tools/host-lisp/toolchain_external.py fetch \
  --tool-root tools \
  --m65tools-archive /path/to/m65tools-develo-207-c5bf0c-linux.7z
python3 tools/host-lisp/toolchain_external.py verify --tool-root tools
```

## Identity levels

- `exact-binary-match`: the complete installed tree matches the manifest; this
  is the primary proof identity.
- pinned source rebuild: suitable for development, not yet proof-equivalent.
- reproduced product: a pinned source rebuild becomes acceptable for proof work
  only after a fresh double build reproduces every sealed product SHA.

LLVM-MOS and MEGA65 tools keep their upstream licenses. See
[`THIRD-PARTY-NOTICES.md`](../THIRD-PARTY-NOTICES.md).
