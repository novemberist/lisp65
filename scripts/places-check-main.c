/* lisp65 — host gate for the setf MVP (lib/stdlib-places.lisp; Lane K, C phase step 5).
 * Checks place macros on BOTH engines as an anti-drift measure: directly in treewalk and through
 * compiled by lcc (lcc-run -> macroexpand-1 -> bytecode on vm_run). Pattern: smoke-main. */
#include <setjmp.h>
#include <stdio.h>
#include <string.h>
#include "eval.h"
#include "interrupt.h"
#include "obj.h"
#include "reader.h"
#include "symbol.h"
#include "vm.h"

static uint8_t lcc_store[8192];
static uint16_t lcc_off;
static int failed;

void vm_code_load(uint8_t bank, uint16_t off, uint16_t len, uint8_t *dst) {
    (void)bank;
    memcpy(dst, lcc_store + off, len);
}
int lcc_region_alloc(uint16_t len, uint8_t *bank, uint16_t *off) {
    if ((uint32_t)lcc_off + len > sizeof lcc_store) return 0;
    *bank = 0; *off = lcc_off;
    lcc_off = (uint16_t)(lcc_off + len);
    return 1;
}
void lcc_region_write(uint8_t bank, uint16_t off, const uint8_t *src, uint16_t len) {
    (void)bank;
    memcpy(lcc_store + off, src, len);
}

static char srcbuf[98304];
static int load_file(const char *path) {
    FILE *f = fopen(path, "rb");
    size_t n;
    if (!f) { printf("FAIL: open %s\n", path); return 0; }
    n = fread(srcbuf, 1, sizeof srcbuf - 1, f);
    fclose(f);
    srcbuf[n] = '\0';
    lisp_error_msg = 0;
    lisp_toplevel_active = 1;
    if (setjmp(lisp_toplevel)) {
        printf("FAIL: load %s: %s\n", path, lisp_error_msg ? lisp_error_msg : "error");
        return 0;
    }
    load_source(srcbuf);
    lisp_toplevel_active = 0;
    if (lisp_error_msg) { printf("FAIL: load %s: %s\n", path, lisp_error_msg); return 0; }
    return 1;
}

static obj run_form(const char *src, const char **err) {
    const char *p = src;
    obj form = read_expr(&p), r = NIL;
    lisp_error_msg = 0;
    lisp_toplevel_active = 1;
    if (setjmp(lisp_toplevel)) {
        *err = lisp_error_msg ? lisp_error_msg : "error";
        lisp_toplevel_active = 0;
        return NIL;
    }
    r = eval(form);
    lisp_toplevel_active = 0;
    *err = lisp_error_msg;
    return r;
}
static void expect_fix(const char *src, int16_t want) {
    const char *err = 0;
    obj got = run_form(src, &err);
    int ok = !err && IS_FIX(got) && FIXVAL(got) == want;
    printf("%-64s => %s\n", src, ok ? "OK" : "FAIL");
    if (!ok) { printf("   err=%s got=%d\n", err ? err : "-", IS_FIX(got) ? FIXVAL(got) : -999); failed++; }
}

int main(void) {
    eval_init();
    lcc_off = 0;
    if (!load_file("lib/lcc.lisp")) return 1;
    if (!load_file("lib/prelude-m1.lisp")) return 1;     /* cadr and friends for plists; product uses the blob */
    if (!load_file("lib/stdlib-plists.lisp")) return 1;
    if (!load_file("lib/stdlib-places.lisp")) return 1;

    puts("== Treewalk-Pfad ==");
    expect_fix("(progn (setq z 5) (incf z) z)", 6);
    expect_fix("(progn (incf z 10) z)", 16);
    expect_fix("(progn (decf z 6) z)", 10);
    expect_fix("(progn (setq l (list 1 2 3)) (setf (car l) 9) (car l))", 9);
    expect_fix("(progn (setf (cdr l) (list 7)) (car (cdr l)))", 7);
    expect_fix("(progn (push 4 l) (car l))", 4);
    expect_fix("(pop l)", 4);
    expect_fix("(car l)", 9);
    expect_fix("(progn (setq pl nil) (setf (getf pl (quote k)) 42) (getf pl (quote k)))", 42);
    expect_fix("(progn (setf (getf pl (quote k)) 5) (getf pl (quote k)))", 5);

    puts("== lcc-Pfad (Makros in kompiliertem Code) ==");
    expect_fix("(progn (lcc-run (quote (defun pt () (progn (setq w 3) (incf w 4) w)))) (pt))", 7);
    expect_fix("(progn (lcc-run (quote (defun pu (x) (progn (push 1 x) (pop x))))) (pu (list 5)))", 1);
    expect_fix("(progn (lcc-run (quote (defun pv (p) (progn (setf (car p) 8) (car p))))) (pv (list 0 0)))", 8);

    if (failed) { printf("FAILED=%d\n", failed); return 1; }
    puts("ALL PASS");
    return 0;
}
