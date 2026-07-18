#!/usr/bin/env python3
"""Validate the permanent P0 opcode and Prim-ID identity ledger."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST_TOOLS = ROOT / "tools" / "host-lisp"
if str(HOST_TOOLS) not in sys.path:
    sys.path.insert(0, str(HOST_TOOLS))

import bytecode_p0 as B  # noqa: E402
import bytecode_p0_compiler as C  # noqa: E402
import bytecode_p0_drift_check as D  # noqa: E402
import v2_native_function_registry as NATIVE_FUNCTIONS  # noqa: E402


DEFAULT_LEDGER = ROOT / "config" / "bytecode-abi-ledger.json"
FORMAT = "lisp65-bytecode-abi-ledger-v1"
TOP_KEYS = {
    "format", "version", "id_bits", "profile_order", "policies", "diagnostics",
    "staging_prim_dispatch", "prim_retirements", "opcode_identities",
    "prim_identities", "profiles",
}
POLICIES = {
    "id_reuse": "forbidden",
    "canonical_name_change": "forbidden",
    "tombstone_reactivation": "forbidden",
    "tombstone_operand_change": "forbidden",
    "decoder_name_retention": "required",
    "disassembler_name_retention": "required",
}
DIAGNOSTICS = {
    "opcode_active": "abi-opcode-active",
    "opcode_tombstone": "abi-opcode-tombstone",
    "opcode_reserved": "abi-opcode-reserved",
    "prim_active": "abi-prim-active",
    "prim_tombstone": "abi-prim-tombstone",
    "prim_reserved": "abi-prim-reserved",
}
OPERANDS = {"none", "s8", "u8", "idx", "rel8", "idx+u8", "pid+u8"}
FROZEN_V1_SHA256 = "30c585bb97fdd0e93d389104add98280ce40a8874ba1da19034fab4965bbfacd"
PRIM_RETIREMENTS = {
    26: {
        "canonical_name": "%string-slice",
        "receipt_id": "prim-26-string-slice",
        "source_commit": "69838e2afa71da34ec8cc24cff6c59713ce5d2be",
        "path": "tests/bytecode/dialect-v2/evidence/capability-carrier/abi-retirements/prim-26-string-slice.json",
        "sha256": "8ba68e6c57e01adc7f7e8ad6233bd3b6dd63ab32566b1daa1a780477b78aea74",
        "prior_abi_sha256": "b5d98dc62f07064f704bbc0f172f35270cfa6b5f4484e5933da77264b12e530d",
        "prior_closure_sha256": "bdef4cab9d965e9c7a366f92406c7c0e860f7d5082db267c9066f8a90256fff0",
        "call_count": 1,
    },
    27: {
        "canonical_name": "%string-concat-list",
        "receipt_id": "prim-27-string-concat-list",
        "source_commit": "69838e2afa71da34ec8cc24cff6c59713ce5d2be",
        "path": "tests/bytecode/dialect-v2/evidence/capability-carrier/abi-retirements/prim-27-string-concat-list.json",
        "sha256": "cc0f664a5eee68b79d2e5e01e9910c015517fcb2b3da03b922f7d02c92506c85",
        "prior_abi_sha256": "b5d98dc62f07064f704bbc0f172f35270cfa6b5f4484e5933da77264b12e530d",
        "prior_closure_sha256": "bdef4cab9d965e9c7a366f92406c7c0e860f7d5082db267c9066f8a90256fff0",
        "call_count": 1,
    },
    34: {
        "canonical_name": "%save-staged",
        "receipt_id": "prim-34-save-staged",
        "source_commit": "938a0ce3804b88c7fc67705be6b415fb940d8cc5",
        "path": "tests/bytecode/dialect-v2/evidence/capability-carrier/abi-retirements/prim-34-save-staged.json",
        "sha256": "0bfad9596a9b7e9f47e152d1a4016dd30a56f06a99eaf32af9737d5ac1359590",
        "prior_abi_sha256": "c6666500baa949e0410ae523d64a8b7810156d7c2a2ea0e9f016333d6ed8a27a",
        "prior_closure_sha256": "10a57261185b348fd91c1deab90065fd364ae9a9760327c68a67f72f2be63829",
        "call_count": 1,
    },
    40: {
        "canonical_name": "number->string",
        "receipt_id": "prim-40-number-to-string",
        "source_commit": "ca9cfb941a7db3374b7705fce1f1925e1e525643",
        "path": "tests/bytecode/dialect-v2/evidence/capability-carrier/abi-retirements/prim-40-number-to-string.json",
        "sha256": "4aaed2bafc2ed38f99d4fde415294733ad1d30884c6e68d4cf0c6b7c4215f81d",
        "prior_abi_sha256": "3328adfcadaa9a7342b85d3d9cd8082504f8ba1024ca8edb95b0beb57930f2d7",
        "prior_closure_sha256": "3b3734b1922fff8a737176d42e5bd6fa7945843f83ba186bc925383dc0a3a83a",
        "call_count": 4,
    },
}


class LedgerError(RuntimeError):
    pass


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise LedgerError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load_json(path: Path) -> dict[str, Any]:
    try:
        if path.is_symlink() or not path.is_file():
            raise LedgerError(f"ledger must be a regular non-symlink file: {path}")
        value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_strict_object)
    except LedgerError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise LedgerError(f"cannot read ledger {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise LedgerError("ledger must be an object")
    return value


def _exact(value: Any, keys: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise LedgerError(f"{label} must be an object")
    missing = sorted(keys - set(value))
    unknown = sorted(set(value) - keys)
    if missing or unknown:
        raise LedgerError(f"{label} keys drift: missing={missing} unknown={unknown}")
    return value


def _sorted_unique_ints(value: Any, label: str) -> list[int]:
    if not isinstance(value, list) or any(type(item) is not int for item in value):
        raise LedgerError(f"{label} must be an integer list")
    if value != sorted(set(value)) or any(item < 0 or item > 255 for item in value):
        raise LedgerError(f"{label} must be sorted, unique, and within 0..255")
    return value


def _ranges(value: Any, label: str) -> set[int]:
    if not isinstance(value, list):
        raise LedgerError(f"{label} must be a range list")
    expanded: set[int] = set()
    previous = -1
    for index, item in enumerate(value):
        if (
            not isinstance(item, list) or len(item) != 2
            or any(type(number) is not int for number in item)
        ):
            raise LedgerError(f"{label}[{index}] must be [start, end]")
        start, end = item
        if start < 0 or end > 255 or start > end or start <= previous:
            raise LedgerError(f"{label}[{index}] is invalid or out of order")
        current = set(range(start, end + 1))
        if expanded & current:
            raise LedgerError(f"{label}[{index}] overlaps a previous range")
        expanded.update(current)
        previous = end
    return expanded


def _identities(value: Any, opcode: bool) -> dict[int, tuple[str, str | None]]:
    label = "opcode_identities" if opcode else "prim_identities"
    keys = {"id", "canonical_name", "operand"} if opcode else {"id", "canonical_name"}
    if not isinstance(value, list) or not value:
        raise LedgerError(f"{label} must be a non-empty list")
    result: dict[int, tuple[str, str | None]] = {}
    order: list[int] = []
    names: set[str] = set()
    for index, raw in enumerate(value):
        item = _exact(raw, keys, f"{label}[{index}]")
        ident = item["id"]
        name = item["canonical_name"]
        operand = item.get("operand")
        if type(ident) is not int or not 0 <= ident <= 255:
            raise LedgerError(f"{label}[{index}].id is invalid")
        if not isinstance(name, str) or not name:
            raise LedgerError(f"{label}[{index}].canonical_name is invalid")
        if opcode and operand not in OPERANDS:
            raise LedgerError(f"{label}[{index}].operand is invalid")
        if ident in result or name in names:
            raise LedgerError(f"duplicate {label} id or canonical name: {ident}/{name}")
        result[ident] = (name, operand)
        order.append(ident)
        names.add(name)
    if order != sorted(order):
        raise LedgerError(f"{label} must be ordered by id")
    return result


def _space(value: Any, label: str, identities: set[int]) -> dict[str, set[int]]:
    item = _exact(value, {"active", "tombstone", "reserved_ranges"}, label)
    active = set(_sorted_unique_ints(item["active"], f"{label}.active"))
    tombstone = set(_sorted_unique_ints(item["tombstone"], f"{label}.tombstone"))
    reserved = _ranges(item["reserved_ranges"], f"{label}.reserved_ranges")
    if active & tombstone or active & reserved or tombstone & reserved:
        raise LedgerError(f"{label} states overlap")
    if active | tombstone | reserved != set(range(256)):
        raise LedgerError(f"{label} must partition the complete 8-bit space")
    if not active | tombstone <= identities:
        raise LedgerError(f"{label} uses an ID without a permanent identity")
    return {"active": active, "tombstone": tombstone, "reserved": reserved}


def _frozen_v1_hash(value: dict[str, Any]) -> str:
    profile = value["profiles"][0]
    opcode_ids = set(profile["opcodes"]["active"]) | set(profile["opcodes"]["tombstone"])
    prim_ids = set(profile["prim_ids"]["active"]) | set(profile["prim_ids"]["tombstone"])
    payload = {
        "opcode_identities": [
            item for item in value["opcode_identities"] if item["id"] in opcode_ids
        ],
        "prim_identities": [
            item for item in value["prim_identities"] if item["id"] in prim_ids
        ],
        "profile": profile,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _prim_retirements(value: Any, prim_ids: dict[int, tuple[str, str | None]]) -> dict[str, set[int]]:
    if not isinstance(value, list) or len(value) != len(PRIM_RETIREMENTS):
        raise LedgerError("Prim-ID retirement inventory drift")
    retired: set[int] = set()
    for index, item in enumerate(value):
        item = _exact(
            item,
            {"id", "canonical_name", "profile", "transition", "runtime", "reuse", "evidence"},
            f"prim_retirements[{index}]",
        )
        prim_id = item["id"]
        spec = PRIM_RETIREMENTS.get(prim_id)
        expected = {
            "id": prim_id,
            "canonical_name": None if spec is None else spec["canonical_name"],
            "profile": "dialect-v2",
            "transition": "active-to-tombstone",
            "runtime": "reject-bad-primitive",
            "reuse": "forbidden",
        }
        if (
            spec is None
            or prim_id in retired
            or {key: item[key] for key in expected} != expected
            or prim_ids.get(prim_id, (None, None))[0] != spec["canonical_name"]
        ):
            raise LedgerError(f"Prim-ID {prim_id} retirement identity/policy drift")
        evidence = _exact(
            item["evidence"], {"path", "sha256"}, f"prim_retirements[{index}].evidence"
        )
        if evidence != {"path": spec["path"], "sha256": spec["sha256"]}:
            raise LedgerError(f"Prim-ID {prim_id} retirement evidence binding drift")
        path = (ROOT / evidence["path"]).resolve()
        try:
            path.relative_to(ROOT.resolve())
        except ValueError as exc:
            raise LedgerError(f"Prim-ID {prim_id} retirement evidence escapes project root") from exc
        if path.is_symlink() or not path.is_file():
            raise LedgerError(f"Prim-ID {prim_id} retirement evidence is missing")
        if hashlib.sha256(path.read_bytes()).hexdigest() != evidence["sha256"]:
            raise LedgerError(f"Prim-ID {prim_id} retirement evidence SHA drift")
        receipt = load_json(path)
        receipt_expected = {
            "format": "lisp65-prim-id-retirement-evidence-v1",
            "version": 1,
            "id": spec["receipt_id"],
            "profile": "dialect-v2",
            "prim_id": prim_id,
            "canonical_name": spec["canonical_name"],
            "transition": "active-to-tombstone",
            "source_commit": spec["source_commit"],
        }
        if any(receipt.get(key) != expected_value for key, expected_value in receipt_expected.items()):
            raise LedgerError(f"Prim-ID {prim_id} retirement receipt identity drift")
        prior = receipt.get("prior_contracts")
        if not isinstance(prior, list) or prior[:2] != [
            {"path": "config/bytecode-abi-ledger.json", "sha256": spec["prior_abi_sha256"]},
            {"path": "config/v2-workbench-artifact-closure.json", "sha256": spec["prior_closure_sha256"]},
        ]:
            raise LedgerError(f"Prim-ID {prim_id} retirement prior-active binding drift")
        artifact = receipt.get("artifact_evidence")
        if (
            not isinstance(artifact, dict)
            or artifact.get("disassembly", {}).get("callprim_id") != prim_id
            or artifact.get("disassembly", {}).get("call_count") != spec["call_count"]
        ):
            raise LedgerError(f"Prim-ID {prim_id} retirement disassembly evidence drift")
        retired.add(prim_id)
    if retired != set(PRIM_RETIREMENTS):
        raise LedgerError("Prim-ID retirement set drift")
    return {"dialect-v2": retired}


def _c_name_id_table(text: str, table: str) -> dict[str, int]:
    match = re.search(
        r"\b" + re.escape(table) + r"\[\]\s*=\s*\{(.*?)\n\s*\};",
        text,
        re.S,
    )
    if not match:
        raise LedgerError(f"cannot resolve C table {table}")
    return {
        name: int(ident)
        for name, ident in re.findall(r'\{\s*"([^"]+)"\s*,\s*([0-9]+)\s*\}', match.group(1))
    }


def _lcc_pairs(text: str) -> list[tuple[str, int]]:
    return [
        (name, int(ident))
        for name, ident in re.findall(r"\(\(eq name '([^\s()]+)\)\s+([0-9]+)\)", text)
    ]


def _direct_c_callprims(text: str) -> list[tuple[int, int]]:
    return [
        (int(ident), int(argc))
        for ident, argc in re.findall(
            r"emit3\s*\(\s*OP_CALLPRIM\s*,\s*([0-9]+)\s*,\s*([0-9]+)\s*\)",
            text,
        )
    ]


def _direct_lcc_callprims(text: str) -> list[tuple[int, int]]:
    return [
        (int(ident), int(argc))
        for ident, argc in re.findall(
            r"'callprim\)\s+([0-9]+)\)\s+([0-9]+)\)",
            text,
        )
    ]


def classify_id(value: dict[str, Any], profile_id: str, kind: str, ident: int) -> dict[str, Any]:
    if kind not in {"opcode", "prim"} or type(ident) is not int or not 0 <= ident <= 255:
        raise LedgerError("classification requires opcode|prim and an 8-bit id")
    profile = next((item for item in value["profiles"] if item["id"] == profile_id), None)
    if profile is None:
        raise LedgerError(f"unknown ABI profile: {profile_id}")
    space_name = "opcodes" if kind == "opcode" else "prim_ids"
    space = profile[space_name]
    active = set(space["active"])
    tombstone = set(space["tombstone"])
    status = "active" if ident in active else "tombstone" if ident in tombstone else "reserved"
    identities = value["opcode_identities"] if kind == "opcode" else value["prim_identities"]
    identity = next((item for item in identities if item["id"] == ident), None)
    if status != "reserved" and identity is None:
        raise LedgerError(f"{profile_id} {kind} {ident} lacks an identity")
    diagnostic = value["diagnostics"][f"{kind}_{status}"]
    return {
        "id": ident,
        "status": status,
        "canonical_name": None if identity is None else identity["canonical_name"],
        "operand": None if kind == "prim" or identity is None else identity["operand"],
        "diagnostic": diagnostic,
    }


def require_active(value: dict[str, Any], profile_id: str, kind: str, ident: int) -> None:
    classification = classify_id(value, profile_id, kind, ident)
    if classification["status"] != "active":
        raise LedgerError(
            f"emitter rejected {profile_id} {kind} {ident}: {classification['diagnostic']}"
        )


def validate(
    value: dict[str, Any], *, check_mirrors: bool = True,
    require_staging_dispatch: bool = False,
) -> dict[str, int]:
    _exact(value, TOP_KEYS, "ledger")
    if value["format"] != FORMAT or value["version"] != 1 or value["id_bits"] != 8:
        raise LedgerError("ledger format/version/id_bits drift")
    if value["policies"] != POLICIES or value["diagnostics"] != DIAGNOSTICS:
        raise LedgerError("ledger policies or diagnostics drift")
    op_ids = _identities(value["opcode_identities"], True)
    prim_ids = _identities(value["prim_identities"], False)
    staging = _exact(
        value["staging_prim_dispatch"],
        {"profile", "first_id", "last_id", "retired_ids", "runtime_status", "required_gate"},
        "staging_prim_dispatch",
    )
    if staging != {
        "profile": "dialect-v2", "first_id": 30, "last_id": 56,
        "retired_ids": [34, 40],
        "runtime_status": "implemented",
        "required_gate": "bytecode-abi-ledger --require-staging-dispatch",
    }:
        raise LedgerError("staging Prim-ID dispatch contract drift")
    staging_ids = set(range(30, 57))
    retired_by_profile = _prim_retirements(value["prim_retirements"], prim_ids)
    staging_active_ids = staging_ids - set(staging["retired_ids"])
    if not staging_ids <= set(prim_ids):
        raise LedgerError("staging Prim-ID range lacks permanent identities")

    profiles = value["profiles"]
    order = value["profile_order"]
    if order != ["dialect-v1", "dialect-v2"]:
        raise LedgerError("profile_order must pin dialect-v1 then dialect-v2")
    if not isinstance(profiles, list) or len(profiles) != len(order):
        raise LedgerError("profiles must match profile_order")
    resolved: dict[str, dict[str, dict[str, set[int]]]] = {}
    for index, raw in enumerate(profiles):
        item = _exact(raw, {"id", "parent", "opcodes", "prim_ids"}, f"profiles[{index}]")
        if item["id"] != order[index]:
            raise LedgerError("profiles must follow profile_order")
        expected_parent = None if index == 0 else order[index - 1]
        if item["parent"] != expected_parent:
            raise LedgerError(f"profile {item['id']} parent drift")
        resolved[item["id"]] = {
            "opcodes": _space(item["opcodes"], f"profiles[{index}].opcodes", set(op_ids)),
            "prim_ids": _space(item["prim_ids"], f"profiles[{index}].prim_ids", set(prim_ids)),
        }
    if _frozen_v1_hash(value) != FROZEN_V1_SHA256:
        raise LedgerError("dialect-v1 ABI genesis snapshot drift")

    for child_id, parent_id in zip(order[1:], order[:-1]):
        for space in ("opcodes", "prim_ids"):
            parent = resolved[parent_id][space]
            child = resolved[child_id][space]
            if not parent["tombstone"] <= child["tombstone"]:
                raise LedgerError(f"{child_id} reactivates a {space} tombstone")
            if not parent["active"] <= child["active"] | child["tombstone"]:
                raise LedgerError(f"{child_id} retires a {space} id without a tombstone")
            if not child["active"] <= parent["active"] | parent["reserved"]:
                raise LedgerError(f"{child_id} uses an invalid {space} transition")
            direct_retirements = child["tombstone"] & parent["reserved"]
            allowed_retirements = retired_by_profile.get(child_id, set()) if space == "prim_ids" else set()
            if direct_retirements != allowed_retirements:
                raise LedgerError(f"{child_id} turns a reserved {space} id directly into a tombstone")

    if set().union(*(resolved[item]["opcodes"]["active"] | resolved[item]["opcodes"]["tombstone"] for item in order)) != set(op_ids):
        raise LedgerError("opcode identity is never introduced by a profile")
    if set().union(*(resolved[item]["prim_ids"]["active"] | resolved[item]["prim_ids"]["tombstone"] for item in order)) != set(prim_ids):
        raise LedgerError("Prim-ID identity is never introduced by a profile")

    if (
        not staging_active_ids <= resolved["dialect-v2"]["prim_ids"]["active"]
        or set(staging["retired_ids"]) != staging_ids & resolved["dialect-v2"]["prim_ids"]["tombstone"]
        or not staging_ids <= resolved["dialect-v1"]["prim_ids"]["reserved"]
    ):
        raise LedgerError("staging Prim-ID range profile allocation drift")
    if not check_mirrors:
        return {"opcodes": len(op_ids), "prim_ids": len(prim_ids), "profiles": len(profiles), "staging_pending": 0}

    doc_ops = D.parse_doc_ops(D.read_text(D.DOC_PATH))
    doc_prims = D.parse_doc_prims(D.read_text(D.DOC_PATH))
    doc_prims.update(D.parse_doc_prim_extensions(D.read_text(D.DOC_EXTENSION_PATH)))
    py_ops = {spec.code: (spec.mnemonic, spec.operand) for spec in B.OP_SPECS}
    py_prims = dict(B.PRIM_IDS)
    ledger_ops = {ident: (name, operand) for ident, (name, operand) in op_ids.items()}
    ledger_prims = {ident: name for ident, (name, _operand) in prim_ids.items()}
    if ledger_ops != py_ops or ledger_ops != doc_ops:
        raise LedgerError("opcode identities drift from bytecode ABI or Python decoder")
    if ledger_prims != py_prims or ledger_prims != doc_prims:
        raise LedgerError("Prim-ID identities drift from bytecode ABI or Python decoder")
    vm_h_ops = D.parse_vm_h_ops(D.read_text(D.VM_H_PATH))
    if vm_h_ops != {ident: name for ident, (name, _operand) in op_ids.items()}:
        raise LedgerError("src/vm.h opcode mirror drift")
    vm_c_text = D.read_text(D.VM_C_PATH)
    vm_cases = D.parse_vm_c_callprim_cases(vm_c_text, doc_prims)
    expected_runtime_ids = set(prim_ids)
    if set(vm_cases) != expected_runtime_ids:
        raise LedgerError("src/vm.c vm_callprim ID coverage drift")
    for ident, name in vm_cases.items():
        if name is not None and name != ledger_prims[ident]:
            raise LedgerError(f"src/vm.c vm_callprim name drift at Prim-ID {ident}")
    host_vm_cases = D.parse_python_callprim_cases(
        (ROOT / "tools" / "host-lisp" / "bytecode_p0.py").read_text(encoding="utf-8")
    )
    if host_vm_cases != set(prim_ids):
        raise LedgerError("bytecode_p0.py CALLPRIM ID coverage drift")
    compile_text = (ROOT / "src" / "compile.c").read_text(encoding="utf-8")
    compile_prims = _c_name_id_table(compile_text, "PRIMS")
    if "LISP65_V2_CALLPRIM_ACTIVE_ROWS" in compile_text:
        generated_registry = NATIVE_FUNCTIONS.load(NATIVE_FUNCTIONS.REGISTRY)
        generated_state = NATIVE_FUNCTIONS.validate(generated_registry, value)
        compile_prims.update(generated_state["compile_repl"])
    compiler_active_ids = (
        resolved["dialect-v1"]["prim_ids"]["active"]
        | set(generated_state["compile_repl"].values())
    )
    if compile_prims != {
        ledger_prims[ident]: ident for ident in compiler_active_ids
    }:
        raise LedgerError("src/compile.c PRIMS mirror drift")
    prim_by_name = {name: ident for ident, name in ledger_prims.items()}
    expected_v1_compiler_prims = {
        ledger_prims[ident]: ident
        for ident in resolved["dialect-v1"]["prim_ids"]["active"]
    }
    expected_v2_compiler_prims = {
        ledger_prims[ident]: ident
        for ident in resolved["dialect-v2"]["prim_ids"]["active"]
    }
    if C.PRIM_CALLS != expected_v1_compiler_prims:
        raise LedgerError("bytecode_p0_compiler.PRIM_CALLS v1 mirror drift")
    if getattr(C, "PRIM_CALLS_V2", None) != expected_v2_compiler_prims:
        raise LedgerError("bytecode_p0_compiler.PRIM_CALLS_V2 mirror drift")
    direct_callprims = _direct_c_callprims(compile_text)
    expected_direct_callprims = [
        (prim_by_name["set-symbol-value"], 2),
        (prim_by_name["symbol-value"], 1),
    ]
    if direct_callprims != expected_direct_callprims:
        raise LedgerError("src/compile.c direct CALLPRIM emissions drift")
    native_registry = NATIVE_FUNCTIONS.load(NATIVE_FUNCTIONS.REGISTRY)
    native_state = NATIVE_FUNCTIONS.validate(native_registry, value)
    native_callprims = {
        item["name"]: item["value"]
        for item in native_state["entries"] if item["kind"] == "callprim"
    }
    if any(ledger_prims.get(ident) != name for name, ident in native_callprims.items()):
        raise LedgerError("generated native dispatch contains a noncanonical Prim-ID")
    if B.INTERNAL_ONLY_PRIM_IDS & set(native_callprims.values()):
        raise LedgerError("generated native dispatch exposes an internal-only Prim-ID")
    vm_opcode_cases = set(re.findall(r"\bcase\s+OP_([A-Z0-9_]+)\s*:", vm_c_text))
    if not set(name for name, _operand in op_ids.values()) <= vm_opcode_cases:
        raise LedgerError("src/vm.c opcode switch coverage drift")
    compiler_opcode_names = set(re.findall(r"\bOP_([A-Z0-9_]+)\b", compile_text))
    if not compiler_opcode_names <= set(name for name, _operand in op_ids.values()):
        raise LedgerError("src/compile.c emits an opcode outside the ledger")
    lcc_text = (ROOT / "lib" / "lcc.lisp").read_text(encoding="utf-8")
    opcode_by_lower = {name.lower(): (ident, operand) for ident, (name, operand) in op_ids.items()}
    lcc_ops: dict[str, int] = {}
    lcc_prims: dict[str, int] = {}
    for name, ident in _lcc_pairs(lcc_text):
        if name in prim_by_name:
            if name in lcc_prims:
                raise LedgerError(f"lib/lcc.lisp duplicate Prim-ID mapping for {name}")
            lcc_prims[name] = ident
        elif name in opcode_by_lower:
            if name in lcc_ops:
                raise LedgerError(f"lib/lcc.lisp duplicate opcode mapping for {name}")
            lcc_ops[name] = ident
        else:
            raise LedgerError(f"lib/lcc.lisp contains unknown ABI mapping {name}/{ident}")
    implicit_lcc_opcodes = {"halt", "pusharg0", "pusharg1", "pusharg2"}
    expected_lcc_ops = {
        name: ident
        for name, (ident, _operand) in opcode_by_lower.items()
        if name not in implicit_lcc_opcodes
    }
    if lcc_ops != expected_lcc_ops:
        raise LedgerError("lib/lcc.lisp opcode mirror coverage drift")
    v1_prim_by_name = {
        ledger_prims[ident]: ident
        for ident in resolved["dialect-v1"]["prim_ids"]["active"]
    }
    if lcc_prims != v1_prim_by_name:
        raise LedgerError("lib/lcc.lisp frozen-v1 Prim-ID mirror coverage drift")
    lcc_v2_text = (ROOT / "lib" / "dialect-v2" / "lcc-profile.lisp").read_text(encoding="utf-8")
    v2_pairs = _lcc_pairs(lcc_v2_text)
    lcc_v2_prims = {} if re.search(r"\(defun\s+%lcc-prim\b", lcc_v2_text) else dict(lcc_prims)
    for name, ident in v2_pairs:
        if name not in prim_by_name:
            raise LedgerError(f"dialect-v2 LCC contains unknown Prim-ID mapping {name}/{ident}")
        lcc_v2_prims[name] = ident
    expected_v2_lcc_prims = native_state["compile_repl"]
    if lcc_v2_prims != expected_v2_lcc_prims:
        raise LedgerError("dialect-v2 LCC Prim-ID mirror coverage drift")
    expected_lcc_direct_callprims = [
        (prim_by_name["symbol-value"], 1),
        (prim_by_name["set-symbol-value"], 2),
    ]
    if _direct_lcc_callprims(lcc_text) != expected_lcc_direct_callprims:
        raise LedgerError("lib/lcc.lisp direct CALLPRIM emissions drift")
    for ident in resolved["dialect-v1"]["opcodes"]["active"]:
        require_active(value, "dialect-v1", "opcode", ident)
    for ident in compile_prims.values():
        profile_id = "dialect-v1" if ident in resolved["dialect-v1"]["prim_ids"]["active"] else "dialect-v2"
        require_active(value, profile_id, "prim", ident)
    if require_staging_dispatch and not staging_ids <= set(vm_cases) & host_vm_cases:
        raise LedgerError("staging Prim-ID dispatch 30..56 mirror coverage drift")
    return {"opcodes": len(op_ids), "prim_ids": len(prim_ids), "profiles": len(profiles), "staging_pending": 0}


def _expect_failure(label: str, action: Callable[[], None]) -> None:
    try:
        action()
    except LedgerError:
        return
    raise LedgerError(f"selftest mutation was accepted: {label}")


def _expect_exception(
    label: str, exception: type[BaseException], action: Callable[[], None]
) -> None:
    try:
        action()
    except exception:
        return
    raise LedgerError(f"selftest operation was not rejected: {label}")


def selftest() -> None:
    base = load_json(DEFAULT_LEDGER)
    validate(base, check_mirrors=False)
    v1_prims = base["profiles"][0]["prim_ids"]
    v2_prims = base["profiles"][1]["prim_ids"]
    if (
        v1_prims["active"] != list(range(23))
        or v1_prims["tombstone"]
        or v2_prims["active"] != [0, *range(3, 26), 28, 29, *range(30, 34), *range(35, 40), *range(41, 67)]
        or v2_prims["tombstone"] != [1, 2, 26, 27, 34, 40]
    ):
        raise LedgerError("pinned dialect-v1/v2 Prim-ID allocation drift")
    if any(B.prim_is_function_designator(pid, "dialect-v2", base) for pid in B.INTERNAL_ONLY_PRIM_IDS):
        raise LedgerError("internal v2 Prim-ID became a function designator")
    native_registry = NATIVE_FUNCTIONS.load(NATIVE_FUNCTIONS.REGISTRY)
    native_state = NATIVE_FUNCTIONS.validate(native_registry, base)
    expected_designators = {
        row["value"] for row in native_state["entries"] if row["kind"] == "callprim"
    }
    actual_designators = {
        pid for pid in v2_prims["active"]
        if B.prim_is_function_designator(pid, "dialect-v2", base)
    }
    if actual_designators != expected_designators:
        raise LedgerError("registry/function-designator classification drift")
    if any(B.prim_is_function_designator(pid, "dialect-v2", base) for pid in PRIM_RETIREMENTS):
        raise LedgerError("retired Prim-ID remained a function designator")
    validate(base, check_mirrors=True, require_staging_dispatch=True)
    if classify_id(base, "dialect-v1", "prim", 23)["status"] != "reserved":
        raise LedgerError("dialect-v1 sees a v2-only Prim-ID as allocated")
    require_active(base, "dialect-v2", "prim", 23)
    for prim_id, argc in ((26, 3), (27, 1), (34, 2), (40, 1)):
        canonical_name = PRIM_RETIREMENTS[prim_id]["canonical_name"]
        if classify_id(base, "dialect-v2", "prim", prim_id) != {
            "id": prim_id,
            "status": "tombstone",
            "canonical_name": canonical_name,
            "operand": None,
            "diagnostic": "abi-prim-tombstone",
        }:
            raise LedgerError(f"Prim-ID {prim_id} retirement classification drift")
        expected_disassembly = (
            f"0000 CALLPRIM prim={prim_id}:{canonical_name}[abi-prim-tombstone] argc={argc}"
        )
        if B.disassemble_payload(
            bytes((61, prim_id, argc)), profile_id="dialect-v2", abi_ledger=base
        ) != [expected_disassembly]:
            raise LedgerError(f"Prim-ID {prim_id} retirement disassembly drift")
        _expect_exception(
            f"retired Prim-ID {prim_id} emitter",
            ValueError,
            lambda prim_id=prim_id, argc=argc: B.encode_instruction(
                "CALLPRIM", prim_id, argc, profile_id="dialect-v2", abi_ledger=base
            ),
        )

    def mutation(change: Callable[[dict[str, Any]], None]) -> Callable[[], None]:
        def run() -> None:
            value = deepcopy(base)
            change(value)
            validate(value, check_mirrors=False)
        return run

    _expect_failure("id width", mutation(lambda value: value.update(id_bits=16)))
    _expect_failure("policy", mutation(lambda value: value["policies"].update(id_reuse="allowed")))
    _expect_failure("retirement missing", mutation(lambda value: value.update(prim_retirements=[])))
    _expect_failure(
        "retirement evidence",
        mutation(lambda value: value["prim_retirements"][0]["evidence"].update(sha256="0" * 64)),
    )
    _expect_failure("identity rename", mutation(lambda value: value["opcode_identities"][0].update(canonical_name="STOP")))
    _expect_failure("identity operand", mutation(lambda value: value["opcode_identities"][0].update(operand="mystery")))
    _expect_failure("duplicate canonical name", mutation(lambda value: value["opcode_identities"][1].update(canonical_name="HALT")))
    _expect_failure("reserved overlap", mutation(lambda value: value["profiles"][0]["opcodes"]["reserved_ranges"].append([0, 0])))
    _expect_failure("missing partition", mutation(lambda value: value["profiles"][0]["prim_ids"]["reserved_ranges"].clear()))
    _expect_failure("tombstone reactivation", mutation(lambda value: (
        value["profiles"][0]["opcodes"]["active"].remove(55),
        value["profiles"][0]["opcodes"]["tombstone"].append(55),
    )))
    _expect_failure("profile order", mutation(lambda value: value["profiles"].reverse()))
    _expect_failure(
        "frozen v1 and v2 tombstone",
        mutation(lambda value: [
            (profile["opcodes"]["active"].remove(55), profile["opcodes"]["tombstone"].append(55))
            for profile in value["profiles"]
        ]),
    )

    allocated = deepcopy(base)
    allocated["opcode_identities"].append(
        {"id": 66, "canonical_name": "V2ONLY", "operand": "u8"}
    )
    allocated["profiles"][1]["opcodes"]["active"].append(66)
    allocated["profiles"][1]["opcodes"]["active"].sort()
    allocated["profiles"][1]["opcodes"]["reserved_ranges"][-1] = [67, 255]
    validate(allocated, check_mirrors=False)
    require_active(allocated, "dialect-v2", "opcode", 66)
    if classify_id(allocated, "dialect-v1", "opcode", 66)["status"] != "reserved":
        raise LedgerError("reserved(v1)->active(v2) transition classification drift")

    tombstone = deepcopy(base)
    tombstone["profiles"][1]["opcodes"]["active"].remove(64)
    tombstone["profiles"][1]["opcodes"]["tombstone"].append(64)
    validate(tombstone, check_mirrors=False)
    classified = classify_id(tombstone, "dialect-v2", "opcode", 64)
    if classified != {
        "id": 64, "status": "tombstone", "canonical_name": "UPVAL", "operand": "u8",
        "diagnostic": "abi-opcode-tombstone",
    }:
        raise LedgerError("synthetic tombstone decoder classification drift")
    if B.disassemble_payload(
        bytes((64, 7)), profile_id="dialect-v2", abi_ledger=tombstone
    ) != ["0000 UPVAL[abi-opcode-tombstone] 7"]:
        raise LedgerError("real tombstone opcode disassembly drift")
    _expect_exception(
        "real tombstone opcode emitter", ValueError,
        lambda: B.encode_instruction(
            "UPVAL", 7, profile_id="dialect-v2", abi_ledger=tombstone
        ),
    )
    _expect_exception(
        "real reserved opcode decoder", B.DecodeError,
        lambda: B.decode_instruction(
            bytes((66,)), 0, profile_id="dialect-v2", abi_ledger=tombstone
        ),
    )
    _expect_failure(
        "tombstone emitter",
        lambda: require_active(tombstone, "dialect-v2", "opcode", 64),
    )

    prim_tombstone = deepcopy(base)
    validate(prim_tombstone, check_mirrors=False)
    if B.disassemble_payload(
        bytes((61, 1, 1)), profile_id="dialect-v2", abi_ledger=prim_tombstone
    ) != ["0000 CALLPRIM prim=1:string->list[abi-prim-tombstone] argc=1"]:
        raise LedgerError("real tombstone Prim-ID disassembly drift")
    _expect_exception(
        "real tombstone Prim-ID emitter", ValueError,
        lambda: B.encode_instruction(
            "CALLPRIM", 1, 1, profile_id="dialect-v2", abi_ledger=prim_tombstone
        ),
    )
    _expect_exception(
        "real reserved Prim-ID decoder", B.DecodeError,
        lambda: B.decode_instruction(
            bytes((61, 67, 0)), 0, profile_id="dialect-v2", abi_ledger=prim_tombstone
        ),
    )
    _expect_exception(
        "real reserved Prim-ID emitter", ValueError,
        lambda: B.encode_instruction(
            "CALLPRIM", 67, 0, profile_id="dialect-v2", abi_ledger=prim_tombstone
        ),
    )
    if B.encode_instruction("UPVAL", 7) != bytes((64, 7)):
        raise LedgerError("default dialect-v1 encoder compatibility drift")
    if B.disassemble_payload(bytes((64, 7))) != ["0000 UPVAL 7"]:
        raise LedgerError("default dialect-v1 disassembler compatibility drift")
    _expect_exception(
        "implicit non-v1 profile", ValueError,
        lambda: B.encode_instruction("UPVAL", 7, profile_id="dialect-v2"),
    )


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ledger", nargs="?", type=Path, default=DEFAULT_LEDGER)
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--require-staging-dispatch", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.selftest:
            selftest()
            print(
                "bytecode-abi-ledger: SELFTEST PASS mutations=12 "
                "transition=reserved-to-active decoder=active+tombstone+reserved "
                "emitter=fail-closed"
            )
            return 0
        path = args.ledger if args.ledger.is_absolute() else ROOT / args.ledger
        totals = validate(
            load_json(path), require_staging_dispatch=args.require_staging_dispatch
        )
    except LedgerError as exc:
        print(f"bytecode-abi-ledger: FAIL: {exc}", file=sys.stderr)
        return 1
    print("bytecode-abi-ledger: PASS opcodes={opcodes} prim_ids={prim_ids} profiles={profiles} staging_pending={staging_pending}".format(**totals))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
