#!/usr/bin/env python3
"""Complete Link 109 and close same-world media after the MAP-mask card."""

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
import c2_v21_map_mask_fix_card as CARD  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
CARD_BUILD = CARD.BUILD
BASE_BUILD = ROOT / "build/c2.3/v2.1-map-mask-media-base"
LIVE_BUILD = ROOT / "build/c2.3/v2.1-map-mask-media-liveness"
FAR_BUILD = ROOT / "build/c2.3/v2.1-map-mask-media"
BASE_RECEIPT = ARCH / "c2.3-v2.1-map-mask-base-media-receipt.json"
LIVE_RECEIPT = ARCH / "c2.3-v2.1-map-mask-liveness-media-receipt.json"
FAR_RECEIPT = ARCH / "c2.3-v2.1-map-mask-media-receipt.json"
PIPELINE_RECEIPT = ARCH / "c2.3-v2.1-map-mask-completion-media-pipeline-receipt.json"
RECEIPT = ARCH / "c2.3-v2.1-map-mask-completion-media-receipt.json"
BASE_SESSION = ROOT / "config/c2-v150-v21-map-mask-device-session.json"
LIVE_SESSION = ROOT / "config/c2-v150-v21-map-mask-live-device-session.json"
FAR_SESSION = ROOT / "config/c2-v150-v21-map-mask-far-device-session.json"
ACCEPTANCE = CARD.ACCEPTANCE_RESULT
DRIVER = Path(__file__).resolve()
LINK = 109


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


def card_authority() -> dict[str, Any]:
    value = load(CARD.RECEIPT); acceptance = load(ACCEPTANCE)
    golden = acceptance.get("VMA_golden", {})
    oracle = acceptance.get("source_authoritative_oracle", {})
    require(
        value.get("status") == "PASS: sole MAP-mask fix card green"
        and value.get("attempt_accounting") == {
            "cards_authorized": 1, "cards_consumed": 1, "WPLTO_runs": 1,
            "product_links": 1, "completion_runs": 0, "media_builds": 0,
            "device_contacts": 0}
        and value.get("artifacts_before") == value.get("artifacts_after")
        and value.get("linked_product", {}).get("tuple_gate", {}).get(
            "positive", {}).get("MAPL") == "0x4fc0"
        and value.get("linked_product", {}).get("free_bytes") == 1
        and acceptance.get("status") == "PASS"
        and golden.get("dependent_fixed_vmas") == 101
        and golden.get("dependent_free_derived_vmas") == 2
        and acceptance.get("delivered_bytes", {}).get("identity_mismatches") == 0
        and acceptance.get("far_payload", {}).get("bytes") == 874
        and oracle.get("status") == "passed-linked-delivery-bound-CRC-oracle"
        and len(oracle.get("c2d_crc16", [])) == 6,
        "green Link-109 card/acceptance authority absent")
    for fact in value["artifacts_before"].values():
        require(fact == bind(ROOT / fact["path"]),
                f"frozen Link-109 artifact drift: {fact['path']}")
    result = deepcopy(value)
    result["acceptance"] = acceptance
    result["acceptance_binding"] = bind(ACCEPTANCE)
    return result


def frozen_artifacts() -> dict[str, dict[str, Any]]:
    return deepcopy(card_authority()["artifacts_before"])


def card_projection() -> dict[str, Any]:
    value = card_authority()
    return {"status": "PASS: Link 109 projects MAP-mask card authority",
        "attempt_accounting": {"cards_authorized": 1, "cards_consumed": 1,
            "device_contacts": 0, "product_link_attempts": 1,
            "wplto_runs": 1},
        "acceptance": value["acceptance"],
        "artifacts": value["artifacts_before"],
        "authority": {"Link109_card": bind(CARD.RECEIPT),
                      "acceptance": bind(ACCEPTANCE)}}


def downstream_source_gate(source_override: str | None = None) -> dict[str, Any]:
    source = DRIVER.read_text(encoding="utf-8") if source_override is None else source_override
    configure_start = source.index("\ndef configure() -> None:") + 1
    validate_start = source.index("\ndef validate(", configure_start)
    build_start = source.index("\ndef build() -> int:", validate_start) + 1
    selftest_start = source.index("\ndef selftest() -> int:", build_start)
    exercised = source[configure_start:validate_start]
    exercised += source[build_start:selftest_start]
    required = ("result = PIPE.orchestrate()", "PIPE.check()",
        "PIPE.card_authority = card_authority",
        "PIPE.frozen_artifacts = frozen_artifacts",
        "PIPE.card_projection = card_projection")
    forbidden = ("CARD.card()", "produce_candidate(", "single_link(",
                 "run_wplto(")
    require(all(token in exercised for token in required)
            and all(token not in exercised for token in forbidden),
            "Link-109 downstream adapter can re-enter product lifecycle")
    return {"status": "PASS: Link-109 downstream-only adapter",
            "fresh_process_stages": 6, "forbidden_calls": 0,
            "additional_WPLTO_runs": 0, "additional_product_links": 0,
            "additional_cards": 0}


def downstream_source_mutations() -> list[str]:
    source = DRIVER.read_text(encoding="utf-8")
    cases = {
        "drop-card-authority": source.replace(
            "    PIPE.card_authority = card_authority\n",
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
        except MediaError:
            rejected.append(name)
    require(rejected == list(cases), "Link-109 adapter mutation survived")
    return rejected


def configure() -> None:
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
    PIPE.CARD.RECEIPT = CARD.RECEIPT
    PIPE.card_authority = card_authority
    PIPE.frozen_artifacts = frozen_artifacts
    PIPE.card_projection = card_projection
    PIPE.downstream_source_gate = downstream_source_gate
    PIPE.downstream_source_mutations = downstream_source_mutations


def validate(value: dict[str, Any]) -> None:
    require(
        value.get("status") ==
            "PASS: Link 109 completed and same-world media closed; D1 ready"
        and value.get("frozen_before") == frozen_artifacts()
        and value.get("frozen_after") == value["frozen_before"]
        and value.get("media", {}).get("roles") == 19
        and value["media"].get("delivered_extent_bytes") == 48156
        and value["media"].get("far_payload_bytes") == 874
        and value["media"].get("same_world") is True
        and value["media"].get("readback") == "byteidentical"
        and value["execution_accounting"] == {
            "additional_WPLTO_runs": 0, "additional_product_links": 0,
            "additional_cards": 0, "artifact_completions": 1,
            "shared_media_builds": 3, "library_builds": 1,
            "device_contacts": 0}
        and value["hardware_handoff"] == {"D1_ready": True,
            "D2_D5_open": False, "session": bind(FAR_SESSION)},
        "Link-109 completion/media summary drift")


def build() -> int:
    configure()
    require(not RECEIPT.exists(), "Link-109 completion/media is one-shot")
    card_authority(); downstream_source_gate(); downstream_source_mutations()
    before = frozen_artifacts()
    result = PIPE.orchestrate()
    require(result == 0, "regular Link-109 completion/media pipeline red")
    after = frozen_artifacts(); pipeline = load(PIPELINE_RECEIPT)
    far = load(FAR_RECEIPT)
    require(before == after and pipeline["media"]["roles"] == 19
            and pipeline["media"]["same_world"] is True
            and pipeline["media"]["readback"] == "byteidentical"
            and far["hardware_handoff"]["D1_repeat_authorized"] is True,
            "regular Link-109 media result red")
    value = {"format": "lisp65-c2.3-v2.1-map-mask-completion-media-v1",
        "recorded_on": "2026-08-15",
        "status": "PASS: Link 109 completed and same-world media closed; D1 ready",
        "authority": {"card": bind(CARD.RECEIPT),
            "acceptance": bind(ACCEPTANCE), "pipeline": bind(PIPELINE_RECEIPT),
            "driver": bind(DRIVER)},
        "frozen_before": before, "frozen_after": after,
        "completion": pipeline["completion"],
        "media": {**pipeline["media"], "same_world": True,
                  "readback": "byteidentical"},
        "source_gate": downstream_source_gate(),
        "source_mutations_rejected": downstream_source_mutations(),
        "execution_accounting": {"additional_WPLTO_runs": 0,
            "additional_product_links": 0, "additional_cards": 0,
            "artifact_completions": 1, "shared_media_builds": 3,
            "library_builds": 1, "device_contacts": 0},
        "hardware_handoff": {"D1_ready": True, "D2_D5_open": False,
            "session": bind(FAR_SESSION)},
        "claim_limit": "Host Completion/media only; D1 not run, D2-D5 closed."}
    validate(value); RECEIPT.write_bytes(canonical(value))
    print("2.1 Link 109 completion/media: PASS roles=19 D1=ready")
    return 0


def check() -> int:
    configure(); value = load(RECEIPT); validate(value); PIPE.check()
    print("2.1 Link 109 completion/media: CHECK PASS D1=ready D2-D5=closed")
    return 0


def selftest() -> int:
    configure(); card_authority(); downstream_source_gate()
    require(len(downstream_source_mutations()) == 3,
            "Link-109 adapter mutation count drift")
    print("2.1 Link 109 completion/media: SELFTEST PASS source=3 card=green")
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
    if action == "build": return build()
    if action == "check": return check()
    if action == "selftest": return selftest()
    return child(action)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"2.1 Link 109 completion/media: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(2)
