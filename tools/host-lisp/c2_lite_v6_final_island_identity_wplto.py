#!/usr/bin/env python3
"""Qualify the final L65R carrier as the sole Island runtime identity.

The one product-shaped WPLTO keeps the Link-41 C2-lite geometry and changes
only the target installer contract: the authenticated final DATA_ONLY record
supplies source offset, length and CRC.  The prerequisite Island seed is a
build input, never a runtime comparison authority.
"""

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
import c2_final_island_identity_gate as IDENTITY  # noqa: E402
import c2_lite_v6_family_slot_identity_wplto as FAMILY_BASE  # noqa: E402
import c2_lite_v6_roots_fronts_coresident_wplto as RF  # noqa: E402


OUT = ROOT / "build/c2-lite/v6-final-island-identity-wplto"
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
RECEIPT = EVIDENCE / (
    "c2.2-c2-lite-v6-final-island-identity-wplto-receipt.json")
CONTRACT = ROOT / "config/c2-lite-execution-contract.json"
ADDENDUM = ROOT / "docs/planning/c2-lite-execution-contract-addendum.md"
FIRST_RED = EVIDENCE / (
    "c2.2-product-link41-c2-lite-v6-island-seed-identity-"
    "hardware-first-red.json")
LINK41 = ROOT / (
    "build/c2.2/substitution/"
    "product-link-41-c2-lite-v6-roots-fronts-coresident-replay3/"
    "lisp65-c2-substitution-linked.prg")
LINK41_RECEIPT = EVIDENCE / (
    "c2.2-product-link41-c2-lite-v6-roots-fronts-coresident-"
    "replay3-structural-receipt.json")
HOST_FIXTURE = ROOT / "scripts/c2-l65r-v2-product-main.c"


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
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    require(contract.get("status") ==
            "class-c-approved-final-island-carrier-single-runtime-identity",
            "final-Island Class-C contract is not current")
    require(FIRST_RED.is_file(), "Link-41 Island first-red receipt absent")
    first = json.loads(FIRST_RED.read_text(encoding="utf-8"))
    require(first.get("status") ==
            "first-red-final-carrier-identity-rejected-by-seed-island-crc",
            "Link-41 Island first-red receipt is not authoritative")
    require(LINK41.is_file() and LINK41_RECEIPT.is_file(),
            "Link-41 rollback line absent")
    return {
        "class_c_contract": bind(CONTRACT),
        "contract_addendum": bind(ADDENDUM),
        "link41_hardware_first_red": bind(FIRST_RED),
        "link41_rollback_product": {**bind(LINK41), "status": "untouched"},
        "link41_structural_receipt": bind(LINK41_RECEIPT),
        "driver": bind(Path(__file__)),
    }


def host_runtime_gate() -> dict[str, Any]:
    """Prove that a valid non-seed carrier is accepted by the active path."""
    source = HOST_FIXTURE.read_text(encoding="utf-8")
    old = "static const uint8_t carrier[] = {'I','S','L','D'};"
    new = "static const uint8_t carrier[] = {'F','I','N','A','L'};"
    limit_old = "put32(bank3 + 20, CARRIER_OFF + 4u);"
    limit_new = "put32(bank3 + 20, CARRIER_OFF + 5u);"
    require(source.count(old) == 1 and source.count(limit_old) == 1,
            "host carrier mutation/bounds anchor drift")
    fixture = OUT / "final-carrier-runtime-host.c"
    fixture.write_text(source.replace(old, new).replace(limit_old, limit_new),
                       encoding="utf-8")
    binary = OUT / "final-carrier-runtime-host"
    command = FAMILY_BASE.host_command(
        ROOT / "src/vm_runtime_overlay.c", binary)
    command[command.index(str(HOST_FIXTURE))] = str(fixture)
    command[command.index(
        "-DLISP65_RUNTIME_OVERLAY_CATALOG_VERSION=2")] = (
        "-DLISP65_RUNTIME_OVERLAY_CATALOG_VERSION=3")
    command[command.index("-DLISP65_RUNTIME_OVERLAY_FORMAT_V2")] = (
        "-DLISP65_RUNTIME_OVERLAY_FORMAT_V3")
    command.insert(command.index("-I" + str(ROOT / "src")),
                   "-DLISP65_RTOV_CRC_CONVERGENCE")
    subprocess.run(command, cwd=ROOT, check=True)
    run = subprocess.run(
        [str(binary)], cwd=ROOT, capture_output=True, text=True,
        env={**os.environ, "ASAN_OPTIONS": "detect_leaks=1",
             "UBSAN_OPTIONS": "halt_on_error=1"})
    stdout = OUT / "final-carrier-runtime-host.stdout.txt"
    stderr = OUT / "final-carrier-runtime-host.stderr.txt"
    stdout.write_text(run.stdout, encoding="utf-8")
    stderr.write_text(run.stderr, encoding="utf-8")
    require(run.returncode == 0 and
            "PASS publish-last+14 fail-closed cases" in run.stdout,
            "final-carrier active runtime host matrix is red")
    return {
        "status": "passed-active-v3-installer-accepts-non-seed-identity",
        "carrier_bytes": 5,
        "seed_length_compile_constant": 4,
        "seed_identity_used_at_runtime": False,
        "publish_last_fail_closed_cases": 14,
        "family_slot_cartesian_cases": 8,
        "qualified_consumers": 4,
        "asan": "passed", "ubsan": "passed",
        "fixture": bind(fixture), "binary": bind(binary),
        "stdout": bind(stdout), "stderr": bind(stderr),
    }


def run_product_wplto() -> dict[str, Any]:
    old_out = RF.OUT
    try:
        RF.OUT = OUT
        product = RF.run_wplto()
    finally:
        RF.OUT = old_out
    aggregate = RF.product_gate(product)
    elf = ROOT / product["artifacts"]["measurement_elf"]["path"]
    directory = elf.parent
    identity = IDENTITY.audit(
        elf,
        directory / "runtime-overlays-boot-c2-lite.bin",
        directory / "runtime-overlays-boot-c2-lite.json",
        directory / "generated-product-sources/vm_runtime_overlay.c",
        OUT / "final-island-identity-gate.json")
    require(identity["mutation_cases"] == 11,
            "final-Island permanent mutation matrix incomplete")
    return {"product": product, "aggregate": aggregate,
            "final_island_identity": identity}


def first_red(error: BaseException) -> None:
    value = {
        "format": "lisp65-c2-lite-v6-final-island-identity-first-red-v1",
        "recorded_on": "2026-07-22",
        "status": "FIRST RED: final-Island identity WPLTO stopped",
        "failure": {"type": type(error).__name__, "message": str(error)},
        "scope": {"whole_program_lto_probes": int(any(
                      OUT.rglob("c2-lite-v6-full-seed.prg.elf"))),
                  "product_links": 0, "hardware_runs": 0,
                  "promotable": False},
        "evidence": [bind(path) for path in sorted(OUT.rglob("*"))
                     if path.is_file()],
        "rollback_line": {**bind(LINK41), "status": "untouched"},
        "latency_attempts_consumed": "0/2",
        "next_gate": "Return to Class-C review; no product link or hardware",
    }
    write_json(RECEIPT, value)
    protect()


def build() -> dict[str, Any]:
    require(not OUT.exists() and not RECEIPT.exists(),
            "final-Island WPLTO is one-shot")
    auth = authority()
    OUT.mkdir(parents=True)
    source = IDENTITY.source_gate()
    host = host_runtime_gate()
    product = run_product_wplto()
    value = {
        "format": "lisp65-c2-lite-v6-final-island-identity-wplto-v1",
        "recorded_on": "2026-07-22",
        "status": "passed-final-island-carrier-single-runtime-identity-WPLTO",
        "scope": {"whole_program_lto_probes": 1, "product_links": 0,
                  "hardware_runs": 0, "promotable": False},
        "authority": auth,
        "source_contract": source,
        "active_runtime_host_matrix": host,
        "product_shaped_wplto": product["product"],
        "aggregate_recovery": product["aggregate"],
        "final_island_identity_gate": product["final_island_identity"],
        "claim_limit": "WPLTO structure and capacity only; no product link, "
                       "hardware, latency, promotion or acceptance claim.",
        "rollback_line": {**bind(LINK41), "status": "untouched"},
        "latency_attempts_consumed": "0/2",
        "next_gate": "Authorized successor product link",
    }
    report = OUT / "final-island-identity-wplto-report.json"
    write_json(report, value)
    value["probe_report"] = bind(report)
    write_json(RECEIPT, value)
    protect()
    return value


def main() -> int:
    try:
        value = build()
    except Exception as error:
        if OUT.exists() and not RECEIPT.exists():
            first_red(error)
        print("c2-final-island-wplto: FIRST RED " + str(error))
        return 2
    walls = value["product_shaped_wplto"]["capacity"]["walls"]
    identity = value["final_island_identity_gate"]["identity"]
    print("c2-final-island-wplto: PASS "
          f"carrier={identity['section_bytes']}B "
          f"crc=0x{identity['section_crc16']:04x} mutations=11/11 "
          f"text={walls['bank0_text_headroom_bytes']}B "
          f"e000={walls['e000_headroom_bytes']}B "
          "product-link=0 hardware=0 latency=0/2")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
