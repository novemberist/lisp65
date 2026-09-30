"""Seed r2 host batch equivalence, allocation walk and instruction lane."""
import copy


def run(O, suites, out, save):
    from cases import cases, lanes
    from admission import cases as admission, row
    from memory_audit import run_audit
    P, B = O.P, O.B
    burst = [
        row('batch-exact-allowance', list(b'a'*250+b'\r'), 'a'*250),
        row('batch-cross-allowance', list(b'a'*251+b'ok\r'), 'ok', '*** input limit'),
        row('batch-weighted-exact', list(b'"\r'+b'a'*247+b'"\r'), '"\n'+'a'*247+'"'),
        row('batch-weighted-cross', list(b'"\r'+b'a'*249+b'ok\r'), 'ok', '*** input limit'),
        row('batch-after-reopen', list(b'"abc\r')+[20]+list(b'def"\r'), '"abcdef"'),
        row('batch-reopen-cross', list(b'"'+b'a'*249+b'\r')+[20]+list(b'xok\r'), 'ok', '*** input limit'),
    ]
    s = suites()
    rows = [x for x in s['cases'] if x['name'].startswith('comfort-string-')] + cases() + lanes() + admission() + burst

    import host_recycle
    class ReplayVM(O.VM):
        def __init__(self,*a,**kw):
            super().__init__(*a,**kw)
            host_recycle.enable(self)
        def _callprim(self,p,n,stack,**kw):
            if p in (1,2,28,29,60,63,65) and len(self.heap.cells)>14000 and len(self.heap.free)<2000:
                host_recycle.recycle(self,list(stack[-n:]) if n else [])
            return super()._callprim(p,n,stack,**kw)

    def execute(suite, rows, caps):
        suite = copy.deepcopy(suite)
        results=[]
        for case in rows:
            suite['cases'] = [case]
            h,n,c,f,r,b,d,compiled,entries,i = P._compile_suite(suite)
            profile,ledger = P._suite_abi(suite)
            entry=entries[0]
            scalar=None
            for cap in caps:
                vm=ReplayVM(heap=h.clone(),directory=d,macro_symbols=P._macro_symbol_objs(h,f,r),max_steps=20000000,key_events=case['key_events'],private_key_event_modes=True,abi_profile=profile,abi_ledger=ledger,batch_cap=cap)
                width=case.get('model',{}).get('width',80)
                vm.screen_columns=width;vm.screen_cells=[32]*(width*25)
                ans=vm.heap.obj_to_text(vm.run(d[h.intern(entry)],[]))
                output=''.join(map(chr,vm.output_chars))
                assert ans==case['expect'],(case['name'],cap,ans,case['expect'])
                assert not vm.key_events
                if 'notice' in case: assert case['notice'] in output
                visible=(ans,output,vm.screen_cells)
                if scalar is None: scalar=visible
                else: assert scalar==visible,(case['name'],cap,'scalar mismatch')
                points=[step for label,step in vm.boundaries if label=='private-2']
                results.append(dict(name=case['name'],cap=cap,steps=vm.steps,root_peak=vm.root_peak,first_batch_instructions=points[1]-points[0] if len(points)>1 else None,passed=True))
            print('PASS batch equivalence',case['name'],flush=True)
        return results

    results=execute(s, rows, [1,107,None])
    save(out/'batch-equivalence.json', dict(status='PASS',rows=len(rows),runs=len(results),results=results))
    # Audit the exact native backlog cap, plus a continuously replenished ring.
    import memory_audit as M
    original=M.AuditVM.__init__
    walks=[]
    for cap in (107,None):
        def init(self,*args,**kw):
            kw['batch_cap']=cap
            original(self,*args,**kw)
        M.AuditVM.__init__=init
        try:
            audited=run_audit(burst+[c for c in admission() if c['name'] in ('active-250-history-max','pending-max-active-202-history-max')])
            walks.append(dict(cap=cap,rows=audited))
        finally: M.AuditVM.__init__=original
    save(out/'batch-heap.json',walks)
    timing=[row('20-char-batch',list(b'a'*20+b'\r'),'a'*20,history='nil')]
    current=execute(suites(),timing,[1,20])
    baseline=execute(suites(False),timing,[1,20])
    save(out/'batch-instructions.json',dict(status='PASS',unit='executed P0 VM instructions between first and second mode-2 polls; no native cycles',baseline='2.5.1 / sealed STRINGS source',candidate=current,baseline_results=baseline))
