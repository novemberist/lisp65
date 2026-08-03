/* Host-only attribution lane for the v1.2.6 editor key-55/56 stall.
 *
 * This is deliberately the real C evaluator/VM/collector with the Workbench
 * heap geometry.  The Python editor oracle has an unbounded heap and cannot
 * answer whether a retained editor cache crosses a target GC boundary.
 * Screen and EXT transports remain plain host memory copies; no product bytes
 * or target transport semantics are changed by this harness.
 */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "c2_kernal_runtime.h"
#include "mem.h"
#include "obj.h"
#include "screen.h"
#include "symbol.h"
#include "vm.h"
#include "vm_embed.h"

obj mem_freelist_head(void);
extern uint8_t mem_oom;

static uint8_t ext_store[65536];
static uint16_t free_cells(void);
static const uint8_t loop_keys[] = {
    /* Eighty ordinary characters.  Completion is the next blocking read:
     * reaching it proves the 80th step, drain, render, tailcall and persistent
     * state store all completed. */
    97, 97, 97, 97, 97, 97, 97, 97, 97, 97,
    97, 97, 97, 97, 97, 97, 97, 97, 97, 97,
    97, 97, 97, 97, 97, 97, 97, 97, 97, 97,
    97, 97, 97, 97, 97, 97, 97, 97, 97, 97,
    97, 97, 97, 97, 97, 97, 97, 97, 97, 97,
    97, 97, 97, 97, 97, 97, 97, 97, 97, 97,
    97, 97, 97, 97, 97, 97, 97, 97, 97, 97,
    97, 97, 97, 97, 97, 97, 97, 97, 97, 97,
};
static uint16_t loop_key_at;
static uint8_t loop_empty_poll;

static void require_visible_ack(void) {
    const uint8_t *screen;
    uint16_t i;

    /* The device harness releases the next key only after the cumulative line
     * is visible.  Mirror that contract here instead of treating a return from
     * ide-render as an acknowledgement by assumption.  Column 79 is the
     * editor's fill boundary, so the ordinary one-line assertion covers the
     * exact failing transition (55 -> 56); the 80th key is accepted by the
     * separate completion witness below after the automatic wrap. */
    if (loop_key_at == 0 || loop_key_at >= 80) return;
    screen = scr_host_buf();
    for (i = 0; i < loop_key_at; ++i) {
        if ((screen[i] & 0x7fu) != 1u) {
            fprintf(stderr,
                    "editor-target-host: FAIL phase=visible-ack key=%u "
                    "column=%u screen-code=%u free=%u gc=%u\n",
                    (unsigned)loop_key_at, (unsigned)i,
                    (unsigned)(screen[i] & 0x7fu), (unsigned)free_cells(),
                    (unsigned)gc_runs);
            fflush(stderr);
            exit(8);
        }
    }
}

/* Model the product-owned typed queue at its one-event-at-a-time contract.
 * After every event, one nonblocking poll observes an empty queue.  The next
 * blocking read then receives the next event.  This makes ide-run execute one
 * ide-step plus one ide-render per key, matching the hardware First Red rather
 * than collapsing the input into one coalesced burst. */
uint8_t c2_kernal_event_poll(lisp65_key_event *event) {
    if (loop_empty_poll) {
        loop_empty_poll = 0;
        return 0;
    }
    require_visible_ack();
    if (loop_key_at >= sizeof(loop_keys)) {
        fprintf(stderr,
                "editor-target-host: PASS mode=loop accepted=80 "
                "free=%u oom=%u gc=%u\n",
                (unsigned)free_cells(), (unsigned)mem_oom,
                (unsigned)gc_runs);
        fflush(stderr);
        exit(0);
    }
    event->code = loop_keys[loop_key_at++];
    event->modifiers = 0;
    loop_empty_poll = 1;
    if (loop_key_at >= 50) {
        fprintf(stderr,
                "editor-target-host: EVENT delivered=%u code=%u free=%u gc=%u\n",
                (unsigned)loop_key_at, (unsigned)event->code,
                (unsigned)free_cells(), (unsigned)gc_runs);
        fflush(stderr);
    }
    return 1;
}

void vm_code_load(uint8_t bank, uint16_t off, uint16_t len, uint8_t *dst) {
    (void)bank;
    memcpy(dst, ext_store + off, len);
}

void vm_ext_write(const uint8_t *src, uint16_t len, uint8_t bank, uint16_t off) {
    (void)bank;
    memcpy(ext_store + off, src, len);
}

static uint16_t free_cells(void) {
    uint16_t count = 0;
    obj cursor;
    for (cursor = mem_freelist_head(); cursor != NIL && count < MAX_CELLS;
         cursor = cell_a(cursor))
        count++;
    return count;
}

static obj call_named(const char *name, obj *args, uint8_t nargs) {
    obj function = sym_function(intern(name));
    if (!IS_BCODE(function)) {
        fprintf(stderr, "editor-target-host: FAIL missing=%s raw=%d\n",
                name, (int)function);
        vm_status = VM_BADOPCODE;
        return NIL;
    }
    vm_status = VM_OK;
    return vm_run_dir((int)BCODE_IDX(function), args, nargs);
}

static int expect_ok(const char *phase, unsigned key) {
    if (vm_status == VM_OK || vm_status == VM_HALT) return 1;
    fprintf(stderr,
            "editor-target-host: FAIL phase=%s key=%u status=%d message=%s "
            "oom=%u gc=%u free=%u\n",
            phase, key, vm_status, vm_status_message(), (unsigned)mem_oom,
            (unsigned)gc_runs, (unsigned)free_cells());
    return 0;
}

static int point_column(obj state) {
    obj buffer, tail, point;
    if (!IS_PTR(state) || cell_type(state) != T_CONS) return -1;
    buffer = cell_a(state);
    if (!IS_PTR(buffer) || cell_type(buffer) != T_CONS) return -1;
    tail = cell_b(buffer);
    if (!IS_PTR(tail) || cell_type(tail) != T_CONS) return -1;
    tail = cell_b(tail);
    if (!IS_PTR(tail) || cell_type(tail) != T_CONS) return -1;
    tail = cell_b(tail);
    if (!IS_PTR(tail) || cell_type(tail) != T_CONS) return -1;
    point = cell_a(tail);
    if (!IS_PTR(point) || cell_type(point) != T_CONS || !IS_FIX(cell_b(point)))
        return -1;
    return (int)FIXVAL(cell_b(point));
}

int main(int argc, char **argv) {
    unsigned key;
    obj state_symbol, state, name, empty, lines, event, args[2];
    int run_loop = argc == 2 && strcmp(argv[1], "--loop") == 0;

    if (argc > 2 || (argc == 2 && !run_loop)) {
        fprintf(stderr, "usage: %s [--loop]\n", argv[0]);
        return 64;
    }

    mem_init();
    vm_dir_reset();
    vm_init();
    scr_init();
    vm_load_embedded_stdlib();
    if (!expect_ok("boot", 0)) return 2;
    gc_freeze_boot();

    state_symbol = intern("%editor-target-host-state");
    name = str_from_bytes((const uint8_t *)"b", 1);
    GC_PUSH(name);
    empty = str_from_bytes((const uint8_t *)"", 0);
    GC_PUSH(empty);
    lines = cons(gc_rootstack[GC_TOP], NIL);
    GC_PUSH(lines);
    args[0] = gc_rootstack[GC_TOP - 2];
    args[1] = gc_rootstack[GC_TOP];
    state = call_named("ide-make-buffer", args, 2);
    if (!expect_ok("make-buffer", 0)) return 2;
    GC_SET(GC_TOP, state);
    args[0] = state;
    state = call_named("ide-make-state", args, 1);
    if (!expect_ok("make-state", 0)) return 2;
    GC_SET(GC_TOP, state);
    set_sym_value(state_symbol, state);
    GC_POPN(3);
    if (!expect_ok("setup", 0)) return 2;
    args[0] = sym_value(state_symbol);
    state = call_named("ide-render", args, 1);
    set_sym_value(state_symbol, state);
    if (!expect_ok("warm-render", 0)) return 2;

    fprintf(stderr,
            "editor-target-host: START max_cells=%u free=%u gc=%u\n",
            (unsigned)MAX_CELLS, (unsigned)free_cells(), (unsigned)gc_runs);
    fflush(stderr);

    if (run_loop) {
        loop_key_at = 0;
        loop_empty_poll = 0;
        args[0] = sym_value(state_symbol);
        state = call_named("ide-run", args, 1);
        set_sym_value(state_symbol, state);
        /* The mock queue terminates successfully at the next blocking read;
         * returning here would mean ide-run exited by an unexpected route. */
        fprintf(stderr,
                "editor-target-host: FAIL phase=loop-return delivered=%u "
                "status=%d\n", (unsigned)loop_key_at, vm_status);
        return 7;
    }

    for (key = 1; key <= 80; key++) {
        int column;
        event = cons(NIL, NIL);
        GC_PUSH(event);
        event = cons(MKFIX(97), gc_rootstack[GC_TOP]);
        GC_SET(GC_TOP, event);
        event = cons(intern("key"), gc_rootstack[GC_TOP]);
        GC_SET(GC_TOP, event);
        args[0] = sym_value(state_symbol);
        args[1] = event;
        state = call_named("ide-step", args, 2);
        GC_POPN(1);
        set_sym_value(state_symbol, state);
        if (!expect_ok("step", key)) return 3;
        args[0] = sym_value(state_symbol);
        state = call_named("ide-render", args, 1);
        set_sym_value(state_symbol, state);
        if (!expect_ok("render", key)) return 4;
        column = point_column(state);
        if (column < 0) return 5;
        fprintf(stderr,
                "editor-target-host: KEY key=%u column=%d free=%u oom=%u gc=%u\n",
                key, column, (unsigned)free_cells(), (unsigned)mem_oom,
                (unsigned)gc_runs);
        fflush(stderr);
        if ((key < 80 && column != (int)key)
            || (key == 80 && column != 1)) {
            fprintf(stderr,
                    "editor-target-host: FAIL phase=ack key=%u column=%d\n",
                    key, column);
            return 6;
        }
    }

    fprintf(stderr,
            "editor-target-host: PASS accepted=80 free=%u oom=%u gc=%u\n",
            (unsigned)free_cells(), (unsigned)mem_oom, (unsigned)gc_runs);
    return 0;
}
