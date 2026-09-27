"""ELF-derived boot observer configuration; no product build or modification."""
from pathlib import Path
import argparse,hashlib,json,sys,subprocess
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools/host-lisp'))
from elf_truth import ElfTruth
def bind(p):
    b=p.read_bytes();return dict(path=str(p.relative_to(ROOT)),bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
def configure(out, *, paths=None, inputs=None, medium=None):
    if paths is None:
        p=ROOT/'build/definition-set-a-final-medium-r1/packed-receipt.json';r=json.loads(p.read_text())
        paths=[p.parent/'packed/autoboot.c65.elf',ROOT/r['elf']['path']]
        inputs=[p];medium=r['medium']
    worlds=[ElfTruth.read(p,llvm_readobj=ROOT/'tools/llvm-mos/bin/llvm-readobj',include_section_data=True) for p in paths]
    specs=[(0,'_start'),(0,'main'),(0,'product_media_identity'),(0,'disk_record'),
           (1,'_init'),(1,'main'),(1,'vm_install_staged_boot_overlay'),(1,'c2_product_install'),
           (1,'vm_runtime_overlay_install_island'),(1,'repl')]
    rows=[]
    for world,name in specs:
        t=worlds[world];s=t.symbol(name);sec=t.section(s.section)
        sig=t.section_bytes(s.section)[s.value-sec.address:s.value-sec.address+16]
        assert len(sig)==16
        rows.append(dict(world=world,name=name,pc=s.value,section=s.section,signature=sig.hex()))
    # The banner entry follows the unique startup-message pointer setup in repl.
    t=worlds[1];s=t.symbol('repl');sec=t.section(s.section);raw=t.section_bytes(s.section)
    msg=t.symbol('repl.startup_message').value
    needle=bytes([0xa2,msg&255,0x86,4,0xa2,msg>>8,0x86,5,0x20])
    body=raw[s.value-sec.address:s.value-sec.address+s.bytes]
    assert body.count(needle)==1
    offset=body.index(needle)+8
    start=s.value+offset
    # Next JSR is the banner VM entry; verify its target against ELF truth.
    nextcall=body.index(bytes([0x20,t.symbol('vm_run_dir').value&255,t.symbol('vm_run_dir').value>>8]),offset+3)
    for name,pc in [('initializing-emit',start),('banner-return',s.value+nextcall+3)]:
        sig=raw[pc-sec.address:pc-sec.address+16]
        rows.append(dict(world=1,name=name,pc=pc,section=s.section,signature=sig.hex()))
    lines=['struct boot_boundary { unsigned world, pc; const char *name; unsigned char sig[16]; };',
           'static const struct boot_boundary boot_boundaries[] = {']
    for r0 in rows:lines.append('{%d,%d,"%s",{%s}},'%(r0['world'],r0['pc'],r0['name'],','.join(str(x) for x in bytes.fromhex(r0['signature']))))
    lines+=['};','#define BOOT_N (sizeof(boot_boundaries)/sizeof(boot_boundaries[0]))']
    (out/'observer/xemu/boot_boundaries.h').write_text('\n'.join(lines)+'\n')
    (out/'configuration.json').write_text(json.dumps(dict(status='CONFIGURED; NOT A TIMING CLAIM',boundaries=rows,
        inputs=[bind(p) for p in (inputs or [])]+[bind(q) for q in paths],medium=medium,product_builds=0),indent=2)+'\n')
def build(out):
    base=ROOT/'build/minibuffer-frame-attribution-r1/cycle-observer'
    out.mkdir(exist_ok=False)
    dest=out/'observer'
    subprocess.run(['cp','-a','--reflink=auto',str(base),str(dest)],check=True)
    configure(out)
    header=ROOT/'tools/host-lisp/fixtures/boot_ledger_observer.h'
    (dest/'xemu/boot_observer.h').write_bytes(header.read_bytes())
    cpu=dest/'xemu/cpu65.c';raw=cpu.read_text()
    edits=[('#include <stdlib.h>','#include <stdlib.h>\n#include "boot_observer.h"',1),
      ('\tCPU65.op = readByte(CPU65.pc);\n#ifdef MEGA65','\tCPU65.op = readByte(CPU65.pc);\n#ifdef MEGA65\n    boot_observe_instruction(all_cycles);',1),
      ('\t\tall_cycles += 7;','\t\tif(boot_phase>=0 && !boot_done)boot_interrupt[boot_phase]+=7;\n\t\tall_cycles += 7;',2),
      ('do_not_clear_prefix:\n','do_not_clear_prefix:\n    dwx_boot_charge(0,CPU65.op_cycles);\n',1)]
    for old,new,n in edits:assert raw.count(old)==n;raw=raw.replace(old,new)
    cpu.write_text(raw)
    machine=dest/'targets/mega65/mega65.c';raw=machine.read_text()
    for old,new in [('\t\tconst int dwx_step_cycles =',
      '\t\textern void dwx_boot_charge(int dma, unsigned cycles);\n\t\tconst int boot_was_dma = !!in_dma;\n\t\tconst int dwx_step_cycles ='),
      ('\t\tdwx_cpu_cycles_total += (Uint64)dwx_step_cycles;',
       '\t\tif(boot_was_dma)dwx_boot_charge(1, dwx_step_cycles);\n\t\tdwx_cpu_cycles_total += (Uint64)dwx_step_cycles;')]:
        assert raw.count(old)==1;raw=raw.replace(old,new)
    machine.write_text(raw)
    flags=subprocess.check_output(['pkg-config','--cflags','gtk+-3.0'],text=True).strip()
    libs=subprocess.check_output(['pkg-config','--libs','gtk+-3.0'],text=True).strip()
    cmd=['make','-C',str(dest/'targets/mega65'),'-j4',
      'SDL2_CFLAGS=-I'+str(ROOT/'build/dwx/stack-envelope-host-sdk/root/usr/include/SDL2')+' -D_GNU_SOURCE=1 -D_REENTRANT',
      'SDL2_LIBS='+str(Path('/usr/lib64/libSDL2-2.0.so.0').resolve()),'GTK3_CFLAGS='+flags,'XEMUGUI_CFLAGS='+flags,
      'GTK3_LIBS='+libs,'XEMUGUI_LIBS='+libs]
    with (out/'build.log').open('w') as f:subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,check=True)
    (out/'build.json').write_text(json.dumps(dict(status='HOST INSTRUMENT BUILT; QUALIFICATION REQUIRED',
      command=cmd,base=[bind(base/p) for p in ['xemu/cpu65.c','targets/mega65/mega65.c']],
      outputs=[bind(p) for p in [header,cpu,machine,dest/'xemu/boot_boundaries.h',dest/'build/bin/xmega65.native']],
      product_builds=0),indent=2)+'\n')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['configure','build']);p.add_argument('out',type=Path)
    a=p.parse_args();globals()[a.action](a.out.resolve())
