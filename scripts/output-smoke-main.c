/* Host smoke for Lisp-visible output functions. */
#include "obj.h"
#include "reader.h"
#include "eval.h"

static void eval_src(const char *src) {
    const char *p = src;
    (void)eval(read_expr(&p));
}

int main(void) {
    eval_init();

    eval_src("(princ \"hi\")");
    eval_src("(terpri)");
    eval_src("(prin1 \"x\")");
    eval_src("(print 'abc)");
    eval_src("(prin1 \"say \\\"hi\\\"\\\\\")");
    eval_src("(terpri)");
    return 0;
}
