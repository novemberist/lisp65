#!/usr/bin/env python3
"""Target transport cost witness, not a cycle simulator.

Count library entries (CALL/TAILCALL), single-owner code buffer acquisitions,
and buffer overlay invocations. src/vm.c vm_buffer_call invalidates that owner
on every primitive 63..65, including byte writes, and intern (68). The 128-byte
OBJ_SETUP/WIN_ENSURE windows and two header loads on return are counted too.
Native execution cycles are not estimated. Evaluation is replaced
by a fixed identical result on both sides; reader and output run normally.
"""
import argparse
from collections import Counter
import json
import os
from pathlib import Path
import o2_lite_r3_host as H
from o2_lite_r3_host import O, P, B, ROOT
import host_recycle

class Finished(Exception): pass

class CostVM(O.VM):
    def __init__(self, *args, library, result, **kw):
        self.library = set(library)
        self.answer = result
        self.measuring = False
        self.owner = None
        self.entry_name = None
        self.window = (0,0)
        self.geometry = {}
        self.entries = Counter()
        self.loads = Counter()
        self.entry_loads = Counter()
        self.return_loads = Counter()
        self.refills = Counter()
        self.overlays = Counter()
        self.marks = {}
        self.events = []
        self.event_key = None
        self.event_start = None
        self.start = 0
        super().__init__(*args, **kw)
        host_recycle.enable(self)

    def snapshot(self):
        return dict(library_calls=sum(self.entries.values()),
                    library_calls_by_object=dict(self.entries),
                    library_reloads=sum(v for k,v in self.loads.items() if k in self.library),
                    all_code_reloads=sum(self.loads.values()),
                    payload_refills=sum(self.refills.values()),
                    code_load_operations=sum(self.entry_loads.values())+2*sum(self.return_loads.values())+sum(self.refills.values()),
                    reloads_by_object=dict(self.loads),
                    buffer_overlays=sum(v for k,v in self.overlays.items() if k!='68'),
                    intern_overlays=self.overlays.get('68',0),
                    buffer_overlays_by_primitive=dict(self.overlays),
                    instructions=self.steps-self.start)

    def _trace_native_frame(self,name,code,args,native_base,frame_slots,tail):
        if self.measuring and name in self.library:
            self.entries[name] += 1
        # A target CALL/TAILCALL establishes a new activation and loads code.
        self.owner = None
        self.entry_name = name
        return super()._trace_native_frame(name,code,args,native_base,frame_slots,tail)

    def _trace_instruction(self,name,code,pc,spec,operand):
        if id(code) not in self.geometry:
            header=len(code.encode())-len(code.payload)
            self.geometry[id(code)]=(len(code.payload),128-header)
        length,capacity=self.geometry[id(code)]
        assert capacity>=3
        if self.owner != name:
            entry=self.entry_name==name
            if self.measuring:
                self.loads[name] += 1
                (self.entry_loads if entry else self.return_loads)[name] += 1
            self.window=(0,min(length,capacity)) if entry else (pc,0)
            self.owner = name
            self.entry_name = None
        start,size=self.window
        if pc<start or start+size<min(pc+3,length):
            if self.measuring:self.refills[name]+=1
            self.window=(pc,min(length-pc,capacity))
        return super()._trace_instruction(name,code,pc,spec,operand)

    def _call(self,code,lit_idx,argc,stack,**kw):
        sym = self._callee_symbol(code,lit_idx)
        if self.heap.symbolp(sym) and self.heap.symbol_name(sym) == 'lcc-run':
            self._pop_args(argc,stack)
            self.marks['reader_handoff'] = self.snapshot()
            # This common phase is outside the transport comparison.
            return self.answer(self)
        answer = super()._call(code,lit_idx,argc,stack,**kw)
        if self.heap.symbolp(sym) and self.heap.symbol_name(sym)=='terpri' and 'reader_handoff' in self.marks:
            self.marks['result_line'] = self.snapshot()
        return answer

    def _callprim(self,p,n,stack,**kw):
        if p == 60 and n and B.is_fix(stack[-1]) and B.fixval(stack[-1]) == 2:
            if self.measuring and self.event_key in (13,20):
                now=self.snapshot()
                self.events.append(dict(key=self.event_key,**{k:now[k]-self.event_start[k]
                    for k in ('library_calls','library_reloads','all_code_reloads','buffer_overlays','instructions')}))
            if self.measuring and not self.key_events:
                self.marks['new_empty_prompt'] = self.snapshot()
                raise Finished()
            key = self.key_events[0] if self.key_events else None
            if isinstance(key, tuple): key = key[0]
            if key == 13 and not self.measuring:
                self.measuring=True
                self.start=self.steps
            if self.measuring:
                self.event_key=key
                self.event_start=self.snapshot()
        if self.measuring and p in (63,64,65,68):
            self.overlays[str(p)] += 1
            self.owner=None
        if p in (1,2,28,29,60,63,65) and len(self.heap.cells)>14000 and len(self.heap.free)<2000:
            host_recycle.recycle(self,list(stack[-n:]) if n else [])
        return super()._callprim(p,n,stack,**kw)


def run(suite, form, result, keys=None, history=()):
    initial='(list '+' '.join(json.dumps(s) for s in history)+')' if history else 'nil'
    suite=dict(suite,cases=[dict(name='return-cost',expr='(%repl-loop '+initial+')',expect='nil')])
    h,n,c,f,r,b,d,compiled,entries,i=P._compile_suite(suite)
    profile,ledger=P._suite_abi(suite)
    vm=CostVM(heap=h.clone(),directory=d,macro_symbols=P._macro_symbol_objs(h,f,r),
        max_steps=20000000,key_events=keys if keys is not None else list((form.replace('\n','\r')+'\r').encode()),private_key_event_modes=True,
        abi_profile=profile,abi_ledger=ledger,batch_cap=1,library=set(n)-set(entries),result=result)
    try:
        vm.run(d[h.intern(entries[0])],[])
        raise AssertionError('missing next prompt')
    except Finished: pass
    assert not vm.key_events and 'reader_handoff' in vm.marks and 'result_line' in vm.marks
    vm.marks['events']=vm.events
    return vm.marks


def main():
    assert os.environ.get('PYTHONDONTWRITEBYTECODE')=='1'
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True)
    a=ap.parse_args();a.out=a.out.resolve();a.out.mkdir(parents=True)
    from o2_lite_r4_host import bindings
    before=bindings()
    current=H.setup(a.out)()
    frozen=json.loads((a.out/'resident.json').read_text())
    frozen['functions'].remove('%rl-empty-backspace')
    frozen['sources']=[str(ROOT/'build/strings-r7/seed/plane/candidate/product-editor.lisp') if x.endswith('/product-editor.lisp') else x for x in frozen['sources']]
    H.save(a.out/'frozen-resident.json',frozen)
    baseline=json.loads((ROOT/'build/o2-lite-product-r2/emission/baseline/suite.json').read_text())
    baseline['resident_suite']=str(a.out/'frozen-resident.json')
    r3=dict(current, resident_suite=str(ROOT/'build/o2-lite-r3-slice-preflight/planes/resident.json'))
    r3suite=json.loads((ROOT/'build/o2-lite-r4-preflight/source-r3/suite.json').read_text())
    r3.update({k:r3suite[k] for k in ('functions','tailcall_self','private_inline_functions')})
    r3['sources']=[str(ROOT/'build/o2-lite-r4-preflight/source-r3'/Path(x).name) if Path(x).name in ('lite.lisp','repl-comfort-v250.lisp') else x for x in current['sources']]
    r3['sources']=[str(ROOT/'lib/sexp-depth.lisp') if Path(x).name=='lite-hot.lisp' else x for x in r3['sources']]
    import o2_lite_r3_price as PRICE
    assert PRICE.measure(r3)==json.loads((ROOT/'build/o2-lite-r3-slice-preflight/planes/price.json').read_text())['library']
    rows=[]
    history=[]
    for form,result in [('(+ 1 2)',lambda vm:B.mkfix(3)),
                        ('(list 1 2 3)',lambda vm:vm._list_from_objs(list(map(B.mkfix,[1,2,3])))),
                        ('(string-length "'+'a'*40+'")',lambda vm:B.mkfix(40))]:
        row=dict(form=form,initial_history=list(history))
        for side,suite in [('v251',baseline),('r3',r3),('r4',current)]:
            row[side]=run(suite,form,result,history=history)
            print(form,side,{phase:{k:v for k,v in data.items() if not isinstance(v,dict)} for phase,data in row[side].items() if phase!='events'},flush=True)
        assert row['r3']['new_empty_prompt']['buffer_overlays']==2*len(form)+13
        rows.append(row)
        history.insert(0,form)
    boundaries=[]
    large='"'+'a'*199+'\n'+'b'*200+'\n'+'c'*200+'\n'+'d'*36+'"'
    assert len(large)==640
    for label,form,keys in [('multiline-short','(+ 1\n2)',None),
                            ('reopen-short','(+ 1 2)',list(b'(+ 1\r')+[20,20,20]+list(b' 2)\r')),
                            ('single-line-250','(string-length "'+'a'*232+'")',None),
                            ('large-form-260','"'+'a'*119+'\n'+'b'*138+'"',None),
                            ('large-form-400','"'+'a'*199+'\n'+'b'*198+'"',None),
                            ('large-form-640',large,None)]:
        result=lambda vm:vm.heap.string_from_text(form[1:-1]) if label.startswith('large-form-') else B.mkfix(232 if label=='single-line-250' else 3)
        values={side:run(suite,form,result,keys) for side,suite in [('r3',r3),('r4',current)]}
        if label!='reopen-short':values['v251']=run(baseline,form,result,keys)
        boundaries.append(dict(name=label,form=form,**values))
        print(label,{side:v['events'] for side,v in values.items()},flush=True)
    assert before==bindings(),'source changed during cost proof'
    H.save(a.out/'cost.json',dict(status='MEASURED',sources=before,rows=rows,boundaries=boundaries,
        scope='Return through actual reader; identical stubbed evaluation; real output and next empty prompt',
        limitation='Counts are transport events, not target cycles; common evaluation is stubbed.'))

if __name__=='__main__': main()
