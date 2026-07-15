/* lisp65 B1 host gate for the FASL emitter.
 * Load lib/lcc.lisp and lib/lcc-fasl.lisp into treewalk, run (fasl-emit-list CORPUS), emit the
 * container to a file, and validate it independently against the pinned L65M v1 format.
 * No lcc-install region is required; the emitter uses only pure-Lisp lcc-compile-obj. */
#include <setjmp.h>
#include <stdio.h>
#include <stdlib.h>
#include "eval.h"
#include "interrupt.h"
#include "obj.h"
#include "reader.h"
#include "symbol.h"
#include "vm.h"

/* Host seam: vm.c loads code through vm_code_load, but the emitter installs nothing. An empty
 * stub is sufficient and cannot be reached because there is no directory code. */
void vm_code_load(uint8_t bank, uint16_t off, uint16_t len, uint8_t *dst) {
    (void)bank; (void)off; (void)len; (void)dst;
}

/* A 96 KiB preload deliberately crosses the historical silent 64 KiB truncation boundary. */
static char srcbuf[98304];

static int load_file(const char *path) {
    FILE *f = fopen(path, "rb");
    size_t n;
    if (!f) { printf("FAIL: kann %s nicht oeffnen\n", path); return 0; }
    n = fread(srcbuf, 1, sizeof srcbuf - 1, f);
    fclose(f);
    if (n >= sizeof srcbuf - 1) { printf("FAIL: %s sprengt den Preload-Puffer\n", path); return 0; }
    srcbuf[n] = '\0';
    lisp_error_msg = 0;
    lisp_toplevel_active = 1;
    if (setjmp(lisp_toplevel)) {
        printf("FAIL: load %s: %s\n", path, lisp_error_msg ? lisp_error_msg : "error");
        return 0;
    }
    load_source(srcbuf);
    lisp_toplevel_active = 0;
    if (lisp_error_msg) { printf("FAIL: load %s: %s\n", path, lisp_error_msg); return 0; }
    return 1;
}

/* v1-Korpus: 0-Lit, FIX-Lit, SYMBOL-Lit (generischer Call), Closure-Helfer (Marker->Name). */
static const char *driver =
    "(fasl-emit-scratch (quote ("
    "(defun sq (x) (* x x))"
    "(defun big () (+ 300 1))"
    "(defun callf (x) (helper-target x))"
    "(defun mk2 (n) (lambda (x) (+ x n)))"
    "(defmacro tw2 (x) (list (quote +) x x))"
    ")))";

int main(int argc, char **argv) {
    const char *out = argc > 1 ? argv[1] : "build/equivalence/fasl-test.bin";
    const char *p = driver;
    obj r;
    FILE *f;
    unsigned n = 0;
    eval_init();
    if (!load_file("lib/lcc.lisp")) return 1;
    if (!load_file("lib/lcc-fasl.lisp")) return 1;
    lisp_error_msg = 0;
    lisp_toplevel_active = 1;
    if (setjmp(lisp_toplevel)) {
        printf("FAIL: fasl-emit-list: %s\n", lisp_error_msg ? lisp_error_msg : "error");
        return 1;
    }
    r = eval(read_expr(&p));
    lisp_toplevel_active = 0;
    if (lisp_error_msg) { printf("FAIL: fasl-emit-list: %s\n", lisp_error_msg); return 1; }
    if (!IS_FIX(r) || FIXVAL(r) <= 42) {   /* prefix and header alone occupy 42 B */
        printf("FAIL: fasl-emit-scratch lieferte keine plausible Laenge\n");
        return 1;
    }
    n = (unsigned)FIXVAL(r);
    f = fopen(out, "wb");
    if (!f) { printf("FAIL: kann %s nicht schreiben\n", out); return 1; }
    {   /* B2 streaming: the emitter wrote directly into the simulated file window;
         * Output begins at file-window offset 16384; see lib/lcc-fasl.lisp. */
        unsigned i;
        for (i = 0; i < n; i++) fputc(ext_disk_get((uint16_t)(256u + 8192u + i)), f);
    }
    fclose(f);
    printf("fasl-emit-check: %u Bytes -> %s\n", n, out);
    return 0;
}
