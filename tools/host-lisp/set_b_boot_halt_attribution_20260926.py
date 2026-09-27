"""Read-only attribution of the positive-medium disarm halt; no guest rerun."""
from dataclasses import asdict
from pathlib import Path
import subprocess
import sys
sys.dont_write_bytecode = True
import set_b_producer as P
import runtime_overlay_bank as B
from elf_truth import ElfTruth
from set_b_third_seed_inventory_halt_20260926 import instructions

ROOT = P.ROOT
OUT = ROOT/'build/set-b-boot-halt-attribution-r4'
ELF = ROOT/'build/set-b-product-r3/wplto/resident-island-seed.prg.elf'


def main():
    OUT.mkdir(exist_ok=False)
    boot = ROOT/'build/set-b-boot-candidate-r2'
    receipt = P.load(boot/'receipt.json')
    assert receipt['status'] == 'HALT' and receipt['result']['ready'] == 1 and receipt['result']['retirement_latch'] == 0
    assert receipt['world']['ELF'] == P.bind(ELF)
    truth = ElfTruth.read(ELF,llvm_readobj=ROOT/'tools/llvm-mos/bin/llvm-readobj',include_section_data=True)
    dump = boot/'run-boot/memory.bin'; memory = dump.read_bytes(); assert len(memory) == 0x60000
    image = (ROOT/'build/set-b-product-r3/set-b-tenants.bin').read_bytes()
    observed = memory[0x5de80:0x5fe80]
    assert observed == image and B.crc16_ccitt_false(observed) == 0x5a58
    (OUT/'late-region.bin').write_bytes(observed)
    journal = memory[0x5de20:0x5de68]; assert journal == bytes(72)
    (OUT/'journal.bin').write_bytes(journal)
    state = {n:dict(symbol=asdict(truth.symbol(n)),hex=memory[truth.symbol(n).value:truth.symbol(n).value+truth.symbol(n).bytes].hex()) for n in ('c2_ready','c2r_boot_count','c2r_gc_failed','vm_status','c2_runtime')}
    decoded, command, text = instructions(ELF)
    (OUT/'disassembly.txt').write_text(text)
    sel = truth.symbol('c2_map_cpu_selector'); sec = truth.section(sel.section)
    code = truth.section_bytes(sel.section)[sel.value-sec.address:sel.value-sec.address+sel.bytes]
    # Match the complete emitted selector, allowing only its two target operands
    # and its two intended caller-derived return identities to vary.
    template = bytearray.fromhex('48daba bd0401 c9e3 d009 bd0301 c9b2 f012 800b c9e8 d007 bd0301 c9d7 f005 fa68 4c002b fa68 4c9522')
    assert len(code) == len(template) == 40
    expected = [truth.symbol('c2_stream_c2d_read').value+0x4b,truth.symbol('c2_stream_shelf_read').value+0xb0]
    for value, hi, lo in [(expected[0],7,14),(expected[1],20,27)]:
        template[hi] = value>>8; template[lo] = value&255
    template[33:35] = truth.symbol('vm_runtime_overlay_exec').value.to_bytes(2,'little')
    template[38:40] = truth.symbol('c2_map_cpu_read').value.to_bytes(2,'little')
    assert code == template
    facade = truth.symbol('c2_facade_runtime_overlay_exec')
    fs = truth.section(facade.section); fraw = truth.section_bytes(fs.name)[facade.value-fs.address:facade.value-fs.address+3]
    assert fraw == b'\x4c'+sel.value.to_bytes(2,'little')
    # Resolve each new call by its section AND PC; overlay VMAs are shared.
    calls = []
    for row in P.load(P.INPUTS)['tenants']:
        section = truth.section(row['section'])
        for pc, ins in decoded[section.name].items():
            raw = bytes.fromhex(ins['bytes'])
            if raw not in (b'\x20'+facade.value.to_bytes(2,'little'),b'\x4c'+facade.value.to_bytes(2,'little')): continue
            owners = [s for s in truth.symbols if s.section == section.name and s.symbol_type == 'Function' and s.bytes and s.value <= pc < s.value+s.bytes]
            assert len(owners) == 1
            if raw[0] == 0x20:
                stacked = [pc+2]
            else:
                owner = owners[0]
                prefix = truth.section_bytes(section.name)[owner.value-section.address:pc-section.address]
                assert prefix == bytes.fromhex('a4068408a4048406a4058407a005840464056409'), 'tail helper stack/register prologue drift'
                callsites = [(address, bytes.fromhex(i['bytes'])) for address,i in decoded[section.name].items() if bytes.fromhex(i['bytes']) in (b'\x20'+owner.value.to_bytes(2,'little'),b'\x4c'+owner.value.to_bytes(2,'little'))]
                assert callsites and all(i[0] == 0x20 for address,i in callsites), 'unexpected tail caller needs further stack proof'
                stacked = [address+2 for address,i in callsites]
            assert all(v not in expected for v in stacked)
            calls.append(dict(slot=row['slot'],section=section.name,owner=owners[0].name,call_pc=pc,
                instruction_hex=raw.hex(),stacked_returns=stacked,admitted_read_returns=expected,
                facade_pc=facade.value,selector_pc=sel.value,selected_tail_pc=sel.value+32,
                selected_target=truth.symbol('vm_runtime_overlay_exec').value,
                intended_target=truth.symbol('c2_map_cpu_read').value))
    assert {r['owner'] for r in calls} == {'rc_read','rm_read','rf_read','c2_retire_reset'} and len(calls) == 4
    reset = next(r for r in calls if r['owner'] == 'c2_retire_reset')
    assert reset['call_pc'] == 0xc3f4 and reset['stacked_returns'] == [0xc3f6]
    # For the actual reset return, the first high-byte compare fails, then the
    # second high-byte compare fails: $2374 JMP selects the overlay ABI.
    assert reset['stacked_returns'][0]>>8 not in [v>>8 for v in expected]
    # Direct compiler roots outside the copied tree are verified against the
    # exact Seed source commit and the Card L sealed source HEAD.
    commands = P.load(ROOT/'build/set-b-product-r3/commands.json'); roots = []
    for index, cmd in enumerate(commands):
        if '-c' not in cmd: continue
        path = ROOT/cmd[cmd.index('-c')+1]
        row = dict(command_index=index,source=P.bind(path))
        if not path.is_relative_to(ROOT/'build/set-b-product-r3/wplto'):
            relative = str(path.relative_to(ROOT))
            bound = subprocess.check_output(['git','show','7c659dfd:'+relative],cwd=ROOT)
            prior = subprocess.check_output(['git','show','cee48d03:'+relative],cwd=ROOT)
            assert path.read_bytes() == bound, relative
            if bound == prior:
                row['proof'] = 'byte-identical at Card L sealed HEAD and Set B Seed HEAD'
            else:
                assert relative == 'src/optional/card_l_stage.c' and relative in P.authority_files()
                P.require_auth()
                row['proof'] = 'explicitly authored Set B stage, bound by current source authority'
        else: row['proof'] = 'copied-tree source census, exact-context projection or admitted materialized input'
        roots.append(row)
    P.write(OUT/'compiler-roots.json',dict(status='PASS',roots=roots,count=len(roots)))
    P.write(OUT/'receipt.json',dict(status='HALT ATTRIBUTED: NEW READ CALLERS MISS EXISTING SELECTOR IDENTITY SET',
        driver=P.bind(Path(__file__)),elf=P.bind(ELF),boot_receipt=P.bind(boot/'receipt.json'),shutdown_memory=P.bind(dump),
        observed=dict(ready=1,retirement_latch=0,vm_status=memory[truth.symbol('vm_status').value],tenant_bytes_equal=True,
            tenant_crc16=B.crc16_ccitt_false(observed),journal_zero=True,state=state),
        selector=dict(symbol=asdict(sel),bytes_hex=code.hex(),read_return_identities=expected),calls=calls,
        disassembly_command=command,compiler_roots=P.bind(OUT/'compiler-roots.json'),
        evidence_limit='First-prompt/disarm observation plus shutdown snapshot and exact linked selector proof; no executed boot boundary trace. Does not establish which earlier stage first rejected or whether an arm was later cleared.',
        inference='The new reset and commit readers alias a context-selecting overlay vector. Their return identities select the overlay-execution ABI, not physical read. This is a native call-routing mismatch requiring repair design, not a CRC tolerance.',
        product_sources_changed=False,new_builds=0,new_links=0,new_guest_runs=0,device_contacts=0))
    print('PASS halt attribution: intact tenant image, zero journal; four new read callsites select overlay ABI')


if __name__ == '__main__': main()
