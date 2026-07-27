#!/usr/bin/env python3
"""Close matrix row F3 with exact-capacity append-seam fixtures."""

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
import c2_append_phase_plan_gate as APPEND_GATE  # noqa: E402


MATRIX = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-cross-invariant-full-matrix-link57-review-receipt.json")
STRUCTURAL = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-product-link57-keymap-nullary-fast-path2-structural-receipt.json")
PRODUCT_DIR = ROOT / (
    "build/c2.2/substitution/product-link-57-keymap-nullary-fast-path2")
PRODUCT = PRODUCT_DIR / "lisp65-c2-substitution-linked.prg"
ELF = PRODUCT_DIR / "lisp65-c2-substitution-linked.prg.elf"
PROFILE = ROOT / "config/workbench.mk"
SYMBOL = ROOT / "src/symbol.c"
RUNTIME = ROOT / "src/c2_product_runtime.c"
ERROR_CODES = ROOT / "src/error_codes.h"
ERROR_TEXTS = ROOT / "config/error-texts.json"
HARNESS = ROOT / "scripts/c2-f3-symbol-exhaustion-main.c"
OUT = ROOT / "build/c2.2/matrix-f3-symbol-exhaustion"
BINARY = OUT / "c2-f3-symbol-exhaustion-host"
CASES = OUT / "cases.json"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-link57-matrix-f3-symbol-exhaustion-fixture-receipt.json")

EXPECTED = {
    MATRIX: "62b5c3cdffa71861f48de6e6619ee40b7ea94ba144ae2653d77a39603e24e8f8",
    STRUCTURAL: "6632a7d00ea3bfaef294924ea618e0af70e34b75da929de05b2e7c451ce26059",
    PRODUCT: "7d568ceb7edab95a237ff3079fcf689768373a9ea48a5a43f355f6275ddc5df8",
    ELF: "306ba2aca61bbd2b924f3b52fd03fbbd9db95330f9c81e1190329abc147bf950",
}
MAX_SYM = 752
NAMEPOOL = 10208
TOO_MANY_SYMBOLS = 34


class GateError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise GateError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def write_bound(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        require(path.read_bytes() == data,
                f"refusing to overwrite divergent artifact: {path}")
    else:
        path.write_bytes(data)
    os.chmod(path, 0o444)


def function_body(source: str, name: str, *, last: bool = False) -> str:
    matches = list(re.finditer(r"\b" + re.escape(name) + r"\s*\(", source))
    for match in reversed(matches) if last else matches:
        brace = source.find("{", match.end())
        semicolon = source.find(";", match.end())
        if brace < 0 or (0 <= semicolon < brace):
            continue
        depth = 0
        for end in range(brace, len(source)):
            if source[end] == "{":
                depth += 1
            elif source[end] == "}":
                depth -= 1
                if depth == 0:
                    return source[match.start():end + 1]
    raise GateError(f"function body absent: {name}")


def _source_errors(symbol: str, runtime: str) -> list[str]:
    errors: list[str] = []
    allocator = function_body(symbol, "new_symbol")
    name_value = function_body(runtime, "c2_stream_name_value")
    resolve = function_body(
        runtime, "c2_append_publish_plan_resolve_phase")
    append_at = runtime.rfind(
        "static C2_KERNAL_RESIDENT uint8_t c2_append_begin(")
    append_end = runtime.find(
        "\nstatic uint8_t c2_append_rollback(", append_at)
    append = runtime[append_at:append_end]
    required_allocator = (
        "nsym >= MAX_SYM",
        "(uint16_t)(len + 1) > (uint16_t)(NAMEPOOL - npool)",
        "lisp_abort_static(LISP65_ERR_TOO_MANY_SYMBOLS",
        "return NIL;",
        "sympool_write(off, name, (uint16_t)(len + 1))",
    )
    for token in required_allocator:
        if token not in allocator:
            errors.append("allocator:" + token)
    if all(token in allocator for token in required_allocator):
        write_at = allocator.index("sympool_write(")
        if (allocator.index("nsym >= MAX_SYM") > write_at
                or allocator.index("NAMEPOOL - npool") > write_at
                or allocator.index("LISP65_ERR_TOO_MANY_SYMBOLS") > write_at):
            errors.append("allocator-check-after-write")
    if ("kind != 3u && kind != 5u && kind != 8u" not in name_value
            or "c2_facade_intern(sym_name_scratch)" not in name_value
            or "*value != (uint16_t)NIL && !mem_oom" not in name_value):
        errors.append("name-value-real-intern-seam")
    if ("c2_stream_name_value(8u, at + 2u, length, &symbol)"
            not in resolve):
        errors.append("persistent-publish-name-cutpoint")
    if (append_at < 0 or append_end <= append_at
            or "c2_decode_from(&c2aw.append, 4u)" not in append
            or "c2_append_run_persistent_publish_plan(&c2aw)" not in append
            or "v5_fail:" not in append
            or "c2_append_run_rollback_plan(&c2aw)" not in append):
        errors.append("append-name-failure-to-one-rollback-plan")
    return errors


def source_gate() -> dict[str, Any]:
    symbol = SYMBOL.read_text(encoding="utf-8")
    runtime = RUNTIME.read_text(encoding="utf-8")
    require(not _source_errors(symbol, runtime),
            "F3 product source seam drift: "
            f"{_source_errors(symbol, runtime)}")
    mutations = {
        "symbol-capacity-check-removed": (
            symbol.replace("|| nsym >= MAX_SYM", "|| 0", 1), runtime),
        "namepool-capacity-check-removed": (
            symbol.replace(
                "|| (uint16_t)(len + 1) > (uint16_t)(NAMEPOOL - npool)",
                "|| 0", 1), runtime),
        "wrong-error-identity": (
            symbol.replace("LISP65_ERR_TOO_MANY_SYMBOLS",
                           "LISP65_ERR_VM_OOM", 1), runtime),
        "publish-name-bypasses-real-intern": (
            symbol, runtime.replace(
                "c2_facade_intern(sym_name_scratch)",
                "(obj)MK_SYMI(0)", 1)),
    }
    rejected: dict[str, str] = {}
    for label, (mutated_symbol, mutated_runtime) in mutations.items():
        require(_source_errors(mutated_symbol, mutated_runtime),
                f"F3 source mutation survived: {label}")
        rejected[label] = "rejected"
    return {
        "status": "passed-real-allocator-to-append-rollback-seam",
        "capacity_checks_before_first_copy": True,
        "error_identity": "LISP65_ERR_TOO_MANY_SYMBOLS",
        "persistent_cutpoint":
            "c2_append_publish_plan_resolve_phase/name-kind-8",
        "transient_cutpoint":
            "c2_decode_from/name-resolution while C2J active",
        "failure_route": "one c2_append_run_rollback_plan",
        "mutations": rejected,
    }


def compile_and_run() -> tuple[list[dict[str, Any]], list[str]]:
    OUT.mkdir(parents=True, exist_ok=True)
    command = [
        "cc", "-std=c11", "-O1", "-Wall", "-Wextra", "-Werror",
        "-ffunction-sections", "-fdata-sections",
        "-fsanitize=address,undefined", "-fno-omit-frame-pointer",
        f"-DMAX_SYM={MAX_SYM}", f"-DNAMEPOOL={NAMEPOOL}",
        "-DLISP65_NUMERIC_ERRORS", "-DLISP65_NAMEOFF_EXT",
        "-DLISP65_SYMVAL_EXT", "-DLISP65_SYMFN_EXT",
        "-DLISP65_SYMPOOL_EXT", "-Isrc",
        str(HARNESS.relative_to(ROOT)), str(SYMBOL.relative_to(ROOT)),
        "-Wl,--gc-sections", "-o", str(BINARY.relative_to(ROOT)),
    ]
    built = subprocess.run(
        command, cwd=ROOT, text=True, capture_output=True, check=False)
    require(built.returncode == 0,
            "F3 host compile red: " + built.stdout + built.stderr)
    results: list[dict[str, Any]] = []
    env = dict(os.environ)
    env["ASAN_OPTIONS"] = "detect_leaks=0"
    env["UBSAN_OPTIONS"] = "halt_on_error=1"
    for resource in ("symbol-slots", "name-pool"):
        for append in ("persistent", "transient"):
            ran = subprocess.run(
                [str(BINARY), resource, append], cwd=ROOT, env=env,
                text=True, capture_output=True, check=False)
            require(ran.returncode == 0,
                    f"F3 case red {resource}/{append}: "
                    + ran.stdout + ran.stderr)
            try:
                value = json.loads(ran.stdout)
            except json.JSONDecodeError as exc:
                raise GateError(
                    f"F3 case emitted invalid JSON {resource}/{append}: "
                    f"{ran.stdout}") from exc
            require(value["resource"] == resource
                    and value["append"] == append,
                    "F3 case identity drift")
            require(value["error_code"] == TOO_MANY_SYMBOLS
                    and value["symbols_before"] == value["symbols_after"]
                    and value["pool_before"] == value["pool_after"],
                    "F3 allocator failure is not exact")
            require(value["c2d_byte_identical"]
                    and value["c2j_byte_identical"]
                    and value["export_cells_byte_identical"],
                    "F3 append rollback is not byte-identical")
            if resource == "symbol-slots":
                require(value["symbols_before"] == MAX_SYM
                        and value["pool_before"] < NAMEPOOL,
                        "symbol-slot fixture also exhausted name pool")
            else:
                require(value["pool_before"] == NAMEPOOL
                        and value["symbols_before"] < MAX_SYM,
                        "name-pool fixture also exhausted symbol slots")
            results.append(value)
    require(len(results) == 4, "F3 four-case matrix incomplete")
    write_bound(CASES, canonical(results))
    return results, command


def build_receipt() -> dict[str, Any]:
    for path, expected in EXPECTED.items():
        require(path.is_file() and sha(path) == expected,
                f"immutable Link-57 input drift: {path}")
    profile = PROFILE.read_text(encoding="utf-8")
    require("-DNAMEPOOL=10208" in profile and "-DMAX_SYM=752" in profile,
            "product symbol-capacity authority drift")
    errors = json.loads(ERROR_TEXTS.read_text(encoding="utf-8"))
    error = next(row for row in errors["entries"]
                 if row["id"] == "too-many-symbols")
    require(error["code"] == TOO_MANY_SYMBOLS
            and error["c_name"] == "LISP65_ERR_TOO_MANY_SYMBOLS",
            "TOO_MANY_SYMBOLS error authority drift")
    matrix = json.loads(MATRIX.read_text(encoding="utf-8"))
    f3 = next(row for row in matrix["rows"] if row["id"] == "F3")
    require(f3["status"] == "OPEN"
            and f3["disposition"]["kind"] == "fixture",
            "accepted F3 disposition drift")

    cases, command = compile_and_run()
    source = source_gate()
    append_source = APPEND_GATE.source_gate()
    linked = APPEND_GATE.linked_gate(ELF)
    require(append_source["status"] == "passed-append-cutpoint-contract"
            and linked["status"] == "passed-linked-cutpoint-citizenship",
            "permanent append rollback gate red")
    plan = linked["plan_data"][
        "lisp65_c2_append_persistent_publish_plan"]["bytes"]
    require(plan == [37, 38, 39, 40, 0],
            "Link-57 persistent name/publish plan drift")

    return {
        "format": "lisp65-c2.2-matrix-f3-symbol-exhaustion-fixture-v1",
        "recorded_on": "2026-07-23",
        "status": "passed-four-append-seam-resource-exhaustion-cases",
        "row": "F3",
        "disposition_result": "PROVEN",
        "authorities": {
            "accepted_matrix_review": bind(MATRIX),
            "link57_structural_receipt": bind(STRUCTURAL),
            "link57_product": bind(PRODUCT),
            "link57_elf": bind(ELF),
            "product_profile": bind(PROFILE),
            "symbol_allocator": bind(SYMBOL),
            "append_runtime": bind(RUNTIME),
            "error_codes": bind(ERROR_CODES),
            "error_texts": bind(ERROR_TEXTS),
            "fixture_source": bind(HARNESS),
        },
        "physical_capacities": {
            "symbol_slots": MAX_SYM,
            "name_pool_bytes": NAMEPOOL,
            "independence": {
                "slot_case_pool_bytes_used": 4512,
                "pool_case_symbol_slots_used": 638,
            },
        },
        "product_dataflow": source,
        "permanent_append_gate": {
            "source_status": append_source["status"],
            "linked_status": linked["status"],
            "persistent_plan_bytes": plan,
            "resolve_slot": 38,
            "rollback_plan":
                append_source["phase_plan"]["rollback_plan"],
        },
        "cases": cases,
        "host_fixture": {
            "binary": bind(BINARY),
            "case_artifact": bind(CASES),
            "compiler_command": command,
            "sanitizers": ["ASAN", "UBSAN"],
        },
        "execution": {
            "host_fixture_builds": 1,
            "host_fixture_runs": 4,
            "product_compiler_runs": 0,
            "product_links": 0,
            "product_bytes_changed": 0,
            "hardware_runs": 0,
            "capacity_effect_bytes": 0,
        },
        "claim_limit": (
            "Closes F3 for the exact Link-57 source/artifact identity by "
            "composing the real exact-capacity symbol allocator, four "
            "ASAN/UBSAN append-seam fixtures, and the permanent linked append "
            "rollback gate. It does not close another matrix row, start the "
            "acceptance chain, promote a product or make a hardware claim."),
        "value_string": (
            "F3=PROVEN link57=exact cases=4/4 "
            "symbol-slots=752@pool4512 name-pool=10208@symbols638 "
            "error=TOO_MANY_SYMBOLS c2d=c2j=exports=byte-identical "
            "product-delta=0 hardware=0 acceptance=blocked"),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("write", "check"))
    args = parser.parse_args()
    try:
        value = build_receipt()
        data = canonical(value)
        if args.action == "write":
            if RECEIPT.exists():
                require(RECEIPT.read_bytes() == data,
                        "refusing to overwrite divergent F3 receipt")
            else:
                RECEIPT.write_bytes(data)
            os.chmod(RECEIPT, 0o444)
            verb = "WROTE"
        else:
            require(RECEIPT.is_file() and RECEIPT.read_bytes() == data,
                    "F3 receipt absent or drifted")
            verb = "CHECK PASS"
        print(
            "c2-matrix-f3-symbol-exhaustion: "
            f"{verb} cases=4/4 error=34 c2d=c2j=exports=exact "
            "product-delta=0")
        return 0
    except (GateError, APPEND_GATE.GateError, OSError, KeyError, ValueError,
            json.JSONDecodeError, subprocess.SubprocessError) as exc:
        print(
            "c2-matrix-f3-symbol-exhaustion: FAIL " + str(exc),
            file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
