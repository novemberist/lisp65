"""Live equivalence hosts, built from the current sources.

`build/equivalence/` holds era artifacts that tracked receipts bind by SHA;
a sealed check may not rewrite them, and a live gate may not test them either,
because they were linked from their era's sources. Live hosts therefore build
into their own unprotected directory. Historical cards keep pointing at their
sealed era artifact; only gates that qualify the current sources use these
paths. `LISP65_EQUIVALENCE_LIVE_DIR` overrides the directory for isolated runs.
"""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LIVE_DIR = ROOT / os.environ.get('LISP65_EQUIVALENCE_LIVE_DIR', 'build/equivalence-live')

#: dialect-v1 harness over the current sources
V1 = LIVE_DIR / 'equivalence-check'
#: dialect-v2 harness over the current sources
V2 = LIVE_DIR / 'dialect-v2-equivalence-check'
#: build receipt of the live dialect-v2 harness (never the era artifact)
V2_BUILD_RECEIPT = LIVE_DIR / 'dialect-v2-build-receipt.json'
#: lane-completion canary of the live equivalence suite
COMPLETION = LIVE_DIR / 'equivalence-completion.json'
#: L65M oracle emitted by the live `make fasl-emit-check`
FASL_TEST = LIVE_DIR / 'fasl-test.bin'
#: frozen dialect-v1 export; not built from the working tree
FROZEN_V1 = ROOT / 'build/equivalence/frozen-v1-f6527d25/equivalence-check'
