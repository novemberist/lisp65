"""Build an isolated, read-only guest writer/stack observer; no product build."""
import hashlib
import json
from pathlib import Path
import subprocess

from elf_truth import ElfTruth
from c2_crc_codegen_gate import disassembly_rows, _direct_operand

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'build/ov-crc16-boot-ledger-r1'
OUT = ROOT / 'build/boot-only-carrier-observer-r2'
ELF = ROOT / 'build/ov-crc16-product-r1/wplto/lisp65-c2-substitution-linked.prg.elf'


def main():
    OUT.mkdir(exist_ok=False)
    subprocess.run(['cp', '-a', '--reflink=auto', str(BASE/'observer'), str(OUT/'observer')], check=True)
    for name in ('configuration.json', 'run.py'):
        (OUT/name).write_bytes((BASE/name).read_bytes())
    truth = ElfTruth.read(ELF, llvm_readobj=ROOT/'tools/llvm-mos/bin/llvm-readobj')
    symbols = truth.symbol_values()
    main = truth.symbol('main')
    dump = subprocess.check_output([str(ROOT/'tools/llvm-mos/bin/llvm-objdump'),
                                   '-d', '--no-show-raw-insn', str(ELF)], text=True)
    rows = [r for r in disassembly_rows(dump) if r['section'] == main.section
            and main.value <= r['address'] < main.value + main.bytes]
    calls = [r for r in rows if r['opcode'] == 'jsr'
             and _direct_operand(r) == symbols['vm_runtime_overlay_install_island']]
    assert len(calls) == 1
    end_pc = calls[0]['address'] + 3
    start = (max(symbols['__lisp65_workbench_overlay_end'],
                 symbols['__lisp65_boot_bank3_stage_end']) + 1) & ~1
    header = OUT/'observer/xemu/boot_observer.h'
    text = header.read_text()
    seam = 'static void boot_observe_instruction(unsigned elapsed) {'
    extra = '''
static unsigned carrier_live, carrier_seen, carrier_low = 65535;
static unsigned long long carrier_writes;
static FILE *carrier_file;
void carrier_watch_write(unsigned at, unsigned data) {
    if (!carrier_live || at < CARRIER_START || at >= CARRIER_END) return;
    ++carrier_writes;
    if (carrier_file) { fprintf(carrier_file,"W %u %u %u %u\\n",CPU65.pc,at,data,in_hypervisor); fflush(carrier_file); }
}
static void carrier_watch_instruction(void) {
    if (!carrier_seen && boot_world == 1 && CPU65.pc == CARRIER_MAIN && !in_hypervisor) {
        carrier_seen=carrier_live=1;
        const char *path=getenv("LISP65_CARRIER_WATCH");
        if (path) { carrier_file=fopen(path,"w"); if(!carrier_file)abort(); }
    }
    if (!carrier_live) return;
    unsigned sp=main_ram[2]+256u*main_ram[3];
    if (!in_hypervisor && sp<carrier_low) carrier_low=sp;
    if (CPU65.pc == CARRIER_RETURN && !in_hypervisor) {
        carrier_live=0;
        if(carrier_file) { fprintf(carrier_file,"END %u %llu\\n",carrier_low,carrier_writes); fclose(carrier_file); carrier_file=NULL; }
    }
}
'''
    definitions = f'#define CARRIER_START {start}u\n#define CARRIER_END {start+704}u\n#define CARRIER_MAIN {main.value}u\n#define CARRIER_RETURN {end_pc}u\n'
    assert text.count(seam) == 1
    text = text.replace(seam, definitions + extra + seam + '\n    carrier_watch_instruction();', 1)
    header.write_text(text)
    mapper = OUT/'observer/targets/mega65/memory_mapper.c'
    text = mapper.read_text()
    seam = 'static void  main_ram_writer ( const Uint32 addr32, const Uint8 data ) {'
    assert text.count(seam) == 1
    text = text.replace(seam, 'extern void carrier_watch_write(unsigned, unsigned);\n' + seam, 1)
    # Both checked and unchecked physical RAM writes, including DMA, use these
    # callbacks. Observe before the actual write; never modify the guest value.
    assert text.count('\tmain_ram[addr32] = data;') == 4
    text = text.replace('\tmain_ram[addr32] = data;',
                        '\tcarrier_watch_write(addr32, data);\n\tmain_ram[addr32] = data;')
    mapper.write_text(text)
    fast = OUT/'observer/targets/mega65/cpu_custom_functions.h'
    text = fast.read_text()
    seam = '\t\tp[addr16 & 0xFFU] = data;'
    assert text.count(seam) == 1
    text = text.replace('extern int cpu_rmw_old_data;',
                        'extern void carrier_watch_write(unsigned, unsigned);\nextern int cpu_rmw_old_data;',1)
    text = text.replace(seam,
                        '\t\tcarrier_watch_write(mem_slot_wr_addr32[addr16 >> 8] + (addr16 & 0xFFU), data);\n'+seam,1)
    fast.write_text(text)
    command = json.loads((BASE/'build.json').read_text())['command']
    command = [arg.replace(str(BASE), str(OUT)) for arg in command]
    with (OUT/'build.log').open('w') as log:
        subprocess.run(command, check=True, stdout=log, stderr=subprocess.STDOUT)
    def bind(p):
        return dict(path=str(p.relative_to(ROOT)), sha256=hashlib.sha256(p.read_bytes()).hexdigest())
    (OUT/'build.json').write_text(json.dumps(dict(
        claim='OBSERVER BUILT; EXECUTION AND QUALIFICATION PENDING', command=command,
        inputs=[bind(ELF),bind(BASE/'observer/xemu/boot_observer.h'),
                bind(BASE/'observer/targets/mega65/memory_mapper.c')],
        outputs=[bind(header),bind(mapper),bind(fast),bind(OUT/'observer/build/bin/xmega65.native')],
        start=start,end=start+704,main=main.value,return_pc=end_pc,
        product_builds=0,device_contacts=0),indent=2)+'\n')


if __name__ == '__main__':
    main()
