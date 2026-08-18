#!/usr/bin/env python3
"""Close candidate-world count, set, and membership expectations."""

from __future__ import annotations

import ast
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_lite_canonical_product as CAN  # noqa: E402
import c2_v150_qualification_ambient_closure as AMBIENT  # noqa: E402
import c2_v19_acceptance_vocabulary as VOCAB  # noqa: E402
import c2_v21_pinned_constant_sweep as OLD  # noqa: E402
import c2_v21_workbench_capacity_card_red_attribution as RED  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.1-cpu-transport-work-plan.md"
CANONICAL = Path(CAN.__file__).resolve()
ABI = ROOT / "tools/host-lisp/c2_asm_leaf_abi_gate.py"
CANDIDATE = ROOT / "tools/host-lisp/c2_v150_candidate_product.py"
RECEIPT = ARCH / "c2.3-v2.1-expectation-shape-sweep-receipt.json"
DRIVER = Path(__file__).resolve()
AUTHORIZATION = "c54a062d"
RECORDED_ON = "2026-08-14"


class SweepError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise SweepError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"artifact absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def git_binding(commit: str, path: Path) -> dict[str, Any]:
    name = path.relative_to(ROOT).as_posix()
    full = subprocess.run(
        ["git", "rev-parse", f"{commit}^{{commit}}"], cwd=ROOT, check=True,
        text=True, stdout=subprocess.PIPE).stdout.strip()
    raw = subprocess.run(
        ["git", "show", f"{full}:{name}"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE).stdout
    return {"authority": "git-blob", "commit": full, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def authorization() -> dict[str, Any]:
    authority = git_binding(AUTHORIZATION, PLAN)
    raw = subprocess.run(
        ["git", "show", f"{authority['commit']}:{authority['path']}"],
        cwd=ROOT, check=True, stdout=subprocess.PIPE).stdout
    text = " ".join(raw.decode().split()).lower()
    for token in (
            "counted expectation to a", "expected-set shape",
            "any expectation enumerating or counting", "one card"):
        require(token in text, f"expectation-shape authorization absent: {token}")
    return authority


def sources(overrides: dict[str, str] | None = None) -> dict[str, str]:
    value = {
        "canonical": CANONICAL.read_text(encoding="utf-8"),
        "abi": ABI.read_text(encoding="utf-8"),
        "candidate": CANDIDATE.read_text(encoding="utf-8"),
    }
    if overrides:
        value.update(overrides)
    return value


def function(text: str, name: str) -> ast.FunctionDef:
    rows = [node for node in ast.walk(ast.parse(text))
            if isinstance(node, ast.FunctionDef) and node.name == name]
    require(len(rows) == 1, f"unique function absent: {name}")
    return rows[0]


def expressions(node: ast.AST) -> set[str]:
    return {ast.unparse(item) for item in ast.walk(node)}


def _literal_shape(node: ast.AST) -> bool:
    return isinstance(node, (ast.Dict, ast.List, ast.Set, ast.Tuple))


def _contains_candidate_inventory(node: ast.AST) -> bool:
    text = ast.unparse(node)
    return "callsite_count" in text or text == "owners" or "['owner']" in text


def forbidden_shape_pins(*nodes: ast.AST) -> list[str]:
    result: list[str] = []
    for root in nodes:
        for row in ast.walk(root):
            if not isinstance(row, ast.Compare):
                continue
            operands = [row.left, *row.comparators]
            if not any(_contains_candidate_inventory(item) for item in operands):
                continue
            if any(isinstance(item, ast.Constant)
                   and isinstance(item.value, int)
                   and not isinstance(item.value, bool) for item in operands):
                result.append(ast.unparse(row))
            elif any(_literal_shape(item) for item in operands):
                result.append(ast.unparse(row))
    return sorted(result)


def source_gate(overrides: dict[str, str] | None = None) -> dict[str, Any]:
    text = sources(overrides)
    classifier = function(text["canonical"], "classify_rtov_crc_callers")
    real_abi = function(text["canonical"], "fresh_real_abi_gate")
    postlink = function(text["canonical"], "fresh_current_product_postlink_gate")
    crc_inventory = function(text["abi"], "_crc_caller_inventory")
    c_called = function(text["abi"], "_c_called_asm_inventory")
    replay = function(text["candidate"], "post_link_replay")
    classifier_expr = expressions(classifier)
    abi_expr = expressions(real_abi)
    postlink_expr = expressions(postlink)
    inventory_expr = expressions(crc_inventory)
    classifier_loops = [item for item in ast.walk(classifier)
                        if isinstance(item, ast.For)
                        and ast.unparse(item.target) == "row"
                        and ast.unparse(item.iter) == "rows"]
    replay_calls = [item for item in ast.walk(replay)
                    if isinstance(item, ast.Call)
                    and ast.unparse(item.func) == "can.fresh_real_abi_gate"]
    require(
        len(classifier_loops) == 1
        and "row.get('model') == expected_model" in classifier_expr
        and "callers.get('callsite_count') == len(rows) == len(classified)"
            in classifier_expr
        and "callers.get('direct_jsr_count') == len(classified)"
            in classifier_expr
        and "classification['candidate_derived_callsite_count'] == "
            "callers['callsite_count']" in abi_expr
        and "abi['classified_callsite_count'] == abi['callsite_count']"
            in postlink_expr
        and "len(result)" in inventory_expr
        and len(replay_calls) == 1,
        "candidate caller classification is not transitively consumed")
    pins = forbidden_shape_pins(classifier, real_abi, postlink)
    require(not pins, f"candidate-world expectation shape remains pinned: {pins}")
    old = OLD.source_gate()
    ambient = AMBIENT.source_gate()
    require(old["pinned_count"] == 0
            and old["expectation_count"] == old["candidate_derived_count"]
            and ambient["ambient_input_count"] == 0,
            "prior transitive qualification closures are not green")
    return {
        "status": "PASS: candidate-world expectation shapes classified",
        "scope": "transitive current Link-107 qualification consumer path",
        "converted_sites": [
            "fresh-real-ABI historical callsite count",
            "fresh-real-ABI historical owner multiset",
            "current-postlink historical callsite count",
        ],
        "converted_site_count": 3,
        "candidate_derived_shapes": [
            "CRC relocation callsite cardinality",
            "CRC caller owner multiset",
            "CRC caller membership and ABI classification",
            "C-called assembler function set and policy coverage",
            "postlink classified-caller cardinality",
        ],
        "candidate_derived_shape_count": 5,
        "pinned_candidate_shape_count": len(pins),
        "classifier_rule":
            "owned-direct-JSR-with-local-pointer-and-length",
        "prior_address_size_identity_expectations": old["expectation_count"],
        "prior_ambient_inputs": ambient["ambient_input_count"],
        "rule": (
            "Every count, set, multiset, or membership list describing "
            "candidate-world entities derives from the candidate. Stable "
            "expectations classify each derived entity by contract."),
    }


def _caller(index: int, owner: str) -> dict[str, Any]:
    return {
        "owner": owner, "owner_section": f".candidate_{index}",
        "call_address": 0x2000 + index * 3,
        "model": {"pointer_low": "__rc2", "pointer_high": "__rc3",
                  "length_low": "A", "length_high": "X",
                  "edge": "JSR rtov_crc_mem"},
    }


def classifier_cases() -> dict[str, Any]:
    accepted: list[int] = []
    for count in (1, 2, 10, 17):
        rows = [_caller(index, f"candidate_owner_{index % 3}")
                for index in range(count)]
        result = CAN.classify_rtov_crc_callers({
            "status": "passed-complete-final-elf-caller-inventory",
            "callsite_count": count, "direct_jsr_count": count,
            "non_jsr_or_unowned_count": 0, "callers": rows})
        require(result["candidate_derived_callsite_count"] == count
                and result["all_callers_classified"] is True,
                "candidate-derived classifier cardinality drift")
        accepted.append(count)
    base = [_caller(index, f"owner_{index}") for index in range(3)]
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "short-declared-count": lambda x: x.update(callsite_count=2),
        "non-JSR-edge": lambda x: x["callers"][0]["model"].update(
            edge="JMP rtov_crc_mem"),
        "unowned-section": lambda x: x["callers"][0].update(owner_section=""),
        "duplicate-call-address": lambda x: x["callers"][1].update(
            call_address=x["callers"][0]["call_address"]),
    }
    rejected: list[str] = []
    prototype = {"status": "passed-complete-final-elf-caller-inventory",
                 "callsite_count": 3, "direct_jsr_count": 3,
                 "non_jsr_or_unowned_count": 0, "callers": base}
    for name, mutate in cases.items():
        candidate = deepcopy(prototype); mutate(candidate)
        try:
            CAN.classify_rtov_crc_callers(candidate)
        except (SweepError, RuntimeError):
            rejected.append(name)
    require(rejected == list(cases), "invalid candidate caller survived")
    return {"accepted_candidate_counts": accepted,
            "rejected_invalid_cases": rejected}


def vocabulary_successor() -> dict[str, Any]:
    prior = load(VOCAB.REBIND)
    prior_members = set(prior["current"]["members"])
    current_members, _consumers = VOCAB.current_driver_tokens(
        load(VOCAB.CONTRACT))
    additions = sorted(current_members - prior_members)
    require(
        len(prior_members) == 104
        and not (prior_members - current_members)
        and additions == [
            "all_callers_classified", "caller_classification",
            "classified_callsite_count", "rule"],
        "expectation-shape driver vocabulary successor drift")
    return {
        "status": "PASS: expectation-shape vocabulary added, none removed",
        "prior_member_count": len(prior_members),
        "current_member_count": len(current_members),
        "current_member_set_sha256": VOCAB.set_sha(current_members),
        "added_members": additions, "removed_members": [],
        "prior_rebind": bind(VOCAB.REBIND),
    }


def source_mutations() -> list[str]:
    base = sources()
    cases: list[tuple[str, str, str, str]] = [
        ("restore-callsite-count-9", "canonical",
         "and classification[\"all_callers_classified\"] is True",
         "and callers[\"callsite_count\"] == 9\n"
         "        and classification[\"all_callers_classified\"] is True"),
        ("restore-owner-multiset", "canonical",
         "classification = classify_rtov_crc_callers(callers)",
         "require(owners == {\"vm_runtime_overlay_exec_family\": 2}, "
         "\"historical owner set\")\n"
         "    classification = classify_rtov_crc_callers(callers)"),
        ("restore-postlink-count-9", "canonical",
         "and abi[\"all_callers_classified\"] is True",
         "and abi[\"callsite_count\"] == 9\n"
         "        and abi[\"all_callers_classified\"] is True"),
        ("restore-owner-whitelist", "canonical",
         "and isinstance(row.get(\"call_address\"), int)",
         "and row[\"owner\"] in (\"vm_runtime_overlay_exec_family\",)\n"
         "            and isinstance(row.get(\"call_address\"), int)"),
        ("classify-only-prefix", "canonical",
         "for row in rows:", "for row in rows[:-1]:"),
    ]
    rejected: list[str] = []
    for name, role, old, new in cases:
        require(old in base[role], f"expectation-shape mutation anchor absent: {name}")
        mutant = dict(base); mutant[role] = mutant[role].replace(old, new, 1)
        try:
            source_gate(mutant)
        except (SweepError, SyntaxError):
            rejected.append(name)
    expected = [name for name, *_rest in cases]
    require(rejected == expected,
            f"expectation-shape source mutation survived: "
            f"expected={expected} rejected={rejected}")
    return rejected


def derive() -> dict[str, Any]:
    red = load(RED.RECEIPT)
    red_rejected = red.pop("mutations_rejected", None)
    RED.validate(red, verify=True)
    require(red_rejected == RED.mutations(red)
            and red["new_final_red"]["actual_callsite_count"] == 10
            and red["new_final_red"]["expected_callsite_count"] == 9,
            "expectation-shape Final Red authority drift")
    gate = source_gate()
    return {
        "format": "lisp65-c2.3-v21-expectation-shape-sweep-v1",
        "recorded_on": RECORDED_ON,
        "status": "PASS: remaining candidate expectation forms derive or classify",
        "sweep": gate,
        "classifier_cases": classifier_cases(),
        "driver_vocabulary_successor": vocabulary_successor(),
        "mutations_rejected": source_mutations(),
        "authority": {"authorization": authorization(),
            "predecessor_attribution": bind(RED.RECEIPT),
            "prior_constant_sweep": bind(OLD.RECEIPT),
            "prior_constant_sweep_driver":
                bind(Path(OLD.__file__).resolve()),
            "canonical_consumer": bind(CANONICAL),
            "ABI_consumer": bind(ABI), "candidate_replay": bind(CANDIDATE),
            "ambient_closure": bind(Path(AMBIENT.__file__).resolve()),
            "vocabulary_gate": bind(Path(VOCAB.__file__).resolve()),
            "driver": bind(DRIVER)},
        "disposition": {"cards_authorized": 1, "cards_consumed": 0,
            "completion_allowed": False, "media_allowed": False,
            "device_allowed": False},
        "claim_limit": (
            "Host-only expectation-form closure. The single authorized card "
            "has not run; no completion, media, or device action."),
    }


def validate(value: dict[str, Any], *, verify: bool) -> None:
    sweep = value.get("sweep", {})
    require(
        value.get("status") ==
            "PASS: remaining candidate expectation forms derive or classify"
        and sweep.get("pinned_candidate_shape_count") == 0
        and sweep.get("converted_site_count") == 3
        and sweep.get("candidate_derived_shape_count") == 5
        and value.get("classifier_cases", {}).get(
            "accepted_candidate_counts") == [1, 2, 10, 17]
        and value.get("mutations_rejected") == source_mutations()
        and value.get("disposition", {}).get("cards_consumed") == 0,
        "expectation-shape sweep receipt red")
    if verify:
        require(value == derive(), "expectation-shape sweep authority drift")


def receipt_mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "hide-pinned-shape": lambda x: x["sweep"].update(
            pinned_candidate_shape_count=1),
        "drop-converted-site": lambda x: x["sweep"]["converted_sites"].pop(),
        "pin-accepted-counts": lambda x: x["classifier_cases"].update(
            accepted_candidate_counts=[10]),
        "consume-card": lambda x: x["disposition"].update(cards_consumed=1),
        "allow-device": lambda x: x["disposition"].update(device_allowed=True),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        candidate = deepcopy(value); mutate(candidate)
        try:
            validate(candidate, verify=True)
        except SweepError:
            rejected.append(name)
    require(rejected == list(cases), "expectation-shape receipt mutation survived")
    return rejected


def record() -> None:
    require(not RECEIPT.exists(), "expectation-shape sweep receipt exists")
    value = derive(); validate(value, verify=True)
    value["receipt_mutations_rejected"] = receipt_mutations(value)
    RECEIPT.write_bytes(canonical(value))
    print("2.1 expectation-shape sweep: PASS converted=3 shapes=5 "
          "pinned=0 mutations=10 card=0/1")


def check() -> None:
    value = load(RECEIPT)
    rejected = value.pop("receipt_mutations_rejected", None)
    validate(value, verify=True)
    require(rejected == receipt_mutations(value),
            "expectation-shape receipt mutation set drift")
    print("2.1 expectation-shape sweep: CHECK PASS pinned=0 card=0/1")


def selftest() -> None:
    value = derive(); validate(value, verify=True); receipt_mutations(value)
    print("2.1 expectation-shape sweep: SELFTEST PASS mutations=10")


def main() -> int:
    require(len(sys.argv) == 2 and sys.argv[1] in ("record", "check", "selftest"),
            "usage: c2_v21_expectation_shape_sweep.py record|check|selftest")
    {"record": record, "check": check, "selftest": selftest}[sys.argv[1]]()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (SweepError, OSError, ValueError, KeyError, json.JSONDecodeError,
            subprocess.SubprocessError) as error:
        print(f"2.1 expectation-shape sweep: FAIL {error}", file=sys.stderr)
        raise SystemExit(2)
