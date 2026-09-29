"""Card-5 successor of the routed Strings Final release chain."""
import copy
import c2_v251_r2_20260929_card5 as H
import v2_string_codec_workloads_r251_20260929 as C

RECEIPT = 'config/c2-v251-check-host-r2-20260929-card5-receipt-r2.json'
HISTORY = {'tools/host-lisp/c2_v251_r2_20260929_card5.py': '3ae1d304d39ca94112951e1c70916fcb580f1e224ddc003701437c7d37486bc0', 'config/c2-v251-r2-20260929-card5-receipt.json': '6becca858418a5a713edb0b01f6248f48675ef701aeae6366eee3865317dd188'}
REPLACEMENTS = {
    'c2_v251_r2_20260929_card5.py': 'c2_v251_check_host_r2_20260929_card5.py',
    'v2_string_codec_workloads_ide_exit_20260928.py': 'v2_string_codec_workloads_r251_20260929.py',
}
K, V = H.K, H.V
K.ROUTES = {target: REPLACEMENTS.get(tool, tool) for target, tool in K.ROUTES.items()}
V.CHECK_HOST_ROUTES = copy.deepcopy(V.CHECK_HOST_ROUTES)
for targets in V.CHECK_HOST_ROUTES.values():
    for target, commands in targets.items():
        for old, new in REPLACEMENTS.items():
            commands = [command.replace(old, new) for command in commands]
        targets[target] = commands


def derive():
    return dict(date='2026-09-29', inherited=H.derive(),
                codec_receipt=C.S.bind(C.RECEIPT))


if __name__ == '__main__':
    C.finish('c2-v251-check-host-r2-card5', derive, RECEIPT, HISTORY,
             (__file__, C.__file__, 'Makefile', 'mk/gates.mk', 'mk/workbench.mk', C.RECEIPT))
