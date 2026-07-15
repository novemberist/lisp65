#include <setjmp.h>
#include <stdio.h>
#include "eval.h"
#include "interrupt.h"

static char srcbuf[16384];

int main(int argc, char **argv) {
    const char *path = argc > 1 ? argv[1] : "lib/m65-disk-alloc.lisp";
    FILE *f = fopen(path, "rb");
    size_t n;
    if (!f) {
        printf("m65-disk-alloc-load-check: FAIL open %s\n", path);
        return 1;
    }
    n = fread(srcbuf, 1, sizeof(srcbuf) - 1, f);
    fclose(f);
    if (n >= sizeof(srcbuf) - 1) {
        printf("m65-disk-alloc-load-check: FAIL source too large\n");
        return 1;
    }
    srcbuf[n] = '\0';

    eval_init();
    lisp_error_msg = 0;
    lisp_toplevel_active = 1;
    if (setjmp(lisp_toplevel)) {
        printf("m65-disk-alloc-load-check: FAIL %s\n", lisp_error_msg ? lisp_error_msg : "error");
        return 1;
    }
    load_source(srcbuf);
    lisp_toplevel_active = 0;
    if (lisp_error_msg) {
        printf("m65-disk-alloc-load-check: FAIL %s\n", lisp_error_msg);
        return 1;
    }
    puts("m65-disk-alloc-load-check: PASS");
    return 0;
}
