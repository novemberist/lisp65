#!/usr/bin/env python3
"""Renderer-only successor using the qualified buffered-repair producer stack."""
import hashlib
from pathlib import Path
import subprocess
import sys
import tempfile
import json

import f011_buffered_repair_product_card as F

ROOT = F.ROOT
PREDECESSOR = {n: getattr(F, n) for n in
               ('BUILD', 'PREFLIGHT', 'PLANE', 'ELF', 'PRG', 'PROFILE', 'PLANE_RECEIPT')}
ORIGINAL_CONFIGURE = F.configure
ORIGINAL_SOURCE_GATE = F.source_gate
BUILD = ROOT/'build/v2.1/renderer-branch-product-r1'
PREFLIGHT = ROOT/'build/v2.1/renderer-branch-product-r1-preflight'
AUTHORIZATION = 'bcd07a8d'
DIRECT = ('src/l65e_bcode_ordinal.s', 'src/optional/c2_map_cpu_read.s')


def failure_checks():
    from c2_no_pcrel16_gate import inspect
    elf = BUILD/'wplto/lisp65-c2-substitution-linked.prg.elf'
    core = ROOT/'build/v2.1/comfort-buffered-repair-device-r1/stack-repair-pricing-r1/gs4510-03b24c6b.vhdl'
    result = inspect(elf, core,
        'd44ae3906e1b0a826ca8e511c73ef1f50223b7de507a3ed349082fdefe58034e',
        elf.parent/'generated-product-sources/c2-stream-phase-02a.c',
        ROOT/'tools/llvm-mos/bin/llvm-readobj', ROOT/'tools/llvm-mos/bin/llvm-objdump')
    assert result['status'] == 'PASS', 'candidate still contains PCRel16 instructions'
    base = Path(tempfile.mkdtemp(prefix='failure-check-', dir=BUILD))
    (base/'no-pcrel16.json').write_text(json.dumps(result, indent=2)+'\n')
    subprocess.run([sys.executable, str(ROOT/'tools/host-lisp/c2_renderer_failure_gate.py'),
        '--elf', str(elf), '--readobj', str(ROOT/'tools/llvm-mos/bin/llvm-readobj'),
        '--medium', str(ROOT/'build/v2.1/f011-buffered-repair-r1/packed-prefilter/comfort/lisp65-v2.1-f011-comfort.d81'),
        '--xemu', str(ROOT/'build/dwx/xemu-buffered-repair-three-patch-r2/build/bin/xmega65.native'),
        '--rom', str(Path.home() / '.local/share/xemu-lgb/mega65/MEGA65.ROM'),
        '--sd-image', str(Path.home() / '.local/share/xemu-lgb/mega65/mega65.img'),
        '--out', str(base/'execution')], cwd=ROOT, check=True)
    (BUILD/'failure-checks.json').write_text(json.dumps({'status': 'PASS',
        'authority': authority(), 'elf': F.C.bind(elf),
        'classifier': F.C.bind(base/'no-pcrel16.json'),
        'execution': F.C.bind(base/'execution/receipt.json')}, indent=2)+'\n')


def authority():
    raw = subprocess.check_output(['git', 'show', AUTHORIZATION+':docs/planning/v2.0.0-pre-plan.md'], cwd=ROOT)
    header = '## BUDGET — renderer card:'.encode()
    assert raw.count(header) == 1
    section = raw.split(header, 1)[1].split(b'\n## ', 1)[0]
    assert b'one seed WPLTO, one final C/LTO call, one' in section
    assert b'No medium and no device contact' in section
    assert F.C.bind(PREDECESSOR['ELF'])['sha256'] == '9c9aa48493a63b7d479eae8f824e226e951c2f424b646a1d2c16bfc0be493637'
    return {'commit': AUTHORIZATION, 'section_sha256': hashlib.sha256(section).hexdigest(),
            'predecessor': {n: F.C.bind(PREDECESSOR[n]) for n in ('ELF', 'PRG')},
            'budget': {'seed_WPLTO': 1, 'final_C_LTO': 1, 'product_links': 1,
                       'medium_builds': 0, 'device_contacts': 0}}


def source_gate():
    result = ORIGINAL_SOURCE_GATE()
    result['renderer_repair'] = {'sources': [F.C.bind(ROOT/p) for p in DIRECT],
        'final_elf_proofs_pending': True,
        'no_other_product_changes': 'enforced by materialize_bound_profile'}
    return result


def configure():
    values = {
        'BUILD': BUILD, 'PREFLIGHT': PREFLIGHT,
        'PLANE': PREFLIGHT/'setup-owned/static-plane/narrow-static',
        'WPLTO': BUILD/'wplto',
        'ELF': BUILD/'wplto/lisp65-c2-substitution-linked.prg.elf',
        'PRG': BUILD/'wplto/lisp65-c2-substitution-linked.prg',
        'PROFILE': BUILD/'wplto/resolved-profile.txt',
        'BOUND_PROFILE': PREFLIGHT/'bound-feature-profile.txt',
        'INVOCATION': PREFLIGHT/'candidate-invocation.json',
        'AUTHORIZATION': AUTHORIZATION,
        'PLAN_HEADER': '## BUDGET — renderer card: one seed WPLTO, one final C/LTO call, one product link — 2026-09-06',
        'FORMAT': 'renderer-branch-product-r1',
        'STATUS': 'PENDING: RENDERER CANDIDATE FAILURE-PATH PROOFS',
        'DRIVER': Path(__file__).resolve(),
        'REPORT': ROOT/'docs/planning/v2.1-renderer-branch-product-report.md',
    }
    for name in ('PLANE_RECEIPT', 'PREFLIGHT_RECEIPT', 'SOURCE_PREFLIGHT',
                 'PRELINK_RED', 'DIFFERENCE', 'RECEIPT'):
        values[name] = PREFLIGHT/(name.lower().replace('_', '-')+'.json')
    PREFLIGHT.mkdir(parents=True, exist_ok=True)
    for name, value in values.items():
        setattr(F, name, value)
    F.OLD.update(PREDECESSOR)
    F.authority = authority
    F.source_gate = source_gate
    ORIGINAL_CONFIGURE()
    # The inherited configure selects its own two C sources. This successor
    # authorizes only the two assembly roots; profile comparison is exact.
    F.C.DIRECT = DIRECT
    F.C.B.DIRECT_CARD6_SOURCES = DIRECT


if __name__ == '__main__':
    if sys.argv[1:] == ['failure-checks']:
        failure_checks()
    else:
        if any(action in sys.argv[1:] for action in ('_scope', '_accept')):
            failure_checks()
        F.configure = configure
        F.main()
