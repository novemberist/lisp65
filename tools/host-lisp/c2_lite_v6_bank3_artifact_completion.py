#!/usr/bin/env python3
"""Finish the owner-approved Bank-3 C2-lite candidate from bound WPLTO bytes.

No compiler or linker is permitted.  The protected WPLTO tree is validated,
copied, published through the already declared 42-byte post-link domain, and
then interrogated by the current artifact-side product gates.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_link33_bss_triage_product_link as BASE  # noqa: E402
import c2_lite_v6_bank3_staging_wplto_probe as STAGE  # noqa: E402
import c2_lite_v6_coresident_diet_probe as DIET  # noqa: E402
import c2_lite_v6_first_product_link as LINK  # noqa: E402
import c2_lite_v6_publish_last_geometry as GEOMETRY  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402


P = STAGE.P
SOURCE = ROOT / (
    "build/c2-lite/v6-bank3-stage-asm-fallback-wplto-replay2")
SOURCE_FULL = SOURCE / "full-product-wplto"
SOURCE_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-c2-lite-v6-bank3-stage-asm-fallback-wplto-replay2-receipt.json")
CHOICE = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-c2-lite-v6-bank3-bootstrap-choice-wplto-diagnosis.json")
PRIOR = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-product-link37-c2-lite-v6-artifact-resume2-structural-receipt.json")
OUT = ROOT / (
    "build/c2.2/substitution/c2-lite-v6-bank3-stage-artifact-candidate-replay5")
FIRST_RED = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-c2-lite-v6-bank3-stage-artifact-completion-structural-receipt.json")
INVENTORY_FIRST_RED = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-c2-lite-v6-bank3-stage-artifact-completion-replay2-structural-receipt.json")
SLICE_COUNT_FIRST_RED = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-c2-lite-v6-bank3-stage-artifact-completion-replay3-structural-receipt.json")
AGGREGATE_FIRST_RED = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-c2-lite-v6-bank3-stage-artifact-completion-replay4-structural-receipt.json")
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-c2-lite-v6-bank3-stage-artifact-completion-replay5-structural-receipt.json")
PRODUCT = OUT / "lisp65-c2-substitution-linked.prg"
SEED = "c2-lite-v6-full-seed.prg"
CAP = 1792
BANK_BYTES = 65536
E000_FLOOR = 115
VERIFIER_BASE = 0xB9CD


class CompletionError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise CompletionError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"artifact absent: {path}")
    return {"path": path.relative_to(ROOT).as_posix(),
            "bytes": path.stat().st_size, "sha256": sha(path)}


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")


def tree(path: Path) -> dict[str, dict[str, Any]]:
    return {item.relative_to(path).as_posix(): {
                "bytes": item.stat().st_size, "sha256": sha(item)}
            for item in sorted(path.rglob("*")) if item.is_file()}


def validate_source() -> dict[str, Any]:
    require(SOURCE_RECEIPT.is_file() and CHOICE.is_file() and PRIOR.is_file()
            and FIRST_RED.is_file() and INVENTORY_FIRST_RED.is_file()
            and SLICE_COUNT_FIRST_RED.is_file()
            and AGGREGATE_FIRST_RED.is_file(),
            "artifact-completion authority absent")
    source = json.loads(SOURCE_RECEIPT.read_text(encoding="utf-8"))
    require(source.get("status")
            == "FIRST RED: Bank-3 staging product-shaped WPLTO stopped"
            and source["failure"]["message"].startswith(
                "40-byte publish-last geometry red:")
            and source["scope"] == {
                "hardware_runs": 0, "product_links": 0,
                "promotable": False, "whole_program_lto_probes": 1},
            "source First Red is not the authorized pin-only stop")
    expected = {Path(row["path"]): row for row in source["evidence"]}
    actual_paths = {path.relative_to(ROOT) for path in SOURCE.rglob("*")
                    if path.is_file()}
    require(actual_paths == set(expected),
            "protected WPLTO source tree membership drift")
    for relative, row in expected.items():
        path = ROOT / relative
        require(path.stat().st_size == row["bytes"]
                and sha(path) == row["sha256"],
                f"protected WPLTO source artifact drift: {relative}")
    choice = json.loads(CHOICE.read_text(encoding="utf-8"))
    require(choice["decision"]["recommended_option"]
            == "non-lto-assembler-fallback"
            and choice["non_lto_assembler_fallback"]["walls"]
                ["bank0_text_headroom_bytes"] == 11,
            "owner-approved bootstrap choice evidence drift")
    return {
        "source_first_red": bind(SOURCE_RECEIPT),
        "artifact_completion_first_red": bind(FIRST_RED),
        "section_inventory_first_red": bind(INVENTORY_FIRST_RED),
        "slice_count_first_red": bind(SLICE_COUNT_FIRST_RED),
        "aggregate_count_first_red": bind(AGGREGATE_FIRST_RED),
        "bootstrap_choice": bind(CHOICE),
        "prior_c2_lite_structural_baseline": bind(PRIOR),
        "source_artifact_count": len(expected),
    }


def copy_source() -> None:
    require(not OUT.exists() and not RECEIPT.exists(),
            "Bank-3 artifact completion is one-shot")
    shutil.copytree(SOURCE_FULL, OUT, copy_function=shutil.copy2)
    for path in sorted(OUT.rglob("*")):
        os.chmod(path, 0o755 if path.is_dir() else 0o644)
    for suffix in ("", ".elf", ".map"):
        shutil.copy2(OUT / (SEED + suffix), Path(str(PRODUCT) + suffix))


def configure() -> None:
    STAGE.apply_profile(BASE.configure)
    P.VERIFIER_BINDING_BASE = VERIFIER_BASE
    require(P.FAMILY_STAGE_BINDINGS
            and P.runtime_binding_bytes() == 40
            and P.total_publish_last_bytes() == 42
            and P.E000_FINAL_FLOOR_BYTES == E000_FLOOR,
            "artifact completion profile drift")
    # Any accidental path back into the build machinery must fail closed.
    def prohibited(*_args: Any, **_kwargs: Any) -> Any:
        raise CompletionError("compiler/linker path entered during artifact replay")
    P.compile_link = prohibited
    P.single_link = prohibited
    # The generic module deliberately retains B954 as its historical default;
    # the C2-lite profile supplies its current address explicitly at both
    # artifact-publication callsites.  Python default arguments captured the
    # historical value when the generic module was imported.
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


def walls_and_shape(elf: Path) -> tuple[dict[str, int], dict[str, Any]]:
    sections = P.section_table(elf)
    text = sections[".text"]
    bss = sections[".bss"]
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
    require(walls == {
        "bank0_text_headroom_bytes": 11,
        "ordinary_bank0_bss_headroom_bytes": 86,
        "fixed_hot_block_headroom_bytes": 33,
        "resident_island_headroom_bytes": 170,
        "e000_headroom_bytes": 501,
    }, f"artifact candidate wall drift: {walls}")
    slice_sections = {spec.split(":")[2] for spec in
                      P.BOOT_SLICE_SPECS + P.SESSION_SLICE_SPECS}
    sizes = {name: sections.get(name, {}).get("bytes", 0)
             for name in slice_sections}
    require(all(0 < value <= CAP for value in sizes.values()),
            "artifact candidate runtime-slice wall red")
    boot = json.loads((OUT / "runtime-overlays-boot-final.json").read_text())
    session = json.loads(
        (OUT / "runtime-overlays-session-final.json").read_text())
    shape = {
        "walls": walls,
        "runtime_slices": {"count": len(sizes), "cap_bytes": CAP,
                           "largest_bytes": max(sizes.values()),
                           "minimum_headroom_bytes": CAP - max(sizes.values())},
        "successor_bank3_pack": {
            "boot": {"bytes": boot["storage"]["size"],
                     "headroom_bytes": BANK_BYTES - boot["storage"]["size"]},
            "session": {"bytes": session["storage"]["size"],
                        "headroom_bytes":
                            BANK_BYTES - session["storage"]["size"]},
        },
    }
    require(shape["successor_bank3_pack"] == {
        "boot": {"bytes": 16210, "headroom_bytes": 49326},
        "session": {"bytes": 65438, "headroom_bytes": 98},
    }, "artifact candidate family capacity drift")
    return walls, shape


def stage_product_gate(
        elf: Path, *, verifier_base: int = VERIFIER_BASE) -> dict[str, Any]:
    truth = ElfTruth.read(elf, llvm_readobj=P.TOOLCHAIN / "llvm-readobj")
    expected = {
        "c2_lite_stage_boot_family_impl": ".lisp65_boot_bank3_stage",
        "c2_lite_stage_boot_family": ".lisp65_boot_bank3_stage",
        "vm_bank3_boot_stage_entry": ".lisp65_boot_bank3_stage",
        "vm_boot_overlay_chain_prepare": ".lisp65_boot_bank3_stage",
        "ov_bank_crc16": ".lisp65_boot_bank3_stage",
        "vm_bank3_boot_stage_fail": ".lisp65_boot_bank3_stage",
        "vm_boot_overlay_chain_commit": ".text",
        "vm_boot_overlay_chain_expected": ".rodata",
        "c2_lite_stage_session_family_impl":
            ".lisp65_rt_bank3_stage_session",
        "c2_lite_stage_session_family": ".lisp65_rt_bank3_stage_session",
    }
    rows = {}
    for name, section in expected.items():
        symbol = truth.symbol(name)
        require(symbol.bytes > 0 and symbol.section == section,
                f"Bank-3 stage ELF citizen drift: {name}")
        rows[name] = {"section": symbol.section, "address": symbol.value,
                      "bytes": symbol.bytes}
    require(rows["vm_boot_overlay_chain_commit"]["bytes"] == 138
            and rows["vm_boot_overlay_chain_expected"]["bytes"] == 6,
            "accepted assembler fallback size drift")
    section = truth.section(P.VERIFIER_BINDING_SECTION)
    require(section.address == verifier_base and section.bytes == 40,
            "repinned 40-byte section geometry drift")
    state = STAGE.state_machine_gate()
    source = STAGE.source_contract_gate()
    require(state["cases"] == 8 and len(source["checks"]) == 14
            and source["checks"]["region1_target_proof_precedes_family_verified"]
            and len(source["mutations_rejected"]) == 5,
            "Bank-3 state/source contract gate red")
    return {"status": "passed", "elf_citizens": rows,
            "state_machine": state, "source_contract": source}


def prior_semantics() -> dict[str, Any]:
    prior = json.loads(PRIOR.read_text(encoding="utf-8"))
    root = prior["fresh_c2_lite_replacement_gates"]["root_surrogate"]
    require(root["status"] == "pass"
            and root["source_truth"]["obj_h_sha256"] == sha(ROOT / "src/obj.h")
            and root["source_truth"]["emitted_rows"] == 57344
            and len(root["negative_fixtures"]) == 8,
            "cached complete-domain root gate no longer matches obj.h")
    return {"status": "passed-bound-unchanged-semantics",
            "root_surrogate": root,
            "source_receipt": bind(PRIOR),
            "claim": (
                "The complete-domain result is replayed from its protected "
                "receipt because artifact completion forbids a host compiler; "
                "the bound obj.h hash remains byte-identical.")}


def protect() -> None:
    for path in OUT.rglob("*"):
        if path.is_file():
            os.chmod(path, 0o444)
    if RECEIPT.is_file():
        os.chmod(RECEIPT, 0o444)


def build() -> dict[str, Any]:
    authority = validate_source()
    # Prove that the generic pre-C2-lite default remains historical before
    # applying the profile-specific B9CD authority to the shared link module.
    geometry = GEOMETRY.collect()
    configure()
    copy_source()
    elf = Path(str(PRODUCT) + ".elf")
    contract = OUT / "resolved-profile.txt"
    try:
        # Completes the existing product bytes only: objcopy, packers and
        # artifact gates are allowed; compile_link/single_link are trapped.
        P.finish_single_link(OUT, PRODUCT, contract)
        generic = json.loads((OUT / "product-substitution-link.json").read_text())
        total = json.loads((OUT / "total-publish-last-domain.json").read_text())
        require(generic["status"] == "passed"
                and total["status"] == "passed"
                and total["declared_domain_bytes"] == 42,
                "generic artifact completion did not close all publish gates")
        inventory = P.final_section_inventory_gate(OUT, PRODUCT)
        overlay = BASE.LINK33_BASE.final_overlay_closure(elf)
        preinstall = BASE.ISLAND.static_elf_gate(elf)
        require(overlay["status"] == "passed-final-elf-overlay-closure"
                and preinstall["status"]
                    == "passed-static-preinstallation-Island-gate",
                "overlay/preinstallation gate red")
        walls, shape = walls_and_shape(elf)
        capacity = DIET.capacity_gate(shape, elf)
        semantics = DIET.semantic_product_gate(shape, PRODUCT, elf)
        no_attic = LINK.no_runtime_attic_gate(
            elf, OUT / "generated-product-sources")
        stage = stage_product_gate(elf)
        cached = prior_semantics()
        require(capacity["status"] == semantics["status"] == "passed"
                and no_attic["status"].startswith("passed")
                and inventory["status"] == "passed",
                "C2-lite replacement gate red")
        product_report = json.loads(
            (OUT / "product-substitution-link.json").read_text())
        required = (
            "identity_gate", "capacity_gate", "one_truth_gate",
            "kernal_freedom_gate", "fixed_host_facade_gate",
            "pre_ownership_gate", "handoff_z_abi_gate")
        require(all("pass" in str(product_report.get(name, ""))
                    for name in required),
                "generic structural gate set red")
        value = {
            "format": "lisp65-c2-lite-v6-bank3-artifact-completion-v1",
            "recorded_on": "2026-07-21",
            "status": "passed-complete-c2-lite-bank3-candidate-hardware-not-run",
            "promotable": False,
            "completion_mode": "artifact-only-from-one-SHA-bound-WPLTO-link",
            "execution_accounting": {
                "source_whole_program_lto_runs": 1,
                "artifact_completion_compiler_runs": 0,
                "artifact_completion_linker_runs": 0,
                "product_links": 0,
                "hardware_runs": 0
            },
            "authority": {**authority, "publish_last_geometry": geometry,
                          "driver": bind(Path(__file__))},
            "product_identity": {
                "product": bind(PRODUCT), "elf": bind(elf),
                "map": bind(Path(str(PRODUCT) + ".map")),
                "resolved_profile": bind(contract),
                "new_identity": True
            },
            "publish_last": {
                "address": "0xb9cd", "verifier_and_stage_bytes": 40,
                "kernal_crc_operand_bytes": 2,
                "declared_domain_bytes": total["declared_domain_bytes"],
                "actual_changed_bytes": total["actual_changed_bytes"],
                "status": total["status"]
            },
            "walls": walls,
            "text_reserve_bookkeeping": {
                "bytes": 11,
                "status": "measured-terminal-no-resident-growth-budget"
            },
            "bank3_family_capacity": shape["successor_bank3_pack"],
            "fresh_generic_gates": {
                name: product_report[name] for name in required
            },
            "fresh_c2_lite_gates": {
                "capacity": capacity, "product_semantics": semantics,
                "no_runtime_attic": no_attic,
                "bank3_stage_before_publish": stage,
                "overlay_closure": overlay["status"],
                "preinstallation_island": preinstall["status"],
                "section_inventory": inventory["status"]
            },
            "bound_unchanged_semantics": cached,
            "rollback_line": {
                **bind(LINK.LINK35_PRODUCT), "status": "untouched"},
            "claim_limit": (
                "Complete structural and capacity candidate from an existing "
                "SHA-bound WPLTO link. Hardware boot, latency, Chip refill "
                "timing, GC cost, Freezer identity, nested eval, promotion "
                "and acceptance remain not-run."),
            "next_gate": (
                "Owner-authorized seven-line receipt-less hardware presmoke "
                "from line 1; completed latency measurements used: 0 of 2.")
        }
        report = OUT / "c2-lite-v6-bank3-artifact-candidate.json"
        write_json(report, value)
        receipt = {**value, "candidate_report": bind(report),
                   "evidence_file_count": len(tree(OUT))}
        write_json(RECEIPT, receipt)
        protect()
        return receipt
    except Exception as error:
        value = {
            "format": "lisp65-c2-lite-v6-bank3-artifact-completion-v1",
            "recorded_on": "2026-07-21",
            "status": "FIRST RED: artifact completion stopped",
            "diagnostic": {"type": type(error).__name__,
                           "message": str(error)},
            "execution_accounting": {
                "artifact_completion_compiler_runs": 0,
                "artifact_completion_linker_runs": 0,
                "product_links": 0, "hardware_runs": 0},
            "authority": authority,
            "evidence": tree(OUT),
            "rollback_line": {
                **bind(LINK.LINK35_PRODUCT), "status": "untouched"},
            "next_gate": "Class-C review; no hardware"
        }
        write_json(RECEIPT, value)
        protect()
        return value


def main() -> int:
    value = build()
    print("c2-lite-v6-bank3-artifact-completion: " + value["status"])
    return 2 if value["status"].startswith("FIRST RED") else 0


if __name__ == "__main__":
    raise SystemExit(main())
