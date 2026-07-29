#!/usr/bin/env python3
"""Build the remote-bound v1.2.1 R6/G6 acceptance-seal candidate."""

from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))

import c2_lite_r6_g6_seal as SEAL  # noqa: E402


BASE = ROOT / "build/c2.2/v1.2.1-acceptance"
SEAL.CONTRACT = ROOT / "config/c2-lite-v1.2.1-r6-g6-seal-contract.json"
SEAL.OFFLINE_VERIFIER = ROOT / "tools/host-lisp/c2_v121_g6_offline.py"
SEAL.PRODUCT_SET = (
    "2115b955512a3b794f68d5f2a1d160708cb89184735b7a0984a7cfc61c38f63f"
)
SEAL.PACKAGE_SET = (
    "04de1bbba86b9fa7adc030b471e6d74af04eb0aa93912693a79b9996e53b511b"
)
SEAL.CONTRACT_ID = "c2-lite-r6-g6-hardware-acceptance-v1.2.1"
SEAL.ARCHIVE_ID_PREFIX = "c2-lite-v1.2.1-r6-g6-hardware-acceptance"
SEAL.REGISTERED_SUBJECT = "c2-lite-v1.2.1-link77-successor-r6-g6"
SEAL.SEAL_RELEASE_CLAIM = "acceptance-sealed-v1.2.1-not-promoted"
SEAL.RELEASE_LABEL = "v1.2.1-acceptance"
SEAL.SEAL_EQUALS_PROMOTION = False
SEAL.R5_RECEIPT = BASE / "r5-tested/r5-tested-set-receipt.json"
SEAL.R6_RECEIPT = BASE / "r6/r6-packaging-receipt.json"
SEAL.R6_MANIFEST = BASE / "r6/ship/manifest.json"
SEAL.G5_TOP_RECEIPT = (
    BASE / "r5/hardware-session-01/g5-hardware-receipt.json"
)
SEAL.TOP_RECEIPT = BASE / "g6/session-01/g6-hardware-receipt.json"
SEAL.ACCEPTANCE_CONTRACT = ROOT / "config/c2-lite-acceptance-chain.json"
SEAL.EVIDENCE_TREES = (BASE,)
SEAL.STATIC_FILES = (
    "config/c2-lite-acceptance-chain.json",
    "config/c2-lite-media-product.json",
    "config/c2-lite-v1.2.1-r6-g6-seal-contract.json",
    "config/promotion-archive-policy.json",
    "docs/planning/v1.2.1-release-plan.md",
    "scripts/c2-v121-g5-hw.sh",
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-v1.2.1-a1-prechain-hygiene-receipt.json",
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-v1.2.1-candidate-build-first-red-resolution-receipt.json",
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-v1.2.1-link77-cross-invariant-delta-receipt.json",
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-v1.2.1-media-fresh-clone-reproducibility-receipt.json",
    "tools/host-lisp/c2_lite_g5_hardware_close.py",
    "tools/host-lisp/c2_lite_g6.py",
    "tools/host-lisp/c2_lite_g6_offline.py",
    "tools/host-lisp/c2_lite_r5_r6.py",
    "tools/host-lisp/c2_lite_r6_offline.py",
    "tools/host-lisp/c2_lite_r6_g6_seal.py",
    "tools/host-lisp/c2_v121_acceptance.py",
    "tools/host-lisp/c2_v121_candidate_media.py",
    "tools/host-lisp/c2_v121_candidate_product.py",
    "tools/host-lisp/c2_v121_g5_hardware.py",
    "tools/host-lisp/c2_v121_g6.py",
    "tools/host-lisp/c2_v121_g6_offline.py",
    "tools/host-lisp/c2_v121_matrix_delta.py",
    "tools/host-lisp/c2_v121_product_reproducibility.py",
    "tools/host-lisp/c2_v121_r4.py",
    "tools/host-lisp/c2_v121_r5_r6.py",
    "tools/host-lisp/c2_v121_r6_g6_seal.py",
    "tools/host-lisp/c2_v121_release_a1.py",
    "tools/host-lisp/remote_source_binding.py",
)


if __name__ == "__main__":
    raise SystemExit(SEAL.main())
