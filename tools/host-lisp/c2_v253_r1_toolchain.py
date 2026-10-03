"""Record exact toolchain trees and pinned host tools for two reproductions (2.5.3).

Successor of the 2.5.1 toolchain inventory (an untracked build script in
build/release-v2.5.1/reproduce-r2.py, files by path and hash only). Reviewer
decision 2026-09-30: additionally binds the
host tools the 2.5.3 Final recipe executes outside tools/llvm-mos -- /usr/bin/llvm-link
and /usr/bin/setarch (native recipe) and /usr/bin/cc (cold-stager host ABI
emitter) -- by path, symlink target and hash, against the reviewed pins.
Host shared libraries are not inventoried; the reproductions run on this host.
No executable runs.
"""
import argparse,hashlib,json,os,stat,tempfile
from pathlib import Path

def require(ok,msg):
    if not ok:raise ValueError(msg)
def inventory(root):
    root=root.resolve();require(root.is_dir(),'missing toolchain');rows=[]
    for p in sorted(root.rglob('*')):
        rel=str(p.relative_to(root));mode=stat.S_IMODE(p.lstat().st_mode)
        if p.is_symlink():
            target=os.readlink(p)
            require(not Path(target).is_absolute() and p.resolve().is_relative_to(root) and p.resolve().exists(),'escaping/broken toolchain symlink')
            rows.append(dict(path=rel,kind='symlink',target=target,mode=mode))
        elif p.is_file():
            h=hashlib.sha256()
            with p.open('rb') as f:
                for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
            rows.append(dict(path=rel,kind='file',bytes=p.stat().st_size,sha256=h.hexdigest(),mode=mode))
        else:require(p.is_dir(),'special toolchain file')
    require(rows,'empty toolchain');return rows

HOST_TOOLS={'/usr/bin/llvm-link':'fbf634ce234c92624853e51226c408e2325953d7266080f2c5a9c8847f383e40',
            '/usr/bin/setarch':'84985115f7365b9a85aba1fa0a51da1feb9a31ff1df54e36cd577ab8e93d8e28',
            '/usr/bin/cc':'153e46b4657620f2baef1b4a70b4b4f275772faa5b0fb9e415697e87ebcb7fea'}
def host_tools(pins=HOST_TOOLS):
    rows=[]
    for path,digest in sorted(pins.items()):
        p=Path(path);real=p.resolve();require(real.is_file(),'missing host tool: '+path)
        raw=real.read_bytes();got=hashlib.sha256(raw).hexdigest()
        require(got==digest,'host tool drift: '+path)
        rows.append(dict(path=path,resolved=str(real),bytes=len(raw),sha256=got,mode=stat.S_IMODE(real.stat().st_mode)))
    return rows

def record(source,roots,out):
    require(len(roots)==2 and roots[0].resolve()!=roots[1].resolve(),'two independent roots')
    expected=inventory(source)
    for root in roots:require(inventory(root/'tools/llvm-mos')==expected,'toolchain copy mismatch')
    value=dict(format='lisp65-v253-toolchain-v2',status='PASS',source=str(source.resolve()),reproductions=[str(r.resolve()) for r in roots],files=expected,host_tools=host_tools())
    out.parent.mkdir(parents=True,exist_ok=True)
    with out.open('x') as f:json.dump(value,f,indent=2,sort_keys=True);f.write('\n')
    return value

def selftest():
    import shutil
    with tempfile.TemporaryDirectory() as t:
        base=Path(t);source=base/'source';source.mkdir();(source/'cc').write_bytes(b'compiler');(source/'alias').symlink_to('cc')
        roots=[base/'a',base/'b']
        for root in roots:shutil.copytree(source,root/'tools/llvm-mos',symlinks=True)
        out=base/'inventory.json';record(source,roots,out)
        try:record(source,roots,out)
        except FileExistsError:pass
        else:raise AssertionError('overwrite accepted')
        (roots[1]/'tools/llvm-mos/cc').write_bytes(b'wrong')
        try:record(source,roots,base/'bad.json')
        except ValueError:pass
        else:raise AssertionError('drift accepted')
        host_tools()
        try:host_tools({'/usr/bin/setarch':'0'*64})
        except ValueError:pass
        else:raise AssertionError('host tool drift accepted')
        (source/'escape').symlink_to('/tmp')
        try:inventory(source)
        except ValueError:pass
        else:raise AssertionError('escape accepted')
    return dict(status='PASS',synthetic_tests=5,host_tools=len(HOST_TOOLS))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--selftest',action='store_true');p.add_argument('--source',type=Path);p.add_argument('--roots',type=Path,nargs=2);p.add_argument('--out',type=Path);a=p.parse_args()
    if a.selftest:print(json.dumps(selftest()))
    else:
        require(a.source and a.roots and a.out,'source, roots and out required');record(a.source,a.roots,a.out);print('PASS: two exact external toolchain copies')
