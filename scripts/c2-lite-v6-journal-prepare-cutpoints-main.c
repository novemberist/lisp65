#include <stdint.h>
#include <stdio.h>

enum {
    OK = 0,
    ERR = 1,
    J_NONE = 0,
    J_ACTIVE = 1,
    J_PREPARED = 2
};

typedef struct {
    uint8_t has_main_sink;
    uint8_t journal_result;
    uint8_t prepare_runs;
    uint8_t write_runs;
} journal_prepare_cutpoint;

static uint8_t prepare(journal_prepare_cutpoint *state) {
    if (!state || state->prepare_runs || state->write_runs
        || state->journal_result != J_NONE) return ERR;
    state->prepare_runs = 1;
    state->journal_result = J_PREPARED;
    return OK;
}

static uint8_t write(journal_prepare_cutpoint *state) {
    if (!state || state->write_runs) return ERR;
    state->write_runs = 1;
    state->journal_result = J_ACTIVE;
    return OK;
}

static uint8_t fused_entry(journal_prepare_cutpoint *state) {
    if (!state) return ERR;
    if (state->has_main_sink) {
        if (state->journal_result != J_NONE) return ERR;
        return write(state);
    }
    if (state->journal_result == J_NONE) return prepare(state);
    if (state->journal_result == J_PREPARED) return write(state);
    return ERR;
}

static int normal_append(void) {
    journal_prepare_cutpoint state = {1, J_NONE, 0, 0};
    return fused_entry(&state) == OK && state.prepare_runs == 0
        && state.write_runs == 1 && state.journal_result == J_ACTIVE;
}

static int rollback(void) {
    journal_prepare_cutpoint state = {0, J_NONE, 0, 0};
    return fused_entry(&state) == OK
        && state.journal_result == J_PREPARED
        && fused_entry(&state) == OK
        && state.prepare_runs == 1 && state.write_runs == 1
        && state.journal_result == J_ACTIVE;
}

static int negative_paths(void) {
    journal_prepare_cutpoint state = {0, J_ACTIVE, 0, 0};
    unsigned rejected = 0;
#define REJECT(expr) do { if ((expr) == ERR) ++rejected; else return 0; } while (0)
    REJECT(fused_entry(0));                         /* absent context */
    REJECT(fused_entry(&state));                    /* replay/skip after active */
    state.journal_result = 0x55; REJECT(fused_entry(&state)); /* foreign */
    state.journal_result = J_PREPARED;
    state.write_runs = 1; REJECT(fused_entry(&state)); /* replay write */
    state = (journal_prepare_cutpoint){1, J_ACTIVE, 0, 1};
    REJECT(fused_entry(&state));                    /* normal replay */
    state = (journal_prepare_cutpoint){0, J_NONE, 1, 0};
    REJECT(fused_entry(&state));                    /* replay prepare */
#undef REJECT
    return rejected == 6u;
}

static int marker_totality(void) {
    unsigned marker;
    unsigned accepted = 0;
    unsigned rejected = 0;

    for (marker = 0; marker != 256u; ++marker) {
        journal_prepare_cutpoint state = {
            1, (uint8_t)marker, 0, 0
        };
        uint8_t result = fused_entry(&state);
        if (marker == J_NONE) {
            if (result != OK || state.prepare_runs
                || state.write_runs != 1u
                || state.journal_result != J_ACTIVE) return 0;
            ++accepted;
        } else {
            if (result != ERR || state.prepare_runs || state.write_runs
                || state.journal_result != (uint8_t)marker) return 0;
            ++rejected;
        }
    }
    for (marker = 0; marker != 256u; ++marker) {
        journal_prepare_cutpoint state = {
            0, (uint8_t)marker, 0, 0
        };
        uint8_t result = fused_entry(&state);
        if (marker == J_NONE) {
            if (result != OK || state.prepare_runs != 1u
                || state.write_runs
                || state.journal_result != J_PREPARED) return 0;
            ++accepted;
        } else if (marker == J_PREPARED) {
            if (result != OK || state.prepare_runs
                || state.write_runs != 1u
                || state.journal_result != J_ACTIVE) return 0;
            ++accepted;
        } else {
            if (result != ERR || state.prepare_runs || state.write_runs
                || state.journal_result != (uint8_t)marker) return 0;
            ++rejected;
        }
    }
    return accepted == 3u && rejected == 509u;
}

int main(void) {
    if (!normal_append() || !rollback() || !negative_paths()
        || !marker_totality()) return 2;
    puts("c2-lite-v6-journal-prepare-cutpoints: PASS slice=1 entries=2 "
         "normal=1 rollback=2 negatives=6 "
         "markers=512 accepted=3 rejected=509 added-state-bytes=0 "
         "added-pointers=0");
    return 0;
}
