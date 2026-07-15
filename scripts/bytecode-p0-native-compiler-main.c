/* Native C-compiler adapter for tests/bytecode/p0-golden-vectors.json. */
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include "compile.h"
#include "mem.h"
#include "reader.h"
#include "symbol.h"
#include "bytecode-p0-native-compile-vectors.h"

#define NATIVE_FN_CAP 16
#define NATIVE_CODE_CAP 1024
#define NATIVE_LIT_CAP 64
#define NO_LITERAL_OVERRIDE 0xffffu

static bc_func functions[NATIVE_FN_CAP];
static uint8_t code[NATIVE_FN_CAP][NATIVE_CODE_CAP];
static obj literals[NATIVE_FN_CAP][NATIVE_LIT_CAP];

static void init_unit(bc_unit *unit) {
    uint8_t index;
    unit->fn = functions;
    unit->fncap = NATIVE_FN_CAP;
    unit->nfn = 0;
    unit->gensym = 0;
    unit->err = 0;
    for (index = 0; index < NATIVE_FN_CAP; index++) {
        functions[index].code = code[index];
        functions[index].codecap = NATIVE_CODE_CAP;
        functions[index].lit = literals[index];
        functions[index].litcap = NATIVE_LIT_CAP;
    }
}

static int is_symbol(obj value) {
    return IS_SYMI(value) || (IS_PTR(value) && cell_type(value) == T_SYM);
}

static int match_literal(obj actual, uint16_t node_index, uint8_t depth) {
    const bc_native_lit_node *node;
    uint16_t index;
    obj cursor;
    if (depth >= 64) return 0;
    node = &bc_native_lit_nodes[node_index];
    switch (node->kind) {
    case BC_NATIVE_FIX:
        return IS_FIX(actual) && FIXVAL(actual) == node->value;
    case BC_NATIVE_NIL:
        return actual == NIL;
    case BC_NATIVE_T:
        return actual == intern("t");
    case BC_NATIVE_SYMBOL:
        return is_symbol(actual) && strcmp(symname(actual), node->name) == 0;
    case BC_NATIVE_CONS:
        return node->count == 2 && IS_PTR(actual) && cell_type(actual) == T_CONS
            && match_literal(cell_a(actual), bc_native_lit_index[node->first], (uint8_t)(depth + 1))
            && match_literal(cell_b(actual), bc_native_lit_index[node->first + 1], (uint8_t)(depth + 1));
    case BC_NATIVE_LIST:
        cursor = actual;
        for (index = 0; index < node->count; index++) {
            if (!IS_PTR(cursor) || cell_type(cursor) != T_CONS
                || !match_literal(
                    cell_a(cursor), bc_native_lit_index[node->first + index],
                    (uint8_t)(depth + 1))) return 0;
            cursor = cell_b(cursor);
        }
        return cursor == NIL;
    case BC_NATIVE_STRING:
        if (!IS_PTR(actual) || cell_type(actual) != T_STR) return 0;
        cursor = cell_a(actual);
        for (index = 0; index < node->count; index++) {
            if (!IS_PTR(cursor) || cell_type(cursor) != T_CONS
                || !match_literal(
                    cell_a(cursor), bc_native_lit_index[node->first + index],
                    (uint8_t)(depth + 1))) return 0;
            cursor = cell_b(cursor);
        }
        return cursor == NIL;
    default:
        return 0;
    }
}

static bc_func *compile_vector(const bc_native_compile_vector *vector, bc_unit *unit) {
    const char *cursor = vector->source;
    obj form = read_expr(&cursor);
    init_unit(unit);
    if (vector->target == BC_NATIVE_TARGET_LAMBDA_HELPER) {
        bc_compile_top(unit, form);
        if (unit->err || unit->nfn < 2) return 0;
        return &unit->fn[1];
    }
    if (vector->target == BC_NATIVE_TARGET_DEFUN) {
        obj rest;
        if (!IS_PTR(form) || cell_type(form) != T_CONS
            || cell_a(form) != intern("defun")) return 0;
        rest = cell_b(form);
        if (!IS_PTR(rest) || cell_type(rest) != T_CONS
            || cell_a(rest) != intern(vector->entry)) return 0;
        rest = cell_b(rest);
        if (!IS_PTR(rest) || cell_type(rest) != T_CONS) return 0;
        bc_compile_defun(unit, cell_a(rest), cell_b(rest));
        if (unit->err || unit->nfn < 1) return 0;
        return &unit->fn[0];
    }
    return 0;
}

static int compare_compiled(
    const bc_native_compile_vector *vector,
    const uint8_t *header,
    const uint8_t *payload,
    uint16_t literal_override,
    int quiet
) {
    bc_unit unit;
    bc_func *function = compile_vector(vector, &unit);
    uint8_t assembled[7 + 2 * NATIVE_LIT_CAP + NATIVE_CODE_CAP];
    uint16_t assembled_len, payload_offset;
    uint8_t index;
    if (!function) {
        if (!quiet) fprintf(stderr, "native-compiler: %s compile failed\n", vector->name);
        return 1;
    }
    assembled_len = bc_assemble(function, assembled, sizeof assembled);
    payload_offset = (uint16_t)(7 + 2 * function->nlit);
    if (!assembled_len || assembled_len != payload_offset + vector->payload_len) {
        if (!quiet) fprintf(
            stderr,
            "native-compiler: %s assembled length mismatch got=%u nlit=%u code=%u "
            "want=%u nlit=%u payload=%u\n",
            vector->name, assembled_len, function->nlit, function->codelen,
            (unsigned)(7 + 2 * vector->nlit + vector->payload_len),
            vector->nlit, vector->payload_len);
        if (!quiet) {
            uint16_t dump;
            fputs("native-compiler: actual payload:", stderr);
            for (dump = 0; dump < function->codelen; dump++)
                fprintf(stderr, " %02x", function->code[dump]);
            fputc('\n', stderr);
        }
        return 1;
    }
    if (memcmp(assembled, header, 7) != 0) {
        if (!quiet) fprintf(stderr, "native-compiler: %s header mismatch\n", vector->name);
        return 1;
    }
    if (memcmp(assembled + payload_offset, payload, vector->payload_len) != 0) {
        if (!quiet) fprintf(stderr, "native-compiler: %s payload mismatch\n", vector->name);
        return 1;
    }
    if (function->nlit != vector->nlit) {
        if (!quiet) fprintf(stderr, "native-compiler: %s literal count mismatch\n", vector->name);
        return 1;
    }
    for (index = 0; index < function->nlit; index++) {
        uint16_t root = bc_native_lit_index[vector->lit_first + index];
        if (index == 0 && literal_override != NO_LITERAL_OVERRIDE) root = literal_override;
        if (!match_literal(function->lit[index], root, 0)) {
            if (!quiet) fprintf(stderr, "native-compiler: %s literal %u mismatch\n", vector->name, index);
            return 1;
        }
    }
    return 0;
}

static int check_rel8_reject(void) {
    const char *cursor = bc_native_rel8_source;
    obj form = read_expr(&cursor);
    bc_unit unit;
    init_unit(&unit);
    bc_compile_top(&unit, form);
    if (!unit.err || unit.nfn < 2 || unit.fn[1].codelen <= 128
        || unit.fn[1].codelen >= unit.fn[1].codecap
        || unit.fn[1].nlit >= unit.fn[1].litcap) {
        fprintf(stderr, "native-compiler: Rel8 overflow was not a non-capacity reject (%s)\n",
                bc_native_rel8_error);
        return 1;
    }
    return 0;
}

static int mutation_tests(void) {
    const bc_native_compile_vector *vector =
        &bc_native_compile_vectors[BC_NATIVE_MUTATION_VECTOR];
    uint8_t header[7];
    uint8_t payload[NATIVE_CODE_CAP];
    if (compare_compiled(vector, vector->header, vector->payload, NO_LITERAL_OVERRIDE, 1)) {
        fprintf(stderr, "native-compiler: mutation baseline failed\n");
        return 1;
    }
    memcpy(header, vector->header, sizeof header);
    header[1] ^= 1;
    if (!compare_compiled(vector, header, vector->payload, NO_LITERAL_OVERRIDE, 1)) {
        fprintf(stderr, "native-compiler: header mutation escaped\n");
        return 1;
    }
    memcpy(payload, vector->payload, vector->payload_len);
    payload[0] ^= 1;
    if (!compare_compiled(vector, vector->header, payload, NO_LITERAL_OVERRIDE, 1)) {
        fprintf(stderr, "native-compiler: payload mutation escaped\n");
        return 1;
    }
    if (!compare_compiled(
            vector, vector->header, vector->payload,
            BC_NATIVE_MUTATION_WRONG_LITERAL_ROOT, 1)) {
        fprintf(stderr, "native-compiler: semantic literal mutation escaped\n");
        return 1;
    }
    return 0;
}

int main(void) {
    uint16_t index;
    mem_init();
    for (index = 0; index < BC_NATIVE_GLOBAL_SYMBOL_COUNT; index++)
        (void)intern(bc_native_global_symbols[index]);
    (void)intern("native-pointer-noise");
    for (index = 0; index < BC_NATIVE_COMPILE_VECTOR_COUNT; index++) {
        const bc_native_compile_vector *vector = &bc_native_compile_vectors[index];
        if (compare_compiled(
                vector, vector->header, vector->payload,
                NO_LITERAL_OVERRIDE, 0)) return 1;
    }
    if (check_rel8_reject() || mutation_tests()) return 1;
    printf("native-compiler-golden: PASS positive=%u negative=1 mutations=3\n",
           (unsigned)BC_NATIVE_COMPILE_VECTOR_COUNT);
    return 0;
}
