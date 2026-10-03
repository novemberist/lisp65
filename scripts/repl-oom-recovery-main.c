/* lisp65 -- host proof for the REPL out-of-memory landing (2.5.3, OOM hang).
 *
 * Runs the REAL src/repl.c loop (or, for the "before" proof, the published
 * 2.5.2 repl.c; the driver tools/host-lisp/repl_oom_recovery_v253_20261002.py
 * builds both) in the product's read-line shape:
 *
 *   LISP65_BYTECODE_STDLIB_NATIVE_READ_LINE_ENTRY -> read_line() runs a
 *   bytecode entry on vm_run.  Its first allocating VM op (list->string,
 *   prim 2) reports VM_HEAPOOM when `mem_oom` is set, exactly as the product
 *   entry does (src/vm.c: `if (s == NIL || mem_oom) vm_status = VM_HEAPOOM`).
 *
 * The entry `%rl` takes the next scripted line from the global list `%lines`
 * and removes it only AFTER the string exists, so a failing entry consumes no
 * input (the device symptom: "key not consumed").  Forms are evaluated by
 * repl() through eval(); the out-of-memory itself is raised inside vm_run by
 * a compiled function (OP_CONS -> VM_HEAPOOM -> vm_check_status ->
 * lisp_abort_code -> longjmp to the repl() landing), with `mem_oom` still 1:
 * the abort skips the normal-completion clear at the end of the line loop.
 *
 * Verdicts (exit code): 0 = script completed, 3 = HANG (more than
 * LANDING_LIMIT landings while no scripted line was consumed), 2 = setup
 * failure.  The transcript on stdout is compared by the driver. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "obj.h"
#include "mem.h"
#include "symbol.h"
#include "reader.h"
#include "printer.h"
#include "eval.h"
#include "vm.h"
#include "compile_repl.h"
#include "interrupt.h"
#include "repl.h"

#define LANDING_LIMIT 8

void vm_code_load(uint8_t bank, uint16_t off, uint16_t len, uint8_t *dst) {
    (void)bank;
    memcpy(dst, crepl_store + off, len);
}

/* Numeric error seam: the product renders the code through its error overlay.
 * The host prints the stable code; 40 is LISP65_ERR_VM_OOM ("VM: OUT OF MEMORY"). */
uint8_t lisp65_error_render_code(lisp65_error_code code, obj symbol) {
    (void)symbol;
    if (code == LISP65_ERR_VM_OOM) printf("VM: OUT OF MEMORY");
    else printf("ERROR %u", (unsigned)code);
    return 1;
}

static obj lines_symbol;
static obj last_lines;
static unsigned landings_without_input;
static unsigned landings_total;

/* Linked with -Wl,--wrap=emit_str: repl() announces every landing with
 * emit_str("*** ").  This is the only observation point; nothing is changed. */
void __real_emit_str(const char *s);
void __wrap_emit_str(const char *s) {
    if (strcmp(s, "*** ") == 0) {
        obj now = sym_value(lines_symbol);
        landings_total++;
        if (now == last_lines) landings_without_input++;
        else landings_without_input = 1;
        last_lines = now;
        printf("\n[landing %u mem_oom=%u free=%u]", landings_total,
               (unsigned)mem_oom, (unsigned)mem_free_cells());
        if (landings_without_input > LANDING_LIMIT) {
            printf("\nHANG: %u landings, input not consumed, mem_oom=%u\n",
                   landings_without_input, (unsigned)mem_oom);
            fflush(stdout);
            exit(3);
        }
        if (now == NIL) {   /* the terminating (%done) line was consumed */
            printf("\nDONE landings=%u\n", landings_total);
            fflush(stdout);
            exit(0);
        }
    }
    __real_emit_str(s);
}

static void define(const char *src) {
    const char *p = src;
    obj got = compile_run_top_form(read_expr(&p));
    if (vm_status != VM_OK || got == NIL) {
        fprintf(stderr, "repl-oom-recovery: cannot define %s\n", src);
        exit(2);
    }
}

static obj charlist(const char *text) {
    size_t i = strlen(text);
    obj list = NIL;
    while (i > 0) {
        GC_PUSH(list);
        list = cons(MKFIX((int16_t)(unsigned char)text[--i]), list);
        GC_POPN(1);
    }
    return list;
}

int main(int argc, char **argv) {
    static const char *const script_live[] = {
        "(+ 1 2)",
        /* garbage only: the list is local to the aborted run */
        "(fill-local)",
        "(+ 3 4)",
        /* a GLOBAL list really fills the heap; the quoted pad dies with the abort */
        "(fill-global '(1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24))",
        "(+ 5 6)",
        /* heap is still full: a genuine second and third OOM must still report */
        "(fill-global '(1 2 3 4 5 6 7 8))",
        "(+ 7 8)",
        "(fill-global '(1 2 3 4 5 6 7 8))",
        /* free the list: full recovery */
        "(setq l nil)",
        "(build 40)",
        "(+ 9 10)",
        "(%done)",
    };
    int i;
    obj all = NIL;
    (void)argc; (void)argv;
    eval_init();
    vm_init();
    vm_dir_reset();
    crepl_reset();
    /* Directory index 0 == LISP65_BYTECODE_STDLIB_NATIVE_READ_LINE_ENTRY. */
    define("(defun %rl () (let ((s (list->string (car %lines)))) (setq %lines (cdr %lines)) s))");
    define("(defun fill-local () (let ((a nil)) (while t (setq a (cons 1 a)))))");
    define("(defun fill-global (pad) (while t (setq l (cons 1 l))))");
    define("(defun build (n) (let ((r nil) (c 0)) (dotimes (i n) (setq r (cons i r))) "
           "(while r (setq c (+ c 1)) (setq r (cdr r))) c))");
    if (vm_dir_count() != 4) { fprintf(stderr, "repl-oom-recovery: directory drift\n"); return 2; }
    lines_symbol = intern("%lines");
    set_sym_value(intern("l"), NIL);
    for (i = (int)(sizeof script_live / sizeof script_live[0]); i > 0; i--) {
        obj line;
        GC_PUSH(all);
        line = charlist(script_live[i - 1]);
        GC_PUSH(line);
        all = cons(line, all);
        GC_POPN(2);
        set_sym_value(lines_symbol, all);   /* rooted through the symbol value */
    }
    last_lines = NIL;
    printf("repl-oom-recovery: heap=%u free=%u lines=%u\n", (unsigned)HEAP_CELLS,
           (unsigned)mem_free_cells(), (unsigned)(sizeof script_live / sizeof script_live[0]));
    repl();
    printf("\nrepl returned\n");
    return 2;
}
