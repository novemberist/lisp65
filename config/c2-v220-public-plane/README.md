# 2.2.0 public input projection

This directory contains the source/data inputs consumed by the accepted
2.2.0 product. `inputs.json` binds each original materialization pathname to
its public file and records any repository-relative path normalization.
`native-recipe.json` supplies the complete configured geometry; no private
card report is a build input.

The serialized bytecode planes are bootstrap inputs, not prebuilt native
objects. The public export's generated `public-export-binary-contract.json`
declares their exact bytes, Lisp source snapshots and consuming build recipe.
The clean native reproductions consume these inputs byte-identically; they
do not claim to regenerate the historical bytecode bootstrap from Lisp.
No prebuilt host shared library is included or required by this producer.

`libraries/libraries.json` binds the five optional packages, their Lisp
sources, suite recipes, bytecode manifests and blob inputs. The public media
producer regenerates their L65S files and their locator-dependent L65I index
using the selected product generation. The result must match the accepted
medium exactly. `string-extra` is the delivered package, not `strings-extra`.
There is no INIT.L65 on this release medium.

The native generated translation units live separately in
`config/c2-v220-public-native`. They are C/assembler source, not object files.
Build with `make workbench-product-v220-build`; verify the same source world
with `make workbench-product-v220-verify`. Both native outputs and the packed
medium are compared with the public accepted-artifact identities.
