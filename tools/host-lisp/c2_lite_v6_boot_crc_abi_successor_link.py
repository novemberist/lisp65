#!/usr/bin/env python3
"""Build the one owner-authorized C2-lite boot-CRC ABI successor link.

The link consumes the current Bank-3 two-record staging profile, projects the
C2D-v6 product sources, runs one resident-island seed link plus exactly one
product-closure link, publishes the 42-byte post-link domain, and then reruns
every generic, C2-lite, staging, assembler-ABI and actual-Workbench CRC gate.
It never runs hardware or promotes the result.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import struct
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_asm_leaf_abi_gate as ABI  # noqa: E402
import c2_crc_asm_leaf_gate as CRC  # noqa: E402
import c2_lite_root_surrogate as ROOT_GATE  # noqa: E402
import c2_lite_v6_bank3_artifact_completion as ART  # noqa: E402
import c2_lite_v6_bank3_staging_wplto_probe as STAGE  # noqa: E402
import c2_lite_v6_boot_crc_abi_wplto as ABI_WPLTO  # noqa: E402
import c2_lite_v6_coresident_diet_probe as DIET  # noqa: E402
import c2_lite_v6_direct_entry_contract as LITE_DIRECT  # noqa: E402
import c2_lite_v6_first_product_link as LINK  # noqa: E402
import c2_lite_v6_first_product_link_successor as B2  # noqa: E402
import c2_lite_v6_first_product_link_successor2 as DIRECT  # noqa: E402
import c2_lite_v6_product_probe as V6  # noqa: E402
import c2_product_hw_presmoke as HW  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402


P = STAGE.P
OUT = ROOT / "build/c2.2/substitution/product-link-38-c2-lite-v6-boot-crc-abi"
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
RECEIPT = EVIDENCE / (
    "c2.2-product-link38-c2-lite-v6-boot-crc-abi-structural-receipt.json")
BASELINE = ROOT / (
    "build/c2.2/substitution/"
    "c2-lite-v6-bank3-stage-artifact-candidate-replay5/"
    "lisp65-c2-substitution-linked.prg")
BASELINE_SHA = "62f556dfcdeec59783cc2adec16afc3ccb5f618a24b17898c1162f81c1c1b954"
BASELINE_RECEIPT = EVIDENCE / (
    "c2.2-c2-lite-v6-bank3-stage-artifact-completion-"
    "replay5-structural-receipt.json")
BASELINE_RECEIPT_SHA = (
    "e852ffd7ceeeee4a689790b0ee50c966a470bc1e14a82087844556b0533fd0e8")
WPLTO_FIRST_RED = EVIDENCE / (
    "c2.2-c2-lite-v6-bank3-boot-crc-abi-wplto-replay2-receipt.json")
WPLTO_FIRST_RED_SHA = (
    "d7113a7a4219f5bbd6ea9c7edd9bf65e2acf447e3b31709b890b819225a80e39")
CAPACITY_DIAGNOSIS = EVIDENCE / (
    "c2.2-c2-lite-v6-bank3-boot-crc-abi-wplto-capacity-diagnosis.json")
CAPACITY_DIAGNOSIS_SHA = (
    "f09a033408ca9224f64a9fc6bccf65af9d5418d12027d0f99d55abd526af9e0f")
DIRECT_RECEIPT_SHA = (
    "2777b476653d668cce6df6cf03a6722e84968a255995299db52133d2159cfdf2")
CAP = 1792
BANK_BYTES = 65536
E000_FLOOR = 115
VERIFIER_BASE = 0xB9CD
EXPECTED_DIRECT_REFS = 637


class LinkError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise LinkError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"successor-link artifact absent: {path}")
    return {"path": path.relative_to(ROOT).as_posix(),
            "bytes": path.stat().st_size, "sha256": sha(path)}


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")


def tree(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    return {item.relative_to(path).as_posix(): {
                "bytes": item.stat().st_size, "sha256": sha(item)}
            for item in sorted(path.rglob("*")) if item.is_file()}


def protect() -> None:
    if OUT.is_dir():
        LINK.BASE.protect(OUT)
    if RECEIPT.is_file():
        os.chmod(RECEIPT, 0o444)


def prerequisites() -> dict[str, Any]:
    expected = {
        BASELINE: BASELINE_SHA,
        BASELINE_RECEIPT: BASELINE_RECEIPT_SHA,
        WPLTO_FIRST_RED: WPLTO_FIRST_RED_SHA,
        CAPACITY_DIAGNOSIS: CAPACITY_DIAGNOSIS_SHA,
        LITE_DIRECT.RECEIPT: DIRECT_RECEIPT_SHA,
    }
    for path, digest in expected.items():
        require(path.is_file() and sha(path) == digest,
                f"successor-link authority drift: {path}")
    diagnosis = json.loads(CAPACITY_DIAGNOSIS.read_text(encoding="utf-8"))
    require(diagnosis["status"] ==
            "FIRST RED: ABI leaf is size-neutral but WPLTO text wall moved"
            and diagnosis["correction"]["vm_boot_overlay_chain_commit"]
                ["delta_bytes"] == 0
            and diagnosis["wplto_capacity"]["walls_after"]
                ["bank0_text_headroom_bytes"] == 1
            and diagnosis["scope"]["product_links"] == 0,
            "accepted 1-byte WPLTO truth drift")
    baseline = json.loads(BASELINE_RECEIPT.read_text(encoding="utf-8"))
    require(baseline["status"] ==
            "passed-complete-c2-lite-bank3-candidate-hardware-not-run"
            and baseline["product_identity"]["product"]["sha256"]
                == BASELINE_SHA,
            "rollback candidate authority is not green")
    return {
        "accepted_one_byte_wplto_truth": bind(CAPACITY_DIAGNOSIS),
        "wplto_first_red": bind(WPLTO_FIRST_RED),
        "rollback_candidate": bind(BASELINE),
        "rollback_candidate_receipt": bind(BASELINE_RECEIPT),
        "current_direct_entry_receipt": bind(LITE_DIRECT.RECEIPT),
        "driver": bind(Path(__file__)),
    }


def configure_profile() -> tuple[str, ...]:
    STAGE.apply_profile(LINK.BASE.configure)
    P.VERIFIER_BINDING_BASE = VERIFIER_BASE
    require(P.FAMILY_STAGE_BINDINGS
            and P.runtime_binding_bytes() == 40
            and P.total_publish_last_bytes() == 42
            and P.E000_FINAL_FLOOR_BYTES == E000_FLOOR,
            "current Bank-3 C2-lite profile drift")
    return STAGE.feature_set()


def install_profile_binding_wrappers() -> tuple[Any, Any]:
    generic_patch = P.patch_verifier_binding_table
    generic_total = P.total_publish_last_gate

    def profile_patch(*args: Any, **kwargs: Any) -> dict[str, object]:
        kwargs["expected_base"] = VERIFIER_BASE
        return generic_patch(*args, **kwargs)

    def profile_total(*args: Any, **kwargs: Any) -> dict[str, object]:
        kwargs["expected_verifier_base"] = VERIFIER_BASE
        return generic_total(*args, **kwargs)

    P.patch_verifier_binding_table = profile_patch
    P.total_publish_last_gate = profile_total
    return generic_patch, generic_total


def fresh_prelink_gates() -> dict[str, Any]:
    mutations = ABI.selftest()
    stage_state = STAGE.state_machine_gate()
    stage_source = STAGE.source_contract_gate()
    old_link_out, old_v6_out, old_diet_out = LINK.OUT, V6.OUT, DIET.OUT
    old_emitter, old_emitter_path = V6._ENTRY_EMITTER, V6._ENTRY_EMITTER_PATH
    try:
        LINK.OUT = OUT
        V6.OUT = OUT / "fresh-c2-lite-prelink-gates/v6-semantics"
        DIET.OUT = OUT / "fresh-c2-lite-prelink-gates/slice-and-publication"
        V6.OUT.mkdir(parents=True)
        DIET.OUT.mkdir(parents=True)
        V6._ENTRY_EMITTER = None
        V6._ENTRY_EMITTER_PATH = None
        host = V6.host_semantics()
        lifetime = V6.bank3_lifetime()
        source = DIET.source_contract_gate()
        cutpoints = DIET.cutpoint_gates()
        shared = DIET.shared_semantics_gate()
        root = ROOT_GATE.collect()
    finally:
        LINK.OUT, V6.OUT, DIET.OUT = old_link_out, old_v6_out, old_diet_out
        V6._ENTRY_EMITTER, V6._ENTRY_EMITTER_PATH = old_emitter, old_emitter_path
    b2 = B2.current_b2_gate(OUT / "fresh-v5-b2-prelink-gates")
    direct = LITE_DIRECT.value()
    require(host["status"] == "passed"
            and host["rollback"]["count"] == 8
            and lifetime["status"] == "passed-lifetime-exclusive"
            and source["status"] == cutpoints["status"]
                == shared["status"] == "passed"
            and root["status"] == "pass"
            and stage_state["cases"] == 8
            and len(stage_source["checks"]) == 14
            and len(stage_source["mutations_rejected"]) == 5
            and b2["b2_model"]["cases"] == 18
            and direct["cross_parity"]["direct_entry_references"]
                == EXPECTED_DIRECT_REFS,
            "fresh successor prelink gate red")
    return {
        "status": "passed",
        "assembler_leaf_abi_mutations": mutations,
        "bank3_stage_state": stage_state,
        "bank3_stage_source": stage_source,
        "c2d_v6_host_semantics": host,
        "bank3_lifetime_model": lifetime,
        "source_contract": source,
        "semantic_split_and_fusion_cutpoints": cutpoints,
        "stage_before_publish_and_one_emitter": shared,
        "root_surrogate_complete_domain": root,
        "b2_run_stop": b2,
        "direct_entry": direct["cross_parity"],
    }


def walls_and_family(elf: Path) -> tuple[dict[str, int], dict[str, Any]]:
    sections = P.section_table(elf)
    text, bss = sections[".text"], sections[".bss"]
    walls = {
        "bank0_text_headroom_bytes":
            P.HANDOFF_BASE - text["address"] - text["bytes"],
        "ordinary_bank0_bss_headroom_bytes":
            P.FIXED_BANK0_BASE - bss["address"] - bss["bytes"],
        "fixed_hot_block_headroom_bytes": P.fixed_bank0_headroom_bytes(),
        "resident_island_headroom_bytes": 2048 - sum(
            sections.get(name, {}).get("bytes", 0) for name in
            (".lisp65_resident_island", ".lisp65_resident_island_annex")),
        "e000_headroom_bytes": P.KERNAL_WINDOW_BYTES - sum(
            sections[name]["bytes"] for name in P.KERNAL_SECTIONS),
    }
    require(all(value >= 0 for key, value in walls.items()
                if key != "e000_headroom_bytes")
            and walls["e000_headroom_bytes"] >=
                P.E000_FINAL_FLOOR_BYTES,
            f"FIRST RED: successor resident wall red: {walls}")
    names = {spec.split(":")[2] for spec in
             P.BOOT_SLICE_SPECS + P.SESSION_SLICE_SPECS}
    sizes = {name: sections.get(name, {}).get("bytes", 0) for name in names}
    bad = {name: size for name, size in sizes.items()
           if size <= 0 or size > CAP}
    require(not bad, f"FIRST RED: successor slice wall red: {bad}")
    boot_path = OUT / "runtime-overlays-boot-final.bin"
    session_path = OUT / "runtime-overlays-session-final.bin"
    boot = json.loads((OUT / "runtime-overlays-boot-final.json").read_text())
    session = json.loads(
        (OUT / "runtime-overlays-session-final.json").read_text())
    require(boot_path.stat().st_size == boot["storage"]["size"] <= BANK_BYTES
            and session_path.stat().st_size == session["storage"]["size"]
                <= BANK_BYTES,
            "FIRST RED: successor Bank-3 family aggregate red")
    return walls, {
        "runtime_slices": {
            "count": len(sizes), "cap_bytes": CAP,
            "largest_bytes": max(sizes.values()),
            "minimum_headroom_bytes": CAP - max(sizes.values())},
        "successor_bank3_pack": {
            "boot": {**bind(boot_path),
                     "headroom_bytes": BANK_BYTES - boot_path.stat().st_size},
            "session": {**bind(session_path),
                        "headroom_bytes": BANK_BYTES
                            - session_path.stat().st_size}},
    }


def workbench_crc_gate(product: Path, elf: Path) -> dict[str, Any]:
    payload = ABI_WPLTO.payload(product, elf)
    expected = CRC.crc_reference(payload)
    truth = ElfTruth.read(elf, llvm_readobj=P.TOOLCHAIN / "llvm-readobj")
    descriptor = HW.boot_overlay_descriptor(
        build_id=int(sha(OUT / "resolved-profile.txt")[:8], 16),
        start=truth.symbol("__lisp65_workbench_overlay_start").value,
        entry=truth.symbol("vm_workbench_boot_overlay_entry").value,
        payload=payload)
    descriptor_crc = struct.unpack_from("<H", descriptor, 16)[0]
    require(descriptor_crc == expected, "successor Workbench descriptor CRC red")
    prior = dict(CRC.VECTORS)
    CRC.VECTORS["actual-workbench-overlay"] = payload
    try:
        report = CRC.audit_elf(
            elf, out=OUT / "c2-crc-asm-leaf-workbench-gate.json")
    finally:
        CRC.VECTORS.clear()
        CRC.VECTORS.update(prior)
    witness = report["vectors"]["actual-workbench-overlay"]
    require(witness["bytes"] == len(payload)
            and witness["crc16"] == expected,
            "successor linked CRC leaf/Workbench parity red")
    return {
        "status": "passed-linked-leaf-equals-current-descriptor-emitter",
        "payload_bytes": len(payload), "payload_crc16": expected,
        "payload_sha256": hashlib.sha256(payload).hexdigest(),
        "descriptor_sha256": hashlib.sha256(descriptor).hexdigest(),
        "linked_leaf_executed_instructions": witness["executed_instructions"],
    }


def replacement_gates(product: Path, elf: Path,
                      host: dict[str, Any]) -> dict[str, Any]:
    walls, family = walls_and_family(elf)
    shape = {"walls": walls, "runtime_slices": family["runtime_slices"],
             "successor_bank3_pack": family["successor_bank3_pack"]}
    capacity = DIET.capacity_gate(shape, elf)
    semantics = DIET.semantic_product_gate(shape, product, elf)
    no_attic = LINK.no_runtime_attic_gate(
        elf, OUT / "generated-product-sources")
    stage = ART.stage_product_gate(elf)
    overlay = LINK.BASE.LINK33_BASE.final_overlay_closure(elf)
    preinstall = LINK.BASE.ISLAND.static_elf_gate(elf)
    root = ROOT_GATE.collect()
    old_direct_out = DIRECT.OUT
    try:
        DIRECT.OUT = OUT
        direct = DIRECT.generated_direct_entry_gate()
    finally:
        DIRECT.OUT = old_direct_out
    crc = workbench_crc_gate(product, elf)
    require(capacity["status"] == semantics["status"] == "passed"
            and no_attic["status"].startswith("passed")
            and stage["status"] == "passed"
            and overlay["status"] == "passed-final-elf-overlay-closure"
            and preinstall["status"]
                == "passed-static-preinstallation-Island-gate"
            and root["status"] == "pass"
            and direct["status"].startswith("passed")
            and crc["status"].startswith("passed"),
            "fresh successor replacement gate set red")
    return {
        "status": "passed",
        "walls": walls,
        "runtime_family": family,
        "capacity": capacity,
        "product_semantics": semantics,
        "no_runtime_attic": no_attic,
        "bank3_stage_before_publish": stage,
        "overlay_closure": overlay,
        "preinstallation_island": preinstall,
        "root_surrogate": root,
        "generated_direct_entry": direct,
        "workbench_crc_end_to_end": crc,
        "generation": {
            "old_handles_rejected": host["c2d_v6_host_semantics"]
                ["stale_generation"]["old_handles_rejected"],
            "boot_binding_invalidated_before_session": host
                ["bank3_lifetime_model"]["invalidation_before_overwrite"]},
    }


def first_red(error: BaseException, authority: dict[str, Any]) -> dict[str, Any]:
    product = OUT / "lisp65-c2-substitution-linked.prg"
    value = {
        "format": "lisp65-c2-lite-v6-boot-crc-abi-link38-first-red-v1",
        "recorded_on": "2026-07-21",
        "status": "FIRST RED: C2-lite boot-CRC ABI successor link stopped",
        "promotable": False,
        "diagnostic": {"type": type(error).__name__, "message": str(error)},
        "execution_accounting": {
            "product_closure_links": int(product.is_file()),
            "hardware_runs": 0,
            "latency_attempts_consumed": "0/2"},
        "authority": authority,
        "evidence": tree(OUT),
        "rollback_line": {**bind(BASELINE), "status": "untouched"},
        "conditional_next_gate": (
            "If and only if the diagnostic is a resident-capacity overflow, "
            "the owner-preauthorized small-hot-object E000 relocation probe "
            "may run; otherwise return to Class-C review."),
    }
    write_json(RECEIPT, value)
    protect()
    return value


def build() -> dict[str, Any]:
    require(not OUT.exists() and not RECEIPT.exists(),
            "Link 38 is one-shot and already has output")
    authority = prerequisites()
    OUT.mkdir(parents=True)
    original_sources = P.source_list
    original_patch, original_total = None, None
    old_direct_out = DIRECT.OUT
    try:
        features = configure_profile()
        original_patch, original_total = install_profile_binding_wrappers()
        prelink = fresh_prelink_gates()
        mapping = V6.generated_product_sources(OUT)

        def projected_sources(
                extra_definitions: tuple[str, ...] = ()) -> list[str]:
            return [str(mapping.get(Path(path).resolve(), Path(path)))
                    for path in original_sources(extra_definitions)]

        P.source_list = projected_sources
        DIRECT.OUT = OUT
        P.single_link(
            OUT, probe_definitions=features,
            direct_entry_receipt=LITE_DIRECT.RECEIPT,
            direct_entry_check_tool="c2_lite_v6_direct_entry_contract.py",
            extra_contract_lines=(
                "mode=link38-c2-lite-v6-boot-crc-abi-successor",
                "source_baseline=link37-bank3-artifact-candidate",
                "feature_defines=" + ",".join(features),
                "c2d_version=6",
                "runtime_refill_source=chip-bank2",
                "native_family_source=chip-bank3",
                "bank3_stage_records=2",
                "assembler_leaf_abi_gate=required",
                "workbench_crc_end_to_end=required",
                f"final_e000_floor_bytes={P.E000_FINAL_FLOOR_BYTES}",
                "green_inheritance=none"))
    except Exception as error:
        return first_red(error, authority)
    finally:
        P.source_list = original_sources
        DIRECT.OUT = old_direct_out
        if original_patch is not None:
            P.patch_verifier_binding_table = original_patch
        if original_total is not None:
            P.total_publish_last_gate = original_total

    product = OUT / "lisp65-c2-substitution-linked.prg"
    elf = Path(str(product) + ".elf")
    try:
        structure = json.loads(
            (OUT / "product-substitution-link.json").read_text())
        total = json.loads((OUT / "total-publish-last-domain.json").read_text())
        required = (
            "identity_gate", "capacity_gate", "one_truth_gate",
            "kernal_freedom_gate", "fixed_host_facade_gate",
            "pre_ownership_gate", "handoff_z_abi_gate")
        require(structure.get("status") == "passed"
                and structure.get("product_closure_link_count") == 1
                and all("pass" in str(structure.get(name, ""))
                        for name in required),
                "generic successor product closure is not fully green")
        require(total.get("status") == "passed"
                and total.get("declared_domain_bytes") == 42,
                "successor publish-last domain is not the complete 42-byte set")
        replacement = replacement_gates(product, elf, prelink)
        require(sha(product) != BASELINE_SHA
                and sha(BASELINE) == BASELINE_SHA,
                "successor identity or rollback line red")
        value = {
            "format": "lisp65-c2-lite-v6-boot-crc-abi-link38-structural-v1",
            "recorded_on": "2026-07-21",
            "status": "passed-new-c2-lite-boot-crc-abi-identity-hardware-not-run",
            "promotable": False,
            "link_number": 38,
            "inheritance": "none; every structural, capacity and replacement gate ran freshly",
            "execution_accounting": {
                "resident_island_seed_links": 1,
                "product_closure_links": 1,
                "hardware_runs": 0,
                "latency_attempts_consumed": "0/2"},
            "authority": authority,
            "product_identity": {
                "product": bind(product), "elf": bind(elf),
                "map": bind(Path(str(product) + ".map")),
                "resolved_profile": bind(OUT / "resolved-profile.txt"),
                "predecessor_sha256": BASELINE_SHA,
                "new_identity": True},
            "fresh_generic_gates": {
                name: structure[name] for name in required},
            "fresh_replacement_gates": replacement,
            "fresh_prelink_gates": prelink,
            "post_link_identity": {
                "declared_mutable_product_bytes": total["declared_domain_bytes"],
                "actual_changed_bytes": total["actual_changed_bytes"],
                "status": total["status"]},
            "rollback_line": {
                **bind(BASELINE), "status": "untouched-and-readable"},
            "claim_limit": (
                "One fresh product-closure link and complete structural, "
                "capacity, staging, assembler-ABI and actual-Workbench CRC "
                "closure only. Hardware, boot, latency, refill timing, GC, "
                "Freezer, nested eval, promotion and acceptance remain not-run."),
            "next_gate": "owner-authorized seven-line receipt-less hardware presmoke from line 1",
        }
        report = OUT / "link38-c2-lite-v6-boot-crc-abi-structural.json"
        write_json(report, value)
        receipt = {**value, "structural_report": bind(report),
                   "evidence_file_count": len(tree(OUT))}
        write_json(RECEIPT, receipt)
        protect()
        return receipt
    except Exception as error:
        return first_red(error, authority)


def main() -> int:
    try:
        value = build()
    except Exception as error:
        if OUT.exists() and not RECEIPT.exists():
            value = first_red(error, prerequisites())
        else:
            raise
    print("c2-lite-v6-boot-crc-abi-successor-link: " + value["status"])
    return 2 if value["status"].startswith("FIRST RED") else 0


if __name__ == "__main__":
    raise SystemExit(main())
