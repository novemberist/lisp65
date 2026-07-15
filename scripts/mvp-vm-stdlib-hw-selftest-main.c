/* Test-only main for the embedded bytecode stdlib MVP hardware selftest.
 * Lane T owns this harness file. It uses the product boot path, then evaluates
 * fixed REPL-equivalent forms and leaves an obvious PASS/FAIL screen/border. */
#include <stdint.h>
#include "obj.h"
#include "reader.h"
#include "printer.h"
#include "eval.h"
#include "vm_embed.h"

#define COLOR_BLACK 0u
#define COLOR_RED   2u
#define COLOR_GREEN 5u

static void visual_status(uint8_t pass) {
#if defined(__MEGA65__) || defined(__C64__) || defined(__CBM__)
    volatile uint8_t *border = (volatile uint8_t *)0xd020;
    volatile uint8_t *background = (volatile uint8_t *)0xd021;
    *border = pass ? COLOR_GREEN : COLOR_RED;
    *background = COLOR_BLACK;
#else
    (void)pass;
#endif
}

static obj eval_src(const char *src) {
    const char *p = src;
    return eval(read_expr(&p));
}

static uint8_t fail_case(const char *name, const char *expr, obj got) {
    visual_status(0);
    emit_str("lisp65 hw-selftest FAIL ");
    emit_str(name);
    emit_str(": ");
    emit_str(expr);
    emit_str(" => ");
    print_obj(got);
    emit('\n');
    return 0;
}

static uint8_t check_fix(const char *name, const char *expr, int16_t expect) {
    obj got = eval_src(expr);
    if (got == MKFIX(expect)) return 1;
    visual_status(0);
    emit_str("lisp65 hw-selftest FAIL ");
    emit_str(name);
    emit_str(": ");
    emit_str(expr);
    emit_str(" => ");
    print_obj(got);
    emit_str(" expected ");
    print_obj(MKFIX(expect));
    emit('\n');
    return 0;
}

static uint8_t check_true(const char *name, const char *expr) {
    obj got = eval_src(expr);
    if (got != NIL) return 1;
    return fail_case(name, expr, got);
}

int main(void) {
    uint8_t pass = 0;
    const uint8_t total = 11;

    visual_status(0);
    eval_init();
    vm_load_embedded_stdlib();

    pass += check_fix("length", "(length '(1 2 3))", 3);
    pass += check_fix("nth", "(nth 2 (list 7 8 9 10))", 9);
    pass += check_fix("reverse", "(length (reverse '(1 2 3 4)))", 4);
    pass += check_true("equal", "(equal (list 'a (cons 'b 'c) 3) (list 'a (cons 'b 'c) 3))");
    pass += check_fix("mapcar", "(cadr (mapcar (lambda (x) (+ x 1)) '(1 2 3)))", 3);
    pass += check_true("every", "(every (lambda (x) (> x 0)) '(1 2 3))");
    pass += check_true("some", "(some (lambda (x) (> x 2)) '(1 2 3))");
    pass += check_fix("count-if", "(count-if (lambda (x) (> x 1)) '(1 2 3))", 2);
    pass += check_fix("remove-if", "(length (remove-if (lambda (x) (> x 2)) '(1 2 3 4)))", 2);
    pass += check_fix("reduce", "(reduce (function +) (list 1 2 3))", 6);
    pass += check_true("string", "(string= (string-append \"a\" \"b\") \"ab\")");

    if (pass == total) {
        visual_status(1);
        emit_str("lisp65 hw-selftest PASS ");
        print_obj(MKFIX(pass));
        emit('/');
        print_obj(MKFIX(total));
        emit('\n');
    } else {
        visual_status(0);
        emit_str("lisp65 hw-selftest FAIL total ");
        print_obj(MKFIX(pass));
        emit('/');
        print_obj(MKFIX(total));
        emit('\n');
    }

    for (;;) { }
    return 0;
}
