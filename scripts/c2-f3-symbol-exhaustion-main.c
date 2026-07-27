/* F3 host fixture: exact product symbol capacities at an open append seam.
 *
 * The allocator implementation is src/symbol.c itself, compiled with the
 * Link-57 MAX_SYM/NAMEPOOL values and the product's EXT access seams.  The
 * transaction arrays are a deliberately small seam model; the permanent
 * append-plan/rollback gate separately binds the real product control flow.
 */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "interrupt.h"
#include "symbol.h"

#ifndef MAX_SYM
#error "F3 requires the product MAX_SYM"
#endif
#ifndef NAMEPOOL
#error "F3 requires the product NAMEPOOL"
#endif

#define C2D_REGION_BYTES 50816u
#define C2J_OFFSET       50752u
#define C2J_BYTES        64u

static uint16_t nameoff_ext[MAX_SYM];
static obj symval_ext[MAX_SYM];
static obj symfn_ext[MAX_SYM];
static char sympool_ext[NAMEPOOL];

static uint8_t c2d[C2D_REGION_BYTES];
static uint8_t c2d_before[C2D_REGION_BYTES];
static obj export_cells[4];
static obj export_before[4];
static lisp65_error_code observed_error;
static unsigned abort_calls;

jmp_buf lisp_toplevel;
int lisp_toplevel_active;
const char *lisp_error_msg;

uint16_t nameoff_get(uint16_t i) { return nameoff_ext[i]; }
void nameoff_set(uint16_t i, uint16_t value) { nameoff_ext[i] = value; }
obj symval_get(uint16_t i) { return symval_ext[i]; }
void symval_set(uint16_t i, obj value) { symval_ext[i] = value; }
obj symfn_ext_get(uint16_t i) { return symfn_ext[i]; }
void symfn_ext_set(uint16_t i, obj value) { symfn_ext[i] = value; }

void sympool_read(uint16_t off, char *dst, uint16_t len) {
    uint16_t i;
    for (i = 0; i < len; ++i)
        dst[i] = (uint16_t)(off + i) < NAMEPOOL
            ? sympool_ext[(uint16_t)(off + i)] : 0;
}

void sympool_write(uint16_t off, const char *src, uint16_t len) {
    memcpy(sympool_ext + off, src, len);
}

void lisp_abort_code(lisp65_error_code code) {
    observed_error = code;
    ++abort_calls;
}

void lisp_abort_symbol(lisp65_error_code code, obj symbol) {
    (void)symbol;
    lisp_abort_code(code);
}

void lisp_abort(const char *message) {
    (void)message;
    observed_error = LISP65_ERR_TOO_MANY_SYMBOLS;
    ++abort_calls;
}

static void die(const char *message) {
    fprintf(stderr, "c2-f3-symbol-exhaustion: FAIL %s\n", message);
    exit(1);
}

static void fill_symbol_slots(void) {
    char name[16];
    uint16_t i;
    for (i = 0; i < MAX_SYM; ++i) {
        snprintf(name, sizeof name, "s%04u", (unsigned)i);
        if (intern(name) == NIL) die("symbol-slot setup failed");
    }
    if (sym_count() != MAX_SYM || sym_pool_used() >= NAMEPOOL)
        die("symbol-slot capacity was not isolated");
}

static void fill_name_pool(void) {
    char name[20];
    uint16_t i;
    const uint16_t names = (uint16_t)(NAMEPOOL / 16u);
    if ((uint16_t)(names * 16u) != NAMEPOOL || names >= MAX_SYM)
        die("name-pool fixture arithmetic drift");
    for (i = 0; i < names; ++i) {
        snprintf(name, sizeof name, "n%014u", (unsigned)i);
        if (strlen(name) != 15u || intern(name) == NIL)
            die("name-pool setup failed");
    }
    if (sym_count() != names || sym_pool_used() != NAMEPOOL)
        die("name-pool capacity was not isolated");
}

static void prepare_append_state(uint8_t transient) {
    uint16_t i;
    for (i = 0; i < C2D_REGION_BYTES; ++i)
        c2d[i] = (uint8_t)(i * 29u + 7u);
    memset(c2d + C2J_OFFSET, 0, C2J_BYTES);
    export_cells[0] = MK_SYMI(1);
    export_cells[1] = MK_BCODE(7);
    export_cells[2] = MKFIX(23);
    export_cells[3] = NIL;
    memcpy(c2d_before, c2d, sizeof c2d);
    memcpy(export_before, export_cells, sizeof export_cells);

    /* Representative writes already made when publish-name is entered. */
    c2d[C2J_OFFSET + 0] = 'C';
    c2d[C2J_OFFSET + 1] = '2';
    c2d[C2J_OFFSET + 2] = 'J';
    c2d[C2J_OFFSET + 3] = 1u;
    c2d[C2J_OFFSET + 4] = transient ? 2u : 1u;
    if (transient) {
        c2d[50000] ^= 0x5au;
        c2d[50001] ^= 0xa5u;
    } else {
        c2d[34000] ^= 0x5au;
        c2d[34001] ^= 0xa5u;
    }
}

static void rollback_append(void) {
    memcpy(c2d, c2d_before, sizeof c2d);
    memcpy(export_cells, export_before, sizeof export_cells);
}

int main(int argc, char **argv) {
    const char *resource;
    const char *append;
    uint8_t transient;
    uint16_t symbols_before, pool_before;
    obj result;

    if (argc != 3) die("usage: <symbol-slots|name-pool> <persistent|transient>");
    resource = argv[1];
    append = argv[2];
    transient = (uint8_t)(strcmp(append, "transient") == 0);
    if (!transient && strcmp(append, "persistent") != 0)
        die("unknown append kind");
    if (strcmp(resource, "symbol-slots") == 0)
        fill_symbol_slots();
    else if (strcmp(resource, "name-pool") == 0)
        fill_name_pool();
    else
        die("unknown resource");

    symbols_before = sym_count();
    pool_before = sym_pool_used();
    prepare_append_state(transient);
    result = intern("f3-overflow");
    if (result != NIL || observed_error != LISP65_ERR_TOO_MANY_SYMBOLS
        || abort_calls != 1u)
        die("allocator did not report TOO_MANY_SYMBOLS exactly once");
    rollback_append();
    if (sym_count() != symbols_before || sym_pool_used() != pool_before)
        die("failed intern changed allocator counters");
    if (memcmp(c2d, c2d_before, sizeof c2d))
        die("C2D rollback is not byte-identical");
    if (memcmp(c2d + C2J_OFFSET, c2d_before + C2J_OFFSET, C2J_BYTES))
        die("C2J rollback is not byte-identical");
    if (memcmp(export_cells, export_before, sizeof export_cells))
        die("export rollback is not byte-identical");

    printf(
        "{\"resource\":\"%s\",\"append\":\"%s\","
        "\"error_code\":%u,\"symbols_before\":%u,\"symbols_after\":%u,"
        "\"symbol_capacity\":%u,\"pool_before\":%u,\"pool_after\":%u,"
        "\"pool_capacity\":%u,\"c2d_byte_identical\":true,"
        "\"c2j_byte_identical\":true,\"export_cells_byte_identical\":true}\n",
        resource, append, (unsigned)observed_error,
        (unsigned)symbols_before, (unsigned)sym_count(), (unsigned)MAX_SYM,
        (unsigned)pool_before, (unsigned)sym_pool_used(), (unsigned)NAMEPOOL);
    return 0;
}
