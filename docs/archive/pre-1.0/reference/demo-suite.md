# lisp65 Demo Suite

This suite is a small set of readable Lisp programs for manual demos and
post-change sanity checks on the MEGA65.  The sources live in `demos/` and are
packaged as plain source files on a D81 image, together with preallocated FASL
slots for on-device `compile-file`.

## Build

```sh
make demo-suite-check
make demo-suite-d81
```

Artifacts:

- `build/demos/lisp65-demo-suite.d81`
- `build/demos/demo-suite-manifest.txt`

`demo-suite-check` compiles the same demo sources through the host P0 compiler
against the resident Ein-Suite surface.  It is also part of `make check`.

## D81 Contents

| Disk file | Host source | FASL slot | Run function |
| --- | --- | --- | --- |
| `dindex` | `demos/demo-index.lisp` | none | `demo-index` |
| `dsimp` | `demos/d00-simplify.lisp` | `fsimp` | `demo-simplify-run` |
| `dstr` | `demos/d01-strings.lisp` | `fstr` | `demo-strings-run` |
| `dlam` | `demos/d02-lambda.lisp` | `flam` | `demo-lambda-run` |
| `dscr` | `demos/d03-screen.lisp` | `fscr` | `demo-screen-run` |
| `dadv` | `demos/d04-adventure.lisp` | `fadv` | `demo-adv-run` |
| `dide` | `demos/d05-ide-buffer.lisp` | `fide` | `demo-ide-run` |
| `dnum` | `demos/d06-numbers.lisp` | `fnum` | `demo-numbers-run` |

The image also includes `ide` by default, using
`build/bytecode/libs/ide.ext.bin`, so Dev-Core users can load the IDE library
from the same mounted D81.

## Device Usage

Upload and mount the D81 through the normal MEGA65 disk workflow, then compile
individual demos on the device:

```lisp
(compile-file "dsimp" "fsimp")
(load "fsimp")
(demo-simplify-run)
```

Every `demo-*-run` function returns `42` on success.  The screen demo also
draws to the display.  On Dev-Core, load the IDE library before running the IDE
buffer demo:

```lisp
(load-lib "ide")
(compile-file "dide" "fide")
(load "fide")
(demo-ide-run)
```

All demo source files intentionally contain only top-level `defun` forms and
comments.  That keeps them inspectable in the IDE while staying compatible with
the current device `compile-file` implementation.

## Automated Hardware Check

The full demo suite can also be exercised on real MEGA65 hardware:

```sh
make hw-demo-suite-dry-run
make hw-demo-suite
```

The runner builds the Dev-Core/FASL profile, uploads the demo D81 as
`DEMOS.D81`, compiles the demo sources on the device, loads each generated FASL
slot, runs the public `demo-*-run` entry and checks final screen markers through
JTAG.

The default hardware target runs four fresh shards, because FASL-loaded symbols
and directory entries are append-only in the current runtime:

```text
demo core pass 9/9
demo screen pass 3/3
demo advnum pass 6/6
demo ide pass 4/4
```

Last live hardware validation: 2026-07-07, direct Etherload only, JTAG
`/dev/ttyUSB1`, no hard `m65 -F` reset.  All four markers above were observed
with `gc_badobj=0`.

The Adventure demo is intentionally kept compact.  A larger 13-`defun` variant
compiled and loaded but left its final public entry unbound on hardware after
FASL load; this version keeps the same state-machine behavior with fewer FASL
entries.
