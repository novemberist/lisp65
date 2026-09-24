"""Compare an executed result with a receipt without publishing over it."""
import json
import hashlib
from pathlib import Path
import tempfile

from terminal_ingress_artifacts import ArtifactError, read_only


def verify(path, result):
    before = path.read_bytes()
    with read_only():
        if json.loads(before) != result:
            raise ArtifactError('live result differs; a successor receipt is required: ' + str(path))
        try:
            path.open('wb')
        except ArtifactError:
            pass
        else:
            raise ArtifactError('receipt-write mutation survived')
    if path.read_bytes() != before:
        raise ArtifactError('receipt changed during verification')
    print('receipt verification: PASS; rejected-write=1; changed-receipts=0')


def report(path, result):
    """Keep a live oracle's already-asserted result separate from its history.

Unlike verify(), this is only for gates whose executable assertions, rather
than equality to an old result, have always been their acceptance oracle.
Every changed result receives a distinct successor, carrying its predecessor
and the complete current value. It never replaces or silently normalizes it.
    """
    before = path.read_bytes() if path.is_file() else None
    with read_only():
        try:
            path.open('wb')
        except ArtifactError:
            pass
        else:
            raise ArtifactError('receipt-write mutation survived')
    if before is not None and json.loads(before) == result:
        verify(path, result)
        return
    root = Path(__file__).resolve().parents[2]
    output = root / 'build/check-result-successors'
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w', prefix=path.stem+'-', suffix='.json',
                                     dir=output, delete=False) as stream:
        json.dump(dict(boundary='Live executed oracle; not a historical replay',
            predecessor=None if before is None else dict(path=str(path), bytes=len(before),
                sha256=hashlib.sha256(before).hexdigest()), result=result), stream,
            indent=2, sort_keys=True)
        stream.write('\n')
        destination = stream.name
    if before is not None and path.read_bytes() != before:
        raise ArtifactError('historical receipt changed')
    print('live successor: '+destination+'; rejected-write=1; changed-receipts=0')
