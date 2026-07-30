#!/usr/bin/env python3
"""Build/check the isolated v1.2.4 fx+time candidate as Link 81."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_v123_candidate_product as LINK80  # noqa: E402
import c2_random_base_gate as RANDOM  # noqa: E402
import c2_v124_fx_gate as FX  # noqa: E402
import c2_v124_time_gate as TIME  # noqa: E402


PRODUCT = LINK80.PRODUCT
CAN = PRODUCT.CAN
RELEASE = "v1.2.4"
LINK = 81
BUILD = ROOT / "build/c2.2/v1.2.4-candidate-product-link81"
MANIFEST = BUILD / "canonical-product-manifest.json"
DRIVER = Path(__file__).resolve()
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
FX_RECEIPT = EVIDENCE / "c2.2-v1.2.4-fx-host-first-receipt.json"
FX_REVALIDATION = (
    EVIDENCE / "c2.2-v1.2.4-fx-post-time-revalidation-receipt.json"
)
FX_FINAL_REVALIDATION = (
    EVIDENCE / "c2.2-v1.2.4-fx-final-composition-revalidation-receipt.json"
)
TIME_RECEIPT = EVIDENCE / "c2.2-v1.2.4-time-host-first-receipt.json"
TIME_FINAL_REVALIDATION = EVIDENCE / (
    "c2.2-v1.2.4-time-final-composition-revalidation-receipt.json"
)
FX_WPLTO = EVIDENCE / "c2.2-v1.2.4-fx-wplto-receipt.json"
TIME_WPLTO = EVIDENCE / "c2.2-v1.2.4-time-wplto-receipt.json"
RANDOM_REVALIDATION = (
    EVIDENCE / "c2.2-v1-random-base-post-time-revalidation-receipt.json"
)
TIME_MANIFEST = TIME.CANDIDATE_PREFIX.with_suffix(".manifest.json")
GENERATED_WORKBENCH_SUITE = ROOT / (
    "build/bytecode/dialect-v2/suites/"
    "p0-stdlib-einsuite-core-workbench-subset.json"
)
PRIVATE_FREIGHT_RECEIPTS = (
    FX_RECEIPT,
    FX_REVALIDATION,
    FX_FINAL_REVALIDATION,
    TIME_RECEIPT,
    TIME_FINAL_REVALIDATION,
    FX_WPLTO,
    TIME_WPLTO,
    RANDOM_REVALIDATION,
)


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    return CAN.bind(path)


def prepare_freight_inputs() -> None:
    """Materialize the generated suite before any freight gate consumes it.

    ``workbench-product`` enters this driver directly, so Make prerequisites
    attached to the standalone random gate are not part of this call graph.
    A dirty proof tree used to hide that ordering bug by leaving the generated
    suite behind.
    """
    output = PRODUCT.run(
        [sys.executable, "tools/host-lisp/v11_c1_lease_codemod.py"],
        "v1.2.4 pre-freight Workbench suite generation",
    )
    if (
        "v11-c1-lease-codemod: PASS" not in output
        or not GENERATED_WORKBENCH_SUITE.is_file()
    ):
        raise RuntimeError(
            "v1.2.4 pre-freight Workbench suite generation incomplete"
        )


# Bind the inherited candidate builder to the final owner-approved producer.
PRODUCT.__doc__ = __doc__
PRODUCT.RELEASE = RELEASE
PRODUCT.LINK = LINK
PRODUCT.BUILD = BUILD
PRODUCT.MANIFEST = MANIFEST
PRODUCT.DRIVER = DRIVER
PRODUCT.V.RANDOM_MANIFEST = TIME_MANIFEST
PRODUCT.V.EXPECTED_STATIC = 43218
PRODUCT.V.EXPECTED_ENTRIES = 725
PRODUCT.V.EXPECTED_RESOLUTIONS = 2843
PRODUCT.V.EXPECTED_ROOTS = 340
PRODUCT.V.EXPECTED_DIRECT_REFS = 656
PRODUCT.V.EXPECTED_PRODUCT_ID = "0x15da63c2"
PRODUCT.V.EXPECTED_BANK2_SHA = (
    "d0ddf417757f62ef61f9fd453840673bb55ee9efa8800113a3ed78497c1d35b1"
)


_inherited_build_manifest = PRODUCT.build_manifest


def build_manifest(
    wplto: dict[str, Any],
    completion: dict[str, Any],
) -> dict[str, Any]:
    value = _inherited_build_manifest(wplto, completion)
    plane = value["static_plane"]
    plane["status"] = "passed-v1.2.4-fx-time-single-emitter-static-plane"
    plane.pop("random_manifest", None)
    plane["fx_time_manifest"] = bind(TIME_MANIFEST)
    plane["fx_contract"] = bind(FX.CONTRACT)
    plane["time_contract"] = bind(TIME.CONTRACT)
    value["candidate"]["release"] = RELEASE
    value["candidate"]["source_driver"] = bind(DRIVER)
    MANIFEST.write_bytes(CAN.json_bytes(value))
    return value


PRODUCT.build_manifest = build_manifest


def run_freight_gates() -> dict[str, Any]:
    prepare_freight_inputs()
    present = [path.is_file() for path in PRIVATE_FREIGHT_RECEIPTS]
    if any(present) and not all(present):
        missing = [
            path.relative_to(ROOT).as_posix()
            for path, available in zip(PRIVATE_FREIGHT_RECEIPTS, present)
            if not available
        ]
        raise RuntimeError(
            "partial v1.2.4 private freight authority: " + ", ".join(missing)
        )
    public_build = not any(present)
    if public_build:
        os.environ["LISP65_PUBLIC_CURRENT_SOURCE_BUILD"] = "1"
    if RANDOM.main(public_build=public_build) != 0:
        raise RuntimeError("v1.2.4 random composition gate red")
    if FX.main(public_build=public_build) != 0:
        raise RuntimeError("v1.2.4 fx source/artifact gate red")
    if TIME.main(public_build=public_build) != 0:
        raise RuntimeError("v1.2.4 time source/artifact gate red")
    if public_build:
        return {
            "mode": "public-current-source-without-private-history",
            "private_evidence_inputs": 0,
            "fx": {
                "current_source_artifact":
                    bind(FX.PUBLIC_BUILD_RECEIPT),
                "contract": bind(FX.CONTRACT),
            },
            "time": {
                "current_source_artifact":
                    bind(TIME.PUBLIC_BUILD_RECEIPT),
                "contract": bind(TIME.CONTRACT),
            },
            "random_composition_revalidation":
                bind(RANDOM.PUBLIC_BUILD_RECEIPT),
        }
    fx = load(FX_RECEIPT)
    fx_revalidation = load(FX_REVALIDATION)
    fx_final = load(FX_FINAL_REVALIDATION)
    random_revalidation = load(RANDOM_REVALIDATION)
    timing = load(TIME_RECEIPT)
    timing_final = load(TIME_FINAL_REVALIDATION)
    fx_wplto = load(FX_WPLTO)
    time_wplto = load(TIME_WPLTO)
    if (
        fx.get("status")
            != "passed-fx-host-reference-modeled-register-and-capacity"
        or fx_revalidation.get("status")
            != "passed-fx-host-reference-revalidated-in-time-composition"
        or fx_final.get("status")
            != "passed-fx-host-reference-in-final-v1.2.4-composition"
        or random_revalidation.get("status")
            != "passed-random-base-revalidated-in-fx-time-composition"
        or timing.get("status") != "passed-time-host-reference-and-admission"
        or timing_final.get("status")
            != "passed-time-host-reference-in-final-v1.2.4-composition"
        or fx_wplto.get("status") != "passed-fx-one-product-shaped-WPLTO"
        or time_wplto.get("status")
            != "passed-combined-fx-time-one-product-shaped-WPLTO"
    ):
        raise RuntimeError("v1.2.4 freight authority drift")
    return {
        "mode": "private-proof-authority",
        "private_evidence_inputs": len(PRIVATE_FREIGHT_RECEIPTS),
        "fx": {
            "host_first": bind(FX_RECEIPT),
            "post_time_revalidation": bind(FX_REVALIDATION),
            "final_composition_revalidation": bind(FX_FINAL_REVALIDATION),
            "wplto": bind(FX_WPLTO),
            "contract": bind(FX.CONTRACT),
        },
        "time": {
            "host_first": bind(TIME_RECEIPT),
            "final_composition_revalidation": bind(TIME_FINAL_REVALIDATION),
            "wplto": bind(TIME_WPLTO),
            "contract": bind(TIME.CONTRACT),
        },
        "random_composition_revalidation": bind(RANDOM_REVALIDATION),
    }


def augment_feature_receipt(freight: dict[str, Any]) -> None:
    path = BUILD / "receipts" / f"{RELEASE}-feature-gates.json"
    value = load(path)
    value.update(freight)
    value["status"] = "passed-current-source-random-while-fx-time-gates"
    path.write_bytes(CAN.json_bytes(value))


def main() -> int:
    action = sys.argv[1] if len(sys.argv) > 1 else None
    freight: dict[str, Any] | None = None
    if action == "build":
        freight = run_freight_gates()
    result = PRODUCT.main()
    if result == 0 and action == "build" and freight is not None:
        augment_feature_receipt(freight)
        print(
            "c2-v1.2.4-candidate-product: FREIGHT PASS "
            "fx=source+artifact time=source+artifact bank2=43218"
        )
    return result


if __name__ == "__main__":
    raise SystemExit(main())
