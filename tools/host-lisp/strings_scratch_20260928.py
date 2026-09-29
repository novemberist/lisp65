"""Fresh unbound output roots; canonical content receipts never bind scratch."""
import hashlib
import os
import json
import tempfile
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch
import strings_successor_r2_20260928 as S

@contextmanager
def scratch():
    with tempfile.TemporaryDirectory(prefix='strings-check-', dir=os.environ.get('LISP65_CHECK_SCRATCH_ROOT', S.ROOT/'build')) as raw:
        root=Path(raw)
        with patch.object(S, 'OUT', root):
            yield root

def normalized(value, root):
    """Retain all output bytes in digests, replacing only the ephemeral root."""
    absolute=str(root); relative=str(root.relative_to(S.ROOT))
    def text(s):return s.replace(absolute, '@scratch').replace(relative, '@scratch')
    # Manifests also bind disassembly containing the output prefix. Rehash
    # those dependencies after canonicalizing paths, retaining every byte.
    files={p:p.read_bytes() for p in root.rglob('*') if p.is_file()}
    hashes={hashlib.sha256(raw).hexdigest():hashlib.sha256(raw).hexdigest() for raw in files.values()}
    def canonical(raw):
        try:
            data=text(raw.decode())
            import re
            data=re.sub(r'(?<![0-9a-f])[0-9a-f]{64}(?![0-9a-f])',lambda m:hashes.get(m[0],m[0]),data)
            return data.encode()
        except UnicodeDecodeError:return raw
    for _ in range(20):
        updated={hashlib.sha256(raw).hexdigest():hashlib.sha256(canonical(raw)).hexdigest() for raw in files.values()}
        if updated==hashes:break
        hashes=updated
    else:raise ValueError('scratch digest graph did not converge')
    def walk(v):
        if isinstance(v, dict):
            if isinstance(v.get('path'),str) and 'sha256' in v:
                p=Path(v['path']);p=p if p.is_absolute() else S.ROOT/p
                if p.is_relative_to(root):
                    raw=canonical(files[p])
                    return dict(content=text(v['path']), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
            return {k:walk(x) for k,x in v.items()}
        if isinstance(v,list):return [walk(x) for x in v]
        if isinstance(v,str):return hashes.get(v,text(v))
        return v
    return walk(value)

@contextmanager
def generated(root):
    import bytecode_p0_stdlib as P
    import v2_workbench_codemod as C
    target=root/'generated'
    C.generate(C.DEFAULT_CLOSURE,target)
    original=P._suite_path
    def resolve(path,base_dir=None):
        p=Path(original(path,base_dir)).resolve()
        import evidence_era as E
        if E.host_source_commit() is not None:return str(p)
        if p.is_relative_to(C.DEFAULT_OUTPUT.resolve()):return str(target/p.relative_to(C.DEFAULT_OUTPUT.resolve()))
        return str(p)
    with patch.object(P,'_suite_path',resolve):yield
