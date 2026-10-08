#!/usr/bin/env python3
"""2.5.5 emulator rows (c255_rows_20261006.json) and the unchanged 2.5.4 / 2.5.3 rows on the 2.5.5 Seed medium.

Successor of c254_rows.py, which stays byte-identical and is imported: its Session class (scratch below
build/, patient monitor transport, RUN/STOP stand-in), its screen readers and every 2.5.4 session are used
as they are.  Driver for c255_emulator.py modes `new` and `control`.  One headless Xemu per boot, strictly
sequential.  Nothing is built.

Sessions (`all` runs them in this order)
  l2        the 14 rows of group l2, three fresh boots:
              L2-plain  no RUN/STOP, no disk write
              L2-save   l2-save-buffer-left-by-switch (user disk, host readback of the final image)
              L2-stop   row stop-probe of the 2.5.4 table first, then the seven rows that abort the editor
            Every row starts with (set-symbol-value (quote ide-buffers) nil).  Never the boot of the e3 or
            seam groups (they are other sessions = other boots; the run asserts it).
            --rows ID[,ID...] runs only the named l2 rows (each in the boot of its group): the rerun of a finding.
  typing    row typing-key-cost: two boots (control = 2.5.4 Final medium, then the 2.5.5 Seed medium), the
            method of build/card-254-ide-typing-r1/keycost.py (ported here: PC breakpoints at TAKE and EMPTY,
            DWX cycle counter read while the CPU is stopped), verdict = c255_row_oracles.timing_verdict with
            the rule of the table.  The row measures; an earlier measurement is read only as a cross-check.
  repl, lib1, oom-rp1, e3, seam, disk-h, d703, reg-repl, reg-disk, reg-ide, reg-oom  (and reg-oom-b when named)
            the sessions of c254_rows.py, unchanged (the 2.5.4 rows are the regression of 2.5.5)

Status of an l2 row -- as in c254_rows.py there is NO automatic PASS for what the host could not derive
  FAIL        hang, the editor did not open / did not return, a HOST-EXECUTED check is not met, the abort was
              not taken, or (prefix rule) the buffers equal no host state for j-1 / j accepted keys
  UNREVIEWED  the row has a NOT-DERIVED check, a `host_first` item, or depends on the RUN/STOP stand-in
  PASS        every check was HOST-EXECUTED, nothing is in the review set, all met
  NOT RUN     stop-probe found no working RUN/STOP stand-in (rows of L2-stop)
Row typing-key-cost: PASS / FAIL by the rule; a point more than 15 % off the model gives UNREVIEWED.

Usage
  through c255_emulator.py (binds the world):  new <out-dir-under-build> --session NAME[,NAME...]|all
  directly (no world, no emulator):
    c255_rows.py plan | selftest
    c255_rows.py review <run-dir> --review FILE --out <new-dir-under-build>
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import statistics
import sys
import time


def _root():
    for p in Path(__file__).resolve().parents:
        if (p / '.git').exists():
            return p
    raise RuntimeError('repository root not found')


ROOT = _root()
TOOLS = ROOT / 'tools/host-lisp'
sys.path.insert(0, str(TOOLS))
import c254_rows as X4  # noqa: E402  (history: read, never edited)
import c255_row_oracles as ORA  # noqa: E402  (timing_verdict / points: pure functions)

X3, L, D, F = X4.X3, X4.L, X4.D, X4.F
C, N = X4.C, X4.N
REVIEW, PASS, FAIL, NOT_RUN = X4.REVIEW, X4.PASS, X4.FAIL, X4.NOT_RUN
FORMAT = 'card255-rows-run-v1'
TABLE = TOOLS / 'c255_rows_20261006.json'
TABLE_SHA256 = 'a4b47d69c1a5e8e82c85b9e1c738520375122ee93f82d15e184cd64eda6711e5'
WRAPPED = {'c254_rows.py': '6e6afd493b3c537a9434fcd6fdcf2c59e4f6f79a0979b5807c6a8a4030aadff0',
           'c255_row_oracles.py': '0600e9c0d3f6946f1b18f9e907b89d5dd60ccb12857f1de26447c0b6504e19e3'}
# The worlds.  The table's typing row still names its seed world as a placeholder (path build/card-255-product-r1,
# hashes null); the Seed that exists is the continuation r1b, pinned here.
SEED = dict(name='build/card-255-product-r1b', medium='build/card-255-product-r1b/media-255/c255.d81',
            medium_sha='4f0b76ad395ed861da104960859b8d9416750a00684dd4826a1193b14245523b',
            elf='build/card-255-product-r1b/wplto/resident-island-seed.prg.elf',
            elf_sha='592b2c71c30901d2bb9599d2324678be5cd910865fbbfaf888c5d28ecb2e701f')
CONTROL = dict(name='build/card-254-final-r1', medium='build/card-254-final-r1/media-254/c254.d81',
               medium_sha='250fdc763ae9e5b04cf149a6f2a7a3aa9fb293ff8da58e9a703e0c601efaef5d',
               elf='build/card-254-final-r1/wplto/resident-island-seed.prg.elf',
               elf_sha='7b951eb9c92bc8797278903465b7483b3168a0eb935237a8f62ea3757f205244')
CROSS_CHECK = 'build/card-255-typing-measure-r1'      # earlier measurement of the same method (read only, optional)
STOP_TEXT = X4.STOP_LINE
EXIT_KEYS = [24, 113]
MHZ = 40.5e6


def sha(b):
    return hashlib.sha256(b).hexdigest()


# ----------------------------------------------------------------- table
_RAW = TABLE.read_bytes()
assert sha(_RAW) == TABLE_SHA256, 'row table drift: ' + str(TABLE.relative_to(ROOT)) + ' (a new table needs a new driver pin)'
for _name, _want in WRAPPED.items():
    assert sha((TOOLS / _name).read_bytes()) == _want, 'wrapped tool drift: ' + _name
DOC = json.loads(_RAW)
assert DOC['format'] == 'card255-rows-v1' and 'oracle' in DOC, 'the table is a draft (no oracle key)'
SPEC = {r['id']: r for r in DOC['rows']}
TYPING_ROW = 'typing-key-cost'
L2_ROWS = list(DOC['sessions']['l2'])
assert len(SPEC) == len(DOC['rows']) == 15 and DOC['sessions']['typing'] == [TYPING_ROW] and len(L2_ROWS) == 14
assert sorted(L2_ROWS + [TYPING_ROW]) == sorted(SPEC) and not SPEC.keys() & (X4.SPEC.keys() | X3.SPEC.keys()), 'row ids collide'
assert all(SPEC[i]['driver'] == 'l2' for i in L2_ROWS) and SPEC[TYPING_ROW]['driver'] == 'keycost'


def aborts(rowid):
    return any(s['end'] != 'exit' for s in SPEC[rowid]['expected']['script'])


def saves(rowid):
    return any(c['kind'] == 'saved-file' for c in SPEC[rowid]['expected']['checks'])


GROUPS = {'L2-plain': [i for i in L2_ROWS if not aborts(i) and not saves(i)],
          'L2-save': [i for i in L2_ROWS if not aborts(i) and saves(i)],
          'L2-stop': [i for i in L2_ROWS if aborts(i)]}
assert sorted(i for v in GROUPS.values() for i in v) == sorted(L2_ROWS)
for _row in (SPEC[i] for i in L2_ROWS):
    for _s in _row['expected']['script']:
        assert _s['end'] in ('exit', 'abort-idle') and (_s['end'] != 'exit' or _s['keys'][-2:] == EXIT_KEYS), ('script end', _row['id'])
        assert all(0 < k < 256 for k in _s['keys'])
PLAN = {'l2': L2_ROWS, 'typing': [TYPING_ROW], **X4.PLAN}
ORDER = ['l2', 'typing'] + list(X4.ORDER)
ROW_FILTER = []


def marks(row):
    """Every derivation mark of a 2.5.5 table row: (where, mark)."""
    exp = row['expected']
    out = [('checks[%d] %s' % (i, c['kind']), c['derivation']['mark']) for i, c in enumerate(exp.get('checks') or [])]
    out.append(('row', exp['derivation']['mark']))
    assert all(m in ('HOST-EXECUTED', 'NOT-DERIVED') for _, m in out), ('unmarked expectation', row['id'])
    return out


CENSUS = {m: sum(1 for i in L2_ROWS for _, x in marks(SPEC[i]) if x == m) for m in ('HOST-EXECUTED', 'NOT-DERIVED')}    # l2 rows, as the oracle receipt counts
assert CENSUS == DOC['oracle']['marks'], ('derivation census differs from the oracle receipt', CENSUS)


def review_reasons(rowid):
    """Why a row can never pass automatically (empty list = an automatic PASS is allowed)."""
    if rowid not in SPEC:
        return X4.review_reasons(rowid) if (rowid in X4.SPEC or rowid == X4.D703_ROW) else ['c253 status']
    row, why = SPEC[rowid], []
    if rowid == TYPING_ROW:
        return []           # status_rule of the table: the status is the verdict of the timing rule
    n = sum(1 for where, m in marks(row) if m == 'NOT-DERIVED' and where != 'row')
    if n:
        why.append('%d check(s) NOT-DERIVED on the host' % n)
    if row.get('host_first'):
        why.append('host_first: ' + '; '.join(row['host_first']))
    if aborts(rowid):
        why.append('depends on the RUN/STOP stand-in (monitor write to C2K_BREAK_PENDING), which only row stop-probe and a reviewer can accept')
    return why


REVIEW_SET = sorted(i for i in L2_ROWS if review_reasons(i))


def status_of(rowid, recs):
    """FAIL beats everything; a row of the review set is never PASS."""
    if any(r.get('ok') is False for r in recs):
        return FAIL
    return REVIEW if review_reasons(rowid) or any(r.get('ok') is None for r in recs) else PASS


def names_line(names):
    """What the product prints for (ide-buffers): a list of strings."""
    return '(' + ' '.join('"%s"' % n for n in names) + ')' if names else 'NIL'


def eval_slot(check, sessions):
    """After which script session a repl-value check runs (the table says it in words)."""
    word = check['after'].split()[0]
    return {'first': 0, 'second': 1, 'third': 2}.get(word, sessions - 1)


def prefix_verdict(states, shown, j_lo, j_hi):
    """Prefix rule of a burst abort.  states[m] = host state after m accepted keys; shown[m] = True / False / None
    (None = the screen cannot tell) for 'both buffers equal states[m]'.  Accepted: m in (j-1, j), j = the consumer
    counter read with the CPU paused at the STOP injection (j_lo).  The counter read after the abort (j_hi) widens
    the window only when it is higher: the product resets the counter on the way back to the prompt, so a lower
    value after the abort says nothing (first run of this driver: j_lo 11, j_hi 0)."""
    n = len(states) - 1
    wanted = [m for m in range(max(min(j_lo, n) - 1, 0), min(max(j_lo, j_hi), n) + 1)]
    fits = [m for m, v in enumerate(shown) if v is True]
    maybe = [m for m, v in enumerate(shown) if v is None]
    if set(fits) & set(wanted):
        return dict(verdict='OK', fits=fits, maybe=maybe, accepted=wanted)
    if set(maybe) & set(wanted):
        return dict(verdict='AMBIGUOUS', fits=fits, maybe=maybe, accepted=wanted)
    return dict(verdict='VIOLATION', fits=fits, maybe=maybe, accepted=wanted)


def apply_readback(row, files):
    """Fill the saved-file checks of a finished row from the host readback of the FINAL image of its boot and
    return the row's status.  files = {NAME bytes: content bytes}."""
    for rec in row['steps']:
        if rec.get('kind') != 'saved-file':
            continue
        got = files.get(rec['file'].upper().encode())
        want = rec['expected'].encode('latin1')
        rec.update(ok=got == want, present=got is not None, observed=None if got is None else got.decode('latin1'),
                   got_bytes=None if got is None else len(got), want_bytes=len(want),
                   got_sha256=None if got is None else sha(got), want_sha256=sha(want), readback='final image of the boot')
    if row['status'] not in (NOT_RUN,) and not row.get('halt'):
        row['status'] = status_of(row['id'], row['steps'])
    return row['status']


# ----------------------------------------------------------------- group l2
def gc_runs(S):
    b = S.m.memory_range(S.truth.symbol('gc_runs').value, 2)
    return b[0] | (b[1] << 8)


def body_text(view):
    """Text area of an editor screen as lines (trailing blank rows dropped; the cursor cell on a character is '?')."""
    rows = [r.replace('\0', '?') for r in view[0]]
    while rows and rows[-1] == '':
        rows.pop()
    return rows


def script_session(S, rid, i, sess, burst):
    name, keys, end = sess['ide'], list(sess['keys']), sess['end']
    shot0, s0 = X3.ide_enter(S, rid, name)
    rec = dict(row=rid, tag=f'script{i}', kind='script', input='(ide "%s") keys %r end=%s%s' % (name, keys, end, ' (one burst)' if burst else ''),
               mark='HOST-EXECUTED' if end == 'exit' else 'NOT-DERIVED', capture=end != 'exit',
               editor_opened=X4.in_editor(s0), screen=shot0, screens=[shot0])
    if not rec['editor_opened']:
        rec.update(ok=False, verdict='EDITOR-NOT-OPEN')
        return rec
    base, g0 = S.taken(), gc_runs(S)
    delta = lambda: (S.taken() - base) & 255                       # noqa: E731
    if end == 'exit':
        shot1, s1 = X3.ide_keys(S, rid, keys[:-2], f'script{i}-typed')
        view = X4.editor_view(s1)
        shot2, _s2, back = X3.ide_exit(S, rid)
        rec.update(ok=bool(back), back_at_prompt=bool(back), text_before_exit=body_text(view) if view else None,
                   collections=(gc_runs(S) - g0) & 0xFFFF, screen=shot2, screens=[shot0, shot1, shot2])
        return rec
    if burst:
        rec['burst'] = S.burst(keys)
        t0 = time.monotonic()
        while delta() < len(keys) and time.monotonic() - t0 < 60:
            pass
        rec['counted_at_target'] = delta()
        S.m.command('t1')               # CPU paused: counter, screen and the flag write describe ONE moment
        try:
            pre, j_lo = S.m.screen(), delta()
            inj = S.inject_stop(S.stop_method)
        finally:
            S.m.command('t0')
        shot1 = S.save_screen(f'{rid}-script{i}-at-stop', pre)
    else:
        shot1, pre = X3.ide_keys(S, rid, keys, f'script{i}-typed')         # settles: the editor is idle
        j_lo = delta()
        inj = S.inject_stop(S.stop_method)
    view = X4.editor_view(pre)
    s, ok = S.wait_for(X4.stopped, limit=30)
    j_hi = delta()
    shot2 = S.save_screen(f'{rid}-script{i}-stop', s)
    rec.update(injection=inj, aborted=ok, j_counter_at_stop=j_lo, j_counter_after_abort=j_hi, keys=len(keys),
               text_before_stop=body_text(view) if view else None, screen=shot2, screens=[shot0, shot1, shot2])
    if burst:
        rec['flush'] = S.flush_keys()
    rec['stopped_lines'] = X4.stop_reports(S.settle(secs=1.5, limit=30)[0]) if ok else 0
    if not ok:
        rec['cleared'] = S.clear_stop(S.stop_method)
        X3.ide_exit(S, rid)
    rec['prompt_cleanup'] = S.clean_prompt()
    rec.update(ok=None if ok else False, verdict='ABORTED' if ok else 'STOP-NOT-TAKEN',
               expected=STOP_TEXT, observed=(STOP_TEXT + ' x %d' % rec['stopped_lines']) if ok else None,
               matches_recorded=ok and rec['stopped_lines'] == 1, collections=(gc_runs(S) - g0) & 0xFFFF)
    return rec


def look(S, rid, name, tag):
    """(ide NAME), read the text area, C-x q."""
    shot, s = X3.ide_enter(S, rid, name)
    view = X4.editor_view(s) if X4.in_editor(s) else None
    shot2, _s2, back = X3.ide_exit(S, rid)
    return view, bool(back), [shot, shot2]


def l2_row(S, rid):
    row, exp = SPEC[rid], SPEC[rid]['expected']
    script, checks, burst = exp['script'], exp['checks'], bool(exp.get('prefix_rule'))
    recs = [S.step(rid, '(set-symbol-value (quote ide-buffers) nil)', 'NIL', tag='reset')]
    add = lambda rec: (S.steps_log.append(rec), recs.append(rec), rec)[2]          # noqa: E731

    def evals(slot):
        for k, c in enumerate(checks):
            if c['kind'] != 'repl-value' or eval_slot(c, len(script)) != slot:
                continue
            buffer = re.search(r'\(eval-buffer "([^"]+)"\)', c['after']).group(1)
            r = S.table_step(rid, '(eval-buffer "%s")' % buffer, [], mark='NOT-DERIVED', limit=900, tag=f'check{k}-eval')
            r.update(kind='eval-buffer', expected='(no error line)', observed='\n'.join(x for x in r['new_lines'] if x.strip()))
            recs.append(r)
            r = S.table_step(rid, c['input'], [c['text']], mark=c['derivation']['mark'], tag=f'check{k}-value')
            r.update(kind='repl-value', expected=c['text'], observed='\n'.join(x for x in r['new_lines'] if x.strip()))
            recs.append(r)

    last = None
    for i, sess in enumerate(script):
        last = add(script_session(S, rid, i, sess, burst and i == len(script) - 1))
        print(f'  {rid}: script {i} ({sess["ide"]}, {len(sess["keys"])} keys, {sess["end"]}) -> ok={last["ok"]}' + (' ' + last['verdict'] if last.get('verdict') else ''), flush=True)
        if last['ok'] is False:
            break
        evals(i)
    if last is not None and last['ok'] is not False:
        for k, c in enumerate(checks):
            if c['kind'] == 'saved-file':
                r = S.table_step(rid, '(save-buffer-to "%s" "%s")' % (c['file'], c['buffer']), ['T'], mark='NOT-DERIVED', limit=900, tag=f'check{k}-save')
                r.update(kind='save-result', expected='T', observed='\n'.join(x for x in r['new_lines'] if x.strip()))
                recs.append(r)
                r = S.table_step(rid, '(ide-error)', ['NIL'], mark='NOT-DERIVED', tag=f'check{k}-ide-error')
                r.update(kind='ide-error', expected='NIL', observed='\n'.join(x for x in r['new_lines'] if x.strip()))
                recs.append(r)
                try:
                    now = F.visible_files(X3.current(S)).get(c['file'].upper().encode())
                except Exception as exc:
                    now = repr(exc).encode()
                add(dict(row=rid, tag=f'check{k}-file', kind='saved-file', input='host readback of file %s' % c['file'].upper(), mark='HOST-EXECUTED',
                         capture=False, ok=None, pending='host readback of the final image of this boot', file=c['file'], buffer=c['buffer'],
                         expected=c['text'], observed=None, mid_session_observed=None if now is None else now.decode('latin1'),
                         screen=r['screen']))
        for k, c in enumerate(checks):
            if c['kind'] == 'buffer-names':
                r = S.table_step(rid, '(ide-buffers)', [names_line(c['names'])], mark=c['derivation']['mark'], tag=f'check{k}-names')
                r.update(kind='buffer-names', expected=names_line(c['names']).upper(), observed='\n'.join(x for x in r['new_lines'] if x.strip()))
                recs.append(r)
        if burst:
            states = exp['after_m_keys_of_last_session']
            names = sorted(states[-1]['buffers'])
            seen = {}
            for b in names:
                view, back, shots = look(S, rid, b, 'prefix')
                seen[b] = dict(view=view, back=back, shots=shots)
            shown = []
            for st in states:
                each = [X4.text_matches(seen[b]['view'], st['buffers'][b]['source']) if seen[b]['view'] else False for b in names]
                shown.append(False if any(v is False for v in each) else (None if any(v is None for v in each) else True))
            v = prefix_verdict(states, shown, last['j_counter_at_stop'], last['j_counter_after_abort'])
            add(dict(row=rid, tag='prefix-rule', kind='prefix-rule', input='re-enter %s, compare with the host states after m keys' % names,
                     mark='HOST-EXECUTED', capture=False, ok=True if v['verdict'] == 'OK' else (None if v['verdict'] == 'AMBIGUOUS' else False),
                     expected='both buffers equal the host state after m keys, m in %r' % v['accepted'],
                     observed={b: body_text(seen[b]['view']) if seen[b]['view'] else None for b in names},
                     back_at_prompt=all(seen[b]['back'] for b in names), screen=seen[names[-1]]['shots'][0],
                     screens=[x for b in names for x in seen[b]['shots']], **v))
            print(f'  {rid}: prefix rule j=[{last["j_counter_at_stop"]},{last["j_counter_after_abort"]}] fits={v["fits"]} -> {v["verdict"]}', flush=True)
        for k, c in enumerate(checks):
            if c['kind'] != 'reenter-screen':
                continue
            view, back, shots = look(S, rid, c['buffer'], f'check{k}')
            m = X4.text_matches(view, c['text']) if view else False
            add(dict(row=rid, tag=f'check{k}-reenter-{c["buffer"]}', kind='reenter-screen', input='(ide "%s") read C-x q' % c['buffer'],
                     mark=c['derivation']['mark'], capture=False, ok=(m if m is not True else True) if back else False, text_matches=m,
                     expected=c['text'], observed='\n'.join(body_text(view)) if view else None, cursor_row=view[1] if view else None,
                     back_at_prompt=back, screen=shots[0], screens=shots))
            print(f'  {rid}: re-enter {c["buffer"]} -> {recs[-1]["observed"]!r} match={m}', flush=True)
    st = status_of(rid, recs)
    extra = dict(group_note='saved-file checks are filled from the final image after the boot') if saves(rid) else {}
    if st == REVIEW:
        extra['review'] = dict(reasons=review_reasons(rid), captured_steps=sum(1 for r in recs if r.get('ok') is None),
                               all_captures_match_recorded=all(r.get('matches_recorded', True) for r in recs if r.get('ok') is None))
    return S.finish_row(rid, recs, extra=extra, status=st)


def selected(gname):
    return [i for i in GROUPS[gname] if not ROW_FILTER or i in ROW_FILTER]


def user_disk(S, sw, imgs):
    sw.swap('u1', imgs['u1'])
    S.run_expected('disk-remount-check', [('(m65d-remount)', '0'), ('(m65d-status)', '0')])


def g_plain(S, sw, imgs, res):
    for rid in selected('L2-plain'):
        l2_row(S, rid)


def g_save(S, sw, imgs, res):
    user_disk(S, sw, imgs)
    for rid in selected('L2-save'):
        l2_row(S, rid)


def g_stop(S, sw, imgs, res):
    assert not {r['id'] for r in S.rows} & (set(X4.SEAM_ROWS) | set(X4.E3_ROWS[1:])), 'l2 rows refused: this boot ran e3 / seam rows'
    user_disk(S, sw, imgs)
    method = X4.stop_probe(S)
    res['stop_method'] = method
    for rid in selected('L2-stop'):
        if method is None:
            S.finish_row(rid, [], status=NOT_RUN, extra=dict(reason='stop-probe found no RUN/STOP stand-in for the idle editor'))
        else:
            l2_row(S, rid)


def session_l2(out, holder):
    groups = [(g, fn) for g, fn in (('L2-plain', g_plain), ('L2-save', g_save), ('L2-stop', g_stop)) if selected(g)]
    result = X3.run_groups(out, 'l2', holder, groups)
    rows_file = out / 'l2-rows.json'
    rows = json.loads(rows_file.read_text()) if rows_file.exists() else []
    host = []
    for gname, _fn in groups:
        image = out / f'l2-{gname}-final.d81'
        try:
            files = F.visible_files(image.read_bytes())
        except Exception as exc:
            files, err = {}, repr(exc)
            host.append(dict(group=gname, error=err))
        for row in rows:
            if row.get('group') == gname and any(s.get('kind') == 'saved-file' for s in row['steps']):
                before = row['status']
                after = apply_readback(row, files)
                host += [dict(row=row['id'], group=gname, file=s['file'].upper(), ok=s['ok'], present=s['present'], got_bytes=s['got_bytes'],
                              want_bytes=s['want_bytes'], mid_session_equal=s['mid_session_observed'] == s['observed'])
                         for s in row['steps'] if s.get('kind') == 'saved-file']
                print(f'ROW {row["id"]} host readback -> {after} (was {before})', flush=True)
    rows_file.write_text(json.dumps(rows, indent=1) + '\n')
    result['host_checks'] = host
    holder.clear()
    return result


# ----------------------------------------------------------------- typing row (keycost method)
class OneConnection(L.R.ProbeMonitor):
    """One monitor connection for the whole measurement (keycost.py): the pinned Xemu writes an unsolicited register
    dump when a breakpoint fires and dies of SIGPIPE when no client is connected.  Never closed early, no resend."""
    END = b'\n.\r\n'

    def __init__(self, path):
        super().__init__(path)
        import socket
        self.client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.client.connect(str(path))
        self.pending = b''

    def command(self, command, timeout=180.0):
        self.client.settimeout(timeout)
        self.client.sendall(command.encode('ascii') + b'\r')
        while self.END not in self.pending:
            block = self.client.recv(16384)
            if not block:
                if command == '~exit':
                    break
                raise RuntimeError('monitor closed during ' + command)
            self.pending += block
        response, _, self.pending = self.pending.partition(self.END)
        return (response + self.END).decode('utf-8', errors='replace')


class KeyCost:
    """Port of build/card-254-ide-typing-r1/keycost.py (same breakpoints, same idle rule, same series)."""
    SCREEN, COLS, CUR, BLANK = 0x0800, 80, 0xA0, 0x20

    def __init__(self, S):
        self.S, self.samples, self.notes = S, [], {}
        self.EDIT, self.REPL = dict(name='editor'), dict(name='repl')
        S.m = OneConnection(S.run['sock'])
        self.gc_addr = S.truth.symbol('gc_runs').value
        poll, take = S.truth.symbol('c2_kernal_event_poll').value, S.truth.symbol('c2_kernal_input_take').value

        def at(addr, pattern, what):
            got = S.m.memory_range(addr, len(pattern))
            assert got == pattern, (what, got.hex())
            return addr
        self.EDIT.update(take=at(poll + 0x2C, bytes((0xEE, 0xFF, 0xBC)), 'editor take'), take_len=3,
                         empty=at(poll + 0x70, bytes((0xA9, 0x00, 0xA3, 0x00, 0x60)), 'editor empty'), empty_len=2)
        self.REPL.update(take=at(take + 0x35, bytes((0xEE, 0xFF, 0xBC, 0x60)), 'repl take'), take_len=3,
                         empty=at(take + 0x39, bytes((0xA9, 0x00, 0x60)), 'repl empty'), empty_len=2)
        self.notes['breakpoints'] = {w['name']: dict(take=hex(w['take']), empty=hex(w['empty'])) for w in (self.EDIT, self.REPL)}

    def pc(self):
        lines = [ln for ln in self.S.m.command('r').splitlines() if re.match(r'^[0-9A-F]{4} ', ln)]
        return int(lines[-1].split()[0], 16)

    def run_to(self, bp, length, limit=120):
        m = self.S.m
        m.command(f'b {bp:04x}')
        m.command('t0')
        t0 = time.monotonic()
        while time.monotonic() - t0 < limit:
            if self.pc() in (bp, bp + length):
                c1 = m.cycle_count()
                if m.cycle_count() == c1:
                    return c1
        raise RuntimeError('breakpoint %04x not reached' % bp)

    def release(self, secs=0.25):
        self.S.m.command('b ffff')
        self.S.m.command('t0')
        time.sleep(secs)

    def to_idle(self, W):
        hits = []
        while True:
            hits.append(self.run_to(W['empty'], W['empty_len']))
            if len(hits) >= 2 and hits[-1] - hits[-2] <= W['idle_gap']:
                return hits[-2], hits[:-2]
            assert len(hits) < 400, 'no idle wait found'

    def calibrate(self, W):
        self.release(1.0)
        c = [self.run_to(W['empty'], W['empty_len']) for _ in range(12)]
        d = [b - a for a, b in zip(c, c[1:])]
        W['idle_gap'] = int(max(d) * 1.5) + 50
        self.notes.setdefault('idle', {})[W['name']] = dict(median=statistics.median(d), min=min(d), max=max(d), idle_gap_rule=W['idle_gap'])

    def gc(self):
        b = self.S.m.memory_range(self.gc_addr, 2)
        return b[0] | (b[1] << 8)

    def cells(self, row, col, n=2):
        return list(self.S.m.memory_range(self.SCREEN + row * self.COLS + col, n))

    def ins_check(self, row, n):
        def check():
            b = self.cells(row, max(n - 1, 0))
            return b[0] not in (self.BLANK, self.CUR, 0) and b[1] == self.CUR
        return check

    def del_check(self, row, n):
        def check():
            b = self.cells(row, n - 1)
            return b[0] == self.CUR and b[1] in (self.BLANK, 0)
        return check

    def key(self, W, label, code, check, **meta):
        self.release()
        self.to_idle(W)
        g0 = self.gc()
        self.S.m.queue_one(code)
        c_inj = self.S.m.cycle_count()
        c_take = self.run_to(W['take'], W['take_len'])
        idle, polls = self.to_idle(W)
        rec = dict(label=label, code=code, cycles=idle - c_take, inject_to_take=c_take - c_inj,
                   empty_polls_before_idle=[p - c_take for p in polls], rendered=bool(check()), gc_runs=(self.gc() - g0) & 0xFFFF, **meta)
        rec['gc'] = rec['gc_runs'] > 0
        self.samples.append(rec)
        return rec

    def burst(self, W, label, row, start, count, code=ord('a'), **meta):
        m, skip = self.S.m, (self.BLANK, self.CUR, 0)
        self.release()
        self.to_idle(W)
        g0 = self.gc()
        m.command('~typehex ' + bytes([code] * count).hex())
        takes, filled = [], []
        for _ in range(count):
            takes.append(self.run_to(W['take'], W['take_len']))
            b = m.memory_range(self.SCREEN + row * self.COLS + start, count + 1)
            filled.append(sum(1 for x in b[:count] if x not in skip))
        idle, polls = self.to_idle(W)
        b = m.memory_range(self.SCREEN + row * self.COLS + start, count + 1)
        done = sum(1 for x in b[:count] if x not in skip)
        rec = dict(label=label, count=count, cycles=idle - takes[0], per_key=round((idle - takes[0]) / count),
                   take_gaps=[y - x for x, y in zip(takes, takes[1:])], filled_at_each_take=filled, filled_at_idle=done,
                   rendered=done == count and b[count] == self.CUR, render_states_seen=len(set(filled + [done]) - {0}),
                   last_take_to_idle=idle - takes[-1], gc_runs=(self.gc() - g0) & 0xFFFF, **meta)
        rec['gc'] = rec['gc_runs'] > 0
        self.samples.append(rec)
        return rec

    def typed(self, codes, done, limit=60):
        m = self.S.m
        m.command('b ffff')
        m.command('t0')
        for off in range(0, len(codes), 16):
            m.command('~typehex ' + bytes(codes[off:off + 16]).hex())
            t0 = time.monotonic()
            while 'DWX HWA input busy: 0' not in m.command('~typebusy'):
                assert time.monotonic() - t0 < limit
        t0 = time.monotonic()
        while not done():
            assert time.monotonic() - t0 < limit, 'unmeasured typing not rendered'
            time.sleep(0.05)

    def fill(self, row, col, count, code=ord('b')):
        if count > 0:
            self.typed([code] * count, self.ins_check(row, col + count))

    def erase(self, row, col, count):
        if count > 0:
            self.typed([20] * count, lambda: self.cells(row, col)[0] == self.CUR)

    def series(self, W, where, row, base, lengths, reps):
        have = 0
        for n in lengths:
            self.fill(row, base + have, (n - 1) - have)
            have = n - 1
            for r in range(reps):
                self.key(W, f'{where}-insert', ord('a'), self.ins_check(row, base + n), length=n, rep=r)
                self.key(W, f'{where}-backspace', 20, self.del_check(row, base + n), length=n, rep=r)
        return have

    def measure(self, reps=7):
        S, EDIT, REPL = self.S, self.EDIT, self.REPL
        scr = S.m.memory_range(self.SCREEN, self.COLS * 25)
        pos = scr.rfind(bytes((12, 54, 53, 62)))
        assert pos >= 0, 'l65> not found in screen RAM'
        prow, pcol = divmod(pos, self.COLS)
        base = pcol + 5
        self.calibrate(REPL)
        have = self.series(REPL, 'repl', prow, base, [1, 10, 20, 30], reps)
        self.erase(prow, base, have)
        self.release()
        S.step('prep', '(load-lib "ide")', 'T', limit=900, tag='ide')
        _shot, s0 = X3.ide_enter(S, 'tm', 'tm')
        assert X4.in_editor(s0), 'editor not open'
        time.sleep(1.0)
        self.calibrate(EDIT)
        have = self.series(EDIT, 'ide', 0, 0, [1, 10, 20, 30, 39], reps)
        self.erase(0, 0, have)
        for count in (8, 32):
            for r in range(reps):
                self.burst(EDIT, f'ide-burst{count}', 0, 0, count, rep=r)
                self.erase(0, 0, count)
        self.fill(0, 0, 30)
        for r in range(reps):
            self.key(EDIT, 'ide-return30', 13, lambda: self.cells(1, 0)[0] == self.CUR and self.cells(0, 30)[0] != self.CUR, length=30, rep=r)
            self.key(EDIT, 'ide-join30', 20, lambda: self.cells(0, 30)[0] == self.CUR, length=30, rep=r)
        self.erase(0, 0, 30)
        row = 0
        for target in (5, 20):
            while row < target - 1:
                nxt = row + 1
                self.typed([ord('b')] * 10 + [13], lambda: self.cells(nxt, 0)[0] == self.CUR)
                row = nxt
            self.fill(row, 0, 9)
            for r in range(reps):
                self.key(EDIT, f'ide-insert-line{target}', ord('a'), self.ins_check(row, 10), length=10, rep=r)
                self.key(EDIT, f'ide-backspace-line{target}', 20, self.del_check(row, 10), length=10, rep=r)
            self.erase(row, 0, 9)
        self.release(1.0)
        X3.ide_exit(S, 'tm')


def medians(samples):
    return {'%s@%s' % k: v['median'] for k, v in ORA.points(samples).items()}


def measure_world(out, tag, world):
    """One boot on a fresh copy of the world's medium; returns the keycost document (samples + notes)."""
    saved = dict(X4.WORLD)
    X4.WORLD.update(medium=ROOT / world['medium'], medium_sha=world['medium_sha'], elf=ROOT / world['elf'], elf_sha=world['elf_sha'])
    S, doc, t0 = X4.Session(out, 'typing-' + tag, writable=False, timeout=3000), None, time.monotonic()
    notes = dict(world=dict(world=tag, name=world['name'], medium=world['medium'], medium_sha=world['medium_sha'], elf_sha=world['elf_sha']))
    samples = []
    try:
        S.start()
        notes['boot'] = S.boot
        K = KeyCost(S)
        samples, notes2 = K.samples, K.notes
        try:
            K.measure()
        finally:
            notes.update(notes2)
    except BaseException:
        import traceback
        notes['error'] = traceback.format_exc()[-2500:]
        print(notes['error'], flush=True)
    finally:
        try:
            if S.run:
                S.m.command('b ffff')
                S.m.command('t0')
                notes['outputs'] = S.stop()
        except Exception as exc:
            notes['stop_error'] = repr(exc)
            S.abort()
        X4.drop_scratch()
        X4.WORLD.clear()
        X4.WORLD.update(saved)
        notes['wall_seconds'] = round(time.monotonic() - t0, 1)
        doc = dict(samples=samples, notes=notes)
        (out / f'typing-{tag}-results.json').write_text(json.dumps(doc, indent=1, default=str) + '\n')
    return doc


def typing_verdict(seed, control, rule):
    """Verdict of the row from two keycost documents (pure)."""
    errors = [w + ': ' + d['notes']['error'][-300:] for w, d in (('seed', seed), ('control', control)) if d['notes'].get('error')]
    if errors:
        return dict(status='FAIL', failed=['a measurement run recorded an error'], review=[], rules=[], errors=errors)
    return ORA.timing_verdict(seed['samples'], control['samples'], rule)


def session_typing(out, holder):
    assert X4.WORLD['label'] == 'seed', 'the typing row measures the Seed against the control; start it in mode new'
    exp = SPEC[TYPING_ROW]['expected']
    want = exp['worlds']['control']
    assert (want['medium'], want['medium_sha'], want['elf_sha']) == (CONTROL['medium'], CONTROL['medium_sha'], CONTROL['elf_sha']), 'control world differs from the table'
    control = measure_world(out, 'control', CONTROL)
    seed = measure_world(out, 'seed', SEED)
    verdict = typing_verdict(seed, control, exp['rule'])
    ms, mc = medians(seed['samples']), medians(control['samples'])
    table = {k: dict(control_cycles=mc.get(k), seed_cycles=ms.get(k), control_ms=round(mc[k] / MHZ * 1000, 1) if mc.get(k) else None,
                     seed_ms=round(ms[k] / MHZ * 1000, 1) if ms.get(k) else None,
                     ratio=round(ms[k] / mc[k], 4) if ms.get(k) and mc.get(k) else None,
                     predicted_cycles=exp['predicted_255_cycles'].get(k),
                     vs_model=round(ms[k] / exp['predicted_255_cycles'][k] - 1, 4) if ms.get(k) and exp['predicted_255_cycles'].get(k) else None)
             for k in sorted(set(ms) | set(mc))}
    cross = dict(source=CROSS_CHECK, note='earlier measurement with the same method; cross-check only, the row measured by itself')
    try:
        earlier = {w: json.loads((ROOT / CROSS_CHECK / d / 'results.json').read_text()) for w, d in (('seed', 'seed-a'), ('control', 'control-a'))}
        cross['inputs'] = [X4.bind_input(ROOT / CROSS_CHECK / d / 'results.json') for d in ('seed-a', 'control-a')]
        dev = {}
        for w, now in (('seed', ms), ('control', mc)):
            old = medians(earlier[w]['samples'])
            dev[w] = {k: round(now[k] / old[k] - 1, 5) for k in now if old.get(k) and now.get(k) and 'burst' not in k}
        cross.update(max_deviation={w: max((abs(v) for v in d.values()), default=None) for w, d in dev.items()}, deviation=dev)
    except Exception as exc:
        cross['unavailable'] = repr(exc)
    status = {'PASS': PASS, 'FAIL': FAIL, 'REVIEW': REVIEW}[verdict['status']]
    rec = dict(row=TYPING_ROW, tag='timing', input='keycost series on the control medium, then on the Seed medium', mark='NOT-DERIVED',
               capture=False, ok=verdict['status'] != 'FAIL' and (None if verdict['status'] == 'REVIEW' else True), verdict=verdict,
               screen=f'typing-seed-results.json', results=['typing-control-results.json', 'typing-seed-results.json'])
    row = dict(id=TYPING_ROW, status=status, steps=[rec], screens=[], points=table, cross_check=cross,
               worlds=dict(control=control['notes']['world'], seed=seed['notes']['world'],
                           table_seed_world=exp['worlds']['seed'], note='the table names the seed world as a placeholder; the driver pins Seed r1b'),
               boots=dict(control=control['notes'].get('boot'), seed=seed['notes'].get('boot')), rule_text=exp['rule_text'])
    (out / 'typing-rows.json').write_text(json.dumps([row], indent=1, default=str) + '\n')
    print(f'ROW {TYPING_ROW} {status}  failed={verdict["failed"]} review={verdict["review"]}', flush=True)
    for k in ('ide-insert@1', 'ide-insert@20', 'ide-insert@39', 'ide-backspace@20', 'ide-return30@30', 'ide-join30@30'):
        print('  ', k, table.get(k), flush=True)
    return dict(verdict=verdict['status'], failed=verdict['failed'], review=verdict['review'])


SESSIONS = {'l2': session_l2, 'typing': session_typing, **X4.SESSIONS}
assert list(SESSIONS) == ORDER
EXTRA_SESSIONS = dict(X4.EXTRA_SESSIONS)


# ----------------------------------------------------------------- receipts
def tool_inputs():
    names = ['c255_rows.py', 'c255_emulator.py', 'c255_rows_20261006.json', 'c255_row_oracles.py']
    return [X4.bind_input(TOOLS / n) for n in names if (TOOLS / n).is_file()] + X4.tool_inputs()


def verdict_of(statuses, errors):
    return X4.verdict_of(statuses, errors)


def run(a):
    W = X4.WORLD
    assert W.get('medium') and W.get('label'), 'no world bound: start through c255_emulator.py new'
    X4.KEEP_SCRATCH = a.keep_scratch
    names = ORDER if a.session == 'all' else a.session.split(',')
    known = {**SESSIONS, **EXTRA_SESSIONS}
    assert names and all(n in known for n in names) and len(set(names)) == len(names), ('unknown or repeated session', names)
    X3.GROUP_FILTER.clear()
    X3.GROUP_FILTER.extend([g for g in a.groups.split(',') if g])
    assert not X3.GROUP_FILTER or len(names) == 1 and names[0] in ('reg-disk', 'reg-ide'), '--groups needs exactly one of reg-disk / reg-ide'
    ROW_FILTER.clear()
    ROW_FILTER.extend([r for r in a.rows.split(',') if r])
    assert not ROW_FILTER or (names == ['l2'] and set(ROW_FILTER) <= set(L2_ROWS)), '--rows needs --session l2 and l2 row ids'
    out = ROOT / 'build' / a.out
    assert out.parent.is_relative_to(ROOT / 'build') and not out.name.startswith(X4.SCRATCH_PREFIX)
    out.mkdir(parents=True, exist_ok=False)
    inputs = dict(medium=X4.bind_input(W['medium']), ELF=X4.bind_input(W['elf']), xemu=X4.bind_input(L.XEMU), rom=X4.bind_input(X3.ROM),
                  table=X4.bind_input(TABLE), table_254=X4.bind_input(X4.TABLE), tools=tool_inputs(),
                  sd_image=dict(name=str(X3.SDIMG), bytes=X3.SDIMG.stat().st_size, note='not hashed (system SD image; each boot uses a copy)'))
    assert inputs['medium']['sha256'] == W['medium_sha'] and inputs['ELF']['sha256'] == W['elf_sha']
    print(json.dumps(dict(format=FORMAT, world=W['label'], table_sha256=TABLE_SHA256, table_254_sha256=X4.TABLE_SHA256, sessions=names,
                          rows=ROW_FILTER or None, review_set=len(REVIEW_SET) + len(X4.REVIEW_SET)), indent=1), flush=True)
    summary, errors = dict(sessions={}), {}
    try:
        for nm in names:
            sub = out / nm
            sub.mkdir()
            holder, error, result, outputs = [], None, {}, None
            try:
                result = known[nm](sub, holder)
            except X3.ProductHang as exc:
                error = 'HALT ' + repr(exc)
                S = holder[0] if holder else None
                if S is not None:
                    S.finish_row(exc.rowid, [r for r in S.steps_log if r['row'] == exc.rowid], status=FAIL, extra=dict(halt=str(exc)))
                print('SESSION HALT', nm, error, flush=True)
            except Exception as exc:      # keep the partial evidence, then go on with the next session
                error = repr(exc)
                print('SESSION ERROR', nm, error, flush=True)
            finally:
                S = holder[0] if holder else None
                if S is not None:
                    try:
                        outputs = S.stop()
                    except Exception as exc:
                        outputs = dict(stop_error=repr(exc))
                        S.abort()
                X4.drop_scratch()
            # a group that did not finish is an error of the run (run card-254-rows-r1 lost five groups silently)
            lost = {g: v.get('error') or v.get('status') for g, v in ((result or {}).get('groups') or {}).items() if v.get('status') != 'DONE'}
            if lost:
                error = '; '.join(filter(None, [error, 'GROUPS NOT DONE ' + json.dumps(lost, sort_keys=True)]))
            bad_files = [h for h in (result or {}).get('host_checks') or [] if h.get('ok') is False or h.get('error')]
            if nm == 'l2' and any(h.get('error') for h in bad_files):
                error = '; '.join(filter(None, [error, 'HOST READBACK ' + json.dumps(bad_files, sort_keys=True)[:400]]))
            rows_file = sub / (f'{nm[4:]}-rows.json' if nm in ('reg-disk', 'reg-ide', 'reg-oom') else f'{nm}-rows.json')
            rows = json.loads(rows_file.read_text()) if rows_file.exists() else []
            statuses = X4.classify(rows)
            for rid in PLAN.get(nm, []):
                if nm != 'l2' or not ROW_FILTER or rid in ROW_FILTER:
                    statuses.setdefault(rid, NOT_RUN)
            entry = dict(error=error, rows=statuses, result=result, outputs=outputs)
            if S is not None:
                entry.update(boot=getattr(S, 'boot', None), counted_keys=S.counted_keys, blind_keys=S.blind_keys)
            if error:
                errors[nm] = error
            summary['sessions'][nm] = entry
            (sub / 'session.json').write_text(json.dumps(entry, indent=1, default=str) + '\n')
    finally:
        X4.drop_scratch()
    statuses = {k: v['rows'] for k, v in summary['sessions'].items()}
    boots = [dict(session=b['session'], xemu_pid=b['xemu_pid'], scratch=b['scratch'], exit_status=b['exit_status'],
                  rows=[r['id'] for r in b['rows']]) for b in X4.Session.boots]
    e3_boots = {b['scratch'] for b in boots if set(b['rows']) & set(X4.E3_ROWS[1:])}
    seam_boots = {b['scratch'] for b in boots if set(b['rows']) & set(X4.SEAM_ROWS)}
    l2_boots = {b['scratch'] for b in boots if set(b['rows']) & set(L2_ROWS)}
    assert not e3_boots & seam_boots and not l2_boots & (e3_boots | seam_boots), 'e3 / seam / l2 rows shared a boot'
    receipt = dict(format=FORMAT, world=W['label'], transport=X4.TRANSPORT, continues=a.continues or None, row_filter=ROW_FILTER or None,
                   inputs=inputs, sessions=statuses, errors=errors, boots=boots,
                   separate_boots=dict(e3=sorted(e3_boots), seam=sorted(seam_boots), l2=sorted(l2_boots), disjoint=True),
                   unreviewed={rid: review_reasons(rid) for per in statuses.values() for rid, st in per.items() if st == REVIEW},
                   counts={st: sum(1 for per in statuses.values() for v in per.values() if v == st)
                           for st in sorted({v for per in statuses.values() for v in per.values()})},
                   verdict='CONTROL RUN on the 2.5.4 Final (not a product verdict)' if W['label'] != 'seed' else verdict_of(statuses, errors),
                   written=sorted(str(p.relative_to(out)) for p in out.rglob('*') if p.is_file()),
                   note='`written` lists files of this run by name only; no file written by this tool is bound by hash')
    summary['receipt'] = 'receipt.json'
    own = [out] + [ROOT / 'build' / b['scratch'] for b in boots]
    bad = X4.self_bindings(receipt, own) + X4.self_bindings(summary, own)
    assert not bad, ('receipt binds a path this tool writes', bad[:5])
    (out / 'summary.json').write_text(json.dumps(summary, indent=1, default=str) + '\n')
    (out / 'receipt.json').write_text(json.dumps(receipt, indent=1) + '\n')
    print(json.dumps(dict(sessions=statuses, counts=receipt['counts'], verdict=receipt['verdict']), indent=1))
    return 1 if errors else (2 if receipt['verdict'] == 'FAIL' else 0)


# ----------------------------------------------------------------- plan / review / selftest
def plan():
    rows = [dict(session='l2', group=g, row=rid, automatic_pass_possible=not review_reasons(rid),
                 not_derived_checks=sum(1 for w, m in marks(SPEC[rid]) if m == 'NOT-DERIVED' and w != 'row'))
            for g, ids in GROUPS.items() for rid in ids]
    rows.append(dict(session='typing', row=TYPING_ROW, automatic_pass_possible=True, status_rule=SPEC[TYPING_ROW]['status_rule']))
    return dict(format=FORMAT, table=X4.bind_input(TABLE), sessions=ORDER, extra_sessions=sorted(EXTRA_SESSIONS),
                boots_per_session={'l2': 3, 'typing': 2, **{k: 1 for k in X4.PLAN}, 'reg-repl': 1, 'reg-disk': 8, 'reg-ide': 4, 'reg-oom': 1},
                rows_255=rows, review_set_255=REVIEW_SET, automatic_pass_possible_255=sorted(set(L2_ROWS) - set(REVIEW_SET)),
                census_255=CENSUS, regression=X4.plan(), worlds=dict(seed=SEED, control=CONTROL))


def review(a):
    """Reviewer decision on a finished run; FILE as in c254_rows.py review."""
    run_dir, out = (ROOT / a.run).resolve(), ROOT / 'build' / a.out
    assert run_dir.is_relative_to(ROOT / 'build') and (run_dir / 'receipt.json').is_file()
    doc = json.loads(Path(a.review).read_text())
    assert doc.get('reviewer') and doc.get('date') and isinstance(doc.get('rows'), dict)
    receipt = json.loads((run_dir / 'receipt.json').read_text())
    assert receipt['format'] == FORMAT and receipt['world'] == 'seed', 'only a Seed-world run can be reviewed'
    final, unknown = {}, set(doc['rows'])
    for _nm, per in receipt['sessions'].items():
        for rid, st in per.items():
            d = doc['rows'].get(rid)
            unknown.discard(rid)
            if d is None or st != REVIEW:
                assert d is None, ('decision on a row that is not UNREVIEWED', rid, st)
                final[rid] = st
                continue
            assert d.get('verdict') in ('ACCEPT', 'REJECT') and d.get('note'), ('decision needs verdict and note', rid)
            final[rid] = PASS if d['verdict'] == 'ACCEPT' else FAIL
    assert not unknown, ('decision on unknown rows', sorted(unknown))
    out.mkdir(parents=True, exist_ok=False)
    result = dict(format='card255-rows-review-v1', run=dict(name=str(run_dir.relative_to(ROOT)), receipt_sha256=sha((run_dir / 'receipt.json').read_bytes())),
                  reviewer=doc['reviewer'], date=doc['date'], decisions=doc['rows'], rows=final,
                  still_unreviewed=sorted(r for r, s in final.items() if s == REVIEW), verdict=verdict_of(dict(all=final), receipt['errors']))
    (out / 'reviewed.json').write_text(json.dumps(result, indent=1) + '\n')
    return result


def selftest():
    log = []
    # 1. the wrapped 2.5.4 driver passes its own selftest (review policy, E3 rule, screen reading, patient transport)
    base = X4.selftest()
    assert base['status'] == 'PASS' and X4._MONITOR.command is X4.patient_command
    log.append('c254_rows.py selftest PASS (%d checks), patient transport installed' % len(base['checks']))
    # 2. review policy of the l2 rows
    for rid in L2_ROWS:
        assert (status_of(rid, [dict(ok=True)]) == PASS) == (rid not in REVIEW_SET), rid
        assert status_of(rid, [dict(ok=True), dict(ok=False)]) == FAIL
        assert status_of(rid, [dict(ok=None, matches_recorded=True)]) == REVIEW
    assert all(i in REVIEW_SET for i in L2_ROWS if aborts(i) or SPEC[i].get('host_first'))
    auto = sorted(set(L2_ROWS) - set(REVIEW_SET))
    assert auto == ['l2-return-backspace-exit', 'l2-switch-back-and-forth', 'l2-two-buffers-switch-exit', 'l2-type-exit-reenter'], auto
    log.append('review policy: %d of 14 l2 rows can never pass automatically; a capture step never passes; FAIL wins; automatic: %s'
               % (len(REVIEW_SET), ', '.join(auto)))
    # 3. census and groups
    assert CENSUS == {'HOST-EXECUTED': 36, 'NOT-DERIVED': 12}
    assert [len(GROUPS[g]) for g in ('L2-plain', 'L2-save', 'L2-stop')] == [6, 1, 7]
    assert all(SPEC[i].get('status_rule') for i in GROUPS['L2-stop']) and 'l2-save-after-abort' in GROUPS['L2-stop']
    assert not set(L2_ROWS) & (set(X4.E3_ROWS) | set(X4.SEAM_ROWS)) and 'l2' not in X4.PLAN and ORDER[:2] == ['l2', 'typing']
    assert SPEC[TYPING_ROW]['expected']['derivation']['mark'] == 'NOT-DERIVED'
    log.append('census 36 HOST-EXECUTED / 12 NOT-DERIVED in the l2 rows as in the oracle receipt (the typing row is one more NOT-DERIVED); groups 6 / 1 / 7; abort rows only in the boot that ran stop-probe; e3 and seam are other sessions')
    # 4. script reading
    assert names_line(['two', 'one']) == '("two" "one")' and names_line([]) == 'NIL'
    ev = [c for c in SPEC['l2-eval-buffer-after-edits']['expected']['checks'] if c['kind'] == 'repl-value']
    assert sorted((eval_slot(c, 2), c['text']) for c in ev) == [(0, '42'), (1, '43')]
    ab = [c for c in SPEC['l2-eval-buffer-after-abort']['expected']['checks'] if c['kind'] == 'repl-value']
    assert [(eval_slot(c, 2), c['text']) for c in ab] == [(1, '6')]
    log.append('script reading: buffer-name line, eval-buffer checks placed after the session the table names')
    # 5. prefix rule
    st = SPEC['l2-abort-mid-burst-after-switch']['expected']['after_m_keys_of_last_session']
    assert len(st) == 12
    one = lambda m: [i == m for i in range(12)]                    # noqa: E731
    assert prefix_verdict(st, one(11), 11, 11)['verdict'] == 'OK' and prefix_verdict(st, one(10), 11, 11)['verdict'] == 'OK'
    assert prefix_verdict(st, one(9), 11, 11)['verdict'] == 'VIOLATION' and prefix_verdict(st, [False] * 12, 5, 6)['verdict'] == 'VIOLATION'
    assert prefix_verdict(st, one(7), 7, 9)['accepted'] == [6, 7, 8, 9] and prefix_verdict(st, one(5), 7, 9)['verdict'] == 'VIOLATION'
    assert prefix_verdict(st, [None if i == 10 else False for i in range(12)], 11, 11)['verdict'] == 'AMBIGUOUS'
    assert prefix_verdict(st, one(11), 11, 0)['verdict'] == 'OK' and prefix_verdict(st, one(11), 11, 0)['accepted'] == [10, 11]
    assert prefix_verdict(st, one(9), 11, 0)['verdict'] == 'VIOLATION'
    log.append('prefix rule: j-1 / j accepted, fewer = VIOLATION, nothing shown = VIOLATION, unreadable = AMBIGUOUS')
    # 6. saved-file readback decides the row
    def saved_row(rid):
        return dict(id=rid, status=REVIEW, steps=[dict(ok=None, kind='save-result', matches_recorded=True),
                                                  dict(ok=None, kind='saved-file', file='l2one', expected='alpha\ngamma', mid_session_observed=None)])
    assert apply_readback(saved_row('l2-save-buffer-left-by-switch'), {b'L2ONE': b'alpha\ngamma'}) == REVIEW
    assert apply_readback(saved_row('l2-save-buffer-left-by-switch'), {b'L2ONE': b'alpha'}) == FAIL
    assert apply_readback(saved_row('l2-save-buffer-left-by-switch'), {}) == FAIL
    log.append('saved-file: byte-identical file keeps the row UNREVIEWED (device return value), a shorter or missing file = FAIL')
    # 7. editor text reading on the shapes the l2 rows produce
    def ide(lines, status='-- ONE * {L}1 -- 693/1008'):
        return '\n'.join(lines + [''] * (24 - len(lines)) + [status])
    v = X4.editor_view(ide(['xy', '{$A0}']))
    assert X4.text_matches(v, 'xy\n') is True and X4.text_matches(v, 'xy') is False and body_text(v) == ['XY']
    v = X4.editor_view(ide(['ab', 'c', 'f{$A0}']))
    assert X4.text_matches(v, 'ab\nc\nf') is True and X4.text_matches(v, 'ab\nc') is False and body_text(v) == ['AB', 'C', 'F']
    log.append('editor text reading: trailing empty line, multi-line text, body text')
    # 8. typing rule: the negative controls of the oracle tool, the error path, and the worlds
    rule = SPEC[TYPING_ROW]['expected']['rule']
    neg = ORA.selftest(rule)
    assert typing_verdict(dict(samples=[], notes=dict(error='x')), dict(samples=[], notes={}), rule)['status'] == 'FAIL'
    assert typing_verdict(dict(samples=[], notes={}), dict(samples=[], notes={}), rule)['status'] == 'FAIL'
    log.append('typing rule: negative controls of c255_row_oracles.py (%s); a run with an error or without samples = FAIL'
               % (len(neg) if hasattr(neg, '__len__') else 'run'))
    for world, bound in ((SEED, 'complete.json'), (CONTROL, 'final-identity.json')):
        for key in ('medium', 'elf'):
            assert sha((ROOT / world[key]).read_bytes()) == world[key + '_sha'], ('world drift', world['name'], key)
    complete = json.loads((ROOT / SEED['name'] / 'complete.json').read_text())
    assert complete['medium']['sha256'] == SEED['medium_sha'] and complete['ELF']['sha256'] == SEED['elf_sha']
    identity = {r['role']: r['final'] for r in json.loads((ROOT / CONTROL['name'] / 'final-identity.json').read_text())['artifacts']}
    assert identity['D81']['sha256'] == CONTROL['medium_sha'] and identity['ELF']['sha256'] == CONTROL['elf_sha']
    want = SPEC[TYPING_ROW]['expected']['worlds']
    assert want['control']['medium_sha'] == CONTROL['medium_sha'] and want['control']['elf_sha'] == CONTROL['elf_sha']
    log.append('worlds: Seed r1b bound by its complete.json, control = 2.5.4 Final by final-identity.json and by the table; '
               'table seed world is the placeholder %r (hashes %r)' % (want['seed']['medium'], want['seed']['medium_sha']))
    # 9. cross-check data, when present, gives the same verdict offline (informational: the row measures by itself)
    try:
        a, b = (json.loads((ROOT / CROSS_CHECK / d / 'results.json').read_text()) for d in ('seed-a', 'control-a'))
        v = typing_verdict(a, b, rule)
        log.append('cross-check %s offline: %s failed=%s review=%s' % (CROSS_CHECK, v['status'], v['failed'], v['review']))
    except OSError:
        log.append('cross-check %s: not present' % CROSS_CHECK)
    # 10. receipts bind no written path
    out = ROOT / 'build' / 'c255-selftest-never-created'
    assert X4.self_bindings(dict(a=[dict(path=str(out / 'x.txt'), sha256='0' * 64)]), [out]) == [str(out / 'x.txt')]
    assert X4.self_bindings(dict(inputs=dict(table=X4.bind_input(TABLE)), written=['l2/l2-rows.json']), [out]) == []
    log.append('receipt check: a {path, sha256} row below the output directory is refused; inputs and names are not')
    return dict(status='PASS', checks=log, emulator='NOT RUN (no emulator code path is exercised by this selftest)')


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest='mode', required=True)
    r = sub.add_parser('run')
    r.add_argument('out')
    r.add_argument('--session', default='all', help='all, or comma separated: ' + ', '.join(ORDER + list(EXTRA_SESSIONS)))
    r.add_argument('--groups', default='', help='reg-disk / reg-ide only: comma separated c253 group names')
    r.add_argument('--rows', default='', help='l2 only: comma separated l2 row ids')
    r.add_argument('--keep-scratch', action='store_true')
    r.add_argument('--continues', default='', help='name of the run this one continues (recorded in the receipt)')
    sub.add_parser('plan')
    sub.add_parser('selftest')
    v = sub.add_parser('review')
    v.add_argument('run')
    v.add_argument('--review', required=True)
    v.add_argument('--out', required=True)
    a = p.parse_args(argv)
    if a.mode == 'run':
        return run(a)
    print(json.dumps(dict(plan=plan, selftest=selftest, review=lambda: review(a))[a.mode](), indent=1, default=str))
    return 0


if __name__ == '__main__':
    sys.exit(main())
