"""One diagnostic link of an extracted collector; no compilation or product write."""
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess
import sys

from elf_truth import ElfTruth

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'build/gc-layout-control-r1'
TOOLS = ROOT / 'tools/llvm-mos/bin'
ELF = ROOT / 'build/boot-only-carrier-product-r1/wplto/lisp65-c2-substitution-linked.prg.elf'
LTO = Path(str(ELF)[:-4] + '.lto.o')
ELF_SHA = '48f637a7d34fdbc8960cf58fd1c861df855fb8858fb6f746af1a9f489351b623'


def bind(p):
    p = ROOT / p
    raw = p.read_bytes()
    return dict(path=str(p.relative_to(ROOT)), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def write_once(p, raw):
    if isinstance(raw, dict):
        raw = (json.dumps(raw, indent=2) + '\n').encode()
    if isinstance(raw, str):
        raw = raw.encode()
    if p.exists():
        assert p.read_bytes() == raw, 'refuse replacement: ' + str(p)
    else:
        p.write_bytes(raw)


def read_truth(p):
    return ElfTruth.read(p, llvm_readobj=TOOLS / 'llvm-readobj', include_section_data=True)


def extracted_object(code, relocations, relocation_type, flags):
    """ELF32 ET_REL container, existing bytes + existing internal ADDR16 relocs.

    No instruction assembly: all external operands are already bound by the
    accepted link. One symbol denotes the extracted section's new base.
    """
    names = b'\0.text.gc_control\0.rela.text.gc_control\0.symtab\0.strtab\0.shstrtab\0'
    strings = b'\0gc_control\0'
    symbols = bytes(16) + struct.pack('<IIIBBH', 1, 0, len(code), 0x12, 0, 1)
    rels = b''.join(struct.pack('<IIi', offset, (1 << 8) | relocation_type, addend)
                    for offset, addend in relocations)
    data = bytearray(52)
    sections = [(0,) * 10]
    for name, typ, flg, payload, link, info, align, entsize in (
        ('.text.gc_control', 1, 6, code, 0, 0, 1, 0),
        ('.rela.text.gc_control', 4, 0, rels, 3, 1, 4, 12),
        ('.symtab', 2, 0, symbols, 4, 1, 4, 16),
        ('.strtab', 3, 0, strings, 0, 0, 1, 0),
        ('.shstrtab', 3, 0, names, 0, 0, 1, 0),
    ):
        data.extend(bytes((-len(data)) % align))
        offset = len(data)
        data.extend(payload)
        sections.append((names.index(name.encode() + b'\0'), typ, flg, 0,
                         offset, len(payload), link, info, align, entsize))
    data.extend(bytes((-len(data)) % 4))
    shoff = len(data)
    data.extend(b''.join(struct.pack('<10I', *s) for s in sections))
    ident = b'\x7fELF\x01\x01\x01' + bytes(9)
    data[:52] = struct.pack('<16sHHIIIIIHHHHHH', ident, 1, 0x1966, 1,
                           0, 0, shoff, flags, 52, 0, 0, 40, len(sections), 5)
    return bytes(data)


def model():
    assert bind(ELF)['sha256'] == ELF_SHA
    t, obj = read_truth(ELF), read_truth(LTO)
    gc = t.symbol('gc_collect')
    text = t.section(gc.section)
    code = t.section_bytes(gc.section)[gc.value-text.address:gc.value-text.address+gc.bytes]
    assert len(code) == 1491 and code[0] == 0x18 and code[-1] == 0x60
    source = obj.section('.text.gc_collect')
    assert source.bytes == len(code)
    internal = [(r.offset, r.addend) for r in obj.relocations
                if r.source_section == source.name and r.target == source.name]
    assert internal and all(0 <= add < len(code) for off, add in internal)
    for off, add in internal:
        assert int.from_bytes(code[off:off+2], 'little') == gc.value + add
    # Derive the numeric relocation kind and architecture flags from this LTO.
    raw = LTO.read_bytes()
    shoff = struct.unpack_from('<I', raw, 32)[0]
    relsec = obj.section('.rela.text.gc_collect')
    sh = struct.unpack_from('<10I', raw, shoff + 40 * relsec.index)
    numerical = {off: info & 255 for off, info, add in
                 struct.iter_unpack('<IIi', raw[sh[4]:sh[4]+sh[5]])}
    kinds = {numerical[off] for off, add in internal}
    assert len(kinds) == 1
    for r in obj.relocations:
        if r.source_section == source.name and r.target == source.name:
            assert r.relocation_type == 'R_MOS_ADDR16'
    dump = subprocess.check_output([str(TOOLS/'llvm-objdump'), '-d',
        '--disassemble-symbols=gc_collect', str(ELF)], text=True)
    instructions = []
    for line in dump.splitlines():
        m = re.match(r'\s*([0-9a-f]+):\s+((?:[0-9a-f]{2} )+)\s*(\S+)', line)
        if m:
            instructions.append((int(m[1], 16)-gc.value, bytes.fromhex(m[2]), m[3]))
    assert sum(len(b) for off, b, name in instructions) == len(code)
    branches = []
    for off, b, name in instructions:
        if b[0] in (0x10,0x30,0x50,0x70,0x90,0xb0,0xd0,0xf0,0x80):
            assert len(b) == 2
            target = off + 2 + int.from_bytes(b[1:], 'little', signed=True)
            assert 0 <= target < len(code)
            branches.append(dict(offset=off, target=target, opcode=b[0]))
    floor = 32
    limit = t.section('.lisp65_c2_mapped_far_facade').address - floor
    low = text.address + text.bytes
    crossing = lambda base, row: (base+row['offset']+2)//256 != (base+row['target'])//256
    # Predeclared adversarial control: maximize changed branch-page membership,
    # breaking ties by the lowest address; no iterative links or timings.
    candidates = range(low, limit-len(code)+1)
    chosen = max(candidates, key=lambda base: (sum(crossing(base,r) != crossing(gc.value,r)
                                                  for r in branches), -base))
    changed = [dict(r, old_crossing=crossing(gc.value,r), new_crossing=crossing(chosen,r))
               for r in branches if crossing(gc.value,r) != crossing(chosen,r)]
    assert changed and chosen + len(code) <= limit
    reloc_code = bytearray(code)
    expected = bytearray(code)
    for off, add in internal:
        reloc_code[off:off+2] = b'\0\0'
        expected[off:off+2] = (chosen+add).to_bytes(2, 'little')
    objraw = extracted_object(bytes(reloc_code), internal, kinds.pop(), struct.unpack_from('<I',raw,36)[0])
    result = dict(status='PASS: PRELINK EXTRACTED MACHINE BODY',
                  original=gc.value, relocated=chosen, bytes=len(code),
                  free_interval=[low,limit], floor=floor, internal_relocations=internal,
                  changed_branch_pages=changed, branch_count=len(branches),
                  original_body_sha256=hashlib.sha256(code).hexdigest(),
                  expected_body_sha256=hashlib.sha256(expected).hexdigest(),
                  inputs=[bind(ELF),bind(LTO),bind(TOOLS/'ld.lld'),bind(Path(__file__))])
    return result, objraw, bytes(expected)


def main():
    assert sys.argv[1:] in (['preflight'], ['link'])
    OUT.mkdir(exist_ok=True)
    result, objraw, expected = model()
    write_once(OUT/'collector.o', objraw)
    write_once(OUT/'expected.bin', expected)
    script = (f'ENTRY(gc_control)\nSECTIONS {{ .text.gc_control 0x{result["relocated"]:x} : '
              '{ KEEP(*(.text.gc_control)) } /DISCARD/ : { *(.comment) *(.note*) } }\n')
    write_once(OUT/'control.ld', script)
    # Read the generated container back with the pinned independent ELF reader.
    generated = read_truth(OUT/'collector.o')
    assert generated.symbol('gc_control').bytes == result['bytes']
    assert len(generated.relocations) == len(result['internal_relocations'])
    write_once(OUT/'preflight.json', result)
    if sys.argv[1] == 'link':
        assert not (OUT/'link-invocation.json').exists(), 'one diagnostic link already consumed'
        command = [str(TOOLS/'ld.lld'), '-T', str(OUT/'control.ld'), '--emit-relocs',
                   '-o', str(OUT/'control.elf'), str(OUT/'collector.o')]
        write_once(OUT/'link-invocation.json', dict(command=command, diagnostic_links=1,
                   seed=0, final=0, product_links=0, preflight=bind(OUT/'preflight.json')))
        run = subprocess.run(command, capture_output=True, text=True)
        write_once(OUT/'link.log', run.stdout+run.stderr)
        assert run.returncode == 0, 'diagnostic link failed; no retry authorized'
        linked = read_truth(OUT/'control.elf')
        assert linked.section_bytes('.text.gc_control') == expected
        assert linked.symbol('gc_control').value == result['relocated']
        write_once(OUT/'linked.json', dict(status='PASS: EXACT RELOCATED BODY',
                   ELF=bind(OUT/'control.elf'), body=bind(OUT/'expected.bin'),
                   preflight=bind(OUT/'preflight.json'), diagnostic_links=1))
    print(json.dumps({k:v for k,v in result.items() if k not in ('inputs','internal_relocations')},indent=2))


if __name__ == '__main__':
    main()
