#!/usr/bin/env python3
"""Sequential r6 host evidence; preserve Claude's probes, redirect only outputs."""
import json, os, subprocess, sys
from pathlib import Path
import o2_lite_r3_host as H
import o2_lite_r4_host as H4
ROOT=H.ROOT
OUT=ROOT/'build/o2-lite-r6-proof'

def run(args, label):
    with (OUT/(label+'.log')).open('x') as log:
        subprocess.run(['nice','-n','19','ionice','-c3',sys.executable,'-B',*map(str,args)],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,check=True)
    print('PASS',label,flush=True)

def validate_review(review):
    before=H4.bindings()
    original=ROOT/'build/external-review-o2-lite-r1'
    heap=json.loads((review/'heap-results.json').read_text())
    root=json.loads((review/'root-results.json').read_text())
    control=json.loads((review/'control-results.json').read_text())
    for r in heap+root['results']+control:
        assert r['peaks']['cells']['cells']+520<=1072
        assert r['peaks']['arena']['arena']+2048<=9344 and r['root_peak']<=128
    assert not root['captures']
    probe=json.loads((review/'probe-results.json').read_text())
    fixed=next(r for r in probe if r['label']=='639-pending-indent-640-submit' and not r['baseline'])
    assert fixed['error'] is None and '***' not in fixed['output'] and len(fixed['answer'])-2==640
    boundary=json.loads((review/'boundary-results.json').read_text())
    for r in boundary:
        assert r['error'] is None and not r['remaining'],r
        if r['label'] in ('string-submit-641','pending-lines-33'):
            assert r['answer']=='"ok"' and '*** input limit' in r['output']
        else:
            assert '*** input limit' not in r['output']
        if r['label'] in ('string-submit-639','string-submit-640'):
            assert len(r['answer'])-2==int(r['label'][-3:])
    for r in probe:
        if r['label']=='history-multiline-comment':
            assert 'unexpected empty input poll' in r['error']
        else:
            assert r['error'] is None,r
    lines=json.loads((review/'line-count-result.json').read_text())
    assert '*** input limit' in lines['output'] # original keys then open a new string and exhaust input
    return dict(status='PASS',sources=before,heap=heap,root=root,control=control,
        original_probes=[str(original/(n+'.py')) for n in ('heap_probe','probe','boundary_probe','root_probe','control_probe')])

def main():
    global OUT
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,default=OUT)
    OUT=parser.parse_args().out.resolve()
    assert os.environ['PYTHONDONTWRITEBYTECODE']=='1'
    OUT.mkdir()
    before=H4.bindings()
    review=OUT/'review';review.mkdir()
    original=ROOT/'build/external-review-o2-lite-r1'
    for name in ('probe.py','heap_probe.py','boundary_probe.py','root_probe.py','control_probe.py','baseline-config.json','baseline-comfort.lisp'):
        (review/name).write_text((original/name).read_text().replace('build/external-review-o2-lite-r1',str(review.relative_to(ROOT))))
    for name in ('heap_probe','probe','boundary_probe','root_probe','control_probe'):
        run([review/(name+'.py')],name)
    H.save(review/'receipt.json',validate_review(review))
    for action in ('oracle','baseline','parity','calls','heap','publication','batches'):
        run(['tools/host-lisp/o2_lite_r3_host.py',action,'--out',OUT/action],action)
    for action in ('extra','lexical','batch-heap','copy-heap'):
        run(['tools/host-lisp/o2_lite_r4_host.py',action,'--out',OUT/action],action)
    run(['tools/host-lisp/o2_lite_r4_cost.py','--out',OUT/'cost'],'cost')
    cost=json.loads((OUT/'cost/cost.json').read_text())
    # R4's 115% ceiling covers its three ordinary probes and the 250-byte
    # single-line case; multiline/reopen costs are separately retained.
    for row in cost['rows']+[r for r in cost['boundaries'] if r['name']=='single-line-250']:
        for phase in ('reader_handoff','result_line','new_empty_prompt'):
            for key in ('library_calls','library_reloads','all_code_reloads','instructions'):
                assert row['r4'][phase][key]<=row['v251'][phase][key]*1.15,(row.get('form'),phase,key)
            assert row['r4'][phase]['buffer_overlays']==0
    for action in ('admission','literals','transport'):
        run(['tools/host-lisp/o2_lite_r5_host.py',action,'--out',OUT/action],action)
    run(['tools/host-lisp/o2_lite_r4_typeahead.py','--out',OUT/'typeahead'],'typeahead')
    assert before==H4.bindings()
    H.save(OUT/'receipt.json',dict(status='PASS',sources=before,review=validate_review(review)['heap'],return_targets='<=115% v251',native_links=0))
if __name__=='__main__':main()
