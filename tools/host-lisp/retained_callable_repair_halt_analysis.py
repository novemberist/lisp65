"""Retained-callable repair: offline analysis of the executed Seed evidence and the halt.

Reads only receipts and raw dumps already written; no emulator, compiler,
linker or product execution.  Every number in the halt report is asserted here.
"""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'tools/host-lisp'))
import retained_callable_writer_analysis as A  # noqa: E402

OUT = ROOT/'build/retained-callable-repair-r1/halt-analysis.json'
LAMBDA = ROOT/'build/retained-callable-repair-gates-lambda-r1'


def bind(path):
    raw = Path(path).read_bytes()
    return dict(path=str(Path(path).resolve().relative_to(ROOT)), bytes=len(raw),
                sha256=hashlib.sha256(raw).hexdigest())


def load(path, inputs):
    p = ROOT/path
    inputs.append(bind(p))
    return json.loads(p.read_text())


def main():
    inputs = []
    seed = ROOT/'build/retained-callable-repair-product-r1/wplto/resident-island-seed.prg.elf'
    inventory = load('build/retained-callable-repair-seed-inventory-r1/inventory.json', inputs)
    assert inventory['status'].startswith('PASS') and not inventory['unclassified_section_bytes']
    assert inventory['ELFs'][1] == bind(seed)
    price = load('build/retained-callable-repair-product-r1/wplto/retained-callable-repair-seed-price.json', inputs)
    assert price['status'].startswith('PASS') and price['owner_floors_unchanged']
    capacity = [load(f'build/retained-callable-repair-capacity{s}-r1/slice-capacity-preflight.json', inputs)
                for s in ('', '-seed')]
    packed = load('build/retained-callable-repair-seed-medium-r1/packed-receipt.json', inputs)
    assert packed['closure']['failures'] == packed['coherence']['failures'] == []
    assert packed['elf']['sha256'] == bind(seed)['sha256']
    boot = load('build/retained-callable-repair-native-boot-r1/qualification.json', inputs)
    assert boot['status'].startswith('PASS') and boot['carrier_writes'] == 0 and boot['prompt_identical']

    def ledger(path):
        inputs.append(bind(ROOT/path))
        rows = [l.split() for l in (ROOT/path).read_text().splitlines() if l.startswith('E ')]
        return int(rows[-1][2]) - int(rows[0][2])
    boot_cycles = dict(anchor=ledger('build/dirty-anchor-native-boot-r2/capture-r1/boot.txt'),
                       seed=ledger('build/retained-callable-repair-native-boot-r1/capture-r1/boot.txt'))
    latency = load('build/retained-callable-repair-r1/latency-qualification.json', inputs)
    assert latency['status'].startswith('PASS')
    gc = load('build/retained-callable-repair-r1/gc-qualification.json', inputs)
    assert gc['status'].startswith('PASS') and gc['forced_delta'] == 0
    usage = {}
    for role in ('baseline', 'candidate'):
        u = load(f'build/retained-callable-repair-usage-{role}-r1/receipt.json', inputs)
        assert u['status'] == 'PASS' and len(u['rows']) == 23
        usage[role] = u['rows'][18]['expected']
    assert usage == {'baseline': '*** VM: BAD BYTECODE', 'candidate': '19'}
    # Gate 3: the halting run.
    r = load('build/retained-callable-repair-gates-lambda-r1/receipt.json', inputs)
    assert r['status'] == 'HALT: PROBE ERROR' and r['mode'] == 'lambda'
    steps = {s['label']: s for s in r['steps']}
    assert steps['lambda']['passed'] and steps['lambda']['tail'][-2] == '19'
    assert not steps['funcall']['passed']
    assert steps['funcall']['tail'][-2] == '*** VM: UNDEFINED FUNCTION #FFE'
    assert [(t['before'], t['after']) for t in r['transitions']] == [(0, 0xB5), (0xB5, 0)]
    for row in r['captures']:
        for b in list(row['regions'].values()) + [row['screen']]:
            assert bind(ROOT/b['path'])['sha256'] == b['sha256'], b['path']
    scratch, runtime = r['symbols']['lisp65_c2_phase_scratch'], r['symbols']['c2_runtime']

    def region(label, name):
        return (LAMBDA/f'{label}-{name}.bin').read_bytes()
    states = {}
    for label in ('boot', 'watch-0', 'watch-1', 'after-lambda'):
        s = A.append_state(region(label, 'bank0'), scratch)
        states[label] = dict(code_len=s['code_len'], chip_code_base=s['chip_code_base'],
                             transient=bool(s['rollback_rebuild_header'] & 0x80), staged=s['staged'],
                             committed=s['committed'], counts=A.counts(region(label, 'c2d')),
                             span=region(label, 'bank2')[0xED39:0xED56].hex())
    # Stage copy of the transient image, then its own retirement wipe.
    assert states['watch-0']['transient'] and states['watch-0']['staged'] == 0
    assert (states['watch-0']['code_len'], states['watch-0']['chip_code_base']) == (29, 0xED39)
    assert states['watch-1']['transient'] and states['watch-1']['staged'] == states['watch-1']['committed'] == 1
    assert (states['watch-1']['code_len'], states['watch-1']['chip_code_base']) == (29, 0xED39)
    assert states['after-lambda']['span'] == '00'*29
    bc, bb = region('boot', 'c2d'), region('boot', 'bank2')
    ac, ab = region('after-lambda', 'c2d'), region('after-lambda', 'bank2')
    n = A.u(bc, 16, 2)
    changed_entries = [i for i in range(n) if A.entry(bc, bb, i) != A.entry(ac, ab, i)]
    planes = {name: bc[off:off+cnt] == ac[off:off+cnt] for name, off, cnt in [
        ('header', 0, 48), ('images', 48, A.u(bc, 12, 2)*32), ('entries', A.u(bc, 30, 2), n*10),
        ('resolutions', A.u(bc, 32, 2), A.u(bc, 20, 2)*2), ('roots', A.u(bc, 34, 2), A.u(bc, 24, 2)*2)]}
    assert changed_entries == [] and all(planes.values()) and bb == ab
    c2d_changes = {hex(i): [bc[i], ac[i]] for i in range(65536) if bc[i] != ac[i]}
    assert ac[0xCBB8:0xCBBA] == bytes.fromhex('fcdf')     # MK_BCODE(4094) = $DFFC
    value = dict(
        status='HALT: GATE 3 RED, NEW DEFECT CLASS (RETAINED TRANSIENT CALLABLE OUTLIVES ITS IMAGE)',
        binding='d3d5044b', authority='e0be22c1',
        seed=dict(ELF=bind(seed), medium=packed['medium']),
        budget_consumed=dict(seed=1, final=0, product_link=0, device=0),
        inventory=dict(status=inventory['status'], counts=inventory['changed_section_byte_counts'],
                       physical_different_bytes=inventory['physical_different_bytes'],
                       members=inventory['members'], witnesses=inventory['witnesses']),
        price=dict(members=price['members'], candidate={k: price['candidate'][k] for k in (
            'ordinary_text_free', 'rodata_free', 'E000_free', 'capture_free', 'high_bss_free', 'CRT_zero_bytes',
            'frame_start', 'frame_bytes', 'metadata_start', 'metadata_bytes')}),
        session=dict(anchor=capacity[0]['families']['session'], seed=capacity[1]['families']['session'],
                     unique_catalog_slots_free=[c['unique_catalog_slots_free'] for c in capacity]),
        boot=dict(qualification=boot['status'], stack_low=boot['stack_low'], e0_e11_cycles=boot_cycles,
                  delta_cycles=boot_cycles['seed'] - boot_cycles['anchor']),
        lanes={k: dict(ratio=v['ratio'], collections=v['collections'],
                       anchor_cycles_per_key=v['worlds']['anchor']['cycles_per_key'],
                       seed_cycles_per_key=v['worlds']['candidate']['cycles_per_key'])
               for k, v in latency['lanes'].items()},
        gc=dict(forced=gc['cycles'], forced_delta=gc['forced_delta'], warmup=gc['warmup'],
                marked_cells=gc['marked_cells']),
        usage_row_18=usage,
        gate3=dict(lambda_result='19', funcall_result=steps['funcall']['tail'][-2],
                   transitions=r['transitions'], append_states=states,
                   persistent_entries=n, persistent_entries_changed=changed_entries,
                   planes_identical=planes, bank2_identical_boot_to_after=True,
                   c2d_bytes_changed=c2d_changes,
                   savedlambda_value_cell=dict(c2d_offset='0xcbb8', bytes='fcdf', handle=4094)),
        not_executed=['gate 1 (N = 1, 2, 16, 54 sweep)', 'gate 2 comparator on the sweep',
                      'gate 4 (dotimes/eval N = 1 watch)', 'sealed full check-source', 'Final', 'device rows'],
        inputs=inputs + [bind(Path(__file__))])
    assert not OUT.exists()
    OUT.write_text(json.dumps(value, indent=2)+'\n')
    print(value['status'])


if __name__ == '__main__':
    main()
