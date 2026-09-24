"""Lower-bound object price for a phase-local Boot symbol index.

This is NOT a placed/accepted cache: the named Bank-5 transport seams and
uncached creation seam are deliberately external and their cost is additional.
No product source is changed and no new memory owner is asserted.
"""
import json
import shlex
from native_diet_object_probe import ROOT, BASE, sha, put, run
from elf_truth import ElfTruth

SOURCE = r'''
#include "symbol.h"
#include "mem.h"
#include <string.h>

/* Only for pricing. Real admission must bind these to one checked owner,
 * generation, abort invalidation and content-converged transport. */
extern uint8_t boot_index_read(uint16_t at, uint8_t *bytes, uint8_t n);
extern uint8_t boot_index_write(uint16_t at, uint8_t value);
extern obj boot_index_new_symbol(const char *name);
typedef struct { uint16_t count; uint8_t valid; } boot_index_state;

#define BOOT_CODE __attribute__((section(".lisp65_rt_c2d_10"), noinline))
static BOOT_CODE uint8_t boot_hash(const char *p) {
    uint8_t value = 0;
    while (*p) value = (uint8_t)((value << 1) | (value >> 7)) ^ (uint8_t)*p++;
    return value;
}

/* Stack-scoped state is initialized on entry to this one phase; it cannot
 * survive return, abort, reset or a family/window change. */
BOOT_CODE obj boot_index_intern(boot_index_state *s, const char *input) {
    char name[LISP65_SYMBOL_NAME_BUFFER];
    uint8_t block[32], hash, n, j;
    uint16_t i, count;
    obj result;
    if (!s->valid) return intern(input);
    for (n = 0; n < sizeof(name); ++n) {
        name[n] = input[n];
        if (!name[n]) break;
    }
    if (n == sizeof(name)) return intern(input);
    hash = boot_hash(name);
    count = sym_count();
    if (count > MAX_SYM || s->count > count) goto lost;
    while (s->count < count) {
        uint8_t h = boot_hash(symname(sym_nth(s->count)));
        if (!boot_index_write(s->count, h)) goto lost;
        ++s->count;
    }
    for (i = 0; i < count; i += n) {
        n = count - i > sizeof(block) ? sizeof(block) : (uint8_t)(count - i);
        if (!boot_index_read(i, block, n)) goto lost;
        for (j = 0; j < n; ++j) {
            if (block[j] != hash) continue;
            result = sym_nth(i + j);
            if (!strcmp(name, symname(result))) return result;
        }
    }
    result = boot_index_new_symbol(name);
    if (result != NIL) {
        if (sym_count() != count + 1u || !boot_index_write(count, hash))
            s->valid = 0;
        else ++s->count;
    }
    return result;
lost:
    s->valid = 0;
    return intern(name);
}
'''


def main():
    out = ROOT / 'build/native-diet-boot-intern-probe-r1'
    out.mkdir(parents=True, exist_ok=True)
    src, obj = out / 'cache.c', out / 'cache.o'
    put(src, SOURCE)
    proof = json.loads((BASE / 'command-proof.json').read_text())
    command = next(c for c in proof['commands'] if '-c' in c
                   and c[c.index('-c') + 1].endswith('/symbol.c'))
    flags = command[1:command.index('-c')]
    closure_path = BASE / 'active-include-check/receipt.json'
    closure = json.loads(closure_path.read_text())
    allowed = {(ROOT / d['path']).resolve(): d['sha256']
               for row in closure['rows'] for d in row['dependencies']}
    deps = run([command[0], *flags, '-M', '-MT', 'probe', str(src)])
    put(out / 'cache.d', deps)
    inputs = []
    for path in shlex.split(deps.replace('\\\n', ' ').split(':', 1)[1]):
        p = (ROOT / path).resolve()
        if p != src and (p not in allowed or sha(p) != allowed[p]):
            raise ValueError('unbound include: ' + str(p))
        inputs.append(dict(path=str(p.relative_to(ROOT)), sha256=sha(p)))
    if obj.exists():
        raise ValueError('experiment already exists')
    cc = [command[0], *flags, '-fno-lto', '-c', str(src), '-o', str(obj)]
    put(out / 'compile.log', run(cc))
    truth = ElfTruth.read(obj, llvm_readobj=ROOT / 'tools/llvm-mos/bin/llvm-readobj')
    sections = {s.name: s.bytes for s in truth.sections
                if s.name.startswith(('.text', '.rodata', '.bss', '.lisp65_rt_'))}
    unresolved = sorted({s.name for s in truth.symbols if s.section_index == 0 and s.name})
    receipt = dict(claim='LOWER-BOUND CACHE CORE ONLY; NOT A PLACEMENT OR CORRECTNESS PASS',
                   budget=dict(seed=0, finale=0, link=0), sections=sections,
                   inputs=inputs, command=cc, unresolved=unresolved,
                   compiler_sha256=sha(__import__('pathlib').Path(command[0])),
                   index_data_bytes=1008, stack_state_bytes=3,
                   unpriced=['owner-bound transport', 'uncached symbol creation seam',
                             'phase split/dispatch', 'cache lifecycle and corruption gates'])
    put(out / 'receipt.json', json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    main()
