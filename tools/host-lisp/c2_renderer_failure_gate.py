#!/usr/bin/env python3
"""Execute final-ELF leaf failure paths in headless Xemu, not source models.

The existing medium only starts the test harness. The selected ELF's exact
function bytes are loaded at their linked VMAs in disposable emulator RAM.
This is a leaf ABI test, not packed-medium or device acceptance.
"""
import argparse
import json
from pathlib import Path
import re

from elf_truth import ElfTruth
import dwx_retroactive_red_replay as R


def require(ok, message):
    if not ok:
        raise ValueError(message)


def run(args):
    truth = ElfTruth.read(args.elf, llvm_readobj=args.readobj, include_section_data=True)
    identities = {n: R.bind(getattr(args, n)) for n in ('elf', 'medium', 'xemu', 'readobj')}
    text = truth.section('.text')
    slot = text.address + text.bytes
    # The harness must fit in the explicitly unused ordinary-text gap.
    successors = [s.address for s in truth.sections if s.bytes and 'SHF_ALLOC' in s.flags
                  and slot <= s.address < 0xc000]
    require(successors and min(successors)-slot >= 12, 'no room for ABI harness')
    args.out.mkdir(parents=True, exist_ok=False)
    session = R.start_run('candidate-elf-leaf-abi', args.medium, args.out, args)
    monitor = session['monitor']
    rows = []

    def put(address, data):
        for i in range(0, len(data), 16):
            monitor.command(f's {address+i:08x} '+' '.join(f'{b:02x}' for b in data[i:i+16]))
        require(monitor.memory_range(address, len(data)) == data, 'RAM load readback differs')

    def function(name):
        s = truth.symbol(name)
        section = truth.section(s.section)
        data = truth.section_bytes(s.section)[s.value-section.address:s.value-section.address+s.bytes]
        require(data and len(data) == s.bytes, 'missing function extent')
        return s, data

    def execute(kind, mutant=False, high=1):
        name = 'lisp65_error_overlay_entry' if kind == 'renderer' else 'c2_map_cpu_read'
        symbol, original = function(name)
        code = bytearray(original)
        if kind == 'renderer':
            # Candidate null guard: LDA zp / ORA zp / BNE over symbolic JMP.
            require(code[0] == 0xa5 and code[2] == 0x05 and code[4:7] == b'\xd0\x03\x4c',
                    'null-context entry contract changed')
            jump = 7
        else:
            rc7 = truth.symbol('__rc7').value
            pattern = bytes([0xa5, rc7, 0xf0, 3, 0x4c])
            positions = [i for i in range(len(code)) if code[i:i+5] == pattern]
            require(len(positions) == 1, 'length rejection edge not uniquely identified')
            jump = positions[0]+5
        target = int.from_bytes(code[jump:jump+2], 'little')
        offset = target-symbol.value
        expected = b'\xa9\x01\x80' if kind == 'renderer' else b'\xa9\x00\x60'
        require(code[offset:offset+3] == expected, 'failure target is not the bound return block')
        if mutant:
            code[jump:jump+2] = (target-1).to_bytes(2, 'little')
        monitor.command('t1')
        put(symbol.value, code)
        # SEI; LDA #0; LDX #0; JSR selected entry; NOP.
        harness = b'\x78\xa9\x00\xa2\x00\x20'+symbol.value.to_bytes(2, 'little')+b'\xea'
        put(slot, harness)
        put(truth.symbol('__rc2').value, b'\0\0')
        put(truth.symbol('__rc6').value, bytes([0, high if kind == 'map' else 0]))
        put(0xa9, b'\x55')
        if kind == 'map':
            put(truth.symbol('__lisp65_c2_fixed_bank0_runtime').value+42, b'\0')
        monitor.command(f'g {slot:04x}')
        trace = []
        previous = slot
        no_writes = True
        returned = False
        for _ in range(80):
            # The complete executed renderer instruction population is read-only.
            # Caller JSR writes its stack frame and is outside that population.
            if symbol.value <= previous < symbol.value+len(code) and kind == 'renderer':
                opcode = code[previous-symbol.value]
                no_writes &= opcode in (0xa5, 0x05, 0xd0, 0x4c, 0xa9, 0x80, 0xa3, 0x60)
            raw = monitor.command('t')
            match = re.search(r'^\s*([0-9a-f]{4})\s+([0-9a-f]{2})\s+', raw, re.I|re.M)
            require(match is not None, 'monitor register response missing')
            pc, a = (int(match[i], 16) for i in (1, 2))
            trace.append({'pc': pc, 'a': a, 'monitor': raw})
            if pc == slot+8:
                returned = True
                break
            previous = pc
        marker = monitor.memory_range(0xa9, 1).hex()
        passed = returned and a == (1 if kind == 'renderer' else 0) and any(
            row['pc'] == target for row in trace)
        if kind == 'renderer':
            passed &= no_writes and marker == '55'
        require(passed != mutant, 'ABI control or off-by-one mutation did not discriminate')
        rows.append({'kind': kind, 'mutant': mutant, 'high_length': high,
            'entry': symbol.value, 'expected_target': target, 'returned': returned,
            'return_a': a, 'passed_contract': bool(passed), 'trace': trace,
            'renderer_no_write_instructions': no_writes if kind == 'renderer' else None,
            'marker_after': marker})

    try:
        execute('renderer')
        execute('renderer', mutant=True)
        for high in (1, 2, 255):
            execute('map', high=high)
        execute('map', mutant=True)
    finally:
        monitor.command('t1')
        outputs = R.finish_run(session)
    require(identities == {n: R.bind(getattr(args, n)) for n in identities}, 'input identity changed')
    result = {'status': 'PASS', 'identities': identities, 'rows': rows, 'outputs': outputs,
        'claim': 'Executed final-ELF leaf ABI paths in emulator RAM; no medium or device acceptance.',
        'device_contacts': 0, 'product_links': 0}
    (args.out/'receipt.json').write_text(json.dumps(result, indent=2)+'\n')
    print('PASS: candidate ELF failure paths and both off-by-one mutations')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('elf', 'readobj', 'medium', 'xemu', 'rom', 'sd-image', 'out'):
        parser.add_argument('--'+name, type=Path, required=True)
    parser.add_argument('--timeout', type=int, default=120)
    run(parser.parse_args())
