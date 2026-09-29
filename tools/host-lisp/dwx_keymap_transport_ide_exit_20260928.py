"""Replay the qualified keymap era, then execute current C queue tuple proof.

The generated live header is host-only and never assigned the historical
Xemu binary's identity. No Xemu binary is executed or altered.
"""
import json
import tempfile
from pathlib import Path
import dwx_keymap_transport as K
import dwx_prefilter_blind_spot_contract as B
import evidence_era as E
import ide_exit_successor_20260928 as S


def derive():
    root = B.CYCLE_MANIFEST_PATH.parent
    manifest = json.loads(B.CYCLE_MANIFEST_PATH.read_bytes())
    with E.host_source_world(S.KEYMAP_ERA, (S.KEYMAP,)) as reads:
        old = K.generate_and_check(root, generate=False)
        S.require(old == manifest['keymap_transport'], 'historical queue proof drift')
    # Pin actual extracted queue writer bytes to the qualified manifest.
    source = root / 'targets/mega65/input_devices.c'
    S.require(K.hashlib.sha256(source.read_bytes()).hexdigest() ==
              manifest['patched_source_sha256']['targets/mega65/input_devices.c'],
              'queue writer escaped qualified source world')
    with tempfile.TemporaryDirectory(prefix='ide-exit-queue-') as temporary:
        host = Path(temporary)
        (host / K.HEADER).parent.mkdir(parents=True)
        (host / 'targets/mega65/input_devices.c').write_bytes(source.read_bytes())
        live = K.generate_and_check(host)
    S.require(set(map(tuple, live['events'])) - set(map(tuple, old['events'])) == {(113, 0)}
              and set(map(tuple, old['events'])) <= set(map(tuple, live['events'])),
              'IDE exit tuple delta differs from q addition')
    return dict(historical_transport=old, historical_reads=reads,
                live_host_transport=live, queue_writer=S.bind(source),
                historical_manifest=S.bind(B.CYCLE_MANIFEST_PATH),
                live_header_is_qualified_xemu=False)

RECEIPT = 'config/dwx-keymap-transport-receipt-ide-exit-20260928.json'
HISTORY = {'tools/host-lisp/dwx_keymap_transport.py': 'd13eaab53247891008f6d6e488e4204d0f95886a4f7332459e420027a2f5446d', 'config/dwx-prefilter-blind-spot-contract.json': '355e87ce51666db1a14dcbf3dcabdb1448329a7fd1d2429dffa194e118f94917'}


if __name__ == '__main__':
    S.finish('dwx-keymap-transport', derive, RECEIPT, HISTORY,
             (S.KEYMAP, __file__, S.__file__))
