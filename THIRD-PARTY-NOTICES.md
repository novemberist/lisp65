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

## MEGA65 tools

Hardware transfer and disk-image workflows use MEGA65 tools from
<https://github.com/MEGA65/mega65-tools>, pinned by the toolchain manifest to
commit `c5bf0ccd7ec6398290176f8af928d0780482577f`. The project is distributed
under GNU GPL version 3. The installed binaries are external build/deployment
tools and are not included in the curated lisp65 source package.

The repository does retain
`patches/mega65-tools-keybuffer-drain.patch`, a downstream change against that
exact commit. Its header records the upstream identity and licence; applying it
does not change the licence of the upstream files.

## Xemu

The delivered-world executor uses a project fork of Xemu from
<https://github.com/lgblgblgb/xemu>, based on commit
`40dfef0d1d5f56be2469492715c12bdb32c75b67`. Xemu is distributed under GNU
GPL version 2 or, at the user's option, any later version. The Xemu source and
binary are external tools and are not part of lisp65 release assets.

Four downstream patches are retained under `tools/xemu-patches/`:

- `mega65-f011-io-buffer-select.patch`
- `mega65-dwx-headless-input.patch`
- `mega65-dwx-cycle-counter.patch`
- `mega65-f011-buffered-read-eq.patch`

The EQ-setting fourth patch is retained as historical evidence but withdrawn
from the active fork under `566c2e23`. The device-bound core suppresses EQ on
buffered SD reads. The qualified executor uses the first three patches only;
the retired patch still carries its original upstream/licence provenance.

Every patch header binds the same upstream commit and licence. The active DWX
blind-spot contract additionally binds the complete patch-set identity,
patched-source hashes and executor binary hash; an incomplete patch set is a
different tool.

The headless-input patch also consumes a generated navigation header from
`config/v11-l-lite-keymap.json`. This generated source and the revised patch
are bound by the navigation requalification; UART/HWA coverage remains
distinct from physical keyboard behavior.

## cc65 spike

The historical `spike/cc65/` experiment was compiled with cc65. cc65 is
distributed under the zlib licence; see <https://github.com/cc65/cc65> and its
`LICENSE` file. lisp65 retains the original spike source, not cc65 itself or
the generated `.o`/`.elf` binaries. Those extensions are ignored repository
wide so generated spike outputs cannot silently become source artifacts.

## MEGA65 reference documents

The private mirror contains locally pinned MEGA65 manuals and reference PDFs.
They are not covered by the lisp65 license and are excluded from the public
repository and lisp65 release assets. Public documentation should link to the
official MEGA65 documentation instead of redistributing these files.
