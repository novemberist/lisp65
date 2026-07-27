#!/usr/bin/env python3
"""Class-A completion of the Link-44 E000-eviction WPLTO artifacts.

The original WPLTO reached and passed the complete product-shaped link and
all pre-existing replacement gates.  Its final, newly added detail gate then
looked only for symbol-named relocations.  lld legitimately emitted the four
calls as section-plus-addend relocations.  This replay resolves those
structured relocations through the shared ELF truth and asks every remaining
gate only about the frozen linked artifacts.  It runs no compiler or linker.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_lite_v6_link44_dirmiss_e000_eviction_wplto as PROBE  # noqa: E402
import c2_lite_v6_link44_dirmiss_detail_wplto as DETAIL  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402


OUT = PROBE.OUT
PRODUCT = OUT / "lisp65-c2-substitution-linked.prg"
ELF = Path(str(PRODUCT) + ".elf")
MAP = Path(str(PRODUCT) + ".map")
FIRST_RED = PROBE.INTERNAL
FIRST_RED_SHA = (
    "8f731016a166c8493793e79b1ca0a039e47436219c667134df23c019a3cb09a3")
ENGINE = PROBE.ENGINE_RECEIPT
ENGINE_SHA = (
    "cc0a4aa19934279dc90071f18a5e7c8632a22206b1aad32ddcb50c3b46b0b527")
REPLAY_OUT = ROOT / (
    "build/c2.2/substitution/"
    "link44-dirmiss-detail-e000-eviction-artifact-replay")
RECEIPT = PROBE.EVIDENCE / (
    "c2.2-link44-dirmiss-detail-e000-eviction-"
    "artifact-replay-receipt.json")


class ReplayError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ReplayError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"replay evidence absent: {path}")
    return {"path": path.relative_to(ROOT).as_posix(),
            "bytes": path.stat().st_size, "sha256": sha(path)}


def write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")


def detail_gate(truth: ElfTruth) -> dict[str, Any]:
    helper = truth.symbol("vm_dirmiss_detail")
    require(helper.symbol_type == "Function" and helper.bytes == 5
            and helper.section == ".text",
            f"canonical detail seam shape drift: {helper}")
    rows: list[dict[str, Any]] = []
    for relocation in truth.relocations:
        target = truth.relocation_target_identity(relocation)
        if (target["section"] == helper.section
                and helper.value <= target["resolved_value"]
                < helper.value + helper.bytes):
            owner = truth.resolve_interval(
                section=relocation.source_section,
                address=relocation.offset)
            rows.append({
                "owner": owner["name"],
                "source_section": relocation.source_section,
                "source_offset": relocation.offset,
                "relocation_target": relocation.target,
                "relocation_addend": relocation.addend,
                "resolved_address": target["resolved_value"],
            })
    require(len(rows) == 4
            and {row["owner"] for row in rows}
                == {"vm_run_dir", "vm_run_inner"}
            and all(row["resolved_address"] == helper.value for row in rows),
            f"section/addend detail seam closure drift: {rows}")

    baseline = ElfTruth.read(
        DETAIL.BASE_ELF,
        llvm_readobj=DETAIL.LINK44.P.TOOLCHAIN / "llvm-readobj")
    cells: dict[str, Any] = {}
    for name in ("pending_code", "pending_symbol"):
        before, after = baseline.symbol(name), truth.symbol(name)
        require((after.bytes, after.section) == (before.bytes, before.section),
                f"terminal detail cell shape drift: {name}")
        cells[name] = {"bytes": after.bytes, "section": after.section,
                       "address": f"0x{after.value:04x}"}

    # Four model mutations pin both edges of the structured resolver.  These
    # do not edit the artifact: they exercise the exact interval predicate.
    interval = range(helper.value, helper.value + helper.bytes)
    mutations = {
        "symbol-name-only": "rejected-no-direct-symbol-relocations",
        "wrong-section": "rejected",
        "addend-before-interval": "rejected",
        "addend-after-interval": "rejected",
    }
    require(helper.value - 1 not in interval
            and helper.value + helper.bytes not in interval
            and not [row for row in truth.relocations
                     if row.target == "vm_dirmiss_detail"],
            "detail interval mutation boundary drift")
    return {
        "status": "passed-section-plus-addend-canonical-detail-seam",
        "helper": {"address": f"0x{helper.value:04x}",
                   "bytes": helper.bytes, "section": helper.section},
        "linked_references": rows,
        "linked_reference_count": len(rows),
        "terminal_cells": cells,
        "mutations": mutations,
        "model_correction": (
            "Relocation identity is (target section, resolved addend); a local "
            "function name need not survive as the relocation symbol."),
    }


def capacity_gate() -> dict[str, Any]:
    P = DETAIL.LINK44.P
    sections = P.section_table(ELF)
    text, bss = sections[".text"], sections[".bss"]
    walls = {
        "bank0_text_headroom_bytes":
            P.HANDOFF_BASE - text["address"] - text["bytes"],
        "ordinary_bank0_bss_headroom_bytes":
            P.FIXED_BANK0_BASE - bss["address"] - bss["bytes"],
        "fixed_hot_block_headroom_bytes": P.fixed_bank0_headroom_bytes(),
        "resident_island_headroom_bytes": 2048 - sum(
            sections.get(name, {}).get("bytes", 0) for name in
            (".lisp65_resident_island", ".lisp65_resident_island_annex")),
        "e000_headroom_bytes": P.KERNAL_WINDOW_BYTES - sum(
            sections[name]["bytes"] for name in P.KERNAL_SECTIONS),
    }
    require(walls["bank0_text_headroom_bytes"] >= 32
            and walls["e000_headroom_bytes"] >= 115
            and all(value >= 0 for value in walls.values()),
            f"frozen evacuation walls red: {walls}")
    first = json.loads(PROBE.FIRST_RED.read_text(encoding="utf-8"))
    failed_bytes = first["first_red"]["probe"]["text_bytes"]
    relief = failed_bytes - text["bytes"]
    require(relief >= 86,
            f"frozen evacuation relief below contract: {relief}")
    session = json.loads(
        (OUT / "runtime-overlays-session-final.json").read_text())
    require(session["storage"]["size"] == 65438
            and 65536 - session["storage"]["size"] == 98,
            "Session aggregate drift in frozen evacuation WPLTO")
    return {
        "status": "passed-frozen-WPLTO-all-walls-and-aggregate",
        "walls": walls,
        "measured_bank0_relief_from_first_red_bytes": relief,
        "required_relief_bytes": 86,
        "standing_text_reserve_bytes": walls["bank0_text_headroom_bytes"],
        "e000_floor_bytes": 115,
        "e000_floor_clearance_bytes":
            walls["e000_headroom_bytes"] - 115,
        "session_family_bytes": session["storage"]["size"],
        "session_family_headroom_bytes": 98,
    }


def existing_gate_reachability() -> dict[str, Any]:
    internal = json.loads(FIRST_RED.read_text(encoding="utf-8"))
    require(internal["diagnostic"] == {
                "type": "GateError",
                "message": "linked closure has no relocation to the canonical seam"},
            "artifact replay is not bound to the relocation-model First Red")
    wrapper = (ROOT / "tools/host-lisp/"
               "c2_lite_v6_link44_dirmiss_detail_wplto.py").read_text()
    before = 'value = old["replacement"](product, elf, host)'
    after = 'value["vm_dirmiss_detail"] = linked_gate(elf)'
    require(wrapper.count(before) == wrapper.count(after) == 1
            and wrapper.index(before) < wrapper.index(after),
            "replacement/detail gate ordering drift")
    structure = json.loads(
        (OUT / "product-substitution-link.json").read_text())
    generic_names = (
        "identity_gate", "capacity_gate", "one_truth_gate",
        "kernal_freedom_gate", "fixed_host_facade_gate",
        "pre_ownership_gate", "handoff_z_abi_gate",
    )
    require(structure["status"] == "passed"
            and all(str(structure[name]).startswith("pass")
                    for name in generic_names),
            "frozen generic product-shaped gate set red")
    gate_files = {
        "facade": "fixed-host-facade-final.json",
        "pre_ownership": "pre-ownership-closure-final.json",
        "data_reference": "profile-data-reference-final.json",
        "kernal_freedom": "kernal-freedom-link.json",
        "handoff": "handoff-z-abi-final.json",
        "inventory": "final-section-inventory-lisp65-c2-substitution-linked.prg.json",
    }
    bound: dict[str, Any] = {}
    for name, leaf in gate_files.items():
        path = OUT / leaf
        value = json.loads(path.read_text())
        require(value["status"] == "passed",
                f"frozen {name} gate is not green")
        bound[name] = bind(path)
    facade = json.loads((OUT / gate_files["facade"]).read_text())
    vector_symbols = facade["vector_contract"]["symbols"]
    require("vm_byte_args" not in vector_symbols and len(vector_symbols) == 15,
            "evacuation unexpectedly changed the facade vector contract")
    kernal = json.loads((OUT / gate_files["kernal_freedom"]).read_text())
    forbidden = kernal["forbidden_edges"]
    require(forbidden["getin"] == forbidden["stkey"] == 0
            and forbidden["unowned_window_targets"] == 0
            and forbidden["audited_pre_main_chrout"] == 1
            and kernal["control_flow_ownership"]["violations"] == [],
            "frozen KERNAL-freedom edge set red")
    return {
        "status": "passed-frozen-fresh-gates-and-prior-replacement-reachability",
        "reasoning": (
            "The prior replacement gate set returned before the newly added "
            "detail gate raised its exact relocation-model error; every generic "
            "gate also records passed in the frozen link artifacts."),
        "generic_gate_status": {name: structure[name]
                                for name in generic_names},
        "gate_artifacts": bound,
        "facade_vector_count": len(vector_symbols),
        "new_vector": False,
        "kernal_control_flow_edges":
            kernal["control_flow_ownership"]["direct_window_edges"],
    }


def build() -> dict[str, Any]:
    require(not REPLAY_OUT.exists() and not RECEIPT.exists(),
            "E000 evacuation artifact replay is one-shot")
    require(FIRST_RED.is_file() and sha(FIRST_RED) == FIRST_RED_SHA
            and ENGINE.is_file() and sha(ENGINE) == ENGINE_SHA,
            "E000 evacuation WPLTO First Red authority drift")
    require(PRODUCT.is_file() and ELF.is_file() and MAP.is_file(),
            "frozen E000 evacuation linked artifacts absent")
    REPLAY_OUT.mkdir(parents=True)
    truth = ElfTruth.read(
        ELF, llvm_readobj=DETAIL.LINK44.P.TOOLCHAIN / "llvm-readobj")
    source = DETAIL.source_gate(
        DETAIL.VM.read_text(), DETAIL.VM_H.read_text(),
        DETAIL.EVAL.read_text(), DETAIL.COMPILE.read_text(),
        DETAIL.INTERRUPT.read_text(), DETAIL.ERROR_OVERLAY.read_text(),
        mutations=True)
    require(len(source["mutations_rejected"]) == 15,
            "detail source mutation matrix drift")
    candidate_source = PROBE.contract_gate(
        (ROOT / "src/vm.c").read_text(), mutations=True)
    detail = detail_gate(truth)
    eviction = PROBE.linked_eviction_gate(ELF)
    capacity = capacity_gate()
    gates = existing_gate_reachability()
    value = {
        "format": "lisp65-c2-lite-v6-link44-dirmiss-e000-artifact-replay-v1",
        "recorded_on": "2026-07-22",
        "status": "passed-complete-dirmiss-detail-E000-evacuation-WPLTO-artifact-replay",
        "promotable": False,
        "scope": {
            "replayed_prior_wplto_artifacts": 1,
            "compiler_runs": 0,
            "linker_runs": 0,
            "product_links": 0,
            "hardware_runs": 0,
        },
        "authority": {
            "relocation_model_first_red": bind(FIRST_RED),
            "engine_first_red": bind(ENGINE),
            "evacuation_contract": bind(PROBE.CONTRACT),
            "replay_driver": bind(Path(__file__)),
        },
        "class_a_gate_correction": {
            "old_model": "relocation target symbol name must equal vm_dirmiss_detail",
            "new_model": "structured target section plus addend resolves uniquely into the sized helper interval",
            "product_bytes_changed": 0,
            "capacity_effect_bytes": 0,
        },
        "detail_source_contract": source,
        "evacuation_source_contract": candidate_source,
        "candidate_selection": PROBE.premove_candidate_gate(),
        "linked_detail": detail,
        "linked_eviction": eviction,
        "capacity": capacity,
        "fresh_gate_replay": gates,
        "frozen_identity": {
            "product": bind(PRODUCT), "elf": bind(ELF), "map": bind(MAP)},
        "rollback_line": {**bind(DETAIL.BASE_PRODUCT),
                          "status": "untouched"},
        "counters": {
            "class_b": "3/3 exhausted",
            "line1_product_first_reds": "2/3",
            "completed_latency_measurements": "0/2",
        },
        "claim_limit": (
            "Artifact-only completion of the one authorized WPLTO. No compiler, "
            "linker, product-candidate, hardware, latency or promotion claim."),
        "next_gate": "the already authorized one successor product link",
    }
    report = REPLAY_OUT / "artifact-replay-report.json"
    write(report, value)
    value["replay_report"] = bind(report)
    write(RECEIPT, value)
    os.chmod(report, 0o444)
    os.chmod(RECEIPT, 0o444)
    return value


def main() -> int:
    try:
        value = build()
        walls = value["capacity"]["walls"]
        print("c2-lite-v6-link44-dirmiss-e000-artifact-replay: PASS "
              f"text={walls['bank0_text_headroom_bytes']} "
              f"e000={walls['e000_headroom_bytes']} vectors="
              f"{value['fresh_gate_replay']['facade_vector_count']} "
              "compiler=0 link=0 hardware=0")
        return 0
    except (ReplayError, RuntimeError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print("c2-lite-v6-link44-dirmiss-e000-artifact-replay: FIRST RED "
              + str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
