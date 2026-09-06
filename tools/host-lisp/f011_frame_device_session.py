#!/usr/bin/env python3
"""Bind a diagnostic cold-start contact; never deploy or access hardware."""
import argparse
from copy import deepcopy
import re

import f011_frame_diagnostic_card as D
from elf_truth import ElfTruth
from evidence_era import stable_recorded_on

OUT = D.ROOT / 'config/v2.1-f011-frame-device-session.json'
WARM_OUT = D.ROOT / 'config/v2.1-f011-frame-warmstart-session.json'


def record_layout():
    header = D.PRICE.HEADER.read_text()
    emitted = D.WPLTO / 'generated-product-sources' / D.PRICE.HEADER.name
    assert emitted.read_text() == header, 'bound diagnostic header differs'
    body = re.search(r'typedef struct \{(.*?)\} f011_status_record;', header, re.S).group(1)
    fields, offset = [], 0
    for kind, names in re.findall(r'(uint8_t|uint16_t)\s+([^;]+);', body):
        size = {'uint8_t': 1, 'uint16_t': 2}[kind]
        for name in names.split(','):
            fields.append({'name': name.strip(), 'offset': offset, 'bytes': size})
            offset += size
    assert offset == 7 and len(fields) == 6
    cap = int(re.search(r'#define F011_MEASURE_CAP_FRAMES (\d+)u', header).group(1))
    return fields, cap


def decode(raw, fields):
    assert len(raw) == 7, 'record width differs'
    values = {f['name']: int.from_bytes(raw[f['offset']:f['offset']+f['bytes']], 'little')
              for f in fields}
    values['busy_after_spin_command'] = bool(values['after_spin_d082'] & 0x80)
    values['completion_mask_passes'] = (values['d082'] & 0x7c) == 0x60
    values['elapsed_frames_usable'] = values['tag'] in (1, 2, 4) and (
        values['validity'] & 7) == 7
    return values


def derive():
    proof = D.C.load(D.BUILD / 'final-proof.json')
    completion = D.C.load(D.RECEIPT)
    pair = [D.C.bind(D.ELF), D.C.bind(D.PRG)]
    assert proof['pair'] == completion['pair'] == pair
    boot = D.C.load(D.BUILD / 'prefilter/boot-r1/receipt.json')
    assert boot['status'] == 'PREFILTER GREEN'
    assert D.C.bind(D.ROOT / boot['medium']['path']) == completion['medium'] == boot['medium']
    truth = ElfTruth.read(D.ELF, llvm_readobj=D.C.B.READOBJ)
    state = truth.symbol('lisp65_f011_status_state')
    fields, cap = record_layout()
    assert state.bytes == 7 and state.value == proof['record_owner']['address']
    geometry = {n: {'address': truth.symbol(n).value, 'bytes': truth.symbol(n).bytes}
                for n in ('scr_base', 'cols_', 'rows_')}
    low = min(v['address'] for v in geometry.values())
    high = max(v['address'] + v['bytes'] for v in geometry.values())
    assert high - low <= 16 and high < 0x100
    raw = bytes.fromhex(boot['record_hex'])
    memory = D.ROOT / boot['outputs']['memory']['path']
    assert D.C.bind(memory) == boot['outputs']['memory']
    assert memory.read_bytes()[state.value:state.value+7] == raw
    return {
        'format': 'f011-frame-cold-start-session-v1',
        'recorded_on': stable_recorded_on(OUT),
        'status': 'BOUND; NOT STARTED; POWER-CYCLE BOOT TRANSPORT UNCONFIRMED',
        'authority': 'Alex: current-turn cold-start session authorization; power off >=30 seconds',
        'diagnostic_completion': D.C.bind(D.RECEIPT), 'pair': pair,
        'medium': dict(boot['medium'], remote_name='V21FRAME.D81'),
        'bound_record_header': D.C.bind(D.PRICE.HEADER),
        'prefilter': D.C.bind(D.BUILD / 'prefilter/boot-r1/receipt.json'),
        'choreography': {
            'fresh_restore_and_SHA_readback': True, 'power_off_min_seconds': 30,
            'power_off_duration_recorded': True, 'stops': 1, 'resumes': 0,
            'resets_after_power_on': 0, 'F011_register_reads': 0,
            'typing_after_power_on': False, 'automated_input': False,
            'freezer_operations': 0,
            'start_prerequisite': 'Prove the selected bound D81 and AUTOBOOT.C65 remain available after power off. A pre-power-off RAM PRG upload is not a boot path. If unconfirmed, do not start the contact.',
            'order': ['restore-and-SHA-readback', 'owner-power-off',
                      'wait-at-least-30-seconds', 'owner-power-on-no-typing',
                      'first-screen-banner-or-cannot-open', 'stop-once',
                      'seal-raw-RAM-record', 'seal-RAM-geometry',
                      'derive-and-seal-framebuffer', 'interpret-without-resume']},
        'record': {'symbol': state.name, 'address': state.value, 'bytes': state.bytes,
                   'fields': fields, 'endian': 'little',
                   'RAM_monitor_window': {'address': state.value, 'bytes': 16},
                   'retention': 'First success retained until first failure replaces it; first failure never overwritten. No read ordinal is recorded.'},
        'screen': {'symbols': geometry,
                   'RAM_monitor_window': {'address': low, 'bytes': 16},
                   'derived_read': 'base=scr_base; logical bytes=cols_*rows_; transport rounded up to 16 bytes; validate 1<=cols<=80, 1<=rows<=25 and entire transport in ordinary RAM [0x0200,0x8000) before reading; otherwise stop without reading the surface'},
        'frame_cap': cap,
        'time_units': 'Frames. No seconds conversion without the measured video/frame rate. Fuel is a bounded no-clock escape, never elapsed time.',
        'calibration': {'raw_hex': raw.hex(), 'decoded': decode(raw, fields),
                        'scope': 'Emulator only; no measured physical spin-up or timing noise claim'},
        'decision_table': {
            'tag1-valid-time-mask-passes': 'Completion observed in N frames; price a separate repair card with historical command ordering and measured margin/cap. No repair or release approval from this diagnostic contact.',
            'tag4-valid-time-cap-reached': 'No completion within the cap; deeper attribution, no automatic timeout enlargement.',
            'tag5': 'Clock not observed or lost; do not base the repair on FF83 at this read point.',
            'tag2': 'Completion status fails the mask; retain raw bytes and attribute status, not a successful timing calibration.',
            'tag0-or-inconsistent': 'Coverage/readpoint unresolved; no success or clock-validity claim.'},
        'claim_boundary': {'diagnostic_only': True, 'release_eligible': False,
                           'Comfort_attributed': False, 'device_contacts_executed': 0}}


def validate_binding(candidate, expected):
    assert candidate == expected, 'session binding drift'


def derive_warm_start(cold):
    value = deepcopy(cold)
    value.update(format='f011-frame-freezer-warmstart-session-v1',
        recorded_on=stable_recorded_on(WARM_OUT),
        status='BOUND; NOT UPLOADED; NOT STARTED',
        variant='B_FREEZER_MOUNT_WARMSTART',
        authority='Alex selected Freezer mount followed by warmstart; no physical cold-start claim')
    value['choreography'] = {
        'fresh_restore_and_SHA_readback': True,
        'initial_power_state': 'not constrained; not evidence of power-off cold start',
        'freezer_operations': 1, 'owner_warmstarts_before_measurement': 1,
        'stops': 1, 'resumes': 0, 'resets_after_measurement_start': 0,
        'F011_register_reads': 0, 'automated_input': False,
        'typing_after_product_start': False,
        'start_prerequisite': 'Owner mounts exactly the SHA-readback D81 through the Freezer, then warmstarts into that product. If the product does not start, stop and report; no improvised loader or additional reset.',
        'order': ['restore-and-SHA-readback', 'owner-freezer-mount-bound-D81',
                  'owner-warmstart', 'product-start-no-typing',
                  'first-screen-banner-or-cannot-open', 'stop-once',
                  'seal-raw-RAM-record', 'seal-RAM-geometry',
                  'derive-and-seal-framebuffer', 'interpret-without-resume']}
    value['decision_table']['tag1-valid-time-mask-passes'] = (
        'Completion observed in N frames in the Freezer-mount/warmstart variant only. '
        'Do not use this number alone to size a power-off cold-start timeout or lift the release block.')
    value['claim_boundary'].update(physical_cold_start=False,
        SD_initialization_cause_established=False,
        Freezer_behavior_covered_by_prefilter=False,
        unmeasured_variant='A: automatic product boot after >=30 seconds power off remains untested')
    return value


def warm_selftest(value):
    rejected = []
    for name, path, replacement in (
        ('warmstart-promoted-to-coldstart', ('claim_boundary', 'physical_cold_start'), True),
        ('emulator-promoted-to-Freezer-proof', ('claim_boundary', 'Freezer_behavior_covered_by_prefilter'), True),
        ('unbound-SD-cause', ('claim_boundary', 'SD_initialization_cause_established'), True),
        ('omit-readback', ('choreography', 'fresh_restore_and_SHA_readback'), False),
        ('resume-after-stop', ('choreography', 'resumes'), 1),
        ('extra-reset', ('choreography', 'resets_after_measurement_start'), 1)):
        trial = deepcopy(value); trial[path[0]][path[1]] = replacement
        try:
            validate_binding(trial, value)
        except AssertionError:
            rejected.append(name)
        else:
            raise AssertionError('warmstart mutation survived: ' + name)
    return rejected


def selftest(value):
    fields = value['record']['fields']
    calibration = decode(bytes.fromhex('017262aa000007'), fields)
    assert calibration['frames'] == 0 and calibration['validity'] == 7
    assert not calibration['busy_after_spin_command'] and calibration['elapsed_frames_usable']
    assert decode(bytes.fromhex('01d062aa010207'), fields)['frames'] == 513
    assert decode(bytes.fromhex('05d0d008ffff03'), fields)['elapsed_frames_usable'] is False
    wrong = deepcopy(fields)
    next(f for f in wrong if f['name'] == 'frames').update(offset=6, bytes=1)
    assert decode(bytes.fromhex('017262aa000007'), wrong)['frames'] != calibration['frames']
    # Exercise the same rejection boundary used by the check command.
    wrong_busy = deepcopy(calibration)
    wrong_busy['busy_after_spin_command'] = True
    for wrong_value in (decode(bytes.fromhex('017262aa000007'), wrong), wrong_busy):
        try:
            validate_binding(wrong_value, calibration)
        except AssertionError:
            pass
        else:
            raise AssertionError('incorrect calibration interpretation survived')
    mutants = []
    for name, path, replacement in (
        ('warm-reset-as-cold-start', ('choreography', 'power_off_min_seconds'), 0),
        ('omit-media-readback', ('choreography', 'fresh_restore_and_SHA_readback'), False),
        ('resume-after-read', ('choreography', 'resumes'), 1),
        ('F011-register-read', ('choreography', 'F011_register_reads'), 1),
        ('stale-three-byte-record', ('record', 'bytes'), 3),
        ('diagnostic-promoted-to-release', ('claim_boundary', 'release_eligible'), True)):
        trial = deepcopy(value); trial[path[0]][path[1]] = replacement
        try:
            validate_binding(trial, value)
        except AssertionError:
            mutants.append(name)
        else:
            raise AssertionError('session mutation survived: ' + name)
    return ['flags-as-frame-count', 'wrong-BUSY-bit', 'invalid-clock-as-elapsed-time', *mutants]


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['emit', 'check'])
    action = parser.parse_args().action
    value = derive(); rejected = selftest(value)
    warm = derive_warm_start(value); rejected.extend(warm_selftest(warm))
    if action == 'emit':
        OUT.write_bytes(D.C.canonical(value))
        WARM_OUT.write_bytes(D.C.canonical(warm))
    else:
        validate_binding(D.C.load(OUT), value)
        validate_binding(D.C.load(WARM_OUT), warm)
    print('F011 frame session bindings PASS; selected=Freezer-warmstart; controls=' + str(len(rejected)) + '; hardware=0')
