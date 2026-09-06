#!/usr/bin/env python3
"""Closed compilation-root attribution for the F011 successor (read-only)."""
from collections import Counter
from dataclasses import asdict
import difflib
import hashlib
import json
import re
import subprocess
import f011_status_product_card as C
from elf_truth import ElfTruth
from evidence_era import stable_recorded_on
import error_text_table as ERROR

OUT=C.BUILD/'attribution'
def digest(b):return hashlib.sha256(b).hexdigest()
def counter_rows(c):return [{'identity':list(k),'count':v} for k,v in sorted(c.items(),key=lambda x:repr(x[0]))]

def ir(path,root):
    s=subprocess.check_output([str(C.ROOT/'tools/llvm-mos/bin/clang'),'--target=mos','-Wno-override-module','-S','-emit-llvm','-x','ir',str(path),'-o','-'],stderr=subprocess.PIPE).decode()
    s=re.sub(r'^; ModuleID = .*\n','',s)
    s=s.replace(str(root),'<WORLD>').replace(str(root.relative_to(C.ROOT)),'<WORLD>')
    # Only metadata referenced as !srcloc may be normalized, never arbitrary
    # integer metadata (TBAA, range, attributes, etc.).
    ids=set(re.findall(r'!srcloc !(\d+)',s))
    for n in ids:
        s=re.sub(r'^!'+n+r' = !\{i64 [^\n]+\}$','!'+n+' = !{<inline-asm-source-location>}',s,flags=re.M)
    return s

def run():
    C.configure();OUT.mkdir(exist_ok=True)
    before_pair=[C.bind(C.OLD_ELF),C.bind(C.OLD_PRG),C.bind(C.ELF),C.bind(C.PRG)]
    profiles=[C.B.profile_inputs(p) for p in [C.OLD_PROFILE,C.PROFILE]]
    base=[{p.rsplit('/',1)[-1]:v for p,v in x.items()} for x in profiles]
    changed=sorted(k for k in set(base[0])|set(base[1]) if base[0].get(k)!=base[1].get(k))
    C.require(changed==['io.c','main.c','vm.c'],'unexpected authored/generated content root: '+str(changed))
    worlds=[C.OLD_BUILD/'wplto',C.WPLTO]
    ids=[C.load(w/'runtime-overlays-boot-final.json')['profile_build_id'] for w in worlds]
    byte_pairs=set(zip(ids[0].to_bytes(4,'little'),ids[1].to_bytes(4,'little')))
    # Independently parse both generated error tables and bind the IR literals
    # to them. Outside ID and CRC fields the tables must be byte-identical.
    tables=[(w/'error-text-table.bin').read_bytes() for w in worlds]
    for x,i in zip(tables,ids):ERROR.parse_table(x,expected_build_id=i)
    C.require(tables[0][:8]==tables[1][:8] and tables[0][12:14]==tables[1][12:14] and tables[0][16:]==tables[1][16:],'error table changed outside ID/CRC')
    objects=[];unexplained=[]
    dirs=[w/'.canonical-objects-lisp65-c2-substitution-linked' for w in worlds]
    old_names={p.name for p in dirs[0].glob('[0-9][0-9][0-9]-*.o')}
    new_names={p.name for p in dirs[1].glob('[0-9][0-9][0-9]-*.o')}
    C.require(old_names==new_names,'compiler object population changed')
    for name in sorted(old_names):
        a,b=[d/name for d in dirs];family='byte-identical'
        hunks=[]
        if a.read_bytes()!=b.read_bytes():
            C.require(name.endswith('.c.o'),'unexplained native assembler change: '+name)
            left,right=ir(a,C.OLD_BUILD),ir(b,C.BUILD)
            if left==right:family='phase-output-path / inline-asm diagnostic locations only'
            elif name[4:-2] in changed:family='authored '+name[4:-2]+'; F011 witness / LOAD_OPEN transfer'
            elif name=='009-error_overlay.c.o':
                la=left.splitlines();lb=right.splitlines()
                pairs=[(x,y) for x,y in zip(la,lb) if x!=y]
                C.require(len(la)==len(lb) and len(pairs)==1 and all(x.startswith('@l65e_table =') for x in pairs[0]),'error table IR contains unrelated changes')
                def literal(line):
                    encoded=line.split(' c"',1)[1].split('", section',1)[0]
                    out=bytearray();i=0
                    while i<len(encoded):
                        if encoded[i:i+2]=='\\\\':out.append(92);i+=2
                        elif encoded[i]=='\\':out.append(int(encoded[i+1:i+3],16));i+=3
                        else:out.append(ord(encoded[i]));i+=1
                    return bytes(out)
                C.require([literal(x) for x in pairs[0]]==tables,'IR error table not bound to generated table')
                family='profile Build-ID and verified error-table CRC'
            else:
                la=left.splitlines();lb=right.splitlines();valid=len(la)==len(lb)
                for x,y in zip(la,lb):
                    if x==y:continue
                    aa=re.fullmatch(r'(\s*%\d+ = icmp eq i8 %\d+, )(-?\d+)',x)
                    bb=re.fullmatch(r'(\s*%\d+ = icmp eq i8 %\d+, )(-?\d+)',y)
                    valid &= bool(aa and bb and aa[1]==bb[1] and (int(aa[2])&255,int(bb[2])&255) in byte_pairs)
                if valid:family='consumed profile-Build-ID byte comparisons'
                else:unexplained.append(name);family='UNEXPLAINED'
            hunks=list(difflib.unified_diff(left.splitlines(),right.splitlines(),n=2))
            (OUT/(name+'.diff.json')).write_bytes(C.canonical({'family':family,'diff':hunks}))
        objects.append({'name':name,'old_sha256':digest(a.read_bytes()),'new_sha256':digest(b.read_bytes()),'family':family})
    C.require(not unexplained,'unclosed compiler roots: '+str(unexplained))
    truths=[ElfTruth.read(p,llvm_readobj=C.B.READOBJ,include_section_data=True) for p in [C.OLD_ELF,C.ELF]]
    families=['authored F011 cold observer and sample-return waits','ordinary LOAD_OPEN transfer / explicit boot reset',
              'derived NOLOAD owner / cold-owner placement and relocations','profile-Build-ID projection and derived CRCs',
              'ELF section/symbol/relocation numbering and physical packing under the closed roots']
    populations={}
    for category,extract in [('sections',lambda t:[(r.name,r.address,r.bytes,r.section_type,tuple(r.flags)) for r in t.sections]),
       ('symbols',lambda t:[(r.name,r.value,r.bytes,r.section,r.symbol_type) for r in t.symbols]),
       ('relocations',lambda t:[(r.source_section,r.offset,r.relocation_type,r.target,r.addend) for r in t.relocations])]:
        a,b=[Counter(extract(t)) for t in truths]
        populations[category]={'removed':counter_rows(a-b),'added':counter_rows(b-a),
            'attribution_basis':'closed compiler inputs plus linker-owner/Build-ID families','families':families}
    headers=C.B.PREV.CARD.CARD2.R2.CARD.ORIGINAL_PROGRAM_HEADERS
    a,b=headers(C.OLD_ELF),headers(C.ELF)
    populations['program_headers']={'removed':counter_rows(a-b),'added':counter_rows(b-a),'families':families}
    a,b=C.OLD_PRG.read_bytes(),C.PRG.read_bytes()
    prg=[[i,a[i] if i<len(a) else None,b[i] if i<len(b) else None]
         for i in range(max(len(a),len(b))) if (a[i] if i<len(a) else None)!=(b[i] if i<len(b) else None)]
    result={'format':'f011-closed-root-attribution-v1','recorded_on':stable_recorded_on(C.DIFFERENCE),
      'pair':before_pair,'changed_content_roots':changed,'profile_build_ids':ids,'objects':objects,
      'families':families,'member_populations':populations,'PRG_changed_byte_members':prg,
      'PRG_changed_bytes':len(prg),'unexplained_compiler_inputs':unexplained,
      'method':'causal compiler-root closure; all member deltas enumerated under the closed transitive families, not a claim of byte-local causal uniqueness',
      'unexplained_members':0}
    C.require(before_pair==[C.bind(C.OLD_ELF),C.bind(C.OLD_PRG),C.bind(C.ELF),C.bind(C.PRG)],'attribution changed product')
    C.DIFFERENCE.write_bytes(C.canonical(result));print('F011 closed-root attribution PASS; PRG changed bytes',len(prg))
if __name__=='__main__':run()
