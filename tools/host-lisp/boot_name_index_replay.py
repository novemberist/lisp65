"""Replay the boot intern census against a 10-bit-hash open-address index.

Host-only projection. Reads build/native-diet-intern-census-r1/capture-r1/intern.txt
(the measured boot request sequence) and derives, per request, the number of full
name comparisons the present linear `sym_lookup` performs and the number an
open-addressed transient index would perform. Nothing here is a native
measurement: only the comparison counts and the census cycles are measured.
"""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CENSUS = ROOT / 'build/native-diet-intern-census-r1/capture-r1/intern.txt'
NAME_MAX = 33
SLOTS = 1024
DECODER_PHASE_10_BOOT_ORDINAL = 8


def nlen4(length):
    return length if length < 15 else 15


def bix_hash(name):
    h = 0
    for ch in name.encode():
        h = (((h << 5) + h) & 0xffff) ^ ch
    return h & 0xffff


def load(path):
    rows = []
    for line in path.read_text().splitlines():
        f = line.split()
        if not f or f[0] != 'N':
            raise ValueError('unexpected census row: ' + line)
        rows.append(dict(boot_phase=int(f[1]), t0=int(f[2]), t1=int(f[3]),
                         nsym0=int(f[4]), nsym1=int(f[5]), pool=int(f[6]),
                         off=int(f[7]), ret=f[8], name=f[9]))
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--census', type=Path, default=CENSUS)
    ap.add_argument('--out', type=Path,
                    default=ROOT / 'build/boot-name-index-preflight-r1')
    a = ap.parse_args()
    if not a.out.is_relative_to(ROOT / 'build'):
        raise ValueError('outputs must stay under build/')
    a.out.mkdir(parents=True, exist_ok=True)
    rows = load(a.census)

    # --- 1. reproduce the measured comparison counts from the linear model ---
    table = []                      # nlen4 class per symbol index, in creation order
    index_of = {}
    model_mismatch = []
    measured_total = 0
    for n, r in enumerate(rows):
        name = r['name']
        if len(name) > NAME_MAX:
            raise ValueError('census name longer than the interner cap')
        want = nlen4(len(name))
        candidates = 0
        for i, cls in enumerate(table):
            if cls != want:
                continue
            candidates += 1
            if index_of.get(name) == i:
                break
        if candidates != r['pool']:
            model_mismatch.append(dict(row=n, name=name, model=candidates,
                                       measured=r['pool']))
        measured_total += r['pool']
        if name not in index_of:
            index_of[name] = len(table)
            table.append(want)
        if r['nsym1'] != len(table) or r['nsym0'] != len(table) - (r['nsym1'] - r['nsym0']):
            raise ValueError('census symbol count disagrees with replay at row %d' % n)

    # --- 2. index projection, same request order -----------------------------
    slots = [0] * SLOTS            # 0 = empty; otherwise (idx+1) | tag<<10
    names = []                     # canonical pool, creation order
    indexed = 0
    ix_cmp = 0                     # full name comparisons
    ix_probe = 0                   # index slot reads (DMA words)
    ix_insert = 0
    ix_order = []
    build_probe = 0
    build_cmp = 0

    def find(name, h):
        nonlocal ix_cmp, ix_probe
        s = h & (SLOTS - 1)
        tag = (h >> 10) & 0x3f
        while True:
            word = slots[s]
            ix_probe += 1
            if word == 0:
                return None, s
            if (word >> 10) == tag:
                ix_cmp += 1
                if names[(word & 0x3ff) - 1] == name:
                    return (word & 0x3ff) - 1, s
            s = (s + 1) & (SLOTS - 1)

    for n, r in enumerate(rows):
        name = r['name']
        # count catch-up: index every symbol created outside this walk
        while indexed < (len(names) if names else 0):
            break
        h = bix_hash(name)
        got, slot = find(name, h)
        if got is None:
            names.append(name)
            ix_order.append(name)
            idx = len(names) - 1
            slots[slot] = (idx + 1) | (((h >> 10) & 0x3f) << 10)
            ix_insert += 1
        # sanity: same symbol identity as the linear replay
        expect = index_of[name]
        got2 = got if got is not None else len(names) - 1
        if got2 != expect:
            raise ValueError('index replay disagrees on symbol index at row %d' % n)

    # Index build cost if the index is (re)built from an already-populated table:
    # the state the decoder-phase-10 walk starts from.
    phase10 = [r for r in rows if r['boot_phase'] == DECODER_PHASE_10_BOOT_ORDINAL]
    nsym_at_phase10 = phase10[0]['nsym0']
    slots_b = [0] * SLOTS
    for i in range(nsym_at_phase10):
        nm = ix_order[i]
        h = bix_hash(nm)
        s = h & (SLOTS - 1)
        tag = (h >> 10) & 0x3f
        while slots_b[s]:
            build_probe += 1
            if (slots_b[s] >> 10) == tag:
                build_cmp += 1
            s = (s + 1) & (SLOTS - 1)
        build_probe += 1
        slots_b[s] = (i + 1) | (tag << 10)

    # --- 3. per-phase aggregation -------------------------------------------
    def agg(sel):
        sub = [r for r in rows if sel(r)]
        return dict(requests=len(sub),
                    comparisons=sum(r['pool'] for r in sub),
                    new_symbols=sum(1 for r in sub if r['nsym1'] > r['nsym0']),
                    cycles=sum(r['t1'] - r['t0'] for r in sub))

    # index comparisons/probes restricted to the decoder-phase-10 window
    slots_c = [0] * SLOTS
    for i in range(nsym_at_phase10):
        nm = ix_order[i]
        h = bix_hash(nm)
        s = h & (SLOTS - 1)
        while slots_c[s]:
            s = (s + 1) & (SLOTS - 1)
        slots_c[s] = (i + 1) | (((h >> 10) & 0x3f) << 10)
    p10_cmp_replay = p10_probe = 0
    live = nsym_at_phase10
    for r in phase10:
        name = r['name']
        h = bix_hash(name)
        s = h & (SLOTS - 1)
        tag = (h >> 10) & 0x3f
        hit = None
        while True:
            word = slots_c[s]
            p10_probe += 1
            if word == 0:
                break
            if (word >> 10) == tag:
                p10_cmp_replay += 1
                if ix_order[(word & 0x3ff) - 1] == name:
                    hit = (word & 0x3ff) - 1
                    break
            s = (s + 1) & (SLOTS - 1)
        if hit is None:
            slots_c[s] = (live + 1) | (tag << 10)
            live += 1

    # --- 4. collection sizing from the measured request sequence ------------
    lengths = [len(r['name']) for r in phase10]
    collection = dict(
        entries=len(phase10),
        entry_bytes_payload24_len8_slot16=6,
        bytes_at_6=6 * len(phase10),
        bytes_at_5=5 * len(phase10),
        bytes_at_4=4 * len(phase10),
        inline_name_stream_bytes=sum(lengths) + len(lengths),
        name_length_min=min(lengths), name_length_max=max(lengths),
        name_length_mean=round(sum(lengths) / len(lengths), 3),
    )

    cycles_total = sum(r['t1'] - r['t0'] for r in rows)
    per_comparison = cycles_total / measured_total

    # --- 5. cost model, fitted to the measured census ------------------------
    # cycles(request) ~ SCAN*nsym_before + CMP*comparisons + NEW*created.
    # The intercept is left in the fit and comes out near zero, which is the
    # only reason the three terms may be read as a cost decomposition.
    def lstsq(x_rows, y):
        n = len(x_rows[0])
        a = [[sum(x_rows[r][i] * x_rows[r][j] for r in range(len(x_rows)))
              for j in range(n)] for i in range(n)]
        b = [sum(x_rows[r][i] * y[r] for r in range(len(x_rows))) for i in range(n)]
        m = [a[i][:] + [b[i]] for i in range(n)]
        for i in range(n):
            pivot = max(range(i, n), key=lambda r: abs(m[r][i]))
            m[i], m[pivot] = m[pivot], m[i]
            for r in range(n):
                if r != i:
                    f = m[r][i] / m[i][i]
                    for c in range(i, n + 1):
                        m[r][c] -= f * m[i][c]
        return [m[i][n] / m[i][i] for i in range(n)]

    design = [[1, r['nsym0'], r['pool'], 1 if r['nsym1'] > r['nsym0'] else 0]
              for r in rows]
    observed = [r['t1'] - r['t0'] for r in rows]
    const, scan, cmp_c, new_c = lstsq(design, observed)
    predicted = [const + scan * d[1] + cmp_c * d[2] + new_c * d[3] for d in design]
    mean = sum(observed) / len(observed)
    r2 = 1 - (sum((a - b) ** 2 for a, b in zip(predicted, observed))
              / sum((o - mean) ** 2 for o in observed))
    HZ = 40500000.0
    scan_sum = sum(r['nsym0'] for r in rows)
    p10_rows = phase10
    p10_scan = sum(r['nsym0'] for r in p10_rows)
    p10_cmp = sum(r['pool'] for r in p10_rows)
    p10_new = sum(1 for r in p10_rows if r['nsym1'] > r['nsym0'])
    p10_cycles = sum(r['t1'] - r['t0'] for r in p10_rows)

    def projected(slot_cost):
        # index form: one confirming comparison per hit, one slot read per probe,
        # unchanged creation cost, plus the build's reads and writes.
        return (cmp_c * p10_cmp_measured_index
                + slot_cost * (p10_probe + build_probe)
                + new_c * p10_new + slot_cost * nsym_at_phase10)

    p10_cmp_measured_index = p10_cmp_replay

    receipt = dict(
        claim='HOST REPLAY PROJECTION ONLY; ONLY THE CENSUS COUNTS AND CYCLES ARE MEASURED',
        budget=dict(seed=0, finale=0, link=0, device_contacts=0),
        census=dict(path=str(a.census.relative_to(ROOT)),
                    sha256=hashlib.sha256(a.census.read_bytes()).hexdigest(),
                    rows=len(rows)),
        linear_model=dict(matched_rows=len(rows) - len(model_mismatch),
                          mismatches=model_mismatch,
                          measured_comparisons=measured_total),
        measured=dict(all=agg(lambda r: True),
                      decoder_phase_10=agg(lambda r: r['boot_phase'] == DECODER_PHASE_10_BOOT_ORDINAL),
                      other=agg(lambda r: r['boot_phase'] != DECODER_PHASE_10_BOOT_ORDINAL),
                      cycles_per_comparison_whole_boot=round(per_comparison, 1)),
        index_projection=dict(
            slots=SLOTS,
            whole_boot_comparisons=ix_cmp, whole_boot_slot_reads=ix_probe,
            inserts=ix_insert,
            symbols_at_decoder_phase_10_entry=nsym_at_phase10,
            build_slot_writes=nsym_at_phase10,
            build_slot_reads=build_probe,
            build_tag_collisions=build_cmp,
            decoder_phase_10_comparisons=p10_cmp_replay,
            decoder_phase_10_slot_reads=p10_probe,
            symbol_identity_agrees_with_linear=True),
        collection=collection,
        cost_model=dict(
            form='cycles = const + scan*symbols_before + cmp*comparisons + new*created',
            const=round(const, 1), scan=round(scan, 2),
            comparison=round(cmp_c, 1), new_symbol=round(new_c, 1),
            r_squared=round(r2, 5),
            whole_boot_model_seconds=round(
                (const * len(rows) + scan * scan_sum + cmp_c * measured_total
                 + new_c * 668) / HZ, 3),
            whole_boot_measured_seconds=round(cycles_total / HZ, 3),
            decoder_phase_10=dict(
                measured_seconds=round(p10_cycles / HZ, 3),
                scan_seconds=round(scan * p10_scan / HZ, 3),
                comparison_seconds=round(cmp_c * p10_cmp / HZ, 3),
                creation_seconds=round(new_c * p10_new / HZ, 3))),
        gain_projection=dict(
            note='PROJECTION, NOT A MEASUREMENT: the cost of one 2-byte '
                 'Bank-5 index word read is not measured; it is bounded below '
                 'by zero and above by the cost of a full name comparison, '
                 'which also reads a name.  Queue writes, slice reloads and '
                 'the collecting walk itself are not priced here.',
            decoder_phase_10_measured_seconds=round(p10_cycles / HZ, 3),
            index_comparisons=p10_cmp_measured_index,
            index_slot_reads=p10_probe + build_probe + nsym_at_phase10,
            optimistic_seconds=round(projected(0) / HZ, 3),
            pessimistic_seconds=round(projected(cmp_c) / HZ, 3),
            optimistic_saving_seconds=round((p10_cycles - projected(0)) / HZ, 3),
            pessimistic_saving_seconds=round(
                (p10_cycles - projected(cmp_c)) / HZ, 3)),
    )
    (a.out / 'replay.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({k: v for k, v in receipt.items() if k != 'linear_model'}, indent=2))
    print('linear model mismatches:', len(model_mismatch))


if __name__ == '__main__':
    main()
