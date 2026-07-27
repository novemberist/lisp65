#include <stdint.h>
#include <stdio.h>

enum {
    OK = 0,
    ERR = 1,
    DECODER_MARK = 0x5a,
    TRANSIENT_MARK = 0x74,
    PERSISTENT_MARK = 0x70,
    STAGE_MARK = 0x53,
    PLAN_MARK = 0x50,
    RAW_ROW_MARK = 0xa7
};

typedef struct {
    uint8_t decoder;
    uint8_t reserve;
    uint8_t stage;
    uint8_t plan;
    uint8_t row;
} cutpoints;

static uint8_t first(uint8_t *slot, uint8_t marker) {
    if (*slot) return ERR;
    *slot = marker; return OK;
}

static uint8_t second(uint8_t *slot, uint8_t marker) {
    if (*slot != marker) return ERR;
    *slot = 0; return OK;
}

static uint8_t plan_scan(cutpoints *c) {
    if (first(&c->plan, PLAN_MARK) != OK || c->row) return ERR;
    c->row = RAW_ROW_MARK; return OK;
}

static uint8_t plan_resolve(cutpoints *c) {
    if (c->plan != PLAN_MARK || c->row != RAW_ROW_MARK) return ERR;
    c->row = 0; c->plan = 0; return OK;
}

static int normal_paths(void) {
    cutpoints c = {0};
    if (first(&c.decoder, DECODER_MARK) || second(&c.decoder, DECODER_MARK))
        return 0;
    if (first(&c.reserve, TRANSIENT_MARK)
        || second(&c.reserve, TRANSIENT_MARK)) return 0;
    if (first(&c.reserve, PERSISTENT_MARK)
        || second(&c.reserve, PERSISTENT_MARK)) return 0;
    if (first(&c.stage, STAGE_MARK) || second(&c.stage, STAGE_MARK)) return 0;
    if (plan_scan(&c) || plan_resolve(&c)) return 0;
    return c.decoder == 0 && c.reserve == 0 && c.stage == 0
        && c.plan == 0 && c.row == 0;
}

static int negative_paths(void) {
    cutpoints c = {0}; unsigned rejected = 0;
#define REJECT(expr) do { if ((expr) == ERR) ++rejected; else return 0; } while (0)
    REJECT(second(&c.decoder, DECODER_MARK));
    c.decoder = 0x51; REJECT(second(&c.decoder, DECODER_MARK)); c.decoder = 0;
    if (first(&c.decoder, DECODER_MARK)) return 0;
    REJECT(first(&c.decoder, DECODER_MARK)); c.decoder = 0;

    REJECT(second(&c.reserve, TRANSIENT_MARK));
    c.reserve = PERSISTENT_MARK; REJECT(second(&c.reserve, TRANSIENT_MARK));
    c.reserve = 0; if (first(&c.reserve, TRANSIENT_MARK)) return 0;
    REJECT(first(&c.reserve, TRANSIENT_MARK)); c.reserve = 0;

    REJECT(second(&c.reserve, PERSISTENT_MARK));
    c.reserve = TRANSIENT_MARK; REJECT(second(&c.reserve, PERSISTENT_MARK));
    c.reserve = 0; if (first(&c.reserve, PERSISTENT_MARK)) return 0;
    REJECT(first(&c.reserve, PERSISTENT_MARK)); c.reserve = 0;

    REJECT(second(&c.stage, STAGE_MARK));
    c.stage = 0x35; REJECT(second(&c.stage, STAGE_MARK)); c.stage = 0;
    if (first(&c.stage, STAGE_MARK)) return 0;
    REJECT(first(&c.stage, STAGE_MARK)); c.stage = 0;

    REJECT(plan_resolve(&c));
    c.plan = PLAN_MARK; c.row = 0x17; REJECT(plan_resolve(&c));
    c.plan = 0; c.row = 0; if (plan_scan(&c)) return 0;
    REJECT(plan_scan(&c));

#undef REJECT
    return rejected == 15u;
}

int main(void) {
    if (!normal_paths() || !negative_paths()) return 2;
    puts("c2-lite-v6-semantic-split-cutpoints: PASS chains=5 negatives=15 "
         "handoff-bytes=0 handoff-pointers=0");
    return 0;
}
