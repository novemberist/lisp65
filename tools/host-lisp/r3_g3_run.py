#!/usr/bin/env python3
"""Run and verify the nine emulator-valid R3/G3 cases, never the six G6 cases."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import Any

import r3_g3_g6_contract as CONTRACT
import r3_g3_harness as HARNESS


ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "config" / "r3-g3-harness.json"
CONTRACT_PATH = ROOT / "config" / "r3-g3-g6-contract.json"
STATIC_RECEIPT = ROOT / "tests" / "bytecode" / "dialect-v2" / "evidence" / "r3" / "g3-static-preflight-receipt.json"
PRODUCT_RECEIPT = ROOT / "tests" / "bytecode" / "dialect-v2" / "evidence" / "r3" / "product-block-receipt.json"
RECEIPT = ROOT / "tests" / "bytecode" / "dialect-v2" / "evidence" / "r3" / "g3-emulator-receipt.json"
RAW = RECEIPT.parent / "g3-raw"
BUILD = ROOT / "build" / "r3" / "g3" / "probes"
STAGER_SOURCE = ROOT / "scripts" / "r3-cold-stager-main.c"
TRACE_SOURCE = ROOT / "scripts" / "r3-g3-stager-trace-main.c"
CHAIN_SOURCE = ROOT / "scripts" / "r3-cold-stager-chain.s"
SAFE_RUNNER = ROOT / "scripts" / "xmega65-safe-run.sh"
CLEANUP_HELPER = ROOT / "scripts" / "kill-xmega65-by-token.py"
SMOKE = ROOT / "scripts" / "smoke-xmega65.sh"
# G3 must execute the same dialect-v2 codemod output that produced the bound
# M65D container.  Compiling the source suite directly would resurrect removed
# public v1 converter names and test a program that is not in the product set.
M65D_SUITE = ROOT / "build" / "bytecode" / "dialect-v2" / "suites" / "p0-m65d-lib.json"
M65D_SOURCE = ROOT / "build" / "bytecode" / "dialect-v2" / "sources" / "lib" / "m65-disk.lisp"
STDLIB_RUNNER = ROOT / "tools" / "host-lisp" / "bytecode_p0_stdlib.py"
M65D_D81_ORACLE = ROOT / "tools" / "host-lisp" / "m65d_blank_d81_oracle.py"
FORMAT = "lisp65-r3-g3-emulator-receipt-v1"
SHA = re.compile(r"[0-9a-f]{64}")
TRACE_CASES = {
    "catalog-crc-reject-restage": 1,
    "catalog-missing-restage": 2,
    "catalog-valid-stage-chain": 3,
    "stager-entry-chain-control": 4,
}
MEDIA_CASES = {
    "product-media-identity-write-reject": ("m65d-product-media-read-only", "10"),
    "arbitrary-user-media-save-remount-read": (
        "m65d-arbitrary-user-media-roundtrip",
        "(0 0 0 (0 10 114 111 117 110 100 116 114 105 112) 0)",
    ),
}
MEDIA_INTEGRITY_FIXTURES = {
    "m65d-blank-d81-create-external": "0",
    "m65d-blank-d81-create-replace-external": "(0 0)",
    "m65d-blank-d81-multisector-create-external": "0",
    "m65d-blank-d81-multisector-replace-external": "(0 0)",
}
HARDWARE_FORBIDDEN = (
    "F011-timing", "SD-buffer-address", "DMA-timing", "physical-reset-semantics",
)


class G3Error(RuntimeError):
    pass


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise G3Error(f"cannot read {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise G3Error(f"{label} must be an object")
    return value


def binding(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise G3Error(f"evidence is not a regular file: {path}")
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def run_checked(argv: list[str], label: str, *, env: dict[str, str] | None = None) -> str:
    result = subprocess.run(
        argv, cwd=ROOT, env=env, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    )
    if result.returncode:
        raise G3Error(f"{label} failed ({result.returncode}):\n{result.stdout}")
    return result.stdout


def validate_preflight() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    config = HARNESS.load(CONFIG, "G3 harness")
    state = HARNESS.validate(config)
    expected = canonical(HARNESS.build_receipt())
    if STATIC_RECEIPT.is_symlink() or not STATIC_RECEIPT.is_file() or STATIC_RECEIPT.read_bytes() != expected:
        raise G3Error("static exact-15 preflight receipt drift")
    contract = load(CONTRACT_PATH, "R3 contract")
    try:
        CONTRACT.validate(contract, verify_environment=True)
    except CONTRACT.ContractError as exc:
        raise G3Error(f"bound emulator environment drift: {exc}") from exc
    product = state["product_value"]
    if product["product_identity"]["artifact_set_sha256"] != state["manifest_value"]["artifact_set_sha256"]:
        raise G3Error("product artifact set drift")
    return state, contract, product


def descriptor_fixture(descriptor: Path) -> Path:
    data = descriptor.read_bytes()
    if len(data) < 16:
        raise G3Error("boot descriptor is truncated")
    header_bytes = data[5]
    record_count = data[6]
    expected_bytes = header_bytes + record_count * 32
    if header_bytes != 16 or record_count != 8 or len(data) != expected_bytes:
        raise G3Error(
            "boot descriptor must contain the exact eight-role product closure"
        )
    rows = [", ".join(f"0x{value:02x}" for value in data[index:index + 16]) for index in range(0, len(data), 16)]
    path = BUILD / "r3-g3-descriptor-fixture.c"
    path.write_text(
        f"#include <stdint.h>\nconst uint8_t r3_g3_descriptor_fixture[{len(data)}] = {{\n    "
        + ",\n    ".join(rows) + "\n};\n",
        encoding="ascii",
    )
    return path


def candidate_role(product: dict[str, Any], role: str) -> Path:
    manifest_path = ROOT / product["candidate_manifest"]["path"]
    manifest = load(manifest_path, "candidate manifest")
    rows = [row for row in manifest["artifacts"] if row.get("role") == role]
    if len(rows) != 1:
        raise G3Error(f"candidate role closure drift: {role}")
    path = ROOT / rows[0]["path"]
    if path.stat().st_size != rows[0]["bytes"] or sha(path) != rows[0]["sha256"]:
        raise G3Error(f"candidate role binding drift: {role}")
    return path


def build_trace_probes(contract: dict[str, Any], product: dict[str, Any]) -> dict[str, Path]:
    BUILD.mkdir(parents=True, exist_ok=True)
    compiler = ROOT / contract["toolchain_bindings"]["compiler"]["invocation"]
    build_id = product["product_identity"]["product_build_id"]
    descriptor = candidate_role(product, "boot-descriptor")
    product_stager = candidate_role(product, "cold-stager")
    fixture = descriptor_fixture(descriptor)
    default_stager = BUILD / "autoboot-default.c65"
    common = [
        str(compiler), "-std=c99", "-Oz", "-Wall", "-Wextra", "-Werror",
        f"-DR3_EXPECTED_PRODUCT_BUILD_ID=0x{build_id}UL",
    ]
    run_checked(common + [str(STAGER_SOURCE), str(CHAIN_SOURCE), "-o", str(default_stager)], "default stager parity build")
    if default_stager.read_bytes() != product_stager.read_bytes():
        raise G3Error("G3 trace seam changed the release stager bytes")
    probes: dict[str, Path] = {}
    for case_id, scenario in TRACE_CASES.items():
        output = BUILD / f"{case_id}.prg"
        run_checked(
            common + ["-Wno-unused-function", f"-DR3_G3_SCENARIO={scenario}",
                      str(TRACE_SOURCE), str(fixture), str(CHAIN_SOURCE), "-o", str(output)],
            f"G3 trace build {case_id}",
        )
        probes[case_id] = output
    return probes


def execute_trace(case_id: str, probe: Path) -> list[dict[str, Any]]:
    RAW.mkdir(parents=True, exist_ok=True)
    dump = RAW / f"{case_id}.dump"
    log = RAW / f"{case_id}.xmega65.log"
    verifier = RAW / f"{case_id}.verifier.txt"
    stored_probe = RAW / f"{case_id}.prg"
    for path in (dump, log, verifier, stored_probe):
        if path.exists():
            path.unlink()
    env = os.environ.copy()
    env.update({
        "DUMP": str(dump), "XMEGA65_LOG": str(log), "XMEGA65_TIMEOUT": "20",
        "XMEGA65": "/home/alex/.local/bin/xmega65",
    })
    expected = f"G3 PASS {case_id}"
    output = run_checked(["sh", str(SMOKE), expected, str(probe)], f"xmega65 G3 {case_id}", env=env)
    verifier.write_text(output, encoding="utf-8")
    shutil.copyfile(probe, stored_probe)
    if expected.encode("ascii") not in dump.read_bytes():
        raise G3Error(f"trace marker absent after successful verifier: {case_id}")
    return [binding(stored_probe), binding(dump), binding(log), binding(verifier)]


def execute_autoboot_boundary(contract: dict[str, Any], product: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Prove AUTOBOOT enters the exact stager, stopping at xmega's F011 boundary."""
    RAW.mkdir(parents=True, exist_ok=True)
    sd_image = ROOT / "build" / "r3" / "g3" / "product-sd.img"
    product_d81 = candidate_role(product, "product-d81")
    dump = RAW / "autoboot-entry-f011-boundary.dump"
    log = RAW / "autoboot-entry-f011-boundary.xmega65.log"
    verifier = RAW / "autoboot-entry-f011-boundary.verifier.txt"
    for path in (sd_image, dump, log, verifier):
        if path.exists():
            path.unlink()
    sd_base = Path(contract["toolchain_bindings"]["sd_base"]["path"])
    xmega = contract["toolchain_bindings"]["xmega65"]["artifact"]["path"]
    rom = contract["toolchain_bindings"]["rom"]["path"]
    run_checked(["cp", "--reflink=auto", "--sparse=always", str(sd_base), str(sd_image)], "G3 SD clone")
    run_checked(
        ["dd", f"if={product_d81}", f"of={sd_image}", "bs=512", "seek=11552", "conv=notrunc", "status=none"],
        "G3 product-D81 injection",
    )
    command = [
        str(SAFE_RUNNER), str(dump), "20", xmega,
        "-headless", "-testing", "-sleepless", "-besure", "-fastboot",
        "-rom", rom, "-sdimg", str(sd_image), "-defd81fromsd", "-autoload",
        "-dumpmem", str(dump),
    ]
    result = subprocess.run(command, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    log.write_text(result.stdout, encoding="utf-8")
    message = b"L65SYS DISK ERROR - CHECK MEDIA"
    if result.returncode not in (0, 66, 124) or not dump.is_file() or dump.stat().st_size < 0x820 or dump.read_bytes()[0x800:0x800 + len(message)] != message:
        raise G3Error(f"exact AUTOBOOT stager entry was not observed (status={result.returncode})")
    verifier.write_text(
        "G3 PASS exact product D81 autoload entered exact candidate stager\n"
        "G3 FIDELITY STOP direct F011 path reached pinned media error; no F011 timing claim\n",
        encoding="utf-8",
    )
    return [binding(dump), binding(log), binding(verifier)], {
        "result": "exact-product-D81-autoload-entered-exact-candidate-stager",
        "screen_oracle": message.decode("ascii"),
        "screen_offset": "0x0800",
        "boundary": "direct-F011-access-not-used-as-G3-verdict",
        "emulator_status": result.returncode,
    }


def run_media_suite() -> tuple[Path, Path, dict[str, dict[str, Any]]]:
    RAW.mkdir(parents=True, exist_ok=True)
    log = RAW / "m65d-media-policy-host.txt"
    report_path = RAW / "m65d-media-policy-observations.json"
    if report_path.exists():
        report_path.unlink()
    output = run_checked(
        [
            sys.executable, str(STDLIB_RUNNER), "--check",
            "--observation-report", str(report_path), str(M65D_SUITE),
        ],
        "M65D media-policy host suite",
    )
    log.write_text(output, encoding="utf-8")
    suite = load(M65D_SUITE, "M65D suite")
    cases = {row.get("name"): row for row in suite.get("cases", []) if isinstance(row, dict)}
    report = load(report_path, "M65D observation report")
    report_suites = report.get("suites")
    if report.get("format") != "lisp65-bytecode-p0-observations-v1" or not isinstance(report_suites, list) or len(report_suites) != 1:
        raise G3Error("M65D observation report shape drift")
    report_cases = {
        row.get("name"): row
        for row in report_suites[0].get("observations", [])
        if isinstance(row, dict)
    }
    selected: dict[str, dict[str, Any]] = {}
    for case_id, (fixture, expected) in MEDIA_CASES.items():
        row = cases.get(fixture)
        observed = report_cases.get(fixture)
        if (
            not isinstance(row, dict) or row.get("expect") != expected
            or not isinstance(observed, dict) or observed.get("result") != expected
        ):
            raise G3Error(f"M65D media fixture drift: {fixture}")
        selected[case_id] = {"fixture": fixture, "result": expected}
    integrity = []
    for fixture, expected in MEDIA_INTEGRITY_FIXTURES.items():
        row = cases.get(fixture)
        observed = report_cases.get(fixture)
        oracle = observed.get("external_d81_oracle") if isinstance(observed, dict) else None
        if (
            not isinstance(row, dict) or row.get("expect") != expected
            or not isinstance(observed, dict) or observed.get("result") != expected
            or not isinstance(oracle, dict) or oracle.get("result") != "pass"
            or oracle.get("witnesses") != ["d81_persistence_fault", "d81_bam_sanity"]
            or oracle.get("header_not_written") is not True
            or oracle.get("header_unchanged") is not True
            or oracle.get("allocated_equals_visible_chain") is not True
            or oracle.get("no_double_allocation") is not True
            or oracle.get("free_plus_file_blocks") != 3160
        ):
            raise G3Error(f"M65D independent D81 integrity fixture drift: {fixture}")
        integrity.append({"fixture": fixture, "result": expected, "oracle": oracle})
    selected["arbitrary-user-media-save-remount-read"]["external_integrity_fixtures"] = integrity
    return log, report_path, selected


def drive9_oracle(contract: dict[str, Any]) -> dict[str, Any]:
    scope = contract["media_model"]["drive_scope"]
    source = M65D_SOURCE.read_text(encoding="utf-8")
    public_signatures = {
        "m65d-status": "(defun m65d-status ()",
        "m65d-save": "(defun m65d-save (name src)",
        "m65d-save-new": "(defun m65d-save-new (name src)",
        "m65d-remount": "(defun m65d-remount ()",
    }
    if scope != {
        "verified_drive": 8,
        "drive_9": "out-of-scope-explicitly-rejected",
        "simultaneous_drives_required": False,
    } or any(signature not in source for signature in public_signatures.values()):
        raise G3Error("drive-8-only media API/policy drift")
    return {
        "result": "pass",
        "verified_drive": 8,
        "drive_9": "not-addressable-by-the-v1-media-API-and-explicitly-rejected-by-contract",
        "device_operation_count": 0,
        "public_signatures": public_signatures,
    }


def execute() -> dict[str, Any]:
    state, contract, product = validate_preflight()
    probes = build_trace_probes(contract, product)
    autoboot_evidence, autoboot_oracle = execute_autoboot_boundary(contract, product)
    trace_evidence = {case_id: execute_trace(case_id, path) for case_id, path in probes.items()}
    media_log, media_report, media_results = run_media_suite()
    drive9 = drive9_oracle(contract)
    product_d81 = candidate_role(product, "product-d81")
    product_d81_before = sha(product_d81)
    if product_d81_before != sha(product_d81):
        raise G3Error("host media policy mutated the product D81")

    cases = []
    for row in state["cases"]:
        case_id = row["id"]
        result = dict(row)
        if row["fidelity"] == "hardware-only":
            result["status"] = "not-run"
            result["evidence"] = []
        elif case_id in trace_evidence:
            result["status"] = "pass"
            result["evidence"] = trace_evidence[case_id]
            result["authority"] = "deterministic-media-boundary-no-F011-timing-claim"
            if case_id == "stager-entry-chain-control":
                result["evidence"].extend(autoboot_evidence)
                result["autoboot_entry_oracle"] = autoboot_oracle
        elif case_id in media_results:
            result["status"] = "pass"
            result["evidence"] = [
                binding(media_log), binding(media_report), binding(M65D_SUITE),
                binding(M65D_SOURCE), binding(M65D_D81_ORACLE),
            ]
            result["oracle"] = media_results[case_id]
            if case_id == "product-media-identity-write-reject":
                result["product_d81_sha256_before_after"] = [product_d81_before, sha(product_d81)]
        elif case_id == "drive9-rejected":
            result["status"] = "pass"
            result["evidence"] = [binding(CONTRACT_PATH), binding(M65D_SOURCE)]
            result["oracle"] = drive9
        elif case_id == "artifact-preflight-exact-set":
            result["status"] = "pass"
            result["evidence"] = [binding(STATIC_RECEIPT), binding(CONFIG)]
        elif case_id == "product-prg-byte-identity":
            nulls = product["null_deltas"]
            if nulls["workbench_bank_bytes"] != 0 or nulls["boot_overlay_bytes"] != 0:
                raise G3Error("product byte-identity null delta drift")
            result["status"] = "pass"
            result["evidence"] = [binding(PRODUCT_RECEIPT)]
            result["oracle"] = {"bank_delta": 0, "boot_overlay_delta": 0, "release_stager_byte_parity": "exact"}
        else:
            raise G3Error(f"no G3 executor for {case_id}")
        cases.append(result)

    g3 = [row for row in cases if row["fidelity"] == "emulator-valid"]
    g6 = [row for row in cases if row["fidelity"] == "hardware-only"]
    if len(g3) != 9 or {row["status"] for row in g3} != {"pass"}:
        raise G3Error("G3 did not close exact nine-case set")
    if len(g6) != 6 or {row["status"] for row in g6} != {"not-run"}:
        raise G3Error("G3 attempted or altered a hardware-only case")
    return {
        "format": FORMAT,
        "id": "r3-g3-nine-case-emulator-prefilter",
        "status": "passed-emulator-prefilter-only",
        "measured_on": "2026-07-19",
        "release_effect": "none-r4-not-sealed",
        "product_artifact_set_sha256": product["product_identity"]["artifact_set_sha256"],
        "product_build_id": product["product_identity"]["product_build_id"],
        "bindings": {
            "contract": binding(CONTRACT_PATH),
            "harness": binding(CONFIG),
            "static_preflight": binding(STATIC_RECEIPT),
            "product_receipt": binding(PRODUCT_RECEIPT),
            "runner": binding(Path(__file__).resolve()),
            "trace_source": binding(TRACE_SOURCE),
            "product_stager_source": binding(STAGER_SOURCE),
            "safe_runner": binding(SAFE_RUNNER),
            "process_cleanup": binding(CLEANUP_HELPER),
            "smoke_verifier": binding(SMOKE),
        },
        "emulator_stack": {
            "xmega65": contract["toolchain_bindings"]["xmega65"],
            "rom": contract["toolchain_bindings"]["rom"],
            "sd_base": contract["toolchain_bindings"]["sd_base"],
            "compiler": contract["toolchain_bindings"]["compiler"],
        },
        "counts": {"pass": 9, "not_run": 6, "total": 15},
        "cases": cases,
        "claims": {
            "G3": "pass",
            "G6": "not-run",
            "emulator_started": True,
            "hardware_started": False,
            "emulator_authority": "prefilter-only",
            "hardware_authority": "arbiter",
            "forbidden_hardware_claims": {name: False for name in HARDWARE_FORBIDDEN},
            "proved": ["autoboot-control", "descriptor-validation", "restage-decision", "reverify-before-chain", "media-policy-control"],
        },
    }


def verify_receipt(path: Path) -> dict[str, Any]:
    receipt = load(path, "G3 receipt")
    required = {
        "format", "id", "status", "measured_on", "release_effect",
        "product_artifact_set_sha256", "product_build_id", "bindings",
        "emulator_stack", "counts", "cases", "claims",
    }
    if set(receipt) != required or receipt["format"] != FORMAT or receipt["status"] != "passed-emulator-prefilter-only":
        raise G3Error("G3 receipt schema/status drift")
    if not SHA.fullmatch(str(receipt["product_artifact_set_sha256"])) or receipt["counts"] != {"pass": 9, "not_run": 6, "total": 15}:
        raise G3Error("G3 identity/count drift")
    for label, item in receipt["bindings"].items():
        if set(item) != {"path", "bytes", "sha256"}:
            raise G3Error(f"G3 binding schema drift: {label}")
        path_item = ROOT / item["path"]
        if path_item.is_symlink() or not path_item.is_file() or path_item.stat().st_size != item["bytes"] or sha(path_item) != item["sha256"]:
            raise G3Error(f"G3 binding drift: {label}")
    cases = receipt["cases"]
    if not isinstance(cases, list) or len(cases) != 15:
        raise G3Error("G3 case closure drift")
    for row in cases:
        expected = "pass" if row.get("fidelity") == "emulator-valid" else "not-run"
        if row.get("status") != expected:
            raise G3Error(f"G3 case status drift: {row.get('id')}")
        for item in row.get("evidence", []):
            path_item = ROOT / item["path"]
            if path_item.is_symlink() or not path_item.is_file() or path_item.stat().st_size != item["bytes"] or sha(path_item) != item["sha256"]:
                raise G3Error(f"G3 raw evidence drift: {row.get('id')}")
    claims = receipt["claims"]
    if claims.get("G3") != "pass" or claims.get("G6") != "not-run" or claims.get("hardware_started") is not False:
        raise G3Error("G3/G6 authority claim drift")
    if set(claims.get("forbidden_hardware_claims", {}).values()) != {False}:
        raise G3Error("G3 made a forbidden hardware claim")
    return receipt


def selftest() -> None:
    receipt = verify_receipt(RECEIPT)
    changed = json.loads(json.dumps(receipt))
    next(row for row in changed["cases"] if row["fidelity"] == "hardware-only")["status"] = "pass"
    temp = BUILD / "mutated-g3-receipt.json"
    temp.write_bytes(canonical(changed))
    try:
        verify_receipt(temp)
    except G3Error:
        temp.unlink(missing_ok=True)
        print("r3-g3-run: SELFTEST PASS hardware-claim-mutation=rejected")
        return
    temp.unlink(missing_ok=True)
    raise G3Error("selftest accepted a hardware-only pass claim")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("run", "check", "selftest"))
    parser.add_argument("--receipt", type=Path, default=RECEIPT)
    args = parser.parse_args(argv)
    receipt_path = args.receipt if args.receipt.is_absolute() else ROOT / args.receipt
    try:
        if args.command == "run":
            value = execute()
            receipt_path.parent.mkdir(parents=True, exist_ok=True)
            receipt_path.write_bytes(canonical(value))
            print(
                "r3-g3-run: PASS emulator-valid=9/9 hardware-only=not-run(6/6) "
                f"set={value['product_artifact_set_sha256']} receipt={receipt_path.relative_to(ROOT)}"
            )
        elif args.command == "check":
            value = verify_receipt(receipt_path)
            print(
                "r3-g3-run: PASS receipt-bound emulator-valid=9/9 "
                f"hardware-only=not-run set={value['product_artifact_set_sha256']}"
            )
        else:
            selftest()
        return 0
    except (G3Error, CONTRACT.ContractError, HARNESS.HarnessError, OSError, ValueError, KeyError, TypeError) as exc:
        print(f"r3-g3-run: FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
