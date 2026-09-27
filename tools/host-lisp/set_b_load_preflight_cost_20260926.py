"""Bound the full-scan cost to exact INIT counts and the existing native leaf."""
import re
from pathlib import Path
import set_b_producer as P
from elf_truth import ElfTruth
from set_b_third_seed_inventory_halt_20260926 import instructions
ROOT=P.ROOT
OUT=ROOT/'build/set-b-load-preflight-cost-r1'

def main():
    OUT.mkdir(exist_ok=False)
    receipt=ROOT/'build/set-b-load-preflight-cl-r1/receipt.json';r=P.load(receipt);assert r['status'].startswith('PASS:')
    rows=P.load(ROOT/'build/set-b-load-preflight-cl-r1/rows.json');scans=next([int(x) for x in row[2].split(',')] for row in rows if row[:2]==['SCANS','exact-init-libraries'])
    assert scans==[785,801,801,804]
    elf=ROOT/'build/set-b-product-r5/wplto/resident-island-seed.prg.elf';t=ElfTruth.read(elf,llvm_readobj=ROOT/'tools/llvm-mos/bin/llvm-readobj')
    symbol=t.symbol('vm_c2d_byte');code,cmd,dis=instructions(elf);by=code[symbol.section];pc=symbol.value;path=[]
    while True:
        row=by[pc];path.append(row);mn=row['mnemonic']
        if mn=='rts':break
        assert mn not in ('bne','bcs'),('unexpected selected path',row)
        if mn=='bcc':pc=int(re.search(r'\$([0-9a-f]+)',row['operand'])[1],16)
        else:pc+=len(bytes.fromhex(row['bytes']))
        assert symbol.value<=pc<symbol.value+symbol.bytes
    # Successful low-address read: first BCC taken (entry bytes below 8430),
    # BEQ after reader not taken; final BCC takes the cheaper byte<128 path.
    assert sum(row['mnemonic']=='jsr' for row in path)==1
    (OUT/'leaf-path.txt').write_text('\n'.join(f"{x['address']:04x}: {x['bytes']} {x['mnemonic']} {x['operand']}" for x in path)+'\n')
    reads=6*sum(scans);floor=reads*len(path)
    assert floor>277701
    P.write(OUT/'receipt.json',dict(status='FULL LISP SCAN EXCEEDS REMAINING COLD ALLOWANCE IN GROSS ADDED WORK',driver=P.bind(Path(__file__)),elf=P.bind(elf),indexed_fixture=P.bind(receipt),
        init=P.bind(ROOT/'build/set-b-seed-medium-r6/base/init.l65'),entry_scan_counts=scans,extra_prim67_byte_reads=reads,
        shortest_successful_leaf_path=P.bind(OUT/'leaf-path.txt'),leaf_instructions=len(path),cycles_per_instruction_floor=1,
        extra_leaf_cycles_at_least=floor,extra_leaf_milliseconds_at_least=floor/40500,
        existing_cold_margin_cycles=277701,existing_cold_margin_milliseconds=277701/40500,
        exclusions='Ignores all VM dispatch, Lisp helpers, allocation/GC, C reader and mapper work. A gross added-cost floor, not a new ELF total or a claim about offsetting layout effects.',
        proposed_native_transport=dict(query_invocations=4,stream_calls=sum(scans)+4,stream_bytes=10*sum(scans)+8*4,old_stream_calls=reads,old_stream_bytes=reads),
        product_builds=0,product_links=0,seeds=0,guest_launches=0,device_contacts=0))
    print('Full scan gross floor',floor,'cycles;',len(path),'instructions/read;',reads,'reads')
if __name__=='__main__':main()
