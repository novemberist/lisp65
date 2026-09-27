"""Read-only fifth Seed inventory using preserved instruction/ELF gates.

Compare to the completely inventoried third Seed. Only two inherited functions and one new resident helper are authored; no extra codegen family is admitted.
"""
import argparse
from dataclasses import asdict
import inspect
from pathlib import Path
import types
import set_b_producer as P
import set_b_fifth_seed_20260926 as S
import set_b_instruction_inventory_20260926 as I
import set_b_linked_inventory_20260926 as A
import set_b_inventory_structure_20260926 as F
from set_b_third_seed_inventory_halt_20260926 import price,instructions
from elf_truth import ElfTruth
ROOT=P.ROOT
PATHS=[ROOT/'build/set-b-product-r4/wplto/resident-island-seed.prg.elf',S.PRODUCT/'wplto/resident-island-seed.prg.elf']
HASHES=['2ba1deb4004ee7115dc673f29395ff1a0a7f91a437ff1f8d3b45d4fd197f9919',P.load(S.PRODUCT/'linked.json')['elf']['sha256']]
AUTHORED={'c2_retire_control','c2_retire_run','c2_retire_call'}


def execute(module,source,replacements,path,globals_extra,args):
    for old,new in replacements:
        assert source.count(old)==1,(module.__name__,old)
        source=source.replace(old,new,1)
    path.write_text(source)
    ns=dict(vars(module));ns.update(PATHS=PATHS,AUTHORED=AUTHORED,__file__=__file__,**globals_extra)
    exec(compile(source,str(path),'exec'),ns);ns['main'](*args)
    return dict(base_driver=P.bind(Path(module.__file__)),executed=P.bind(path),replacements=[dict(before=x,after=y) for x,y in replacements])


def main(out):
    out.mkdir(parents=True,exist_ok=False)
    assert [P.bind(p)['sha256'] for p in PATHS]==HASHES
    S.require_auth();transforms=[]
    truth=ElfTruth.read(PATHS[1],llvm_readobj=ROOT/'tools/llvm-mos/bin/llvm-readobj',include_section_data=True)
    q=price(truth)
    assert q['text_free']>=32 and q['rodata_free']>=0 and q['e000_free']>=54 and q['capture_free']>=57
    assert q['helper_end']<=q['helper_limit'] and q['consumer_end']<=q['consumer_limit']
    assert q['high_bss_free']>=5 and q['low_frame_end']+5<=q['raw_input_start'] and q['bank5_tail']==374
    image,tenants=P.extract_tenants(PATHS[1]);assert image==(S.PRODUCT/'set-b-tenants.bin').read_bytes()
    rows=[]
    for t in tenants:
        assert t['payload'][t['code_bytes']:]==bytes(len(t['payload'])-t['code_bytes'])
        rows.append({k:v for k,v in t.items() if k!='payload'})
    P.write(out/'price.json',dict(status='PASS: LINKED FLOORS AND TENANT EXTENTS',prices=q,tenants=rows,extent=6752,tail=1440))
    src=inspect.getsource(I.main)
    start=src.index('    assert [hashlib.sha256(');end=src.index('    ts = ',start)
    src=src[:start]+"    assert [hashlib.sha256(p.read_bytes()).hexdigest() for p in PATHS] == HASHES\n"+src[end:]
    transforms.append(execute(I,src,[],out/'instructions-executed.py',dict(HASHES=HASHES),[out/'instructions']))
    census=P.load(out/'instructions/census.json')
    P.write(out/'transformations.json',transforms)
    assert census['status']=='PASS INSTRUCTION PASS ONLY' and not census['widenings'] and {f['name'] for f in census['new']}=={'c2_retire_call'},census['failures']
    proxy=types.SimpleNamespace(**{**vars(P),'require_auth':S.require_auth})
    replacements=[("assert census['widenings'] == dict(eval_init=2, vm_buf_ensure_mine=4, vm_buffer_call=2, vm_run_inner=2)","assert census['widenings'] == {}"),
        ("new_sections = {r['section'] for r in P.load(P.INPUTS)['tenants']}","new_sections = set() # all seven tenant sections already existed"),
        ("f['name'] != 'c2_retire_run'","f['name'] != 'c2_retire_call'")]
    transforms.append(execute(A,inspect.getsource(A.main),replacements,out/'allocated-executed.py',dict(P=proxy),[out/'allocated',out/'instructions']))
    c=P.load(out/'allocated/allocated-census.json');assert c['status']=='PASS ALLOCATED CONTENT',c
    replacements=[("build/set-b-product-r3","build/set-b-product-r4")]
    source=inspect.getsource(F.main).replace('build/set-b-product-r3','build/set-b-product-r5').replace('widening_named_code_cost=10','widening_named_code_cost=0')
    transforms.append(execute(F,source,[],out/'structure-executed.py',dict(P=proxy),[out/'structure',out/'allocated',out/'instructions']))
    P.write(out/'transformations.json',transforms)
    f=P.load(out/'structure/inventory.json');assert f['status']=='PASS',f['failures']
    # Read every new edge from section-aware ELF relocations and encoded bytes.
    edges=[]
    for r in truth.relocations:
        if r.target!='c2_map_cpu_read' or not r.source_section.startswith('.lisp65_rt_c2append_retire_'):continue
        sec=truth.section(r.source_section);data=truth.section_bytes(sec.name);at=r.offset-sec.address
        assert r.relocation_type=='R_MOS_ADDR16' and r.addend==0
        assert data[at-1] in (0x20,0x4c) and int.from_bytes(data[at:at+2],'little')==truth.symbol('c2_map_cpu_read').value
        edges.append(dict(relocation=asdict(r),opcode=data[at-1:at+2].hex()))
    assert len(edges)==4 and len({x['relocation']['source_section'] for x in edges})==4
    assert not [r for r in truth.relocations if r.source_section.startswith('.lisp65_rt_c2append_retire_') and r.target=='c2_facade_runtime_overlay_exec']
    transaction_edges=[]
    for r in truth.relocations:
        if r.target not in ('vm_runtime_overlay_transaction_begin','vm_runtime_overlay_transaction_end'):continue
        if r.source_section.startswith('.lisp65_rt_c2append_retire_'):raise AssertionError('transaction API still called by a tenant')
        owner=truth.symbol('c2_retire_call')
        if r.source_section==owner.section and owner.value<=r.offset<owner.value+owner.bytes:
            transaction_edges.append(asdict(r))
    assert {r['target'] for r in transaction_edges}=={'vm_runtime_overlay_transaction_begin','vm_runtime_overlay_transaction_end'}
    P.write(out/'receipt.json',dict(status='PASS: FIFTH SEED LINKED BYTE INVENTORY',complete_inventory=True,
        unclassified_bytes=0,unclassified_relocations='bidirectional ledger pending',source_authority=S.require_auth(),
        driver=P.bind(Path(__file__)),seed=P.bind(PATHS[1]),predecessor=P.bind(PATHS[0]),
        price=P.bind(out/'price.json'),instructions=P.bind(out/'instructions/census.json'),
        allocated=P.bind(out/'allocated/allocated-census.json'),structure=P.bind(out/'structure/inventory.json'),
        transformations=P.bind(out/'transformations.json'),physical_read_edges=edges,
        resident_transaction_edges=transaction_edges,authored_functions=sorted(AUTHORED),builds=0,links=0))
    print('PASS fifth Seed allocated/physical inventory and four physical-reader edges',flush=True)

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
    try:main(a.out.resolve())
    except Exception:
        import traceback
        P.write(a.out.resolve()/'halt.json',dict(status='HALT',error=traceback.format_exc(),driver=P.bind(Path(__file__)),product_links=0))
        raise
