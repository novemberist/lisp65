#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include "intern_service_overlay.h"
#include "mem.h"
#include "symbol.h"
#include "vm.h"

char sym_name_scratch[LISP65_SYMBOL_NAME_BUFFER];
uint8_t mem_oom;
Cell heap[HEAP_CELLS];
static const char *source_text;
static uint16_t source_length;

uint16_t str_copy_out(obj string, char *dst, uint16_t max) {
    uint16_t count = source_length < max ? source_length : max;
    (void)string;
    memcpy(dst, source_text, count);
    return count;
}

uint16_t str_len(obj string) {
    return (uint16_t)FIXVAL(cell_a(string));
}

obj intern(const char *name) {
    if (!strcmp(name, "alpha") || strlen(name) == LISP65_SYMBOL_NAME_MAX)
        return (obj)0x2469u;
    return NIL;
}

int main(void) {
    lisp65_buffer_overlay_context context;
    obj args[1];
    char exact[LISP65_SYMBOL_NAME_BUFFER];
    uint8_t status;

    memset(exact, 'q', LISP65_SYMBOL_NAME_MAX);
    exact[LISP65_SYMBOL_NAME_MAX] = '\0';
    source_text = "alpha";
    source_length = 5u;
    args[0] = (obj)2u;
    heap[1].type = T_STR;
    heap[1].a = MKFIX(source_length);
    context.args = args;
    context.result = NIL;
    context.argc = 1u;
    status = lisp65_intern_service_entry(&context);
    if (status != VM_OK || context.result != (obj)0x2469u
        || strcmp(sym_name_scratch, "alpha"))
        return 1;
    if (lisp65_intern_service_entry(0) != VM_BADOPCODE)
        return 2;
    source_length = LISP65_SYMBOL_NAME_MAX + 1u;
    heap[1].a = MKFIX(source_length);
    if (lisp65_intern_service_entry(&context) != VM_TYPEERROR)
        return 3;
    source_text = exact;
    source_length = LISP65_SYMBOL_NAME_MAX;
    heap[1].a = MKFIX(source_length);
    context.result = NIL;
    if (lisp65_intern_service_entry(&context) != VM_OK
        || context.result != (obj)0x2469u
        || strcmp(sym_name_scratch, exact))
        return 4;
    source_text = "missing";
    source_length = 7u;
    heap[1].a = MKFIX(source_length);
    context.result = (obj)0x2469u;
    mem_oom = 1u;
    if (lisp65_intern_service_entry(&context) != VM_HEAPOOM)
        return 5;
    puts("c2-intern-session-service: PASS cases=5 exact-name=33 "
         "state-bytes=0");
    return 0;
}
