#!/usr/bin/env python3
"""Pack artifact-only media from the accepted nested-MAP final pair."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_v160_nested_map_swap_replacement_card as CARD  # noqa: E402
import c2_v160_refill_boundary_witness_media_repair as REPAIR  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402


RED = REPAIR.RED
BASE = REPAIR.BASE
ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v1.6.0-freight-work-plan.md"
CARD_BUILD = CARD.BUILD
WPLTO = CARD_BUILD / "wplto"
STATIC = CARD_BUILD / "static-plane/narrow-static"
BUILD = ROOT / "build/c2.3/v1.6-nested-map-swap-media-replacement2"
RECEIPT = ARCH / "c2.3-v1.6-nested-map-swap-media-receipt.json"
SESSION = ROOT / "config/c2-v160-nested-map-swap-session.json"
CLOSURE = ARCH / "c2.3-v1.6-nested-map-swap-acceptance-union-resume.json"
ACCEPTANCE = CARD_BUILD / "artifact-acceptance.json"
AUTHORIZATION = "f8ded60b"
PRODUCT_REMOTE = "V16MAP.D81"
LIBRARY_REMOTE = "V16MAL.D81"
EXPECTED = {
    "PRG": (41566, "7591b37a611f26735fbd43731dc7cb2ff2a71423eb8caf8cd70dc577c3eb9cce"),
    "ELF": (646992, "92e8dc7abe8dfe1ffe9a20db7be3fa723867db3ae685ec7c92a732b8e807a2a9"),
}
STATUS = "PASS: V1.6 NESTED MAP SEAM CONFIRMATION MEDIA READY"
FIRST_RED = ARCH / "c2.3-v1.6-nested-map-swap-media-first-red.json"


def require(value: bool, message: str) -> None:
    if not value:
        raise RuntimeError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def authority() -> dict[str, Any]:
    name = PLAN.relative_to(ROOT).as_posix()
    commit = subprocess.run(["git", "rev-parse", f"{AUTHORIZATION}^{{commit}}"],
        cwd=ROOT, check=True, text=True, stdout=subprocess.PIPE).stdout.strip()
    raw = subprocess.run(["git", "show", f"{commit}:{name}"], cwd=ROOT,
        check=True, stdout=subprocess.PIPE).stdout
    text = " ".join(raw.decode().lower().replace("`", "").replace(
        "*", "").split())
    for token in ("artifact-only replacement media",
                  "short confirmation contact", "witness removal card"):
        require(token in text, f"nested-MAP media authority absent: {token}")
    return {"authority": "git-blob", "commit": commit, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def configure_candidate() -> None:
    """Reconstruct the configuration consumed by the frozen final link."""
    CARD.install()
    CARD.PREV.configure_module()
    core, _activation = BASE.REOPEN.configure_stack(CARD_BUILD, CARD.PREFLIGHT)
    core.PRODUCT.BASE.configure()
    BASE.CAN.REPLAY.PROFILE.configure()
    if BASE.PRODUCT.PROFILE_RODATA_BYTES == 342:
        BASE.PRODUCT.configure_require_resolver_profile_geometry()
        BASE.PRODUCT.configure_defstruct_foundation_profile_geometry()
    BASE.CAN.REPLAY.BANK2.configure_bank2_stage()
    BASE.CAN.REPLAY.TWO.configure_two_region()
    BASE.CAN.REPLAY.LINK60.configure_current_pin_adapters()
    BASE.PRODUCT.configure_intern_session_service()
    BASE.PRODUCT.configure_full_map_ownership()
    BASE.PRODUCT.configure_low_resident_lma_reset()
    BASE.HEADER.configure_consumption()
    BASE.PRODUCT.PRODUCT_ARTIFACTS_MANIFEST = (
        STATIC / "product/substitution-artifacts.json")
    BASE.PRODUCT.INITIAL_C2D = STATIC / "product/initial.c2d-v3.bin"
    BASE.PRODUCT.PRODUCT_SHELF = STATIC / "product/product-shelf-v4-direct.bin"
    elf = WPLTO / "lisp65-c2-substitution-linked.prg.elf"
    section = ElfTruth.read(elf,
        llvm_readobj=ROOT / "tools/llvm-mos/bin/llvm-readobj").section(
            BASE.PRODUCT.VERIFIER_BINDING_SECTION)
    BASE.PRODUCT.VERIFIER_BINDING_BASE = section.address
    BASE.PRODUCT.LINK60_VERIFIER_BINDING_BASE = section.address
    require(section.bytes == 40, "candidate verifier-binding size drift")


def complete() -> dict[str, Any]:
    BASE.configure_paths()
    product = WPLTO / "lisp65-c2-substitution-linked.prg"
    elf = Path(str(product) + ".elf")
    require((product.stat().st_size, BASE.sha(product)) == EXPECTED["PRG"]
            and (elf.stat().st_size, BASE.sha(elf)) == EXPECTED["ELF"],
            "accepted nested-MAP pair drift")
    configure_candidate()
    closure = load(CLOSURE)
    acceptance = load(ACCEPTANCE)
    projection = acceptance["VMA_golden"]
    require(closure["status"] ==
                "PASS: NESTED MAP ACCEPTANCE ACTIVE-REGISTRY UNION"
            and closure["frozen_pair_before"] == closure["frozen_pair_after"]
            and closure["MAP_fix_closed"] is True
            and acceptance["status"] == "PASS"
            and acceptance["additive_card_freight"]["candidate_sections"] == 107,
            "nested-MAP closure or Acceptance drift")

    class AcceptedProjection:
        @staticmethod
        def compare_elf(candidate: Path) -> dict[str, Any]:
            require((candidate.stat().st_size, BASE.sha(candidate)) ==
                    EXPECTED["ELF"],
                    "Completion received a different nested-MAP ELF")
            return projection

    accepted = AcceptedProjection()
    BASE.SOURCE_MEDIA.FLOW.BASE.INV = accepted
    BASE.CRC_MEDIA.INV = accepted
    BASE.SOURCE_MEDIA.card_projection = lambda: {
        "acceptance": {"VMA_golden": projection}}
    original_configure = BASE.CAN.REPLAY.configure
    original_fixed = BASE.PRODUCT.FIXED_BLOCK_LEAF.audit_elf
    original_facade = BASE.PRODUCT.fixed_facade_gate

    def fixed(candidate: Path, **kwargs: Any) -> dict[str, Any]:
        return BASE.SOURCE_MEDIA._link105_fixed_audit(
            original_fixed, candidate, **kwargs)

    def facade(out: Path, target: Path, suffix: str) -> dict[str, Any]:
        value = BASE.CRC_MEDIA._current_facade_gate(
            original_facade, out, target, suffix)
        value["packed_PRG_facade"] = REPAIR.packed_facade_gate(
            target, Path(str(target) + ".elf"))
        return value

    BASE.CAN.REPLAY.configure = lambda: None
    BASE.PRODUCT.FIXED_BLOCK_LEAF.audit_elf = fixed
    BASE.PRODUCT.fixed_facade_gate = facade
    try:
        value = BASE.CAN.complete_artifacts()
    finally:
        BASE.CAN.REPLAY.configure = original_configure
        BASE.PRODUCT.FIXED_BLOCK_LEAF.audit_elf = original_fixed
        BASE.PRODUCT.fixed_facade_gate = original_facade
    final_product = BASE.CAN.FINAL / product.name
    final_elf = Path(str(final_product) + ".elf")
    require((final_elf.stat().st_size, BASE.sha(final_elf)) == EXPECTED["ELF"]
            and value["compiler_runs"] == value["linker_runs"] == 0,
            "artifact-only Completion rebuilt the nested-MAP pair")
    REPAIR.packed_facade_gate(final_product, final_elf)
    return value


def materialize_candidate_publish_predecessors(final: Path, product: Path,
                                               elf: Path) -> dict[str, Any]:
    """Materialize the facade across every candidate-declared publish domain."""
    unbound = final / "lisp65-c2-substitution-unbound.prg"
    window_bound = final / "lisp65-c2-substitution-window-bound.prg"
    kernal_path = final / "kernal-window-publish-last.json"
    verifier_path = final / "runtime-verifier-publish-last.json"
    require(all(path.is_file() for path in (
                unbound, window_bound, kernal_path, verifier_path)),
            "candidate publish-last predecessors are absent")
    kernal = load(kernal_path)
    verifier = load(verifier_path)
    frozen_kernal = bind(kernal_path)
    unbound_report = REPAIR.materialize_facade(
        unbound, elf, final / "packed-prg-unbound-facade-materialization.json")
    window_report = REPAIR.materialize_facade(
        window_bound, elf,
        final / "packed-prg-window-facade-materialization.json")
    product_report = REPAIR.materialize_facade(
        product, elf, final / "packed-prg-facade-materialization.json")
    before = unbound.read_bytes(); after = product.read_bytes()
    changed = {index for index, pair in enumerate(zip(before, after))
               if pair[0] != pair[1]}
    kernal_domain = {int(row["file_offset"])
                     for row in kernal["binding_operands"]}
    verifier_domain = set(range(int(verifier["file_offset"]),
                                int(verifier["file_offset"]) +
                                int(verifier["bytes"])))
    allowed = kernal_domain | verifier_domain
    require(changed <= allowed
            and len(changed & kernal_domain) == kernal["actual_changed_bytes"]
            and len(changed & verifier_domain) == verifier["changed_bytes"],
            "facade predecessor escaped candidate publish-last domains")
    prior = deepcopy(kernal)
    prior["unbound_product_sha256"] = hashlib.sha256(before).hexdigest()
    prior["window_bound_product_sha256"] = hashlib.sha256(
        window_bound.read_bytes()).hexdigest()
    prior["completion_facade_predecessor"] = {
        "authority": AUTHORIZATION, "source": REPAIR.FACADE_SECTION,
        "bytes": REPAIR.FACADE_BYTES, "frozen_receipt": frozen_kernal,
        "declared_publish_domains": ["kernal-window", "runtime-verifier"],
        "changed_bytes": len(changed),
        "rule": "facade precedes every candidate-declared publish-last domain"}
    kernal_path.write_bytes(canonical(prior))
    verifier["pre_overlay_binding_sha256"] = hashlib.sha256(
        window_bound.read_bytes()).hexdigest()
    verifier["bound_sha256"] = hashlib.sha256(after).hexdigest()
    verifier_path.write_bytes(canonical(verifier))
    report = {"format": "lisp65-v1.6-candidate-publish-domain-rebind-v1",
        "status": "passed-candidate-declared-publish-domains",
        "unbound": unbound_report, "window_bound": window_report,
        "final_product": product_report,
        "changed_bytes": len(changed), "allowed_domain_bytes": len(allowed),
        "kernal_changed_bytes": len(changed & kernal_domain),
        "verifier_changed_bytes": len(changed & verifier_domain),
        "frozen_wplto_unchanged": True}
    (final / "packed-prg-facade-predecessor-rebind.json").write_bytes(
        canonical(report))
    return report


def completion_with_facade() -> dict[str, Any]:
    original = BASE.CAN.complete_artifacts

    def materializing_completion() -> dict[str, Any]:
        original_gate = BASE.PRODUCT.fixed_facade_gate

        def shipped_gate(out: Path, target: Path, suffix: str) -> dict[str, Any]:
            elf = Path(str(target) + ".elf")
            report = out / "packed-prg-facade-materialization.json"
            if not report.exists():
                materialize_candidate_publish_predecessors(out, target, elf)
            value = original_gate(out, target, suffix)
            value["packed_PRG_facade"] = REPAIR.packed_facade_gate(target, elf)
            return value

        BASE.PRODUCT.fixed_facade_gate = shipped_gate
        try:
            return original()
        finally:
            BASE.PRODUCT.fixed_facade_gate = original_gate

    BASE.CAN.complete_artifacts = materializing_completion
    try:
        return complete()
    finally:
        BASE.CAN.complete_artifacts = original


def session_config(product: Path, library: Path) -> dict[str, Any]:
    value = RED.PREV.session_config(product, library)
    value["format"] = "lisp65-c2-v160-nested-map-seam-session-v1"
    value["recorded_on"] = "2026-08-23"
    value["media"]["product"]["remote_name"] = PRODUCT_REMOTE
    value["media"]["library"]["remote_name"] = LIBRARY_REMOTE
    value["claim_scope"] = {"accepts": ["nested-MAP-seam-confirmation"],
        "excludes": ["v1.6-items-1-2", "release-acceptance"]}
    value["rows"] = [
        {"id": "M1-boot", "action": "cold boot product and mount library",
         "expect": "native lisp65> prompt"},
        {"id": "M2-load", "action":
            "submit (require 'v16core), then (require 'repl-comfort)",
         "expect": "t after each form"},
        {"id": "M3-seam", "action": "submit (repl) and make no further input",
         "expect": "visible l65> prompt; no red frame at the former MAP seam"},
    ]
    return value


def configure() -> None:
    REPAIR.BUILD = BUILD
    REPAIR.RECEIPT = RECEIPT
    REPAIR.SESSION = SESSION
    REPAIR.PRODUCT_REMOTE = PRODUCT_REMOTE
    REPAIR.LIBRARY_REMOTE = LIBRARY_REMOTE
    RED.BUILD = BUILD; RED.CARD_BUILD = CARD_BUILD; RED.WPLTO = WPLTO
    RED.STATIC = STATIC; RED.CLOSURE = CLOSURE; RED.EXPECTED = EXPECTED
    RED.configure_candidate = configure_candidate
    RED.complete = complete
    RED.product_manifest = RED.product_manifest
    RED.session_config = session_config
    REPAIR.configure()
    BASE.complete = completion_with_facade
    BASE.product_manifest = RED.product_manifest
    BASE.session_config = session_config


def preflight() -> None:
    configure()
    require(not BUILD.exists() and not RECEIPT.exists() and not SESSION.exists(),
            "nested-MAP media preparation is one-shot")
    closure = load(CLOSURE)
    require(closure["MAP_fix_closed"] is True,
            "nested-MAP closure is not green")
    product = WPLTO / "lisp65-c2-substitution-linked.prg"
    elf = Path(str(product) + ".elf")
    require((product.stat().st_size, BASE.sha(product)) == EXPECTED["PRG"]
            and (elf.stat().st_size, BASE.sha(elf)) == EXPECTED["ELF"],
            "nested-MAP media input pair drift")
    require(REPAIR.mutation_selftest(product, elf)["cases"] == 2,
            "packed-facade preflight drift")
    print("v1.6 nested-MAP media: PREFLIGHT PASS artifact-only")


def build() -> None:
    configure()
    value = BASE.build()
    finalize(value)
    print("v1.6 nested-MAP media: PASS media=2 contact=seam-confirmation")


def finalize(value: dict[str, Any] | None = None) -> None:
    """Seal already-built media without invoking its one-shot producer."""
    configure()
    value = load(RECEIPT) if value is None else value
    completion = load(ROOT / value["completion"]["path"])
    require(value.get("status") == "PASS: V1.6 ITEMS 1/2 DEVICE CONTACT READY"
            and completion.get("compiler_runs") == 0
            and completion.get("linker_runs") == 0,
            "artifact-only base media receipt is not sealable")
    product = BASE.CAN.FINAL / "lisp65-c2-substitution-linked.prg"
    elf = Path(str(product) + ".elf")
    value.update({"format": "lisp65-c2-v160-nested-map-swap-media-v1",
        "recorded_on": "2026-08-23", "successor_authority": authority(),
        "MAP_closure": bind(CLOSURE),
        "shipped_byte_facade": REPAIR.packed_facade_gate(product, elf),
        "facade_mutations": REPAIR.mutation_selftest(product, elf),
        "accounting": {"WPLTO_runs": 0, "product_links": 0,
            "product_cards": 0, "replacement_media_builds": 2,
            "device_contacts": 0}, "status": STATUS})
    RECEIPT.write_bytes(canonical(value))


def check() -> dict[str, Any]:
    configure()
    value = load(RECEIPT)
    require(value["status"] == STATUS and value["accounting"] == {
                "WPLTO_runs": 0, "product_links": 0, "product_cards": 0,
                "replacement_media_builds": 2, "device_contacts": 0},
            "nested-MAP media receipt drift")
    for row in [value["completion"], value["media_closure"],
                *value["media"].values(), value["session"], value["MAP_closure"]]:
        require(bind(ROOT / row["path"]) == row,
                f"nested-MAP prepared artifact drift: {row['path']}")
    product = BASE.CAN.FINAL / "lisp65-c2-substitution-linked.prg"
    elf = Path(str(product) + ".elf")
    require(value["shipped_byte_facade"] ==
                REPAIR.packed_facade_gate(product, elf)
            and value["facade_mutations"] ==
                REPAIR.mutation_selftest(product, elf),
            "nested-MAP shipped facade gate drift")
    pair = BASE.PAIR.pair_identity(ROOT / value["media"]["product"]["path"],
                                   ROOT / value["media"]["library"]["path"])
    require(pair == value["same_world_pair"], "nested-MAP media pair drift")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("preflight", "build", "finalize", "check"))
    action = parser.parse_args().action
    if action == "preflight": preflight()
    elif action == "build": build()
    elif action == "finalize":
        finalize(); print("v1.6 nested-MAP media: FINALIZE PASS no-rebuild")
    else: check(); print("v1.6 nested-MAP media: CHECK PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
