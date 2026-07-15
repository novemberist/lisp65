/* Exact C-side boot symbol count for lisp65.
 *
 * Manifest-based footprint tools count blob defun names but not symbols interned by eval_init:
 * primitives, special forms, and cached k_* symbols. The observed correction was eight symbols.
 *
 * The DMA-based embedded blob boot cannot run on the host, but eval_init can. This program
 * reports the exact profile-specific C symbol count that manifest tools add to blob defuns.
 *
 * Build/run through scripts/boot-symcount.sh <profile>. Prints the C count and names. */
#include <stdio.h>
#include "obj.h"
#include "symbol.h"
#include "eval.h"

/* Host stubs for device seams referenced by eval.c. They are never called; only primitive names
 * are interned. */
void vm_code_load(unsigned char bank, unsigned short off, unsigned short len, unsigned char *dst) {
    (void)bank; (void)off; (void)len; (void)dst; }   /* never called; only eval_init interns */
#ifdef LISP65_LCC_INSTALL
int  lcc_region_alloc(unsigned short len, unsigned char *bank, unsigned short *off) {
    (void)len; (void)bank; (void)off; return 0; }
void lcc_region_write(unsigned char bank, unsigned short off, const unsigned char *src, unsigned short len) {
    (void)bank; (void)off; (void)src; (void)len; }
#endif

int main(void) {
    uint16_t before, after, i;
    /* eval_init interns mem_init, primitives, special forms, and the k_* cache. */
    before = 0;
    eval_init();
    after = sym_count();
    printf("boot-symcount (C-Anteil, eval_init): %u Symbole\n", (unsigned)(after - before));
    printf("MAX_SYM(Profil)=%u\n", sym_max());
    printf("--- C-Symbol-Namen (die das Manifest-Tool ADDIEREN muss) ---\n");
    for (i = 0; i < after; i++) {
        const char *nm = symname(sym_nth(i));
        printf("%s%s", nm, (i + 1) % 6 == 0 ? "\n" : "  ");
    }
    printf("\n");
    return 0;
}
