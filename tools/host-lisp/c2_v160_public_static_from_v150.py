#!/usr/bin/env python3
"""Emit only the v1.5 public static plane from a historical checkout.

The script deliberately resolves its source root from the working directory.
The v1.6 public driver invokes it inside the public v1.5 parent checkout, so
the static compiler state is public history while the v1.6 product receives
the sole WPLTO/product-link cycle.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path.cwd().resolve()
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_v150_public_product as V15  # noqa: E402


class StaticBuildError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise StaticBuildError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"artifact absent: {path}")
    return {"path": path.relative_to(ROOT).as_posix(),
            "bytes": path.stat().st_size, "sha256": sha(path)}


def build(output: Path) -> dict[str, Any]:
    output = output.resolve()
    require(output == V15.BUILD.resolve() and not output.exists(),
            "historical static output must be the fresh canonical v1.5 root")
    V15.prerequisites()
    V15.prepare_link95_base()

    original_candidate_suite = V15.L95.candidate_suite

    def candidate_suite() -> dict[str, Any]:
        value = original_candidate_suite()
        value["allow_omitted_defuns"] = [
            row for row in value.get("allow_omitted_defuns", [])
            if row.get("name") != "%time-error-duration-overflow"]
        return value

    V15.L95.candidate_suite = candidate_suite
    try:
        V15.L95.build_product()
    finally:
        V15.L95.candidate_suite = original_candidate_suite

    original_source_suite = V15.PRE.source_suite

    def source_suite():
        suite, texts = original_source_suite()
        suite["allow_omitted_defuns"] = [
            row for row in suite.get("allow_omitted_defuns", [])
            if row.get("name") not in {
                "%c2-direct-expression", "%c2-direct-expression-p"}]
        return suite, texts

    V15.PRE.source_suite = source_suite
    try:
        V15.PRE.emit_static_plane()
    finally:
        V15.PRE.source_suite = original_source_suite

    V15.prepare_public_release_authorities()
    V15.OWN.configure_projection_paths()
    V15.FIX.write_projection()
    V15.CARD.install()
    full_span = V15.CARD.BASE.PRODUCT.BASE.BASE
    phase9_replacement = full_span.BASE
    phase9_replacement.projected_contracts = (
        phase9_replacement.OLD.projected_contracts)
    V15.CARD.BASE.PRODUCT.BASE.write_projections()

    bank2 = V15.PRE.V6_PLANE / "bank2-static-code.bin"
    shelf = V15.PRE.STATIC / "product/product-shelf-v4-direct.bin"
    product = V15.PRE.STATIC / "product/substitution-artifacts.json"
    require((bank2.stat().st_size, sha(bank2)) == (46043,
                "a241a8c23a5cc8d7f7525ed2f1f522ca41f103c28928a2636a58c1972ba7e7de")
            and (shelf.stat().st_size, sha(shelf)) == (93681,
                "0924fff5a35d2c72e830e90a949ba5f70a9937e17378db1f39a49844f31a795c"),
            "historical public static payload differs from selected plane")
    value = {"status": "PASS: V1.6 PUBLIC HISTORICAL STATIC SOURCE PLANE",
        "source_role": "public-v1.5-parent", "private_evidence_inputs": 0,
        "product_WPLTO_runs": 0, "product_links": 0, "images": 6,
        "bank2": bind(bank2), "product": bind(product), "shelf": bind(shelf),
        "candidate_profile": bind(V15.OWN.CANDIDATE_PROFILE)}
    receipt = output / "public-static.json"
    receipt.write_bytes(canonical(value))
    print("v1.6 public historical static: PASS images=6 WPLTO=0 evidence=0")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    build(parser.parse_args().output)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (StaticBuildError, RuntimeError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print(f"c2-v160-public-static: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(2)
