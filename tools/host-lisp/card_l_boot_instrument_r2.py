"""Build per-role ELF-derived boot observers only; never launch an emulator."""
import json
from pathlib import Path
import re
import subprocess
from boot_ledger_observer import configure
from card_l_r1_common import ROOT, worlds, N, ElfTruth
from c2_crc_codegen_gate import disassembly_rows, _direct_operand

OUT = ROOT/'build/card-l-boot-instrument-r2'
PENDING = ROOT/'build/card-l-r1/pending-files.txt'

def main():
    canonical = worlds()
    assert canonical[1]['medium']['sha256'] == 'ac05fdea6e6fb00b2e10b31c2ac30a3bd5d7530908a88c0aaa388cf62a0c1cc7'
    OUT.mkdir(exist_ok=False)
    configs = []
    try:
        for w, base, loader in zip(canonical,
            ['build/nested-error-recovery-native-boot-r1', 'build/card-l-boot-instrument-r1'],
            ['build/nested-error-recovery-seed-medium-r1/packed/autoboot.c65.elf',
             'build/card-l-seed-medium-r2/media-seed/autoboot.c65.elf']):
            base = ROOT/base
            dest = OUT/w['role']; dest.mkdir()
            subprocess.run(['cp', '-a', '--reflink=auto', str(base/'observer'), str(dest/'observer')], check=True)
            elf = N.checked_binding(w['ELF'])
            configure(dest, paths=[ROOT/loader, elf], medium=w['medium'])
            truth = ElfTruth.read(elf, llvm_readobj=ROOT/'tools/llvm-mos/bin/llvm-readobj')
            main = truth.symbol('main'); values = truth.symbol_values()
            dump = subprocess.check_output([str(ROOT/'tools/llvm-mos/bin/llvm-objdump'), '-d', '--no-show-raw-insn', str(elf)], text=True)
            calls = [r for r in disassembly_rows(dump) if r['section']==main.section
                     and main.value<=r['address']<main.value+main.bytes and r['opcode']=='jsr'
                     and _direct_operand(r)==values['vm_runtime_overlay_install_island']]
            assert len(calls)==1
            changes = dict(CARRIER_START=values['__lisp65_boot_carrier_start'],
                CARRIER_END=values['__lisp65_boot_carrier_end'], CARRIER_MAIN=main.value,
                CARRIER_RETURN=calls[0]['address']+3)
            header = dest/'observer/xemu/boot_observer.h'; raw = header.read_text()
            for key, value in changes.items():
                raw, count = re.subn(r'#define '+key+r' \d+u', f'#define {key} {value}u', raw)
                assert count==1
            header.write_text(raw)
            receipt = base/('instrument.json' if w['role']=='candidate' else 'build.json')
            command = [arg.replace(str(base),str(dest)) for arg in json.loads(receipt.read_text())['command']]
            # Force rebuilding the CPU translation unit that includes both generated headers.
            (dest/'observer/xemu/cpu65.c').touch()
            with (dest/'build.log').open('w') as log:
                subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, check=True)
            w['binary'] = N.bind(dest/'observer/build/bin/xmega65.native')
            config = json.loads((dest/'configuration.json').read_text())
            configs.append(dict(role=w['role'], **config, carrier=changes,
                binary=w['binary'], command=command, parent=N.bind(receipt)))
        config_path = OUT/'configuration.json'
        config_path.write_text(json.dumps(dict(status='CONFIGURED AND HOST BUILT; LIVE QUALIFICATION PENDING',
            worlds=configs, product_builds=0, observer_builds=2),indent=2)+'\n')
        (OUT/'instrument.json').write_text(json.dumps(dict(worlds=canonical,
            configuration=N.bind(config_path), parent=N.bind(ROOT/'build/card-l-boot-instrument-r1/instrument.json'),
            product_builds=0, observer_builds=2),indent=2)+'\n')
    finally:
        with PENDING.open('a') as f:
            for p in sorted(OUT.rglob('*')):
                if p.is_file() or p.is_symlink(): f.write(str(p.relative_to(ROOT))+'\n')

if __name__=='__main__': main()
