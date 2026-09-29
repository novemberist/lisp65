"""Strings allocation successor; inherit all allocation and screen oracles."""
import c2_v126_editor_allocation_ide_exit_20260928 as H
import strings_successor_r2_20260928 as S
from strings_scratch_20260928 import scratch, generated, normalized
RECEIPT='config/c2-v126-editor-allocation-receipt-strings-r2-20260928.json'
HISTORY={'tools/host-lisp/c2_v126_editor_allocation_ide_exit_20260928.py': '97a76d9a19f1c4b0c37f0f588ae58078c3c094630296b436088b53fd47b4c9b0', 'config/c2-v126-editor-allocation-receipt-ide-exit-20260928.json': '9fd9b058e12ec7ac188cf5cec1681f0633725e800f208a46155251fdeaaa50c8'}
HISTORY.update({'tools/host-lisp/c2_v126_editor_allocation_strings_20260928.py': 'a66c871d068065b0b9a15f5a9dae7961fb229cdfd1da3a6f787b365f86ea984e', 'config/c2-v126-editor-allocation-receipt-strings-20260928.json': 'c18095e8ce9770746a76c365a5c0ce34eae18ac2a0a4211613534d3ba2c0cc0e'})
from strings_generated_r11_20260929 import current_generated
def derive():
    with scratch() as root, current_generated(root):return normalized(H.derive(),root)
if __name__=='__main__':S.finish('c2-v126-editor-allocation',derive,RECEIPT,HISTORY,(__file__,'config/v2-workbench-artifact-closure.json','tools/host-lisp/bytecode_p0_stdlib.py','tools/host-lisp/strings_generated_r11_20260929.py','tools/host-lisp/v2_workbench_codemod.py','tools/host-lisp/strings_scratch_20260928.py',H.__file__))
