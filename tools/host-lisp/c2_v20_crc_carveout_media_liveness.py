#!/usr/bin/env python3
"""Reclose the 2.0 current-world media with the delivered liveness opt-in.

This is a media-only successor.  The product card, completed product bytes and
library medium are immutable inputs.  The shared-system medium is rebuilt by
the regular pipeline because its stager is the defective artifact.
"""

from __future__ import annotations

import argparse
import ast
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_lite_media_product as MEDIA  # noqa: E402
import c2_link95_world_bound_media as PAIR  # noqa: E402
import c2_v150_stager_liveness_successor as LIVE  # noqa: E402
import c2_v20_crc_carveout_media as BASE  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
BUILD = ROOT / "build/c2.3/v2.0-crc-carveout-media-liveness"
SHARED = BUILD / "shared-system"
MANIFEST = SHARED / "candidate-manifest.json"
DESCRIPTOR = SHARED / "boot.id"
STAGER = SHARED / "autoboot.c65"
STAGER_ELF = SHARED / "autoboot.c65.elf"
STAGER_MAP = SHARED / "autoboot.c65.map"
PRODUCT_D81 = SHARED / "lisp65-product.d81"
WORK_D81 = SHARED / "lisp65-work.d81"
MOUNT = SHARED / "lisp65-product.mount.json"
LIBRARY_D81 = BASE.LIBRARY_D81
PRODUCT_MANIFEST = BASE.MANIFEST
PREDECESSOR_RECEIPT = BASE.RECEIPT
RECEIPT = EVIDENCE / (
    "c2.3-v2.0-crc-carveout-media-liveness-closure-receipt.json")
ATTRIBUTION_RECEIPT = EVIDENCE / (
    "c2.3-v2.0-building-heap-attribution-receipt.json")
SESSION = ROOT / "config/c2-v150-v20-liveness-device-session.json"
DRIVER = Path(__file__).resolve()
OPT_IN = LIVE.OPT_IN
FORMAT = "lisp65-c2.3-v20-crc-carveout-media-liveness-closure-v1"
STATUS = "V20-D1-THREE-HOST-PRECONDITIONS-GREEN; OWNER-RECONTACT-PENDING"
RECORDED_ON = "2026-08-12"

# The artifact registry is part of the closure contract.  Equality of these
# key sets makes omission distinguishable from a merely green role/SHA scan.
PACKED_ARTIFACTS = {"autoboot.c65.elf": STAGER_ELF}
PACKED_ARTIFACT_GATES: dict[str, Callable[[Path], dict[str, Any]]] = {
    "autoboot.c65.elf": LIVE.delivered_liveness_gate,
}


class LivenessMediaError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise LivenessMediaError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"artifact absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def configure() -> Any:
    _paths, can = BASE.configure_candidate()
    MEDIA.CANONICAL = can
    MEDIA.BUILD = SHARED
    MEDIA.PRODUCT_MANIFEST = PRODUCT_MANIFEST
    MEDIA.MANIFEST = MANIFEST
    MEDIA.DESCRIPTOR = DESCRIPTOR
    MEDIA.STAGER = STAGER
    MEDIA.STAGER_MAP = STAGER_MAP
    MEDIA.PRODUCT_D81 = PRODUCT_D81
    MEDIA.WORK_D81 = WORK_D81
    MEDIA.MOUNT = MOUNT
    return can


def run_packed_artifact_gates() -> dict[str, Any]:
    require(set(PACKED_ARTIFACTS) == set(PACKED_ARTIFACT_GATES),
            "packed-artifact closure omits a registered artifact gate")
    return {name: PACKED_ARTIFACT_GATES[name](path)
            for name, path in PACKED_ARTIFACTS.items()}


def source_gate(source_override: str | None = None) -> dict[str, Any]:
    source = source_override or DRIVER.read_text(encoding="utf-8")
    tree = ast.parse(source)
    functions = {node.name: node for node in tree.body
                 if isinstance(node, ast.FunctionDef)}
    build = functions.get("build_action")
    facts = functions.get("facts")
    require(build is not None and facts is not None,
            "media successor lifecycle absent")
    build_text = ast.unparse(build)
    facts_calls = [ast.unparse(node.func) for node in ast.walk(facts)
                   if isinstance(node, ast.Call)]
    build_calls = [ast.unparse(node.func) for node in ast.walk(build)
                   if isinstance(node, ast.Call)]
    require(
        build_calls.count("MEDIA.build") == 1
        and "stager_compile_defines=(OPT_IN,)" in build_text
        and facts_calls.count("run_packed_artifact_gates") == 1
        and "BASE.complete_action" not in build_calls
        and "BASE.fresh_completion" not in build_calls
        and "BASE.CARD.card" not in build_calls
        and "BASE.library_facts" not in build_calls,
        "media successor can omit opt-in/gates or rebuild frozen freight")
    return {
        "result": "passed-media-only-complete-artifact-gate-closure",
        "shared_media_builds": 1, "library_builds": 0,
        "product_links": 0, "WPLTO_runs": 0,
        "registered_artifact_gates": sorted(PACKED_ARTIFACT_GATES),
    }


def source_mutations() -> list[str]:
    source = DRIVER.read_text(encoding="utf-8")
    build_anchor = (
        "    source_gate(); source_mutations(); artifact_mutations()\n"
        "    can = configure()\n")
    require(build_anchor in source, "liveness media build mutation anchor absent")
    cases = {
        "drop-real-stager-opt-in": source.replace(
            "    shared = MEDIA.build(stager_compile_defines=(OPT_IN,))\n"
            "    require(shared[\"artifact_count\"] == 19",
            "    shared = MEDIA.build(stager_compile_defines=())\n"
            "    require(shared[\"artifact_count\"] == 19", 1),
        "omit-registered-artifact-gates": source.replace(
            "    packed = run_packed_artifact_gates()\n"
            "    require(\n        shared[\"artifact_count\"] == 19",
            "    packed = {}\n"
            "    require(\n        shared[\"artifact_count\"] == 19", 1),
        "reenter-completion": source.replace(
            build_anchor,
            "    source_gate(); source_mutations(); artifact_mutations()\n"
            "    BASE.fresh_completion()\n    can = configure()\n", 1),
        "rebuild-library": source.replace(
            build_anchor,
            "    source_gate(); source_mutations(); artifact_mutations()\n"
            "    BASE.library_facts(0, existing=False)\n"
            "    can = configure()\n", 1),
    }
    rejected: list[str] = []
    for name, candidate in cases.items():
        try:
            source_gate(candidate)
        except (LivenessMediaError, SyntaxError):
            rejected.append(name)
    require(rejected == list(cases), "media successor source mutation survived")
    return rejected


def artifact_mutations() -> list[str]:
    predecessor_elf = BASE.SHARED / "autoboot.c65.elf"
    rejected: list[str] = []
    try:
        LIVE.delivered_liveness_gate(predecessor_elf)
    except LIVE.SuccessorError:
        rejected.append("packed-current-world-ELF-without-opt-in")
    require(rejected == ["packed-current-world-ELF-without-opt-in"],
            "historical packed-ELF mutation survived")
    return rejected


def session_value() -> dict[str, Any]:
    value = deepcopy(load(BASE.SESSION))
    value["format"] = "lisp65-c2-v150-v20-liveness-device-session-v1"
    value["status"] = "prepared-D1-recontact-review-pending"
    value["identity"] = {
        "product_medium": PRODUCT_D81.relative_to(ROOT).as_posix(),
        "library_medium": LIBRARY_D81.relative_to(ROOT).as_posix(),
    }
    value["authority"] = {
        "product_card": bind(BASE.CARD.RECEIPT),
        "media_closure": RECEIPT.relative_to(ROOT).as_posix(),
        "release_contract": bind(BASE.RELEASE_CONTRACT),
        "BUILDING_HEAP_attribution": bind(ATTRIBUTION_RECEIPT),
    }
    value["recontact_authorized"] = False
    value["D2_D5_open"] = False
    return value


def facts(*, configured: bool = False) -> dict[str, Any]:
    if not configured:
        configure()
    shared = MEDIA.check()
    build_id = BASE.product_build_id()
    library = BASE.library_facts(build_id, existing=True)
    pair = PAIR.pair_identity(PRODUCT_D81, LIBRARY_D81)
    packed = run_packed_artifact_gates()
    require(
        shared["artifact_count"] == 19
        and shared["canonical_product"] == bind(PRODUCT_MANIFEST)
        and pair["result"] == "same-world-pair"
        and pair["product_build_id"] == f"0x{build_id:08x}"
        and library["D81"] == bind(LIBRARY_D81),
        "liveness media role/readback/same-world closure red")
    require(load(SESSION) == session_value(), "blocked session handoff drift")
    return {"shared": shared, "library": library, "pair": pair,
            "packed_artifact_gates": packed}


def derive(*, configured: bool = False) -> dict[str, Any]:
    result = facts(configured=configured)
    predecessor = load(PREDECESSOR_RECEIPT)
    attribution = load(ATTRIBUTION_RECEIPT)
    require(predecessor["status"]
            == "V20-OWNED-GEOMETRY-HOST-AND-MEDIA-GREEN; D1-D5-PENDING",
            "historical incomplete closure authority drift")
    require(attribution["status"]
            == "HOST-GREEN-NO-MECHANISM; ONE-STOPPED-STATE-ROW-SPECIFIED"
            and attribution["disposition"]["capture_row_specified"] is True
            and attribution["disposition"]["recontact_authorized"] is False,
            "BUILDING-HEAP host attribution/capture-row authority absent")
    return {
        "format": FORMAT, "recorded_on": RECORDED_ON,
        "status": STATUS,
        "attempt_accounting": {
            "product_links": 0, "WPLTO_runs": 0,
            "artifact_completions": 0, "cold_stager_compiler_runs": 1,
            "shared_system_builds": 1, "library_builds": 0,
            "media_readbacks": 1, "hardware_runs": 0,
        },
        "authority": {
            "owner_approval": {"commit": "809c1e1e"},
            "incomplete_predecessor": bind(PREDECESSOR_RECEIPT),
            "BUILDING_HEAP_attribution": bind(ATTRIBUTION_RECEIPT),
            "frozen_product_manifest": bind(PRODUCT_MANIFEST),
            "frozen_library_D81": bind(LIBRARY_D81),
            "producer": bind(DRIVER),
        },
        "predecessor_retirement": {
            "current_authority": False,
            "reason": "packed stager omitted the required liveness opt-in",
            "actual_ELF_rejected": True,
        },
        "producer_gate": source_gate(),
        "producer_mutations_rejected": source_mutations(),
        "artifact_mutations_rejected": artifact_mutations(),
        "packed_artifact_gate_registry": {
            "registered": sorted(PACKED_ARTIFACT_GATES),
            "executed": sorted(result["packed_artifact_gates"]),
            "complete": True,
            "results": result["packed_artifact_gates"],
        },
        "shared_system": {
            "artifact_count": result["shared"]["artifact_count"],
            "artifact_set_sha256": result["shared"]["artifact_set_sha256"],
            "manifest": bind(MANIFEST), "boot_id": bind(DESCRIPTOR),
            "autoboot": bind(STAGER), "autoboot_ELF": bind(STAGER_ELF),
            "product_D81": bind(PRODUCT_D81), "work_D81": bind(WORK_D81),
            "readback": "passed",
        },
        "library": {"D81": result["library"]["D81"],
                    "rebuilt": False, "readback": "predecessor-bound"},
        "pair_identity": result["pair"],
        "hardware_handoff": {
            "recontact_authorized": False,
            "three_green_preconditions": {
                "packed_ELF_opt_in": True,
                "media_closure_complete": True,
                "BUILDING_HEAP_mechanism_or_capture_row": True,
            },
            "D2_D5_open": False,
        },
        "claim_limit": (
            "Media-only repair plus binding of the independent host attribution. "
            "All three desk preconditions are green, but owner recontact remains "
            "false. Product/library bytes are frozen; no device or D1-D5 claim."),
    }


def validate(value: dict[str, Any], *, verify: bool) -> None:
    require(
        value.get("format") == FORMAT and value.get("status") == STATUS
        and value.get("attempt_accounting") == {
            "product_links": 0, "WPLTO_runs": 0, "artifact_completions": 0,
            "cold_stager_compiler_runs": 1, "shared_system_builds": 1,
            "library_builds": 0, "media_readbacks": 1, "hardware_runs": 0}
        and value["predecessor_retirement"]["current_authority"] is False
        and value["packed_artifact_gate_registry"]["complete"] is True
        and value["packed_artifact_gate_registry"]["registered"]
            == value["packed_artifact_gate_registry"]["executed"]
        and value["packed_artifact_gate_registry"]["results"]
            ["autoboot.c65.elf"]["result"]
                == "passed-actual-linked-stager-prefix"
        and value["shared_system"]["artifact_count"] == 19
        and value["pair_identity"]["result"] == "same-world-pair"
        and all(value["hardware_handoff"]["three_green_preconditions"].values())
        and value["hardware_handoff"]["recontact_authorized"] is False
        and value["hardware_handoff"]["D2_D5_open"] is False,
        "liveness media closure claim drift")
    if verify:
        require(value == derive(), "liveness media receipt stale")


def receipt_mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "claim-link": lambda x: x["attempt_accounting"].update(product_links=1),
        "promote-incomplete-predecessor": lambda x:
            x["predecessor_retirement"].update(current_authority=True),
        "omit-registered-artifact-gate": lambda x:
            x["packed_artifact_gate_registry"].update(executed=[]),
        "accept-source-only-gate": lambda x:
            x["packed_artifact_gate_registry"]["results"]
                ["autoboot.c65.elf"].update(result="source-only"),
        "cross-world": lambda x: x["pair_identity"].update(result="mismatch"),
        "drop-heap-capture-row": lambda x:
            x["hardware_handoff"]["three_green_preconditions"].update(
                BUILDING_HEAP_mechanism_or_capture_row=False),
        "authorize-recontact": lambda x:
            x["hardware_handoff"].update(recontact_authorized=True),
        "open-D2-D5": lambda x: x["hardware_handoff"].update(D2_D5_open=True),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        candidate = deepcopy(value); mutate(candidate)
        try:
            validate(candidate, verify=False)
        except LivenessMediaError:
            rejected.append(name)
    require(rejected == list(cases), "liveness media receipt mutation survived")
    return rejected


def build_action() -> int:
    require(not BUILD.exists() and not RECEIPT.exists() and not SESSION.exists(),
            "liveness media successor is one-shot")
    frozen = {"product": bind(PRODUCT_MANIFEST), "library": bind(LIBRARY_D81)}
    source_gate(); source_mutations(); artifact_mutations()
    can = configure()
    shared = MEDIA.build(stager_compile_defines=(OPT_IN,))
    require(shared["artifact_count"] == 19, "shared role count drift")
    require(frozen == {"product": bind(PRODUCT_MANIFEST),
                       "library": bind(LIBRARY_D81)},
            "media repair changed frozen product/library authority")
    SESSION.write_bytes(canonical(session_value()))
    value = derive(configured=True); validate(value, verify=False)
    value["mutations_rejected"] = receipt_mutations(value)
    RECEIPT.write_bytes(canonical(value))
    print("2.0 liveness media: PASS three-host-preconditions owner-pending")
    return 0


def close_action() -> int:
    """Finish the just-built local receipt after the independent desk lane."""
    require(BUILD.is_dir() and RECEIPT.is_file() and SESSION.is_file(),
            "liveness media local closure is not available to finish")
    configure()
    SESSION.write_bytes(canonical(session_value()))
    value = derive(configured=True); validate(value, verify=False)
    value["mutations_rejected"] = receipt_mutations(value)
    RECEIPT.write_bytes(canonical(value))
    print("2.0 liveness media: PASS three-host-preconditions owner-pending")
    return 0


def check() -> int:
    value = load(RECEIPT); rejected = value.pop("mutations_rejected", None)
    validate(value, verify=True)
    require(rejected == receipt_mutations(value),
            "liveness media mutation set drift")
    print("2.0 liveness media check: PASS actual-ELF closure-complete")
    return 0


def selftest() -> int:
    source_gate()
    require(len(source_mutations()) == 4 and len(artifact_mutations()) == 1,
            "liveness media mutation count drift")
    print("2.0 liveness media selftest: PASS source=4 artifact=1")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("build", "check", "selftest", "_close"))
    action = parser.parse_args().action
    if action == "build":
        result = build_action()
        fresh = subprocess.run(
            [sys.executable, str(DRIVER), "check"], cwd=ROOT, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
        require(fresh.returncode == 0,
                "fresh liveness-media readback red:\n" + fresh.stdout)
        print(fresh.stdout.strip())
        return result
    return {"check": check, "selftest": selftest, "_close": close_action}[action]()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (LivenessMediaError, LIVE.SuccessorError, BASE.MediaClosureError,
            MEDIA.MediaError, RuntimeError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print(f"2.0 liveness media: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(2)
