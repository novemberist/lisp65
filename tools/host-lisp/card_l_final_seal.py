#!/usr/bin/env python3
"""Read-only Card L check; explicit seal promotes the prepared DRAFT once.

The prepared manifest and receipt copies freeze the review evidence before the
source run. `seal` adds the exact-HEAD source and Final bindings and becomes
immutable. Neither mode compiles, links, packs, or runs an emulator.
"""
import argparse
import json
import os
import sys
import card_l_final as F

sys.dont_write_bytecode = True
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'


def check(allow_pending=False):
    result = F.preflight(allow_pending, need_final=True)
    manifest = F.load(F.MANIFEST)
    for row in manifest['receipt_copies']:
        F.verify(row['copy'])
        F.require((F.ROOT/row['source']['path']).read_bytes() ==
                  (F.ROOT/row['copy']['path']).read_bytes(), 'receipt copy differs')
    for row in manifest.get('closing_inputs', []):
        F.verify(row)
    if manifest['status'] == 'DRAFT':
        result['pending'].append('immutable Final seal (draft evidence snapshot only)')
    else:
        F.require(manifest['status'] == 'PASS: CARD L FINAL', 'unknown seal status')
        F.require(manifest['source_head'] == F.git('rev-parse', 'HEAD'), 'seal HEAD mismatch')
    F.require(allow_pending or not result['pending'], 'pending bindings: ' + '; '.join(result['pending']))
    result['status'] = 'PENDING' if result['pending'] else 'PASS'
    result['receipt_copies'] = len(manifest['receipt_copies'])
    return result


def seal():
    value = F.load(F.MANIFEST)
    F.require(value['status'] == 'DRAFT', 'immutable seal already exists')
    F.preflight(need_final=True)
    # Validate all prepared copies without treating draft status as a failure.
    result = check(True)
    F.require(result['pending'] == ['immutable Final seal (draft evidence snapshot only)'], 'incomplete closure')
    closing = [F.SOURCE, str((F.OUT/'final-identity.json').relative_to(F.ROOT)),
               str((F.OUT/'final-invocation.json').relative_to(F.ROOT)),
               str((F.OUT/'final-command-consumption.json').relative_to(F.ROOT))]
    value['closing_inputs'] = [F.bind(path) for path in closing]
    for path in closing:
        dest = F.MANIFEST.parent/F.STEM/path
        dest.parent.mkdir(parents=True, exist_ok=True)
        with dest.open('xb') as stream:
            stream.write((F.ROOT/path).read_bytes())
        value['receipt_copies'].append(dict(source=F.bind(path), copy=F.bind(dest)))
    source = F.load(F.SOURCE)
    value.update(status='PASS: CARD L FINAL', source_head=source['head_before'],
                 source_seconds=source['seconds'], final=F.load(F.OUT/'final-identity.json'), pending=[])
    # Only the explicitly marked draft can be promoted; a sealed file is never overwritten.
    tmp = F.MANIFEST.with_suffix('.json.tmp')
    F.write_once(tmp, value)
    tmp.replace(F.MANIFEST)
    print('PASS: immutable Card L Final seal written')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['check', 'seal'])
    parser.add_argument('--allow-pending', action='store_true')
    args = parser.parse_args()
    if args.mode == 'check':
        print(json.dumps(check(args.allow_pending), indent=2))
    else:
        F.require(not args.allow_pending, 'seal cannot allow pending bindings')
        seal()


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, KeyError) as error:
        sys.exit('FAIL: ' + str(error))
