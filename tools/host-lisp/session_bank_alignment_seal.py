"""Seal the session-bank-alignment card's host evidence; no build, no device.

SCAFFOLD ONLY. Structured after native_diet_seal.py, but several paths and
figures below cannot be bound yet: AUTH is still '0ed9e98d' (see
session_bank_alignment_producer.py), so no Seed has been constructed and
none of PRICE/IDENTITY/INVOCATION/ATTEMPT/SOURCE_RUN/MEDIUM below exist on
disk yet. main() therefore refuses to run past that gate, mirroring the
producer's own AUTH_PENDING refusal, instead of failing on missing files
with a less informative message.

Once AUTH is bound and the Seed/medium/qualification runs above have
produced their receipts, this file still needs:
  - GC/lane receipt paths bound to this card's own r1 world (placeholders
    below reuse the *-s4-* / *-r4 naming this card does not use; they are
    left as TODO markers, not measured names).
  - A BOOT/BOOT_REFERENCE pair once a boot ledger capture for this card's
    world exists (the plan's owner word says "the ledger decides"; no
    capture has been taken here).
  - The manifest region-0 free-bytes figure, read back from the packed
    Session bank manifest (build/session-bank-alignment-seed-medium-r1/...),
    against the plan's stated floor (>= 1,888 - 3,426 + the index card's two
    slices once that card resumes; on this card's own world, the measured
    free bytes are what the owner word says to state).
Every figure this seal eventually writes must be read back from the
artifact that produced it and bound by path/bytes/SHA, exactly as
native_diet_seal.py does; nothing here should be typed in by hand.
"""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SEAL = ROOT/('tests/bytecode/dialect-v2/evidence/architecture-blocks/'
             'session-bank-alignment-final.json')
PRICE = ROOT/'build/session-bank-alignment-product-r1/wplto/session-bank-alignment-seed-price.json'
IDENTITY = ROOT/'build/session-bank-alignment-r1/final-identity.json'
INVOCATION = ROOT/'build/session-bank-alignment-r1/final-invocation.json'
ATTEMPT = ROOT/'build/session-bank-alignment-r1/final-attempt.json'
COMPOSITION = ROOT/'build/session-bank-alignment-r1/composition.json'
SOURCE_RUN = ROOT/'build/session-bank-alignment-source-qualification-r1/full-source-run.json'
MEDIUM = ROOT/'build/session-bank-alignment-seed-medium-r1/packed-receipt.json'
BOOT = ROOT/'build/session-bank-alignment-boot-ledger-r1/capture-r1'
BOOT_REFERENCE = ROOT/'build/native-diet-boot-ledger-r2/capture-r1'
LANES = {'natural': ROOT/'build/session-bank-alignment-native-natural-r1/receipt.json',
         'equal-phase': ROOT/'build/session-bank-alignment-native-equal-phase-r1/receipt.json'}
GC = {'baseline': ROOT/'build/session-bank-alignment-gc-equal-baseline-0/receipt.json',
      'candidate': ROOT/'build/session-bank-alignment-gc-equal-candidate-0/receipt.json'}
FREQUENCY = 40.5e6
AUTH = '0ed9e98d'


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
    if AUTH == 'AUTH_PENDING':
        raise SystemExit('bind AUTH to the commissioned source commit first; '
                          'no Seed has been constructed to seal')
    if SEAL.exists():
        raise SystemExit('seal already exists: '+str(SEAL))
    if BOOT is None:
        raise SystemExit('bind a boot ledger capture for this card before sealing')
    price = load(PRICE)
    identity = load(IDENTITY)
    if identity['status'] != 'PASS' or not identity['ELF_byteidentical']:
        raise SystemExit('final is not byteidentical to the Seed')
    run = load(SOURCE_RUN)
    if run['exit_code'] or run['changed_files'] or run['changed_protected_files']:
        raise SystemExit('source qualification is not green and write-neutral')
    lanes = {}
    for name, path in LANES.items():
        row = load(path)
        lanes[name] = dict(receipt=bind(path),
                           ratios=row.get('ratios', row.get('ratio')))
    gc = {name: dict(receipt=bind(path), rows=load(path).get('rows', load(path)))
          for name, path in GC.items()}
    boot = boot_row(BOOT)
    reference = boot_row(BOOT_REFERENCE)
    medium = load(MEDIUM)
    value = dict(
        format='lisp65-session-bank-alignment-final-v1',
        status='PASS: HOST QUALIFIED; DEVICE ROWS BATCHED',
        authority=AUTH,
        budget=dict(seed=1, final=1, link=1, device_contacts=0),
        alignment=dict(session_payload_alignment_from=256, session_payload_alignment_to=32,
                       catalog_end_alignment=256, boot_family_alignment=256),
        price=bind(PRICE), price_status=price['status'],
        section_deltas=price.get('section_deltas'),
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
        medium=dict(receipt=bind(MEDIUM), manifest_policy=medium.get('manifest', {}).get('policy')),
        boot_ledger=dict(candidate=boot, predecessor_native_diet=reference,
                         claim=('emulated cycle equivalents at 40.5 MHz; not a '
                                'physical stopwatch and not a device claim')),
        lanes=lanes, gc_equal_state=gc,
        limits=['no device contact; the batched device rows remain open',
                'boot figures are emulator cycle equivalents',
                'the boot-time name index card (parked at its Seed 4) resumes '
                'on this card\'s world after the Final; its media adapter is '
                'already prepared for 55 records'],
    )
    SEAL.write_text(json.dumps(value, indent=2, sort_keys=True)+'\n', encoding='utf-8')
    print('session-bank-alignment seal: WRITTEN '+str(SEAL.relative_to(ROOT)))
    print('  final byteidentical=%s' % (value['final']['byteidentical'],))


if __name__ == '__main__':
    main()
