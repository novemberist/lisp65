"""Artifact-only Put-Kit medium; retain the accepted carrier extent adapter."""
import inspect
import sys
from pathlib import Path

import boot_only_carrier_seed_media as CARRIER
import dirty_anchor_producer as P
P.write_once = P.CACHE.PARENT.write_once


def producer():
    import builtins
    import types
    import dirty_anchor_producer as DRIVER
    captured = []
    def load_only(code, scope):
        assert scope['__name__'] == '__main__'
        scope['__name__'] = 'dirty_anchor_media_constructor'
        builtins.exec(code, scope)
        captured.append(scope)
    argv, original = sys.argv[:], DRIVER.builtins
    try:
        sys.argv = [str(Path(DRIVER.__file__)), 'command-probe']
        DRIVER.builtins = types.SimpleNamespace(exec=load_only, compile=builtins.compile)
        DRIVER.main()
    finally:
        DRIVER.builtins = original
        sys.argv = argv
    assert len(captured) == 1
    return captured[0]['g']


def configure():
    raw = (P.ROOT / 'tools/host-lisp/ov_crc16_seed_media.py').read_text()
    raw = raw[raw.index('from pathlib import Path'):]
    raw = raw.replace('ov_crc16', 'dirty_anchor').replace('ov-crc16', 'dirty-anchor')
    raw = raw.replace("HERE = ROOT/'build/dirty-anchor-r1'", "HERE = ROOT/'build/dirty-anchor-card-r1'")
    start, end = raw.index('def producer():'), raw.index('\ng = producer()')
    raw = raw[:start] + inspect.getsource(producer) + '\n' + raw[end:]
    target = P.HERE / 'seed-media-constructor.py'
    P.write_once(target, raw)
    CARRIER.TEMPLATE = target
    scope = CARRIER.configure()
    return scope


if __name__ == '__main__':
    if sys.argv[1:] not in (['configure-only'], ['materialize'], ['resume'], ['pack']):
        raise SystemExit('configure-only | materialize | resume | pack')
    scope = configure()
    if sys.argv[1:] == ['configure-only']:
        print('PASS: Put-Kit carrier media configured; no build/link/pack')
    elif sys.argv[1:] == ['pack']:
        scope['pack']()
    else:
        scope['setup']()
        getattr(scope['M'], sys.argv[1])()
