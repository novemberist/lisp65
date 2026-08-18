#!/usr/bin/env python3
"""Run the one-card 2.0 ownership recharter.

The producer combines the current v1.5 freight, the mandatory F018B
content-convergence routes and the already-owned full-map linker.  Acceptance
is deliberately smaller than production: exactly one canonical candidate ELF
layout comparison against the reviewed SHA-bound golden artifact.
"""

from __future__ import annotations

import argparse
import ast
import contextlib
from copy import deepcopy
from datetime import date
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_f018b_content_safe_reads as SAFE  # noqa: E402
import c2_golden_layout_inversion as GOLD  # noqa: E402
import c2_lite_v6_product_probe as V6  # noqa: E402
import c2_product_substitution_link as PRODUCT  # noqa: E402
import c2_v150_candidate_product as BASE  # noqa: E402
import c2_v150_f018b_fix_card as FIX  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
CHARTER = ROOT / "docs/planning/2.0-ownership-recharter-work-plan.md"
CHARTER_COMMIT = "f50f4714bb998526dc371aed16480e17a832f013"
BUILD = ROOT / "build/c2.3/v2.0-ownership-recharter-card"
PREFLIGHT = ROOT / "build/c2.3/v2.0-ownership-recharter-preflight"
PREFLIGHT_RECEIPT = PREFLIGHT / "preflight.json"
INPUTS = ROOT / "build/c2.3/v2.0-ownership-recharter-inputs"
CANDIDATE_PROFILE = INPUTS / "candidate-profile.json"
CANDIDATE_CONTRACT = INPUTS / "c2-lite-execution-contract.json"
CANDIDATE_HEADER = INPUTS / "c2_lite_static_plane.h"
INVOCATION = PREFLIGHT / "card-invocation.json"
RECEIPT = EVIDENCE / "c2.3-v2.0-ownership-recharter-card-receipt.json"
FINAL_RED = EVIDENCE / "c2.3-v2.0-ownership-recharter-card-final-red.json"
DRIVER = Path(__file__).resolve()
LINK = 99
FORMAT = "lisp65-c2.3-v20-ownership-recharter-card-v1"
RECORDED_ON = date.today().isoformat()


class RecharterError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise RecharterError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(),
            f"regular JSON authority absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(),
            f"regular authority absent: {path}")
    raw = path.read_bytes()
    return {
        "path": path.resolve().relative_to(ROOT.resolve()).as_posix(),
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def run(command: list[str], label: str) -> dict[str, Any]:
    result = subprocess.run(
        command, cwd=ROOT, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, check=False)
    require(result.returncode == 0, f"{label} red:\n{result.stdout}")
    raw = result.stdout.encode()
    return {
        "status": "passed", "output_bytes": len(raw),
        "output_sha256": hashlib.sha256(raw).hexdigest(),
    }


def commission_binding() -> dict[str, Any]:
    value = GOLD.git_binding(
        CHARTER_COMMIT, CHARTER.relative_to(ROOT).as_posix())
    raw = subprocess.run(
        ["git", "show", f"{CHARTER_COMMIT}:{value['path']}"], cwd=ROOT,
        check=True, stdout=subprocess.PIPE).stdout
    require(
        b"One product card carrying" in raw
        and b"golden comparison is the only acceptance authority" in raw
        and b"One card. A red of any kind" in raw,
        "2.0 one-card owner commission is not bound")
    return value


def configure_projection_paths() -> None:
    FIX.PROFILE_ROOT = INPUTS
    FIX.CANDIDATE_PROFILE = CANDIDATE_PROFILE
    FIX.CANDIDATE_CONTRACT = CANDIDATE_CONTRACT
    FIX.CANDIDATE_HEADER = CANDIDATE_HEADER


def validate_input_closure(value: dict[str, Any]) -> None:
    authorities = value.get("authorities", {})
    require(
        value.get("format") == "lisp65-c2.3-v20-producer-input-closure-v1"
        and value.get("status") == "PASS: producer inputs closed before card"
        and value.get("execution_accounting") == {
            "wplto_runs": 0, "product_links": 0, "device_contacts": 0}
        and authorities.get("owner_commission") == commission_binding()
        and authorities.get("golden") == bind(GOLD.GOLDEN)
        and authorities.get("golden_review") == bind(GOLD.RECEIPT)
        and authorities.get("v1.5_preflight") == bind(BASE.PRE.RECEIPT)
        and authorities.get("v1.5_freight_closure")
            == bind(BASE.CLOSURE.RECEIPT)
        and authorities.get("candidate_profile") == bind(CANDIDATE_PROFILE)
        and authorities.get("candidate_contract") == bind(CANDIDATE_CONTRACT)
        and authorities.get("candidate_header") == bind(CANDIDATE_HEADER)
        and authorities.get("full_map_contract")
            == bind(PRODUCT.FULL_MAP_OWNERSHIP_CONTRACT)
        and authorities.get("f018b_contract") == bind(SAFE.CONTRACT)
        and authorities.get("f018b_pricing") == bind(SAFE.RECEIPT)
        and authorities.get("driver") == bind(DRIVER)
        and value.get("acceptance") == {
            "authority": "SHA-bound reviewed golden layout",
            "comparison_operations": 1,
            "historical_postlink_qualifiers": 0,
        },
        "2.0 producer input closure drift")


def input_mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "drop-golden": lambda x: x["authorities"].pop("golden"),
        "detach-charter": lambda x: x["authorities"]["owner_commission"].update(
            sha256="0" * 64),
        "consume-historical-profile": lambda x: x["authorities"].update(
            candidate_profile=bind(FIX.HISTORICAL_PROFILE)),
        "drop-real-consumer": lambda x: x["host_gates"].pop(
            "real_projected_profile_consumer"),
        "add-historical-acceptor": lambda x: x["acceptance"].update(
            historical_postlink_qualifiers=1),
        "claim-a-card": lambda x: x["execution_accounting"].update(
            wplto_runs=1),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        candidate = deepcopy(value)
        mutate(candidate)
        try:
            validate_input_closure(candidate)
            require("real_projected_profile_consumer" in candidate["host_gates"],
                    "real projected-profile consumer absent")
        except RecharterError:
            rejected.append(name)
    require(rejected == list(cases), "2.0 producer-input mutation survived")
    return rejected


PATH_FUNCTIONS = {"produce_candidate", "card"}
FORBIDDEN_ACCEPTORS = {
    "postlink", "guard_result", "check", "linked_gates",
    "replacement_gates", "fresh_current_product_postlink_gate",
    "full_map_layout", "complete_in_fresh_process",
}


def call_tail(node: ast.Call) -> str:
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return ""


def audit_card_path(source: str | None = None) -> dict[str, Any]:
    text = DRIVER.read_text(encoding="utf-8") if source is None else source
    tree = ast.parse(text)
    functions = {
        node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)
    }
    require(PATH_FUNCTIONS <= functions.keys(), "2.0 card-path function absent")
    golden = 0
    forbidden: list[str] = []
    for name in sorted(PATH_FUNCTIONS):
        for node in ast.walk(functions[name]):
            if not isinstance(node, ast.Call):
                continue
            tail = call_tail(node)
            if tail == "compare_elf":
                golden += 1
            if tail in FORBIDDEN_ACCEPTORS:
                forbidden.append(f"{name}:{tail}")
    require(golden == 1, "2.0 card must contain exactly one golden comparison")
    require(not forbidden,
            f"non-golden acceptance call present in card path: {forbidden}")
    return {
        "golden_comparisons": golden,
        "non_golden_acceptors": 0,
        "path_functions": sorted(PATH_FUNCTIONS),
    }


def path_mutations() -> list[str]:
    source = DRIVER.read_text(encoding="utf-8")
    anchor = "comparison = GOLD.compare_elf(artifacts[\"elf\"])"
    require(source.count(anchor) == 1, "golden comparison mutation anchor drift")
    cases = {
        "remove-golden": source.replace(
            anchor, "comparison = GOLD.layout_from_elf(artifacts[\"elf\"])", 1),
        "double-golden": source.replace(anchor, anchor + "\n    " + anchor, 1),
        "add-content-postlink": source.replace(
            anchor, "SAFE.postlink(artifacts[\"elf\"])\n    " + anchor, 1),
        "add-historical-check": source.replace(
            anchor, "BASE.L95.CAN.check()\n    " + anchor, 1),
    }
    rejected: list[str] = []
    for name, mutant in cases.items():
        try:
            audit_card_path(mutant)
        except RecharterError:
            rejected.append(name)
    require(rejected == list(cases), "2.0 card-path mutation survived")
    return rejected


def host_gates() -> dict[str, Any]:
    review = GOLD.build_receipt()
    require(GOLD.canonical(review) == GOLD.canonical(load(GOLD.RECEIPT)),
            "reviewed golden receipt drift")
    freight = BASE.freight_gates()
    return {
        "golden_inversion": {
            "status": "passed", "mutations": len(review["mutations_rejected"]),
            "source_order_independent": review["golden"][
                "source_order_independent"],
        },
        "real_projected_profile_consumer": {
            "status": "passed",
            "mutations": 4,
            "real_consumer": "fresh_static_plane_bundle",
        },
        "v1.5_freight": freight,
        "full_map": run([
            sys.executable, "tools/host-lisp/c2_v18_full_map_phase_c.py",
            "check"], "full-map Phase-C gate"),
        "mapped_far": run([
            sys.executable, "tools/host-lisp/c2_mapped_far_service_gate.py"],
            "mapped far-service gate"),
        "mapped_far_equivalence": run([
            sys.executable, "tools/host-lisp/c2_mapped_far_asm_equivalence.py"],
            "mapped far-service equivalence"),
        "f018b_content_safe_reads": run([
            sys.executable, "tools/host-lisp/c2_f018b_content_safe_reads.py",
            "check"], "F018B content-safe-read gate"),
    }


def preflight() -> None:
    require(
        not BUILD.exists() and not PREFLIGHT.exists() and not INPUTS.exists()
        and not RECEIPT.exists() and not FINAL_RED.exists(),
        "2.0 preflight/card is one-shot")
    commission_binding()
    audit_card_path()
    require(path_mutations() == [
        "remove-golden", "double-golden", "add-content-postlink",
        "add-historical-check"], "2.0 card-path mutation set drift")
    configure_projection_paths()
    FIX.write_projection()
    FIX.projection_selftest()
    gates = host_gates()
    PREFLIGHT.mkdir(parents=True)
    value = {
        "format": "lisp65-c2.3-v20-producer-input-closure-v1",
        "recorded_on": RECORDED_ON,
        "status": "PASS: producer inputs closed before card",
        "execution_accounting": {
            "wplto_runs": 0, "product_links": 0, "device_contacts": 0},
        "acceptance": {
            "authority": "SHA-bound reviewed golden layout",
            "comparison_operations": 1,
            "historical_postlink_qualifiers": 0,
        },
        "host_gates": gates,
        "card_path_gate": {
            **audit_card_path(), "mutations_rejected": path_mutations()},
        "authorities": {
            "owner_commission": commission_binding(),
            "live_phasing": bind(CHARTER),
            "golden": bind(GOLD.GOLDEN),
            "golden_review": bind(GOLD.RECEIPT),
            "v1.5_preflight": bind(BASE.PRE.RECEIPT),
            "v1.5_freight_closure": bind(BASE.CLOSURE.RECEIPT),
            "candidate_profile": bind(CANDIDATE_PROFILE),
            "candidate_contract": bind(CANDIDATE_CONTRACT),
            "candidate_header": bind(CANDIDATE_HEADER),
            "full_map_contract": bind(PRODUCT.FULL_MAP_OWNERSHIP_CONTRACT),
            "f018b_contract": bind(SAFE.CONTRACT),
            "f018b_pricing": bind(SAFE.RECEIPT),
            "driver": bind(DRIVER),
        },
        "next": "exactly one product-shaped WPLTO and one golden comparison",
    }
    validate_input_closure(value)
    value["mutations_rejected"] = input_mutations(value)
    PREFLIGHT_RECEIPT.write_bytes(canonical(value))
    print("2.0 ownership recharter: PREFLIGHT PASS "
          "golden-mutations=12 producer-mutations=6 wplto=0 device=0")


def configure_producer() -> dict[str, Path]:
    BASE.LINK = LINK
    BASE.BUILD = BUILD
    BASE.MANIFEST = BUILD / "unused-canonical-product-manifest.json"
    BASE.RECEIPT = BUILD / "unused-product-card-receipt.json"
    BASE.FIRST_RED = FINAL_RED
    BASE.GUARD_RECEIPT = BUILD / "unused-terminal-guard-receipt.json"
    BASE.DRIVER = DRIVER
    BASE.PROFILE = CANDIDATE_PROFILE
    BASE.HEADER = CANDIDATE_HEADER
    plane = BASE.L95.BASE.PROBE.REQ.F1W.PLANE
    plane.CONTRACT = CANDIDATE_CONTRACT
    plane.HEADER = CANDIDATE_HEADER
    PRODUCT.configure_full_map_ownership()
    return BASE.configure(CANDIDATE_PROFILE)


def candidate_oracle_input_paths() -> dict[str, Path]:
    static = BUILD / "static-plane/narrow-static"
    return {
        "product_identity": static / "product/substitution-artifacts.json",
        "shelf": static / "product/product-shelf-v4-direct.bin",
        "c2d": static / "v6-semantics/initial.c2d-v6.bin",
    }


def bind_candidate_oracle_inputs() -> dict[str, Any]:
    """Bind and select the exact candidate delivery world before codegen."""
    paths = candidate_oracle_input_paths()
    rows = {name: bind(path) for name, path in paths.items()}
    V6.OUT = paths["c2d"].parent
    V6.PRODUCT_IDENTITY = paths["product_identity"]
    shelf = V6.canonical_product_shelf_identity()
    require(shelf["shelf"] == rows["shelf"]
            and shelf["authority"] == rows["product_identity"],
            "candidate oracle shelf/product identity cross-binding drift")
    c2d = paths["c2d"].read_bytes()
    require(len(c2d) == V6.C2D_TOTAL_BYTES
            and c2d[:8] == b"C2D\0\x06\x30\x20\x0a",
            "candidate oracle C2D authority drift")
    value = {
        "format": "lisp65-c2.3-v20-candidate-oracle-input-closure-v1",
        "status": "PASS: oracle codegen inputs bound to candidate world",
        "candidate_build": BUILD.relative_to(ROOT).as_posix(),
        "inputs": rows,
        "selected_globals": {
            "V6.OUT": V6.OUT.relative_to(ROOT).as_posix(),
            "V6.PRODUCT_IDENTITY":
                V6.PRODUCT_IDENTITY.relative_to(ROOT).as_posix(),
        },
        "historical_OUT_inputs": 0,
    }
    receipt = BUILD / "receipts/candidate-oracle-input-closure.json"
    require(not receipt.exists(), "candidate oracle input closure is one-shot")
    receipt.parent.mkdir(parents=True, exist_ok=True)
    receipt.write_bytes(canonical(value))
    return value


def candidate_oracle_source_gate(source_override: str | None = None) -> dict[str, Any]:
    """Prove binding occurs before the real WPLTO consumer is configured."""
    source = DRIVER.read_text(encoding="utf-8") \
        if source_override is None else source_override
    binding = '    V6.OUT = paths["c2d"].parent\n'
    identity = '    V6.PRODUCT_IDENTITY = paths["product_identity"]\n'
    call = "    oracle_inputs = bind_candidate_oracle_inputs()\n"
    consumer = "    old = BASE.L95.CAN.configure_wplto()\n"
    require(source.count(binding) == source.count(identity) == 1
            and source.count(call) == source.count(consumer) == 1
            and source.index(binding) < source.index(call)
            and source.index(identity) < source.index(call)
            and source.index(call) < source.index(consumer),
            "candidate oracle input binding escaped the real producer path")
    return {
        "status": "PASS: real producer binds candidate oracle inputs first",
        "candidate_binding_calls": 1,
        "historical_OUT_reads": 0,
        "consumer": "BASE.L95.CAN.configure_wplto",
    }


def candidate_oracle_source_mutations() -> list[str]:
    source = DRIVER.read_text(encoding="utf-8")
    call = "    oracle_inputs = bind_candidate_oracle_inputs()\n"
    cases = {
        "historical-OUT-as-oracle": source.replace(
            '    V6.OUT = paths["c2d"].parent\n',
            "    V6.OUT = ROOT / 'build/c2-lite/product-shaped-v6-probe'\n",
            1),
        "drop-candidate-input-binding": source.replace(call, "", 1),
        "bind-after-real-consumer": source.replace(
            call + "    old = BASE.L95.CAN.configure_wplto()\n",
            "    old = BASE.L95.CAN.configure_wplto()\n" + call, 1),
    }
    rejected: list[str] = []
    for name, candidate in cases.items():
        try:
            candidate_oracle_source_gate(candidate)
        except RecharterError:
            rejected.append(name)
    require(rejected == list(cases),
            "candidate oracle input source mutation survived")
    return rejected


def produce_candidate() -> dict[str, Any]:
    """Emit one candidate mechanically; do not qualify or accept it here."""
    BUILD.mkdir(parents=True)
    shutil.copytree(BASE.PRE.BUILD / "static-plane", BUILD / "static-plane")
    paths = configure_producer()
    static = BASE.L95.BASE.PROBE.REQ.build_static_plane()
    plane = BASE.L95.BASE.PROBE.REQ.F1W.static_gate()
    header = BASE.L95.CORE.bind_generated_stdlib_header(paths)
    expected = BASE.PRE.geometry()["static_code_bytes"]
    require(
        static["semantics"]["code_bytes"] == expected
        and plane["static_code_bytes"] == expected,
        "real current-candidate static-plane consumer red")

    oracle_inputs = bind_candidate_oracle_inputs()
    old = BASE.L95.CAN.configure_wplto()
    output = io.StringIO()
    producer_return: int | None = None
    try:
        with contextlib.redirect_stdout(output):
            producer_return = BASE.L95.CAN.LINK_GATE.BASE.main()
    finally:
        BASE.L95.CAN.restore_wplto(old)
        log = BUILD / "receipts/v20-producer.log"
        log.parent.mkdir(parents=True, exist_ok=True)
        log.write_text(output.getvalue(), encoding="utf-8")

    elf = paths["wplto"] / "lisp65-c2-substitution-linked.prg.elf"
    prg = paths["wplto"] / "lisp65-c2-substitution-linked.prg"
    result_path = BASE.L95.CAN.LINK_GATE.BASE.BASE_RESULT
    require(elf.is_file() and prg.is_file() and result_path.is_file(),
            "producer did not emit the linked candidate artifacts")
    result = load(result_path).get("WPLTO", {})
    require(result.get("product_completed") is True
            and result.get("exception") is None,
            "producer did not mechanically complete the candidate link")
    return {
        "elf": elf,
        "prg": prg,
        "map": paths["wplto"] / "lisp65-c2-substitution-linked.prg.map",
        "lto": paths["wplto"] / "resident-island-seed.prg.lto.o",
        "linker": paths["wplto"] / "c2-substitution.ld",
        "resolved_profile": paths["wplto"] / "resolved-profile.txt",
        "producer_log": log,
        "producer_return": producer_return,
        "target_stdlib_header": header,
        "candidate_oracle_inputs": oracle_inputs,
    }


def card() -> None:
    preflight_value = load(PREFLIGHT_RECEIPT)
    rejected = preflight_value.pop("mutations_rejected", None)
    validate_input_closure(preflight_value)
    require(rejected == input_mutations(preflight_value),
            "2.0 producer-input mutation receipt drift")
    require(preflight_value["authorities"]["driver"] == bind(DRIVER),
            "2.0 driver changed after preflight")
    require(not BUILD.exists() and not INVOCATION.exists()
            and not RECEIPT.exists() and not FINAL_RED.exists(),
            "2.0 product card is one-shot")
    INVOCATION.write_bytes(canonical({
        "format": "lisp65-c2.3-v20-card-invocation-v1",
        "recorded_on": RECORDED_ON,
        "status": "INVOKED: terminal outcome required",
        "owner_commission": commission_binding(),
        "preflight": bind(PREFLIGHT_RECEIPT),
        "driver": bind(DRIVER),
    }))
    artifacts = produce_candidate()
    comparison = GOLD.compare_elf(artifacts["elf"])
    value = {
        "format": FORMAT,
        "recorded_on": RECORDED_ON,
        "status": "PASS: owned v1.5 plus F018B candidate equals golden",
        "attempt_accounting": {
            "cards_authorized": 1, "cards_consumed": 1,
            "wplto_runs": 1, "product_link_attempts": 1,
            "device_contacts": 0,
        },
        "acceptance": {
            **comparison,
            "operations": 1,
            "non_golden_acceptance_operations": 0,
        },
        "producer": {
            "mechanical_completion_only": True,
            "historical_return_nonauthoritative": artifacts["producer_return"],
            "log": bind(artifacts["producer_log"]),
            "resolved_profile": bind(artifacts["resolved_profile"]),
            "target_stdlib_header": artifacts["target_stdlib_header"],
        },
        "artifacts": {
            key: bind(artifacts[key])
            for key in ("elf", "prg", "map", "lto", "linker")},
        "authority": {
            "owner_commission": commission_binding(),
            "golden": bind(GOLD.GOLDEN),
            "preflight": bind(PREFLIGHT_RECEIPT),
            "invocation": bind(INVOCATION),
            "driver": bind(DRIVER),
        },
        "next_gate": "Fresh v1.5 D1-D5 device session; parity remains separate.",
        "claim_limit": (
            "One host-only product card accepted solely by exact golden-layout "
            "equality; no media, device, release, publication or parity claim."),
    }
    RECEIPT.write_bytes(canonical(value))
    print("2.0 ownership recharter: PASS "
          f"sections={comparison['allocatable_sections']} "
          f"boundaries={comparison['boundary_symbols']} wplto=1 device=0")


def layout_delta(elf: Path) -> dict[str, Any]:
    candidate = GOLD.layout_from_elf(elf)
    golden = load(GOLD.GOLDEN)
    expected_sections = {
        row["name"]: row for row in golden["allocatable_sections"]}
    actual_sections = {
        row["name"]: row for row in candidate["allocatable_sections"]}
    section_delta = []
    for name in sorted(set(expected_sections) | set(actual_sections)):
        expected = expected_sections.get(name)
        actual = actual_sections.get(name)
        if expected != actual:
            section_delta.append({"name": name, "golden": expected,
                                  "candidate": actual})
    boundary_delta = {
        name: {"golden": golden["boundary_symbols"].get(name),
               "candidate": candidate["boundary_symbols"].get(name)}
        for name in sorted(set(golden["boundary_symbols"])
                           | set(candidate["boundary_symbols"]))
        if golden["boundary_symbols"].get(name)
            != candidate["boundary_symbols"].get(name)
    }
    candidate_bytes = GOLD.canonical(candidate)
    return {
        "candidate_layout_sha256": hashlib.sha256(candidate_bytes).hexdigest(),
        "golden_layout_sha256": GOLD.GOLDEN_SHA256,
        "differing_sections": section_delta,
        "differing_boundaries": boundary_delta,
    }


def record_final_red(error: BaseException) -> None:
    require(not RECEIPT.exists() and not FINAL_RED.exists(),
            "2.0 terminal result is immutable")
    artifacts: dict[str, dict[str, Any]] = {}
    for name, relative in {
        "seed_lto": "wplto/resident-island-seed.prg.lto.o",
        "candidate_lto": "wplto/lisp65-c2-substitution-linked.prg.lto.o",
        "candidate_elf": "wplto/lisp65-c2-substitution-linked.prg.elf",
        "candidate_prg": "wplto/lisp65-c2-substitution-linked.prg",
        "candidate_map": "wplto/lisp65-c2-substitution-linked.prg.map",
        "linker": "wplto/c2-substitution.ld",
        "resolved_profile": "wplto/resolved-profile.txt",
        "producer_log": "receipts/v20-producer.log",
    }.items():
        path = BUILD / relative
        if path.is_file():
            artifacts[name] = bind(path)
    elf = BUILD / "wplto/lisp65-c2-substitution-linked.prg.elf"
    delta = layout_delta(elf) if elf.is_file() else None
    value = {
        "format": "lisp65-c2.3-v20-ownership-recharter-final-red-v1",
        "recorded_on": RECORDED_ON,
        "status": "FINAL RED: 2.0 plan returns to owner",
        "error": {"type": type(error).__name__, "message": str(error)},
        "attempt_accounting": {
            "cards_authorized": 1, "cards_consumed": 1,
            "wplto_runs": int((BUILD / "wplto").exists()),
            "product_link_attempts": int((BUILD / "wplto").exists()),
            "linked_candidate_elf_emitted": elf.is_file(),
            "golden_comparison_reached": elf.is_file(),
            "device_contacts": 0,
        },
        "retry_authorized": False,
        "final_owner_disposition_required": True,
        "layout_delta": delta,
        "artifacts": artifacts,
        "authority": {
            "owner_commission": commission_binding(),
            "golden": bind(GOLD.GOLDEN),
            "preflight": bind(PREFLIGHT_RECEIPT),
            "invocation": bind(INVOCATION),
            "driver": bind(DRIVER),
        },
        "claim_limit": (
            "The sole 2.0 card is consumed. No retry, replacement card, "
            "narrower golden, device session, release or parity claim."),
    }
    FINAL_RED.write_bytes(canonical(value))


def selftest() -> None:
    commission_binding()
    gate = audit_card_path()
    mutations = path_mutations()
    require(GOLD.golden_bytes() and gate["golden_comparisons"] == 1
            and len(mutations) == 4,
            "2.0 sole-acceptance path selftest red")
    print("2.0 ownership recharter: SELFTEST PASS "
          "acceptance=golden-only path-mutations=4")


def check() -> None:
    selftest()
    require(not (RECEIPT.exists() and FINAL_RED.exists()),
            "2.0 card has two terminal outcomes")
    if not RECEIPT.exists() and not FINAL_RED.exists():
        print("2.0 ownership recharter: CHECK ARMED card=unused")
        return
    if FINAL_RED.exists():
        value = load(FINAL_RED)
        require(value.get("retry_authorized") is False
                and value.get("final_owner_disposition_required") is True,
                "2.0 final-red disposition drift")
        print("2.0 ownership recharter: CHECK FINAL RED "
              "retry=none owner-disposition=required")
        return
    value = load(RECEIPT)
    require(value.get("acceptance", {}).get("comparison") == "byte-identical"
            and value["acceptance"]["operations"] == 1
            and value["attempt_accounting"]["wplto_runs"] == 1,
            "2.0 green card receipt drift")
    elf = ROOT / value["artifacts"]["elf"]["path"]
    require(GOLD.canonical(GOLD.layout_from_elf(elf)) == GOLD.golden_bytes(),
            "persisted 2.0 candidate layout no longer equals golden")
    print("2.0 ownership recharter: CHECK PASS comparison=byte-identical")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("selftest", "preflight", "card", "check"))
    args = parser.parse_args()
    configure_projection_paths()
    if args.action == "selftest":
        selftest()
    elif args.action == "preflight":
        preflight()
    elif args.action == "card":
        card()
    else:
        check()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        RecharterError, GOLD.GoldenLayoutError, SAFE.FixError,
        BASE.CardError, OSError, ValueError, KeyError, json.JSONDecodeError,
        subprocess.CalledProcessError,
    ) as error:
        if len(sys.argv) > 1 and sys.argv[1] == "card":
            try:
                record_final_red(error)
            except Exception as receipt_error:  # never hide the terminal red
                print(f"2.0 ownership recharter: receipt failure: {receipt_error}",
                      file=sys.stderr)
        print(f"2.0 ownership recharter: FINAL RED: {error}", file=sys.stderr)
        raise SystemExit(2)
