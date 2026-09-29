"""Strings resolver successor; keep all source/index/capacity/rollback mutations."""
import sys, copy, json
from unittest.mock import patch
import c2_require_resolver_gate as H
import strings_successor_r2_20260928 as S
from strings_scratch_20260928 import scratch, normalized
RECEIPT='config/c2-require-resolver-receipt-strings-20260928.json'
HISTORY={'tools/host-lisp/comfort_default_resolver_20260927.py': '462850a50d3c33006875a51e41c76006ff15d5a0d0a05b03a2d0a0b5ef3288e6', 'tests/bytecode/dialect-v2/evidence/architecture-blocks/library-require-resolver-comfort-default-successor-20260927.json': '21abcfb43535a2c3ae3463a0a075c5645e0700d2f62f2fd94437eb549b8a2b16'}
def derive():
    with scratch() as root:
        with patch.object(H,'SUCCESSOR_RECEIPT',root/'receipt.json'),patch.object(H,'BUILD',root/'resolver'),patch.object(H,'stable_recorded_on',lambda p:'2026-09-28'):
            S.require(H.main(record_successor=True)==0,'inherited resolver gate failed')
            value=H.load(H.SUCCESSOR_RECEIPT)
        current=normalized(value,root)
        old=H.load(S.ROOT/'tests/bytecode/dialect-v2/evidence/architecture-blocks/library-require-resolver-comfort-default-successor-20260927.json')
        def projection(v):
            v=copy.deepcopy(v);v.pop('recorded_on');v['authority'].pop('gate')
            v['target_bank2_compile'].pop('manifest')
            def strip(x):
                if isinstance(x,dict):return {k:strip(a) for k,a in x.items() if k not in ('path','content')}
                if isinstance(x,list):return [strip(a) for a in x]
                if isinstance(x,str):return x.replace('build/post-promotion/require-resolver/l65i-v1','@scratch/resolver')
                return x
            return strip(v)
        S.require(projection(current)==projection(old),'resolver semantic continuity drift')
        trial=copy.deepcopy(current);trial['claim_limit']='unauthorized claim'
        S.require(projection(trial)!=projection(old),'resolver continuity mutation survived')
        return current
if __name__=='__main__':
    if len(sys.argv)==1:sys.argv.append('check')
    S.finish('c2-require-resolver',derive,RECEIPT,HISTORY,(__file__,H.__file__,'config/comfort-default-plane/libraries/repl-comfort-suite.json'))
