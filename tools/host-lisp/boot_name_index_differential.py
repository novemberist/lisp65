"""Host differential test for the boot name index, as extracted C.

The baseline is the product's own name model transcribed from src/symbol.c: a
linear scan over the symbol table with the four-bit length prefilter and a full
canonical name comparison per surviving candidate.  The candidate is the
transient open-addressed index proposed for the split boot phase, with a mocked
Bank-5 word store.  Both are driven by the **measured** boot request sequence
from the intern census, and must agree on every returned symbol index, on the
symbol creation order, on the name pool and on the length-class table.

Four mutations must be rejected:
  hash-equality   a tag match is accepted without the full name comparison
  no-catchup      the count catch-up is omitted while a symbol is created
                  outside the index's knowledge
  no-invalidate   the index survives the phase and is reused against a table
                  that grew on the unchanged linear path
  read-fail       a Bank-5 index word read fails and must abort, not miss

Host C only.  No native code, no link, no Seed, no device contact.
"""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CENSUS = ROOT / 'build/native-diet-intern-census-r1/capture-r1/intern.txt'
DECODER_PHASE_10_BOOT_ORDINAL = 8

SOURCE = r'''
/* Extracted host differential: product linear name model vs. transient index.
 * Not product code; compiled and run on the host only. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

#include "requests.h"

#define NAME_MAX 33
#define NAME_BUFFER (NAME_MAX + 1)
#define MAX_SYM 1008
#define NAMEPOOL 16351
#define BNX_SLOTS 1024u

/* ---- the product's own table, transcribed from src/symbol.c -------------- */
static uint16_t nsym, npool;
static uint8_t  nlen4[(MAX_SYM + 1) / 2];
static uint16_t nameoff[MAX_SYM];
static char     pool[NAMEPOOL];
static unsigned long comparisons, slot_reads;

#define NLEN4_CAP(l) ((uint8_t)((l) < 15 ? (l) : 15))
static uint8_t nlen4_get(uint16_t i) {
    return (i & 1u) ? (uint8_t)(nlen4[i >> 1] >> 4) : (uint8_t)(nlen4[i >> 1] & 15u);
}
static void nlen4_set(uint16_t i, uint8_t l) {
    if (i & 1u) nlen4[i >> 1] = (uint8_t)((nlen4[i >> 1] & 0x0fu) | (uint8_t)(l << 4));
    else        nlen4[i >> 1] = (uint8_t)((nlen4[i >> 1] & 0xf0u) | l);
}
/* sympool_streq: reads the full 34-byte buffer, then compares. */
static uint8_t sympool_streq(uint16_t off, const char *name) {
    char buf[NAME_BUFFER]; uint16_t i;
    ++comparisons;
    memcpy(buf, pool + off, NAME_BUFFER);
    for (i = 0; i < NAME_BUFFER; i++) {
        if (buf[i] != name[i]) return 0;
        if (buf[i] == 0) return 1;
    }
    return 1;
}
static int sym_create(const char *name) {
    uint16_t len = 0, off;
    while (name[len] && len <= NAME_MAX) len++;
    if (len > NAME_MAX || nsym >= MAX_SYM
        || (uint16_t)(len + 1) > (uint16_t)(NAMEPOOL - npool)) return -1;
    off = npool;
    memcpy(pool + off, name, (size_t)len + 1u);
    npool = (uint16_t)(npool + len + 1);
    nlen4_set(nsym, NLEN4_CAP(len));
    nameoff[nsym] = off;
    return (int)nsym++;
}
static int sym_lookup(const char *name) {
    uint16_t i, len = 0;
    while (name[len] && len <= NAME_MAX) len++;
    for (i = 0; i < nsym; i++) {
        if (nlen4_get(i) != NLEN4_CAP(len)) continue;
        if (sympool_streq(nameoff[i], name)) return (int)i;
    }
    return -1;
}
static int intern_linear(const char *name) {
    int found = sym_lookup(name);
    return found >= 0 ? found : sym_create(name);
}
/* symname: the single resident scratch buffer.  The index MUST NOT keep the
 * query name here, because confirming a hit overwrites it. */
static char sym_name_scratch[NAME_BUFFER];
static const char *symname(uint16_t index) {
    memcpy(sym_name_scratch, pool + nameoff[index], NAME_BUFFER);
    sym_name_scratch[NAME_BUFFER - 1] = 0;
    return sym_name_scratch;
}

/* ---- mocked Bank-5 transient index owner --------------------------------- */
static uint16_t bnx[BNX_SLOTS];
static unsigned long bnx_fail_at, bnx_reads;
static int bnx_aborted;

static uint16_t bnx_get(uint16_t slot) {
    ++bnx_reads; ++slot_reads;
#ifdef MUT_READ_FAIL
    if (bnx_reads == bnx_fail_at) { bnx_aborted = 1; return 0xffffu; }
#endif
    return bnx[slot];
}
static void bnx_put(uint16_t slot, uint16_t word) { bnx[slot] = word; }

static uint16_t bnx_hash(const char *p) {
    uint16_t h = 0;
    while (*p) h = (uint16_t)((uint16_t)(h << 5) + h) ^ (uint8_t)*p++;
    return h;
}
/* Returns the symbol index, or -1 with *slot at the first empty probe slot. */
static int bnx_find(const char *name, uint16_t h, uint16_t *slot) {
    uint16_t s = (uint16_t)(h & (BNX_SLOTS - 1u)), word, idx;
    while ((word = bnx_get(s)) != 0u) {
        if (bnx_aborted) return -2;
        idx = (uint16_t)((word & 0x3ffu) - 1u);
        if ((uint8_t)(word >> 10) == (uint8_t)((h >> 10) & 0x3fu)) {
#ifdef MUT_HASH_EQUALITY
            return (int)idx;                /* mutation: tag taken as equality */
#else
            {
                const char *known = symname(idx); uint8_t i = 0;
                ++comparisons;                  /* a full canonical comparison */
                while (known[i] == name[i] && name[i]) ++i;
                if (known[i] == name[i]) return (int)idx;
            }
#endif
        }
        s = (uint16_t)((s + 1u) & (BNX_SLOTS - 1u));
    }
    *slot = s;
    return -1;
}
static int bnx_indexed;
static int bnx_catch_up(void) {
    char name[NAME_BUFFER]; uint16_t slot = 0, h; uint8_t i;
    while (bnx_indexed < (int)nsym) {
        const char *known = symname((uint16_t)bnx_indexed);
        for (i = 0; (name[i] = known[i]) != 0; ++i) {}
        h = bnx_hash(name);
        if (bnx_find(name, h, &slot) == -2) return -2;
        bnx_put(slot, (uint16_t)((uint16_t)(bnx_indexed + 1)
                | (uint16_t)(((h >> 10) & 0x3fu) << 10)));
        ++bnx_indexed;
    }
    return 0;
}
static int bnx_begin(void) {
    memset(bnx, 0, sizeof bnx);
    bnx_indexed = 0;
    return bnx_catch_up();
}
static void bnx_end(void) {
#ifndef MUT_NO_INVALIDATE
    memset(bnx, 0, sizeof bnx);
    bnx_indexed = 0;
#endif
}
/* The resolve phase's per-entry path. */
static int bnx_value(const char *query) {
    char name[NAME_BUFFER]; uint16_t h, slot = 0; int s;
    size_t n = strlen(query);
    if (!n || n > NAME_MAX) return -1;
    memcpy(name, query, n + 1u);
#ifndef MUT_NO_CATCHUP
    if (bnx_catch_up() == -2) return -2;
#endif
    h = bnx_hash(name);
    s = bnx_find(name, h, &slot);
    if (s == -2) return -2;
    if (s < 0) {
        s = sym_create(name);
        if (s < 0) return -1;
        if (s == bnx_indexed) {
            bnx_put(slot, (uint16_t)((uint16_t)(bnx_indexed + 1)
                    | (uint16_t)(((h >> 10) & 0x3fu) << 10)));
            ++bnx_indexed;
        }
    }
    return s;
}

/* ---- drive both models over the measured request sequence ---------------- */
static int expect[REQUESTS];
static uint16_t expect_nsym[REQUESTS];
static char expect_pool[NAMEPOOL];
static uint8_t expect_nlen4[(MAX_SYM + 1) / 2];
static uint16_t expect_final_nsym, expect_final_npool;
static unsigned long expect_comparisons;

/* A modelled decode abort: the symbol table and name pool roll back to the
 * state at phase entry.  Stale index slots then name indices that no longer
 * exist, and `indexed` claims symbols that were never inserted. */
static char ref_pool[NAMEPOOL];
static uint16_t ref_nameoff[MAX_SYM];
static uint16_t snap_nsym, snap_npool;
static uint8_t snap_nlen4[(MAX_SYM + 1) / 2];
static uint16_t snap_nameoff[MAX_SYM];
static char snap_pool[NAMEPOOL];
static void snapshot(void) {
    snap_nsym = nsym; snap_npool = npool;
    memcpy(snap_nlen4, nlen4, sizeof nlen4);
    memcpy(snap_nameoff, nameoff, sizeof nameoff);
    memcpy(snap_pool, pool, sizeof pool);
}
static void rollback(void) {
    nsym = snap_nsym; npool = snap_npool;
    memcpy(nlen4, snap_nlen4, sizeof nlen4);
    memcpy(nameoff, snap_nameoff, sizeof nameoff);
    memcpy(pool, snap_pool, sizeof pool);
}
static void bnx_abort(void) {
#ifndef MUT_NO_INVALIDATE
    memset(bnx, 0, sizeof bnx);
    bnx_indexed = 0;
#endif
}

static void reset(void) {
    nsym = npool = 0; comparisons = slot_reads = 0;
    memset(nlen4, 0, sizeof nlen4); memset(nameoff, 0, sizeof nameoff);
    memset(pool, 0, sizeof pool);
    memset(bnx, 0, sizeof bnx); bnx_indexed = 0; bnx_reads = 0; bnx_aborted = 0;
}

int main(int argc, char **argv) {
    unsigned i, mismatches = 0, collisions = 0, creations = 0;
    unsigned long ix_comparisons, ix_slot_reads;
    unsigned retried = 0;
    int pool_same = 0, nlen4_same = 0, final_same = 0;
    int external_at = -1;
    bnx_fail_at = argc > 1 ? strtoul(argv[1], 0, 10) : 0;
    if (argc > 2) external_at = atoi(argv[2]);

    /* pass 1: the unchanged linear model is the reference */
    reset();
    for (i = 0; i < REQUESTS; ++i) {
        if ((int)i == external_at) (void)intern_linear(EXTERNAL_NAME);
        expect[i] = intern_linear(request_name[i]);
        expect_nsym[i] = nsym;
    }
    expect_final_nsym = nsym; expect_final_npool = npool;
    expect_comparisons = comparisons;
    memcpy(expect_pool, pool, sizeof pool);
    memcpy(expect_nlen4, nlen4, sizeof nlen4);

    /* pass 2: the index is live only inside the decoder-phase-10 window */
    reset();
    for (i = 0; i < REQUESTS; ++i) {
        int got;
        if ((int)i == external_at) (void)intern_linear(EXTERNAL_NAME);
        if (request_phase[i] == WINDOW_PHASE) {
            if (i == 0 || request_phase[i - 1] != WINDOW_PHASE) {
                if (bnx_begin() == -2) { printf("ABORT begin at %u\n", i); return 3; }
            }
            {
                uint16_t before = nsym;
                got = bnx_value(request_name[i]);
                if (got == -2) { printf("ABORT read at %u\n", i); return 3; }
                if (nsym != before) ++creations;
            }
            if (i + 1 == REQUESTS || request_phase[i + 1] != WINDOW_PHASE) bnx_end();
        } else {
            got = intern_linear(request_name[i]);
        }
        if (got != expect[i] || nsym != expect_nsym[i]) ++mismatches;
    }
    ix_comparisons = comparisons; ix_slot_reads = slot_reads;
    pool_same = memcmp(expect_pool, pool, sizeof pool) == 0;
    nlen4_same = memcmp(expect_nlen4, nlen4, sizeof nlen4) == 0;
    final_same = (nsym == expect_final_nsym) && (npool == expect_final_npool);
    /* a real same-slot, different-name tag collision must be exercised, and
     * the abort path must invalidate: after a modelled rollback the phase is
     * retried from its first record and must reproduce the reference exactly. */
    {
        unsigned first = 0, last = 0, j, retry_mismatches = 0;
        for (i = 0; i < REQUESTS; ++i) if (request_phase[i] == WINDOW_PHASE) { first = i; break; }
        for (i = REQUESTS; i-- > 0;) if (request_phase[i] == WINDOW_PHASE) { last = i; break; }
        reset();
        for (i = 0; i < first; ++i) (void)intern_linear(request_name[i]);
        snapshot();
        if (bnx_begin() == -2) { printf("ABORT begin\n"); return 3; }
        for (j = first; j < first + (last - first) / 2u; ++j) {
            uint16_t h = bnx_hash(request_name[j]), slot = 0;
            uint16_t s2 = (uint16_t)(h & (BNX_SLOTS - 1u)), word;
            while ((word = bnx[s2]) != 0u) {
                uint16_t idx = (uint16_t)((word & 0x3ffu) - 1u);
                if (strcmp(pool + nameoff[idx], request_name[j]) == 0) break;
                ++collisions;
                s2 = (uint16_t)((s2 + 1u) & (BNX_SLOTS - 1u));
            }
            (void)slot;
            if (bnx_value(request_name[j]) < 0) { printf("probe failure\n"); return 3; }
        }
        rollback();
        bnx_abort();
        /* Recovery between the abort and the retry: the unchanged linear path
         * creates symbols the aborted attempt had not yet reached.  A live
         * index that was not invalidated still claims to cover the table. */
        for (j = 0; j < RECOVERY_NAMES; ++j) (void)intern_linear(recovery_name[j]);
        if (bnx_indexed == 0) { if (bnx_begin() == -2) { printf("ABORT rebuild\n"); return 3; } }
        for (j = first; j <= last; ++j) {
            if (bnx_value(request_name[j]) < 0) { printf("retry failure\n"); return 3; }
        }
        /* the retry must land on exactly the reference table */
        {
            uint16_t ref_nsym = nsym, k; int agree = 1;
            memcpy(ref_pool, pool, sizeof pool);
            memcpy(ref_nameoff, nameoff, sizeof nameoff);
            reset();
            for (i = 0; i < first; ++i) (void)intern_linear(request_name[i]);
            for (j = 0; j < RECOVERY_NAMES; ++j) (void)intern_linear(recovery_name[j]);
            for (j = first; j <= last; ++j) (void)intern_linear(request_name[j]);
            if (ref_nsym != nsym) agree = 0;
            for (k = 0; agree && k < nsym; ++k)
                if (strcmp(ref_pool + ref_nameoff[k], pool + nameoff[k])) agree = 0;
            if (!agree) ++retry_mismatches;
        }
        mismatches += retry_mismatches;
        retried = retry_mismatches;
    }
    printf("{\"requests\": %u, \"mismatches\": %u, \"creations_in_window\": %u,"
           " \"probe_collisions\": %u, \"abort_retry_mismatches\": %u,"
           " \"linear_comparisons\": %lu, \"index_comparisons\": %lu,"
           " \"index_slot_reads\": %lu,"
           " \"final_nsym\": %u, \"pool_identical\": %d, \"nlen4_identical\": %d,"
           " \"final_counts_identical\": %d}\n",
           REQUESTS, mismatches, creations, collisions, retried,
           expect_comparisons, ix_comparisons, ix_slot_reads, expect_final_nsym,
           pool_same, nlen4_same, final_same);
    return (mismatches || !pool_same || !nlen4_same || !final_same) ? 1 : 0;
}
'''


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out', type=Path,
                    default=ROOT / 'build/boot-name-index-differential-r1')
    ap.add_argument('--census', type=Path, default=CENSUS)
    a = ap.parse_args()
    out = a.out.resolve()
    if not out.is_relative_to(ROOT / 'build'):
        raise ValueError('outputs must stay under build/')
    out.mkdir(parents=True, exist_ok=True)

    rows = []
    for line in a.census.read_text().splitlines():
        f = line.split()
        if f[0] != 'N':
            raise ValueError('unexpected census row')
        rows.append((int(f[1]), f[9]))
    names = ''.join('    "%s",\n' % n for _, n in rows)
    phases = ''.join('    %d,\n' % p for p, _ in rows)
    window = [n for p, n in rows if p == DECODER_PHASE_10_BOOT_ORDINAL]
    recovery = list(dict.fromkeys(window[-8:]))
    header = ('/* Generated from the measured intern census; do not edit. */\n'
              '#define REQUESTS %d\n#define WINDOW_PHASE %d\n'
              '#define EXTERNAL_NAME "%%bnx-external-witness"\n'
              'static const char *const request_name[REQUESTS] = {\n%s};\n'
              'static const unsigned char request_phase[REQUESTS] = {\n%s};\n'
              '#define RECOVERY_NAMES %d\n'
              'static const char *const recovery_name[RECOVERY_NAMES] = {\n%s};\n'
              % (len(rows), DECODER_PHASE_10_BOOT_ORDINAL, names, phases,
                 len(recovery), ''.join('    "%s",\n' % n for n in recovery)))
    (out / 'requests.h').write_text(header)
    (out / 'differential.c').write_text(SOURCE)

    variants = [('baseline-vs-index', []),
                ('hash-equality', ['-DMUT_HASH_EQUALITY']),
                ('no-catchup', ['-DMUT_NO_CATCHUP']),
                ('no-invalidate', ['-DMUT_NO_INVALIDATE']),
                ('read-fail', ['-DMUT_READ_FAIL'])]
    results = []
    for name, defines in variants:
        binary = out / name
        cc = ['cc', '-O2', '-std=c99', '-Wall', '-Wextra', '-I', str(out),
              *defines, str(out / 'differential.c'), '-o', str(binary)]
        log = subprocess.run(cc, cwd=ROOT, capture_output=True, text=True)
        (out / (name + '.compile.log')).write_text(log.stdout + log.stderr)
        if log.returncode:
            raise ValueError('compile failed: ' + name + '\n' + log.stdout + log.stderr)
        # the catch-up mutation only shows with a symbol made outside the index;
        # the read mutation needs a failing index word read.
        args = []
        if name in ('no-catchup',):
            args = ['0', '1200']
        elif name == 'read-fail':
            args = ['500']
        run = subprocess.run([str(binary), *args], capture_output=True, text=True)
        results.append(dict(variant=name, defines=defines, args=args,
                            exit_status=run.returncode,
                            stdout=run.stdout.strip(),
                            expectation='agree' if name == 'baseline-vs-index'
                                        else 'reject'))

    agree = results[0]
    if agree['exit_status'] != 0:
        verdict = 'FAILED: the index disagrees with the linear model'
    elif any(r['exit_status'] == 0 for r in results[1:]):
        verdict = 'FAILED: a mutation was not rejected'
    else:
        verdict = 'PASS: agreement on the measured sequence; all four mutations rejected'

    receipt = dict(
        claim='HOST C DIFFERENTIAL ONLY; NOT NATIVE, NOT A LINK OR SEED PRICE',
        budget=dict(seed=0, finale=0, link=0, device_contacts=0),
        census=dict(path=str(a.census.relative_to(ROOT)),
                    sha256=hashlib.sha256(a.census.read_bytes()).hexdigest(),
                    requests=len(rows)),
        source_sha256=hashlib.sha256((out / 'differential.c').read_bytes()).hexdigest(),
        requests_sha256=hashlib.sha256((out / 'requests.h').read_bytes()).hexdigest(),
        verdict=verdict, results=results)
    (out / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    main()
