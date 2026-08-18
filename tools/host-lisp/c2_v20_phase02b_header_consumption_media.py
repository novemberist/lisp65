#!/usr/bin/env python3
"""Complete Link 106 and close its same-world v1.5 media.

The established Link-105 downstream lifecycle is reused without any path back
to WPLTO or the linker.  This adapter supplies only the green Link-106 card
authority and fresh completion/media domains, then records a Link-106 summary
over the independently checked inherited stage receipts.
"""

from __future__ import annotations

import argparse
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

import c2_v20_phase02b_header_consumption_replacement_card as CARD  # noqa: E402
import c2_v20_source_oracle_media as MEDIA  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
CARD_BUILD = CARD.BUILD
BASE_BUILD = ROOT / "build/c2.3/v2.0-phase02b-header-consumption-media-base"
LIVE_BUILD = ROOT / (
    "build/c2.3/v2.0-phase02b-header-consumption-media-liveness")
FAR_BUILD = ROOT / "build/c2.3/v2.0-phase02b-header-consumption-media"
BASE_RECEIPT = EVIDENCE / (
    "c2.3-v2.0-phase02b-header-consumption-base-media-receipt.json")
LIVE_RECEIPT = EVIDENCE / (
    "c2.3-v2.0-phase02b-header-consumption-liveness-media-receipt.json")
FAR_RECEIPT = EVIDENCE / (
    "c2.3-v2.0-phase02b-header-consumption-media-receipt.json")
INHERITED_SUMMARY = EVIDENCE / (
    "c2.3-v2.0-phase02b-header-consumption-inherited-media-receipt.json")
SUMMARY_RECEIPT = EVIDENCE / (
    "c2.3-v2.0-phase02b-header-consumption-completion-media-receipt.json")
BASE_SESSION = ROOT / (
    "config/c2-v150-v20-phase02b-header-consumption-device-session.json")
LIVE_SESSION = ROOT / (
    "config/c2-v150-v20-phase02b-header-consumption-liveness-device-session.json")
FAR_SESSION = ROOT / (
    "config/c2-v150-v20-phase02b-header-consumption-far-device-session.json")
DRIVER = Path(__file__).resolve()
RECORDED_ON = "2026-08-13"
LINK = 106
ORIGINAL_MEDIA_SOURCE = Path(MEDIA.__file__).read_text(encoding="utf-8")
ORIGINAL_DOWNSTREAM_GATE = MEDIA.downstream_source_gate
ORIGINAL_COMPLETION_GATE = MEDIA.completion_adapter_gate


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
    value = load(CARD.RECEIPT)
    acceptance = value.get("acceptance", {})
    oracle = acceptance.get("source_authoritative_oracle", {})
    require(
        value.get("status")
            == "PASS: replacement Link-106 consumed candidate header"
        and value.get("attempt_accounting") == {
            "replacement_cards_authorized": 1,
            "replacement_cards_consumed": 1, "wplto_runs": 1,
            "product_links": 1, "media_builds": 0, "device_contacts": 0}
        and value.get("artifacts_before") == value.get("artifacts_after")
        and value.get("adapter_contract", {}).get(
            "non_exported_adapter_calls") == 0
        and acceptance["VMA_golden"]["allocatable_sections"] == 103
        and acceptance["VMA_golden"]["fixed_boundary_symbols"] == 27
        and acceptance["delivered_bytes"]["identity_mismatches"] == 0
        and acceptance["far_payload"]["bytes"] == 874
        and oracle.get("status") == "passed-linked-delivery-bound-CRC-oracle"
        and oracle.get("records_per_image") == 6
        and len(oracle.get("c2d_crc16", [])) == 6,
        "green Link 106 header-consumption card authority absent")
    for name, fact in value["artifacts_before"].items():
        require(fact == bind(ROOT / fact["path"]),
                f"Link 106 frozen artifact drift: {name}")
    return value


def frozen_artifacts() -> dict[str, dict[str, Any]]:
    return deepcopy(card_authority()["artifacts_before"])


def card_projection() -> dict[str, Any]:
    value = card_authority()
    return {
        "status": "PASS: Link 106 projects green card authority",
        "attempt_accounting": {"cards_authorized": 1, "cards_consumed": 1,
            "device_contacts": 0, "product_link_attempts": 1,
            "wplto_runs": 1},
        "acceptance": value["acceptance"],
        "artifacts": value["artifacts_before"],
        "authority": {"Link106_card": bind(CARD.RECEIPT)},
    }


def downstream_source_gate(source_override: str | None = None) -> dict[str, Any]:
    source = ORIGINAL_MEDIA_SOURCE if source_override is None else source_override
    value = ORIGINAL_DOWNSTREAM_GATE(source)
    require(value.get("fresh_process_stages") == 6
            and value.get("product_cards") == 0
            and value.get("WPLTO_runs") == value.get("product_links") == 0,
            "inherited downstream-only source gate drift")
    return {**value, "authority": "c2_v20_source_oracle_media.orchestrate"}


def downstream_source_mutations() -> list[str]:
    source = ORIGINAL_MEDIA_SOURCE
    cases = {
        "reenter-card": source.replace(
            '    run_child("_base")\n',
            '    CARD.card()\n    run_child("_base")\n', 1),
        "drop-far-stage": source.replace('    run_child("_far")\n', "", 1),
        "drop-far-readback": source.replace(
            '    run_child("_far_check")\n', "", 1),
        "reenter-link": source.replace(
            '    run_child("_base")\n',
            '    FLOW.BASE.PRODUCT.single_link()\n'
            '    run_child("_base")\n', 1),
    }
    rejected: list[str] = []
    for name, candidate in cases.items():
        try:
            downstream_source_gate(candidate)
        except Exception:
            rejected.append(name)
    require(rejected == list(cases), "downstream source mutation survived")
    return rejected


def completion_adapter_gate() -> dict[str, Any]:
    value = ORIGINAL_COMPLETION_GATE(ORIGINAL_MEDIA_SOURCE)
    require(value.get("forwarding_sites") == 2,
            "completion full-map adapter drift")
    return {**value, "authority": "c2_v20_source_oracle_media adapters"}


def completion_adapter_mutations() -> list[str]:
    source = ORIGINAL_MEDIA_SOURCE
    cases = {
        "drop-outer-full-map-parameter": source.replace(
            "        full_map_ownership: bool = False,\n",
            "", 1),
        "drop-real-consumer-full-map-parameter": source.replace(
            "                      full_map_ownership: bool = False) -> dict[str, Any]:\n",
            "                      ) -> dict[str, Any]:\n", 1),
        "drop-full-map-forwarding": source.replace(
            "        full_map_ownership=full_map_ownership)\n",
            "        full_map_ownership=False)\n", 1),
    }
    rejected: list[str] = []
    for name, candidate in cases.items():
        try:
            ORIGINAL_COMPLETION_GATE(candidate)
        except Exception:
            rejected.append(name)
    require(rejected == list(cases), "completion adapter mutation survived")
    return rejected


def configure_media() -> None:
    MEDIA.CARD = CARD
    MEDIA.CARD_BUILD = CARD_BUILD
    MEDIA.BASE_BUILD = BASE_BUILD
    MEDIA.LIVE_BUILD = LIVE_BUILD
    MEDIA.FAR_BUILD = FAR_BUILD
    MEDIA.BASE_RECEIPT = BASE_RECEIPT
    MEDIA.LIVE_RECEIPT = LIVE_RECEIPT
    MEDIA.FAR_RECEIPT = FAR_RECEIPT
    MEDIA.SUMMARY_RECEIPT = INHERITED_SUMMARY
    MEDIA.BASE_SESSION = BASE_SESSION
    MEDIA.LIVE_SESSION = LIVE_SESSION
    MEDIA.FAR_SESSION = FAR_SESSION
    MEDIA.DRIVER = DRIVER
    MEDIA.RECORDED_ON = RECORDED_ON
    MEDIA.LINK = LINK
    MEDIA.card_authority = card_authority
    MEDIA.frozen_artifacts = frozen_artifacts
    MEDIA.card_projection = card_projection
    MEDIA.downstream_source_gate = downstream_source_gate
    MEDIA.downstream_source_mutations = downstream_source_mutations
    MEDIA.completion_adapter_gate = completion_adapter_gate
    MEDIA.completion_adapter_mutations = completion_adapter_mutations


def complete_child() -> int:
    configure_media()
    return MEDIA.complete_child()


def base_child() -> int:
    configure_media()
    return MEDIA.base_child()


def base_check_child() -> int:
    configure_media()
    return MEDIA.base_check_child()


def liveness_child() -> int:
    configure_media()
    return MEDIA.liveness_child()


def liveness_check_child() -> int:
    configure_media()
    return MEDIA.liveness_check_child()


def far_child() -> int:
    configure_media()
    return MEDIA.far_child()


def far_check_child() -> int:
    configure_media()
    return MEDIA.far_check_child()


def run_child(action: str) -> None:
    environment = os.environ.copy()
    environment.update(
        MEDIA.FLOW.BASE.PRODUCER.BASE.L95.CAN.canonical_build_environment())
    result = subprocess.run(
        [sys.executable, str(DRIVER), action], cwd=ROOT, env=environment,
        text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        check=False)
    require(result.returncode == 0,
            f"Link 106 completion/media child {action} red:\n{result.stdout}")


def summary_value() -> dict[str, Any]:
    inherited = load(INHERITED_SUMMARY)
    far = load(FAR_RECEIPT)
    return {
        "format": "lisp65-c2.3-v20-phase02b-header-consumption-media-v1",
        "recorded_on": RECORDED_ON,
        "status": "PASS: Link 106 completed and media closed; D1 ready",
        "authority": {"Link106_card": bind(CARD.RECEIPT),
            "inherited_downstream_summary": bind(INHERITED_SUMMARY),
            "base_media": bind(BASE_RECEIPT),
            "liveness_media": bind(LIVE_RECEIPT),
            "far_media": bind(FAR_RECEIPT), "driver": bind(DRIVER)},
        "immutable_before": frozen_artifacts(),
        "immutable_after": frozen_artifacts(),
        "compiler_input_consumption": card_authority()[
            "compiler_input_consumption"],
        "completion": bind(CARD_BUILD / "receipts/artifact-completion.json"),
        "final_artifacts": {
            "elf": bind(CARD_BUILD / (
                "final/lisp65-c2-substitution-linked.prg.elf")),
            "prg": bind(CARD_BUILD / (
                "final/lisp65-c2-substitution-linked.prg")),
            "manifest": bind(CARD_BUILD / "canonical-product-manifest.json")},
        "media": {
            "product_D81": bind(
                FAR_BUILD / "shared-system/lisp65-product.d81"),
            "library_D81": bind(
                BASE_BUILD / "library/lisp65-library.d81"),
            "session": bind(FAR_SESSION), "roles": 19,
            "far_payload_bytes": 874, "delivered_extent_bytes": 48156,
            "readback": "byteidentical", "same_world": True,
            "packed_gate_registry_complete": far[
                "packed_artifact_gate_registry"]["complete"],
            "actual_ELF_liveness": far["packed_artifact_gate_registry"]
                ["results"]["autoboot.c65.elf"]["result"]},
        "downstream_source_gate": downstream_source_gate(),
        "downstream_mutations_rejected": downstream_source_mutations(),
        "completion_adapter_gate": completion_adapter_gate(),
        "completion_adapter_mutations_rejected": completion_adapter_mutations(),
        "execution_accounting": {"additional_product_cards": 0,
            "additional_WPLTO_runs": 0, "additional_product_links": 0,
            "artifact_completions": 1, "shared_media_builds": 3,
            "library_builds": 1, "device_contacts": 0},
        "hardware_handoff": {"D1_ready": True, "D2_D5_open": False,
            "session": bind(FAR_SESSION)},
        "inherited_stage_status": inherited["status"],
        "claim_limit": (
            "Link 106 completion and same-world host/media closure only. "
            "D1 is ready but has not run; D2-D5 remain closed."),
    }


def validate_summary(value: dict[str, Any]) -> None:
    require(
        value == summary_value()
        and value["status"] == "PASS: Link 106 completed and media closed; D1 ready"
        and value["immutable_before"] == value["immutable_after"]
        and value["media"]["roles"] == 19
        and value["media"]["delivered_extent_bytes"] == 48156
        and value["media"]["far_payload_bytes"] == 874
        and value["media"]["same_world"] is True
        and value["media"]["packed_gate_registry_complete"] is True
        and value["hardware_handoff"]["D1_ready"] is True
        and value["hardware_handoff"]["D2_D5_open"] is False,
        "Link 106 completion/media summary drift")


def summary_mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "claim-link": lambda x: x["execution_accounting"].update(
            additional_product_links=1),
        "truncate-far": lambda x: x["media"].update(
            delivered_extent_bytes=48155),
        "cross-world": lambda x: x["media"].update(same_world=False),
        "omit-packed-gate": lambda x: x["media"].update(
            packed_gate_registry_complete=False),
        "open-D2": lambda x: x["hardware_handoff"].update(D2_D5_open=True),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        candidate = deepcopy(value); mutate(candidate)
        try:
            validate_summary(candidate)
        except MediaError:
            rejected.append(name)
    require(rejected == list(cases), "Link 106 media summary mutation survived")
    return rejected


def build() -> int:
    configure_media()
    require(not SUMMARY_RECEIPT.exists(), "Link 106 media summary is one-shot")
    MEDIA.orchestrate()
    value = summary_value(); validate_summary(value)
    value["mutations_rejected"] = summary_mutations(value)
    SUMMARY_RECEIPT.write_bytes(canonical(value))
    print("2.0 Link 106 completion/media: PASS roles=19 extent=48156 D1=ready")
    return 0


def check() -> int:
    configure_media()
    value = load(SUMMARY_RECEIPT)
    rejected = value.pop("mutations_rejected", None)
    validate_summary(value)
    require(rejected == summary_mutations(value),
            "Link 106 media summary mutation receipt drift")
    MEDIA.check()
    print("2.0 Link 106 completion/media: CHECK PASS D1=ready D2-D5=closed")
    return 0


def selftest() -> int:
    configure_media()
    card_authority(); downstream_source_gate(); completion_adapter_gate()
    require(len(downstream_source_mutations()) == 4
            and len(completion_adapter_mutations()) == 3,
            "Link 106 completion/media selftest mutation drift")
    print("2.0 Link 106 completion/media: SELFTEST PASS source=4 adapter=3")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=(
        "selftest", "build", "check", "_complete", "_base",
        "_base_check", "_liveness", "_liveness_check", "_far",
        "_far_check"))
    action = parser.parse_args().action
    return {"selftest": selftest, "build": build, "check": check,
            "_complete": complete_child, "_base": base_child,
            "_base_check": base_check_child, "_liveness": liveness_child,
            "_liveness_check": liveness_check_child, "_far": far_child,
            "_far_check": far_check_child}[action]()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"2.0 Link 106 completion/media: FIRST RED: {error}",
              file=sys.stderr)
        raise SystemExit(2)
