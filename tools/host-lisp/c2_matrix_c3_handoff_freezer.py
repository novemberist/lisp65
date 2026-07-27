#!/usr/bin/env python3
"""Qualify C3's owner-qualified H0-H3 handoff state machine."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ADDENDA = ROOT / "config/c2-cross-invariant-c2.2-open-addenda.json"
REVIEW = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-cross-invariant-b3-c3-d3-e5-contract-review-receipt.json")
STRUCTURAL = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-product-link57-keymap-nullary-fast-path2-structural-receipt.json")
ELF = ROOT / (
    "build/c2.2/substitution/product-link-57-keymap-nullary-fast-path2/"
    "lisp65-c2-substitution-linked.prg.elf")
RUNTIME = ROOT / "src/c2_kernal_runtime.c"
WINDOW = ROOT / "src/c2_kernal_window.s"
CORE = ROOT / "build/upstream-verification/mega65-core"
CORE_CPU = CORE / "src/vhdl/gs4510.vhdl"
CORE_TASK = CORE / "src/hyppo/task.asm"
CORE_FREEZE = CORE / "src/hyppo/freeze.asm"
CORE_UNFREEZE = CORE / "src/hyppo/syspart.asm"
OUT = ROOT / "build/c2.2/matrix-c3-handoff-freezer"
PLAN = OUT / "hardware-cutpoint-plan.json"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-link58-matrix-c3-handoff-freezer-source-replay-receipt.json")

EXPECTED = {
    ADDENDA: "73aa314bc1a8f9dceaa3e0ce144262335dd197503ea11afca2356d5b67671777",
    REVIEW: "1d3e203390460efb08a8d479b0dc753a742afb6ff5346c78c2446dfa5a7708c8",
    STRUCTURAL: "6632a7d00ea3bfaef294924ea618e0af70e34b75da929de05b2e7c451ce26059",
    ELF: "306ba2aca61bbd2b924f3b52fd03fbbd9db95330f9c81e1190329abc147bf950",
    CORE_CPU: "ce8c7f120aac11e142add5e08e9a83dc9450b813b211bf310cb95553b4eae957",
    CORE_TASK: "07497c4738023639300c7119e178c9a6233830026a017636fa840020472c9894",
    CORE_FREEZE: "fd5f4cbd7c2c594388895293007055050e6c73a00fb6d423ff45b47bb51b58cd",
    CORE_UNFREEZE: "b436f778ab9232f81ccd78b3cb45dbda3181c838b113387b1b7844946c57bf74",
}
CORE_COMMIT = "a9158930665763c592d004c895d52eff4a9eefc3"


class GateError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise GateError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def write_bound(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        require(path.read_bytes() == data,
                f"refusing to overwrite divergent artifact: {path}")
    else:
        path.write_bytes(data)
    os.chmod(path, 0o444)


def function_body(source: str, name: str) -> str:
    match = re.search(r"\b" + re.escape(name) + r"\s*:[^\n]*\n", source)
    require(match is not None, f"assembler function absent: {name}")
    tail = source[match.start():]
    next_section = tail.find("\n\t.section", 1)
    return tail if next_section < 0 else tail[:next_section]


def core_gate() -> dict[str, Any]:
    commit = subprocess.run(
        ["git", "-C", str(CORE), "rev-parse", "HEAD"],
        cwd=ROOT, text=True, capture_output=True, check=True).stdout.strip()
    require(commit == CORE_COMMIT, "pinned mega65-core commit drift")
    cpu = CORE_CPU.read_text(encoding="utf-8")
    task = CORE_TASK.read_text(encoding="utf-8")
    unfreeze = CORE_UNFREEZE.read_text(encoding="utf-8")
    freeze = CORE_FREEZE.read_text(encoding="utf-8")
    require("Trap #66 ($42) = RESTORE key double-tap" in cpu,
            "Freezer trap 0x42 identity drift")
    require("restore_press_trap:" in task and "jsr freeze_to_slot" in task,
            "Freezer entry path drift")
    require("@unfreezesyncwait:" in unfreeze
            and "sta hypervisor_enterexit_trigger" in unfreeze,
            "Freezer return-before-resume path drift")
    require("384KB RAM" in freeze and "!8 6" in freeze,
            "Freezer full guest-RAM domain drift")
    return {
        "commit": commit,
        "freezer": "hypervisor-trap-0x42-at-instruction-boundary",
        "guest_nmi": "independent-CPU-vector-source",
        "classification_equal": False,
        "SEI_masks_guest_NMI": False,
        "restore_before_resume": True,
    }


def source_gate(runtime: str, window: str) -> dict[str, Any]:
    handoff_match = re.search(
        r"C2K_SECTION uint8_t c2_kernal_take_ownership\(void\) \{",
        runtime)
    require(handoff_match is not None, "handoff root absent")
    handoff = runtime[handoff_match.start():]
    sequence = (
        '__asm__ volatile("sei\\n\\tldz #0"',
        "c2_kernal_reveal_io();",
        "VIC_D01A = 0u;",
        "c2k_copy(",
        "c2_kernal_map_window();",
        "if (c2k_crc16(",
        "C2K_MAP_GENERATION = 1u;",
        "C2K_STATE = C2K_STATE_PRODUCT;",
        "VIC_D01A = 0x01u;",
        '__asm__ volatile("cli"',
    )
    positions = [handoff.find(token) for token in sequence]
    require(all(at >= 0 for at in positions)
            and positions == sorted(positions),
            "handoff sequence does not establish H1/H2/H3 in order")
    nmi = function_body(window, "c2_kernal_nmi_handler")
    require(
        all(token in nmi for token in (
            "pha", "lda $dd0d", "inc C2K_NMI_COUNT", "pla", "rti")),
        "owned NMI handler seam drift")
    require(not re.search(r"\b(?:jsr|jmp)\b", nmi)
            and not any(token in nmi for token in (
                "lisp", "alloc", "emit", "c2_product")),
            "owned NMI reaches evaluator/allocation/call surface")
    vector = window[window.index(
        ".section .lisp65_c2_vectors"):]
    require(
        vector.count(".word") == 3
        and ".word c2_kernal_nmi_handler" in vector
        and ".word c2_kernal_fail_closed" in vector
        and ".word c2_kernal_irq_handler" in vector,
        "complete owned vector table drift")
    return {
        "status": "passed",
        "handoff_sequence": list(sequence),
        "H1": {
            "begin": "SEI+LDZ",
            "end": "MAP commit",
            "product_state_published": False,
        },
        "H2": {
            "begin": "MAP commit",
            "end": "C2K_STATE_PRODUCT publication",
            "product_state_published": False,
        },
        "H3": {
            "begin": "C2K_STATE_PRODUCT publication",
            "owned_irq_enable": "after-publication",
        },
        "nmi": {
            "acknowledgement": "CIA2 ICR read",
            "A": "PHA/PLA preserved",
            "X_Y_Z": "not touched",
            "P_PC": "hardware frame restored by RTI",
            "Lisp_edges": 0,
            "allocation_edges": 0,
        },
    }


def owner_rows(addenda: dict[str, Any]) -> list[dict[str, Any]]:
    rows = deepcopy(addenda["C3"]["cutpoints"])
    require([row["id"] for row in rows] == ["H0", "H1", "H2", "H3"],
            "C3 cutpoint order drift")
    return rows


def validate_rows(rows: list[dict[str, Any]], *,
                  freezer_is_nmi: bool = False,
                  sei_masks_nmi: bool = False,
                  accept_wrong_generation: bool = False,
                  vector_target_ready: bool = True) -> list[str]:
    errors: list[str] = []
    expected = {
        "H0": ("firmware", "firmware", "firmware", "firmware-owned"),
        "H1": ("firmware", "firmware", "firmware", "replacement-armed"),
        "H2": ("C2", "C2", "C2", "handoff-closed"),
        "H3": ("C2", "C2", "C2", "product-owned"),
    }
    for row in rows:
        actual = (
            row["map_owner"], row["vector_owner"], row["nmi_owner"],
            row["published_state"])
        if actual != expected[row["id"]]:
            errors.append(f"{row['id']}:owner-tuple")
        continuation = row["only_legal_continuation"]
        if row["id"] in ("H0", "H1", "H2") and \
                "evaluator" in continuation and "no product vector" not in continuation:
            errors.append(f"{row['id']}:evaluator-continuation")
        if row["id"] == "H3" and "identity-specific" not in continuation:
            errors.append("H3:identity-verifier-absent")
    if freezer_is_nmi:
        errors.append("freezer-routed-through-guest-NMI")
    if sei_masks_nmi:
        errors.append("SEI-treated-as-NMI-mask")
    if accept_wrong_generation:
        errors.append("wrong-map-generation-accepted")
    if not vector_target_ready:
        errors.append("vector-published-before-target")
    return errors


def mutation_gate(rows: list[dict[str, Any]]) -> dict[str, str]:
    trials: dict[str, tuple[list[dict[str, Any]], dict[str, bool]]] = {}
    trials["treat-SEI-as-NMI-mask"] = (
        deepcopy(rows), {"sei_masks_nmi": True})
    trials["route-Freezer-through-guest-NMI"] = (
        deepcopy(rows), {"freezer_is_nmi": True})
    h1 = deepcopy(rows)
    h1[1]["published_state"] = "product-owned"
    trials["publish-product-owned-at-H1"] = (h1, {})
    h2 = deepcopy(rows)
    h2[2]["only_legal_continuation"] = "resume evaluator directly"
    trials["resume-evaluator-from-H2"] = (h2, {})
    trials["accept-wrong-map-generation"] = (
        deepcopy(rows), {"accept_wrong_generation": True})
    trials["accept-vector-before-target"] = (
        deepcopy(rows), {"vector_target_ready": False})
    rejected: dict[str, str] = {}
    for label, (trial_rows, flags) in trials.items():
        require(validate_rows(trial_rows, **flags),
                f"C3 mutation survived: {label}")
        rejected[label] = "rejected"
    return rejected


def hardware_plan(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "format": "lisp65-c2.2-c3-freezer-cutpoint-hardware-plan-v1",
        "recorded_on": "2026-07-23",
        "status": "authorized-not-built-until-successor-ELF-is-green",
        "identity_rule": (
            "Every carrier is non-promotable and SHA-bound to the exact "
            "successor ELF. Patch offsets are derived only after WPLTO/link."),
        "runs": [
            {
                "id": "H1-H2-bundled",
                "cutpoints": ["H1", "H2"],
                "method": (
                    "deterministic hold inside the named interval; physical "
                    "Freezer roundtrip; resume only into the interval verifier"),
                "accept": (
                    "exact owner tuple, same-interval continuation, no "
                    "evaluator edge and subsequent transition checks fresh"),
            },
            {
                "id": "H3-product-roundtrip",
                "cutpoints": ["H3"],
                "method": (
                    "identity-specific Freezer roundtrip over E000, vector "
                    "table, map generation and both Chip planes"),
                "accept": "all regions byte-identical and evaluator resumes",
            },
        ],
        "cutpoint_contract": rows,
        "skip_rule": (
            "A cutpoint not deterministically reachable on the pinned core "
            "remains OPEN with the exact limitation; it is never inferred."),
        "xemu": "non-authoritative-and-not-a-Freezer-PASS",
    }


def build_receipt() -> dict[str, Any]:
    for path, expected in EXPECTED.items():
        require(path.is_file() and sha(path) == expected,
                f"bound C3 authority drift: {path}")
    addenda = json.loads(ADDENDA.read_text(encoding="utf-8"))
    rows = owner_rows(addenda)
    require(not validate_rows(rows), "approved C3 owner table is invalid")
    source = source_gate(
        RUNTIME.read_text(encoding="utf-8"),
        WINDOW.read_text(encoding="utf-8"))
    core = core_gate()
    mutations = mutation_gate(rows)
    require(len(mutations) == 6, "C3 mutation count drift")
    plan = hardware_plan(rows)
    write_bound(PLAN, canonical(plan))
    return {
        "format": "lisp65-c2.2-matrix-c3-handoff-freezer-host-fixture-v1",
        "recorded_on": "2026-07-23",
        "status": "passed-host-owner-matrix-awaiting-hardware-cutpoints",
        "row": "C3",
        "platform_distinction": core,
        "owner_matrix": rows,
        "source_gate": source,
        "continuation_cardinality": {
            row["id"]: 1 for row in rows
        },
        "forbidden_evaluator_edges_H0_H2": 0,
        "mutations": mutations,
        "hardware_plan": bind(PLAN),
        "authorities": {
            "approved_addenda": bind(ADDENDA),
            "line_review_receipt": bind(REVIEW),
            "link57_structural_receipt": bind(STRUCTURAL),
            "link57_elf": bind(ELF),
            "handoff_source": bind(RUNTIME),
            "window_source": bind(WINDOW),
            "core_cpu": bind(CORE_CPU),
            "core_task": bind(CORE_TASK),
            "core_freeze": bind(CORE_FREEZE),
            "core_unfreeze": bind(CORE_UNFREEZE),
        },
        "execution": {
            "host_owner_tuples": 4,
            "mutations": 6,
            "whole_program_lto_runs": 0,
            "product_links": 0,
            "hardware_runs": 0,
        },
        "claim_limit": (
            "Proves the H0-H3 owner/continuation model, product source "
            "ordering, guest-NMI closure and Freezer/NMI distinction. C3 "
            "remains OPEN until every deterministically reachable H1/H2/H3 "
            "hardware cutpoint is green on the successor identity. No "
            "acceptance or promotion is claimed."),
        "value_string": (
            "C3=host-green owners=4/4 continuations=1-each "
            "freezer!=guest-NMI mutations=6/6 hardware=H1/H2/H3-pending "
            "acceptance=blocked"),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("write", "check"))
    args = parser.parse_args()
    try:
        value = build_receipt()
        data = canonical(value)
        if args.action == "write":
            if RECEIPT.exists():
                require(RECEIPT.read_bytes() == data,
                        "refusing to overwrite divergent C3 receipt")
            else:
                RECEIPT.parent.mkdir(parents=True, exist_ok=True)
                RECEIPT.write_bytes(data)
            os.chmod(RECEIPT, 0o444)
            verb = "WROTE"
        else:
            require(RECEIPT.is_file() and RECEIPT.read_bytes() == data,
                    "C3 receipt absent or drifted")
            verb = "CHECK PASS"
        print(
            "c2-matrix-c3-handoff-freezer: "
            f"{verb} owners=4/4 mutations=6/6 hardware=H1/H2/H3-pending")
        return 0
    except (GateError, OSError, KeyError, ValueError,
            json.JSONDecodeError, subprocess.CalledProcessError) as exc:
        print("c2-matrix-c3-handoff-freezer: FAIL " + str(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
