#!/usr/bin/env python3
"""Complete Link 105 and close its same-world v1.5 media.

This is a strictly downstream, one-shot lifecycle.  The consumed Link 105
card is the only artifact authority.  Six fresh-process stages perform
publish-last completion, base media closure, actual packed-ELF liveness
closure, and mapped-far extent/identity closure.  No producer, WPLTO, linker,
or product card is reachable from this driver.
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
import c2_v20_source_oracle_replacement3_card as CARD  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
CARD_BUILD = CARD.BUILD
BASE_BUILD = ROOT / "build/c2.3/v2.0-source-oracle-media-base"
LIVE_BUILD = ROOT / "build/c2.3/v2.0-source-oracle-media-liveness"
FAR_BUILD = ROOT / "build/c2.3/v2.0-source-oracle-media"
BASE_RECEIPT = EVIDENCE / (
    "c2.3-v2.0-source-oracle-base-media-closure-receipt.json")
LIVE_RECEIPT = EVIDENCE / (
    "c2.3-v2.0-source-oracle-liveness-media-closure-receipt.json")
FAR_RECEIPT = EVIDENCE / (
    "c2.3-v2.0-source-oracle-media-closure-receipt.json")
SUMMARY_RECEIPT = EVIDENCE / (
    "c2.3-v2.0-source-oracle-completion-media-receipt.json")
BASE_SESSION = ROOT / "config/c2-v150-v20-source-oracle-device-session.json"
LIVE_SESSION = ROOT / (
    "config/c2-v150-v20-source-oracle-liveness-device-session.json")
FAR_SESSION = ROOT / (
    "config/c2-v150-v20-source-oracle-far-device-session.json")
DRIVER = Path(__file__).resolve()
RECORDED_ON = "2026-08-13"
LINK = 105


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
            == "PASS: candidate-world source-oracle replacement card green"
        and value.get("attempt_accounting") == {
            "replacement_cards_authorized": 1,
            "replacement_cards_consumed": 1,
            "wplto_runs": 1, "product_links": 1,
            "media_builds": 0, "device_contacts": 0}
        and value.get("artifacts_before") == value.get("artifacts_after")
        and acceptance["VMA_golden"]["allocatable_sections"] == 103
        and acceptance["VMA_golden"]["fixed_boundary_symbols"] == 27
        and acceptance["delivered_bytes"]["identity_mismatches"] == 0
        and acceptance["far_payload"]["bytes"] == 874
        and oracle.get("status")
            == "passed-linked-delivery-bound-CRC-oracle"
        and oracle.get("records_per_image") == 6
        and len(oracle.get("c2d_crc16", [])) == 6,
        "green Link 105 candidate-world card authority absent")
    for name, fact in value["artifacts_before"].items():
        require(fact == bind(ROOT / fact["path"]),
                f"Link 105 frozen artifact drift: {name}")
    return value


def frozen_artifacts() -> dict[str, dict[str, Any]]:
    return deepcopy(card_authority()["artifacts_before"])


def card_projection() -> dict[str, Any]:
    value = card_authority()
    return {
        "status": "PASS: Link 105 projects green card authority",
        "attempt_accounting": {
            "cards_authorized": 1, "cards_consumed": 1,
            "device_contacts": 0, "product_link_attempts": 1,
            "wplto_runs": 1},
        "acceptance": value["acceptance"],
        "artifacts": value["artifacts_before"],
        "authority": {"Link105_card": bind(CARD.RECEIPT)},
    }


def configure_flow() -> None:
    """Bind the established downstream stages to Link 105 and fresh outputs."""
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


def downstream_source_gate(source_override: str | None = None) -> dict[str, Any]:
    source = DRIVER.read_text(encoding="utf-8") if source_override is None else source_override
    tree = ast.parse(source)
    functions = {node.name: node for node in tree.body
                 if isinstance(node, ast.FunctionDef)}
    orchestrate = functions.get("orchestrate")
    require(orchestrate is not None, "Link 105 media orchestrator absent")
    calls = [ast.unparse(node.func) for node in ast.walk(orchestrate)
             if isinstance(node, ast.Call)]
    forbidden = {"CARD.card", "CARD.produce_candidate",
                 "FLOW.REPLACEMENT.card", "FLOW.MAP_CARD.card",
                 "FLOW.BASE.PRODUCER.produce_candidate",
                 "FLOW.BASE.PRODUCT.single_link"}
    require(calls.count("run_child") == 6 and not (set(calls) & forbidden),
            "Link 105 media path can re-enter card/producer/link lifecycle")
    return {
        "status": "PASS: Link 105 downstream-only completion/media lifecycle",
        "fresh_process_stages": 6, "product_cards": 0,
        "WPLTO_runs": 0, "product_links": 0,
        "forbidden_calls_absent": sorted(forbidden),
    }


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
    require(rejected == list(cases), "Link 105 media source mutation survived")
    return rejected


def completion_adapter_gate(source_override: str | None = None) -> dict[str, Any]:
    """The completion adapter must forward current full-map ownership."""
    source = DRIVER.read_text(encoding="utf-8") if source_override is None else source_override
    tree = ast.parse(source)
    functions = {node.name: node for node in tree.body
                 if isinstance(node, ast.FunctionDef)}
    outer = functions.get("_link105_fixed_audit")
    complete = functions.get("link105_complete_action")
    inner = None if complete is None else next((
        node for node in complete.body
        if isinstance(node, ast.FunctionDef) and node.name == "fixed_adapter"),
        None)
    require(outer is not None and inner is not None,
            "completion adapter functions are absent")
    outer_args = {item.arg for item in outer.args.kwonlyargs}
    inner_args = {item.arg for item in inner.args.kwonlyargs}
    forwarded = [
        keyword for node in ast.walk(tree) if isinstance(node, ast.Call)
        for keyword in node.keywords
        if keyword.arg == "full_map_ownership"
        and isinstance(keyword.value, ast.Name)
        and keyword.value.id == "full_map_ownership"]
    require("full_map_ownership" in outer_args
            and "full_map_ownership" in inner_args
            and len(forwarded) == 2,
            "completion adapter does not preserve full-map ownership")
    return {
        "status": "PASS: completion adapter forwards full-map ownership",
        "outer_adapter": True, "nested_real_consumer_adapter": True,
        "forwarding_sites": 2,
    }


def completion_adapter_mutations() -> list[str]:
    source = DRIVER.read_text(encoding="utf-8")
    cases = {
        "drop-outer-full-map-parameter": source.replace(
            "def _link105_fixed_audit(\n"
            "        original: Callable[..., dict[str, Any]], elf: Path,\n"
            "        *, out: Path | None = None, require_hot_bss: bool = True,\n"
            "        full_map_ownership: bool = False,\n",
            "def _link105_fixed_audit(\n"
            "        original: Callable[..., dict[str, Any]], elf: Path,\n"
            "        *, out: Path | None = None, require_hot_bss: bool = True,\n",
            1),
        "drop-real-consumer-full-map-parameter": source.replace(
            "    def fixed_adapter(elf: Path, *, out: Path | None = None,\n"
            "                      require_hot_bss: bool = True,\n"
            "                      full_map_ownership: bool = False) -> dict[str, Any]:\n",
            "    def fixed_adapter(elf: Path, *, out: Path | None = None,\n"
            "                      require_hot_bss: bool = True) -> dict[str, Any]:\n",
            1),
        "drop-full-map-forwarding": source.replace(
            "    value = original(\n"
            "        elf, out=None, require_hot_bss=False,\n"
            "        full_map_ownership=full_map_ownership)\n",
            "    value = original(elf, out=None, require_hot_bss=False)\n",
            1),
    }
    rejected: list[str] = []
    for name, candidate in cases.items():
        try:
            completion_adapter_gate(candidate)
        except MediaError:
            rejected.append(name)
    require(rejected == list(cases),
            "completion adapter compatibility mutation survived")
    return rejected


def configure_stages() -> None:
    configure_flow()
    FLOW.downstream_source_gate = downstream_source_gate
    FLOW.downstream_source_mutations = downstream_source_mutations


def _link105_fixed_audit(
        original: Callable[..., dict[str, Any]], elf: Path,
        *, out: Path | None = None, require_hot_bss: bool = True,
        full_map_ownership: bool = False,
        ) -> dict[str, Any]:
    """Adapt artifact completion to the current fixed-leaf ABI."""
    base = FLOW.BASE
    value = original(
        elf, out=None, require_hot_bss=False,
        full_map_ownership=full_map_ownership)
    comparison = base.INV.compare_elf(elf)
    base.require(comparison == card_projection()["acceptance"]["VMA_golden"],
                 "Link 105 completion fixed-state authority drift")
    truth = base.ElfTruth.read(
        elf, llvm_readobj=ROOT / "tools/llvm-mos/bin/llvm-readobj")
    hot = truth.section(".lisp65_c2_fixed_bank0_hot_bss")
    noinit = truth.section(".noinit")
    base.require(
        (hot.address, hot.bytes) == (0xC25D, 240)
        and (noinit.address, noinit.bytes) == (0xC34D, 0),
        "Link 105 owned hot-BSS/noinit geometry drift")
    value["hot_bss"] = {
        "authority": "VMA-invariant-golden-and-Link105-card",
        "address": hot.address, "bytes": hot.bytes,
        "end_exclusive": hot.address + hot.bytes,
        "following_noinit": {
            "address": noinit.address, "bytes": noinit.bytes,
            "end_exclusive": noinit.address + noinit.bytes},
        "heap_start": 0xC354, "overlay_floor": 0xC356,
    }
    value["VMA_golden"] = comparison
    if out is not None:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(canonical(value))
    return value


def link105_complete_action() -> int:
    """Run only canonical publish-last completion over frozen Link 105."""
    base = FLOW.BASE
    card = card_projection()
    paths, can = base.configure_candidate()
    base.require(not paths["final"].exists() and not base.MANIFEST.exists(),
                 "Link 105 artifact completion is one-shot")

    replay = can.REPLAY
    original_configure = replay.configure
    original_fixed = base.PRODUCT.FIXED_BLOCK_LEAF.audit_elf
    original_facade = base.PRODUCT.fixed_facade_gate
    original_verify = can.verify_published_verifier_binding
    geometry_ready = False

    def current_geometry() -> None:
        nonlocal geometry_ready
        if geometry_ready:
            return
        replay.PROFILE.configure()
        replay.BANK2.configure_bank2_stage()
        replay.TWO.configure_two_region()
        replay.LINK60.configure_current_pin_adapters()
        replay.P.configure_intern_session_service()
        base.PRODUCT.configure_full_map_ownership()
        base.PRODUCT.configure_low_resident_lma_reset()
        replay.P.PRODUCT_ARTIFACTS_MANIFEST = (
            paths["static_product"] / "substitution-artifacts.json")
        elf = paths["wplto"] / "lisp65-c2-substitution-linked.prg.elf"
        binding = base.ElfTruth.read(
            elf, llvm_readobj=ROOT / "tools/llvm-mos/bin/llvm-readobj"
        ).section(".lisp65_runtime_overlay_verifier_bindings")
        base.require((binding.address, binding.bytes) == (0xB98C, 40),
                     "Link 105 runtime-verifier binding geometry drift")
        replay.P.VERIFIER_BINDING_BASE = binding.address
        replay.P.LINK60_VERIFIER_BINDING_BASE = binding.address
        base.require(
            replay.P.RUNTIME_OVERLAY_FORMAT_VERSION == 4
            and replay.P.PROFILE_RODATA_BYTES == 348
            and replay.P.runtime_binding_bytes() == 40
            and replay.P.total_publish_last_bytes() == 42
            and replay.P.INTERN_SESSION_SERVICE,
            "Link 105 artifact-completion service shape drift")
        geometry_ready = True

    def fixed_adapter(elf: Path, *, out: Path | None = None,
                      require_hot_bss: bool = True,
                      full_map_ownership: bool = False) -> dict[str, Any]:
        return _link105_fixed_audit(
            original_fixed, elf, out=out,
            require_hot_bss=require_hot_bss,
            full_map_ownership=full_map_ownership)

    def facade_adapter(out: Path, target: Path,
                       suffix: str) -> dict[str, Any]:
        return base._current_facade_gate(
            original_facade, out, target, suffix)

    def publish_runtime_binding(
            product: Path, boot_manifest: Path,
            session_manifest: Path) -> dict[str, Any]:
        return base.PRODUCT.patch_verifier_binding_table(
            can.FINAL, product, boot_manifest, session_manifest,
            expected_base=base.PRODUCT.LINK60_VERIFIER_BINDING_BASE)

    current_geometry()
    delivery = base.CARD.delivered_bytes_gate(
        paths["wplto"] / "lisp65-c2-substitution-linked.prg.elf",
        paths["wplto"] / "lisp65-c2-substitution-linked.prg")
    base.require(delivery == card["acceptance"]["delivered_bytes"],
                 "Link 105 delivered-byte authority drift before completion")

    replay.configure = current_geometry
    base.PRODUCT.FIXED_BLOCK_LEAF.audit_elf = fixed_adapter
    base.PRODUCT.fixed_facade_gate = facade_adapter
    can.verify_published_verifier_binding = publish_runtime_binding
    try:
        completion = can.complete_artifacts()
    finally:
        replay.configure = original_configure
        base.PRODUCT.FIXED_BLOCK_LEAF.audit_elf = original_fixed
        base.PRODUCT.fixed_facade_gate = original_facade
        can.verify_published_verifier_binding = original_verify
    base.require(
        completion["status"]
            == "passed-no-relink-publish-last-artifact-completion"
        and completion["compiler_runs"] == completion["linker_runs"] == 0,
        "Link 105 artifact completion red")
    print("2.0 Link 105 completion: PASS compiler=0 linker=0")
    return 0


def complete_child() -> int:
    configure_stages()
    FLOW.configure_base()
    return link105_complete_action()


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
            f"Link 105 completion/media child {action} red:\n{result.stdout}")


def orchestrate() -> int:
    configure_stages()
    require(
        not BASE_BUILD.exists() and not LIVE_BUILD.exists()
        and not FAR_BUILD.exists() and not BASE_RECEIPT.exists()
        and not LIVE_RECEIPT.exists() and not FAR_RECEIPT.exists()
        and not SUMMARY_RECEIPT.exists() and not BASE_SESSION.exists()
        and not LIVE_SESSION.exists() and not FAR_SESSION.exists()
        and not (CARD_BUILD / "final").exists(),
        "Link 105 completion/media lifecycle is one-shot")
    card_authority()
    downstream_source_gate()
    downstream_source_mutations()
    frozen_before = frozen_artifacts()
    run_child("_base")
    run_child("_base_check")
    run_child("_liveness")
    run_child("_liveness_check")
    run_child("_far")
    run_child("_far_check")
    frozen_after = frozen_artifacts()
    require(frozen_after == frozen_before,
            "Link 105 media path changed a frozen WPLTO artifact")
    far = load(FAR_RECEIPT)
    packed = far.get("packed_artifact_gate_registry", {})
    require(
        far.get("status")
            == "V20-MAPPED-FAR-PAYLOAD-DELIVERED; D1-REPEAT-AUTHORIZED"
        and far["materialization"]["delivered_bytes"] == 48156
        and far["materialization"]["payload_bytes"] == 874
        and far["materialization"]["gate"]["identity_mismatches"] == 0
        and packed.get("complete") is True
        and packed.get("registered") == packed.get("executed")
        and packed["results"]["autoboot.c65.elf"]["result"]
            == "passed-actual-linked-stager-prefix"
        and packed["results"]["lisp65-product.d81/CODE.BIN"]
            ["identity_mismatches"] == 0
        and far["pair_identity"]["result"] == "same-world-pair"
        and far["hardware_handoff"]["D1_repeat_authorized"] is True
        and far["hardware_handoff"]["D2_D5_open"] is False,
        "Link 105 final media closure is not D1-ready")
    configure_stages()
    value = {
        "format": "lisp65-c2.3-v20-source-oracle-completion-media-v1",
        "recorded_on": RECORDED_ON,
        "status": "PASS: Link 105 completed and media closed; D1 ready",
        "authority": {
            "Link105_card": bind(CARD.RECEIPT),
            "base_media": bind(BASE_RECEIPT),
            "liveness_media": bind(LIVE_RECEIPT),
            "far_media": bind(FAR_RECEIPT), "driver": bind(DRIVER)},
        "immutable_before": frozen_before, "immutable_after": frozen_after,
        "candidate_oracle": card_authority()["acceptance"]
            ["source_authoritative_oracle"],
        "completion": bind(
            CARD_BUILD / "receipts/artifact-completion.json"),
        "final_artifacts": {
            "elf": bind(CARD_BUILD / (
                "final/lisp65-c2-substitution-linked.prg.elf")),
            "prg": bind(CARD_BUILD / (
                "final/lisp65-c2-substitution-linked.prg")),
            "manifest": bind(FLOW.BASE.MANIFEST)},
        "media": {
            "product_D81": bind(
                FAR_BUILD / "shared-system/lisp65-product.d81"),
            "library_D81": bind(
                BASE_BUILD / "library/lisp65-library.d81"),
            "session": bind(FAR_SESSION), "roles": 19,
            "far_payload_bytes": 874, "delivered_extent_bytes": 48156,
            "readback": "byteidentical", "same_world": True,
            "packed_gate_registry_complete": True,
            "actual_ELF_liveness": "passed-actual-linked-stager-prefix"},
        "source_gate": downstream_source_gate(),
        "source_mutations_rejected": downstream_source_mutations(),
        "completion_adapter_gate": completion_adapter_gate(),
        "completion_adapter_mutations_rejected": completion_adapter_mutations(),
        "execution_accounting": {
            "additional_product_cards": 0, "additional_WPLTO_runs": 0,
            "additional_product_links": 0, "artifact_completions": 1,
            "shared_media_builds": 3, "library_builds": 1,
            "device_contacts": 0},
        "hardware_handoff": {
            "D1_ready": True, "D2_D5_open": False,
            "session": bind(FAR_SESSION)},
        "claim_limit": (
            "Link 105 artifact completion and host/media closure only. "
            "D1 is ready but has not run; D2-D5 remain closed."),
    }
    validate_summary(value)
    value["mutations_rejected"] = summary_mutations(value)
    SUMMARY_RECEIPT.write_bytes(canonical(value))
    print("2.0 Link 105 completion/media: PASS roles=19 extent=48156 D1=ready")
    return 0


def validate_summary(value: dict[str, Any]) -> None:
    configure_stages()
    require(
        value.get("status") == "PASS: Link 105 completed and media closed; D1 ready"
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
        and value["media"]["actual_ELF_liveness"]
            == "passed-actual-linked-stager-prefix"
        and value["media"]["session"] == bind(FAR_SESSION)
        and value["media"]["product_D81"] == bind(
            FAR_BUILD / "shared-system/lisp65-product.d81")
        and value["media"]["library_D81"] == bind(
            BASE_BUILD / "library/lisp65-library.d81")
        and value["completion_adapter_gate"] == completion_adapter_gate()
        and value["completion_adapter_mutations_rejected"]
            == completion_adapter_mutations()
        and value["execution_accounting"] == {
            "additional_product_cards": 0, "additional_WPLTO_runs": 0,
            "additional_product_links": 0, "artifact_completions": 1,
            "shared_media_builds": 3, "library_builds": 1,
            "device_contacts": 0}
        and value["hardware_handoff"] == {
            "D1_ready": True, "D2_D5_open": False,
            "session": bind(FAR_SESSION)},
        "Link 105 completion/media summary drift")


def summary_mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "claim-link": lambda x: x["execution_accounting"].update(
            additional_product_links=1),
        "truncate-far": lambda x: x["media"].update(
            delivered_extent_bytes=48155),
        "cross-world": lambda x: x["media"].update(same_world=False),
        "omit-packed-gate": lambda x: x["media"].update(
            packed_gate_registry_complete=False),
        "lose-liveness": lambda x: x["media"].update(
            actual_ELF_liveness="source-only"),
        "open-D2": lambda x: x["hardware_handoff"].update(D2_D5_open=True),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        candidate = deepcopy(value)
        mutate(candidate)
        try:
            validate_summary(candidate)
        except MediaError:
            rejected.append(name)
    require(rejected == list(cases), "Link 105 media summary mutation survived")
    return rejected


def rebind_base_child() -> int:
    configure_stages()
    return FLOW.rebind_base_child()


def rebind_liveness_child() -> int:
    configure_stages()
    return FLOW.rebind_liveness_child()


def rebind_far_child() -> int:
    configure_stages()
    return FLOW.rebind_far_child()


def rebind_summary_child() -> int:
    configure_stages()
    value = load(SUMMARY_RECEIPT)
    value.pop("mutations_rejected", None)
    value["authority"] = {
        "Link105_card": bind(CARD.RECEIPT),
        "base_media": bind(BASE_RECEIPT),
        "liveness_media": bind(LIVE_RECEIPT),
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
    value["completion_adapter_gate"] = completion_adapter_gate()
    value["completion_adapter_mutations_rejected"] = (
        completion_adapter_mutations())
    validate_summary(value)
    value["mutations_rejected"] = summary_mutations(value)
    SUMMARY_RECEIPT.write_bytes(canonical(value))
    return 0


def rebind_action() -> int:
    """Update only receipt authorities after downstream driver hardening."""
    require(BASE_BUILD.is_dir() and LIVE_BUILD.is_dir() and FAR_BUILD.is_dir()
            and SUMMARY_RECEIPT.is_file(),
            "completed Link 105 media chain absent for authority rebind")
    run_child("_rebind_base")
    run_child("_rebind_liveness")
    run_child("_rebind_far")
    run_child("_rebind_summary")
    print("2.0 Link 105 completion/media: REBIND PASS artifacts=unchanged")
    return 0


def check() -> int:
    configure_stages()
    value = load(SUMMARY_RECEIPT)
    rejected = value.pop("mutations_rejected", None)
    validate_summary(value)
    require(rejected == summary_mutations(value),
            "Link 105 media summary mutation drift")
    run_child("_far_check")
    print("2.0 Link 105 completion/media: CHECK PASS D1=ready D2-D5=closed")
    return 0


def selftest() -> int:
    configure_stages()
    card_authority()
    downstream_source_gate()
    require(len(downstream_source_mutations()) == 4,
            "Link 105 media source mutation count drift")
    completion_adapter_gate()
    require(len(completion_adapter_mutations()) == 3,
            "completion adapter mutation count drift")
    print("2.0 Link 105 completion/media: SELFTEST PASS source=4 adapter=3")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=(
        "selftest", "build", "check", "_complete", "_base",
        "_base_check", "_liveness", "_liveness_check", "_far",
        "_far_check", "rebind", "_rebind_base", "_rebind_liveness",
        "_rebind_far", "_rebind_summary"))
    action = parser.parse_args().action
    if action == "build":
        return orchestrate()
    return {
        "selftest": selftest, "check": check,
        "_complete": complete_child, "_base": base_child,
        "_base_check": base_check_child, "_liveness": liveness_child,
        "_liveness_check": liveness_check_child, "_far": far_child,
        "_far_check": far_check_child,
        "rebind": rebind_action, "_rebind_base": rebind_base_child,
        "_rebind_liveness": rebind_liveness_child,
        "_rebind_far": rebind_far_child,
        "_rebind_summary": rebind_summary_child,
    }[action]()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"2.0 Link 105 completion/media: FIRST RED: {error}",
              file=sys.stderr)
        raise SystemExit(2)
