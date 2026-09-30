#!/usr/bin/env python3
"""Resident-only O2-lite r3 host proof. A red heap gate forbids Seed production.

Reuses the historical behavioral oracle and allocation walker without modifying
r1/r2 evidence. This is not a target timing or target GC measurement.
"""
import argparse
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'build/multiline-lite-r2'))
import oracle as O
import memory_audit as M
from cases import cases, lanes
from admission import row
P, B = O.P, O.B


def save(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')


def project_editor():
    """Keep the delivered projection except the authorized boundary changes."""
    frozen = ROOT / 'build/strings-r7/seed/plane/candidate/product-editor.lisp'
    before = frozen.read_text()
    live = (ROOT / 'lib/stdlib-read-line.lisp').read_text()
    def form(source, name):
        start = source.index('(defun '+name+' ')
        # Parse/print would rewrite all whitespace; copy this balanced form.
        end = start; depth = 0; quoted = escaped = comment = False
        for end in range(start, len(source)):
            ch = source[end]
            if comment:
                if ch == '\n': comment = False
                continue
            if quoted:
                if escaped: escaped = False
                elif ch == '\\': escaped = True
                elif ch == '"': quoted = False
                continue
            if ch == ';': comment = True
            elif ch == '"': quoted = True
            elif ch == '(': depth += 1
            elif ch == ')':
                depth -= 1
                if depth == 0: return source[start:end+1]
        raise ValueError('unclosed '+name)
    for name in ('%rl-dispatch','%rl-end'):
        before = before.replace(form(before,name),form(live,name),1)
    projected = before+'\n'+form(live,'%rl-empty-backspace')+'\n'
    # Fixed internal slots: preserve the slot-8 suffix-presence test.
    projected = re.sub(r'\(nthcdr (\d+) state\)',
        lambda m: '(cdr '*int(m[1])+'state'+')'*int(m[1]), projected)
    return projected.replace('(cadr event)', '(car (cdr event))')


def setup(out):
    editor = out / 'product-editor.lisp'
    editor.write_text(project_editor())
    resident = P._read_suite(str(ROOT / 'tests/bytecode/libs/p0-repl-comfort-v240-resident.json'))
    resident['sources'] = [str(editor) if x.endswith('/022-product-editor.lisp') else x for x in resident['sources']]
    for name in re.findall(r'\(defun ([^ ]+)', editor.read_text()):
        if name not in resident['functions']:
            resident['functions'].append(name)
    save(out / 'resident.json', resident)
    def suites():
        suite = P._read_suite(str(ROOT / 'tests/bytecode/libs/p0-repl-comfort-v250.json'))
        suite['resident_suite'] = str(out / 'resident.json')
        return suite
    O.suites = M.suites = suites
    return suites


def admission():
    lines = ['"' + 'a'*18] + ['b'*19]*31
    keys = '\r'.join(lines) + '\r'
    pending = '\n'.join(lines) + '\n'
    assert len(pending) == 640
    reopen_all = list(keys.encode()) + [20]
    for line in reversed(lines[1:]):
        reopen_all += [20] * (len(line) + 1)
    reopen_all += list(b'"\r')
    long_lines = ['"'+'a'*249, 'b'*250, 'c'*137]
    assert sum(len(s)+1 for s in long_lines) == 640
    reopen_long = list(('\r'.join(long_lines)+'\r').encode()) + [20]
    for line in reversed(long_lines[1:]):
        reopen_long += [20] * (len(line) + 1)
    reopen_long += [20] + list(b'"\r')
    return [
        row('active-250-history-max', list(b'a'*250+b'\r'), 'a'*250),
        row('resident-cap-saturates-251', list(b'a'*251+b'\r'), 'a'*250),
        row('pending-640-active-250', list((keys+'z'*250+'\rok\r').encode()), 'ok', '*** input limit'),
        row('reopen-640', list(keys.encode())+[20,20]+list(b'"\r'), pending[:-2]+'"'),
        row('reopen-640-back-to-first', reopen_all, lines[0]+'"'),
        row('reopen-640-long-back-to-first', reopen_long, long_lines[0][:-1]+'"'),
        row('submit-640', list(('"'+'a'*199+'\r'+'b'*200+'\r'+'c'*200+'\r'+'d'*36+'"\r').encode()), '"'+'a'*199+'\n'+'b'*200+'\n'+'c'*200+'\n'+'d'*36+'"'),
        row('submit-641-refused', list(('"'+'a'*199+'\r'+'b'*200+'\r'+'c'*200+'\r'+'d'*37+'"\rok\r').encode()), 'ok', '*** input limit'),
        row('pending-lines-33-refused', list(('"\r'+'\r'*32+'ok\r').encode()), 'ok', '*** input limit'),
        row('full-250-with-pending', list(('"\r'+'a'*249+'"\r').encode()), '"\n'+'a'*249+'"'),
        row('full-250-at-32-lines', list(('"\r'+'\r'*31+'a'*249+'"\r').encode()), '"'+'\n'*32+'a'*249+'"'),
        row('history-at-max-recall', [145,13], 'a'*250),
        row('history-251-refused', [], None, '*** history limit', history='(list "'+'x'*251+'")'),
        row('history-11-refused', [], None, '*** history limit', history='(list '+'"x" '*11+')'),
        row('prefix-over-total-refused', list(keys.encode())+[145]+list(b'ok\r'), 'ok', '*** input limit'),
        row('reopen-scan-long-lines', list(('"'+'a'*249+'\r'+'b'*250+'\r').encode())+[20,20]+list(b'"\r'), '"'+'a'*249+'\n'+'b'*249+'"'),
    ]


def heap(suites, out):
    original = M.AuditVM._trace_native_frame
    def trace(self, name, code, args, native_base, frame_slots, tail):
        result = original(self, name, code, args, native_base, frame_slots, tail)
        if name in ('%read-line-loop', '%rl-put', '%rl-poll', '%lt-reopen', '%lt-checkpoint'):
            self.sample(args, native_base, name)
        return result
    M.AuditVM._trace_native_frame = trace
    rows = M.run_audit(admission())
    cells = max(x['peaks']['cells']['cells'] for x in rows)
    arena = max(x['peaks']['arena']['arena'] for x in rows)
    result = dict(status='PASS' if cells+520 <= 1072 and arena+2048 <= 9344 else 'HALT',
                  cells=cells, cell_reserve=520, cell_capacity=1072,
                  cell_shortfall=max(0, cells+520-1072), arena=arena,
                  arena_reserve=2048, arena_capacity=9344,
                  root_peak=max(x['root_peak'] for x in rows), rows=rows)
    save(out / 'heap.json', result)
    return result


def resident_calls(suites, out):
    suite = suites()
    # Every event in this fixture, other than Return, is an ordinary editing key.
    keys = list(b'abc')+[157,29,20,1,20,5]+list(b'd')+[13]
    suite['cases'] = [dict(name='resident-keys',expr='(%repl-step nil "" 0)',expect='"abd"',key_events=keys)]
    h,n,c,f,r,b,d,compiled,entries,i = P._compile_suite(suite)
    profile,ledger = P._suite_abi(suite)
    library = set(n) - set(entries)
    class CallVM(O.VM):
        def __init__(self, *a, **kw):
            self.active_key = None
            self.calls = []
            super().__init__(*a, **kw)
        def _trace_native_frame(self, name, code, args, native_base, frame_slots, tail):
            if self.active_key is not None and name in library:
                self.calls[self.active_key]['library_calls'].append(name)
            return super()._trace_native_frame(name, code, args, native_base, frame_slots, tail)
        def _callprim(self, p, argc, stack, **kw):
            if p == 60 and argc and B.is_fix(stack[-1]) and B.fixval(stack[-1]) == 2:
                if self.active_key is not None:
                    previous=self.calls[self.active_key]
                    previous['instructions']=self.steps-previous.pop('start')
                key = self.key_events[0]
                if isinstance(key, tuple):
                    key = key[0]
                self.active_key = None if key == 13 else len(self.calls)
                if self.active_key is not None:
                    self.calls.append(dict(key=key, library_calls=[],start=self.steps))
            return super()._callprim(p, argc, stack, **kw)
    vm = CallVM(heap=h.clone(),directory=d,macro_symbols=P._macro_symbol_objs(h,f,r),max_steps=3000000,key_events=keys,private_key_event_modes=True,abi_profile=profile,abi_ledger=ledger,batch_cap=1)
    answer = vm.heap.obj_to_text(vm.run(d[h.intern(entries[0])], []))
    assert answer == '"abd"' and not vm.key_events, answer
    assert len(vm.calls) == len(keys)-1 and all(not x['library_calls'] for x in vm.calls), vm.calls
    frozen=json.loads((out/'resident.json').read_text())
    frozen['functions'].remove('%rl-empty-backspace')
    frozen['sources']=[str(ROOT/'build/strings-r7/seed/plane/candidate/product-editor.lisp') if x.endswith('/product-editor.lisp') else x for x in frozen['sources']]
    save(out/'frozen-resident.json',frozen)
    base=json.loads((ROOT/'build/o2-lite-product-r2/emission/baseline/suite.json').read_text())
    base['resident_suite']=str(out/'frozen-resident.json');base['cases']=suite['cases']
    bh,bn,bc,bf,br,bb,bd,bcompiled,bentries,bi=P._compile_suite(base)
    old=CallVM(heap=bh.clone(),directory=bd,macro_symbols=P._macro_symbol_objs(bh,bf,br),max_steps=3000000,key_events=keys,private_key_event_modes=True,abi_profile=profile,abi_ledger=ledger,batch_cap=1)
    assert old.heap.obj_to_text(old.run(bd[bh.intern(bentries[0])],[]))==answer
    deltas=[x['instructions']-y['instructions'] for x,y in zip(vm.calls,old.calls,strict=True)]
    # Only point-zero Backspace enters the new helper, including on nonempty lines.
    assert all(v<=0 for i,v in enumerate(deltas) if i!=7),deltas
    assert deltas[7] <= 10, deltas  # cold hook plus fixed-slot savings
    result = dict(status='PASS',library_objects=sorted(library),keys=vm.calls,library_calls_per_key=0,
                  baseline_keys=old.calls,instruction_deltas=deltas,
                  unit='host VM instructions; no target cycle claim',point_zero_backspace_index=7)
    save(out / 'resident-calls.json', result)
    return result


def return_parity(out):
    """Compare all output bytes and screen cells against the unchanged editor."""
    import hashlib
    fixed=json.loads((out/'resident.json').read_text())
    frozen=dict(fixed,functions=[x for x in fixed['functions'] if x!='%rl-empty-backspace'],
                sources=[str(ROOT/'build/strings-r7/seed/plane/candidate/product-editor.lisp')
                         if x.endswith('/product-editor.lisp') else x for x in fixed['sources']])
    save(out/'frozen-resident.json',frozen)
    keys=list(b'a'*250)+[157,20,29,98,13]
    results=[]
    for name,expr in [('native','(%native-read-line)'),('plain','(read-line)'),
                      ('comfort','(%repl-step nil "" 0)')]:
        visible=[]
        for side in ('frozen','fixed'):
            suite=json.loads((ROOT/'build/o2-lite-product-r2/emission/baseline/suite.json').read_text())
            suite['resident_suite']=str(out/('frozen-resident.json' if side=='frozen' else 'resident.json'))
            suite['cases']=[dict(name=name,expr=expr,expect='"'+'a'*249+'b"',key_events=keys)]
            h,n,c,f,r,b,d,compiled,entries,i=P._compile_suite(suite)
            profile,ledger=P._suite_abi(suite)
            vm=O.VM(heap=h.clone(),directory=d,macro_symbols=P._macro_symbol_objs(h,f,r),
                    max_steps=3000000,key_events=keys,private_key_event_modes=True,
                    abi_profile=profile,abi_ledger=ledger,batch_cap=8)
            answer=vm.heap.obj_to_text(vm.run(d[h.intern(entries[0])],[]))
            assert answer==suite['cases'][0]['expect'] and not vm.key_events
            visible.append(dict(answer=answer,output=vm.output_chars,screen=vm.screen_cells,
                                polls=[dict(cells=x['cells'],output=x['output']) for x in vm.frames]))
        assert visible[0]==visible[1],name
        results.append(dict(session=name,passed=True,output_bytes=len(visible[0]['output']),
                            complete_visible_trace_sha256=hashlib.sha256(json.dumps(visible[0],sort_keys=True).encode()).hexdigest()))
    result=dict(status='PASS',rows=results,comparison='every output byte, final screen cell and pre-poll screen/output snapshot')
    save(out/'return-parity.json',result)
    return result


def publication(out):
    """Reuse the actual publication/reader-handoff oracle with this suite."""
    import runpy
    original = M.save
    M.save = lambda name, value: save(out/name, value)
    try:
        runpy.run_path(str(ROOT/'build/multiline-lite-r2/publication.py'), run_name='__main__')
    finally:
        M.save = original
    rows = json.loads((out/'publication.json').read_text())
    assert all(x['peaks']['cells']['cells']+520 <= 1072 and
               x['peaks']['arena']['arena']+2048 <= 9344 and
               x['root_peak'] <= 128 for x in rows)
    return dict(status='PASS', rows=rows)


def batches(suites, out):
    """Compare full visible results at scalar, native-ring and uncapped input."""
    import hashlib
    import host_recycle
    class Replay(O.VM):
        def __init__(self,*args,**kw):
            super().__init__(*args,**kw)
            host_recycle.enable(self)
        def _callprim(self,p,n,stack,**kw):
            if p in (1,2,28,29,60,63,65) and len(self.heap.cells)>14000 and len(self.heap.free)<2000:
                host_recycle.recycle(self,list(stack[-n:]) if n else [])
            return super()._callprim(p,n,stack,**kw)
    suite=suites()
    rows=[x for x in suite['cases'] if x['name'].startswith('comfort-string-')]+cases()+lanes()+admission()
    results=[]
    for case in rows:
        suite['cases']=[case]
        h,n,c,f,r,b,d,compiled,entries,i=P._compile_suite(suite)
        profile,ledger=P._suite_abi(suite)
        reference=None
        for cap in (1,107,None):
            vm=Replay(heap=h.clone(),directory=d,macro_symbols=P._macro_symbol_objs(h,f,r),
                max_steps=20000000,key_events=case['key_events'],private_key_event_modes=True,
                abi_profile=profile,abi_ledger=ledger,batch_cap=cap)
            width=case.get('model',{}).get('width',80)
            vm.screen_columns=width;vm.screen_cells=[32]*(width*25)
            answer=vm.heap.obj_to_text(vm.run(d[h.intern(entries[0])],[]))
            output=''.join(map(chr,vm.output_chars))
            assert answer==case['expect'] and not vm.key_events,(case['name'],cap,answer)
            if 'notice' in case:assert case['notice'] in output
            visible=(answer,output,vm.screen_cells)
            if reference is None:reference=visible
            else:assert visible==reference,(case['name'],cap)
            results.append(dict(name=case['name'],cap=cap,passed=True,
                visible_sha256=hashlib.sha256(json.dumps(visible).encode()).hexdigest()))
        print('PASS batch parity',case['name'],flush=True)
    result=dict(status='PASS',rows=len(rows),runs=len(results),results=results)
    save(out/'batches.json',result)
    return result


def main():
    assert os.environ.get('PYTHONDONTWRITEBYTECODE') == '1'
    parser=argparse.ArgumentParser()
    parser.add_argument('action', choices=['oracle','baseline','inherited','parity','heap','calls','publication','batches'])
    parser.add_argument('--out', type=Path, required=True)
    args=parser.parse_args()
    args.out.mkdir(parents=True)  # Exclusive, including failed attempts.
    suites=setup(args.out)
    if args.action == 'oracle':
        suite=suites()
        suite['cases']=[x for x in suite['cases'] if x['name'].startswith('comfort-string-')]+cases()+lanes()
        result=O.run(suite)
        save(args.out/'oracle.json',result)
    elif args.action == 'baseline':
        suite=json.loads((ROOT/'build/o2-lite-product-r2/emission/baseline/suite.json').read_text())
        suite['resident_suite']=str(args.out/'resident.json')
        suite['cases']=lanes()+[x for x in cases() if x['name'] in ('native-entry-unchanged','history-unchanged','history-down-empty')]
        result=O.run(suite)
        save(args.out/'baseline.json',result)
    elif args.action == 'inherited':
        frozen=json.loads((args.out/'resident.json').read_text())
        frozen['functions'].remove('%rl-empty-backspace')
        frozen['sources']=[str(ROOT/'build/strings-r7/seed/plane/candidate/product-editor.lisp') if x.endswith('/product-editor.lisp') else x for x in frozen['sources']]
        save(args.out/'frozen-resident.json',frozen)
        suite=json.loads((ROOT/'build/o2-lite-product-r2/emission/baseline/suite.json').read_text())
        suite['resident_suite']=str(args.out/'frozen-resident.json')
        M.suites=lambda: dict(suite)
        result=M.run_audit([row('strings-final-return-250',list(b'a'*250+b'\r'),'a'*250)])
        save(args.out/'inherited.json',result)
    elif args.action == 'parity':
        result=return_parity(args.out)
    elif args.action == 'heap':
        result=heap(suites,args.out)
    elif args.action == 'publication':
        result=publication(args.out)
    elif args.action == 'batches':
        result=batches(suites,args.out)
    else:
        result=resident_calls(suites,args.out)
    print(json.dumps(dict(action=args.action,status=result.get('status') if isinstance(result,dict) else 'PASS'),indent=2))
    if isinstance(result,dict) and result.get('status') == 'HALT':
        raise SystemExit(2)


if __name__ == '__main__':
    main()
