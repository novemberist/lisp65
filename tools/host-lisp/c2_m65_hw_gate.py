#!/usr/bin/env python3
"""Permanent source/artifact gate for the v1.4 synchronous MEGA65 pilot."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "config/c2-m65-hw-contract.json"
REGISTERS = ROOT / "lib/m65-hw-registers.lisp"
SOURCE = ROOT / "lib/m65-hw.lisp"
SUITE = ROOT / "tests/bytecode/libs/p0-stdlib-m65-hw-base.json"
BASE_SUITE = ROOT / "tests/bytecode/libs/p0-stdlib-ship-input-wait-base.json"
BUILD = ROOT / "build/post-promotion/v14/m65-hw/host-first"
PREFIX = BUILD / "m65-hw"
BASE_PREFIX = BUILD / "base"
OBSERVATIONS = BUILD / "observations.json"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.4-m65-hw-host-first-receipt.json"
)
PUBLIC = [
    "m65-byte-read", "m65-byte-write", "m65-bit-set", "m65-bit-clear",
    "m65-bit-test", "m65-word-read", "m65-word-write", "m65-draw-plot",
    "m65-draw-line", "m65-draw-fill", "m65-sprite-enable",
    "m65-sprite-position", "m65-sprite-shape", "m65-sprite-color",
    "m65-sid-voice",
]
CASES = {
    "m65-byte-and-bit-access", "m65-word-page-carry",
    "m65-word-ffff-rejected", "m65-draw-plot",
    "m65-draw-line-inclusive", "m65-draw-fill-inclusive",
    "m65-draw-bounds-before-write", "m65-sprite-position-enable-color",
    "m65-sprite-shape-and-live-pointer",
    "m65-sprite-atomic-session-composition",
    "m65-sprite-shape-length-rejected", "m65-sid-voice-snapshot",
    "m65-sid-volume-rejected",
}


class GateError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise GateError(message)


def load(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"authority absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    return {
        "path": path.resolve().relative_to(ROOT.resolve()).as_posix(),
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def atomic_json(path: Path, value: dict[str, Any]) -> None:
    payload = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(payload)
    temporary.replace(path)


def validate(
    contract: dict[str, Any], registers: str, source: str, suite: dict[str, Any]
) -> dict[str, Any]:
    require(
        contract["format"] == "lisp65-c2-m65-hw-synchronous-pilot-v1"
        and list(contract["public_surface"]) == PUBLIC,
        "m65-hw public contract drift",
    )
    placement = contract["placement"]
    require(
        placement["admission_budget_bytes"] == 2048
        and placement["code"] == "Bank-2 library freight"
        and all(placement[key] == 0 for key in (
            "resident_code_bytes", "resident_state_bytes",
            "new_resident_gc_roots", "runtime_overlay_records",
            "native_primitives",
        ))
        and placement["require_dependency"] is False,
        "m65-hw placement drift",
    )
    require(
        contract["drawing"]["surface"].startswith("the current character-cell")
        and "$2000" in contract["drawing"]["bitmap_exclusion"]
        and contract["sprite"]["shape_slot"] == "0x17c0-0x17ff"
        and contract["sprite"]["shape_pointer"] == 95
        and "private-inlined" in contract["sprite"]["vic_unlock_rule"]
        and contract["sid"]["write_order"][-1] == "control",
        "m65-hw synchronous scope drift",
    )
    require(
        suite["extends"] == "p0-stdlib-ship-input-wait-base.json"
        and suite["sources"] == [
            "lib/m65-hw-registers.lisp", "lib/m65-hw.lisp"
        ]
        and set(row["name"] for row in suite["cases"]) == CASES
        and len(suite["cases"]) == len(CASES)
        and suite["min_private_inline_functions"] == 28
        and len(suite["private_inline_functions"]) == 28
        and "%m65-vic-open" in suite["private_inline_functions"],
        "m65-hw executable suite drift",
    )
    require(
        registers.count("(defun %m65-") == 23
        and "defmacro" not in registers,
        "generated inline register authority drift",
    )
    for name in PUBLIC:
        require(f"(defun {name} " in source or f"(defun {name}\n" in source,
                f"m65-hw public definition absent: {name}")
    require(
        "(require " not in source
        and "8192" not in source
        and "edma" not in source.lower()
        and "(%m65-vic-open)" in source
        and "(= (string-length shape) 63)" in source
        and "buffer" not in source.lower()
        and "(<= table-low 248)" in source
        and "(+ base 4) control" in source,
        "m65-hw implementation boundary drift",
    )
    case = {row["name"]: row for row in suite["cases"]}
    require(
        case["m65-word-ffff-rejected"]["expect_io_exact"]
            == {"memory_read": 0, "memory_write": 0}
        and case["m65-draw-bounds-before-write"]["expect_io_exact"]
            == {"screen_put_char": 0}
        and case["m65-sid-voice-snapshot"]["expect_memory_write_trace"][-1]
            == [0xD40B, 17],
        "m65-hw fail-before-I/O or SID-order witness drift",
    )
    return {
        "status": "passed-synchronous-scope-source-contract",
        "public_names": len(PUBLIC),
        "cases": len(CASES),
        "generated_inline_constants": 23,
    }


def run_suite(suite: Path, prefix: Path, observations: Path | None = None) -> subprocess.CompletedProcess[str]:
    prefix.parent.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable, "tools/host-lisp/bytecode_p0_stdlib.py", "--check",
        "--emit-artifacts", str(prefix.relative_to(ROOT)),
    ]
    if observations is not None:
        command += ["--observation-report", str(observations.relative_to(ROOT))]
    command.append(str(suite.relative_to(ROOT)))
    return subprocess.run(
        command, cwd=ROOT, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, check=False,
    )


def artifact_gate(contract: dict[str, Any]) -> dict[str, Any]:
    baseline_result = run_suite(BASE_SUITE, BASE_PREFIX)
    require(
        baseline_result.returncode == 0,
        "m65-hw baseline lane red:\n" + baseline_result.stdout,
    )
    result = run_suite(SUITE, PREFIX, OBSERVATIONS)
    require(result.returncode == 0, "m65-hw source/artifact lane red:\n" + result.stdout)
    require(
        "bytecode-p0-stdlib-check: PASS" in result.stdout
        and "bytecode-p0-stdlib-embed-check: PASS" in result.stdout,
        "m65-hw execution lane witness absent",
    )
    manifest = load(PREFIX.with_suffix(".manifest.json"))
    baseline = load(BASE_PREFIX.with_suffix(".manifest.json"))
    code_bytes = int(manifest["code_bytes"]) - int(baseline["code_bytes"])
    object_delta = int(manifest["objects"]) - int(baseline["objects"])
    require(
        code_bytes <= contract["placement"]["admission_budget_bytes"]
        and object_delta == 30
        and manifest["cost"]["private_inline_gate"]["functions"] == 28
        and not (set(manifest["private_inline_functions"])
                 & set(manifest["functions"]))
        and set(PUBLIC) <= set(manifest["functions"]),
        "m65-hw emitted placement/identity drift",
    )
    all_rows = load(OBSERVATIONS)["suites"][0]["observations"]
    rows = [row for row in all_rows if row["name"] in CASES]
    require(
        len(rows) == len(CASES)
        and {row["name"] for row in rows} == CASES
        and sum(row.get("io_witness", {}).get("memory_write", 0) for row in rows) >= 86
        and sum(row.get("io_witness", {}).get("screen_put_char", 0) for row in rows) >= 11,
        "m65-hw positive execution witness drift",
    )
    return {
        "status": "passed-source-and-emitted-artifact",
        "code_bytes": code_bytes,
        "budget_bytes": contract["placement"]["admission_budget_bytes"],
        "headroom_bytes": contract["placement"]["admission_budget_bytes"] - code_bytes,
        "objects": object_delta,
        "cases_executed_per_lane": len(rows),
        "lanes": 2,
        "memory_writes_observed": sum(
            row.get("io_witness", {}).get("memory_write", 0) for row in rows
        ),
        "screen_writes_observed": sum(
            row.get("io_witness", {}).get("screen_put_char", 0) for row in rows
        ),
    }


def mutation_suite(label: str, suite: dict[str, Any], *, source: str, registers: str) -> bool:
    directory = BUILD / "mutations" / label
    directory.mkdir(parents=True, exist_ok=True)
    source_path = directory / "m65-hw.lisp"
    registers_path = directory / "m65-hw-registers.lisp"
    source_path.write_text(source, encoding="utf-8")
    registers_path.write_text(registers, encoding="utf-8")
    changed = copy.deepcopy(suite)
    changed["extends"] = str(BASE_SUITE)
    changed["sources"] = [
        registers_path.relative_to(ROOT).as_posix(),
        source_path.relative_to(ROOT).as_posix(),
    ]
    suite_path = directory / "suite.json"
    atomic_json(suite_path, changed)
    result = run_suite(suite_path, directory / "artifact")
    return result.returncode != 0


def mutations(
    contract: dict[str, Any], registers: str, source: str, suite: dict[str, Any]
) -> dict[str, str]:
    rejected: dict[str, str] = {}

    def source_mutation(label: str, old: str, new: str) -> None:
        require(old in source, f"mutation anchor absent: {label}")
        require(
            mutation_suite(label, suite, source=source.replace(old, new, 1),
                           registers=registers),
            f"mutation survived: {label}",
        )
        rejected[label] = "rejected-by-executed-source-or-artifact-lane"

    changed_registers = registers.replace(
        "(defun %m65-reg-vic-sprite-xy-base-hi () 208)",
        "(defun %m65-reg-vic-sprite-xy-base-hi () 209)", 1,
    )
    require(
        mutation_suite("wrong-register", suite, source=source,
                       registers=changed_registers),
        "wrong register mutation survived",
    )
    rejected["wrong-register"] = "rejected-by-I/O-trace"
    source_mutation("word-no-page-carry", "(if (= low 255) (+ high 1) high)",
                    "(if (= low 255) high high)")
    source_mutation("draw-admits-edge", "(< x columns)", "(<= x columns)")
    source_mutation("sprite-x-msb-inverted", "(if (> x 255)", "(if (< x 255)")
    source_mutation("sprite-padding-nonzero", "shape-slot-hi) 255 0)",
                    "shape-slot-hi) 255 1)")
    old = """(m65-byte-write (%m65-reg-sid-volume-hi)\n                          (%m65-reg-sid-volume-lo) volume)\n          (m65-byte-write (%m65-reg-sid-voice-base-hi) (+ base 4) control)"""
    new = """(m65-byte-write (%m65-reg-sid-voice-base-hi) (+ base 4) control)\n          (m65-byte-write (%m65-reg-sid-volume-hi)\n                          (%m65-reg-sid-volume-lo) volume)"""
    source_mutation("sid-control-not-last", old, new)

    static_rows: list[tuple[str, dict[str, Any], dict[str, Any]]] = []
    changed = copy.deepcopy(contract)
    changed["placement"]["resident_code_bytes"] = 1
    static_rows.append(("resident-byte", changed, suite))
    changed = copy.deepcopy(contract)
    changed["placement"]["require_dependency"] = True
    static_rows.append(("require-dependency", changed, suite))
    changed_suite = copy.deepcopy(suite)
    changed_suite["cases"] = changed_suite["cases"][:-1]
    static_rows.append(("case-built-not-run", contract, changed_suite))
    changed_suite = copy.deepcopy(suite)
    changed_suite["private_inline_functions"].remove("%m65-vic-open")
    changed_suite["min_private_inline_functions"] = 27
    static_rows.append(("vic-open-tailcall-restored", contract, changed_suite))
    for label, changed_contract, changed_suite in static_rows:
        try:
            validate(changed_contract, registers, source, changed_suite)
        except GateError:
            rejected[label] = "rejected-by-static-contract"
        else:
            raise GateError(f"mutation survived: {label}")
    return rejected


def main() -> int:
    try:
        contract = load(CONTRACT)
        registers = REGISTERS.read_text(encoding="utf-8")
        source = SOURCE.read_text(encoding="utf-8")
        suite = load(SUITE)
        generator = subprocess.run(
            [sys.executable, "tools/host-lisp/c2_m65_hw_registers.py", "--check"],
            cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            check=False,
        )
        require(generator.returncode == 0, generator.stdout.strip())
        source_gate = validate(contract, registers, source, suite)
        artifact = artifact_gate(contract)
        rejected = mutations(contract, registers, source, suite)
        receipt = {
            "format": "lisp65-c2-v14-m65-hw-host-first-receipt-v1",
            "status": "passed",
            "source_contract": source_gate,
            "artifact": artifact,
            "mutations": {
                "count": len(rejected), "expected": len(rejected),
                "rejected": rejected,
            },
            "inputs": {
                "contract": bind(CONTRACT), "registers": bind(REGISTERS),
                "source": bind(SOURCE), "suite": bind(SUITE),
                "base_suite": bind(BASE_SUITE),
                "generator": bind(ROOT / "tools/host-lisp/c2_m65_hw_registers.py"),
                "vm": bind(ROOT / "tools/host-lisp/bytecode_p0.py"),
                "runner": bind(ROOT / "tools/host-lisp/bytecode_p0_stdlib.py"),
            },
            "claim_limit": contract["claim_limit"],
        }
        atomic_json(RECEIPT, receipt)
        print(
            "c2-m65-hw: PASS public=%d cases=%dx2 mutations=%d "
            "bank2=%d/%d headroom=%d resident=+0"
            % (
                len(PUBLIC), artifact["cases_executed_per_lane"], len(rejected),
                artifact["code_bytes"], artifact["budget_bytes"],
                artifact["headroom_bytes"],
            )
        )
        return 0
    except (GateError, KeyError, ValueError, OSError) as exc:
        print(f"c2-m65-hw: FIRST RED: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
