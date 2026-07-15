/* lisp65 -- M5 Lisp save-new allocator smoke.
 *
 * Loads an allocator from the throwaway D81 into the treewalker, calls the Lisp
 * save-new prototype to create a source file on a throwaway Workbench D81, then
 * reloads that file through the C directory lookup. The shell harness verifies
 * the exact D81 diff and boots the Workbench to call normal (load "<name>").
 */
#include <stdint.h>
#include "obj.h"
#include "reader.h"
#include "printer.h"
#include "eval.h"
#include "io.h"
#include "interrupt.h"
#include "screen.h"

#ifndef SAVE_NEW_PAYLOAD_HEADER
#define SAVE_NEW_PAYLOAD_HEADER "m5-new-payload-form.h"
#endif
#include SAVE_NEW_PAYLOAD_HEADER

#ifndef SAVE_NEW_TARGET_NAME
#define SAVE_NEW_TARGET_NAME "m5src"
#endif

#ifndef SAVE_NEW_ALLOC_NAME
#define SAVE_NEW_ALLOC_NAME "m5alloc"
#endif

#ifndef SAVE_NEW_PAYLOAD_SRC
#define SAVE_NEW_PAYLOAD_SRC m5_payload_src
#endif

#ifndef SAVE_NEW_RUN_EXPR
#define SAVE_NEW_RUN_EXPR "(m5-new-run)"
#endif

#ifndef SAVE_NEW_RUN_EXPECT
#define SAVE_NEW_RUN_EXPECT 797
#endif

#ifndef SAVE_NEW_RUN_NAME
#define SAVE_NEW_RUN_NAME SAVE_NEW_RUN_EXPR
#endif

#ifndef SAVE_NEW_FUNCTION
#define SAVE_NEW_FUNCTION "m65d-save-new-2"
#endif

#ifndef SAVE_NEW_EXPR
#define SAVE_NEW_EXPR "(" SAVE_NEW_FUNCTION " \"" SAVE_NEW_TARGET_NAME "\" (m65d-test-payload))"
#endif

#define COLOR_BLACK 0u
#define COLOR_RED   2u
#define COLOR_GREEN 5u

#ifndef SYMPOOL_EXT_BANK
#define SYMPOOL_EXT_BANK 5u
#endif
#ifndef SYMPOOL_EXT_OFF
#define SYMPOOL_EXT_OFF 0x8000u
#endif

#if defined(LISP65_SYMPOOL_EXT) || defined(LISP65_SYMVAL_EXT) || \
    defined(LISP65_NAMEOFF_EXT) || defined(LISP65_SYMFN_EXT)
__attribute__((used)) unsigned char m5_sym_dma_list[12];

static void m5_sym_dma(uint16_t sa, uint8_t sb, uint16_t da, uint8_t db, uint16_t n) {
    m5_sym_dma_list[0] = 0;
    m5_sym_dma_list[1] = (uint8_t)n;
    m5_sym_dma_list[2] = (uint8_t)(n >> 8);
    m5_sym_dma_list[3] = (uint8_t)sa;
    m5_sym_dma_list[4] = (uint8_t)(sa >> 8);
    m5_sym_dma_list[5] = sb;
    m5_sym_dma_list[6] = (uint8_t)da;
    m5_sym_dma_list[7] = (uint8_t)(da >> 8);
    m5_sym_dma_list[8] = db;
    m5_sym_dma_list[9] = 0;
    m5_sym_dma_list[10] = 0;
    m5_sym_dma_list[11] = 0;
    __asm__ volatile(
        "lda #0\n\t"
        "sta $d702\n\t"
        "lda #mos16hi(m5_sym_dma_list)\n\t"
        "sta $d701\n\t"
        "lda #mos16lo(m5_sym_dma_list)\n\t"
        "sta $d700\n\t"
        ::: "a", "memory");
}
#endif

#ifdef LISP65_SYMPOOL_EXT
void sympool_read(uint16_t off, char *dst, uint16_t len) {
    m5_sym_dma((uint16_t)(SYMPOOL_EXT_OFF + off), SYMPOOL_EXT_BANK, (uint16_t)(uintptr_t)dst, 0, len);
}
void sympool_write(uint16_t off, const char *src, uint16_t len) {
    m5_sym_dma((uint16_t)(uintptr_t)src, 0, (uint16_t)(SYMPOOL_EXT_OFF + off), SYMPOOL_EXT_BANK, len);
}
#endif

#ifdef LISP65_SYMVAL_EXT
#ifndef SYMVAL_EXT_BANK
#define SYMVAL_EXT_BANK 5u
#endif
#ifndef SYMVAL_EXT_OFF
#define SYMVAL_EXT_OFF ((uint16_t)(SYMPOOL_EXT_OFF + NAMEPOOL))
#endif
obj symval_get(uint16_t i) {
    uint16_t v;
    m5_sym_dma((uint16_t)(SYMVAL_EXT_OFF + i * 2u), SYMVAL_EXT_BANK, (uint16_t)(uintptr_t)&v, 0, 2);
    return (obj)v;
}
void symval_set(uint16_t i, obj val) {
    uint16_t v = (uint16_t)val;
    m5_sym_dma((uint16_t)(uintptr_t)&v, 0, (uint16_t)(SYMVAL_EXT_OFF + i * 2u), SYMVAL_EXT_BANK, 2);
}
#endif

#ifdef LISP65_NAMEOFF_EXT
#ifndef NAMEOFF_EXT_BANK
#define NAMEOFF_EXT_BANK 5u
#endif
#ifndef NAMEOFF_EXT_OFF
#define NAMEOFF_EXT_OFF ((uint16_t)(SYMPOOL_EXT_OFF + NAMEPOOL + MAX_SYM * 2u))
#endif
uint16_t nameoff_get(uint16_t i) {
    uint16_t v;
    m5_sym_dma((uint16_t)(NAMEOFF_EXT_OFF + i * 2u), NAMEOFF_EXT_BANK, (uint16_t)(uintptr_t)&v, 0, 2);
    return v;
}
void nameoff_set(uint16_t i, uint16_t off) {
    uint16_t v = off;
    m5_sym_dma((uint16_t)(uintptr_t)&v, 0, (uint16_t)(NAMEOFF_EXT_OFF + i * 2u), NAMEOFF_EXT_BANK, 2);
}
#endif

#ifdef LISP65_SYMFN_EXT
#ifndef SYMFN_EXT_BANK
#define SYMFN_EXT_BANK 5u
#endif
#ifndef SYMFN_EXT_OFF
#define SYMFN_EXT_OFF ((uint16_t)(NAMEOFF_EXT_OFF + MAX_SYM * 2u))
#endif
obj symfn_ext_get(uint16_t i) {
    uint16_t v;
    m5_sym_dma((uint16_t)(SYMFN_EXT_OFF + i * 2u), SYMFN_EXT_BANK, (uint16_t)(uintptr_t)&v, 0, 2);
    return (obj)v;
}
void symfn_ext_set(uint16_t i, obj val) {
    uint16_t v = (uint16_t)val;
    m5_sym_dma((uint16_t)(uintptr_t)&v, 0, (uint16_t)(SYMFN_EXT_OFF + i * 2u), SYMFN_EXT_BANK, 2);
}
#endif

enum {
    CASE_ALLOC_LIB = 0,
    CASE_PAYLOAD_FORM,
    CASE_SAVE_NEW,
    CASE_LOAD_NAMED,
    CASE_RUN_PAYLOAD,
    CASES
};

__attribute__((used)) volatile uint8_t hw_save_new_pass;
__attribute__((used)) volatile uint8_t hw_save_new_total;
__attribute__((used)) volatile uint8_t hw_save_new_results[CASES];
__attribute__((used)) volatile int16_t hw_save_new_got[CASES];
__attribute__((used)) volatile int16_t hw_save_new_want[CASES];

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

static void record(uint8_t idx, uint8_t ok, int16_t got, int16_t want) {
    hw_save_new_results[idx] = ok ? 1 : 0;
    hw_save_new_got[idx] = got;
    hw_save_new_want[idx] = want;
    hw_save_new_total++;
    if (ok) hw_save_new_pass++;
}

static obj eval_src(const char *src) {
    const char *p = src;
    lisp_error_msg = 0;
    return eval(read_expr(&p));
}

static void fail_case(const char *name, int16_t got, int16_t want) {
    visual_status(0);
    emit_str("save new fail ");
    emit_str(name);
    emit_str(" got ");
    print_obj(MKFIX(got));
    emit_str(" want ");
    print_obj(MKFIX(want));
    if (lisp_error_msg) {
        emit_str(" abort ");
        emit_str(lisp_error_msg);
    }
    emit('\n');
}

static uint8_t load_embedded(const char *name, const char *src, uint8_t idx) {
    lisp_error_msg = 0;
    load_source(src);
    if (!lisp_error_msg) {
        record(idx, 1, 1, 1);
        return 1;
    }
    record(idx, 0, 0, 1);
    fail_case(name, 0, 1);
    return 0;
}

static uint8_t check_true(const char *name, const char *expr, uint8_t idx) {
    obj got = eval_src(expr);
    if (!lisp_error_msg && got != NIL) {
        record(idx, 1, 1, 1);
        return 1;
    }
    record(idx, 0, got == NIL ? 0 : 1, 1);
    fail_case(name, got == NIL ? 0 : 1, 1);
    return 0;
}

static uint8_t check_fix(const char *name, const char *expr, int16_t expect, uint8_t idx) {
    obj got = eval_src(expr);
    if (!lisp_error_msg && got == MKFIX(expect)) {
        record(idx, 1, expect, expect);
        return 1;
    }
    record(idx, 0, IS_FIX(got) ? FIXVAL(got) : -32767, expect);
    fail_case(name, IS_FIX(got) ? FIXVAL(got) : -32767, expect);
    return 0;
}

static uint8_t check_load_named(const char *name, const char *disk_name, uint8_t idx) {
    lisp_error_msg = 0;
    if (io_disk_load_named(disk_name) && !lisp_error_msg) {
        record(idx, 1, 1, 1);
        return 1;
    }
    record(idx, 0, 0, 1);
    fail_case(name, 0, 1);
    return 0;
}

int main(void) {
    uint8_t pass;

    eval_init();
    scr_init();
    visual_status(0);
    emit_str("save new hw smoke\n");

    check_load_named("alloc-lib", SAVE_NEW_ALLOC_NAME, CASE_ALLOC_LIB);
    load_embedded("payload-form", SAVE_NEW_PAYLOAD_SRC, CASE_PAYLOAD_FORM);
    check_true("save-new", SAVE_NEW_EXPR, CASE_SAVE_NEW);
    check_load_named("load-named", SAVE_NEW_TARGET_NAME, CASE_LOAD_NAMED);
    check_fix(SAVE_NEW_RUN_NAME, SAVE_NEW_RUN_EXPR, SAVE_NEW_RUN_EXPECT, CASE_RUN_PAYLOAD);

    pass = hw_save_new_pass;
    visual_status(pass == CASES);
    emit_str(pass == CASES ? "save new pass " : "save new fail ");
    print_obj(MKFIX(pass));
    emit('/');
    print_obj(MKFIX(CASES));
    emit('\n');

    for (;;) {}
}
