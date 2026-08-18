#!/usr/bin/env python3
"""Close ambient input roots across the remaining Link-97 qualification path."""

from __future__ import annotations

import argparse
import ast
from copy import deepcopy
import hashlib
import importlib
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_candidate_capacity_identity as CAPACITY_GATE  # noqa: E402
import c2_lite_v6_boot_crc_abi_successor_link as SUCCESSOR_GATE  # noqa: E402

EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
SUCCESSOR = HOST / "c2_lite_v6_boot_crc_abi_successor_link.py"
CANONICAL = HOST / "c2_lite_canonical_product.py"
SUCCESSOR_IDENTITY = HOST / "c2_postlink_successor_identity.py"
CANDIDATE = HOST / "c2_v150_candidate_product.py"
LINKED = HOST / "c2_link65_single_submit_completion_wplto.py"
FIRST_RED = EVIDENCE / (
    "c2.3-v1.5.0-link97-post-link-qualification-replay-r6-first-red.json")
CAPACITY = EVIDENCE / (
    "c2.3-v1.5.0-link97-capacity-identity-inversion-receipt.json")
ELF = ROOT / (
    "build/c2.3/v1.5.0-candidate-product-link97/wplto/"
    "lisp65-c2-substitution-linked.prg.elf")
PRODUCT = ROOT / (
    "build/c2.3/v1.5.0-candidate-product-link97/wplto/"
    "lisp65-c2-substitution-linked.prg")
ROOT_PROOF = ROOT / (
    "build/c2.3/terminal-return-guard-link96/receipts/wplto-internal.json")
DIRECT_PROOF = ROOT / (
    "build/c2.3/v1.5.0-candidate-product-link97/receipts/"
    "fresh-direct-entry-contract.json")
RUNTIME_OUT = ROOT / "build/c2.3/v1.5.0-qualification-ambient-closure"
HISTORICAL_RECEIPT = EVIDENCE / (
    "c2.3-v1.5.0-link97-qualification-ambient-closure-receipt.json")
ISOLATED_RECEIPT = EVIDENCE / (
    "c2.3-v1.5.0-link97-qualification-process-isolation-receipt.json")
SCHEMA_MAP = EVIDENCE / (
    "c2.3-v1.5.0-link97-three-postlink-successor-content-map-receipt.json")
SCHEMA_RECEIPT = EVIDENCE / (
    "c2.3-v1.5.0-link97-qualification-current-schema-rebind-receipt.json")
EXPECTATION_SHAPE_RECEIPT = EVIDENCE / (
    "c2.3-v2.1-expectation-shape-sweep-receipt.json")
RECEIPT = (SCHEMA_RECEIPT if SCHEMA_RECEIPT.is_file() else
           ISOLATED_RECEIPT if ISOLATED_RECEIPT.is_file() else
           HISTORICAL_RECEIPT)
FORMAT = "lisp65-c2.3-v150-link97-qualification-ambient-closure-v1"
STATUS = "PASSED-REPLACEMENT-INVERSION-AND-ONE-TIME-AMBIENT-SWEEP"


class AmbientClosureError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise AmbientClosureError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"input absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"artifact absent: {path}")
    raw = path.read_bytes()
    return {
        "path": path.resolve().relative_to(ROOT.resolve()).as_posix(),
        "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
    }


def sources(overrides: dict[str, str] | None = None) -> dict[str, str]:
    values = {name: path.read_text(encoding="utf-8") for name, path in {
        "successor": SUCCESSOR, "canonical": CANONICAL,
        "successor_identity": SUCCESSOR_IDENTITY,
        "candidate": CANDIDATE, "linked": LINKED}.items()}
    if overrides:
        values.update(overrides)
    return values


def function(text: str, name: str) -> ast.FunctionDef:
    tree = ast.parse(text)
    node = next((item for item in tree.body
                 if isinstance(item, ast.FunctionDef) and item.name == name), None)
    require(node is not None, f"qualification stage absent: {name}")
    return node


def expressions(node: ast.AST) -> set[str]:
    return {ast.unparse(item) for item in ast.walk(node)}


def loaded_names(node: ast.AST) -> set[str]:
    return {item.id for item in ast.walk(node)
            if isinstance(item, ast.Name) and isinstance(item.ctx, ast.Load)}


def calls(node: ast.AST, target: str) -> list[ast.Call]:
    return [item for item in ast.walk(node) if isinstance(item, ast.Call)
            and ast.unparse(item.func) == target]


def keywords(call: ast.Call) -> dict[str | None, str]:
    return {item.arg: ast.unparse(item.value) for item in call.keywords}


def source_gate(overrides: dict[str, str] | None = None) -> dict[str, Any]:
    text = sources(overrides)
    replacement = function(text["successor"], "replacement_gates")
    crc = function(text["successor"], "workbench_crc_gate")
    abi = function(text["canonical"], "fresh_real_abi_gate")
    postlink = function(text["canonical"], "fresh_current_product_postlink_gate")
    successor_identity = function(text["successor_identity"], "project")
    replay = function(text["candidate"], "post_link_replay")
    complete = function(text["candidate"], "complete_action")
    complete_fresh = function(text["candidate"], "complete_in_fresh_process")
    linked = function(text["linked"], "linked_gates")

    replacement_expr = expressions(replacement)
    crc_expr = expressions(crc)
    abi_expr = expressions(abi)
    postlink_expr = expressions(postlink)
    successor_identity_expr = expressions(successor_identity)
    replay_expr = expressions(replay)
    complete_expr = expressions(complete)
    fresh_expr = expressions(complete_fresh)
    linked_expr = expressions(linked)

    replacement_calls = calls(replay, "base.replacement_gates")
    abi_calls = calls(replay, "can.fresh_real_abi_gate")
    postlink_calls = calls(replay, "can.fresh_current_product_postlink_gate")
    linked_calls = calls(replay, "can.LINK_GATE.linked_gates")
    require(
        len(replacement_calls) == len(abi_calls) == len(postlink_calls)
            == len(linked_calls) == 1,
        "remaining qualification call graph is incomplete")
    require(
        "OUT" not in loaded_names(replacement)
        and "OUT" not in loaded_names(crc)
        and "artifact_root = elf.parent" in replacement_expr
        and "artifact_root = elf.parent" in crc_expr
        and "artifact_root / 'generated-product-sources'" in replacement_expr
        and "ART.stage_product_gate(elf, verifier_base=verifier_base)"
            in replacement_expr
        and "LINK.BASE.LINK33_BASE.final_overlay_closure(elf, "
            "expected_sections=set(family['overlay_sections']))"
            in replacement_expr
        and "DIRECT.OUT = artifact_root" in replacement_expr
        and "artifact_root / 'resolved-profile.txt'" in crc_expr
        and "report_root / 'c2-crc-asm-leaf-workbench-gate.json'" in crc_expr,
        "replacement stage retains an ambient source root")
    require(
        keywords(replacement_calls[0]) == {
            "capacity_qualifier": "can.fresh_session_capacity_gate",
            "root_qualifier": "bound_root",
            "direct_qualifier": "bound_direct_entry_gate",
            "qualification_root": "REPLAY",
            "verifier_base":
                "can.PRODUCT.LINK60_VERIFIER_BINDING_BASE"}
        and keywords(abi_calls[0]).get("report_path")
            == "REPLAY / 'c2-asm-leaf-real-abi-callers.json'"
        and keywords(postlink_calls[0]) == {
            "internal_path": "REPLAY_INTERNAL", "artifact_root": "elf.parent"}
        and len(linked_calls[0].args) == 1
        and ast.unparse(linked_calls[0].args[0]) == "elf"
        and keywords(linked_calls[0]).get("receipt") == "REPLAY_LINKED_GATE",
        "replay omits an explicit remaining-stage input")
    require(
        "REAL_ABI_LINK.OUT" not in abi_expr
        and "report_path = elf.parent / 'c2-asm-leaf-real-abi-callers.json'"
            in abi_expr
        and "internal = load(internal_path)" in postlink_expr
        and "SUCCESSOR_IDENTITY.project(replacement, artifact_root)"
            in postlink_expr
        and "artifact_root = artifact_root.resolve()"
            in successor_identity_expr
        and ("static_root = artifact_root.parent / "
             "'static-plane/narrow-static'") in successor_identity_expr
        and "artifact_root / 'runtime-overlays-session-final.json'"
            in postlink_expr
        and "linked = LENGTH.audit_elf(elf)" in linked_expr
        and "abi = ABI.audit_elf(elf, require_bank3_chain=True)" in linked_expr
        and "write_receipt(receipt, value)" in linked_expr,
        "post-replacement gate retains an unconverted ambient input")
    require(
        "configure()" in complete_expr
        and "L95.L94.complete_action()" in complete_expr
        and "'LISP65_V150_POSTLINK_REPLAY'" in fresh_expr
        and "REPLAY_PROFILE.is_file()" in fresh_expr
        and "str(DRIVER)" in fresh_expr
        and "can.configure_wplto()" in replay_expr,
        "fresh-process completion is not bound to candidate configuration")

    inventory = [
        ("replacement.product", "passed-artifact"),
        ("replacement.ELF", "passed-artifact"),
        ("replacement.family-manifests", "ELF-parent-derived"),
        ("replacement.capacity", "explicit-injected-qualifier"),
        ("replacement.product-semantics", "passed-product-and-ELF"),
        ("replacement.no-attic-sources", "ELF-parent-derived"),
        ("replacement.stage", "passed-ELF-and-explicit-candidate-contract"),
        ("replacement.overlay", "ELF-parent-manifest-and-passed-ELF"),
        ("replacement.preinstall", "passed-ELF"),
        ("replacement.root-surrogate", "SHA-bound-injected-proof"),
        ("replacement.direct-entry", "SHA-bound-injected-proof"),
        ("replacement.CRC-profile", "ELF-parent-derived"),
        ("replacement.CRC-report", "explicit-replay-output"),
        ("real-ABI.ELF", "passed-artifact"),
        ("real-ABI.report", "explicit-replay-output"),
        ("postlink.internal", "explicit-replay-receipt"),
        ("postlink.artifact-root", "ELF-parent-derived"),
        ("postlink.successor-identities", "ELF-parent-and-current-schema-derived"),
        ("linked.ELF", "passed-artifact"),
        ("linked.receipt", "explicit-replay-output"),
        ("guard.product-and-ELF", "passed-artifacts"),
        ("completion.profile", "explicit-replay-environment"),
        ("completion.driver", "current-candidate-driver"),
        ("completion.paths", "candidate-configure-before-use"),
        ("manifest.inputs", "passed-qualification-and-completion"),
        ("freight.inputs", "SHA-bound-preflight-and-closure"),
    ]
    return {
        "status": "passed-all-remaining-qualification-inputs-classified",
        "stage_inputs": [
            {"id": name, "classification": classification, "ambient": False}
            for name, classification in inventory],
        "stage_input_count": len(inventory),
        "ambient_input_count": 0,
        "replacement_module_OUT_reads": 0,
        "rule": (
            "Every remaining qualification-stage input is passed, derived "
            "from the passed ELF's artifact root, or bound by an explicit "
            "candidate authority; ambient module output state is forbidden."),
    }


def source_mutations() -> list[str]:
    base = sources()
    cases: list[tuple[str, str, str, str]] = [
        ("no-attic-global-OUT", "successor",
         "elf, artifact_root / \"generated-product-sources\"",
         "elf, OUT / \"generated-product-sources\""),
        ("CRC-profile-global-OUT", "successor",
         "sha(artifact_root / \"resolved-profile.txt\")",
         "sha(OUT / \"resolved-profile.txt\")"),
        ("CRC-report-global-OUT", "successor",
         "out=report_root / \"c2-crc-asm-leaf-workbench-gate.json\"",
         "out=OUT / \"c2-crc-asm-leaf-workbench-gate.json\""),
        ("direct-entry-global-OUT", "successor",
         "DIRECT.OUT = artifact_root", "DIRECT.OUT = OUT"),
        ("stage-historical-verifier-base", "successor",
         "stage = ART.stage_product_gate(elf, verifier_base=verifier_base)",
         "stage = ART.stage_product_gate(elf)"),
        ("overlay-historical-section-set", "successor",
         "elf, expected_sections=set(family[\"overlay_sections\"])",
         "elf, expected_sections=None"),
        ("ABI-report-global-OUT", "canonical",
         "report_path = elf.parent / \"c2-asm-leaf-real-abi-callers.json\"",
         "report_path = REAL_ABI_LINK.OUT / \"c2-asm-leaf-real-abi-callers.json\""),
        ("postlink-global-WPLTO", "canonical",
         "artifact_root / \"runtime-overlays-session-final.json\"",
         "WPLTO / \"runtime-overlays-session-final.json\""),
        ("postlink-successor-global-root", "successor_identity",
         "static_root = artifact_root.parent / \"static-plane/narrow-static\"",
         "static_root = ROOT / \"build/ambient-static-plane\""),
        ("linked-global-ELF", "linked",
         "linked = LENGTH.audit_elf(elf)",
         "linked = LENGTH.audit_elf(BASE.ELF)"),
        ("linked-global-receipt", "linked",
         "write_receipt(receipt, value)",
         "write_receipt(LINKED_GATE, value)"),
        ("completion-without-configure", "candidate",
         "    configure()\n    return L95.L94.complete_action()",
         "    return L95.L94.complete_action()"),
        ("completion-without-replay-profile", "candidate",
         "    if REPLAY_PROFILE.is_file():\n"
         "        environment[\"LISP65_V150_POSTLINK_REPLAY\"] = \"1\"",
         "    if False:\n"
         "        environment[\"LISP65_V150_POSTLINK_REPLAY\"] = \"1\""),
    ]
    rejected: list[str] = []
    for name, role, old, new in cases:
        require(old in base[role], f"ambient mutation anchor absent: {name}")
        mutant = dict(base)
        mutant[role] = mutant[role].replace(old, new, 1)
        try:
            source_gate(mutant)
        except AmbientClosureError:
            rejected.append(name)

    def replace_last(text: str, old: str, new: str) -> str:
        prefix, separator, suffix = text.rpartition(old)
        require(bool(separator), f"last replay mutation anchor absent: {old}")
        return prefix + new + suffix

    replay_cases: list[tuple[str, Callable[[str], str]]] = [
        ("omit-root-qualifier", lambda text: replace_last(
            text, "            root_qualifier=bound_root,\n", "")),
        ("omit-direct-qualifier", lambda text: replace_last(
            text, "            direct_qualifier=bound_direct_entry_gate,\n", "")),
        ("omit-qualification-root", lambda text: replace_last(
            text, "            qualification_root=REPLAY,\n",
            "            qualification_root=None,\n")),
        ("restore-historical-stage-contract", lambda text: replace_last(
            text,
            "            verifier_base=can.PRODUCT."
            "LINK60_VERIFIER_BINDING_BASE)",
            "            verifier_base=base.VERIFIER_BASE)")),
        ("omit-ABI-report", lambda text: text.replace(
            "elf, report_path=REPLAY / \"c2-asm-leaf-real-abi-callers.json\")",
            "elf)", 1)),
        ("omit-postlink-roots", lambda text: text.replace(
            "            internal_path=REPLAY_INTERNAL, artifact_root=elf.parent)",
            "            internal_path=None, artifact_root=None)", 1)),
        ("omit-linked-ELF", lambda text: text.replace(
            "            elf, receipt=REPLAY_LINKED_GATE)",
            "            receipt=REPLAY_LINKED_GATE)", 1)),
    ]
    for name, mutate in replay_cases:
        mutant = dict(base)
        mutant["candidate"] = mutate(mutant["candidate"])
        require(mutant["candidate"] != base["candidate"],
                f"replay mutation anchor absent: {name}")
        try:
            source_gate(mutant)
        except AmbientClosureError:
            rejected.append(name)
    expected = [name for name, *_rest in cases] + [
        name for name, _mutate in replay_cases]
    require(rejected == expected, "ambient qualification mutation survived")
    return rejected


def _runtime_gate_local() -> dict[str, Any]:
    root_internal = load(ROOT_PROOF)
    root = root_internal["fresh_prelink_gates"][
        "root_surrogate_complete_domain"]
    direct = load(DIRECT_PROOF)
    require(
        root.get("status") == "pass"
        and root.get("root_surrogates", {}).get("count") == 1536
        and direct.get("status")
            == "passed-current-v6-root-surrogate-direct-entry-contract"
        and direct.get("cross_parity", {}).get("fixnum_decodable_published_values")
            == 0,
        "bound pre-link qualification witnesses are not green")
    RUNTIME_OUT.mkdir(parents=True, exist_ok=True)
    host = {
        "c2d_v6_host_semantics": {
            "stale_generation": {"old_handles_rejected": 10}},
        "bank3_lifetime_model": {"invalidation_before_overwrite": True},
    }
    candidate = importlib.import_module("c2_v150_candidate_product")
    candidate.configure(candidate.REPLAY_PREVIOUS_RED / "candidate-profile.json")
    can = candidate.L95.CAN
    old = can.configure_wplto()
    try:
        result = SUCCESSOR_GATE.replacement_gates(
            PRODUCT, ELF, host,
            capacity_qualifier=CAPACITY_GATE.capacity_gate,
            root_qualifier=lambda: deepcopy(root),
            direct_qualifier=lambda: deepcopy(direct),
            qualification_root=RUNTIME_OUT,
            verifier_base=candidate.PRODUCT.LINK60_VERIFIER_BINDING_BASE)
    finally:
        can.restore_wplto(old)
    require(result.get("status") == "passed",
            "artifact-bound replacement-stage runtime fixture red")
    return {
        "status": "passed-artifact-bound-replacement-stage-runtime-fixture",
        "capacity_status": result["capacity"]["identity_status"],
        "no_attic_status": result["no_runtime_attic"]["status"],
        "direct_status": result["generated_direct_entry"]["status"],
        "CRC_status": result["workbench_crc_end_to_end"]["status"],
        "inputs": {
            "product": bind(PRODUCT), "ELF": bind(ELF),
            "root_surrogate": bind(ROOT_PROOF),
            "direct_entry": bind(DIRECT_PROOF),
        },
        "output": bind(RUNTIME_OUT / "c2-crc-asm-leaf-workbench-gate.json"),
    }


def _selector_state() -> dict[str, int] | None:
    candidate = sys.modules.get("c2_v150_candidate_product")
    if candidate is None:
        return None
    product = candidate.L95.CAN.PRODUCT
    return dict(product.PROFILE_RODATA_INPUT_SECTIONS)


def process_isolation_gate(source: str | None = None) -> dict[str, Any]:
    text = (Path(__file__).read_text(encoding="utf-8")
            if source is None else source)
    runtime = function(text, "runtime_gate")
    local = function(text, "_runtime_gate_local")
    complete = function(sources()["candidate"], "complete_in_fresh_process")
    runtime_calls = {ast.unparse(item.func) for item in ast.walk(runtime)
                     if isinstance(item, ast.Call)}
    local_calls = {ast.unparse(item.func) for item in ast.walk(local)
                   if isinstance(item, ast.Call)}
    complete_calls = {ast.unparse(item.func) for item in ast.walk(complete)
                      if isinstance(item, ast.Call)}
    require(
        "subprocess.run" in runtime_calls
        and "_runtime_gate_local" not in runtime_calls
        and "candidate.configure" in local_calls
        and "subprocess.run" in complete_calls
        and "'_runtime'" in text,
        "one-shot fixture lacks fresh-process isolation")
    return {
        "status": "passed-all-one-shot-fixtures-process-isolated",
        "one_shot_fixture_count": 2,
        "isolated_fixture_count": 2,
        "parent_selector_state_leaks": 0,
        "fixtures": {
            "replacement-runtime-fixture": "fresh-subprocess",
            "artifact-completion": "fresh-subprocess",
        },
        "rule": (
            "Every fixture that configures one-shot runtime state executes "
            "in its own fresh process; any parent-state leakage is red."),
    }


def validate_process_isolation(value: dict[str, Any]) -> None:
    require(
        value.get("status")
            == "passed-all-one-shot-fixtures-process-isolated"
        and value.get("one_shot_fixture_count") == 2
        and value.get("isolated_fixture_count") == 2
        and value.get("parent_selector_state_leaks") == 0
        and set(value.get("fixtures", {}).values()) == {"fresh-subprocess"},
        "one-shot process-isolation contract drift")


def process_isolation_mutations() -> list[str]:
    value = process_isolation_gate()
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "runtime-fixture-in-process": lambda x: x["fixtures"].update(
            {"replacement-runtime-fixture": "candidate-process"}),
        "completion-in-process": lambda x: x["fixtures"].update(
            {"artifact-completion": "candidate-process"}),
        "selector-state-leak": lambda x: x.update(
            parent_selector_state_leaks=1),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        candidate = deepcopy(value); mutate(candidate)
        try:
            validate_process_isolation(candidate)
        except AmbientClosureError:
            rejected.append(name)
    require(rejected == list(cases), "process-isolation mutation survived")
    return rejected


def runtime_gate() -> dict[str, Any]:
    before = _selector_state()
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(HOST)
    result = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), "_runtime"],
        cwd=ROOT, env=environment, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    require(result.returncode == 0,
            "isolated replacement runtime fixture red:\n" + result.stderr)
    after = _selector_state()
    require(before == after,
            "one-shot selector state leaked from isolated runtime fixture")
    value = json.loads(result.stdout)
    require(isinstance(value, dict), "isolated runtime fixture result absent")
    value["process_isolation"] = {
        "mode": "fresh-subprocess", "parent_selector_state_unchanged": True}
    return value


def collect(*, schema_rebind: bool | None = None) -> dict[str, Any]:
    if schema_rebind is None:
        schema_rebind = SCHEMA_RECEIPT.is_file()
    first_red = load(FIRST_RED)
    require(
        first_red.get("mechanism", {}).get("classification")
            == "post-capacity-ambient-Link38-generated-source-root"
        and first_red.get("boundary", {}).get("capacity_gate_completed") is True,
        "ambient sweep First Red authority drift")
    value = {
        "format": FORMAT, "recorded_on": "2026-08-11", "status": STATUS,
        "source_gate": source_gate(),
        "process_isolation_gate": process_isolation_gate(),
        "process_isolation_mutations_rejected":
            process_isolation_mutations(),
        "runtime_gate": runtime_gate(),
        "isolation_rebind": {
            "recorded_on": "2026-08-11",
            "authorization_commit": "5ebf8e93",
            "prior_receipt": bind(HISTORICAL_RECEIPT),
            "class_precedents": [
                "v1.12-configure_shared-double-in-process",
                "v1.5-ambient-runtime-fixture-selector-state-leak"],
        },
        "authorities": {
            "tool": bind(Path(__file__)), "r6_first_red": bind(FIRST_RED),
            "capacity": bind(CAPACITY), "product": bind(PRODUCT),
            "ELF": bind(ELF),
            "sources": {name: bind(path) for name, path in {
                "successor": SUCCESSOR, "canonical": CANONICAL,
                "successor_identity": SUCCESSOR_IDENTITY,
                "candidate": CANDIDATE, "linked": LINKED}.items()},
        },
        "claim_limit": (
            "Host-only source/input closure for the remaining frozen Link-97 "
            "qualification path. No replay, completion, medium or hardware."),
    }
    if schema_rebind:
        value["schema_rebind"] = {
            "recorded_on": "2026-08-11",
            "authorization_commit": "0a2bf127",
            "prior_receipt": bind(ISOLATED_RECEIPT),
            "three_field_content_map": bind(SCHEMA_MAP),
            "semantic_fields_reasserted": 3,
            "semantic_fields_inherited": 0,
        }
    return value


def validate(value: dict[str, Any], *, verify: bool) -> None:
    gate = value.get("source_gate", {})
    runtime = value.get("runtime_gate", {})
    isolation = value.get("process_isolation_gate", {})
    require(
        value.get("format") == FORMAT and value.get("status") == STATUS
        and gate.get("ambient_input_count") == 0
        and gate.get("stage_input_count") == len(gate.get("stage_inputs", []))
        and gate.get("stage_input_count") >= 25
        and all(row.get("ambient") is False for row in gate.get("stage_inputs", []))
        and gate == source_gate()
        and runtime.get("status")
            == "passed-artifact-bound-replacement-stage-runtime-fixture"
        and runtime.get("capacity_status")
            == "passed-current-contract-derived-capacity"
        and runtime.get("process_isolation") == {
            "mode": "fresh-subprocess",
            "parent_selector_state_unchanged": True}
        and isolation == process_isolation_gate()
        and value.get("process_isolation_mutations_rejected")
            == process_isolation_mutations()
        and value.get("isolation_rebind", {}).get("authorization_commit")
            == "5ebf8e93",
        "ambient qualification closure receipt drift")
    schema = value.get("schema_rebind")
    if schema is not None:
        require(
            schema.get("authorization_commit") == "0a2bf127"
            and schema.get("recorded_on") == "2026-08-11"
            and schema.get("prior_receipt") == bind(ISOLATED_RECEIPT)
            and schema.get("three_field_content_map") == bind(SCHEMA_MAP)
            and schema.get("semantic_fields_reasserted") == 3
            and schema.get("semantic_fields_inherited") == 0,
            "current-schema authority rebind drift")
    if verify:
        current = collect(schema_rebind=schema is not None)
        if value != current:
            shape = load(EXPECTATION_SHAPE_RECEIPT)
            require(
                shape.get("status") ==
                    "PASS: remaining candidate expectation forms derive or classify"
                and shape.get("sweep", {}).get(
                    "pinned_candidate_shape_count") == 0
                and shape["authority"]["canonical_consumer"]
                    == current["authorities"]["sources"]["canonical"]
                and shape["authority"]["candidate_replay"]
                    == current["authorities"]["sources"]["candidate"]
                and shape["authority"]["ambient_closure"]
                    == current["authorities"]["tool"],
                "ambient expectation-shape source rebind authority red")
            recorded_projection = deepcopy(value)
            current_projection = deepcopy(current)
            for role in ("canonical", "candidate"):
                recorded_projection["authorities"]["sources"].pop(role)
                current_projection["authorities"]["sources"].pop(role)
            recorded_projection["authorities"].pop("tool")
            current_projection["authorities"].pop("tool")
            require(recorded_projection == current_projection,
                    "ambient qualification drift exceeds classified sources")


def mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "hide-ambient-input": lambda x: x["source_gate"].update(
            ambient_input_count=1),
        "drop-stage-input": lambda x: x["source_gate"]["stage_inputs"].pop(),
        "mark-stage-ambient": lambda x: x["source_gate"]["stage_inputs"][0]
            .update(ambient=True),
        "red-runtime-stage": lambda x: x["runtime_gate"].update(
            status="FIRST RED"),
        "claim-parent-state-leak": lambda x: x["runtime_gate"]
            ["process_isolation"].update(parent_selector_state_unchanged=False),
    }
    if "schema_rebind" in value:
        cases["inherit-schema-claims"] = lambda x: x["schema_rebind"].update(
            semantic_fields_reasserted=0, semantic_fields_inherited=3)
    rejected: list[str] = []
    for name, mutate in cases.items():
        candidate = deepcopy(value); mutate(candidate)
        try:
            validate(candidate, verify=False)
        except AmbientClosureError:
            rejected.append(name)
    require(rejected == list(cases), "ambient receipt mutation survived")
    return [*source_mutations(), *process_isolation_mutations(), *rejected]


def selftest() -> int:
    value = collect(); mutations(value)
    print("v1.5 qualification ambient closure selftest: PASS "
          f"inputs={value['source_gate']['stage_input_count']}")
    return 0


def capture() -> int:
    value = collect(); value["mutations_rejected"] = mutations(value)
    RECEIPT.write_bytes(canonical(value))
    print("v1.5 qualification ambient closure capture: PASS "
          f"inputs={value['source_gate']['stage_input_count']}")
    return 0


def isolate() -> int:
    require(HISTORICAL_RECEIPT.is_file() and not ISOLATED_RECEIPT.exists(),
            "process-isolation receipt boundary is not fresh")
    value = collect(); value["mutations_rejected"] = mutations(value)
    ISOLATED_RECEIPT.write_bytes(canonical(value))
    print("v1.5 qualification process isolation: PASS fixtures=2 leaks=0")
    return 0


def schema_rebind() -> int:
    require(ISOLATED_RECEIPT.is_file() and SCHEMA_MAP.is_file()
            and not SCHEMA_RECEIPT.exists(),
            "current-schema rebind boundary is not fresh")
    value = collect(schema_rebind=True)
    value["mutations_rejected"] = mutations(value)
    SCHEMA_RECEIPT.write_bytes(canonical(value))
    print("v1.5 qualification current-schema rebind: PASS fields=3 inherited=0")
    return 0


def check() -> int:
    value = load(RECEIPT); rejected = value.pop("mutations_rejected", None)
    validate(value, verify=True)
    require(rejected == mutations(value), "ambient mutation receipt drift")
    print("v1.5 qualification ambient closure check: PASS "
          f"inputs={value['source_gate']['stage_input_count']}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "action", choices=("capture", "isolate", "check", "selftest",
                           "schema-rebind", "_runtime"))
    action = parser.parse_args().action
    if action == "_runtime":
        print(json.dumps(_runtime_gate_local(), sort_keys=True))
        return 0
    return {"capture": capture, "isolate": isolate,
            "schema-rebind": schema_rebind, "check": check,
            "selftest": selftest}[action]()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AmbientClosureError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print(f"v1.5 qualification ambient closure: FAIL: {error}")
        raise SystemExit(2)
