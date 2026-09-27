"""Seal the bounded batch-query host proof and space/copy-cost halt."""
import argparse
import gzip
import hashlib
from pathlib import Path
import shutil
import subprocess
import set_b_producer as P
import set_b_fifth_seed_20260926 as S
import set_b_load_preflight_seal_20260926 as PREVIOUS
from set_b_fourth_halt_seal_20260926 import local_import_closure

ROOT = P.ROOT
ARCH = ROOT/'tests/bytecode/dialect-v2/evidence/architecture-blocks'
STEM = 'set-b-library-load-batch-20260926'
SEAL = ARCH/(STEM+'.json')
REPORT = ROOT/'docs/planning/set-b-library-load-batch-report.md'
CLOSURE = ROOT/'build/set-b-load-batch-close-r1/receipt.json'


def create():
    assert not SEAL.exists() and not (ARCH/STEM).exists()
    PREVIOUS.check()
    authority = S.require_auth()
    closure = P.load(CLOSURE)
    assert closure['status'] == 'HALT: BATCH QUERY EXCEEDS OBJECT AIR AND UNCHANGED-READER COPY COST'
    assert closure['copy_instruction_floor'] == 349751
    assert closure['air']['shortfall_to_floor'] == 69
    selected = set()
    for root in sorted((ROOT/'build').glob('set-b-load-batch-*')):
        selected.update(p for p in ([root] if root.is_file() else root.rglob('*')) if p.is_file())

    def add_bindings(value):
        if isinstance(value, dict):
            if {'path','bytes','sha256'} <= value.keys():
                bound = {k:value[k] for k in ('path','bytes','sha256')}
                path = ROOT/bound['path']
                assert P.bind(path) == bound, bound['path']
                selected.add(path)
            else:
                for item in value.values():
                    add_bindings(item)
        elif isinstance(value, list):
            for item in value:
                add_bindings(item)

    for path in sorted(selected):
        if path.name in ('receipt.json','binding.json','commands.json','stack-objects.json'):
            add_bindings(P.load(path))
    for row in closure['reused_receipts']:
        add_bindings(P.load(ROOT/row['path']))
    for row in P.load(ROOT/'build/set-b-load-batch-native-r1/commands.json'):
        assert row['exit'] == row['dependencies']['exit'] == 0
    selected.update(ROOT/p for p in S.authority_files())
    selected.update(local_import_closure(sorted((ROOT/'tools/host-lisp').glob('set_b_load_batch*_20260926.py'))))
    selected.update([
        REPORT, PREVIOUS.SEAL, PREVIOUS.REPORT,
        ROOT/'src/optional/c2_map_cpu_read.s',ROOT/'src/c2_product_runtime.c',
        ROOT/'config/set-b-native/linker/c2-substitution.ld',
        ROOT/'build/set-b-seed-medium-r6/media-seed/set-b-comfort.d81',
        ROOT/'build/set-b-seed-medium-r6/base/init.l65',
        ROOT/'build/input-cost-attribution-r6/xemu/xemu/cpu65.c',
    ])
    scope = ARCH/STEM/'owner-scope.txt'
    scope.parent.mkdir(parents=True)
    scope.write_text('Owner word: Dann bitte gemäß deiner Empfehlung fortfahren. '
        'Continue bounded native batch-read host cost/air/lifetime proof from d8719dc4; '
        'zero product builds/links/Seeds/device. No sixth Seed.\n\n' +
        subprocess.check_output(['git','show','d8719dc4:docs/planning/set-b-library-load-preflight-report.md'],cwd=ROOT,text=True))
    inputs,copies=[],[]
    for path in sorted(selected):
        bound=P.bind(path);inputs.append(bound)
        if not path.is_relative_to(ROOT/'build'):
            continue
        raw=path.read_bytes();compressed=len(raw)>131072
        dest=ARCH/STEM/path.relative_to(ROOT)
        if compressed:
            dest=dest.with_name(dest.name+'.gz')
        dest.parent.mkdir(parents=True,exist_ok=True);assert not dest.exists()
        dest.write_bytes(gzip.compress(raw,compresslevel=9,mtime=0) if compressed else raw)
        copies.append(dict(source=bound,copy=P.bind(dest),encoding='gzip' if compressed else 'identity'))
    toolchain=[P.bind(ROOT/'tools/llvm-mos/bin'/n) for n in ('mos-mega65-clang','llvm-objdump','llvm-readobj')]
    external=[PREVIOUS.external_binding(Path(shutil.which(n))) for n in ('cc','python3')]
    P.write(SEAL,dict(status=closure['status'],source_authority=authority,execution_head='d8719dc4',
        owner_scope=P.bind(scope),report=P.bind(REPORT),closure=P.bind(CLOSURE),
        predecessor_seal=P.bind(PREVIOUS.SEAL),accepted_world='Card L Final',public_release='2.4.0',
        consumed=closure['consumed'],authorized_ceiling=dict(seeds=5,finals=1,product_links=5),
        further_seed_or_product_link_authorized=False,this_commission=closure['this_commission'],
        inputs=inputs,receipt_copies=copies,toolchain=toolchain,external_toolchain=external,
        limits='Actual helper host proof and existing ELF copy-loop floor; non-LTO space/frame projection. '
               'No new target timing, linked-stack, consumer or full-source qualification.'))
    print('SEALED',len(inputs),'inputs;',len(copies),'lossless archive copies')


def check():
    seal=P.load(SEAL)
    for row in seal['inputs']+seal['toolchain']+[seal['owner_scope']]:
        assert P.bind(ROOT/row['path'])==row,row['path']
    for row in seal['external_toolchain']:
        assert PREVIOUS.external_binding(Path(row['path']))==row,row['path']
    for row in seal['receipt_copies']:
        path=ROOT/row['copy']['path'];assert P.bind(path)==row['copy']
        raw=path.read_bytes()
        if row['encoding']=='gzip':
            raw=gzip.decompress(raw)
        assert len(raw)==row['source']['bytes']
        assert hashlib.sha256(raw).hexdigest()==row['source']['sha256']
    S.require_auth()
    print('PASS batch seal: immutable authority, bound proof identities and lossless copies')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=('create','check'))
    create() if parser.parse_args().mode=='create' else check()
