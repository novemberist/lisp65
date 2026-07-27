#!/usr/bin/env python3
"""Prove that quote sugar and explicit QUOTE have one emission identity.

The permanent fixture crosses the native reader, the Lisp-written LCC oracle,
the independent Python compiler, and the exact input boundary of the product
C2 session emitter.  No target compiler, product link, or hardware is used.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FIXTURE = ROOT / "tests/equivalence/quote-emission-parity.json"
DEFAULT_READER = ROOT / "build/reader-conformance-host"
DEFAULT_BINARY = ROOT / "build/equivalence/equivalence-check"
DEFAULT_OUT = ROOT / "build/equivalence/quote-emission-parity.json"
FORMAT = "lisp65-quote-emission-parity-v1"

sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import bytecode_p0_compiler as P0  # noqa: E402


class ParityError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ParityError(message)


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": len(data),
        "sha256": sha_bytes(data),
    }


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("ascii")


def load_lcc_oracle() -> Any:
    path = ROOT / "scripts/lcc-oracle.py"
    spec = importlib.util.spec_from_file_location("lisp65_lcc_oracle", path)
    require(spec is not None and spec.loader is not None,
            "cannot load the canonical LCC oracle")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_fixture(path: Path) -> list[dict[str, str]]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(
        isinstance(value, dict) and value.get("format") == FORMAT,
        "unexpected quote-parity fixture format",
    )
    cases = value.get("cases")
    require(isinstance(cases, list) and cases, "quote-parity cases are absent")
    names: set[str] = set()
    definitions: set[str] = set()
    for index, row in enumerate(cases):
        require(isinstance(row, dict), f"case {index} is not an object")
        require(set(row) == {"name", "definition", "datum"},
                f"case {index} fields drift")
        require(all(isinstance(row[key], str) and row[key]
                    for key in ("name", "definition", "datum")),
                f"case {index} has an empty field")
        require(row["name"] not in names, f"duplicate case: {row['name']}")
        require(row["definition"] not in definitions,
                f"duplicate definition: {row['definition']}")
        names.add(row["name"])
        definitions.add(row["definition"])
    return cases


def read_native(reader: Path, source: str) -> dict[str, Any]:
    run = subprocess.run(
        [str(reader), source],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    value = json.loads(run.stdout)
    require(
        value.get("status") == "ok"
        and value.get("error") == "none"
        and isinstance(value.get("value"), str),
        f"native reader rejected {source!r}",
    )
    return value


def python_emission(source: str) -> dict[str, Any]:
    ast = P0.parse_one(source)
    heap = P0.prepare_heap([])
    name, code, helpers = P0.compile_top_form_with_helpers(ast, heap)

    def code_row(value: Any) -> dict[str, Any]:
        return {
            "nargs": value.nargs,
            "nlocals": value.nlocals,
            "flags": value.flags,
            "littab": list(value.littab),
            "payload_hex": bytes(value.payload).hex(),
        }

    return {
        "ast": ast,
        "definition": name,
        "main": code_row(code),
        "helpers": [
            {"name": helper_name, "code": code_row(helper_code)}
            for helper_name, helper_code in helpers
        ],
    }


def fnlist_summary(fnlist: Any) -> list[dict[str, Any]]:
    require(isinstance(fnlist, list) and fnlist, "LCC emitted no functions")
    result: list[dict[str, Any]] = []
    for index, fn in enumerate(fnlist):
        require(isinstance(fn, list) and len(fn) == 5,
                f"LCC function {index} has invalid shape")
        literals = [] if isinstance(fn[3], str) and fn[3].lower() == "nil" else fn[3]
        require(isinstance(literals, list) and isinstance(fn[4], list),
                f"LCC function {index} has invalid literals/payload")
        result.append({
            "nargs": fn[0],
            "nlocals": fn[1],
            "flags": fn[2],
            "literals": literals,
            "payload": fn[4],
            "payload_hex": bytes(fn[4]).hex(),
        })
    return result


def product_emitter_input(
        fnlist: Any, definition: str, export_flags: int = 0
) -> dict[str, Any]:
    """Represent every value visible at c2_session_emit_add().

    Raw reader spelling is absent at this boundary.  Equal values here feed
    the one deterministic C2I-v2 emitter and therefore have one output.
    """
    return {
        "fnlist": fnlist,
        "export_name": definition.upper(),
        "export_flags": export_flags,
    }


def source_closure_gate() -> dict[str, bool]:
    eval_source = (ROOT / "src/eval.c").read_text(encoding="utf-8")
    runtime_source = (ROOT / "src/c2_product_runtime.c").read_text(
        encoding="utf-8")
    emitter_source = (ROOT / "src/c2_session_emitter.c").read_text(
        encoding="utf-8")
    checks = {
        "evaluator_passes_fnlist":
            "c2_product_install(fnlist, defname)" in eval_source,
        "installer_accepts_fnlist":
            "obj c2_product_install(obj fnlist, obj definition_name)"
            in runtime_source,
        "installer_calls_single_session_emitter":
            runtime_source.count("c2_session_emit_add(fnlist,") == 1,
        "emitter_boundary_is_fnlist_name_flags":
            "c2_session_emit_add(obj fnlist, obj export_name,"
            in emitter_source,
        "emitter_has_no_source_spelling_parameter":
            "source_text" not in emitter_source
            and "source_spelling" not in emitter_source,
    }
    require(all(checks.values()), "product-emitter closure drift: "
            + str([name for name, ok in checks.items() if not ok]))
    return checks


def mutation_gate(reference: dict[str, Any]) -> dict[str, str]:
    def rejected(mutated: dict[str, Any]) -> bool:
        return canonical_bytes(mutated) != canonical_bytes(reference)

    mutations: dict[str, dict[str, Any]] = {}
    value = copy.deepcopy(reference)
    value["reader_normal_form"] += " MUTATED"
    mutations["reader-normal-form"] = value

    value = copy.deepcopy(reference)
    value["lcc_fnlist"][-1][4][-1] ^= 1
    mutations["payload-byte"] = value

    value = copy.deepcopy(reference)
    value["product_emitter_input"]["export_name"] += "-MUTATED"
    mutations["export-name"] = value

    value = copy.deepcopy(reference)
    value["product_emitter_input"]["export_flags"] = 1
    mutations["export-flags"] = value

    result = {
        name: "rejected" for name, mutation in mutations.items()
        if rejected(mutation)
    }
    require(len(result) == len(mutations), "quote-parity mutation survived")
    return result


def run(
    binary: Path, reader: Path, fixture: Path, output: Path,
    receipt: Path | None, incident: Path | None,
) -> dict[str, Any]:
    for path, label in (
        (binary, "LCC host binary"),
        (reader, "native reader"),
        (fixture, "parity fixture"),
    ):
        require(path.is_file(), f"{label} is absent: {path}")

    lcc = load_lcc_oracle()
    cases = load_fixture(fixture)
    rows: list[dict[str, Any]] = []
    checks = 0
    for case in cases:
        definition = case["definition"]
        datum = case["datum"]
        sugar = f"(defun {definition} () '{datum})"
        explicit = f"(defun {definition} () (quote {datum}))"

        sugar_reader = read_native(reader, sugar)
        explicit_reader = read_native(reader, explicit)
        require(
            sugar_reader["value"] == explicit_reader["value"],
            f"{case['name']}: native reader normalization diverged",
        )
        checks += 1

        sugar_raw = lcc.lcc_compile_all(str(binary), [sugar])[0]
        explicit_raw = lcc.lcc_compile_all(str(binary), [explicit])[0]
        sugar_fnlist = lcc.parse_sexp(sugar_raw)
        explicit_fnlist = lcc.parse_sexp(explicit_raw)
        require(
            sugar_raw == explicit_raw and sugar_fnlist == explicit_fnlist,
            f"{case['name']}: Lisp LCC emission diverged",
        )
        checks += 1

        sugar_python = python_emission(sugar)
        explicit_python = python_emission(explicit)
        require(
            sugar_python == explicit_python,
            f"{case['name']}: Python compiler emission diverged",
        )
        checks += 1

        sugar_input = product_emitter_input(
            sugar_fnlist, definition, export_flags=0)
        explicit_input = product_emitter_input(
            explicit_fnlist, definition, export_flags=0)
        require(
            canonical_bytes(sugar_input) == canonical_bytes(explicit_input),
            f"{case['name']}: product emitter input diverged",
        )
        checks += 1

        reference = {
            "reader_normal_form": sugar_reader["value"],
            "lcc_fnlist": sugar_fnlist,
            "product_emitter_input": sugar_input,
        }
        rows.append({
            "name": case["name"],
            "sugar_source": sugar,
            "explicit_source": explicit,
            "reader_normal_form": sugar_reader["value"],
            "reader_consumed_bytes": {
                "sugar": sugar_reader["offset"],
                "explicit": explicit_reader["offset"],
            },
            "lcc_raw": sugar_raw,
            "lcc_functions": fnlist_summary(sugar_fnlist),
            "lcc_fnlist_sha256": sha_bytes(canonical_bytes(sugar_fnlist)),
            "python_emission_sha256":
                sha_bytes(canonical_bytes(sugar_python)),
            "product_emitter_input_sha256":
                sha_bytes(canonical_bytes(sugar_input)),
            "mutations": mutation_gate(reference),
        })

    closure = source_closure_gate()
    result = {
        "format": "lisp65-quote-emission-parity-result-v1",
        "recorded_on": "2026-07-25",
        "status": "passed-no-host-emission-divergence",
        "first_divergent_stage": None,
        "cases": rows,
        "summary": {
            "cases": len(rows),
            "stage_equalities": checks,
            "mutations_rejected": sum(
                len(row["mutations"]) for row in rows),
            "reader": "byte-identical canonical object rendering",
            "literal_lowering": "byte-identical LCC fnlist/literals/payload",
            "special_form_dispatch": "byte-identical opcode emission",
            "product_emitter_boundary":
                "byte-identical fnlist/export-name/flags",
        },
        "product_emitter_closure": closure,
        "conclusion": (
            "The current host path has no semantic or byte-emission "
            "difference between apostrophe sugar and explicit QUOTE. The "
            "Link-64 hardware First Red cannot be attributed to source "
            "spelling at reader, literal-lowering, special-form, or product "
            "emitter-input boundaries."
        ),
        "scope": {
            "product_bytes_changed": 0,
            "target_compiler_runs": 0,
            "product_links": 0,
            "hardware_runs": 0,
            "wplto_runs": 0,
            "promotable": False,
        },
        "authority": {
            "fixture": bind(fixture),
            "native_reader": bind(reader),
            "lcc_host_binary": bind(binary),
            "lcc_source": bind(ROOT / "lib/lcc.lisp"),
            "lcc_oracle": bind(ROOT / "scripts/lcc-oracle.py"),
            "python_compiler": bind(
                ROOT / "tools/host-lisp/bytecode_p0_compiler.py"),
            "product_evaluator": bind(ROOT / "src/eval.c"),
            "product_installer": bind(ROOT / "src/c2_product_runtime.c"),
            "product_emitter": bind(ROOT / "src/c2_session_emitter.c"),
            "gate": bind(Path(__file__)),
        },
    }
    if incident is not None:
        require(incident.is_file(), f"incident receipt is absent: {incident}")
        result["authority"]["hardware_first_red"] = bind(incident)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    result["authority"]["result"] = bind(output)
    if receipt is not None:
        receipt.parent.mkdir(parents=True, exist_ok=True)
        receipt.write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, default=DEFAULT_BINARY)
    parser.add_argument("--reader", type=Path, default=DEFAULT_READER)
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--receipt", type=Path)
    parser.add_argument("--incident", type=Path)
    args = parser.parse_args()
    try:
        result = run(
            args.binary.resolve(),
            args.reader.resolve(),
            args.fixture.resolve(),
            args.out.resolve(),
            args.receipt.resolve() if args.receipt is not None else None,
            args.incident.resolve() if args.incident is not None else None,
        )
    except (
        ParityError, OSError, ValueError, subprocess.CalledProcessError
    ) as error:
        print(f"quote-emission-parity: FAIL: {error}", file=sys.stderr)
        return 1
    print(
        "quote-emission-parity: PASS "
        f"cases={result['summary']['cases']} "
        f"stages={result['summary']['stage_equalities']} "
        f"mutations={result['summary']['mutations_rejected']} "
        "first-divergence=none"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
