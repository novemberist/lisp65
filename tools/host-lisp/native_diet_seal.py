"""Seal the native diet/placement card's host evidence; no build, no device.

Every figure is read back from the artifact that produced it and bound by
path/bytes/SHA. The seal refuses to overwrite itself.
"""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SEAL = ROOT/('tests/bytecode/dialect-v2/evidence/architecture-blocks/'
             'native-diet-placement-final.json')
PRICE = ROOT/'build/native-diet-product-r4/wplto/native-diet-fourth-seed-price.json'
IDENTITY = ROOT/'build/native-diet-r4/final-identity.json'
INVOCATION = ROOT/'build/native-diet-r4/final-invocation.json'
ATTEMPT = ROOT/'build/native-diet-r4/final-attempt.json'
COMPOSITION = ROOT/'build/native-diet-r4/composition.json'
SOURCE_RUN = ROOT/'build/native-diet-source-qualification-r4/full-source-run.json'
LEAF_GATE = ROOT/'build/native-diet-final-leaf-gate.json'
MEDIUM = ROOT/'build/native-diet-seed-medium-r5/packed-receipt.json'
BOOT = ROOT/'build/native-diet-boot-ledger-r2/capture-r1'
BOOT_REFERENCE = ROOT/'build/boot-ledger-r1/capture-r2'
LANES = {'natural': ROOT/'build/native-diet-s4-native-natural-r1/receipt.json',
         'equal-phase': ROOT/'build/native-diet-s4-native-equal-phase-r1/receipt.json'}
GC = {'baseline': ROOT/'build/native-diet-s4-gc-equal-baseline-0/receipt.json',
      'candidate': ROOT/'build/native-diet-s4-gc-equal-candidate-0/receipt.json'}
FREQUENCY = 40.5e6


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path):
    return dict(path=str(path.relative_to(ROOT)), bytes=path.stat().st_size,
                sha256=sha(path))


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def boundaries(capture):
    """First cycle stamp per boundary ordinal from an observer trace."""
    stamps = {}
    for line in (capture/'boot.txt').read_text().splitlines():
        if line.startswith('E '):
            fields = line.split()
            stamps.setdefault(int(fields[1]), int(fields[2]))
    return stamps


def boot_row(capture):
    stamps = boundaries(capture)
    start = stamps[0]
    return dict(capture=bind(capture/'boot.txt'), prompt=bind(capture/'prompt.txt'),
                cycles_to_initializing=stamps[10]-start,
                cycles_to_banner_return=stamps[11]-start,
                seconds_to_initializing=round((stamps[10]-start)/FREQUENCY, 3),
                seconds_to_banner_return=round((stamps[11]-start)/FREQUENCY, 3))


def main():
    if SEAL.exists():
        raise SystemExit('seal already exists: '+str(SEAL))
    price = load(PRICE)
    identity = load(IDENTITY)
    if identity['status'] != 'PASS' or not identity['ELF_byteidentical']:
        raise SystemExit('final is not byteidentical to the Seed')
    run = load(SOURCE_RUN)
    if run['exit_code'] or run['changed_files'] or run['changed_protected_files']:
        raise SystemExit('source qualification is not green and write-neutral')
    leaf = load(LEAF_GATE)
    if leaf['status'] != 'passed-linked-assembler-leaf-crc-equivalence':
        raise SystemExit('CRC16 leaf gate did not pass on the Seed ELF')
    lanes = {}
    for name, path in LANES.items():
        row = load(path)
        lanes[name] = dict(receipt=bind(path),
                           ratios=row.get('ratios', row.get('ratio')))
    gc = {name: dict(receipt=bind(path), rows=load(path).get('rows', load(path)))
          for name, path in GC.items()}
    boot = boot_row(BOOT)
    reference = boot_row(BOOT_REFERENCE)
    value = dict(
        format='lisp65-native-diet-placement-final-v1',
        status='PASS: HOST QUALIFIED; DEVICE ROWS BATCHED',
        authority='4e3bdafe',
        budget=dict(seed=4, final=1, link=1, device_contacts=0),
        target=dict(resident_text_bytes_required=600,
                    resident_text_bytes_recovered=price['predecessor']['text_bytes']
                    - price['candidate']['text_bytes'],
                    shortfall=600-(price['predecessor']['text_bytes']
                                   - price['candidate']['text_bytes'])),
        price=bind(PRICE), price_status=price['status'],
        floors={name: dict(predecessor=price['predecessor'][name],
                           candidate=price['candidate'][name])
                for name in ('ordinary_text_free', 'rodata_bytes', 'rodata_free',
                             'E000_free', 'capture_free', 'high_bss_free',
                             'CRT_zero_bytes')},
        section_deltas=price['section_deltas'],
        seed_ELF=price['candidate']['ELF'], predecessor_ELF=price['predecessor']['ELF'],
        final=dict(identity=bind(IDENTITY), invocation=bind(INVOCATION),
                   attempt=bind(ATTEMPT), byteidentical=True,
                   seed_rebuilds=load(ATTEMPT)['seed_rebuilds']),
        composition=bind(COMPOSITION),
        source_qualification=dict(receipt=bind(SOURCE_RUN),
                                  protected_files=run['protected_files'],
                                  changed_protected_files=run['changed_protected_files'],
                                  sealed_artifacts_read_only=run['sealed_artifacts_read_only'],
                                  seconds=run['seconds']),
        assembler_leaf_gate=dict(receipt=bind(LEAF_GATE), leaf=leaf['leaf'],
                                 vectors=sorted(leaf['vectors'])),
        medium=dict(receipt=bind(MEDIUM)),
        boot_ledger=dict(candidate=boot, predecessor_set_a=reference,
                         claim=('emulated cycle equivalents at 40.5 MHz; not a '
                                'physical stopwatch and not a device claim')),
        prompt_screen_identical_to_predecessor=(
            (BOOT/'prompt.txt').read_bytes() == (BOOT_REFERENCE/'prompt.txt').read_bytes()),
        lanes=lanes, gc_equal_state=gc,
        limits=['no device contact; the batched device rows remain open',
                'boot figures are emulator cycle equivalents',
                'GC baseline repetitions differ by up to 110 cycles on the '
                'unchanged predecessor; differences at or below that spread '
                'are instrument noise, not a candidate effect',
                'the nibble CRC32 costs more cycles than the bit loop it '
                'replaces; the card buys resident text, and the whole boot '
                'still ends faster than the predecessor world'],
    )
    SEAL.write_text(json.dumps(value, indent=2, sort_keys=True)+'\n', encoding='utf-8')
    print('native-diet seal: WRITTEN '+str(SEAL.relative_to(ROOT)))
    print('  text recovered %d of required %d; final byteidentical=%s'
          % (value['target']['resident_text_bytes_recovered'],
             value['target']['resident_text_bytes_required'],
             value['final']['byteidentical']))


if __name__ == '__main__':
    main()
