#!/usr/bin/env python3
"""Build and bind the host-only closure of Link-95 packed callees."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_packed_symbolic_callee_closure as PACKED  # noqa: E402
import c2_ship_input_wait_gate as INPUT  # noqa: E402
import c2_substitution_artifacts as SUB  # noqa: E402
import c2_top_level_macro_redispatch as REDISPATCH  # noqa: E402


FORMAT = "lisp65-c2.3-link95-packed-callee-closure-v1"
COMMISSION = "b06383262d88f03a9a21f9b01590e83e11413195"
BASE = ROOT / "build/c2.3/top-level-macro-publication-link95-preflight"
BASE_SUITE = BASE / "link95-stdlib-suite.json"
BASE_PRODUCT = BASE / "static-plane/narrow-static/product/substitution-artifacts.json"
OUT = ROOT / "build/c2.3/link95-packed-callee-closure"
CODEMOD = OUT / "codemod"
SUITE = OUT / "link95-closed-stdlib-suite.json"
STDLIB_PREFIX = OUT / "static-plane/narrow-static/stdlib-p0"
OBSERVATIONS = OUT / "stdlib-observations.json"
PRODUCT_DIR = OUT / "static-plane/narrow-static/product"
PRODUCT = PRODUCT_DIR / "substitution-artifacts.json"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-link95-packed-symbolic-callee-closure-receipt.json"
)
FIRST_RED = PACKED.FIRST_RED


class ClosureRoundError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ClosureRoundError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"authority absent: {path}")
    return {
        "path": path.resolve().relative_to(ROOT.resolve()).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def run(command: list[str], label: str) -> str:
    result = subprocess.run(
        command, cwd=ROOT, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, check=False,
    )
    require(result.returncode == 0, f"{label} red:\n{result.stdout}")
    return result.stdout.strip()


def candidate_suite() -> dict[str, Any]:
    suite = load(BASE_SUITE)
    old_prefix = BASE.relative_to(ROOT).as_posix() + "/codemod/"
    new_prefix = CODEMOD.relative_to(ROOT).as_posix() + "/"
    sources = suite.get("sources")
    require(isinstance(sources, list), "Link-95 suite source inventory absent")
    rewritten: list[str] = []
    for source in sources:
        require(isinstance(source, str), "Link-95 suite source is not a path")
        if source.startswith(old_prefix):
            rewritten.append(new_prefix + source[len(old_prefix):])
        elif source == "lib/stdlib-time.lisp":
            rewritten.append(
                (OUT / "sources/lib/stdlib-time.lisp")
                .relative_to(ROOT).as_posix()
            )
        else:
            rewritten.append(source)
    suite["sources"] = rewritten
    functions = suite.get("functions")
    require(isinstance(functions, list)
            and functions.count("%time-delta") == 1
            and "%time-error-duration-overflow" not in functions,
            "Link-95 time function inventory drift")
    functions.insert(
        functions.index("%time-delta") + 1,
        "%time-error-duration-overflow",
    )
    changed = 0
    for row in suite.get("cases", []):
        if row.get("name") in {"time-delta-overflow", "wait-overflow-rejected"}:
            require(row.get("expect_vm_error") == "DirMiss",
                    f"historical overflow oracle drift: {row}")
            row["expect_vm_error"] = "TypeError"
            changed += 1
    require(changed == 2, "overflow oracle cardinality drift")
    return suite


def prepare_sources() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    output = run([
        sys.executable, "tools/host-lisp/v2_workbench_codemod.py",
        "--out", CODEMOD.relative_to(ROOT).as_posix(),
    ], "isolated Link-95 closure codemod")
    require("v2-workbench-codemod: PASS" in output,
            "isolated Link-95 codemod witness absent")
    contract = load(REDISPATCH.CONTRACT)
    runtime = CODEMOD / "sources/lib/dialect-v2/eval-runtime.lisp"
    runtime.write_text(REDISPATCH.candidate_runtime(contract), encoding="utf-8")
    fasl = CODEMOD / "sources/lib/lcc-fasl.lisp"
    fasl_source = fasl.read_text(encoding="utf-8")
    old_carrier = "      (%c1-compile-form first)"
    new_carrier = "      (%c2-compile-form first)"
    require(fasl_source.count(old_carrier) == 1
            and new_carrier not in fasl_source,
            "product compiler-carrier publication boundary drift")
    fasl.write_text(fasl_source.replace(old_carrier, new_carrier, 1),
                    encoding="utf-8")
    time = OUT / "sources/lib/stdlib-time.lisp"
    time.parent.mkdir(parents=True)
    shutil.copyfile(ROOT / "lib/stdlib-time.lisp", time)
    SUITE.write_bytes(canonical(candidate_suite()))


def product_specs(stdlib: Path) -> tuple[tuple[str, str, Path], ...]:
    return (
        ("stdlib-p0", "stdlib", stdlib),
        ("ide", "ide", BASE / "authorities/ide.manifest.json"),
        ("idex", "idex", ROOT / (
            "build/c2.2/substitution/published-nullary-call-bytecode-artifacts/"
            "libs/idex.manifest.json")),
        ("m65d", "m65d", ROOT / (
            "build/c2.2/substitution/published-nullary-call-bytecode-artifacts/"
            "libs/m65d.manifest.json")),
        ("buffer", "buffer", BASE / "authorities/buffer.manifest.json"),
        ("lcc", "lcc", ROOT / "build/post-promotion/v112/compiler/lcc.manifest.json"),
    )


def restore_bound_authorities() -> None:
    """Materialize the Link-95 IDE/buffer snapshots at manifest-owned paths."""
    target = ROOT / "build/bytecode/dialect-v2/libs"
    target.mkdir(parents=True, exist_ok=True)
    for stem, count in (("ide", 8), ("buffer", 7)):
        sources = sorted((BASE / "authorities").glob(f"{stem}.*"))
        require(len(sources) == count,
                f"Link-95 {stem} authority snapshot is incomplete")
        for source in sources:
            shutil.copyfile(source, target / source.name)
        require(sha(target / f"{stem}.manifest.json")
                == sha(BASE / f"authorities/{stem}.manifest.json"),
                f"Link-95 {stem} authority restore drift")


def build_product() -> tuple[dict[str, Any], tuple[tuple[str, str, Path], ...]]:
    prepare_sources()
    stdlib = INPUT.run_suite(SUITE, STDLIB_PREFIX, OBSERVATIONS)
    stdlib_manifest = STDLIB_PREFIX.with_suffix(".manifest.json")
    require(stdlib == load(stdlib_manifest), "stdlib runner result drift")
    specs = product_specs(stdlib_manifest)
    require(all(path.is_file() for _key, _name, path in specs),
            "six-image candidate inventory incomplete")
    restore_bound_authorities()
    old = (SUB.BUILD, SUB.SPECS)
    try:
        SUB.BUILD = PRODUCT_DIR
        SUB.SPECS = specs
        product = SUB.build()
    finally:
        SUB.BUILD, SUB.SPECS = old
    require(product == load(PRODUCT), "packed product result drift")
    return product, specs


def stripped(value: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(value)
    result.pop("call_sites", None)
    return result


def native_opcode_sites(caller: str, mnemonic: str) -> list[dict[str, Any]]:
    image = PACKED._packed_image(PRODUCT.parent, "stdlib-p0")
    entries = [row for row in image["entries"] if row["name"] == caller]
    require(len(entries) == 1, f"packed native caller absent: {caller}")
    entry = entries[0]
    code = PACKED.B.decode_code_object(
        image["code"][entry["offset"]:entry["offset"] + entry["length"]]
    )
    ledger = PACKED.C._abi_ledger("dialect-v2", None)
    rows: list[dict[str, Any]] = []
    pc = 0
    while pc < len(code.payload):
        here = pc
        op, _operand, pc = PACKED.B.decode_instruction(
            code.payload, pc, profile_id="dialect-v2", abi_ledger=ledger,
        )
        if op.mnemonic == mnemonic:
            rows.append({
                "image": "stdlib-p0", "caller": caller, "pc": here,
                "opcode": mnemonic, "argc": 1, "literal": None,
                "packed_literal_kind": None, "target": "consp",
                "classification": "native",
            })
    return rows


def closed_sites(before: dict[str, Any], after: dict[str, Any]) -> list[dict[str, Any]]:
    old = before["failures"]
    require(len(old) == 8, "commissioned eight-site First Red drift")
    rows = after["call_sites"]
    litnode_consp = native_opcode_sites("%fasl-litnode", "CONSP")
    form_consp = native_opcode_sites("%fasl-form", "CONSP")
    require(len(litnode_consp) == 1 and len(form_consp) == 2,
            "FASL native CONSP lowering cardinality drift")
    native = [
        ("fasl-litnode-consp", litnode_consp[0]),
        ("fasl-form-defun-consp", form_consp[0]),
        ("fasl-form-defmacro-consp", form_consp[1]),
    ]
    expected = (
        ("fasl-form-defun-compiler", "%fasl-form", "%c1-compile", 3,
         "published-cell", 1),
        ("fasl-form-defmacro-compiler", "%fasl-form", "%c1-compile", 3,
         "published-cell", 2),
        ("c1-compile-carrier", "%c1-compile", "%c2-compile-form", 1,
         "published-cell", 1),
        ("time-overflow-helper", "%time-delta", "%time-error-duration-overflow",
         0, "published-cell", 1),
        ("wait-overflow-helper", "wait", "%time-error-duration-overflow",
         0, "published-cell", 1),
    )
    result: list[dict[str, Any]] = []
    for site_id, native_row in native:
        row = deepcopy(native_row)
        row["id"] = site_id
        result.append(row)
    seen: dict[tuple[str, str, int, str], int] = {}
    for site_id, caller, target, argc, classification, occurrence in expected:
        matches = sorted(
            (row for row in rows
             if row["image"] == "stdlib-p0"
             and row["caller"] == caller and row["target"] == target
             and row["argc"] == argc and row["classification"] == classification),
            key=lambda row: row["pc"],
        )
        key = (caller, target, argc, classification)
        require(len(matches) >= occurrence,
                f"closed packed site absent: {site_id}: {matches}")
        row = deepcopy(matches[occurrence - 1])
        require(key not in seen or occurrence == seen[key] + 1,
                f"packed site occurrence order drift: {site_id}")
        seen[key] = occurrence
        row["id"] = site_id
        result.append(row)
    require(len(result) == 8, "closed site cardinality drift")
    return result


def per_site_mutations(rows: list[dict[str, Any]]) -> list[str]:
    rejected: list[str] = []
    for row in rows:
        candidate = deepcopy(row)
        candidate["classification"] = "anonymous-only"
        try:
            PACKED.require_closed({"failures": [candidate]})
        except PACKED.ClosureError:
            rejected.append(row["id"])
    require(len(rejected) == 8, "per-site packed closure mutation survived")
    return rejected


def build_receipt() -> dict[str, Any]:
    product, specs = build_product()
    before = PACKED.inventory(BASE_PRODUCT, include_rows=True)
    after = PACKED.inventory(PRODUCT, include_rows=True)
    PACKED.require_closed(after)
    rows = closed_sites(before, after)
    static_bytes = sum(int(load(path)["code_bytes"]) for _key, _name, path in specs)
    baseline_specs = product_specs(
        BASE / "static-plane/narrow-static/stdlib-p0.manifest.json")
    baseline_static = sum(
        int(load(path)["code_bytes"]) for _key, _name, path in baseline_specs)
    require(static_bytes < 65536 and static_bytes - baseline_static <= 256,
            "Link-95 closure Bank-2 price exceeds the commissioned wall")
    return {
        "format": FORMAT,
        "recorded_on": "2026-08-09",
        "status": "HOST-GREEN; EIGHT-LEGACY-PACKED-CALLEES-CLOSED",
        "commission": COMMISSION,
        "rule": "every packed symbolic callee is published, native, or direct",
        "authorities": {
            "commission": {
                "commit": COMMISSION,
                "path": "docs/planning/post-v1.4.0-direction-plan.md",
            },
            "first_red": bind(FIRST_RED),
            "candidate_suite": bind(SUITE),
            "candidate_stdlib": bind(STDLIB_PREFIX.with_suffix(".manifest.json")),
            "candidate_product": bind(PRODUCT),
            "candidate_sources": {
                "eval_runtime": bind(CODEMOD / "sources/lib/dialect-v2/eval-runtime.lisp"),
                "fasl": bind(CODEMOD / "sources/lib/lcc-fasl.lisp"),
                "time": bind(OUT / "sources/lib/stdlib-time.lisp"),
            },
            "driver": bind(Path(__file__)),
            "packed_gate": bind(Path(PACKED.__file__)),
        },
        "before": stripped(before),
        "after": stripped(after),
        "closed_sites": rows,
        "per_site_mutations_rejected": per_site_mutations(rows),
        "class_mutations_rejected": PACKED.mutation_tests(),
        "price": {
            "baseline_bank2_static_code_bytes": baseline_static,
            "candidate_bank2_static_code_bytes": static_bytes,
            "bank2_delta_bytes": static_bytes - baseline_static,
            "candidate_bank2_headroom_bytes": 65536 - static_bytes,
            "resident_delta_bytes": 0,
            "entries_delta": int(product["entries"])
                - int(load(BASE_PRODUCT)["entries"]),
            "resolutions_delta": int(product["resolutions"])
                - int(load(BASE_PRODUCT)["resolutions"]),
            "roots_delta": int(product["roots"])
                - int(load(BASE_PRODUCT)["roots"]),
        },
        "attempt_accounting": {
            "product_cards_authorized": 1,
            "product_cards_consumed": 0,
            "product_links": 0,
            "device_contacts": 0,
        },
        "next_gate": "the single commissioned Link-95 product card",
        "claim_limit": "Host packed-product closure and Bank-2 price only.",
    }


def validate_receipt(value: dict[str, Any]) -> None:
    require(value.get("format") == FORMAT
            and value.get("status")
                == "HOST-GREEN; EIGHT-LEGACY-PACKED-CALLEES-CLOSED"
            and value.get("commission") == COMMISSION,
            "Link-95 closure receipt identity drift")
    require(value.get("per_site_mutations_rejected")
            == [row["id"] for row in value.get("closed_sites", [])]
            and len(value.get("closed_sites", [])) == 8,
            "Link-95 per-site closure witness drift")
    current = PACKED.inventory(PRODUCT)
    PACKED.require_closed(current)
    require(value["after"] == current,
            "Link-95 packed closure artifact drift")
    require(value["authorities"]["first_red"] == bind(FIRST_RED)
            and value["authorities"]["candidate_suite"] == bind(SUITE)
            and value["authorities"]["candidate_stdlib"]
                == bind(STDLIB_PREFIX.with_suffix(".manifest.json"))
            and value["authorities"]["candidate_product"] == bind(PRODUCT)
            and all(
                isinstance(value["authorities"].get(name), dict)
                and isinstance(value["authorities"][name].get("path"), str)
                and isinstance(value["authorities"][name].get("bytes"), int)
                and isinstance(value["authorities"][name].get("sha256"), str)
                and len(value["authorities"][name]["sha256"]) == 64
                for name in ("driver", "packed_gate")
            ),
            "Link-95 closure authority drift")
    require(value["price"]["resident_delta_bytes"] == 0
            and value["attempt_accounting"]["product_cards_consumed"] == 0,
            "Link-95 closure exceeded its host-only boundary")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("build", "check", "selftest"))
    action = parser.parse_args().action
    try:
        if action == "build":
            value = build_receipt()
            RECEIPT.parent.mkdir(parents=True, exist_ok=True)
            RECEIPT.write_bytes(canonical(value))
        elif action == "check":
            value = load(RECEIPT)
            validate_receipt(value)
        else:
            require(len(PACKED.mutation_tests()) == 3,
                    "packed class mutation wall drift")
            value = {"status": "passed", "class_mutations": 3}
    except (ClosureRoundError, PACKED.ClosureError, OSError, ValueError,
            KeyError, json.JSONDecodeError) as error:
        print(f"c2-link95-packed-callee-closure: FAIL: {error}", file=sys.stderr)
        return 1
    print(json.dumps(value, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
