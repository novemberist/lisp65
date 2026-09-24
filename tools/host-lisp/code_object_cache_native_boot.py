"""Qualified boot observer on the cache candidate, with no product rebuild."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
source=ROOT/'tools/host-lisp/boot_only_carrier_native_boot.py'
raw=source.read_text().replace('build/boot-only-carrier-native-boot-r1','build/code-object-cache-native-boot-r1').replace('build/boot-only-carrier-seed-medium-r1','build/code-object-cache-seed-medium-r1')
exec(compile(raw,str(source),'exec'),dict(__name__='__main__',__file__=__file__))
