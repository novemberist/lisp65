#!/usr/bin/env python3
"""Complete and close current-world media after the MAP-tuple replay."""

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

import c2_v20_crc_carveout_media as BASE  # noqa: E402
import c2_v20_crc_carveout_media_liveness as LIVE  # noqa: E402
import c2_v20_far_payload_delivery as FAR  # noqa: E402
import c2_v20_map_tuple_artifact_replay as REPLAY  # noqa: E402
import c2_v20_map_tuple_fix_card as MAP_CARD  # noqa: E402
import c2_v20_map_tuple_fix_replacement_card as REPLACEMENT  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
CARD_BUILD = REPLACEMENT.BUILD
BASE_BUILD = ROOT / "build/c2.3/v2.0-map-tuple-media-base"
LIVE_BUILD = ROOT / "build/c2.3/v2.0-map-tuple-media-liveness"
FAR_BUILD = ROOT / "build/c2.3/v2.0-map-tuple-media"
BASE_RECEIPT = EVIDENCE / "c2.3-v2.0-map-tuple-base-media-closure-receipt.json"
LIVE_RECEIPT = EVIDENCE / "c2.3-v2.0-map-tuple-liveness-media-closure-receipt.json"
FAR_RECEIPT = EVIDENCE / "c2.3-v2.0-map-tuple-media-closure-receipt.json"
SUMMARY_RECEIPT = EVIDENCE / (
    "c2.3-v2.0-map-tuple-completion-media-receipt.json")
BASE_SESSION = ROOT / "config/c2-v150-v20-map-tuple-device-session.json"
LIVE_SESSION = ROOT / "config/c2-v150-v20-map-tuple-liveness-device-session.json"
FAR_SESSION = ROOT / "config/c2-v150-v20-map-tuple-far-device-session.json"
DRIVER = Path(__file__).resolve()
RECORDED_ON = "2026-08-13"
LINK = 101


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


def replay_authority() -> dict[str, Any]:
    value = load(REPLAY.RECEIPT)
    require(
        value.get("status") == "PASS: fresh-process artifact-only replay green"
        and value.get("immutable_before") == value.get("immutable_after")
        and value.get("execution_accounting", {}).get("WPLTO_runs") == 0
        and value["acceptance"]["VMA_golden"]["allocatable_sections"] == 103
        and value["acceptance"]["delivered_bytes"]["identity_mismatches"] == 0,
        "green artifact-only replay authority absent")
    for name in ("elf", "prg", "map"):
        require(value["immutable_before"][name] == bind(
            ROOT / value["immutable_before"][name]["path"]),
            f"frozen replay artifact drift: {name}")
    return value


def card_projection() -> dict[str, Any]:
    replay = replay_authority()
    return {
        "status": "PASS: artifact-only replay projects green card authority",
        "attempt_accounting": {"cards_authorized": 1, "cards_consumed": 1,
            "device_contacts": 0, "product_link_attempts": 1, "wplto_runs": 1},
        "acceptance": replay["acceptance"],
        "artifacts": replay["immutable_before"],
        "authority": {"artifact_replay": bind(REPLAY.RECEIPT)},
    }


ORIGINAL_CONFIGURE_CANDIDATE = BASE.configure_candidate


def configure_candidate() -> tuple[dict[str, Path], Any]:
    MAP_CARD.configure_fix_source()
    return ORIGINAL_CONFIGURE_CANDIDATE()


def downstream_source_gate(source_override: str | None = None) -> dict[str, Any]:
    source = DRIVER.read_text(encoding="utf-8") if source_override is None else source_override
    tree = ast.parse(source)
    functions = {node.name: node for node in tree.body
                 if isinstance(node, ast.FunctionDef)}
    orchestrate = functions.get("orchestrate")
    require(orchestrate is not None, "completion/media orchestrator absent")
    calls = [ast.unparse(node.func) for node in ast.walk(orchestrate)
             if isinstance(node, ast.Call)]
    forbidden = {"REPLACEMENT.card", "MAP_CARD.card", "BASE.CARD.card",
                 "BASE.PRODUCER.produce_candidate", "BASE.PRODUCT.single_link"}
    require(
        calls.count("run_child") == 6 and not (set(calls) & forbidden),
        "completion/media orchestrator can re-enter a card/producer/link")
    return {"status": "PASS: downstream-only completion/media lifecycle",
            "fresh_process_stages": 6, "product_cards": 0,
            "WPLTO_runs": 0, "product_links": 0,
            "forbidden_calls_absent": sorted(forbidden)}


def downstream_source_mutations() -> list[str]:
    source = DRIVER.read_text(encoding="utf-8")
    cases = {
        "reenter-card": source.replace(
            '    run_child("_base")\n',
            "    REPLACEMENT.card()\n    run_child(\"_base\")\n", 1),
        "drop-far-stage": source.replace('    run_child("_far")\n', "", 1),
        "drop-far-readback": source.replace('    run_child("_far_check")\n', "", 1),
    }
    rejected: list[str] = []
    for name, candidate in cases.items():
        try:
            downstream_source_gate(candidate)
        except (MediaError, SyntaxError):
            rejected.append(name)
    require(rejected == list(cases), "downstream media source mutation survived")
    return rejected


def configure_base() -> None:
    BASE.BUILD = BASE_BUILD
    BASE.SHARED = BASE_BUILD / "shared-system"
    BASE.LIBRARY = BASE_BUILD / "library"
    BASE.MANIFEST = CARD_BUILD / "canonical-product-manifest.json"
    BASE.PRODUCT_D81 = BASE.SHARED / "lisp65-product.d81"
    BASE.WORK_D81 = BASE.SHARED / "lisp65-work.d81"
    BASE.LIBRARY_D81 = BASE.LIBRARY / "lisp65-library.d81"
    BASE.MEDIA_MANIFEST = BASE.SHARED / "candidate-manifest.json"
    BASE.RECEIPT = BASE_RECEIPT
    BASE.SESSION = BASE_SESSION
    BASE.DRIVER = DRIVER
    BASE.LINK = LINK
    BASE._CONFIGURE_CALLS = 0
    BASE.CARD.BUILD = CARD_BUILD
    BASE.CARD.RECEIPT = REPLAY.RECEIPT
    BASE.card_authority = card_projection
    BASE.configure_candidate = configure_candidate
    BASE.source_gate = downstream_source_gate
    BASE.source_mutations = downstream_source_mutations


def configure_liveness() -> None:
    configure_base()
    LIVE.BUILD = LIVE_BUILD
    LIVE.SHARED = LIVE_BUILD / "shared-system"
    LIVE.MANIFEST = LIVE.SHARED / "candidate-manifest.json"
    LIVE.DESCRIPTOR = LIVE.SHARED / "boot.id"
    LIVE.STAGER = LIVE.SHARED / "autoboot.c65"
    LIVE.STAGER_ELF = LIVE.SHARED / "autoboot.c65.elf"
    LIVE.STAGER_MAP = LIVE.SHARED / "autoboot.c65.map"
    LIVE.PRODUCT_D81 = LIVE.SHARED / "lisp65-product.d81"
    LIVE.WORK_D81 = LIVE.SHARED / "lisp65-work.d81"
    LIVE.MOUNT = LIVE.SHARED / "lisp65-product.mount.json"
    LIVE.LIBRARY_D81 = BASE.LIBRARY_D81
    LIVE.PRODUCT_MANIFEST = BASE.MANIFEST
    LIVE.PREDECESSOR_RECEIPT = BASE.RECEIPT
    LIVE.RECEIPT = LIVE_RECEIPT
    LIVE.SESSION = LIVE_SESSION


def configure_far() -> None:
    configure_liveness()
    FAR.BUILD = FAR_BUILD
    FAR.INPUTS = FAR_BUILD / "product-inputs"
    FAR.SHARED = FAR_BUILD / "shared-system"
    FAR.PRODUCT_MANIFEST = FAR.INPUTS / "canonical-product-manifest.json"
    FAR.BANK2 = FAR.INPUTS / "bank2-static-code.bin"
    FAR.MEDIA_MANIFEST = FAR.SHARED / "candidate-manifest.json"
    FAR.DESCRIPTOR = FAR.SHARED / "boot.id"
    FAR.STAGER = FAR.SHARED / "autoboot.c65"
    FAR.STAGER_ELF = FAR.SHARED / "autoboot.c65.elf"
    FAR.STAGER_MAP = FAR.SHARED / "autoboot.c65.map"
    FAR.PRODUCT_D81 = FAR.SHARED / "lisp65-product.d81"
    FAR.WORK_D81 = FAR.SHARED / "lisp65-work.d81"
    FAR.MOUNT = FAR.SHARED / "lisp65-product.mount.json"
    FAR.LIBRARY_D81 = BASE.LIBRARY_D81
    FAR.BASE_MANIFEST = BASE.MANIFEST
    FAR.ELF = CARD_BUILD / "final/lisp65-c2-substitution-linked.prg.elf"
    FAR.RECEIPT = FAR_RECEIPT
    FAR.SESSION = FAR_SESSION


def complete_child() -> int:
    configure_base()
    return BASE.complete_action()


def base_child() -> int:
    configure_base()
    return BASE.build_action()


def base_check_child() -> int:
    configure_base()
    return BASE.check()


def liveness_child() -> int:
    configure_liveness()
    return LIVE.build_action()


def liveness_check_child() -> int:
    configure_liveness()
    return LIVE.check()


def far_child() -> int:
    configure_far()
    return FAR.build_action()


def far_check_child() -> int:
    configure_far()
    return FAR.check()


def run_child(action: str) -> None:
    environment = os.environ.copy()
    environment.update(BASE.PRODUCER.BASE.L95.CAN.canonical_build_environment())
    result = subprocess.run(
        [sys.executable, str(DRIVER), action], cwd=ROOT, env=environment,
        text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
    require(result.returncode == 0,
            f"completion/media child {action} red:\n{result.stdout}")


def orchestrate() -> int:
    require(
        not BASE_BUILD.exists() and not LIVE_BUILD.exists() and not FAR_BUILD.exists()
        and not BASE_RECEIPT.exists() and not LIVE_RECEIPT.exists()
        and not FAR_RECEIPT.exists() and not SUMMARY_RECEIPT.exists()
        and not BASE_SESSION.exists() and not LIVE_SESSION.exists()
        and not FAR_SESSION.exists() and not (CARD_BUILD / "final").exists(),
        "MAP-tuple completion/media lifecycle is one-shot")
    replay_authority(); downstream_source_gate(); downstream_source_mutations()
    frozen_before = REPLAY.frozen_artifacts()
    run_child("_base")
    run_child("_base_check")
    run_child("_liveness")
    run_child("_liveness_check")
    run_child("_far")
    run_child("_far_check")
    frozen_after = REPLAY.frozen_artifacts()
    require(frozen_after == frozen_before,
            "completion/media changed a frozen WPLTO artifact")
    far = load(FAR_RECEIPT)
    require(
        far.get("status") == "V20-MAPPED-FAR-PAYLOAD-DELIVERED; D1-REPEAT-AUTHORIZED"
        and far["materialization"]["delivered_bytes"] == 48156
        and far["materialization"]["payload_bytes"] == 874
        and far["materialization"]["gate"]["identity_mismatches"] == 0
        and far["hardware_handoff"]["D1_repeat_authorized"] is True
        and far["hardware_handoff"]["D2_D5_open"] is False,
        "final MAP-tuple media closure is not D1-ready")
    value = {
        "format": "lisp65-c2.3-v20-map-tuple-completion-media-v1",
        "recorded_on": RECORDED_ON,
        "status": "PASS: corrected MAP tuple completed and media closed; D1 ready",
        "authority": {"artifact_replay": bind(REPLAY.RECEIPT),
            "base_media": bind(BASE_RECEIPT), "liveness_media": bind(LIVE_RECEIPT),
            "far_media": bind(FAR_RECEIPT), "driver": bind(DRIVER)},
        "immutable_before": frozen_before, "immutable_after": frozen_after,
        "completion": bind(CARD_BUILD / "receipts/artifact-completion.json"),
        "final_artifacts": {
            "elf": bind(CARD_BUILD / "final/lisp65-c2-substitution-linked.prg.elf"),
            "prg": bind(CARD_BUILD / "final/lisp65-c2-substitution-linked.prg"),
            "manifest": bind(BASE.MANIFEST)},
        "media": {"product_D81": bind(FAR.PRODUCT_D81),
            "library_D81": bind(FAR.LIBRARY_D81),
            "session": bind(FAR_SESSION), "roles": 19,
            "far_payload_bytes": 874, "delivered_extent_bytes": 48156,
            "readback": "byteidentical", "same_world": True},
        "source_gate": downstream_source_gate(),
        "source_mutations_rejected": downstream_source_mutations(),
        "execution_accounting": {"additional_product_cards": 0,
            "additional_WPLTO_runs": 0, "additional_product_links": 0,
            "artifact_completions": 1, "shared_media_builds": 3,
            "library_builds": 1, "device_contacts": 0},
        "hardware_handoff": {"D1_ready": True, "D2_D5_open": False,
                             "session": bind(FAR_SESSION)},
        "claim_limit": (
            "Artifact completion and host/media closure only. D1 is ready but "
            "has not run; D2-D5 remain closed."),
    }
    SUMMARY_RECEIPT.write_bytes(canonical(value))
    print("2.0 MAP-tuple completion/media: PASS roles=19 extent=48156 D1=ready")
    return 0


def validate_summary(value: dict[str, Any]) -> None:
    expected_manifest = CARD_BUILD / "canonical-product-manifest.json"
    expected_product = FAR_BUILD / "shared-system/lisp65-product.d81"
    expected_library = BASE_BUILD / "library/lisp65-library.d81"
    require(
        value.get("status")
            == "PASS: corrected MAP tuple completed and media closed; D1 ready"
        and value.get("immutable_before") == REPLAY.frozen_artifacts()
        and value.get("immutable_after") == value["immutable_before"]
        and value.get("media", {}).get("far_payload_bytes") == 874
        and value["media"]["delivered_extent_bytes"] == 48156
        and value["media"]["readback"] == "byteidentical"
        and value["media"]["same_world"] is True
        and value["media"]["session"] == bind(FAR_SESSION)
        and value["final_artifacts"]["manifest"] == bind(expected_manifest)
        and value["media"]["product_D81"] == bind(expected_product)
        and value["media"]["library_D81"] == bind(expected_library)
        and value["execution_accounting"] == {
            "additional_product_cards": 0, "additional_WPLTO_runs": 0,
            "additional_product_links": 0, "artifact_completions": 1,
            "shared_media_builds": 3, "library_builds": 1,
            "device_contacts": 0}
        and value["hardware_handoff"] == {
            "D1_ready": True, "D2_D5_open": False,
            "session": bind(FAR_SESSION)},
        "MAP-tuple completion/media summary drift")


def rebind_base_child() -> int:
    configure_base()
    base = BASE.derive()
    BASE.validate(base, verify=False)
    base["mutations_rejected"] = BASE.receipt_mutations(base)
    BASE_RECEIPT.write_bytes(canonical(base))
    return 0


def rebind_liveness_child() -> int:
    configure_liveness()
    return LIVE.close_action()


def rebind_far_child() -> int:
    configure_far()
    return FAR.close_action()


def rebind_summary_child() -> int:
    configure_far()
    value = load(SUMMARY_RECEIPT)
    value.pop("mutations_rejected", None)
    value["authority"] = {"artifact_replay": bind(REPLAY.RECEIPT),
        "base_media": bind(BASE_RECEIPT), "liveness_media": bind(LIVE_RECEIPT),
        "far_media": bind(FAR_RECEIPT), "driver": bind(DRIVER)}
    value["final_artifacts"]["manifest"] = bind(
        CARD_BUILD / "canonical-product-manifest.json")
    value["media"]["product_D81"] = bind(
        FAR_BUILD / "shared-system/lisp65-product.d81")
    value["media"]["library_D81"] = bind(
        BASE_BUILD / "library/lisp65-library.d81")
    value["media"]["session"] = bind(FAR_SESSION)
    value["hardware_handoff"]["session"] = bind(FAR_SESSION)
    value["source_gate"] = downstream_source_gate()
    value["source_mutations_rejected"] = downstream_source_mutations()
    validate_summary(value)
    value["mutations_rejected"] = summary_mutations(value)
    SUMMARY_RECEIPT.write_bytes(canonical(value))
    return 0


def rebind_action() -> int:
    """Repair only authority projections after this driver's summary fix."""
    require(
        BASE_BUILD.is_dir() and LIVE_BUILD.is_dir() and FAR_BUILD.is_dir()
        and SUMMARY_RECEIPT.is_file(),
        "completed media chain absent for read-only authority rebind")

    run_child("_rebind_base")
    run_child("_rebind_liveness")
    run_child("_rebind_far")
    run_child("_rebind_summary")
    print("2.0 MAP-tuple completion/media: REBIND PASS artifacts=unchanged")
    return 0


def summary_mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "claim-link": lambda x: x["execution_accounting"].update(
            additional_product_links=1),
        "truncate-far": lambda x: x["media"].update(delivered_extent_bytes=48155),
        "cross-world": lambda x: x["media"].update(same_world=False),
        "open-D2": lambda x: x["hardware_handoff"].update(D2_D5_open=True),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        candidate = deepcopy(value); mutate(candidate)
        try:
            validate_summary(candidate)
        except MediaError:
            rejected.append(name)
    require(rejected == list(cases), "media summary mutation survived")
    return rejected


def check() -> int:
    value = load(SUMMARY_RECEIPT); rejected = value.pop("mutations_rejected", None)
    validate_summary(value)
    require(rejected == summary_mutations(value), "media summary mutation drift")
    run_child("_far_check")
    print("2.0 MAP-tuple completion/media: CHECK PASS D1=ready D2-D5=closed")
    return 0


def selftest() -> int:
    replay_authority(); downstream_source_gate()
    require(len(downstream_source_mutations()) == 3,
            "completion/media source mutation count drift")
    print("2.0 MAP-tuple completion/media: SELFTEST PASS source=3")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("selftest", "build", "check",
        "_complete", "_base", "_base_check", "_liveness",
        "_liveness_check", "_far", "_far_check", "_rebind",
        "_rebind_base", "_rebind_liveness", "_rebind_far",
        "_rebind_summary"))
    action = parser.parse_args().action
    if action == "build":
        result = orchestrate()
        value = load(SUMMARY_RECEIPT)
        value["mutations_rejected"] = summary_mutations(value)
        SUMMARY_RECEIPT.write_bytes(canonical(value))
        return result
    return {"selftest": selftest, "check": check,
            "_complete": complete_child, "_base": base_child,
            "_base_check": base_check_child, "_liveness": liveness_child,
            "_liveness_check": liveness_check_child, "_far": far_child,
            "_far_check": far_check_child, "_rebind": rebind_action,
            "_rebind_base": rebind_base_child,
            "_rebind_liveness": rebind_liveness_child,
            "_rebind_far": rebind_far_child,
            "_rebind_summary": rebind_summary_child}[action]()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"2.0 MAP-tuple completion/media: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(2)
