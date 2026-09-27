"""Existing fourth Seed: trace reset and first retirement without mutation/link."""
import argparse
import inspect
from pathlib import Path
import set_b_producer as P
import set_b_fourth_seed_20260926 as S
import set_b_read_path_trace_20260926 as T
from set_b_third_seed_inventory_halt_20260926 import instructions
from elf_truth import ElfTruth
ROOT=P.ROOT


def trace(monitor, world, out, steps, result):
    assert world['ELF']['sha256']=='2ba1deb4004ee7115dc673f29395ff1a0a7f91a437ff1f8d3b45d4fd197f9919'
    boundary=T.boundary
    boundary(monitor,0xa85d,'stage succeeded; call reset',steps,'20e1fe')
    r=boundary(monitor,0xc3f4,'reset physical-reader call',steps,'209522')
    destination=int.from_bytes(bytes.fromhex(r['zp'])[6:8],'little')
    result['read_destination']=destination
    result['destination_before']=monitor.memory16(destination)[0]
    r=boundary(monitor,0xc3f7,'reset physical-reader returned',steps,'a003')
    result['reader_return']=r['a'];result['destination_after']=monitor.memory16(destination)[0]
    r=boundary(monitor,0xc416,'reset status selected',steps,'98')
    result['reset_status']=r['a']
    boundary(monitor,0xa860,'reset returned; before READY',steps,'a201')
    boundary(monitor,0xa862,'READY set',steps,'868c')
    if result['reset_status']==0:
        r=boundary(monitor,0x2a67,'first retirement resident entry',steps,'48')
        result['first_mode']=r['a']
        r=boundary(monitor,0xc368,'first control entry',steps,'18')
        elf=ROOT/world['ELF']['path']
        truth=ElfTruth.read(elf,llvm_readobj=ROOT/'tools/llvm-mos/bin/llvm-readobj')
        ins,command,raw=instructions(elf);(out/'disassembly.txt').write_text(raw)
        sym=truth.symbol('c2_retire_control');rows=ins[sym.section]
        trace_rows=[]
        # Walk only the bound control owner. Step over its calls and preserve
        # both pre-call state and return state. The monitor breakpoint opcode
        # has already executed, so post-call rows say exactly where they stop.
        for index in range(1200):
            r=T.registers(monitor);pc=r['pc']
            assert r['b']==0 and pc in rows and sym.value<=pc<sym.value+sym.bytes,(index,r)
            instruction=rows[pc]
            assert monitor.memory_range(pc,len(bytes.fromhex(instruction['bytes']))).hex()==instruction['bytes']
            r.update(instruction=instruction,busy=monitor.memory16(0x78)[0],roots=monitor.memory16(0x5c)[0],arm=monitor.memory16(0x31)[0],phase_owner=monitor.memory16(0x89)[0])
            z=monitor.memory_range(0,32);d=int.from_bytes(z[22:24],'little')
            r['dispatch_address']=d;r['dispatch']=monitor.memory_range(d,5).hex()
            trace_rows.append(r)
            if pc==0xc4e1:
                result['control_status']=r['x'];break
            if instruction['mnemonic']=='jsr':
                after=pc+3;target=int.from_bytes(bytes.fromhex(instruction['bytes'])[1:],'little')
                if target==0xfc19:
                    b=boundary(monitor,0xfc1c,'transaction begin reads busy',steps,'a578')
                    result['busy_read']=b['a']
                    b=boundary(monitor,0xfc70,'transaction begin return selected',steps,'8a')
                    result['begin_status']=b['a']
                boundary(monitor,after,'control call return '+hex(pc),steps,rows[after]['bytes'])
            else:
                monitor.command('t')
        else:raise AssertionError('Control walk exceeded bound')
        P.write(out/'control-walk.json',dict(rows=trace_rows,disassembly_command=command))
        boundary(monitor,0x2ac7,'first control returns to resident',steps,'aa')
        # All refusal paths must leave the normal boot and prompt available.
    monitor.end_breakpoint_connection();monitor.command('t0')
    screen=monitor.wait_screen(['LISP65>'],timeout=180);(out/'boot-screen.txt').write_text(screen)
    monitor.command('t1')
    result['ready_at_prompt']=monitor.memory16(0x8c)[0]
    result['arm_at_prompt']=monitor.memory16(0x31)[0]
    result['tenants_intact']=monitor.memory_range(0x5de80,8192)==(S.PRODUCT/'set-b-tenants.bin').read_bytes()
    result['journal']=monitor.memory_range(0x5de20,72).hex()
    assert result['ready_at_prompt']==1 and result['arm_at_prompt']==0 and result['tenants_intact']
    assert result['journal']==bytes(72).hex()
    print('PASS existing-Seed trace:',result,flush=True)


def main(out):
    S.require_auth()
    source=inspect.getsource(T.main)
    source=source.replace('build/set-b-product-r3/','build/set-b-product-r4/')
    start=source.index('            # All PCs bound');end=source.index('        except BaseException:',start)
    source=source[:start]+'            trace(monitor,world,out,steps,result)\n'+source[end:]
    source=source.replace('PASS: EXECUTED RESET REFUSAL ATTRIBUTION','PASS: EXECUTED FOURTH SEED BOUNDARY ATTRIBUTION')
    evidence=ROOT/'build/set-b-transaction-trace-driver-r1';evidence.mkdir(exist_ok=False)
    (evidence/'executed.py').write_text(source)
    P.write(evidence/'binding.json',dict(driver=P.bind(Path(__file__)),parent=P.bind(Path(T.__file__)),executed=P.bind(evidence/'executed.py'),source_authority=S.require_auth(),product_links=0))
    ns=dict(vars(T));ns.update(trace=trace,MEDIAROOT=ROOT/'build/set-b-seed-medium-r5',__file__=__file__)
    exec(compile(source,str(evidence/'executed.py'),'exec'),ns);ns['main'](out,'candidate')


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',type=Path,required=True)
    main(ap.parse_args().out.resolve())
