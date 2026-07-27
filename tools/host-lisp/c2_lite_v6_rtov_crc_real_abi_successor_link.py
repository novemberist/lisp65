#!/usr/bin/env python3
"""Build the owner-authorized C2-lite real-ABI successor product link.

This is Link 39.  It starts from the protected Link-38 product identity and
the Class-C-qualified real-ABI WPLTO truth, performs one fresh product link,
publishes the complete 42-byte post-link domain, and reruns all generic,
C2-lite, Bank-3 staging, real-ABI and Workbench-CRC gates.  It never runs
hardware or promotes the result.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys
import traceback
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_asm_leaf_abi_gate as ABI  # noqa: E402
import c2_lite_v6_boot_crc_abi_successor_link as BASE_LINK  # noqa: E402
import c2_lite_v6_direct_entry_contract as LITE_DIRECT  # noqa: E402
import c2_lite_v6_first_product_link_successor2 as DIRECT  # noqa: E402
import c2_lite_v6_product_probe as V6  # noqa: E402


P = BASE_LINK.P
LINK_NUMBER = 39
OUT = ROOT / "build/c2.2/substitution/product-link-39-c2-lite-v6-real-abi"
EVIDENCE = BASE_LINK.EVIDENCE
RECEIPT = EVIDENCE / (
    "c2.2-product-link39-c2-lite-v6-real-abi-structural-receipt.json")
BASELINE = ROOT / (
    "build/c2.2/substitution/"
    "product-link-38-c2-lite-v6-boot-crc-abi-replay/"
    "lisp65-c2-substitution-linked.prg")
BASELINE_SHA = (
    "61f406b57eeb2e258e941be432e8f6cea797c0623f421f09cc56e91f6f1419a2")
BASELINE_RECEIPT = EVIDENCE / (
    "c2.2-product-link38-c2-lite-v6-boot-crc-abi-"
    "artifact-replay-receipt.json")
BASELINE_RECEIPT_SHA = (
    "3cad09e6a609f7b7e860896bf30ba707a17acb68975b9d56d9ba1c08117f1cfc")
QUALIFICATION = EVIDENCE / (
    "c2.2-c2-lite-v6-link38-rtov-crc-real-abi-wplto-"
    "pure-replay-receipt.json")
QUALIFICATION_SHA = (
    "0bef9debcd85ea704cfa37dd4c58b834f025a134b06fd30e67ccb951ba524757")
HARDWARE_DIAGNOSIS = EVIDENCE / (
    "c2.2-link38-c2-lite-hold-before-fail-hardware-receipt.json")
HARDWARE_DIAGNOSIS_SHA = (
    "69cee2766fc1fc3744fd3c19680479578ca6cbf6f36db0d2c37b2410025e0ca8")
SOURCE_PINS = {
    ROOT / "src/rtov_crc_mem.s":
        "e63328fb96cee962b970fc9965a3d5b78cf4423b770c58c353a5ba04f3102821",
    ROOT / "tools/host-lisp/c2_asm_leaf_abi_gate.py":
        "17df845e5bf82f2d53f0c4d70eae3eb32c078daccd84109eacd3f0285e379ec7",
    ROOT / "tools/host-lisp/c2_crc_asm_leaf_gate.py":
        "10995f5f2cbc449b48aceea287c8bc5b7d37f67b9b49dea2f9a6a23f82c9cc72",
}
EXPECTED_CALLERS = {
    "vm_runtime_overlay_exec_family": 2,
    "rtov_run_batch": 1,
    "vm_runtime_overlay_catalog_verifier": 1,
    "vm_resident_island_install": 2,
    "vm_runtime_overlay_record_verifier": 1,
}


class LinkError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise LinkError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"Link-39 artifact absent: {path}")
    return {"path": path.relative_to(ROOT).as_posix(),
            "bytes": path.stat().st_size, "sha256": sha(path)}


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")


def tree(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    return {
        item.relative_to(path).as_posix(): {
            "bytes": item.stat().st_size, "sha256": sha(item)}
        for item in sorted(path.rglob("*")) if item.is_file()
    }


def protect() -> None:
    if OUT.is_dir():
        BASE_LINK.LINK.BASE.protect(OUT)
    if RECEIPT.is_file():
        os.chmod(RECEIPT, 0o444)


def prerequisites() -> dict[str, Any]:
    expected = {
        BASELINE: BASELINE_SHA,
        BASELINE_RECEIPT: BASELINE_RECEIPT_SHA,
        QUALIFICATION: QUALIFICATION_SHA,
        HARDWARE_DIAGNOSIS: HARDWARE_DIAGNOSIS_SHA,
        **SOURCE_PINS,
    }
    for path, digest in expected.items():
        require(path.is_file() and sha(path) == digest,
                f"Link-39 authority drift: {path}")
    baseline = json.loads(BASELINE_RECEIPT.read_text(encoding="utf-8"))
    qualification = json.loads(QUALIFICATION.read_text(encoding="utf-8"))
    diagnosis = json.loads(HARDWARE_DIAGNOSIS.read_text(encoding="utf-8"))
    require(
        baseline["status"] ==
            "passed-link38-artifact-only-structural-closure-hardware-not-run"
        and baseline["product_identity"]["product"]["sha256"] == BASELINE_SHA,
        "Link-38 rollback identity is not authoritative")
    require(
        qualification["status"] ==
            "passed-pure-qualification-replay-real-abi"
        and qualification["class_c_disposition"]["accepted_delta"] == {
            ".lisp65_rt_island_00": 49, ".text": 8}
        and qualification["replay"]["real_abi"]["callsite_count"] == 7
        and qualification["replay"]["six_vector_crc_parity"]["cases"] == 6
        and qualification["tool_invocations"]["product_links"] == 0,
        "Class-C real-ABI qualification is not authoritative")
    require(
        diagnosis["status"] == "answered-link38-bank3-island-edge"
        and diagnosis["observations"]["classification"] ==
            "transport-exact-crc-leaf-abi-reversed",
        "hardware transport/ABI diagnosis drift")
    return {
        "link38_rollback_product": bind(BASELINE),
        "link38_structural_authority": bind(BASELINE_RECEIPT),
        "class_c_real_abi_qualification": bind(QUALIFICATION),
        "hardware_transport_exoneration": bind(HARDWARE_DIAGNOSIS),
        "real_abi_sources": [bind(path) for path in SOURCE_PINS],
        "driver": bind(Path(__file__)),
    }


def first_red(error: BaseException, authority: dict[str, Any]) -> dict[str, Any]:
    if os.environ.get("LISP65_PUBLIC_CLEAN_BUILD") == "1":
        traceback.print_exception(error)
    product = OUT / "lisp65-c2-substitution-linked.prg"
    value = {
        "format": (
            f"lisp65-c2-lite-v6-real-abi-link{LINK_NUMBER}-first-red-v1"),
        "recorded_on": "2026-07-22",
        "status": f"FIRST RED: C2-lite real-ABI Link {LINK_NUMBER} stopped",
        "promotable": False,
        "diagnostic": {"type": type(error).__name__, "message": str(error)},
        "execution_accounting": {
            "product_closure_links": int(product.is_file()),
            "hardware_runs": 0,
            "latency_attempts_consumed": "0/2",
        },
        "authority": authority,
        "evidence": tree(OUT),
        "rollback_line": {**bind(BASELINE), "status": "untouched"},
        "conditional_next_gate": (
            "Only a resident-capacity overflow authorizes the standing "
            "small-hot-object E000 relocation probe; every other failure "
            "returns to Class-C review."),
    }
    write_json(RECEIPT, value)
    protect()
    return value


def real_abi_gate(elf: Path) -> dict[str, Any]:
    report = ABI.audit_elf(
        elf, out=OUT / "c2-asm-leaf-real-abi-callers.json",
        require_bank3_chain=True)
    callers = report["rtov_crc_mem_callers"]
    owners: dict[str, int] = {}
    for row in callers["callers"]:
        owners[row["owner"]] = owners.get(row["owner"], 0) + 1
    require(callers["callsite_count"] == 7
            and owners == EXPECTED_CALLERS,
            f"fresh Link-39 real-ABI caller inventory drift: {owners}")
    return {
        "status": report["status"],
        "callsite_count": callers["callsite_count"],
        "owners": owners,
        "product_assembler_callers": 0,
        "report": report,
    }


def build() -> dict[str, Any]:
    require(not OUT.exists() and not RECEIPT.exists(),
            "Link 39 is one-shot")
    authority = prerequisites()
    OUT.mkdir(parents=True)
    original_sources = P.source_list
    original_patch: Any = None
    original_total: Any = None
    old_base_out = BASE_LINK.OUT
    old_direct_out = DIRECT.OUT
    try:
        BASE_LINK.OUT = OUT
        features = BASE_LINK.configure_profile()
        original_patch, original_total = (
            BASE_LINK.install_profile_binding_wrappers())
        prelink = BASE_LINK.fresh_prelink_gates()
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
                f"mode=link{LINK_NUMBER}-c2-lite-v6-real-abi-successor",
                "source_baseline=link38-c2-lite-v6-boot-crc-abi",
                "real_abi_qualification_sha256=" + QUALIFICATION_SHA,
                "feature_defines=" + ",".join(features),
                "c2d_version=6",
                "runtime_refill_source=chip-bank2",
                "native_family_source=chip-bank3",
                "bank3_stage_records=2",
                "assembler_leaf_real_abi_gate=required",
                "workbench_crc_six_vector_gate=required",
                "final_e000_floor_bytes=115",
                "green_inheritance=none"))
    except Exception as error:
        return first_red(error, authority)
    finally:
        P.source_list = original_sources
        DIRECT.OUT = old_direct_out
        BASE_LINK.OUT = old_base_out
        if original_patch is not None:
            P.patch_verifier_binding_table = original_patch
        if original_total is not None:
            P.total_publish_last_gate = original_total

    product = OUT / "lisp65-c2-substitution-linked.prg"
    elf = Path(str(product) + ".elf")
    try:
        BASE_LINK.OUT = OUT
        structure = json.loads(
            (OUT / "product-substitution-link.json").read_text())
        total = json.loads(
            (OUT / "total-publish-last-domain.json").read_text())
        required = (
            "identity_gate", "capacity_gate", "one_truth_gate",
            "kernal_freedom_gate", "fixed_host_facade_gate",
            "pre_ownership_gate", "handoff_z_abi_gate")
        require(structure.get("status") == "passed"
                and structure.get("product_closure_link_count") == 1
                and all("pass" in str(structure.get(name, ""))
                        for name in required),
                "fresh Link-39 generic product closure is not fully green")
        require(total.get("status") == "passed"
                and total.get("declared_domain_bytes") == 42,
                "Link-39 publish-last domain is not the complete 42-byte set")
        replacement = BASE_LINK.replacement_gates(product, elf, prelink)
        abi = real_abi_gate(elf)
        require(abi["status"] == "passed-all-assembler-leaf-abi-contracts",
                "fresh Link-39 real-ABI gate red")
        require(sha(product) != BASELINE_SHA and sha(BASELINE) == BASELINE_SHA,
                "Link-39 identity or rollback line red")
        value = {
            "format": (
                f"lisp65-c2-lite-v6-real-abi-link{LINK_NUMBER}-structural-v1"),
            "recorded_on": "2026-07-22",
            "status": "passed-new-c2-lite-real-abi-identity-hardware-not-run",
            "promotable": False,
            "link_number": LINK_NUMBER,
            "inheritance": (
                "none; every structural, capacity, C2-lite, staging, "
                "real-ABI and CRC gate ran freshly"),
            "execution_accounting": {
                "resident_island_seed_links": 1,
                "product_closure_links": 1,
                "hardware_runs": 0,
                "latency_attempts_consumed": "0/2",
            },
            "authority": authority,
            "product_identity": {
                "product": bind(product),
                "elf": bind(elf),
                "map": bind(Path(str(product) + ".map")),
                "resolved_profile": bind(OUT / "resolved-profile.txt"),
                "predecessor_sha256": BASELINE_SHA,
                "new_identity": True,
            },
            "fresh_generic_gates": {
                name: structure[name] for name in required},
            "fresh_replacement_gates": replacement,
            "fresh_prelink_gates": prelink,
            "fresh_real_abi_gate": abi,
            "post_link_identity": {
                "declared_mutable_product_bytes":
                    total["declared_domain_bytes"],
                "actual_changed_bytes": total["actual_changed_bytes"],
                "status": total["status"],
            },
            "rollback_line": {
                **bind(BASELINE), "status": "untouched-and-readable"},
            "claim_limit": (
                "One fresh product-closure link and complete structural, "
                "capacity, C2-lite, staging, real-ABI and six-vector CRC "
                "closure. Hardware, boot, latency, refill timing, GC, "
                "Freezer, nested eval, promotion and acceptance remain not-run."),
            "next_gate": (
                "Owner-authorized seven-line receipt-less hardware presmoke "
                "from line 1"),
        }
        report = OUT / (
            f"link{LINK_NUMBER}-c2-lite-v6-real-abi-structural.json")
        write_json(report, value)
        receipt = {**value, "structural_report": bind(report),
                   "evidence_file_count": len(tree(OUT))}
        write_json(RECEIPT, receipt)
        protect()
        return receipt
    except Exception as error:
        return first_red(error, authority)
    finally:
        BASE_LINK.OUT = old_base_out


def main() -> int:
    try:
        value = build()
    except Exception as error:
        if OUT.exists() and not RECEIPT.exists():
            value = first_red(error, prerequisites())
        else:
            raise
    print("c2-lite-v6-rtov-crc-real-abi-successor-link: " + value["status"])
    return 2 if value["status"].startswith("FIRST RED") else 0


if __name__ == "__main__":
    raise SystemExit(main())
