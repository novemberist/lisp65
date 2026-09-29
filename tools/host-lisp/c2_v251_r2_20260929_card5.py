"""Strings Final release preparation successor; preserve the full Card-5 chain."""
import copy
import c2_v251_card5_strings_r4_20260928 as H
import strings_successor_r2_20260928 as S
RECEIPT='config/c2-v251-r2-20260929-card5-receipt.json'
HISTORY={'tools/host-lisp/c2_v251_card5_strings_r4_20260928.py': '4b31d0b36fa19ef44bd947a39f4cbb6219cf469bf6b76db030e5d9c2fc9ffc13', 'config/c2-v251-card5-receipt-strings-r4-20260928.json': '91e66ec001ce8cf6789bbf37123da882f46329390f466bd6427f9bad7b99c515'}
REPLACEMENTS={'c2_v251_keymap.py': 'c2_v251_r2_20260929_keymap.py', 'c2_v251_public_naming.py': 'c2_v251_r2_20260929_public_naming.py', 'c2_v251_bundle_docs_gate.py': 'c2_v251_r2_20260929_bundle_docs_gate.py', 'c2_v251_v210_bundle_docs.py': 'c2_v251_r2_20260929_v210_bundle_docs.py', 'c2_v251_media_census.py': 'c2_v251_r2_20260929_media_census.py', 'c2_v251_reproduction_gate.py': 'c2_v251_r2_20260929_reproduction_gate.py', 'c2_v251_card5_strings_r4_20260928.py': 'c2_v251_r2_20260929_card5.py', 'c2_v251_keymap_receipt_strings_r2_20260928.py': 'c2_v251_r2_20260929_keymap_receipt.py', 'c2_v251_public_authority_strings_r2_20260928.py check': 'c2_v251_r2_20260929_public_product.py preflight'}
K,V=H.K,H.V
K.ROUTES={target:REPLACEMENTS.get(tool,tool) for target,tool in K.ROUTES.items()}
V.CHECK_HOST_ROUTES=copy.deepcopy(V.CHECK_HOST_ROUTES)
for targets in V.CHECK_HOST_ROUTES.values():
    for target,commands in targets.items():
        for old,new in REPLACEMENTS.items():commands=[c.replace(old,new) for c in commands]
        targets[target]=commands
RECEIPTS=['config/c2-v251-r2-20260929-reproductions.json', 'config/c2-v251-r2-20260929-media-census-receipt.json', 'config/c2-v251-r2-20260929-keymap-receipt.json', 'config/c2-v251-r2-20260929-bundle-docs.json', 'config/c2-v251-r2-20260929-public-naming-receipt.json', 'config/c2-v251-r2-20260929-v210-bundle-docs-receipt.json']
def derive():return dict(date="2026-09-29",product="Strings Final",inherited=H.derive(),release_receipts=[S.bind(p) for p in RECEIPTS],historical_backspace_receipts=[S.bind(p) for p in ['config/c2-v251-reproductions.json', 'config/c2-v251-media-census-receipt.json', 'config/c2-v251-keymap-receipt.json', 'config/c2-v251-bundle-docs.json', 'config/c2-v251-public-naming-receipt.json', 'config/c2-v251-v210-bundle-docs-receipt.json', 'config/c2-v251-card5-receipt.json']])
if __name__=='__main__':S.finish('c2-v251-strings-release-r2',derive,RECEIPT,HISTORY,(__file__,'mk/gates.mk','mk/workbench.mk',*RECEIPTS))
