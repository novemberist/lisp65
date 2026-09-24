"""Read-only boot-carrier geometry preflight; not a lifetime admission."""
import argparse
import hashlib
import json
from pathlib import Path

from elf_truth import ElfTruth

ROOT = Path(__file__).resolve().parents[2]
DEFAULT = ROOT / 'build/ov-crc16-product-r1/wplto/lisp65-c2-substitution-linked.prg.elf'


def validate(start, size, floor, stack, writers):
    if size <= 0 or size > 704 or start & 1:
        raise ValueError('invalid carrier size/alignment')
    if floor != stack - 512 or start + size > floor:
        raise ValueError('boot stack floor violated')
    for name, lo, hi in writers:
        if hi < lo or max(start, lo) < min(start + size, hi):
            raise ValueError('live writer overlaps carrier: ' + name)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--elf', type=Path, default=DEFAULT)
    args = parser.parse_args()
    truth = ElfTruth.read(args.elf, llvm_readobj=ROOT / 'tools/llvm-mos/bin/llvm-readobj')
    values = truth.symbol_values()
    work_end = values['__lisp65_workbench_overlay_end']
    cold_end = values['__lisp65_boot_bank3_stage_end']
    start = (max(work_end, cold_end) + 1) & ~1
    floor = values['__lisp65_workbench_boot_slice_limit']
    stack = values['__stack']
    writers = [
        ('Workbench copy and wipe', values['__lisp65_workbench_overlay_start'], work_end),
        ('cold record load', values['__lisp65_boot_bank3_stage_start'], cold_end),
        ('runtime window load and wipe', values['__lisp65_workbench_overlay_start'],
         values['__lisp65_workbench_runtime_overlay_limit']),
        ('island wipe', 0x1800, 0x2000),
    ]
    validate(start, 704, floor, stack, writers)
    rejected = []
    mutations = [
        ('oversize', start, 705, floor, stack, writers),
        ('empty', start, 0, floor, stack, writers),
        ('unaligned', start+1, 704, floor, stack, writers),
        ('stack overlap', floor-702, 704, floor, stack, writers),
        ('lowered floor', start, 704, floor+2, stack, writers),
        ('window overwrite', start, 704, floor, stack,
         writers + [('injected write', start, start+1)]),
    ]
    for name, *case in mutations:
        try:
            validate(*case)
        except ValueError:
            rejected.append(name)
        else:
            raise AssertionError('mutation escaped: ' + name)
    print(json.dumps(dict(
        claim='GEOMETRY ONLY; NO SEED ADMISSION',
        elf=str(args.elf), sha256=hashlib.sha256(args.elf.read_bytes()).hexdigest(),
        start=start, cap=704, end=start+704, boot_stack_floor=floor,
        margin=floor-start-704, enumerated_writers=writers,
        rejected_mutations=rejected,
        pending=['complete writer/callee inventory including IRQ and errors',
                 'software stack low-water proof while carrier lives',
                 'authenticated extended PRG extraction and negative controls'],
        budget=dict(seed=0, finale=0, link=0)), indent=2))


if __name__ == '__main__':
    main()
