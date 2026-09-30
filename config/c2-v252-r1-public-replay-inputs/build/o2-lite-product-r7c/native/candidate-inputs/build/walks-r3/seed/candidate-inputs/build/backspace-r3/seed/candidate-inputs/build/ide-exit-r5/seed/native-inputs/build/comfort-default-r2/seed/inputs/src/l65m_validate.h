/* Pointer-free L65M disk-library validation contract. */
#ifndef LISP65_L65M_VALIDATE_H
#define LISP65_L65M_VALIDATE_H

#include <stdint.h>

#define L65M_HEADER_SIZE 38u
#define L65M_MAX_GRAPH_DEPTH 9u

typedef enum {
    L65M_OK = 0,
    L65M_ERR_ARGUMENT = 1,
    L65M_ERR_SOURCE = 2,
    L65M_ERR_CONTAINER = 3,
    L65M_ERR_HEADER = 4,
    L65M_ERR_SECTIONS = 5,
    L65M_ERR_STRINGS = 6,
    L65M_ERR_ENTRIES = 7,
    L65M_ERR_CODE = 8,
    L65M_ERR_INDEX = 9,
    L65M_ERR_NODE = 10,
    L65M_ERR_GRAPH = 11,
    L65M_ERR_PATCH = 12,
    L65M_ERR_REGION = 13,
    L65M_ERR_DIRECTORY = 14,
    L65M_ERR_SYMBOLS = 15,
    L65M_ERR_NAMEPOOL = 16,
    L65M_ERR_HEAP = 17,
    L65M_ERR_ARENA = 18,
    L65M_ERR_ROOTS = 19,
    L65M_ERR_STATE = 20
} l65m_status;

typedef uint8_t (*l65m_read_fn)(void *ctx, uint16_t off, uint8_t *dst, uint16_t len);
typedef uint8_t (*l65m_symbol_exists_fn)(void *ctx, const char *name);

/* The source is the complete [u16 blob_len][u16 md_len][blob][L65M] file. */
typedef struct {
    l65m_read_fn read;
    void *ctx;
    uint16_t length;
} l65m_source;

typedef struct {
    uint16_t dir_count, dir_capacity;
    uint16_t symbol_count, symbol_capacity;
    uint16_t namepool_used, namepool_capacity;
    uint16_t heap_free;
    uint16_t arena_used, arena_capacity;
    uint16_t roots_used, roots_capacity;
    uint8_t string_arena;
    l65m_symbol_exists_fn symbol_exists;
    void *symbol_ctx;
} l65m_limits;

/* Public and deliberately pointer-free: tests and the commit pass can bind the exact preflight. */
typedef struct {
    uint16_t source_length;
    uint16_t source_crc16;
    uint16_t source_blob_off, source_metadata_off;
    uint16_t code_base, blob_len, metadata_len;
    uint16_t entry_count, index_count, node_count, patch_count;
    uint16_t entries_off, index_off, nodes_off, patches_off;
    uint16_t strings_off, strings_bytes;
    uint16_t dir_before, dir_after;
    uint16_t symbols_before, namepool_before;
    uint16_t heap_free_before, arena_used_before, roots_before;
    uint16_t new_symbols, new_name_bytes;
    uint16_t heap_cells, arena_bytes;
    uint8_t root_slots, max_graph_depth;
    uint8_t format_version;
} l65m_plan;

l65m_status l65m_probe(const l65m_source *source,
                       uint16_t *blob_len, uint16_t *metadata_len);
l65m_status l65m_validate(const l65m_source *source, uint16_t code_base,
                          const l65m_limits *limits, l65m_plan *plan);

#endif /* LISP65_L65M_VALIDATE_H */
