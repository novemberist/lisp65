#!/usr/bin/env python3
"""2.5.4 Final identity pins (set AFTER the Seed, BEFORE the replay is prepared).

Why this is NOT in c254_config.py: the Seed's selftest/preflight/Seed receipts bind
tool_identity() = sha256 of c254_product.py + c254_seed_producer.py + c254_config.py +
c254_e3_product.py (FOUR members since the product-world E3 gate, D-E3), and the
Final re-enters the unchanged producer (verify_preflight(), inventory(), media()), which
re-checks that identity.  Editing c254_config.py after the Seed (its [SET-AFTER-SEED] block)
would make every Final/replay/seal step fail closed with 'tool bytes changed since preflight'.
The c254_config.py placeholders SEED_RECEIPT_SHA/RECIPE_SHA/ARTIFACT_SHA/SEAL_SHA therefore stay
None forever, and `c254_seed_producer.py emit-final-constants` (whose header line still says
c254_config.py) is copied HERE instead.

This module has no side effects on import.  `check` and `emit` are read-only.

Usage:  python3 -B tools/host-lisp/c254_final_pins.py          check every pin against the Seed (exit 1 on a problem)
        python3 -B tools/host-lisp/c254_final_pins.py emit     print the assignments for every pin below,
                                                               computed from the finished Seed (writes nothing)
        python3 -B tools/host-lisp/c254_final_pins.py selfcheck  negative controls of the pins on the real Seed
"""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(ROOT / 'tools/host-lisp'))
import c254_config as CFG

# [SET-AFTER-SEED] from `c254_seed_continue_r1b.py emit` and SEED/attempt.json `tools`.
# A missing or malformed digest makes artifacts() raise, so c254_final / c254_replay / c254_seal /
# c254_final_rehearsal do not even import, and c254_emulator / c254_gc_stress refuse their world.
# Any edit here needs a NEW named replay (this file is a replay input).
# The two names are spelled out on purpose (cross-check against c254_config.SEED: a new attempt tag must be
# re-pinned here, never inherited).
#
# TWO directories since the reviewed halt of attempt r1 (build/card-254-seed-continue-r1b/notes.txt section D):
#   SEED_NAME       the Seed RECEIPTS: seed.json, complete.json, media.json, the medium, native/inventory.json,
#                   and byte-identical copies of the ELF / PRG / LTO object and the five native receipts
#   SEED_LINK_NAME  the LINK attempt = c254_config.SEED (cannot be edited): the 75 command logs, the claim,
#                   the compiled inputs; every path inside the native receipts names this directory; it keeps
#                   its halt.json for ever.
# HAZARD: SEED_LINK_NAME is a string prefix of SEED_NAME; never test a path with startswith(SEED_LINK_NAME).
SEED_NAME = 'build/card-254-product-r1b'
SEED_LINK_NAME = 'build/card-254-product-r1'
# Values from `c254_seed_continue_r1b.py emit` on the official continuation (2026-10-04).
SEED_RECEIPT_SHA = '8efe0ec4631994a65d3005e1889fce5bc806635277a60f4e546f1ac2388f3c6f'   # SEED/seed.json (== complete.json)
RECIPE_SHA = 'b037825d4ed307f7b8182a4998caeea41ff706c4860cac07cf921bbfc752125d'         # SEED/native/command-proof.json
ARTIFACT_SHA = dict(
    D81='250fdc763ae9e5b04cf149a6f2a7a3aa9fb293ff8da58e9a703e0c601efaef5d',   # SEED/media-254/c254.d81
    ELF='7b951eb9c92bc8797278903465b7483b3168a0eb935237a8f62ea3757f205244',   # SEED/wplto/resident-island-seed.prg.elf
    LTO='e9d6dc850e01dac45efb0dc1163ac3b463a5d26e00a49c3107380073da472afc',   # SEED/wplto/resident-island-seed.prg.lto.o
    PRG='192138eb70b4dc46a992e95651f52180a4e1687cd138b9347f8e3b77e37d70c4')   # SEED/wplto/resident-island-seed.prg
ARTIFACT_PATH = dict(CFG.ARTIFACT_PATH)
# The Seed tool identity that every Seed receipt binds; the Final refuses any other bytes.
# = SEED/attempt.json `tools` of the 2.5.4 Seed: FOUR members (c254_product.tool_identity()); `e3` is the
# product-world E3 harness c254_e3_product.py.  The key set must equal tool_identity()'s key set.
SEED_TOOL_SHA = dict(
    config='f1535d279981f852671874dae934bc34953a3d89e21434a65eb6b5feb5bed7e6',     # c254_config.py
    producer='b59526dbca0c9aa1ca141222d588087e2135a70d0bec70989b6e60bbb063fac7',   # c254_seed_producer.py
    product='2b093d166aafc18e05766435bda0f335517f77b38dd563a1df27eb4d290be7ed',    # c254_product.py
    e3='db8e4c47e301a70cde16b7b3c8bba056dae7bf11713e6c4e1094768f83d324a9')         # c254_e3_product.py
SEED_TOOL_KEYS = ('config', 'producer', 'product', 'e3')
# The FIFTH tool: the continuation that completed the halted attempt without a relink.  It is NOT a member
# of SEED_TOOL_SHA (tool_identity() and SEED/attempt.json `tools` stay four); it has its own pins.
SEED_CONTINUE_TOOL = 'c254_seed_continue_r1b.py'
SEED_CONTINUE_TOOL_SHA = '0233d9e8a972ae59a026874efec33681132f820aaf746361c20c42ac4cbc82e8'
SEED_CONTINUATION_SHA = '4e96c1634db1ae1837a96e82e4af998ed71c667978c12e91c0413deff835507d'   # SEED/continuation.json
# The halted link attempt (SEED_LINK_NAME): its four records, pinned.
R1_ATTEMPT_SHA = 'a08ddbdcfd658d5581a80a6742f4a026664e09f510a41cfa5e5bb1bf7b12e657'   # attempt.json
R1_CLAIM_SHA = '668fd5ccc692d8cd0eaec890d2beadfa22f84c0cbc726685a06f8352e13ea816'     # product-link-claim.json
R1_LINKED_SHA = '30c3d2b1f22189201a2b00114fb24327580778b179b3e77acc7a63f9da9dee89'    # linked.json
R1_HALT_SHA = '7b6b6b0108eb1d2c88affbe5f0f585c8ae1600b06088a6ca9d99ca69dc558dd2'      # halt.json
R1_RECORDS = (('attempt.json', 'R1_ATTEMPT_SHA'), ('product-link-claim.json', 'R1_CLAIM_SHA'),
              ('linked.json', 'R1_LINKED_SHA'), ('halt.json', 'R1_HALT_SHA'))
# The exhaustive product-world E3 receipt the Seed bound (SEED/attempt.json `e3`, SEED/source.json
# `e3.exhaustive`): sha256 of <c254_config.E3>/receipt.json.
E3_RECEIPT_SHA = '95ab0d26e9460c26994e06877bdb0f08aeef73ef2c5801d43132c8ef48f990a6'   # build/card-254-e3-r1/receipt.json
PIN_TOOL = 'c254_final_pins.py'


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def artifacts():
    """{role: (Seed-relative path, sha256)}; fails closed when a pin is missing or malformed."""
    values = [SEED_RECEIPT_SHA, RECIPE_SHA, E3_RECEIPT_SHA, *ARTIFACT_SHA.values(), *SEED_TOOL_SHA.values(),
              SEED_CONTINUE_TOOL_SHA, SEED_CONTINUATION_SHA, R1_ATTEMPT_SHA, R1_CLAIM_SHA, R1_LINKED_SHA, R1_HALT_SHA]
    if tuple(sorted(SEED_TOOL_SHA)) != tuple(sorted(SEED_TOOL_KEYS)):
        raise ValueError('Final pins name another Seed tool population')
    if not all(isinstance(v, str) and len(v) == 64 and set(v) <= set('0123456789abcdef') for v in values):
        raise ValueError('Final pins not set after Seed')
    if set(ARTIFACT_SHA) != set(ARTIFACT_PATH) or SEED_LINK_NAME != CFG.SEED or SEED_NAME != SEED_LINK_NAME + 'b':
        raise ValueError('Final pins name another Seed or artifact population')
    return {k: (ARTIFACT_PATH[k], ARTIFACT_SHA[k]) for k in sorted(ARTIFACT_PATH)}


def problems(root=ROOT):
    """Read-only: every pin against the real Seed bytes and the frozen Seed tool identity."""
    found = []
    try:
        rows = artifacts()
    except ValueError as error:
        return [str(error)]
    seed = Path(root) / SEED_NAME
    link = Path(root) / SEED_LINK_NAME
    for name in ('complete.json', 'seed.json', 'linked.json', 'attempt.json', 'continuation.json'):
        if not (seed / name).is_file():
            found.append('Seed receipt missing: ' + name)
    if (seed / 'halt.json').exists():
        found.append('Seed attempt carries halt.json')
    # The link attempt must be exactly the reviewed halted attempt: its four pinned records and no Seed receipt.
    for name, pin in R1_RECORDS:
        if not (link / name).is_file():
            found.append('link attempt record missing: ' + name)
        elif _sha(link / name) != globals()[pin]:
            found.append(pin + ' drift')
    for name in ('complete.json', 'seed.json'):
        if (link / name).exists():
            found.append('link attempt carries a Seed receipt: ' + name)
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
    if complete['ELF'] != dict(path=SEED_NAME + '/' + ARTIFACT_PATH['ELF'], bytes=(seed / ARTIFACT_PATH['ELF']).stat().st_size,
                               sha256=ARTIFACT_SHA['ELF']):
        found.append('Seed receipt names another ELF')
    if complete['medium'].get('path') != SEED_NAME + '/' + ARTIFACT_PATH['D81'] or complete['medium'].get('sha256') != ARTIFACT_SHA['D81']:
        found.append('Seed receipt names another medium')
    linked = json.loads((seed / 'linked.json').read_text())
    if linked.get('ELF', {}).get('sha256') != ARTIFACT_SHA['ELF'] or linked.get('product_links') != 1:
        found.append('linked.json names another ELF/link count')
    tools = dict(config=CFG.CONFIG_TOOL, producer=CFG.PRODUCER_TOOL, product=CFG.PRODUCT_TOOL, e3=CFG.E3_TOOL)
    for label in ('attempt.json',):
        for where in (SEED_NAME, CFG.PREFLIGHT, CFG.SELFTEST):
            bound = json.loads((Path(root) / where / label).read_text())['tools']
            if set(bound) != set(tools):
                found.append(f'{where}/{label} binds another tool population')
                continue
            for key, name in tools.items():
                if bound[key]['sha256'] != SEED_TOOL_SHA[key]:
                    found.append(f'{where}/{label} binds another {name}')
    for key, name in tools.items():
        if _sha(Path(root) / 'tools/host-lisp' / name) != SEED_TOOL_SHA[key]:
            found.append('Seed tool edited after the Seed (Final would fail closed): ' + name)
    found += continuation_problems(root)
    found += e3_problems(root)
    # The config placeholders must stay unset: a set value proves c254_config.py was edited.
    # (getattr: the 2.5.4 config may drop the placeholders altogether; present-and-set is the defect.)
    if any(getattr(CFG, n, None) for n in ('SEED_RECEIPT_SHA', 'RECIPE_SHA', 'SEAL_SHA')) or \
            any((getattr(CFG, 'ARTIFACT_SHA', None) or {}).values()):
        found.append('c254_config.py Final placeholders were filled in; they must stay None')
    return found


def continuation_problems(root=ROOT):
    """The continuation: the fifth tool, its record, what the Seed receipt says it continues, and the carried
    artifacts.  Messages name the tool KEY (never a Seed tool file name; see e3_problems)."""
    found = []
    seed, link = Path(root) / SEED_NAME, Path(root) / SEED_LINK_NAME
    if _sha(Path(root) / 'tools/host-lisp' / SEED_CONTINUE_TOOL) != SEED_CONTINUE_TOOL_SHA:
        found.append('continuation tool edited after the Seed')
    if _sha(seed / 'continuation.json') != SEED_CONTINUATION_SHA:
        found.append('SEED_CONTINUATION_SHA drift')
    record = json.loads((seed / 'continuation.json').read_text())
    if not (record.get('status') == 'PASS' and record.get('dry') is False and record.get('product_links_here') == 0 and
            record.get('product_compiles') == 0 and record.get('product_links_of_the_attempt') == 1 and
            record.get('tool', {}).get('sha256') == SEED_CONTINUE_TOOL_SHA):
        found.append('continuation.json is not the pinned official continuation')
    attempt = json.loads((seed / 'attempt.json').read_text())
    if not (attempt.get('status') == 'CONTINUATION' and attempt.get('continuation_tool', {}).get('sha256') == SEED_CONTINUE_TOOL_SHA and
            (attempt.get('continues') or {}).get('attempt') == SEED_LINK_NAME):
        found.append('Seed attempt.json is not the pinned continuation (key continues / continuation_tool)')
    link_tools = json.loads((link / 'attempt.json').read_text()).get('tools', {})
    if {k: v.get('sha256') for k, v in link_tools.items()} != SEED_TOOL_SHA:
        found.append('link attempt record binds another Seed tool identity (key tools)')
    told = json.loads((seed / 'complete.json').read_text()).get('continues') or {}
    want = dict(attempt=SEED_LINK_NAME, dry=False, product_links_here=0,
                halt=(SEED_LINK_NAME + '/halt.json', R1_HALT_SHA), linked=(SEED_LINK_NAME + '/linked.json', R1_LINKED_SHA),
                product_link_claim=(SEED_LINK_NAME + '/product-link-claim.json', R1_CLAIM_SHA),
                record=(SEED_NAME + '/continuation.json', SEED_CONTINUATION_SHA),
                tool=('tools/host-lisp/' + SEED_CONTINUE_TOOL, SEED_CONTINUE_TOOL_SHA))
    for key, value in want.items():
        got = told.get(key)
        if isinstance(value, tuple):
            got = (got.get('path'), got.get('sha256')) if isinstance(got, dict) else None
        if got != value or type(got) is not type(value):
            found.append('Seed receipt `continues` names another ' + key)
    linked = json.loads((seed / 'linked.json').read_text())
    if not (linked.get('status') == 'CARRIED' and linked.get('claim', {}).get('sha256') == R1_CLAIM_SHA and
            linked.get('linked_in', {}).get('sha256') == R1_LINKED_SHA):
        found.append('Seed linked.json is not the carried link of the pinned attempt')
    for role in ('ELF', 'PRG', 'LTO'):
        if not (link / ARTIFACT_PATH[role]).is_file() or _sha(link / ARTIFACT_PATH[role]) != ARTIFACT_SHA[role]:
            found.append('carried artifact differs from the link attempt: ' + role)
    if _sha(link / 'native/command-proof.json') != RECIPE_SHA:
        found.append('carried recipe differs from the link attempt')
    return found


def e3_problems(root=ROOT):
    """The exhaustive E3 receipt: the pinned bytes, PASS/exhaustive, swept with the pinned tools, and bound by
    the Seed.  Messages name the tool KEY, never the file name (c254_host_selftest.py section 7 counts the
    messages that name c254_config.py: three attempt records plus the live file)."""
    found = []
    e3 = Path(root) / CFG.E3
    if not (e3 / 'receipt.json').is_file() or not (e3 / 'attempt.json').is_file():
        return ['exhaustive E3 receipt or attempt record missing: ' + CFG.E3]
    if _sha(e3 / 'receipt.json') != E3_RECEIPT_SHA:
        found.append('E3_RECEIPT_SHA drift')
    receipt = json.loads((e3 / 'receipt.json').read_text())
    if receipt.get('status') != 'PASS' or receipt.get('mode') != 'exhaustive':
        found.append('E3 receipt is not a PASS exhaustive sweep')
    for label, bound in (('receipt.json', receipt.get('tools', {})),
                         ('attempt.json', json.loads((e3 / 'attempt.json').read_text()).get('tools', {}))):
        for key in SEED_TOOL_KEYS:
            if bound.get(key, {}).get('sha256') != SEED_TOOL_SHA[key]:
                found.append(f'{CFG.E3}/{label} was swept with another Seed tool ({key})')
    seed = Path(root) / SEED_NAME
    want = dict(path=CFG.E3 + '/receipt.json', sha256=E3_RECEIPT_SHA)
    attempt = json.loads((seed / 'attempt.json').read_text()).get('e3') or {}
    if {k: attempt.get(k) for k in want} != want:
        found.append('Seed attempt.json binds another E3 receipt')
    source = (json.loads((seed / 'source.json').read_text()).get('e3') or {}).get('exhaustive') or {}
    if {k: source.get(k) for k in want} != want:
        found.append('Seed source.json binds another E3 receipt')
    return found


def emit(root=ROOT):
    """Read-only: the assignments for every pin, computed from the finished Seed (receipts in SEED_NAME, link
    attempt in SEED_LINK_NAME).  The first nine lines equal `c254_seed_continue_r1b.py emit`.
    `c254_seed_producer.py emit-final-constants` cannot be used any more (it reads c254_config.SEED).
    Copy by hand, then run the check (no argument)."""
    seed, link = Path(root) / SEED_NAME, Path(root) / SEED_LINK_NAME
    complete = json.loads((seed / 'complete.json').read_text())
    assert complete['status'] == 'PASS' and complete['product_links'] == 1 and not (seed / 'halt.json').exists()
    assert (link / 'halt.json').is_file() and not (link / 'complete.json').exists(), 'link attempt is not the halted attempt'
    attempt = json.loads((seed / 'attempt.json').read_text())
    assert set(attempt['tools']) == set(SEED_TOOL_KEYS), 'Seed attempt binds another tool population'
    assert attempt['e3']['path'] == CFG.E3 + '/receipt.json' and \
        attempt['e3']['sha256'] == _sha(Path(root) / CFG.E3 / 'receipt.json'), 'Seed attempt binds another E3 receipt'
    lines = [f"SEED_NAME = '{SEED_NAME}'",
             f"SEED_LINK_NAME = '{SEED_LINK_NAME}'",
             f"SEED_RECEIPT_SHA = '{_sha(seed / 'seed.json')}'",
             f"RECIPE_SHA = '{_sha(seed / 'native/command-proof.json')}'",
             'ARTIFACT_SHA = dict(' + ', '.join(f"{k}='{_sha(seed / ARTIFACT_PATH[k])}'" for k in sorted(ARTIFACT_PATH)) + ')',
             'SEED_TOOL_SHA = dict(' + ', '.join(f"{k}='{attempt['tools'][k]['sha256']}'" for k in SEED_TOOL_KEYS) + ')',
             f"SEED_CONTINUE_TOOL_SHA = '{attempt['continuation_tool']['sha256']}'",
             f"SEED_CONTINUATION_SHA = '{_sha(seed / 'continuation.json')}'",
             f"E3_RECEIPT_SHA = '{attempt['e3']['sha256']}'"]
    lines += [f"{pin} = '{_sha(link / name)}'" for name, pin in R1_RECORDS]
    return dict(status='PASS', seed=SEED_NAME, link_attempt=SEED_LINK_NAME, assignments=lines)


def check(root=ROOT):
    found = problems(root)
    return dict(status='PASS' if not found else 'FAIL', problems=found, seed=SEED_NAME, link_attempt=SEED_LINK_NAME,
                final=CFG.FINAL,
                artifacts={k: dict(path=SEED_NAME + '/' + p, sha256=s) for k, (p, s) in artifacts().items()} if not found else {})


def selfcheck(root=ROOT):
    """Read-only negative controls of the pins on the REAL Seed.  The committed c254_host_selftest.py runs its
    Final section only when SEED_NAME == c254_config.SEED; with the continued Seed (r1b) it prints
    'skipped: no pinned Seed' and cannot be edited.  This is the replacement for the pin part of that section."""
    from unittest.mock import patch
    here = sys.modules[__name__]
    assert problems(root) == [], problems(root)
    log = []

    def expect(label, target, patched, needle):
        with patched:
            try:
                found = target()
            except ValueError as error:
                found = [str(error)]
        assert any(needle in x for x in found), (label, needle, found)
        log.append(label)
    zero = '0' * 64
    expect('wrong ELF pin', lambda: problems(root), patch.dict(ARTIFACT_SHA, ELF=zero), 'ARTIFACT_SHA drift: ELF')
    expect('wrong medium pin', lambda: problems(root), patch.dict(ARTIFACT_SHA, D81=zero), 'Seed receipt names another medium')
    expect('wrong Seed receipt pin', lambda: problems(root), patch.object(here, 'SEED_RECEIPT_SHA', zero), 'SEED_RECEIPT_SHA drift')
    expect('wrong recipe pin', lambda: problems(root), patch.object(here, 'RECIPE_SHA', zero), 'RECIPE_SHA drift')
    expect('wrong Seed tool pin', lambda: problems(root), patch.dict(SEED_TOOL_SHA, config=zero), 'binds another c254_config.py')
    expect('fifth member in the tool identity', artifacts, patch.dict(SEED_TOOL_SHA, continuation=zero), 'another Seed tool population')
    expect('wrong continuation tool pin', lambda: problems(root), patch.object(here, 'SEED_CONTINUE_TOOL_SHA', zero),
           'continuation tool edited')
    expect('wrong continuation record pin', lambda: problems(root), patch.object(here, 'SEED_CONTINUATION_SHA', zero),
           'SEED_CONTINUATION_SHA drift')
    for pin in ('R1_ATTEMPT_SHA', 'R1_CLAIM_SHA', 'R1_LINKED_SHA', 'R1_HALT_SHA'):
        expect('wrong ' + pin, lambda: problems(root), patch.object(here, pin, zero), pin + ' drift')
    expect('wrong E3 receipt pin', lambda: problems(root), patch.object(here, 'E3_RECEIPT_SHA', zero), 'E3_RECEIPT_SHA drift')
    expect('receipts taken from the link attempt', artifacts, patch.object(here, 'SEED_NAME', SEED_LINK_NAME), 'another Seed')
    expect('another link attempt', artifacts, patch.object(here, 'SEED_LINK_NAME', 'build/card-254-product-r0'), 'another Seed')
    expect('unset pin', artifacts, patch.object(here, 'RECIPE_SHA', None), 'not set after Seed')
    expect('config placeholder filled in', lambda: problems(root), patch.object(CFG, 'SEED_RECEIPT_SHA', zero, create=True), 'placeholders')
    assert problems(root) == []
    return dict(status='PASS', negative_controls=log)


if __name__ == '__main__':
    if sys.argv[1:] not in ([], ['emit'], ['selfcheck']):
        sys.exit('usage: c254_final_pins.py [emit | selfcheck]')
    result = dict(emit=emit, selfcheck=selfcheck).get((sys.argv[1:] or ['check'])[0], check)()
    print(json.dumps(result, indent=2))
    sys.exit(0 if result['status'] == 'PASS' else 1)
