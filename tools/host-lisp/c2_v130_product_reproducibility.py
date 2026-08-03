#!/usr/bin/env python3
"""Prove the Link-88 v1.3.0 media set in two varied fresh checkouts."""

from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_lite_product_reproducibility as BASE  # noqa: E402


BASE.GENERATOR = Path(__file__).resolve()
BASE.DEFAULT_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.3.0-media-fresh-clone-reproducibility-receipt.json")
BASE.FORMAT = "lisp65-c2-lite-v1.3.0-media-product-reproducibility-v1"
BASE.BUILD_COMMANDS = (
    ("python3", "tools/host-lisp/c2_v130_static_input_carrier.py",
     "materialize"),
    ("make", "--no-print-directory", "v2-workbench-artifacts",
     "bytecode-p0-buffer-lib-artifacts", "c2-while-check",
     "fasl-emit-check"),
    ("python3", "tools/host-lisp/c2_v13_link88_candidate_product.py", "build"),
    ("python3", "tools/host-lisp/c2_v13_link88_candidate_media.py", "build"),
)
BASE.MEDIA_MANIFEST_RELATIVE = Path(
    "build/c2.3/v1.3.0-candidate-media-link88-r1/candidate-manifest.json")
BASE.TOOLCHAIN_MATERIALIZATION = "symlink"


if __name__ == "__main__":
    raise SystemExit(BASE.main())
