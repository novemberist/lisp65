/*
 * Standalone current-toolchain repro candidate for historical finding L3.
 *
 * It deliberately uses the stock KERNAL CHROUT path and emits enough lines
 * to cross the bottom row.  The binary is only an issue attachment after a
 * fresh hardware run against the recorded compiler/core pair.
 */
#include <cbm.h>
#include <stdint.h>

int main(void) {
    cbm_k_chrout(0x93); /* clear screen */
    for (uint8_t line = 0; line != 32; ++line) {
        cbm_k_chrout('L');
        cbm_k_chrout((uint8_t)('0' + (line / 10)));
        cbm_k_chrout((uint8_t)('0' + (line % 10)));
        cbm_k_chrout(0x0d);
    }
    cbm_k_chrout('O');
    cbm_k_chrout('K');
    for (;;) {
    }
}
