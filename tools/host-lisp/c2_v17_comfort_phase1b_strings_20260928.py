"""Strings successor; replay predecessor against exact pre-string inputs."""
import c2_v17_comfort_phase1b_walks_20260928 as H
import strings_successor_20260928 as S
import evidence_era as E
RECEIPT='config/c2-v17-comfort-phase1b-receipt-strings-20260928.json'
HISTORY={'tools/host-lisp/c2_v17_comfort_phase1b_walks_20260928.py': 'e0ff30077a7365289e4a94b0ff3826c7b178649ebf2701fb4311b2327a0b42fe', 'config/c2-v17-comfort-phase1b-receipt-walks-20260928.json': 'a9ea3613656fcc5423c5eefdce6d839891117d0121a250ec432b1d737f9bca3f'}
def derive():
    with E.generated_workbench_world('a0caffea') as generated, S.predecessor_world(): inherited=H.derive()
    return dict(inherited=inherited,predecessor_generated_reads=generated,live_strings=S.live())
if __name__=='__main__':
    S.finish('c2_v17_comfort_phase1b',derive,RECEIPT,HISTORY,(__file__,H.__file__,'tests/bytecode/libs/p0-repl-comfort-v250.json'))
