"""ca9af627: stopped-memory attribution on existing anchor Final; no build/link."""
import argparse,json,os,re,time,traceback
from pathlib import Path
import native_cycle_stationary as N
import dwx_retroactive_red_replay as R
import dwx_comfort_resume as C
from elf_truth import ElfTruth
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'build/retained-callable-writer-r1'

def main():
    OUT.mkdir(exist_ok=False)
    identity=json.loads((ROOT/'build/anchor-cache-projection-r1/instrument.json').read_text())
    world=identity['worlds'][0]
    os.environ['LISP65_COST_CONFIG']=world['cost_config']
    os.environ['LISP65_DWX_PC_OUTPUT']=str(OUT/'pc-current.txt')
    elf=N.checked_binding(world['ELF']);binary=N.checked_binding(world['binary']);medium=N.checked_binding(world['medium'])
    t=ElfTruth.read(elf,llvm_readobj=ROOT/'tools/llvm-mos/bin/llvm-readobj')
    status=t.symbol('vm_status').value
    args=argparse.Namespace(xemu=binary,rom=Path(str(Path.home() / '.local/share/xemu-lgb/mega65/MEGA65.ROM')),sd_image=Path(str(Path.home() / '.local/share/xemu-lgb/mega65/mega65.img')),timeout=600)
    parent=R.ProbeMonitor
    class Monitor(parent):
        def wait_screen(self,required,timeout=20):return super().wait_screen(required,timeout=120)
    R.ProbeMonitor=Monitor
    run=None;captures=[];error=None
    form="(dotimes (n 54) (eval '(defun capfill () 7)))";preparation=[]
    def dump(m,label):
        record=dict(label=label,registers=m.command('r'),status=m.memory16(status)[0],regions={})
        for name,address in [('bank0',0),('bank1',0x10000),('bank2',0x20000),('c2d',0x50000)]:
            data=bytearray()
            for at in range(address,address+65536,256):
                response=m.command(f'M {at:08x}')
                rows=re.findall(r':([0-9A-Fa-f]{8}):([0-9A-Fa-f]{32})',response)
                assert [int(a,16) for a,b in rows]==list(range(at,at+256,16))
                data.extend(b''.join(bytes.fromhex(b) for a,b in rows))
            p=OUT/f'{label}-{name}.bin';p.write_bytes(data);record['regions'][name]=N.bind(p)
        p=OUT/f'{label}-screen.txt';p.write_text(m.screen());record['screen']=N.bind(p)
        captures.append(record);(OUT/'captures.json').write_text(json.dumps(captures,indent=2)+'\n')
        print(label,record['status'],record['registers'],flush=True)
    try:
        run=R.start_run('lambda',medium,OUT,args);m=run['monitor']
        for label,expression,expected in [('package','(require "defstruct")','T')]:
            before=m.screen();m.type_text(expression+'\n');deadline=time.monotonic()+600
            while time.monotonic()<deadline:
                screen=m.screen()
                if C.fresh_result(before,screen,expected) and C.active(screen):break
                time.sleep(.1)
            else:raise AssertionError('preparation failed: '+label+'\n'+screen)
            path=OUT/(label+'-screen.txt');path.write_text(screen)
            preparation.append(dict(form=expression,expected=expected,screen=N.bind(path)))
            print(label,'PASS',flush=True)
            m.command('t1');dump(m,label);m.command('t0')
        m.command('t1');dump(m,'before')
        assert m.memory16(status)[0]==0
        watch=0x2cc23;previous=m.memory16(watch)[0]
        m.begin_breakpoint_connection()
        m.command(f'w {watch:08x}');m.command(f'b {t.symbol("vm_status_error_code").value:04x}');m.command('t0')
        m.type_text(form+'\n');deadline=time.monotonic()+300
        changed=[]
        while time.monotonic()<deadline:
            value=m.memory16(watch)[0]
            if value!=previous:
                m.command('t1');dump(m,f'write-{len(changed)}')
                changed.append(dict(before=previous,after=value))
                print('watch',changed[-1],flush=True)
                if previous==0xb5 and value==0:break
                previous=value;m.command('t0')
            time.sleep(.02)
        else:raise AssertionError('no published-code zero transition')
        m.end_breakpoint_connection()
    except BaseException:
        error=traceback.format_exc();raise
    finally:
        output=R.finish_run(run) if run else None
        (OUT/'receipt.json').write_text(json.dumps(dict(status='HALT: PROBE ERROR' if error else 'CAPTURED: CODE WRITE TRANSITIONS',
            authority='ca9af627',form=form,preparation=preparation,world=world,vm_status_address=status,captures=captures,output=output,error=error,
            driver=N.bind(Path(__file__)),builds=0,links=0,seeds=0,device_contacts=0),indent=2)+'\n')
if __name__=='__main__':main()
