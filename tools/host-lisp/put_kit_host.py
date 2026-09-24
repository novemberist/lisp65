"""Execute the proposed C kit with bounded canonical-name transport stubs.

This is an algorithm/lifetime preflight, not native timing or a Seed witness.
The exact functions priced by put_kit_objects are compiled, not a Python
reimplementation. Product integration and abort-driver proof remain separate.
"""
import argparse
import json
from pathlib import Path
import subprocess

import put_kit_objects as P


def function(text, signature):
    start = text.index(signature)
    opening = text.index('{', start)
    depth = 1
    end = opening + 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    return text[start:end] + '\n'


PREAMBLE = r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
typedef uint16_t obj;
#define NIL 0xffffu
#define MK_SYMI(i) ((obj)(i))
#define SYMI_IDX(i) (i)
#define LISP65_SYMBOL_NAME_BUFFER 34
#define LISP65_SYMBOL_NAME_MAX 33
#define C2_BNX_SLOTS 1024u
#define LISP65_C2_BNX_DONE 0xffffu
static char names[1008][34], query[34];
static uint16_t table[1024], count;
static unsigned reads, writes, creates;
static uint8_t mem_oom;
static uint16_t sym_count(void) { return count; }
static const char *symname(obj i) { assert(i < count); return names[i]; }
static uint16_t c2_u16(const uint8_t *p) { return p[0] | (uint16_t)p[1]<<8; }
static uint32_t c2_u24(const uint8_t *p) { return c2_u16(p) | (uint32_t)p[2]<<16; }
static uint16_t v2_bnx_get(uint16_t slot) {
    assert(slot < 1024); ++reads; return table[slot];
}
static void v2_bnx_put(uint16_t slot, uint16_t value) {
    assert(slot < 1024); ++writes; table[slot] = value;
}
static uint8_t c2_stream_shelf_read(uint32_t at, void *out, uint8_t length) {
    assert(at == 2); memcpy(out, query, length); return 1;
}
static obj sym_create(const char *name) {
    assert(count < 1008); assert(strlen(name) <= 33);
    strcpy(names[count], name); ++creates; return count++;
}
static obj linear(const char *name) {
    for (obj i = 0; i < count; ++i) if (!strcmp(name, names[i])) return i;
    return sym_create(name);
}
'''

TESTS = r'''
static obj lookup(const char *name, uint16_t *indexed) {
    uint8_t row[8] = {0}; strcpy(query, name); row[3] = strlen(name);
    obj result = c2_publish_bnx_lookup(row, indexed);
    return result == NIL ? linear(name) : result;
}
int main(void) {
    char name[34]; uint16_t indexed = 0, slot;
    for (unsigned i = 0; i < 763; ++i) {
        snprintf(name, sizeof name, "boot%u", i); linear(name);
    }
    v2_bnx_catch_up(&indexed); assert(indexed == count);
    /* Every indexed name, creation, duplicate, and intervening linear intern. */
    for (unsigned i = 0; i < 763; ++i) {
        snprintf(name, sizeof name, "boot%u", i); assert(lookup(name, &indexed) == i);
    }
    assert(lookup("publication", &indexed) == 763);
    assert(lookup("publication", &indexed) == 763);
    assert(linear("intervening") == 764);
    assert(lookup("intervening", &indexed) == 764);
    assert(count == 765 && indexed == 765);
    /* A complete hash collision must still compare canonical bytes. */
    char first[34] = {0}, second[34] = {0};
    static int seen[65536];
    for (unsigned i = 1; i < 100000; ++i) {
        snprintf(name, sizeof name, "collision%u", i);
        uint16_t h = v2_bnx_hash(name);
        if (seen[h]) {
            snprintf(first, sizeof first, "collision%d", seen[h]);
            strcpy(second, name); break;
        }
        seen[h] = i;
    }
    assert(first[0] && strcmp(first, second));
    obj a = lookup(first, &indexed), b = lookup(second, &indexed);
    assert(a != b && lookup(first, &indexed) == a && lookup(second, &indexed) == b);
    /* Full owner cannot loop or claim absence: sentinel forces linear fallback. */
    for (unsigned i = 0; i < 1024; ++i) table[i] = 1;
    unsigned before = reads;
    assert(v2_bnx_find("not-there", v2_bnx_hash("not-there"), &slot) == NIL);
    assert(slot == 0xffffu && reads - before == 1024);
    assert(lookup("full-table-fallback", &indexed) == count - 1);
    assert(indexed == 0xffffu);
    /* Bad ordinal is not dereferenced. */
    for (unsigned i = 0; i < 1024; ++i) table[i] = 1023;
    assert(v2_bnx_find("bad", v2_bnx_hash("bad"), &slot) == NIL && slot == 0xffffu);
    /* An abandoned owner's frontier is never reused by the next lifetime. */
    memset(table, 0, sizeof table); indexed = 0;
    v2_bnx_catch_up(&indexed); assert(indexed == count);
    assert(lookup("publication", &indexed) == 763);
    while (count < 1008) {
        snprintf(name, sizeof name, "capacity%u", count); lookup(name, &indexed);
    }
    assert(indexed == 1008);
    for (unsigned i = 0; i < 1008; ++i) {
        strcpy(name, names[i]); assert(lookup(name, &indexed) == i);
    }
    assert(creates == 1008);
    printf("PASS 1008 names; collision, catch-up, full/bad owner and fresh lifetime; %u reads %u writes\n", reads, writes);
}
'''


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--objects', required=True)
    parser.add_argument('--out', required=True)
    args = parser.parse_args()
    objects = P.ROOT / args.objects
    receipt = json.loads((objects / 'receipt.json').read_text())
    assert receipt['tool_sha256'] == P.sha(Path(P.__file__))
    for row in receipt['rows']:
        for binding in row['inputs']:
            assert P.sha(P.ROOT / binding['path']) == binding['sha256']
    out = P.ROOT / args.out
    out.mkdir(parents=True, exist_ok=False)
    decoder = (objects / 'put-kit/c2-stream-v2-decoder.c').read_text()
    runtime = (objects / 'put-kit/c2_product_runtime.c').read_text()
    body = ''.join(function(decoder, signature) for signature in
                   ('uint16_t v2_bnx_hash(', 'obj v2_bnx_find(', 'void v2_bnx_catch_up('))
    body += function(runtime, 'static obj c2_publish_bnx_lookup(')
    source = PREAMBLE + body + TESTS
    cases = {'candidate': source,
             'hash-is-equality': source.replace('if (known[i] == name[i]) return MK_SYMI(idx);',
                                                'return MK_SYMI(idx);'),
             'omit-catch-up': source.replace('    v2_bnx_catch_up(indexed);', ''),
             'unbounded-probe': source.replace('while (left--) {', 'while (1) {')}
    results = []
    for case, text in cases.items():
        if case != 'candidate':
            assert text != source
        path = out / (case + '.c')
        binary = path.with_suffix('')
        path.write_text(text)
        command = ['cc', '-std=c99', '-O1', '-g', '-fsanitize=address,undefined',
                   '-fno-pie', '-no-pie', str(path), '-o', str(binary)]
        subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            run = subprocess.run([str(binary)], text=True, stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT, timeout=10)
            code, output = run.returncode, run.stdout
        except subprocess.TimeoutExpired:
            code, output = 124, 'bounded probe mutation timed out\n'
        (out / (case + '.log')).write_text(output)
        assert (code == 0) == (case == 'candidate'), (case, output)
        results.append(dict(case=case, returncode=code, source_sha256=P.sha(path), output=output))
    (out / 'receipt.json').write_text(json.dumps(dict(
        claim='HOST C PREFLIGHT ONLY; NOT NATIVE LIFETIME ACCEPTANCE',
        inputs=dict(objects_sha256=P.sha(objects / 'receipt.json'), tool_sha256=P.sha(Path(__file__))),
        results=results), indent=2) + '\n')
    print('put-kit-host: PASS candidate and 3 falling mutations')


if __name__ == '__main__':
    main()
