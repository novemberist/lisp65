#include "dwx_pc_histogram.h"
#include <assert.h>
static dwx_pc_histogram h;
int main(void) {
    dwx_pc_init(&h, 0x1000, 0x2000);
    dwx_pc_sample(&h, 0x2000, 0x2000, 0x48, 7, 0);
    assert(h.instructions == 0);
    dwx_pc_sample(&h, 0x1000, 0x1000, 0x60, 0, 1);
    assert(!h.armed && h.hypervisor == 1);
    dwx_pc_sample(&h, 0x1000, 0x21000, 0x60, 0, 0);
    assert(!h.armed && h.nonidentity == 1);
    dwx_pc_sample(&h, 0x1000, 0x1000, 0x60, 0, 0);
    dwx_pc_sample(&h, 0x2000, 0x2000, 0x48, 7, 0);
    assert(h.armed && h.instructions == 2 && h.dispatch[7] == 1);
    assert(h.counts[0x1000] == 1 && h.counts[0x2000] == 1);
    assert(h.opcode[0x1000] == 0x60 && h.opcode[0x2000] == 0x48);
    for (unsigned sp=0; sp<256; sp++) dwx_pc_stack(&h, sp, 1);
    assert(h.min_sp == 0 && h.wraps == 1);
    dwx_pc_sample(&h, 0x2000, 0x2000, 0x60, 8, 0);
    assert(h.changed[0x2000] && h.dispatch[8] == 1);
    h.counts[0x2000] = UINT64_MAX;
    dwx_pc_sample(&h, 0x2000, 0x2000, 0x60, 0, 0);
    assert(h.invalid);
    dwx_pc_init(&h, 0, 0x2000); assert(h.invalid);
    dwx_pc_init(&h, 0x1000, 65536); assert(h.invalid);
    return 0;
}
