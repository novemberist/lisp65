#!/usr/bin/env python3
"""Bind the complete literal census and the non-authorizing C2 recursive-literal fork."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
PROPOSAL = ROOT / "config/c2-recursive-literal-proposal.json"
DOCUMENT = ROOT / "docs/planning/c2.1-recursive-literal-addendum.md"
SESSION = ROOT / "config/c2-session-directory-proposal.json"
CORE = ROOT / "config/c2-address-identity-contract.json"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2-recursive-literal-proposal-receipt.json"
)
MANIFESTS = (
    ("stdlib-p0", ROOT / "build/bytecode/dialect-v2/workbench/stdlib-p0.manifest.json"),
    ("ide", ROOT / "build/bytecode/dialect-v2/libs/ide.manifest.json"),
    ("idex", ROOT / "build/bytecode/dialect-v2/libs/idex.manifest.json"),
    ("m65d", ROOT / "build/bytecode/dialect-v2/libs/m65d.manifest.json"),
    ("buffer", ROOT / "build/bytecode/dialect-v2/libs/buffer.manifest.json"),
    ("lcc", ROOT / "build/bytecode/dialect-v2/libs/lcc.manifest.json"),
)
KIND_NAMES = {1: "fixnum", 2: "nil", 3: "true", 4: "symbol", 5: "cons",
              6: "list", 7: "string", 8: "entry_ref"}


class LiteralError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise LiteralError(message)


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"object required: {path}")
    return value


def binding(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest()}


def census() -> dict[str, Any]:
    counts = {name: 0 for name in KIND_NAMES.values()}
    lists: list[dict[str, Any]] = []
    total = 0
    for image, path in MANIFESTS:
        manifest = load(path)
        nodes = manifest.get("literal_nodes", [])
        index = manifest.get("literal_index", [])
        require(isinstance(nodes, list) and isinstance(index, list), "literal tables missing")
        for ordinal, node in enumerate(nodes):
            kind = int(node.get("kind", -1))
            require(kind in KIND_NAMES, f"unknown current literal kind {kind}")
            counts[KIND_NAMES[kind]] += 1
            total += 1
            if kind in (5, 6):
                first, count = int(node["first"]), int(node["count"])
                require(0 <= first <= len(index) and 0 <= count <= len(index) - first,
                        "recursive literal index range")
                children = [int(value) for value in index[first:first + count]]
                require(all(0 <= child < len(nodes) for child in children),
                        "recursive child out of range")
                lists.append({"image": image, "ordinal": ordinal, "kind": KIND_NAMES[kind],
                              "children": count,
                              "all_children_precede_parent": all(child < ordinal for child in children)})
    return {"images": len(MANIFESTS), "literal_nodes": total,
            "literal_kind_counts": counts, "recursive_nodes": lists,
            "recursive_edges": sum(row["children"] for row in lists)}


def validate(proposal: dict[str, Any], facts: dict[str, Any]) -> None:
    require(proposal.get("format") == "lisp65-c2-recursive-literal-proposal-v1"
            and proposal.get("status") == "owner-approved-option-a-c2i-v2-authorized",
            "proposal status drift")
    require("Option A approved on 2026-07-19" in proposal.get("owner_decision", ""),
            "recursive-literal owner approval missing")
    session = load(SESSION)
    require(session.get("status") == "owner-approved-option-a-product-layout-authorized",
            "C2D Option A approval missing")
    core = load(CORE)
    kinds = core["direct_container"]["literal_descriptor"]["kinds"]
    require(len(kinds) == 7 and not any("cons" in value or "list" in value for value in kinds),
            "approved C2I-v1 vocabulary no longer exhibits the measured gap")
    measured = proposal["measured_inputs"]
    require(measured["images"] == facts["images"] == 6, "image census drift")
    require(measured["literal_nodes"] == facts["literal_nodes"] == 2084,
            "literal census drift")
    require(measured["literal_kind_counts"] == facts["literal_kind_counts"],
            "literal kind census drift")
    require(measured["recursive_list_edges"] == facts["recursive_edges"] == 168,
            "recursive edge census drift")
    rows = facts["recursive_nodes"]
    require(len(rows) == 4 and {row["image"] for row in rows} == {"ide"}
            and [row["children"] for row in rows] == [34, 48, 74, 12]
            and all(row["kind"] == "list" and row["all_children_precede_parent"] for row in rows),
            "recursive list geometry drift")
    options = proposal["options"]
    require([row["id"] for row in options] == [
        "c2i-v2-cons-pair-lowering", "c2i-v2-edge-section",
        "retain-l65m-recursive-materializer", "rewrite-four-ide-literals-in-source"
    ], "option closure drift")
    require([row["assessment"] for row in options] == [
        "recommended", "fallback-more-format-and-decoder-complexity",
        "rejected", "rejected-special-case"
    ], "option assessment drift")
    selected = options[0]["exact_current_delta"]
    require(selected["new_cons_descriptors"] == 168
            and selected["new_nil_descriptors"] == 1
            and selected["removed_list_descriptors"] == 4
            and selected["net_descriptor_growth"] == 165,
            "cons lowering arithmetic drift")
    require(selected["immutable_metadata_growth_bytes"] == 165 * 8
            and selected["session_resolution_growth_bytes"] == 165 * 2
            and selected["c2d_v1_bytes_after_lowering"] == 10150 + 165 * 2
            and selected["projected_bank5_headroom_bytes"] == 50816 - (10150 + 165 * 2),
            "cons lowering byte arithmetic drift")
    fallback = options[1]["exact_current_delta"]
    require(fallback["edge_records"] == 168 and fallback["edge_bytes"] == 336
            and fallback["six_image_header_growth_bytes"] == 48
            and fallback["minimum_immutable_metadata_growth_bytes"] == 384,
            "edge-section arithmetic drift")
    require(len(proposal.get("recommended_negative_fixtures", [])) == 8,
            "recursive negative closure drift")


def collect() -> dict[str, Any]:
    proposal = load(PROPOSAL)
    facts = census()
    validate(proposal, facts)
    return {
        "format": "lisp65-c2-recursive-literal-proposal-receipt-v1",
        "version": 1,
        "recorded_on": "2026-07-19",
        "status": "option-a-owner-approved-c2i-v2-authorized",
        "claim_limit": (
            "This receipt binds the complete current literal census and two format options. "
            "It changes no product byte, authorizes no capacity and does not amend or "
            "invalidate the historical C2I-v1 proof receipt."
        ),
        "bindings": {
            "proposal": binding(PROPOSAL), "document": binding(DOCUMENT),
            "session_contract": binding(SESSION), "core_contract": binding(CORE),
            "verifier": binding(Path(__file__)),
            "manifests": [binding(path) for _key, path in MANIFESTS],
        },
        "measured": facts,
        "validated": {
            "unsupported_current_recursive_nodes": 4,
            "unsupported_current_recursive_edges": 168,
            "recommended_net_descriptor_growth": 165,
            "recommended_c2d_bytes": 10480,
            "recommended_projected_bank5_headroom_bytes": 40336,
            "required_negative_fixture_classes": 8,
            "product_bytes_changed": 0,
        },
        "next_action": "Implement strict C2I-v2 lowering after complete literal-semantic closure; stop at every uncovered kind"
    }


def selftest() -> None:
    proposal, facts = load(PROPOSAL), census()
    rejected = []
    for label, mutate in (
        ("kind-count", lambda value: value["measured_inputs"]["literal_kind_counts"].__setitem__("list", 3)),
        ("edge-count", lambda value: value["measured_inputs"].__setitem__("recursive_list_edges", 167)),
        ("descriptor-growth", lambda value: value["options"][0]["exact_current_delta"].__setitem__("net_descriptor_growth", 164)),
        ("session-bytes", lambda value: value["options"][0]["exact_current_delta"].__setitem__("c2d_v1_bytes_after_lowering", 10478)),
        ("fallback-bytes", lambda value: value["options"][1]["exact_current_delta"].__setitem__("minimum_immutable_metadata_growth_bytes", 382)),
    ):
        bad = copy.deepcopy(proposal)
        mutate(bad)
        try:
            validate(bad, facts)
        except LiteralError:
            rejected.append(label)
    require(len(rejected) == 5, f"mutations not rejected: {rejected}")


def canonical(value: dict[str, Any]) -> str:
    return json.dumps(value, indent=2, sort_keys=True) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("write", "check", "selftest"))
    args = parser.parse_args()
    if args.action == "selftest":
        selftest()
        print("c2-recursive-literal: SELFTEST PASS mutations=5")
        return 0
    value = canonical(collect())
    if args.action == "write":
        RECEIPT.parent.mkdir(parents=True, exist_ok=True)
        RECEIPT.write_text(value, encoding="utf-8")
        verb = "WROTE"
    else:
        require(RECEIPT.is_file() and RECEIPT.read_text(encoding="utf-8") == value,
                "recursive-literal receipt drift; regenerate with write")
        verb = "PASS"
    print(f"c2-recursive-literal: {verb} nodes=2084 recursive=4/168 option=A-approved")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
