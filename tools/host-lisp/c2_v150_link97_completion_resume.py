#!/usr/bin/env python3
"""Resume Link-97 at completion without repeating its green r10 qualification."""

from __future__ import annotations

import argparse
import ast
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
sys.path.insert(0, str(HOST))
import c2_v150_candidate_product as CARD  # noqa: E402
import c2_v150_replay_r10 as R10  # noqa: E402
import c2_v150_replay_r10_first_red as RED  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
SESSION = ROOT / "config/c2-v150-link97-completion-resume-session.json"
CONTENT = EVIDENCE / (
    "c2.3-v1.5.0-link97-three-postlink-successor-content-map-receipt.json")
RESUME_RECEIPT = CARD.REPLAY_RECEIPT
AUTHORIZATION = "b3dfae83"
FORMAT = "lisp65-c2.3-v150-link97-r10-completion-resume-v1"
STATUS = "PASSED-R10-COMPLETION-RESUME; MEDIA-AND-HARDWARE-PENDING"


class ResumeError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ResumeError(message)


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
    return {"path": path.relative_to(ROOT).as_posix(),
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def calls(function: ast.FunctionDef) -> list[str]:
    return [ast.unparse(node.func) for node in ast.walk(function)
            if isinstance(node, ast.Call)]


def ownership_gate(*, adapter_source: str | None = None,
                   resume_source: str | None = None,
                   session_override: dict[str, Any] | None = None,
                   inherited_override: tuple[str, str] | None = None,
                   ) -> dict[str, Any]:
    adapter_text = (Path(R10.__file__).read_text(encoding="utf-8")
                    if adapter_source is None else adapter_source)
    resume_text = (Path(__file__).read_text(encoding="utf-8")
                   if resume_source is None else resume_source)
    adapter_tree = ast.parse(adapter_text)
    resume_tree = ast.parse(resume_text)
    adapter_functions = {node.name: node for node in adapter_tree.body
                         if isinstance(node, ast.FunctionDef)}
    resume_functions = {node.name: node for node in resume_tree.body
                        if isinstance(node, ast.FunctionDef)}
    complete = adapter_functions.get("complete")
    resume = resume_functions.get("resume_action")
    require(complete is not None and resume is not None,
            "completion owner entrypoint absent")
    complete_calls = calls(complete)
    resume_calls = calls(resume)

    if inherited_override is None:
        link95_text = Path(CARD.L95.__file__).read_text(encoding="utf-8")
        link94_text = Path(CARD.L95.L94.__file__).read_text(encoding="utf-8")
    else:
        link95_text, link94_text = inherited_override
    link95_tree = ast.parse(link95_text)
    link94_tree = ast.parse(link94_text)
    link95_complete = next(
        (node for node in link95_tree.body
         if isinstance(node, ast.FunctionDef) and node.name == "complete_action"),
        None)
    link94_complete = next(
        (node for node in link94_tree.body
         if isinstance(node, ast.FunctionDef) and node.name == "complete_action"),
        None)
    require(link95_complete is not None and link94_complete is not None,
            "inherited closer entrypoint absent")
    link95_calls = calls(link95_complete)
    link94_calls = calls(link94_complete)

    session = load(SESSION) if session_override is None else session_override
    resources = session.get("one_shot_resources", {})
    require(
        session.get("format")
            == "lisp65-c2-v150-link97-completion-resume-session-v1"
        and session.get("authorization_commit") == AUTHORIZATION
        and session.get("resume_budget") == 1
        and set(resources) == {
            "completion_child_product_profile",
            "resume_parent_product_profile",
        }
        and all(row.get("configuring_parties") == 1 and row.get("owner")
                for row in resources.values())
        and resources["completion_child_product_profile"].get("adapter_role")
            == "identity-binding-and-delegation-only"
        and session.get("qualification_policy", {}).get(
            "post_link_qualification_reexecuted") is False
        and complete_calls.count("CARD.configure_identity") == 1
        and "CARD.configure" not in complete_calls
        and complete_calls.count("CARD.L95.complete_action") == 1
        and link95_calls.count("L94.complete_action") == 1
        and link94_calls.count("configure_card") == 1
        and resume_calls.count("CARD.configure") == 1
        and resume_calls.count("run_completion_child") == 1
        and "CARD.post_link_replay" not in resume_calls
        and "R10.replay" not in resume_calls,
        "one-shot profile single-owner contract red")
    return {
        "status": "passed-named-single-owner-one-shot-session-contract",
        "session": bind(SESSION),
        "completion_child_configuring_parties": 1,
        "resume_parent_configuring_parties": 1,
        "adapter_profile_configure_calls": 0,
        "adapter_identity_bind_calls": 1,
        "qualification_replay_calls": 0,
        "completion_resume_calls": 1,
    }


def ownership_mutations() -> list[str]:
    adapter = Path(R10.__file__).read_text(encoding="utf-8")
    resume = Path(__file__).read_text(encoding="utf-8")
    session = load(SESSION)
    link95 = Path(CARD.L95.__file__).read_text(encoding="utf-8")
    link94 = Path(CARD.L95.L94.__file__).read_text(encoding="utf-8")
    cases: dict[str, Callable[[], None]] = {
        "adapter-reclaims-profile": lambda: ownership_gate(
            adapter_source=adapter.replace(
                "CARD.configure_identity(CARD.REPLAY_PROFILE)",
                "CARD.configure(CARD.REPLAY_PROFILE)", 1)),
        "adapter-adds-second-configurer": lambda: ownership_gate(
            adapter_source=adapter.replace(
                "return CARD.L95.complete_action()",
                "CARD.configure(CARD.REPLAY_PROFILE)\n"
                "    return CARD.L95.complete_action()", 1)),
        "unnamed-owner": lambda: ownership_gate(session_override=(
            lambda value: (value["one_shot_resources"]
                           ["completion_child_product_profile"].update(
                               owner="") or value))(deepcopy(session))),
        "two-configuring-parties": lambda: ownership_gate(session_override=(
            lambda value: (value["one_shot_resources"]
                           ["completion_child_product_profile"].update(
                               configuring_parties=2) or value))(deepcopy(session))),
        "closer-skips-owner": lambda: ownership_gate(
            inherited_override=(link95, link94.replace(
                "paths = configure_card()", "paths = completed_paths()", 1))),
        "resume-repeats-qualification": lambda: ownership_gate(
            resume_source=resume.replace(
                "    owner_mutations = ownership_mutations()\n"
                "    before = frozen_inputs()",
                "    owner_mutations = ownership_mutations()\n"
                "    CARD.post_link_replay()\n"
                "    before = frozen_inputs()", 1)),
        "resume-duplicates-completion": lambda: ownership_gate(
            resume_source=resume.replace(
                "    paths = CARD.configure(CARD.REPLAY_PROFILE)\n"
                "    run_completion_child()\n"
                "    after = frozen_inputs()",
                "    paths = CARD.configure(CARD.REPLAY_PROFILE)\n"
                "    run_completion_child()\n"
                "    run_completion_child()\n"
                "    after = frozen_inputs()", 1)),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        try:
            mutate()
        except ResumeError:
            rejected.append(name)
    require(rejected == list(cases), "single-owner mutation survived")
    return rejected


def frozen_stopped_outputs() -> dict[str, Any]:
    first_red = load(RED.RECEIPT)
    rows = first_red["stopped_output"]
    for name, row in rows.items():
        if isinstance(row, dict) and "path" in row:
            require(bind(ROOT / row["path"]) == row,
                    f"r10 stopped output drift: {name}")
    return deepcopy(rows)


def frozen_inputs() -> dict[str, Any]:
    return {
        "stopped_r10": frozen_stopped_outputs(),
        "frozen_Link97": CARD.frozen_red_artifact_preflight(),
        "terminal_guard": bind(CARD.GUARD_RECEIPT),
        "r10_first_red": bind(RED.RECEIPT),
        "three_field_content_map": bind(CONTENT),
    }


def run_completion_child() -> None:
    environment = os.environ.copy()
    environment.update(CARD.L95.CAN.canonical_build_environment())
    environment["LISP65_V150_POSTLINK_REPLAY"] = "1"
    result = subprocess.run(
        [sys.executable, str(Path(R10.__file__).resolve()), "_complete"],
        cwd=ROOT, env=environment, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
    require(result.returncode == 0,
            "v1.5 r10 completion-only resume red:\n" + result.stdout)
    paths = CARD.completed_paths()
    (paths["receipts"] / "artifact-completion.log").write_text(
        result.stdout, encoding="utf-8")


def reconstruct_wplto_authority(paths: dict[str, Path]) -> dict[str, Any]:
    """Project the already-green r10 record; execute no qualification gate."""
    internal = load(R10.R10 / "wplto-internal.json")
    linked = load(R10.R10 / "single-submit-linked-gates.json")
    content = load(CONTENT)
    replacement = internal["fresh_replacement_gates"]
    require(
        internal["status"]
            == "passed-new-c2-lite-real-abi-identity-hardware-not-run"
        and replacement["status"] == "passed"
        and linked["status"]
            == "passed-single-submit-local-observation-and-complete-leaf-ABI"
        and content["decision"]["vocabulary_cases"] == 3
        and content["decision"]["qualification_gaps"] == 0,
        "bound r10 qualification authority is not green")
    raw = load(paths["receipts"] / "wplto-raw.json")
    current = {
        "status": "passed-current-v4-pre-publish-WPLTO-closure",
        "reconstruction": "bound-r10-output-no-qualification-reexecution",
        "authority": bind(RED.RECEIPT),
        "walls": replacement["walls"],
        "capacity": replacement["capacity"],
        "current_successor_identity": {
            "status": "passed-three-current-successor-identities",
            "authority": bind(CONTENT),
            "vocabulary_cases": 3,
            "qualification_gaps": 0,
        },
        "assembler_leaf_ABI": {
            "callsite_count": internal["fresh_real_abi_gate"]["callsite_count"],
            "unclassified_C_called_functions": internal[
                "fresh_real_abi_gate"]["unclassified_C_called_functions"],
        },
        "pre_publish_identity": internal["product_identity"],
        "sealed_role_check": "deferred-to-post-publish-public-clean-build-gate",
    }
    return {
        "status": (
            "passed-one-current-WPLTO-closure-at-repaired-historical-"
            "qualification-boundary"),
        "publish_last_authority":
            f"0x{CARD.L95.CAN.PRODUCT.LINK60_VERIFIER_BINDING_BASE:04x}",
        "historical_checker_boundary": {
            "classification":
                "bound-r10-qualification-reconstruction-no-reexecution",
            "raw_status": raw["status"],
            "raw_error": raw["error"],
            "captured_driver_log": bind(
                paths["receipts"] / "wplto-historical-driver.log"),
            "current_replacement_gates": current,
        },
        "qualification": bind(R10.R10 / "wplto-internal.json"),
        "linked_gate": bind(R10.R10 / "single-submit-linked-gates.json"),
        "resume_authority": bind(RED.RECEIPT),
    }


def resume_value(*, before: dict[str, Any], after: dict[str, Any],
                 owner_gate: dict[str, Any], owner_mutations: list[str],
                 completion: Path, final_prg: Path, final_elf: Path,
                 product_card: Path) -> dict[str, Any]:
    return {
        "format": FORMAT,
        "recorded_on": "2026-08-11",
        "status": STATUS,
        "authorization_commit": AUTHORIZATION,
        "single_owner_gate": owner_gate,
        "single_owner_mutations_rejected": owner_mutations,
        "predecessor_first_red": bind(RED.RECEIPT),
        "immutable_before": before,
        "immutable_after": after,
        "artifact_completion": bind(completion),
        "completed_product": bind(final_prg),
        "completed_ELF": bind(final_elf),
        "product_card": bind(product_card),
        "execution_accounting": {
            "completion_resumes_authorized": 1,
            "completion_resumes_consumed": 1,
            "post_link_qualification_reexecutions": 0,
            "artifact_completions": 1,
            "WPLTO_runs": 0,
            "compiler_runs": 0,
            "linker_runs": 0,
            "media_builds": 0,
            "hardware_runs": 0,
        },
        "next_gate": "construct and close the v1.5 media set, then D1-D5",
        "claim_limit": (
            "Completion and host product closure of the frozen, already "
            "qualified Link-97 r10 outputs. Media, device acceptance, Halt, "
            "release and publication remain unclaimed."),
    }


def validate_resume(value: dict[str, Any]) -> None:
    require(
        value.get("format") == FORMAT and value.get("status") == STATUS
        and value.get("authorization_commit") == AUTHORIZATION
        and value.get("execution_accounting") == {
            "completion_resumes_authorized": 1,
            "completion_resumes_consumed": 1,
            "post_link_qualification_reexecutions": 0,
            "artifact_completions": 1,
            "WPLTO_runs": 0, "compiler_runs": 0, "linker_runs": 0,
            "media_builds": 0, "hardware_runs": 0,
        }
        and value.get("single_owner_gate", {}).get("status")
            == "passed-named-single-owner-one-shot-session-contract",
        "r10 completion resume claim drift")


def selftest() -> int:
    require(
        RED.RECEIPT.is_file() and R10.R10.is_dir()
        and not RESUME_RECEIPT.exists() and not CARD.RECEIPT.exists()
        and not CARD.completed_paths()["final"].exists(),
        "r10 completion resume boundary is not fresh")
    RED.check()
    frozen_inputs()
    gate = ownership_gate()
    rejected = ownership_mutations()
    require(len(rejected) == 7, "single-owner mutation count drift")
    print("v1.5 Link-97 completion resume selftest: PASS owners=2x1 mutations=7")
    return 0


def resume_action() -> int:
    require(
        RED.RECEIPT.is_file() and R10.R10.is_dir()
        and not RESUME_RECEIPT.exists() and not CARD.RECEIPT.exists()
        and not CARD.completed_paths()["final"].exists(),
        "r10 completion resume is one-shot or boundary is not fresh")
    RED.check()
    owner_gate = ownership_gate()
    owner_mutations = ownership_mutations()
    before = frozen_inputs()
    R10.configure_replay()
    paths = CARD.configure(CARD.REPLAY_PROFILE)
    run_completion_child()
    after = frozen_inputs()
    require(after == before, "completion resume changed a frozen r10 input")

    completion_path = paths["receipts"] / "artifact-completion.json"
    completion = load(completion_path)
    final_elf = paths["final"] / "lisp65-c2-substitution-linked.prg.elf"
    final_prg = paths["final"] / "lisp65-c2-substitution-linked.prg"
    guard_before = load(CARD.GUARD_RECEIPT)
    require(
        completion["status"]
            == "passed-no-relink-publish-last-artifact-completion"
        and completion["compiler_runs"] == completion["linker_runs"] == 0
        and CARD.semantic_guard(guard_before) == CARD.semantic_guard(
            CARD.guard_result(final_elf, final_prg)),
        "r10 completion changed identity or terminal-guard semantics")

    authority = reconstruct_wplto_authority(paths)
    manifest = CARD.build_manifest(authority, completion)
    checked = CARD.L95.CAN.check()
    require(checked["identity"] == manifest["identity"],
            "v1.5 completed resume identity red")
    freight = CARD.freight_gates()
    header = CARD.L95.CORE.bind_generated_stdlib_header(paths)
    (paths["receipts"] / "v1.5.0-feature-gates.json").write_bytes(canonical({
        "status": "passed-v1.5.0-frozen-freight-gates",
        "freight": freight, "target_stdlib_header": header,
    }))
    product = CARD.derive(); CARD.validate(product, verify=False)
    product["mutations_rejected"] = CARD.mutations(product)
    CARD.RECEIPT.write_bytes(canonical(product))

    value = resume_value(
        before=before, after=after, owner_gate=owner_gate,
        owner_mutations=owner_mutations, completion=completion_path,
        final_prg=final_prg, final_elf=final_elf, product_card=CARD.RECEIPT)
    validate_resume(value)
    RESUME_RECEIPT.write_bytes(canonical(value))
    print("v1.5 Link-97 r10 completion resume: PASS "
          f"text={product['geometry']['walls']['bank0_text_headroom_bytes']} "
          f"e000={product['geometry']['walls']['e000_headroom_bytes']} "
          "qualification=0 WPLTO=0 compiler=0 linker=0")
    return 0


def check() -> int:
    value = load(RESUME_RECEIPT); validate_resume(value)
    before = value["immutable_before"]
    require(frozen_inputs() == before == value["immutable_after"],
            "r10 resume frozen-input authority drift")
    ownership_gate()
    R10.configure_replay()
    CARD.check()
    print("v1.5 Link-97 completion resume check: PASS")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("selftest", "resume", "check"))
    return {"selftest": selftest, "resume": resume_action,
            "check": check}[parser.parse_args().action]()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ResumeError, CARD.CardError, RED.FirstRedError, OSError,
            ValueError, KeyError, subprocess.CalledProcessError) as error:
        print(f"v1.5 Link-97 completion resume: FIRST RED: {error}")
        raise SystemExit(2)
