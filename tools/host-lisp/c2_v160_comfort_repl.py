#!/usr/bin/env python3
"""Permanent host gate for the v1.6 Comfort REPL shelf library."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import bytecode_p0_stdlib as P  # noqa: E402
import c2_v160_comfort_repl_symbol_pricing as PRICING  # noqa: E402
import evidence_era as ERA  # noqa: E402
import v11_l_lite_keymap as KEYMAP  # noqa: E402


CONTRACT = ROOT / "config/c2-v160-comfort-repl-implementation-contract.json"
COMFORT = ROOT / "lib/repl-comfort.lisp"
SCANNER = ROOT / "lib/sexp-depth.lisp"
IDE_SYNTAX = ROOT / "lib/ide-syntax.lisp"
READ_LINE = ROOT / "lib/stdlib-read-line.lisp"
NATIVE_REPL = ROOT / "src/repl.c"
KEYMAP_CONTRACT = ROOT / "config/v11-l-lite-keymap.json"
CORE_SUITE = ROOT / "tests/bytecode/libs/p0-stdlib-ship-input-wait-base.json"
IDE_SUITE = ROOT / "tests/bytecode/libs/p0-ide-lib.json"
COMFORT_SUITE = ROOT / "tests/bytecode/libs/p0-repl-comfort.json"
RESIDENT_SUITE = ROOT / "config/c2-v160-comfort-repl-resident-suite.json"
PRICING_MANIFEST = ROOT / (
    "build/c2.3/v1.6-repl-cursor-navigation/candidate/stdlib-p0.manifest.json"
)
BUILD = ROOT / "build/c2.3/v1.6-comfort-repl"
ARTIFACT = BUILD / "repl-comfort"
OBSERVATIONS = BUILD / "observations.json"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-comfort-repl-host-first-receipt.json"
)
FORMAT = "lisp65-c2-v160-comfort-repl-host-first-v1"
SEALED_COMMIT = "c4a78738"
RECLAIMS = [
    "%take", "%case-fold-list", "%fasl-len", "%subseq-list", "%append2",
]
HYBRID_RECLAIM = "%require-c2d-header-layout-p"
DISPLAY_RECLAIM = "%fasl-fs"
RECLAIM_CALLERS = {
    "%take": ["butlast"],
    "%case-fold-list": ["string-equal"],
    "%fasl-len": ["%fasl-obj"],
    "%subseq-list": ["substring"],
    "%append2": ["%append-lists"],
}
NEW_NAMES = ["repl", "repl-comfort", "%repl-read", "%repl-step"]


class ComfortGateError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ComfortGateError(message)


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"authority absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    return {
        "path": path.resolve().relative_to(ROOT.resolve()).as_posix(),
        "bytes": len(raw),
        "sha256": sha(raw),
    }


def write(path: Path, value: dict[str, Any]) -> None:
    payload = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(payload)
    temporary.replace(path)


def validate_contract(contract: dict[str, Any]) -> dict[str, Any]:
    require(
        contract.get("format") == "lisp65-c2-v160-comfort-repl-implementation-v1"
        and contract.get("status") == "owner-authorized-host-first"
        and contract.get("pricing_acceptance_commit") == "cac1ee30"
        and contract.get("library_scope_commit") == "7002c51c",
        "Comfort implementation authority drift",
    )
    activation = contract["activation"]
    require(
        activation == {
            "library_designator": "repl-comfort",
            "public_entry": "repl",
            "requires": ["core", "ide"],
            "native_repl_remains_fallback": True,
        },
        "Comfort activation contract drift",
    )
    semantics = contract["semantics"]
    require(
        semantics == {
            "maximum_history_lines": 10,
            "indent_spaces_per_depth": 2,
            "maximum_indent_depth": 10,
            "physical_line_limit": 250,
            "aggregate_input_exceeds_native_192": True,
            "overclose_rejected_before_evaluation": True,
            "scanner_shared_with_ide": "%ide-line-net-depth",
            "evaluation_path": ["read-from-string", "lcc-run"],
            "top_level_wrapper": "progn",
        },
        "Comfort semantic contract drift",
    )
    budget = contract["symbol_budget"]
    reclaimed = sum(len(name) + 1 for name in RECLAIMS)
    added = sum(len(name) + 1 for name in NEW_NAMES)
    baseline = budget["baseline_projected_free"]
    projected = {
        "symbol_slots": baseline["symbol_slots"] + len(RECLAIMS) - len(NEW_NAMES),
        "namepool_bytes": baseline["namepool_bytes"] + reclaimed - added,
    }
    adjusted = {
        key: projected[key] + budget["measured_projection_bias"][key]
        for key in projected
    }
    minimum = budget["release_minimum_free"]
    margin = {key: adjusted[key] - minimum[key] for key in adjusted}
    require(
        budget["reclaimed_private_entries"] == RECLAIMS
        and budget["new_interned_names"] == NEW_NAMES
        and (reclaimed, added) == (54, 40)
        and budget["reclaimed_namepool_bytes"] == reclaimed
        and budget["new_namepool_bytes"] == added
        and baseline == {"symbol_slots": 32, "namepool_bytes": 562}
        and projected == budget["projected_free"]
        == {"symbol_slots": 33, "namepool_bytes": 576}
        and budget["measured_projection_bias"]
        == {"symbol_slots": -1, "namepool_bytes": -4}
        and adjusted == budget["bias_adjusted_free"]
        == {"symbol_slots": 32, "namepool_bytes": 572}
        and minimum == {"symbol_slots": 32, "namepool_bytes": 384}
        and margin == budget["bias_adjusted_margin"]
        == {"symbol_slots": 0, "namepool_bytes": 188}
        and budget["future_named_helper_requires_repricing"] is True
        and "loads repl-comfort" in budget["d5_configuration"],
        "bias-adjusted Comfort symbol arithmetic drift",
    )
    placement = contract["placement"]
    require(
        placement == {
            "resident_code_delta_bytes": 0,
            "resident_state_delta_bytes": 0,
            "native_primitive_delta": 0,
            "product_links": 0,
            "hardware_runs": 0,
        },
        "Comfort placement/claim wall drift",
    )
    gates = contract["gates"]
    required_cases = gates.get("comfort_required_cases")
    require(
        set(gates) == {"real_workbench_cases", "comfort_required_cases",
            "long_input_dynamic_cases", "code_object_limit_bytes",
            "device_d5_required_before_release"}
        and gates["real_workbench_cases"] == 248
        and isinstance(required_cases, list)
        and len(required_cases) == len(set(required_cases))
        and "comfort-cursor-down-empty-boundary" in required_cases
        and gates["long_input_dynamic_cases"] == 1
        and gates["code_object_limit_bytes"] == 255
        and gates["device_d5_required_before_release"] is True,
        "Comfort executable/release gate wall drift",
    )
    return {
        "projected_free": projected,
        "bias_adjusted_free": adjusted,
        "bias_adjusted_margin": margin,
        "reclaimed_namepool_bytes": reclaimed,
        "new_namepool_bytes": added,
    }


def source_gate(contract: dict[str, Any]) -> dict[str, Any]:
    comfort = COMFORT.read_text(encoding="utf-8")
    scanner = SCANNER.read_text(encoding="utf-8")
    ide = IDE_SYNTAX.read_text(encoding="utf-8")
    editor = READ_LINE.read_text(encoding="utf-8")
    native = NATIVE_REPL.read_text(encoding="utf-8")
    suite = load(COMFORT_SUITE)
    resident = load(RESIDENT_SUITE)
    ide_suite = load(IDE_SUITE)
    keymap = load(KEYMAP_CONTRACT)
    KEYMAP.validate(keymap)

    case_names = [row.get("name") for row in suite.get("cases", [])]
    validate_case_registry(contract["gates"]["comfort_required_cases"],
                           case_names)
    require(
        comfort.count("(defun %repl-read ") == 1
        and comfort.count("(defun %repl-step ") == 1
        and comfort.count("(defun repl ") == 1
        and comfort.count("(read-from-string ") == 1
        and comfort.count("(lcc-run form)") == 1
        and '(string-append "(progn " source ")")' in comfort
        and "%c2-compile-form" not in comfort
        and "lcc-install" not in comfort,
        "Comfort does not hand one progn to the exact public evaluation seam",
    )
    require(
        "((< next-depth 0)" in comfort
        and comfort.index("((< next-depth 0)") < comfort.index("(t (repl 'eval")
        and "(write-line \"*** reader: unmatched close parenthesis\")" in comfort
        and "(* 2 (if (> depth 10) 10 depth))" in comfort
        and "(>= (length history) 10)" in comfort
        and ("(if (< length 250)" in editor
             or "(if (< (car (nthcdr 4 state)) 250)" in editor),
        "balanced-input/history/line-bound semantics drift",
    )
    require(
        scanner.count("(defun %ide-line-net-depth ") == 1
        and "(if (< d 0)" in scanner
        and "(if (= c 59)" in scanner
        and "(if (= c 34)" in scanner
        and "(defun %ide-line-net-depth " not in ide
        and "lib/sexp-depth.lisp" in ide_suite.get("sources", [])
        and "lib/sexp-depth.lisp" in ide_suite.get("functions_from_sources", [])
        and suite.get("sources") == ["lib/repl-comfort.lisp"]
        and "lib/sexp-depth.lisp" not in suite.get("sources", []),
        "IDE/Comfort scanner ceased to be one shared source",
    )
    projection = keymap["repl_line_projection"]["binding_ids"]
    require(
        projection == [
            "return", "delete-backward", "cursor-left", "cursor-right",
            "cursor-up", "cursor-down", "control-d", "control-f",
            "control-b", "control-a", "control-e",
        ]
        and generated_block(editor) == KEYMAP.render_repl_expression(keymap).strip()
        and "((or (= command 1108) (= command 1003))" in editor
        and "(if (car (nthcdr 8 state)) command (%read-line-loop state))" in editor,
        "Comfort history navigation is not generated from the shared keymap",
    )
    require(
        "static uint8_t read_line(" in native
        and "st = read_line(buf, &n, BUF_MAX);" in native
        and "vm_run_dir" not in native[native.index("st = read_line"):][:300],
        "native C REPL no longer owns boot/fail-closed input",
    )
    require(
        suite.get("name") == contract["activation"]["library_designator"]
        and suite.get("provides") == ["repl-comfort"]
        and suite.get("requires") == contract["activation"]["requires"]
        and suite.get("functions") == ["%repl-read", "%repl-step", "repl"]
        and suite.get("tailcall_self") == ["%repl-read", "%repl-step"]
        and suite.get("require_all_defuns") is True
        and resident.get("private_inline_functions", [])[-7:]
            == RECLAIMS + [HYBRID_RECLAIM, DISPLAY_RECLAIM],
        "Comfort suite/library identity drift",
    )
    return {
        "functions": suite["functions"],
        "static_cases": len(suite["cases"]),
        "keymap_bindings": len(KEYMAP.repl_projection(keymap)),
        "native_fallback": True,
        "shared_scanner": True,
        "evaluation_path": ["read-from-string", "lcc-run"],
    }


def validate_case_registry(required: list[str], observed: list[Any]) -> None:
    require(len(required) == len(set(required))
            and len(observed) == len(set(observed))
            and set(observed) == set(required),
            "Comfort required-case registry drift")


def case_registry_mutations(contract: dict[str, Any]) -> dict[str, str]:
    required = contract["gates"]["comfort_required_cases"]
    cases = load(COMFORT_SUITE)["cases"]
    observed = [row["name"] for row in cases]
    trials = {
        "remove-required-empty-boundary": [name for name in observed
            if name != "comfort-cursor-down-empty-boundary"],
        "add-unregistered-case": [*observed, "comfort-unregistered-mutant"],
    }
    rejected: dict[str, str] = {}
    for name, candidate in trials.items():
        try:
            validate_case_registry(required, candidate)
        except ComfortGateError as error:
            rejected[name] = str(error)
        else:
            raise ComfortGateError(
                f"Comfort case-registry mutation survived: {name}")
    require(len(rejected) == 2,
            "Comfort case-registry mutation count drift")
    return rejected


def generated_block(source: str) -> str:
    require(source.count(KEYMAP.REPL_BLOCK_BEGIN) == 1
            and source.count(KEYMAP.REPL_BLOCK_END) == 1,
            "generated REPL keymap boundary drift")
    _before, tail = source.split(KEYMAP.REPL_BLOCK_BEGIN, 1)
    body, _after = tail.split(KEYMAP.REPL_BLOCK_END, 1)
    return body.strip()


def run_artifact() -> dict[str, Any]:
    BUILD.mkdir(parents=True, exist_ok=True)
    process = subprocess.run(
        [
            sys.executable, "tools/host-lisp/bytecode_p0_stdlib.py",
            "--check", "--artifact-role", "disk-lib", "--emit-artifacts",
            str(ARTIFACT.relative_to(ROOT)), "--observation-report",
            str(OBSERVATIONS.relative_to(ROOT)), str(COMFORT_SUITE.relative_to(ROOT)),
        ],
        cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    )
    require(process.returncode == 0, "Comfort executable suite red:\n" + process.stdout)
    manifest = load(ARTIFACT.with_suffix(".manifest.json"))
    require(
        manifest.get("artifact_role") == "disk-lib"
        and manifest.get("name") == "repl-comfort"
        and manifest.get("provides") == ["repl-comfort"]
        and manifest.get("requires") == ["core", "ide"]
        and manifest.get("functions") == ["%repl-read", "%repl-step", "repl"]
        and manifest.get("objects") == 3
        and manifest["cost"]["largest_code_object"] in manifest["functions"]
        and manifest["cost"]["largest_code_object_bytes"] <= 255,
        "Comfort disk-library artifact identity/size drift",
    )
    resident = P._read_suite(str(ROOT / "tests/bytecode/libs/p0-repl-comfort-resident.json"))
    resident_names = set(resident.get("functions", []))
    symbol_names = set(manifest["cost"]["symbol_names"])
    novel_entries = (symbol_names - resident_names) | set(manifest["provides"])
    require(novel_entries == set(NEW_NAMES),
            f"unpriced Comfort symbol escaped artifact: {sorted(novel_entries)}")
    return {
        "manifest": bind(ARTIFACT.with_suffix(".manifest.json")),
        "blob": bind(ARTIFACT.with_suffix(".blob.bin")),
        "directory": bind(ARTIFACT.with_suffix(".dir.bin")),
        "observations": bind(OBSERVATIONS),
        "objects": manifest["objects"],
        "code_bytes": manifest["code_bytes"],
        "directory_bytes": manifest["directory_bytes"],
        "largest_code_object_bytes": manifest["cost"]["largest_code_object_bytes"],
        "new_interned_names": sorted(novel_entries),
    }


def reclaim_gate(contract: dict[str, Any]) -> dict[str, Any]:
    manifest = load(PRICING_MANIFEST)
    sites = PRICING.call_sites(manifest)
    require({name: sites.get(name) for name in RECLAIMS} == RECLAIM_CALLERS,
            "five reclaim candidates are not single-caller product entries")
    require(sites.get(HYBRID_RECLAIM) == ["%require-c2d-state"],
            "hybrid reclaim is not a single-caller product entry")
    suite = P._read_suite(str(CORE_SUITE))
    existing = list(suite.get("private_inline_functions", []))
    require(sites.get(DISPLAY_RECLAIM) == ["%c1-compile-source"],
            "display reclaim is not a single-caller product entry")
    live_reclaims = RECLAIMS + [HYBRID_RECLAIM, DISPLAY_RECLAIM]
    callers = {
        **RECLAIM_CALLERS,
        HYBRID_RECLAIM: ["%require-c2d-state"],
        DISPLAY_RECLAIM: ["%c1-compile-source"],
    }
    require(not (set(existing) & set(live_reclaims)),
            "reclaim was already hidden in baseline")
    suite["private_inline_functions"] = existing + live_reclaims
    suite["min_private_inline_functions"] = len(existing) + len(live_reclaims)
    result = P.check_suite("v1.6-comfort-five-reclaims", suite)
    code = result["code_by_name"]
    require(
        result["cases"] == contract["gates"]["real_workbench_cases"] == 248
        and result["functions"]
            == len(suite["functions"]) - len(suite["private_inline_functions"])
        and all(name not in code for name in live_reclaims)
        and all(caller in code for rows in callers.values() for caller in rows),
        "real Workbench suite did not preserve all callers under seven reclaims",
    )
    return {
        "status": "PASS: real compiler and complete Workbench suite",
        "cases": result["cases"],
        "functions_after": result["functions"],
        "private_inline_functions_after": len(existing) + len(live_reclaims),
        "entries_absent": live_reclaims,
        "callers_preserved": callers,
    }


def long_input_gate() -> dict[str, Any]:
    suite = P._read_suite(str(COMFORT_SUITE))
    comfort = COMFORT.read_text(encoding="utf-8")
    prompts = re.findall(r'\(screen-write-string 0 row "([^"]+)"\)', comfort)
    require(prompts == ["l65> "],
            "Comfort prompt must have one candidate-derived source owner")
    # Cross the native aggregate ceiling with ordinary short physical lines.
    # A single 200-byte line only measures the Python reference VM's recursion
    # depth; Comfort's promise is that the *aggregate* is heap-backed.
    comments = [";" + ("x" * 40) for _ in range(5)]
    lines = ["(+ 1", *comments, "2)"]
    events: list[int] = []
    for line in lines:
        events.extend(line.encode("ascii"))
        events.append(13)
    events.append(13)
    aggregate_bytes = sum(map(len, lines)) + (len(lines) - 1) * 3
    require(aggregate_bytes > 192 and max(map(len, lines)) < 250,
            "long-input fixture does not cross only the aggregate limit")
    suite["cases"] = [{
        "name": "comfort-aggregate-input-exceeds-native-buffer",
        "expr": "(repl)",
        "expect": "nil",
        "expect_output_codes": [10] * (len(lines) + 2),
        "max_steps": 3000000,
        "key_events": events,
        "expect_key_events_remaining": 0,
    }]
    result = P.check_suite("v1.6-comfort-long-input", suite)
    require(result["cases"] == 1, "long-input execution witness absent")
    return {
        "status": "PASS: heap aggregate exceeds native C line",
        "aggregate_source_bytes": aggregate_bytes,
        "longest_typed_physical_line_bytes": max(map(len, lines)),
        "native_buffer_bytes": 192,
        "cases": 1,
    }


def executable_scanner_mutation() -> str:
    source = SCANNER.read_text(encoding="utf-8")
    require("(if (< d 0)" in source, "scanner mutation anchor absent")
    changed = source.replace("(if (< d 0)", "(if nil", 1)
    root = BUILD / "mutation"
    root.mkdir(parents=True, exist_ok=True)
    path = root / "sexp-depth.lisp"
    path.write_text(changed, encoding="utf-8")
    suite = {
        "sources": [str(path.relative_to(ROOT))],
        "functions": ["%ide-line-net-depth"],
        "tailcall_self": ["%ide-line-net-depth"],
        "cases": [{
            "name": "overclose-cannot-be-cancelled-later",
            "expr": "(%ide-line-net-depth (string->list \")(\") 0 0)",
            "expect": "-1",
        }],
    }
    try:
        P.check_suite("v1.6-comfort-overclose-mutation", suite)
    except AssertionError:
        return "rejected-by-executable-overclose-case"
    raise ComfortGateError("non-sticky overclose scanner mutation survived")


def mutations(contract: dict[str, Any]) -> dict[str, str]:
    rows: list[tuple[str, dict[str, Any]]] = []

    def changed(label: str, path: list[str], value: Any) -> None:
        candidate = copy.deepcopy(contract)
        cursor: Any = candidate
        for key in path[:-1]:
            cursor = cursor[key]
        cursor[path[-1]] = value
        rows.append((label, candidate))

    changed("lower-symbol-floor", ["symbol_budget", "release_minimum_free", "symbol_slots"], 31)
    changed("erase-measured-bias", ["symbol_budget", "measured_projection_bias", "symbol_slots"], 0)
    changed("hide-private-helper", ["symbol_budget", "new_interned_names"], NEW_NAMES[:-1])
    changed("drop-reclaim", ["symbol_budget", "reclaimed_private_entries"], RECLAIMS[:-1])
    changed("omit-NUL-price", ["symbol_budget", "new_namepool_bytes"], 36)
    changed("skip-D5", ["gates", "device_d5_required_before_release"], False)
    changed("replace-eval-path", ["semantics", "evaluation_path"], ["eval"])
    changed("weaken-overclose", ["semantics", "overclose_rejected_before_evaluation"], False)
    changed("grow-history-silently", ["semantics", "maximum_history_lines"], 11)
    changed("claim-hardware", ["placement", "hardware_runs"], 1)
    rejected: dict[str, str] = {}
    for label, candidate in rows:
        try:
            validate_contract(candidate)
        except ComfortGateError as error:
            rejected[label] = str(error)
        else:
            raise ComfortGateError(f"Comfort contract mutation survived: {label}")
    require(len(rejected) == 10, "Comfort contract mutation count drift")
    return rejected


def run_selftest() -> dict[str, Any]:
    contract = load(CONTRACT)
    pricing = validate_contract(contract)
    source = source_gate(contract)
    rejected = mutations(contract)
    case_rejected = case_registry_mutations(contract)
    executable = executable_scanner_mutation()
    return {
        "pricing": pricing,
        "source": source,
        "contract_mutations_rejected": rejected,
        "case_registry_mutations_rejected": case_rejected,
        "executable_mutation": executable,
    }


def run_check() -> dict[str, Any]:
    contract = load(CONTRACT)
    selftest = run_selftest()
    artifact = run_artifact()
    reclaim = reclaim_gate(contract)
    long_input = long_input_gate()
    value = {
        "format": FORMAT,
        "recorded_on": "2026-08-18",
        "status": "PASS: v1.6 Comfort REPL host-qualified",
        "promotable": False,
        "product_links": 0,
        "hardware_runs": 0,
        "source": selftest["source"],
        "symbol_budget": selftest["pricing"],
        "reclamation": reclaim,
        "artifact": artifact,
        "long_input": long_input,
        "mutations_rejected": {
            "contract": selftest["contract_mutations_rejected"],
            "case_registry": selftest["case_registry_mutations_rejected"],
            "scanner": selftest["executable_mutation"],
        },
        "authority": {
            "contract": bind(CONTRACT),
            "comfort_source": bind(COMFORT),
            "scanner_source": bind(SCANNER),
            "editor_source": bind(READ_LINE),
            "comfort_suite": bind(COMFORT_SUITE),
            "resident_suite": bind(RESIDENT_SUITE),
            "core_suite": bind(CORE_SUITE),
            "ide_suite": bind(IDE_SUITE),
            "keymap": bind(KEYMAP_CONTRACT),
            "native_repl": bind(NATIVE_REPL),
            "checker": bind(Path(__file__)),
        },
        "claim_limit": "host source/artifact semantics and bias-adjusted capacity; no device claim",
        "next": "owner review authorizes the one Comfort hardware acceptance contact",
    }
    # This receipt certifies the original Comfort card.  Once a successor
    # changes its sources, execute the live semantics above but leave the
    # historical receipt in its own world instead of rewriting its evidence.
    sealed = ERA.era_blob(
        SEALED_COMMIT, RECEIPT.relative_to(ROOT).as_posix())
    live_moved = any(
        path.read_bytes() != ERA.era_blob(
            SEALED_COMMIT, path.relative_to(ROOT).as_posix())
        for path in (COMFORT, READ_LINE, NATIVE_REPL))
    if live_moved:
        require(RECEIPT.read_bytes() == sealed,
                "historical Comfort receipt changed under successor source")
    else:
        write(RECEIPT, value)
    return value


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("selftest", "check"))
    args = parser.parse_args(argv)
    try:
        value = run_selftest() if args.command == "selftest" else run_check()
        if args.command == "selftest":
            print("c2-v160-comfort-repl: SELFTEST PASS mutations=10+2+1")
        else:
            print(
                "c2-v160-comfort-repl: PASS "
                f"cases={value['source']['static_cases']}+{value['long_input']['cases']} "
                f"workbench={value['reclamation']['cases']} "
                f"objects={value['artifact']['objects']} "
                f"largest={value['artifact']['largest_code_object_bytes']} "
                "D5=32/572 resident=+0 native=+0"
            )
        return 0
    except (ComfortGateError, KEYMAP.KeymapError, P.StdlibCheckError,
            AssertionError, KeyError, OSError, ValueError) as error:
        print(f"c2-v160-comfort-repl: FIRST RED: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
