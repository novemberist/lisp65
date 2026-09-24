"""Attribute the isolated layout experiment using executed instruction flow."""
from collections import Counter, defaultdict
from fractions import Fraction
import hashlib
import json
import re
import subprocess
import sys

from gc_layout_control import ROOT, OUT, ELF, TOOLS, bind, read_truth, write_once


def counts(folder, phase):
    result = Counter()
    for line in (folder/f'pc-1-{phase}.txt').read_text().splitlines():
        f = line.split()
        if f and f[0] == 'P':
            result[int(f[1])] = int(f[2])
    return result


def flow(instructions, population, base):
    """Solve conditional taken counts from exact incoming/outgoing PC counts.

    Every reconstructed count must satisfy all CFG conservation equations and
    its measured execution bound. No guessed branch probability is used.
    """
    conditional = {off for off,b,name in instructions if b[0] in
                   (0x10,0x30,0x50,0x70,0x90,0xb0,0xd0,0xf0)}
    known = Counter({1: 1})  # CLC executed before the measurement interval.
    coefficients = defaultdict(Counter)
    taken = {}
    for off, b, name in instructions:
        n = population[base+off]
        nxt = off+len(b)
        if off in conditional or b[0] == 0x80:
            dest = nxt+int.from_bytes(b[1:], 'little', signed=True)
            if off in conditional:
                known[nxt] += n
                coefficients[nxt][off] -= 1
                coefficients[dest][off] += 1
            else:
                known[dest] += n
                taken[off] = n
        elif b[0] == 0x4c:
            dest = int.from_bytes(b[1:], 'little')-base
            assert 0 <= dest < 1491
            known[dest] += n
        elif b[0] == 0x60:
            pass
        else:
            assert b[0] not in (0x6c,0x7c,0x40), 'unmodelled CFG edge'
            known[nxt] += n
    equations = []
    for off,b,name in instructions:
        eq = {k:Fraction(v) for k,v in coefficients[off].items() if v}
        rhs = Fraction(population[base+off]-known[off])
        equations.append((eq,rhs))
    for off in conditional:
        if not population[base+off]:
            equations.append(({off:Fraction(1)},Fraction(0)))
    pivots = {}
    for equation,rhs in equations:
        row = dict(equation)
        while row:
            key = min(row)
            if key not in pivots:
                factor = row[key]
                pivots[key] = ({k:v/factor for k,v in row.items()}, rhs/factor)
                break
            prior,value = pivots[key]
            factor = row[key]
            rhs -= factor*value
            for k,v in prior.items():
                row[k] = row.get(k,0)-factor*v
                if row[k] == 0:
                    del row[k]
        else:
            assert rhs == 0, 'instruction flow mismatch'
    assert set(pivots) == conditional, 'underdetermined branch population'
    for key in sorted(pivots,reverse=True):
        row,value = pivots[key]
        value -= sum(v*taken[k] for k,v in row.items() if k != key)
        assert value.denominator == 1 and 0 <= value <= population[base+key]
        taken[key] = int(value)
    for row,rhs in equations:
        assert sum(v*taken[k] for k,v in row.items()) == rhs
    return taken


def main():
    admission = json.loads((OUT/'preflight.json').read_text())
    old,new = admission['original'],admission['relocated']
    inputs = [bind(OUT/'preflight.json'),bind(OUT/'linked.json')]
    runs = {}
    for role in ('baseline','relocated'):
        folder = ROOT/f'build/gc-layout-measure-{role}-r1'
        for filename in ('receipt.json','relocation-entry.json','diagnostic.json',
                         'pc-1-before.txt','pc-1-after.txt'):
            inputs.append(bind(folder/filename))
        receipt = json.loads((folder/'receipt.json').read_text())
        forced = [r for r in receipt['collections'] if r['phase']=='forced']
        assert len(forced)==1 and receipt['natural_count']==1 and not receipt['excluded_collections']
        population = counts(folder,'after'); population.subtract(counts(folder,'before'))
        assert all(v>=0 for v in population.values())
        runs[role] = dict(row=forced[0],population=population,receipt=receipt)
    a,b = runs['baseline']['row'],runs['relocated']['row']
    for key in ('graph','root_bytes','symbols','gc_frozen'):
        assert a['entry_state'][key] == b['entry_state'][key]
    assert a['marked'] == b['marked'] and a['return_witness'] == b['return_witness']
    entries=[json.loads((ROOT/f'build/gc-layout-measure-{r}-r1/relocation-entry.json').read_text())
             for r in ('baseline','relocated')]
    # Absolute boot clock/IRQ phase is not the logical GC-state contract;
    # interrupt differences are decoded and charged independently below.
    assert ({k:v for k,v in entries[0].items() if k!='cycles'} ==
            {k:v for k,v in entries[1].items() if k!='cycles'}), 'pre-relocation state differs'
    assert runs['baseline']['receipt']['medium'] == runs['relocated']['receipt']['medium']
    candidate = Counter()
    for pc,n in runs['relocated']['population'].items():
        candidate[pc-new+old if new <= pc < new+1491 else pc] += n
    difference = candidate.copy(); difference.subtract(runs['baseline']['population'])
    difference = {pc:n for pc,n in difference.items() if n}
    irq = irq_difference(difference)
    text = subprocess.check_output([str(TOOLS/'llvm-objdump'),'-d',
           '--disassemble-symbols=gc_collect',str(ELF)],text=True)
    instructions = []
    for line in text.splitlines():
        m = re.match(r'\s*([0-9a-f]+):\s+((?:[0-9a-f]{2} )+)\s*(\S+)',line)
        if m:
            instructions.append((int(m[1],16)-old,bytes.fromhex(m[2]),m[3]))
    taken = flow(instructions,runs['baseline']['population'],old)
    rows = []
    # Pinned _BRA compares the operand PC (opcode+1), not the following PC.
    cpu = ROOT/'build/boot-only-carrier-ready-instrument-r1/xemu/xemu/cpu65.c'
    source = cpu.read_text()
    assert 'if ((temp & 0xFF00) != (CPU65.pc & 0xFF00)) CPU65.op_cycles++;' in source
    inputs.append(bind(cpu))
    for off,raw,name in instructions:
        if off not in taken:
            continue
        target=off+2+int.from_bytes(raw[1:],'little',signed=True)
        before=(old+off+1)//256 != (old+target)//256
        after=(new+off+1)//256 != (new+target)//256
        if before != after:
            rows.append(dict(offset=off,baseline_pc=old+off,relocated_pc=new+off,
                             taken=taken[off],old_crossing=before,new_crossing=after,
                             cycles=taken[off]*(int(after)-int(before))))
    predicted=sum(r['cycles'] for r in rows)
    delta=b['cycles']-a['cycles']
    assert delta == predicted+irq['cycles'], f'unattributed delta: measured {delta}, branch pages {predicted}, IRQ {irq}'
    result=dict(status='PASS: ISOLATED LAYOUT DELTA FULLY ATTRIBUTED',inputs=inputs,
        baseline_cycles=a['cycles'],relocated_cycles=b['cycles'],delta_cycles=delta,
        delta_seconds=delta/40500000,marked_cells=a['marked']['count'],
        normalized_instruction_count=sum(candidate.values()),
        collector_and_non_irq_population_identical=True,branch_pages=rows,
        branch_page_cycles=predicted,interrupt_delta=irq,
        diagnostic_links=1,product_changes=0,device_contacts=0)
    for row in inputs+[irq['source'],irq['timing']]:
        assert bind(row['path'])['sha256']==row['sha256']
    write_once(OUT/'analysis.json',result)
    print(json.dumps(result,indent=2))


def irq_difference(difference):
    """Require one complete, independently decoded IRQ path, not a residual.

    Its path must consume exactly the differing PCs, including the capture
    JSR/RTS and final RTI. No address/fixed 110-cycle exception is admitted.
    """
    if not difference:
        return dict(cycles=0,instructions=0)
    assert set(difference.values()) in ({1},{-1})
    sign=next(iter(difference.values()))
    t=read_truth(ELF)
    start=t.symbol('c2_kernal_irq_handler').value
    allowed={t.symbol('c2_kernal_irq_handler').section,
             t.symbol('c2_kernal_input_capture').section}
    decoded={}
    raw=subprocess.check_output([str(TOOLS/'llvm-objdump'),'-d',str(ELF)],text=True)
    section=None
    for line in raw.splitlines():
        m=re.match(r'Disassembly of section (.+):',line)
        if m: section=m[1]
        m=re.match(r'\s*([0-9a-f]+):\s+((?:[0-9a-f]{2} )+)\s*(\S+)',line)
        if m and section in allowed:
            decoded[int(m[1],16)]=bytes.fromhex(m[2])
    assert start in difference and set(difference)<=set(decoded)
    solutions=[]
    def walk(pc,left,stack,path,taken):
        if pc not in left:return
        b=decoded[pc];left=left-{pc};path=path+[pc];nxt=pc+len(b)
        if b[0]==0x40:
            if not left and not stack:solutions.append((path,taken))
        elif b[0]==0x20:
            walk(int.from_bytes(b[1:],'little'),left,stack+[nxt],path,taken)
        elif b[0]==0x60:
            if stack:walk(stack[-1],left,stack[:-1],path,taken)
        elif b[0] in (0x10,0x30,0x50,0x70,0x90,0xb0,0xd0,0xf0,0x80):
            dest=nxt+int.from_bytes(b[1:],'little',signed=True)
            extra=(0 if b[0]==0x80 else 2)+int((pc+1)//256 != dest//256)
            walk(dest,left,stack,path,taken+extra)
            if b[0]!=0x80:walk(nxt,left,stack,path,taken)
        else:walk(nxt,left,stack,path,taken)
    walk(start,set(difference),[],[],0)
    assert len(solutions)==1, 'IRQ difference is not one unambiguous complete path'
    path,branch_cycles=solutions[0]
    timing=ROOT/'build/boot-only-carrier-ready-instrument-r1/xemu/xemu/cpu65_mega65_timings.h'
    cpu=ROOT/'build/boot-only-carrier-ready-instrument-r1/xemu/xemu/cpu65.c'
    table=[int(v) for v in re.search(r'#define TIMINGS_65GS_FAST\s*\{([^}]+)\}',timing.read_text())[1].split(',')]
    assert len(table)==256
    source=cpu.read_text()
    assert 'BRANCH8_COST = 2;' in source and 'all_cycles += 7;' in source
    fixed=sum(table[decoded[pc][0]] for pc in path)
    return dict(cycles=sign*(fixed+branch_cycles+7),instructions=sign*len(path),
                fixed_opcode_cycles=sign*fixed,branch_cycles=sign*branch_cycles,
                hardware_entry_cycles=sign*7,path=path,
                source=bind(cpu),timing=bind(timing))


def selftest():
    import contextlib
    import io
    from unittest.mock import patch
    from pathlib import Path
    saved=(OUT/'analysis.json').read_bytes()
    with contextlib.redirect_stdout(io.StringIO()):main()
    path=ROOT/'build/gc-layout-measure-relocated-r1/receipt.json'
    original=Path.read_text
    rejected=0
    def case(change):
        nonlocal rejected
        def read(p,*args,**kwargs):
            raw=original(p,*args,**kwargs)
            if p==path:
                d=json.loads(raw);change(d);raw=json.dumps(d)
            return raw
        with patch.object(Path,'read_text',read),contextlib.redirect_stdout(io.StringIO()):
            try:main()
            except AssertionError:rejected+=1
            else:raise AssertionError('mutation admitted')
    forced=lambda d:next(r for r in d['collections'] if r['phase']=='forced')
    case(lambda d:forced(d).__setitem__('cycles',forced(d)['cycles']+1))
    case(lambda d:forced(d)['marked'].__setitem__('count',502))
    case(lambda d:forced(d)['entry_state'].__setitem__('symbols',0))
    case(lambda d:forced(d)['return_witness'].__setitem__('return_pc',0))
    case(lambda d:d['medium'].__setitem__('sha256','0'*64))
    case(lambda d:d.__setitem__('natural_count',2))
    analysis=json.loads(saved)
    for diff in ({0x2023:-1},{p:-1 for p in analysis['interrupt_delta']['path'][1:]}):
        try:irq_difference(diff)
        except AssertionError:rejected+=1
        else:raise AssertionError('non-IRQ or incomplete IRQ admitted')
    assert rejected==8 and (OUT/'analysis.json').read_bytes()==saved
    print('GC layout analysis: PASS replay, eight mutations rejected, zero receipt changes')


if __name__=='__main__':
    assert sys.argv[1:] in ([],['--selftest'])
    selftest() if sys.argv[1:] else main()
