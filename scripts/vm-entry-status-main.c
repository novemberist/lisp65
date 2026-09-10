/* Entry error boundary: a status already set on entry must not skip the first
 * opcode.
 *
 * This VM keeps errors sticky until the abort site, so vm_run_inner can be
 * entered with vm_status already non-OK.  The original prologue reached the
 * first dispatch iteration with no status test in between; the tail-call path
 * did cross the bottom-of-loop test.  A refactor that routes the initial entry
 * through that test changes the executed opcode stream while leaving printed
 * output and recovery identical -- which is exactly how it escapes an
 * output-only comparison (halt of 2026-09-08).
 *
 * The check here needs no trace tooling: the code object's FIRST opcode is a
 * CALL to a symbol that is not in the directory, so it reaches the tree-walker
 * bridge, and the bridge is observable.  If the first opcode runs, the bridge
 * runs.  Exit 0 = PASS.
 */
#include <stdio.h>
#include <string.h>
#include "obj.h"
#include "mem.h"
#include "symbol.h"
#include "vm.h"

#ifndef VM_CODEBUF
#define VM_CODEBUF 128   /* mirrors the vm.c default; only used for the banner */
#endif

static uint8_t code_store[64];
void vm_code_load(uint8_t bank, uint16_t off, uint16_t len, uint8_t *dst) {
    (void)bank; memcpy(dst, code_store + off, len);
}

static unsigned bridge_calls;
static obj bridge(obj sym, const obj *args, uint8_t n) {
    (void)sym; (void)args; (void)n;
    bridge_calls++;
    return NIL;
}

#define NLITS 1
#define HDRLEN (CO_OFF_LITTAB + 2 * NLITS)
static const uint8_t payload[] = {
    OP_CALL, 0, 0,      /* 0: call an uncompiled symbol -> the bridge */
    OP_RET              /* 3 */
};
#define OBJLEN ((uint16_t)(HDRLEN + sizeof payload))

static int failed;

static void row(const char *name, uint8_t preset) {
    unsigned before;
    gc_rootsp = 0;
    bridge_calls = 0;
    vm_status = preset;                 /* the state the VM can legally be in */
    before = bridge_calls;
    (void)vm_run(0, 0, OBJLEN, NULL, 0);
    printf("%-28s preset=%-2u bridge_calls=%u (want 1)%s\n",
           name, (unsigned)preset, bridge_calls - before,
           (bridge_calls - before) == 1u ? "" : "   <-- FIRST OPCODE SKIPPED");
    if ((bridge_calls - before) != 1u) failed++;
    /* the root stack must come back either way */
    if (gc_rootsp != 0) { printf("      gc_rootsp=%u (want 0)\n", (unsigned)gc_rootsp); failed++; }
}

int main(void) {
    obj sym;
    mem_init();
    vm_init();
    vm_treewalk_call = bridge;

    memset(code_store, 0, sizeof code_store);
    code_store[CO_OFF_MAGIC] = CO_MAGIC;
    code_store[CO_OFF_NARGS] = 0;
    code_store[CO_OFF_NLOCS] = 0;
    code_store[CO_OFF_FLAGS] = 0;
    code_store[CO_OFF_CLEN]  = (uint8_t)(sizeof payload);
    code_store[CO_OFF_NLITS] = NLITS;
    memcpy(code_store + HDRLEN, payload, sizeof payload);
    vm_dir_reset();
    sym = intern("not-compiled");
    code_store[CO_OFF_LITTAB + 0] = (uint8_t)((uint16_t)sym & 0xffu);
    code_store[CO_OFF_LITTAB + 1] = (uint8_t)(((uint16_t)sym >> 8) & 0xffu);

    printf("VM_CODEBUF=%d GC_ROOTS=%d\n", (int)VM_CODEBUF, (int)GC_ROOTS);
    row("clean entry",        (uint8_t)VM_OK);
    row("sticky TYPEERROR",   (uint8_t)VM_TYPEERROR);
    row("sticky BADOPCODE",   (uint8_t)VM_BADOPCODE);
    row("sticky STACKOVER",   (uint8_t)VM_STACKOVER);
    row("sticky HEAPOOM",     (uint8_t)VM_HEAPOOM);
    row("sticky DIRMISS",     (uint8_t)VM_DIRMISS);
    row("sticky ARITY",       (uint8_t)VM_ARITY);
    row("sticky HALT",        (uint8_t)VM_HALT);

    printf("vm-entry-status: %s (failures=%d)\n", failed ? "FAIL" : "PASS", failed);
    return failed ? 1 : 0;
}
