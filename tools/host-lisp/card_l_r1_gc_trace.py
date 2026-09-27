"""9ff48e97: diagnostic forced GC through alloc at a witnessed input boundary.

No product build or instruction patch. Clear only the free-list head after
alloc's first (ELF-checked LDX zp) instruction; its existing empty-list path
collects and reconstructs the free list. All roots and heap bytes are retained.
"""
import argparse,hashlib,inspect,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'tools/host-lisp'))
import block_26_vm_hardening_dwx_prefilter as G
from elf_truth import ElfTruth
from card_l_r1_common import worlds, preview
p=argparse.ArgumentParser();p.add_argument('role',choices=['baseline','candidate']);p.add_argument('--trial',type=int,default=1);p.add_argument('--dry-run',action='store_true');a=p.parse_args()
world=next(w for w in worlds() if w['role']==a.role)
if a.dry_run:
    import ast
    tree=ast.parse(Path(__file__).read_text())
    edits=ast.literal_eval(next(n.value for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='changes' for t in n.targets)))
    protocol=inspect.getsource(G.measure_gc_population)
    for old,new in [('before=monitor.cycle_count();gen_before=generation()',"before=monitor.cycle_count();gen_before=generation();carrier_pc_capture(monitor,len(rows),'before')"),('after=monitor.cycle_count();gen_after=generation()',"after=monitor.cycle_count();gen_after=generation();carrier_pc_capture(monitor,len(rows),'after')")]:
        assert protocol.count(old)==1;protocol=protocol.replace(old,new)
    for old,new in edits.items():assert protocol.count(old)==1,old;protocol=protocol.replace(old,new)
    compile(protocol,str(G.__file__),'exec')
    t=ElfTruth.read(Path(world['ELF']['path']),llvm_readobj=G.CARD.READOBJ,include_section_data=True)
    for name,opcode in [('alloc',0xa6),('c2_kernal_input_take',0xaa)]:
        member=t.symbol(name);sec=t.section(member.section)
        assert t.section_bytes(member.section)[member.value-sec.address]==opcode
    assert t.symbol('freelist').bytes==2
    preview(world,ROOT/f'build/card-l-gc-equal-{a.role}-{a.trial}'/'runtime',a.role,900)
    print('DRY RUN PASS: matched natural/forced GC with PC snapshots; no emulator launched')
    raise SystemExit(0)
OUT=ROOT/f'build/card-l-gc-equal-{a.role}-{a.trial}';assert not OUT.exists();OUT.mkdir();G.BUILD=OUT
(OUT/'driver.py').write_bytes(Path(__file__).read_bytes())
binary=world['binary']
def checked(b):
    p=ROOT/b['path'];assert G.sha256(p)==b['sha256'];return p
G.XEMU=checked(binary)
class StartupMonitor(G.CYCLES.ProbeMonitor):
    def wait_screen(self,required,timeout=20):return super().wait_screen(required,timeout=max(timeout,120))
G.CYCLES.ProbeMonitor=StartupMonitor
pack=dict(elf=world['ELF'],medium=world['medium']);elf=checked(pack['elf']);medium=checked(pack['medium'])
t=ElfTruth.read(elf,llvm_readobj=G.CARD.READOBJ,include_section_data=True)
def code(s):
    sec=t.section(s.section);return t.section_bytes(s.section)[s.value-sec.address:s.value-sec.address+s.bytes]
alloc=t.symbol('alloc');take=t.symbol('c2_kernal_input_take');free=t.symbol('freelist')
assert code(alloc)[0]==0xa6 and code(take)[0]==0xaa and free.bytes==2
import symbol_layout_manifest as LAYOUT
definitions=LAYOUT.values()
name_addresses=(definitions['SYMPOOL_EXT_BANK']*65536+definitions['SYMPOOL_EXT_OFF'],
                definitions['NAMEOFF_EXT_BANK']*65536+definitions['NAMEOFF_EXT_OFF'])
if True:
    assert name_addresses==(t.symbol('__storage_symbol_names_start').value,t.symbol('__storage_nameoff_start').value)
state={};snapshots=[]
def boundary(m):
    m.command('t1');m.command(f'b {take.value:04x}');m.command('t0')
    line=G.wait_register(m,lambda r:G.gc_registers(r)['pc']==take.value+1,'equal-state key readiness')
    assert m.memory16(0xBCFC)[:4]==bytes((128,))*4 # 18 * (32+32) events
    state['ready']=dict(registers=line,counters=m.memory16(0xBCFC)[:4].hex(),entry_pc=take.value,entry_opcode=code(take)[0])
    m.command(f'b {alloc.value:04x}');m.command('t0')
def force(m):
    assert not state.get('forced')
    before=m.memory16(free.value)[:2];assert before!=bytes(2)
    count=m.cycle_count();line=G.register_line(m)
    m.command(f's {free.value:08x} 00 00')
    assert m.memory16(free.value)[:2]==bytes(2) and m.cycle_count()==count
    state['forced']=dict(registers=line,freelist=G.bind(elf),address=free.value,before=before.hex(),after='0000',cycles=count)
    m.command(f'b {G.gc_bounds(elf)["entry"]:04x}');m.command('t0')
def snapshot(m,index):
    cache={}
    def read(at,n):
        out=bytearray()
        for x in range(at,at+n):
            base=x&~15
            if base not in cache:cache[base]=m.memory16(base)
            out.append(cache[base][x-base])
        return bytes(out)
    def var(name):
        s=t.symbol(name);return int.from_bytes(read(s.value,s.bytes),'little')
    hot=t.symbol('heap');n=var('gc_rootsp');root=t.symbol('gc_rootstack')
    def show(o,path=()):
        if o==0:return None
        if o&1:return dict(fixnum=((o if o<32768 else o-65536)>>1))
        if o>=0xe000:
            symbol=(o-0xe000)>>1;assert symbol<var('nsym')
            pool,offsets=name_addresses
            off=int.from_bytes(read(offsets+symbol*2,2),'little');raw=bytearray()
            while True:
                ch=read(pool+off+len(raw),1)[0]
                if not ch:break
                raw.append(ch);assert len(raw)<=255
            return dict(symbol=raw.decode('ascii'))
        if o>=0x8000:return dict(immediate=o)
        i=o>>1;assert 0<i<1072
        if i in path:return dict(back_reference=path.index(i))
        at=hot.value+i*5 if i<48 else 0x40000+(i-48)*8
        b=read(at,5 if i<48 else 8);kind=b[0];x=int.from_bytes(b[1:3] if i<48 else b[2:4],'little');y=int.from_bytes(b[3:5] if i<48 else b[4:6],'little')
        if kind==5:return dict(type=kind,string_hex=read(0x40000+var('str_cur_off')+(y>>1),x>>1).hex())
        if kind in (0,3,4):return dict(type=kind,a=show(x,path+(i,)),b=show(y,path+(i,)))
        return dict(type=kind,a=x,b=y)
    roots=[int.from_bytes(read(root.value+2*i,2),'little') for i in range(n)]
    identifiers={};nodes=[]
    def graph(o):
        if o==0 or o&1 or o>=0x8000:return show(o)
        i=o>>1
        if i in identifiers:return dict(ref=identifiers[i])
        ident=len(nodes);identifiers[i]=ident;node={};nodes.append(node)
        at=hot.value+i*5 if i<48 else 0x40000+(i-48)*8
        b=read(at,5 if i<48 else 8);kind=b[0]
        x=int.from_bytes(b[1:3] if i<48 else b[2:4],'little');y=int.from_bytes(b[3:5] if i<48 else b[4:6],'little')
        node['type']=kind
        if kind in (0,3,4):node.update(a=graph(x),b=graph(y))
        elif kind==5:node.update(string_hex=show(o)['string_hex'])
        else:node.update(a=x,b=y)
        return dict(ref=ident)
    graph_roots=[graph(o) for o in roots]
    v=dict(index=index,counters=read(0xBCFC,4).hex(),shadow_count=n,shadow=[show(o) for o in roots],
           graph=dict(roots=graph_roots,nodes=nodes),shadow_cells=len(nodes),
           gc_frozen=var('gc_frozen'),symbols=var('nsym'),root_bytes=read(root.value,n*2).hex())
    assert v['gc_frozen']==0
    v['shadow_sha256']=hashlib.sha256(json.dumps(v['shadow'],sort_keys=True).encode()).hexdigest()
    rawpath=OUT/f'{index}-entry-memory.json';rawpath.write_text(json.dumps({str(at):b.hex() for at,b in cache.items()},sort_keys=True)+'\n')
    v['memory_blocks']=G.bind(rawpath)
    path=OUT/f'{index}-entry-state.json';path.write_text(json.dumps(v,indent=2)+'\n');snapshots.append(G.bind(path));return v
def marked(m):
    s=t.symbol('marks');raw=m.memory_range(s.value,s.bytes)
    return dict(address=s.value,bytes=raw.hex(),count=sum(x.bit_count() for x in raw))
import os
pc=OUT/'pc-current.txt'
os.environ['LISP65_DWX_PC_OUTPUT']=str(pc)
os.environ['LISP65_COST_CONFIG']=world['cost_config']
def carrier_pc_capture(monitor,index,phase):
    cycles=monitor.cycle_count()
    assert 'DWX PC save: 0' in monitor.command('~pcsave')
    assert monitor.cycle_count()==cycles
    (OUT/f'pc-{index}-{phase}.txt').write_bytes(pc.read_bytes())
G.carrier_pc_capture=carrier_pc_capture
source=inspect.getsource(G.measure_gc_population)
changes={
 'timeout=360':'timeout=900',
 "chunks.extend([('measured',FINAL[:-1]),('measured','\\n')])":"chunks.extend([('forced',FINAL[:1]),('measured',FINAL[1:-1]),('measured','\\n')])",
 "            expected=(counter+len(chunk)) & 255":"            if phase=='forced': boundary(monitor)\n            expected=(counter+len(chunk)) & 255",
 "                if gc_registers(line)['pc']==bounds['entry_after_first_opcode']:":"                if phase=='forced' and not state.get('forced') and gc_registers(line)['pc']==alloc.value+2:\n                    force(monitor);continue\n                if gc_registers(line)['pc']==bounds['entry_after_first_opcode']:",
 '                    before=monitor.cycle_count();gen_before=generation()':"                    entry_state=snapshot(monitor,len(rows)) if phase=='forced' else None\n                    before=monitor.cycle_count();gen_before=generation()",
 "                    rows.append(dict(phase=phase,trigger_chunk_index=index,entry_registers=line,":"                    mark_state=marked(monitor)\n                    if phase=='forced':state['completed']=True\n                    rows.append(dict(entry_state=entry_state,marked=mark_state,phase=phase,trigger_chunk_index=index,entry_registers=line,",
 "                if monitor.memory16(0xBCFC)[:4]==bytes((expected,))*4:":"                if (phase!='forced' or state.get('completed')) and monitor.memory16(0xBCFC)[:4]==bytes((expected,))*4:",
}
source=source.replace('before=monitor.cycle_count();gen_before=generation()',"before=monitor.cycle_count();gen_before=generation();carrier_pc_capture(monitor,len(rows),'before')").replace('after=monitor.cycle_count();gen_after=generation()',"after=monitor.cycle_count();gen_after=generation();carrier_pc_capture(monitor,len(rows),'after')")
changed=source
for old,new in changes.items():assert changed.count(old)==1,old;changed=changed.replace(old,new)
ns=dict(G.__dict__,boundary=boundary,force=force,state=state,alloc=alloc,snapshot=snapshot,marked=marked)
exec(compile(changed,str(G.__file__),'exec'),ns)
row=ns['measure_gc_population'](a.role,medium,elf)
forced=[r for r in row['collections'] if r['phase']=='forced'];assert len(forced)==1 and forced[0]['entry_state']
row.update(world=world, instrument=G.bind(ROOT/'build/card-l-r1/instrument-lanes.json'), authority='9ff48e97',forcing=state,entry_snapshots=snapshots,forced_count=1,natural_count=len(row['collections'])-1,
    driver=G.bind(OUT/'driver.py'),adapter=G.bind(Path(G.__file__)),transformations=changes,
    claim='Diagnostic matched-boundary collection; no product bytes changed; natural-count companion comes from unforced protocol.')
(OUT/'receipt.json').write_text(json.dumps(row,indent=2)+'\n')
print(a.role,a.trial,[(r['phase'],r['cycles'],r['marked']['count']) for r in row['collections']],flush=True)

