/* Test-only main for embedded Prelude allocation/GC stress. Lane T owns this harness file. */
#include "obj.h"
#include "reader.h"
#include "printer.h"
#include "eval.h"
#include "prelude_gen.h"

static obj eval_src(const char *src) {
    const char *p = src;
    return eval(read_expr(&p));
}

static uint8_t check_case(const char *expr, const char *expect) {
    obj got = eval_src(expr);
    obj want = eval_src(expect);
    if (got == want) return 1;

    emit_str("gc FAIL: ");
    emit_str(expr);
    emit_str(" got ");
    print_obj(got);
    emit_str(" expected ");
    print_obj(want);
    emit('\n');
    return 0;
}

int main(void) {
    uint8_t pass = 0;

    eval_init();
    load_source(prelude_src);

    load_source(
        "(defun fact (n) (if (zerop n) 1 (* n (fact (1- n)))))"
        "(defun adder (x) (lambda (y) (+ x y)))");

    pass += check_case("(fact 7)", "5040");
    pass += check_case("(length (reverse (list 1 2 3 4 5 6 7 8)))", "8");
    pass += check_case("(length (mapcar (lambda (x) (+ x 1)) (list 1 2 3 4 5)))", "5");
    pass += check_case("(let* ((a 1) (b (+ a 1)) (c (+ b 1))) c)", "3");
    pass += check_case("(length `(1 ,(+ 1 1) ,@(list 3 4) 5))", "5");
    pass += check_case("(cond ((eq 1 2) 'a) ((eq 2 2) 'b) (t 'c))", "'b");
    pass += check_case("(unless nil 'ok)", "'ok");
    pass += check_case("(case 'b ((a b) 7) (otherwise 9))", "7");
    pass += check_case("(cadr (assoc 2 (list (list 1 'a) (list 2 'b))))", "'b");
    pass += check_case("(funcall (adder 10) 5)", "15");
    pass += check_case("(apply (function +) (list 1 2 3))", "6");
    pass += check_case("(let ((s 0)) (mapc (lambda (x) (setq s (+ s x))) (list 1 2 3)) s)", "6");

    emit_str("lisp65 gc-stress: ");
    print_obj(MKFIX(pass));
    emit('\n');

#ifdef LISP65_XEMU_TEST
    emit_test_terminate();
    asm volatile("jmp $a474");
#endif
    return 0;
}
