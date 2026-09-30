#!/usr/bin/env python3
"""Sequential r4 host gates plus fast/slow-boundary and lexical witnesses."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import o2_lite_r3_host as H
from o2_lite_r3_host import ROOT, O, P, B, M
import host_recycle

SOURCES = ['lib/stdlib-read-line.lisp','lib/repl-comfort-v250.lisp',
           'lib/lite.lisp','lib/lite-hot.lisp','lib/sexp-depth.lisp',
           'config/comfort-default-plane/libraries/repl-comfort-suite.json']

def bindings():
    return {p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in SOURCES}

def extra(out):
    out.mkdir()
    suites=H.setup(out)
    from admission import row
    rows=[]
    for size in (248,249,250,251,258,259,260):
        # Two admitted lines, total output length straddles the join threshold.
        source='"'+'a'*119+'\n'+'b'*(size-122)+'"'
        assert len(source)==size
        rows.append(row('join-'+str(size),list((source.replace('\n','\r')+'\r').encode()),source))
    for size in (249,250,251):
        line='"'+'a'*(size-2)
        rows.append(row('slice-'+str(size),list((line+'\r').encode())+[20,20]+list(b'"\r'),line[:-1]+'"'))
    # The two target failure fixtures in isolation, with maximal retained history.
    source='(string-length "'+'a'*120+'\n'+'b'*120+'")'
    rows.append(row('target-history-omission-input',list((source.replace('\n','\r')+'\r').encode()),source))
    measured=M.run_audit(rows)
    assert all(r['peaks']['cells']['cells']+520<=1072 and
               r['peaks']['arena']['arena']+2048<=9344 and r['root_peak']<=128 for r in measured)
    H.save(out/'boundaries.json',dict(status='PASS',rows=measured))
    return measured

def lexical(out):
    out.mkdir()
    suite=H.setup(out)()
    old=dict(suite)
    old['sources']=[str(ROOT/'lib/sexp-depth.lisp') if Path(x).name=='lite-hot.lisp' else x for x in suite['sources']]
    old['private_inline_functions']=[x for x in suite['private_inline_functions'] if x!='%sexp-step']
    vms=[]
    for s in (old,suite):
        s=dict(s,cases=[dict(name='lexical',expr='nil',expect='nil')])
        h,n,c,f,r,b,d,cases,entries,i=P._compile_suite(s)
        profile,ledger=P._suite_abi(s)
        vm=O.VM(heap=h.clone(),directory=d,macro_symbols=P._macro_symbol_objs(h,f,r),
                abi_profile=profile,abi_ledger=ledger,max_steps=100000)
        host_recycle.enable(vm)
        vms.append(vm)
    fixtures=[([c],packed) for packed in [-4,-1]+list(range(12))+list(range(40,44)) for c in range(256)]
    fixtures += [(list(text.encode()),packed) for packed in range(12)
                 for text in ['', ';ignored )', '"x\\"y"', ')(', '\\', '((a))', '"x\\', 'a;"(']]
    for codes,packed in fixtures:
        results=[]
        for vm in vms:
            host_recycle.recycle(vm,[])
            args=[vm._list_from_objs(list(map(B.mkfix,codes))),B.mkfix(packed)]
            results.append(vm.run(vm.directory[vm.heap.intern('%sexp-line-state')],args))
        assert results[0]==results[1],(codes,packed,results)
    result=dict(status='PASS',comparisons=len(fixtures),scope='compiled old/new whole-line scanners, every byte and packed state, negative depth, comments and escapes')
    H.save(out/'lexical.json',result)
    return result

def batch_heap(out):
    out.mkdir()
    H.setup(out)
    original=M.AuditVM
    rows=[]
    for cap in (107,None):
        class Audit(original):
            def __init__(self,*args,**kw):
                kw['batch_cap']=cap
                super().__init__(*args,**kw)
            def _trace_native_frame(self,name,code,args,native_base,frame_slots,tail):
                result=super()._trace_native_frame(name,code,args,native_base,frame_slots,tail)
                if name in ('%read-line-loop','%rl-put','%rl-poll','%lt-reopen','%lt-checkpoint'):
                    self.sample(args,native_base,name)
                return result
        M.AuditVM=Audit
        cases=[r for r in H.admission() if r['name'] in
               ('active-250-history-max','pending-640-active-250','reopen-640-long-back-to-first')]
        measured=M.run_audit(cases)
        for row in measured:row['batch_cap']=cap
        rows+=measured
    M.AuditVM=original
    assert len(rows)==6
    assert all(r['peaks']['cells']['cells']+520<=1072 and
               r['peaks']['arena']['arena']+2048<=9344 and r['root_peak']<=128 for r in rows)
    H.save(out/'receipt.json',dict(status='PASS',sources=bindings(),rows=rows))

def copy_heap(out):
    """Price CONS and variadic-frame transients inside new resident copies.

    The inherited walker samples string/buffer primitives. That alone misses
    temporary reverse/append lists which die before the next string primitive.
    """
    out.mkdir()
    H.setup(out)
    original=M.AuditVM
    class Audit(original):
        after_cons=False
        def _trace_instruction(self,name,code,pc,spec,operand):
            if self.after_cons:
                self.sample(label='after copy CONS')
                self.after_cons=False
            copying=any(n in ('string-append','substring') for n in self._trace_stack)
            if copying and spec.mnemonic=='CONS':
                self.sample(label='before copy CONS')
                self.after_cons=True
            if copying and pc==0 and code.flags&B.CO_FLAG_REST:
                self.sample(label='copy rest frame')
            return super()._trace_instruction(name,code,pc,spec,operand)
    M.AuditVM=Audit
    # Publication samples the full actual caller/history/wrapper path.
    H.publication(out)
    from admission import row
    cases=[]
    for size in (249,250,251):
        line='"'+'a'*(size-2)
        cases.append(row('copy-slice-'+str(size),list((line+'\r').encode())+[20,20]+list(b'"\r'),line[:-1]+'"'))
    source='"'+'a'*119+'\n'+'b'*137+'"'
    assert len(source)==259
    cases.append(row('copy-join-259',list((source.replace('\n','\r')+'\r').encode()),source))
    source='"'+'a'*248+'\n'+'b'*8+'"'
    assert len(source)==259
    cases.append(row('copy-join-250-plus-9',list((source.replace('\n','\r')+'\r').encode()),source))
    source='"'+'a'*248+'\n'+'b'*7+'\n\n"'
    assert len(source)==260
    cases.append(row('copy-join-258-plus-lf',list((source.replace('\n','\r')+'\r').encode()),source))
    rows=M.run_audit(cases)
    M.AuditVM=original
    allrows=rows+json.loads((out/'publication.json').read_text())
    status='PASS' if all(r['peaks']['cells']['cells']+520<=1072 and
               r['peaks']['arena']['arena']+2048<=9344 and r['root_peak']<=128 for r in allrows) else 'HALT'
    H.save(out/'receipt.json',dict(status=status,sources=bindings(),rows=allrows))
    if status=='HALT':raise SystemExit(2)

def main():
    assert os.environ.get('PYTHONDONTWRITEBYTECODE')=='1'
    ap=argparse.ArgumentParser();ap.add_argument('action',choices=['all','extra','lexical','batch-heap','copy-heap']);ap.add_argument('--out',type=Path,required=True)
    a=ap.parse_args();a.out=a.out.resolve()
    before=bindings()
    if a.action=='extra': extra(a.out)
    elif a.action=='lexical': lexical(a.out)
    elif a.action=='batch-heap': batch_heap(a.out)
    elif a.action=='copy-heap': copy_heap(a.out)
    else:
        a.out.mkdir()
        for action in ('oracle','baseline','parity','calls','heap','publication','batches'):
            with (a.out/(action+'.log')).open('xb') as log:
                subprocess.run(['nice','-n','18','ionice','-c3','python',str(ROOT/'tools/host-lisp/o2_lite_r3_host.py'),action,'--out',str(a.out/action)],
                               cwd=ROOT,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'),stdout=log,stderr=subprocess.STDOUT,check=True)
            print('PASS',action,flush=True)
        extra(a.out/'boundaries')
        lexical(a.out/'lexical')
        assert bindings()==before,'source changed during host proof'
        H.save(a.out/'receipt.json',dict(status='PASS',sources=before,
             gates=['oracle','baseline','parity','calls','heap','publication','batches','boundaries','lexical']))
    assert bindings()==before

if __name__=='__main__':main()
