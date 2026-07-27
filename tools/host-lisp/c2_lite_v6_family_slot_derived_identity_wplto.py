#!/usr/bin/env python3
"""Qualify derived (family, slot) identity without a duplicate resident guard."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_lite_v6_family_slot_identity_wplto as BASE  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402


P = BASE.P
STAGE = BASE.STAGE
LINK = BASE.LINK
ABI = BASE.ABI
ABI_PROBE = BASE.ABI_PROBE
OUT = ROOT / "build/c2-lite/v6-link40-family-slot-derived-identity-wplto"
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
RECEIPT = EVIDENCE / (
    "c2.2-c2-lite-v6-link40-family-slot-derived-identity-wplto-receipt.json")
CAPACITY_FIRST_RED = EVIDENCE / (
    "c2.2-c2-lite-v6-link40-family-slot-identity-wplto-replay-receipt.json")
CAPACITY_FIRST_RED_SHA = (
    "d13a5e271d3e3a3afa1d0a966aed9896dde5138616878acf2809bd0cef381f50")
SOURCE = BASE.SOURCE
HOST_MAIN = BASE.HOST_MAIN
E000_FLOOR = 115
BANK_BYTES = 65536


class ProbeError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ProbeError(message)


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


def protect() -> None:
    if OUT.exists():
        for path in OUT.rglob("*"):
            if path.is_file():
                os.chmod(path, 0o444)
    if RECEIPT.is_file():
        os.chmod(RECEIPT, 0o444)


def authority() -> dict[str, Any]:
    value = BASE.authority()
    require(CAPACITY_FIRST_RED.is_file() and
            sha(CAPACITY_FIRST_RED) == CAPACITY_FIRST_RED_SHA,
            "one-byte family/slot capacity First Red drift")
    first = json.loads(CAPACITY_FIRST_RED.read_text(encoding="utf-8"))
    require(first["status"] ==
            "FIRST RED: family/slot identity WPLTO stopped"
            and first["failure"]["message"] ==
                "link command failed before orphan-wrapper acceptance: exit=1",
            "one-byte capacity First Red is not authoritative")
    value["one_byte_capacity_first_red"] = bind(CAPACITY_FIRST_RED)
    value["owner_decision"] = {
        "choice": "derive installer family through explicit family seam",
        "closure_gate": "required proof, not an alternative",
        "duplicate_resident_guard": "forbidden",
    }
    value["derived_identity_driver"] = bind(Path(__file__))
    return value


def run_host(source: Path, binary: Path) -> subprocess.CompletedProcess[str]:
    subprocess.run(BASE.host_command(source, binary), cwd=ROOT, check=True)
    return subprocess.run(
        ["/usr/bin/setarch", os.uname().machine, "-R", str(binary)],
        cwd=ROOT, capture_output=True, text=True,
        env={**os.environ, "ASAN_OPTIONS": "detect_leaks=1",
             "UBSAN_OPTIONS": "halt_on_error=1"})


def host_gate() -> dict[str, Any]:
    binary = OUT / "family-slot-derived-host"
    run = run_host(SOURCE, binary)
    require(run.returncode == 0 and
            "family-slot=8/8 consumers=4/4" in run.stdout,
            "derived family/slot host matrix is red")
    stdout = OUT / "family-slot-derived-host.stdout.txt"
    stdout.write_text(run.stdout, encoding="utf-8")
    source = SOURCE.read_text(encoding="utf-8")
    mutations = {
        "family-blind-installer-special": (
            "if (rtov_family == LISP65_RUNTIME_OVERLAY_FAMILY_BOOT &&\n",
            "if (1u &&\n"),
        "session-accepts-boot-record": (
            "#ifdef LISP65_RUNTIME_OVERLAY_LIFETIME_FAMILIES\n"
            "        (context->flags == LISP65_RUNTIME_OVERLAY_FLAG_BOOT &&\n"
            "         rtov_family != LISP65_RUNTIME_OVERLAY_FAMILY_BOOT) ||\n"
            "#endif\n", ""),
        "installer-loses-explicit-family-seam": (
            "transport = vm_runtime_overlay_exec_family(\n"
            "        LISP65_RUNTIME_OVERLAY_FAMILY_BOOT, 0,\n"
            "        LISP65_RUNTIME_ISLAND_INSTALL_SLOT, 0, &result);",
            "transport = vm_runtime_overlay_exec(\n"
            "        LISP65_RUNTIME_ISLAND_INSTALL_SLOT, 0, &result);"),
        "boot-receives-session-batch-policy": (
            "#ifdef LISP65_RUNTIME_OVERLAY_LIFETIME_FAMILIES\n"
            "    /* Batch-policy slot ranges are Session-family ABI.  The same numeric\n"
            "     * slots in Boot name unrelated records and receive no batch privilege. */\n"
            "    if (rtov_family != LISP65_RUNTIME_OVERLAY_FAMILY_SESSION)\n"
            "        whitelisted = 0;\n"
            "#endif\n", ""),
    }
    rejected: dict[str, Any] = {}
    for name, (old, new) in mutations.items():
        require(source.count(old) == 1,
                f"mutation anchor absent or ambiguous: {name}")
        mutant = OUT / f"mutant-{name}.c"
        mutant.write_text(source.replace(old, new), encoding="utf-8")
        target = OUT / f"mutant-{name}"
        result = run_host(mutant, target)
        log = OUT / f"mutant-{name}.log.txt"
        log.write_text(
            BASE.stable_host_log(result.stdout + result.stderr),
            encoding="utf-8")
        require(result.returncode != 0 and "FAIL" in
                (result.stdout + result.stderr),
                f"derived identity mutation survived: {name}")
        rejected[name] = {"status": "rejected", "source": bind(mutant),
                          "binary": bind(target), "log": bind(log)}
    return {
        "status": "passed-derived-identity-host-matrix",
        "cartesian_cases": 8, "qualified_consumers": 4,
        "mutations_rejected": rejected,
        "asan": "passed", "ubsan": "passed",
        "binary": bind(binary), "stdout": bind(stdout),
    }


def source_gate(source: str) -> dict[str, Any]:
    duplicate = (
        "if (rtov_family != LISP65_RUNTIME_OVERLAY_FAMILY_BOOT ||\n"
        "        rtov_family_generation)")
    seam_v2 = (
        "transport = vm_runtime_overlay_exec_family(\n"
        "        LISP65_RUNTIME_OVERLAY_FAMILY_BOOT, 0,\n"
        "        LISP65_RUNTIME_ISLAND_INSTALL_SLOT, 0, &result);")
    seam_v1 = (
        "transport = vm_runtime_overlay_exec_family(\n"
        "        LISP65_RUNTIME_OVERLAY_FAMILY_BOOT, 0,\n"
        "        LISP65_RUNTIME_ISLAND_INSTALL_SLOT, &context, &result);")
    seam_finalize = (
        "transport = vm_runtime_overlay_exec_family(\n"
        "            LISP65_RUNTIME_OVERLAY_FAMILY_BOOT, 0,\n"
        "            LISP65_RUNTIME_ISLAND_FINALIZE_SLOT, 0, &result);")
    require(duplicate not in source, "duplicate resident family guard survived")
    require(source.count(seam_v2) == 1 and source.count(seam_v1) == 1
            and source.count(seam_finalize) == 1,
            "Boot installer calls did not all consume the explicit family seam")
    require(source.count(
        "context->slot == LISP65_RUNTIME_ISLAND_INSTALL_SLOT") == 1,
        "installer verifier special is absent or duplicated")
    return {
        "status": "passed-one-family-truth-derived-at-call-seam",
        "duplicate_resident_family_checks": 0,
        "explicit_boot_family_calls": 3,
        "installer_special_predicates": 1,
    }


def closure_gate(target: Path, elf: Path) -> dict[str, Any]:
    source = (target.parent /
              "generated-product-sources/vm_runtime_overlay.c").read_text(
                  encoding="utf-8")
    source_result = source_gate(source)
    truth = ElfTruth.read(elf, llvm_readobj=P.TOOLCHAIN / "llvm-readobj")
    installer = truth.symbol("vm_runtime_overlay_install_island")
    family_seam = truth.symbol("vm_runtime_overlay_exec_family")
    require(installer.bytes > 0 and family_seam.bytes > 0,
            "installer or explicit family seam lost ELF identity")
    disassembly = P.run([
        str(P.TOOLCHAIN / "llvm-objdump"), "-d", str(elf)], capture=True)
    nodes, _ = P._sectioned_disassembly(disassembly)
    installer_nodes = [row for row in nodes.values()
                       if "vm_runtime_overlay_install_island" in row["names"]]
    require(len(installer_nodes) == 1,
            "installer does not have one ELF control-flow node")
    installer_targets = P._direct_call_targets(installer_nodes[0]["lines"])
    require(family_seam.value in installer_targets,
            "installer ELF closure bypasses explicit family seam")
    callers = []
    for row in nodes.values():
        if installer.value in P._direct_call_targets(row["lines"]):
            callers.extend(row["names"])
    require(callers == ["main"],
            f"installer gained a non-Boot product caller: {callers}")
    return {
        "status": "passed-derived-family-seam-closure",
        "installer": {"section": installer.section,
                      "address": installer.value, "bytes": installer.bytes},
        "family_seam": {"section": family_seam.section,
                        "address": family_seam.value,
                        "bytes": family_seam.bytes},
        "installer_directly_calls_family_seam": True,
        "product_callers": callers,
        "source": source_result,
    }


def product_wplto() -> dict[str, Any]:
    features = (*STAGE.feature_set(), "LISP65_C2_LITE_VM_ARITY_E000")
    old_out = STAGE.OUT
    STAGE.OUT = OUT
    try:
        states = STAGE.state_machine_gate()
        stage_source = STAGE.source_contract_gate()
        wplto, target, elf = STAGE.run_wplto(features)
        stage = STAGE.product_gate(wplto, target, elf)
    finally:
        STAGE.OUT = old_out
    derived = closure_gate(target, elf)
    old_abi_out = ABI_PROBE.OUT
    try:
        ABI_PROBE.OUT = OUT
        abi = ABI.audit_elf(elf,
            out=OUT / "c2-asm-leaf-real-abi-callers.json",
            require_bank3_chain=True)
        crc = ABI_PROBE.workbench_crc_gate(target, elf)
    finally:
        ABI_PROBE.OUT = old_abi_out
    facade = P.fixed_facade_gate(OUT, target, "family-slot-derived-wplto")
    handoff = P.handoff_z_abi_gate(OUT, target, "family-slot-derived-wplto")
    pre = P.pre_ownership_gate(OUT, target, "family-slot-derived-wplto")
    profile = P.profile_data_reference_gate(
        OUT, target, "family-slot-derived-wplto", pre)
    inventory = P.final_section_inventory_gate(OUT, target)
    kernal = P.kernal_freedom_gate(OUT, target)
    no_attic = LINK.no_runtime_attic_gate(
        elf, target.parent / "generated-product-sources")
    overlay = LINK.BASE.LINK33_BASE.final_overlay_closure(elf)
    preinstall = LINK.BASE.ISLAND.static_elf_gate(elf)
    require(all(gate["status"] == "passed" for gate in
                (facade, handoff, pre, profile, inventory, kernal))
            and no_attic["status"].startswith("passed")
            and overlay["status"] == "passed-final-elf-overlay-closure"
            and preinstall["status"] ==
                "passed-static-preinstallation-Island-gate",
            "one or more derived-identity structural gates are red")
    walls = dict(stage["walls"])
    require(walls["e000_headroom_bytes"] >= E000_FLOOR
            and all(value >= 0 for value in walls.values()),
            f"derived family identity crossed a capacity wall: {walls}")
    session = target.parent / "runtime-overlays-session-c2-lite.bin"
    require(session.stat().st_size <= BANK_BYTES,
            "derived identity crossed Session aggregate")
    return {
        "status": "passed-one-product-shaped-derived-identity-WPLTO",
        "state_machine": states, "stage_source": stage_source,
        "stage_product": stage, "derived_identity_closure": derived,
        "whole_program_lto": wplto,
        "capacity": {"walls": walls, "e000_floor_bytes": E000_FLOOR,
                     "session_aggregate": {**bind(session),
                         "headroom_bytes": BANK_BYTES-session.stat().st_size}},
        "fresh_gates": {"real_abi": abi, "six_vector_crc": crc,
            "fixed_facade": facade, "handoff": handoff,
            "pre_ownership": pre, "profile_data": profile,
            "section_inventory": inventory, "kernal_freedom": kernal,
            "no_runtime_attic": no_attic, "overlay_closure": overlay,
            "preinstallation_island": preinstall},
        "artifacts": {"measurement_product": bind(target),
                      "measurement_elf": bind(elf),
                      "measurement_map": bind(Path(str(target) + ".map"))},
    }


def first_red(error: BaseException) -> dict[str, Any]:
    value = {
        "format": "lisp65-c2-lite-v6-family-slot-derived-first-red-v1",
        "recorded_on": "2026-07-22",
        "status": "FIRST RED: derived family/slot WPLTO stopped",
        "failure": {"type": type(error).__name__, "message": str(error)},
        "scope": {"wplto_attempts": 1, "successful_wplto": 0,
                  "product_links": 0, "hardware_runs": 0,
                  "promotable": False},
        "evidence": [bind(path) for path in sorted(OUT.rglob("*"))
                     if path.is_file()],
        "rollback_line": {**bind(BASE.LINK40_PRODUCT), "status": "untouched"},
        "next_gate": "Return to Class-C review; no product link or hardware",
    }
    write_json(RECEIPT, value); protect(); return value


def build() -> dict[str, Any]:
    require(not OUT.exists() and not RECEIPT.exists(), "probe already exists")
    auth = authority(); OUT.mkdir(parents=True)
    source = source_gate(SOURCE.read_text(encoding="utf-8"))
    host = host_gate()
    product = product_wplto()
    value = {
        "format": "lisp65-c2-lite-v6-family-slot-derived-identity-wplto-v1",
        "recorded_on": "2026-07-22",
        "status": "passed-derived-family-slot-identity-WPLTO",
        "scope": {"whole_program_lto_probes": 1, "product_links": 0,
                  "hardware_runs": 0, "promotable": False},
        "authority": auth, "source_gate": source, "host_matrix": host,
        "product_shaped_wplto": product,
        "claim_limit": "No product link, hardware, latency or promotion claim.",
        "rollback_line": {**bind(BASE.LINK40_PRODUCT), "status": "untouched"},
        "latency_attempts_consumed": "0/2",
        "next_gate": "Owner-authorized successor product link",
    }
    write_json(OUT / "family-slot-derived-identity-wplto-report.json", value)
    value["probe_report"] = bind(
        OUT / "family-slot-derived-identity-wplto-report.json")
    write_json(RECEIPT, value); protect(); return value


def main() -> int:
    try:
        value = build()
    except Exception as error:
        if OUT.exists() and not RECEIPT.exists():
            first_red(error)
        print("c2-lite-family-slot-derived: FIRST RED " + str(error))
        return 2
    walls = value["product_shaped_wplto"]["capacity"]["walls"]
    print("c2-lite-family-slot-derived: PASS matrix=8/8 mutations=4/4 "
          f"text={walls['bank0_text_headroom_bytes']}B "
          f"e000={walls['e000_headroom_bytes']}B product-link=0 hardware=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
