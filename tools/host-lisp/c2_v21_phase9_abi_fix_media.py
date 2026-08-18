#!/usr/bin/env python3
"""Complete and close media for the frozen phase-9 ABI candidate.

The frozen WPLTO artifacts have already passed the v5 Golden and the
candidate-derived far-service Acceptance.  This downstream-only adapter keeps
the historical media implementation intact while replacing its last freight
snapshot assumptions with facts read from the emitted candidate ELF.
"""

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
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_v21_dependent_vma_media as PIPE  # noqa: E402
import c2_v21_phase9_abi_fix_artifact_resume as RESUME  # noqa: E402
import c2_v21_phase9_abi_fix_replacement_card as CARD  # noqa: E402
import c2_v21_phase9_candidate_derived_tuple_gate as SIZE  # noqa: E402
import c2_v21_phase9_freight_boundary_golden as GOLD  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.1-cpu-transport-work-plan.md"
CARD_BUILD = CARD.BUILD
BASE_BUILD = ROOT / "build/c2.3/v2.1-phase9-abi-media-base"
LIVE_BUILD = ROOT / "build/c2.3/v2.1-phase9-abi-media-liveness"
FAR_BUILD = ROOT / "build/c2.3/v2.1-phase9-abi-media-r3"
BASE_RECEIPT = ARCH / "c2.3-v2.1-phase9-abi-base-media-receipt.json"
LIVE_RECEIPT = ARCH / "c2.3-v2.1-phase9-abi-liveness-media-receipt.json"
FAR_RECEIPT = ARCH / "c2.3-v2.1-phase9-abi-media-r3-receipt.json"
RECEIPT = ARCH / "c2.3-v2.1-phase9-abi-completion-media-receipt.json"
BASE_SESSION = ROOT / "config/c2-v150-v21-phase9-abi-device-session.json"
LIVE_SESSION = ROOT / "config/c2-v150-v21-phase9-abi-live-device-session.json"
FAR_SESSION = ROOT / "config/c2-v150-v21-phase9-abi-far-r3-device-session.json"
DRIVER = Path(__file__).resolve()
AUTHORIZATION = "ded37acd"
RECORDED_ON = "2026-08-16"
LINK = 110


class MediaError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise MediaError(message)


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
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def authorization() -> dict[str, Any]:
    full = subprocess.run(
        ["git", "rev-parse", f"{AUTHORIZATION}^{{commit}}"], cwd=ROOT,
        check=True, text=True, stdout=subprocess.PIPE).stdout.strip()
    name = PLAN.relative_to(ROOT).as_posix()
    raw = subprocess.run(
        ["git", "show", f"{full}:{name}"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE).stdout
    text = " ".join(raw.decode().lower().split())
    for token in ("size derivation approved", "emitted candidate",
                  "fixed arena capacity",
                  "acceptance continues on the frozen artifacts only"):
        require(token in text, f"media authority absent: {token}")
    return {"authority": "git-blob", "commit": full, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def replay_authority() -> dict[str, Any]:
    value = load(RESUME.RECEIPT)
    acceptance = value.get("acceptance", {})
    golden = acceptance.get("VMA_golden", {})
    far = acceptance.get("far_payload", {})
    oracle = acceptance.get("source_authoritative_oracle", {})
    require(
        value.get("status") == "PASS: frozen phase-9 Acceptance resumed and green"
        and value.get("execution_accounting") == {
            "acceptance_resumes_authorized": 1,
            "acceptance_resumes_run": 1, "WPLTO_runs": 0,
            "product_links": 0, "cards_consumed": 0, "scope_runs": 0,
            "completion_runs": 0, "media_builds": 0, "device_contacts": 0}
        and value.get("frozen_artifacts_before") ==
            value.get("frozen_artifacts_after")
        and golden.get("dependent_fixed_vmas") == 101
        and golden.get("dependent_free_derived_vmas") == 2
        and golden.get("fixed_boundary_symbols") == 25
        and golden.get("freight_derived_boundary_symbols") == 3
        and far.get("candidate_derived_bytes") == 1086
        and far.get("arena_capacity_bytes") == 1499
        and far.get("fixed_size_expectation") is False
        and oracle.get("status") == "passed-linked-delivery-bound-CRC-oracle"
        and len(oracle.get("c2d_crc16", [])) == 6,
        "green phase-9 frozen Acceptance authority absent")
    for name, fact in value["frozen_artifacts_before"].items():
        require(fact == bind(ROOT / fact["path"]),
                f"frozen phase-9 artifact drift: {name}")
    return value


def frozen_artifacts() -> dict[str, dict[str, Any]]:
    return deepcopy(replay_authority()["frozen_artifacts_before"])


def card_projection() -> dict[str, Any]:
    value = replay_authority()
    return {
        "status": "PASS: phase-9 projects frozen Acceptance authority",
        "attempt_accounting": {"cards_authorized": 0, "cards_consumed": 0,
            "device_contacts": 0, "product_link_attempts": 0,
            "wplto_runs": 0, "artifact_replays": 1},
        "acceptance": value["acceptance"],
        "artifacts": value["frozen_artifacts_before"],
        "authority": {"phase9_acceptance": bind(RESUME.RECEIPT)},
    }


def candidate_payload_authority(image: Any) -> list[dict[str, Any]]:
    """Derive the media payload extent from the emitted candidate."""
    section = image.section(SIZE.SECTION)
    start = image.symbol("__lisp65_c2_mapped_far_service_load_start").value
    end = image.symbol("__lisp65_c2_mapped_far_service_load_end").value
    raw = image.section_bytes(SIZE.SECTION)
    require(
        section.address == SIZE.ARENA_START and section.bytes > 0
        and section.bytes == len(raw) == end - start
        and section.address + section.bytes <= SIZE.ARENA_END,
        "candidate-derived far payload escaped emitted extent or fixed arena")
    return [{"name": SIZE.SECTION, "start": start,
             "end_exclusive": end, "bytes": section.bytes,
             "sha256": hashlib.sha256(raw).hexdigest(), "raw": raw,
             "size_source": "emitted-candidate-section-and-symbol-extents",
             "arena_capacity_bytes": SIZE.ARENA_END - SIZE.ARENA_START,
             "candidate_headroom_bytes":
                SIZE.ARENA_END - section.address - section.bytes}]


def candidate_materialized_bytes() -> tuple[bytes, dict[str, Any]]:
    far = PIPE.FLOW.FAR
    _manifest, bank, _elf = far.base_artifacts()
    old = (ROOT / bank["path"]).read_bytes()
    image = far.truth()
    payload = candidate_payload_authority(image)[0]
    destination = far.role_destination()
    offset = payload["start"] - destination
    require(destination <= payload["start"] and len(old) <= offset,
            "candidate payload cannot extend the existing Bank-2 role")
    padding = bytes(offset - len(old))
    result = old + padding + payload["raw"]
    gate = far.extent_identity_gate(image, [(destination, result)])
    require(len(result) == payload["end_exclusive"] - destination,
            "candidate-derived delivered extent is discontinuous")
    return result, {
        "source_bank2": bank, "source_bytes_preserved": len(old),
        "zero_padding_bytes": len(padding),
        "padding_start": f"0x{destination + len(old):08x}",
        "payload_start": f"0x{payload['start']:08x}",
        "payload_bytes": payload["bytes"], "delivered_bytes": len(result),
        "delivered_sha256": hashlib.sha256(result).hexdigest(),
        "size_source": "emitted-candidate-section-and-symbol-extents",
        "fixed_size_expectation": False,
        "arena_capacity_bytes": payload["arena_capacity_bytes"],
        "candidate_headroom_bytes": payload["candidate_headroom_bytes"],
        "gate": gate,
    }


def expected_geometry() -> dict[str, int]:
    far = PIPE.FLOW.FAR
    elf = CARD_BUILD / "final/lisp65-c2-substitution-linked.prg.elf"
    if not elf.is_file():
        elf = CARD_BUILD / "wplto/lisp65-c2-substitution-linked.prg.elf"
    image = far.ElfTruth.read(
        elf, llvm_readobj=far.READOBJ, include_section_data=True)
    payload = candidate_payload_authority(image)[0]
    return {"payload_bytes": payload["bytes"],
            "delivered_bytes":
                payload["end_exclusive"] - PIPE.FLOW.FAR.role_destination(),
            "arena_capacity_bytes": payload["arena_capacity_bytes"],
            "candidate_headroom_bytes": payload["candidate_headroom_bytes"]}


LEGACY_FAR_DERIVE = PIPE.FLOW.FAR.derive
LEGACY_CONFIGURE_FAR = PIPE.FLOW.configure_far


def candidate_far_derive(*, configured: bool = False) -> dict[str, Any]:
    value = LEGACY_FAR_DERIVE(configured=configured)
    geometry = expected_geometry()
    require(value["materialization"]["payload_bytes"] ==
            geometry["payload_bytes"]
            and value["materialization"]["delivered_bytes"] ==
            geometry["delivered_bytes"],
            "media derivation did not consume candidate freight")
    value["candidate_derived_freight"] = {
        **geometry, "fixed_size_expectation": False,
        "authority": bind(SIZE.RECEIPT),
        "frozen_acceptance": bind(RESUME.RECEIPT)}
    value["authority"]["candidate_size_authorization"] = authorization()
    return value


def validate_far_receipt(value: dict[str, Any], *, verify: bool) -> None:
    far = PIPE.FLOW.FAR
    geometry = expected_geometry()
    require(
        value.get("status") == far.STATUS
        and value.get("attempt_accounting") == {
            "additional_product_cards": 0, "additional_WPLTO_runs": 0,
            "additional_product_links": 0, "artifact_completions": 0,
            "shared_system_builds": 1, "cold_stager_compiler_runs": 1,
            "library_builds": 0, "media_readbacks": 1,
            "hardware_runs": 0}
        and value["predecessor_retirement"]["current_authority"] is False
        and value["materialization"]["delivered_bytes"] ==
            geometry["delivered_bytes"]
        and value["materialization"]["payload_bytes"] ==
            geometry["payload_bytes"]
        and value["materialization"]["fixed_size_expectation"] is False
        and value["materialization"]["gate"]["identity_mismatches"] == 0
        and value["candidate_derived_freight"] == {
            **geometry, "fixed_size_expectation": False,
            "authority": bind(SIZE.RECEIPT),
            "frozen_acceptance": bind(RESUME.RECEIPT)}
        and value["packed_artifact_gate_registry"]["complete"] is True
        and value["packed_artifact_gate_registry"]["registered"] ==
            value["packed_artifact_gate_registry"]["executed"]
        and value["shared_system"]["artifact_count"] == 19
        and value["shared_system"]["readback"] == "byteidentical"
        and value["library"]["rebuilt"] is False
        and value["pair_identity"]["result"] == "same-world-pair"
        and all(value["hardware_handoff"]["conditions"].values())
        and value["hardware_handoff"]["D1_repeat_authorized"] is True
        and value["hardware_handoff"]["D2_D5_open"] is False,
        "candidate-derived far media closure claim drift")
    if verify:
        require(value == candidate_far_derive(),
                "candidate-derived far media receipt stale")


def far_receipt_mutations(value: dict[str, Any]) -> list[str]:
    geometry = expected_geometry()
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "claim-link": lambda x: x["attempt_accounting"].update(
            additional_product_links=1),
        "restore-874-pin": lambda x: x["materialization"].update(
            payload_bytes=874, fixed_size_expectation=True),
        "truncate-derived-extent": lambda x: x["materialization"].update(
            delivered_bytes=geometry["delivered_bytes"] - 1),
        "hide-identity-mismatch": lambda x: x["materialization"]["gate"].update(
            identity_mismatches=1),
        "omit-packed-gate": lambda x: x["packed_artifact_gate_registry"].update(
            executed=["autoboot.c65.elf"]),
        "skip-readback": lambda x: x["shared_system"].update(readback="skipped"),
        "cross-world": lambda x: x["pair_identity"].update(result="mismatch"),
        "open-D2-D5": lambda x: x["hardware_handoff"].update(D2_D5_open=True),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        trial = deepcopy(value); mutate(trial)
        try:
            validate_far_receipt(trial, verify=False)
        except MediaError:
            rejected.append(name)
    require(rejected == list(cases), "candidate-derived media mutation survived")
    return rejected


def freight_source_gate(source_override: str | None = None) -> dict[str, Any]:
    source = DRIVER.read_text(encoding="utf-8") if source_override is None else source_override
    tree = ast.parse(source)
    functions = {node.name: node for node in tree.body
                 if isinstance(node, ast.FunctionDef)}
    required = ("candidate_payload_authority", "candidate_materialized_bytes",
                "orchestrate")
    require(all(name in functions for name in required),
            "candidate-derived media lifecycle absent")
    exercised = "\n".join(ast.unparse(functions[name]) for name in required)
    lifecycle = tuple(f"run_child('{name}')" for name in (
        "_base", "_base_check", "_liveness", "_liveness_check",
        "_far", "_far_check"))
    require(
        "section.bytes == len(raw) == end - start" in exercised
        and "section.address + section.bytes <= SIZE.ARENA_END" in exercised
        and "len(result) == payload['end_exclusive'] - destination" in exercised
        and "== 874" not in exercised and "== 48156" not in exercised
        and all(exercised.count(call) == 1 for call in lifecycle),
        "candidate media uses a pinned freight value or incomplete lifecycle")
    return {"status": "passed-candidate-derived-media-freight",
            "payload_source": "emitted-candidate-section-and-symbol-extents",
            "fixed_capacity_bytes": SIZE.ARENA_END - SIZE.ARENA_START,
            "fixed_size_expectations": 0, "fresh_process_stages": 6,
            "additional_WPLTO_runs": 0, "additional_product_links": 0}


def freight_source_mutations() -> list[str]:
    source = DRIVER.read_text(encoding="utf-8")
    cases = {
        "restore-874-payload-pin": source.replace(
            "section.bytes == len(raw) == end - start",
            "section.bytes == len(raw) == end - start == 874", 1),
        "restore-48156-extent-pin": source.replace(
            "len(result) == payload[\"end_exclusive\"] - destination",
            "len(result) == payload[\"end_exclusive\"] - destination == 48156", 1),
        "remove-fixed-arena-wall": source.replace(
            "and section.address + section.bytes <= SIZE.ARENA_END",
            "and section.address + section.bytes > 0", 1),
        "drop-far-stage": source.replace('    run_child("_far")\n', "", 1),
    }
    rejected: list[str] = []
    for name, candidate in cases.items():
        try:
            freight_source_gate(candidate)
        except (MediaError, SyntaxError):
            rejected.append(name)
    require(rejected == list(cases), "candidate media source mutation survived")
    return rejected


def install_candidate_freight() -> None:
    far = PIPE.FLOW.FAR
    far.payload_authority = candidate_payload_authority
    far.materialized_bytes = candidate_materialized_bytes
    far.derive = candidate_far_derive
    far.validate = validate_far_receipt
    far.receipt_mutations = far_receipt_mutations
    far.source_gate = freight_source_gate
    far.source_mutations = freight_source_mutations


def configure_candidate_far() -> None:
    """Apply the legacy path binding, then refresh its captured registry."""
    LEGACY_CONFIGURE_FAR()
    install_candidate_freight()
    far = PIPE.FLOW.FAR
    far.PACKED_ARTIFACTS = {
        "autoboot.c65.elf": far.STAGER_ELF,
        "lisp65-product.d81/CODE.BIN": far.PRODUCT_D81,
    }
    far.PACKED_ARTIFACT_GATES = {
        "autoboot.c65.elf": far.PREVIOUS.LIVE.delivered_liveness_gate,
        "lisp65-product.d81/CODE.BIN": far.packed_far_payload_gate,
    }


def configure() -> None:
    PIPE.CARD_BUILD = CARD_BUILD
    PIPE.BASE_BUILD = BASE_BUILD
    PIPE.LIVE_BUILD = LIVE_BUILD
    PIPE.FAR_BUILD = FAR_BUILD
    PIPE.BASE_RECEIPT = BASE_RECEIPT
    PIPE.LIVE_RECEIPT = LIVE_RECEIPT
    PIPE.FAR_RECEIPT = FAR_RECEIPT
    PIPE.SUMMARY_RECEIPT = RECEIPT
    PIPE.BASE_SESSION = BASE_SESSION
    PIPE.LIVE_SESSION = LIVE_SESSION
    PIPE.FAR_SESSION = FAR_SESSION
    PIPE.DRIVER = DRIVER
    PIPE.RECORDED_ON = RECORDED_ON
    PIPE.LINK = LINK
    PIPE.GOLD = GOLD
    PIPE.CARD.BUILD = CARD_BUILD
    PIPE.CARD.RECEIPT = RESUME.RECEIPT
    PIPE.card_authority = replay_authority
    PIPE.frozen_artifacts = frozen_artifacts
    PIPE.card_projection = card_projection
    PIPE.downstream_source_gate = freight_source_gate
    PIPE.downstream_source_mutations = freight_source_mutations
    PIPE.FLOW.configure_far = configure_candidate_far
    install_candidate_freight()


def run_child(action: str) -> None:
    environment = os.environ.copy()
    environment.update(
        PIPE.FLOW.BASE.PRODUCER.BASE.L95.CAN.canonical_build_environment())
    result = subprocess.run(
        [sys.executable, str(DRIVER), action], cwd=ROOT, env=environment,
        text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        check=False)
    require(result.returncode == 0,
            f"phase-9 completion/media child {action} red:\n{result.stdout}")


def summary_value(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    geometry = expected_geometry()
    far = load(FAR_RECEIPT)
    packed = far.get("packed_artifact_gate_registry", {})
    require(
        far.get("status") == PIPE.FLOW.FAR.STATUS
        and far["materialization"]["payload_bytes"] == geometry["payload_bytes"]
        and far["materialization"]["delivered_bytes"] == geometry["delivered_bytes"]
        and far["materialization"]["fixed_size_expectation"] is False
        and far["materialization"]["gate"]["identity_mismatches"] == 0
        and packed.get("complete") is True
        and packed.get("registered") == packed.get("executed")
        and packed["results"]["autoboot.c65.elf"]["result"] ==
            "passed-actual-linked-stager-prefix"
        and packed["results"]["lisp65-product.d81/CODE.BIN"][
            "identity_mismatches"] == 0
        and far["pair_identity"]["result"] == "same-world-pair"
        and far["hardware_handoff"]["D1_repeat_authorized"] is True
        and far["hardware_handoff"]["D2_D5_open"] is False,
        "phase-9 final media is not D1-ready")
    return {
        "format": "lisp65-c2.3-v2.1-phase9-ABI-completion-media-v1",
        "recorded_on": RECORDED_ON,
        "status": "PASS: phase-9 ABI candidate completed and media closed; D1 ready",
        "authority": {"owner": authorization(),
            "frozen_acceptance": bind(RESUME.RECEIPT),
            "candidate_size_gate": bind(SIZE.RECEIPT),
            "freight_boundary_golden": bind(GOLD.RECEIPT),
            "base_media": bind(BASE_RECEIPT),
            "liveness_media": bind(LIVE_RECEIPT),
            "far_media": bind(FAR_RECEIPT), "driver": bind(DRIVER)},
        "frozen_before": before, "frozen_after": after,
        "acceptance": replay_authority()["acceptance"],
        "completion": bind(CARD_BUILD / "receipts/artifact-completion.json"),
        "final_artifacts": {
            "elf": bind(CARD_BUILD / "final/lisp65-c2-substitution-linked.prg.elf"),
            "prg": bind(CARD_BUILD / "final/lisp65-c2-substitution-linked.prg"),
            "manifest": bind(PIPE.FLOW.BASE.MANIFEST)},
        "media": {
            "product_D81": bind(FAR_BUILD / "shared-system/lisp65-product.d81"),
            "library_D81": bind(BASE_BUILD / "library/lisp65-library.d81"),
            "session": bind(FAR_SESSION), "roles": 19,
            **geometry, "fixed_size_expectation": False,
            "readback": "byteidentical", "same_world": True,
            "packed_gate_registry_complete": True,
            "actual_ELF_liveness": "passed-actual-linked-stager-prefix"},
        "source_gate": freight_source_gate(),
        "source_mutations_rejected": freight_source_mutations(),
        "execution_accounting": {"additional_WPLTO_runs": 0,
            "additional_product_links": 0, "additional_cards": 0,
            "artifact_completions": 1, "shared_media_builds": 3,
            "library_builds": 1, "device_contacts": 0},
        "hardware_handoff": {"D1_ready": True, "D2_D5_open": False,
            "session": bind(FAR_SESSION)},
        "claim_limit": "Host Completion/media only; D1 not run, D2-D5 closed.",
    }


def validate_summary(value: dict[str, Any]) -> None:
    geometry = expected_geometry()
    require(
        value.get("status") ==
            "PASS: phase-9 ABI candidate completed and media closed; D1 ready"
        and value.get("frozen_before") == frozen_artifacts()
        and value.get("frozen_after") == value["frozen_before"]
        and value["media"]["roles"] == 19
        and all(value["media"][key] == expected
                for key, expected in geometry.items())
        and value["media"]["fixed_size_expectation"] is False
        and value["media"]["readback"] == "byteidentical"
        and value["media"]["same_world"] is True
        and value["media"]["packed_gate_registry_complete"] is True
        and value["media"]["actual_ELF_liveness"] ==
            "passed-actual-linked-stager-prefix"
        and value["media"]["session"] == bind(FAR_SESSION)
        and value["execution_accounting"] == {
            "additional_WPLTO_runs": 0, "additional_product_links": 0,
            "additional_cards": 0, "artifact_completions": 1,
            "shared_media_builds": 3, "library_builds": 1,
            "device_contacts": 0}
        and value["hardware_handoff"] == {"D1_ready": True,
            "D2_D5_open": False, "session": bind(FAR_SESSION)},
        "phase-9 completion/media summary drift")


def summary_mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "claim-link": lambda x: x["execution_accounting"].update(
            additional_product_links=1),
        "restore-874-pin": lambda x: x["media"].update(
            payload_bytes=874, fixed_size_expectation=True),
        "truncate-extent": lambda x: x["media"].update(
            delivered_bytes=x["media"]["delivered_bytes"] - 1),
        "cross-world": lambda x: x["media"].update(same_world=False),
        "omit-packed-gate": lambda x: x["media"].update(
            packed_gate_registry_complete=False),
        "open-D2": lambda x: x["hardware_handoff"].update(D2_D5_open=True),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        trial = deepcopy(value); mutate(trial)
        try:
            validate_summary(trial)
        except MediaError:
            rejected.append(name)
    require(rejected == list(cases), "phase-9 summary mutation survived")
    return rejected


def orchestrate() -> int:
    configure()
    base_ready = (BASE_BUILD.is_dir() and BASE_RECEIPT.is_file()
                  and BASE_SESSION.is_file())
    live_ready = (LIVE_BUILD.is_dir() and LIVE_RECEIPT.is_file()
                  and LIVE_SESSION.is_file())
    far_partial = (FAR_BUILD.is_dir() and FAR_SESSION.is_file()
                   and not FAR_RECEIPT.exists())
    require(
        (base_ready == (BASE_BUILD.exists() and BASE_RECEIPT.exists()
                        and BASE_SESSION.exists()))
        and (live_ready == (LIVE_BUILD.exists() and LIVE_RECEIPT.exists()
                            and LIVE_SESSION.exists()))
        and (far_partial or (not FAR_BUILD.exists()
                             and not FAR_RECEIPT.exists()
                             and not FAR_SESSION.exists()))
        and not RECEIPT.exists()
        and ((not (CARD_BUILD / "final").exists()) or
             (CARD_BUILD / "receipts/artifact-completion.json").is_file()),
        "phase-9 completion/media lifecycle is one-shot")
    replay_authority(); freight_source_gate(); freight_source_mutations()
    before = frozen_artifacts()
    if not base_ready:
        run_child("_base")
    else:
        run_child("_rebind_base")
    run_child("_base_check")
    if not live_ready:
        run_child("_liveness")
    else:
        run_child("_rebind_liveness")
    run_child("_liveness_check")
    if far_partial:
        run_child("_finalize_far")
    else:
        run_child("_far")
    run_child("_far_check")
    after = frozen_artifacts()
    require(after == before,
            "phase-9 media path changed a frozen WPLTO artifact")
    value = summary_value(before, after)
    validate_summary(value)
    value["mutations_rejected"] = summary_mutations(value)
    RECEIPT.write_bytes(canonical(value))
    geometry = expected_geometry()
    print("2.1 phase-9 Completion/media: PASS "
          f"payload={geometry['payload_bytes']} "
          f"extent={geometry['delivered_bytes']} D1=ready")
    return 0


def check() -> int:
    configure()
    value = load(RECEIPT)
    rejected = value.pop("mutations_rejected", None)
    validate_summary(value)
    require(rejected == summary_mutations(value),
            "phase-9 summary mutation set drift")
    run_child("_far_check")
    print("2.1 phase-9 Completion/media: CHECK PASS D1=ready D2-D5=closed")
    return 0


def selftest() -> int:
    configure(); replay_authority(); freight_source_gate()
    require(len(freight_source_mutations()) == 4,
            "phase-9 media source mutation count drift")
    geometry = expected_geometry()
    require(geometry == {"payload_bytes": 1086, "delivered_bytes": 48368,
                         "arena_capacity_bytes": 1499,
                         "candidate_headroom_bytes": 413},
            "phase-9 candidate freight preflight drift")
    print("2.1 phase-9 Completion/media: SELFTEST PASS freight=derived")
    return 0


def finalize_far_child() -> int:
    """Finish an already-built r2 medium after an authority-only stop."""
    configure(); PIPE.configure_stages(); PIPE.FLOW.configure_far()
    require(FAR_BUILD.is_dir() and FAR_SESSION.is_file()
            and not FAR_RECEIPT.exists(),
            "partial candidate-derived far medium is not resumable")
    value = candidate_far_derive(configured=True)
    validate_far_receipt(value, verify=False)
    value["mutations_rejected"] = far_receipt_mutations(value)
    FAR_RECEIPT.write_bytes(canonical(value))
    print("2.1 phase-9 far media: PASS authority-resume artifacts-unchanged")
    return 0


def rebind_base_child() -> int:
    configure(); PIPE.configure_stages()
    return PIPE.FLOW.rebind_base_child()


def rebind_liveness_child() -> int:
    configure(); PIPE.configure_stages()
    return PIPE.FLOW.rebind_liveness_child()


def child(action: str) -> int:
    configure()
    return {"_complete": PIPE.complete_child, "_base": PIPE.base_child,
        "_base_check": PIPE.base_check_child,
        "_liveness": PIPE.liveness_child,
        "_liveness_check": PIPE.liveness_check_child,
        "_far": PIPE.far_child, "_far_check": PIPE.far_check_child,
        "_finalize_far": finalize_far_child,
        "_rebind_base": rebind_base_child,
        "_rebind_liveness": rebind_liveness_child}[action]()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("selftest", "build", "check",
        "_complete", "_base", "_base_check", "_liveness",
        "_liveness_check", "_far", "_far_check", "_finalize_far",
        "_rebind_base", "_rebind_liveness"))
    action = parser.parse_args().action
    if action == "build":
        return orchestrate()
    if action == "check":
        return check()
    if action == "selftest":
        return selftest()
    return child(action)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"2.1 phase-9 Completion/media: FIRST RED: {error}",
              file=sys.stderr)
        raise SystemExit(2)
