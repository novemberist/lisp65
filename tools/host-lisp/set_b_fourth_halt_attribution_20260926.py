"""Read-only attribution of the fourth Seed's activation halt; no guest launch.

Stopped-state observations and a static transaction conflict are separate.
This tool does not claim the first executed failing predicate is known.
"""
from dataclasses import asdict
from pathlib import Path
import sys
sys.dont_write_bytecode = True
import set_b_producer as P
import set_b_fourth_seed_20260926 as S
from set_b_third_seed_inventory_halt_20260926 import instructions
from elf_truth import ElfTruth
ROOT = P.ROOT
OUT = S.OUT / 'halt-attribution-r1'


def main():
    OUT.mkdir(exist_ok=False)
    boot = P.load(ROOT / 'build/set-b-fourth-boot-r1/receipt.json')
    assert boot['status'] == 'HALT' and boot['steps'] == []
    elf = ROOT / boot['world']['ELF']['path']
    assert P.bind(elf) == boot['world']['ELF']
    assert S.require_auth().startswith('958a7d2a')
    dump = ROOT / 'build/set-b-fourth-boot-r1/run-boot/memory.bin'
    memory = dump.read_bytes()
    assert len(memory) == 393216
    t = ElfTruth.read(elf, llvm_readobj=ROOT/'tools/llvm-mos/bin/llvm-readobj', include_section_data=True)
    states = {}
    for name in ['c2_ready', 'c2r_boot_count', 'vm_status', 'c2r_gc_failed',
                 'rtov_busy', 'rtov_loaded_len', 'rtov_fault', 'rtov_family',
                 'rtov_family_generation', 'c2_phase_owner', 'c2_pending_roots',
                 'c2_committed_roots', 'c2_journal_count', 'gc_rootsp', 'c2_runtime']:
        sym = t.symbol(name)
        raw = memory[sym.value:sym.value + sym.bytes]
        states[name] = dict(symbol=asdict(sym), raw=raw.hex(), value=int.from_bytes(raw, 'little') if sym.bytes <= 2 else None)
    assert states['c2_ready']['value'] == 1 and states['c2r_boot_count']['value'] == 0
    tenants = S.PRODUCT / 'set-b-tenants.bin'
    assert memory[0x5de80:0x5fe80] == tenants.read_bytes()
    assert memory[0x5de20:0x5de68] == bytes(72)
    assert memory[0xc356:0xc356+1792] == bytes(1792)
    ins, command, disassembly = instructions(elf)
    (OUT/'linked-disassembly.txt').write_text(disassembly)
    owners = ['c2_retire_control', 'c2_retire_run', 'vm_runtime_overlay_exec_family',
              'vm_runtime_overlay_transaction_begin', 'vm_retire_prompt_quiescent']
    functions = {}
    for name in owners:
        sym = t.symbol(name)
        functions[name] = dict(symbol=asdict(sym), instructions=[r for a, r in ins[sym.section].items() if sym.value <= a < sym.value+sym.bytes])
    witnesses = []
    def prove(owner, address, raw, meaning):
        sym = t.symbol(owner)
        row = ins[sym.section][address]
        assert sym.value <= address < sym.value+sym.bytes and row['bytes'] == raw
        witnesses.append(dict(owner=owner, section=sym.section, instruction=row, meaning=meaning))
    prove('vm_runtime_overlay_exec_family', 0x2bff, 'a001', 'Y = 1')
    prove('vm_runtime_overlay_exec_family', 0x2c01, '8478', 'busy = 1 before loading and calling the tenant')
    prove('vm_runtime_overlay_exec_family', 0x2d49, '201925', 'indirect call to the loaded entry')
    prove('vm_runtime_overlay_exec_family', 0x2d72, '6478', 'busy cleared after the entry has returned')
    prove('c2_retire_control', 0xc4a8, '2019fc', 'tenant calls transaction_begin while executing')
    prove('vm_runtime_overlay_transaction_begin', 0xfc1c, 'a578', 'read busy')
    prove('vm_runtime_overlay_transaction_begin', 0xfc1e, '2901', 'test busy bit')
    prove('vm_runtime_overlay_transaction_begin', 0xfc20, 'a203', 'prepare ERR_BUSY = 3')
    prove('vm_runtime_overlay_transaction_begin', 0xfc24, 'f003', 'only busy == 0 continues validation')
    prove('vm_runtime_overlay_transaction_begin', 0xfc26, '4c70fc', 'busy branch to return')
    prove('vm_runtime_overlay_transaction_begin', 0xfc70, '8a', 'A = ERR_BUSY')
    prove('vm_runtime_overlay_transaction_begin', 0xfc71, '60', 'return ERR_BUSY')
    prove('c2_retire_control', 0xc4ab, 'a208', 'prepare C2_STREAM_ERR_STATE = 8')
    prove('c2_retire_control', 0xc4ae, 'd031', 'nonzero begin result goes to error return')
    prove('c2_retire_control', 0xc4e1, '8a', 'return state error')
    P.write(OUT/'linked-functions.json', functions)
    P.write(OUT/'receipt.json', dict(
        status='HALT PRESERVED; STOPPED STATE AND STATIC CONFLICT ATTRIBUTED',
        driver=P.bind(Path(__file__)), source_authority=S.require_auth(),
        boot=P.bind(ROOT/'build/set-b-fourth-boot-r1/receipt.json'), seed=P.bind(elf),
        memory=P.bind(dump), states=states, tenant_image=P.bind(tenants),
        tenants_byteidentical=True, journal_zero=True, overlay_window_zero=True,
        disassembly=dict(command=command, exit=0, output=P.bind(OUT/'linked-disassembly.txt')),
        functions=P.bind(OUT/'linked-functions.json'), witnesses=witnesses,
        source_inputs=[P.bind(ROOT/p) for p in ['src/optional/set_b_retire_control.c', 'src/vm_runtime_overlay.c']],
        conclusion='If normal control reaches transaction_begin, executing-tenant busy state forces ERR_BUSY; control returns STATE. Static integration conflict, not a boundary trace.',
        first_executed_failure='UNKNOWN: reset and earlier prompt predicates were not traced on this Seed',
        gc_rootsp_limit='Observed at stopped input only; cannot attribute the earlier prompt predicate from this value.',
        builds=0, links=0, guest_launches=0, device_contacts=0))
    print('PASS read-only attribution; product activation remains HALT; first executed failure unknown')


if __name__ == '__main__':
    main()
