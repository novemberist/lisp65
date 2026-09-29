"""Paired live editor semantics; full inputs/results/output/framebuffers are retained."""
import sys,json,copy,contextlib
from pathlib import Path
from unittest.mock import patch

import bytecode_p0_stdlib as P
import evidence_era as E
import walks_successor_20260928 as W
ROOT=W.ROOT; OUT=ROOT/'build/walks-r6'
OUT.mkdir(parents=True,exist_ok=True)
sys.setrecursionlimit(30000)
def run(era):
    capture=[]
    original=P._validate_case_io
    def observe(case,vm,*args,**kw):
        validated=dict(case)
        if case['name'].startswith('comfort-'): validated.pop('expect_output_codes',None)
        result=original(validated,vm,*args,**kw)
        capture.append(dict(input=case,output=list(vm.output_chars),screen=list(vm.screen_cells),remaining=vm.key_events))
        return result
    with E.host_source_world(era) if era else contextlib.nullcontext():
        base=P._read_suite(str(ROOT/'tests/bytecode/libs/p0-stdlib-ship-input-wait-base.json'))
        base['cases'] += [dict(name='bound-'+str(n),expr='(read-line)',expect='"'+'a'*min(n,250)+'"',key_events=[97]*n+[13],max_steps=3000000) for n in (249,250,251)]
        resident=P._read_suite(str(ROOT/'tests/bytecode/libs/p0-repl-comfort-v240-resident.json'))
        resident['sources']=[W.SOURCE if x.endswith('/022-product-editor.lisp') else x for x in resident['sources']]+['lib/sexp-depth.lisp']
        resident['functions'] += [name for name in W.forms((ROOT/'lib/sexp-depth.lisp').read_text()) if name not in resident['functions']]
        for name in W.forms((ROOT/W.SOURCE).read_text()):
            if name not in resident['functions']:resident['functions'].append(name)
        rp=OUT/'semantic-resident.json';rp.write_text(json.dumps(resident))
        comfort=P._read_suite(str(ROOT/'tests/bytecode/libs/p0-repl-comfort.json'))
        comfort['resident_suites']=[str(rp)]
        comfort['cases'] += [
            dict(name='history-order',expr='(%repl-read -1 (list "0" "1" "2" "3" "4" "5" "6" "7" "8" "9") 0 0 0)',expect='("0" "1" "2" "3" "4" "5" "6" "7" "8")'),
            dict(name='history-recall-down',expr='(%repl-read "" (list "newest" "older") 0 75 -26)',expect='"newest"',key_events=[145,145,17,13],max_steps=3000000),
            dict(name='history-edit-recalled',expr='(%repl-read "" (list "newest" "older") 0 75 -26)',expect='"newesb"',key_events=[145,20,98,13],max_steps=3000000),
        ]
        results=[]
        with patch.object(P,'_validate_case_io',observe):
            for name,suite in [('editor',base),('comfort',comfort)]:
                print(era,name,flush=True)
                result=P.check_suite(name,suite)
                results.extend([{k:v for k,v in row.items() if k!='object'} for row in result['observations']])
        return dict(observations=results,io=capture)

def derive():
    before=run('c8c20a64^'); after=run(None)
    for label,value in [('before',before),('after',after)]:
        (OUT/('semantic-'+label+'.json')).write_bytes(W.S.canonical(value))
    W.S.require(before==after,'walks behavioral regression: see semantic-before/after.json')
    # Heap object addresses and execution costs are deliberately not observables.
    return dict(cases=len(before['io']),differences=0,
                before_sha256=__import__('hashlib').sha256(W.S.canonical(before)).hexdigest(),
                after_sha256=__import__('hashlib').sha256(W.S.canonical(after)).hexdigest(),
                legacy_output_policy='Original Comfort output expectations retained as metadata; exact pre-walks/current output and framebuffer equality required.',
                mutations=mutation_checks())

def mutation_checks():
    original=P._read_source
    rejected=[]
    for label,path,old,new,suite,case in [
        ('line-bound-251',W.SOURCE,'250','251',
         P._read_suite(str(ROOT/'tests/bytecode/libs/p0-stdlib-ship-input-wait-base.json')),
         dict(name='reject-251',expr='(string-length (read-line))',expect='250',key_events=[97]*251+[13],max_steps=3000000)),
        ('history-cap-11','lib/repl-comfort.lisp','(>= (length history) 10)','(>= (length history) 11)',
         P._read_suite(str(ROOT/'tests/bytecode/libs/p0-repl-comfort.json')),
         dict(name='reject-history-11',expr='(length (%repl-read -1 (list "0" "1" "2" "3" "4" "5" "6" "7" "8" "9") 0 0 0))',expect='9')),
    ]:
        if label.startswith('history'):suite['resident_suites']=[str(OUT/'semantic-resident.json')]
        suite['cases']=[case]
        def changed(name):
            raw=original(name)
            return raw.replace(old,new) if (ROOT/name).resolve()==(ROOT/path).resolve() else raw
        try:
            with patch.object(P,'_read_source',changed):P.check_suite(label,suite)
        except AssertionError as error:
            W.S.require('expected' in str(error),'mutation failed outside result assertion')
            rejected.append(dict(name=label,rejection=str(error)))
        else:raise ValueError('semantic mutation survived: '+label)
    return rejected
