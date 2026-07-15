/* Host smoke for native-REPL surface forms in the MVP VM-stdlib boot path. */
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include "obj.h"
#include "reader.h"
#include "printer.h"
#include "eval.h"
#include "vm_embed.h"

static uint8_t ext_store[65536];

void vm_code_load(uint8_t bank, uint16_t off, uint16_t len, uint8_t *dst) {
    (void)bank;
    memcpy(dst, ext_store + off, len);
}

void vm_ext_write(const uint8_t *src, uint16_t len, uint8_t bank, uint16_t off) {
    (void)bank;
    memcpy(ext_store + off, src, len);
}

static obj eval_src(const char *src) {
    const char *p = src;
    return eval(read_expr(&p));
}

static int fail_case(const char *name, const char *expr, obj got, const char *expect) {
    fprintf(stderr, "repl-surface-smoke: FAIL %s: %s => ", name, expr);
    print_obj(got);
    fprintf(stderr, " expected %s\n", expect);
    return 1;
}

static int check_fix(const char *name, const char *expr, int16_t expect) {
    obj got = eval_src(expr);
    if (got == MKFIX(expect)) return 0;
    return fail_case(name, expr, got, "fixnum");
}

static int check_nil(const char *name, const char *expr) {
    obj got = eval_src(expr);
    if (got == NIL) return 0;
    return fail_case(name, expr, got, "nil");
}

int main(void) {
    int fail = 0;

    eval_init();
    vm_load_embedded_stdlib();

    fail += check_fix("when-true", "(when t 41 42)", 42);
    fail += check_nil("when-false", "(when nil 41)");
    fail += check_fix("unless-false", "(unless nil 6 7)", 7);
    fail += check_fix("let-star-chain", "(let* ((x 1) (y (1+ x))) y)", 2);
    fail += check_fix("case-list-hit", "(case 'b ((a c) 1) ((b d) 2) (otherwise 3))", 2);
    fail += check_fix("case-default", "(case 'q ((a c) 1) (otherwise 3))", 3);

    if (fail) return 1;
    printf("repl-surface-smoke: PASS cases=6\n");
    return 0;
}
