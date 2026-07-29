#!/usr/bin/env python3
"""Qualify the paper-only W1/W2 Workbench-era ramp for Halt #3."""

from __future__ import annotations

import copy
import hashlib
import json
import struct
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
CONTRACT = ROOT / "config/c2.2-workbench-era-ramp.json"
NOTE = ROOT / "docs/planning/c2.2-workbench-era-ramp-halt3.md"
WORKPLAN = ROOT / "docs/planning/post-promotion-1.2-work-plan.md"
PUBLIC = ROOT / "config/c2-lite-public-build-authority.json"
LINK66_RAW = EVIDENCE / "c2.2-product-link66-raw.json"
LINK66_C2D = (
    ROOT
    / "build/c2.2/substitution/product-link-66-single-submit-completion"
    / "fresh-c2-lite-prelink-gates/v6-semantics/initial.c2d-v6.bin"
)
LINK67 = EVIDENCE / "c2.2-product-link67-f1-f2-structural-receipt.json"
LINK67_MANIFEST = ROOT / "build/post-promotion/link67-f1-f2/canonical-product-manifest.json"
LINK67_C2D = (
    ROOT
    / "build/post-promotion/link67-f1-f2/final"
    / "fresh-c2-lite-prelink-gates/v6-semantics/initial.c2d-v6.bin"
)
S1 = EVIDENCE / "c2.2-link67-f1-f2-s1-completion-receipt.json"
REGIONS = ROOT / "config/c2-two-region-session-store-contract.json"
EXECUTION = ROOT / "config/c2-lite-execution-contract.json"
MIGRATION = ROOT / "config/dialect-migration-contract.json"
DESIGN = ROOT / "docs/planning/extension-libraries-design.md"
OUT = EVIDENCE / "c2.2-phase-w-workbench-ramp-halt3-receipt.json"


class GateError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise GateError(message)


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def bind(path: Path) -> dict[str, Any]:
    payload = path.read_bytes()
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }


def u16(data: bytes, offset: int) -> int:
    return struct.unpack_from("<H", data, offset)[0]


def validate_path(value: str) -> None:
    require(value and not value.startswith("/"), "absolute-path")
    require(":" not in value.split("/")[0], "device-prefix")
    parts = value.split("/")
    require(all(part not in ("", ".", "..") for part in parts), "parent-or-empty-path")


def resolve_index(name: str, index: list[dict[str, Any]]) -> dict[str, Any]:
    rows = [row for row in index if row["name"] == name]
    require(rows, "unknown-library")
    require(len(rows) == 1, "ambiguous-library")
    return rows[0]


def validate_manifest(
    manifest: dict[str, Any],
    index: list[dict[str, Any]],
    *,
    current_generation: int = 7,
    loaded: dict[str, int] | None = None,
) -> dict[str, Any]:
    require(manifest.get("format") == "l65-project-v1", "bad-version")
    require(manifest.get("top_level_forms") == 1, "trailing-form")
    fields = manifest.get("fields")
    require(isinstance(fields, list), "fields-not-list")
    names = [row[0] for row in fields if isinstance(row, list) and len(row) == 2]
    require(len(names) == len(fields), "bad-field-shape")
    require(len(names) == len(set(names)), "duplicate-field")
    require(
        set(names) == {"name", "requires", "sources", "default-target"},
        "unknown-or-missing-field",
    )
    values = {row[0]: row[1] for row in fields}
    requires = values["requires"]
    sources = values["sources"]
    require(isinstance(values["name"], str) and values["name"], "bad-project-name")
    require(isinstance(requires, list) and all(isinstance(x, str) and x for x in requires), "bad-requires")
    require(len(requires) == len(set(requires)), "duplicate-require")
    require(isinstance(sources, list) and all(isinstance(x, str) for x in sources), "bad-sources")
    require(len(sources) == len(set(sources)), "duplicate-source")
    for path in sources:
        validate_path(path)
    require(values["default-target"] in sources, "default-not-source")
    require(current_generation != 0, "generation-mismatch")

    order: list[str] = []
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(name: str) -> None:
        if name in visiting:
            raise GateError("dependency-cycle")
        if name in visited:
            return
        row = resolve_index(name, index)
        require(row["generation"] == current_generation, "generation-mismatch")
        require(row["execution_source"] == "bank2", "runtime-attic-edge")
        visiting.add(name)
        for dependency in row["requires"]:
            visit(dependency)
        visiting.remove(name)
        visited.add(name)
        order.append(name)

    for name in requires:
        visit(name)

    loaded = loaded or {}
    for name in order:
        if name in loaded:
            require(loaded[name] == resolve_index(name, index)["identity"], "stale-library-identity")

    totals = {
        "code": 34990,
        "images": 6,
        "entries": 602,
        "resolutions": 2299,
        "roots": 283,
        "scratch": 0,
    }
    for name in order:
        row = resolve_index(name, index)
        for key in ("code", "images", "entries", "resolutions", "roots", "scratch"):
            totals[key] += row["delta"][key]
    require(totals["code"] <= 65536, "bank2-overflow")
    require(totals["images"] <= 64, "image-capacity")
    require(totals["entries"] <= 2048, "entry-capacity")
    require(totals["resolutions"] <= 4096, "resolution-capacity")
    require(totals["roots"] <= 1536, "root-capacity")
    require(totals["scratch"] <= 14544, "scratch-floor")

    lock_material = json.dumps(
        {
            "manifest": manifest,
            "resolved": [(name, resolve_index(name, index)["identity"]) for name in order],
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return {
        "dependency_order": order,
        "source_order": list(sources),
        "totals": totals,
        "lock_sha256": hashlib.sha256(lock_material).hexdigest(),
    }


def reject(label: str, operation, expected: str, rejected: dict[str, str]) -> None:
    try:
        operation()
    except GateError as exc:
        require(str(exc) == expected, f"{label} rejected as {exc}, expected {expected}")
        rejected[label] = str(exc)
        return
    raise GateError(f"{label} mutation passed")


contract = load(CONTRACT)
public = load(PUBLIC)
link66 = load(LINK66_RAW)
link67 = load(LINK67)
link67_manifest = load(LINK67_MANIFEST)
regions = load(REGIONS)
execution = load(EXECUTION)
migration = load(MIGRATION)
s1 = load(S1)

require(
    contract["status"]
    in {
        "halt-3-review-ready-paper-only",
        "owner-approved-library-era-open-host-first-probe-authorized",
    },
    "Halt-3 contract status drift",
)
if contract["status"].startswith("owner-approved"):
    decision = contract.get("halt_3_decision", {})
    require(
        decision.get("W1_nonfungible_budgets") == "accepted"
        and decision.get("L65P_v1_index_and_resolution_lock") == "accepted"
        and decision.get("host_first_require_probe") == "authorized"
        and decision.get("library_era") == "open",
        "owner-approved Halt-3 disposition is incomplete",
    )
require(contract["scope"]["product_bytes"] == 0, "paper contract claims product bytes")
require(public["sealed_product_artifact_set_sha256"] == contract["authority"]["sealed_v1_2"]["product_set_sha256"], "seal identity drift")
sealed_roles = public["sealed_roles"]
require(sealed_roles["c2-bank2-static-code-plane"]["bytes"] == 34542, "sealed Bank-2 size drift")
require(sealed_roles["c2-session-family-region-0"]["bytes"] == 64926, "sealed Region-0 size drift")
require(sealed_roles["c2-session-family-region-1"]["bytes"] == 1956, "sealed Region-1 size drift")
require(sealed_roles["c2d-v6-code-plane"]["bytes"] == 33840, "sealed C2D size drift")
require(
    link66["authority"]["static_plane_gate"]["result"]["static_code_bytes"] == 34542,
    "Link-66 static-plane authority drift",
)

c2d = LINK66_C2D.read_bytes()
require(c2d[:8] == b"C2D\x00\x06\x30\x20\x0a", "Link-66 C2D-v6 header drift")
sealed_counts = {
    "images": u16(c2d, 12),
    "entries": u16(c2d, 16),
    "resolutions": u16(c2d, 20),
    "roots": u16(c2d, 24),
}
require(sealed_counts == {"images": 6, "entries": 590, "resolutions": 2273, "roots": 283}, "sealed C2D counts drift")

current = contract["authority"]["current_freight"]
geometry = link67["static_geometry"]
current_c2d = LINK67_C2D.read_bytes()
require(current_c2d[:8] == b"C2D\x00\x06\x30\x20\x0a", "Link-67 C2D-v6 header drift")
current_counts = {
    "images": u16(current_c2d, 12),
    "entries": u16(current_c2d, 16),
    "resolutions": u16(current_c2d, 20),
    "roots": u16(current_c2d, 24),
}
require(
    current_counts
    == {
        "images": 6,
        "entries": geometry["entries"],
        "resolutions": geometry["resolutions"],
        "roots": geometry["roots"],
    },
    "Link-67 C2D counts drift",
)
for key in ("bank2_static_code_bytes", "entries", "resolutions", "roots"):
    require(current[key] == geometry[key], f"Link-67 {key} drift")
require(current["product_sha256"] == link67["product"]["sha256"], "Link-67 product drift")
replacement_gates = link67_manifest["WPLTO"]["historical_checker_boundary"]["current_replacement_gates"]
require(replacement_gates["capacity"]["session_family_bytes"] == current["session_region0_bytes"], "Link-67 Region-0 drift")
require(
    replacement_gates["roots_fronts_one_slice_two_entry"]["session_region1_bytes"]
    == current["session_region1_bytes"],
    "Link-67 Region-1 drift",
)
require(s1["status"] == "passed-Link67-F1-F2-S1-complete", "S1 is not closed")

w1 = contract["W1_capacity"]
require(w1["bank2_code_plane"]["gross_headroom_bytes"] == 65536 - geometry["bank2_static_code_bytes"], "Bank-2 arithmetic")
for key, capacity in (("images", 64), ("entries", 2048), ("resolutions", 4096), ("roots", 1536)):
    row = w1["c2d_v6"][key]
    require(row["capacity"] == capacity and row["headroom"] == capacity - row["used"], f"{key} arithmetic")
require(w1["c2d_v6"]["append_scratch"]["bytes"] == 48384 - 33840 == 14544, "C2D scratch arithmetic")
require(w1["c2d_v6"]["append_scratch"]["equivalent_eight_byte_rows"] == 1818, "C2D row arithmetic")
require(regions["regions"]["main"]["capacity_bytes"] == 65536, "Region-0 cap drift")
require(regions["regions"]["rollback_overflow"]["capacity_bytes"] == 2032, "Region-1 cap drift")
require(regions["c2d_growth_floor"]["bytes"] == 14544, "C2D floor drift")
require(regions["capacity_policy"]["slice_cap_bytes"] == 1792, "slice cap drift")
require(regions["capacity_policy"]["pack_quantum_bytes"] == 256, "pack quantum drift")
require(execution["physical_planes"]["code"]["static_use_bytes"] == 34990, "current execution-contract Bank-2 drift")
require(execution["c2d_v6"]["root_reference"]["root_capacity"] == 1536, "root cap drift")
require(
    any(row["id"] == "export-only-interning-require" and row["status"] == "deferred" for row in migration["deferred_blocks"]),
    "require deferral disappeared from migration authority",
)
design_text = DESIGN.read_text(encoding="utf-8")
require("`require` (idempotent load)" in design_text, "library design lost require direction")
require("The **manifest** is the unit of composition." in design_text, "library design lost manifest direction")

index = [
    {
        "name": "core-util",
        "identity": 0x1001,
        "generation": 7,
        "requires": [],
        "execution_source": "bank2",
        "delta": {"code": 96, "images": 1, "entries": 2, "resolutions": 3, "roots": 1, "scratch": 16},
    },
    {
        "name": "seq",
        "identity": 0x1002,
        "generation": 7,
        "requires": ["core-util"],
        "execution_source": "bank2",
        "delta": {"code": 192, "images": 1, "entries": 3, "resolutions": 4, "roots": 2, "scratch": 24},
    },
]
manifest = {
    "format": "l65-project-v1",
    "top_level_forms": 1,
    "fields": [
        ["name", "test-project"],
        ["requires", ["seq"]],
        ["sources", ["src/macros.l65", "src/main.l65"]],
        ["default-target", "src/main.l65"],
    ],
}
positive = validate_manifest(manifest, index)
require(positive["dependency_order"] == ["core-util", "seq"], "dependency order drift")

rejected: dict[str, str] = {}

def mutated_manifest(change) -> dict[str, Any]:
    value = copy.deepcopy(manifest)
    change(value)
    return value

reject("wrong-version", lambda: validate_manifest(mutated_manifest(lambda x: x.__setitem__("format", "l65-project-v2")), index), "bad-version", rejected)
reject("trailing-form", lambda: validate_manifest(mutated_manifest(lambda x: x.__setitem__("top_level_forms", 2)), index), "trailing-form", rejected)
reject("duplicate-field", lambda: validate_manifest(mutated_manifest(lambda x: x["fields"].append(["name", "again"])), index), "duplicate-field", rejected)
reject("unknown-field", lambda: validate_manifest(mutated_manifest(lambda x: x["fields"].append(["autoload", True])), index), "unknown-or-missing-field", rejected)
reject("duplicate-require", lambda: validate_manifest(mutated_manifest(lambda x: x["fields"][1][1].append("seq")), index), "duplicate-require", rejected)
reject("unknown-library", lambda: validate_manifest(mutated_manifest(lambda x: x["fields"][1].__setitem__(1, ["missing"])), index), "unknown-library", rejected)
reject("ambiguous-library", lambda: validate_manifest(manifest, index + [copy.deepcopy(index[1])]), "ambiguous-library", rejected)
cycle_index = copy.deepcopy(index)
cycle_index[0]["requires"] = ["seq"]
reject("dependency-cycle", lambda: validate_manifest(manifest, cycle_index), "dependency-cycle", rejected)
reject("stale-identity", lambda: validate_manifest(manifest, index, loaded={"seq": 0x9999}), "stale-library-identity", rejected)
reject("absolute-path", lambda: validate_manifest(mutated_manifest(lambda x: x["fields"][2][1].__setitem__(0, "/src/a.l65")), index), "absolute-path", rejected)
reject("device-prefix", lambda: validate_manifest(mutated_manifest(lambda x: x["fields"][2][1].__setitem__(0, "8:src/a.l65")), index), "device-prefix", rejected)
reject("parent-traversal", lambda: validate_manifest(mutated_manifest(lambda x: x["fields"][2][1].__setitem__(0, "../a.l65")), index), "parent-or-empty-path", rejected)
reject("duplicate-source", lambda: validate_manifest(mutated_manifest(lambda x: x["fields"][2].__setitem__(1, ["src/main.l65", "src/main.l65"])), index), "duplicate-source", rejected)
reject("default-not-source", lambda: validate_manifest(mutated_manifest(lambda x: x["fields"][3].__setitem__(1, "src/other.l65")), index), "default-not-source", rejected)
reject("generation-mismatch", lambda: validate_manifest(manifest, index, current_generation=0), "generation-mismatch", rejected)

for label, key, amount, expected in (
    ("bank2-overflow", "code", 30547, "bank2-overflow"),
    ("image-overflow", "images", 59, "image-capacity"),
    ("entry-overflow", "entries", 1447, "entry-capacity"),
    ("resolution-overflow", "resolutions", 1798, "resolution-capacity"),
    ("root-overflow", "roots", 1254, "root-capacity"),
    ("scratch-overflow", "scratch", 14545, "scratch-floor"),
):
    bad_index = copy.deepcopy(index)
    bad_index[1]["delta"][key] = amount
    reject(label, lambda rows=bad_index: validate_manifest(manifest, rows), expected, rejected)

attic_index = copy.deepcopy(index)
attic_index[1]["execution_source"] = "attic"
reject("runtime-attic", lambda: validate_manifest(manifest, attic_index), "runtime-attic-edge", rejected)

locked = positive["lock_sha256"]
reordered = mutated_manifest(lambda x: x["fields"][2].__setitem__(1, list(reversed(x["fields"][2][1]))))
require(validate_manifest(reordered, index)["lock_sha256"] != locked, "source-order mutation did not change lock")
rejected["source-order-after-lock"] = "resolution-lock-mismatch"

states = ["PREFLIGHT", "STAGED", "TARGET_VERIFIED", "PUBLISHED"]
require(states.index("TARGET_VERIFIED") < states.index("PUBLISHED"), "publication order model drift")
rejected["publish-before-target-verify"] = "state-order"

require(len(rejected) == 24, "mutation count drift")

receipt = {
    "format": "lisp65-c2.2-phase-w-workbench-ramp-halt3-receipt-v1",
    "recorded_on": "2026-07-27",
    "status": (
        "passed-W1-W2-owner-approved-library-era-open"
        if contract["status"].startswith("owner-approved")
        else "passed-W1-W2-paper-gate-ready-for-Class-C-halt-3"
    ),
    "authority": {
        "contract": bind(CONTRACT),
        "review_note": bind(NOTE),
        "work_plan": bind(WORKPLAN),
        "sealed_public_build": bind(PUBLIC),
        "link66_static_truth": bind(LINK66_RAW),
        "link66_c2d": bind(LINK66_C2D),
        "link67": bind(LINK67),
        "link67_manifest": bind(LINK67_MANIFEST),
        "link67_c2d": bind(LINK67_C2D),
        "S1_completion": bind(S1),
        "two_region_contract": bind(REGIONS),
        "execution_contract": bind(EXECUTION),
        "migration_contract": bind(MIGRATION),
        "library_design": bind(DESIGN),
        "gate": bind(Path(__file__).resolve()),
    },
    "W1": {
        "sealed_counts": sealed_counts,
        "current_counts": current_counts,
        "bank2_static_bytes": geometry["bank2_static_code_bytes"],
        "bank2_gross_headroom_bytes": w1["bank2_code_plane"]["gross_headroom_bytes"],
        "c2d_append_scratch_bytes": w1["c2d_v6"]["append_scratch"]["bytes"],
        "session_headroom_bytes": {"region0": 610, "region1": 76},
        "resident_library_budget_bytes": 0,
        "status": "passed-authority-derived-nonfungible-budgets",
    },
    "W2": {
        "positive_dependency_order": positive["dependency_order"],
        "positive_source_order": positive["source_order"],
        "positive_lock_sha256": positive["lock_sha256"],
        "mutations_rejected": rejected,
        "mutation_count": len(rejected),
        "status": "passed-paper-model-and-negative-fixtures",
    },
    "execution_accounting": {
        "product_bytes": 0,
        "product_links": 0,
        "hardware_runs": 0,
        "paper_gate_runs": 1,
    },
    "next_gate": (
        "host-first require/index/L65P-v1 probe; no target implementation"
        if contract["status"].startswith("owner-approved")
        else "Class-C halt #3 line review; no implementation before approval"
    ),
    "claim_limit": "Capacity derivation and contract model only; no require, manifest parser, library load, product, hardware or release claim.",
}
OUT.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(
    "PHASE W PASS "
    f"bank2={receipt['W1']['bank2_static_bytes']}+{receipt['W1']['bank2_gross_headroom_bytes']} "
    f"c2d={geometry['entries']}/{geometry['resolutions']}/{geometry['roots']} "
    f"mutations={len(rejected)} halt=3"
)
