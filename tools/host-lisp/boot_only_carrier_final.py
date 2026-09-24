"""One profile-bound Final/link over the accepted carrier Seed, never a Seed."""
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
H=ROOT/'build/boot-only-carrier-r1'
SEED='48f637a7d34fdbc8960cf58fd1c861df855fb8858fb6f746af1a9f489351b623'
OLD='05baccd657b7373100d74e2b41e36e46689dbd26f435294b173d979dbc353d67'


def generate():
    # Export only the configured constructor. The command-probe dispatch is
    # suppressed by the same capture seam used for Seed medium qualification.
    product=(ROOT/'build/ov-crc16-r1/product-card.py').read_text()
    product=product.replace('ov_crc16','boot_only_carrier')
    includes=(ROOT/'build/ov-crc16-r1/storage_final_includes.py').read_text()
    includes=includes.replace('final-command-includes-ov-crc16','final-command-includes-boot-only-carrier')
    includes=includes.replace('final-active-includes-ov-crc16','final-active-includes-boot-only-carrier')
    # Reuse the pre-existing final generator, changing only its bound world,
    # source authority, price receipt and predecessor identity.
    final=(ROOT/'build/ov-crc16-r1/final.py').read_text()
    final=final.replace('ov-crc16','boot-only-carrier').replace('0a41035d','4cd7eac3')
    final=final.replace('boot-only-carrier-first-seed-price.json','boot-only-carrier-seed-price.json')
    final=final.replace(OLD,SEED)
    final=final.replace('b10c08ba33a8691e8656317e0e7c52f6f9fa9985a1e67c2d437e984fbb577c2b',OLD)
    for name,raw in [('product-card.py',product),('storage_final_includes.py',includes),('final.py',final)]:
        target=H/name
        if target.exists():
            assert target.read_text()==raw, 'never overwrite a final adapter: '+name
        else: target.write_text(raw)


if __name__=='__main__':
    assert sys.argv[1:] in (['preflight'],['final'])
    generate()
    target=H/'final.py'
    exec(compile(target.read_text(),str(target),'exec'),dict(__name__='__main__',__file__=str(target)))
