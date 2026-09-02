# Phase-0 Toolchain Spike

This directory preserves the experiment that selected C with llvm-mos for the
native MEGA65 kernel instead of a hand-written assembly core or a C64-only C
toolchain. It is historical evidence, not a current build entry point.

## Result

The no-stdio compute benchmark measured:

| Toolchain | Target | PRG bytes |
| --- | --- | ---: |
| llvm-mos `-Os` | C64 | 665 |
| llvm-mos `-Os`/`-O3` | MEGA65 | 686 |
| cc65 `-O` | C64 | 871 |

llvm-mos produced roughly 22% smaller compute code than cc65 and, unlike cc65,
provided a native MEGA65 target with access to the 45GS02 and expanded machine.
Hand assembly remained potentially smaller but carried substantially higher
implementation and maintenance cost.

The earlier printf-based benchmark is not representative: 32-bit libc output
dominated its size. `bench-nolib.c`, which stores results in volatile globals,
is the relevant code-generation comparison.

## Hardware result

The acme C64, cc65 C64, and llvm-mos native MEGA65 artifacts were all run on a
physical MEGA65 on 2026-06-30. Only llvm-mos exercised the native MEGA65 mode;
the C64 toolchains remained constrained to C64 mode.

## Reproducing the historical builds

```sh
( cd asm && acme hello.asm )
( cd cc65 && cl65 -t c64 -O hello.c -o hello-cc65.prg )
( cd llvm-mos && ../../tools/llvm-mos/bin/mos-mega65-clang -Os hello.c -o hello-llvmmos-mega65.prg )
( cd llvm-mos && ../../tools/llvm-mos/bin/mos-c64-clang -Os hello.c -o hello-llvmmos-c64.prg )
```

Generated PRG files are ignored. Current product builds and verification are
documented in [`docs/development.md`](../docs/development.md).
