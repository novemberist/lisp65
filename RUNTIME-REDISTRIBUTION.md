# Runtime redistribution

This notice explains how the lisp65 project applies the Mozilla Public License
2.0 to programs built with lisp65. The license text in [`LICENSE`](LICENSE)
controls if this explanation and the license ever differ.

## User programs

Using the lisp65 compiler, evaluator, libraries, or future Ship Builder does
not by itself place a user's source code, FASLs, data, or other independently
authored files under the MPL. Users choose the license for those materials.
Compiler output that does not contain lisp65 Covered Software is likewise not
Covered Software merely because lisp65 produced it.

## Shipping with the runtime

A user may distribute independently authored program files together with
lisp65 runtime components that a release manifest designates as
redistributable. When the program and runtime remain separate files, including
when packaged on one D81 or in one archive, the package is a Larger Work under
MPL 2.0 section 3.3 and may be distributed under terms chosen by the user.

The MPL continues to apply to the lisp65 Covered Software inside that package.
A distributor must:

- preserve applicable license notices;
- include or point recipients to the MPL 2.0 license; and
- make the corresponding source for the distributed lisp65 components
  available by reasonable means, as required by MPL 2.0 sections 3.1 and 3.2.

These requirements do not require disclosure or relicensing of independent
user files. If a user copies or modifies lisp65 source inside a user file, the
copied or modified Covered Software remains subject to the MPL.

## Product support boundary

Licensing permission is broader than the supported product surface. Release
1.0.0 ships the Workbench; internal proof carriers are not supported
redistributable runtimes merely because their source is available. A future
release that promotes a standalone runtime will identify its exact artifacts
and corresponding source in its public manifest.
