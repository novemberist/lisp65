"""Artifact-only historical prices (09b91c98); never replay a producer.

Recorded numerical assertions and their mutations remain executable. Sources
are read at the declared era, artifacts at their recorded SHA. Neither a
compiler invocation nor a write is permitted inside the verification scope.
"""
from copy import deepcopy
import json
import subprocess
from unittest.mock import patch

from terminal_ingress_artifacts import ArtifactError, bindings, read_only, sha

PINS = {
    'c2_v111_locality_replay_closure':
        'f48360c5086e1819a3d0a03eb755eaa833cf8d0754627d893b799f9d1da2ea07',
    'block_26_compiler_prelude_card':
        '7ad937228b94f2789cc675564b3404fb3f75dceb6779a2f9bcdb71df84b3f91b',
    'c2_v190_native_prompt_editor_pricing':
        'a44f76bde4a9d5fb302d2a3f191529064129e6b2991f8328415afea82492dd4d',
    'c2_v200_symbol22_first_fault_pricing':
        '34de78cf6c00f96363209cc7b89f14c14247be69bec37bdf33af6e8feec41a56',
    'c2_v200_symbol22_first_fault_repricing':
        '8556488799d891b13b94d8af59083965fb96bccba13fdc4dd28ec9ddd285f0a6',
}


def check(module):
    name = module.RECEIPT.name
    key = module.Path(module.__file__).stem
    raw = module.RECEIPT.read_bytes()
    if sha(raw) != PINS[key]:
        raise ArtifactError('historical receipt SHA drift: ' + name)
    value = json.loads(raw)
    era = (getattr(module, 'SEAL_ERA', None)
           or getattr(module, 'EVIDENCE_ERA', None)
           or getattr(module, 'EVIDENCE_COMMIT', None)
           or getattr(module, 'SEALED_COMMIT', None)
           or 'c2bacfea339908101e78b2faa3ac326971092405')
    sources = {}
    for row in bindings(value):
        path = row['path']
        if path.startswith('build/'):
            continue
        current = module.ROOT / path
        if key == 'c2_v111_locality_replay_closure' and not current.is_file():
            fixture = module.FIXTURE/path
            if fixture.is_file():
                payload = fixture.read_bytes()
                if len(payload) != row['bytes'] or sha(payload) != row['sha256']:
                    raise ArtifactError('locality fixture SHA drift: '+path)
                sources[(path, row['sha256'])] = payload
                continue
        if 'commit' not in row and current.is_file():
            payload = current.read_bytes()
            if len(payload) == row['bytes'] and sha(payload) == row['sha256']:
                sources[(path, row['sha256'])] = payload
                continue
        commit = row.get('commit', era)
        payload = subprocess.check_output(
            ['git', 'show', commit + ':' + path], cwd=module.ROOT)
        if 'section' in row:
            header = row['section']
            text = payload.decode()
            if text.count(header) != 1:
                raise ArtifactError('historical section missing or ambiguous')
            payload = (header + text.split(header, 1)[1]).split('\n## ', 1)[0].rstrip().encode() + b'\n'
        if key == 'block_26_compiler_prelude_card' and sha(payload) != row['sha256']:
            # This receipt contains several explicitly inherited source eras.
            # A byte identity, never newest/available source, chooses the blob.
            commits = subprocess.check_output(['git','log','--all','--format=%H','--',path], cwd=module.ROOT).decode().splitlines()
            for candidate in commits:
                found = subprocess.run(['git','show',candidate+':'+path], cwd=module.ROOT,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                if found.returncode == 0 and sha(found.stdout) == row['sha256']:
                    payload = found.stdout
                    break
        sources[(path, row['sha256'])] = payload

    def verify(candidate):
        for row in bindings(candidate):
            payload = sources.get((row['path'], row['sha256']))
            if payload is None:
                payload = (module.ROOT / row['path']).read_bytes()
            if len(payload) != row['bytes'] or sha(payload) != row['sha256']:
                raise ArtifactError('historical artifact/source SHA drift: ' + row['path'])

    def forbidden(*args, **kwargs):
        raise ArtifactError('historical price attempted producer replay')

    if key == 'c2_v111_locality_replay_closure':
        rows = module.audit_contract(module.load(module.CONTRACT))
        module.sealed_source_era_selftest()
        with read_only(), patch.object(module, 'derive', forbidden), \
                patch.object(module, 'audit_contract', lambda _: rows):
            verify(value)
            module.validate(value, verify_inputs=True)
            actual = module.mutation_proof(value)
            if actual != value['mutations_rejected']:
                raise ArtifactError('historical locality mutations drift')
            try: module.RECEIPT.open('wb')
            except ArtifactError: pass
            else: raise ArtifactError('write mutation survived')
        print(key+': PASS historical artifacts, 33 original controls; rejected-write=1; rebuilds=0; no fresh noise replay')
        return 0
    if key == 'block_26_compiler_prelude_card':
        texts = {name: sources[(row['path'], row['sha256'])].decode()
                 for name, row in value['sources'].items()}
        texts['macros'] = texts.pop('prelude_macros')
        texts['lists'] = texts.pop('lists_core')
        texts['tier1'] = texts.pop('domain_tier1')
        with read_only(), patch.object(module, 'materialize', forbidden):
            verify(value)
            module.source_gate(texts)
            if module.mutation_gate(texts) != value['mutations_rejected']:
                raise ArtifactError('Card 4 original mutations drift')
            try: module.RECEIPT.open('wb')
            except ArtifactError: pass
            else: raise ArtifactError('write mutation survived')
        print(key+': PASS historical artifacts and 8 source mutations; rejected-write=1; rebuilds=0')
        return 0
    with read_only(), patch.object(module, 'derive', forbidden):
        verify(value)
        # The original validators receive the pre-mutation verification block,
        # exactly as in derive(); recorded mutation results are checked separately.
        checked = deepcopy(value)
        expected = checked['verification'].pop('mutations_rejected')
        module.validate(checked)
        mutation = getattr(module, 'mutations', None) or module.mutation_selftest
        actual = mutation(checked)
        if actual != expected:
            raise ArtifactError('historical mutation population drift')
        if module.REPORT.read_text() != module.report(value):
            raise ArtifactError('historical report arithmetic drift')
        rejected = []
        for label, operation in (
            ('write-receipt', lambda: module.RECEIPT.open('wb')),
            ('producer-replay', module.derive),
        ):
            try:
                operation()
            except ArtifactError:
                rejected.append(label)
            else:
                raise ArtifactError('side-effect mutation survived: ' + label)
        bad = deepcopy(value)
        next(row for row in bindings(bad) if row['path'].startswith('build/'))['sha256'] = '00' * 32
        try:
            verify(bad)
        except ArtifactError:
            rejected.append('wrong-artifact-sha')
        else:
            raise ArtifactError('wrong artifact SHA survived')
    print(key + ': PASS historical artifact/SHA verification; '
          + str(len(actual)) + ' original controls, '
          + str(len(rejected)) + ' side-effect/integrity controls; rebuilds=0')
    return 0
