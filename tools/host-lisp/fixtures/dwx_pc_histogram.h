/* Diagnostic host observer only. No guest read, write, or cycle accounting.
 * Caller supplies the already fetched opcode and translated instruction PC.
 * Overlaid and mapped execution is counted separately, never silently assigned
 * to a fixed resident symbol with the same CPU address. */
#ifndef DWX_PC_HISTOGRAM_H
#define DWX_PC_HISTOGRAM_H
#include <stdint.h>
#include <string.h>
#include <limits.h>
typedef struct {
    uint64_t counts[65536], dispatch[256];
    uint8_t opcode[65536], changed[65536];
    uint64_t nonidentity, hypervisor, instructions;
    unsigned invalid, armed, main_pc, dispatch_pc, min_sp, wraps;
} dwx_pc_histogram;
static void dwx_pc_init(dwx_pc_histogram *h, unsigned main_pc, unsigned dispatch_pc) {
    memset(h, 0, sizeof(*h));
    h->main_pc = main_pc; h->dispatch_pc = dispatch_pc;
    h->min_sp = 255;
    h->invalid = !main_pc || main_pc > 65535 || !dispatch_pc || dispatch_pc > 65535;
}
static void dwx_pc_stack(dwx_pc_histogram *h, unsigned sp, unsigned pushing) {
    if (!h->armed || h->invalid) return;
    if (sp > 255) { h->invalid = 1; return; }
    if (sp < h->min_sp) h->min_sp = sp;
    if (pushing && !sp) h->wraps++;
}
static void dwx_pc_sample(dwx_pc_histogram *h, unsigned pc, uint32_t physical,
                          unsigned opcode, unsigned a, unsigned hypervisor) {
    if (h->invalid) return;
    if (hypervisor) { h->hypervisor++; return; }
    if (physical != pc) { h->nonidentity++; return; }
    if (pc == h->main_pc) h->armed = 1;
    if (!h->armed) return;
    if (pc > 65535 || opcode > 255 || a > 255 ||
        h->counts[pc] == UINT64_MAX || h->instructions == UINT64_MAX ||
        (pc == h->dispatch_pc && h->dispatch[a] == UINT64_MAX)) {
        h->invalid = 1; return;
    }
    if (h->counts[pc] && h->opcode[pc] != opcode) h->changed[pc] = 1;
    h->opcode[pc] = opcode;
    h->counts[pc]++; h->instructions++;
    if (pc == h->dispatch_pc) h->dispatch[a]++;
}
#endif
