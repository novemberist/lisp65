"""Exact r7 disk source lane, separate from immutable predecessor replays."""
import argparse
import builtins
import copy
import hashlib
import io
import json
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

import strings_successor_r2_20260928 as S
import evidence_era as E
import o2_lite_consumers_20260929 as O

ROOT = S.ROOT
SOURCE = 'lib/m65-disk.lisp'
SOURCE_SHA = '4c05de2d65cbc6e27bb5e689e7fed93c60ddfcc44c58962c9b94c0aac39b7525'
ERA = '4fddd315afec4a62e8d2880828a3e7eeca64da27'
SUITE = 'tests/bytecode/libs/p0-m65d-lib-disk-r7-20260930.json'
CLOSURE = 'config/v2-workbench-artifact-closure-disk-r7-20260930.json'
RECEIPT = 'config/disk-r7-consumers-receipt-20260930.json'
FROZEN = 'build/walks-product-r1/plane/candidate/m65d.manifest.json'
PINS = {SOURCE: SOURCE_SHA,
        SUITE: '5e540a6824719f05010c9d6d35f113a626961e893c6f681a3868705650bfb149',
        CLOSURE: '65cc26490b28179abd0f162d01cf03afb360d22b521f3655f28b7e7709693396',
        FROZEN: '86f27e83004c6d99036832506c1f393e8babafe6d2ad27386454198fdec23cf2'}
SUPPORT = ['tools/host-lisp/' + p + '.py' for p in (
    'disk_r7_directory_20260930', 'v2_workbench_codemod_disk_r7_20260930',
    'v2_workbench_codemod', 'bytecode_p0_stdlib', 'bytecode_p0_compiler',
    'bytecode_p0', 'strings_scratch_20260928', 'o2_lite_consumers_20260929')]


def require(ok, message):
    S.require(ok, message)


@contextmanager
def predecessor_disk():
    """Only the disk source is replayed; nested era selectors keep precedence."""
    before = E.era_blob(ERA, SOURCE)
    a, b = builtins.open, io.open
    def opened(original, file, mode='r', *args, **kwargs):
        if isinstance(file, (str, Path)) and Path(file).resolve() == ROOT / SOURCE:
            require(mode in ('r', 'rt', 'rb'), 'write to predecessor disk')
            return io.BytesIO(before) if 'b' in mode else io.StringIO(before.decode())
        return original(file, mode, *args, **kwargs)
    with patch.object(builtins, 'open', lambda *a_, **kw: opened(a, *a_, **kw)), \
         patch.object(io, 'open', lambda *a_, **kw: opened(b, *a_, **kw)):
        yield


def source_controls():
    def validate(rows):
        require(rows == PINS, 'r7 source/suite/closure/frozen binding drift')
    actual = {p: S.bind(p)['sha256'] for p in PINS}
    validate(actual)
    for p in PINS:
        trial = dict(actual)
        trial[p] = '0' * 64
        try:
            validate(trial)
        except ValueError:
            pass
        else:
            raise ValueError('r7 binding mutation survived: ' + p)
    old = json.loads((ROOT / 'tests/bytecode/libs/p0-m65d-lib.json').read_bytes())
    new = json.loads((ROOT / SUITE).read_bytes())
    expected = copy.deepcopy(new)
    expected['cases'] = expected['cases'][:-3]
    require(expected == old, 'inherited M65D suite population drift')
    require(len({r['name'] for r in new['cases']}) == len(new['cases']), 'duplicate disk test')
    O.controls()


def measure():
    """Recompile both worlds; compare every object payload and literal table."""
    import bytecode_p0_stdlib as P
    import v2_workbench_codemod as C
    source_controls()
    with O.scratch() as out:
        __import__("v2_workbench_codemod_disk_r7_20260930").generate(ROOT / CLOSURE, out / 'generated')
        path = out / 'generated/suites/p0-m65d-lib.json'
        suite = P._read_suite(str(path))
        require(len(suite['private_inline_functions']) == 14, 'product inline population drift')
        result = P.check_suite(str(path), suite)
        candidate_source = Path(suite['sources'][0])
        if not candidate_source.is_absolute():
            candidate_source = ROOT / candidate_source
        rewritten, _ = C.rewrite_tokens((ROOT / SOURCE).read_text())
        require(candidate_source.read_text() == rewritten, 'stale generated disk source')
        values = {}
        for side in ('baseline', 'current'):
            text = E.era_blob(ERA, SOURCE).decode() if side == 'baseline' else (ROOT / SOURCE).read_text()
            text, _ = C.rewrite_tokens(text)
            source = out / (side + '.lisp')
            source.write_text(text)
            selected = dict(suite, sources=[str(source)])
            heap, names, codes, *_ = P._compile_suite(selected, include_cases=False)
            values[side] = dict(bytes=sum(len(codes[n].encode()) for n in names),
                objects=len(names), max_object=max(len(codes[n].encode()) for n in names),
                entries=[dict(name=n, bytes=len(codes[n].encode()), payload=codes[n].payload.hex(),
                              literals=[heap.obj_to_text(v) for v in codes[n].littab]) for n in names])
        # The old source must actually fail the new linked-directory case.
        old_suite = dict(suite, sources=[str(out / 'baseline.lisp')], cases=suite['cases'][-3:])
        try:
            P.check_suite(str(path), old_suite)
        except (P.StdlibCheckError, AssertionError) as error:
            require('disk-r7-dir-fill' in str(error), 'unexpected baseline regression failure')
        else:
            raise ValueError('old directory-clear implementation survived regression')
        frozen = json.loads((ROOT / FROZEN).read_bytes())
        blob = (ROOT / frozen['blob']).read_bytes()
        require(hashlib.sha256(blob).hexdigest() == frozen['blob_sha256'], 'old M65D blob drift')
        before = {r['name']: r for r in values['baseline']['entries']}
        after = {r['name']: r for r in values['current']['entries']}
        require(set(before) == set(after) == {r['name'] for r in frozen['entries']}, 'object population drift')
        for entry in frozen['entries']:
            raw = blob[entry['blob_offset']:entry['blob_offset'] + entry['length']]
            require(before[entry['name']]['payload'] == raw[7 + 2 * entry['lit_count']:].hex(), 'frozen M65D payload drift')
        changed = [n for n in before if before[n] != after[n]]
        require(changed == ['%m65d-dir-fill'], 'foreign object change')
        require(values['baseline']['bytes'] == 4083 and values['current']['bytes'] == 4086, 'M65D price drift')
        require(values['current']['objects'] == 39 and values['current']['max_object'] <= 255, 'object capacity drift')
        return dict(source=S.bind(SOURCE), generated_source_sha256=hashlib.sha256(rewritten.encode()).hexdigest(),
                    cases=result['cases'], private_inlines=14, changed=changed, values=values,
                    source_mutations_rejected=len(PINS), old_source_regression_rejected=True,
                    projected_capacity=dict(delta=values['current']['bytes']-values['baseline']['bytes'],
                        static_code_bytes=50060+values['current']['bytes']-values['baseline']['bytes'],
                        shelf_bytes=99552+values['current']['bytes']-values['baseline']['bytes'],
                        aggregate_code_bytes=54788+values['current']['bytes']-values['baseline']['bytes'],
                        aggregate_limit=60758, spare_bytes=60758-54788-values['current']['bytes']+values['baseline']['bytes']),
                    claim_limit='Computed M65D source price; six-image/product delivery is deferred to Chunk C')


def finish(name, derive, receipt, predecessor, inputs=()):
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('build', 'check', 'selftest', 'qualification-check'))
    action = parser.parse_args().action
    source_controls()
    old = json.loads((ROOT / predecessor.RECEIPT).read_bytes()) if predecessor else None
    history = dict(getattr(predecessor, 'HISTORY', {}))
    if predecessor:
        history.update({str(Path(predecessor.__file__).relative_to(ROOT)): S.bind(predecessor.__file__)['sha256'],
                        predecessor.RECEIPT: S.bind(predecessor.RECEIPT)['sha256']})
    S.history(history)
    population = [r['path'] for r in old.get('inputs', [])] if old else []
    current = derive()
    value = dict(format='lisp65-disk-r7-consumer-successor-v1', date='2026-09-30', status='PASS',
                 predecessor=history, current=current,
                 inputs=[S.bind(p) for p in sorted(set([str(Path(__file__).relative_to(ROOT)), SOURCE,
                         SUITE, CLOSURE, *PINS, *SUPPORT, *population, *inputs]))],
                 product_links=0, xemu_runs=0, device_contacts=0,
                 claim_limit='Host source proof; r7 product/media acceptance requires Chunk C')
    raw = S.canonical(value)
    path = ROOT / receipt
    if action == 'build':
        with path.open('xb') as stream:
            stream.write(raw)
    else:
        require(path.read_bytes() == raw, name + ' r7 receipt drift')
    print(name + ': ' + action.upper() + ' PASS')


def replay(predecessor):
    """Execute inherited assertions, then require the complete old measurement."""
    with predecessor_disk(), O.scratch():
        value = predecessor.derive()
    old = json.loads((ROOT / predecessor.RECEIPT).read_bytes())
    require(value == old['current'], 'predecessor disk replay drift')
    return dict(inherited=value, disk_r7=measure())


if __name__ == '__main__':
    from disk_r7_directory_20260930 import verify
    def derive_source():
        return dict(price=measure(), directory=verify())
    finish('disk-r7-source', derive_source, RECEIPT, None, (__file__,))
