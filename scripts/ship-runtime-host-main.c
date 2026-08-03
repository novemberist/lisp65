/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/. */

/* Host execution witness for an evaluator-free Ship Runtime image. */
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include "interrupt.h"
#include "mem.h"
#include "ship_runtime_io.h"
#include "symbol.h"
#include "vm.h"
#include "vm_embed.h"

#ifndef LISP65_SHIP_ENTRY
#error "LISP65_SHIP_ENTRY is required"
#endif

static uint8_t ext_code[65536];
static uint16_t host_raster_line;

uint16_t lisp65_ship_io_host_raster_step(void) {
    uint16_t event;
    host_raster_line = (uint16_t)((host_raster_line + 1u) % 312u);
    event = host_raster_line;
    if (host_raster_line == 255u) event |= LISP65_SHIP_HOST_RASTER_IRQ;
    return event;
}

void vm_ext_write(const uint8_t *src, uint16_t len, uint8_t bank, uint16_t off) {
    if (bank != 5 || (uint32_t)off + len > sizeof(ext_code)) return;
    memcpy(ext_code + off, src, len);
}

void vm_code_load(uint8_t bank, uint16_t off, uint16_t len, uint8_t *dst) {
    if (bank != 5 || (uint32_t)off + len > sizeof(ext_code)) {
        memset(dst, 0, len);
        return;
    }
    memcpy(dst, ext_code + off, len);
}

int main(void) {
    obj truth, entry, fn, result;
    if (setjmp(lisp_toplevel)) {
        fprintf(stderr, "ship-runtime-host: FAIL abort=%s\n",
                lisp_error_msg ? lisp_error_msg : "unknown");
        return 1;
    }
    lisp_toplevel_active = 1;
    mem_init();
    vm_dir_reset();
    vm_init();
    truth = intern("t");
    set_sym_value(truth, truth);
    vm_load_embedded_stdlib();
#ifdef LISP65_EXT_HEAP
    gc_freeze_boot();
#endif
    if (lisp65_ship_io_host_clock_armed()
        || lisp65_ship_io_host_clock_verified()
        || lisp65_ship_io_host_input_armed()) {
        fprintf(stderr, "ship-runtime-host: FAIL inherited host I/O was armed\n");
        return 1;
    }
    if (!lisp65_ship_io_init()
        || !lisp65_ship_io_host_clock_armed()
        || !lisp65_ship_io_host_clock_verified()
        || lisp65_ship_io_host_verified_deltas() != 3u
        || !lisp65_ship_io_host_input_armed()) {
        fprintf(stderr, "ship-runtime-host: FAIL boot I/O was not proved\n");
        return 1;
    }
    entry = intern(LISP65_SHIP_ENTRY);
    fn = sym_function(entry);
    if (!IS_BCODE(fn)) {
        fprintf(stderr, "ship-runtime-host: FAIL missing-entry=%s\n", LISP65_SHIP_ENTRY);
        return 1;
    }
    vm_status = VM_OK;
    result = vm_run_dir((int)BCODE_IDX(fn), 0, 0);
    if (vm_status != VM_OK && vm_status != VM_HALT) {
        fprintf(stderr, "ship-runtime-host: FAIL status=%u\n", (unsigned)vm_status);
        return 1;
    }
    lisp_toplevel_active = 0;
    printf("ship-runtime-host: PASS entry=%s result=0x%04x status=%u input=%u output=%u output-hash=%08lx boot-armed=1 boot-verified=1 input-armed=1\n",
           LISP65_SHIP_ENTRY, (unsigned)result, (unsigned)vm_status,
           (unsigned)lisp65_ship_io_input_used(),
           (unsigned)lisp65_ship_io_output_count(),
           (unsigned long)lisp65_ship_io_output_hash());
    return 0;
}
