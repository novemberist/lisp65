#!/usr/bin/env python3
"""Complete the green 2.0 card and build its same-world v1.5 media.

This driver is deliberately downstream of the consumed product card.  It may
run canonical publish-last artifact completion and media packing, but it may
not compile, link, qualify, or execute another card.
"""

from __future__ import annotations

import argparse
import ast
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_lite_media_product as MEDIA  # noqa: E402
import c2_link95_world_bound_media as PAIR  # noqa: E402
import c2_product_substitution_link as PRODUCT  # noqa: E402
import c2_v112_candidate_media as LIB  # noqa: E402
import c2_v150_candidate_media as LINK97_MEDIA  # noqa: E402
import c2_v20_crc_carveout_card as CARD  # noqa: E402
import c2_v20_ownership_recharter as PRODUCER  # noqa: E402
import c2_v20_vma_invariant_golden as INV  # noqa: E402
import evidence_era as ERA  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
BUILD = ROOT / "build/c2.3/v2.0-crc-carveout-media"
SHARED = BUILD / "shared-system"
LIBRARY = BUILD / "library"
MANIFEST = CARD.BUILD / "canonical-product-manifest.json"
PRODUCT_D81 = SHARED / "lisp65-product.d81"
WORK_D81 = SHARED / "lisp65-work.d81"
LIBRARY_D81 = LIBRARY / "lisp65-library.d81"
MEDIA_MANIFEST = SHARED / "candidate-manifest.json"
RECEIPT = EVIDENCE / "c2.3-v2.0-crc-carveout-media-closure-receipt.json"
SESSION = ROOT / "config/c2-v150-v20-device-session.json"
RELEASE_CONTRACT = ROOT / "config/c2-v150-release-contract.json"
OLD_MEDIA_RECEIPT = LINK97_MEDIA.RECEIPT
DRIVER = Path(__file__).resolve()
FORMAT = "lisp65-c2.3-v20-crc-carveout-media-closure-v1"
STATUS = "V20-OWNED-GEOMETRY-HOST-AND-MEDIA-GREEN; D1-D5-PENDING"
RECORDED_ON = "2026-08-12"
LINK = 99
VARIANTS = LINK97_MEDIA.VARIANTS
_CONFIGURE_CALLS = 0


class MediaClosureError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise MediaClosureError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(),
            f"regular JSON authority absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(),
            f"regular artifact absent: {path}")
    raw = path.read_bytes()
    return {
        "path": path.resolve().relative_to(ROOT.resolve()).as_posix(),
        "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
    }


def card_authority() -> dict[str, Any]:
    value = load(CARD.RECEIPT)
    require(
        value.get("status")
            == "PASS: VMA geometry, LMA reset and CRC-aware delivery exact"
        and value.get("attempt_accounting") == {
            "cards_authorized": 1, "cards_consumed": 1,
            "device_contacts": 0, "product_link_attempts": 1,
            "wplto_runs": 1,
        }
        and value["acceptance"]["VMA_golden"]["allocatable_sections"] == 103
        and value["acceptance"]["VMA_golden"]["fixed_boundary_symbols"] == 27
        and value["acceptance"]["delivered_bytes"]["identity_mismatches"] == 0
        and value["acceptance"]["delivered_bytes"]["publish_last"][
            "values_correct"] is True,
        "green CRC-aware card authority absent")
    for role in ("elf", "prg", "map"):
        require(value["artifacts"][role] == bind(
            ROOT / value["artifacts"][role]["path"]),
            f"consumed card artifact drift: {role}")
    return value


def configure_candidate() -> tuple[dict[str, Path], Any]:
    """Rebind completion to the consumed card without entering its producer."""
    global _CONFIGURE_CALLS
    require(_CONFIGURE_CALLS == 0,
            "current-world completion/media configured twice in one process")
    _CONFIGURE_CALLS += 1
    PRODUCER.BUILD = CARD.BUILD
    PRODUCER.FINAL_RED = CARD.BUILD / "producer-internal-first-red.json"
    paths = PRODUCER.configure_producer()
    PRODUCT.configure_full_map_ownership()
    PRODUCT.configure_low_resident_lma_reset()
    return paths, PRODUCER.BASE.L95.CAN


def _current_fixed_audit(
        original: Callable[..., dict[str, Any]], elf: Path,
        *, out: Path | None = None, require_hot_bss: bool = True,
        ) -> dict[str, Any]:
    """Retain the fixed leaf proof; source owned state from the VMA golden."""
    value = original(elf, out=None, require_hot_bss=False)
    comparison = INV.compare_elf(elf)
    require(comparison == card_authority()["acceptance"]["VMA_golden"],
            "completion fixed-state adapter differs from consumed card")
    truth = ElfTruth.read(
        elf, llvm_readobj=ROOT / "tools/llvm-mos/bin/llvm-readobj")
    hot = truth.section(".lisp65_c2_fixed_bank0_hot_bss")
    noinit = truth.section(".noinit")
    require(
        (hot.address, hot.bytes) == (0xC25D, 240)
        and (noinit.address, noinit.bytes) == (0xC34D, 0),
        "owned hot-BSS/noinit geometry differs from VMA authority")
    value["hot_bss"] = {
        "authority": "VMA-invariant-golden-and-consumed-card",
        "address": hot.address, "bytes": hot.bytes,
        "end_exclusive": hot.address + hot.bytes,
        "following_noinit": {
            "address": noinit.address, "bytes": noinit.bytes,
            "end_exclusive": noinit.address + noinit.bytes,
        },
        "heap_start": 0xC354, "overlay_floor": 0xC356,
    }
    value["VMA_golden"] = comparison
    if out is not None:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(canonical(value))
    return value


def _current_facade_gate(
        original: Callable[..., dict[str, Any]], out: Path,
        target: Path, suffix: str) -> dict[str, Any]:
    """Run the inherited edge gate with the two owned far-facade callees."""
    elf = Path(str(target) + ".elf")
    symbols = PRODUCT.defined_symbols(elf)
    far_names = ("vm_code_load_converged", "c2_physical_read_converged")
    require(all(name in symbols for name in far_names),
            "current mapped-far facade targets absent")
    old_bss = PRODUCT.BSS_TRIAGE
    old_vectors = PRODUCT.host_facade_vector_addresses

    def current_vectors() -> dict[str, int]:
        value = old_vectors()
        value.update({name: symbols[name] for name in far_names})
        return value

    try:
        # The inherited gate's six-byte .noinit snapshot predates full-map
        # ownership.  The VMA golden above owns that state; every other fixed
        # leaf, vector, and E000 edge check remains live here.
        PRODUCT.BSS_TRIAGE = False
        PRODUCT.host_facade_vector_addresses = current_vectors
        value = original(out, target, suffix)
    finally:
        PRODUCT.BSS_TRIAGE = old_bss
        PRODUCT.host_facade_vector_addresses = old_vectors
    value["owned_full_map_state"] = INV.compare_elf(elf)
    value["mapped_far_facade_edges"] = {
        name: symbols[name] for name in far_names}
    (out / f"fixed-host-facade-{suffix}.json").write_bytes(canonical(value))
    return value


def complete_action() -> int:
    card = card_authority()
    paths, can = configure_candidate()
    require(not paths["final"].exists() and not MANIFEST.exists(),
            "current-world artifact completion is one-shot")

    replay = can.REPLAY
    original_configure = replay.configure
    original_fixed = PRODUCT.FIXED_BLOCK_LEAF.audit_elf
    original_facade = PRODUCT.fixed_facade_gate
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
        PRODUCT.configure_full_map_ownership()
        PRODUCT.configure_low_resident_lma_reset()
        replay.P.PRODUCT_ARTIFACTS_MANIFEST = (
            paths["static_product"] / "substitution-artifacts.json")
        elf = paths["wplto"] / "lisp65-c2-substitution-linked.prg.elf"
        binding = ElfTruth.read(
            elf, llvm_readobj=ROOT / "tools/llvm-mos/bin/llvm-readobj"
        ).section(".lisp65_runtime_overlay_verifier_bindings")
        require((binding.address, binding.bytes) == (0xB98C, 40),
                "candidate runtime-verifier binding geometry drift")
        replay.P.VERIFIER_BINDING_BASE = binding.address
        replay.P.LINK60_VERIFIER_BINDING_BASE = binding.address
        require(
            replay.P.RUNTIME_OVERLAY_FORMAT_VERSION == 4
            and replay.P.PROFILE_RODATA_BYTES == 348
            and replay.P.runtime_binding_bytes() == 40
            and replay.P.total_publish_last_bytes() == 42
            and replay.P.INTERN_SESSION_SERVICE,
            "current-world artifact-completion service shape drift")
        geometry_ready = True

    def fixed_adapter(elf: Path, *, out: Path | None = None,
                      require_hot_bss: bool = True) -> dict[str, Any]:
        return _current_fixed_audit(
            original_fixed, elf, out=out,
            require_hot_bss=require_hot_bss)

    def facade_adapter(out: Path, target: Path,
                       suffix: str) -> dict[str, Any]:
        return _current_facade_gate(original_facade, out, target, suffix)

    def publish_runtime_binding(
            product: Path, boot_manifest: Path,
            session_manifest: Path) -> dict[str, Any]:
        """Publish what this card intentionally left to artifact completion."""
        return PRODUCT.patch_verifier_binding_table(
            can.FINAL, product, boot_manifest, session_manifest,
            expected_base=PRODUCT.LINK60_VERIFIER_BINDING_BASE)

    # Reconstruct the linked card's actual product configuration before the
    # independent delivery replay.  The card ran after these one-way profile
    # selectors; module import defaults are deliberately not an authority.
    current_geometry()
    delivery = CARD.delivered_bytes_gate(
        paths["wplto"] / "lisp65-c2-substitution-linked.prg.elf",
        paths["wplto"] / "lisp65-c2-substitution-linked.prg")
    require(delivery == card["acceptance"]["delivered_bytes"],
            "CRC-aware delivered-byte authority drift before completion")

    replay.configure = current_geometry
    PRODUCT.FIXED_BLOCK_LEAF.audit_elf = fixed_adapter
    PRODUCT.fixed_facade_gate = facade_adapter
    can.verify_published_verifier_binding = publish_runtime_binding
    try:
        completion = can.complete_artifacts()
    finally:
        replay.configure = original_configure
        PRODUCT.FIXED_BLOCK_LEAF.audit_elf = original_fixed
        PRODUCT.fixed_facade_gate = original_facade
        can.verify_published_verifier_binding = original_verify
    require(
        completion["status"]
            == "passed-no-relink-publish-last-artifact-completion"
        and completion["compiler_runs"] == completion["linker_runs"] == 0,
        "current-world artifact completion red")
    print("2.0 current-world completion: PASS compiler=0 linker=0")
    return 0


def fresh_completion() -> None:
    environment = os.environ.copy()
    environment.update(PRODUCER.BASE.L95.CAN.canonical_build_environment())
    result = subprocess.run(
        [sys.executable, str(DRIVER), "_complete"], cwd=ROOT,
        env=environment, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, check=False)
    require(result.returncode == 0,
            "fresh current-world completion red:\n" + result.stdout)
    (CARD.BUILD / "receipts/artifact-completion.log").write_text(
        result.stdout, encoding="utf-8")


def completion_delta() -> dict[str, Any]:
    card = card_authority()
    wplto = CARD.BUILD / "wplto/lisp65-c2-substitution-linked.prg"
    final = CARD.BUILD / "final/lisp65-c2-substitution-linked.prg"
    elf = Path(str(final) + ".elf")
    before = (CARD.BUILD / "final/lisp65-c2-substitution-unbound.prg").read_bytes()
    after = final.read_bytes()
    require(len(before) == len(after), "artifact completion changed PRG length")
    load_address = int.from_bytes(before[:2], "little")
    truth = ElfTruth.read(
        elf, llvm_readobj=ROOT / "tools/llvm-mos/bin/llvm-readobj")
    binding = truth.section(".lisp65_runtime_overlay_verifier_bindings")
    allowed = set(range(binding.address, binding.address + binding.bytes))
    allowed.update(CARD.CARVEOUT)
    changed = {
        load_address + offset - 2
        for offset, (left, right) in enumerate(zip(before, after))
        if left != right and offset >= 2
    }
    require(changed <= allowed and set(CARD.CARVEOUT) <= changed,
            "completion wrote outside runtime-binding/CRC publish-last domain")
    window = (CARD.BUILD / "final/c2-product-kernal-window.bin").read_bytes()
    require(len(window) == 0x2000, "completed KERNAL window is truncated")
    crc = CARD.crc16_oracle(window)
    high = after[2 + CARD.HIGH - load_address]
    low = after[2 + CARD.LOW - load_address]
    require((high, low) == (crc >> 8, crc & 0xFF),
            "final media candidate CRC operands differ from final window")
    window_bound = CARD.BUILD / "final/lisp65-c2-substitution-window-bound.prg"
    require(window_bound.read_bytes() == wplto.read_bytes(),
            "artifact completion predecessor differs from consumed card PRG")
    require(card["artifacts"]["prg"] == bind(wplto),
            "consumed WPLTO PRG changed during artifact completion")
    return {
        "status": "passed-domain-aware-canonical-publish-last-completion",
        "allowed_addresses": len(allowed),
        "changed_addresses": len(changed),
        "changes_outside_domain": 0,
        "runtime_binding": {
            "address": binding.address, "bytes": binding.bytes},
        "CRC_operands": [CARD.HIGH, CARD.LOW],
        "final_window_crc16": f"0x{crc:04x}",
        "final_values": [high, low],
        "wplto_PRG": bind(wplto), "final_PRG": bind(final),
    }


def build_product_manifest(can: Any) -> dict[str, Any]:
    profile = load(PRODUCER.CANDIDATE_PROFILE)
    completion = load(CARD.BUILD / "receipts/artifact-completion.json")
    static = {
        "status": "passed-v1.5-current-world-owned-static-plane",
        "bank2_static_code_bytes": profile["bank2_static_code"]["bytes"],
        "bank2_sha256": profile["bank2_static_code"]["sha256"],
        "entries": profile["entries"], "resolutions": profile["resolutions"],
        "roots": profile["roots"],
        "direct_entry_refs": profile["direct_entry_refs"],
        "product_build_id": profile["product_build_id"],
        "card": bind(CARD.RECEIPT), "VMA_golden": bind(INV.GOLDEN),
    }
    manifest_static = BUILD / "manifest-inputs"
    library_dir = manifest_static / "libs"
    library_dir.mkdir(parents=True, exist_ok=False)
    specs = {key: manifest for key, _name, manifest in can.SPECS}
    for name in ("ide", "idex", "m65d"):
        manifest = specs[name]
        suffix = ".manifest.json"
        require(manifest.name.endswith(suffix),
                f"noncanonical manifest name for media role: {name}")
        source = manifest.with_name(
            manifest.name.removesuffix(suffix) + ".ext.bin")
        require(source.is_file(), f"linked media role absent: {source}")
        shutil.copyfile(source, library_dir / f"{name}.ext.bin")
    original_static = can.STATIC
    try:
        can.STATIC = manifest_static
        value = can.manifest(static, card_authority(), completion)
    finally:
        can.STATIC = original_static
    value["candidate"] = {
        "release": "v1.5.0", "link": LINK, "pre_promotion": True,
        "public_surface_changed": True, "source_driver": bind(DRIVER),
        "owned_full_map": True, "F018B_content_safe_reads": True,
    }
    MANIFEST.write_bytes(canonical(value))
    require(can.check()["identity"] == value["identity"],
            "current-world canonical manifest readback red")
    return value


def configure_media(can: Any) -> None:
    MEDIA.CANONICAL = can
    MEDIA.BUILD = SHARED
    MEDIA.PRODUCT_MANIFEST = MANIFEST
    MEDIA.MANIFEST = MEDIA_MANIFEST
    MEDIA.DESCRIPTOR = SHARED / "boot.id"
    MEDIA.STAGER = SHARED / "autoboot.c65"
    MEDIA.STAGER_MAP = SHARED / "autoboot.c65.map"
    MEDIA.PRODUCT_D81 = PRODUCT_D81
    MEDIA.WORK_D81 = WORK_D81
    MEDIA.MOUNT = SHARED / "lisp65-product.mount.json"


def product_build_id() -> int:
    value = load(MANIFEST)
    build_id = int(value["static_plane"]["product_build_id"], 0)
    roles = {row["role"]: row for row in value["artifacts"]}
    c2d = (ROOT / roles["c2d-v6-code-plane"]["path"]).read_bytes()
    require(int.from_bytes(c2d[44:48], "little") == build_id,
            "manifest/C2D current-world identity drift")
    return build_id


def library_facts(build_id: int, *, existing: bool) -> dict[str, Any]:
    old = LIB.VARIANTS
    try:
        LIB.VARIANTS = VARIANTS
        value = (LIB.existing_library_variant if existing
                 else LIB.build_library_variant)(
                     "v1.5", LIBRARY, build_id)
    finally:
        LIB.VARIANTS = old
    require(
        [row["name"] for row in value["index_rows"]]
            == ["string-extra", "inspect", "place", "defstruct"]
        and value["resolver_contracts"]["defstruct"][
            "declared_dependency_closure"] == [2, 3],
        "current-world library closure drift")
    return value


# The closure receipt and the session handoff it seals are closed records, so
# every authority they name has to be read in the world that sealed them.
# Binding them to the working tree made closed records answer for living files:
# a later producer edit and the 2026-08-17 correction of the string-op
# expectation both drifted a closure that had long since been bound.  The
# media content itself is still verified live -- only identity is era-bound.
CLOSURE_ERA_COMMIT = "73c6f83d"


def era_bind(path: Path) -> dict[str, Any]:
    """Bind an authority as the media closure sealed it, not as it is today."""
    return ERA.era_bind(CLOSURE_ERA_COMMIT, path)


def session_value() -> dict[str, Any]:
    value = deepcopy(load(LINK97_MEDIA.SESSION))
    value["format"] = "lisp65-c2-v150-v20-device-session-v1"
    value["identity"] = {
        "product_medium": PRODUCT_D81.relative_to(ROOT).as_posix(),
        "library_medium": LIBRARY_D81.relative_to(ROOT).as_posix(),
    }
    value["authority"] = {
        "product_card": bind(CARD.RECEIPT),
        "media_closure": RECEIPT.relative_to(ROOT).as_posix(),
        "release_contract": era_bind(RELEASE_CONTRACT),
    }
    return value


def source_gate(source_override: str | None = None) -> dict[str, Any]:
    source = source_override or DRIVER.read_text(encoding="utf-8")
    tree = ast.parse(source)
    functions = {node.name: node for node in tree.body
                 if isinstance(node, ast.FunctionDef)}
    build = functions.get("build_action")
    complete = functions.get("complete_action")
    require(build is not None and complete is not None,
            "current-world media lifecycle entrypoint absent")
    build_calls = [ast.unparse(node.func) for node in ast.walk(build)
                   if isinstance(node, ast.Call)]
    complete_calls = [ast.unparse(node.func) for node in ast.walk(complete)
                      if isinstance(node, ast.Call)]
    forbidden = {
        "PRODUCER.produce_candidate", "CARD.card", "CARD.produce_candidate",
        "can.run_wplto", "PRODUCT.single_link", "subprocess.check_call",
    }
    require(
        not (set(build_calls + complete_calls) & forbidden)
        and build_calls.count("fresh_completion") == 1
        and build_calls.count("MEDIA.build") == 1
        and build_calls.count("library_facts") >= 1
        and complete_calls.count("can.complete_artifacts") == 1,
        "media closure can re-enter a card/compiler/linker or loses a stage")
    return {
        "status": "passed-card-downstream-completion-and-media-source-gate",
        "product_cards": 0, "WPLTO_runs": 0, "product_links": 0,
        "artifact_completions": 1, "shared_media_builds": 1,
        "library_media_builds": 1, "forbidden_calls_absent": sorted(forbidden),
    }


def source_mutations() -> list[str]:
    source = DRIVER.read_text(encoding="utf-8")
    anchor = (
        "    else:\n        fresh_completion()\n"
        "    _paths, can = configure_candidate()\n")
    require(anchor in source, "media build mutation anchor absent")
    cases = {
        "reenter-card": source.replace(
            anchor,
            "    else:\n        CARD.card()\n        fresh_completion()\n"
            "    _paths, can = configure_candidate()\n", 1),
        "reenter-producer": source.replace(
            anchor,
            "    else:\n        PRODUCER.produce_candidate()\n"
            "        fresh_completion()\n"
            "    _paths, can = configure_candidate()\n", 1),
        "drop-completion": source.replace(
            anchor, "    else:\n        pass\n"
            "    _paths, can = configure_candidate()\n", 1),
        "double-media": source.replace(
            "    configure_media(can)\n    shared = MEDIA.build()\n",
            "    configure_media(can)\n    MEDIA.build()\n"
            "    shared = MEDIA.build()\n", 1),
    }
    rejected: list[str] = []
    for name, candidate in cases.items():
        try:
            source_gate(candidate)
        except MediaClosureError:
            rejected.append(name)
    require(rejected == list(cases), "media source mutation survived")
    return rejected


def derive(*, configured: bool = False) -> dict[str, Any]:
    if configured:
        can = PRODUCER.BASE.L95.CAN
    else:
        _paths, can = configure_candidate()
        configure_media(can)
    shared = MEDIA.check()
    build_id = product_build_id()
    library = library_facts(build_id, existing=True)
    pair = PAIR.pair_identity(PRODUCT_D81, LIBRARY_D81)
    require(
        shared["artifact_count"] == 19
        and shared["canonical_product"] == bind(MANIFEST)
        and pair["result"] == "same-world-pair"
        and pair["product_build_id"] == f"0x{build_id:08x}"
        and pair["index_rows"] == 4,
        "current-world media readback or pair identity red")
    session = load(SESSION)
    require(session == session_value(), "D1-D5 session handoff drift")
    return {
        "format": FORMAT, "recorded_on": RECORDED_ON,
        "status": STATUS,
        "attempt_accounting": {
            "additional_product_cards": 0, "additional_WPLTO_runs": 0,
            "additional_product_links": 0, "artifact_completions": 1,
            "shared_system_builds": 1, "library_builds": 1,
            "media_readbacks": 1, "hardware_runs": 0,
        },
        "authority": {
            "green_card": bind(CARD.RECEIPT),
            "VMA_golden": bind(INV.GOLDEN),
            "product_manifest": bind(MANIFEST),
            "producer": era_bind(DRIVER),
        },
        "Link97_closure_retirement": {
            "historical_receipt": bind(OLD_MEDIA_RECEIPT),
            "current_world_authority": False,
            "reason": "same-world media now derives from the green 2.0 card",
        },
        "completion": completion_delta(),
        "shared_system": {
            "artifact_count": shared["artifact_count"],
            "artifact_set_sha256": shared["artifact_set_sha256"],
            "manifest": bind(MEDIA_MANIFEST),
            "product_D81": bind(PRODUCT_D81),
            "work_D81": bind(WORK_D81), "readback": "passed",
        },
        "library": {**library, "readback": "passed"},
        "pair_identity": pair,
        "session": {"status": "prepared-not-run", "rows": [
            "D1", "D2", "D3", "D4", "D5"], "contract": bind(SESSION)},
        "producer_source_gate": source_gate(),
        "producer_mutations_rejected": source_mutations(),
        "claim_limit": (
            "Host-completed current-world product/library media and D1-D5 "
            "handoff only; no device, Halt, release, publication or parity claim."),
    }


def validate(value: dict[str, Any], *, verify: bool) -> None:
    require(
        value.get("format") == FORMAT and value.get("status") == STATUS
        and value.get("attempt_accounting") == {
            "additional_product_cards": 0, "additional_WPLTO_runs": 0,
            "additional_product_links": 0, "artifact_completions": 1,
            "shared_system_builds": 1, "library_builds": 1,
            "media_readbacks": 1, "hardware_runs": 0,
        }
        and value["Link97_closure_retirement"]["current_world_authority"] is False
        and value["completion"]["changes_outside_domain"] == 0
        and value["shared_system"]["artifact_count"] == 19
        and value["shared_system"]["readback"] == "passed"
        and value["library"]["readback"] == "passed"
        and value["pair_identity"]["result"] == "same-world-pair"
        and value["pair_identity"]["index_rows"] == 4
        and value["session"]["rows"] == ["D1", "D2", "D3", "D4", "D5"],
        "current-world media closure claim drift")
    if verify:
        require(value == derive(), "current-world media closure receipt is stale")


def receipt_mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "claim-card": lambda x: x["attempt_accounting"].update(
            additional_product_cards=1),
        "claim-link": lambda x: x["attempt_accounting"].update(
            additional_product_links=1),
        "claim-device": lambda x: x["attempt_accounting"].update(
            hardware_runs=1),
        "promote-Link97": lambda x: x["Link97_closure_retirement"].update(
            current_world_authority=True),
        "escape-completion-domain": lambda x: x["completion"].update(
            changes_outside_domain=1),
        "drop-role": lambda x: x["shared_system"].update(artifact_count=18),
        "cross-world": lambda x: x["pair_identity"].update(result="mismatch"),
        "drop-library-row": lambda x: x["pair_identity"].update(index_rows=3),
        "reorder-session": lambda x: x["session"]["rows"].reverse(),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        candidate = deepcopy(value)
        mutate(candidate)
        try:
            validate(candidate, verify=False)
        except MediaClosureError:
            rejected.append(name)
    require(rejected == list(cases), "media receipt mutation survived")
    return rejected


def producer_owned_outputs() -> dict[str, Path]:
    """Enumerate every output root owned by the Base media producer."""
    return {"build_tree": BUILD, "product_manifest": MANIFEST,
            "session": SESSION, "receipt": RECEIPT}


def require_clean_build_lifecycle() -> dict[str, str]:
    """The real one-shot predicate, shared verbatim with host preflight."""
    outputs = producer_owned_outputs()
    require(set(outputs) == {
                "build_tree", "product_manifest", "session", "receipt"}
            and all(not path.exists() for path in outputs.values()),
            "current-world completion/media closure is one-shot")
    return {name: path.as_posix() for name, path in outputs.items()}


def build_action() -> int:
    require_clean_build_lifecycle()
    card_authority()
    source_gate()
    source_mutations()
    completion = CARD.BUILD / "receipts/artifact-completion.json"
    if completion.is_file() and (CARD.BUILD / "final").is_dir():
        require(
            load(completion).get("status")
                == "passed-no-relink-publish-last-artifact-completion",
            "existing artifact completion is not resumable green")
        completion_delta()
    else:
        fresh_completion()
    _paths, can = configure_candidate()
    build_product_manifest(can)
    configure_media(can)
    shared = MEDIA.build()
    require(shared["artifact_count"] == 19,
            "current-world shared media role count drift")
    build_id = product_build_id()
    library_facts(build_id, existing=False)
    SESSION.write_bytes(canonical(session_value()))
    value = derive(configured=True)
    validate(value, verify=False)
    value["mutations_rejected"] = receipt_mutations(value)
    RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    RECEIPT.write_bytes(canonical(value))
    print("2.0 current-world media: PASS roles=19 rows=4 same-world D1-D5")
    return 0


def check() -> int:
    value = load(RECEIPT)
    rejected = value.pop("mutations_rejected", None)
    validate(value, verify=True)
    require(rejected == receipt_mutations(value),
            "media receipt mutation set drift")
    print("2.0 current-world media check: PASS roles=19 rows=4 same-world")
    return 0


def selftest() -> int:
    card_authority()
    source_gate()
    require(len(source_mutations()) == 4,
            "media source mutation count drift")
    print("2.0 current-world media selftest: PASS mutations=4")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("build", "check", "selftest", "_complete"))
    action = parser.parse_args().action
    if action == "build":
        result = build_action()
        fresh = subprocess.run(
            [sys.executable, str(DRIVER), "check"], cwd=ROOT,
            text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            check=False)
        require(fresh.returncode == 0,
                "fresh media readback red:\n" + fresh.stdout)
        print(fresh.stdout.strip())
        return result
    if action == "_complete":
        return complete_action()
    return {"check": check, "selftest": selftest}[action]()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        MediaClosureError, CARD.CarveoutCardError, MEDIA.MediaError,
        LIB.MediaClosureError, RuntimeError, OSError, ValueError, KeyError,
        json.JSONDecodeError, subprocess.SubprocessError,
    ) as error:
        print("2.0 current-world media: FIRST RED: " + str(error))
        raise SystemExit(2)
