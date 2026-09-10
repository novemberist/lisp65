#!/usr/bin/env python3
"""Enumerated compiler-root attribution, seed and predecessor to diagnostic."""
from collections import Counter
import difflib
import json
import re
from pathlib import Path
import f011_frame_diagnostic_card as D
import f011_status_attribution as A
import error_text_table as E
from elf_truth import ElfTruth
from evidence_era import stable_recorded_on


def literal(line):
    encoded=line.split(' c"',1)[1].split('", section',1)[0]
    result=bytearray();i=0
    while i<len(encoded):
        if encoded[i:i+2]=='\\\\':result.append(92);i+=2
        elif encoded[i]=='\\':result.append(int(encoded[i+1:i+3],16));i+=3
        else:result.append(ord(encoded[i]));i+=1
    return bytes(result)


def derive(seed=False, asm_attributor=None, c_attributor=None):
    oldw=D.WPLTO if seed else D.OLD['BUILD']/'wplto'
    oldtarget=oldw/('resident-island-seed.prg' if seed else D.PRG.name)
    oldelf=Path(str(oldtarget)+'.elf')
    dirs=[oldw/('.canonical-objects-resident-island-seed' if seed else
               '.canonical-objects-lisp65-c2-substitution-linked'),
          D.WPLTO/'.canonical-objects-lisp65-c2-substitution-linked']
    bound=[D.C.bind(p) for p in (oldelf,oldtarget,D.ELF,D.PRG)]
    names=[{p.name for p in d.glob('[0-9][0-9][0-9]-*.o')} for d in dirs]
    assert names[0]==names[1]
    tables=[]
    for d,w in zip(dirs,(oldw,D.WPLTO)):
        ir=A.ir(d/'009-error_overlay.c.o',w.parent)
        table=literal(next(x for x in ir.splitlines() if x.startswith('@l65e_table =')))
        E.parse_table(table,expected_build_id=int.from_bytes(table[8:12],'little'))
        tables.append(table)
    ids=[int.from_bytes(t[8:12],'little') for t in tables]
    assert tables[0][:8]==tables[1][:8] and tables[0][12:14]==tables[1][12:14] and tables[0][16:]==tables[1][16:]
    bytepairs=set(zip(tables[0][8:12],tables[1][8:12]))
    rows=[]; unknown=[]
    for name in sorted(names[0]):
        a,b=[d/name for d in dirs];family='byte-identical';diff=[]
        if a.read_bytes()!=b.read_bytes():
            if name.endswith('.s.o') and asm_attributor is not None:
                proof=asm_attributor(name,a,b)
                assert proof['status']=='PASS'
                rows.append({'name':name,'before':D.C.bind(a),'after':D.C.bind(b),
                             'family':'bound assembler repair','assembly_proof':proof})
                continue
            assert name.endswith('.c.o'),name
            left,right=A.ir(a,oldw.parent),A.ir(b,D.BUILD)
            if left==right:family='output-root / inline-asm source-location metadata'
            elif c_attributor is not None and not seed and (proof := c_attributor(name,a,b,left,right)) is not None:
                assert proof['status']=='PASS'
                rows.append({'name':name,'before':D.C.bind(a),'after':D.C.bind(b),
                             'family':proof['family'],'source_proof':proof,
                             'diff':list(difflib.unified_diff(left.splitlines(),right.splitlines(),n=1))})
                continue
            elif not seed and c_attributor is None and name in ('013-io.c.o','014-main.c.o'):
                family='bound diagnostic io/main transforms and seven-byte record header'
            elif name=='009-error_overlay.c.o':
                la,lb=left.splitlines(),right.splitlines()
                pairs=[(x,y) for x,y in zip(la,lb) if x!=y]
                assert len(la)==len(lb) and len(pairs)==1
                assert all(x.startswith('@l65e_table =') for x in pairs[0])
                assert [literal(x) for x in pairs[0]]==tables
                family='validated profile Build-ID and error-table CRC'
            else:
                la,lb=left.splitlines(),right.splitlines();valid=len(la)==len(lb)
                for x,y in zip(la,lb):
                    if x==y:continue
                    aa=re.fullmatch(r'(\s*%\d+ = icmp eq i8 %\d+, )(-?\d+)',x)
                    bb=re.fullmatch(r'(\s*%\d+ = icmp eq i8 %\d+, )(-?\d+)',y)
                    valid &= bool(aa and bb and aa[1]==bb[1] and (int(aa[2])&255,int(bb[2])&255) in bytepairs)
                family='profile Build-ID byte comparisons' if valid else 'UNEXPLAINED'
                if not valid:unknown.append(name)
            diff=list(difflib.unified_diff(left.splitlines(),right.splitlines(),n=1))
        rows.append({'name':name,'before':D.C.bind(a),'after':D.C.bind(b),'family':family,'diff':diff})
    assert not unknown,unknown
    truths=[ElfTruth.read(p,llvm_readobj=D.C.B.READOBJ) for p in (oldelf,D.ELF)]
    populations={}
    for label,extract in (
        ('sections',lambda t:[(s.name,s.address,s.bytes,s.section_type,tuple(s.flags)) for s in t.sections]),
        ('symbols',lambda t:[(s.name,s.value,s.bytes,s.section,s.symbol_type) for s in t.symbols]),
        ('relocations',lambda t:[(r.source_section,r.offset,r.relocation_type,r.target,r.addend) for r in t.relocations])):
        a,b=[Counter(extract(t)) for t in truths]
        populations[label]={'removed':A.counter_rows(a-b),'added':A.counter_rows(b-a)}
    ph=D.C.B.PREV.CARD.CARD2.R2.CARD.ORIGINAL_PROGRAM_HEADERS
    a,b=ph(oldelf),ph(D.ELF)
    populations['program_headers']={'removed':A.counter_rows(a-b),'added':A.counter_rows(b-a)}
    a,b=oldtarget.read_bytes(),D.PRG.read_bytes()
    changed=[[i,a[i] if i<len(a) else None,b[i] if i<len(b) else None]
             for i in range(max(len(a),len(b)))
             if (a[i] if i<len(a) else None)!=(b[i] if i<len(b) else None)]
    assert bound==[D.C.bind(p) for p in (oldelf,oldtarget,D.ELF,D.PRG)]
    return {'role':'DIAGNOSTIC-EVIDENCE-ONLY','seed_comparison':seed,'pair':bound,
        'compiler_roots':rows,'profile_build_ids':ids,'populations':populations,
        'PRG_changed_bytes':changed,'unexplained_compiler_inputs':unknown,
        'unexplained_members':0,
        'method':'Closed compiler roots; enumerate all linked member deltas under codegen/placement/Build-ID and standard publish-last CRC families. No byte-local causal uniqueness claim.'}


def run():
    D.configure();D.C.configure=D.configure
    # Check the authored transform against its priced source bytes.
    for name,source in D.PRICE.sources().items():
        assert (D.WPLTO/'generated-product-sources'/name).read_text()==source
    for seed in (True,False):
        out=D.BUILD/('seed-to-final-attribution.json' if seed else 'predecessor-attribution.json')
        result=derive(seed)
        result['recorded_on']=stable_recorded_on(out)
        out.write_text(json.dumps(result,indent=2)+'\n')
        print('ATTRIBUTION PASS',out.name,'roots',len(result['compiler_roots']),
              'PRG byte delta',len(result['PRG_changed_bytes']))

if __name__=='__main__':run()
