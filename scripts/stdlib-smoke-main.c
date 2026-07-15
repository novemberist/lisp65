/* Test-only main for embedded Stdlib layers after the bootstrap Prelude. */
#include "obj.h"
#include "reader.h"
#include "printer.h"
#include "eval.h"
#include "prelude_gen.h"
#include "stdlib_sequences_gen.h"
#include "stdlib_math_gen.h"
#include "stdlib_plists_gen.h"

static obj eval_src(const char *src) {
    const char *p = src;
    return eval(read_expr(&p));
}

static uint8_t check_case(const char *expr, const char *expect) {
    obj got = eval_src(expr);
    obj want = eval_src(expect);
    if (got == want) return 1;

    emit_str("stdlib FAIL: ");
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
    load_source(stdlib_sequences_src);
    load_source(stdlib_math_src);
    load_source(stdlib_plists_src);

    pass += check_case("(if (function reduce) 1 0)", "1");
    pass += check_case("(if (function %reduce-from) 1 0)", "1");
    pass += check_case("(if (function list*) 1 0)", "1");
    pass += check_case("(if (function every) 1 0)", "1");
    pass += check_case("(if (function some) 1 0)", "1");
    pass += check_case("(if (function max) 1 0)", "1");
    pass += check_case("(if (function min) 1 0)", "1");
    pass += check_case("(if (function getf) 1 0)", "1");
    pass += check_case("(if (function remf) 1 0)", "1");
    pass += check_case("(length (append (quote (1 2)) (quote (3))))", "3");
    pass += check_case("(cadr (mapcar (function 1+) (quote (1 2 3))))", "3");
    pass += check_case("(cadr (assoc (quote b) (quote ((a 1) (b 2)))))", "2");
    pass += check_case("(reduce (function +) (list 1 2 3))", "6");
    pass += check_case("(every (lambda (x) (> x 0)) (list 1 2 3))", "t");
    pass += check_case("(some (lambda (x) (> x 2)) (list 1 2 3))", "t");
    pass += check_case("(length (list* 1 2 (list 3 4)))", "4");
    pass += check_case("(max 1 5 3)", "5");
    pass += check_case("(min 1 5 3)", "1");
    pass += check_case("(getf (quote (:a 1 :b 2)) (quote :b))", "2");
    pass += check_case("(getf (quote (:a 1 :b 2)) (quote :c) 99)", "99");
    pass += check_case("(getf (remf (quote (:a 1 :b 2)) (quote :a)) (quote :a) 99)", "99");
    pass += check_case("(getf (remf (quote (:a 1 :b 2)) (quote :a)) (quote :b))", "2");
    pass += check_case("(length (remf (quote (a 1 b 2 c 3)) (quote b)))", "4");

    emit_str("lisp65 stdlib: ");
    print_obj(MKFIX(pass));
    emit('\n');

#ifdef LISP65_XEMU_TEST
    emit_test_terminate();
    asm volatile("jmp $a474");
#endif
    return 0;
}
