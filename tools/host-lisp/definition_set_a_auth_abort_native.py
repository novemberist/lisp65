"""Diagnostic abort through the real captured-frame entry during emitter auth.

No product build. A temporary seven-byte call shim occupies proved free
ordinary text, never a product instruction. It creates a real JSR return
slot; no guessed stack offsets or synthetic return addresses are installed.
"""
from pathlib import Path
import argparse, hashlib, json, sys, time

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools/host-lisp'))
import dwx_retroactive_red_replay as R
import dwx_comfort_resume as C
import block_26_vm_hardening_dwx_prefilter as G
from elf_truth import ElfTruth

p=argparse.ArgumentParser();p.add_argument('--attempt',required=True);a=p.parse_args()
out=ROOT/f'build/definition-set-a-auth-abort-{a.attempt}';out.mkdir(exist_ok=False)
pack=json.loads((ROOT/'build/definition-set-a-seed-medium-r2/packed-receipt.json').read_text())
def checked(b):
    p=ROOT/b['path'];assert R.bind(p)['sha256']==b['sha256'];return p
elf=checked(pack['elf']);medium=checked(pack['medium'])
t=ElfTruth.read(elf,llvm_readobj=ROOT/'tools/llvm-mos/bin/llvm-readobj',include_section_data=True)
binary=checked(next(w for w in json.loads((ROOT/'build/definition-set-a-r3/ready-instrument.json').read_text())['worlds'] if w['role']=='candidate')['binary'])
args=argparse.Namespace(xemu=binary,rom=Path(str(Path.home() / '.local/share/xemu-lgb/mega65/MEGA65.ROM')),
 sd_image=Path(str(Path.home() / '.local/share/xemu-lgb/mega65/mega65.img')),timeout=900)
parent=R.ProbeMonitor
class Monitor(parent):
    def wait_screen(self,required,timeout=20):return super().wait_screen(required,timeout=180)
R.ProbeMonitor=Monitor
run=None;error=None;proof={};outputs=None
def objects(m):
    h=m.memory_range(0x50000,48);n=int.from_bytes(h[16:18],'little');off=int.from_bytes(h[30:32],'little')
    d=m.memory_range(0x50000+off,n*10);bank=m.memory_range(0x20000,65536)
    return {str(i):dict(row=d[i*10:i*10+10].hex(),sha256=hashlib.sha256(
        bank[int.from_bytes(d[i*10+2:i*10+4],'little'):int.from_bytes(d[i*10+2:i*10+4],'little')+int.from_bytes(d[i*10+4:i*10+6],'little')]).hexdigest()) for i in range(n)}
try:
    run=R.start_run('abort',medium,out,args);m=run['monitor']
    def result(before,value):
        end=time.monotonic()+240
        while time.monotonic()<end:
            s=m.screen()
            if C.active(s)=='LISP65>' and C.fresh_result(before,s,value):return s
            time.sleep(.05)
        raise AssertionError(('missing result',value,m.screen()))
    def form(text,value,label):
        before=m.screen();m.type_text(text+'\n');s=result(before,value)
        path=out/(label+'.txt');path.write_text(s);proof[label]=R.bind(path)
    form('(require "defstruct")','T','load')
    form('(defun abortanchor () 7)','ABORTANCHOR','anchor')
    m.command('t1');prior=objects(m)
    slot=t.section('.text').address+t.section('.text').bytes
    abort=t.symbol('lisp_abort_code').value
    shim=bytes([0xa9,38,0x20,abort&255,abort>>8,0x80,0xfe])
    assert slot+len(shim)<=0xb3b0-32
    saved=m.memory_range(slot,len(shim))
    active=t.symbol('rtov_batch_slot_id').value
    assert m.memory_range(active,1)==b'\0'
    entry=t.symbol('c2_session_emit_add')
    section=t.section(entry.section)
    code=t.section_bytes(entry.section)[entry.value-section.address:entry.value-section.address+4]
    before=m.screen();m.begin_breakpoint_connection()
    try:
        m.command(f'b {entry.value:04x}');m.command('t0')
        m.type_text('(defstruct abortgroup a b c d e)\n')
        regs=G.wait_register(m,lambda r:entry.value<G.gc_registers(r)['pc']<=entry.value+3,
            'emitter entry with active auth',timeout=300)
        assert m.memory_range(entry.value,len(code))==code
        flag=m.memory_range(active,1);assert flag!=b'\0'
        proof['entry']=dict(registers=regs,symbol=entry.name,code=code.hex(),active_address=active,active=flag.hex())
        m.command('~pcclearbreak')
        m.command(f's {slot:08x} '+' '.join(f'{x:02x}' for x in shim))
        assert m.memory_range(slot,len(shim))==shim
        proof['shim']=dict(address=slot,bytes=shim.hex(),original=saved.hex(),free_end=0xb3b0,abort_entry=abort)
        m.command(f'g {slot:04x}');m.command('t0')
        s=result(before,'*** VM: TYPE ERROR');(out/'abort.txt').write_text(s)
        m.command('t1')
        assert m.memory_range(active,1)==b'\0','auth survived abort'
        after=objects(m);assert after==prior,'abort changed prior code/directory'
        m.command(f's {slot:08x} '+' '.join(f'{x:02x}' for x in saved))
        assert m.memory_range(slot,len(saved))==saved
        proof['foreign_objects']=prior;proof['abort_closed']=True
        m.command('t0')
    finally:m.end_breakpoint_connection()
    form('(+ 4 5)','9','recovery')
    form('(abortanchor)','7','old-use')
    form('(defstruct afterabort a b c d e)','T','new-group')
    form('(afterabort-a (make-afterabort 42 2 3 4 5))','42','new-use')
    m.command('t1');assert m.memory_range(active,1)==b'\0'
except BaseException as exc:error=repr(exc);raise
finally:
    if run:outputs=R.finish_run(run)
    (out/'receipt.json').write_text(json.dumps(dict(status='HALT' if error else 'PASS',error=error,
        proof=proof,outputs=outputs,ELF=pack['elf'],medium=pack['medium'],binary=R.bind(binary),
        driver=R.bind(Path(__file__)),product_builds=0,device_contacts=0,
        limit='Explicit diagnostic abort shim; not a naturally occurring failure or a device witness.'),indent=2)+'\n')
