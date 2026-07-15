/* Native host proof for the manifest-bound resident dialect-v2 LCC. */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <setjmp.h>

#include "eval.h"
#include "interrupt.h"
#include "mem.h"
#include "reader.h"
#include "symbol.h"
#include "vm.h"
#include "stdlib-p0.h"

extern const uint8_t lisp65_stdlib_blob[];

#define CODE_STORE_BYTES 60000u
static uint8_t code_store[CODE_STORE_BYTES];
static uint16_t code_used;
static obj keep_symbol = NIL;

uint8_t lisp65_error_render_code(lisp65_error_code code, obj symbol) {
    (void)code;
    (void)symbol;
    return 0;
}

const char *io_load_file(const char *name) {
    (void)name;
    return NULL;
}

int lcc_region_alloc(uint16_t length, uint8_t *bank, uint16_t *off) {
    if (!bank || !off || (uint32_t)code_used + length > sizeof(code_store))
        return 0;
    *bank = lisp65_stdlib_bank;
    *off = code_used;
    code_used = (uint16_t)(code_used + length);
    return 1;
}

void lcc_region_write(uint8_t bank, uint16_t off,
                      const uint8_t *source, uint16_t length) {
    if (bank != lisp65_stdlib_bank || !source ||
        (uint32_t)off + length > code_used) {
        fprintf(stderr, "manifest-vm: code write outside allocated region\n");
        exit(3);
    }
    memcpy(code_store + off, source, length);
}

void vm_code_load(uint8_t bank, uint16_t off, uint16_t len, uint8_t *dst) {
    if (bank != lisp65_stdlib_bank || (uint32_t)off + len > sizeof(code_store)) {
        fprintf(stderr, "manifest-vm: code read outside bound blob\n");
        exit(3);
    }
    memcpy(dst, code_store + off, len);
}

static uint8_t is_symbol(obj value) {
    return IS_SYMI(value) || (IS_PTR(value) && cell_type(value) == T_SYM);
}

static obj materialize_literal(uint16_t index, uint16_t depth) {
    const lisp65_bc_literal_node *node;
    obj value, other;
    uint16_t cursor;

    if (index >= LISP65_BYTECODE_STDLIB_LITERAL_NODE_COUNT || depth >= 128u)
        return NIL;
    node = &lisp65_bytecode_stdlib_literal_nodes[index];
    switch (node->kind) {
    case LISP65_BC_LIT_FIX:
        return MKFIX(node->value);
    case LISP65_BC_LIT_NIL:
        return NIL;
    case LISP65_BC_LIT_T:
        return intern("t");
    case LISP65_BC_LIT_SYMBOL:
        return node->name ? intern(node->name) : NIL;
    case LISP65_BC_LIT_STRING:
        return node->name
             ? str_from_bytes((const uint8_t *)node->name,
                              (uint16_t)strlen(node->name))
             : NIL;
    case LISP65_BC_LIT_CONS:
        if (node->count != 2u ||
            (uint32_t)node->first + 1u >=
                LISP65_BYTECODE_STDLIB_LITERAL_INDEX_COUNT)
            return NIL;
        value = materialize_literal(
            lisp65_bytecode_stdlib_literal_index[node->first],
            (uint16_t)(depth + 1u));
        GC_PUSH(value);
        other = materialize_literal(
            lisp65_bytecode_stdlib_literal_index[node->first + 1u],
            (uint16_t)(depth + 1u));
        value = gc_rootstack[GC_TOP];
        GC_POPN(1);
        return cons(value, other);
    case LISP65_BC_LIT_LIST:
        if ((uint32_t)node->first + node->count >
            LISP65_BYTECODE_STDLIB_LITERAL_INDEX_COUNT)
            return NIL;
        value = NIL;
        GC_PUSH(value);
        for (cursor = node->count; cursor > 0u; cursor--) {
            other = materialize_literal(
                lisp65_bytecode_stdlib_literal_index[
                    node->first + cursor - 1u],
                (uint16_t)(depth + 1u));
            value = cons(other, gc_rootstack[GC_TOP]);
            GC_SET(GC_TOP, value);
        }
        GC_POPN(1);
        return value;
    default:
        return NIL;
    }
}

static uint8_t keep_literal(obj value) {
    obj kept;
    if (!IS_PTR(value) || cell_type(value) == T_SYM) return 1;
    GC_PUSH(value);
    kept = cons(gc_rootstack[GC_TOP], sym_value(keep_symbol));
    value = gc_rootstack[GC_TOP];
    GC_POPN(1);
    if (kept == NIL || mem_oom) return 0;
    set_sym_value(keep_symbol, kept);
    (void)value;
    return 1;
}

static uint8_t load_manifest_artifact(void) {
    uint16_t index;

    if (lisp65_stdlib_blob_len != LISP65_BYTECODE_STDLIB_BLOB_BYTES ||
        lisp65_embed_count != LISP65_BYTECODE_STDLIB_EMBED_COUNT)
        return 0;
    memcpy(code_store, lisp65_stdlib_blob,
           LISP65_BYTECODE_STDLIB_BLOB_BYTES);
    code_used = LISP65_BYTECODE_STDLIB_BLOB_BYTES;
    keep_symbol = intern("%manifest-literal-keep");
    if (!is_symbol(keep_symbol)) return 0;

    for (index = 0; index < LISP65_BYTECODE_STDLIB_LITERAL_PATCH_COUNT; index++) {
        const lisp65_bc_literal_patch *patch =
            &lisp65_bytecode_stdlib_literal_patches[index];
        obj value;
        if ((uint32_t)patch->blob_offset + 2u > sizeof(code_store) ||
            patch->node >= LISP65_BYTECODE_STDLIB_LITERAL_NODE_COUNT)
            return 0;
        value = materialize_literal(patch->node, 0);
        if (mem_oom || !keep_literal(value)) return 0;
        code_store[patch->blob_offset] = (uint8_t)(uint16_t)value;
        code_store[patch->blob_offset + 1u] =
            (uint8_t)((uint16_t)value >> 8);
    }
    return vm_register_embedded(lisp65_embed, lisp65_embed_count);
}

static obj quoted_argument(const char *source) {
    const char *cursor = source;
    obj form = read_expr(&cursor), args, quoted, quote_args;
    if (!(IS_PTR(form) && cell_type(form) == T_CONS) ||
        !is_symbol(cell_a(form)) ||
        strcmp(symname(cell_a(form)), "lcc-compile-obj") != 0)
        return NIL;
    args = cell_b(form);
    if (!(IS_PTR(args) && cell_type(args) == T_CONS) || cell_b(args) != NIL)
        return NIL;
    quoted = cell_a(args);
    if (!(IS_PTR(quoted) && cell_type(quoted) == T_CONS) ||
        !is_symbol(cell_a(quoted)) || strcmp(symname(cell_a(quoted)), "quote") != 0)
        return NIL;
    quote_args = cell_b(quoted);
    if (!(IS_PTR(quote_args) && cell_type(quote_args) == T_CONS) ||
        cell_b(quote_args) != NIL)
        return NIL;
    while (*cursor == ' ' || *cursor == '\t' || *cursor == '\r' || *cursor == '\n')
        cursor++;
    return *cursor == '\0' ? cell_a(quote_args) : NIL;
}

static obj read_complete_form(const char *source) {
    const char *cursor = source;
    obj form = read_expr(&cursor);
    while (*cursor == ' ' || *cursor == '\t' || *cursor == '\r' || *cursor == '\n')
        cursor++;
    return *cursor == '\0' ? form : NIL;
}

static uint8_t run_surface_case(
    const char *label, const char *function_name, const char *args_source
) {
    obj function = intern(function_name);
    obj arguments = read_complete_form(args_source);
    obj result;
    uint16_t root_base = gc_rootsp;
    if (arguments == NIL) {
        fprintf(stderr, "manifest-vm: malformed %s surface arguments\n", label);
        return 0;
    }
    GC_PUSH(arguments);
    lisp65_error_clear();
    vm_status = VM_OK;
    lisp_toplevel_active = 1;
    if (setjmp(lisp_toplevel) != 0) {
        lisp_toplevel_active = 0;
        fprintf(stderr, "manifest-vm: %s surface aborted code=%u\n", label,
                (unsigned)lisp65_error_pending_code());
        return 0;
    }
    result = vm_native_apply(function, gc_rootstack[GC_TOP]);
    lisp_toplevel_active = 0;
    gc_rootsp = root_base;
    if (vm_status != VM_OK || result != MKFIX(42)) {
        fprintf(stderr, "manifest-vm: %s surface got status=%u value=%d\n",
                label, (unsigned)vm_status,
                IS_FIX(result) ? (int)FIXVAL(result) : -32768);
        return 0;
    }
    printf("surface:%s=42\n", label);
    return 1;
}

static char *read_source(const char *path) {
    FILE *stream = fopen(path, "rb");
    long length;
    char *source;
    if (!stream || fseek(stream, 0, SEEK_END) != 0 ||
        (length = ftell(stream)) < 0 || length > 4096 ||
        fseek(stream, 0, SEEK_SET) != 0) {
        if (stream) fclose(stream);
        return NULL;
    }
    source = (char *)malloc((size_t)length + 1u);
    if (!source || fread(source, 1, (size_t)length, stream) != (size_t)length) {
        free(source);
        fclose(stream);
        return NULL;
    }
    source[length] = '\0';
    fclose(stream);
    return source;
}

int main(int argc, char **argv) {
    char *source;
    obj argument, function, call_args[1];
    int directory_index;

    if (argc != 2) {
        fprintf(stderr, "usage: %s source.lisp\n", argv[0]);
        return 2;
    }
    source = read_source(argv[1]);
    if (!source) {
        fprintf(stderr, "manifest-vm: cannot read source\n");
        return 2;
    }
    eval_init();
    if (!load_manifest_artifact()) {
        fprintf(stderr, "manifest-vm: artifact materialization failed\n");
        free(source);
        return 3;
    }
    if (!run_surface_case("eval-direct", "eval", "((+ 40 2))") ||
        !run_surface_case("funcall-eval", "funcall", "(eval (+ 40 2))") ||
        !run_surface_case("apply-eval", "apply", "(eval ((+ 40 2)))")) {
        free(source);
        return 1;
    }
    argument = quoted_argument(source);
    free(source);
    if (argument == NIL) {
        fprintf(stderr, "manifest-vm: source is not the pinned lcc-compile-obj form\n");
        return 2;
    }
    function = sym_function(intern("lcc-compile-obj"));
    if (!IS_BCODE(function)) {
        fprintf(stderr, "manifest-vm: lcc-compile-obj is not resident bytecode\n");
        return 3;
    }
    directory_index = (int)BCODE_IDX(function);
    GC_PUSH(argument);
    call_args[0] = gc_rootstack[GC_TOP];
    lisp65_error_clear();
    lisp_toplevel_active = 1;
    if (setjmp(lisp_toplevel) == 0) {
        vm_status = VM_OK;
        (void)vm_run_dir(directory_index, call_args, 1);
        lisp_toplevel_active = 0;
        GC_POPN(1);
        fprintf(stderr, "manifest-vm: invalid parameter list returned normally status=%u\n",
                (unsigned)vm_status);
        return 1;
    }
    lisp_toplevel_active = 0;
    if (lisp65_error_pending_code() != LISP65_ERR_LCC_INVALID_PARAMETER_LIST ||
        !is_symbol(lisp65_error_pending_symbol()) ||
        strcmp(symname(lisp65_error_pending_symbol()),
               "%lcc-error-invalid-parameter-list") != 0) {
        fprintf(stderr, "manifest-vm: wrong structured error code=%u symbol=%s\n",
                (unsigned)lisp65_error_pending_code(),
                is_symbol(lisp65_error_pending_symbol())
                    ? symname(lisp65_error_pending_symbol()) : "<none>");
        return 1;
    }
    puts("!error:code=59:symbol=%lcc-error-invalid-parameter-list");
    return 0;
}
