/* lisp65 — host reproduction of the blob-boot heap bug (Lane K, 2026-07-05).
 * xemu showed that after blob boot (EXT-first allocation, gc_freeze_boot, hot=60),
 * (length (quote (1 x16))) returned zero and defun bodies compiled empty. This harness
 * recreates that boot state with LISP65_EXT_HEAP and host ext_sim: about 300 boot conses,
 * rooted permanently like literal-table patches, followed by gc_freeze_boot and REPL input
 * through compile_run_top_form. Exit zero means PASS; the bug produces FAIL. */
#include <stdio.h>
#include <string.h>
#include "obj.h"
#include "mem.h"
#include "symbol.h"
#include "reader.h"
#include "vm.h"
#include "compile_repl.h"

void vm_code_load(uint8_t bank, uint16_t off, uint16_t len, uint8_t *dst) { (void)bank; memcpy(dst, crepl_store + off, len); }

static int failed = 0;
static obj run(const char *s) { const char *p = s; return compile_run_top_form(read_expr(&p)); }
static void expect_fix(const char *src, int16_t n) {
    obj got = run(src);
    int ok = (vm_status == VM_OK) && IS_FIX(got) && FIXVAL(got) == n;
    printf("%-52s => %s", src, ok ? "OK" : "FAIL");
    if (!ok) { failed++; printf("  (status=%u val=%d want %d)", vm_status, IS_FIX(got) ? FIXVAL(got) : -999, n); }
    printf("\n");
}

int main(void) {
    int i;
    mem_init(); vm_init(); vm_dir_reset(); crepl_reset();

    /* Boot simulation: allocate about 300 EXT cells (mem_init is EXT-first), root
     * them permanently like literal-table objects, then freeze as main.c does after blob boot. */
    for (i = 0; i < 150; i++) {
        obj l = cons(MKFIX(i), NIL);
        GC_PUSH(l);
        l = cons(MKFIX(i), gc_rootstack[GC_TOP]); GC_SET(GC_TOP, l);   /* rooted two-item list */
    }
    printf("boot: %d permanents gerootet, gc_runs=%u\n", 150, gc_runs);
    gc_freeze_boot();

    /* Define the function before heap pressure, matching blob-boot behavior observed in xemu. */
    run("(defun len16 (l) (if l (+ 1 (len16 (cdr l))) 0))");
    printf("defun len16 => %s\n", vm_status == VM_OK ? "OK" : "FAIL(status)");

    expect_fix("(+ 1 2)", 3);
    expect_fix("(len16 (quote (9 9 9 9)))", 4);
    /* xemu reproduction: a large quoted list exhausts the hot remainder and triggers GC in read/compile. */
    expect_fix("(len16 (quote (1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1)))", 16);
    expect_fix("(len16 (quote (1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1)))", 16);   /* repeat at a different heap state */
    for (i = 0; i < 8; i++) expect_fix("(len16 (quote (1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1)))", 16);
    run("(defun sq (x) (* x x))");
    expect_fix("(sq 5)", 25);
    printf("gc_runs am Ende: %u\n", gc_runs);
    printf(failed ? "\nFAILED (%d)\n" : "\nALL PASS\n", failed);
    return failed ? 1 : 0;
}
