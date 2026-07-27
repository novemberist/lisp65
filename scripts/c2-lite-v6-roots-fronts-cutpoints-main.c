#include <stdint.h>
#include <stdio.h>

enum {
    OK = 0,
    ERR = 1,
    ROOTS_REQUEST = 0x72,
    FRONTS_REQUEST = 0x66
};

typedef struct {
    uint8_t marker;
    uint8_t roots_runs;
    uint8_t fronts_runs;
} roots_fronts_cutpoint;

static uint8_t roots_entry(roots_fronts_cutpoint *state) {
    if (!state || state->roots_runs || state->fronts_runs) return ERR;
    state->roots_runs = 1;
    return OK;
}

static uint8_t fronts_entry(roots_fronts_cutpoint *state) {
    if (!state || !state->roots_runs || state->fronts_runs) return ERR;
    state->fronts_runs = 1;
    return OK;
}

static uint8_t slice_entry(roots_fronts_cutpoint *state) {
    uint8_t requested;
    if (!state) return ERR;
    requested = state->marker;
    state->marker = 0;
    if (requested == ROOTS_REQUEST) return roots_entry(state);
    if (requested == FRONTS_REQUEST) return fronts_entry(state);
    return ERR;
}

static int normal_path(void) {
    roots_fronts_cutpoint state = {0};
    state.marker = ROOTS_REQUEST;
    if (slice_entry(&state)) return 0;
    state.marker = FRONTS_REQUEST;
    if (slice_entry(&state)) return 0;
    return !state.marker && state.roots_runs == 1 && state.fronts_runs == 1;
}

static int fronts_only_rollback(void) {
    roots_fronts_cutpoint state = {0, 1, 0};
    state.marker = FRONTS_REQUEST;
    return !slice_entry(&state) && !state.marker && state.fronts_runs == 1;
}

static int negative_paths(void) {
    roots_fronts_cutpoint state = {0};
    unsigned rejected = 0;
#define REJECT(expr) do { if ((expr) == ERR) ++rejected; else return 0; } while (0)
    REJECT(slice_entry(&state));                         /* skipped selector */
    state.marker = FRONTS_REQUEST; REJECT(slice_entry(&state)); /* skipped roots */
    state.marker = 0x31; REJECT(slice_entry(&state));   /* foreign selector */
    state.marker = ROOTS_REQUEST;
    if (slice_entry(&state)) return 0;
    state.marker = ROOTS_REQUEST; REJECT(slice_entry(&state)); /* replay roots */
    state.marker = FRONTS_REQUEST;
    if (slice_entry(&state)) return 0;
    state.marker = FRONTS_REQUEST; REJECT(slice_entry(&state)); /* replay fronts */
    state.marker = ROOTS_REQUEST; REJECT(slice_entry(&state)); /* roots after fronts */
#undef REJECT
    return rejected == 6u && !state.marker;
}

int main(void) {
    if (!normal_path() || !fronts_only_rollback() || !negative_paths())
        return 2;
    puts("c2-lite-v6-roots-fronts-cutpoints: PASS slice=1 entries=2 "
         "normal=2 rollback=1 negatives=6 added-state-bytes=0 "
         "added-pointers=0");
    return 0;
}
