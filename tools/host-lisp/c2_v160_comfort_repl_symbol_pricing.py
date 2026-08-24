#!/usr/bin/env python3
"""Price the Comfort REPL name footprint before implementation begins."""

from __future__ import annotations

import argparse
from copy import deepcopy
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import re
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_v150_link97_symbol_capacity_attribution as CAP  # noqa: E402
import bytecode_p0_stdlib as P  # noqa: E402
import evidence_era as ERA  # noqa: E402


CONTRACT = ROOT / "config/c2-v160-comfort-repl-symbol-pricing-contract.json"
HEADROOM = ROOT / "config/release-user-headroom-contract.json"
PROFILE = ROOT / "config/workbench.mk"
CURSOR_SOURCE = ROOT / "lib/stdlib-read-line.lisp"
LIST_SOURCE = ROOT / "lib/stdlib-lists.lisp"
CURSOR_SUITE = ROOT / "tests/bytecode/libs/p0-stdlib-ship-input-wait-base.json"
CURSOR_MANIFEST = ROOT / (
    "build/c2.3/v1.6-repl-cursor-navigation/candidate/stdlib-p0.manifest.json"
)
CURSOR_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-repl-cursor-navigation-host-first-receipt.json"
)
DEVICE_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v2.1-link116-name-freight-device-receipt.json"
)
RUNTIME_REPL = ROOT / "src/repl.c"
DESIGN = ROOT / "docs/planning/extension-libraries-design.md"
PLAN = ROOT / "docs/planning/v1.6.0-freight-work-plan.md"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-comfort-repl-symbol-pricing-receipt.json"
)
FORMAT = "lisp65-c2-v160-comfort-repl-symbol-pricing-receipt-v2"
OWNER_COMMIT = "3c750a0f"
BIAS_CORRECTION_COMMIT = "88263f14"
COMFORT_SOURCE = ROOT / "lib/repl-comfort.lisp"
IMPLEMENTATION_CONTRACT = ROOT / "config/c2-v160-comfort-repl-implementation-contract.json"
PRICING_ACCEPTANCE_COMMIT = "cac1ee30"
RECEIPT_SEALED_COMMIT = (
    "2f92d46f555ad09ad5b46074cc79630d8ebb46fc")


class PricingError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise PricingError(message)


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
    raw = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(raw)
    temporary.replace(path)


def profile_integer(name: str, source: str) -> int:
    matches = re.findall(
        rf"(?:^|\s)-D{re.escape(name)}=(0x[0-9a-fA-F]+|[0-9]+)(?:\s|$)",
        source,
    )
    require(len(matches) == 1, f"profile integer authority drift: {name}")
    return int(matches[0], 0)


def resident_symbol_bytes(max_symbols: int) -> int:
    """Bank-0 arrays whose dimensions still depend on MAX_SYM."""
    return ((max_symbols + 1) // 2
            + 2 * ((max_symbols + 7) // 8))


def named_functions(suite: dict[str, Any]) -> set[str]:
    functions = suite.get("functions")
    require(isinstance(functions, list), "cursor suite function inventory absent")
    return {str(name).lower() for name in functions}


def literal_symbols(value: Any) -> list[str]:
    if isinstance(value, dict):
        if set(value) == {"symbol"} and isinstance(value["symbol"], str):
            return [value["symbol"]]
        return [name for item in value.values() for name in literal_symbols(item)]
    if isinstance(value, list):
        return [name for item in value for name in literal_symbols(item)]
    return []


def call_sites(manifest: dict[str, Any]) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    entries = manifest.get("entries")
    require(isinstance(entries, list), "cursor manifest entry inventory absent")
    for entry in entries:
        require(isinstance(entry, dict) and isinstance(entry.get("name"), str),
                "cursor manifest entry malformed")
        for target in literal_symbols(entry.get("literals", [])):
            result.setdefault(target, []).append(entry["name"])
    return result


@lru_cache(maxsize=1)
def third_helper_private_inline_probe() -> dict[str, Any]:
    suite = P._read_suite(str(CURSOR_SUITE))
    existing = list(suite.get("private_inline_functions", []))
    require("%take" not in existing, "third helper is already private-inline")
    suite["private_inline_functions"] = existing + ["%take"]
    suite["min_private_inline_functions"] = len(existing) + 1
    result = P.check_suite("comfort-pricing-%take-private-inline", suite)
    code = result["code_by_name"]
    require("%take" not in code and "butlast" in code,
            "real suite did not eliminate the third helper")
    return {
        "status": "PASS: real compiler and complete suite",
        "cases": result["cases"],
        "functions_after": result["functions"],
        "private_inline_functions_after": len(existing) + 1,
        "helper_entry_absent": True,
        "only_caller_preserved": "butlast",
    }


def current_union_excludes_repl() -> dict[str, Any]:
    manifests = [CURSOR_MANIFEST]
    rows: list[dict[str, Any]] = []
    union: set[str] = set()
    for path in manifests:
        require(path.is_file(), f"simultaneous-live manifest absent: {path}")
        names = CAP.manifest_names(path)
        union.update(names)
        rows.append({**bind(path), "canonical_names": len(names)})
    session_names = {
        "inspect", "string-extra", "defstruct", "trace-probe", "x",
        "point", "y", "make-point", "point-p", "copy-point", "point-x",
        "point-set-x", "point-with-x", "point-y", "point-set-y",
        "point-with-y", "v15-ceremony-probe", "v15-perf-probe",
    }
    union.update(session_names)
    require(not ({"repl", "repl-comfort"} & union),
            "Comfort surface is already interned")
    freight_sources = [
        ROOT / "lib/comfort-who-calls-generated.lisp",
        ROOT / "lib/inspect-trace.lisp",
        ROOT / "lib/comfort-strings.lisp",
        ROOT / "lib/stdlib-places.lisp",
        ROOT / "lib/defstruct.lisp",
    ]
    token = re.compile(r"(?<![a-z0-9%*-])repl(?:-comfort)?(?![a-z0-9%*-])",
                       re.IGNORECASE)
    source_rows: list[dict[str, Any]] = []
    for path in freight_sources:
        raw = path.read_text(encoding="utf-8")
        require(not token.search(raw),
                f"current shipped freight already names Comfort surface: {path}")
        source_rows.append(bind(path))
    return {
        "manifests": rows,
        "shipped_library_sources": source_rows,
        "session_names_checked": sorted(session_names),
        "comfort_surface_absent": True,
    }


def derive(contract: dict[str, Any]) -> dict[str, Any]:
    require(contract.get("format") == "lisp65-c2-v160-comfort-repl-symbol-pricing-v2"
            and contract.get("status") == "owner-required-bias-adjusted-pricing-only"
            and contract.get("owner_condition_commit") == OWNER_COMMIT
            and contract.get("owner_bias_correction_commit")
                == BIAS_CORRECTION_COMMIT,
            "pricing contract identity drift")
    try:
        ERA.era_blob(PRICING_ACCEPTANCE_COMMIT, "lib/repl-comfort.lisp")
    except ERA.EraError:
        pass
    else:
        raise PricingError("Comfort source existed in the accepted pricing era")
    require(COMFORT_SOURCE.is_file() and IMPLEMENTATION_CONTRACT.is_file(),
            "authorized Comfort successor is incomplete")
    implementation = load(IMPLEMENTATION_CONTRACT)
    require(
        implementation.get("format")
            == "lisp65-c2-v160-comfort-repl-implementation-v1"
        and implementation.get("pricing_acceptance_commit")
            == PRICING_ACCEPTANCE_COMMIT,
        "Comfort successor is not descended from the accepted pricing",
    )

    cursor = load(CURSOR_RECEIPT)
    device = load(DEVICE_RECEIPT)
    headroom = load(HEADROOM)
    suite = load(CURSOR_SUITE)
    cursor_manifest = load(CURSOR_MANIFEST)
    source = ERA.era_blob(
        PRICING_ACCEPTANCE_COMMIT,
        CURSOR_SOURCE.relative_to(ROOT).as_posix(),
    ).decode("utf-8")
    list_source = LIST_SOURCE.read_text(encoding="utf-8")
    repl_c = RUNTIME_REPL.read_text(encoding="utf-8")
    profile = PROFILE.read_text(encoding="utf-8")

    baseline = contract["baseline"]
    minimum = headroom["minimum_free"]
    calibration = baseline["calibration"]
    device_projection = device["pricing_projection_delta"]
    measured_bias = device_projection["delta"]
    require(baseline["projected_free"] == cursor["source_contract"]["d5_projected"]
            == {"symbol_slots": 32, "namepool_bytes": 562}
            and minimum == baseline["release_minimum_free"]
                == {"symbol_slots": 32, "namepool_bytes": 384}
            and calibration["v15_host_projected_free"]
                == device_projection["projected_free"]
                == {"symbol_slots": 35, "namepool_bytes": 549}
            and calibration["v15_hardware_observed_free"]
                == device_projection["observed_free"]
                == {"symbol_slots": 34, "namepool_bytes": 545}
            and calibration["measured_projection_bias"] == measured_bias
                == {"symbol_slots": -1, "namepool_bytes": -4}
            and calibration["required_projected_free"]
                == {"symbol_slots": 33, "namepool_bytes": 388}
            and device["D5_user_headroom"]["free"]
                == {"symbol_slots": 34, "namepool_bytes": 545},
            "D5 baseline/floor/bias authority drift")
    require(headroom["release_policy"]["failure_is_release_terminal"] is True,
            "release-terminal headroom rule was weakened")
    max_symbols = profile_integer("MAX_SYM", profile)
    namepool = profile_integer("NAMEPOOL", profile)
    require((max_symbols, namepool) == (752, 10208),
            "Workbench symbol geometry drift")

    activation = contract["activation_contract"]
    require(activation["canonical_new_names"] == ["repl", "repl-comfort"]
            and activation["library_designator"] == "repl-comfort"
            and activation["public_entry"] == "repl"
            and activation["priced_named_private_helpers"] == 0
            and activation["additional_named_helpers_require_repricing"] is True,
            "minimal Comfort activation identity drift")
    require("static uint8_t read_line(" in repl_c
            and "st = read_line(buf, &n, BUF_MAX);" in repl_c,
            "native REPL no longer owns its direct C input path")
    require("vm_run_dir" not in repl_c[repl_c.index("st = read_line"):][:300],
            "native REPL unexpectedly dispatches line input through Lisp")
    union = current_union_excludes_repl()

    options = contract["options"]
    reclamation = options["reclaim_three_single_use_helpers"]
    helpers = reclamation["helpers"]
    require(helpers == ["%rl-dispatch", "%rl-put", "%take"],
            "reclamation candidate drift")
    require(reclamation["third_helper"] == {
        "name": "%take",
        "only_caller": "butlast",
        "source": "lib/stdlib-lists.lisp",
        "private_inline_real_suite_required": True,
    }, "third helper contract drift")
    functions = named_functions(suite)
    for helper in helpers[:2]:
        require(helper in functions
                and source.count(f"({helper} ") == 1
                and helper not in suite.get("tailcall_self", []),
                f"cursor helper is not a single-use inline candidate: {helper}")
    sites = call_sites(cursor_manifest)
    require(list_source.count("(defun %take ") == 1
            and sites.get("%take") == ["butlast"]
            and "%take" not in cursor_manifest.get("private_inline_functions", []),
            "third helper is not a single-call private-inline candidate")
    third_probe = third_helper_private_inline_probe()
    require(third_probe["cases"]
                == implementation["gates"]["real_workbench_cases"] == 248
            and len(cursor_manifest["cases"]) in (247, 248)
            and third_probe["functions_after"]
                == len(cursor_manifest["functions"]) - 1
            and third_probe["private_inline_functions_after"]
                == len(cursor_manifest["private_inline_functions"]) + 1,
            "third helper real-suite proof drift")
    reclaimed_name_bytes = sum(len(name.encode("ascii")) + 1 for name in helpers)
    comfort_names = set(activation["canonical_new_names"])
    comfort_name_bytes = sum(len(name) + 1 for name in comfort_names)
    require((reclaimed_name_bytes, comfort_name_bytes) == (27, 18),
            "NUL-inclusive name price drift")

    projected = baseline["projected_free"]
    minimum_slots = minimum["symbol_slots"]
    minimum_names = minimum["namepool_bytes"]
    no_reclaim = {
        "symbol_slots": projected["symbol_slots"] - len(comfort_names),
        "namepool_bytes": projected["namepool_bytes"] - comfort_name_bytes,
    }
    two_reclaim_name_bytes = sum(len(name) + 1 for name in helpers[:2])
    two_reclaims = {
        "symbol_slots": projected["symbol_slots"] + 2 - len(comfort_names),
        "namepool_bytes": (projected["namepool_bytes"]
                           + two_reclaim_name_bytes - comfort_name_bytes),
    }
    selected = {
        "symbol_slots": projected["symbol_slots"] + 3 - len(comfort_names),
        "namepool_bytes": (projected["namepool_bytes"]
                           + reclaimed_name_bytes - comfort_name_bytes),
    }
    one_name = {
        "symbol_slots": projected["symbol_slots"] + 3 - 1,
        "namepool_bytes": projected["namepool_bytes"] + reclaimed_name_bytes - 5,
    }
    def bias_adjust(row: dict[str, int]) -> dict[str, int]:
        return {key: row[key] + measured_bias[key] for key in row}

    no_reclaim_device = bias_adjust(no_reclaim)
    two_reclaims_device = bias_adjust(two_reclaims)
    selected_device = bias_adjust(selected)
    one_name_device = bias_adjust(one_name)
    require(no_reclaim == {"symbol_slots": 30, "namepool_bytes": 544}
            and no_reclaim_device == {"symbol_slots": 29, "namepool_bytes": 540}
            and two_reclaims == {"symbol_slots": 32, "namepool_bytes": 565}
            and two_reclaims_device
                == {"symbol_slots": 31, "namepool_bytes": 561}
            and selected == {"symbol_slots": 33, "namepool_bytes": 571}
            and selected_device == {"symbol_slots": 32, "namepool_bytes": 567}
            and one_name == {"symbol_slots": 34, "namepool_bytes": 584}
            and one_name_device == {"symbol_slots": 33, "namepool_bytes": 580}
            and two_reclaims_device["symbol_slots"] < minimum_slots
            and selected_device["symbol_slots"] - minimum_slots == 0
            and selected_device["namepool_bytes"] - minimum_names == 183,
            "Comfort/reclamation price arithmetic drift")

    raised = max_symbols + 3
    bank0_delta = resident_symbol_bytes(raised) - resident_symbol_bytes(max_symbols)
    bank5_delta = (raised - max_symbols) * 6
    margin_raised = max_symbols + 4
    margin_bank0_delta = (
        resident_symbol_bytes(margin_raised) - resident_symbol_bytes(max_symbols)
    )
    margin_bank5_delta = (margin_raised - max_symbols) * 6
    require((raised, bank0_delta, bank5_delta,
             margin_raised, margin_bank0_delta, margin_bank5_delta)
            == (755, 4, 18, 756, 4, 24),
            "MAX_SYM alternative price drift")

    require(options["zero_new_symbols"]["viable"] is False
            and options["standing_surface_without_reclamation"]["projected_free"]
                == no_reclaim
            and options["standing_surface_without_reclamation"]["bias_adjusted_free"]
                == no_reclaim_device
            and options["standing_surface_without_reclamation"]["meets_release_contract"]
                is False
            and options["two_helper_predecessor"]["projected_free_after_comfort"]
                == two_reclaims
            and options["two_helper_predecessor"][
                "bias_adjusted_free_after_comfort"] == two_reclaims_device
            and options["two_helper_predecessor"]["meets_release_contract"] is False
            and options["reclaim_three_single_use_helpers"][
                "projected_free_after_comfort"] == selected
            and options["reclaim_three_single_use_helpers"][
                "bias_adjusted_free_after_comfort"] == selected_device
            and options["reclaim_three_single_use_helpers"][
                "reclaimed_symbol_slots"] == 3
            and options["reclaim_three_single_use_helpers"][
                "reclaimed_namepool_bytes"] == reclaimed_name_bytes
            and options["reclaim_three_single_use_helpers"][
                "comfort_new_symbol_slots"] == len(comfort_names)
            and options["reclaim_three_single_use_helpers"][
                "comfort_new_namepool_bytes"] == comfort_name_bytes
            and options["reclaim_three_single_use_helpers"]["selected"] is True
            and options["one_name_convergence"] == {
                "selected": False,
                "canonical_name": "repl",
                "projected_free_after_three_reclaims": one_name,
                "bias_adjusted_free_after_three_reclaims": one_name_device,
                "reason": (
                    "restores one measured slot of margin but changes the standing "
                    "public library designator and requires owner approval"
                ),
            }
            and options["raise_max_sym"]["selected"] is False
            and options["raise_max_sym"]["minimum_raise_to_bias_adjusted_floor"] == 3
            and options["raise_max_sym"]["structural_bank0_array_delta_bytes"]
                == bank0_delta
            and options["raise_max_sym"]["minimum_raise_for_one_measured_slot_margin"]
                == 4
            and options["raise_max_sym"][
                "one_margin_structural_bank0_array_delta_bytes"] == margin_bank0_delta
            and options["raise_max_sym"]["one_margin_bank5_table_delta_bytes"]
                == margin_bank5_delta,
            "priced decision table drift")
    require(contract["walls"] == {
        "comfort_source_must_be_absent_during_pricing": True,
        "hardware_runs": 0,
        "product_links": 0,
        "do_not_lower_release_floor": True,
        "do_not_erase_measured_bias": True,
        "do_not_raise_max_sym": True,
        "do_not_relabel_private_helpers_as_public": True,
        "device_d5_required_before_release": True,
    }, "pricing wall drift")

    return {
        "baseline_projected_free": projected,
        "release_minimum_free": minimum,
        "calibration": calibration,
        "activation": {
            "new_canonical_names": sorted(comfort_names),
            "library_designator_equals_public_entry": False,
            "zero_symbol_form_viable": False,
            "reason": "native C REPL owns a direct static read_line call",
        },
        "successor": {
            "status": "authorized implementation follows accepted pricing",
            "pricing_acceptance_commit": PRICING_ACCEPTANCE_COMMIT,
            "historical_comfort_source_absent": True,
            "live_implementation_contract": bind(IMPLEMENTATION_CONTRACT),
        },
        "current_union": union,
        "options": {
            "standing_surface_without_reclamation": no_reclaim,
            "standing_surface_without_reclamation_bias_adjusted": no_reclaim_device,
            "two_helpers_reclaimed_then_standing_surface": two_reclaims,
            "two_helpers_bias_adjusted": two_reclaims_device,
            "three_helpers_reclaimed_then_standing_surface": selected,
            "three_helpers_bias_adjusted": selected_device,
            "one_name_owner_variant": one_name,
            "one_name_owner_variant_bias_adjusted": one_name_device,
            "raise_MAX_SYM_by_3": {
                "resulting_symbol_slots": 33,
                "structural_bank0_array_delta_bytes": bank0_delta,
                "bank5_table_delta_bytes": bank5_delta,
                "selected": False,
            },
            "raise_MAX_SYM_by_4_for_one_measured_slot_margin": {
                "resulting_symbol_slots": 34,
                "structural_bank0_array_delta_bytes": margin_bank0_delta,
                "bank5_table_delta_bytes": margin_bank5_delta,
                "selected": False,
            },
        },
        "selected": {
            "reclaim": helpers,
            "reclaimed_symbol_slots": 3,
            "reclaimed_namepool_bytes": reclaimed_name_bytes,
            "comfort_new_symbol_slots": len(comfort_names),
            "comfort_new_namepool_bytes": comfort_name_bytes,
            "projected_free_after_comfort": selected,
            "bias_adjusted_free_after_comfort": selected_device,
            "bias_adjusted_margin_above_release_minimum": {
                "symbol_slots": 0,
                "namepool_bytes": 183,
            },
            "third_helper_real_suite_proof": third_probe,
            "implementation_wall": (
                "eliminate both single-use cursor helpers with cursor equivalence "
                "and allocation gates unchanged; private-inline %take through the "
                "real suite; any named Comfort helper triggers capacity repricing"
            ),
        },
    }


def mutations(contract: dict[str, Any]) -> dict[str, str]:
    rows: list[tuple[str, dict[str, Any]]] = []

    def changed(label: str, path: list[str], value: Any) -> None:
        candidate = deepcopy(contract)
        cursor: Any = candidate
        for key in path[:-1]:
            cursor = cursor[key]
        cursor[path[-1]] = value
        rows.append((label, candidate))

    changed("lower-symbol-floor", ["baseline", "release_minimum_free", "symbol_slots"], 31)
    changed("invent-zero-symbol-entry", ["options", "zero_new_symbols", "viable"], True)
    changed("collapse-public-surface-without-owner", ["activation_contract", "library_designator"], "repl")
    changed("erase-slot-bias", ["baseline", "calibration", "measured_projection_bias", "symbol_slots"], 0)
    changed("erase-name-bias", ["baseline", "calibration", "measured_projection_bias", "namepool_bytes"], 0)
    changed("lower-required-projection", ["baseline", "calibration", "required_projected_free", "symbol_slots"], 32)
    changed("hide-helper-repricing", ["activation_contract", "additional_named_helpers_require_repricing"], False)
    changed("reclaim-only-two", ["options", "reclaim_three_single_use_helpers", "helpers"], ["%rl-dispatch", "%rl-put"])
    changed("invent-third-helper-caller", ["options", "reclaim_three_single_use_helpers", "third_helper", "only_caller"], "%rl-dispatch")
    changed("drop-NUL-cost", ["options", "reclaim_three_single_use_helpers", "reclaimed_namepool_bytes"], 26)
    changed("select-MAX-SYM", ["options", "raise_max_sym", "selected"], True)
    changed("hide-resident-cost", ["options", "raise_max_sym", "structural_bank0_array_delta_bytes"], 0)
    changed("claim-hardware", ["walls", "hardware_runs"], 1)
    changed("skip-device-D5", ["walls", "device_d5_required_before_release"], False)
    changed("select-one-name-without-owner", ["options", "one_name_convergence", "selected"], True)

    rejected: dict[str, str] = {}
    for label, candidate in rows:
        try:
            derive(candidate)
        except PricingError as exc:
            rejected[label] = str(exc)
        else:
            raise PricingError(f"pricing mutation survived: {label}")
    require(len(rejected) == 15, "pricing mutation count drift")
    return rejected


def run_selftest() -> dict[str, Any]:
    contract = load(CONTRACT)
    base = derive(contract)
    rejected = mutations(contract)
    return {"derived": base, "mutations_rejected": rejected}


def run_check() -> dict[str, Any]:
    value = load(RECEIPT)
    require(
        RECEIPT.read_bytes() == ERA.era_blob(
            RECEIPT_SEALED_COMMIT, RECEIPT.relative_to(ROOT).as_posix()),
        "historical pricing receipt was regenerated",
    )
    require(
        value.get("format") == FORMAT
        and value.get("result", {}).get("selected", {}).get(
            "bias_adjusted_free_after_comfort")
            == {"symbol_slots": 32, "namepool_bytes": 567}
        and value.get("result", {}).get("calibration", {}).get(
            "measured_projection_bias")
            == {"symbol_slots": -1, "namepool_bytes": -4}
        and value.get("result", {}).get("release_minimum_free")
            == {"symbol_slots": 32, "namepool_bytes": 384}
        and len(value.get("mutations_rejected", {})) == 15
        and value.get("next")
            == "historical pricing remains sealed; live implementation owns its repriced gate",
        "sealed pricing witness no longer describes its own accepted era",
    )
    return value


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("selftest", "check"))
    args = parser.parse_args(argv)
    value = run_selftest() if args.command == "selftest" else run_check()
    selected = value.get("derived", value.get("result", {})).get("selected", {})
    projected = selected.get("projected_free_after_comfort", {})
    adjusted = selected.get("bias_adjusted_free_after_comfort", {})
    print(
        "c2-v160-comfort-repl-symbol-pricing: PASS "
        f"mutations=15 selected=reclaim-3/add-2 "
        f"projected={projected.get('symbol_slots')}/{projected.get('namepool_bytes')} "
        f"bias-adjusted={adjusted.get('symbol_slots')}/{adjusted.get('namepool_bytes')} "
        "resident=+0 implementation=authorized-successor"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
