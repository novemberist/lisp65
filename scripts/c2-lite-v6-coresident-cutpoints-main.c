#include <stdint.h>
#include <stdio.h>

enum {
    OK = 0,
    ERR = 1,
    CRC_DONE = 0x43,
    EXPORTS_PROVED = 0x51
};

typedef struct {
    uint8_t crc_metadata;
    uint8_t publish_exports;
    uint8_t published_cells;
} fused_cutpoints;

static uint8_t crc_half(fused_cutpoints *c) {
    if (!c || c->crc_metadata) return ERR;
    c->crc_metadata = CRC_DONE;
    return OK;
}

static uint8_t metadata_half(fused_cutpoints *c) {
    if (!c || c->crc_metadata != CRC_DONE) return ERR;
    c->crc_metadata = 0;
    return OK;
}

static uint8_t export_preflight_half(fused_cutpoints *c) {
    if (!c || c->publish_exports || c->published_cells) return ERR;
    c->publish_exports = EXPORTS_PROVED;
    return OK;
}

static uint8_t export_cells_half(fused_cutpoints *c) {
    if (!c || c->publish_exports != EXPORTS_PROVED || c->published_cells)
        return ERR;
    c->published_cells = 1;
    c->publish_exports = 0;
    return OK;
}

static int normal_paths(void) {
    fused_cutpoints c = {0};
    if (crc_half(&c) || metadata_half(&c)) return 0;
    if (export_preflight_half(&c) || export_cells_half(&c)) return 0;
    return c.crc_metadata == 0 && c.publish_exports == 0
        && c.published_cells == 1;
}

static int negative_paths(void) {
    fused_cutpoints c = {0}; unsigned rejected = 0;
#define REJECT(expr) do { if ((expr) == ERR) ++rejected; else return 0; } while (0)
    REJECT(metadata_half(&c));
    c.crc_metadata = 0x34; REJECT(metadata_half(&c));
    c.crc_metadata = 0; if (crc_half(&c)) return 0;
    REJECT(crc_half(&c));
    if (metadata_half(&c)) return 0;
    REJECT(metadata_half(&c));

    REJECT(export_cells_half(&c));
    c.publish_exports = 0x15; REJECT(export_cells_half(&c));
    c.publish_exports = 0; if (export_preflight_half(&c)) return 0;
    REJECT(export_preflight_half(&c));
    if (export_cells_half(&c)) return 0;
    REJECT(export_cells_half(&c));
#undef REJECT
    return rejected == 8u;
}

int main(void) {
    if (!normal_paths() || !negative_paths()) return 2;
    puts("c2-lite-v6-coresident-cutpoints: PASS fusions=2 halves=4 "
         "negatives=8 added-state-bytes=0 added-pointers=0");
    return 0;
}
