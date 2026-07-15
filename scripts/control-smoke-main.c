/* Test-only main for the iteration/control stdlib layer. */
#include "obj.h"
#include "reader.h"
#include "printer.h"
#include "eval.h"
#include "prelude_gen.h"
#include "stdlib_control_gen.h"

static obj eval_src(const char *src) {
    const char *p = src;
    return eval(read_expr(&p));
}

static uint8_t check_case(const char *expr, const char *expect) {
    obj got = eval_src(expr);
    obj want = eval_src(expect);
    if (got == want) return 1;

    emit_str("control FAIL: ");
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
    load_source(stdlib_control_src);

    pass += check_case("((lambda (loop) (setq loop (lambda (i) (if (= i 3) i (funcall loop (1+ i))))) (funcall loop 0)) nil)", "3");
    pass += check_case("(do ((i 0 (1+ i))) ((= i 3) i))", "3");
    pass += check_case("(let ((s 0)) (do ((i 0 (1+ i))) ((= i 4) s) (setq s (+ s i))))", "6");
    pass += check_case("(dotimes (i 3 i))", "3");
    pass += check_case("(let ((s 0)) (dotimes (i 4 s) (setq s (+ s i))))", "6");
    pass += check_case("(dolist (x (quote (1 2 3)) 7) nil)", "7");
    pass += check_case("(let ((s 0)) (dolist (x (quote (1 2 3)) s) (setq s (+ s x))))", "6");

    emit_str("lisp65 control: ");
    print_obj(MKFIX(pass));
    emit('\n');

#ifdef LISP65_XEMU_TEST
    emit_test_terminate();
    asm volatile("jmp $a474");
#endif
    return 0;
}
