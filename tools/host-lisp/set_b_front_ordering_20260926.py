"""Read-only reconciliation of Set B's DMA ordering authority; no compiler calls."""
import argparse
import gzip
import hashlib
from pathlib import Path
import shutil
import subprocess

import set_b_producer as P
import set_b_fifth_seed_20260926 as S
import set_b_front_fence_seal_20260926 as PREVIOUS
from set_b_fourth_halt_seal_20260926 import local_import_closure
from set_b_load_preflight_seal_20260926 import external_binding

ROOT = P.ROOT
OUT = ROOT / 'build/set-b-front-ordering-r1'
ARCH = ROOT / 'tests/bytecode/dialect-v2/evidence/architecture-blocks'
STEM = 'set-b-front-ordering-20260926'
SEAL = ARCH / (STEM + '.json')
REPORT = ROOT / 'docs/planning/set-b-front-ordering-report.md'
HEAD = 'a7d4c41d'
AUTHORITIES = [
    'config/c2-cpu-chip-write-completion-contract.json',
    'config/c2-runtime-overlay-dma-completion-contract.json',
    'config/c2-f018b-content-safe-read-contract.json',
    'config/c2-v21-cpu-transport-release-contract.json',
    'docs/planning/c2.2-cpu-chip-write-completion-contract.md',
    'docs/planning/c2.2-cpu-chip-write-completion-granularity-review.md',
    'docs/planning/c2.2-runtime-overlay-dma-completion-contract.md',
    'docs/planning/c2.2-symbol-read-completion-investigation.md',
    'docs/planning/2.1-cpu-transport-work-plan.md',
    'tests/bytecode/dialect-v2/evidence/architecture-blocks/c2.2-link59-C1-Freezer-cutpoint4-late-chip-write-hardware-first-red.json',
    'tests/bytecode/dialect-v2/evidence/architecture-blocks/c2.3-v2.0-map-cpu-transport-probe-receipt.json',
    'tests/bytecode/dialect-v2/evidence/architecture-blocks/c2.3-v2.0-cpu-transport-reconciliation-receipt.json',
    'tests/bytecode/dialect-v2/evidence/architecture-blocks/c2.3-v2.0-cpu-transport-reconciliation-rebind-2026-08-25.json',
]


def audit():
    PREVIOUS.check()
    authority = S.require_auth()
    assert subprocess.check_output(['git', 'rev-parse', '--short=8', 'HEAD'], cwd=ROOT, text=True).strip() == HEAD
    OUT.mkdir(exist_ok=False)
    cp = ROOT / 'build/set-b-r1/step4-r6/closure-r1/compiler-inputs.json'
    closure = P.load(cp)
    roots = [r['after'] for r in closure['roots']] + closure['sources']
    assert closure['root_count'] == 74
    for row in roots:
        assert P.bind(ROOT / row['path']) == row
    candidate = P.load(ROOT / 'build/set-b-front-span-r1/binding.json')
    for row in candidate['candidate']:
        assert P.bind(ROOT / row['path']) == row

    contract = P.load(ROOT / AUTHORITIES[0])
    documented = P.load(ROOT / AUTHORITIES[1])['documented_semantics']
    pdf = ROOT / documented['chipset_reference']['path']
    assert P.bind(pdf)['sha256'] == documented['chipset_reference']['sha256']
    command = ['pdftotext', '-f', '84', '-l', '84', '-layout', str(pdf), '-']
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert 'processor stops trying to execute instructions until the DMA job has completed' in result.stdout
    (OUT / 'chipset-page84.txt').write_text(result.stdout)
    P.write(OUT / 'pdf-extraction.json', dict(command=command, exit=result.returncode,
        source=P.bind(pdf), result=P.bind(OUT / 'chipset-page84.txt'),
        tool=external_binding(Path(shutil.which('pdftotext')).resolve())))

    register = subprocess.check_output(['git', 'show', HEAD + ':docs/reference/parked-items-register.md'], cwd=ROOT, text=True)
    attic = [line for line in register.splitlines() if line.startswith('| **Attic runtime refill')]
    assert len(attic) == 1 and 'Upstream responded 2026-08-25' in attic[0]
    (OUT / 'prior-register-attic-row.txt').write_text(attic[0] + '\n')
    late = P.load(ROOT / AUTHORITIES[9])
    assert late['captures']['bank2']['changed_bytes'] == 5
    assert late['captures']['bank2']['range_before'] == '00 00 00 00 00 00 00 00 00'
    assert len(late['captures']['bank5']['Freezer_delta']['export_journal_offsets']) == 2
    assert late['captures']['bank5']['Freezer_delta']['C2J'] == 'ACTIVE and otherwise byte-identical'
    assert 'same ordered DMA engine' in contract['completion']['ordering_witness']
    assert 'late-write' in str(contract) or 'late_write' in str(contract)

    old = P.load(ROOT / 'build/set-b-front-fence-close-r2/receipt.json')
    assert old['passing_content_rows'] == 72 and old['replay_rows'] == 0
    attribution = P.load(ROOT / 'build/set-b-front-fence-close-r2/ordering-attribution.json')
    for row in attribution['sources']:
        assert P.bind(ROOT / row['path']) == row

    searches = []
    for pattern in ('CPU.stall|stops trying|ordering_witness|same ordered DMA',
                    'late.write|late_write|cutpoint4|partial|dropped',
                    'MAP|journal/rollback|existing transport|claim_limit'):
        command = ['rg', '-n', '-i', pattern] + AUTHORITIES
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
        assert result.returncode in (0, 1), result.stderr
        dest = OUT / ('search-' + str(len(searches) + 1) + '.txt')
        dest.write_text(result.stdout)
        searches.append(dict(command=command, exit=result.returncode, result=P.bind(dest)))
    P.write(OUT / 'search-ledger.json', dict(searches=searches,
        scope='13 named historical contracts, plans and receipts; source/active profile from prior sealed attribution. Not an exhaustive historical search.',
        upstream=dict(issue_url='https://github.com/MEGA65/mega65-user-guide/issues/670',
            direct_fetch='Web tool cache miss; comment text not independently retrieved.',
            search_url='https://github.com/MEGA65/mega65-user-guide/issues',
            search_observation='Official issue listing identifies Enhanced Attic convergence issue 670, opened July 31 2026. No comment-based guarantee inferred.',
            incorrect_initial_url='https://github.com/MEGA65/mega65-core/issues/670',
            local_comment_authority=P.bind(OUT / 'prior-register-attic-row.txt'))))
    P.write(OUT / 'authority-table.json', dict(sources=[P.bind(ROOT / p) for p in AUTHORITIES],
        active_sources=attribution['sources'], manual=P.bind(pdf), rows=[
            dict(id='intended-stall', verdict='DOCUMENTED INTENT', domain='Ordinary DMA and F018/F018B semantics',
                 finding='Manual page84/printed70 promises CPU execution resumes after completion. Under that ideal premise a later CPU read cannot overtake the write.'),
            dict(id='attic-l10', verdict='HISTORICAL OBSERVED VIOLATION', domain='Enhanced Attic-to-Bank0',
                 finding='Contract captures target convergence at691ms. Register records714ms repeat and upstream intended-semantics response; this audit did not retrieve that response.'),
            dict(id='chip-link59', verdict='RELEVANT HISTORICAL COUNTEREVIDENCE', domain='CPU-to-Bank2/Bank5 across Freezer cutpoint4',
                 finding='Nine-byte Bank2 span (five bytes change) and two export-journal bytes arrive late while ACTIVE journal is unchanged. Historical receipt, not a new hardware reproduction or current-world failure.'),
            dict(id='july-contract', verdict='BOUND SAME-ENGINE PREMISE', domain='CPU-to-Chip transaction data, journal and rollback',
                 finding=contract['completion']['ordering_witness']),
            dict(id='map-admission', verdict='READABILITY, NOT WRITE-DRAIN PROOF', domain='Bank5/Attic tested read spans; later product activation',
                 finding='Probe tests existing four-byte spans. CPU work plan retains journal/rollback walls and leaves writes unchanged; no override of late-write protection identified.'),
            dict(id='active-predicate', verdict='ORDERING GAP REMAINS', domain='Current span candidate, all74 roots unchanged',
                 finding='DMA writes; synchronous MAP/CPU journal read; old matching C2J alone does not establish unrelated transaction bytes. Prior synthetic row is still not a hardware reachability claim.')]))
    P.write(OUT / 'fault-domain.json', dict(rows=[
        dict(kind='ideal fully completed writes', status='Conditional correctness premise; documented intent, not sufficient acceptance evidence against historical violations.'),
        dict(kind='eventually delivered ordered writes with delayed visibility', status='Must remain covered: July contract explicitly requires draining late Bank2/Bank5 writes before publication or restoration.'),
        dict(kind='temporarily partial earlier write', status='An intermediate state of delayed visibility; cannot be silently excluded. Specific fixture timing remains synthetic.'),
        dict(kind='permanent loss/truncation or reordering despite successful trailing read', status='Not established by old journal witness. Neither coverage nor owner-approved exclusion found in the reviewed scope; needs explicit disposition before any broader claim.'),
        dict(kind='stale/partial/failed journal or header read', status='72 prior actual-C rows cover the stated host content failures only; no native timing claim.'),
        dict(kind='post-barrier corruption or source lifetime violation', status='Separate obligations; no new defect asserted or corruption experiment run.')],
        decision='Do not narrow the existing late-write requirement. No new fault-domain exclusion is authorized by this audit.'))
    P.write(OUT / 'receipt.json', dict(status='AUDIT COMPLETE; ORDERING HALT REMAINS',
        execution_head=HEAD, source_authority=authority, driver=P.bind(Path(__file__)),
        predecessor=P.bind(PREVIOUS.SEAL), compiler_authority=P.bind(cp), compiler_inputs=roots,
        candidate=candidate['candidate'], verified_compiler_roots=74,
        authority_table=P.bind(OUT / 'authority-table.json'), fault_domain=P.bind(OUT / 'fault-domain.json'),
        search_ledger=P.bind(OUT / 'search-ledger.json'), pdf_extraction=P.bind(OUT / 'pdf-extraction.json'),
        inherited_air=old['unchanged_air'], consumed=old['consumed'], authorized_ceiling=old['authorized_ceiling'],
        this_commission=dict(compiler_calls=0, dependency_calls=0, assembler_calls=0, host_c_runs=0,
            product_builds=0, product_links=0, seeds=0, finals=0, guest_runs=0, device_contacts=0),
        product_admitted=False, limits='Read-only documentary/source reconciliation. No RTL timing proof, host C rerun, current-world hardware reproduction or new product-defect claim. No guarantee found in the named scope that closes the active ordering bridge.'))
    print('AUDIT COMPLETE: intended stall found; relevant historical late Chip writes; ordering halt remains; 74 roots unchanged')


def seal():
    PREVIOUS.check()
    S.require_auth()
    assert not SEAL.exists() and not (ARCH / STEM).exists()
    receipt = P.load(OUT / 'receipt.json')
    selected = set(OUT.rglob('*'))
    selected = {p for p in selected if p.is_file()}
    selected.update(ROOT / p for p in AUTHORITIES)
    selected.update(local_import_closure([Path(__file__)]))
    selected.update([REPORT, PREVIOUS.SEAL, PREVIOUS.REPORT])
    external = [external_binding(Path(shutil.which('python3')).resolve()),
                external_binding(Path(shutil.which('pdftotext')).resolve()),
                external_binding(Path(shutil.which('rg')).resolve())]

    def bindings(value):
        if isinstance(value, dict):
            if {'path', 'bytes', 'sha256'} <= value.keys():
                row = {k: value[k] for k in ('path', 'bytes', 'sha256')}
                path = ROOT / row['path']
                if path.is_relative_to(ROOT):
                    assert P.bind(path) == row, row['path']
                    selected.add(path)
                else:
                    assert external_binding(path) == row
                    external.append(row)
            else:
                for item in value.values():
                    bindings(item)
        elif isinstance(value, list):
            for item in value:
                bindings(item)
    for path in sorted(OUT.glob('*.json')):
        bindings(P.load(path))
    scope = ARCH / STEM / 'owner-scope.txt'
    scope.parent.mkdir(parents=True)
    scope.write_text('Owner: Dann bitte gemäß deiner Empfehlung fortfahren. Continue a7d4c41d read-only transport-authority reconciliation. No product source changes, compiler calls, build/link/Seed/guest/device.\n\n' +
        subprocess.check_output(['git', 'show', HEAD + ':docs/planning/set-b-front-fence-report.md'], cwd=ROOT, text=True))
    inputs, copies = [], []
    for path in sorted(selected):
        bound = P.bind(path)
        inputs.append(bound)
        if not path.is_relative_to(ROOT / 'build'):
            continue
        raw = path.read_bytes()
        compressed = len(raw) > 131072
        dest = ARCH / STEM / path.relative_to(ROOT)
        if compressed:
            dest = dest.with_name(dest.name + '.gz')
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(gzip.compress(raw, compresslevel=9, mtime=0) if compressed else raw)
        copies.append(dict(source=bound, copy=P.bind(dest), encoding='gzip' if compressed else 'identity'))
    P.write(SEAL, dict(status=receipt['status'], execution_head=HEAD,
        owner_scope=P.bind(scope), report=P.bind(REPORT), closure=P.bind(OUT / 'receipt.json'),
        predecessor=P.bind(PREVIOUS.SEAL), inputs=inputs, receipt_copies=copies,
        external_tools=list({r['path']: r for r in external}.values()),
        this_commission=receipt['this_commission'], consumed=receipt['consumed'],
        authorized_ceiling=receipt['authorized_ceiling'], accepted_world='Card L Final',
        public_release='2.4.0', product_admitted=False))
    print('SEALED', len(inputs), 'inputs;', len(copies), 'lossless build copies')


def check():
    value = P.load(SEAL)
    for row in value['inputs'] + [value['owner_scope']]:
        assert P.bind(ROOT / row['path']) == row, row['path']
    for row in value['external_tools']:
        assert external_binding(Path(row['path'])) == row
    for row in value['receipt_copies']:
        path = ROOT / row['copy']['path']
        assert P.bind(path) == row['copy']
        raw = path.read_bytes()
        if row['encoding'] == 'gzip':
            raw = gzip.decompress(raw)
        assert len(raw) == row['source']['bytes']
        assert hashlib.sha256(raw).hexdigest() == row['source']['sha256']
    PREVIOUS.check()
    S.require_auth()
    print('PASS ordering seal: sources, 74 roots, authority, report and lossless receipts')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('audit', 'seal', 'check'))
    {'audit': audit, 'seal': seal, 'check': check}[parser.parse_args().mode]()
