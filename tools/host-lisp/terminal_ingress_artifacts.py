"""Read-only validation of the historical terminal-ingress artifact world."""
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
import hashlib
import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

ERA = '61a861f14f1aeda8328fc5b4426202170ba56754'
RECEIPT_SHA = '8270c660532fbe48234347d029f51e8cd95c392de26011f12114c2fc051db57f'
ACTIVE = ContextVar('terminal_ingress_artifact_only', default=False)

class ArtifactError(RuntimeError):
    pass

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def reject(event, args):
    if not ACTIVE.get():
        return
    if event == 'open':
        mode, flags = args[1:3]
        if (isinstance(mode, str) and any(c in mode for c in 'wax+')) or (
                isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND)):
            raise ArtifactError('artifact checker attempted a write: ' + str(args[0]))
    if event in {'subprocess.Popen', 'os.system', 'os.exec', 'os.posix_spawn',
                 'os.remove', 'os.rename', 'os.rmdir', 'os.mkdir', 'os.link',
                 'os.symlink', 'os.truncate', 'os.chmod', 'os.utime'}:
        raise ArtifactError('artifact checker attempted side effect: ' + event)

sys.addaudithook(reject)

@contextmanager
def read_only():
    token = ACTIVE.set(True)
    try:
        yield
    finally:
        ACTIVE.reset(token)

def bindings(value):
    if isinstance(value, dict):
        if {'path', 'bytes', 'sha256'} <= value.keys():
            yield value
        for child in value.values():
            yield from bindings(child)
    elif isinstance(value, list):
        for child in value:
            yield from bindings(child)

def main(module):
    value = module.load(module.RECEIPT)
    if sha(module.RECEIPT.read_bytes()) != RECEIPT_SHA:
        raise ArtifactError('historical receipt SHA drift')
    # Git reads are explicit provenance reads, never a producer invocation.
    historical = {}
    for row in bindings(value):
        commit = row.get('commit') if row.get('authority') == 'git-blob' else None
        if row['path'] == str(module.DRIVER.relative_to(module.ROOT)):
            commit = ERA
        if commit:
            raw = subprocess.check_output(['git', 'show', commit + ':' + row['path']], cwd=module.ROOT)
            if len(raw) != row['bytes'] or sha(raw) != row['sha256']:
                raise ArtifactError('historical source SHA drift: ' + row['path'])
            historical[(row['path'], row['sha256'])] = raw

    def verify(trial):
        for row in bindings(trial):
            raw = historical.get((row['path'], row['sha256']))
            if raw is None:
                raw = (module.ROOT / row['path']).read_bytes()
            if len(raw) != row['bytes'] or sha(raw) != row['sha256']:
                raise ArtifactError('sealed artifact SHA drift: ' + row['path'])

    original_bind = module.bind
    def bound(path):
        if Path(path) == module.DRIVER:
            return value['authorities']['driver']
        return original_bind(path)
    def no_producer(*args, **kwargs):
        raise ArtifactError('producer called by historical artifact checker')

    with read_only(), patch.object(module, 'bind', bound), \
            patch.object(module, 'derive', no_producer), \
            patch.object(module, 'build_medium', no_producer), \
            patch.object(module.MEDIA, 'compile_stager', no_producer):
        verify(value)
        module.gate_wiring()
        module.runner_audit()
        module.validate(value, reproduce=False)
        rejected = module.mutations(value)
        if module.load(module.DEPLOY)['status'] != 'host-green-session-authorized-not-run':
            raise ArtifactError('deployment status drift')
        trial = deepcopy(value)
        trial['identity']['diagnostic_medium']['sha256'] = '00' * 32
        controls = [
            ('wrong-medium-SHA', lambda: verify(trial)),
            ('write-artifact', lambda: module.DIAG_D81.write_bytes(b'forbidden')),
            ('remove-artifact', lambda: module.DIAG_D81.unlink()),
            ('launch-producer', lambda: subprocess.run(['false'])),
            ('old-check-rebuild', lambda: module.derive(write_artifacts=False)),
            ('stager-build', lambda: module.MEDIA.compile_stager()),
        ]
        for name, run in controls:
            try:
                run()
            except ArtifactError:
                rejected.append(name)
            else:
                raise ArtifactError('negative control survived: ' + name)
    print('terminal-ingress artifacts: PASS; no builds/writes; controls=' + str(len(rejected)))
    return 0
