# 2.3.0 public input projection

This directory contains the serialized Plane and five library input recipes
consumed by the accepted 2.3.0 world. The native source projection and its
transitive include identities live in `../c2-v230-public-native/`.

`inputs.json` lists the public source of every materialized input, its original
consumption identity and any repository-relative path-metadata conversion.
`native-recipe.json` binds the product definitions and layout, independently
of host-only Makefile edits. The accepted resolved profile remains unchanged.
Generated suite-header comments are made repository-relative; all other header
bytes remain identical, and both original and exported identities are recorded.

`media-authority.json` binds the ten boot roles, nineteen delivered files and
their exact identities. The stager and descriptor are derived from the same
delivery population. `IDE`, `IDEX` and `M65D` are static-only; `BUFFER` remains
a disk package. The shipped `INIT.L65` loads `place` and `string-extra`.

The public producer imports no private card adapter or evidence receipt.
Historical pathnames in provenance identify prior consumption, not external
files that a user must obtain. Serialized Plane inputs are consumed byte for
byte; regeneration of the bootstrap compiler is not claimed by the native
reproduction. Native compilation and media packing must match the release
authority, otherwise the build stops.

Build with `make workbench-product-v230-build` in a fresh checkout, then run
`make workbench-product-v230-verify`. Source preparation and copied-artifact
preflight checks are not clean-build reproductions.
