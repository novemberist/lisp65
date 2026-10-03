#!/usr/bin/env python3
"""2.5.3 new emulator rows (c253_rows_20261001.json + r8 c253_rows_r8_20261003.json) on the pinned Seed medium.

Driver for c253_emulator.py mode `new`.  One headless Xemu per session, strictly
sequential, counted singleton key transport (comfort_default_rows.send_counted),
framebuffer and memory reads only.  Nothing is built.

Sessions
  repl  LCC / nth / macro rows and the pure-function IDE state rows (REPL command
        path; the product disk stays mounted, no disk write)
  disk  IDE save command path, eval-buffer, D2-D5; prepared user D81 images are
        swapped IN PLACE under the running emulator (the host overwrites the
        mounted image file, the equivalent of the Freezer disk swap of the
        2.5.2 device DISK row); host readback of every image after the session
  ide   IDE key path (edit, C-x C-w save, buffer switch, dirty edit cache)
  oom   r8: OOM recovery on the plain REPL (let-local garbage, then a global list that fills the heap);
        its own fresh boot so the full heap cannot leak into other rows

Usage (through c253_emulator.py):  new <out-dir-under-build> --session repl|disk|ide|all
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/host-lisp'))
import comfort_default_rows as D  # noqa: E402
import comfort_library_rows as L  # noqa: E402
import dwx_retroactive_red_replay as R  # noqa: E402
import d81_persistence_fault as F  # noqa: E402
import m65d_blank_d81_oracle as O  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402

WORLD = {}   # medium, medium_sha, elf, elf_sha (filled by c253_emulator.py)
ROWS_JSON = ROOT / 'tools/host-lisp/c253_rows_20261001.json'
ROWS_JSON_R8 = ROOT / 'tools/host-lisp/c253_rows_r8_20261003.json'   # r8 additions (F2/ladder/OOM), ids disjoint
C, N = L.C, L.N
ROM = Path(str(Path.home() / '.local/share/xemu-lgb/mega65/MEGA65.ROM'))
SDIMG = Path(str(Path.home() / '.local/share/xemu-lgb/mega65/mega65.img'))
SPEC = {r['id']: r for r in json.loads(ROWS_JSON.read_text())['rows']}
_R8DOC = json.loads(ROWS_JSON_R8.read_text())
_R8 = {r['id']: r for r in _R8DOC['rows']}
assert not SPEC.keys() & _R8.keys(), ('r8 row ids collide', sorted(SPEC.keys() & _R8.keys()))
SPEC.update(_R8)
# Corrected expected texts of r7-table rows (measured on Seed r8); each must replace exactly one entry whose
# old text is the recorded one, so a drifting r7 table cannot be silently overridden.
for _rid, _fixes in _R8DOC.get('expected_overrides', {}).get('rows', {}).items():
    for _fix in _fixes:
        _hits = [e for e in SPEC[_rid]['expected']['screen'] if e['input'] == _fix['input']]
        assert len(_hits) == 1 and _hits[0]['screen'] == _fix['was'], ('override seam', _rid, _fix['input'])
        _hits[0]['screen'] = _fix['screen']


def sha(b):
    return hashlib.sha256(b).hexdigest()


def upper_screen(s):
    return s.upper()


def expect(rowid):
    """host-derived (input, screen) pairs of a row, as fixed in the JSON."""
    return [(e['input'], e['screen']) for e in SPEC[rowid]['expected']['screen']]


class ProductHang(Exception):
    def __init__(self, rowid, rec):
        super().__init__(f'{rowid}: {rec.get("hang") or "timeout"} at {rec.get("input")!r}')
        self.rowid, self.rec = rowid, rec


# ----------------------------------------------------------------- session
class Session:
    def __init__(self, out: Path, name: str, writable=False, timeout=3000):
        self.out, self.name, self.writable, self.timeout = out, name, writable, timeout
        self.rows, self.steps_log, self.run = [], [], None
        self.seq = 0
        self.counted_keys = 0
        self.blind_keys = 0

    # -- life cycle
    def start(self):
        medium, medium_sha, elf = WORLD['medium'], WORLD['medium_sha'], WORLD['elf']
        assert R.bind(medium)['sha256'] == medium_sha, 'medium drift'
        assert R.bind(elf)['sha256'] == WORLD['elf_sha'], 'elf drift'
        assert R.bind(L.XEMU)['sha256'] == L.EXPECT['xemu'], 'xemu drift'
        self.truth = ElfTruth.read(elf, llvm_readobj=ROOT / 'tools/llvm-mos/bin/llvm-readobj')
        self.taken_addr = self.truth.symbol('C2K_INPUT_EVENTS_TAKEN').value
        run_dir = self.out / ('run-' + self.name)
        run_dir.mkdir()
        sd_copy = run_dir / 'system-sd.img'
        subprocess.run(['cp', '--reflink=auto', '--sparse=always', str(SDIMG), str(sd_copy)], check=True)
        self.medium_copy = run_dir / medium.name
        shutil.copyfile(medium, self.medium_copy)
        self.medium_copy.chmod(0o644 if self.writable else 0o444)
        memory, screen, log = run_dir / 'memory.bin', run_dir / 'framebuffer.txt', run_dir / 'xemu.log'
        sock = Path('/tmp') / f'l65-c253-{os.getpid()}-{self.name}.sock'
        sock.unlink(missing_ok=True)
        cmd = [str(R.SAFE_RUNNER), str(memory), str(self.timeout), str(L.XEMU),
               '-skipconfigfile', '-headless', '-testing', '-sleepless', '-besure', '-fastboot', '-nosound',
               '-rom', str(ROM), '-sdimg', str(sd_copy), '-8', str(self.medium_copy), '-autoload',
               '-uartmon', str(sock), '-dumpscreen', str(screen), '-dumpmem', str(memory)]
        self.log_handle = log.open('wb')
        self.proc = subprocess.Popen(cmd, stdout=self.log_handle, stderr=subprocess.STDOUT)
        self.run = dict(dir=run_dir, memory=memory, screen=screen, log=log, sock=sock)
        t_start = time.monotonic()
        deadline = time.monotonic() + 15
        while not sock.exists() and time.monotonic() < deadline:
            assert self.proc.poll() is None, 'Xemu exited before monitor'
            time.sleep(0.02)
        assert sock.exists(), 'UART monitor absent'
        self.m = R.ProbeMonitor(sock)
        last, since, cycles = None, time.monotonic(), None
        deadline = time.monotonic() + 300
        while time.monotonic() < deadline:
            s = self.m.screen()
            if s != last:
                last, since = s, time.monotonic()
                cycles = self.m.cycle_count() if L.active(s) in (N, C) else None
            if cycles is not None and time.monotonic() - since > 3:
                break
            time.sleep(0.05)
        self.m.command('t1')
        boot = self.m.screen()
        self.m.command('t0')
        self.boot = dict(active=L.active(boot), cycles_upper=cycles, wall_seconds=round(time.monotonic() - t_start, 1),
                         seconds_at_40_5MHz=round(cycles / 40.5e6, 2) if cycles else None)
        (self.out / f'{self.name}-boot.txt').write_text(boot)
        assert self.boot['active'] == C, 'boot did not reach l65>'
        return self.boot

    def stop(self):
        outputs = None
        try:
            if self.run:
                fb = self.m.screen()
                (self.run['dir'] / 'oracle-framebuffer.txt').write_text(fb)
                self.m.command('~exit')
                status = self.proc.wait(timeout=30)
                self.log_handle.close()
                self.run['sock'].unlink(missing_ok=True)
                outputs = dict(exit_status=status, framebuffer=R.bind(self.run['dir'] / 'oracle-framebuffer.txt'),
                               memory=R.bind(self.run['memory']) if self.run['memory'].exists() else None)
        finally:
            self.abort()
        return outputs

    def abort(self):
        p = getattr(self, 'proc', None)
        if p and p.poll() is None:
            p.terminate()
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                p.kill()
                p.wait(timeout=5)
        if getattr(self, 'log_handle', None) and not self.log_handle.closed:
            self.log_handle.close()
        if self.run:
            self.run['sock'].unlink(missing_ok=True)

    # -- low level
    def taken(self):
        return self.m.memory_range(self.taken_addr, 1)[0]

    def screen(self):
        return self.m.screen()

    def settle(self, secs=1.5, limit=240, cond=None):
        last, since, t0 = None, time.monotonic(), time.monotonic()
        while time.monotonic() - t0 < limit:
            s = self.m.screen()
            if s != last:
                last, since = s, time.monotonic()
            elif time.monotonic() - since > secs and (cond is None or cond(s)):
                return s, True
            time.sleep(0.05)
        return last, False

    def save_screen(self, tag, s):
        self.seq += 1
        p = self.out / f'{self.name}-{self.seq:03d}-{tag}.txt'
        p.write_text(s)
        return str(p.relative_to(ROOT))

    def key(self, code):
        """One singleton HWA event; acknowledged by the consumer counter when it moves."""
        before = self.taken()
        self.m.queue_one(code)
        t0 = time.monotonic()
        wait = 4 if (self.counted_keys or self.blind_keys < 2) else 0.3
        while time.monotonic() - t0 < wait:
            if (self.taken() - before) & 255:
                self.counted_keys += 1
                return
            time.sleep(0.02)
        self.blind_keys += 1
        time.sleep(0.6)

    def send_line(self, text, timeout=240):
        D.send_counted(self.m, [text.replace('\n', '\n')], self.taken_addr, timeout=timeout)

    # -- REPL step
    @staticmethod
    def segment(s, first_line):
        """Screen lines between the echo of the typed form and the active prompt line (None if the echo
        scrolled off).  Robust against identical result lines ("T") that difflib treats as unchanged."""
        ls = [x.replace('{$A0}', ' ').rstrip() for x in L.lines(s)]
        key = ('L65> ' + first_line).upper()[:20]
        for i in range(len(ls) - 2, -1, -1):
            if ls[i].startswith(key):
                return ls[i + 1:-1]
        return None

    def step(self, rowid, text, want, forbid=(), limit=300, tag=None, noerr=None):
        """Type one (possibly multi-line) form + Return; expect each `want` as a result line between the echo
        and the prompt (decoded, upper-cased) and the Comfort prompt back.  Raises ProductHang when the
        product stops taking input or loops on out-of-memory errors."""
        before = self.m.screen()
        t0 = time.monotonic()
        lines = text if isinstance(text, list) else [text]
        hang = None
        try:
            for ln in lines:
                self.send_line(ln + '\n', timeout=120)
        except Exception as exc:
            hang = 'input not consumed: ' + repr(exc)
        wants = [want] if isinstance(want, str) else list(want)
        wants_u = [w.upper() for w in wants]

        def view(s):
            seg = self.segment(s, lines[0])
            return seg if seg is not None else L.new_lines(before, s)

        last, since, deadline = None, time.monotonic(), time.monotonic() + limit
        s = before
        while hang is None and time.monotonic() < deadline:
            s = self.m.screen()
            if s != last:
                last, since = s, time.monotonic()
            if s.count('OUT OF MEMORY') >= 4 and L.active(s) != C:
                hang = 'OUT OF MEMORY repeated on screen, no prompt (error livelock)'
                break
            seg = view(s)
            good = L.active(s) == C and all(w in seg for w in wants_u)
            if good and time.monotonic() - since > 1.5:
                break
            if L.active(s) == C and time.monotonic() - since > 8:
                break
            time.sleep(0.1)
        timed_out = hang is None and time.monotonic() >= deadline
        s = self.m.screen() if hang else s
        got = view(s)
        if noerr is None:
            noerr = not wants_u
        ok = (hang is None and not timed_out and L.active(s) == C and all(w in got for w in wants_u)
              and not any(f.upper() in got for f in forbid)
              and not (noerr and any(x.startswith('*** ') for x in got)))
        shot = self.save_screen(f'{rowid}-{tag or "s"}', s)
        rec = dict(row=rowid, input=text, want=wants, forbid=list(forbid), ok=ok, timed_out=timed_out, hang=hang,
                   active=L.active(s), new_lines=got, screen=shot, seconds=round(time.monotonic() - t0, 1))
        self.steps_log.append(rec)
        print(f'  {rowid}: {"ok  " if ok else "FAIL"} {str(text)[:70]!r} -> {got[-3:]}', flush=True)
        if hang or timed_out:
            raise ProductHang(rowid, rec)
        return rec

    def finish_row(self, rowid, recs, extra=None, status=None):
        st = status or ('PASS' if all(r['ok'] for r in recs) else 'FAIL')
        row = dict(id=rowid, status=st, steps=recs, screens=[r['screen'] for r in recs], **(extra or {}))
        self.rows.append(row)
        print(f'ROW {rowid} {st}', flush=True)
        (self.out / f'{self.name}-rows.json').write_text(json.dumps(self.rows, indent=1) + '\n')
        return row

    def run_expected(self, rowid, pairs, forbid=(), limit=300):
        recs = [self.step(rowid, inp, scr, forbid=forbid, limit=limit, tag=f'{i:02d}') for i, (inp, scr) in enumerate(pairs)]
        return self.finish_row(rowid, recs)

    def oom_step(self, rowid, text, any_of, limit=900, tag=None):
        """r8 OOM recovery step.  ok = the input is consumed, the Comfort prompt comes back, and the result
        segment shows one of `any_of` (each a result line, e.g. '3' or '*** VM: OUT OF MEMORY').  Livelock =
        two or more OUT OF MEMORY reports in the segment of THIS input without the prompt (2.5.2/r7 symptom);
        unlike step(), earlier OOM reports elsewhere on the screen do not count (a genuine full heap
        legitimately reports once per input)."""
        before = self.m.screen()
        t0 = time.monotonic()
        hang = None
        try:
            self.send_line(text + '\n', timeout=120)
        except Exception as exc:
            hang = 'input not consumed: ' + repr(exc)
        alts = [a.upper() for a in any_of]

        def view(s):
            seg = self.segment(s, text)
            return seg if seg is not None else L.new_lines(before, s)
        last, since, deadline, s = None, time.monotonic(), time.monotonic() + limit, before
        while hang is None and time.monotonic() < deadline:
            s = self.m.screen()
            if s != last:
                last, since = s, time.monotonic()
            seg = view(s)
            if sum('OUT OF MEMORY' in x for x in seg) >= 2 and L.active(s) != C:
                hang = 'OUT OF MEMORY repeated for one input, no prompt (error livelock)'
                break
            if L.active(s) == C and time.monotonic() - since > 3:
                break
            time.sleep(0.1)
        timed_out = hang is None and time.monotonic() >= deadline
        s = self.m.screen() if hang else s
        got = view(s)
        hit = [a for a in alts if a in got]
        ok = hang is None and not timed_out and L.active(s) == C and len(hit) == 1 and \
            sum('OUT OF MEMORY' in x for x in got) <= 1
        shot = self.save_screen(f'{rowid}-{tag or "s"}', s)
        rec = dict(row=rowid, input=text, any_of=list(any_of), outcome=hit[0] if len(hit) == 1 else None, ok=ok,
                   timed_out=timed_out, hang=hang, active=L.active(s), new_lines=got, screen=shot,
                   seconds=round(time.monotonic() - t0, 1))
        self.steps_log.append(rec)
        print(f'  {rowid}: {"ok  " if ok else "FAIL"} {text[:70]!r} -> {got[-3:]}', flush=True)
        if hang or timed_out:
            raise ProductHang(rowid, rec)
        return rec


# ----------------------------------------------------------------- D81 images
def _user_base(label, disk_id, dir_sectors=2):
    img = F.blank_image(directory_sectors=dir_sectors)
    off = F.sector_offset(40, 0)
    img[off:off + 256] = O.blank_user_image(label, disk_id)[off:off + 256]
    return bytes(img)


def make_image(label, disk_id, files, dir_sectors=2):
    img = _user_base(label, disk_id, dir_sectors)
    for name, payload in files:
        img = F.seed_file(img, name, payload)
    return img


def image_report(img):
    """Host check of a D81: BAM counts, directory, chains, cross-links, leaks; payload digests."""
    F.validate_bam(img)
    slots = [s for s in F.directory_slots(img) if s.record[2]]
    chains = [ts for s in slots for ts in F.file_chain(img, s.record)]
    files = F.visible_files(img)
    return dict(bytes=len(img), sha256=sha(img), files=len(files),
                crosslinked=len(chains) != len(set(chains)),
                leaked_or_free_mismatch=set(chains) != F.allocated_sectors(img),
                payloads={k.decode('latin1'): (len(v), sha(v)) for k, v in files.items()})


def fixture_lines(rowid):
    return SPEC[rowid]['expected']['fixture_lines']


def fixture_bytes(rowid):
    return '\n'.join(fixture_lines(rowid)).encode('latin1')


D3_CONTENT = 'a  \n\n  b\r\nc\r\n  \n\n'


def user_images():
    files = []
    for rid, name in (('ide-save-20x40', 'src20x40'), ('ide-save-50x40', 'src50x40'),
                      ('ide-save-100x20', 'src100x20'), ('ide-save-100x40-refusal', 'src100x40')):
        data = fixture_bytes(rid)
        rb = SPEC[rid]['expected'].get('readback')
        if rb:
            assert len(data) == rb['bytes'] and sha(data) == rb['sha256'], 'fixture drift ' + rid
        files.append((name, data))
    files.append(('ev5', SPEC['eval-buffer-5']['expected']['buffer_text'].encode()))
    files.append(('ev50', SPEC['eval-buffer-50']['expected']['buffer_text'].encode()))
    files.append(('d3src', D3_CONTENT.encode('latin1')))
    files.append(('keep', b'KEEP'))
    files.append(('one', b'one'))
    files.append(('bee', b'bee'))
    u1 = make_image(b'L65WORK', b'65', files, dir_sectors=3)
    u2 = make_image(b'OTHERDSK', b'77', [('other', b'OTHER')], dir_sectors=2)
    leak = bytearray(make_image(b'L65LEAK', b'65', [('f1', b'one'), ('f2', b'two')], dir_sectors=2))
    F.set_sector_free(leak, 20, 7, False)          # allocated block owned by no file
    big = make_image(b'L65BIG', b'65', [(f'f{i:03d}', f'file {i}'.encode()) for i in range(144)], dir_sectors=20)
    return dict(u1=u1, u2=u2, leak=bytes(leak), f144=big)


# ----------------------------------------------------------------- sessions
def row_lcc_and_repl(S):
    """REPL command path; no disk, no IDE library."""
    # macro: ordinary (unforced) forms; MY-ID oracle strings are confirmed here, the forced sweep is c253_gc_stress
    S.run_expected('macro-normal', expect('macro-normal'))
    recs = [S.step('set-macro-forced-gc', '(defmacro my-id (x) x)', 'MY-ID', tag='00'),
            S.step('set-macro-forced-gc', '(my-id 7)', '7', tag='01')]
    S.finish_row('set-macro-forced-gc', recs, extra=dict(
        scope='UNFORCED confirmation of the oracle strings only; the forced-collection sweep is the separate '
              'c253_gc_stress defmacro-gc run (see receipt.json gc_stress)'),
        status='PASS' if all(r['ok'] for r in recs) else 'FAIL')
    S.run_expected('lcc-setq-multi', expect('lcc-setq-multi'))
    S.run_expected('lcc-setq-odd', expect('lcc-setq-odd'))
    S.run_expected('lcc-car-2args', expect('lcc-car-2args'))
    S.run_expected('lcc-arity-compiled', expect('lcc-arity-compiled'))
    S.run_expected('lcc-setq-probes', [(e['input'], e['screen']) for e in SPEC['lcc-setq-probes']['expected']['screen']],
                   limit=900)
    S.run_expected('nth-dotted', expect('nth-dotted'))


def row_ide_state(S):
    """Function-level IDE state oracles executed by the product.  Only PUBLIC names are callable at the
    product REPL (the %-helpers used by the host oracle are not published), so the forms are the
    oracle's own ide-make-state / ide-step chain with the state kept in globals (nesting depth stays below
    the REPL stack limit that the host VM does not have)."""
    def key(i, prev, code):
        return S.step(rid, f'(setq s{i} (ide-step {prev} (list (quote key) {code} nil)))', [], tag=f'k{i}')
    rid = 'ide-buffer-switch'
    r = [S.step(rid, '(set-symbol-value (quote ide-buffers) nil)', 'NIL', tag='reset'),
         S.step(rid, '(setq s0 (ide-make-state (ide-make-buffer "a" (list "one"))))', [], tag='s0')]
    for i, (prev, code) in enumerate((('s0', 120), ('s1', 24), ('s2', 14), ('s3', 24), ('s4', 16)), 1):
        r.append(key(i, prev, code))
    r.append(S.step(rid, '(list (ide-buffer-lines (ide-state-buffer s1)) (ide-buffer-lines (ide-state-buffer s3)) (ide-buffer-lines (ide-state-buffer s5)))',
                    '(("XONE") ("XONE") ("XONE"))', tag='lines'))
    r.append(S.step(rid, '(nth 5 (ide-state-buffer s5))', 'T', tag='modified'))
    S.finish_row(rid, r, extra=dict(oracle=SPEC[rid]['expected']['host_result'], path='function-level (ide-step)'))
    rid = 'ide-buffer-switch-two'
    r = [S.step(rid, '(set-symbol-value (quote ide-buffers) nil)', 'NIL', tag='reset'),
         S.step(rid, '(load-file-to-buffer "bee" "b")', 'T', limit=600, tag='store-b'),
         S.step(rid, '(setq s0 (ide-make-state (ide-make-buffer "a" (list "one"))))', [], tag='s0')]
    for i, (prev, code) in enumerate((('s0', 120), ('s1', 24), ('s2', 14), ('s3', 24), ('s4', 14), ('s5', 24), ('s6', 16)), 1):
        r.append(key(i, prev, code))
    for n, want in ((3, '("A" ("XONE"))'), (5, '("B" ("BEE"))'), (7, '("A" ("XONE"))')):
        r.append(S.step(rid, f'(list (ide-buffer-name (ide-state-buffer s{n})) (ide-buffer-lines (ide-state-buffer s{n})))', want, tag=f'view-s{n}'))
    S.finish_row(rid, r, extra=dict(oracle=SPEC[rid]['expected']['host_result'], path='function-level (ide-step)',
                                    note='b is stored from file BEE (public load-file-to-buffer) instead of the private %ide-store-buffer'))
    rid = 'ide-mark-stale'
    r = [S.step(rid, '(setq mb (quote ("m" nil ("abc" "def") (1 . 2) (0 . 1) nil 1105 nil nil)))', [], tag='mb'),
         S.step(rid, '(setq mb2 (%ide-buffer-with-lines-point mb (list "x") (cons 0 0)))', [], tag='mb2'),
         S.step(rid, '(ide-buffer-mark mb)', '(0 . 1)', tag='mark-before'),
         S.step(rid, '(ide-buffer-mark mb2)', 'NIL', tag='mark-after')]
    S.finish_row(rid, r, extra=dict(oracle=SPEC[rid]['expected']['host_result']))


def load_libs(S):
    recs = [S.step('prep', '(load-lib "ide")', 'T', limit=900, tag='ide'),
            S.step('prep', '(load-lib "m65d")', 'T', limit=900, tag='m65d')]
    S.finish_row('prep-load-libs', recs, extra=dict(note='harness step: libraries loaded from the product disk before the user-disk swap'))
    return recs


class Swapper:
    """In-place disk swap: overwrite the image file the emulator has mounted as drive 8."""

    def __init__(self, S):
        self.S, self.log = S, []

    def swap(self, label, image):
        assert len(image) == 819200
        p = self.S.medium_copy
        before = p.read_bytes()
        with open(p, 'r+b') as f:
            f.seek(0)
            f.write(image)
            f.flush()
            os.fsync(f.fileno())
        rec = dict(label=label, replaced_sha=sha(before), new_sha=sha(image))
        self.log.append(rec)
        return rec


def current(S):
    return S.medium_copy.read_bytes()


def check_equal(name, got, want_bytes):
    return dict(file=name, ok=got == want_bytes, got_bytes=None if got is None else len(got),
                want_bytes=len(want_bytes), got_sha=None if got is None else sha(got), want_sha=sha(want_bytes))


def row_ide_state_group(S, sw, imgs, res):
    sw.swap('u1', imgs['u1'])
    row_ide_state(S)


def g_save_small(S, sw, imgs, res):
    sw.swap('u1', imgs['u1'])
    S.run_expected('disk-remount-check', [('(m65d-remount)', '0'), ('(m65d-status)', '0')])
    for rid, name, outname, rt in (('ide-save-20x40', 'src20x40', 'out20x40', 'rt20x40'),
                                   ('ide-save-50x40', 'src50x40', 'out50x40', 'rt50x40')):
        save_row(S, rid, name, outname, rt)
    row_ide_state(S)


def save_row(S, rid, name, outname, rt, reset_before_reload=False):
    oom = ['*** VM: OUT OF MEMORY']
    recs = [S.step(rid, '(progn (set-symbol-value (quote ide-buffers) nil) (load-file-to-buffer "%s" "big"))' % name, 'T', forbid=oom, limit=600, tag='load'),
            S.step(rid, '(save-buffer-to "%s" "big")' % outname, 'T', forbid=oom, limit=900, tag='save'),
            S.step(rid, '(ide-error)', 'NIL', tag='error'),
            S.step(rid, '(m65d-remount)', '0', tag='remount')]
    if reset_before_reload:
        recs.append(S.step(rid, '(set-symbol-value (quote ide-buffers) nil)', 'NIL', tag='drop-buffers'))
    recs += [S.step(rid, '(load-file-to-buffer "%s" "copy")' % outname, 'T', forbid=oom, limit=600, tag='reload'),
             S.step(rid, '(save-buffer-to "%s" "copy")' % rt, 'T', forbid=oom, limit=900, tag='roundtrip-save')]
    S.finish_row(rid, recs, extra=dict(path='command', host_readback=[outname.upper(), rt.upper()],
                                       note='reload equality is shown by the round trip: the reloaded buffer is saved again and the host compares both files with the source'))


def g_save_100x20(S, sw, imgs, res):
    sw.swap('u1', imgs['u1'])
    save_row(S, 'ide-save-100x20', 'src100x20', 'out100x20', 'rt100x20')


def g_save_100x20_reset(S, sw, imgs, res):
    sw.swap('u1', imgs['u1'])
    save_row(S, 'ide-save-100x20-reset', 'src100x20', 'out100x20', 'rt100x20', reset_before_reload=True)


def g_100x40(S, sw, imgs, res):
    sw.swap('u1', imgs['u1'])
    rid = 'ide-save-100x40-refusal'
    recs = [S.step(rid, '(progn (set-symbol-value (quote ide-buffers) nil) (load-file-to-buffer "src100x40" "big"))', ['T'], limit=900, tag='load')]
    r = S.step(rid, '(save-buffer-to "out100x40" "big")', ['T'], limit=900, tag='save')
    recs.append(r)
    recs.append(S.step(rid, '(+ 1 2)', '3', tag='alive'))
    recs.append(S.step(rid, '(ide-error)', ['NIL'], tag='error'))
    S.finish_row(rid, recs, extra=dict(path='command', observed_save=r['new_lines'][-3:],
                                       criteria='success with byte-identical readback OR a refusal; prompt usable; old data intact (host check)'),
                 status='OBSERVED')
    # r8: OOM landing fix on the IDE save path (2.5.2 / r7: the prompt never came back after this OOM).
    rid = 'oom-ide-save-100x40-recovery'
    rr = [dict(recs[1], row=rid, ok=(not recs[1]['hang'] and not recs[1]['timed_out'] and recs[1]['active'] == C)),
          dict(recs[2], row=rid)]
    rr.append(S.oom_step(rid, '(set-symbol-value (quote ide-buffers) nil)', ['NIL'], tag='drop'))
    rr.append(S.oom_step(rid, '(+ 3 4)', ['7'], tag='alive'))
    rr.append(S.oom_step(rid, '(length (list 1 2 3))', ['3'], tag='alloc'))
    S.finish_row(rid, rr, extra=dict(observed_save=r['new_lines'][-3:], host_check='OUT100X40 absent or byte-identical (C-100x40 host readback)'))


def g_eval(S, sw, imgs, res):
    sw.swap('u1', imgs['u1'])
    for rid, fn, final in (('eval-buffer-5', 'ev5', '(5 DONE NIL)'), ('eval-buffer-50', 'ev50', '(50 DONE NIL)')):
        recs = [S.step(rid, '(progn (setq c 0) (setq order-error nil) (setq sentinel nil))', 'NIL', tag='init'),
                S.step(rid, '(progn (set-symbol-value (quote ide-buffers) nil) (load-file-to-buffer "%s" "%s"))' % (fn, fn), 'T', limit=600, tag='load'),
                S.step(rid, '(eval-buffer "%s")' % fn, 'T', limit=1800, tag='eval'),
                S.step(rid, '(list c sentinel order-error)', final, tag='state')]
        S.finish_row(rid, recs)
    rid = 'eval-buffer-50-after-error'
    recs = [S.step(rid, '(capzz)', '*** UNDEFINED FUNCTION: CAPZZ', tag='err'),
            S.step(rid, '(progn (setq c 0) (setq order-error nil) (setq sentinel nil))', 'NIL', tag='init'),
            S.step(rid, '(eval-buffer "ev50")', 'T', limit=1800, tag='eval'),
            S.step(rid, '(list c sentinel order-error)', '(50 DONE NIL)', tag='state')]
    S.finish_row(rid, recs, extra=dict(note='JSON expect: repeat after an ordinary eval error'))


def g_d3_d2(S, sw, imgs, res):
    sw.swap('u1', imgs['u1'])
    rid = 'disk-d3-lossless'
    recs = [S.step(rid, '(progn (set-symbol-value (quote ide-buffers) nil) (load-file-to-buffer "d3src" "d3"))', 'T', limit=600, tag='load'),
            S.step(rid, '(save-buffer-to "d3out" "d3")', 'T', limit=600, tag='save'),
            S.step(rid, '(load-file-to-buffer "d3out" "d3b")', 'T', limit=600, tag='reload'),
            S.step(rid, '(save-buffer-to "d3rt" "d3b")', 'T', limit=600, tag='roundtrip-save')]
    S.finish_row(rid, recs, extra=dict(oracle=SPEC['disk-d3-lossless']['expected']['host_result'], host_readback=['D3OUT', 'D3RT'],
                                       note='the private %ide-disk-read-string / line accessors are not callable at the product REPL; byte identity is shown by the host readback of D3OUT and D3RT against the 17-byte source'))
    rid = 'disk-d2-aborted-save-8'
    recs = [S.step(rid, '(m65d-remount)', '0', tag='remount'),
            S.step(rid, '(progn (set-symbol-value (quote m65d-save) (cons 1 2)) t)', 'T', tag='abort-marker'),
            S.step(rid, '(m65d-save "x" "y")', '8', tag='refused'),
            S.step(rid, '(m65d-remount)', '0', tag='clean-remount'),
            S.step(rid, '(symbol-value (quote m65d-save))', 'NIL', tag='marker-cleared'),
            S.step(rid, '(m65d-save "ctl" "ok")', '0', limit=600, tag='save-after-remount')]
    S.finish_row(rid, recs, extra=dict(oracle='tests/bytecode/libs/p0-m65d-lib-disk-r8-20261001.json d2d4-open-transaction-latches + d2d4-clean-remount-closes-transaction',
                                       note='aborted save SIMULATED by the oracle marker (no emulator fault injection); %m65d-latched-p is private, the latch is observed through the status-8 refusal'))
    res['u1_after'] = image_report(current(S))
    (S.out / 'image-u1-after.d81').write_bytes(current(S))
    sw.swap('u2', imgs['u2'])          # real disk swap without remount
    rid = 'disk-d4-swapped-identity'
    recs = [S.step(rid, '(m65d-save "swap" "x")', '12', limit=600, tag='refused'),
            S.step(rid, '(m65d-save "swap2" "x")', '8', limit=600, tag='latched-8'),
            S.step(rid, '(m65d-remount)', '0', limit=600, tag='remount-u2')]
    S.finish_row(rid, recs, extra=dict(oracle='d2d4-swapped-identity-refused-before-write: (12 t)',
                                       note='real in-place swap of the mounted image instead of the oracle header poke; "latched" is observed as the following status 8'))
    res['u2_after'] = image_report(current(S))
    (S.out / 'image-u2-after.d81').write_bytes(current(S))
    res['u2_unchanged'] = current(S) == imgs['u2']


def g_leak(S, sw, imgs, res):
    sw.swap('leak', imgs['leak'])
    rid = 'disk-d4-mitigation'
    recs = [S.step(rid, '(list (m65d-remount) (m65d-save "x" "y") (m65d-remount))', '(13 8 13)', limit=600, tag='latch'),
            S.step(rid, '(m65d-status)', '13', tag='status'),
            S.step(rid, '(load-file-to-buffer "f1" "s")', 'T', limit=600, tag='read-file'),
            S.step(rid, '(length (dir))', '2', limit=600, tag='dir-reads'),
            S.step(rid, '(save-buffer-to "leak" "s")', 'NIL', limit=600, tag='save'),
            S.step(rid, '(ide-error)', '"DISK ALLOCATION INCONSISTENT; DISK NOT WRITTEN"', tag='message')]
    S.finish_row(rid, recs, extra=dict(oracle='%s ; d2d4-leaked-block-refused (13 t 8 13) ; host_result (nil "disk allocation inconsistent; disk not written" 13)'
                                       % SPEC['disk-d4-mitigation']['expected']['host_result'],
                                       note='"reads still work" = read-file and (dir) steps; zero writes = host compare of the image after the session'))
    after = current(S)
    res['leak_after'] = dict(bytes_identical_to_initial=after == imgs['leak'], sha256=sha(after))


def g_f144(S, sw, imgs, res):
    sw.swap('f144', imgs['f144'])
    rid = 'disk-d5-remount'
    recs = [S.step(rid, '(m65d-remount)', '0', limit=900, tag='remount'),
            S.step(rid, '(m65d-status)', '0', tag='status'),
            S.step(rid, '(m65d-save "f000" "new0")', '0', limit=900, tag='save'),
            S.step(rid, '(m65d-remount)', '0', limit=900, tag='remount-again'),
            S.step(rid, '(length (dir))', '144', limit=900, tag='dir')]
    S.finish_row(rid, recs, extra=dict(oracle=SPEC[rid]['expected']['host_result'],
                                       note='(length (dir)) = 144 is derived from the fixture, not from the host oracle'))
    res['f144_after'] = image_report(current(S))
    (S.out / 'image-f144-after.d81').write_bytes(current(S))


GROUP_FILTER = []


def run_groups(out, name, holder, groups, writable=True):
    """One fresh Xemu per group (a product hang loses only that group).  Rows are merged into <name>-rows.json."""
    imgs = user_images()
    all_rows, result = [], dict(groups={})
    for k, v in imgs.items():
        (out / f'image-{k}-initial.d81').write_bytes(v)
    if GROUP_FILTER:
        known = {g for g, _ in groups}
        assert set(GROUP_FILTER) <= known, ('unknown group', GROUP_FILTER, sorted(known))
        groups = [(g, f) for g in GROUP_FILTER for (g2, f) in groups if g2 == g]
    for gname, fn in groups:
        S = Session(out, f'{name}-{gname}', writable=writable)
        holder.append(S)
        gres = dict(group=gname)
        sw = Swapper(S)
        try:
            S.start()
            gres['boot'] = S.boot
            load_libs(S)
            fn(S, sw, imgs, gres)
            gres['status'] = 'DONE'
        except ProductHang as exc:
            gres['status'] = 'HALT'
            gres['error'] = repr(exc)
            print('GROUP HALT', gname, exc, flush=True)
            mine = [r for r in S.steps_log if r['row'] == exc.rowid]
            S.finish_row(exc.rowid, mine, status='FAIL', extra=dict(halt=str(exc)))
        except Exception as exc:
            gres['status'] = 'HALT'
            gres['error'] = repr(exc)
            print('GROUP ERROR', gname, repr(exc), flush=True)
        finally:
            try:
                gres['outputs'] = S.stop()
            except Exception as exc:
                gres['outputs'] = dict(stop_error=repr(exc))
                S.abort()
            holder.remove(S)
        gres['swaps'] = sw.log
        gres['counted_keys'], gres['blind_keys'] = S.counted_keys, S.blind_keys
        try:
            gres['final_image'] = image_report(S.medium_copy.read_bytes()) if S.writable and gname not in ('leak',) else None
        except Exception as exc:
            gres['final_image'] = dict(error=repr(exc))
        (out / f'{name}-{gname}-final.d81').write_bytes(S.medium_copy.read_bytes())
        for r in S.rows:
            r['group'] = gname
        all_rows += S.rows
        result['groups'][gname] = gres
        (out / f'{name}-rows.json').write_text(json.dumps(all_rows, indent=1) + '\n')
    return result


def host_readbacks(out, gname, checks, name='disk'):
    img = (out / f'{name}-{gname}-final.d81').read_bytes()
    files = F.visible_files(img)
    hc = []
    for rid, fname, srcdata in checks:
        got = files.get(fname.encode())
        hc.append(dict(row=rid, present=got is not None, group=gname, **check_equal(fname, got, srcdata)))
    return hc


def session_disk(out, holder):
    groups = [('A-save-small', g_save_small), ('B-save100x20', g_save_100x20),
              ('B2-save100x20-reset', g_save_100x20_reset), ('C-100x40', g_100x40), ('D-eval', g_eval),
              ('E-d3-d2', g_d3_d2), ('F-leak', g_leak), ('G-f144', g_f144)]
    result = run_groups(out, 'disk', holder, groups)
    f = fixture_bytes
    hc = []
    hc += host_readbacks(out, 'A-save-small', [('ide-save-20x40', 'OUT20X40', f('ide-save-20x40')), ('ide-save-20x40', 'RT20X40', f('ide-save-20x40')),
                                               ('ide-save-50x40', 'OUT50X40', f('ide-save-50x40')), ('ide-save-50x40', 'RT50X40', f('ide-save-50x40'))])
    hc += host_readbacks(out, 'B-save100x20', [('ide-save-100x20', 'OUT100X20', f('ide-save-100x20')), ('ide-save-100x20', 'RT100X20', f('ide-save-100x20'))])
    hc += host_readbacks(out, 'B2-save100x20-reset', [('ide-save-100x20-reset', 'OUT100X20', f('ide-save-100x20')), ('ide-save-100x20-reset', 'RT100X20', f('ide-save-100x20'))])
    hc += host_readbacks(out, 'C-100x40', [('ide-save-100x40-refusal', 'OUT100X40', f('ide-save-100x40-refusal'))])
    hc += host_readbacks(out, 'E-d3-d2', [('disk-d3-lossless', 'D3OUT', D3_CONTENT.encode('latin1')), ('disk-d3-lossless', 'D3RT', D3_CONTENT.encode('latin1')),
                                          ('disk-d2-aborted-save-8', 'CTL', b'ok')])
    result['host_checks'] = hc
    try:
        f144 = F.visible_files((out / 'disk-G-f144-final.d81').read_bytes())
        result['f144_checks'] = dict(files=len(f144), f000_is_new0=f144.get(b'F000') == b'new0',
                                     others_intact=all(f144.get(f'F{i:03d}'.encode()) == f'file {i}'.encode() for i in range(1, 144)))
    except Exception as exc:
        result['f144_checks'] = dict(error=repr(exc))
    holder.clear()
    return result


def row_f2_ladder(S):
    """r8: the F2 regression forms and the nesting-ladder points (max depth compiles and gives the value,
    max+1 reports *** VM: STACK OVERFLOW and the prompt returns).  Depths = candidate column of the
    lcc-nesting-ladder-check receipt; shapes whose depth the emulator calibrated (2.5.2 r7c / 2.5.3 r7) are
    PASS/FAIL rows, the host-only shapes are OBSERVED."""
    S.run_expected('lcc-f2-regression', expect('lcc-f2-regression'), forbid=('STACK OVERFLOW',), limit=900)
    for rid in ('lcc-ladder-calibrated', 'lcc-ladder-host-only'):
        pairs = expect(rid)
        recs = [S.step(rid, inp, scr, limit=900, tag=f'{i:02d}') for i, (inp, scr) in enumerate(pairs)]
        S.finish_row(rid, recs, extra=dict(oracle=SPEC[rid]['oracle_253']),
                     status=None if rid == 'lcc-ladder-calibrated' else
                     ('OBSERVED-MATCH' if all(r['ok'] for r in recs) else 'OBSERVED'))


def session_repl(out, holder):
    S = Session(out, 'repl', writable=False)
    holder.append(S)
    S.start()
    row_lcc_and_repl(S)
    row_f2_ladder(S)
    return {}


def session_oom(out, holder):
    """r8 OOM landing fix (src/repl.c `mem_oom = 0;`): the prompt must come back after every OOM report."""
    S = Session(out, 'oom', writable=False, timeout=3600)
    holder.append(S)
    S.start()
    rid = 'oom-repl-local'
    recs = [S.oom_step(rid, '(let ((a nil)) (while t (setq a (cons 1 a))))', ['*** VM: OUT OF MEMORY'], tag='oom'),
            S.oom_step(rid, '(+ 1 2)', ['3'], tag='alive'),
            S.oom_step(rid, '(length (list 1 2 3))', ['3'], tag='alloc')]
    S.finish_row(rid, recs)
    rid = 'oom-repl-global'
    recs = [S.oom_step(rid, '(setq l nil)', ['NIL'], tag='init'),
            S.oom_step(rid, '(while t (setq l (cons 1 l)))', ['*** VM: OUT OF MEMORY'], tag='fill')]
    # Genuine full heap: each input may report OOM once (repeated report), never loop.
    for i in range(2):
        recs.append(S.oom_step(rid, '(+ 1 2)', ['3', '*** VM: OUT OF MEMORY'], tag=f'full{i}'))
    dropped = False
    for i, form in enumerate(('(setq l nil)', '(setq l nil)', '(set-symbol-value (quote l) nil)')):
        r = S.oom_step(rid, form, ['NIL', '*** VM: OUT OF MEMORY'], tag=f'drop{i}')
        recs.append(r)
        if r['outcome'] == 'NIL':
            dropped = True
            break
    if dropped:
        recs.append(S.oom_step(rid, '(length (list 1 2 3))', ['3'], tag='recovered'))
        recs.append(S.oom_step(rid, '(+ 3 4)', ['7'], tag='alive'))
    no_livelock = all(r['ok'] for r in recs)
    S.finish_row(rid, recs, extra=dict(dropped=dropped, no_livelock=no_livelock,
                                       criteria='hard: every input consumed and prompt back with at most one OOM report '
                                                '(no livelock); recovery after the drop is the owner-visible outcome'),
                 status='PASS' if no_livelock and dropped else ('FAIL-NO-DROP' if no_livelock else 'FAIL'))
    return {}


# --- IDE key path
def ide_enter(S, rowid, name):
    S.send_line('(ide "%s")\n' % name, timeout=600)
    s, ok = S.settle(secs=3.0, limit=180)
    return S.save_screen(f'{rowid}-ide-open', s), s


def ide_keys(S, rowid, codes, tag):
    for c in codes:
        S.key(c)
    s, ok = S.settle(secs=2.5, limit=240)
    return S.save_screen(f'{rowid}-{tag}', s), s


def screen_has(s, *needles):
    """Needle search on the decoded screen.  The editor draws the character under the cursor as a markup tag
    ({flon}), so that one character is a wildcard (the framebuffer dump does not keep its code)."""
    import re
    flat = L.R.ROWS.decoded_framebuffer(s)
    lines = [re.sub(r'\{FLON\}|\{FLOFF\}', '\0', x) for x in flat.splitlines()]

    def has(n):
        n = n.upper()
        for ln in lines:
            for i in range(len(ln) - len(n) + 1):
                if all(a == b or a == '\0' for a, b in zip(ln[i:i + len(n)], n)):
                    return True
        return False
    return all(has(n) for n in needles)


def ide_exit(S, rowid):
    for c in (24, ord('q')):
        S.key(c)
    s, ok = S.settle(secs=2.5, limit=240, cond=lambda x: L.active(x) == C)
    return S.save_screen(f'{rowid}-ide-exit', s), s, L.active(s) == C


def keyrec(rid, text, ok, screen, screens, **kw):
    return dict(row=rid, input=text, ok=ok, screen=screen, screens=screens, **kw)


def k_save(S, rid, srcname, outname, rt):
    recs = [S.step(rid, '(progn (set-symbol-value (quote ide-buffers) nil) (load-file-to-buffer "%s" "big"))' % srcname, 'T', limit=600, tag='load')]
    shot, s0 = ide_enter(S, rid, 'big')
    in_editor = L.active(s0) != C
    keys_shot, s1 = ide_keys(S, rid, [24, 23], 'cxcw')                 # C-x C-w : prompt for a file name
    typed_shot, s2 = ide_keys(S, rid, [ord(c) for c in outname], 'name')
    S.key(13)                                                          # Return : save (long: wait for the prompt to go)
    s3, _ = S.settle(secs=3.0, limit=900, cond=lambda x: not screen_has(x, 'write file:'))
    saved_shot = S.save_screen(f'{rid}-return', s3)
    saved_ok = screen_has(s3, 'saved')
    oom = screen_has(s3, 'out of memory')
    exit_shot, s4, back = ide_exit(S, rid)
    recs.append(keyrec(rid, '(ide "big") C-x C-w %s RET C-x q' % outname, in_editor and saved_ok and not oom and back, saved_shot,
                       [shot, keys_shot, typed_shot, saved_shot, exit_shot], in_editor=in_editor,
                       saved_message_seen=saved_ok, oom_seen=oom, back_at_prompt=back))
    print(f'  {rid}: editor={in_editor} saved={saved_ok} oom={oom} back={back}', flush=True)
    recs.append(S.step(rid, '(m65d-remount)', '0', tag='remount'))
    recs.append(S.step(rid, '(load-file-to-buffer "%s" "copy")' % outname, 'T', forbid=['*** VM: OUT OF MEMORY'], limit=600, tag='reload'))
    recs.append(S.step(rid, '(save-buffer-to "%s" "copy")' % rt, 'T', forbid=['*** VM: OUT OF MEMORY'], limit=900, tag='roundtrip-save'))
    S.finish_row(rid, recs, extra=dict(path='keys', host_readback=[outname.upper(), rt.upper()]))


def gk_small(S, sw, imgs, res):
    sw.swap('u1', imgs['u1'])
    S.run_expected('ide-key-remount', [('(m65d-remount)', '0')])
    k_save(S, 'ide-save-20x40-keys', 'src20x40', 'kout20', 'krt20')
    k_save(S, 'ide-save-50x40-keys', 'src50x40', 'kout50', 'krt50')


def gk_100(S, sw, imgs, res):
    sw.swap('u1', imgs['u1'])
    k_save(S, 'ide-save-100x20-keys', 'src100x20', 'kout100', 'krt100')


def gk_switch(S, sw, imgs, res):
    sw.swap('u1', imgs['u1'])
    rid = 'ide-buffer-switch-keys'
    recs = [S.step(rid, '(progn (set-symbol-value (quote ide-buffers) nil) (load-file-to-buffer "one" "a"))', 'T', limit=600, tag='prep')]
    shot, s0 = ide_enter(S, rid, 'a')
    seen = []
    for tag, codes in (('x', [120]), ('cn', [24, 14]), ('cp', [24, 16])):
        sh, s = ide_keys(S, rid, codes, tag)
        seen.append(dict(stage=tag, screen=sh, ok=screen_has(s, 'xone')))
    exit_shot, s4, back = ide_exit(S, rid)
    recs.append(keyrec(rid, '(ide "a") x C-x C-n C-x C-p C-x q', all(x['ok'] for x in seen) and back, seen[-1]['screen'],
                       [shot] + [x['screen'] for x in seen] + [exit_shot], stages=seen, back_at_prompt=back))
    S.finish_row(rid, recs, extra=dict(expect='text XONE after typing, after C-x C-n and after C-x C-p (single buffer)'))
    rid = 'ide-buffer-switch-two-keys'
    recs = [S.step(rid, '(progn (set-symbol-value (quote ide-buffers) nil) (load-file-to-buffer "bee" "b"))', 'T', limit=600, tag='prep-b'),
            S.step(rid, '(load-file-to-buffer "one" "a")', 'T', limit=600, tag='prep-a')]
    shot, s0 = ide_enter(S, rid, 'a')
    seen = []
    for tag, codes, needle in (('x', [120], 'xone'), ('cn1', [24, 14], 'xone'), ('cn2', [24, 14], 'bee'), ('cp', [24, 16], 'xone')):
        sh, s = ide_keys(S, rid, codes, tag)
        seen.append(dict(stage=tag, screen=sh, want=needle, ok=screen_has(s, needle)))
    exit_shot, s4, back = ide_exit(S, rid)
    recs.append(keyrec(rid, '(ide "a") x C-x C-n C-x C-n C-x C-p C-x q', all(x['ok'] for x in seen) and back, seen[-1]['screen'],
                       [shot] + [x['screen'] for x in seen] + [exit_shot], stages=seen, back_at_prompt=back))
    S.finish_row(rid, recs, extra=dict(expect='oracle sequence a(xone) -> a(xone) -> b(bee) -> a(xone), host_result (("a" ("xone") "b" ("bee") "a" ("xone")))',
                                       note='per the host oracle the first C-x C-n does not leave a'))


def gk_dirty(S, sw, imgs, res):
    sw.swap('u1', imgs['u1'])
    rid = 'eval-dirty-cache'
    recs = [S.step(rid, '(progn (set-symbol-value (quote ide-buffers) nil) (setq dcw 0) (setq ec 0) (setq ml 0))', [], tag='prep')]

    def edit(name, text_keys, tag):
        shot, s0 = ide_enter(S, rid, name)
        typed_shot, s1 = ide_keys(S, rid, text_keys, tag) if text_keys else (shot, s0)
        exit_shot, s4, back = ide_exit(S, rid)
        return typed_shot, back, s1
    text = '(setq dcw 5)'
    sh, back, s1 = edit('dc', [ord(ch) for ch in text], 'typed')
    recs.append(keyrec(rid, '(ide "dc") type %s C-x q' % text, back and screen_has(s1, text), sh, [sh], back_at_prompt=back))
    recs.append(S.step(rid, '(eval-buffer "dc")', 'T', limit=600, tag='eval'))
    recs.append(S.step(rid, 'dcw', '5', tag='value'))
    sh, back, s1 = edit('e0', None, 'empty')
    recs.append(keyrec(rid, '(ide "e0") C-x q (empty buffer)', back, sh, [sh], back_at_prompt=back))
    recs.append(S.step(rid, '(eval-buffer "e0")', 'T', limit=600, tag='eval-empty'))
    sh, back, s1 = edit('e1', [ord(ch) for ch in '(setq ec 1)'] + [13] + [ord(ch) for ch in '; end'], 'typed')
    recs.append(keyrec(rid, '(ide "e1") type (setq ec 1) RET ; end C-x q', back, sh, [sh], back_at_prompt=back))
    recs.append(S.step(rid, '(eval-buffer "e1")', 'T', limit=600, tag='eval-eof-comment'))
    recs.append(S.step(rid, 'ec', '1', tag='eof-value'))
    sh, back, s1 = edit('e2', [ord(ch) for ch in '(setq ml'] + [13] + [ord(ch) for ch in '(+ 1 2))'], 'typed')
    recs.append(keyrec(rid, '(ide "e2") type (setq ml RET (+ 1 2)) C-x q', back, sh, [sh], back_at_prompt=back))
    recs.append(S.step(rid, '(eval-buffer "e2")', 'T', limit=600, tag='eval-multiline'))
    recs.append(S.step(rid, 'ml', '3', tag='multiline-value'))
    S.finish_row(rid, recs, extra=dict(note='variants of the JSON row via the editor keys: dirty edit cache, empty source, EOF comment, multi-line form'))


def session_ide(out, holder):
    groups = [('K-small', gk_small), ('K-switch', gk_switch), ('K-dirty', gk_dirty), ('K-100x20', gk_100)]
    result = run_groups(out, 'ide', holder, groups)
    f = fixture_bytes
    hc = host_readbacks(out, 'K-small', [('ide-save-20x40-keys', 'KOUT20', f('ide-save-20x40')), ('ide-save-20x40-keys', 'KRT20', f('ide-save-20x40')),
                                         ('ide-save-50x40-keys', 'KOUT50', f('ide-save-50x40')), ('ide-save-50x40-keys', 'KRT50', f('ide-save-50x40'))], name='ide')
    hc += host_readbacks(out, 'K-100x20', [('ide-save-100x20-keys', 'KOUT100', f('ide-save-100x20')), ('ide-save-100x20-keys', 'KRT100', f('ide-save-100x20'))], name='ide')
    result['host_checks'] = hc
    holder.clear()
    return result


def classify(rows):
    return {r['id']: r['status'] for r in rows}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('out')
    p.add_argument('--session', choices=['repl', 'disk', 'ide', 'oom', 'all'], default='all')
    p.add_argument('--groups', default='', help='comma separated group names of the session (default: all, in order)')
    a = p.parse_args()
    GROUP_FILTER.clear()
    GROUP_FILTER.extend([g for g in a.groups.split(',') if g])
    out = ROOT / 'build' / a.out
    out.mkdir(parents=True, exist_ok=False)
    names = ['repl', 'disk', 'ide', 'oom'] if a.session == 'all' else [a.session]
    summary = dict(sessions={})
    for nm in names:
        sub = out / nm
        sub.mkdir()
        holder, error, result, outputs = [], None, {}, None
        try:
            result = dict(repl=session_repl, disk=session_disk, ide=session_ide, oom=session_oom)[nm](sub, holder)
        except Exception as exc:   # keep the partial evidence, then go on with the next session
            error = repr(exc)
            print('SESSION HALT', nm, error, flush=True)
        finally:
            S = holder[0] if holder else None
            if S is not None:
                try:
                    outputs = S.stop()
                except Exception as exc:
                    outputs = dict(stop_error=repr(exc))
                    S.abort()
        rows_file = sub / f'{nm}-rows.json'
        rows = json.loads(rows_file.read_text()) if rows_file.exists() else []
        entry = dict(error=error, rows=classify(rows), result=result, outputs=outputs)
        if holder:
            entry.update(boot=holder[0].boot if hasattr(holder[0], 'boot') else None,
                         counted_keys=holder[0].counted_keys, blind_keys=holder[0].blind_keys)
        summary['sessions'][nm] = entry
        (sub / 'session.json').write_text(json.dumps(entry, indent=1) + '\n')
    (out / 'summary.json').write_text(json.dumps(summary, indent=1) + '\n')
    print(json.dumps({k: v['rows'] for k, v in summary['sessions'].items()}, indent=1))


if __name__ == '__main__':
    main()
