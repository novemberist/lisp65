#!/usr/bin/env python3
"""2.5.3 D81: accepted-Final readback (private) and the public disk writer.

assemble() writes freshly derived payloads into the frozen 2.5.3 Final layout: the
track-40 header/BAM/directory skeleton, per-file sector chains, and the
classified slack rules. It never reads a retained medium.
"""
import argparse
import hashlib
import json
import c2_v253_r2_public_native as N
import c2_v253_r2_public_overlays as O


def check():
    """Private preflight: persisted Final D81 readback against the policy."""
    import d81_persistence_fault as D
    import c2_require_resolver_gate as L
    p = O.policy()
    a = N.load(N.AUTHORITY)
    raw = N.bound(a['raw_pair']['D81'])
    N.require(N.identity(raw) == p['medium'], 'wrong product D81')
    D.validate_bam(raw)
    files = D.visible_files(raw)
    N.require({n.decode(): N.identity(b) for n, b in files.items()} == p['files'], 'Final medium file drift')
    names = [s['name'] for s in p['packages']]
    payloads = {n: files[n.upper().encode()] for n in names}
    rows = L.decode_index(files[b'L65INDEX'], payloads, artifact_build_id=p['product_build_id'])
    N.require(rows == [s['row'] for s in p['packages']], 'index drift')
    mutations = L.mutation_gate(files[b'L65INDEX'], payloads, artifact_build_id=p['product_build_id'])
    readback = N.load(N.local(a['final_media_readback']['path']))
    N.require(readback['status'] == 'PASS' and readback['every_file_read_back'] is True and
              readback['unclassified_bytes'] == 0 and readback['files'] == p['files'], 'Final readback receipt')
    rebuilt = assemble({n.decode(): b for n, b in files.items()})
    N.require(rebuilt == raw, 'layout/slack recipe does not reassemble the Final medium')
    return dict(status='PASS: ACCEPTED FINAL MEDIUM READBACK', files=len(files), packages=len(payloads),
                mutations=mutations, layout_reassembled=True, public_reproduction=False)


def assemble(payloads, layout=None):
    import d81_persistence_fault as D
    layout = O.policy()['layout'] if layout is None else layout
    names = [f['name'] for f in layout['files']]
    N.require(set(payloads) == set(names) and len(names) == 20, 'media payload population')
    image = bytearray(D.IMAGE_SIZE)
    for row in layout['skeleton_track40']:
        at = D.sector_offset(40, row['sector'])
        image[at:at + 256] = bytes.fromhex(row['hex'])
    chains = {f['name']: tuple(tuple(x) for x in f['chain']) for f in layout['files']}
    used = {}
    written = {}
    for name in names:
        payload, chain = payloads[name], chains[name]
        N.require(len(chain) == (len(payload) + 253) // 254 and payload, 'chain length drift: ' + name)
        for i, (t, s) in enumerate(chain):
            N.require(t != 40, 'file chain on directory track')
            sector = bytearray(D.chain_sector(payload, chain, i))
            at = D.sector_offset(t, s)
            N.require(not any(image[at:at + 256]), 'crosslinked sector: ' + name)
            image[at:at + 256] = sector
            written[(name, i)] = sector
        used[name] = 2 + len(payload[(len(chain) - 1) * 254:])

    def set_last(name, sector):
        t, s = chains[name][-1]
        at = D.sector_offset(t, s)
        image[at:at + 256] = sector
        written[(name, len(chains[name]) - 1)] = sector

    slack = layout['slack']
    N.require(slack['zero_default'] is True, 'slack default')
    for name in slack['own_previous_sector']:
        n = len(chains[name]) - 1
        N.require(n >= 1, 'no previous sector: ' + name)
        sector = bytearray(written[(name, n)])
        sector[used[name]:] = written[(name, n - 1)][used[name]:]
        set_last(name, sector)
    for name, source in slack['previous_file_buffer'].items():
        N.require(names.index(source) == names.index(name) - 1, 'buffer residue needs directory predecessor')
        buffer = written[(source, len(chains[source]) - 1)]
        sector = bytearray(written[(name, len(chains[name]) - 1)])
        sector[used[name]:] = buffer[used[name]:]
        set_last(name, sector)
    for name, count in slack['tail_repeat'].items():
        sector = bytearray(written[(name, len(chains[name]) - 1)])
        N.require(used[name] + count <= 256, 'tail repeat exceeds sector')
        sector[used[name]:used[name] + count] = payloads[name][-count:]
        set_last(name, sector)
    raw = bytes(image)
    D.validate_bam(raw)
    slots = [s for s in D.directory_slots(raw) if s.record[2]]
    N.require([D.entry_name(s.record).decode() for s in slots] == names, 'directory order drift')
    for s in slots:
        N.require(D.file_chain(raw, s.record) == chains[D.entry_name(s.record).decode()], 'directory/chain mismatch')
    system = {(40, k) for k in range(40)}
    N.require(D.allocated_sectors(raw) == set().union(*chains.values()) - system, 'BAM does not equal chain allocation')
    N.require({n.decode(): b for n, b in D.visible_files(raw).items()} == payloads, 'persisted readback mismatch')
    return raw


def selftest():
    """Negative controls for the writer and templates (private: uses the Final payloads)."""
    import copy
    import d81_persistence_fault as D
    a = N.load(N.AUTHORITY)
    raw = N.bound(a['raw_pair']['D81'])
    files = {n.decode(): b for n, b in D.visible_files(raw).items()}
    N.require(assemble(files) == raw, 'writer baseline')
    layout = O.policy()['layout']
    rejected = []

    def differs(label, fn):
        try:
            out = fn()
        except (ValueError, KeyError, IndexError, StopIteration):
            rejected.append(label); return
        N.require(out != raw, 'mutation survived: ' + label)
        rejected.append(label)
    def raises(label, fn):
        try:
            fn()
        except ValueError:
            rejected.append(label); return
        raise ValueError('mutation survived: ' + label)
    trial = dict(files); trial['PLACE'] = trial['PLACE'][:-1] + bytes([trial['PLACE'][-1] ^ 1])
    differs('payload byte', lambda: assemble(trial))
    trial = dict(files); trial.pop('INIT.L65')
    differs('payload omitted', lambda: assemble(trial))
    for key, mutate in (('own_previous_sector', lambda s: s['own_previous_sector'].pop()),
                        ('previous_file_buffer', lambda s: s['previous_file_buffer'].clear()),
                        ('tail_repeat', lambda s: s['tail_repeat'].clear()),
                        ('zero_default', lambda s: s.update(zero_default=False))):
        lay = copy.deepcopy(layout); mutate(lay['slack'])
        differs('slack rule ' + key, lambda: assemble(files, lay))
    lay = copy.deepcopy(layout); lay['files'][0]['chain'][0] = lay['files'][1]['chain'][0]
    differs('crosslinked chain', lambda: assemble(files, lay))
    lay = copy.deepcopy(layout); lay['files'][0], lay['files'][1] = lay['files'][1], lay['files'][0]
    differs('directory order', lambda: assemble(files, lay))
    for fam, t in O.policy()['families'].items():
        bad = copy.deepcopy(t); h = bytearray.fromhex(bad['header_records']); h[24] = 1; bad['header_records'] = h.hex()
        raises('template CRC ' + fam, lambda: O.template_is_geometry(fam, bad))
        bad = copy.deepcopy(t); bad['manifest']['slices'][0]['sha256'] = '0' * 64
        raises('template digest ' + fam, lambda: O.template_is_geometry(fam, bad))
    return dict(status='PASS', mutations_rejected=len(rejected), controls=rejected)


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('mode', choices=['check', 'selftest']); a = p.parse_args()
    print(json.dumps(check() if a.mode == 'check' else selftest(), indent=2, default=str))
