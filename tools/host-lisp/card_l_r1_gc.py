"""Card L matched GC against 2.4.0 Final: 5,385,995 forced / 5,655,838 natural.

Adapted from nested_error_recovery_gc. Reuses its decoded branch-page and
whole-IRQ attribution. Maps resident/E000 PCs by the per-function inventory,
excluding overlay VMA aliases; Card L does not have a uniform text delta.
All collected populations and live roots remain mandatory. The fresh baseline
must reproduce the accepted reference or explain its entire delta by a decoded
IRQ path. The Seed placement cost must be fully attributed and <=0.05%.
"""
from collections import Counter
import json
import re
import subprocess
from pathlib import Path

from elf_truth import ElfTruth
from card_l_r1_common import ROOT, worlds, N
HERE=ROOT/'build/card-l-r1'
bind=N.bind
import native_cycle_stationary as N

OBJDUMP = ROOT/'tools/llvm-mos/bin/llvm-objdump'
READOBJ = ROOT/'tools/llvm-mos/bin/llvm-readobj'
CEILING = 0.0005
BRANCH8 = {0x10, 0x30, 0x50, 0x70, 0x90, 0xb0, 0xd0, 0xf0, 0x80}
BITBRANCH = {x | 0x0f for x in range(0, 256, 16)}   # BBR/BBS: opcode, zp, rel
RESIDENT = ('.text',)


def decode(elf, truth):
    """Resident instruction map {pc: (bytes, mnemonic)} for .text and the E000 window."""
    names = [s.name for s in truth.sections if 'SHF_EXECINSTR' in s.flags and s.bytes and
             (s.name in RESIDENT or s.name.startswith('.lisp65_c2_kernal_window'))]
    rows = {}
    for name in names:
        text = subprocess.check_output([str(OBJDUMP), '-d', '--section='+name, str(elf)], text=True)
        for line in text.splitlines():
            m = re.match(r'^\s+([0-9a-f]+):\s+((?:[0-9a-f]{2} )+)\s*(\S+)', line)
            if m:
                rows[int(m[1], 16)] = (bytes.fromhex(m[2].replace(' ', '')), m[3])
    return rows


def branch(pc, raw):
    op = raw[0]
    if op in BRANCH8 and len(raw) == 2:
        operand = pc+1
        target = pc+2+int.from_bytes(raw[1:2], 'little', signed=True)
        return operand, target, pc+2, op == 0x80
    if op in BITBRANCH and len(raw) == 3:
        operand = pc+2
        target = pc+3+int.from_bytes(raw[2:3], 'little', signed=True)
        return operand, target, pc+3, False
    return None


def inflow_targets(code):
    """Static control-flow targets inside the decoded population."""
    targets = Counter()
    for pc, (raw, name) in code.items():
        b = branch(pc, raw)
        if b:
            targets[b[1]] += 1
        elif raw[0] in (0x4c, 0x20) and len(raw) == 3:   # jmp abs / jsr abs
            targets[int.from_bytes(raw[1:3], 'little')] += 1
    return targets


def falls_through(raw):
    return raw[0] not in (0x60, 0x40, 0x4c, 0x6c, 0x7c, 0x80)


def irq_difference(difference, elf):
    """Require whole, independently decoded IRQ paths, not a residual (gc_layout_analyse method).

    The difference must be one complete path from c2_kernal_irq_handler to its
    RTI, all counts +1 or all -1, decoded from the E000 window of the Seed ELF
    (unchanged by this card), costed from the pinned emulator timing table.
    """
    if not difference:
        return dict(cycles=0, instructions=0)
    assert set(difference.values()) in ({1}, {-1}), 'non-unit population difference'
    sign = next(iter(difference.values()))
    t = ElfTruth.read(elf, llvm_readobj=READOBJ)
    start = t.symbol('c2_kernal_irq_handler').value
    allowed = {t.symbol('c2_kernal_irq_handler').section, t.symbol('c2_kernal_input_capture').section}
    decoded = {}
    section = None
    for line in subprocess.check_output([str(OBJDUMP), '-d', str(elf)], text=True).splitlines():
        m = re.match(r'Disassembly of section (.+):', line)
        if m:
            section = m[1]
        m = re.match(r'\s*([0-9a-f]+):\s+((?:[0-9a-f]{2} )+)\s*(\S+)', line)
        if m and section in allowed:
            decoded[int(m[1], 16)] = bytes.fromhex(m[2].replace(' ', ''))
    assert start in difference and set(difference) <= set(decoded), 'difference outside the IRQ path'
    solutions = []

    def walk(pc, left, stack, path, taken):
        if pc not in left:
            return
        b = decoded[pc]
        left = left-{pc}
        path = path+[pc]
        nxt = pc+len(b)
        if b[0] == 0x40:
            if not left and not stack:
                solutions.append((path, taken))
        elif b[0] == 0x20:
            walk(int.from_bytes(b[1:], 'little'), left, stack+[nxt], path, taken)
        elif b[0] == 0x60:
            if stack:
                walk(stack[-1], left, stack[:-1], path, taken)
        elif b[0] in BRANCH8:
            dest = nxt+int.from_bytes(b[1:], 'little', signed=True)
            extra = (0 if b[0] == 0x80 else 2)+int((pc+1)//256 != dest//256)
            walk(dest, left, stack, path, taken+extra)
            if b[0] != 0x80:
                walk(nxt, left, stack, path, taken)
        else:
            walk(nxt, left, stack, path, taken)
    walk(start, set(difference), [], [], 0)
    assert len(solutions) == 1, 'IRQ difference is not one unambiguous complete path'
    path, branch_cycles = solutions[0]
    timing = ROOT/'build/card-l-ready-instrument-r1/xemu/xemu/cpu65_mega65_timings.h'
    cpu = ROOT/'build/card-l-ready-instrument-r1/xemu/xemu/cpu65.c'
    table = [int(v) for v in re.search(r'#define TIMINGS_65GS_FAST\s*\{([^}]+)\}', timing.read_text())[1].split(',')]
    assert len(table) == 256
    source = cpu.read_text()
    assert 'BRANCH8_COST = 2;' in source and 'all_cycles += 7;' in source
    assert 'if ((temp & 0xFF00) != (CPU65.pc & 0xFF00)) CPU65.op_cycles++;' in source
    fixed = sum(table[decoded[pc][0]] for pc in path)
    return dict(cycles=sign*(fixed+branch_cycles+7), instructions=sign*len(path),
                fixed_opcode_cycles=sign*fixed, branch_cycles=sign*branch_cycles,
                hardware_entry_cycles=sign*7, path=path, source=bind(cpu), timing=bind(timing))


def lever_projection(code, raw_pops, amap):
    """Projected placement delta of each collection for member growth 128..175 bytes.

    Uses the base world's executed branch sites and their derived taken counts
    (sites before the member never move); unresolved sites give bounds."""
    targets = inflow_targets(code)
    prev = {pc+len(raw): pc for pc, (raw, _) in code.items()}
    grow0 = amap['delta']
    table = {}
    for phase in ('warmup', 'forced'):
        c = raw_pops[('baseline', phase)]
        sites = []
        for pc, n in c.items():
            if n <= 0 or pc not in code:
                continue
            b = branch(pc, code[pc][0])
            if not b:
                continue
            operand, target, fall, always = b
            if always:
                tk = n
            elif c.get(target, 0) == 0:
                tk = 0
            elif c.get(fall, 0) == 0:
                tk = n
            elif targets[fall] == 0:
                tk = n-c.get(fall, 0)
            elif targets[target] == 1 and target in prev and \
                    (not falls_through(code[prev[target]][0]) or c.get(prev[target], 0) == 0):
                tk = c.get(target, 0)
            else:
                tk = None
            sites.append((operand, target, n, tk, amap['member_end_base'] <= pc <= amap['text_end_base']))
        rows = []
        for grow in range(128, 176):
            lo = hi = 0
            for operand, target, n, tk, moves in sites:
                if not moves:
                    continue
                a = (operand >> 8) != (target >> 8)
                b = ((operand+grow) >> 8) != ((target+grow) >> 8)
                if a == b:
                    continue
                d = int(b)-int(a)
                if tk is None:
                    lo += min(0, d*n)
                    hi += max(0, d*n)
                else:
                    lo += d*tk
                    hi += d*tk
            rows.append(dict(growth=grow, pad=grow-grow0, cycles=[lo, hi]))
        table[phase] = rows
    return dict(model='same code, member grown by `growth` bytes instead of the Seed growth', rows=table)


def resident_address_map():
    inventory_path=ROOT/'build/card-l-r1/inventory-r5/codegen-function-equivalence.json'
    inventory=json.loads(inventory_path.read_text())
    def records(value):
        if isinstance(value,dict):
            if 'function' in value: yield value
            for v in value.values(): yield from records(v)
        elif isinstance(value,list):
            for v in value: yield from records(v)
    amap=[r for r in records(inventory) if r.get('before_bytes')==r.get('after_bytes') and
          (r.get('section') in RESIDENT or r.get('section','').startswith('.lisp65_c2_kernal_window'))]
    forward={};reverse={}
    for r in amap:
        for i in range(r['before_bytes']):
            a0=r['before_address']+i;b0=r['after_address']+i
            assert a0 not in forward or forward[a0]==b0
            assert b0 not in reverse or reverse[b0]==a0
            forward[a0]=b0;reverse[b0]=a0
    return inventory_path, amap, forward, reverse


def main():
    worlds()
    inputs, rows, populations, raw_pops, receipts = [], {}, {}, {}, {}
    elfs, truths, codes = {}, {}, {}
    for role in ('baseline', 'candidate'):
        out = ROOT/f'build/card-l-gc-equal-{role}-1'
        p = out/'receipt.json'
        inputs.append(bind(p))
        r = json.loads(p.read_text())
        receipts[role] = r
        assert r['natural_count'] == 1 and r['forced_count'] == 1 and not r['excluded_collections']
        rows[role] = {x['phase']: x for x in r['collections']}
        elf = N.checked_binding(r['ELF'])
        inputs.append(bind(elf))
        elfs[role] = elf
        t = ElfTruth.read(elf, llvm_readobj=READOBJ)
        truths[role] = t
        codes[role] = decode(elf, t)
        funcs = sorted([s for s in t.symbols if s.symbol_type == 'Function' and s.bytes and
                        (s.section in RESIDENT or s.section.startswith('.lisp65_c2_kernal_window'))], key=lambda s: s.value)
        for index, phase in ((0, 'warmup'), (1, 'forced')):
            def pc(ph):
                q = out/f'pc-{index}-{ph}.txt'
                inputs.append(bind(q))
                return Counter({int(a[1]): int(a[2]) for line in q.read_text().splitlines()
                                if (a := line.split())[0] == 'P'})
            counts = pc('after')
            counts.subtract(pc('before'))
            assert all(v >= 0 for v in counts.values())
            counts = Counter({k: v for k, v in counts.items() if v})
            normalized = Counter()
            for at, count in counts.items():
                matches = [s for s in funcs if s.value <= at < s.value+s.bytes]
                s = min(matches, key=lambda s: (s.bytes, s.name)) if matches else None
                normalized[(s.name, at-s.value) if s else ('absolute', at)] += count
            populations[(role, phase)] = normalized
            raw_pops[(role, phase)] = counts
    a, b = rows['baseline']['forced'], rows['candidate']['forced']
    for field in ('graph', 'root_bytes', 'symbols', 'gc_frozen'):
        assert a['entry_state'][field] == b['entry_state'][field], field
    assert a['marked'] == b['marked']
    assert rows['baseline']['warmup']['marked']['count'] == rows['candidate']['warmup']['marked']['count']
    inventory_path,amap,forward,reverse=resident_address_map()
    def f(x):return forward.get(x,x)
    reference_dir=ROOT/'build/nested-error-recovery-gc-equal-candidate-1'
    reference=json.loads((reference_dir/'receipt.json').read_text())
    assert reference['ELF']['sha256']==receipts['baseline']['ELF']['sha256']
    inputs.append(bind(reference_dir/'receipt.json'))
    reference_rows={r['phase']:r for r in reference['collections']}
    reference_comparisons={}
    for index,phase,expected in [(1,'forced',5385995),(0,'warmup',5655838)]:
        assert reference_rows[phase]['cycles']==expected
        old_counts={}
        for boundary in ('before','after'):
            path=reference_dir/f'pc-{index}-{boundary}.txt';inputs.append(bind(path))
            old_counts[boundary]=Counter({int(a[1]):int(a[2]) for line in path.read_text().splitlines() if (a:=line.split())[0]=='P'})
        reference_population=old_counts['after'];reference_population.subtract(old_counts['before'])
        diff=Counter(raw_pops[('baseline',phase)]);diff.subtract(reference_population)
        diff={k:v for k,v in diff.items() if v}
        irq=irq_difference(diff,elfs['baseline'])
        measured=rows['baseline'][phase]['cycles']-expected
        assert measured==irq['cycles'], ('baseline reference delta unexplained',phase,measured,irq)
        if phase=='forced':
            for field in ('graph','root_bytes','symbols','gc_frozen'):
                assert rows['baseline'][phase]['entry_state'][field]==reference_rows[phase]['entry_state'][field]
        reference_comparisons[phase]=dict(reference_cycles=expected,fresh_cycles=rows['baseline'][phase]['cycles'],delta=measured,irq=irq,fully_attributed=True)
    collections = {}
    for phase in ('warmup', 'forced'):
        pa, pb = populations[('baseline', phase)], populations[('candidate', phase)]
        identical = pa == pb
        ca, cb = raw_pops[('baseline', phase)], raw_pops[('candidate', phase)]
        # Raw PC pairing through the proved address map (only .text moves).
        mapped = Counter({f(k) if k < 0xc000 else k: v for k, v in ca.items()})
        raw_identical = mapped == cb
        tb = inflow_targets(codes['candidate'])
        prev_b = {pc+len(raw): pc for pc, (raw, _) in codes['candidate'].items()}
        sites, expected, lower, upper, unresolved = [], 0, 0, 0, []
        for pc, n in cb.items():
            if pc not in codes['candidate']:
                continue
            raw = codes['candidate'][pc][0]
            bb = branch(pc, raw)
            if not bb:
                continue
            base_pc = reverse.get(pc,pc)
            rawa = codes['baseline'].get(base_pc, (b'', ''))[0]
            assert rawa == raw or (raw[0] not in BRANCH8 and raw[0] not in BITBRANCH), ('branch drift', hex(pc))
            ba = branch(base_pc, rawa)
            operand, target, fall, always = bb
            cross_b = (operand & 0xff00) != (target & 0xff00)
            cross_a = (ba[0] & 0xff00) != (ba[1] & 0xff00)
            if cross_a == cross_b:
                continue
            sign = 1 if cross_b else -1
            if always:
                taken, how = n, 'unconditional'
            elif cb.get(target, 0) == 0:
                taken, how = 0, 'target not executed'
            elif cb.get(fall, 0) == 0:
                taken, how = n, 'fall-through not executed'
            elif tb[fall] == 0 and fall in codes['candidate']:
                taken, how = n-cb.get(fall, 0), 'fall-through isolated'
            elif tb[target] == 1 and target in prev_b and not falls_through(codes['candidate'][prev_b[target]][0]):
                taken, how = cb.get(target, 0), 'target isolated'
            elif tb[target] == 1 and target in prev_b and cb.get(prev_b[target], 0) == 0:
                taken, how = cb.get(target, 0), 'target isolated (predecessor not executed)'
            else:
                taken, how = None, 'unresolved'
            row = dict(pc_base=base_pc, pc_seed=pc, executions=n, target_seed=target,
                       cross_base=cross_a, cross_seed=cross_b, sign=sign, taken=taken, derivation=how)
            sites.append(row)
            if taken is None:
                unresolved.append(row)
                lower += min(0, sign*n)
                upper += max(0, sign*n)
            else:
                assert 0 <= taken <= n, row
                expected += sign*taken
                lower += sign*taken
                upper += sign*taken
        ra, rb2 = rows['baseline'][phase], rows['candidate'][phase]
        measured = rb2['cycles']-ra['cycles']
        difference = Counter(cb)
        difference.subtract(mapped)
        difference = {k: v for k, v in difference.items() if v}
        irq = irq_difference(difference, elfs['candidate'])
        placement_fraction = abs(expected)/ra['cycles']
        collections[phase] = dict(
            cycles=dict(baseline=ra['cycles'], candidate=rb2['cycles']), measured_delta=measured,
            fraction=abs(measured)/ra['cycles'], marked=ra['marked']['count'],
            normalized_population_identical=identical, raw_population_identical_under_map=raw_identical,
            instructions=sum(pb.values()), changed_branch_sites=len(sites), sites=sites,
            expected_placement_delta=expected, bounds=[lower, upper], unresolved_sites=len(unresolved),
            interrupt_delta=irq, placement_fraction=placement_fraction,
            fully_attributed=not unresolved and measured == expected+irq['cycles'],
            within_named_cost=placement_fraction <= CEILING)
        print(phase, 'measured', measured, 'placement', expected, 'irq', irq['cycles'], 'bounds', [lower, upper],
              'sites', len(sites), 'unresolved', len(unresolved), 'pop-identical', identical, raw_identical,
              'placement fraction', placement_fraction)
    for phase, c in collections.items():
        assert c['fully_attributed'], phase+': GC delta not fully attributed'
    lever = dict(note='Per-function inventory map; a uniform text delta is invalid for Card L.')
    ok = all(c['within_named_cost'] for c in collections.values())
    status = 'PASS: MATCHED GC; PLACEMENT DELTA FULLY ATTRIBUTED AND WITHIN 0.05 %' if ok else \
        'HALT: PLACEMENT DELTA FULLY ATTRIBUTED BUT ABOVE 0.05 % OF A COLLECTION (NAMED-COST RULE)'
    result = dict(status=status, binding='Card L Seed 2026-09-25', collections=collections, ceiling=CEILING,
                  alignment_lever=lever,
                  live_graph_and_marks_identical=True, address_map=amap,
                  reference_comparisons=reference_comparisons,
                  baseline_v240=dict(forced=5385995, warmup=5655838,
                                            note='same ELF as the baseline; warmup varies by IRQ phase run to run'),
                  model='Xemu _BRA: +1 cycle for a taken 8-bit branch whose target page differs from its operand page',
                  inputs=inputs+[bind(inventory_path),
                                 bind(Path(__file__))])
    p = HERE/'gc-qualification.json'
    assert not p.exists()
    p.write_text(json.dumps(result, indent=2)+'\n')
    print(status)
    if not ok:
        raise SystemExit(2)


if __name__ == '__main__':
    import argparse, subprocess, os, sys
    p=argparse.ArgumentParser();p.add_argument('--dry-run',action='store_true');p.add_argument('--analyse-only',action='store_true');a=p.parse_args()
    if not a.analyse_only:
        for role in ('baseline','candidate'):
            command=[sys.executable,'-B',str(ROOT/'tools/host-lisp/card_l_r1_gc_trace.py'),role]
            if a.dry_run:command.append('--dry-run')
            subprocess.run(command,check=True,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'))
    if a.dry_run:
        worlds()
        resident_address_map()
        reference=json.loads((ROOT/'build/nested-error-recovery-gc-equal-candidate-1/receipt.json').read_text())
        assert {r['phase']:r['cycles'] for r in reference['collections']}==dict(forced=5385995,warmup=5655838)
        for index in (0,1):
            for boundary in ('before','after'):assert (ROOT/f'build/nested-error-recovery-gc-equal-candidate-1/pc-{index}-{boundary}.txt').is_file()
        print('DRY RUN PASS: GC comparator references forced=5385995 natural=5655838; per-function placement + decoded IRQ attribution; ceiling=0.0005')
    else:main()
