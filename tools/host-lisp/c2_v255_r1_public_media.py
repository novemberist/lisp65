#!/usr/bin/env python3
"""2.5.5 D81: accepted-Final readback (private) and the public disk writer.

assemble() writes freshly derived payloads into the frozen 2.5.5 Final layout: the
track-40 header/BAM/directory skeleton, per-file sector chains, and the
classified slack rules. It never reads a retained medium.

2.5.5 residue zeroing: SHELF.BIN is two sectors shorter than in 2.5.4 (399 -> 397).  The Seed's explicit media step
zeroed the two freed sectors and the slack behind the stored length of the new last sector, so the medium itself
satisfies the rule "a sector outside every file chain and outside the six system sectors is zero, and the bytes of SHELF.BIN's last
sector behind its stored length are zero".  That is exactly this writer's zero default: the freed sectors are in no
chain of the layout (they stay zero in the fresh image), and SHELF.BIN has no slack rule.  No byte of a predecessor
medium is needed for it; check() asserts the rule on the Final medium (residue_rule).
"""
import argparse
import hashlib
import json
import c2_v255_r1_public_native as N
import c2_v255_r1_public_overlays as O


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
                mutations=mutations, layout_reassembled=True, residue_rule=residue_rule(raw), public_reproduction=False)


def residue_rule(raw, layout=None):
    """The residue-zeroing rule, read from the medium alone (no predecessor bytes).

    Every sector that belongs to no file chain and is not one of the header/BAM/directory sectors of track 40 is
    zero, the BAM marks exactly the chain sectors as allocated, and every file without a classified slack rule (SHELF.BIN among them) has zero slack behind
    its stored length."""
    import d81_persistence_fault as D
    layout = O.policy()['layout'] if layout is None else layout
    chains = {f['name']: [tuple(x) for x in f['chain']] for f in layout['files']}
    owned = {s for chain in chains.values() for s in chain}
    N.require(D.allocated_sectors(raw) == owned, 'BAM does not equal the chain allocation')
    system = {(40, row['sector']) for row in layout['skeleton_track40']}
    free = [(t, s) for t in range(1, 81) for s in range(40) if (t, s) not in owned and (t, s) not in system]
    dirty = [x for x in free if any(raw[D.sector_offset(*x):D.sector_offset(*x) + 256])]
    N.require(not dirty, 'non-zero sector outside every file chain: ' + repr(dirty[:4]))
    slack = layout['slack']
    N.require(slack['zero_default'] is True, 'slack default')
    ruled = (set(slack['own_previous_sector']) | set(slack['previous_file_buffer']) | set(slack['tail_repeat']) |
             set(slack['predecessor_own_previous_sector']))
    N.require('SHELF.BIN' in chains and 'SHELF.BIN' not in ruled, 'SHELF.BIN must fall under the zero default')
    zero_slack = 0
    for name, chain in chains.items():
        at = D.sector_offset(*chain[-1])
        last = raw[at:at + 256]
        N.require(last[0] == 0 and last[1] >= 1, 'last sector link: ' + name)
        tail = last[last[1] + 1:]
        if name in ruled:
            continue
        N.require(not any(tail), 'non-zero slack without a classified rule: ' + name)
        zero_slack += len(tail)
    track, sector = chains['SHELF.BIN'][-1]
    holes = []
    while sector + 1 < 40 and (track, sector + 1) not in owned:
        sector += 1
        holes.append((track, sector))
    recorded = O.policy()['residue_zeroing']
    N.require(recorded['predecessor_bytes_used'] == 0 and recorded['file'] == 'SHELF.BIN' and
              recorded['sectors'] == len(chains['SHELF.BIN']) and recorded['last_sector'] == list(chains['SHELF.BIN'][-1]) and
              recorded['freed_sectors'] == [list(x) for x in holes] and recorded['free_sectors'] == len(free) and
              recorded['slack_bytes'] == 255 - raw[D.sector_offset(*chains['SHELF.BIN'][-1]) + 1],
              'residue-zeroing record does not describe the medium')
    return dict(status='PASS', free_sectors_zero=len(free), files_with_zero_slack=len(chains) - len(ruled),
                zero_slack_bytes=zero_slack, classified_slack_files=sorted(ruled),
                shelf_sectors=len(chains['SHELF.BIN']), shelf_last_sector=list(chains['SHELF.BIN'][-1]),
                free_sectors_behind_shelf=[list(x) for x in holes], predecessor_bytes_used=0)


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
    # Since 2.5.4: a file REPLACED IN PLACE keeps the slack the predecessor medium had.  L65INDEX is such a file
    # (byte-exact against 2.5.4 in 2.5.5; the Seed kept its sectors): its
    # last-sector slack is the own-previous-sector residue of the 2.5.3 index, not of the current one (they differ
    # in four bytes of the DEFSTRUCT row).  The predecessor payload is re-derived, never copied: it is the index
    # encoded from the package rows of the bound, exported 2.5.3 media policy.
    for name, rule in slack['predecessor_own_previous_sector'].items():
        import c2_require_resolver_gate as L
        N.require(name == 'L65INDEX' and name not in slack['own_previous_sector'], 'predecessor residue rule population')
        old = L.encode_index([s['row'] for s in json.loads(N.bound(rule['predecessor_policy']))['packages']])
        N.require(N.identity(old) == rule['predecessor_payload'] and len(old) == len(payloads[name]),
                  'predecessor index derivation drift')
        n = len(chains[name]) - 1
        N.require(n >= 1, 'no previous sector: ' + name)
        sector = bytearray(written[(name, n)])
        sector[used[name]:] = D.chain_sector(old, chains[name], n - 1)[used[name]:]
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
                        ('predecessor_own_previous_sector', lambda s: (s['own_previous_sector'].append('L65INDEX'),
                                                                       s['predecessor_own_previous_sector'].clear())),
                        ('predecessor payload', lambda s: s['predecessor_own_previous_sector']['L65INDEX'][
                            'predecessor_payload'].update(sha256='0' * 64)),
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
    # Residue-zeroing rule (2.5.5): read from the medium alone; each control leaves one residue byte or bends the rule.
    N.require(residue_rule(raw)['status'] == 'PASS', 'residue rule baseline')
    chains = {f['name']: f['chain'] for f in layout['files']}
    shelf_last = D.sector_offset(*chains['SHELF.BIN'][-1])
    freed = O.policy()['residue_zeroing']['freed_sectors']
    for label, at in (('residue byte in a freed sector', D.sector_offset(*freed[0]) + 7),
                      ('residue byte in the second freed sector', D.sector_offset(*freed[1]) + 255),
                      ('residue byte in the SHELF.BIN slack', shelf_last + 255),
                      ('residue byte in a free sector elsewhere', D.sector_offset(79, 39) + 1)):
        N.require(raw[at] == 0, 'residue control position is not free: ' + label)
        bad = bytearray(raw); bad[at] = 0x55
        raises(label, lambda: residue_rule(bytes(bad)))
    lay = copy.deepcopy(layout); lay['slack']['tail_repeat']['SHELF.BIN'] = 1
    raises('SHELF.BIN under a slack rule', lambda: residue_rule(raw, lay))
    lay = copy.deepcopy(layout); lay['files'] = [f for f in lay['files'] if f['name'] != 'PLACE']
    raises('chain population differs from the BAM', lambda: residue_rule(raw, lay))
    return dict(status='PASS', mutations_rejected=len(rejected), controls=rejected)


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('mode', choices=['check', 'selftest']); a = p.parse_args()
    print(json.dumps(check() if a.mode == 'check' else selftest(), indent=2, default=str))
