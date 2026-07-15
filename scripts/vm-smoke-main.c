/* Host smoke for src/vm.c against tests/bytecode P0 golden vectors. */
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include "mem.h"
#include "symbol.h"
#include "vm.h"
#ifdef LISP65_SCREEN_DRIVER
#include "screen.h"
#endif
#include "bytecode-p0-vectors.h"

static uint8_t code_buf[BC_P0_MAX_CODE_LEN];
static uint8_t code_store[BC_P0_MAX_CODE_LEN];

void vm_code_load(uint8_t bank, uint16_t off, uint16_t len, uint8_t *dst) {
    (void)bank;
    memcpy(dst, code_store + off, len);
}

static obj make_arg(uint16_t idx) {
    const bc_p0_arg_node *n = &bc_p0_arg_nodes[idx];
    switch (n->kind) {
    case BC_ARG_FIX:
        return MKFIX(n->value);
    case BC_ARG_NIL:
        return NIL;
    case BC_ARG_T:
        return intern("t");
    case BC_ARG_SYMBOL:
        return intern(n->name);
    case BC_ARG_CONS: {
        obj a = make_arg(bc_p0_arg_index[n->first]);
        obj b;
        GC_PUSH(a);
        b = make_arg(bc_p0_arg_index[n->first + 1]);
        a = gc_rootstack[GC_TOP];
        GC_POPN(1);
        return cons(a, b);
    }
    case BC_ARG_LIST: {
        obj out = NIL;
        uint16_t i;
        for (i = n->count; i > 0; i--) {
            obj item;
            GC_PUSH(out);
            item = make_arg(bc_p0_arg_index[n->first + i - 1]);
            out = cons(item, gc_rootstack[GC_TOP]);
            GC_POPN(1);
        }
        return out;
    }
    case BC_ARG_STRING: {
        obj chars = NIL;
        obj s;
        uint16_t i;
        for (i = n->count; i > 0; i--) {
            obj item;
            GC_PUSH(chars);
            item = make_arg(bc_p0_arg_index[n->first + i - 1]);
            chars = cons(item, gc_rootstack[GC_TOP]);
            GC_POPN(1);
        }
        GC_PUSH(chars);
        s = alloc(T_STR);
        chars = gc_rootstack[GC_TOP];
        GC_POPN(1);
        cell_set_a(s, chars);
        cell_set_b(s, NIL);
        return s;
    }
    default:
        return NIL;
    }
}

static int obj_equal(obj a, obj b) {
    uint8_t ta, tb;
    if (a == b) return 1;
    if (!IS_PTR(a) || !IS_PTR(b)) return 0;
    ta = cell_type(a);
    tb = cell_type(b);
    if (ta != tb) return 0;
    if (ta == T_CONS) return obj_equal(cell_a(a), cell_a(b)) && obj_equal(cell_b(a), cell_b(b));
    if (ta == T_STR) return obj_equal(cell_a(a), cell_a(b));
    if (ta == T_SYM) return strcmp(symname(a), symname(b)) == 0;
    return 0;
}

static int run_vector(const bc_p0_vector *v) {
    obj args[VM_MAXARGS];
    uint16_t base = gc_rootsp;
    uint8_t i;
    obj got, expect;

    if (v->argc > VM_MAXARGS) {
        fprintf(stderr, "vm-smoke: FAIL %s: argc %u > VM_MAXARGS\n", v->name, v->argc);
        return 1;
    }
    if (v->code_len > sizeof(code_buf)) {
        fprintf(stderr, "vm-smoke: FAIL %s: code object too large\n", v->name);
        return 1;
    }

    memcpy(code_buf, v->code, v->code_len);
#ifdef LISP65_DIALECT_V2
    code_buf[CO_OFF_FLAGS] |= CO_FLAG_STRICT_ARITY;
#endif
    for (i = 0; i < v->nlits; i++) {
        obj lit = make_arg(bc_p0_arg_index[v->lit_first + i]);
        uint16_t raw = (uint16_t)lit;
        uint16_t off = (uint16_t)(7 + 2 * i);
        code_buf[off] = (uint8_t)(raw & 0xff);
        code_buf[off + 1] = (uint8_t)(raw >> 8);
    }
    memcpy(code_store, code_buf, v->code_len);

    vm_dir_reset();
    if (v->entry) {
        /* Mirror the product contract in eval.c vm_register_embedded: store the
         * directory index as a BCODE immediate in the function cell. */
        obj sym = intern(v->entry);
        int di = vm_dir_add(sym, 0, 0, v->code_len);
        if (di < 0) {
            fprintf(stderr, "vm-smoke: FAIL %s: directory full\n", v->name);
            return 1;
        }
        set_sym_function(sym, MK_BCODE(di));
    }

    for (i = 0; i < v->argc; i++) {
        args[i] = make_arg(bc_p0_arg_index[v->arg_first + i]);
        GC_PUSH(args[i]);
    }
    gc_rootsp = base;

    got = vm_run(0, 0, v->code_len, args, v->argc);
    if (vm_status != VM_OK) {
        fprintf(stderr, "vm-smoke: FAIL %s: vm_status=%u\n", v->name, vm_status);
        return 1;
    }
    expect = make_arg(v->expect_node);
    if (!obj_equal(got, expect)) {
        fprintf(stderr, "vm-smoke: FAIL %s: expected obj=$%04x got=$%04x\n",
                v->name, (uint16_t)expect, (uint16_t)got);
        return 1;
    }
    return 0;
}

static int run_bad_opcode_diag(void) {
    static const uint8_t bad_code[] = {
        CO_MAGIC, 0, 0,
#ifdef LISP65_DIALECT_V2
        CO_FLAG_STRICT_ARITY,
#else
        0,
#endif
        1, 0, 0, 0xff
    };
    const char *msg;

    memcpy(code_store, bad_code, sizeof(bad_code));
    vm_dir_reset();
    if (vm_dir_add(intern("badop"), 0, 0, sizeof(bad_code)) < 0) {
        fprintf(stderr, "vm-smoke: FAIL bad-opcode-diag: directory full\n");
        return 1;
    }
    (void)vm_run_dir(0, NULL, 0);
    if (vm_status != VM_BADOPCODE) {
        fprintf(stderr, "vm-smoke: FAIL bad-opcode-diag: vm_status=%u\n", vm_status);
        return 1;
    }
    msg = vm_status_message();
    if (!strstr(msg, "bad bytecode") || !strstr(msg, "pc=$0000") ||
        !strstr(msg, "op=$ff") || !strstr(msg, "fn=")) {
        fprintf(stderr, "vm-smoke: FAIL bad-opcode-diag: message=%s\n", msg);
        return 1;
    }
    return 0;
}

static int arity_case(uint8_t nargs, uint8_t nlocals, uint8_t flags,
                      uint8_t actual, uint8_t expected_status) {
    static const uint8_t payload[] = { OP_PUSHARG0, OP_RET };
    obj args[4] = { MKFIX(1), MKFIX(2), MKFIX(3), MKFIX(4) };
    uint8_t code[] = {
        CO_MAGIC, 0, 0, 0, sizeof payload, 0, 0,
        OP_PUSHARG0, OP_RET
    };
    code[CO_OFF_NARGS] = nargs;
    code[CO_OFF_NLOCS] = nlocals;
    code[CO_OFF_FLAGS] = flags;
    memcpy(code_store, code, sizeof code);
    vm_status = VM_OK;
    (void)vm_run(0, 0, sizeof code, args, actual);
    if (vm_status != expected_status) {
        fprintf(stderr,
                "vm-smoke: FAIL strict-arity nargs=%u flags=%u actual=%u status=%u expected=%u\n",
                nargs, flags, actual, vm_status, expected_status);
        return 1;
    }
    return 0;
}

static int run_arity_contract(void) {
#ifdef LISP65_DIALECT_V2
    uint8_t strict = CO_FLAG_STRICT_ARITY;
    uint8_t optional = CO_ARITY_FLAGS(2, 0);
    uint8_t rest = CO_ARITY_FLAGS(0, 1);
    if (arity_case(2, 0, strict, 1, VM_ARITY) ||
        arity_case(2, 0, strict, 2, VM_OK) ||
        arity_case(2, 0, strict, 3, VM_ARITY) ||
        arity_case(3, 0, optional, 0, VM_ARITY) ||
        arity_case(3, 0, optional, 1, VM_OK) ||
        arity_case(3, 0, optional, 3, VM_OK) ||
        arity_case(3, 0, optional, 4, VM_ARITY) ||
        arity_case(1, 1, rest, 0, VM_ARITY) ||
        arity_case(1, 1, rest, 3, VM_OK) ||
        arity_case(2, 0, 0, 1, VM_BADOPCODE) ||
        arity_case(2, 0, 0, 3, VM_BADOPCODE) ||
        arity_case(1, 0, (uint8_t)(1u << CO_FLAG_OPTIONAL_SHIFT), 1,
                   VM_BADOPCODE) ||
        arity_case(1, 0, CO_ARITY_FLAGS(0, 1), 1, VM_BADOPCODE))
        return 1;
    if (vm_status_error_code(VM_ARITY) != LISP65_ERR_WRONG_ARGUMENT_COUNT) {
        fprintf(stderr, "vm-smoke: FAIL strict-arity error-code binding\n");
        return 1;
    }
    return 0;
#else
    if (arity_case(2, 0, 0, 1, VM_OK) ||
        arity_case(2, 0, 0, 3, VM_OK))
        return 1;
    return 0;
#endif
}

int main(void) {
    unsigned i;

    mem_init();
    vm_init();
#ifdef LISP65_SCREEN_DRIVER
    scr_init();
#endif
    for (i = 0; i < BC_P0_GLOBAL_SYMBOL_COUNT; i++) {
        (void)intern(bc_p0_global_symbols[i]);
    }

    for (i = 0; i < BC_P0_VECTOR_COUNT; i++) {
        if (run_vector(&bc_p0_vectors[i])) return 1;
    }
    if (run_bad_opcode_diag()) return 1;
    if (run_arity_contract()) return 1;
    printf("vm-smoke: PASS=%u OMITTED=%u FAIL=0 strict_arity_cases=%u\n",
           (unsigned)(BC_P0_VECTOR_COUNT + 2), (unsigned)BC_P0_OMISSION_COUNT,
#ifdef LISP65_DIALECT_V2
           13u);
#else
           0u);
#endif
    return 0;
}
