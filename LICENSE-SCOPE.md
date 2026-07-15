# License scope

The original lisp65 source code, build and verification tooling, tests, and
documentation are made available under the Mozilla Public License 2.0 unless a
file or directory carries a different notice. The canonical license text is in
[`LICENSE`](LICENSE).

The license applies only to material for which the lisp65 contributors have
sufficient rights. It does not replace or override the terms of third-party
material.

The curated public repository does not include:

- the bundled LLVM-MOS toolchain under `tools/llvm-mos/`;
- third-party MEGA65 manuals and reference PDFs;
- sealed promotion and hardware-evidence archives;
- internal planning, operational records, or private release material; or
- release tarballs stored in Git or Git LFS.

Those exclusions describe the public export boundary. They do not alter the
historical private proof repository or the evidence bound to release 1.0.0.
End-user bundles are distributed separately as release assets and carry their
own license and provenance files.

Release-1.0 source files are not modified merely to add per-file headers,
because complete-file hashes and product debug metadata participate in the
sealed evidence identity. This file is the prominent license location allowed
by Exhibit A of the MPL. New source files should use the standard MPL 2.0
Exhibit A notice where practical.
