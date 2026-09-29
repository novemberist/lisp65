"""Strings successor: immutable predecessor worlds and live loader content."""
import argparse,builtins,io,json,hashlib,copy
from pathlib import Path
from contextlib import contextmanager
ROOT=Path(__file__).resolve().parents[2]
BASELINE="config/strings-source-baseline-r2-20260928.json"
BASELINE_SHA='5ffa21ce2806310091a17b6e14bed5a99d10f9acb9fa228c35c16fc2d2a1e55a'
OUT=ROOT/"build/strings-r6/consumers"
def canonical(v):return (json.dumps(v,sort_keys=True,indent=2)+"\n").encode()
def require(ok,message):
    if not ok:raise ValueError(message)
def bind(path):
    p=Path(path)
    if not p.is_absolute():p=ROOT/p
    raw=p.read_bytes()
    return dict(path=str(p.relative_to(ROOT)),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
def baseline():
    require(bind(BASELINE)['sha256']==BASELINE_SHA,'baseline snapshot drift')
    value=json.loads((ROOT/BASELINE).read_bytes())
    for p,row in value['files'].items():require(hashlib.sha256(row['text'].encode()).hexdigest()==row['sha256'],'baseline content drift: '+p)
    return value['files']
@contextmanager
def predecessor_world():
    """Exact pre-string inputs only; nested historical eras remain independent."""
    rows=baseline();a,b=builtins.open,io.open
    def opened(original,file,mode='r',*args,**kw):
        if isinstance(file,(str,Path)):
            try:name=str(Path(file).resolve().relative_to(ROOT))
            except ValueError:name=None
            if name in rows:
                require(mode in ('r','rb','rt'),'write to predecessor world')
                raw=rows[name]['text'].encode()
                return io.BytesIO(raw) if 'b' in mode else io.StringIO(raw.decode(kw.get('encoding') or 'utf-8'))
        return original(file,mode,*args,**kw)
    builtins.open=lambda *a_,**kw:opened(a,*a_,**kw)
    io.open=lambda *a_,**kw:opened(b,*a_,**kw)
    try:yield
    finally:builtins.open,io.open=a,b

def history(rows):
    actual={p:bind(p)['sha256'] for p in rows}
    require(actual==rows,'immutable predecessor drift')
    rejected=0
    for p in rows:
        trial=dict(actual);trial[p]='0'*64
        require(trial!=rows,'predecessor mutation survived');rejected+=1
    return dict(commit='a0caffea3aa791b6ced30102aa068323166508e7',sha256=actual,mutations_rejected=rejected)

def project_editor(text):
    from walks_successor_20260928 import forms
    old=forms(text)['%rl-end'][2]
    new=old.replace('(if (< row -2)', '(if (or (< row -2) (numberp (car (nthcdr 9 state))))',1)
    new=new.replace('(%rl-screen-tail nil 0 0 -1', '(%rl-screen-tail nil 0 (* (car (nthcdr 6 state)) (+ (car (nthcdr 5 state)) 1)) -1',1)
    new=new.replace('(write-string (if (< row -34) "lisp65> " "l65> "))', '(if (< row -2) (write-string (if (< row -34) "lisp65> " "l65> ")) nil)',1)
    require(new!=old,'resident projection already applied or seam missing')
    # The same exact edit must reproduce the revised authored function.
    before=baseline()['lib/stdlib-read-line.lisp']['text']
    authored=forms((ROOT/'lib/stdlib-read-line.lisp').read_text())['%rl-end'][3]
    if text != before:
        require(forms(project_editor(before))['%rl-end'][3]==authored,'authored Return delta drift')
    return text.replace(old,new)

@contextmanager
def live_world():
    """Fresh generated closure plus revised resident projection; no oracle edits."""
    import bytecode_p0_stdlib as P
    import v2_workbench_codemod as C
    from unittest.mock import patch
    out=OUT/'live';out.mkdir(parents=True,exist_ok=True)
    C.generate(C.DEFAULT_CLOSURE,out/'generated')
    resident=ROOT/'tests/bytecode/libs/p0-repl-comfort-v240-resident.json'
    frozen=json.loads((ROOT/'build/walks-product-r1/plane/candidate/stdlib-p0.manifest.json').read_bytes())
    value=P._read_suite(frozen['suite'])
    editor,=[p for p in value['sources'] if '(defun %rl-end ' in (ROOT/p).read_text()]
    target=out/'product-editor.lisp';target.write_text(project_editor((ROOT/editor).read_text()))
    value['sources']=[str(target) if p==editor else p for p in value['sources']]
    rp=out/'resident.json';rp.write_text(json.dumps(value,indent=2)+'\n')
    original=P._suite_path
    def resolve(path,base_dir=None):
        p=Path(original(path,base_dir)).resolve()
        if p==resident:return str(rp)
        if p.is_relative_to(C.DEFAULT_OUTPUT.resolve()):return str(out/'generated'/p.relative_to(C.DEFAULT_OUTPUT.resolve()))
        return str(p)
    with patch.object(P,'_suite_path',resolve):yield

def live():
    import bytecode_p0_stdlib as P
    rows=[]
    with live_world():
        for name,count in [('p0-repl-comfort-v240',20),('p0-repl-comfort-v250',32)]:
            path='tests/bytecode/libs/'+name+'.json'
            result=P.check_suite(path,P._read_suite(str(ROOT/path)))
            require(result['cases']==count,'Comfort regression population drift')
            rows.append(dict(cases=result['cases'],status='PASS',suite=bind(path)))
    return rows

def finish(name,derive,receipt,previous,inputs=()):
    p=argparse.ArgumentParser();p.add_argument('action',choices=['build','check','selftest','qualification-check']);a=p.parse_args().action
    if a=='qualification-check':a='check'
    value=dict(format='lisp65-'+name+'-strings-successor-v1',date='2026-09-28',status='PASS',
      predecessor=history(previous),current=derive(),
      inputs=[bind(x) for x in sorted(set([str(Path(__file__).relative_to(ROOT)),BASELINE,*baseline(),'tests/bytecode/libs/p0-repl-comfort-v240.json','tests/bytecode/libs/p0-repl-comfort-v250.json',*inputs]))],
      product_links=0,xemu_runs=0,device_contacts=0,claim_limit='Host source and loader content; future strings product acceptance is separate')
    raw=canonical(value);path=ROOT/receipt
    if a=='build':
        with path.open('xb') as f:f.write(raw)
    elif a=='check':require(path.read_bytes()==raw,name+' receipt drift')
    print(name+': '+a.upper()+' PASS')
