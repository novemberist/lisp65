/* lisp65 — host reproduction of the repeated-RETURN crash (Lane K, 2026-07-06).
 * Device scenario: an (ide) session followed by repeated RETURN once caused a type error and
 * (hardware JTAG: bank=78). This uses the same C core (eval/vm/mem/GC) and subset blob in a
 * Host build with device-like budgets; -DGC_STRESS exposes every GC-lifetime
 * hole deterministically. Pattern: scripts/repl-surface-smoke-main.c. */
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include "obj.h"
#include "reader.h"
#include "printer.h"
#include "eval.h"
#include "vm.h"
#include "vm_embed.h"
#include "mem.h"
obj mem_freelist_head(void);   /* diagnostic seam; mem.c static state needs a separate counter */

/* Host seam matching repl-surface-smoke: model the EXT code region as flat memory. */
static uint8_t ext_store[65536];
void vm_code_load(uint8_t bank, uint16_t off, uint16_t len, uint8_t *dst) {
    (void)bank;
    memcpy(dst, ext_store + off, len);
}
void vm_ext_write(const uint8_t *src, uint16_t len, uint8_t bank, uint16_t off) {
    (void)bank;
    memcpy(ext_store + off, src, len);
}

/* lcc region for transient REPL mains in the stripped profile: above the
 * blobs in the same ext_store; vm_code_load ignores bank, yielding one address space. */
static uint16_t lcc_off = 0xA000;
int lcc_region_alloc(uint16_t len, uint8_t *bank, uint16_t *off) {
    if ((uint32_t)lcc_off + len > sizeof ext_store) return 0;
    *bank = 5; *off = lcc_off; lcc_off = (uint16_t)(lcc_off + len);
    return 1;
}
void lcc_region_write(uint8_t bank, uint16_t off, const uint8_t *src, uint16_t len) {
    (void)bank;
    memcpy(ext_store + off, src, len);
}

static obj eval_src(const char *src) {
    const char *p = src;
    return eval(read_expr(&p));
}

int main(void) {
    int i;
    eval_init();
    vm_load_embedded_stdlib();

    {   /* Staged setup probe: identify the exact point where status changes. */
        const char *probes[] = {
            "(+ 1 2)",
            "(function-kind (quote ide-make-buffer))",
            "(setq bb (ide-make-buffer \"b\" (cons \"\" nil)))",
            "(setq st (ide-make-state bb))",
            "(screen-size)",
            "(setq st (ide-render st))",
        };
        unsigned k;
        for (k = 0; k < sizeof probes / sizeof probes[0]; k++) {
            obj r = eval_src(probes[k]);
            fprintf(stderr, "probe %u: %s -> vm_status=%d obj=%d\n", k, probes[k], vm_status, (int)r);
            if (vm_status != VM_OK && vm_status != VM_HALT) return 2;
        }
    }
    if (vm_status != VM_OK && vm_status != VM_HALT) {
        fprintf(stderr, "setup: vm_status=%d\n", vm_status);
        return 2;
    }
    for (i = 1; i <= 100; i++) {
        eval_src("(setq st (ide-render (ide-step st (list (quote key) 13 nil))))");
        if (vm_status != VM_OK && vm_status != VM_HALT) {
            extern uint8_t mem_oom;
            fprintf(stderr, "CRASH bei RETURN #%d: vm_status=%d (%s) mem_oom=%d gc_runs=%d\n",
                    i, vm_status, vm_status_message(), mem_oom, gc_runs);
            return 1;
        }
        {
            extern uint8_t mem_oom;
            uint16_t free_n = 0; obj f;
            for (f = mem_freelist_head(); f != NIL && free_n < 9999; f = cell_a(f)) free_n++;
            fprintf(stderr, "RETURN #%d ok (frei=%u oom=%d gc=%d)\n", i, free_n, mem_oom, gc_runs);
        }
    }
    fprintf(stderr, "100 RETURNs ohne Crash\n");
    return 0;
}
