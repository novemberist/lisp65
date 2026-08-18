#!/usr/bin/env python3
"""Price v1.5 name freight and enforce the release user-headroom contract.

This tool does not build a product or choose a fix.  It reconstructs the
simultaneously-live Link-97/D5 symbol set, prices the three commissioned
levers, and makes the already-owned Workbench headroom floors release
terminal.  Its optional device verifier reads nsym/npool from one physical
Bank-0 capture at ELF-derived addresses; it never interns a diagnostic name.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

CAPACITY_PATH = HOST / "c2_v150_link97_symbol_capacity_attribution.py"
SPEC = importlib.util.spec_from_file_location("c2_v150_capacity", CAPACITY_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load Link-97 capacity authority")
CAP = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = CAP
SPEC.loader.exec_module(CAP)

from elf_truth import ElfTruth, ElfTruthError  # noqa: E402


PLAN = ROOT / "docs/planning/v1.5.0-release-work-plan.md"
WORKBENCH = ROOT / "config/workbench.mk"
CONTRACT = ROOT / "config/release-user-headroom-contract.json"
ROWS = ROOT / "config/c2-v150-link97-device-rows.json"
FIRST_RED = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.5.0-link97-d3-symbol-capacity-first-red.json")
STATIC_EXT = ROOT / (
    "build/c2.3/v1.5.0-candidate-product-link97/static-plane/"
    "narrow-static/stdlib-p0.manifest.json")
ELF = ROOT / (
    "build/c2.3/v1.5.0-candidate-product-link97/final/"
    "lisp65-c2-substitution-linked.prg.elf")
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.5.0-name-freight-pricing-receipt.json")
DRIVER = Path(__file__).resolve()
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"

FORMAT = "lisp65-c2.3-v1.5.0-name-freight-pricing-v1"
OWNER_COMMIT = "7526d1e7"
PLAN_PATH = "docs/planning/v1.5.0-release-work-plan.md"
SLOT_TABLE_BYTES = 6


class PricingError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise PricingError(message)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"authority absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": sha(raw)}


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def git_bind(commit: str, path: str) -> dict[str, Any]:
    full = subprocess.run(
        ["git", "rev-parse", f"{commit}^{{commit}}"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE).stdout.decode().strip()
    raw = subprocess.run(
        ["git", "show", f"{full}:{path}"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE).stdout
    return {"commit": full, "path": path, "bytes": len(raw), "sha256": sha(raw)}


def mk_int(name: str) -> int:
    source = WORKBENCH.read_text(encoding="utf-8")
    matches = re.findall(rf"^(?:\s*-D)?{re.escape(name)}\s*(?::=|=)\s*(0x[0-9a-fA-F]+|[0-9]+)",
                         source, re.MULTILINE)
    require(len(matches) == 1, f"Workbench integer authority drift: {name}")
    return int(matches[0], 0)


def cold_link97_names() -> set[str]:
    link92, used = CAP.pool_names(CAP.LINK92_POOL)
    require(len(link92) == 690 and used == 9646,
            "Link-92 physical symbol authority drift")
    static92 = CAP.static_names(CAP.load(CAP.LINK92_STATIC))
    static97 = CAP.static_names(CAP.load(CAP.LINK97_STATIC))
    old_library = CAP.manifest_names(CAP.OLD_INSPECT) | CAP.manifest_names(
        CAP.STRING_EXTRA)
    session_only = (old_library - static92) | {"inspect", "string-extra"}
    base92 = link92 - session_only
    result = (base92 - (static92 - static97)) | (static97 - static92)
    require(len(result) == 636 and CAP.name_bytes(result) == 8681,
            "Link-97 cold symbol reconstruction drift")
    return result


def symbol_nodes(value: Any) -> set[str]:
    result: set[str] = set()
    if isinstance(value, dict):
        symbol = value.get("symbol")
        if isinstance(symbol, str):
            result.add(symbol.lower())
        for key, child in value.items():
            if key != "symbol":
                result.update(symbol_nodes(child))
    elif isinstance(value, list):
        for child in value:
            result.update(symbol_nodes(child))
    return result


def alias_char(index: int) -> str:
    alphabet = "0123456789abcdefghijklmnopqrstuvwxyz"
    require(0 <= index < len(alphabet), "private alias domain exceeds one digit")
    return alphabet[index]


def private_group(manifest: dict[str, Any], prefix: str,
                  extra: set[str]) -> dict[str, str]:
    private = sorted({str(name).lower() for name in manifest["functions"]
                      if str(name).startswith("%")} | extra)
    aliases = {name: f"%{prefix}{alias_char(index)}"
               for index, name in enumerate(private)}
    require(len(set(aliases.values())) == len(private), "private alias collision")
    return aliases


def renamed(names: set[str], mapping: dict[str, str]) -> set[str]:
    require(set(mapping) <= names, "short-name candidate contains an absent source name")
    require(not (set(mapping.values()) & (names - set(mapping))),
            "short-name candidate collides with a retained name")
    result = (names - set(mapping)) | set(mapping.values())
    require(len(result) == len(names), "short-name candidate changed symbol count")
    return result


def capacity(names: set[str], max_symbols: int, namepool: int) -> dict[str, int]:
    used = CAP.name_bytes(names)
    return {"symbols": len(names), "namepool_bytes": used,
            "symbol_headroom": max_symbols - len(names),
            "namepool_headroom": namepool - used}


def fits(row: dict[str, int], floors: dict[str, int]) -> bool:
    return (row["symbol_headroom"] >= floors["symbol_slots"]
            and row["namepool_headroom"] >= floors["namepool_bytes"])


def derive() -> dict[str, Any]:
    contract = load(CONTRACT)
    rows = load(ROWS)
    first_red = load(FIRST_RED)
    inspect = load(CAP.INSPECT)
    place = load(CAP.PLACE)
    defstruct = load(CAP.DEFSTRUCT)
    string_extra = load(CAP.STRING_EXTRA)
    static_ext = load(STATIC_EXT)

    max_symbols = mk_int("MAX_SYM")
    namepool = mk_int("NAMEPOOL")
    sympool_off = mk_int("SYMPOOL_EXT_OFF")
    floors = contract["minimum_free"]
    require(contract["status"] == "mandatory"
            and floors == {"namepool_bytes": 384, "symbol_slots": 32}
            and floors["symbol_slots"] == mk_int("WORKBENCH_MIN_SYMBOL_HEADROOM")
            and floors["namepool_bytes"] == mk_int("WORKBENCH_MIN_NAMEPOOL_HEADROOM"),
            "user-headroom contract no longer matches owned Workbench floors")
    require(max_symbols == 752 and namepool == 10208 and sympool_off == 0xC680,
            "Link-97 symbol geometry drift")

    cold = cold_link97_names()
    shipped = (cold | {"inspect"} | CAP.manifest_names(CAP.INSPECT)
               | {"string-extra"} | CAP.manifest_names(CAP.STRING_EXTRA)
               | CAP.manifest_names(CAP.PLACE) | {"defstruct"}
               | CAP.manifest_names(CAP.DEFSTRUCT))
    trace_fixture = {"trace-probe", "x"}
    d5_names = {
        "point", "y", "make-point", "point-p", "copy-point", "point-x",
        "point-set-x", "point-with-x", "point-y", "point-set-y",
        "point-with-y", "v15-ceremony-probe", "v15-perf-probe",
    }
    row_by_id = {row["id"]: row["form"] for row in rows["rows"]}
    require(row_by_id["d2-define-probe"] == "(defun trace-probe (x) (+ x 1))"
            and row_by_id["d3-define-point"] == "(defstruct point x y)"
            and row_by_id["d4-durable-ceremony"]
                == "(setq v15-ceremony-probe 1)"
            and row_by_id["d5-setup-published-call"]
                == "(defun v15-perf-probe (x) (+ x 1))",
            "D2-D5 session-created-name authority drift")
    final_names = shipped | trace_fixture | d5_names
    current = capacity(final_names, max_symbols, namepool)
    require(current == {"symbols": 767, "namepool_bytes": 10964,
                        "symbol_headroom": -15, "namepool_headroom": -756},
            "full D5 simultaneous-live capacity drift")

    groups = {
        "inspect": private_group(inspect, "i", {"*inspect-trace-bindings*"}),
        "place": private_group(place, "p", {
            "*setf-place-open*", "*setf-place-pending*",
            "*setf-place-registry*"}),
        "defstruct": private_group(defstruct, "d", {"value", "new-value"}),
        "string_extra": private_group(string_extra, "s", set()),
    }
    require({name: len(mapping) for name, mapping in groups.items()} == {
        "inspect": 11, "place": 14, "defstruct": 22, "string_extra": 1},
        "private-name inventory drift")
    all_aliases = {old: new for mapping in groups.values()
                   for old, new in mapping.items()}
    require(len(all_aliases) == 48, "private short-name union drift")
    short_all_names = renamed(final_names, all_aliases)
    short_all = capacity(short_all_names, max_symbols, namepool)
    short_saving = CAP.name_bytes(set(all_aliases)) - CAP.name_bytes(
        set(all_aliases.values()))
    require(short_saving == 778 and short_all == {
        "symbols": 767, "namepool_bytes": 10186,
        "symbol_headroom": -15, "namepool_headroom": 22,
    }, "short-name price drift")

    callers_symbols = symbol_nodes(inspect["entries"][0]["literals"])
    remaining_inspect_symbols = (symbol_nodes(inspect["entries"][1:])
                                 | {str(name).lower()
                                    for name in inspect["functions"]})
    lazy_names = callers_symbols - cold
    require(len(callers_symbols) == 60 and len(lazy_names) == 50
            and CAP.name_bytes(lazy_names) == 946
            and not (lazy_names & remaining_inspect_symbols),
            "who-calls scoped metadata inventory drift")
    scoped_names = final_names - lazy_names
    scoped = capacity(scoped_names, max_symbols, namepool)
    require(scoped == {"symbols": 717, "namepool_bytes": 10018,
                       "symbol_headroom": 35, "namepool_headroom": 190},
            "scoped-interning price drift")

    scoped_short_all_names = renamed(scoped_names, all_aliases)
    scoped_short_all = capacity(scoped_short_all_names, max_symbols, namepool)
    defstruct_aliases = groups["defstruct"]
    scoped_short_defstruct_names = renamed(scoped_names, defstruct_aliases)
    scoped_short_defstruct = capacity(scoped_short_defstruct_names,
                                      max_symbols, namepool)
    scoped_short_place = capacity(renamed(scoped_names, groups["place"]),
                                  max_symbols, namepool)
    require(scoped_short_all == {
        "symbols": 717, "namepool_bytes": 9240,
        "symbol_headroom": 35, "namepool_headroom": 968,
    } and scoped_short_defstruct == {
        "symbols": 717, "namepool_bytes": 9651,
        "symbol_headroom": 35, "namepool_headroom": 557,
    } and scoped_short_place == {
        "symbols": 717, "namepool_bytes": 9820,
        "symbol_headroom": 35, "namepool_headroom": 388,
    }, "combined lever price drift")

    required_symbols = current["symbols"] + floors["symbol_slots"]
    required_namepool = current["namepool_bytes"] + floors["namepool_bytes"]
    slot_delta = required_symbols - max_symbols
    name_delta = required_namepool - namepool
    footprint_delta = name_delta + slot_delta * SLOT_TABLE_BYTES
    image_bytes = static_ext["external_image"]["bytes"]
    current_gap = sympool_off - image_bytes
    moved_off = sympool_off - footprint_delta
    require((required_symbols, required_namepool, slot_delta, name_delta,
             footprint_delta, moved_off, current_gap - footprint_delta)
            == (799, 11348, 47, 1140, 1422, 0xC0F2, 14955),
            "arena-growth geometry price drift")

    lever_rows = {
        "current_full_D5": {**current, "meets_contract": fits(current, floors)},
        "short_all_private_names": {
            **short_all, "meets_contract": fits(short_all, floors),
            "name_bytes_saved": short_saving, "symbols_saved": 0},
        "scoped_who_calls_metadata": {
            **scoped, "meets_contract": fits(scoped, floors),
            "name_bytes_saved": 946, "symbols_saved": 50},
        "scoped_plus_short_place": {
            **scoped_short_place,
            "meets_contract": fits(scoped_short_place, floors),
            "margin_above_floor": {"symbol_slots": 3, "namepool_bytes": 4}},
        "scoped_plus_short_defstruct": {
            **scoped_short_defstruct,
            "meets_contract": fits(scoped_short_defstruct, floors),
            "margin_above_floor": {"symbol_slots": 3, "namepool_bytes": 173}},
        "scoped_plus_short_all_private_names": {
            **scoped_short_all,
            "meets_contract": fits(scoped_short_all, floors),
            "margin_above_floor": {"symbol_slots": 3, "namepool_bytes": 584}},
    }
    require(not lever_rows["short_all_private_names"]["meets_contract"]
            and not lever_rows["scoped_who_calls_metadata"]["meets_contract"]
            and lever_rows["scoped_plus_short_defstruct"]["meets_contract"],
            "lever decision table drift")
    require(first_red["status"] == "D3-NAMEPOOL-EXHAUSTION-ATTRIBUTED",
            "First Red authority drift")

    return {
        "format": FORMAT,
        "recorded_on": "2026-08-11",
        "status": "PRICED-COMBINED-LIBRARY-FORM-RECOMMENDED-RELEASE-BLOCKED",
        "authority": {
            "owner_commission": git_bind(OWNER_COMMIT, PLAN_PATH),
            "first_red": bind(FIRST_RED), "contract": bind(CONTRACT),
            "workbench_profile": bind(WORKBENCH), "device_rows": bind(ROWS),
            "capacity_reconstructor": bind(CAPACITY_PATH),
            "inspect": bind(CAP.INSPECT), "string_extra": bind(CAP.STRING_EXTRA),
            "place": bind(CAP.PLACE), "defstruct": bind(CAP.DEFSTRUCT),
            "static_external_image": bind(STATIC_EXT), "candidate_ELF": bind(ELF),
            "checker": bind(DRIVER),
        },
        "contract": {
            "minimum_free": floors,
            "scope": contract["release_policy"]["scope"],
            "union_rule": contract["release_policy"]["union_rule"],
            "NUL_terminator_included_per_name": True,
            "release_terminal": True,
            "D5_measurement": contract["d5_measurement"],
        },
        "simultaneous_live": {
            "cold_Link97": capacity(cold, max_symbols, namepool),
            "shipped_roles_before_session_names": capacity(
                shipped, max_symbols, namepool),
            "trace_fixture_names": sorted(trace_fixture),
            "post_D2_session_names": sorted(d5_names),
            "final_D5": current,
        },
        "lever_1_short_internal_names": {
            "groups": {
                name: {"renamed": len(mapping),
                       "old_name_bytes": CAP.name_bytes(set(mapping)),
                       "new_name_bytes": CAP.name_bytes(set(mapping.values())),
                       "saved_name_bytes": (CAP.name_bytes(set(mapping))
                                            - CAP.name_bytes(set(mapping.values()))),
                       "mapping": mapping}
                for name, mapping in groups.items()
            },
            "total_private_names": len(all_aliases),
            "total_name_bytes_saved": short_saving,
            "result": lever_rows["short_all_private_names"],
            "decision": "does not satisfy either the slot fit or user floors alone",
        },
        "lever_2_scoped_interning": {
            "owner": "%comfort-callers-index / who-calls metadata",
            "all_nested_names": len(callers_symbols),
            "cold_names_reused": len(callers_symbols & cold),
            "eager_only_names": sorted(lazy_names),
            "eager_only_symbols": len(lazy_names),
            "eager_only_name_bytes": CAP.name_bytes(lazy_names),
            "implementation_shape": (
                "keep the callers index noninterned and intern query/result names only "
                "when who-calls is invoked"),
            "result": lever_rows["scoped_who_calls_metadata"],
            "decision": "raw freight fits but the name-byte user floor fails alone",
        },
        "lever_3_arena_placement": {
            "current": {"MAX_SYM": max_symbols, "NAMEPOOL": namepool,
                        "SYMPOOL_EXT_OFF": f"0x{sympool_off:04X}",
                        "slot_table_bytes_per_symbol": SLOT_TABLE_BYTES},
            "fit_with_contract_requires": {
                "MAX_SYM": required_symbols, "NAMEPOOL": required_namepool,
                "additional_symbol_slots": slot_delta,
                "additional_namepool_bytes": name_delta,
                "same_bank_footprint_delta_bytes": footprint_delta,
                "moved_SYMPOOL_EXT_OFF": f"0x{moved_off:04X}"},
            "external_image_extent": {
                "bytes": image_bytes, "current_gap_to_pool": current_gap,
                "gap_after_growth": current_gap - footprint_delta,
                "configured_post_headroom_floor": mk_int(
                    "WORKBENCH_MIN_EXT_CODE_POST_HEADROOM")},
            "decision": (
                "not a local constant change: honest growth consumes 1422 bytes "
                "of the protected Bank-5 code-to-pool interval and requires an "
                "owned placement architecture"),
        },
        "decision_table": lever_rows,
        "recommendation": {
            "form": "scoped who-calls metadata plus short private defstruct names",
            "reason": (
                "the narrowest combined form with nontrivial name-byte margin; "
                "place-only shortening passes by just four bytes above the floor"),
            "projected_final_D5": scoped_short_defstruct,
            "release_reopened": False,
            "next_authority": (
                "implementation and semantic gates for both library changes, then "
                "fresh freight pricing; only that result may reopen D3"),
        },
        "execution_accounting": {"product_bytes_changed": 0, "product_links": 0,
                                 "media_builds": 0, "device_contacts": 0},
        "claim_limit": (
            "This receipt prices candidate forms and establishes the permanent "
            "user-headroom gate. It does not implement a library change, alter "
            "symbol geometry, descope freight, rebuild media, retry D3, run D4/D5, "
            "or reopen the v1.5 release."),
    }


def audit(value: dict[str, Any]) -> None:
    require(value == derive(), "name-freight receipt differs from derivation")


def set_path(value: dict[str, Any], path: list[str], replacement: Any) -> None:
    cursor: Any = value
    for key in path[:-1]:
        cursor = cursor[key]
    cursor[path[-1]] = replacement


def selftest() -> dict[str, Any]:
    base = derive()
    cases: list[tuple[str, list[str], Any]] = [
        ("lower-symbol-floor", ["contract", "minimum_free", "symbol_slots"], 0),
        ("lower-name-floor", ["contract", "minimum_free", "namepool_bytes"], 0),
        ("drop-NUL-cost", ["contract", "NUL_terminator_included_per_name"], False),
        ("per-package-fit", ["contract", "union_rule"], "each package fits"),
        ("omit-D5-name", ["simultaneous_live", "post_D2_session_names"], []),
        ("short-only-pass", ["decision_table", "short_all_private_names",
                             "meets_contract"], True),
        ("scoped-only-pass", ["decision_table", "scoped_who_calls_metadata",
                              "meets_contract"], True),
        ("omit-scoped-name", ["lever_2_scoped_interning", "eager_only_symbols"], 49),
        ("ignore-slot-tables", ["lever_3_arena_placement",
                                "fit_with_contract_requires",
                                "same_bank_footprint_delta_bytes"], 1140),
        ("hardcode-D5-address", ["contract", "D5_measurement",
                                 "forbid_hardcoded_historical_addresses"], False),
        ("REPL-D5-probe", ["contract", "D5_measurement",
                           "forbid_public_repl_introspection"], False),
        ("pre-D5-stop", ["contract", "D5_measurement", "observation_point"],
         "before D5"),
        ("reopen-release", ["recommendation", "release_reopened"], True),
        ("claim-fix", ["execution_accounting", "product_bytes_changed"], 1),
    ]
    rejected: dict[str, str] = {}
    for name, path, replacement in cases:
        trial = deepcopy(base)
        set_path(trial, path, replacement)
        try:
            audit(trial)
        except PricingError as error:
            rejected[name] = str(error)
        else:
            raise PricingError(f"mutation survived: {name}")
    require(len(rejected) == len(cases), "headroom mutation count drift")
    return {"status": "SELFTEST PASS", "mutations": len(rejected),
            "recommended_symbol_headroom": base["recommendation"]
                ["projected_final_D5"]["symbol_headroom"],
            "recommended_namepool_headroom": base["recommendation"]
                ["projected_final_D5"]["namepool_headroom"],
            "rejected": rejected}


def elf_symbol_addresses(elf: Path) -> dict[str, int]:
    require(elf.is_file(), f"candidate ELF absent: {elf}")
    truth = ElfTruth.read(elf, llvm_readobj=READOBJ)
    return {name: truth.symbol(name).value for name in ("nsym", "npool")}


def verify_device(elf: Path, bank0: Path) -> dict[str, Any]:
    contract = load(CONTRACT)
    raw = bank0.read_bytes()
    require(len(raw) >= 0xC000, "physical Bank-0 capture is incomplete")
    addresses = elf_symbol_addresses(elf)
    require(all(0 <= address <= len(raw) - 2 for address in addresses.values()),
            "ELF counter lies outside physical Bank-0 capture")
    observed = {name: int.from_bytes(raw[address:address + 2], "little")
                for name, address in addresses.items()}
    limits = {"symbols": mk_int("MAX_SYM"), "namepool_bytes": mk_int("NAMEPOOL")}
    free = {"symbol_slots": limits["symbols"] - observed["nsym"],
            "namepool_bytes": limits["namepool_bytes"] - observed["npool"]}
    floors = contract["minimum_free"]
    require(free["symbol_slots"] >= floors["symbol_slots"],
            "D5 user symbol-slot floor violated")
    require(free["namepool_bytes"] >= floors["namepool_bytes"],
            "D5 user name-byte floor violated")
    return {"status": "D5 USER HEADROOM PASS",
            "ELF": bind(elf), "physical_bank0": bind(bank0),
            "ELF_derived_addresses": {key: f"0x{value:04X}"
                                      for key, value in addresses.items()},
            "observed": observed, "limits": limits, "free": free,
            "minimum_free": floors}


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="action", required=True)
    for action in ("write", "check", "selftest"):
        sub.add_parser(action)
    device = sub.add_parser("verify-device")
    device.add_argument("--elf", type=Path, required=True)
    device.add_argument("--physical-bank0", type=Path, required=True)
    args = parser.parse_args()
    if args.action == "write":
        value = derive()
        RECEIPT.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
        result = {"status": "WRITTEN", "receipt": bind(RECEIPT)}
    elif args.action == "check":
        audit(load(RECEIPT))
        result = {"status": "PASS", "mutations": 14,
                  "recommendation": derive()["recommendation"]["form"]}
    elif args.action == "selftest":
        result = selftest()
    else:
        result = verify_device(args.elf, args.physical_bank0)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (PricingError, ElfTruthError, OSError, ValueError, KeyError, IndexError,
            json.JSONDecodeError, subprocess.CalledProcessError) as error:
        print(f"V1.5 NAME FREIGHT PRICING: {error}", file=sys.stderr)
        raise SystemExit(1)
