#!/usr/bin/env python3
"""Complete Link 107 and close its dependent-VMA same-world media.

This is a downstream-only lifecycle over the sole green v4-Golden card.  It
reuses the already-qualified six-stage current-world media pipeline, replacing
only the card/output bindings and the reviewed Golden operator.  No producer,
WPLTO, linker or additional product card is reachable from this driver.
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

import c2_v20_map_tuple_media as FLOW  # noqa: E402
import c2_v20_source_oracle_media as COMPLETE  # noqa: E402
import c2_v21_dependency_invariant_golden as GOLD  # noqa: E402
import c2_v21_dependent_vma_replacement_card as CARD  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
CARD_BUILD = CARD.BUILD
BASE_BUILD = ROOT / "build/c2.3/v2.1-dependent-vma-media-base"
LIVE_BUILD = ROOT / "build/c2.3/v2.1-dependent-vma-media-liveness"
FAR_BUILD = ROOT / "build/c2.3/v2.1-dependent-vma-media"
BASE_RECEIPT = ARCH / "c2.3-v2.1-dependent-vma-base-media-receipt.json"
LIVE_RECEIPT = ARCH / "c2.3-v2.1-dependent-vma-liveness-media-receipt.json"
FAR_RECEIPT = ARCH / "c2.3-v2.1-dependent-vma-media-receipt.json"
SUMMARY_RECEIPT = ARCH / (
    "c2.3-v2.1-dependent-vma-completion-media-receipt.json")
BASE_SESSION = ROOT / "config/c2-v150-v21-dependent-vma-device-session.json"
LIVE_SESSION = ROOT / (
    "config/c2-v150-v21-dependent-vma-liveness-device-session.json")
FAR_SESSION = ROOT / (
    "config/c2-v150-v21-dependent-vma-far-device-session.json")
DRIVER = Path(__file__).resolve()
RECORDED_ON = "2026-08-15"
LINK = 107


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
    comparison = value.get("dependent_vma_comparison", {})
    require(
        value.get("status") ==
            "PASS: sole dependent-VMA replacement card green"
        and value.get("attempt_accounting") == {
            "cards_authorized": 1, "cards_consumed": 1,
            "WPLTO_runs": 1, "product_links": 1,
            "completion_runs": 0, "media_builds": 0, "device_contacts": 0}
        and value.get("artifacts_before") == value.get("artifacts_after")
        and comparison.get("allocatable_sections") == 103
        and comparison.get("dependent_fixed_vmas") == 101
        and comparison.get("dependent_free_derived_vmas") == 2
        and comparison.get("fixed_boundary_symbols") == 27
        and acceptance["delivered_bytes"]["identity_mismatches"] == 0
        and acceptance["far_payload"]["bytes"] == 874
        and oracle.get("status") == "passed-linked-delivery-bound-CRC-oracle"
        and oracle.get("records_per_image") == 6
        and len(oracle.get("c2d_crc16", [])) == 6,
        "green Link-107 dependent-VMA card authority absent")
    for name, fact in value["artifacts_before"].items():
        require(fact == bind(ROOT / fact["path"]),
                f"Link-107 frozen artifact drift: {name}")
    return value


def frozen_artifacts() -> dict[str, dict[str, Any]]:
    return deepcopy(card_authority()["artifacts_before"])


def card_projection() -> dict[str, Any]:
    value = card_authority()
    return {
        "status": "PASS: Link 107 projects dependent-VMA card authority",
        "attempt_accounting": {"cards_authorized": 1, "cards_consumed": 1,
            "device_contacts": 0, "product_link_attempts": 1,
            "wplto_runs": 1},
        "acceptance": value["acceptance"],
        "artifacts": value["artifacts_before"],
        "authority": {"Link107_card": bind(CARD.RECEIPT)},
    }


def configure_flow() -> None:
    FLOW.CARD_BUILD = CARD_BUILD
    FLOW.BASE_BUILD = BASE_BUILD
    FLOW.LIVE_BUILD = LIVE_BUILD
    FLOW.FAR_BUILD = FAR_BUILD
    FLOW.BASE_RECEIPT = BASE_RECEIPT
    FLOW.LIVE_RECEIPT = LIVE_RECEIPT
    FLOW.FAR_RECEIPT = FAR_RECEIPT
    FLOW.SUMMARY_RECEIPT = SUMMARY_RECEIPT
    FLOW.BASE_SESSION = BASE_SESSION
    FLOW.LIVE_SESSION = LIVE_SESSION
    FLOW.FAR_SESSION = FAR_SESSION
    FLOW.DRIVER = DRIVER
    FLOW.RECORDED_ON = RECORDED_ON
    FLOW.LINK = LINK
    FLOW.REPLAY.RECEIPT = CARD.RECEIPT
    FLOW.REPLAY.frozen_artifacts = frozen_artifacts
    FLOW.replay_authority = card_authority
    FLOW.card_projection = card_projection
    FLOW.BASE.INV = GOLD


def downstream_source_gate(source_override: str | None = None) -> dict[str, Any]:
    source = DRIVER.read_text(encoding="utf-8") if source_override is None else source_override
    tree = ast.parse(source)
    functions = {node.name: node for node in tree.body
                 if isinstance(node, ast.FunctionDef)}
    orchestrate = functions.get("orchestrate")
    require(orchestrate is not None, "Link-107 media orchestrator absent")
    calls = [ast.unparse(node.func) for node in ast.walk(orchestrate)
             if isinstance(node, ast.Call)]
    forbidden = {"CARD.card", "CARD.produce_child",
                 "FLOW.REPLACEMENT.card", "FLOW.MAP_CARD.card",
                 "FLOW.BASE.PRODUCER.produce_candidate",
                 "FLOW.BASE.PRODUCT.single_link"}
    require(calls.count("run_child") == 6 and not (set(calls) & forbidden),
            "Link-107 media path can re-enter card/producer/link lifecycle")
    return {"status": "PASS: downstream-only Link-107 completion/media",
            "fresh_process_stages": 6, "product_cards": 0,
            "WPLTO_runs": 0, "product_links": 0,
            "forbidden_calls_absent": sorted(forbidden)}


def downstream_source_mutations() -> list[str]:
    source = DRIVER.read_text(encoding="utf-8")
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
        except (MediaError, SyntaxError):
            rejected.append(name)
    require(rejected == list(cases), "Link-107 media source mutation survived")
    return rejected


def configure_stages() -> None:
    configure_flow()
    FLOW.downstream_source_gate = downstream_source_gate
    FLOW.downstream_source_mutations = downstream_source_mutations
    COMPLETE.CARD = CARD
    COMPLETE.CARD_BUILD = CARD_BUILD
    COMPLETE.DRIVER = DRIVER
    COMPLETE.LINK = LINK
    COMPLETE.card_authority = card_authority
    COMPLETE.frozen_artifacts = frozen_artifacts
    COMPLETE.card_projection = card_projection
    FLOW.BASE.completion_delta = completion_delta


def completion_delta() -> dict[str, Any]:
    """Validate an already-completed producer artifact as the predecessor."""
    base = FLOW.BASE
    card = base.card_authority()
    wplto = CARD_BUILD / "wplto"
    final = CARD_BUILD / "final"
    linked = final / "lisp65-c2-substitution-linked.prg"
    elf = Path(str(linked) + ".elf")
    before = (final / "lisp65-c2-substitution-unbound.prg").read_bytes()
    after = linked.read_bytes()
    require(len(before) == len(after), "artifact completion changed PRG length")
    load_address = int.from_bytes(before[:2], "little")
    truth = base.ElfTruth.read(
        elf, llvm_readobj=ROOT / "tools/llvm-mos/bin/llvm-readobj")
    binding = truth.section(".lisp65_runtime_overlay_verifier_bindings")
    allowed = set(range(binding.address, binding.address + binding.bytes))
    allowed.update(base.CARD.CARVEOUT)
    changed = {
        load_address + offset - 2
        for offset, (left, right) in enumerate(zip(before, after))
        if left != right and offset >= 2}
    require(changed <= allowed and set(base.CARD.CARVEOUT) <= changed,
            "completion escaped runtime-binding/CRC publish-last domain")
    window = (final / "c2-product-kernal-window.bin").read_bytes()
    require(len(window) == 0x2000, "completed KERNAL window is truncated")
    crc = base.CARD.crc16_oracle(window)
    high = after[2 + base.CARD.HIGH - load_address]
    low = after[2 + base.CARD.LOW - load_address]
    require((high, low) == (crc >> 8, crc & 0xFF),
            "final candidate CRC operands differ from final window")
    require(
        (final / "lisp65-c2-substitution-window-bound.prg").read_bytes() ==
            (wplto / "lisp65-c2-substitution-window-bound.prg").read_bytes()
        and linked.read_bytes() ==
            (wplto / "lisp65-c2-substitution-linked.prg").read_bytes()
        and card["artifacts"]["prg"] == bind(
            wplto / "lisp65-c2-substitution-linked.prg"),
        "artifact completion predecessor differs from consumed bound card PRG")
    return {
        "status": "passed-domain-aware-already-published-completion",
        "allowed_addresses": len(allowed),
        "changed_addresses": len(changed), "changes_outside_domain": 0,
        "runtime_binding": {"address": binding.address,
                            "bytes": binding.bytes},
        "CRC_operands": [base.CARD.HIGH, base.CARD.LOW],
        "final_window_crc16": f"0x{crc:04x}",
        "final_values": [high, low],
        "predecessor": "consumed-card-already-published",
    }


def published_binding_gate(
        out: Path, target: Path, boot_manifest: Path,
        session_manifest: Path, *, expected_base: int) -> dict[str, Any]:
    """Consume an already-published table without publishing it twice."""
    base = FLOW.BASE
    product = base.PRODUCT
    elf = Path(str(target) + ".elf")
    truth = base.ElfTruth.read(
        elf, llvm_readobj=ROOT / "tools/llvm-mos/bin/llvm-readobj")
    section = truth.section(product.VERIFIER_BINDING_SECTION)
    require((section.address, section.bytes) == (
                expected_base, product.runtime_binding_bytes()),
            "already-published verifier binding geometry drift")
    raw = target.read_bytes()
    load_address = int.from_bytes(raw[:2], "little")
    offset = 2 + section.address - load_address
    binding = product.verifier_binding_bytes(boot_manifest, session_manifest)
    if product.FAMILY_STAGE_BINDINGS:
        binding += product.family_stage_binding_bytes(
            boot_manifest, session_manifest)
    require(raw[offset:offset + section.bytes] == binding,
            "already-published verifier table differs from current manifests")
    source = CARD_BUILD / "wplto"
    report = load(source / "runtime-verifier-publish-last.json")
    require(
        report.get("status") == "passed"
        and report.get("address") == section.address
        and report.get("expected_address") == expected_base
        and report.get("bytes") == section.bytes
        and report.get("bound_sha256") == hashlib.sha256(raw).hexdigest()
        and report.get("binding_sha256") == hashlib.sha256(binding).hexdigest()
        and bind(out / "runtime-overlay-verifier-bindings.bin")["sha256"] ==
            hashlib.sha256(binding).hexdigest()
        and bind(out / "lisp65-c2-substitution-window-bound.prg")["sha256"] ==
            report["pre_overlay_binding_sha256"],
        "already-published verifier receipt/artifact drift")
    return report


def complete_child() -> int:
    configure_stages()
    FLOW.configure_base()
    FLOW.BASE.INV = GOLD
    product = FLOW.BASE.PRODUCT
    original = product.patch_verifier_binding_table
    product.patch_verifier_binding_table = published_binding_gate
    try:
        return COMPLETE.link105_complete_action()
    finally:
        product.patch_verifier_binding_table = original


def base_child() -> int:
    configure_stages()
    return FLOW.base_child()


def base_check_child() -> int:
    configure_stages()
    return FLOW.base_check_child()


def liveness_child() -> int:
    configure_stages()
    return FLOW.liveness_child()


def liveness_check_child() -> int:
    configure_stages()
    return FLOW.liveness_check_child()


def far_child() -> int:
    configure_stages()
    return FLOW.far_child()


def far_check_child() -> int:
    configure_stages()
    return FLOW.far_check_child()


def run_child(action: str) -> None:
    environment = os.environ.copy()
    environment.update(FLOW.BASE.PRODUCER.BASE.L95.CAN.canonical_build_environment())
    result = subprocess.run(
        [sys.executable, str(DRIVER), action], cwd=ROOT, env=environment,
        text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        check=False)
    require(result.returncode == 0,
            f"Link-107 completion/media child {action} red:\n{result.stdout}")


def completion_resume_authority() -> dict[str, Any] | None:
    receipt = CARD_BUILD / "receipts/artifact-completion.json"
    final = CARD_BUILD / "final"
    if not receipt.exists() and not final.exists():
        return None
    require(receipt.is_file() and final.is_dir(),
            "partial Completion cannot be resumed")
    value = load(receipt)
    require(
        value.get("status") ==
            "passed-no-relink-publish-last-artifact-completion"
        and value.get("compiler_runs") == value.get("linker_runs") == 0,
        "existing Completion receipt is not resumable green")
    configure_stages(); FLOW.configure_base()
    delta = completion_delta()
    return {"receipt": bind(receipt), "delta": delta,
            "mode": "resume-green-completion-without-reexecution"}


def orchestrate() -> int:
    configure_stages()
    resume = completion_resume_authority()
    require(
        not BASE_BUILD.exists() and not LIVE_BUILD.exists()
        and not FAR_BUILD.exists() and not BASE_RECEIPT.exists()
        and not LIVE_RECEIPT.exists() and not FAR_RECEIPT.exists()
        and not SUMMARY_RECEIPT.exists() and not BASE_SESSION.exists()
        and not LIVE_SESSION.exists() and not FAR_SESSION.exists()
        and (not (CARD_BUILD / "final").exists() or resume is not None),
        "Link-107 completion/media lifecycle is one-shot")
    card_authority(); downstream_source_gate(); downstream_source_mutations()
    frozen_before = frozen_artifacts()
    run_child("_base")
    run_child("_base_check")
    run_child("_liveness")
    run_child("_liveness_check")
    run_child("_far")
    run_child("_far_check")
    frozen_after = frozen_artifacts()
    require(frozen_after == frozen_before,
            "Link-107 media path changed a frozen WPLTO artifact")
    far = load(FAR_RECEIPT)
    packed = far.get("packed_artifact_gate_registry", {})
    require(
        far.get("status") ==
            "V20-MAPPED-FAR-PAYLOAD-DELIVERED; D1-REPEAT-AUTHORIZED"
        and far["materialization"]["delivered_bytes"] == 48156
        and far["materialization"]["payload_bytes"] == 874
        and far["materialization"]["gate"]["identity_mismatches"] == 0
        and packed.get("complete") is True
        and packed.get("registered") == packed.get("executed")
        and packed["results"]["autoboot.c65.elf"]["result"] ==
            "passed-actual-linked-stager-prefix"
        and packed["results"]["lisp65-product.d81/CODE.BIN"]
            ["identity_mismatches"] == 0
        and far["pair_identity"]["result"] == "same-world-pair"
        and far["hardware_handoff"]["D1_repeat_authorized"] is True
        and far["hardware_handoff"]["D2_D5_open"] is False,
        "Link-107 final media closure is not D1-ready")
    value = {
        "format": "lisp65-c2.3-v21-dependent-vma-completion-media-v1",
        "recorded_on": RECORDED_ON,
        "status": "PASS: Link 107 completed and media closed; D1 ready",
        "authority": {"Link107_card": bind(CARD.RECEIPT),
            "dependent_VMA_golden": bind(GOLD.GOLDEN),
            "base_media": bind(BASE_RECEIPT),
            "liveness_media": bind(LIVE_RECEIPT),
            "far_media": bind(FAR_RECEIPT), "driver": bind(DRIVER)},
        "immutable_before": frozen_before, "immutable_after": frozen_after,
        "candidate_oracle": card_authority()["acceptance"]
            ["source_authoritative_oracle"],
        "completion": bind(CARD_BUILD / "receipts/artifact-completion.json"),
        "final_artifacts": {
            "elf": bind(CARD_BUILD / "final/lisp65-c2-substitution-linked.prg.elf"),
            "prg": bind(CARD_BUILD / "final/lisp65-c2-substitution-linked.prg"),
            "manifest": bind(FLOW.BASE.MANIFEST)},
        "media": {"product_D81": bind(FAR_BUILD / "shared-system/lisp65-product.d81"),
            "library_D81": bind(BASE_BUILD / "library/lisp65-library.d81"),
            "session": bind(FAR_SESSION), "roles": 19,
            "far_payload_bytes": 874, "delivered_extent_bytes": 48156,
            "readback": "byteidentical", "same_world": True,
            "packed_gate_registry_complete": True,
            "actual_ELF_liveness": "passed-actual-linked-stager-prefix"},
        "source_gate": downstream_source_gate(),
        "source_mutations_rejected": downstream_source_mutations(),
        "completion_binding": {
            "mode": "consume-already-published",
            "source": bind(CARD_BUILD / "wplto/runtime-verifier-publish-last.json"),
            "double_publish_attempted": False,
            "resume": resume},
        "execution_accounting": {"additional_product_cards": 0,
            "additional_WPLTO_runs": 0, "additional_product_links": 0,
            "artifact_completions": 1, "shared_media_builds": 3,
            "library_builds": 1, "device_contacts": 0},
        "hardware_handoff": {"D1_ready": True, "D2_D5_open": False,
            "session": bind(FAR_SESSION)},
        "claim_limit": "Host completion/media only; D1 not run, D2-D5 closed.",
    }
    validate_summary(value)
    value["mutations_rejected"] = summary_mutations(value)
    SUMMARY_RECEIPT.write_bytes(canonical(value))
    print("2.1 Link 107 completion/media: PASS roles=19 extent=48156 D1=ready")
    return 0


def validate_summary(value: dict[str, Any]) -> None:
    configure_stages()
    require(
        value.get("status") == "PASS: Link 107 completed and media closed; D1 ready"
        and value.get("immutable_before") == frozen_artifacts()
        and value.get("immutable_after") == value["immutable_before"]
        and value.get("candidate_oracle", {}).get("records_per_image") == 6
        and len(value["candidate_oracle"]["c2d_crc16"]) == 6
        and value["media"]["roles"] == 19
        and value["media"]["far_payload_bytes"] == 874
        and value["media"]["delivered_extent_bytes"] == 48156
        and value["media"]["readback"] == "byteidentical"
        and value["media"]["same_world"] is True
        and value["media"]["packed_gate_registry_complete"] is True
        and value["media"]["actual_ELF_liveness"] ==
            "passed-actual-linked-stager-prefix"
        and value["completion_binding"]["mode"] ==
            "consume-already-published"
        and value["completion_binding"]["double_publish_attempted"] is False
        and value["media"]["session"] == bind(FAR_SESSION)
        and value["media"]["product_D81"] == bind(
            FAR_BUILD / "shared-system/lisp65-product.d81")
        and value["media"]["library_D81"] == bind(
            BASE_BUILD / "library/lisp65-library.d81")
        and value["execution_accounting"] == {
            "additional_product_cards": 0, "additional_WPLTO_runs": 0,
            "additional_product_links": 0, "artifact_completions": 1,
            "shared_media_builds": 3, "library_builds": 1,
            "device_contacts": 0}
        and value["hardware_handoff"] == {
            "D1_ready": True, "D2_D5_open": False,
            "session": bind(FAR_SESSION)},
        "Link-107 completion/media summary drift")


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
        "double-publish": lambda x: x["completion_binding"].update(
            double_publish_attempted=True),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        candidate = deepcopy(value); mutate(candidate)
        try:
            validate_summary(candidate)
        except MediaError:
            rejected.append(name)
    require(rejected == list(cases), "Link-107 summary mutation survived")
    return rejected


def check() -> int:
    configure_stages()
    value = load(SUMMARY_RECEIPT)
    rejected = value.pop("mutations_rejected", None)
    validate_summary(value)
    require(rejected == summary_mutations(value),
            "Link-107 media summary mutation drift")
    run_child("_far_check")
    print("2.1 Link 107 completion/media: CHECK PASS D1=ready D2-D5=closed")
    return 0


def selftest() -> int:
    configure_stages(); card_authority(); downstream_source_gate()
    require(len(downstream_source_mutations()) == 4,
            "Link-107 media source mutation count drift")
    FLOW.configure_base()
    _paths, candidate = FLOW.BASE.configure_candidate()
    replay = candidate.REPLAY
    replay.PROFILE.configure()
    replay.BANK2.configure_bank2_stage()
    replay.TWO.configure_two_region()
    replay.LINK60.configure_current_pin_adapters()
    replay.P.configure_intern_session_service()
    FLOW.BASE.PRODUCT.configure_full_map_ownership()
    FLOW.BASE.PRODUCT.configure_low_resident_lma_reset()
    source = CARD_BUILD / "wplto"
    published_binding_gate(
        source, source / "lisp65-c2-substitution-linked.prg",
        source / "runtime-overlays-boot-final.json",
        source / "runtime-overlays-session-final.json",
        expected_base=0xB98C)
    print("2.1 Link 107 completion/media: SELFTEST PASS source=4 "
          "binding=already-published")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=(
        "selftest", "build", "check", "_complete", "_base", "_base_check",
        "_liveness", "_liveness_check", "_far", "_far_check"))
    action = parser.parse_args().action
    if action == "build":
        return orchestrate()
    return {"selftest": selftest, "check": check,
        "_complete": complete_child, "_base": base_child,
        "_base_check": base_check_child, "_liveness": liveness_child,
        "_liveness_check": liveness_check_child,
        "_far": far_child, "_far_check": far_check_child}[action]()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"2.1 Link 107 completion/media: FIRST RED: {error}",
              file=sys.stderr)
        raise SystemExit(2)
