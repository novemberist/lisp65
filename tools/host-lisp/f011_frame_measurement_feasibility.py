#!/usr/bin/env python3
"""Host-only observation-contract check. No compile/link/device operations."""
import hashlib
import json
from pathlib import Path
import subprocess

from elf_truth import ElfTruth
from evidence_era import stable_recorded_on

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'build/v2.1/f011-frame-measurement-feasibility'
OLD = ROOT / 'build/c2.3/v2.0.0-release-card-r3/wplto/lisp65-c2-substitution-linked.prg.elf'
NEW = ROOT / 'build/v2.1/f011-status-product-r1/wplto/lisp65-c2-substitution-linked.prg.elf'

def bind(path):
    data = path.read_bytes()
    return dict(path=str(path.relative_to(ROOT)), bytes=len(data), sha256=hashlib.sha256(data).hexdigest())

def body(elf, name):
    sym = elf.symbol(name)
    sec = elf.section(sym.section)
    start = sym.value - sec.address
    return sym, elf.section_bytes(sec.name)[start:start+sym.bytes]

def historical_gap(data):
    # Actual straight-line instruction bytes, not objdump labels or C source.
    start = bytes.fromhex('a2 20 8e 81 d0')
    end = bytes.fromhex('a2 40 8e 81 d0')
    assert data.count(start) == data.count(end) == 1
    a = data.index(start) + len(start)
    b = data.index(end)
    # INY; LDX rc4; DEX; STX D084; STY D085; LDX rc3; STX D086.
    assert data[a:b] == bytes.fromhex('c8 a6 06 ca 8e 84 d0 8c 85 d0 a6 05 8e 86 d0')
    return a, b

def main():
    authority = subprocess.check_output(['git', 'show', '47804fe2:docs/planning/v2.0.0-pre-plan.md'], cwd=ROOT)
    assert b'Both phases measured, and the proceed-time status too' in authority
    old = ElfTruth.read(OLD, llvm_readobj=Path('/usr/bin/llvm-readobj'), include_section_data=True)
    new = ElfTruth.read(NEW, llvm_readobj=Path('/usr/bin/llvm-readobj'), include_section_data=True)
    assert bind(OLD)['sha256'] == '96ba670981172fab72383d40cf6da24d3318749d03a916014b716d4b881ecd05'
    assert bind(NEW)['sha256'] == '29d3ff462afc9c59ad9769fac8098ed0f02900d3c7cf5a37c89855b0444d9cc6'
    s, raw = body(old, 'f011_read_at')
    a, b = historical_gap(raw)
    mutant = raw[:a] + bytes.fromhex('ad 82 d0') + raw[a:]
    try:
        historical_gap(mutant)
    except AssertionError:
        rejected = True
    else:
        raise AssertionError('added pre-read status sample escaped historical proof')
    state = new.section('.noinit.lisp65_f011_status')
    raw_owner = new.section('.lisp65_c2_input_raw_owner')
    assert state.bytes == 3
    # Logical counterexample only, not a simulation or claim about real F011.
    # Both devices behave identically when READ is issued after readiness.
    # They differ only when READ arrives while BUSY, which the proposal avoids.
    def model(queues_early_read, issue_at):
        ready_at = 30
        if issue_at < ready_at and not queues_early_read:
            return None
        return max(issue_at, ready_at) + 5
    waited = [model(q, 30) for q in (False, True)]
    early = [model(q, 0) for q in (False, True)]
    assert waited[0] == waited[1] and early[0] != early[1]
    receipt = dict(
        format='f011-frame-instrument-observation-feasibility-v1',
        recorded_on=stable_recorded_on(OUT/'receipt.json'), authority='47804fe2',
        authority_plan_sha256=hashlib.sha256(authority).hexdigest(),
        predecessor=bind(OLD), current=bind(NEW),
        historical_function=dict(address=s.value, bytes=s.bytes, body_sha256=hashlib.sha256(raw).hexdigest()),
        spinup_to_read_gap=dict(start=s.value+a, end_exclusive=s.value+b,
                               bytes=raw[a:b].hex(), polling_reads=0, loops=0, calls=0),
        sharp_control=dict(insert_status_read_rejected=rejected),
        record_projection=dict(current_start=state.address, current_bytes=3,
                               requested_bytes=7, delta=4,
                               projected_raw_input_gap=raw_owner.address-(state.address+7), floor=5,
                               final_link_price=False),
        observability_counterexample=dict(model_only=True, waited_completion=waited,
                                          early_completion=early,
                                          conclusion='wait-before-read cannot identify early-command acceptance'),
        storage=dict(tag=1, consumed_d082=1, sampled_d083=1, spin_frames=2, read_frames=2,
                     total=7, extra_distinct_proceed_d082=1,
                     total_if_all_retained=8,
                     limit='raw distinct samples; no approved lossy compression or field repurposing'),
        status='STOP: measurement contract needs disposition before code pricing',
        WPLTO=0, links=0, compiler_invocations=0, media=0, device_contacts=0,
        limits=['No measured device timing or physical command-queue model.',
                'No instrument implementation, final placement, abort survival or clock-liveness claim.'])
    OUT.mkdir(parents=True, exist_ok=True)
    for path, data in [(OUT/'historical-f011-body.bin', raw),
                       (OUT/'receipt.json', (json.dumps(receipt, indent=2)+'\n').encode())]:
        if path.exists():
            assert path.read_bytes() == data, 'existing evidence differs'
        else:
            with path.open('xb') as f:
                f.write(data)
    print(json.dumps(receipt, indent=2))

if __name__ == '__main__':
    main()
