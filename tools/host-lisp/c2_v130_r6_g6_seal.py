#!/usr/bin/env python3
"""Build the remote-bound v1.3.0 R6/G6 acceptance-seal candidate."""

from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))

import c2_lite_r6_g6_seal as SEAL  # noqa: E402


BASE = ROOT / "build/c2.3/v1.3.0-acceptance"
SEAL.CONTRACT = ROOT / "config/c2-lite-v1.3.0-r6-g6-seal-contract.json"
SEAL.OFFLINE_VERIFIER = ROOT / "tools/host-lisp/c2_v130_g6_offline.py"
SEAL.PRODUCT_SET = (
    "072ca89affc35bdf0e20cab382e8bd4a9df64babf535e23f6b2e268962daed1f"
)
SEAL.PACKAGE_SET = (
    "3e0db21adb825cfa44c60bd005f2644a3717f4fcc5b02ae87e1139d3188a3397"
)
SEAL.CONTRACT_ID = "c2-lite-r6-g6-hardware-acceptance-v1.3.0"
SEAL.ARCHIVE_ID_PREFIX = "c2-lite-v1.3.0-r6-g6-hardware-acceptance"
SEAL.REGISTERED_SUBJECT = "c2-lite-v1.3.0-link88-r6-g6"
SEAL.SEAL_RELEASE_CLAIM = "acceptance-sealed-v1.3.0-not-promoted"
SEAL.RELEASE_LABEL = "v1.3.0-acceptance"
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
    "config/c2-lite-v1.3.0-r6-g6-seal-contract.json",
    "config/promotion-archive-policy.json",
    "docs/planning/1.3-ship-builder-work-plan.md",
    "docs/planning/1.3-link84-closing-first-red-review.md",
    "scripts/c2-v121-g5-hw.sh",
    "scripts/c2-v130-g5-hw.sh",
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.3.0-a1-prechain-hygiene-receipt.json",
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.3.0-link88-cross-invariant-delta-receipt.json",
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.3.0-media-fresh-clone-reproducibility-receipt.json",
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.3-link88-interactive-human-device-receipt.json",
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.3-phase-e-string-surface-first-red.json",
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.3-phase-e-g5-reset-domain-tool-first-red.json",
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.3-phase-e-g6-fresh-state-poll-first-red.json",
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.3-phase-e-g6-late-product-prompt-first-red.json",
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.3-phase-e-seal-self-inclusion-first-red.json",
    "tools/host-lisp/c2_lite_g5_hardware_close.py",
    "tools/host-lisp/c2_lite_g6.py",
    "tools/host-lisp/c2_lite_g6_offline.py",
    "tools/host-lisp/c2_lite_r5_r6.py",
    "tools/host-lisp/c2_lite_r6_offline.py",
    "tools/host-lisp/c2_lite_r6_g6_seal.py",
    "tools/host-lisp/c2_v121_r5_r6.py",
    "tools/host-lisp/c2_v130_acceptance.py",
    "tools/host-lisp/c2_v130_g5_hardware.py",
    "tools/host-lisp/c2_v130_g6.py",
    "tools/host-lisp/c2_v130_g6_offline.py",
    "tools/host-lisp/c2_v130_matrix_delta.py",
    "tools/host-lisp/c2_v130_product_reproducibility.py",
    "tools/host-lisp/c2_v130_r4.py",
    "tools/host-lisp/c2_v130_r5_r6.py",
    "tools/host-lisp/c2_v130_r6_g6_seal.py",
    "tools/host-lisp/c2_v130_release_a1.py",
    "tools/host-lisp/c2_v130_static_input_carrier.py",
    "tools/host-lisp/promotion_archive.py",
    "tools/host-lisp/promotion_archive_offline.py",
    "tools/host-lisp/remote_source_binding.py",
)


if __name__ == "__main__":
    raise SystemExit(SEAL.main())
