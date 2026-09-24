#!/usr/bin/env python3
"""Era-bound successor check of the Link-106 convergence granularity review.

`c2_v20_convergence_granularity_review.py --check` re-derives its receipt from
live files. Two of its bound authorities moved after the review was sealed
(`0124407e`, 2026-08-14): the mapped-far convergence source and the parked
items register. The desk review's claim is about the world it read, so this
successor re-derives the receipt with exactly those two authorities read from
the sealing commit and requires the stored receipt byte for byte. Every other
authority stays live. Controls: the live world must be detected as drifted,
an era read of any other path is refused by construction, and a mutated
stored receipt is rejected.
"""
from __future__ import annotations

from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'tools/host-lisp'))
import c2_v20_convergence_granularity_review as G  # noqa: E402
import evidence_era as E  # noqa: E402

ERA = '0124407e'
DRIFTED = ('src/c2_mapped_far_convergence.s', 'docs/reference/parked-items-register.md')


def derive(era: bool) -> bytes:
    if not era:
        return G.canonical(G.build_receipt())
    with E.host_source_world(ERA, DRIFTED) as reads:
        encoded = G.canonical(G.build_receipt())
    G.require(set(reads) >= set(DRIFTED), 'era authorities were not consumed')
    return encoded


def main() -> int:
    try:
        stored = G.RECEIPT.read_bytes()
        historical = derive(True)
        G.require(historical == stored, 'era-bound granularity receipt differs')
        live = derive(False)
        G.require(live != stored, 'live-drift control vacuous: live world equals the sealed era')
        live_rows = json.loads(live)['authority']
        stored_rows = json.loads(stored)['authority']
        moved = sorted(row['path'] for key, row in live_rows.items()
                       if isinstance(row, dict) and row != stored_rows.get(key))
        G.require(moved == sorted(DRIFTED), 'unexpected live authority drift: ' + repr(moved))
        mutated = bytearray(stored); mutated[len(mutated)//2] ^= 1
        G.require(bytes(mutated) != historical, 'stored-receipt mutation survived')
        print(json.dumps(dict(status='PASS: ERA-BOUND GRANULARITY REVIEW', era=ERA,
                              era_authorities=list(DRIFTED), live_drift=moved,
                              controls=['live-drift-detected', 'stored-receipt-mutation-rejected'],
                              receipt=G.bind(G.RECEIPT)), indent=2))
        return 0
    except (G.ReviewError, E.EraError, OSError, ValueError) as error:
        print(f'c2-v20-convergence-granularity-era: FAIL: {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
