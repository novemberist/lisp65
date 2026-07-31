#!/usr/bin/env python3
"""Build/check the v1.2.5 require Option-A correction as Link 82."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_v124_candidate_product as LINK81  # noqa: E402


PRODUCT = LINK81.PRODUCT
CAN = PRODUCT.CAN
RELEASE = "v1.2.5"
LINK = 82
BUILD = ROOT / "build/c2.2/v1.2.5-candidate-product-link82"
MANIFEST = BUILD / "canonical-product-manifest.json"
DRIVER = Path(__file__).resolve()
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
OPTION_A = EVIDENCE / (
    "c2.2-require-prior-append-option-A-host-gate-receipt.json")
FASTPATH = EVIDENCE / "c2.2-require-idempotence-fastpath-receipt.json"
WPLTO = EVIDENCE / "c2.2-v1.2.5-require-option-A-wplto-receipt.json"
FX_FINAL = EVIDENCE / (
    "c2.2-v1.2.4-fx-final-composition-revalidation-receipt.json")
TIME_FINAL = EVIDENCE / (
    "c2.2-v1.2.4-time-final-composition-revalidation-receipt.json")
RANDOM_FINAL = EVIDENCE / (
    "c2.2-v1-random-base-final-composition-revalidation-receipt.json")
WHILE_RECEIPT = EVIDENCE / "c2.2-v2-while-four-view-receipt.json"
ACCEPTANCE = ROOT / "config/c2-require-prior-append-acceptance.json"
RESOLVER_CONTRACT = ROOT / "config/c2-require-resolver-contract.json"
RESOLVER_CURRENT = EVIDENCE / (
    "c2.2-require-resolver-source-index-gate-receipt.json"
)
PUBLIC_REQUIRE_RECEIPT = ROOT / (
    "build/post-promotion/require-option-A-public/"
    "current-source-freight.json"
)
TIME_MANIFEST = LINK81.TIME_MANIFEST
REQUIRE_LIBRARY_INPUTS = (
    (
        ROOT / "build/bytecode/dialect-v2/libs/testlib",
        ROOT / "tests/bytecode/libs/p0-testlib.json",
    ),
    (
        ROOT / "build/bytecode/dialect-v2/libs/buffer",
        ROOT / "tests/bytecode/libs/p0-buffer-lib.json",
    ),
)


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    return CAN.bind(path)


def run(command: list[str], label: str) -> str:
    result = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"{label} red:\n{result.stdout}")
    return result.stdout.strip().splitlines()[-1]


# Bind the inherited canonical producer to the commissioned successor.
PRODUCT.__doc__ = __doc__
PRODUCT.RELEASE = RELEASE
PRODUCT.LINK = LINK
PRODUCT.BUILD = BUILD
PRODUCT.MANIFEST = MANIFEST
PRODUCT.DRIVER = DRIVER
PRODUCT.V.RANDOM_MANIFEST = TIME_MANIFEST
PRODUCT.V.EXPECTED_STATIC = 43237
PRODUCT.V.EXPECTED_ENTRIES = 725
PRODUCT.V.EXPECTED_RESOLUTIONS = 2842
PRODUCT.V.EXPECTED_ROOTS = 340
PRODUCT.V.EXPECTED_DIRECT_REFS = 656
PRODUCT.V.EXPECTED_PRODUCT_ID = "0x270030c3"
PRODUCT.V.EXPECTED_BANK2_SHA = (
    "55193531f424da0c85349cd08679963223715c1f571704ab314743fb5f3dc248")


def build_manifest(
    wplto: dict[str, Any],
    completion: dict[str, Any],
) -> dict[str, Any]:
    # Start below the v1.2.4 wrapper so no old release/path globals can leak
    # into the successor manifest, then bind the retained fx/time freight.
    value = LINK81._inherited_build_manifest(wplto, completion)
    plane = value["static_plane"]
    plane["status"] = "passed-v1.2.5-require-option-A-static-plane"
    plane.pop("random_manifest", None)
    plane["fx_time_manifest"] = bind(TIME_MANIFEST)
    plane["fx_contract"] = bind(LINK81.FX.CONTRACT)
    plane["time_contract"] = bind(LINK81.TIME.CONTRACT)
    public_build = (
        os.environ.get("LISP65_PUBLIC_CURRENT_SOURCE_BUILD") == "1"
    )
    plane["require_option_A"] = {
        "contract": bind(RESOLVER_CONTRACT),
        "host_execution_gate": bind(OPTION_A),
        "idempotence_fastpath": bind(FASTPATH),
        "acceptance_row": bind(ACCEPTANCE),
    }
    if public_build:
        plane["require_option_A"]["public_current_source"] = bind(
            PUBLIC_REQUIRE_RECEIPT
        )
    else:
        plane["require_option_A"]["wplto"] = bind(WPLTO)
    value["candidate"]["release"] = RELEASE
    value["candidate"]["source_driver"] = bind(DRIVER)
    MANIFEST.write_bytes(CAN.json_bytes(value))
    return value


PRODUCT.build_manifest = build_manifest


def run_freight_gates() -> dict[str, Any]:
    # Reproduce the complete accepted Link-81 freight plane from current
    # sources before Link 82 consumes any selected manifest.  Calling only
    # ``prepare_freight_inputs`` generated the Workbench suite but left the
    # fx/time manifests to an invisible predecessor build tree.  A dirty tree
    # therefore hid that ``current_random_while_feature_gates`` could not bind
    # the selected time-composition manifest in a fresh clone.
    public_build = not WPLTO.is_file()
    if not public_build and not (
        OPTION_A.is_file() and FASTPATH.is_file()
    ):
        missing = [
            path.relative_to(ROOT).as_posix()
            for path in (OPTION_A, FASTPATH)
            if not path.is_file()
        ]
        raise RuntimeError(
            "partial v1.2.5 private require authority: "
            + ", ".join(missing)
        )
    if public_build:
        os.environ["LISP65_PUBLIC_CURRENT_SOURCE_BUILD"] = "1"
    predecessor_freight = LINK81.run_freight_gates()
    for prefix, suite in REQUIRE_LIBRARY_INPUTS:
        prefix.parent.mkdir(parents=True, exist_ok=True)
        run(
            [
                sys.executable,
                "tools/host-lisp/bytecode_p0_stdlib.py",
                "--check",
                "--emit-artifacts",
                prefix.relative_to(ROOT).as_posix(),
                "--artifact-role",
                "disk-lib",
                "--base-addr",
                "0x000000",
                suite.relative_to(ROOT).as_posix(),
            ],
            f"v1.2.5 require input {suite.stem}",
        )
    summaries = {
        "resolver": run(
            [sys.executable, "tools/host-lisp/c2_require_resolver_gate.py"],
            "v1.2.5 resolver gate",
        ),
        "prior_append": run(
            [sys.executable,
             "tools/host-lisp/c2_require_prior_append_option_a_gate.py"],
            "v1.2.5 prior-append execution gate",
        ),
        "fastpath": run(
            [sys.executable,
             "tools/host-lisp/c2_require_idempotence_fastpath.py"],
            "v1.2.5 idempotence gate",
        ),
    }
    if public_build:
        option = load(OPTION_A)
        fastpath = load(FASTPATH)
        resolver = load(RESOLVER_CURRENT)
        if not (
            option.get("status")
                == "passed-option-A-require-after-two-ordinary-appends-host-lane"
            and option.get("authority", {}).get(
                "private_evidence_inputs"
            ) == 0
            and fastpath.get("status")
                == "passed-public-current-source-fastpath-semantics"
            and fastpath.get("baseline_repeat", {}).get(
                "private_evidence_inputs"
            ) == 0
            and resolver.get("host_first_prerequisite", {}).get(
                "private_evidence_inputs"
            ) == 0
        ):
            raise RuntimeError(
                "v1.2.5 public current-source require freight drift"
            )
        PUBLIC_REQUIRE_RECEIPT.parent.mkdir(parents=True, exist_ok=True)
        PUBLIC_REQUIRE_RECEIPT.write_bytes(CAN.json_bytes({
            "format":
                "lisp65-v1.2.5-public-current-source-require-freight-v1",
            "version": 1,
            "status": "passed-without-private-evidence-inputs",
            "private_evidence_inputs": 0,
            "summaries": summaries,
            "resolver": bind(RESOLVER_CURRENT),
            "prior_append": bind(OPTION_A),
            "idempotence": bind(FASTPATH),
            "contract": bind(RESOLVER_CONTRACT),
            "acceptance_row": bind(ACCEPTANCE),
        }))
        return {
            "mode": "v1.2.5-public-current-source-without-private-history",
            "private_evidence_inputs": 0,
            "link81_source_freight": predecessor_freight,
            "summaries": summaries,
            "require_current_source": bind(PUBLIC_REQUIRE_RECEIPT),
        }
    option = load(OPTION_A)
    fastpath = load(FASTPATH)
    wplto = load(WPLTO)
    fx = load(FX_FINAL)
    timing = load(TIME_FINAL)
    random = load(RANDOM_FINAL)
    if not (
        option.get("status")
            == "passed-option-A-require-after-two-ordinary-appends-host-lane"
        and option["execution_witness"]["cases_executed"] == 2
        and option["execution_witness"]["mutations_executed"] == 5
        and fastpath.get("status")
            == "passed-parser-free-idempotence-fastpath"
        and fastpath["fallback_mutations"]["foreign-identity"]["result"] == "t"
        and wplto.get("status")
            == "passed-require-option-A-one-product-shaped-WPLTO"
        and fx.get("status")
            == "passed-fx-host-reference-in-final-v1.2.4-composition"
        and timing.get("status")
            == "passed-time-host-reference-in-final-v1.2.4-composition"
        and random.get("status")
            == "passed-random-base-in-final-v1.2.4-composition"
    ):
        raise RuntimeError("v1.2.5 freight authority drift")
    return {
        "mode": "v1.2.5-private-proof-authority",
        "link81_source_freight": predecessor_freight,
        "summaries": summaries,
        "require_option_A": bind(OPTION_A),
        "require_idempotence_fastpath": bind(FASTPATH),
        "require_option_A_wplto": bind(WPLTO),
        "require_acceptance_row": bind(ACCEPTANCE),
        "fx_final_composition": bind(FX_FINAL),
        "time_final_composition": bind(TIME_FINAL),
        "random_final_composition": bind(RANDOM_FINAL),
    }


def current_random_while_feature_gates() -> dict[str, Any]:
    """Use the final-composition random authority, not its Link-76 admission.

    The inherited Phase-V builder normally reruns random's historical
    *admission* calculation.  Once random, fx, time and Option A are already
    in the tracked static plane, that calculation double-adds random's 489
    bytes and is no longer a meaningful current-composition gate.  The
    current final-composition receipt was freshly source-revalidated by the
    Option-A WPLTO.  ``while`` still executes its four-view gate here.
    """
    v = PRODUCT.V
    while_output = run(
        [sys.executable, str(v.WHILE_GATE)],
        "v1.2.5 while four-view gate",
    )
    public_build = (
        os.environ.get("LISP65_PUBLIC_CURRENT_SOURCE_BUILD") == "1"
    )
    random_receipt_path = (
        LINK81.RANDOM.PUBLIC_BUILD_RECEIPT
        if public_build
        else RANDOM_FINAL
    )
    random = load(random_receipt_path)
    while_receipt = load(WHILE_RECEIPT)
    if not (
        random.get("status")
            == (
                "passed-random-base-current-source-public-build"
                if public_build
                else "passed-random-base-in-final-v1.2.4-composition"
            )
        and (
            not public_build
            or random.get("composition", {}).get(
                "private_evidence_inputs") == 0
        )
        and while_receipt.get("status")
            == "passed-four-view-while-successor-link-authorized-not-run"
        and len(while_receipt["mutations_rejected"]) == 14
        and while_receipt["bound_device_carrier"]["result"] == 3
    ):
        raise RuntimeError("v1.2.5 random/while final authority drift")
    carrier, suite, source = v.BOUND.source_binding_gate(
        v.WHILE_MANIFEST, v.WHILE_TIER)
    execution = v.BOUND.execute_bound_cases(
        v.WHILE_MANIFEST, carrier, suite, require_while=True)
    if not (
        execution["while_lowering_case"] == "passed"
        and execution["is_prim68_case"] == "passed"
    ):
        raise RuntimeError("v1.2.5 bound carrier omitted while execution")
    return {
        "random": {
            "receipt": bind(random_receipt_path),
            "candidate_manifest": bind(v.RANDOM_MANIFEST),
            "delta": {
                "bank2_code_bytes": 489,
                "directory_bytes": 77,
                "objects": 11,
                "resolution_words": 31,
                "resident_bytes": 0,
            },
        },
        "while": {
            "receipt": bind(WHILE_RECEIPT),
            "gate_output": while_output,
            "candidate_manifest": bind(v.WHILE_MANIFEST),
            "compiler_tier": source,
            "bound_execution": execution,
            "streamed_backedge":
                while_receipt["host_compiler_VM"]["streamed_backedge"],
        },
    }


def augment_feature_receipt(freight: dict[str, Any]) -> None:
    path = BUILD / "receipts" / f"{RELEASE}-feature-gates.json"
    value = load(path)
    value.update(freight)
    value["status"] = (
        "passed-current-source-random-while-fx-time-require-option-A-gates")
    path.write_bytes(CAN.json_bytes(value))


def main() -> int:
    action = sys.argv[1] if len(sys.argv) > 1 else None
    freight: dict[str, Any] | None = None
    if action == "build":
        freight = run_freight_gates()
        PRODUCT.V.feature_gates = current_random_while_feature_gates
    result = PRODUCT.main()
    if result == 0 and action == "build" and freight is not None:
        augment_feature_receipt(freight)
        print(
            "c2-v1.2.5-candidate-product: FREIGHT PASS "
            "require=Option-A bank2=43237 delta=+19 resident=+0"
        )
    return result


if __name__ == "__main__":
    raise SystemExit(main())
