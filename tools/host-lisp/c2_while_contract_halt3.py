#!/usr/bin/env python3
"""Bind the Phase-V2 while contract for owner Halt #3."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import tempfile
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "config/c2-while-contract.json"
NOTE = ROOT / "docs/planning/c2.2-v2-while-contract-halt3.md"
PAPER = ROOT / "config/c2-control-flow-repair-decision.json"
PAPER_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-f5-while-catch-throw-design-probe-receipt.json"
)
LINK76 = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-product-link76-require-fastpath-irq-ownership-structural-receipt.json"
)
VM_H = ROOT / "src/vm.h"
VM_C = ROOT / "src/vm.c"
EVAL_C = ROOT / "src/eval.c"
COMPILE_C = ROOT / "src/compile.c"
COMPILE_PY = ROOT / "tools/host-lisp/bytecode_p0_compiler.py"
LCC = ROOT / "lib/lcc.lisp"
LCC_PROFILE = ROOT / "lib/dialect-v2/lcc-profile.lisp"
MIGRATION = ROOT / "config/dialect-migration-contract.json"
SURFACE = ROOT / "config/dialect-v2-surface.json"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-v2-while-contract-halt3-receipt.json"
)


class GateError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise GateError(message)


def load(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"authority absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"bound input absent: {path}")
    data = path.read_bytes()
    return {
        "path": path.resolve().relative_to(ROOT.resolve()).as_posix(),
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def atomic_json(path: Path, value: dict[str, Any]) -> None:
    payload = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(payload)
    temporary.replace(path)


def validate_contract(contract: dict[str, Any]) -> dict[str, Any]:
    scope = contract["scope"]
    syntax = contract["syntax"]
    semantics = contract["semantics"]
    lowering = contract["lowering"]
    views = contract["execution_views"]
    proofs = contract["required_proofs"]
    capacity = contract["capacity_policy"]
    require(
        contract["format"] == "lisp65-c2-while-product-contract-v1"
        and contract["status"]
        == "awaiting-owner-halt3-review-implementation-not-authorized"
        and scope == {
            "phase": "V2",
            "surface": "while",
            "product_source_changes_authorized": 0,
            "product_links_authorized": 0,
            "hardware_runs": 0,
            "performance_claim": "none",
        },
        "while Halt-3 scope drift",
    )
    require(
        contract["taxonomy"]["class"] == "structured local iteration"
        and contract["taxonomy"]["not"] == "non-local exit"
        and syntax["form"] == "(while test form*)"
        and syntax["minimum_arguments"] == 1
        and semantics["result"] == "NIL after normal termination"
        and "every other object continues" in semantics["truth"]
        and "every body value is discarded" in semantics["body"]
        and "RUN/STOP remains observable" in semantics["empty_body"],
        "while surface/semantic drift",
    )
    require(
        lowering["bytecode"] == [
            "loop_start",
            "compile test",
            "JFALSEREL loop_exit",
            "compile each body form followed by DROP",
            "JMPREL loop_start",
            "loop_exit: PUSHNIL",
        ]
        and lowering["relative_branch_domain"]
        == {
            "minimum": -128,
            "maximum": 127,
            "exact_meets": (
                "both -128 and 127 are legal; values outside fail "
                "compilation closed"
            ),
        }
        and all(lowering[key] == 0 for key in (
            "new_vm_opcodes", "new_runtime_state",
            "new_resident_gc_roots", "new_c2j_fields",
            "new_runtime_overlay_records",
        )),
        "while lowering/runtime-state drift",
    )
    require(
        set(views) == {
            "native_treewalk", "native_bytecode_compiler",
            "host_bytecode_compiler", "device_lcc", "vm",
        }
        and "product-bound compiler carrier" in views["device_lcc"]
        and len(proofs["parity"]) == 4
        and len(proofs["binding"]) == 3,
        "while execution-view or binding proof drift",
    )
    require(
        capacity["no_geometry_renegotiation"] is True
        and "32 bytes text noise reserve" in capacity["resident"]
        and "54-byte E000 floor" in capacity["resident"]
        and "park while" in capacity["first_red"],
        "while terminal-geometry policy drift",
    )
    require(
        len(contract["excluded"]) == 10
        and "catch" in contract["excluded"]
        and "throw" in contract["excluded"]
        and "reuse of C2J as a Lisp unwind stack" in contract["excluded"],
        "while exclusion boundary drift",
    )
    return {
        "status": "passed-complete-while-product-contract",
        "syntax": syntax["form"],
        "result": semantics["result"],
        "execution_seams": list(views),
        "parity_views": list(proofs["parity"]),
        "rel8_domain": [-128, 127],
        "new_vm_opcodes": 0,
        "new_runtime_state": 0,
        "geometry_renegotiation": False,
    }


def validate_preimplementation() -> dict[str, Any]:
    paper = load(PAPER)
    paper_receipt = load(PAPER_RECEIPT)
    link76 = load(LINK76)
    vm_h = VM_H.read_text(encoding="utf-8")
    vm_c = VM_C.read_text(encoding="utf-8")
    eval_c = EVAL_C.read_text(encoding="utf-8")
    compile_c = COMPILE_C.read_text(encoding="utf-8")
    compile_py = COMPILE_PY.read_text(encoding="utf-8")
    lcc = LCC.read_text(encoding="utf-8")
    profile = LCC_PROFILE.read_text(encoding="utf-8")
    migration = load(MIGRATION)
    surface = load(SURFACE)

    require(
        paper["decision"]["selected"] == "while"
        and paper["taxonomy"]["correction"]
        == "while is structured local iteration, not a non-local-exit primitive"
        and paper_receipt["status"]
        == "passed-owner-accepted-paper-decision",
        "accepted F5 paper authority drift",
    )
    require(
        "OP_JMPREL=28" in vm_h
        and "OP_JFALSEREL=29" in vm_h
        and "case OP_JMPREL:" in vm_c
        and "case OP_JFALSEREL:" in vm_c,
        "existing VM branch ABI absent",
    )
    require(
        "static void compile_dotimes" in compile_c
        and "static void compile_dolist" in compile_c
        and "rel < -128 || rel > 127" in compile_c
        and 'op_is(op, "while")' not in compile_c,
        "native compiler baseline or preimplementation boundary drift",
    )
    require(
        "def compile_dotimes" in compile_py
        and "def compile_dolist" in compile_py
        and 'self.patch_rel8(back_op + 1, loop_start, context="dotimes")'
        in compile_py
        and 'op == "while"' not in compile_py,
        "host compiler baseline or preimplementation boundary drift",
    )
    require(
        "if (op == sf_dotimes || op == sf_dolist)" in eval_c
        and "loop_body(body, newenv);" in eval_c
        and "lisp_poll();   /* RUN/STOP auch bei leerem Body */" in eval_c
        and "sf_while" not in eval_c,
        "treewalk flat-loop baseline or preimplementation boundary drift",
    )
    require(
        "(defun %lcc-do-loop" in lcc
        and "'jfalserel" in lcc
        and "'jmprel" in lcc
        and "(if (< d -127)" in lcc
        and "(eq op 'while)" not in lcc
        and "(eq op 'while)" not in profile,
        "device-LCC loop baseline or rel8 correction witness absent",
    )
    special = migration["syntax"]["special_forms_current"]
    target = migration["syntax"]["special_forms_target"]
    names = [row["name"] for row in surface["definitions"]]
    require(
        "while" not in special
        and "while" not in target
        and "while" not in names,
        "while leaked into public inventories before owner authorization",
    )
    parity = link76["bound_artifact_source_parity"]
    require(
        link76["status"]
        == "passed-Link76-require-fastpath-and-strict-IRQ-ownership-hardware-not-run"
        and parity["status"]
        == "passed-source-to-actual-product-bound-artifact-parity"
        and parity["compiler_carrier"]["status"]
        == "passed-current-source-to-generated-tier-to-carrier"
        and parity["inventory"]["uncovered_classes"] == 0,
        "Link-76 bound-carrier baseline drift",
    )
    return {
        "status": "passed-real-four-view-preimplementation-baseline",
        "paper_decision": "while",
        "existing_vm_branch_opcodes": [28, 29],
        "native_treewalk_witness": "dotimes/dolist flat C loop plus empty-body poll",
        "native_compiler_witness": "dotimes/dolist rel8 lowering",
        "host_compiler_witness": "dotimes/dolist rel8 lowering",
        "device_lcc_witness": "native do-family constant-stack loop",
        "required_lcc_boundary_correction": "-128 exact meet is currently rejected",
        "bound_carrier_gate": parity["status"],
        "while_currently_absent": True,
    }


def mutation_tests(contract: dict[str, Any]) -> dict[str, str]:
    rejected: dict[str, str] = {}

    def reject(label: str, change: Callable[[dict[str, Any]], None]) -> None:
        candidate = copy.deepcopy(contract)
        change(candidate)
        try:
            validate_contract(candidate)
        except GateError as error:
            rejected[label] = str(error)
        else:
            raise GateError(f"while contract mutation survived: {label}")

    reject("implementation-preauthorized", lambda c: c["scope"].update(
        product_source_changes_authorized=1))
    reject("hardware-preauthorized", lambda c: c["scope"].update(
        hardware_runs=1))
    reject("non-local-misclassification", lambda c: c["taxonomy"].update(
        **{"class": "non-local exit"}))
    reject("test-optional", lambda c: c["syntax"].update(minimum_arguments=0))
    reject("last-value-result", lambda c: c["semantics"].update(
        result="last body value"))
    reject("nil-only-truth", lambda c: c["semantics"].update(
        truth="only T continues"))
    reject("body-value-leak", lambda c: c["semantics"].update(
        body="body values remain on the operand stack"))
    reject("rel8-minus-128-rejected", lambda c: c["lowering"][
        "relative_branch_domain"].update(minimum=-127))
    reject("new-opcode", lambda c: c["lowering"].update(new_vm_opcodes=1))
    reject("missing-device-lcc", lambda c: c["execution_views"].pop(
        "device_lcc"))
    reject("geometry-negotiable", lambda c: c["capacity_policy"].update(
        no_geometry_renegotiation=False))
    reject("catch-smuggled-in", lambda c: c["excluded"].remove("catch"))
    return rejected


def main() -> int:
    try:
        contract = load(CONTRACT)
        contract_proof = validate_contract(contract)
        baseline = validate_preimplementation()
        mutations = mutation_tests(contract)
        receipt = {
            "format": "lisp65-c2.2-v2-while-contract-halt3-receipt-v1",
            "recorded_on": "2026-07-28",
            "status": "passed-awaiting-owner-halt3-review",
            "promotable": False,
            "product_links": 0,
            "hardware_runs": 0,
            "implementation_authorized": False,
            "contract": contract_proof,
            "preimplementation_evidence": baseline,
            "mutations_rejected": mutations,
            "authority": {
                "contract": bind(CONTRACT),
                "review_note": bind(NOTE),
                "paper_decision": bind(PAPER),
                "paper_receipt": bind(PAPER_RECEIPT),
                "Link76": bind(LINK76),
                "vm_h": bind(VM_H),
                "vm_c": bind(VM_C),
                "eval_c": bind(EVAL_C),
                "native_compiler": bind(COMPILE_C),
                "host_compiler": bind(COMPILE_PY),
                "lcc": bind(LCC),
                "lcc_profile": bind(LCC_PROFILE),
                "migration_contract": bind(MIGRATION),
                "surface": bind(SURFACE),
                "gate": bind(Path(__file__)),
            },
            "owner_decision": (
                "Accept or reject the complete V2 while contract. A yes "
                "authorizes implementation and one WPLTO, not a link."
            ),
            "claim_limit": (
                "Contract and real preimplementation authority only. No "
                "while implementation, capacity, product-link or hardware "
                "claim."
            ),
        }
        atomic_json(RECEIPT, receipt)
        print(
            "c2-while-contract-halt3: PASS "
            f"views={len(contract_proof['parity_views'])} "
            f"mutations={len(mutations)} implementation=0 link=0 hardware=0"
        )
        return 0
    except (GateError, KeyError, OSError, ValueError) as error:
        print(f"c2-while-contract-halt3: FIRST RED: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
