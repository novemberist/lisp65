# Third-party notices

The curated lisp65 public repository and its release assets must carry an
inventory generated from their exact contents. The private development mirror
contains additional third-party material that is deliberately outside the
public export.

## LLVM-MOS

lisp65 is built with LLVM-MOS. The bundled development toolchain under
`tools/llvm-mos/` is not part of the curated public repository and must be
obtained separately from the LLVM-MOS project.

The signed-division behavior implemented by `src/mega65_math.s` was informed by
the semantics of LLVM-MOS `libcrt` division code. LLVM and LLVM-MOS materials
are distributed under the Apache License 2.0 with LLVM Exceptions. This notice
is retained conservatively as attribution; lisp65 does not redistribute the
LLVM-MOS toolchain in its public source package.

- <https://github.com/llvm-mos/llvm-mos>
- <https://llvm.org/LICENSE.txt>

## MEGA65 reference documents

The private mirror contains locally pinned MEGA65 manuals and reference PDFs.
They are not covered by the lisp65 license and are excluded from the public
repository and lisp65 release assets. Public documentation should link to the
official MEGA65 documentation instead of redistributing these files.
