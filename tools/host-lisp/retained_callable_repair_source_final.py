"""Retained-callable repair: seal a fresh exact-HEAD full check; on success immediately invoke one Final."""
import json
from pathlib import Path
import subprocess
import sys
from retained_callable_repair_r2_producer import ROOT, bind

OUT = ROOT / 'build/retained-callable-repair-check-source-r1'
ALIAS = ROOT / 'build/retained-callable-repair-source-qualification-r1/full-source-run.json'

def main():
    assert not subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT)
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    assert not ALIAS.exists()
    result = subprocess.run([sys.executable, '-B', 'tools/host-lisp/sealed_check_run.py',
        '--out', str(OUT), '--generated-tree', 'build/bytecode/dialect-v2',
        '--', 'make', '-k', 'check-source'], cwd=ROOT)
    if result.returncode:
        raise SystemExit(result.returncode)
    receipt = json.loads((OUT / 'receipt.json').read_text())
    assert receipt['target'] == 'make -k check-source'
    assert receipt['exit_code'] == receipt['changed_protected_files'] == 0
    assert not receipt['changed_files'] and not receipt['changed_sealed_artifacts']
    assert receipt['head_before'] == receipt['head_after'] == head
    assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip() == head
    assert not subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT)
    assert bind(ROOT / receipt['log']['path'])['sha256'] == receipt['log']['sha256']
    ALIAS.parent.mkdir(exist_ok=True)
    ALIAS.write_bytes((OUT / 'receipt.json').read_bytes())
    subprocess.run([sys.executable, '-B', 'tools/host-lisp/retained_callable_repair_final.py', 'final'], cwd=ROOT, check=True)

if __name__ == '__main__':
    main()
