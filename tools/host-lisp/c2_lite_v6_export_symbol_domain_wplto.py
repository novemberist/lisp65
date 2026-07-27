#!/usr/bin/env python3
"""Qualify the Link-42 export-plan SYMI correction with one WPLTO.

The probe consumes the exact 353-row hardware plan, proves its canonical SYMI
domain and the five foreign-domain rejections, then performs one complete
product-shaped C2-lite WPLTO.  It creates no promotable product link and does
not access hardware.
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
import c2_final_island_identity_gate as ISLAND  # noqa: E402
import c2_lite_v6_coresident_diet_probe as CORESIDENT  # noqa: E402
import c2_lite_v6_product_probe as V6  # noqa: E402
import c2_lite_v6_roots_fronts_coresident_wplto as RF  # noqa: E402


OUT = ROOT / "build/c2-lite/v6-export-symbol-domain-wplto"
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
RECEIPT = EVIDENCE / (
    "c2.2-c2-lite-v6-export-symbol-domain-wplto-receipt.json")
FIRST_RED = EVIDENCE / (
    "c2.2-product-link42-c2-lite-v6-export-symbol-domain-"
    "hardware-first-red.json")
FIRST_RED_SHA = (
    "85a3949df9abbf2841218de55eebfbb069f5603301bba73d5c561527e008efeb")
STRUCTURAL = EVIDENCE / (
    "c2.2-product-link42-c2-lite-v6-final-island-identity-replay-"
    "structural-receipt.json")
LINK42 = ROOT / (
    "build/c2.2/substitution/"
    "product-link-42-c2-lite-v6-final-island-identity-replay/"
    "lisp65-c2-substitution-linked.prg")
CONTRACT = ROOT / "config/c2-lite-execution-contract.json"
ADDENDUM = ROOT / "docs/planning/c2-lite-execution-contract-addendum.md"
RUNTIME = ROOT / "src/c2_product_runtime.c"
FIXTURE = ROOT / "scripts/c2-lite-v6-export-symbol-domain-main.c"
REAL_PLAN = ROOT / (
    "build/c2.2/hardware-presmoke-link42-final-island/"
    "first-red-profiled-preload/export-plan-journal.bin")


class ProbeError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
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
    for path in OUT.rglob("*") if OUT.exists() else ():
        if path.is_file():
            os.chmod(path, 0o444)
    for path in (FIRST_RED, REAL_PLAN, RECEIPT):
        if path.is_file():
            os.chmod(path, 0o444)


def authority() -> dict[str, Any]:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    require(contract["status"] ==
            "class-c-approved-export-symbol-domain-wplto-probe",
            "export-symbol-domain Class-C authority absent")
    require(contract["scope"]["product_links_authorized"] == 0,
            "probe authority unexpectedly permits a product link")
    require(FIRST_RED.is_file() and sha(FIRST_RED) == FIRST_RED_SHA,
            "Link-42 export-domain First Red drift")
    first = json.loads(FIRST_RED.read_text(encoding="utf-8"))
    require(first["status"] == "first-red-product-semantic-review-required"
            and first["root_cause"]["rows_satisfying_symi"] == 353
            and first["root_cause"]["rows_satisfying_is_ptr"] == 0,
            "Link-42 export-domain diagnosis is not authoritative")
    return {
        "class_c_contract": bind(CONTRACT),
        "contract_addendum": bind(ADDENDUM),
        "hardware_first_red": bind(FIRST_RED),
        "link42_product": {**bind(LINK42), "status": "untouched"},
        "link42_structural_receipt": bind(STRUCTURAL),
        "driver": bind(Path(__file__)),
    }


def source_domain_gate(source_path: Path = RUNTIME) -> dict[str, Any]:
    source = source_path.read_text(encoding="utf-8")
    active = V6.c_function_definition(
        source, "c2_append_publish_exports_phase")
    names = V6.c_function_definition(source, "c2_append_publish_names_phase")
    cells = V6.c_function_definition(source, "c2_append_publish_cells_phase")
    checks = {
        "active_co_resident_accepts_symi_only":
            active.count("!IS_SYMI((obj)c2_u16(row))") == 1
            and "!IS_PTR((obj)c2_u16(row))" not in active,
        "legacy_names_accepts_symi_only":
            names.count("!IS_SYMI((obj)c2_u16(row))") == 1
            and "!IS_PTR((obj)c2_u16(row))" not in names,
        "legacy_cells_accepts_symi_only":
            cells.count("!IS_SYMI(symbol)") == 1
            and "!IS_PTR(symbol)" not in cells,
        "producer_is_canonical_intern":
            "*value = (uint16_t)c2_facade_intern(sym_name_scratch);"
                in source,
    }
    require(all(checks.values()), "export-symbol source gate red: "
            + str([name for name, passed in checks.items() if not passed]))
    return {"status": "passed-one-canonical-symi-domain",
            "checks": checks, "source": bind(source_path)}


def real_plan_gate() -> dict[str, Any]:
    require(sha(REAL_PLAN) ==
            "06cb0990bc1eeacabef2d95432d64d93cc0f431a4179527a2b66c071cee9769d",
            "real Link-42 export plan drift")
    binary = OUT / "export-symbol-domain-host"
    command = [
        "cc", "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror",
        "-fsanitize=address,undefined", "-Isrc", str(FIXTURE),
        "-o", str(binary)]
    subprocess.run(command, cwd=ROOT, check=True)
    run = subprocess.run(
        [str(binary), str(REAL_PLAN)], cwd=ROOT, capture_output=True,
        text=True, env={**os.environ, "ASAN_OPTIONS": "detect_leaks=1",
                        "UBSAN_OPTIONS": "halt_on_error=1"})
    stdout = OUT / "export-symbol-domain-host.stdout.txt"
    stderr = OUT / "export-symbol-domain-host.stderr.txt"
    stdout.write_text(run.stdout, encoding="utf-8")
    stderr.write_text(run.stderr, encoding="utf-8")
    require(run.returncode == 0 and
            "PASS rows=353 foreign-domains-rejected=5" in run.stdout,
            "real 353-row export-plan matrix is red")
    return {
        "status": "passed-real-link42-plan-and-foreign-domain-matrix",
        "accepted_real_rows": 353,
        "rejected_domains": ["heap-pointer", "NIL", "Fixnum", "BCODE",
                             "odd-damaged-SYMI"],
        "negative_cases": 5,
        "asan": "passed", "ubsan": "passed",
        "fixture": bind(FIXTURE), "real_plan": bind(REAL_PLAN),
        "binary": bind(binary), "stdout": bind(stdout),
        "stderr": bind(stderr),
    }


def product_wplto() -> dict[str, Any]:
    previous_out = RF.OUT
    try:
        RF.OUT = OUT
        product = RF.run_wplto()
    finally:
        RF.OUT = previous_out
    aggregate = RF.product_gate(product)
    elf = ROOT / product["artifacts"]["measurement_elf"]["path"]
    directory = elf.parent
    generated = directory / "generated-product-sources/c2_product_runtime.c"
    generated_source = source_domain_gate(generated)
    island = ISLAND.audit(
        elf,
        directory / "runtime-overlays-boot-c2-lite.bin",
        directory / "runtime-overlays-boot-c2-lite.json",
        directory / "generated-product-sources/vm_runtime_overlay.c",
        OUT / "final-island-identity-gate.json")
    require(island["mutation_cases"] == 11,
            "final-Island identity matrix incomplete")
    return {"product": product, "aggregate": aggregate,
            "generated_source_domain": generated_source,
            "final_island_identity": island}


def first_red(error: BaseException) -> None:
    value = {
        "format": "lisp65-c2-lite-v6-export-symbol-domain-wplto-first-red-v1",
        "recorded_on": "2026-07-22",
        "status": "FIRST RED: export-symbol-domain WPLTO stopped",
        "failure": {"type": type(error).__name__, "message": str(error)},
        "scope": {"whole_program_lto_probes": int(any(
                      OUT.rglob("c2-lite-v6-full-seed.prg.elf"))),
                  "product_links": 0, "hardware_runs": 0,
                  "promotable": False},
        "evidence": [bind(path) for path in sorted(OUT.rglob("*"))
                     if path.is_file()],
        "rollback_line": {**bind(LINK42), "status": "untouched"},
        "line1_first_red_budget": "1/3 consumed",
        "latency_measurement_attempts": "0/2 consumed",
        "next_gate": "Return to Class-C review; no product link or hardware",
    }
    write_json(RECEIPT, value)
    protect()


def build() -> dict[str, Any]:
    require(not OUT.exists() and not RECEIPT.exists(),
            "export-symbol-domain WPLTO is one-shot")
    auth = authority()
    OUT.mkdir(parents=True)
    source = source_domain_gate()
    plan = real_plan_gate()
    coresident = CORESIDENT.source_contract_gate()
    product = product_wplto()
    value = {
        "format": "lisp65-c2-lite-v6-export-symbol-domain-wplto-v1",
        "recorded_on": "2026-07-22",
        "status": "passed-export-symbol-domain-product-shaped-WPLTO",
        "scope": {"whole_program_lto_probes": 1, "product_links": 0,
                  "hardware_runs": 0, "promotable": False},
        "authority": auth,
        "source_domain_gate": source,
        "real_353_row_plan_gate": plan,
        "co_resident_contract_gate": coresident,
        "product_shaped_wplto": product["product"],
        "aggregate_recovery": product["aggregate"],
        "generated_source_domain_gate": product["generated_source_domain"],
        "final_island_identity_gate": product["final_island_identity"],
        "line1_first_red_budget": "1/3 consumed; 2 remain",
        "latency_measurement_attempts": "0/2 consumed",
        "claim_limit": "Contract, exact hardware-plan domain matrix and one "
                       "nonpromotable product-shaped WPLTO only; no product "
                       "link, hardware, latency, promotion or acceptance claim.",
        "rollback_line": {**bind(LINK42), "status": "untouched"},
        "next_gate": "Separate Class-C authorization for the successor product link",
    }
    report = OUT / "export-symbol-domain-wplto-report.json"
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
        print("c2-lite-v6-export-symbol-domain-wplto: FIRST RED " + str(error))
        return 2
    walls = value["product_shaped_wplto"]["capacity"]["walls"]
    aggregate = value["aggregate_recovery"]
    print("c2-lite-v6-export-symbol-domain-wplto: PASS "
          "rows=353 negatives=5 "
          f"publish={aggregate['slice']['bytes']}B "
          f"session={aggregate['session_family_bytes']}B "
          f"text={walls['bank0_text_headroom_bytes']}B "
          f"e000={walls['e000_headroom_bytes']}B "
          "product-link=0 hardware=0 budget=1/3 latency=0/2")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
