#!/usr/bin/env python3
"""2.5.3 M65D disk integrity host gate (D2/D4 ownership check, D3 lossless load, D5 full directory).

Compiles the live lib/m65-disk.lisp and lib/ide-disk.lisp (with the resident
helpers they need) through the host compiler and runs them in the host VM on
complete D81 byte images.  Reads only; writes nothing.

  d3d5      D3 load/save byte round trip and D5 full-directory remount (37 cases).
  d2d4      Representative subset of the card-253 D2/D4 cut-point matrix:
            clean controls never refused; every cut/fail/postfail point of the
            new1 and replace1 transactions; the new700 leak points; ownership
            corruption, abort/retry, stale-status, swap and recovery rows.  Any
            inconsistent image must remount 13 (latched, zero writes, the next
            save writes nothing); any consistent one must remount 0.
  selftest  The gate discriminates: with the ownership comparison disabled in
            the source, a leak and a live-free block are no longer refused.
  check     d3d5 + d2d4.

The full 287-row matrix lives in build/card-253-disk-d2d4-r1/harness.
"""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.dont_write_bytecode = True
sys.setrecursionlimit(100000)
sys.path.insert(0, str(ROOT / 'tools/host-lisp'))
import bytecode_p0 as B  # noqa: E402
import bytecode_p0_compiler as C  # noqa: E402
import d81_persistence_fault as D  # noqa: E402
import m65d_blank_d81_oracle as O  # noqa: E402

SOURCES = ['lib/prelude-m1.lisp', 'lib/stdlib-bytecode-bridges.lisp', 'lib/stdlib-einsuite-bridges.lisp',
           'lib/runtime-core.lisp', 'lib/stdlib-lists.lisp', 'lib/stdlib-strings.lisp', 'lib/stdlib-load.lisp',
           'lib/m65-disk.lisp', 'lib/ide-buffer.lisp', 'lib/ide-disk.lisp']
LEDGER = json.loads((ROOT / 'config/bytecode-abi-ledger.json').read_text())
OWN_CMP_OK = '(= (+ (%disk-byte off) (%buffer-read 2 own (+ off shift))) 255))'


class Cut(Exception):
    pass


class World:
    def __init__(self, overrides=None):
        kw = dict(strict_arity=True, abi_profile='dialect-v2', abi_ledger=LEDGER, prebuilt_primitives=True)
        self.heap = C.prepare_heap([]); self.directory = {}; self.names = {}
        for path in SOURCES:
            text = (ROOT / path).read_text()
            for old, new in (overrides or {}).get(path, []):
                if old not in text:
                    raise SystemExit('selftest mutation anchor missing in %s' % path)
                text = text.replace(old, new)
            for form in C.parse_all(text):
                if isinstance(form, list) and form[0] == 'defun':
                    self._add(*C.compile_top_form_with_helpers(form, self.heap, **kw))
        for source in ['(defun string->list (s) (%string-codes s))', '(defun list->string (s) (%string-from-codes s))']:
            self._add(*C.compile_top_form_with_helpers(C.parse_one(source), self.heap, **kw))

    def _add(self, name, code, helpers):
        for n, c in [(name, code)] + helpers:
            self.directory[self.heap.intern(n)] = c; self.names[id(c)] = n

    def vm(self, image, **kw):
        return DiskVM(self, image, **kw)


class DiskVM(B.P0VM):
    def __init__(self, world, image, cut=None, fail=None, postfail=None):
        self.world = world; self.image = bytearray(image)
        self.cut = cut; self.fail = fail; self.postfail = postfail; self.writes = []
        super().__init__(heap=world.heap.clone(), directory=world.directory, code_names=world.names,
                         max_steps=60000000, abi_profile='dialect-v2', abi_ledger=LEDGER)

    def _disk_read_sector_impl(self, t, s):
        if not (1 <= t <= 80 and 0 <= s < 40):
            return False
        self.disk_buf = list(D.get_sector(self.image, t, s)); return True

    def _disk_write_sector(self, t, s):
        self.io_counters['disk_write'] += 1; n = self.io_counters['disk_write']
        if n == self.fail:
            return False
        off = D.sector_offset(t, s); self.image[off:off + 256] = bytes(self.disk_buf)
        self.writes.append((t, s, bytes(self.disk_buf)))
        if n == self.cut:
            raise Cut(n)
        return n != self.postfail

    def call(self, name, *args):
        return self.run(self.world.directory[self.heap.intern(name)], list(args))

    def text(self, s):
        return self.heap.string_from_text(s)

    def st(self, obj):
        return B.fixval(obj) if B.is_fix(obj) else self.heap.obj_to_text(obj)

    def remount(self):
        return self.st(self.call('m65d-remount'))

    def save(self, name, data):
        return self.st(self.call('m65d-save', self.text(name), self.text(data)))

    def latched(self):
        return self.call('%m65d-latched-p') != B.NIL

    def lines(self, name):
        r = self.call('%ide-disk-read-lines', self.text(name)); out = []
        if r == B.NIL:
            return None
        while r != B.NIL:
            c = self.heap.cell(r); out.append(bytes(ord(ch) for ch in self.heap.string_to_text(c.a))); r = c.b
        return out


def blank(n=1):
    im = D.blank_image(n); h = D.sector_offset(40, 0); v = O.blank_user_image(); im[h:h + 256] = v[h:h + 256]
    return bytes(im)


def seeded(n, dirs, size=None):
    im = blank(dirs)
    for i in range(n):
        im = D.seed_file(im, 'f%03d' % i, ('OLD%03d' % i).encode() if size is None else D.payload(size, i))
    return im


def payload_of(im, name):
    for s in D.directory_slots(im):
        if s.record[2] and D.entry_name(s.record).decode('ascii').lower() == name:
            return D.read_record_payload(im, s.record)
    return None


def chain_of(im, name):
    slot = next(s for s in D.directory_slots(im) if D.entry_name(s.record) == name.upper().encode())
    return slot, D.file_chain(im, slot.record)


def consistent(im):
    owners = {}
    try:
        D.validate_bam(im)
        for slot in D.directory_slots(im):
            if slot.record[2]:
                D.read_record_payload(im, slot.record)
                for ts in D.file_chain(im, slot.record):
                    owners[ts] = owners.get(ts, 0) + 1
    except Exception:
        return False
    return set(owners) == D.allocated_sectors(im) and all(v == 1 for v in owners.values())


class Report:
    def __init__(self):
        self.rows = 0; self.fails = []

    def check(self, label, ok, detail=''):
        self.rows += 1
        if not ok:
            self.fails.append(label)
            print('FAIL', label, detail, flush=True)


# --------------------------------------------------------------------- D3/D5
D3_FIX = {
    'plain': b'abc', 'trailing-spaces-and-empty-lines': b'abc  \n\n', 'only-trailing-spaces': b'abc     ',
    'single-space': b' ', 'space-lines': b'  \n  \n', 'cr-inside': b'abc\rdef', 'cr-trailing': b'abc\r',
    'crlf': b'a\r\nb\r\n', 'lone-cr-mix': b'\r\rx\r\n\r', 'only-newlines': b'\n\n\n', 'one-newline': b'\n',
    'line-254': b'x' * 254, 'line-255': b'y' * 255, 'line-256': b'z' * 256,
    'line-300': bytes(range(33, 127)) * 4, 'line-600-spaces-tail': b'q' * 590 + b' ' * 10,
    'two-long-lines': (b'a' * 300) + b'\n' + (b'b' * 260) + b'  \n', 'len-508': b'k' * 508,
    'len-509-nl-tail': b'k' * 507 + b'\n\n', 'high-bytes': bytes([200, 13, 32, 10, 255, 32]),
    'lisp-literal-spaces': b'(print "a  \r\n  b")  \n',
}


def run_d3d5(w, rep):
    for label, data in D3_FIX.items():
        im = D.seed_file(blank(1), 'f', data)
        vm = w.vm(im); ls = vm.lines('f')
        exact = ls is not None and b'\n'.join(ls) == data and ls == data.split(b'\n')
        joined = vm.call('%ide-join', vm.call('%ide-disk-read-lines', vm.text('f')))
        st = vm.remount(); sv = vm.st(vm.call('m65d-save', vm.text('f'), joined))
        rep.check('D3 roundtrip ' + label, exact and st == 0 and sv == 0 and payload_of(bytes(vm.image), 'f') == data,
                  'lines=%s remount=%s save=%s' % (None if ls is None else len(ls), st, sv))
    im = bytearray(D.seed_file(blank(1), 'e', b'x'))
    for s in D.directory_slots(im):
        if s.record[2]:
            im[D.sector_offset(s.record[3], s.record[4]) + 1] = 1
    vm = w.vm(im); ls = vm.lines('e')
    rep.check('D3 empty file loads as one empty line', ls == [b''], repr(ls))
    joined = vm.call('%ide-join', vm.call('%ide-disk-read-lines', vm.text('e')))
    vm.remount(); st = vm.st(vm.call('m65d-save', vm.text('e'), joined))
    rep.check('D3 empty buffer save refused (status 3)', st == 3, 'status=%s' % st)
    vm = w.vm(D.seed_file(blank(1), 'legacy', b'(a)\n' + b' ' * 100))
    rep.check('D3 padded slot keeps padding', vm.lines('legacy') == [b'(a)', b' ' * 100])
    vm = w.vm(D.seed_file(blank(1), 'src', b'(+ 1 2)  \r\n\r\n'))
    rep.check('D3 read-string returns full text', vm.call('%ide-disk-read-string', vm.text('src')) != B.NIL)
    full = seeded(144, 18)
    vm = w.vm(full); st = vm.remount()
    rep.check('D5 full144 remount ok', st == 0 and not vm.writes, 'status=%s' % st)
    s = vm.save('f001', 'NEWCONTENT'); files = D.visible_files(bytes(vm.image))
    rep.check('D5 full144 replace existing ok',
              s == 0 and len(files) == 144 and payload_of(bytes(vm.image), 'f001') == b'NEWCONTENT', 'save=%s' % s)
    s = vm.save('brandnew', 'x')
    rep.check('D5 full144 new name refused with 5', s == 5 and len(D.visible_files(bytes(vm.image))) == 144, s)
    vm = w.vm(full); r = vm.call('dir'); n = 0
    while r != B.NIL:
        n += 1; r = vm.heap.cell(r).b
    rep.check('D5 dir lists all 144', n == 144, n)
    vm = w.vm(full); s1 = vm.save('f002', 'RETRY'); s2 = vm.remount(); s3 = vm.save('f002', 'RETRY')
    rep.check('D5 needs-remount flow on full dir',
              (s1, s2, s3) == (8, 0, 0) and payload_of(bytes(vm.image), 'f002') == b'RETRY', (s1, s2, s3))
    for cnt, dirs in [(143, 18), (9, 2), (1, 1)]:
        vm = w.vm(seeded(cnt, dirs)); st = vm.remount()
        rep.check('D5 remount ok files=%d' % cnt, st == 0 and not vm.writes, st)
    bad = bytearray(full)
    for s in D.directory_slots(bad):
        if s.index == 3 and s.sector == 3:
            bad[D.sector_offset(s.track, s.sector) + s.index * 32 + 2] = 0x85
    rep.check('D5 invalid entry on full dir still status 6', w.vm(bad).remount() == 6)
    loop = bytearray(seeded(9, 2)); o = D.sector_offset(40, 3); loop[o] = 40; loop[o + 1] = 3
    rep.check('D5 self-linked directory sector status 6', w.vm(loop).remount() == 6)
    cm = bytearray(seeded(2, 1)); cm[D.bam_locations(1, 0)[0]] -= 1
    rep.check('D5 BAM count mismatch status 6', w.vm(cm).remount() == 6)
    vm = w.vm(loop); vm.remount(); vm.image[:] = full
    rep.check('D5 clean remount after failed remount', vm.remount() == 0)


# --------------------------------------------------------------------- D2/D4
def verdict(w, rep, label, im):
    """Fresh VM (power cycle): consistent -> 0, unlatched; inconsistent -> 13, latched, no write ever."""
    vm = w.vm(im); st = vm.remount()
    if consistent(im):
        ok = st == 0 and not vm.latched() and not vm.writes
    else:
        ok = st == 13 and vm.latched() and not vm.writes and vm.save('probe', 'x') == 8 and not vm.writes
    rep.check(label, ok, 'remount=%s consistent=%s' % (st, consistent(im)))
    return st


def corruptions():
    out = {}
    im = bytearray(seeded(2, 1)); _, ch = chain_of(im, 'f000'); D.set_sector_free(im, *ch[0], True)
    out['live-sector-marked-free'] = im
    im = bytearray(seeded(2, 1)); a, _ = chain_of(im, 'f000'); _, chb = chain_of(im, 'f001')
    off = D.sector_offset(a.track, a.sector) + a.index * 32; im[off + 3:off + 5] = bytes(chb[0])
    out['crosslink-same-start-with-compensating-leak'] = im
    im = bytearray(seeded(2, 1, size=700)); _, cha = chain_of(im, 'f000'); _, chb = chain_of(im, 'f001')
    o = D.sector_offset(*cha[1]); im[o:o + 2] = bytes(chb[1]); D.set_sector_free(im, *cha[2], True)
    out['crosslink-shared-tail-count-consistent'] = im
    im = bytearray(seeded(1, 1, size=700)); _, ch = chain_of(im, 'f000'); o = D.sector_offset(*ch[2])
    im[o:o + 2] = bytes(ch[0]); out['cycle-back-to-start'] = im
    im = bytearray(seeded(1, 1, size=700)); _, ch = chain_of(im, 'f000'); o = D.sector_offset(*ch[1])
    im[o:o + 2] = bytes([40, 3]); out['link-into-directory-track'] = im
    im = bytearray(seeded(2, 1)); D.set_sector_free(im, 20, 7, False); out['single-leak-bam1'] = im
    im = bytearray(seeded(2, 1)); D.set_sector_free(im, 60, 39, False); out['single-leak-bam2'] = im
    return out


def run_d2d4(w, rep):
    counts = dict(points=0, detected=0, clean=0)
    t40 = bytearray(seeded(9, 2)); c, _, _ = D.bam_locations(40, 0); t40[c:c + 6] = bytes([35, 0xE0, 255, 255, 255, 255])
    for label, im in [('blank', blank(1)), ('oracle-blank-user-image', bytes(O.blank_user_image())),
                      ('seeded-9-2dirs', seeded(9, 2)), ('seeded-144-full-directory', seeded(144, 18)),
                      ('track40-bam-marked', bytes(t40))]:
        rep.check('control-consistent:' + label, consistent(im))
        verdict(w, rep, 'control:' + label, im)
    old = seeded(2, 1)
    for label, im, name, data, prefix_only in [('new1', blank(), 'x', 'n', False),
                                               ('replace1', old, 'f001', 'n', False),
                                               ('new700', blank(), 'x', 'n' * 700, True)]:
        v = w.vm(im); v.remount(); st = v.save(name, data)
        rep.check('txn:' + label, st == 0 and not v.latched(), st)
        verdict(w, rep, 'txn-after:' + label, bytes(v.image))
        full = list(v.writes)
        for mode in ['cut', 'fail', 'postfail']:
            for i in range(1, len(full) + 1):
                if prefix_only:
                    state = bytearray(im)
                    for t, s, data_ in full[:i if mode != 'fail' else i - 1]:
                        state[D.sector_offset(t, s):D.sector_offset(t, s) + 256] = data_
                    image = bytes(state)
                    if consistent(image):
                        continue       # new700: only its leak points, by prefix replay
                else:
                    q = w.vm(im, **{mode: i}); q.remount()
                    try:
                        q.save(name, data)
                    except (Cut, B.VMError):
                        pass
                    image = bytes(q.image); q.cut = q.fail = q.postfail = None; n0 = len(q.writes)
                    if not consistent(image):
                        retry = q.save(name, data)
                        rep.check('fault-retry:%s:%s:%d' % (label, mode, i), retry == 8 and len(q.writes) == n0, retry)
                counts['points'] += 1
                st = verdict(w, rep, 'fault:%s:%s:%d' % (label, mode, i), image)
                counts['detected' if st == 13 else 'clean'] += 1
    for label, im in corruptions().items():
        rep.check('corrupt-refused:' + label, verdict(w, rep, 'corrupt:' + label, bytes(im)) == 13)
    v = w.vm(old, cut=2); v.remount()
    try:
        v.save('f001', 'new')
    except Cut:
        pass
    v.cut = None; n0 = len(v.writes)
    rep.check('abort-claim-then-retry-refused', v.save('f001', 'again') == 8 and len(v.writes) == n0 and v.latched())
    rep.check('abort-claim-remount-detects', v.remount() == 13 and v.save('f001', 'again') == 8 and len(v.writes) == n0)
    leak = bytes(corruptions()['single-leak-bam1'])
    v = w.vm(leak); s8 = v.save('x', 'y'); s13 = v.remount()
    rep.check('status-8-then-13-not-aliased', (s8, s13, v.st(v.call('m65d-status'))) == (8, 13, 13), (s8, s13))
    v = w.vm(leak); a1 = v.remount(); v.image[:] = seeded(2, 1); a2 = v.remount()
    rep.check('refused-then-clean-medium-remounts', (a1, a2) == (13, 0) and not v.latched(), (a1, a2))

    def swapped(im):
        x = bytearray(im); h = D.sector_offset(40, 0)
        x[h + 4:h + 20] = b'OTHERDISK'.ljust(16, b'\xa0'); x[h + 22:h + 24] = b'77'
        return x
    v = w.vm(seeded(2, 1)); v.remount(); v.image[:] = swapped(corruptions()['live-sector-marked-free'])
    st = v.save('extra', 'NEW')
    rep.check('swap-to-unchecked-damaged-disk-no-write', st == 12 and not v.writes and v.latched(), st)
    v = w.vm(seeded(2, 1)); v.remount(); v.image[:] = swapped(seeded(2, 1))
    st = v.save('extra', 'NEW'); rm = v.remount(); st2 = v.save('extra', 'NEW')
    rep.check('swap-clean-other-disk: 12, remount 0, save 0', (st, rm, st2) == (12, 0, 0), (st, rm, st2))
    v = w.vm(blank()); v.remount()
    seq = [v.save('s%d' % (i % 4), 'v' * (37 * i + 1)) for i in range(6)]
    rep.check('six-saves-one-mount', seq == [0] * 6 and not v.latched(), seq)
    verdict(w, rep, 'six-saves-fresh-remount', bytes(v.image))
    v = w.vm(blank()); bad = []
    for t in list(range(1, 40)) + list(range(41, 81)):
        for sec in range(0, 40, 3):
            _, off, mask = D.bam_locations(t, sec)
            got = (B.fixval(v.call('%m65d-bitmap-off', B.mkfix(t), B.mkfix(sec))), B.fixval(v.call('%m65d-mask', B.mkfix(sec))))
            if got != (off - D.sector_offset(40, 1 if t < 41 else 2), mask):
                bad.append((t, sec))
    rep.check('diet-mask-bitmap-off-sampled', not bad, bad[:5])
    rep.check('ide-message-13', 'inconsistent' in v.heap.obj_to_text(v.call('%ide-m65d-message', B.mkfix(13))))
    rep.check('ide-message-12', 'medium changed' in v.heap.obj_to_text(v.call('%ide-m65d-message', B.mkfix(12))))
    # Discrimination floor: the subset must contain refused leak states and accepted fault states.
    rep.check('subset-discriminates', counts['detected'] >= 9 and counts['clean'] >= 9, counts)
    return counts


def selftest():
    w = World({'lib/m65-disk.lisp': [(OWN_CMP_OK, 't)')]})
    leaks = corruptions()
    for label in ['single-leak-bam1', 'live-sector-marked-free']:
        st = w.vm(bytes(leaks[label])).remount()
        if st == 13:
            raise SystemExit('m65d-disk-integrity selftest: FAIL, %s still refused without the BAM comparison' % label)
    print('m65d-disk-integrity selftest: PASS (disabled ownership comparison is observed: leak/live-free accepted)')


def main(argv):
    if argv not in (['d3d5'], ['d2d4'], ['check'], ['selftest']):
        raise SystemExit('usage: m65d_disk_integrity_v253_20261001.py d3d5|d2d4|check|selftest')
    if argv == ['selftest']:
        return selftest()
    w = World(); rep = Report(); extra = ''
    if argv[0] in ('d3d5', 'check'):
        run_d3d5(w, rep)
    if argv[0] in ('d2d4', 'check'):
        extra = ' points=%(points)d detected=%(detected)d clean=%(clean)d' % run_d2d4(w, rep)
    digest = hashlib.sha256((ROOT / 'lib/m65-disk.lisp').read_bytes()).hexdigest()[:12]
    print('m65d-disk-integrity %s: %s rows=%d failed=%d%s m65-disk=%s' % (
        argv[0], 'FAIL' if rep.fails else 'PASS', rep.rows, len(rep.fails), extra, digest))
    return 1 if rep.fails else 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
