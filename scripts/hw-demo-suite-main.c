/* lisp65 -- hardware runner for the readable demo suite.
 *
 * The program boots the Dev-Core/FASL runtime, compiles each demo source from
 * the mounted D81 into its preallocated FASL slot, registers the resulting
 * bytecode library, then calls the demo's public run function.  A passing demo
 * returns 42.  The final line is read back through JTAG by scripts/hw-demo-suite.sh.
 */
#include <stdint.h>
#include "obj.h"
#include "reader.h"
#include "printer.h"
#include "eval.h"
#include "vm_embed.h"
#include "interrupt.h"
#include "io.h"
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
    lisp_error_msg = 0;
    return eval(read_expr(&p));
}

static uint8_t fail_case(const char *name, const char *expr, obj got) {
    visual_status(0);
    emit_str("demo fail ");
    emit_str(name);
    emit_str(": ");
    emit_str(expr);
    emit_str(" => ");
    print_obj(got);
    if (lisp_error_msg) {
        emit_str(" [abort: ");
        emit_str(lisp_error_msg);
        emit(']');
    }
    emit('\n');
    return 0;
}

static uint8_t check_true(const char *name, const char *expr) {
    obj got = eval_src(expr);
    if (got != NIL) return 1;
    return fail_case(name, expr, got);
}

static uint8_t check_fix(const char *name, const char *expr, int16_t expect) {
    obj got = eval_src(expr);
    if (got == MKFIX(expect)) return 1;
    return fail_case(name, expr, got);
}

static uint8_t load_fasl(const char *name) {
    unsigned char track, sector;
    if (io_fasl_find(name, &track, &sector) && io_disk_load_lib(track, sector)) {
        return 1;
    }
    visual_status(0);
    emit_str("demo fail load ");
    emit_str(name);
    emit('\n');
    return 0;
}

static uint8_t check_load(const char *name) {
    return load_fasl(name);
}

static uint8_t run_demo(const char *label,
                        const char *compile_expr,
                        const char *fasl_name,
                        const char *run_expr) {
    uint8_t pass = 0;
    pass += check_true(label, compile_expr);
    pass += check_load(fasl_name);
    pass += check_fix(label, run_expr, 42);
    return pass;
}

#if !defined(LISP65_DEMO_SHARD_CORE) && !defined(LISP65_DEMO_SHARD_SCREEN) && !defined(LISP65_DEMO_SHARD_ADVNUM) && !defined(LISP65_DEMO_SHARD_IDE)
#define LISP65_DEMO_SHARD_CORE
#define LISP65_DEMO_SHARD_SCREEN
#define LISP65_DEMO_SHARD_ADVNUM
#define LISP65_DEMO_SHARD_IDE
#define LISP65_DEMO_SHARD_NAME "suite"
#endif
#ifdef LISP65_DEMO_SHARD_CORE
#ifndef LISP65_DEMO_SHARD_NAME
#define LISP65_DEMO_SHARD_NAME "core"
#endif
#endif
#ifdef LISP65_DEMO_SHARD_SCREEN
#ifndef LISP65_DEMO_SHARD_NAME
#define LISP65_DEMO_SHARD_NAME "screen"
#endif
#endif
#ifdef LISP65_DEMO_SHARD_ADVNUM
#ifndef LISP65_DEMO_SHARD_NAME
#define LISP65_DEMO_SHARD_NAME "advnum"
#endif
#endif
#ifdef LISP65_DEMO_SHARD_IDE
#ifndef LISP65_DEMO_SHARD_NAME
#define LISP65_DEMO_SHARD_NAME "ide"
#endif
#endif

int main(void) {
    uint8_t pass = 0;
    uint8_t total = 0;

    visual_status(0);
    eval_init();
    vm_load_embedded_stdlib();
#ifdef LISP65_SCREEN_DRIVER
    scr_init();
#endif

    emit_str("demo ");
    emit_str(LISP65_DEMO_SHARD_NAME);
    emit_str(" hw run ...\n");

#ifdef LISP65_DEMO_SHARD_CORE
    total = (uint8_t)(total + 9);
    pass += run_demo("dsimp",
                     "(compile-file \"dsimp\" \"fsimp\")",
                     "fsimp",
                     "(demo-simplify-run)");
    pass += run_demo("dstr",
                     "(compile-file \"dstr\" \"fstr\")",
                     "fstr",
                     "(demo-strings-run)");
    pass += run_demo("dlam",
                     "(compile-file \"dlam\" \"flam\")",
                     "flam",
                     "(demo-lambda-run)");
#endif

#ifdef LISP65_DEMO_SHARD_SCREEN
    total = (uint8_t)(total + 3);
    pass += run_demo("dscr",
                     "(compile-file \"dscr\" \"fscr\")",
                     "fscr",
                     "(demo-screen-run)");
#endif

#ifdef LISP65_DEMO_SHARD_ADVNUM
    total = (uint8_t)(total + 6);
    pass += run_demo("dadv",
                     "(compile-file \"dadv\" \"fadv\")",
                     "fadv",
                     "(demo-adv-run)");
    pass += run_demo("dnum",
                     "(compile-file \"dnum\" \"fnum\")",
                     "fnum",
                     "(demo-numbers-run)");
#endif

#ifdef LISP65_DEMO_SHARD_IDE
    total = (uint8_t)(total + 4);
    pass += check_load("ide");
    pass += run_demo("dide",
                     "(compile-file \"dide\" \"fide\")",
                     "fide",
                     "(demo-ide-run)");
#endif

    if (pass == total) {
        visual_status(1);
        emit_str("demo ");
        emit_str(LISP65_DEMO_SHARD_NAME);
        emit_str(" pass ");
    } else {
        visual_status(0);
        emit_str("demo ");
        emit_str(LISP65_DEMO_SHARD_NAME);
        emit_str(" fail ");
    }
    print_obj(MKFIX(pass));
    emit('/');
    print_obj(MKFIX(total));
    emit('\n');

    for (;;) { }
    return 0;
}
