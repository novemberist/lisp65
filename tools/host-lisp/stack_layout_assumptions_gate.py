#!/usr/bin/env python3
"""A4/A5/A6: compare linked frame producers with their linked consumers.

Read-only; never assembles, links or changes a product.  The default ELF is
the released authority's pair. --elf audits a successor without inheriting
the release's addresses, sizes or prologue depth. This is a layout check,
not a proof against hardware-stack exhaustion or arbitrary callee ABI bugs.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import subprocess

from elf_truth import ElfTruth

ROOT = Path(__file__).resolve().parents[2]
LLVM = ROOT / 'tools/llvm-mos/bin'
AUTHORITY = ROOT / 'config/c2-v220-public-build-authority.json'


class GateError(RuntimeError):
    pass


def require(ok, why):
    if not ok:
        raise GateError(why)


def address(operand):
    match = re.match(r'\$([0-9a-f]+)(?:\s|$)', operand)
    require(match, f'unknown direct target: {operand}')
    return int(match[1], 16)


def depth_at(rows, entry, target):
    """All local CFG paths; calls use the compiler's balanced-call ABI."""
    ordered = sorted(rows)
    following = dict(zip(ordered, ordered[1:]))
    pending, seen, depths = [(entry, 0)], set(), set()
    branches = {'beq', 'bne', 'bcc', 'bcs', 'bmi', 'bpl', 'bvc', 'bvs'}
    while pending:
        pc, depth = pending.pop()
        if (pc, depth) in seen:
            continue
        seen.add((pc, depth))
        require(0 <= depth <= 255, 'unbounded/unbalanced local frame')
        require(pc in rows, f'local CFG escapes at {pc:04x}')
        if pc == target:
            depths.add(depth)
            continue
        op, arg = rows[pc]
        require(op not in {'txs', 'tys', 'taz', 'rtn', 'phw', 'bsr'},
                f'unmodelled frame instruction: {op}')
        depth += int(op in {'pha', 'phx', 'phy', 'phz', 'php'})
        depth -= int(op in {'pla', 'plx', 'ply', 'plz', 'plp'})
        if op in {'rts', 'rti', 'brk'}:
            continue
        if op in branches | {'bra', 'jmp'}:
            dest = address(arg)
            # Tail exits outside this owner cannot return to the target.
            if dest in rows:
                pending.append((dest, depth))
            if op in {'bra', 'jmp'}:
                continue
        require(pc in following, f'fallthrough outside owner at {pc:04x}')
        pending.append((following[pc], depth))
    require(len(depths) == 1, f'nonunique/unreachable frame: {sorted(depths)}')
    return depths.pop()


def indexed_reads(rows):
    result = []
    for _, (op, arg) in sorted(rows.items()):
        match = re.fullmatch(r'\$(1[0-9a-f]{2}),x', arg)
        if op == 'lda' and match:
            result.append(int(match[1], 16) - 0x100)
    return result


def audit(model):
    functions, values = model['functions'], model['values']
    require(model['vector_target'] == values['c2_map_cpu_selector'], 'reader vector bypasses selector')
    intern, latch = functions['intern'], functions['lisp65_symbol22_latch_capture']
    calls = [pc for pc, (op, arg) in intern.items()
             if op == 'jsr' and address(arg) == values['lisp65_symbol22_latch_capture']]
    require(len(calls) == 1, 'intern/latch call population changed')
    depth = depth_at(intern, values['intern'], calls[0])
    # At latch entry: two bytes of latch JSR, then intern's saved registers,
    # then intern's caller return, low byte first at SP+depth+2+1.
    expected = [depth + 3, depth + 4]
    require(indexed_reads(latch) == expected, 'A4 latch/frame mismatch')

    irq, classifier = functions['c2_kernal_irq_handler'], functions['retired_window_brk_classifier']
    tails = [pc for pc, (op, arg) in irq.items()
             if op == 'jmp' and address(arg) == values['retired_window_brk_classifier']]
    require(len(tails) == 1, 'IRQ/classifier tail population changed')
    irq_depth = depth_at(irq, values['c2_kernal_irq_handler'], tails[0])
    require(indexed_reads(classifier) == [irq_depth+1, irq_depth+2, irq_depth+3],
            'A6 classifier/frame mismatch')

    identities = []
    for name in ('c2_stream_c2d_read', 'c2_stream_shelf_read'):
        sites = [pc for pc, (op, arg) in functions[name].items()
                 if op == 'jsr' and address(arg) == values['c2_facade_runtime_overlay_exec']]
        require(len(sites) == 1, f'A5 reader/vector population: {name}')
        identities.append(dict(function=name, jsr=sites[0], pushed_return=sites[0]+2,
                               offset=sites[0]+2-values[name]))
    selector = functions['c2_map_cpu_selector']
    immediates = [int(arg[2:], 16) for _, (op, arg) in sorted(selector.items())
                  if op == 'cmp' and re.fullmatch(r'#\$[0-9a-f]+', arg)]
    returns = [row['pushed_return'] for row in identities]
    require(immediates == [returns[0] >> 8, returns[0] & 255,
                           returns[1] >> 8, returns[1] & 255],
            'A5 selector/JSR return identity mismatch')
    # Also protect the selector's local frame, rather than just its literals.
    tsx = [pc for pc, (op, _) in selector.items() if op == 'tsx']
    require(len(tsx) == 1, 'selector TSX population')
    sd = depth_at(selector, values['c2_map_cpu_selector'], tsx[0])
    require(indexed_reads(selector) == [sd+2, sd+1, sd+1], 'selector stack slot drift')
    return dict(latch=dict(saved_bytes=depth, offsets=expected),
                classifier=dict(saved_bytes=irq_depth, offsets=indexed_reads(classifier)),
                selector=dict(saved_bytes=sd, identities=identities),
                claim='Linked frame layout and return-identity compatibility; no stack-capacity claim.')


def read_model(elf):
    truth = ElfTruth.read(elf, llvm_readobj=LLVM/'llvm-readobj', include_section_data=True)
    names = ('intern', 'lisp65_symbol22_latch_capture', 'c2_kernal_irq_handler',
             'retired_window_brk_classifier', 'c2_stream_c2d_read',
             'c2_stream_shelf_read', 'c2_map_cpu_selector', 'c2_facade_runtime_overlay_exec')
    model = dict(values={}, functions={})
    section_rows = {}
    for name in names:
        symbol = truth.symbol(name)
        model['values'][name] = symbol.value
        if name == 'c2_facade_runtime_overlay_exec':
            section = truth.section(symbol.section)
            offset = symbol.value-section.address
            raw = truth.section_bytes(symbol.section)[offset:offset+3]
            require(len(raw) == 3 and raw[0] == 0x4c, 'selector vector is not JMP absolute')
            model['vector_target'] = int.from_bytes(raw[1:], 'little')
            continue
        if symbol.section not in section_rows:
            text = subprocess.check_output([str(LLVM/'llvm-objdump'), '-d',
                '--no-show-raw-insn', '--section='+symbol.section, str(elf)], text=True)
            rows = {}
            for line in text.splitlines():
                m = re.match(r'^\s*([0-9a-f]+):\s+([a-z][a-z0-9]*)\s*(.*?)\s*$', line)
                if m:
                    arg = m[3].split(';')[0].split('<')[0].strip()
                    rows[int(m[1], 16)] = (m[2], arg)
            section_rows[symbol.section] = rows
        # IRQ includes its named return label and source-less tail, and owns
        # the entire dedicated input section. Other functions must be sized.
        if name == 'c2_kernal_irq_handler':
            rows = section_rows[symbol.section]
        else:
            require(symbol.bytes > 0, f'unsized function: {name}')
            rows = {pc: ins for pc, ins in section_rows[symbol.section].items()
                    if symbol.value <= pc < symbol.value+symbol.bytes}
        require(rows, f'no instructions: {name}')
        model['functions'][name] = rows
    return model


def controls(model):
    rejected = []
    for label, function in [('extra-intern-push', 'intern'),
                            ('extra-IRQ-push', 'c2_kernal_irq_handler'),
                            ('extra-selector-push', 'c2_map_cpu_selector')]:
        mutant = deepcopy(model)
        rows = mutant['functions'][function]
        first = min(rows)
        # Insert a new entry instruction in the decoded CFG, retaining the
        # original consumer slots. Addresses are model identities here.
        rows[first-1] = ('pha', '')
        mutant['values'][function] = first-1
        try:
            audit(mutant)
        except GateError:
            rejected.append(label)
        else:
            raise GateError('mutation survived: '+label)
    for function in ('c2_stream_c2d_read', 'c2_stream_shelf_read'):
        mutant = deepcopy(model)
        rows = mutant['functions'][function]
        site = next(pc for pc, (op, arg) in rows.items() if op == 'jsr'
                    and address(arg) == model['values']['c2_facade_runtime_overlay_exec'])
        rows[site+1] = rows.pop(site)
        try:
            audit(mutant)
        except GateError:
            rejected.append('moved-JSR-'+function)
        else:
            raise GateError('moved JSR mutation survived')
    return rejected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--elf', type=Path)
    parser.add_argument('--out', type=Path, default=ROOT/'build/stack-layout-assumptions/receipt.json')
    args = parser.parse_args()
    authority = json.loads(AUTHORITY.read_text())['raw_pair']['ELF']
    elf = args.elf or ROOT/authority['path']
    raw = elf.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    if args.elf is None:
        require(len(raw) == authority['bytes'] and sha == authority['sha256'], 'release ELF binding drift')
    model = read_model(elf)
    result = dict(status='PASS', elf=dict(path=str(elf), sha256=sha),
                  layout=audit(model), mutations_rejected=controls(model))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2)+'\n')
    print('stack-layout-assumptions: PASS A4/A5/A6, five rejected mutations')


if __name__ == '__main__':
    main()
