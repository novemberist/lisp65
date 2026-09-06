#!/usr/bin/env python3
# SPDX-License-Identifier: MPL-2.0
"""Audit every blob of the actual source commit, not a policy-selected subset.

An optional source archive must have exactly the same blob population and bytes.
Binary declarations are exact paths with identities, source inputs and a consumer;
they never exempt an embedded private path or executable ELF from inspection.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import subprocess
import tarfile

from public_export import PRIVATE_PATH_RE, scan_data

CONTRACT = 'config/public-export-binary-contract.json'
BINARY_SUFFIXES = {'.so', '.o', '.a', '.bin', '.prg', '.d81', '.l65m', '.elf'}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def safe_name(name):
    p = PurePosixPath(name)
    require(bool(name) and not p.is_absolute() and '..' not in p.parts
            and str(p) == name, 'non-canonical export path: ' + name)
    return name


def archive_blobs(raw, prefix=''):
    blobs = {}
    with tarfile.open(fileobj=io.BytesIO(raw), mode='r:*') as archive:
        for entry in archive:
            if entry.isdir():
                continue
            require(entry.isfile(), 'non-regular export member: ' + entry.name)
            require(entry.name.startswith(prefix), 'archive root mismatch')
            name = safe_name(entry.name[len(prefix):])
            require(name not in blobs, 'duplicate archive member: ' + name)
            blobs[name] = archive.extractfile(entry).read()
    require(blobs, 'empty export population')
    return blobs


def commit_blobs(root, commit):
    # git archive includes every tracked blob, including files excluded by the
    # private export selector. Filtering here would repeat the original defect.
    blobs = archive_blobs(subprocess.check_output(
        ['git', 'archive', '--format=tar', commit], cwd=root))
    population = set()
    for record in subprocess.check_output(
            ['git', 'ls-tree', '-rz', commit], cwd=root).split(b'\0'):
        if not record: continue
        metadata, name = record.split(b'\t', 1)
        mode, kind, _oid = metadata.split()
        require(kind == b'blob' and mode in (b'100644', b'100755'),
                'non-regular source-tree member')
        population.add(name.decode())
    require(set(blobs) == population,
            'git archive omitted tracked members (including export-ignore)')
    return blobs


def is_binary(name, raw):
    return (PurePosixPath(name).suffix.lower() in BINARY_SUFFIXES
            or b'\0' in raw or raw.startswith((b'\x7fELF', b'!<arch>\n', b'MZ')))


def audit(blobs, contract):
    require(contract.get('format') == 'lisp65-public-export-binaries-v1',
            'missing binary contract')
    declarations = contract.get('artifacts', {})
    require(isinstance(declarations, dict), 'invalid artifact declarations')
    binaries = {name for name, raw in blobs.items() if is_binary(name, raw)}
    require(set(declarations) == binaries, 'binary declaration population mismatch: '
            + repr(sorted(set(declarations) ^ binaries)))
    rows = []
    for name, raw in sorted(blobs.items()):
        safe_name(name)
        # Scan the entire blob, including binary/debug/string tables.
        require(not PRIVATE_PATH_RE.search(raw), 'private absolute path: ' + name)
        require(not raw.startswith(b'\x7fELF'), 'prebuilt ELF forbidden: ' + name)
        if name in binaries:
            declaration = declarations[name]
            require(declaration.get('sha256') == digest(raw)
                    and declaration.get('bytes') == len(raw),
                    'binary identity mismatch: ' + name)
            sources = declaration.get('sources', {})
            require(isinstance(sources, dict) and sources,
                    'binary source provenance missing: ' + name)
            for source, sha in sources.items():
                safe_name(source)
                require(source in blobs and source not in binaries
                        and digest(blobs[source]) == sha,
                        'binary source unavailable or changed: ' + source)
            require(declaration.get('kind') in ('serialized-build-input', 'test-fixture'),
                    'unclassified prebuilt artifact: ' + name)
            require(declaration.get('reproduction_scope') == 'consumed-byte-identically; regeneration-not-claimed',
                    'binary reproduction claim absent: ' + name)
            recipe = declaration.get('consumer', {})
            path = recipe.get('path', '')
            safe_name(path)
            require(path in blobs and path not in binaries
                    and digest(blobs[path]) == recipe.get('sha256')
                    and isinstance(recipe.get('command'), list)
                    and recipe['command'] and all(isinstance(x, str) and x
                                                 for x in recipe['command']),
                    'binary consumer missing or changed: ' + name)
        rows.append({'path': name, 'bytes': len(raw), 'sha256': digest(raw),
                     'classification': 'declared-binary' if name in binaries else 'source'})
    return {'status': 'PASS', 'population': 'all git-archive blobs; no selector',
            'files': rows, 'binary_count': len(binaries)}


def audit_export(blobs):
    require(CONTRACT in blobs, 'export binary contract absent')
    require('config/public-export-policy.json' in blobs, 'export policy absent')
    policy = json.loads(blobs['config/public-export-policy.json'])
    gates = policy['gates']
    require(gates['forbid_elf_binaries'] is True
            and gates['forbid_private_absolute_paths'] is True,
            'export safety contract weakened')
    require(set(policy['required']) <= set(blobs), 'required export member absent')
    for name, raw in blobs.items():
        errors = scan_data(name, raw, policy)
        require(not errors, '\n'.join(errors))
    result = audit(blobs, json.loads(blobs[CONTRACT]))
    result['existing_export_policy'] = 'PASS over every source blob'
    return result


def compare_archive(blobs, archive, source_commit=None):
    archive = dict(archive)
    if source_commit is not None:
        name = 'PUBLIC-SOURCE-MANIFEST.json'
        require(name not in blobs and name in archive, 'derived source manifest absent or authored')
        manifest = json.loads(archive.pop(name))
        rows = [{'path': n, 'bytes': len(b), 'sha256': digest(b)}
                for n, b in sorted(blobs.items())]
        tree = hashlib.sha256()
        for row in rows:
            tree.update(row['path'].encode() + b'\0' + row['sha256'].encode() + b'\n')
        require(manifest == {'format': 'lisp65-public-source-manifest-v1',
            'source_commit': source_commit, 'source_tree_clean': True,
            'file_count': len(rows), 'tree_sha256': tree.hexdigest(), 'files': rows},
            'derived source manifest population or identity differs')
    require(blobs == archive, 'archive population or bytes differ from source commit')


def selftest():
    source = b'int value;\n'
    recipe = b'generate fixture\n'
    binary = b'\0\1'
    blobs = {'src/input.c': source, 'scripts/build.py': recipe, 'data.bin': binary}
    contract = {'format': 'lisp65-public-export-binaries-v1', 'artifacts': {
        'data.bin': {'sha256': digest(binary), 'bytes': 2,
            'kind': 'serialized-build-input',
            'reproduction_scope': 'consumed-byte-identically; regeneration-not-claimed',
            'sources': {'src/input.c': digest(source)},
            'consumer': {'path': 'scripts/build.py', 'sha256': digest(recipe),
                       'command': ['python3', 'scripts/build.py']}}}}
    audit(blobs, contract)
    cases = []
    import copy
    for label in ('private-text', 'private-binary', 'new-undeclared-binary',
                  'declaration-omitted', 'source-omitted', 'consumer-omitted',
                  'binary-changed', 'new-excluded-subtree', 'elf-with-declaration'):
        b, c = dict(blobs), copy.deepcopy(contract)
        private = b'/' + b'home/' + b'fixture/private/source.c'
        if label == 'private-text': b['note.txt'] = private
        elif label == 'private-binary':
            b['data.bin'] += private
            c['artifacts']['data.bin'].update(sha256=digest(b['data.bin']), bytes=len(b['data.bin']))
        elif label == 'new-undeclared-binary': b['new.bin'] = binary
        elif label == 'declaration-omitted': c['artifacts'].clear()
        elif label == 'source-omitted': del b['src/input.c']
        elif label == 'consumer-omitted': del c['artifacts']['data.bin']['consumer']
        elif label == 'binary-changed': b['data.bin'] += b'X'
        elif label == 'new-excluded-subtree': b['excluded/new.txt'] = private
        elif label == 'elf-with-declaration':
            b['data.bin'] = b'\x7fELF\0'
            c['artifacts']['data.bin'].update(sha256=digest(b['data.bin']), bytes=len(b['data.bin']))
        try: audit(b, c)
        except ValueError: cases.append(label)
        else: raise AssertionError('mutation survived: ' + label)
    for label, b in [('archive-member-omitted', {'data.bin': binary}),
                     ('archive-member-added', {**blobs, 'extra.txt': b'x'})]:
        try: compare_archive(blobs, b)
        except ValueError: cases.append(label)
        else: raise AssertionError('mutation survived: ' + label)
    return {'status': 'PASS', 'mutations_rejected': cases,
            'relative_path_and_declared_binary_control': 'PASS'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--selftest', action='store_true')
    parser.add_argument('--repository', type=Path, default=Path.cwd())
    parser.add_argument('--commit', default='HEAD')
    parser.add_argument('--archive', type=Path)
    parser.add_argument('--archive-root')
    parser.add_argument('--receipt', type=Path)
    args = parser.parse_args()
    try:
        if args.selftest:
            result = selftest()
        else:
            blobs = commit_blobs(args.repository, args.commit)
            result = audit_export(blobs)
            if args.archive:
                require(args.archive_root, 'explicit archive root required')
                commit = subprocess.check_output(['git', 'rev-parse', args.commit],
                                                 cwd=args.repository).decode().strip()
                compare_archive(blobs, archive_blobs(args.archive.read_bytes(), args.archive_root + '/'), commit)
                result['archive_comparison'] = 'PASS: exact population and bytes'
            result['mutations'] = selftest()
    except (ValueError, KeyError) as exc:
        raise SystemExit('HALT: ' + str(exc)) from exc
    if args.receipt:
        args.receipt.parent.mkdir(parents=True, exist_ok=True)
        args.receipt.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'files'}, indent=2))


if __name__ == '__main__':
    main()
