#!/usr/bin/env python3
"""Pure artifact replay for the completed Link-38 product bytes.

The sole product link already completed every generic gate and stopped only
when the historical direct-entry harness populated v5 root ordinals for the
generated C2D-v6 phase-12 checker.  This replay validates the protected tree,
checks the 637 direct values and the v6 root-surrogate seam without compiling,
and reruns artifact-side product gates.  It cannot compile or link.
"""

from __future__ import annotations

from collections import Counter
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
import c2_bcode_contract as BCODE  # noqa: E402
import c2_crc_asm_leaf_gate as CRC  # noqa: E402
import c2_direct_entry_contract as DIRECT  # noqa: E402
import c2_lite_v6_bank3_artifact_completion as ART  # noqa: E402
import c2_lite_v6_bank3_staging_wplto_probe as STAGE  # noqa: E402
import c2_lite_v6_boot_crc_abi_wplto as ABI_WPLTO  # noqa: E402
import c2_lite_v6_coresident_diet_probe as DIET  # noqa: E402
import c2_lite_v6_first_product_link as LINK  # noqa: E402
import c2_product_hw_presmoke as HW  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402


P = STAGE.P
SOURCE = ROOT / (
    "build/c2.2/substitution/"
    "product-link-38-c2-lite-v6-boot-crc-abi-replay")
FIRST_RED = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-product-link38-c2-lite-v6-boot-crc-abi-replay-structural-receipt.json")
OUT = ROOT / (
    "build/c2.2/substitution/"
    "product-link-38-c2-lite-v6-boot-crc-abi-artifact-replay")
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-product-link38-c2-lite-v6-boot-crc-abi-artifact-replay-receipt.json")
DIAGNOSIS = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-product-link38-c2-lite-v6-direct-entry-root-surrogate-diagnosis.json")
PRODUCT = SOURCE / "lisp65-c2-substitution-linked.prg"
ELF = Path(str(PRODUCT) + ".elf")
BASELINE = ROOT / (
    "build/c2.2/substitution/"
    "c2-lite-v6-bank3-stage-artifact-candidate-replay5/"
    "lisp65-c2-substitution-linked.prg")
BASELINE_SHA = "62f556dfcdeec59783cc2adec16afc3ccb5f618a24b17898c1162f81c1c1b954"
ROOT_SURROGATE_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-c2-lite-v6-product-shaped-probe-receipt.json")
ROOT_SURROGATE_RECEIPT_SHA = (
    "05007ac1b9f6ab43bb9095ed536728e15a73ca7cb0d91d90c9f918ff33cde913")
OBJ_H_SHA = "c780e3573fc4fa09c4b08ec7c5c80168afa74f1cc7e693e028e4c7066734c306"
CAP = 1792
BANK_BYTES = 65536
E000_FLOOR = 115


class ReplayError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ReplayError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"artifact replay input absent: {path}")
    return {"path": path.relative_to(ROOT).as_posix(),
            "bytes": path.stat().st_size, "sha256": sha(path)}


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")


def validate_source() -> dict[str, Any]:
    require(FIRST_RED.is_file() and PRODUCT.is_file() and ELF.is_file()
            and sha(BASELINE) == BASELINE_SHA,
            "artifact replay authority absent")
    first = json.loads(FIRST_RED.read_text(encoding="utf-8"))
    require(first["status"] ==
            "FIRST RED: C2-lite boot-CRC ABI successor link stopped"
            and first["diagnostic"] == {
                "message": "target contract harness failed: ",
                "type": "DirectEntryError"}
            and first["execution_accounting"]["product_closure_links"] == 1
            and first["execution_accounting"]["hardware_runs"] == 0,
            "artifact replay First Red drift")
    expected = first["evidence"]
    actual = {path.relative_to(SOURCE).as_posix()
              for path in SOURCE.rglob("*") if path.is_file()}
    require(actual == set(expected), "protected Link-38 tree membership drift")
    for relative, row in expected.items():
        path = SOURCE / relative
        require(path.stat().st_size == row["bytes"]
                and sha(path) == row["sha256"],
                f"protected Link-38 artifact drift: {relative}")
    generic = json.loads((SOURCE / "product-substitution-link.json").read_text())
    require(generic["status"] == "passed"
            and generic["product_closure_link_count"] == 1
            and generic["identity_components"]["assembler_leaf_abi_dataflow"]
                == "passed-all-assembler-leaf-abi-contracts"
            and generic["identity_components"]
                ["total_post_link_mutable_product_bytes"] == 42,
            "completed generic Link-38 closure drift")
    return {"first_red": bind(FIRST_RED),
            "protected_artifact_count": len(expected),
            "product_sha256": sha(PRODUCT),
            "generic_closure": generic}


def direct_entry_artifact_gate() -> dict[str, Any]:
    generated = SOURCE / "generated-product-sources"
    normalized = SOURCE / (
        "generated-direct-entry-gate/normalized-direct-entry-plane.bin")
    resolved = SOURCE / (
        "generated-direct-entry-gate/target-resolved-direct-entry-plane.bin")
    shelf = DIRECT.SHELF.read_bytes()
    c2d = DIRECT.C2D.read_bytes()
    geometry = DIRECT.current_geometry(c2d)
    rows = DIRECT.descriptor_rows(shelf, c2d, geometry)
    expected_normalized = DIRECT.normalized_c2d(c2d, geometry)
    require(normalized.read_bytes() == expected_normalized,
            "protected normalized direct-entry plane drift")
    data = resolved.read_bytes()
    require(len(data) == len(expected_normalized),
            "protected resolved direct-entry plane length drift")
    resolution_offset = 32 + geometry["images"] * 20
    values: list[int] = []
    per_image: Counter[int] = Counter()
    for row in rows:
        value = DIRECT.u16(
            data, resolution_offset + row["global_resolution"] * 2)
        BCODE.require_published_entry(value, row["global_entry"])
        values.append(value)
        per_image[row["image"]] += 1
    require(len(values) == 637 and not any(value & 1 for value in values)
            and min(values) >= 0xC000 and max(values) <= 0xDFFE,
            "protected generated direct-entry values red")
    decoder = (generated / "c2-stream-v2-decoder.c").read_text(
        encoding="utf-8")
    phase8 = decoder[decoder.index("#if C2_STREAM_V2_PHASE == 8"):
                     decoder.index("#if C2_STREAM_V2_PHASE == 9")]
    phase12 = decoder[decoder.index("#if C2_STREAM_V2_PHASE == 12"):
                      decoder.index("#if C2_STREAM_V2_PHASE == 13")]
    harness = (ROOT / "scripts/c2-direct-entry-contract-main.c").read_text(
        encoding="utf-8")
    require(phase8.count("MK_BCODE(") == 1
            and "0xc000u +" not in phase8
            and "word != (uint16_t)((root + 1u) << 1)" in phase12
            and "#ifdef C2D_V6_ROOT_SURROGATE" in harness
            and "(uint16_t)((root + 1u) << 1)" in harness,
            "v6 direct-entry/root-surrogate source seam red")
    bcode_mutations = BCODE.mutation_selftest()
    require(sha(ROOT_SURROGATE_RECEIPT) == ROOT_SURROGATE_RECEIPT_SHA
            and sha(ROOT / "src/obj.h") == OBJ_H_SHA,
            "bound root-surrogate source truth drift")
    root_receipt = json.loads(
        ROOT_SURROGATE_RECEIPT.read_text(encoding="utf-8"))
    root = root_receipt["green_before_first_red"][
        "permanent_root_surrogate_gate"]
    require(list(bcode_mutations.values()).count("rejected") == 4
            and root["status"] == "pass"
            and len(root["negative_fixtures"]) == 8,
            "direct-entry/root-surrogate negative matrix red")
    return {
        "status": "passed-pure-artifact-637-of-637",
        "direct_entry_references": len(values),
        "per_image": {str(key): per_image[key] for key in sorted(per_image)},
        "minimum_published_value": f"0x{min(values):04x}",
        "maximum_published_value": f"0x{max(values):04x}",
        "fixnum_decodable_published_values": 0,
        "bcode_negative_classes": list(bcode_mutations.values()).count(
            "rejected"),
        "root_surrogate_negative_classes": len(root["negative_fixtures"]),
        "root_surrogate_bound_receipt": bind(ROOT_SURROGATE_RECEIPT),
        "normalized_plane": bind(normalized),
        "resolved_plane": bind(resolved),
        "generated_decoder": bind(generated / "c2-stream-v2-decoder.c"),
        "harness_mode": "C2D_V6_ROOT_SURROGATE",
        "compiler_runs": 0,
    }


def walls_and_shape() -> tuple[dict[str, int], dict[str, Any]]:
    sections = P.section_table(ELF)
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
            and walls["e000_headroom_bytes"] >= E000_FLOOR,
            f"artifact replay resident wall red: {walls}")
    names = {spec.split(":")[2] for spec in
             P.BOOT_SLICE_SPECS + P.SESSION_SLICE_SPECS}
    sizes = {name: sections.get(name, {}).get("bytes", 0) for name in names}
    require(all(0 < value <= CAP for value in sizes.values()),
            "artifact replay runtime slice wall red")
    boot = SOURCE / "runtime-overlays-boot-final.bin"
    session = SOURCE / "runtime-overlays-session-final.bin"
    require(boot.stat().st_size <= BANK_BYTES
            and session.stat().st_size <= BANK_BYTES,
            "artifact replay Bank-3 aggregate red")
    return walls, {
        "walls": walls,
        "runtime_slices": {"count": len(sizes), "cap_bytes": CAP,
                           "largest_bytes": max(sizes.values()),
                           "minimum_headroom_bytes": CAP - max(sizes.values())},
        "successor_bank3_pack": {
            "boot": {**bind(boot),
                     "headroom_bytes": BANK_BYTES - boot.stat().st_size},
            "session": {**bind(session),
                        "headroom_bytes": BANK_BYTES - session.stat().st_size}},
    }


def workbench_crc_gate() -> dict[str, Any]:
    payload = ABI_WPLTO.payload(PRODUCT, ELF)
    expected = CRC.crc_reference(payload)
    truth = ElfTruth.read(ELF, llvm_readobj=P.TOOLCHAIN / "llvm-readobj")
    descriptor = HW.boot_overlay_descriptor(
        build_id=int(sha(SOURCE / "resolved-profile.txt")[:8], 16),
        start=truth.symbol("__lisp65_workbench_overlay_start").value,
        entry=truth.symbol("vm_workbench_boot_overlay_entry").value,
        payload=payload)
    require(struct.unpack_from("<H", descriptor, 16)[0] == expected,
            "artifact replay Workbench descriptor CRC red")
    prior = dict(CRC.VECTORS)
    CRC.VECTORS["actual-workbench-overlay"] = payload
    try:
        report = CRC.audit_elf(
            ELF, out=OUT / "c2-crc-asm-leaf-workbench-gate.json")
    finally:
        CRC.VECTORS.clear()
        CRC.VECTORS.update(prior)
    witness = report["vectors"]["actual-workbench-overlay"]
    require(witness["crc16"] == expected,
            "artifact replay linked CRC leaf parity red")
    return {"status": "passed", "payload_bytes": len(payload),
            "payload_crc16": expected,
            "payload_sha256": hashlib.sha256(payload).hexdigest(),
            "descriptor_sha256": hashlib.sha256(descriptor).hexdigest(),
            "linked_leaf_executed_instructions":
                witness["executed_instructions"]}


def build() -> dict[str, Any]:
    require(not OUT.exists() and not RECEIPT.exists() and not DIAGNOSIS.exists(),
            "Link-38 artifact replay is one-shot")
    authority = validate_source()
    OUT.mkdir(parents=True)
    STAGE.apply_profile(LINK.BASE.configure)
    P.VERIFIER_BINDING_BASE = 0xB9CD
    direct = direct_entry_artifact_gate()
    write_json(OUT / "direct-entry-v6-artifact-gate.json", direct)
    diagnosis = {
        "format": "lisp65-c2-lite-v6-direct-entry-root-surrogate-diagnosis-v1",
        "recorded_on": "2026-07-21",
        "status": "passed-class-a-harness-correction-product-unchanged",
        "first_red": bind(FIRST_RED),
        "failure": {
            "harness_exit": 97,
            "completed_before_exit": "637 direct values emitted and checked",
            "cause": (
                "The generated C2D-v6 phase-12 checker requires root_ref = "
                "(root_ordinal + 1) << 1, while the historical harness "
                "populated v5 root ordinals for its unrelated heap rows.")},
        "correction": {
            "mode_define": "C2D_V6_ROOT_SURROGATE",
            "default_v5_harness_semantics_unchanged": True,
            "product_bytes_changed": 0},
        "replay": direct,
        "scope": {"compiler_runs": 0, "product_links": 0,
                  "hardware_runs": 0, "capacity_effect_bytes": 0},
    }
    write_json(DIAGNOSIS, diagnosis)
    os.chmod(DIAGNOSIS, 0o444)
    walls, shape = walls_and_shape()
    capacity = DIET.capacity_gate(shape, ELF)
    semantics = DIET.semantic_product_gate(shape, PRODUCT, ELF)
    no_attic = LINK.no_runtime_attic_gate(
        ELF, SOURCE / "generated-product-sources")
    stage = ART.stage_product_gate(ELF)
    overlay = LINK.BASE.LINK33_BASE.final_overlay_closure(ELF)
    preinstall = LINK.BASE.ISLAND.static_elf_gate(ELF)
    abi = ABI.audit_elf(
        ELF, out=OUT / "c2-asm-leaf-abi-dataflow-gate.json",
        require_bank3_chain=True)
    crc = workbench_crc_gate()
    generic = authority["generic_closure"]
    total = json.loads((SOURCE / "total-publish-last-domain.json").read_text())
    require(capacity["status"] == semantics["status"] == "passed"
            and no_attic["status"].startswith("passed")
            and stage["status"] == "passed"
            and overlay["status"] == "passed-final-elf-overlay-closure"
            and preinstall["status"]
                == "passed-static-preinstallation-Island-gate"
            and abi["status"] == "passed-all-assembler-leaf-abi-contracts"
            and crc["status"] == "passed"
            and total["status"] == "passed"
            and total["declared_domain_bytes"] == 42
            and generic["status"] == "passed",
            "Link-38 pure artifact gate closure red")
    value = {
        "format": "lisp65-c2-lite-v6-boot-crc-abi-link38-artifact-replay-v1",
        "recorded_on": "2026-07-21",
        "status": "passed-link38-artifact-only-structural-closure-hardware-not-run",
        "promotable": False,
        "execution_accounting": {"compiler_runs": 0, "linker_runs": 0,
                                 "product_links": 0, "hardware_runs": 0,
                                 "latency_attempts_consumed": "0/2"},
        "authority": authority,
        "product_identity": {"product": bind(PRODUCT), "elf": bind(ELF),
                             "map": bind(Path(str(PRODUCT) + ".map")),
                             "resolved_profile": bind(
                                 SOURCE / "resolved-profile.txt")},
        "walls": walls,
        "runtime_family": shape,
        "direct_entry_v6": direct,
        "assembler_leaf_abi": abi,
        "workbench_crc_end_to_end": crc,
        "fresh_artifact_gates": {
            "capacity": capacity, "semantics": semantics,
            "no_runtime_attic": no_attic,
            "bank3_stage_before_publish": stage,
            "overlay_closure": overlay,
            "preinstallation_island": preinstall,
            "total_publish_last": total["status"]},
        "rollback_line": {**bind(BASELINE), "status": "untouched"},
        "claim_limit": (
            "Pure replay of one already completed, protected product link. "
            "No compiler, linker, product-byte change, hardware, latency, "
            "promotion or acceptance claim."),
        "next_gate": "owner-authorized seven-line receipt-less hardware presmoke from line 1",
    }
    report = OUT / "link38-artifact-replay.json"
    write_json(report, value)
    receipt = {**value, "artifact_replay_report": bind(report),
               "harness_diagnosis": bind(DIAGNOSIS)}
    write_json(RECEIPT, receipt)
    for path in OUT.rglob("*"):
        if path.is_file():
            os.chmod(path, 0o444)
    os.chmod(RECEIPT, 0o444)
    return receipt


def main() -> int:
    value = build()
    print("c2-lite-v6-link38-artifact-replay: " + value["status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
