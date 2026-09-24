"""Seal executed first-Seed facts without claiming Final qualification."""
from pathlib import Path
import hashlib
import json
import r3_product_block as BOOT

ROOT = Path(__file__).resolve().parents[2]
TARGET = ROOT/'tests/bytecode/dialect-v2/evidence/architecture-blocks/definition-set-a-seed.json'


def bind(p):
    p = p.resolve()
    data = p.read_bytes()
    return dict(path=str(p.relative_to(ROOT)), bytes=len(data),
                sha256=hashlib.sha256(data).hexdigest())


def main():
    assert not TARGET.exists(), 'preserve sealed Seed checkpoints'
    roots = [
        'build/definition-set-a-product-r1/seed-invocation.json',
        'build/definition-set-a-product-r1/wplto/definition-set-a-seed-price.json',
        'build/definition-set-a-product-r2-preflight/command-ready.json',
        'build/definition-set-a-seed-medium-r1/packed-receipt.json',
        'build/definition-set-a-r2/final-five-library-pack-receipt.json',
        'build/definition-set-a-r2/currency-proof.json',
        'build/definition-set-a-native-group-r1/receipt.json',
        'build/definition-set-a-order-r1/receipt.json',
        'build/definition-set-a-ledger-5-r2/receipt.json',
        'build/definition-ledger-full-5-r2/receipt.json',
        'build/definition-set-a-capacity-r3/receipt.json',
    ]
    paths = set(roots)
    # The package receipt deliberately records the medium before the final
    # boot-marker write. Reconstruct and verify that exact intermediate
    # identity instead of mislabelling it as the current delivered file.
    package_receipt = json.loads((ROOT/roots[4]).read_text())
    historical = package_receipt['medium_before_boot_stamp']
    current = ROOT/historical['path']
    construction = current.parent/'five-libraries/locator-construction.d81'
    data = bytearray(current.read_bytes())
    at = ((40-1)*40)*256 + BOOT.PRODUCT_BOOT_MARKER_OFFSET
    assert data[at:at+len(BOOT.PRODUCT_BOOT_MARKER)] == BOOT.PRODUCT_BOOT_MARKER
    data[at:at+len(BOOT.PRODUCT_BOOT_MARKER)] = construction.read_bytes()[at:at+len(BOOT.PRODUCT_BOOT_MARKER)]
    assert hashlib.sha256(data).hexdigest() == historical['sha256']
    reconstructed = ROOT/'build/definition-set-a-r2/medium-before-boot-marker.bin'
    if reconstructed.exists():
        assert reconstructed.read_bytes() == data
    else:
        reconstructed.write_bytes(data)
    paths.update((str(reconstructed.relative_to(ROOT)), str(construction.relative_to(ROOT)),
                  str(Path(BOOT.__file__).resolve().relative_to(ROOT))))
    def consume(value):
        if isinstance(value, dict):
            if 'path' in value and 'sha256' in value:
                actual = bind(ROOT/value['path'])
                assert actual['sha256'] == value['sha256'], value['path']
                if 'bytes' in value:
                    assert actual['bytes'] == value['bytes'], value['path']
                paths.add(actual['path'])
            for key, item in value.items():
                if key == 'medium_before_boot_stamp':
                    assert item == historical
                    continue  # exact preimage was verified above
                consume(item)
        elif isinstance(value, list):
            for item in value:
                consume(item)
    values = {}
    for path in roots:
        value = json.loads((ROOT/path).read_text())
        values[path] = value
        consume(value)
    currency = values[roots[5]]
    assert currency['free'] == dict(symbols=248, names=5471, code=8365)
    assert currency['images'] == dict(used=11, capacity=64) and currency['gap_bytes'] == 0
    for path in roots[6:]:
        assert values[path]['status'] == 'PASS', path
    for path in (ROOT/'build/definition-set-a-capacity-r3').glob('*-objects.json'):
        paths.add(str(path.relative_to(ROOT)))
    tools = ('seed_price', 'seed_media', 'native_group', 'currency',
             'currency_proof', 'ledger', 'order', 'capacity_native', 'seed_seal')
    paths.update('tools/host-lisp/definition_set_a_'+name+'.py' for name in tools)
    paths.update((
        'build/index-crc-r1/seed-price.py',
        'build/init-echo-r1/library-media.py',
        'build/init-repair-r2/library-media.py',
        'build/library-delivery-r8/load-five.py',
        'build/minibuffer-round3/five-ide-currency.py',
        'build/definition-ledger-r1/full-r2.py',
        'build/definition-pricing-r1/order-witness.py',
        'docs/planning/definition-set-a-seed-report.md',
    ))
    price = values[roots[1]]['candidate']
    result = dict(status='FIRST SEED FACTS; QUALIFICATION IN PROGRESS',
        authority='c97a8e60', source='cb34ad32',
        budget=dict(seed=1, final=0, product_link=0, device_contact=0),
        ELF=price['ELF'], medium=values[roots[3]]['medium'],
        currency=currency['free'], images=currency['images'], gap_bytes=0,
        price=price, native_group='two groups: one image/18 entries each, accessors 42',
        ordinary_progn=[5,6,9], capacity='last group accepted; next OOM; foreign code identical; 9 then 42',
        boot_marker_preimage=dict(recorded=historical, reconstructed=bind(reconstructed)),
        timing=dict(whole_before=1263886293, whole_after=818182246,
                    append_before=626233239, append_after=63740024,
                    outside_append_increase=116789168, cycles_per_second=40500000),
        remaining=['injected abort/control', 'three prerequisite rows on this Seed',
                   'outside-Append attribution', 'both Lane readings', 'matched GC',
                   'full check-source', 'Final/link/medium qualification', 'device acceptance'],
        bindings=[bind(ROOT/p) for p in sorted(paths)])
    TARGET.write_text(json.dumps(result, indent=2)+'\n')
    print('SEALED', len(paths), 'bindings; first Seed only, no Final acceptance')


if __name__ == '__main__':
    main()
