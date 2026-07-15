/* lisp65 S5: measure how many symbols the device compiler interns while compiling
 * the complete stdlib and IDE source on the host. Reports MAX_SYM demand and the
 * share of __L helper symbols caused by gensym leakage. Usage: s5-symcount <bundle.lisp> */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "obj.h"
#include "mem.h"
#include "symbol.h"
#include "reader.h"
#include "vm.h"
#include "compile_repl.h"

void vm_code_load(uint8_t bank, uint16_t off, uint16_t len, uint8_t *dst){ (void)bank; memcpy(dst, crepl_store+off, len); }
void load_source(const char *src);   /* aus compile_repl.c (unter LISP65_COMPILE_REPL) */

int main(int argc, char **argv) {
    const char *path = argc > 1 ? argv[1] : "build/s5/stdlib-source.lisp";
    FILE *f = fopen(path, "rb");
    if (!f) { fprintf(stderr, "kann %s nicht oeffnen\n", path); return 2; }
    fseek(f, 0, SEEK_END); long n = ftell(f); fseek(f, 0, SEEK_SET);
    char *src = malloc((size_t)n + 1); fread(src, 1, (size_t)n, f); src[n] = 0; fclose(f);

    mem_init(); vm_init(); vm_dir_reset(); crepl_reset();
    uint16_t sym_before = sym_count();
    load_source(src);
    uint16_t sym_after = sym_count();

    /* __L-Helfer zaehlen (Gensym-Leck) */
    uint16_t helpers = 0, i;
    for (i = 0; i < sym_after; i++) {
        const char *nm = symname(sym_nth(i));
        if (nm[0] == '_' && nm[1] == 'L' && nm[2] >= '0' && nm[2] <= '9') helpers++;
    }
    printf("Quelle: %s (%ld B)\n", path, n);
    printf("Symbole vor Load:  %u\n", sym_before);
    printf("Symbole nach Load: %u  (Bedarf = MAX_SYM-Untergrenze)\n", sym_after);
    printf("davon __L-Helfer (Gensym-Leck): %u\n", helpers);
    printf("ohne das Leck waeren es: %u\n", (uint16_t)(sym_after - helpers));
    return 0;
}
