"""r7 Card-5 successor: complete inherited route and mutation chain."""
import copy
import c2_v251_card5_o2_lite_20260929 as H
import disk_r7_consumers_20260930 as S
# r2 successor: the first receipt bound the r7 producer before its r7b/r7c fixes.
RECEIPT = 'config/c2-v251-card5-disk-r7-receipt-r2-20260930.json'
HISTORY = {**H.HISTORY, **{'tools/host-lisp/c2_v251_card5_o2_lite_20260929.py': 'bbfd139b4ec67f4bb1d3edc0ebf68d700a634f4219fb298ba141769575fa6cab', 'config/c2-v251-card5-o2-lite-receipt-20260929.json': '26f041ec06ac4e00e304624beed965ba458e1d74f6b4e8410d702ec4320a12ae'}}
REPLACEMENTS = {'c2_v160_hybrid_strings_r2_20260928.py': 'c2_v160_hybrid_disk_r7_20260930.py', 'c2_v160_hybrid_capacity_strings_r2_20260928.py': 'c2_v160_hybrid_capacity_disk_r7_20260930.py', 'c2_v17_comfort_phase1b_o2_lite_20260929.py': 'c2_v17_comfort_phase1b_disk_r7_20260930.py', 'c2_v17_repl_idle_blink_o2_lite_20260929.py': 'c2_v17_repl_idle_blink_disk_r7_20260930.py', 'stdlib_artifacts_o2_lite_20260929.py': 'stdlib_artifacts_disk_r7_20260930.py', 'v11_function_metadata_ide_exit_20260928.py': 'v11_function_metadata_disk_r7_20260930.py', 'v2_string_codec_workloads_r251_20260929.py': 'v2_string_codec_workloads_disk_r7_20260930.py', 'c2_v251_card5_o2_lite_20260929.py': 'c2_v251_card5_disk_r7_20260930.py', 'chain_walker_inventory.py': 'chain_walker_inventory_disk_r7_20260930.py'}
RECEIPTS = ['config/c2-v160-hybrid-capacity-disk-r7-receipt-20260930.json', 'config/c2-v160-hybrid-disk-r7-receipt-20260930.json', 'config/c2-v17-comfort-phase1b-disk-r7-receipt-20260930.json', 'config/c2-v17-repl-idle-blink-disk-r7-receipt-20260930.json', 'config/chain-walker-inventory-disk-r7-receipt-20260930.json', 'config/disk-r7-consumers-receipt-20260930.json', 'config/stdlib-artifacts-disk-r7-receipt-20260930.json', 'config/v11-function-metadata-disk-r7-receipt-20260930.json', 'config/v2-string-codec-workloads-disk-r7-receipt-20260930.json']
RECEIPTS.append('config/dialect-v2-system-runtime-disk-r7-receipt-20260930.json')
RECEIPTS.append('config/disk-r7-consumer-mutations-receipt-20260930.json')
K, V = H.K, H.V
K.ROUTES = {target: REPLACEMENTS.get(tool, tool) for target,tool in K.ROUTES.items()}
V.CHECK_HOST_ROUTES = copy.deepcopy(V.CHECK_HOST_ROUTES)
for targets in V.CHECK_HOST_ROUTES.values():
    for target, commands in targets.items():
        for old,new in REPLACEMENTS.items(): commands=[c.replace(old,new) for c in commands]
        targets[target]=commands

def derive():
    S.S.history(HISTORY)
    return dict(inherited=H.derive(), receipts=[S.S.bind(p) for p in RECEIPTS], disk_source=S.S.bind(S.SOURCE),
                product_receipts='Deferred until Chunk C; no r7 media/plane PASS claimed')
if __name__ == '__main__':
    S.finish('card5', derive, RECEIPT, H, (__file__, 'Makefile', 'mk/gates.mk', 'mk/workbench.mk',
        'mk/workbench-service-inventory.mk', 'mk/disk-r7-consumers.mk', *RECEIPTS, *('tools/host-lisp/'+p for p in REPLACEMENTS.values()),
        'tools/host-lisp/v2_workbench_codemod_disk_r7_20260930.py', 'tools/host-lisp/disk_r7_directory_20260930.py', 'tools/host-lisp/disk_r7_consumer_mutations_20260930.py', 'tools/host-lisp/disk_r7_product_receipts_20260930.py', 'tools/host-lisp/chain_walker_exit_disk_r7_20260930.py', 'tools/host-lisp/dialect_v2_system_runtime_disk_r7_20260930.py', 'tools/host-lisp/dialect_v2_prelude_evidence_disk_r7_20260930.py', 'tools/host-lisp/c2_v251_card5_disk_r7_product_20260930.py'))
