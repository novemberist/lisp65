"""Historical Link-82 reconstruction with frozen carrier and semantic receipts.

Raw encoded hashes include heap literal words. Keep all payloads/literal
specifications, names, arities, window rows and outcomes; omit only encoded
hashes and the aggregate digests that transitively include them.
"""
import copy
from pathlib import Path
from unittest.mock import patch
import c2_v16_defstruct_phase_a as H
import evidence_era as E
import walks_successor_20260928 as W
ERA='a0dc9ba6'
ARCHIVE=W.ROOT/'build/release-v1.4.0/smoke-source-ce2e8bdc'
FROZEN=[H.COMPILER_MANIFEST,H.COMPILER_TIER,W.ROOT/'build/post-promotion/phase-v/while/gate/carrier/lcc.blob.bin']
RECEIPT='config/c2-v16-defstruct-phase-a-receipt-walks-20260928.json'
HISTORY={'tools/host-lisp/c2_v16_defstruct_phase_a.py': '5ffba2d869c56b54f0aabf0088a5abf1cb82e6c7efa7359f06d3220a826d5472', 'tests/bytecode/dialect-v2/evidence/architecture-blocks/c2.3-v1.6-defstruct-phase-a-host-reconstruction-receipt.json': '10dc7b68f9bb21afaddb96af59c54f5ac38ffdf475b0e64e97df7ea59653c4d0'}
DERIVED={'encoded_sha256','semantic_sha256','code_semantic_sha256','projection_sha256','schedule_sha256','event_sha256'}
def projection(value,path=()):
    if isinstance(value,list):return [projection(x,path+(str(i),)) for i,x in enumerate(value)]
    if not isinstance(value,dict):return value
    return {k:projection(v,path+(k,)) for k,v in value.items()
            if k not in DERIVED and not (k=='sha256' and path in
            [('windowed_sequence','refill_schedule'),('windowed_sequence','initial_window_schedule')])}

def derive():
    original=Path.open
    used=set()
    def opened(path,mode='r',*args,**kwargs):
        if path in FROZEN:
            W.S.require(mode in ('r','rt','rb'),'historical artifact write')
            used.add(str(path.relative_to(W.ROOT)))
            return original(ARCHIVE/path.relative_to(W.ROOT),mode,*args,**kwargs)
        return original(path,mode,*args,**kwargs)
    extras=[str(p.relative_to(W.ROOT)) for p in [H.GATES,H.PLAN,H.WHILE_RECEIPT,Path(H.__file__)]]
    with E.host_source_world(ERA,extras) as reads,patch.object(Path,'open',opened):
        H.validate_window_authority();H.carrier_binding_selftest()
        current=H.build_receipt()
        old=H.load(H.RECEIPT)
        W.S.require(projection(old)==projection(current),'historical semantic reconstruction drift')
    expected=projection(current)
    pointer=copy.deepcopy(current)
    pointer['windowed_sequence']['forms'][0]['code']['encoded_sha256']='0'*64
    W.S.require(projection(pointer)==expected,'allocator words affected semantic projection')
    for field in ('payload_hex','literals'):
        mutant=copy.deepcopy(current);mutant['windowed_sequence']['forms'][0]['code'][field]='corrupt'
        W.S.require(projection(mutant)!=expected,'code/literal mutation escaped projection')
    mutant=copy.deepcopy(current);mutant['windowed_sequence']['refill_schedule']['count']+=1
    W.S.require(projection(mutant)!=expected,'window mutation escaped projection')
    return dict(historical_era=ERA,era_reads=reads,archived_inputs=[W.S.bind(ARCHIVE/p) for p in sorted(used)],
                loader_independent_reconstruction=expected,projection_mutations=4,
                claim_limit='Exact historical Link-82 host reconstruction; no walks product claim')
if __name__=='__main__':
    W.finish('c2-v16-defstruct-phase-a',derive,RECEIPT,HISTORY,(__file__,H.__file__))
