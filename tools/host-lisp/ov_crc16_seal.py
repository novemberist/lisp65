"""Seal the ov_crc16 card's host evidence; no build, no device.

SCAFFOLD ONLY, structured after export_publication_seal.py (itself
structured after boot_name_index_seal.py/native_diet_seal.py). AUTH is still
'AUTH_PENDING' (see ov_crc16_producer.py), so no Seed has been constructed
and none of PRICE/IDENTITY/INVOCATION/ATTEMPT/SOURCE_RUN/MEDIUM/
DIFFERENTIAL/LEAF_GATE below exist on disk yet. main() therefore refuses to
run past that gate, mirroring the producer's own AUTH_PENDING refusal,
instead of failing on missing files with a less informative message.

The AUTH guard below is written as `if AUTH == AUTH_PENDING_SENTINEL`
rather than `if AUTH == 'AUTH_PENDING'`: a global sed run across this
substitution family (rebinding every card's own 'AUTH_PENDING' literal to
the real commit at once) would otherwise silently rewrite the STRING
LITERAL inside this guard's comparison as well, turning it into a
tautologically-false (or wrongly-true) check instead of leaving the guard
intact. Binding the sentinel to a module-level constant defined once, well
away from the textual pattern a blanket "AUTH_PENDING" -> "<commit>" sed
would target, keeps the guard's own comparison text stable regardless of
how AUTH itself gets rebound.

Once AUTH is bound and the Seed/medium/qualification runs above have
produced their receipts, this file still needs:
  - Confirmation that the boot ledger reference stays the export-publication
    capture (build/export-publication-boot-ledger-r1/capture-r1), per the
    coordinator's instruction, rather than a new capture of its own -- this
    card carries no boot-time behavior change of its own to re-measure
    beyond replacing one JSR target with another of the same ABI (its hunk
    is confined to the two already-admitted ov_crc16 call sites), so the r2
    boot ledger is the correct "predecessor" row and this card's own BOOT
    capture (once taken) is compared against it exactly as
    export_publication_seal.py compares its own BOOT against
    BOOT_REFERENCE=boot-name-index's ledger. No boot-time claim is made for
    this card (see build/ov-crc16-preflight-r1/report-draft.md: "no valid
    cycles-per-byte comparison with the leaf without a controlled probe");
    BOOT/BOOT_REFERENCE here are the stated-not-claimed ledger figures, not
    a speed claim.
  - DIFFERENTIAL: build/ov-crc16-impl-r1/differential.json is the CRC
    differential the concurrent Opus agent's source authority produces
    (host differential between the removed ov_crc16 path and the retargeted
    rtov_crc_mem path); it does not exist yet. Bound here as a prospective
    path, the same way every other *_PATH constant in this file is
    prospective until AUTH binds.
  - LEAF_GATE: the assembler-leaf ABI gate receipt binding
    `c2_asm_leaf_abi_gate.py`'s own proof that both retargeted call sites
    are direct JSRs into rtov_crc_mem with locally provable register
    setup, and that the ASM commit leaf's own `_crc_call_gate` names
    rtov_crc_mem (not ov_crc16) as its single CRC target -- the gate this
    card's whole form (b) depends on (see build/ov-crc16-preflight-r1/
    receipt.json: "form_b_retarget_callers" -> gate_changes_required).
    Bound here as a prospective path.
  - The manifest region-0 free-bytes figure and Session catalog counts,
    read back from the packed Session bank manifest
    (build/ov-crc16-seed-medium-r1/...) -- unchanged in COUNT from r2 (55
    records): this card removes a function and retargets two call sites,
    it does not touch the Session catalog.
Every figure this seal eventually writes must be read back from the
artifact that produced it and bound by path/bytes/SHA, exactly as
native_diet_seal.py/boot_name_index_seal.py/export_publication_seal.py do;
nothing here should be typed in by hand.
"""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SEAL = ROOT/('tests/bytecode/dialect-v2/evidence/architecture-blocks/'
             'ov-crc16-final.json')
PRICE = ROOT/'build/ov-crc16-product-r1/wplto/ov-crc16-first-seed-price.json'
IDENTITY = ROOT/'build/ov-crc16-r1/final-identity.json'
INVOCATION = ROOT/'build/ov-crc16-r1/final-invocation.json'
ATTEMPT = ROOT/'build/ov-crc16-r1/final-attempt.json'
COMPOSITION = ROOT/'build/ov-crc16-r1/composition.json'
SOURCE_RUN = ROOT/'build/ov-crc16-source-qualification-r1/full-source-run.json'
MEDIUM = ROOT/'build/ov-crc16-seed-medium-r1/packed-receipt.json'
# The CRC differential the concurrent source-authority commit is expected to
# produce; does not exist yet (AUTH_PENDING) -- see module docstring.
DIFFERENTIAL = ROOT/'build/ov-crc16-impl-r1/differential.json'
# The assembler-leaf ABI gate's own receipt, binding proof that both
# retargeted call sites are direct JSRs into the proven leaf rtov_crc_mem;
# does not exist yet (AUTH_PENDING) -- see module docstring.
LEAF_GATE = ROOT/'build/ov-crc16-r1/leaf-abi-gate.json'
BOOT = ROOT/'build/ov-crc16-boot-ledger-r1/capture-r1'
# Predecessor reference stays the export-publication card's own boot ledger
# capture (this card's own producer predecessor, r2) -- per coordinator
# instruction -- not boot-name-index's, unlike export_publication_seal.py
# whose own BOOT_REFERENCE is one card further back (its own producer
# predecessor at the time, boot-name-index).
BOOT_REFERENCE = ROOT/'build/export-publication-boot-ledger-r1/capture-r1'
INTERN = {'baseline': ROOT/'build/ov-crc16-intern-lane-baseline-r1/receipt.json',
          'candidate': ROOT/'build/ov-crc16-intern-lane-candidate-r1/receipt.json'}
LANES = {'natural': ROOT/'build/ov-crc16-native-natural-r1/receipt.json',
         'equal-phase': ROOT/'build/ov-crc16-native-equal-phase-r1/receipt.json'}
GC = {'baseline': ROOT/'build/ov-crc16-gc-equal-baseline-0/receipt.json',
      'candidate': ROOT/'build/ov-crc16-gc-equal-candidate-0/receipt.json'}
FREQUENCY = 40.5e6
AUTH = '0a41035d'
# See module docstring: a distinct constant, not the string literal itself,
# so a blanket "AUTH_PENDING" -> "<commit>" sed rebinding AUTH above cannot
# also rewrite the comparison this sentinel drives in main() below.
AUTH_PENDING_SENTINEL = 'AUTH_PENDING'


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
    if AUTH == AUTH_PENDING_SENTINEL:
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
    # The CRC differential's verdict is its status word plus the random
    # differential's mismatch count.
    random = differential.get('random_differential', {})
    if (not str(differential.get('status', '')).startswith('passed')
            or random.get('mismatches', 0) != 0):
        raise SystemExit('CRC differential is not green')
    leaf_gate = load(LEAF_GATE)
    # The gate receipt's verdict is its `status` word (`passed-…`).
    if not str(leaf_gate.get('status', '')).startswith('passed'):
        raise SystemExit('assembler-leaf ABI gate is not green')
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
        format='lisp65-ov-crc16-final-v1',
        status='PASS: HOST QUALIFIED; DEVICE ROWS BATCHED',
        authority=AUTH,
        budget=dict(seed=1, seed_halts=[], final=1, link=1, device_contacts=0),
        shape=dict(shape='B', slices={'10a': 53, '10b': 54},
                   feature='LISP65_C2_BOOT_NAME_INDEX',
                   feature_admitted_by='boot-name-index (predecessor r5); '
                                       'not re-admitted by this card',
                   new_feature=None, new_slices=0,
                   session_catalog=session['catalog']['slice_count'],
                   session_region0_end=region0_end, session_region0_free=65536-region0_end,
                   session_payload_alignment=session['policy']['payload_alignment']),
        leaf_retarget=dict(removed='ov_crc16', target='rtov_crc_mem',
                           call_sites=['vm_boot_overlay_chain_commit (ASM, src/c2_boot_chain_commit.s)',
                                       'vm_install_staged_boot_overlay (C, src/vm_boot_overlay.c)'],
                           leaf_gate=bind(LEAF_GATE)),
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
                         claim='emulated cycle equivalents at 40.5 MHz; no speed claim for the '
                               'leaf retarget itself (no controlled equal-length probe was run)'),
        lanes=lanes, gc_equal_state=gc,
        limits=['no device contact; the batched device rows remain open',
                'boot figures are emulator cycle equivalents',
                'this card admits no new feature/slice; both are carried '
                'unchanged from the boot-name-index predecessor (r5)',
                'no cycles-per-byte claim between ov_crc16 and rtov_crc_mem'],
    )
    SEAL.write_text(json.dumps(value, indent=2, sort_keys=True)+'\n', encoding='utf-8')
    print('ov-crc16 seal: WRITTEN '+str(SEAL.relative_to(ROOT)))
    print('  final byteidentical=%s' % (value['final']['byteidentical'],))


if __name__ == '__main__':
    main()
