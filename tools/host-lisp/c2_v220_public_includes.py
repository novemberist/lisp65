#!/usr/bin/env python3
"""Resolve consumed C includes before code generation; bind assembler includes."""
import json
import re
import shlex
import subprocess
import os
from pathlib import Path

import c2_v220_public_product as C
import c2_v220_public_native as N


def verify_dependency(row, authority):
    key=os.path.normpath(row['path'])
    N.require(key in authority,'include outside bound projection: '+key)
    N.require(all(row[k]==authority[key][k] for k in ('bytes','sha256')),
              'include identity drift: '+key)


def check(*,headers=None,target_name='resident-island-seed.prg'):
    captured=C.command_preflight(header_overrides=headers,target_name=target_name)
    commands=C.load(N.local(captured['receipt']))['commands']
    compile_commands=[cmd for cmd in commands if '-c' in cmd]
    N.require(all(cmd[i+1]!='scripts' for cmd in compile_commands for i,x in enumerate(cmd) if x=='-I'),
              'unbound scripts search path restored')
    closure=C.load(N.ROOT/'config/c2-v220-public-native/include-closure.json')
    authority={r['path']:r for r in closure['dependencies']}
    N.require(len(authority)==len(closure['dependencies']),'duplicate dependency owner')
    N.require(target_name in ('resident-island-seed.prg','lisp65-c2-substitution-linked.prg'),'unbound include phase')
    if target_name=='lisp65-c2-substitution-linked.prg':
        authority.update({r['path']:r for r in closure['final_dependencies']})
    kernel_path='build/retirement-repair-product-r2/wplto/c2-kernal-window.generated.h'
    sentinel=C.P.kernal_header_values(C.P.KERNAL_CRC_BINDING_SENTINEL,'0'*64)
    import hashlib
    N.require(authority[kernel_path]['sha256']==hashlib.sha256(sentinel).hexdigest()
              and authority[kernel_path]['bytes']==len(sentinel),'compiler kernel authority is not sentinel')
    postlink=C.P.kernal_header_values(0xc4fb,'d9628f3e7060d50a174d6d72dc48d55c896fe3fc68e86e2783431c553b9a26ca')
    try:verify_dependency(dict(path=kernel_path,bytes=len(postlink),sha256=hashlib.sha256(postlink).hexdigest()),authority)
    except ValueError:pass
    else:raise ValueError('postlink kernel header accepted as compiler input')
    native=C.load(N.MANIFEST)
    expected=[r['materialized_path'] for r in native['sources'] if r['translation_unit']]
    N.require([cmd[cmd.index('-c')+1] for cmd in compile_commands]==expected,'include gate TU population drift')
    out=N.local(captured['receipt']).with_suffix('.includes');out.mkdir()
    prepared=C.load(C.OUT/'public-source-prepared.json')
    alias=N.local(prepared['ordinary_stdlib_include']['path'])
    selected=N.bound(C.P.COMPILER_CONSUMED_STDLIB_HEADER_BINDING)
    N.require(N.bound(prepared['ordinary_stdlib_include'])==selected,'include path/value divergence')
    rows=[];repl_command=None
    result=dict(status='STARTED',translation_units=len(expected),rows=rows,
                ordinary_include=C.bind(alias),codegen_invocations=0,wplto=0,links=0)
    receipt=out/'receipt.json'
    def save():receipt.write_bytes(N.canonical(result))
    try:
        for ordinal,cmd in enumerate(compile_commands):
            source=cmd[cmd.index('-c')+1]
            if Path(source).suffix=='.s':
                # These units go directly to the assembler, not the C
                # preprocessor. Resolve every literal .include using the
                # assembler's configured search directories.
                directories=[N.ROOT]+[N.local(cmd[i+1]) for i,x in enumerate(cmd) if x=='-I']
                pending=[N.local(source)];seen=set();deps=[]
                while pending:
                    path=pending.pop()
                    if path in seen:continue
                    seen.add(path)
                    for name in re.findall(r'^\s*\.include\s+"([^"]+)"',path.read_text(),re.M):
                        found=next((p/name for p in directories if (p/name).is_file()),None)
                        N.require(found is not None,'assembler include absent: '+name)
                        binding=C.bind(found);verify_dependency(binding,authority)
                        deps.append(binding);pending.append(found)
                rows.append(dict(source=source,mode='assembler-include-resolution',dependencies=deps))
                continue
            arguments=list(cmd)
            at=arguments.index('-o');del arguments[at:at+2]
            arguments.remove('-c')
            dep=out/f'{ordinal:03d}.d'
            arguments+=['-E','-M','-MF',str(dep),'-MT','include-gate']
            N.require('-c' not in arguments and '-E' in arguments,'include check would generate code')
            run=subprocess.run(arguments,cwd=N.ROOT,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
            (out/f'{ordinal:03d}.log').write_text(run.stdout)
            N.require(run.returncode==0,'include preprocessing failed: '+source+'\n'+run.stdout)
            paths=shlex.split(dep.read_text().replace('\\\n',' ').split(':',1)[1])
            N.require(paths,'empty preprocessor dependency population')
            dependencies=[]
            for name in dict.fromkeys(paths):
                path=Path(name)
                if not path.is_absolute():path=N.ROOT/path
                if not path.is_relative_to(N.ROOT):
                    relative=path.resolve().relative_to(C.P.TOOLCHAIN.parent.resolve())
                    path=C.P.TOOLCHAIN.parent/relative
                path=Path(os.path.normpath(path))
                binding=C.bind(path);verify_dependency(binding,authority)
                dependencies.append(binding)
            rows.append(dict(source=source,mode='compiler-preprocessing-only',dependencies=dependencies))
            if source=='src/repl.c':repl_command=arguments
        N.require(repl_command is not None,'ordinary include regression consumer absent')
        # Exercise the actual lookup failure, not a source spelling predicate.
        raw=alias.read_bytes();alias.unlink()
        try:
            mutant=subprocess.run(repl_command,cwd=N.ROOT,text=True,
                                  stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
        finally:alias.write_bytes(raw)
        (out/'missing-header-mutation.log').write_text(mutant.stdout)
        N.require(mutant.returncode!=0 and "'stdlib-p0.h' file not found" in mutant.stdout,
                  'missing-header mutation survived or failed for another reason')
        N.require(N.bound(prepared['ordinary_stdlib_include'])==selected,'header restoration drift')
        # Reproduce the original successful-but-wrong lookup. The old source
        # still preprocesses; its resolved path must fail the identity gate.
        for name,wrapper in (('c2-stream-decoder.c','c2-stream-phase-02a.c'),
                             ('c2-stream-v2-decoder.c','c2-stream-v2-phase-07.c')):
            local=C.OUT/'generated-product-sources'/name
            command=next(list(c) for c in compile_commands if c[c.index('-c')+1].endswith('/'+wrapper))
            at=command.index('-o');del command[at:at+2];command.remove('-c')
            dep=out/(name+'.fallback.d')
            command+=['-I','scripts','-E','-M','-MF',str(dep),'-MT','fallback']
            raw=local.read_bytes();local.unlink()
            try:
                fallback=subprocess.run(command,cwd=N.ROOT,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
            finally:local.write_bytes(raw)
            N.require(fallback.returncode==0,'fallback mutation did not reach old source: '+fallback.stdout)
            N.require('scripts/'+name in dep.read_text(),'fallback source not consumed')
            try:verify_dependency(C.bind(N.ROOT/'scripts'/name),authority)
            except ValueError:pass
            else:raise ValueError('scripts fallback mutation survived')
        specimen=dict(rows[0]['dependencies'][0])
        for kind in ('sha','outside'):
            mutant=dict(specimen)
            mutant['sha256' if kind=='sha' else 'path']='0'*64 if kind=='sha' else 'unbound/input.h'
            try:verify_dependency(mutant,authority)
            except ValueError:pass
            else:raise ValueError('dependency mutation survived: '+kind)
        result.update(status='PASS: ALL CONSUMED INCLUDE DEPENDENCIES RESOLVED',
            missing_header_mutation='rejected by actual preprocessor',
            closure_authority=C.bind(N.ROOT/'config/c2-v220-public-native/include-closure.json'),
            identity_controls=['two scripts fallbacks rejected','wrong SHA rejected','outside projection rejected'],
            kernel_postlink_mutation='rejected; both compiler phases require derived sentinel',
            preprocessor_invocations=sum(r['mode']=='compiler-preprocessing-only' for r in rows)+3)
        save()
    except BaseException as error:
        result.update(status='HALT',error=str(error));save();raise
    return dict(status=result['status'],receipt=C.bind(receipt),translation_units=len(rows),
                preprocessor_invocations=result['preprocessor_invocations'],codegen_invocations=0)


if __name__=='__main__':
    print(json.dumps(check(),indent=2))
