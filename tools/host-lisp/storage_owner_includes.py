"""Active include closure for the storage producer, before native codegen.

The caller supplies the explicitly derived candidate input authority. Compiler
dependency output discovers consumption; it never creates that authority.
"""
import hashlib
import json
from pathlib import Path
import re
import shlex
import subprocess

ROOT = Path(__file__).resolve().parents[2]
CLOSURE = ROOT / 'config/c2-v230-public-native/include-closure.json'
CLOSURE_SHA = '088decb00891d9ce13eaa2555a696c59b316c9349d2bcb154f44a20cc35c8c8d'


def binding(path):
    path = path.resolve()
    raw = path.read_bytes()
    return dict(path=str(path.relative_to(ROOT)), bytes=len(raw),
                sha256=hashlib.sha256(raw).hexdigest())


def projection():
    if binding(CLOSURE)['sha256'] != CLOSURE_SHA:
        raise ValueError('public include authority drift')
    return json.loads(CLOSURE.read_text())


def materialize(directory):
    """The entire bound decoder population, not just the first missing header."""
    records = projection()['materialized']
    result = []
    for row in records:
        # The public producer owns the source/path spelling of these records.
        source = ROOT / row['source']['path']
        if binding(source) != row['source']:
            raise ValueError('decoder projection source drift: ' + str(source))
        target = directory / source.name
        if target.exists() and target.read_bytes() != source.read_bytes():
            raise ValueError('decoder conflicts with consumed predecessor: ' + target.name)
        target.write_bytes(source.read_bytes())
        result.append(dict(source=row['source'], consumed=binding(target)))
    return result


def verify(row, authority):
    expected = authority.get(row['path'])
    if expected is None:
        raise ValueError('include outside selected projection: ' + row['path'])
    if row != expected:
        raise ValueError('include SHA/size drift: ' + row['path'])


def check(commands, authority, output):
    """Run only preprocessing (-E -M), using the actual codegen arguments."""
    output.mkdir(parents=True, exist_ok=False)
    rows = []
    result = dict(status='STARTED', rows=rows, codegen_invocations=0,
                  authority=list(authority.values()), closure=binding(CLOSURE))
    receipt = output / 'receipt.json'
    def save():
        receipt.write_text(json.dumps(result, indent=2) + '\n')
    try:
        for ordinal, original in enumerate(commands):
            if '-c' not in original:
                continue
            command = list(original)
            source = Path(command[command.index('-c') + 1])
            directories = [ROOT] + [Path(command[i+1]).resolve()
                                    for i, x in enumerate(command) if x == '-I']
            if ROOT / 'scripts' in directories:
                raise ValueError('scripts fallback search path is forbidden')
            if source.suffix == '.s':
                pending = [source.resolve()]
                seen = set()
                dependencies = []
                while pending:
                    path = pending.pop()
                    if path in seen:
                        continue
                    seen.add(path)
                    row = binding(path)
                    verify(row, authority)
                    dependencies.append(row)
                    for name in re.findall(r'^\s*\.include\s+"([^"]+)"', path.read_text(), re.M):
                        found = next((p/name for p in directories if (p/name).is_file()), None)
                        if found is None:
                            raise ValueError('assembler include absent: ' + name)
                        pending.append(found.resolve())
                mode = 'assembler-include-resolution'
            else:
                at = command.index('-o')
                del command[at:at+2]
                command.remove('-c')
                dep = output / f'{ordinal:03d}.d'
                command += ['-E', '-M', '-MF', str(dep), '-MT', 'storage-include-gate']
                run = subprocess.run(command, cwd=ROOT, text=True, stdout=subprocess.PIPE,
                                     stderr=subprocess.STDOUT)
                (output / f'{ordinal:03d}.log').write_text(run.stdout)
                if run.returncode:
                    raise ValueError('preprocessing failed: ' + str(source) + '\n' + run.stdout)
                paths = shlex.split(dep.read_text().replace('\\\n', ' ').split(':', 1)[1])
                if not paths:
                    raise ValueError('empty dependency population')
                dependencies = [binding(Path(p)) for p in dict.fromkeys(paths)]
                for row in dependencies:
                    verify(row, authority)
                mode = 'compiler-preprocessing-only'
            rows.append(dict(source=str(source), mode=mode, dependencies=dependencies))
        if not rows:
            raise ValueError('no translation units checked')
        result.update(status='PASS: ACTIVE INCLUDE PATHS AND SHAS', translation_units=len(rows))
    except BaseException as error:
        result.update(status='HALT', error=str(error))
        raise
    finally:
        save()
    return binding(receipt)


def controls(commands, authority, output, generated):
    """Exercise the omitted-header form and successful-but-wrong fallbacks."""
    output.mkdir(parents=True, exist_ok=False)
    rejected = []
    for name, unit in [('c2-stream-v2-decoder.h', 'c2_hot_literal.c'),
                       ('c2-stream-decoder.h', 'c2_session_emitter.c')]:
        command = next(c for c in commands if '-c' in c and
                       Path(c[c.index('-c')+1]).name == unit)
        path = generated/name
        raw = path.read_bytes()
        try:
            path.unlink()
            try:
                check([command], authority, output/(name+'.missing'))
            except ValueError as error:
                if name not in str(error) or 'file not found' not in str(error):
                    raise
                rejected.append('missing:'+name)
            else:
                raise ValueError('missing decoder header survived: '+name)
            # The old fallback search path is itself forbidden, before even
            # preprocessing; additionally reject its identical-byte file by
            # resolved path, not just by digest.
            fallback = list(command)+['-I', str(ROOT/'scripts')]
            try:
                check([fallback], authority, output/(name+'.fallback'))
            except ValueError as error:
                if 'scripts fallback search path is forbidden' not in str(error):
                    raise
                rejected.append('forbidden-fallback:'+name)
            else:
                raise ValueError('scripts fallback survived')
            try:
                verify(binding(ROOT/'scripts'/name), authority)
            except ValueError:
                rejected.append('fallback-path:'+name)
            else:
                raise ValueError('same-byte fallback path survived')
        finally:
            path.write_bytes(raw)
    specimen = next(iter(authority.values()))
    for kind in ('sha', 'outside'):
        mutant = dict(specimen)
        mutant['sha256' if kind == 'sha' else 'path'] = '0'*64 if kind == 'sha' else 'unbound/input.h'
        try:
            verify(mutant, authority)
        except ValueError:
            rejected.append(kind)
        else:
            raise ValueError('include identity mutation survived: '+kind)
    receipt = output/'receipt.json'
    receipt.write_text(json.dumps(dict(status='PASS', rejected=rejected,
                                      codegen_invocations=0), indent=2)+'\n')
    return binding(receipt)
