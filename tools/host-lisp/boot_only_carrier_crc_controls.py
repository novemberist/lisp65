"""Native fail-closed extended-PRG controls; reuse the admitted stager binary.

Only diagnostic copies of the medium change. Descriptor and stager stay byte
identical. No packing producer, compiler, linker or hardware contact occurs.
"""
import argparse
import json
import os
from pathlib import Path

import dwx_retroactive_red_replay as D
import legacy_ide_delivery as MEDIA
from boot_only_carrier_native_boot import bind, OUT as OBSERVER, ROOT

OUT = ROOT/'build/boot-only-carrier-crc-controls-r1'


def main():
    pack = json.loads((ROOT/'build/boot-only-carrier-seed-medium-r1/packed-receipt.json').read_text())
    medium = ROOT/pack['medium']['path']
    assert D.sha256(medium) == pack['medium']['sha256']
    raw = medium.read_bytes()
    files = MEDIA.inventory(raw)
    extent = json.loads((ROOT/'build/boot-only-carrier-seed-medium-r1/extended-resident.json').read_text())
    extended_path = ROOT/extent['extended']['path']
    assert D.sha256(extended_path) == extent['extended']['sha256']
    extended = extended_path.read_bytes()
    names = [name for name, row in files.items() if row['data'] == extended]
    assert len(names) == 1
    name = names[0]
    prefix_path = ROOT/extent['prefix']['path']
    assert D.sha256(prefix_path) == extent['prefix']['sha256']
    prefix = prefix_path.read_bytes()
    assert extended.startswith(prefix)
    OUT.mkdir(exist_ok=True)
    assert not any(OUT.iterdir()), 'refuse evidence overwrite'
    # Same-size displacement cannot fail merely on length: CRC must protect it.
    changed = bytearray(extended); changed[-1] ^= 1
    cases = {'corrupt': bytes(changed), 'missing': prefix,
             'mispositioned': extended[:-678] + b'\0' + extended[-678:-1]}
    parent = D.ProbeMonitor

    class Monitor(parent):
        def wait_screen(self, required, timeout=20):
            return super().wait_screen(['DISK ERROR'], timeout=180)

    D.ProbeMonitor = Monitor
    args = argparse.Namespace(xemu=OBSERVER/'observer/build/bin/xmega65.native',
        rom=Path(str(Path.home() / '.local/share/xemu-lgb/mega65/MEGA65.ROM')),
        sd_image=Path(str(Path.home() / '.local/share/xemu-lgb/mega65/mega65.img')), timeout=240)
    rows = []
    for label, payload in cases.items():
        folder = OUT/label; folder.mkdir()
        diagnostic = folder/'diagnostic.d81'
        diagnostic.write_bytes(MEDIA.compose(raw, set(), {name: payload}))
        current = MEDIA.inventory(diagnostic.read_bytes())
        assert all(current[n] == row for n, row in files.items() if n != name)
        os.environ['LISP65_BOOT_LEDGER'] = str(folder/'boot.txt')
        os.environ['LISP65_CARRIER_WATCH'] = str(folder/'writes.txt')
        run = None
        try:
            run = D.start_run(label, diagnostic, folder, args)
            screen = run['monitor'].screen()
            assert 'DISK ERROR' in D.ROWS.decoded_framebuffer(screen)
            outputs = D.finish_run(run, screen); run = None
            trace = (folder/'boot.txt').read_text()
            boundaries = [int(line.split()[1]) for line in trace.splitlines() if line.startswith('E ')]
            assert boundaries and max(boundaries) < 4, 'product entered after rejected PRG'
            assert not (folder/'writes.txt').exists() or not (folder/'writes.txt').read_text()
            rows.append(dict(case=label, medium=bind(diagnostic), boundaries=boundaries,
                             outputs=outputs, product_entered=False, carrier_entered=False))
        finally:
            if run is not None:
                D.finish_run(run)
    result = dict(status='PASS', original_medium=pack['medium'],
                  binary=bind(args.xemu), cases=rows, product_builds=0,
                  stager_builds=0, media_links=0, device_contacts=0)
    (OUT/'receipt.json').write_text(json.dumps(result, indent=2)+'\n')
    print('PASS: native missing/corrupt/mispositioned carrier rejected before product entry')


if __name__ == '__main__':
    main()
