#!/usr/bin/env python3
"""Build the exact static 15-case R3 preflight without launching an emulator."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import sys
from typing import Any

import block_capacity_delta_policy as CAPACITY


ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "config" / "r3-g3-harness.json"
CONTRACT = ROOT / "config" / "r3-g3-g6-contract.json"
RECEIPT = ROOT / "tests" / "bytecode" / "dialect-v2" / "evidence" / "r3" / "g3-static-preflight-receipt.json"
FORMAT = "lisp65-r3-g3-static-preflight-v1"
CONFIG_FORMAT = "lisp65-r3-g3-harness-v1"
SHA = re.compile(r"[0-9a-f]{64}")
EXPECTED_FIDELITY = {"emulator-valid": 9, "hardware-only": 6}
SPECIAL_ROLES = {"candidate-manifest", "rom", "xmega65", "sd-base"}


class HarnessError(RuntimeError):
    pass


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def exact(value: Any, keys: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        raise HarnessError(f"{label} schema drift")
    return value


def repo_path(value: Any, label: str) -> Path:
    if not isinstance(value, str) or not value:
        raise HarnessError(f"{label} must be a repository path")
    pure = PurePosixPath(value)
    if pure.is_absolute() or pure.as_posix() != value or ".." in pure.parts:
        raise HarnessError(f"{label} is not canonical")
    return ROOT / pure


def load(path: Path, label: str) -> dict[str, Any]:
    try:
        if path.is_symlink() or not path.is_file():
            raise HarnessError(f"{label} must be a regular file")
        value = json.loads(path.read_text(encoding="utf-8"))
    except HarnessError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise HarnessError(f"cannot read {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise HarnessError(f"{label} must be an object")
    return value


def bound(value: Any, label: str) -> Path:
    item = exact(value, {"path", "sha256"}, label)
    path = repo_path(item["path"], f"{label}.path")
    if not SHA.fullmatch(str(item["sha256"])) or path.is_symlink() or not path.is_file() or sha(path) != item["sha256"]:
        raise HarnessError(f"{label} binding drift")
    return path


def validate(config: dict[str, Any]) -> dict[str, Any]:
    exact(
        config,
        {
            "format", "version", "id", "status", "contract_id", "contract_path",
            "matrix", "product_receipt", "targets", "verifiers", "cases",
        },
        "G3 harness",
    )
    if (
        config["format"] != CONFIG_FORMAT or config["version"] != 1
        or config["id"] != "r3-exact-15-case-static-harness"
        or config["status"] != "static-preflight-only-no-execution"
        or config["contract_id"] != "workbench-r3-g3-g6"
        or config["contract_path"] != "config/r3-g3-g6-contract.json"
    ):
        raise HarnessError("G3 harness identity/status drift")
    matrix_path = bound(config["matrix"], "matrix")
    product_path = bound(config["product_receipt"], "product_receipt")
    matrix = load(matrix_path, "boot matrix")
    product = load(product_path, "R3 product receipt")
    if (
        product.get("format") != "lisp65-r3-product-block-receipt-v1"
        or product.get("status") != "product-implemented-g3-not-run"
        or product.get("verification", {}).get("emulator_started") is not False
    ):
        raise HarnessError("R3 product receipt claim drift")
    try:
        CAPACITY.validate_policy()
        CAPACITY.validate_capacity_delta(product["capacity_delta"])
    except (CAPACITY.CapacityDeltaError, KeyError) as exc:
        raise HarnessError(f"product capacity delta drift: {exc}") from exc
    manifest_path = bound(product["candidate_manifest"], "candidate_manifest")
    manifest = load(manifest_path, "candidate manifest")
    if (
        manifest.get("format") != "lisp65-r3-candidate-manifest-v1"
        or manifest.get("status") != "product-built-g3-not-run"
        or manifest.get("artifact_set_sha256")
        != product.get("product_identity", {}).get("artifact_set_sha256")
    ):
        raise HarnessError("candidate manifest/product identity drift")
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        raise HarnessError("candidate manifest inventory missing")
    roles = {row.get("role") for row in artifacts if isinstance(row, dict)}
    if None in roles or len(roles) != len(artifacts):
        raise HarnessError("candidate artifact roles must be complete and unique")
    for index, row in enumerate(artifacts):
        path = repo_path(row.get("path"), f"artifact[{index}].path")
        if (
            path.is_symlink() or not path.is_file() or path.stat().st_size != row.get("bytes")
            or sha(path) != row.get("sha256")
        ):
            raise HarnessError(f"candidate artifact binding drift: {row.get('role')}")

    targets = exact(config["targets"], {"host-static", "bytecode-host", "xmega65-controlled", "hardware-receipt"}, "targets")
    expected_targets = {
        "host-static": {"kind": "read-only-static", "executes_product": False},
        "bytecode-host": {"kind": "host-model", "executes_product": False},
        "xmega65-controlled": {"kind": "emulator", "executes_product": True},
        "hardware-receipt": {"kind": "physical-hardware", "executes_product": True},
    }
    if targets != expected_targets:
        raise HarnessError("target semantics drift")
    verifiers = exact(
        config["verifiers"],
        {
            "product-block", "stager-trace", "media-policy", "hardware-oracle",
            "safe-runner", "process-cleanup", "smoke-verifier",
        },
        "verifiers",
    )
    verifier_paths = {name: bound(value, f"verifier.{name}") for name, value in verifiers.items()}

    matrix_cases = matrix.get("cases")
    harness_cases = config["cases"]
    if not isinstance(matrix_cases, list) or not isinstance(harness_cases, list) or len(matrix_cases) != 15 or len(harness_cases) != 15:
        raise HarnessError("exact 15-case matrix required")
    matrix_by_id = {row.get("id"): row for row in matrix_cases if isinstance(row, dict)}
    if len(matrix_by_id) != 15:
        raise HarnessError("matrix case identity drift")
    counts = {key: 0 for key in EXPECTED_FIDELITY}
    covered_roles: set[str] = set()
    previous = ""
    case_rows = []
    for index, raw in enumerate(harness_cases):
        case = exact(raw, {"id", "fidelity", "target", "verifier", "artifact_roles"}, f"case[{index}]")
        case_id = case["id"]
        if not isinstance(case_id, str) or case_id <= previous or case_id not in matrix_by_id:
            raise HarnessError("harness cases must be sorted exact matrix identities")
        previous = case_id
        matrix_case = matrix_by_id[case_id]
        if case["fidelity"] != matrix_case.get("fidelity"):
            raise HarnessError(f"case fidelity drift: {case_id}")
        if case["target"] not in targets or case["verifier"] not in verifiers:
            raise HarnessError(f"unbound target/verifier: {case_id}")
        if (
            case["fidelity"] == "emulator-valid" and case["target"] == "hardware-receipt"
        ) or (
            case["fidelity"] == "hardware-only" and case["target"] != "hardware-receipt"
        ):
            raise HarnessError(f"target authority drift: {case_id}")
        case_roles = case["artifact_roles"]
        if not isinstance(case_roles, list) or not case_roles or any(not isinstance(role, str) for role in case_roles):
            raise HarnessError(f"artifact roles missing: {case_id}")
        unknown = set(case_roles) - roles - SPECIAL_ROLES
        if unknown:
            raise HarnessError(f"unbound artifact roles for {case_id}: {sorted(unknown)}")
        covered_roles.update(case_roles)
        counts[case["fidelity"]] += 1
        case_rows.append({
            "id": case_id, "fidelity": case["fidelity"], "target": case["target"],
            "verifier": case["verifier"], "artifact_roles": case_roles, "status": "not-run",
        })
    if counts != EXPECTED_FIDELITY or set(matrix_by_id) != {row["id"] for row in harness_cases}:
        raise HarnessError("harness fidelity/coverage drift")
    required_roles = roles | SPECIAL_ROLES
    if not required_roles <= covered_roles:
        raise HarnessError(f"candidate closure is incomplete: {sorted(required_roles - covered_roles)}")
    for gate in ("G3", "G6"):
        statuses = product["verification"][gate]
        if not isinstance(statuses, dict) or set(statuses.values()) != {"not-run"}:
            raise HarnessError(f"product receipt {gate} status drift")
    return {
        "matrix": matrix_path, "product": product_path, "manifest": manifest_path,
        "product_value": product, "manifest_value": manifest, "verifiers": verifier_paths,
        "cases": case_rows, "counts": counts,
    }


def build_receipt() -> dict[str, Any]:
    config = load(CONFIG, "G3 harness")
    state = validate(config)
    contract = load(CONTRACT, "R3 contract")
    product = state["product_value"]
    return {
        "format": FORMAT,
        "id": "r3-g3-static-exact-15-case-preflight",
        "status": "passed-g3-not-run",
        "measured_on": "2026-07-19",
        "contract": {"path": CONTRACT.relative_to(ROOT).as_posix(), "sha256": sha(CONTRACT)},
        "harness": {"path": CONFIG.relative_to(ROOT).as_posix(), "sha256": sha(CONFIG)},
        "matrix": {"path": state["matrix"].relative_to(ROOT).as_posix(), "sha256": sha(state["matrix"])},
        "product_receipt": {"path": state["product"].relative_to(ROOT).as_posix(), "sha256": sha(state["product"])},
        "candidate_manifest": {"path": state["manifest"].relative_to(ROOT).as_posix(), "sha256": sha(state["manifest"])},
        "product_artifact_set_sha256": product["product_identity"]["artifact_set_sha256"],
        "toolchain": {
            "xmega65": contract["toolchain_bindings"]["xmega65"],
            "rom": contract["toolchain_bindings"]["rom"],
            "sd_base": contract["toolchain_bindings"]["sd_base"],
        },
        "verifiers": {
            name: {"path": path.relative_to(ROOT).as_posix(), "sha256": sha(path)}
            for name, path in sorted(state["verifiers"].items())
        },
        "counts": state["counts"] | {"total": 15},
        "cases": state["cases"],
        "claims": {
            "static_bindings_complete": True,
            "all_cases_not_run": True,
            "emulator_started": False,
            "hardware_started": False,
            "ready_for_first_emulator_run": True,
            "G3": "not-run",
            "G6": "not-run",
            "release_effect": "none",
        },
    }


def selftest() -> None:
    config = load(CONFIG, "G3 harness")
    validate(config)
    survivors = []
    for name, mutate in (
        ("missing-case", lambda x: x["cases"].pop()),
        ("wrong-fidelity", lambda x: x["cases"][0].update(fidelity="hardware-only")),
        ("unbound-target", lambda x: x["cases"][0].update(target="unknown")),
        ("unbound-verifier", lambda x: x["cases"][0].update(verifier="unknown")),
        ("unbound-artifact", lambda x: x["cases"][0]["artifact_roles"].append("foreign")),
    ):
        changed = deepcopy(config)
        mutate(changed)
        try:
            validate(changed)
        except HarnessError:
            continue
        survivors.append(name)
    if survivors:
        raise HarnessError(f"selftest accepted mutations: {survivors}")
    print("r3-g3-harness: SELFTEST PASS mutations=5 cases=15 execution=none")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("selftest", "generate", "check"))
    parser.add_argument("--receipt", type=Path, default=RECEIPT)
    args = parser.parse_args(argv)
    receipt_path = args.receipt if args.receipt.is_absolute() else ROOT / args.receipt
    try:
        if args.command == "selftest":
            selftest()
            return 0
        receipt = build_receipt()
        encoded = canonical(receipt)
        if args.command == "generate":
            receipt_path.parent.mkdir(parents=True, exist_ok=True)
            receipt_path.write_bytes(encoded)
            print(
                "r3-g3-harness: WROTE status=passed-g3-not-run cases=15 "
                f"set={receipt['product_artifact_set_sha256']} output={receipt_path.relative_to(ROOT)}"
            )
        else:
            if receipt_path.is_symlink() or not receipt_path.is_file() or receipt_path.read_bytes() != encoded:
                raise HarnessError("G3 static preflight receipt drift")
            print(
                "r3-g3-harness: PASS status=passed-g3-not-run cases=15 "
                "emulator=not-run hardware=not-run"
            )
        return 0
    except (HarnessError, CAPACITY.CapacityDeltaError, OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        print(f"r3-g3-harness: FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
