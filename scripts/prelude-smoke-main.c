/* Test-only main for the embedded Prelude smoke. Lane T owns this harness file. */
#include "obj.h"
#include "reader.h"
#include "printer.h"
#include "eval.h"
#include "prelude_gen.h"

int main(void) {
    eval_init();
    load_source(prelude_src);

    {
        const char *src = "(progn (defvar *x* 1) (defvar *x* 2) (when t *x*))";
        obj r = eval(read_expr(&src));
        emit_str("lisp65 prelude: ");
        print_obj(r);
        emit('\n');
    }

#ifdef LISP65_XEMU_TEST
    emit_test_terminate();
    asm volatile("jmp $a474");
#endif
    return 0;
}
