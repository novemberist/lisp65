"""Qualify the isolated carrier observer's hooks and compare its guest outcome."""
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT/'build/ov-crc16-boot-ledger-r1'
OUT = ROOT/'build/boot-only-carrier-observer-r2'


def main():
    header = (OUT/'observer/xemu/boot_observer.h').read_text()
    body = header[header.index('#define CARRIER_START'):header.index('static void boot_observe_instruction')]
    fixture = '''#include <stdio.h>
#include <stdlib.h>
#include <assert.h>
static struct { unsigned pc; } CPU65;
static unsigned char main_ram[65536];
static unsigned in_hypervisor, boot_world;
''' + body + '''
int main(void) {
    unsetenv("LISP65_CARRIER_WATCH");
    carrier_watch_write(CARRIER_START,1); assert(!carrier_writes);
    boot_world=1; CPU65.pc=CARRIER_MAIN; main_ram[2]=0x80; main_ram[3]=0xcf;
    carrier_watch_instruction(); assert(carrier_live && carrier_low==0xcf80);
    carrier_watch_write(CARRIER_START-1,1); carrier_watch_write(CARRIER_END,1);
    assert(!carrier_writes);
    carrier_watch_write(CARRIER_START,1); carrier_watch_write(CARRIER_END-1,1);
    assert(carrier_writes==2);
    main_ram[2]=0x7c; carrier_watch_instruction(); assert(carrier_low==0xcf7c);
    in_hypervisor=1; main_ram[3]=0; carrier_watch_instruction(); assert(carrier_low==0xcf7c);
    in_hypervisor=0; main_ram[3]=0xcf; CPU65.pc=CARRIER_RETURN;
    carrier_watch_instruction(); assert(!carrier_live);
    carrier_watch_write(CARRIER_START,1); assert(carrier_writes==2);
    return 0;
}
'''
    source = OUT/'observer-control.c'
    if source.exists():
        raise ValueError('do not overwrite a prior qualification')
    source.write_text(fixture)
    executable = OUT/'observer-control'
    subprocess.run(['cc','-O2','-Wall','-Wextra',str(source),'-o',str(executable)],check=True)
    subprocess.run([str(executable)],check=True)
    fast = (OUT/'observer/targets/mega65/cpu_custom_functions.h').read_text()
    mapper = (OUT/'observer/targets/mega65/memory_mapper.c').read_text()
    fast_hook = 'carrier_watch_write(mem_slot_wr_addr32[addr16 >> 8] + (addr16 & 0xFFU), data);'
    assert fast.count(fast_hook)==1
    assert mapper.count('carrier_watch_write(addr32, data);')==4
    # Removing the fast hook is exactly the first observer's incomplete form.
    assert fast.replace(fast_hook,'').count(fast_hook)!=1
    assert (BASE/'capture-r1/prompt.txt').read_bytes()==(OUT/'capture-r1/prompt.txt').read_bytes()
    old = (BASE/'capture-r1/boot.txt').read_text().splitlines()
    new = (OUT/'capture-r1/boot.txt').read_text().splitlines()
    assert old == new, 'observer changed boot ledger'
    write_log = (OUT/'writes.txt').read_text().splitlines()
    assert len(write_log)==1 and write_log[0].startswith('END ')
    _,low,writes = write_log[0].split()
    assert int(low)>=0xce00 and int(writes)==0
    receipt = dict(claim='NORMAL BOOT OBSERVATION; NOT ALL ERROR PATHS',
                   stack_low=int(low),carrier_writes=int(writes),
                   prompt_identical=True,boot_ledger_identical=True,
                   hook_controls='range/lifetime/stack/hypervisor and missing fast hook passed',
                   supersedes='r1 omitted CPU fast-pointer writes; not a complete writer witness',
                   files={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
                          for p in (source,OUT/'writes.txt',OUT/'capture-r1/boot.txt',
                                    OUT/'observer/build/bin/xmega65.native')},
                   product_builds=0,device_contacts=0)
    (OUT/'qualification.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps(receipt,indent=2))


if __name__ == '__main__':
    main()
