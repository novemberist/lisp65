#!/usr/bin/env python3
"""2.5.5 Seed producer CLI (successor of the 2.5.4 producer CLI).

Actions (all names/constants come from c255_config.py; the authority commit is pinned there as AUTHORITY_PIN
(the commit the green sealed check-source run build/card-255-check-source-r1 qualified); C255_AUTHORITY, if
exported, must be a prefix of the pin.  C255_DRY_WORKTREE=1 runs check-constants/selftest/preflight/e3/rehearse
against the working tree under 'dry-' run names; never a Seed):

  check-constants   read-only: frozen 2.5.4 baseline (Seed receipts r1b, link attempt r1, Final r1 and its seal),
                    recipe shape, pinned Fedora 45 host tools and the committed evidence that they reproduce the
                    baseline artifacts, authority and its qualifying sealed run, pins set, free run names
  selftest          host-only negative controls (write-once SELFTEST directory)
  preflight         host-only Chunk A (write-once PREFLIGHT directory): baseline replay,
                    authority emission, image classification, constants, capacity, reduced E3 sweep
  e3                exhaustive product-world E3 abort sweep (c255_e3_product.py: independent references, the
                    control must fail in both shapes) on the preflight's projected IDE world
                    (write-once E3 directory; host only, about 25 minutes).
                    rehearse and seed refuse without its PASS receipt.
  rehearse          everything the Seed does except the 75 frozen commands (write-once REHEARSAL
                    directory): full native input materialisation + include closure + command
                    preconditions, the immediate-shape prediction for the new constants, then
                    inventory/media/receipts with the 2.5.4 ELF as stand-in (the SHRUNK static plane
                    goes through the whole D81 transaction here, before the link).
                    Refuses any compile/link.  Run it between e3 and seed.
  seed              Chunk C: ONE attempt, ONE product link (write-once SEED directory)
  emit-final-constants
                    read-only: print the assignments that the Final pins module (c255_final_pins.py) needs
                    (Seed receipt/recipe/artifact hashes); writes nothing

Order is strict and the tool bytes AND the three pinned host tools must not change between steps:
  check-constants -> selftest -> preflight -> e3 -> rehearse -> (reviewer) -> seed.
selftest binds tool_identity() (c255_product.py + this file + c255_config.py + c255_e3_product.py +
c254_e3_product.py) and host_identity(); every later step re-verifies both.  Any edit therefore means a NEW
ATTEMPT tag in c255_config.py (all write-once names derive from it) and a fresh selftest/preflight.
"""
from __future__ import annotations
import argparse
import json
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import c255_config as CFG
import c255_product as P


def check_constants():
    result = CFG.check(stage='seed')
    result['authority'] = CFG.AUTHORITY or None
    result['authority_pin'] = CFG.AUTHORITY_PIN
    try:
        result['head'] = CFG.verify_authority()
        # D-5: the consumed source roots (git tree ids at the authority) that HEAD must carry unchanged.
        result['root_list'] = result['head']['root_trees']
    except (AssertionError, Exception) as error:
        result['problems'].append('authority: ' + str(error)); result['status'] = 'FAIL'
    try:
        result['host'] = P.host_identity()
        result['tools'] = P.tool_identity()
    except (AssertionError, Exception) as error:
        result['problems'].append('host / tools: ' + str(error)); result['status'] = 'FAIL'
    result['baseline'] = dict(seed=CFG.BASE, link_attempt=CFG.BASE_LINK, final=CFG.BASE_FINAL, preflight=CFG.BASE_PREFLIGHT,
                              base_authority=CFG.BASE_AUTHORITY, host_equivalence=[rel for rel, _sha in CFG.HOST_EQUIVALENCE.values()])
    result['expect_changed'], result['expect_exact'] = list(CFG.EXPECT_CHANGED), list(CFG.EXPECT_EXACT)
    result['closure_config'] = CFG.CLOSURE_CONFIG
    try:
        result['era'] = CFG.prime_era()
        covered = CFG.routed_lib()
        result['routes'] = dict(projections=CFG.PROJECTIONS, packages=CFG.PACKAGE_ROUTED_LIB, unrouted=CFG.UNROUTED_LIB)
        if covered != result['era']['changed_lib']:
            result['problems'].append('changed lib files not all routed: ' + repr(covered)); result['status'] = 'FAIL'
    except (AssertionError, Exception) as error:
        result['problems'].append('era: ' + str(error)); result['status'] = 'FAIL'
    return result


def emit_final_constants():
    """Print what must be copied into c255_final_pins.py before any Final tool is used."""
    seed = P.ROOT / CFG.SEED
    complete = json.loads((seed / 'complete.json').read_text())
    assert complete['status'] == 'PASS' and complete['product_links'] == 1
    rows = {'ELF': P.ROOT / complete['ELF']['path'], 'D81': P.ROOT / complete['medium']['path']}
    rows['PRG'] = seed / 'wplto/resident-island-seed.prg'
    rows['LTO'] = seed / 'wplto/resident-island-seed.prg.lto.o'
    lines = ['# c255_final_pins.py  [SET-AFTER-SEED] -- copy exactly, then commit with the replay',
             f"SEED_RECEIPT_SHA = '{CFG.sha256_file(seed / 'seed.json')}'",
             f"RECIPE_SHA = '{CFG.sha256_file(seed / 'native/command-proof.json')}'",
             'ARTIFACT_SHA = dict(' + ', '.join(f"{k}='{CFG.sha256_file(v)}'" for k, v in sorted(rows.items())) + ')']
    assert str(rows['D81'].relative_to(P.ROOT)) == f'{CFG.SEED}/{CFG.ARTIFACT_PATH["D81"]}', 'D81 path differs from ARTIFACT_PATH'
    return dict(status='PASS', assignments=lines)


def main():
    assert os.environ.get('PYTHONDONTWRITEBYTECODE') == '1'
    assert not sys.flags.optimize, 'assertions are mandatory'
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('action', choices=['check-constants', 'selftest', 'preflight', 'e3', 'rehearse', 'seed', 'emit-final-constants'])
    parser.add_argument('--output', type=Path,
                        help='explicit named successor for preflight/selftest rehearsal; never an in-place retry. '
                             'A rehearsal output can NOT satisfy seed (seed reads the configured names).')
    args = parser.parse_args()
    if args.action == 'check-constants':
        print(json.dumps(check_constants(), indent=2)); return
    if args.action == 'emit-final-constants':
        print(json.dumps(emit_final_constants(), indent=2)); return
    CFG.verify_authority()   # read-only git queries BEFORE the audit hook (guard) is installed
    CFG.prime_era()          # BASE host-source era cache + changed lib list, also before the hook
    assert args.action != 'seed' or args.output is None
    assert not (CFG.DRY and args.action == 'seed'), 'dry mode (C255_DRY_WORKTREE=1) never runs a Seed'
    P.host_identity()        # the pinned Fedora 45 host tools, before anything is written
    names = {'preflight': P.PREFLIGHT, 'selftest': P.SELFTEST, 'seed': P.BUILD, 'rehearse': P.ROOT / CFG.REHEARSAL,
             'e3': P.ROOT / CFG.E3}
    assert args.action != 'e3' or args.output is None
    root = args.output.resolve() if args.output else names[args.action]
    assert root.is_relative_to(P.ROOT / 'build') and root != P.ROOT / 'build'
    assert not any(root.is_relative_to(p) for p in (P.BASE, P.BASE_LINK, P.FROZEN_PLANE, P.FROZEN_NATIVE, P.FROZEN_MEDIA,
                                                    P.ROOT / CFG.BASE_FINAL, P.ROOT / CFG.BASE_PREFLIGHT))
    assert args.action == 'seed' or root.relative_to(P.ROOT / 'build').parts[0].startswith('card-255-')
    if args.action == 'seed':
        gate = CFG.check(stage='seed')
        assert gate['status'] == 'PASS', gate['problems']
    existed = root.exists()
    P.guard(root, host_only=args.action not in ('seed', 'rehearse'), rehearsal=args.action == 'rehearse')
    try:
        result = P.seed() if args.action == 'seed' else getattr(P, args.action)(root)
    except BaseException as error:
        if not existed and root.exists() and not (root / 'halt.json').exists():
            P.save(root / 'halt.json', dict(status='HALT', error=repr(error)))
        raise
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
