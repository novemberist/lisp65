#!/usr/bin/env python3
"""Replay editor-slots measurements and existing authored/product oracles on r4."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import re
import o2_lite_r3_host as H
import o2_lite_r3_price as PRICE
from o2_lite_r4_host import bindings

ROOT = H.ROOT

def main():
    assert os.environ.get('PYTHONDONTWRITEBYTECODE') == '1'
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True)
    args=ap.parse_args();out=args.out.resolve();out.mkdir()
    before=bindings()
    spec=importlib.util.spec_from_file_location('slot_measure',ROOT/'build/editor-slots-r1/measure.py')
    M=importlib.util.module_from_spec(spec);spec.loader.exec_module(M)
    # The pre-slot snapshots retain the r4 resident hook and end fix.
    sources={'working':((out.parent/'editor-before.lisp').read_text(),(ROOT/'lib/stdlib-read-line.lisp').read_text()),
             'product-working':((ROOT/'build/o2-lite-r4-preflight/planes-final/product-editor.lisp').read_text(),H.project_editor())}
    specs=[(p,n,pos,[key]) for p in ('native','comfort') for n in (10,40,70) for pos in (n,n//2) for key in (97,20)]
    results={};prices={};oracles={}
    for world,pair in sources.items():
        results[world]={};prices[world]={}
        for side,source in zip(('before','candidate'),pair):
            path=out/(world+'-'+side+'.lisp');path.write_text(source)
            rows,sizes=M.run(world,path,specs)
            results[world][side]=dict(sizes=sizes,rows=[dict(prompt=x[0],initial_length=x[1],initial_position=x[2],key=x[3][0],**r) for x,r in zip(specs,rows)])
            assert max(sizes.values())<=255
        for a,b in zip(results[world]['before']['rows'],results[world]['candidate']['rows'],strict=True):
            for key in ('cells','position','length','lift','text','screen_writes','answer','final_cells','output'):
                assert a[key]==b[key],(world,key)
        prices[world]={'before':results[world]['before']['sizes'],'candidate':results[world]['candidate']['sizes']}
    suite=H.P._read_suite(str(ROOT/'tests/bytecode/libs/p0-stdlib-ship-input-wait-base.json'))
    for name in re.findall(r'\(defun ([^ ]+)',(ROOT/'lib/stdlib-read-line.lisp').read_text()):
        if name not in suite['functions']:suite['functions'].append(name)
    H.save(out/'authored-suite.json',suite)
    result=H.P.check_suite(str(out/'authored-suite.json'),suite);result.pop('code_by_name',None)
    oracles['authored']=result
    product=H.setup(out)()
    product['cases']=[x for x in product['cases'] if x['name'].startswith('comfort-string-')]+H.cases()+H.lanes()
    oracles['product']=H.O.run(product)
    assert bindings()==before
    H.save(out/'measurements.json',results)
    H.save(out/'oracles.json',oracles)
    H.save(out/'receipt.json',dict(status='PASS',sources=before,paired_rows=48,executions=96,object_sizes=prices,
        measurement_tool=str(ROOT/'build/editor-slots-r1/measure.py'),scope='same 56-byte single-owner load model and existing oracles as editor-slots-r1'))

if __name__=='__main__':main()
