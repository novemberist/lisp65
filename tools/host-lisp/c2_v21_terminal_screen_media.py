#!/usr/bin/env python3
"""Complete Link 111 and close its same-world clean-screen media."""

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

import c2_v21_phase9_abi_fix_media as PIPE  # noqa: E402
import c2_v21_terminal_screen_artifact_replay as REPLAY  # noqa: E402
import c2_v21_terminal_screen_lease_card as CARD  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.1-cpu-transport-work-plan.md"
CARD_BUILD = CARD.BUILD
BASE_BUILD = ROOT / "build/c2.3/v2.1-terminal-screen-media-base"
LIVE_BUILD = ROOT / "build/c2.3/v2.1-terminal-screen-media-liveness"
FAR_BUILD = ROOT / "build/c2.3/v2.1-terminal-screen-media"
BASE_RECEIPT = ARCH / "c2.3-v2.1-terminal-screen-base-media-receipt.json"
LIVE_RECEIPT = ARCH / "c2.3-v2.1-terminal-screen-liveness-media-receipt.json"
FAR_RECEIPT = ARCH / "c2.3-v2.1-terminal-screen-far-media-receipt.json"
PIPELINE_RECEIPT = ARCH / (
    "c2.3-v2.1-terminal-screen-completion-media-pipeline-receipt.json")
RECEIPT = ARCH / "c2.3-v2.1-terminal-screen-completion-media-receipt.json"
BASE_SESSION = ROOT / "config/c2-v150-v21-terminal-screen-device-session.json"
LIVE_SESSION = ROOT / (
    "config/c2-v150-v21-terminal-screen-live-device-session.json")
FAR_SESSION = ROOT / (
    "config/c2-v150-v21-terminal-screen-far-device-session.json")
DRIVER = Path(__file__).resolve()
AUTHORIZATION = "9180e59a"
LINK = 111
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
    for token in ("artifact-only qualification replay", "green proceeds to completion",
                  "media", "owner-observed d1", "clean screen"):
        require(token in text, f"terminal-screen media token absent: {token}")
    return {"authority": "git-blob", "commit": full, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def replay_authority() -> dict[str, Any]:
    value = load(REPLAY.RECEIPT)
    acceptance = value.get("acceptance", {})
    golden = acceptance.get("VMA_golden", {})
    far = acceptance.get("far_payload", {})
    oracle = acceptance.get("source_authoritative_oracle", {})
    screen = value.get("producer_tail", {}).get("linked_product", {}).get(
        "terminal_screen_lease", {})
    require(
        value.get("status") ==
            "PASS: Link-111 artifact-only producer-tail Scope Acceptance"
        and value.get("execution_accounting") == {
            "artifact_replays_authorized": 1, "artifact_replays_run": 1,
            "WPLTO_runs": 0, "product_links": 0, "cards_consumed": 0,
            "completion_runs": 0, "media_builds": 0, "device_contacts": 0}
        and value.get("frozen_artifacts_before") ==
            value.get("frozen_artifacts_after")
        and golden.get("dependent_fixed_vmas") == 101
        and golden.get("dependent_free_derived_vmas") == 2
        and far.get("candidate_derived_bytes") == 1086
        and far.get("arena_capacity_bytes") == 1499
        and far.get("fixed_size_expectation") is False
        and oracle.get("status") ==
            "passed-linked-delivery-bound-CRC-oracle"
        and len(oracle.get("c2d_crc16", [])) == 6
        and screen.get("post_phase_visible") is False
        and screen.get("post_phase_screen_code") == "0x20",
        "green Link-111 replay authority absent")
    for name, fact in value["frozen_artifacts_before"].items():
        require(fact == bind(ROOT / fact["path"]),
                f"frozen Link-111 artifact drift: {name}")
    return value


def frozen_artifacts() -> dict[str, dict[str, Any]]:
    return deepcopy(replay_authority()["frozen_artifacts_before"])


def card_projection() -> dict[str, Any]:
    value = replay_authority()
    return {"status": "PASS: Link 111 projects frozen replay authority",
        "attempt_accounting": {"cards_authorized": 0, "cards_consumed": 0,
            "device_contacts": 0, "product_link_attempts": 0,
            "wplto_runs": 0, "artifact_replays": 1},
        "acceptance": value["acceptance"],
        "artifacts": value["frozen_artifacts_before"],
        "authority": {"Link111_artifact_replay": bind(REPLAY.RECEIPT)}}


def source_gate(source_override: str | None = None) -> dict[str, Any]:
    source = DRIVER.read_text(encoding="utf-8") if source_override is None else source_override
    tree = ast.parse(source)
    functions = {node.name: node for node in tree.body
                 if isinstance(node, ast.FunctionDef)}
    require(all(name in functions for name in ("configure", "build", "check")),
            "Link-111 downstream lifecycle functions absent")
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
            "Link-111 downstream adapter can re-enter product lifecycle")
    return {"status": "PASS: Link-111 downstream-only completion/media",
        "additional_WPLTO_runs": 0, "additional_product_links": 0,
        "additional_cards": 0, "forbidden_calls": 0}


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
        except MediaError:
            rejected.append(name)
    require(rejected == list(cases), "Link-111 media mutation survived")
    return rejected


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


def run_child(action: str) -> None:
    environment = os.environ.copy()
    environment.update(
        PIPE.PIPE.FLOW.BASE.PRODUCER.BASE.L95.CAN.canonical_build_environment())
    result = subprocess.run(
        [sys.executable, str(DRIVER), action], cwd=ROOT, env=environment,
        text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        check=False)
    require(result.returncode == 0,
            f"Link-111 completion/media child {action} red:\n{result.stdout}")


def child(action: str) -> int:
    configure()
    return PIPE.child(action)


def validate(value: dict[str, Any]) -> None:
    candidate_manifest = bind(CARD_BUILD / "canonical-product-manifest.json")
    require(
        value.get("status") ==
            "PASS: Link 111 completed and same-world clean-screen media closed"
        and value.get("frozen_before") == frozen_artifacts()
        and value.get("frozen_after") == value["frozen_before"]
        and value.get("media", {}).get("roles") == 19
        and value["media"].get("payload_bytes") == 1086
        and value["media"].get("delivered_bytes") == 48368
        and value["media"].get("same_world") is True
        and value["media"].get("readback") == "byteidentical"
        and value["media"].get("screen_cell_returned") is True
        and value["final_artifacts"].get("manifest") == candidate_manifest
        and value["manifest_projection"] == {
            "status": "PASS: summary follows consumed candidate manifest",
            "candidate": candidate_manifest,
            "historical_global_rejected": True}
        and value["execution_accounting"] == {
            "artifact_replays": 1, "additional_WPLTO_runs": 0,
            "additional_product_links": 0, "additional_cards": 0,
            "artifact_completions": 1, "shared_media_builds": 3,
            "library_builds": 1, "device_contacts": 0}
        and value["hardware_handoff"] == {"D1_ready": True,
            "D2_D5_open": False, "session": bind(FAR_SESSION)},
        "Link-111 completion/media summary drift")


def mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "claim-link": lambda x: x["execution_accounting"].update(
            additional_product_links=1),
        "cross-world": lambda x: x["media"].update(same_world=False),
        "skip-readback": lambda x: x["media"].update(readback="skipped"),
        "restore-stray-zero": lambda x: x["media"].update(
            screen_cell_returned=False),
        "restore-global-manifest": lambda x: x["final_artifacts"].update(
            manifest={"path": "build/c2.3/v2.0-crc-carveout-card/"
                              "canonical-product-manifest.json"}),
        "open-D2": lambda x: x["hardware_handoff"].update(D2_D5_open=True),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        trial = deepcopy(value); mutate(trial)
        try:
            validate(trial)
        except MediaError:
            rejected.append(name)
    require(rejected == list(cases), "Link-111 summary mutation survived")
    return rejected


def summary_value(pipeline: dict[str, Any]) -> dict[str, Any]:
    replay = replay_authority()
    manifest = bind(CARD_BUILD / "canonical-product-manifest.json")
    far = load(FAR_RECEIPT)
    require(far.get("authority", {}).get("frozen_product_manifest") == manifest,
            "media closure did not consume the Link-111 product manifest")
    final_artifacts = deepcopy(pipeline["final_artifacts"])
    final_artifacts["manifest"] = manifest
    return {"format": "lisp65-c2.3-v2.1-terminal-screen-completion-media-v1",
        "recorded_on": RECORDED_ON,
        "status": "PASS: Link 111 completed and same-world clean-screen media closed",
        "authority": {"owner": authorization(),
            "artifact_replay": bind(REPLAY.RECEIPT),
            "pipeline": bind(PIPELINE_RECEIPT), "driver": bind(DRIVER)},
        "frozen_before": pipeline["frozen_before"],
        "frozen_after": pipeline["frozen_after"],
        "completion": pipeline["completion"],
        "final_artifacts": final_artifacts,
        "manifest_projection": {
            "status": "PASS: summary follows consumed candidate manifest",
            "candidate": manifest, "historical_global_rejected": True},
        "media": {**pipeline["media"], "screen_cell_returned":
            replay["producer_tail"]["linked_product"]
                ["terminal_screen_lease"]["post_phase_visible"] is False},
        "source_gate": source_gate(),
        "source_mutations_rejected": source_mutations(),
        "execution_accounting": {"artifact_replays": 1,
            "additional_WPLTO_runs": 0, "additional_product_links": 0,
            "additional_cards": 0, "artifact_completions": 1,
            "shared_media_builds": 3, "library_builds": 1,
            "device_contacts": 0},
        "hardware_handoff": {"D1_ready": True, "D2_D5_open": False,
            "session": bind(FAR_SESSION)},
        "claim_limit": "Host Completion/media only; D1 not run, D2-D5 closed."}


def build() -> int:
    configure(); replay_authority(); source_gate(); source_mutations()
    require(not RECEIPT.exists(), "Link-111 completion/media is one-shot")
    result = PIPE.orchestrate()
    require(result == 0, "Link-111 downstream pipeline returned red")
    pipeline = load(PIPELINE_RECEIPT)
    require(pipeline.get("status") ==
            "PASS: phase-9 ABI candidate completed and media closed; D1 ready",
            "Link-111 rebound completion/media pipeline red")
    value = summary_value(pipeline); validate(value)
    value["mutations_rejected"] = mutations(value)
    RECEIPT.write_bytes(canonical(value))
    print("2.1 terminal screen media: PASS Completion=1 media=19 D1=ready")
    return 0


def check() -> int:
    configure()
    value = load(RECEIPT); rejected = value.pop("mutations_rejected", None)
    validate(value)
    require(rejected == mutations(value), "Link-111 mutation receipt drift")
    run_child("_far_check")
    print("2.1 terminal screen media: CHECK PASS screen=clean D2-D5=closed")
    return 0


def selftest() -> int:
    configure(); replay_authority(); source_gate()
    require(len(source_mutations()) == 4, "Link-111 source mutation drift")
    print("2.1 terminal screen media: SELFTEST PASS downstream-only")
    return 0


def rebind_summary() -> int:
    configure(); replay_authority(); source_gate(); source_mutations()
    pipeline = load(PIPELINE_RECEIPT)
    require(pipeline.get("status") ==
            "PASS: phase-9 ABI candidate completed and media closed; D1 ready",
            "persisted Link-111 pipeline is not green")
    value = summary_value(pipeline); validate(value)
    value["mutations_rejected"] = mutations(value)
    RECEIPT.write_bytes(canonical(value))
    print("2.1 terminal screen media: SUMMARY REBIND candidate-manifest-only")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    child_actions = ("_complete", "_base", "_base_check", "_liveness",
        "_liveness_check", "_far", "_far_check", "_finalize_far",
        "_rebind_base", "_rebind_liveness")
    parser.add_argument("action", choices=("selftest", "build", "check",
                                           "rebind-summary",
                                           *child_actions))
    action = parser.parse_args().action
    if action in child_actions:
        return child(action)
    return {"selftest": selftest, "build": build,
            "check": check, "rebind-summary": rebind_summary}[action]()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"2.1 terminal screen media: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(2)
