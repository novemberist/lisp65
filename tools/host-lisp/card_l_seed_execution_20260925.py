"""Run the committed Card L producer once, with the commissioned output path.

Only seed()'s output directory is rebound; all admission and command execution
remain the committed producer's code. Never retries a failed invocation.
"""
import inspect
import json
import os
from pathlib import Path
import sys
import traceback

sys.dont_write_bytecode = True
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
import card_l_producer as P


def main():
    out = P.HERE / 'execution-r2'
    invocation = out / 'seed-invocation.json'
    if invocation.exists():
        raise ValueError('Seed invocation already recorded; no retry')
    for path in ('link-preprobe/receipt.json', 'e000-preprobe/e000-low-edges-receipt.json',
                 'authority-admission.json'):
        assert P.load(out / path)['status'] == 'PASS', path
    capacity = P.load(out / 'capacity/slice-capacity-preflight-20260924.json')
    assert capacity['all_fit'] and capacity['directory']['growth_bytes'] == 256
    assert capacity['placements'][0]['requested_bytes'] == 597
    source = inspect.getsource(P.seed)
    old = "out=HERE/'seed'"
    assert source.count(old) == 1
    source = source.replace(old, "out=ROOT/'build/card-l-product-r1'", 1)
    (out / 'seed-function.py').write_text(source)
    P.write_once(invocation, dict(argv=sys.argv, authority=P.require_auth(),
        producer=P.bind(Path(P.__file__)), wrapper=P.bind(Path(__file__)),
        output='build/card-l-product-r1', seed_budget=1,
        transformation=dict(before=old, after="out=ROOT/'build/card-l-product-r1'")))
    namespace = dict(vars(P))
    exec(compile(source, str(out / 'seed-function.py'), 'exec'), namespace)
    try:
        namespace['seed']()
    except Exception as error:
        P.write_once(out / 'seed-result.json', dict(status='FAIL', error=str(error),
            traceback=traceback.format_exc(), retry=False))
        raise
    P.write_once(out / 'seed-result.json', dict(status='PASS', retry=False))


if __name__ == '__main__':
    main()
