"""Derive storage-owner linker changes from the consumed predecessor and manifest.

Only emits linker text. No compiler or linker is invoked. MEMORY belongs in
the outer commodore script, never in c.ld's SECTIONS body.
"""
from pathlib import Path
import argparse
import difflib
import hashlib
import json
import re
import symbol_layout_manifest as L
from elf_truth import ElfTruth

FILES=('c2-substitution.ld','full-map-linker/c.ld','full-map-linker/commodore.ld','full-map-linker/zp-data.ld')
def once(text,old,new):
    if text.count(old)!=1: raise ValueError('predecessor linker shape differs: '+old[:80])
    return text.replace(old,new,1)

def facade_fixed_price(source):
    """Sum actual input-section sizes; the C abort section is the variable owner."""
    name='.lisp65_c2_mapped_far_facade';active=False;fixed=0;total=0;rows=[]
    for line in (source/'lisp65-c2-substitution-linked.prg.map').read_text().splitlines():
        section=re.fullmatch(r'\s*([0-9a-f]+)\s+([0-9a-f]+)\s+([0-9a-f]+)\s+\d+ (\.[\w.]+)',line)
        if section:
            active=section[4]==name
            if active: total=int(section[3],16)
            continue
        member=re.fullmatch(r'\s*([0-9a-f]+)\s+([0-9a-f]+)\s+([0-9a-f]+)\s+\d+\s+(.+\.o):\(([^)]+)\)',line)
        if active and member:
            path=L.ROOT/member[4]
            owner=ElfTruth.read(path,llvm_readobj=L.ROOT/'tools/llvm-mos/bin/llvm-readobj').section(member[5])
            if owner.bytes!=int(member[3],16): raise ValueError('facade map/input owner drift')
            row=dict(path=str(path.relative_to(L.ROOT)),section=owner.name,bytes=owner.bytes,
                     sha256=hashlib.sha256(path.read_bytes()).hexdigest())
            rows.append(row)
            if owner.name!=name+'.abort': fixed+=owner.bytes
    if not rows or sum(r['bytes'] for r in rows)!=total: raise ValueError('incomplete facade input population')
    if len([r for r in rows if r['section']==name+'.abort'])!=1: raise ValueError('variable facade input population drift')
    return dict(fixed_bytes=fixed,previous_bytes=total,inputs=rows)

def transform(files,facade):
    m=L.load();d=L.values(m);slots=d['MAX_SYM'];frame=m['soft_frames']
    metadata=(slots+1)//2+2*((slots+7)//8)+2
    result=dict(files);c=files['full-map-linker/c.ld']
    old=re.search(r'(?ms)^\.lisp65_vm_soft_frames_bss .*?^ASSERT\(ADDR\(\.lisp65_vm_soft_frames_bss\).*?\n',c)
    if not old: raise ValueError('old R2 owner not found')
    frame_text=(f'.lisp65_vm_soft_frames_bss (ADDR(.noinit.lisp65_f011_status) + SIZEOF(.noinit.lisp65_f011_status) + {frame["preceding_floor"]}) (NOLOAD) : {{\n'
        '    __storage_soft_frames_start = .;\n'
        '    KEEP(*(.lisp65_vm_soft_frames_bss))\n'
        '    __storage_soft_frames_end = .;\n'
        '} >c_writeable\n'
        f'ASSERT(SIZEOF(.lisp65_vm_soft_frames_bss) == {frame["count"]} * {frame["frame_bytes"]} + {frame["depth_bytes"]}, "R2 frame owner size drift")\n'
        f'ASSERT(__storage_soft_frames_end + {frame["following_floor"]} <= ADDR(.lisp65_c2_input_raw_owner), "R2 low BSS floor")\n')
    c=once(c,old[0],'')
    c=once(c,'.lisp65_c2_input_raw_owner 0xbc90 (NOLOAD) : {',frame_text+'\n.lisp65_c2_input_raw_owner 0xbc90 (NOLOAD) : {')
    old=re.search(r'(?ms)^\.noinit\.library_symbol_functions .*?"Library function-cell population drift"\)\n',c)
    if not old: raise ValueError('old function-cell owner not found')
    names=m['name_owner'];tables=m['table_owner']
    pool_physical=names['bank']*65536+names['offset']
    table_physical=tables['bank']*65536+tables['offset']
    owners=(f'.noinit.storage_symbol_names {pool_physical:#x} (NOLOAD) : {{\n'
        '    __storage_symbol_names_start = .;\n'
        f'    . += {d["NAMEPOOL"]};\n'
        '    __storage_symbol_names_usable_end = .;\n'
        f'    . += {names["tail_guard"]};\n'
        '    __storage_symbol_names_end = .;\n'
        '} >storage_symbol_names\n'
        f'.noinit.storage_symbol_tables {table_physical:#x} (NOLOAD) : {{\n')
    for name in tables['tables']:
        owners+=f'    __storage_{name}_start = .;\n    . += {slots} * {tables["bytes_per_slot"]};\n'
    owners+=('    __storage_symbol_tables_end = .;\n'
        '} >storage_symbol_tables\n'
        '__library_bank2_code_limit = __card2b_carrier_start - 0x20000;\n'
        f'ASSERT(__library_bank2_code_limit == {d["LISP65_C2_BANK2_CODE_LIMIT"]}, "carrier-derived code limit drift")\n'
        f'ASSERT(__storage_symbol_names_start == {pool_physical:#x} && __storage_symbol_names_end == 0x20000, "Bank-1 user fence or tail guard drift")\n'
        f'ASSERT(0x60000 - __storage_symbol_tables_end >= {m["floors"]["bank5_free"]}, "Bank-5 table floor")\n')
    c=once(c,old[0],owners)
    c=once(c,'SIZEOF(.lisp65_c2_symbol_metadata_bss) == 600,',f'SIZEOF(.lisp65_c2_symbol_metadata_bss) == {metadata},')
    c=once(c,'ASSERT(__lisp65_c2_symbol_metadata_bss_end <= 0xc000,',
           f'ASSERT(__lisp65_c2_symbol_metadata_bss_end + {m["floors"]["high_bss"]} <= 0xc000,')
    result['full-map-linker/c.ld']=c
    outer=files['full-map-linker/commodore.ld']
    old='MEMORY { library_symbol_functions (rw) : ORIGIN = 0x2e720, LENGTH = 1590 }\n'
    new=(f'MEMORY {{ storage_symbol_names (rw) : ORIGIN = {pool_physical:#x}, LENGTH = {names["bytes"]} }}\n'
         f'MEMORY {{ storage_symbol_tables (rw) : ORIGIN = {table_physical:#x}, LENGTH = {slots*2*3} }}\n')
    result['full-map-linker/commodore.ld']=once(outer,old,new)
    # The mutable-reader body is repriced by this card. Do not reuse the old
    # whole-facade 98-byte price as if it priced the new body. The unchanged
    # assembler entry/stub owners are summed from the consumed objects;
    # only the C abort-owner span is variable. Postlink input coverage must
    # independently account for the whole output (including this span).
    outer=result['c2-substitution.ld']
    outer=once(outer,'        KEEP(*(.lisp65_c2_mapped_far_facade.abort))',
        '        __storage_facade_abort_start = .;\n'
        '        KEEP(*(.lisp65_c2_mapped_far_facade.abort))\n'
        '        __storage_facade_abort_end = .;')
    outer=once(outer,f'SIZEOF(.lisp65_c2_mapped_far_facade) == {facade["previous_bytes"]}',
        f'SIZEOF(.lisp65_c2_mapped_far_facade) == {facade["fixed_bytes"]} +\n'
        '            (__storage_facade_abort_end - __storage_facade_abort_start)')
    result['c2-substitution.ld']=outer
    return result

def verify(actual,expected):
    if actual.keys()!=expected.keys() or any(actual[k]!=expected[k] for k in expected):
        raise ValueError('whole linker population differs from derived storage change')
    if 'MEMORY' in actual['full-map-linker/c.ld']: raise ValueError('MEMORY inside SECTIONS')

def derive(source,output):
    files={name:(source/name).read_text() for name in FILES}
    facade=facade_fixed_price(source)
    expected=transform(files,facade);verify(expected,expected)
    controls=[]
    mutants={'old complete scripts':files}
    for label,part,old,new in [
        ('missing carrier','c2-substitution.ld','__card2b_carrier_start','__missing_carrier_start'),
        ('old metadata pin','full-map-linker/c.ld','== 758,','== 600,'),
        ('weak low floor','full-map-linker/c.ld','__storage_soft_frames_end + 5','__storage_soft_frames_end + 4'),
        ('short name owner','full-map-linker/commodore.ld','LENGTH = 16384','LENGTH = 16383'),
        ('missing tail guard','full-map-linker/c.ld','. += 33;','. += 32;'),
        ('facade fixed owners drift','c2-substitution.ld',f'== {facade["fixed_bytes"]} +',f'== {facade["fixed_bytes"]+1} +'),
        ('extra unrelated change','c2-substitution.ld','0x020000','0x020001')]:
        mutant=dict(expected)
        if old not in mutant[part]: raise ValueError('mutation target missing: '+label)
        mutant[part]=mutant[part].replace(old,new,1);mutants[label]=mutant
    for label,mutant in mutants.items():
        try:verify(mutant,expected)
        except ValueError:controls.append(label)
        else:raise ValueError('mutation survived: '+label)
    for name,text in expected.items():
        target=output/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_text(text)
    changes={name:''.join(difflib.unified_diff(files[name].splitlines(True),expected[name].splitlines(True),
             fromfile='predecessor/'+name,tofile='candidate/'+name)) for name in FILES if files[name]!=expected[name]}
    bindings={name:dict(predecessor_sha256=hashlib.sha256(files[name].encode()).hexdigest(),
                       candidate_sha256=hashlib.sha256(expected[name].encode()).hexdigest())
              for name in FILES}
    return dict(status='PASS: whole linker delta derived, no build',changes=changes,
                controls=controls,facade=facade,bindings=bindings,
                claim='Derived scripts only; actual producer consumption and candidate input-section ownership remain to be proved.')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--predecessor',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    r=derive(a.predecessor,a.output)
    from check_result_receipt import report
    report(a.output/'storage-linker-proof.json', r)
    print(r['status'],'controls',len(r['controls']))
