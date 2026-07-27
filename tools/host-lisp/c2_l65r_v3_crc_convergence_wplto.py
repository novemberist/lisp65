#!/usr/bin/env python3
"""One product-shaped L65R-v3/CRC-convergence WPLTO capacity probe."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_link33_bss_triage_product_link as BASE  # noqa: E402
import c2_link34_dma_completion_leaf_presmoke as LEAF  # noqa: E402
import c2_link33_product_profile as PROFILE  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
OUT = ROOT / (
    "build/c2.2/substitution/l65r-v3-crc-convergence-temperature-wplto")
RECEIPT = EVIDENCE / (
    "c2.2-l65r-v3-crc-convergence-temperature-wplto-probe-receipt.json")
FIRST_RED = EVIDENCE / (
    "c2.2-l65r-v3-crc-convergence-temperature-wplto-first-red.json")
V3_RECEIPT = EVIDENCE / "c2.2-l65r-v3-record-crc-contract-probe-receipt.json"
V3_CONFIG = ROOT / "config/c2-l65r-v3-record-crc-contract.json"
COMPLETION_CONFIG = ROOT / "config/c2-runtime-overlay-dma-completion-contract.json"
SOURCE = ROOT / "src/vm_runtime_overlay.c"
HOST_MAIN = ROOT / "scripts/c2-l65r-v2-product-main.c"
FEATURES = (*PROFILE.feature_defines(), LEAF.DEFINE)


class ProbeError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ProbeError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"probe artifact absent: {path}")
    return {"path": path.relative_to(ROOT).as_posix(),
            "bytes": path.stat().st_size, "sha256": sha(path)}


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")


def protect(out: Path, receipt: Path) -> None:
    if out.exists():
        BASE.protect(out)
    if receipt.exists():
        os.chmod(receipt, 0o444)


def tree(out: Path) -> dict[str, dict[str, Any]]:
    if not out.exists():
        return {}
    return {p.relative_to(out).as_posix(): {
                "bytes": p.stat().st_size, "sha256": sha(p)}
            for p in sorted(out.rglob("*")) if p.is_file()}


def prerequisites() -> dict[str, Any]:
    receipt = json.loads(V3_RECEIPT.read_text(encoding="utf-8"))
    require(receipt.get("status") ==
            "passed-strict-l65r-v3-record-crc-contract",
            "strict L65R-v3 contract receipt is not green")
    require("LISP65_RUNTIME_OVERLAY_FORMAT_V3" in FEATURES
            and "LISP65_RUNTIME_OVERLAY_FORMAT_V2" not in FEATURES
            and "LISP65_RTOV_CRC_CONVERGENCE" in FEATURES
            and LEAF.DEFINE in FEATURES,
            "probe feature closure is not strict v3 plus convergence and marker leaf")
    return {
        "v3_contract": bind(V3_CONFIG),
        "v3_contract_receipt": bind(V3_RECEIPT),
        "completion_contract": bind(COMPLETION_CONFIG),
        "canonical_product_profile": PROFILE.receipt_identity(),
        "completion_leaf": bind(ROOT / "src/rtov_dma_completion.s"),
    }


def host_gate(out: Path) -> dict[str, Any]:
    binary = out / "l65r-v3-convergence-host"
    command = [
        "cc", "-std=c99", "-Wall", "-Wextra", "-Werror",
        "-fsanitize=address,undefined",
        "-DLISP65_VM", "-DLISP65_RUNTIME_OVERLAY_HOST_TEST",
        "-DLISP65_RUNTIME_OVERLAY_CATALOG_VERSION=3",
        "-DLISP65_RUNTIME_OVERLAY_FORMAT_V3",
        "-DLISP65_RTOV_CRC_CONVERGENCE",
        "-DLISP65_RUNTIME_OVERLAY_LIFETIME_FAMILIES",
        "-DLISP65_RUNTIME_OVERLAY_BOOT_STORAGE_BASE=0x08200000UL",
        "-DLISP65_RUNTIME_OVERLAY_BOOT_CATALOG_VERIFIER_FILE_OFF=0x0500u",
        "-DLISP65_RUNTIME_OVERLAY_BOOT_CATALOG_VERIFIER_FILE_SIZE=8u",
        "-DLISP65_RUNTIME_OVERLAY_BOOT_CATALOG_VERIFIER_ENTRY_OFFSET=0u",
        "-DLISP65_RUNTIME_OVERLAY_BOOT_CATALOG_VERIFIER_CRC16=0x37e8u",
        "-DLISP65_RUNTIME_OVERLAY_BOOT_RECORD_VERIFIER_FILE_OFF=0x0600u",
        "-DLISP65_RUNTIME_OVERLAY_BOOT_RECORD_VERIFIER_FILE_SIZE=8u",
        "-DLISP65_RUNTIME_OVERLAY_BOOT_RECORD_VERIFIER_ENTRY_OFFSET=0u",
        "-DLISP65_RUNTIME_OVERLAY_BOOT_RECORD_VERIFIER_CRC16=0x5afbu",
        "-DLISP65_RUNTIME_ISLAND_INSTALL_SLOT=8",
        "-DLISP65_RUNTIME_ISLAND_CARRIER_SLOT=9",
        "-I" + str(ROOT / "src"), str(HOST_MAIN), str(SOURCE),
        "-o", str(binary),
    ]
    subprocess.run(command, cwd=ROOT, check=True)
    run = subprocess.run(
        [str(binary)], cwd=ROOT, check=True, capture_output=True, text=True,
        env={**os.environ, "ASAN_OPTIONS": "detect_leaks=1",
             "UBSAN_OPTIONS": "halt_on_error=1"})
    require("PASS publish-last+14 fail-closed cases" in run.stdout,
            "strict v3 target-source host matrix did not pass")
    stdout = out / "l65r-v3-convergence-host.stdout.txt"
    stdout.write_text(run.stdout, encoding="utf-8")
    return {"status": "passed-target-source-asan-ubsan",
            "fail_closed_cases": 14, "binary": bind(binary),
            "stdout": bind(stdout)}


def source_gate() -> dict[str, Any]:
    source = SOURCE.read_text(encoding="utf-8")
    once = (
        "static RTOV_NOINLINE vm_runtime_overlay_status rtov_crc_converge(",
        "static RTOV_RECORDFN vm_runtime_overlay_status rtov_r_record_converge(",
        "static RTOV_ISLANDFN vm_runtime_overlay_status rtov_island_record_converge(",
        "static RTOV_ISLANDFN vm_runtime_overlay_status rtov_island_source_converge(",
        "static RTOV_ISLANDFN vm_runtime_overlay_status rtov_island_target_converge(",
        "static RTOV_CATALOGFN uint16_t rtov_c_crc_virtual_zero(",
        "LISP65_RTOV_COMPLETION_TIMEOUT_FRAMES;",
    )
    for token in once:
        require(source.count(token) == 1,
                f"convergence source invariant absent/duplicated: {token}")
    require(source.count("return VM_RUNTIME_OVERLAY_ERR_COMPLETION_TIMEOUT;") >= 3,
            "completion timeout does not survive all convergence consumers")
    require(source.count("rtov_crc_converge(") == 3,
            "resident convergence is not exactly one driver plus two hot consumers")
    require(source.count("rtov_r_record_converge(record)") == 1
            and source.count("rtov_island_record_converge(record)") == 1,
            "the two cold record consumers do not own their slice-local barriers")
    require(source.count("rtov_island_source_converge(") == 2
            and source.count("rtov_island_target_converge(") == 2,
            "the Island slice does not own both carrier convergence barriers")
    require("return c2_kernal_frame_count();" not in source
            and source.count("c2_kernal_frame_count_inline()") == 1,
            "cold convergence imported the handoff helper instead of the owned inline frame source")
    require(source.count("rtov_read(") == 4
            and source.count("static void rtov_read(") == 2,
            "target transport inventory drift")
    require("LISP65_RUNTIME_OVERLAY_FORMAT_VERSION == 3u" in source
            and "L65R-v3 record reads require CRC convergence" in source,
            "strict v3 compile-time boundary absent")
    return {"status": "passed-source-temperature-intent-one-hot-driver",
            "claim_limit": (
                "Source ownership only; WPLTO map placement remains the "
                "authority for resident/cold attribution."),
            "temperature_attribution": {
                "resident_hot": ["catalog-verifier-payload",
                                 "record-verifier-payload",
                                 "application-payload"],
                "catalog_slice_cold": ["catalog-header",
                                       "catalog-directory-chunks"],
                "record_slice_cold": ["requested-record-entry"],
                "island_slice_cold": ["island-carrier-record",
                                      "island-source-crc-chunks",
                                      "island-carrier-destination"],
            },
            "resident_convergence_drivers": 1,
            "record_consumers": 2, "timeout_frames": 64,
            "timeout_status": "VM_RUNTIME_OVERLAY_ERR_COMPLETION_TIMEOUT"}


def manifest_gate(out: Path) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for family in ("boot", "session"):
        path = out / f"runtime-overlays-{family}-final.json"
        value = json.loads(path.read_text(encoding="utf-8"))
        require(value["storage"]["format"] == "lisp65-runtime-overlay-bank-v3"
                and value["catalog"]["version"] == 3,
                f"{family} family is not strict L65R-v3")
        crcs = [row.get("record_crc16") for row in value["slices"]]
        require(crcs and all(type(crc) is int and 0 < crc <= 0xFFFF
                             for crc in crcs),
                f"{family} family has a missing/zero record CRC")
        result[family] = {"records": len(crcs),
                          "nonzero_record_crcs": len(crcs),
                          "manifest": bind(path)}
    return {"status": "passed-all-emitted-records-v3-self-authenticating",
            "families": result}


def capacity_gate(capacity: dict[str, Any]) -> dict[str, Any]:
    walls = {
        "bank0_text": capacity["bank0_text_headroom_bytes"],
        "ordinary_bss": capacity["ordinary_bank0_bss_headroom_bytes"],
        "fixed_hot_block": capacity["fixed_hot_block_headroom_bytes"],
        "resident_island": capacity["resident_island_headroom_bytes"],
        "e000": capacity["e000"]["actual_headroom_bytes"],
        "runtime_slice_min": capacity["runtime_slices"]["minimum_headroom_bytes"],
        "boot_overlay_bank": capacity["runtime_overlay_bank"]["boot_headroom_bytes"],
        "session_overlay_bank": capacity["runtime_overlay_bank"]["session_headroom_bytes"],
    }
    require(all(value >= 0 for value in walls.values()),
            f"CRC-convergence WPLTO has a red capacity wall: {walls}")
    require(capacity["e000"]["actual_headroom_bytes"] == 115
            and capacity["e000"]["delta_bytes"] == 0,
            "CRC convergence moved the final E000 floor")
    return {"status": "passed-all-bound-capacity-walls",
            "walls_headroom_bytes": walls, "e000_delta_bytes": 0}


def full_probe() -> dict[str, Any]:
    BASE.configure()
    authority = prerequisites()
    OUT.mkdir(parents=True)
    host = host_gate(OUT)
    fresh = BASE.PRE.check(OUT / "fresh-v5-prelink-gates")
    require(fresh["status"] == "passed-prelink-product-link-not-run",
            "fresh nested-append/B2 prelink gates failed")
    BASE.P.single_link(
        OUT, probe_definitions=FEATURES,
        direct_entry_receipt=BASE.DIRECT.RECEIPT,
        direct_entry_check_tool="c2_hot_refill_direct_entry_contract.py",
        extra_contract_lines=(
            "mode=l65r-v3-crc-convergence-wplto-capacity-probe",
            "promotable=no", "hardware_execution=prohibited",
            "runtime_overlay_catalog_version=3",
            "runtime_overlay_decoder_versions=3-only",
            "record_crc_emitter_sites=1",
            "completion_timeout_frames=64",
            "feature_defines=" + ",".join(FEATURES),
            "final_e000_floor_bytes=115", "green_inheritance=none",
        ))
    product = OUT / "lisp65-c2-substitution-linked.prg"
    elf = Path(str(product) + ".elf")
    structure = json.loads(
        (OUT / "product-substitution-link.json").read_text(encoding="utf-8"))
    total = json.loads(
        (OUT / "total-publish-last-domain.json").read_text(encoding="utf-8"))
    required = (
        "identity_gate", "capacity_gate", "one_truth_gate",
        "kernal_freedom_gate", "fixed_host_facade_gate",
        "pre_ownership_gate", "handoff_z_abi_gate",
    )
    require(structure.get("status") == "passed"
            and structure.get("product_closure_link_count") == 1
            and all(structure.get(name) == "passed" for name in required),
            "fresh product closure structure is not green")
    require(total.get("status") == "passed"
            and total.get("declared_domain_bytes") == 34,
            "post-link 34-byte mutation domain drift")
    capacity, sections = BASE.capacity(elf, OUT)
    walls = capacity_gate(capacity)
    completion_leaf = LEAF.elf_gate(elf)
    closure = BASE.LINK33_BASE.final_overlay_closure(elf)
    preinstall = BASE.ISLAND.static_elf_gate(elf)
    hot = BASE.HOT.direct_path_gate(elf)
    source = source_gate()
    manifests = manifest_gate(OUT)
    gates = {
        **{name: structure[name] for name in required},
        "direct_entry_encoding": structure["direct_entry_encoding_gate"],
        "total_publish_last": total["status"],
        "overlay_closure": closure["status"],
        "preinstallation_island": preinstall["status"],
        "hot_refill": hot["status"],
        "dma_completion_leaf": completion_leaf["status"],
        "v3_source": source["status"],
        "v3_emission": manifests["status"],
        "capacity": walls["status"],
    }
    require(all("pass" in value for value in gates.values()),
            f"fresh WPLTO gate set red: {gates}")
    return {
        "format": "lisp65-l65r-v3-crc-convergence-temperature-wplto-receipt-v1",
        "recorded_on": "2026-07-21",
        "status": "passed-l65r-v3-crc-convergence-temperature-wplto-product-link-not-authorized",
        "promotable": False,
        "claim_limit": (
            "Product-shaped WPLTO capacity/placement proof only. No "
            "promotable product identity and no hardware execution."),
        "authority": authority,
        "host_semantics": host,
        "fresh_gates": gates,
        "v3_source": source,
        "v3_manifests": manifests,
        "capacity": capacity,
        "capacity_gate": walls,
        "section_count": len(sections),
        "post_link_identity": {
            "declared_mutable_product_bytes": total["declared_domain_bytes"],
            "actual_changed_bytes": total["actual_changed_bytes"],
            "status": total["status"],
        },
        "evidence": tree(OUT),
        "execution_accounting": {
            "whole_program_lto_closure_links": 1, "hardware_runs": 0,
            "promotable_product_candidates": 0},
        "next_gate": "Class-C review; product link remains separately authorized",
    }


def first_red(error: BaseException) -> dict[str, Any]:
    value = {
        "format": "lisp65-l65r-v3-crc-convergence-temperature-wplto-first-red-v1",
        "recorded_on": "2026-07-21",
        "status": "FIRST RED: L65R-v3 CRC-convergence WPLTO probe stopped",
        "promotable": False,
        "diagnostic": {"type": type(error).__name__, "message": str(error)},
        "claim_limit": "No product link authorization or hardware claim.",
        "evidence": tree(OUT),
        "execution_accounting": {
            "whole_program_lto_closure_links": int(
                (OUT / "lisp65-c2-substitution-linked.prg").is_file()),
            "hardware_runs": 0, "promotable_product_candidates": 0},
        "next_gate": "stop and return the measured First Red to Class-C review",
    }
    write_json(FIRST_RED, value)
    protect(OUT, FIRST_RED)
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", action="store_true")
    parser.parse_args()
    require(not OUT.exists() and not RECEIPT.exists() and not FIRST_RED.exists(),
            "L65R-v3 convergence WPLTO probe already consumed")
    try:
        value = full_probe()
    except Exception as error:  # fail-closed receipt is part of the probe
        value = first_red(error)
        print(value["status"] + ": " + value["diagnostic"]["message"])
        return 3
    write_json(RECEIPT, value)
    protect(OUT, RECEIPT)
    print(value["status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
