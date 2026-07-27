#!/usr/bin/env python3
"""Qualify the owner-approved roots/fronts aggregate recovery.

The probe replaces the adjacent roots and fronts records with one physical
Session slice containing two marker-selected entry bodies.  It runs the fused
cutpoint matrix and one product-shaped WPLTO with the complete Link-40 gate
set.  It does not create a product link or use hardware.
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
import c2_lite_v6_family_slot_derived_identity_wplto as DERIVED  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402


P = DERIVED.P
STAGE = DERIVED.STAGE
OUT = ROOT / "build/c2-lite/v6-link40-roots-fronts-coresident-wplto"
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
RECEIPT = EVIDENCE / (
    "c2.2-c2-lite-v6-link40-roots-fronts-coresident-wplto-receipt.json")
AUTHORITY = EVIDENCE / (
    "c2.2-c2-lite-v6-link40-family-slot-derived-identity-wplto-receipt.json")
AUTHORITY_SHA = (
    "07b3a9900397184eda7a9ca444c0dc517927a807c4b1e9eaf417994ca5c46b61")
FIXTURE = ROOT / "scripts/c2-lite-v6-roots-fronts-cutpoints-main.c"
RUNTIME = ROOT / "src/c2_product_runtime.c"
HEADER = ROOT / "src/c2_product_runtime.h"
FEATURE = "LISP65_C2_LITE_V6_ROOTS_FRONTS_CORESIDENT"
CAP = 1792
BANK_BYTES = 65536
PACK_QUANTUM = 256
EXPECTED_SESSION_BYTES = 65438
EXPECTED_SESSION_HEADROOM = 98


class ProbeError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ProbeError(message)


def marker_reuses_dead_source_byte(source: str) -> bool:
    """Accept only the two contract-equivalent spellings of record[23]."""
    direct = source.count(
        "#define C2AW_ROOTS_FRONTS_MARK(w) ((w)->record[23])") == 1
    shared = (
        source.count(
            "#define C2AW_FUSED_PHASE_MARK(w) ((w)->record[23])") == 1
        and source.count(
            "#define C2AW_ROOTS_FRONTS_MARK(w) C2AW_FUSED_PHASE_MARK(w)") == 1)
    return direct != shared


def marker_source_mutations(source: str) -> dict[str, str]:
    require(marker_reuses_dead_source_byte(source),
            "roots/fronts source marker authority absent")
    mutations = {
        "wrong_backing_byte": source.replace(
            "#define C2AW_FUSED_PHASE_MARK(w) ((w)->record[23])",
            "#define C2AW_FUSED_PHASE_MARK(w) ((w)->record[22])", 1),
        "wrong_shared_alias": source.replace(
            "#define C2AW_ROOTS_FRONTS_MARK(w) C2AW_FUSED_PHASE_MARK(w)",
            "#define C2AW_ROOTS_FRONTS_MARK(w) C2AW_PUBLISH_CLEAR_MARK(w)",
            1),
        "duplicate_direct_authority": source.replace(
            "#define C2AW_ROOTS_FRONTS_MARK(w) C2AW_FUSED_PHASE_MARK(w)",
            "#define C2AW_ROOTS_FRONTS_MARK(w) C2AW_FUSED_PHASE_MARK(w)\n"
            "#define C2AW_ROOTS_FRONTS_MARK(w) ((w)->record[23])",
            1),
    }
    rejected = {name: "rejected" for name, mutation in mutations.items()
                if not marker_reuses_dead_source_byte(mutation)}
    require(len(rejected) == len(mutations),
            "roots/fronts marker source mutation escaped")
    return rejected


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


def configure_roots_fronts() -> None:
    rows = list(P.C2_APPEND_SLICES)
    names = [name for name, _entry in rows]
    require(names.count("roots") == names.count("fronts") == 1,
            "roots/fronts profile anchors absent")
    at = names.index("roots")
    require(rows[at + 1][0] == "fronts", "roots/fronts are not adjacent")
    rows[at:at + 2] = [
        ("roots_fronts", "c2_append_roots_fronts_phase")]
    P.configure_append_slices(rows)
    require(len(P.C2_APPEND_SLICES) == 23
            and P.SESSION_APPEND_SLOT_BASE == 23
            and P.SESSION_SERVICE_SLOT_BASE == 46
            and len(P.SESSION_SLICE_SPECS) == 50
            and P.UNIQUE_SLICE_COUNT == 57,
            "roots/fronts runtime-family ABI drift")


def cutpoint_gate() -> dict[str, Any]:
    binary = OUT / "roots-fronts-cutpoints"
    command = [
        "cc", "-std=c99", "-Wall", "-Wextra", "-Werror",
        "-fsanitize=address,undefined", str(FIXTURE), "-o", str(binary)]
    subprocess.run(command, cwd=ROOT, check=True)
    run = subprocess.run(
        [str(binary)], cwd=ROOT, capture_output=True, text=True,
        env={**os.environ, "ASAN_OPTIONS": "detect_leaks=1",
             "UBSAN_OPTIONS": "halt_on_error=1"})
    expected = ("c2-lite-v6-roots-fronts-cutpoints: PASS slice=1 "
                "entries=2 normal=2 rollback=1 negatives=6 "
                "added-state-bytes=0 added-pointers=0")
    require(run.returncode == 0 and expected in run.stdout,
            "roots/fronts cutpoint fixture is red")
    stdout = OUT / "roots-fronts-cutpoints.stdout.txt"
    stdout.write_text(run.stdout, encoding="utf-8")
    return {
        "status": "passed-fused-cutpoint-skip-replay-matrix",
        "physical_slices": 1, "logical_entries": 2,
        "normal_entry_calls": 2, "fronts_only_rollback_calls": 1,
        "negative_cases": 6, "added_state_bytes": 0,
        "added_pointers": 0, "asan": "passed", "ubsan": "passed",
        "fixture": bind(FIXTURE), "binary": bind(binary),
        "stdout": bind(stdout),
    }


def source_gate() -> dict[str, Any]:
    source = RUNTIME.read_text(encoding="utf-8")
    header = HEADER.read_text(encoding="utf-8")
    marker_mutations = marker_source_mutations(source)
    checks = {
        "one_fused_section": source.count(
            'C2_ROOTS_FRONTS_SECTION C2_APPEND_SECTION("roots_fronts")') == 1,
        "two_internal_entries":
            source.count("C2_ROOTS_ENTRY uint8_t c2_append_roots_phase") == 1
            and source.count(
                "C2_FRONTS_ENTRY uint8_t c2_append_fronts_phase") == 1,
        "one_catalog_entry": source.count(
            "uint8_t c2_append_roots_fronts_phase") == 1,
        "normal_driver_calls_both":
            source.count("C2AW_ROOTS_FRONTS_MARK(&c2aw) = "
                         "C2_ROOTS_REQUEST_MARK;") == 1
            and source.count("C2AW_ROOTS_FRONTS_MARK(&c2aw) = "
                             "C2_FRONTS_REQUEST_MARK;") >= 2,
        "abort_control_selects_fronts": source.count(
            "C2AW_ROOTS_FRONTS_MARK(w) = C2_FRONTS_REQUEST_MARK;") == 2,
        "marker_reuses_dead_source_byte":
            marker_reuses_dead_source_byte(source),
        "slot_alias_and_shift":
            "#define LISP65_C2_APPEND_ROOTS_FRONTS_SLOT 25u" in header
            and ("#define LISP65_C2_APPEND_FRONTS_SLOT "
                 "LISP65_C2_APPEND_ROOTS_FRONTS_SLOT") in header
            and "#define LISP65_C2_APPEND_ABORT_CONTROL_SLOT 45u" in header,
    }
    require(all(checks.values()), "roots/fronts source contract red: "
            + str([name for name, ok in checks.items() if not ok]))
    return {"status": "passed", "checks": checks,
            "marker_source_mutations": marker_mutations,
            "runtime": bind(RUNTIME), "header": bind(HEADER)}


def run_wplto() -> dict[str, Any]:
    old_apply = STAGE.apply_profile
    old_features = STAGE.feature_set
    old_derived_out = DERIVED.OUT

    def apply_profile(base_configure: Any) -> None:
        old_apply(base_configure)
        configure_roots_fronts()

    def feature_set() -> tuple[str, ...]:
        features = old_features()
        require(FEATURE not in features, "roots/fronts feature duplicated")
        return (*features, FEATURE)

    try:
        STAGE.apply_profile = apply_profile
        STAGE.feature_set = feature_set
        DERIVED.OUT = OUT
        return DERIVED.product_wplto()
    finally:
        STAGE.apply_profile = old_apply
        STAGE.feature_set = old_features
        DERIVED.OUT = old_derived_out


def product_gate(product: dict[str, Any]) -> dict[str, Any]:
    elf = ROOT / product["artifacts"]["measurement_elf"]["path"]
    truth = ElfTruth.read(elf, llvm_readobj=P.TOOLCHAIN / "llvm-readobj")
    fused = truth.section(".lisp65_rt_c2append_roots_fronts")
    retired = {
        name: name in truth.sections_by_name for name in (
            ".lisp65_rt_c2append_roots", ".lisp65_rt_c2append_fronts")}
    require(0 < fused.bytes <= CAP, "roots/fronts fused slice exceeds cap")
    require(not any(retired.values()), "roots/fronts predecessor survived")
    symbols = {
        name: truth.symbol(name) for name in (
            "c2_append_roots_phase", "c2_append_fronts_phase",
            "c2_append_roots_fronts_phase")}
    require(all(symbol.section == fused.name and symbol.bytes > 0
                for symbol in symbols.values()),
            "one of the two entries or dispatcher escaped the fused section")
    session = product["capacity"]["session_aggregate"]
    require(session["bytes"] == EXPECTED_SESSION_BYTES
            and session["headroom_bytes"] == EXPECTED_SESSION_HEADROOM,
            f"Session aggregate did not recover one quantum: {session}")
    require(P.SESSION_SERVICE_SLOT_BASE == 46
            and len(P.SESSION_SLICE_SPECS) == 50,
            "post-WPLTO append ABI drift")
    return {
        "status": "passed-one-slice-two-entry-aggregate-recovery",
        "slice": {"section": fused.name, "bytes": fused.bytes,
                  "headroom_to_cap": CAP - fused.bytes},
        "entry_symbols": {
            name: {"address": symbol.value, "bytes": symbol.bytes,
                   "section": symbol.section}
            for name, symbol in symbols.items()},
        "predecessor_sections_present": retired,
        "catalog_records_before": 51, "catalog_records_after": 50,
        "pack_quantum_recovered_bytes": PACK_QUANTUM,
        "session_family_bytes": session["bytes"],
        "session_family_headroom_bytes": session["headroom_bytes"],
    }


def first_red(error: BaseException) -> None:
    value = {
        "format": "lisp65-c2-lite-v6-roots-fronts-coresident-first-red-v1",
        "recorded_on": "2026-07-22",
        "status": "FIRST RED: roots/fronts co-resident WPLTO stopped",
        "failure": {"type": type(error).__name__, "message": str(error)},
        "scope": {"whole_program_lto_probes": int(any(
                      OUT.rglob("c2-lite-v6-full-seed.prg.elf"))),
                  "product_links": 0, "hardware_runs": 0,
                  "promotable": False},
        "evidence": [bind(path) for path in sorted(OUT.rglob("*"))
                     if path.is_file()],
        "rollback_line": {**bind(DERIVED.BASE.LINK40_PRODUCT),
                          "status": "untouched"},
        "next_gate": "Return to Class-C review; no product link or hardware",
    }
    write_json(RECEIPT, value)
    protect()


def build() -> dict[str, Any]:
    require(not OUT.exists() and not RECEIPT.exists(), "probe already exists")
    require(AUTHORITY.is_file() and sha(AUTHORITY) == AUTHORITY_SHA,
            "derived family/slot WPLTO authority drift")
    OUT.mkdir(parents=True)
    source = source_gate()
    cutpoints = cutpoint_gate()
    product = run_wplto()
    capacity = product_gate(product)
    value = {
        "format": "lisp65-c2-lite-v6-roots-fronts-coresident-wplto-v1",
        "recorded_on": "2026-07-22",
        "status": "passed-roots-fronts-coresident-product-shaped-WPLTO",
        "scope": {"whole_program_lto_probes": 1, "product_links": 0,
                  "hardware_runs": 0, "promotable": False},
        "authority": {"derived_family_slot_wplto": bind(AUTHORITY),
                      "driver": bind(Path(__file__))},
        "source_contract": source, "cutpoint_fixtures": cutpoints,
        "product_shaped_wplto": product,
        "aggregate_recovery": capacity,
        "claim_limit": "WPLTO structure and capacity only; no product link, "
                       "hardware, latency, promotion or acceptance claim.",
        "rollback_line": {**bind(DERIVED.BASE.LINK40_PRODUCT),
                          "status": "untouched"},
        "latency_attempts_consumed": "0/2",
        "next_gate": "Owner-authorized successor product link",
    }
    write_json(OUT / "roots-fronts-coresident-wplto-report.json", value)
    value["probe_report"] = bind(
        OUT / "roots-fronts-coresident-wplto-report.json")
    write_json(RECEIPT, value)
    protect()
    return value


def main() -> int:
    try:
        value = build()
    except Exception as error:
        if OUT.exists() and not RECEIPT.exists():
            first_red(error)
        print("c2-lite-roots-fronts-coresident: FIRST RED " + str(error))
        return 2
    cap = value["aggregate_recovery"]
    walls = value["product_shaped_wplto"]["capacity"]["walls"]
    print("c2-lite-roots-fronts-coresident: PASS "
          f"slice={cap['slice']['bytes']}B session={cap['session_family_bytes']}B "
          f"headroom={cap['session_family_headroom_bytes']}B "
          f"text={walls['bank0_text_headroom_bytes']}B "
          f"e000={walls['e000_headroom_bytes']}B product-link=0 hardware=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
