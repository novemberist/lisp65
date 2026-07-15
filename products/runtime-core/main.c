/* lisp65 Runtime Core - evaluator-free boot and named bytecode entry. */
#include <setjmp.h>
#include <stdint.h>

#include "interrupt.h"
#include "mem.h"
#include "preload_integrity.h"
#include "symbol.h"
#include "vm.h"
#include "vm_embed.h"

#ifndef LISP65_RUNTIME_ENTRY
#define LISP65_RUNTIME_ENTRY "runtime-main"
#endif

#ifndef LISP65_RUNTIME_PRELOAD_PAYLOAD_BYTES
#error "build-bound Runtime Core preload length is required"
#endif
#ifndef LISP65_RUNTIME_PRELOAD_CRC16
#error "build-bound Runtime Core preload CRC16 is required"
#endif
#ifndef LISP65_RUNTIME_PRELOAD_BUILD_ID
#error "build-bound Runtime Core preload build ID is required"
#endif
#ifndef LISP65_RUNTIME_PRELOAD_BANK
#define LISP65_RUNTIME_PRELOAD_BANK 5u
#endif
#ifndef LISP65_RUNTIME_PRELOAD_OFF
#define LISP65_RUNTIME_PRELOAD_OFF 0u
#endif
#if LISP65_RUNTIME_PRELOAD_BANK != 5u || LISP65_RUNTIME_PRELOAD_OFF != 0u
#error "Runtime Core preload must preserve the Bank-5 offset-zero layout"
#endif

#define RUNTIME_BIND_BYTE(value, shift) \
    ((uint8_t)(((uint32_t)(value) >> (shift)) & 0xffu))

/* Ship-v2 verifies this record directly in the PRG. Volatile reads make it
 * the runtime source of truth as well, so a foreign profile can be rebound
 * without recompiling otherwise identical code. */
volatile const uint8_t lisp65_runtime_preload_binding_record[
    RUNTIME_PRELOAD_BINDING_RECORD_BYTES
] __attribute__((used)) = {
    'L', '6', '5', 'P',
    RUNTIME_PRELOAD_BINDING_RECORD_VERSION,
    RUNTIME_PRELOAD_BINDING_RECORD_BYTES,
    RUNTIME_BIND_BYTE(LISP65_RUNTIME_PRELOAD_PAYLOAD_BYTES, 0),
    RUNTIME_BIND_BYTE(LISP65_RUNTIME_PRELOAD_PAYLOAD_BYTES, 8),
    RUNTIME_BIND_BYTE(LISP65_RUNTIME_PRELOAD_CRC16, 0),
    RUNTIME_BIND_BYTE(LISP65_RUNTIME_PRELOAD_CRC16, 8),
    RUNTIME_BIND_BYTE(LISP65_RUNTIME_PRELOAD_BUILD_ID, 0),
    RUNTIME_BIND_BYTE(LISP65_RUNTIME_PRELOAD_BUILD_ID, 8),
    RUNTIME_BIND_BYTE(LISP65_RUNTIME_PRELOAD_BUILD_ID, 16),
    RUNTIME_BIND_BYTE(LISP65_RUNTIME_PRELOAD_BUILD_ID, 24)
};

enum {
    RUNTIME_BOOTING = 1,
    RUNTIME_LOADED = 2,
    RUNTIME_COMPLETE = 3,
    RUNTIME_BOOT_ERROR = 0xe1,
    RUNTIME_ENTRY_ERROR = 0xe2,
    RUNTIME_VM_ERROR = 0xe3,
    RUNTIME_PRELOAD_ERROR = 0xe4
};

volatile uint8_t lisp65_runtime_state = 0;
volatile obj lisp65_runtime_result = NIL;
volatile uint8_t lisp65_runtime_preload_detail = RUNTIME_PRELOAD_OK;

static uint8_t runtime_preload_read(void *context, uint16_t offset,
                                    uint8_t *dst, uint16_t length) {
    uint32_t end;
    (void)context;
    end = (uint32_t)LISP65_RUNTIME_PRELOAD_OFF + offset + length;
    if (end > 0x10000UL) return 0;
    vm_code_load((uint8_t)LISP65_RUNTIME_PRELOAD_BANK,
                 (uint16_t)(LISP65_RUNTIME_PRELOAD_OFF + offset), length, dst);
    return 1;
}

static uint16_t runtime_binding_u16(uint8_t offset) {
    return (uint16_t)(lisp65_runtime_preload_binding_record[offset]
        | ((uint16_t)lisp65_runtime_preload_binding_record[offset + 1u] << 8));
}

static uint32_t runtime_binding_u32(uint8_t offset) {
    return (uint32_t)lisp65_runtime_preload_binding_record[offset]
        | ((uint32_t)lisp65_runtime_preload_binding_record[offset + 1u] << 8)
        | ((uint32_t)lisp65_runtime_preload_binding_record[offset + 2u] << 16)
        | ((uint32_t)lisp65_runtime_preload_binding_record[offset + 3u] << 24);
}

int main(void) {
    obj t, entry, fn, result;
    runtime_preload_contract preload;
    runtime_preload_status preload_status;

#if defined(__MEGA65__)
    *(volatile unsigned char *)0xD02F = 0x47;
    *(volatile unsigned char *)0xD02F = 0x53;
    *(volatile unsigned char *)0xD054 |= 0x40;
#endif

    if (setjmp(lisp_toplevel)) {
        lisp65_runtime_state = RUNTIME_BOOT_ERROR;
        return 1;
    }
    lisp_toplevel_active = 1;
    lisp65_runtime_state = RUNTIME_BOOTING;
    lisp65_runtime_result = NIL;
    lisp65_runtime_preload_detail = RUNTIME_PRELOAD_OK;

    preload.payload_length = runtime_binding_u16(6u);
    preload.image_crc16 = runtime_binding_u16(8u);
    preload.build_id = runtime_binding_u32(10u);
    preload_status = runtime_preload_verify(runtime_preload_read, 0,
                                             &preload, 0);
    if (preload_status != RUNTIME_PRELOAD_OK) {
        lisp65_runtime_preload_detail = (uint8_t)preload_status;
        lisp65_runtime_state = RUNTIME_PRELOAD_ERROR;
        return 4;
    }

    mem_init();
    vm_dir_reset();
    vm_init();
    t = intern("t");
    set_sym_value(t, t);
    vm_load_embedded_stdlib();
#ifdef LISP65_EXT_HEAP
    gc_freeze_boot();
#endif
    lisp65_runtime_state = RUNTIME_LOADED;

    entry = intern(LISP65_RUNTIME_ENTRY);
    fn = sym_function(entry);
    if (!IS_BCODE(fn)) {
        vm_status = VM_DIRMISS;
        lisp65_runtime_state = RUNTIME_ENTRY_ERROR;
        return 2;
    }

    vm_status = VM_OK;
    result = vm_run_dir((int)BCODE_IDX(fn), 0, 0);
    lisp65_runtime_result = result;
    if (vm_status != VM_OK && vm_status != VM_HALT) {
        lisp65_runtime_state = RUNTIME_VM_ERROR;
        return 3;
    }
    lisp65_runtime_state = RUNTIME_COMPLETE;
    return 0;
}
