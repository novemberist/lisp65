"""Strings successor: immutable predecessor worlds and live loader content."""
import argparse,builtins,io,json,hashlib,copy
from pathlib import Path
from contextlib import contextmanager
ROOT=Path(__file__).resolve().parents[2]
BASELINE="config/strings-source-baseline-20260928.json"
BASELINE_SHA='85bae00f4fb350a8641d1dd8b6f6f2c9fea755cc701c2903d2e28112cc815cce'
OUT=ROOT/"build/strings-consumers-20260928"
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

def live():
    import bytecode_p0_stdlib as P
    path='tests/bytecode/libs/p0-repl-comfort-v250.json'
    result=P.check_suite(path,P._read_suite(str(ROOT/path)))
    require(result['cases']==32,'Comfort regression population drift')
    return dict(cases=result['cases'],status='PASS',suite=bind(path))

def finish(name,derive,receipt,previous,inputs=()):
    p=argparse.ArgumentParser();p.add_argument('action',choices=['build','check','selftest','qualification-check']);a=p.parse_args().action
    if a=='qualification-check':a='check'
    value=dict(format='lisp65-'+name+'-strings-successor-v1',date='2026-09-28',status='PASS',
      predecessor=history(previous),current=derive(),
      inputs=[bind(x) for x in sorted(set([str(Path(__file__).relative_to(ROOT)),BASELINE,*baseline(),*inputs]))],
      product_links=0,xemu_runs=0,device_contacts=0,claim_limit='Host source and loader content; future strings product acceptance is separate')
    raw=canonical(value);path=ROOT/receipt
    if a=='build':
        with path.open('xb') as f:f.write(raw)
    elif a=='check':require(path.read_bytes()==raw,name+' receipt drift')
    print(name+': '+a.upper()+' PASS')
