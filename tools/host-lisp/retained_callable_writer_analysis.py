"""ca9af627: offline attribution of the retained-callable published-code wipe.

Reads only captured emulator memory and the bound ELFs.  No emulator run, no
build, no link.  Every number this writes is derived from a receipt dump.
"""
import hashlib, json
from pathlib import Path
from elf_truth import ElfTruth

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'build/retained-callable-writer-analysis-r1'
ANCHOR_ELF = ROOT / 'build/dirty-anchor-final-r3/wplto/lisp65-c2-substitution-linked.prg.elf'
V230_ELF = ROOT / 'build/retained-callable-writer-r1/v230/lisp65-2.3.0/product/lisp65-c2-substitution-linked.prg.elf'
READOBJ = ROOT / 'tools/llvm-mos/bin/llvm-readobj'
PHASE_SCRATCH = 0xC0C6          # lisp65_c2_phase_scratch == the single c2_append_state
RUNTIME = 0xC084                # c2_runtime
DECODE_ACTIVE = 0xC082
OVERLAY_BASE = 0xC356

# c2_append_state layout, derived from the consumed generated product source
# (c2_product_runtime.c, c2_stream_context is 46 bytes).
FIELDS = [('before', 0x00, 2), ('main_ordinal', 0x02, 2), ('length', 0x32, 2),
          ('code_off', 0x34, 2), ('code_len', 0x36, 2), ('meta_off', 0x38, 2),
          ('meta_len', 0x3A, 2), ('entries', 0x3C, 2), ('literals', 0x3E, 2),
          ('roots', 0x40, 2), ('old_images', 0x42, 2), ('old_entries', 0x44, 2),
          ('old_res', 0x46, 2), ('old_roots', 0x48, 2), ('new_images', 0x4A, 2),
          ('new_entries', 0x4C, 2), ('new_res', 0x4E, 2), ('new_roots', 0x50, 2),
          ('attic', 0x52, 4), ('staged', 0xEE, 1), ('committed', 0xEF, 1),
          ('rollback_rebuild_header', 0xF0, 1),
          ('chip_code_base', 0xB6 + 28, 2)]   # C2AW_CHIP_CODE_BASE == record + 28
CONTEXT = ['c2d_bytes', 'generation', 'image_count', 'entry_count', 'resolution_count',
           'images_offset', 'entries_offset', 'resolutions_offset', 'roots_offset',
           'image_cursor', 'entry_cursor', 'resolution_cursor', 'pair_depth_max',
           'image_first', 'entry_first', 'resolution_first', 'root_first']


def bind(path):
    path = Path(path).resolve()
    return dict(path=str(path.relative_to(ROOT)), bytes=path.stat().st_size,
                sha256=hashlib.sha256(path.read_bytes()).hexdigest())


def u(data, at, size):
    return int.from_bytes(data[at:at + size], 'little')


def context(data, base):
    row = {name: u(data, base + 8 + 2 * i, 2) for i, name in enumerate(CONTEXT)}
    row.update(phase=data[base + 42], finished=data[base + 43], error=data[base + 44])
    return row


def append_state(bank0, base=PHASE_SCRATCH):
    row = {name: u(bank0, base + off, size) for name, off, size in FIELDS}
    row['append'] = context(bank0, base + 4)
    return row


def entry(c2d, bank2, ordinal):
    at = u(c2d, 30, 2) + ordinal * 10
    row = c2d[at:at + 10]
    offset, length = u(row, 2, 2), u(row, 4, 2)
    return dict(ordinal=ordinal, raw=row.hex(), image=row[0], literals=row[1],
                bank2_offset=offset, length=length, generation=u(row, 8, 2),
                code=bank2[offset:offset + length].hex())


def counts(c2d):
    return dict(images=u(c2d, 12, 2), entries=u(c2d, 16, 2),
                resolutions=u(c2d, 20, 2), roots=u(c2d, 24, 2))


class Overlays:
    def __init__(self, elf):
        self.truth = ElfTruth.read(elf, llvm_readobj=READOBJ, include_section_data=True)
        self.sections = [s for s in self.truth.sections
                         if s.address == OVERLAY_BASE and s.bytes and s.section_type == 'SHT_PROGBITS']

    def resident(self, bank0):
        hits = [s for s in self.sections
                if bank0[OVERLAY_BASE:OVERLAY_BASE + s.bytes] == self.truth._section_data[s.index]]
        return hits[0] if len(hits) == 1 else None

    def owner(self, section, pc):
        best = None
        for sym in self.truth.symbols:
            if sym.section_index == section.index and sym.symbol_type == 'Function' \
                    and sym.bytes and sym.value <= pc < sym.value + sym.bytes:
                best = sym.name
        return best


def registers(text):
    rows = [line.split() for line in text.splitlines() if line.strip()]
    for row in rows:
        if len(row) >= 8 and len(row[0]) == 4:
            try:
                return dict(pc=int(row[0], 16), a=int(row[1], 16), x=int(row[2], 16),
                            y=int(row[3], 16), last_op=row[8] if len(row) > 8 else None)
            except ValueError:
                continue
    return {}


def main():
    OUT.mkdir(exist_ok=True, parents=True)
    overlays = Overlays(ANCHOR_ELF)
    writer = ROOT / 'build/retained-callable-writer-r1'
    receipt = json.loads((writer / 'receipt.json').read_text())
    labelled = {row['label']: row for row in receipt['captures']}
    # The watch run was driven by the previous worker's script; re-verify its
    # driver and every raw dump against the SHAs its own receipt bound.
    assert bind(receipt['driver']['path'])['sha256'] == receipt['driver']['sha256']
    for row in receipt['captures']:
        for binding in list(row['regions'].values()) + [row['screen']]:
            assert bind(binding['path'])['sha256'] == binding['sha256'], binding['path']
    events = []
    for label in ['write-0', 'write-1']:
        bank0 = (writer / f'{label}-bank0.bin').read_bytes()
        bank2 = (writer / f'{label}-bank2.bin').read_bytes()
        c2d = (writer / f'{label}-c2d.bin').read_bytes()
        section = overlays.resident(bank0)
        reg = registers(labelled[label]['registers'])
        state = append_state(bank0)
        events.append(dict(
            label=label, pc=hex(reg.get('pc', 0)), last_op=reg.get('last_op'),
            resident_overlay=section.name if section else None,
            owning_function=overlays.owner(section, reg['pc']) if section else None,
            watched_byte=hex(bank2[0xCC23]), watched_span=bank2[0xCC23:0xCC2D].hex(),
            c2d_counts=counts(c2d), append_state=state,
            transient=bool(state['rollback_rebuild_header'] & 0x80),
            c2_runtime=context(bank0, RUNTIME), decode_active=hex(u(bank0, DECODE_ACTIVE, 2)),
            zero_page=bank0[0:0x20].hex()))
    # The destructive event: a transient rollback that still carries the previous
    # persistent transaction's chip code base and code length.
    first, second = events
    assert not first['transient'] and second['transient']
    assert first['append_state']['chip_code_base'] == second['append_state']['chip_code_base'] == 0xCC23
    assert first['append_state']['code_len'] == second['append_state']['code_len'] == 10
    assert second['owning_function'] == 'c2_append_rollback_zero_chip_code'
    assert first['owning_function'] == 'c2_append_stage_copy_phase'
    assert second['watched_span'] == '00' * 10

    # Affected population of the executed 54 iteration run (attribution receipts r4).
    r4 = ROOT / 'build/retained-callable-attribution-r4'
    before_c2d = (r4 / 'package-c2d.bin').read_bytes()
    before_b2 = (r4 / 'package-bank2.bin').read_bytes()
    after_c2d = (r4 / 'fill-c2d.bin').read_bytes()
    after_b2 = (r4 / 'fill-bank2.bin').read_bytes()
    base_entries = u(before_c2d, 16, 2)
    changed_existing = [i for i in range(base_entries)
                        if entry(before_c2d, before_b2, i) != entry(after_c2d, after_b2, i)]
    zeroed_new, valid_new = [], []
    for i in range(base_entries, u(after_c2d, 16, 2)):
        row = entry(after_c2d, after_b2, i)
        (zeroed_new if set(bytes.fromhex(row['code'])) == {0} else valid_new).append(i)
    planes = {}
    for name, offset, count in [('images', 48, u(before_c2d, 12, 2) * 32),
                                ('entries', u(before_c2d, 30, 2), base_entries * 10),
                                ('resolutions', u(before_c2d, 32, 2), u(before_c2d, 20, 2) * 2),
                                ('roots', u(before_c2d, 34, 2), u(before_c2d, 24, 2) * 2)]:
        planes[name] = before_c2d[offset:offset + count] == after_c2d[offset:offset + count]
    other = [i for i in range(65536) if before_c2d[i] != after_c2d[i]
             and not any(o <= i < o + c for _, o, c in
                         [('h', 0, 48), ('i', 48, u(after_c2d, 12, 2) * 32),
                          ('e', u(after_c2d, 30, 2), u(after_c2d, 16, 2) * 10),
                          ('r', u(after_c2d, 32, 2), u(after_c2d, 20, 2) * 2),
                          ('t', u(after_c2d, 34, 2), u(after_c2d, 24, 2) * 2)])]
    population = dict(
        run='build/retained-callable-attribution-r4 (54 iterations)',
        entries_before=base_entries, entries_after=u(after_c2d, 16, 2),
        pre_existing_entries_changed=changed_existing,
        new_entries_zeroed=zeroed_new, new_entries_valid=len(valid_new),
        pre_existing_planes_identical=planes,
        c2d_bytes_outside_planes_changed=[hex(i) for i in other],
        function_cell_capfill=dict(physical=hex(0x50000 + 0xD640 + 693 * 2),
                                   before=before_c2d[0xD640 + 693 * 2:0xD640 + 693 * 2 + 2].hex(),
                                   after=after_c2d[0xD640 + 693 * 2:0xD640 + 693 * 2 + 2].hex()))
    assert changed_existing == [] and zeroed_new == [878] and all(planes.values())

    # Minimal reproduction sweep (r2), if executed.
    sweep = {}
    sweep_dir = ROOT / 'build/retained-callable-writer-r2'
    if (sweep_dir / 'receipt.json').is_file():
        data = json.loads((sweep_dir / 'receipt.json').read_text())
        rows = []
        previous = 'plain'
        for step in data['steps']:
            if step['label'].startswith('loop-'):
                count = int(step['label'].split('-')[1])
                c2d = (sweep_dir / f'loop-{count}-c2d.bin').read_bytes()
                bank2 = (sweep_dir / f'loop-{count}-bank2.bin').read_bytes()
                last = entry(c2d, bank2, u(c2d, 16, 2) - 1)
                call = [s for s in data['steps'] if s['label'] == f'call-{count}']
                before_c2d = (sweep_dir / f'{previous}-c2d.bin').read_bytes()
                before_b2 = (sweep_dir / f'{previous}-bank2.bin').read_bytes()
                base = u(before_c2d, 16, 2)
                delta = dict(
                    from_capture=previous,
                    pre_existing_entries_changed=[i for i in range(base)
                                                  if entry(before_c2d, before_b2, i)
                                                  != entry(c2d, bank2, i)],
                    new_entries_zeroed=[i for i in range(base, u(c2d, 16, 2))
                                        if set(bytes.fromhex(entry(c2d, bank2, i)['code'])) == {0}],
                    new_entries=u(c2d, 16, 2) - base,
                    pre_existing_planes_identical={
                        name: before_c2d[offset:offset + size] == c2d[offset:offset + size]
                        for name, offset, size in
                        [('images', 48, u(before_c2d, 12, 2) * 32),
                         ('entries', u(before_c2d, 30, 2), base * 10),
                         ('resolutions', u(before_c2d, 32, 2), u(before_c2d, 20, 2) * 2),
                         ('roots', u(before_c2d, 34, 2), u(before_c2d, 24, 2) * 2)]})
                rows.append(dict(n=count, loop_result=step['tail'][-2],
                                 counts=counts(c2d), last_entry=last,
                                 last_entry_zero=set(bytes.fromhex(last['code'])) == {0},
                                 call_result=call[0]['tail'][-2] if call else None,
                                 delta=delta))
                previous = f'call-{count}'
        controls = [dict(label=s['label'], form=s['form'], result=s['tail'][-2])
                    for s in data['steps'] if s['label'].startswith('plain-')]
        sweep = dict(receipt=bind(sweep_dir / 'receipt.json'), status=data['status'],
                     rows=rows, controls=controls)

    # 2.3.0 reproduction (r3), if executed.
    release = {}
    release_rows = []
    for release_dir in [ROOT / 'build/retained-callable-writer-r3', ROOT / 'build/retained-callable-writer-r6']:
        if not (release_dir / 'receipt.json').is_file():
            continue
        data = json.loads((release_dir / 'receipt.json').read_text())
        rows = []
        for step in data['steps']:
            if step['label'].startswith('loop-'):
                count = int(step['label'].split('-')[1])
                c2d = (release_dir / f'loop-{count}-c2d.bin').read_bytes()
                bank2 = (release_dir / f'loop-{count}-bank2.bin').read_bytes()
                last = entry(c2d, bank2, u(c2d, 16, 2) - 1)
                call = [s for s in data['steps'] if s['label'] == f'call-{count}']
                rows.append(dict(n=count, loop_result=step['tail'][-2], counts=counts(c2d),
                                 last_entry=last,
                                 last_entry_zero=set(bytes.fromhex(last['code'])) == {0},
                                 call_result=call[0]['tail'][-2] if call else None))
        release_rows.append(dict(receipt=bind(release_dir / 'receipt.json'), status=data['status'],
                                 lambda_class=[dict(label=s['label'], form=s['form'], tail=s['tail'])
                                               for s in data['steps'] if s['label'].startswith('lambda')],
                                 capfill_class=rows, elf=data.get('elf', data.get('inputs', [None])[0]),
                                 medium=data.get('medium', (data.get('inputs') or [None, None])[1])))
    release = dict(runs=release_rows,
                   capfill_class=[row for run in release_rows for row in run['capfill_class']])

    result = dict(
        status='ATTRIBUTED: TRANSIENT ROLLBACK WIPE ZEROES THE LAST PUBLISHED PERSISTENT OBJECT',
        authority='ca9af627', accepted_world='1e210f3f',
        writer=dict(
            owning_function='c2_append_rollback_zero_chip_code',
            resident_overlay='.lisp65_rt_c2append_rollback_wipe_chip',
            phase_entry='c2_append_rollback_wipe_chip_phase',
            store='enhanced DMA fill issued at $C4DE (jsr c2_facade_c2_dma); stopped PC $C4E1',
            destination='bank 2 $CC23, 10 bytes (zero page $05/$06/$07/$08 = 23 CC 02 0A)',
            transaction='transient rollback (rollback_rebuild_header = $80), staged=1, committed=1',
            stale_fields=['code_len', 'C2AW_CHIP_CODE_BASE (record+28)'],
            source_attribution='c2_append_rollback_prepare_phase populates the transient '
                               'rollback state from the retiring image row but never sets '
                               'w->code_len or record+28, so the wipe uses the previous '
                               'persistent publish values',
            iteration_index='last iteration of the loop; the wipe runs once per top level '
                            'form that retires a transient image'),
        events=events, population=population, sweep=sweep, release_2_3_0=release,
        inputs=[bind(ANCHOR_ELF), bind(V230_ELF),
                bind(ROOT / 'build/dirty-anchor-seed-medium-r1/packed/hardware-sp-seed.d81'),
                bind(ROOT / 'build/retained-callable-writer-r1/v230/lisp65-2.3.0/media/lisp65-product.d81'),
                bind(ROOT / 'build/input-cost-attribution-r6/xemu/build/bin/xmega65.native'),
                bind(ROOT / 'build/dirty-anchor-product-r1/wplto/generated-product-sources/c2_product_runtime.c'),
                bind(ROOT / 'build/dirty-anchor-product-r1/wplto/generated-product-sources/c2-stream-v2-decoder.c'),
                bind(writer / 'receipt.json'),
                bind(ROOT / 'build/retained-callable-attribution-r4/receipt.json'),
                bind(Path(__file__)),
                bind(ROOT / 'tools/host-lisp/retained_callable_writer_probe_r1.py'),
                bind(ROOT / 'tools/host-lisp/retained_callable_writer_probe_r2.py'),
                bind(ROOT / 'tools/host-lisp/retained_callable_writer_probe_r3.py'),
                bind(ROOT / 'tools/host-lisp/retained_callable_writer_probe_r4.py'),
                bind(ROOT / 'tools/host-lisp/retained_callable_writer_probe_r6.py'),
                bind(ROOT / 'tools/host-lisp/retained_callable_writer_partial_receipts.py')],
        product_builds=0, observer_builds=0, links=0, seeds=0, device_contacts=0)
    (OUT / 'attribution.json').write_text(json.dumps(result, indent=2) + '\n')
    print(result['status'])
    for row in events:
        print(row['label'], row['pc'], row['resident_overlay'], row['owning_function'],
              row['watched_span'], row['c2d_counts'])
    print('population', population['pre_existing_entries_changed'], population['new_entries_zeroed'])
    for row in sweep.get('rows', []):
        print('N', row['n'], row['counts'], row['last_entry_zero'], row['call_result'])
    for row in release.get('capfill_class', []):
        print('2.3.0 N', row['n'], row['counts'], row['last_entry_zero'], row['call_result'])


if __name__ == '__main__':
    main()
