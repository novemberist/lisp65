/* lisp65 single-suite hardware self-test. This test-only main uses the product boot path with
 * an external blob at 0x050000, then runs the fixed xemu proof forms: bridge reduction,
 * lcc-first self-hosting, recursion, and both capturing and non-capturing closure factories.
 * The verdict is a green/red border plus a text line. scripts/hw-smoke-einsuite.sh builds and
 * runs it without modifying the Makefile. */
#include <stdint.h>
#include "obj.h"
#include "reader.h"
#include "printer.h"
#include "eval.h"
#include "vm_embed.h"
#include "interrupt.h"   /* Expose the abort reason through lisp_error_msg; no setjmp here. */
#if defined(LISP65_HW_FASL_ROUNDTRIP) || defined(LISP65_HW_B4_WORKFLOW)
#include "io.h"          /* io_fasl_find + io_disk_load_lib: C-side library/FASL load */
#endif
#ifdef LISP65_SCREEN_DRIVER
#include "screen.h"
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
    lisp_error_msg = 0;   /* reset so fail_case reports this form's abort reason */
    return eval(read_expr(&p));
}

static uint8_t fail_case(const char *name, const char *expr, obj got) {
    visual_status(0);
    emit_str("einsuite fail ");
    emit_str(name);
    emit_str(": ");
    emit_str(expr);
    emit_str(" => ");
    print_obj(got);
    if (lisp_error_msg) { emit_str(" [abort: "); emit_str(lisp_error_msg); emit(']'); }
    emit('\n');
    return 0;
}

static uint8_t check_fix(const char *name, const char *expr, int16_t expect) {
    obj got = eval_src(expr);
    if (got == MKFIX(expect)) return 1;
    return fail_case(name, expr, got);
}

static uint8_t check_true(const char *name, const char *expr) {
    obj got = eval_src(expr);
    if (got != NIL) return 1;
    return fail_case(name, expr, got);
}

int main(void) {
    uint8_t pass = 0;
    uint8_t total = 10;   /* + gegatete Strip-Checks unten */

    visual_status(0);
    eval_init();
    vm_load_embedded_stdlib();
#ifdef LISP65_SCREEN_DRIVER
    scr_init();   /* like repl: establish driver geometry before output */
#endif
    emit_str("lisp65 einsuite hw-selftest ...\n");   /* Boot-Banner VOR den (langsamen) Checks */

#ifdef LISP65_HW_B4_WORKFLOW
    /* B4 workflow proof: load IDE + PLACE on demand, save source into a slot, compile it to
     * FASL, reload, and execute. Interactive editing remains a manual check. */
    total = 10;
    pass += check_fix("add", "(+ 1 2)", 3);
    pass += check_fix("loop", "(dotimes (i 30 i) nil)", 30);
    {
        unsigned char t9, s9x;
        if (io_fasl_find("ide", &t9, &s9x) && io_disk_load_lib(t9, s9x)) pass++;
        else { visual_status(0); emit_str("einsuite fail ide-lib-load\n"); }
        if (io_fasl_find("place", &t9, &s9x) && io_disk_load_lib(t9, s9x)) pass++;
        else { visual_status(0); emit_str("einsuite fail place-lib-load\n"); }
    }
    pass += check_true("ide-fn", "(eq (function-kind (quote ide-make-buffer)) (quote bytecode))");
    pass += check_true("setf-macro", "(eq (function-kind (quote setf)) (quote macro))");
    pass += check_fix("incf", "(progn (setq pz 5) (incf pz 37) pz)", 42);
    pass += check_true("edit-save", "(save \"fsrc2\" \"(defun q7 (x) (* x 7))\")");
    pass += check_true("compile-file", "(compile-file \"fsrc2\" \"fasl9\")");
    {
        unsigned char t9, s9x;
        if (io_fasl_find("fasl9", &t9, &s9x) && io_disk_load_lib(t9, s9x)) {
            pass += check_fix("q7", "(q7 6)", 42);
        } else { visual_status(0); emit_str("einsuite fail fasl-load\n"); }
    }
#elif defined(LISP65_HW_FASL_ROUNDTRIP)
    /* B3 standalone minimum: compile disk source FSRC to FASL9, load it through the C-side
     * find/io_disk_load_lib path, then run its bytecode functions including a closure factory. */
    total = 10;
    pass += check_fix("add", "(+ 1 2)", 3);
    pass += check_fix("vsub", "(- 9 2 3)", 4);
    pass += check_true("defun", "(defun sq (x) (* x x))");
    pass += check_fix("sq", "(sq 5)", 25);
    pass += check_true("closure", "(defun ad (n) (lambda (x) (+ x n)))");
    pass += check_fix("ad", "(funcall (ad 10) 5)", 15);
    {   /* Diagnostic stage 1: isolate the emitter without disk; verify the blob-compiled
         * device lcc-fasl? Expect a fixnum length near 90 and a non-space window prefix. */
        obj r = eval_src("(fasl-emit-scratch (quote ((defun zz (x) (* x 5)))))");
        uint8_t k;
        emit_str("  emit => "); print_obj(r);
        if (lisp_error_msg) { emit_str(" [abort: "); emit_str(lisp_error_msg); emit(']'); }
        emit_str(" win ");
        for (k = 0; k < 6; k++) { print_obj(MKFIX((int16_t)ext_disk_get((uint16_t)(256u + 8192u + k)))); emit(' '); }
        emit('\n');
    }
    pass += check_true("compile-file", "(compile-file \"fsrc\" \"fasl9\")");
    {
        unsigned char ft, fs2, i;
        (void)i;
        if (!io_fasl_find("fasl9", &ft, &fs2)) {
            visual_status(0); emit_str("einsuite fail fasl-load: find\n");
        } else if (io_disk_load_lib(ft, fs2)) pass++;
        else { visual_status(0); emit_str("einsuite fail fasl-load: reg\n"); }
    }
    pass += check_fix("fasl-s9", "(s9 6)", 54);
    pass += check_fix("fasl-mk9", "(funcall (mk9 40) 2)", 42);
#else
    /* Bridge reduction: base names come from bytecode, not C primitives. */
    pass += check_fix("bridge-add", "(+ 1 2)", 3);
    pass += check_fix("bridge-sub", "(- 9 2 3)", 4);
    /* lcc-first: the Lisp compiler compiles user code on the device. */
    pass += check_true("lcc-sq", "(lcc-run '(defun sq (x) (* x x)))");
    pass += check_fix("sq", "(sq 5)", 25);
    pass += check_true("lcc-dn", "(lcc-run '(defun dn (n) (if (< n 1) 7 (dn (- n 1)))))");
    pass += check_fix("dn", "(dn 9)", 7);
    /* Mandatory closure gate: factories installed through lcc-install. */
    pass += check_true("lcc-mk", "(lcc-run '(defun mk () (lambda (x) (* x 2))))");
    pass += check_fix("mk", "(funcall (mk) 21)", 42);
    pass += check_true("lcc-ad", "(lcc-run '(defun ad (n) (lambda (x) (+ x n))))");
    pass += check_fix("ad", "(funcall (ad 10) 5)", 15);
#ifdef LISP65_TREEWALK_STRIP
    /* M3 convergence: defmacro without eval_env and eval from compiled code while vm_run runs. */
    total += 3;
    pass += check_true("defmacro", "(lcc-run '(defmacro twice (x) (list '+ x x)))");
    pass += check_fix("twice", "(twice 21)", 42);
    pass += check_fix("eval", "(eval '(+ 20 3))", 23);
#endif
#ifdef LISP65_HW_DISK_ROUNDTRIP
    /* M4: load/save round trip on ROUNDTRP.D81. Load TESTLIB, save source into preallocated S6,
     * reload it, and call the resulting function. */
    total += 4;
    pass += check_true("load-lib", "(load \"testlib\")");
    pass += check_true("save", "(save \"s6\" \"(defun s6 (x) (* x 6))\")");
    pass += check_true("load-s6", "(load \"s6\")");
    pass += check_fix("s6", "(s6 7)", 42);
#endif
#endif /* !LISP65_HW_FASL_ROUNDTRIP */

    if (pass == total) {
        visual_status(1);
        emit_str("einsuite hw-selftest pass ");   /* klein: Grossbuchstaben rendert der Treiber als Blank */
    } else {
        visual_status(0);
        emit_str("einsuite hw-selftest fail total ");
    }
    print_obj(MKFIX(pass));
    emit('/');
    print_obj(MKFIX(total));
    emit('\n');

    for (;;) { }
    return 0;
}
