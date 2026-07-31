#!/usr/bin/env python3
"""Rebind Link 82 after deterministic Option-A host-gate corrections."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
OPTION_A = EVIDENCE / (
    "c2.2-require-prior-append-option-A-host-gate-receipt.json")
FASTPATH = EVIDENCE / "c2.2-require-idempotence-fastpath-receipt.json"
WPLTO = EVIDENCE / "c2.2-v1.2.5-require-option-A-wplto-receipt.json"
BUILD = ROOT / "build/c2.2/v1.2.5-candidate-product-link82"
MANIFEST = BUILD / "canonical-product-manifest.json"
FEATURES = BUILD / "receipts/v1.2.5-feature-gates.json"
MEDIA_MANIFEST = ROOT / (
    "build/c2.2/v1.2.5-candidate-media/candidate-manifest.json")
RECEIPT = EVIDENCE / (
    "c2.2-v1.2.5-option-A-deterministic-gate-artifact-rebind-receipt.json")
EXPECTED_BOUND_GATE = (
    "889871fedd84abd52ff92aed8fa66740f6113bb4d6748e8f51d3362c48c81d32")
EXPECTED_BOUND_FASTPATH = (
    "4a64d28ff0a40de6eee1a7ea6ba1baaf9924a73bb3b7b22751666fd1f8af2c1e")
EXPECTED_PRODUCT = (
    "cef92b1dace70ae700402cb37e95b755d8be5625d168dd65c2ff319176247efe")
EXPECTED_ELF = (
    "3d9e4c4e7e8d0719223561c66578fb4b24058f32e42483642322a88c4884d8d6")
EXPECTED_PROFILE = (
    "05679c60fcc6044d0944206a03b9b8f4a0bb13328353a3bed88d2395008e6fe6")


class RebindError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise RebindError(message)


def load(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"authority absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def canonical(value: Any) -> bytes:
    return (
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    ).encode("utf-8")


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    return {
        "path": path.resolve().relative_to(ROOT.resolve()).as_posix(),
        "bytes": len(data),
        "sha256": sha(data),
    }


def product_identity(manifest: dict[str, Any]) -> dict[str, str]:
    identity = manifest["identity"]
    value = {
        "resident_prg_sha256": identity["resident_prg_sha256"],
        "linked_elf_sha256": identity["linked_elf_sha256"],
        "resolved_profile_sha256": identity["resolved_profile_sha256"],
    }
    require(
        value == {
            "resident_prg_sha256": EXPECTED_PRODUCT,
            "linked_elf_sha256": EXPECTED_ELF,
            "resolved_profile_sha256": EXPECTED_PROFILE,
        },
        "Link-82 product identity drift",
    )
    return value


def main() -> int:
    try:
        option = load(OPTION_A)
        fastpath = load(FASTPATH)
        wplto = load(WPLTO)
        manifest = load(MANIFEST)
        features = load(FEATURES)
        identity_before = product_identity(manifest)
        bound_gate = wplto["host_gates"]["option_A"]
        bound_fastpath = wplto["host_gates"]["fastpath"]
        prior_rebind = wplto.get("artifact_side_rebind")
        require(
            bound_gate["sha256"] in {
                EXPECTED_BOUND_GATE, bind(OPTION_A)["sha256"]}
            and manifest["static_plane"]["require_option_A"][
                "host_execution_gate"]["sha256"] in {
                    EXPECTED_BOUND_GATE, bind(OPTION_A)["sha256"]},
            "artifact rebind predecessor gate identity drift",
        )
        require(
            bound_fastpath["sha256"] in {
                EXPECTED_BOUND_FASTPATH, bind(FASTPATH)["sha256"]}
            and manifest["static_plane"]["require_option_A"][
                "idempotence_fastpath"]["sha256"] in {
                    EXPECTED_BOUND_FASTPATH, bind(FASTPATH)["sha256"]}
            and features["require_idempotence_fastpath"]["sha256"] in {
                EXPECTED_BOUND_FASTPATH, bind(FASTPATH)["sha256"]},
            "artifact rebind predecessor fastpath identity drift",
        )
        require(
            option["recorded_on"] == "2026-07-31"
            and option["status"]
                == "passed-option-A-require-after-two-ordinary-appends-host-lane"
            and option["execution_witness"]["cases_executed"] == 2
            and option["execution_witness"]["mutations_executed"] == 5,
            "deterministic Option-A successor gate is not green",
        )
        require(
            fastpath["status"] == "passed-parser-free-idempotence-fastpath"
            and fastpath["candidate"]["idempotent_repeat"][
                "vm_instructions"] == 2750
            and fastpath["candidate"]["idempotent_repeat"][
                "prim67_reads"] == 26
            and len(fastpath["fallback_mutations"]) == 5,
            "source-closed fastpath successor gate is not green",
        )
        current_gate = bind(OPTION_A)
        current_fastpath = bind(FASTPATH)
        wplto["host_gates"]["option_A"] = current_gate
        wplto["host_gates"]["fastpath"] = current_fastpath
        history = list(wplto.get("artifact_side_rebind_history", []))
        if isinstance(prior_rebind, dict) and prior_rebind not in history:
            history.append(prior_rebind)
        wplto["artifact_side_rebind_history"] = history
        wplto["artifact_side_rebind"] = {
            "reason": (
                "Fresh-clone qualification found that the permanent host gate "
                "consumed ignored v1.2.4 acceptance, phase-M and phase-V "
                "builds. The successor rebuilds its target-shaped plane, "
                "package medium and current C2 compiler carrier solely from "
                "tracked sources. The adjacent fastpath gate now consumes "
                "the same source-built model instead of Link-75 build files."
            ),
            "predecessor_gate": bound_gate,
            "successor_gate": current_gate,
            "predecessor_fastpath": bound_fastpath,
            "successor_fastpath": current_fastpath,
            "two_consecutive_successor_receipts":
                "byte-identical-sha256-" + current_gate["sha256"],
            "WPLTO_reruns": 0,
            "product_links": 0,
            "product_identity_delta_bytes": 0,
        }
        WPLTO.write_bytes(canonical(wplto))
        current_wplto = bind(WPLTO)

        features["require_option_A"] = current_gate
        features["require_idempotence_fastpath"] = current_fastpath
        features["require_option_A_wplto"] = current_wplto
        FEATURES.write_bytes(canonical(features))

        plane = manifest["static_plane"]["require_option_A"]
        plane["host_execution_gate"] = current_gate
        plane["idempotence_fastpath"] = current_fastpath
        plane["wplto"] = current_wplto
        MANIFEST.write_bytes(canonical(manifest))
        identity_after = product_identity(load(MANIFEST))
        require(
            identity_after == identity_before,
            "artifact-side rebind changed Link-82 product identity",
        )
        media_binding = None
        if MEDIA_MANIFEST.is_file():
            media = load(MEDIA_MANIFEST)
            require(
                media["status"]
                    == "passed-complete-C2-lite-two-media-product"
                and media["artifact_count"] == 19,
                "candidate media envelope drift",
            )
            media["canonical_product"] = bind(MANIFEST)
            MEDIA_MANIFEST.write_bytes(canonical(media))
            media_binding = bind(MEDIA_MANIFEST)
        receipt = {
            "format":
                "lisp65-c2.2-v1.2.5-option-A-gate-artifact-rebind-v2",
            "recorded_on": "2026-07-31",
            "status":
                "passed-deterministic-gate-rebind-without-WPLTO-or-link",
            "predecessor_gate": bound_gate,
            "predecessor_fastpath": bound_fastpath,
            "predecessor_rebind_history": history,
            "successor_gate": current_gate,
            "successor_fastpath": current_fastpath,
            "successor_WPLTO": current_wplto,
            "candidate_manifest": bind(MANIFEST),
            "candidate_media_manifest": media_binding,
            "feature_gates": bind(FEATURES),
            "identity_before": identity_before,
            "identity_after": identity_after,
            "execution_accounting": {
                "WPLTO_reruns": 0,
                "product_links": 0,
                "hardware_runs": 0,
            },
            "driver": bind(Path(__file__).resolve()),
            "claim_limit": (
                "Artifact-side proof rebinding only. Product bytes, ELF, "
                "resolved profile, WPLTO map and hardware are unchanged."
            ),
        }
        RECEIPT.write_bytes(canonical(receipt))
        print(
            "c2-v125-gate-artifact-rebind: PASS "
            f"gate={current_gate['sha256']} WPLTO=0 links=0 "
            "product-delta=0"
        )
        return 0
    except (
        OSError, KeyError, ValueError, TypeError, json.JSONDecodeError,
        RebindError,
    ) as error:
        print(
            "c2-v125-gate-artifact-rebind: FIRST RED: " + str(error),
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
