#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

#include "obj.h"

enum {
    PLAN_ROWS = 353,
    PLAN_ROW_BYTES = 8,
    ENTRY_CAP = 2048
};

static uint16_t u16(const uint8_t *p) {
    return (uint16_t)p[0] | (uint16_t)p[1] << 8;
}

static void put16(uint8_t *p, uint16_t value) {
    p[0] = (uint8_t)value;
    p[1] = (uint8_t)(value >> 8);
}

static int plan_row_valid(const uint8_t row[PLAN_ROW_BYTES]) {
    uint16_t tagged = u16(row + 4);
    return IS_SYMI((obj)u16(row))
        && !(tagged & 0x7000u)
        && (tagged & 0x0fffu) < ENTRY_CAP
        && row[6] == 0u && row[7] == 0u;
}

static int rejects_symbol(uint8_t row[PLAN_ROW_BYTES], uint16_t value) {
    uint16_t saved = u16(row);
    int rejected;
    put16(row, value);
    rejected = !plan_row_valid(row);
    put16(row, saved);
    return rejected;
}

int main(int argc, char **argv) {
    uint8_t plan[PLAN_ROWS * PLAN_ROW_BYTES];
    uint8_t *row;
    FILE *input;
    size_t got;
    unsigned i, accepted = 0, rejected = 0;

    if (argc != 2) return 2;
    input = fopen(argv[1], "rb");
    if (!input) return 3;
    got = fread(plan, 1, sizeof plan, input);
    if (fclose(input) || got != sizeof plan) return 4;

    for (i = 0; i < PLAN_ROWS; ++i) {
        row = plan + i * PLAN_ROW_BYTES;
        if (!plan_row_valid(row)) return 5;
        ++accepted;
    }

    row = plan;
    rejected += (unsigned)rejects_symbol(row, 0x0002u); /* heap pointer */
    rejected += (unsigned)rejects_symbol(row, 0x0000u); /* NIL */
    rejected += (unsigned)rejects_symbol(row, (uint16_t)MKFIX(1));
    rejected += (unsigned)rejects_symbol(row, (uint16_t)MK_BCODE(0));
    rejected += (unsigned)rejects_symbol(row, (uint16_t)(u16(row) | 1u));
    if (rejected != 5u || !plan_row_valid(row)) return 6;

    printf("c2-lite-v6-export-symbol-domain: PASS rows=%u "
           "foreign-domains-rejected=%u first-symi=0x%04x\n",
           accepted, rejected, u16(row));
    return 0;
}
