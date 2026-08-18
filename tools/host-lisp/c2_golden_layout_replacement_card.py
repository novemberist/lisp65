#!/usr/bin/env python3
"""The owner-authorized replacement card for the golden-layout inversion.

The historical card and its First Red are immutable evidence.  This driver
owns the single replacement attempt.  Candidate production may establish
mechanical inputs and must emit a linked ELF; product acceptance is exactly
one operation: canonical linked-ELF layout bytes equal the SHA-bound golden
bytes.  Any red from the replacement attempt is terminal.
"""

from __future__ import annotations

import argparse
import ast
import contextlib
import io
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))

import c2_golden_layout_inversion as GOLD  # noqa: E402
import c2_golden_layout_product_card as HISTORICAL  # noqa: E402
import c2_v18_full_map_repair_wplto as V18  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
BUILD = ROOT / (
    "build/post-promotion/golden-layout-inversion-replacement-product-card")
PREFLIGHT = ROOT / (
    "build/post-promotion/golden-layout-inversion-replacement-preflight")
PREFLIGHT_RECEIPT = PREFLIGHT / "preflight.json"
INVOCATION = PREFLIGHT / "card-invocation.json"
RECEIPT = EVIDENCE / (
    "c2.3-golden-layout-inversion-replacement-product-card-receipt.json")
FINAL_RED = EVIDENCE / (
    "c2.3-golden-layout-inversion-replacement-product-card-final-red.json")
OWNER_DISPOSITION = ROOT / (
    "docs/planning/golden-layout-inversion-final-park.md")
OWNER_DISPOSITION_COMMIT = "e4d03191ba64c29086cbdd531595cd2ab1541781"
HISTORICAL_FIRST_RED = HISTORICAL.FIRST_RED
RECORDED_ON = "2026-08-09"
DRIVER = Path(__file__).resolve()


class ReplacementCardError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ReplacementCardError(message)


def canonical(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(),
            f"regular JSON authority absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(),
            f"regular card artifact absent: {path}")
    return GOLD.bind(path)


def owner_disposition() -> dict[str, Any]:
    binding = GOLD.git_binding(
        OWNER_DISPOSITION_COMMIT,
        OWNER_DISPOSITION.relative_to(ROOT).as_posix())
    raw = V18.subprocess.run(
        ["git", "show", f"{OWNER_DISPOSITION_COMMIT}:{binding['path']}"],
        cwd=ROOT, check=True, stdout=V18.subprocess.PIPE).stdout
    require(
        b"pre-inversion harness defect" in raw
        and b"F1W.static_gate()" in raw
        and b"geometric, harness, cosmic" in raw,
        "replacement-card owner disposition is not bound")
    return binding


PATH_FUNCTIONS = {
    "configure_replacement", "produce_candidate", "replacement_card"}
FORBIDDEN_CALLS = {
    "static_gate", "host_gates", "full_map_layout", "annotate",
    "audit_review", "historical_seed_authority", "semantic_profile_delta",
}
FORBIDDEN_PRODUCT_PREDICATE_NAMES = {
    "PROFILE_RECEIPT", "EXPECTED_PRODUCT_ID", "EXPECTED_BANK2_SHA",
    "product_build_id",
}
FORBIDDEN_PRODUCT_PREDICATE_STRINGS = {
    "product_build_id", "passed-v1.3-joint-linker-free-profile",
    "passed-owner-reauthorized-final-full-map-WPLTO",
}


def call_tail(call: ast.Call) -> str:
    node: ast.expr = call.func
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return ""


def function_nodes(source: str) -> dict[str, ast.FunctionDef]:
    tree = ast.parse(source)
    return {
        node.name: node for node in tree.body
        if isinstance(node, ast.FunctionDef)
    }


def audit_card_path(source: str) -> dict[str, Any]:
    """Reject every historical/non-geometric product precondition.

    Governance (owner authority and one-shot state) and mechanical producer
    completion are deliberately outside product acceptance.  This audit owns
    the full local call path that can insert acceptance before ``compare_elf``.
    """
    functions = function_nodes(source)
    require(PATH_FUNCTIONS <= functions.keys(),
            "replacement-card path function missing")
    calls: list[str] = []
    product_predicates = 0
    golden_comparisons = 0
    for name in sorted(PATH_FUNCTIONS):
        node = functions[name]
        for item in ast.walk(node):
            if not isinstance(item, ast.Call):
                continue
            tail = call_tail(item)
            calls.append(f"{name}:{tail}")
            require(tail not in FORBIDDEN_CALLS,
                    f"non-geometric card-path call forbidden: {tail}")
            if tail == "compare_elf":
                golden_comparisons += 1
            if tail != "require" or not item.args:
                continue
            predicate = item.args[0]
            names = {part.id for part in ast.walk(predicate)
                     if isinstance(part, ast.Name)}
            strings = {part.value for part in ast.walk(predicate)
                       if isinstance(part, ast.Constant)
                       and isinstance(part.value, str)}
            if (names & FORBIDDEN_PRODUCT_PREDICATE_NAMES
                    or any(token in string
                           for token in FORBIDDEN_PRODUCT_PREDICATE_STRINGS
                           for string in strings)):
                product_predicates += 1
    require(product_predicates == 0,
            "non-geometric product predicate present in card path")
    require(golden_comparisons == 1,
            "replacement card must contain exactly one golden comparison")
    return {
        "status": "PASS: card path has no non-geometric product precondition",
        "path_functions": sorted(PATH_FUNCTIONS),
        "calls_audited": len(calls),
        "non_geometric_product_preconditions": product_predicates,
        "golden_comparisons": golden_comparisons,
    }


def audit_mutations(source: str) -> dict[str, Any]:
    producer_marker = "# " + "CARD_PRODUCT_PATH_START"
    golden_line = (
        "comparison = GOLD." + "compare_elf(artifacts[\"elf\"])")
    mutations = {
        "historical-static-gate": source.replace(
            producer_marker,
            "joint.BASE.PROBE.REQ.F1W.static_gate()\n"
            "    " + producer_marker, 1),
        "profile-precondition": source.replace(
            producer_marker,
            "require(PROFILE_RECEIPT.is_file(), 'profile')\n"
            "    " + producer_marker, 1),
        "container-id-precondition": source.replace(
            producer_marker,
            "require(product_build_id == 'old', 'container')\n"
            "    " + producer_marker, 1),
        "historical-closer": source.replace(
            producer_marker,
            "annotate()\n    " + producer_marker, 1),
        "missing-golden": source.replace(
            golden_line,
            "comparison = {'status': 'assumed'}", 1),
        "double-golden": source.replace(
            golden_line,
            "GOLD.compare_elf(artifacts[\"elf\"])\n"
            "    " + golden_line, 1),
    }
    require(all(mutated != source for mutated in mutations.values()),
            "card-path mutation did not alter source")
    rejected: list[str] = []
    for name, mutated in mutations.items():
        try:
            audit_card_path(mutated)
        except ReplacementCardError:
            rejected.append(name)
    require(rejected == list(mutations),
            f"card-path mutation survived: {sorted(set(mutations) - set(rejected))}")
    return {
        "status": "PASS: every forbidden precondition mutation rejected",
        "mutations": len(mutations),
        "rejected": rejected,
    }


def path_gate() -> dict[str, Any]:
    source = DRIVER.read_text(encoding="utf-8")
    return {
        "audit": audit_card_path(source),
        "mutation_witness": audit_mutations(source),
    }


def configure_replacement() -> None:
    V18.BUILD = BUILD
    V18.PREFLIGHT = PREFLIGHT
    V18.PREFLIGHT_RECEIPT = PREFLIGHT_RECEIPT
    V18.RECEIPT = RECEIPT
    V18.FIRST_RED = FINAL_RED
    V18.DRIVER = DRIVER
    V18.configure_base()
    # Producer-side historical host closers are not an acceptance surface.
    V18.BASE.host_gates = lambda: {}
    V18.BASE.configure()


def produce_candidate() -> dict[str, Any]:
    """Mechanically emit one linked candidate, without accepting its product."""
    joint = V18.BASE.JOINT
    # CARD_PRODUCT_PATH_START
    paths = joint.configure(BUILD)
    static = joint.BASE.PROBE.REQ.build_static_plane()
    header = joint.PRODUCT.bind_generated_stdlib_header(paths)
    product_path = paths["static_product"] / "substitution-artifacts.json"
    product = load(product_path)
    bank2 = paths["v6"] / "bank2-static-code.bin"

    # These assignments route the just-emitted container through legacy
    # producer internals.  They compare nothing and carry no acceptance
    # authority; the linked ELF's canonical layout is the sole product oracle.
    joint.V.EXPECTED_PRODUCT_ID = product["product_build_id_hex"]
    joint.V.EXPECTED_BANK2_SHA = GOLD.sha(bank2)
    old = joint.CAN.configure_wplto()
    output = io.StringIO()
    producer_return: int | None = None
    try:
        with contextlib.redirect_stdout(output):
            producer_return = joint.CAN.LINK_GATE.BASE.main()
    finally:
        joint.CAN.restore_wplto(old)
        log = BUILD / "receipts/golden-replacement-producer.log"
        log.parent.mkdir(parents=True, exist_ok=True)
        log.write_text(output.getvalue(), encoding="utf-8")

    elf = paths["wplto"] / "lisp65-c2-substitution-linked.prg.elf"
    base_result_path = joint.CAN.LINK_GATE.BASE.BASE_RESULT
    require(elf.is_file() and base_result_path.is_file(),
            "producer did not mechanically emit the linked candidate ELF")
    base_result = load(base_result_path)
    wplto = base_result.get("WPLTO", {})
    require(wplto.get("product_completed") is True
            and wplto.get("exception") is None,
            "producer did not mechanically complete linked artifacts")
    return {
        "elf": elf,
        "map": paths["wplto"] / "lisp65-c2-substitution-linked.prg.map",
        "prg": paths["wplto"] / "lisp65-c2-substitution-linked.prg",
        "lto": paths["wplto"] / "resident-island-seed.prg.lto.o",
        "linker": paths["wplto"] / "c2-substitution.ld",
        "producer_log": log,
        "producer_return": producer_return,
        "static": static,
        "static_product": product_path,
        "bank2": bank2,
        "target_stdlib_header": header,
    }


def preflight() -> None:
    require(not BUILD.exists() and not PREFLIGHT.exists()
            and not RECEIPT.exists() and not FINAL_RED.exists(),
            "replacement card/preflight is one-shot")
    require(HISTORICAL_FIRST_RED.is_file(),
            "historical pre-inversion First Red absent")
    gate = path_gate()
    approval = owner_disposition()
    PREFLIGHT.mkdir(parents=True)
    value = {
        "format": "lisp65-c2.3-golden-layout-replacement-preflight-v1",
        "recorded_on": RECORDED_ON,
        "status": "PASS: exactly one exceptionless replacement card armed",
        "wplto_started": False,
        "product_compiles": 0,
        "device_contacts": 0,
        "product_acceptance_operations": [
            "canonical(candidate linked-ELF layout bytes) == "
            "SHA-bound golden bytes",
        ],
        "card_path_gate": gate,
        "authority": {
            "golden": bind(GOLD.GOLDEN),
            "historical_first_red": bind(HISTORICAL_FIRST_RED),
            "owner_disposition": approval,
            "driver": bind(DRIVER),
        },
        "terminal_clause": (
            "Any replacement-card red of any class parks Priority 1 finally; "
            "no exception or further card exists."),
    }
    PREFLIGHT_RECEIPT.write_bytes(canonical(value))
    print("c2-golden-layout-replacement-card: PREFLIGHT PASS "
          "preconditions=0 mutations=6 card=one exception=none")


def replacement_card() -> None:
    require(PREFLIGHT_RECEIPT.is_file()
            and load(PREFLIGHT_RECEIPT)["status"]
                == "PASS: exactly one exceptionless replacement card armed",
            "green replacement preflight required")
    require(load(PREFLIGHT_RECEIPT)["authority"]["driver"] == bind(DRIVER),
            "replacement driver changed after preflight")
    require(not BUILD.exists() and not INVOCATION.exists()
            and not RECEIPT.exists() and not FINAL_RED.exists(),
            "replacement product card is one-shot")
    INVOCATION.write_bytes(canonical({
        "format": "lisp65-c2.3-golden-layout-replacement-invocation-v1",
        "recorded_on": RECORDED_ON,
        "status": "INVOKED: terminal outcome required",
        "owner_disposition": owner_disposition(),
        "driver": bind(DRIVER),
    }))
    configure_replacement()
    artifacts = produce_candidate()
    comparison = GOLD.compare_elf(artifacts["elf"])
    value = {
        "format": "lisp65-c2.3-golden-layout-replacement-product-card-v1",
        "recorded_on": RECORDED_ON,
        "status": "PASS: replacement card equals golden layout",
        "promotable": False,
        "wplto_probes_consumed": 1,
        "product_links": 0,
        "device_contacts": 0,
        "acceptance": {
            **comparison,
            "operations": 1,
            "non_geometric_product_preconditions": 0,
            "external_checker_vocabularies": 0,
            "historical_postlink_status_consumed": False,
        },
        "producer": {
            "mechanical_completion_only": True,
            "historical_closer_return_nonauthoritative":
                artifacts["producer_return"],
            "log": bind(artifacts["producer_log"]),
            "static_product": bind(artifacts["static_product"]),
            "bank2": bind(artifacts["bank2"]),
            "target_stdlib_header": artifacts["target_stdlib_header"],
        },
        "artifacts": {
            key: bind(artifacts[key])
            for key in ("elf", "map", "prg", "lto", "linker")
        },
        "card_path_gate": path_gate(),
        "authority": {
            "golden": bind(GOLD.GOLDEN),
            "historical_first_red": bind(HISTORICAL_FIRST_RED),
            "preflight": bind(PREFLIGHT_RECEIPT),
            "invocation": bind(INVOCATION),
            "owner_disposition": owner_disposition(),
            "driver": bind(DRIVER),
        },
        "next_gate": (
            "Owner Halt: reopen 1.5 Halt 2, the preserved parity pilot and "
            "Link 91. No device action ran."),
        "claim_limit": (
            "One host-only non-promotable replacement WPLTO accepted solely "
            "by exact golden-layout equality; no Link 91, device, parity "
            "surface, product promotion or release claim."),
    }
    RECEIPT.write_bytes(canonical(value))
    print("c2-golden-layout-replacement-card: PASS "
          f"sections={comparison['allocatable_sections']} "
          f"boundaries={comparison['boundary_symbols']} "
          "comparison=byte-identical wplto=1 device=0")


def record_final_red(error: BaseException) -> None:
    require(not RECEIPT.exists() and not FINAL_RED.exists(),
            "replacement terminal result is immutable")
    artifacts: dict[str, dict[str, Any]] = {}
    for name, relative in {
        "seed_lto": "wplto/resident-island-seed.prg.lto.o",
        "seed_elf": "wplto/resident-island-seed.prg.elf",
        "candidate_lto": "wplto/lisp65-c2-substitution-linked.prg.lto.o",
        "candidate_elf": "wplto/lisp65-c2-substitution-linked.prg.elf",
        "candidate_map": "wplto/lisp65-c2-substitution-linked.prg.map",
        "linker": "wplto/c2-substitution.ld",
    }.items():
        path = BUILD / relative
        if path.is_file():
            artifacts[name] = bind(path)
    candidate = BUILD / "wplto/lisp65-c2-substitution-linked.prg.elf"
    value = {
        "format": "lisp65-c2.3-golden-layout-replacement-final-red-v1",
        "recorded_on": RECORDED_ON,
        "status": "FINAL RED: Priority 1 parked finally and unappealably",
        "error": {"type": type(error).__name__, "message": str(error)},
        "replacement_card_invoked": INVOCATION.is_file(),
        "wplto_started": any("lto" in key for key in artifacts),
        "wplto_probes_consumed": int(any("lto" in key for key in artifacts)),
        "linked_candidate_elf_emitted": candidate.is_file(),
        "golden_comparison_green": False,
        "retry_authorized": False,
        "final_park_required": True,
        "device_contacts": 0,
        "artifacts": artifacts,
        "authority": {
            "golden": bind(GOLD.GOLDEN),
            "historical_first_red": bind(HISTORICAL_FIRST_RED),
            "preflight": bind(PREFLIGHT_RECEIPT),
            "invocation": bind(INVOCATION),
            "owner_disposition": owner_disposition(),
            "driver": bind(DRIVER),
        },
        "claim_limit": (
            "The sole exceptionless replacement card is consumed. Priority "
            "1 is finally parked; no retry, Link 91 or device action."),
    }
    FINAL_RED.write_bytes(canonical(value))


def selftest() -> None:
    require(HISTORICAL_FIRST_RED.is_file(),
            "historical pre-inversion First Red absent")
    owner_disposition()
    gate = path_gate()
    require(gate["audit"]["non_geometric_product_preconditions"] == 0
            and gate["audit"]["golden_comparisons"] == 1
            and gate["mutation_witness"]["mutations"] == 6,
            "replacement-card path gate drift")
    print("c2-golden-layout-replacement-card: SELFTEST PASS "
          "preconditions=0 golden=1 mutations=6")


def check() -> None:
    selftest()
    require(not (RECEIPT.is_file() and FINAL_RED.is_file()),
            "replacement card has two terminal outcomes")
    if not RECEIPT.is_file() and not FINAL_RED.is_file():
        require(not INVOCATION.is_file(),
                "replacement invocation lacks a terminal outcome")
        print("c2-golden-layout-replacement-card: CHECK ARMED "
              "card=unused outcome=pending")
        return
    if FINAL_RED.is_file():
        value = load(FINAL_RED)
        require(value["retry_authorized"] is False
                and value["final_park_required"] is True,
                "replacement final-red disposition drift")
        print("c2-golden-layout-replacement-card: CHECK FINAL RED "
              "retry=none priority1=parked")
        return
    value = load(RECEIPT)
    require(value["status"]
            == "PASS: replacement card equals golden layout"
            and value["wplto_probes_consumed"] == 1
            and value["device_contacts"] == 0
            and value["acceptance"]["non_geometric_product_preconditions"]
                == 0,
            "green replacement-card receipt drift")
    candidate = ROOT / value["artifacts"]["elf"]["path"]
    comparison = GOLD.compare_elf(candidate)
    require(comparison["candidate_layout_sha256"] == GOLD.GOLDEN_SHA256,
            "persisted replacement candidate/golden comparison drift")
    print("c2-golden-layout-replacement-card: CHECK PASS "
          "comparison=byte-identical card=consumed retry=none device=0")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "mode", choices=("selftest", "preflight", "card", "check"))
    args = parser.parse_args()
    if args.mode == "selftest":
        selftest()
    elif args.mode == "preflight":
        preflight()
    elif args.mode == "card":
        replacement_card()
    else:
        check()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        ReplacementCardError, GOLD.GoldenLayoutError, V18.RepairCardError,
        V18.BASE.CardError, V18.BASE.JOINT.WPLTOError,
        OSError, KeyError, ValueError, json.JSONDecodeError,
        V18.subprocess.CalledProcessError,
    ) as error:
        if len(sys.argv) > 1 and sys.argv[1] == "card":
            try:
                record_final_red(error)
            except Exception as receipt_error:  # never mask the terminal red
                print("c2-golden-layout-replacement-card: receipt failure: "
                      f"{receipt_error}", file=sys.stderr)
        print(f"c2-golden-layout-replacement-card: FINAL RED: {error}",
              file=sys.stderr)
        raise SystemExit(2)
