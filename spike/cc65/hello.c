/* lisp65 phase-0 spike: minimal C64 PRG written in C with cc65.
 * It performs the same task as the acme spike by printing a banner.
 * Build: cl65 -t c64 -O hello.c -o hello-cc65.prg
 * Run:   etherload -4 -r hello-cc65.prg (C64 mode on a real MEGA65)
 */
#include <conio.h>

int main(void) {
    clrscr();
    cputs("lisp65 cc65 spike ok");
    return 0;
}
