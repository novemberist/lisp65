#!/usr/bin/env python3
"""Build the remote-bound v1.2.5 R6/G6 acceptance-seal candidate."""

from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))

import c2_lite_r6_g6_seal as SEAL  # noqa: E402


BASE = ROOT / "build/c2.2/v1.2.5-acceptance"
SEAL.CONTRACT = ROOT / "config/c2-lite-v1.2.5-r6-g6-seal-contract.json"
SEAL.OFFLINE_VERIFIER = ROOT / "tools/host-lisp/c2_v125_g6_offline.py"
SEAL.PRODUCT_SET = (
    "fa9cf0c2e97118af5f3ed52934e50387ff0d0a895499abc497987a2daaa1f56a"
)
SEAL.PACKAGE_SET = (
    "3dc8dc557624bf23405eb6ef681b726831818bc01b730c5ded0e9620364e5f34"
)
SEAL.CONTRACT_ID = "c2-lite-r6-g6-hardware-acceptance-v1.2.5"
SEAL.ARCHIVE_ID_PREFIX = "c2-lite-v1.2.5-r6-g6-hardware-acceptance"
SEAL.REGISTERED_SUBJECT = "c2-lite-v1.2.5-link82-r6-g6"
SEAL.SEAL_RELEASE_CLAIM = "acceptance-sealed-v1.2.5-not-promoted"
SEAL.RELEASE_LABEL = "v1.2.5-acceptance"
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
    "config/c2-lite-v1.2.5-r6-g6-seal-contract.json",
    "config/promotion-archive-policy.json",
    "docs/planning/v1.2.5-release-plan.md",
    "scripts/c2-v121-g5-hw.sh",
    "scripts/c2-v125-g5-hw.sh",
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-v1.2.5-a1-prechain-hygiene-receipt.json",
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-v1.2.5-link82-cross-invariant-delta-receipt.json",
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-v1.2.5-media-fresh-clone-reproducibility-receipt.json",
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-v1.2.5-phase-b-link82-receipt.json",
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-v1.2.5-g6-work-media-harness-first-red-receipt.json",
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-v1.2.5-require-prior-append-hardware-receipt.json",
    "tools/host-lisp/c2_lite_g5_hardware_close.py",
    "tools/host-lisp/c2_lite_g6.py",
    "tools/host-lisp/c2_lite_g6_offline.py",
    "tools/host-lisp/c2_lite_r5_r6.py",
    "tools/host-lisp/c2_lite_r6_offline.py",
    "tools/host-lisp/c2_lite_r6_g6_seal.py",
    "tools/host-lisp/c2_v121_r5_r6.py",
    "tools/host-lisp/c2_v125_acceptance.py",
    "tools/host-lisp/c2_v125_candidate_media.py",
    "tools/host-lisp/c2_v125_candidate_product.py",
    "tools/host-lisp/c2_v125_g5_hardware.py",
    "tools/host-lisp/c2_v125_g6.py",
    "tools/host-lisp/c2_v125_g6_offline.py",
    "tools/host-lisp/c2_v125_matrix_delta.py",
    "tools/host-lisp/c2_v125_product_reproducibility.py",
    "tools/host-lisp/c2_v125_r4.py",
    "tools/host-lisp/c2_v125_r6_g6_seal.py",
    "tools/host-lisp/c2_v125_release_a1.py",
    "tools/host-lisp/promotion_archive.py",
    "tools/host-lisp/promotion_archive_offline.py",
    "tools/host-lisp/remote_source_binding.py",
)


if __name__ == "__main__":
    raise SystemExit(SEAL.main())
