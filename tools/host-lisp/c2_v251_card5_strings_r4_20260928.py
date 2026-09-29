"""Card-5 successor for environment-independent strings consumer receipts."""
import copy
import c2_v251_card5_strings_r3_20260928 as H
import strings_successor_r2_20260928 as S
RECEIPT='config/c2-v251-card5-receipt-strings-r4-20260928.json'
HISTORY={'tools/host-lisp/c2_v251_card5_strings_r3_20260928.py': '25e1720730bfea9b29ef9eca2929288dcb0a8d82eff7f7ac74b7b8a385d1039b', 'config/c2-v251-card5-receipt-strings-r3-20260928.json': '73100646510ad97e2484ab5ae3ca836ab4f4200c01ded669bb904d533801b344'}
REPLACEMENTS={'c2_q_strings_20260928.py': 'c2_q_strings_r2_20260928.py', 'comfort_default_option_a_strings_20260928.py': 'comfort_default_option_a_strings_r2_20260928.py', 'c2_v126_editor_allocation_strings_20260928.py': 'c2_v126_editor_allocation_strings_r2_20260928.py', 'c2_v251_card5_strings_r3_20260928.py': 'c2_v251_card5_strings_r4_20260928.py'}
RECEIPTS=['config/c2-q-receipt-strings-r2-20260928.json', 'config/c2-require-resolver-receipt-strings-r2-20260928.json', 'config/c2-v126-editor-allocation-receipt-strings-r2-20260928.json']
K,V=H.K,H.V
K.ROUTES={target:REPLACEMENTS.get(tool,tool) for target,tool in K.ROUTES.items()}
V.CHECK_HOST_ROUTES=copy.deepcopy(V.CHECK_HOST_ROUTES)
for targets in V.CHECK_HOST_ROUTES.values():
    for target,commands in targets.items():
        for old,new in REPLACEMENTS.items():commands=[c.replace(old,new) for c in commands]
        targets[target]=commands

def derive():return dict(inherited=H.derive(),receipts=[S.bind(p) for p in RECEIPTS])
if __name__=='__main__':S.finish('c2-v251-card5-r4',derive,RECEIPT,HISTORY,(__file__,'mk/gates.mk','tools/host-lisp/comfort_default_resolver_strings_r2_20260928.py',*RECEIPTS,*('tools/host-lisp/'+p for p in REPLACEMENTS.values())))
