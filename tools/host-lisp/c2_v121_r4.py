#!/usr/bin/env python3
"""Seal the fresh v1.2.1 candidate as an isolated Promotion-v3 R4 cut."""

from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_v121_product_reproducibility as VREPRO  # noqa: E402
import c2_lite_r4 as R4  # noqa: E402


EVIDENCE = (
    ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks")
R4.REPRO = VREPRO.BASE
R4.ASSERTIONS = (
    ROOT / "build/c2.2/v1.2.1-acceptance/r4/"
    "r4-product-candidate-assertions.json")
R4.ARCHIVE = (
    ROOT / "build/c2.2/v1.2.1-acceptance/r4/"
    "c2-lite-v1.2.1-r4-product.tar.gz")
R4.MATRIX = EVIDENCE / (
    "c2.2-v1.2.1-link77-cross-invariant-delta-receipt.json")
R4.MEASUREMENTS = EVIDENCE / (
    "c2.2-link77-gc-discriminator-bundled-hardware-receipt.json")
R4.MATRIX_BINDING_KEY = "link77_cross_invariant_delta_review"
R4.MEASUREMENTS_BINDING_KEY = "link77_hardware_measurement_context"
R4.ASSERTIONS_SOURCE_BOUND = False
R4.R5_HARDWARE_RESULTS = "fresh-only-no-Link77-inheritance"


if __name__ == "__main__":
    raise SystemExit(R4.main())
