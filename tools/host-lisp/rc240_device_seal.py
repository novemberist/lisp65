"""Seal the release-candidate 2.4.0 device session (build/rc240-device-r1).

Binds every raw file of the session, the product ELF/D81 identities, the
transport tools, the binding plan and the device report, and records the
per-row verdicts read from the session receipts. Read-only on the device
records; no device contact, no build.

  python3 -B tools/host-lisp/rc240_device_seal.py write   # once; immutable
  python3 -B tools/host-lisp/rc240_device_seal.py check   # recompute and compare
"""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SESSION = ROOT / 'build/rc240-device-r1'
OUT = ROOT / 'tests/bytecode/dialect-v2/evidence/architecture-blocks/rc240-device-20260924.json'
REPORT = 'docs/planning/release-candidate-device-report-2026-09-24.md'
BINDING = 'docs/planning/release-candidate-device-plan-2026-09-24.md'
ELF = ('build/nested-error-recovery-final-r1/wplto/lisp65-c2-substitution-linked.prg.elf',
       '66165507a8e5ad1d857afdd967f9056be2ce7bbccc332d5328e981398078b47b')
MEDIUM = ('build/nested-error-recovery-seed-medium-r1/packed/hardware-sp-seed.d81',
          '87cb0f6ea9b2dc690f66ee11d9c76d5138e11f28452254a9b5730c78cabc5f5d')
TOOLS = {'tools/m65tools/m65': '158c932c07a82771704c86e8ee79700c992e150fe0cd64b2ba99b10071233bc4',
         'tools/m65tools/mega65_ftp': 'd39a7fe880d3037a1b57ecfc84aed14fd7f931e6fe05d57392cce5ab2cac17c4'}
CALIBRATION = 'build/rc240-row-d-calibration-r3'
CALIBRATIONS = ['build/rc240-row-d-calibration-r1', 'build/rc240-row-d-calibration-r2', CALIBRATION]  # r1/r2: matcher faults, kept
HOST_GATE = [('build/nested-error-recovery-gates-overcap-g1', 'after-min-c2d.bin'),
             ('build/nested-error-recovery-gates-overcap-g1', 'after-refused-c2d.bin'),
             ('build/nested-error-recovery-gates-cumulative-g1', 'after-54-c2d.bin'),
             ('build/nested-error-recovery-gates-cumulative-g1', 'after-refused-c2d.bin')]
WORK_SHA = '1149e85926f707f6e48465d682d200bdd68346480d1bc10d52b0f8c3f3179021'


def bind(path):
    path = Path(path).resolve()
    raw = path.read_bytes()
    return dict(path=str(path.relative_to(ROOT)), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def receipt(rel):
    return json.loads((SESSION / rel / 'receipt.json').read_text())


def build():
    elf, medium = bind(ROOT / ELF[0]), bind(ROOT / MEDIUM[0])
    assert elf['sha256'] == ELF[1] and medium['sha256'] == MEDIUM[1]
    tools = [bind(ROOT / p) for p in TOOLS]
    assert all(t['sha256'] == TOOLS[t['path']] for t in tools)
    session = json.loads((SESSION / 'session.json').read_text())
    assert session['elf'] == elf and session['medium'] == medium and session['tools'] == tools
    assert bind(ROOT / session['plan']['path']) == session['plan']

    up = receipt('01-upload-01')
    assert up['status'] == 'PASS: RC240.D81 AND RC240W.D81 NEW, BYTE-IDENTICAL READBACK' and up['new_file_witnesses'] == 2
    rb = {Path(r['path']).name: r for r in up['readbacks']}
    assert rb['RC240-upload-readback.d81']['sha256'] == MEDIUM[1] and rb['RC240W-upload-readback.d81']['sha256'] == WORK_SHA
    assert bind(ROOT / up['work']['path'])['sha256'] == WORK_SHA

    a = receipt('A-boot-01'); ai = receipt('A-boot-inspect-01')
    run = a['steps'][-1]
    assert a['status'].startswith('HALT') and 'banner rows differ' in a['error'] and run['form'] == 'run'
    assert ai['stable'] and all(r['banner_equal'] and r['prompt'] == [24, ''] for r in ai['reads'])
    b = receipt('B-ordinary-01'); assert b['status'] == 'PASS' and len(b['rows']) == 9
    assert b['rows'][2]['observed_case'] == '"Abc"'
    c = receipt('C-typing-01')
    assert c['status'].startswith('HALT') and 'C-x C-c' in c['error']
    assert c['ide']['minibuffer_17_present'] and 'demo1234567890123' in c['ide']['status_typed']
    cr = receipt('C-exit-reset-01'); assert cr['status'] == 'PASS: NORMAL RESET, AUTOMATIC BOOT, SETTLED IDLE PROMPT'
    b2 = receipt('B2-reestablish-01'); assert b2['status'] == 'PASS'
    assert [r['observed_case'] for r in b2['rows']] == [r['observed_case'] for r in b['rows']]
    cl = receipt('C-repl-line-01'); assert cl['status'] == 'PASS' and cl['rows'][0]['observed'] == '28'
    d = receipt('D-storage-01'); assert d['status'].startswith('HALT') and 'storage census differs' in d['error']
    assert [r['observed'] for r in d['rows']] == ['T', '42', 'T', '42', 'T', '42']
    da, db = d['capture_before']['decoded'], d['capture_after']['decoded']
    for k in ('capture_before', 'capture_after'):
        cap = json.loads((ROOT / d[k]['receipt']['path']).read_text())
        assert cap['stop_ack'] and cap['resume_ack']
    assert (da['nsym'], db['nsym'], d['delta']) == (761, 822, dict(nsym=61, images=3, entries=54))
    cal = json.loads((ROOT / CALIBRATION / 'receipt.json').read_text())
    assert cal['status'] == 'CAPTURED: ROW D CALIBRATION' and cal['world']['ELF']['sha256'] == ELF[1]
    assert cal['world']['medium']['sha256'] == MEDIUM[1] and cal['device_contacts'] == cal['guest_memory_writes'] == 0
    keys = ('nsym', 'npool', 'images', 'entries', 'resolutions', 'roots')
    dev = [(x['nsym'], x['npool'], x['images']['used'], x['entries']['used'], x['resolutions']['used'], x['roots']['used']) for x in (da, db)]
    emu = [tuple(c[k] for k in keys) for c in cal['captures']]
    assert dev == emu, (dev, emu)
    e = receipt('E-retained-01'); f = receipt('F-nested-01'); g = receipt('G-overcap-01')
    assert e['status'] == f['status'] == 'PASS'
    assert [r['observed'] for r in e['rows']] == ['NIL', '7', '*** VM: BAD BYTECODE', '9']
    assert [r['observed'] for r in f['rows']] == ['*** UNDEFINED FUNCTION: CAPZZ', '9']
    assert g['status'].startswith('HALT') and 'images not 64/64' in g['error']
    assert g['rows'][0]['observed'] == '*** VM: OUT OF MEMORY' and len(g['rows']) == 1
    assert g['rows'][0]['after']['images'] == 63 and g['rows'][0]['after']['image_capacity'] == 64
    g2 = receipt('G-close-01'); assert g2['status'] == 'PASS' and g2['counts_at_start']['images'] == 63
    assert [r['observed'] for r in g2['rows']] == ['7', '9']
    host = [(ROOT / d / n).read_bytes()[12:14] for d, n in HOST_GATE]
    assert all(int.from_bytes(x, 'little') == 63 for x in host)
    i = receipt('I-final-reset-01')
    assert i['status'] == 'PASS: NORMAL RESET -> AUTOMATIC BOOT -> SETTLED IDLE PROMPT 8/64' and i['banner_rows_equal_emulator']

    files = sorted(p for p in SESSION.rglob('*') if p.is_file() and '__pycache__' not in p.parts)
    cal_files = []
    for cal_dir in CALIBRATIONS:
        cal_files += sorted(p for p in (ROOT / cal_dir).rglob('*') if p.is_file() and p.name != 'system-sd.img')
    inputs = [bind(p) for p in files] + [bind(p) for p in cal_files] + [bind(ROOT / 'docs/planning/nested-error-recovery-final-report.md'),
                                                                *[bind(ROOT / d / n) for d, n in HOST_GATE], elf, medium, *tools, bind(ROOT / BINDING), bind(ROOT / REPORT), bind(Path(__file__))]
    rows = dict(
        A=dict(verdict='PASS on stable-screen inspection; first comparison halted on a torn snapshot (kept)',
               run_to_initializing_seconds=run['run_to_initializing_first_seen_seconds'],
               run_to_initializing_bracket=run['run_to_initializing_bracket'],
               run_to_prompt_seconds=run['run_to_prompt_seconds'], run_to_prompt_bracket=run['run_to_prompt_bracket'],
               clock='tool clock, not stopwatch', images=a['counts']['images'], entries=a['counts']['entries'],
               prompt_row=24, emulator_prompt_row=9),
        B=dict(verdict='PASS', results=[r['observed_case'] for r in b['rows']],
               upper_bound_seconds=[r['return_to_result_seconds_upper_bound'] for r in b['rows']],
               images_after=b['rows'][-1]['after']['images'], entries_after=b['rows'][-1]['after']['entries']),
        C=dict(verdict='PASS: M-x, 17 characters, C-g and the 17-character REPL line; physical C-x C-c left to the owner',
               minibuffer=c['ide'], ide_exit_attempt=c['error'], repl_line=cl['rows'][0]['form'], repl_result=cl['rows'][0]['observed'],
               attribution='reviewer decision: tool limitation, not a product fault; src/c2_kernal_window.s drains hardware '
                           'queue code $03, code 3 reaches the IDE only as the RUN/STOP matrix edge; no earlier device report '
                           'records a physical C-x C-c exit (documented in docs/user-guide.md:458)',
               ide_left_by_normal_reset=dict(reset_to_initializing_seconds=cr['reset_to_initializing_seconds'],
                                             reset_to_settled_prompt_seconds=cr['reset_to_settled_prompt_seconds'],
                                             images=cr['counts']['images'])),
        B2=dict(verdict='PASS: bound row B forms replayed after the reset to re-establish the precondition of rows D-G',
                images_after=b2['rows'][-1]['after']['images'], entries_after=b2['rows'][-1]['after']['entries']),
        D=dict(verdict='PASS (calibrated): 822 symbols; first check halted against the uncalibrated Put-Kit 824',
               results=['t', '42', 't', '42', 't', '42'], before=da, after=db, delta=d['delta'],
               calibration=dict(receipt=bind(ROOT / CALIBRATION / 'receipt.json'), emulator=emu, device=dev,
                                decision='reviewer 2026-09-24: 824 copied from Put-Kit (other interned names); '
                                         'emulator replay of the exact device sequence decides; 822 = PASS')),
        E=dict(verdict='PASS', results=[r['observed_case'] for r in e['rows']],
               upper_bound_seconds=[r['return_to_result_seconds_upper_bound'] for r in e['rows']]),
        F=dict(verdict='PASS', results=[r['observed_case'] for r in f['rows']],
               upper_bound_seconds=[r['return_to_result_seconds_upper_bound'] for r in f['rows']]),
        G=dict(verdict='PASS (calibrated): exact OUT OF MEMORY at a live prompt, 63/64 images; first check halted against the uncalibrated 64/64',
               result=g['rows'][0]['observed_case'], seconds_upper=g['rows'][0]['return_to_result_seconds_upper_bound'],
               images_before=g['rows'][0]['before']['images'], images_after=g['rows'][0]['after']['images'],
               entries_after=g['rows'][0]['after']['entries'], close=[r['observed'] for r in g2['rows']],
               calibration_source='accepted nested-error-recovery Final report, gate 2: refusal at 63 images; '
                                  'host gate captures ' + ', '.join(d + '/' + n for d, n in HOST_GATE) + ' read 63'),
        H='NOT RUN: left to the owner (Freezer mount)',
        I=dict(verdict='PASS: normal reset -> automatic boot of the mounted RC240.D81 -> settled idle prompt',
               reset_to_initializing_seconds=i['reset_to_initializing_seconds'],
               reset_to_settled_prompt_seconds=i['reset_to_settled_prompt_seconds'],
               images=i['counts']['images'], entries=i['counts']['entries']))
    return dict(format='lisp65-rc240-device-v1', date='2026-09-24',
                status='PASS for rows A-G and I (D and G calibrated against host truth); row H and the listed owner rows left to the owner',
                reviewer_decisions='2026-09-24: row A stands on the settled inspection (first read = driver read fault); '
                                   'row C minibuffer PASS, C-x C-c a tool limitation; continue via normal reset; '
                                   'row D calibrated on the host emulator (822); row G calibrated to host gate 2 (63/64)',
                end_of_session_readback='not attempted: both normal resets auto-booted the mounted RC240.D81; '
                                        'BASIC at rest needs the owner; left to the owner',
                binding=BINDING + ' @ c4045372', product=dict(elf=elf, medium=medium, work=up['work'],
                                                           sd_names=['RC240.D81', 'RC240W.D81']),
                transfer=dict(readbacks=up['readbacks'], new_names_confirmed=2, existing_files_changed=0),
                rows=rows,
                device_state_at_end='lisp65 auto-booted by the final normal reset, idle prompt 8/64; no repair',
                left_to_owner=['RUN/STOP inside a running form', 'cold power cycle and stopwatch feel',
                               'physical C-x C-c exit from the IDE',
                               'row H Freezer mount of RC240W.D81', 'end-of-session SD readback from BASIC at rest'],
                claim_limits=['Automated virtual-keyboard input; no physical-keyboard fidelity',
                              'Timings from the tool clock only', 'No end-of-session SD readback',
                              'Rows after the reset run on a fresh boot with row B replayed',
                              'No release decision is derived'],
                product_ram_writes=0, f011_mmio_reads=0, stopped_captures=2, resets=dict(m65_normal=4, mega65_ftp_exit=2), cold_power_cycle=False,
                inputs=inputs)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('mode', choices=['write', 'check'])
    mode = ap.parse_args().mode
    value = build()
    text = json.dumps(value, indent=2) + '\n'
    if mode == 'write':
        with OUT.open('x') as f:
            f.write(text)
        print('WROTE', OUT.relative_to(ROOT), len(value['inputs']), 'inputs')
    else:
        assert OUT.read_text() == text, 'seal differs from recomputed evidence'
        print('CHECK PASS', OUT.relative_to(ROOT), len(value['inputs']), 'inputs;', value['status'])


if __name__ == '__main__':
    main()
