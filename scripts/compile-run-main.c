/* Host compile-and-run smoke: compile a form with the device compiler, assemble a CodeObject,
 * execute it in host vm_run, and check the result. This semantic end-to-end verification is
 * stronger than byte equality and supports macro and REPL integration. Exit 0 means PASS. */
#include <stdio.h>
#include <string.h>
#include "obj.h"
#include "mem.h"
#include "symbol.h"
#include "reader.h"
#include "vm.h"
#include "compile.h"

/* Platform seam: host vm_run reads code_store instead of banked device RAM. */
static uint8_t code_store[1024];
void vm_code_load(uint8_t bank, uint16_t off, uint16_t len, uint8_t *dst) { (void)bank; memcpy(dst, code_store + off, len); }

static int failed = 0;
#define NF 8
static bc_func FN[NF]; static uint8_t CODE[NF][160]; static obj LIT[NF][16];

/* Kompilieren -> Main @0 assemblieren, Helper dahinter (registriert) -> vm_run(Main). */
static obj compile_run(const char *src) {
    const char *p = src; obj form = read_expr(&p);
    bc_unit u; int i; uint16_t off, mainlen;
    u.fn = FN; u.fncap = NF; u.nfn = 0; u.gensym = 0; u.err = 0;
    for (i = 0; i < NF; i++) { FN[i].code = CODE[i]; FN[i].codecap = 160; FN[i].lit = LIT[i]; FN[i].litcap = 16; }
    bc_compile_top(&u, form);
    if (u.err) { vm_status = 0xFF; return NIL; }
    vm_dir_reset();
    mainlen = bc_assemble(&u.fn[0], code_store, sizeof code_store);
    off = mainlen;
    for (i = 1; i < u.nfn; i++) {                          /* Lambda-Helper registrieren */
        uint16_t hlen = bc_assemble(&u.fn[i], code_store + off, (uint16_t)(sizeof code_store - off));
        int di = vm_dir_add(u.fn[i].name, 0, off, hlen);
        if (di < 0) { vm_status = 0xFE; return NIL; }
        set_sym_function(u.fn[i].name, MK_BCODE(di));
        off += hlen;
    }
    return vm_run(0, 0, mainlen, NULL, 0);
}

static void expect_fix(const char *src, int16_t n) {
    obj got = compile_run(src);
    int ok = (vm_status == VM_OK) && IS_FIX(got) && FIXVAL(got) == n;
    printf("%-38s => %s\n", src, ok ? "OK" : "FAIL");
    if (!ok) { failed++; printf("      status=%u fix=%d val=%d (want %d)\n",
              vm_status, (int)(IS_FIX(got) != 0), IS_FIX(got) ? FIXVAL(got) : 0, n); }
}
static void expect_nil(const char *src) {
    obj got = compile_run(src);
    int ok = (vm_status == VM_OK) && got == NIL;
    printf("%-38s => %s\n", src, ok ? "OK (nil)" : "FAIL"); if (!ok) failed++;
}
static void expect_t(const char *src) {
    obj got = compile_run(src);
    int ok = (vm_status == VM_OK) && got == intern("t");
    printf("%-38s => %s\n", src, ok ? "OK (t)" : "FAIL"); if (!ok) failed++;
}

/* Lambda end-to-end without apply/eval.c: register the helper under the name from callsrc,
 * then execute (name args) through OP_CALL using only the vm.c path. */
static void lambda_call(const char *lam, const char *callsrc, int16_t want) {
    const char *p; obj form, nm; bc_unit u; int i; uint16_t hlen, hoff, mlen;
    obj got; int ok;
    u.fn = FN; u.fncap = NF; u.nfn = 0; u.gensym = 0; u.err = 0;
    for (i = 0; i < NF; i++) { FN[i].code = CODE[i]; FN[i].codecap = 160; FN[i].lit = LIT[i]; FN[i].litcap = 16; }
    p = lam; form = read_expr(&p); bc_compile_top(&u, form);
    if (u.err || u.nfn < 2) { printf("%-22s + %-12s => FAIL(compile)\n", lam, callsrc); failed++; return; }
    vm_dir_reset();
    hlen = bc_assemble(&u.fn[1], code_store, sizeof code_store);        /* Helper @ 0 */
    { const char *q = callsrc; obj cf = read_expr(&q); nm = cell_a(cf); }
    set_sym_function(nm, MK_BCODE(vm_dir_add(nm, 0, 0, hlen)));         /* unter callsrc-Name registrieren */
    hoff = hlen;
    u.nfn = 0; u.gensym = 0; u.err = 0;
    p = callsrc; form = read_expr(&p); bc_compile_top(&u, form);       /* (name args) -> CALL */
    mlen = bc_assemble(&u.fn[0], code_store + hoff, (uint16_t)(sizeof code_store - hoff));
    got = vm_run(0, hoff, mlen, NULL, 0);
    ok = (vm_status == VM_OK) && IS_FIX(got) && FIXVAL(got) == want;
    printf("%-22s + %-12s => %s\n", lam, callsrc, ok ? "OK" : "FAIL");
    if (!ok) { failed++; printf("      status=%u val=%d (want %d)\n", vm_status, IS_FIX(got) ? FIXVAL(got) : -999, want); }
}

int main(void) {
    mem_init(); vm_init();
    puts("== Ausdruecke + Kontrollfluss ==");
    expect_fix("(+ 1 2)", 3);
    expect_fix("(* (+ 1 2) 3)", 9);
    expect_fix("(- 10 3)", 7);
    expect_fix("(remainder 17 5)", 2);
    expect_fix("(if (< 1 2) 10 20)", 10);
    expect_fix("(if (> 1 2) 10 20)", 20);
    expect_fix("(progn 1 2 3)", 3);
    expect_fix("(car (cons 1 2))", 1);
    expect_fix("(cdr (cons 1 2))", 2);
    puts("== Bindungen ==");
    expect_fix("(let ((x 5)) (+ x 1))", 6);
    expect_fix("(let ((x 2) (y 3)) (* x y))", 6);
    expect_fix("(let* ((a 2) (b (+ a 3))) (* a b))", 10);
    expect_fix("(let ((x 1)) (setq x 9) (+ x 1))", 10);
    puts("== Globale Wert-Zellen ==");
    expect_nil("fresh-global");
    expect_fix("(progn (setq m6g 41) (+ m6g 1))", 42);
    expect_fix("(setq m6a 1 m6b 2)", 2);
    puts("== or / and / cond ==");
    expect_fix("(or nil 7)", 7);
    expect_fix("(or 3 nil)", 3);
    expect_nil("(or nil nil)");
    expect_fix("(and 1 2 3)", 3);
    expect_nil("(and 1 nil 3)");
    expect_fix("(cond ((< 5 1) 10) ((< 1 5) 20) (t 30))", 20);
    expect_fix("(cond ((< 5 1) 10) (t 30))", 30);
    expect_t("(>= 5 3)");
    expect_nil("(>= 3 5)");
    puts("== Schleifen (dotimes / dolist) ==");
    expect_fix("(let ((s 0)) (dotimes (i 5 s) (setq s (+ s i))))", 10);
    expect_fix("(let ((n 0)) (dotimes (i 3) (setq n (+ n 1))) n)", 3);
    expect_fix("(let ((s 0)) (dolist (x (quote (4 5 6)) s) (setq s (+ s x))))", 15);
    expect_fix("(let ((p 1)) (dotimes (i 4 p) (setq p (* p 2))))", 16);
    expect_nil("(dotimes (i 3) nil)");                 /* result default nil */

    puts("== case ==");
    expect_fix("(case 2 (1 10) (2 20) (t 30))", 20);
    expect_fix("(case 5 (1 10) (2 20) (t 30))", 30);
    expect_fix("(case 1 (1 10) (2 20))", 10);
    expect_nil("(case 9 (1 10) (2 20))");

    puts("== lambda end-to-end (Helper laeuft via OP_CALL) ==");
    lambda_call("(lambda (x) (* x x))",        "(sq 5)",     25);
    lambda_call("(lambda (a b) (+ a b))",      "(add 4 6)",  10);
    lambda_call("(lambda (n) (if (< n 0) 0 n))", "(clamp 7)",  7);
    lambda_call("(lambda (n) (if (< n 0) 0 n))", "(clamp -3)", 0);
    lambda_call("(lambda (a &rest r) (car r))", "(f 1 2 3)",  2);   /* &rest: r=(2 3) */
    lambda_call("(lambda (&rest r) (car r))",   "(g 7 8)",    7);   /* &rest: r=(7 8) */

    printf(failed ? "\nFAILED (%d)\n" : "\nALL PASS\n", failed);
    return failed ? 1 : 0;
}
