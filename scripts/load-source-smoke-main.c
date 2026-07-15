/* Test-only main for loading a second source after the embedded Prelude. */
#include "obj.h"
#include "reader.h"
#include "printer.h"
#include "eval.h"
#include "prelude_gen.h"
#include "load_smoke_gen.h"

int main(void) {
    eval_init();
    load_source(prelude_src);
    load_source(load_smoke_src);

    {
        const char *src = "(loaded-when t (loaded-final))";
        obj r = eval(read_expr(&src));
        emit_str("lisp65 load-source: ");
        print_obj(r);
        emit('\n');
    }

#ifdef LISP65_XEMU_TEST
    emit_test_terminate();
    asm volatile("jmp $a474");
#endif
    return 0;
}
