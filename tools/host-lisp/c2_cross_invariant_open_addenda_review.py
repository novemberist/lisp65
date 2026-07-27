#!/usr/bin/env python3
"""Bind the B3/C3/D3/E5 C2.2 addenda as a paper-only review package."""

from __future__ import annotations

import copy
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "config/c2-cross-invariant-c2.2-open-addenda.json"
DOCUMENT = ROOT / "docs/planning/c2.2-cross-invariant-open-addenda.md"
MATRIX = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-cross-invariant-full-matrix-link57-review-receipt.json"
)
KERNAL = ROOT / "config/c2-kernal-unmap-contract.json"
DMA = ROOT / "config/c2-runtime-overlay-dma-completion-contract.json"
NESTED = ROOT / "config/c2-nested-append-unwind-contract.json"
ERRORS = ROOT / "config/error-texts.json"
ERROR_H = ROOT / "src/error_codes.h"
INTERRUPT = ROOT / "src/interrupt.c"
WINDOW = ROOT / "src/c2_kernal_window.s"
PRODUCT = ROOT / "src/c2_product_runtime.c"
CORE = ROOT / "build/upstream-verification/mega65-core"
CORE_MATRIX = CORE / "src/vhdl/matrix_to_ascii.vhdl"
CORE_MAPPER = CORE / "src/vhdl/keymapper.vhdl"
CORE_IOMAPPER = CORE / "src/vhdl/iomapper.vhdl"
CORE_UART = CORE / "src/vhdl/c65uart.vhdl"
CORE_CPU = CORE / "src/vhdl/gs4510.vhdl"
CORE_TASK = CORE / "src/hyppo/task.asm"
CORE_UNFREEZE = CORE / "src/hyppo/syspart.asm"
CORE_COMMIT = "a9158930665763c592d004c895d52eff4a9eefc3"
PRG = ROOT / (
    "build/c2.2/substitution/product-link-57-keymap-nullary-fast-path2/"
    "lisp65-c2-substitution-linked.prg"
)
ELF = Path(str(PRG) + ".elf")
OUT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-cross-invariant-b3-c3-d3-e5-contract-review-receipt.json"
)


class ReviewError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ReviewError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"{path.relative_to(ROOT)} is not an object")
    return value


def binding(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"binding absent: {path.relative_to(ROOT)}")
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def text(path: Path) -> str:
    require(path.is_file(), f"source absent: {path.relative_to(ROOT)}")
    return path.read_text(encoding="utf-8")


def validate_contract(value: dict[str, Any]) -> None:
    require(value.get("format") == "lisp65-c2.2-cross-invariant-open-addenda-v1",
            "contract format drift")
    require(value.get("status") == "draft-for-class-c-line-review-no-product-authorization",
            "contract status overclaims review or implementation")
    scope = value.get("scope", {})
    require(scope.get("matrix_rows") == ["B3", "C3", "D3", "E5"],
            "row inventory/order drift")
    identity = scope.get("product_identity", {})
    require(identity == {
        "link": 57,
        "prg_sha256": "7d568ceb7edab95a237ff3079fcf689768373a9ea48a5a43f355f6275ddc5df8",
        "elf_sha256": "306ba2aca61bbd2b924f3b52fd03fbbd9db95330f9c81e1190329abc147bf950",
    }, "Link-57 identity drift")

    b3 = value.get("B3", {})
    require(b3.get("decision") == "defer-exactly-once-to-first-safe-evaluator-boundary",
            "B3 decision drift")
    b3_states = b3.get("transport_state_machine", [])
    require([row.get("state") for row in b3_states] == [
        "pre-submit", "submitted-unproved", "content-proved",
        "safe-evaluator-boundary",
    ], "B3 transport state order drift")
    require("forbidden" in b3_states[1].get("poll_or_longjmp", "")
            and b3_states[3].get("break_action", "").startswith("consume the one"),
            "B3 non-local-exit boundary drift")
    require(b3.get("fixture", {}).get("cutpoints") == [
        "immediately-before-submit",
        "after-submit-before-first-content-proof",
        "during-convergence-after-at-least-one-mismatch",
        "after-content-match-before-seam-return",
        "first-safe-evaluator-boundary",
    ], "B3 cutpoint inventory drift")

    c3 = value.get("C3", {})
    require(c3.get("decision") == "owner-qualified-cutpoints-and-exact-continuation-only",
            "C3 decision drift")
    require(c3.get("platform_distinction", {}).get("rule", "").startswith(
        "Freezer and guest NMI are separate"), "C3 Freezer/NMI distinction drift")
    cutpoints = c3.get("cutpoints", [])
    require([row.get("id") for row in cutpoints] == ["H0", "H1", "H2", "H3"],
            "C3 cutpoint inventory drift")
    require([(row.get("map_owner"), row.get("vector_owner"),
              row.get("nmi_owner")) for row in cutpoints] == [
        ("firmware", "firmware", "firmware"),
        ("firmware", "firmware", "firmware"),
        ("C2", "C2", "C2"),
        ("C2", "C2", "C2"),
    ], "C3 owner table drift")
    require(all("only_legal_continuation" in row for row in cutpoints),
            "C3 cutpoint lacks continuation")
    require(c3.get("fixture", {}).get("hardware", {}).get("required_cutpoints")
            == ["H1 replacement-armed before MAP",
                "H2 handoff-closed before product publication",
                "H3 product-owned identity-specific Freezer roundtrip"],
            "C3 hardware cutpoint set drift")

    d3 = value.get("D3", {})
    require(d3.get("decision") == "single-independent-matrix-edge-source",
            "D3 decision drift")
    require(d3.get("pinned_source") == {
        "selector_register": "0xd614",
        "selector_value": 7,
        "peek_register": "0xd613",
        "active_low_mask": "0x80",
        "matrix_ordinal": 63,
        "normal_ascii": "0x03",
        "meaning": "physical RUN/STOP level independent of the typed event queue",
    }, "D3 source identity drift")
    require(d3.get("queue_fact", {}).get("total_events") == 5
            and d3["queue_fact"].get("buffered_slots") == 4,
            "D3 queue capacity drift")
    rules = "\n".join(d3.get("source_rule", []))
    require("only from the matrix edge source" in rules
            and "dequeued exactly once but is discarded as an abort source" in rules,
            "D3 single-source or duplicate suppression drift")
    require("no product-local keymap table" in d3.get("single_truth_rule", ""),
            "D3 second-keymap exclusion drift")

    e5 = value.get("E5", {})
    require(e5.get("decision") == "append-only-stable-depth-error",
            "E5 decision drift")
    error = e5.get("error", {})
    require(error.get("code") == 63
            and error.get("c_name") == "LISP65_ERR_C2_NESTING_DEPTH"
            and error.get("numeric_fallback") == "E3f"
            and error.get("detail") == {
                "kind": "fixnum",
                "value": 5,
                "meaning": "the refused transient depth; the configured maximum remains four",
            }, "E5 error identity/detail drift")
    require(e5.get("failure_order", [None])[0]
            == "read and authenticate the current transient depth",
            "E5 pre-mutation order drift")
    require(len(e5.get("state_postcondition", [])) == 7,
            "E5 exact-state surface drift")

    gate = value.get("review_gate", {})
    require(gate.get("implementation") == "blocked-until-all-four-decisions-are-reviewed"
            and gate.get("C1_hardware")
            == "blocked-until-C3-review-fixes-the-Freezer-handoff model",
            "review boundary drift")
    require(value.get("claim_limit", "").startswith("Contract draft"),
            "claim limit drift")


def validate_document(document: str) -> None:
    required = (
        "no implementation authorized",
        "No `lisp_poll`, `lisp_abort`, `longjmp`",
        "double-RESTORE",
        "does not\nenter the guest NMI vector",
        "`$D614` is fixed to segment 7",
        "dequeued but discarded as\n   an abort source",
        "LISP65_ERR_C2_NESTING_DEPTH",
        "Until all four are decided",
    )
    for phrase in required:
        require(phrase in document, f"review document misses: {phrase}")


def source_facts() -> dict[str, Any]:
    result = subprocess.run(
        ["git", "-C", str(CORE), "rev-parse", "HEAD"],
        capture_output=True, text=True, check=False,
    )
    require(result.returncode == 0 and result.stdout.strip() == CORE_COMMIT,
            "pinned core commit drift")
    matrix = text(CORE_MATRIX)
    mapper = text(CORE_MAPPER)
    iomapper = text(CORE_IOMAPPER)
    uart = text(CORE_UART)
    cpu = text(CORE_CPU)
    task = text(CORE_TASK)
    unfreeze = text(CORE_UNFREEZE)
    interrupt = text(INTERRUPT)
    window = text(WINDOW)
    product = text(PRODUCT)
    error_h = text(ERROR_H)

    require('63 => x"03", -- RUN/STOP' in matrix,
            "core ordinal 63 is not normal RUN/STOP $03")
    require("Bit#7 $7F" in mapper and "Run/Stop" in mapper,
            "core matrix segment/bit fact drift")
    require("if key_buffer_count < 4 then" in iomapper
            and "key_presenting <= '1';" in iomapper,
            "core five-event queue model drift")
    require('@IO:GS $D613 UARTMISC:KEYMATRIXPEEK' in uart
            and '@IO:GS $D614 UARTMISC:KEYMATRIXSEL' in uart,
            "core D613/D614 identity drift")
    require("Trap #66 ($42) = RESTORE key double-tap" in cpu,
            "Freezer trap identity drift")
    require("restore_press_trap:" in task and "jsr freeze_to_slot" in task,
            "Freezer entry source drift")
    require("@unfreezesyncwait:" in unfreeze
            and "sta hypervisor_enterexit_trigger" in unfreeze,
            "Freezer restore source drift")
    require('lisp_abort_static(LISP65_ERR_STOPPED, "stopped (run/stop)")' in interrupt,
            "current RUN/STOP longjmp surface drift")
    require("c2_kernal_window_poll" in window and "c2_kernal_nmi_handler" in window,
            "current queue/NMI window surfaces drift")
    require("C2D_MAX_TRANSIENT_DEPTH" in product
            and "depth >= C2D_MAX_TRANSIENT_DEPTH" in product,
            "current depth-four product check drift")
    require("LISP65_ERR_RUNTIME_FAMILY_STAGE = 62" in error_h
            and "LISP65_ERROR_CODE_LIMIT = 63" in error_h,
            "append-only E5 slot is no longer 63")

    return {
        "D3": {
            "matrix_ordinal_63": "normal ASCII/PETSCII identity $03",
            "matrix_position": "segment 7 active-low bit 7",
            "queue_capacity": {
                "presented_head": 1,
                "buffered": 4,
                "total": 5,
                "overflow": "new event not enqueued when key_buffer_count is 4",
            },
            "registers": {"selector": "0xd614", "peek": "0xd613"},
        },
        "C3": {
            "freezer_entry": "hypervisor trap 0x42 at instruction-fetch boundary",
            "guest_nmi": "separate vector surface",
            "unfreeze": "restores before hypervisor exit",
        },
        "E5": {
            "maximum_depth": 4,
            "last_existing_error_code": 62,
            "next_append_only_code": 63,
        },
        "B3": {
            "current_abort_surface": "lisp_poll -> lisp_abort_static(LISP65_ERR_STOPPED)",
            "current_transport_contract_seams": len(load(DMA)["covered_seams"]),
        },
    }


def mutation_tests(value: dict[str, Any]) -> list[str]:
    mutations: list[tuple[str, tuple[str, ...], Any]] = [
        ("B3-poll-in-flight", ("B3", "transport_state_machine", "1", "poll_or_longjmp"),
         "permitted"),
        ("B3-missing-safe-cutpoint", ("B3", "fixture", "cutpoints"), []),
        ("C3-SEI-masks-NMI", ("C3", "platform_distinction", "rule"),
         "SEI masks Freezer and NMI"),
        ("C3-H2-firmware-vector", ("C3", "cutpoints", "2", "vector_owner"),
         "firmware"),
        ("C3-missing-H2-hardware", ("C3", "fixture", "hardware", "required_cutpoints"),
         ["H1 replacement-armed before MAP", "H3 product-owned identity-specific Freezer roundtrip"]),
        ("D3-queue-source", ("D3", "decision"), "typed-queue-only"),
        ("D3-wrong-segment", ("D3", "pinned_source", "selector_value"), 6),
        ("D3-wrong-bit", ("D3", "pinned_source", "active_low_mask"), "0x40"),
        ("D3-second-keymap", ("D3", "single_truth_rule"), "product-local table"),
        ("E5-reuse-code", ("E5", "error", "code"), 43),
        ("E5-no-detail", ("E5", "error", "detail"), None),
        ("E5-mutation-before-check", ("E5", "failure_order", "0"),
         "publish journal"),
        ("review-early-implementation", ("review_gate", "implementation"), "authorized"),
    ]
    rejected: list[str] = []
    for name, path, replacement in mutations:
        candidate = copy.deepcopy(value)
        target: Any = candidate
        for token in path[:-1]:
            target = target[int(token)] if isinstance(target, list) else target[token]
        last = path[-1]
        if isinstance(target, list):
            target[int(last)] = replacement
        else:
            target[last] = replacement
        try:
            validate_contract(candidate)
        except ReviewError:
            rejected.append(name)
    require(len(rejected) == len(mutations),
            "one contract mutation survived")
    return rejected


def matrix_rows() -> dict[str, Any]:
    matrix = load(MATRIX)
    rows = {row["id"]: row for row in matrix.get("rows", [])}
    require(set(("B3", "C3", "D3", "E5")) <= rows.keys(),
            "matrix receipt lacks addendum rows")
    result: dict[str, Any] = {}
    for row_id in ("B3", "C3", "D3", "E5"):
        row = rows[row_id]
        require(row.get("status") == "OPEN"
                and row.get("disposition", {}).get("kind") == "addendum",
                f"matrix row {row_id} no longer requests an addendum")
        result[row_id] = {
            "crossing": row["crossing"],
            "accepted_disposition_source": row["disposition"]["proposed_action"],
            "closure_condition": row["disposition"]["closure_condition"],
            "draft_effect": "still OPEN pending line review and implementation",
        }
    return result


def main() -> int:
    try:
        value = load(CONTRACT)
        validate_contract(value)
        validate_document(text(DOCUMENT))
        facts = source_facts()
        rows = matrix_rows()
        mutations = mutation_tests(value)
        require(sha(PRG) == value["scope"]["product_identity"]["prg_sha256"],
                "Link-57 PRG identity drift")
        require(sha(ELF) == value["scope"]["product_identity"]["elf_sha256"],
                "Link-57 ELF identity drift")

        inputs = [
            Path(__file__).resolve(),
            CONTRACT, DOCUMENT, MATRIX, KERNAL, DMA, NESTED, ERRORS, ERROR_H,
            INTERRUPT, WINDOW, PRODUCT, CORE_MATRIX, CORE_MAPPER,
            CORE_IOMAPPER, CORE_UART, CORE_CPU, CORE_TASK, CORE_UNFREEZE,
            PRG, ELF,
        ]
        receipt = {
            "format": "lisp65-c2.2-cross-invariant-open-addenda-review-v1",
            "recorded_on": "2026-07-23",
            "status": "draft-bound-for-class-c-line-review",
            "scope": {
                "rows": ["B3", "C3", "D3", "E5"],
                "product_bytes_changed": 0,
                "capacity_effect_bytes": 0,
                "compiler_runs": 0,
                "product_links": 0,
                "hardware_runs": 0,
            },
            "bindings": {
                path.relative_to(ROOT).as_posix(): binding(path)
                for path in inputs
            },
            "source_facts": facts,
            "rows": rows,
            "proposed_decisions": {
                "B3": "defer one matrix-latched break through every submitted transport and deliver once at the first safe evaluator boundary",
                "C3": "separate hypervisor Freezer trap from guest NMI and bind map/vector/NMI owner plus exact continuation at H0-H3",
                "D3": "use the generated segment-7/bit-7 physical matrix edge as the sole abort source; discard queued $03 as an abort",
                "E5": "append stable code 63 with Fixnum-5 detail and reject before every mutation",
            },
            "negative_mutations": {
                "required": 13,
                "rejected": len(mutations),
                "names": mutations,
            },
            "review": {
                "required": ["B3", "C3", "D3", "E5"],
                "implementation": "blocked",
                "C1_hardware": "blocked-until-C3-reviewed",
                "matrix_gate": "blocked",
                "acceptance_chain": "blocked",
            },
            "value_string": (
                "OPEN-ADDENDA=DRAFT rows=B3,C3,D3,E5 "
                "D3=matrix7/bit7/queue5 E5=code63/detail5 "
                "mutations=13/13 product-delta=0 links=0 hardware=0 "
                "review=required acceptance=blocked"
            ),
            "claim_limit": value["claim_limit"],
        }
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n",
                       encoding="utf-8")
        print("c2-cross-invariant-open-addenda: DRAFT PASS "
              "rows=4 source-facts=4 mutations=13/13 "
              "product-delta=0 links=0 hardware=0")
        print(f"receipt={OUT.relative_to(ROOT)}")
        print(f"receipt_sha256={sha(OUT)}")
        return 0
    except (OSError, KeyError, ValueError, ReviewError) as exc:
        print(f"c2-cross-invariant-open-addenda: FAIL {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
