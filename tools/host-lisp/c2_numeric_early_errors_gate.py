#!/usr/bin/env python3
"""Contract, mutation and linked gates for numeric-only early C2 errors."""

from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
from elf_truth import ElfTruth  # noqa: E402


FEATURE = "LISP65_C2_NUMERIC_EARLY_ERRORS"
CONTRACT = ROOT / "config/c2-append-final-hybrid-contract.json"
SOURCE = ROOT / "src/interrupt.c"
FIXTURE = ROOT / "scripts/error-state-main.c"
TOOLCHAIN = ROOT / "tools/llvm-mos/bin"
EARLY_SENTENCES = (
    b"E2e catalog missing; redeploy",
    b"E2f runtime island invalid; redeploy",
    b"E3d runtime transport timeout; reboot",
    b"E3e runtime family staging failed; redeploy",
)


class GateError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise GateError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"evidence absent: {path}")
    return {"path": path.relative_to(ROOT).as_posix(),
            "bytes": path.stat().st_size, "sha256": sha(path)}


def validate_source(source: str, contract: dict[str, Any]) -> None:
    selection = contract["selection"]
    require(selection["selected_candidate"] == "numeric-early-errors"
            and selection["selected_attributed_text_bytes"] == 81
            and selection["product_source_changes_authorized"] == 1,
            "numeric early-error scope cut is not owner-selected")
    require(source.count("#ifndef LISP65_C2_NUMERIC_EARLY_ERRORS") == 2
            and source.count(
                "static uint8_t error_render_resident(lisp65_error_code code)") == 1
            and source.count("if (error_render_resident(code)) return 1;") == 1,
            "early prose is not guarded at both definition and call")
    require(all(sentence.decode("ascii") in source
                for sentence in EARLY_SENTENCES)
            and source.count("if (lisp65_error_render_code(code, pending_symbol)) return 1;") == 1
            and source.count("emit('E');") == 1
            and source.count("emit(error_hex_digit") == 2,
            "numeric/overlay fallback or preserved legacy prose source drift")


def source_gate() -> dict[str, Any]:
    source = SOURCE.read_text(encoding="utf-8")
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    validate_source(source, contract)
    mutations: dict[str, tuple[str, dict[str, Any]]] = {}
    mutations["definition_guard_removed"] = (
        source.replace("#ifndef LISP65_C2_NUMERIC_EARLY_ERRORS", "#if 1", 1),
        contract)
    mutations["call_guard_removed"] = (
        source.replace("#ifndef LISP65_C2_NUMERIC_EARLY_ERRORS", "#if 1", 2),
        contract)
    mutations["numeric_prefix_removed"] = (
        source.replace("    emit('E');", "    /* mutation */", 1), contract)
    wrong = copy.deepcopy(contract)
    wrong["selection"]["selected_candidate"] = "visible-block-cursor"
    mutations["wrong_owner_selection"] = (source, wrong)
    rejected = []
    for name, (changed_source, changed_contract) in mutations.items():
        try:
            validate_source(changed_source, changed_contract)
        except (GateError, KeyError, TypeError, ValueError):
            rejected.append(name)
        else:
            raise GateError(f"numeric early-error mutation accepted: {name}")
    return {
        "status": "passed-owner-selected-numeric-early-error-source-contract",
        "feature": FEATURE,
        "selected_attributed_text_bytes": 81,
        "preserved": ["overlay renderer", "stable Ehh fallback",
                      "inner status identity", "fail-closed control flow"],
        "mutations_rejected": rejected,
        "contract": bind(CONTRACT), "source": bind(SOURCE),
        "fixture": bind(FIXTURE),
    }


def host_gate(out: Path) -> dict[str, Any]:
    out = out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    binary = out / "numeric-early-errors-host"
    command = [
        "cc", "-std=c99", "-Wall", "-Wextra", "-Werror",
        "-fsanitize=address,undefined", "-DLISP65_RUNTIME_OVERLAY",
        "-DLISP65_NUMERIC_ERRORS", f"-D{FEATURE}", "-Isrc",
        str(FIXTURE), str(SOURCE), "-o", str(binary)]
    subprocess.run(command, cwd=ROOT, check=True)
    run = subprocess.run(
        [str(binary)], cwd=ROOT, text=True, capture_output=True,
        env={**os.environ, "ASAN_OPTIONS": "detect_leaks=1",
             "UBSAN_OPTIONS": "halt_on_error=1"})
    require(run.returncode == 0
            and "error-state: PASS" in run.stdout,
            "numeric early-error host fixture red")
    stdout = out / "numeric-early-errors-host.stdout.txt"
    stdout.write_text(run.stdout, encoding="utf-8")
    return {
        "status": "passed-overlay-then-numeric-fallback-host-fixture",
        "output_for_runtime_catalog": "E2e",
        "asan": "passed", "ubsan": "passed",
        "binary": bind(binary), "stdout": bind(stdout),
    }


def linked_gate(elf: Path) -> dict[str, Any]:
    truth = ElfTruth.read(elf, llvm_readobj=TOOLCHAIN / "llvm-readobj")
    symbol = truth.symbol("lisp65_error_render_pending")
    data = elf.read_bytes()
    require(symbol.bytes > 0 and symbol.section.startswith(".text")
            and not any(sentence in data for sentence in EARLY_SENTENCES),
            "linked product retained resident early-error prose")
    return {
        "status": "passed-linked-numeric-only-early-errors",
        "renderer": {"section": symbol.section, "address": symbol.value,
                     "bytes": symbol.bytes},
        "resident_sentences_present": 0,
        "stable_numeric_codes": ["E2e", "E2f", "E3d", "E3e"],
    }


def main() -> int:
    try:
        print(json.dumps(source_gate(), indent=2, sort_keys=True))
        return 0
    except (GateError, OSError, ValueError) as error:
        print(f"c2-numeric-early-errors-gate: FAIL: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
