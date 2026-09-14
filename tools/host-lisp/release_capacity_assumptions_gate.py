#!/usr/bin/env python3
"""A10/A11/A12: read-only capacity census of an explicitly bound world.

The release medium supplies the complete file/index population. The consumed
native projection supplies capacities; source defaults and legacy VM_DIR_MAX
are not authorities. No claims about peak append usage or user workloads.
"""
import argparse
import ast
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import re
import struct
import zlib

import c2_require_resolver_gate as INDEX
import d81_persistence_fault as D81
from c2_product_substitution_link import ordinary_bss_next_owner
from elf_truth import ElfTruth
from stack_layout_assumptions_gate import ROOT, LLVM, AUTHORITY, require


def report_consumer(source):
    funcs = [n for n in ast.parse(source).body if isinstance(n,ast.FunctionDef) and n.name=='kernal_freedom_gate']
    require(len(funcs) == 1, 'KERNAL report producer absent')
    for name, expression in [('ordinary_bss_owner', 'ordinary_bss_next_owner(truth)'),
                              ('ordinary_bss_headroom', "ordinary_bss_owner['headroom_bytes']")]:
        values = [n.value for n in ast.walk(funcs[0]) if isinstance(n,ast.Assign)
                  and any(isinstance(t,ast.Name) and t.id==name for t in n.targets)]
        require(len(values)==1 and ast.dump(values[0])==ast.dump(ast.parse(expression,mode='eval').body),
                'live BSS report does not consume next-owner geometry')


def bound(row):
    data = (ROOT/row['path']).read_bytes()
    require(len(data) == row['bytes'] and hashlib.sha256(data).hexdigest() == row['sha256'],
            'input binding drift: '+row['path'])
    return data


def budget(c2d, rows, caps):
    require(c2d[:8] == b'C2D\0\x06\x30\x20\x0a', 'C2D-v6 header required')
    report = {}
    for name, offset in [('images',12), ('entries',16), ('resolutions',20), ('roots',24)]:
        count, capacity = struct.unpack_from('<HH', c2d, offset)
        require(capacity == caps[name], 'C2D/native capacity disagreement: '+name)
        added = sum(row[name] for row in rows)
        require(count+added <= capacity, 'all-library C2D budget exceeded: '+name)
        report[name] = dict(boot=count, libraries=added, capacity=capacity,
                            headroom=capacity-count-added)
    return report


def file_window(files, window):
    require(window > 0, 'nonpositive file window')
    require(all(len(data) <= window for data in files.values()), 'file exceeds consumed file window')
    return [dict(name=name.decode('ascii'), bytes=len(data), headroom=window-len(data))
            for name,data in sorted(files.items())]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--authority', type=Path, default=AUTHORITY)
    args = parser.parse_args()
    authority = json.loads(args.authority.read_text())
    inputs = {r['path']: r for r in authority['producer_inputs']}
    native = json.loads(bound(authority['native_projection']))
    runtime_rows = [r for p,r in inputs.items() if p.endswith('/sources/c2_product_runtime.c')]
    require(len(runtime_rows) == 1, 'native runtime source population')
    runtime = bound(runtime_rows[0]).decode()
    caps = {}
    for name, macro in [('images','IMAGE'),('entries','ENTRY'),('resolutions','RESOLUTION'),('roots','ROOT')]:
        found = re.findall(r'^#define C2D_'+macro+r'_CAP (\d+)u$', runtime, re.M)
        require(len(found) == 1, 'unresolved consumed capacity: '+macro)
        caps[name] = int(found[0])
    window_values = [s.split('=',1)[1] for s in native['definitions'] if s.startswith('DISK_EXT_FILE_MAX=')]
    require(len(window_values) == 1, 'file window definition missing/duplicate')
    window = int(window_values[0],0)
    media = bound(authority['medium'])
    files = D81.visible_files(media)
    # Exact public library authority supplies names/dependencies and payload
    # bindings; the index decoder independently validates its row CRCs and
    # payload-derived C2D deltas, not merely their summed declarations.
    library_inputs = [r for p,r in inputs.items() if p.endswith('/libraries/libraries.json')]
    require(len(library_inputs) == 1, 'library authority absent')
    libraries = json.loads(bound(library_inputs[0]))
    artifacts = {r['name']: files[r['name'].upper().encode()] for r in libraries['libraries']}
    for row in libraries['libraries']:
        data = artifacts[row['name']]
        require(row['artifact'] == dict(bytes=len(data),sha256=hashlib.sha256(data).hexdigest()),
                'shipped library bytes differ: '+row['name'])
    rows = INDEX.decode_index(files[b'L65INDEX'], artifacts,
                              artifact_build_id=libraries['product_build_id'])
    require({r['name'] for r in rows} == set(artifacts), 'index/package population differs')
    capacities = budget(files[b'C2D.BIN'], rows, caps)
    # Binary transport roles do not enter load/load-lib's file window.
    # Match their SHA/size, never infer exclusions from a .BIN extension.
    media_authorities = [r for p,r in inputs.items() if p.endswith('/media-authority.json')]
    require(len(media_authorities) == 1, 'media role authority absent')
    media_authority = json.loads(bound(media_authorities[0]))
    roles = media_authority['roles']
    # Stage reset-domain expansion is explicitly different from the input
    # C2D role. Consume the bound materialization receipt, not a suffix rule.
    provenance = media_authority['provenance']
    raw_receipt = (ROOT/provenance['path']).read_bytes()
    require(hashlib.sha256(raw_receipt).hexdigest() == provenance['sha256'], 'staged-role receipt drift')
    staged_receipt = json.loads(raw_receipt)
    staged = {}
    for row in staged_receipt['descriptor']:
        name = row['name'].upper().encode()
        require(name not in staged and name in files, 'duplicate/missing staged file')
        require(len(files[name]) == row['bytes'] and
                f'{zlib.crc32(files[name]) & 0xffffffff:08x}' == row['crc32'], 'staged descriptor/file mismatch')
        staged[name] = row['role_id']
    checked, excluded = {}, []
    for name, data in files.items():
        identity = dict(bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
        matches = [role for role, record in roles.items() if record == identity]
        if name in {n.upper().encode() for n in artifacts} or any(r.startswith('library-') for r in matches):
            checked[name] = data
        elif name == b'L65INDEX':
            excluded.append(dict(name=name.decode(), reason='sector-streamed L65I, not file-window loading'))
        elif matches:
            excluded.append(dict(name=name.decode(), roles=matches))
        elif name in staged:
            excluded.append(dict(name=name.decode(), staged_role_id=staged[name]))
        elif name.lower().endswith((b'.l65', b'.lisp')):
            checked[name] = data
        else:
            raise RuntimeError('unclassified shipped file: '+repr(name))
    window_report = file_window(checked, window)
    elf_row = authority['raw_pair']['ELF']; bound(elf_row)
    truth = ElfTruth.read(ROOT/elf_row['path'],llvm_readobj=LLVM/'llvm-readobj')
    bss = ordinary_bss_next_owner(truth)
    report_source = (ROOT/'tools/host-lisp/c2_product_substitution_link.py').read_text()
    report_consumer(report_source)
    controls = []
    for name in caps:
        altered = deepcopy(rows)
        altered[0][name] += capacities[name]['headroom']+1
        try: budget(files[b'C2D.BIN'], altered, caps)
        except RuntimeError: controls.append('overflow-'+name)
        else: raise RuntimeError('capacity mutation survived: '+name)
    altered = dict(checked); altered[b'OVERSIZE.L65'] = bytes(window+1)
    try: file_window(altered, window)
    except RuntimeError: controls.append('oversize-source')
    else: raise RuntimeError('oversize source survived')
    altered = dict(checked); altered[b'BOUNDARY.L65'] = bytes(window)
    file_window(altered,window)
    # The old fixed-C080 metric must disagree on this world, while changing
    # the nearest owner by one byte must change the reported room by one.
    old_room = truth.section('.lisp65_c2_fixed_bank0').address - (
        truth.section('.bss').address+truth.section('.bss').bytes)
    require(old_room != bss['headroom_bytes'], 'old fixed-owner mutation is not sharp')
    controls.append('old-fixed-bank0-headroom')
    old_consumer = report_source.replace("ordinary_bss_headroom = ordinary_bss_owner['headroom_bytes']",
                                        'ordinary_bss_headroom = FIXED_BANK0_BASE - ordinary_bss_end')
    require(old_consumer != report_source, 'old-report mutation anchor absent')
    try: report_consumer(old_consumer)
    except RuntimeError: controls.append('old-report-consumer')
    else: raise RuntimeError('old report consumer survived')
    shifted = deepcopy(truth)
    shifted.sections = [replace(s,address=s.address-1) if s.name==bss['next_owner'] else s
                        for s in shifted.sections]
    require(ordinary_bss_next_owner(shifted)['headroom_bytes'] == bss['headroom_bytes']-1,
            'next-owner displacement not consumed')
    controls.append('next-owner-displacement')
    result = dict(status='PASS', authority=str(args.authority), medium=authority['medium'],
        native_projection=authority['native_projection'], C2D=capacities,
        file_window_bytes=window, checked_files=window_report, excluded_files=excluded,
        ordinary_bss=bss, historical_fixed_owner_figure=old_room, mutations_rejected=controls,
        claim='Static released-media capacity and actual BSS geometry; no live workload/append high-water or device claim.')
    out = ROOT/'build/release-capacity-assumptions/receipt.json'
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,indent=2)+'\n')
    print('release-capacity-assumptions: PASS', capacities, bss)


if __name__ == '__main__':
    main()
