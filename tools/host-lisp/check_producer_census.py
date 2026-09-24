"""Conservative, non-executing producer-call census of gate Python programs.

Every function is inspected, including record-only branches. A hit is a review
candidate, not proof that a check executes it. Local imported helpers are included;
dynamic dispatch and shell recipes are explicitly retained as review boundaries.
"""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / 'tools/host-lisp'
GATES = ROOT / 'mk/gates.mk'
PRODUCER = re.compile(r'(^|_)(build|compile|link|pack|publish|generate|materialize|record|write|derive)(_|$)')
PROCESS = {'run', 'Popen', 'check_call', 'check_output', 'system', 'execv', 'execve'}
WRITES = {'write_bytes', 'write_text', 'write', 'writelines', 'copy', 'copyfile', 'copytree', 'move', 'replace', 'unlink'}

def inspect(source):
    tree = ast.parse(source)
    hits = []
    def walk(node, owner='<module>', guards=()):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            owner = node.name
        if isinstance(node, ast.Call):
            name = ast.unparse(node.func)
            leaf = name.rsplit('.', 1)[-1]
            kind = ('producer-named-call' if PRODUCER.search(leaf) else
                    'process-dispatch' if leaf in PROCESS else
                    'write-or-copy' if leaf in WRITES else None)
            if kind:
                hits.append(dict(function=owner, line=node.lineno, call=name,
                                 kind=kind, guards=list(guards), expression=ast.unparse(node)[:400]))
        if isinstance(node, ast.If):
            walk(node.test, owner, guards)
            for child in node.body: walk(child, owner, guards + (ast.unparse(node.test),))
            for child in node.orelse: walk(child, owner, guards + ('not (' + ast.unparse(node.test) + ')',))
        else:
            for child in ast.iter_child_nodes(node): walk(child, owner, guards)
    walk(tree)
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import): imports.update(x.name.split('.')[0] for x in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module: imports.add(node.module.split('.')[0])
    return hits, imports

def derive():
    recipes = []
    targets = ''
    for number, line in enumerate(GATES.read_text().splitlines(), 1):
        if line and not line[0].isspace() and ':' in line:
            targets = line.split(':', 1)[0]
        if line.startswith('\t'):
            recipes.append(dict(targets=targets, line=number, command=line.strip(),
                                scripts=re.findall(r'tools/host-lisp/[\w.-]+\.py', line)))
    roots = sorted({s for row in recipes for s in row['scripts']})
    pending = list(roots)
    files = {}
    while pending:
        name = pending.pop()
        if name in files: continue
        path = ROOT / name
        if not path.is_file():
            files[name] = dict(missing=True)
            continue
        raw = path.read_bytes()
        hits, imports = inspect(raw.decode())
        helpers = sorted(str((TOOLS / (i + '.py')).relative_to(ROOT))
                         for i in imports if (TOOLS / (i + '.py')).is_file())
        files[name] = dict(sha256=hashlib.sha256(raw).hexdigest(), hits=hits, imports=helpers)
        pending.extend(helpers)
    return dict(format='gate-producer-census-v1', method='conservative AST; no gate execution',
                limits=['all branches included, including record-only',
                        'dynamic dispatch and shell commands require runtime/write-boundary checks'],
                recipes=recipes, direct_scripts=roots, files=files,
                producer_candidates=sorted(n for n,v in files.items()
                    if any(h['kind']=='producer-named-call' for h in v.get('hits', []))))

def selftest():
    cases = ["def check():\n    build_medium()\n",
             "def check():\n    MEDIA.compile_stager()\n",
             "def check():\n    subprocess.run(['cc'])\n",
             "def check():\n    RECEIPT.write_bytes(b'x')\n"]
    for source in cases:
        assert inspect(source)[0], 'census missed producer/write control'

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    selftest()
    value = derive()
    if args.output:
        args.output.write_text(json.dumps(value, indent=2) + '\n')
    print(json.dumps(dict(scripts=len(value['direct_scripts']),
                          with_helpers=len(value['files']),
                          candidates=len(value['producer_candidates']))))

if __name__ == '__main__': main()
