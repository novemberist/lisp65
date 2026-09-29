"""Next Card-5 on the routed phase1b walks chain; no Seed producer input."""
import copy
import c2_v251_card5_phase1b_walks_20260928 as H
import strings_successor_20260928 as S
RECEIPT='config/c2-v251-card5-receipt-strings-20260928.json'
HISTORY={'tools/host-lisp/c2_v251_card5_phase1b_walks_20260928.py': '115933fdd43c40d6acf977d145fba7439620e39910e57eb6a002835cca655829', 'config/c2-v251-card5-phase1b-receipt-walks-20260928.json': '08b4e60be6d3d5b8d86cb17f2663acd1c5c72ca5a1258ce92ad16d8e604f9053'}
REPLACEMENTS={'c2_v160_comfort_repl_walks_20260928.py': 'c2_v160_comfort_repl_strings_20260928.py', 'c2_v17_comfort_phase1b_walks_20260928.py': 'c2_v17_comfort_phase1b_strings_20260928.py', 'c2_v251_public_authority_walks_20260928.py': 'c2_v251_public_authority_strings_20260928.py', 'c2_v251_card5_phase1b_walks_20260928.py': 'c2_v251_card5_strings_20260928.py'}
K=H.H.H.K
V=H.H.H.V
K.ROUTES=dict(K.ROUTES,**{'block-26-build-integrity-check':'c2_v251_card5_strings_20260928.py'})
V.CHECK_HOST_ROUTES=copy.deepcopy(V.CHECK_HOST_ROUTES)
for targets in V.CHECK_HOST_ROUTES.values():
    for target,commands in targets.items():
        for old,new in REPLACEMENTS.items():commands=[c.replace(old,new) for c in commands]
        targets[target]=commands
V.CHECK_HOST_ROUTES['mk/gates.mk']['c2-v17-repl-idle-blink-card-check']=['c2_v17_repl_idle_blink_strings_20260928.py check']
V.CHECK_HOST_ROUTES['mk/gates.mk']['comfort-strings-artifacts-check']=['stdlib_artifacts_strings_20260928.py check']
RECEIPTS=['config/c2-v17-repl-idle-blink-receipt-strings-20260928.json','config/c2-v160-comfort-repl-receipt-strings-20260928.json',
          'config/c2-v17-comfort-phase1b-receipt-strings-20260928.json',
          'config/c2-v251-public-authority-receipt-strings-20260928.json',
          'config/strings-stdlib-artifacts-receipt-20260928.json']
def derive():
    value=H.derive()
    return dict(inherited=value,receipts=[S.bind(p) for p in RECEIPTS])
if __name__=='__main__':
    S.finish('c2-v251-card5',derive,RECEIPT,HISTORY,(__file__,H.__file__,'mk/gates.mk',*RECEIPTS,
        *('tools/host-lisp/'+p for p in REPLACEMENTS.values()),'tools/host-lisp/stdlib_artifacts_strings_20260928.py','tools/host-lisp/c2_v17_repl_idle_blink_strings_20260928.py'))
