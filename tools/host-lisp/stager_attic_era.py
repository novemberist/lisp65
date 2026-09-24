"""Historical Attic attribution consumes the stager of its sealed era."""
import argparse
import json
from unittest.mock import patch
import c2_v21_attic_write_convergence_attribution as A
import evidence_era as E

COMMIT = '29839748'
STAGER = 'scripts/r3-cold-stager-main.c'

def verify():
    if E.host_source_commit() != COMMIT:
        raise ValueError('wrong Attic source era')
    A.check()

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('check', 'selftest'))
    parser.parse_args()
    with E.host_source_world(COMMIT, {STAGER}) as reads:
        verify()
    captured = dict(reads)
    assert STAGER in captured
    rejected = []
    for name, era in [('live-source', None), ('wrong-era', '0' * 40)]:
        token = E._host_source_commit.set(era)
        try:
            try: verify()
            except ValueError: rejected.append(name)
            else: raise AssertionError('era mutation survived')
        finally: E._host_source_commit.reset(token)
    original = E.era_blob
    def corrupt(commit, path):
        raw = original(commit, path)
        return raw + b'\n/* changed historical source */\n' if path == STAGER else raw
    with patch.object(E, 'era_blob', corrupt), E.host_source_world(COMMIT, {STAGER}):
        try: verify()
        except A.AttributionError: rejected.append('historical-source-changed')
        else: raise AssertionError('changed historical source accepted')
    assert len(rejected) == 3
    print(json.dumps(dict(status='PASS', era=COMMIT, reads=captured,
                          controls=rejected, receipt_rewritten=False, builds=0)))

if __name__ == '__main__': main()
