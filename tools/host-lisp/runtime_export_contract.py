#!/usr/bin/env python3
"""Validate the planning and application contracts for Runtime Export v1."""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "host-lisp"))

import l65m_contract as L65M  # noqa: E402


CONTRACT_FORMAT = "lisp65-runtime-export-contract-v2"
APP_FORMAT = "lisp65-runtime-app-v1"
SUITE_FORMAT = "lisp65-bytecode-p0-disk-lib-suite-v1"
ARTIFACT_FORMAT = "lisp65-bytecode-p0-disk-lib-artifacts-v1"
DEFAULT_CONTRACT = ROOT / "config" / "runtime-export-contract.json"
ROOT_KEYS = {
    "format", "status", "claims", "profile", "application", "package",
    "capabilities", "budgets", "gates", "open_gaps",
}
CLAIM_KEYS = {"interactive_product", "language_semantics", "release", "runtime_export"}
PROFILE_KEYS = {"id", "layout", "entry_abi", "application_preload", "runtime_disk_loader"}
APPLICATION_KEYS = {
    "descriptor", "descriptor_format", "artifact_format", "bytecode_abi", "l65m_version",
}
PACKAGE_KEYS = {"format", "files"}
CAPABILITY_KEYS = {"required", "forbidden_native_symbols"}
BUDGET_KEYS = {
    "min_boot_stack_gap", "min_post_boot_reserve", "post_boot_reserve_target",
    "max_prg_file_end", "min_symbol_headroom",
}
GATE_KEYS = {"G0", "G1", "G2", "G4", "G5"}
APP_KEYS = {
    "format", "status", "name", "suite", "entry", "exports", "provides",
    "requires", "library_closure", "native_capabilities", "expected_result",
}
ENTRY_KEYS = {"name", "arity"}
EXPECTED_PACKAGE_FILES = [
    "manifest.json", "resolved-profile.txt", "runtime-app.json", "runtime-app.l65m",
    "runtime-preload.bin", "runtime.prg", "toolchain-report.txt",
]


class ContractError(RuntimeError):
    pass


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise ContractError("duplicate JSON key: %s" % key)
        out[key] = value
    return out


def _load(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_strict_object)
    except ContractError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ContractError("cannot read %s %s: %s" % (label, path, exc)) from exc
    if not isinstance(value, dict):
        raise ContractError("%s must be an object" % label)
    return value


def _exact(value: Any, keys: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ContractError("%s must be an object" % label)
    missing = sorted(keys - set(value))
    extra = sorted(set(value) - keys)
    if missing or extra:
        raise ContractError(
            "%s keys differ: missing=%s extra=%s"
            % (label, ",".join(missing) or "-", ",".join(extra) or "-")
        )
    return value


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ContractError("%s must be a non-empty string" % label)
    return value


def _strings(value: Any, label: str, *, nonempty: bool = True) -> list[str]:
    if not isinstance(value, list) or (nonempty and not value):
        raise ContractError("%s must be %sa list" % (label, "a non-empty " if nonempty else ""))
    out = [_text(item, "%s[%d]" % (label, index)) for index, item in enumerate(value)]
    if len(out) != len(set(out)):
        raise ContractError("%s contains duplicates" % label)
    return out


def _integer(value: Any, label: str, minimum: int = 0) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
        raise ContractError("%s must be an integer >= %d" % (label, minimum))
    return value


def _repo_path(value: str, label: str) -> Path:
    path = (ROOT / value).resolve()
    try:
        path.relative_to(ROOT)
    except ValueError as exc:
        raise ContractError("%s escapes the repository" % label) from exc
    if not path.is_file():
        raise ContractError("%s does not exist: %s" % (label, value))
    return path


def validate(contract: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    _exact(contract, ROOT_KEYS, "contract")
    if contract["format"] != CONTRACT_FORMAT or contract["status"] != "candidate":
        raise ContractError("contract format/status must describe a v1 candidate")

    claims = _exact(contract["claims"], CLAIM_KEYS, "contract.claims")
    if claims != {
        "interactive_product": False,
        "language_semantics": False,
        "release": False,
        "runtime_export": True,
    }:
        raise ContractError("candidate claims differ from the approved AP7 boundary")

    profile = _exact(contract["profile"], PROFILE_KEYS, "contract.profile")
    expected_profile = {
        "id": "runtime-export-v2-candidate",
        "layout": "inline-boot-overlay",
        "entry_abi": "named-zero-argument-p0",
        "application_preload": "bank5-build-bound",
        "runtime_disk_loader": False,
    }
    if profile != expected_profile:
        raise ContractError("profile differs from the approved AP7 boundary")

    application = _exact(contract["application"], APPLICATION_KEYS, "contract.application")
    if application["descriptor_format"] != APP_FORMAT:
        raise ContractError("application descriptor format mismatch")
    if application["artifact_format"] != ARTIFACT_FORMAT:
        raise ContractError("application artifact format mismatch")
    if application["bytecode_abi"] != "P0" or application["l65m_version"] != 1:
        raise ContractError("application ABI must be P0/L65M-v1")
    app_path = _repo_path(_text(application["descriptor"], "application.descriptor"), "app descriptor")
    app = _load(app_path, "app descriptor")

    package = _exact(contract["package"], PACKAGE_KEYS, "contract.package")
    if package["format"] != "lisp65-runtime-export-ship-v2":
        raise ContractError("package format mismatch")
    if _strings(package["files"], "package.files") != EXPECTED_PACKAGE_FILES:
        raise ContractError("package file set/order differs from Runtime Export v1")

    capabilities = _exact(contract["capabilities"], CAPABILITY_KEYS, "contract.capabilities")
    required_capabilities = _strings(capabilities["required"], "capabilities.required")
    _strings(capabilities["forbidden_native_symbols"], "capabilities.forbidden_native_symbols")

    budgets = _exact(contract["budgets"], BUDGET_KEYS, "contract.budgets")
    for key in BUDGET_KEYS:
        _integer(budgets[key], "budgets.%s" % key, 1)
    if budgets["post_boot_reserve_target"] < budgets["min_post_boot_reserve"]:
        raise ContractError("post-boot reserve target is below its hard minimum")

    gates = _exact(contract["gates"], GATE_KEYS, "contract.gates")
    for gate in sorted(GATE_KEYS):
        _strings(gates[gate], "gates.%s" % gate)
    if _strings(contract["open_gaps"], "contract.open_gaps") != ["cold-boot-hardware"]:
        raise ContractError("contract open gaps must name only cold-boot-hardware")

    _exact(app, APP_KEYS, "app")
    if app["format"] != APP_FORMAT or app["status"] != "candidate":
        raise ContractError("app format/status must describe a v1 candidate")
    _text(app["name"], "app.name")
    suite_path = _repo_path(_text(app["suite"], "app.suite"), "app suite")
    entry = _exact(app["entry"], ENTRY_KEYS, "app.entry")
    entry_name = _text(entry["name"], "app.entry.name")
    if _integer(entry["arity"], "app.entry.arity") != 0:
        raise ContractError("Runtime Export v1 entry arity must be zero")
    exports = _strings(app["exports"], "app.exports")
    if entry_name not in exports:
        raise ContractError("runtime entry must be public in app.exports")
    provides = _strings(app["provides"], "app.provides")
    requires = _strings(app["requires"], "app.requires")
    if "core" not in requires or set(provides) & set(requires):
        raise ContractError("app dependency closure must require core without overlap")
    _strings(app["library_closure"], "app.library_closure", nonempty=False)
    app_capabilities = _strings(app["native_capabilities"], "app.native_capabilities")
    if app_capabilities != required_capabilities:
        raise ContractError("app capabilities differ from the export profile")
    _text(app["expected_result"], "app.expected_result")

    suite = _load(suite_path, "app suite")
    if suite.get("format") != SUITE_FORMAT:
        raise ContractError("app suite must use the disk-lib suite format")
    if suite.get("name") != app["name"]:
        raise ContractError("app and suite names differ")
    if suite.get("provides") != provides or suite.get("requires") != requires:
        raise ContractError("app dependency metadata differs from its suite")
    functions = _strings(suite.get("functions"), "suite.functions")
    if entry_name not in functions or not set(exports).issubset(functions):
        raise ContractError("app entry/exports are missing from the suite")
    return app, suite


def validate_artifact(
    contract: dict[str, Any], app: dict[str, Any], artifact: Path, manifest_path: Path
) -> L65M.Summary:
    try:
        image = artifact.read_bytes()
        summary = L65M.validate_image(image)
    except (OSError, L65M.ContractError) as exc:
        raise ContractError("application L65M failed preflight: %s" % exc) from exc
    manifest = _load(manifest_path, "application artifact manifest")
    if manifest.get("format") != contract["application"]["artifact_format"]:
        raise ContractError("application artifact manifest format mismatch")
    if manifest.get("artifact_role") != "disk-lib" or manifest.get("name") != app["name"]:
        raise ContractError("application artifact identity mismatch")
    if manifest.get("provides") != app["provides"] or manifest.get("requires") != app["requires"]:
        raise ContractError("application artifact dependency metadata mismatch")
    entry_name = app["entry"]["name"]
    if entry_name not in summary.entry_names:
        raise ContractError("application L65M is missing its runtime entry")
    entries = manifest.get("entries")
    matches = [item for item in entries or [] if isinstance(item, dict) and item.get("name") == entry_name]
    if len(matches) != 1 or matches[0].get("kind") != "function":
        raise ContractError("application manifest needs exactly one function entry")
    offset = 4 + _integer(matches[0].get("blob_offset"), "entry.blob_offset")
    if offset + 2 > len(image) or image[offset] != 0xB5 or image[offset + 1] != 0:
        raise ContractError("application runtime entry is not zero-argument P0 bytecode")
    return summary


def selftest() -> int:
    contract = _load(DEFAULT_CONTRACT, "runtime export contract")
    validate(contract)
    mutations: list[tuple[str, Any, str]] = [
        ("claim", lambda c: c["claims"].update({"release": True}), "claims"),
        ("layout", lambda c: c["profile"].update({"layout": "dynamic-d81"}), "profile"),
        ("disk-loader", lambda c: c["profile"].update({"runtime_disk_loader": True}), "profile"),
        ("package", lambda c: c["package"]["files"].pop(), "file set"),
        ("abi", lambda c: c["application"].update({"l65m_version": 2}), "P0/L65M"),
        ("budget", lambda c: c["budgets"].update({"post_boot_reserve_target": 4096}), "hard minimum"),
        ("gap", lambda c: c.update({"open_gaps": []}), "non-empty"),
    ]
    for label, mutate, needle in mutations:
        changed = copy.deepcopy(contract)
        mutate(changed)
        try:
            validate(changed)
        except ContractError as exc:
            if needle not in str(exc):
                raise ContractError("selftest %s failed for wrong reason: %s" % (label, exc)) from exc
        else:
            raise ContractError("selftest mutation passed: %s" % label)
    print("runtime-export-contract selftest: PASS mutations=%d" % len(mutations))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("contract", nargs="?", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--artifact", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.selftest:
            return selftest()
        contract = _load(args.contract, "runtime export contract")
        app, _suite = validate(contract)
        if (args.artifact is None) != (args.manifest is None):
            raise ContractError("--artifact and --manifest must be used together")
        summary = None
        if args.artifact is not None and args.manifest is not None:
            summary = validate_artifact(contract, app, args.artifact, args.manifest)
    except (ContractError, OSError, ValueError) as exc:
        print("runtime-export-contract: FAIL: %s" % exc, file=sys.stderr)
        return 1
    suffix = ""
    if summary is not None:
        suffix = " entries=%d bytes=%d" % (len(summary.entry_names), summary.bytes)
    print("runtime-export-contract: PASS status=candidate claims=runtime-export-only%s" % suffix)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
