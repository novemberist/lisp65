#!/usr/bin/env python3
"""Prepare/evaluate the commissioned Link-85 full-reset closing session."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "scripts/c2-v13-closing-device.py"
SPEC = importlib.util.spec_from_file_location("c2_v13_closing_device", SOURCE)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot load closing-session driver: {SOURCE}")
OLD = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = OLD
SPEC.loader.exec_module(OLD)


OLD.CONFIG = ROOT / "config/c2-ship-builder-v1-link85-hardware-session.json"
OLD.CANDIDATE = ROOT / (
    "build/c2.3/v1.3.0-candidate-product-link85-r1/"
    "canonical-product-manifest.json"
)
OLD.MEDIA_MANIFEST = ROOT / (
    "build/c2.3/v1.3.0-candidate-media-link85-r1/candidate-manifest.json"
)
OLD.OUT = ROOT / "build/ship-builder/v13/link85-closing-device-session"
OLD.DEPLOYMENT = OLD.OUT / "deployment.json"
OLD.PREPARATION = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.3-link85-full-reset-closing-device-preparation-receipt.json"
)
OLD.HARDWARE = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.3-link85-full-reset-closing-device-receipt.json"
)
OLD.DRIVER = Path(__file__).resolve()
OLD.SCRIPT = ROOT / "scripts/c2-v13-link85-closing-hw.sh"


if __name__ == "__main__":
    raise SystemExit(OLD.main())
