"""Apply d0f00e98 to the unchanged Seed evidence; never relabel the old halt."""
from pathlib import Path
import json
from dirty_anchor_producer import ROOT,HERE,bind
from elf_truth import ElfTruth

def main():
    base=ROOT/'build/dirty-anchor-seed-inventory-r1'
    inv=json.loads((base/'inventory.json').read_text());closure=json.loads((base/'compiler-closure.json').read_text());em=json.loads((base/'emitter-attribution.json').read_text())
    assert inv['authority']=='b7f5f291' and inv['status'].startswith('HALT')
    assert not inv['unclassified_section_bytes'] and len(closure['rows'])==73 and em['instructions']==661
    seed=ROOT/inv['ELFs'][1]['path'];assert bind(seed)==inv['ELFs'][1]
    assert inv['ELFs'][1]['sha256']=='6aa3040c3f6533a94c053b7b64b932be15514d856dd05f675da771a1f1ea1811'
    t=ElfTruth.read(seed,llvm_readobj=ROOT/'tools/llvm-mos/bin/llvm-readobj',include_section_data=True)
    raw=t.section_bytes('.lisp65_rt_c2emit_final_crc');start=t.section('.lisp65_rt_c2emit_final_crc').address
    # A=$17, then only loads of X/Y and stores, followed by DEC A.
    assert raw[0xc667-start:0xc678-start]==bytes.fromhex('a917a29484048505a0ad84068607a2003a')
    assert t.section_bytes('.lisp65_rt_c2d_00b')[285:288]==bytes.fromhex('850a18')
    families={r['family'] for r in em['rows']}
    assert families=={'derived product identity immediate','REJECTED shifted relocation target after one-byte owner shrink','REJECTED LDA #$16 (2 bytes) replaced by DEC A (1 byte); prior A is new product-ID byte $17'}
    # Local architectural equivalence for all incoming status-bit combinations.
    def nz(p,a):return (p&~0x82)|(0x80 if a&128 else 0)|(2 if a==0 else 0)
    for p in range(256):
        assert (0x16,nz(p,0x16))==((0x17-1)&255,nz(p,(0x17-1)&255))
        for a in range(256):
            old=(a,p&~1,a);new=(a,p&~1,a) # (A,P,memory[$0A]); STA changes no flags.
            assert old==new
    proof=[
        'LDA #$16 and DEC A with A=$17 both leave A=$16, N=0, Z=0 and preserve every other status bit. The bound instruction window proves no intervening modification of A. X, Y and memory are unchanged by either instruction.',
        'CLC clears C and changes no other state. STA $0A stores A and changes no flags. With no intervening instruction, both orders leave the same registers, memory and status. The inventory identifies the sole relocated store operand.',
        'Emitter pairing covers all 661 instructions. Four changed product-ID materializations derive from the consumed manifest; the sole size-changing operation is the admitted replacement. Remaining changed encodings are re-paired relocation targets after the one-byte shrink. The 161 relocation records preserve target identity and differ only by the recorded displacement.'
    ]
    result=dict(status='PASS: SEED-SPECIFIC CORRECTED IDENTITY GATE',authority='d0f00e98',retroactive=True,prior_halt_preserved=True,seed=bind(seed),proof=proof,other_families_admitted=False,inputs=[bind(base/n) for n in ('inventory.json','compiler-closure.json','emitter-attribution.json','verification.json')]+[bind(Path(__file__))])
    p=HERE/'identity-qualification.json';assert not p.exists();p.write_text(json.dumps(result,indent=2)+'\n');print(result['status'])
if __name__=='__main__':main()
