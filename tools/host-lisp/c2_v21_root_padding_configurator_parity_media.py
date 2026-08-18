#!/usr/bin/env python3
"""Complete the configurator-parity finals and close same-world v1.5 media.

The four linked artifacts are immutable inputs.  This driver projects the
already-bound materialization inputs into their Completion context, runs the
publish-last artifact closer once, and delegates media construction to the
current candidate-derived/packed-gate pipeline.  It cannot compile, WPLTO,
link, or enter a product card.
"""

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

import c2_product_substitution_link as PRODUCT  # noqa: E402
import c2_v20_crc_carveout_card as CRC  # noqa: E402
import c2_v20_crc_carveout_media as CRC_MEDIA  # noqa: E402
import c2_v20_source_oracle_media as SOURCE_MEDIA  # noqa: E402
import c2_v21_phase9_abi_fix_media as PIPE  # noqa: E402
import c2_v21_root_padding_configurator_parity_acceptance as ACCEPT  # noqa: E402
import c2_v21_root_padding_configurator_projection_replacement as LINK  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.1-cpu-transport-work-plan.md"
TARGET = LINK.TARGET
WPLTO = LINK.WPLTO
FINAL = TARGET / "final"
RECEIPTS = TARGET / "receipts"
ACCEPTANCE = ACCEPT.RECEIPT
BASE_BUILD = ROOT / "build/c2.3/v2.1-configurator-parity-media-base"
LIVE_BUILD = ROOT / "build/c2.3/v2.1-configurator-parity-media-liveness"
FAR_BUILD = ROOT / "build/c2.3/v2.1-configurator-parity-media"
BASE_RECEIPT = ARCH / "c2.3-v2.1-configurator-parity-base-media-receipt.json"
LIVE_RECEIPT = ARCH / "c2.3-v2.1-configurator-parity-liveness-media-receipt.json"
FAR_RECEIPT = ARCH / "c2.3-v2.1-configurator-parity-far-media-receipt.json"
PIPELINE_RECEIPT = ARCH / (
    "c2.3-v2.1-configurator-parity-completion-media-pipeline-receipt.json")
RECEIPT = ARCH / (
    "c2.3-v2.1-configurator-parity-completion-media-receipt.json")
FIRST_RED = ARCH / (
    "c2.3-v2.1-configurator-parity-completion-first-red.json")
RESUME_RED = ARCH / (
    "c2.3-v2.1-configurator-parity-completion-resume-red.json")
POST_COMPLETION = ARCH / (
    "c2.3-v2.1-configurator-parity-post-completion-delivery-receipt.json")
CONFIGURATOR_PREFLIGHT = TARGET / (
    "receipts/configurator-parity-completion-preflight.json")
FAILED_ADAPTER_PREFLIGHT_ROOT = TARGET / "completion-adapter-preflight"
FAILED_GOLDEN_PREFLIGHT_ROOT = TARGET / (
    "completion-adapter-preflight-candidate-golden")
ADAPTER_PREFLIGHT_ROOT = TARGET / (
    "completion-adapter-preflight-ordered-publish-chain")
CLEANUP_RECEIPT = ARCH / (
    "c2.3-v2.1-configurator-parity-partial-completion-cleanup-receipt.json")
FINAL_RESUME_RED = ARCH / (
    "c2.3-v2.1-configurator-parity-completion-final-resume-red.json")
ADAPTER_AUTHORITY_RESUME_RED = ARCH / (
    "c2.3-v2.1-configurator-parity-adapter-authority-resume-red.json")
ORDERED_CHAIN_CLEANUP_RECEIPT = ARCH / (
    "c2.3-v2.1-configurator-parity-ordered-chain-cleanup-receipt.json")
ORDERED_CHAIN_RESUME_RED = ARCH / (
    "c2.3-v2.1-configurator-parity-ordered-chain-resume-red.json")
MEDIA_CLEANUP_RECEIPT = ARCH / (
    "c2.3-v2.1-configurator-parity-base-media-cleanup-receipt.json")
MEDIA_PREFLIGHT = TARGET / "receipts/configurator-parity-media-preflight.json"
MEDIA_RESUME_RED = ARCH / (
    "c2.3-v2.1-configurator-parity-media-resume-red.json")
MEDIA_RESUME_ATTRIBUTION = ARCH / (
    "c2.3-v2.1-configurator-parity-media-resume-attribution.json")
MANIFEST_CLEANUP_RECEIPT = ARCH / (
    "c2.3-v2.1-configurator-parity-manifest-cleanup-receipt.json")
REPLACEMENT_MEDIA_PREFLIGHT = TARGET / (
    "receipts/configurator-parity-replacement-media-preflight.json")
REPLACEMENT_MEDIA_RESUME_RED = ARCH / (
    "c2.3-v2.1-configurator-parity-replacement-media-resume-red.json")
BASE_SESSION = ROOT / "config/c2-v150-v21-configurator-parity-device-session.json"
LIVE_SESSION = ROOT / (
    "config/c2-v150-v21-configurator-parity-live-device-session.json")
FAR_SESSION = ROOT / (
    "config/c2-v150-v21-configurator-parity-far-device-session.json")
DRIVER = Path(__file__).resolve()
AUTHORIZATION = "7d49bb5d"
RESUME_AUTHORIZATION = "d5d54fe2"
FINAL_RESUME_AUTHORIZATION = "e6806ae0"
ADAPTER_AUTHORITY_AUTHORIZATION = "092dbce5"
ORDERED_CHAIN_AUTHORIZATION = "fe595535"
MEDIA_RESUME_AUTHORIZATION = "2c2df4c3"
REPLACEMENT_MEDIA_AUTHORIZATION = "41d41b70"
RECORDED_ON = "2026-08-17"
LINK_NUMBER = 113
SOURCE_STATIC = LINK.BASE.SOURCE_MANIFEST.parents[1]
SOURCE_PROFILE = LINK.BASE.PROFILE
_CONFIGURE_CALLS = 0
_ORIGINAL_CONFIGURE_STAGES = PIPE.PIPE.configure_stages


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
    text = " ".join(raw.decode().lower().replace("*", "").split())
    for token in ("tainted finals persist", "configure_consumption()",
                  "46,043", "exactly one new final link",
                  "completion, media and the poison-regression d2"):
        require(token in text, f"Completion/media authority absent: {token}")
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
    text = " ".join(raw.decode().lower().replace("*", "").split())
    for token in ("completion repeat authorized",
                  "exact sha-bound authority file",
                  "real seven-configurator closure",
                  "fresh-process preflight", "one completion repeat"):
        require(token in text, f"Completion-retry authority absent: {token}")
    return {"authority": "git-blob", "commit": full, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def final_resume_authorization() -> dict[str, Any]:
    name = PLAN.relative_to(ROOT).as_posix()
    full = subprocess.run(
        ["git", "rev-parse", f"{FINAL_RESUME_AUTHORIZATION}^{{commit}}"],
        cwd=ROOT, check=True, text=True,
        stdout=subprocess.PIPE).stdout.strip()
    raw = subprocess.run(
        ["git", "show", f"{full}:{name}"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE).stdout
    text = " ".join(raw.decode().lower().replace("*", "").split())
    for token in ("adapter-owner fix and one resume authorized",
                  "correct adapter owner", "every completion adapter",
                  "95 inventoried partials", "exactly one resume"):
        require(token in text, f"Completion final-resume authority absent: {token}")
    return {"authority": "git-blob", "commit": full, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def adapter_authority_authorization() -> dict[str, Any]:
    name = PLAN.relative_to(ROOT).as_posix()
    full = subprocess.run(
        ["git", "rev-parse", f"{ADAPTER_AUTHORITY_AUTHORIZATION}^{{commit}}"],
        cwd=ROOT, check=True, text=True,
        stdout=subprocess.PIPE).stdout.strip()
    raw = subprocess.run(
        ["git", "show", f"{full}:{name}"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE).stdout
    text = " ".join(raw.decode().lower().replace("*", "").split())
    for token in ("golden projection into the adapter namespace",
                  "actually consuming nested adapter namespace",
                  "both preflight and completion bind",
                  "any adapter consuming a golden outside",
                  "exactly one resume"):
        require(token in text,
                f"adapter-Golden resume authority absent: {token}")
    return {"authority": "git-blob", "commit": full, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def ordered_chain_authorization() -> dict[str, Any]:
    name = PLAN.relative_to(ROOT).as_posix()
    full = subprocess.run(
        ["git", "rev-parse", f"{ORDERED_CHAIN_AUTHORIZATION}^{{commit}}"],
        cwd=ROOT, check=True, text=True,
        stdout=subprocess.PIPE).stdout.strip()
    raw = subprocess.run(
        ["git", "show", f"{full}:{name}"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE).stdout
    text = " ".join(raw.decode().lower().replace("*", "").split())
    for token in ("kernal publisher joins the chain",
                  "ordered adapter", "complete adapter chain",
                  "producer is absent or late", "110 partials",
                  "exactly one resume"):
        require(token in text, f"ordered-chain authority absent: {token}")
    return {"authority": "git-blob", "commit": full, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def media_resume_authorization() -> dict[str, Any]:
    """Bind the owner-approved receipt-primary, media-only continuation."""
    name = PLAN.relative_to(ROOT).as_posix()
    full = subprocess.run(
        ["git", "rev-parse", f"{MEDIA_RESUME_AUTHORIZATION}^{{commit}}"],
        cwd=ROOT, check=True, text=True,
        stdout=subprocess.PIPE).stdout.strip()
    raw = subprocess.run(
        ["git", "show", f"{full}:{name}"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE).stdout
    text = " ".join(raw.decode().lower().replace("*", "").split())
    for token in (
            "media consumer disposition",
            "consumes the green post-completion receipt read-only after identity check",
            "13-section candidate projection",
            "ambient fallback dies with a mutation",
            "completion does not run again",
            "21 base-media partials", "one media resume"):
        require(token in text, f"media-resume authority absent: {token}")
    return {"authority": "git-blob", "commit": full, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def replacement_media_authorization() -> dict[str, Any]:
    """Bind the one owner-authorized replacement media resume."""
    name = PLAN.relative_to(ROOT).as_posix()
    full = subprocess.run(
        ["git", "rev-parse",
         f"{REPLACEMENT_MEDIA_AUTHORIZATION}^{{commit}}"],
        cwd=ROOT, check=True, text=True,
        stdout=subprocess.PIPE).stdout.strip()
    raw = subprocess.run(
        ["git", "show", f"{full}:{name}"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE).stdout
    text = " ".join(raw.decode().lower().replace("*", "").split())
    for token in (
            "manifest joins the output closure",
            "every producer-owned output enumerated",
            "sibling artifacts included",
            "mutation for an output outside the enumeration",
            "preflight checks the real lifecycle",
            "exactly that partial discards controlled",
            "one replacement media resume"):
        require(token in text,
                f"replacement-media authority absent: {token}")
    return {"authority": "git-blob", "commit": full, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def acceptance_authority() -> dict[str, Any]:
    value = load(ACCEPTANCE)
    acceptance = value.get("acceptance", {})
    require(
        value.get("status") == ACCEPT.STATUS
        and value.get("execution_accounting") == {
            "new_WPLTO_card_runs": 0, "new_materializations": 0,
            "final_product_links": 0, "qualification_runs": 1,
            "completion_runs": 0, "media_builds": 0,
            "device_contacts": 0}
        and value.get("final_artifacts_before") ==
            value.get("final_artifacts_after")
        and acceptance.get("delivered_bytes", {}).get("status") ==
            "DEFERRED-UNTIL-PUBLISH-LAST-COMPLETION"
        and acceptance.get("VMA_golden", {}).get("dependent_fixed_vmas") == 101
        and acceptance.get("VMA_golden", {}).get(
            "dependent_free_derived_vmas") == 2
        and acceptance.get("far_payload", {}).get(
            "candidate_derived_bytes") == 1248
        and acceptance.get("far_payload", {}).get(
            "candidate_headroom_bytes") == 251
        and value.get("structural_absence", {}).get(
            "unsafe_content_DMA_count") == 0,
        "green configurator-parity Acceptance absent")
    for name, fact in value["final_artifacts_before"].items():
        require(fact == bind(ROOT / fact["path"]),
                f"frozen configurator-parity final drift: {name}")
    return value


def frozen_artifacts() -> dict[str, dict[str, Any]]:
    return deepcopy(acceptance_authority()["final_artifacts_before"])


def card_projection() -> dict[str, Any]:
    value = acceptance_authority()
    return {
        "status": "PASS: configurator-parity Acceptance projected read-only",
        "attempt_accounting": {"cards_authorized": 0, "cards_consumed": 0,
            "device_contacts": 0, "product_link_attempts": 0,
            "wplto_runs": 0, "artifact_replays": 1},
        "acceptance": value["acceptance"],
        "artifacts": value["final_artifacts_before"],
        "authority": {"configurator_parity_acceptance": bind(ACCEPTANCE)},
    }


def projection_sources() -> dict[str, dict[str, Any]]:
    rows = {
        "profile": SOURCE_PROFILE,
        "bank2_static_code": SOURCE_STATIC / "v6-semantics/bank2-static-code.bin",
        "initial_c2d": SOURCE_STATIC / "v6-semantics/initial.c2d-v6.bin",
        "product_identity": SOURCE_STATIC / "product/substitution-artifacts.json",
        "product_shelf": SOURCE_STATIC / "product/product-shelf-v4-direct.bin",
        "static_plane_authority": LINK.BASE.SOURCE_WPLTO.parent /
            "receipts/defstruct-static-plane-authority.json",
    }
    value = {name: bind(path) for name, path in rows.items()}
    require(value["bank2_static_code"]["bytes"] == 46043
            and value["initial_c2d"]["bytes"] == 33840,
            "bound Completion materialization truth drift")
    return value


def prepare_completion_inputs() -> dict[str, Any]:
    """Project immutable materialization inputs; never alter linked finals."""
    before = frozen_artifacts()
    projected = projection_sources()
    static_target = TARGET / "static-plane/narrow-static"
    if not static_target.exists():
        static_target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(SOURCE_STATIC, static_target)
    profile_target = WPLTO / "resolved-profile.txt"
    if not profile_target.exists():
        shutil.copyfile(SOURCE_PROFILE, profile_target)
    prelink = WPLTO / "fresh-c2-lite-prelink-gates/v6-semantics"
    prelink.mkdir(parents=True, exist_ok=True)
    for name in ("bank2-static-code.bin", "initial.c2d-v6.bin"):
        target = prelink / name
        source = SOURCE_STATIC / "v6-semantics" / name
        if not target.exists():
            shutil.copyfile(source, target)
        require(target.read_bytes() == source.read_bytes(),
                f"Completion projection differs from bound truth: {name}")
    authority_target = TARGET / "receipts/defstruct-static-plane-authority.json"
    authority_source = ROOT / projected["static_plane_authority"]["path"]
    authority_target.parent.mkdir(parents=True, exist_ok=True)
    if not authority_target.exists():
        shutil.copyfile(authority_source, authority_target)
    require(profile_target.read_bytes() == SOURCE_PROFILE.read_bytes()
            and authority_target.read_bytes() == authority_source.read_bytes()
            and bind(static_target / "product/substitution-artifacts.json") ==
                {**projected["product_identity"],
                 "path": (static_target / "product/substitution-artifacts.json")
                    .relative_to(ROOT).as_posix()}
            and frozen_artifacts() == before,
            "Completion input projection changed identity or linked finals")
    return {"status": "PASS: immutable Completion inputs projected",
            "inputs": projected, "linked_finals_unchanged": True,
            "static_plane_authority_projection": bind(authority_target),
            "materialization_runs": 0}


def configure_current_candidate() -> tuple[dict[str, Path], Any]:
    """Run the exact seven-configurator closure over the current target."""
    global _CONFIGURE_CALLS
    require(_CONFIGURE_CALLS == 0,
            "current Completion candidate configured twice in one process")
    _CONFIGURE_CALLS += 1
    prepare_completion_inputs()
    continuation = LINK.BASE.PREVIOUS
    continuation.BUILD = TARGET
    old, paths = continuation.configure_candidate()
    canonical_product = LINK.CANONICAL
    canonical_product.REPLAY.PROFILE.configure()
    canonical_product.REPLAY.BANK2.configure_bank2_stage()
    canonical_product.REPLAY.TWO.configure_two_region()
    canonical_product.REPLAY.LINK60.configure_current_pin_adapters()
    PRODUCT.configure_intern_session_service()
    header = LINK.HEADER.configure_consumption()
    require(
        paths["build"] == TARGET and paths["wplto"] == WPLTO
        and paths["final"] == FINAL
        and paths["static"] == TARGET / "static-plane/narrow-static"
        and header["bytes"] == 293
        and PRODUCT.COMPILER_CONSUMED_STATIC_CODE_BYTES == 46043
        and PRODUCT.CONVERGENCE_DEFINES == (
            "LISP65_CODE_WINDOW_CONVERGENCE",
            "LISP65_DMA_CONTENT_CONVERGENCE",
            "LISP65_C2_ASM_CONVERGENCE",
            "LISP65_C2_FULL_SPAN_CONVERGENCE",
            "LISP65_C2_MUTABLE_CPU_READS"),
        "Completion configurator closure differs from linked candidate")
    # ``old`` belongs to the fresh child and is intentionally not restored;
    # Completion consumes the configured state in that same process.
    del old
    return paths, canonical_product


def project_candidate_golden_to_adapters(elf: Path) -> dict[str, Any]:
    """Bind the accepted Golden in the namespaces adapters really consume."""
    SOURCE_MEDIA.FLOW.BASE.INV = PIPE.GOLD
    SOURCE_MEDIA.card_projection = card_projection
    CRC_MEDIA.INV = PIPE.GOLD
    observed = PIPE.GOLD.compare_elf(elf)
    expected = acceptance_authority()["acceptance"]["VMA_golden"]
    require(
        SOURCE_MEDIA.FLOW.BASE.INV is PIPE.GOLD
        and CRC_MEDIA.INV is PIPE.GOLD
        and observed == expected
        and observed["dependent_fixed_vmas"] == 101
        and observed["dependent_free_derived_vmas"] == 2
        and observed["mapped_far_service_capacity"][
            "candidate_headroom_bytes"] == 251,
        "candidate Golden did not reach an actual adapter consumer")
    return {
        "status": "PASS: candidate Golden projected to adapter consumers",
        "golden_module": PIPE.GOLD.__name__,
        "consumers": {
            "fixed_adapter": "SOURCE_MEDIA.FLOW.BASE.INV",
            "facade_adapter": "CRC_MEDIA.INV"},
        "consumer_count": 2,
        "candidate_golden": bind(PIPE.GOLD.GOLDEN),
        "candidate_acceptance": bind(ACCEPTANCE),
        "comparison": observed,
    }


def completion_adapter_preflight(paths: dict[str, Path], can: Any) -> dict[str, Any]:
    """Execute every Completion adapter against an owned scratch product."""
    require(not ADAPTER_PREFLIGHT_ROOT.exists(),
            "Completion adapter preflight target pre-exists")
    before = frozen_artifacts()
    ADAPTER_PREFLIGHT_ROOT.mkdir()
    product = ADAPTER_PREFLIGHT_ROOT / LINK.FINAL.name
    for source in LINK.BASE.family(LINK.FINAL):
        shutil.copyfile(source, ADAPTER_PREFLIGHT_ROOT / source.name)
    header_source = WPLTO / "c2-kernal-window.generated.h"
    header = ADAPTER_PREFLIGHT_ROOT / header_source.name
    require(header_source.is_file(), "candidate KERNAL header input absent")
    shutil.copyfile(header_source, header)
    original_fixed = PRODUCT.FIXED_BLOCK_LEAF.audit_elf
    original_facade = PRODUCT.fixed_facade_gate
    elf = Path(str(product) + ".elf")
    order: list[str] = []
    facade = CRC_MEDIA._current_facade_gate(
        original_facade, ADAPTER_PREFLIGHT_ROOT, product,
        "completion-adapter-preflight")
    order.append("facade-gate")
    fixed = SOURCE_MEDIA._link105_fixed_audit(
        original_fixed, elf,
        out=ADAPTER_PREFLIGHT_ROOT / "fixed-adapter.json",
        require_hot_bss=True, full_map_ownership=True)
    order.append("fixed-audit")
    boot = PRODUCT.overlay_pack_family(
        ADAPTER_PREFLIGHT_ROOT, product, SOURCE_PROFILE, "boot", "unbound")
    order.append("boot-overlay-producer")
    session = PRODUCT.overlay_pack_family(
        ADAPTER_PREFLIGHT_ROOT, product, SOURCE_PROFILE, "session", "unbound")
    order.append("session-overlay-producer")
    scratch_before = product.read_bytes()
    window = PRODUCT.publish_kernal_window_binding(
        ADAPTER_PREFLIGHT_ROOT, product)
    order.append("kernal-window-publisher")
    published = PRODUCT.patch_verifier_binding_table(
        ADAPTER_PREFLIGHT_ROOT, product, boot[1], session[1],
        expected_base=PRODUCT.LINK60_VERIFIER_BINDING_BASE)
    order.append("runtime-binding-publisher")
    total = PRODUCT.total_publish_last_gate(
        ADAPTER_PREFLIGHT_ROOT, product, window, published,
        expected_verifier_base=PRODUCT.LINK60_VERIFIER_BINDING_BASE)
    order.append("total-publish-consumer")
    scratch_after = product.read_bytes()
    require(
        fixed.get("status") ==
            "passed-fixed-block-rtov-fail-identity-and-fixed-target"
        and facade.get("status") == "passed"
        and published.get("status") == "passed"
        and published.get("bytes") == 40
        and window.get("status") == "passed"
        and window.get("single_product_link_window", {}).get("bytes") == 8192
        and total.get("status") == "passed"
        and order.index("kernal-window-publisher") <
            order.index("total-publish-consumer")
        and order.index("runtime-binding-publisher") <
            order.index("total-publish-consumer")
        and scratch_before != scratch_after
        and frozen_artifacts() == before
        and paths["wplto"] == WPLTO and can.WPLTO == WPLTO,
        "real Completion adapter preflight red")
    return {
        "status": "PASS: every Completion adapter executed on scratch",
        "pid": os.getpid(),
        "adapters": {
            "fixed": {"owner": "c2_v20_source_oracle_media",
                "reference": "_link105_fixed_audit",
                "result": fixed["status"],
                "receipt": bind(ADAPTER_PREFLIGHT_ROOT / "fixed-adapter.json")},
            "facade": {"owner": "c2_v20_crc_carveout_media",
                "reference": "_current_facade_gate",
                "result": facade["status"],
                "receipt": bind(ADAPTER_PREFLIGHT_ROOT /
                    "fixed-host-facade-completion-adapter-preflight.json")},
            "publish_last": {"owner": "c2_product_substitution_link",
                "reference": "patch_verifier_binding_table",
                "result": published["status"],
                "receipt": bind(ADAPTER_PREFLIGHT_ROOT /
                    "runtime-verifier-publish-last.json")},
            "kernal_publish_last": {
                "owner": "c2_product_substitution_link",
                "reference": "publish_kernal_window_binding",
                "result": window["status"],
                "receipt": bind(ADAPTER_PREFLIGHT_ROOT /
                    "kernal-window-publish-last.json")},
            "total_publish_last": {
                "owner": "c2_product_substitution_link",
                "reference": "total_publish_last_gate",
                "result": total["status"],
                "receipt": bind(ADAPTER_PREFLIGHT_ROOT /
                    "total-publish-last-domain.json")}},
        "adapter_count": 5,
        "ordered_chain": order,
        "producer_before_consumer": True,
        "kernal_header_input": bind(header),
        "scratch_product_before_sha256": hashlib.sha256(
            scratch_before).hexdigest(),
        "scratch_product_after_sha256": hashlib.sha256(
            scratch_after).hexdigest(),
        "scratch_only": True, "frozen_finals_unchanged": True,
    }


def partial_completion_inventory() -> dict[str, Any]:
    """Bind every partial produced by the consumed Completion retry."""
    require(FINAL.is_dir(), "partial Completion directory absent")
    rows = [bind(path) for path in sorted(FINAL.rglob("*"))
            if path.is_file() and not path.is_symlink()]
    return {"files": len(rows), "rows": rows,
            "inventory_sha256": hashlib.sha256(canonical(rows)).hexdigest()}


def discard_partial_completion() -> dict[str, Any]:
    """Discard only the exact inventoried Red partials, once and loudly."""
    require(not CLEANUP_RECEIPT.exists()
            and RESUME_RED.is_file() and CONFIGURATOR_PREFLIGHT.is_file()
            and not ADAPTER_PREFLIGHT_ROOT.exists()
            and not (RECEIPTS / "artifact-completion.json").exists()
            and not (FINAL / "runtime-verifier-publish-last.json").exists()
            and not PIPELINE_RECEIPT.exists()
            and not BASE_BUILD.exists() and not LIVE_BUILD.exists()
            and not FAR_BUILD.exists(),
            "controlled partial-Completion cleanup lifecycle drift")
    red = load(RESUME_RED)
    observed = partial_completion_inventory()
    expected = red["partial_completion"]
    require(
        red.get("status") ==
            "RESUME RED: COMPLETION ADAPTER RETURNS TO OWNER"
        and observed["files"] == expected["files"] == 95
        and observed["inventory_sha256"] ==
            expected["inventory_sha256"] ==
            "3fe82a4332cac43294deaf2d29e8588c651a3a73b2bf0dc9e442ee533944e20a"
        and red["frozen_finals_before"] == red["frozen_finals_after"]
        and frozen_artifacts() == red["frozen_finals_before"],
        "partial Completion inventory differs from bound Red evidence")
    prior_preflight = bind(CONFIGURATOR_PREFLIGHT)
    frozen_before = frozen_artifacts()
    shutil.rmtree(FINAL)
    CONFIGURATOR_PREFLIGHT.unlink()
    require(not FINAL.exists() and not CONFIGURATOR_PREFLIGHT.exists()
            and frozen_artifacts() == frozen_before,
            "controlled partial-Completion cleanup incomplete")
    value = {
        "format": "lisp65-c2.3-v2.1-partial-completion-cleanup-v1",
        "recorded_on": RECORDED_ON,
        "status": "PASS: 95 bound Completion partials discarded once",
        "discarded": observed,
        "prior_configurator_preflight": prior_preflight,
        "postcondition": {"final_directory_absent": True,
            "configurator_preflight_absent": True,
            "publish_last_writes": 0, "artifact_completion_receipts": 0,
            "media_builds": 0},
        "frozen_finals_before": frozen_before,
        "frozen_finals_after": frozen_artifacts(),
        "execution_accounting": {"files_discarded": 95,
            "completion_resumes": 0, "WPLTO_runs": 0,
            "product_links": 0, "cards": 0, "device_contacts": 0},
        "authority": {"owner": final_resume_authorization(),
            "resume_red": bind(RESUME_RED), "driver": bind(DRIVER)},
        "claim_limit": (
            "Only the exact SHA-bound 95-file Red inventory and its stale "
            "preflight receipt were removed. Accepted linked finals remain "
            "immutable; Completion has not resumed yet."),
    }
    CLEANUP_RECEIPT.write_bytes(canonical(value))
    return value


def discard_ordered_chain_partials() -> dict[str, Any]:
    """Discard the exact 110-file chain-order Red inventory once."""
    require(not ORDERED_CHAIN_CLEANUP_RECEIPT.exists()
            and ADAPTER_AUTHORITY_RESUME_RED.is_file()
            and CONFIGURATOR_PREFLIGHT.is_file() and FINAL.is_dir()
            and FAILED_ADAPTER_PREFLIGHT_ROOT.is_dir()
            and FAILED_GOLDEN_PREFLIGHT_ROOT.is_dir()
            and not ADAPTER_PREFLIGHT_ROOT.exists()
            and (FINAL / "runtime-verifier-publish-last.json").is_file()
            and not (FINAL / "kernal-window-publish-last.json").exists()
            and not (RECEIPTS / "artifact-completion.json").exists()
            and not PIPELINE_RECEIPT.exists()
            and not BASE_BUILD.exists() and not LIVE_BUILD.exists()
            and not FAR_BUILD.exists(),
            "ordered-chain partial cleanup lifecycle drift")
    red = load(ADAPTER_AUTHORITY_RESUME_RED)
    observed = partial_completion_inventory()
    require(
        red.get("status") ==
            "ADAPTER AUTHORITY RESUME RED: RETURNS TO OWNER"
        and observed["files"] == red["partial_outputs"]["files"] == 110
        and observed["inventory_sha256"] ==
            red["partial_outputs"]["inventory_sha256"] ==
            "208a56d10df0e6610e7832e7edca83b3f6bcb6861044887eda1d53a0e22839cc"
        and frozen_artifacts() == red["frozen_finals_before"] ==
            red["frozen_finals_after"],
        "ordered-chain partial inventory differs from bound Red")
    prior_preflight = bind(CONFIGURATOR_PREFLIGHT)
    frozen_before = frozen_artifacts()
    shutil.rmtree(FINAL)
    CONFIGURATOR_PREFLIGHT.unlink()
    require(not FINAL.exists() and not CONFIGURATOR_PREFLIGHT.exists()
            and frozen_artifacts() == frozen_before,
            "ordered-chain controlled cleanup incomplete")
    value = {
        "format": "lisp65-c2.3-v2.1-ordered-chain-cleanup-v1",
        "recorded_on": RECORDED_ON,
        "status": "PASS: 110 bound Completion partials discarded once",
        "discarded": observed,
        "prior_configurator_preflight": prior_preflight,
        "preserved_red_scratch": {
            "adapter_owner": bind(FAILED_ADAPTER_PREFLIGHT_ROOT /
                (LINK.FINAL.name + ".elf")),
            "candidate_golden": bind(FAILED_GOLDEN_PREFLIGHT_ROOT /
                (LINK.FINAL.name + ".elf"))},
        "postcondition": {"final_directory_absent": True,
            "configurator_preflight_absent": True,
            "artifact_completion_receipts": 0, "media_builds": 0},
        "frozen_finals_before": frozen_before,
        "frozen_finals_after": frozen_artifacts(),
        "execution_accounting": {"files_discarded": 110,
            "ordered_chain_resumes": 0, "WPLTO_runs": 0,
            "product_links": 0, "cards": 0, "device_contacts": 0},
        "authority": {"owner": ordered_chain_authorization(),
            "predecessor_red": bind(ADAPTER_AUTHORITY_RESUME_RED),
            "driver": bind(DRIVER)},
        "claim_limit": (
            "Only the exact 110-file failed Completion tree and its stale "
            "preflight receipt were removed. Both prior scratch evidence "
            "trees and all accepted linked finals remain immutable."),
    }
    ORDERED_CHAIN_CLEANUP_RECEIPT.write_bytes(canonical(value))
    return value


def base_media_partial_inventory() -> dict[str, Any]:
    """Bind the failed base-medium tree and its separately written session."""
    require(BASE_BUILD.is_dir() and BASE_SESSION.is_file(),
            "partial base-medium outputs are absent")
    rows = [bind(path) for path in sorted(BASE_BUILD.rglob("*"))
            if path.is_file() and not path.is_symlink()]
    return {"files": len(rows), "rows": rows,
            "inventory_sha256": hashlib.sha256(canonical(rows)).hexdigest(),
            "session": bind(BASE_SESSION)}


def completed_final_inventory() -> dict[str, Any]:
    """Bind every completed artifact without deriving any delivery truth."""
    require(FINAL.is_dir(), "completed final directory absent")
    rows = [bind(path) for path in sorted(FINAL.rglob("*"))
            if path.is_file() and not path.is_symlink()]
    return {"files": len(rows), "rows": rows,
            "inventory_sha256": hashlib.sha256(canonical(rows)).hexdigest()}


def discard_partial_base_media() -> dict[str, Any]:
    """Discard exactly the bound 21-file media Red and its partial session."""
    require(not MEDIA_CLEANUP_RECEIPT.exists()
            and ORDERED_CHAIN_RESUME_RED.is_file()
            and POST_COMPLETION.is_file()
            and (RECEIPTS / "artifact-completion.json").is_file()
            and BASE_BUILD.is_dir() and BASE_SESSION.is_file()
            and not BASE_RECEIPT.exists()
            and not LIVE_BUILD.exists() and not LIVE_RECEIPT.exists()
            and not LIVE_SESSION.exists()
            and not FAR_BUILD.exists() and not FAR_RECEIPT.exists()
            and not FAR_SESSION.exists() and not PIPELINE_RECEIPT.exists()
            and not RECEIPT.exists() and not MEDIA_PREFLIGHT.exists(),
            "controlled base-media cleanup lifecycle drift")
    red = load(ORDERED_CHAIN_RESUME_RED)
    observed = base_media_partial_inventory()
    expected = red["resume_progress"]["partial_base_media"]
    require(
        red.get("status") == "ORDERED CHAIN RESUME RED: RETURNS TO OWNER"
        and observed["files"] == expected["files"] == 21
        and observed["inventory_sha256"] ==
            expected["inventory_sha256"] ==
            "d4ba75f1794002c0c897ef55674e83c9296b56a3a8d3db6d16e5c1261e6a400e"
        and observed["session"] == red["resume_progress"][
            "session_config_partial"]
        and red["frozen_finals_before"] == red["frozen_finals_after"]
        and frozen_artifacts() == red["frozen_finals_before"],
        "partial base-media inventory differs from bound Red evidence")
    completion_before = bind(RECEIPTS / "artifact-completion.json")
    post_before = bind(POST_COMPLETION)
    finals_before = completed_final_inventory()
    frozen_before = frozen_artifacts()
    shutil.rmtree(BASE_BUILD)
    BASE_SESSION.unlink()
    require(not BASE_BUILD.exists() and not BASE_SESSION.exists()
            and bind(RECEIPTS / "artifact-completion.json") == completion_before
            and bind(POST_COMPLETION) == post_before
            and completed_final_inventory() == finals_before
            and frozen_artifacts() == frozen_before,
            "controlled base-media cleanup changed completed evidence")
    value = {
        "format": "lisp65-c2.3-v2.1-base-media-cleanup-v1",
        "recorded_on": RECORDED_ON,
        "status": "PASS: 21 bound base-media partials discarded once",
        "discarded": observed,
        "preserved": {"artifact_completion": completion_before,
            "post_completion": post_before, "completed_finals": finals_before},
        "postcondition": {"base_build_absent": True,
            "base_session_absent": True, "base_receipt_absent": True,
            "completion_reruns": 0, "media_resumes": 0},
        "frozen_finals_before": frozen_before,
        "frozen_finals_after": frozen_artifacts(),
        "execution_accounting": {"files_discarded": 21,
            "session_files_discarded": 1, "artifact_completions": 0,
            "media_resumes": 0, "WPLTO_runs": 0, "product_links": 0,
            "cards": 0, "device_contacts": 0},
        "authority": {"owner": media_resume_authorization(),
            "predecessor_red": bind(ORDERED_CHAIN_RESUME_RED),
            "driver": bind(DRIVER)},
        "claim_limit": (
            "Only the exact SHA-bound 21-file base-media Red tree and its "
            "bound partial session were removed. Completion, completed "
            "finals and WPLTO inputs remain byteidentical and unreadmitted."),
    }
    MEDIA_CLEANUP_RECEIPT.write_bytes(canonical(value))
    return value


def post_completion_identity() -> dict[str, Any]:
    """Read and identity-check the sole post-Completion delivery truth."""
    post = load(POST_COMPLETION)
    completion = load(RECEIPTS / "artifact-completion.json")
    delta = post.get("delta", {})
    delivered = delta.get("delivered_bytes", {})
    publish = delivered.get("publish_last", {})
    require(
        post.get("status") == "PASS: Completion and delivered bytes exact"
        and post.get("completion") == bind(
            RECEIPTS / "artifact-completion.json")
        and completion.get("status") ==
            "passed-no-relink-publish-last-artifact-completion"
        and completion.get("compiler_runs") == completion.get("linker_runs") == 0
        and completion.get("product") == bind(FINAL / LINK.FINAL.name)
        and completion.get("elf") == bind(
            FINAL / (LINK.FINAL.name + ".elf"))
        and delta.get("completed_PRG") == bind(FINAL / LINK.FINAL.name)
        and delivered.get("candidate_elf") == bind(
            FINAL / (LINK.FINAL.name + ".elf"))
        and delivered.get("completed_resident_prg") == bind(
            FINAL / LINK.FINAL.name)
        and delivered.get("identity_mismatches") == 0
        and publish.get("independent_crc16") == "0x1da1"
        and publish.get("independent_window_bytes") == 8192
        and publish.get("independent_window_sha256") == bind(
            FINAL / "c2-product-kernal-window.bin")["sha256"]
        and publish.get("values_correct") is True,
        "green post-Completion identity or delivery truth drift")
    return post


def media_preflight_child() -> int:
    """Validate the 13-section candidate projection in a fresh process."""
    require(MEDIA_CLEANUP_RECEIPT.is_file() and POST_COMPLETION.is_file()
            and not MEDIA_PREFLIGHT.exists()
            and not BASE_BUILD.exists() and not BASE_RECEIPT.exists()
            and not BASE_SESSION.exists() and not LIVE_BUILD.exists()
            and not FAR_BUILD.exists() and not PIPELINE_RECEIPT.exists(),
            "media preflight lifecycle drift")
    before = completed_final_inventory()
    frozen_before = frozen_artifacts()
    post = post_completion_identity()
    paths, _can = configure_current_candidate()
    sections = list(PRODUCT.KERNAL_SECTIONS)
    extras = load(ORDERED_CHAIN_RESUME_RED)["attribution"]["proof"][
        "configured_extra_sections"]
    publish = post["delta"]["delivered_bytes"]["publish_last"]
    require(
        paths["final"] == FINAL and paths["wplto"] == WPLTO
        and len(sections) == 13 and len(set(sections)) == 13
        and all(name in sections for name in extras)
        and bind(FINAL / "c2-product-kernal-window.bin")["sha256"] ==
            publish["independent_window_sha256"]
        and completed_final_inventory() == before
        and frozen_artifacts() == frozen_before,
        "13-section candidate projection does not validate Completion truth")
    value = {
        "format": "lisp65-c2.3-v2.1-media-consumer-preflight-v1",
        "recorded_on": RECORDED_ON,
        "status": "PASS: green Completion receipt validates against 13-section candidate projection",
        "pid": os.getpid(), "section_count": len(sections),
        "sections": sections, "configured_extra_sections": extras,
        "window": bind(FINAL / "c2-product-kernal-window.bin"),
        "expected_crc16": publish["independent_crc16"],
        "post_completion": bind(POST_COMPLETION),
        "artifact_completion": bind(RECEIPTS / "artifact-completion.json"),
        "completed_finals_before": before,
        "completed_finals_after": completed_final_inventory(),
        "frozen_finals_before": frozen_before,
        "frozen_finals_after": frozen_artifacts(),
        "execution_accounting": {"artifact_completions": 0,
            "WPLTO_runs": 0, "product_links": 0, "media_builds": 0,
            "device_contacts": 0},
        "authority": {"owner": media_resume_authorization(),
            "cleanup": bind(MEDIA_CLEANUP_RECEIPT), "driver": bind(DRIVER)},
    }
    MEDIA_PREFLIGHT.write_bytes(canonical(value))
    print("configurator parity media: PREFLIGHT PASS sections=13 receipt=primary")
    return 0


def media_preflight() -> dict[str, Any]:
    """Run and bind the real candidate projection outside the media process."""
    require(not MEDIA_PREFLIGHT.exists(), "media preflight is one-shot")
    environment = os.environ.copy()
    environment.update(
        PIPE.PIPE.FLOW.BASE.PRODUCER.BASE.L95.CAN.canonical_build_environment())
    result = subprocess.run(
        [sys.executable, str(DRIVER), "_media_preflight"], cwd=ROOT,
        env=environment, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, check=False)
    require(result.returncode == 0,
            "fresh-process media preflight red:\n" + result.stdout)
    value = load(MEDIA_PREFLIGHT)
    require(
        value.get("status") ==
            "PASS: green Completion receipt validates against 13-section candidate projection"
        and value.get("pid") != os.getpid()
        and value.get("section_count") == 13
        and value.get("expected_crc16") == "0x1da1"
        and value.get("post_completion") == bind(POST_COMPLETION)
        and value.get("artifact_completion") == bind(
            RECEIPTS / "artifact-completion.json")
        and value.get("completed_finals_before") ==
            value.get("completed_finals_after")
        and value.get("frozen_finals_before") ==
            value.get("frozen_finals_after"),
        "persisted media preflight drift")
    return value


def validate_base_output_closure(
        producer: dict[str, Path], enumerated: dict[str, Path]) -> None:
    """Require enumeration parity for every Base producer-owned output."""
    roles = {"build_tree", "product_manifest", "session", "receipt"}
    require(set(producer) == set(enumerated) == roles
            and producer == enumerated
            and enumerated["product_manifest"].parent == TARGET
            and BASE_BUILD not in enumerated["product_manifest"].parents,
            "Base producer output exists outside the enumerated closure")


def base_output_closure() -> dict[str, Any]:
    """Bind the actual Base producer registry, including sibling outputs."""
    patched_configure_stages()
    PIPE.PIPE.FLOW.configure_base()
    base = PIPE.PIPE.FLOW.BASE
    producer = base.producer_owned_outputs()
    enumerated = {"build_tree": BASE_BUILD,
        "product_manifest": TARGET / "canonical-product-manifest.json",
        "session": BASE_SESSION, "receipt": BASE_RECEIPT}
    validate_base_output_closure(producer, enumerated)
    return {"status": "PASS: every Base producer output enumerated",
            "roles": {name: path.relative_to(ROOT).as_posix()
                      for name, path in enumerated.items()},
            "role_count": len(enumerated), "sibling_outputs": 1}


def base_output_closure_mutations() -> list[str]:
    producer = {"build_tree": BASE_BUILD,
        "product_manifest": TARGET / "canonical-product-manifest.json",
        "session": BASE_SESSION, "receipt": BASE_RECEIPT}
    cases = {
        "producer-output-outside-enumeration": (
            {**producer, "unregistered_sibling": TARGET / "extra.json"},
            producer),
        "enumeration-omits-sibling-manifest": (
            producer, {name: path for name, path in producer.items()
                       if name != "product_manifest"}),
        "manifest-hidden-inside-build-tree": (
            {**producer, "product_manifest": BASE_BUILD / "manifest.json"},
            {**producer, "product_manifest": BASE_BUILD / "manifest.json"}),
    }
    rejected: list[str] = []
    for name, (actual, enumerated) in cases.items():
        try:
            validate_base_output_closure(actual, enumerated)
        except MediaError:
            rejected.append(name)
    require(rejected == list(cases),
            f"Base output-closure mutation survived: {rejected}")
    return rejected


def discard_external_manifest_partial() -> dict[str, Any]:
    """Discard only the exact sibling manifest bound by the consumed Red."""
    manifest = TARGET / "canonical-product-manifest.json"
    require(not MANIFEST_CLEANUP_RECEIPT.exists()
            and MEDIA_RESUME_RED.is_file()
            and MEDIA_RESUME_ATTRIBUTION.is_file()
            and MEDIA_CLEANUP_RECEIPT.is_file()
            and MEDIA_PREFLIGHT.is_file()
            and manifest.is_file() and not manifest.is_symlink()
            and not BASE_BUILD.exists() and not BASE_RECEIPT.exists()
            and not BASE_SESSION.exists() and not LIVE_BUILD.exists()
            and not FAR_BUILD.exists() and not PIPELINE_RECEIPT.exists()
            and not RECEIPT.exists()
            and not REPLACEMENT_MEDIA_PREFLIGHT.exists(),
            "external-manifest cleanup lifecycle drift")
    attribution = load(MEDIA_RESUME_ATTRIBUTION)
    observed = bind(manifest)
    require(
        attribution.get("status") ==
            "MEDIA RESUME RED ATTRIBUTED: UNENUMERATED EXTERNAL BASE-MEDIA PARTIAL"
        and observed == attribution["attribution"]["unclaimed_partial"]
        and observed["sha256"] ==
            "529f92aad5972d53ca9b3085e1849a66cc342f9776749697a77b83fc2df8e602",
        "external manifest differs from bound media-resume Red")
    completion_before = bind(RECEIPTS / "artifact-completion.json")
    post_before = bind(POST_COMPLETION)
    completed_before = completed_final_inventory()
    frozen_before = frozen_artifacts()
    manifest.unlink()
    require(not manifest.exists()
            and bind(RECEIPTS / "artifact-completion.json") == completion_before
            and bind(POST_COMPLETION) == post_before
            and completed_final_inventory() == completed_before
            and frozen_artifacts() == frozen_before,
            "external-manifest cleanup changed completed evidence")
    value = {
        "format": "lisp65-c2.3-v2.1-external-manifest-cleanup-v1",
        "recorded_on": RECORDED_ON,
        "status": "PASS: exact external Base manifest partial discarded once",
        "discarded": observed,
        "output_closure": {"roles": 4, "sibling_outputs": 1,
            "mutations_rejected": base_output_closure_mutations()},
        "preserved": {"artifact_completion": completion_before,
            "post_completion": post_before,
            "completed_finals": completed_before},
        "postcondition": {"manifest_absent": True,
            "all_base_outputs_absent": True,
            "completion_reruns": 0, "replacement_media_resumes": 0},
        "frozen_finals_before": frozen_before,
        "frozen_finals_after": frozen_artifacts(),
        "execution_accounting": {"files_discarded": 1,
            "artifact_completions": 0, "media_resumes": 0,
            "WPLTO_runs": 0, "product_links": 0, "cards": 0,
            "device_contacts": 0},
        "authority": {"owner": replacement_media_authorization(),
            "media_resume_red": bind(MEDIA_RESUME_RED),
            "attribution": bind(MEDIA_RESUME_ATTRIBUTION),
            "driver": bind(DRIVER)},
        "claim_limit": (
            "Only the one SHA-bound external Base manifest partial was "
            "removed. Completion and every linked/completed artifact remain "
            "byteidentical; the replacement media resume has not run."),
    }
    MANIFEST_CLEANUP_RECEIPT.write_bytes(canonical(value))
    return value


def replacement_media_preflight_child() -> int:
    """Run the exact Base lifecycle predicate before the replacement run."""
    require(MANIFEST_CLEANUP_RECEIPT.is_file()
            and not REPLACEMENT_MEDIA_PREFLIGHT.exists()
            and not (TARGET / "canonical-product-manifest.json").exists()
            and not BASE_BUILD.exists() and not BASE_RECEIPT.exists()
            and not BASE_SESSION.exists() and not LIVE_BUILD.exists()
            and not FAR_BUILD.exists() and not PIPELINE_RECEIPT.exists(),
            "replacement-media preflight lifecycle drift")
    before = completed_final_inventory()
    frozen_before = frozen_artifacts()
    post = post_completion_identity()
    configure()
    closure = base_output_closure()
    mutations = base_output_closure_mutations()
    base = PIPE.PIPE.FLOW.BASE
    lifecycle = base.require_clean_build_lifecycle()
    paths, _can = configure_current_candidate()
    sections = list(PRODUCT.KERNAL_SECTIONS)
    publish = post["delta"]["delivered_bytes"]["publish_last"]
    require(paths["final"] == FINAL and paths["wplto"] == WPLTO
            and len(sections) == 13 and len(set(sections)) == 13
            and bind(FINAL / "c2-product-kernal-window.bin")["sha256"] ==
                publish["independent_window_sha256"]
            and completed_final_inventory() == before
            and frozen_artifacts() == frozen_before,
            "replacement-media real lifecycle/candidate preflight red")
    value = {
        "format": "lisp65-c2.3-v2.1-replacement-media-preflight-v1",
        "recorded_on": RECORDED_ON,
        "status": "PASS: real Base lifecycle clean and 13-section receipt authority valid",
        "pid": os.getpid(), "real_lifecycle": lifecycle,
        "output_closure": closure,
        "output_closure_mutations_rejected": mutations,
        "section_count": len(sections), "sections": sections,
        "window": bind(FINAL / "c2-product-kernal-window.bin"),
        "expected_crc16": publish["independent_crc16"],
        "post_completion": bind(POST_COMPLETION),
        "artifact_completion": bind(RECEIPTS / "artifact-completion.json"),
        "completed_finals_before": before,
        "completed_finals_after": completed_final_inventory(),
        "frozen_finals_before": frozen_before,
        "frozen_finals_after": frozen_artifacts(),
        "execution_accounting": {"artifact_completions": 0,
            "WPLTO_runs": 0, "product_links": 0, "media_builds": 0,
            "device_contacts": 0},
        "authority": {"owner": replacement_media_authorization(),
            "manifest_cleanup": bind(MANIFEST_CLEANUP_RECEIPT),
            "driver": bind(DRIVER)},
    }
    REPLACEMENT_MEDIA_PREFLIGHT.write_bytes(canonical(value))
    print("configurator parity media: REPLACEMENT PREFLIGHT PASS lifecycle=real outputs=4")
    return 0


def replacement_media_preflight() -> dict[str, Any]:
    require(not REPLACEMENT_MEDIA_PREFLIGHT.exists(),
            "replacement-media preflight is one-shot")
    environment = os.environ.copy()
    environment.update(
        PIPE.PIPE.FLOW.BASE.PRODUCER.BASE.L95.CAN.canonical_build_environment())
    result = subprocess.run(
        [sys.executable, str(DRIVER), "_replacement_media_preflight"],
        cwd=ROOT, env=environment, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, check=False)
    require(result.returncode == 0,
            "fresh-process replacement-media preflight red:\n" +
            result.stdout)
    value = load(REPLACEMENT_MEDIA_PREFLIGHT)
    require(
        value.get("status") ==
            "PASS: real Base lifecycle clean and 13-section receipt authority valid"
        and value.get("pid") != os.getpid()
        and value.get("section_count") == 13
        and value.get("expected_crc16") == "0x1da1"
        and value.get("output_closure", {}).get("role_count") == 4
        and value.get("output_closure", {}).get("sibling_outputs") == 1
        and len(value.get("output_closure_mutations_rejected", [])) == 3
        and value.get("post_completion") == bind(POST_COMPLETION)
        and value.get("artifact_completion") == bind(
            RECEIPTS / "artifact-completion.json")
        and value.get("completed_finals_before") ==
            value.get("completed_finals_after")
        and value.get("frozen_finals_before") ==
            value.get("frozen_finals_after"),
        "persisted replacement-media preflight drift")
    return value


def receipt_completion_delta() -> dict[str, Any]:
    """Consume persisted Completion truth; never derive it from ambient state."""
    preflight = load(REPLACEMENT_MEDIA_PREFLIGHT)
    post = post_completion_identity()
    require(
        preflight.get("section_count") == 13
        and preflight.get("post_completion") == bind(POST_COMPLETION)
        and preflight.get("artifact_completion") == bind(
            RECEIPTS / "artifact-completion.json")
        and preflight.get("window") == bind(
            FINAL / "c2-product-kernal-window.bin"),
        "media consumer lacks the bound 13-section validation authority")
    delta = deepcopy(post["delta"])
    delta["truth_source"] = "read-only-green-post-completion-receipt"
    delta["truth_receipt"] = bind(POST_COMPLETION)
    delta["candidate_projection"] = bind(MEDIA_PREFLIGHT)
    return delta


def configurator_preflight_child() -> int:
    """Exercise the real configured consumer in its own process."""
    require(FIRST_RED.is_file() and RESUME_RED.is_file()
            and FINAL_RESUME_RED.is_file() and CLEANUP_RECEIPT.is_file()
            and FAILED_ADAPTER_PREFLIGHT_ROOT.is_dir()
            and ADAPTER_AUTHORITY_RESUME_RED.is_file()
            and ORDERED_CHAIN_CLEANUP_RECEIPT.is_file()
            and FAILED_GOLDEN_PREFLIGHT_ROOT.is_dir()
            and not CONFIGURATOR_PREFLIGHT.exists() and not FINAL.exists(),
            "Completion configurator preflight lifecycle drift")
    before = frozen_artifacts()
    projection = prepare_completion_inputs()
    paths, can = configure_current_candidate()
    adapter_authority = project_candidate_golden_to_adapters(
        WPLTO / (LINK.FINAL.name + ".elf"))
    persisted = load(LINK.RECEIPT)["configurator_projection"]
    closure = persisted["continuation_configurators"]
    names = [row["name"] for row in closure]
    artifacts = load(LINK.BASE.SOURCE_MANIFEST)
    actual = LINK.state(artifacts)
    adapters = completion_adapter_preflight(paths, can)
    require(
        len(closure) == 7
        and names == [
            "product-candidate-chain", "complete-profile", "bank2-stage",
            "two-region", "current-pin-adapters", "intern-session-service",
            "static-header-consumption"]
        and actual == persisted["final_state"]
        and PRODUCT.COMPILER_CONSUMED_STATIC_CODE_BYTES == 46043
        and paths["wplto"] == WPLTO and paths["final"] == FINAL
        and frozen_artifacts() == before and not FINAL.exists(),
        "fresh-process Completion configurator parity red")
    value = {
        "format": "lisp65-c2.3-v2.1-completion-configurator-preflight-v1",
        "recorded_on": RECORDED_ON,
        "status": "PASS: real seven-configurator Completion preflight",
        "pid": os.getpid(), "configurator_count": 7,
        "configurators": names, "final_state": actual,
        "static_header_consumed_bytes": 46043,
        "completion_adapters": adapters,
        "completion_adapter_authority": adapter_authority,
        "input_projection": projection,
        "frozen_finals_before": before,
        "frozen_finals_after": frozen_artifacts(),
        "execution_accounting": {"WPLTO_runs": 0, "product_links": 0,
            "complete_artifacts_calls": 0, "media_builds": 0,
            "device_contacts": 0},
        "authority": {"owner": ordered_chain_authorization(),
            "prior_adapter_authority_owner":
                adapter_authority_authorization(),
            "prior_final_resume_owner": final_resume_authorization(),
            "prior_retry_owner": resume_authorization(),
            "cleanup": bind(CLEANUP_RECEIPT),
            "adapter_authority_red": bind(FINAL_RESUME_RED),
            "ordered_chain_red": bind(ADAPTER_AUTHORITY_RESUME_RED),
            "ordered_chain_cleanup": bind(ORDERED_CHAIN_CLEANUP_RECEIPT),
            "first_red": bind(FIRST_RED), "final_link": bind(LINK.RECEIPT),
            "driver": bind(DRIVER)},
    }
    CONFIGURATOR_PREFLIGHT.write_bytes(canonical(value))
    print("configurator parity Completion: PREFLIGHT PASS configurators=7")
    return 0


def configurator_preflight() -> dict[str, Any]:
    require(not CONFIGURATOR_PREFLIGHT.exists(),
            "Completion configurator preflight is one-shot")
    environment = os.environ.copy()
    environment.update(
        PIPE.PIPE.FLOW.BASE.PRODUCER.BASE.L95.CAN.canonical_build_environment())
    result = subprocess.run(
        [sys.executable, str(DRIVER), "_config_preflight"], cwd=ROOT,
        env=environment, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, check=False)
    require(result.returncode == 0,
            "fresh-process Completion configurator preflight red:\n" +
            result.stdout)
    value = load(CONFIGURATOR_PREFLIGHT)
    require(value.get("status") ==
            "PASS: real seven-configurator Completion preflight"
            and value.get("configurator_count") == 7
            and value.get("static_header_consumed_bytes") == 46043
            and value.get("completion_adapters", {}).get("adapter_count") == 5
            and value["completion_adapters"].get("scratch_only") is True
            and value["completion_adapters"].get(
                "producer_before_consumer") is True
            and value.get("completion_adapter_authority", {}).get(
                "consumer_count") == 2
            and value["completion_adapter_authority"].get("comparison") ==
                acceptance_authority()["acceptance"]["VMA_golden"]
            and value.get("pid") != os.getpid()
            and value["frozen_finals_before"] ==
                value["frozen_finals_after"],
            "persisted Completion configurator preflight drift")
    return value


def completion_delta() -> dict[str, Any]:
    wplto = WPLTO / LINK.FINAL.name
    final = FINAL / LINK.FINAL.name
    elf = Path(str(final) + ".elf")
    before = (FINAL / "lisp65-c2-substitution-unbound.prg").read_bytes()
    after = final.read_bytes()
    require(len(before) == len(after), "Completion changed PRG length")
    load_address = int.from_bytes(before[:2], "little")
    truth = SOURCE_MEDIA.FLOW.BASE.ElfTruth.read(
        elf, llvm_readobj=ROOT / "tools/llvm-mos/bin/llvm-readobj")
    binding = truth.section(".lisp65_runtime_overlay_verifier_bindings")
    allowed = set(range(binding.address, binding.address + binding.bytes))
    allowed.update(CRC.CARVEOUT)
    changed = {load_address + offset - 2
               for offset, (left, right) in enumerate(zip(before, after))
               if offset >= 2 and left != right}
    require(changed <= allowed and set(CRC.CARVEOUT) <= changed,
            "Completion escaped publish-last domains")
    delivery = CRC.delivered_bytes_gate(elf, final)
    require(delivery["identity_mismatches"] == 0
            and delivery["publish_last"]["addresses"] == list(CRC.CARVEOUT)
            and delivery["publish_last"]["values_correct"] is True,
            "post-Completion delivered bytes are not value/identity exact")
    require(wplto.read_bytes() == before
            and frozen_artifacts() == acceptance_authority()[
                "final_artifacts_before"],
            "Completion changed frozen linked inputs")
    return {"status": "PASS: domain-aware publish-last Completion",
            "changed_addresses": len(changed), "changes_outside_domain": 0,
            "runtime_binding": {"address": binding.address,
                                "bytes": binding.bytes},
            "CRC_operands": list(CRC.CARVEOUT),
            "delivered_bytes": delivery,
            "frozen_WPLTO_PRG": bind(wplto), "completed_PRG": bind(final)}


def complete_child() -> int:
    preflight = load(CONFIGURATOR_PREFLIGHT)
    require(preflight.get("status") ==
            "PASS: real seven-configurator Completion preflight"
            and preflight.get("pid") != os.getpid()
            and preflight.get("configurator_count") == 7
            and preflight.get("completion_adapters", {}).get(
                "adapter_count") == 5
            and {name: row.get("result") for name, row in
                 preflight["completion_adapters"]["adapters"].items()} == {
                    "fixed":
                        "passed-fixed-block-rtov-fail-identity-and-fixed-target",
                    "facade": "passed", "publish_last": "passed",
                    "kernal_publish_last": "passed",
                    "total_publish_last": "passed"}
            and preflight["completion_adapters"].get(
                "producer_before_consumer") is True,
            "Completion did not follow an isolated configurator preflight")
    require(CLEANUP_RECEIPT.is_file() and RESUME_RED.is_file()
            and FINAL_RESUME_RED.is_file()
            and ADAPTER_AUTHORITY_RESUME_RED.is_file()
            and ORDERED_CHAIN_CLEANUP_RECEIPT.is_file()
            and load(CLEANUP_RECEIPT).get("status") ==
                "PASS: 95 bound Completion partials discarded once"
            and load(ORDERED_CHAIN_CLEANUP_RECEIPT).get("status") ==
                "PASS: 110 bound Completion partials discarded once",
            "Completion did not follow controlled partial cleanup")
    paths, can = configure_current_candidate()
    adapter_authority = project_candidate_golden_to_adapters(
        WPLTO / (LINK.FINAL.name + ".elf"))
    require(adapter_authority == preflight["completion_adapter_authority"],
            "Completion adapter Golden differs from fresh preflight")
    require(not FINAL.exists() and not (TARGET / "canonical-product-manifest.json").exists(),
            "configurator-parity Completion is one-shot")
    replay = can.REPLAY
    original_configure = replay.configure
    original_fixed = PRODUCT.FIXED_BLOCK_LEAF.audit_elf
    original_facade = PRODUCT.fixed_facade_gate
    original_verify = can.verify_published_verifier_binding

    def configured_geometry() -> None:
        require(PRODUCT.COMPILER_CONSUMED_STATIC_CODE_BYTES == 46043,
                "Completion lost candidate header consumption")

    def fixed_adapter(elf: Path, *, out: Path | None = None,
                      require_hot_bss: bool = True,
                      full_map_ownership: bool = False) -> dict[str, Any]:
        return SOURCE_MEDIA._link105_fixed_audit(
            original_fixed, elf, out=out,
            require_hot_bss=require_hot_bss,
            full_map_ownership=full_map_ownership)

    def facade_adapter(out: Path, target: Path,
                       suffix: str) -> dict[str, Any]:
        return CRC_MEDIA._current_facade_gate(
            original_facade, out, target, suffix)

    def publish_binding(product: Path, boot_manifest: Path,
                        session_manifest: Path) -> dict[str, Any]:
        window = PRODUCT.publish_kernal_window_binding(can.FINAL, product)
        require(window.get("status") == "passed"
                and (can.FINAL / "kernal-window-publish-last.json").is_file(),
                "KERNAL publisher did not precede its Completion consumer")
        return PRODUCT.patch_verifier_binding_table(
            can.FINAL, product, boot_manifest, session_manifest,
            expected_base=PRODUCT.LINK60_VERIFIER_BINDING_BASE)

    PRODUCT.PRODUCT_ARTIFACTS_MANIFEST = (
        paths["static_product"] / "substitution-artifacts.json")
    replay.configure = configured_geometry
    PRODUCT.FIXED_BLOCK_LEAF.audit_elf = fixed_adapter
    PRODUCT.fixed_facade_gate = facade_adapter
    can.verify_published_verifier_binding = publish_binding
    try:
        completion = can.complete_artifacts()
    finally:
        replay.configure = original_configure
        PRODUCT.FIXED_BLOCK_LEAF.audit_elf = original_fixed
        PRODUCT.fixed_facade_gate = original_facade
        can.verify_published_verifier_binding = original_verify
    require(completion["status"] ==
            "passed-no-relink-publish-last-artifact-completion"
            and completion["compiler_runs"] == completion["linker_runs"] == 0,
            "configurator-parity Completion red")
    delta = completion_delta()
    POST_COMPLETION.write_bytes(canonical({
        "format": "lisp65-c2.3-v2.1-configurator-parity-post-completion-v1",
        "recorded_on": RECORDED_ON,
        "status": "PASS: Completion and delivered bytes exact",
        "authority": {"owner": authorization(),
            "resume_owner": resume_authorization(),
            "final_resume_owner": final_resume_authorization(),
            "adapter_authority_owner": adapter_authority_authorization(),
            "ordered_chain_owner": ordered_chain_authorization(),
            "resume_red": bind(RESUME_RED),
            "adapter_authority_red": bind(FINAL_RESUME_RED),
            "ordered_chain_red": bind(ADAPTER_AUTHORITY_RESUME_RED),
            "ordered_chain_cleanup": bind(ORDERED_CHAIN_CLEANUP_RECEIPT),
            "cleanup": bind(CLEANUP_RECEIPT),
            "acceptance": bind(ACCEPTANCE),
            "configurator_preflight": bind(CONFIGURATOR_PREFLIGHT),
            "driver": bind(DRIVER)},
        "completion": bind(RECEIPTS / "artifact-completion.json"),
        "delta": delta,
        "execution_accounting": {"WPLTO_runs": 0, "product_links": 0,
            "artifact_completions": 1, "media_builds": 0,
            "device_contacts": 0}}))
    print("configurator parity Completion: PASS compiler=0 linker=0 CRC=value-exact")
    return 0


def patched_configure_stages() -> None:
    _ORIGINAL_CONFIGURE_STAGES()
    PIPE.PIPE.FLOW.BASE.configure_candidate = configure_current_candidate
    PIPE.PIPE.FLOW.BASE.completion_delta = receipt_completion_delta
    PIPE.PIPE.complete_child = complete_child


def source_gate(source_override: str | None = None) -> dict[str, Any]:
    source = DRIVER.read_text(encoding="utf-8") if source_override is None else source_override
    tree = ast.parse(source)
    functions = {node.name: node for node in tree.body
                 if isinstance(node, ast.FunctionDef)}
    required = ("complete_child", "configure_current_candidate",
                "configurator_preflight_child", "configurator_preflight",
                "completion_adapter_preflight",
                "project_candidate_golden_to_adapters", "configure",
                "prepare_completion_inputs", "discard_partial_completion",
                "discard_ordered_chain_partials",
                "build")
    require(all(name in functions for name in required),
            "Completion/media lifecycle function absent")
    exercised = "\n".join(ast.unparse(functions[name]) for name in required)
    preflight_call_lines = {
        ast.unparse(node.func): node.lineno
        for node in ast.walk(functions["completion_adapter_preflight"])
        if isinstance(node, ast.Call)}
    complete_call_lines = {
        ast.unparse(node.func): node.lineno
        for node in ast.walk(functions["complete_child"])
        if isinstance(node, ast.Call)}
    calls = [ast.unparse(node.func) for name in required
             for node in ast.walk(functions[name]) if isinstance(node, ast.Call)]
    forbidden = ("run_wplto(", "single_link(", ".card(",
                 "produce_candidate(", "compile_link(")
    require(all(token not in exercised for token in forbidden)
            and calls.count("can.complete_artifacts") == 1
            and calls.count("prepare_completion_inputs") >= 3
            and calls.count("configurator_preflight") == 1
            and calls.count("PIPE.orchestrate") == 1
            and calls.count("SOURCE_MEDIA._link105_fixed_audit") == 2
            and calls.count("CRC_MEDIA._current_facade_gate") == 2
            and calls.count("PRODUCT.patch_verifier_binding_table") == 2
            and calls.count("PRODUCT.publish_kernal_window_binding") == 2
            and calls.count("PRODUCT.total_publish_last_gate") == 1
            and calls.count("project_candidate_golden_to_adapters") == 3
            and preflight_call_lines[
                "PRODUCT.publish_kernal_window_binding"] <
                preflight_call_lines["PRODUCT.patch_verifier_binding_table"] <
                preflight_call_lines["PRODUCT.total_publish_last_gate"]
            and complete_call_lines[
                "PRODUCT.publish_kernal_window_binding"] <
                complete_call_lines["PRODUCT.patch_verifier_binding_table"]
            and "SOURCE_MEDIA.FLOW.BASE.INV = PIPE.GOLD" in exercised
            and "CRC_MEDIA.INV = PIPE.GOLD" in exercised
            and "SOURCE_MEDIA._current_facade_gate" not in exercised,
            "Completion/media path can enter producer/link/card lifecycle")
    return {"status": "PASS: downstream-only Completion/media",
            "WPLTO_runs": 0, "product_links": 0, "cards": 0,
            "artifact_completions": 1,
            "completion_adapters": 5,
            "forbidden_calls": list(forbidden)}


def source_mutations() -> list[str]:
    source = DRIVER.read_text(encoding="utf-8")
    cases = {
        "reenter-link": source.replace(
            "        completion = can.complete_artifacts()\n",
            "        PRODUCT.single_link(WPLTO)\n"
            "        completion = can.complete_artifacts()\n", 1),
        "drop-completion": source.replace(
            "        completion = can.complete_artifacts()\n",
            "        completion = {}\n", 1),
        "drop-projection": source.replace(
            "    prepare_completion_inputs()\n", "", 1),
        "reenter-WPLTO": source.replace(
            "    result = PIPE.orchestrate()\n",
            "    run_wplto()\n    result = PIPE.orchestrate()\n", 1),
        "wrong-facade-owner": source.replace(
            "CRC_MEDIA._current_facade_gate(",
            "SOURCE_MEDIA._current_facade_gate(", 1),
        "ambient-adapter-golden": source.replace(
            "    SOURCE_MEDIA.FLOW.BASE.INV = PIPE.GOLD\n",
            "    SOURCE_MEDIA.INV = PIPE.GOLD\n", 1),
        "missing-kernal-producer": source.replace(
            "    window = PRODUCT.publish_kernal_window_binding(\n"
            "        ADAPTER_PREFLIGHT_ROOT, product)\n",
            "    window = {}\n", 1),
        "late-kernal-producer": source.replace(
            "    window = PRODUCT.publish_kernal_window_binding(\n"
            "        ADAPTER_PREFLIGHT_ROOT, product)\n",
            "    window = PRODUCT.publish_kernal_window_binding_late(\n"
            "        ADAPTER_PREFLIGHT_ROOT, product)\n", 1).replace(
            "    order.append(\"total-publish-consumer\")\n",
            "    order.append(\"total-publish-consumer\")\n"
            "    late_window = PRODUCT.publish_kernal_window_binding(\n"
            "        ADAPTER_PREFLIGHT_ROOT, product)\n", 1),
    }
    rejected: list[str] = []
    for name, candidate in cases.items():
        try:
            source_gate(candidate)
        except (MediaError, SyntaxError):
            rejected.append(name)
    require(rejected == list(cases),
            f"Completion/media source mutation survived: {rejected}")
    return rejected


def media_resume_source_gate(source_override: str | None = None) -> dict[str, Any]:
    """Prove that the authorized path is media-only and receipt-primary."""
    source = (DRIVER.read_text(encoding="utf-8")
              if source_override is None else source_override)
    tree = ast.parse(source)
    functions = {node.name: node for node in tree.body
                 if isinstance(node, ast.FunctionDef)}
    names = ("media_resume", "receipt_completion_delta",
             "post_completion_identity", "media_preflight_child",
             "media_preflight", "discard_partial_base_media")
    require(all(name in functions for name in names),
            "receipt-primary media lifecycle function absent")
    exercised = "\n".join(ast.unparse(functions[name]) for name in names)
    calls = [ast.unparse(node.func) for name in names
             for node in ast.walk(functions[name])
             if isinstance(node, ast.Call)]
    forbidden = {"complete_child", "can.complete_artifacts",
                 "CRC.delivered_bytes_gate", "completion_delta",
                 "PRODUCT.single_link", "run_wplto"}
    pipeline_source = Path(PIPE.__file__).read_text(encoding="utf-8")
    pipeline_tree = ast.parse(pipeline_source)
    pipeline_orchestrate = next(
        node for node in pipeline_tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "orchestrate")
    pipeline_actions = [
        node.args[0].value for node in ast.walk(pipeline_orchestrate)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name) and node.func.id == "run_child"
        and node.args and isinstance(node.args[0], ast.Constant)
        and isinstance(node.args[0].value, str)]
    require(
        not (set(calls) & forbidden)
        and calls.count("PIPE.orchestrate") == 1
        and calls.count("discard_partial_base_media") == 1
        and calls.count("media_preflight") == 1
        and calls.count("load") >= 4
        and calls.count("post_completion_identity") == 3
        and calls.count("configure_current_candidate") == 1
        and len(pipeline_actions) == 9
        and set(pipeline_actions) == {
            "_base", "_rebind_base", "_base_check", "_liveness",
            "_rebind_liveness", "_liveness_check", "_finalize_far",
            "_far", "_far_check"}
        and "delta = deepcopy(post['delta'])" in exercised
        and "preflight.get('section_count') == 13" in exercised,
        "media resume can rerun Completion or consume ambient delivery truth")
    return {"status": "PASS: receipt-primary media-only resume",
            "post_completion_receipts": 1,
            "candidate_projection_sections": 13,
            "artifact_completions_this_resume": 0,
            "media_resumes": 1,
            "pipeline_completion_actions": 0,
            "forbidden_calls_absent": sorted(forbidden)}


def media_resume_source_mutations() -> list[str]:
    source = DRIVER.read_text(encoding="utf-8")
    cases = {
        "ambient-delivered-byte-fallback": source.replace(
            "    delta = deepcopy(post[\"delta\"])\n",
            "    delta = CRC.delivered_bytes_gate(\n"
            "        FINAL / (LINK.FINAL.name + \".elf\"),\n"
            "        FINAL / LINK.FINAL.name)\n", 1),
        "rerun-completion": source.replace(
            "    preflight = media_preflight()\n"
            "    configure()\n"
            "    result = PIPE.orchestrate()\n",
            "    preflight = media_preflight()\n"
            "    configure()\n"
            "    complete_child()\n"
            "    result = PIPE.orchestrate()\n", 1),
        "drop-identity-check": source.replace(
            "    preflight = load(REPLACEMENT_MEDIA_PREFLIGHT)\n"
            "    post = post_completion_identity()\n",
            "    preflight = load(REPLACEMENT_MEDIA_PREFLIGHT)\n"
            "    post = load(POST_COMPLETION)\n", 1),
        "accept-ten-section-ambient": source.replace(
            "preflight.get(\"section_count\") == 13\n",
            "preflight.get(\"section_count\") == 10\n", 1),
        "skip-controlled-cleanup": source.replace(
            "    cleanup = discard_partial_base_media()\n", "", 1),
    }
    rejected: list[str] = []
    for name, candidate in cases.items():
        try:
            media_resume_source_gate(candidate)
        except (MediaError, SyntaxError):
            rejected.append(name)
    require(rejected == list(cases),
            f"media-resume source mutation survived: {rejected}")
    return rejected


def replacement_media_source_gate(
        source_override: str | None = None) -> dict[str, Any]:
    """Prove output-complete, real-lifecycle, media-only replacement flow."""
    source = (DRIVER.read_text(encoding="utf-8")
              if source_override is None else source_override)
    tree = ast.parse(source)
    functions = {node.name: node for node in tree.body
                 if isinstance(node, ast.FunctionDef)}
    names = ("replacement_media_resume", "replacement_media_preflight_child",
             "replacement_media_preflight", "discard_external_manifest_partial",
             "base_output_closure", "receipt_completion_delta")
    require(all(name in functions for name in names),
            "replacement-media lifecycle function absent")
    exercised = "\n".join(ast.unparse(functions[name]) for name in names)
    calls = [ast.unparse(node.func) for name in names
             for node in ast.walk(functions[name])
             if isinstance(node, ast.Call)]
    forbidden = {"complete_child", "can.complete_artifacts",
                 "CRC.delivered_bytes_gate", "completion_delta",
                 "PRODUCT.single_link", "run_wplto"}
    closure = functions["base_output_closure"]
    enumerated = next(
        node.value for node in ast.walk(closure)
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "enumerated"
                for target in node.targets))
    require(isinstance(enumerated, ast.Dict),
            "Base output enumeration is not an explicit typed registry")
    output_roles = {
        key.value for key in enumerated.keys
        if isinstance(key, ast.Constant) and isinstance(key.value, str)}
    base_source = Path(PIPE.PIPE.FLOW.BASE.__file__).read_text(encoding="utf-8")
    base_tree = ast.parse(base_source)
    base_functions = {node.name: node for node in base_tree.body
                      if isinstance(node, ast.FunctionDef)}
    build_calls = [ast.unparse(node.func)
                   for node in ast.walk(base_functions["build_action"])
                   if isinstance(node, ast.Call)]
    pipeline_source = Path(PIPE.__file__).read_text(encoding="utf-8")
    pipeline_tree = ast.parse(pipeline_source)
    pipeline_orchestrate = next(
        node for node in pipeline_tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "orchestrate")
    pipeline_actions = [
        node.args[0].value for node in ast.walk(pipeline_orchestrate)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name) and node.func.id == "run_child"
        and node.args and isinstance(node.args[0], ast.Constant)
        and isinstance(node.args[0].value, str)]
    require(
        not (set(calls) & forbidden)
        and calls.count("PIPE.orchestrate") == 1
        and calls.count("discard_external_manifest_partial") == 1
        and calls.count("replacement_media_preflight") == 1
        and calls.count("base.require_clean_build_lifecycle") == 1
        and calls.count("base.producer_owned_outputs") == 1
        and calls.count("post_completion_identity") >= 2
        and build_calls.count("require_clean_build_lifecycle") == 1
        and output_roles == {
            "build_tree", "product_manifest", "session", "receipt"}
        and len(pipeline_actions) == 9
        and set(pipeline_actions) == {
            "_base", "_rebind_base", "_base_check", "_liveness",
            "_rebind_liveness", "_liveness_check", "_finalize_far",
            "_far", "_far_check"}
        and "delta = deepcopy(post['delta'])" in exercised
        and "preflight = load(REPLACEMENT_MEDIA_PREFLIGHT)" in exercised,
        "replacement media path loses output closure, real lifecycle, or receipt truth")
    return {"status": "PASS: output-complete replacement media-only resume",
            "producer_output_roles": sorted(output_roles),
            "producer_output_count": len(output_roles),
            "sibling_outputs": 1, "real_lifecycle_calls": 1,
            "artifact_completions_this_resume": 0,
            "replacement_media_resumes": 1,
            "pipeline_completion_actions": 0,
            "forbidden_calls_absent": sorted(forbidden)}


def replacement_media_source_mutations() -> list[str]:
    source = DRIVER.read_text(encoding="utf-8")
    cases = {
        "ambient-delivered-byte-fallback": source.replace(
            "    delta = deepcopy(post[\"delta\"])\n",
            "    delta = CRC.delivered_bytes_gate(\n"
            "        FINAL / (LINK.FINAL.name + \".elf\"),\n"
            "        FINAL / LINK.FINAL.name)\n", 1),
        "rerun-completion": source.replace(
            "    preflight = replacement_media_preflight()\n"
            "    configure()\n"
            "    result = PIPE.orchestrate()\n",
            "    preflight = replacement_media_preflight()\n"
            "    configure()\n"
            "    complete_child()\n"
            "    result = PIPE.orchestrate()\n", 1),
        "skip-external-manifest-cleanup": source.replace(
            "    cleanup = discard_external_manifest_partial()\n", "", 1),
        "substitute-real-lifecycle": source.replace(
            "    lifecycle = base.require_clean_build_lifecycle()\n",
            "    lifecycle = {}\n", 1),
        "omit-sibling-output": source.replace(
            "        \"product_manifest\": TARGET / \"canonical-product-manifest.json\",\n"
            "        \"session\": BASE_SESSION, \"receipt\": BASE_RECEIPT}\n"
            "    validate_base_output_closure(producer, enumerated)\n",
            "        \"session\": BASE_SESSION, \"receipt\": BASE_RECEIPT}\n"
            "    validate_base_output_closure(producer, enumerated)\n", 1),
    }
    rejected: list[str] = []
    for name, candidate in cases.items():
        try:
            replacement_media_source_gate(candidate)
        except (MediaError, SyntaxError, StopIteration):
            rejected.append(name)
    require(rejected == list(cases),
            f"replacement-media source mutation survived: {rejected}")
    return rejected


def configure() -> None:
    PIPE.CARD_BUILD = TARGET
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
    PIPE.DRIVER = DRIVER
    PIPE.RECORDED_ON = RECORDED_ON
    PIPE.LINK = LINK_NUMBER
    PIPE.SIZE.RECEIPT = ACCEPTANCE
    PIPE.RESUME.RECEIPT = ACCEPTANCE
    PIPE.GOLD.RECEIPT = ACCEPTANCE
    PIPE.authorization = authorization
    PIPE.replay_authority = acceptance_authority
    PIPE.frozen_artifacts = frozen_artifacts
    PIPE.card_projection = card_projection
    PIPE.run_child = run_child
    PIPE.freight_source_gate = replacement_media_source_gate
    PIPE.freight_source_mutations = replacement_media_source_mutations
    PIPE.PIPE.configure_stages = patched_configure_stages
    PIPE.configure()
    PIPE.PIPE.complete_child = complete_child
    PIPE.PIPE.FLOW.BASE.configure_candidate = configure_current_candidate
    PIPE.PIPE.FLOW.BASE.completion_delta = receipt_completion_delta
    project_candidate_golden_to_adapters(
        WPLTO / (LINK.FINAL.name + ".elf"))


def run_child(action: str) -> None:
    environment = os.environ.copy()
    environment.update(
        PIPE.PIPE.FLOW.BASE.PRODUCER.BASE.L95.CAN.canonical_build_environment())
    result = subprocess.run(
        [sys.executable, str(DRIVER), action], cwd=ROOT, env=environment,
        text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        check=False)
    require(result.returncode == 0,
            f"configurator-parity child {action} red:\n{result.stdout}")


def child(action: str) -> int:
    configure()
    return PIPE.child(action)


def validate(value: dict[str, Any]) -> None:
    require(
        value.get("status") ==
            "PASS: configurator-parity Completion/media closed; D2 ready"
        and value.get("frozen_before") == frozen_artifacts()
        and value.get("frozen_after") == value["frozen_before"]
        and value.get("completion", {}).get("delta", {}).get(
            "changes_outside_domain") == 0
        and value["completion"]["delta"].get("truth_source") ==
            "read-only-green-post-completion-receipt"
        and value["completion"].get("mode") ==
            "consume-green-post-completion-receipt-read-only"
        and value["completion"]["delta"]["delivered_bytes"][
            "identity_mismatches"] == 0
        and value["completion"]["delta"]["delivered_bytes"][
            "publish_last"]["values_correct"] is True
        and value.get("media", {}).get("roles") == 19
        and value["media"].get("payload_bytes") == 1248
        and value["media"].get("candidate_headroom_bytes") == 251
        and value["media"].get("readback") == "byteidentical"
        and value["media"].get("same_world") is True
        and value.get("execution_accounting") == {
            "WPLTO_runs": 0, "product_links": 0, "cards": 0,
            "artifact_completions": 1, "shared_media_builds": 3,
            "library_builds": 1, "completion_repeats_authorized": 1,
            "completion_repeats_run": 1,
            "completion_resumes_authorized": 1,
            "completion_resumes_run": 1,
            "adapter_authority_resumes_authorized": 1,
            "adapter_authority_resumes_run": 1,
            "ordered_chain_resumes_authorized": 1,
            "ordered_chain_resumes_run": 1,
            "media_resumes_authorized": 2,
            "media_resumes_run": 2,
            "replacement_media_resumes_authorized": 1,
            "replacement_media_resumes_run": 1,
            "artifact_completions_this_resume": 0,
            "device_contacts": 0}
        and value.get("controlled_cleanup", {}).get(
            "discarded_files") == 95
        and value["controlled_cleanup"].get(
            "ordered_chain_discarded_files") == 110
        and value["controlled_cleanup"].get(
            "base_media_discarded_files") == 21
        and value["controlled_cleanup"].get(
            "base_media_session_discarded") is True
        and value["controlled_cleanup"].get(
            "external_manifest_discarded_files") == 1
        and value.get("configurator_preflight", {}).get(
            "completion_adapters") == 5
        and value["configurator_preflight"].get(
            "producer_before_consumer") is True
        and value["configurator_preflight"].get(
            "real_base_lifecycle") is True
        and value["configurator_preflight"].get(
            "base_output_roles") == 4
        and value["configurator_preflight"].get(
            "adapter_golden_consumers") == 2
        and value.get("hardware_handoff") == {
            "D2_poison_regression_ready": True,
            "D3_D5_open": False, "session": bind(FAR_SESSION)},
        "configurator-parity Completion/media summary drift")


def mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "claim-link": lambda x: x["execution_accounting"].update(
            product_links=1),
        "escape-Completion": lambda x: x["completion"]["delta"].update(
            changes_outside_domain=1),
        "bad-CRC": lambda x: x["completion"]["delta"]["delivered_bytes"]
            ["publish_last"].update(values_correct=False),
        "ambient-completion-truth": lambda x: x["completion"]["delta"].update(
            truth_source="ambient-recomputation"),
        "claim-completion-rerun": lambda x: x["execution_accounting"].update(
            artifact_completions_this_resume=1),
        "truncate-payload": lambda x: x["media"].update(payload_bytes=1247),
        "cross-world": lambda x: x["media"].update(same_world=False),
        "open-D3": lambda x: x["hardware_handoff"].update(D3_D5_open=True),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        trial = deepcopy(value); mutate(trial)
        try:
            validate(trial)
        except MediaError:
            rejected.append(name)
    require(rejected == list(cases), "Completion/media summary mutation survived")
    return rejected


def build(*, resume: bool = False,
          adapter_authority_resume: bool = False,
          ordered_chain_resume: bool = False) -> int:
    require(not RECEIPT.exists() and not PIPELINE_RECEIPT.exists(),
            "configurator-parity Completion/media is one-shot")
    require(FIRST_RED.is_file(), "authorized Completion First Red absent")
    acceptance_authority(); authorization(); resume_authorization()
    cleanup = None
    require(sum((resume, adapter_authority_resume, ordered_chain_resume)) <= 1,
            "Completion resume modes are mutually exclusive")
    if ordered_chain_resume:
        require(ADAPTER_AUTHORITY_RESUME_RED.is_file()
                and CLEANUP_RECEIPT.is_file()
                and FAILED_ADAPTER_PREFLIGHT_ROOT.is_dir()
                and FAILED_GOLDEN_PREFLIGHT_ROOT.is_dir()
                and not ADAPTER_PREFLIGHT_ROOT.exists()
                and FINAL.is_dir() and CONFIGURATOR_PREFLIGHT.is_file()
                and not ORDERED_CHAIN_CLEANUP_RECEIPT.exists(),
                "authorized ordered-chain resume state absent")
        ordered_chain_authorization()
        cleanup = discard_ordered_chain_partials()
    elif adapter_authority_resume:
        require(RESUME_RED.is_file() and FINAL_RESUME_RED.is_file()
                and CLEANUP_RECEIPT.is_file()
                and FAILED_ADAPTER_PREFLIGHT_ROOT.is_dir()
                and not ADAPTER_PREFLIGHT_ROOT.exists()
                and not FINAL.exists()
                and not CONFIGURATOR_PREFLIGHT.exists(),
                "authorized adapter-Golden resume state absent")
        adapter_authority_authorization()
        cleanup = load(CLEANUP_RECEIPT)
    elif resume:
        require(RESUME_RED.is_file() and FINAL.is_dir()
                and CONFIGURATOR_PREFLIGHT.is_file()
                and not CLEANUP_RECEIPT.exists(),
                "authorized Completion resume state absent")
        final_resume_authorization()
        cleanup = discard_partial_completion()
    else:
        require(not RESUME_RED.exists() and not FINAL.exists(),
                "initial Completion build cannot consume resume state")
    source_gate(); source_mutations()
    projection = prepare_completion_inputs()
    preflight = configurator_preflight()
    before = frozen_artifacts()
    configure()
    result = PIPE.orchestrate()
    require(result == 0, "configurator-parity Completion/media pipeline red")
    pipeline = load(PIPELINE_RECEIPT)
    delta = completion_delta()
    far = load(FAR_RECEIPT)
    value = {
        "format": "lisp65-c2.3-v2.1-configurator-parity-completion-media-v1",
        "recorded_on": RECORDED_ON,
        "status": "PASS: configurator-parity Completion/media closed; D2 ready",
        "authority": {"owner": authorization(),
            "resume_owner": resume_authorization(),
            "final_resume_owner": final_resume_authorization(),
            "adapter_authority_resume_owner":
                adapter_authority_authorization(),
            "ordered_chain_resume_owner": ordered_chain_authorization(),
            "acceptance": bind(ACCEPTANCE),
            "first_red": bind(FIRST_RED), "resume_red": bind(RESUME_RED),
            "adapter_authority_red": bind(FINAL_RESUME_RED),
            "ordered_chain_red": bind(ADAPTER_AUTHORITY_RESUME_RED),
            "cleanup": bind(CLEANUP_RECEIPT),
            "ordered_chain_cleanup": bind(ORDERED_CHAIN_CLEANUP_RECEIPT),
            "configurator_preflight": bind(CONFIGURATOR_PREFLIGHT),
            "pipeline": bind(PIPELINE_RECEIPT), "driver": bind(DRIVER)},
        "frozen_before": before, "frozen_after": frozen_artifacts(),
        "input_projection": projection,
        "configurator_preflight": {
            "receipt": bind(CONFIGURATOR_PREFLIGHT),
            "pid": preflight["pid"], "configurators": 7,
            "completion_adapters": preflight[
                "completion_adapters"]["adapter_count"],
            "adapter_golden_consumers": preflight[
                "completion_adapter_authority"]["consumer_count"],
            "producer_before_consumer": preflight[
                "completion_adapters"]["producer_before_consumer"],
            "completion_pid_distinct": True},
        "controlled_cleanup": {"receipt": bind(CLEANUP_RECEIPT),
            "discarded_files": load(CLEANUP_RECEIPT)["discarded"]["files"],
            "discarded_inventory_sha256": load(CLEANUP_RECEIPT)["discarded"][
                "inventory_sha256"],
            "ordered_chain_receipt": bind(ORDERED_CHAIN_CLEANUP_RECEIPT),
            "ordered_chain_discarded_files": cleanup["discarded"]["files"],
            "ordered_chain_inventory_sha256": cleanup["discarded"][
                "inventory_sha256"]},
        "completion": {"receipt": bind(
            RECEIPTS / "artifact-completion.json"), "delta": delta,
            "post_completion": bind(POST_COMPLETION)},
        "media": {"product_D81": bind(
                FAR_BUILD / "shared-system/lisp65-product.d81"),
            "library_D81": bind(BASE_BUILD / "library/lisp65-library.d81"),
            "roles": 19, "payload_bytes": far["materialization"][
                "payload_bytes"],
            "delivered_bytes": far["materialization"]["delivered_bytes"],
            "arena_capacity_bytes": 1499,
            "candidate_headroom_bytes": 251,
            "readback": "byteidentical", "same_world": True,
            "packed_gate_registry_complete": far[
                "packed_artifact_gate_registry"]["complete"]},
        "source_gate": source_gate(),
        "source_mutations_rejected": source_mutations(),
        "execution_accounting": {"WPLTO_runs": 0, "product_links": 0,
            "cards": 0, "artifact_completions": 1,
            "shared_media_builds": 3, "library_builds": 1,
            "completion_repeats_authorized": 1,
            "completion_repeats_run": 1,
            "completion_resumes_authorized": 1,
            "completion_resumes_run": 1,
            "adapter_authority_resumes_authorized": 1,
            "adapter_authority_resumes_run": 1,
            "ordered_chain_resumes_authorized": 1,
            "ordered_chain_resumes_run": 1,
            "device_contacts": 0},
        "hardware_handoff": {"D2_poison_regression_ready": True,
            "D3_D5_open": False, "session": bind(FAR_SESSION)},
        "claim_limit": (
            "Host Completion and same-world media only. D2 poison regression "
            "is ready but has not run; D3-D5 remain closed."),
    }
    validate(value)
    value["mutations_rejected"] = mutations(value)
    RECEIPT.write_bytes(canonical(value))
    print("configurator parity media: PASS Completion=1 roles=19 D2=ready")
    return 0


def media_resume() -> int:
    """Resume only media from the immutable green Completion receipt."""
    require(not RECEIPT.exists() and not PIPELINE_RECEIPT.exists()
            and not MEDIA_CLEANUP_RECEIPT.exists()
            and not MEDIA_PREFLIGHT.exists() and not MEDIA_RESUME_RED.exists()
            and ORDERED_CHAIN_RESUME_RED.is_file()
            and POST_COMPLETION.is_file()
            and (RECEIPTS / "artifact-completion.json").is_file()
            and FINAL.is_dir() and BASE_BUILD.is_dir()
            and BASE_SESSION.is_file() and not BASE_RECEIPT.exists()
            and not LIVE_BUILD.exists() and not LIVE_RECEIPT.exists()
            and not LIVE_SESSION.exists() and not FAR_BUILD.exists()
            and not FAR_RECEIPT.exists() and not FAR_SESSION.exists(),
            "authorized receipt-primary media-resume state absent")
    media_resume_authorization()
    media_resume_source_gate(); media_resume_source_mutations()
    post_completion_identity()
    completed_before = completed_final_inventory()
    completion_before = bind(RECEIPTS / "artifact-completion.json")
    post_before = bind(POST_COMPLETION)
    frozen_before = frozen_artifacts()
    cleanup = discard_partial_base_media()
    preflight = media_preflight()
    configure()
    result = PIPE.orchestrate()
    require(result == 0, "receipt-primary media pipeline red")
    require(
        bind(RECEIPTS / "artifact-completion.json") == completion_before
        and bind(POST_COMPLETION) == post_before
        and completed_final_inventory() == completed_before
        and frozen_artifacts() == frozen_before,
        "media resume changed Completion or accepted linked artifacts")
    pipeline = load(PIPELINE_RECEIPT)
    delta = receipt_completion_delta()
    far = load(FAR_RECEIPT)
    prior_cleanup = load(CLEANUP_RECEIPT)
    ordered_cleanup = load(ORDERED_CHAIN_CLEANUP_RECEIPT)
    value = {
        "format": "lisp65-c2.3-v2.1-configurator-parity-completion-media-v1",
        "recorded_on": RECORDED_ON,
        "status": "PASS: configurator-parity Completion/media closed; D2 ready",
        "authority": {"owner": authorization(),
            "resume_owner": resume_authorization(),
            "final_resume_owner": final_resume_authorization(),
            "adapter_authority_resume_owner":
                adapter_authority_authorization(),
            "ordered_chain_resume_owner": ordered_chain_authorization(),
            "media_resume_owner": media_resume_authorization(),
            "acceptance": bind(ACCEPTANCE),
            "first_red": bind(FIRST_RED), "resume_red": bind(RESUME_RED),
            "adapter_authority_red": bind(FINAL_RESUME_RED),
            "ordered_chain_red": bind(ADAPTER_AUTHORITY_RESUME_RED),
            "media_predecessor_red": bind(ORDERED_CHAIN_RESUME_RED),
            "cleanup": bind(CLEANUP_RECEIPT),
            "ordered_chain_cleanup": bind(ORDERED_CHAIN_CLEANUP_RECEIPT),
            "base_media_cleanup": bind(MEDIA_CLEANUP_RECEIPT),
            "configurator_preflight": bind(CONFIGURATOR_PREFLIGHT),
            "media_preflight": bind(MEDIA_PREFLIGHT),
            "pipeline": bind(PIPELINE_RECEIPT), "driver": bind(DRIVER)},
        "frozen_before": frozen_before, "frozen_after": frozen_artifacts(),
        "completed_finals_before": completed_before,
        "completed_finals_after": completed_final_inventory(),
        "input_projection": {"status":
            "PASS: 13-section candidate projection validates persisted truth",
            "receipt": bind(MEDIA_PREFLIGHT),
            "sections": preflight["section_count"],
            "post_completion": bind(POST_COMPLETION)},
        "configurator_preflight": {
            "receipt": bind(CONFIGURATOR_PREFLIGHT),
            "pid": load(CONFIGURATOR_PREFLIGHT)["pid"], "configurators": 7,
            "completion_adapters": load(CONFIGURATOR_PREFLIGHT)[
                "completion_adapters"]["adapter_count"],
            "adapter_golden_consumers": load(CONFIGURATOR_PREFLIGHT)[
                "completion_adapter_authority"]["consumer_count"],
            "producer_before_consumer": load(CONFIGURATOR_PREFLIGHT)[
                "completion_adapters"]["producer_before_consumer"],
            "completion_pid_distinct": True,
            "media_projection_pid": preflight["pid"],
            "media_projection_pid_distinct": True},
        "controlled_cleanup": {"receipt": bind(CLEANUP_RECEIPT),
            "discarded_files": prior_cleanup["discarded"]["files"],
            "discarded_inventory_sha256": prior_cleanup["discarded"][
                "inventory_sha256"],
            "ordered_chain_receipt": bind(ORDERED_CHAIN_CLEANUP_RECEIPT),
            "ordered_chain_discarded_files": ordered_cleanup["discarded"][
                "files"],
            "ordered_chain_inventory_sha256": ordered_cleanup["discarded"][
                "inventory_sha256"],
            "base_media_receipt": bind(MEDIA_CLEANUP_RECEIPT),
            "base_media_discarded_files": cleanup["discarded"]["files"],
            "base_media_inventory_sha256": cleanup["discarded"][
                "inventory_sha256"],
            "base_media_session_discarded": True},
        "completion": {"receipt": completion_before, "delta": delta,
            "post_completion": post_before,
            "mode": "consume-green-post-completion-receipt-read-only",
            "rerun": False},
        "media": {"product_D81": bind(
                FAR_BUILD / "shared-system/lisp65-product.d81"),
            "library_D81": bind(BASE_BUILD / "library/lisp65-library.d81"),
            "roles": 19, "payload_bytes": far["materialization"][
                "payload_bytes"],
            "delivered_bytes": far["materialization"]["delivered_bytes"],
            "arena_capacity_bytes": 1499,
            "candidate_headroom_bytes": 251,
            "readback": "byteidentical", "same_world": True,
            "packed_gate_registry_complete": far[
                "packed_artifact_gate_registry"]["complete"],
            "pipeline_status": pipeline["status"]},
        "source_gate": media_resume_source_gate(),
        "source_mutations_rejected": media_resume_source_mutations(),
        "execution_accounting": {"WPLTO_runs": 0, "product_links": 0,
            "cards": 0, "artifact_completions": 1,
            "shared_media_builds": 3, "library_builds": 1,
            "completion_repeats_authorized": 1,
            "completion_repeats_run": 1,
            "completion_resumes_authorized": 1,
            "completion_resumes_run": 1,
            "adapter_authority_resumes_authorized": 1,
            "adapter_authority_resumes_run": 1,
            "ordered_chain_resumes_authorized": 1,
            "ordered_chain_resumes_run": 1,
            "media_resumes_authorized": 1, "media_resumes_run": 1,
            "artifact_completions_this_resume": 0,
            "device_contacts": 0},
        "hardware_handoff": {"D2_poison_regression_ready": True,
            "D3_D5_open": False, "session": bind(FAR_SESSION)},
        "claim_limit": (
            "Host media-only resume from one read-only green Completion "
            "receipt. Completion did not rerun. D2 poison regression is "
            "ready but has not run; D3-D5 remain closed."),
    }
    validate(value)
    value["mutations_rejected"] = mutations(value)
    RECEIPT.write_bytes(canonical(value))
    print("configurator parity media: PASS receipt=primary Completion-reruns=0 roles=19 D2=ready")
    return 0


def replacement_media_resume() -> int:
    """Run the one replacement media resume behind complete output closure."""
    manifest = TARGET / "canonical-product-manifest.json"
    require(not RECEIPT.exists() and not PIPELINE_RECEIPT.exists()
            and not MANIFEST_CLEANUP_RECEIPT.exists()
            and not REPLACEMENT_MEDIA_PREFLIGHT.exists()
            and not REPLACEMENT_MEDIA_RESUME_RED.exists()
            and MEDIA_RESUME_RED.is_file()
            and MEDIA_RESUME_ATTRIBUTION.is_file()
            and MEDIA_CLEANUP_RECEIPT.is_file()
            and POST_COMPLETION.is_file()
            and (RECEIPTS / "artifact-completion.json").is_file()
            and FINAL.is_dir() and manifest.is_file()
            and not BASE_BUILD.exists() and not BASE_RECEIPT.exists()
            and not BASE_SESSION.exists() and not LIVE_BUILD.exists()
            and not LIVE_RECEIPT.exists() and not LIVE_SESSION.exists()
            and not FAR_BUILD.exists() and not FAR_RECEIPT.exists()
            and not FAR_SESSION.exists(),
            "authorized replacement-media state absent")
    replacement_media_authorization()
    replacement_media_source_gate(); replacement_media_source_mutations()
    post_completion_identity()
    completed_before = completed_final_inventory()
    completion_before = bind(RECEIPTS / "artifact-completion.json")
    post_before = bind(POST_COMPLETION)
    frozen_before = frozen_artifacts()
    cleanup = discard_external_manifest_partial()
    preflight = replacement_media_preflight()
    configure()
    result = PIPE.orchestrate()
    require(result == 0, "replacement receipt-primary media pipeline red")
    require(
        bind(RECEIPTS / "artifact-completion.json") == completion_before
        and bind(POST_COMPLETION) == post_before
        and completed_final_inventory() == completed_before
        and frozen_artifacts() == frozen_before,
        "replacement media resume changed Completion or accepted finals")
    pipeline = load(PIPELINE_RECEIPT)
    delta = receipt_completion_delta()
    far = load(FAR_RECEIPT)
    first_cleanup = load(CLEANUP_RECEIPT)
    ordered_cleanup = load(ORDERED_CHAIN_CLEANUP_RECEIPT)
    base_cleanup = load(MEDIA_CLEANUP_RECEIPT)
    value = {
        "format": "lisp65-c2.3-v2.1-configurator-parity-completion-media-v1",
        "recorded_on": RECORDED_ON,
        "status": "PASS: configurator-parity Completion/media closed; D2 ready",
        "authority": {"owner": authorization(),
            "resume_owner": resume_authorization(),
            "final_resume_owner": final_resume_authorization(),
            "adapter_authority_resume_owner":
                adapter_authority_authorization(),
            "ordered_chain_resume_owner": ordered_chain_authorization(),
            "media_resume_owner": media_resume_authorization(),
            "replacement_media_resume_owner":
                replacement_media_authorization(),
            "acceptance": bind(ACCEPTANCE),
            "first_red": bind(FIRST_RED), "resume_red": bind(RESUME_RED),
            "adapter_authority_red": bind(FINAL_RESUME_RED),
            "ordered_chain_red": bind(ADAPTER_AUTHORITY_RESUME_RED),
            "media_predecessor_red": bind(ORDERED_CHAIN_RESUME_RED),
            "media_resume_red": bind(MEDIA_RESUME_RED),
            "media_resume_attribution": bind(MEDIA_RESUME_ATTRIBUTION),
            "cleanup": bind(CLEANUP_RECEIPT),
            "ordered_chain_cleanup": bind(ORDERED_CHAIN_CLEANUP_RECEIPT),
            "base_media_cleanup": bind(MEDIA_CLEANUP_RECEIPT),
            "manifest_cleanup": bind(MANIFEST_CLEANUP_RECEIPT),
            "configurator_preflight": bind(CONFIGURATOR_PREFLIGHT),
            "media_preflight": bind(REPLACEMENT_MEDIA_PREFLIGHT),
            "pipeline": bind(PIPELINE_RECEIPT), "driver": bind(DRIVER)},
        "frozen_before": frozen_before, "frozen_after": frozen_artifacts(),
        "completed_finals_before": completed_before,
        "completed_finals_after": completed_final_inventory(),
        "input_projection": {"status":
            "PASS: real Base lifecycle plus 13-section receipt authority",
            "receipt": bind(REPLACEMENT_MEDIA_PREFLIGHT),
            "sections": preflight["section_count"],
            "output_roles": preflight["output_closure"]["role_count"],
            "post_completion": bind(POST_COMPLETION)},
        "configurator_preflight": {
            "receipt": bind(CONFIGURATOR_PREFLIGHT),
            "pid": load(CONFIGURATOR_PREFLIGHT)["pid"], "configurators": 7,
            "completion_adapters": load(CONFIGURATOR_PREFLIGHT)[
                "completion_adapters"]["adapter_count"],
            "adapter_golden_consumers": load(CONFIGURATOR_PREFLIGHT)[
                "completion_adapter_authority"]["consumer_count"],
            "producer_before_consumer": load(CONFIGURATOR_PREFLIGHT)[
                "completion_adapters"]["producer_before_consumer"],
            "completion_pid_distinct": True,
            "media_projection_pid": preflight["pid"],
            "media_projection_pid_distinct": True,
            "real_base_lifecycle": True,
            "base_output_roles": preflight["output_closure"]["role_count"]},
        "controlled_cleanup": {"receipt": bind(CLEANUP_RECEIPT),
            "discarded_files": first_cleanup["discarded"]["files"],
            "discarded_inventory_sha256": first_cleanup["discarded"][
                "inventory_sha256"],
            "ordered_chain_receipt": bind(ORDERED_CHAIN_CLEANUP_RECEIPT),
            "ordered_chain_discarded_files": ordered_cleanup["discarded"][
                "files"],
            "ordered_chain_inventory_sha256": ordered_cleanup["discarded"][
                "inventory_sha256"],
            "base_media_receipt": bind(MEDIA_CLEANUP_RECEIPT),
            "base_media_discarded_files": base_cleanup["discarded"]["files"],
            "base_media_inventory_sha256": base_cleanup["discarded"][
                "inventory_sha256"],
            "base_media_session_discarded": True,
            "manifest_receipt": bind(MANIFEST_CLEANUP_RECEIPT),
            "external_manifest_discarded_files": cleanup[
                "execution_accounting"]["files_discarded"]},
        "completion": {"receipt": completion_before, "delta": delta,
            "post_completion": post_before,
            "mode": "consume-green-post-completion-receipt-read-only",
            "rerun": False},
        "media": {"product_D81": bind(
                FAR_BUILD / "shared-system/lisp65-product.d81"),
            "library_D81": bind(BASE_BUILD / "library/lisp65-library.d81"),
            "roles": 19, "payload_bytes": far["materialization"][
                "payload_bytes"],
            "delivered_bytes": far["materialization"]["delivered_bytes"],
            "arena_capacity_bytes": 1499,
            "candidate_headroom_bytes": 251,
            "readback": "byteidentical", "same_world": True,
            "packed_gate_registry_complete": far[
                "packed_artifact_gate_registry"]["complete"],
            "pipeline_status": pipeline["status"]},
        "source_gate": replacement_media_source_gate(),
        "source_mutations_rejected": replacement_media_source_mutations(),
        "output_closure_mutations_rejected":
            base_output_closure_mutations(),
        "execution_accounting": {"WPLTO_runs": 0, "product_links": 0,
            "cards": 0, "artifact_completions": 1,
            "shared_media_builds": 3, "library_builds": 1,
            "completion_repeats_authorized": 1,
            "completion_repeats_run": 1,
            "completion_resumes_authorized": 1,
            "completion_resumes_run": 1,
            "adapter_authority_resumes_authorized": 1,
            "adapter_authority_resumes_run": 1,
            "ordered_chain_resumes_authorized": 1,
            "ordered_chain_resumes_run": 1,
            "media_resumes_authorized": 2, "media_resumes_run": 2,
            "replacement_media_resumes_authorized": 1,
            "replacement_media_resumes_run": 1,
            "artifact_completions_this_resume": 0,
            "device_contacts": 0},
        "hardware_handoff": {"D2_poison_regression_ready": True,
            "D3_D5_open": False, "session": bind(FAR_SESSION)},
        "claim_limit": (
            "Host replacement media-only resume from one read-only green "
            "Completion receipt. Completion did not rerun. D2 poison "
            "regression is ready but has not run; D3-D5 remain closed."),
    }
    validate(value)
    value["mutations_rejected"] = mutations(value)
    RECEIPT.write_bytes(canonical(value))
    print("configurator parity media: PASS replacement=1 Completion-reruns=0 roles=19 D2=ready")
    return 0


def check() -> int:
    configure()
    value = load(RECEIPT)
    rejected = value.pop("mutations_rejected", None)
    validate(value)
    require(rejected == mutations(value), "summary mutation receipt drift")
    run_child("_far_check")
    print("configurator parity media: CHECK PASS D2=ready D3-D5=closed")
    return 0


def selftest() -> int:
    acceptance_authority(); authorization(); resume_authorization()
    final_resume_authorization(); adapter_authority_authorization()
    ordered_chain_authorization(); media_resume_authorization()
    replacement_media_authorization()
    source_gate(); media_resume_source_gate(); replacement_media_source_gate()
    require(len(source_mutations()) == 8
            and len(media_resume_source_mutations()) == 5
            and len(replacement_media_source_mutations()) == 5
            and len(base_output_closure_mutations()) == 3
            and projection_sources()["bank2_static_code"]["bytes"] == 46043,
            "configurator-parity media selftest drift")
    print("configurator parity media: SELFTEST PASS source=8 media=5 replacement=5 outputs=3 static=46043")
    return 0


def record_first_red(error: Exception) -> None:
    """Bind the pre-publish Completion stop without changing its evidence."""
    if FIRST_RED.exists() or RECEIPT.exists():
        return
    source = LINK.BASE.SOURCE_WPLTO.parent / (
        "receipts/defstruct-static-plane-authority.json")
    target = TARGET / "receipts/defstruct-static-plane-authority.json"
    require(source.is_file() and not target.exists()
            and not FINAL.exists()
            and not (RECEIPTS / "artifact-completion.json").exists()
            and not PIPELINE_RECEIPT.exists()
            and not BASE_BUILD.exists() and not LIVE_BUILD.exists()
            and not FAR_BUILD.exists(),
            "Completion First Red state is not the observed pre-publish stop")
    value = {
        "format": "lisp65-c2.3-v2.1-configurator-parity-completion-red-v1",
        "recorded_on": RECORDED_ON,
        "status": "FIRST RED: COMPLETION INPUT CLOSURE RETURNS TO OWNER",
        "error": {"type": type(error).__name__, "message": str(error)},
        "attribution": {
            "class": "BOUND-MATERIALIZATION-AUTHORITY-NOT-PROJECTED",
            "missing_target": target.relative_to(ROOT).as_posix(),
            "bound_source": bind(source),
            "mechanism": (
                "the Completion continuation projected the static payload "
                "tree but omitted the sibling authority receipt consumed by "
                "the real defstruct/static-plane configurator"),
            "product_or_link_finding": False,
            "narrow_repair": (
                "project the exact SHA-bound authority receipt and execute "
                "the real seven-configurator consumer as a fresh-process "
                "Completion preflight before any retry"),
        },
        "frozen_finals_before": frozen_artifacts(),
        "frozen_finals_after": frozen_artifacts(),
        "partial_outputs": {"final_directory": False,
            "artifact_completion_receipt": False,
            "media_builds": 0, "publish_last_writes": 0},
        "execution_accounting": {"Completion_contacts": 1,
            "complete_artifacts_calls": 0, "WPLTO_runs": 0,
            "product_links": 0, "cards": 0, "media_builds": 0,
            "device_contacts": 0},
        "retry_authorized": False,
        "owner_disposition_required": True,
        "authority": {"owner": authorization(),
            "acceptance": bind(ACCEPTANCE), "driver": bind(DRIVER)},
        "claim_limit": (
            "The first Completion contact stopped in configurator setup "
            "before complete_artifacts, publish-last, final copying, media, "
            "or device work. A retry is not authorized by this receipt."),
    }
    FIRST_RED.write_bytes(canonical(value))


def bind_red() -> int:
    record_first_red(FileNotFoundError(
        str(TARGET / "receipts/defstruct-static-plane-authority.json")))
    value = load(FIRST_RED)
    require(value.get("status") ==
            "FIRST RED: COMPLETION INPUT CLOSURE RETURNS TO OWNER"
            and value["frozen_finals_before"] == value["frozen_finals_after"]
            and value["execution_accounting"]["complete_artifacts_calls"] == 0,
            "Completion First Red receipt drift")
    print("configurator parity media: FIRST RED BOUND publish-last=0 media=0")
    return 0


def record_resume_red(error: Exception) -> None:
    """Bind the consumed retry and its untouched publish-last boundary."""
    if RESUME_RED.exists() or RECEIPT.exists():
        return
    require(FIRST_RED.is_file() and CONFIGURATOR_PREFLIGHT.is_file()
            and FINAL.is_dir()
            and not (RECEIPTS / "artifact-completion.json").exists()
            and not (FINAL / "runtime-verifier-publish-last.json").exists()
            and not PIPELINE_RECEIPT.exists()
            and not BASE_BUILD.exists() and not LIVE_BUILD.exists()
            and not FAR_BUILD.exists(),
            "Completion resume Red state differs from the observed stop")
    names = (LINK.FINAL.name, LINK.FINAL.name + ".elf",
             LINK.FINAL.name + ".lto.o", LINK.FINAL.name + ".map")
    copied = {name: bind(FINAL / name) for name in names}
    source = {name: bind(WPLTO / name) for name in names}
    require(all(copied[name]["bytes"] == source[name]["bytes"]
                and copied[name]["sha256"] == source[name]["sha256"]
                for name in names),
            "partial Completion copies differ from frozen finals")
    partial_rows = [bind(path) for path in sorted(FINAL.rglob("*"))
                    if path.is_file() and not path.is_symlink()]
    aggregate = hashlib.sha256(canonical(partial_rows)).hexdigest()
    value = {
        "format": "lisp65-c2.3-v2.1-configurator-parity-completion-resume-red-v1",
        "recorded_on": RECORDED_ON,
        "status": "RESUME RED: COMPLETION ADAPTER RETURNS TO OWNER",
        "error": {"type": type(error).__name__, "message": str(error)},
        "attribution": {
            "class": "COMPLETION-ADAPTER-OWNER-MISADDRESSED",
            "configured_candidate": "passed-seven-of-seven",
            "faulty_reference": "c2_v20_source_oracle_media._current_facade_gate",
            "actual_owner": "c2_v20_crc_carveout_media._current_facade_gate",
            "mechanism": (
                "the Completion wrapper resolved the facade adapter from the "
                "wrong module after the isolated configurator preflight; the "
                "preflight covered configurator parity but not post-link "
                "adapter conformance"),
            "product_or_link_finding": False,
            "narrow_repair": (
                "bind the actual facade-adapter owner, add a real-consumer "
                "callable/signature preflight for every Completion adapter, "
                "discard the inventoried partial FINAL, then resume only on "
                "new owner authority"),
        },
        "configurator_preflight": bind(CONFIGURATOR_PREFLIGHT),
        "frozen_finals_before": frozen_artifacts(),
        "frozen_finals_after": frozen_artifacts(),
        "partial_completion": {
            "files": len(partial_rows), "inventory_sha256": aggregate,
            "copied_final_family": copied,
            "copied_final_family_byteidentical": True,
            "publish_last_receipt": False,
            "artifact_completion_receipt": False,
            "media_builds": 0},
        "execution_accounting": {"completion_repeats_authorized": 1,
            "completion_repeats_run": 1, "complete_artifacts_calls": 1,
            "completion_green": False, "WPLTO_runs": 0,
            "product_links": 0, "cards": 0, "media_builds": 0,
            "device_contacts": 0},
        "retry_authorized": False, "owner_disposition_required": True,
        "authority": {"owner": resume_authorization(),
            "first_red": bind(FIRST_RED),
            "acceptance": bind(ACCEPTANCE), "driver": bind(DRIVER)},
        "claim_limit": (
            "The sole authorized Completion repeat stopped at wrapper "
            "dispatch. No publish-last write, Completion receipt, medium, "
            "device action, WPLTO or link followed."),
    }
    RESUME_RED.write_bytes(canonical(value))


def bind_resume_red() -> int:
    record_resume_red(AttributeError(
        "module 'c2_v20_source_oracle_media' has no attribute "
        "'_current_facade_gate'"))
    value = load(RESUME_RED)
    require(value.get("status") ==
            "RESUME RED: COMPLETION ADAPTER RETURNS TO OWNER"
            and value["partial_completion"]["publish_last_receipt"] is False
            and value["execution_accounting"]["completion_repeats_run"] == 1,
            "Completion resume Red receipt drift")
    print("configurator parity media: RESUME RED BOUND publish-last=0 media=0")
    return 0


def record_final_resume_red(error: Exception) -> None:
    """Bind a failed owner-authorized final resume without granting another."""
    if FINAL_RESUME_RED.exists() or RECEIPT.exists() \
            or not CLEANUP_RECEIPT.exists():
        return
    partials = ([bind(path) for path in sorted(FINAL.rglob("*"))
                 if path.is_file() and not path.is_symlink()]
                if FINAL.is_dir() else [])
    artifact_completion = RECEIPTS / "artifact-completion.json"
    publish_last = FINAL / "runtime-verifier-publish-last.json"
    value = {
        "format": "lisp65-c2.3-v2.1-completion-final-resume-red-v1",
        "recorded_on": RECORDED_ON,
        "status": "FINAL RESUME RED: RETURNS TO OWNER",
        "error": {"type": type(error).__name__, "message": str(error)},
        "frozen_finals_before": frozen_artifacts(),
        "frozen_finals_after": frozen_artifacts(),
        "partial_outputs": {"files": len(partials),
            "inventory_sha256": hashlib.sha256(
                canonical(partials)).hexdigest(),
            "artifact_completion_receipt": artifact_completion.is_file(),
            "publish_last_receipt": publish_last.is_file(),
            "pipeline_receipt": PIPELINE_RECEIPT.is_file(),
            "media_builds": sum(path.exists() for path in (
                BASE_BUILD, LIVE_BUILD, FAR_BUILD))},
        "execution_accounting": {"completion_resumes_authorized": 1,
            "completion_resumes_run": 1, "WPLTO_runs": 0,
            "product_links": 0, "cards": 0, "device_contacts": 0},
        "retry_authorized": False, "owner_disposition_required": True,
        "authority": {"owner": final_resume_authorization(),
            "resume_red": bind(RESUME_RED),
            "cleanup": bind(CLEANUP_RECEIPT), "driver": bind(DRIVER)},
        "claim_limit": (
            "The sole adapter-owner Completion resume was consumed. No "
            "further Completion or media attempt is authorized here."),
    }
    FINAL_RESUME_RED.write_bytes(canonical(value))


def record_adapter_authority_resume_red(error: Exception) -> None:
    """Bind the sole nested-adapter-authority resume if it stops."""
    if ADAPTER_AUTHORITY_RESUME_RED.exists() or RECEIPT.exists():
        return
    require(FINAL_RESUME_RED.is_file() and CLEANUP_RECEIPT.is_file(),
            "adapter-authority resume Red lacks predecessor evidence")
    partials = ([bind(path) for path in sorted(FINAL.rglob("*"))
                 if path.is_file() and not path.is_symlink()]
                if FINAL.is_dir() else [])
    value = {
        "format": "lisp65-c2.3-v2.1-adapter-authority-resume-red-v1",
        "recorded_on": RECORDED_ON,
        "status": "ADAPTER AUTHORITY RESUME RED: RETURNS TO OWNER",
        "error": {"type": type(error).__name__, "message": str(error)},
        "frozen_finals_before": frozen_artifacts(),
        "frozen_finals_after": frozen_artifacts(),
        "partial_outputs": {"files": len(partials),
            "inventory_sha256": hashlib.sha256(
                canonical(partials)).hexdigest(),
            "configurator_preflight": CONFIGURATOR_PREFLIGHT.is_file(),
            "artifact_completion_receipt": (
                RECEIPTS / "artifact-completion.json").is_file(),
            "publish_last_receipt": (
                FINAL / "runtime-verifier-publish-last.json").is_file(),
            "pipeline_receipt": PIPELINE_RECEIPT.is_file(),
            "media_builds": sum(path.exists() for path in (
                BASE_BUILD, LIVE_BUILD, FAR_BUILD))},
        "execution_accounting": {
            "adapter_authority_resumes_authorized": 1,
            "adapter_authority_resumes_run": 1, "WPLTO_runs": 0,
            "product_links": 0, "cards": 0, "device_contacts": 0},
        "retry_authorized": False, "owner_disposition_required": True,
        "authority": {"owner": adapter_authority_authorization(),
            "predecessor_red": bind(FINAL_RESUME_RED),
            "cleanup": bind(CLEANUP_RECEIPT), "driver": bind(DRIVER)},
        "claim_limit": (
            "The sole nested-adapter-Golden resume was consumed. No further "
            "Completion, medium, or hardware contact is authorized here."),
    }
    ADAPTER_AUTHORITY_RESUME_RED.write_bytes(canonical(value))


def record_ordered_chain_resume_red(error: Exception) -> None:
    """Bind the sole ordered-publish-chain resume if it stops."""
    if ORDERED_CHAIN_RESUME_RED.exists() or RECEIPT.exists():
        return
    require(ADAPTER_AUTHORITY_RESUME_RED.is_file()
            and ORDERED_CHAIN_CLEANUP_RECEIPT.is_file(),
            "ordered-chain resume Red lacks predecessor evidence")
    partials = ([bind(path) for path in sorted(FINAL.rglob("*"))
                 if path.is_file() and not path.is_symlink()]
                if FINAL.is_dir() else [])
    value = {
        "format": "lisp65-c2.3-v2.1-ordered-chain-resume-red-v1",
        "recorded_on": RECORDED_ON,
        "status": "ORDERED CHAIN RESUME RED: RETURNS TO OWNER",
        "error": {"type": type(error).__name__, "message": str(error)},
        "frozen_finals_before": frozen_artifacts(),
        "frozen_finals_after": frozen_artifacts(),
        "partial_outputs": {"files": len(partials),
            "inventory_sha256": hashlib.sha256(
                canonical(partials)).hexdigest(),
            "configurator_preflight": CONFIGURATOR_PREFLIGHT.is_file(),
            "kernal_publish_last": (
                FINAL / "kernal-window-publish-last.json").is_file(),
            "runtime_publish_last": (
                FINAL / "runtime-verifier-publish-last.json").is_file(),
            "total_publish_last": (
                FINAL / "total-publish-last-domain.json").is_file(),
            "artifact_completion_receipt": (
                RECEIPTS / "artifact-completion.json").is_file(),
            "pipeline_receipt": PIPELINE_RECEIPT.is_file(),
            "media_builds": sum(path.exists() for path in (
                BASE_BUILD, LIVE_BUILD, FAR_BUILD))},
        "execution_accounting": {"ordered_chain_resumes_authorized": 1,
            "ordered_chain_resumes_run": 1, "WPLTO_runs": 0,
            "product_links": 0, "cards": 0, "device_contacts": 0},
        "retry_authorized": False, "owner_disposition_required": True,
        "authority": {"owner": ordered_chain_authorization(),
            "predecessor_red": bind(ADAPTER_AUTHORITY_RESUME_RED),
            "cleanup": bind(ORDERED_CHAIN_CLEANUP_RECEIPT),
            "driver": bind(DRIVER)},
        "claim_limit": (
            "The sole ordered-publish-chain resume was consumed. No further "
            "Completion, medium, or hardware contact is authorized here."),
    }
    ORDERED_CHAIN_RESUME_RED.write_bytes(canonical(value))


def record_media_resume_red(error: Exception) -> None:
    """Bind the sole media-only resume if it stops; never grant a retry."""
    if MEDIA_RESUME_RED.exists() or RECEIPT.exists():
        return
    require(ORDERED_CHAIN_RESUME_RED.is_file()
            and POST_COMPLETION.is_file()
            and (RECEIPTS / "artifact-completion.json").is_file(),
            "media-resume Red lacks its green Completion predecessor")

    def inventory(path: Path) -> dict[str, Any]:
        rows = ([bind(item) for item in sorted(path.rglob("*"))
                 if item.is_file() and not item.is_symlink()]
                if path.is_dir() else [])
        return {"exists": path.exists(), "files": len(rows),
                "rows": rows,
                "inventory_sha256": hashlib.sha256(
                    canonical(rows)).hexdigest()}

    completion = bind(RECEIPTS / "artifact-completion.json")
    post = bind(POST_COMPLETION)
    value = {
        "format": "lisp65-c2.3-v2.1-configurator-parity-media-resume-red-v1",
        "recorded_on": RECORDED_ON,
        "status": "MEDIA RESUME RED: RETURNS TO OWNER",
        "error": {"type": type(error).__name__, "message": str(error)},
        "completed_finals": completed_final_inventory(),
        "frozen_finals_before": frozen_artifacts(),
        "frozen_finals_after": frozen_artifacts(),
        "green_completion": {"receipt": completion,
            "post_completion": post, "rerun": False},
        "partial_outputs": {"base": inventory(BASE_BUILD),
            "liveness": inventory(LIVE_BUILD), "far": inventory(FAR_BUILD),
            "base_receipt": BASE_RECEIPT.is_file(),
            "liveness_receipt": LIVE_RECEIPT.is_file(),
            "far_receipt": FAR_RECEIPT.is_file(),
            "pipeline_receipt": PIPELINE_RECEIPT.is_file(),
            "media_preflight": MEDIA_PREFLIGHT.is_file(),
            "controlled_cleanup": MEDIA_CLEANUP_RECEIPT.is_file()},
        "execution_accounting": {"media_resumes_authorized": 1,
            "media_resumes_run": 1, "artifact_completions_this_resume": 0,
            "WPLTO_runs": 0, "product_links": 0, "cards": 0,
            "device_contacts": 0},
        "retry_authorized": False, "owner_disposition_required": True,
        "authority": {"owner": media_resume_authorization(),
            "predecessor_red": bind(ORDERED_CHAIN_RESUME_RED),
            "cleanup": (bind(MEDIA_CLEANUP_RECEIPT)
                        if MEDIA_CLEANUP_RECEIPT.is_file() else None),
            "driver": bind(DRIVER)},
        "claim_limit": (
            "The sole media-only resume was consumed. Completion remained "
            "read-only and did not rerun. No retry or hardware contact is "
            "authorized by this receipt."),
    }
    MEDIA_RESUME_RED.write_bytes(canonical(value))


def bind_media_resume_attribution() -> int:
    """Name the already-observed lifecycle stop without granting a retry."""
    require(MEDIA_RESUME_RED.is_file()
            and MEDIA_CLEANUP_RECEIPT.is_file()
            and MEDIA_PREFLIGHT.is_file()
            and not MEDIA_RESUME_ATTRIBUTION.exists()
            and not BASE_BUILD.exists() and not BASE_RECEIPT.exists()
            and not BASE_SESSION.exists() and not LIVE_BUILD.exists()
            and not FAR_BUILD.exists() and not PIPELINE_RECEIPT.exists()
            and not RECEIPT.exists(),
            "media-resume attribution lifecycle drift")
    red = load(MEDIA_RESUME_RED)
    manifest = TARGET / "canonical-product-manifest.json"
    value = load(manifest)
    require(
        red.get("status") == "MEDIA RESUME RED: RETURNS TO OWNER"
        and red["error"]["message"].endswith(
            "current-world completion/media closure is one-shot\n")
        and value.get("status") ==
            "passed-fresh-source-product-and-post-link-completion"
        and value.get("candidate", {}).get("source_driver", {}).get(
            "sha256") == "9240d9edb85fa54f1ce5653b1d1f2e21775e06087baa90f60f8799569027be80"
        and value.get("identity", {}).get("linked_elf_sha256") == bind(
            FINAL / (LINK.FINAL.name + ".elf"))["sha256"]
        and value["identity"].get("resident_prg_sha256") == bind(
            FINAL / LINK.FINAL.name)["sha256"],
        "external partial manifest does not belong to the failed base run")
    attribution = {
        "format": "lisp65-c2.3-v2.1-media-resume-attribution-v1",
        "recorded_on": RECORDED_ON,
        "status": "MEDIA RESUME RED ATTRIBUTED: UNENUMERATED EXTERNAL BASE-MEDIA PARTIAL",
        "attribution": {
            "class": "MEDIA-PRODUCER-OUTPUT-CLOSURE-INCOMPLETE",
            "failed_stage": "base-media lifecycle entry before media generation",
            "mechanism": (
                "the prior Red enumerated the 21 files below BASE_BUILD and "
                "the session file, but build_product_manifest had also "
                "written the Base producer-owned canonical manifest in the "
                "candidate target; the controlled cleanup therefore left "
                "one stale owned output, and the real one-shot producer "
                "correctly refused to overwrite it"),
            "unclaimed_partial": bind(manifest),
            "product_or_completion_finding": False,
            "new_media_outputs_this_resume": 0,
            "narrow_repair": (
                "extend the bound Base-output closure to the external "
                "canonical manifest, make the media preflight execute the "
                "real Base lifecycle predicate, discard that one exact "
                "partial only under new owner authority, then authorize a "
                "replacement media resume")},
        "green_completion": {"artifact": bind(
                RECEIPTS / "artifact-completion.json"),
            "post_completion": bind(POST_COMPLETION),
            "completed_product": bind(FINAL / LINK.FINAL.name),
            "rerun": False},
        "media_preflight": bind(MEDIA_PREFLIGHT),
        "controlled_cleanup": bind(MEDIA_CLEANUP_RECEIPT),
        "media_resume_red": bind(MEDIA_RESUME_RED),
        "execution_accounting": {"media_resumes_authorized": 1,
            "media_resumes_run": 1, "artifact_completions_this_resume": 0,
            "base_media_build_actions_entered": 0,
            "new_media_files": 0, "WPLTO_runs": 0, "product_links": 0,
            "cards": 0, "device_contacts": 0},
        "retry_authorized": False, "owner_disposition_required": True,
        "claim_limit": (
            "This receipt attributes the consumed media-resume stop. It "
            "does not authorize removal of the external manifest or another "
            "media resume."),
    }
    MEDIA_RESUME_ATTRIBUTION.write_bytes(canonical(attribution))
    print("configurator parity media: RESUME RED ATTRIBUTED external-partials=1")
    return 0


def record_replacement_media_resume_red(error: Exception) -> None:
    """Bind a stopped replacement media resume without granting another."""
    if REPLACEMENT_MEDIA_RESUME_RED.exists() or RECEIPT.exists():
        return
    require(MEDIA_RESUME_RED.is_file() and MEDIA_RESUME_ATTRIBUTION.is_file()
            and MANIFEST_CLEANUP_RECEIPT.is_file()
            and (RECEIPTS / "artifact-completion.json").is_file(),
            "replacement-media Red lacks predecessor evidence")

    def inventory(path: Path) -> dict[str, Any]:
        rows = ([bind(item) for item in sorted(path.rglob("*"))
                 if item.is_file() and not item.is_symlink()]
                if path.is_dir() else [])
        return {"exists": path.exists(), "files": len(rows),
                "rows": rows, "inventory_sha256": hashlib.sha256(
                    canonical(rows)).hexdigest()}

    value = {
        "format": "lisp65-c2.3-v2.1-replacement-media-resume-red-v1",
        "recorded_on": RECORDED_ON,
        "status": "REPLACEMENT MEDIA RESUME RED: RETURNS TO OWNER",
        "error": {"type": type(error).__name__, "message": str(error)},
        "completed_finals": completed_final_inventory(),
        "frozen_finals_before": frozen_artifacts(),
        "frozen_finals_after": frozen_artifacts(),
        "green_completion": {"receipt": bind(
                RECEIPTS / "artifact-completion.json"),
            "post_completion": bind(POST_COMPLETION), "rerun": False},
        "partial_outputs": {"base": inventory(BASE_BUILD),
            "liveness": inventory(LIVE_BUILD), "far": inventory(FAR_BUILD),
            "manifest": ((bind(TARGET / "canonical-product-manifest.json"))
                         if (TARGET / "canonical-product-manifest.json").is_file()
                         else None),
            "base_receipt": BASE_RECEIPT.is_file(),
            "liveness_receipt": LIVE_RECEIPT.is_file(),
            "far_receipt": FAR_RECEIPT.is_file(),
            "pipeline_receipt": PIPELINE_RECEIPT.is_file(),
            "replacement_preflight": REPLACEMENT_MEDIA_PREFLIGHT.is_file()},
        "execution_accounting": {"replacement_media_resumes_authorized": 1,
            "replacement_media_resumes_run": 1,
            "artifact_completions_this_resume": 0,
            "WPLTO_runs": 0, "product_links": 0, "cards": 0,
            "device_contacts": 0},
        "retry_authorized": False, "owner_disposition_required": True,
        "authority": {"owner": replacement_media_authorization(),
            "predecessor_red": bind(MEDIA_RESUME_RED),
            "attribution": bind(MEDIA_RESUME_ATTRIBUTION),
            "manifest_cleanup": bind(MANIFEST_CLEANUP_RECEIPT),
            "driver": bind(DRIVER)},
        "claim_limit": (
            "The sole replacement media resume was consumed. Completion "
            "remained read-only. No retry or hardware contact is authorized "
            "by this receipt."),
    }
    REPLACEMENT_MEDIA_RESUME_RED.write_bytes(canonical(value))


def main() -> int:
    actions = ("_config_preflight", "_media_preflight",
               "_replacement_media_preflight", "_complete", "_base", "_base_check", "_liveness",
               "_liveness_check", "_far", "_far_check", "_finalize_far",
               "_rebind_base", "_rebind_liveness")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=(
        "selftest", "build", "resume", "resume-adapter-golden",
        "resume-ordered-chain", "resume-media", "resume-media-replacement",
        "check", "bind-red", "bind-resume-red",
        "bind-media-resume-attribution",
        *actions))
    action = parser.parse_args().action
    if action == "_config_preflight":
        return configurator_preflight_child()
    if action == "_media_preflight":
        return media_preflight_child()
    if action == "_replacement_media_preflight":
        return replacement_media_preflight_child()
    if action in actions:
        return child(action)
    return {"selftest": selftest, "build": build,
            "resume": lambda: build(resume=True), "check": check,
            "resume-adapter-golden": lambda: build(
                adapter_authority_resume=True),
            "resume-ordered-chain": lambda: build(
                ordered_chain_resume=True),
            "resume-media": media_resume,
            "resume-media-replacement": replacement_media_resume,
            "bind-red": bind_red,
            "bind-resume-red": bind_resume_red,
            "bind-media-resume-attribution":
                bind_media_resume_attribution}[action]()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        if len(sys.argv) > 1 and sys.argv[1] == "build":
            try:
                if CONFIGURATOR_PREFLIGHT.exists():
                    record_resume_red(error)
                else:
                    record_first_red(error)
            except Exception as receipt_error:
                print(f"configurator parity media receipt failure: {receipt_error}",
                      file=sys.stderr)
        if len(sys.argv) > 1 and sys.argv[1] == "resume":
            try:
                record_final_resume_red(error)
            except Exception as receipt_error:
                print(f"configurator parity media receipt failure: {receipt_error}",
                      file=sys.stderr)
        if len(sys.argv) > 1 and sys.argv[1] == "resume-adapter-golden":
            try:
                record_adapter_authority_resume_red(error)
            except Exception as receipt_error:
                print(f"configurator parity media receipt failure: {receipt_error}",
                      file=sys.stderr)
        if len(sys.argv) > 1 and sys.argv[1] == "resume-ordered-chain":
            try:
                record_ordered_chain_resume_red(error)
            except Exception as receipt_error:
                print(f"configurator parity media receipt failure: {receipt_error}",
                      file=sys.stderr)
        if len(sys.argv) > 1 and sys.argv[1] == "resume-media":
            try:
                record_media_resume_red(error)
            except Exception as receipt_error:
                print(f"configurator parity media receipt failure: {receipt_error}",
                      file=sys.stderr)
        if (len(sys.argv) > 1 and
                sys.argv[1] == "resume-media-replacement"):
            try:
                record_replacement_media_resume_red(error)
            except Exception as receipt_error:
                print(f"configurator parity media receipt failure: {receipt_error}",
                      file=sys.stderr)
        label = ("ORDERED CHAIN RESUME RED"
                 if len(sys.argv) > 1 and sys.argv[1] == "resume-ordered-chain"
                 else "MEDIA RESUME RED"
                 if len(sys.argv) > 1 and sys.argv[1] == "resume-media"
                 else "REPLACEMENT MEDIA RESUME RED"
                 if len(sys.argv) > 1 and
                    sys.argv[1] == "resume-media-replacement"
                 else "ADAPTER AUTHORITY RESUME RED"
                 if len(sys.argv) > 1 and
                    sys.argv[1] == "resume-adapter-golden"
                 else "FINAL RESUME RED"
                 if len(sys.argv) > 1 and sys.argv[1] == "resume"
                 else "FIRST RED")
        print(f"configurator parity media: {label}: {error}", file=sys.stderr)
        raise SystemExit(2)
