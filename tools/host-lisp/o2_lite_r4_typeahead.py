#!/usr/bin/env python3
"""Queue typeahead during buffer joins, then consume it at the next prompt.

Host semantic evidence only; IRQ admission is checked against frozen assembly.
No claim of unbounded input capacity or target timing.
"""
import argparse
import os
from pathlib import Path
import o2_lite_r3_host as H
from o2_lite_r4_host import bindings
import host_recycle
B,P=H.B,H.P

def main():
    assert os.environ.get('PYTHONDONTWRITEBYTECODE')=='1'
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True)
    out=ap.parse_args().out.resolve();out.mkdir();before=bindings();suite=H.setup(out)()
    rows=[]
    for size,source in [(260,'"'+'a'*119+'\n'+'b'*138+'"'),(400,'"'+'a'*199+'\n'+'b'*198+'"'),
                        (640,'"'+'a'*199+'\n'+'b'*200+'\n'+'c'*200+'\n'+'d'*36+'"')]:
        assert len(source)==size
        for count in (16,107):
            queued=list(b'z'*(count-1)+b'\r')
            s=dict(suite,cases=[dict(name='typeahead',expr='(progn (%repl-step nil "" 0) (%repl-step nil "" 0))',expect='nil')])
            h,n,c,f,r,b,d,cases,entries,i=P._compile_suite(s)
            abi,ledger=P._suite_abi(s)
            class VM(H.O.VM):
                injected=False
                def _callprim(self,p,argc,stack,**kw):
                    if p==65 and argc and B.is_fix(stack[-1]) and B.fixval(stack[-1])>=260 and not self.injected:
                        self.key_events.extend((key, 0) for key in queued);self.injected=True
                    return super()._callprim(p,argc,stack,**kw)
            vm=VM(heap=h.clone(),directory=d,macro_symbols=P._macro_symbol_objs(h,f,r),max_steps=20000000,
                  key_events=list((source.replace('\n','\r')+'\r').encode()),private_key_event_modes=True,
                  abi_profile=abi,abi_ledger=ledger,batch_cap=107)
            host_recycle.enable(vm)
            answer=vm.heap.obj_to_text(vm.run(d[h.intern(entries[0])],[]))
            assert vm.injected and not vm.key_events and answer=='"'+'z'*(count-1)+'"'
            rows.append(dict(source_bytes=size,injected_events=count,remaining_events=0,passed=True))
    capture=(H.ROOT/'src/optional/c2_kernal_input_capture.s').read_text()
    assert capture.index('beq .Lcapture_commit_done')<capture.index('sta $d619')
    assert 'C2K_INPUT_RING_SLOTS, 108' in (H.ROOT/'src/c2_kernal_window_equates.inc').read_text()
    assert before==bindings()
    H.save(out/'receipt.json',dict(status='PASS',sources=before,rows=rows,ring_slots=108,usable=107,
        full_behavior='No hardware acknowledgement on full ring; pending event stays in hardware queue. Further arrivals can overflow the finite hardware FIFO; no unbounded guarantee.',
        scope='Host queue retention plus capture assembly inspection; no target IRQ/timing claim'))

if __name__=='__main__':main()
