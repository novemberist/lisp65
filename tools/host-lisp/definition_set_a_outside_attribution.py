"""Read-only accounting of existing whole-form and Append observations.

Buffer ownership is diagnostic, not an exclusive semantic-stage proof.
Inclusive logical memberships are deliberately not summed.
"""
from collections import Counter
from pathlib import Path
import hashlib
import json
import sys
from elf_truth import ElfTruth

ROOT = Path(__file__).resolve().parents[2]


def checked(binding):
    path = ROOT / binding['path']
    assert hashlib.sha256(path.read_bytes()).hexdigest() == binding['sha256']
    return path


def counts(binding, tag):
    result = Counter()
    for line in checked(binding).read_text().splitlines():
        fields = line.split()
        if fields and fields[0] == tag:
            # F: CPU + DMA (not the overlapping membership column).
            result[int(fields[1])] = sum(map(int, fields[2:4]))
    return result


def subtract(a, b):
    return Counter({k: a.get(k, 0) - b.get(k, 0) for k in a.keys() | b.keys()})


def world(directory):
    path = ROOT / directory / 'receipt.json'
    receipt = json.loads(path.read_text())
    assert receipt['status'] == 'PASS'
    entries = json.loads(checked(receipt['manifest']).read_text())['entries']
    whole = receipt['whole']
    def boundary_charge(binding, pc):
        fields = [line.split() for line in checked(binding).read_text().splitlines()]
        count = next(int(w[2]) for w in fields if w[0] == 'P' and int(w[1]) == pc)
        cycles = next(int(w[2]) for w in fields if w[0] == 'C' and int(w[1]) == pc)
        charge, remainder = divmod(cycles, count)
        assert remainder == 0
        return charge
    def correction(span, after, entry_size):
        entry = int(span['witness']['entry'].split()[0], 16) - entry_size
        return boundary_charge(after, entry) - boundary_charge(after, span['witness']['pc'])
    whole_correction = correction(whole, whole['after'], 1)
    raw = subtract(counts(whole['after'], 'F'), counts(whole['before'], 'F'))
    assert sum(raw.values()) == whole['cycles']
    append = Counter()
    append_correction = 0
    for row in receipt['rows']:
        delta = subtract(counts(row['after_trace'], 'F'), counts(row['before_trace'], 'F'))
        assert sum(delta.values()) == row['cycles']
        append.update(delta)
        append_correction += correction(row, row['after_trace'], 2)
    outside = subtract(raw, append)
    names = Counter()
    for ordinal, cycles in outside.items():
        name = entries[ordinal]['name'] if ordinal < len(entries) else f'dynamic-or-none:{ordinal}'
        names[name] += cycles
    stages = subtract(counts(whole['after'], 'T'), counts(whole['before'], 'T'))
    for row in receipt['rows']:
        stages.subtract(subtract(counts(row['after_trace'], 'T'), counts(row['before_trace'], 'T')))
    assert sum(stages.values()) == sum(outside.values())
    # T is an observer accounting bucket, not a session-slice ID outside Append.
    def cpu(binding):
        return Counter({int(w[1]): int(w[2]) for line in checked(binding).read_text().splitlines()
                        if (w := line.split()) and w[0] == 'C'})
    pcs = subtract(cpu(whole['after']), cpu(whole['before']))
    for row in receipt['rows']:
        pcs.subtract(subtract(cpu(row['after_trace']), cpu(row['before_trace'])))
    truth = ElfTruth.read(checked(receipt['elf']), llvm_readobj=ROOT/'tools/llvm-mos/bin/llvm-readobj')
    functions = [s for s in truth.symbols if s.symbol_type == 'Function' and s.bytes]
    native = Counter()
    for pc, cycles in pcs.items():
        if not cycles:
            continue
        matches = [s for s in functions if s.value <= pc < s.value + s.bytes]
        # Overlay PCs can alias: preserve the ambiguity rather than guessing.
        label = '|'.join(sorted(s.name for s in matches)) or f'unmapped:{pc:04x}'
        native[label] += cycles
    return dict(receipt_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                whole_raw=whole['cycles'], append_raw=sum(append.values()),
                outside_raw=sum(outside.values()), ownership=names,
                outside_boundary_correction=whole_correction-append_correction,
                outside_exact=sum(outside.values())+whole_correction-append_correction,
                native_cpu=native, observation_buckets=dict(stages))


if __name__ == '__main__':
    emitter = '--emitter' in sys.argv
    before = world('build/definition-set-a-emitter-before-5-r2' if emitter else 'build/definition-ledger-full-5-r2')
    after = world('build/definition-set-a-emitter-seed-5-r2' if emitter else 'build/definition-set-a-ledger-5-r2')
    delta = subtract(after['ownership'], before['ownership'])
    assert sum(delta.values()) == after['outside_raw'] - before['outside_raw']
    print(json.dumps(dict(before=before, after=after, delta=sum(delta.values()),
                         ownership_deltas=sorted(delta.items(), key=lambda x: -abs(x[1])),
                         native_cpu_deltas=sorted(subtract(after['native_cpu'], before['native_cpu']).items(), key=lambda x: -abs(x[1])),
                         observation_bucket_deltas=sorted(subtract(Counter(after['observation_buckets']), Counter(before['observation_buckets'])).items(), key=lambda x: -abs(x[1])),
                         limit='Raw witnessed intervals; boundary charges and semantic attribution remain separate.'), indent=2))
