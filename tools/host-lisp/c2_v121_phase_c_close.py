#!/usr/bin/env python3
"""Close the autonomous v1.2.1 Phase-C housekeeping rows."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
PLAN = ROOT / "docs/planning/v1.2.1-release-plan.md"
RUNNER_DOC = ROOT / "docs/planning/c2-product-session-host-runner.md"
UPSTREAM = ROOT / "docs/upstream-owner-bundle-2026-07-27.md"
VM = ROOT / "src/vm.c"
MAKEFILE = ROOT / "Makefile"
INDEX = ROOT / "config/document-index.json"
DIRMISS_TOOL = ROOT / (
    "tools/host-lisp/c2_v121_dirmiss_renderer_attribution.py")
DIRMISS_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-v1.2.1-dirmiss-renderer-attribution-receipt.json")
IRQ_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-interrupt-ownership-source-gate-receipt.json")
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-v1.2.1-phase-c-closure-receipt.json")
LOG_ROOT = ROOT / "build/c2.2/v1.2.1/phase-c"

FORMAT = "lisp65-v1.2.1-phase-c-closure-v1"
REPAIR_COMMIT = "3585ae60788d8cfa4299f3056d5ff7d49b234aca"


class ClosureError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ClosureError(message)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"missing file: {path}")
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"missing JSON: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def run(args: list[str], name: str) -> str:
    result = subprocess.run(
        args, cwd=ROOT, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, check=False)
    LOG_ROOT.mkdir(parents=True, exist_ok=True)
    (LOG_ROOT / f"{name}.log").write_text(result.stdout, encoding="utf-8")
    require(result.returncode == 0, f"{name} failed:\n{result.stdout[-5000:]}")
    return result.stdout


def validate_vm_guard(vm_text: str) -> None:
    require(
        "#if defined(LISP65_INTERN_SESSION_SERVICE) || \\\n"
        "    defined(LISP65_V2_NATIVE_STRING_CODECS)\n"
        "/* Prim 0 and Prim 68 share one resident string-domain truth."
        in vm_text
        and vm_text.count("uint8_t vm_string_arg_p(obj value)") == 1,
        "vm_string_arg_p is not visible in both required profiles")


def validate_native_execution(output: str) -> None:
    require(
        "-DLISP65_V2_NATIVE_STRING_CODECS" in output,
        "native-codec profile was not compiled")
    require(
        "v2-native-function-registry: PASS active=63 public=40 "
        "restricted=39 cases=211 engines=4 evaluations=844" in output,
        "registry execution witness absent")
    require(
        "v2-native-function-matrix: PASS entries=40 routes=3 "
        "engines=4 evaluations=844" in output,
        "native matrix execution witness absent")


def validate_l11(upstream_text: str, irq: dict[str, Any]) -> None:
    require(
        "## L11 — Audio-DMA interrupt documentation contradicts "
        "tested-core RTL" in upstream_text
        and "03b24c6b9d0e456f762fdca0d2dd66ec3c3e1fc6" in upstream_text
        and "lines 4533–4553" in upstream_text,
        "paste-ready upstream L11 evidence drift")
    binding = irq.get("documentation", {}).get("upstream_L11", {})
    require(
        irq.get("status") == "passed-strict-internal-interrupt-ownership"
        and binding.get("path") == UPSTREAM.relative_to(ROOT).as_posix()
        and binding.get("sha256") == sha256(UPSTREAM),
        "interrupt-ownership receipt does not bind current L11")


def mutation_checks(vm_text: str, native_output: str,
                    upstream_text: str, irq: dict[str, Any]) -> dict[str, Any]:
    checks = [
        (
            "codec-guard-removed",
            lambda: validate_vm_guard(vm_text.replace(
                " || \\\n    defined(LISP65_V2_NATIVE_STRING_CODECS)", ""))),
        (
            "matrix-zero-executions",
            lambda: validate_native_execution(native_output.replace(
                "engines=4 evaluations=844",
                "engines=4 evaluations=0"))),
        (
            "native-codec-compile-flag-removed",
            lambda: validate_native_execution(native_output.replace(
                "-DLISP65_V2_NATIVE_STRING_CODECS", ""))),
        (
            "L11-heading-removed",
            lambda: validate_l11(upstream_text.replace(
                "## L11 — Audio-DMA interrupt documentation contradicts "
                "tested-core RTL", "## L11 removed"), irq)),
        (
            "L11-receipt-hash-drift",
            lambda: validate_l11(
                upstream_text,
                {
                    **irq,
                    "documentation": {
                        **irq.get("documentation", {}),
                        "upstream_L11": {
                            **irq.get("documentation", {}).get(
                                "upstream_L11", {}),
                            "sha256": "0" * 64,
                        },
                    },
                })),
    ]
    rejected: list[str] = []
    for name, check in checks:
        try:
            check()
        except ClosureError:
            rejected.append(name)
    require(
        len(rejected) == len(checks),
        "Phase-C mutation escaped: "
        + ", ".join(name for name, _ in checks if name not in rejected))
    return {
        "attempted": len(checks),
        "rejected": len(rejected),
        "names": rejected,
    }


def collect(run_gates: bool) -> dict[str, Any]:
    dirmiss_output = ""
    native_output = ""
    index_output = ""
    if run_gates:
        dirmiss_output = run(
            [sys.executable, str(DIRMISS_TOOL), "--check"],
            "dirmiss-attribution")
        native_output = run(
            ["make", "-B", "v2-native-function-matrix-check"],
            "v2-native-function-matrix")
        index_output = run(["make", "document-index-check"], "document-index")
    else:
        # Verification remains execution-bearing: a buildable but unexecuted
        # harness is the exact class this closure is meant to prevent.
        dirmiss_output = run(
            [sys.executable, str(DIRMISS_TOOL), "--check"],
            "dirmiss-attribution")
        native_output = run(
            ["make", "-B", "v2-native-function-matrix-check"],
            "v2-native-function-matrix")
        index_output = run(["make", "document-index-check"], "document-index")

    vm_text = VM.read_text(encoding="utf-8")
    upstream_text = UPSTREAM.read_text(encoding="utf-8")
    irq = load(IRQ_RECEIPT)
    dirmiss = load(DIRMISS_RECEIPT)
    index = load(INDEX)

    validate_vm_guard(vm_text)
    validate_native_execution(native_output)
    validate_l11(upstream_text, irq)
    require(
        "c2-v1.2.1-dirmiss-attribution: VERIFY PASS" in dirmiss_output
        and dirmiss.get("status")
        == "passed-renderer-pointer-abi-overwrite-attributed",
        "DIRMISS attribution execution witness absent")
    documents = index.get("documents")
    require(
        isinstance(documents, list) and len(documents) == 226
        and "document-index: PASS documents=226" in index_output,
        "document-index Phase-C closure drift")

    commit = run(
        ["git", "show", "-s", "--format=%H", REPAIR_COMMIT],
        "repair-commit").strip()
    require(commit == REPAIR_COMMIT, "vm_string_arg_p repair commit missing")
    mutations = mutation_checks(
        vm_text, native_output, upstream_text, irq)

    return {
        "format": FORMAT,
        "status": "passed-autonomous-phase-c-closed",
        "scope": "paper-host-housekeeping-no-product-delta",
        "rows": {
            "C1_dirmiss": {
                "status": "closed-attributed-fix-parked-v1.2.2",
                "mechanism": (
                    "L65E overwrites symname pointer return in "
                    "__rc2/__rc3 with incidental A/X"),
                "receipt": bind(DIRMISS_RECEIPT),
                "hardware_followup": "none",
            },
            "C2_upstream_L11": {
                "status": "owner-paste-ready-no-upstream-action-taken",
                "tested_core": (
                    "03b24c6b9d0e456f762fdca0d2dd66ec3c3e1fc6"),
                "bundle": bind(UPSTREAM),
                "source_gate": bind(IRQ_RECEIPT),
            },
            "C3_vm_string_arg_p": {
                "status": "closed-compiled-and-executed",
                "repair_commit": REPAIR_COMMIT,
                "profile": (
                    "LISP65_V2_NATIVE_STRING_CODECS without "
                    "LISP65_INTERN_SESSION_SERVICE"),
                "entries": 40,
                "routes": 3,
                "engines": 4,
                "evaluations": 844,
                "source": bind(VM),
                "runner_document": bind(RUNNER_DOC),
            },
            "C3_document_index": {
                "status": "passed-complete-tracked-inventory",
                "documents": 226,
                "index": bind(INDEX),
            },
        },
        "mutations": mutations,
        "authority": {
            "release_plan": bind(PLAN),
            "verifier": bind(Path(__file__)),
            "makefile": bind(MAKEFILE),
        },
        "claim_limit": (
            "Phase-C host/paper closure only. No product byte, acceptance "
            "artifact, promotion, tag, public push or release claim is "
            "created or changed."),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("write", "verify"))
    args = parser.parse_args()
    try:
        value = collect(run_gates=True)
        encoded = json.dumps(
            value, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
        if args.action == "write":
            RECEIPT.parent.mkdir(parents=True, exist_ok=True)
            RECEIPT.write_text(encoded, encoding="utf-8")
            print(
                "c2-v1.2.1-phase-c: PASS C1=attributed C2=L11-ready "
                "C3=844-executions documents=226 mutations=5/5")
        else:
            require(RECEIPT.is_file(), f"missing receipt: {RECEIPT}")
            require(
                RECEIPT.read_text(encoding="utf-8") == encoded,
                "tracked Phase-C receipt drift")
            print(
                "c2-v1.2.1-phase-c: VERIFY PASS "
                "rows=4 mutations=5/5")
        return 0
    except (ClosureError, OSError, UnicodeError, json.JSONDecodeError,
            ValueError) as error:
        print(f"c2-v1.2.1-phase-c: FIRST RED: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
