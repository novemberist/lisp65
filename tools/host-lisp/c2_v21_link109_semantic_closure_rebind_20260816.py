#!/usr/bin/env python3
"""Replace Link-109 aggregate drift with a semantic, commit-bound closure."""

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

import evidence_era as ERA  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.1-cpu-transport-work-plan.md"
OLD_LINK109 = ARCH / (
    "c2.3-v2.1-reopen-gap-attribution-phase9-abi-rebind-20260815-receipt.json")
DOMAIN_SPLIT = ARCH / (
    "c2.3-v2.1-phase9-domain-split-source-rebind-20260815-receipt.json")
SERVICE_END_REBIND = ARCH / (
    "c2.3-v2.1-phase9-domain-split-source-rebind-20260816-receipt.json")
SERVICE_END_ATTRIBUTION = ARCH / (
    "c2.3-v2.1-phase9-service-end-dependency-attribution-receipt.json")
MAP_REBIND = ARCH / (
    "c2.3-v2.1-map-mask-fix-phase9-abi-rebind-receipt.json")
RELOCATION_EMISSION = ARCH / (
    "c2.3-v2.1-phase9-relocation-emission-receipt.json")
FULL_SPAN = ARCH / "c2.3-v2.1-full-span-convergence-receipt.json"
ABI_PAIRING = ARCH / "c2.3-v2.1-abi-vocabulary-pairing-receipt.json"
ABI_CONTRACT = ROOT / "config/c2-mapped-far-abi-preservation-contract-v2.json"
FAR_SOURCE = ROOT / "src/c2_mapped_far_convergence.s"
READER_SOURCE = ROOT / "src/optional/c2_map_cpu_read.s"
ABI_GATE = HOST / "c2_asm_leaf_abi_gate.py"
SERVICE_GATE = HOST / "c2_mapped_far_service_gate.py"
EQUIVALENCE_GATE = HOST / "c2_mapped_far_asm_equivalence.py"
GATES = ROOT / "mk/gates.mk"
RECEIPT = ARCH / (
    "c2.3-v2.1-link109-semantic-closure-rebind-20260816-receipt.json")
DRIVER = Path(__file__).resolve()
AUTHORIZATION = "b2c5c3e8"
SEAL_ERA_COMMIT = "ab2d433392a555a70bb4742a54648bfa0ddea827"
SEALED_MUTATIONS = [
    "drop-semantic-input", "restore-global-count", "restore-living-plan",
    "drop-freight-successor", "rewrite-history", "merge-ABI-domains",
    "lose-service-exit", "fix-freight-end", "run-product-link",
]

HISTORICAL_SHA256 = {
    "Link109": "b714b8eaf12a5476f5b69ac45b7a53863830390d27697f6f325816666bbba3d4",
    "domain_split": "dba4d2c5e23e2b99aec75dd08f7063698172ff7d771da128a333a8137627df77",
    "service_end_rebind": "48cc31c693e3e30bb849e2e924ab70e658e7058bec428df19f8e7b1abaa91a08",
    "service_end_attribution": "0f7522afeff5e7d04a9e850dbeea990f8baf3febadccc2a2209a2e2a9bc04bde",
}


class RebindError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise RebindError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"input absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def git_bind(commit: str, path: Path) -> dict[str, Any]:
    name = path.relative_to(ROOT).as_posix()
    full = subprocess.run(
        ["git", "rev-parse", f"{commit}^{{commit}}"], cwd=ROOT, check=True,
        text=True, stdout=subprocess.PIPE).stdout.strip()
    raw = subprocess.run(
        ["git", "show", f"{full}:{name}"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE).stdout
    return {"authority": "git-blob", "commit": full, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def authorization() -> dict[str, Any]:
    authority = git_bind(AUTHORIZATION, PLAN)
    raw = subprocess.run(
        ["git", "show", f"{authority['commit']}:{authority['path']}"],
        cwd=ROOT, check=True, stdout=subprocess.PIPE).stdout
    text = " ".join(raw.decode().lower().split())
    for token in ("link-109 closure successor approved",
                  "semantic input inventory", "commit-bound documents",
                  "global file count", "historical receipts stay untouched"):
        require(token in text, f"Link-109 closure authority absent: {token}")
    return authority


def historical_closure() -> dict[str, Any]:
    paths = {"Link109": OLD_LINK109, "domain_split": DOMAIN_SPLIT,
             "service_end_rebind": SERVICE_END_REBIND,
             "service_end_attribution": SERVICE_END_ATTRIBUTION}
    for name, path in paths.items():
        require(bind(path)["sha256"] == HISTORICAL_SHA256[name],
                f"historical {name} receipt was rewritten")
    link109 = load(OLD_LINK109)
    domain = load(DOMAIN_SPLIT)
    end_rebind = load(SERVICE_END_REBIND)
    end_attr = load(SERVICE_END_ATTRIBUTION)
    require(
        link109.get("status") ==
            "PASS: LOUD LINK109 PHASE9-ABI SOURCE-CLOSURE REBIND"
        and link109.get("result", {}).get("gap0") == "derived"
        and link109.get("result", {}).get("gap1") == "derived"
        and link109.get("result", {}).get("gap2") == "fixed"
        and domain.get("status") ==
            "PASS: LOUD PHASE9 DOMAIN-SPLIT SOURCE-CLOSURE REBIND"
        and set(domain.get("gate_domains", {})) == {
            "C_reachable_ASM_closure", "contractual_service_exits"}
        and domain["gate_domains"]["contractual_service_exits"]
            ["exit_count"] == 8
        and end_rebind.get("status") ==
            "PASS: LOUD SERVICE-END PLAN-AUTHORITY SOURCE REBIND"
        and end_rebind.get("semantic_projection", {}).get(
            "service_end_class") == "freight-derived"
        and end_rebind.get("semantic_projection", {}).get(
            "service_load_end_class") == "freight-derived"
        and end_attr.get("status") ==
            "ATTRIBUTED: mapped-far end symbols have no fixed-address dependent",
        "historical Link-109 semantic closure drift")
    return {name: bind(path) for name, path in paths.items()}


def semantic_inputs() -> list[dict[str, Any]]:
    rows = [
        ("mapped-far-ABI-contract", "ABI preservation contract", ABI_CONTRACT),
        ("mapped-far-service-source", "emitted service implementation", FAR_SOURCE),
        ("MAP-CPU-reader-source", "mapped CPU transport implementation", READER_SOURCE),
        ("transitive-ABI-gate", "C-reachable ASM closure", ABI_GATE),
        ("mapped-far-service-gate", "eight contractual exits", SERVICE_GATE),
        ("assembly-equivalence-gate", "service semantic equivalence", EQUIVALENCE_GATE),
        ("MAP-semantic-rebind", "decoded MAP tuple authority", MAP_REBIND),
        ("relocation-emission", "candidate-derived relocation freight", RELOCATION_EMISSION),
        ("full-span-successor", "partial-transfer-safe convergence", FULL_SPAN),
        ("ABI-vocabulary-pairing", "producer/consumer status identity", ABI_PAIRING),
    ]
    tool_paths = {ABI_GATE, SERVICE_GATE, EQUIVALENCE_GATE}
    result = [{"id": name, "role": role,
               "identity": (ERA.era_bind(SEAL_ERA_COMMIT, path)
                            if path in tool_paths else bind(path))}
              for name, role, path in rows]
    require(len(result) == 10 and len({row["id"] for row in result}) == 10,
            "Link-109 semantic input inventory is incomplete")
    return result


def source_gate(source_override: str | None = None) -> dict[str, Any]:
    driver = DRIVER.read_text(encoding="utf-8") \
        if source_override is None else source_override
    tree = ast.parse(driver)
    governing = "\n".join(ast.unparse(node) for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name in {"authorization", "semantic_inputs", "derive"})
    require("current_tracked_files" not in governing
            and "tracked_text_files" not in governing
            and "bind(PLAN)" not in governing
            and "git_bind(AUTHORIZATION, PLAN)" in governing,
            "Link-109 successor retains aggregate or living-plan authority")
    gates = GATES.read_text(encoding="utf-8")
    retired = (
        "python3 tools/host-lisp/"
        "c2_v21_reopen_gap_attribution_rebind_phase9_abi_20260815.py check",
        "python3 tools/host-lisp/"
        "c2_v21_phase9_domain_split_source_rebind_20260816.py check",
        "python3 tools/host-lisp/"
        "c2_v21_phase9_service_end_dependency_attribution.py check",
    )
    require(not any(command in gates for command in retired),
            "historical Link-109 reconstruction remains in the live gate")
    successor = (
        "python3 tools/host-lisp/"
        "c2_v21_link109_semantic_closure_rebind_20260816.py check")
    require(gates.count(successor) >= 2,
            "Link-109 semantic successor absent from live gate")
    freight_successor = successor.removesuffix(" check") + " freight-check"
    require(gates.count(freight_successor) == 1,
            "freight-boundary consumer is not successor-routed")
    return {"status": "PASS: semantic successor is the sole live closure",
            "aggregate_file_counts": 0, "living_plan_bindings": 0,
            "historical_reconstruction_commands": 0,
            "successor_check_commands": gates.count(successor),
            "freight_successor_checks": gates.count(freight_successor)}


def derive() -> dict[str, Any]:
    history = historical_closure()
    inputs = semantic_inputs()
    return {
        "format": "lisp65-c2.3-v21-link109-semantic-closure-rebind-v1",
        "recorded_on": "2026-08-16",
        "status": "PASS: Link-109 closure is semantic and commit-bound",
        "authority": {"owner": authorization(),
                      "driver": ERA.era_bind(SEAL_ERA_COMMIT, DRIVER),
                      "historical_receipts": history},
        "semantic_inputs": inputs,
        "semantic_input_count": len(inputs),
        "documents": {"owner_plan": authorization()},
        "semantic_projection": {
            "gap0": "derived", "gap1": "derived", "gap2": "fixed",
            "ABI_gate_domains": ["C_reachable_ASM_closure",
                                 "contractual_service_exits"],
            "contractual_service_exit_count": 8,
            "service_end": "freight-derived",
            "service_load_end": "freight-derived",
            "historical_receipts_changed": False,
            "product_artifacts_changed": False},
        "live_gate": source_gate(),
        "execution_lock": {"WPLTO_runs": 0, "product_links": 0,
            "cards_consumed": 0, "completion_runs": 0,
            "media_builds": 0, "device_contacts": 0},
        "claim_limit": (
            "Closure-authority successor only. Historical receipts remain "
            "unchanged; no product, media or device action."),
    }


def validate(value: dict[str, Any]) -> None:
    projection = value.get("semantic_projection", {})
    inputs = {row.get("id"): row.get("identity")
              for row in value.get("semantic_inputs", [])}
    require(
        value.get("status") ==
            "PASS: Link-109 closure is semantic and commit-bound"
        and value.get("semantic_input_count") == 10
        and len(value.get("semantic_inputs", [])) == 10
        and len({row["id"] for row in value["semantic_inputs"]}) == 10
        and value.get("documents", {}).get("owner_plan", {}).get(
            "authority") == "git-blob"
        and projection == {
            "gap0": "derived", "gap1": "derived", "gap2": "fixed",
            "ABI_gate_domains": ["C_reachable_ASM_closure",
                                 "contractual_service_exits"],
            "contractual_service_exit_count": 8,
            "service_end": "freight-derived",
            "service_load_end": "freight-derived",
            "historical_receipts_changed": False,
            "product_artifacts_changed": False}
        and value["live_gate"] == {
            "status": "PASS: semantic successor is the sole live closure",
            "aggregate_file_counts": 0, "living_plan_bindings": 0,
            "historical_reconstruction_commands": 0,
            "successor_check_commands": 2,
            "freight_successor_checks": 1}
        and not any(value["execution_lock"].values()),
        "Link-109 semantic closure rebind drift")
    require(value.get("authority", {}).get("driver") ==
            ERA.era_bind(SEAL_ERA_COMMIT, DRIVER)
            and inputs.get("transitive-ABI-gate") ==
            ERA.era_bind(SEAL_ERA_COMMIT, ABI_GATE)
            and inputs.get("mapped-far-service-gate") ==
            ERA.era_bind(SEAL_ERA_COMMIT, SERVICE_GATE)
            and inputs.get("assembly-equivalence-gate") ==
            ERA.era_bind(SEAL_ERA_COMMIT, EQUIVALENCE_GATE),
            "Link-109 tool provenance escaped its sealing era")


def mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "drop-semantic-input": lambda x: x["semantic_inputs"].pop(),
        "restore-global-count": lambda x: x["live_gate"].update(
            aggregate_file_counts=1),
        "restore-living-plan": lambda x: x["live_gate"].update(
            living_plan_bindings=1),
        "drop-freight-successor": lambda x: x["live_gate"].update(
            freight_successor_checks=0),
        "rewrite-history": lambda x: x["semantic_projection"].update(
            historical_receipts_changed=True),
        "merge-ABI-domains": lambda x: x["semantic_projection"].update(
            ABI_gate_domains=["all-ASM"]),
        "lose-service-exit": lambda x: x["semantic_projection"].update(
            contractual_service_exit_count=7),
        "fix-freight-end": lambda x: x["semantic_projection"].update(
            service_end="fixed"),
        "run-product-link": lambda x: x["execution_lock"].update(
            product_links=1),
        "collapse-era-to-live": lambda x: next(
            row for row in x["semantic_inputs"]
            if row["id"] == "mapped-far-service-gate").update(
                identity=ERA.era_bind("HEAD", SERVICE_GATE)),
        "restore-working-tree-binding": lambda x: x["authority"].update(
            driver=bind(DRIVER)),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        trial = deepcopy(value); mutate(trial)
        try:
            validate(trial)
        except RebindError:
            rejected.append(name)
    require(rejected == list(cases), "Link-109 closure mutation survived")
    return rejected


def write() -> None:
    require(not RECEIPT.exists(), "Link-109 semantic closure receipt exists")
    value = derive(); validate(value)
    value["mutations_rejected"] = mutations(value)
    RECEIPT.write_bytes(canonical(value))
    print("Link-109 semantic closure: PASS inputs=10 counts=0 living-plan=0")


def check() -> None:
    value = load(RECEIPT); rejected = value.pop("mutations_rejected", None)
    validate(value); expected = derive(); validate(expected)
    require(value == expected and rejected == SEALED_MUTATIONS,
            "Link-109 semantic closure receipt drift")
    require(len(mutations(value)) == 11,
            "live Link-109 era mutations did not run")
    print("Link-109 semantic closure: CHECK PASS history=unchanged inputs=10")


def selftest() -> None:
    value = derive(); validate(value)
    require(len(mutations(value)) == 11, "Link-109 closure mutation drift")
    mutant = DRIVER.read_text(encoding="utf-8").replace(
        "git_bind(AUTHORIZATION, PLAN)", "bind(PLAN)", 1)
    try:
        source_gate(mutant)
    except RebindError:
        pass
    else:
        raise RebindError("living-plan source mutation survived")
    print("Link-109 semantic closure: SELFTEST PASS mutations=12")


def freight_check() -> None:
    import c2_v21_phase9_freight_boundary_golden as freight

    original = freight.dependency_authority

    def successor_authority(*, verify: bool) -> dict[str, Any]:
        if verify:
            check()
        return freight.bind(SERVICE_END_ATTRIBUTION)

    freight.dependency_authority = successor_authority
    try:
        freight.check()
    finally:
        freight.dependency_authority = original


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action", choices=("write", "check", "selftest", "freight-check"))
    {"write": write, "check": check, "selftest": selftest,
     "freight-check": freight_check}[
        parser.parse_args().action]()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"Link-109 semantic closure: RED: {error}", file=sys.stderr)
        raise SystemExit(2)
