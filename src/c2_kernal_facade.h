/* Stable calls from the owned $e000 window into moving Bank-0 code.
 * Implementations remain ordinary whole-program symbols; only these thirteen
 * entry addresses are ABI. */
#ifndef LISP65_C2_KERNAL_FACADE_H
#define LISP65_C2_KERNAL_FACADE_H

#include <stdint.h>
#include "obj.h"
#include "vm_runtime_overlay.h"

void c2_facade_vm_code_load(uint8_t bank, uint16_t offset, uint16_t length,
                            uint8_t *destination);
void c2_facade_c2_dma(uint16_t source, uint8_t source_bank,
                      uint16_t target, uint8_t target_bank, uint16_t length);
uint8_t c2_facade_overlay_call_family(uint8_t family, uint16_t generation,
                                      uint8_t slot, void *context);
uint8_t c2_facade_c2e_cons(obj value);
uint8_t c2_facade_c2e_overlay(uint8_t slot);
obj c2_facade_car(obj value);
obj c2_facade_cdr(obj value);
void c2_facade_gc_collect(void);
obj c2_facade_str_open(void);
uint8_t c2_facade_str_putc(obj string, uint8_t byte);
obj c2_facade_intern(const char *name);
vm_runtime_overlay_status c2_facade_select_family(uint8_t family,
                                                   uint16_t generation);
void c2_facade_gc_mark(obj value);
vm_runtime_overlay_status c2_facade_runtime_overlay_exec(
    uint8_t slot, void *context, uint8_t *entry_result);
uint16_t c2_facade_handle_normalize(void *context, uint16_t handle);

#endif
