#!/usr/bin/env python3
"""Build/check the single commissioned v1.5.0 product card (Link 97)."""

from __future__ import annotations

import argparse
import ast
import contextlib
from copy import deepcopy
import hashlib
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

import c2_link95_product_card as L95  # noqa: E402
import c2_candidate_capacity_identity as CAPACITY_IDENTITY  # noqa: E402
import c2_lite_v6_real_abi_direct_entry_contract as DIRECT  # noqa: E402
import c2_product_substitution_link as PRODUCT  # noqa: E402
import c2_terminal_return_guard_gate as GUARD  # noqa: E402
import c2_v150_release_preflight as PRE  # noqa: E402
import c2_v150_release_closure as CLOSURE  # noqa: E402
import c2_v150_link97_slice_content_map as SLICE_MAP  # noqa: E402
import c2_v150_qualification_ambient_closure as AMBIENT  # noqa: E402
import c2_f1_published_value_call_wplto as F1W  # noqa: E402
import c2_lite_v6_link48_append_final_hybrid_facade16_artifact_replay as ARTIFACT_REPLAY  # noqa: E402,E501


RELEASE = "v1.5.0"
LINK = 97
BUILD = ROOT / "build/c2.3/v1.5.0-candidate-product-link97"
MANIFEST = BUILD / "canonical-product-manifest.json"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.5.0-link97-product-card-receipt.json"
)
FIRST_RED = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.5.0-link97-product-card-first-red.json"
)
GUARD_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.5.0-link97-terminal-guard-receipt.json"
)
REPLAY_FIRST_RED = BUILD / "post-link-qualification-replay"
REPLAY_PREVIOUS_RED = BUILD / "post-link-qualification-replay-r6"
REPLAY = BUILD / "post-link-qualification-replay-r7"
REPLAY_PROFILE = REPLAY / "candidate-profile.json"
REPLAY_INTERNAL = REPLAY / "wplto-internal.json"
REPLAY_LINKED_GATE = REPLAY / "single-submit-linked-gates.json"
ROOT_PROOF_INTERNAL = (
    ROOT / "build/c2.3/terminal-return-guard-link96/receipts/wplto-internal.json")
REPLAY_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.5.0-link97-post-link-qualification-replay-receipt.json"
)
REPLAY_FIRST_RED_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.5.0-link97-post-link-qualification-replay-r6-first-red.json"
)
REPLAY_AUTHORIZATIONS = [
    "12e3bd38", "10334190", "07a2969a", "c5231035", "c931dd3c",
    "85ff1758", "f1560759"]
CONTRACT = PRE.CONTRACT
PROFILE = ROOT / "config/c2-l-full-product-profile.json"
HEADER = ROOT / "src/c2_lite_static_plane.h"
DRIVER = Path(__file__).resolve()
FORMAT = "lisp65-c2.3-v150-link97-product-card-v1"
STATUS = "V150-LINK97-HOST-PRODUCT-GREEN; MEDIA-AND-HARDWARE-PENDING"
EXECUTED_DRIVER = {
    "path": "tools/host-lisp/c2_v150_candidate_product.py",
    "bytes": 17543,
    "sha256": "0a7d19bd310771cca7a1b60f3bf0b109671ef556a7c687080118fe8aa3a003ec",
}
FROZEN_FIRST_RED_AUTHORITIES = {
    "current_recorder": {
        "bytes": 26170,
        "path": "tools/host-lisp/c2_v150_candidate_product.py",
        "sha256": (
            "465b170375bf7451089699aa5d921e2c20f1d7d4e62bf34244451979764cb62a"
        ),
    },
    "historical_fixture": {
        "bytes": 16726,
        "path": "tools/host-lisp/c2_f1_published_value_call_wplto.py",
        "sha256": (
            "d00a01c47c43aeac5322aea5f42d73da9feec2ee5e8e23feb60faf3560e70784"
        ),
    },
    "preflight": {
        "bytes": 13741,
        "path": (
            "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
            "c2.3-v1.5.0-release-preflight-receipt.json"),
        "sha256": (
            "ca6af824a9089e6671dc54f6e5006540dc32ac18234d188b2aae483421c8e1e4"
        ),
    },
    "freight_closure": {
        "bytes": 4246,
        "path": (
            "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
            "c2.3-v1.5.0-release-freight-closure-receipt.json"),
        "sha256": (
            "97fc9a3808d6e33a62cd6fe9241ba4d8c726bdc77f1819ee33e4c8fa6417294a"
        ),
    },
}
FROZEN_RED_ARTIFACTS = {
    "product": {
        "bytes": 41566,
        "path": (
            "build/c2.3/v1.5.0-candidate-product-link97/wplto/"
            "lisp65-c2-substitution-linked.prg"),
        "sha256": "f7a9d536e65a7ab89bb2534678f8cdea08fce50d8500a126f452d1525e3c497e",
    },
    "ELF": {
        "bytes": 623428,
        "path": (
            "build/c2.3/v1.5.0-candidate-product-link97/wplto/"
            "lisp65-c2-substitution-linked.prg.elf"),
        "sha256": "104f6fc4217fa9d803bfb675cabf46c38deb246cad17502a51e9aadeba95c84c",
    },
    "map": {
        "bytes": 178516,
        "path": (
            "build/c2.3/v1.5.0-candidate-product-link97/wplto/"
            "lisp65-c2-substitution-linked.prg.map"),
        "sha256": "983595e360f2d6d3d11a5e944009f25ff492b5a02659431f3d7f7761df9af281",
    },
    "wplto_internal": {
        "bytes": 52800,
        "path": (
            "build/c2.3/v1.5.0-candidate-product-link97/receipts/"
            "wplto-internal.json"),
        "sha256": "064d27992b7d85c44c79214cde4ab885771d8991a80d0aedbc971255afc273b8",
    },
    "wplto_base_result": {
        "bytes": 4454,
        "path": (
            "build/c2.3/v1.5.0-candidate-product-link97/receipts/"
            "wplto-base-result.json"),
        "sha256": "cd51294e5f75f1d33ae74a9875de22ef4ebbf3006ba8722878d838cd7c213440",
    },
    "driver_log": {
        "bytes": 500,
        "path": (
            "build/c2.3/v1.5.0-candidate-product-link97/receipts/"
            "wplto-historical-driver.log"),
        "sha256": "f4a4454d6ce8093e1339563442218068f52163ba029fd30a438a855f7e1bc8e1",
    },
}


class CardError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise CardError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
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


def run(command: list[str], label: str) -> dict[str, Any]:
    result = subprocess.run(
        command, cwd=ROOT, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, check=False,
    )
    require(result.returncode == 0, f"{label} red:\n{result.stdout}")
    raw = result.stdout.encode()
    return {"status": "passed", "output_bytes": len(raw),
            "output_sha256": hashlib.sha256(raw).hexdigest()}


def profile_geometry(profile: Path = PROFILE) -> dict[str, Any]:
    value = load(profile)
    code = value["bank2_static_code"]
    return {
        "static_code_bytes": int(code["bytes"]),
        "bank2_headroom_bytes": int(code["headroom_bytes"]),
        "bank2_sha256": str(code["sha256"]),
        "entries": int(value["entries"]),
        "resolutions": int(value["resolutions"]),
        "roots": int(value["roots"]),
        "direct_entry_refs": int(value["direct_entry_refs"]),
        "product_build_id": str(value["product_build_id"]),
    }


def configure_identity(profile: Path = PROFILE) -> None:
    geo = PRE.geometry()
    require(geo == profile_geometry(profile),
            "v1.5 qualification profile differs from preflight")
    L95.RELEASE = RELEASE
    L95.LINK = LINK
    L95.DRIVER = DRIVER
    L95.PREFLIGHT = PRE.BUILD
    L95.BUILD = BUILD
    L95.MANIFEST = MANIFEST
    L95.STATIC = PRE.STATIC
    L95.STATIC_PRODUCT = PRE.STATIC / "product"
    L95.V6_PLANE = PRE.V6_PLANE
    L95.STDLIB_PREFIX = PRE.STDLIB_PREFIX
    L95.STDLIB = PRE.STDLIB
    L95.PREFLIGHT_RECEIPT = PRE.RECEIPT
    L95.HOST_RECEIPT = PRE.RECEIPT
    L95.CONTRACT = CONTRACT
    L95.PROFILE = profile
    L95.HEADER = HEADER
    L95.EXPECTED_STATIC = geo["static_code_bytes"]
    L95.EXPECTED_ENTRIES = geo["entries"]
    L95.EXPECTED_RESOLUTIONS = geo["resolutions"]
    L95.EXPECTED_ROOTS = geo["roots"]
    L95.EXPECTED_DIRECT_REFS = geo["direct_entry_refs"]
    L95.EXPECTED_PRODUCT_ID = geo["product_build_id"]
    L95.EXPECTED_BANK2_SHA = geo["bank2_sha256"]
    L95.specs = PRE.specs
    L95.CLOSURE.OUT = PRE.BUILD
    L95.CLOSURE.PRODUCT = PRE.PRODUCT
    L95.CLOSURE.RECEIPT = PRE.RECEIPT
    L95.CLOSURE.restore_bound_authorities = lambda: None


def configure(profile: Path | None = None) -> dict[str, Path]:
    if profile is None:
        profile = (REPLAY_PROFILE if os.environ.get(
            "LISP65_V150_POSTLINK_REPLAY") == "1" else PROFILE)
    configure_identity(profile)
    paths = L95.configure_card()
    # Link-95's compatibility adapter predates profile injection and leaves
    # these two readers on the tracked predecessor.  Qualification replay
    # owns a build-local projection of the already linked candidate instead.
    L95.L94.PROFILE = profile
    L95.CAN.PROFILE = profile
    L95.CAN.PLANE.PROFILE = profile
    inherited = L95.L94.PRODUCT_LINK.single_link

    def v150_single_link(
        out: Path, *, probe_definitions: tuple[str, ...] = (),
        direct_entry_receipt: Path = DIRECT.RECEIPT,
        direct_entry_check_tool: str =
            "c2_lite_v6_real_abi_direct_entry_contract.py",
        extra_contract_lines: tuple[str, ...] = (),
    ) -> None:
        authorized = tuple(load(CONTRACT)["build"]["activation_defines"])
        features = tuple(dict.fromkeys((
            *probe_definitions, *authorized,
        )))
        return inherited(
            out, probe_definitions=features,
            direct_entry_receipt=direct_entry_receipt,
            direct_entry_check_tool=direct_entry_check_tool,
            extra_contract_lines=(
                *extra_contract_lines,
                "release=v1.5.0",
                "experience=boot-liveness-and-require-intent",
                "terminal_return_guard=shadow-restore-first-signature",
                "resident_freight_delta=0",
            ),
        )

    L95.L94.PRODUCT_LINK.single_link = v150_single_link
    return paths


def completed_paths() -> dict[str, Path]:
    return L95.BASE.paths(BUILD)


def guard_result(elf: Path, prg: Path) -> dict[str, Any]:
    value = GUARD.audit(elf, prg)
    rejected = GUARD.mutation_selftest(elf, prg)
    value["mutations_rejected"] = rejected
    value["mutation_count"] = len(rejected)
    return value


def semantic_guard(value: dict[str, Any]) -> bytes:
    copy = deepcopy(value)
    for role in ("ELF", "product_PRG"):
        copy["authorities"][role].pop("path", None)
    return canonical(copy)


def write_replay_profile() -> dict[str, Any]:
    """Project the frozen candidate identity without changing tracked state."""
    value = load(PROFILE)
    geo = PRE.geometry()
    value.update({
        "recorded_on": "2026-08-11",
        "bank2_static_code": {
            "bytes": geo["static_code_bytes"],
            "headroom_bytes": geo["bank2_headroom_bytes"],
            "sha256": geo["bank2_sha256"],
        },
        "entries": geo["entries"],
        "resolutions": geo["resolutions"],
        "roots": geo["roots"],
        "direct_entry_refs": geo["direct_entry_refs"],
        "product_build_id": geo["product_build_id"],
    })
    value["authority"] = {
        "kind": "post-link-qualification-projection-of-frozen-Link-97",
        "rule": (
            "Qualification consumes the already linked candidate identity; "
            "this build-local object is not a source-build or relink input."),
        "preflight": bind(PRE.RECEIPT),
        "frozen_product": FROZEN_RED_ARTIFACTS["product"],
        "authorization_commits": REPLAY_AUTHORIZATIONS,
    }
    REPLAY.mkdir(parents=True, exist_ok=False)
    REPLAY_PROFILE.write_bytes(canonical(value))
    require(profile_geometry(REPLAY_PROFILE) == geo,
            "build-local replay profile did not close candidate identity")
    return value


def frozen_red_artifact_preflight() -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for role, expected in FROZEN_RED_ARTIFACTS.items():
        path = ROOT / expected["path"]
        actual = bind(path)
        require(actual == expected, f"frozen Link-97 artifact drift: {role}")
        rows[role] = actual
    return rows


def bound_direct_entry_gate() -> dict[str, Any]:
    """Consume the candidate's pre-link proof without recompiling its helper."""
    path = BUILD / "receipts/fresh-direct-entry-contract.json"
    value = load(path)
    bindings = value["bindings"]
    for name, row in bindings.items():
        target = ROOT / row["path"]
        actual = bind(target)
        require(
            all(actual[key] == row[key] for key in ("path", "bytes", "sha256")),
            f"bound Link-97 direct-entry input drift: {name}")
    parity = value["cross_parity"]
    require(
        value["status"] == "passed-current-v6-root-surrogate-direct-entry-contract"
        and parity["direct_entry_references"] == PRE.geometry()[
            "direct_entry_refs"]
        and parity["entries"] == PRE.geometry()["entries"]
        and parity["resolutions"] == PRE.geometry()["resolutions"]
        and parity["fixnum_decodable_published_values"] == 0
        and parity["target_phase12_negative_classes"] == 4,
        "bound Link-97 direct-entry proof differs from candidate identity",
    )
    return {
        "status": "passed-bound-generated-current-product-direct-entry-proof",
        "cross_parity": parity,
        "single_truth": value["single_truth"],
        "target_execution": value["target_execution"],
        "bindings": bindings,
        "compiler_runs_in_replay": 0,
        "authority": bind(path),
    }


def validate_bound_root_surrogate(proof: dict[str, Any]) -> None:
    source = proof.get("source_truth", {})
    require(
        proof.get("status") == "pass"
        and source.get("obj_h_sha256")
            == hashlib.sha256(ARTIFACT_REPLAY.ROOT_GATE.OBJ_H.read_bytes()).hexdigest()
        and source.get("helper_source_sha256") == hashlib.sha256(
            ARTIFACT_REPLAY.ROOT_GATE.helper_source().encode()).hexdigest()
        and source.get("emitted_rows") == 57344
        and proof.get("root_surrogates", {}).get("count") == 1536
        and all(value == 0 for value in proof.get(
            "collision_intersections", {}).values()),
        "bound Link-96 root-surrogate proof differs from current inputs",
    )


def bound_root_surrogate_gate() -> dict[str, Any]:
    """Select proof ancestry by exact inputs, never by historical age."""
    internal = load(ROOT_PROOF_INTERNAL)
    proof = internal["fresh_prelink_gates"]["root_surrogate_complete_domain"]
    validate_bound_root_surrogate(proof)
    return deepcopy(proof)


def bound_root_surrogate_mutations() -> list[str]:
    proof = bound_root_surrogate_gate()
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "stale-obj-h": lambda x: x["source_truth"].update(
            obj_h_sha256="c780e3573fc4fa09c4b08ec7c5c80168afa74f1cc7e693e028e4c7066734c306"),
        "wrong-helper": lambda x: x["source_truth"].update(
            helper_source_sha256="0" * 64),
        "short-domain": lambda x: x["source_truth"].update(emitted_rows=57343),
        "red-proof": lambda x: x.update(status="FIRST RED"),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        candidate = deepcopy(proof); mutate(candidate)
        try:
            validate_bound_root_surrogate(candidate)
        except CardError:
            rejected.append(name)
    require(len(rejected) == len(cases),
            "input-selected root-surrogate mutation survived")
    return rejected


def replay_source_gate(source: str | None = None) -> dict[str, Any]:
    text = Path(__file__).read_text(encoding="utf-8") if source is None else source
    tree = ast.parse(text)
    node = next((item for item in tree.body
                 if isinstance(item, ast.FunctionDef)
                 and item.name == "post_link_replay"), None)
    require(node is not None, "post-link replay entrypoint absent")
    calls = {ast.unparse(item.func) for item in ast.walk(node)
             if isinstance(item, ast.Call)}
    forbidden = {
        "L95.CAN.run_wplto", "L95.L94.build", "L95.build",
        "L95.CAN.PRODUCT.single_link", "subprocess.check_call",
    }
    require(not (calls & forbidden),
            "post-link replay can re-enter compilation or linking")
    replacement_calls = [
        item for item in ast.walk(node) if isinstance(item, ast.Call)
        and ast.unparse(item.func) == "base.replacement_gates"]
    replacement_keywords = (
        {item.arg: ast.unparse(item.value)
         for item in replacement_calls[0].keywords}
        if len(replacement_calls) == 1 else {})
    abi_calls = [item for item in ast.walk(node) if isinstance(item, ast.Call)
                 and ast.unparse(item.func) == "can.fresh_real_abi_gate"]
    postlink_calls = [
        item for item in ast.walk(node) if isinstance(item, ast.Call)
        and ast.unparse(item.func)
            == "can.fresh_current_product_postlink_gate"]
    linked_calls = [item for item in ast.walk(node) if isinstance(item, ast.Call)
                    and ast.unparse(item.func)
                        == "can.LINK_GATE.linked_gates"]
    abi_keywords = ({item.arg: ast.unparse(item.value)
                     for item in abi_calls[0].keywords}
                    if len(abi_calls) == 1 else {})
    postlink_keywords = ({item.arg: ast.unparse(item.value)
                          for item in postlink_calls[0].keywords}
                         if len(postlink_calls) == 1 else {})
    linked_keywords = ({item.arg: ast.unparse(item.value)
                        for item in linked_calls[0].keywords}
                       if len(linked_calls) == 1 else {})
    require(
        len(replacement_calls) == 1
        and replacement_keywords == {
            "capacity_qualifier": "can.fresh_session_capacity_gate",
            "root_qualifier": "bound_root",
            "direct_qualifier": "bound_direct_entry_gate",
            "qualification_root": "REPLAY",
            "verifier_base":
                "can.PRODUCT.LINK60_VERIFIER_BINDING_BASE",
        }
        and len(abi_calls) == len(postlink_calls) == len(linked_calls) == 1
        and abi_keywords.get("report_path")
            == "REPLAY / 'c2-asm-leaf-real-abi-callers.json'"
        and postlink_keywords == {
            "internal_path": "REPLAY_INTERNAL", "artifact_root": "elf.parent"}
        and len(linked_calls[0].args) == 1
        and ast.unparse(linked_calls[0].args[0]) == "elf"
        and linked_keywords.get("receipt") == "REPLAY_LINKED_GATE",
        "post-link replay contains an ambient qualification-stage input",
    )
    return {
        "status": "passed-artifact-only-post-link-replay-source-shape",
        "forbidden_calls_absent": sorted(forbidden),
        "capacity_qualifier": "can.fresh_session_capacity_gate",
        "replacement_inputs": "explicit-capacity-root-direct-and-output",
        "real_ABI_input": "explicit-elf-and-report",
        "postlink_inputs": "explicit-internal-and-artifact-root",
        "linked_inputs": "explicit-elf-and-receipt",
    }


def replay_source_mutations() -> list[str]:
    source = Path(__file__).read_text(encoding="utf-8")
    anchor = """replacement = base.replacement_gates(
            product, elf, prelink,
            capacity_qualifier=can.fresh_session_capacity_gate,
            root_qualifier=bound_root,
            direct_qualifier=bound_direct_entry_gate,
            qualification_root=REPLAY,
            verifier_base=can.PRODUCT.LINK60_VERIFIER_BINDING_BASE)"""
    require(anchor in source, "post-link replay mutation anchor absent")
    prefix, separator, suffix = source.rpartition(anchor)
    require(bool(separator), "post-link replay callsite mutation anchor absent")
    mutants = {
        "re-enter-WPLTO":
            prefix + "replacement = L95.CAN.run_wplto()" + suffix,
        "restore-prior-world-capacity-stage": prefix +
            "replacement = base.replacement_gates(product, elf, prelink)" +
            suffix,
        "drop-explicit-root-qualifiers": prefix +
            "replacement = base.replacement_gates(\n"
            "            product, elf, prelink,\n"
            "            capacity_qualifier=can.fresh_session_capacity_gate)" +
            suffix,
    }
    rejected: list[str] = []
    for name, mutant in mutants.items():
        try:
            replay_source_gate(mutant)
        except CardError:
            rejected.append(name)
    require(rejected == list(mutants),
            "post-link replay source mutation survived")
    return rejected


def qualified_internal_path() -> Path:
    return REPLAY_INTERNAL if REPLAY_INTERNAL.is_file() else (
        completed_paths()["receipts"] / "wplto-internal.json")


def build_manifest(wplto: dict[str, Any], completion: dict[str, Any]) -> dict[str, Any]:
    value = L95.build_manifest(wplto, completion)
    geo = PRE.geometry()
    value["static_plane"].update({
        "status": "passed-v1.5.0-frozen-freight-static-plane",
        "bank2_static_code_bytes": geo["static_code_bytes"],
        "entries": geo["entries"], "resolutions": geo["resolutions"],
        "roots": geo["roots"], "direct_entry_refs": geo["direct_entry_refs"],
        "product_build_id": geo["product_build_id"],
        "bank2_sha256": geo["bank2_sha256"],
        "stdlib_manifest": bind(PRE.STDLIB),
        "linker_free_preflight": bind(PRE.RECEIPT),
    })
    value["candidate"] = {
        "release": RELEASE, "link": LINK, "pre_promotion": True,
        "public_surface_changed": True, "source_driver": bind(DRIVER),
        "activation_defines": load(CONTRACT)["build"]["activation_defines"],
    }
    value["terminal_return_guard"] = {
        "feature": PRODUCT.TERMINAL_RETURN_GUARD_FEATURE,
        "ELF_gate": bind(GUARD_RECEIPT), "resident_delta_bytes": 0,
        "hardware_status": "pending",
    }
    MANIFEST.write_bytes(L95.CAN.json_bytes(value))
    return value


def complete_action() -> int:
    configure()
    return L95.L94.complete_action()


def complete_in_fresh_process() -> None:
    environment = os.environ.copy()
    environment.update(L95.CAN.canonical_build_environment())
    if REPLAY_PROFILE.is_file():
        environment["LISP65_V150_POSTLINK_REPLAY"] = "1"
    result = subprocess.run(
        [sys.executable, str(DRIVER), "_complete"], cwd=ROOT, env=environment,
        text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False,
    )
    require(result.returncode == 0,
            "v1.5 fresh-process completion red:\n" + result.stdout)
    paths = completed_paths()
    (paths["receipts"] / "artifact-completion.log").write_text(
        result.stdout, encoding="utf-8")


def freight_gates() -> dict[str, Any]:
    PRE.validate({key: value for key, value in load(PRE.RECEIPT).items()
                  if key != "mutations_rejected"}, verify=True)
    closure = load(CLOSURE.RECEIPT)
    rejected = closure.pop("mutations_rejected", None)
    CLOSURE.validate(closure, verify=True)
    require(rejected == CLOSURE.mutations(closure),
            "v1.5 freight closure mutation set drift")
    return {
        "release_closure": bind(CLOSURE.RECEIPT),
        "preflight": bind(PRE.RECEIPT),
        "f018b_content_safe_reads": run([
            sys.executable,
            "tools/host-lisp/c2_f018b_content_safe_reads.py", "check"],
            "F018B content-safe read gate"),
        "direct_expression": run([
            sys.executable, "tools/host-lisp/c2_repl_direct_expression_gate.py",
            "check"], "direct-expression gate"),
        "experience": run([
            sys.executable, "tools/host-lisp/c2_startup_require_experience_gate.py",
            "check"], "Experience gate"),
        "trace_abi": run([
            sys.executable, "tools/host-lisp/c2_trace_core_abi.py", "check"],
            "trace ABI gate"),
        "packed_callees": run([
            sys.executable, "tools/host-lisp/c2_packed_symbolic_callee_closure.py",
            "audit", "--product", PRE.PRODUCT.relative_to(ROOT).as_posix()],
            "packed symbolic callee closure"),
    }


def derive() -> dict[str, Any]:
    paths = completed_paths()
    internal = load(qualified_internal_path())
    replacement = internal["fresh_replacement_gates"]
    walls = replacement["walls"]
    capacity = replacement["capacity"]
    completion = load(paths["receipts"] / "artifact-completion.json")
    manifest = load(MANIFEST)
    require(
        internal["execution_accounting"]["product_closure_links"] == 1
        and replacement["status"] == "passed"
        and walls["bank0_text_headroom_bytes"] >= 32
        and walls["e000_headroom_bytes"] >= 54
        and walls["ordinary_bank0_bss_headroom_bytes"] >= 0
        and walls["resident_island_headroom_bytes"] >= 0
        and capacity["session_family_headroom_bytes"] >= 0
        and completion["status"]
            == "passed-no-relink-publish-last-artifact-completion"
        and manifest["candidate"]["release"] == RELEASE
        and manifest["terminal_return_guard"]["resident_delta_bytes"] == 0,
        "v1.5 product closure did not close",
    )
    return {
        "format": FORMAT, "recorded_on": "2026-08-11", "status": STATUS,
        "attempt_accounting": {
            "product_cards_authorized": 1, "product_cards_consumed": 1,
            "product_closure_links": 1, "hardware_runs": 0,
        },
        "freight": {
            "terminal_return_guard": True, "direct_expression": True,
            "boot_liveness": True, "require_echo": True,
            "banner": "WORKBENCH 1.5.0", "resident_delta_bytes": 0,
        },
        "geometry": {
            **PRE.geometry(), "walls": walls, "session_capacity": capacity,
        },
        "artifacts": {
            "manifest": bind(MANIFEST),
            "product": bind(paths["final"] / "lisp65-c2-substitution-linked.prg"),
            "ELF": bind(paths["final"] / "lisp65-c2-substitution-linked.prg.elf"),
            "map": bind(paths["final"] / "lisp65-c2-substitution-linked.prg.map"),
            "profile": bind(paths["final"] / "resolved-profile.txt"),
            "completion": bind(paths["receipts"] / "artifact-completion.json"),
            "guard": bind(GUARD_RECEIPT),
        },
        "hardware_handoff": {"status": "media-pending", "rows": 5},
        "claim_limit": (
            "One host-green v1.5 product card. Media, device acceptance, Halt "
            "#1, release and publication remain unclaimed."),
    }


def post_link_replay() -> tuple[dict[str, Any], dict[str, Any]]:
    """Qualify the frozen product link without entering its producer."""
    ambient = load(AMBIENT.RECEIPT)
    ambient_mutations = ambient.pop("mutations_rejected", None)
    AMBIENT.validate(ambient, verify=True)
    require(ambient_mutations == AMBIENT.mutations(ambient),
            "remaining qualification ambient-closure mutation set drift")
    capacity_identity = load(CAPACITY_IDENTITY.RECEIPT)
    capacity_mutations = capacity_identity.pop("mutations_rejected", None)
    CAPACITY_IDENTITY.validate(capacity_identity, verify=True)
    require(capacity_mutations == CAPACITY_IDENTITY.mutations(
        capacity_identity), "candidate capacity identity mutation set drift")
    content_map = load(SLICE_MAP.RECEIPT)
    content_map_mutations = content_map.pop("mutations_rejected", None)
    SLICE_MAP.validate(content_map, verify=True)
    require(content_map_mutations == SLICE_MAP.mutations(content_map),
            "Link-97 successor content-map mutation set drift")
    source_gate = replay_source_gate()
    source_mutations = replay_source_mutations()
    identity_gate = F1W.target_identity_source_gate()
    identity_mutations = F1W.target_identity_mutations()
    root_gate = bound_root_surrogate_gate()
    root_mutations = bound_root_surrogate_mutations()
    before = frozen_red_artifact_preflight()
    paths = configure(REPLAY_PROFILE)
    can = L95.CAN
    old_wplto = can.configure_wplto()
    base = can.REAL_ABI_LINK.BASE_LINK
    product = paths["wplto"] / "lisp65-c2-substitution-linked.prg"
    elf = Path(str(product) + ".elf")
    map_file = Path(str(product) + ".map")
    old_run = subprocess.run
    old_internal = can.LINK_GATE.BASE.INTERNAL
    old_linked_gate = can.LINK_GATE.LINKED_GATE
    commands: list[str] = []

    def bound_root() -> dict[str, Any]:
        return deepcopy(root_gate)

    def guarded_run(command: Any, *args: Any, **kwargs: Any) -> Any:
        executable = Path(str(command[0] if isinstance(command, (list, tuple))
                              else command)).name
        lowered = executable.lower()
        require("clang" not in lowered and lowered not in {
                    "cc", "gcc", "ld", "ld.lld", "lld",
                    "mos-mega65-clang", "llvm-link"},
                f"post-link replay attempted compiler/linker: {executable}")
        commands.append(executable)
        return old_run(command, *args, **kwargs)

    # These pre-link facts were already established before the frozen link;
    # replacement_gates consumes only the two booleans below.  Re-running
    # their C harnesses would violate the artifact-only authorization.
    prelink = {
        "status": "passed-bound-pre-link-semantics-not-reexecuted",
        "c2d_v6_host_semantics": {
            "stale_generation": {"old_handles_rejected": 10}},
        "bank3_lifetime_model": {
            "invalidation_before_overwrite": True},
        "direct_entry": bound_direct_entry_gate(),
        "root_surrogate_complete_domain": bound_root(),
    }
    try:
        subprocess.run = guarded_run
        replacement = base.replacement_gates(
            product, elf, prelink,
            capacity_qualifier=can.fresh_session_capacity_gate,
            root_qualifier=bound_root,
            direct_qualifier=bound_direct_entry_gate,
            qualification_root=REPLAY,
            verifier_base=can.PRODUCT.LINK60_VERIFIER_BINDING_BASE)
        abi = can.fresh_real_abi_gate(
            elf, report_path=REPLAY / "c2-asm-leaf-real-abi-callers.json")
        require(replacement["status"] == "passed"
                and abi["status"] == "passed-all-assembler-leaf-abi-contracts",
                "Link-97 artifact-only replacement or ABI gate red")
        internal = {
            "format": "lisp65-c2-lite-v6-real-abi-link97-replay-structural-v1",
            "recorded_on": "2026-08-11",
            "status": "passed-new-c2-lite-real-abi-identity-hardware-not-run",
            "promotable": False,
            "link_number": LINK,
            "execution_accounting": {
                "resident_island_seed_links": 1,
                "product_closure_links": 1,
                "replay_compiler_runs": 0,
                "replay_linker_runs": 0,
                "hardware_runs": 0,
            },
            "authority": {
                "owner_authorization_commits": REPLAY_AUTHORIZATIONS,
                "qualification_ambient_closure": bind(AMBIENT.RECEIPT),
                "qualification_ambient_mutations_rejected":
                    ambient_mutations,
                "candidate_capacity_identity": bind(
                    CAPACITY_IDENTITY.RECEIPT),
                "candidate_capacity_source_gate":
                    capacity_identity["source_gate"],
                "candidate_capacity_mutations_rejected":
                    capacity_mutations,
                "successor_content_map": bind(SLICE_MAP.RECEIPT),
                "first_red": bind(FIRST_RED),
                "first_replay_red": bind(REPLAY_FIRST_RED_RECEIPT),
                "candidate_profile": bind(REPLAY_PROFILE),
                "F1_candidate_identity_gate": identity_gate,
                "F1_identity_mutations_rejected": identity_mutations,
                "artifact_replay_source_gate": source_gate,
                "artifact_replay_source_mutations_rejected": source_mutations,
                "bound_direct_entry": prelink["direct_entry"]["authority"],
                "bound_root_surrogate": bind(ROOT_PROOF_INTERNAL),
                "bound_root_surrogate_inputs": root_gate["source_truth"],
                "bound_root_surrogate_mutations_rejected": root_mutations,
            },
            "product_identity": {
                "product": bind(product), "elf": bind(elf),
                "map": bind(map_file),
                "resolved_profile": bind(paths["wplto"] / "resolved-profile.txt"),
                "new_identity": False,
            },
            "fresh_prelink_gates": prelink,
            "fresh_replacement_gates": replacement,
            "fresh_real_abi_gate": abi,
            "claim_limit": (
                "Artifact-only qualification of the frozen Link-97 product "
                "link; no WPLTO, compilation, relink, card, media or hardware."),
        }
        REPLAY_INTERNAL.write_bytes(canonical(internal))
        can.LINK_GATE.BASE.INTERNAL = REPLAY_INTERNAL
        can.LINK_GATE.LINKED_GATE = REPLAY_LINKED_GATE
        current = can.fresh_current_product_postlink_gate(
            internal_path=REPLAY_INTERNAL, artifact_root=elf.parent)
        linked, linked_abi = can.LINK_GATE.linked_gates(
            elf, receipt=REPLAY_LINKED_GATE)
        require(
            current["status"] == "passed-current-v4-pre-publish-WPLTO-closure"
            and linked["status"]
                == "passed-linked-stateless-mode-derived-completion-length"
            and linked_abi["status"] == "passed-all-assembler-leaf-abi-contracts",
            "Link-97 current post-link closure replay red",
        )
    finally:
        subprocess.run = old_run
        can.LINK_GATE.BASE.INTERNAL = old_internal
        can.LINK_GATE.LINKED_GATE = old_linked_gate
        can.restore_wplto(old_wplto)
    after = frozen_red_artifact_preflight()
    require(before == after, "artifact-only qualification changed frozen Link-97")
    raw = load(paths["receipts"] / "wplto-raw.json")
    authority = {
        "status": (
            "passed-one-current-WPLTO-closure-at-repaired-historical-"
            "qualification-boundary"),
        "publish_last_authority": (
            f"0x{can.PRODUCT.LINK60_VERIFIER_BINDING_BASE:04x}"),
        "historical_checker_boundary": {
            "classification": (
                "historical-size-pin-repaired-by-candidate-identity-"
                "artifact-only-replay"),
            "raw_status": raw["status"],
            "raw_error": raw["error"],
            "captured_driver_log": bind(
                paths["receipts"] / "wplto-historical-driver.log"),
            "current_replacement_gates": current,
        },
        "qualification": bind(REPLAY_INTERNAL),
        "linked_gate": bind(REPLAY_LINKED_GATE),
    }
    replay = {
        "format": "lisp65-c2.3-v150-link97-post-link-qualification-replay-v1",
        "recorded_on": "2026-08-11",
        "status": "passed-artifact-only-post-link-qualification-replay",
        "authorization_commits": REPLAY_AUTHORIZATIONS,
        "qualification_ambient_closure": bind(AMBIENT.RECEIPT),
        "qualification_ambient_mutations_rejected": ambient_mutations,
        "candidate_capacity_identity": bind(CAPACITY_IDENTITY.RECEIPT),
        "candidate_capacity_source_gate": capacity_identity["source_gate"],
        "candidate_capacity_mutations_rejected": capacity_mutations,
        "successor_content_map": bind(SLICE_MAP.RECEIPT),
        "first_replay_red": bind(REPLAY_FIRST_RED_RECEIPT),
        "F1_identity_gate": identity_gate,
        "F1_identity_mutations_rejected": identity_mutations,
        "replay_source_gate": source_gate,
        "replay_source_mutations_rejected": source_mutations,
        "bound_root_surrogate": bind(ROOT_PROOF_INTERNAL),
        "bound_root_surrogate_inputs": root_gate["source_truth"],
        "bound_root_surrogate_mutations_rejected": root_mutations,
        "immutable_before": before,
        "immutable_after": after,
        "current_postlink_closure": current,
        "linked_completion": linked,
        "linked_assembler_ABI": linked_abi,
        "read_only_tool_invocations": commands,
        "execution_accounting": {
            "WPLTO_runs": 0, "compiler_runs": 0, "linker_runs": 0,
            "new_product_cards": 0, "hardware_runs": 0,
        },
        "claim_limit": (
            "Qualification and post-link completion eligibility for the "
            "frozen successful Link-97 artifacts only."),
    }
    return authority, replay


def validate(value: dict[str, Any], *, verify: bool) -> None:
    require(
        value.get("format") == FORMAT and value.get("status") == STATUS
        and value.get("attempt_accounting") == {
            "product_cards_authorized": 1, "product_cards_consumed": 1,
            "product_closure_links": 1, "hardware_runs": 0}
        and value.get("freight", {}).get("banner") == "WORKBENCH 1.5.0"
        and value.get("freight", {}).get("resident_delta_bytes") == 0
        and value.get("hardware_handoff", {}).get("status") == "media-pending",
        "v1.5 product-card claim drift",
    )
    if verify:
        require(value == derive(), "v1.5 product-card receipt is stale")


def mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "hide-card": lambda x: x["attempt_accounting"].update(
            product_cards_consumed=0),
        "hide-link": lambda x: x["attempt_accounting"].update(
            product_closure_links=0),
        "claim-device": lambda x: x["attempt_accounting"].update(
            hardware_runs=1),
        "wrong-banner": lambda x: x["freight"].update(
            banner="WORKBENCH 1.4.0"),
        "grow-resident": lambda x: x["freight"].update(resident_delta_bytes=1),
        "claim-media": lambda x: x["hardware_handoff"].update(status="ready"),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        candidate = deepcopy(value); mutate(candidate)
        try:
            validate(candidate, verify=False)
        except CardError:
            rejected.append(name)
    require(len(rejected) == len(cases), "v1.5 product mutation survived")
    return rejected


def build() -> int:
    require(not BUILD.exists() and not RECEIPT.exists()
            and not GUARD_RECEIPT.exists(), "v1.5 product card is one-shot")
    preflight = load(PRE.RECEIPT)
    rejected = preflight.pop("mutations_rejected", None)
    PRE.validate(preflight, verify=True)
    require(rejected == PRE.mutations(preflight), "preflight mutations drift")
    require(CLOSURE.RECEIPT.is_file(),
            "v1.5 freight closure absent before product card")
    freight = freight_gates()
    BUILD.mkdir(parents=True)
    shutil.copytree(PRE.BUILD / "static-plane", BUILD / "static-plane")
    paths = configure()
    static = L95.BASE.PROBE.REQ.build_static_plane()
    plane = L95.BASE.PROBE.REQ.F1W.static_gate()
    header = L95.CORE.bind_generated_stdlib_header(paths)
    geo = PRE.geometry()
    require(
        static["semantics"]["code_bytes"] == geo["static_code_bytes"]
        and plane["static_code_bytes"] == geo["static_code_bytes"]
        and header["manifest"] == bind(PRE.STDLIB),
        "v1.5 copied static plane failed its pre-card gate",
    )
    wplto = L95.CAN.run_wplto()
    work_elf = BUILD / "wplto/lisp65-c2-substitution-linked.prg.elf"
    work_prg = BUILD / "wplto/lisp65-c2-substitution-linked.prg"
    before = guard_result(work_elf, work_prg)
    GUARD_RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    GUARD_RECEIPT.write_bytes(canonical(before))
    complete_in_fresh_process()
    final_elf = paths["final"] / "lisp65-c2-substitution-linked.prg.elf"
    final_prg = paths["final"] / "lisp65-c2-substitution-linked.prg"
    require(semantic_guard(before) == semantic_guard(
        guard_result(final_elf, final_prg)),
        "artifact completion changed terminal-guard proof")
    completion = load(paths["receipts"] / "artifact-completion.json")
    manifest = build_manifest(wplto, completion)
    checked = L95.CAN.check()
    require(checked["identity"] == manifest["identity"],
            "v1.5 completed product identity red")
    (paths["receipts"] / "v1.5.0-feature-gates.json").write_bytes(canonical({
        "status": "passed-v1.5.0-frozen-freight-gates",
        "freight": freight, "target_stdlib_header": header,
    }))
    value = derive(); validate(value, verify=False)
    value["mutations_rejected"] = mutations(value)
    RECEIPT.write_bytes(canonical(value))
    print("v1.5 Link-97 product card: PASS "
          f"text={value['geometry']['walls']['bank0_text_headroom_bytes']} "
          f"e000={value['geometry']['walls']['e000_headroom_bytes']} "
          f"bank2={value['geometry']['bank2_headroom_bytes']}")
    return 0


def replay() -> int:
    require(
        FIRST_RED.is_file() and REPLAY_FIRST_RED_RECEIPT.is_file()
        and REPLAY_FIRST_RED.is_dir()
        and (REPLAY_FIRST_RED / "candidate-profile.json").is_file()
        and REPLAY_PREVIOUS_RED.is_dir()
        and (REPLAY_PREVIOUS_RED / "candidate-profile.json").is_file()
        and BUILD.is_dir()
        and not REPLAY.exists() and not RECEIPT.exists()
        and not GUARD_RECEIPT.exists() and not completed_paths()["final"].exists(),
        "v1.5 post-link replay boundary is not fresh",
    )
    validate_first_red(load(FIRST_RED), verify=True)
    before = frozen_red_artifact_preflight()
    write_replay_profile()
    authority, replay_value = post_link_replay()
    paths = completed_paths()
    work_elf = paths["wplto"] / "lisp65-c2-substitution-linked.prg.elf"
    work_prg = paths["wplto"] / "lisp65-c2-substitution-linked.prg"
    guard_before = guard_result(work_elf, work_prg)
    GUARD_RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    GUARD_RECEIPT.write_bytes(canonical(guard_before))
    complete_in_fresh_process()
    require(frozen_red_artifact_preflight() == before,
            "artifact completion changed frozen Link-97 WPLTO identity")
    final_elf = paths["final"] / "lisp65-c2-substitution-linked.prg.elf"
    final_prg = paths["final"] / "lisp65-c2-substitution-linked.prg"
    require(
        semantic_guard(guard_before) == semantic_guard(
            guard_result(final_elf, final_prg)),
        "artifact completion changed terminal-return-guard proof",
    )
    completion = load(paths["receipts"] / "artifact-completion.json")
    manifest = build_manifest(authority, completion)
    checked = L95.CAN.check()
    require(checked["identity"] == manifest["identity"],
            "v1.5 completed replay identity red")
    freight = freight_gates()
    header = L95.CORE.bind_generated_stdlib_header(paths)
    (paths["receipts"] / "v1.5.0-feature-gates.json").write_bytes(canonical({
        "status": "passed-v1.5.0-frozen-freight-gates",
        "freight": freight, "target_stdlib_header": header,
    }))
    value = derive(); validate(value, verify=False)
    value["mutations_rejected"] = mutations(value)
    RECEIPT.write_bytes(canonical(value))
    replay_value["artifact_completion"] = bind(
        paths["receipts"] / "artifact-completion.json")
    replay_value["completed_product"] = bind(final_prg)
    replay_value["completed_ELF"] = bind(final_elf)
    replay_value["product_card"] = bind(RECEIPT)
    replay_value["immutable_after_completion"] = frozen_red_artifact_preflight()
    replay_value["status"] = (
        "passed-artifact-only-qualification-and-no-relink-completion-replay")
    REPLAY_RECEIPT.write_bytes(canonical(replay_value))
    print("v1.5 Link-97 post-link replay: PASS "
          f"text={value['geometry']['walls']['bank0_text_headroom_bytes']} "
          f"e000={value['geometry']['walls']['e000_headroom_bytes']} "
          "WPLTO=0 compiler=0 linker=0")
    return 0


def check() -> int:
    value = load(RECEIPT)
    rejected = value.pop("mutations_rejected", None)
    validate(value, verify=True)
    require(rejected == mutations(value), "v1.5 product mutations drift")
    print("v1.5 Link-97 product card check: PASS")
    return 0


def selftest() -> int:
    GUARD.semantic_cases()
    F1W.target_identity_source_gate()
    F1W.target_identity_mutations()
    replay_source_gate()
    replay_source_mutations()
    bound_root_surrogate_gate()
    bound_root_surrogate_mutations()
    if FIRST_RED.exists():
        validate_first_red(load(FIRST_RED), verify=True)
    else:
        require(PRE.geometry() == profile_geometry(),
                "v1.5 profile preflight drift")
    print("v1.5 product-card selftest: PASS")
    return 0


def first_red_value() -> dict[str, Any]:
    paths = completed_paths()
    base = load(paths["receipts"] / "wplto-base-result.json")
    internal = load(paths["receipts"] / "wplto-internal.json")
    raw = load(paths["receipts"] / "wplto-raw.json")
    qualification = load(paths["receipts"] / "wplto-qualification.json")
    require(
        base.get("WPLTO", {}).get("product_completed") is True
        and base.get("WPLTO", {}).get("return_code") == 2
        and internal.get("status") == "FIRST RED: C2-lite real-ABI Link 50 stopped"
        and "fresh_replacement_gates" not in internal
        and raw.get("status")
            == "FIRST RED: historical checker stopped current-product L-full keymap WPLTO"
        and qualification.get("status")
            == "FIRST RED: final E000-S1 map or qualification did not close",
        "v1.5 card stopped-state authority drift",
    )
    product = BUILD / "wplto/lisp65-c2-substitution-linked.prg"
    elf = product.with_suffix(product.suffix + ".elf")
    map_file = product.with_suffix(product.suffix + ".map")
    require(product.is_file() and elf.is_file() and map_file.is_file(),
            "v1.5 red card linked artifacts absent")
    fixture = ROOT / "tools/host-lisp/c2_f1_published_value_call_wplto.py"
    source = fixture.read_text(encoding="utf-8")
    require("EXPECTED_STATIC = 34748" in source
            and "len(expected_plane) == EXPECTED_STATIC" in source,
            "attributed historical F1 fixture assumption drift")
    return {
        "format": "lisp65-c2.3-v150-link97-product-card-first-red-v1",
        "recorded_on": "2026-08-11",
        "status": "FIRST RED; OWNER-DISPOSITION-REQUIRED; NO-RETRY-AUTHORIZED",
        "attempt_accounting": {
            "product_cards_authorized": 1, "product_cards_consumed": 1,
            "product_links": 1, "artifact_completions": 0,
            "media_builds": 0, "device_contacts": 0,
        },
        "boundary": {
            "product_link_completed": True,
            "linked_overlays_packed": True,
            "fresh_replacement_gates_completed": False,
            "artifact_completion_completed": False,
            "manifest_written": False,
        },
        "mechanism": {
            "classification": "post-link-historical-F1-target-fixture-geometry-pin",
            "fixture_expected_static_bytes": 34748,
            "candidate_static_bytes": PRE.geometry()["static_code_bytes"],
            "failure": "F1 Bank-2 target fixture artifact geometry drift",
            "consequence": (
                "The current product link exists, but the inherited F1 target "
                "fixture rejected the successor plane before the fresh "
                "replacement-gate dictionary could be projected."),
        },
        "frozen_artifacts": {
            "product": bind(product), "ELF": bind(elf), "map": bind(map_file),
            "wplto_internal": bind(paths["receipts"] / "wplto-internal.json"),
            "wplto_base_result": bind(
                paths["receipts"] / "wplto-base-result.json"),
            "driver_log": bind(paths["receipts"] / "wplto-historical-driver.log"),
        },
        "authorities": {
            "executed_driver": EXECUTED_DRIVER,
            "current_recorder": bind(DRIVER),
            "historical_fixture": bind(fixture),
            "preflight": bind(PRE.RECEIPT),
            "freight_closure": bind(CLOSURE.RECEIPT),
        },
        "disposition": {
            "automatic_retry_authorized": False,
            "media_or_device_authorized": False,
            "owner_question": (
                "Park the release block or authorize a narrowly bounded "
                "identity-not-position repair for the inherited F1 target fixture."),
        },
        "claim_limit": (
            "One consumed v1.5 product card and one completed product link. "
            "No completed product closure, media, device, Halt #1, release or "
            "publication claim."),
    }


def validate_first_red(value: dict[str, Any], *, verify: bool) -> None:
    require(
        value.get("format")
            == "lisp65-c2.3-v150-link97-product-card-first-red-v1"
        and value.get("status")
            == "FIRST RED; OWNER-DISPOSITION-REQUIRED; NO-RETRY-AUTHORIZED"
        and value.get("attempt_accounting") == {
            "product_cards_authorized": 1, "product_cards_consumed": 1,
            "product_links": 1, "artifact_completions": 0,
            "media_builds": 0, "device_contacts": 0}
        and value.get("disposition", {}).get("automatic_retry_authorized") is False
        and value.get("disposition", {}).get("media_or_device_authorized") is False
        and value.get("frozen_artifacts") == FROZEN_RED_ARTIFACTS,
        "v1.5 product-card First Red claim drift",
    )
    if verify:
        require(value.get("authorities") == {
            "executed_driver": EXECUTED_DRIVER,
            "current_recorder": FROZEN_FIRST_RED_AUTHORITIES[
                "current_recorder"],
            "historical_fixture": FROZEN_FIRST_RED_AUTHORITIES[
                "historical_fixture"],
            "preflight": FROZEN_FIRST_RED_AUTHORITIES["preflight"],
            "freight_closure": FROZEN_FIRST_RED_AUTHORITIES[
                "freight_closure"],
        }, "v1.5 product-card First Red authority drift")
        existing = [ROOT / row["path"]
                    for row in FROZEN_RED_ARTIFACTS.values()
                    if (ROOT / row["path"]).is_file()]
        require(
            all(bind(path) == FROZEN_RED_ARTIFACTS[key]
                for key, path in ((key, ROOT / row["path"])
                                  for key, row in FROZEN_RED_ARTIFACTS.items())
                if path.is_file()),
            "v1.5 frozen First-Red artifact drift",
        )
        require(not existing or len(existing) == len(FROZEN_RED_ARTIFACTS),
                "partial v1.5 First-Red artifact set")


def record_first_red() -> int:
    require(BUILD.is_dir() and not RECEIPT.exists(),
            "v1.5 First Red boundary absent")
    value = first_red_value(); validate_first_red(value, verify=False)
    FIRST_RED.parent.mkdir(parents=True, exist_ok=True)
    FIRST_RED.write_bytes(canonical(value))
    print("v1.5 Link-97 product card: FIRST RED bound; owner disposition required")
    return 0


def check_first_red() -> int:
    validate_first_red(load(FIRST_RED), verify=True)
    print("v1.5 Link-97 product-card First Red check: PASS no-retry")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action", choices=("build", "replay", "_complete", "check", "selftest",
                           "record-first-red", "check-first-red"))
    action = parser.parse_args().action
    if action == "_complete":
        os.environ.update(L95.CAN.canonical_build_environment())
        return complete_action()
    if action == "build":
        environment = L95.CAN.canonical_build_environment()
        if any(os.environ.get(key) != value for key, value in environment.items()):
            updated = os.environ.copy(); updated.update(environment)
            os.execve(sys.executable, [sys.executable, str(DRIVER), "build"], updated)
        return build()
    if action == "replay":
        environment = L95.CAN.canonical_build_environment()
        if any(os.environ.get(key) != value for key, value in environment.items()):
            updated = os.environ.copy(); updated.update(environment)
            os.execve(sys.executable,
                      [sys.executable, str(DRIVER), "replay"], updated)
        return replay()
    return {"check": check, "selftest": selftest,
            "record-first-red": record_first_red,
            "check-first-red": check_first_red}[action]()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (CardError, PRE.PreflightError, GUARD.GateError, RuntimeError,
            OSError, ValueError, KeyError, json.JSONDecodeError,
            subprocess.SubprocessError) as error:
        print(f"v1.5 Link-97 product card: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(2)
