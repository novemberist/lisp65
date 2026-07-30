#!/usr/bin/env python3
"""Build the remote-bound v1.2.4 R6/G6 acceptance-seal candidate."""

from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))

import c2_lite_r6_g6_seal as SEAL  # noqa: E402


BASE = ROOT / "build/c2.2/v1.2.4-acceptance"
SEAL.CONTRACT = ROOT / "config/c2-lite-v1.2.4-r6-g6-seal-contract.json"
SEAL.OFFLINE_VERIFIER = ROOT / "tools/host-lisp/c2_v124_g6_offline.py"
SEAL.PRODUCT_SET = (
    "f686c8a78d7e65927740049e0b33c51f879613f21593b46be8342840c18093f8"
)
SEAL.PACKAGE_SET = (
    "1fa8ef2494eeeff40e4456f80e007aa46cb30f1e876856aaed9ea225469c8eb6"
)
SEAL.CONTRACT_ID = "c2-lite-r6-g6-hardware-acceptance-v1.2.4"
SEAL.ARCHIVE_ID_PREFIX = "c2-lite-v1.2.4-r6-g6-hardware-acceptance"
SEAL.REGISTERED_SUBJECT = "c2-lite-v1.2.4-link81-r6-g6"
SEAL.SEAL_RELEASE_CLAIM = "acceptance-sealed-v1.2.4-not-promoted"
SEAL.RELEASE_LABEL = "v1.2.4-acceptance"
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
    "config/c2-lite-v1.2.4-r6-g6-seal-contract.json",
    "config/promotion-archive-policy.json",
    "docs/planning/1.2.4-work-plan.md",
    "scripts/c2-v121-g5-hw.sh",
    "scripts/c2-v124-g5-hw.sh",
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-v1.2.4-a1-prechain-hygiene-receipt.json",
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-v1.2.4-link81-cross-invariant-delta-receipt.json",
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-v1.2.4-media-fresh-clone-reproducibility-receipt.json",
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-v1.2.4-phase-e-link81-receipt.json",
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-v1.2.4-phase-m-hardware-receipt.json",
    "tools/host-lisp/c2_lite_g5_hardware_close.py",
    "tools/host-lisp/c2_lite_g6.py",
    "tools/host-lisp/c2_lite_g6_offline.py",
    "tools/host-lisp/c2_lite_r5_r6.py",
    "tools/host-lisp/c2_lite_r6_offline.py",
    "tools/host-lisp/c2_lite_r6_g6_seal.py",
    "tools/host-lisp/c2_v121_r5_r6.py",
    "tools/host-lisp/c2_v124_acceptance.py",
    "tools/host-lisp/c2_v124_candidate_media.py",
    "tools/host-lisp/c2_v124_candidate_product.py",
    "tools/host-lisp/c2_v124_g5_hardware.py",
    "tools/host-lisp/c2_v124_g6.py",
    "tools/host-lisp/c2_v124_g6_offline.py",
    "tools/host-lisp/c2_v124_matrix_delta.py",
    "tools/host-lisp/c2_v124_product_reproducibility.py",
    "tools/host-lisp/c2_v124_r4.py",
    "tools/host-lisp/c2_v124_r6_g6_seal.py",
    "tools/host-lisp/c2_v124_release_a1.py",
    "tools/host-lisp/promotion_archive.py",
    "tools/host-lisp/promotion_archive_offline.py",
    "tools/host-lisp/remote_source_binding.py",
)


if __name__ == "__main__":
    raise SystemExit(SEAL.main())
