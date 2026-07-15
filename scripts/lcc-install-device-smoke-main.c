/* lisp65 -- Host smoke for the P6c-style lcc-install path with the optional closure gate.
 * Loads lib/lcc.lisp through the Treewalker and exercises the actual lcc-install primitive
 * without LISP65_COMPILE_REPL. This catches VM-closure support gaps hidden by the older
 * equivalence harness, which used vm_native_apply from the compile-repl profile. */
#include <setjmp.h>
#include <stdio.h>
#include <string.h>
#include "eval.h"
#include "interrupt.h"
#include "obj.h"
#include "reader.h"
#include "symbol.h"
#include "vm.h"
#include "lcc_gen.h"

static uint8_t lcc_store[4096];
static uint16_t lcc_off;
static int failed;

void vm_code_load(uint8_t bank, uint16_t off, uint16_t len, uint8_t *dst) {
    (void)bank;
    memcpy(dst, lcc_store + off, len);
}

int lcc_region_alloc(uint16_t len, uint8_t *bank, uint16_t *off) {
    if ((uint32_t)lcc_off + len > sizeof lcc_store) return 0;
    *bank = 0;
    *off = lcc_off;
    lcc_off = (uint16_t)(lcc_off + len);
    return 1;
}

void lcc_region_write(uint8_t bank, uint16_t off, const uint8_t *src, uint16_t len) {
    (void)bank;
    memcpy(lcc_store + off, src, len);
}

static obj run_form(const char *src, const char **err) {
    const char *p = src;
    obj form = read_expr(&p);
    obj r = NIL;
    lisp_error_msg = 0;
    lisp_toplevel_active = 1;
    if (setjmp(lisp_toplevel)) {
        *err = lisp_error_msg ? lisp_error_msg : "error";
        lisp_toplevel_active = 0;
        return NIL;
    }
    r = eval(form);
    lisp_toplevel_active = 0;
    *err = lisp_error_msg;
    return r;
}

static void expect_symbol(const char *src, const char *name) {
    const char *err = 0;
    obj got = run_form(src, &err);
    obj want = intern(name);
    int ok = !err && got == want;
    printf("%-68s => %s\n", src, ok ? "OK" : "FAIL");
    if (!ok) {
        printf("      err=%s got=0x%04x want=%s\n", err ? err : "none", (unsigned)got, name);
        failed++;
    }
}

static void expect_fix(const char *src, int16_t want) {
    const char *err = 0;
    obj got = run_form(src, &err);
    int ok = !err && vm_status == VM_OK && IS_FIX(got) && FIXVAL(got) == want;
    printf("%-68s => %s\n", src, ok ? "OK" : "FAIL");
    if (!ok) {
        printf("      err=%s vm=%s got=%d want=%d\n",
               err ? err : "none", vm_status_message(), IS_FIX(got) ? FIXVAL(got) : -999, want);
        failed++;
    }
}

static int expect_checked_register_dir_full(void) {
    vm_embed_entry e = { "checked-dir-full", 0, 0, 0, 1 };
    obj fill = intern("checked-dir-fill");
    uint16_t i;

#ifndef VM_DIR_MAX
#define VM_DIR_MAX 128
#endif
    vm_dir_reset();
    for (i = 0; i < VM_DIR_MAX; i++) {
        if (vm_dir_add(fill, 0, i, 1) < 0) {
            printf("checked register dir-full guard => FAIL (prefill %u)\n", (unsigned)i);
            return 1;
        }
    }
    lisp_error_msg = 0;
    if (vm_register_embedded(&e, 1)) {
        printf("checked register dir-full guard => FAIL (reported success)\n");
        vm_dir_reset();
        return 1;
    }
    if (lisp_error_msg) {
        printf("checked register dir-full guard => FAIL (%s)\n", lisp_error_msg);
        vm_dir_reset();
        return 1;
    }
    vm_dir_reset();
    puts("checked register dir-full guard => OK");
    return 0;
}

int main(void) {
    eval_init();
    if (expect_checked_register_dir_full()) return 1;
    lcc_off = 0;
    lisp_error_msg = 0;
    lisp_toplevel_active = 1;
    if (setjmp(lisp_toplevel)) {
        printf("load lib/lcc.lisp => FAIL (%s)\n", lisp_error_msg ? lisp_error_msg : "error");
        return 1;
    }
    load_source(lcc_src);
    lisp_toplevel_active = 0;
    if (lisp_error_msg) {
        printf("load lib/lcc.lisp => FAIL (%s)\n", lisp_error_msg);
        return 1;
    }

    puts("== lcc-install closure-gated profile ==");
    expect_symbol("(lcc-run (quote (defun sq (x) (* x x))))", "sq");
    expect_fix("(sq 5)", 25);

    puts("== defun with helper, capture-free ==");
    expect_symbol("(lcc-run (quote (defun mk () (lambda (x) (* x 2)))))", "mk");
    expect_fix("(funcall (mk) 21)", 42);

    puts("== defun with helper, capturing ==");
    expect_symbol("(lcc-run (quote (defun ad (n) (lambda (x) (+ x n)))))", "ad");
    expect_fix("(funcall (ad 10) 5)", 15);

    printf(failed ? "\nFAILED (%d)\n" : "\nALL PASS\n", failed);
    return failed ? 1 : 0;
}
