/* lisp65 phase-0 spike: minimal C PRG built with llvm-mos.
 * It performs the same banner task as the acme and cc65 spikes.
 * Build for native MEGA65: ../../tools/llvm-mos/bin/mos-mega65-clang -Os hello.c -o hello-llvmmos-mega65.prg
 * Build for C64 mode:     ../../tools/llvm-mos/bin/mos-c64-clang    -Os hello.c -o hello-llvmmos-c64.prg
 * Run on MEGA65: etherload -5 -r hello-llvmmos-mega65.prg
 * Run in C64 mode: etherload -4 -r hello-llvmmos-c64.prg
 */
#include <stdio.h>

int main(void) {
    printf("lisp65 llvm-mos spike ok\n");
    return 0;
}
