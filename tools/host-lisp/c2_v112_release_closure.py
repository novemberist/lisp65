#!/usr/bin/env python3
"""Permanent release-closure gate for the scope-frozen v1.4.0 block."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "config/c2-v112-release-closure.json"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.12-release-closure-receipt.json"
)
DRIVER = Path(__file__).resolve()
GATES = ROOT / "mk/gates.mk"
FORMAT = "lisp65-c2-v112-release-closure-receipt-v1"
STATES = ("closure-only", "host-integrated", "media-closed", "selected")
FREIGHT = ("who-calls", "capitalize", "string-split")
CONDITIONAL = ("defstruct",)


class ClosureError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ClosureError(message)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON authority absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"authority absent: {path}")
    raw = path.read_bytes()
    return {
        "path": path.resolve().relative_to(ROOT.resolve()).as_posix(),
        "bytes": len(raw),
        "sha256": sha(raw),
    }


def git_bind(commit: str) -> str:
    result = subprocess.run(
        ["git", "rev-parse", f"{commit}^{{commit}}"], cwd=ROOT,
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    require(result.returncode == 0, f"owner commit is not bound: {commit}")
    return result.stdout.strip()


def canonical(value: dict[str, Any]) -> str:
    return json.dumps(value, indent=2, sort_keys=True) + "\n"


def surface_map(surface: dict[str, Any]) -> dict[str, str]:
    rows = surface.get("definitions")
    require(isinstance(rows, list), "surface definitions absent")
    result: dict[str, str] = {}
    for row in rows:
        require(isinstance(row, dict) and set(row) == {"kind", "name", "visibility"},
                "surface row vocabulary drift")
        name = row["name"]
        require(isinstance(name, str) and name not in result,
                f"duplicate/non-string surface name: {name}")
        require(row["visibility"] == "public", f"non-public surface row: {name}")
        result[name] = row["kind"]
    return result


def source_definitions(contract: dict[str, Any], overrides: dict[str, str] | None = None) -> dict[str, Any]:
    overrides = overrides or {}
    result: dict[str, Any] = {}
    for name, raw_path in contract["sources"].items():
        path = ROOT / raw_path
        text = overrides.get(name, path.read_text(encoding="utf-8"))
        pattern = re.compile(r"\(def(un|macro)\s+" + re.escape(name) + r"(?:\s|\))")
        matches = pattern.findall(text)
        require(len(matches) == 1, f"{name} lacks exactly one source definition")
        actual = "function" if matches[0] == "un" else "macro"
        result[name] = {"kind": actual, "source": bind(path)}
    return result


def audit_contract(contract: dict[str, Any]) -> None:
    require(contract.get("format") == "lisp65-c2-v112-release-closure-v1",
            "release closure format drift")
    require(contract.get("recorded_on") == "2026-08-07", "closure date drift")
    commits = contract.get("owner_commits", {})
    require(set(commits) == {
        "commission", "phase_plan", "phase_a_authorization", "library_split",
        "trace_descope", "halt_1_selection", "halt_1_register"},
            "owner-commit closure drift")
    expected_commits = {
        "commission": "b9980cb0",
        "phase_plan": "f250f322",
        "phase_a_authorization": "5bd3c2ec",
        "library_split": "a1cf5b9b",
        "trace_descope": "f426f7c7",
        "halt_1_selection": "8e4f4be4",
        "halt_1_register": "70fb52ec",
    }
    require(commits == expected_commits, "owner-commit identities drift")
    require(contract.get("integration_state") in STATES, "unknown integration state")
    require(contract.get("scope") == {
        "release": "v1.4.0",
        "product_banner": "WORKBENCH 1.4.0",
        "product_cores": 1,
        "media_variants": 2,
        "device_sessions": 1,
        "owner_halts": 2,
        "sealed_release_untouched": "v1.3.0",
        "resident_delta_bytes": 0,
    }, "release scope broadened")
    unconditional = contract.get("unconditional_surface")
    conditional = contract.get("conditional_surface")
    require([row.get("name") for row in unconditional] == list(FREIGHT)
            and [row.get("kind") for row in unconditional]
            == ["function", "function", "function"],
            "unconditional surface drift")
    require(conditional == [
        {"kind": "macro", "name": "defstruct", "selector": "D2-green"}
    ], "conditional surface drift")
    require(contract.get("public_surface") == {
        "capitalize": {"kind": "function", "delivery": "string-extra-library"},
        "string-split": {"kind": "function", "delivery": "string-extra-library"},
        "who-calls": {"kind": "function", "delivery": "inspect-library"},
    }, "release surface-extension truth drift")
    require(contract.get("trace_descope") == {
        "status": "not-delivered-in-v1.4.0",
        "names": ["trace", "untrace"],
        "reason": "exact restoration is not representable on the delivered Link-92 ABI",
        "restart": "explicit core-ABI block with a function-cell getter or journal old-value exposure plus atomic publication/restoration",
        "authority": "tests/bytecode/dialect-v2/evidence/architecture-blocks/c2.3-v1.12-link92-r5-trace-fix-library-scope.json",
    }, "trace/untrace descope contract drift")
    require(contract.get("promotion") == {
        "compiler_overlay": "lib/dialect-v2/lcc-locality.lisp",
        "compiler_generator": "tools/host-lisp/c2_v112_product_compiler_tier.py",
        "compiler_suite": "build/post-promotion/v112/compiler-tier/suite.json",
        "compiler_manifest": "build/post-promotion/v112/compiler/lcc.manifest.json",
        "string_extra_manifest": (
            "build/post-promotion/v112/string-extra/string-extra.manifest.json"
        ),
        "inspect_manifest": "build/post-promotion/v112/inspect/inspect.manifest.json",
        "defstruct_manifest": (
            "build/post-promotion/v110-performance/"
            "defstruct-candidate.manifest.json"
        ),
        "freight_receipt": (
            "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
            "c2.3-v1.12-release-freight-receipt.json"
        ),
    }, "release promotion closure drift")
    selector = contract.get("selector", {})
    require(selector.get("allowed_states") == ["pending", "base", "defstruct"]
            and selector.get("state") in selector["allowed_states"]
            and selector.get("d2_required_for_defstruct") is True
            and selector.get("invalid_or_setup_red_blocks_selection") is True
            and selector.get("structural_price_seconds") == 179
            and selector.get("structural_price_is_completion_upper_bound") is False
            and selector.get("minimum_quiet_floor_seconds") >= 180
            and selector.get("selected_media_sha256")
            == "1a77a2f5d71c58ef8e9650316d7d0103675fd419b5aa96d37e8f44e7b24186b7"
            and selector.get("selection_authority")
            == "tests/bytecode/dialect-v2/evidence/architecture-blocks/c2.3-v1.12-link92-r5-phase-d-d2-device-receipt.json"
            and selector.get("decision") == "base-selected-defstruct-not-delivered"
            and "no infinite-hang" in selector.get("d2_red_claim", ""),
            "conditional selector/claim drift")
    media = contract.get("media", {})
    require(media.get("allowed_variant_delta") == [
        "defstruct library artifact",
        "defstruct index row",
        "conditional surface selection metadata",
    ] and media.get("shared_roles_must_be_byteidentical") is True
       and media.get("only_selected_variant_may_ship") is True,
       "two-variant identity contract drift")
    require(contract.get("out_of_scope") == [
        "parity primitives", "tick hook", "ownership retry", "$91 repair",
        "new string converters", "new product feature outside the commissioned freight",
    ], "scope-freeze exclusion drift")
    require(contract.get("a1") == {
        "preferred_exception_list": [],
        "calendar_exception_requires_exact_dated_rebind": True,
        "category_wide_calendar_exception_forbidden": True,
    }, "A1 exception policy drift")


def audit_authorities(contract: dict[str, Any]) -> dict[str, Any]:
    paths = {key: ROOT / raw for key, raw in contract["authorities"].items()}
    values = {key: load(path) for key, path in paths.items()
              if path.suffix == ".json"}
    combined = values["combined_development_receipt"]
    v110 = values["persistent_performance_receipt"]
    v111 = values["compiler_locality_receipt"]
    trace_descope = values["trace_descope_receipt"]
    editor = values["editor_allocation_receipt"]
    physical = values["editor_physical_64_of_64_receipt"]
    require(combined.get("status") == "passed-host-only-development-material"
            and combined.get("artifact", {}).get("functions") == 10
            and combined.get("artifact", {}).get("source_cases") == 13
            and combined.get("who_calls", {}).get("unique_edges") == 109
            and combined.get("mutations", {}).get("count") == 17,
            "combined development authority drift")
    require(v110.get("status") == "HOST-CLOSED-MATERIAL-REDUCTION; HEADLINE-NOT-REACHED"
            and v110.get("host_execution", {}).get("behavior_projection", {}).get("C2J") == "CLEAR"
            and len(v110.get("mutations_rejected", {})) == 22,
            "1.10 authority drift")
    require(
        trace_descope.get("status")
        == "descope-required-missing-function-cell-capability"
        and trace_descope.get("scope_disposition", {}).get("prebound_edge")
        == "triggered"
        and trace_descope.get("scope_disposition", {}).get(
            "compiler_or_core_changed") is False,
        "trace descope authority drift",
    )
    price = v111.get("pricing", {})
    require(v111.get("status") == "HOST-CLOSED; POST-REQUIRE-HEADLINE-REACHED"
            and price.get("full_sequence", {}).get("candidate", {}).get("operational_floor_seconds") == 677
            and price.get("post_require_definition", {}).get("candidate", {}).get("operational_floor_seconds") == 179
            and "not a completion upper bound" in price.get("claim", "")
            and v111.get("freight", {}).get("resident_delta_bytes") == 0
            and v111.get("freight", {}).get("delta", {}).get("external_image_bytes") == -336
            and len(v111.get("mutations_rejected", {})) == 29,
            "1.11 authority drift")
    require(editor.get("status") == "passed", "editor allocation authority drift")
    rider = physical.get("rider_1_physical_editor", {})
    require(rider.get("result") == "passed-64-physical-keys-persisted-64"
            and rider.get("active_window", {}).get("physical_keys") == 64
            and rider.get("active_window", {}).get("monitor_accesses") == 0
            and rider.get("postcondition", {}).get("fill") == 64,
            "physical 64/64 editor authority drift")
    for raw in contract["consumers"]:
        path = ROOT / raw
        require(path.is_file() and not path.is_symlink(), f"consumer absent: {raw}")
    issues = (ROOT / "docs/known-issues.md").read_text(encoding="utf-8")
    require("Not delivered in 1.4.0: `defstruct`" in issues
            and "Editor transport finding: physical 64/64" in issues,
            "known-issues source rows absent")
    return {key: bind(path) for key, path in paths.items()}


def audit_state(contract: dict[str, Any], surface: dict[str, Any]) -> dict[str, Any]:
    state = contract["integration_state"]
    selector = contract["selector"]["state"]
    media = contract["media"]
    names = surface_map(surface)
    expected_kinds = {row["name"]: row["kind"]
                      for row in contract["unconditional_surface"]}
    expected_kinds["defstruct"] = "macro"
    if state == "closure-only":
        require(selector == "pending", "Phase-A selector must be pending")
        require(all(name not in names for name in (*FREIGHT, *CONDITIONAL)),
                "closure-only state leaked a commissioned surface name")
        require(all(media[key] is None for key in (
            "shared_product_core", "base_manifest", "defstruct_acceptance_manifest")),
            "closure-only state bound premature media")
    else:
        extensions = contract["public_surface"]
        require(all(extensions.get(name, {}).get("kind") == expected_kinds[name]
                    for name in FREIGHT),
                "integrated split-library surface is incomplete or mistyped")
        require(all(name not in names for name in FREIGHT),
                "split-library extension acquired a second canonical surface truth")
        if selector == "defstruct":
            require(state == "selected" and names.get("defstruct") == "macro",
                    "defstruct surface escaped the green selector")
        else:
            require("defstruct" not in names,
                    "defstruct surface present without D2-green selection")
        if state in ("media-closed", "selected"):
            require(all(isinstance(media[key], str) and media[key]
                        for key in ("shared_product_core", "base_manifest",
                                    "defstruct_acceptance_manifest")),
                    "closed media identities absent")
        if state == "host-integrated":
            require(selector == "pending", "host integration selected media early")
    return {
        "integration_state": state,
        "selector": selector,
        "surface_names_before_release": len(names) + (len(FREIGHT) if state != "closure-only" else 0),
        "split_library_public": (sorted(FREIGHT) if state != "closure-only" else []),
        "defstruct_public": "defstruct" in names,
    }


def build(contract_override: dict[str, Any] | None = None,
          surface_override: dict[str, Any] | None = None,
          source_overrides: dict[str, str] | None = None) -> dict[str, Any]:
    contract = deepcopy(contract_override) if contract_override is not None else load(CONTRACT)
    audit_contract(contract)
    authorities = audit_authorities(contract)
    surface = deepcopy(surface_override) if surface_override is not None else load(
        ROOT / contract["authorities"]["public_surface"])
    definitions = source_definitions(contract, source_overrides)
    expected = {row["name"]: row["kind"] for row in contract["unconditional_surface"]}
    expected["defstruct"] = "macro"
    require({name: row["kind"] for name, row in definitions.items()} == expected,
            "source kind and commissioned surface kind disagree")
    state = audit_state(contract, surface)
    promotion = {}
    if contract["integration_state"] != "closure-only":
        for key, raw in contract["promotion"].items():
            promotion[key] = bind(ROOT / raw)
    commits = {key: git_bind(value) for key, value in contract["owner_commits"].items()}
    gate_text = GATES.read_text(encoding="utf-8")
    require("c2-v112-release-closure-check" in gate_text
            and "check-source: c2-v112-release-closure-check" in gate_text,
            "release closure is not permanent in check-source")
    return {
        "format": FORMAT,
        "recorded_on": contract["recorded_on"],
        "status": "passed-v1.12-release-closure-" + state["integration_state"],
        "scope": contract["scope"],
        "state": state,
        "surface_contract": {
            "unconditional": list(FREIGHT),
            "conditional": list(CONDITIONAL),
            "d2_red_is_delivery_only": True,
            "structural_price_is_completion_upper_bound": False,
        },
        "source_definitions": definitions,
        "consumer_count": len(contract["consumers"]),
        "consumers": list(contract["consumers"]),
        "out_of_scope": list(contract["out_of_scope"]),
        "a1_policy": contract["a1"],
        "authorities": authorities,
        "promotion": promotion,
        "owner_commits": commits,
        "gate": bind(DRIVER),
        "contract": bind(CONTRACT),
        "claim_limit": (
            "Release-scope, host-integration and selector closure only. This "
            "creates no media, device, product-link or release claim."
        ),
    }


def rejected(label: str, action: Callable[[], None], results: dict[str, str]) -> None:
    try:
        action()
    except ClosureError as error:
        results[label] = str(error)
    else:
        raise ClosureError(f"release-closure mutation survived: {label}")


def selftest() -> dict[str, str]:
    contract = load(CONTRACT)
    surface = load(ROOT / contract["authorities"]["public_surface"])
    results: dict[str, str] = {}

    def mutate_contract(label: str, path: tuple[str, ...], value: Any) -> None:
        changed = deepcopy(contract)
        cursor: Any = changed
        for key in path[:-1]:
            cursor = cursor[key]
        cursor[path[-1]] = value
        rejected(label, lambda: build(changed, surface), results)

    mutate_contract("scope:second-product-core", ("scope", "product_cores"), 2)
    mutate_contract("scope:resident-byte", ("scope", "resident_delta_bytes"), 1)
    mutate_contract("selector:price-as-upper-bound",
                    ("selector", "structural_price_is_completion_upper_bound"), True)
    mutate_contract("selector:short-quiet-floor",
                    ("selector", "minimum_quiet_floor_seconds"), 179)
    mutate_contract("selector:defstruct-against-red-D2", ("selector", "state"), "defstruct")
    mutate_contract("selector:wrong-selected-media", ("selector", "selected_media_sha256"), "0" * 64)
    mutate_contract("A1:blanket-calendar-exception",
                    ("a1", "category_wide_calendar_exception_forbidden"), False)
    mutate_contract("media:shared-role-divergence",
                    ("media", "shared_roles_must_be_byteidentical"), False)
    changed = deepcopy(contract)
    changed["unconditional_surface"].append({"kind": "macro", "name": "trace"})
    rejected("descope:trace-surface-reintroduced",
             lambda: build(changed, surface), results)
    changed = deepcopy(contract)
    changed["public_surface"]["untrace"] = {
        "kind": "macro", "delivery": "inspect-library"}
    rejected("descope:untrace-delivery-reintroduced",
             lambda: build(changed, surface), results)
    mutate_contract("scope:parity-rides-release", ("out_of_scope",),
                    contract["out_of_scope"][:-1])
    changed_surface = deepcopy(surface)
    changed_surface["definitions"].append(
        {"kind": "macro", "name": "defstruct", "visibility": "public"})
    rejected("surface:defstruct-leaked-before-D2",
             lambda: build(contract, changed_surface), results)
    changed_surface = deepcopy(surface)
    changed_surface["definitions"].append(
        {"kind": "function", "name": "who-calls", "visibility": "public"})
    rejected("surface:split-library-leaked-before-integration",
             lambda: build(contract, changed_surface), results)
    bad_sources = {
        "capitalize": (ROOT / contract["sources"]["capitalize"])
        .read_text(encoding="utf-8").replace("(defun capitalize", "(defun cap-lost", 1)
    }
    rejected("source:commissioned-name-absent",
             lambda: build(contract, surface, bad_sources), results)
    require(len(results) == 14, "release-closure selftest count drift")
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("selftest", "write", "check"))
    args = parser.parse_args()
    try:
        if args.action == "selftest":
            mutations = selftest()
            print(f"c2-v112-release-closure: SELFTEST PASS mutations={len(mutations)}")
            return 0
        value = build()
        mutations = selftest()
        value["mutations_rejected"] = mutations
        value["mutation_count"] = len(mutations)
        if args.action == "write":
            RECEIPT.write_text(canonical(value), encoding="utf-8")
        else:
            require(RECEIPT.is_file(), "release-closure receipt absent")
            require(load(RECEIPT) == value, "release-closure receipt drift")
        print(
            "c2-v112-release-closure: PASS "
            f"state={value['state']['integration_state']} "
            f"split-library={len(value['surface_contract']['unconditional'])} "
            f"conditional={len(value['surface_contract']['conditional'])} "
            f"mutations={len(mutations)}"
        )
        return 0
    except (ClosureError, OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        print(f"c2-v112-release-closure: FIRST RED: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
