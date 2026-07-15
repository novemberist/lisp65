/* Test-only main for the string stdlib layer. */
#include "obj.h"
#include "reader.h"
#include "printer.h"
#include "eval.h"
#include "prelude_gen.h"
#include "stdlib_strings_gen.h"

static obj eval_src(const char *src) {
    const char *p = src;
    return eval(read_expr(&p));
}

static uint8_t check_case(const char *expr, const char *expect) {
    obj got = eval_src(expr);
    obj want = eval_src(expect);
    if (got == want) return 1;

    emit_str("string FAIL: ");
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
    load_source(stdlib_strings_src);

    pass += check_case("(if (stringp \"abc\") 1 0)", "1");
    pass += check_case("(if (stringp 65) 0 1)", "1");
    pass += check_case("(cadr (string->list \"Az\"))", "122");
    pass += check_case("(string-length (list->string (quote (65 122))))", "2");
    pass += check_case("(string-ref \"abc\" 1)", "98");
    pass += check_case("(if (function string=) 1 0)", "1");
    pass += check_case("(if (function string<) 1 0)", "1");
    pass += check_case("(if (function char) 1 0)", "1");
    pass += check_case("(if (string= \"ab\" (string-append \"a\" \"b\")) 1 0)", "1");
    pass += check_case("(if (string< \"abc\" \"abd\") 1 0)", "1");
    pass += check_case("(if (string< \"ab\" \"abc\") 1 0)", "1");
    pass += check_case("(if (string< \"abd\" \"abc\") 0 1)", "1");
    pass += check_case("(char \"Az\" 1)", "122");
    pass += check_case("(if (string= (substring \"abcdef\" 2 5) \"cde\") 1 0)", "1");
    pass += check_case("(if (string= (string-upcase \"Az\") \"AZ\") 1 0)", "1");
    pass += check_case("(if (string= (string-downcase \"Az\") \"az\") 1 0)", "1");
    pass += check_case("(if (string= (char->string 65) \"A\") 1 0)", "1");

    emit_str("lisp65 string: ");
    print_obj(MKFIX(pass));
    emit('\n');

#ifdef LISP65_XEMU_TEST
    emit_test_terminate();
    asm volatile("jmp $a474");
#endif
    return 0;
}
