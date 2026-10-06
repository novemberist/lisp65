#!/usr/bin/env python3
"""2.5.4 emulator rows (c254_rows_20261004.json) and the 2.5.3 regression rows on the pinned Seed medium.

Successor of c253_rows.py (which stays byte-identical and is imported for the regression rows and the
shared helpers).  Driver for c254_emulator.py mode `new`.  One headless Xemu per boot, strictly
sequential, framebuffer and memory access through the UART monitor only.  Nothing is built.

Sessions (each name = at least one fresh boot; `all` runs them in this order)
  repl      new REPL rows: closures, closure ladder, mapcan, arity, RP1, HIST1
  lib1      LIB1 defstruct collisions (own boot: the loaded package must not leak into other rows)
  oom-rp1   rp1-flat-1101-heap (own boot: a full heap must not leak)
  e3        group K-e3: stop-probe, the seven E3 burst rows, the two pending-C-x rows
  seam      group K-seam: the eight ide-bind-key rows          (NEVER the boot of the e3 group: row
            e3-pending-cx-reset-bound binds key 102, the registry text of seam-registry-value would
            gain a tail; the driver refuses to run a seam row in a boot that ran an e3 row)
  disk-h    group H-load-guard: save refused while a source file loads
  d703      the $D703 DMA-format probe (build/scope-254-r1 decision D10); capture only
  reg-repl, reg-disk, reg-ide, reg-oom
            the 2.5.3 tables through the c253 row functions with the 2.5.4 expected_overrides
            (reg-disk / reg-ide take --groups as in c253_rows.py)

Status of a 2.5.4 row -- there is NO automatic PASS for a row whose screen text the host could not derive
  FAIL        hang / timeout, or an expectation that was HOST-EXECUTED is not met, or an E3 text was lost
  UNREVIEWED  capture-then-review: the row carries a NOT-DERIVED expected text, a `host_first` item, or
              depends on the RUN/STOP stand-in transport.  The screen is recorded; `matches_recorded`
              says whether it equals the text in the table; a reviewer decides (`review` below).
  PASS        every expectation was HOST-EXECUTED, nothing is in the review set, all met
  NOT RUN     a prerequisite did not hold (stop-probe found no working RUN/STOP stand-in)
The 2.5.3 regression rows keep the c253 statuses (PASS / FAIL / OBSERVED / OBSERVED-MATCH / FAIL-NO-DROP).

Usage
  through c254_emulator.py (binds the world):  new <out-dir-under-build> --session NAME[,NAME...]|all
  directly (no world, no emulator):
    c254_rows.py plan                                   print sessions, boots, rows, review set
    c254_rows.py selftest                               offline checks of the pure logic (no emulator)
    c254_rows.py review <run-dir> --review FILE --out <new-dir-under-build>
    c254_rows.py timing <run-dir> --control <control-run-dir>

Paths: evidence goes to the write-once directory build/<out>; emulator scratch (SD image copy, medium
copy, monitor socket, memory dump) goes to tempfile.mkdtemp(dir=ROOT/'build', prefix='c254-rows-') and is
removed at the end (--keep-scratch keeps it).  No receipt binds a path this tool writes: receipts bind
inputs only (medium, ELF, emulator, ROM, tables, tool files) and list written files by name.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time


def _root():
    for p in Path(__file__).resolve().parents:
        if (p / '.git').exists():
            return p
    raise RuntimeError('repository root not found')


ROOT = _root()
TOOLS = ROOT / 'tools/host-lisp'
sys.path.insert(0, str(TOOLS))
import c253_rows as X3  # noqa: E402  (history: read, never edited; regression rows and shared helpers)
import comfort_default_rows as D  # noqa: E402
import comfort_library_rows as L  # noqa: E402
import d81_persistence_fault as F  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402

FORMAT = 'card254-rows-run-v1'
WORLD = {}   # label, medium, medium_sha, elf, elf_sha (filled by c254_emulator.py)
TABLE = TOOLS / 'c254_rows_20261004.json'
TABLE_SHA256 = 'a4cc6ab755d1212a8ca0fd876ca52816b81b397a4b40e90463b7c9488ac87026'
C, N, K = L.C, L.N, L.K
PROMPTS = dict(C=C, N=N, K=K)
STOP_LINE = '*** STOPPED (RUN/STOP)'
CYCLES_PER_SECOND = 40.5e6
SCRATCH_PREFIX = 'c254-rows-'
REVIEW, PASS, FAIL, NOT_RUN = 'UNREVIEWED', 'PASS', 'FAIL', 'NOT RUN'
D703_ROW = 'd703-dma-format-probe'
D703_LINEAR = 0xFFD3703          # MEGA65 I/O personality page, DMA list-format register (F018B enable)
STOP_METHODS = ('flag', 'flag-cpu')
CONTROL_VARIANT = 15            # C-o: a control code Xemu delivers unchanged and the C-x table does not bind


def sha(b):
    return hashlib.sha256(b).hexdigest()


# ----------------------------------------------------------------- table
_RAW = TABLE.read_bytes()
assert sha(_RAW) == TABLE_SHA256, 'row table drift: ' + str(TABLE.relative_to(ROOT)) + ' (a new table needs a new driver pin)'
DOC = json.loads(_RAW)
assert DOC['format'] == 'card254-rows-v1'
SPEC = {r['id']: r for r in DOC['rows']}
assert len(SPEC) == len(DOC['rows']) == 33 and not SPEC.keys() & X3.SPEC.keys(), 'row ids collide with the 2.5.3 tables'
assert sorted(i for ids in DOC['sessions'].values() for i in ids) == sorted(SPEC), 'table sessions do not cover the rows'
# 2.5.4 expected texts of 2.5.3-table rows: applied in memory AFTER the r8 overrides of c253_rows.py; each
# must replace exactly one entry whose current text is the recorded one (a drifting table cannot be overridden silently).
for _rid, _fixes in DOC['expected_overrides']['rows'].items():
    for _fix in _fixes:
        _hits = [e for e in X3.SPEC[_rid]['expected']['screen'] if e['input'] == _fix['input']]
        assert len(_hits) == 1 and _hits[0]['screen'] == _fix['was'], ('override seam', _rid, _fix['input'])
        _hits[0]['screen'] = _fix['screen']

E3_ROWS = [i for i in DOC['sessions']['ide'] if SPEC[i]['group'] == 'e3']
SEAM_ROWS = [i for i in DOC['sessions']['ide'] if SPEC[i]['group'] == 'seam']
assert len(E3_ROWS) == 10 and len(SEAM_ROWS) == 8 and E3_ROWS[0] == 'stop-probe'
# session of this driver -> rows of the table it runs (the table's `ide` session is split into two boots)
PLAN = {
    'repl': [i for i in DOC['sessions']['repl'] if i != 'lib1-defstruct-collision'],
    'lib1': ['lib1-defstruct-collision'],
    'oom-rp1': list(DOC['sessions']['oom']),
    'e3': E3_ROWS,
    'seam': SEAM_ROWS,
    'disk-h': list(DOC['sessions']['disk']),
    'd703': [D703_ROW],
}
REGRESSION = ('reg-repl', 'reg-disk', 'reg-ide', 'reg-oom')
ORDER = list(PLAN) + list(REGRESSION)
assert sorted(i for k, ids in PLAN.items() if k != 'd703' for i in ids) == sorted(SPEC)
assert not set(PLAN['e3']) & set(PLAN['seam'])


def marks(row):
    """Every derivation mark of a table row: (where, mark)."""
    exp = row['expected']
    out = [('screen[%d]' % i, e['derivation']['mark']) for i, e in enumerate(exp.get('screen') or [])]
    out += [('any_of[%s]' % k, v['derivation']['mark']) for k, v in (exp.get('any_of') or {}).items()]
    if 'derivation' in exp:
        out.append(('row', exp['derivation']['mark']))
    assert out and all(m in ('HOST-EXECUTED', 'NOT-DERIVED') for _, m in out), ('unmarked expectation', row['id'])
    return out


def review_reasons(rowid):
    """Why a row can never pass automatically (empty list = an automatic PASS is allowed)."""
    if rowid == D703_ROW:
        return ['no host model of the DMA list-format bit; the observation itself is the result']
    row, why = SPEC[rowid], []
    n = sum(1 for _, m in marks(row) if m == 'NOT-DERIVED')
    if n:
        why.append('%d expected text(s) NOT-DERIVED on the host' % n)
    if row.get('host_first'):
        why.append('host_first: ' + '; '.join(row['host_first']))
    if row['driver'] in ('stop', 'e3'):
        why.append('depends on the RUN/STOP stand-in (monitor write to C2K_BREAK_PENDING), which only row stop-probe and a reviewer can accept')
    if row['driver'] == 'keyseq':
        why.append('prompt glyphs and values after a history recall are device facts')
    return why


REVIEW_SET = sorted(i for i in SPEC if review_reasons(i))
NOT_DERIVED_TEXTS = sum(1 for r in SPEC.values() for _, m in marks(r) if m == 'NOT-DERIVED')
assert NOT_DERIVED_TEXTS == DOC['oracle']['marks']['NOT-DERIVED'] == 26, 'NOT-DERIVED census differs from the oracle receipt'
assert sum(1 for r in SPEC.values() if r.get('host_first')) == 26 and \
    {i for i, r in SPEC.items() if r.get('host_first')} <= set(REVIEW_SET), 'a host_first row is outside the review set'


def status_of(rowid, recs):
    """FAIL beats everything; a row of the review set is never PASS."""
    if any(r.get('ok') is False for r in recs):
        return FAIL
    return REVIEW if review_reasons(rowid) or any(r.get('ok') is None for r in recs) else PASS


# ----------------------------------------------------------------- transport
# Finding of run card-254-rows-r1 (2026-10-04): the pinned headless Xemu sends a monitor reply with a plain
# send() and does not ignore SIGPIPE.  The stock Monitor.command gives every connection 0.5 s for the reply,
# then closes the socket and sends the command again.  On a loaded host a reply can take longer than that:
# the close then kills the emulator (exit by signal 13, log not flushed) and every later command reports
# "Connection refused".  One early close was enough in the isolated reproduction.
# The patient transport never closes a connection that carries a sent command before the reply is complete
# and never sends a command twice.  It changes host waiting only: no guest input, no emulated time.
REPLY_PATIENCE = 180.0          # host seconds for one reply; only a dead or stuck emulator reaches it
TRANSPORT = 'patient (c254_rows.patient_command: one connection per command, no early close, no resend)'
_MONITOR = L.R.ROWS.Monitor
_STOCK_COMMAND = _MONITOR.command


def patient_command(self, command, timeout=3.0):
    """Drop-in for dwx_mirrored_prefilter_rows.Monitor.command (installed in memory; the file is not edited)."""
    if getattr(self, '_breakpoint_socket', None) is not None:
        return _STOCK_COMMAND(self, command, timeout)       # the owned breakpoint connection is already patient
    deadline = time.monotonic() + timeout
    while True:
        client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            try:
                client.settimeout(max(0.5, timeout))
                client.connect(str(self.path))
            except OSError as error:        # nothing was sent yet: trying again is harmless
                if time.monotonic() >= deadline:
                    raise L.R.ROWS.RowError(f'UART monitor command failed: {command}: {error}') from None
                time.sleep(0.02)
                continue
            try:
                client.settimeout(REPLY_PATIENCE)
                client.sendall(command.encode('ascii') + b'\r')
                raw = b''
                while b'\n.\r\n' not in raw:
                    block = client.recv(16384)
                    if not block:
                        break
                    raw += block
            except OSError as error:
                raise L.R.ROWS.RowError(f'UART monitor command failed: {command}: {error!r} after the command '
                                        'was sent (not sent again)') from None
            if command == '~pcsave' and b'\n.\r\n' not in raw:
                raise L.R.ROWS.RowError('PC histogram response incomplete')
            return raw.decode('utf-8', errors='replace')
        finally:
            client.close()


_MONITOR.command = patient_command


# ----------------------------------------------------------------- scratch
SCRATCH = []
KEEP_SCRATCH = False


def new_scratch():
    """Emulator scratch below build/ (never /tmp: the socket and the medium copy stay on the build volume)."""
    path = Path(tempfile.mkdtemp(dir=ROOT / 'build', prefix=SCRATCH_PREFIX))
    SCRATCH.append(path)
    return path


def drop_scratch():
    """Remove only directories this process created with new_scratch()."""
    while SCRATCH:
        path = SCRATCH.pop()
        if KEEP_SCRATCH:
            print('scratch kept:', path.relative_to(ROOT), flush=True)
            continue
        assert path.parent == ROOT / 'build' and path.name.startswith(SCRATCH_PREFIX) and not path.is_symlink()
        shutil.rmtree(path, ignore_errors=True)


# ----------------------------------------------------------------- screen helpers
def decoded(screen):
    return L.R.ROWS.decoded_framebuffer(screen)


def editor_view(screen):
    """(text rows, cursor row index or None, status row or None) of an IDE screen; None when it is not one.

    Layout (shakedown build/card-254-shakedown-r1): 24 text rows, the status row is row 25 and starts with
    '-- ' ('-- NAME [*] [MESSAGE] L<n> -- used/total'; a message is drawn INSIDE the status row).  The product
    does not redraw the status row when a buffer is re-entered with an unchanged status text (2.5.3 r8 and the
    2.5.4 Seed alike), and the framebuffer dump drops trailing blank rows: such a screen is still an IDE screen,
    with status row None.  A REPL screen is told apart by its last non-blank row (a prompt row) or by a
    non-blank row 25 that is no status row.  A cursor on a blank cell is dumped as {$A0} (kept as a space);
    a cursor on a character is dumped as a markup tag that hides the character: that one cell is a wildcard
    ('\\0'), as in c253_rows.screen_has."""
    rows = decoded(screen).split('\n')
    rows += [''] * (25 - len(rows))
    plain = [r.replace('{$A0}', ' ').strip() for r in rows]
    status = rows[24] if rows[24].startswith('-- ') else None
    if status is None:
        used = [r for r in plain if r]
        if plain[24] or (used and used[-1].startswith((C, N))):
            return None
    body, cursor = [], None
    for i, r in enumerate(rows[:24]):
        if '{$A0}' in r or '{FLON}' in r or '{FLOFF}' in r:
            cursor = i
        body.append(re.sub(r'\{FLON\}|\{FLOFF\}', '\0', r).replace('{$A0}', ' ').rstrip(' '))
    if status is None and cursor is None:
        return None
    return body, cursor, status


def text_matches(view, text):
    """Does the IDE screen show exactly `text` (lower case, '\\n' separated; a trailing '\\n' = one more, empty, line)?
    Returns True / False / None (None = the screen cannot tell 'x' from 'x\\n': no cursor on the last line)."""
    body, cursor, _status = view
    want = text.upper().split('\n')
    shown = list(body)
    while shown and shown[-1] == '':
        shown.pop()
    core = list(want)
    while core and core[-1] == '':
        core.pop()
    if len(shown) != len(core):
        return False
    for got, exp in zip(shown, core):
        if len(got) != len(exp) or any(a != b and a != '\0' for a, b in zip(got, exp)):
            return False
    extra = len(want) - len(core)             # trailing empty lines the text demands
    if cursor is not None and cursor >= len(core):
        return cursor == len(want) - 1        # the cursor sits on a trailing empty line: line count is visible
    if cursor is not None and cursor == len(core) - 1 and core:
        return extra == 0                     # the cursor is on the last text line: no further line exists
    return None if (extra or core) else True  # cursor elsewhere / unknown: trailing-newline state not visible


def e3_verdict(texts, shown, floor, idle=False, stopped_lines=1):
    """The E3 rule on one iteration.  texts = T(0..n); shown = [True/False/None per m] (text_matches);
    floor = the smallest m that is acceptable (keys known to be accepted before the STOP, minus one).
    OK: the screen shows T(m) for an m >= floor and no candidate below the floor fits.
    VIOLATION: only texts below the floor fit, or none fits.  AMBIGUOUS: the screen cannot decide."""
    sure = [m for m, v in enumerate(shown) if v is True]
    maybe = [m for m, v in enumerate(shown) if v is None]
    n = len(texts) - 1
    if idle:
        ok = sure == [n] and stopped_lines == 1
        return dict(verdict='OK' if ok else ('AMBIGUOUS' if n in maybe and stopped_lines == 1 else 'VIOLATION'), fits=sure, maybe=maybe, floor=n)
    # equal texts at different m (Backspace rows): any fitting m at or above the floor is acceptable
    if any(m >= floor for m in sure):
        return dict(verdict='OK', fits=sure, maybe=maybe, floor=floor)
    if any(m >= floor for m in maybe):
        return dict(verdict='AMBIGUOUS', fits=sure, maybe=maybe, floor=floor)
    return dict(verdict='VIOLATION', fits=sure, maybe=maybe, floor=floor)


# ----------------------------------------------------------------- session
class Session(X3.Session):
    """c253 session with: scratch below build/, no binding of written files, cycle stamps, capture steps,
    RUN/STOP stand-in, burst input."""
    boots = []          # one entry per started emulator (session name, pid, rows) -- separation evidence

    def start(self):
        medium, elf = WORLD['medium'], WORLD['elf']
        assert sha(medium.read_bytes()) == WORLD['medium_sha'], 'medium drift'
        assert sha(elf.read_bytes()) == WORLD['elf_sha'], 'elf drift'
        assert sha(L.XEMU.read_bytes()) == L.EXPECT['xemu'], 'xemu drift'
        self.truth = ElfTruth.read(elf, llvm_readobj=ROOT / 'tools/llvm-mos/bin/llvm-readobj')
        self.taken_addr = self.truth.symbol('C2K_INPUT_EVENTS_TAKEN').value
        self.break_addr = self.truth.symbol('C2K_BREAK_PENDING').value
        self.stop_method = None
        run_dir = new_scratch()
        sd_copy = run_dir / 'system-sd.img'
        subprocess.run(['cp', '--reflink=auto', '--sparse=always', str(X3.SDIMG), str(sd_copy)], check=True)
        self.medium_copy = run_dir / medium.name
        shutil.copyfile(medium, self.medium_copy)
        self.medium_copy.chmod(0o644 if self.writable else 0o444)
        memory, screen, log, sock = run_dir / 'memory.bin', run_dir / 'framebuffer.txt', run_dir / 'xemu.log', run_dir / 'm.sock'
        assert len(str(sock)) < 100, 'monitor socket path too long for AF_UNIX'
        cmd = [str(L.R.SAFE_RUNNER), str(memory), str(self.timeout), str(L.XEMU),
               '-skipconfigfile', '-headless', '-testing', '-sleepless', '-besure', '-fastboot', '-nosound',
               '-rom', str(X3.ROM), '-sdimg', str(sd_copy), '-8', str(self.medium_copy), '-autoload',
               '-uartmon', str(sock), '-dumpscreen', str(screen), '-dumpmem', str(memory)]
        self.log_handle = log.open('wb')
        self.proc = subprocess.Popen(cmd, stdout=self.log_handle, stderr=subprocess.STDOUT)
        self.run = dict(dir=run_dir, memory=memory, screen=screen, log=log, sock=sock)
        self.boot_record = dict(session=self.name, xemu_pid=self.proc.pid, scratch=run_dir.name, rows=self.rows, exit_status=None)
        Session.boots.append(self.boot_record)
        t_start = time.monotonic()
        deadline = time.monotonic() + 15
        while not sock.exists() and time.monotonic() < deadline:
            assert self.proc.poll() is None, 'Xemu exited before monitor'
            time.sleep(0.02)
        assert sock.exists(), 'UART monitor absent'
        self.m = L.R.ProbeMonitor(sock)
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
                         seconds_at_40_5MHz=round(cycles / CYCLES_PER_SECOND, 2) if cycles else None)
        (self.out / f'{self.name}-boot.txt').write_text(boot)
        assert self.boot['active'] == C, 'boot did not reach l65>'
        return self.boot

    def stop(self):
        """Evidence is COPIED into the output directory and listed by name; nothing written here is bound."""
        outputs = None
        try:
            if self.run:
                written = [f'{self.name}-final-framebuffer.txt']
                (self.out / written[0]).write_text(self.m.screen())
                self.m.command('~exit')
                status = self.proc.wait(timeout=30)
                self.log_handle.close()
                if self.run['log'].exists():
                    shutil.copyfile(self.run['log'], self.out / f'{self.name}-xemu.log')
                    written.append(f'{self.name}-xemu.log')
                outputs = dict(exit_status=status, written=written,
                               memory_dump_bytes=self.run['memory'].stat().st_size if self.run['memory'].exists() else None)
        finally:
            self.abort()
        return outputs

    def abort(self):
        """Name an emulator that ended by itself (status of the runner: 128 + signal, 141 = SIGPIPE, 124 = timeout)."""
        p, record = getattr(self, 'proc', None), getattr(self, 'boot_record', None)
        status = p.poll() if p else None
        if record is not None and record['exit_status'] is None and status is not None:
            record['exit_status'] = status
            if status != 0:
                print('XEMU ENDED BY ITSELF', self.name, 'runner status', status, flush=True)
        super().abort()

    # -- low level
    def cycles(self):
        try:
            return self.m.cycle_count()
        except Exception:
            return None

    def poke(self, address, value):
        """Monitor memory write (`s <28-bit address> <byte>`; 0x777xxxx = CPU view), with the echo and a readback."""
        response = self.m.command(f's {address:08x} {value:02x}')
        return dict(command=f's {address:08x} {value:02x}', response=response[:80], readback=self.m.memory_range(address, 1)[0])

    def wait_for(self, cond, limit=30, poll=0.05):
        t0, s = time.monotonic(), self.m.screen()
        while time.monotonic() - t0 < limit:
            if cond(s):
                return s, True
            time.sleep(poll)
            s = self.m.screen()
        return s, cond(s)

    def wait_cycles(self, seconds):
        """Wait `seconds` of EMULATED time (the emulator runs -sleepless: wall time is not device time)."""
        c0 = self.cycles()
        if c0 is None:
            time.sleep(seconds)
            return dict(unit='wall', seconds=seconds)
        target, t0 = c0 + int(seconds * CYCLES_PER_SECOND), time.monotonic()
        now = c0
        while now < target and time.monotonic() - t0 < 60:
            now = self.cycles() or target
        return dict(unit='emulated', seconds=seconds, cycles=now - c0)

    def inject_stop(self, method):
        """RUN/STOP stand-in.  The product's IRQ does `inc C2K_BREAK_PENDING` on the $D613 matrix edge
        (src/c2_kernal_irq_base.s); c2_kernal_event_poll / lisp_poll consume that flag.  A typed code 3 is
        NOT an abort authority (src/c2_kernal_window.s drains it), so no key event is used.
          flag      linear bank-0 address of the symbol (the $e000 window is published into bank-0 RAM)
          flag-cpu  the same address through the CPU map (0x777xxxx monitor view)"""
        assert method in STOP_METHODS
        address = self.break_addr if method == 'flag' else (0x7770000 | (self.break_addr & 0xFFFF))
        return dict(method=method, address='%07x' % address, **self.poke(address, 1))

    def clear_stop(self, method):
        address = self.break_addr if method == 'flag' else (0x7770000 | (self.break_addr & 0xFFFF))
        return self.poke(address, 0)

    def burst(self, codes):
        """Queue all keys at once: one `~typehex` paste.  Xemu feeds its 5-slot hardware queue once per frame
        with the same encoding as the singleton transport and gives up after 60 stalled frames; the driver does
        NOT wait for the consumer counter between keys.  (`~typeone` cannot burst: it resets the queue.)"""
        assert codes and all(0 < c < 256 for c in codes)
        response = self.m.command('~typehex ' + bytes(codes).hex())
        assert 'DWX HWA input queued' in response, 'burst was not queued: ' + response[:80]
        return dict(transport='typehex paste (5-slot HWA queue, 60-frame stall limit)', queued=len(codes))

    def paste_busy(self):
        return 'DWX HWA input busy: 0' not in self.m.command('~typebusy')

    def flush_keys(self, limit=20):
        """After an abort: let the paste end, then drop whatever is still in the hardware queue."""
        t0 = time.monotonic()
        while self.paste_busy() and time.monotonic() - t0 < limit:
            time.sleep(0.05)
        self.m.command('~typeone 14')     # resets the HWA queue; the one DEL it queues is harmless at the prompt
        return dict(paste_ended=not self.paste_busy())

    def clean_prompt(self, rounds=6):
        """Remove residue of a burst that was typed at the REPL prompt after the abort."""
        log = []
        for _ in range(rounds):
            s, _ok = self.settle(secs=1.5, limit=60)
            act = L.active(s)
            log.append(act)
            if act == C:
                return dict(clean=True, lines=log)
            for _ in range((len(act) - len(C) if act.startswith(C) else len(act)) + 2):
                self.key(20)
        return dict(clean=False, lines=log)

    def send_line(self, text, timeout=240):
        """Counted singleton transport at the Comfort prompt (c253).  At the native LISP65> prompt the paste
        transport is used, as comfort_default_rows does for its non-Comfort members."""
        if L.active(self.m.screen()) == N:
            if text.strip('\n'):
                self.m.type_text(text)
            else:
                self.m.queue_one(13)
                time.sleep(0.5)
            return
        super().send_line(text, timeout=timeout)

    # -- REPL steps
    def step(self, rowid, text, want, forbid=(), limit=300, tag=None, noerr=None):
        """c253 step (same acceptance) + tag and DWX cycles from the first key to the first screen that shows
        the result (the settle time after it is excluded; -sleepless wall seconds are not device seconds)."""
        before = self.m.screen()
        t0, c0, c_hit = time.monotonic(), self.cycles(), None
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
            if good and c_hit is None:
                c_hit = self.cycles()
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
        cyc = (c_hit - c0) if (c_hit is not None and c0 is not None) else None
        rec = dict(row=rowid, tag=tag, input=text, want=wants, forbid=list(forbid), ok=ok, timed_out=timed_out, hang=hang,
                   active=L.active(s), new_lines=got, screen=shot, seconds=round(time.monotonic() - t0, 1),
                   cycles_to_result=cyc, seconds_at_40_5MHz=round(cyc / CYCLES_PER_SECOND, 2) if cyc is not None else None)
        self.steps_log.append(rec)
        print(f'  {rowid}: {"ok  " if ok else "FAIL"} {str(text)[:70]!r} -> {got[-3:]}', flush=True)
        if hang or timed_out:
            raise X3.ProductHang(rowid, rec)
        return rec

    def table_step(self, rowid, text, expected, *, mark, forbid=(), limit=600, tag=None, prompts=(C,)):
        """One typed form of a 2.5.4 table row.  expected = acceptable result lines (any one; [] = none named).
        HOST-EXECUTED: ok is True/False.  NOT-DERIVED: capture only -- ok is None, the screen is recorded and
        `matches_recorded` says whether it equals the table text; never a pass by itself."""
        before = self.m.screen()
        t0, c0, c_hit = time.monotonic(), self.cycles(), None
        hang = None
        try:
            self.send_line(text + '\n', timeout=120)
        except Exception as exc:
            hang = 'input not consumed: ' + repr(exc)
        alts = [a.upper() for a in expected]

        def view(s):
            seg = self.segment(s, text) if text else None
            return seg if seg is not None else L.new_lines(before, s)

        last, since, deadline, s = None, time.monotonic(), time.monotonic() + limit, before
        while hang is None and time.monotonic() < deadline:
            s = self.m.screen()
            if s != last:
                last, since = s, time.monotonic()
            seg, at_prompt = view(s), L.active(s) in prompts
            if sum('OUT OF MEMORY' in x for x in seg) >= 2 and not at_prompt:
                hang = 'OUT OF MEMORY repeated for one input, no prompt (error livelock)'
                break
            hit = at_prompt and any(a in seg for a in alts)
            if hit and c_hit is None:
                c_hit = self.cycles()
            if hit and time.monotonic() - since > 1.5:
                break
            if at_prompt and time.monotonic() - since > (8 if alts else 3):
                break
            time.sleep(0.1)
        timed_out = hang is None and time.monotonic() >= deadline
        s = self.m.screen() if hang else s
        got = view(s)
        matched = [a for a in alts if a in got]
        errors = [x for x in got if x.startswith('*** ')]
        forbidden = [f for f in forbid if f.upper() in got]
        prompt_back = L.active(s) in prompts
        mechanical = prompt_back and not forbidden and (bool(matched) if alts else not errors)
        capture = mark != 'HOST-EXECUTED'
        ok = False if (hang or timed_out) else (None if capture else mechanical)
        shot = self.save_screen(f'{rowid}-{tag or "s"}', s)
        cyc = (c_hit - c0) if (c_hit is not None and c0 is not None) else None
        rec = dict(row=rowid, tag=tag, input=text, mark=mark, expected=list(expected), matched=matched, forbid=list(forbid),
                   forbidden_seen=forbidden, error_lines=errors, ok=ok, capture=capture, matches_recorded=mechanical,
                   prompt_back=prompt_back, timed_out=timed_out, hang=hang, active=L.active(s), new_lines=got,
                   screen=shot, seconds=round(time.monotonic() - t0, 1), cycles_to_result=cyc)
        self.steps_log.append(rec)
        word = 'HANG' if ok is False and (hang or timed_out) else ('FAIL' if ok is False else ('seen' if capture else 'ok  '))
        print(f'  {rowid}: {word} {text[:70]!r} -> {got[-3:]}', flush=True)
        if hang or timed_out:
            raise X3.ProductHang(rowid, rec)
        return rec

    def finish254(self, rowid, recs, extra=None, status=None):
        extra = dict(extra or {})
        st = status or status_of(rowid, recs)
        if st == REVIEW:
            extra['review'] = dict(reasons=review_reasons(rowid),
                                   captured_steps=sum(1 for r in recs if r.get('ok') is None),
                                   all_captures_match_recorded=all(r.get('matches_recorded', True) for r in recs if r.get('ok') is None))
        assert not (st == PASS and review_reasons(rowid)), 'automatic PASS of a review row'
        return self.finish_row(rowid, recs, extra=extra, status=st)


X3.Session = Session      # the c253 row functions (run_groups, session_*) start THIS session class
X3.WORLD = WORLD          # the driver's start() reads this module's WORLD; kept equal for any c253 reader


# ----------------------------------------------------------------- table rows: typed forms
def typed_row(S, rowid, prompts=(C,), limit=600, extra=None):
    """Rows whose table entry is a list of typed forms (expected.screen and/or expected.any_of)."""
    exp, recs = SPEC[rowid]['expected'], []
    entries = [(e['input'], [e['screen']] if e.get('screen') is not None else [], e.get('forbid', []), e['derivation']['mark'])
               for e in exp.get('screen') or []]
    entries += [(inp, e['any_of'], [], e['derivation']['mark']) for inp, e in (exp.get('any_of') or {}).items()]
    assert [e[0] for e in entries] == SPEC[rowid]['steps'], ('table steps differ from the expectations', rowid)
    for i, (inp, alts, forbid, mark) in enumerate(entries):
        recs.append(S.table_step(rowid, inp, alts, mark=mark, forbid=forbid, limit=limit, tag=f'{i:02d}', prompts=prompts))
    return S.finish254(rowid, recs, extra=extra)


def keyseq_row(S, rowid):
    """HIST1: key sequences with Return / cursor-up.  Every check is a device fact (prompt glyphs, values after a
    recall): all segments are captures; `mechanical` records what the table's prompt/line model saw."""
    recs = []
    for i, seg in enumerate(SPEC[rowid]['expected']['keys']):
        before = S.m.screen()
        keys = [seg['send']] if isinstance(seg['send'], str) else [L.UP if k == 'UP' else k for k in seg['send']]
        hang = None
        try:
            D.send_counted(S.m, keys, S.taken_addr, timeout=120)
        except Exception as exc:
            hang = 'input not consumed: ' + repr(exc)
        s, stable = S.settle(secs=2.0, limit=180)
        act, new = L.active(s), L.new_lines(before, s)
        want = seg['want_prompt']
        prompt_ok = (act == C or act.startswith(C + ' ')) if want == 'C' else (not act.startswith(C) and not act.startswith(N))
        continuation = not act.startswith(C) and not act.startswith(N)
        mech = (hang is None and stable and prompt_ok and all(w.upper() in new for w in seg.get('want_lines', []))
                and not (seg.get('forbid_prompt') == 'K' and continuation))
        rec = dict(row=rowid, tag=f'{i:02d}', input=seg['send'], mark='NOT-DERIVED', capture=True, ok=False if hang else None,
                   matches_recorded=mech, want_prompt=want, active=act, want_lines=seg.get('want_lines', []), new_lines=new,
                   hang=hang, screen=S.save_screen(f'{rowid}-{i:02d}', s))
        S.steps_log.append(rec)
        recs.append(rec)
        print(f'  {rowid}: {"HANG" if hang else "seen"} {seg["send"]!r} -> prompt {act!r} {new[-2:]}', flush=True)
        if hang:
            raise X3.ProductHang(rowid, rec)
    return S.finish254(rowid, recs)


def session_repl(out, holder):
    S = Session(out, 'repl', writable=False)
    holder.append(S)
    S.start()
    for rid in ('closure-compile', 'closure-still-refused', 'lcc-ladder-closure', 'mapcan-beyond-12', 'mapcan-heap-edge',
                'arity-bitops-eq-refused', 'arity-toplevel-direct', 'rp1-bounded-result', 'rp1-accepted-large'):
        typed_row(S, rid, limit=900)
    keyseq_row(S, 'hist1-recall-comment')
    keyseq_row(S, 'hist1-recall-two-comments')
    # LAST: it leaves Comfort (empty line -> LISP65>) and re-enters it with (repl)
    typed_row(S, 'rp1-depth8-reentry', prompts=(C, N))
    assert [r['id'] for r in S.rows] == _order('repl'), 'repl session did not run its plan'
    return {}


def _order(name):
    """Execution order of a session (the plan lists the same rows in table order)."""
    order = {'repl': ['closure-compile', 'closure-still-refused', 'lcc-ladder-closure', 'mapcan-beyond-12', 'mapcan-heap-edge',
                      'arity-bitops-eq-refused', 'arity-toplevel-direct', 'rp1-bounded-result', 'rp1-accepted-large',
                      'hist1-recall-comment', 'hist1-recall-two-comments', 'rp1-depth8-reentry']}.get(name, PLAN[name])
    assert sorted(order) == sorted(PLAN[name])
    return order


def session_lib1(out, holder):
    S = Session(out, 'lib1', writable=False)
    holder.append(S)
    S.start()
    typed_row(S, 'lib1-defstruct-collision', limit=900)
    return {}


def session_oom_rp1(out, holder):
    S = Session(out, 'oom-rp1', writable=False, timeout=3600)
    holder.append(S)
    S.start()
    typed_row(S, 'rp1-flat-1101-heap', limit=900,
              extra=dict(note='all three texts are NOT-DERIVED: the row stays UNREVIEWED; RESULT TOO DEEP instead of OUT OF MEMORY means the heap is larger than modelled'))
    return {}


# ----------------------------------------------------------------- group K-e3
def in_editor(s):
    return editor_view(s) is not None and L.active(s) not in (C, N)


def stopped(s):
    return STOP_LINE in decoded(s) and L.active(s).startswith(C)


def stop_reports(s):
    """STOPPED lines directly above the active prompt = the reports of the abort that just happened."""
    n = 0
    for x in reversed([y.replace('{$A0}', ' ').strip() for y in L.lines(s)][:-1]):
        if x == STOP_LINE:
            n += 1
        elif x:
            break
    return n


def stop_probe(S):
    """Row stop-probe: find a RUN/STOP stand-in that aborts (a) a running form and (b) the idle editor, each with
    exactly one STOPPED line.  Sets S.stop_method (None = none works: the E3 rows are NOT RUN).  Capture row."""
    rid, recs = 'stop-probe', []
    before = S.m.screen()
    S.send_line('(while t nil)\n', timeout=120)
    time.sleep(1.0)
    attempts, s, ok, method = [], before, False, None
    for method in STOP_METHODS:
        a = S.inject_stop(method)
        s, ok = S.wait_for(stopped, limit=20)
        a.update(aborted=ok, stopped_lines=stop_reports(S.settle(secs=1.5, limit=30)[0]) if ok else 0)
        if not ok:
            a['cleared'] = S.clear_stop(method)
        attempts.append(a)
        if ok:
            break
    rec = dict(row=rid, tag='running-form', input='(while t nil) + injected RUN/STOP', mark='NOT-DERIVED', capture=True,
               ok=None if ok else False, matches_recorded=ok and attempts[-1]['stopped_lines'] == 1, attempts=attempts,
               active=L.active(s), new_lines=L.new_lines(before, s), screen=S.save_screen(rid + '-running', s),
               hang=None if ok else 'no RUN/STOP stand-in aborts a running form')
    S.steps_log.append(rec)
    recs.append(rec)
    print(f'  {rid}: running form aborted={ok} by {method if ok else None}', flush=True)
    if not ok:
        raise X3.ProductHang(rid, rec)      # the form runs for ever: this boot is lost, E3 rows NOT RUN
    running_method = method
    exp = SPEC[rid]['expected']['screen'][1]
    recs.append(S.table_step(rid, exp['input'], [exp['screen']], mark=exp['derivation']['mark'], tag='alive'))
    shot, s0 = X3.ide_enter(S, rid, 'stopp')
    S.key(ord('a'))
    S.settle(secs=2.5, limit=60)
    attempts, ok = [], False
    for method in [running_method] + [x for x in STOP_METHODS if x != running_method]:
        a = S.inject_stop(method)
        s, ok = S.wait_for(stopped, limit=20)
        a.update(aborted=ok, stopped_lines=stop_reports(S.settle(secs=1.5, limit=30)[0]) if ok else 0)
        if not ok:
            a['cleared'] = S.clear_stop(method)
        attempts.append(a)
        if ok:
            S.stop_method = method
            break
    rec = dict(row=rid, tag='idle-editor', input='(ide "stopp") a + injected RUN/STOP', mark='NOT-DERIVED', capture=True, ok=None,
               matches_recorded=ok and attempts[-1]['stopped_lines'] == 1, attempts=attempts, editor_opened=in_editor(s0),
               active=L.active(s), screen=S.save_screen(rid + '-editor', s), screens=[shot])
    S.steps_log.append(rec)
    recs.append(rec)
    print(f'  {rid}: idle editor aborted={ok} by {S.stop_method}', flush=True)
    if not ok:
        X3.ide_exit(S, rid)
    rec['prompt_cleanup'] = S.clean_prompt()
    S.finish254(rid, recs, extra=dict(stop_method=S.stop_method, methods_tried=list(STOP_METHODS),
                                     note='UNREVIEWED by construction: the reviewer accepts or rejects the stand-in; '
                                          'the E3 rows of this boot depend on it'))
    return S.stop_method


def e3_iteration(S, rid, name, keys, texts, stop, k=None, delay=None, idle=False):
    rec = dict(row=rid, buffer=name, stop=stop, k=k, delay_s=delay, mark='HOST-EXECUTED rule / device observation', capture=True)
    shot0, s0 = X3.ide_enter(S, rid, name)
    if not in_editor(s0):
        rec.update(ok=False, verdict='EDITOR-NOT-OPEN', screen=shot0)
        return rec
    n, base = len(keys), S.taken()
    delta = lambda: (S.taken() - base) & 255                       # noqa: E731
    rec['burst'] = S.burst(keys)
    target = k if k is not None else n
    t0 = time.monotonic()
    while delta() < target and time.monotonic() - t0 < 60:
        pass
    rec['counted_at_target'] = delta()
    if idle:
        S.settle(secs=2.5, limit=120)
    elif delay:
        rec['delay'] = S.wait_cycles(delay)
    S.m.command('t1')                   # CPU paused: counter, screen and the flag write describe ONE moment
    try:
        pre = S.m.screen()
        j_lo = delta()
        inj = S.inject_stop(S.stop_method)
    finally:
        S.m.command('t0')
    pre_view = editor_view(pre)
    seen = [m for m, t in enumerate(texts) if pre_view and text_matches(pre_view, t) is True]
    s, ok = S.wait_for(stopped, limit=30)
    j_hi = delta()
    rec.update(injection=inj, aborted=ok, j_counter_at_stop=j_lo, j_counter_after_abort=j_hi,
               keys_rendered_before_stop=max(seen) if seen else None,
               stop_screen=S.save_screen(f'{rid}-{name}-stop', s), flush=S.flush_keys())
    rec['stopped_lines'] = stop_reports(S.settle(secs=1.5, limit=30)[0]) if (ok and idle) else None
    if not ok:
        rec['cleared'] = S.clear_stop(S.stop_method)
        X3.ide_exit(S, rid)
        rec.update(ok=None, verdict='STOP-NOT-TAKEN', prompt_cleanup=S.clean_prompt())
        return rec
    rec['prompt_cleanup'] = S.clean_prompt()
    shot1, s1 = X3.ide_enter(S, rid, name)
    view = editor_view(s1)
    shown = [text_matches(view, t) if view else False for t in texts]
    # floor: keys certainly accepted before the STOP, minus one.  The consumer counter is the measure; when it did
    # not move in the editor (hardware-queue path, not counted) the last text rendered before the STOP is used.
    known = j_lo if rec['counted_at_target'] else (max(seen) if seen else 0)
    rec['floor_source'] = 'consumer counter' if rec['counted_at_target'] else 'last text rendered before the STOP (counter did not move)'
    verdict = e3_verdict(texts, shown, max(min(known, n) - 1, 0), idle=idle, stopped_lines=rec['stopped_lines'] if idle else 1)
    _shot, _s, back = X3.ide_exit(S, rid)
    rec.update(verdict, ok=False if verdict['verdict'] == 'VIOLATION' else None, matches_recorded=verdict['verdict'] == 'OK',
               reentry_text=view[0] if view else None, screen=shot1, screens=[shot0, shot1], back_at_prompt=back)
    print(f'  {rid}: {name} stop={stop} k={k} delay={delay} j=[{j_lo},{j_hi}] fits={verdict["fits"]} -> {verdict["verdict"]}', flush=True)
    return rec


def e3_row(S, rid):
    exp = SPEC[rid]['expected']
    keys, texts, stop = exp['keys'], exp['texts_after_m_keys'], exp['stop']
    base = SPEC[rid]['steps'][0].split('"')[1]
    kind = stop['stop']
    if kind in ('after-last-taken', 'idle'):
        points = [dict()]
    elif kind == 'after-k-counted':
        points = [dict(k=k) for k in stop['k']]
    elif kind == 'delay-after-last-taken':
        points = [dict(delay=d) for d in stop['delay_s']]
    elif kind == 'after-k-counted-then-delay':
        points = [dict(k=k, delay=d) for k in stop['k'] for d in stop['delay_s']]
    else:
        raise AssertionError('unknown stop spec ' + kind)
    recs = [e3_iteration(S, rid, f'{base}{i}', keys, texts, kind, idle=kind == 'idle', **p) for i, p in enumerate(points)]
    for r in recs:
        S.steps_log.append(r)
    return S.finish254(rid, recs, extra=dict(stop_method=S.stop_method, points=len(points),
                                            verdicts=[r['verdict'] for r in recs]))


def e3_pending_row(S, rid):
    exp, recs = SPEC[rid]['expected'], []
    for i, form in enumerate(exp.get('prep', [])):
        recs.append(S.table_step(rid, form, [], mark='NOT-DERIVED', tag=f'prep{i}'))
    name = [x for x in SPEC[rid]['steps'] if x.startswith('(ide ')][0].split('"')[1]
    shot0, s0 = X3.ide_enter(S, rid, name)
    for c in exp['keys']:
        S.key(c)
    inj = S.inject_stop(S.stop_method)
    s, ok = S.wait_for(stopped, limit=30)
    rec = dict(row=rid, tag='pending-cx', input='(ide "%s") %r + injected RUN/STOP, re-entry, %r' % (name, exp['keys'], exp['then']),
               mark='HOST-EXECUTED rule / device observation', capture=True, injection=inj, aborted=ok,
               stop_screen=S.save_screen(f'{rid}-stop', s), flush=S.flush_keys())
    if not ok:
        rec['cleared'] = S.clear_stop(S.stop_method)
        X3.ide_exit(S, rid)
        rec.update(ok=None, verdict='STOP-NOT-TAKEN', prompt_cleanup=S.clean_prompt())
    else:
        rec['prompt_cleanup'] = S.clean_prompt()
        shot1, _s1 = X3.ide_enter(S, rid, name)
        shot2, s2 = X3.ide_keys(S, rid, exp['then'], 'then')
        view = editor_view(s2)
        fits = [t for t in exp['texts_final'] if view and text_matches(view, t) is True]
        bad = [f for f in exp['forbid_screen'] if X3.screen_has(s2, f)]
        _shot, _s, back = X3.ide_exit(S, rid)
        good = bool(fits) and not bad
        rec.update(ok=None if good else False, matches_recorded=good, verdict='OK' if good else 'VIOLATION',
                   reentry_text=view[0] if view else None, forbidden_seen=bad, screen=shot2, screens=[shot0, shot1, shot2],
                   back_at_prompt=back)
    S.steps_log.append(rec)
    recs.append(rec)
    print(f'  {rid}: {rec["verdict"]}', flush=True)
    return S.finish254(rid, recs, extra=dict(stop_method=S.stop_method))


def gk_e3(S, sw, imgs, res):
    assert not {r['id'] for r in S.rows} & set(SEAM_ROWS), 'e3 rows refused: this boot ran a seam row'
    method = stop_probe(S)
    res['stop_method'] = method
    for rid in E3_ROWS[1:]:
        if method is None:
            S.finish254(rid, [], status=NOT_RUN, extra=dict(reason='stop-probe found no RUN/STOP stand-in for the idle editor'))
        elif SPEC[rid]['expected'].get('stop'):
            e3_row(S, rid)
        else:
            e3_pending_row(S, rid)


# ----------------------------------------------------------------- group K-seam
def seam_keys(S, rid, name, segs, recs, tag):
    """Open buffer `name`, send each key segment, check its expectations, leave with C-x q (unless a segment
    expects the prompt, i.e. the keys themselves left the editor)."""
    shot0, s = X3.ide_enter(S, rid, name)
    opened, left = in_editor(s), False
    for i, seg in enumerate(segs):
        v0 = editor_view(S.m.screen())
        codes = seg['send'] if isinstance(seg, dict) else seg
        seg = seg if isinstance(seg, dict) else {}
        shot, s = X3.ide_keys(S, rid, codes, f'{tag}{i}')
        v1 = editor_view(s)
        checks = {}
        if 'expect_text' in seg:
            checks['text'] = bool(v1) and text_matches(v1, seg['expect_text']) is True
        if seg.get('expect_text_unchanged'):
            checks['text_unchanged'] = bool(v0) and bool(v1) and v0[0] == v1[0]
        if 'expect_text_suffix' in seg:
            last = [x for x in (v1[0] if v1 else []) if x]
            checks['suffix'] = bool(last) and last[-1].endswith(seg['expect_text_suffix'].upper()) and \
                not last[-1].endswith(seg.get('forbid_text_suffix', '\x01').upper())
        if 'expect_screen' in seg:
            checks['screen'] = X3.screen_has(s, *seg['expect_screen'])
        if 'forbid_screen' in seg:
            checks['forbid_screen'] = not any(X3.screen_has(s, f) for f in seg['forbid_screen'])
        if 'expect_prompt' in seg:
            s, _ok = S.settle(secs=2.5, limit=120, cond=lambda x: L.active(x) == PROMPTS[seg['expect_prompt']])
            checks['prompt'] = left = L.active(s) == PROMPTS[seg['expect_prompt']]
        rec = dict(row=rid, tag=f'{tag}{i}', input='(ide "%s") keys %r' % (name, codes), mark='HOST-EXECUTED', capture=False,
                   ok=opened and all(checks.values()), checks=checks, text=v1[0] if v1 else None,
                   status_row=v1[2] if v1 else None, status_row_drawn=bool(v1 and v1[2]), screen=shot, screens=[shot0, shot])
        S.steps_log.append(rec)
        recs.append(rec)
        print(f'  {rid}: {"ok  " if rec["ok"] else "FAIL"} keys {codes} -> {checks}', flush=True)
    if not left:
        X3.ide_exit(S, rid)


def typed(S, rid, recs, form, tag, entry=None):
    """A typed form of a seam row: from the table when it has an expectation for it, else a harness step."""
    hit = [e for e in SPEC[rid]['expected'].get('screen') or [] if e['input'] == form]
    if hit:
        recs.append(S.table_step(rid, form, [hit[0]['screen']], mark=hit[0]['derivation']['mark'], tag=tag))
    else:
        recs.append(S.table_step(rid, form, [entry] if entry else [], mark='NOT-DERIVED', tag=tag))


def gk_seam(S, sw, imgs, res):
    assert not {r['id'] for r in S.rows} & set(E3_ROWS), 'seam rows refused: this boot ran an e3 row (key 102 may be bound)'
    typed_row(S, 'seam-prepare')
    registry_empty = S.rows[-1]['steps'][-1].get('matches_recorded')
    res['registry_empty_at_start'] = registry_empty
    rid, recs = 'seam-unbound-unknown', []
    exp = SPEC[rid]['expected']
    seam_keys(S, rid, 'sm', [exp['keys'][:2], dict(send=exp['keys'][2:], expect_screen=exp['expect_screen'], expect_text='ab')], recs, 'k')
    S.finish254(rid, recs)
    rid, recs = 'seam-bind-buffer', []
    exp = SPEC[rid]['expected']
    typed(S, rid, recs, '(ide-bind-key 102 (quote seam-bang))', 'bind')
    seam_keys(S, rid, 'sm', exp['keys'], recs, 'k')
    typed(S, rid, recs, '(ide-bind-key 102 (quote seam-hash))', 'rebind', entry='102')
    seam_keys(S, rid, 'sm', exp['after_shadow'], recs, 's')
    S.finish254(rid, recs)
    for rid in ('seam-message-result', 'seam-nil-result'):
        recs, exp = [], SPEC[rid]['expected']
        typed(S, rid, recs, exp['screen'][0]['input'], 'bind')
        seam_keys(S, rid, 'sm', exp['keys'], recs, 'k')
        S.finish254(rid, recs)
    rid, recs = 'seam-control-cancels', []
    # The table's code 8 cannot reach the product in this Xemu: `~typeone 08` is rewritten to 0x14 and `~keyevent 08 00`
    # is rejected (code 8 is not in the generated keymap).  A second segment therefore sends C-x C-o f: code 15 is
    # delivered unchanged and, like 8 and 0x14, is a non-printable code outside the C-x table (%ide-prefix-command).
    second = dict(send=[24, CONTROL_VARIANT, 102], expect_text_suffix='ff', forbid_text_suffix='#')
    seam_keys(S, rid, 'sm', list(SPEC[rid]['expected']['keys']) + [second], recs, 'k')
    S.finish254(rid, recs, extra=dict(
        transport_caution='Xemu `~typeone 08` is rewritten to 0x14 (Backspace) by the HWA fake-key encoder '
                          '(input_devices.c add_hwa_fake_key_unprotected) and `~keyevent 08 00` is rejected; the control key '
                          'of segment k0 that reaches the product is therefore 0x14, not C-h.  Segment k1 (driver addition, '
                          'not in the table) repeats the case with code 15 (C-o), which is delivered unchanged.  The '
                          'reviewer decides whether the row stands.'))
    rid, recs = 'seam-builtin-not-overridable', []
    exp = SPEC[rid]['expected']
    typed(S, rid, recs, exp['screen'][0]['input'], 'bind')
    seam_keys(S, rid, 'sm', exp['keys'], recs, 'k')
    S.finish254(rid, recs)
    typed_row(S, 'seam-registry-value')
    assert [r['id'] for r in S.rows if r['id'] in SPEC] == SEAM_ROWS, 'seam group did not run its plan in order'


# ----------------------------------------------------------------- group H-load-guard
def g_load_guard(S, sw, imgs, res):
    rid = 'save-refused-during-load'
    exp = SPEC[rid]['expected']
    image = imgs['u1']
    for f in exp['fixture_files']:
        image = F.seed_file(image, f['name'], f['content'].encode('latin1'))
    (S.out / 'image-u1self-initial.d81').write_bytes(image)
    sw.swap('u1self', image)
    recs = [S.step(rid, '(m65d-remount)', '0', limit=900, tag='remount')]
    snaps = {}
    for i, e in enumerate(exp['screen']):
        if e['input'] == '(load "self")':
            snaps['before_load'] = sha(X3.current(S))
        recs.append(S.table_step(rid, e['input'], [e['screen']], mark=e['derivation']['mark'], limit=900, tag=f'{i:02d}'))
        if e['input'] == '(load "self")':
            snaps['after_load'] = sha(X3.current(S))
    res['load_guard'] = dict(snapshots=snaps, mid_session_equal=snaps.get('before_load') == snaps.get('after_load'),
                             note='mid-session image compare is informational (the emulator may cache sectors); the '
                                  'trusted checks are the host readbacks of the final image')
    S.finish254(rid, recs, extra=dict(path='command', host_readback=['SELFOUT absent', 'SELFOK == b"one"']))


def session_disk_h(out, holder):
    result = X3.run_groups(out, 'disk-h', holder, [('H-load-guard', g_load_guard)])
    try:
        files = F.visible_files((out / 'disk-h-H-load-guard-final.d81').read_bytes())
        result['host_checks'] = [dict(row='save-refused-during-load', file='SELFOUT', ok=b'SELFOUT' not in files, present=b'SELFOUT' in files),
                                 dict(row='save-refused-during-load', file='SELFOK', ok=files.get(b'SELFOK') == b'one',
                                      got_bytes=None if b'SELFOK' not in files else len(files[b'SELFOK'])),
                                 dict(row='save-refused-during-load', file='SELF', ok=b'SELF' in files, note='fixture still present')]
    except Exception as exc:
        result['host_checks'] = [dict(row='save-refused-during-load', ok=False, error=repr(exc))]
    holder.clear()
    return result


def session_e3(out, holder):
    result = X3.run_groups(out, 'e3', holder, [('K-e3', gk_e3)], writable=False)
    holder.clear()
    return result


def session_seam(out, holder):
    result = X3.run_groups(out, 'seam', holder, [('K-seam', gk_seam)], writable=False)
    holder.clear()
    return result


# ----------------------------------------------------------------- $D703 probe (scope-254 decision D10)
def session_d703(out, holder):
    """build/scope-254-r1/save/report.txt H3: the $D700-triggered chained DMA jobs do not set the list-format bit
    $D703 themselves.  Probe: clear $D703 at the idle prompt through the monitor, then make the product run (a) a
    typed form, (b) a library load (VM code-window loads = the chained jobs).  A hang or crash proves the
    dependency; survival with the bit still 0 at the trigger refutes it for these paths.  Capture row, UNREVIEWED."""
    S = Session(out, 'd703', writable=False, timeout=1800)
    holder.append(S)
    S.start()
    rid, recs = D703_ROW, []
    recs.append(S.table_step(rid, '(+ 1 2)', ['3'], mark='HOST-EXECUTED', tag='control'))
    before = S.m.memory_range(D703_LINEAR, 1)[0]
    observation = 'SURVIVED'
    try:
        w1 = S.poke(D703_LINEAR, 0)
        r = S.table_step(rid, '(+ 3 4)', ['7'], mark='NOT-DERIVED', limit=120, tag='typed-after-clear')
        r.update(d703_before=before, d703_write=w1, d703_after=S.m.memory_range(D703_LINEAR, 1)[0])
        recs.append(r)
        D.send_counted(S.m, ['(load-lib "ide")'], S.taken_addr, timeout=120)   # typed, Return not yet sent
        w2 = S.poke(D703_LINEAR, 0)
        r = S.table_step(rid, '', ['T'], mark='NOT-DERIVED', limit=900, tag='load-lib-after-clear')
        r.update(input='(load-lib "ide") with $D703 cleared immediately before Return', d703_write=w2,
                 d703_after=S.m.memory_range(D703_LINEAR, 1)[0])
        recs.append(r)
        recs.append(S.table_step(rid, '(+ 4 5)', ['9'], mark='NOT-DERIVED', limit=120, tag='alive'))
        applied = w1['readback'] == 0 and w2['readback'] == 0
        if not applied:
            observation = 'NOT-APPLIED (the monitor write to $D703 did not read back 0: the probe proves nothing)'
    except X3.ProductHang as exc:
        observation = 'HANG-OR-CRASH after $D703 was cleared: ' + str(exc)
        recs.append(dict(exc.rec, ok=None, capture=True, matches_recorded=False))
        applied = True
    S.finish254(rid, recs, extra=dict(observation=observation, d703_at_boot_prompt=before, write_applied=applied,
                                     source='build/scope-254-r1/save/report.txt H3; build/scope-254-r1/report.txt D10',
                                     note='a hang here is the finding, not a tool failure; the row is never PASS/FAIL by itself'))
    return dict(observation=observation)


# ----------------------------------------------------------------- regression sessions (2.5.3 tables)
def session_reg_repl(out, holder):
    S = Session(out, 'reg-repl', writable=False)
    holder.append(S)
    S.start()
    X3.row_lcc_and_repl(S)
    X3.row_f2_ladder(S)
    return {}


def session_reg_oom_b(out, holder):
    """Row oom-repl-global with the typing-tolerant harness of 2.5.3 r8 (method and name of
    build/card-253-rows-r8/tools/oomb.py, record build/card-253-rows-r8/oom-b).  Reason, as there: on the full
    heap the product reports OUT OF MEMORY while the drop form is still being typed, the key counter then moves
    by more than one and the strict transport of reg-oom halts ('unexpected extra input consumption').  Here every
    key goes through Session.key (no delta == 1 assertion) and the outcome of each attempt is read from the
    screen.  Capture only: the row is UNREVIEWED whatever it shows.  Not part of `all`."""
    S = Session(out, 'reg-oom-b', writable=False, timeout=3600)
    holder.append(S)
    S.start()
    rid, recs, oom = 'oom-repl-global-b', [], '*** VM: OUT OF MEMORY'

    def tol(text, tag, limit=150):
        before, t0 = S.m.screen(), time.monotonic()
        for ch in text:
            S.key(ord(ch))
        S.key(13)
        s, stable = S.settle(secs=3, limit=limit, cond=lambda s: L.active(s) == C)
        seg = S.segment(s, text)
        if seg is None:
            seg = L.new_lines(before, s)
        ls = [x.replace('{$A0}', ' ').rstrip() for x in L.lines(s)]
        rec = dict(row=rid, tag=tag, input=text, ok=None, capture=True, prompt_back=L.active(s) == C, settled=stable,
                   result_lines=[x for x in seg if x.strip()],
                   full_echo_seen=any(x.upper().startswith(('L65> ' + text).upper()) for x in ls),
                   oom_in_segment=sum(oom in x for x in seg), screen=S.save_screen(f'{rid}-{tag}', s),
                   seconds=round(time.monotonic() - t0, 1))
        S.steps_log.append(rec)
        recs.append(rec)
        print(f'  {rid}: seen {text[:70]!r} -> {rec["result_lines"][-3:]}', flush=True)
        return rec
    tol('(setq l nil)', 'init')
    tol('(while t (setq l (cons 1 l)))', 'fill', limit=600)
    for i in range(3):
        tol('(+ 1 2)', f'full{i}')
    dropped, attempts = False, 0
    for i in range(8):
        attempts = i + 1
        r = tol(('(setq l nil)', '(setq l nil)', '(set-symbol-value (quote l) nil)')[i % 3], f'drop{i}')
        if r['prompt_back'] and 'NIL' in r['result_lines'] and r['full_echo_seen']:
            dropped = True
            break
    if dropped:
        tol('(length (list 1 2 3))', 'recovered')
        tol('(+ 3 4)', 'alive')
    S.finish_row(rid, recs, status=REVIEW, extra=dict(
        dropped=dropped, drop_attempts=attempts, method='build/card-253-rows-r8/tools/oomb.py (typing-tolerant harness)',
        control_253_r8=dict(record='build/card-253-rows-r8/oom-b/result.json', dropped=False, drop_attempts=8)))
    return dict(dropped=dropped, drop_attempts=attempts)


def _host_readbacks(out, gname, checks, name='disk'):
    """c253 session_disk reads the final image of every group; with --groups the unselected ones do not exist."""
    if X3.GROUP_FILTER and gname not in X3.GROUP_FILTER:
        return [dict(group=gname, skipped='group not selected by --groups', rows=sorted({c[0] for c in checks}))]
    return _STOCK_HOST_READBACKS(out, gname, checks, name)


_STOCK_HOST_READBACKS = X3.host_readbacks
X3.host_readbacks = _host_readbacks


SESSIONS = {'repl': session_repl, 'lib1': session_lib1, 'oom-rp1': session_oom_rp1, 'e3': session_e3, 'seam': session_seam,
            'disk-h': session_disk_h, 'd703': session_d703, 'reg-repl': session_reg_repl,
            'reg-disk': X3.session_disk, 'reg-ide': X3.session_ide, 'reg-oom': X3.session_oom}
assert list(SESSIONS) == ORDER
EXTRA_SESSIONS = {'reg-oom-b': session_reg_oom_b}      # only when named; `all` and the plan are unchanged


# ----------------------------------------------------------------- receipts
def bind_input(path):
    """Binding of an INPUT (never of a file this tool writes)."""
    path = Path(path)
    raw = path.read_bytes()
    name = str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)
    return dict(path=name, bytes=len(raw), sha256=sha(raw))


def self_bindings(value, forbidden):
    """Every {path, sha256} row whose path lies below one of the `forbidden` directories (written by this tool)."""
    found = []
    if isinstance(value, dict):
        if {'path', 'sha256'} <= value.keys():
            p = Path(value['path'])
            p = p if p.is_absolute() else ROOT / p
            if any(p == f or f in p.parents for f in forbidden):
                found.append(value['path'])
        for child in value.values():
            found += self_bindings(child, forbidden)
    elif isinstance(value, list):
        for child in value:
            found += self_bindings(child, forbidden)
    return found


def tool_inputs():
    names = ['c254_rows.py', 'c254_emulator.py', 'c254_final_pins.py', 'c254_rows_20261004.json', 'c253_rows.py',
             'c253_rows_20261001.json', 'c253_rows_r8_20261003.json', 'comfort_default_rows.py', 'comfort_library_rows.py',
             'dwx_retroactive_red_replay.py', 'dwx_mirrored_prefilter_rows.py', 'd81_persistence_fault.py',
             'm65d_blank_d81_oracle.py', 'elf_truth.py']
    return [bind_input(TOOLS / n) for n in names if (TOOLS / n).is_file()]


def classify(rows):
    return {r['id']: r['status'] for r in rows}


def verdict_of(statuses, errors):
    values = [s for per in statuses.values() for s in per.values()]
    if errors or any(v in (FAIL, 'FAIL-NO-DROP') for v in values):
        return 'FAIL'
    if any(v in (REVIEW, NOT_RUN) for v in values):
        return 'INCOMPLETE: rows await review (UNREVIEWED) or did not run -- NOT a pass'
    return 'PASS' if values else 'EMPTY'


def run(a):
    global KEEP_SCRATCH
    assert WORLD.get('medium') and WORLD.get('label'), 'no world bound: start through c254_emulator.py new'
    KEEP_SCRATCH = a.keep_scratch
    names = ORDER if a.session == 'all' else a.session.split(',')
    known = {**SESSIONS, **EXTRA_SESSIONS}
    assert names and all(n in known for n in names) and len(set(names)) == len(names), ('unknown or repeated session', names)
    X3.GROUP_FILTER.clear()
    X3.GROUP_FILTER.extend([g for g in a.groups.split(',') if g])
    assert not X3.GROUP_FILTER or len(names) == 1 and names[0] in ('reg-disk', 'reg-ide'), '--groups needs exactly one of reg-disk / reg-ide'
    out = ROOT / 'build' / a.out
    assert out.parent.is_relative_to(ROOT / 'build') and not out.name.startswith(SCRATCH_PREFIX)
    out.mkdir(parents=True, exist_ok=False)
    inputs = dict(medium=bind_input(WORLD['medium']), ELF=bind_input(WORLD['elf']), xemu=bind_input(L.XEMU), rom=bind_input(X3.ROM),
                  table=bind_input(TABLE), tools=tool_inputs(),
                  sd_image=dict(name=str(X3.SDIMG), bytes=X3.SDIMG.stat().st_size, note='not hashed (system SD image; each boot uses a copy)'))
    assert inputs['medium']['sha256'] == WORLD['medium_sha'] and inputs['ELF']['sha256'] == WORLD['elf_sha']
    print(json.dumps(dict(format=FORMAT, world=WORLD['label'], table_sha256=TABLE_SHA256, sessions=names,
                          review_set=len(REVIEW_SET), not_derived_texts=NOT_DERIVED_TEXTS), indent=1), flush=True)
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
                drop_scratch()
            # a group that did not finish is an error of the run (run card-254-rows-r1 lost five groups silently)
            lost = {g: v.get('error') or v.get('status') for g, v in ((result or {}).get('groups') or {}).items() if v.get('status') != 'DONE'}
            if lost:
                error = '; '.join(filter(None, [error, 'GROUPS NOT DONE ' + json.dumps(lost, sort_keys=True)]))
            # the c253 session functions name their files 'disk' / 'ide' / 'oom'
            rows_file = sub / (f'{nm[4:]}-rows.json' if nm in ('reg-disk', 'reg-ide', 'reg-oom') else f'{nm}-rows.json')
            rows = json.loads(rows_file.read_text()) if rows_file.exists() else []
            statuses = classify(rows)
            for rid in PLAN.get(nm, []):
                statuses.setdefault(rid, NOT_RUN)
            entry = dict(error=error, rows=statuses, result=result, outputs=outputs)
            if S is not None:
                entry.update(boot=getattr(S, 'boot', None), counted_keys=S.counted_keys, blind_keys=S.blind_keys)
            if error:
                errors[nm] = error
            summary['sessions'][nm] = entry
            (sub / 'session.json').write_text(json.dumps(entry, indent=1) + '\n')
    finally:
        drop_scratch()
    statuses = {k: v['rows'] for k, v in summary['sessions'].items()}
    boots = [dict(session=b['session'], xemu_pid=b['xemu_pid'], scratch=b['scratch'], exit_status=b['exit_status'],
                  rows=[r['id'] for r in b['rows']]) for b in Session.boots]
    e3_boots = {b['scratch'] for b in boots if set(b['rows']) & set(E3_ROWS)}
    seam_boots = {b['scratch'] for b in boots if set(b['rows']) & set(SEAM_ROWS)}
    assert not e3_boots & seam_boots, 'e3 and seam rows shared a boot'
    receipt = dict(format=FORMAT, world=WORLD['label'], transport=TRANSPORT, continues=a.continues or None,
                   inputs=inputs, sessions=statuses, errors=errors, boots=boots,
                   separate_boots=dict(e3=sorted(e3_boots), seam=sorted(seam_boots), disjoint=True),
                   unreviewed={rid: review_reasons(rid) if rid in SPEC or rid == D703_ROW else ['c253 status']
                               for per in statuses.values() for rid, st in per.items() if st == REVIEW},
                   counts={st: sum(1 for per in statuses.values() for v in per.values() if v == st)
                           for st in sorted({v for per in statuses.values() for v in per.values()})},
                   verdict='CONTROL RUN on the 2.5.3 Seed r8 (not a product verdict)' if WORLD['label'] != 'seed' else verdict_of(statuses, errors),
                   written=sorted(str(p.relative_to(out)) for p in out.rglob('*') if p.is_file()),
                   note='`written` lists files of this run by name only; no file written by this tool is bound by hash')
    summary['receipt'] = 'receipt.json'
    own = [out] + [ROOT / 'build' / b['scratch'] for b in boots]
    bad = self_bindings(receipt, own) + self_bindings(summary, own)
    assert not bad, ('receipt binds a path this tool writes', bad[:5])
    (out / 'summary.json').write_text(json.dumps(summary, indent=1) + '\n')
    (out / 'receipt.json').write_text(json.dumps(receipt, indent=1) + '\n')
    print(json.dumps(dict(sessions=statuses, counts=receipt['counts'], verdict=receipt['verdict']), indent=1))
    return 1 if errors else (2 if receipt['verdict'] == 'FAIL' else 0)


# ----------------------------------------------------------------- plan / review / timing / selftest
def plan():
    rows = []
    for nm in ORDER:
        for rid in (PLAN.get(nm) and _order(nm)) or []:
            rows.append(dict(session=nm, row=rid, automatic_pass_possible=not review_reasons(rid),
                             not_derived_texts=0 if rid == D703_ROW else sum(1 for _, m in marks(SPEC[rid]) if m == 'NOT-DERIVED')))
    return dict(format=FORMAT, table=bind_input(TABLE), sessions=ORDER, boots_per_session={
        **{k: 1 for k in PLAN}, 'reg-repl': 1, 'reg-disk': 8, 'reg-ide': 4, 'reg-oom': 1}, rows=rows,
        review_set=len(REVIEW_SET), automatic_pass_possible=sorted(set(SPEC) - set(REVIEW_SET)),
        not_derived_texts=NOT_DERIVED_TEXTS, regression='2.5.3 tables through c253_rows (29 table rows + harness rows) with %d override(s)'
        % sum(len(v) for v in DOC['expected_overrides']['rows'].values()))


def review(a):
    """Reviewer decision on a finished run.  FILE = {"reviewer": ..., "date": ..., "rows": {id: {"verdict": "ACCEPT"|"REJECT",
    "note": ...}}}.  ACCEPT turns UNREVIEWED into PASS; REJECT into FAIL; anything else stays as it is."""
    run_dir, out = (ROOT / a.run).resolve(), ROOT / 'build' / a.out
    assert run_dir.is_relative_to(ROOT / 'build') and (run_dir / 'receipt.json').is_file()
    doc = json.loads(Path(a.review).read_text())
    assert doc.get('reviewer') and doc.get('date') and isinstance(doc.get('rows'), dict)
    receipt = json.loads((run_dir / 'receipt.json').read_text())
    assert receipt['format'] == FORMAT and receipt['world'] == 'seed', 'only a Seed-world run can be reviewed'
    final, unknown = {}, set(doc['rows'])
    for nm, per in receipt['sessions'].items():
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
    result = dict(format='card254-rows-review-v1', run=dict(name=str(run_dir.relative_to(ROOT)), receipt_sha256=sha((run_dir / 'receipt.json').read_bytes())),
                  reviewer=doc['reviewer'], date=doc['date'], decisions=doc['rows'], rows=final,
                  still_unreviewed=sorted(r for r, s in final.items() if s == REVIEW),
                  verdict=verdict_of(dict(all=final), receipt['errors']))
    (out / 'reviewed.json').write_text(json.dumps(result, indent=1) + '\n')
    return result


# numeric form of DOC['timing_rules']['rules'] (the strings are asserted so the two cannot drift apart)
TIMING = {'ide-save-20x40': ('save', 0.35, 20, 'save step <= 0.35 x control AND <= 20 s wall'),
          'ide-save-50x40': ('save', 0.30, 30, 'save step <= 0.30 x control AND <= 30 s wall'),
          'ide-save-100x20': ('save', 0.30, 30, 'save step <= 0.30 x control AND <= 30 s wall'),
          'eval-buffer-50': ('eval', 0.75, 150, 'eval step <= 0.75 x control AND <= 150 s wall')}
assert all(DOC['timing_rules']['rules'][k].startswith(v[3]) for k, v in TIMING.items()), 'timing rule text drift'


def timing_verdicts(rows, control):
    """rows / control = lists of row records (reg-disk-rows.json) of the Seed run and of the 2.5.3 control run."""
    def step(recs, rid, tag):
        hit = [s for r in recs if r['id'] == rid for s in r['steps'] if s.get('tag') == tag]
        return hit[0] if len(hit) == 1 else None
    out = {}
    for rid, (tag, ratio, cap, text) in TIMING.items():
        new, old = step(rows, rid, tag), step(control, rid, tag)
        if new is None or old is None or not old.get('seconds'):
            out[rid] = dict(verdict='NO-CONTROL' if new is not None else 'NOT RUN', rule=text)
            continue
        r = new['seconds'] / old['seconds']
        cyc = (new['cycles_to_result'] / old['cycles_to_result']) if new.get('cycles_to_result') and old.get('cycles_to_result') else None
        out[rid] = dict(rule=text, seconds=new['seconds'], control_seconds=old['seconds'], ratio=round(r, 3),
                        cycles_ratio=round(cyc, 3) if cyc else None, step_ok=bool(new.get('ok')),
                        verdict='TIMING-PASS' if (r <= ratio and new['seconds'] <= cap and new.get('ok')) else 'TIMING-FAIL')
    return out


def timing(a):
    def load(name):
        p = (ROOT / name).resolve()
        assert p.is_relative_to(ROOT / 'build')
        return json.loads((p / 'reg-disk/disk-rows.json').read_text())
    return dict(format='card254-rows-timing-v1', run=a.run, control=a.control, rules=timing_verdicts(load(a.run), load(a.control)),
                note='wall seconds of an emulator that runs -sleepless; the ratio to the same-session control is the measure')


def selftest():
    log = []
    # 1. review policy: no automatic PASS for any row of the review set, whatever the steps say
    good = [dict(ok=True)]
    for rid in SPEC:
        st = status_of(rid, good)
        assert (st == PASS) == (rid not in REVIEW_SET), rid
        assert status_of(rid, [dict(ok=True), dict(ok=False)]) == FAIL
        assert status_of(rid, [dict(ok=None, matches_recorded=True)]) == REVIEW
    assert status_of(D703_ROW, good) == REVIEW
    log.append('review policy: %d of 33 rows can never pass automatically; a capture step never passes; FAIL wins' % len(REVIEW_SET))
    log.append('rows with an automatic PASS: ' + ', '.join(sorted(set(SPEC) - set(REVIEW_SET))))
    # 2. census
    assert NOT_DERIVED_TEXTS == 26 and all(any(m == 'NOT-DERIVED' for _, m in marks(SPEC[r])) or SPEC[r].get('host_first')
                                           or SPEC[r]['driver'] in ('stop', 'e3', 'keyseq') for r in REVIEW_SET)
    log.append('26 NOT-DERIVED texts, 26 host_first rows: all inside the review set')
    # 3. separate boots
    assert not set(PLAN['e3']) & set(PLAN['seam']) and 'e3-pending-cx-reset-bound' in PLAN['e3'] and 'seam-registry-value' in PLAN['seam']
    log.append('e3 (10 rows) and seam (8 rows) are different sessions = different boots')
    # 4. override seam
    hit = [e for e in X3.SPEC['lcc-ladder-host-only']['expected']['screen'] if 'funcall' in e['input'] and e['input'].count('(+ 1') == 6]
    assert len(hit) == 1 and hit[0]['screen'] == '7'
    log.append('expected override applied to the 2.5.3 table in memory (upvalue-setq, 6 pluses -> 7)')
    # 5. editor screen reading
    def ide(lines, status='-- E3A * {L}1 -- 693/1008'):
        return '\n'.join(lines + [''] * (24 - len(lines)) + [status])
    v = editor_view(ide(['abc{$A0}']))
    assert v[0][0] == 'ABC' and v[1] == 0 and text_matches(v, 'abc') is True and text_matches(v, 'ab') is False
    assert text_matches(v, 'abc\n') is False
    v = editor_view(ide(['ab', '{$A0}']))
    assert text_matches(v, 'ab\n') is True and text_matches(v, 'ab') is False and text_matches(v, 'ab\nc') is False
    v = editor_view(ide(['{flon}b', 'cd']))
    assert text_matches(v, 'ab\ncd') is None and text_matches(v, 'ab\nc') is False and text_matches(v, 'xb\ncd') is None
    v = editor_view(ide(['{$A0}']))
    assert text_matches(v, '') is True and text_matches(v, 'a') is False
    assert editor_view('L65> (+ 1 2)\n3\nL65>') is None
    # status row not redrawn on re-entry (trailing blank rows dropped by the dump): still an IDE screen
    v = editor_view('ab!!{$A0}')
    assert v is not None and v[2] is None and text_matches(v, 'ab!!') is True
    assert editor_view('-- E3A0 * {L}1 -- 693/08\n*** STOPPED (RUN/STOP)\n\nL65> {$A0}') is None    # screen after an abort
    assert editor_view('T- SM * {L}1 -- 698/1008\nL65> {$A0}') is None                                # screen after C-x q
    assert editor_view(ide(['ab{$A0}'], status='-- SM * UNKNOWN COMMAND {L}1 -- 698/1008'))[2].startswith('-- SM * UNKNOWN COMMAND')
    log.append('editor text reading: cursor cell, wildcard cell, trailing-newline visibility')
    # 6. E3 rule
    T = ['', 'a', 'ab', 'abc']
    sh = lambda text: [text == t for t in T]                      # noqa: E731
    assert e3_verdict(T, sh('abc'), 2)['verdict'] == 'OK' and e3_verdict(T, sh('ab'), 2)['verdict'] == 'OK'
    assert e3_verdict(T, sh('a'), 2)['verdict'] == 'VIOLATION' and e3_verdict(T, sh(''), 2)['verdict'] == 'VIOLATION'
    assert e3_verdict(T, [False] * 4, 0)['verdict'] == 'VIOLATION'
    assert e3_verdict(T, [False, False, None, False], 2)['verdict'] == 'AMBIGUOUS'
    assert e3_verdict(T, sh('abc'), 2, idle=True)['verdict'] == 'OK' and e3_verdict(T, sh('ab'), 2, idle=True)['verdict'] == 'VIOLATION'
    assert e3_verdict(T, sh('abc'), 2, idle=True, stopped_lines=2)['verdict'] == 'VIOLATION'
    B = SPEC['e3-stop-backspace-mix']['expected']['texts_after_m_keys']
    assert e3_verdict(B, [t == 'abc' for t in B], 4)['verdict'] == 'OK' and e3_verdict(B, [t == 'ab' for t in B], 4)['verdict'] == 'VIOLATION'
    log.append('E3 rule: j-1 / j accepted, fewer = VIOLATION, lost batch = VIOLATION, idle = full text and one STOPPED line')
    # 7. receipts bind no written path
    out = ROOT / 'build' / 'c254-selftest-never-created'
    assert self_bindings(dict(a=[dict(path=str(out / 'x.txt'), sha256='0' * 64)]), [out]) == [str(out / 'x.txt')]
    assert self_bindings(dict(inputs=dict(table=bind_input(TABLE)), written=['repl/repl-rows.json']), [out]) == []
    log.append('receipt check: a {path, sha256} row below the output directory is refused; inputs and names are not')
    # 8. timing rule
    def rows_(sec, cyc):
        return [dict(id='ide-save-20x40', steps=[dict(tag='load', seconds=9), dict(tag='save', seconds=sec, cycles_to_result=cyc, ok=True)])]
    assert timing_verdicts(rows_(10, 100), rows_(46.1, 1000))['ide-save-20x40']['verdict'] == 'TIMING-PASS'
    assert timing_verdicts(rows_(25, 100), rows_(100, 1000))['ide-save-20x40']['verdict'] == 'TIMING-FAIL'      # over the 20 s cap
    assert timing_verdicts(rows_(18, 100), rows_(46.1, 1000))['ide-save-20x40']['verdict'] == 'TIMING-FAIL'     # ratio 0.39
    assert timing_verdicts(rows_(10, 100), [])['ide-save-20x40']['verdict'] == 'NO-CONTROL'
    log.append('timing rules: ratio and cap, no control = no verdict')
    # 9. the oracle world of the table is the pinned product world of the Seed config
    import c254_config as CFG
    assert {k: list(v) for k, v in CFG.CANDIDATE_BLOBS.items()} == DOC['oracle']['candidate_blobs'], 'oracle images differ from the config pins'
    assert {k: list(v) for k, v in CFG.PACKAGE_BLOBS.items()} == DOC['oracle']['package_blobs'], 'oracle packages differ from the config pins'
    log.append('oracle world of the table == CANDIDATE_BLOBS / PACKAGE_BLOBS of c254_config (the Seed preflight asserts the same pins)')
    # 10. patient transport against a slow peer: one connection, the command sent once, the late reply received
    import threading
    with tempfile.TemporaryDirectory(dir=ROOT / 'build', prefix=SCRATCH_PREFIX + 'selftest-') as box:
        path, seen = Path(box) / 'm.sock', []
        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server.bind(str(path))
        server.listen(4)
        server.settimeout(10)

        def peer():
            conn, _ = server.accept()
            seen.append(conn.recv(100))
            time.sleep(0.9)                 # longer than the 0.5 s after which the stock transport closes and resends
            conn.sendall(b'~screen\r\nLATE\n.\r\n')
            conn.close()
        thread = threading.Thread(target=peer)
        thread.start()
        monitor = _MONITOR.__new__(_MONITOR)
        monitor.path = path
        reply = monitor.command('~screen')
        thread.join()
        server.close()
        assert _MONITOR.command is patient_command and seen == [b'~screen\r'] and 'LATE' in reply, (seen, reply)
        try:
            monitor.command('~screen', timeout=0.2)     # no listener any more: the refusal is reported, nothing hangs
            raise AssertionError('a dead peer was not reported')
        except L.R.ROWS.RowError as error:
            assert 'UART monitor command failed: ~screen' in str(error)
    log.append('patient transport: a reply 0.9 s late is received on the first connection, no resend; a dead peer is a RowError')
    return dict(status='PASS', checks=log, emulator='NOT RUN (no emulator code path is exercised by this selftest)')


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest='mode', required=True)
    r = sub.add_parser('run')
    r.add_argument('out')
    r.add_argument('--session', default='all', help='all, or comma separated: ' + ', '.join(ORDER + list(EXTRA_SESSIONS)))
    r.add_argument('--groups', default='', help='reg-disk / reg-ide only: comma separated c253 group names')
    r.add_argument('--keep-scratch', action='store_true')
    r.add_argument('--continues', default='', help='name of the run this one continues (recorded in the receipt)')
    sub.add_parser('plan')
    sub.add_parser('selftest')
    v = sub.add_parser('review')
    v.add_argument('run')
    v.add_argument('--review', required=True)
    v.add_argument('--out', required=True)
    t = sub.add_parser('timing')
    t.add_argument('run')
    t.add_argument('--control', required=True)
    a = p.parse_args(argv)
    if a.mode == 'run':
        return run(a)
    print(json.dumps(dict(plan=plan, selftest=selftest, review=lambda: review(a), timing=lambda: timing(a))[a.mode](), indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main())
