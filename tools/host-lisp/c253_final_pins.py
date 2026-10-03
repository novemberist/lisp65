#!/usr/bin/env python3
"""2.5.3 Final identity pins (set AFTER the Seed, BEFORE the replay is prepared).

Why this is NOT in c253_config.py: the Seed's selftest/preflight/Seed receipts bind
tool_identity() = sha256 of c253_product.py + c253_seed_producer.py + c253_config.py, and the
Final re-enters the unchanged producer (verify_preflight(), inventory(), media()), which
re-checks that identity.  Editing c253_config.py after the Seed (its [SET-AFTER-SEED] block)
would make every Final/replay/seal step fail closed with 'tool bytes changed since preflight'.
The c253_config.py placeholders SEED_RECEIPT_SHA/RECIPE_SHA/ARTIFACT_SHA/SEAL_SHA therefore stay
None forever, and `c253_seed_producer.py emit-final-constants` (whose header line still says
c253_config.py) is copied HERE instead.

This module has no side effects on import.  `check` is read-only.
"""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(ROOT / 'tools/host-lisp'))
import c253_config as CFG

# [SET-AFTER-SEED] from `c253_seed_producer.py emit-final-constants`, Seed build/card-253-product-r8
# (PASS 2026-10-03: .text +340 B, changed eval_v2_workbench_service/main/repl).
# Any edit here needs a NEW named replay (this file is a replay input).
# r7 (Seed + Final r7 PASS, not shipped, owner decision 2026-10-02): seed.json f115777b..., recipe cb258f5c...,
# D81 abc9bb49..., ELF 47519653..., LTO e1f08f8e..., PRG c1f68a7f...; tools config 0b0d9507..., producer
# e9c9847a..., product 44a6b63f....
SEED_NAME = 'build/card-253-product-r8'
SEED_RECEIPT_SHA = '4aa1b35c972de40b18b88f8c4f86568d2414ed6393ffc1e601bba23c083b43c2'   # SEED/seed.json
RECIPE_SHA = '339523296f0a7a683b70adb07529ef449ff1f1b8bf012467aacfc22f4a37d8a4'         # SEED/native/command-proof.json
ARTIFACT_SHA = dict(
    D81='7df9db67f16c7218e56c9e4b64dfc0ed512c43771c9c39d9ccd56ddc76e55c2f',
    ELF='5eb056e03158578bb51edacbb9bd3064ea97a88b8d7613c1d0c052ae6a63d293',
    LTO='0491996a5d530545bb663dbb72712be484190e665addf0318d5de51b86f13c6b',
    PRG='6bf9dbd59b7ef3c4ef19eaa900f57606d313fbbc106475c1ede0102d3ada63ad')
ARTIFACT_PATH = dict(CFG.ARTIFACT_PATH)
# The Seed tool identity that every Seed receipt binds; the Final refuses any other bytes.
# = SEED/attempt.json tools of Seed r8 (b42aaade); the producer bytes are unchanged from r7.
SEED_TOOL_SHA = dict(
    config='15ce6f941b89bbc68ebbfff388f8f26be5882685981536e03c37a60ca6d89dbd',
    producer='e9c9847a22dba1e8f05d354c14bd2622eaefbe3a56d7bbcba6e83fc9069e75ae',
    product='6ca810cd5cdc44e5eecbbcad8e01ccbf9d18179adaead3445e8ba1eff01ba44f')
PIN_TOOL = 'c253_final_pins.py'


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def artifacts():
    """{role: (Seed-relative path, sha256)}; fails closed when a pin is missing or malformed."""
    values = [SEED_RECEIPT_SHA, RECIPE_SHA, *ARTIFACT_SHA.values(), *SEED_TOOL_SHA.values()]
    if not all(isinstance(v, str) and len(v) == 64 and set(v) <= set('0123456789abcdef') for v in values):
        raise ValueError('Final pins not set after Seed')
    if set(ARTIFACT_SHA) != set(ARTIFACT_PATH) or SEED_NAME != CFG.SEED:
        raise ValueError('Final pins name another Seed or artifact population')
    return {k: (ARTIFACT_PATH[k], ARTIFACT_SHA[k]) for k in sorted(ARTIFACT_PATH)}


def problems(root=ROOT):
    """Read-only: every pin against the real Seed bytes and the frozen Seed tool identity."""
    found = []
    try:
        rows = artifacts()
    except ValueError as error:
        return [str(error)]
    seed = Path(root) / CFG.SEED
    for name in ('complete.json', 'seed.json', 'linked.json'):
        if not (seed / name).is_file():
            found.append('Seed receipt missing: ' + name)
    if (seed / 'halt.json').exists():
        found.append('Seed attempt carries halt.json')
    if found:
        return found
    complete = json.loads((seed / 'complete.json').read_text())
    if not (complete['status'] == 'PASS' and complete['product_links'] == 1 and complete['seed'] == 1 and complete['final'] == 0):
        found.append('Seed complete.json is not a PASS Seed')
    if (seed / 'seed.json').read_bytes() != (seed / 'complete.json').read_bytes():
        found.append('seed.json and complete.json differ')
    if _sha(seed / 'seed.json') != SEED_RECEIPT_SHA:
        found.append('SEED_RECEIPT_SHA drift')
    if _sha(seed / 'native/command-proof.json') != RECIPE_SHA:
        found.append('RECIPE_SHA drift')
    for role, (suffix, digest) in rows.items():
        if _sha(seed / suffix) != digest:
            found.append('ARTIFACT_SHA drift: ' + role)
    if complete['ELF'] != dict(path=CFG.SEED + '/' + ARTIFACT_PATH['ELF'], bytes=(seed / ARTIFACT_PATH['ELF']).stat().st_size,
                               sha256=ARTIFACT_SHA['ELF']):
        found.append('Seed receipt names another ELF')
    if complete['medium'].get('path') != CFG.SEED + '/' + ARTIFACT_PATH['D81'] or complete['medium'].get('sha256') != ARTIFACT_SHA['D81']:
        found.append('Seed receipt names another medium')
    linked = json.loads((seed / 'linked.json').read_text())
    if linked.get('ELF', {}).get('sha256') != ARTIFACT_SHA['ELF'] or linked.get('product_links') != 1:
        found.append('linked.json names another ELF/link count')
    tools = dict(config=CFG.CONFIG_TOOL, producer=CFG.PRODUCER_TOOL, product=CFG.PRODUCT_TOOL)
    for label in ('attempt.json',):
        for where in (CFG.SEED, CFG.PREFLIGHT, CFG.SELFTEST):
            bound = json.loads((Path(root) / where / label).read_text())['tools']
            for key, name in tools.items():
                if bound[key]['sha256'] != SEED_TOOL_SHA[key]:
                    found.append(f'{where}/{label} binds another {name}')
    for key, name in tools.items():
        if _sha(Path(root) / 'tools/host-lisp' / name) != SEED_TOOL_SHA[key]:
            found.append('Seed tool edited after the Seed (Final would fail closed): ' + name)
    # The config placeholders must stay unset: a set value proves c253_config.py was edited.
    if CFG.SEED_RECEIPT_SHA or CFG.RECIPE_SHA or CFG.SEAL_SHA or any(CFG.ARTIFACT_SHA.values()):
        found.append('c253_config.py Final placeholders were filled in; they must stay None')
    return found


def check(root=ROOT):
    found = problems(root)
    return dict(status='PASS' if not found else 'FAIL', problems=found, seed=CFG.SEED, final=CFG.FINAL,
                artifacts={k: dict(path=CFG.SEED + '/' + p, sha256=s) for k, (p, s) in artifacts().items()} if not found else {})


if __name__ == '__main__':
    result = check()
    print(json.dumps(result, indent=2))
    sys.exit(0 if result['status'] == 'PASS' else 1)
