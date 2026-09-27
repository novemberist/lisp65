#!/usr/bin/env python3
"""Read-only validation of the preparation routing manifest; never run check-host."""
import hashlib
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
CONFIG=ROOT/'config/c2-v250-check-host-successors-20260928.json'
ROUTES={
    'block-26-build-integrity-check':'c2_v250_card5_20260928.py check',
    'c2-media-builder-closure-enumeration-check':'c2_v250_media_census_20260928.py check',
    'v240-bundle-docs-check':'c2_v250_v240_bundle_era_20260928.py',
    'v250-bundle-docs-check':'c2_v250_bundle_docs_gate.py',
    'v250-public-authority-check':'c2_v250_public_product.py preflight',
}
def validate(text):
    import re
    for target,command in ROUTES.items():
        found=re.search(r'^'+re.escape(target)+r':[^\n]*\n((?:\t[^\n]*\n)+)',text,re.M)
        if not found or 'tools/host-lisp/'+command not in found[1]:raise ValueError('route drift: '+target)
def check():
    config=json.loads(CONFIG.read_text())
    for p,sha in config['predecessors'].items():
        if hashlib.sha256((ROOT/p).read_bytes()).hexdigest()!=sha:raise ValueError('predecessor drift: '+p)
    for row in config['successors']:
        if not (ROOT/row['successor']).is_file():raise ValueError('successor absent')
    text=(ROOT/'mk/gates.mk').read_text();validate(text)
    for target,command in ROUTES.items():
        try:validate(text.replace(command,'withdrawn.py'))
        except ValueError:pass
        else:raise ValueError('route mutation survived: '+target)
    print('PASS: successor manifest; routing mutations='+str(len(ROUTES))+'; sealed check-host NOT RUN')
if __name__=='__main__':check()
