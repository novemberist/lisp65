#!/usr/bin/env python3
"""2.5.4 GC-stress session: dated successor WRAPPER of c254_gc_stress.py (committed, imported, never edited).

Why (run build/card-254-gc-r1, 2026-10-05, halted by the reviewer after 90 minutes): the committed driver is
not at fault in its transport or its breakpoint addresses -- two forced collections ran -- but
  1. its screen reading does not know how the Comfort REPL draws a long active line.  Continuation rows of
     an entry are indented by the width of the prompt (5 columns behind "L65> ", none behind the empty
     continuation prompt), and a cursor that stands ON a character is dumped as a one-cell markup tag
     ({$A8} = reverse "(", {home} = reverse "S").  screen_matches() joins the rows as they are, so the
     250-character oracles never match although the product shows exactly the expected text; and
  2. a step whose oracle does not match waits 7,200 s with the emulator running free (99 % CPU).
The 2.5.3 session met the same wall: its private copy (build/card-253-rows-final-r1/tools/gcs.py) added a
330 s limit and recorded LIMIT for return250, history10 and the two delete/refill scenarios.

What this wrapper changes, in memory only:
  * c254_gc_stress.screen_matches gets ONE more reading of the same screen for the same expected text:
    hanging indent removed, cursor tags decoded (a named tag is a one-cell wildcard, at most one).  The
    committed reading is tried first; scenario contracts, expected texts, heap validation, the forcing
    protocol and compare() are the committed ones, untouched.
  * a wall limit and a stall limit per scenario (SIGALRM): the driver's own abort path stops its emulator.
  * the Final role: SEAL_SHA / SOURCE_RUN of the committed file are None (set-after-seal); the sealed
    2.5.4 Final is supplied here, so world('lite') performs its full seal / identity check.

Usage (repository root; one emulator at a time)
  c254_gc_session_20261006.py selftest
  c254_gc_session_20261006.py run --role lite|v253 --scenario S --out build/DIR/S [--limit s] [--stall s]
  c254_gc_session_20261006.py summary build/DIR        (compare() where both roles ran; one summary.json)
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import sys
import time

sys.dont_write_bytecode = True
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/host-lisp'))
import c254_gc_stress as GS  # noqa: E402  (committed driver)

DRIVER_SHA = 'bda6e11d10e5fda0458db559c890ee719460b612ae23e1e1852396dd05e3564c'      # c254_gc_stress.py as wrapped
FINAL_SEAL_SHA = '7b70c025ef66de595e1d2c050e6d65d54ed9d34243c807c8faf4618fda8e5603'  # build/card-254-final-r1/seal.json
FINAL_SOURCE_RUN = 'build/card-254-check-source-final-r1'
V253_SESSION = 'build/card-253-rows-r8'       # the 2.5.3 Seed r8 session (private limited driver), informational
CEILING = dict(live_cells=1070, arena_bytes=9344)      # c254_gc_stress.validate_snapshot
LIMITS = {'reopen-home-delete-refill250': 10800, 'history-home-delete-refill250': 10800}
DEFAULT_LIMIT, DEFAULT_STALL = 3600, 600
IDLE_WAIT = 300
FORMAT = 'card254-gc-session-v1'
_COMMITTED_MATCH = GS.screen_matches
CURSOR = '\x01'
ACTIVITY = dict(at=time.monotonic(), want=None, steps=0, second_reading=0)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class SessionLimit(BaseException):
    """Raised from the alarm handler; BaseException so that the driver's own abort path runs."""


# ------------------------------------------------------------------ screen reading
def _cells(line):
    """One screen row as cells.  {$A0} = cursor on a blank (CURSOR); {$XX} with a letter / ASCII screen code = that
    character in reverse video (the cursor stands on it); any other tag = one unknown cell ('\\0')."""
    out, i = [], 0
    for m in re.finditer(r'\{([^{}]*)\}', line):
        out.extend(line[i:m.start()])
        tag = m.group(1)
        if len(tag) == 1:
            out.append(tag)                       # dump markup of a plain character, e.g. {L}
        elif tag.upper() == '$A0':
            out.append(CURSOR)                    # cursor on a blank cell: kept, it fixes the end of the entry
        elif re.fullmatch(r'\$[0-9A-Fa-f]{2}', tag):
            code = int(tag[1:], 16) & 0x7F
            out.append(chr(code + 64) if 1 <= code <= 26 else (chr(code) if 32 <= code <= 63 else '\0'))
        else:
            out.append('\0')
        i = m.end()
    out.extend(line[i:])
    return ''.join(out).upper().rstrip(' ')


def second_reading(screen, want):
    """The expected text ends the screen when continuation rows lose their hanging indent (the width of the
    prompt on the entry's first row) and cursor tags are read as cells.  At most one unknown cell."""
    rows = [_cells(x) for x in screen.split('\n')]
    while rows and rows[-1] == '':
        rows.pop()
    want = want.upper()
    if not rows or not want:
        return False
    if want != want.rstrip(' ') and not rows[-1].endswith(CURSOR):
        return False                              # trailing blanks are only readable in front of the cursor
    for indent in (5, 0):
        flat = ''
        for k in range(len(rows) - 1, -1, -1):
            row = rows[k]
            if indent and k and row.startswith(' ' * indent):
                flat = row[indent:] + flat          # continuation row of the entry: drop the hanging indent
                continue
            flat = row + flat
            if indent or len(flat) >= len(want):    # indent: this was the entry's first row; none: enough cells
                break
        # A cursor on a blank cell at the very end marks where the entry ends: blanks in front of it belong to
        # the entry (an expected text may end in a space: "(STRING-LENGTH " -- run card-254-gc-r2, refill-15).
        flat = flat[:-1] if flat.endswith(CURSOR) else flat
        flat = flat.replace(CURSOR, ' ')
        if len(flat) < len(want):
            continue
        tail = flat[-len(want):]
        if tail.count('\0') <= 1 and all(a == b or a == '\0' for a, b in zip(tail, want)):
            return True
    return False


def screen_matches(screen, want):
    """Committed reading first; the second reading only for the driver's last case (text that ends the screen)."""
    if want != ACTIVITY['want']:
        ACTIVITY.update(want=want, at=time.monotonic(), steps=ACTIVITY['steps'] + 1)
    if _COMMITTED_MATCH(screen, want):
        return True
    if want in ('@empty', 'L65>') or want.isdigit() or want.startswith(('=', '*** ')):
        return False
    if second_reading(screen, want):
        ACTIVITY['second_reading'] += 1
        return True
    return False


def install():
    assert sha(GS.__file__) == DRIVER_SHA, 'c254_gc_stress.py is not the wrapped driver'
    GS.SEAL_SHA, GS.SOURCE_RUN = FINAL_SEAL_SHA, FINAL_SOURCE_RUN
    GS.screen_matches = screen_matches


# ------------------------------------------------------------------ one scenario
def figures(row):
    after = [c['after'] for c in row.get('collections', [])]
    before = [c['before'] for c in row.get('collections', [])]
    return dict(collections=len(after), transitions_done=len(row.get('events', [])),
                transitions_total=len(row['scenario_contract']['steps']) if 'scenario_contract' in row else None,
                peak_live_cells=max((a['live_cells'] for a in after), default=None),
                peak_arena_bytes=max((a['arena_bytes'] for a in after), default=None),
                peak_root_slots=max((b['root_slots'] for b in before), default=None),
                mem_oom_ever_set=any(a['mem_oom'] for a in after + before),
                gc_cycles_max=max((c['cycles'] for c in row.get('collections', [])), default=None))


def run(role, scenario, out, limit, stall):
    install()
    import c254_emulator as E
    # House rule: no sealed run / producer / other emulator.  The emulator of the scenario before this one may
    # still be exiting (run card-254-gc-r2: the scenario after a STALL was refused): wait for it, bounded.
    waited = time.monotonic()
    while True:
        try:
            E.idle()
            break
        except ValueError as exc:
            if 'emulator of this checkout' not in str(exc) or time.monotonic() - waited > IDLE_WAIT:
                raise
            time.sleep(5)
    target = (ROOT / out).resolve()
    assert target.is_relative_to(ROOT / 'build') and not target.exists(), 'output must be a new directory under build/'
    assert role != 'v253' or scenario in GS.PEAK_PHASE, 'v253 baseline only for scenarios with a comparison phase'
    progress, started = target / 'progress.json', time.monotonic()
    ACTIVITY.update(at=started, want=None, steps=0, second_reading=0)

    def tick(_signum, _frame):
        now = time.monotonic()
        last = ACTIVITY['at']
        if progress.exists():
            last = max(last, now - (time.time() - progress.stat().st_mtime))
        if now - started > limit:
            raise SessionLimit(f'LIMIT: wall limit {limit} s')
        if now - last > stall:
            raise SessionLimit(f'STALL: no new step and no collection for {stall} s')
    signal.signal(signal.SIGALRM, tick)
    signal.setitimer(signal.ITIMER_REAL, 15, 15)
    status, error, result = 'ERROR', None, None
    try:
        result = GS.run_case(role, scenario, target)
        status = result['status']
    except SessionLimit as exc:
        status, error = str(exc).split(':')[0], str(exc)
    except BaseException as exc:          # the driver wrote its receipt (status HALT) and stopped its emulator
        error = repr(exc)
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
    row = result
    if row is None and (target / 'receipt.json').is_file():
        row = json.loads((target / 'receipt.json').read_text())
    session = dict(format=FORMAT, role=role, scenario=scenario, status=status, error=error,
                   elapsed_s=round(time.monotonic() - started, 1), limit_s=limit, stall_s=stall,
                   screen_reading=dict(steps_seen=ACTIVITY['steps'], matches_by_second_reading=ACTIVITY['second_reading']),
                   wrapper=dict(path='tools/host-lisp/' + Path(__file__).name, sha256=sha(__file__)),
                   driver=dict(path='tools/host-lisp/c254_gc_stress.py', sha256=DRIVER_SHA),
                   medium=row.get('medium') if row else None, ELF=row.get('ELF') if row else None,
                   figures=figures(row) if row else None,
                   final=dict(seal_sha256=FINAL_SEAL_SHA, source_run=FINAL_SOURCE_RUN) if role == 'lite' else None,
                   stopped_in=None)
    if row and status != 'PASS':
        steps = row['scenario_contract']['steps']
        done = len(row.get('events', []))
        session['stopped_in'] = steps[done][0] if done < len(steps) else None
    if target.is_dir():
        (target / 'session.json').write_text(json.dumps(session, indent=1) + '\n')
    print(json.dumps(session, indent=1), flush=True)
    return 0 if status == 'PASS' else 2


# ------------------------------------------------------------------ comparison
def compare_receipts(a, b):
    """The committed compare() on two receipts, twice: as it is, and with its stimulus check made able to
    succeed.  compare() requires `receipt['scenario_contract'] == scenarios()[name]`; a receipt read from JSON
    holds the steps as lists, scenarios() as tuples, so the committed check refuses every real pair
    ('comparison stimuli differ').  The second call gives compare() the same contracts after a JSON round trip;
    every other requirement, including "no peak figure above the 2.5.3 Final", is the committed one."""
    from unittest.mock import patch
    out = dict(rule='PASS only if live_cells and arena_bytes peaks of the measured phase are <= the 2.5.3 Final')
    try:
        out['committed'] = GS.compare(a, b)
    except ValueError as exc:
        out['committed'] = dict(status='FAIL', error=str(exc))
    plain = json.loads(json.dumps(GS.scenarios()))
    try:
        with patch.object(GS, 'scenarios', lambda: plain):
            out['stimuli_normalised'] = GS.compare(a, b)
    except ValueError as exc:
        out['stimuli_normalised'] = dict(status='FAIL', error=str(exc))
    rows = list(zip(a['collections'], b['collections']))
    out['measured'] = dict(
        collections=[len(a['collections']), len(b['collections'])],
        stimuli_equal=a['scenario_contract'] == b['scenario_contract'],
        delta_at_every_collection={k: sorted({x['after'][k] - y['after'][k] for x, y in rows})
                                   for k in ('live_cells', 'arena_bytes', 'root_slots', 'frozen_cells')}
        if len(a['collections']) == len(b['collections']) else None,
        peak_v254={k: max(c['after'][k] for c in a['collections']) for k in ('live_cells', 'arena_bytes')},
        peak_v253={k: max(c['after'][k] for c in b['collections']) for k in ('live_cells', 'arena_bytes')})
    out['status'] = out['stimuli_normalised']['status']
    return out


# ------------------------------------------------------------------ summary
def summary(directory):
    install()
    base = (ROOT / directory).resolve()
    assert base.is_relative_to(ROOT / 'build')
    rows, comparisons = [], {}
    for name in GS.scenarios():
        entry = dict(scenario=name)
        # the latest attempt counts: <dir>/<scenario>, then <dir>/rerun-N/<scenario>; earlier ones are listed
        attempts = [q for q in [base / name] + sorted(base.glob(f'rerun-*/{name}')) if (q / 'session.json').is_file()]
        here = attempts[-1] if attempts else base / name
        path = here / 'session.json'
        if not path.is_file():
            entry.update(status='NOT RUN')
        else:
            s = json.loads(path.read_text())
            entry.update(status=s['status'], error=s['error'], elapsed_s=s['elapsed_s'], stopped_in=s['stopped_in'],
                         role=s['role'], medium_sha256=(s['medium'] or {}).get('sha256'), **(s['figures'] or {}),
                         matches_by_second_reading=s['screen_reading']['matches_by_second_reading'],
                         receipt=dict(name=str((here / 'receipt.json').relative_to(base)), sha256=sha(here / 'receipt.json')))
        old = ROOT / V253_SESSION / ('gc-' + name) / 'receipt.json'
        if old.is_file():
            o = json.loads(old.read_text())
            entry['v253_seed_r8_session'] = {k: o.get(k) for k in ('status', 'collections_done', 'peak_live_cells', 'peak_arena_bytes',
                                                                 'peak_root_slots', 'transitions_done', 'transitions_total', 'stopped_in')}
        a, b = here / 'receipt.json', base / 'v253' / name / 'receipt.json'
        if name in GS.PEAK_PHASE:
            try:
                comparisons[name] = compare_receipts(json.loads(a.read_text()), json.loads(b.read_text()))
            except (OSError, KeyError) as exc:
                comparisons[name] = dict(status='FAIL', error=repr(exc))
            entry['v253_final_r8_baseline'] = json.loads((base / 'v253' / name / 'session.json').read_text())['figures'] \
                if (base / 'v253' / name / 'session.json').is_file() else None
        if entry.get('peak_live_cells') is not None:
            entry['headroom'] = dict(live_cells=CEILING['live_cells'] - entry['peak_live_cells'],
                                     arena_bytes=CEILING['arena_bytes'] - entry['peak_arena_bytes'])
        if len(attempts) > 1:
            entry['earlier_attempts'] = [dict(dir=str(q.relative_to(base)), **{k: json.loads((q / 'session.json').read_text())[k]
                                         for k in ('status', 'error', 'stopped_in', 'elapsed_s')}) for q in attempts[:-1]]
        rows.append(entry)
    ok = all(r['status'] == 'PASS' and not r['mem_oom_ever_set'] for r in rows) and \
        all(c['status'] == 'PASS' for c in comparisons.values()) and set(comparisons) == set(GS.PEAK_PHASE)
    result = dict(format=FORMAT, gate='gc-session', status='PASS' if ok else 'FAIL', role='lite (sealed 2.5.4 Final)',
                  final=dict(dir=GS.FINAL, seal_sha256=FINAL_SEAL_SHA, source_run=FINAL_SOURCE_RUN,
                             medium_sha256=GS.D81_SHA, elf_sha256=GS.ELF_SHA),
                  wrapper=dict(path='tools/host-lisp/' + Path(__file__).name, sha256=sha(__file__)),
                  driver=dict(path='tools/host-lisp/c254_gc_stress.py', sha256=DRIVER_SHA),
                  ceiling=CEILING, scenarios=rows, comparison_with_v253_final=comparisons,
                  not_pass=[r['scenario'] for r in rows if r['status'] != 'PASS'] +
                           ['compare:' + k for k, v in comparisons.items() if v['status'] != 'PASS'],
                  claim='Forced collection at every allocation of each measured transition; emulator only, no natural-pause or device claim')
    (base / 'summary.json').write_text(json.dumps(result, indent=1) + '\n')
    print(json.dumps(dict(status=result['status'], scenarios={r['scenario']: r['status'] for r in rows},
                          comparison={k: v['status'] for k, v in comparisons.items()}), indent=1))
    return 0 if ok else 2


# ------------------------------------------------------------------ selftest (offline)
def selftest():
    log = []
    assert sha(GS.__file__) == DRIVER_SHA
    before = json.dumps(GS.scenarios(), sort_keys=True)
    install()
    assert json.dumps(GS.scenarios(), sort_keys=True) == before and GS.screen_matches is screen_matches
    log.append('scenario contracts and expected texts are the committed ones')
    base = GS.selftest()                          # the committed selftest still passes with the wrapper installed
    assert base['status'] == 'PASS'
    log.append('committed driver selftest passes under the wrapper (%d negative controls)' % len(base['negative_controls']))
    medium, elf = GS.world('lite')
    assert sha(medium) == GS.D81_SHA and sha(elf) == GS.ELF_SHA and medium.is_relative_to(ROOT / GS.FINAL)
    log.append('Final role resolves through the committed seal / identity check: ' + str(medium.relative_to(ROOT)))
    for bad in (dict(SEAL_SHA='0' * 64), dict(SOURCE_RUN='build/another-run')):
        saved = {k: getattr(GS, k) for k in bad}
        try:
            for k, v in bad.items():
                setattr(GS, k, v)
            try:
                GS.world('lite')
            except ValueError:
                pass
            else:
                raise AssertionError('wrong seal / source run admitted')
        finally:
            for k, v in saved.items():
                setattr(GS, k, v)
    log.append('wrong seal sha and wrong source run are refused')
    # screens as observed on the 2.5.4 Seed (build/card-254-gc-r2/explore/a) and in build/card-254-gc-r1
    text = GS.line250().upper()
    first, rest = text[:75], text[75:]
    hanging = '\n'.join(['OLD', 'L65> ' + first] + ['     ' + rest[i:i + 75] for i in range(0, len(rest), 75)])
    assert not _COMMITTED_MATCH(hanging + '{$A0}', text) and screen_matches(hanging + '{$A0}', text)
    log.append('250-character active line with a 5-column hanging indent')
    plain = '\n'.join(text[i:i + 80] for i in range(0, len(text), 80))
    assert screen_matches(plain, text) and ACTIVITY['second_reading'] >= 1
    assert screen_matches('L65> {$A8}' + first[1:] + '\n     ' + rest[:75], first + rest[:75])          # cursor on "("
    assert screen_matches('L65> {home}' + first[2:] + '\n     ' + rest[:75], first[1:] + rest[:75])     # cursor on "S"
    pend = '"' + 'A' * 249
    rows = [pend[i:i + 80] for i in range(0, 250, 80)]
    assert screen_matches('\n'.join(['{$A2}' + rows[0][1:]] + rows[1:]), pend)                           # continuation, cursor on the quote
    left = 'A' * 249
    rows = [left[i:i + 80] for i in range(0, 249, 80)]
    assert screen_matches('\n'.join(['{$81}' + rows[0][1:]] + rows[1:]), left)                          # after one Delete
    log.append('cursor on a character: {$XX} decoded, a named tag is one wildcard cell; continuation rows without indent')
    wrong = hanging.replace('A', 'B', 1)
    assert not screen_matches(wrong + '{$A0}', text)
    assert not screen_matches(hanging[:-3] + '{$A0}', text)                                              # text cut short
    assert not screen_matches('L65> {home}{home}' + first[3:] + '\n     ' + rest[:75], first[1:] + rest[:75])
    assert not screen_matches(hanging.replace('     A', '    A', 1) + '{$A0}', text)                    # another indent
    assert not screen_matches('232\nL65> STILL TYPING', '232') and screen_matches('232\nL65> {$A0}', '232')
    assert not screen_matches('L65> (STRING', '@empty') and not screen_matches('DEF\nL65>', 'DEF')
    log.append('negative controls: wrong character, short text, two unknown cells, other indent, committed prompt rules')
    old = 'L65> "AAAA\n\n'
    assert screen_matches(old + '(STRING-LENGTH {$A0}', '(STRING-LENGTH ') and not _COMMITTED_MATCH(old + '(STRING-LENGTH {$A0}', '(STRING-LENGTH ')
    assert not screen_matches(old + '(STRING-LENGTH{$A0}', '(STRING-LENGTH ')          # the space was not typed yet
    assert not screen_matches(old + '(STRING-LENGTH', '(STRING-LENGTH ')                # no cursor: trailing blank unreadable
    assert screen_matches(old + '(STRING-LENGTH{$A0}', '(STRING-LENGTH')
    log.append('expected text that ends in a blank is read in front of the cursor')
    receipt = lambda role, n: dict(status='PASS', role=role, scenario='return250', no_heap_exhaustion=True,   # noqa: E731
                                   scenario_contract=json.loads(json.dumps(GS.scenarios()['return250'])),
                                   medium=dict(sha256=GS.D81_SHA if role == 'lite' else GS.V253_D81_SHA),
                                   ELF=dict(sha256=GS.ELF_SHA if role == 'lite' else GS.V253_ELF_SHA),
                                   collections=[dict(phase='return-echo-scan-reader',
                                                     after=dict(live_cells=n, arena_bytes=100, root_slots=1, frozen_cells=0))])
    c = compare_receipts(receipt('lite', 100), receipt('v253', 100))
    assert c['committed']['status'] == 'FAIL' and 'stimuli differ' in c['committed']['error'] and c['status'] == 'PASS'
    c = compare_receipts(receipt('lite', 103), receipt('v253', 100))
    assert c['status'] == 'FAIL' and 'peak regression' in c['stimuli_normalised']['error'] and \
        c['measured']['delta_at_every_collection']['live_cells'] == [3]
    log.append('compare(): JSON receipts fail the committed stimulus check (tuple / list); with equal stimuli a higher peak still FAILS')
    raised = []
    def handler(_s, _f):
        raise SessionLimit('LIMIT: selftest')
    signal.signal(signal.SIGALRM, handler)
    signal.setitimer(signal.ITIMER_REAL, 0.05)
    try:
        time.sleep(2)
    except SessionLimit as exc:
        raised.append(str(exc))
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
    assert raised == ['LIMIT: selftest'] and not issubclass(SessionLimit, Exception)
    log.append('the alarm interrupts a blocked wait with a BaseException (the driver abort path)')
    return dict(status='PASS', checks=log, emulator_runs=0)


if __name__ == '__main__':
    assert __debug__, 'assertions required'
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest='mode', required=True)
    sub.add_parser('selftest')
    r = sub.add_parser('run')
    r.add_argument('--role', choices=['lite', 'v253'], required=True)
    r.add_argument('--scenario', choices=list(GS.scenarios()), required=True)
    r.add_argument('--out', required=True)
    r.add_argument('--limit', type=int)
    r.add_argument('--stall', type=int, default=DEFAULT_STALL)
    s = sub.add_parser('summary')
    s.add_argument('directory')
    a = p.parse_args()
    if a.mode == 'selftest':
        print(json.dumps(selftest(), indent=1))
    elif a.mode == 'run':
        sys.exit(run(a.role, a.scenario, a.out, a.limit or LIMITS.get(a.scenario, DEFAULT_LIMIT), a.stall))
    else:
        sys.exit(summary(a.directory))
