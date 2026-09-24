"""Exercise carrier placement ASSERTs with tiny synthetic MOS objects, not product links."""
import json
from pathlib import Path
import subprocess
from boot_only_carrier_linker import FRAGMENT
from elf_truth import ElfTruth

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT/'tools/llvm-mos/bin'
OUT = ROOT/'build/boot-only-carrier-linker-fixture-r1'
SCRIPT = '''MEMORY { ram (rwx) : ORIGIN = 0x1800, LENGTH = 0xb800 }
SECTIONS {
 .text 0x2001 : { *(.text*) } >ram
 .lisp65_resident_island 0x1800 : AT(0x30000) { *(.island) } >ram
}
__stack = 0xd000;
__lisp65_workbench_required_boot_stack = 512;
__lisp65_workbench_overlay_end = 0xca9e;
__lisp65_boot_bank3_stage_end = 0xc933;
__lisp65_workbench_runtime_overlay_limit = 0xca56;
__lisp65_workbench_boot_slice_limit = __stack - __lisp65_workbench_required_boot_stack;
'''
ASM = '''.section .text,"ax",@progbits
.globl _start
_start: rts
.section .island,"ax",@progbits
.byte 0x60
.section .lisp65_boot_carrier,"ax",@progbits
.globl vm_install_staged_boot_overlay
.type vm_install_staged_boot_overlay,@function
vm_install_staged_boot_overlay: rts
.size vm_install_staged_boot_overlay,1
.globl vm_runtime_overlay_install_island
.type vm_runtime_overlay_install_island,@function
vm_runtime_overlay_install_island: rts
.size vm_runtime_overlay_install_island,1
.space FILL
'''


def main():
    OUT.mkdir(exist_ok=False)
    results = []
    for name,fill,script,ok in [
        ('fits',696,SCRIPT,True),
        ('oversize',703,SCRIPT,False),
        ('stack-overlap',696,SCRIPT.replace('0xca9e','0xcdf0'),False),
        ('stack-floor-change',696,SCRIPT.replace('= 512','= 510'),False),
        ('runtime-window-overlap',696,SCRIPT.replace('0xca56','0xcb00'),False),
    ]:
        source = OUT/(name+'.s'); source.write_text(ASM.replace('FILL',str(fill)))
        obj = OUT/(name+'.o')
        subprocess.run([str(TOOLS/'mos-mega65-clang'),'-c',str(source),'-o',str(obj)],check=True)
        ld = OUT/(name+'.ld'); ld.write_text(script+FRAGMENT)
        elf = OUT/(name+'.elf')
        command = [str(TOOLS/'ld.lld'),'-T',str(ld),str(obj),'-o',str(elf)]
        result = subprocess.run(command,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        (OUT/(name+'.log')).write_text(result.stdout+result.stderr)
        assert (result.returncode==0)==ok, (name,result.stderr)
        row = dict(name=name,accepted=ok,command=command)
        if ok:
            truth = ElfTruth.read(elf,llvm_readobj=TOOLS/'llvm-readobj')
            sec = truth.section('.lisp65_boot_carrier')
            assert sec.address==0xca9e and sec.bytes==698
            row.update(address=sec.address,bytes=sec.bytes)
        else:
            assert 'boot-only carrier' in result.stderr
        results.append(row)
    (OUT/'receipt.json').write_text(json.dumps(dict(
        claim='SYNTHETIC LINKER FIXTURE ONLY',results=results,
        product_seed=0,product_finale=0,product_link=0),indent=2)+'\n')
    print('boot-only-carrier-linker-fixture: PASS positive and 4 negative links; product budget 0/0/0')


if __name__ == '__main__':
    main()
