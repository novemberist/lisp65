"""Replay reader ABI, consumed include closure, geometry and trace assertions.

Two dependency-only preprocessor invocations; no object compile/link/guest run.
"""
from dataclasses import asdict
from pathlib import Path
import subprocess
import sys
sys.dont_write_bytecode=True
import set_b_producer as P
from elf_truth import ElfTruth
from set_b_read_path_proposal_20260926 import SECTIONS
ROOT=P.ROOT
OUT=ROOT/'build/set-b-read-path-checks-r1'
OBJ=ROOT/'build/set-b-read-path-proposal-r1'
PROPOSAL=ROOT/'build/set-b-read-path-proposal-r5'


def main():
    OUT.mkdir(exist_ok=False)
    dependency_rows=[];closures={};truths={}
    for row in P.load(OBJ/'compile-receipt.json')['compiles']:
        label=row['label'];cc=row['command'].copy();ix=cc.index('-o');del cc[ix:ix+2]
        cc.remove('-c');cc+=['-M','-MT','runtime']
        run=subprocess.run(cc,cwd=ROOT,capture_output=True,text=True)
        log=OUT/(label+'-dependencies.txt');log.write_text(run.stdout+run.stderr)
        assert run.returncode==0,run.stderr
        deps=run.stdout.replace('\\\n',' ').split(':',1)[1].split()
        roots=[];closure={};tree=OBJ/label/'generated-product-sources'
        for raw in deps:
            path=(ROOT/raw).resolve()
            if path.is_relative_to(tree):name='generated/'+str(path.relative_to(tree))
            else:name=str(path.relative_to(ROOT))
            bound=P.bind(path);roots.append(dict(logical=name,binding=bound));closure[name]=bound['sha256']
        dependency_rows.append(dict(label=label,command=cc,exit=run.returncode,log=P.bind(log),inputs=roots))
        closures[label]=closure
        truths[label]=ElfTruth.read(OBJ/label/'005-c2_product_runtime.c.o',llvm_readobj=ROOT/'tools/llvm-mos/bin/llvm-readobj',include_section_data=True)
    assert closures['before'].keys()==closures['after'].keys()
    differences=[n for n in closures['before'] if closures['before'][n]!=closures['after'][n]]
    expected=['generated/optional/set_b_retire_'+n+'.c' for n in ('commit_a','commit_b','commit_c','reset')]
    assert set(differences)==set(expected),differences
    # Exact consumed C prototypes: canonical header has same ABI as the old
    # local declaration, while the callable identity is now the real reader.
    assert 'src/c2_platform_dma.h' in closures['after'] or 'generated/c2_platform_dma.h' in closures['after']
    a,b=truths['before'],truths['after'];abi=[]
    for name in ('rc_read','rm_read','rf_read','c2_retire_reset'):
        x,y=a.symbol(name),b.symbol(name)
        assert x.bytes==y.bytes
        bx=a.section_bytes(x.section)[x.value:x.value+x.bytes]
        by=b.section_bytes(y.section)[y.value:y.value+y.bytes]
        assert bx==by,(name,'ABI or instruction bytes changed')
        def rel(t,s):return [(r.offset-s.value,r.relocation_type,r.target,r.addend) for r in t.relocations if r.source_section==s.section and s.value<=r.offset<s.value+s.bytes]
        before,after=rel(a,x),rel(b,y)
        # Local symbol addends in reset remain invariant; all other
        # relocations remain unchanged except the one physical-read callee.
        assert [(o,k,'c2_map_cpu_read' if n=='c2_facade_runtime_overlay_exec' else n,z) for o,k,n,z in before]==after
        transfer=next(r for r in after if r[2]=='c2_map_cpu_read')
        assert by[transfer[0]-1]==(0x20 if name=='c2_retire_reset' else 0x4c)
        abi.append(dict(name=name,bytes=x.bytes,identical_unrelocated_bytes=True,relocations_before=before,relocations_after=after,after_symbol=asdict(y)))
    p=P.load(PROPOSAL/'receipt.json')
    def geometry(rows):
        at=0
        for r in rows:
            assert r['offset']==at and r['proposed_extent']%32==0
            assert r['proposed_extent']-r['budget']>=16
            at+=r['proposed_extent']
        assert at==6752 and 8192-at==1440
    geometry(p['tenants'])
    rejected=[]
    from copy import deepcopy
    for label in ('16-byte-record','overlap','no-air'):
        rows=deepcopy(p['tenants'])
        if label=='16-byte-record':rows[3]['proposed_extent']-=16
        elif label=='overlap':rows[4]['offset']-=32
        else:rows[3]['budget']=rows[3]['proposed_extent']
        try:geometry(rows)
        except AssertionError:rejected.append(label)
    assert len(rejected)==3
    trace=P.load(ROOT/'build/set-b-read-path-trace-r2/receipt.json')
    assert trace['status']=='PASS: EXECUTED RESET REFUSAL ATTRIBUTION'
    r=trace['result'];steps=trace['steps'];sel=steps[2]
    stack=bytes.fromhex(sel['stack']);sp=sel['sp']&255
    # Selector breakpoint executes PHA before pausing: pushed A, return low,
    # return high sit at SP+1/+2/+3. Original caller identity is C3F6.
    assert stack[sp+1]==0x20 and int.from_bytes(stack[sp+2:sp+4],'little')==0xc3f6
    route=r['selector_steps'];assert route[-2]['pc']==0x2374 and route[-2]['opcode'].startswith('4c002b') and route[-1]['pc']==0x2b00
    assert steps[3]['a']==3 and steps[4]['a']==3
    assert r['destination_before']==r['destination_after']==255 and r['read_destination']==0xcf89
    assert all(s['arm']==0 for s in steps)
    assert [s['ready'] for s in steps]==[0,0,0,0,0,0,1]
    memory=(ROOT/'build/set-b-read-path-trace-r2/run-boot/memory.bin').read_bytes()
    assert memory[0x5de80:0x5fe80]==(ROOT/'build/set-b-product-r3/set-b-tenants.bin').read_bytes()
    assert memory[0x5de20:0x5de68]==bytes(72)
    P.write(OUT/'receipt.json',dict(status='PASS: ABI, INPUT CLOSURE, GEOMETRY AND EXECUTED TRACE',
        driver=P.bind(Path(__file__)),dependency_rows=dependency_rows,input_differences=differences,
        abi=abi,geometry_controls=rejected,trace=P.bind(ROOT/'build/set-b-read-path-trace-r2/receipt.json'),
        seed_tenants_still_identical=True,journal_zero=True,observed_return_identity=0xc3f6,
        first_wrong_dispatch_pc=0x2374,read_result=3,reset_result=3,source_ready_never_cleared_by_repair=True,
        disclaimer='Candidate source/object proof only, not executed repair or whole-product linked proof.',
        new_object_compiles=0,product_links=0,guest_launches=0))
    print('PASS: 4 ABI transfers; only 4 consumed include changes; 3 geometry controls; executed reset refusal',flush=True)

if __name__=='__main__':main()
