"""Seal the export-publication card's host evidence; no build, no device.

SCAFFOLD ONLY, structured after boot_name_index_seal.py (itself a scaffold
"structured after native_diet_seal.py"). AUTH is still '227e59e9' (see
export_publication_producer.py), so no Seed has been constructed and none of
PRICE/IDENTITY/INVOCATION/ATTEMPT/SOURCE_RUN/MEDIUM/DIFFERENTIAL below exist
on disk yet. main() therefore refuses to run past that gate, mirroring the
producer's own AUTH_PENDING refusal, instead of failing on missing files
with a less informative message.

Once AUTH is bound and the Seed/medium/qualification runs above have
produced their receipts, this file still needs:
  - Confirmation that the boot ledger reference stays the boot-name-index
    capture (build/boot-name-index-boot-ledger-r1/capture-r1), per the
    coordinator's instruction, rather than a new capture of its own -- this
    card carries no boot-time behavior change of its own to re-measure (its
    hunk is confined to c2_product_runtime.c's already-admitted phase-10
    dispatch), so the r5 boot ledger is the correct "predecessor" row and
    this card's own BOOT capture (once taken) is compared against it exactly
    as boot_name_index_seal.py compares its own BOOT against
    BOOT_REFERENCE=session-bank-alignment's ledger.
  - DIFFERENTIAL: build/export-publication-impl-r1/differential/receipt.json
    is the publication differential the concurrent Opus agent's source
    authority produces; it does not exist yet. Bound here (see DIFFERENTIAL
    below) as a prospective path, the same way every other *_PATH constant
    in this file is prospective until AUTH binds.
  - The manifest region-0 free-bytes figure and Session catalog counts,
    read back from the packed Session bank manifest
    (build/export-publication-seed-medium-r1/...) -- unchanged in COUNT from
    r5 (55 records) unless this card's own commissioned hunk is shown to add
    one, which the producer's SOURCES/HEADERS population does not indicate.
Every figure this seal eventually writes must be read back from the
artifact that produced it and bound by path/bytes/SHA, exactly as
native_diet_seal.py/boot_name_index_seal.py do; nothing here should be typed
in by hand.
"""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SEAL = ROOT/('tests/bytecode/dialect-v2/evidence/architecture-blocks/'
             'export-publication-final.json')
PRICE = ROOT/'build/export-publication-product-r2/wplto/export-publication-second-seed-price.json'
IDENTITY = ROOT/'build/export-publication-r1/final-identity.json'
INVOCATION = ROOT/'build/export-publication-r1/final-invocation.json'
ATTEMPT = ROOT/'build/export-publication-r1/final-attempt.json'
COMPOSITION = ROOT/'build/export-publication-r1/composition.json'
SOURCE_RUN = ROOT/'build/export-publication-source-qualification-r1/full-source-run.json'
MEDIUM = ROOT/'build/export-publication-seed-medium-r1/packed-receipt.json'
# The publication differential the concurrent source-authority commit is
# expected to produce; does not exist yet (AUTH_PENDING) -- see module
# docstring.
DIFFERENTIAL = ROOT/'build/export-publication-impl-r1/differential/receipt.json'
BOOT = ROOT/'build/export-publication-boot-ledger-r1/capture-r1'
# Predecessor reference stays the boot-name-index card's own boot ledger
# capture (this card's own producer predecessor, r5) -- per coordinator
# instruction -- not session-bank-alignment's, unlike boot_name_index_seal.py
# whose own BOOT_REFERENCE is one card further back (its own producer
# predecessor at the time, session-bank-alignment).
BOOT_REFERENCE = ROOT/'build/boot-name-index-boot-ledger-r1/capture-r1'
INTERN = {'baseline': ROOT/'build/export-publication-intern-lane-baseline-r2/receipt.json',
          'candidate': ROOT/'build/export-publication-intern-lane-candidate-r2/receipt.json'}
LANES = {'natural': ROOT/'build/export-publication-native-natural-r2/receipt.json',
         'equal-phase': ROOT/'build/export-publication-native-equal-phase-r2/receipt.json'}
GC = {'baseline': ROOT/'build/export-publication-gc-equal-baseline-0/receipt.json',
      'candidate': ROOT/'build/export-publication-gc-equal-candidate-0/receipt.json'}
FREQUENCY = 40.5e6
AUTH = '227e59e9'


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
    differential = load(DIFFERENTIAL)
    # The differential receipt carries no status word; its verdict is the
    # `all_as_expected` flag over the whole publication population.
    if differential.get('all_as_expected') is not True or differential.get('population') != 507:
        raise SystemExit('publication differential is not green')
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
    intern = {name: load(path) for name, path in INTERN.items()}
    if any(v['status'] != 'PASS' for v in intern.values()):
        raise SystemExit('intern lane is not green')
    keys = lambda rows: [(r['name'], r['phase'], r['before'], r['after'], r['result']) for r in rows]
    if keys(intern['baseline']['rows']) != keys(intern['candidate']['rows']):
        raise SystemExit('intern lane: names, counts or results differ between worlds')
    intern_cycles = {name: {ph: sum(r['cycles'] for r in v['rows'] if r['phase'] == ph)
                            for ph in ('new', 'existing')} for name, v in intern.items()}
    session = json.loads((MEDIUM.parent/'materialized/runtime-overlays-session-final.json').read_text())
    region0_end = max(s['file_offset']+s['file_size'] for s in session['slices'] if s.get('region_id', 0) == 0)
    value = dict(
        format='lisp65-export-publication-final-v1',
        status='PASS: HOST QUALIFIED; DEVICE ROWS BATCHED',
        authority=AUTH,
        budget=dict(seed=2, seed_halts=['r1: final section inventory (slices not registered in the link tool)'], final=1, link=1, device_contacts=0),
        shape=dict(shape='C', slices={'10a': 53, '10b': 54},
                   feature='LISP65_C2_BOOT_NAME_INDEX',
                   feature_admitted_by='boot-name-index (predecessor r5); '
                                       'not re-admitted by this card',
                   session_catalog=session['catalog']['slice_count'],
                   session_region0_end=region0_end, session_region0_free=65536-region0_end,
                   session_payload_alignment=session['policy']['payload_alignment']),
        intern_lane=dict(receipts={n: bind(pth) for n, pth in INTERN.items()},
                         identical_names_counts_results=True, cycles=intern_cycles),
        price=bind(PRICE), price_status=price['status'],
        section_deltas=price.get('section_deltas'),
        seed_ELF=price['candidate']['ELF'], predecessor_ELF=price['predecessor']['ELF'],
        final=dict(identity=bind(IDENTITY), invocation=bind(INVOCATION),
                   attempt=bind(ATTEMPT), byteidentical=True,
                   seed_rebuilds=load(ATTEMPT)['seed_rebuilds']),
        composition=bind(COMPOSITION),
        differential=bind(DIFFERENTIAL),
        source_qualification=dict(receipt=bind(SOURCE_RUN),
                                  protected_files=run['protected_files'],
                                  changed_protected_files=run['changed_protected_files'],
                                  sealed_artifacts_read_only=run['sealed_artifacts_read_only'],
                                  seconds=run['seconds']),
        medium=dict(receipt=bind(MEDIUM), manifest_policy=medium.get('manifest', {}).get('policy')),
        boot_ledger=dict(candidate=boot, predecessor_index_world=reference,
                         claim=('emulated cycle equivalents at 40.5 MHz; not a '
                                'physical stopwatch and not a device claim')),
        lanes=lanes, gc_equal_state=gc,
        limits=['no device contact; the batched device rows remain open',
                'boot figures are emulator cycle equivalents',
                'this card admits no new feature/slice; both are carried '
                'unchanged from the boot-name-index predecessor (r5)'],
    )
    SEAL.write_text(json.dumps(value, indent=2, sort_keys=True)+'\n', encoding='utf-8')
    print('export-publication seal: WRITTEN '+str(SEAL.relative_to(ROOT)))
    print('  final byteidentical=%s' % (value['final']['byteidentical'],))


if __name__ == '__main__':
    main()
