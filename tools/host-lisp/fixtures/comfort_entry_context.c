/* Execute the real native half. Lisp's form decision is a separate witness. */
#include <assert.h>
#define LISP65_VM 1
#define LISP65_TREEWALK_STRIP 1
#define MEGA65_F011_LOAD 1
#define LISP65_COMFORT_TRAMPOLINE 1
#include "repl.c"
#include "c2_product_runtime.h"

jmp_buf lisp_toplevel;
obj gc_rootstack[GC_ROOTS];
uint16_t gc_rootsp;
obj lisp_t = MKFIX(1);
uint8_t vm_status;
static uint8_t vm_buf_bank;
static uint16_t vm_buf_off;
static obj mode20(obj *a, uint8_t n) {
#include "prim20.c"
    assert(0); return NIL; /* This fixture executes only the two new modes. */
}
static unsigned char terminal;
static unsigned normalized;
void lisp_abort_code(lisp65_error_code code) { (void)code; assert(0); }
unsigned char io_source_terminal(void) { return terminal; }
char reader_skip_peek(void) { ++normalized; return 0; }

static void reset(void) {
    repl_input_entry = NIL;
    repl_booting = repl_stream_depth = repl_pending = 0;
    repl_context = repl_base_depth = repl_vm_depth = 0;
    repl_form_root = 0;
    gc_rootsp = 0; normalized = 0; terminal = 1;
    vm_status = VM_OK;
    vm_buf_bank = LISP65_C2_CODE_BANK_TAG; vm_buf_off = 100;
}
static void running_form(void) {
    /* Source fixture of the existing lcc-run argument and transient main.
     * The candidate carrier must independently prove these two VM entries. */
    gc_rootstack[gc_rootsp++] = MKFIX(17);
    repl_vm_depth += 2;
}
static void unchanged_query(obj expected) {
    obj entry = repl_input_entry;
    unsigned root = repl_form_root, sp = gc_rootsp, scans = normalized;
    uint8_t pending = repl_pending, context = repl_context;
    assert(repl_mode20(NIL, 0) == expected);
    assert(entry == repl_input_entry && root == repl_form_root && sp == gc_rootsp);
    assert(pending == repl_pending && context == repl_context && scans == normalized);
}
static void refusal(void) {
    unsigned depth = repl_vm_depth, sp = gc_rootsp;
    assert(repl_mode20(MK_BCODE(101), 1) == NIL);
    /* The caller continues and consumes the value; no abort or handoff. */
    assert(repl_input_entry == NIL && !repl_pending);
    assert(depth == repl_vm_depth && sp == gc_rootsp);
}
int main(void) {
    reset(); repl_prepare(1); running_form();
    unchanged_query(MKFIX(17));
    assert(repl_mode20(MK_BCODE(101), 1) == lisp_t);
    assert(repl_input_entry == MK_BCODE(101) && repl_pending);

    reset(); repl_prepare(0); running_form(); refusal();
    reset(); repl_prepare(1); running_form(); ++repl_vm_depth; refusal();
    reset(); repl_prepare(1); /* argument root not installed */ refusal();
    reset(); repl_prepare(1); running_form();
    assert(repl_mode20(MKFIX(99), 1) == NIL && !repl_pending);

    reset(); repl_booting = 1; repl_stream_begin(); repl_stream_form(MKFIX(17));
    assert(normalized == 1);
    running_form(); unchanged_query(MKFIX(17));
    assert(repl_mode20(MK_BCODE(101), 1) == lisp_t);
    switch (setjmp(lisp_toplevel)) {
    case 0: repl_stream_form_done(); assert(0); break;
    case 2: break;
    default: assert(0);
    }
    reset(); repl_booting = 1; repl_stream_begin(); repl_stream_form(MKFIX(17));
    running_form(); terminal = 0; unchanged_query(NIL); refusal();
    repl_stream_form_done(); repl_stream_end();
    assert(repl_stream_depth == 0);

    reset(); repl_booting = 1; repl_stream_begin(); repl_stream_begin();
    repl_stream_form(MKFIX(17)); running_form(); refusal();
    assert(normalized == 0);

    reset(); repl_input_entry = MK_BCODE(101);
    repl_stream_begin(); repl_stream_form_done(); repl_stream_end();
    assert(repl_input_entry == MK_BCODE(101));

    /* Retain the old executing-owner check through the living Prim mode. */
    {
        obj args[3] = {MK_BCODE(101), MK_BCODE(100), MKFIX(70)};
        reset(); repl_prepare(1); running_form();
        assert(mode20(args, 0) == MKFIX(17) && !repl_pending);
        assert(mode20(args, 3) == lisp_t && repl_pending);
        reset(); repl_prepare(1); running_form(); vm_buf_off = 102;
        assert(mode20(args, 3) == NIL && !repl_pending && vm_status == VM_OK);
        reset(); repl_prepare(1); running_form(); vm_buf_bank = 1;
        assert(mode20(args, 3) == NIL && !repl_pending && vm_status == VM_OK);
    }
    return 0;
}
