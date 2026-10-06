"""Record exact toolchain trees and pinned host tools for two reproductions (2.5.4, Fedora 45 host).

Successor of c2_v253_r1_toolchain.py (immutable; its pins are the Fedora 44 host tools of 2026-10-03, on which
the 2.5.4 Final r1 was linked).  The build host was upgraded to Fedora 45 on 2026-10-04, after the Final and
before the public reproductions.  Reviewer decision 2026-10-04: the old host tools are not restored; the 2.5.4
public authority is qualified on the new host.  The Final was linked with FINAL_HOST_TOOLS, the two public
reproductions run with HOST_TOOLS, and both must give the same ELF, LTO object, PRG and D81 byte for byte.
The record written here carries both pin sets side by side.
/usr/bin/llvm-link merges the canonical objects into one bitcode file before the single product link; that
intermediate file is HOST-DEPENDENT (LLVM 23.1.2 writes a different combined-c.bc than the Final host did) and
is not an artifact: the reproduction gate records it per reproduction and never compares it with the Final.
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

FORMAT='lisp65-v254-toolchain-v1'
# Reproduction host (Fedora 45, measured 2026-10-04): llvm-23.1.2-2.fc45, util-linux-2.42.4-1.fc45, gcc-16.2.1-2.fc45.1.
HOST='Fedora 45'
HOST_TOOLS={'/usr/bin/llvm-link':'dc265a662955c414c16eea8b4eec8af24322608bf6b5be6ee585f72fef90d47c',
            '/usr/bin/setarch':'8a6670f4aa0a72a08715a076549efa35832c0ce3b69c5926b96c6636a2075f3e',
            '/usr/bin/cc':'66317f5338535ded9ce9e2fc7b1c20d33bf96b7d6d1c35a71aa6dc309be3a57e'}
# Final host (Fedora 44): the pins of c2_v253_r1_toolchain.py, with which Seed and Final r1 were built.
FINAL_HOST='Fedora 44'
FINAL_HOST_TOOLS={'/usr/bin/llvm-link':'fbf634ce234c92624853e51226c408e2325953d7266080f2c5a9c8847f383e40',
                  '/usr/bin/setarch':'84985115f7365b9a85aba1fa0a51da1feb9a31ff1df54e36cd577ab8e93d8e28',
                  '/usr/bin/cc':'153e46b4657620f2baef1b4a70b4b4f275772faa5b0fb9e415697e87ebcb7fea'}
RULE=('Final r1 was linked on the Final host; the public reproductions run on the reproduction host. ELF, LTO object, '
      'PRG and D81 must be byte-identical to the Final. The merged bitcode written by /usr/bin/llvm-link is a '
      'host-dependent intermediate and is recorded, not compared with the Final.')
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
    value=dict(format=FORMAT,status='PASS',source=str(source.resolve()),reproductions=[str(r.resolve()) for r in roots],files=expected,host_tools=host_tools(),
               host=HOST,final_host=FINAL_HOST,final_host_tools=[dict(path=p,sha256=d) for p,d in sorted(FINAL_HOST_TOOLS.items())],rule=RULE)
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
        require(set(HOST_TOOLS)==set(FINAL_HOST_TOOLS) and all(HOST_TOOLS[p]!=FINAL_HOST_TOOLS[p] for p in HOST_TOOLS),'host pin sets')
        try:host_tools(FINAL_HOST_TOOLS)
        except ValueError:pass
        else:raise AssertionError('Final host pins accepted on the reproduction host')
        try:host_tools({'/usr/bin/setarch':'0'*64})
        except ValueError:pass
        else:raise AssertionError('host tool drift accepted')
        (source/'escape').symlink_to('/tmp')
        try:inventory(source)
        except ValueError:pass
        else:raise AssertionError('escape accepted')
    return dict(status='PASS',synthetic_tests=6,host_tools=len(HOST_TOOLS),host=HOST,final_host=FINAL_HOST)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--selftest',action='store_true');p.add_argument('--source',type=Path);p.add_argument('--roots',type=Path,nargs=2);p.add_argument('--out',type=Path);a=p.parse_args()
    if a.selftest:print(json.dumps(selftest()))
    else:
        require(a.source and a.roots and a.out,'source, roots and out required');record(a.source,a.roots,a.out);print('PASS: two exact external toolchain copies')
