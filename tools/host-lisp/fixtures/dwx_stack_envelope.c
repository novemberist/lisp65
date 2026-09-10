#include <assert.h>
#include "dwx_stack_envelope.h"

int main(void) {
    dwx_sp_envelope w;
    dwx_sp_init(&w);
    dwx_sp_checkpoint(&w, 100, 0x1000);
    dwx_sp_sample(&w, 102, 0x1009); /* helper RTS, scope remains */
    assert(w.count == 1);
    dwx_sp_sample(&w, 90, 0x2000);
    assert(w.max_post == 10 && w.post_origin_pc == 0x1000);
    dwx_sp_checkpoint(&w, 88, 0x1000);
    assert(w.max_post == 12 && w.count == 2);
    dwx_sp_sample(&w, 80, 0x2001); /* child charged 8, not parent's 20 */
    assert(w.max_post == 12);
    dwx_sp_sample(&w, 94, 0x2002); /* child returned, parent restored */
    assert(w.count == 1);
    dwx_sp_sample(&w, 85, 0x2003);
    assert(w.max_post == 15);

    dwx_sp_row_reset(&w);
    assert(w.count == 1 && w.max_post == 0);
    dwx_sp_sample(&w, 90, 0x2004);
    assert(w.max_post == 10); /* inherited live scope covers new typing row */
    dwx_sp_interrupt_enter(&w, 90);
    dwx_sp_sample(&w, 79, 0xff00);
    dwx_sp_interrupt_enter(&w, 79);
    dwx_sp_sample(&w, 75, 0xff10);
    assert(w.max_irq == 15 && w.max_post == 10);
    dwx_sp_interrupt_exit(&w);
    dwx_sp_sample(&w, 79, 0xff20);
    dwx_sp_interrupt_exit(&w);
    dwx_sp_sample(&w, 90, 0x2004);
    assert(w.max_irq == 15 && w.max_post == 10 && !w.invalid);
    dwx_sp_sample(&w, 104, 0x3000);
    assert(w.count == 0);

    dwx_sp_init(&w);
    dwx_sp_before_push(&w, 0);
    assert(w.wraps == 1);
    dwx_sp_interrupt_exit(&w);
    assert(w.invalid);
    dwx_sp_init(&w);
    dwx_sp_checkpoint(&w, 254, 0x1000);
    assert(w.invalid); /* helper JSR itself crossed the page boundary */

    dwx_sp_init(&w);
    w.caller_gap = 4; /* Body -> shared wrapper -> nine-byte predicate. */
    dwx_sp_checkpoint(&w, 100, 0x1000);
    dwx_sp_sample(&w, 102, 0x1100); /* predicate returned */
    dwx_sp_sample(&w, 104, 0x2000); /* wrapper returned, body still live */
    dwx_sp_sample(&w, 90, 0x2001);
    assert(w.count == 1 && w.max_post == 10);
    dwx_sp_sample(&w, 106, 0x3000);
    assert(w.count == 0);
    dwx_sp_init(&w); /* Old two-byte scope silently misses the body. */
    dwx_sp_checkpoint(&w, 100, 0x1000);
    dwx_sp_sample(&w, 102, 0x1100);
    dwx_sp_sample(&w, 104, 0x2000);
    dwx_sp_sample(&w, 90, 0x2001);
    assert(w.max_post != 10); /* Discriminating old-shape counterexample. */
    return 0;
}
