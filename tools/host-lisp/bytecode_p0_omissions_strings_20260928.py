"""Audit every declared suite against a fresh current generated closure."""
import bytecode_p0_stdlib as P
from strings_scratch_20260928 import scratch, generated
if __name__=='__main__':
    P._omission_contract_selftest()
    with scratch() as root, generated(root):P._omission_contract_audit()
