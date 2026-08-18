#!/usr/bin/env python3
"""Complete and close same-world media for the frozen Link-108 candidate."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_v21_dependent_vma_media as PIPE  # noqa: E402
import c2_v21_product_loading_liveness_card as CARD  # noqa: E402
import c2_v21_product_liveness_artifact_replay as REPLAY  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
CARD_BUILD = CARD.BUILD
BASE_BUILD = ROOT / "build/c2.3/v2.1-product-liveness-media-base"
LIVE_BUILD = ROOT / "build/c2.3/v2.1-product-liveness-media-liveness"
FAR_BUILD = ROOT / "build/c2.3/v2.1-product-liveness-media"
BASE_RECEIPT = ARCH / "c2.3-v2.1-product-liveness-base-media-receipt.json"
LIVE_RECEIPT = ARCH / "c2.3-v2.1-product-liveness-liveness-media-receipt.json"
FAR_RECEIPT = ARCH / "c2.3-v2.1-product-liveness-media-receipt.json"
PIPELINE_RECEIPT = ARCH / (
    "c2.3-v2.1-product-liveness-completion-media-pipeline-receipt.json")
RECEIPT = ARCH / "c2.3-v2.1-product-liveness-completion-media-receipt.json"
BASE_SESSION = ROOT / "config/c2-v150-v21-product-liveness-device-session.json"
LIVE_SESSION = ROOT / (
    "config/c2-v150-v21-product-liveness-live-device-session.json")
FAR_SESSION = ROOT / (
    "config/c2-v150-v21-product-liveness-far-device-session.json")
DRIVER = Path(__file__).resolve()
LINK = 108


class ProductMediaError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ProductMediaError(message)


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


def replay_authority() -> dict[str, Any]:
    value = load(REPLAY.RECEIPT)
    acceptance = value.get("acceptance", {})
    golden = acceptance.get("VMA_golden", {})
    oracle = acceptance.get("source_authoritative_oracle", {})
    require(
        value.get("status") ==
            "PASS: artifact-only producer-tail Scope Acceptance replay"
        and value.get("execution_accounting") == {
            "artifact_replays_authorized": 1, "artifact_replays_run": 1,
            "WPLTO_runs": 0, "product_links": 0, "cards_consumed": 0,
            "completion_runs": 0, "media_builds": 0, "device_contacts": 0}
        and value.get("frozen_artifacts_before") ==
            value.get("frozen_artifacts_after")
        and golden.get("dependent_fixed_vmas") == 101
        and golden.get("dependent_free_derived_vmas") == 2
        and acceptance.get("delivered_bytes", {}).get(
            "identity_mismatches") == 0
        and acceptance.get("far_payload", {}).get("bytes") == 874
        and oracle.get("status") ==
            "passed-linked-delivery-bound-CRC-oracle"
        and oracle.get("records_per_image") == 6
        and len(oracle.get("c2d_crc16", [])) == 6,
        "green Link-108 artifact replay authority absent")
    for name, fact in value["frozen_artifacts_before"].items():
        require(fact == bind(ROOT / fact["path"]),
                f"frozen Link-108 artifact drift: {name}")
    return value


def frozen_artifacts() -> dict[str, dict[str, Any]]:
    return deepcopy(replay_authority()["frozen_artifacts_before"])


def card_projection() -> dict[str, Any]:
    value = replay_authority()
    return {
        "status": "PASS: Link 108 projects artifact-only replay authority",
        "attempt_accounting": {"cards_authorized": 0, "cards_consumed": 0,
            "device_contacts": 0, "product_link_attempts": 0,
            "wplto_runs": 0, "artifact_replays": 1},
        "acceptance": value["acceptance"],
        "artifacts": value["frozen_artifacts_before"],
        "authority": {"Link108_artifact_replay": bind(REPLAY.RECEIPT)},
    }


def downstream_source_gate(source_override: str | None = None) -> dict[str, Any]:
    source = DRIVER.read_text(encoding="utf-8") if source_override is None else source_override
    configure_start = source.index("\ndef configure() -> None:") + 1
    validate_start = source.index("\ndef validate(", configure_start)
    build_start = source.index("\ndef build() -> int:", validate_start) + 1
    check_start = source.index("\ndef check() -> int:", build_start) + 1
    selftest_start = source.index("\ndef selftest() -> int:", check_start)
    configure_source = source[configure_start:validate_start]
    build_source = source[build_start:check_start]
    check_source = source[check_start:selftest_start]
    exercised = configure_source + build_source + check_source
    required = (
        "result = PIPE.orchestrate()",
        "PIPE.check()",
        "PIPE.card_authority = replay_authority",
        "PIPE.frozen_artifacts = frozen_artifacts",
        "PIPE.card_projection = card_projection",
    )
    forbidden = ("CARD.card()", "produce_candidate(", "single_link(",
                 "run_wplto(")
    require(all(token in exercised for token in required)
            and all(token not in exercised for token in forbidden),
            "Link-108 downstream wrapper can re-enter product lifecycle")
    return {"status": "PASS: Link-108 downstream-only adapter",
            "delegated_pipeline": bind(PIPE.DRIVER), "forbidden_calls": 0,
            "additional_WPLTO_runs": 0, "additional_product_links": 0,
            "additional_cards": 0}


def downstream_source_mutations() -> list[str]:
    source = DRIVER.read_text(encoding="utf-8")
    cases = {
        "drop-replay-authority": source.replace(
            "    PIPE.card_authority = replay_authority\n",
            "    PIPE.card_authority = None\n", 1),
        "drop-frozen-binding": source.replace(
            "    PIPE.frozen_artifacts = frozen_artifacts\n",
            "    PIPE.frozen_artifacts = None\n", 1),
        "reenter-card": source.replace(
            "    result = PIPE.orchestrate()\n",
            "    CARD.card()\n    result = PIPE.orchestrate()\n", 1),
    }
    rejected: list[str] = []
    for name, candidate in cases.items():
        try:
            downstream_source_gate(candidate)
        except ProductMediaError:
            rejected.append(name)
    require(rejected == list(cases), "Link-108 adapter mutation survived")
    return rejected


def configure() -> None:
    # The proven Link-107 driver is retained as the six-stage regular media
    # pipeline.  Only candidate authority and output identities are rebound.
    PIPE.CARD_BUILD = CARD_BUILD
    PIPE.BASE_BUILD = BASE_BUILD
    PIPE.LIVE_BUILD = LIVE_BUILD
    PIPE.FAR_BUILD = FAR_BUILD
    PIPE.BASE_RECEIPT = BASE_RECEIPT
    PIPE.LIVE_RECEIPT = LIVE_RECEIPT
    PIPE.FAR_RECEIPT = FAR_RECEIPT
    PIPE.SUMMARY_RECEIPT = PIPELINE_RECEIPT
    PIPE.BASE_SESSION = BASE_SESSION
    PIPE.LIVE_SESSION = LIVE_SESSION
    PIPE.FAR_SESSION = FAR_SESSION
    PIPE.DRIVER = DRIVER
    PIPE.RECORDED_ON = "2026-08-15"
    PIPE.LINK = LINK
    PIPE.CARD.BUILD = CARD_BUILD
    PIPE.CARD.RECEIPT = REPLAY.RECEIPT
    PIPE.card_authority = replay_authority
    PIPE.frozen_artifacts = frozen_artifacts
    PIPE.card_projection = card_projection
    PIPE.downstream_source_gate = downstream_source_gate
    PIPE.downstream_source_mutations = downstream_source_mutations


def validate(value: dict[str, Any]) -> None:
    require(
        value.get("status") ==
            "PASS: Link 108 completed and same-world media closed; D1 ready"
        and value.get("frozen_before") == frozen_artifacts()
        and value.get("frozen_after") == value["frozen_before"]
        and value.get("media", {}).get("roles") == 19
        and value["media"].get("delivered_extent_bytes") == 48156
        and value["media"].get("far_payload_bytes") == 874
        and value["media"].get("same_world") is True
        and value["media"].get("readback") == "byteidentical"
        and value["execution_accounting"] == {
            "artifact_replays": 1, "additional_WPLTO_runs": 0,
            "additional_product_links": 0, "additional_cards": 0,
            "artifact_completions": 1, "shared_media_builds": 3,
            "library_builds": 1, "device_contacts": 0}
        and value["hardware_handoff"] == {
            "D1_ready": True, "D2_D5_open": False,
            "session": bind(FAR_SESSION)},
        "Link-108 completion/media summary drift")


def build() -> int:
    configure()
    require(not RECEIPT.exists(), "Link-108 completion/media is one-shot")
    replay_authority(); downstream_source_gate(); downstream_source_mutations()
    before = frozen_artifacts()
    result = PIPE.orchestrate()
    require(result == 0, "regular completion/media pipeline red")
    after = frozen_artifacts()
    pipeline = load(PIPELINE_RECEIPT)
    far = load(FAR_RECEIPT)
    require(before == after
            and pipeline["media"]["roles"] == 19
            and pipeline["media"]["same_world"] is True
            and pipeline["media"]["readback"] == "byteidentical"
            and far["hardware_handoff"]["D1_repeat_authorized"] is True,
            "regular Link-108 media result red")
    value = {
        "format": "lisp65-c2.3-v2.1-product-liveness-completion-media-v1",
        "recorded_on": "2026-08-15",
        "status": "PASS: Link 108 completed and same-world media closed; D1 ready",
        "authority": {"artifact_replay": bind(REPLAY.RECEIPT),
            "pipeline": bind(PIPELINE_RECEIPT), "driver": bind(DRIVER)},
        "frozen_before": before, "frozen_after": after,
        "completion": pipeline["completion"],
        "media": {**pipeline["media"], "same_world": True,
                  "readback": "byteidentical"},
        "source_gate": downstream_source_gate(),
        "source_mutations_rejected": downstream_source_mutations(),
        "execution_accounting": {"artifact_replays": 1,
            "additional_WPLTO_runs": 0, "additional_product_links": 0,
            "additional_cards": 0, "artifact_completions": 1,
            "shared_media_builds": 3, "library_builds": 1,
            "device_contacts": 0},
        "hardware_handoff": {"D1_ready": True, "D2_D5_open": False,
            "session": bind(FAR_SESSION)},
        "claim_limit": "Host Completion/media only; D1 not run, D2-D5 closed.",
    }
    validate(value)
    RECEIPT.write_bytes(canonical(value))
    print("2.1 Link 108 completion/media: PASS roles=19 D1=ready")
    return 0


def check() -> int:
    configure()
    value = load(RECEIPT)
    validate(value)
    PIPE.check()
    print("2.1 Link 108 completion/media: CHECK PASS D1=ready D2-D5=closed")
    return 0


def selftest() -> int:
    configure(); replay_authority(); downstream_source_gate()
    require(len(downstream_source_mutations()) == 3,
            "Link-108 adapter mutation count drift")
    PIPE.configure_stages(); PIPE.FLOW.configure_base()
    _paths, candidate = PIPE.FLOW.BASE.configure_candidate()
    replay = candidate.REPLAY
    replay.PROFILE.configure()
    replay.BANK2.configure_bank2_stage()
    replay.TWO.configure_two_region()
    replay.LINK60.configure_current_pin_adapters()
    replay.P.configure_intern_session_service()
    PIPE.FLOW.BASE.PRODUCT.configure_full_map_ownership()
    PIPE.FLOW.BASE.PRODUCT.configure_low_resident_lma_reset()
    source = CARD_BUILD / "wplto"
    PIPE.published_binding_gate(
        source, source / "lisp65-c2-substitution-linked.prg",
        source / "runtime-overlays-boot-final.json",
        source / "runtime-overlays-session-final.json",
        expected_base=0xB98C)
    print("2.1 Link 108 completion/media: SELFTEST PASS source=3 "
          "binding=already-published")
    return 0


def child(action: str) -> int:
    configure()
    return {"_complete": PIPE.complete_child, "_base": PIPE.base_child,
        "_base_check": PIPE.base_check_child,
        "_liveness": PIPE.liveness_child,
        "_liveness_check": PIPE.liveness_check_child,
        "_far": PIPE.far_child, "_far_check": PIPE.far_check_child}[action]()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("selftest", "build", "check",
        "_complete", "_base", "_base_check", "_liveness",
        "_liveness_check", "_far", "_far_check"))
    action = parser.parse_args().action
    if action == "build":
        return build()
    if action == "check":
        return check()
    if action == "selftest":
        return selftest()
    return child(action)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"2.1 Link 108 completion/media: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(2)
