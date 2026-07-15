/* Emit assembler symbols directly from the C-side contracts. */
#include <stddef.h>
#include <stdio.h>

#include "l65m_batch_contract.h"
#include "r3-cold-stager-contract.h"

static void equ(const char *name, unsigned long value) {
    printf(".equ\t%s, %lu\n", name, value);
}

int main(void) {
    puts("; Generated from C contracts. Do not edit.");
    equ("ASM_L65M_OK", L65M_OK);
    equ("ASM_L65M_PREFLIGHT_ABI", L65M_OVERLAY_ABI_VERSION);
    equ("ASM_L65M_COMMIT_ABI", L65M_COMMIT_OVERLAY_ABI_VERSION);
    equ("ASM_L65M_PREFLIGHT_SLOT_BASE", VM_RTOV_PREFLIGHT_SLOT_BASE);
    equ("ASM_L65M_COMMIT_SLOT_BASE", VM_RTOV_COMMIT_SLOT_BASE);
    equ("ASM_L65M_ABI_VERSION_OFFSET", offsetof(vm_l65m_batch_header, abi_version));
    equ("ASM_L65M_ABI_VERSION_HIGH_OFFSET",
        offsetof(vm_l65m_batch_header, abi_version) + 1u);
    equ("ASM_L65M_EXPECTED_PHASE_OFFSET",
        offsetof(vm_l65m_batch_header, expected_phase));
    equ("ASM_L65M_BUSY_OFFSET", offsetof(vm_l65m_batch_header, busy));
    equ("ASM_L65M_REPEAT_PHASE_OFFSET",
        offsetof(vm_l65m_batch_header, repeat_phase));
    equ("ASM_R3_CHAIN_JOB_ADDR_LO", R3_CHAIN_JOB_ADDR & 0xffu);
    equ("ASM_R3_CHAIN_JOB_ADDR_HI", (R3_CHAIN_JOB_ADDR >> 8) & 0xffu);
    equ("ASM_R3_PRODUCT_ENTRY", R3_PRODUCT_ENTRY);
    return 0;
}
