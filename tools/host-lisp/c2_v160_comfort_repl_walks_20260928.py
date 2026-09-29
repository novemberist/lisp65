"""Keep v1.6 syntactic predicates in their era; execute current editor suite."""
import os,subprocess,sys
import c2_v160_comfort_repl as H
import walks_successor_20260928 as W
import evidence_era as E
RECEIPT='config/c2-v160-comfort-repl-receipt-walks-20260928.json'
HISTORY={'tools/host-lisp/c2_v160_comfort_repl.py': '616d12bf7456c18dfe700905c70fdbe7b586785121f4b57ff4cb0957ba6fd0b5', 'tests/bytecode/dialect-v2/evidence/architecture-blocks/c2.3-v1.6-comfort-repl-host-first-receipt.json': 'b1c79d57864be198154078a8500c596b17279192e35846b344b61a837ef9bf70'}
def derive():
    with E.host_source_world('c8c20a64^') as reads:
        inherited=H.run_selftest()
    historical=H.sealed_successor_check()
    command=['nice','-n','18','ionice','-c3',sys.executable,'-B','tools/host-lisp/bytecode_p0_stdlib.py','--check','tests/bytecode/libs/p0-stdlib-ship-input-wait-base.json']
    result=subprocess.run(command,cwd=W.ROOT,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'),text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    W.S.require(result.returncode==0,result.stdout)
    return dict(inherited=inherited,historical=historical,era_reads=reads,live_suite=result.stdout.strip())
if __name__=='__main__':
    W.finish('c2-v160-comfort-repl',derive,RECEIPT,HISTORY,(__file__,H.__file__,'tests/bytecode/libs/p0-stdlib-ship-input-wait-base.json'))
