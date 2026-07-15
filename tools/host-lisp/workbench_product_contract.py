#!/usr/bin/env python3
"""Validate the narrow AP7 Workbench product and verified package contract."""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "host-lisp"))

import workbench_ship as WorkbenchShip  # noqa: E402


FORMAT = "lisp65-workbench-product-contract-v1"
DEFAULT_CONTRACT = ROOT / "config" / "workbench-product-contract.json"
ROOT_KEYS = {"format", "status", "claims", "product", "release_policy", "workflows", "delivery", "package", "release"}
CLAIM_KEYS = {"interactive_product", "language_semantics", "release", "runtime_export"}
PRODUCT_KEYS = {"id", "profile", "ship_format", "verified_status"}
RELEASE_POLICY_KEYS = {
    "only_product", "required_dialect", "dialect_v1", "runtime_core",
    "runtime_core_receipt_effect", "requires",
}
DELIVERY_KEYS = {"resident", "on_demand", "optional"}
PACKAGE_KEYS = {"files", "verified_directory", "deploy_target", "deploy_dry_run_target"}
RELEASE_KEYS = {"G3", "generic_targets", "release_claim"}
EXPECTED_WORKFLOWS = [
    "repl", "editor", "lcc-compile-install", "source-load-save",
    "compile-load-lib", "error-recovery",
]
EXPECTED_FILES = [
    "manifest.json", "lisp65-mvp-workbench.prg",
    "lisp65-mvp-workbench.blob.bin", "lisp65-mvp-workbench.overlays.bin",
    "lisp65-mvp-workbench.d81", "mvp-vm-stdlib-footprint.txt",
    "workbench-d81-manifest.txt", "stdlib-artifact-manifest.json",
    "resolved-profile.txt", "toolchain-report.txt",
]


class ContractError(RuntimeError):
    pass


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ContractError(f"duplicate JSON key: {key}")
        value[key] = item
    return value


def _load(path: Path) -> dict[str, Any]:
    try:
        if path.is_symlink() or not path.is_file():
            raise ContractError(f"contract must be a regular non-symlink file: {path}")
        value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_strict_object)
    except ContractError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ContractError(f"cannot read contract {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ContractError("contract root must be an object")
    return value


def _exact(value: Any, keys: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ContractError(f"{label} must be an object")
    missing = sorted(keys - set(value))
    extra = sorted(set(value) - keys)
    if missing or extra:
        raise ContractError(
            f"{label} keys differ: missing={','.join(missing) or '-'} "
            f"extra={','.join(extra) or '-'}"
        )
    return value


def _strings(value: Any, label: str) -> list[str]:
    if not isinstance(value, list) or not value:
        raise ContractError(f"{label} must be a non-empty list")
    if any(not isinstance(item, str) or not item for item in value):
        raise ContractError(f"{label} must contain non-empty strings")
    if len(value) != len(set(value)):
        raise ContractError(f"{label} contains duplicates")
    return value


def validate(contract: dict[str, Any]) -> None:
    _exact(contract, ROOT_KEYS, "contract")
    if contract["format"] != FORMAT or contract["status"] != "candidate":
        raise ContractError("contract format/status must describe the AP7 candidate")

    claims = _exact(contract["claims"], CLAIM_KEYS, "claims")
    if claims != {
        "interactive_product": True,
        "language_semantics": False,
        "release": False,
        "runtime_export": False,
    }:
        raise ContractError("claims differ from the approved Workbench boundary")

    product = _exact(contract["product"], PRODUCT_KEYS, "product")
    if product != {
        "id": "lisp65-workbench",
        "profile": "mvp-vm-stdlib-einsuite-core-workbench",
        "ship_format": "lisp65-workbench-ship-v5",
        "verified_status": "g2-verified-candidate",
    }:
        raise ContractError("product identity differs from Ship-v5")

    release_policy = _exact(
        contract["release_policy"], RELEASE_POLICY_KEYS, "release_policy"
    )
    if release_policy != {
        "only_product": "lisp65-workbench",
        "required_dialect": "dialect-v2",
        "dialect_v1": "frozen-evidence-never-release",
        "runtime_core": "internal-proof-never-release",
        "runtime_core_receipt_effect": "none",
        "requires": [
            "workbench-v2-link-budget",
            "full-workbench-plus-runtime-g5",
        ],
    }:
        raise ContractError("release convergence differs from the Workbench-v2 decision")

    if _strings(contract["workflows"], "workflows") != EXPECTED_WORKFLOWS:
        raise ContractError("supported Workbench workflows differ from the AP7 boundary")

    delivery = _exact(contract["delivery"], DELIVERY_KEYS, "delivery")
    if _strings(delivery["resident"], "delivery.resident") != [
        "repl", "lcc", "source-load", "compile-string", "load-lib", "error-recovery",
    ]:
        raise ContractError("resident delivery surface differs from the Workbench profile")
    if _strings(delivery["on_demand"], "delivery.on_demand") != ["ide", "m65d"]:
        raise ContractError("on-demand delivery surface differs from the Workbench profile")
    if _strings(delivery["optional"], "delivery.optional") != ["idex"]:
        raise ContractError("optional delivery surface differs from the Workbench profile")

    package = _exact(contract["package"], PACKAGE_KEYS, "package")
    if _strings(package["files"], "package.files") != EXPECTED_FILES:
        raise ContractError("package file set/order differs from Ship-v5")
    if package["verified_directory"] != "build/ship":
        raise ContractError("verified package directory must remain build/ship")
    if package["deploy_target"] != "workbench-deploy":
        raise ContractError("verified deploy target drifted")
    if package["deploy_dry_run_target"] != "workbench-deploy-dry-run":
        raise ContractError("verified dry-run target drifted")

    release = _exact(contract["release"], RELEASE_KEYS, "release")
    if release != {
        "G3": "not-available",
        "generic_targets": "fail-closed",
        "release_claim": False,
    }:
        raise ContractError("release state must remain fail-closed while G3 is unavailable")


def validate_ship(contract: dict[str, Any], ship_dir: Path) -> None:
    errors = WorkbenchShip.verify_package(
        ship_dir, strict=True, expected_format=contract["product"]["ship_format"]
    )
    if errors:
        raise ContractError("Ship-v5 verification failed: " + "; ".join(errors))
    actual = sorted(path.name for path in ship_dir.iterdir())
    expected = sorted(contract["package"]["files"])
    if actual != expected:
        raise ContractError(
            "verified package files differ: expected=%s actual=%s"
            % (",".join(expected), ",".join(actual))
        )
    manifest = _load(ship_dir / "manifest.json")
    for field, expected_value in (
        ("product", contract["product"]["id"]),
        ("profile", contract["product"]["profile"]),
        ("status", contract["product"]["verified_status"]),
    ):
        if manifest.get(field) != expected_value:
            raise ContractError(f"Ship-v5 {field} differs from the product contract")


def _expect_failure(label: str, action: Callable[[], None]) -> None:
    try:
        action()
    except ContractError:
        return
    raise ContractError(f"selftest mutation was accepted: {label}")


def selftest() -> None:
    contract = _load(DEFAULT_CONTRACT)
    validate(contract)
    mutations: list[tuple[str, Callable[[dict[str, Any]], None]]] = [
        ("release claim", lambda value: value["claims"].update(release=True)),
        ("runtime export", lambda value: value["claims"].update(runtime_export=True)),
        ("workflow", lambda value: value["workflows"].pop()),
        ("resident surface", lambda value: value["delivery"]["resident"].append("eval")),
        ("ship format", lambda value: value["product"].update(ship_format="v6")),
        ("v1 release", lambda value: value["release_policy"].update(dialect_v1="release")),
        ("runtime release", lambda value: value["release_policy"].update(runtime_core="release")),
        ("runtime receipt", lambda value: value["release_policy"].update(runtime_core_receipt_effect="release")),
        ("package", lambda value: value["package"]["files"].pop()),
        ("G3", lambda value: value["release"].update(G3="pass")),
    ]
    for label, mutate in mutations:
        changed = copy.deepcopy(contract)
        mutate(changed)
        _expect_failure(label, lambda changed=changed: validate(changed))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("contract", nargs="?", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--ship-dir", type=Path)
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.selftest:
            selftest()
            print("workbench-product-contract: SELFTEST PASS mutations=10")
            return 0
        contract = _load(args.contract)
        validate(contract)
        if args.ship_dir is not None:
            validate_ship(contract, args.ship_dir)
    except (ContractError, OSError, ValueError) as exc:
        print(f"workbench-product-contract: FAIL: {exc}", file=sys.stderr)
        return 1
    suffix = " ship=verified" if args.ship_dir is not None else ""
    print(f"workbench-product-contract: PASS workflows=6 release=false{suffix}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
