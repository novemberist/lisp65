#!/usr/bin/env python3
"""Run the dialect-v2 System/Runtime primitive differential."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import bytecode_p0 as P0  # noqa: E402
import bytecode_p0_compiler as P0C  # noqa: E402


FIXTURE = ROOT / "tests/bytecode/dialect-v2/system-runtime/cases.json"
V1_BINARY = ROOT / "build/equivalence/frozen-v1-f6527d25/equivalence-check"
V2_BINARY = ROOT / "build/equivalence/dialect-v2-equivalence-check"
V1_ROOT = ROOT / "build/equivalence/frozen-v1-f6527d25/source"
V1_BUILD = ROOT / "build/equivalence/frozen-v1-f6527d25/build-receipt.json"
V2_BUILD = ROOT / "build/equivalence/dialect-v2-build-receipt.json"
OUTPUT = ROOT / "build/bytecode/dialect-v2/system-runtime"
PROFILES = ("dialect-v1", "dialect-v2")
ENGINES = (
    "native-c-treewalk", "native-c-compiler-vm",
    "python-p0-compiler-vm", "lisp-lcc",
)
MODES = {
    "native-c-treewalk": "tree",
    "native-c-compiler-vm": "vm",
    "lisp-lcc": "lcc",
}


class SystemRuntimeError(RuntimeError):
    pass


def load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise SystemRuntimeError(f"cannot load {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise SystemRuntimeError(f"{path}: root is not an object")
    return value


def digest_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def digest(path: Path) -> str:
    return digest_bytes(path.read_bytes())


def validate(value: dict[str, Any]) -> list[dict[str, Any]]:
    if value.get("format") != "lisp65-dialect-v2-system-runtime-cases-v1" or value.get("family") != "system-runtime":
        raise SystemRuntimeError("fixture identity drift")
    cases = value.get("cases")
    if not isinstance(cases, list) or not cases:
        raise SystemRuntimeError("fixture has no cases")
    ids = []
    for case in cases:
        if not isinstance(case, dict) or set(case) != {"id", "forms", "decision", "observations"}:
            raise SystemRuntimeError("case shape drift")
        ids.append(case["id"])
        if case["decision"] not in {"key-event-blocking-semantics", "set-public-semantics"}:
            raise SystemRuntimeError(f"{case['id']}: decision drift")
        if not isinstance(case["forms"], list) or not case["forms"]:
            raise SystemRuntimeError(f"{case['id']}: empty forms")
        for profile in PROFILES:
            if set(case["observations"].get(profile, {})) != set(ENGINES):
                raise SystemRuntimeError(f"{case['id']}/{profile}: engine coverage drift")
    if ids != sorted(set(ids)):
        raise SystemRuntimeError("case ids are not sorted and unique")
    return cases


def normalize_p0(exc: P0.VMError) -> str:
    if exc.status == "ArityError":
        return "!error:arity"
    if exc.status == "DirMiss":
        return "!error:undefined-public-name"
    return "!error:runtime"


def run_p0(profile: str, case: dict[str, Any], index: int) -> str:
    if profile == "dialect-v1":
        return "!error:undefined-public-name"
    ledger = load(ROOT / "config/bytecode-abi-ledger.json")
    heap = P0.Heap()
    directory: dict[int, P0.CodeObject] = {}
    result = P0.NIL
    for form_index, source in enumerate(case["forms"]):
        parsed = P0C.parse_one(source)
        name = f"%system-runtime-{index}-{form_index}"
        top = ["defun", name, [], parsed]
        compiled_name, code, helpers = P0C.compile_top_form_with_helpers(
            top, heap, strict_arity=True
        )
        for helper_name, helper in helpers:
            directory[heap.intern(helper_name)] = helper
        directory[heap.intern(compiled_name)] = code
        vm = P0.P0VM(heap=heap, directory=directory, abi_profile="dialect-v2", abi_ledger=ledger)
        try:
            result = vm.run(code, [])
        except P0.VMError as exc:
            return normalize_p0(exc)
    return heap.obj_to_text(result)


def run_native(profile: str, engine: str, case: dict[str, Any], temp: Path) -> str:
    binary = V1_BINARY if profile == "dialect-v1" else V2_BINARY
    if not binary.is_file():
        raise SystemRuntimeError(f"missing binary: {binary}")
    forms = temp / f"{profile}-{engine}-{case['id']}.lisp"
    forms.write_text("\n".join(case["forms"]) + "\n", encoding="utf-8")
    command = [str(binary), MODES[engine], str(forms)]
    if engine == "lisp-lcc":
        preload = temp / f"{profile}-lcc-preload.lisp"
        if not preload.exists():
            root = V1_ROOT if profile == "dialect-v1" else ROOT
            parts = [(root / "lib/lcc.lisp").read_text(encoding="utf-8")]
            if profile == "dialect-v2":
                parts.append((ROOT / "lib/dialect-v2/lcc-profile.lisp").read_text(encoding="utf-8"))
            preload.write_text("\n".join(parts) + "\n", encoding="utf-8")
        command += ["--preload", str(preload)]
    process = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=30)
    if process.returncode:
        raise SystemRuntimeError(f"{profile}/{engine}/{case['id']}: {process.stderr.strip()}")
    observed = [line.rsplit(" => ", 1)[1].strip() for line in process.stdout.splitlines() if " => " in line]
    if len(observed) != len(case["forms"]):
        raise SystemRuntimeError(f"{profile}/{engine}/{case['id']}: observation count drift")
    return observed[-1]


def provenance(profile: str, engine: str, preload: bytes) -> dict[str, Any]:
    if engine == "python-p0-compiler-vm":
        inputs = [
            "config/bytecode-abi-ledger.json",
            "tools/host-lisp/bytecode_p0.py",
            "tools/host-lisp/bytecode_p0_compiler.py",
        ]
        binding = "".join(f"{path}:{digest(ROOT / path)}\n" for path in inputs)
        engine_sha = digest_bytes(binding.encode("ascii"))
        return {
            "source_commit": (
                "f6527d25e2035eae5a98dae7431d641515e2fd2e"
                if profile == "dialect-v1" else None
            ),
            "binary_sha256": engine_sha,
            "build_profile_sha256": digest_bytes(
                f"{profile}:{engine}:{engine_sha}".encode("ascii")
            ),
            "preload_sha256": digest_bytes(preload),
        }
    build = load(V1_BUILD if profile == "dialect-v1" else V2_BUILD)
    return {
        "source_commit": build["source_commit"],
        "binary_sha256": build["binary_sha256"],
        "build_profile_sha256": build["build_profile_sha256"],
        "preload_sha256": digest_bytes(preload),
    }


def run(engines: tuple[str, ...]) -> int:
    cases = validate(load(FIXTURE))
    fixture_sha = digest(FIXTURE)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    failed = 0
    with tempfile.TemporaryDirectory(prefix="system-runtime-") as temp_name:
        temp = Path(temp_name)
        for profile in PROFILES:
            for engine in engines:
                verdict_cases = []
                preload_parts: list[bytes] = []
                if engine == "lisp-lcc":
                    root = V1_ROOT if profile == "dialect-v1" else ROOT
                    preload_parts.append((root / "lib/lcc.lisp").read_bytes())
                    if profile == "dialect-v2":
                        preload_parts.append(
                            (ROOT / "lib/dialect-v2/lcc-profile.lisp").read_bytes()
                        )
                for index, case in enumerate(cases):
                    observed = run_p0(profile, case, index) if engine == "python-p0-compiler-vm" else run_native(profile, engine, case, temp)
                    expected = case["observations"][profile][engine]
                    accepted = observed == expected
                    failed += int(not accepted)
                    verdict_cases.append({
                        "id": case["id"],
                        "decision": f"decision:{case['decision']}",
                        "verdict": "accept" if accepted else "reject",
                        "result_sha256": digest_bytes(observed.encode("utf-8")),
                    })
                    print(f"{profile}/{engine}/{case['id']}: {'PASS' if accepted else 'FAIL'} observed={observed} expected={expected}")
                verdict = {
                    "format": "lisp65-dialect-v2-family-verdict-v1",
                    "family": "system-runtime", "profile": profile, "engine": engine,
                    "fixture_sha256": fixture_sha,
                    "provenance": provenance(profile, engine, b"\0".join(preload_parts)),
                    "cases": verdict_cases,
                }
                (OUTPUT / f"{profile}-{engine}-verdict.json").write_text(
                    json.dumps(verdict, indent=2, sort_keys=True) + "\n", encoding="utf-8"
                )
    print(f"dialect-v2-system-runtime: {'PASS' if not failed else 'FAIL'} cases={len(cases)} runs={len(cases)*len(PROFILES)*len(engines)} failed={failed}")
    return 0 if not failed else 1


def main() -> int:
    global FIXTURE
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("check",))
    parser.add_argument("--fixture", type=Path, default=FIXTURE)
    parser.add_argument("--engine", choices=ENGINES)
    args = parser.parse_args()
    FIXTURE = args.fixture
    engines = (args.engine,) if args.engine else ENGINES
    return run(engines)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, subprocess.SubprocessError, SystemRuntimeError) as exc:
        print(f"dialect-v2-system-runtime: FAIL {exc}", file=sys.stderr)
        raise SystemExit(1)
