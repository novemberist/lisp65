#!/usr/bin/env python3
"""Check the frozen Comfort include authority without compiling live headers."""
import json
import c2_v251_public_native as N
def check():
    N.check()
    closure=json.loads((N.ROOT/'config/comfort-default-native/include-closure.json').read_text())
    for r in closure['rows']:
        N.bound(dict(path=r['successor'],sha256=r['sha256'],bytes=r['consumed']['bytes']))
    return dict(status='PASS: FROZEN COMFORT INCLUDE AUTHORITY',includes=len(closure['rows']),compiler_invocations=0,qualification='Authority only; full compiler-consumed closure needs public replay')
if __name__=='__main__':print(json.dumps(check(),indent=2))
