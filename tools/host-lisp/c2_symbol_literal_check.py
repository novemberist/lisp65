#!/usr/bin/env python3
"""Bind the complete general-symbol census and the C2I-v2 kind-8 proposal."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
PROPOSAL = ROOT / "config/c2-symbol-literal-proposal.json"
DOCUMENT = ROOT / "docs/planning/c2.1-symbol-literal-addendum.md"
RECURSIVE = ROOT / "config/c2-recursive-literal-proposal.json"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2-symbol-literal-proposal-receipt.json"
)
MANIFESTS = (
    ("stdlib-p0", ROOT / "build/bytecode/dialect-v2/workbench/stdlib-p0.manifest.json"),
    ("ide", ROOT / "build/bytecode/dialect-v2/libs/ide.manifest.json"),
    ("idex", ROOT / "build/bytecode/dialect-v2/libs/idex.manifest.json"),
    ("m65d", ROOT / "build/bytecode/dialect-v2/libs/m65d.manifest.json"),
    ("buffer", ROOT / "build/bytecode/dialect-v2/libs/buffer.manifest.json"),
    ("lcc", ROOT / "build/bytecode/dialect-v2/libs/lcc.manifest.json"),
)


class SymbolError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SymbolError(message)


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"object required: {path}")
    return value


def binding(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest()}


def census() -> dict[str, Any]:
    per_image: dict[str, int] = {}
    names: list[str] = []
    for image, path in MANIFESTS:
        manifest = load(path)
        current = [node.get("name") for node in manifest.get("literal_nodes", [])
                   if int(node.get("kind", -1)) == 4]
        require(all(isinstance(name, str) for name in current), "symbol name is not text")
        per_image[image] = len(current)
        names.extend(current)
    canonical = all(1 <= len(name.encode("ascii")) <= 255
                    and all(0x21 <= byte <= 0x7e for byte in name.encode("ascii"))
                    for name in names)
    return {"symbol_nodes": len(names), "distinct_symbol_names": len(set(names)),
            "maximum_symbol_name_bytes": max(map(lambda value: len(value.encode("ascii")), names)),
            "all_names_canonical_ascii_1_through_255": canonical,
            "per_image_symbol_nodes": per_image}


def validate(proposal: dict[str, Any], facts: dict[str, Any]) -> None:
    require(proposal.get("format") == "lisp65-c2-symbol-literal-proposal-v1"
            and proposal.get("status") == "owner-approved-option-a-c2i-v2-authorized",
            "proposal status drift")
    require("Option A approved on 2026-07-19" in proposal.get("owner_decision", ""),
            "symbol-literal owner approval missing")
    recursive = load(RECURSIVE)
    require(recursive.get("status") == "owner-approved-option-a-c2i-v2-authorized",
            "C2I-v2 recursive approval missing")
    measured = proposal["measured_inputs"]
    for key, value in facts.items():
        require(measured.get(key) == value, f"symbol census drift: {key}")
    require(facts["symbol_nodes"] == 979 and facts["distinct_symbol_names"] == 344
            and facts["maximum_symbol_name_bytes"] == 33
            and facts["all_names_canonical_ascii_1_through_255"],
            "symbol census closure drift")
    options = proposal["options"]
    require([row["id"] for row in options] == [
        "c2i-v2-general-symbol-kind-8", "rename-kind-5-to-general-symbol",
        "infer-callable-role-from-name"
    ], "symbol option closure drift")
    require([row["assessment"] for row in options] == [
        "recommended", "rejected-weakens-export-edge-contract",
        "rejected-false-evidence"
    ], "symbol option assessment drift")
    delta = options[0]["format_delta"]
    require(all(delta[key] == 0 for key in (
        "header_bytes", "entry_record_bytes", "literal_descriptor_bytes",
        "descriptor_count", "c2d_resolution_bytes"
    )) and delta["c2d_v1_bytes"] == 10480
       and delta["projected_bank5_headroom_bytes"] == 40336,
       "symbol option byte arithmetic drift")
    require(len(proposal.get("required_negative_fixtures", [])) == 8,
            "symbol negative closure drift")
    consumer = proposal.get("consumer_rule", "")
    require(all(term in consumer for term in (
        "Tree-shaking", "who-calls", "ide-help", "only kind 5",
        "Kind 8 is invisible", "spelling alone"
    )), "call-graph consumer rule missing")


def collect() -> dict[str, Any]:
    proposal, facts = load(PROPOSAL), census()
    validate(proposal, facts)
    return {
        "format": "lisp65-c2-symbol-literal-proposal-receipt-v1",
        "version": 1,
        "recorded_on": "2026-07-19",
        "status": "option-a-owner-approved-c2i-v2-kind-8-authorized",
        "claim_limit": (
            "This receipt binds the complete current general-symbol census and the "
            "zero-record-byte format fork. It changes no product byte, authorizes no "
            "capacity and makes no claim that spelling proves call provenance."
        ),
        "bindings": {
            "proposal": binding(PROPOSAL), "document": binding(DOCUMENT),
            "recursive_contract": binding(RECURSIVE), "verifier": binding(Path(__file__)),
            "manifests": [binding(path) for _key, path in MANIFESTS],
        },
        "measured": facts,
        "validated": {
            "general_symbol_kind": 8,
            "format_record_byte_delta": 0,
            "c2d_bytes": 10480,
            "projected_bank5_headroom_bytes": 40336,
            "required_negative_fixture_classes": 8,
            "product_bytes_changed": 0,
        },
        "next_action": "Emit strict C2I-v2 over all six manifests and prove kind-5/kind-8 consumer separation"
    }


def selftest() -> None:
    proposal, facts = load(PROPOSAL), census()
    rejected = []
    for label, mutate in (
        ("node-count", lambda value: value["measured_inputs"].__setitem__("symbol_nodes", 978)),
        ("distinct-count", lambda value: value["measured_inputs"].__setitem__("distinct_symbol_names", 343)),
        ("kind-order", lambda value: value["options"].reverse()),
        ("record-cost", lambda value: value["options"][0]["format_delta"].__setitem__("literal_descriptor_bytes", 1)),
        ("session-cost", lambda value: value["options"][0]["format_delta"].__setitem__("c2d_v1_bytes", 10482)),
        ("consumer-boundary", lambda value: value.__setitem__("consumer_rule", "all symbols are call edges")),
    ):
        bad = copy.deepcopy(proposal)
        mutate(bad)
        try:
            validate(bad, facts)
        except SymbolError:
            rejected.append(label)
    require(len(rejected) == 6, f"mutations not rejected: {rejected}")


def canonical(value: dict[str, Any]) -> str:
    return json.dumps(value, indent=2, sort_keys=True) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("write", "check", "selftest"))
    args = parser.parse_args()
    if args.action == "selftest":
        selftest()
        print("c2-symbol-literal: SELFTEST PASS mutations=6")
        return 0
    data = canonical(collect())
    if args.action == "write":
        RECEIPT.parent.mkdir(parents=True, exist_ok=True)
        RECEIPT.write_text(data, encoding="utf-8")
        verb = "WROTE"
    else:
        require(RECEIPT.is_file() and RECEIPT.read_text(encoding="utf-8") == data,
                "symbol-literal receipt drift; regenerate with write")
        verb = "PASS"
    print(f"c2-symbol-literal: {verb} nodes=979 names=344 option=A-approved")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
