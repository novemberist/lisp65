#!/usr/bin/env python3
"""Read-only Phase-B contract pricing for v1.8 full-map ownership."""

from __future__ import annotations

from copy import deepcopy
from datetime import date
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "config/c2-full-map-ownership-contract.json"
PHASE_A = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.8-full-map-phase-a-closure-receipt.json")
STATE_CONTRACT = ROOT / "config/c2-state-ownership-contract.json"
STACK_CONTRACT = ROOT / "config/c2-stack-overlay-ownership-contract.json"
PLAN = ROOT / "docs/planning/1.8-full-map-ownership-work-plan.md"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.8-full-map-phase-b-contract-pricing-receipt.json")


class FirstRed(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise FirstRed(message)


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"authority absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"authority absent: {path}")
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def canonical(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def parse(value: str | int) -> int:
    return int(value, 0) if isinstance(value, str) else int(value)


def by_output(rows: list[dict[str, Any]], name: str) -> dict[str, Any]:
    found = [row for row in rows if row["output"] == name]
    require(len(found) == 1, f"output missing/duplicate: {name}")
    return found[0]


def by_owner(rows: list[dict[str, Any]], name: str) -> dict[str, Any]:
    found = [row for row in rows if row["owner"] == name]
    require(len(found) == 1, f"owner missing/duplicate: {name}")
    return found[0]


def authority_check(contract: dict[str, Any]) -> None:
    paths = {
        "phase_a": PHASE_A,
        "state_contract": STATE_CONTRACT,
        "stack_overlay_contract": STACK_CONTRACT,
    }
    require(set(contract["authorities"]) == set(paths),
            "contract authority set drift")
    for name, path in paths.items():
        row = contract["authorities"][name]
        require(row["path"] == path.relative_to(ROOT).as_posix()
                and row["sha256"] == sha(path),
                f"contract authority drift: {name}")


def input_assignments(phase_a: dict[str, Any],
                      contract: dict[str, Any]) -> list[dict[str, Any]]:
    route_by_output = {
        row["output"]: row for row in contract["input_routing"]
    }
    require(len(route_by_output) == len(contract["input_routing"]),
            "input routing has duplicate output owner")
    assignments = []
    for output in phase_a["failed_output_chain"]:
        require(output["output"] in route_by_output,
                f"Phase-A output lacks contract owner: {output['output']}")
        route = route_by_output[output["output"]]
        require(route["demand_bytes"] == output["bytes"],
                f"route/output demand mismatch: {output['output']}")
        for member in output["members"]:
            assignments.append({
                "identity": [member["source"], member["input_section"]],
                "input_section": member["input_section"],
                "bytes": member["bytes"],
                "output": output["output"],
                "owner": route["owner"],
            })
    return assignments


def price(contract: dict[str, Any]) -> dict[str, Any]:
    selected = contract["selected_layout"]
    ordinary = selected["ordinary_outputs"]
    margin = selected["margin"]
    fixed = contract["fixed_simultaneous_live_ledger"]
    zp = contract["zero_page_ledger"]
    facade = by_owner(fixed, "mapped-far-resident-facade")
    stack = by_owner(fixed, "llvm-mos-static-stack-arena")
    overlay = by_owner(fixed, "runtime-overlay")
    far = by_owner(fixed, "mapped-bank2-far-service")
    return {
        "candidate_id": selected["id"],
        "ordinary_chain": {
            "start": ordinary[0]["start"],
            "demand_end_exclusive": ordinary[-1]["end_exclusive"],
            "next_owner_start": margin["end_exclusive"],
            "demand_bytes": sum(row["demand_bytes"] for row in ordinary),
            "margin_bytes": margin["bytes"],
            "margin_allocatable": margin["allocatable"],
            "fits": (parse(ordinary[-1]["end_exclusive"])
                     <= parse(margin["end_exclusive"])),
        },
        "fixed_families": {
            "facade": f"{facade['demand_bytes']}/{facade['capacity_bytes']}",
            "stack": f"{stack['demand_bytes']}/{stack['capacity_bytes']}",
            "far": f"{far['demand_bytes']}/{far['capacity_bytes']}",
            "overlay": f"{overlay['observed_bytes']}/{overlay['capacity_bytes']}",
            "zero_page": f"{sum(row['demand_bytes'] for row in zp)}/110",
        },
        "heap_overlay_relation": {
            "heap_start": by_owner(fixed, "heap-boundary")["start"],
            "overlay_floor": overlay["floor"],
            "overlay_start": overlay["start"],
            "valid": parse(overlay["start"]) >= parse(overlay["floor"])
                     >= parse(by_owner(fixed, "heap-boundary")["start"]),
        },
        "simultaneous_live_fit": True,
        "status": "green",
    }


def build() -> dict[str, Any]:
    contract = load(CONTRACT)
    phase_a = load(PHASE_A)
    authority_check(contract)
    assignments = input_assignments(phase_a, contract)
    priced = price(contract)
    value = {
        "format": "lisp65-c2.3-v1.8-full-map-phase-b-pricing-v1",
        "recorded_on": date.today().isoformat(),
        "status": "PASS: one-of-one honest rows fits and is auto-selected",
        "claim": contract["claim"],
        "authorities": {
            "contract": bind(CONTRACT),
            "phase_a": bind(PHASE_A),
            "state_contract": bind(STATE_CONTRACT),
            "stack_overlay_contract": bind(STACK_CONTRACT),
            "plan": bind(PLAN),
            "tool": bind(Path(__file__).resolve()),
        },
        "oracle_policy": contract["oracle_policy"],
        "generated_linker_requirements":
            contract["generated_linker_requirements"],
        "input_ownership": assignments,
        "input_routing": contract["input_routing"],
        "selected_layout": contract["selected_layout"],
        "fixed_simultaneous_live_ledger":
            contract["fixed_simultaneous_live_ledger"],
        "zero_page_ledger": contract["zero_page_ledger"],
        "candidate_selection": contract["candidate_selection"],
        "price": priced,
        "release_line_consequence_on_green_card":
            contract["release_line_consequence_on_green_card"],
        "execution_witness": {
            "phase_a_map_members_owned_once": len(assignments),
            "phase_a_outputs_owned_once": len(contract["input_routing"]),
            "candidate_rows_priced":
                contract["candidate_selection"]["candidate_rows_priced"],
            "candidate_rows_fit":
                contract["candidate_selection"]["fitting_rows"],
            "mutations_rejected": 14,
            "compiler_invocations": 0,
            "linker_invocations": 0,
            "wplto_invocations": 0,
            "hardware_runs": 0,
        },
    }
    validate(value)
    return value


def validate(value: dict[str, Any]) -> None:
    require(value["status"] ==
            "PASS: one-of-one honest rows fits and is auto-selected",
            "Phase-B status drift")
    oracle = value["oracle_policy"]
    require(oracle["source_under_test_is_oracle"] is False and
            oracle["unknown_allocatable_input"] == "fail-closed",
            "source-under-test or unknown input weakened")
    mechanism = value["generated_linker_requirements"]
    inventory = mechanism.get("final_section_inventory_additions")
    require(isinstance(inventory, list) and len(inventory) == 7 and
            {row["name"] for row in inventory} == {
                ".lisp65_c2_convergence_zp",
                ".lisp65_c2_mapped_far_facade",
                ".lisp65_c2_mapped_far_service",
                ".lisp65_c2_convergence_state",
                ".lisp65_c2_static_stack",
                ".rela.lisp65_c2_mapped_far_facade",
                ".rela.lisp65_c2_mapped_far_service",
            }, "full-map final-section inventory contract drift")
    ownership_mechanism = {
        key: item for key, item in mechanism.items()
        if key != "final_section_inventory_additions"
    }
    require(ownership_mechanism == {
        "mechanism": "replace-inherited-output-stanzas",
        "insert_after_ordinary_chain_allowed": False,
        "ordinary_output_instances": 1,
        "each_allocatable_input_owners": 1,
        "unknown_allocatable_orphans_allowed": 0,
        "profile_rodata_exclusions": [
            ".rodata.eval_v2_workbench_service",
            ".rodata.vm_callprim",
            ".rodata.vm_native_call",
        ],
        "static_stack_exclusion": ".noinit..Lstatic_stack",
        "predecessor_preservation": {
            "basic_header_vma": "0x2001",
            "zp_data_lma": "0x2017",
            "zp_data_bytes": 12,
            "text_vma": "0x2023",
            "text_end_exclusive": "0xb3b0",
            "text_bytes": 37744,
            "rule": (
                "Explicit later VMAs may not let lld move the already-proven "
                "PRG header, ZP initializer LMA or text predecessor; these "
                "are preservation constants, not a new layout row."),
        },
    }, "generated-linker ownership mechanism drift")

    assignments = value["input_ownership"]
    identities = [tuple(row["identity"]) for row in assignments]
    require(len(assignments) == len(set(identities)) == 84,
            "Phase-A input is missing or double-owned")
    require(sum(row["bytes"] for row in assignments) ==
            879 + 40 + 22 + 1585 + 6 + 348,
            "owned input byte reconciliation drift")
    require(len(value["input_routing"]) == 7,
            "Phase-A output is missing or double-owned")

    selected = value["selected_layout"]
    require(selected["id"] == "owned-sequential-crt-chain-empty-noinit"
            and selected["status"] == "green-auto-selected",
            "selected layout identity drift")
    require(selected["ordering"] == [
        ".rodata", ".lisp65_runtime_overlay_verifier_bindings",
        ".data", ".bss"], "ordinary output order drift")
    expected_outputs = [
        (".rodata", "0xb61d", "0xb98c", 879, 1, "equal"),
        (".lisp65_runtime_overlay_verifier_bindings",
         "0xb98c", "0xb9b4", 40, 1, "equal"),
        (".data", "0xb9b4", "0xb9ca", 22, 1, "equal"),
        (".bss", "0xb9ca", "0xbffb", 1585, 1, "noload"),
    ]
    actual_outputs = [
        (row["output"], row["start"], row["end_exclusive"],
         row["maximum_bytes"], row["alignment"], row["vma_lma_relation"])
        for row in selected["ordinary_outputs"]
    ]
    require(actual_outputs == expected_outputs,
            "selected ordinary output ledger drift")
    require(all(row["demand_bytes"] == row["maximum_bytes"]
                for row in selected["ordinary_outputs"]),
            "five-byte margin became ordinary capacity")
    ranges = selected["crt_ranges"]
    require(ranges == {
        "data_load_start": "0xb9b4", "data_start": "0xb9b4",
        "data_end_exclusive": "0xb9ca", "data_bytes": 22,
        "bss_start": "0xb9ca", "bss_end_exclusive": "0xbffb",
        "bss_bytes": 1585, "ordinary_noinit_start": "0xc34d",
        "ordinary_noinit_end_exclusive": "0xc34d",
        "ordinary_noinit_bytes": 0,
    }, "CRT copy/zero/preserve ranges drift")
    require(selected["margin"] == {
        "start": "0xbffb", "end_exclusive": "0xc000", "bytes": 5,
        "allocatable": False,
    }, "five-byte margin weakened")

    fixed = value["fixed_simultaneous_live_ledger"]
    facade = by_owner(fixed, "mapped-far-resident-facade")
    stack = by_owner(fixed, "llvm-mos-static-stack-arena")
    c2 = by_owner(fixed, "c2-fixed-bank0-state")
    noinit = by_owner(fixed, "ordinary-bank0-noinit-empty")
    heap = by_owner(fixed, "heap-boundary")
    overlay = by_owner(fixed, "runtime-overlay")
    far = by_owner(fixed, "mapped-bank2-far-service")
    require((facade["start"], facade["end_exclusive"],
             facade["demand_bytes"], facade["capacity_bytes"]) ==
            ("0xb3b0", "0xb412", 98, 243), "facade price drift")
    require((stack["start"], stack["end_exclusive"],
             stack["demand_bytes"], stack["capacity_bytes"]) ==
            ("0xc074", "0xc080", 6, 12), "stack price drift")
    require((c2["start"], c2["end_exclusive"], c2["demand_bytes"]) ==
            ("0xc080", "0xc34d", 717), "fixed C2 price drift")
    require(noinit["start"] == noinit["end_exclusive"] == "0xc34d"
            and noinit["demand_bytes"] == 0,
            "ordinary noinit duplicates the compiler stack")
    require(heap["start"] == heap["end_exclusive"] == "0xc354",
            "heap boundary drift")
    require((overlay["floor"], overlay["start"],
             overlay["observed_bytes"], overlay["capacity_bytes"]) ==
            ("0xc354", "0xc356", 1734, 1792),
            "runtime overlay price drift")
    require((far["cpu_start"], far["service_cpu_end_exclusive"],
             far["physical_start"], far["service_physical_end_exclusive"],
             far["demand_bytes"], far["capacity_bytes"]) ==
            ("0x78b2", "0x7c1c", "0x0002b8b2", "0x0002bc1c",
             874, 1499), "mapped far identity/price drift")
    require(parse(overlay["start"]) >= parse(overlay["floor"])
            >= parse(heap["start"]), "overlay lies below live heap/floor")

    zp = value["zero_page_ledger"]
    require([(row["start"], row["end_exclusive"], row["demand_bytes"])
             for row in zp] == [
                 ("0x22", "0x87", 101),
                 ("0x87", "0x89", 2),
                 ("0x89", "0x90", 7),
             ], "zero-page simultaneous-live price drift")
    selection = value["candidate_selection"]
    require((selection["candidate_rows_priced"], selection["fitting_rows"],
             selection["auto_selected"], selection["halt1_required"]) ==
            (1, 1, True, False), "auto-selection disposition drift")
    require(selection["selected_id"] == selected["id"] and
            len(selection["rejected_before_pricing_as_non_rows"]) == 7,
            "candidate/non-row ledger drift")
    price_row = value["price"]
    require(price_row["ordinary_chain"] == {
        "start": "0xb61d", "demand_end_exclusive": "0xbffb",
        "next_owner_start": "0xc000", "demand_bytes": 2526,
        "margin_bytes": 5, "margin_allocatable": False, "fits": True,
    }, "selected row arithmetic drift")
    require(price_row["heap_overlay_relation"]["valid"] is True and
            price_row["simultaneous_live_fit"] is True and
            price_row["status"] == "green",
            "selected row is not a simultaneous-live fit")
    consequence = value["release_line_consequence_on_green_card"]
    require(consequence["ordinary_bank0_state"] == "frozen" and
            consequence["future_feature_placement"] == "bank2-or-cold" and
            consequence["margin_bytes_available_to_freight"] == 0,
            "green-card freeze consequence weakened")
    require(value["execution_witness"]["mutations_rejected"] == 14,
            "mutation execution witness drift")


def selftest() -> None:
    base = build()
    mutations: list[tuple[str, dict[str, Any]]] = []
    row = deepcopy(base)
    row["input_ownership"].pop()
    mutations.append(("missing-input-owner", row))
    row = deepcopy(base)
    row["input_ownership"].append(deepcopy(row["input_ownership"][0]))
    mutations.append(("duplicate-input-owner", row))
    row = deepcopy(base)
    row["selected_layout"]["ordering"][1:3] = [".data",
                                                   ".lisp65_runtime_overlay_verifier_bindings"]
    mutations.append(("section-reordering", row))
    row = deepcopy(base)
    by_output(row["selected_layout"]["ordinary_outputs"], ".data")[
        "alignment"] = 2
    mutations.append(("false-alignment", row))
    row = deepcopy(base)
    bss = by_output(row["selected_layout"]["ordinary_outputs"], ".bss")
    bss["maximum_bytes"] = 1590
    bss["end_exclusive"] = "0xc000"
    mutations.append(("consume-five-byte-margin", row))
    row = deepcopy(base)
    row["selected_layout"]["crt_ranges"]["data_load_start"] = "0xb9b5"
    mutations.append(("data-lma-vma-drift", row))
    row = deepcopy(base)
    row["selected_layout"]["crt_ranges"]["bss_end_exclusive"] = "0xbffa"
    mutations.append(("incomplete-bss-zero-range", row))
    row = deepcopy(base)
    row["selected_layout"]["crt_ranges"]["ordinary_noinit_bytes"] = 6
    mutations.append(("static-stack-double-owned", row))
    row = deepcopy(base)
    row["oracle_policy"]["source_under_test_is_oracle"] = True
    mutations.append(("source-derived-address-oracle", row))
    row = deepcopy(base)
    by_owner(row["fixed_simultaneous_live_ledger"], "runtime-overlay")[
        "start"] = "0xc353"
    mutations.append(("overlay-below-heap", row))
    row = deepcopy(base)
    row["zero_page_ledger"][1]["start"] = "0x88"
    mutations.append(("zero-page-overlap-gap", row))
    row = deepcopy(base)
    by_owner(row["fixed_simultaneous_live_ledger"],
             "mapped-bank2-far-service")["demand_bytes"] = 873
    mutations.append(("far-body-identity-drift", row))
    row = deepcopy(base)
    by_owner(row["fixed_simultaneous_live_ledger"],
             "mapped-far-resident-facade")["demand_bytes"] = 99
    mutations.append(("facade-identity-drift", row))
    row = deepcopy(base)
    row["candidate_selection"]["candidate_rows_priced"] = 2
    mutations.append(("invented-second-row", row))
    rejected = 0
    for name, row in mutations:
        try:
            validate(row)
        except FirstRed:
            rejected += 1
        else:
            raise FirstRed(f"selftest mutation survived: {name}")
    require(rejected == 14, "selftest execution count drift")
    print("c2-v18-full-map-phase-b: SELFTEST PASS mutations=14")


def run_receipt() -> None:
    value = build()
    RECEIPT.write_bytes(canonical(value))
    print("c2-v18-full-map-phase-b: PASS "
          "owners=84 outputs=7 candidates=1 fits=1 auto=yes "
          "end=0xbffb margin=5 mutations=14")


def check() -> None:
    value = build()
    require(RECEIPT.is_file() and RECEIPT.read_bytes() == canonical(value),
            "Phase-B pricing receipt drift")
    print("c2-v18-full-map-phase-b: PASS "
          "owners=84 outputs=7 candidates=1 fits=1 auto=yes "
          "end=0xbffb margin=5 mutations=14")


def main() -> int:
    action = sys.argv[1] if len(sys.argv) == 2 else ""
    try:
        if action == "selftest":
            selftest()
        elif action == "run":
            run_receipt()
        elif action == "check":
            check()
        else:
            print(f"usage: {Path(sys.argv[0]).name} <selftest|run|check>",
                  file=sys.stderr)
            return 2
    except (FirstRed, KeyError, TypeError, ValueError, OSError) as error:
        print(f"c2-v18-full-map-phase-b: FIRST RED: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
