#!/usr/bin/env python3
"""Complete Link 112 and close its same-world full-span media."""

from __future__ import annotations

import argparse
import ast
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

import c2_v21_phase9_abi_fix_media as PIPE  # noqa: E402
import c2_v21_full_span_projection_artifact_replay as REPLAY  # noqa: E402
import c2_v21_full_span_convergence_card as CARD  # noqa: E402
import c2_v21_terminal_screen_lease as LEASE  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.1-cpu-transport-work-plan.md"
CARD_BUILD = CARD.BUILD
BASE_BUILD = ROOT / "build/c2.3/v2.1-full-span-media-base"
LIVE_BUILD = ROOT / "build/c2.3/v2.1-full-span-media-liveness"
FAR_BUILD = ROOT / "build/c2.3/v2.1-full-span-media"
BASE_RECEIPT = ARCH / "c2.3-v2.1-full-span-base-media-receipt.json"
LIVE_RECEIPT = ARCH / "c2.3-v2.1-full-span-liveness-media-receipt.json"
FAR_RECEIPT = ARCH / "c2.3-v2.1-full-span-far-media-receipt.json"
PIPELINE_RECEIPT = ARCH / (
    "c2.3-v2.1-full-span-completion-media-pipeline-receipt.json")
RECEIPT = ARCH / "c2.3-v2.1-full-span-completion-media-receipt.json"
FIRST_RED = ARCH / "c2.3-v2.1-full-span-completion-first-red.json"
CLEANUP_RECEIPT = ARCH / (
    "c2.3-v2.1-full-span-partial-completion-cleanup-receipt.json")
RESUME_RED = ARCH / "c2.3-v2.1-full-span-completion-resume-red.json"
BASE_SESSION = ROOT / "config/c2-v150-v21-full-span-device-session.json"
LIVE_SESSION = ROOT / (
    "config/c2-v150-v21-full-span-live-device-session.json")
FAR_SESSION = ROOT / (
    "config/c2-v150-v21-full-span-far-device-session.json")
DRIVER = Path(__file__).resolve()
AUTHORIZATION = "957295ef"
RESUME_AUTHORIZATION = "19131cb5"
LINK = 112
RECORDED_ON = "2026-08-16"
PHASE9_DRIVER = PIPE.DRIVER
ORIGINAL_FREIGHT_SOURCE_GATE = PIPE.freight_source_gate
ORIGINAL_FREIGHT_SOURCE_MUTATIONS = PIPE.freight_source_mutations


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
    name = PLAN.relative_to(ROOT).as_posix()
    full = subprocess.run(
        ["git", "rev-parse", f"{AUTHORIZATION}^{{commit}}"], cwd=ROOT,
        check=True, text=True, stdout=subprocess.PIPE).stdout.strip()
    raw = subprocess.run(
        ["git", "show", f"{full}:{name}"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE).stdout
    text = " ".join(raw.decode().lower().split())
    for token in ("headroom derives from the arena contract",
                  "only the outer qualification tail",
                  "green proceeds to completion, media",
                  "no wplto, link or card"):
        require(token in text, f"full-span media authority absent: {token}")
    return {"authority": "git-blob", "commit": full, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def resume_authorization() -> dict[str, Any]:
    name = PLAN.relative_to(ROOT).as_posix()
    full = subprocess.run(
        ["git", "rev-parse", f"{RESUME_AUTHORIZATION}^{{commit}}"], cwd=ROOT,
        check=True, text=True, stdout=subprocess.PIPE).stdout.strip()
    raw = subprocess.run(
        ["git", "show", f"{full}:{name}"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE).stdout
    text = " ".join(raw.decode().lower().split())
    for token in ("read-only from the frozen elf",
                  "completion is a reader, never a configurator",
                  "discarded in a controlled, logged way",
                  "completion repeats exactly once",
                  "no wplto", "no relink", "no card"):
        require(token in text, f"Completion-resume authority absent: {token}")
    return {"authority": "git-blob", "commit": full, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def read_only_screen_identity() -> dict[str, Any]:
    elf = CARD_BUILD / "wplto/lisp65-c2-substitution-linked.prg.elf"
    truth = ElfTruth.read(
        elf, llvm_readobj=ROOT / "tools/llvm-mos/bin/llvm-readobj",
        include_section_data=True)
    reader = truth.symbol("c2_map_cpu_read")
    section = truth.section(reader.section)
    body = truth.section_bytes(section.name)[
        reader.value - section.address:
        reader.value - section.address + reader.bytes]
    progress = body[12:34]
    require(reader.bytes == 189 and progress == LEASE.EXPECTED_LINKED_PROGRESS,
            "frozen ELF lacks the clean terminal-screen handoff")
    return {"status": "PASS: clean-screen identity read from frozen ELF",
        "authority": bind(elf), "reader": reader.name,
        "reader_VMA": f"0x{reader.value:04x}", "reader_bytes": reader.bytes,
        "progress_bytes": progress.hex(), "post_phase_screen_code": "0x20",
        "post_phase_visible": False, "configuration_calls": 0}


def replay_authority() -> dict[str, Any]:
    value = load(REPLAY.RECEIPT)
    acceptance = value.get("persisted_acceptance", {})
    golden = acceptance.get("VMA_golden", {})
    far = acceptance.get("far_payload", {})
    oracle = acceptance.get("source_authoritative_oracle", {})
    accounting = value.get("execution_accounting", {})
    screen = read_only_screen_identity()
    require(
        value.get("status") ==
            "PASS: Link-112 candidate-derived freight tail qualified"
        and accounting.get("WPLTO_runs") == 0
        and accounting.get("product_links") == 0
        and accounting.get("cards_consumed") == 0
        and accounting.get("completion_runs") == 0
        and accounting.get("media_builds") == 0
        and accounting.get("device_contacts") == 0
        and accounting.get("scope_repeated_in_tail") == 0
        and accounting.get("acceptance_repeated_in_tail") == 0
        and value.get("frozen_artifacts_before") ==
            value.get("frozen_artifacts_after")
        and golden.get("dependent_fixed_vmas") == 101
        and golden.get("dependent_free_derived_vmas") == 2
        and far.get("candidate_derived_bytes") == 1248
        and far.get("arena_capacity_bytes") == 1499
        and far.get("candidate_headroom_bytes") == 251
        and far.get("fixed_size_expectation") is False
        and oracle.get("status") == "passed-linked-delivery-bound-CRC-oracle"
        and len(oracle.get("c2d_crc16", [])) == 6
        and screen.get("post_phase_visible") is False
        and screen.get("post_phase_screen_code") == "0x20",
        "green Link-112 qualification-tail authority absent")
    for name, fact in value["frozen_artifacts_before"].items():
        require(fact == bind(ROOT / fact["path"]),
                f"frozen Link-112 artifact drift: {name}")
    result = deepcopy(value)
    result["acceptance"] = acceptance
    result["terminal_screen_lease"] = screen
    return result


def completion_reader_source_gate(
        source_override: str | None = None) -> dict[str, Any]:
    source = DRIVER.read_text(encoding="utf-8") if source_override is None else source_override
    tree = ast.parse(source)
    functions = {node.name: ast.unparse(node) for node in tree.body
                 if isinstance(node, ast.FunctionDef)}
    reader = functions.get("read_only_screen_identity", "")
    authority = functions.get("replay_authority", "")
    combined = reader + "\n" + authority
    forbidden = ("REPLAY.configure()", "CARD.configure()",
                 "CARD.linked_product()", "configure_full_span_source()")
    require(
        "ElfTruth.read" in reader
        and "truth.symbol('c2_map_cpu_read')" in reader
        and "read_only_screen_identity()" in authority
        and all(token not in combined for token in forbidden),
        "Completion authority reconstruction configures shared state")
    return {"status": "PASS: Completion authority is read-only",
        "frozen_ELF_reads": 1, "configuration_calls": 0,
        "forbidden_calls": list(forbidden)}


def completion_reader_mutations() -> list[str]:
    source = DRIVER.read_text(encoding="utf-8")
    cases = {
        "configure-before-read": source.replace(
            "    screen = read_only_screen_identity()\n",
            "    REPLAY.configure()\n"
            "    screen = read_only_screen_identity()\n", 1),
        "reconstruct-through-card": source.replace(
            "    screen = read_only_screen_identity()\n",
            "    CARD.linked_product()\n"
            "    screen = read_only_screen_identity()\n", 1),
    }
    rejected: list[str] = []
    for name, candidate in cases.items():
        try:
            completion_reader_source_gate(candidate)
        except (MediaError, SyntaxError):
            rejected.append(name)
    require(rejected == list(cases),
            "state-mutating Completion authority mutation survived")
    return rejected


def frozen_artifacts() -> dict[str, dict[str, Any]]:
    return deepcopy(replay_authority()["frozen_artifacts_before"])


def card_projection() -> dict[str, Any]:
    value = replay_authority()
    return {"status": "PASS: Link 112 projects frozen tail authority",
        "attempt_accounting": {"cards_authorized": 0, "cards_consumed": 0,
            "device_contacts": 0, "product_link_attempts": 0,
            "wplto_runs": 0, "artifact_replays": 1},
        "acceptance": value["acceptance"],
        "artifacts": value["frozen_artifacts_before"],
        "authority": {"Link112_qualification_tail": bind(REPLAY.RECEIPT)}}


def source_gate(source_override: str | None = None) -> dict[str, Any]:
    source = DRIVER.read_text(encoding="utf-8") if source_override is None else source_override
    tree = ast.parse(source)
    functions = {node.name: node for node in tree.body
                 if isinstance(node, ast.FunctionDef)}
    require(all(name in functions for name in ("configure", "build", "check")),
            "Link-112 downstream lifecycle functions absent")
    exercised = "\n".join(ast.unparse(functions[name])
                           for name in ("configure", "build", "check"))
    required = ("PIPE.orchestrate()", "run_child('_far_check')",
                "PIPE.replay_authority = replay_authority",
                "PIPE.frozen_artifacts = frozen_artifacts",
                "PIPE.card_projection = card_projection")
    forbidden = ("CARD.card()", "produce_candidate(", "single_link(",
                 "run_wplto(")
    require(all(token in exercised for token in required)
            and all(token not in exercised for token in forbidden),
            "Link-112 downstream adapter can re-enter product lifecycle")
    completion_reader_source_gate(source_override)
    return {"status": "PASS: Link-112 downstream-only completion/media",
        "additional_WPLTO_runs": 0, "additional_product_links": 0,
        "additional_cards": 0, "forbidden_calls": 0,
        "completion_authority_configuration_calls": 0}


def source_mutations() -> list[str]:
    source = DRIVER.read_text(encoding="utf-8")
    cases = {
        "drop-replay-authority": source.replace(
            "    PIPE.replay_authority = replay_authority\n", "", 1),
        "drop-frozen-binding": source.replace(
            "    PIPE.frozen_artifacts = frozen_artifacts\n", "", 1),
        "reenter-card": source.replace(
            "    result = PIPE.orchestrate()\n",
            "    CARD.card()\n    result = PIPE.orchestrate()\n", 1),
        "reenter-link": source.replace(
            "    result = PIPE.orchestrate()\n",
            "    single_link()\n    result = PIPE.orchestrate()\n", 1),
    }
    rejected: list[str] = []
    for name, candidate in cases.items():
        try:
            source_gate(candidate)
        except (MediaError, SyntaxError):
            rejected.append(name)
    require(rejected == list(cases), "Link-112 media mutation survived")
    return rejected


def inherited_freight_source_gate(
        source_override: str | None = None) -> dict[str, Any]:
    source = (PHASE9_DRIVER.read_text(encoding="utf-8")
              if source_override is None else source_override)
    return ORIGINAL_FREIGHT_SOURCE_GATE(source)


def inherited_freight_source_mutations() -> list[str]:
    current = PIPE.DRIVER
    PIPE.DRIVER = PHASE9_DRIVER
    try:
        return ORIGINAL_FREIGHT_SOURCE_MUTATIONS()
    finally:
        PIPE.DRIVER = current


def configure() -> None:
    PIPE.CARD_BUILD = CARD_BUILD
    PIPE.BASE_BUILD = BASE_BUILD
    PIPE.LIVE_BUILD = LIVE_BUILD
    PIPE.FAR_BUILD = FAR_BUILD
    PIPE.BASE_RECEIPT = BASE_RECEIPT
    PIPE.LIVE_RECEIPT = LIVE_RECEIPT
    PIPE.FAR_RECEIPT = FAR_RECEIPT
    PIPE.RECEIPT = PIPELINE_RECEIPT
    PIPE.BASE_SESSION = BASE_SESSION
    PIPE.LIVE_SESSION = LIVE_SESSION
    PIPE.FAR_SESSION = FAR_SESSION
    PIPE.RECORDED_ON = RECORDED_ON
    PIPE.LINK = LINK
    PIPE.DRIVER = DRIVER
    PIPE.RESUME.RECEIPT = REPLAY.RECEIPT
    PIPE.replay_authority = replay_authority
    PIPE.frozen_artifacts = frozen_artifacts
    PIPE.card_projection = card_projection
    PIPE.authorization = authorization
    PIPE.run_child = run_child
    PIPE.freight_source_gate = inherited_freight_source_gate
    PIPE.freight_source_mutations = inherited_freight_source_mutations


def run_child(action: str) -> None:
    environment = os.environ.copy()
    environment.update(
        PIPE.PIPE.FLOW.BASE.PRODUCER.BASE.L95.CAN.canonical_build_environment())
    result = subprocess.run(
        [sys.executable, str(DRIVER), action], cwd=ROOT, env=environment,
        text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        check=False)
    require(result.returncode == 0,
            f"Link-112 completion/media child {action} red:\n{result.stdout}")


def child(action: str) -> int:
    configure()
    return PIPE.child(action)


def expected_geometry() -> dict[str, int]:
    configure()
    value = PIPE.expected_geometry()
    acceptance = replay_authority()["acceptance"]["far_payload"]
    require(
        value == {"payload_bytes": acceptance["candidate_derived_bytes"],
            "delivered_bytes": int(acceptance["LMA_end_exclusive"], 0)
                - PIPE.PIPE.FLOW.FAR.role_destination(),
            "arena_capacity_bytes": acceptance["arena_capacity_bytes"],
            "candidate_headroom_bytes": acceptance["candidate_headroom_bytes"]},
        "Link-112 media geometry differs from persisted Acceptance")
    return value


def validate(value: dict[str, Any]) -> None:
    geometry = expected_geometry()
    manifest = bind(CARD_BUILD / "canonical-product-manifest.json")
    require(
        value.get("status") ==
            "PASS: Link 112 completed and same-world full-span media closed"
        and value.get("frozen_before") == frozen_artifacts()
        and value.get("frozen_after") == value["frozen_before"]
        and value.get("media", {}).get("roles") == 19
        and all(value["media"].get(key) == expected
                for key, expected in geometry.items())
        and value["media"].get("same_world") is True
        and value["media"].get("readback") == "byteidentical"
        and value["media"].get("screen_cell_returned") is True
        and value["final_artifacts"].get("manifest") == manifest
        and value["manifest_projection"] == {
            "status": "PASS: summary follows consumed candidate manifest",
            "candidate": manifest, "historical_global_rejected": True}
        and value["execution_accounting"] == {
            "artifact_replays": 1, "additional_WPLTO_runs": 0,
            "additional_product_links": 0, "additional_cards": 0,
            "artifact_completions": 1, "shared_media_builds": 3,
            "library_builds": 1, "completion_retries_authorized": 1,
            "completion_retries_run": 1, "device_contacts": 0}
        and value["hardware_handoff"] == {"D2_resume_ready": True,
            "D3_D5_open": False, "session": bind(FAR_SESSION)},
        "Link-112 completion/media summary drift")


def mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "claim-link": lambda x: x["execution_accounting"].update(
            additional_product_links=1),
        "truncate-extent": lambda x: x["media"].update(
            delivered_bytes=x["media"]["delivered_bytes"] - 1),
        "cross-world": lambda x: x["media"].update(same_world=False),
        "skip-readback": lambda x: x["media"].update(readback="skipped"),
        "restore-stray-zero": lambda x: x["media"].update(
            screen_cell_returned=False),
        "open-D3": lambda x: x["hardware_handoff"].update(D3_D5_open=True),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        trial = deepcopy(value); mutate(trial)
        try:
            validate(trial)
        except MediaError:
            rejected.append(name)
    require(rejected == list(cases), "Link-112 summary mutation survived")
    return rejected


def summary_value(pipeline: dict[str, Any]) -> dict[str, Any]:
    replay = replay_authority()
    manifest = bind(CARD_BUILD / "canonical-product-manifest.json")
    far = load(FAR_RECEIPT)
    require(far.get("authority", {}).get("frozen_product_manifest") == manifest,
            "media closure did not consume the Link-112 product manifest")
    final_artifacts = deepcopy(pipeline["final_artifacts"])
    final_artifacts["manifest"] = manifest
    return {"format": "lisp65-c2.3-v2.1-full-span-completion-media-v1",
        "recorded_on": RECORDED_ON,
        "status": "PASS: Link 112 completed and same-world full-span media closed",
        "authority": {"owner": authorization(),
            "completion_resume_owner": resume_authorization(),
            "qualification_tail": bind(REPLAY.RECEIPT),
            "Completion_First_Red": bind(FIRST_RED),
            "partial_cleanup": bind(CLEANUP_RECEIPT),
            "pipeline": bind(PIPELINE_RECEIPT), "driver": bind(DRIVER)},
        "frozen_before": pipeline["frozen_before"],
        "frozen_after": pipeline["frozen_after"],
        "completion": pipeline["completion"],
        "final_artifacts": final_artifacts,
        "manifest_projection": {
            "status": "PASS: summary follows consumed candidate manifest",
            "candidate": manifest, "historical_global_rejected": True},
        "media": {**pipeline["media"], "screen_cell_returned":
            replay["terminal_screen_lease"]["post_phase_visible"] is False},
        "source_gate": source_gate(),
        "source_mutations_rejected": source_mutations(),
        "completion_reader_gate": completion_reader_source_gate(),
        "completion_reader_mutations_rejected": completion_reader_mutations(),
        "execution_accounting": {"artifact_replays": 1,
            "additional_WPLTO_runs": 0, "additional_product_links": 0,
            "additional_cards": 0, "artifact_completions": 1,
            "shared_media_builds": 3, "library_builds": 1,
            "completion_retries_authorized": 1,
            "completion_retries_run": 1,
            "device_contacts": 0},
        "hardware_handoff": {"D2_resume_ready": True,
            "D3_D5_open": False, "session": bind(FAR_SESSION)},
        "claim_limit": "Host Completion/media only; D2 resume not run; D3-D5 closed."}


def partial_inventory() -> list[dict[str, Any]]:
    final = CARD_BUILD / "final"
    source_gate_receipt = CARD_BUILD / "receipts/write-completion-source-gate.json"
    require(final.is_dir() and source_gate_receipt.is_file(),
            "authorized partial Completion outputs are absent")
    rows = [bind(path) for path in sorted(final.rglob("*"))
            if path.is_file() and not path.is_symlink()]
    rows.append(bind(source_gate_receipt))
    require(rows and not (CARD_BUILD / "receipts/artifact-completion.json").exists()
            and not (CARD_BUILD / "canonical-product-manifest.json").exists(),
            "partial Completion crossed its authorized cleanup boundary")
    return rows


def cleanup_partial_completion() -> dict[str, Any]:
    final = CARD_BUILD / "final"
    source_gate_receipt = CARD_BUILD / "receipts/write-completion-source-gate.json"
    if CLEANUP_RECEIPT.exists():
        value = load(CLEANUP_RECEIPT)
        require(value.get("status") ==
                "PASS: partial Link-112 Completion outputs discarded"
                and not final.exists() and not source_gate_receipt.exists(),
                "partial Completion cleanup receipt is not resumable")
        return value
    red = load(FIRST_RED)
    require(red.get("status") ==
            "FIRST RED: Link-112 Completion returns to owner"
            and red.get("retry_authorized") is False,
            "Completion cleanup lacks its First Red")
    before = frozen_artifacts()
    inventory = partial_inventory()
    armed = {"format": "lisp65-c2.3-v2.1-partial-completion-cleanup-v1",
        "recorded_on": RECORDED_ON,
        "status": "ARMED: partial Link-112 Completion cleanup",
        "authority": {"owner": resume_authorization(),
            "Completion_First_Red": bind(FIRST_RED), "driver": bind(DRIVER)},
        "discard_set": inventory, "discarded_files": 0,
        "frozen_artifacts_before": before,
        "frozen_artifacts_after": before,
        "WPLTO_runs": 0, "product_links": 0, "cards_consumed": 0}
    CLEANUP_RECEIPT.write_bytes(canonical(armed))
    shutil.rmtree(final)
    source_gate_receipt.unlink()
    require(not final.exists() and not source_gate_receipt.exists(),
            "partial Completion cleanup did not finish")
    after = frozen_artifacts()
    require(after == before, "partial cleanup changed frozen Link-112 bytes")
    armed.update(status="PASS: partial Link-112 Completion outputs discarded",
                 discarded_files=len(inventory),
                 frozen_artifacts_after=after)
    CLEANUP_RECEIPT.write_bytes(canonical(armed))
    return armed


def build() -> int:
    configure(); replay_authority(); source_gate(); source_mutations()
    require(not RECEIPT.exists(), "Link-112 completion/media is one-shot")
    result = PIPE.orchestrate()
    require(result == 0, "Link-112 downstream pipeline returned red")
    pipeline = load(PIPELINE_RECEIPT)
    require(pipeline.get("status") ==
            "PASS: phase-9 ABI candidate completed and media closed; D1 ready",
            "Link-112 rebound completion/media pipeline red")
    value = summary_value(pipeline); validate(value)
    value["mutations_rejected"] = mutations(value)
    RECEIPT.write_bytes(canonical(value))
    geometry = expected_geometry()
    print("2.1 full-span media: PASS Completion=1 media=19 "
          f"payload={geometry['payload_bytes']} "
          f"extent={geometry['delivered_bytes']} D2=ready")
    return 0


def resume() -> int:
    resume_authorization(); completion_reader_source_gate()
    completion_reader_mutations()
    require(FIRST_RED.exists() and not RECEIPT.exists()
            and not RESUME_RED.exists(),
            "Link-112 Completion resume boundary drift")
    cleanup = cleanup_partial_completion()
    require(cleanup.get("discarded_files", 0) > 0,
            "Link-112 partial Completion cleanup is empty")
    return build()


def check() -> int:
    configure()
    if RESUME_RED.exists() and not RECEIPT.exists():
        value = load(RESUME_RED)
        require(value.get("status") ==
                "RESUME RED: Link-112 Completion/media returns to owner"
                and value.get("retry_authorized") is False
                and value.get("owner_disposition_required") is True
                and value.get("frozen_artifacts_before") == frozen_artifacts()
                and value.get("frozen_artifacts_after") == frozen_artifacts(),
                "Link-112 Completion resume Red drift")
        print("2.1 full-span media: CHECK RESUME RED")
        return 0
    if FIRST_RED.exists() and not RECEIPT.exists():
        value = load(FIRST_RED)
        require(
            value.get("status") ==
                "FIRST RED: Link-112 Completion returns to owner"
            and value.get("retry_authorized") is False
            and value.get("owner_disposition_required") is True
            and value.get("frozen_artifacts_before") == frozen_artifacts()
            and value.get("frozen_artifacts_after") == frozen_artifacts()
            and value.get("execution_accounting", {}).get(
                "completion_attempts") == 1
            and value.get("execution_accounting", {}).get("media_builds") == 0,
            "Link-112 Completion First Red drift")
        print("2.1 full-span media: CHECK FIRST RED Completion=0 media=0")
        return 0
    value = load(RECEIPT); rejected = value.pop("mutations_rejected", None)
    validate(value)
    require(rejected == mutations(value), "Link-112 mutation receipt drift")
    run_child("_far_check")
    print("2.1 full-span media: CHECK PASS same-world D2=ready D3-D5=closed")
    return 0


def record_first_red(error: Exception) -> None:
    if FIRST_RED.exists() or RECEIPT.exists():
        return
    frozen = frozen_artifacts()
    wplto = CARD_BUILD / "wplto"
    final = CARD_BUILD / "final"
    linked = "lisp65-c2-substitution-linked.prg"
    elf = linked + ".elf"
    require(final.is_dir() and (final / linked).is_file()
            and (final / elf).is_file(),
            "Completion First Red did not preserve its copied artifacts")
    require(bind(wplto / linked) == {
                **bind(final / linked),
                "path": (wplto / linked).relative_to(ROOT).as_posix()}
            and bind(wplto / elf) == {
                **bind(final / elf),
                "path": (wplto / elf).relative_to(ROOT).as_posix()},
            "partial Completion copy differs from frozen Link-112 artifacts")
    value = {
        "format": "lisp65-c2.3-v2.1-full-span-completion-red-v1",
        "recorded_on": RECORDED_ON,
        "status": "FIRST RED: Link-112 Completion returns to owner",
        "error": {"type": type(error).__name__, "message": str(error)},
        "attribution": {
            "class": "COMPLETION-CONSUMER-DISPLACED-BY-AUTHORITY-RECONSTRUCTION",
            "candidate_state": "verifier-binding-already-published",
            "published_binding": bind(wplto / "runtime-verifier-publish-last.json"),
            "intended_consumer":
                "c2_v21_dependent_vma_media.published_binding_gate",
            "displacing_call":
                "replay_authority -> REPLAY.configure -> CARD.linked_product",
            "displacing_owner":
                "c2_v21_text_recovery_replacement_card.candidate_patch",
            "mechanism": (
                "authority reconstruction mutates the shared completion "
                "dispatch after the outer closer installed its read-only "
                "already-published consumer"),
            "narrow_repair": (
                "derive the clean-screen fact directly from the frozen ELF; "
                "authority reconstruction must not configure shared product "
                "state during Completion")},
        "partial_completion": {
            "final_directory_exists": True,
            "linked_PRG_byteidentical_to_wplto": True,
            "linked_ELF_byteidentical_to_wplto": True,
            "artifact_completion_receipt_exists": (
                CARD_BUILD / "receipts/artifact-completion.json").exists(),
            "candidate_manifest_exists": (
                CARD_BUILD / "canonical-product-manifest.json").exists()},
        "execution_accounting": {"artifact_replays": 1,
            "additional_WPLTO_runs": 0, "additional_product_links": 0,
            "additional_cards": 0, "completion_attempts": 1,
            "completion_green": False, "media_builds": 0,
            "device_contacts": 0},
        "frozen_artifacts_before": frozen,
        "frozen_artifacts_after": frozen,
        "retry_authorized": False,
        "owner_disposition_required": True,
        "authority": {"owner": authorization(),
            "qualification_tail": bind(REPLAY.RECEIPT),
            "driver": bind(DRIVER)},
        "claim_limit": (
            "Completion stopped before its receipt; no media or device. "
            "The frozen WPLTO/link artifacts remain unchanged; cleanup and "
            "one Completion retry require owner authorization."),
    }
    FIRST_RED.write_bytes(canonical(value))


def selftest() -> int:
    configure(); replay_authority(); source_gate()
    require(len(source_mutations()) == 4,
            "Link-112 source mutation drift")
    require(completion_reader_source_gate()["configuration_calls"] == 0
            and len(completion_reader_mutations()) == 2,
            "Link-112 Completion reader mutation drift")
    geometry = expected_geometry()
    require(geometry["payload_bytes"] + geometry["candidate_headroom_bytes"]
            == geometry["arena_capacity_bytes"],
            "Link-112 candidate freight arithmetic drift")
    print("2.1 full-span media: SELFTEST PASS freight=candidate-derived")
    return 0


def record_resume_red(error: Exception) -> None:
    if RESUME_RED.exists() or RECEIPT.exists() or not CLEANUP_RECEIPT.exists():
        return
    frozen = frozen_artifacts()
    RESUME_RED.write_bytes(canonical({
        "format": "lisp65-c2.3-v2.1-full-span-completion-resume-red-v1",
        "recorded_on": RECORDED_ON,
        "status": "RESUME RED: Link-112 Completion/media returns to owner",
        "error": {"type": type(error).__name__, "message": str(error)},
        "execution_accounting": {"completion_retries_authorized": 1,
            "completion_retries_run": 1, "additional_WPLTO_runs": 0,
            "additional_product_links": 0, "additional_cards": 0,
            "device_contacts": 0},
        "frozen_artifacts_before": frozen,
        "frozen_artifacts_after": frozen,
        "retry_authorized": False, "owner_disposition_required": True,
        "authority": {"owner": resume_authorization(),
            "Completion_First_Red": bind(FIRST_RED),
            "partial_cleanup": bind(CLEANUP_RECEIPT), "driver": bind(DRIVER)},
        "claim_limit": "The sole authorized Completion repeat stopped; no device contact."}))


def main() -> int:
    child_actions = ("_complete", "_base", "_base_check", "_liveness",
        "_liveness_check", "_far", "_far_check", "_finalize_far",
        "_rebind_base", "_rebind_liveness")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("selftest", "build", "resume", "check",
                                           *child_actions))
    action = parser.parse_args().action
    if action in child_actions:
        return child(action)
    return {"selftest": selftest, "build": build, "resume": resume,
            "check": check}[action]()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        if len(sys.argv) > 1 and sys.argv[1] == "build":
            try:
                record_first_red(error)
            except Exception as receipt_error:
                print(f"2.1 full-span media receipt failure: {receipt_error}",
                      file=sys.stderr)
        if len(sys.argv) > 1 and sys.argv[1] == "resume":
            try:
                record_resume_red(error)
            except Exception as receipt_error:
                print(f"2.1 full-span media resume receipt failure: {receipt_error}",
                      file=sys.stderr)
        print(f"2.1 full-span media: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(2)
