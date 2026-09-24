#!/usr/bin/env python3
"""Bounded MOS object/diagnostic-layout proof; never a product build or link."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile

from elf_truth import ElfTruth
from c2_no_pcrel16_gate import input_owners, linked_data_owners

ROOT = Path(__file__).resolve().parents[2]
BIN = ROOT/'tools/llvm-mos/bin'
SECTION = '.text.lisp65_startup_message'
EXPECTED = b'Initializing...\n\0'


def main():
    source = (ROOT/'src/repl.c').read_text()
    declaration = re.search(r'        static const char startup_message\[\][\s\S]+?;', source)
    assert declaration and declaration.group().count(SECTION) == 1
    assert 'emit_str(startup_message);' in source
    unit = ('extern void emit_str(const char *);\nvoid probe(void){\n' +
            declaration.group() + '\nemit_str(startup_message);\n}\n')
    with tempfile.TemporaryDirectory(prefix='startup-placement-') as temp:
        out = Path(temp)
        # An already-full ordinary constant owner and an independent verifier
        # boundary, copied from the consumed layout, not enlarged for this test.
        script = out/'layout.ld'
        script.write_text('SECTIONS { .text 0x2023 : { *(.text .text.*) }\n'
                          '.rodata 0xb61d : { BYTE(0); . = . + 878; *(.rodata .rodata.*) }\n'
                          'ASSERT(ADDR(.rodata)+SIZEOF(.rodata)<=0xb98c,"rodata owner overlap")\n'
                          '/DISCARD/ : { *(.comment) *(.llvm_addrsig) } }\n')
        results = {}
        for label, text in (('placed', unit),
                            ('old-rodata', re.sub(r'__attribute__\(\(section\("[^"]+"\)\)\)', '', unit))):
            c = out/(label+'.c'); c.write_text(text)
            obj = out/(label+'.o')
            subprocess.run([str(BIN/'mos-mega65-clang'), '-Os', '-fno-lto', '-c',
                            str(c), '-o', str(obj)], check=True)
            truth = ElfTruth.read(obj, llvm_readobj=BIN/'llvm-readobj', include_section_data=True)
            symbols = [s for s in truth.symbols if s.name.endswith('startup_message') and s.symbol_type == 'Object']
            assert len(symbols) == 1, [(s.name, s.symbol_type, s.bytes, s.section) for s in truth.symbols]
            symbol = symbols[0]; section = truth.section(symbol.section)
            assert symbol.symbol_type == 'Object' and symbol.bytes == len(EXPECTED)
            assert truth.section_bytes(section.name)[symbol.value:symbol.value+symbol.bytes] == EXPECTED
            elf = out/(label+'.elf'); mapfile = out/(label+'.map')
            link = subprocess.run([str(BIN/'ld.lld'), '-T', str(script), '--emit-relocs',
                                   '--unresolved-symbols=ignore-all', '-Map='+str(mapfile),
                                   str(obj), '-o', str(elf)], text=True, capture_output=True)
            if label == 'old-rodata':
                assert section.name.startswith('.rodata')
                assert link.returncode and 'rodata owner overlap' in link.stderr
                results[label] = 'REJECTED: full ordinary rodata owner'
                continue
            assert link.returncode == 0, link.stderr
            assert section.name == SECTION
            assert set(section.flags) == {'SHF_ALLOC'}, section.flags
            linked = ElfTruth.read(elf, llvm_readobj=BIN/'llvm-readobj', include_section_data=True)
            final = linked.symbol(symbol.name)
            assert final.section == '.text' and final.bytes == len(EXPECTED)
            owners, inputs = input_owners(linked, mapfile, BIN/'llvm-readobj')
            data = [r for r in owners if r['input_section'] == SECTION]
            assert len(data) == 1 and data[0]['kind'] == 'data'
            assert data[0]['start'] == final.value and data[0]['end'] == final.value+len(EXPECTED)
            proof = linked_data_owners(linked, truth, mapfile.read_text(), obj)
            assert len(proof) == 1 and proof[0]['bytes'] == EXPECTED.hex()
            results[label] = dict(flags=list(section.flags), symbol=symbol.name,
                                 bytes=symbol.bytes, section=SECTION, output=final.section,
                                 start=final.value, scanner_owner_kind=data[0]['kind'])
    print(json.dumps(dict(status='PASS: OBJECT PLACEMENT PROJECTION', rows=results,
                         compiler_sha256=hashlib.sha256((BIN/'mos-mega65-clang').read_bytes()).hexdigest(),
                         product_seed=0, product_final=0, product_link=0,
                         limits=['Diagnostic link, not the product; final scanner controls and byte ownership remain mandatory']), indent=2))


if __name__ == '__main__':
    main()
