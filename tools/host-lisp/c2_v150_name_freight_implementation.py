#!/usr/bin/env python3
"""Build and prove the authorized v1.5 combined name-freight form.

Historical library sources and artifacts remain untouched.  This successor
generates two v1.5-only sources: a string-backed who-calls index which interns
only the selected row on first use, and an exact private-name rewrite of the
defstruct source.  It then compiles both through the real disk-library path,
checks public surface and semantic parity, and prices the actual D5 union.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import bytecode_p0_stdlib as STDLIB  # noqa: E402
import c2_v150_name_freight_pricing as PRICE  # noqa: E402
import comfort_track_gate as COMFORT  # noqa: E402


BUILD = ROOT / "build/c2.3/v1.5.0-name-freight-libraries"
SOURCE_DIR = BUILD / "sources"
SUITE_DIR = BUILD / "suites"
INSPECT_PREFIX = BUILD / "inspect"
DEFSTRUCT_PREFIX = BUILD / "defstruct"
INSPECT_SOURCE = SOURCE_DIR / "who-calls-scoped.lisp"
DEFSTRUCT_SOURCE = SOURCE_DIR / "defstruct-short.lisp"
INSPECT_SUITE = SUITE_DIR / "p0-inspect-trace-v15.json"
DEFSTRUCT_SUITE = SUITE_DIR / "p0-defstruct-v15.json"
INSPECT_MANIFEST = INSPECT_PREFIX.with_suffix(".manifest.json")
DEFSTRUCT_MANIFEST = DEFSTRUCT_PREFIX.with_suffix(".manifest.json")
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.5.0-name-freight-implementation-receipt.json")
CONTRACT = ROOT / "config/release-user-headroom-contract.json"
AUTHORIZATION_COMMIT = "a8f7f08a"
PLAN_PATH = "docs/planning/v1.5.0-release-work-plan.md"
FORMAT = "lisp65-c2.3-v1.5.0-name-freight-implementation-v1"


class ImplementationError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ImplementationError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"authority absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": sha(raw)}


def git_bind(commit: str, path: str) -> dict[str, Any]:
    full = subprocess.run(
        ["git", "rev-parse", f"{commit}^{{commit}}"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE).stdout.decode().strip()
    raw = subprocess.run(
        ["git", "show", f"{full}:{path}"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE).stdout
    return {"commit": full, "path": path, "bytes": len(raw), "sha256": sha(raw)}


def scoped_who_calls_source(graph: dict[str, list[str]]) -> str:
    lines = [
        "; Generated from v1.3 shelf directory-only entry refs; do not edit.",
        "; v1.5 keeps names as strings and interns only the selected row.",
        "(defun %comfort-callers-index (name rows)",
        "  (if rows",
        "      (if (string= (symbol-name name) (car (car rows)))",
        "          (mapcar (function intern) (cdr (car rows)))",
        "          (%comfort-callers-index name (cdr rows)))",
        "      nil))",
        "",
        "(defun who-calls (name)",
        "  (%comfort-callers-index",
        "   name",
        "   '(",
    ]
    for target, callers in sorted(graph.items()):
        values = " ".join(json.dumps(value) for value in [target, *callers])
        lines.append(f"     ({values})")
    lines.extend(["     )))", ""])
    return "\n".join(lines)


def short_mapping() -> dict[str, str]:
    price = load(PRICE.RECEIPT)
    mapping = price["lever_1_short_internal_names"]["groups"]["defstruct"][
        "mapping"]
    result = {old: new for old, new in mapping.items() if old.startswith("%")}
    require(len(result) == 20 and all(new.startswith("%d") for new in result.values()),
            "authorized percent-private defstruct mapping drift")
    require("value" not in result and "new-value" not in result,
            "public-looking lexical names entered the private-percent rewrite")
    return result


def rewrite_tokens(source: str, mapping: dict[str, str]) -> str:
    result = source
    constituents = r"A-Za-z0-9%*+/<>=!?_.-"
    for old in sorted(mapping, key=len, reverse=True):
        result = re.sub(
            rf"(?<![{constituents}]){re.escape(old)}(?![{constituents}])",
            mapping[old], result)
    return result


def generated_inputs() -> dict[str, Any]:
    contract = COMFORT.load(COMFORT.CONTRACT)
    graph, graph_info = COMFORT.shelf_graph(contract)
    who_source = scoped_who_calls_source(graph)
    base_defstruct = (ROOT / "lib/defstruct.lisp").read_text(encoding="utf-8")
    mapping = short_mapping()
    short_source = rewrite_tokens(base_defstruct, mapping)
    require(rewrite_tokens(short_source, {new: old for old, new in mapping.items()})
            == base_defstruct, "private defstruct rewrite is not invertible")
    require(not any(old in short_source for old in mapping),
            "old private defstruct name survived the rewrite")

    inspect_suite = load(ROOT / "tests/bytecode/libs/p0-inspect-trace.json")
    inspect_suite["name"] = "inspect-trace-v15-scoped"
    inspect_suite["description"] = (
        "v1.5 inspect candidate with exact trace ABI and first-use who-calls metadata")
    inspect_suite["sources"] = [
        INSPECT_SOURCE.relative_to(ROOT).as_posix(), "lib/inspect-trace.lisp"]
    inspect_suite["resident_suite"] = str(
        ROOT / "tests/bytecode/libs/p0-stdlib-ship-input-wait-base.json")

    defstruct_suite = load(ROOT / "tests/bytecode/libs/p0-defstruct-v1-lib.json")
    defstruct_suite["name"] = "defstruct-v15-short-private"
    defstruct_suite["description"] = (
        "v1.5 defstruct candidate with percent-private aliases and unchanged surface")
    defstruct_suite["sources"] = [DEFSTRUCT_SOURCE.relative_to(ROOT).as_posix()]
    defstruct_suite["resident_suite"] = str(
        ROOT / "tests/bytecode/libs/p0-stdlib-require-resolver.json")
    defstruct_suite["functions"] = [mapping.get(name, name)
                                    for name in defstruct_suite["functions"]]
    for case in defstruct_suite["cases"]:
        case["expr"] = rewrite_tokens(case["expr"], mapping)
    return {
        "graph": graph, "graph_info": graph_info,
        "who_source": who_source, "defstruct_source": short_source,
        "mapping": mapping, "inspect_suite": inspect_suite,
        "defstruct_suite": defstruct_suite,
    }


def write_generated(inputs: dict[str, Any]) -> None:
    SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    SUITE_DIR.mkdir(parents=True, exist_ok=True)
    INSPECT_SOURCE.write_text(inputs["who_source"], encoding="utf-8")
    DEFSTRUCT_SOURCE.write_text(inputs["defstruct_source"], encoding="utf-8")
    INSPECT_SUITE.write_bytes(canonical(inputs["inspect_suite"]))
    DEFSTRUCT_SUITE.write_bytes(canonical(inputs["defstruct_suite"]))


def compile_library(suite_path: Path, prefix: Path) -> dict[str, Any]:
    suite = STDLIB._read_suite(str(suite_path))
    checked = STDLIB.check_suite(str(suite_path), suite)
    artifact = STDLIB.emit_artifacts(
        str(suite_path), suite, str(prefix), base_addr=0,
        artifact_role="disk-lib")
    return {"checked": checked, "artifact": artifact,
            "manifest": load(prefix.with_suffix(".manifest.json"))}


def public_entries(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    return sorted(
        ({"name": row["name"], "kind": row["kind"],
          "flags": int(row.get("flags", 0))}
         for row in manifest["entries"] if not str(row["name"]).startswith("%")),
        key=lambda row: row["name"])


def build_outputs(*, clean: bool) -> dict[str, Any]:
    if clean and BUILD.exists():
        shutil.rmtree(BUILD)
    inputs = generated_inputs()
    write_generated(inputs)
    inspect_result = compile_library(INSPECT_SUITE, INSPECT_PREFIX)
    defstruct_result = compile_library(DEFSTRUCT_SUITE, DEFSTRUCT_PREFIX)
    return {"inputs": inputs, "inspect": inspect_result,
            "defstruct": defstruct_result}


def capacity(manifest_inspect: dict[str, Any],
             manifest_defstruct: dict[str, Any]) -> dict[str, Any]:
    cold = PRICE.cold_link97_names()
    shipped = (cold | {"inspect"} | PRICE.CAP.manifest_names(INSPECT_MANIFEST)
               | {"string-extra"} | PRICE.CAP.manifest_names(PRICE.CAP.STRING_EXTRA)
               | PRICE.CAP.manifest_names(PRICE.CAP.PLACE) | {"defstruct"}
               | PRICE.CAP.manifest_names(DEFSTRUCT_MANIFEST))
    final = shipped | {"trace-probe", "x"} | {
        "point", "y", "make-point", "point-p", "copy-point", "point-x",
        "point-set-x", "point-with-x", "point-y", "point-set-y",
        "point-with-y", "v15-ceremony-probe", "v15-perf-probe",
    }
    maximum = PRICE.mk_int("MAX_SYM")
    namepool = PRICE.mk_int("NAMEPOOL")
    row = PRICE.capacity(final, maximum, namepool)
    floors = load(CONTRACT)["minimum_free"]
    require(row == {"symbols": 717, "namepool_bytes": 9659,
                    "symbol_headroom": 35, "namepool_headroom": 549},
            "actual combined-form D5 price drift")
    require(PRICE.fits(row, floors), "actual combined form violates user headroom")
    return {"final_D5": row, "minimum_free": floors,
            "margin_above_floor": {
                "symbol_slots": row["symbol_headroom"] - floors["symbol_slots"],
                "namepool_bytes": row["namepool_headroom"] - floors["namepool_bytes"]},
            "lexical_name_adjustment": (
                "549 rather than the priced 557 name bytes: authorization permits "
                "only percent-private renames, so value/new-value remain unchanged")}


def derive(*, rebuild: bool) -> dict[str, Any]:
    results = build_outputs(clean=rebuild)
    inputs = results["inputs"]
    inspect = results["inspect"]["manifest"]
    defstruct = results["defstruct"]["manifest"]
    old_inspect = load(PRICE.CAP.INSPECT)
    old_defstruct = load(PRICE.CAP.DEFSTRUCT)

    expected_inspect_public = public_entries(old_inspect)
    expected_defstruct_public = public_entries(old_defstruct)
    require(public_entries(inspect) == expected_inspect_public
            and public_entries(defstruct) == expected_defstruct_public,
            "public library surface changed")
    require(results["inspect"]["checked"]["cases"] == 4
            and results["defstruct"]["checked"]["cases"] == 2,
            "host semantic case count drift")

    mapping = inputs["mapping"]
    old_private = set(mapping)
    new_entries = {row["name"] for row in defstruct["entries"]}
    require(not (old_private & new_entries)
            and set(mapping.values()) <= new_entries
            and {"defstruct"} <= new_entries,
            "defstruct private alias closure drift")
    old_shapes = {row["name"]: (row["kind"], row["length"], row["lit_count"])
                  for row in old_defstruct["entries"]}
    new_shapes = {{new: old for old, new in mapping.items()}.get(
        row["name"], row["name"]): (row["kind"], row["length"], row["lit_count"])
                  for row in defstruct["entries"]}
    require(old_shapes == new_shapes,
            "defstruct alias rewrite changed object shape")

    lazy = set(load(PRICE.RECEIPT)["lever_2_scoped_interning"]["eager_only_names"])
    inspect_symbols = PRICE.CAP.manifest_names(INSPECT_MANIFEST)
    require(not (lazy & inspect_symbols),
            "string-backed who-calls metadata still interns an eager-only name")
    require(inputs["graph_info"]["unique_edges"] == 109
            and inputs["graph_info"]["targets"] == 50,
            "who-calls graph semantic authority drift")
    require(any(case["name"] == "who-calls-known"
                for case in inputs["inspect_suite"]["cases"]),
            "who-calls first-use result case absent")

    capacity_result = capacity(inspect, defstruct)
    return {
        "format": FORMAT, "recorded_on": "2026-08-11",
        "status": "HOST-GREEN-COMBINED-NAME-FREIGHT; MEDIA-PENDING",
        "authority": {
            "owner_authorization": git_bind(AUTHORIZATION_COMMIT, PLAN_PATH),
            "headroom_contract": bind(CONTRACT),
            "pricing_receipt": bind(PRICE.RECEIPT),
            "historical_who_calls": bind(ROOT / "lib/comfort-who-calls-generated.lisp"),
            "historical_defstruct": bind(ROOT / "lib/defstruct.lisp"),
            "trace_source": bind(ROOT / "lib/inspect-trace.lisp"),
            "historical_inspect_manifest": bind(PRICE.CAP.INSPECT),
            "historical_defstruct_manifest": bind(PRICE.CAP.DEFSTRUCT),
            "checker": bind(Path(__file__)),
        },
        "generated": {
            "who_calls_source": bind(INSPECT_SOURCE),
            "defstruct_source": bind(DEFSTRUCT_SOURCE),
            "inspect_suite": bind(INSPECT_SUITE),
            "defstruct_suite": bind(DEFSTRUCT_SUITE),
        },
        "who_calls": {
            "representation": "string rows; selected row interned on first use",
            "targets": inputs["graph_info"]["targets"],
            "unique_edges": inputs["graph_info"]["unique_edges"],
            "eager_only_symbols_removed": len(lazy),
            "eager_only_name_bytes_removed": PRICE.CAP.name_bytes(lazy),
            "first_use_case": "who-calls-known PASS",
            "manifest_contains_eager_only_symbols": False,
        },
        "defstruct": {
            "renamed_percent_private_entries": len(mapping),
            "mapping": mapping,
            "public_entries": expected_defstruct_public,
            "old_object_shapes_equal_after_inverse_alias": True,
            "non_percent_lexical_names_renamed": False,
        },
        "surface_parity": {
            "inspect": expected_inspect_public,
            "defstruct": expected_defstruct_public,
            "public_names_changed": 0,
        },
        "artifacts": {
            "inspect_manifest": bind(INSPECT_MANIFEST),
            "inspect_external_image": bind(INSPECT_PREFIX.with_suffix(".ext.bin")),
            "defstruct_manifest": bind(DEFSTRUCT_MANIFEST),
            "defstruct_external_image": bind(
                DEFSTRUCT_PREFIX.with_suffix(".ext.bin")),
            "resident_delta_bytes": 0,
        },
        "capacity": capacity_result,
        "execution_accounting": {"product_links": 0, "media_builds": 0,
                                 "device_contacts": 0},
        "claim_limit": (
            "Host library implementation, equivalence, surface parity and exact "
            "D5 freight only. Product bytes are unchanged. Media, D1-D5, Halt and "
            "release remain unclaimed until the regular successor media closure."),
    }


def audit(value: dict[str, Any]) -> None:
    require(value == derive(rebuild=True),
            "name-freight implementation receipt differs from fresh rebuild")


def mutate(value: dict[str, Any], path: list[str], replacement: Any) -> None:
    cursor: Any = value
    for key in path[:-1]:
        cursor = cursor[key]
    cursor[path[-1]] = replacement


def selftest() -> dict[str, Any]:
    base = derive(rebuild=True)
    cases: list[tuple[str, list[str], Any]] = [
        ("rename-public", ["surface_parity", "public_names_changed"], 1),
        ("eager-symbol", ["who_calls", "manifest_contains_eager_only_symbols"], True),
        ("drop-edge", ["who_calls", "unique_edges"], 108),
        ("drop-target", ["who_calls", "targets"], 49),
        ("skip-first-use", ["who_calls", "first_use_case"], "absent"),
        ("retain-old-private", ["defstruct", "renamed_percent_private_entries"], 19),
        ("rename-lexical", ["defstruct", "non_percent_lexical_names_renamed"], True),
        ("change-object-shape", ["defstruct",
                                 "old_object_shapes_equal_after_inverse_alias"], False),
        ("lower-symbol-floor", ["capacity", "minimum_free", "symbol_slots"], 0),
        ("lower-name-floor", ["capacity", "minimum_free", "namepool_bytes"], 0),
        ("omit-D5-name", ["capacity", "final_D5", "symbols"], 716),
        ("claim-resident", ["artifacts", "resident_delta_bytes"], 1),
        ("claim-product-link", ["execution_accounting", "product_links"], 1),
        ("claim-media", ["execution_accounting", "media_builds"], 1),
    ]
    rejected: list[str] = []
    for name, path, replacement in cases:
        trial = deepcopy(base); mutate(trial, path, replacement)
        try:
            audit(trial)
        except ImplementationError:
            rejected.append(name)
    require(rejected == [row[0] for row in cases],
            "name-freight implementation mutation survived")
    return {"status": "SELFTEST PASS", "mutations": len(rejected),
            "symbol_headroom": base["capacity"]["final_D5"]["symbol_headroom"],
            "namepool_headroom": base["capacity"]["final_D5"]["namepool_headroom"]}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("build", "check", "selftest"))
    action = parser.parse_args().action
    if action == "build":
        value = derive(rebuild=True)
        RECEIPT.write_bytes(canonical(value))
        result = {"status": "BUILT", "receipt": bind(RECEIPT),
                  "capacity": value["capacity"]}
    elif action == "check":
        audit(load(RECEIPT))
        result = {"status": "PASS", "capacity": derive(rebuild=False)["capacity"]}
    else:
        result = selftest()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ImplementationError, COMFORT.ComfortError, OSError, ValueError,
            KeyError, IndexError, json.JSONDecodeError,
            subprocess.CalledProcessError) as error:
        print(f"V1.5 NAME FREIGHT IMPLEMENTATION: {error}", file=sys.stderr)
        raise SystemExit(1)
