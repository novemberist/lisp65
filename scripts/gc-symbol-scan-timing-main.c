/* Host-only timing probe for the GC's interned-symbol root scan.
 * The exact visit counter proves the work term; monotonic time bounds its
 * observed scaling without claiming target-cycle accuracy. */
#define _POSIX_C_SOURCE 200809L
#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <time.h>

#include "mem.h"
#include "symbol.h"

static uint64_t now_ns(void) {
    struct timespec ts;
    if (clock_gettime(CLOCK_MONOTONIC, &ts) != 0) return 0;
    return (uint64_t)ts.tv_sec * UINT64_C(1000000000) + (uint64_t)ts.tv_nsec;
}

int main(int argc, char **argv) {
    unsigned symbols, rounds, warmup, i;
    uint64_t started, elapsed;
    char name[12];

    if (argc != 4) return 2;
    symbols = (unsigned)strtoul(argv[1], 0, 0);
    rounds = (unsigned)strtoul(argv[2], 0, 0);
    warmup = (unsigned)strtoul(argv[3], 0, 0);
    if (!rounds || symbols > MAX_SYM) return 2;

    mem_init();
    for (i = 0; i < symbols; i++) {
        (void)snprintf(name, sizeof(name), "s%04u", i);
        (void)intern(name);
    }
    if (sym_count() != symbols) return 3;

    for (i = 0; i < warmup; i++) gc_collect();
    gc_symbol_scan_visits = 0;
    started = now_ns();
    for (i = 0; i < rounds; i++) gc_collect();
    elapsed = now_ns() - started;

    printf("{\"symbols\":%u,\"rounds\":%u,\"elapsed_ns\":%" PRIu64
           ",\"scan_visits\":%" PRIu32 ",\"gc_runs\":%u}\n",
           symbols, rounds, elapsed, gc_symbol_scan_visits, gc_runs);
    return 0;
}
