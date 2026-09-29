"""Inherit Card-6 descriptor and mutation proof, route DWX to its successor."""
from unittest.mock import patch
import block_26_small_hardening_card as H
import dwx_prefilter_blind_spot_contract_ide_exit_20260928 as D
import ide_exit_successor_20260928 as S


def derive():
    original = H.run
    def run(command, label):
        command = list(command)
        if len(command) == 3 and command[1] == 'tools/host-lisp/dwx_prefilter_blind_spot_contract.py':
            command[1] = 'tools/host-lisp/dwx_prefilter_blind_spot_contract_ide_exit_20260928.py'
            command[2] = command[2].removeprefix('--')
        return original(command, label)
    with patch.object(H, 'run', run):
        result = H.check(False)
    return dict(inherited=result, dwx_successor=S.bind(D.RECEIPT))

RECEIPT = 'config/block-26-small-hardening-card-receipt-ide-exit-20260928.json'
HISTORY = {'tools/host-lisp/block_26_small_hardening_card.py': 'f35cb361795b9983af95ba823e16ce69a6101dae4b108fc8f0d14c0a8f1aeecb', 'tests/bytecode/dialect-v2/evidence/architecture-blocks/block-2.6-card6-small-hardening-omission-prelink-receipt.json': '2effc96616e7528611ef0699128cd243d25e6d5ea2b07327c607ffa52a63d756'}


if __name__ == '__main__':
    S.finish('block-26-small-hardening', derive, RECEIPT, HISTORY,
             (S.KEYMAP, __file__, D.__file__, S.__file__))
