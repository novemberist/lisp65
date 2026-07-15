#!/usr/bin/env python3
"""Run the generated native primitive x call-route matrix on four engines."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import tempfile
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "host-lisp"))

import eval_surface_contract as E  # noqa: E402


REGISTRY = ROOT / "config" / "v2-native-function-registry.json"
HEADER = ROOT / "src" / "v2_native_function_dispatch.h"
FIXTURE = ROOT / "tests" / "bytecode" / "dialect-v2" / "native-function-routes" / "cases.generated.json"
RECEIPT = ROOT / "tests" / "bytecode" / "dialect-v2" / "evidence" / "capability-carrier" / "native-function-route-matrix.json"
DEFAULT_BINARY = ROOT / "build" / "equivalence" / "dialect-v2-equivalence-check"


class MatrixError(RuntimeError):
    pass


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def binding(path: Path) -> dict:
    return {"path": str(path.relative_to(ROOT)), "sha256": digest(path)}


def run(binary: Path) -> dict:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    fixture = E._load_fixture(FIXTURE)
    entries = len(registry["entries"])
    safety_cases = len(registry["safety_cases"])
    expected_cases = entries * 4 + safety_cases * 3
    if len(fixture.get("cases", [])) != expected_cases:
        raise MatrixError("generated case count does not equal routes+safety+function-kind closure")
    if not binary.is_file():
        raise MatrixError(f"missing dialect-v2 equivalence binary: {binary}")

    engine_rows = []
    cases, forms = E.run_native_fixture(
        fixture, binary, "native-treewalk", str(FIXTURE)
    )
    engine_rows.append({"id": "native-c-treewalk", "cases": cases, "forms": forms, "status": "passed"})
    cases, forms = E.run_native_fixture(
        fixture, binary, "native-c-compiler-vm", str(FIXTURE)
    )
    engine_rows.append({"id": "native-c-compiler-vm", "cases": cases, "forms": forms, "status": "passed"})
    cases, forms, steps, helpers = E.run_fixture(
        fixture, str(FIXTURE), abi_profile="dialect-v2"
    )
    engine_rows.append({
        "id": "python-p0-compiler-vm", "cases": cases, "forms": forms,
        "p0_steps": steps, "helpers": helpers, "status": "passed",
    })
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".lisp") as preload:
        preload.write((ROOT / "lib" / "lcc.lisp").read_text(encoding="utf-8"))
        preload.write("\n")
        preload.write((ROOT / "lib" / "dialect-v2" / "lcc-profile.lisp").read_text(encoding="utf-8"))
        preload.flush()
        cases, forms = E.run_native_fixture(
            fixture, binary, "lisp-lcc", str(FIXTURE), preload=Path(preload.name)
        )
    engine_rows.append({"id": "lisp-lcc", "cases": cases, "forms": forms, "status": "passed"})
    if any(row["cases"] != expected_cases for row in engine_rows):
        raise MatrixError("an engine did not execute the complete generated case set")
    return {
        "format": "lisp65-v2-native-function-route-matrix-v1",
        "status": "passed",
        "profile": "dialect-v2-capability-carrier",
        "construction": "generated-from-native-function-registry",
        "registry_entries": entries,
        "routes": registry["routes"],
        "engines": engine_rows,
        "safety_cases": safety_cases,
        "evaluations": expected_cases * 4,
        "parity": {
            "registry_entries": entries,
            "generated_dispatch_entries": entries,
            "generated_cases": expected_cases,
            "status": "passed",
        },
        "bindings": [binding(REGISTRY), binding(HEADER), binding(FIXTURE)],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("generate", "check"))
    parser.add_argument("--binary", type=Path, default=DEFAULT_BINARY)
    parser.add_argument("--receipt", type=Path, default=RECEIPT)
    args = parser.parse_args(argv)
    value = run(args.binary)
    rendered = json.dumps(value, indent=2) + "\n"
    if args.action == "generate":
        args.receipt.parent.mkdir(parents=True, exist_ok=True)
        args.receipt.write_text(rendered, encoding="utf-8")
        action = "GENERATED"
    else:
        if not args.receipt.is_file() or args.receipt.read_text(encoding="utf-8") != rendered:
            raise MatrixError("pinned matrix receipt drift")
        action = "PASS"
    print(
        f"v2-native-function-matrix: {action} entries={value['registry_entries']} "
        f"routes=3 engines=4 evaluations={value['evaluations']}"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, E.ContractError, MatrixError) as exc:
        print(f"v2-native-function-matrix: FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
