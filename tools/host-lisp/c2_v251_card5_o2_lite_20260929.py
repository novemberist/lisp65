"""O2-lite Card-5 route successor with the complete inherited control chain."""
import copy
import c2_v251_check_host_r2_20260929_card5 as H
import o2_lite_consumers_20260929 as S
RECEIPT='config/c2-v251-card5-o2-lite-receipt-20260929.json'
HISTORY={'tools/host-lisp/c2_v251_check_host_r2_20260929_card5.py': '437bd0c845a9da5ca162c6a452df23c8b8786ec56c4cf6a1266708f51b56c375', 'config/c2-v251-check-host-r2-20260929-card5-receipt-r2.json': '4f82ee55687ee21bebbb4e97255862b527cf3ea15ea42912176a128796c762ea'}
# Retain every predecessor binding and its mutation controls.
HISTORY = {**H.HISTORY, **HISTORY}
INPUTS = [row['path'] for row in S.json.loads((S.ROOT / H.RECEIPT).read_bytes())['inputs']]
REPLACEMENTS={'c2_q_strings_r2_20260928.py': 'c2_q_o2_lite_20260929.py', 'comfort_default_resolver_strings_r2_20260928.py': 'comfort_default_resolver_o2_lite_20260929.py', 'c2_v126_editor_allocation_strings_r2_20260928.py': 'c2_v126_editor_allocation_o2_lite_20260929.py', 'c2_v17_comfort_phase1b_strings_r2_20260928.py': 'c2_v17_comfort_phase1b_o2_lite_20260929.py', 'stdlib_artifacts_strings_r3_20260928.py': 'stdlib_artifacts_o2_lite_20260929.py', 'c2_v251_r2_20260929_keymap_receipt.py': 'c2_v251_keymap_receipt_o2_lite_20260929.py', 'comfort_track_strings_20260928.py': 'comfort_track_o2_lite_20260929.py', 'bytecode_p0_omissions_strings_20260928.py': 'bytecode_p0_omissions_o2_lite_20260929.py', 'c2_m65_hw_gate.py': 'c2_m65_hw_o2_lite_20260929.py', 'comfort_default_option_a_strings_r2_20260928.py': 'comfort_default_option_a_o2_lite_20260929.py', 'c2_v251_check_host_r2_20260929_card5.py': 'c2_v251_card5_o2_lite_20260929.py'}
RECEIPTS=['config/c2-q-o2-lite-receipt-20260929.json', 'config/comfort-default-resolver-o2-lite-receipt-20260929.json', 'config/c2-v126-editor-allocation-o2-lite-receipt-20260929.json', 'config/c2-v17-comfort-phase1b-o2-lite-receipt-20260929.json', 'config/stdlib-artifacts-o2-lite-receipt-20260929.json', 'config/c2-v251-keymap-receipt-o2-lite-receipt-20260929.json']
REPLACEMENTS['c2_v160_comfort_repl_strings_r2_20260928.py']='c2_v160_comfort_repl_o2_lite_20260929.py'
RECEIPTS.append('config/c2-v160-comfort-repl-o2-lite-receipt-20260929.json')
REPLACEMENTS['c2_v17_repl_idle_blink_strings_r2_20260928.py']='c2_v17_repl_idle_blink_o2_lite_20260929.py'
RECEIPTS.append('config/c2-v17-repl-idle-blink-o2-lite-receipt-20260929.json')
K,V=H.K,H.V
K.ROUTES={target:REPLACEMENTS.get(tool,tool) for target,tool in K.ROUTES.items()}
V.CHECK_HOST_ROUTES=copy.deepcopy(V.CHECK_HOST_ROUTES)
for targets in V.CHECK_HOST_ROUTES.values():
    for target,commands in targets.items():
        for old,new in REPLACEMENTS.items():commands=[c.replace(old,new) for c in commands]
        targets[target]=commands

def derive():
    return dict(inherited=H.derive(),receipts=[S.S.bind(p) for p in RECEIPTS])
if __name__=='__main__':
    S.finish('card5',derive,RECEIPT,HISTORY,(__file__,*INPUTS,'Makefile','mk/gates.mk','mk/workbench.mk',*RECEIPTS,*('tools/host-lisp/'+p for p in REPLACEMENTS.values())))
