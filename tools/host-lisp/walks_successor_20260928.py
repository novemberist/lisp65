"""Editor walks authority, trimmed product projection, exclusive dated receipts."""
import hashlib
from unittest.mock import patch
import ide_exit_successor_20260928 as S
from evidence_era import era_blob
from v2_workbench_codemod import _top_level_forms
from bytecode_p0_stdlib import C
ROOT=S.ROOT
AUTH='c8c20a64'
ERA='c8c20a64'
SOURCE='lib/stdlib-read-line.lisp'
SHARED=('%rl-rows','%rl-cut','%rl-move','%rl-put','%rl-dispatch','%rl-end')

def forms(text):
    rows=[(C.parse_one(text[a:b])[1],(a,b,text[a:b],C.parse_one(text[a:b])))
          for a,b in _top_level_forms(text) if text[a:b].startswith('(defun ')]
    S.require(len(dict(rows))==len(rows),'duplicate function')
    return dict(rows)

def transform(text):
    return transform_core(text,era_blob(AUTH+'^',SOURCE).decode(),era_blob(AUTH,SOURCE).decode())

def transform_core(text,before,after):
    old=forms(before)
    new=forms(after)
    product=forms(text)
    edits=[]
    for name in SHARED:
        S.require(name in product,'missing product function: '+name)
        S.require(product[name][3]==old[name][3], 'product predecessor function drift: '+name)
        a,b,_,_=product[name];edits.append((a,b,new[name][2]))
    # The frozen product intentionally omits the idle matcher. Preserve its
    # existing event expression, carrying only the new initialization from poll.
    a,b,_,loop=product['%read-line-loop']
    expected=C.parse_one(old['%read-line-loop'][2])
    event=loop[3][1][0][1]
    S.require(event==C.parse_one('(if (nthcdr 8 state) (%rl-render nil 0 0 0 0 -1) (key-event 1))'), 'trimmed event seam drift')
    trial=C.parse_one(product['%read-line-loop'][2]);trial[3][1][0][1]=C.parse_one('(%rl-poll state)')
    S.require(trial==expected,'trimmed loop has foreign changes')
    poll=new['%rl-poll'][3]
    init=poll[3][2]
    # The initialization's only poll-local reference is s3 (state position).
    def subst(x):
        if x=='s3': return C.parse_one('(cdr (cdr (cdr state)))')
        return [subst(y) for y in x] if isinstance(x,list) else x
    init=subst(init)
    def _emit(x):
        return "("+" ".join(map(_emit,x))+")" if isinstance(x,list) else str(x)
    replacement=new['%read-line-loop'][2].replace('(%rl-poll state)', '(progn '+_emit(init)+' '+_emit(event)+')')
    edits.append((a,b,replacement))
    for a,b,value in sorted(edits,reverse=True):text=text[:a]+value+text[b:]
    return text

def source_proof():
    raw=(ROOT/SOURCE).read_bytes(); expected=era_blob(AUTH,SOURCE)
    S.require(raw==expected,'walks source authority drift')
    for bad in (era_blob(AUTH+'^',SOURCE),expected+b';foreign\n'):
        S.require(bad!=expected,'source mutation survived')
    return dict(authority=AUTH,source=S.bind(SOURCE),mutations_rejected=2)

def finish(name,derive,receipt,history,inputs=()):
    # Restrict the era override to predecessor validation. Inherited consumers
    # retain their own historical eras during derive().
    import argparse
    action=argparse.ArgumentParser();action.add_argument('action',choices=('build','check','selftest'));action=action.parse_args().action
    with patch.object(S,'ERA',ERA): predecessor=S.history(history)
    value=dict(format='lisp65-'+name+'-walks-successor-v1',status='PASS',date='2026-09-28',predecessor=predecessor,source=source_proof(),current=derive(),inputs=[S.bind(p) for p in sorted(set((*inputs,__file__,SOURCE)))],product_links=0,device_contacts=0,xemu_runs=0)
    raw=S.canonical(value);path=ROOT/receipt
    if action=='build':
        with path.open('xb') as f:f.write(raw)
    elif action=='check':S.require(path.read_bytes()==raw,name+' walks receipt drift')
    print(name+': '+action.upper()+' PASS')
