"""O2-lite consumer era: exact source bindings and dated suite declarations."""
import argparse, copy, json, subprocess, sys
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch
import strings_successor_r2_20260928 as S
import evidence_era as E
from strings_scratch_20260928 import scratch, normalized
ROOT = S.ROOT
ERA = 'b3a4e3311defbfa015cd746da625eaa3164f404b'
SUITES = {'tests/bytecode/libs/p0-stdlib-ship-input-wait-base.json': 'tests/bytecode/libs/p0-stdlib-ship-input-wait-base-o2-lite-20260929.json', 'tests/bytecode/libs/p0-stdlib-m65-hw-base.json': 'tests/bytecode/libs/p0-stdlib-m65-hw-base-o2-lite-20260929.json', 'tests/bytecode/libs/p0-v160-comfort-device-delta.json': 'tests/bytecode/libs/p0-v160-comfort-device-delta-o2-lite-20260929.json'}
SOURCES = {'lib/stdlib-read-line.lisp': '5e758c50ac07bbf8e826da15ef274c59c274c8604014825f849b5dfb7743f597', 'lib/repl-comfort-v250.lisp': '138127b73e3cf3fc36844d1e548da75146589f1e5d9aa3bec963d8875669a293', 'lib/lite.lisp': '367d07dc3b5adf8a60c2ad655e9ca2bab867f0b7295a90eae0287c88786d3ffc', 'lib/lite-hot.lisp': '70ae2b48cccdddf8ccfdd0671de20141a391fefcf56586dad1eff2237198c92f', 'lib/sexp-depth.lisp': '05b436332b15c87c7fd5a5edd38c4194392a5e4c3a91a99927f31f617adcebac', 'config/comfort-default-plane/libraries/repl-comfort-suite.json': 'b64e297d15b1da2990f46583d43c5e6fa4a15abc24ff529e752ab7d8d9c5ebe9'}

def validate_sources(rows):
    S.require(rows == SOURCES, 'O2-lite source binding drift')

def controls():
    validate_sources({p:S.bind(p)['sha256'] for p in SOURCES})
    for p in SOURCES:
        trial=dict(SOURCES);trial[p]='0'*64
        try:validate_sources(trial)
        except ValueError:pass
        else:raise ValueError('O2-lite source mutation survived')
    for old,new in SUITES.items():
        before=json.loads((ROOT/old).read_bytes());after=json.loads((ROOT/new).read_bytes())
        expected=copy.deepcopy(before)
        if 'm65' in old:
            expected['extends']=Path(SUITES['tests/bytecode/libs/'+before['extends']]).name
        elif 'v160' in old:
            expected['allow_omitted_defuns'].append({'name': '%rl-empty-backspace', 'reason': 'O2-lite empty-continuation helper is emitted by the live resident editor owner, not the historical v16core delta.'})
        else:
            expected['functions'].append('%rl-empty-backspace')
        S.require(after==expected,'O2-lite suite declaration drift')

@contextmanager
def suites():
    import bytecode_p0_stdlib as P
    original,run=P._suite_path,subprocess.run
    def resolve(path,base_dir=None):
        p=Path(original(path,base_dir)).resolve()
        if E.host_source_commit() is None:
            for old,new in SUITES.items():
                if p==ROOT/old:return str(ROOT/new)
        return str(p)
    def child(command,*args,**kwargs):
        command=list(command)
        if len(command)>1 and command[1]=='tools/host-lisp/bytecode_p0_stdlib.py':
            command[1]='tools/host-lisp/o2_lite_consumers_20260929.py'
        return run(command,*args,**kwargs)
    with patch.object(P,'_suite_path',resolve),patch.object(subprocess,'run',child):yield

def live():
    import bytecode_p0_stdlib as P
    import o2_lite_r3_host as H
    from v11_function_metadata_ide_exit_20260928 import idex_projection, projection_selftest
    controls()
    with scratch() as out:
        H.setup(out)
        frozen=ROOT/'build/o2-lite-r4-slots-preflight/planes'
        S.require((out/'product-editor.lisp').read_bytes()==(frozen/'product-editor.lisp').read_bytes(), 'O2-lite resident projection drift')
        resident=P._read_suite(str(out/'resident.json'))
        P.emit_artifacts(str(out/'resident.json'),resident,str(out/'stdlib-p0'),base_addr=0,artifact_role='stdlib')
        rm=json.loads((out/'stdlib-p0.manifest.json').read_bytes());rb=(out/'stdlib-p0.blob.bin').read_bytes()
        fm=json.loads((frozen/'candidate/stdlib-p0.manifest.json').read_bytes());fb=(frozen/'candidate/stdlib-p0.blob.bin').read_bytes()
        resident_content=idex_projection(rm,rb)
        S.require(resident_content==idex_projection(fm,fb),'O2-lite resident loader content drift')
        rows=[]
        for name,count in [('p0-repl-comfort-v240',20),('p0-repl-comfort-v250',32)]:
            path='tests/bytecode/libs/'+name+'.json'
            suite=P._read_suite(str(ROOT/path));suite['resident_suite']=str(out/'resident.json')
            result=P.check_suite(path,suite)
            S.require(result['cases']==count,'O2-lite regression population drift')
            rows.append(dict(suite=path,cases=count))
        path=ROOT/'config/comfort-default-plane/libraries/repl-comfort-suite.json'
        suite=P._read_suite(str(path));suite['resident_suite']=str(out/'resident.json')
        P.emit_artifacts(str(path),suite,str(out/'repl-comfort'),base_addr=0,artifact_role='disk-lib')
        m=json.loads((out/'repl-comfort.manifest.json').read_bytes());b=(out/'repl-comfort.blob.bin').read_bytes()
        projection_selftest(m,b)
        seed=ROOT/'build/o2-lite-product-r6/media-r6'
        sm=json.loads((seed/'repl-comfort.manifest.json').read_bytes());sb=(seed/'repl-comfort.blob.bin').read_bytes()
        content=idex_projection(m,b)
        S.require(content==idex_projection(sm,sb),'O2-lite Seed loader content drift')
        regressions=review_cases()
        for case in regressions:
            H.O.run(dict(H.O.suites(),cases=[case]))
        return dict(review_cases=[r['name'] for r in regressions],regressions=rows,resident_content=resident_content,library_bytes=len(b),content=content,source_mutations_rejected=len(SOURCES))

def review_cases():
    """Claude's destructive-prefix edits with ten full history entries."""
    from admission import row
    cases=[
        row('history-home-delete-refill250',[145,1]+[4]*250+list(b'z'*250+b'\r'),'z'*250),
        row('reopen-home-delete-refill250',list(b'"'+b'a'*249+b'\r')+[20,1]+[4]*250+list(b'z'*250+b'\r'),'z'*250),
    ]
    first='(progn ;'+'a'*241;second=';'+'b'*246;third=';'+'c'*135
    pending=first+'\n  '+second+'\n  '+third+'\n'
    assert len(pending)==639
    keys=list((first+'\r'+second+'\r'+third+'\r').encode())+[20,20]
    cases += [row('indent-delete-submit640',keys+[41,13],pending+')'),
              row('indent-delete-submit641',keys+[32,41,13]+list(b'ok\r'),'ok','*** input limit')]
    history='(list "('+'\n'*32+')")'
    cases.append(row('history-pending-lf-refusal',[34,13,145,13]+list(b'ok\r'),'ok','*** input limit',history=history))
    cases.append(row('history-complete-32lf',[145,13],'('+'\n'*32+')',history=history))
    return cases


def continuity(current, receipt):
    old=json.loads((ROOT/receipt).read_bytes())
    expected=old.get('current',old)
    S.require(current==expected,'inherited measurement drift')
    trial=copy.deepcopy(current);trial['unexpected-successor-field']=True
    S.require(trial!=expected,'measurement mutation survived')
    return current


def finish(name,derive,receipt,history,inputs=()):
    p=argparse.ArgumentParser();p.add_argument('action',choices=['build','check','selftest','qualification-check']);action=p.parse_args().action
    controls(); S.history(history)
    value=dict(format='lisp65-o2-lite-consumer-successor-v1',date='2026-09-29',status='PASS',
        predecessor=history,current=derive(),inputs=[S.bind(x) for x in sorted(set([str(Path(__file__).relative_to(ROOT)),*SOURCES,*SUITES,*SUITES.values(),*inputs]))],
        product_links=0,xemu_runs=0,device_contacts=0,claim_limit='Host source and bytecode only')
    raw=S.canonical(value);path=ROOT/receipt
    if action=='build':
        with path.open('xb') as stream:stream.write(raw)
    else:
        S.require(path.read_bytes()==raw,name+' O2-lite receipt drift')
    print(name+': '+action.upper()+' PASS')

if __name__=='__main__':
    import bytecode_p0_stdlib as P
    controls()
    with suites():raise SystemExit(P.main())
