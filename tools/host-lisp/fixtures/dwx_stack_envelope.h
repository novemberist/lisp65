/* Host-only observer state. No access to guest memory and no CPU writes.
 * Inputs are SP samples BEFORE instructions and interrupt entry/exit events.
 * A checkpoint is the entry to the nine-byte helper: SP includes its JSR.
 * The checked body's level is SP+caller_gap: two for a direct call, or the
 * ELF-proven call depth through the shared wrapper. Returning from the
 * wrapper must not close the interval. A deeper checkpoint cuts it; unwinding
 * restores the enclosing interval. IRQ/NMI consumption is measured separately.
 */
#ifndef DWX_STACK_ENVELOPE_H
#define DWX_STACK_ENVELOPE_H
#include <string.h>
typedef struct {
    unsigned sp, caller_level, pc;
} dwx_sp_scope;
typedef struct {
    dwx_sp_scope scopes[256];
    unsigned count, irq_depth, irq_origin;
    unsigned max_post, max_irq, post_pc, post_origin_pc;
    unsigned minimum_sp, checkpoints, wraps, invalid;
    unsigned caller_gap;
} dwx_sp_envelope;

static void dwx_sp_init(dwx_sp_envelope *w) {
    memset(w, 0, sizeof(*w));
    w->minimum_sp = 255;
    w->caller_gap = 2; /* Direct-call synthetic control; real runner binds it. */
}

static void dwx_sp_row_reset(dwx_sp_envelope *w) {
    /* Scopes and interrupt nesting belong to CPU execution, not to a row.
     * In particular a typing row can begin inside an already live VM call. */
    w->max_post = w->max_irq = w->post_pc = w->post_origin_pc = 0;
    w->minimum_sp = 255;
    w->checkpoints = w->wraps = w->invalid = 0;
}

static void dwx_sp_sample(dwx_sp_envelope *w, unsigned sp, unsigned pc) {
    if (sp > 255) { w->invalid = 1; return; }
    if (sp < w->minimum_sp) w->minimum_sp = sp;
    if (w->irq_depth) {
        if (sp <= w->irq_origin && w->irq_origin - sp > w->max_irq)
            w->max_irq = w->irq_origin - sp;
        return;
    }
    while (w->count && sp > w->scopes[w->count - 1].caller_level) --w->count;
    if (w->count) {
        dwx_sp_scope *s = &w->scopes[w->count - 1];
        if (sp <= s->sp && s->sp - sp > w->max_post) {
            w->max_post = s->sp - sp;
            w->post_pc = pc;
            w->post_origin_pc = s->pc;
        }
    }
}

static void dwx_sp_checkpoint(dwx_sp_envelope *w, unsigned sp, unsigned pc) {
    dwx_sp_sample(w, sp, pc); /* charge the approach to the preceding scope */
    if (w->irq_depth || w->caller_gap < 2 || w->caller_gap > 255
        || sp > 255-w->caller_gap || w->count == 256) { w->invalid = 1; return; }
    ++w->checkpoints;
    /* Repeated checks at the same caller level replace rather than retain
     * a completed earlier invocation with the same stack position. */
    while (w->count && sp + w->caller_gap >= w->scopes[w->count - 1].caller_level) --w->count;
    w->scopes[w->count++] = (dwx_sp_scope){sp, sp + w->caller_gap, pc};
}

static void dwx_sp_interrupt_enter(dwx_sp_envelope *w, unsigned sp) {
    if (!w->irq_depth) w->irq_origin = sp;
    ++w->irq_depth;
    if (w->irq_depth > 2) w->invalid = 1; /* bound context: one IRQ plus one NMI */
}

static void dwx_sp_interrupt_exit(dwx_sp_envelope *w) {
    if (!w->irq_depth) w->invalid = 1;
    else --w->irq_depth;
}

static void dwx_sp_before_push(dwx_sp_envelope *w, unsigned sp) {
    if (!sp) ++w->wraps;
}
#endif
