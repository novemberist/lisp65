"""Card-5 r6: r5 routes; the Seed producer is card tooling (bound by the card seal), not a Card-5 input."""
import copy
import c2_ide_exit_card5_r4_20260928 as H
import ide_exit_successor_20260928 as S
import backspace_successor_20260928 as B

H.H.H.H.K.ROUTES = dict(H.H.H.H.K.ROUTES, **{
    'block-26-build-integrity-check': 'c2_ide_exit_card5_r6_20260928.py'})
H.H.H.CHECK_HOST_ROUTES = copy.deepcopy(H.H.H.CHECK_HOST_ROUTES)
H.H.H.CHECK_HOST_ROUTES['mk/gates.mk'].update({
    'block-26-build-integrity-selftest': ['c2_ide_exit_card5_r6_20260928.py selftest'],
    'c2-v160-input-service-hybrid-capacity-world-attribution-selftest': ['c2_v160_hybrid_capacity_backspace_20260928.py selftest'],
    'c2-v160-input-service-hybrid-capacity-world-attribution-check': ['c2_v160_hybrid_capacity_backspace_20260928.py check'],
    'c2-v160-input-service-hybrid-selftest': ['c2_v160_hybrid_backspace_20260928.py selftest'],
    'c2-v160-input-service-hybrid-check': ['c2_v160_hybrid_backspace_20260928.py check'],
    'backspace-stdlib-artifacts-check': ['stdlib_artifacts_backspace_20260928.py check'],
})
RECEIPT = 'config/c2-ide-exit-card5-receipt-r6-backspace-20260928.json'
HISTORY = {'tools/host-lisp/c2_ide_exit_card5_r4_20260928.py': '978fe8997708819f162fad9fce1afea9f913b963b51a758b1b46e9a1b462533a', 'config/c2-ide-exit-card5-receipt-r4-20260928.json': 'dd1d3fb61de808a5cda14b384c1a0936c8ce1c4a635f3203f6032af6c263d3b0'}


def derive():
    # Preserve r4's efcf258f predecessor era independently of the new r4 chain.
    history = S.history(H.HISTORY)
    return dict(inherited=H.derive(), inherited_r4_history=history,
                stdlib_receipt=S.bind('config/backspace-stdlib-artifacts-receipt-20260928.json'))


if __name__ == '__main__':
    inputs=[__file__,H.__file__,S.__file__,
            'tools/host-lisp/c2_v160_hybrid_backspace_20260928.py',
            'config/c2-v160-hybrid-receipt-backspace-20260928.json',
            'tools/host-lisp/c2_v160_hybrid_capacity_backspace_20260928.py',
            'config/c2-v160-hybrid-capacity-receipt-backspace-20260928.json',
            'tools/host-lisp/stdlib_artifacts_backspace_20260928.py',
            'config/backspace-stdlib-artifacts-receipt-20260928.json',*H.RECEIPTS,
            'config/v2-string-codec-workloads-receipt-ide-exit-20260928.json',
            'config/dwx-freezer-free-boot-variants-receipt-ide-exit-20260928.json',
            'config/dwx-media-admission-gate-receipt-ide-exit-20260928.json']
    B.finish('card5-r6',derive,RECEIPT,HISTORY,inputs)
