/* Host prelude compilability diagnostic.
 *
 * Checks whether the device compiler can translate every top-level form in the embedded prelude.
 * Only then can load_source switch to compile_run_top_form and omit treewalk eval_env. This is a
 * diagnostic rather than a release gate: it reports defun failures with source and classifies
 * defmacro/defparameter/defvar separately for the REPL integration path. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "obj.h"
#include "mem.h"
#include "symbol.h"
#include "reader.h"
#include "vm.h"
#include "compile_repl.h"

/* Host seam: vm_run reads the compiled-function region populated by compile_repl.c. */
void vm_code_load(uint8_t bank, uint16_t off, uint16_t len, uint8_t *dst) { (void)bank; memcpy(dst, crepl_store + off, len); }

static int is_head(obj form, const char *name) {
    return IS_PTR(form) && cell_type(form) == T_CONS && cell_a(form) == intern(name);
}

int main(void) {
    static char buf[65536];
    FILE *f = fopen("lib/prelude-m1.lisp", "rb");
    if (!f) { perror("prelude-m1.lisp"); return 2; }
    size_t n = fread(buf, 1, sizeof buf - 1, f); buf[n] = '\0'; fclose(f);

    mem_init(); vm_init(); vm_dir_reset(); crepl_reset();

    int def_ok = 0, def_fail = 0, mac = 0, glob = 0, other_ok = 0, other_fail = 0;
    const char *p = buf;
    for (;;) {
        while (*p == ' ' || *p == '\t' || *p == '\n' || *p == '\r') p++;
        if (*p == ';') { while (*p && *p != '\n') p++; continue; }
        if (*p == '\0') break;
        const char *start = p;
        obj form = read_expr(&p);

        if (is_head(form, "defmacro"))      { mac++;  continue; }   /* REPL-Swap: bekannte Form -> Compiler lowert selbst */
        if (is_head(form, "defparameter") ||
            is_head(form, "defvar"))        { glob++; continue; }   /* REPL-Swap: globaler Define (set-symbol-value) */

        int is_defun = is_head(form, "defun");
        vm_status = VM_OK;
        obj r = compile_run_top_form(form);
        int ok = (vm_status == VM_OK) && (r != NIL || !is_defun);

        if (is_defun) { if (ok) def_ok++; else { def_fail++; goto report_fail; } }
        else          { if (ok) other_ok++; else { other_fail++; goto report_fail; } }
        continue;
    report_fail:
        {   int len = (int)(p - start); while (len > 0 && (start[len-1]=='\n'||start[len-1]==' ')) len--;
            if (len > 72) len = 72;
            printf("  FAIL (status=%u): %.*s%s\n", vm_status, len, start, len >= 72 ? " ..." : ""); }
    }

    printf("\n=== Prelude-Compile-Gate ===\n");
    printf("defun:        %d OK, %d FAIL\n", def_ok, def_fail);
    printf("andere Formen:%d OK, %d FAIL\n", other_ok, other_fail);
    printf("defmacro:     %d (vom REPL-Swap gesondert behandelt: Compiler lowert die Form selbst)\n", mac);
    printf("defparam/var: %d (globaler Define via set-symbol-value)\n", glob);
    int fail = def_fail + other_fail;
    printf("\n%s\n", fail ? ">>> Compiler deckt das Prelude NICHT voll ab -- obige Formen brauchen Codegen-Arbeit."
                          : ">>> Compiler deckt ALLE Prelude-defuns ab -- load_source-Swap ist ohne M5 erreichbar.");
    return fail ? 1 : 0;
}
