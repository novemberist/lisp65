#!/usr/bin/env python3
"""Read-only closed-root predecessor/seed attribution for buffered repair."""
import json
import f011_buffered_repair_product_card as R
import f011_frame_attribution as A
from evidence_era import stable_recorded_on

def run():
    R.configure();R.C.configure=R.configure
    # Reuse the qualified closed compiler-root algorithm, not diagnostic claims.
    A.D=R
    inputs=R.C.B.profile_inputs(R.BOUND_PROFILE)
    for name in ('io.c','main.c'):
        assert inputs['src/'+name]==R.C.bind(R.ROOT/'src'/name)['sha256']
    source=R.C.load(R.PREFLIGHT_RECEIPT)['profile']
    assert source['changed_authored_roots']==['src/io.c','src/main.c']
    assert source['header_roots']==[R.C.bind(R.H.HEADER)]
    for seed in (True,False):
        result=A.derive(seed)
        result['role']='BUFFERED-F011-REPAIR-PRODUCT'
        for row in result['compiler_roots']:
            if row['family']=='bound diagnostic io/main transforms and seven-byte record header':
                row['family']='authorized buffered wait/mask and removal of temporary instrument'
        result['bound_source_preflight']=R.C.bind(R.PREFLIGHT_RECEIPT)
        out=R.BUILD/('seed-to-final-attribution.json' if seed else 'predecessor-attribution.json')
        result['recorded_on']=stable_recorded_on(out)
        out.write_text(json.dumps(result,indent=2)+'\n')
        print('ATTRIBUTION PASS',out.name,'roots',len(result['compiler_roots']),
              'changed PRG bytes',len(result['PRG_changed_bytes']))

if __name__=='__main__':run()
