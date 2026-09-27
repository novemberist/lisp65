#!/usr/bin/env python3
"""comfort-library card: add the sixth library package to the 2.4.0 medium.

Budget 0 Seed / 0 Final / 0 product link.  The accepted 2.4.0 D81 (87cb0f6e) is
copied; the Comfort role (repl-comfort, shelf label "repl") is packed through
the same L65I codec the 2.4.0 producer uses (c2_defstruct_foundations_gate.
measured_row, product build id from config/c2-v240-public-plane/libraries/
libraries.json), written with c1541 as a new file, and the library index is
rewritten as the five decoded 2.4.0 rows byte-for-byte plus one appended row
(the v2.1 Comfort media card's delete-and-write method).  The tool then proves
that every other visible file, directory record and sector chain is unchanged
and that the D81 differs only in the BAM, directory, index and new-file
sectors.  One-shot: the output directory must not exist.

r2 (this binding): the library carries the trailing-comment seam fix (source
97ebf0e5, blob 636b684e, still 897 B); r1 (blob 1b3f88be, the branch source
byte for byte) stays as the superseded attempt in build/comfort-library-medium-r1.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / 'tools/host-lisp'
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_defstruct_foundations_gate as F  # noqa: E402
import c2_require_resolver_gate as L65I  # noqa: E402

D81 = L65I.D81
ELF = ROOT / 'build/nested-error-recovery-final-r1/wplto/lisp65-c2-substitution-linked.prg.elf'
BASE = ROOT / 'build/nested-error-recovery-seed-medium-r1/packed/hardware-sp-seed.d81'
BASE_PACKED = ROOT / 'build/nested-error-recovery-seed-medium-r1/packed-receipt.json'
AUTHORITY = ROOT / 'config/c2-v240-public-plane/media-authority.json'
LIBRARIES = ROOT / 'config/c2-v240-public-plane/libraries/libraries.json'
MANIFEST = ROOT / 'build/comfort-library-r1/role-r2/repl-comfort.manifest.json'
SUITE = ROOT / 'tests/bytecode/libs/p0-repl-comfort-v240.json'
SOURCE = ROOT / 'lib/repl-comfort-v240.lisp'
OUT = ROOT / 'build/comfort-library-medium-r2'
EXPECT = dict(
    elf='66165507a8e5ad1d857afdd967f9056be2ce7bbccc332d5328e981398078b47b',
    d81='87cb0f6ea9b2dc690f66ee11d9c76d5138e11f28452254a9b5730c78cabc5f5d',
    blob='636b684e11cace84bb2bf4a60c89fdb1e598ca1aa9c14698a46fadf794cd15f2',
    source='97ebf0e597bd7b1e84b406af552c30b39a4e855cdd468171c3f13d8404cea032')
NAME, SHELF = 'repl-comfort', 'repl'


def require(ok, message):
    if not ok:
        raise SystemExit('comfort-library-medium: ' + message)


def bind(p: Path) -> dict:
    data = p.read_bytes()
    return dict(path=str(p.relative_to(ROOT)), bytes=len(data), sha256=hashlib.sha256(data).hexdigest())


def c1541(image: Path, *arguments: str) -> str:
    tool = shutil.which('c1541')
    require(tool is not None, 'c1541 unavailable')
    r = subprocess.run([tool, str(image), *arguments], cwd=ROOT, text=True,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    require(r.returncode == 0, 'c1541 failed:\n' + r.stdout)
    return r.stdout


def directory(data: bytes) -> dict[bytes, dict]:
    out = {}
    for slot in D81.directory_slots(data):
        if not slot.record[2]:
            continue
        name = D81.entry_name(slot.record)
        out[name] = dict(slot=[getattr(slot, 'track', None), getattr(slot, 'sector', None), getattr(slot, 'index', None)],
                         record=bytes(slot.record).hex(),
                         chain=[list(x) for x in D81.file_chain(data, slot.record)])
    return out


def main() -> int:
    require(bind(ELF)['sha256'] == EXPECT['elf'], 'ELF identity')
    require(bind(BASE)['sha256'] == EXPECT['d81'], 'base D81 identity')
    require(bind(SOURCE)['sha256'] == EXPECT['source'], 'package source identity')
    manifest = json.loads(MANIFEST.read_text())
    blob = (ROOT / manifest['blob']).read_bytes() if not Path(manifest['blob']).is_absolute() else Path(manifest['blob']).read_bytes()
    require(hashlib.sha256(blob).hexdigest() == EXPECT['blob'] and len(blob) == 897, 'role blob identity')
    libraries = json.loads(LIBRARIES.read_text())
    build_id = int(libraries['product_build_id'])
    authority = json.loads(AUTHORITY.read_text())
    require(authority['medium']['sha256'] == EXPECT['d81'], 'media authority names another medium')
    require(not OUT.exists(), 'one-shot: output exists')
    packed = OUT / 'packed'
    packed.mkdir(parents=True)
    medium = packed / 'cmf240.d81'
    shutil.copyfile(BASE, medium)
    medium.chmod(0o644)

    before_raw = BASE.read_bytes()
    before = D81.visible_files(before_raw)
    require(set(before) == {k.encode() for k in authority['files']}, 'base visible population differs from authority')
    for name, row in authority['files'].items():
        require(hashlib.sha256(before[name.encode()]).hexdigest() == row['sha256'], 'base file drift: ' + name)
    require(b'REPL-COMFORT' not in before, 'base already carries the package')
    old_index = before[b'L65INDEX']
    five = {r['name']: before[r['name'].upper().encode()] for r in libraries['libraries']}
    old_rows = L65I.decode_index(old_index, five, artifact_build_id=build_id)
    require([r['name'] for r in old_rows] == [r['name'] for r in libraries['libraries']], 'base index population')

    placeholder, artifact = F.measured_row(NAME, NAME, SHELF, MANIFEST, (), 1, 1, product_build_id=build_id)
    art = packed / 'repl-comfort.l65s'
    art.write_bytes(artifact)
    c1541(medium, '-write', str(art), NAME)
    locator = L65I.d81_locators(medium)[NAME]
    row, located = F.measured_row(NAME, NAME, SHELF, MANIFEST, (), *locator, product_build_id=build_id)
    require(located == artifact, 'locator changed library payload')
    index_bytes = L65I.encode_index([*old_rows, row])
    require(index_bytes[L65I.HEADER_BYTES:L65I.HEADER_BYTES + 5 * L65I.ROW_BYTES]
            == old_index[L65I.HEADER_BYTES:], 'the five 2.4.0 index rows changed')
    index = packed / 'l65index'
    index.write_bytes(index_bytes)
    c1541(medium, '-delete', 'l65index')
    c1541(medium, '-write', str(index), 'l65index')

    after_raw = medium.read_bytes()
    D81.validate_bam(after_raw)
    after = D81.visible_files(after_raw)
    added = sorted(k.decode() for k in set(after) - set(before))
    changed = sorted(k.decode() for k in before if after.get(k) != before[k])
    require(added == ['REPL-COMFORT'] and changed == ['L65INDEX'], f'population: added={added} changed={changed}')
    require(after[b'REPL-COMFORT'] == artifact and after[b'L65INDEX'] == index_bytes, 'written payloads differ')
    all_artifacts = {**five, NAME: artifact}
    rows = L65I.decode_index(index_bytes, all_artifacts, artifact_build_id=build_id)
    require(len(rows) == 6 and rows[5]['name'] == NAME and rows[5]['dependencies'] == [], 'six-row index')
    mutations = L65I.mutation_gate(index_bytes, all_artifacts, artifact_build_id=build_id)

    dir_before, dir_after = directory(before_raw), directory(after_raw)
    record_changes = sorted(k.decode() for k in dir_before if dir_before[k] != dir_after.get(k))
    require(record_changes in ([], ['L65INDEX']), f'other directory records changed: {record_changes}')
    sectors = []
    for off in range(0, len(after_raw), 256):
        if before_raw[off:off + 256] != after_raw[off:off + 256]:
            sectors.append([off // 256 // 40 + 1, off // 256 % 40])
    owned = {tuple(x) for k in (b'L65INDEX', b'REPL-COMFORT') for x in dir_after[k]['chain']}
    owned |= {tuple(x) for x in dir_before[b'L65INDEX']['chain']}
    foreign = [s for s in sectors if tuple(s) not in owned and s[0] != 40]
    require(not foreign, f'sectors outside BAM/directory/index/new file changed: {foreign}')

    value = dict(
        status='PASS: SIXTH PACKAGE ADDED; EVERY OTHER MEDIUM FILE BYTE-IDENTICAL TO 2.4.0',
        card='comfort-library', binding='180cb993',
        budget=dict(seed=0, final=0, product_link=0, product_builds=0, device_contacts=0),
        elf=bind(ELF), base_medium=bind(BASE), base_packed_receipt=bind(BASE_PACKED),
        media_authority=bind(AUTHORITY), libraries=bind(LIBRARIES),
        medium=bind(medium), artifact=bind(art), index=bind(index),
        role_manifest=bind(MANIFEST), suite=bind(SUITE), source=bind(SOURCE),
        package=dict(name=NAME, shelf=SHELF, d81_file='REPL-COMFORT', locator=list(locator),
                     row=row, code_bytes=len(blob), artifact_bytes=len(artifact)),
        product_build_id=f'0x{build_id:08x}',
        files_unchanged=sorted(k.decode() for k in before if k != b'L65INDEX'),
        files_unchanged_count=len(before) - 1,
        file_sha256={k.decode(): hashlib.sha256(v).hexdigest() for k, v in sorted(after.items())},
        index_rows=rows, index_prefix_rows_identical=5, mutations=mutations,
        directory_records_changed=record_changes, changed_sectors=sectors,
        directory=dict(before={k.decode(): v for k, v in dir_before.items()},
                       after={k.decode(): v for k, v in dir_after.items()}),
        tool=bind(Path(__file__)),
        claim='Host packing and readback only; runtime ELF not rebuilt; no device contact.')
    (OUT / 'packed-receipt.json').write_text(json.dumps(value, indent=2) + '\n')
    print(value['status'], value['medium']['sha256'], 'locator', locator, 'sectors', len(sectors))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
