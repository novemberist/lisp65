"""Storage-owner host admission. Never starts a product compiler or linker."""
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
import argparse
import hashlib
import json
import re
import subprocess

from elf_truth import ElfTruth
import symbol_layout_manifest as layout
import c2_v21_cpu_transport_preflight as transport
import c2_v21_map_mask_fix as mask

ROOT = Path(__file__).resolve().parents[2]
READOBJ = ROOT/'tools/llvm-mos/bin/llvm-readobj'

def bind(path):
    raw = path.read_bytes()
    return dict(path=str(path.relative_to(ROOT)),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())

def require(value, message):
    if not value: raise ValueError(message)

def measured_user_code_target(m):
    """The legacy floors key holds a measured currency target, not an owner wall."""
    witness = m.get('user_code_measurement')
    require(isinstance(witness, dict) and witness.get('kind') ==
            'executed-final-target-not-owner-floor', 'executed user-code witness absent')
    path = (ROOT/witness['path']).resolve()
    require(path.is_relative_to(ROOT/'tests/bytecode/dialect-v2/evidence/architecture-blocks'),
            'user-code witness escaped the evidence population')
    raw = path.read_bytes()
    require(len(raw) == witness['bytes'] and hashlib.sha256(raw).hexdigest() == witness['sha256'],
            'executed user-code witness drift')
    value = json.loads(raw)
    require(value['status'] == 'PASS: EXECUTED FINAL CURRENCY'
            and value['authority'] == witness['authority'], 'user-code witness is not an executed Final')
    measured = value['measured']
    front = max(row['end'] for row in measured['records'])
    require(front == measured['persistent_front'] and measured['limit'] == m['bank2_code_limit'],
            'user-code witness uses a different code owner')
    target = measured['limit']-front
    require(0 <= target == value['free']['code'], 'user-code target is not the measured contiguous remainder')
    return target

def geometry(m, elf):
    d = layout.values(m)
    require(d['MAX_SYM'] == 1008 and d['NAMEPOOL'] == 16351, 'bound symbol capacities')
    require(d['SYMPOOL_EXT_BANK'] == 1 and d['SYMPOOL_EXT_OFF'] == 0xc000, 'Bank-1 ruling')
    require(d['SYMFN_EXT_BANK'] == d['SYMVAL_EXT_BANK'] == d['NAMEOFF_EXT_BANK'] == 5, 'three Bank-5 tables')
    carrier = elf.symbol('__card2b_carrier_start').value-0x20000
    require(d['LISP65_C2_BANK2_CODE_LIMIT'] == carrier, 'carrier-derived code limit')
    low = elf.section('.noinit.lisp65_f011_status')
    low_end = low.address+low.bytes
    inp = elf.section('.lisp65_c2_input_raw_owner')
    meta = elf.section('.lisp65_c2_symbol_metadata_bss')
    frame = elf.section('.lisp65_vm_soft_frames_bss')
    f = m['soft_frames']
    require(f['count']==16 and f['frame_bytes']==9 and f['depth_bytes']==2, 'R2 frame contract')
    require(f['preceding_floor']>=5 and f['following_floor']>=5, 'low BSS floors')
    size = f['count']*f['frame_bytes']+f['depth_bytes']
    require(size == frame.bytes, 'consumed R2 owner size')
    start = low_end+f['preceding_floor']
    require(start+size+f['following_floor'] <= inp.address, 'low BSS capacity')
    n = d['MAX_SYM']; metadata_size = (n+1)//2+2*((n+7)//8)+2
    require(meta.address+metadata_size+m['floors']['high_bss'] <= 0xc000, 'high BSS floor')
    require(m['floors']['high_bss'] >= 5, 'high floor weakened')
    # The manifest floor is the bytes that must stay free *behind* the
    # boot-time name index (src/c2_platform_dma.c, C2_BNX_EXT_* near line
    # 302): 1,024-slot index (2,048 B) + 1,024-entry queue (6,144 B) +
    # 10-byte resume header = 8,202 B, live only while the boot decoder
    # alternates phases 10a/10b. Checking the raw manifest floor against a
    # frozen constant (formerly ">= 8576") went stale the moment that
    # transient owner was carved out of the same free tail; the measured
    # free region taken from the ELF must now cover the floor plus the
    # owner, so a manifest that claims more headroom than is actually free
    # once the owner is seated (e.g. reverting to the pre-owner 8,576
    # floor) is rejected instead of silently accepted.
    bnx_transient_owner_bytes = 8202
    measured_bank5_free = 65536-(d['SYMFN_EXT_OFF']+n*2)
    require(measured_bank5_free >= m['floors']['bank5_free']+bnx_transient_owner_bytes,
            'Bank-5 floor weakened')
    require(m['floors']['user_code']==measured_user_code_target(m), 'executed user-code target drift')
    require(m['floors']['symbols']==245 and m['floors']['names']==5442,
            'symbol and name acceptance floors')
    return dict(definitions=d,soft_frames=dict(start=start,bytes=size,preceding=start-low_end,
        following=inp.address-start-size),metadata=dict(start=meta.address,bytes=metadata_size,
        following=0xc000-meta.address-metadata_size),
        zero_interval=[elf.symbol('__bss_start').value,meta.address+metadata_size],
        zero_store_delta=meta.address+metadata_size-elf.symbol('__bss_end').value,
        bank5_free=measured_bank5_free)

def relocation_proof(elf, obj):
    owner = obj.section('.lisp65_vm_soft_frames_bss')
    by_index = {s.index:s for s in obj.symbols}
    refs = [r for r in obj.relocations if by_index[r.target_symbol_index].section_index==owner.index]
    require(bool(refs), 'frame relocation population absent')
    old = elf.section(owner.name).address
    rows=[]
    for r in refs:
        require(r.source_section=='.text.vm_run_inner', 'new frame consumer needs attribution')
        target=by_index[r.target_symbol_index].value+r.addend
        require(0<=target<owner.bytes, 'relocation outside frame owner')
        fn=elf.symbol('vm_run_inner');sec=elf.section(fn.section)
        at=fn.value-sec.address+r.offset
        body=elf.section_bytes(fn.section)
        if r.relocation_type=='R_MOS_ADDR16': observed=int.from_bytes(body[at:at+2],'little');expected=old+target
        elif r.relocation_type=='R_MOS_ADDR16_LO': observed=body[at];expected=(old+target)&255
        elif r.relocation_type=='R_MOS_ADDR16_HI': observed=body[at];expected=(old+target)>>8
        else: raise ValueError('frame relocation is not a complete 16-bit address')
        require(observed==expected, 'LTO relocation does not reproduce consumed linked operand')
        rows.append(dict(**asdict(r),linked_operand=observed))
    return rows

def consumers():
    d=layout.values()
    historical=layout.historical_values()
    require(historical['MAX_SYM']==752 and historical['NAMEPOOL']==10208, 'historical population drift')
    text=(ROOT/'config/workbench.mk').read_text()
    require('$(WORKBENCH_SYMBOL_DEFINES)' in text and 'symbol_layout_manifest.py defines' in text,
            'Make consumer does not use manifest')
    require('symbol_layout_manifest.py stage-limit' in text, 'staging is not Bank-5-derived')
    require('-DMAX_SYM=' not in text and '-DNAMEPOOL=' not in text, 'stale live Make copies')
    common=(ROOT/'tools/host-lisp/c2_product_substitution_link.py').read_text()
    require('*symbol_layout_definitions()' in common, 'common producer bypasses manifest')
    for old in ('"MAX_SYM=752"','"NAMEPOOL=10208"'): require(old not in common,'old producer capacity')
    require(layout.stage_limit()==50816 and layout.stage_limit()!=d['SYMPOOL_EXT_OFF'], 'wrong-bank staging ceiling')
    require(layout.historical_workbench_binding()['sha256']==layout.load()['historical_workbench']['sha256'], 'era profile drift')
    modules=('c2_matrix_f3_symbol_exhaustion','c2_phase_m_gc_envelope','c2_v160_primary_vm_type_attribution')
    for module in modules:
        source=(ROOT/'tools/host-lisp'/f'{module}.py').read_text()
        require('SYMBOL_LAYOUT.historical_values()' in source, 'historical consumer lacks era manifest: '+module)
    return dict(live=['config/workbench.mk','tools/host-lisp/c2_product_substitution_link.py'],
                historical=list(modules),historical_profile=layout.historical_workbench_binding())

def run(elf_path,obj_path):
    elf=ElfTruth.read(elf_path,llvm_readobj=READOBJ,include_section_data=True)
    obj=ElfTruth.read(obj_path,llvm_readobj=READOBJ)
    m=layout.load();g=geometry(m,elf);refs=relocation_proof(elf,obj)
    trials=[]
    for label,field,key,value in [
        ('missing tail guard','name_owner','tail_guard',0),
        ('wrong bank','name_owner','bank',5),('user graphics overlap','name_owner','offset',49151),
        ('frame count changed','soft_frames','count',17),('frame size changed','soft_frames','frame_bytes',8),
        ('before floor removed','soft_frames','preceding_floor',4),('after floor removed','soft_frames','following_floor',4),
        ('high floor removed','floors','high_bss',4),
        # 8,576 was the pre-owner floor: with the boot-time name index now
        # seated in the same free tail, that value overcommits the region
        # (it no longer leaves room for the transient owner) and must fail.
        ('Bank-5 floor overcommits transient owner','floors','bank5_free',8576),
        ('old user-code claim','floors','user_code',10183),
        ('superseded storage measurement','floors','user_code',8432),
        ('corrupt measured target','user_code_measurement','sha256','0'*64)]:
        mutant=deepcopy(m);mutant[field][key]=value;trials.append((label,mutant))
    mutant=deepcopy(m);mutant.pop('user_code_measurement');trials.append(('missing measured target',mutant))
    mutant=deepcopy(m);mutant['floors'].pop('bank5_free');trials.append(('Bank-5 floor field removed',mutant))
    for label,key,value in [('old symbol capacity','symbol_slots',795),('rejected 1024 slots','symbol_slots',1024),
                            ('old Bank-2 limit','bank2_code_limit',59168)]:
        mutant=deepcopy(m);mutant[key]=value;trials.append((label,mutant))
    rejected=[]
    for label,mutant in trials:
        try: geometry(mutant,elf)
        except (ValueError,KeyError): rejected.append(label)
        else: raise ValueError('surviving mutation: '+label)
    domains={'bank1-name-owner':(0x1c000,16384)}
    for name in ('SYMVAL','NAMEOFF','SYMFN'):
        domains[name.lower()+'-bank5']=(0x50000+g['definitions'][name+'_EXT_OFF'],g['definitions']['MAX_SYM']*2)
    range_result=transport.range_model(domains)
    # linked_gate reads the consumed opcodes; model_gate exercises their tuple construction.
    linked=mask.linked_gate(elf_path)
    saved=mask.SOURCE_DOMAINS
    try:
        mask.SOURCE_DOMAINS=domains
        tuples=mask.model_gate()
    finally: mask.SOURCE_DOMAINS=saved
    return dict(status='PASS: no-build storage geometry, linked relocation/MAP and define consumers',
        authority=m['authority'],manifest=bind(layout.MANIFEST),geometry=g,relocations=refs,
        controls=rejected,consumers=consumers(),map=dict(range=range_result,linked=linked,tuples=tuples),
        inputs=[bind(elf_path),bind(obj_path)],
        claim='Admission only. Candidate link, live currencies, native lanes/GC/boot and hardware remain unproved.',
        product_budget=dict(seed=0,final=0,link=0))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--elf',type=Path,required=True);p.add_argument('--object',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();result=run(a.elf.resolve(),a.object.resolve())
    from check_result_receipt import report
    report(a.output, result)
    print(result['status'], 'controls',len(result['controls']),'relocations',len(result['relocations']))
