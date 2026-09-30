"""Current r7 walker execution; archived source/probe receipts stay unchanged."""
import chain_walker_inventory as H
import disk_r7_consumers_20260930 as S
import chain_walker_exit_disk_r7_20260930 as X
RECEIPT = 'config/chain-walker-inventory-disk-r7-receipt-20260930.json'
PREVIOUS = 'tests/bytecode/dialect-v2/evidence/architecture-blocks/wave1-chain-walker-inventory-probe-receipt.json'
HISTORY = {'tools/host-lisp/chain_walker_inventory.py': 'becce9acd57368f4ca86d3b833b6f487cd674074a99c4871c0ecf64d50a75c7f', 'tests/bytecode/dialect-v2/evidence/architecture-blocks/wave1-chain-walker-inventory-probe-receipt.json': 'af32125e6fcbd7e0903ec75cf5860b49d6c33e9a1f9eddb229f64e6045883de7'}
def derive():
    S.S.history(HISTORY)
    controls = []
    execute = H.execute_exits
    def observed(*args, **kwargs):
        value = execute(*args, **kwargs)
        if kwargs.get('controls'): controls.append(value)
        return value
    with S.patch.object(H, 'c_exit', X.c_exit), S.patch.object(H, 'execute_exits', observed):
        H.selftest()
        walkers = H.verify()
    walkers['executed_exits']['claim'] = walkers['executed_exits']['claim'].replace(
        'debugger-supplied local budgets', 'host-injected local budgets at the original loop boundary')
    S.require(len(controls) == 1 and len(controls[0]['mutations']) == 29, 'walker mutation population drift')
    controls[0]['claim'] = walkers['executed_exits']['claim']
    return dict(walkers=walkers, executed_controls=controls[0], disk_r7=S.measure(), predecessor_probe=S.S.bind(PREVIOUS),
                budget_seam='Explicit exhausted-local assignment at original first loop; all exit/mutation controls retained')
if __name__ == '__main__':
    S.finish('chain-walker-inventory', derive, RECEIPT, None, (__file__, H.__file__, X.__file__, PREVIOUS))
