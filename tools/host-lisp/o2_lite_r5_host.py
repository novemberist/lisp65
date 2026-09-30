#!/usr/bin/env python3
"""Host-only admission and frozen-product literal boundary witnesses for r5."""
import argparse
import json
import os
from pathlib import Path
import subprocess

import o2_lite_r3_host as H
import o2_lite_r4_host as H4
import c2_repl_pipeline_cost_attribution as PIPE
import bytecode_p0_compiler as C
import strings_seed_producer as S

ROOT = H.ROOT


def admission(out):
    out.mkdir()
    H.setup(out)
    from admission import row
    rows = []
    for n in (639, 640, 641):
        source = '"'+'a'*199+'\n'+'b'*200+'\n'+'c'*200+'\n'+'d'*(n-604)+'"'
        assert len(source) == n
        for path in ('typed', 'reopened', 'recalled'):
            notice = '*** input limit' if n == 641 else None
            answer = 'ok' if notice else source
            if path == 'typed':
                keys = list((source.replace('\n', '\r')+'\r').encode())
            elif path == 'reopened':
                keys = list(('"'+'a'*199+'\r'+'b'*200+'\r'+'c'*199+'\r').encode())
                keys += [20]+list(('c\r'+'d'*(n-604)+'"\r').encode())
            else:
                prefix = 'd'*249+'"'
                pending = '"'+'a'*198+'\n'+'b'*(n-451)+'\n'
                assert len(pending)+len(prefix) == n
                answer = 'ok' if notice else pending+prefix
                keys = [145] + ([] if notice else [13])
            if notice:
                keys += list(b'ok\r')
            case = row(path+'-'+str(n), keys, answer, notice)
            if path == 'recalled':
                case['expr'] = ('(%repl-step (list (string-append "'+prefix[:-1]+
                                '" (%string-from-codes (list 34)))) '
                                '(string-append (%string-from-codes (list 34)) "'+
                                pending[1:]+'") 2)')
            rows.append(case)
    # Exercise scalar, actual ring capacity and replenished/uncapped batching.
    original = H.M.AuditVM
    results = []
    for cap in (1, 107, None):
        class Audit(original):
            def __init__(self, *args, **kw):
                kw['batch_cap'] = cap
                super().__init__(*args, **kw)
        H.M.AuditVM = Audit
        measured = H.M.run_audit(rows)
        for r in measured:
            r['batch_cap'] = cap
            assert r['peaks']['cells']['cells']+520 <= 1072
            assert r['peaks']['arena']['arena']+2048 <= 9344
            assert r['root_peak'] <= 128
        results += measured
    H.M.AuditVM = original
    H.save(out/'receipt.json', dict(status='PASS', sources=H4.bindings(), rows=results))


def function(source, marker):
    start = source.index(marker)
    brace = source.index('{', start)
    depth = 1
    end = brace+1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end]


def literals(out):
    out.mkdir()
    # Execute the exact C admission functions with host memory/staging seams.
    # The compiler itself is loaded from the frozen product manifests below.
    frozen = ROOT/'build/strings-r7/seed/candidate-inputs/src/c2_session_emitter.c'
    if not frozen.exists():
        ready = json.loads((ROOT/'build/strings-r7/seed/command-ready.json').read_text())
        frozen = ROOT/next(r['restored']['path'] for r in ready['native']
                          if r['source']['path'].endswith('/c2_session_emitter.c'))
    source = frozen.read_text()
    pieces = [function(source, 'C2E_INLINE uint16_t '+n+'(')
              for n in ('c2e_add_raw_string', 'c2e_add_string')]
    assert pieces == [function((ROOT/'src/c2_session_emitter.c').read_text(),
                               'C2E_INLINE uint16_t '+n+'(')
                      for n in ('c2e_add_raw_string', 'c2e_add_string')]
    cfile = out/'literal-boundary.c'
    cfile.write_text('''#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#define C2E_INLINE static inline
#define C2E_MAX_STRINGS 2048u
#define C2E_STRING_STAGE 11264u
#define C2E_ANONYMOUS 0xffffu
#define T_STR 1
#define IS_PTR(x) ((x)==2)
typedef uint16_t obj;
static struct { uint16_t string_bytes; } c2e;
static uint16_t length;
static uint8_t stage[16384];
static int cell_type(obj x) { (void)x; return T_STR; }
static uint16_t str_len(obj x) { (void)x; return length; }
static uint8_t str_byte(obj x, uint16_t i) { (void)x; (void)i; return 97; }
static void c2e_put(uint16_t at, uint8_t v) { stage[at]=v; }
static void c2e_w16(uint16_t at, uint16_t v) { stage[at]=v; stage[at+1]=v>>8; }
'''+ '\n'.join(pieces)+'''
int main(int argc, char **argv) {
    if (argc != 2) return 2;
    length=(uint16_t)atoi(argv[1]);
    uint16_t result=c2e_add_string(2);
    printf("%u\\n", result);
    if (result != C2E_ANONYMOUS &&
        (c2e.string_bytes != length+2 || stage[C2E_STRING_STAGE+2] != 97)) return 3;
    return 0;
}
''')
    command = ['cc', '-std=c99', '-Wall', '-Wextra', '-Werror',
               '-fsanitize=undefined', str(cfile), '-o', str(out/'literal-boundary')]
    subprocess.run(command, check=True)
    products = [ROOT/'build/strings-r7/seed/plane/candidate/product/substitution-artifacts.json',
                ROOT/'build/o2-lite-r4-slots-preflight/planes/candidate/product/substitution-artifacts.json']
    results = []
    bindings = []
    for world, product in zip(('2.5.1', 'r4'), products):
        spec = json.loads(product.read_text())
        manifests = [ROOT/r['path'] for r in spec['manifests']]
        selected = [p for p in manifests if json.loads(p.read_text()).get('name') == 'c2-v112-product-compiler-tier'
                    or p.name == 'stdlib-p0.manifest.json']
        assert len(selected) == 2
        heap = C.prepare_heap([])
        directory, names, origins, macros = {}, {}, {}, set()
        for p in selected:
            bindings.append(PIPE.load_manifest_entries(heap, p, world, directory, macros, names, origins))
        vm = PIPE.PipelineVM(heap=heap, directory=directory, macro_symbols=macros,
                             max_steps=10000000, code_names=names, abi_profile='dialect-v2',
                             abi_ledger=PIPE.load(ROOT/'config/bytecode-abi-ledger.json'))
        fixtures = [('literal-'+str(n), '"'+'a'*n+'"', n) for n in (254,255,256,600,638,639,640)]
        fixtures += [('multiline-640', '(progn\n;'+ 'a'*198+'\n;'+ 'b'*198+'\n;'+ 'c'*228+'\n42)', None)]
        assert len(fixtures[-1][1]) == 640
        for label, text, n in fixtures:
            form = vm._compiler_form_obj(C.parse_one(text))
            try:
                vm.run(directory[heap.intern('lcc-run')], [form])
            except PIPE.InstallBoundary as boundary:
                code = PIPE.decode_definition(heap, boundary.args[0], label)
            else:
                raise AssertionError('missing product install boundary')
            if n is not None:
                assert len(code.littab) == 1
                assert len(heap.string_to_text(code.littab[0])) == n
                emitted = int(subprocess.check_output([str(out/'literal-boundary'), str(n)], text=True))
            else:
                emitted = 0
            if emitted == 65535:
                result = 'C2_EMIT_STRINGS -> VM_BADOPCODE'
            else:
                # Execute the compiled object on the same VM after successful
                # native string admission. No substitute compiler is used.
                value = vm.run(code, [])
                result = heap.obj_to_text(value)
                assert result == ('"'+'a'*n+'"' if n is not None else '42')
            results.append(dict(world=world, name=label, source_bytes=len(text),
                                literal_bytes=n, object_bytes=len(code.encode()), result=result))
        assert [r['result'] for r in results if r['world']==world and r['literal_bytes'] is not None and r['literal_bytes']>255] == ['C2_EMIT_STRINGS -> VM_BADOPCODE']*5
    H.save(out/'receipt.json', dict(status='PASS', rows=results, manifests=bindings,
            frozen_emitter=S.bind(frozen), emitted_c=S.bind(cfile), command=command,
            scope='Frozen product compiler bytecode on host VM; exact native C string admission functions; product error mapping inspected, no target execution'))


def transport(out):
    out.mkdir()
    import comfort_default_rows as ROWS
    from elf_truth import ElfTruth
    elf = ROOT/'build/o2-lite-product-r4/wplto/resident-island-seed.prg.elf'
    truth = ElfTruth.read(elf, llvm_readobj=ROOT/'tools/llvm-mos/bin/llvm-readobj')
    address = truth.symbol('C2K_INPUT_EVENTS_TAKEN').value
    assert address == 0xbcff

    class Monitor:
        def __init__(self, *, increment=1, stalled=False):
            self.clock = 0
            self.counter = 254
            self.pending = None
            self.sent = []
            self.increment = increment
            self.stalled = stalled
        def memory_range(self, at, count):
            assert (at,count) == (address,1)
            if self.pending is not None and self.clock >= self.pending and not self.stalled:
                self.counter = (self.counter+self.increment)&255
                self.pending = None
            return bytes([self.counter])
        def queue_one(self, code):
            assert self.pending is None
            self.sent.append(code)
            self.pending = self.clock+20  # longer than old paste wait
        def now(self): return self.clock
        def sleep(self, duration): self.clock += 1
    row = next(r for r in ROWS.LITE if r[0]=='lite-input-641')
    m = Monitor()
    result = ROWS.send_counted(m,row[2],address,now=m.now,sleep=m.sleep)
    assert result['consumed'] == 642 and m.sent.count(13) == 4
    assert len(bytes(m.sent).replace(b'\r',b'\n')[:-1]) == 641
    negative = []
    for label, m in [('stalled',Monitor(stalled=True)),('extra-input',Monitor(increment=2))]:
        try:
            ROWS.send_counted(m,['a'],address,timeout=25,now=m.now,sleep=m.sleep)
        except ROWS.R.ReplayError:
            negative.append(label)
        else:
            raise AssertionError('transport negative survived')

    # Compile only the actual paste state machine; never start Xemu.
    injector = ROOT/'build/nested-error-recovery-ready-instrument-r1/xemu/targets/mega65/inject.c'
    block = function(injector.read_text(), 'if (kbd_hwa_pasting) {')
    cfile = out/'paste-timeout.c'
    cfile.write_text('''#include <stdio.h>
#include <string.h>
static char text[202];
static char *kbd_hwa_pasting;
static int kbd_hwa_pasting_single_case, osd_display_console_log, osd_status;
static int accepted, dropped, errors;
#define OSD_STATIC 1
#define OSD(...) ((void)0)
#define ERROR_WINDOW(...) (++errors)
static void discard(void *p) { dropped=(int)strlen((char *)p)-accepted; }
#define free discard
static const char *hwa_kbd_add_string(const char *s, int mode) {
    (void)mode;
    if (!accepted) { accepted=112; return s+112; }
    return s; /* hardware plus software backlog full during slow Return */
}
static void tick(void) {
'''+block+'''
}
int main(void) {
    memset(text, 'a', 201); text[201]=0; kbd_hwa_pasting=text;
    for (int i=0; i<62; ++i) tick();
    printf("accepted=%d dropped=%d errors=%d busy=%d\\n",accepted,dropped,errors,kbd_hwa_pasting!=0);
    return !(accepted==112 && dropped==89 && errors==1 && !kbd_hwa_pasting);
}
''')
    subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror',str(cfile),'-o',str(out/'paste-timeout')],check=True)
    actual = subprocess.check_output([str(out/'paste-timeout')],text=True).strip()
    log = ROOT/'build/lite-rows-r4/run-rows/xemu.log'
    assert 'ERROR: Pasting did not work through.' in log.read_text()
    H.save(out/'receipt.json', dict(status='PASS', delivery=result, negative_controls=negative,
            counter_address=address, injector=S.bind(injector), native_reproduction=actual,
            reviewer_log=S.bind(log), source=S.bind(Path(ROWS.__file__)),
            scope='Compiled injector state machine with stalled queue seam; singleton counter protocol fake monitor; no emulator run'))


def main():
    assert os.environ.get('PYTHONDONTWRITEBYTECODE') == '1'
    ap = argparse.ArgumentParser()
    ap.add_argument('action', choices=('admission','literals','transport'))
    ap.add_argument('--out', type=Path, required=True)
    args = ap.parse_args()
    globals()[args.action](args.out.resolve())


if __name__ == '__main__':
    main()
