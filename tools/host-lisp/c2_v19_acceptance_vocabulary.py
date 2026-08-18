#!/usr/bin/env python3
"""Prove the complete acceptance vocabulary before the sole v1.9 card."""

from __future__ import annotations

import argparse
import ast
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))

from elf_truth import ElfTruth  # noqa: E402
import c2_asm_leaf_abi_gate as ABI  # noqa: E402


CONTRACT = ROOT / "config/c2-v19-acceptance-vocabulary.json"
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
RECEIPT = EVIDENCE / "c2.3-v1.9-acceptance-vocabulary-receipt.json"
REBIND = EVIDENCE / "c2.3-v1.9-acceptance-vocabulary-driver-rebind-receipt.json"
EXPECTATION_SHAPE = (
    EVIDENCE / "c2.3-v2.1-expectation-shape-sweep-receipt.json")
PLAN = ROOT / "docs/planning/1.9-full-map-recharter-work-plan.md"
LLVM_READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
RECORDED_ON = "2026-08-06"
HISTORICAL_GATE_COMMIT = "361c95df"
DRIVER_SUCCESSORS = {
    "bank2_workbench_scratch_negative":
        "bank2-target-and-workbench-identity",
    "final_island_single_runtime_identity":
        "final-island-carrier-identity",
    "roots_fronts_one_slice_two_entry":
        "roots-fronts-single-slice-entry-identity",
}


class VocabularyError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise VocabularyError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def set_sha(values: list[str] | set[str]) -> str:
    return hashlib.sha256(
        ("\n".join(sorted(values)) + "\n").encode("utf-8")).hexdigest()


def order_sha(values: list[str]) -> str:
    return hashlib.sha256(
        ("\n".join(values) + "\n").encode("utf-8")).hexdigest()


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(),
            f"regular JSON authority absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


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


def resolve(pointer: str, value: Any) -> Any:
    require(pointer.startswith("/"), f"JSON pointer must be absolute: {pointer}")
    current = value
    for raw in pointer[1:].split("/"):
        token = raw.replace("~1", "/").replace("~0", "~")
        require(isinstance(current, dict) and token in current,
                f"JSON pointer absent: {pointer}")
        current = current[token]
    return current


def exact_set(candidate: set[str], *, count: int, digest: str,
              label: str) -> None:
    require(len(candidate) == count, f"{label} count drift: {len(candidate)}")
    require(set_sha(candidate) == digest, f"{label} member-set drift")


def rejected(label: str, action: Callable[[], None],
             mutations: dict[str, str]) -> None:
    try:
        action()
    except VocabularyError as error:
        mutations[label] = str(error)
    else:
        raise VocabularyError(f"vocabulary mutation survived: {label}")


def bind_authorities(contract: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result = {}
    for name, row in contract["authorities"].items():
        path = ROOT / row["path"]
        actual = bind(path)
        require(actual["sha256"] == row["sha256"],
                f"vocabulary authority drift: {name}")
        result[name] = actual
    return result


def section_vocabulary(contract: dict[str, Any],
                       mutations: dict[str, str]) -> dict[str, Any]:
    spec = contract["vocabulary_classes"]["output_sections"]
    elf = ROOT / contract["authorities"]["terminal_repair_elf"]["path"]
    truth = ElfTruth.read(elf, llvm_readobj=LLVM_READOBJ)
    names = [row.name for row in truth.sections if row.name]

    def audit(candidate: list[str]) -> None:
        exact_set(set(candidate), count=spec["artifact_members"],
                  digest=spec["member_set_sha256"],
                  label="output-section vocabulary")
        require(len(candidate) == len(set(candidate)),
                "output-section vocabulary contains duplicates")

    audit(names)
    require(order_sha(names) == spec["member_order_sha256"],
            "output-section order/provenance drift")
    require(set(spec["convicted_precedents"]) <= set(names),
            "convicted section precedent absent from closure")
    inventory_reports = {}
    for key in ("terminal_seed_inventory", "terminal_final_inventory"):
        report = load(ROOT / contract["authorities"][key]["path"])
        report_names = [row["name"] for row in report["actual_sections"]]
        require(report["status"] == "passed"
                and report["pin"]["expected_sections"] == len(names)
                and report_names == names
                and report["missing_sections"] == []
                and report["unknown_sections"] == [],
                f"historical final-inventory producer closure drift: {key}")
        inventory_reports[key] = {
            "status": report["status"],
            "actual_sections": len(report_names),
            "missing_sections": 0,
            "unknown_sections": 0,
            "negative_matrix": report["negative_matrix"],
        }
    for name in names:
        rejected(f"output-section-deleted:{name}",
                 lambda name=name: audit([row for row in names if row != name]),
                 mutations)
    rejected("output-section-unowned-stray",
             lambda: audit([*names, ".lisp65_v19_unowned_stray"]),
             mutations)
    return {
        "producer": spec["producer"],
        "members": names,
        "count": len(names),
        "member_set_sha256": set_sha(set(names)),
        "member_order_sha256": order_sha(names),
        "convicted_precedents": spec["convicted_precedents"],
        "historical_producer_receipts": inventory_reports,
    }


def abi_vocabulary(contract: dict[str, Any],
                   mutations: dict[str, str]) -> dict[str, Any]:
    spec = contract["vocabulary_classes"]["assembler_abi_policies"]
    elf = ROOT / contract["authorities"]["terminal_repair_elf"]["path"]
    declarations = set(ABI._declared_asm_functions())
    policies = set(ABI.ABI_POLICIES)
    exact_set(declarations, count=spec["declared_assembler_functions"],
              digest=spec["declared_member_set_sha256"],
              label="declared assembler vocabulary")
    exact_set(policies, count=spec["policy_members"],
              digest=spec["policy_member_set_sha256"],
              label="assembler ABI policy vocabulary")
    report = ABI.audit_elf(elf)
    derived = report["ELF_derived_C_called_inventory"]
    called = set(derived["C_called_functions"])
    expected_called = set(spec["c_called_members"])
    require(called == expected_called and not (called - policies),
            "ELF-derived C-called assembler vocabulary is not fully covered")
    require(set(spec["convicted_precedents"]) <= called,
            "convicted ABI precedent absent from derived caller universe")

    for name in declarations:
        rejected(
            f"assembler-declaration-deleted:{name}",
            lambda name=name: exact_set(
                declarations - {name},
                count=spec["declared_assembler_functions"],
                digest=spec["declared_member_set_sha256"],
                label="declared assembler vocabulary"),
            mutations)
    for name in policies:
        rejected(
            f"assembler-policy-deleted:{name}",
            lambda name=name: exact_set(
                policies - {name}, count=spec["policy_members"],
                digest=spec["policy_member_set_sha256"],
                label="assembler ABI policy vocabulary"),
            mutations)
    for name in called:
        rejected(
            f"C-called-member-deleted:{name}",
            lambda name=name: require(
                called - {name} == expected_called,
                "C-called assembler member missing"),
            mutations)
    return {
        "producer": spec["producer"],
        "declared_members": sorted(declarations),
        "declared_count": len(declarations),
        "policy_members": sorted(policies),
        "policy_count": len(policies),
        "C_called_members": sorted(called),
        "C_called_count": len(called),
        "unclassified_C_called_functions":
            derived["unclassified_C_called_functions"],
        "convicted_precedents": spec["convicted_precedents"],
        "full_exact_ELF_audit": report["status"],
    }


def function_tokens(path: Path, names: set[str]) -> tuple[set[str], set[str]]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: set[str] = set()
    tokens: set[str] = set()
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                or node.name not in names:
            continue
        found.add(node.name)
        for item in ast.walk(node):
            if (isinstance(item, ast.Subscript)
                    and isinstance(item.slice, ast.Constant)
                    and isinstance(item.slice.value, str)):
                tokens.add(item.slice.value)
            if (isinstance(item, ast.Call)
                    and isinstance(item.func, ast.Attribute)
                    and item.func.attr == "get" and item.args
                    and isinstance(item.args[0], ast.Constant)
                    and isinstance(item.args[0].value, str)):
                tokens.add(item.args[0].value)
    return found, tokens


def receipt_union(value: dict[str, Any]) -> str:
    if "diagnostic" in value:
        require(isinstance(value["diagnostic"], dict)
                and {"type", "message"} <= set(value["diagnostic"]),
                "failure receipt lacks typed diagnostic")
        require("fresh_replacement_gates" not in value,
                "failed receipt masquerades as successful replacement gates")
        return "failure"
    require("fresh_replacement_gates" in value,
            "successful internal receipt lacks fresh_replacement_gates")
    replacement = value["fresh_replacement_gates"]
    require(isinstance(replacement, dict)
            and {"status", "walls", "capacity"} <= set(replacement),
            "successful replacement-gate shape is incomplete")
    return "success"


def current_driver_tokens(contract: dict[str, Any]) -> tuple[set[str], dict[str, Any]]:
    spec = contract["vocabulary_classes"]["driver_receipt_tokens"]
    tokens: set[str] = set()
    consumers = {}
    for relative, function_names in spec["consumers"].items():
        path = ROOT / relative
        wanted = set(function_names)
        found, local = function_tokens(path, wanted)
        require(found == wanted,
                f"acceptance consumer function drift: {relative}")
        tokens.update(local)
        consumers[relative] = {
            "functions": sorted(found), "tokens": sorted(local)}
    return tokens, consumers


def driver_vocabulary(contract: dict[str, Any],
                      mutations: dict[str, str],
                      expected_members: set[str] | None = None) -> dict[str, Any]:
    spec = contract["vocabulary_classes"]["driver_receipt_tokens"]
    tokens, consumers = current_driver_tokens(contract)
    expected = (set(spec["members"]) if expected_members is None
                else set(expected_members))
    require(tokens == expected,
            "driver receipt-token vocabulary drift: "
            f"missing={sorted(expected - tokens)} extra={sorted(tokens - expected)}")
    expected_digest = (spec["member_set_sha256"] if expected_members is None
                       else set_sha(expected))
    require(set_sha(tokens) == expected_digest,
            "driver receipt-token set hash drift")
    require(spec["convicted_precedent"] in tokens,
            "convicted driver token absent")
    for name in tokens:
        rejected(f"driver-token-deleted:{name}",
                 lambda name=name: require(
                     tokens - {name} == expected,
                     "driver receipt token missing"), mutations)

    failed = load(ROOT / contract["authorities"][
        "terminal_internal_receipt"]["path"])
    require(receipt_union(failed) == "failure",
            "terminal internal receipt is not a typed failure")
    success_fixture = {"fresh_replacement_gates": {
        "status": "passed", "walls": {}, "capacity": {}}}
    require(receipt_union(success_fixture) == "success",
            "success receipt fixture did not classify")
    for name, candidate in {
        "failure-without-diagnostic-type": {
            "diagnostic": {"message": "red"}},
        "failure-without-diagnostic-message": {
            "diagnostic": {"type": "GateError"}},
        "failure-with-success-payload": {
            "diagnostic": {"type": "GateError", "message": "red"},
            "fresh_replacement_gates": {}},
        "success-without-fresh-replacement-gates": {"status": "passed"},
    }.items():
        rejected(f"receipt-union:{name}",
                 lambda candidate=candidate: receipt_union(candidate),
                 mutations)
    return {
        "consumers": consumers,
        "members": sorted(tokens),
        "count": len(tokens),
        "member_set_sha256": set_sha(tokens),
        "convicted_precedent": spec["convicted_precedent"],
        "historical_failure_class": "typed-failure-no-success-consumption",
        "success_model_class": "fresh-replacement-gates-with-walls-capacity",
    }


def owner_vocabulary(contract: dict[str, Any],
                     mutations: dict[str, str]) -> dict[str, Any]:
    source = load(ROOT / contract["authorities"]["full_map_contract"]["path"])
    spec = contract["vocabulary_classes"]["owners_and_live_sets"]
    actual = {
        "input_routing_owners": [row["owner"] for row in source["input_routing"]],
        "simultaneous_live_owners": [
            row["owner"] for row in source["fixed_simultaneous_live_ledger"]],
        "zero_page_owners": [row["owner"] for row in source["zero_page_ledger"]],
    }
    result = {}
    for class_name, members in actual.items():
        expected = spec[class_name]
        member_set = set(members)
        exact_set(member_set, count=expected["members"],
                  digest=expected["member_set_sha256"], label=class_name)
        require(len(members) == len(member_set),
                f"duplicate owner in {class_name}")
        for name in member_set:
            rejected(
                f"{class_name}-deleted:{name}",
                lambda name=name, member_set=member_set, expected=expected,
                class_name=class_name: exact_set(
                    member_set - {name}, count=expected["members"],
                    digest=expected["member_set_sha256"], label=class_name),
                mutations)
        result[class_name] = {
            "members": members,
            "count": len(members),
            "member_set_sha256": set_sha(member_set),
        }
    return result


def expectation_vocabulary(contract: dict[str, Any],
                           mutations: dict[str, str]) -> dict[str, Any]:
    rows = contract["checker_expectations"]
    ids = [row["id"] for row in rows]
    require(len(ids) == len(set(ids)) == 10,
            "checker expectation vocabulary is not ten unique rows")
    observations = []
    for row in rows:
        source = load(ROOT / row["path"])
        observed = resolve(row["locator"], source)
        require(observed == row["equals"],
                f"checker expectation drift: {row['id']}")
        observations.append({**row, "observed": observed,
                             "authority": bind(ROOT / row["path"])})
    expected_ids = set(ids)
    for name in ids:
        rejected(f"checker-expectation-deleted:{name}",
                 lambda name=name: require(
                     expected_ids - {name} == expected_ids,
                     "checker expectation missing"), mutations)
    return {"count": len(rows), "expectations": observations}


def build_receipt(driver_members: set[str] | None = None) -> dict[str, Any]:
    contract = load(CONTRACT)
    require(contract["format"] == "lisp65-c2-v19-acceptance-vocabulary-v1",
            "v1.9 vocabulary contract format drift")
    mutations: dict[str, str] = {}
    authorities = bind_authorities(contract)
    sections = section_vocabulary(contract, mutations)
    abi = abi_vocabulary(contract, mutations)
    driver = driver_vocabulary(contract, mutations, driver_members)
    owners = owner_vocabulary(contract, mutations)
    expectations = expectation_vocabulary(contract, mutations)
    counts = {
        "output_sections": sections["count"],
        "assembler_declarations": abi["declared_count"],
        "assembler_policies": abi["policy_count"],
        "C_called_assembler_members": abi["C_called_count"],
        "driver_receipt_tokens": driver["count"],
        "owner_and_live_set_members": sum(
            row["count"] for row in owners.values()),
        "checker_expectations": expectations["count"],
        "mutations": len(mutations),
    }
    driver_count = (92 if driver_members is None else len(driver_members))
    mutation_count = 378 + driver_count - 92
    require(counts == {
        "output_sections": 190,
        "assembler_declarations": 29,
        "assembler_policies": 17,
        "C_called_assembler_members": 13,
        "driver_receipt_tokens": driver_count,
        "owner_and_live_set_members": 22,
        "checker_expectations": 10,
        "mutations": mutation_count,
    }, f"v1.9 vocabulary execution count drift: {counts}")
    return {
        "format": "lisp65-c2.3-v1.9-acceptance-vocabulary-receipt-v1",
        "recorded_on": RECORDED_ON,
        "status": "PASS",
        "claim": contract["claim"],
        "classes": {
            "output_sections": sections,
            "assembler_abi_policies": abi,
            "driver_receipt_tokens": driver,
            "owners_and_live_sets": owners,
            "checker_expectations": expectations,
        },
        "execution_witness": counts,
        "mutations_rejected": mutations,
        "authorities": {**authorities, "contract": bind(CONTRACT),
                         "gate": bind(Path(__file__))},
        "card_gate": {
            "wplto_started": False,
            "compiler_invocations": 0,
            "linker_invocations": 0,
            "device_contacts": 0,
            "condition": (
                "The sole v1.9 product card remains forbidden until this "
                "receipt and the later SHA-bound replay closure are green."),
        },
    }


def build_driver_rebind() -> dict[str, Any]:
    contract = load(CONTRACT)
    historical = load(RECEIPT)
    old = set(historical["classes"]["driver_receipt_tokens"]["members"])
    require(old == set(contract["vocabulary_classes"]
                       ["driver_receipt_tokens"]["members"]),
            "historical driver vocabulary no longer matches its contract")
    current, consumers = current_driver_tokens(contract)
    missing = old - current
    added = current - old
    require(missing == set(DRIVER_SUCCESSORS),
            f"unexpected historical driver token loss: {sorted(missing)}")
    require(set(DRIVER_SUCCESSORS.values()) <= added,
            "one or more named successor identities are absent")
    schema_additions = added - set(DRIVER_SUCCESSORS.values())
    require(len(current) >= 104 and len(schema_additions) >= 12,
            "current driver-vocabulary successor lost a bound member")
    mutations: dict[str, str] = {}
    for name in sorted(current):
        rejected(f"current-token-deleted:{name}",
                 lambda name=name: require(
                     current - {name} == current,
                     "current driver token missing"), mutations)
    for old_name in sorted(DRIVER_SUCCESSORS):
        rejected(f"successor-map-deleted:{old_name}",
                 lambda old_name=old_name: require(
                     old_name in (set(DRIVER_SUCCESSORS) - {old_name}),
                     "successor identity missing"), mutations)
    historical_binding = bind(RECEIPT)
    rejected("historical-receipt-rewritten",
             lambda: require(
                 {**historical_binding, "sha256": "0" * 64}
                 == historical_binding,
                 "historical receipt must remain immutable"), mutations)
    return {
        "format": "lisp65-c2.3-v1.9-driver-vocabulary-rebind-v1",
        "recorded_on": "2026-08-11",
        "status": "PASS-LOUD-DATED-REBIND",
        "authorization": "a8f7f08a",
        "historical": {
            "receipt": bind(RECEIPT),
            "member_count": len(old),
            "member_set_sha256": set_sha(old),
            "members": sorted(old),
            "rewritten": False,
        },
        "current": {
            "member_count": len(current),
            "member_set_sha256": set_sha(current),
            "members": sorted(current),
            "consumers": consumers,
            "consumer_authorities": {
                path: bind(ROOT / path)
                for path in sorted(contract["vocabulary_classes"]
                                   ["driver_receipt_tokens"]["consumers"])
            },
        },
        "semantic_successors": DRIVER_SUCCESSORS,
        "schema_additions": sorted(schema_additions),
        "mutations_rejected": mutations,
        "authorities": {
            "contract": bind(CONTRACT), "plan": bind(PLAN),
            "gate": bind(Path(__file__)),
        },
        "execution_accounting": {
            "product_links": 0, "WPLTO_runs": 0,
            "media_builds": 0, "device_contacts": 0,
        },
        "claim_limit": (
            "Current consumer vocabulary only. Historical v1.9 evidence is "
            "immutable and the finally parked ownership programme is not reopened."),
    }


def validate_driver_rebind(value: dict[str, Any]) -> None:
    expected = build_driver_rebind()
    if value == expected:
        return
    successor = load(EXPECTATION_SHAPE)
    current, _consumers = current_driver_tokens(load(CONTRACT))
    authority = successor.get("authority", {})
    rebind = successor.get("driver_vocabulary_successor", {})
    require(
        value.get("format") == "lisp65-c2.3-v1.9-driver-vocabulary-rebind-v1"
        and value.get("status") == "PASS-LOUD-DATED-REBIND"
        and rebind.get("status") ==
            "PASS: expectation-shape vocabulary added, none removed"
        and rebind.get("prior_rebind") == bind(REBIND)
        and rebind.get("current_member_count") == len(current)
        and rebind.get("current_member_set_sha256") == set_sha(current)
        and rebind.get("removed_members") == []
        and authority.get("vocabulary_gate") == bind(Path(__file__)),
        "v1.9 driver-vocabulary successor authority drift")


def historical_projection(value: dict[str, Any],
                          historical: dict[str, Any]) -> None:
    value["classes"]["driver_receipt_tokens"] = deepcopy(
        historical["classes"]["driver_receipt_tokens"])
    prefix = "driver-token-deleted:"
    for key in list(value["mutations_rejected"]):
        if key.startswith(prefix):
            del value["mutations_rejected"][key]
    for key, message in historical["mutations_rejected"].items():
        if key.startswith(prefix):
            value["mutations_rejected"][key] = message
    value["execution_witness"]["driver_receipt_tokens"] = 92
    value["execution_witness"]["mutations"] = 378


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("selftest", "write", "rebind", "check"))
    args = parser.parse_args()
    if args.mode == "rebind":
        require(not REBIND.exists(), "v1.9 driver rebind receipt already exists")
        value = build_driver_rebind()
        REBIND.write_bytes(canonical(value))
        validate_driver_rebind(value)
        print("c2-v19-acceptance-vocabulary: PASS loud-rebind "
              "driver=104 successors=3 schema-additions=12")
        return 0
    if args.mode in {"selftest", "check"}:
        require(REBIND.is_file(), "v1.9 driver-vocabulary rebind absent")
        rebind = load(REBIND)
        validate_driver_rebind(rebind)
        current, _consumers = current_driver_tokens(load(CONTRACT))
        value = build_receipt(current)
    else:
        value = build_receipt()
    if args.mode == "write":
        require(not RECEIPT.exists(), "historical vocabulary receipt is immutable")
        RECEIPT.write_bytes(canonical(value))
    elif args.mode == "check":
        historical = load(RECEIPT)
        historical_projection(value, historical)
        # 2026-08-07, ad6aa0ef: the owner commissioned a complete opt-in
        # closure for the parked ownership path.  Its permanent selected-path
        # gates retain the same semantic observations but necessarily refresh
        # their self/source authority SHAs.  Prove the live observations first,
        # then preserve the v1.9 receipt as immutable history rather than
        # silently rewriting it.  The current gates and generator are bound by
        # the new v1.12 opt-in-closure receipt.
        live_rows = {
            row["id"]: row
            for row in value["classes"]["checker_expectations"]["expectations"]
        }
        historical_rows = {
            row["id"]: row for row in historical["classes"]
                ["checker_expectations"]["expectations"]
        }
        refreshed = {
            "mapped-far-assembly-equivalence",
            "state-ownership-executions",
            "content-convergence-executions",
            "dma-sweep-linked-sites",
            "dma-sweep-protected-sites",
        }
        for identifier in refreshed:
            live = live_rows[identifier]
            old = historical_rows[identifier]
            require(
                all(live[key] == old[key]
                    for key in ("id", "path", "locator", "equals", "observed")),
                f"2026-08-07 selected-gate semantic rebind drift: {identifier}")
            live["authority"] = old["authority"]
        gate_binding = historical["authorities"]["gate"]
        raw = subprocess.run(
            ["git", "show", f"{HISTORICAL_GATE_COMMIT}:"
             f"{gate_binding['path']}"], cwd=ROOT, check=True,
            stdout=subprocess.PIPE).stdout
        require(len(raw) == gate_binding["bytes"]
                and hashlib.sha256(raw).hexdigest() == gate_binding["sha256"],
                "historical v1.9 vocabulary gate binding drift")
        value["authorities"]["gate"] = gate_binding
        require(RECEIPT.is_file() and canonical(value) == canonical(historical),
                "v1.9 acceptance-vocabulary receipt drift")
    counts = value["execution_witness"]
    print("c2-v19-acceptance-vocabulary: PASS "
          f"sections={counts['output_sections']} "
          f"abi={counts['C_called_assembler_members']}/"
          f"{counts['assembler_policies']} "
          f"driver={counts['driver_receipt_tokens']} "
          f"owners={counts['owner_and_live_set_members']} "
          f"mutations={counts['mutations']} wplto=0 device=0")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (VocabularyError, OSError, ValueError, KeyError) as error:
        print(f"c2-v19-acceptance-vocabulary: FIRST RED: {error}",
              file=sys.stderr)
        raise SystemExit(2)
