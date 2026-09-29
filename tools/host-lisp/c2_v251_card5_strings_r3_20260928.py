"""Card-5 successor for sealed strings checker routes."""
import copy
import c2_v251_card5_strings_r2_20260928 as H
import strings_successor_r2_20260928 as S
RECEIPT='config/c2-v251-card5-receipt-strings-r3-20260928.json'
HISTORY={'tools/host-lisp/c2_v251_card5_strings_r2_20260928.py': '9d8be6d693b8a8460b09b4f68f2c12c742660c9e141a084f2cff13e8c8ff1ea7', 'config/c2-v251-card5-receipt-strings-r2-20260928.json': '4b883716fb011458371984c9e9ba4979f928b9430693a91ba5d7f3b1886b033d'}
REPLACEMENTS={'comfort_track_gate.py': 'comfort_track_strings_20260928.py', 'c2_v200_block3_hot_path_repair.py': 'c2_v200_block3_hot_path_repair_strings_20260928.py', 'stdlib_artifacts_strings_r2_20260928.py': 'stdlib_artifacts_strings_r3_20260928.py', 'c2_q_gate.py': 'c2_q_strings_20260928.py', 'comfort_default_option_a_20260927.py': 'comfort_default_option_a_strings_20260928.py', 'c2_v126_editor_allocation_ide_exit_20260928.py': 'c2_v126_editor_allocation_strings_20260928.py', 'c2_v251_card5_strings_r2_20260928.py': 'c2_v251_card5_strings_r3_20260928.py'}
RECEIPTS=['config/strings-stdlib-artifacts-receipt-r3-20260928.json','config/c2-q-receipt-strings-20260928.json','config/c2-require-resolver-receipt-strings-20260928.json','config/c2-v126-editor-allocation-receipt-strings-20260928.json']
K,V=H.H.K,H.H.V
K.ROUTES={target:REPLACEMENTS.get(tool,tool) for target,tool in K.ROUTES.items()}
V.CHECK_HOST_ROUTES=copy.deepcopy(V.CHECK_HOST_ROUTES)
for targets in V.CHECK_HOST_ROUTES.values():
    for target,commands in targets.items():
        for old,new in REPLACEMENTS.items():commands=[c.replace(old,new) for c in commands]
        targets[target]=commands

def derive():return dict(inherited=H.derive(),receipts=[S.bind(p) for p in RECEIPTS])
if __name__=='__main__':S.finish('c2-v251-card5-r3',derive,RECEIPT,HISTORY,(__file__,'Makefile','mk/gates.mk','tests/bytecode/stdlib/p0-stdlib-core-subset.json','tests/bytecode/libs/p0-v160-comfort-device-delta.json','tools/host-lisp/strings_scratch_20260928.py','tools/host-lisp/bytecode_p0_omissions_strings_20260928.py',*RECEIPTS,*('tools/host-lisp/'+p for p in REPLACEMENTS.values())))
