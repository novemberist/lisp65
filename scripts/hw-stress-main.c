/* lisp65 -- MEGA65 hardware stress harness.
 * Test-only main: product boot path, embedded stdlib metadata + external blob, then
 * intentionally allocation-heavy REPL-equivalent forms. Leaves a visible PASS/FAIL
 * line; optional DMA profiling counters can be read through JTAG/memsave. */
#include <stdint.h>
#include "obj.h"
#include "reader.h"
#include "printer.h"
#include "eval.h"
#include "vm_embed.h"
#include "interrupt.h"
#include "mem.h"
#ifdef LISP65_SCREEN_DRIVER
#include "screen.h"
#endif

#if defined(LISP65_HW_STRESS_DEEP1) || defined(LISP65_HW_STRESS_DEEP2)
#define LISP65_HW_STRESS_DEEP 1
#endif

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
#ifdef LISP65_HW_STRESS_DEEP1
    volatile int prev_active = lisp_toplevel_active;
    obj got;
#endif

    lisp_error_msg = 0;
    mem_oom = 0;
#ifdef LISP65_HW_STRESS_DEEP1
    if (setjmp(lisp_toplevel)) {
        lisp_toplevel_active = prev_active;
        gc_rootsp = 0;
        return NIL;
    }
    lisp_toplevel_active = 1;
    got = eval(read_expr(&p));
    lisp_toplevel_active = prev_active;
    return got;
#else
    return eval(read_expr(&p));
#endif
}

#ifndef LISP65_HW_STRESS_DEEP
static uint8_t fail_case(const char *name, obj got) {
    visual_status(0);
    emit_str("fail ");
    emit_str(name);
    emit_str(" got ");
    print_obj(got);
    emit('\n');
    return 0;
}
#endif

static uint8_t check_fix(const char *name, const char *expr, int16_t expect) {
    obj got = eval_src(expr);
    if (!lisp_error_msg && !mem_oom && got == MKFIX(expect)) return 1;
    visual_status(0);
    emit_str("fail ");
    emit_str(name);
    emit_str(" got ");
    print_obj(got);
    emit_str(" exp ");
    print_obj(MKFIX(expect));
    emit('\n');
    return 0;
}

#ifndef LISP65_HW_STRESS_DEEP
static uint8_t check_true(const char *name, const char *expr) {
    obj got = eval_src(expr);
    if (!lisp_error_msg && !mem_oom && got != NIL) return 1;
    return fail_case(name, got);
}
#endif

#ifdef LISP65_HW_STRESS_DEEP1
static uint8_t check_recover_fix(const char *name, const char *bad_expr,
                                 const char *good_expr, int16_t expect) {
    (void)eval_src(bad_expr);
    if (!lisp_error_msg) {
        visual_status(0);
        emit_str("fail ");
        emit_str(name);
        emit_str(" no-error\n");
        return 0;
    }
    return check_fix(name, good_expr, expect);
}
#endif

#ifndef LISP65_HW_STRESS_DEEP
static uint8_t check_runtime_health(void) {
    if (gc_badobj == 0) return 1;
    visual_status(0);
    emit_str("fail health ");
    print_obj(MKFIX((int16_t)gc_badobj));
    emit('\n');
    return 0;
}
#endif

#ifdef LISP65_HW_STRESS_DEEP2
static uint8_t check_output_screen_health(void) {
    obj got = eval_src("(if(and(>(car(screen-size))0)(>(cadr(screen-size))0)(screen-bulk-p))42 0)");
    if (!lisp_error_msg && !mem_oom && got == MKFIX(42) && gc_badobj == 0) return 1;
    visual_status(0);
    emit_str("fail dos got ");
    print_obj(got);
    emit_str(" badobj ");
    print_obj(MKFIX((int16_t)gc_badobj));
    emit('\n');
    return 0;
}
#endif

int main(void) {
    uint8_t pass = 0;
#ifdef LISP65_HW_STRESS_DEEP
    const uint8_t total = 5;
#else
    const uint8_t total = 15;
#endif

    visual_status(0);
    eval_init();
    vm_load_embedded_stdlib();
#ifdef LISP65_SCREEN_DRIVER
    scr_init();
#endif

#ifdef LISP65_HW_STRESS_DEEP
#ifdef LISP65_HW_STRESS_DEEP1
    pass += check_fix("dgc",
        "(progn"
        "(lcc-run '(defun dh(n a)(if(< n 1)a(dh(- n 1)(cons(list n(list(+ n 1)))a)))))"
        "(lcc-run '(defun ds(x s)(if(null x)s(ds(cdr x)(+ s(car(car x)))))))"
        "(lcc-run '(defun db(r)(if(< r 1)0(progn(dh 20 nil)(db(- r 1))))))"
        "(let((k(dh 24 nil)))(db 8)(ds k 0)))",
        300);

    pass += check_fix("dvm",
        "(progn"
        "(lcc-run '(defun d0(x)(+ x 1)))"
        "(lcc-run '(defun d1(x)(+ x 2)))"
        "(lcc-run '(defun d2(x)(+ x 3)))"
        "(lcc-run '(defun d3(x)(- x 1)))"
        "(lcc-run '(defun d4(x)(+ x 4)))"
        "(lcc-run '(defun dt(n x)(if(< n 1)x(dt(- n 1)(d4(d3(d2(d1(d0 x)))))))))"
        "(dt 20 0))",
        180);

    pass += check_fix("dcl",
        "(progn"
        "(lcc-run '(defun da(n)(lambda(x)(+ x n))))"
        "(lcc-run '(defun dc(n s)(if(< n 1)s(dc(- n 1)(+ s(funcall(da n)1))))))"
        "(dc 20 0))",
        230);

    pass += check_fix("dmc",
        "(progn"
        "(lcc-run '(defmacro dm(x)(list '+ x 2)))"
        "(lcc-run '(defun dn(n s)(if(< n 1)s(dn(- n 1)(dm s)))))"
        "(dn 21 0))",
        42);

    pass += check_recover_fix("der",
        "(dz 1)",
        "(+ 40 2)",
        42);
#else
    pass += check_fix("dsy",
        "(progn"
        "(setq dsym '(s0 s1 s2 s3 s4 s5 s6 s7 s8 s9 s10 s11 s12 s13 s14 s15))"
        "(if(equal '(a(b)c) '(a(b)c))(length dsym)0))",
        16);

    pass += check_fix("dst",
        "(if(and"
        "(string=(string-upcase(string-append \"ab\" \"cd\"))\"ABCD\")"
        "(=(search \"bc\" \"abcd\")1)"
        "(string-suffix-p \"cd\" \"abcd\"))42 0)",
        42);

    pass += check_fix("dib",
        "(let*((b(ide-set-point(ide-make-buffer 'x '(\"a\"))0 1))"
        "(b(ide-insert-char b 33))"
        "(b(ide-split-line b))"
        "(b(ide-insert-char b 40))"
        "(b(ide-delete-backward-char b)))"
        "(+(ide-line-count b)(string-length(ide-line-at b 0))"
        "(ide-point-line(ide-buffer-point b))(ide-point-column(ide-buffer-point b))))",
        5);

    pass += check_fix("dnu",
        "(if(and(=(/ 84 2)42)(=(mod -3 5)-3)(=(clamp 99 0 42)42)(=(max 1 42 3)42)(=(min 9 8 7)7))42 0)",
        42);

    pass += check_output_screen_health();
#endif
#else
    emit_str("stress\n");

    pass += check_fix("eval", "(eval '(+ 20 22))", 42);
    pass += check_fix("bridge-sub", "(- 99 40 17)", 42);

    pass += check_true("isum", "(lcc-run '(defun hss (n s) (if (< n 1) s (hss (- n 1) (+ s (- n 1))))))");
    pass += check_fix("sum", "(hss 40 0)", 780);

    pass += check_true("imk", "(lcc-run '(defun hsm (n a) (if (< n 1) a (hsm (- n 1) (cons n a)))))");
    pass += check_fix("mklist", "(length (hsm 48 nil))", 48);

    pass += check_true("ichurn", "(lcc-run '(defun hsc (r n s) (if (< r 1) s (hsc (- r 1) n (+ s (length (hsm n nil)))))))");
    pass += check_fix("churn", "(hsc 10 28 0)", 280);

    pass += check_true("iadd", "(lcc-run '(defun hsa (n) (lambda (x) (+ x n))))");
    pass += check_true("iclo", "(lcc-run '(defun hsk (n s) (if (< n 1) s (hsk (- n 1) (+ s (funcall (hsa (- n 1)) 1))))))");
    pass += check_fix("closure-loop", "(hsk 16 0)", 136);

    pass += check_true("imac", "(lcc-run '(defmacro htw (x) (list '+ x x)))");
    pass += check_fix("macro-use", "(htw 21)", 42);

    pass += check_true("str", "(string= (list->string (reverse (string->list \"abcd\"))) \"dcba\")");
    pass += check_runtime_health();
#endif

    if (pass == total) {
        visual_status(1);
        emit_str("stress ");
#ifdef LISP65_HW_STRESS_DEEP
#ifdef LISP65_HW_STRESS_DEEP1
        emit_str("deep1 ");
#else
        emit_str("deep2 ");
#endif
#endif
        emit_str("pass ");
    } else {
        visual_status(0);
        emit_str("stress ");
#ifdef LISP65_HW_STRESS_DEEP
#ifdef LISP65_HW_STRESS_DEEP1
        emit_str("deep1 ");
#else
        emit_str("deep2 ");
#endif
#endif
        emit_str("fail ");
    }
    print_obj(MKFIX(pass));
    emit('/');
    print_obj(MKFIX(total));
    emit('\n');

    for (;;) { }
    return 0;
}
