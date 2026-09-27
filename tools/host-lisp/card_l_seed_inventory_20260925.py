"""Card L exhaustive ELF ledger and symbol/relocation equivalence audit. No link."""
import collections
import hashlib
import json
import struct
from dataclasses import asdict
from pathlib import Path
import sys
sys.dont_write_bytecode = True
from elf_truth import ElfTruth

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT/'build/card-l-r1/inventory-r3'
PATHS = [ROOT/'build/nested-error-recovery-final-r1/wplto/lisp65-c2-substitution-linked.prg.elf',
         ROOT/'build/card-l-product-r1/wplto/resident-island-seed.prg.elf']
STAGE = '.lisp65_rt_card_l_stage'
WIDTH = {'R_MOS_ADDR8':1, 'R_MOS_ADDR16':2, 'R_MOS_ADDR16_LO':1,
         'R_MOS_ADDR16_HI':1, 'R_MOS_IMM8':1}
INSERT = bytes.fromhex('a937a2008604a20086052030e1')
INSERT_OFF = 0xa79f-0xa53d


def sha(raw): return hashlib.sha256(raw).hexdigest()
def write(name, value): (OUT/name).write_text(json.dumps(value,indent=2)+'\n')


def main():
    OUT.mkdir(exist_ok=False)
    raws = [p.read_bytes() for p in PATHS]
    assert sha(raws[0]) == '66165507a8e5ad1d857afdd967f9056be2ce7bbccc332d5328e981398078b47b'
    ts = [ElfTruth.read(p,llvm_readobj=ROOT/'tools/llvm-mos/bin/llvm-readobj',include_section_data=True) for p in PATHS]
    assert sha(raws[1]) == '7e57bc17f318dd22a6dbc0212fd5fde5b9598eaf645f4f98d6387e0c3f53f3b5'
    a,b = ts
    failures=[]
    def require(ok, reason):
        if not ok: failures.append(reason)
    # Map each text byte through its named owner, permitting only the exact
    # stage-call insertion in main (the product boot was inlined there).
    syms=[{(s.section,s.name,s.symbol_type):s for s in t.symbols if s.bytes} for t in ts]
    mapping={}; owners={}; cover=[set(),set()]
    functions=[]
    for key,old in syms[0].items():
        new=syms[1].get(key)
        require(new is not None, ['removed sized symbol',key])
        if new is None: continue
        extra=13 if key==('.text','main','Function') else 0
        require(new.bytes==old.bytes+extra,['symbol size',key,old.bytes,new.bytes])
        if old.section=='.text':
            for i in range(old.bytes):
                target=new.value+i+(13 if extra and i>=INSERT_OFF else 0)
                require(target not in mapping or mapping[target]==old.value+i,['overlap map',key,target])
                mapping[target]=old.value+i;owners[target]=old.name
            cover[0].update(range(old.value,old.value+old.bytes))
            cover[1].update(range(new.value,new.value+new.bytes))
        functions.append(dict(name=old.name,section=old.section,before_address=old.value,
            after_address=new.value,before_bytes=old.bytes,after_bytes=new.bytes))
    gaps=[]
    for t,c in zip(ts,cover):
        s=t.section('.text');gaps.append([v for v in range(s.address,s.address+s.bytes) if v not in c])
    require(len(gaps[0])==len(gaps[1]),'text gap cardinality')
    for x,y in zip(*gaps):mapping[y]=x;owners[y]='unnamed text interval'
    newmain=b.symbol('main');oldmain=a.symbol('main')
    insert_start=newmain.value+INSERT_OFF
    require(b.section_bytes('.text')[insert_start-b.section('.text').address:insert_start-b.section('.text').address+13]==INSERT,'exact inline boot call')

    # A section-relative relocation resolves to an owner and offset, rather
    # than merely an address, so moved functions cannot hide changed targets.
    indexes=[]
    for t in ts:
        idx=collections.defaultdict(dict)
        for s in sorted((s for s in t.symbols if s.bytes),key=lambda s:(s.bytes,s.name),reverse=True):
            for address in range(s.value,s.value+s.bytes):idx[s.section][address]=s
        indexes.append(idx)
    def expression(which,rel):
        t=ts[which];s=t.symbols[rel.target_symbol_index]
        if s.symbol_type=='Section':
            address=s.value+rel.addend;owner=indexes[which][s.section].get(address)
            if owner:return [s.section,owner.name,address-owner.value]
        return [s.name,rel.addend]
    relmaps=[{(v.source_section,v.offset):v for v in t.relocations} for t in ts]
    relocation_proofs=[]; admitted_reloc_bytes=set(); relocation_ledger=[]; consumed_old=set()
    for rel in b.relocations:
        if rel.source_section==STAGE:
            entry=b.symbol('card_l_stage_entry');binding=b.symbol('rtov_late_stage_binding')
            category=('binding record' if rel.offset>=binding.value else
                      'slot-55 slice entry' if rel.offset>=entry.value else 'slot-55 slice section')
            relocation_ledger.append(dict(category=category,change='added',before=None,after=asdict(rel)))
            continue
        sec=b.section(rel.source_section)
        oldaddress=mapping.get(rel.offset,rel.offset) if sec.name=='.text' else rel.offset
        inside_main=sec.name=='.text' and newmain.value<=rel.offset<newmain.value+newmain.bytes
        if insert_start<=rel.offset<insert_start+len(INSERT) and inside_main:
            # The exact instruction bytes were checked above; these are their
            # retained operands, each checked independently by symbol identity.
            operand=rel.offset-insert_start
            instruction={5:('R_MOS_ADDR8','__rc2'),9:('R_MOS_ADDR8','__rc3'),11:('R_MOS_ADDR16','c2_overlay_call')}
            require(instruction.get(operand)==(rel.relocation_type,rel.target) and rel.addend==0,
                    ['unclassified new call-stub relocation',asdict(rel)])
            relocation_ledger.append(dict(category='new call stub in c2_product_boot (inlined into main)',
                change='added',instruction_offset=operand,before=None,after=asdict(rel)))
            continue
        old=relmaps[0].get((sec.name,oldaddress))
        if old is None:
            require(False,['new relocation outside stage insertion',asdict(rel)]);continue
        consumed_old.add((old.source_section,old.offset))
        same=old.relocation_type==rel.relocation_type and expression(0,old)==expression(1,rel)
        # main's local destinations may include the inserted call; raw main
        # bytes and all remaining relocations are checked below.
        if not same:
            require(False,
                    ['relocation target change',asdict(old),asdict(rel)])
        category=('unchanged relocation' if asdict(old)==asdict(rel) else
                  'compiler codegen drift: symbol reindexing / owner placement; equivalent expression')
        relocation_ledger.append(dict(category=category,change='paired',before=asdict(old),after=asdict(rel),
            before_expression=expression(0,old),after_expression=expression(1,rel)))
        w=WIDTH.get(rel.relocation_type)
        if w is None:
            require(old.relocation_type==rel.relocation_type and old.addend==rel.addend and old.target==rel.target,
                    ['unsupported relocation drift',asdict(rel)])
            continue
        # Verify the encoded destination, not only the retained relocation.
        for t,v in ((a,old),(b,rel)):
            val=t.symbols[v.target_symbol_index].value+v.addend
            encoded=t.section_bytes(v.source_section)[v.offset-t.section(v.source_section).address:v.offset-t.section(v.source_section).address+w]
            expected=((val>>8)&255).to_bytes(1,'little') if v.relocation_type=='R_MOS_ADDR16_HI' else (val & ((1<<(8*w))-1)).to_bytes(w,'little')
            require(encoded==expected,['relocation encoding',asdict(v),encoded.hex(),expected.hex()])
        for i in range(w):admitted_reloc_bytes.add((sec.name,rel.offset+i))
        if rel.offset!=old.offset or a.section_bytes(sec.name)[old.offset-a.section(sec.name).address:old.offset-a.section(sec.name).address+w]!=b.section_bytes(sec.name)[rel.offset-sec.address:rel.offset-sec.address+w]:
            relocation_proofs.append(dict(section=sec.name,before_offset=old.offset,after_offset=rel.offset,
                type=rel.relocation_type,before_expression=expression(0,old),after_expression=expression(1,rel)))
    for key,old in relmaps[0].items():
        if key not in consumed_old:
            failures.append(['unclassified removed relocation',asdict(old)])
            relocation_ledger.append(dict(category='UNCLASSIFIED',change='removed',before=asdict(old),after=None))
    write('all-relocations.json',relocation_ledger)
    # Exhaustive allocated byte comparison in owner coordinates.
    counts=collections.Counter(); byte_proofs=[]
    for sec in b.sections:
        if 'SHF_ALLOC' not in sec.flags or sec.section_type=='SHT_NOBITS':continue
        right=b.section_bytes(sec.name)
        if sec.name==STAGE:
            binding=b.symbol('rtov_late_stage_binding');entry=b.symbol('card_l_stage_entry')
            counts['slot-55 slice section']+=entry.value-sec.address
            counts['slot-55 slice entry']+=binding.value-entry.value
            counts['binding record']+=binding.bytes
            require(binding.value+binding.bytes==sec.address+len(right),'binding tail coverage')
            continue
        require(sec.name in a.sections_by_name,['new allocated section',sec.name])
        if sec.name not in a.sections_by_name:continue
        oldsec=a.section(sec.name);left=a.section_bytes(sec.name)
        if sec.name!='.text':require((sec.address,sec.bytes)==(oldsec.address,oldsec.bytes),['section geometry',sec.name])
        for i,y in enumerate(right):
            address=sec.address+i
            if sec.name=='.text' and insert_start<=address<insert_start+13:
                counts['inline c2_product_boot stage call']+=1;continue
            oldaddress=mapping.get(address,address) if sec.name=='.text' else address
            offset=oldaddress-oldsec.address
            x=left[offset] if 0<=offset<len(left) else None
            if x==y:counts['owner-coordinate byte identity']+=1;continue
            if (sec.name,address) in admitted_reloc_bytes:
                counts['proved relocation operand']+=1
            else:
                failures.append(['unclassified allocated byte',sec.name,hex(address),x,y])
                counts['UNCLASSIFIED']+=1
            byte_proofs.append(dict(section=sec.name,before_address=oldaddress,after_address=address,before=x,after=y))
    write('allocated-byte-proofs.json',byte_proofs)
    write('relocation-equivalence.json',relocation_proofs)
    write('owner-equivalence.json',functions)
    # Stop before admitting structural ELF metadata if executable/data proof
    # has an unclassified byte; no subsequent gate is run on that basis.
    write('content-verdict.json',dict(status='FAIL' if failures else 'PASS',counts=dict(counts),failures=failures))
    if failures:
        print(json.dumps(dict(status='HALT',failures=failures[:12],count=len(failures)),indent=2))
        raise SystemExit(1)
    print('PASS: allocated content and relocation expressions; structural inventory follows')


# Entry point below runs both content and structural passes.


def structural_inventory():
    """Close metadata and all physical offsets after the content verdict."""
    assert json.loads((OUT/'content-verdict.json').read_text())['status']=='PASS'
    raws=[p.read_bytes() for p in PATHS]
    ts=[ElfTruth.read(p,llvm_readobj=ROOT/'tools/llvm-mos/bin/llvm-readobj',include_section_data=True) for p in PATHS]
    a,b=ts
    old={(s.name,s.section,s.symbol_type,s.binding):s for s in a.symbols}
    new={(s.name,s.section,s.symbol_type,s.binding):s for s in b.symbols}
    assert old.keys()<=new.keys()
    ownerrows=json.loads((OUT/'owner-equivalence.json').read_text())
    def moved_address(address):
        matches=[p for p in ownerrows if p['section']=='.text' and p['before_address']<=address<p['before_address']+p['before_bytes']]
        if matches:
            p=matches[0];off=address-p['before_address']
            return p['after_address']+off+(13 if p['name']=='main' and off>=INSERT_OFF else 0)
        if address==a.section('.text').address+a.section('.text').bytes:return b.section('.text').address+b.section('.text').bytes
        return address
    symbol_deltas=[]
    for key,s in new.items():
        p=old.get(key)
        if p is None:
            assert s.section in (STAGE,'.noinit.card_l_gap','.noinit.card_l_late'),s
        else:
            assert s.bytes==p.bytes+(13 if s.name=='main' else 0),s
            if s.section=='.text':assert s.value==moved_address(p.value),(p,s)
            elif s.name=='__lisp65_resident_island_seed_lma':
                # Its physical address is the island owner LMA in the program
                # headers; the introduced stage shifts the packed load image.
                for t,raw,symbol in ((a,raws[0],p),(b,raws[1],s)):
                    source=t.section('.lisp65_rt_intern_service')
                    phoff=struct.unpack_from('<I',raw,28)[0];phsize,phnum=struct.unpack_from('<HH',raw,42)
                    loads=[struct.unpack_from('<8I',raw,phoff+i*phsize) for i in range(phnum)]
                    loads=[v for v in loads if v[0]==1 and v[2]<=source.address and source.address+source.bytes<=v[2]+v[5]]
                    # Overlay VMAs overlap: select the section's file interval.
                    shoff=struct.unpack_from('<I',raw,32)[0];shsize=struct.unpack_from('<H',raw,46)[0]
                    off=struct.unpack_from('<10I',raw,shoff+source.index*shsize)[4]
                    loads=[v for v in loads if v[1]<=off and off+source.bytes<=v[1]+v[4]]
                    assert len(loads)==1
                    v=loads[0];lma=v[3]+off-v[1]
                    assert symbol.value==(lma+source.bytes+255)//256*256
            else:assert s.value==p.value,(p,s)
        if p is None or (p.value,p.bytes,p.index,p.section_index)!=(s.value,s.bytes,s.index,s.section_index):
            symbol_deltas.append(dict(before=asdict(p) if p else None,after=asdict(s)))
    # This section stores a partition name followed by an address in .text.
    xp,yp=[t.section_bytes('.llvm_sympart') for t in ts]
    assert xp[:-4]==yp[:-4]==b'contingent\0'
    assert int.from_bytes(yp[-4:],'little')==moved_address(int.from_bytes(xp[-4:],'little'))
    # Account for every relocation, including deletions, in owner coordinates.
    relcounts=[]
    for t in ts:
        relcounts.append(collections.Counter(v.source_section for v in t.relocations))
    assert all(relcounts[0][k]==relcounts[1][k] for k in relcounts[0] if k!='.text')
    relocation_ledger=json.loads((OUT/'all-relocations.json').read_text())
    stub=[v for v in relocation_ledger if v['change']=='added' and v['after']['source_section']=='.text']
    # Delta is an OUTPUT of the bijective ledger, never a guessed gate.
    assert sum(v['before'] is not None for v in relocation_ledger)==len(a.relocations)
    assert sum(v['after'] is not None for v in relocation_ledger)==len(b.relocations)
    write('call-stub-relocations.json',dict(before=relcounts[0]['.text'],after=relcounts[1]['.text'],
        delta=relcounts[1]['.text']-relcounts[0]['.text'],attribution=stub))
    # Record complete section-content deltas. Raw positional comparisons are
    # intentionally distinct from the proved owner-coordinate equivalence.
    rows=[];counts=collections.Counter()
    for name in dict.fromkeys([s.name for s in a.sections]+[s.name for s in b.sections]):
        x=a.section(name) if name in a.sections_by_name else None
        y=b.section(name) if name in b.sections_by_name else None
        if x and y:assert (x.address,x.section_type,x.flags)==(y.address,y.section_type,y.flags),name
        else:assert name in (STAGE,'.rela'+STAGE,'.noinit.card_l_gap','.noinit.card_l_late'),name
        if (y or x).section_type=='SHT_NOBITS':continue
        left=a.section_bytes(name) if x else b'';right=b.section_bytes(name) if y else b''
        if left==right:continue
        kind=(y or x).section_type
        if name==STAGE:family='slot-55 slice section/entry and binding record (593 + 4 bytes)'
        elif kind=='SHT_RELA':family='proved relocation metadata and new stage relocations'
        elif kind=='SHT_SYMTAB':family='proved symbol metadata'
        elif kind=='SHT_STRTAB':family='symbol and section name serialization'
        elif name=='.llvm_sympart':family='proved moved partition address'
        elif 'SHF_ALLOC' in (y or x).flags:family='proved allocated content; see owner and relocation ledgers'
        else:raise AssertionError(('unclassified section',name))
        diffs=[[i,left[i] if i<len(left) else None,right[i] if i<len(right) else None]
               for i in range(max(len(left),len(right))) if (left[i] if i<len(left) else None)!=(right[i] if i<len(right) else None)]
        rows.append(dict(section=name,family=family,before=asdict(x) if x else None,after=asdict(y) if y else None,differences=diffs))
        counts[family]+=len(diffs)
    write('sections.json',rows);write('symbols.json',symbol_deltas)
    # Exact physical ledger, including ELF/program/section headers, padding,
    # all non-loaded data and EOF. Replay reconstructs the entire Seed ELF.
    def layout(raw,t):
        shoff,phoff=struct.unpack_from('<I',raw,32)[0],struct.unpack_from('<I',raw,28)[0]
        eh,phsize,phnum,shsize,shnum,_=struct.unpack_from('<6H',raw,40)
        assert shnum==len(t.sections)
        spans=[(0,eh,'ELF header'),(phoff,phoff+phsize*phnum,'program headers'),(shoff,shoff+shsize*shnum,'section headers')]
        for s in t.sections:
            v=struct.unpack_from('<10I',raw,shoff+s.index*shsize);offset,size=v[4:6]
            assert size==s.bytes
            if s.section_type!='SHT_NOBITS' and size:spans.append((offset,offset+size,s.name))
        labels=[None]*len(raw)
        for start,end,label in spans:
            for i in range(start,end):assert labels[i] is None;labels[i]=label
        for i,label in enumerate(labels):
            if label is None:assert raw[i]==0;labels[i]='zero padding'
        return labels
    labels=[layout(raw,t) for raw,t in zip(raws,ts)]
    ledger=[];run=None;total=0
    for i in range(max(map(len,raws))):
        x=raws[0][i] if i<len(raws[0]) else None;y=raws[1][i] if i<len(raws[1]) else None
        if x==y:run=None;continue
        total+=1;owners=[labels[k][i] if i<len(labels[k]) else 'EOF' for k in (0,1)]
        if run and run['offset']+run['length']==i and run['owners']==owners:
            run['length']+=1;run['before']+=f'{x:02x}' if x is not None else '';run['after']+=f'{y:02x}' if y is not None else ''
        else:
            run=dict(offset=i,length=1,owners=owners,before=f'{x:02x}' if x is not None else '',after=f'{y:02x}' if y is not None else '');ledger.append(run)
    rebuilt=bytearray(raws[0]);rebuilt.extend(bytes(max(0,len(raws[1])-len(rebuilt))))
    for row in ledger:
        data=bytes.fromhex(row['after']);rebuilt[row['offset']:row['offset']+len(data)]=data
    assert bytes(rebuilt[:len(raws[1])])==raws[1]
    write('physical-byte-delta.json',dict(different_positions=total,rows=ledger))
    write('inventory.json',dict(status='PASS',unclassified_bytes=0,ELFs=[dict(path=str(p.relative_to(ROOT)),sha256=sha(p.read_bytes())) for p in PATHS],section_counts=dict(counts),physical_differences=total,reconstructed_seed_sha256=sha(bytes(rebuilt[:len(raws[1])])),new_stage_bytes=b.section(STAGE).bytes,codegen_families=['resident function placement with identical owner bytes and relocation targets','main: exact 13-byte inline c2_product_boot stage call','data/code pointer operands: same owner and offset, verified encodings','symbol indices and partition address derived from owner placement'],relocation_counts=[dict(c) for c in relcounts]))
    summary=json.loads((OUT/'inventory.json').read_text())
    summary['relocation_categories']=dict(collections.Counter(v['category'] for v in relocation_ledger))
    summary['added_text_relocations']=stub
    summary['allocated_byte_categories']=json.loads((OUT/'content-verdict.json').read_text())['counts']
    summary['derived_data_changes']={'Build-ID':0,'CRC tables':0,'Shelf lengths':0,'static-boundary immediates':0}
    summary['unclassified_relocations']=[]
    write('inventory.json',summary)
    print('PASS: complete linked-byte inventory; zero unclassified bytes')


def serialization_inventory():
    out=OUT
    rows=[];fail=[]
    for path in PATHS:
     raw=path.read_bytes();t=ElfTruth.read(path,llvm_readobj=ROOT/'tools/llvm-mos/bin/llvm-readobj')
     shoff=struct.unpack_from('<I',raw,32)[0];shsize,shnum,shstridx=struct.unpack_from('<HHH',raw,46)
     sh=[struct.unpack_from('<10I',raw,shoff+i*shsize) for i in range(shnum)]
     sym=t.section('.symtab');tab=sh[sym.index];strings=sh[tab[6]];stringraw=raw[strings[4]:strings[4]+strings[5]]
     used={0};records=[]
     for n in range(tab[5]//tab[9]):
      name,value,size,info,other,idx=struct.unpack_from('<IIIBBH',raw,tab[4]+n*tab[9]);end=stringraw.index(0,name)
      used.update(range(name,end+1));records.append(dict(name=stringraw[name:end].decode(),other=other,info=info))
     orphan=[i for i,v in enumerate(stringraw) if i not in used]
     if orphan:fail.append(dict(path=str(path),kind='unreferenced .strtab bytes',offsets=orphan))
     names=sh[shstridx];data=raw[names[4]:names[4]+names[5]];usednames={0}
     for hdr in sh:
      start=hdr[0];end=data.index(0,start);usednames.update(range(start,end+1))
     orphan=[i for i,v in enumerate(data) if i not in usednames]
     if orphan:fail.append(dict(path=str(path),kind='unreferenced .shstrtab bytes',offsets=orphan))
     rows.append(dict(path=str(path.relative_to(ROOT)),symbol_records=records,strtab_all_bytes_referenced=len(used)==len(stringraw),shstrtab_all_bytes_referenced=len(usednames)==len(data)))
    from collections import Counter
    a=Counter((r['name'],r['info'],r['other']) for r in rows[0]['symbol_records'])
    b=Counter((r['name'],r['info'],r['other']) for r in rows[1]['symbol_records'])
    for key,count in (a-b).items():fail.append(dict(kind='removed symbol info/visibility record',record=key,count=count))
    (out/'serialization-proof.json').write_text(json.dumps(dict(status='FAIL' if fail else 'PASS',rows=rows,unclassified=fail),indent=2)+'\n')
    print('Serialization proof:', 'FAIL' if fail else 'PASS', len(fail));print(json.dumps(fail[:3]))
    if fail: raise ValueError('unclassified serialization records: '+repr(fail))

def function_equivalence():
    ts=[ElfTruth.read(p,llvm_readobj=ROOT/'tools/llvm-mos/bin/llvm-readobj',include_section_data=True) for p in PATHS]
    proof=[];indexes=[]
    for t in ts:
        grouped=collections.defaultdict(list)
        for rel in t.relocations:grouped[rel.source_section].append(rel)
        indexes.append(grouped)
    a,b=ts
    new={(s.section,s.name):s for s in b.symbols if s.symbol_type=='Function' and s.bytes}
    for old in a.symbols:
        if old.symbol_type!='Function' or not old.bytes:continue
        current=new[(old.section,old.name)];masked=[]
        for k,(t,s) in enumerate(zip(ts,(old,current))):
            sec=t.section(s.section);raw=bytearray(t.section_bytes(s.section)[s.value-sec.address:s.value-sec.address+s.bytes])
            for rel in indexes[k][s.section]:
                if s.value<=rel.offset<s.value+s.bytes:
                    width=WIDTH[rel.relocation_type];at=rel.offset-s.value;raw[at:at+width]=bytes(width)
            if k==1 and s.name=='main':del raw[INSERT_OFF:INSERT_OFF+len(INSERT)]
            masked.append(bytes(raw))
        if masked[0]!=masked[1]:
            write('unclassified-codegen.json',dict(function=old.name,section=old.section,
                before=masked[0].hex(),after=masked[1].hex()))
            raise ValueError('unclassified function codegen: '+old.name)
        proof.append(dict(function=old.name,section=old.section,before_address=old.value,
            after_address=current.value,before_bytes=old.bytes,after_bytes=current.bytes,
            normalized_sha256=sha(masked[0]),
            method='Exact instruction-byte identity after zeroing proved relocation operands'+
                ('; remove exact inline boot stub' if old.name=='main' else ''),
            target_expression_proof='all-relocations.json'))
    write('codegen-function-equivalence.json',dict(status='PASS',functions=proof,
        functions_checked=len(proof),moved_functions=sum(p['before_address']!=p['after_address'] for p in proof)))


if __name__=='__main__':
    import argparse,traceback
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,default=ROOT/'build/card-l-r1/inventory-r4')
    args=parser.parse_args();OUT=args.out.resolve()
    assert OUT.is_relative_to(ROOT/'build/card-l-r1')
    try:
        main()
        structural_inventory()
        serialization_inventory()
        function_equivalence()
        final=json.loads((OUT/'inventory.json').read_text())
        final['serialization_proof']='serialization-proof.json'
        final['codegen_function_proof']='codegen-function-equivalence.json'
        final['driver_sha256']=sha(Path(__file__).read_bytes())
        write('inventory.json',final)
    except Exception as error:
        if OUT.exists():
            write('failure.json',dict(status='FAIL',error=str(error),traceback=traceback.format_exc()))
        raise
