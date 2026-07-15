/* Test-only main for the small FORMAT stdlib layer. */
#include "obj.h"
#include "reader.h"
#include "printer.h"
#include "eval.h"
#include "prelude_gen.h"
#include "stdlib_format_gen.h"

static obj eval_src(const char *src) {
    const char *p = src;
    return eval(read_expr(&p));
}

static uint8_t check_case(const char *expr, const char *expect) {
    obj got = eval_src(expr);
    obj want = eval_src(expect);
    if (got == want) return 1;

    emit_str("format FAIL: ");
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
    load_source(stdlib_format_src);

    pass += check_case("(if (function format) 1 0)", "1");
    pass += check_case("(if (function integer->string) 1 0)", "1");
    pass += check_case("(string-length (format nil \"~A\" 42))", "2");
    pass += check_case("(string-ref (format nil \"~A\" 42) 0)", "52");
    pass += check_case("(string-ref (format nil \"~A\" 42) 1)", "50");
    pass += check_case("(string-length (format nil \"x=~A\" -7))", "4");
    pass += check_case("(string-ref (format nil \"x=~A\" -7) 0)", "120");
    pass += check_case("(string-ref (format nil \"x=~A\" -7) 2)", "45");
    pass += check_case("(string-ref (format nil \"x=~A\" -7) 3)", "55");
    pass += check_case("(string-length (format nil \"hi ~A\" \"bob\"))", "6");
    pass += check_case("(string-ref (format nil \"hi ~A\" \"bob\") 3)", "98");
    pass += check_case("(string-ref (format nil \"hi ~A\" \"bob\") 5)", "98");

    emit_str("lisp65 format: ");
    print_obj(MKFIX(pass));
    emit('\n');

#ifdef LISP65_XEMU_TEST
    emit_test_terminate();
    asm volatile("jmp $a474");
#endif
    return 0;
}
