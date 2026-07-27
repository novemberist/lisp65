#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

enum {
    SCRATCH_BYTES = 304,
    TRACE_OFFSET = 302,
    TRACE_BYTES = 2
};

typedef uint16_t obj;

typedef struct {
    uint8_t kind;
    uint16_t arg0;
    uint32_t arg1;
} __attribute__((packed)) descriptor;

typedef struct {
    obj cdr_value;
    uint16_t car_ordinal;
    uint8_t state;
} __attribute__((packed)) literal_frame;

typedef struct {
    uint16_t code_cursor;
    uint16_t entry_count;
    uint16_t literal_count;
    uint16_t string_bytes;
    uint8_t active;
    uint8_t failed;
} __attribute__((packed)) session_state;

typedef struct {
    obj cursor, helper, export_name, function;
    obj literals, literal_walk, code, literal_current;
    union {
        uint16_t function_count;
        uint16_t final_length;
    };
    uint16_t local;
    uint16_t literal_count;
    union {
        uint16_t literal_index;
        uint16_t code_start;
    };
    uint16_t code_count, first, name_off;
    uint8_t export_flags, nargs, nlocals, flags, is_main;
    uint8_t literal_depth, literal_have, literal_done, literal_atom_pending;
    descriptor literal_result;
    literal_frame literal_stack[49];
    uint8_t status;
    session_state session;
} __attribute__((packed)) work_state;

_Static_assert(sizeof(session_state) == 10, "session geometry");
_Static_assert(sizeof(work_state) == TRACE_OFFSET, "scratch geometry");

typedef enum {
    PH_RESET,
    PH_ADD,
    PH_LITERAL,
    PH_CODE,
    PH_FINAL
} phase;

static uint8_t scratch[SCRATCH_BYTES];
static work_state *const work = (work_state *)(void *)scratch;
static phase current;

static void reject_unless(int condition, const char *name) {
    if (!condition) {
        fprintf(stderr, "rejected:%s\n", name);
        exit(2);
    }
}

static void enter_add(uint16_t functions) {
    reject_unless(current == PH_RESET || current == PH_CODE, "add-lifetime");
    current = PH_ADD;
    work->function_count = functions;
}

static void enter_literal(uint16_t index) {
    reject_unless(current == PH_ADD, "literal-lifetime");
    current = PH_LITERAL;
    work->literal_index = index;
}

static void enter_code(uint16_t start) {
    reject_unless(current == PH_LITERAL, "code-lifetime");
    current = PH_CODE;
    work->code_start = start;
}

static void enter_final(uint16_t length) {
    reject_unless(current == PH_CODE, "final-lifetime");
    current = PH_FINAL;
    work->final_length = length;
}

static void verify_session(const session_state *expected) {
    reject_unless(
        memcmp(&work->session, expected, sizeof *expected) == 0,
        "session-clobber");
    reject_unless(
        scratch[TRACE_OFFSET] == 0x5a && scratch[TRACE_OFFSET + 1] == 0xa5,
        "trace-clobber");
}

int main(int argc, char **argv) {
    session_state expected = {
        0x0040, 7, 11, 13, 1, 0
    };
    memset(scratch, 0, sizeof scratch);
    memcpy(&work->session, &expected, sizeof expected);
    scratch[TRACE_OFFSET] = 0x5a;
    scratch[TRACE_OFFSET + 1] = 0xa5;
    current = PH_RESET;

    if (argc == 2 && !strcmp(argv[1], "final-before-add-end")) {
        enter_add(3);
        enter_final(0x1234);
    } else if (argc == 2 && !strcmp(argv[1], "code-before-literal-end")) {
        enter_add(3);
        enter_code(0x4567);
    } else if (argc == 2 && !strcmp(argv[1], "function-after-final")) {
        enter_add(3);
        enter_literal(0);
        enter_code(0x4567);
        enter_final(0x1234);
        enter_add(4);
    } else if (argc == 2 && !strcmp(argv[1], "literal-after-code")) {
        enter_add(3);
        enter_literal(0);
        enter_code(0x4567);
        enter_literal(1);
    } else {
        enter_add(3);
        enter_literal(0);
        enter_code(0x4567);
        verify_session(&expected);
        enter_add(2);
        enter_literal(0);
        enter_code(0x4789);
        enter_final(0x1234);
        verify_session(&expected);
        puts("c2-emitter-work-state-union: PASS");
    }
    return 0;
}
