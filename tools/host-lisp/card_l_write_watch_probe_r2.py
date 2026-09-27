"""Card L Seed successor: marker identity and Bank-5 snapshot-difference row.

Host-only, read-only on the guest (memory reads, pause/resume, keyboard
queue). Region: $5DE20-$5FE89 (96-byte gap + 10-byte header + 8,192-byte
payload of the boot name index), read as $5DE20..$5FE90 (8,304 bytes,
16-aligned). Boundary: the first LISP65> prompt after boot (later than the
boot publication, stated as a limit). After every workload form the region
is re-read with the CPU paused and compared byte for byte with the boundary
snapshot. The marker must match at the first prompt and after every workload form;
Comfort is required and allocation pressure must advance gc_runs.
Zero changed bytes across the workload is the snapshot result;
any change is reported with its offsets. Derived from
tools/host-lisp/retained_callable_writer_probe_r1.py (2.4.0 world via the
nested-error-recovery instrument identity).
"""
import argparse, hashlib, json, os, re, sys, time, traceback
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/host-lisp'))
import native_cycle_stationary as N
import dwx_retroactive_red_replay as R
import dwx_comfort_resume as C
from elf_truth import ElfTruth
OUT = ROOT / 'build/card-l-r1/write-watch-r1'
REGION_LO, REGION_HI = 0x5DE20, 0x5FE90
GAP = (0x5DE20, 0x5DE80); HEADER = (0x5FE80, 0x5FE8A); PAYLOAD = (0x5DE80, 0x5FE80)

WORKLOAD = [
    ('require-comfort', '(require "repl-comfort")', 'T'),
    ('arith', '(+ 4 5)', '9'),
    ('require-inspect', '(require "inspect")', 'T'),
    ('who-calls', "(who-calls 'no-such)", 'NIL'),
    ('require-buffer', '(require "buffer")', 'T'),
    ('require-defstruct', '(require "defstruct")', 'T'),
    ('load-lib-ide', '(load-lib "ide")', 'T'),
    ('defstruct-a', '(defstruct storea a b c d e)', 'T'),
    ('access-a', '(storea-e (make-storea 1 2 3 4 42))', '42'),
    ('defstruct-b', '(defstruct storeb a b c d e)', 'T'),
    ('defstruct-c', '(defstruct storec a b c d e)', 'T'),
    ('eval-loop-16', "(dotimes (n 16) (eval '(defun f16 () 7)))", 'NIL'),
    ('call-f16', '(f16)', '7'),
    ('nested-error', "(let ((q 1)) (eval '(capzz)))", '*** UNDEFINED FUNCTION: CAPZZ'),
    ('arith-2', '(+ 4 5)', '9'),
    ('overcap-60', "(dotimes (n 60) (eval '(defun capn () 7)))", '*** VM: OUT OF MEMORY'),
    ('call-capn', '(capn)', '7'),
    ('arith-3', '(+ 4 5)', '9'),
    ('forced-collection', '(dotimes (n 2048) (cons n nil))', 'NIL'),
    ('arith-after-gc', '(+ 4 5)', '9'),
]


def read_region(m):
    data = bytearray()
    for at in range(REGION_LO, REGION_HI, 256):
        response = m.command(f'M {at:08x}')
        rows = re.findall(r':([0-9A-Fa-f]{8}):([0-9A-Fa-f]{32})', response)
        assert [int(a, 16) for a, b in rows] == list(range(at, at + 256, 16)), response[:200]
        data.extend(b''.join(bytes.fromhex(b) for a, b in rows))
    return bytes(data[:REGION_HI - REGION_LO])


def classify(offset):
    a = REGION_LO + offset
    if GAP[0] <= a < GAP[1]: return 'gap'
    if HEADER[0] <= a < HEADER[1]: return 'header'
    if PAYLOAD[0] <= a < PAYLOAD[1]: return 'payload'
    return 'outside'


def verify_marker(data, marker):
    """Pure host check, also usable on saved paused-memory snapshots."""
    if len(data) != REGION_HI - REGION_LO or len(marker) != 8192:
        raise ValueError('late-region snapshot or marker extent mismatch')
    staged = data[PAYLOAD[0]-REGION_LO:PAYLOAD[1]-REGION_LO]
    if staged != marker:
        different = [i for i, (a, b) in enumerate(zip(staged, marker)) if a != b]
        raise ValueError('staged marker differs: %d bytes; first addresses %s' %
                         (len(different), [hex(PAYLOAD[0]+i) for i in different[:16]]))
    return dict(marker_equal=True, marker_sha256=hashlib.sha256(staged).hexdigest(), bytes=len(staged))


def main():
    global OUT
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--identity', type=Path, required=True,
                        help='reviewer-created instrumentation JSON, candidate world for the Card L + Comfort medium')
    parser.add_argument('--out', type=Path, default=OUT)
    parser.add_argument('--marker', type=Path, default=ROOT/'build/card-l-r1/card-l-marker.bin')
    options = parser.parse_args()
    OUT = options.out.resolve()
    assert OUT.is_relative_to(ROOT/'build/card-l-r1')
    OUT.mkdir(exist_ok=False)
    marker = options.marker.read_bytes()
    sealed = json.loads((ROOT/'config/card-l-native/card-l-inputs.json').read_text())
    assert hashlib.sha256(marker).hexdigest() == sealed['image']['sha256']
    identity = json.loads(options.identity.read_text())
    world = next(w for w in identity['worlds'] if w['role'] == 'candidate')
    os.environ['LISP65_COST_CONFIG'] = world['cost_config']
    os.environ['LISP65_DWX_PC_OUTPUT'] = str(OUT / 'pc-current.txt')
    elf = N.checked_binding(world['ELF']); binary = N.checked_binding(world['binary']); medium = N.checked_binding(world['medium'])
    assert hashlib.sha256(elf.read_bytes()).hexdigest() == '7e57bc17f318dd22a6dbc0212fd5fde5b9598eaf645f4f98d6387e0c3f53f3b5'
    receipt = json.loads((ROOT/'build/card-l-seed-medium-r2/comfort/receipt.json').read_text())
    assert hashlib.sha256(medium.read_bytes()).hexdigest() == receipt['sha256']
    t = ElfTruth.read(elf, llvm_readobj=ROOT / 'tools/llvm-mos/bin/llvm-readobj')
    status = t.symbol('vm_status').value
    gc_runs = t.symbol('gc_runs').value
    args = argparse.Namespace(xemu=binary, rom=Path(str(Path.home() / '.local/share/xemu-lgb/mega65/MEGA65.ROM')),
                              sd_image=Path(str(Path.home() / '.local/share/xemu-lgb/mega65/mega65.img')),
                              timeout=1500, out=OUT, action='probe')
    parent = R.ProbeMonitor
    class Monitor(parent):
        def wait_screen(self, required, timeout=20): return super().wait_screen(required, timeout=180)
    R.ProbeMonitor = Monitor
    run = None; steps = []; error = None; baseline = None
    def snapshot(m, label):
        m.command('t1')
        data = read_region(m)
        verify_marker(data, marker)
        p = OUT / f'{label}-region.bin'; p.write_bytes(data)
        s = OUT / f'{label}-screen.txt'; s.write_text(m.screen())
        m.command('t0')
        return data, N.bind(p), N.bind(s)
    try:
        run = R.start_run('cardl', medium, OUT, args); m = run['monitor']
        baseline, bind_b, bind_s = snapshot(m, 'boundary')
        header = baseline[HEADER[0] - REGION_LO:HEADER[1] - REGION_LO]
        steps.append(dict(label='boundary', region=bind_b, screen=bind_s, header_hex=header.hex(),
                          payload_nonzero=sum(1 for b in baseline[PAYLOAD[0]-REGION_LO:PAYLOAD[1]-REGION_LO] if b),
                          gap_hex=baseline[:GAP[1]-GAP[0]].hex()))
        print('boundary header', header.hex(), 'payload nonzero', steps[-1]['payload_nonzero'], flush=True)
        for label, form, expected in WORKLOAD:
            gc_before = int.from_bytes(m.memory16(gc_runs)[:2], 'little')
            before = m.screen(); m.type_text(form + '\n'); deadline = time.monotonic() + 900
            while time.monotonic() < deadline:
                screen = m.screen()
                if C.fresh_result(before, screen, expected) and C.active(screen).endswith('>'): break
                time.sleep(.2)
            else:
                raise AssertionError('form did not complete: ' + label + '\n' + R.ROWS.decoded_framebuffer(screen))
            data, bind_r, bind_sc = snapshot(m, label)
            gc_after = int.from_bytes(m.memory16(gc_runs)[:2], 'little')
            gc_delta = (gc_after-gc_before) & 65535
            if label == 'forced-collection':
                assert gc_delta > 0, 'allocation-pressure row did not witness a collection'
            changed = [i for i in range(len(data)) if data[i] != baseline[i]]
            by_class = {}
            for i in changed: by_class[classify(i)] = by_class.get(classify(i), 0) + 1
            rec = dict(label=label, form=form, expected=expected, region=bind_r, screen=bind_sc,
                       changed_bytes=len(changed), changed_by_class=by_class,
                       first_changes=[dict(address=hex(REGION_LO + i), before=baseline[i], after=data[i]) for i in changed[:32]],
                       vm_status=m.memory16(status)[0], marker=verify_marker(data, marker),
                       gc_runs_before=gc_before, gc_runs_after=gc_after, collections=gc_delta)
            steps.append(rec); print(label, 'changed', len(changed), by_class, flush=True)
            (OUT / 'steps.json').write_text(json.dumps(steps, indent=2) + '\n')
    except BaseException:
        error = traceback.format_exc(); raise
    finally:
        output = R.finish_run(run) if run else None
        total = sum(s.get('changed_bytes', 0) for s in steps)
        (OUT / 'receipt.json').write_text(json.dumps(dict(
            status='HALT: PROBE ERROR' if error else ('PASS: ZERO BYTES CHANGED IN THE LATE REGION ACROSS THE WORKLOAD' if total == 0 else f'FINDING: {total} BYTE CHANGES IN THE LATE REGION'),
            authority='fee85e6f / Card L reviewer decision 2026-09-25', method='snapshot diff of $5DE20-$5FE90 with the CPU paused after every form; boundary = first prompt (later than the boot publication)',
            world=world, region=dict(lo=hex(REGION_LO), hi=hex(REGION_HI), gap=[hex(GAP[0]), hex(GAP[1])], header=[hex(HEADER[0]), hex(HEADER[1])], payload=[hex(PAYLOAD[0]), hex(PAYLOAD[1])]),
            steps=steps, output=output, error=error, driver=N.bind(Path(__file__)),
            builds=0, links=0, seeds=0, device_contacts=0, guest_memory_writes=0,
            limits=['boundary is the first prompt, not the publication instant', 'same-value writes are invisible to a snapshot diff', 'allocation-pressure collection witnessed by gc_runs; matched GC timing is a separate gate', 'snapshot diffs do not prove the absence of transient writes or attribute writer PCs']), indent=2) + '\n')
if __name__ == '__main__': main()
