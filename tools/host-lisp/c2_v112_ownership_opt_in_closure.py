#!/usr/bin/env python3
"""Close every parked ownership trace over one explicit opt-in seam."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import inspect
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_product_substitution_link as PRODUCT  # noqa: E402


CONTRACT = ROOT / "config/c2-v112-ownership-opt-in-closure.json"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.12-ownership-opt-in-closure-receipt.json")
FOREIGN_REFRESH_AUTHORITIES = (
    ROOT / (
        "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
        "c2.2-v2-while-four-view-receipt.json"),
)


class ClosureError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ClosureError(message)


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(),
            f"regular JSON authority absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(),
            f"regular authority absent: {path}")
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def canonical(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def relative_sources(values: list[str]) -> set[str]:
    return {Path(value).resolve().relative_to(ROOT).as_posix()
            for value in values}


def assertion_messages(text: str) -> set[str]:
    return set(re.findall(
        r'ASSERT\(.*?"([^"]+)"\);', text, flags=re.DOTALL))


def symbol_names(text: str) -> set[str]:
    return set(re.findall(r"__lisp65_c2_mapped_far_[A-Za-z0-9_]+", text))


def inventory_projection() -> dict[str, Any]:
    """Derive both scopes from live producers, never from the contract."""
    saved = PRODUCT.FULL_MAP_OWNERSHIP
    try:
        PRODUCT.FULL_MAP_OWNERSHIP = False
        dummy = {
            "product_build_id_hex": "0x00000000",
            "artifacts": {"shelf": {"bytes": 0}},
        }
        base_definitions = set(PRODUCT.definitions(dummy))
        ordinary_definitions = set(PRODUCT.scoped_probe_definitions(()))
        selected_definitions = set(PRODUCT.scoped_probe_definitions(
            (PRODUCT.CONVERGENCE_FEATURE,)))
        ordinary_sources = relative_sources(PRODUCT.source_list(()))
        selected_sources = relative_sources(PRODUCT.source_list(
            (PRODUCT.CONVERGENCE_FEATURE,)))
        ordinary_linker = PRODUCT.linker_script()
        selected_linker = PRODUCT.linker_script(ownership_opt_in=True)
        ordinary_inventory = set(
            PRODUCT.final_section_inventory_expectation()["names"])
        ordinary_flags = set(PRODUCT.ownership_link_flags(()))
        selected_flags = set(PRODUCT.ownership_link_flags(
            (PRODUCT.CONVERGENCE_FEATURE,)))

        with tempfile.TemporaryDirectory(prefix="c2-v112-opt-out-") as raw:
            ordinary_dir = Path(raw) / "ordinary"
            PRODUCT.write_product_linker_sources(ordinary_dir, ())
            ordinary_platform = {
                path.name for path in (ordinary_dir / "full-map-linker").glob("*")
            } if (ordinary_dir / "full-map-linker").exists() else set()

        PRODUCT.FULL_MAP_OWNERSHIP = True
        full_definitions = set(PRODUCT.scoped_probe_definitions(()))
        full_sources = relative_sources(PRODUCT.source_list(()))
        full_inventory = set(
            PRODUCT.final_section_inventory_expectation()["names"])
        platform_renderers = {
            "c.ld": PRODUCT.full_map_platform_c_ld(),
            "commodore.ld": PRODUCT.full_map_platform_commodore_ld(),
            "zp-data.ld": PRODUCT.full_map_platform_zp_data_ld(),
        }
        require(all(text.strip() for text in platform_renderers.values()),
                "selected full-map platform renderer is empty")
        writer_source = inspect.getsource(PRODUCT.write_product_linker_sources)
        full_platform = {
            value for value in re.findall(r'["\']([^"\']+\.ld)["\']',
                                           writer_source)
            if value != "c2-substitution.ld"
        }
    finally:
        PRODUCT.FULL_MAP_OWNERSHIP = saved

    define_universe = set(PRODUCT.CONVERGENCE_DEFINES)
    source_universe = {
        path.relative_to(ROOT).as_posix() for path in PRODUCT.CONVERGENCE_SOURCES
    }
    selected_assertions = assertion_messages(selected_linker)
    ordinary_assertions = assertion_messages(ordinary_linker)
    ownership_assertions = selected_assertions - ordinary_assertions
    selected_symbols = symbol_names(selected_linker)
    ordinary_symbols = symbol_names(ordinary_linker)
    keep_patterns = lambda text: set(re.findall(  # noqa: E731
        r"KEEP\(\*\(([^)]+)\)\)", text))
    selected_keep = keep_patterns(selected_linker)
    ordinary_keep = keep_patterns(ordinary_linker)
    guarded_consumers: dict[str, list[str]] = {}
    for path in sorted((ROOT / "src").rglob("*")):
        if not path.is_file() or path.suffix not in {".c", ".h", ".s"}:
            continue
        source = path.read_text(encoding="utf-8")
        tokens = sorted(token for token in define_universe if token in source)
        if tokens:
            guarded_consumers[path.relative_to(ROOT).as_posix()] = tokens
    return {
        "base_parked_defines": sorted(base_definitions & define_universe),
        "ordinary": {
            "defines": sorted(ordinary_definitions & define_universe),
            "sources": sorted(ordinary_sources & source_universe),
            "flags": sorted(ordinary_flags),
            "ownership_assertions": sorted(
                ownership_assertions & ordinary_assertions),
            "ownership_symbols": sorted(selected_symbols & ordinary_symbols),
            "fixed_floor": (
                "__lisp65_workbench_overlay_min_start = 0xc354;"
                in ordinary_linker),
            "derived_floor_instances": ordinary_linker.count(
                "__lisp65_workbench_overlay_min_start = "
                "ALIGN(__lisp65_workbench_noinit_end + 1, 2);"),
            "platform_linkers": sorted(ordinary_platform),
        },
        "selected": {
            "defines": sorted(selected_definitions & define_universe),
            "sources": sorted(selected_sources & source_universe),
            "flags": sorted(selected_flags),
            "sections": sorted({
                token for token in re.findall(
                    r"\.lisp65_c2_[A-Za-z0-9_.]+", selected_linker)
                if token.startswith((
                    ".lisp65_c2_convergence_",
                    ".lisp65_c2_static_stack",
                    ".lisp65_c2_mapped_far_"))
                and not token.endswith(".")
            } - {
                token for token in re.findall(
                    r"\.lisp65_c2_[A-Za-z0-9_.]+", ordinary_linker)
            }),
            "input_patterns_present": sorted(
                selected_keep - ordinary_keep),
            "assertion_messages": sorted(
                selected_assertions - ordinary_assertions),
            "symbols": sorted(selected_symbols - ordinary_symbols),
            "fixed_floor": (
                "__lisp65_workbench_overlay_min_start = 0xc354;"
                in selected_linker),
            "derived_floor_instances": selected_linker.count(
                "__lisp65_workbench_overlay_min_start = "
                "ALIGN(__lisp65_workbench_noinit_end + 1, 2);"),
        },
        "full_map": {
            "defines": sorted(full_definitions & define_universe),
            "sources": sorted(full_sources & source_universe),
            "platform_linkers": sorted(full_platform),
            "inventory_additions": sorted(full_inventory - ordinary_inventory),
        },
        "guarded_consumers": guarded_consumers,
    }


def audit(projection: dict[str, Any], contract: dict[str, Any]) -> None:
    expected_defines = sorted(contract["parked_defines"])
    expected_sources = sorted(contract["parked_sources"])
    selected = contract["selected_linker"]
    canonical_spec = contract["canonical_linker"]
    full = contract["full_map_selected_only"]
    ordinary = projection["ordinary"]
    require(projection["base_parked_defines"] == [],
            "parked define leaked into canonical definitions")
    require(ordinary["defines"] == [] and ordinary["sources"] == []
            and ordinary["flags"] == [],
            "parked define/source/flag leaked into canonical scope")
    require(ordinary["ownership_assertions"] == []
            and ordinary["ownership_symbols"] == []
            and ordinary["fixed_floor"] is False
            and ordinary["derived_floor_instances"] == 1
            and ordinary["platform_linkers"] == [],
            "parked linker/checker placement leaked into canonical scope")
    require(projection["selected"]["defines"] == expected_defines
            and projection["selected"]["sources"] == expected_sources,
            "selected define/source ownership bundle is incomplete")
    require(projection["selected"]["flags"] == sorted(selected["flags"])
            and projection["selected"]["sections"]
                == sorted(selected["sections"])
            and projection["selected"]["input_patterns_present"]
                == sorted(selected["input_patterns"])
            and projection["selected"]["assertion_messages"]
                == sorted(selected["assertion_messages"])
            and projection["selected"]["symbols"]
                == sorted(selected["symbols"])
            and projection["selected"]["fixed_floor"] is True
            and projection["selected"]["derived_floor_instances"] == 0,
            "selected ownership linker closure is incomplete")
    require(projection["full_map"]["defines"] == expected_defines
            and projection["full_map"]["sources"] == expected_sources
            and projection["full_map"]["platform_linkers"]
                == sorted(full["generated_platform_linkers"])
            and projection["full_map"]["inventory_additions"]
                == sorted(full["final_inventory_additions"]),
            "full-map selector does not close its complete owner bundle")
    require(projection["guarded_consumers"] == {
                path: sorted(tokens)
                for path, tokens in contract["guarded_consumers"].items()
            }, "guarded consumer vocabulary drift")
    require(canonical_spec["parked_member_instances"] == 0
            and canonical_spec["parked_link_flags"] == 0
            and canonical_spec["parked_sources"] == 0
            and canonical_spec["parked_defines"] == 0,
            "canonical zero-member policy drift")


def rejected(label: str, action: Callable[[], None],
             mutations: dict[str, str]) -> None:
    try:
        action()
    except ClosureError as error:
        mutations[label] = str(error)
    else:
        raise ClosureError(f"ownership closure mutation survived: {label}")


def mutate_list(projection: dict[str, Any], path: tuple[str, ...],
                value: str, *, add: bool) -> dict[str, Any]:
    mutant = deepcopy(projection)
    current: Any = mutant
    for key in path[:-1]:
        current = current[key]
    values = list(current[path[-1]])
    if add:
        values.append(value)
    else:
        require(value in values, f"mutation member absent: {value}")
        values.remove(value)
    current[path[-1]] = sorted(values)
    return mutant


def model_selftest() -> dict[str, Any]:
    contract = load(CONTRACT)
    require(contract.get("format")
            == "lisp65-c2-v112-parked-ownership-opt-in-closure-v1"
            and contract.get("recorded_on") == "2026-08-07",
            "ownership opt-in contract identity drift")
    projection = inventory_projection()
    audit(projection, contract)
    mutations: dict[str, str] = {}
    categories = (
        (("selected", "defines"), contract["parked_defines"]),
        (("selected", "sources"), contract["parked_sources"]),
        (("selected", "flags"), contract["selected_linker"]["flags"]),
        (("selected", "sections"), contract["selected_linker"]["sections"]),
        (("selected", "input_patterns_present"),
         contract["selected_linker"]["input_patterns"]),
        (("selected", "assertion_messages"),
         contract["selected_linker"]["assertion_messages"]),
        (("selected", "symbols"), contract["selected_linker"]["symbols"]),
        (("full_map", "platform_linkers"),
         contract["full_map_selected_only"]["generated_platform_linkers"]),
        (("full_map", "inventory_additions"),
         contract["full_map_selected_only"]["final_inventory_additions"]),
    )
    for path, values in categories:
        for value in values:
            label = f"selected-member-deleted:{path[-1]}:{value}"
            rejected(label,
                     lambda path=path, value=value: audit(
                         mutate_list(projection, path, value, add=False),
                         contract), mutations)
    for key, values in (
            ("defines", contract["parked_defines"]),
            ("sources", contract["parked_sources"]),
            ("flags", contract["selected_linker"]["flags"])):
        for value in values:
            rejected(
                f"canonical-member-leaked:{key}:{value}",
                lambda key=key, value=value: audit(
                    mutate_list(projection, ("ordinary", key), value,
                                add=True), contract),
                mutations)
    for path, value in (
            (("ordinary", "fixed_floor"), True),
            (("ordinary", "derived_floor_instances"), 0),
            (("selected", "fixed_floor"), False),
            (("selected", "derived_floor_instances"), 1)):
        mutant = deepcopy(projection)
        mutant[path[0]][path[1]] = value
        rejected(f"floor-mode-mutated:{path[0]}:{path[1]}",
                 lambda mutant=mutant: audit(mutant, contract), mutations)
    for path, tokens in contract["guarded_consumers"].items():
        for token in tokens:
            mutant = deepcopy(projection)
            mutant["guarded_consumers"][path].remove(token)
            rejected(f"guarded-consumer-token-deleted:{path}:{token}",
                     lambda mutant=mutant: audit(mutant, contract), mutations)
    require(len(mutations) >= 50,
            f"ownership closure mutation census too small: {len(mutations)}")
    return {
        "status": "passed-complete-ownership-opt-in-inventory",
        "projection": projection,
        "mutations_rejected": len(mutations),
        "mutations": mutations,
    }


def seed_check(contract: dict[str, Any]) -> dict[str, Any]:
    spec = contract["canonical_seed"]
    build = ROOT / spec["build"]
    receipt = ROOT / spec["receipt"]
    require(build == ROOT / "build/c2.3/v1.4.0-ownership-opt-out-seed-closure",
            "canonical seed build authority drift")
    if build.exists():
        shutil.rmtree(build)
    if receipt.exists():
        receipt.unlink()
    environment = dict(os.environ)
    environment.update({
        "LISP65_CANONICAL_SCOPE_BUILD": spec["build"],
        "LISP65_CANONICAL_SCOPE_SEED_RECEIPT": spec["receipt"],
    })
    foreign_before = {
        path: path.read_bytes() for path in FOREIGN_REFRESH_AUTHORITIES
    }
    try:
        completed = subprocess.run(
            [sys.executable, spec["driver"], spec["action"]],
            cwd=ROOT, env=environment, check=False, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    finally:
        # One inherited predecessor gate intentionally refreshes its own
        # historical completion canary.  That write is outside this closure's
        # authority: restore the exact pre-run bytes (including any caller
        # change) instead of letting a canonical seed check rewrite history.
        for path, data in foreign_before.items():
            path.write_bytes(data)
    build.mkdir(parents=True, exist_ok=True)
    (build / "closure-driver.stdout.txt").write_text(
        completed.stdout or "", encoding="utf-8")
    (build / "closure-driver.stderr.txt").write_text(
        completed.stderr or "", encoding="utf-8")
    require(completed.returncode == 0,
            "canonical opt-out seed link failed: "
            f"exit={completed.returncode}; stderr={completed.stderr[-2000:]}")
    value = load(receipt)
    require(value.get("status") == spec["required_status"]
            and value.get("ownership_opt_in") is False
            and value.get("seed_links") == spec["seed_links"]
            and value.get("product_links") == spec["product_links"]
            and value.get("product_completed") is False
            and value.get("final_product_absent") is True,
            "canonical opt-out seed receipt claim drift")
    forbidden = (
        build / "canonical-product-manifest.json",
        build / "media",
        build / "receipts/v1.4.0-completion.json",
    )
    require(not any(path.exists() for path in forbidden),
            "canonical seed closure crossed into product completion")
    return {
        "status": value["status"],
        "receipt": bind(receipt),
        "driver_stdout": bind(build / "closure-driver.stdout.txt"),
        "driver_stderr": bind(build / "closure-driver.stderr.txt"),
        "seed_artifacts": value["artifacts"],
        "seed_links": value["seed_links"],
        "product_links": value["product_links"],
        "product_completed": value["product_completed"],
    }


def check() -> dict[str, Any]:
    contract = load(CONTRACT)
    model = model_selftest()
    seed = seed_check(contract)
    value = {
        "format": "lisp65-c2-v112-ownership-opt-in-closure-receipt-v1",
        "recorded_on": "2026-08-07",
        "status": "passed-complete-opt-in-and-canonical-seed-closure",
        "owner_disposition": "ad6aa0ef",
        "contract": bind(CONTRACT),
        "authorities": {
            "closure_gate": bind(Path(__file__).resolve()),
            "product_linker_generator": bind(
                ROOT / "tools/host-lisp/c2_product_substitution_link.py"),
            "candidate_driver": bind(ROOT / contract["canonical_seed"]["driver"]),
            "mapped_far_selected_gate": bind(
                ROOT / "tools/host-lisp/c2_mapped_far_service_gate.py"),
            "convergence_selected_gate": bind(
                ROOT / "tools/host-lisp/c2_code_window_convergence_gate.py"),
        },
        "inventory": model,
        "canonical_seed_link": seed,
        "convicted_precedents": contract["convicted_precedents"],
        "scope_frozen": True,
        "new_product_cards": 0,
        "product_completed": False,
        "next_gate": (
            "Return the Link-92 card question to the owner; this closure does "
            "not authorize or execute a fourth card."),
        "claim_limit": contract["claim"],
    }
    RECEIPT.write_bytes(canonical(value))
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("selftest", "check"))
    args = parser.parse_args()
    try:
        if args.action == "selftest":
            value = model_selftest()
            print("c2-v112-ownership-opt-in-closure: PASS "
                  f"mode=selftest mutations={value['mutations_rejected']}")
            return 0
        value = check()
        print("c2-v112-ownership-opt-in-closure: PASS "
              f"mode=check mutations="
              f"{value['inventory']['mutations_rejected']} "
              f"seed-links={value['canonical_seed_link']['seed_links']} "
              "product-links=0 cards=0")
        return 0
    except (ClosureError, RuntimeError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print(f"c2-v112-ownership-opt-in-closure: FIRST RED: {error}",
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
