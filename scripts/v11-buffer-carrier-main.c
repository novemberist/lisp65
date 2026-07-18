/* Host gate for the private 1.1-E carrier ABI. This exercises product C code;
 * the separate Python suite is the independent semantic oracle. */
#include <stdint.h>
#include <stdio.h>

#include "buffer_overlay.h"
#include "mem.h"
#include "vm.h"

static unsigned checks;
static unsigned failures;

static void expect(int condition, const char *label) {
    checks++;
    if (!condition) {
        failures++;
        fprintf(stderr, "FAIL: %s\n", label);
    }
}

static uint8_t invoke(uint8_t entry, obj *args, uint8_t argc, obj *result) {
    lisp65_buffer_overlay_context context;
    uint8_t status;
    context.args = args;
    context.argc = argc;
    context.result = (obj)0x7ffe;
    if (entry == LISP65_BUFFER_PRIM_READ)
        status = lisp65_buffer_overlay_read_entry(&context);
    else if (entry == LISP65_BUFFER_PRIM_WRITE)
        status = lisp65_buffer_overlay_write_entry(&context);
    else status = lisp65_buffer_overlay_alloc_entry(&context);
    *result = context.result;
    return status;
}

int main(void) {
    static const uint8_t abc[] = {'a', 'b', 'c'};
    obj args[3], result, buffer, string, copy;
    uint8_t status;

    mem_init();

    args[0] = MKFIX(0); args[1] = MKFIX(4);
    status = invoke(LISP65_BUFFER_PRIM_ALLOC, args, 2, &buffer);
    expect(status == VM_OK && IS_PTR(buffer) && cell_type(buffer) == T_BUF,
           "make-buffer publishes a buffer only after allocation");

    args[0] = MKFIX(0); args[1] = buffer;
    expect(invoke(LISP65_BUFFER_PRIM_READ, args, 2, &result) == VM_OK &&
           result == buffer, "buffer predicate returns truthy witness");
    args[0] = MKFIX(1); args[1] = buffer;
    expect(invoke(LISP65_BUFFER_PRIM_READ, args, 2, &result) == VM_OK &&
           FIXVAL(result) == 4, "buffer length");
    args[0] = MKFIX(2); args[1] = buffer; args[2] = MKFIX(3);
    expect(invoke(LISP65_BUFFER_PRIM_READ, args, 3, &result) == VM_OK &&
           FIXVAL(result) == 0, "new buffer is zero filled and zero based");

    args[0] = buffer; args[1] = MKFIX(3); args[2] = MKFIX(255);
    expect(invoke(LISP65_BUFFER_PRIM_WRITE, args, 3, &result) == VM_OK &&
           FIXVAL(result) == 255 && buf_byte(buffer, 3) == 255,
           "write returns byte and mutates exact index");

    string = str_from_bytes(abc, sizeof abc);
    args[0] = MKFIX(1); args[1] = string;
    status = invoke(LISP65_BUFFER_PRIM_ALLOC, args, 2, &copy);
    expect(status == VM_OK && cell_type(copy) == T_BUF && buf_len(copy) == 3 &&
           buf_byte(copy, 0) == 'a' && buf_byte(copy, 2) == 'c',
           "string-to-buffer copies bytes");
    args[0] = MKFIX(3); args[1] = copy;
    expect(invoke(LISP65_BUFFER_PRIM_READ, args, 2, &result) == VM_OK &&
           result == copy && cell_type(copy) == T_STR && str_byte(copy, 1) == 'b',
           "freeze transfers the same allocation atomically");
    args[0] = MKFIX(0); args[1] = copy;
    expect(invoke(LISP65_BUFFER_PRIM_READ, args, 2, &result) == VM_OK &&
           result == NIL, "frozen object is no longer a buffer");

    args[0] = MKFIX(0); args[1] = MKFIX(-1);
    expect(invoke(LISP65_BUFFER_PRIM_ALLOC, args, 2, &result) == VM_TYPEERROR &&
           result == NIL, "negative allocation fails closed");
    args[0] = MKFIX(0); args[1] = MKFIX((int16_t)(str_arena_capacity() + 1u));
    expect(invoke(LISP65_BUFFER_PRIM_ALLOC, args, 2, &result) == VM_HEAPOOM &&
           result == NIL, "arena OOM publishes no buffer");

    args[0] = buffer; args[1] = MKFIX(-1); args[2] = MKFIX(1);
    expect(invoke(LISP65_BUFFER_PRIM_WRITE, args, 3, &result) == VM_TYPEERROR &&
           result == NIL, "negative index rejected");
    args[1] = MKFIX(4);
    expect(invoke(LISP65_BUFFER_PRIM_WRITE, args, 3, &result) == VM_TYPEERROR,
           "upper index rejected");
    args[1] = MKFIX(0); args[2] = MKFIX(256);
    expect(invoke(LISP65_BUFFER_PRIM_WRITE, args, 3, &result) == VM_TYPEERROR,
           "non-byte value rejected");
    expect(invoke(LISP65_BUFFER_PRIM_WRITE, args, 2, &result) == VM_ARITY,
           "write strict arity");

    args[0] = MKFIX(2); args[1] = buffer; args[2] = MKFIX(4);
    expect(invoke(LISP65_BUFFER_PRIM_READ, args, 3, &result) == VM_TYPEERROR &&
           result == NIL, "read upper bound rejected");
    args[0] = MKFIX(1); args[1] = MKFIX(1);
    expect(invoke(LISP65_BUFFER_PRIM_READ, args, 2, &result) == VM_TYPEERROR,
           "read buffer type rejected");
    args[0] = MKFIX(9); args[1] = buffer;
    expect(invoke(LISP65_BUFFER_PRIM_READ, args, 2, &result) == VM_TYPEERROR,
           "unknown read operation rejected");

    fprintf(stdout,
            "v11-buffer-carrier-observation-v1 checks=%u failures=%u "
            "length=4 last=255 copy=abc freeze=same oom=closed\n",
            checks, failures);
    return failures ? 1 : 0;
}
