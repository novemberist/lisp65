"""Seal the cache's concrete host preflight before native product compilation."""
import json
from pathlib import Path
import code_object_cache_producer as P
import slice_capacity_preflight as C
from elf_truth import ElfTruth


def main():
    evidence=[]
    def read(path):
        p=P.ROOT/path;evidence.append(P.bind(p));return json.loads(p.read_text())
    host=read('build/code-object-cache-host-r4/receipt.json')
    assert host['status'].startswith('PASS:') and host['mutant_returncode']!=0
    for r in host['inputs']:assert P.bind(Path(r['path']).resolve())['sha256']==r['sha256']
    price=read('build/code-object-cache-price-r5/receipt.json')
    for row in price['rows']:
        for dep in row['inputs']:assert P.bind(P.ROOT/dep['path'])==dep
    assert P.bind(Path(__file__).with_name('code_object_cache_transform.py'))==price['transform']
    delta=price['delta'];e000=delta['.lisp65_c2_kernal_window.c2_resident']
    assert e000<0 and 146-e000>=54
    elf=P.BASE/'wplto/lisp65-c2-substitution-linked.prg.elf'
    evidence.append(P.bind(elf))
    truth=ElfTruth.read(elf,llvm_readobj=P.ROOT/'tools/llvm-mos/bin/llvm-readobj')
    helper=truth.section('.lisp65_c2_kernal_window.input_capture_helper')
    state=truth.section('.lisp65_c2_kernal_window.session_emitter_state')
    contiguous_before=state.address-helper.address-helper.bytes
    contiguous_after=contiguous_before-e000
    assert contiguous_before==27 and contiguous_after>=0, 'contiguous capture gap exhausted'
    ordinary=sum(v for k,v in delta.items() if k.startswith('.text'))
    assert 1354-ordinary>=32
    assert delta['.lisp65_code_cache_key']==2 and delta['.lisp65_code_cache_row']==10
    linker=read('build/code-object-cache-linker-r1/receipt.json');assert linker['status'].startswith('PASS:')
    link=read('build/code-object-cache-link-preprobe-r2/receipt.json');assert link['status']=='PASS' and link['new_findings_count']==0
    edge=read('build/code-object-cache-e000-preprobe-r2/e000-low-edges-receipt.json');assert edge['status']=='PASS' and edge['new_findings_count']==0
    locality=read('build/code-object-cache-locality-lane-r4/locality.json')
    assert all(r['writes']==0 for r in locality['rows'])
    hits=sum(r['slots']['1']['hits'] for r in locality['rows']);lookups=sum(r['slots']['1']['lookups'] for r in locality['rows'])
    assert hits/lookups>.75
    neutral=read('build/code-object-cache-locality-lane-r4/observer-neutrality.json');assert neutral['status']=='PASS'
    ready=read('build/code-object-cache-product-r3-preflight/command-ready.json')
    assert ready['driver']==P.bind(Path(P.__file__))
    for k in ('proof','active_includes','include_controls'):
        r=ready[k];assert P.bind(P.ROOT/r['path'])==r;evidence.append(r)
    world=C.load_world(P.ROOT/'build/put-kit-seed-medium-r1/materialized')
    capacity=[]
    for family,manifest in world['manifests'].items():
        for region in (0,1,2):
            position=0;prior_end=0
            for row in manifest['slices']:
                if row['region_id']!=region:continue
                start=row['source_address']%65536
                # Apply growth to complete slices; retain every already paid gap.
                position=C.align_up(position+start-prior_end,manifest['policy']['payload_alignment'])
                size=row['file_size']+max(0,delta.get(row['section'],0));assert size<=manifest['policy']['max_slice_bytes']
                position+=size;prior_end=start+row['file_size']
            growth=position-prior_end
            owner=world['families'][family][f'region{region}']
            if owner is None:
                assert prior_end==0
                continue
            available=owner['free']
            assert growth<=available,(family,region,growth,available)
            capacity.append(dict(family=family,region=region,growth=growth,remaining=available-growth))
    for p in sorted((P.ROOT/'tools/host-lisp').glob('code_object_cache_*.py')):evidence.append(P.bind(p))
    for p in [P.HERE/'composition.json',P.HERE/'expanded-constructor.py',P.HERE/'linker-scripts-carrier-successor.json']:
        evidence.append(P.bind(p))
    result=dict(status='PASS',authority=P.AUTH,owner_instruction='Dann bitte alle Punkte selbstständig abarbeiten',
        phase='cache native candidate admission',budget_used=dict(seed=0,link=0,final=0),
        projected_e000_free=146-e000,projected_ordinary_text_free=1354-ordinary,
        contiguous_capture_gap_before=contiguous_before,projected_contiguous_capture_gap=contiguous_after,
        low_bss_free=5,high_bss_free=8,capacity=capacity,unique_slots=world['slice_count_unique'],
        locality=dict(hits=hits,lookups=lookups),evidence=evidence,
        limits=['Native placement and latency remain to be measured','Host oracle is not native fault injection','No physical keyboard timing claim'])
    P.PARENT.write_once(P.HERE/'preflight-admission.json',json.dumps(result,indent=2)+'\n');print('PASS cache preflight',capacity)
if __name__=='__main__':main()
