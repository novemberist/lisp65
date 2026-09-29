"""Reconstruct the historical blink suite and generated sources together."""
import c2_v17_repl_idle_blink_card as H
import evidence_era as E
import strings_successor_r2_20260928 as S
RECEIPT='config/c2-v17-repl-idle-blink-receipt-strings-r2-20260928.json'
HISTORY={'tools/host-lisp/c2_v17_repl_idle_blink_card.py': '6f62493ff12249894bc2b3692b89a8e4f867dad506fe0fb264492be77e38d40c', 'tests/bytecode/dialect-v2/evidence/architecture-blocks/c2.3-v1.7-repl-idle-blink-card-receipt.json': '6da7ba632fd53cd55d59f8ef7626c453c9f3b1bb53b95c14bd252b50120698b8', 'tools/host-lisp/c2_v17_repl_idle_blink_strings_20260928.py': '3f96718cbc6122e01cd72a923d015f2176b9206e7d6ee807a7e1cc6826f601eb', 'config/c2-v17-repl-idle-blink-receipt-strings-20260928.json': 'ecba7786db7c0d0d64ab85f920f4a37f1268a22cc5727f8cd7a238089d71f290'}
def derive():
    with E.generated_workbench_world('520352a6') as reads:
        sealed,observed=H.check_sealed_successor()
    return dict(historical=observed,generated_reads=reads,live_strings=S.live())
if __name__=='__main__':
    S.finish('c2-v17-repl-idle-blink',derive,RECEIPT,HISTORY,(__file__,H.__file__,'tests/bytecode/libs/p0-repl-comfort-v250.json'))
