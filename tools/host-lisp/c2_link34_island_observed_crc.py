#!/usr/bin/env python3
"""Build and evaluate the authorized Link-34 observed-CRC diagnostic probe."""

from __future__ import annotations

import argparse
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
import c2_link33_bss_triage_product_link as BASE  # noqa: E402
import c2_link34_island_status_latch as STATUS  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
SOURCE = ROOT / "src/vm_runtime_overlay.c"
LINK34_PRODUCT = STATUS.LINK34_PRODUCT
LINK34_ELF = STATUS.LINK34_ELF
LINK34_RECEIPT = STATUS.LINK34_RECEIPT
PRIOR_DIAGNOSIS = EVIDENCE / (
    "c2.2-product-link34-catalog-verifier-transport-hardware-first-red-"
    "diagnosis.json")
PRIOR_DIAGNOSIS_SHA = (
    "ea979619a7608f31a0b6863209742a24b2a04c798e75e33cb5ec90c4cdc0e596")

DEFINES = {
    "double": "LISP65_C2_ISLAND_DIAGNOSTIC_CRC_LATCH_DOUBLE",
    "single": "LISP65_C2_ISLAND_DIAGNOSTIC_CRC_LATCH_SINGLE",
}
PROBE_OUTS = {
    mode: ROOT / f"build/c2.2/substitution/link34-observed-crc-{mode}-wplto"
    for mode in DEFINES
}
PROBE_RECEIPTS = {
    mode: EVIDENCE / f"c2.2-link34-observed-crc-{mode}-wplto-probe-receipt.json"
    for mode in DEFINES
}
LINK_OUT = ROOT / "build/c2.2/substitution/link34-observed-crc-diagnostic"
LINK_RECEIPT = EVIDENCE / (
    "c2.2-link34-observed-crc-diagnostic-link-receipt.json")
HARDWARE_OUT = ROOT / "build/c2.2/link34-observed-crc-hardware"
HARDWARE_RESULT = HARDWARE_OUT / "hardware-result.json"


class GateError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise GateError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"observed-CRC artifact absent: {path}")
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")


def run(command: list[str]) -> str:
    result = subprocess.run(command, cwd=ROOT, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            check=False)
    if result.returncode:
        raise GateError(
            f"command failed ({result.returncode}): {' '.join(command)}: "
            f"{(result.stderr or result.stdout).strip()}")
    require(not result.stderr.strip(),
            f"unexpected tool diagnostic: {result.stderr.strip()}")
    return result.stdout


def prerequisites(mode: str) -> dict[str, Any]:
    require(mode in DEFINES, f"unsupported observed-CRC mode: {mode}")
    require(PRIOR_DIAGNOSIS.is_file()
            and sha(PRIOR_DIAGNOSIS) == PRIOR_DIAGNOSIS_SHA,
            "transport First-Red diagnosis drift")
    diagnosis = json.loads(PRIOR_DIAGNOSIS.read_text(encoding="utf-8"))
    require(diagnosis.get("status") ==
            "FIRST RED: catalog-verifier tuple payload CRC before verifier entry"
            and diagnosis.get("promotable") is False,
            "transport First-Red diagnosis is not authoritative")
    source = SOURCE.read_text(encoding="utf-8")
    required = (
        DEFINES[mode],
        "observed_crc = rtov_crc_mem((const uint8_t *)RTOV_TARGET, file_len);",
        "((volatile uint8_t *)&rtov_call_context)[0] =",
        "((volatile uint8_t *)&rtov_call_context)[1] =",
    )
    for token in required:
        require(token in source, f"observed-CRC source token absent: {token}")
    if mode == "double":
        require(source.count(
                    "observed_crc = rtov_crc_mem((const uint8_t *)RTOV_TARGET, "
                    "file_len);") >= 3,
                "double observed-CRC source has no repeated calculation")
    return {
        "transport_first_red": bind(PRIOR_DIAGNOSIS),
        "link34_rollback_product": {**bind(LINK34_PRODUCT),
                                    "status": "untouched"},
        "link34_structural_baseline": bind(LINK34_RECEIPT),
        "diagnostic_source": bind(SOURCE),
    }


def symbols(path: Path) -> dict[str, dict[str, int | str]]:
    result: dict[str, dict[str, int | str]] = {}
    text = run([str(STATUS.TOOLCHAIN / "llvm-nm"), "--defined-only",
                "--print-size", "--numeric-sort", str(path)])
    for line in text.splitlines():
        fields = line.split()
        if len(fields) >= 4:
            result[fields[-1]] = {
                "address": int(fields[0], 16),
                "bytes": int(fields[1], 16),
                "type": fields[2],
            }
    return result


def function_disassembly(
    elf: Path, name: str, table: dict[str, dict[str, int | str]],
) -> str:
    row = table[name]
    begin = int(row["address"])
    end = begin + int(row["bytes"])
    text = run([str(STATUS.TOOLCHAIN / "llvm-objdump"), "-d",
                "--no-show-raw-insn", "--symbolize-operands", str(elf)])
    lines: list[str] = []
    for line in text.splitlines():
        match = re.match(r"^\s*([0-9a-f]+):", line)
        if match and begin <= int(match.group(1), 16) < end:
            lines.append(line)
    require(lines, f"no disassembly for observed-CRC owner {name}")
    return "\n".join(lines)


def classify(first: int, second: int | None, expected: int) -> str:
    require(0 <= first <= 0xffff and 0 <= expected <= 0xffff,
            "CRC outside u16 domain")
    require(first != expected,
            "first observed CRC does not reproduce the authorized First Red")
    if second is None:
        return "single-observation-transport-divergence"
    require(0 <= second <= 0xffff, "second CRC outside u16 domain")
    if second == expected:
        return "completion-ordering-candidate-second-read-converged"
    if second == first:
        return "stable-cpu-view-divergence"
    return "evolving-or-partially-visible-cpu-view"


def selftest() -> dict[str, str]:
    cases = {
        "second-converges": (0x1111, 0xce8c, 0xce8c,
                             "completion-ordering-candidate-second-read-converged"),
        "stable-wrong": (0x1111, 0x1111, 0xce8c,
                         "stable-cpu-view-divergence"),
        "evolving-wrong": (0x1111, 0x2222, 0xce8c,
                           "evolving-or-partially-visible-cpu-view"),
        "single": (0x1111, None, 0xce8c,
                   "single-observation-transport-divergence"),
    }
    for name, (first, second, expected, want) in cases.items():
        require(classify(first, second, expected) == want,
                f"observed-CRC model drift: {name}")
    rejected = 0
    try:
        classify(0xce8c, 0xce8c, 0xce8c)
    except GateError:
        rejected += 1
    require(rejected == 1, "matching first CRC mutation accepted")
    return {name: "passed" for name in (*cases, "matching-first-rejected")}


def crc_latch_elf_gate(elf: Path, mode: str) -> dict[str, Any]:
    current = symbols(elf)
    baseline = symbols(LINK34_ELF)
    state_names = ("rtov_call_context", "rtov_call_result",
                   "rtov_loaded_len", "rtov_fault")
    state: dict[str, Any] = {}
    for name in state_names:
        require(name in current and name in baseline,
                f"observed-CRC state symbol absent: {name}")
        require(current[name] == baseline[name],
                f"observed-CRC latch allocated or moved state: {name}")
        state[name] = current[name]
    require(current["rtov_call_context"]["bytes"] == 2
            and current["rtov_call_result"]["bytes"] == 2,
            "observed-CRC latch is not the existing four-byte tuple")
    body = function_disassembly(
        elf, "vm_runtime_overlay_exec_family", current)
    addresses = [
        int(current["rtov_call_context"]["address"]),
        int(current["rtov_call_context"]["address"]) + 1,
    ]
    if mode == "double":
        addresses.extend((
            int(current["rtov_call_result"]["address"]),
            int(current["rtov_call_result"]["address"]) + 1,
        ))
    missing = [address for address in addresses
               if not re.search(
                   rf"\b(?:sta|stx|sty|stz)\s+\${address:x}\b", body)]
    require(not missing,
            f"observed-CRC final stores absent: {missing}")
    require(body.count("rtov_crc_mem") >= (2 if mode == "double" else 1),
            "final WPLTO body lacks requested CRC observations")
    return {
        "status": "passed-existing-four-byte-observed-crc-latch",
        "mode": mode,
        "owner": "vm_runtime_overlay_exec_family",
        "state_symbols": state,
        "store_addresses": [f"0x{address:02x}" for address in addresses],
        "new_state_bytes": 0,
        "decision_uses_first_crc": True,
        "second_crc_is_observation_only": mode == "double",
        "fail_closed_wipe_unchanged": True,
        "negative_matrix": selftest(),
    }


def protect(out: Path, receipt: Path) -> None:
    BASE.protect(out)
    os.chmod(receipt, 0o444)


def first_red(
    out: Path, receipt: Path, stage: str, mode: str, error: BaseException,
) -> dict[str, Any]:
    value = {
        "format": "lisp65-c2-link34-observed-crc-first-red-v1",
        "recorded_on": "2026-07-21",
        "status": f"FIRST RED: observed-CRC {stage} stopped",
        "mode": mode,
        "promotable": False,
        "diagnostic": {"type": type(error).__name__, "message": str(error)},
        "execution_accounting": {"hardware_runs": 0,
                                 "promotable_product_links": 0},
        "link34_rollback": {**bind(LINK34_PRODUCT), "status": "untouched"},
        "next_gate": "stop before hardware",
    }
    write(receipt, value)
    if out.exists():
        protect(out, receipt)
    else:
        os.chmod(receipt, 0o444)
    return value


def build_probe(mode: str) -> dict[str, Any]:
    out = PROBE_OUTS[mode]
    receipt = PROBE_RECEIPTS[mode]
    require(not out.exists() and not receipt.exists(),
            f"observed-CRC {mode} WPLTO probe already consumed")
    try:
        authority = prerequisites(mode)
        result = STATUS.full_gate_build(
            out, mode=f"observed-crc-{mode}-wplto",
            features=(*BASE.FEATURES, DEFINES[mode]),
            diagnostic_define=DEFINES[mode],
            diagnostic_gate=lambda elf: crc_latch_elf_gate(elf, mode),
        )
        result.update({
            "format": "lisp65-c2-link34-observed-crc-wplto-probe-v1",
            "recorded_on": "2026-07-21",
            "status": "passed-observed-crc-wplto-no-diagnostic-link",
            "mode": mode,
            "promotable": False,
            "authority": authority,
            "claim_limit": (
                "One product-shaped WPLTO capacity/placement probe for the "
                "observed-CRC latch. It is not a product candidate, hardware "
                "evidence or promotion."),
            "next_gate": "one non-promotable diagnostic link in the same mode",
        })
        report = out / "observed-crc-wplto-probe.json"
        write(report, result)
        value = {**result, "report": bind(report)}
        write(receipt, value)
        protect(out, receipt)
        return value
    except (GateError, STATUS.GateError, BASE.LinkError, BASE.PRE.GateError,
            BASE.ISLAND.GateError, RuntimeError, OSError, ValueError, KeyError,
            json.JSONDecodeError, subprocess.SubprocessError) as error:
        return first_red(out, receipt, "WPLTO probe", mode, error)


def selected_probe() -> tuple[str, dict[str, Any]]:
    for mode in ("double", "single"):
        receipt = PROBE_RECEIPTS[mode]
        if not receipt.is_file():
            continue
        value = json.loads(receipt.read_text(encoding="utf-8"))
        if value.get("status") == "passed-observed-crc-wplto-no-diagnostic-link":
            return mode, value
    raise GateError("no green observed-CRC WPLTO probe")


def build_link() -> dict[str, Any]:
    mode, probe = selected_probe()
    require(not LINK_OUT.exists() and not LINK_RECEIPT.exists(),
            "observed-CRC diagnostic link already consumed")
    try:
        result = STATUS.full_gate_build(
            LINK_OUT, mode=f"observed-crc-{mode}-diagnostic-link",
            features=(*BASE.FEATURES, DEFINES[mode]),
            diagnostic_define=DEFINES[mode],
            diagnostic_gate=lambda elf: crc_latch_elf_gate(elf, mode),
        )
        result.update({
            "format": "lisp65-c2-link34-observed-crc-diagnostic-link-v1",
            "recorded_on": "2026-07-21",
            "status": "passed-nonpromotable-observed-crc-link-hardware-not-run",
            "mode": mode,
            "promotable": False,
            "capacity_probe": bind(PROBE_RECEIPTS[mode]),
            "capacity_probe_product_sha256":
                probe["product_identity"]["product"]["sha256"],
            "claim_limit": (
                "One fully gated but permanently non-promotable diagnostic "
                "link. It may be used only for the one authorized observed-CRC "
                "hardware run."),
            "next_gate": "one diagnostic hardware run; stop after capture",
        })
        report = LINK_OUT / "diagnostic-observed-crc-link.json"
        write(report, result)
        value = {**result, "report": bind(report)}
        write(LINK_RECEIPT, value)
        protect(LINK_OUT, LINK_RECEIPT)
        return value
    except (GateError, STATUS.GateError, BASE.LinkError, BASE.PRE.GateError,
            BASE.ISLAND.GateError, RuntimeError, OSError, ValueError, KeyError,
            json.JSONDecodeError, subprocess.SubprocessError) as error:
        return first_red(LINK_OUT, LINK_RECEIPT, "diagnostic link", mode, error)


def check_link() -> dict[str, Any]:
    require(LINK_RECEIPT.is_file(), "observed-CRC diagnostic receipt absent")
    value = json.loads(LINK_RECEIPT.read_text(encoding="utf-8"))
    require(value.get("status") ==
            "passed-nonpromotable-observed-crc-link-hardware-not-run"
            and value.get("promotable") is False,
            "observed-CRC diagnostic link is not green/non-promotable")
    for row in value["product_identity"].values():
        require(bind(ROOT / row["path"]) == row,
                f"observed-CRC identity drift: {row['path']}")
    require(sha(LINK34_PRODUCT) == STATUS.LINK34_PRODUCT_SHA,
            "Link-34 rollback product drift")
    return value


def evaluate_hardware(*, replay: bool = False) -> dict[str, Any]:
    link = check_link()
    if HARDWARE_RESULT.exists():
        require(replay, "observed-CRC hardware result already exists; second run forbidden")
        old_result = json.loads(HARDWARE_RESULT.read_text(encoding="utf-8"))
        require(old_result.get("execution_accounting", {})
                .get("diagnostic_hardware_runs") == 1,
                "observed-CRC replay lacks the one-run hardware account")
    else:
        require(not replay, "observed-CRC replay requested without a hardware result")
    deployment = HARDWARE_OUT / "deployment.json"
    low_path = HARDWARE_OUT / "diagnostic-low-0000-1fff.bin"
    boot_path = HARDWARE_OUT / "diagnostic-boot-family.bin"
    require(deployment.is_file() and low_path.is_file()
            and low_path.stat().st_size == 0x2000 and boot_path.is_file(),
            "observed-CRC hardware captures are incomplete")
    dep = json.loads(deployment.read_text(encoding="utf-8"))
    boot_binding = next(row for row in dep["preloads"]
                        if row["address"] == "0x08200000")
    require(sha(boot_path) == boot_binding["sha256"]
            and boot_path.stat().st_size == boot_binding["bytes"],
            "observed-CRC Boot-family readback drift")
    elf = ROOT / link["product_identity"]["elf"]["path"]
    boot_manifest_path = elf.parent / "runtime-overlays-boot-final.json"
    boot_manifest = json.loads(boot_manifest_path.read_text(encoding="utf-8"))
    catalog = next(row for row in boot_manifest["slices"]
                   if row["name"] == "catalog-verifier")
    require(catalog["file_size"] == 1156 and catalog["file_offset"] == 512,
            "observed-CRC catalog tuple drift")
    table = symbols(elf)
    low = low_path.read_bytes()

    def byte(name: str, offset: int = 0) -> int:
        address = int(table[name]["address"]) + offset
        require(0 <= address < len(low),
                f"observed-CRC symbol outside capture: {name}")
        return low[address]

    first = byte("rtov_call_context") | (byte("rtov_call_context", 1) << 8)
    second = None
    if link["mode"] == "double":
        second = byte("rtov_call_result") | (byte("rtov_call_result", 1) << 8)
    expected = int(catalog["crc16"])
    outer_fault = byte("rtov_fault")
    island_state = byte("rtov_island_state")
    busy = byte("rtov_busy")
    result_class = classify(first, second, expected)
    require(outer_fault == 20 and island_state == 3 and busy == 0,
            "observed-CRC run did not stop at fail-closed outer E2f")
    value = {
        "format": "lisp65-c2-link34-observed-crc-hardware-result-v1",
        "recorded_on": "2026-07-21",
        "status": "FIRST RED: " + result_class,
        "mode": link["mode"],
        "promotable": False,
        "diagnostic_link": bind(LINK_RECEIPT),
        "boot_manifest": bind(boot_manifest_path),
        "deployment": bind(deployment),
        "captures": {"low": bind(low_path), "boot_family": bind(boot_path)},
        "observed": {
            "first_crc16": f"0x{first:04x}",
            "second_crc16": None if second is None else f"0x{second:04x}",
            "expected_crc16": f"0x{expected:04x}",
            "all_zero_crc16": "0xba75",
            "all_ff_crc16": "0x5aee",
            "classification": result_class,
            "outer_fault": outer_fault,
            "outer_fault_name": "ERR_ISLAND",
            "island_state": island_state,
            "busy": busy,
        },
        "execution_accounting": {
            "diagnostic_hardware_runs": 1,
            "capture_evaluation_replays": 1 if replay else 0,
            "product_presmoke_retries": 0,
            "promotable_product_links": 0,
        },
        "claim_limit": (
            "One owner-authorized non-promotable observed-CRC hardware run. "
            "It is diagnosis only, not a fix, promotion or product acceptance."),
        "next_gate": "stop and return the observed CRC pair for review",
    }
    if replay:
        require(old_result["captures"]["low"] == bind(low_path)
                and old_result["captures"]["boot_family"] == bind(boot_path)
                and old_result["deployment"] == bind(deployment),
                "observed-CRC replay capture identity drift")
        os.chmod(HARDWARE_RESULT, 0o644)
    write(HARDWARE_RESULT, value)
    for path in HARDWARE_OUT.rglob("*"):
        if path.is_file():
            os.chmod(path, 0o444)
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    probe = sub.add_parser("probe")
    probe.add_argument("--mode", choices=tuple(DEFINES), required=True)
    sub.add_parser("link")
    sub.add_parser("check-link")
    sub.add_parser("evaluate-hardware")
    sub.add_parser("replay-hardware")
    sub.add_parser("selftest")
    args = parser.parse_args()
    try:
        if args.action == "probe":
            value = build_probe(args.mode)
        elif args.action == "link":
            value = build_link()
        elif args.action == "check-link":
            value = check_link()
        elif args.action in ("evaluate-hardware", "replay-hardware"):
            value = evaluate_hardware(replay=args.action == "replay-hardware")
        else:
            BASE.configure()
            prerequisites("double")
            value = {"status": "SELFTEST PASS", "matrix": selftest()}
        print("c2-link34-island-observed-crc: " + value["status"])
        return 3 if value["status"].startswith("FIRST RED") else 0
    except (GateError, STATUS.GateError, BASE.LinkError, BASE.PRE.GateError,
            BASE.ISLAND.GateError, RuntimeError, OSError, ValueError, KeyError,
            json.JSONDecodeError, subprocess.SubprocessError) as error:
        print("c2-link34-island-observed-crc: FAIL: " + str(error),
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
