#!/usr/bin/env python3
"""Validate the versioned lisp65 current-dialect inventory."""

from __future__ import annotations

import argparse
from copy import deepcopy
from functools import lru_cache
import hashlib
import importlib
import io
import json
from pathlib import Path, PurePosixPath
import subprocess
import sys
import tarfile
import tempfile
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST_TOOLS = ROOT / "tools" / "host-lisp"
DEFAULT_CONTRACT = ROOT / "config" / "dialect-contract.json"
DEFAULT_SELECTION = ROOT / "config" / "dialect-profile-selection.json"
FORMAT = "lisp65-dialect-contract-v1"
ROLES = ("core", "workbench", "library", "internal", "removed")
DELIVERIES = ("bank0-native", "bank5-preload", "disk-on-demand", "build-only")
ROOT_KEYS = {
    "format",
    "version",
    "status",
    "vocabularies",
    "policy",
    "current_surfaces",
    "proposed_changes",
    "removed_public_names",
}
SURFACE_KEYS = {
    "id",
    "status",
    "kind",
    "public_role",
    "internal_role",
    "delivery",
    "suite_manifest",
    "application_descriptor",
    "generated_manifest",
    "binding",
    "sources",
    "public_names",
    "internal_inventory",
    "private_inline_inventory",
    "private_inline_delivery",
}
INVENTORY_KEYS = {"count", "sha256"}
PROPOSAL_KEYS = {"id", "status", "role", "delivery", "names"}


class DialectContractError(RuntimeError):
    pass


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DialectContractError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load_json(path: Path, label: str) -> Any:
    try:
        if path.is_symlink() or not path.is_file():
            raise DialectContractError(f"{label} must be a regular non-symlink file: {path}")
        return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_strict_object)
    except DialectContractError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise DialectContractError(f"cannot read {label} {path}: {exc}") from exc


def _exact_keys(value: Any, expected: set[str], label: str) -> None:
    if not isinstance(value, dict):
        raise DialectContractError(f"{label} must be an object")
    missing = sorted(expected - set(value))
    unknown = sorted(set(value) - expected)
    if missing or unknown:
        details = []
        if missing:
            details.append("missing " + ", ".join(missing))
        if unknown:
            details.append("unknown " + ", ".join(unknown))
        raise DialectContractError(f"{label} has " + "; ".join(details))


def _canonical_path(value: Any, label: str, *, nullable: bool = False) -> str | None:
    if value is None and nullable:
        return None
    if not isinstance(value, str) or not value:
        raise DialectContractError(f"{label} must be a non-empty path string")
    path = PurePosixPath(value)
    if path.is_absolute() or value != path.as_posix() or ".." in path.parts:
        raise DialectContractError(f"{label} is not a canonical repository path: {value!r}")
    return value


def _name_list(value: Any, label: str) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
        raise DialectContractError(f"{label} must be a list of non-empty strings")
    if value != sorted(value) or len(value) != len(set(value)):
        raise DialectContractError(f"{label} must be sorted and duplicate-free")
    return value


def _inventory(names: list[str]) -> dict[str, Any]:
    payload = "".join(name + "\n" for name in sorted(names)).encode("utf-8")
    return {"count": len(names), "sha256": hashlib.sha256(payload).hexdigest()}


def _validate_inventory(value: Any, names: list[str], label: str) -> None:
    _exact_keys(value, INVENTORY_KEYS, label)
    expected = _inventory(names)
    if value != expected:
        raise DialectContractError(
            f"{label} drift: expected count={expected['count']} sha256={expected['sha256']}"
        )


def validate_schema(contract: Any) -> None:
    _exact_keys(contract, ROOT_KEYS, "contract")
    if contract["format"] != FORMAT or contract["version"] != 1:
        raise DialectContractError(f"contract must use {FORMAT} version 1")
    if contract["status"] != "current":
        raise DialectContractError("contract status must be current")
    vocabularies = contract["vocabularies"]
    _exact_keys(vocabularies, {"roles", "deliveries"}, "vocabularies")
    if vocabularies["roles"] != list(ROLES):
        raise DialectContractError("role vocabulary or ordering drift")
    if vocabularies["deliveries"] != list(DELIVERIES):
        raise DialectContractError("delivery vocabulary or ordering drift")
    policy = contract["policy"]
    _exact_keys(
        policy,
        {"public_name_removal", "implicit_internal_prefix", "proposals_affect_current"},
        "policy",
    )
    if policy != {
        "public_name_removal": "forbidden-in-v1",
        "implicit_internal_prefix": "%",
        "proposals_affect_current": False,
    }:
        raise DialectContractError("v1 policy drift")
    if contract["removed_public_names"] != []:
        raise DialectContractError("v1 must not remove public names")

    surfaces = contract["current_surfaces"]
    if not isinstance(surfaces, list) or not surfaces:
        raise DialectContractError("current_surfaces must be a non-empty list")
    ids: set[str] = set()
    for index, surface in enumerate(surfaces):
        label = f"current_surfaces[{index}]"
        _exact_keys(surface, SURFACE_KEYS, label)
        if not isinstance(surface["id"], str) or not surface["id"]:
            raise DialectContractError(f"{label}.id must be a non-empty string")
        if surface["id"] in ids:
            raise DialectContractError(f"duplicate current surface id: {surface['id']}")
        ids.add(surface["id"])
        if surface["status"] != "current":
            raise DialectContractError(f"{label}.status must be current")
        if surface["kind"] not in ("native-primitives", "bytecode-suite"):
            raise DialectContractError(f"{label}.kind is unsupported")
        if surface["public_role"] not in ROLES or surface["public_role"] in ("internal", "removed"):
            raise DialectContractError(f"{label}.public_role is not public")
        if surface["internal_role"] != "internal":
            raise DialectContractError(f"{label}.internal_role must be internal")
        if surface["delivery"] not in DELIVERIES or surface["delivery"] == "build-only":
            raise DialectContractError(f"{label}.delivery is not a runtime delivery")
        _canonical_path(surface["suite_manifest"], f"{label}.suite_manifest", nullable=True)
        _canonical_path(
            surface["application_descriptor"], f"{label}.application_descriptor", nullable=True
        )
        _canonical_path(surface["generated_manifest"], f"{label}.generated_manifest", nullable=True)
        if not isinstance(surface["sources"], list) or not surface["sources"]:
            raise DialectContractError(f"{label}.sources must be a non-empty list")
        for number, source in enumerate(surface["sources"]):
            _canonical_path(source, f"{label}.sources[{number}]")
        if surface["sources"] != sorted(set(surface["sources"])):
            raise DialectContractError(f"{label}.sources must be sorted and duplicate-free")
        public = _name_list(surface["public_names"], f"{label}.public_names")
        if not public:
            raise DialectContractError(f"{label} must expose at least one public name")
        _exact_keys(surface["internal_inventory"], INVENTORY_KEYS, f"{label}.internal_inventory")
        _exact_keys(
            surface["private_inline_inventory"],
            INVENTORY_KEYS,
            f"{label}.private_inline_inventory",
        )
        if surface["private_inline_delivery"] != "build-only":
            raise DialectContractError(f"{label}.private_inline_delivery must be build-only")
        binding = surface["binding"]
        if surface["kind"] == "native-primitives":
            _exact_keys(binding, {"bindings"}, f"{label}.binding")
            if not isinstance(binding["bindings"], list) or not binding["bindings"]:
                raise DialectContractError(f"{label}.binding.bindings must be non-empty")
            for number, item in enumerate(binding["bindings"]):
                _exact_keys(item, {"module", "attribute"}, f"{label}.binding.bindings[{number}]")
                if not all(isinstance(item[key], str) and item[key] for key in item):
                    raise DialectContractError(f"{label}.binding.bindings[{number}] is invalid")
            if surface["suite_manifest"] is not None or surface["generated_manifest"] is not None:
                raise DialectContractError(f"{label} native surface cannot bind suite artifacts")
        elif binding is not None:
            raise DialectContractError(f"{label} bytecode surface binding must be null")

    proposals = contract["proposed_changes"]
    if not isinstance(proposals, list):
        raise DialectContractError("proposed_changes must be a list")
    proposal_ids: set[str] = set()
    for index, proposal in enumerate(proposals):
        label = f"proposed_changes[{index}]"
        _exact_keys(proposal, PROPOSAL_KEYS, label)
        if proposal["status"] != "proposed":
            raise DialectContractError(f"{label}.status must be proposed")
        if proposal["role"] not in ROLES or proposal["delivery"] not in DELIVERIES:
            raise DialectContractError(f"{label} uses an unsupported axis value")
        if not isinstance(proposal["id"], str) or not proposal["id"] or proposal["id"] in proposal_ids:
            raise DialectContractError(f"{label}.id must be unique and non-empty")
        proposal_ids.add(proposal["id"])
        _name_list(proposal["names"], f"{label}.names")


def _load_suite(surface: dict[str, Any]) -> tuple[dict[str, Any], list[str], list[str]]:
    if str(HOST_TOOLS) not in sys.path:
        sys.path.insert(0, str(HOST_TOOLS))
    try:
        stdlib = importlib.import_module("bytecode_p0_stdlib")
        suite = stdlib._read_suite(str(ROOT / surface["suite_manifest"]))
        functions, _forms, _macros, _inliner = stdlib._suite_functions_and_forms(suite)
    except Exception as exc:
        raise DialectContractError(
            f"cannot resolve suite {surface['suite_manifest']}: {exc}"
        ) from exc
    return suite, sorted(functions), sorted(suite.get("private_inline_functions", []))


def _validate_native(surface: dict[str, Any], label: str) -> None:
    binding = surface["binding"]
    if str(HOST_TOOLS) not in sys.path:
        sys.path.insert(0, str(HOST_TOOLS))
    try:
        names: set[str] = set()
        for item in binding["bindings"]:
            module = importlib.import_module(item["module"])
            value = getattr(module, item["attribute"])
            candidates = list(value.keys() if isinstance(value, dict) else value)
            if any(not isinstance(name, str) or not name for name in candidates):
                raise DialectContractError(f"{label} native binding contains a non-name")
            names.update(candidates)
    except (ImportError, AttributeError) as exc:
        raise DialectContractError(f"{label} cannot load native binding: {exc}") from exc
    names = sorted(names)
    public = sorted(name for name in names if not name.startswith("%"))
    internal = sorted(set(names) - set(public))
    if surface["public_names"] != public:
        raise DialectContractError(f"{label}.public_names drift from native binding")
    _validate_inventory(surface["internal_inventory"], internal, f"{label}.internal_inventory")
    _validate_inventory(surface["private_inline_inventory"], [], f"{label}.private_inline_inventory")


def _validate_suite(surface: dict[str, Any], label: str) -> None:
    suite, functions, private = _load_suite(surface)
    resolved_sources = sorted(suite.get("sources", []))
    if surface["sources"] != resolved_sources:
        raise DialectContractError(f"{label}.sources drift from resolved suite")
    descriptor_path = surface["application_descriptor"]
    if descriptor_path is None:
        public = sorted(name for name in functions if not name.startswith("%"))
    else:
        descriptor = load_json(ROOT / descriptor_path, f"{label} application descriptor")
        if descriptor.get("suite") != surface["suite_manifest"]:
            raise DialectContractError(f"{label} descriptor suite binding drift")
        public = _name_list(descriptor.get("exports"), f"{label} descriptor exports")
        if not set(public) <= set(functions):
            raise DialectContractError(f"{label} descriptor exports missing from suite")
    internal = sorted(set(functions) - set(public))
    if surface["public_names"] != public:
        raise DialectContractError(f"{label}.public_names drift from current suite")
    _validate_inventory(surface["internal_inventory"], internal, f"{label}.internal_inventory")
    _validate_inventory(
        surface["private_inline_inventory"], private, f"{label}.private_inline_inventory"
    )


def validate_bindings(contract: dict[str, Any]) -> dict[str, int]:
    totals = {"surfaces": 0, "public": 0, "internal": 0, "private": 0}
    for index, surface in enumerate(contract["current_surfaces"]):
        label = f"current_surfaces[{index}]/{surface['id']}"
        for source in surface["sources"]:
            path = ROOT / source
            if path.is_symlink() or not path.is_file():
                raise DialectContractError(f"{label} source missing or not regular: {source}")
        if surface["kind"] == "native-primitives":
            _validate_native(surface, label)
        else:
            _validate_suite(surface, label)
        totals["surfaces"] += 1
        totals["public"] += len(surface["public_names"])
        totals["internal"] += surface["internal_inventory"]["count"]
        totals["private"] += surface["private_inline_inventory"]["count"]
    return totals


def _declared_totals(contract: dict[str, Any]) -> dict[str, int]:
    return {
        "surfaces": len(contract["current_surfaces"]),
        "public": sum(len(surface["public_names"]) for surface in contract["current_surfaces"]),
        "internal": sum(surface["internal_inventory"]["count"] for surface in contract["current_surfaces"]),
        "private": sum(surface["private_inline_inventory"]["count"] for surface in contract["current_surfaces"]),
    }


@lru_cache(maxsize=8)
def validate_frozen_commit(commit: str, repository_path: str, expected_sha256: str) -> dict[str, int]:
    if (
        len(commit) != 40 or any(character not in "0123456789abcdef" for character in commit)
        or len(expected_sha256) != 64
        or any(character not in "0123456789abcdef" for character in expected_sha256)
    ):
        raise DialectContractError("frozen dialect snapshot identity is invalid")
    path = PurePosixPath(repository_path)
    if path.is_absolute() or path.as_posix() != repository_path or ".." in path.parts:
        raise DialectContractError("frozen dialect contract path is invalid")
    blob = subprocess.run(
        ["git", "show", f"{commit}:{repository_path}"], cwd=ROOT,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    if blob.returncode or hashlib.sha256(blob.stdout).hexdigest() != expected_sha256:
        raise DialectContractError("frozen dialect contract blob binding drift")
    archive = subprocess.run(
        ["git", "archive", "--format=tar", commit], cwd=ROOT,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    if archive.returncode:
        raise DialectContractError("cannot materialize frozen dialect source snapshot")
    with tempfile.TemporaryDirectory(prefix="lisp65-frozen-dialect-") as raw:
        snapshot = Path(raw)
        with tarfile.open(fileobj=io.BytesIO(archive.stdout), mode="r:") as bundle:
            for member in bundle.getmembers():
                member_path = PurePosixPath(member.name)
                if member_path.is_absolute() or ".." in member_path.parts:
                    raise DialectContractError("frozen dialect archive contains an unsafe path")
            bundle.extractall(snapshot)
        validator = snapshot / "tools" / "host-lisp" / "dialect_contract.py"
        validator.write_bytes(Path(__file__).read_bytes())
        contract_path = snapshot / repository_path
        result = subprocess.run(
            [sys.executable, str(validator), str(contract_path), "--live-bindings"],
            cwd=snapshot, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        )
        if result.returncode:
            tail = "\n".join(result.stdout.splitlines()[-60:])
            raise DialectContractError(f"frozen dialect snapshot validation failed:\n{tail}")
    frozen = json.loads(blob.stdout)
    validate_schema(frozen)
    return _declared_totals(frozen)


def _default_frozen_binding() -> tuple[str, str, str]:
    selection = load_json(DEFAULT_SELECTION, "dialect profile selection")
    profiles = selection.get("profiles")
    if not isinstance(profiles, list):
        raise DialectContractError("dialect profile selection lacks profiles")
    profile = next(
        (item for item in profiles if isinstance(item, dict) and item.get("id") == "dialect-v1"),
        None,
    )
    if not isinstance(profile, dict) or profile.get("state") != "frozen-evidence":
        raise DialectContractError("dialect-v1 frozen profile binding is missing")
    if profile.get("contract") != DEFAULT_CONTRACT.relative_to(ROOT).as_posix():
        raise DialectContractError("dialect-v1 frozen contract path drift")
    return profile["source_commit"], profile["contract"], profile["contract_sha256"]


def _expect_failure(label: str, action: Callable[[], None]) -> None:
    try:
        action()
    except DialectContractError:
        return
    raise DialectContractError(f"selftest mutation was accepted: {label}")


def run_selftest() -> None:
    base = load_json(DEFAULT_CONTRACT, "dialect contract")
    validate_schema(base)
    validate_frozen_commit(*_default_frozen_binding())

    def mutation(change: Callable[[dict[str, Any]], None]) -> Callable[[], None]:
        def check() -> None:
            value = deepcopy(base)
            change(value)
            validate_schema(value)

        return check

    _expect_failure("format", mutation(lambda value: value.update(format="v2")))
    _expect_failure("role vocabulary", mutation(lambda value: value["vocabularies"]["roles"].reverse()))
    _expect_failure("public removal", mutation(lambda value: value["removed_public_names"].append("car")))
    _expect_failure(
        "duplicate surface",
        mutation(lambda value: value["current_surfaces"].append(deepcopy(value["current_surfaces"][0]))),
    )
    _expect_failure("current status", mutation(lambda value: value["current_surfaces"][0].update(status="proposed")))
    _expect_failure("public role", mutation(lambda value: value["current_surfaces"][0].update(public_role="internal")))
    _expect_failure("delivery", mutation(lambda value: value["current_surfaces"][0].update(delivery="rom")))
    _expect_failure("source order", mutation(lambda value: value["current_surfaces"][1]["sources"].reverse()))
    _expect_failure("public order", mutation(lambda value: value["current_surfaces"][1]["public_names"].reverse()))
    _expect_failure("inventory field", mutation(lambda value: value["current_surfaces"][0]["internal_inventory"].update(extra=1)))
    _expect_failure(
        "proposal status",
        mutation(
            lambda value: value["proposed_changes"].append(
                {"id": "x", "status": "current", "role": "internal", "delivery": "build-only", "names": []}
            )
        ),
    )

    def binding_mutation(change: Callable[[dict[str, Any]], None]) -> Callable[[], None]:
        def check() -> None:
            value = deepcopy(base)
            change(value)
            validate_schema(value)
            validate_bindings(value)

        return check

    _expect_failure(
        "public surface drift",
        binding_mutation(lambda value: value["current_surfaces"][1]["public_names"].pop()),
    )
    _expect_failure(
        "internal inventory drift",
        binding_mutation(
            lambda value: value["current_surfaces"][4]["internal_inventory"].update(
                sha256="0" * 64
            )
        ),
    )
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "duplicate.json"
        path.write_text('{"format":"a","format":"b"}\n', encoding="utf-8")
        _expect_failure("duplicate JSON key", lambda: load_json(path, "duplicate fixture"))


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("contract", nargs="?", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--live-bindings", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    try:
        if args.selftest:
            run_selftest()
            print("dialect-contract: SELFTEST PASS mutations=14")
            return 0
        path = args.contract if args.contract.is_absolute() else ROOT / args.contract
        contract = load_json(path, "dialect contract")
        validate_schema(contract)
        if args.live_bindings or path.resolve() != DEFAULT_CONTRACT.resolve():
            totals = validate_bindings(contract)
            mode = "live"
        else:
            totals = validate_frozen_commit(*_default_frozen_binding())
            mode = "frozen-snapshot"
    except DialectContractError as exc:
        print(f"dialect-contract: FAIL: {exc}", file=sys.stderr)
        return 1
    print(
        "dialect-contract: PASS mode={mode} surfaces={surfaces} public={public} "
        "internal={internal} private={private}".format(
            mode=mode, **totals
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
