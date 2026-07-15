/* Host smoke test for the LISP65_EVAL_PRIMS seam. Exercises eval and eval-string on the real
 * treewalk path, including multi-form sources, final-value return, persistent defuns, and stream
 * survival under allocation pressure. Exit 0 means every check passed.
 * Ad-hoc build: cc -DLISP65_EVAL_PRIMS ... scripts/eval-prims-smoke.c
 *   src/eval.c src/reader.c src/printer.c src/mem.c src/symbol.c src/interrupt.c src/io.c */
#include <stdio.h>
#include <string.h>
#include "obj.h"
#include "mem.h"
#include "reader.h"
#include "eval.h"
#include "interrupt.h"

static int fails = 0;
static void check(const char *label, const char *src, int16_t want) {
    const char *p = src;
    obj r = eval(read_expr(&p));
    int ok = (r != NIL) && !IS_PTR(r) && FIXVAL(r) == want;
    printf("  %-58s => %s\n", label, ok ? "OK" : "FAIL");
    if (!ok) fails++;
}

int main(void) {
    const char *p;
    obj r;
    eval_init();
    /* 1) eval: data -> code */
    check("(eval (quote (+ 2 3)))", "(eval (quote (+ 2 3)))", 5);
    /* 2) eval-string: one form */
    check("(eval-string \"(* 6 7)\")", "(eval-string \"(* 6 7)\")", 42);
    /* 3) Multiple forms, final value, and persistent defun; the IDE region-eval case. */
    check("(eval-string \"(defun sq (x) (* x x)) (sq 5)\")",
          "(eval-string \"(defun sq (x) (* x x)) (sq 5)\")", 25);
    check("sq persistiert nach eval-string: (sq 9)", "(sq 9)", 81);
    /* 4) Comments and whitespace in an editor source stream. */
    check("eval-string mit Kommentar/Newlines",
          "(eval-string \"; kommentar\n(+ 1\n   2)\")", 3);
    /* 5) GC robustness: the stream survives allocation pressure during evaluation. */
    check("GC-Haerte (viel Allokation im Stream)",
          "(eval-string \"(defun f (n acc) (if (eql n 0) acc (f (- n 1) (car (cons acc nil))))) (f 40 7)\")", 7);
    /* 6) Nesting: construct the inner source from character codes to cover list->string. */
    check("verschachteltes eval-string (innerer String via list->string)",
          "(eval-string \"(eval-string (list->string (list 40 43 32 50 48 32 50 50 41)))\")", 42);
    /* 7) A reader error ends only the current source; the next evaluation remains healthy. */
    p = "(eval-string \"(+ 1 2\")";
    lisp_error_msg = 0;
    r = eval(read_expr(&p));
    if (r != NIL || reader_status != READER_ERROR || lisp_error_msg == 0 || gc_rootsp != 0) fails++;
    lisp_error_msg = 0;
    check("Erholung nach eval-string-Readerfehler", "(+ 20 22)", 42);
    load_source("(defun reader-before () 1) (broken");
    if (reader_status != READER_ERROR || lisp_error_msg == 0 || gc_rootsp != 0) fails++;
    lisp_error_msg = 0;
    load_source("(defun reader-after () 42)");
    check("Erholung nach Treewalk-Loaderfehler", "(reader-after)", 42);
    if (fails == 0) { printf("ALL PASS (eval-prims-smoke)\n"); return 0; }
    printf("FAILED: %d\n", fails);
    return 1;
}
