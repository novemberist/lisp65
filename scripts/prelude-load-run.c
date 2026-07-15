/* Host proof for swapping load_source to the compiled path.
 *
 * Every top-level form in the embedded prelude passes through compile_run_top_form, including
 * recognized defmacros and defparameter/defvar forms. The harness then calls prelude functions
 * and checks their results. Exit 0 proves that LISP65_COMPILE_REPL does not need eval_env. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "obj.h"
#include "mem.h"
#include "symbol.h"
#include "reader.h"
#include "vm.h"
#include "compile_repl.h"

void vm_code_load(uint8_t bank, uint16_t off, uint16_t len, uint8_t *dst) { (void)bank; memcpy(dst, crepl_store + off, len); }

static int failed = 0;
static obj run(const char *src) { const char *p = src; vm_status = VM_OK; return compile_run_top_form(read_expr(&p)); }

static void expect_fix(const char *src, int16_t n) {
    obj got = run(src);
    int ok = (vm_status == VM_OK) && IS_FIX(got) && FIXVAL(got) == n;
    printf("%-52s => %s\n", src, ok ? "OK" : "FAIL");
    if (!ok) { failed++; printf("      status=%u val=%d (want %d)\n", vm_status, IS_FIX(got) ? FIXVAL(got) : -999, n); }
}
static void expect_true(const char *src) {
    obj got = run(src);
    int ok = (vm_status == VM_OK) && got != NIL;
    printf("%-52s => %s\n", src, ok ? "OK (non-nil)" : "FAIL");
    if (!ok) failed++;
}

int main(void) {
    static char buf[65536];
    FILE *f = fopen("lib/prelude-m1.lisp", "rb");
    if (!f) { perror("prelude-m1.lisp"); return 2; }
    size_t n = fread(buf, 1, sizeof buf - 1, f); buf[n] = '\0'; fclose(f);

    mem_init(); vm_init(); vm_dir_reset(); crepl_reset();

    /* Phase 1: load the complete prelude like load_source and count errors. */
    int forms = 0, loadfail = 0;
    const char *p = buf;
    for (;;) {
        while (*p == ' ' || *p == '\t' || *p == '\n' || *p == '\r') p++;
        if (*p == ';') { while (*p && *p != '\n') p++; continue; }
        if (*p == '\0') break;
        vm_status = VM_OK;
        compile_run_top_form(read_expr(&p));
        forms++;
        if (vm_status != VM_OK) { loadfail++; printf("  LOAD-FAIL (Form %d, status=%u)\n", forms, vm_status); }
    }
    printf("Prelude geladen: %d Formen, %d Fehler\n\n", forms, loadfail);
    if (loadfail) failed++;

    /* Phase 2: call prelude functions and verify results. */
    puts("== Listen/Zugriff ==");
    expect_fix("(length (quote (1 2 3 4 5)))", 5);
    expect_fix("(nth 2 (quote (10 20 30 40)))", 30);
    expect_fix("(first (quote (42 1 2)))", 42);
    expect_fix("(second (quote (7 8 9)))", 8);
    expect_fix("(position 30 (quote (10 20 30 40)))", 2);
    expect_fix("(identity 99)", 99);

    puts("== append (das Immediate-Lambda-defun!) + reverse + remove ==");
    expect_fix("(length (append (quote (1 2)) (quote (3 4 5))))", 5);
    expect_fix("(car (reverse (quote (1 2 3))))", 3);
    expect_fix("(length (remove 2 (quote (1 2 3 2 4))))", 3);

    puts("== Praedikate ==");
    expect_true("(member 3 (quote (1 2 3 4)))");
    expect_true("(zerop 0)");
    expect_true("(plusp 5)");

    /* Higher-order calls use VM-native apply. vm_treewalk_apply remains unset, proving that
     * funcall/apply/mapcar of bytecode functions work without treewalk. */
    puts("== Higher-Order via VM-natives apply (ohne Treewalk!) ==");
    run("(defun dbl (x) (* x 2))");
    expect_fix("(funcall (function dbl) 21)", 42);
    expect_fix("(apply (function dbl) (quote (21)))", 42);
    expect_fix("(car (mapcar (function dbl) (quote (5 6 7))))", 10);
    expect_fix("(length (mapcar (function identity) (quote (1 2 3 4))))", 4);

    puts("== Primitive Funktionsdesignatoren (Codex-Bug #1) ==");
    expect_fix("(apply (function +) (quote (1 2 3 4)))", 10);      /* Arithmetik-Fold */
    expect_fix("(apply (function *) (quote (2 3 4)))", 24);
    expect_fix("(apply (function -) (quote (10 3 2)))", 5);
    expect_fix("(funcall (function +) 5 7)", 12);
    expect_true("(funcall (function numberp) 5)");                 /* CALLPRIM-Designator (Prim 6) */
    expect_true("(apply (function numberp) (quote (42)))");

    puts("== Mehrargumentiges apply (Codex-Bug #2) ==");
    run("(defun add2 (a b) (+ a b))");
    expect_fix("(apply (function add2) 3 (quote (4)))", 7);        /* Prefix-Arg + Liste */
    expect_fix("(apply (function add2) (quote (3 4)))", 7);
    expect_fix("(apply (function +) 1 2 (quote (3 4)))", 10);      /* Prefix-Args + primitiver Designator */

    puts("== M-closures Phase 1: flache Capture (ohne Treewalk!) ==");
    run("(defun adder (n) (lambda (x) (+ x n)))");
    expect_fix("(funcall (adder 10) 5)", 15);                      /* n=10 eingefangen */
    expect_fix("(funcall (adder 100) 1)", 101);
    expect_fix("(car (mapcar (adder 10) (quote (1 2 3))))", 11);   /* Closure als HOF-Argument */
    run("(setq a5 (adder 5))");
    run("(setq a9 (adder 9))");
    expect_fix("(+ (funcall a5 1) (funcall a9 1))", 16);           /* unabhaengige Captures: (5+1)+(9+1) */
    run("(defun make-const (k) (lambda () k))");                   /* parameterless closure with one capture */
    expect_fix("(funcall (make-const 42))", 42);

    puts("== M-closures Phase 3: mehrstufige/transitive Capture ==");
    run("(defun outer3 (a) (lambda (b) (lambda (c) (+ a (+ b c)))))");  /* c faengt a (2 Ebenen) + b (1 Ebene) */
    expect_fix("(funcall (funcall (funcall (function outer3) 1) 2) 3)", 6);
    expect_fix("(funcall (funcall (funcall (function outer3) 10) 20) 30)", 60);

    puts("== M-closures Phase 2: mutierbare Capture (setq, Zaehler-Trick) ==");
    run("(defun make-counter () (let ((c 0)) (lambda () (setq c (+ c 1)))))");
    run("(setq ctr (make-counter))");
    expect_fix("(funcall ctr)", 1);                                 /* Upvalue c mutiert + persistent */
    expect_fix("(funcall ctr)", 2);
    expect_fix("(funcall ctr)", 3);
    run("(setq ctr2 (make-counter))");
    expect_fix("(funcall ctr2)", 1);                                /* eigener Zaehler, unabhaengig von ctr */
    expect_fix("(funcall ctr)", 4);                                 /* ctr laeuft unbeirrt weiter */

    printf(failed ? "\nFAILED (%d)\n" : "\nALL PASS\n", failed);
    return failed ? 1 : 0;
}
