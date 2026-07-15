/* lisp65 — REPL session host test (Lane K, M6). Validates extracted src/compile_repl.c:
 * compile_run_top_form, the compiled-function region, and top-level defun including
 * recursion and redefinition on host vm_run, the operation shared by the REPL swap and
 * load_source (design section 4a). Exit zero means PASS. */
#include <stdio.h>
#include <string.h>
#include "obj.h"
#include "mem.h"
#include "symbol.h"
#include "reader.h"
#include "eval.h"
#include "vm.h"
#include "compile_repl.h"
#include "interrupt.h"

/* Platform seam: host vm_run reads code from the compiled-function region
 * (crepl_store) filled by src/compile_repl.c. On device, vm_code_load reads Bank 5. */
void vm_code_load(uint8_t bank, uint16_t off, uint16_t len, uint8_t *dst) { (void)bank; memcpy(dst, crepl_store + off, len); }

static int failed = 0;
static obj do_form(const char *src) { const char *p = src; return compile_run_top_form(read_expr(&p)); }

static void expect_fix(const char *src, int16_t n) {
    obj got = do_form(src);
    int ok = (vm_status == VM_OK) && IS_FIX(got) && FIXVAL(got) == n;
    printf("%-48s => %s\n", src, ok ? "OK" : "FAIL");
    if (!ok) { failed++; printf("      status=%u val=%d (want %d)\n", vm_status, IS_FIX(got) ? FIXVAL(got) : -999, n); }
}
static void def(const char *src) {
    obj got = do_form(src);
    printf("%-48s => %s\n", src, (vm_status == VM_OK) && got != NIL ? "def OK" : "FAIL");
    if (!(vm_status == VM_OK && got != NIL)) failed++;
}

int main(void) {
    mem_init(); vm_init(); vm_dir_reset(); crepl_reset();

    puts("== REPL-Sitzung: defun + Aufruf ==");
    def("(defun sq (x) (* x x))");
    expect_fix("(sq 5)", 25);
    expect_fix("(sq (sq 2))", 16);

    puts("== rekursives defun ==");
    def("(defun fact (n) (if (< n 2) 1 (* n (fact (- n 1)))))");
    expect_fix("(fact 5)", 120);
    expect_fix("(fact 0)", 1);

    puts("== defun ruft anderes defun; Ausdruck mischt beide ==");
    def("(defun add3 (a b c) (+ (+ a b) c))");
    expect_fix("(add3 (sq 2) (fact 3) 1)", 11);
    expect_fix("(let ((x 3)) (+ (sq x) (fact x)))", 15);

    puts("== defun mit Schleife + lokalem Zustand ==");
    def("(defun sumto (n) (let ((s 0)) (dotimes (i n s) (setq s (+ s i)))))");
    expect_fix("(sumto 5)", 10);
    expect_fix("(sumto 10)", 45);

    puts("== &rest-defun + globaler Zustand ==");
    def("(defun firstof (a &rest r) a)");
    expect_fix("(firstof 7 8 9)", 7);
    expect_fix("(progn (setq acc 0) (dolist (x (quote (1 2 3 4)) acc) (setq acc (+ acc x))))", 10);

    puts("== Redefinition ==");
    def("(defun sq (x) (+ x 100))");
    expect_fix("(sq 5)", 105);

    puts("== Readerfehler-Erholung im Compile-Loader ==");
    lisp_error_msg = 0;
    load_source("(defun reader-before () 1) (broken");
    if (reader_status != READER_ERROR || lisp_error_msg == 0 || gc_rootsp != 0) failed++;
    lisp_error_msg = 0;
    load_source("(defun reader-after () 42)");
    expect_fix("(reader-after)", 42);

    printf(failed ? "\nFAILED (%d)\n" : "\nALL PASS\n", failed);
    return failed ? 1 : 0;
}
