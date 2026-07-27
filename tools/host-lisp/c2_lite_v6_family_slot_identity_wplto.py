#!/usr/bin/env python3
"""Qualify C2-lite runtime-overlay identity as the tuple (family, slot).

The probe exercises the actual Link-40 collision (Boot slot 9 versus Session
slot 9), rejects four source-level regressions, inventories every slot-aware
consumer, and performs one nonpromotable product-shaped WPLTO with the full
C2-lite structural gate set.  It never creates a product link or uses hardware.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_asm_leaf_abi_gate as ABI  # noqa: E402
import c2_lite_v6_bank3_staging_wplto_probe as STAGE  # noqa: E402
import c2_lite_v6_first_product_link as LINK  # noqa: E402
import c2_lite_v6_rtov_crc_real_abi_wplto as ABI_PROBE  # noqa: E402


P = STAGE.P
OUT = ROOT / "build/c2-lite/v6-link40-family-slot-identity-wplto"
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
RECEIPT = EVIDENCE / (
    "c2.2-c2-lite-v6-link40-family-slot-identity-wplto-receipt.json")
FIRST_RED = EVIDENCE / (
    "c2.2-product-link40-c2-lite-v6-family-slot-collision-"
    "hardware-first-red.json")
FIRST_RED_SHA = (
    "6fab2115b96749290e80ef71f34e734d493dc2f849cc980a051e644465af0b75")
LINK40_RECEIPT = EVIDENCE / (
    "c2.2-product-link40-c2-lite-v6-real-abi-e000-structural-receipt.json")
LINK40_PRODUCT = ROOT / (
    "build/c2.2/substitution/product-link-40-c2-lite-v6-real-abi-e000/"
    "lisp65-c2-substitution-linked.prg")
LINK40_PRODUCT_SHA = (
    "a683a2e9b3be92b41bcc5ef0013f0e1c7ef379a63c26f4fe1883a21508bf44a0")
SOURCE = ROOT / "src/vm_runtime_overlay.c"
HOST_MAIN = ROOT / "scripts/c2-l65r-v2-product-main.c"
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
    require(FIRST_RED.is_file() and sha(FIRST_RED) == FIRST_RED_SHA,
            "family/slot hardware First Red authority drift")
    require(LINK40_PRODUCT.is_file() and sha(LINK40_PRODUCT) ==
            LINK40_PRODUCT_SHA, "Link-40 rollback product drift")
    link = json.loads(LINK40_RECEIPT.read_text(encoding="utf-8"))
    require(link.get("status") ==
            "passed-new-c2-lite-real-abi-identity-hardware-not-run"
            and link["product_identity"]["product"]["sha256"] ==
                LINK40_PRODUCT_SHA,
            "Link-40 structural receipt is not authoritative")
    return {
        "link40_family_slot_hardware_first_red": bind(FIRST_RED),
        "link40_structural_receipt": bind(LINK40_RECEIPT),
        "link40_rollback_product": {**bind(LINK40_PRODUCT),
                                     "status": "untouched"},
        "runtime_overlay_source": bind(SOURCE),
        "family_slot_fixture": bind(HOST_MAIN),
        "probe_driver": bind(Path(__file__)),
    }


def host_command(source: Path, binary: Path) -> list[str]:
    return [
        "cc", "-std=c99", "-Wall", "-Wextra", "-Werror",
        "-fsanitize=address,undefined",
        "-DLISP65_VM", "-DLISP65_RUNTIME_OVERLAY_HOST_TEST",
        "-DLISP65_RUNTIME_OVERLAY_CATALOG_VERSION=2",
        "-DLISP65_RUNTIME_OVERLAY_FORMAT_V2",
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
        # Link 40's actual collision: Boot installer slot 9 and Session phase 9.
        "-DLISP65_RUNTIME_ISLAND_INSTALL_SLOT=9",
        "-DLISP65_RUNTIME_ISLAND_CARRIER_SLOT=10",
        "-I" + str(ROOT / "src"), str(HOST_MAIN), str(source),
        "-o", str(binary),
    ]


def run_host(source: Path, binary: Path) -> subprocess.CompletedProcess[str]:
    subprocess.run(host_command(source, binary), cwd=ROOT, check=True)
    return subprocess.run(
        ["/usr/bin/setarch", os.uname().machine, "-R", str(binary)],
        cwd=ROOT, capture_output=True, text=True,
        env={**os.environ, "ASAN_OPTIONS": "detect_leaks=1",
             "UBSAN_OPTIONS": "halt_on_error=1"})


def stable_host_log(value: str) -> str:
    """Remove host-process identity while preserving the sanitizer proof."""
    return re.sub(
        r"==\d+==", "==PID==",
        value.replace(str(ROOT), "$ROOT"))


def host_matrix_and_mutations() -> dict[str, Any]:
    host = OUT / "family-slot-link40-host"
    run = run_host(SOURCE, host)
    require(run.returncode == 0 and
            "family-slot=8/8 consumers=4/4" in run.stdout,
            "family/slot Cartesian target-source matrix is red")
    (OUT / "family-slot-link40-host.stdout.txt").write_text(
        run.stdout, encoding="utf-8")

    source = SOURCE.read_text(encoding="utf-8")
    mutations = {
        "family-blind-installer-special": (
            "if (rtov_family == LISP65_RUNTIME_OVERLAY_FAMILY_BOOT &&\n",
            "if (1u &&\n"),
        "session-accepts-boot-record": (
            "#ifdef LISP65_RUNTIME_OVERLAY_LIFETIME_FAMILIES\n"
            "        (context->flags == LISP65_RUNTIME_OVERLAY_FLAG_BOOT &&\n"
            "         rtov_family != LISP65_RUNTIME_OVERLAY_FAMILY_BOOT) ||\n"
            "#endif\n",
            ""),
        "installer-entry-loses-family-guard": (
            "#ifdef LISP65_RUNTIME_OVERLAY_LIFETIME_FAMILIES\n"
            "    /* The installer slot is the tuple (Boot, slot), never a globally unique\n"
            "     * numeric slot.  Reject a late/foreign-family entry before state changes. */\n"
            "    if (rtov_family != LISP65_RUNTIME_OVERLAY_FAMILY_BOOT ||\n"
            "        rtov_family_generation)\n"
            "        return VM_RUNTIME_OVERLAY_ERR_FAMILY;\n"
            "#endif\n",
            ""),
        "boot-receives-session-batch-policy": (
            "#ifdef LISP65_RUNTIME_OVERLAY_LIFETIME_FAMILIES\n"
            "    /* Batch-policy slot ranges are Session-family ABI.  The same numeric\n"
            "     * slots in Boot name unrelated records and receive no batch privilege. */\n"
            "    if (rtov_family != LISP65_RUNTIME_OVERLAY_FAMILY_SESSION)\n"
            "        whitelisted = 0;\n"
            "#endif\n",
            ""),
    }
    rejected: dict[str, Any] = {}
    for name, (old, new) in mutations.items():
        require(source.count(old) == 1,
                f"mutation anchor absent or ambiguous: {name}")
        mutant = OUT / f"mutant-{name}.c"
        mutant.write_text(source.replace(old, new), encoding="utf-8")
        binary = OUT / f"mutant-{name}"
        result = run_host(mutant, binary)
        log = OUT / f"mutant-{name}.log.txt"
        log.write_text(
            stable_host_log(result.stdout + result.stderr),
            encoding="utf-8")
        require(result.returncode != 0 and "FAIL" in
                (result.stdout + result.stderr),
                f"family/slot mutation survived: {name}")
        rejected[name] = {"status": "rejected", "source": bind(mutant),
                          "binary": bind(binary), "log": bind(log),
                          "returncode": result.returncode}
    return {
        "status": "passed-link40-slot9-cartesian-and-consumer-matrix",
        "families": ["Boot", "Session"],
        "slot_classes": ["ordinary", "installer-number-9"],
        "record_classes": ["Boot-only", "runtime-reusable"],
        "cartesian_cases": 8,
        "qualified_consumers": 4,
        "asan": "passed", "ubsan": "passed",
        "mutations": rejected,
        "binary": bind(host),
        "stdout": bind(OUT / "family-slot-link40-host.stdout.txt"),
    }


def consumer_inventory() -> dict[str, Any]:
    rtov = SOURCE.read_text(encoding="utf-8")
    vm = (ROOT / "src/vm.c").read_text(encoding="utf-8")
    product = (ROOT / "src/c2_product_runtime.c").read_text(encoding="utf-8")
    required = {
        "installer-special-is-boot-slot-tuple":
            "if (rtov_family == LISP65_RUNTIME_OVERLAY_FAMILY_BOOT &&\n",
        "boot-record-flags-are-boot-family-only":
            "context->flags == LISP65_RUNTIME_OVERLAY_FLAG_BOOT &&\n"
            "         rtov_family != LISP65_RUNTIME_OVERLAY_FAMILY_BOOT",
        "installer-public-entry-is-boot-only":
            "if (rtov_family != LISP65_RUNTIME_OVERLAY_FAMILY_BOOT ||\n"
            "        rtov_family_generation)",
        "batch-ranges-are-session-family-only":
            "if (rtov_family != LISP65_RUNTIME_OVERLAY_FAMILY_SESSION)\n"
            "        whitelisted = 0;",
        "active-family-selects-verifier-table":
            "rtov_family == LISP65_RUNTIME_OVERLAY_FAMILY_BOOT\n"
            "                    ? rtov_boot_verifiers : rtov_verifiers",
        "explicit-family-call-validates-family-and-generation":
            "expected_family != rtov_family\n"
            "        || expected_generation != rtov_family_generation",
        "transaction-range-is-session-scoped":
            "family != LISP65_RUNTIME_OVERLAY_FAMILY_SESSION",
    }
    for label, anchor in required.items():
        require(anchor in rtov, f"slot-consumer invariant absent: {label}")
    require(rtov.count("context->slot == LISP65_RUNTIME_ISLAND_INSTALL_SLOT")
            == 1, "installer special has another slot-only reader")
    require("#ifdef LISP65_RUNTIME_OVERLAY\n    /* The transport writes" in vm
            and "vm_runtime_overlay_exec(slot, context, &vm_status)" in vm,
            "VM service slots lost the Session runtime transport boundary")
    require("vm_runtime_overlay_exec_family(\n"
            "                         family, generation, slot, context, &status)"
            in product, "C2 family caller lost explicit tuple transport")

    patterns = re.compile(
        r"(?:context->slot|verify->slot|\bslot\b).{0,48}"
        r"(?:==|!=|<=|>=|<|>)|(?:==|!=|<=|>=|<|>).{0,48}"
        r"(?:context->slot|verify->slot|\bslot\b)")
    rows: list[str] = []
    for path in (SOURCE, ROOT / "src/c2_product_runtime.c", ROOT / "src/vm.c",
                 ROOT / "src/vm_boot_overlay.c"):
        for number, line in enumerate(
                path.read_text(encoding="utf-8").splitlines(), 1):
            if patterns.search(line):
                rows.append(f"{path.relative_to(ROOT)}:{number}:{line.strip()}")
    scan = OUT / "slot-consumer-source-scan.txt"
    scan.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return {
        "status": "passed-no-unqualified-cross-family-slot-consumer",
        "cross_family_consumers": {
            "record-verifier-installer-special": "fixed-family+slot",
            "record-flag-lifetime": "fixed-family+flag",
            "public-island-installer": "fixed-Boot-family-entry",
            "batch-policy-ranges": "fixed-Session-family-ABI",
        },
        "generic_active_family_consumers": {
            "catalog-slot-range": "count belongs to selected family",
            "record-id-equality": "record belongs to selected family table",
            "transaction-slot-range": "transaction begin requires Session",
            "verifier-table": "selected by active family",
        },
        "caller_local_consumers": {
            "vm-buffer-service-slot-result":
                "runtime path uses the already selected Session family",
            "c2-product-phase-slot": "calls explicit family+generation API",
        },
        "source_scan_rows": len(rows),
        "source_scan": bind(scan),
    }


def product_wplto() -> dict[str, Any]:
    features = (*STAGE.feature_set(), "LISP65_C2_LITE_VM_ARITY_E000")
    old_out = STAGE.OUT
    STAGE.OUT = OUT
    try:
        stage_states = STAGE.state_machine_gate()
        stage_source = STAGE.source_contract_gate()
        wplto, target, elf = STAGE.run_wplto(features)
        stage = STAGE.product_gate(wplto, target, elf)
    finally:
        STAGE.OUT = old_out

    old_abi_out = ABI_PROBE.OUT
    try:
        ABI_PROBE.OUT = OUT
        abi = ABI.audit_elf(
            elf, out=OUT / "c2-asm-leaf-real-abi-callers.json",
            require_bank3_chain=True)
        crc = ABI_PROBE.workbench_crc_gate(target, elf)
    finally:
        ABI_PROBE.OUT = old_abi_out

    facade = P.fixed_facade_gate(OUT, target, "family-slot-identity-wplto")
    handoff = P.handoff_z_abi_gate(OUT, target, "family-slot-identity-wplto")
    pre = P.pre_ownership_gate(OUT, target, "family-slot-identity-wplto")
    profile = P.profile_data_reference_gate(
        OUT, target, "family-slot-identity-wplto", pre)
    inventory = P.final_section_inventory_gate(OUT, target)
    kernal = P.kernal_freedom_gate(OUT, target)
    no_attic = LINK.no_runtime_attic_gate(
        elf, target.parent / "generated-product-sources")
    overlay = LINK.BASE.LINK33_BASE.final_overlay_closure(elf)
    preinstall = LINK.BASE.ISLAND.static_elf_gate(elf)
    statuses = (facade["status"], handoff["status"], pre["status"],
                profile["status"], inventory["status"], kernal["status"])
    require(all(value == "passed" for value in statuses)
            and no_attic["status"].startswith("passed")
            and overlay["status"] == "passed-final-elf-overlay-closure"
            and preinstall["status"] ==
                "passed-static-preinstallation-Island-gate",
            "one or more fresh family/slot WPLTO structure gates are red")

    generated = target.parent / "generated-product-sources/vm_runtime_overlay.c"
    generated_text = generated.read_text(encoding="utf-8")
    for anchor in (
        "rtov_family == LISP65_RUNTIME_OVERLAY_FAMILY_BOOT &&\n",
        "rtov_family != LISP65_RUNTIME_OVERLAY_FAMILY_SESSION)\n"
        "        whitelisted = 0",
        "rtov_family != LISP65_RUNTIME_OVERLAY_FAMILY_BOOT ||\n"
        "        rtov_family_generation"):
        require(anchor in generated_text,
                "product-shaped source lost family-qualified slot identity")

    walls = dict(stage["walls"])
    require(walls["e000_headroom_bytes"] >= E000_FLOOR
            and all(value >= 0 for value in walls.values()),
            f"family/slot fix crossed a capacity wall: {walls}")
    session = target.parent / "runtime-overlays-session-c2-lite.bin"
    require(session.stat().st_size <= BANK_BYTES,
            "family/slot fix crossed the Session family aggregate")
    return {
        "status": "passed-one-product-shaped-family-slot-WPLTO",
        "stage_state_machine": stage_states,
        "stage_source_contract": stage_source,
        "stage_product": stage,
        "whole_program_lto": wplto,
        "capacity": {
            "walls": walls,
            "e000_floor_bytes": E000_FLOOR,
            "session_aggregate": {**bind(session),
                                  "headroom_bytes":
                                      BANK_BYTES - session.stat().st_size},
        },
        "fresh_gates": {
            "real_abi": abi, "six_vector_crc": crc,
            "fixed_facade": facade, "handoff": handoff,
            "pre_ownership": pre, "profile_data": profile,
            "section_inventory": inventory, "kernal_freedom": kernal,
            "no_runtime_attic": no_attic, "overlay_closure": overlay,
            "preinstallation_island": preinstall,
        },
        "artifacts": {"measurement_product": bind(target),
                      "measurement_elf": bind(elf),
                      "measurement_map": bind(Path(str(target) + ".map"))},
    }


def first_red(error: BaseException) -> dict[str, Any]:
    value = {
        "format": "lisp65-c2-lite-v6-family-slot-identity-first-red-v1",
        "recorded_on": "2026-07-22",
        "status": "FIRST RED: family/slot identity WPLTO stopped",
        "failure": {"type": type(error).__name__, "message": str(error)},
        "scope": {"whole_program_lto_probes": int(any(
                      OUT.rglob("c2-lite-v6-full-seed.prg.elf"))),
                  "product_links": 0, "hardware_runs": 0,
                  "promotable": False},
        "evidence": [bind(path) for path in sorted(OUT.rglob("*"))
                     if path.is_file()],
        "rollback_line": {**bind(LINK40_PRODUCT), "status": "untouched"},
        "next_gate": "Return to Class-C review; no product link or hardware",
    }
    write_json(RECEIPT, value)
    protect()
    return value


def build() -> dict[str, Any]:
    require(not OUT.exists() and not RECEIPT.exists(), "probe already exists")
    auth = authority()
    OUT.mkdir(parents=True)
    host = host_matrix_and_mutations()
    consumers = consumer_inventory()
    product = product_wplto()
    value = {
        "format": "lisp65-c2-lite-v6-family-slot-identity-wplto-v1",
        "recorded_on": "2026-07-22",
        "status": "passed-family-slot-identity-product-shaped-WPLTO",
        "scope": {"whole_program_lto_probes": 1, "product_links": 0,
                  "hardware_runs": 0, "promotable": False},
        "authority": auth,
        "host_matrix": host,
        "slot_consumer_inventory": consumers,
        "product_shaped_wplto": product,
        "claim_limit": (
            "Family/slot semantics, mutations, source inventory, capacity and "
            "structure only. No product link, hardware, latency, promotion "
            "or acceptance claim."),
        "rollback_line": {**bind(LINK40_PRODUCT), "status": "untouched"},
        "latency_attempts_consumed": "0/2",
        "next_gate": "Separate Class-C approval before the successor product link",
    }
    write_json(OUT / "family-slot-identity-wplto-report.json", value)
    value["probe_report"] = bind(
        OUT / "family-slot-identity-wplto-report.json")
    write_json(RECEIPT, value)
    protect()
    return value


def main() -> int:
    try:
        value = build()
    except Exception as error:
        if OUT.exists() and not RECEIPT.exists():
            first_red(error)
        print("c2-lite-family-slot-identity: FIRST RED " + str(error))
        return 2
    walls = value["product_shaped_wplto"]["capacity"]["walls"]
    print("c2-lite-family-slot-identity: PASS "
          f"matrix=8/8 mutations=4/4 text="
          f"{walls['bank0_text_headroom_bytes']}B e000="
          f"{walls['e000_headroom_bytes']}B product-link=0 hardware=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
